import unittest
from pathlib import Path
from unittest.mock import patch

import afterdark


class TunnelCommandTests(unittest.TestCase):
    def test_tunnel_provider_is_cloudflared(self):
        provider = afterdark._choose_tunnel_provider("C:/cloudflared.exe", "auto")

        self.assertEqual(provider, "cloudflared")
        self.assertEqual(afterdark._choose_tunnel_provider(None, "localhostrun"), "cloudflared")

    def test_localhostrun_command_uses_real_ssh_config_file(self):
        root_dir = Path("D:/AfterDark")
        cmd = afterdark._build_localhostrun_command(root_dir, 5000)

        self.assertEqual(cmd[0], "ssh")
        self.assertIn("-F", cmd)
        config_path = cmd[cmd.index("-F") + 1]
        self.assertNotEqual(config_path.upper(), "NUL")
        self.assertTrue(config_path.endswith("empty_ssh_config"))
        self.assertIn("nokey@localhost.run", cmd)

    def test_cloudflared_command_points_at_local_dashboard(self):
        cmd = afterdark._build_cloudflared_command("C:/cloudflared.exe", 5000)

        self.assertEqual(cmd[0], "C:/cloudflared.exe")
        self.assertEqual(cmd[1:3], ["tunnel", "--url"])
        self.assertEqual(cmd[3], "http://127.0.0.1:5000")

    def test_menu_clear_payload_uses_commands_button(self):
        payload = afterdark._build_commands_menu_button_payload()

        self.assertEqual(payload["type"], "commands")

    def test_tunnel_health_accepts_local_dashboard_fallback(self):
        with patch("afterdark._check_health_url", side_effect=[False, True]):
            healthy = afterdark._probe_tunnel_health("https://example.trycloudflare.com", 5000)

        self.assertTrue(healthy)


if __name__ == "__main__":
    unittest.main()
