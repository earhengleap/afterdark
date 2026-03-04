import re
import os

def add_keys():
    filepath = r"d:\Project\AfterDark\resources\languages.py"
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # English keys
    en_keys = {
        'bulk_videos': 'Bulk Videos',
        'bulk_images': 'Bulk Images',
        'detect': 'Detect',
        'share': 'Share',
        'bulk_queue': 'Bulk Queue',
        'history': 'History',
        'stats': 'Stats',
        'videy_links': 'Videy Links',
        'notifications_on': 'Notifications: ON',
        'notifications_off': 'Notifications: OFF',
        'theme': 'Theme',
        'storage': 'Storage',
        'back_to_home': 'Back to Home'
    }

    # Spanish keys
    es_keys = {
        'bulk_videos': 'Videos Masivos',
        'bulk_images': 'Imágenes Masivas',
        'detect': 'Detectar',
        'share': 'Compartir',
        'bulk_queue': 'Cola Masiva',
        'history': 'Historial',
        'stats': 'Estadísticas',
        'videy_links': 'Enlaces Videy',
        'notifications_on': 'Notificaciones: ACTIVADAS',
        'notifications_off': 'Notificaciones: DESACTIVADAS',
        'theme': 'Tema',
        'storage': 'Almacenamiento',
        'back_to_home': 'Volver al Inicio'
    }

    # Khmer keys
    km_keys = {
        'bulk_videos': 'វីដេអូច្រើន',
        'bulk_images': 'រូបភាពច្រើន',
        'detect': 'ស្វែងរក',
        'share': 'ចែករំលែក',
        'bulk_queue': 'បញ្ជីទាញយក',
        'history': 'ប្រវត្តិ',
        'stats': 'ស្ថិតិ',
        'videy_links': 'តំណ Videy',
        'notifications_on': 'ការជូនដំណឹង៖ បើក',
        'notifications_off': 'ការជូនដំណឹង៖ បិទ',
        'theme': 'ប្រធានបទ',
        'storage': 'ការផ្ទុក',
        'back_to_home': 'ត្រឡប់ទៅដើម'
    }

    def inject_keys(lang_code, keys_dict, text):
        pattern = rf"('{lang_code}':\s*\{{[^}}]*)"
        
        match = re.search(pattern, text, re.DOTALL)
        if not match:
            return text
            
        block = match.group(1)
        for key, val in keys_dict.items():
            if f"'{key}':" not in block:
                block += f"\n            '{key}': '{val}',"
        
        return text.replace(match.group(1), block)

    content = inject_keys('en', en_keys, content)
    content = inject_keys('es', es_keys, content)
    content = inject_keys('km', km_keys, content)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

if __name__ == "__main__":
    add_keys()
