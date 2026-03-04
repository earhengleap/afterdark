# twitter_download/ui/messages.py

"""
UI Messages Module
Contains all text messages and templates for the bot with multi-language support
"""

from datetime import datetime
from resources.themes import theme_manager

# Import language system if available
from .languages import get_text
LANG_SUPPORT = True


class Messages:
    """Professional message templates for the bot"""
    
    # Emojis for consistent branding
    LOGO = "🎬"
    SUCCESS = "✅"
    ERROR = "❌"
    WARNING = "⚠️"
    INFO = "ℹ️"
    DOWNLOAD = "📥"
    UPLOAD = "📤"
    STATS = "📊"
    SETTINGS = "⚙️"
    
    @staticmethod
    def welcome(user_name, user_id=None):
        """Welcome message for /start command"""

        theme = theme_manager.get_theme(user_id)
        welcome_text = get_text(user_id, 'welcome_title', 'Welcome')
        bot_name = get_text(user_id, 'bot_name', 'AfterDark Vault')
        description = get_text(user_id, 'welcome_description', 'Your premium companion for downloading and managing media across X (Twitter), RedGifs, Videy, and more!')
        quick_actions = get_text(user_id, 'quick_actions', 'Quick Actions:')
        download_video = get_text(user_id, 'download_video', 'Download Media')
        download_images = get_text(user_id, 'download_images', 'Download Images')
        bulk_upload = get_text(user_id, 'bulk_upload', 'Bulk Upload')
        statistics = get_text(user_id, 'statistics', 'Statistics')
        
        return f"""👋 **{welcome_text} {user_name}!**

{theme.get('logo', '🎬')} **{bot_name}**

{description}

**{quick_actions}**
• Click **{theme.get('download', '📥')} {download_video}** or **🖼️ {download_images}**
• Use **{theme.get('upload', '📤')} {bulk_upload}** to organize and sync media batches
• View your **{theme.get('stats', '📊')} {statistics}** to review download history
• Need help? Check the **❓ Help** section

Simply drop any supported media URL here and I'll handle the rest! ✨

━━━━━━━━━━━━━━━━━━━━
*Powered by AfterDark • Fast & Reliable*"""
    
    @staticmethod
    def help_text(user_id=None):
        """Comprehensive help message"""

        theme = theme_manager.get_theme(user_id)
        if user_id and LANG_SUPPORT:
            help_title = get_text(user_id, 'help', 'Help')
        else:
            help_title = 'Help'
            
        return f"""❓ **How to Use This Bot**

**Step-by-Step Guide:**

**Single Media Download:**
1️⃣ Click the **'{theme.get('download', '📥')} Download Media'** button or simply drop a supported media URL directly in the chat

2️⃣ Supported Platforms:
   • **X (Twitter):** `https://x.com/username/status/...`
   • **RedGifs:** `https://www.redgifs.com/watch/...`
   • **Videy / Porn91** etc.

3️⃣ Wait while I download and process the media

4️⃣ Receive your files directly in chat!

5️⃣ Use **{theme.get('upload', '📤')} Upload to Group** button to push straight to the gallery

**Bulk Media Processing:**
1️⃣ Click **'{theme.get('download', '📥')} Download Media'** button

2️⃣ Send multiple URLs simultaneously:

   **Formats supported:**
   • Space-separated: `url1 url2 url3`
   • Pipe-separated: `url1 | url2 | url3`
   • New lines:
     ```
     url1
     url2
     url3
     ```

3️⃣ Watch the real-time progress indicators

4️⃣ After completion, choose:
   • **{theme.get('upload', '📤')} Upload All to Group**
   • **{theme.get('download', '📥')} Download More**
   • **{theme.get('stats', '📊')} View All History**

━━━━━━━━━━━━━━━━━━━━

**Tips:**
{theme.get('info', 'ℹ️')} Large files may take slightly longer due to high-quality retention.
{theme.get('info', 'ℹ️')} The Dashboard Mini App organizes downloaded media by AI category.
{theme.get('info', 'ℹ️')} Upload progress shows realtime analytics and ETAs.

━━━━━━━━━━━━━━━━━━━━
*Need more help? Let support know!*"""
    
    @staticmethod
    def about_text(user_id=None):
        """About bot information"""

        theme = theme_manager.get_theme(user_id)
        return f"""{theme.get('info', 'ℹ️')} **About This Bot**

**AfterDark** is a premium Telegram integration suite designed to simplify gathering, processing, and categorizing your favorite media uniformly from across the Web.

**Key Features:**
{theme.get('success', '✅')} Original Quality Media Acquisition
{theme.get('success', '✅')} Comprehensive Multi-platform reach
{theme.get('success', '✅')} Seamless Background Syncing
{theme.get('success', '✅')} Local First-AI Auto Categorization (via Ollama)
{theme.get('success', '✅')} Telegram Mini App Dashboard Integration
{theme.get('success', '✅')} High-fidelity Tunnel Connectivity
{theme.get('success', '✅')} Smart Bulk Queuing Operations

**Technology Stack:**
• **Backend Framework:** Pyrogram + FastAPI
• **Download Engines:** yt-dlp, native API scrapers
• **Computer Vision:** Local Ollama Pipelines

━━━━━━━━━━━━━━━━━━━━

**Status:** AfterDark Stable Release v{__import__('config.settings', fromlist=['BOT_VERSION']).BOT_VERSION}

Developed with ❤️ for media connoisseurs.

━━━━━━━━━━━━━━━━━━━━
*Private • Seamless • Beautiful*"""
    
    @staticmethod
    def settings_text(user_id=None):
        """Settings menu text"""

        theme = theme_manager.get_theme(user_id)
        if user_id and LANG_SUPPORT:
            settings = get_text(user_id, 'settings', 'Settings')
            language = get_text(user_id, 'language', 'Language')
        else:
            settings = 'Settings'
            language = 'Language'
            
        return f"""{theme.get('settings', '⚙️')} **Bot {settings}**

Customize your download experience:

🔔 **Notifications** - Get updates about downloads
🎨 **Theme** - Choose your preferred interface style
📁 **Storage** - Manage downloaded files
🌐 **{language}** - Select your language (11 languages available)

━━━━━━━━━━━━━━━━━━━━
*More settings coming soon!*"""
    
    @staticmethod
    def stats_text(log_data, user_id=None):
        """Generate statistics message from log data"""

        theme = theme_manager.get_theme(user_id)
        total_downloads = len(log_data)
        
        if user_id and LANG_SUPPORT:
            stats = get_text(user_id, 'statistics', 'Statistics')
            download_video = get_text(user_id, 'download_video', 'Download Video')
        else:
            stats = 'Statistics'
            download_video = 'Download Video'
        
        if total_downloads == 0:
            return f"""{theme.get('stats', '📊')} **Your {stats}**

You haven't downloaded any videos yet!

Click **{theme.get('download', '📥')} {download_video}** to get started."""
        
        total_size = sum(entry.get('filesize', 0) for entry in log_data)
        total_duration = sum(entry.get('duration', 0) for entry in log_data)
        
        size_mb = total_size / (1024 * 1024) if total_size > 0 else 0
        duration_min = total_duration / 60 if total_duration > 0 else 0
        
        latest_download = log_data[-1] if log_data else None
        latest_info = ""
        if latest_download:
            latest_info = f"\n**Latest Download:**\n📹 {latest_download.get('title', 'Unknown')[:50]}..."
        
        return f"""{theme.get('stats', '📊')} **Your {stats}**

**Total Downloads:** {total_downloads} videos
**Total Size:** {size_mb:.2f} MB
**Total Duration:** {duration_min:.1f} minutes

**Average per Video:**
• Size: {size_mb/total_downloads:.2f} MB
• Duration: {duration_min/total_downloads:.1f} min
{latest_info}

━━━━━━━━━━━━━━━━━━━━
*Keep downloading to see more stats!*"""
    
    @staticmethod
    def download_prompt(user_id=None):
        """Prompt user to send URL"""

        theme = theme_manager.get_theme(user_id)
        if user_id and LANG_SUPPORT:
            ready = get_text(user_id, 'ready_to_download', 'Ready to Download')
            send_url = get_text(user_id, 'send_url', 'Please send me the X/Twitter video URL(s) now.')
            single_url = get_text(user_id, 'single_url', 'Single URL:')
            multiple_urls = get_text(user_id, 'multiple_urls', 'Multiple URLs (choose any format):')
        else:
            ready = 'Ready to Download'
            send_url = 'Please send me the X/Twitter video URL(s) now.'
            single_url = 'Single URL:'
            multiple_urls = 'Multiple URLs (choose any format):'
            
        return f"""{theme.get('download', '📥')} **{ready}**

{send_url}

**{single_url}**
`https://x.com/user/status/123456789`

**{multiple_urls}**

📌 **Space-separated:**
`https://x.com/user/status/111 https://x.com/user/status/222`

📌 **Pipe-separated:**
`https://x.com/user/status/111 | https://x.com/user/status/222`

📌 **Line-separated:**
```
https://x.com/user/status/111
https://x.com/user/status/222
https://x.com/user/status/333
```

{theme.get('info', 'ℹ️')} You can mix formats too!

━━━━━━━━━━━━━━━━━━━━
*Waiting for your URL(s)...*"""
    
    @staticmethod
    def bulk_upload_prompt(video_count, user_id=None):
        """Prompt for bulk upload"""

        theme = theme_manager.get_theme(user_id)
        if user_id and LANG_SUPPORT:
            bulk_upload = get_text(user_id, 'bulk_upload', 'Bulk Upload')
            select_all = get_text(user_id, 'select_all', 'Select All')
            deselect_all = get_text(user_id, 'deselect_all', 'Deselect All')
            confirm_upload = get_text(user_id, 'confirm_upload', 'Confirm Upload')
        else:
            bulk_upload = 'Bulk Upload'
            select_all = 'Select All'
            deselect_all = 'Deselect All'
            confirm_upload = 'Confirm Upload'
            
        return f"""{theme.get('upload', '📤')} **{bulk_upload} Videos**

📁 Found **{video_count}** video{'s' if video_count != 1 else ''} in your download folder.

**Instructions:**
1️⃣ Tap on videos to select/deselect them
2️⃣ Use **✅ {select_all}** or **❌ {deselect_all}** buttons
3️⃣ Click **📤 {confirm_upload}** to send selected videos to group

{theme.get('info', 'ℹ️')} Videos will be sent one by one with progress tracking

━━━━━━━━━━━━━━━━━━━━
*Select the videos you want to upload below:*"""
    
    @staticmethod
    def downloading(url, user_id=None):
        """Message shown during download"""

        theme = theme_manager.get_theme(user_id)
        if user_id and LANG_SUPPORT:
            downloading = get_text(user_id, 'downloading', 'Downloading Video')
            processing = get_text(user_id, 'processing', 'Processing your request...')
            please_wait = get_text(user_id, 'please_wait', 'Please wait...')
        else:
            downloading = 'Downloading Video'
            processing = 'Processing your request...'
            please_wait = 'Please wait'
            
        return f"""{theme.get('download', '📥')} **{downloading}**

⏳ {processing}
🔗 Source: `{url[:50]}...`

{please_wait} while I fetch the video for you.

*This may take a few moments depending on video size*"""
    
    @staticmethod
    def uploading(user_id=None):
        """Message shown during upload"""

        theme = theme_manager.get_theme(user_id)
        if user_id and LANG_SUPPORT:
            uploading = get_text(user_id, 'uploading', 'Uploading Video')
            please_wait = get_text(user_id, 'please_wait', 'Please wait...')
        else:
            uploading = 'Uploading Video'
            please_wait = 'Please wait...'
            
        return f"""{theme.get('upload', '📤')} **{uploading}**

⏳ Almost done! Sending video to you...

*{please_wait}*"""
    
    @staticmethod
    def download_failed(user_id=None):
        """Error message for failed downloads"""

        theme = theme_manager.get_theme(user_id)
        if user_id and LANG_SUPPORT:
            failed = get_text(user_id, 'download_failed', 'Download Failed')
        else:
            failed = 'Download Failed'
            
        return f"""{theme.get('error', '❌')} **{failed}**

I couldn't download the video. This might be because:

• The tweet is private or deleted
• The link doesn't contain a video
• The video is too large or restricted
• Network/server issues

{theme.get('info', 'ℹ️')} **Try again with:**
• A public tweet with a video
• A different video URL
• Checking if the link is correct

━━━━━━━━━━━━━━━━━━━━
*Need help? Contact support*"""
    
    @staticmethod
    def upload_failed(error_msg, user_id=None):
        """Error message for failed uploads"""

        theme = theme_manager.get_theme(user_id)
        if user_id and LANG_SUPPORT:
            failed = get_text(user_id, 'upload_failed', 'Upload Failed')
        else:
            failed = 'Upload Failed'
            
        return f"""{theme.get('error', '❌')} **{failed}**

The video was downloaded but couldn't be sent.

**Error details:** `{error_msg[:100]}`

{theme.get('warning', '⚠️')} This might be due to:
• Video file size too large
• Network issues
• Telegram API limits

━━━━━━━━━━━━━━━━━━━━
*Please try again*"""
    
    @staticmethod
    def video_caption(filename, user_id=None):
        """Caption for uploaded video"""

        theme = theme_manager.get_theme(user_id)
        if user_id and LANG_SUPPORT:
            complete = get_text(user_id, 'download_complete', 'Download Complete')
        else:
            complete = 'Download Complete'
            
        return f"""{theme.get('success', '✅')} **{complete}**

📁 File: `{filename}`
⚡ Downloaded with X Video Downloader Bot v1.0.0

━━━━━━━━━━━━━━━━━━━━
Download another? Send a new URL!"""
    
    @staticmethod
    def action_cancelled(user_id=None):
        """Message when user cancels an action"""

        theme = theme_manager.get_theme(user_id)
        if user_id and LANG_SUPPORT:
            cancel = get_text(user_id, 'cancel', 'Cancel')
        else:
            cancel = 'Cancel'
            
        return f"""{theme.get('info', 'ℹ️')} **Action Cancelled**

No problem! What would you like to do next?

Choose an option from the menu below."""
    
    @staticmethod
    def invalid_url(user_id=None):
        """Error for invalid URL format"""

        theme = theme_manager.get_theme(user_id)
        return f"""{theme.get('error', '❌')} **Invalid URL**

Please send a valid X/Twitter video URL.

**Correct format:**
`https://x.com/username/status/1234567890`

{theme.get('info', 'ℹ️')} The URL must start with `http://` or `https://`

**For multiple URLs, use:**
• Spaces: `url1 url2 url3`
• Pipes: `url1 | url2 | url3`
• New lines (one per line)"""
    
    @staticmethod
    def maintenance(user_id=None):
        """Maintenance mode message"""

        theme = theme_manager.get_theme(user_id)
        return f"""{theme.get('warning', '⚠️')} **Maintenance Mode**

The bot is currently under maintenance.

We'll be back shortly. Thank you for your patience!

━━━━━━━━━━━━━━━━━━━━
*Estimated time: 15 minutes*"""
    
    @staticmethod
    def rate_limit(user_id=None):
        """Rate limit message"""

        theme = theme_manager.get_theme(user_id)
        return f"""{theme.get('warning', '⚠️')} **Slow Down!**

You're sending requests too quickly.

Please wait a moment before trying again.

━━━━━━━━━━━━━━━━━━━━
*This helps keep the bot running smoothly*"""
    @staticmethod
    def image_download_prompt(user_id=None):
        """Prompt user to send URL for image download"""

        theme = theme_manager.get_theme(user_id)
        if user_id and LANG_SUPPORT:
            ready = get_text(user_id, 'ready_to_download', 'Ready to Download')
            send_url = get_text(user_id, 'send_url', 'Please send me the X/Twitter image URL(s) now.')
            single_url = get_text(user_id, 'single_url', 'Single URL:')
            multiple_urls = get_text(user_id, 'multiple_urls', 'Multiple URLs (choose any format):')
        else:
            ready = 'Ready to Download Images'
            send_url = 'Please send me the X/Twitter image URL(s) now.'
            single_url = 'Single URL:'
            multiple_urls = 'Multiple URLs (choose any format):'
            
        return f"""🖼️ **{ready}**

{send_url}

**{single_url}**
`https://x.com/user/status/123456789`

**{multiple_urls}**

📌 **Space-separated:**
`https://x.com/user/status/111 https://x.com/user/status/222`

📌 **Pipe-separated:**
`https://x.com/user/status/111 | https://x.com/user/status/222`

📌 **Line-separated:**
https://x.com/user/status/111
https://x.com/user/status/222
https://x.com/user/status/333


ℹ️ **Note:** This will download all images from the tweet(s), including multiple images from single tweets.

━━━━━━━━━━━━━━━━━━━━
*Waiting for your URL(s)...*"""

    @staticmethod
    def bulk_image_upload_prompt(image_count, user_id=None):
        """Prompt for bulk image upload"""

        theme = theme_manager.get_theme(user_id)
        if user_id and LANG_SUPPORT:
            bulk_upload = get_text(user_id, 'bulk_upload', 'Bulk Upload')
            select_all = get_text(user_id, 'select_all', 'Select All')
            deselect_all = get_text(user_id, 'deselect_all', 'Deselect All')
            confirm_upload = get_text(user_id, 'confirm_upload', 'Confirm Upload')
        else:
            bulk_upload = 'Bulk Image Upload'
            select_all = 'Select All'
            deselect_all = 'Deselect All'
            confirm_upload = 'Confirm Upload'
            
        return f"""🖼️ **{bulk_upload} Images**

📁 Found **{image_count}** image{'s' if image_count != 1 else ''} in your download folder.

**Instructions:**
1️⃣ Tap on images to select/deselect them
2️⃣ Use **✅ {select_all}** or **❌ {deselect_all}** buttons
3️⃣ Click **📤 {confirm_upload}** to send selected images to group

ℹ️ Images will be sent in batches with progress tracking

━━━━━━━━━━━━━━━━━━━━
*Select the images you want to upload below:*"""

    @staticmethod
    def bulk_content_prompt(user_id=None):
        """Prompt for bulk content detection"""

        theme = theme_manager.get_theme(user_id)
        return f"""🔍 **Bulk Content Detection**

This feature automatically detects and processes multiple URLs containing both **Videos** and **Images**.

**How it works:**
• Paste multiple X/Twitter URLs (space, pipe, or line-separated)
• Bot automatically detects content type in each URL
• Downloads all videos and images found
• Organizes them for easy bulk upload

**Supported formats:**
📌 Space-separated: `url1 url2 url3`
📌 Pipe-separated: `url1 | url2 | url3`
📌 Line-separated (one per line)

Please send your URLs now:

━━━━━━━━━━━━━━━━━━━━
*Waiting for your URL(s)...*"""