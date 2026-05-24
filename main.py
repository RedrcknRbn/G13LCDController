# Dependencies
import os
import ctypes
import configparser
import time
import textwrap
import imageio
import threading
import queue
from PIL import Image, ImageDraw, ImageGrab, GifImagePlugin, UnidentifiedImageError
try:
    import pystray
    from pystray import Icon, MenuItem, Menu
except Exception:
    pystray = None

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
config["DEFAULT"].setdefault("StartupProfile", "default")
config["DEFAULT"].setdefault("ProfileOrder", "")

# Profile support
profile_names = [section for section in config.sections() if section != configparser.DEFAULTSECT]
if not profile_names:
    config["base"] = {}
    config["base"].setdefault("Name", "Base Profile")
    config["base"].setdefault("MediaPath", config["DEFAULT"]["MediaPath"])
    config["base"].setdefault("MediaType", config["DEFAULT"]["MediaType"])
    profile_names = ["base"]

profile_order_input = config["DEFAULT"].get("ProfileOrder", "")
ordered_profiles = [name.strip() for name in profile_order_input.split(",") if name.strip() in profile_names]
ordered_profiles += [name for name in profile_names if name not in ordered_profiles]
if not ordered_profiles:
    ordered_profiles = profile_names

startup_profile = config["DEFAULT"].get("StartupProfile", ordered_profiles[0])
if startup_profile not in ordered_profiles:
    startup_profile = ordered_profiles[0]

config["DEFAULT"]["ProfileOrder"] = ", ".join(ordered_profiles)
config["DEFAULT"]["StartupProfile"] = startup_profile
with open('config.ini', 'w') as configfile:
    config.write(configfile)


def load_profile(section_name):
    section = config[section_name]
    return {
        "name": section.get("Name", section_name),
        "media_path": section.get("MediaPath", config["DEFAULT"]["MediaPath"]),
        "media_type": section.get("MediaType", config["DEFAULT"]["MediaType"]).upper(),
        "lcd_type": 0x00000001 if section.get("LCDType", config["DEFAULT"]["LCDType"]).upper() == "MONO" else 0x00000002,
        "applet_name": section.get("AppletName", config["DEFAULT"]["AppletName"]),
    }

active_profile_names = ordered_profiles
active_profile_index = active_profile_names.index(startup_profile)
active_profile = load_profile(startup_profile)
DLLPath = config["DEFAULT"]["DLLPath"]
MediaPath = active_profile["media_path"]
MediaType = active_profile["media_type"]
# convert the applet name to the correct format for thhe dll
AppletName = ctypes.c_wchar_p(active_profile["applet_name"])
LCDType = active_profile["lcd_type"]


# Code

# DLL Loading
try:
    LogiLCD = ctypes.CDLL(DLLPath)
    
    # attempt to load the needed DLL functions
    LogiLCDInit = LogiLCD.LogiLcdInit # LogiLcdInit(wchar_t* displayName, int displayType)
    # displayType: Mono (0x00000001) or Color (0x00000002)
    
    LogiLCDConnection = LogiLCD.LogiLcdIsConnected # LogiLcdIsConnected(int displayType)
    # displayType: Mono (0x00000001) or Color (0x00000002)
    
    LogiLCDButtonPressed = LogiLCD.LogiLcdIsButtonPressed # LogiLcdIsButtonPressed(int buttonFlag)
    button_queue = queue.Queue()
    PROFILE_BUTTON_PREV = 0x00000001
    PROFILE_BUTTON_NEXT = 0x00000002
    BUTTON_FLAGS = (PROFILE_BUTTON_PREV, PROFILE_BUTTON_NEXT, 0x00000004, 0x00000008, 0x00000010, 0x00000020, 0x00000040)
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
    # lineNumber: 0-3 for mono displays, 0-7 for color displays
    
    MonoSetBackground = LogiLCD.LogiLcdMonoSetBackground # LogiLcdMonoSetBackground(BYTE monoBitmap[])
    
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
    lines = []
    if inputText is None:
        inputText = ""
    for raw_line in str(inputText).splitlines():
        # preserve empty lines
        if raw_line.strip() == "":
            lines.append("")
        else:
            wrapped = textwrap.wrap(raw_line, 26)
            if not wrapped:
                lines.append("")
            else:
                lines.extend(wrapped)

    # limit to 4 lines for the mono display and send each line
    lines = lines[:4]
    for i in range(4):
        text = lines[i] if i < len(lines) else ""
        MonoSetText(i, ctypes.c_wchar_p(text))
    LogiLCDUpdate()

# sends the image to the driver
def sendImage(img):  # takes in a 160x43 Pillow image in monochrome mode
    if img:
        imgbytes = img.tobytes()
        byte_array_type = ctypes.c_byte * 6880
        lcd_buffer = byte_array_type.from_buffer(bytearray(imgbytes))
        MonoSetBackground(lcd_buffer)
        LogiLCDUpdate()

# clear the ENTIRE screen
def clearScreen():
    # send an all-zero buffer to clear background
    byte_array_type = ctypes.c_byte * 6880
    empty_buffer = byte_array_type.from_buffer(bytearray(b"\x00" * 6880))
    MonoSetBackground(empty_buffer)
    # clear text lines (mono supports 4 lines)
    for i in range(4):
        MonoSetText(i, ctypes.c_wchar_p(""))
    LogiLCDUpdate()

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
    except (UnidentifiedImageError, FileNotFoundError, OSError):
        # Not an image Pillow can handle or file cannot be opened; try reading as a video with imageio
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
    if not os.path.isdir(folder):
        print(f"Media folder not found: {folder}")
        time.sleep(1)
        return

    for filename in os.listdir(folder):
        if profile_change_event.is_set():
            return
        print(f"Processing file: {filename}")
        table, fps = openAndDecodeImage(os.path.join(folder, filename))
        for img in table:
            if profile_change_event.is_set():
                return
            sendImage(img)
            LogiLCDUpdate()
            time.sleep(1/fps)  # delay to control frame rate

# show a single file
def displayFile(path):
    table, fps = openAndDecodeImage(path)
    for img in table:
        if profile_change_event.is_set():
            return
        sendImage(img)
        LogiLCDUpdate()
        time.sleep(1/fps)


# safely read a text file path and return its contents
def read_text_file(path, max_chars=10_000):
    try:
        if not path:
            return ""
        # Expand user and make absolute for safety
        path = os.path.expanduser(path)
        if not os.path.exists(path):
            print(f"Text file not found: {path}")
            return ""
        if not os.path.isfile(path):
            print(f"Path is not a file: {path}")
            return ""
        # Open with utf-8 and replace errors to avoid decode exceptions
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read(max_chars)
            return content
    except PermissionError:
        print(f"Permission denied reading file: {path}")
    except OSError as e:
        print(f"OS error reading file {path}: {e}")
    return ""

# create a thread to check for button presses without blocking the main thread
lastPressed = []
def asyncButtonWorker():
    global lastPressed
    while not shutdown_event.is_set() and getattr(threading.current_thread(), "do_run", True):
        currentlyDown = [flag for flag in BUTTON_FLAGS if LogiLCDButtonPressed(flag)]
        newPressed = [btn for btn in currentlyDown if btn not in lastPressed]
        lastPressed = currentlyDown
        if newPressed:
            button_queue.put(newPressed)
            handleButtonPresses()
        time.sleep(0.02)

profile_lock = threading.Lock()
profile_change_event = threading.Event()
shutdown_event = threading.Event()
input_thread = None

# switch profiles and update global variables accordingly
def set_active_profile(new_index):
    global active_profile_index, active_profile, MediaPath, MediaType, AppletName, LCDType
    new_index %= len(active_profile_names)
    if new_index == active_profile_index:
        return
    active_profile_index = new_index
    active_profile = load_profile(active_profile_names[active_profile_index])
    MediaPath = active_profile["media_path"]
    MediaType = active_profile["media_type"]
    AppletName = ctypes.c_wchar_p(active_profile["applet_name"])
    LCDType = active_profile["lcd_type"]
    print(f"Switched to profile: {active_profile['name']} ({active_profile_names[active_profile_index]})")
    profile_change_event.set()

# check and perform button actions
def handleButtonPresses():
    try:
        currentlyPressed = button_queue.get_nowait()
        print(f"Buttons currently pressed: {currentlyPressed}")
        for btn in currentlyPressed:
            if btn == PROFILE_BUTTON_PREV:
                set_active_profile(active_profile_index - 1)
            elif btn == PROFILE_BUTTON_NEXT:
                set_active_profile(active_profile_index + 1)
    except queue.Empty:
        currentlyPressed = None

def main():
    try:
        if LogiLCDConnection(LCDType):  # check if an LCD is *actually* connected
            global input_thread
            input_thread = threading.Thread(target=asyncButtonWorker, daemon=True)
            input_thread.start()
            while not shutdown_event.is_set():
                clearScreen()
                if profile_change_event.is_set():
                    profile_change_event.clear()
                    continue

                if MediaType == "FOLDER":
                    loopThroughFolder(MediaPath)
                elif MediaType == "FILE":
                    displayFile(MediaPath)
                elif MediaType == "SCREEN":
                    captureScreen()
                elif MediaType == "TEXT":
                    text_content = read_text_file(MediaPath)
                    if text_content:
                        wrapText(text_content)
                    else:
                        clearScreen()
                    time.sleep(1)
                else:
                    print(f"Unknown media type: {MediaType}")
                    time.sleep(1)

                time.sleep(0.001)

        else:
            print("SDK initalized, but no device was detected")

    finally:
        if input_thread is not None:
            input_thread.do_run = False
            input_thread.join(timeout=1)
        print("Shutting down applet")
        LogiLCDShutdown()


if __name__ == "__main__":
    # Start the main applet loop in a background thread and run a system tray icon
    def on_tray_exit(icon, item):
        shutdown_event.set()
        # signal profile change to unblock folder loops
        profile_change_event.set()
        if input_thread is not None:
            input_thread.do_run = False
        icon.stop()

    # Start applet in a worker thread
    app_thread = threading.Thread(target=main, daemon=True)
    app_thread.start()

    # If pystray is available, create a tray icon with an Exit menu
    if pystray is not None:
        # create a simple icon image
        icon_img = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(icon_img)
        # draw a simple white rectangle as an icon placeholder
        draw.rectangle((8, 8, 56, 56), fill=(255, 255, 255, 255))
        tray_icon = Icon("G13LCDController", icon_img, "G13LCDController", menu=Menu(MenuItem('Exit', on_tray_exit)))
        try:
            tray_icon.run()
        except KeyboardInterrupt:
            on_tray_exit(tray_icon, None)
    else:
        # No pystray available — run until the app thread finishes
        try:
            while app_thread.is_alive():
                time.sleep(0.5)
        except KeyboardInterrupt:
            shutdown_event.set()
            profile_change_event.set()
            if input_thread is not None:
                input_thread.do_run = False
            app_thread.join(timeout=1)
