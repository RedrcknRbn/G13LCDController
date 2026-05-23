# Dependencies
import os
import ctypes
import configparser
import time
import textwrap

# Config-related thingies
config = configparser.ConfigParser()
config.read("config.ini")
if "SETTINGS" in config: # there's *probably* a better way of doing this, but idk how to do it yet
    if not "DLLPath" in config["SETTINGS"]:
        config["SETTINGS"]["DLLPath"] = r"C:\Program Files\Logitech Gaming Software\SDK\LCD\x64\LogitechLcd.dll"
    if not "AppletName" in config["SETTINGS"]:
        config["SETTINGS"]["AppletName"] = r"Python LCD Controller"
    if not "LCDType" in config["SETTINGS"]:
        config["SETTINGS"]["LCDType"] = r"MONO" # we default to mono as it'll be the safest (i think)
else:
    config["SETTINGS"] = {
        "DLLPath": r"C:\Program Files\Logitech Gaming Software\SDK\LCD\x64\LogitechLcd.dll",
        "AppletName": r"Python LCD Controller",
        "LCDType": r"MONO"
    }

with open('config.ini', 'w') as configfile:
    config.write(configfile)
    
## Init Config Vars
DLLPath = config["SETTINGS"]["DLLPath"]
AppletName = ctypes.c_wchar_p(config["SETTINGS"]["AppletName"]) # convert the applet name to the correct format for thhe dll
if config["SETTINGS"]["LCDType"] == "MONO":
    LCDType = 0x00000001 # Mono is HEX 1
else:
    LCDType = 0x00000002 # Color is HEX 2


# Code

## DLL Loading
try:
    LogiLCD = ctypes.CDLL(DLLPath)
    # attempt to load the needed DLL functions
    LogiLCDInit = LogiLCD.LogiLcdInit
    LogiLCDUpdate = LogiLCD.LogiLcdUpdate
    LogiLCDShutdown = LogiLCD.LogiLcdShutdown
    LogiLCDConnection = LogiLCD.LogiLcdIsConnected
    # mono functions
    MonoSetText = LogiLCD.LogiLcdMonoSetText
    MonoSetBackground = LogiLCD.LogiLcdMonoSetBackground
except OSError as e:
    print(f"Could not load DLL. Ensure Python is 64-bit and path is correct:\n{e}")
    exit(1)

## Applet-related thingies
init_success = LogiLCDInit(AppletName, LCDType) # create the applet
if not init_success:
    print("Failed to initialize LGS LCD SDK. Is LGS running?")
    exit(1)

try:
    if LogiLCDConnection(LCDType): # check if an LCD is *actually* connected
        # Each line supports ~26-30 characters, so we'll need wrapping for each 26 characters (to be safe!)  -- SUBNOTE: IT TURNS OUT CHARACTERS ARENT MONOSPACED ON THIS THING. FUCCCCKKKKKKKKKKKKKKKKKKKK
        # This also means we need to split it up into a max of 4 lines for the mono display
        userText = textwrap.wrap(input("Text: "),26)[:4]
        for i, text in enumerate(userText):
            MonoSetText(i, ctypes.c_wchar_p(text))
        LogiLCDUpdate()
        time.sleep(1)
        input("Enter to shut down")
        
    else:
        print("SDK initalized, but no device was detected")

finally:
    print("Shutting down applet")
    LogiLCDShutdown()