"""
Serial console interface for PiRate.

This module provides the `SerialConsole` class (or equivalent) to bridge
between local stdin/stdout and a serial device. It handles keystroke forwarding,
escape sequences (e.g., detach, EOF), and log/diagnostic integration.
"""

import os
import select
import signal
import sys
import termios
import tty
from collections.abc import Callable
from contextlib import suppress

from serial import Serial

from pirate.lib.config import Config
from pirate.lib.logger import Logger


class SerialConsole:
    """
    Relay stdin/stdout to a remote shell over a serial link.

    This class does **not** implement a shell itself. It relays bytes between
    the local terminal and a serial device using a `select()` loop, forwards
    local SIGINT as `^C` (0x03), supports local detach with `Ctrl-]` (0x1D),
    sends a remote EOF on `Ctrl-D` (0x04), and exits automatically when the
    sentinel `DONE_MARKER` (default: ``b"__PIRATE_DONE__"``) is observed in the
    incoming serial stream.
    """

    DONE_MARKER = b"__PIRATE_DONE__"

    def __init__(
        self,
        path: str | None = None,
        baud: int | None = None,
        newline: str | None = None,
        on_ready: Callable[[], None] | None = None,
        disable_serial: bool | None = None,
    ):
        """
        Initialize a serial console relay.

        Args:
            path (str, optional): Serial device path. Defaults to config value.
            baud (int, optional): Baud rate. Defaults to config value.
            newline (str, optional): Newline mode (e.g., "crlf", "lf"). Defaults to config value.
            on_ready (Callable, optional): Callback invoked after port open/TTY setup.
            disable_serial (bool, optional): Disable serial I/O (dev/test). Defaults to config value.

        """
        self.device_path = path if path is not None else Config.get("serial", "path", "/dev/ttyGS0")
        self.baud = baud if baud is not None else Config.get("serial", "baud", 115200)
        self.newline = newline if newline is not None else Config.get("serial", "newline", "crlf")
        self.disable_serial = disable_serial if disable_serial is not None else Config.get("dev", "disable_serial", False)

        self.on_ready = on_ready

        if self.disable_serial:
            Logger.debug("Serial disabled in config. Skipping connection...")

    def stdio(
        self,
        baud: int | None = None,
        ser: Serial | None = None,
        in_fd: int | None = None,
        out_fd: int | None = None,
        manage_tty: bool | None = True,
        install_sigint_handler: bool | None = True,
    ) -> None:
        """
        Relay stdin/stdout to the serial device until detach/EOF/marker.

        - Forwards local SIGINT to remote as 0x03 without killing the loop.
        - Ctrl-] (0x1D) detaches locally.
        - Ctrl-D (0x04) sends EOF to remote.
        - Exits when '__PIRATE_DONE__' is observed.

        Args:
            baud (int, optional): Override baud for this call.
            ser (object, optional): Serial-like object (fileno/read/write/close).
            in_fd (int, optional): FD to read as stdin (defaults to sys.stdin).
            out_fd (int, optional): FD to write as stdout (defaults to sys.stdout).
            manage_tty (bool): If True, set cbreak and restore TTY on exit.
            install_sigint_handler (bool): If True, install SIGINT forwarder.

        """
        # Don't open connection if in dev_mode
        if self.disable_serial:
            return

        baud = self.baud if baud is None else baud
        created_ser = ser is None
        ser = ser or Serial(
            self.device_path,
            baudrate=baud,
            timeout=0,
            write_timeout=0,
            rtscts=False,
            dsrdtr=False,
            xonxoff=False,
        )

        ready_fired = False
        fd_in = in_fd if in_fd is not None else sys.stdin.fileno()
        fd_out = out_fd if out_fd is not None else sys.stdout.fileno()

        old_tty = None
        prev_sig = None
        if manage_tty:
            old_tty = termios.tcgetattr(fd_in)
            tty.setcbreak(fd_in)
        if install_sigint_handler:

            def on_sigint(_sig: int, _frm: object) -> None:
                with suppress(Exception):
                    ser.write(b"\x03")

            prev_sig = signal.getsignal(signal.SIGINT)
            signal.signal(signal.SIGINT, on_sigint)

        buf = bytearray()
        max_buf = len(self.DONE_MARKER) + 1024

        try:
            while True:
                r, _, _ = select.select([fd_in, ser.fileno()], [], [])

                # Serial -> stdout (and marker detection)
                if ser.fileno() in r:
                    data = ser.read(4096)
                    if data:
                        # Fire on_ready call
                        if not ready_fired and self.on_ready:
                            self.on_ready()
                            ready_fired = True

                        buf.extend(data)
                        if len(buf) > max_buf:
                            del buf[: len(buf) - max_buf]

                        os.write(fd_out, data)

                        if self.DONE_MARKER in buf:
                            os.write(fd_out, b"\r\n")
                            break

                # Stdin -> serial
                if fd_in in r:
                    data = os.read(fd_in, 4096)

                    # stdin closed; send EOF to remote and detach
                    if not data:
                        ser.write(b"\x04")
                        break

                    # Local detach on Ctrl-]
                    if b"\x1d" in data:
                        break

                    # Treat a lone Ctrl-D as EOF for remote
                    if data == b"\x04":
                        ser.write(b"\x04")
                        continue

                    ser.write(data)
        finally:
            if manage_tty and old_tty is not None:
                with suppress(Exception):
                    termios.tcsetattr(fd_in, termios.TCSADRAIN, old_tty)

            if install_sigint_handler and prev_sig is not None:
                with suppress(Exception):
                    signal.signal(signal.SIGINT, prev_sig)

            if created_ser:
                with suppress(Exception):
                    ser.close()
