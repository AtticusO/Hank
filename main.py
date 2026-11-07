## main.py — Hank, everything in one process.
##
##   python main.py                          bartender: vision + tracking + music page
##   python main.py --mode keys              keyboard jog   (also: ps5, server, off)
##   python main.py --no-display             no camera window (SSH / systemd)
##   python main.py --mock                   don't move servos (laptop / bench testing)
##   python main.py --buttons                GPIO mode buttons + status LED (pins in config.py)
##   python main.py --distance               use the ultrasonic sensor (lean in when close)
##
## Ownership (fixes.md §7.1):
##   cam_ops.Cam         camera reader thread
##   ServoWorker         servo thread — the ONLY thing touching servos
##   vision loop         main thread: YOLO -> personality -> worker targets
##   music server        ThreadingHTTPServer daemon (page + queue + dance)
##   DanceController     watcher thread: song -> BPM -> dance
##   mode manager        --mode / GPIO buttons; switching never needs a restart

import argparse
import logging
import os
import signal
import sys
import time

MODES = ("bartender", "keys", "ps5", "server", "off")
CYCLE = ("bartender", "keys", "ps5", "off")          # what the mode button steps through

log = logging.getLogger("hank")


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="Hank the robot bartender")
    ap.add_argument("--mode", choices=MODES, default="bartender")
    ap.add_argument("--no-display", action="store_true", help="no camera preview window")
    ap.add_argument("--no-server", action="store_true", help="don't start the music page")
    ap.add_argument("--mock", action="store_true", help="simulate the servos (same as HANK_MOCK=1)")
    ap.add_argument("--buttons", action="store_true", help="enable GPIO mode buttons + status LED")
    ap.add_argument("--distance", action="store_true", help="enable the ultrasonic distance sensor")
    ap.add_argument("-v", "--verbose", action="store_true")
    return ap.parse_args(argv)


class Hank:
    ## Hank owns every piece of hardware exactly once and shares references;
    ## creating a second Cam or servo stack crashes on the Pi
    def __init__(self, args=None):
        import config
        import orientation
        self.config = config
        self.args = args or parse_args([])
        self.mode = self.args.mode
        self.running = True
        self.display = (not self.args.no_display and
                        bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")
                             or sys.platform == "win32"))
        self.factory = self._pigpio_factory()
        self.arm = orientation.positions(factory=self.factory)
        self.cam = self.detector = self.pers = None
        self.keys = self.ps5 = None
        self.dist = None
        self.server = self.dancer = None
        self.led = None
        self._last_frame = -1
        self._frames = 0

    def _pigpio_factory(self):
        ## One factory shared by servos, distance sensor and buttons
        if self.config.MOCK:
            return None
        try:
            from gpiozero.pins.pigpio import PiGPIOFactory
            return PiGPIOFactory()
        except ImportError:
            return None
        except Exception as e:
            raise RuntimeError(f"Can't reach pigpiod ({e}). Start it: "
                               "sudo systemctl enable --now pigpiod") from e

    ## ------------------------------------------------- lazily built pieces
    def _ensure_vision(self):
        if self.cam is None:
            import cam_ops
            import obj_detection
            import personality
            self.cam = cam_ops.Cam(0)
            self.detector = obj_detection.detect()
            self.pers = personality.acts(self.arm)
            if self.args.distance:
                import distance
                self.dist = distance.make(self.factory)

    def _ensure_keys(self):
        if self.keys is None:
            from orientation import KeyboardControl
            self.keys = KeyboardControl(self.arm)

    def _ensure_ps5(self):
        if self.ps5 is None:
            import ps5_controls
            self.ps5 = ps5_controls.Controller(self.arm)

    def start_music(self):
        import dance
        import server
        self.dancer = dance.DanceController(self.arm)
        server.attach_dance(self.dancer)
        try:
            self.server = server.start_server(background=True)
        except OSError as e:
            log.error("Music server failed to start: %s", e)

    ## ------------------------------------------------------------- modes
    def set_mode(self, mode):
        if mode != self.mode:
            log.info("Mode: %s -> %s", self.mode, mode)
            self.mode = mode
            self._show_mode()

    def cycle_mode(self):
        i = CYCLE.index(self.mode) if self.mode in CYCLE else -1
        self.set_mode(CYCLE[(i + 1) % len(CYCLE)])

    def _show_mode(self):
        if self.led is not None:
            n = (CYCLE.index(self.mode) + 1) if self.mode in CYCLE else 1
            self.led.blink(on_time=0.2, off_time=0.3, n=n, background=True)

    def _setup_buttons(self):
        from gpiozero import LED, Button
        c = self.config
        self.mode_btn = Button(c.BUTTON_MODE_PIN, bounce_time=0.05, pin_factory=self.factory)
        self.select_btn = Button(c.BUTTON_SELECT_PIN, bounce_time=0.05, hold_time=1.5,
                                 pin_factory=self.factory)
        self.led = LED(c.STATUS_LED_PIN, pin_factory=self.factory)
        self.mode_btn.when_pressed = self.cycle_mode
        self.select_btn.when_held = lambda: self.arm.reset(wait=False)   # long press = reset
        log.info("Buttons: GPIO%s = mode, GPIO%s (hold) = reset, LED on GPIO%s",
                 c.BUTTON_MODE_PIN, c.BUTTON_SELECT_PIN, c.STATUS_LED_PIN)
        self._show_mode()

    ## ------------------------------------------------------- vision loop
    def video_step(self):
        self._ensure_vision()
        count, frame, stamp = self.cam.read()
        if frame is None or count == self._last_frame:   # don't re-run YOLO on the same frame
            time.sleep(0.005)
            return
        self._last_frame = count
        pose = self.arm.angles()                         # arm pose at ~capture time
        annotated, tags, cords, ids = self.detector.detection(frame, draw=self.display)
        self.pers.follow(tags, cords, ids, pose=pose, capture_t=stamp)
        self._frames += 1
        if self.dist is not None and self._frames % 5 == 0:
            self.pers.pers_condit(tags, cords, self.dist.dist())
        if self.display:
            import cv2
            cv2.imshow("Hank View", annotated)
            if cv2.waitKey(1) == ord('q'):
                self.running = False

    def step(self):
        m = self.mode
        if m == "bartender":
            self.video_step()
        elif m == "keys":
            self._ensure_keys()
            self.keys.step(timeout=0.05)
            if self.keys.quit:
                self.running = False
        elif m == "ps5":
            self._ensure_ps5()
            self.ps5.remote()
            time.sleep(self.ps5.TICK)
            if self.ps5.cancel:
                self.running = False
        else:                                            # server / off: background threads only
            time.sleep(0.2)

    def run(self):
        signal.signal(signal.SIGTERM, lambda *_: setattr(self, "running", False))
        try:
            if not self.args.no_server:
                self.start_music()
            if self.args.buttons:
                self._setup_buttons()
            if self.mode == "keys":
                self.arm.reset()
            log.info("Hank running in %s mode%s", self.mode, "" if self.display else " (no display)")
            while self.running:
                self.step()
        except KeyboardInterrupt:
            pass
        finally:
            self.shutdown()

    def shutdown(self):
        log.info("Shutting down")
        if self.dancer is not None:
            self.dancer.stop()
        self.arm.stop()
        if self.cam is not None:
            self.cam.stop()
        if self.display:
            try:
                import cv2
                cv2.destroyAllWindows()
            except Exception:
                pass
        if self.ps5 is not None:
            self.ps5.close()
        if self.server is not None:
            self.server.shutdown()


if __name__ == "__main__":
    args = parse_args()
    if args.mock:
        os.environ["HANK_MOCK"] = "1"      # must be set before config is imported
    import config
    config.setup_logging(args.verbose)
    log.info("Executing Hank Protocols")
    Hank(args).run()
