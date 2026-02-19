@echo off
REM Start TWA Gallery with stable serveo tunnel
REM 
REM Usage: start_stable_tunnel.bat [subdomain]
REM Example: start_stable_tunnel.bat mygallery
REM
REM This will create a stable URL like: https://mygallery.serveo.net
REM The subdomain will remain the same across restarts

SETlocal

REM Set your custom subdomain here or pass as argument
if "%~1"=="" (
    set SUBDOMAIN=afterdark
) else (
    set SUBDOMAIN=%~1
)

echo Starting TWA Gallery with stable tunnel...
echo Subdomain: %SUBDOMAIN%
echo Public URL will be: https://%SUBDOMAIN%.serveo.net
echo.

cd /d "%~dp0"

REM Set environment variables for stable tunnel
set TWA_SERVEO_SUBDOMAIN=%SUBDOMAIN%
set TWA_SERVEO_AUTOSTART=1
set TWA_SERVEO_URL_TIMEOUT=60
set TWA_SERVEO_CONNECT_TIMEOUT=15
set TWA_LOCALHOSTRUN_AUTOSTART=0
set TWA_TUNNEL_PROVIDER=serveo

REM Start the server
python server.py

endlocal
