import json
import time
import re
from importlib.resources import files
from typing import List, Dict
from lib.config import Config
from lib.logger import Logger

class Keyboard:
    """
    A class to control a USB HID keyboard for emulating keystrokes.

    This class provides functionality for loading keymaps and
    interacting with a USB HID device to send keyboard inputs.
    """

    def __init__(self, layout: str = None, wpm: int = None, path: str = None, log_keystrokes: bool = None, disable_keyboard: bool = None):
        self.device_path = path if path is not None else Config.get("keyboard", "path", "/dev/hidg0")
        self.keymap = self._load_keymap(layout if layout is not None else Config.get("keyboard", "layout", "us"))
        self.wpm = wpm if wpm is not None else Config.get("keyboard", "wpm", 400)
        self.log_keystrokes = log_keystrokes if log_keystrokes is not None else Config.get("keyboard", "log_keystrokes", True)
        self.disable_keyboard = disable_keyboard if disable_keyboard is not None else Config.get("dev", "disable_keyboard", False)
        self.keystroke_count = 0
    
    def _load_keymap(self, layout: str) -> Dict[str, List[str]]:
        """Loads a keymap identifier into the controller."""

        data = files("resources").joinpath(f"layouts/{layout}.json").read_text(encoding="utf-8")
        return json.loads(data)

    def _write_report(self, report: List[int]) -> None:
        """Writes an 8-byte HID report to the device."""

        # Dont execute if in dev mode
        if self.disable_keyboard:
            return

        try:
            with open(self.device_path, 'rb+') as hid:
                hid.write(bytearray(report))
                hid.write(bytearray([0x00] * 8))
        except FileNotFoundError:
            raise FileNotFoundError(f"Device path '{self.device_path}' not found.")
        except PermissionError:
            raise PermissionError(f"Permission denied for device path '{self.device_path}'.")
    
    def _wpm_to_delay(self, wpm: int) -> float:
        """Converts typing speed in words-per-minute to an inter-keystroke delay."""

        # Clamp WPM between 10-1000
        if wpm < 10:
            wpm = 10
        elif wpm > 1000:
            wpm = 1000

        chars_per_word = 5
        delay = 60 / (wpm * chars_per_word)

        return delay

    def _process_keystroke(self, keystroke: str) -> None:
        """Converts a keystroke into an HID report and sends it to the device."""

        self.keystroke_count += 1
        report = [0x00] * 8 # Initialize an 8-byte HID report
        keys = keystroke.split("+") # Split keystroke into single keys (e.g., "WIN+R")

        # Process each key
        for key in keys:
            # Exit if key not found in keymap
            if key not in self.keymap:
                raise KeymapError(f"Key '{key}' not found in keymap.")
            
            # Get modifier and keycode
            modifier, keycode = self.keymap[key]
            report[0] |= int(modifier, 16) # Add modifier bits to byte 0

            # Add keycode to the next available slot (bytes 2-7)
            for i in range(2, 8):
                if report[i] == 0x00: # Find an empty slot
                    report[i] = int(keycode, 16)
                    break
            else:
                raise HIDReportError("Too many keys in report. HID report full.")
                
        # Log the keystrokes as hexdump
        if self.log_keystrokes:
            formatted_report = " ".join(f"{byte:02X}" for byte in report)
            Logger.debug(f"{self.keystroke_count:05}  {formatted_report}  {' + '.join(keys)}")

        self._write_report(report)

    def send(self, text: str, wpm: int = None) -> None:
        """
        Parses text and sends keystrokes to the device.

        This interprets escape sequences like {KEY:WIN+R} as single hotkeys
        and processes plain text character-by-character.

        Args:
            text (str): Text to send, including any escape sequences.
            wpm (Optional[int]): Per-call words-per-minute override. Defaults to self.wpm.
        """

        delay = self._wpm_to_delay(self.wpm if wpm is None else wpm)
        pattern = re.compile(r"\{KEY:(.*?)\}")
        keystrokes = []
        pos = 0
    
        # Add characters to keystrokes and hotkeys as single keystroke.
        while pos < len(text):
            match = pattern.search(text, pos)

            if match:
                escaped_key = match.group(1).replace(" ", "")

                keystrokes.extend(list(text[pos:match.start()])) # Add all keys as keystroke before hotkey
                keystrokes.append(escaped_key) # Add hotkey as single keystroke

                pos = match.end() # Move position past the match
            else:
                keystrokes.extend(list(text[pos:])) # Add remaining text as regular characters
                break

        # Loop through key codes and send to HID
        for key in keystrokes:
            self._process_keystroke(key)
            time.sleep(delay)

class KeymapError(Exception):
    """Custom exception for keymap-related errors."""

    pass

class HIDReportError(Exception):
    """Custom exception for HID report errors."""

    pass