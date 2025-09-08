import os
import tempfile
import textwrap
import types
import unittest
from unittest.mock import MagicMock, patch

import pirate.cli as cli
from pirate.lib.config import Config
from pirate.lib.logger import Logger


class TestCLI(unittest.TestCase):
    def setUp(self):
        fd, path = tempfile.mkstemp(prefix="pirate_", suffix=".cfg")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(
                textwrap.dedent(
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
                ).lstrip()
            )

        self.path = path
        Config.load(self.path)
        Logger.setup(Logger.DEBUG)
        Logger._logger.handlers.clear()  # Silence std logs

    def tearDown(self):
        if os.path.exists(self.path):
            os.remove(self.path)

    def test_version_command(self):
        parser = cli._build_parser()
        ns = parser.parse_args(["version"])
        with patch("builtins.print") as mock_print:
            rc = ns.handler(ns)
        self.assertEqual(rc, 0)
        mock_print.assert_called_once_with(cli.__version__)

    def test_execute_valid_payload(self):
        fake_mod = types.SimpleNamespace(execute=MagicMock())
        with patch("pirate.cli._resolve_payload", return_value=fake_mod):
            parser = cli._build_parser()
            ns = parser.parse_args(["execute", "macos.serial_shell"])
            rc = ns.handler(ns)

        self.assertEqual(rc, 0)
        fake_mod.execute.assert_called_once()

    def test_execute_missing_payload(self):
        with (
            self.assertLogs(Logger._logger.name, level="ERROR") as cm,
            patch("pirate.cli._resolve_payload", side_effect=cli.PayloadNotFoundError("No payload named 'foo.bar'")),
        ):
            parser = cli._build_parser()
            ns = parser.parse_args(["execute", "foo.bar"])
            rc = ns.handler(ns)

        self.assertEqual(rc, 1)
        self.assertTrue(any("No payload named 'foo.bar'" in line for line in cm.output))

    def test_execute_invalid_payload(self):
        fake_mod = types.SimpleNamespace()  # missing execute()
        with (
            self.assertLogs(Logger._logger.name, level="ERROR") as cm,
            patch("pirate.cli._resolve_payload", return_value=fake_mod),
        ):
            parser = cli._build_parser()
            ns = parser.parse_args(["execute", "foo.invalid"])
            rc = ns.handler(ns)

        self.assertEqual(rc, 1)
        self.assertTrue(any("missing callable execute()" in line for line in cm.output))

    def test_main_runs_version(self):
        with patch("sys.argv", ["pirate", "version"]), patch("builtins.print") as mock_print:
            rc = cli.main()
        self.assertEqual(rc, 0)
        mock_print.assert_called_once_with(cli.__version__)
