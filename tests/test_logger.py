import io
import logging
import unittest

from colorama import Fore, Style

from pirate.lib.logger import Logger


class TestLogger(unittest.TestCase):
    def setUp(self):
        Logger._logger = None
        Logger.setup(logging.DEBUG)

        self.stream = io.StringIO()
        handler = Logger._logger.handlers[0]
        handler.stream = self.stream

    def _read_stream(self) -> str:
        """Flush and read the captured stream."""

        for h in Logger._logger.handlers:
            h.flush()
        return self.stream.getvalue()

    def test_setup(self):
        self.assertEqual(Logger._logger.name, "pirate")
        self.assertEqual(Logger._logger.level, logging.DEBUG)

        handlers = Logger._logger.handlers
        self.assertEqual(len(handlers), 1)
        self.assertIsInstance(handlers[0], logging.StreamHandler)
        self.assertIsNotNone(handlers[0].formatter)
        self.assertEqual(handlers[0].formatter._fmt, "%(message)s")

        self.assertEqual(logging.getLevelName(Logger.SUCCESS), "SUCCESS")  # Custom log level

    def test_set_level(self):
        current_level = Logger._logger.level

        Logger.set_level(Logger.INFO)
        self.assertEqual(Logger._logger.level, logging.INFO)

        Logger.set_level(current_level)  # Reset to debugger

    def test_log_success(self):
        message = "Operation completed"

        Logger.success(message)
        out = self._read_stream()

        self.assertEqual(out, f"{Fore.GREEN}{Style.BRIGHT}[+]{Style.RESET_ALL} {message}\n")

    def test_log_info(self):
        message = "Informational log"

        Logger.info(message)
        out = self._read_stream()

        self.assertEqual(out, f"{Fore.BLUE}{Style.BRIGHT}[*]{Style.RESET_ALL} {message}\n")

    def test_log_warning(self):
        message = "Be careful!"

        Logger.warning(message)
        out = self._read_stream()

        self.assertEqual(out, f"{Fore.YELLOW}{Style.BRIGHT}[!]{Style.RESET_ALL} {message}\n")

    def test_log_error(self):
        message = "An error has occured!"

        Logger.error(message)
        out = self._read_stream()

        self.assertEqual(out, f"{Fore.RED}{Style.BRIGHT}[-]{Style.RESET_ALL} {message}\n")

    def test_log_dev(self):
        message = "Verbose information here"

        Logger.debug(message)
        out = self._read_stream()

        self.assertEqual(out, f"{Fore.LIGHTBLACK_EX}{Style.BRIGHT}[>]{Style.RESET_ALL} {message}\n")

    def test_filtered_log(self):
        Logger.set_level("INFO")

        Logger.debug("This log should be filtered")
        out = self._read_stream()

        self.assertEqual(out, "")
