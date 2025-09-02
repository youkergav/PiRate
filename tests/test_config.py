import os
import unittest
import tempfile
import textwrap
from unittest.mock import patch
from pirate.lib.logger import Logger
from pirate.lib.config import Config

class TestConfig(unittest.TestCase):
    def setUp(self):
        fd, path = tempfile.mkstemp(prefix="pirate_", suffix=".cfg")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(textwrap.dedent(
                """
                    [keyboard]
                    wpm = 300                 
                    log_keystrokes = false     

                    [serial]
                    baud = 9600             
                    newline = lf            

                    [dev]
                    log_level = debug          
                    stack_trace_errors = true
                    disable_keyboard = false  
                    disable_serial = true    
                """
            ).lstrip())
        
        self.path = path
        Config.load(self.path)
    
    def tearDown(self):
        try:
            os.remove(self.path)
        except FileNotFoundError:
            pass
    
    def test_loaded(self):
        self.assertEqual(Config.get("keyboard", "wpm"), 300)
        self.assertEqual(Config.get("keyboard", "log_keystrokes"), False)
        self.assertEqual(Config.get("serial", "baud"), 9600)
        self.assertEqual(Config.get("serial", "newline"), "lf")
        self.assertEqual(Config.get("dev", "log_level"), Logger.DEBUG)
        self.assertEqual(Config.get("dev", "stack_trace_errors"), True)
        self.assertEqual(Config.get("dev", "disable_keyboard"), False)
        self.assertEqual(Config.get("dev", "disable_serial"), True)
    
    def test_default(self):
        self.assertEqual(Config.get("keyboard", "path"), "/dev/hidg0")
        self.assertEqual(Config.get("serial", "path"), "/dev/ttyGS0")
    
    def test_fallback(self):
        self.assertFalse(Config.get("keybaord", "unknown"))
        self.assertEqual(Config.get("keybaord", "new_property", "new_value"), "new_value")
        self.assertEqual(Config.get("unknown_category", "unknown_property", "unknown_value"), "unknown_value")
    
    def test_load_missing_config(self):
        missing = os.path.join(tempfile.gettempdir(), "definitely_not_here.cfg")
        with patch("pirate.lib.logger.Logger.warning") as warn:
            Config.load(missing)
            warn.assert_called()
        
        self.assertEqual(Config.get("keyboard", "layout"), "us")
        self.assertEqual(Config.get("dev", "log_level"), Logger.INFO)