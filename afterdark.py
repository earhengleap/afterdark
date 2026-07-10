# afterdark.py

"""
X Video Downloader Bot - Clean Architecture Implementation
Version: 1.0.1
"""

import os
import time
import sys
import signal
import asyncio
import logging
import subprocess
import shutil
import atexit
import json
import urllib.request
import urllib.parse
import socket
import re
from datetime import datetime
from pathlib import Path

from pyrogram import Client, idle
from pyrogram.types import BotCommand
from pyrogram.errors import ApiIdInvalid, AuthKeyInvalid, FloodWait

# Configuration imports
from config.settings import BOT_TOKEN, API_ID, API_HASH, BOT_VERSION, BOT_NAME, VERSION_DATE, CHAT_ID
from config.paths import setup_directories

# Core functionality imports
from core.logger import setup_logger
from core.metrics import metrics, get_metrics
from core.config_validator import validate_configuration
from core.health_monitor import start_health_monitor, get_health_monitor
from core.database import history_db

# Handler imports
from handlers.command_handlers import setup_command_handlers
from handlers.callback_handlers import setup_callback_handlers
from handlers.media_sync_handler import setup_media_sync_handlers, handle_group_media

# Initialize Logger
logger = setup_logger()

# ==================== SINGLE INSTANCE LOCK ====================
import socket
import sys
import platform

def _get_running_pid() -> int:
    """Get current process PID"""
    return os.getpid()

def _is_process_running(pid: int) -> bool:
    """Check if a process with given PID is running"""
    if os.name == 'nt':
        try:
            import subprocess
            result = subprocess.run(
                ['tasklist', '/FI', f'PID eq {pid}'],
                capture_output=True,
                text=True,
                timeout=5
            )
            return str(pid) in result.stdout
        except:
            return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

def _check_single_instance() -> bool:
    """Ensure only one instance of the bot runs at a time"""
    pid_file = os.path.join(os.getcwd(), "data", "afterdark.pid")
    os.makedirs(os.path.dirname(pid_file), exist_ok=True)
    
    current_pid = _get_running_pid()
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    system_info = platform.system()
    
    # Check for existing PID
    existing_pid = None
    if os.path.exists(pid_file):
        try:
            with open(pid_file, 'r') as f:
                existing_pid = int(f.read().strip())
        except:
            existing_pid = None
    
    # Check if existing process is still running
    if existing_pid and existing_pid != current_pid:
        if _is_process_running(existing_pid):
            logger.error("=" * 60)
            logger.error("  [MULTIPLE INSTANCE DETECTED]")
            logger.error("=" * 60)
            logger.error(f"  Current PID:    {current_pid}")
            logger.error(f"  Running PID:    {existing_pid}")
            logger.error(f"  System:         {system_info}")
            logger.error(f"  Time:            {current_time}")
            logger.info("-" * 60)
            logger.error("  Another instance of AfterDark is already running!")
            logger.error("  Please stop the existing instance first:")
            logger.error(f"     Windows: Taskkill //PID {existing_pid} //F")
            logger.error(f"     Linux:   kill -9 {existing_pid}")
            logger.error("=" * 60)
            return False
        else:
            logger.warning(f"Stale PID file found (PID: {existing_pid}), cleaning up...")
            try:
                os.remove(pid_file)
            except:
                pass
    
    # Acquire lock by writing current PID
    lock_file = os.path.join(os.getcwd(), "data", "afterdark.lock")
    try:
        with open(pid_file, 'w') as f:
            f.write(str(current_pid))
        with open(lock_file, 'w') as f:
            f.write(str(current_pid))
        
        return True
        
    except Exception as e:
        logger.critical("=" * 60)
        logger.critical("  [FAILED TO ACQUIRE LOCK]")
        logger.critical("=" * 60)
        logger.critical(f"  Error: {e}")
        logger.critical("  Please check file permissions")
        logger.critical("=" * 60)
        return False


# ==================== TWA BOOTSTRAP ====================

_aux_processes = []


def _resolve_notify_usernames() -> list[str]:
    """
    Resolve the list of Telegram usernames to notify.
    Reads from the config/config.py (NOTIFY_USERNAMES).
    """
    from config.settings import config_instance
    raw = config_instance.notify_usernames.strip()
    if raw:
        names = [n.strip() for n in raw.split(",") if n.strip()]
        if names:
            return names
    # Default: original hardcoded values as a safe fallback
    return ["@HengleapEar", "@arekushisu_2001"]


_NOTIFY_USERNAMES: list[str] = _resolve_notify_usernames()





def _is_true(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _resolve_executable(preferred_env: str, candidates: list[str]) -> str | None:
    preferred = os.getenv(preferred_env, "").strip()
    if preferred:
        return preferred

    for candidate in candidates:
        found = shutil.which(candidate)
        if found:
            return found
    return None








def _is_port_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1.0)
        return sock.connect_ex((host, port)) == 0


def _is_twa_http_healthy(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=4) as response:
            if response.status != 200:
                return False
            payload = json.loads(response.read().decode("utf-8"))
        return bool(payload.get("ok"))
    except Exception:
        return False


def _supports_ai_title_api(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/media/recent?limit=1", timeout=6) as response:
            if response.status != 200:
                return False
            payload = json.loads(response.read().decode("utf-8"))
        return isinstance(payload, dict) and "ai_titled_count" in payload
    except Exception:
        return False


def _find_available_port(start_port: int, max_candidates: int = 20) -> int:
    for candidate in range(start_port, start_port + max_candidates):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", candidate))
                return candidate
            except OSError:
                continue
    return start_port


def _telegram_api_post(method: str, payload: dict[str, str]) -> dict:
    data = urllib.parse.urlencode(payload).encode("utf-8")
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{BOT_TOKEN}/{method}",
        data=data,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        body = response.read().decode("utf-8")
    parsed = json.loads(body)
    if not parsed.get("ok"):
        raise RuntimeError(f"Telegram API {method} failed: {parsed}")
    return parsed


def _resolve_menu_chat_ids(root_dir: Path) -> list[str]:
    max_ids_raw = os.getenv("TWA_MENU_MAX_CHATS", "25").strip()
    try:
        max_ids = max(0, int(max_ids_raw))
    except ValueError:
        max_ids = 25

    result: list[str] = []
    seen: set[str] = set()

    raw_ids = os.getenv("TWA_MENU_CHAT_IDS", "")
    for item in raw_ids.split(","):
        candidate = item.strip()
        if candidate and candidate not in seen:
            seen.add(candidate)
            result.append(candidate)

    if max_ids and _is_true(os.getenv("TWA_MENU_USERS_AUTODETECT", "1")):
        users_dir = root_dir / "users"
        if users_dir.exists():
            for entry in sorted(users_dir.glob("*.json")):
                candidate = entry.stem.strip()
                if not candidate or not candidate.lstrip("-").isdigit():
                    continue
                if candidate in seen:
                    continue
                seen.add(candidate)
                result.append(candidate)
                if len(result) >= max_ids:
                    break

    return result[:max_ids] if max_ids else []



def _build_commands_menu_button_payload() -> dict[str, str]:
    return {"type": "commands"}


def _sync_menu_buttons(root_dir: Path, public_url: str) -> None:
    """Clear persistent Mini App menu buttons so /gallery is the primary launcher."""
    if not _is_true(os.getenv("TWA_MENU_SYNC_AUTOSTART", "1")):
        return

    menu_button = _build_commands_menu_button_payload()
    payload = {"menu_button": json.dumps(menu_button)}

    try:
        _telegram_api_post("setChatMenuButton", payload)
    except Exception as e:
        logger.warning(f"Failed to reset default Telegram menu button: {e}")

    chat_ids = _resolve_menu_chat_ids(root_dir)
    if not chat_ids:
        return

    updated = 0
    for chat_id in chat_ids:
        try:
            _telegram_api_post(
                "setChatMenuButton",
                {
                    "chat_id": str(chat_id),
                    "menu_button": json.dumps(menu_button),
                },
            )
            updated += 1
        except Exception as e:
            logger.warning(f"Failed to reset Telegram menu button for chat_id={chat_id}: {e}")

    logger.info(f"Telegram menu button reset to commands for {updated}/{len(chat_ids)} chat(s).")


def _persist_twa_public_url(root_dir: Path, public_url: str) -> None:
    normalized = public_url.rstrip("/") + "/"
    os.environ["TWA_PUBLIC_URL"] = normalized
    target = root_dir / "data" / "twa_public_url.txt"
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(normalized + "\n", encoding="utf-8")
    except Exception as e:
        logger.warning(f"Failed to persist TWA public URL to {target}: {e}")


def _read_persisted_twa_public_url(root_dir: Path) -> str | None:
    target = root_dir / "data" / "twa_public_url.txt"
    try:
        if target.exists():
            content = target.read_text(encoding="utf-8").strip()
            if content:
                return content.rstrip("/")
    except Exception:
        pass
    return None


def _is_public_url_healthy(public_url: str) -> bool:
    normalized = public_url.strip().rstrip("/")
    if not normalized.startswith("https://"):
        return False

    health_url = normalized + "/api/health"
    try:
        with urllib.request.urlopen(health_url, timeout=8) as response:
            if response.status != 200:
                return False
            payload = json.loads(response.read().decode("utf-8"))
        return bool(payload.get("ok"))
    except Exception:
        return False


def _check_health_url(health_url: str, timeout: int = 8) -> bool:
    try:
        with urllib.request.urlopen(health_url, timeout=timeout) as response:
            if response.status != 200:
                return False
            payload = json.loads(response.read().decode("utf-8"))
        return bool(payload.get("ok"))
    except Exception:
        return False


def _probe_tunnel_health(public_url: str, twa_port: int) -> bool:
    normalized = public_url.strip().rstrip("/")
    if not normalized.startswith("https://"):
        return False

    public_health_url = normalized + "/api/health"
    if _check_health_url(public_health_url, timeout=10):
        return True

    local_health_url = f"http://127.0.0.1:{twa_port}/api/health"
    return _check_health_url(local_health_url, timeout=3)


def _wait_for_public_url_health(public_url: str, timeout_seconds: int) -> bool:
    deadline = time.time() + max(1, timeout_seconds)
    consecutive_success = 0
    while time.time() < deadline:
        if _is_public_url_healthy(public_url):
            consecutive_success += 1
            # Require 3 consecutive successful checks to ensure proxy routing has stabilized 
            # across all of the tunnel provider's global edge nodes before telling the user.
            if consecutive_success >= 3:
                # Add an extra 4s buffer to prevent immediate 502 when the user clicks the link
                # (DNS/edge routes take a few seconds to fully propagate)
                time.sleep(4) 
                return True
        else:
            consecutive_success = 0
        time.sleep(2.0)
    return False





def _kill_port_process(port: int) -> bool:
    try:
        import subprocess, os, time
        killed_any = False
        if os.name == 'nt':
            output = subprocess.check_output(f"netstat -ano | findstr :{port}", shell=True, text=True)
            for line in output.strip().split('\n'):
                if f":{port} " in line and "LISTENING" in line:
                    parts = line.strip().split()
                    if len(parts) > 4:
                        pid = parts[-1]
                        if pid.isdigit() and int(pid) > 0:
                            logger.info(f"Force killing process {pid} occupying port {port}...")
                            subprocess.run(f"taskkill //PID {pid} //F", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                            killed_any = True
        else:
            output = subprocess.check_output(f"lsof -i:{port} -t", shell=True, text=True)
            for pid in output.strip().split('\n'):
                if pid.isdigit() and int(pid) > 0:
                    logger.info(f"Force killing process {pid} occupying port {port}...")
                    os.kill(int(pid), 9)
                    killed_any = True
        if killed_any:
            time.sleep(1)
        return killed_any
    except Exception as e:
        logger.debug(f"Failed to kill process on port {port}: {e}")
        return False


def _kill_port_process(port: int) -> None:
    """Find and kill any process listening on the specified port (Windows only)."""
    if os.name != 'nt':
        return
    try:
        # Get netstat output for the port
        cmd = f'netstat -ano | findstr :{port}'
        output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode()
        
        pids_killed = set()
        for line in output.splitlines():
            if 'LISTENING' in line:
                parts = line.strip().split()
                if len(parts) >= 5:
                    pid = parts[-1]
                    if pid not in pids_killed and pid != '0':
                        logger.info(f"Cleaning up existing process on port {port} (PID: {pid})...")
                        subprocess.run(['taskkill', '/F', '/T', '/PID', pid], capture_output=True, check=False)
                        pids_killed.add(pid)
    except Exception:
        # Port is likely free or netstat found nothing
        pass

def _start_twa_stack() -> None:
    """Start the TWA FastAPI dashboard server. Localhost only — no tunnels."""
    if not _is_true(os.getenv("TWA_AUTOSTART", "1")):
        return

    root_dir = Path(__file__).resolve().parent
    server_script = root_dir / "dashboard/server.py"
    if not server_script.exists():
        logger.warning("TWA server script not found, skipping Mini App bootstrap")
        return

    twa_port = os.getenv("TWA_PORT", "5000").strip() or "5000"
    try:
        twa_port_int = int(twa_port)
    except ValueError:
        logger.warning(f"Invalid TWA_PORT='{twa_port}', fallback to 5000")
        twa_port = "5000"
        twa_port_int = 5000

    # If the port is already occupied, force-kill the old process and try again
    if _is_port_open("127.0.0.1", twa_port_int):
        logger.info(f"Port {twa_port} occupied — force-killing old process...")
        _kill_port_process(twa_port_int)
        if _is_port_open("127.0.0.1", twa_port_int):
            logger.warning(f"Could not free port {twa_port}. TWA may not start correctly.")

    os.environ["TWA_PORT"] = twa_port
    server_env = os.environ.copy()
    server_env.setdefault("TELEGRAM_GALLERY_AUTH", "auto")
    server_env["TWA_PORT"] = twa_port
    if not server_env.get("TWA_AI_TEXT_MODEL", "").strip():
        server_env["TWA_AI_TEXT_MODEL"] = "dolphin-llama3:8b"
    if not server_env.get("TWA_AI_TEXT_FALLBACK_MODELS", "").strip():
        server_env["TWA_AI_TEXT_FALLBACK_MODELS"] = "gemma3:4b"

    logs_dir = root_dir / "logs"
    logs_dir.mkdir(exist_ok=True)
    dashboard_log_path = logs_dir / "dashboard_server.log"
    # Keep file handle open for the lifetime of the subprocess
    _dashboard_log_fh = open(dashboard_log_path, "a", encoding="utf-8")
    _aux_processes.append(_dashboard_log_fh)  # store so it isn't GC'd

    server_proc = subprocess.Popen(
        [sys.executable, str(server_script)],
        cwd=str(root_dir),
        env=server_env,
        stdout=_dashboard_log_fh,
        stderr=_dashboard_log_fh,
    )

    _aux_processes.append(server_proc)

    # Actively poll until the backend is ready (up to 20 seconds)
    logger.info(f"Waiting for dashboard server to bind on port {twa_port}...")
    deadline = time.time() + 20
    backend_ready = False
    while time.time() < deadline:
        if server_proc.poll() is not None:
            logger.warning(
                f"TWA backend exited early (exit code {server_proc.returncode}). "
                f"Check logs/dashboard_server.log for details."
            )
            return
        if _is_port_open("127.0.0.1", twa_port_int):
            backend_ready = True
            break
    if not backend_ready:
        logger.warning(
            f"Dashboard server did not bind on port {twa_port} within 20 seconds. "
            f"Check logs/dashboard_server.log for errors."
        )
        return

    logger.info(f"TWA dashboard ready on http://localhost:{twa_port}")
    _start_frontend_dev()
    _start_auto_tunnel()


def _start_frontend_dev() -> None:
    """Start the Vite frontend development server if the folder exists."""
    root_dir = Path(__file__).resolve().parent
    frontend_dir = root_dir / "dashboard/frontend"
    
    if not frontend_dir.exists():
        return

    logger.info("Starting frontend development server (Vite) on http://localhost:3000...")
    
    vite_log_path = root_dir / "logs" / "vite.log"
    npm_cmd = "npm.cmd" if os.name == "nt" else "npm"
    _vite_log_fh = open(vite_log_path, "a", encoding="utf-8")
    _aux_processes.append(_vite_log_fh)

    frontend_proc = subprocess.Popen(
        [npm_cmd, "run", "dev"],
        cwd=str(frontend_dir),
        stdout=_vite_log_fh,
        stderr=_vite_log_fh,
    )
    _aux_processes.append(frontend_proc)
    logger.info("Frontend dev server started — output: logs/vite.log")


def _find_cloudflared() -> str | None:
    # Check common Windows install paths
    candidates = [
        r"C:\Program Files (x86)\cloudflared\cloudflared.exe",
        r"C:\Program Files\cloudflared\cloudflared.exe",
        "cloudflared",
    ]
    for c in candidates:
        found = shutil.which(c) or (c if os.path.exists(c) else None)
        if found:
            return found
    return None


def _choose_tunnel_provider(cloudflared_exe: str | None, configured: str) -> str:
    return "cloudflared"


def _read_tunnel_url_from_log(log_paths, timeout: int = 30) -> str | None:
    """Parse the HTTPS tunnel URL from one or more log files (cloudflare or lhr.life)."""
    import time as _time
    if isinstance(log_paths, Path):
        log_paths = [log_paths]
    deadline = _time.time() + timeout
    # Match both Cloudflare and localhost.run URLs
    url_re = re.compile(r"https://[a-zA-Z0-9\-]+\.(trycloudflare\.com|lhr\.life)")
    while _time.time() < deadline:
        for log_path in log_paths:
            try:
                if log_path.exists():
                    text = log_path.read_text(encoding="utf-8", errors="ignore")
                    match = url_re.search(text)
                    if match:
                        return match.group(0)
            except Exception:
                pass
        _time.sleep(1)
    return None


def _empty_ssh_config_path(root_dir: Path) -> Path:
    target = root_dir / "data" / "empty_ssh_config"
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_text("", encoding="utf-8")
    return target


def _build_localhostrun_command(root_dir: Path, twa_port: int) -> list[str]:
    ssh_config_path = _empty_ssh_config_path(root_dir)
    return [
        "ssh",
        "-F", str(ssh_config_path),
        "-o", "StrictHostKeyChecking=no",
        "-o", "ServerAliveInterval=30",
        "-o", "ServerAliveCountMax=3",
        "-o", "IdentitiesOnly=yes",
        "-R", f"80:127.0.0.1:{twa_port}",
        "nokey@localhost.run",
    ]


def _build_cloudflared_command(cloudflared_exe: str, twa_port: int) -> list[str]:
    return [
        cloudflared_exe,
        "tunnel",
        "--url",
        f"http://127.0.0.1:{twa_port}",
    ]


def _start_auto_tunnel() -> None:
    """Start a Cloudflare Tunnel and keep it alive."""
    if not _is_true(os.getenv("TWA_TUNNEL_AUTOSTART", "1")):
        logger.info("TWA_TUNNEL_AUTOSTART=0 — skipping tunnel.")
        return

    explicit_url = os.getenv("TWA_PUBLIC_URL", "").strip()
    if explicit_url.startswith("https://"):
        logger.info(f"TWA_PUBLIC_URL set explicitly — skipping auto-tunnel: {explicit_url[:60]}")
        _persist_twa_public_url(Path(__file__).resolve().parent, explicit_url)
        return

    root_dir = Path(__file__).resolve().parent
    twa_port = int(os.getenv("TWA_PORT", "5000") or "5000")
    logs_dir = root_dir / "logs"
    logs_dir.mkdir(exist_ok=True)
    cloudflared_exe = _find_cloudflared()
    provider = _choose_tunnel_provider(cloudflared_exe, os.getenv("TWA_TUNNEL_PROVIDER", "auto"))
    if not cloudflared_exe:
        logger.warning("cloudflared not found. Auto-tunnel is disabled until cloudflared is installed or configured.")
        return

    def _launch_cloudflared(log_fh, err_fh):
        cmd = _build_cloudflared_command(cloudflared_exe, twa_port)
        return subprocess.Popen(cmd, stdout=log_fh, stderr=err_fh)

    def _tunnel_worker():
        import time as _time
        while True:
            logger.info("Starting cloudflared tunnel...")
            log_path = logs_dir / "tunnel.log"
            err_path = logs_dir / "tunnel_err.log"
            # Clear log so we find the fresh URL quickly
            for f in (log_path, err_path):
                try:
                    f.write_text("", encoding="utf-8")
                except Exception:
                    pass

            proc = None
            try:
                log_fh = open(log_path, "a", encoding="utf-8")
                err_fh = open(err_path, "a", encoding="utf-8")
                _aux_processes.extend([log_fh, err_fh])
                proc = _launch_cloudflared(log_fh, err_fh)
                _aux_processes.append(proc)
                log_paths = [log_path, err_path]
            except Exception as e:
                logger.warning(f"{provider} failed to launch: {e}. Retrying in 60s...")
                _time.sleep(60)
                continue

            public_url = _read_tunnel_url_from_log(log_paths, timeout=60)
            if public_url:
                logger.info(f"✅ Tunnel active: {public_url}")
                _persist_twa_public_url(root_dir, public_url)
                try:
                    _time.sleep(3)
                    _sync_menu_buttons(root_dir, public_url)
                    logger.info("✅ Telegram persistent menu button cleared; use /gallery for a fresh Mini App link")
                except Exception as e:
                    logger.warning(f"Menu button sync failed: {e}")
                fail_count = 0
                while proc.poll() is None:
                    _time.sleep(30)
                    healthy = _probe_tunnel_health(public_url, twa_port)
                        
                    if not healthy:
                        fail_count += 1
                        logger.warning(f"Tunnel health check failed ({fail_count}/3): {public_url}")
                        if fail_count >= 3:
                            logger.error(f"Tunnel {public_url} is dead! Force killing SSH process.")
                            try:
                                proc.terminate()
                                proc.kill()
                            except Exception:
                                pass
                            break
                    else:
                        fail_count = 0  # Reset on success
            else:
                logger.warning("Tunnel URL not detected within 60s — will retry when process exits.")

            try:
                proc.wait(timeout=5)
            except Exception:
                pass
            
            logger.warning("Tunnel disconnected — restarting in 5s...")
            _time.sleep(5)

    import threading
    t = threading.Thread(target=_tunnel_worker, daemon=True, name="tunnel-watchdog")
    t.start()
    logger.info(f"Tunnel watchdog started ({provider}).")


def _stop_aux_processes() -> None:
    """Forcefully stop all auxiliary processes and close log file handles."""
    for proc in reversed(_aux_processes):
        try:
            # File handles stored alongside processes — just close them
            if hasattr(proc, 'write') and hasattr(proc, 'close'):
                try:
                    proc.close()
                except Exception:
                    pass
                continue

            if proc and proc.poll() is None:
                if os.name == 'nt':
                    # On Windows, taskkill /T /F ensures the entire process tree (e.g. npm -> node) is killed
                    try:
                        subprocess.run(['taskkill', '/F', '/T', '/PID', str(proc.pid)], 
                                     capture_output=True, check=False)
                    except Exception:
                        proc.terminate()
                else:
                    proc.terminate()
                
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    try:
                        proc.wait(timeout=2)
                    except:
                        pass
        except Exception:
            try:
                if proc and hasattr(proc, 'kill'):
                    proc.kill()
            except Exception:
                pass

    
    # Clean up lock files
    try:
        pid_file = os.path.join(os.getcwd(), "data", "afterdark.pid")
        lock_file = os.path.join(os.getcwd(), "data", "afterdark.lock")
        if os.path.exists(pid_file):
            os.remove(pid_file)
        if os.path.exists(lock_file):
            os.remove(lock_file)
    except Exception:
        pass
    
    _aux_processes.clear()

# Register cleanup on any exit
atexit.register(_stop_aux_processes)


# ==================== PYROGRAM CLIENT ====================


def _build_bot_client() -> Client:
    # --- Smart Session Logic ---
    # Default to file-based sessions on local/Windows to prevent FloodWait during restarts.
    is_local = os.name == 'nt' or os.getenv("IS_LOCAL", "0") == "1"
    session_in_memory_default = "0" if is_local else "1"
    
    session_name = os.getenv("BOT_SESSION_NAME", "afterdark_bot").strip() or "afterdark_bot"
    session_in_memory = os.getenv("BOT_SESSION_IN_MEMORY", session_in_memory_default).strip().lower() in {"1", "true", "yes", "on"}
    session_workdir = os.getenv("BOT_SESSION_WORKDIR", "data").strip()
    
    if not os.path.exists(session_workdir):
        os.makedirs(session_workdir, exist_ok=True)

    client_kwargs = {
        "api_id": API_ID,
        "api_hash": API_HASH,
        "bot_token": BOT_TOKEN,
        "in_memory": session_in_memory,
        "workdir": session_workdir,
    }

    if session_in_memory:
        logger.info("Using in-memory bot session (BOT_SESSION_IN_MEMORY=1).")
    else:
        logger.info(f"Using file-based bot session '{session_name}' in '{session_workdir}/'.")

    return Client(session_name, **client_kwargs)


app = _build_bot_client()

# ==================== SHUTDOWN HANDLER ====================

async def shutdown(signal_name, loop):
    """Enhanced graceful shutdown handler with timeout and cleanup"""
    logger.info(f"Received signal {signal_name}: Initiating graceful shutdown...")
    
    # Set shutdown timeout
    shutdown_timeout = 30
    
    try:
        # Stop accepting new requests
        logger.info("Stopping bot client...")
        await asyncio.wait_for(app.stop(), timeout=10)
        logger.info("✓ Telegram client stopped successfully")
    except asyncio.TimeoutError:
        logger.error("â±ï¸ Timeout while stopping client - forcing shutdown")
    except Exception as e:
        logger.warning(f"âš ï¸ Error stopping client: {e}")
    
    # Cancel all running tasks gracefully
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    if tasks:
        logger.info(f"Cancelling {len(tasks)} pending tasks...")
        
        for task in tasks:
            task.cancel()
        
        # Wait for tasks to complete cancellation
        try:
            await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=10
            )
            logger.info("✓ All tasks cancelled successfully")
        except asyncio.TimeoutError:
            logger.warning("â±ï¸ Some tasks did not cancel in time")
    
    # Log final metrics
    logger.info("📊 Final metrics:")
    logger.info(f"\n{metrics.get_summary()}")
    
    logger.info("Goodbye! 👋")
    _stop_aux_processes()
    loop.stop()

def handle_exception(loop, context):
    msg = context.get("exception", context["message"])
    logger.error(f"Unhandled exception: {msg}")

# ==================== MAIN ENTRY POINT ====================

def print_banner():
    """Print a professional startup rectangle with runtime metadata."""
    import sys

    if (sys.stdout.encoding or "").lower() != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    width = 84
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    pid = os.getpid()
    system = platform.system()
    workdir = os.getcwd()

    def _line(text: str) -> str:
        return f"| {text:<{width - 4}} |"

    try:
        top = "+" + ("=" * (width - 2)) + "+"
        sep = "|" + ("-" * (width - 2)) + "|"
        print(f"\n\033[1;36m{top}\033[0m")
        print(f"\033[1;36m{_line('AfterDark'.center(width - 4))}\033[0m")
        print(f"\033[1;36m{_line('Production Ready - Stable Build'.center(width - 4))}\033[0m")
        print(f"\033[1;36m{sep}\033[0m")
        print(f"\033[1;37m{_line(f'Bot Name : {BOT_NAME}')}\033[0m")
        print(f"\033[1;37m{_line(f'Version  : {BOT_VERSION}')}\033[0m")
        print(f"\033[1;37m{_line(f'Release  : {VERSION_DATE}')}\033[0m")
        print(f"\033[1;37m{_line(f'PID      : {pid}')}\033[0m")
        print(f"\033[1;37m{_line(f'System   : {system}')}\033[0m")
        print(f"\033[1;37m{_line(f'Started  : {now}')}\033[0m")
        print(f"\033[1;37m{_line(f'Workdir  : {workdir}')}\033[0m")
        print(f"\033[1;36m{top}\033[0m")
    except UnicodeEncodeError:
        print("\n+===============================+")
        print("|           AfterDark          |")
        print("|-------------------------------|")
        print(f"| Version : {BOT_VERSION:<20} |")
        print(f"| Started : {now:<20} |")
        print("+===============================+\n")

async def sync_group_history(client: Client):
    """
    Skipped: Delegate history sync to the website dashboard (User Session).
    The bot only handles real-time link processing to avoid method restrictions.
    """
    logger.info("ℹ️ History sync delegated to website (User Session).")


async def main():
    """Main bot entry point with enhanced error handling and monitoring"""
    print_banner()
    if not _check_single_instance():
        return

    # Step 1: Validate configuration
    logger.info("Validating configuration...")
    try:
        validate_configuration(raise_on_error=True)
        logger.info("✓ Configuration validated successfully")
    except ValueError as e:
        logger.critical(f"Configuration validation failed: {e}")
        return
    
    # Step 2: Setup directories
    logger.info("Initializing system directories...")
    setup_directories()
    logger.info("✓ Directories initialized")
    
    # Step 3: Setup handlers
    logger.info("Setting up command and callback handlers...")
    setup_command_handlers(app)
    setup_callback_handlers(app)
    setup_media_sync_handlers(app)
    logger.info("✓ Handlers configured")

    # Step 3.5: Start Mini App dashboard (localhost only)
    try:
        _start_twa_stack()
    except Exception as e:
        logger.warning(f"TWA bootstrap failed, continuing bot-only mode: {e}")

    
    # Step 4: Start bot with retry logic
    logger.info("Connecting to Telegram API...")
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            await app.start()
            me = await app.get_me()
            
            # Set bot commands for autocomplete
            await app.set_bot_commands([
                BotCommand("start", "Start the bot"),
                BotCommand("help", "Get help instructions"),
                BotCommand("stats", "View download statistics"),
                BotCommand("videy", "View your Videy CDN links"),
                BotCommand("version", "Check bot version"),
                BotCommand("health", "System health status"),
                BotCommand("cleanup", "View & manage disk storage"),
                BotCommand("chat", "Chat with the AI Assistant"),
                BotCommand("get_following", "Scrape a Twitter user's following list"),
                BotCommand("x_media", "Download media from an X username"),
                BotCommand("redgifs_media", "Download all gifs from a RedGifs username")
            ])
            
            logger.info(f"✅ Bot '{me.first_name}' (@{me.username}) is now LIVE!")
            logger.info(f"🆔 Bot ID: {me.id}")
            logger.info(f"📅 Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info("⌨️ Press Ctrl+C to stop")
            
            # Start Group History Sync in background
            asyncio.create_task(sync_group_history(app))

            # Step 5: Start health monitoring
            logger.info("Starting health monitor...")
            asyncio.create_task(start_health_monitor(app, interval=300))

            # Start periodic media auto-cleanup
            from core.media_cleaner import start_auto_cleanup
            asyncio.create_task(start_auto_cleanup())
            logger.info("Auto-cleanup task scheduled")
            
            # Step 6: Log initial metrics
            logger.info("📊 Metrics tracking enabled")
            
            # Keep the bot running
            await idle()
            break
            
        except (ApiIdInvalid, AuthKeyInvalid) as e:
            logger.critical("âŒ Invalid API_ID, API_HASH, or BOT_TOKEN")
            logger.critical("Please check your .env configuration file")
            return
            
        except ConnectionError as e:
            retry_count += 1
            if retry_count < max_retries:
                wait_time = 2 ** retry_count
                logger.warning(
                    f"âš ï¸ Connection failed (attempt {retry_count}/{max_retries}). "
                    f"Retrying in {wait_time}s..."
                )
                await asyncio.sleep(wait_time)
            else:
                logger.critical(f"âŒ Failed to connect after {max_retries} attempts")
                return
                
        except FloodWait as e:
            logger.warning(f"⚠️ Telegram FloodWait: Must wait {e.value} seconds before retrying...")
            await asyncio.sleep(e.value)
            continue
        except Exception as e:
            if "database is locked" in str(e).lower():
                retry_count += 1
                if retry_count < max_retries:
                    wait_time = 2 ** retry_count
                    logger.warning(
                        f"Pyrogram session database is locked (attempt {retry_count}/{max_retries}). "
                        f"Retrying in {wait_time}s..."
                    )
                    await asyncio.sleep(wait_time)
                    continue
                logger.critical(
                    "Failed to start bot because session database remained locked. "
                    "If another bot instance is running, stop it and retry. "
                    "Tip: keep BOT_SESSION_IN_MEMORY=1 to avoid file lock issues."
                )
                return
            logger.critical(f"Critical system failure: {e}", exc_info=True)
            metrics.increment_errors("critical_startup_error")
            return
            
    # Cleanup on exit
    try:
        if app.is_connected:
            logger.info("Disconnecting bot...")
            await app.stop()
            logger.info("✓ Bot disconnected")
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")
    finally:
        _stop_aux_processes()
        logger.info("Bot execution ended")

if __name__ == "__main__":
    # Setup signal handlers
    loop = asyncio.get_event_loop()
    
    # Windows doesn't support adding signal handlers to the loop easily for SIGINT/SIGTERM in some versions
    # but we can try basic signal handling. 
    # For better cross-platform support, we just rely on KeyboardInterrupt for local dev, 
    # but for production on Linux, add_signal_handler is better.
    
    def handle_exception(loop, context):
        msg = context.get("exception", context["message"])
        logger.error(f"Caught exception: {msg}")
        
    async def shutdown(signal_name, loop):
        logger.info(f"Received exit signal {signal_name}...")
        try:
            if app.is_connected:
                logger.info("Disconnecting bot...")
                await app.stop()
                logger.info("✓ Bot disconnected")
        except Exception as e:
            logger.error(f"Error during shutdown disconnect: {e}")
        finally:
            _stop_aux_processes()
            
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        for task in tasks:
            task.cancel()
        
        await asyncio.gather(*tasks, return_exceptions=True)
        loop.stop()

    if os.name != 'nt':
        signals = (signal.SIGHUP, signal.SIGTERM, signal.SIGINT)
        for s in signals:
            loop.add_signal_handler(
                s, lambda s=s: asyncio.create_task(shutdown(s.name, loop)))
    
    loop.set_exception_handler(handle_exception)

    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        logger.warning("\nBot stopped by user interrupt (KeyboardInterrupt)")
        # On Windows or when signal handlers don't catch it first, ensure cleanup runs
        try:
            if loop.is_running():
                # If loop is still running, schedule shutdown
                loop.create_task(shutdown("SIGINT", loop))
            else:
                # If loop stopped, run shutdown explicitly
                loop.run_until_complete(shutdown("SIGINT", loop))
        except Exception as e:
            logger.critical(f"Error executing emergency shutdown: {e}")
            _stop_aux_processes()
    finally:
        logger.info("System shutdown complete")



