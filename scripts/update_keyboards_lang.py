import re
import os

def update_keyboards():
    filepath = r"d:\Project\AfterDark\resources\keyboards.py"
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Add get_text import inside methods OR at the top if safely handled.
    # To avoid circularity, let's inject it inside each method that needs it.

    # 1. Main Menu
    old_main_menu = """    @staticmethod
    def main_menu(user_id=None):
        \"\"\"Main menu keyboard with primary actions\"\"\"
        theme = theme_manager.get_theme(user_id)
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"{theme.get('download', '📥')} Download Video", callback_data="download"),
                InlineKeyboardButton(f"🖼️ Download Images", callback_data="download_images")
            ],
            [
                InlineKeyboardButton(f"📦 Bulk Videos", callback_data="bulk_upload"),
                InlineKeyboardButton(f"📦 Bulk Images", callback_data="bulk_upload_images")
            ],
            [
                InlineKeyboardButton(f"🔍 Detect", callback_data="bulk_content"),
                InlineKeyboardButton(f"📥 Share", callback_data="get_share_link")
            ],
            [
                InlineKeyboardButton(f"📦 Bulk Queue", callback_data="bulk_queue")
            ],
            [
                InlineKeyboardButton(f"{theme.get('stats', '📊')} History", callback_data="history:1"),
                InlineKeyboardButton(f"{theme.get('stats', '📊')} Stats", callback_data="stats")
            ],
            [
                InlineKeyboardButton(f"🔗 Videy Links", callback_data="videy_links")
            ],
            [
                InlineKeyboardButton(f"{theme.get('settings', '⚙️')} Settings", callback_data="settings"),
                InlineKeyboardButton(f"❓ Help", callback_data="help")
            ]
        ])"""

    new_main_menu = """    @staticmethod
    def main_menu(user_id=None):
        \"\"\"Main menu keyboard with primary actions\"\"\"
        from resources.languages import get_text
        theme = theme_manager.get_theme(user_id)
        
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"{theme.get('download', '📥')} {get_text(user_id, 'download_video', 'Download Video')}", callback_data="download"),
                InlineKeyboardButton(f"🖼️ {get_text(user_id, 'download_images', 'Download Images')}", callback_data="download_images")
            ],
            [
                InlineKeyboardButton(f"📦 {get_text(user_id, 'bulk_videos', 'Bulk Videos')}", callback_data="bulk_upload"),
                InlineKeyboardButton(f"📦 {get_text(user_id, 'bulk_images', 'Bulk Images')}", callback_data="bulk_upload_images")
            ],
            [
                InlineKeyboardButton(f"🔍 {get_text(user_id, 'detect', 'Detect')}", callback_data="bulk_content"),
                InlineKeyboardButton(f"📥 {get_text(user_id, 'share', 'Share')}", callback_data="get_share_link")
            ],
            [
                InlineKeyboardButton(f"📦 {get_text(user_id, 'bulk_queue', 'Bulk Queue')}", callback_data="bulk_queue")
            ],
            [
                InlineKeyboardButton(f"{theme.get('stats', '📊')} {get_text(user_id, 'history', 'History')}", callback_data="history:1"),
                InlineKeyboardButton(f"{theme.get('stats', '📊')} {get_text(user_id, 'stats', 'Stats')}", callback_data="stats")
            ],
            [
                InlineKeyboardButton(f"🔗 {get_text(user_id, 'videy_links', 'Videy Links')}", callback_data="videy_links")
            ],
            [
                InlineKeyboardButton(f"{theme.get('settings', '⚙️')} {get_text(user_id, 'settings', 'Settings')}", callback_data="settings"),
                InlineKeyboardButton(f"❓ {get_text(user_id, 'help', 'Help')}", callback_data="help")
            ]
        ])"""

    content = content.replace(old_main_menu, new_main_menu)

    # 2. Settings Menu
    old_settings = """    @staticmethod
    def settings_menu(notifications_enabled: bool = True, user_id=None):
        \"\"\"Settings menu keyboard\"\"\"
        theme = theme_manager.get_theme(user_id)
        notif_label = "🔔 Notifications: ON" if notifications_enabled else "🔕 Notifications: OFF"
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton(notif_label, callback_data="settings_notifications"),
                InlineKeyboardButton(f"{theme.get('settings', '⚙️')} Theme", callback_data="settings_theme")
            ],
            [
                InlineKeyboardButton(f"📁 Storage", callback_data="settings_storage"),
                InlineKeyboardButton(f"🌐 Language", callback_data="settings_language")
            ],
            [
                InlineKeyboardButton(f"{theme.get('home', '🏠')} Main Menu", callback_data="main_menu")
            ]
        ])"""

    new_settings = """    @staticmethod
    def settings_menu(notifications_enabled: bool = True, user_id=None):
        \"\"\"Settings menu keyboard\"\"\"
        from resources.languages import get_text
        theme = theme_manager.get_theme(user_id)
        
        notif_key = 'notifications_on' if notifications_enabled else 'notifications_off'
        notif_label = f"🔔 {get_text(user_id, notif_key, 'Notifications: ON' if notifications_enabled else 'Notifications: OFF')}"
        
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton(notif_label, callback_data="settings_notifications"),
                InlineKeyboardButton(f"{theme.get('settings', '⚙️')} {get_text(user_id, 'theme', 'Theme')}", callback_data="settings_theme")
            ],
            [
                InlineKeyboardButton(f"📁 {get_text(user_id, 'storage', 'Storage')}", callback_data="settings_storage"),
                InlineKeyboardButton(f"🌐 {get_text(user_id, 'language', 'Language')}", callback_data="settings_language")
            ],
            [
                InlineKeyboardButton(f"{theme.get('home', '🏠')} {get_text(user_id, 'main_menu', 'Main Menu')}", callback_data="main_menu")
            ]
        ])"""

    content = content.replace(old_settings, new_settings)

    # 3. Back to Main
    old_back = """    @staticmethod
    def back_to_main(user_id=None):
        \"\"\"Simple back button to return to main menu\"\"\"
        theme = theme_manager.get_theme(user_id)
        return InlineKeyboardMarkup([
            [InlineKeyboardButton(f"{theme.get('home', '🏠')} Back to Home", callback_data="main_menu")]
        ])"""

    new_back = """    @staticmethod
    def back_to_main(user_id=None):
        \"\"\"Simple back button to return to main menu\"\"\"
        from resources.languages import get_text
        theme = theme_manager.get_theme(user_id)
        return InlineKeyboardMarkup([
            [InlineKeyboardButton(f"{theme.get('home', '🏠')} {get_text(user_id, 'back_to_home', 'Back to Home')}", callback_data="main_menu")]
        ])"""

    content = content.replace(old_back, new_back)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

if __name__ == "__main__":
    update_keyboards()
