@echo off
REM ============================================================
REM AfterDark bot launcher
REM Double-click this file (or its Desktop shortcut) to start
REM the Telegram bot. The console window stays open after exit
REM so you can read any error messages before it closes.
REM ============================================================

title AfterDark Bot
cd /d "%~dp0"

echo Starting AfterDark bot...
echo (Press Ctrl+C to stop)
echo.

python afterdark.py

echo.
echo ============================================================
echo Bot has exited. Press any key to close this window.
echo ============================================================
pause >nul
