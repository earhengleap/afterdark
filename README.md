# X Video Downloader Pro - Telegram Bot

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue.svg" alt="Python Version">
  <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License">
  <img src="https://img.shields.io/badge/Telegram-Bot_API-v20-orange.svg" alt="Telegram API">
</p>

A powerful Telegram bot for downloading and managing media from X (Twitter). Features include bulk downloads, AI-powered media categorization, and a beautiful Telegram Mini App (TWA) gallery for browsing your media collection.

![AfterDark Vault](https://img.shields.io/badge/AfterDark_Vault-TWA_Gallery-blueviolet)

## Features

### Core Functionality
- **Media Downloads**: Download videos and images from X (Twitter) links
- **Bulk Processing**: Process multiple URLs simultaneously with queue management
- **Telegram Group Sync**: Automatically sync media from configured Telegram groups
- **AI-Powered Organization**: Auto-generate titles and descriptions using local AI (Ollama)

### Telegram Mini App (TWA) Gallery
- **Web-based Gallery**: Beautiful responsive gallery interface accessible via Telegram
- **Filter & Search**: Filter by media type (video/image), search by AI titles
- **Media Viewer**: Full-screen viewer with video playback support
- **Auto-Sync**: Background synchronization of new media from Telegram
- **AI Enhancement**: Generate intelligent titles and descriptions for your media

### Technical Features
- **Pyrogram Client**: Modern Telegram client with full API support
- **FastAPI Backend**: High-performance API for the Mini App
- **SQLite Persistence**: Local database for user settings and download history
- **Async Processing**: Non-blocking operations for optimal performance
- **CDN Mode**: Stream media directly from Telegram CDN for faster loading

## Prerequisites

- Python 3.10 or higher
- Telegram API credentials (API_ID, API_HASH)
- Telegram Bot Token
- (Optional) Ollama server for AI features

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

Create a `.env` file or set environment variables:

```env
# Required
API_ID=your_api_id
API_HASH=your_api_hash
BOT_TOKEN=your_bot_token
CHAT_ID=your_chat_id

# Optional - For AI features
TWITTER_COOKIES=your_twitter_cookies
TELEGRAM_GALLERY_AUTH=user
TWA_AI_TITLES=1

# Optional - Ollama settings
TWA_AI_OLLAMA_URL=http://127.0.0.1:11434/api/generate
TWA_AI_MODEL=moondream:latest
```

### 5. Run the Bot

```bash
python afterdark.py
```

## Telegram Mini App Setup

### Running the TWA Server

```bash
# Basic usage
python telegram-bot-websites/server.py

# With custom port
TWA_PORT=5000 python telegram-bot-websites/server.py

# With ngrok tunnel for testing
python telegram-bot-websites/start_with_tunnel.py
```

### Configuration Options

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `TWA_PORT` | 5000 | Server port |
| `TELEGRAM_GALLERY_AUTH` | auto | Auth mode: auto, bot, or user |
| `TWA_CDN_ONLY` | 1 | Use Telegram CDN for streaming |
| `TWA_LIVE_SYNC` | 1 | Enable background sync |
| `TWA_AI_TITLES` | 1 | Enable AI title generation |
| `TWA_STARTUP_SYNC_LIMIT` | all | Media to sync on startup |

## Project Structure

```
Telegram-Bot/
├── afterdark.py            # Main bot entrypoint
├── config/
│   ├── settings.py         # Configuration management
│   └── config_loader.py    # Config loading utilities
├── core/
│   ├── downloader.py       # Media download pipeline
│   ├── database.py          # SQLite persistence
│   └── logger.py           # Logging utilities
├── handlers/
│   ├── command_handlers.py # Bot commands
│   └── callback_handlers.py # Callback queries
├── telegram-bot-websites/
│   ├── server.py           # TWA API server
│   ├── script.js           # Frontend JavaScript
│   ├── style.css           # Frontend styles
│   ├── index.html          # TWA HTML entry
│   └── media_cache/        # Downloaded media storage
├── ui/
│   └── keyboards.py        # Telegram keyboards
├── utils/                  # Utility functions
├── models/                 # Data models
└── tests/                  # Unit tests
```

## Usage

### Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Start the bot |
| `/help` | Show help message |
| `/sync` | Sync media from Telegram group |
| `/status` | Show bot status |

### TWA Gallery

1. Open your bot in Telegram
2. Click the menu button (three lines)
3. Select "Gallery" or use the inline button
4. Browse, search, and view your media collection

## API Endpoints

### Mini App API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Server health check |
| `/api/media` | GET | Get all media items |
| `/api/media/page` | GET | Paginated media list |
| `/api/media/recent` | GET | Recent media items |
| `/api/sync` | POST | Trigger media sync |
| `/api/ai-titles` | POST | Generate AI titles |
| `/api/file/{id}` | GET | Get media file |

## Development

### Running Tests

```bash
# Run all tests
python -m unittest discover -s tests

# Run specific test
python -m unittest tests.test_image_downloader_rename
```

### Code Quality

```bash
# Install linters
pip install ruff mypy

# Run ruff
ruff check .

# Run mypy
mypy .
```

## Tech Stack

- **Bot Framework**: [Pyrogram](https://docs.pyrogram.org/) / [pyrofork](https://pyrofork.mahdul.com/)
- **Web Framework**: [FastAPI](https://fastapi.tiangolo.com/)
- **Database**: SQLite
- **AI**: [Ollama](https://ollama.ai/) (local LLMs)
- **Media Processing**: FFmpeg, PIL

## License

MIT License - See [LICENSE](LICENSE) for details.

## Acknowledgments

- [Pyrogram](https://github.com/pyrogram/pyrogram) - Telegram client
- [gallery-dl](https://github.com/mikf/gallery-dl) - Media downloading
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) - Video downloading

## Support

For issues and feature requests, please [open an issue](https://github.com/earhengleap/Telegram-Bot/issues) on GitHub.

---

<p align="center">
  Made with ❤️ by <a href="https://github.com/earhengleap">earhengleap</a>
</p>
