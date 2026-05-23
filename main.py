# Dependencies
import os
import ctypes
import configparser
import time
import textwrap
import imageio
from PIL import Image, ImageDraw, ImageGrab, GifImagePlugin

# Config-related thingies
config = configparser.ConfigParser()
config.read("config.ini")
if "SETTINGS" not in config:
    config["SETTINGS"] = {}
# set default config stuff
config["SETTINGS"].setdefault(
    "DLLPath", r"C:\Program Files\Logitech Gaming Software\SDK\LCD\x64\LogitechLcd.dll")
config["SETTINGS"].setdefault("AppletName", r"Python LCD Controller")
# we ONLY support mono for now. ( i dont have a color g13 :3 )
config["SETTINGS"].setdefault("LCDType", r"MONO")
config["SETTINGS"].setdefault("MediaPath", r"./media")

with open('config.ini', 'w') as configfile:
    config.write(configfile)

# Init Config Vars
DLLPath = config["SETTINGS"]["DLLPath"]
MediaPath = config["SETTINGS"]["MediaPath"]
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

# wraps a string and send to the driver
def wrapText(inputText):
    # Each line supports ~26-30 characters, so we'll need wrapping for each 26 characters (to be safe!)  -- SUBNOTE: IT TURNS OUT CHARACTERS ARENT MONOSPACED ON THIS THING. FUCCCCKKKKKKKKKKKKKKKKKKKK
    # This also means we need to split it up into a max of 4 lines for the mono display
    userText = textwrap.wrap(inputText, 26)[:4]
    for i, text in enumerate(userText):
        MonoSetText(i, ctypes.c_wchar_p(text))

# sends the image to the driver
def sendImage(img):  # takes in a 160x43 Pillow image in monochrome mode
    if img:
        imgbytes = img.tobytes()
        byte_array_type = ctypes.c_byte * 6880
        lcd_buffer = byte_array_type.from_buffer(bytearray(imgbytes))
        MonoSetBackground(lcd_buffer)

# convert the image to the correct format for the LCD (160x43, monochrome)
def convertImage(img):
    if img:
        img = img.convert("L")
        img = img.resize((160, 43), Image.Resampling.LANCZOS)
        # mono devices are EVIL and only support 2 states (on/off)
        img = img.point(lambda x: 255 if x >= 128 else 0)
        return img

# screenshot!
def captureScreen():
    img = ImageGrab.grab()
    img = convertImage(img)
    sendImage(img)

# decodes a file and returns a list of Pillow images
def openAndDecodeImage(path):
    table = []
    fps = 1  # default fps (so images show for 1 second if the file is not a video or animated image)
    try:
        with Image.open(path) as img:
            img.verify()  # verify that it's a Pillow supported format
            # check to see if its gif or apng (or any other formats that are animated)
            if img.is_animated:
                durations = [] # we want to average out the duration because im lazy and dont wanna write a per-frame sleep
                for frame in range(img.n_frames):
                    img.seek(frame)
                    table.append(convertImage(img.copy()))
                    durations.append(img.info.get('duration', 100))  # default to 100ms if not available
                fps = 1000 / (sum(durations) / len(durations)) # ugly math!
            else:
                table.append(convertImage(img))
    except:  # if its not Pillow supported, it's possibly a video file
        try:
            reader = imageio.get_reader(path)
            fps = reader.get_meta_data().get('fps', 30)  # default to 30 fps if not available
            for frame in reader:
                pil_image = Image.fromarray(frame)
                table.append(convertImage(pil_image))
        except:  # its an evil file
            print(f"Error occurred while processing file: {path}")
    return table, fps

# loop thru a folder to find media files and display them
def loopThroughFolder(folder):
    for filename in os.listdir(folder):
        print(f"Processing file: {filename}")
        table, fps = openAndDecodeImage(os.path.join(folder, filename))
        for img in table:
            sendImage(img)
            LogiLCDUpdate()
            time.sleep(1/fps)  # delay to control frame rate


try:
    if LogiLCDConnection(LCDType):  # check if an LCD is *actually* connected
        while True:
            # main loop
            loopThroughFolder(MediaPath)

    else:
        print("SDK initalized, but no device was detected")

finally:
    print("Shutting down applet")
    LogiLCDShutdown()
