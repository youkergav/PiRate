"""
# PiRate Technical Documentation

PiRate is a USB HID keystroke injection and serial relay toolkit for the
Raspberry Pi Zero 2 W. These docs are generated from the project's
docstrings and serve as a technical reference for developers and operators.

---

## Disclaimer

PiRate is intended for research, red-teaming, and defensive security testing.
Use only on systems you own or have explicit authorization to test.

---

## Purpose

PiRate provides the building blocks for:
- Emulating a USB keyboard and delivering scripted keystrokes.
- Relaying serial sessions between a host and a connected target.
- Running payloads that automate common Windows and macOS actions.
- Managing configuration and structured logging across modules.

---

## How to Use This Documentation

- Browse the **modules** listed in the sidebar to explore available APIs.
- Each class and function includes argument and return value details.
- Private helpers (`_method`, `_Class`) are minimally documented.
- Payload modules are documented for completeness but may change frequently.

---
## Contributing

For information on coding standards, testing practices, and how to submit
changes, please see the project's **Contributing Guide**.
"""

from importlib.metadata import version

__version__ = version("pirate")
