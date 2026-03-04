"""
Multi-Language Support System
Supports: English, Khmer, Korean, Chinese, Japanese, Russian
"""

import json
import os


class Languages:
    """Language management system"""
    
    # Supported languages (6 total)
    LANGUAGES = {
        'en': '🇬🇧 English',
        'km': '🇰🇭 ភាសាខ្មែរ',
        'ko': '🇰🇷 한국어',
        'zh': '🇨🇳 中文',
        'ja': '🇯🇵 日本語',
        'ru': '🇷🇺 Русский',
    }
    
    # ─────────────────────────────────────────────────────────────────────────
    # Full translation database for all 6 languages
    # ─────────────────────────────────────────────────────────────────────────
    TRANSLATIONS = {
        # ── ENGLISH ──────────────────────────────────────────────────────────
        'en': {
            # Basics
            'welcome_title': 'Welcome',
            'bot_name': 'AfterDark Vault',
            'welcome_description': 'Your premium companion for downloading and managing media across X (Twitter), RedGifs, Videy, and more!',
            'quick_actions': 'Quick Actions:',
            'download_video': 'Download Media',
            'download_images': 'Download Images',
            'bulk_upload': 'Bulk Upload',
            'statistics': 'Statistics',
            'help': 'Help',
            'about': 'About',
            'settings': 'Settings',
            'main_menu': 'Main Menu',
            'cancel': 'Cancel',
            'back': 'Back',
            'yes': 'Yes',
            'no': 'No',
            'back_to_home': 'Back to Home',
            'back_to_menu': 'Back to Menu',
            # Download flow
            'ready_to_download': 'Ready to Download',
            'send_url': 'Please send me the X/Twitter video or image URL(s) now.',
            'single_url': 'Single URL:',
            'multiple_urls': 'Multiple URLs (choose any format):',
            'downloading': 'Downloading...',
            'uploading': 'Uploading...',
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
            'new_download': 'New Download',
            'download_more': 'Download More',
            'download_more_images': 'Download More Images',
            # Selection
            'select_all': 'Select All',
            'deselect_all': 'Deselect All',
            'select_all_images': 'Select All Images',
            'deselect_all_images': 'Deselect All Images',
            'confirm_upload': 'Confirm Upload',
            'confirm_image_upload': 'Confirm Image Upload',
            # Bulk
            'bulk_download_complete': 'Bulk Download Complete!',
            'upload_all': 'Upload All to Group',
            'upload_all_videos': 'Upload All Videos to Group',
            'upload_all_images': 'Upload All Images to Group',
            'upload_all_content': 'Upload All Content to Group',
            'view_all_videos': 'View All Videos',
            'view_all_images': 'View All Images',
            'detected_urls': 'Detected URLs:',
            'summary': 'Summary:',
            'total_urls': 'Total URLs',
            'downloaded': 'Downloaded',
            'failed': 'Failed',
            'time': 'Time',
            'videos_saved': 'files saved and sent to you.',
            'what_next': 'What would you like to do next?',
            # Navigation
            'prev': 'Prev',
            'next': 'Next',
            # Settings
            'language': 'Language',
            'select_language': 'Select Your Language',
            'language_changed': 'Language changed successfully! ✅',
            'current_language': 'Current language',
            'theme': 'Theme',
            'storage': 'Storage',
            'notifications_on': 'Notifications: ON 🔔',
            'notifications_off': 'Notifications: OFF 🔕',
            # Main menu buttons
            'bulk_videos': 'Bulk Videos',
            'bulk_images': 'Bulk Images',
            'detect': 'Detect',
            'share': 'Share',
            'bulk_queue': 'Bulk Queue',
            'history': 'History',
            'stats': 'Stats',
            'videy_links': 'Videy Links',
            # History / Export
            'export': 'Export',
            'clear': 'Clear',
            'export_csv': 'CSV (Excel)',
            'export_txt': 'Text File',
            'confirm_clear': 'Yes, Clear All',
            # Upload group
            'send_to_group': 'Send to Telegram Group',
        },

        # ── KHMER ─────────────────────────────────────────────────────────────
        'km': {
            'welcome_title': 'សូមស្វាគមន៍',
            'bot_name': 'AfterDark Vault',
            'welcome_description': 'ជំនួយការពិសេសសម្រាប់ទាញយក និងគ្រប់គ្រងមេឌៀពី X (Twitter), RedGifs, Videy និងច្រើនទៀត!',
            'quick_actions': 'សកម្មភាពរហ័ស៖',
            'download_video': 'ទាញយកមេឌៀ',
            'download_images': 'ទាញយករូបភាព',
            'bulk_upload': 'ផ្ទុកឡើងច្រើន',
            'statistics': 'ស្ថិតិ',
            'help': 'ជំនួយ',
            'about': 'អំពី',
            'settings': 'ការកំណត់',
            'main_menu': 'ម៉ឺនុយមេ',
            'cancel': 'បោះបង់',
            'back': 'ថយក្រោយ',
            'yes': 'បាទ/ចាស',
            'no': 'ទេ',
            'back_to_home': 'ត្រឡប់ទៅដើម',
            'back_to_menu': 'ត្រឡប់ទៅម៉ឺនុយ',
            'ready_to_download': 'រួចរាល់សម្រាប់ទាញយក',
            'send_url': 'សូមផ្ញើ URL វីដេអូ ឬរូបភាព X/Twitter ឥឡូវ។',
            'single_url': 'URL តែមួយ៖',
            'multiple_urls': 'URL ច្រើន (ជ្រើសរើសទម្រង់)៖',
            'downloading': 'កំពុងទាញយក...',
            'uploading': 'កំពុងផ្ទុកឡើង...',
            'download_complete': 'ទាញយករួចរាល់!',
            'upload_complete': 'ផ្ទុកឡើងរួចរាល់!',
            'download_failed': 'ទាញយកបរាជ័យ',
            'upload_failed': 'ផ្ទុកបរាជ័យ',
            'success': 'ជោគជ័យ',
            'error': 'កំហុស',
            'processing': 'កំពុងដំណើរការ...',
            'please_wait': 'សូមរង់ចាំ...',
            'upload_to_group': 'ផ្ទុកឡើងទៅក្រុម',
            'download_another': 'ទាញយកថ្មីទៀត',
            'new_download': 'ទាញយកថ្មី',
            'download_more': 'ទាញយកបន្ថែម',
            'download_more_images': 'ទាញយករូបភាពបន្ថែម',
            'select_all': 'ជ្រើសរើសទាំងអស់',
            'deselect_all': 'មិនជ្រើសរើស',
            'select_all_images': 'ជ្រើសរូបភាពទាំងអស់',
            'deselect_all_images': 'មិនជ្រើសរូបភាព',
            'confirm_upload': 'បញ្ជាក់ការផ្ទុក',
            'confirm_image_upload': 'បញ្ជាក់ការផ្ទុករូបភាព',
            'bulk_download_complete': 'ទាញយកច្រើនរួចរាល់!',
            'upload_all': 'ផ្ទុកទាំងអស់ទៅក្រុម',
            'upload_all_videos': 'ផ្ទុកវីដេអូទាំងអស់ទៅក្រុម',
            'upload_all_images': 'ផ្ទុករូបភាពទាំងអស់ទៅក្រុម',
            'upload_all_content': 'ផ្ទុករាល់មាតិកា',
            'view_all_videos': 'មើលវីដេអូទាំងអស់',
            'view_all_images': 'មើលរូបភាពទាំងអស់',
            'detected_urls': 'URL ដែលរកឃើញ៖',
            'summary': 'សង្ខេប៖',
            'total_urls': 'URL សរុប',
            'downloaded': 'បានទាញយក',
            'failed': 'បរាជ័យ',
            'time': 'ពេលវេលា',
            'videos_saved': 'ឯកសារបានរក្សាទុក។',
            'what_next': 'តើចង់ធ្វើអ្វីបន្ទាប់?',
            'prev': 'មុន',
            'next': 'បន្ទាប់',
            'language': 'ភាសា',
            'select_language': 'ជ្រើសរើសភាសា',
            'language_changed': 'បានប្តូរភាសាដោយជោគជ័យ! ✅',
            'current_language': 'ភាសាបច្ចុប្បន្ន',
            'theme': 'ប្រធានបទ',
            'storage': 'ការផ្ទុក',
            'notifications_on': 'ការជូនដំណឹង៖ បើក 🔔',
            'notifications_off': 'ការជូនដំណឹង៖ បិទ 🔕',
            'bulk_videos': 'វីដេអូច្រើន',
            'bulk_images': 'រូបភាពច្រើន',
            'detect': 'ស្វែងរក',
            'share': 'ចែករំលែក',
            'bulk_queue': 'ជួរទាញ',
            'history': 'ប្រវត្តិ',
            'stats': 'ស្ថិតិ',
            'videy_links': 'តំណ Videy',
            'export': 'នាំចេញ',
            'clear': 'លុបចោល',
            'export_csv': 'CSV (Excel)',
            'export_txt': 'ឯកសារអក្សរ',
            'confirm_clear': 'បាទ/ចាស លុបទាំងអស់',
            'send_to_group': 'ផ្ញើទៅក្រុម Telegram',
        },

        # ── KOREAN ────────────────────────────────────────────────────────────
        'ko': {
            'welcome_title': '환영합니다',
            'bot_name': 'AfterDark Vault',
            'welcome_description': 'X(Twitter), RedGifs, Videy 등에서 미디어를 다운로드하고 관리하는 프리미엄 도우미!',
            'quick_actions': '빠른 작업:',
            'download_video': '미디어 다운로드',
            'download_images': '이미지 다운로드',
            'bulk_upload': '대량 업로드',
            'statistics': '통계',
            'help': '도움말',
            'about': '정보',
            'settings': '설정',
            'main_menu': '메인 메뉴',
            'cancel': '취소',
            'back': '뒤로',
            'yes': '예',
            'no': '아니오',
            'back_to_home': '홈으로',
            'back_to_menu': '메뉴로',
            'ready_to_download': '다운로드 준비 완료',
            'send_url': 'X/Twitter 비디오 또는 이미지 URL을 지금 보내주세요.',
            'single_url': '단일 URL:',
            'multiple_urls': '여러 URL (형식 선택):',
            'downloading': '다운로드 중...',
            'uploading': '업로드 중...',
            'download_complete': '다운로드 완료',
            'upload_complete': '업로드 완료',
            'download_failed': '다운로드 실패',
            'upload_failed': '업로드 실패',
            'success': '성공',
            'error': '오류',
            'processing': '요청 처리 중...',
            'please_wait': '잠시 기다려주세요...',
            'upload_to_group': '그룹에 업로드',
            'download_another': '다른 것 다운로드',
            'new_download': '새 다운로드',
            'download_more': '더 다운로드',
            'download_more_images': '이미지 더 다운로드',
            'select_all': '전체 선택',
            'deselect_all': '전체 해제',
            'select_all_images': '이미지 전체 선택',
            'deselect_all_images': '이미지 전체 해제',
            'confirm_upload': '업로드 확인',
            'confirm_image_upload': '이미지 업로드 확인',
            'bulk_download_complete': '대량 다운로드 완료!',
            'upload_all': '전체 그룹에 업로드',
            'upload_all_videos': '모든 동영상 그룹 업로드',
            'upload_all_images': '모든 이미지 그룹 업로드',
            'upload_all_content': '모든 콘텐츠 업로드',
            'view_all_videos': '모든 동영상 보기',
            'view_all_images': '모든 이미지 보기',
            'detected_urls': '감지된 URL:',
            'summary': '요약:',
            'total_urls': '전체 URL',
            'downloaded': '다운로드됨',
            'failed': '실패',
            'time': '시간',
            'videos_saved': '파일이 저장되어 전송되었습니다.',
            'what_next': '다음에 무엇을 하시겠습니까?',
            'prev': '이전',
            'next': '다음',
            'language': '언어',
            'select_language': '언어를 선택하세요',
            'language_changed': '언어가 성공적으로 변경되었습니다! ✅',
            'current_language': '현재 언어',
            'theme': '테마',
            'storage': '저장소',
            'notifications_on': '알림: 켜짐 🔔',
            'notifications_off': '알림: 꺼짐 🔕',
            'bulk_videos': '대량 동영상',
            'bulk_images': '대량 이미지',
            'detect': '감지',
            'share': '공유',
            'bulk_queue': '대량 대기열',
            'history': '기록',
            'stats': '통계',
            'videy_links': 'Videy 링크',
            'export': '내보내기',
            'clear': '지우기',
            'export_csv': 'CSV (Excel)',
            'export_txt': '텍스트 파일',
            'confirm_clear': '예, 전체 삭제',
            'send_to_group': 'Telegram 그룹에 전송',
        },

        # ── CHINESE (Simplified) ───────────────────────────────────────────────
        'zh': {
            'welcome_title': '欢迎',
            'bot_name': 'AfterDark Vault',
            'welcome_description': '您的高级媒体下载和管理助手，支持 X (Twitter)、RedGifs、Videy 等！',
            'quick_actions': '快速操作：',
            'download_video': '下载媒体',
            'download_images': '下载图片',
            'bulk_upload': '批量上传',
            'statistics': '统计',
            'help': '帮助',
            'about': '关于',
            'settings': '设置',
            'main_menu': '主菜单',
            'cancel': '取消',
            'back': '返回',
            'yes': '是',
            'no': '否',
            'back_to_home': '返回主页',
            'back_to_menu': '返回菜单',
            'ready_to_download': '准备下载',
            'send_url': '请现在发送 X/Twitter 视频或图片 URL。',
            'single_url': '单个 URL：',
            'multiple_urls': '多个 URL（选择任意格式）：',
            'downloading': '下载中...',
            'uploading': '上传中...',
            'download_complete': '下载完成',
            'upload_complete': '上传完成',
            'download_failed': '下载失败',
            'upload_failed': '上传失败',
            'success': '成功',
            'error': '错误',
            'processing': '正在处理...',
            'please_wait': '请稍候...',
            'upload_to_group': '上传到群组',
            'download_another': '下载另一个',
            'new_download': '新下载',
            'download_more': '下载更多',
            'download_more_images': '下载更多图片',
            'select_all': '全选',
            'deselect_all': '取消全选',
            'select_all_images': '全选图片',
            'deselect_all_images': '取消全选图片',
            'confirm_upload': '确认上传',
            'confirm_image_upload': '确认图片上传',
            'bulk_download_complete': '批量下载完成！',
            'upload_all': '全部上传到群组',
            'upload_all_videos': '所有视频上传到群组',
            'upload_all_images': '所有图片上传到群组',
            'upload_all_content': '上传所有内容',
            'view_all_videos': '查看所有视频',
            'view_all_images': '查看所有图片',
            'detected_urls': '检测到的 URL：',
            'summary': '摘要：',
            'total_urls': '总 URL 数',
            'downloaded': '已下载',
            'failed': '失败',
            'time': '时间',
            'videos_saved': '个文件已保存并发送。',
            'what_next': '接下来要做什么？',
            'prev': '上一页',
            'next': '下一页',
            'language': '语言',
            'select_language': '选择语言',
            'language_changed': '语言更改成功！✅',
            'current_language': '当前语言',
            'theme': '主题',
            'storage': '存储',
            'notifications_on': '通知：开启 🔔',
            'notifications_off': '通知：关闭 🔕',
            'bulk_videos': '批量视频',
            'bulk_images': '批量图片',
            'detect': '检测',
            'share': '分享',
            'bulk_queue': '批量队列',
            'history': '历史记录',
            'stats': '统计',
            'videy_links': 'Videy 链接',
            'export': '导出',
            'clear': '清除',
            'export_csv': 'CSV (Excel)',
            'export_txt': '文本文件',
            'confirm_clear': '是，全部清除',
            'send_to_group': '发送到 Telegram 群组',
        },

        # ── JAPANESE ──────────────────────────────────────────────────────────
        'ja': {
            'welcome_title': 'ようこそ',
            'bot_name': 'AfterDark Vault',
            'welcome_description': 'X（Twitter）、RedGifs、Videyなどからメディアをダウンロード・管理するプレミアムアシスタント！',
            'quick_actions': 'クイックアクション：',
            'download_video': 'メディアをダウンロード',
            'download_images': '画像をダウンロード',
            'bulk_upload': '一括アップロード',
            'statistics': '統計',
            'help': 'ヘルプ',
            'about': '概要',
            'settings': '設定',
            'main_menu': 'メインメニュー',
            'cancel': 'キャンセル',
            'back': '戻る',
            'yes': 'はい',
            'no': 'いいえ',
            'back_to_home': 'ホームへ',
            'back_to_menu': 'メニューへ',
            'ready_to_download': 'ダウンロード準備完了',
            'send_url': 'X/Twitter の動画・画像 URL を送信してください。',
            'single_url': '単一 URL：',
            'multiple_urls': '複数 URL（形式を選択）：',
            'downloading': 'ダウンロード中...',
            'uploading': 'アップロード中...',
            'download_complete': 'ダウンロード完了',
            'upload_complete': 'アップロード完了',
            'download_failed': 'ダウンロード失敗',
            'upload_failed': 'アップロード失敗',
            'success': '成功',
            'error': 'エラー',
            'processing': '処理中...',
            'please_wait': 'お待ちください...',
            'upload_to_group': 'グループにアップロード',
            'download_another': '別のものをダウンロード',
            'new_download': '新しいダウンロード',
            'download_more': 'さらにダウンロード',
            'download_more_images': '画像をさらにダウンロード',
            'select_all': 'すべて選択',
            'deselect_all': 'すべて解除',
            'select_all_images': '画像をすべて選択',
            'deselect_all_images': '画像をすべて解除',
            'confirm_upload': 'アップロードを確認',
            'confirm_image_upload': '画像アップロードを確認',
            'bulk_download_complete': '一括ダウンロード完了！',
            'upload_all': 'すべてグループにアップロード',
            'upload_all_videos': 'すべての動画をアップロード',
            'upload_all_images': 'すべての画像をアップロード',
            'upload_all_content': 'すべてのコンテンツをアップロード',
            'view_all_videos': 'すべての動画を表示',
            'view_all_images': 'すべての画像を表示',
            'detected_urls': '検出された URL：',
            'summary': '概要：',
            'total_urls': '合計 URL 数',
            'downloaded': 'ダウンロード済み',
            'failed': '失敗',
            'time': '時間',
            'videos_saved': '件のファイルが保存され送信されました。',
            'what_next': '次に何をしますか？',
            'prev': '前へ',
            'next': '次へ',
            'language': '言語',
            'select_language': '言語を選択',
            'language_changed': '言語が正常に変更されました！✅',
            'current_language': '現在の言語',
            'theme': 'テーマ',
            'storage': 'ストレージ',
            'notifications_on': '通知：オン 🔔',
            'notifications_off': '通知：オフ 🔕',
            'bulk_videos': '一括動画',
            'bulk_images': '一括画像',
            'detect': '検出',
            'share': '共有',
            'bulk_queue': '一括キュー',
            'history': '履歴',
            'stats': '統計',
            'videy_links': 'Videy リンク',
            'export': 'エクスポート',
            'clear': 'クリア',
            'export_csv': 'CSV (Excel)',
            'export_txt': 'テキストファイル',
            'confirm_clear': 'はい、すべて削除',
            'send_to_group': 'Telegram グループに送信',
        },

        # ── RUSSIAN ───────────────────────────────────────────────────────────
        'ru': {
            'welcome_title': 'Добро пожаловать',
            'bot_name': 'AfterDark Vault',
            'welcome_description': 'Ваш премиальный помощник для загрузки и управления медиафайлами из X (Twitter), RedGifs, Videy и других!',
            'quick_actions': 'Быстрые действия:',
            'download_video': 'Скачать медиа',
            'download_images': 'Скачать изображения',
            'bulk_upload': 'Массовая загрузка',
            'statistics': 'Статистика',
            'help': 'Помощь',
            'about': 'О боте',
            'settings': 'Настройки',
            'main_menu': 'Главное меню',
            'cancel': 'Отмена',
            'back': 'Назад',
            'yes': 'Да',
            'no': 'Нет',
            'back_to_home': 'На главную',
            'back_to_menu': 'В меню',
            'ready_to_download': 'Готово к загрузке',
            'send_url': 'Отправьте URL видео или изображения X/Twitter.',
            'single_url': 'Один URL:',
            'multiple_urls': 'Несколько URL (выберите формат):',
            'downloading': 'Скачивание...',
            'uploading': 'Загрузка...',
            'download_complete': 'Загрузка завершена',
            'upload_complete': 'Отправка завершена',
            'download_failed': 'Ошибка загрузки',
            'upload_failed': 'Ошибка отправки',
            'success': 'Успех',
            'error': 'Ошибка',
            'processing': 'Обработка запроса...',
            'please_wait': 'Подождите...',
            'upload_to_group': 'Загрузить в группу',
            'download_another': 'Скачать ещё',
            'new_download': 'Новая загрузка',
            'download_more': 'Скачать ещё',
            'download_more_images': 'Скачать больше изображений',
            'select_all': 'Выбрать всё',
            'deselect_all': 'Снять выбор',
            'select_all_images': 'Выбрать все изображения',
            'deselect_all_images': 'Снять выбор с изображений',
            'confirm_upload': 'Подтвердить загрузку',
            'confirm_image_upload': 'Подтвердить загрузку изображений',
            'bulk_download_complete': 'Массовая загрузка завершена!',
            'upload_all': 'Загрузить всё в группу',
            'upload_all_videos': 'Загрузить все видео в группу',
            'upload_all_images': 'Загрузить все изображения в группу',
            'upload_all_content': 'Загрузить весь контент',
            'view_all_videos': 'Просмотреть все видео',
            'view_all_images': 'Просмотреть все изображения',
            'detected_urls': 'Обнаруженные URL:',
            'summary': 'Сводка:',
            'total_urls': 'Всего URL',
            'downloaded': 'Загружено',
            'failed': 'Ошибка',
            'time': 'Время',
            'videos_saved': 'файлов сохранено и отправлено.',
            'what_next': 'Что хотите сделать дальше?',
            'prev': 'Назад',
            'next': 'Далее',
            'language': 'Язык',
            'select_language': 'Выберите язык',
            'language_changed': 'Язык успешно изменён! ✅',
            'current_language': 'Текущий язык',
            'theme': 'Тема',
            'storage': 'Хранилище',
            'notifications_on': 'Уведомления: ВКЛ 🔔',
            'notifications_off': 'Уведомления: ВЫКЛ 🔕',
            'bulk_videos': 'Видео группой',
            'bulk_images': 'Изображения группой',
            'detect': 'Определить',
            'share': 'Поделиться',
            'bulk_queue': 'Очередь загрузки',
            'history': 'История',
            'stats': 'Статистика',
            'videy_links': 'Ссылки Videy',
            'export': 'Экспорт',
            'clear': 'Очистить',
            'export_csv': 'CSV (Excel)',
            'export_txt': 'Текстовый файл',
            'confirm_clear': 'Да, очистить всё',
            'send_to_group': 'Отправить в Telegram-группу',
        },
    }
    
    def __init__(self, data_folder='data'):
        """Initialize language system"""
        self.data_folder = data_folder
        self.user_prefs_file = os.path.join(data_folder, 'user_languages.json')
        self.user_languages = self._load_user_preferences()
    
    def _load_user_preferences(self):
        """Load user language preferences from file"""
        if os.path.exists(self.user_prefs_file):
            try:
                with open(self.user_prefs_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}
    
    def save_user_preferences(self):
        """Save user language preferences to file"""
        os.makedirs(self.data_folder, exist_ok=True)
        try:
            with open(self.user_prefs_file, 'w', encoding='utf-8') as f:
                json.dump(self.user_languages, f, indent=2, ensure_ascii=False)
        except Exception:
            pass
    
    def set_user_language(self, user_id, language_code):
        """Set language preference for a user (in DB + local cache)"""
        if language_code not in self.LANGUAGES:
            return False
        from core.database import history_db
        history_db.set_setting(user_id, "bot_language", language_code)
        self.user_languages[str(user_id)] = language_code
        self.save_user_preferences()
        return True
    
    def get_user_language(self, user_id):
        """Get user's preferred language (default: English)"""
        if user_id is None:
            return 'en'
        try:
            from core.database import history_db
            lang = history_db.get_setting(user_id, "bot_language", "en")
            # Validate it is one of the 6 supported languages
            return lang if lang in self.LANGUAGES else 'en'
        except Exception:
            return 'en'
    
    def translate(self, user_id, key, default=None):
        """Get translated text for user's language"""
        lang = self.get_user_language(user_id)
        
        # Try user's language
        if lang in self.TRANSLATIONS and key in self.TRANSLATIONS[lang]:
            return self.TRANSLATIONS[lang][key]
        
        # Fall back to English
        if key in self.TRANSLATIONS['en']:
            return self.TRANSLATIONS['en'][key]
        
        return default or key
    
    def get_language_keyboard(self, user_id=None):
        """Generate language selection keyboard with only the 6 supported languages"""
        from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        from resources.themes import theme_manager
        
        theme = theme_manager.get_theme(user_id)
        current_lang = self.get_user_language(user_id) if user_id else 'en'
        
        buttons = []
        row = []
        
        for code, name in self.LANGUAGES.items():
            display = f"✅ {name}" if code == current_lang else name
            row.append(InlineKeyboardButton(display, callback_data=f"lang_{code}"))
            if len(row) == 2:
                buttons.append(row)
                row = []
        
        if row:
            buttons.append(row)
        
        back_label = self.translate(user_id, 'back', 'Back')
        buttons.append([
            InlineKeyboardButton(
                f"{theme.get('nav_prev', '🔙')} {back_label}",
                callback_data="settings"
            )
        ])
        
        return InlineKeyboardMarkup(buttons)


# ── Module-level singletons ────────────────────────────────────────────────────
language_manager = Languages()


def get_text(user_id, key, default=None):
    """Quick-access function to get translated text"""
    return language_manager.translate(user_id, key, default)
