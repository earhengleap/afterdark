# X Downloader Web

## Overview
A web-based X/Twitter video and image downloader with Telegram upload functionality. Built with FastAPI backend serving a responsive web interface.

## Project Structure
```
/
├── x_downloader_web/     # Main web application
│   ├── web_backend.py    # FastAPI server (runs on port 5000)
│   ├── templates/        # Jinja2 HTML templates
│   ├── static/           # CSS, JS assets
│   └── data/             # Downloaded files storage
├── core/                 # Core download/upload logic
├── config/               # Configuration files
├── handlers/             # Telegram bot handlers
├── models/               # Data models
├── ui/                   # UI components
├── utils/                # Utility functions
└── x_telegram.py         # Telegram bot entry point
```

## Running the Application
The web server runs on port 5000 using FastAPI with Uvicorn:
```bash
cd x_downloader_web && python web_backend.py
```

## Dependencies
- Python 3.11
- FastAPI + Uvicorn for web server
- yt-dlp for video downloading
- Pyrogram/Pyrofork for Telegram integration
- Pydantic for data validation

## Features
- Download videos and images from X/Twitter URLs
- Bulk download support
- Upload to Telegram
- Task tracking and progress display
- File management interface

## Recent Changes
- 2026-02-01: Imported from GitHub and configured for Replit environment
  - Changed web server port from 8000 to 5000
  - Installed Python 3.11 and all dependencies
  - Set up workflow for web server
