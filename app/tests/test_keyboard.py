import os
import unittest
import tempfile
import textwrap
from unittest.mock import patch, mock_open

from lib.logger import Logger
from lib.config import Config
from lib.keyboard import Keyboard, HIDReportError, KeymapError

class TestKeyboard(unittest.TestCase):
    def setUp(self):
        fd, path = tempfile.mkstemp(prefix="pirate_", suffix=".cfg")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(textwrap.dedent(
                """
                    [keyboard]
                    path= /tmp/fakehid
                    layout = us
                    log_keystrokes = false
                """
            ).lstrip())
        self.cfg_path = path
        Config.load(self.cfg_path)

    def tearDown(self):
        try:
            os.remove(self.cfg_path)
        except FileNotFoundError:
            pass

    def test_init_defaults(self):
        keymap = {"a": ["00", "04"]}
        with patch.object(Keyboard, "_load_keymap", return_value=keymap):
            kb = Keyboard(wpm=300)

            self.assertEqual(kb.device_path, "/tmp/fakehid")
            self.assertEqual(kb.wpm, 300)
            self.assertFalse(kb.log_keystrokes)
            self.assertFalse(kb.disable_keyboard)

    @patch("lib.keyboard.time.sleep", return_value=None)
    def test_send_keystroke(self, _sleep):
        keymap = {"a": ["00", "04"]} # a key

        with patch.object(Keyboard, "_load_keymap", return_value=keymap), patch("builtins.open", mock_open()) as mopen:
            kb = Keyboard()
            kb.send("a")

            handle = mopen()
            writes = [args[0] for (args, _) in handle.write.call_args_list]
            self.assertEqual(writes[0], bytearray([0x00, 0x00, 0x04, 0x00, 0x00, 0x00, 0x00, 0x00]))
            self.assertEqual(writes[1], bytearray([0x00] * 8))

    @patch("lib.keyboard.time.sleep", return_value=None)
    def test_send_keystroke_combo(self, _sleep):
        keymap = {"WIN": ["08", "00"], "r": ["00", "15"]} # WIN+r keys

        with patch.object(Keyboard, "_load_keymap", return_value=keymap), patch("builtins.open", mock_open()) as mopen:
            kb = Keyboard()
            kb.send("{KEY:WIN+r}")

            handle = mopen()
            writes = [args[0] for (args, _) in handle.write.call_args_list]
            self.assertEqual(writes[0], bytearray([0x08, 0x00, 0x15, 0x00, 0x00, 0x00, 0x00, 0x00]))
            self.assertEqual(writes[1], bytearray([0x00] * 8))

    @patch("lib.keyboard.time.sleep", return_value=None)
    def test_six_keystrokes(self, _sleep):
        keymap = {
            "K1": ["00", "01"], "K2": ["00", "02"], "K3": ["00", "03"],
            "K4": ["00", "04"], "K5": ["00", "05"], "K6": ["00", "06"],
        }
        with patch.object(Keyboard, "_load_keymap", return_value=keymap):
            kb = Keyboard(disable_keyboard=True)
            kb.send("{KEY:K1+K2+K3+K4+K5+K6}")

    @patch("lib.keyboard.time.sleep", return_value=None)
    def test_mixed_plaintext_and_hotkey(self, _sleep):
        keymap = {
            "a": ["00","04"], "b": ["00","05"], "c": ["00","06"],
            "WIN": ["08","00"], "r": ["00","15"]
        }

        with patch.object(Keyboard, "_load_keymap", return_value=keymap), patch("builtins.open", mock_open()) as mopen:
            kb = Keyboard()
            kb.send("ab{KEY:WIN+r}c")

            handle = mopen()
            writes = [args[0] for (args, _) in handle.write.call_args_list]
            self.assertEqual(writes[0], bytearray([0x00, 0x00, 0x04, 0x00, 0x00, 0x00, 0x00, 0x00]))
            self.assertEqual(writes[4], bytearray([0x08, 0x00, 0x15, 0x00, 0x00, 0x00, 0x00, 0x00]))
    
    @patch("lib.keyboard.time.sleep", return_value=None)
    def test_wpm_override_and_clamp(self, sleep_mock):
        keymap = {"a": ["00", "04"]}

        with patch.object(Keyboard, "_load_keymap", return_value=keymap), patch("builtins.open", mock_open()):
            kb = Keyboard()
            kb.send("a", wpm=1) # Clamp to 10 wpm
            sleep_mock.assert_called_with(1.2) # 10wpm = 1.2s

    @patch("lib.keyboard.time.sleep", return_value=None)
    def test_disable_keyboard(self, _sleep):
        keymap = {"a": ["00", "04"]} # a key

        with patch.object(Keyboard, "_load_keymap", return_value=keymap), patch("builtins.open", mock_open()) as mopen:
            kb = Keyboard(disable_keyboard=True)
            kb.send("a")

            mopen.assert_not_called()

    @patch("lib.keyboard.time.sleep", return_value=None)
    def test_log_keystrokes(self, _sleep):
        keymap = {"a": ["00", "04"]}

        with patch.object(Keyboard, "_load_keymap", return_value=keymap), patch.object(Logger, "debug") as log_debug:
            kb = Keyboard(log_keystrokes=True, disable_keyboard=True)
            kb.send("a")

            message = log_debug.call_args[0][0]
            log_debug.assert_called_once()
            self.assertEqual("00001  00 00 04 00 00 00 00 00  a", message)

    def test_unknown_key_raises(self):
        keymap = {"a": ["00", "04"]}

        with patch.object(Keyboard, "_load_keymap", return_value=keymap):
            kb = Keyboard()

            with self.assertRaises(KeymapError):
                kb.send("b")
    
    @patch("lib.keyboard.time.sleep", return_value=None)
    def test_too_many_keystrokes_raises(self, _sleep):
        keymap = {
            "K1": ["00", "01"], "K2": ["00", "02"], "K3": ["00", "03"],
            "K4": ["00", "04"], "K5": ["00", "05"], "K6": ["00", "06"],
            "K7": ["00", "07"],
        }
        with patch.object(Keyboard, "_load_keymap", return_value=keymap):
            kb = Keyboard(disable_keyboard=True)
            
            with self.assertRaises(HIDReportError):
                kb.send("{KEY:K1+K2+K3+K4+K5+K6+K7}")
