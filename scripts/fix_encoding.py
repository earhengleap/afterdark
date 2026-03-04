import os

def fix_mojibake(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        return

    new_lines = []
    changed = False
    
    for line in content.splitlines(keepends=True):
        try:
            # Revert the double-encoding:
            # Encode what Python thinks is CP1252 back to bytes, then decode as UTF-8
            fixed_line = line.encode('cp1252').decode('utf-8')
            if fixed_line != line:
                new_lines.append(fixed_line)
                changed = True
            else:
                new_lines.append(line)
        except (UnicodeEncodeError, UnicodeDecodeError):
            # This line contains valid Unicode that is NOT mojibake (e.g. real emojis), 
            # so we leave it alone.
            new_lines.append(line)

    if changed:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("".join(new_lines))
        print(f"Fixed encoding in {filepath}")

def main():
    skip_dirs = {".git", "venv", "__pycache__", ".venv"}
    target_exts = {".py", ".json", ".md", ".txt", ".html", ".js", ".css"}
    
    for root, dirs, files in os.walk("."):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        for f in files:
            if any(f.endswith(ext) for ext in target_exts):
                fix_mojibake(os.path.join(root, f))

if __name__ == "__main__":
    main()
