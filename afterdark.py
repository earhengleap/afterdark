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
import json
import urllib.request
import urllib.parse
import socket
import re
from datetime import datetime
from pathlib import Path

from pyrogram import Client, idle
from pyrogram.types import BotCommand
from pyrogram.errors import ApiIdInvalid, AuthKeyInvalid

# Configuration imports
from config.settings import BOT_TOKEN, API_ID, API_HASH, BOT_VERSION, BOT_NAME, VERSION_DATE, CHAT_ID
from config.paths import setup_directories

# Core functionality imports
from core.logger import setup_logger
from core.metrics import metrics, get_metrics
from core.config_validator import validate_configuration
from core.health_monitor import start_health_monitor, get_health_monitor

# Handler imports
from handlers.command_handlers import setup_command_handlers
from handlers.callback_handlers import setup_callback_handlers

# Initialize Logger
logger = setup_logger()

# ==================== TWA BOOTSTRAP ====================

_aux_processes = []
_NOTIFY_USERNAME = "@HengleapEar"


def _send_tunnel_notification(public_url: str) -> None:
    """Send tunnel URL notification to Telegram user synchronously via HTTP to avoid event loop crashes."""
    try:
        message_text = (
            f"🌐 **Tunnel Active**\n\n"
            f"URL: {public_url}\n\n"
            f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        payload = {
            "chat_id": CHAT_ID,
            "text": message_text,
            "disable_web_page_preview": "true"
        }
        _telegram_api_post("sendMessage", payload)
        logger.info(f"✅ Tunnel URL sent to Chat ID {CHAT_ID}")
    except Exception as e:
        logger.error(f"❌ Failed to send tunnel notification: {e}")


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


def _resolve_ssh_executable() -> str | None:
    candidates = ["ssh.exe", "ssh"] if os.name == "nt" else ["ssh"]
    return _resolve_executable("TWA_SSH_BIN", candidates)


_LOCALHOSTRUN_URL_RE = re.compile(r"https://[A-Za-z0-9.-]+")
_LOCALHOSTRUN_HINT_RE = re.compile(
    r"tunneled with tls termination,\s*(https://[A-Za-z0-9.-]+)",
    re.IGNORECASE,
)
_SERVEO_URL_RE = re.compile(r"https://[A-Za-z0-9.-]*serveousercontent\.com", re.IGNORECASE)


def _localhostrun_target() -> str:
    return os.getenv("TWA_LOCALHOSTRUN_TARGET", "nokey@localhost.run").strip() or "nokey@localhost.run"


def _localhostrun_remote_port() -> str:
    raw = os.getenv("TWA_LOCALHOSTRUN_REMOTE_PORT", "80").strip() or "80"
    return raw if raw.isdigit() else "80"


def _localhostrun_log_paths(root_dir: Path) -> tuple[Path, Path]:
    stdout_custom = os.getenv("TWA_LOCALHOSTRUN_STDOUT_LOG", "").strip()
    stderr_custom = os.getenv("TWA_LOCALHOSTRUN_STDERR_LOG", "").strip()

    stdout_path = Path(stdout_custom).expanduser() if stdout_custom else (root_dir / "logs" / "localhostrun.stdout.log")
    stderr_path = Path(stderr_custom).expanduser() if stderr_custom else (root_dir / "logs" / "localhostrun.stderr.log")
    return stdout_path, stderr_path


def _serveo_target() -> str:
    return os.getenv("TWA_SERVEO_TARGET", "serveo.net").strip() or "serveo.net"


def _serveo_remote_port() -> str:
    raw = os.getenv("TWA_SERVEO_REMOTE_PORT", "80").strip() or "80"
    return raw if raw.isdigit() else "80"


def _serveo_log_paths(root_dir: Path) -> tuple[Path, Path]:
    stdout_custom = os.getenv("TWA_SERVEO_STDOUT_LOG", "").strip()
    stderr_custom = os.getenv("TWA_SERVEO_STDERR_LOG", "").strip()

    stdout_path = Path(stdout_custom).expanduser() if stdout_custom else (root_dir / "logs" / "serveo.stdout.log")
    stderr_path = Path(stderr_custom).expanduser() if stderr_custom else (root_dir / "logs" / "serveo.stderr.log")
    return stdout_path, stderr_path


def _parse_port_candidates(raw: str, defaults: list[int]) -> list[int]:
    ports: list[int] = []
    for token in str(raw or "").split(","):
        value = token.strip()
        if not value.isdigit():
            continue
        port = int(value)
        if 1 <= port <= 65535 and port not in ports:
            ports.append(port)
    return ports or list(defaults)


def _serveo_ssh_ports() -> list[int]:
    single = os.getenv("TWA_SERVEO_SSH_PORT", "").strip()
    if single.isdigit():
        port = int(single)
        if 1 <= port <= 65535:
            return [port]
    return _parse_port_candidates(os.getenv("TWA_SERVEO_SSH_PORTS", "").strip(), [22, 443])


def _ssh_target_host(target: str) -> str:
    value = str(target or "").strip()
    if "@" in value:
        return value.rsplit("@", 1)[-1]
    return value


def _is_tcp_reachable(host: str, port: int, timeout_seconds: float = 6.0) -> bool:
    try:
        with socket.create_connection((host, int(port)), timeout=timeout_seconds):
            return True
    except Exception:
        return False


def _terminate_process(proc: subprocess.Popen | None) -> None:
    if not proc:
        return
    try:
        if proc.poll() is None:
            proc.terminate()
    except Exception:
        pass


def _read_localhostrun_public_url(root_dir: Path) -> str | None:
    stdout_path, stderr_path = _localhostrun_log_paths(root_dir)
    text_parts: list[str] = []

    for path in (stdout_path, stderr_path):
        try:
            if path.exists():
                text_parts.append(path.read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            continue

    if not text_parts:
        return None

    text = "\n".join(text_parts)
    hinted = _LOCALHOSTRUN_HINT_RE.findall(text)
    for url in reversed(hinted):
        normalized = url.strip().rstrip("/")
        if normalized.startswith("https://"):
            return normalized

    blocked_hosts = {"localhost.run", "admin.localhost.run", "twitter.com", "openssh.com"}
    matches = _LOCALHOSTRUN_URL_RE.findall(text)
    prioritized: list[str] = []
    for url in reversed(matches):
        normalized = url.strip().rstrip("/")
        if not normalized.startswith("https://"):
            continue
        host = urllib.parse.urlparse(normalized).netloc.lower()
        if not host or host in blocked_hosts:
            continue
        if host.endswith(".lhr.life") or host.endswith(".localhost.run"):
            prioritized.append(normalized)

    if prioritized:
        return prioritized[0]
    return None


def _read_serveo_public_url(root_dir: Path) -> str | None:
    stdout_path, stderr_path = _serveo_log_paths(root_dir)
    text_parts: list[str] = []

    for path in (stdout_path, stderr_path):
        try:
            if path.exists():
                text_parts.append(path.read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            continue

    if not text_parts:
        return None

    text = "\n".join(text_parts)
    matches = _SERVEO_URL_RE.findall(text)
    if matches:
        return matches[-1].strip().rstrip("/")

    generic = _LOCALHOSTRUN_URL_RE.findall(text)
    for url in reversed(generic):
        normalized = url.strip().rstrip("/")
        host = urllib.parse.urlparse(normalized).netloc.lower()
        if "serveo" in host and normalized.startswith("https://"):
            return normalized
    return None


def _wait_for_localhostrun_public_url(root_dir: Path, timeout_seconds: int) -> str | None:
    deadline = time.time() + max(1, timeout_seconds)
    while time.time() < deadline:
        url = _read_localhostrun_public_url(root_dir)
        if url:
            return url
        time.sleep(1)
    return None


def _wait_for_serveo_public_url(root_dir: Path, timeout_seconds: int) -> str | None:
    deadline = time.time() + max(1, timeout_seconds)
    while time.time() < deadline:
        url = _read_serveo_public_url(root_dir)
        if url:
            return url
        time.sleep(1)
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


def _sync_twa_menu_button(public_url: str, root_dir: Path) -> None:
    if not _is_true(os.getenv("TWA_MENU_SYNC_AUTOSTART", "1")):
        return

    url = public_url.rstrip("/") + "/"
    button_text = os.getenv("TWA_MENU_TEXT", "Open Vault").strip() or "Open Vault"
    menu_button = {
        "type": "web_app",
        "text": button_text,
        "web_app": {"url": url},
    }
    payload = {"menu_button": json.dumps(menu_button)}

    try:
        _telegram_api_post("setChatMenuButton", payload)
    except Exception as e:
        logger.warning(f"Failed to sync default Mini App menu URL: {e}")

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
            logger.warning(f"Failed to sync Mini App menu URL for chat_id={chat_id}: {e}")

    logger.info(f"Mini App menu URL synced for {updated}/{len(chat_ids)} chat(s).")


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


def _start_serveo_tunnel(root_dir: Path, twa_port: str) -> bool:
    ssh_executable = _resolve_ssh_executable()
    if not ssh_executable:
        logger.warning(
            "Mini App backend started, but ssh client was not found on PATH. "
            "Install OpenSSH client or set TWA_SSH_BIN."
        )
        return False

    stdout_log, stderr_log = _serveo_log_paths(root_dir)
    try:
        stdout_log.parent.mkdir(parents=True, exist_ok=True)
        stderr_log.parent.mkdir(parents=True, exist_ok=True)
        if _is_true(os.getenv("TWA_SERVEO_TRUNCATE_LOG", "1")):
            stdout_log.write_text("", encoding="utf-8")
            stderr_log.write_text("", encoding="utf-8")
    except Exception as e:
        logger.warning(f"Unable to initialize serveo log files: {e}")

    remote_port = _serveo_remote_port()
    tunnel_target = _serveo_target()
    target_host = _ssh_target_host(tunnel_target)
    connect_timeout_raw = os.getenv("TWA_SERVEO_CONNECT_TIMEOUT", "8").strip()
    try:
        connect_timeout = max(2, int(connect_timeout_raw))
    except ValueError:
        connect_timeout = 8

    ssh_ports = _serveo_ssh_ports()
    reachable_ports = [port for port in ssh_ports if _is_tcp_reachable(target_host, port, connect_timeout)]
    if not reachable_ports:
        logger.warning(
            f"serveo host '{target_host}' is unreachable on SSH port(s) {ssh_ports}. "
            "Check firewall/ISP/VPN routing or set TWA_SERVEO_TARGET/TWA_SERVEO_SSH_PORTS."
        )
        return False

    timeout_raw = os.getenv("TWA_SERVEO_URL_TIMEOUT", "45").strip()
    try:
        timeout_seconds = max(5, int(timeout_raw))
    except ValueError:
        timeout_seconds = 45

    health_timeout_raw = os.getenv("TWA_TUNNEL_HEALTH_TIMEOUT", "18").strip()
    try:
        health_timeout = max(3, int(health_timeout_raw))
    except ValueError:
        health_timeout = 18

    for ssh_port in reachable_ports:
        command = [
            ssh_executable,
            "-p",
            str(ssh_port),
            "-o",
            "StrictHostKeyChecking=accept-new",
            "-o",
            "ExitOnForwardFailure=yes",
            "-o",
            "ServerAliveInterval=15",
            "-o",
            "ServerAliveCountMax=5",
            "-R",
            f"{remote_port}:127.0.0.1:{twa_port}",
            tunnel_target,
        ]

        try:
            stdout_log.write_text("", encoding="utf-8")
            stderr_log.write_text("", encoding="utf-8")
        except Exception:
            pass

        stdout_handle = open(stdout_log, "a", encoding="utf-8", errors="ignore")
        stderr_handle = open(stderr_log, "a", encoding="utf-8", errors="ignore")
        try:
            if os.name == "nt":
                tunnel_proc = subprocess.Popen(
                    command,
                    cwd=str(root_dir),
                    env=os.environ.copy(),
                    creationflags=subprocess.CREATE_NEW_CONSOLE,
                    stdout=stdout_handle,
                    stderr=stderr_handle,
                )
            else:
                tunnel_proc = subprocess.Popen(
                    command,
                    cwd=str(root_dir),
                    env=os.environ.copy(),
                    stdout=stdout_handle,
                    stderr=stderr_handle,
                )
        finally:
            stdout_handle.close()
            stderr_handle.close()

        _aux_processes.append(tunnel_proc)
        time.sleep(2)
        if tunnel_proc.poll() is not None:
            logger.warning(
                f"serveo tunnel exited early on SSH port {ssh_port}. "
                "Trying next serveo port/fallback."
            )
            _terminate_process(tunnel_proc)
            continue

        public_url = _wait_for_serveo_public_url(root_dir, timeout_seconds)
        if not public_url:
            logger.warning(
                f"serveo started on SSH port {ssh_port}, but no public URL was found in "
                f"{stdout_log} or {stderr_log}."
            )
            _terminate_process(tunnel_proc)
            continue

        # Serveo can take 20-40 seconds to fully propagate its proxies worldwide
        serveo_health_timeout = max(health_timeout, 60)
        logger.info(f"serveo URL found: {public_url}. Waiting up to {serveo_health_timeout}s for health check...")
        if not _wait_for_public_url_health(public_url, serveo_health_timeout):
            logger.warning(
                f"serveo URL is not healthy after {serveo_health_timeout}s: {public_url}. "
                "Trying next serveo port/fallback."
            )
            _terminate_process(tunnel_proc)
            continue

        logger.info(f"TWA serveo tunnel active and healthy: {public_url}")
        _persist_twa_public_url(root_dir, public_url)
        _sync_twa_menu_button(public_url, root_dir)
        _send_tunnel_notification(public_url)
        return True

    if len(reachable_ports) > 1:
        logger.warning(
            f"serveo failed across reachable SSH port(s) {reachable_ports}. "
            "Trying fallback provider."
        )
    return False


def _start_localhostrun_tunnel(root_dir: Path, twa_port: str) -> bool:
    ssh_executable = _resolve_ssh_executable()
    if not ssh_executable:
        logger.warning(
            "Mini App backend started, but ssh client was not found on PATH. "
            "Install OpenSSH client or set TWA_SSH_BIN."
        )
        return False

    stdout_log, stderr_log = _localhostrun_log_paths(root_dir)
    try:
        stdout_log.parent.mkdir(parents=True, exist_ok=True)
        stderr_log.parent.mkdir(parents=True, exist_ok=True)
        if _is_true(os.getenv("TWA_LOCALHOSTRUN_TRUNCATE_LOG", "1")):
            stdout_log.write_text("", encoding="utf-8")
            stderr_log.write_text("", encoding="utf-8")
    except Exception as e:
        logger.warning(f"Unable to initialize localhost.run log files: {e}")

    remote_port = _localhostrun_remote_port()
    tunnel_target = _localhostrun_target()
    command = [
        ssh_executable,
        "-F",
        "/dev/null",
        "-v",
        "-o",
        "StrictHostKeyChecking=accept-new",
        "-o",
        "ExitOnForwardFailure=yes",
        "-o",
        "ServerAliveInterval=30",
        "-o",
        "ServerAliveCountMax=3",
        "-R",
        f"{remote_port}:127.0.0.1:{twa_port}",
        tunnel_target,
    ]

    stdout_handle = open(stdout_log, "a", encoding="utf-8", errors="ignore")
    stderr_handle = open(stderr_log, "a", encoding="utf-8", errors="ignore")
    try:
        tunnel_proc = subprocess.Popen(
            command,
            cwd=str(root_dir),
            env=os.environ.copy(),
            stdout=stdout_handle,
            stderr=stderr_handle,
        )
    finally:
        stdout_handle.close()
        stderr_handle.close()

    _aux_processes.append(tunnel_proc)
    time.sleep(3)
    if tunnel_proc.poll() is not None:
        stdout_content = stdout_log.read_text(encoding="utf-8", errors="ignore") if stdout_log.exists() else ""
        stderr_content = stderr_log.read_text(encoding="utf-8", errors="ignore") if stderr_log.exists() else ""
        logger.warning(f"localhost.run tunnel exited early. stdout: {stdout_content[:200]}, stderr: {stderr_content[:200]}")
        _terminate_process(tunnel_proc)
        return False

    timeout_raw = os.getenv("TWA_LOCALHOSTRUN_URL_TIMEOUT", "120").strip()
    try:
        timeout_seconds = max(5, int(timeout_raw))
    except ValueError:
        timeout_seconds = 120

    public_url = _wait_for_localhostrun_public_url(root_dir, timeout_seconds)
    if public_url:
        health_timeout_raw = os.getenv("TWA_TUNNEL_HEALTH_TIMEOUT", "18").strip()
        try:
            health_timeout = max(3, int(health_timeout_raw))
        except ValueError:
            health_timeout = 18

        if not _wait_for_public_url_health(public_url, health_timeout):
            logger.warning(
                f"localhost.run URL is not healthy after {health_timeout}s: {public_url}. "
                "Trying fallback provider."
            )
            try:
                if tunnel_proc.poll() is None:
                    tunnel_proc.terminate()
            except Exception:
                pass
            return False

        logger.info(f"TWA localhost.run tunnel active: {public_url}")
        _persist_twa_public_url(root_dir, public_url)
        _sync_twa_menu_button(public_url, root_dir)
        _send_tunnel_notification(public_url)
        return True
    else:
        logger.warning(
            f"localhost.run started, but no public URL was found in {stdout_log} or {stderr_log}. "
            "Set TWA_PUBLIC_URL manually if needed."
        )
        _terminate_process(tunnel_proc)
        return False


def _pinggy_target() -> str:
    return os.getenv("TWA_PINGGY_TARGET", "a.pinggy.io").strip() or "a.pinggy.io"


def _pinggy_log_paths(root_dir: Path) -> tuple[Path, Path]:
    stdout_custom = os.getenv("TWA_PINGGY_STDOUT_LOG", "").strip()
    stderr_custom = os.getenv("TWA_PINGGY_STDERR_LOG", "").strip()

    stdout_path = Path(stdout_custom).expanduser() if stdout_custom else (root_dir / "logs" / "pinggy.stdout.log")
    stderr_path = Path(stderr_custom).expanduser() if stderr_custom else (root_dir / "logs" / "pinggy.stderr.log")
    return stdout_path, stderr_path


def _read_pinggy_public_url(root_dir: Path) -> str | None:
    stdout_path, stderr_path = _pinggy_log_paths(root_dir)
    text_parts: list[str] = []

    for path in (stdout_path, stderr_path):
        try:
            if path.exists():
                text_parts.append(path.read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            continue

    if not text_parts:
        return None

    text = "\n".join(text_parts)
    # Pinggy output usually contains "https://rnnbv-xxx.a.pinggy.online"
    matches = re.findall(r"https://[A-Za-z0-9.-]+\.pinggy\.online", text, re.IGNORECASE)
    if matches:
        return matches[-1].strip().rstrip("/")
    return None


def _wait_for_pinggy_public_url(root_dir: Path, timeout_seconds: int) -> str | None:
    deadline = time.time() + max(1, timeout_seconds)
    while time.time() < deadline:
        url = _read_pinggy_public_url(root_dir)
        if url:
            return url
        time.sleep(2)
    return None


def _start_pinggy_tunnel(root_dir: Path, twa_port: str) -> bool:
    ssh_executable = _resolve_ssh_executable()
    if not ssh_executable:
        logger.warning(
            "Mini App backend started, but ssh client was not found on PATH. "
            "Install OpenSSH client or set TWA_SSH_BIN."
        )
        return False

    stdout_log, stderr_log = _pinggy_log_paths(root_dir)
    try:
        stdout_log.parent.mkdir(parents=True, exist_ok=True)
        stderr_log.parent.mkdir(parents=True, exist_ok=True)
        if _is_true(os.getenv("TWA_PINGGY_TRUNCATE_LOG", "1")):
            stdout_log.write_text("", encoding="utf-8")
            stderr_log.write_text("", encoding="utf-8")
    except Exception as e:
        logger.warning(f"Unable to initialize pinggy log files: {e}")

    tunnel_target = _pinggy_target()
    command = [
        ssh_executable,
        "-p",
        "443",
        "-o",
        "StrictHostKeyChecking=accept-new",
        "-o",
        "ExitOnForwardFailure=yes",
        "-o",
        "ServerAliveInterval=30",
        "-o",
        "ServerAliveCountMax=3",
        "-R0:127.0.0.1:" + twa_port,
        tunnel_target,
    ]

    stdout_handle = open(stdout_log, "a", encoding="utf-8", errors="ignore")
    stderr_handle = open(stderr_log, "a", encoding="utf-8", errors="ignore")
    try:
        tunnel_proc = subprocess.Popen(
            command,
            cwd=str(root_dir),
            env=os.environ.copy(),
            stdout=stdout_handle,
            stderr=stderr_handle,
        )
    finally:
        stdout_handle.close()
        stderr_handle.close()

    _aux_processes.append(tunnel_proc)
    time.sleep(4)
    if tunnel_proc.poll() is not None:
        stdout_content = stdout_log.read_text(encoding="utf-8", errors="ignore") if stdout_log.exists() else ""
        stderr_content = stderr_log.read_text(encoding="utf-8", errors="ignore") if stderr_log.exists() else ""
        logger.warning(f"pinggy tunnel exited early. stdout: {stdout_content[:200]}, stderr: {stderr_content[:200]}")
        _terminate_process(tunnel_proc)
        return False

    timeout_raw = os.getenv("TWA_PINGGY_URL_TIMEOUT", "45").strip()
    try:
        timeout_seconds = max(5, int(timeout_raw))
    except ValueError:
        timeout_seconds = 45

    public_url = _wait_for_pinggy_public_url(root_dir, timeout_seconds)
    if public_url:
        health_timeout_raw = os.getenv("TWA_TUNNEL_HEALTH_TIMEOUT", "25").strip()
        try:
            health_timeout = max(3, int(health_timeout_raw))
        except ValueError:
            health_timeout = 25

        if not _wait_for_public_url_health(public_url, health_timeout):
            logger.warning(
                f"pinggy URL is not healthy after {health_timeout}s: {public_url}. "
                "Trying fallback provider."
            )
            try:
                if tunnel_proc.poll() is None:
                    tunnel_proc.terminate()
            except Exception:
                pass
            return False

        logger.info(f"TWA pinggy tunnel active: {public_url}")
        _persist_twa_public_url(root_dir, public_url)
        _sync_twa_menu_button(public_url, root_dir)
        _send_tunnel_notification(public_url)
        return True
    else:
        logger.warning(
            f"pinggy started, but no public URL was found in {stdout_log} or {stderr_log}. "
            "Set TWA_PUBLIC_URL manually if needed."
        )
        _terminate_process(tunnel_proc)
        return False


def _stop_tunnel_processes() -> None:
    for proc in reversed(_aux_processes):
        try:
            if proc and proc.poll() is None:
                args = getattr(proc, 'args', [])
                if isinstance(args, list) and any('ssh' in str(a).lower() for a in args):
                    proc.terminate()
                    proc.wait(timeout=3)
        except Exception:
            pass


def _start_tunnel_provider_flow(root_dir: Path, twa_port: str) -> bool:
    provider_raw = os.getenv("TWA_TUNNEL_PROVIDER", "auto").strip().lower()
    provider = provider_raw if provider_raw else "auto"

    if provider == "auto":
        if not _resolve_ssh_executable():
            logger.info("TWA Mini App started without public tunnel (ssh client not found).")
            return False
        if _is_true(os.getenv("TWA_LOCALHOSTRUN_AUTOSTART", "1")) and _start_localhostrun_tunnel(root_dir, twa_port):
            return True
        logger.warning("localhost.run tunnel failed in auto mode, trying pinggy.io...")
        if _is_true(os.getenv("TWA_PINGGY_AUTOSTART", "1")) and _start_pinggy_tunnel(root_dir, twa_port):
            return True
        logger.warning("pinggy tunnel failed, trying serveo as last resort...")
        if _is_true(os.getenv("TWA_SERVEO_AUTOSTART", "1")) and _start_serveo_tunnel(root_dir, twa_port):
            return True
        logger.warning("No tunnel provider succeeded in auto mode.")
        return False

    if provider in {"none", "off", "disabled"}:
        logger.info("TWA Mini App started without public tunnel (TWA_TUNNEL_PROVIDER=none).")
        return False

    if provider == "serveo":
        if not _is_true(os.getenv("TWA_SERVEO_AUTOSTART", "1")):
            logger.info("TWA Mini App started. serveo autostart disabled by TWA_SERVEO_AUTOSTART.")
            return False
        if _start_serveo_tunnel(root_dir, twa_port):
            return True
        logger.warning("serveo failed, falling back to localhost.run...")
        if _is_true(os.getenv("TWA_LOCALHOSTRUN_AUTOSTART", "1")) and _start_localhostrun_tunnel(root_dir, twa_port):
            return True
        return False

    if provider == "localhostrun":
        if not _is_true(os.getenv("TWA_LOCALHOSTRUN_AUTOSTART", "1")):
            logger.info("TWA Mini App started. localhost.run autostart disabled by TWA_LOCALHOSTRUN_AUTOSTART.")
            return False
        if _start_localhostrun_tunnel(root_dir, twa_port):
            return True
        logger.warning("localhost.run failed, falling back to serveo...")
        if _is_true(os.getenv("TWA_SERVEO_AUTOSTART", "1")) and _start_serveo_tunnel(root_dir, twa_port):
            return True
        return False

    if provider == "pinggy":
        if not _is_true(os.getenv("TWA_PINGGY_AUTOSTART", "1")):
            logger.info("TWA Mini App started. pinggy.io autostart disabled by TWA_PINGGY_AUTOSTART.")
            return False
        if _start_pinggy_tunnel(root_dir, twa_port):
            return True
        logger.warning("pinggy.io failed, falling back to localhost.run...")
        if _is_true(os.getenv("TWA_LOCALHOSTRUN_AUTOSTART", "1")) and _start_localhostrun_tunnel(root_dir, twa_port):
            return True
        return False

    logger.warning(
        f"Unknown TWA_TUNNEL_PROVIDER='{provider_raw}'. "
        "Valid values: auto, serveo, localhostrun, lhrlife, none, off, disabled."
    )
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
                            subprocess.run(f"taskkill /F /PID {pid}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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


def _start_twa_stack() -> None:
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

    selected_port_int = twa_port_int
    selected_port = str(selected_port_int)
    reuse_existing_server = False
    
    if _is_port_open("127.0.0.1", twa_port_int):
        logger.info(f"Port {twa_port} is occupied. Force-killing to prevent reusing old servers...")
        _kill_port_process(twa_port_int)
        
        if _is_port_open("127.0.0.1", twa_port_int):
            fallback_port = _find_available_port(twa_port_int + 1)
            selected_port_int = fallback_port
            selected_port = str(fallback_port)
            logger.warning(
                f"Failed to kill process on port {twa_port}."
                f"Starting a fresh backend on port {selected_port}."
            )

    twa_port_int = selected_port_int
    twa_port = selected_port
    os.environ["TWA_PORT"] = twa_port

    server_env = os.environ.copy()
    server_env.setdefault("TELEGRAM_GALLERY_AUTH", "auto")
    server_env["TWA_PORT"] = twa_port
    if not server_env.get("TWA_AI_TEXT_MODEL", "").strip():
        server_env["TWA_AI_TEXT_MODEL"] = "dolphin-llama3:8b"
    if not server_env.get("TWA_AI_TEXT_FALLBACK_MODELS", "").strip():
        server_env["TWA_AI_TEXT_FALLBACK_MODELS"] = "gemma3:4b"

    if not reuse_existing_server:
        if os.name == "nt":
            python_exe = sys.executable or "python"
            server_proc = subprocess.Popen(
                [python_exe, str(server_script)],
                cwd=str(root_dir),
                env=server_env,
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
        else:
            server_proc = subprocess.Popen(
                [sys.executable, str(server_script)],
                cwd=str(root_dir),
                env=server_env,
            )

        _aux_processes.append(server_proc)
        time.sleep(2)
        if server_proc.poll() is not None:
            logger.warning("Mini App backend exited early. Check server logs.")
            return

    explicit_public_url = os.getenv("TWA_PUBLIC_URL", "").strip()
    if explicit_public_url.startswith("https://"):
        if _is_public_url_healthy(explicit_public_url):
            logger.info(f"Using explicit TWA_PUBLIC_URL: {explicit_public_url}")
            _persist_twa_public_url(root_dir, explicit_public_url)
            _sync_twa_menu_button(explicit_public_url, root_dir)
            return
        logger.warning(
            "Ignoring explicit TWA_PUBLIC_URL because /api/health is unreachable. "
            "Starting tunnel provider flow."
        )

    persisted_url = _read_persisted_twa_public_url(root_dir)
    if persisted_url and _is_public_url_healthy(persisted_url):
        logger.info(f"Using existing persisted TWA URL: {persisted_url}")
        _sync_twa_menu_button(persisted_url, root_dir)
        return

    _start_tunnel_provider_flow(root_dir, twa_port)


def _stop_aux_processes() -> None:
    for proc in reversed(_aux_processes):
        try:
            if proc and proc.poll() is None:
                proc.terminate()
                proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass

async def tunnel_watchdog(app) -> None:
    """Continuously monitor TWA tunnel health and restart if disconnected."""
    if not _is_true(os.getenv("TWA_AUTOSTART", "1")):
        return

    root_dir = Path(__file__).resolve().parent
    # Wait a bit after startup to avoid reacting to initialization 502s
    await asyncio.sleep(60)
    
    while True:
        try:
            provider = os.getenv("TWA_TUNNEL_PROVIDER", "auto").strip().lower()
            if provider in {"none", "off", "disabled"}:
                break
                
            explicit = os.getenv("TWA_PUBLIC_URL", "").strip()
            if explicit.startswith("https://"):
                await asyncio.sleep(60)
                continue
                
            twa_port = os.getenv("TWA_PORT", "5000").strip() or "5000"
            
            # Fast check: did the SSH process crash unexpectedly?
            ssh_dead = False
            for proc in reversed(_aux_processes):
                if proc and getattr(proc, 'args', []):
                    args_str = str(getattr(proc, 'args', [])).lower()
                    if 'ssh' in args_str:
                        if proc.poll() is not None:
                            ssh_dead = True
                        break # Only check the most recent ssh process
                        
            if ssh_dead:
                logger.warning("SSH tunnel process crashed! Restarting tunnel instantly...")
                await asyncio.to_thread(_stop_tunnel_processes)
                await asyncio.sleep(2)
                await asyncio.to_thread(_start_tunnel_provider_flow, root_dir, twa_port)
                await asyncio.sleep(15)
                continue

            persisted = await asyncio.to_thread(_read_persisted_twa_public_url, root_dir)
            
            if persisted:
                # Check public URL health
                is_healthy = await asyncio.to_thread(_is_public_url_healthy, persisted)
                if not is_healthy:
                    logger.warning(f"Tunnel {persisted} is unhealthy! Restarting SSH tunnel...")
                    await asyncio.to_thread(_stop_tunnel_processes)
                    await asyncio.sleep(2)
                    await asyncio.to_thread(_start_tunnel_provider_flow, root_dir, twa_port)
            else:
                # URL missing entirely? Maybe startup failed altogether. 
                # Attempt to restart it.
                await asyncio.to_thread(_start_tunnel_provider_flow, root_dir, twa_port)
                
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.debug(f"Tunnel watchdog error: {e}")
            
        await asyncio.sleep(45)

# ==================== PYROGRAM CLIENT ====================

def _build_bot_client() -> Client:
    session_name = os.getenv("BOT_SESSION_NAME", "afterdark_bot").strip() or "afterdark_bot"
    session_in_memory = _is_true(os.getenv("BOT_SESSION_IN_MEMORY", "1"))
    session_workdir = os.getenv("BOT_SESSION_WORKDIR", "").strip()

    client_kwargs = {
        "api_id": API_ID,
        "api_hash": API_HASH,
        "bot_token": BOT_TOKEN,
        "in_memory": session_in_memory,
    }
    if session_workdir:
        client_kwargs["workdir"] = session_workdir

    if session_in_memory:
        logger.info("Using in-memory bot session (BOT_SESSION_IN_MEMORY=1).")
    else:
        logger.info(f"Using file bot session '{session_name}'.")

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
        logger.error("⏱️ Timeout while stopping client - forcing shutdown")
    except Exception as e:
        logger.warning(f"⚠️ Error stopping client: {e}")
    
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
            logger.warning("⏱️ Some tasks did not cancel in time")
    
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
    """Print a professional banner on startup"""
    import sys
    # Force UTF-8 encoding for standard output to prevent charmap errors on Windows
    if sys.stdout.encoding.lower() != 'utf-8':
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except Exception:
            pass
            
    width = 60
    border = "━" * width
    try:
        print(f"\n\033[1;36m┏{border}┓\033[0m")
        print(f"\033[1;36m┃\033[0m \033[1;33m{BOT_NAME.center(width-2)}\033[0m \033[1;36m┃\033[0m")
        print(f"\033[1;36m┃\033[0m \033[1;32m{'Production Ready • Stable Version'.center(width-2)}\033[0m \033[1;36m┃\033[0m")
        print(f"\033[1;36m┣{border}┫\033[0m")
        print(f"\033[1;36m┃\033[0m \033[1;37m📦 Version: {BOT_VERSION.ljust(width-14)}\033[0m \033[1;36m┃\033[0m")
        print(f"\033[1;36m┃\033[0m \033[1;37m📅 Release: {VERSION_DATE.ljust(width-14)}\033[0m \033[1;36m┃\033[0m")
        print(f"\033[1;36m┃\033[0m \033[1;37m🛡️ System:   {os.name.upper().ljust(width-14)}\033[0m \033[1;36m┃\033[0m")
        print(f"\033[1;36m┃\033[0m \033[1;37m🕒 Startup: {datetime.now().strftime('%Y-%m-%d %H:%M:%S').ljust(width-14)}\033[0m \033[1;36m┃\033[0m")
        print(f"\033[1;36m┗{border}┛\033[0m")
    except UnicodeEncodeError:
        # Fallback if reconfigure failed and terminal absolutely cannot print emojis
        print("\n--- X Video Downloader Pro ---")
        print(f"Version: {BOT_VERSION}")
        print(f"Startup: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("------------------------------\n")

async def main():
    """Main bot entry point with enhanced error handling and monitoring"""
    print_banner()
    
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
    logger.info("✓ Handlers configured")
    # Step 3.5: Start Mini App backend stack
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
                BotCommand("version", "Check bot version"),
                BotCommand("health", "System health status"),
                BotCommand("chat", "Chat with the AI Assistant"),
                BotCommand("get_following", "Scrape a Twitter user's following list")
            ])
            
            logger.info(f"✅ Bot '{me.first_name}' (@{me.username}) is now LIVE!")
            logger.info(f"🆔 Bot ID: {me.id}")
            logger.info(f"📅 Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info("⌨️ Press Ctrl+C to stop")
            
            # Step 5: Start health monitoring
            logger.info("Starting health monitor...")
            asyncio.create_task(start_health_monitor(app, interval=300))
            
            # Start tunnel watchdog to auto-restart dropped tunnels
            asyncio.create_task(tunnel_watchdog(app))
            
            # Step 6: Log initial metrics
            logger.info("📊 Metrics tracking enabled")
            
            # Keep the bot running
            await idle()
            break
            
        except (ApiIdInvalid, AuthKeyInvalid) as e:
            logger.critical("❌ Invalid API_ID, API_HASH, or BOT_TOKEN")
            logger.critical("Please check your .env configuration file")
            return
            
        except ConnectionError as e:
            retry_count += 1
            if retry_count < max_retries:
                wait_time = 2 ** retry_count
                logger.warning(
                    f"⚠️ Connection failed (attempt {retry_count}/{max_retries}). "
                    f"Retrying in {wait_time}s..."
                )
                await asyncio.sleep(wait_time)
            else:
                logger.critical(f"❌ Failed to connect after {max_retries} attempts")
                return
                
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
    
    if os.name != 'nt':
        signals = (signal.SIGHUP, signal.SIGTERM, signal.SIGINT)
        for s in signals:
            loop.add_signal_handler(
                s, lambda s=s: asyncio.create_task(shutdown(s.name, loop)))
    
    loop.set_exception_handler(handle_exception)

    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        logger.warning("Bot stopped by user interrupt (KeyboardInterrupt)")
    finally:
        logger.info("System shutdown complete")
