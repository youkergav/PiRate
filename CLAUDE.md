# PiRate Codebase Architecture Guide

This document provides a comprehensive overview of the PiRate project architecture for developers and Claude instances working on this codebase.

## Project Summary

PiRate is a USB HID keystroke injection + serial relay toolkit designed for the Raspberry Pi Zero 2 W. It enables:
- Emulating a USB keyboard to inject keystrokes into a target host
- Relaying serial sessions between the PiRate device and a connected target
- Executing platform-specific payloads (Windows, macOS, Linux) that automate attacks
- Managing configuration through INI-style config files
- Providing comprehensive logging with custom log levels

**Key Disclaimer**: This is a security testing tool. It can be used to perform keystroke injection attacks. Use only on systems you own or are explicitly authorized to test.

---

## 1. Overall Project Structure

```
./claude/pirate/
├── src/pirate/                    # Main source code
│   ├── __init__.py               # Package init + documentation
│   ├── cli.py                    # CLI entry point and command dispatch
│   ├── lib/                      # Core library modules
│   │   ├── __init__.py
│   │   ├── config.py            # Configuration singleton
│   │   ├── logger.py            # Colored logging singleton
│   │   ├── keyboard.py          # USB HID keyboard emulation
│   │   └── serial_console.py    # Serial I/O relay
│   ├── payloads/                # Platform-specific attack payloads
│   │   ├── __init__.py
│   │   └── macos/               # macOS payloads
│   │       └── serial_shell.py  # Opens macOS terminal and injects shell stager
│   └── resources/
│       └── layouts/             # Keyboard layout JSON files
│           └── us.json          # US keyboard mapping
├── config/                       # Configuration templates and defaults
│   ├── pirate.cfg              # Main config (device settings)
│   ├── pirate.cfg.template     # Config template
│   ├── wifi.cfg                # WiFi profile config
│   └── wifi.cfg.template       # WiFi config template
├── tests/                       # Unit tests
│   ├── test_cli.py
│   ├── test_config.py
│   ├── test_keyboard.py
│   ├── test_logger.py
│   └── test_serial_console.py
├── docs/                        # Generated documentation
├── pyproject.toml              # Poetry configuration
└── README.md                   # User-facing documentation
```

---

## 2. Main Entry Point and CLI Structure

**File**: `./claude/pirate/src/pirate/cli.py`

### CLI Flow
```
pirate (main)
  ├── Logger.setup()
  ├── Config.load()
  └── Subcommand dispatch:
      ├── version      → cmd_version()
      └── execute      → cmd_execute()
```

### Key Components

1. **Main Entry Point**: `cli.main(argv=None) -> int`
   - Initializes Logger (INFO level)
   - Loads configuration from file
   - Sets log level from config
   - Parses arguments
   - Dispatches to handler

2. **Subcommands**:
   - `pirate version` - Prints package version
   - `pirate execute <payload>` - Executes a payload module

3. **Payload Resolution**: `_resolve_payload(short_path: str) -> ModuleType`
   - Takes short path like `macos.serial_shell`
   - Converts to full module path: `pirate.payloads.macos.serial_shell`
   - Uses `importlib.import_module()` to load
   - Raises `PayloadNotFoundError` if module not found
   - Looks for `execute()` callable in the module
   - Calls the function with no arguments

4. **Error Handling**:
   - `PayloadNotFoundError` - raised when payload doesn't exist
   - Stack traces controlled by `Config.get("dev", "stack_trace_errors", False)`

### Testing Entry Points
See `./claude/pirate/tests/test_cli.py` for examples of:
- Testing version command
- Testing payload execution
- Testing error cases

---

## 3. How Payloads Work and Are Executed

### Payload Contract

Any payload must:
1. Be located under `pirate.payloads.<platform>.<name>`
2. Export a callable `execute()` function with signature: `execute() -> None`
3. Can optionally take keyword arguments that have defaults

### Example Payload: macOS Serial Shell

**File**: `./claude/pirate/src/pirate/payloads/macos/serial_shell.py`

```python
def execute(baud: int = 115200, show_diagnostics: bool = False) -> None:
    """
    Opens a macOS terminal and injects a shell stager via keyboard.
    The stager finds USB devices and opens an interactive shell over serial.
    """
```

### Execution Flow (macos.serial_shell)

1. **Instantiate Core Components**:
   ```python
   kb = Keyboard()              # USB HID keyboard emulator
   rl = SerialConsole(on_ready=_on_ready)  # Serial relay
   ```

2. **Inject Keyboard Commands**:
   ```python
   kb.send("{KEY:GUI+SPACE}")   # Open Spotlight search
   time.sleep(0.35)
   kb.send("terminal{KEY:ENTER}")  # Launch Terminal app
   time.sleep(1.0)
   kb.send("{KEY:GUI+n}")       # New terminal window
   time.sleep(0.5)
   ```

3. **Send Payload Script**:
   - Constructs shell one-liner that:
     - Finds USB device (`/dev/tty.usb*`)
     - Opens file descriptor to it
     - Configures serial settings with `stty`
     - Launches interactive zsh shell
     - Sends sentinel marker when done
   - Sends via keyboard: `kb.send(payload)`

4. **Relay Serial Session**:
   - `rl.stdio(baud=baud)` - takes over stdin/stdout
   - Forwards keystrokes to serial device
   - Reads responses and prints to stdout
   - Exits when `__PIRATE_DONE__` marker is seen

### Payload Design Pattern

Payloads are **self-contained modules** that:
- Import core libraries (Keyboard, SerialConsole, Logger, Config)
- Define an `execute()` function
- Handle all timing, sequencing, and error management themselves
- Can be tested independently by calling `execute()` directly
- Log progress via `Logger.info()`, `Logger.success()`, etc.

---

## 4. The Configuration System

**File**: `./claude/pirate/src/pirate/lib/config.py`

### Architecture

The `Config` class is a **singleton** that loads and manages application settings.

### Default Configuration

```python
_defaults = {
    "keyboard": {
        "layout": "us",           # Keyboard layout file (without .json)
        "wpm": 200,               # Typing speed in words per minute
        "path": "/dev/hidg0",     # HID device path
        "log_keystrokes": False,  # Debug logging of raw HID reports
    },
    "serial": {
        "path": "/dev/ttyGS0",    # Serial device path
        "baud": 115200,           # Baud rate
        "newline": "crlf",        # Line ending (crlf or lf)
    },
    "dev": {
        "stack_trace_errors": False,  # Show full stack traces on error
        "log_level": "info",          # Log level (debug/info/warning/error)
        "disable_keyboard": False,    # Disable HID writes (dev mode)
        "disable_serial": False,      # Disable serial connection (dev mode)
    },
}
```

### Configuration Resolution Path

1. **Environment Variable**: `PIRATE_CONFIG` - if set and file exists, use it
2. **Development Repo**: `<repo>/config/pirate.cfg` - for dev/testing
3. **Device Canonical**: `/config/pirate.cfg` - mounted on Raspberry Pi
4. **Defaults**: If no file found, use built-in defaults with warning

### File Format

INI-style configuration (using Python's `configparser`):

```ini
[keyboard]
layout = us
wpm = 500
path = /dev/hidg0
log_keystrokes = true

[serial]
path = /dev/ttyGS0
baud = 115200
newline = crlf

[dev]
log_level = info
stack_trace_errors = false
disable_keyboard = false
disable_serial = false
```

### Usage

```python
from pirate.lib.config import Config

Config.load()  # Loads from default path
Config.load("/path/to/custom.cfg")  # Load specific file

# Retrieve values
layout = Config.get("keyboard", "layout", "us")  # With default
wpm = Config.get("keyboard", "wpm")  # Uses loaded value
```

### Type Coercion

The config system automatically converts string values from INI to proper types:
- **bool**: "1", "true", "yes", "on" → True, others → False
- **int**: "123" → 123
- **str**: Direct assignment
- **None**: Empty string → None

### Custom Normalizers

Special post-load transformations:
- `("dev", "log_level")`: Converts log level string to Logger enum value

---

## 5. The Keyboard/HID Injection System

**File**: `./claude/pirate/src/pirate/lib/keyboard.py`

### Architecture

The `Keyboard` class emulates a USB keyboard by writing 8-byte HID reports to a device file.

### Initialization

```python
kb = Keyboard(
    layout="us",              # Keyboard layout (optional, uses config)
    wpm=200,                  # Words per minute typing speed (optional)
    path="/dev/hidg0",        # HID device path (optional)
    log_keystrokes=False,     # Log raw reports (optional)
    disable_keyboard=False,   # Test mode - don't write to device (optional)
)
```

All parameters are optional and fall back to config values.

### Keyboard Layout System

**Format**: JSON files in `src/pirate/resources/layouts/`

Example (`us.json`):
```json
{
    "a": ["0x00", "0x04"],      // [modifier_byte, keycode_byte]
    "A": ["0x02", "0x04"],      // 0x02 = Shift modifier
    "WIN": ["0x08", "0x00"],    // GUI/Windows key
    "GUI+SPACE": ...,           // Combinations possible
    ...
}
```

Keys map to `[modifier_hex, keycode_hex]` tuples.

### HID Report Format

Standard USB HID keyboard report (8 bytes):
```
Byte 0: Modifier bits (Shift, Ctrl, Alt, GUI, etc.)
Byte 1: Reserved (always 0)
Bytes 2-7: Up to 6 keycodes (0 = no key)
```

### Core Methods

1. **`_load_keymap(layout: str) -> Keymap`**
   - Loads JSON keymap from resources
   - Returns `dict[str, list[str]]` mapping key names to [modifier, keycode]

2. **`_wpm_to_delay(wpm: int) -> float`**
   - Converts words-per-minute to inter-keystroke delay in seconds
   - Formula: `delay = 60 / (wpm * 5)` (5 chars/word assumption)
   - Clamps WPM between 10-1000

3. **`_process_keystroke(keystroke: str) -> None`**
   - Parses keystroke string (e.g., "WIN+R", "a")
   - Splits on "+" for combinations
   - Builds 8-byte HID report
   - Combines modifiers (OR operation on byte 0)
   - Places keycodes in first available slots (bytes 2-7)
   - Validates against max 6-key rollover
   - Logs raw report if enabled
   - Writes report + release (8 zero bytes)

4. **`send(text: str, wpm: int | None = None) -> None`**
   - Main public API for sending text
   - Parses escape sequences: `{KEY:HOTKEY}` for special keys
   - Supports mixed plaintext and hotkeys
   - Example: `kb.send("Hello {KEY:WIN+R} calc{KEY:ENTER}")`
   - Applies WPM delay between each keystroke

### Keystroke Escape Sequence Format

```
{KEY:KEYNAME}           Single key
{KEY:MODIFIER+KEY}      Combined keys (joined with +, spaces ignored)
{KEY:GUI+SPACE}         Example: Open Spotlight on macOS
{KEY:WIN+R}             Example: Open Run dialog on Windows
```

Multiple keys in one escape can be combined: `{KEY:CTRL+ALT+DEL}`

### Writing to HID Device

```python
def _write_report(self, report: list[int]) -> None:
    with open(self.device_path, "rb+") as hid:
        hid.write(bytearray(report))          # Write 8-byte report
        hid.write(bytearray([0x00] * 8))      # Write release (all zeros)
```

### Error Classes

- **`KeymapError`**: Raised when key not found in keymap
- **`HIDReportError`**: Raised when HID report is full (>6 keys) or device not accessible

### Development/Testing Mode

When `disable_keyboard=True`:
- No device file writes occur
- `_write_report()` returns early
- Useful for testing on machines without HID devices

---

## 6. The Serial Communication System

**File**: `./claude/pirate/src/pirate/lib/serial_console.py`

### Architecture

The `SerialConsole` class relays stdin/stdout between the local terminal and a remote serial device using non-blocking I/O.

### Initialization

```python
rl = SerialConsole(
    path="/dev/ttyGS0",           # Serial device path (optional)
    baud=115200,                  # Baud rate (optional)
    newline="crlf",               # Line ending mode (optional)
    on_ready=None,                # Callback when connection ready (optional)
    disable_serial=False,         # Test mode (optional)
)
```

### Core Method: `stdio()`

```python
def stdio(
    baud: int | None = None,
    ser: Serial | None = None,                # Can pass existing Serial object
    in_fd: int | None = None,                 # FD for stdin
    out_fd: int | None = None,                # FD for stdout
    manage_tty: bool = True,                  # Set terminal to cbreak mode
    install_sigint_handler: bool = True,      # Intercept Ctrl-C
) -> None:
```

### Relay Loop Architecture

Uses `select.select()` for non-blocking multiplexed I/O:

```python
while True:
    r, _, _ = select.select([fd_in, ser.fileno()], [], [])
    
    # Serial -> stdout
    if ser.fileno() in r:
        data = ser.read(4096)
        # Print to stdout
        # Check for DONE_MARKER
    
    # Stdin -> serial
    if fd_in in r:
        data = os.read(fd_in, 4096)
        # Forward to serial
```

### Control Sequences

| Sequence | Meaning | Action |
|----------|---------|--------|
| `Ctrl-C` (0x03) | SIGINT | Forwarded to remote as 0x03 byte |
| `Ctrl-]` (0x1D) | Local detach | Breaks relay loop locally |
| `Ctrl-D` (0x04) | EOF | Sends 0x04 to remote, then detaches |
| `__PIRATE_DONE__` | Sentinel | Marker in serial stream causes clean exit |

### Terminal Management

When `manage_tty=True`:
1. Saves original terminal settings with `termios.tcgetattr()`
2. Sets terminal to cbreak mode with `tty.setcbreak()` (canonical input disabled, echo disabled)
3. Restores settings on exit with `tcsetattr()`

### Signal Handling

When `install_sigint_handler=True`:
1. Installs custom SIGINT handler
2. Handler forwards `\x03` (Ctrl-C) to serial device
3. Does NOT kill the relay loop
4. Restores original handler on exit

### Done Marker Detection

```python
DONE_MARKER = b"__PIRATE_DONE__"
buf = bytearray()
max_buf = len(DONE_MARKER) + 1024

if self.DONE_MARKER in buf:
    os.write(fd_out, b"\r\n")
    break  # Exit cleanly
```

Uses a sliding buffer (max 1KB + marker) to detect marker in stream.

### Error Recovery

All cleanup is wrapped in `try/finally` with `suppress(Exception)` to ensure:
- TTY is always restored
- Signal handlers are always restored
- Serial port is always closed

---

## 7. Key Abstractions and Design Patterns

### Design Patterns Used

#### 1. **Singleton Pattern**
Used for `Logger` and `Config`:
```python
class Logger:
    _logger: logging.Logger | None = None
    
    @classmethod
    def setup(cls, ...): ...
    
    @classmethod
    def info(cls, message: str): ...
```

Benefits:
- Single initialization point
- Shared state across application
- Easy to inject for testing via mocking

#### 2. **Module-as-Plugin Pattern**
Payloads are plugins loaded dynamically via `importlib`:
```python
def _resolve_payload(short_path: str) -> ModuleType:
    full = f"pirate.payloads.{short_path}"
    return importlib.import_module(full)
```

Benefits:
- Easy to add new payloads (just drop in new `.py` file)
- Payloads can be platform-specific (macos/, windows/, linux/)
- Decouples CLI from specific attack implementations

#### 3. **Configuration Injection**
Components read config on initialization, allowing overrides:
```python
class Keyboard:
    def __init__(self, layout=None, wpm=None, path=None, ...):
        self.layout = layout if layout is not None else Config.get(...)
```

Benefits:
- Can override config per-instance for testing
- Testable without mocking entire Config
- Supports both config file and programmatic configuration

#### 4. **Callback Pattern**
Serial relay supports custom callbacks:
```python
rl = SerialConsole(on_ready=lambda: Logger.success("Connected!"))
rl.stdio()  # Fires callback when data first arrives
```

#### 5. **Type Hints and Strict Typing**
- Full type annotations on all public APIs
- MyPy strict mode enabled
- Helps prevent bugs and documents intent

### Class Hierarchy and Relationships

```
Config (Singleton)
  └── used by: Keyboard, SerialConsole, CLI
  
Logger (Singleton)
  └── used by: Config, Keyboard, SerialConsole, CLI, Payloads
  
Keyboard
  ├── uses: Config, Logger
  └── used by: Payloads
  
SerialConsole
  ├── uses: Config, Logger
  └── used by: Payloads
  
Payload (abstract pattern)
  ├── uses: Keyboard, SerialConsole, Logger, Config
  └── invoked by: CLI._resolve_payload()
  
CLI
  ├── uses: Config, Logger, importlib
  └── loads and executes: Payloads
```

### Key Abstractions

1. **Payload Abstraction**:
   - Defined by contract: must export `execute()` callable
   - Platform-specific: `payloads/macos/`, `payloads/windows/`, etc.
   - Self-contained: brings its own timing, sequencing, error handling

2. **Device Abstraction**:
   - Keyboard writes to `/dev/hidg0` (HID gadget)
   - Serial reads/writes to `/dev/ttyGS0` (serial gadget)
   - Both are file-like interfaces (allowing easy mocking)

3. **Configuration Abstraction**:
   - Centralized Config singleton
   - INI-style file format
   - Environment variable override support
   - Type coercion built-in

4. **Logging Abstraction**:
   - Custom log level (SUCCESS)
   - Colored output via colorama
   - Easy level control at runtime
   - Centralized formatting

---

## 8. Key Files Quick Reference

| File | Purpose | Key Classes/Functions |
|------|---------|----------------------|
| `cli.py` | Entry point & command dispatch | `main()`, `_resolve_payload()`, `cmd_execute()`, `cmd_version()` |
| `lib/config.py` | Configuration management | `Config` (singleton) |
| `lib/logger.py` | Logging with colors | `Logger` (singleton) |
| `lib/keyboard.py` | USB HID keyboard emulation | `Keyboard`, `KeymapError`, `HIDReportError` |
| `lib/serial_console.py` | Serial I/O relay | `SerialConsole` |
| `payloads/macos/serial_shell.py` | macOS payload example | `execute(baud=115200, show_diagnostics=False)` |
| `resources/layouts/us.json` | Keyboard layout mapping | JSON keymap |
| `config/pirate.cfg` | Configuration template | INI format settings |

---

## 9. Testing Strategy

All core modules have comprehensive unit tests in `/tests/`:

- **test_cli.py**: Command parsing, payload resolution, error handling
- **test_config.py**: Config loading, type coercion, defaults, overrides
- **test_keyboard.py**: HID report building, keystroke parsing, WPM delay
- **test_logger.py**: Log levels, colored output
- **test_serial_console.py**: I/O relay, marker detection, signal handling

### Testing Approach
- Heavy use of mocking (`unittest.mock`)
- Mocking file operations, Serial objects, signal handlers
- Testing both happy path and error cases
- 80%+ code coverage requirement

---

## 10. Common Development Tasks

### Add a New Payload
1. Create file: `src/pirate/payloads/PLATFORM/PAYLOAD_NAME.py`
2. Implement: `def execute() -> None: ...`
3. Import needed libraries: `Keyboard`, `SerialConsole`, `Logger`, etc.
4. Run via: `pirate execute PLATFORM.PAYLOAD_NAME`

### Add a New Keyboard Layout
1. Create: `src/pirate/resources/layouts/LAYOUT_CODE.json`
2. Map keys to `[modifier_hex, keycode_hex]` pairs
3. Update config default if needed
4. Use via: `Config.get("keyboard", "layout")` or `Keyboard(layout="LAYOUT_CODE")`

### Modify Configuration System
1. Update `Config._defaults` dict
2. Add custom normalizer if needed
3. Update config template files
4. Write tests in `test_config.py`

### Debug an Attack
1. Set `log_level = debug` in config
2. Set `log_keystrokes = true` to see raw HID reports
3. Set `stack_trace_errors = true` for full traces
4. Set `disable_keyboard = true` and `disable_serial = true` for dry-run
5. Payloads can add their own logging via `Logger.debug()`

---

## 11. Key Code Patterns to Understand

### Config Usage Pattern
```python
from pirate.lib.config import Config

# In __init__ or function start
Config.load()  # Usually called by CLI

# In any component
value = Config.get("section", "key", default_value)
```

### Logger Usage Pattern
```python
from pirate.lib.logger import Logger

Logger.setup(Logger.INFO)  # Called by CLI
Logger.info("Starting...")
Logger.success("Done!")
Logger.warning("Be careful")
Logger.error("Something went wrong")
Logger.debug("Detailed info (only if log_level=debug)")
```

### Keyboard Usage Pattern
```python
from pirate.lib.keyboard import Keyboard

kb = Keyboard()  # Loads from config
kb.send("hello{KEY:ENTER}")  # Mixed text and hotkeys
kb.send("{KEY:WIN+R}")  # Just hotkey
```

### SerialConsole Usage Pattern
```python
from pirate.lib.serial_console import SerialConsole

def on_connected():
    Logger.success("Serial connected!")

rl = SerialConsole(on_ready=on_connected)
rl.stdio()  # Block until DONE_MARKER or Ctrl-]
```

---

## 12. Important Security Considerations

1. **HID Injection**: The keyboard class writes raw HID reports. On Linux with g_mass_storage or g_hid kernel modules, this creates a legitimate USB keyboard device that the host accepts without drivers.

2. **Serial Relay**: The serial device is /dev/ttyGS0 on Raspberry Pi (serial gadget), which appears as a COM port on Windows or /dev/tty.usb* on macOS.

3. **Timing**: Many payloads use `time.sleep()` to allow the target OS to catch up (open applications, focus windows, etc.).

4. **Payload Execution**: Payloads run with the privileges of whatever user started the pirate command. Usually the `capn` user, but could be root.

5. **Configuration Files**: The /config partition (FAT32) is readable from the target machine without mounting the OS, making it easy to manage without SSH.

---

## 13. Where to Dig Deeper

- **Keyboard HID Protocol**: Read `lib/keyboard.py` → understand USB HID spec (8-byte report format)
- **Serial Protocol**: Read `lib/serial_console.py` → understand select() and termios APIs
- **Payload Design**: Read `payloads/macos/serial_shell.py` → see attack flow example
- **Configuration**: Read `lib/config.py` → understand INI parsing and type coercion
- **Tests**: All `/tests/` files → understand expected behavior

---

## 14. Quick Reference: Running Commands

```bash
# Build/install the package
poetry install

# Run tests
poetry run pytest tests/

# Run a specific test
poetry run pytest tests/test_keyboard.py::TestKeyboard::test_send_keystroke

# Check code quality
poetry run ruff check src/
poetry run mypy src/

# Run a payload (on the device)
pirate execute macos.serial_shell

# Print version
pirate version
```

---

**Last Updated**: November 11, 2025  
**Target Audience**: Claude instances and developers maintaining PiRate  
**Version Reference**: 0.2.3
