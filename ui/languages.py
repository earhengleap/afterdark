# twitter_download/ui/languages.py

"""
Multi-Language Support System
Provides internationalization for the bot
"""

import json
import os

class Languages:
    """Language management system"""
    
    # Available languages
    LANGUAGES = {
        'en': '🇬🇧 English',
        'es': '🇪🇸 Español',
        'fr': '🇫🇷 Français',
        'de': '🇩🇪 Deutsch',
        'zh': '🇨🇳 中文',
        'ja': '🇯🇵 日本語',
        'ko': '🇰🇷 한국어',
        'ru': '🇷🇺 Русский',
        'ar': '🇸🇦 العربية',
        'pt': '🇧🇷 Português',
        'km': '🇰🇭 ភាសាខ្មែរ'
    }
    
    # Translation database
    TRANSLATIONS = {
        'en': {
            'welcome_title': 'Welcome',
            'bot_name': 'X Video Downloader Bot',
            'welcome_description': 'I help you download videos from X (Twitter) quickly and easily!',
            'quick_actions': 'Quick Actions:',
            'download_video': 'Download Video',
            'bulk_upload': 'Bulk Upload',
            'statistics': 'Statistics',
            'help': 'Help',
            'about': 'About',
            'settings': 'Settings',
            'main_menu': 'Main Menu',
            'cancel': 'Cancel',
            'back': 'Back',
            'ready_to_download': 'Ready to Download',
            'send_url': 'Please send me the X/Twitter video URL(s) now.',
            'single_url': 'Single URL:',
            'multiple_urls': 'Multiple URLs (choose any format):',
            'downloading': 'Downloading Video',
            'uploading': 'Uploading Video',
            'download_complete': 'Download Complete',
            'upload_complete': 'Upload Complete',
            'download_failed': 'Download Failed',
            'upload_failed': 'Upload Failed',
            'success': 'Success',
            'error': 'Error',
            'processing': 'Processing your request...',
            'please_wait': 'Please wait...',
            'upload_to_group': 'Upload to Group',
            'download_another': 'Download Another',
            'select_all': 'Select All',
            'deselect_all': 'Deselect All',
            'confirm_upload': 'Confirm Upload',
            'bulk_download_complete': 'Bulk Download Complete!',
            'detected_urls': 'Detected URLs:',
            'summary': 'Summary:',
            'total_urls': 'Total URLs',
            'downloaded': 'Downloaded',
            'failed': 'Failed',
            'time': 'Time',
            'videos_saved': 'video(s) saved and sent to you.',
            'what_next': 'What would you like to do next?',
            'language': 'Language',
            'select_language': 'Select Your Language',
            'language_changed': 'Language changed successfully!',
            'current_language': 'Current language',
        },
        'es': {
            'welcome_title': 'Bienvenido',
            'bot_name': 'Bot de Descarga de Videos X',
            'welcome_description': '¡Te ayudo a descargar videos de X (Twitter) rápida y fácilmente!',
            'quick_actions': 'Acciones Rápidas:',
            'download_video': 'Descargar Video',
            'bulk_upload': 'Subida Masiva',
            'statistics': 'Estadísticas',
            'help': 'Ayuda',
            'about': 'Acerca de',
            'settings': 'Configuración',
            'main_menu': 'Menú Principal',
            'cancel': 'Cancelar',
            'back': 'Volver',
            'ready_to_download': 'Listo para Descargar',
            'send_url': 'Por favor envíame la(s) URL(s) del video de X/Twitter ahora.',
            'single_url': 'URL única:',
            'multiple_urls': 'URLs múltiples (elige cualquier formato):',
            'downloading': 'Descargando Video',
            'uploading': 'Subiendo Video',
            'download_complete': 'Descarga Completa',
            'upload_complete': 'Subida Completa',
            'download_failed': 'Descarga Fallida',
            'upload_failed': 'Subida Fallida',
            'success': 'Éxito',
            'error': 'Error',
            'processing': 'Procesando tu solicitud...',
            'please_wait': 'Por favor espera...',
            'upload_to_group': 'Subir al Grupo',
            'download_another': 'Descargar Otro',
            'select_all': 'Seleccionar Todo',
            'deselect_all': 'Deseleccionar Todo',
            'confirm_upload': 'Confirmar Subida',
            'bulk_download_complete': '¡Descarga Masiva Completa!',
            'detected_urls': 'URLs Detectadas:',
            'summary': 'Resumen:',
            'total_urls': 'URLs Totales',
            'downloaded': 'Descargado',
            'failed': 'Fallido',
            'time': 'Tiempo',
            'videos_saved': 'video(s) guardado(s) y enviado(s).',
            'what_next': '¿Qué te gustaría hacer a continuación?',
            'language': 'Idioma',
            'select_language': 'Selecciona Tu Idioma',
            'language_changed': '¡Idioma cambiado exitosamente!',
            'current_language': 'Idioma actual',
        },
        'zh': {
            'welcome_title': '欢迎',
            'bot_name': 'X视频下载机器人',
            'welcome_description': '我可以帮助您快速轻松地从X (Twitter)下载视频！',
            'quick_actions': '快速操作：',
            'download_video': '下载视频',
            'bulk_upload': '批量上传',
            'statistics': '统计',
            'help': '帮助',
            'about': '关于',
            'settings': '设置',
            'main_menu': '主菜单',
            'cancel': '取消',
            'back': '返回',
            'ready_to_download': '准备下载',
            'send_url': '请现在发送X/Twitter视频URL。',
            'single_url': '单个URL：',
            'multiple_urls': '多个URL（选择任意格式）：',
            'downloading': '正在下载视频',
            'uploading': '正在上传视频',
            'download_complete': '下载完成',
            'upload_complete': '上传完成',
            'download_failed': '下载失败',
            'upload_failed': '上传失败',
            'success': '成功',
            'error': '错误',
            'processing': '正在处理您的请求...',
            'please_wait': '请稍候...',
            'upload_to_group': '上传到群组',
            'download_another': '下载另一个',
            'select_all': '全选',
            'deselect_all': '取消全选',
            'confirm_upload': '确认上传',
            'bulk_download_complete': '批量下载完成！',
            'detected_urls': '检测到的URL：',
            'summary': '摘要：',
            'total_urls': '总URL数',
            'downloaded': '已下载',
            'failed': '失败',
            'time': '时间',
            'videos_saved': '个视频已保存并发送给您。',
            'what_next': '您接下来想做什么？',
            'language': '语言',
            'select_language': '选择您的语言',
            'language_changed': '语言更改成功！',
            'current_language': '当前语言',
        },
        'ja': {
            'welcome_title': 'ようこそ',
            'bot_name': 'X動画ダウンローダーボット',
            'welcome_description': 'X（Twitter）から動画を素早く簡単にダウンロードできます！',
            'quick_actions': 'クイックアクション：',
            'download_video': '動画をダウンロード',
            'bulk_upload': '一括アップロード',
            'statistics': '統計',
            'help': 'ヘルプ',
            'about': '概要',
            'settings': '設定',
            'main_menu': 'メインメニュー',
            'cancel': 'キャンセル',
            'back': '戻る',
            'ready_to_download': 'ダウンロード準備完了',
            'send_url': 'X/Twitter動画のURLを送信してください。',
            'single_url': '単一URL：',
            'multiple_urls': '複数URL（任意の形式）：',
            'downloading': '動画をダウンロード中',
            'uploading': '動画をアップロード中',
            'download_complete': 'ダウンロード完了',
            'upload_complete': 'アップロード完了',
            'download_failed': 'ダウンロード失敗',
            'upload_failed': 'アップロード失敗',
            'success': '成功',
            'error': 'エラー',
            'processing': 'リクエストを処理中...',
            'please_wait': 'お待ちください...',
            'upload_to_group': 'グループにアップロード',
            'download_another': '別の動画をダウンロード',
            'select_all': 'すべて選択',
            'deselect_all': 'すべて解除',
            'confirm_upload': 'アップロードを確認',
            'bulk_download_complete': '一括ダウンロード完了！',
            'detected_urls': '検出されたURL：',
            'summary': '概要：',
            'total_urls': '総URL数',
            'downloaded': 'ダウンロード済み',
            'failed': '失敗',
            'time': '時間',
            'videos_saved': '本の動画が保存され、送信されました。',
            'what_next': '次に何をしますか？',
            'language': '言語',
            'select_language': '言語を選択',
            'language_changed': '言語が正常に変更されました！',
            'current_language': '現在の言語',
        },
        'km': {
            'welcome_title': 'សូមស្វាគមន៍',
            'bot_name': 'ប៊ូតទាញយកវីដេអូ X',
            'welcome_description': 'ខ្ញុំជួយអ្នកទាញយកវីដេអូពី X (Twitter) យ៉ាងរហ័សនិងងាយស្រួល!',
            'quick_actions': 'សកម្មភាពរហ័ស៖',
            'download_video': 'ទាញយកវីដេអូ',
            'bulk_upload': 'ផ្ទុកឡើងច្រើន',
            'statistics': 'ស្ថិតិ',
            'help': 'ជំនួយ',
            'about': 'អំពី',
            'settings': 'ការកំណត់',
            'main_menu': 'ម៉ឺនុយមេ',
            'cancel': 'បោះបង់',
            'back': 'ថយក្រោយ',
            'ready_to_download': 'រួចរាល់សម្រាប់ទាញយក',
            'send_url': 'សូមផ្ញើតំណ URL វីដេអូ X/Twitter ឥឡូវនេះ។',
            'single_url': 'URL តែមួយ៖',
            'multiple_urls': 'URL ច្រើន (ជ្រើសរើសទ្រង់ទ្រាយណាមួយ)៖',
            'downloading': 'កំពុងទាញយកវីដេអូ',
            'uploading': 'កំពុងផ្ទុកវីដេអូឡើង',
            'download_complete': 'ទាញយករួចរាល់',
            'upload_complete': 'ផ្ទុកឡើងរួចរាល់',
            'download_failed': 'ទាញយកបរាជ័យ',
            'upload_failed': 'ផ្ទុកឡើងបរាជ័យ',
            'success': 'ជោគជ័យ',
            'error': 'កំហុស',
            'processing': 'កំពុងដំណើរការសំណើរបស់អ្នក...',
            'please_wait': 'សូមរង់ចាំ...',
            'upload_to_group': 'ផ្ទុកឡើងទៅក្រុម',
            'download_another': 'ទាញយកមួយផ្សេងទៀត',
            'select_all': 'ជ្រើសរើសទាំងអស់',
            'deselect_all': 'មិនជ្រើសរើសទាំងអស់',
            'confirm_upload': 'បញ្ជាក់ការផ្ទុកឡើង',
            'bulk_download_complete': 'ទាញយកច្រើនរួចរាល់!',
            'detected_urls': 'URL ដែលរកឃើញ៖',
            'summary': 'សង្ខេប៖',
            'total_urls': 'URL សរុប',
            'downloaded': 'បានទាញយក',
            'failed': 'បរាជ័យ',
            'time': 'ពេលវេលា',
            'videos_saved': 'វីដេអូត្រូវបានរក្សាទុកនិងផ្ញើទៅអ្នក។',
            'what_next': 'តើអ្នកចង់ធ្វើអ្វីបន្ទាប់?',
            'language': 'ភាសា',
            'select_language': 'ជ្រើសរើសភាសារបស់អ្នក',
            'language_changed': 'បានប្តូរភាសាដោយជោគជ័យ!',
            'current_language': 'ភាសាបច្ចុប្បន្ន',
        }
    }
    
    def __init__(self, data_folder='data'):
        """Initialize language system"""
        self.data_folder = data_folder
        self.user_prefs_file = os.path.join(data_folder, 'user_languages.json')
        self.user_languages = self.load_user_preferences()
    
    def load_user_preferences(self):
        """Load user language preferences from file"""
        if os.path.exists(self.user_prefs_file):
            try:
                with open(self.user_prefs_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def save_user_preferences(self):
        """Save user language preferences to file"""
        os.makedirs(self.data_folder, exist_ok=True)
        with open(self.user_prefs_file, 'w', encoding='utf-8') as f:
            json.dump(self.user_languages, f, indent=2, ensure_ascii=False)
    
    def set_user_language(self, user_id, language_code):
        """Set language preference for a user"""
        if language_code in self.LANGUAGES:
            self.user_languages[str(user_id)] = language_code
            self.save_user_preferences()
            return True
        return False
    
    def get_user_language(self, user_id):
        """Get user's preferred language (default: English)"""
        return self.user_languages.get(str(user_id), 'en')
    
    def translate(self, user_id, key, default=None):
        """Get translated text for user's language"""
        lang = self.get_user_language(user_id)
        
        # Try user's language first
        if lang in self.TRANSLATIONS and key in self.TRANSLATIONS[lang]:
            return self.TRANSLATIONS[lang][key]
        
        # Fall back to English
        if key in self.TRANSLATIONS['en']:
            return self.TRANSLATIONS['en'][key]
        
        # Return default or key itself
        return default or key
    
    def get_language_keyboard(self):
        """Generate language selection keyboard"""
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
        
        return InlineKeyboardMarkup(buttons)
    
    def get_text(user_id, key, default=None):
        """Quick access function to get translated text"""
        return language_manager.translate(user_id, key, default)
    
language_manager = Languages()
