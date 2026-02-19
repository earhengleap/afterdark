# Quick Start Guide - AI Title Generation

## ✅ System Status

**All fixes applied and verified!**

- ✓ Critical bug fixed in `server.py`
- ✓ Logging added for debugging
- ✓ Ollama running with all models
- ✓ All tests passed (4/4)

---

## 🚀 Start Using Now

### 1. Restart Server

```bash
cd d:\BOT\Telegram-Bot
python telegram-bot-websites\server.py
```

**Look for**: `AI title worker active`

### 2. Test It

1. Post new video/image to Telegram group
2. Wait 10-20 seconds
3. Check website for AI title

### 3. Monitor Logs

Watch for:
```
✓ AI title generated for video message_id=12345: [title]
AI title batch complete: X titles generated
```

---

## 🔧 If Issues Occur

**No titles appearing?**
```bash
# Test Ollama
python test_ollama.py

# Restart server
# Ctrl+C to stop, then restart
```

**Check logs for**:
- "AI title worker active" ← Should see this
- "AI title generation: X candidates" ← Processing
- "✓ AI title generated" ← Success!

---

## 📱 Website Features

- AI titles on all media cards
- Search works on AI titles
- "AI Enhanced" sort option
- Full descriptions in viewer

---

**That's it!** The system is ready. Just restart the server and it will work automatically.
