# Dependencies
import os
import ctypes
import configparser
import time
import textwrap
from PIL import Image, ImageDraw, ImageGrab

# Config-related thingies
config = configparser.ConfigParser()
config.read("config.ini")
if "SETTINGS" not in config:
    config["SETTINGS"] = {}
# set default config stuff
config["SETTINGS"].setdefault(
    "DLLPath", r"C:\Program Files\Logitech Gaming Software\SDK\LCD\x64\LogitechLcd.dll")
config["SETTINGS"].setdefault("AppletName", r"Python LCD Controller")
config["SETTINGS"].setdefault("LCDType", r"MONO") # we ONLY support mono for now. ( i dont have a color g13 :3 )

with open('config.ini', 'w') as configfile:
    config.write(configfile)

# Init Config Vars
DLLPath = config["SETTINGS"]["DLLPath"]
# convert the applet name to the correct format for thhe dll
AppletName = ctypes.c_wchar_p(config["SETTINGS"]["AppletName"])
if config["SETTINGS"]["LCDType"] == "MONO":
    LCDType = 0x00000001  # Mono is HEX 1
else:
    LCDType = 0x00000002  # Color is HEX 2


# Code

# DLL Loading
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
    print(
        f"Could not load DLL. Ensure Python is 64-bit and path is correct:\n{e}")
    exit(1)

# Applet-related thingies
init_success = LogiLCDInit(AppletName, LCDType)  # create the applet
if not init_success:
    print("Failed to initialize LGS LCD SDK. Is LGS running?")
    exit(1)

# Functions to handle rendering

def wrapText(inputText):
    # Each line supports ~26-30 characters, so we'll need wrapping for each 26 characters (to be safe!)  -- SUBNOTE: IT TURNS OUT CHARACTERS ARENT MONOSPACED ON THIS THING. FUCCCCKKKKKKKKKKKKKKKKKKKK
    # This also means we need to split it up into a max of 4 lines for the mono display
    userText = textwrap.wrap(inputText, 26)[:4]
    for i, text in enumerate(userText):
        MonoSetText(i, ctypes.c_wchar_p(text))


def sendImage(img):  # takes in a 160x43 Pillow image in monochrome mode
    imgbytes = img.tobytes()
    byte_array_type = ctypes.c_byte * 6880
    lcd_buffer = byte_array_type.from_buffer(bytearray(imgbytes))
    MonoSetBackground(lcd_buffer)

# convert the image to the correct format for the LCD (160x43, monochrome)
def convertImage(img):
    img = img.convert("L")
    img = img.resize((160, 43), Image.Resampling.LANCZOS)
    # mono devices are EVIL and only support 2 states (on/off)
    img = img.point(lambda x: 255 if x >= 128 else 0)
    return img

def captureScreen():
    img = ImageGrab.grab()
    img = convertImage(img)
    sendImage(img)

try:
    if LogiLCDConnection(LCDType):  # check if an LCD is *actually* connected
        while True:
            sendImage(convertImage(Image.open("image.png")))
            LogiLCDUpdate()
            time.sleep(1/30)

    else:
        print("SDK initalized, but no device was detected")

finally:
    print("Shutting down applet")
    LogiLCDShutdown()
