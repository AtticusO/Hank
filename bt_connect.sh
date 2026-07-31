#!/bin/bash

BT_MAC=90:B6:85:C2:26:82

bluetoothctl power on
bluetoothctl pair "$BT_MAC"
bluetoothctl trust "$BT_MAC"
bluetoothctl connect "$BT_MAC"
