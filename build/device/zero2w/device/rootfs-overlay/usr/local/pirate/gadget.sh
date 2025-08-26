#!/usr/bin/env bash
set -euo pipefail

G=/sys/kernel/config/usb_gadget/pirate
VID=0x1d6b
PID=0x0104
SN=0123456789
MFG="PiRate"
PROD="PiRate HID + Serial"

modprobe libcomposite
mkdir -p "$G"
cd "$G"

echo $VID > idVendor
echo $PID > idProduct
echo 0x0100 > bcdDevice
echo 0x0200 > bcdUSB

mkdir -p strings/0x409
echo "$SN" > strings/0x409/serialnumber
echo "$MFG" > strings/0x409/manufacturer
echo "$PROD" > strings/0x409/product

mkdir -p configs/c.1/strings/0x409
echo 120 > configs/c.1/MaxPower
echo "Config 1" > configs/c.1/strings/0x409/configuration

# HID keyboard (boot protocol)
mkdir -p functions/hid.usb0
echo 1 > functions/hid.usb0/protocol
echo 1 > functions/hid.usb0/subclass
echo 8 > functions/hid.usb0/report_length
printf '\x05\x01\x09\x06\xa1\x01\x05\x07\x19\xe0\x29\xe7\x15\x00\x25\x01\x75\x01\x95\x08\x81\x02\x95\x01\x75\x08\x81\x03\x95\x05\x75\x01\x05\x08\x19\x01\x29\x05\x91\x02\x95\x01\x75\x03\x91\x03\x95\x06\x75\x08\x15\x00\x25\x65\x05\x07\x19\x00\x29\x65\x81\x00\xc0' > functions/hid.usb0/report_desc
ln -sf functions/hid.usb0 configs/c.1/

# CDC-ACM serial
mkdir -p functions/acm.usb0
ln -sf functions/acm.usb0 configs/c.1/

# bind
UDC=$(ls /sys/class/udc | head -n1)
echo "$UDC" > UDC