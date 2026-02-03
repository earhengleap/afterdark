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

### Telegram Bot
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

## Environment Variables
The following environment variables are needed for the Telegram bot:
- BOT_TOKEN - Telegram bot token from BotFather
- API_ID - Telegram API ID
- API_HASH - Telegram API Hash
- CHAT_ID - Telegram chat/group ID

## Recent Changes
- 2026-02-03: Set up for Replit environment with Video Gallery Server workflow
