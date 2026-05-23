# G13LCDController
This project displays images, GIFs, videos, or screen captures on the Logitech G13 LCD via the Logitech SDK.
## Requirements
- Windows
- Python 3.14.3+ (64-bit)
- Logitech Gaming Software installed with the `LogitechLcd.dll` SDK available
- A supported Logitech LCD device connected (G13, G15, G510, etc.)
## Setup
1. Clone the repository or download the project files.
2. Install dependencies:
```bash
   pip install -r requirements.txt
```
3. Open `config.ini` and update the DLL path if necessary.
## Configuration
The app uses `config.ini` for settings and profiles.
### Default options
- `dllpath` - path to `LogitechLcd.dll`
- `appletname` - name shown in the SDK applet list
- `lcdtype` - `MONO` or `COLOR` // Note, COLOR support is not yet implemented
- `mediapath` - default media path
- `mediatype` - `FOLDER`, `FILE`, `SCREEN`, `TEXT`
- `startupprofile` - profile to load on startup
- `profileorder` - comma-separated profile names to define switch order
### Profiles
Add sections below `[DEFAULT]` for each profile. Example:

```ini
[default]
name = Default
mediapath = ./media
mediatype = FOLDER

[screen]
name = Screen Capture
mediatype = SCREEN
```
Each profile can override:
- `Name`
- `MediaPath`
- `MediaType`
- `LCDType`
- `AppletName`
## Profile switching
Use the G13 button mapping to switch profiles at runtime:
- `Button 0` / left arrow: previous profile
- `Button 1` / right arrow: next profile
## Notes
- `FOLDER` mode loops through files in the configured folder.
- `FILE` mode displays a single file.
- `SCREEN` mode captures the screen and sends it to the LCD.
- `TEXT` mode takes in text from a file, with a max of 4 lines.
- If `config.ini` is missing required sections, the app creates a fallback base profile.
## Disclaimer
PRs are heavily encouraged, as I am still very new to python, and thus this codebase is a bit bad. You can get started by looking at `TODO.md`!

*Works with the Logitech G13 Programmable Gameboard with LCD Display®*
*This product is not affiliated with Logitech*
_Logitech, Logi, and their logos are trademarks or registered trademarks of Logitech Europe S.A. and/or its affiliates in the United States and/or other countries._