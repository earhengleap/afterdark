#!/usr/bin/env python3
"""
Configure Telegram bot menu button for Mini App (WebApp).

Usage:
  python telegram-bot-websites/configure_twa.py --url https://your-public-domain.example
"""

import argparse
import json
import sys
from typing import Any, Dict

import requests

sys.path.insert(0, ".")
from config.settings import BOT_TOKEN  # noqa: E402


API_BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"


def telegram_api(method: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    response = requests.post(f"{API_BASE}/{method}", data=payload, timeout=30)
    response.raise_for_status()
    body = response.json()
    if not body.get("ok"):
        raise RuntimeError(f"Telegram API {method} failed: {body}")
    return body


def main() -> None:
    parser = argparse.ArgumentParser(description="Set bot menu button as Telegram Mini App")
    parser.add_argument("--url", required=True, help="Public HTTPS URL for your Mini App")
    parser.add_argument("--text", default="Open Vault", help="Menu button text")
    args = parser.parse_args()

    if not args.url.startswith("https://"):
        raise ValueError("Mini App URL must be HTTPS")

    menu_button = {
        "type": "web_app",
        "text": args.text,
        "web_app": {
            "url": args.url,
        },
    }

    result = telegram_api(
        "setChatMenuButton",
        {
            "menu_button": json.dumps(menu_button),
        },
    )

    print("Menu button configured successfully.")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
