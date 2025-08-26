import os
import configparser
from pathlib import Path
from typing import Any, Dict
from lib.logger import Logger

class Config:
    """
    Singleton class to load and store configuration settings.
    Allows overriding defaults via CLI arguments.
    """
    
    _data: Dict = {}
    _defaults: Dict = {
        "keyboard": {
            "layout": "us",
            "wpm": 200,
            "path": "/dev/hidg0",
            "log_keystrokes": False
        },
        "serial": {
            "path": "/dev/ttyGS0",
            "baud": 115200,
            "newline": "crlf"
        },
        "dev": {
            "stack_trace_errors": False,
            "log_level": "info",
            "disable_keyboard": False,
            "disable_serial": False
        }
    }

    @classmethod
    def _resolve_config_path(cls) -> str:
        """Return a usable pirate.cfg path (env > /config > repo fallback) or raise."""
        # ENV override
        env = os.getenv("PIRATE_CONFIG")
        if env and Path(env).exists():
            return env

        # Canonical on-device location
        p = Path("/config/pirate.cfg")
        if p.exists():
            return str(p)

        # 3) Repo location fallback
        dev = Path(__file__).resolve().parents[2] / "config" / "pirate.cfg"
        if dev.exists():
            return str(dev)

        raise FileNotFoundError("pirate.cfg not found.")

    @classmethod
    def load(cls) -> None:
        """
        Loads the configuration from a file and merges CLI arguments.

        Args:
            filepath (str): Path to the configuration file.
        """

        filepath = cls._resolve_config_path()

        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Config file '{filepath}' not found.")
        
        if not filepath.endswith(".cfg"):
            raise ValueError("File must end with a CFG extension.")
        
        cp = configparser.ConfigParser(
            interpolation=None,
            inline_comment_prefixes=("#", ";"),
            strict=True,
        )
        cp.read(filepath)

        data = {s: dict(v) for s, v in cls._defaults.items()}
        for section, defaults in cls._defaults.items():
            if cp.has_section(section):
                resolved = {}

                for key, dval in defaults.items():
                    if cp.has_option(section, key):
                        raw = cp.get(section, key, raw=True).strip()
                        resolved[key] = cls._coerce(dval, raw)
                    else:
                        resolved[key] = dval
                data[section] = resolved
            else:
                data[section] = dict(defaults)

        # Perform type castings.
        data["dev"]["log_level"] = Logger.str_to_level(data["dev"]["log_level"])
        
        cls._data = data
    
    @classmethod
    def get(cls, section: str, key: str, default: Any = None) -> Any:
        """
        Retrieves a configuration value.

        Args:
            section (str): The section in the CFG file to retrieve.
            key (str): The key to retrieve.
            default: The default value if the key is not found.

        Returns:
            Any: The configuration value or the default value.
        """

        if cls._data is None:
            raise RuntimeError("Configuration is not loaded. Call `Config.load(filepath)` first.")
        
        if section not in cls._data:
            return default
        
        return cls._data[section].get(key, default)

    @staticmethod
    def _coerce(default_value: Any, raw: str) -> Any:
        """Coerce a string 'raw' into the type of 'default_value'."""
        
        if raw == "" and default_value is not None:
            return default_value
        if isinstance(default_value, bool):
            return raw.lower() in ("1", "true", "yes", "on")
        if isinstance(default_value, int):
            return int(raw)
        if default_value is None:
            return None if raw == "" else raw
        
        return raw
