import os
import shutil
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path

import core.image_downloader as image_downloader
from core.image_downloader import ImageDownloader


@contextmanager
def _writable_temp_dir() -> str:
    """tempfile.TemporaryDirectory() creates 0o700 dirs, which are not writable in this sandbox.

    Create a unique directory under tests/_tmp using default permissions instead.
    """

    base = Path(__file__).resolve().parent / "_tmp"
    base.mkdir(parents=True, exist_ok=True)
    target = base / f"tmp_{uuid.uuid4().hex}"
    target.mkdir()
    try:
        yield str(target)
    finally:
        shutil.rmtree(target, ignore_errors=True)


class TestImageDownloaderSafeRename(unittest.TestCase):
    def test_safe_rename_does_not_double_prefix(self) -> None:
        with _writable_temp_dir() as tmp:
            old_images_folder = image_downloader.IMAGES_FOLDER
            image_downloader.IMAGES_FOLDER = tmp
            try:
                original = os.path.join(tmp, "24-twitter_123.jpg")
                with open(original, "wb") as f:
                    f.write(b"x")

                renamed = ImageDownloader._safe_rename_with_number(original)

                self.assertEqual(renamed, original)
                self.assertTrue(os.path.exists(original))
            finally:
                image_downloader.IMAGES_FOLDER = old_images_folder

    def test_safe_rename_adds_prefix_for_unprefixed_file(self) -> None:
        with _writable_temp_dir() as tmp:
            old_images_folder = image_downloader.IMAGES_FOLDER
            image_downloader.IMAGES_FOLDER = tmp
            try:
                original = os.path.join(tmp, "twitter_123.jpg")
                with open(original, "wb") as f:
                    f.write(b"x")

                renamed = ImageDownloader._safe_rename_with_number(original)

                self.assertNotEqual(renamed, original)
                self.assertTrue(os.path.exists(renamed))
                self.assertFalse(os.path.exists(original))
                self.assertTrue(os.path.basename(renamed).startswith("01-"))
            finally:
                image_downloader.IMAGES_FOLDER = old_images_folder
