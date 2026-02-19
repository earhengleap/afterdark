import os
import unittest
from pathlib import Path
from unittest.mock import patch

import x_telegram


class _FakeTunnelProcess:
    def poll(self):
        return None

    def terminate(self):
        return None


class TestTwaTunnelTimeouts(unittest.TestCase):
    def test_localhostrun_uses_longer_default_url_timeout(self) -> None:
        root_dir = Path(__file__).resolve().parent.parent
        logs_dir = root_dir / "data" / "test_twa_timeout_logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        stdout_log = logs_dir / "localhostrun.stdout.log"
        stderr_log = logs_dir / "localhostrun.stderr.log"
        captured: dict[str, int] = {}

        def _fake_wait_public_url(_root: Path, timeout_seconds: int) -> str | None:
            captured["timeout"] = timeout_seconds
            return "https://abc123.lhr.life"

        env_updates = {"TWA_LOCALHOSTRUN_URL_TIMEOUT": ""}
        with patch.dict(os.environ, env_updates):
            with patch("x_telegram._resolve_ssh_executable", return_value="ssh.exe"):
                with patch("x_telegram._localhostrun_log_paths", return_value=(stdout_log, stderr_log)):
                    with patch("x_telegram.subprocess.Popen", return_value=_FakeTunnelProcess()):
                        with patch("x_telegram.time.sleep", return_value=None):
                            with patch(
                                "x_telegram._wait_for_localhostrun_public_url",
                                side_effect=_fake_wait_public_url,
                            ):
                                with patch("x_telegram._wait_for_public_url_health", return_value=True):
                                    with patch("x_telegram._persist_twa_public_url"):
                                        with patch("x_telegram._sync_twa_menu_button"):
                                            ok = x_telegram._start_localhostrun_tunnel(root_dir, "5000")

        self.assertTrue(ok)
        self.assertEqual(captured.get("timeout"), 120)
