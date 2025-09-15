#!/usr/bin/env bash

set -euo pipefail
CFG="${1:-/config/first-boot.cfg}"

# Function to parse config attributes
ini_get() {
  awk -v KEY="$2" '
    BEGIN { IGNORECASE=1 }
    /^[[:space:]]*($|[#;])/ { next }
    { pos=index($0,"="); if(!pos) next
      k=substr($0,1,pos-1); v=substr($0,pos+1)
      gsub(/^[ \t]+|[ \t]+$/, "", k)
      sub(/[;#].*$/, "", v); gsub(/^[ \t]+|[ \t]+$/, "", v)
      if (tolower(k)==tolower(KEY)) { print v; exit }
    }' "$1"
}

# Define variables
hostname="$(ini_get "$CFG" hostname || echo aurora)"
username="$(ini_get "$CFG" username || echo capn)"
password="$(ini_get "$CFG" password || echo scallywag)"

# Setup the hostname
if [[ "$hostname" =~ ^[a-zA-Z0-9][-a-zA-Z0-9]{0,62}$ ]]; then
  hostnamectl set-hostname "$hostname"
  sed -i "s/127.0.1.1.*/127.0.1.1\t$hostname/g" /etc/hosts
else
  echo "Invalid hostname '$hostname'; skipping"
fi

# Set the username and password
if [[ "$username" =~ ^[a-z_][a-z0-9_-]{0,31}$ ]]; then
  first_user=$(getent passwd 1000 | cut -d: -f1)
  first_group=$(getent group 1000 | cut -d: -f1)

  if [ "$first_user" != "$username" ]; then
    usermod -l "$username" "$first_user"
    usermod -m -d "/home/$username" "$username"
    groupmod -n "$username" "$first_group"
    sed -i "s/^$first_user:/$username:/" /etc/subuid /etc/subgid
    sed -i "s/^$first_user /$username /" /etc/sudoers.d/010_pi-nopasswd
  fi

  hashed_password=$(openssl passwd -6 "$password")
  echo "$username:$hashed_password" | chpasswd -e
else
  echo "Invalid username '$username'; using default credentials"
fi

# Expand rootfs
raspi-config --expand-rootfs

# Disable first boot and cleanup
rm "$CFG"
touch /boot/firstboot_done
systemctl disable pirate-firstboot.service

systemctl reboot # Reboot for changes to take effect