#!/bin/bash
## One-time setup (run once, re-running is safe): makes pigpiod and raspotify
## start at boot via systemd, and installs hank.service.
##   ./startup.sh              set up the daemons and install (not enable) Hank
##   ./startup.sh --with-hank  also start Hank now and at every boot
##
## Hank itself never needs sudo — only installing system services does.
set -e
cd "$(dirname "$0")"

sudo cp systemd/pigpiod.service systemd/hank.service /etc/systemd/system/
sudo systemctl daemon-reload

## a pigpiod started by hand (`sudo pigpiod`) would block the service from starting
if pgrep -x pigpiod >/dev/null && ! systemctl is-active --quiet pigpiod; then
    echo "Stopping the manually started pigpiod so systemd can manage it"
    sudo killall pigpiod
    sleep 1
fi

## enable --now: start immediately AND at boot (plain `enable` only did the boot part)
sudo systemctl enable --now pigpiod raspotify

if [ "$1" = "--with-hank" ]; then
    sudo systemctl enable --now hank
    echo "Hank is running. Logs: journalctl -u hank -f"
else
    echo "Daemons ready. Start Hank with:  sudo systemctl enable --now hank"
    echo "                  or by hand:     .venv/bin/python main.py"
fi
