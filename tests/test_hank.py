## Hank's tests — no hardware needed (servos are mocked).
##   python -m unittest discover tests        (from the repo root)

import os
import sys
import time
import types
import unittest
import py_compile
import glob

os.environ["HANK_MOCK"] = "1"                      # never touch real servos from tests
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import config        # noqa: E402
import personality   # noqa: E402
import server        # noqa: E402
import gestures      # noqa: E402
import servo_ops     # noqa: E402
from servo_worker import ServoWorker  # noqa: E402


class SyntaxGate(unittest.TestCase):
    ## py_compile every module, including the Pi-only ones (§5.4)
    def test_all_modules_compile(self):
        for path in glob.glob(os.path.join(ROOT, "*.py")):
            with self.subTest(path=os.path.basename(path)):
                py_compile.compile(path, doraise=True)


class ControlLaw(unittest.TestCase):
    def test_right_of_centre_turns_waist_down(self):
        b = personality.bearing(600, waist_at_capture=0)
        self.assertLess(personality.waist_correction(b, 0.0, 0.0), 0.0)

    def test_left_of_centre_turns_waist_up(self):
        b = personality.bearing(40, waist_at_capture=0)
        self.assertGreater(personality.waist_correction(b, 0.0, 0.0), 0.0)

    def test_deadband_holds(self):
        b = personality.bearing(config.FRAME_W / 2 + 3, waist_at_capture=10)
        self.assertEqual(personality.waist_correction(b, 0.0, 10.0), 10.0)

    def test_lead_exceeds_static_correction(self):
        b = personality.bearing(500, waist_at_capture=0)
        static = personality.waist_correction(b, 0.0, 0.0)
        moving = personality.waist_correction(b, -40.0, 0.0)      # moving further right
        self.assertLess(moving, static)

    def test_bearing_cancels_arm_motion(self):
        ## same person, arm turned 10° toward them: pixel shifts, bearing doesn't
        dpp = config.FOV_X_DEG / config.FRAME_W
        a = personality.bearing(500, waist_at_capture=0)
        b = personality.bearing(500 - 10 / dpp, waist_at_capture=-10)
        self.assertAlmostEqual(a, b, places=6)

    def test_pitch_target_above_centre_raises(self):
        self.assertGreater(personality.pitch_correction(50), 0)
        self.assertLess(personality.pitch_correction(430), 0)
        self.assertEqual(personality.pitch_correction(config.FRAME_H / 2), 0)


class Worker(unittest.TestCase):
    def setUp(self):
        self.servos = servo_ops.move()
        self.w = ServoWorker(self.servos)

    def tearDown(self):
        self.w.stop()

    def test_mock_selected(self):
        self.assertEqual(type(self.servos).__module__, "mock_servos")

    def test_clamp_and_sync(self):
        self.w.set_target("waist", 400)
        self.assertEqual(self.w.get_targets()["waist"], 90)
        self.assertTrue(self.w.wait_idle(5, tol=0.01))
        self.assertEqual(self.servos.angles["waist"], 90)

    def test_lands_exactly(self):
        self.w.set_target("elbow", -12.5)
        self.w.wait_idle(5, tol=0.0)
        self.assertEqual(self.servos.angles["elbow"], -12.5)

    def test_gesture_final_pose_becomes_target(self):
        self.w.play_gesture(*gestures.get("curl"), wait=True)
        self.assertEqual(self.w.get_targets(), {"waist": 0, "shoulder": 0, "elbow": 90})
        time.sleep(0.2)
        self.assertEqual(self.servos.angles["elbow"], 90)      # no glide back

    def test_none_holds_joint(self):
        self.w.set_targets([10, 20, 30])
        self.w.wait_idle(5, tol=0.0)
        self.w.play_gesture([[None, None, -30]], [0], wait=True)
        self.assertEqual(self.w.get_angles(), {"waist": 10, "shoulder": 20, "elbow": -30})

    def test_busy_while_gesture_queued(self):
        done = self.w.play_gesture(*gestures.get("jab"), wait=False)
        self.assertTrue(self.w.busy())
        done.wait(5)
        self.assertFalse(self.w.busy())


class Dance(unittest.TestCase):
    def test_swing_period_locks_to_beat(self):
        import orientation
        arm = orientation.positions()
        try:
            peaks, last = [], None
            t0 = time.monotonic()

            def keep():
                nonlocal last
                a = arm.angles()["waist"]
                side = 1 if a > 0 else -1
                if abs(abs(a) - config.DANCE_AMPLITUDE) < 0.01 and side != last:
                    peaks.append(time.monotonic())
                    last = side
                return time.monotonic() - t0 < 3.2

            arm.dance(120, keep_going=keep)
            gaps = [b - a for a, b in zip(peaks, peaks[1:])]
            self.assertGreaterEqual(len(gaps), 3)
            self.assertAlmostEqual(sum(gaps) / len(gaps), 0.5, delta=0.05)  # 120 BPM = 0.5 s per swing
            self.assertFalse(arm.dancing.is_set())
        finally:
            arm.stop()


class Queue(unittest.TestCase):
    def setUp(self):
        self.played = []
        self.now = None
        fake = types.SimpleNamespace(
            play=lambda uri: (self.played.append(uri),
                              setattr(self, "now", {"is_playing": True, "progress_ms": 10,
                                                     "duration_ms": 200000})),
            now_playing=lambda: self.now, MusicError=Exception)
        self._real = server.music
        server.music = fake
        server.queue.clear()
        server._last_started = 0.0

    def tearDown(self):
        server.music = self._real
        server.queue.clear()

    def test_idle_plays_immediately_then_queues(self):
        server.enqueue({"uri": "a"})
        server.enqueue({"uri": "b"})
        self.assertEqual(self.played, ["a"])
        self.assertEqual([e["uri"] for e in server.queue], ["b"])

    def test_song_end_advances(self):
        server.enqueue({"uri": "a"})
        server.enqueue({"uri": "b"})
        server._last_started -= 10
        self.now = {"is_playing": False, "progress_ms": 0, "duration_ms": 200000}
        server.advance_once()
        self.assertEqual(self.played, ["a", "b"])

    def test_pause_mid_song_does_not_advance(self):
        server.enqueue({"uri": "a"})
        server.enqueue({"uri": "b"})
        server._last_started -= 10
        self.now = {"is_playing": False, "progress_ms": 60000, "duration_ms": 200000}
        server.advance_once()
        self.assertEqual(self.played, ["a"])

    def test_no_double_advance_right_after_start(self):
        server.enqueue({"uri": "a"})
        server.enqueue({"uri": "b"})
        self.now = {"is_playing": False, "progress_ms": 0, "duration_ms": 200000}  # stale state
        server.advance_once()
        self.assertEqual(self.played, ["a"])


class Tracking(unittest.TestCase):
    def setUp(self):
        import orientation
        self.arm = orientation.positions()
        self.p = personality.acts(self.arm)
        self.p.person_time = time.time()                 # no greeting wave during the test

    def tearDown(self):
        self.arm.stop()

    def test_locks_one_person_not_the_average(self):
        big, small = [400, 100, 600, 450], [0, 100, 60, 160]
        self.p.follow(["person", "person"], [big, small], ids=[7, 8], pose=self.arm.angles())
        self.assertEqual(self.p.lock_id, 7)
        self.assertLess(self.arm.orient["waist"], 0)      # aimed at the big one (right of centre)

    def test_holds_when_locked_target_briefly_hidden(self):
        self.p.follow(["person"], [[400, 100, 600, 450]], ids=[7], pose=self.arm.angles())
        before = self.arm.orient["waist"]
        self.p.follow(["person"], [[0, 100, 60, 160]], ids=[8], pose=self.arm.angles())
        self.assertEqual(self.arm.orient["waist"], before)
        self.assertEqual(self.p.lock_id, 7)

    def test_cup_when_nobody_there(self):
        self.p.follow(["cup"], [[0, 200, 80, 280]], ids=[3], pose=self.arm.angles())
        self.assertEqual(self.p.lock_tag, "cup")
        self.assertGreater(self.arm.orient["waist"], 0)   # cup on the left


class Ps5(unittest.TestCase):
    def setUp(self):
        import orientation
        import ps5_controls
        self.st = types.SimpleNamespace(
            cross=False, circle=False, square=False, triangle=False, DpadUp=False, DpadDown=False,
            options=False, share=False, L1=False, R1=False, L2=False, R2=False,
            L2_value=0, R2_value=0, LX=0, LY=0, RX=0, RY=0)
        self.arm = orientation.positions()
        self.c = ps5_controls.Controller(self.arm, ps5=types.SimpleNamespace(state=self.st, close=lambda: 0))

    def tearDown(self):
        self.arm.stop()

    def test_light_trigger_touch_ignored(self):
        self.st.L2, self.st.L2_value = True, 10
        self.c.remote()
        self.assertEqual(self.arm.orient["waist"], 0)

    def test_held_button_fires_once(self):
        self.st.cross = True
        for _ in range(10):
            self.c.remote()
        self.assertEqual(self.arm.worker._pending, 1)

    def test_shoulder_uses_stick_y(self):
        self.st.LX = 127
        self.c.remote()
        self.assertEqual(self.arm.orient["shoulder"], 70)
        self.st.LX, self.st.LY = 0, -127
        self.c.remote()
        self.assertLess(self.arm.orient["shoulder"], 70)


class Keyboard(unittest.TestCase):
    ## Fake evdev device: a pipe makes select() see input; read() hands back events
    def test_press_keys_fire_once_and_hold_keys_repeat(self):
        try:
            import evdev  # noqa: F401
        except ImportError:
            self.skipTest("evdev is Linux only")
        import orientation
        DOWN, UP = 1, 0
        arm = orientation.positions()
        r, w = os.pipe()
        pending = []

        def read():
            os.read(r, 1)
            out = [types.SimpleNamespace(type=1, code=c, state=st) for c, st in pending]
            pending.clear()
            return out

        def feed(*events):
            pending.extend(events)
            os.write(w, b"x")

        dev = types.SimpleNamespace(fd=r, path="fake", name="fake", read=read)
        fired = []
        arm.gesture = lambda name, wait=True: fired.append(name)
        try:
            k = orientation.KeyboardControl(arm, dev=dev)
            k._ecodes = types.SimpleNamespace(EV_KEY=1)
            k._categorize = lambda e: types.SimpleNamespace(keycode=e.code, keystate=e.state,
                                                             key_down=DOWN, key_up=UP)
            feed(("KEY_R", DOWN))
            for _ in range(6):                        # R held for 6 ticks
                k.step()
            self.assertEqual(fired, ["reset"])        # once, not every tick (#21)
            feed(("KEY_R", UP), ("KEY_RIGHT", DOWN))
            for _ in range(3):                        # RIGHT held for 3 ticks
                k.step()
            self.assertEqual(arm.orient["waist"], 15) # 3 ticks x 5°
            feed(("KEY_ESC", DOWN))
            k.step()
            self.assertTrue(k.quit)
        finally:
            os.close(r)
            os.close(w)
            arm.stop()


if __name__ == "__main__":
    unittest.main()
