#!/usr/bin/env bash
set -euo pipefail


# ========== Functions ==========
# Function to display help
usage() {
  cat <<USAGE
Usage:
  sudo $0 /dev/sdX [image.img] [options]

Positional:
  /dev/sdX            Whole device path (e.g., /dev/sdb, /dev/disk3)
  image.img           (Optional) Path to a local image file. If omitted, it will be auto-downloaded later.

Options:
  --hostname VALUE
  --username VALUE
  --password VALUE
  --wifi-country VALUE
  --wifi-profile VALUE
  --wifi-hotspot-ssid VALUE
  --wifi-hotspot-psk VALUE
  --wifi-management-ssid VALUE
  --wifi-management-psk VALUE
  -h, --help

Examples:
  $0 /dev/sda
  $0 /dev/sda ~/Downloads/pirate-0.2.3.img
  $0 /dev/sda --hostname indigo
  $0 /dev/sda pirate-0.2.3.img --username private --password mypassword
  $0 /dev/sda --username private --password mypassword --hostname indigo \\
     --wifi-country US --wifi-hotspot-ssid Ocean --wifi-hotspot-psk yarg \\
     --wifi-management-ssid MyWifi --wifi-management-psk MyPassword \\
     --wifi-profile management
USAGE
}

# Function to display progress
function progress_bar {
    local message=$1
    local progress=$2
    
    local total_width=40
    local done=$(awk "BEGIN {printf \"%d\", $progress * $total_width / 100}")
    local left=$((total_width - done))
    local fill=$(printf "%${done}s")
    local empty=$(printf "%${left}s")

    printf "\r%s [%s%s] %3d%%" "$message" "${fill// /#}" "${empty// / }" "$progress" > /dev/tty
}

# Align trailing `; comment` columns for neatness (same logic you used earlier)
align_cfg_comments() {
  local file="$1"
  local tmp
  tmp="$(mktemp "${file}.XXXX")"
  awk -F';' '
  {
      sub(/[[:space:]]+$/, "", $1)      # trim trailing spaces from key/value area
      len = length($1)
      if (len > max) max = len
      lines[NR]    = $0
      kv[NR]       = $1
      comments[NR] = $2
  }
  END {
      for (i = 1; i <= NR; i++) {
          if (comments[i] == "") {
              print lines[i]
          } else {
              pad = max - length(kv[i]) + 2  # at least two spaces before the semicolon
              printf "%s%*s;%s\n", kv[i], pad, "", comments[i]
          }
      }
  }' "$file" > "$tmp" && mv "$tmp" "$file"
}

# Set key=value in a flat cfg (no sections), preserving trailing `; comment`
cfg_set_flat() {
  # $1=file, $2=key, $3=value
  local file="$1" key="$2" val="$3"
  awk -v KEY="$key" -v VAL="$val" '
    BEGIN { IGNORECASE=1 }
    /^[[:space:]]*($|[#;])/ { print; next }        # blank/comment passthrough
    /^[[:space:]]*[[:alnum:]_.-]+[[:space:]]*=/ {  # <-- use [[:space:]] not \s
      line=$0
      pos=index(line,"=")
      k=substr(line,1,pos-1); v=substr(line,pos+1)
      gsub(/^[ \t]+|[ \t]+$/, "", k)
      comment=""
      if (match(v, /[;#].*$/)) { comment=substr(v,RSTART) }
      if (tolower(k) == tolower(KEY)) {
        printf "%s = %s%s\n", k, VAL, (comment==""?"":(" " comment))
        next
      }
    }
    { print }
  ' "$file" > "$file.tmp" && mv "$file.tmp" "$file"
}

# Set key=value inside a [section] INI, preserving trailing `; comment`
cfg_set_ini() {
  # $1=file, $2=section, $3=key, $4=value
  local file="$1" sec="$2" key="$3" val="$4"
  awk -v SEC="$sec" -v KEY="$key" -v VAL="$val" '
    BEGIN { IGNORECASE=1; insec=0 }
    /^[[:space:]]*\[/ {
      # entering a section
      s=$0
      gsub(/^[[:space:]]+|\r|\n/, "", s)
      insec = (tolower(s) == "[" tolower(SEC) "]")
      print
      next
    }
    {
      if (insec) {
        if ($0 ~ /^[[:space:]]*($|[#;])/ ) { print; next }
        if ($0 ~ /^[[:space:]]*[[:alnum:]_.-]+[[:space:]]*=/) {
          line=$0
          pos=index(line,"=")
          k=substr(line,1,pos-1); v=substr(line,pos+1)
          gsub(/^[ \t]+|[ \t]+$/, "", k)
          comment=""
          if (match(v, /[;#].*$/)) { comment=substr(v,RSTART) }
          if (tolower(k)==tolower(KEY)) {
            printf "%s = %s%s\n", k, VAL, (comment==""?"":(" " comment))
            next
          }
        }
      }
      print
    }
  ' "$file" > "$file.tmp" && mv "$file.tmp" "$file"
}


# ========== PARSE/VALIDATE ARGS ==========
# Validate running as root
if [[ $EUID -ne 0 ]]; then
  echo "error: this script must be run with sudo/root privileges."
  exit 1
fi

# Validate device path
if [[ $# -lt 1 ]]; then
  echo "error: usage: $0 /dev/sdX [image.img] [--options]"
  usage
  exit 1
fi
DEVICE_PATH="$1"
shift

if [[ ! -b "$DEVICE_PATH" ]]; then
  echo "error: device path '$DEVICE_PATH' does not exist or is not a block device."
  exit 1
fi

# Validate optional image path
IMAGE_PATH=""
if [[ $# -gt 0 && "${1:0:1}" != "-" ]]; then
  IMAGE_PATH="$1"
  shift
  if [[ ! -f "$IMAGE_PATH" ]]; then
    echo "error: image file '$IMAGE_PATH' does not exist."
    exit 1
  fi
fi


# ========== PARSE/VALIDATE FLAGS ==========
# Preseed variables from CLI flags (empty means "not provided yet")
hostname="${hostname:-}"
username="${username:-}"
password="${password:-}"
wifi_country="${wifi_country:-}"
wifi_profile="${wifi_profile:-}"
wifi_hotspot_ssid="${wifi_hotspot_ssid:-}"
wifi_hotspot_psk="${wifi_hotspot_psk:-}"
wifi_management_ssid="${wifi_management_ssid:-}"
wifi_management_psk="${wifi_management_psk:-}"

# Parse long options
while [[ $# -gt 0 ]]; do
  case "$1" in
    --hostname)              hostname="$2"; shift 2 ;;
    --username)              username="$2"; shift 2 ;;
    --password)              password="$2"; shift 2 ;;
    --wifi-country)          wifi_country="$2"; shift 2 ;;
    --wifi-profile)          wifi_profile="$2"; shift 2 ;;
    --wifi-hotspot-ssid)     wifi_hotspot_ssid="$2"; shift 2 ;;
    --wifi-hotspot-psk)      wifi_hotspot_psk="$2"; shift 2 ;;
    --wifi-management-ssid)  wifi_management_ssid="$2"; shift 2 ;;
    --wifi-management-psk)   wifi_management_psk="$2"; shift 2 ;;
    -h|--help)               usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 1 ;;
  esac
done

# Validate hostname
if [[ -n "${hostname}" ]]; then
  [[ "$hostname" =~ ^[a-zA-Z0-9][-a-zA-Z0-9]{0,62}$ ]] \
    || { echo "error: --hostname must be 1–63 chars of letters/digits/hyphens (no trailing hyphen)"; exit 1; }
fi

# Validate username
if [[ -n "${username}" ]]; then
  [[ "$username" =~ ^[a-z_][a-z0-9_-]{0,31}$ ]] \
    || { echo "error: --username must start with [a-z_] and contain only [a-z0-9_-], max 32 chars"; exit 1; }
fi

# Validate wifi country
if [[ -n "${wifi_country}" ]]; then
  wifi_country="$(echo "$wifi_country" | tr '[:lower:]' '[:upper:]')"
  [[ "$wifi_country" =~ ^[A-Z]{2}$ ]] \
    || { echo "error: --wifi-country must be a two-letter code (e.g., US, GB, DE)"; exit 1; }
fi

# Validate wifi profile
if [[ -n "${wifi_profile}" ]]; then
  [[ "$wifi_profile" =~ ^(hotspot|management)$ ]] \
    || { echo "error: --wifi-profile must be 'hotspot' or 'management'"; exit 1; }
fi

# Validate hotspot SSID/PSK
if [[ -n "${wifi_hotspot_ssid}" ]]; then
  [[ -n "$wifi_hotspot_ssid" ]] \
    || { echo "error: --wifi-hotspot-ssid cannot be empty"; exit 1; }
fi
if [[ -n "${wifi_hotspot_psk}" ]]; then
  len=${#wifi_hotspot_psk}
  if (( len < 8 || len > 63 )); then
    echo "error: --wifi-hotspot-psk must be between 8 and 63 characters"
    exit 1
  fi
fi

# Validate management SSID/PSK
if [[ -n "${wifi_management_ssid}" && -z "${wifi_management_psk}" ]]; then
  : # no-op; prompt section will handle asking for PSK
fi
if [[ -n "${wifi_management_psk}" ]]; then
  len=${#wifi_management_psk}
  if (( len < 8 || len > 63 )); then
    echo "error: --wifi-management-psk must be between 8 and 63 characters"
    exit 1
  fi
  if [[ -z "${wifi_management_ssid}" ]]; then
    echo "error: --wifi-management-psk provided but --wifi-management-ssid is missing"
    exit 1
  fi
fi

echo "Welcome to the PiRate imager!"
echo

# ========== PROMPTS ==========
# Hostname
if [[ -z "${hostname}" ]]; then
  echo "Enter the hostname for the device below (default: aurora)"
  while true; do
    read -rp "hostname (aurora): " hostname
    hostname="${hostname:-aurora}"
    [[ "$hostname" =~ ^[a-zA-Z0-9][-a-zA-Z0-9]{0,62}$ ]] && break
    echo "Invalid hostname. Use alphanumeric and dashes only (1–63 chars)."
  done
fi

# Login credentials
if [[ -z "${username}" || -z "${password}" ]]; then
  echo
  echo "Enter the login credentials to the device below (default: capn:scallywag)"
  if [[ -z "${username}" ]]; then
    while true; do
      read -rp "username (capn): " username
      username="${username:-capn}"
      [[ "$username" =~ ^[a-z_][a-z0-9_-]{0,31}$ ]] && break
      echo "Invalid username."
    done
  else
    echo "username (capn): ${username}"
  fi
  if [[ -z "${password}" ]]; then
    while true; do
      read -rsp "password (scallywag): " password; echo
      password="${password:-scallywag}"
      if [[ "$password" == "scallywag" ]]; then
        break
      fi
      read -rsp "confirm password: " confirm; echo
      [[ "$password" == "$confirm" ]] && break || echo "Passwords do not match. Try again."
    done
  else
    echo "password: (provided)"
  fi
fi

# WiFi country
if [[ -z "${wifi_country}" ]]; then
  echo
  echo "Enter the two-letter WiFi country code below (default: US)"
  while true; do
    read -rp "country (US): " wifi_country
    wifi_country="${wifi_country:-US}"
    wifi_country=$(echo "$wifi_country" | tr '[:lower:]' '[:upper:]')
    [[ "$wifi_country" =~ ^[A-Z]{2}$ ]] && break || echo "Must be two uppercase letters (e.g., US, GB, DE)."
  done
else
  wifi_country=$(echo "$wifi_country" | tr '[:lower:]' '[:upper:]')
fi

# Hotspot profile
if [[ -z "${wifi_hotspot_ssid}" || -z "${wifi_hotspot_psk}" ]]; then
  echo
  echo "Enter the credentials for the hotspot WiFi profile below (default: Sea:scallywag)"

  if [[ -z "${wifi_hotspot_ssid}" ]]; then
    while true; do
      read -rp "SSID (Sea): " wifi_hotspot_ssid
      wifi_hotspot_ssid="${wifi_hotspot_ssid:-Sea}"
      [[ -n "$wifi_hotspot_ssid" ]] && break || echo "SSID cannot be empty."
    done
  else
    echo "SSID (Sea): ${wifi_hotspot_ssid}"
  fi

  if [[ -z "${wifi_hotspot_psk}" ]]; then
    while true; do
      read -rsp "PSK (scallywag): " wifi_hotspot_psk; echo
      wifi_hotspot_psk="${wifi_hotspot_psk:-scallywag}"

      # Default 'scallywag' is accepted without length/confirm
      if [[ "$wifi_hotspot_psk" == "scallywag" ]]; then
        break
      fi

      # Length check
      len=${#wifi_hotspot_psk}
      if (( len < 8 || len > 63 )); then
        echo "PSK must be between 8 and 63 characters."
        continue
      fi

      read -rsp "confirm PSK: " confirm; echo
      [[ "$wifi_hotspot_psk" == "$confirm" ]] && break || echo "PSKs do not match. Try again."
    done
  else
    echo "PSK (scallywag): (provided)"
  fi
fi

# Management profile
if [[ -z "${wifi_management_ssid}" || -z "${wifi_management_psk}" ]]; then
  echo
  echo "Enter the credentials for the management WiFi profile below"

  if [[ -z "${wifi_management_ssid}" ]]; then
    read -rp "SSID: " wifi_management_ssid
  else
    echo "SSID: ${wifi_management_ssid}"
  fi

  if [[ -n "${wifi_management_ssid}" ]]; then
    if [[ -z "${wifi_management_psk}" ]]; then
      while true; do
        read -rsp "PSK: " wifi_management_psk; echo
        [[ -n "$wifi_management_psk" ]] || { echo "PSK cannot be empty if SSID is provided."; continue; }

        # Length check (no special default here)
        len=${#wifi_management_psk}
        if (( len < 8 || len > 63 )); then
          echo "PSK must be between 8 and 63 characters."
          continue
        fi

        read -rsp "confirm PSK: " confirm; echo
        [[ "$wifi_management_psk" == "$confirm" ]] && break || echo "PSKs do not match. Try again."
      done
    else
      # If provided via flag, assume already validated earlier
      echo "PSK: (provided)"
    fi
  else
    wifi_management_psk=""
  fi
fi

# Initial WiFi profile
if [[ -z "${wifi_profile}" ]]; then
  echo
  if [[ -n "$wifi_management_ssid" ]]; then
    echo "Choose the initial WiFi profile below (default: management options: hotspot/management)"
    while true; do
      read -rp "wifi profile (management): " wifi_profile
      wifi_profile="${wifi_profile:-management}"
      [[ "$wifi_profile" =~ ^(hotspot|management)$ ]] && break || echo "Enter hotspot or management."
    done
  else
    echo "Choose the initial WiFi profile below (default: hotspot options: hotspot/management)"
    while true; do
      read -rp "wifi profile (hotspot): " wifi_profile
      wifi_profile="${wifi_profile:-hotspot}"
      [[ "$wifi_profile" =~ ^(hotspot|management)$ ]] && break || echo "Enter hotspot or management."
    done
  fi
fi


# ========== DOWNLOAD IMAGE ==========
printf "\nStarting installer... $(tput setaf 2)done$(tput sgr0)\n"

if [[ -z "$IMAGE_PATH" ]]; then
  # Query GitHub Releases API for latest .img
  release_url=$(curl -s https://api.github.com/repos/youkergav/PiRate/releases/latest \
    | grep "browser_download_url" \
    | grep ".img" \
    | cut -d '"' -f 4)

  if [[ -z "$release_url" ]]; then
    echo "error: could not determine latest image URL from GitHub releases."
    exit 1
  fi

  IMAGE_NAME=$(basename "$release_url")
  IMAGE_PATH="/tmp/$IMAGE_NAME"

  # Download if not already cached
  if [[ ! -f "$IMAGE_PATH" ]]; then
    headers=$(curl -sIL "$release_url")
    curl -L -o "$IMAGE_PATH" "$release_url" --silent &

    # Monitor the download progress
    curl_pid=$!
    file_size=$(echo "$headers" | grep -i '^content-length:' | tail -n 1 | awk '{print $2}' | tr -d '\r\n')
    downloaded_size=0
    
    while kill -0 $curl_pid 2>/dev/null; do
        if [[ -f "$IMAGE_PATH" ]]; then
            downloaded_size=$(stat -f%z $IMAGE_PATH | tr -d '\n')
            progress=$(( (downloaded_size * 100) / file_size ))

            progress_bar "Downloading $IMAGE_NAME..." "$progress"
        fi

        sleep 0.1
    done

    printf "\r\033[K%sDownloading $IMAGE_NAME... $(tput setaf 2)done$(tput sgr0)\n" > /dev/tty
    sleep 0.5
  else
    echo "Downloading $IMAGE_NAME... $(tput setaf 2)done$(tput sgr0)"
  fi
else
  IMAGE_NAME=$(basename "$IMAGE_PATH")
fi


# ========== FLASH IMAGE ==========
if mount | grep -q "$DEVICE_PATH"; then
    sudo diskutil unmountDisk force $DEVICE_PATH > /dev/null 2>&1
fi

total_size=$(ls -l $IMAGE_PATH | awk '{print $5}' | tr -d '\r\n')
sudo dd if="$IMAGE_PATH" of="$DEVICE_PATH" bs=1M status=progress 2> /tmp/pirate_dd.log &
dd_pid=$!

transfered_size=0
while kill -0 "$dd_pid" 2>/dev/null; do
    transfered_size=$(tr '\r' '\n' < /tmp/pirate_dd.log | awk '/bytes.*transferred/ {print $1}' | tail -n 1)
    progress=$(( (transfered_size * 100) / total_size ))

    progress_bar "Flashing $IMAGE_NAME..." "$progress"
    sleep 1
done

rm /tmp/pirate_dd.log
printf "\r\033[K%sFlashing $IMAGE_NAME... $(tput setaf 2)done$(tput sgr0)\n" > /dev/tty
sleep 0.5


# ========== MOUNT CONFIG PARTITION ==========
printf "Mounting CONFIG partition... "
CONFIG_MNT="/Volumes/CONFIG"

if [[ "$(uname)" == "Darwin" ]]; then
  # Force the kernel to re-read partition table
  diskutil unmountDisk force "$DEVICE_PATH" >/dev/null 2>&1 || true
  sleep 1
  diskutil mountDisk "$DEVICE_PATH" >/dev/null 2>&1 || true

  # Retry loop: wait until CONFIG actually mounted and has files
  for i in {1..50}; do
    if [[ -d "$CONFIG_MNT" && -f "$CONFIG_MNT/wifi.cfg" ]]; then
      printf "$(tput setaf 2)done$(tput sgr0)\n"
      break
    fi
    sleep 0.2
  done

  if [[ ! -d "$CONFIG_MNT" || ! -f "$CONFIG_MNT/wifi.cfg" ]]; then
    echo "error: could not mount CONFIG partition."
    exit 1
  fi
else
  CONFIG_DEV="${DEVICE_PATH}1"
  mkdir -p /mnt/config
  mount "$CONFIG_DEV" /mnt/config
  CONFIG_MNT="/mnt/config"
  printf "$(tput setaf 2)done$(tput sgr0)\n"
fi

if [[ -z "$CONFIG_MNT" || ! -d "$CONFIG_MNT" ]]; then
  echo "error: could not mount CONFIG partition."
  exit 1
else
  printf "$(tput setaf 2)done$(tput sgr0)\n"
fi


# ========== WRITE CONFIG FILES ==========
printf "Updating config files... "

WIFI_CFG="$CONFIG_MNT/wifi.cfg"
FB_CFG="$CONFIG_MNT/first-boot.cfg"

# wifi.cfg
if [[ -f "$WIFI_CFG" ]]; then
  cfg_set_ini  "$WIFI_CFG" device     interface "wlan0"           # static (or make this a flag later)
  cfg_set_ini  "$WIFI_CFG" device     country   "$wifi_country"
  cfg_set_ini  "$WIFI_CFG" device     profile   "$wifi_profile"

  cfg_set_ini  "$WIFI_CFG" hotspot    ssid      "$wifi_hotspot_ssid"
  cfg_set_ini  "$WIFI_CFG" hotspot    psk       "$wifi_hotspot_psk"

  cfg_set_ini  "$WIFI_CFG" management ssid      "$wifi_management_ssid"
  cfg_set_ini  "$WIFI_CFG" management psk       "$wifi_management_psk"

  align_cfg_comments "$WIFI_CFG"
else
  echo "warning: $WIFI_CFG not found; skipping WiFi configuration."
fi

# first-boot.cfg
if [[ -f "$FB_CFG" ]]; then
  cfg_set_flat "$FB_CFG" hostname "$hostname"
  cfg_set_flat "$FB_CFG" username "$username"
  cfg_set_flat "$FB_CFG" password "$password"
  align_cfg_comments "$FB_CFG"
else
  echo "warning: $FB_CFG not found; skipping first-boot configuration."
fi

sync
printf "$(tput setaf 2)done$(tput sgr0)\n"


# ========== EJECT / UNMOUNT ==========
printf "Ejecting CONFIG partition... "

sync

if [[ "$(uname)" == "Darwin" ]]; then
  DISK_FOR_DU="${DEVICE_PATH/rdisk/disk}"

  # 1) Try to stop Spotlight indexing to reduce remount races
  if [[ -n "$CONFIG_MNT" && -d "$CONFIG_MNT" ]]; then
    mdutil -i off "$CONFIG_MNT" >/dev/null 2>&1 || true
  fi

  # 2) Unmount the volume path first (retry a few times)
  for _ in {1..10}; do
    [[ -n "$CONFIG_MNT" ]] && diskutil unmount "$CONFIG_MNT" >/dev/null 2>&1 || true
    # Break if it’s truly gone
    mount | grep -q -- "$CONFIG_MNT" || break
    sleep 0.3
  done

  # 3) Unmount the whole disk (retry)
  for _ in {1..10}; do
    diskutil unmountDisk "$DISK_FOR_DU" >/dev/null 2>&1 || true
    # If no slices are mounted, we’re good
    diskutil list "$DISK_FOR_DU" | awk '/Apple_APFS|Microsoft Basic Data|DOS_FAT/ {print $NF}' \
      | while read -r p; do diskutil info "$p" | grep -q 'Mounted:.*Yes' && echo mounted; done \
      | grep -q mounted || break
    sleep 0.3
  done

  # 4) Eject the disk (retry)
  for _ in {1..10}; do
    diskutil eject "$DISK_FOR_DU" >/dev/null 2>&1 && break
    sleep 0.3
  done

  # Final check
  if diskutil info "$DISK_FOR_DU" >/dev/null 2>&1; then
    echo "warning: could not fully eject $DISK_FOR_DU; please eject manually in Finder."
  else
    printf "$(tput setaf 2)done$(tput sgr0)\n"
  fi
else
  umount "$CONFIG_MNT" >/dev/null 2>&1 || true
  # Best-effort: ensure it’s gone
  for _ in {1..10}; do
    mount | grep -q -- "$CONFIG_MNT" || break
    umount -l "$CONFIG_MNT" >/dev/null 2>&1 || true
    sleep 0.3
  done
  printf "$(tput setaf 2)done$(tput sgr0)\n"
fi


printf "\nPiRate image successfully installed! You may now safely remove the SD card.\n"