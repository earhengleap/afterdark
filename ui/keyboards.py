"""
UI Keyboards Module
Contains all inline keyboard layouts for the bot
"""

from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton


class Keyboards:
    """Dynamic keyboard layouts for the bot"""
    
    @staticmethod
    def main_menu():
        """Main menu keyboard with primary actions"""
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🎬 Download Video", callback_data="download"),
                InlineKeyboardButton("🖼️ Download Images", callback_data="download_images")
            ],
            [
                InlineKeyboardButton("📦 Bulk Videos", callback_data="bulk_upload"),
                InlineKeyboardButton("📦 Bulk Images", callback_data="bulk_upload_images")
            ],
            [
                InlineKeyboardButton("🔍 Bulk Content Detection", callback_data="bulk_content")
            ],
            [
                InlineKeyboardButton("📤 Share to Bot", callback_data="get_share_link")
            ],
            [
                InlineKeyboardButton("📜 History", callback_data="history:1"),
                InlineKeyboardButton("📊 Stats", callback_data="stats")
            ],
            [
                InlineKeyboardButton("⚙️ Settings", callback_data="settings"),
                InlineKeyboardButton("❓ Help", callback_data="help")
            ]
        ])
    
    @staticmethod
    def back_to_main():
        """Simple back button to return to main menu"""
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back to Home", callback_data="main_menu")]
        ])
    
    @staticmethod
    def cancel_button():
        """Cancel button for active operations"""
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]
        ])
    
    @staticmethod
    def settings_menu():
        """Settings menu keyboard"""
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🔔 Notifications", callback_data="settings_notifications"),
                InlineKeyboardButton("🎨 Theme", callback_data="settings_theme")
            ],
            [
                InlineKeyboardButton("📁 Storage", callback_data="settings_storage"),
                InlineKeyboardButton("🌐 Language", callback_data="settings_language")
            ],
            [
                InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")
            ]
        ])
    
    @staticmethod
    def download_options():
        """Quality selection keyboard for downloads"""
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🎬 Best Quality", callback_data="quality_best"),
                InlineKeyboardButton("⚡ Fast Download", callback_data="quality_fast")
            ],
            [
                InlineKeyboardButton("❌ Cancel", callback_data="cancel")
            ]
        ])
    
    @staticmethod
    def video_actions(video_id):
        """Actions available after video download"""
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📥 Download Another", callback_data="download"),
                InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")
            ]
        ])
    
    @staticmethod
    def video_actions_with_upload(user_id):
        """Actions available after video download with upload option"""
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🚀 Send to Telegram Group", callback_data=f"upload_to_group_{user_id}")
            ],
            [
                InlineKeyboardButton("🔄 New Download", callback_data="download"),
                InlineKeyboardButton("🏠 Home", callback_data="main_menu")
            ]
        ])
    
    @staticmethod
    def image_actions_with_upload(user_id):
        """Actions available after image download with upload option"""
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🚀 Send to Telegram Group", callback_data=f"upload_images_to_group_{user_id}")
            ],
            [
                InlineKeyboardButton("🔄 New Download", callback_data="download_images"),
                InlineKeyboardButton("🏠 Home", callback_data="main_menu")
            ]
        ])
    
    @staticmethod
    def confirmation(action):
        """Generic confirmation keyboard"""
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Yes", callback_data=f"confirm_{action}"),
                InlineKeyboardButton("❌ No", callback_data=f"cancel_{action}")
            ]
        ])
    
    @staticmethod
    def social_links():
        """Social media and support links"""
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton("💬 Support Channel", url="https://t.me/your_channel"),
                InlineKeyboardButton("👥 Community", url="https://t.me/your_group")
            ],
            [
                InlineKeyboardButton("⭐ Rate Us", url="https://t.me/your_bot?start=rate"),
                InlineKeyboardButton("🐛 Report Bug", callback_data="report_bug")
            ],
            [
                InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")
            ]
        ])
    
    @staticmethod
    def bulk_download_complete(user_id, downloaded_paths):
        """Keyboard shown after bulk download completes"""
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📤 Upload All to Group", callback_data="upload_bulk_downloaded")
            ],
            [
                InlineKeyboardButton("📥 Download More", callback_data="download"),
                InlineKeyboardButton("📊 View All Videos", callback_data="bulk_upload")
            ],
            [
                InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")
            ]
        ])
    
    @staticmethod
    def bulk_image_download_complete(user_id, downloaded_paths):
        """Keyboard shown after bulk image download completes"""
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📤 Upload All Images to Group", callback_data="upload_bulk_images_downloaded")
            ],
            [
                InlineKeyboardButton("🖼️ Download More Images", callback_data="download_images"),
                InlineKeyboardButton("🖼️ View All Images", callback_data="bulk_upload_images")
            ],
            [
                InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")
            ]
        ])
    
    # -------------------- FIXED --------------------
    @staticmethod
    def video_list_keyboard(videos, selected_indices, page=0, per_page=5):
        """
        Inline keyboard for selecting multiple videos for bulk upload.
        videos: list of dicts with 'filename'
        selected_indices: set of video indices already selected
        page: current page number (pagination)
        per_page: number of videos per page
        """
        start = page * per_page
        end = start + per_page
        page_videos = videos[start:end]

        buttons = []

        # Add video buttons with selection checkbox (using INDEX instead of filename)
        for idx, v in enumerate(page_videos, start=start):
            filename = v["filename"]
            # Truncate filename for display
            display_name = filename if len(filename) <= 35 else filename[:32] + "..."
            checked = "✅" if idx in selected_indices else "⬜"
            # Use index instead of filename in callback_data
            buttons.append([InlineKeyboardButton(
                f"{checked} {display_name}", 
                callback_data=f"sel_{idx}"
            )])

        # Pagination buttons
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"pg_{page-1}"))
        if end < len(videos):
            nav_buttons.append(InlineKeyboardButton("➡️ Next", callback_data=f"pg_{page+1}"))
        if nav_buttons:
            buttons.append(nav_buttons)

        # Select / Deselect all + Confirm
        buttons.append([
            InlineKeyboardButton("✅ Select All", callback_data="sel_all"),
            InlineKeyboardButton("❌ Deselect All", callback_data="desel_all")
        ])
        buttons.append([
            InlineKeyboardButton("📤 Confirm Upload", callback_data="confirm_upload")
        ])
        buttons.append([
            InlineKeyboardButton("🏠 Back", callback_data="main_menu")
        ])

        return InlineKeyboardMarkup(buttons)
    
    @staticmethod
    def image_list_keyboard(images, selected_indices, page=0, per_page=5):
        """
        Inline keyboard for selecting multiple images for bulk upload.
        images: list of dicts with 'filename'
        selected_indices: set of image indices already selected
        page: current page number (pagination)
        per_page: number of images per page
        """
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
            nav_buttons.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"img_pg_{page-1}"))
        if end < len(images):
            nav_buttons.append(InlineKeyboardButton("➡️ Next", callback_data=f"img_pg_{page+1}"))
        if nav_buttons:
            buttons.append(nav_buttons)

        # Select / Deselect all + Confirm
        buttons.append([
            InlineKeyboardButton("✅ Select All Images", callback_data="img_sel_all"),
            InlineKeyboardButton("❌ Deselect All Images", callback_data="img_desel_all")
        ])
        buttons.append([
            InlineKeyboardButton("📤 Confirm Image Upload", callback_data="confirm_image_upload")
        ])
        buttons.append([
            InlineKeyboardButton("🏠 Back", callback_data="main_menu")
        ])

        return InlineKeyboardMarkup(buttons)
    
    @staticmethod
    def single_video_upload(video_key):
        """Single video upload button."""
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("📤 Upload to Group", callback_data=f"upload_single_{video_key}")]
        ])
    
    @staticmethod
    def single_image_upload(image_key):
        """Single image upload button with short callback data"""
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("📤 Upload to Group", callback_data=f"up_img_{image_key}")]
        ])
    @staticmethod
    def bulk_download_complete_mixed(user_id, video_paths, image_paths):
        """Keyboard shown after mixed bulk download completes"""
        buttons = []
        
        if video_paths:
            buttons.append([InlineKeyboardButton("📤 Upload All Videos to Group", callback_data="upload_bulk_videos_downloaded")])
        
        if image_paths:
            buttons.append([InlineKeyboardButton("📤 Upload All Images to Group", callback_data="upload_bulk_images_downloaded")])
        
        if video_paths or image_paths:
            buttons.append([InlineKeyboardButton("📤 Upload All Content to Group", callback_data="upload_bulk_all_downloaded")])
        
        buttons.extend([
            [
                InlineKeyboardButton("📥 Download More", callback_data="download"),
                InlineKeyboardButton("📊 View All Videos", callback_data="bulk_upload")
            ],
            [
                InlineKeyboardButton("🖼️ View All Images", callback_data="bulk_upload_images")
            ],
            [
                InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")
            ]
        ])

        return InlineKeyboardMarkup(buttons)
    
    @staticmethod
    def history_pagination(current_page: int, total_pages: int):
        """History view pagination keyboard"""
        buttons = []
        
        # Navigation buttons
        nav_row = []
        if current_page > 1:
            nav_row.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"history:{current_page-1}"))
        if current_page < total_pages:
            nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"history:{current_page+1}"))
        
        if nav_row:
            buttons.append(nav_row)
        
        # Action buttons
        buttons.append([
            InlineKeyboardButton("📊 Export", callback_data="history:export"),
            InlineKeyboardButton("🗑️ Clear", callback_data="history:clear")
        ])
        
        # Back button
        buttons.append([InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")])
        
        return InlineKeyboardMarkup(buttons)
    
    @staticmethod
    def export_format_selection():
        """Export format selection keyboard"""
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 CSV (Excel)", callback_data="export:csv")],
            [InlineKeyboardButton("📄 Text File", callback_data="export:txt")],
            [InlineKeyboardButton("🔙 Cancel", callback_data="history:1")]
        ])
    
    @staticmethod
    def clear_history_confirmation():
        """Confirm clearing history"""
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Yes, Clear All", callback_data="history:clear:confirm"),
                InlineKeyboardButton("❌ Cancel", callback_data="history:1")
            ]
        ])
