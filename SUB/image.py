import os
import subprocess
import sys

def ensure_gallery_dl():
    try:
        import gallery_dl  # noqa
    except ImportError:
        print("📦 Installing gallery-dl...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "gallery-dl"])

def download_x_images(post_url, output_dir="downloads", cookie_file="twitter_cookies.txt"):
    ensure_gallery_dl()
    os.makedirs(output_dir, exist_ok=True)

    print("=" * 60)
    print("🖼️  X/Twitter Image Downloader (gallery-dl with cookies)")
    print("=" * 60)
    print(f"URL: {post_url}\n")

    cmd = [
        sys.executable,
        "-m", "gallery_dl",
        "-d", output_dir,
        "--verbose",        # show more debug info
    ]

    if os.path.exists(cookie_file):
        cmd += ["--cookies", cookie_file]
    else:
        print(f"⚠️ Cookie file '{cookie_file}' not found. Login-required tweets will fail.")

    cmd.append(post_url)

    try:
        subprocess.run(cmd, check=True)
        print(f"\n✅ Download completed. Check the '{output_dir}' folder.")
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Download failed: {e}")

if __name__ == "__main__":
    url = "https://twitter.com/ninicherri/status/1976329843433500813"
    download_x_images(url)
