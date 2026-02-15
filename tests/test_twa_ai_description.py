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
