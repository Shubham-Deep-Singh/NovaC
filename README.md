# NovaC — Gesture Control Center

NovaC uses your webcam, OpenCV, MediaPipe, and PyAutoGUI to control your computer with hand gestures. This version includes a desktop control panel with a live camera preview.

## Requirements
- Windows 10/11
- Python 3.11, 64-bit recommended
- A working webcam

## Setup (PowerShell)
Open PowerShell in the `NovaC` folder:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python main.py
```

If PowerShell blocks activation, run this once in that PowerShell window, then activate again:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

## Controls
- **Move:** Raise your index finger and move your hand.
- **Left click:** Pinch thumb + index fingertip.
- **Right click:** Pinch thumb + middle fingertip.
- **Enter volume mode:** Hold an open palm for about 0.8 seconds.
- **Volume up/down:** In volume mode, spread thumb and index finger to raise volume; bring them close to lower it.
- **Exit volume mode:** Make a fist.
- Use the control panel toggles to disable mouse or volume gestures.
- Adjust mouse sensitivity using the slider.
- Press **Stop** in the panel to stop tracking.
- Click **Open floating keyboard** to open the always-on-top virtual keyboard.
- In the keyboard, click **Select typing window**. The keyboard hides for 3 seconds; click the destination application/text field during that time. The keyboard then reappears.
- Point the cursor at a virtual key and use the normal pinch-click gesture to press it. The keyboard also supports clicking keys directly.
- The keyboard includes letters, numbers, Space, Enter, Backspace, Tab, arrow keys, and a one-shot Shift toggle.

## Safety
PyAutoGUI's failsafe is enabled. Moving the cursor to the top-left corner of the screen triggers its emergency stop. Use this only in a safe environment and avoid running it while typing passwords or handling sensitive actions. The floating keyboard uses simulated input and may not work on secure Windows screens or elevated/admin prompts. Confirm the selected typing target before entering text.

## Troubleshooting
- If the camera does not open, close apps that may already be using it, then press Start again.
- If MediaPipe import errors occur, verify that Python 3.11 (64-bit) is active and reinstall using `pip install -r requirements.txt`.
- Tkinter is included with most standard Windows Python installations.


## Cursor movement troubleshooting
- Ensure **Virtual mouse + clicks** is checked in the NovaC panel.
- Start tracking and move your index fingertip around the camera view; the preview shows a teal circle around the tracked fingertip.
- This update uses a more responsive smoothing value and maps the central camera area to the screen.
- If the cursor still does not move, restart NovaC and check whether another app or Windows security prompt is blocking simulated mouse input.


## Added gesture and keyboard features
- **Scroll:** raise the index and middle fingers while keeping ring and pinky fingers down, then move the hand up or down.
- **Drag and drop:** point at an item, pinch thumb + index, and keep the pinch held for about 0.35 seconds to begin dragging. Move the hand while holding the pinch; release the pinch to drop.
- **Floating keyboard layouts:** use the ABC, Symbols, and Number pad buttons to change layouts. Caps Lock toggles persistent capitalization; Shift applies one-shot capitalization. Drag the keyboard by its Windows title bar to reposition it.
- These gestures can take a little practice. Test scrolling and drag-and-drop in a harmless window first.


## Final feature set before publishing
- Gesture mouse with adjustable sensitivity and reduced cursor jitter.
- Left/right click, scroll pose, and hold-pinch drag-and-drop.
- Volume gestures and quick media controls.
- Floating keyboard with ABC, Symbols, and Number pad layouts, Shift/Caps Lock, and typing preview.
- Camera index selection and saved settings in `novac_settings.json`.
- Desktop status panel with hand count and current action.

## Before publishing to GitHub
1. Test each gesture in a safe app such as Notepad and a harmless browser page.
2. Do not commit `.venv/`, `build/`, `dist/`, `__pycache__/`, or personal settings.
3. Check `git status` before committing. See `.gitignore`.
4. Explain in the README that simulated input may not work on secure Windows screens.


## Final improvements included
- Gesture scrolling and hold-pinch drag-and-drop.
- Floating keyboard with ABC, Symbols and Number pad layouts, Caps Lock/Shift, and typing preview.
- Media buttons for previous track, play/pause, and next track (supported by the active Windows app).
- Camera index selection, saved mouse/volume/sensitivity settings, and improved live status.
- Settings are stored locally in `novac_settings.json`, which is excluded from Git.

## Before publishing
Test every gesture and keyboard layout. Do not commit `.venv/`, build outputs, local settings, personal logs, or private screenshots. Simulated input may not work on secure Windows screens or administrator prompts.
