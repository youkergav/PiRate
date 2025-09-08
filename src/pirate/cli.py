#!/usr/bin/env python3
import argparse
import importlib
import sys

from pirate import __version__
from pirate.lib.config import Config
from pirate.lib.logger import Logger


class PayloadNotFoundError(Exception):
    """Raised when a requested payload module does not exist."""

    pass


def _resolve_payload(short_path: str):
    """
    Import 'pirate.payloads.<short_path>' and return the module object.

    Raises:
        PayloadNotFoundError: If the payload module doesn't exist.
        ImportError: If the module exists but fails due to an internal dependency.
    """

    full = f"pirate.payloads.{short_path}"
    try:
        return importlib.import_module(full)
    except ModuleNotFoundError as e:
        missing = getattr(e, "name", "") or ""

        if (
            isinstance(missing, str)
            and missing.startswith("pirate.payloads")
            and (missing == full or full.startswith(missing + "."))
        ):
            raise PayloadNotFoundError(f"No payload named '{short_path}'") from None

        raise


def _build_parser() -> argparse.ArgumentParser:
    """Build the top-level argparse parser with subcommands."""

    parser = argparse.ArgumentParser(prog="pirate", description="PiRate CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_version = sub.add_parser("version", help="Print the package version")
    p_version.set_defaults(handler=cmd_version)

    p_exec = sub.add_parser("execute", help="Execute a payload (e.g., macos.serial_shell)")
    p_exec.add_argument("payload", help="Under pirate.payloads, e.g. 'macos.serial_shell'")
    p_exec.set_defaults(handler=cmd_execute)

    return parser


def cmd_version(_: argparse.Namespace) -> int:
    """
    Print the package version.

    Args:
        _ (argparse.Namespace): Unused argparse namespace.

    Returns:
        int: Process exit code (0 on success).
    """

    print(__version__)
    return 0


def cmd_execute(ns: argparse.Namespace) -> int:
    try:
        Logger.info("Starting PiRate...")

        if Config.get("dev", "log_level", Logger.INFO) == Logger.DEBUG:
            Logger.debug("Developer logging enabled.")
        if Config.get("dev", "stack_trace_errors", False):
            Logger.debug("Stack trace errors enabled.")

        mod = _resolve_payload(ns.payload)
        main_fn = getattr(mod, "execute", None)
        if not callable(main_fn):
            Logger.error(f"Payload '{ns.payload}' is invalid: missing callable execute()")
            return 1

        Logger.info(f"Executing payload '{ns.payload}'...")
        main_fn()
        Logger.success("Payload complete.")
        return 0

    except PayloadNotFoundError as e:
        Logger.error(str(e))
        return 1
    except Exception as e:
        if Config.get("dev", "stack_trace_errors", False):
            raise

        Logger.error(f"Failed to run payload '{ns.payload}': {e}")
        return 1


def main(argv: list[str] | None = None) -> int:
    """
    Entry point for the `pirate` CLI.

    Initializes logging, loads configuration, and dispatches subcommands.

    Args:
        argv (list[str] | None): Arguments excluding the executable; if None, uses sys.argv[1:].

    Returns:
        int: Process exit code.
    """

    Logger.setup(Logger.INFO)

    # If your Config.load() needs a path, wire it here. Leaving as you had it:
    Config.load()
    Logger.set_level(Config.get("dev", "log_level", Logger.INFO))

    parser = _build_parser()
    ns = parser.parse_args(argv)
    return ns.handler(ns)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        if Config.get("dev", "stack_trace_errors", False):
            raise
        Logger.error(f"Error: {e}")
        sys.exit(1)
