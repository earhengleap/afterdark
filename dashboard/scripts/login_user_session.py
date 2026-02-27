#!/usr/bin/env python3
"""
Create a USER session for Telegram gallery history access.

This is required if you want full history reads from group/channel.
"""

import asyncio
import os
import sys

# Make sure imports work no matter where script is run from
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, project_root)

from pyrogram import Client  # noqa: E402
from config.settings import API_ID, API_HASH  # noqa: E402

SESSION_NAME = "twa_user"
# Force workdir to always be absolute path to project_root/dashboard/media_cache
WORKDIR = os.path.join(project_root, "dashboard", "media_cache")


async def main() -> None:
    app = Client(SESSION_NAME, api_id=API_ID, api_hash=API_HASH, workdir=WORKDIR)
    await app.start()
    me = await app.get_me()
    print(f"Logged in as: {me.id} {getattr(me, 'username', '')}")
    await app.stop()
    print("User session saved successfully.")


if __name__ == "__main__":
    asyncio.run(main())
