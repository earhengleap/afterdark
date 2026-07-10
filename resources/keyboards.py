"""
UI Keyboards Module
Contains all inline keyboard layouts for the bot
"""

from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from resources.themes import theme_manager


class Keyboards:
    """Dynamic keyboard layouts for the bot"""
    
    @staticmethod
    def main_menu(user_id=None):
        """Main menu keyboard with primary actions"""
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
        ])
    
    @staticmethod
    def back_to_main(user_id=None):
        """Simple back button to return to main menu"""
        from resources.languages import get_text
        theme = theme_manager.get_theme(user_id)
        return InlineKeyboardMarkup([
            [InlineKeyboardButton(f"{theme.get('home', '🏠')} {get_text(user_id, 'back_to_home', 'Back to Home')}", callback_data="main_menu")]
        ])
    
    @staticmethod
    def cancel_button(user_id=None):
        """Cancel button for active operations"""
        from resources.languages import get_text
        return InlineKeyboardMarkup([
            [InlineKeyboardButton(f"❌ {get_text(user_id, 'cancel', 'Cancel')}", callback_data="cancel")]
        ])
    
    @staticmethod
    def settings_menu(notifications_enabled: bool = True, user_id=None):
        """Settings menu keyboard"""
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
        ])
    

    @staticmethod
    def theme_selection_menu(current_theme_name: str, user_id=None):
        """Menu for selecting the bot theme"""
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
    @staticmethod
    def bulk_queue_menu(queue_count: int, is_bulk_mode: bool, user_id=None):
        """Menu for managing bulk download queue"""
        from resources.languages import get_text
        theme = theme_manager.get_theme(user_id)
        
        # Status indicator
        mode_text = f"🟢 {get_text(user_id, 'enabled', 'Enabled')}" if is_bulk_mode else f"🔴 {get_text(user_id, 'disabled', 'Disabled')}"
        mode_action = "disable" if is_bulk_mode else "enable"
        
        # Process button only active if items in queue
        if queue_count > 0:
            process_text = f"🚀 {get_text(user_id, 'process_queue', 'Process Queue')} ({queue_count})"
            process_data = "process_queue"
        else:
            process_text = f"{get_text(user_id, 'process_queue_empty', 'Process Queue (Empty)')}"
            process_data = "ignore"
        
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"{get_text(user_id, 'bulk_mode', 'Bulk Mode')}: {mode_text}", callback_data=f"toggle_bulk:{mode_action}")
            ],
            [
                InlineKeyboardButton(process_text, callback_data=process_data)
            ],
            [
                InlineKeyboardButton(f"🗑️ {get_text(user_id, 'clear_queue', 'Clear Queue')}", callback_data="clear_queue"),
                InlineKeyboardButton(f"🔃 {get_text(user_id, 'refresh', 'Refresh')}", callback_data="bulk_queue")
            ],
            [
                InlineKeyboardButton(f"{theme.get('home', '🏠')} {get_text(user_id, 'back_to_home', 'Back to Home')}", callback_data="main_menu")
            ]
        ])
    
    @staticmethod
    def download_options(user_id=None):
        """Quality selection keyboard for downloads"""
        from resources.languages import get_text
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"🎬 {get_text(user_id, 'best_quality', 'Best Quality')}", callback_data="quality_best"),
                InlineKeyboardButton(f"⚡ {get_text(user_id, 'fast_download', 'Fast Download')}", callback_data="quality_fast")
            ],
            [
                InlineKeyboardButton(f"❌ {get_text(user_id, 'cancel', 'Cancel')}", callback_data="cancel")
            ]
        ])
    
    @staticmethod
    def video_actions(video_id, user_id=None):
        """Actions available after video download"""
        from resources.languages import get_text
        theme = theme_manager.get_theme(user_id)
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"📥 {get_text(user_id, 'download_another', 'Download Another')}", callback_data="download"),
                InlineKeyboardButton(f"{theme.get('home', '🏠')} {get_text(user_id, 'main_menu', 'Main Menu')}", callback_data="main_menu")
            ]
        ])
    
    @staticmethod
    def video_actions_with_upload(user_id):
        """Actions available after video download with upload option"""
        from resources.languages import get_text
        theme = theme_manager.get_theme(user_id)
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"🚀 {get_text(user_id, 'send_to_group', 'Send to Telegram Group')}", callback_data=f"upload_to_group_{user_id}")
            ],
            [
                InlineKeyboardButton(f"🔄 {get_text(user_id, 'new_download', 'New Download')}", callback_data="download"),
                InlineKeyboardButton(f"{theme.get('home', '🏠')} {get_text(user_id, 'main_menu', 'Main Menu')}", callback_data="main_menu")
            ]
        ])
    
    @staticmethod
    def image_actions_with_upload(user_id):
        """Actions available after image download with upload option"""
        from resources.languages import get_text
        theme = theme_manager.get_theme(user_id)
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"🚀 {get_text(user_id, 'send_to_group', 'Send to Telegram Group')}", callback_data=f"upload_images_to_group_{user_id}")
            ],
            [
                InlineKeyboardButton(f"🔄 {get_text(user_id, 'new_download', 'New Download')}", callback_data="download_images"),
                InlineKeyboardButton(f"{theme.get('home', '🏠')} {get_text(user_id, 'main_menu', 'Main Menu')}", callback_data="main_menu")
            ]
        ])
    
    @staticmethod
    def confirmation(action, user_id=None):
        """Generic confirmation keyboard"""
        from resources.languages import get_text
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"✅ {get_text(user_id, 'yes', 'Yes')}", callback_data=f"confirm_{action}"),
                InlineKeyboardButton(f"❌ {get_text(user_id, 'no', 'No')}", callback_data=f"cancel_{action}")
            ]
        ])
    
    @staticmethod
    def social_links(user_id=None):
        """Social media and support links"""
        from resources.languages import get_text
        theme = theme_manager.get_theme(user_id)
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"💬 {get_text(user_id, 'support_channel', 'Support Channel')}", url="https://t.me/your_channel"),
                InlineKeyboardButton(f"👥 {get_text(user_id, 'community', 'Community')}", url="https://t.me/your_group")
            ],
            [
                InlineKeyboardButton(f"⭐ {get_text(user_id, 'rate_us', 'Rate Us')}", url="https://t.me/your_bot?start=rate"),
                InlineKeyboardButton(f"🐛 {get_text(user_id, 'report_bug', 'Report Bug')}", callback_data="report_bug")
            ],
            [
                InlineKeyboardButton(f"{theme.get('home', '🏠')} {get_text(user_id, 'main_menu', 'Main Menu')}", callback_data="main_menu")
            ]
        ])
    
    @staticmethod
    def bulk_download_complete(user_id, downloaded_paths):
        """Keyboard shown after bulk download completes"""
        from resources.languages import get_text
        theme = theme_manager.get_theme(user_id)
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"📤 {get_text(user_id, 'upload_all', 'Upload All to Group')}", callback_data="upload_bulk_downloaded")
            ],
            [
                InlineKeyboardButton(f"📥 {get_text(user_id, 'download_more', 'Download More')}", callback_data="download"),
                InlineKeyboardButton(f"📊 {get_text(user_id, 'view_all_videos', 'View All Videos')}", callback_data="bulk_upload")
            ],
            [
                InlineKeyboardButton(f"{theme.get('home', '🏠')} {get_text(user_id, 'main_menu', 'Main Menu')}", callback_data="main_menu")
            ]
        ])
    
    @staticmethod
    def bulk_image_download_complete(user_id, downloaded_paths):
        """Keyboard shown after bulk image download completes"""
        from resources.languages import get_text
        theme = theme_manager.get_theme(user_id)
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"📤 {get_text(user_id, 'upload_all_images', 'Upload All Images to Group')}", callback_data="upload_bulk_images_downloaded")
            ],
            [
                InlineKeyboardButton(f"🖼️ {get_text(user_id, 'download_more_images', 'Download More Images')}", callback_data="download_images"),
                InlineKeyboardButton(f"🖼️ {get_text(user_id, 'view_all_images', 'View All Images')}", callback_data="bulk_upload_images")
            ],
            [
                InlineKeyboardButton(f"{theme.get('home', '🏠')} {get_text(user_id, 'main_menu', 'Main Menu')}", callback_data="main_menu")
            ]
        ])
    
    # -------------------- FIXED --------------------
    @staticmethod
    def video_list_keyboard(videos, selected_indices, page=0, per_page=5, user_id=None):
        """
        Inline keyboard for selecting multiple videos for bulk upload.
        videos: list of dicts with 'filename'
        selected_indices: set of video indices already selected
        page: current page number (pagination)
        per_page: number of videos per page
        """
        from resources.languages import get_text
        theme = theme_manager.get_theme(user_id)
        
        start = page * per_page
        end = start + per_page
        page_videos = videos[start:end]

        buttons = []

        # Add video buttons with selection checkbox
        for idx, v in enumerate(page_videos, start=start):
            filename = v["filename"]
            display_name = filename if len(filename) <= 35 else filename[:32] + "..."
            checked = "✅" if idx in selected_indices else "⬜"
            buttons.append([InlineKeyboardButton(
                f"{checked} {display_name}", 
                callback_data=f"sel_{idx}"
            )])

        # Pagination buttons
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton(f"{theme.get('nav_prev', '⬅️')} {get_text(user_id, 'prev', 'Prev')}", callback_data=f"pg_{page-1}"))
        if end < len(videos):
            nav_buttons.append(InlineKeyboardButton(f"{get_text(user_id, 'next', 'Next')} {theme.get('nav_next', '➡️')}", callback_data=f"pg_{page+1}"))
        if nav_buttons:
            buttons.append(nav_buttons)

        # Select / Deselect all + Confirm
        buttons.append([
            InlineKeyboardButton(f"✅ {get_text(user_id, 'select_all', 'Select All')}", callback_data="sel_all"),
            InlineKeyboardButton(f"❌ {get_text(user_id, 'deselect_all', 'Deselect All')}", callback_data="desel_all")
        ])
        buttons.append([
            InlineKeyboardButton(f"📤 {get_text(user_id, 'confirm_upload', 'Confirm Upload')}", callback_data="confirm_upload")
        ])
        buttons.append([
            InlineKeyboardButton(f"{theme.get('home', '🏠')} {get_text(user_id, 'back', 'Back')}", callback_data="main_menu")
        ])

        return InlineKeyboardMarkup(buttons)
    
    @staticmethod
    def image_list_keyboard(images, selected_indices, page=0, per_page=5, user_id=None):
        """
        Inline keyboard for selecting multiple images for bulk upload.
        images: list of dicts with 'filename'
        selected_indices: set of image indices already selected
        page: current page number (pagination)
        per_page: number of images per page
        """
        from resources.languages import get_text
        theme = theme_manager.get_theme(user_id)
        
        start = page * per_page
        end = start + per_page
        page_images = images[start:end]

        buttons = []

        # Add image buttons with selection checkbox
        for idx, img in enumerate(page_images, start=start):
            filename = img["filename"]
            display_name = filename if len(filename) <= 35 else filename[:32] + "..."
            checked = "✅" if idx in selected_indices else "⬜"
            buttons.append([InlineKeyboardButton(
                f"{checked} {display_name}", 
                callback_data=f"img_sel_{idx}"
            )])

        # Pagination buttons
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton(f"{theme.get('nav_prev', '⬅️')} {get_text(user_id, 'prev', 'Prev')}", callback_data=f"img_pg_{page-1}"))
        if end < len(images):
            nav_buttons.append(InlineKeyboardButton(f"{get_text(user_id, 'next', 'Next')} {theme.get('nav_next', '➡️')}", callback_data=f"img_pg_{page+1}"))
        if nav_buttons:
            buttons.append(nav_buttons)

        # Select / Deselect all + Confirm
        buttons.append([
            InlineKeyboardButton(f"✅ {get_text(user_id, 'select_all_images', 'Select All Images')}", callback_data="img_sel_all"),
            InlineKeyboardButton(f"❌ {get_text(user_id, 'deselect_all_images', 'Deselect All Images')}", callback_data="img_desel_all")
        ])
        buttons.append([
            InlineKeyboardButton(f"📤 {get_text(user_id, 'confirm_image_upload', 'Confirm Image Upload')}", callback_data="confirm_image_upload")
        ])
        buttons.append([
            InlineKeyboardButton(f"{theme.get('home', '🏠')} {get_text(user_id, 'back', 'Back')}", callback_data="main_menu")
        ])

        return InlineKeyboardMarkup(buttons)
    
    @staticmethod
    def single_video_upload(video_key, user_id=None):
        """Single video upload button."""
        from resources.languages import get_text
        return InlineKeyboardMarkup([
            [InlineKeyboardButton(f"📤 {get_text(user_id, 'upload_to_group', 'Upload to Group')}", callback_data=f"upload_single_{video_key}")]
        ])
    
    @staticmethod
    def single_image_upload(image_key, user_id=None):
        """Single image upload button with short callback data"""
        from resources.languages import get_text
        return InlineKeyboardMarkup([
            [InlineKeyboardButton(f"📤 {get_text(user_id, 'upload_to_group', 'Upload to Group')}", callback_data=f"up_img_{image_key}")]
        ])
    @staticmethod
    def bulk_download_complete_mixed(user_id, video_paths, image_paths):
        """Keyboard shown after mixed bulk download completes"""
        from resources.languages import get_text
        theme = theme_manager.get_theme(user_id)
        buttons = []
        
        if video_paths:
            buttons.append([InlineKeyboardButton(f"📤 {get_text(user_id, 'upload_all_videos', 'Upload All Videos to Group')}", callback_data="upload_bulk_videos_downloaded")])
        
        if image_paths:
            buttons.append([InlineKeyboardButton(f"📤 {get_text(user_id, 'upload_all_images', 'Upload All Images to Group')}", callback_data="upload_bulk_images_downloaded")])
        
        if video_paths or image_paths:
            buttons.append([InlineKeyboardButton(f"📤 {get_text(user_id, 'upload_all_content', 'Upload All Content to Group')}", callback_data="upload_bulk_all_downloaded")])
        
        buttons.extend([
            [
                InlineKeyboardButton(f"📥 {get_text(user_id, 'download_more', 'Download More')}", callback_data="download"),
                InlineKeyboardButton(f"📊 {get_text(user_id, 'view_all_videos', 'View All Videos')}", callback_data="bulk_upload")
            ],
            [
                InlineKeyboardButton(f"🖼️ {get_text(user_id, 'view_all_images', 'View All Images')}", callback_data="bulk_upload_images")
            ],
            [
                InlineKeyboardButton(f"{theme.get('home', '🏠')} {get_text(user_id, 'main_menu', 'Main Menu')}", callback_data="main_menu")
            ]
        ])

        return InlineKeyboardMarkup(buttons)
    
    @staticmethod
    def history_pagination(current_page: int, total_pages: int, user_id=None):
        """History view pagination keyboard"""
        from resources.languages import get_text
        theme = theme_manager.get_theme(user_id)
        buttons = []
        
        # Navigation buttons
        nav_row = []
        if current_page > 1:
            nav_row.append(InlineKeyboardButton(f"{theme.get('nav_prev', '⬅️')} {get_text(user_id, 'prev', 'Prev')}", callback_data=f"history:{current_page-1}"))
        if current_page < total_pages:
            nav_row.append(InlineKeyboardButton(f"{get_text(user_id, 'next', 'Next')} {theme.get('nav_next', '➡️')}", callback_data=f"history:{current_page+1}"))
        
        if nav_row:
            buttons.append(nav_row)
        
        # Action buttons
        buttons.append([
            InlineKeyboardButton(f"📊 {get_text(user_id, 'export', 'Export')}", callback_data="history:export"),
            InlineKeyboardButton(f"🗑️ {get_text(user_id, 'clear', 'Clear')}", callback_data="history:clear")
        ])
        
        # Back button
        buttons.append([InlineKeyboardButton(f"{theme.get('nav_prev', '🔙')} {get_text(user_id, 'back_to_menu', 'Back to Menu')}", callback_data="main_menu")])
        
        return InlineKeyboardMarkup(buttons)

    @staticmethod
    def videy_pagination(current_page: int, total_pages: int, user_id=None):
        """Videy links pagination keyboard (read-only list + export)."""
        from resources.languages import get_text
        theme = theme_manager.get_theme(user_id)
        buttons = []

        nav_row = []
        if current_page > 1:
            nav_row.append(InlineKeyboardButton(f"{theme.get('nav_prev', '⬅️')} {get_text(user_id, 'prev', 'Prev')}", callback_data=f"videy:{current_page-1}"))
        if current_page < total_pages:
            nav_row.append(InlineKeyboardButton(f"{get_text(user_id, 'next', 'Next')} {theme.get('nav_next', '➡️')}", callback_data=f"videy:{current_page+1}"))
        if nav_row:
            buttons.append(nav_row)

        buttons.append([InlineKeyboardButton(f"📊 {get_text(user_id, 'export', 'Export')}", callback_data="videy:export")])
        buttons.append([InlineKeyboardButton(f"{theme.get('nav_prev', '🔙')} {get_text(user_id, 'back_to_menu', 'Back to Menu')}", callback_data="main_menu")])
        return InlineKeyboardMarkup(buttons)

    @staticmethod
    def videy_export_format_selection(user_id=None):
        """Videy export format selection keyboard."""
        from resources.languages import get_text
        theme = theme_manager.get_theme(user_id)
        return InlineKeyboardMarkup([
            [InlineKeyboardButton(f"📊 {get_text(user_id, 'export_csv', 'CSV (Excel)')}", callback_data="videy_export:csv")],
            [InlineKeyboardButton(f"📄 {get_text(user_id, 'export_txt', 'Text File')}", callback_data="videy_export:txt")],
            [InlineKeyboardButton(f"{theme.get('nav_prev', '🔙')} {get_text(user_id, 'cancel', 'Cancel')}", callback_data="videy:1")]
        ])
    
    @staticmethod
    def export_format_selection(user_id=None):
        """Export format selection keyboard"""
        from resources.languages import get_text
        theme = theme_manager.get_theme(user_id)
        return InlineKeyboardMarkup([
            [InlineKeyboardButton(f"📊 {get_text(user_id, 'export_csv', 'CSV (Excel)')}", callback_data="export:csv")],
            [InlineKeyboardButton(f"📄 {get_text(user_id, 'export_txt', 'Text File')}", callback_data="export:txt")],
            [InlineKeyboardButton(f"{theme.get('nav_prev', '🔙')} {get_text(user_id, 'cancel', 'Cancel')}", callback_data="history:1")]
        ])
    
    @staticmethod
    def clear_history_confirmation(user_id=None):
        """Confirm clearing history"""
        from resources.languages import get_text
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"✅ {get_text(user_id, 'confirm_clear', 'Yes, Clear All')}", callback_data="history:clear:confirm"),
                InlineKeyboardButton(f"❌ {get_text(user_id, 'cancel', 'Cancel')}", callback_data="history:1")
            ]
        ])
    @staticmethod
    def cleanup_menu(user_id=None, min_age_days: int = 7):
        """Keyboard for /cleanup storage management screen."""
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    f"🔄 Refresh Report",
                    callback_data="cleanup:scan"
                )
            ],
            [
                InlineKeyboardButton(
                    f"♻️ Delete Files Older Than {min_age_days}d",
                    callback_data="cleanup:confirm"
                )
            ],
            [
                InlineKeyboardButton(
                    "🏠 Main Menu",
                    callback_data="main_menu"
                )
            ]
        ])

    @staticmethod
    def cleanup_confirm(user_id=None, min_age_days: int = 7):
        """Confirmation keyboard before actually deleting old media files."""
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    f"✅ Yes, Delete Files Older Than {min_age_days}d",
                    callback_data="cleanup:delete"
                )
            ],
            [
                InlineKeyboardButton(
                    "❌ Cancel",
                    callback_data="cleanup:scan"
                )
            ]
        ])
