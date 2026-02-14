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

# Force localhost.run over SSH
$env:TWA_TUNNEL_PROVIDER='localhostrun'

# Disable tunnel autostart (local-only)
$env:TWA_TUNNEL_PROVIDER='none'
```
