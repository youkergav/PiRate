# PiRate

USB HID keystroke injection + serial relay toolkit. **Built for Raspberry Pi Zero 2 W** and shipped as a ready‑to‑flash image.

> **Legal & Ethical Use Only**  
> This project can emulate HID keystrokes and interact with attached hosts. Use it **only** on 
> systems you own or are explicitly authorized to test. You are solely responsible for complying
> with all applicable laws and policies.
>
> **No Warranty** 
> The software is provided “AS IS”, without warranty of any kind. The authors are not liable for
> any damages or misuse.

## Features
- Powered over a single USB connection.
- USB **HID keyboard** and **USB serial** gadget.
- Executes **user‑selected payloads** (Windows/macOS/Linux).
- **Hotspot** and **Management** Wi‑Fi modes with automatic fallback.
- Human‑readable config files on a **CONFIG** partition.
- **Dry‑run** functionality for development (no HID writes/serial connection).

## Hardware Requirements
- Raspberry Pi Zero 2 W
- MicroSD card (≥ 2 GB)
- [USB Dongle Expansion Board](https://www.amazon.com/GeeekPi-Dongle-Expansion-Raspberry-Inserted/dp/B098JP79ZX)
  - This is recommended but not required. Without it, you will need to use a USB‑A to Micro‑USB OTG cable.

## Installation
1. Download the latest `.img` from Releases.
2. Flash it to a microSD (Raspberry Pi Imager, `dd`, etc).
3. Safely eject the card, insert it into the Pi Zero 2 W, and connect it to the host.

> The first boot performs initial setup and may take longer than normal.

## Getting Started
1. Connect the Pi to a host. 
    - PiRate's Wi-Fi profile is set to hotspot mode by default. See [Wi-Fi Profiles](#wi-fi-profiles) for more info.
    - The **default credentials** are: SSID: `Sea` PSK: `scallywag`
2. SSH into PiRate.
    - The **default hostname** is `aurora.local`
    - The **default credentials** are: Username: `capn` Password: `scallywag`
3. To execute your first payload, simply run `pirate`.

## Configuration
PiRate stores its configurable settings on a FAT32 **CONFIG** partition so you can edit them
without directly logging into the OS.

### Where it can be access
- **From another computer:**
  - **Windows:** shows up as a new drive named `CONFIG`
  - **macOS:** mounted at `/Volumes/CONFIG`
  - **Linux:** typically `/media/<user>/CONFIG`
- **On PiRate itself:** mounted at **`/config`**

### Files on the CONFIG partition
| File         | Purpose                                                            |
|--------------|--------------------------------------------------------------------|
| `wifi.cfg`   | Selects Wi-Fi profile, and holds SSID/PSK for each profile.        |
| `pirate.cfg` | App settings: keyboard settings, serial settings, and dev toggles. |

## Wi-Fi Profiles
PiRate supports two Wi-Fi profiles, that can be set in `CONFIG/wifi.cfg`. See [Configuration](#configuration) for more info.

### Hotspot Mode
The default Wi-Fi mode. PiRate creates and broadcasts its own access point so you can connect directly to it. This is used when you do not have access to an existing Wi-Fi network. The drawbacks are you will not have Internet access and you must be in range.

**Default Credentials: SSID: `Sea` PSK: `scallywag`**

### Management Mode
PiRate attempts to join your existing network using the SSID/PSK. This can be used when you have access to a Wi-Fi network, allowing you to gain Internet access as well as not needing to be in as close proximity. **This mode is also used for managing the PiRate device, like installing updates.**

### Switching Profiles
To switch from hotspot mode to management mode, perform the following:
1. Modify `CONFIG/wifi.cfg`:
    ```ini
    [device]
    profile = management
    ...
    [management]
    ssid = YourWifiName
    psk  = YourWifiPassword
    ```
2. Restart pirate-wifi: `sudo systemctl restart pirate-wifi.service`
    - This service is automatically run on startup, so rebooting works too.

> If connecting in management mode fails, PiRate falls back to hotspot automatically so you don’t get locked out.

## License
MIT © 2025 Gavin Youker
