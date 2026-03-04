import re

def update_messages():
    filepath = "d:\\Project\\AfterDark\\resources\\messages.py"
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
        
    if "from resources.themes import theme_manager" not in content:
        content = content.replace(
            "from datetime import datetime\n",
            "from datetime import datetime\nfrom resources.themes import theme_manager\n"
        )
            
    # Regex to match method definitions up to the end of the docstring.
    # We will compute the indentation of the method block so we can inject `theme = theme_manager...` exactly inline.
    
    def replacer(match):
        method_def = match.group(1)
        # Find the indentation of the `def `
        lines = method_def.split('\n')
        for line in lines:
            if 'def ' in line:
                indent = line[:len(line) - len(line.lstrip())]
                break
        
        # Inject at the very end of the matched string (which includes the docstring)
        # We need an extra 4 spaces for the inside block.
        inside_indent = indent + "    "
        return method_def + f"\n{inside_indent}theme = theme_manager.get_theme(user_id)\n"
    
    # Matches `    @staticmethod\n    def xyz(..., user_id=None):\n        """..."""`
    pattern = r'(    @staticmethod\n    def [a-zA-Z0-9_]+\(.*?(?:user_id=None|user_id).*?\):\n(?:        \"\"\"[^\"]*\"\"\"\n)?)'
    
    replaced = re.sub(pattern, replacer, content, flags=re.DOTALL)
    
    # Now replace {Messages.LOGO} -> {theme.get('logo', '🎬')}
    mappings = {
        'Messages.LOGO': "theme.get('logo', '🎬')",
        'Messages.SUCCESS': "theme.get('success', '✅')",
        'Messages.ERROR': "theme.get('error', '❌')",
        'Messages.WARNING': "theme.get('warning', '⚠️')",
        'Messages.INFO': "theme.get('info', 'ℹ️')",
        'Messages.DOWNLOAD': "theme.get('download', '📥')",
        'Messages.UPLOAD': "theme.get('upload', '📤')",
        'Messages.STATS': "theme.get('stats', '📊')",
        'Messages.SETTINGS': "theme.get('settings', '⚙️')"
    }
    
    for old, new in mappings.items():
        replaced = replaced.replace(f"{{{old}}}", f"{{{new}}}")
        
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(replaced)

if __name__ == "__main__":
    update_messages()
