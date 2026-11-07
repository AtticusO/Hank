#!/bin/bash
## Connects Hank's DualSense controller over Bluetooth.
##
##   ./bt_connect.sh            reconnect: press the PS button when asked
##   ./bt_connect.sh --repair   fresh pairing — use this when the controller was
##                              paired with something else (PS5, PC) in the meantime
##
## A DualSense only remembers ONE host. After it pairs with a PS5 or a PC, the
## Pi's stored key no longer works: connecting fails with "Invalid exchange" /
## br-connection-create-socket even though the Pi still shows it as paired.
## The only fix is to forget it on the Pi and pair again (--repair).

BT_MAC=90:B6:85:C2:26:82
WAIT_S=15

connected() { bluetoothctl info "$BT_MAC" 2>/dev/null | grep -q "Connected: yes"; }
paired()    { bluetoothctl info "$BT_MAC" 2>/dev/null | grep -q "Paired: yes"; }

bluetoothctl power on >/dev/null

if connected; then
    echo "PS5 controller already connected"
    exit 0
fi

if [ "$1" != "--repair" ] && paired; then
    ## The Pi can't wake a sleeping controller: the controller connects itself
    ## when you press PS. So wait for it instead of firing `connect` once and failing.
    echo "Press the PS button on the controller (waiting ${WAIT_S}s)..."
    bluetoothctl connect "$BT_MAC" >/dev/null 2>&1      # works if it's already awake
    for _ in $(seq "$WAIT_S"); do
        connected && { echo "PS5 controller connected"; exit 0; }
        sleep 1
    done
    echo "Couldn't connect. If the controller was used with a PS5 or a PC since, re-pair it:"
    echo "    ./bt_connect.sh --repair"
    exit 1
fi

## ---- fresh pairing
echo "Put the controller in pairing mode: hold CREATE + PS until the light bar flashes quickly."
read -r -t 60 -p "Press Enter once it's flashing... " || true
bluetoothctl remove "$BT_MAC" >/dev/null 2>&1           # drop the stale key
echo "Scanning..."
found=""
for _ in 1 2 3; do
    bluetoothctl --timeout 10 scan on >/dev/null 2>&1
    if bluetoothctl devices | grep -q "$BT_MAC"; then found=1; break; fi
done
if [ -z "$found" ]; then
    echo "Controller not found. Is the light bar still flashing quickly? Try again."
    exit 1
fi
bluetoothctl pair "$BT_MAC" && bluetoothctl trust "$BT_MAC" && bluetoothctl connect "$BT_MAC"
sleep 2
if connected; then
    echo "PS5 controller paired and connected. Next time just press PS (./bt_connect.sh)."
else
    echo "Pairing didn't complete — run ./bt_connect.sh --repair again."
    exit 1
fi
