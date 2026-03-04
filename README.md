# AfterDark - Telegram Bot

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue.svg" alt="Python Version">
  <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License">
  <img src="https://img.shields.io/badge/Telegram-Bot_API-v20-orange.svg" alt="Telegram API">
</p>

A robust and feature-rich Telegram bot platform designed originally for downloading media from X (Twitter), expanded into a comprehensive media management system. Features include bulk downloads, AI-powered media categorization, advanced tunnel setups, and a beautiful locally-hosted Telegram Mini App (TWA) gallery dashboard for browsing your synced media.

![AfterDark Vault](https://img.shields.io/badge/AfterDark_Vault-TWA_Dashboard-blueviolet)

## Features

### Core Capabilities
- **Multi-Platform Media Support**: Download videos and images from X (Twitter), RedGifs, Porn91, Videy, and more.
- **Bulk Processing & Queues**: Process multiple links concurrently with rate limiting and progress tracking.
- **Group Synchronization**: Automatically scrape and cache media from specified Telegram groups.
- **Auto-Scheduler**: Periodic scheduling for health checks and synchronizations. 

### Telegram Mini App (TWA) Dashboard
- **Web-based Gallery**: A responsive Mini App Dashboard deployed directly through the bot for intuitive media browsing.
- **Filtering & AI Search**: Filter media explicitly by type (video/image), and search collections using an AI-generated title and description base.
- **Background Sync**: Live-syncs new media dropped in your configured groups directly into the dashboard.
- **Secure Authentication Options**: Selectable session handling between bot auth or explicit user auth for greater history retention.

### Tunnels and Connectivity
Built-in advanced tunnel proxies (`Serveo`, `Localhost.run`, `Pinggy`, `Localtunnel`, and Cloudflare options) allow you to serve the TWA locally while securely exposing it to Telegram, managed directly through the bot runner (`afterdark.py`).

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

# Mini App Tunnel and Hosting 
TWA_PORT=5000
TWA_MENU_SYNC_AUTOSTART=1
TWA_GALLERY_AUTH=auto

# Optional - Tunnel Providers (serveo, localhost.run, pinggy)
TWA_TUNNEL_PROVIDER=serveo

# Optional - AI features (Ollama)
TWA_AI_TITLES=1
TWA_AI_OLLAMA_URL=http://127.0.0.1:11434/api/generate
TWA_AI_MODEL=moondream:latest
```

### 5. Start the Bot & Mini App Server

Running the primary bot startup will invoke both the Telegram MTProto client and the background dashboard web server, initializing your configured tunnels automatically.

```bash
python afterdark.py
```

*For manual control over the Mini App server independently:*
```bash
python dashboard/server.py
```
*To test tunnels directly via the dashboard backend:*
```bash
python dashboard/scripts/start_with_tunnel.py
```

## Project Structure

```
AfterDark/
├── afterdark.py            # Primary bot entrypoint & multi-process bootstrapper
├── config/                 # Core settings, constants, and Path validations
├── core/                   # Service layer and internal systems
│   ├── downloader.py       # Core media download pipeline
│   ├── database.py         # SQLite persistence operations
│   ├── auto_scheduler.py   # Background job management
│   ├── health_monitor.py   # TWA Server & Tunnel health checks
│   └── *_service.py        # Independent downloaders (Twitter, Redgifs, etc.)
├── dashboard/              # TWA Backend and Web components (Replaced 'telegram-bot-websites')
│   ├── server.py           # FastAPI Web Server for Mini App
│   ├── scripts/            # Build pipelines, index rebuilders, auth login
│   ├── public/             # CSS/JS frontend components
│   └── media_cache/        # Target disk for downloaded files
├── data/                   # PIDs, state files, tunnel URLs
├── handlers/               # Command and Callback pyrogram callbacks
├── media/                  # Shared thumbnail definitions
├── models/                 # Data Enums and typing 
├── resources/              # External copy & keyboards structures
├── scripts/                # External tools and manual execution scripts
├── tests/                  # Unit test framework
└── ui/                     # Shared UI/Keyboards elements
```

## API Highlights (Dashboard)

The `dashboard/server.py` runs a FastAPI service exposing routes to your Mini App.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Validates server routing & tunnel stability |
| `/api/media` | GET | Generates the active media list for the TWA |
| `/api/sync` | POST | Triggers forced history alignment from the Chat |
| `/api/ai-titles`| POST | Manually invokes Ollama for pending items |
| `/api/file/{id}`| GET | Serves media proxy from Local System/CDN |

## Support

For issues, configurations, and feature requests, please [open an issue](https://github.com/earhengleap/Telegram-Bot/issues) on GitHub.

---

<p align="center">
  Made with ❤️ by <a href="https://github.com/earhengleap">earhengleap</a>
</p>
