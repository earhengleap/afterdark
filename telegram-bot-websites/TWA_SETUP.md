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

## 3) Expose HTTPS with any tunnel/reverse proxy
```powershell
# Example only: expose local port 5000 with your preferred provider
# and copy the resulting HTTPS URL.
```
Copy the `https://...` URL from your provider.

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
