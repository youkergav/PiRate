import json
import time
import re
import os
from sys import stdout
from importlib.resources import files
from typing import List, Dict
from lib.config import Config
from lib.logger import Logger

class KeymapError(Exception):
    """Custom exception for keymap-related errors."""

    pass

class HIDReportError(Exception):
    """Custom exception for HID report errors."""

    pass

class Keyboard:
    """
    A class to control a USB HID keyboard for emulating keystrokes.

    This class provides functionality for loading keymaps and
    interacting with a USB HID device to send keyboard inputs.
    """

    keystroke_count = 0

    def __init__(self):
        self.device_path = Config.get("keyboard", "path", "/dev/hidg0")
        self.keymap = self._load_keymap(Config.get("keyboard", "layout", "us"))
    
    def _load_keymap(self, layout: str) -> Dict[str, List[str]]:
        """Loads a keymap identifier into the controller."""

        data = files("resources").joinpath(f"layouts/{layout}.json").read_text(encoding="utf-8")
        return json.loads(data)

    def _write_report(self, report: List[int]) -> None:
        """Writes an 8-byte HID report to the device."""

        # Dont execute if in dev mode
        if Config.get("dev", "disable_keyboard", False):
            return

        try:
            with open(self.device_path, 'rb+') as hid:
                hid.write(bytearray(report))
                hid.write(bytearray([0x00] * 8))
        except FileNotFoundError:
            raise FileNotFoundError(f"Device path '{self.device_path}' not found.")
        except PermissionError:
            raise PermissionError(f"Permission denied for device path '{self.device_path}'.")

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
                
        # Format report as hexadecimal for output
        formatted_report = " ".join(f"{byte:02X}" for byte in report)
        Logger.debug(f"{self.keystroke_count:05}  {formatted_report}  {' + '.join(keys)}")

        self._write_report(report)

    def send(self, text: str, delay: float=0.025) -> None:
        """
        Parses text and sends keystrokes to the device.

        This method interprets escape sequences like {KEY:WIN+R}' 
        as key combinations and processes plain text character-by-character.

        Args:
            text (str): The text to send, including any escape sequences.
            delay (float): Delay (in seconds) between key presses. Default is 0.025.
        """

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