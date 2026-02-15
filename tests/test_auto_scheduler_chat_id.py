import unittest
from unittest.mock import patch

from core.auto_scheduler import AutoScheduler


class _FakeChat:
    def __init__(self, chat_id: int):
        self.id = chat_id


class _FakeMessage:
    def __init__(self, chat_id: int, text: str = "hello"):
        self.chat = _FakeChat(chat_id)
        self.caption = None
        self.text = text
        self.reply_markup = None

    async def edit_caption(self, caption=None, reply_markup=None, **kwargs):
        self.caption = caption
        self.reply_markup = reply_markup
        return self

    async def edit_text(self, text=None, reply_markup=None, **kwargs):
        self.text = text
        self.reply_markup = reply_markup
        return self


class _FakeStatusMessage:
    def __init__(self):
        self.texts = []

    async def edit_text(self, text, **kwargs):
        self.texts.append(text)
        return self


class _FakeClient:
    def __init__(self):
        self.sent = []

    async def send_message(self, chat_id=None, text=None, **kwargs):
        self.sent.append({"chat_id": chat_id, "text": text})
        return _FakeStatusMessage()


class TestAutoSchedulerTargetChat(unittest.IsolatedAsyncioTestCase):
    async def test_auto_scheduler_sends_status_to_message_chat(self) -> None:
        client = _FakeClient()
        message = _FakeMessage(chat_id=-100123456789, text="summary")
        user_id = 999999

        async def _fake_upload_to_group(video_path, uid, status_msg=None, client=None):
            return True, "ok"

        with patch("core.auto_scheduler.VideoUploader.upload_to_group", new=_fake_upload_to_group):
            await AutoScheduler._countdown_and_upload(
                client=client,
                message=message,
                user_id=user_id,
                content_type="video_single",
                content_path="does_not_exist.mp4",
                duration=0,
                task_key="t1",
            )

        self.assertEqual(len(client.sent), 1)
        self.assertEqual(client.sent[0]["chat_id"], message.chat.id)

