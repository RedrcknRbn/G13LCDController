# Dependencies
import os
import ctypes
import configparser
import time
import textwrap
import imageio
from PIL import Image, ImageDraw, ImageGrab, GifImagePlugin, UnidentifiedImageError

# Config-related thingies
config = configparser.ConfigParser()
config.read("config.ini")
if "DEFAULT" not in config:
    config["DEFAULT"] = {}
# set default config stuff
config["DEFAULT"].setdefault(
    "DLLPath", r"C:\Program Files\Logitech Gaming Software\SDK\LCD\x64\LogitechLcd.dll")
config["DEFAULT"].setdefault("AppletName", r"Python LCD Controller")
# we ONLY support mono for now. ( i dont have a color g13 :3 )
config["DEFAULT"].setdefault("LCDType", r"MONO")
config["DEFAULT"].setdefault("MediaPath", r"./media")
config["DEFAULT"].setdefault("MediaType", r"FOLDER") # FOLDER for looping through a folder, FILE for just displaying a single file, SCREEN for capturing the screen and displaying it

with open('config.ini', 'w') as configfile:
    config.write(configfile)

# Init Config Vars
DLLPath = config["DEFAULT"]["DLLPath"]
MediaPath = config["DEFAULT"]["MediaPath"]
MediaType = config["DEFAULT"]["MediaType"]
# convert the applet name to the correct format for thhe dll
AppletName = ctypes.c_wchar_p(config["DEFAULT"]["AppletName"])
if config["DEFAULT"]["LCDType"] == "MONO":
    LCDType = 0x00000001  # Mono is HEX 1
else:
    LCDType = 0x00000002  # Color is HEX 2


# Code

# DLL Loading
try:
    LogiLCD = ctypes.CDLL(DLLPath)
    
    # attempt to load the needed DLL functions
    LogiLCDInit = LogiLCD.LogiLcdInit # LogiLcdInit(wchar_t* displayName, int displayType)
    LogiLCDInit.restype = ctypes.c_bool
    LogiLCDInit.argtypes = [ctypes.c_wchar_p, ctypes.c_int]
    # displayType: Mono (0x00000001) or Color (0x00000002)
    
    LogiLCDConnection = LogiLCD.LogiLcdIsConnected # LogiLcdIsConnected(int displayType)
    LogiLCDConnection.restype = ctypes.c_bool
    LogiLCDConnection.argtypes = [ctypes.c_int]
    # displayType: Mono (0x00000001) or Color (0x00000002)
    
    LogiLCDButtonPressed = LogiLCD.LogiLcdIsButtonPressed # LogiLcdIsButtonPressed(int buttonFlag)
    LogiLCDButtonPressed.restype = ctypes.c_bool
    LogiLCDButtonPressed.argtypes = [ctypes.c_int]
    # Button Flag (Hex Constants)	G13 / G15 / G510 Soft-keys	G19 Color Soft-keys
    # 0x00000001	                Button 0 (Far Left)         Left Arrow Button
    # 0x00000002	                Button 1                    Right Arrow Button
    # 0x00000004	                Button 2                    Up Arrow Button
    # 0x00000008	                Button 3 (Far Right)	    Down Arrow Button
    # 0x00000010	                N/A	                        "OK" / Select Button
    # 0x00000020	                N/A	                        "Cancel" / Back Button
    # 0x00000040	                N/A	                        Menu Button
    
    LogiLCDUpdate = LogiLCD.LogiLcdUpdate # LogiLcdUpdate()
    LogiLCDShutdown = LogiLCD.LogiLcdShutdown # LogiLcdShutdown()
    
    # mono functions
    MonoSetText = LogiLCD.LogiLcdMonoSetText # LogiLcdMonoSetText(int lineNumber, wchar_t* text)
    MonoSetText.restype = ctypes.c_bool
    MonoSetText.argtypes = [ctypes.c_int, ctypes.c_wchar_p]
    # lineNumber: 0-3 for mono displays, 0-7 for color displays
    
    MonoSetBackground = LogiLCD.LogiLcdMonoSetBackground # LogiLcdMonoSetBackground(BYTE monoBitmap[])
    MonoSetBackground.restype = ctypes.c_bool
    MonoSetBackground.argtypes = [ctypes.POINTER(ctypes.c_ubyte)]
    
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
    LogiLCDUpdate()
    time.sleep(1/30)

# decodes a file and returns a list of Pillow images
def openAndDecodeImage(path):
    table = []
    fps = 0.5  # default fps (so images show for 2 seconds if the file is not a video or animated image)
    try:
        img = Image.open(path)
        # check to see if it's an animated image (GIF, APNG, etc.)
        if getattr(img, 'is_animated', False):
            durations = []
            frame_count = getattr(img, 'n_frames', 1)
            for frame in range(frame_count):
                img.seek(frame)
                table.append(convertImage(img.copy()))
                durations.append(img.info.get('duration', 100))  # default to 100ms
            if frame_count == 1:
                fps = 0.5
            else:
                fps = 1000 / (sum(durations) / len(durations))
        else:
            table.append(convertImage(img.copy()))
    except UnidentifiedImageError:
        # Not an image Pillow can handle; try reading as a video with imageio
        try:
            reader = imageio.get_reader(path)
            fps = reader.get_meta_data().get('fps', 30)  # default to 30 fps if not available
            for frame in reader:
                pil_image = Image.fromarray(frame)
                table.append(convertImage(pil_image))
        except Exception:
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
            if MediaType == "FOLDER":
                loopThroughFolder(MediaPath)
            if MediaType == "FILE":
                openAndDecodeImage(MediaPath)
            if MediaType == "SCREEN":
                captureScreen()

    else:
        print("SDK initalized, but no device was detected")

finally:
    print("Shutting down applet")
    LogiLCDShutdown()
