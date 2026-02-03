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
  - This server.py is the website for browsing or the place to watch the videos after downloaded.
  - [MUST] if you add this in to new project, make sure dont make any log of this website into the main log of @x_telegram.py, keep the main @x_telegram.py clean and simple. but if this already fixed no need to use this [MUST].
```bash
python telegram-bot-websites/server.py
```

### Telegram Bot
Requires BOT_TOKEN, API_ID, API_HASH environment variables:
  @x_telegram.py is the main file for the bot to run. Make sure this file is the pirority file to run the bot.  
```bash
python x_telegram.py
```

## Dependencies
- Python 3.11
- yt-dlp for video downloading
- Pyrogram/Pyrofork for Telegram integration
- FastAPI + Uvicorn (available for advanced usage)
- gallery-dl for additional download support

## Always add thi ENV into the .replit whenever create a new replit account 
[userenv]

[userenv.shared]
API_HASH = "6764e4d6dd12108e82105f355c6309d8"
CHAT_ID = "-1001816303239"
API_ID = "22268900"
BOT_TOKEN = "8396142955:AAHTFHGai_SNUAooPOzmyNG1Y-wp6G5IXNo"
