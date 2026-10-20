# Before publishing NovaC to GitHub

## 1. Test locally
Test cursor movement, clicks, scroll, drag-and-drop, volume gestures, media buttons, and all keyboard layouts.

## 2. Keep local files out of Git
The `.gitignore` excludes `.venv/`, build outputs, IDE files, and `novac_settings.json`. Do not upload passwords, API keys, private logs, or personal screenshots.

## 3. Initialize Git (from this project folder)
```powershell
git init
git add .
git status
git commit -m "Initial NovaC gesture control project"
```
Review `git status` before committing.

## 4. Create a GitHub repository
Create an empty repository on GitHub, then use the commands shown by GitHub to add the remote and push the commit.

## 5. Setup
Python 3.11 (64-bit) is recommended. Install with `pip install -r requirements.txt`, then run `python main.py`.
