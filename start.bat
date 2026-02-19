@echo off
echo Starting AfterDark Vault...
echo.

echo Starting Python backend + Next.js frontend...
start "Telegram Bot" cmd /k "python x_telegram.py"
timeout /t 3 /nobreak >nul
start "Next.js" cmd /k "cd web && npm run dev"

echo.
echo Done! Open http://localhost:5000 in your browser
pause
