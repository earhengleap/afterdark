import unittest
from unittest.mock import patch

from pyrogram.errors import FloodWait

from core.uploader import safe_edit_text


class _FakeMessage:
    def __init__(self):
        self.calls = 0

    async def edit_text(self, text, **kwargs):
        self.calls += 1
        if self.calls == 1:
            raise FloodWait(0)
        return None


class TestSafeEditText(unittest.IsolatedAsyncioTestCase):
    async def test_safe_edit_text_retries_after_floodwait(self) -> None:
        msg = _FakeMessage()
        slept = []

        async def _fake_sleep(seconds):
            slept.append(seconds)

        with patch("core.uploader.asyncio.sleep", new=_fake_sleep):
            try:
                await safe_edit_text(msg, "hello", disable_web_page_preview=True)
            except FloodWait:
                self.fail("safe_edit_text should handle FloodWait exceptions")

        self.assertGreaterEqual(msg.calls, 2)
        self.assertGreaterEqual(len(slept), 1)

