import os
import re

MAPPING = {
    "core.formatting.formatters": "core.formatting.formatters",
    "core.formatting.videy_formatter": "core.formatting.videy_formatter",
    "core.formatting.history_formatter": "core.formatting.history_formatter",
    "core.export.videy_exporter": "core.export.videy_exporter",
    "core.export.history_exporter": "core.export.history_exporter",
    "core.media.upload_logger": "core.media.upload_logger",
    "core.media.video_processor": "core.media.video_processor",
    "core.media.media_info": "core.media.media_info",
    "core.parsing.url_extractor": "core.parsing.url_extractor",
    "core.parsing.deep_link": "core.parsing.deep_link",
    "core.parsing.url_parser": "core.parsing.url_parser"
}

def update_file(filepath):
    if not filepath.endswith(".py"): return
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    
    original = content
    for old, new in MAPPING.items():
        # Match 'from utils.x import' and 'import utils.x' safely
        content = re.sub(rf'\b{old}\b', new, content)
        
    if content != original:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Updated {filepath}")

def main():
    for root, dirs, files in os.walk("."):
        if ".git" in root or "__pycache__" in root or "venv" in root:
            continue
        for file in files:
            update_file(os.path.join(root, file))

if __name__ == "__main__":
    main()
