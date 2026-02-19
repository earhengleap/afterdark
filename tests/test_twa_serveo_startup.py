import os
import unittest
from pathlib import Path
from unittest.mock import patch

import x_telegram


class TestTwaServeoStartup(unittest.TestCase):
    def test_serveo_ssh_ports_from_env(self) -> None:
        with patch.dict(os.environ, {"TWA_SERVEO_SSH_PORT": "", "TWA_SERVEO_SSH_PORTS": "443,22,443,abc"}):
            self.assertEqual(x_telegram._serveo_ssh_ports(), [443, 22])

    def test_serveo_unreachable_skips_spawn(self) -> None:
        root_dir = Path(__file__).resolve().parent.parent
        logs_dir = root_dir / "data" / "test_twa_serveo_logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        stdout_log = logs_dir / "serveo.stdout.log"
        stderr_log = logs_dir / "serveo.stderr.log"

        env_updates = {
            "TWA_SERVEO_TRUNCATE_LOG": "1",
            "TWA_SERVEO_TARGET": "serveo.net",
            "TWA_SERVEO_SSH_PORTS": "22,443",
            "TWA_SERVEO_SSH_PORT": "",
        }
        with patch.dict(os.environ, env_updates):
            with patch("x_telegram._resolve_ssh_executable", return_value="ssh.exe"):
                with patch("x_telegram._serveo_log_paths", return_value=(stdout_log, stderr_log)):
                    with patch("x_telegram._is_tcp_reachable", return_value=False):
                        with patch("x_telegram.subprocess.Popen") as popen:
                            ok = x_telegram._start_serveo_tunnel(root_dir, "5000")

        self.assertFalse(ok)
        popen.assert_not_called()

