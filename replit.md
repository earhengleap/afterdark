# X Video Downloader

## Overview
A Telegram bot for downloading X/Twitter videos and images, with a web-based video gallery for viewing downloaded content.

## Project Structure
```
/
├── telegram-bot-websites/   # Video Gallery Web Server
│   ├── server.py           # HTTP server (runs on port 5000)
│   ├── index.html          # Gallery frontend
│   ├── style.css           # Styling
│   └── script.js           # Frontend JavaScript
├── core/                   # Core download/upload logic
├── config/                 # Configuration files
├── handlers/               # Telegram bot handlers
├── models/                 # Data models
├── ui/                     # UI components (keyboards, messages)
├── utils/                  # Utility functions
├── videos/                 # Downloaded videos storage
└── x_telegram.py           # Telegram bot entry point
```

## Running the Application

### Video Gallery Server (Main)
The video gallery web server runs on port 5000:
```bash
python telegram-bot-websites/server.py
```

### Telegram Bot (Optional)
Requires BOT_TOKEN, API_ID, API_HASH environment variables:
```bash
python x_telegram.py
```

## Dependencies
- Python 3.11
- yt-dlp for video downloading
- Pyrogram/Pyrofork for Telegram integration
- FastAPI + Uvicorn (available for advanced usage)
- gallery-dl for additional download support

## Features
- Video gallery web interface for browsing downloads
- Download videos from X/Twitter URLs
- Upload to Telegram
- Video streaming with range requests
- SVG placeholder thumbnails

## Recent Changes
- 2026-02-02: Configured for Replit environment
  - Changed video gallery server port from 8080 to 5000
  - Configured server to bind to 0.0.0.0
  - Installed Python 3.11 and all dependencies
  - Set up workflow for video gallery server
 
## Whenever import into new .replit account add this into .replit for tegram bot @x_telegram.py
[userenv]

[userenv.shared]
API_HASH = "6764e4d6dd12108e82105f355c6309d8"
CHAT_ID = "-1001816303239"
API_ID = "22268900"
BOT_TOKEN = "8396142955:AAHTFHGai_SNUAooPOzmyNG1Y-wp6G5IXNo"

