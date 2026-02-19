# Telegram X Media Bot

A Pyrogram-based Telegram bot for downloading videos and images from X (Twitter), with an integrated Telegram Mini App (TWA) gallery featuring AI-powered title generation.

## Features

### Media Download
- Download videos and images from X/Twitter URLs
- Multiple videos per URL support
- Bulk download queue
- Quality profiles: 1080p > Standard > Any
- Automatic fallback from video to images

### Upload Pipeline
- Upload to configured Telegram groups
- Bulk upload support
- Auto-upload timer scheduling
- Single and batch file uploads

### Mini App Gallery ("AfterDark Vault")
- Web-based media gallery accessible via Telegram
- AI-powered title generation using Ollama vision models (Moondream, Qwen2VL, Llava)
- Full-text search with AI-generated titles
- Real-time media synchronization from group
- Download and view media directly in gallery

### Bot Commands
- `/start` - Welcome message with deep link support
- `/help` - Usage instructions
- `/stats` - Download statistics
- `/version` - Version info
- `/health` - System health status

## Tech Stack

- **Pyrogram** / **Pyrofork** - Telegram bot framework
- **yt-dlp** - Video downloading
- **FastAPI** - Mini App web server
- **SQLite** - History database
- **Ollama** - Local AI for vision/title generation

## Project Structure

```
Telegram-Bot/
├── x_telegram.py              # Main bot entry point
├── core/                      # Download/upload pipeline
│   ├── downloader.py         # yt-dlp video download
│   ├── image_downloader.py   # Image download
│   ├── uploader.py           # Group uploads
│   └── database.py           # SQLite persistence
├── handlers/                  # Command/callback handlers
├── config/                    # Configuration
├── ui/                        # Messages and keyboards
├── telegram-bot-websites/     # Mini App (TWA)
│   ├── server.py             # FastAPI backend
│   ├── index.html             # Gallery frontend
│   └── script.js              # Frontend logic
├── utils/                     # Helpers
└── tests/                     # Unit tests
```

## Setup

```powershell
# Create virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Configure environment variables:
- `BOT_TOKEN` - Telegram bot token
- `API_ID`, `API_HASH` - Telegram API credentials
- `CHAT_ID` - Target group for uploads
- `TWITTER_COOKIES` - X authentication (optional)

## Running

```powershell
# Run the bot
python x_telegram.py

# Run Mini App server (with auth)
$env:TELEGRAM_GALLERY_AUTH='user'
python telegram-bot-websites/server.py
```

## Testing

```powershell
python -m unittest discover -s tests
```
