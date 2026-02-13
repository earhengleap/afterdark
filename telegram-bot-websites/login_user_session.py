#!/usr/bin/env python3
"""
Create a USER session for Telegram gallery history access.

This is required if you want full history reads from group/channel.
"""

import asyncio
import sys

sys.path.insert(0, ".")
from pyrogram import Client  # noqa: E402
from config.settings import API_ID, API_HASH  # noqa: E402

SESSION_NAME = "twa_user"
WORKDIR = "telegram-bot-websites/media_cache"


async def main() -> None:
    app = Client(SESSION_NAME, api_id=API_ID, api_hash=API_HASH, workdir=WORKDIR)
    await app.start()
    me = await app.get_me()
    print(f"Logged in as: {me.id} {getattr(me, 'username', '')}")
    await app.stop()
    print("User session saved successfully.")


if __name__ == "__main__":
    asyncio.run(main())
