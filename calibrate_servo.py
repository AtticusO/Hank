## calibrate_servo.py — find one servo's real pulse-width range (fixes.md §3.2.4).
##
##   python calibrate_servo.py shoulder
##
## Starts at the pulse width the joint is at in its HOME pose (so it doesn't
## jump), then you creep it outward:
##   +  / -      10 µs step         ++ / --   50 µs step
##   1500        go to an exact pulse width in µs (500–2500)
##   min / max   record the current pulse as that end of the range
##   q           quit and print the line to paste into config.PULSE_WIDTHS
##
## Creep slowly. Stop the moment the servo buzzes/strains or the arm touches
## anything — that is its mechanical stop; back off ~20 µs and record that.
## Don't run this while Hank (main.py) is running: both would drive the pin.

import sys

import config

STEPS = {"+": 10, "-": -10, "++": 50, "--": -50}


def home_pulse_us(name):
    lo, hi = config.PULSE_WIDTHS[name]
    angle = config.HOME[name]
    return int(round((lo + (angle + 90) / 180.0 * (hi - lo)) * 1e6))


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in config.SERVO_PINS:
        raise SystemExit(f"usage: python calibrate_servo.py {{{'|'.join(config.SERVO_PINS)}}}")
    name = sys.argv[1]
    if config.MOCK:
        raise SystemExit("HANK_MOCK=1 is set — calibration needs the real servo")
    import pigpio
    pi = pigpio.pi()
    if not pi.connected:
        raise SystemExit("Can't reach pigpiod — sudo systemctl enable --now pigpiod")
    pin = config.SERVO_PINS[name]
    pw = home_pulse_us(name)
    lo_rec, hi_rec = None, None
    pi.set_servo_pulsewidth(pin, pw)
    print(f"{name} on GPIO{pin} at {pw} µs (its HOME pose). Commands: + - ++ -- <µs> min max q")
    try:
        while True:
            cmd = input(f"[{pw} µs] > ").strip().lower()
            if cmd in STEPS:
                pw += STEPS[cmd]
            elif cmd.isdigit():
                pw = int(cmd)
            elif cmd == "min":
                lo_rec = pw
                print(f"min = {pw} µs")
                continue
            elif cmd == "max":
                hi_rec = pw
                print(f"max = {pw} µs")
                continue
            elif cmd in ("q", "quit"):
                break
            else:
                print("Commands: + - ++ -- <µs> min max q")
                continue
            pw = max(500, min(2500, pw))
            pi.set_servo_pulsewidth(pin, pw)
    except (KeyboardInterrupt, EOFError):
        pass
    finally:
        pi.set_servo_pulsewidth(pin, 0)      # go limp
        pi.stop()
    if lo_rec and hi_rec:
        lo_rec, hi_rec = sorted((lo_rec, hi_rec))
        print(f'\nPut this in config.PULSE_WIDTHS:\n    "{name}": ({lo_rec / 1000:.3f} / 1000, {hi_rec / 1000:.3f} / 1000),')
        print("Note: changing the range changes what every angle means. Re-check HOME, the gestures "
              "and LIMITS for this joint afterwards.")
    else:
        print("Record both 'min' and 'max' to get a config line.")


if __name__ == "__main__":
    main()
