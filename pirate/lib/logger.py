import logging
from colorama import Fore, Style
        
class Logger:
    """A singleton class for handling formatted and colored logging."""

    _logger = None

    SUCCESS = 25
    INFO = logging.INFO
    WARNING = logging.WARN
    ERROR = logging.ERROR
    DEBUG = logging.DEBUG
    
    @classmethod
    def _log(cls, level: int, message: str) -> None:
        """Write a log message based on log level."""

        symbols = {
            cls.SUCCESS: f"{Fore.GREEN}{Style.BRIGHT}[+]{Style.RESET_ALL}",
            cls.INFO: f"{Fore.BLUE}{Style.BRIGHT}[*]{Style.RESET_ALL}",
            cls.WARNING: f"{Fore.YELLOW}{Style.BRIGHT}[!]{Style.RESET_ALL}",
            cls.ERROR: f"{Fore.RED}{Style.BRIGHT}[-]{Style.RESET_ALL}",
            cls.DEBUG: f"{Fore.LIGHTBLACK_EX}{Style.BRIGHT}[>]{Style.RESET_ALL}",
        }

        cls._logger.log(level, f"{symbols[level]} {message}")

    @classmethod
    def set_level(cls, level: int):
        """
        Sets a log level for the singleton.

        Args:
            level (int): The log level to set.
        """

        cls._logger.setLevel(level)

    @classmethod
    def setup(cls, log_level: int):
        """
        Sets up the Logger singleton.

        Args:
            level_level (int): The log level to set.
        """
        
        cls._logger = logging.getLogger("pirate_logger")
        cls._logger.setLevel((log_level))

        # Add stream handler
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        cls._logger.handlers.clear()
        cls._logger.addHandler(handler)

        # Add custom SUCCESS log level level
        logging.addLevelName(cls.SUCCESS, "SUCCESS")

    @classmethod
    def success(cls, message: str) -> None:
        """
        Logs a success message.

        Args:
            message (str): The success message to log.
        """

        cls._log(cls.SUCCESS, message)
    
    @classmethod
    def info(cls, message: str) -> None:
        """
        Logs a info message.

        Args:
            message (str): The info message to log.
        """

        cls._log(cls.INFO, message)
    
    @classmethod
    def warning(cls, message: str) -> None:
        """
        Logs a warning message.

        Args:
            message (str): The warning message to log.
        """

        cls._log(cls.WARNING, message)
    
    @classmethod
    def error(cls, message: str) -> None:
        """
        Logs an error message.

        Args:
            message (str): The error message to log.
        """

        cls._log(cls.ERROR, message)

    @classmethod
    def debug(cls, message: str) -> None:
        """
        Logs a debug message.

        Args:
            message (str): The debug message to log.
        """

        cls._log(cls.DEBUG, message)