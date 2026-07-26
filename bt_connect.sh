#!/bin/bash

BT_MAC = 90:BB:CC:DD:EE:FF

echo -e "power on\nagent on\ndefault-agent\npair $DEVICE_MAC\ntrust $DEVICE_MAC\nconnect $DEVICE_MAC\nquit" | bluetoothctl
