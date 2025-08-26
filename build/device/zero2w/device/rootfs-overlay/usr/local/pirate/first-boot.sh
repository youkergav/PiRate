#!/usr/bin/env bash
set -euo pipefail

raspi-config --expand-rootfs

touch /boot/firstboot_done
systemctl disable pirate-firstboot.service
systemctl reboot
