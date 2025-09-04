"""
Configuration management for PiRate.

This module defines the `Config` singleton class, which loads settings from
a CFG file, applies type conversions, and exposes a `get` method for
retrieving and overriding values at runtime.
"""

import configparser
import os
from pathlib import Path
from typing import Any, ClassVar

from pirate.lib.logger import Logger


class Config:
    """
    Singleton class to load and store configuration settings.

    Allows overriding defaults via CLI arguments.
    """

    _data: ClassVar[dict[str, dict[str, Any]] | None] = None
    _defaults: ClassVar[dict[str, dict[str, Any]]] = {
        "keyboard": {
            "layout": "us",
            "wpm": 200,
            "path": "/dev/hidg0",
            "log_keystrokes": False,
        },
        "serial": {"path": "/dev/ttyGS0", "baud": 115200, "newline": "crlf"},
        "dev": {
            "stack_trace_errors": False,
            "log_level": "info",
            "disable_keyboard": False,
            "disable_serial": False,
        },
    }

    # Special post-load normalizers for keys that need custom casting
    _NORMALIZERS = {
        ("dev", "log_level"): "_str_to_level",
    }

    @classmethod
    def _resolve_config_path(cls) -> str | None:
        """Return a usable pirate.cfg path (env > /config > repo fallback) or None."""

        # ENV override
        env = os.getenv("PIRATE_CONFIG")
        if env and Path(env).exists():
            return env

        # Repo location fallback
        dev = Path(__file__).resolve().parents[3] / "config" / "pirate.cfg"
        if dev.exists():
            return str(dev)

        # Canonical on-device location fallback
        p = Path("/config/pirate.cfg")
        if p.exists():
            return str(p)

        return None

    @classmethod
    def _apply_normalizers(cls, data: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
        """Apply custom normalizers."""

        out = {s: dict(v) for s, v in data.items()}

        for (section, key), func in cls._NORMALIZERS.items():
            if isinstance(func, str):
                func = getattr(cls, func)
            if section in out and key in out[section]:
                out[section][key] = func(out[section][key])

        return out

    @classmethod
    def _str_to_level(cls, level: str) -> int:
        """Convert a log levels str to Enum."""

        levels = {
            "success": Logger.SUCCESS,
            "info": Logger.INFO,
            "warning": Logger.WARNING,
            "error": Logger.ERROR,
            "debug": Logger.DEBUG,
        }

        if level not in levels:
            raise ValueError(f"The level {level} not a valid log level.")

        return levels[level]

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

    @classmethod
    def load(cls, filepath: str | None = None) -> None:
        """
        Load the configuration from a file and merges CLI arguments.

        Args:
            filepath (str): Path to the configuration file.
        """

        filepath = filepath or cls._resolve_config_path()

        if not filepath or not os.path.exists(filepath):
            Logger.warning("No config file found. Loading defaults...")
            cls._data = cls._apply_normalizers(cls._defaults.copy())
            return

        if not filepath.endswith(".cfg"):
            Logger.warning("Config path does not end with .cfg. Loading defaults...")
            cls._data = cls._apply_normalizers(cls._defaults.copy())
            return

        cp = configparser.ConfigParser(
            interpolation=None,
            inline_comment_prefixes=("#", ";"),
            strict=True,
        )

        try:
            cp.read(filepath)
        except configparser.MissingSectionHeaderError:
            Logger.warning("Invalid config file. Loading defaults...")
            cls._data = cls._apply_normalizers(cls._defaults.copy())
            return

        data = cls._defaults.copy()
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

        cls._data = cls._apply_normalizers(data)

    @classmethod
    def get(cls, section: str, key: str, default: Any = None) -> Any:
        """
        Retrieve a configuration value.

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
