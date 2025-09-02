import os, sys, select, signal, termios, tty
import serial
from typing import Callable
from pirate.lib.config import Config
from pirate.lib.logger import Logger

class SerialConsole:
    """
    Interactive serial console between the host terminal (stdin/stdout) and a
    remote shell over a serial link.

    This class does **not** implement a shell itself. It relays bytes between
    the local terminal and a serial device using a `select()` loop, forwards
    local SIGINT as `^C` (0x03), supports local detach with `Ctrl-]` (0x1D),
    sends a remote EOF on `Ctrl-D` (0x04), and exits automatically when the
    sentinel `DONE_MARKER` (default: ``b"__PIRATE_DONE__"``) is observed in the
    incoming serial stream.
    """
    
    DONE_MARKER = b"__PIRATE_DONE__"

    def __init__(self, path: str = None, baud: int = None, newline: str = None, on_ready: Callable = None, disable_serial: bool = None):
        self.device_path = path if path is not None else Config.get("serial", "path", "/dev/ttyGS0")
        self.baud = baud if baud is not None else Config.get("serial", "baud", 115200)
        self.newline = newline if newline is not None else Config.get("serial", "newline", "crlf")
        self.disable_serial = disable_serial if disable_serial is not None else Config.get("dev", "disable_serial", False)

        self.on_ready = on_ready

    def stdio(self, baud: int = None, ser: object = None, in_fd: int = None, out_fd: int = None, manage_tty: bool = True, install_sigint_handler: bool = True) -> None:
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
            Logger.debug("Serial disabled in config. Skipping connection...")
            return

        baud = self.baud if baud is None else baud
        created_ser = ser is None
        ser = ser or serial.Serial(
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
            def on_sigint(_sig, _frm):
                try: ser.write(b"\x03")
                except Exception: pass
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
                            try:
                                self.on_ready()
                                ready_fired = True
                            except Exception:
                                pass

                        buf.extend(data)
                        if len(buf) > max_buf:
                            del buf[:len(buf) - max_buf]

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
                try: termios.tcsetattr(fd_in, termios.TCSADRAIN, old_tty)
                except Exception: pass

            if install_sigint_handler and prev_sig is not None:
                try: signal.signal(signal.SIGINT, prev_sig)
                except Exception: pass

            if created_ser:
                try: ser.close()
                except Exception: pass