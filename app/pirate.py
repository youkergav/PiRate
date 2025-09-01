#!/usr/bin/env python3

import lib.payloads
from lib.config import Config
from lib.logger import Logger

def main():
    # Setup the environment
    Logger.setup(Logger.INFO)
    Logger.info("Starting PiRate...")
    
    Config.load()
    Logger.set_level(Config.get("dev", "log_level", Logger.INFO))

    # Setup dev mode if enabled.
    if Config.get("dev", "log_level", Logger.INFO) == Logger.DEBUG:
        Logger.debug("Developer logging enabled.")

    if Config.get("dev", "stack_trace_errors", False):
        Logger.debug("Stack trace errors enabled.")

    # Run the program
    lib.payloads.macos()

    return 0

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        if Config.get("dev", "stack_trace_errors", False):
            raise
        else:
            Logger.error(f"Error: {e}")
