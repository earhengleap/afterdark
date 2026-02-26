# Telegram Mini App Setup (TWA)

## Why `/api/media` failed
If you see `BOT_METHOD_INVALID`, Telegram bot sessions cannot call history methods (`messages.GetHistory`).
For full gallery history, use a **user session**.

## 1) Create user session once (required)
```powershell
python telegram-bot-websites/login_user_session.py
```
Complete login prompts (phone/code/2FA if requested).

## 2) Run server in user-session mode
```powershell
$env:TELEGRAM_GALLERY_AUTH='user'
python telegram-bot-websites/server.py
```

## 3) Expose HTTPS with free Serveo tunnel (recommended)
```powershell
# OpenSSH client is included on most Windows installs.
# Start free HTTPS tunnel to local port 5000:
ssh -o StrictHostKeyChecking=accept-new -R 80:127.0.0.1:5000 serveo.net
```
Copy the `https://....serveousercontent.com` URL.

Fallback option:
```powershell
ssh -o StrictHostKeyChecking=accept-new -R 80:127.0.0.1:5000 nokey@localhost.run
```

## 4) Set bot menu button to Mini App URL
```powershell
python telegram-bot-websites/configure_twa.py --url https://YOUR-PUBLIC-URL
```

Now opening your bot menu button in Telegram launches this Mini App.

## Security note
`server.py` validates Telegram `initData` when provided.
- Default mode: accepts browser/dev mode too.
- Strict mode: set env var `TWA_VERIFY_STRICT=1` to reject invalid/non-Telegram sessions.

Example:
```powershell
$env:TWA_VERIFY_STRICT='1'; python telegram-bot-websites/server.py
```

## Optional orchestrator tunnel settings (`x_telegram.py`)
```powershell
# Auto-select provider
$env:TWA_TUNNEL_PROVIDER='auto'

# Force serveo tunnel
$env:TWA_TUNNEL_PROVIDER='serveo'
$env:TWA_SERVEO_SSH_PORTS='22,443'   # try 22 first, then 443
$env:TWA_SERVEO_URL_TIMEOUT='45'
$env:TWA_SERVEO_CONNECT_TIMEOUT='8'

# Force localhost.run over SSH
$env:TWA_TUNNEL_PROVIDER='localhostrun'
$env:TWA_LOCALHOSTRUN_URL_TIMEOUT='120'

# Disable tunnel autostart (local-only)
$env:TWA_TUNNEL_PROVIDER='none'
```

## Optional AI Titles (free, local)
Mini App can auto-generate short titles for images/videos using local Ollama vision model.

### 1) Install Ollama and pull vision model
```powershell
# Default (lightweight + reliable)
ollama pull moondream:latest

# Optional vision fallback (can be very slow on CPU)
ollama pull qwen2.5vl:3b

# Optional (larger vision model; may crash on low-resource machines)
ollama pull llava:7b
```

### 2) Keep Ollama running
```powershell
ollama serve
```

### 3) Enable AI title generation
```powershell
$env:TWA_AI_TITLES='1'
$env:TWA_AI_TITLE_PROVIDER='ollama'
$env:TWA_AI_MODEL='moondream:latest'
$env:TWA_AI_FALLBACK_MODELS='qwen2.5vl:3b'   # optional

# Title style: "explicit" (default) or "tasteful"
$env:TWA_AI_TITLE_STYLE='explicit'

# Optional: use a fast text model to polish titles (porn-style phrasing)
$env:TWA_AI_TEXT_MODEL='gemma3:4b'
$env:TWA_AI_POLISH_TITLES='1'
```

More explicit/uncensored wording (local, via Ollama):
```powershell
# Optional: Dolphin (text-only) as the title polisher.
# Pick the exact Dolphin tag you want from the Ollama library, then pull it:
#   ollama pull <dolphin-model-tag>
# Confirm it exists locally:
#   ollama list

# Use Dolphin for title polishing; fall back to gemma3 if Dolphin is missing/unavailable.
$env:TWA_AI_TEXT_MODEL='<dolphin-model-tag>'
$env:TWA_AI_TEXT_FALLBACK_MODELS='gemma3:4b'
```

Safety guardrails (built-in): titles will not include age/teen/school terms or sensitive attributes.

### 4) Optional tuning
```powershell
# model response timeout (seconds). Keep high on CPU-only machines.
$env:TWA_AI_TIMEOUT_SECONDS='240'

# seconds between AI title worker cycles
$env:TWA_AI_POLL_SECONDS='12'

# titles generated per cycle
$env:TWA_AI_BATCH_SIZE='3'

# scan window for missing titles:
# - 0 = scan full cached index (backfill older media)
# - N = only scan newest N items
$env:TWA_AI_RECENT_SCAN_LIMIT='0'

# re-title behavior:
# - missing   (default): only generate when ai_title is empty
# - fallback  : retry items that have fallback titles
# - style     : retry when ai_title_style differs from current TWA_AI_TITLE_STYLE (plus fallback)
# - force     : overwrite titles (within recent scan limit)
$env:TWA_AI_RETITLE_MODE='missing'
```

### 5) Manual trigger (optional)
```powershell
# Generate titles now for newest media (without waiting for next worker cycle)
Invoke-WebRequest -UseBasicParsing -Method Post "http://127.0.0.1:5000/api/ai-titles?batch_size=3&recent_limit=240&mode=style"
```

One-time improvement pass (re-title older titles into the current style):
```powershell
# This runs in batches; repeat until you're satisfied.
Invoke-WebRequest -UseBasicParsing -Method Post "http://127.0.0.1:5000/api/ai-titles?batch_size=10&recent_limit=0&mode=style"
```
