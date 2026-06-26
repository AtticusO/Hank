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
    dev = find_keyboard()
    print(f"Listening on {dev.path} ({dev.name})")
    for event in dev.read_loop():
        if event.type != ecodes.EV_KEY:
            continue
        key = categorize(event)
        if key.keystate != key.key_down:   # only on press, ignore release/hold
            continue
        if key.keycode == "KEY_UP":
            print("UP PRESSED")
        elif key.keycode == "KEY_DOWN":
            print("DOWN PRESSED")
        elif key.keycode == "KEY_LEFT":
            print("LEFT PRESSED")
        elif key.keycode == "KEY_RIGHT":
            print("RIGHT PRESSED")
        elif key.keycode == "KEY_ESC":
            break


if __name__ == "__main__":
    listen()
