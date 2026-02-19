import os
import shutil
import unittest
import uuid
from contextlib import contextmanager
import json
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType
from unittest.mock import patch


@contextmanager
def _writable_temp_dir() -> str:
    base = Path(__file__).resolve().parent / "_tmp"
    base.mkdir(parents=True, exist_ok=True)
    target = base / f"tmp_{uuid.uuid4().hex}"
    target.mkdir()
    try:
        yield str(target)
    finally:
        shutil.rmtree(target, ignore_errors=True)


def _load_twa_server_module() -> ModuleType:
    # Ensure config loader doesn't sys.exit() in tests when env vars are missing.
    os.environ.setdefault("BOT_TOKEN", "test-token")
    os.environ.setdefault("API_ID", "12345")
    os.environ.setdefault("API_HASH", "test-hash")

    repo_root = Path(__file__).resolve().parents[1]
    server_path = repo_root / "telegram-bot-websites" / "server.py"
    spec = spec_from_file_location(f"twa_server_{uuid.uuid4().hex}", server_path)
    assert spec and spec.loader
    mod = module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


class _FakeResponse:
    def __init__(self, payload: bytes):
        self._payload = payload

    def read(self) -> bytes:
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class TestTwaAiDescription(unittest.TestCase):
    def test_ai_needs_generation_when_description_missing(self) -> None:
        mod = _load_twa_server_module()

        entry = {"ai_title": "Tasteful adult pose", "ai_description": ""}
        self.assertTrue(mod.TelegramGalleryService._ai_title_needs_generation(entry, mode="missing"))

    def test_ollama_analyze_image_path_parses_title_and_description(self) -> None:
        mod = _load_twa_server_module()

        # Keep test deterministic and avoid hitting any local Ollama instance.
        mod.AI_TITLE_PROVIDER = "ollama"
        mod.AI_TITLE_OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
        mod.AI_TITLE_MODEL = "vision-test:latest"
        mod.AI_TITLE_FALLBACK_MODELS = []
        mod.AI_TITLE_TIMEOUT_SECONDS = 3
        mod.AI_TITLE_STYLE = "tasteful"

        with _writable_temp_dir() as tmp:
            cache_dir = Path(tmp) / "cache"
            cache_dir.mkdir(parents=True, exist_ok=True)

            # Dummy "image" bytes are fine; the HTTP call is mocked.
            image_path = Path(tmp) / "sample.jpg"
            image_path.write_bytes(b"not-a-real-jpeg")

            # Avoid constructing real Pyrogram clients (event loop warnings); analysis code doesn't need it.
            with patch.object(mod.TelegramGalleryService, "_build_client", return_value=object()):
                service = mod.TelegramGalleryService(cache_dir=cache_dir)

            model_output = (
                '{ "title": "Tasteful adult nude pose", '
                '"description": "An adult nude pose in a bedroom. No explicit details." }'
            )
            http_body = json.dumps({"response": model_output, "done": True}).encode("utf-8")

            with patch.object(mod.urllib.request, "urlopen", return_value=_FakeResponse(http_body)):
                result = service._ollama_analyze_image_path(
                    image_path=image_path,
                    media_kind="image",
                    caption="",
                    message_id=123,
                )

        self.assertIsNotNone(result)
        title, desc, used_model = result  # type: ignore[misc]
        self.assertIn("Tasteful", title)
        self.assertIn("adult", title.lower())
        self.assertIn("bedroom", desc.lower())
        self.assertEqual(used_model, "vision-test:latest")

    def test_ai_needs_generation_for_default_placeholder_title(self) -> None:
        mod = _load_twa_server_module()

        entry = {
            "ai_title": "Video #123",
            "ai_description": "A generic placeholder description",
            "media_kind": "video",
            "message_id": 123,
        }
        self.assertTrue(mod.TelegramGalleryService._ai_title_needs_generation(entry, mode="missing"))


class TestTwaAiRealtimeBehavior(unittest.IsolatedAsyncioTestCase):
    async def test_generate_missing_ai_titles_prioritizes_images(self) -> None:
        mod = _load_twa_server_module()
        mod.AI_TITLE_IMAGE_PRIORITY = True

        with _writable_temp_dir() as tmp:
            cache_dir = Path(tmp) / "cache"
            cache_dir.mkdir(parents=True, exist_ok=True)

            with patch.object(mod.TelegramGalleryService, "_build_client", return_value=object()):
                service = mod.TelegramGalleryService(cache_dir=cache_dir)

            service._started = True
            service.media_index = [
                {
                    "message_id": 101,
                    "media_kind": "video",
                    "ai_title": "",
                    "ai_description": "",
                    "caption": "",
                    "is_cached": False,
                    "size": 0,
                },
                {
                    "message_id": 102,
                    "media_kind": "image",
                    "ai_title": "",
                    "ai_description": "",
                    "caption": "",
                    "is_cached": False,
                    "size": 0,
                },
            ]

            call_order = []

            async def _fake_generate(item, mode="missing"):
                call_order.append(int(item.get("message_id", 0)))
                item["ai_description"] = "desc"
                item["ai_title_model"] = "test-model"
                item["ai_title_generated_at"] = "2026-02-18T00:00:00+00:00"
                return f"title-{item['message_id']}"

            service._generate_ai_title_for_item = _fake_generate  # type: ignore[method-assign]
            service._save_index = lambda: None  # type: ignore[assignment]

            generated = await service.generate_missing_ai_titles(batch_size=2, recent_limit=0, mode="missing")

        self.assertEqual(generated, 2)
        self.assertEqual(call_order, [102, 101])

    async def test_api_sync_does_not_call_full_infinite_ai_processing(self) -> None:
        mod = _load_twa_server_module()

        sample_items = [
            {
                "message_id": 5001,
                "media_kind": "image",
                "ai_title": "",
                "ai_description": "",
                "caption": "",
                "date": "2026-02-18T00:00:00+00:00",
                "url": "/api/file/5001",
                "thumb_url": "/api/file/5001",
                "size": 100,
                "is_cached": False,
            }
        ]

        async def _fake_sync(*args, **kwargs):
            mod.service.media_index = list(sample_items)
            return list(sample_items)

        async def _fake_generate_missing_ai_titles(*args, **kwargs):
            return 0

        with (
            patch.object(mod.service, "sync_group_media", side_effect=_fake_sync),
            patch.object(mod.service, "generate_missing_ai_titles", side_effect=_fake_generate_missing_ai_titles),
            patch.object(mod.service, "process_all_untitled_media_fully", side_effect=RuntimeError("should not be called")) as mocked_full_process,
        ):
            result = await mod.api_sync(
                limit="all",
                force_redownload=False,
                response_limit="240",
                wait_seconds=3,
                process_ai=True,
                ai_max_items=None,
                init_data=None,
                user_agent=None,
            )

        self.assertTrue(result["sync_started"])
        self.assertIsNone(result["sync_error"])
        self.assertEqual(mocked_full_process.call_count, 0)
