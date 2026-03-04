import re

def update_languages():
    filepath = "d:\\Project\\AfterDark\\resources\\languages.py"
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Update `get_user_language` to use `history_db`
    old_get_user_language = """    def get_user_language(self, user_id):
        \"\"\"Get user's preferred language (default: English)\"\"\"
        return self.user_languages.get(str(user_id), 'en')"""
        
    new_get_user_language = """    def get_user_language(self, user_id):
        \"\"\"Get user's preferred language (default: English)\"\"\"
        from core.database import history_db
        return history_db.get_setting(user_id, "bot_language", "en")"""
        
    content = content.replace(old_get_user_language, new_get_user_language)

    # 2. Update `get_language_keyboard` to highlight the selected language
    old_keyboard = """    def get_language_keyboard(self):
        \"\"\"Generate language selection keyboard\"\"\"
        from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        
        buttons = []
        row = []
        
        for code, name in self.LANGUAGES.items():
            row.append(InlineKeyboardButton(name, callback_data=f"lang_{code}"))
            
            # Two buttons per row
            if len(row) == 2:
                buttons.append(row)
                row = []
        
        # Add remaining button if any
        if row:
            buttons.append(row)
        
        # Add back button
        buttons.append([InlineKeyboardButton("🏠 Back", callback_data="settings")])
        
        return InlineKeyboardMarkup(buttons)"""

    new_keyboard = """    def get_language_keyboard(self, user_id=None):
        \"\"\"Generate language selection keyboard\"\"\"
        from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        from resources.themes import theme_manager
        
        theme = theme_manager.get_theme(user_id)
        current_lang = self.get_user_language(user_id) if user_id else 'en'
        
        buttons = []
        row = []
        
        for code, name in self.LANGUAGES.items():
            display_name = f"✅ {name}" if code == current_lang else name
            row.append(InlineKeyboardButton(display_name, callback_data=f"lang_{code}"))
            
            # Two buttons per row
            if len(row) == 2:
                buttons.append(row)
                row = []
        
        # Add remaining button if any
        if row:
            buttons.append(row)
        
        # Add back button
        buttons.append([InlineKeyboardButton(f"{theme.get('nav_prev', '🔙')} Back", callback_data="settings")])
        
        return InlineKeyboardMarkup(buttons)"""
        
    content = content.replace(old_keyboard, new_keyboard)
    
    # 3. Clean up the `__init__` which used to load JSON
    # It might look like:
    # def __init__(self):
    #     self.user_languages = {}
    init_pattern = r'(    def __init__\(self\):.*?)(?=\n    # Available languages)'
    content = re.sub(init_pattern, r'    def __init__(self):\n        """Initialize language manager"""\n        pass\n', content, flags=re.DOTALL)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

if __name__ == "__main__":
    update_languages()
