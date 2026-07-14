# AfterDark - Telegram Bot

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue.svg" alt="Python Version">
  <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License">
  <img src="https://img.shields.io/badge/Telegram-Bot_API-v20-orange.svg" alt="Telegram API">
</p>

A robust and feature-rich Telegram bot for downloading media from X (Twitter), RedGifs, and other platforms. Features include bulk downloads, AI-powered media categorization, group synchronization, and Videy CDN uploads.

## Features

### Core Capabilities
- **Multi-Platform Media Support**: Download videos and images from X (Twitter), RedGifs, Porn91, Videy, and more.
- **Bulk Processing & Queues**: Process multiple links concurrently with rate limiting and progress tracking.
- **Group Synchronization**: Automatically scrape and cache media from specified Telegram groups.
- **Auto-Scheduler**: Periodic scheduling for health checks and synchronizations. 
- **Videy CDN Upload**: Automatically upload downloaded videos to Videy CDN for easy sharing.
- **AI Chat Assistant**: Built-in AI chat functionality.

### Advanced Features
- **X/Twitter Media Scraping**: Download all media from a user's timeline (`/x_media`)
- **RedGifs Profile Downloads**: Download all gifs from a RedGifs user (`/redgifs_media`)
- **Twitter Following Scraper**: Scrape a user's following list (`/get_following`)
- **Media Cleanup**: Automatic disk space management (`/cleanup`)
- **Health Monitoring**: System health checks (`/health`)

## Prerequisites

- Python 3.10 or higher
- FFmpeg (for media processing and thumbnail generation)
- Telegram Bot Token
- Telegram API credentials (API_ID, API_HASH)
- *(Optional)* Ollama server for AI categorization

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/earhengleap/Telegram-Bot.git
cd Telegram-Bot
```

### 2. Create Virtual Environment

```bash
# Windows
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Linux/Mac
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment

Create a `.env` file referencing the needed parameters. Here's a quick startup setup:

```env
# Required Telegram Credentials
API_ID=your_api_id
API_HASH=your_api_hash
BOT_TOKEN=your_bot_token
CHAT_ID=your_chat_id

# Optional - AI features (Ollama)
TWA_AI_TITLES=1
TWA_AI_OLLAMA_URL=http://127.0.0.1:11434/api/generate
TWA_AI_MODEL=moondream:latest
```

### 5. Start the Bot

```bash
python afterdark.py
```

## Available Commands

| Command | Description |
|---------|-------------|
| `/start` | Start the bot |
| `/help` | Get help instructions |
| `/stats` | View download statistics |
| `/videy` | View your Videy CDN links |
| `/version` | Check bot version |
| `/health` | System health status |
| `/cleanup` | View & manage disk storage |
| `/chat` | Chat with the AI Assistant |
| `/get_following` | Scrape a Twitter user's following list |
| `/x_media` | Download media from an X username |
| `/redgifs_media` | Download all gifs from a RedGifs username |

## Project Structure

```
AfterDark/
├── afterdark.py            # Primary bot entrypoint
├── config/                 # Core settings, constants, and Path validations
├── core/                   # Service layer and internal systems
│   ├── downloader.py       # Core media download pipeline
│   ├── database.py         # SQLite persistence operations
│   ├── auto_scheduler.py   # Background job management
│   ├── health_monitor.py   # Health checks
│   ├── media_cleaner.py    # Disk space management
│   └── *_service.py        # Independent downloaders (Twitter, Redgifs, etc.)
├── data/                   # PIDs, state files
├── handlers/               # Command and Callback pyrogram callbacks
├── media/                  # Shared thumbnail definitions
├── models/                 # Data Enums and typing 
├── resources/              # External copy & keyboards structures
├── scripts/                # External tools and manual execution scripts
├── tests/                  # Unit test framework
└── ui/                     # Shared UI/Keyboards elements
```

## Support

For issues, configurations, and feature requests, please [open an issue](https://github.com/earhengleap/Telegram-Bot/issues) on GitHub.

---

<p align="center">
  Made with ❤️ by <a href="https://github.com/earhengleap">earhengleap</a>
</p>