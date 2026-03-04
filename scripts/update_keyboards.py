import re

def rewrite_keyboards():
    filepath = "d:\\Project\\AfterDark\\resources\\keyboards.py"
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Add import
    if "from resources.themes import theme_manager" not in content:
        content = content.replace(
            "from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton\n",
            "from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton\nfrom resources.themes import theme_manager\n"
        )

    # 1. Update main_menu definition
    content = content.replace(
        "def main_menu():",
        "def main_menu(user_id=None):"
    )

    # Inject theme = theme_manager.get_theme(user_id) into main_menu
    pattern_main = r'(    def main_menu\(user_id=None\):\n        \"\"\"Main menu keyboard with primary actions\"\"\"\n)'
    def replacer_main(m):
        return m.group(1) + "        theme = theme_manager.get_theme(user_id)\n"
    content = re.sub(pattern_main, replacer_main, content)

    # Replace hardcoded emojis in main_menu
    content = content.replace('"🎬 Download Video"', 'f"{theme.get(\'download\', \'📥\')} Download Video"')
    content = content.replace('"🖼️ Download Images"', 'f"🖼️ Download Images"')
    content = content.replace('"📦 Bulk Videos"', 'f"📦 Bulk Videos"')
    content = content.replace('"📦 Bulk Images"', 'f"📦 Bulk Images"')
    content = content.replace('"🔍 Detect"', 'f"🔍 Detect"')
    content = content.replace('"📥 Share"', 'f"📥 Share"')
    content = content.replace('"📦 Bulk Queue"', 'f"📦 Bulk Queue"')
    content = content.replace('"📜 History"', 'f"{theme.get(\'stats\', \'📊\')} History"')
    content = content.replace('"📊 Stats"', 'f"{theme.get(\'stats\', \'📊\')} Stats"')
    content = content.replace('"🔗 Videy Links"', 'f"🔗 Videy Links"')
    content = content.replace('"⚙️ Settings"', 'f"{theme.get(\'settings\', \'⚙️\')} Settings"')
    content = content.replace('"❓ Help"', 'f"❓ Help"')


    # 2. Update settings_menu definition
    content = content.replace(
        "def settings_menu(notifications_enabled: bool = True):",
        "def settings_menu(notifications_enabled: bool = True, user_id=None):"
    )

    pattern_settings = r'(    def settings_menu\(notifications_enabled: bool = True, user_id=None\):\n        \"\"\"Settings menu keyboard\"\"\"\n)'
    def replacer_settings(m):
        return m.group(1) + "        theme = theme_manager.get_theme(user_id)\n"
    content = re.sub(pattern_settings, replacer_settings, content)

    # Replace hardcoded emojis in settings_menu
    content = content.replace('"🎨 Theme"', 'f"{theme.get(\'settings\', \'⚙️\')} Theme"')
    content = content.replace('"📁 Storage"', 'f"📁 Storage"')
    content = content.replace('"🌐 Language"', 'f"🌐 Language"')
    content = content.replace('"🏠 Main Menu"', 'f"{theme.get(\'home\', \'🏠\')} Main Menu"')
    
    # Also replace back_to_main button
    content = content.replace(
        "def back_to_main():\n        \"\"\"Simple back button to return to main menu\"\"\"\n        return InlineKeyboardMarkup([\n            [InlineKeyboardButton(\"🔙 Back to Home\", callback_data=\"main_menu\")]\n        ])",
        "def back_to_main(user_id=None):\n        \"\"\"Simple back button to return to main menu\"\"\"\n        theme = theme_manager.get_theme(user_id)\n        return InlineKeyboardMarkup([\n            [InlineKeyboardButton(f\"{theme.get('home', '🏠')} Back to Home\", callback_data=\"main_menu\")]\n        ])"
    )

    # 3. Add theme_selection_menu
    custom_menu = """
    @staticmethod
    def theme_selection_menu(current_theme_name: str, user_id=None):
        \"\"\"Menu for selecting the bot theme\"\"\"
        theme = theme_manager.get_theme(user_id)
        buttons = []
        for key, details in theme_manager.THEMES.items():
            name = details['name']
            if key == current_theme_name:
                name = f"✅ {name}"
                
            buttons.append([InlineKeyboardButton(name, callback_data=f"set_theme:{key}")])
            
        buttons.append([InlineKeyboardButton(f"{theme.get('nav_prev', '🔙')} Back", callback_data="settings")])
        buttons.append([InlineKeyboardButton(f"{theme.get('home', '🏠')} Main Menu", callback_data="main_menu")])
        
        return InlineKeyboardMarkup(buttons)
"""
    # Insert custom_menu before bulk_queue_menu
    if "def theme_selection_menu" not in content:
        content = content.replace(
            "    @staticmethod\n    def bulk_queue_menu",
            custom_menu + "    @staticmethod\n    def bulk_queue_menu"
        )

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

if __name__ == "__main__":
    rewrite_keyboards()
