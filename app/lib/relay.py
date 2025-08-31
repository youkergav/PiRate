import os, sys, select, signal, termios, tty
import serial
from typing import Callable
from lib.config import Config
from lib.logger import Logger

class Relay:
    def __init__(self, path: str = None, baud: int = None, newline: str = None, on_ready: Callable = None, disable_serial: bool = None):
        self.device_path = path if path is not None else Config.get("serial", "path", "/dev/ttyGS0")
        self.baud = baud if baud is not None else Config.get("serial", "baud", 115200)
        self.newline = newline if newline is not None else Config.get("serial", "newline", "crlf")
        self.disable_serial = disable_serial if disable_serial is not None else Config.get("dev", "disable_serial", True)

        self.on_ready = on_ready

        self.done_marker = b"__PIRATE_DONE__"

    def stdio(self, baud: int = None) -> None:
        """
        Raw pass-through between local stdin/stdout and the serial device.

        - Forwards Ctrl-C (SIGINT) to the remote as 0x03.
        - Ctrl-] (0x1D) detaches locally.
        - Ctrl-D (0x04) sends EOF to remote.
        - Exits automatically when '__PIRATE_DONE__' arrives (CR/LF tolerant).
        
        Args:
            device (str): Serial device path on the Pi.
            baud (int): Baud rate to open device with.
        """

        # Don't open connection if in dev_mode
        if self.disable_serial:
            Logger.debug("Serial disabled in config. Skipping connection...")
            return

        baud = self.baud if baud is None else baud
        ser = serial.Serial(
            self.device_path,
            baudrate=baud,
            timeout=0,
            write_timeout=0,
            rtscts=False,
            dsrdtr=False,
            xonxoff=False
        )

        ready_fired = False
        fd_in, fd_out = sys.stdin.fileno(), sys.stdout.fileno()
        old_tty = termios.tcgetattr(fd_in)
        # Use cbreak so SIGINT is delivered locally (we'll forward it)
        tty.setcbreak(fd_in)

        # Forward local SIGINT to remote as ^C, but keep relay alive
        def on_sigint(_sig, _frm):
            try:
                ser.write(b"\x03")
            except Exception:
                pass
        signal.signal(signal.SIGINT, on_sigint)

        buf = bytearray()
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
                        os.write(fd_out, data) # write_stdout_normalized(data)
                        # Match marker even if CR/LF boundaries split it
                        if self.done_marker in buf:
                            os.write(fd_out, b"\r\n")
                            break

                # Stdin -> serial
                if fd_in in r:
                    data = os.read(fd_in, 4096)
                    if not data:
                        # stdin closed; send EOF to remote and detach
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
            termios.tcsetattr(fd_in, termios.TCSADRAIN, old_tty)
            try:
                ser.close()
            except Exception:
                pass