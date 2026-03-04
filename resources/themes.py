"""
Theme Management for AfterDark
Handles dynamic emoji themes for users
"""

class ThemeManager:
    """Manages different emoji sets and aesthetic themes for users."""
    
    THEMES = {
        'default': {
            'name': '🌟 Default',
            'logo': '🎬',
            'success': '✅',
            'error': '❌',
            'warning': '⚠️',
            'info': 'ℹ️',
            'download': '📥',
            'upload': '📤',
            'stats': '📊',
            'settings': '⚙️',
            'bullet': '•',
            'nav_prev': '⬅️ Prev',
            'nav_next': 'Next ➡️',
            'home': '🏠'
        },
        'minimal': {
            'name': '▫️ Minimal',
            'logo': '▫️',
            'success': '✓',
            'error': '✕',
            'warning': '!',
            'info': 'i',
            'download': '↓',
            'upload': '↑',
            'stats': '≡',
            'settings': '⛭',
            'bullet': '-',
            'nav_prev': '< Prev',
            'nav_next': 'Next >',
            'home': '⌂'
        },
        'cyberpunk': {
            'name': '⚡ Cyberpunk',
            'logo': '⚡',
            'success': '🟢',
            'error': '🔴',
            'warning': '🟡',
            'info': '🧿',
            'download': '🔻',
            'upload': '🔺',
            'stats': '📈',
            'settings': '🔧',
            'bullet': '»',
            'nav_prev': '« Prev',
            'nav_next': 'Next »',
            'home': '🚀'
        },
        'anime': {
            'name': '🌸 Anime',
            'logo': '🌸',
            'success': '✨',
            'error': '💢',
            'warning': '💦',
            'info': '💌',
            'download': '💝',
            'upload': '💖',
            'stats': '🎀',
            'settings': '🪄',
            'bullet': '✿',
            'nav_prev': '⏪ Prev',
            'nav_next': 'Next ⏩',
            'home': '🏰'
        }
    }

    @classmethod
    def get_theme(cls, user_id=None) -> dict:
        """Fetch the theme dictionary for a user"""
        if not user_id:
            return cls.THEMES['default']
            
        from core.database import history_db
        theme_name = history_db.get_setting(user_id, "bot_theme", "default")
        if theme_name not in cls.THEMES:
            theme_name = "default"
            
        return cls.THEMES[theme_name]

    @classmethod
    def get_theme_name(cls, user_id) -> str:
        """Fetch the current display name of the user's theme"""
        theme = cls.get_theme(user_id)
        return theme['name']

theme_manager = ThemeManager()
