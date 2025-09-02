import os
import tempfile
import textwrap
import unittest
from unittest.mock import MagicMock, patch
from pirate.lib.config import Config
from pirate.lib.serial_console import SerialConsole

def seq(*items):
    """Yield each item once; then keep returning the last item."""
    it = iter(items)
    last = items[-1] if items else None
    def _(*_a, **_k):
        nonlocal last
        try:
            last = next(it)
        except StopIteration:
            pass
        return last
    return _


class TestRelay(unittest.TestCase):
    def setUp(self):
        # Stable fake FDs
        self.fd_in = 10
        self.fd_out = 11
        self.ser_fd = 100

        fd, path = tempfile.mkstemp(prefix="pirate_", suffix=".cfg")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(textwrap.dedent(
                """
                    [serial]
                    path = /dev/ttyGS0
                    baud = 115200
                    newline = crlf
                """
            ).lstrip())
        self.cfg_path = path
        Config.load(self.cfg_path)
    
    def tearDown(self):
        try:
            os.remove(self.cfg_path)
        except FileNotFoundError:
            pass

    def _mk_serial_mock(self):
        ser = MagicMock()
        ser.fileno.return_value = self.ser_fd
        ser.read.return_value = b""
        return ser

    def test_serial_disabled(self):
        with patch("serial.Serial") as serial_ctor, patch("pirate.lib.logger.Logger.debug") as log_debug:
            rl = SerialConsole(disable_serial=True)
            rl.stdio()

            serial_ctor.assert_not_called()
            log_debug.assert_called()

    def test_on_ready_fires_and_done_marker_exits(self):
        ser = self._mk_serial_mock()
        ser.read.side_effect = [b"hello", b"__PIRATE_DONE__"]

        writes = []
        def fake_write(fd, data):
            writes.append((fd, bytes(data)))
            return len(data)

        on_ready = MagicMock()

        with patch("serial.Serial", return_value=ser), \
             patch("select.select", side_effect=seq(([self.ser_fd], [], []),
                                                    ([self.ser_fd], [], []))), \
             patch("os.write", side_effect=fake_write):
            rl = SerialConsole(on_ready=on_ready, disable_serial=False)
            rl.stdio(in_fd=self.fd_in, out_fd=self.fd_out,
                     manage_tty=False, install_sigint_handler=False)

        on_ready.assert_called_once()
        # stdout got both chunks + CRLF on exit
        outs = [d for (fd, d) in writes if fd == self.fd_out]
        self.assertIn(b"hello", outs[0])
        self.assertIn(b"__PIRATE_DONE__", outs[1])
        self.assertTrue(any(o.endswith(b"\r\n") for o in outs))

    def test_done_marker_across_chunks(self):
        ser = self._mk_serial_mock()
        ser.read.side_effect = [b"__PIRATE_", b"DONE__"]

        with patch("serial.Serial", return_value=ser), \
             patch("select.select", side_effect=seq(([self.ser_fd], [], []),
                                                    ([self.ser_fd], [], []))), \
             patch("os.write") as osw:
            rl = SerialConsole(disable_serial=False)
            rl.stdio(in_fd=self.fd_in, out_fd=self.fd_out,
                     manage_tty=False, install_sigint_handler=False)

        # CRLF appended on exit
        self.assertTrue(any(args[0][1].endswith(b"\r\n") for args in osw.call_args_list))

    def test_detach_on_ctrl_bracket(self):
        ser = self._mk_serial_mock()

        with patch("serial.Serial", return_value=ser), \
             patch("select.select", side_effect=seq(([self.fd_in], [], []))), \
             patch("os.read", return_value=b"\x1d"), \
             patch("os.write"):
            rl = SerialConsole(disable_serial=False)
            rl.stdio(in_fd=self.fd_in, out_fd=self.fd_out,
                     manage_tty=False, install_sigint_handler=False)

        writes = b"".join(call.args[0] for call in ser.write.call_args_list)
        self.assertNotIn(b"\x04", writes)  # no EOF sent

    def test_stdin_close_sends_eof(self):
        ser = self._mk_serial_mock()

        with patch("serial.Serial", return_value=ser), \
             patch("select.select", side_effect=seq(([self.fd_in], [], []))), \
             patch("os.read", return_value=b""), \
             patch("os.write"):
            rl = SerialConsole(disable_serial=False)
            rl.stdio(in_fd=self.fd_in, out_fd=self.fd_out,
                     manage_tty=False, install_sigint_handler=False)

        ser.write.assert_any_call(b"\x04")

    def test_lone_ctrl_d_then_detach(self):
        ser = self._mk_serial_mock()

        with patch("serial.Serial", return_value=ser), \
             patch("select.select", side_effect=seq(([self.fd_in], [], []),
                                                    ([self.fd_in], [], []))), \
             patch("os.read", side_effect=[b"\x04", b"\x1d"]), \
             patch("os.write"):
            rl = SerialConsole(disable_serial=False)
            rl.stdio(in_fd=self.fd_in, out_fd=self.fd_out,
                     manage_tty=False, install_sigint_handler=False)

        writes = [args[0] for (args, _) in ser.write.call_args_list]
        self.assertIn(b"\x04", writes)   # EOF was sent

    def test_forwards_stdin_bytes_to_serial(self):
        ser = self._mk_serial_mock()

        with patch("serial.Serial", return_value=ser), \
             patch("select.select", side_effect=seq(([self.fd_in], [], []),
                                                    ([self.fd_in], [], []))), \
             patch("os.read", side_effect=[b"ls -la\n", b"\x1d"]), \
             patch("os.write"):
            rl = SerialConsole(disable_serial=False)
            rl.stdio(in_fd=self.fd_in, out_fd=self.fd_out,
                     manage_tty=False, install_sigint_handler=False)

        sent = b"".join(call.args[0] for call in ser.write.call_args_list)
        self.assertIn(b"ls -la\n", sent)

    def test_sigint_forwards_ctrl_c(self):
        ser = self._mk_serial_mock()
        captured = {}
        def capture_signal(sig, handler):
            captured["handler"] = handler

        with patch("serial.Serial", return_value=ser), \
             patch("signal.signal", side_effect=capture_signal), \
             patch("signal.getsignal", return_value=None), \
             patch("select.select", side_effect=seq(([self.fd_in], [], []))), \
             patch("os.read", return_value=b"\x1d"), \
             patch("os.write"):
            rl = SerialConsole(disable_serial=False)
            rl.stdio(in_fd=self.fd_in, out_fd=self.fd_out,
                     manage_tty=False, install_sigint_handler=True)

        # Simulate SIGINT after installation
        handler = captured.get("handler")
        self.assertIsNotNone(handler)
        handler(None, None)
        ser.write.assert_any_call(b"\x03")

    def test_restores_tty_on_exit(self):
        ser = self._mk_serial_mock()

        with patch("serial.Serial", return_value=ser), \
             patch("termios.tcgetattr", return_value=["old"]), \
             patch("termios.tcsetattr") as tcset, \
             patch("tty.setcbreak"), \
             patch("select.select", side_effect=seq(([self.fd_in], [], []))), \
             patch("os.read", return_value=b"\x1d"), \
             patch("os.write"):
            rl = SerialConsole(disable_serial=False)
            rl.stdio(in_fd=self.fd_in, out_fd=self.fd_out,
                     manage_tty=True, install_sigint_handler=False)

        # termios restored with the original settings
        self.assertTrue(tcset.called)
        args, _ = tcset.call_args
        self.assertEqual(args[2], ["old"])