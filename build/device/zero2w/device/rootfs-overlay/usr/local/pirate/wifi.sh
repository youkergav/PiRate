#!/usr/bin/env bash

set -euo pipefail
CFG="${1:-/config/wifi.cfg}"

# Function to parse config attributes
ini_get() {
  awk -v SEC="$2" -v KEY="$3" '
  BEGIN { IGNORECASE=1; sec="["SEC"]" }
  /^\s*\[/ { inside=(tolower($0)==tolower(sec)); next }
  inside {
    if ($0 ~ /^[[:space:]]*($|;|#)/) next
    pos=index($0,"="); if (!pos) next
    k=substr($0,1,pos-1); v=substr($0,pos+1)
    gsub(/^[ \t]+|[ \t]+$/, "", k)
    sub(/[;#].*$/, "", v); gsub(/^[ \t]+|[ \t]+$/, "", v)
    if (tolower(k)==tolower(KEY)) { print v; exit }
  }' "$1"
}

# Check for NetworkManager connection
has_connectivity() {
  state="$(nmcli -t -f CONNECTIVITY general 2>/dev/null | tr -d '\r')"

  case "$state" in
    full|limited|portal) return 0 ;;   # treat portal/limited as "usable" for mgmt
    none)                 :        ;;  # keep waiting
    unknown|'')                 # fallback: consider it ok if we at least got an IPv4
      ip="$(nmcli -g IP4.ADDRESS device show "$iface" 2>/dev/null | sed -n '1p')"
      [[ -n "$ip" ]] && return 0
      ;;
  esac

  return 1
}

# Define variables
modified=0
iface="$(ini_get "$CFG" device interface || echo wlan0)"
country="$(ini_get "$CFG" device country || echo US)"; country="${country^^}"
profile="$(ini_get "$CFG" device profile || echo hotspot)"; profile="${profile,,}"
hs_ssid="$(ini_get "$CFG" hotspot ssid || echo Sea)"
hs_psk="$(ini_get "$CFG" hotspot psk || echo scallywag)"
mg_ssid="$(ini_get "$CFG" management ssid || true)"
mg_psk="$(ini_get "$CFG" management psk || true)"

# Configure country
if [[ -n "${country}" ]]; then
  cur_country="$(iw reg get 2>/dev/null | awk 'tolower($1)=="country" { c=$2; sub(/:.*/,"",c); print toupper(c); exit }')"
  if [[ "$cur_country" != "$country" ]]; then
    iw reg set "$country"
  fi
fi

# Configure hotspot
if ! nmcli con show hotspot >/dev/null 2>&1; then
  nmcli con add type wifi ifname "$iface" con-name hotspot \
    802-11-wireless.ssid Sea \
    802-11-wireless.mode ap \
    802-11-wireless.band bg \
    wifi-sec.key-mgmt wpa-psk \
    wifi-sec.psk Scallywag \
    802-11-wireless-security.group ccmp \
    802-11-wireless-security.pairwise ccmp \
    802-11-wireless-security.proto rsn \
    ipv4.method shared \
    ipv4.addresses 10.42.0.1/24 \
    ipv6.method ignore \
    ipv6.addr-gen-mode default \
    connection.autoconnect no
fi

if [[ -n "${hs_ssid}" && -n "${hs_psk}" ]]; then
  cur_hs_ssid="$(nmcli -g 802-11-wireless.ssid connection show hotspot)"
  if [[ "$cur_hs_ssid" != "$hs_ssid" ]]; then
    nmcli con modify hotspot 802-11-wireless.ssid "$hs_ssid"
    modified=1
  fi

  cur_hs_psk="$(nmcli -s -g 802-11-wireless-security.psk connection show hotspot)"
  if [[ "$cur_hs_psk" != "$hs_psk" ]]; then
    nmcli con modify hotspot 802-11-wireless-security.psk "$hs_psk"
    modified=1
  fi
fi

# Configure management
if ! nmcli con show management >/dev/null 2>&1; then
  nmcli con add type wifi ifname "$iface" con-name management ssid UNKNOWN_NETWORK \
    802-11-wireless.mode infrastructure \
    wifi-sec.key-mgmt wpa-psk \
    wifi-sec.psk UNKNOWN_NETWORK \
    802-11-wireless-security.proto rsn \
    802-11-wireless-security.pairwise ccmp \
    802-11-wireless-security.group ccmp \
    ipv4.method auto \
    ipv6.method ignore \
    ipv6.addr-gen-mode default
fi

if [[ -n "${mg_ssid}" && -n "${mg_psk}" ]]; then
  cur_mg_ssid="$(nmcli -g 802-11-wireless.ssid connection show management)"
  if [[ "$cur_mg_ssid" != "$mg_ssid" ]]; then
    nmcli con modify management 802-11-wireless.ssid "$mg_ssid"
    modified=1
  fi

  cur_mg_psk="$(nmcli -s -g 802-11-wireless-security.psk connection show management)"
  if [[ "$cur_mg_psk" != "$mg_psk" ]]; then
    nmcli con modify management 802-11-wireless-security.psk "$mg_psk"
    modified=1
  fi
fi

# Configure profiles
case "$profile" in
  hotspot) want="hotspot"; other="management";;
  management) want="management"; other="hotspot";;
  *) want="hotspot"; other="management";;
esac

cur_profile="$(nmcli -t -f GENERAL.CONNECTION device show "$iface" | sed 's/^GENERAL\.CONNECTION://')"
if [[ "$cur_profile" != "$profile" ]]; then
  nmcli connection modify "$want" connection.autoconnect yes connection.autoconnect-priority 20
  nmcli connection modify "$other" connection.autoconnect no connection.autoconnect-priority 0

  modified=1
fi

# Reload connections
if (( modified == 1 )); then
  nmcli con down management 2>/dev/null || true
  nmcli con down hotspot 2>/dev/null || true

  if ! nmcli --wait 20 con up "$want"; then
    if [[ "$want" == "management" ]]; then
      echo "activation of 'management' failed; falling back to 'hotspot'"

      nmcli con down management 2>/dev/null || true
      nmcli --wait 20 con up hotspot
    fi
  fi
fi