import select
from evdev import InputDevice, list_devices, categorize, ecodes


def find_keyboard():
    """Return the main keyboard device (has letter keys + arrows),
    skipping media/consumer-control sub-devices."""
    for path in list_devices():
        dev = InputDevice(path)
        keys = dev.capabilities().get(ecodes.EV_KEY, [])
        if ecodes.KEY_A in keys and ecodes.KEY_UP in keys:
            return dev
    raise RuntimeError("No keyboard found in /dev/input")


def listen():
    """Hold-aware loop: tracks which keys are currently held and acts
    repeatedly while they stay down, independent of OS key-repeat rate."""
    dev = find_keyboard()
    print(f"Listening on {dev.path} ({dev.name})")
    held = set()

    while True:
        # Wait up to 0.05s for input; returns immediately if a key event is ready.
        r, _, _ = select.select([dev.fd], [], [], 0.05)
        if r:
            for event in dev.read():
                if event.type != ecodes.EV_KEY:
                    continue
                key = categorize(event)
                if key.keystate == key.key_down:
                    held.add(key.keycode)
                elif key.keystate == key.key_up:
                    held.discard(key.keycode)

        if "KEY_ESC" in held:
            break

        # This block runs ~20x/sec for as long as a key stays held.
        if "KEY_UP" in held:
            print("UP held")
        if "KEY_DOWN" in held:
            print("DOWN held")
        if "KEY_LEFT" in held:
            print("LEFT held")
        if "KEY_RIGHT" in held:
            print("RIGHT held")


if __name__ == "__main__":
    listen()
