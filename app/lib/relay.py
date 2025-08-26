import os, sys, select, signal, termios, tty
import serial
from lib.config import Config

class Relay:
    def stdio(self, device: str = "/dev/ttyGS0", baud: int = 115200) -> None:
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
        if Config.get("dev", "disable_keyboard", False):
            return

        ser = serial.Serial(device, baudrate=baud, timeout=0, write_timeout=0,
                            rtscts=False, dsrdtr=False, xonxoff=False)

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

        done_marker = b"__PIRATE_DONE__"
        buf = bytearray()

        def write_stdout_normalized(b: bytes):
            # Insert \r before lone \n to avoid "stairs"
            i = 0
            out = bytearray()
            while i < len(b):
                ch = b[i:i+1]
                if ch == b"\n":
                    # If previous byte wasn't \r, insert one
                    prev = b[i-1:i] if i > 0 else b""
                    if prev != b"\r":
                        out += b"\r"
                out += ch
                i += 1
            os.write(fd_out, out)

        try:
            while True:
                r, _, _ = select.select([fd_in, ser.fileno()], [], [])
                
                # Serial -> stdout (and marker detection)
                if ser.fileno() in r:
                    data = ser.read(4096)
                    if data:
                        buf.extend(data)
                        os.write(fd_out, data) # write_stdout_normalized(data)
                        # Match marker even if CR/LF boundaries split it
                        if done_marker in buf:
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