#!/usr/bin/env bash
set -euo pipefail

rootfs="$1"
genimg_in="$2"

FW_SIZE=120%
ROOT_SIZE=120%
CONFIG_SIZE=256M

SELF_DIR="$(cd -- "$(dirname -- "$0")" && pwd)"

# Pull files from REPO_ROOT/config
CONFIG_SRC="$(realpath "$SELF_DIR/../../../config" || true)"

# Stage into artefacts/input dir where genimage reads "files = { ... }"
CONFIG_DST_IMG="$genimg_in/config"
rm -rf "$CONFIG_DST_IMG"; mkdir -p "$CONFIG_DST_IMG"
if [[ -d "$CONFIG_SRC" ]]; then
  rsync -a \
    --include='*/' \
    --include='*.cfg.template' \
    --exclude='*' \
    "$CONFIG_SRC"/ "$CONFIG_DST_IMG"/
  
  while IFS= read -r -d '' f; do
    mv "$f" "${f%.template}"
  done < <(find "$CONFIG_DST_IMG" -type f -name '*.cfg.template' -print0)
fi

# Build list for genimage "files = { ... }" relative to artefacts/
CONFIG_FILES=""
if [[ -d "$CONFIG_DST_IMG" ]]; then
  while IFS= read -r -d '' f; do
    rel="config/${f#"$CONFIG_DST_IMG/"}"
    CONFIG_FILES+="${CONFIG_FILES:+, }\"$rel\""
  done < <(find "$CONFIG_DST_IMG" -type f -print0)
fi
: "${CONFIG_FILES:=}"

# Generate final wifi.cfg
sed -i \
  -e "s|<IFACE>|$IGconf_wifi_iface|g" \
  -e "s|<COUNTRY>|$IGconf_wifi_country|g" \
  -e "s|<PROFILE>|$IGconf_wifi_profile|g" \
  -e "s|<HS_SSID>|$IGconf_wifi_hotspot_ssid|g" \
  -e "s|<HS_PSK>|$IGconf_wifi_hotspot_psk|g" \
  "$CONFIG_DST_IMG/wifi.cfg"

# Align comments in wifi.cfg
awk -F';' '
{
    # trim trailing spaces in field 1
    sub(/[[:space:]]+$/, "", $1)
    len = length($1)
    if (len > max) max = len
    lines[NR] = $0
    keys[NR]  = $1
    comments[NR] = $2
}
END {
    for (i = 1; i <= NR; i++) {
        if (comments[i] == "") {
            print lines[i]
        } else {
            pad = max - length(keys[i]) + 2  # two spaces before comment
            printf "%s%*s;%s\n", keys[i], pad, "", comments[i]
        }
    }
}' "$CONFIG_DST_IMG/wifi.cfg" > "$CONFIG_DST_IMG/wifi.cfg.tmp" && mv "$CONFIG_DST_IMG/wifi.cfg.tmp" "$CONFIG_DST_IMG/wifi.cfg"


# Generate final genimage.cfg
sed -e "s|<IMAGE_DIR>|$IGconf_sys_outputdir|g" \
  -e "s|<IMAGE_NAME>|$IGconf_image_name|g" \
  -e "s|<IMAGE_SUFFIX>|$IGconf_image_suffix|g" \
  -e "s|<FW_SIZE>|$FW_SIZE|g" \
  -e "s|<ROOT_SIZE>|$ROOT_SIZE|g" \
  -e "s|<CONFIG_SIZE>|$CONFIG_SIZE|g" \
  -e "s|<CONFIG_FILES>|$CONFIG_FILES|g" \
  "$SELF_DIR/genimage.cfg.in" > "$genimg_in/genimage.cfg"
