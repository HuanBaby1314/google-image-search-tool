# Google Image Search Tool

<div align="center">

![Chrome Extension](https://img.shields.io/badge/Chrome-Extension-blue?style=flat-square&logo=google-chrome)
![Python](https://img.shields.io/badge/Python-3.8+-yellow?style=flat-square&logo=python)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)
![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey?style=flat-square)

**Batch download web images and upload to Google Image Search**

[Features](#features) • [Quick Start](#quick-start) • [Usage](#usage) • [Development](#development) • [Changelog](#changelog)

</div>

---

## Features

- 🔍 **Smart Scanning** - Scan page images, support lazy loading and Shadow DOM
- 📥 **Batch Download** - One-click download selected images with auto date directory
- 🔍 **Google Search** - Auto upload images to Google Image Search
- 🔄 **Skip Duplicates** - Auto skip already searched images
- 🖥️ **System Tray** - Local service runs in system tray
- 🛠️ **Debug Mode** - Step-by-step debugging support

## Quick Start

### 1. Install Chrome Extension

1. Download [latest release](https://github.com/YOUR_USERNAME/google-image-search-tool/releases)
2. Open Chrome/Edge browser
3. Go to `chrome://extensions/` or `edge://extensions/`
4. Enable "Developer mode"
5. Click "Load unpacked"
6. Select `chrome-extension` folder

### 2. Start Local Service

**Option 1: Run exe (Recommended)**
```
Double-click dist/GoogleImageSearch.exe
```

**Option 2: Run with Python**
```bash
cd local-server
pip install -r requirements.txt
python server.py
```

### 3. Usage

1. Open a webpage with images
2. Click the extension icon
3. Click "Scan Page Images"
4. Select images
5. Click "Google Search"

## Usage

### Scan Images

- Click "Scan Page Images" button
- Supports: regular images, lazy-loaded images, Shadow DOM images
- Auto filters SVG and small icons

### Download Images

- Select images to download
- Click "Download Selected"
- Images saved to `Downloads/qingqing_helper_dir/date/` directory
- Downloaded images marked as "Downloaded"

### Google Search

- Select images and click "Google Search"
- Auto executes: open search page → click upload → select file → search
- Already searched images are auto-skipped

### Local Images

- Click "Local Images" to select local files
- Local images use original path, no duplicate download

### Debug Mode

- Click 🐛 icon to enter debug mode
- Step-by-step execution
- Detailed execution logs

## Development

### Project Structure

```
google-image-search-tool/
├── chrome-extension/          # Chrome Extension
│   ├── manifest.json          # Extension config
│   ├── background.js          # Background service
│   ├── popup.html             # Popup UI
│   ├── popup.js               # UI logic
│   └── icons/                 # Extension icons
├── local-server/              # Local Server
│   ├── server.py              # Flask server (dev)
│   ├── tray_service.py        # System tray (production)
│   ├── upload_handler.py      # pyautogui file operations
│   ├── build.bat              # Build script
│   ├── build.spec             # PyInstaller config
│   └── requirements.txt       # Python dependencies
├── LICENSE                    # MIT License
└── README.md                  # This file
```

### Development Environment

**Chrome Extension:**
- Chrome/Edge browser
- Developer mode enabled

**Local Server:**
- Python 3.8+
- Dependencies: Flask, pyautogui, pyperclip, pygetwindow, pywin32

### Build & Release

```bash
cd local-server
build.bat
```

Output: `dist/GoogleImageSearch.exe`

## Changelog

### v1.0.0 (2026-06-04)

- ✨ Initial release
- 🔍 Page image scanning (Shadow DOM support)
- 📥 Batch image download
- 🔍 Google Image Search
- 🖥️ System tray service
- 🛠️ Debug mode
- 📝 Search history persistence

## License

This project is licensed under the [MIT License](LICENSE).

---

<div align="center">

**English** | **[中文](README.md)**

Made with ❤️

</div>