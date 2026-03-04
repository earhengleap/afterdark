import re

def update_callbacks():
    filepath = "d:\\Project\\AfterDark\\handlers\\callback_handlers.py"
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Update `Keyboards.main_menu()` to `Keyboards.main_menu(user_id=user_id)`
    content = content.replace("Keyboards.main_menu()", "Keyboards.main_menu(user_id=user_id)")
    
    # 2. Update `Keyboards.settings_menu(new_enabled)` to `Keyboards.settings_menu(new_enabled, user_id=user_id)`
    content = content.replace("Keyboards.settings_menu(new_enabled)", "Keyboards.settings_menu(new_enabled, user_id=user_id)")
    content = content.replace("Keyboards.settings_menu(is_enabled)", "Keyboards.settings_menu(is_enabled, user_id=user_id)")
    
    # 3. Add `settings_theme` and `set_theme:` callbacks before `main_menu`
    if "elif data == \"settings_theme\":" not in content:
        theme_handlers = """
        elif data == "settings_theme":
            from core.database import history_db
            current_theme = history_db.get_setting(user_id, "bot_theme", "default")
            keyboard = Keyboards.theme_selection_menu(current_theme, user_id=user_id)
            
            await callback_query.message.edit_text(
                Messages.settings_text(user_id=user_id) + "\\n\\n🎨 **Choose a Theme:**",
                reply_markup=keyboard
            )
            
        elif data.startswith("set_theme:"):
            from core.database import history_db
            from resources.themes import theme_manager
            
            new_theme = data.split(":")[1]
            if new_theme in theme_manager.THEMES:
                history_db.set_setting(user_id, "bot_theme", new_theme)
                await callback_query.answer(f"✅ Theme changed to {theme_manager.THEMES[new_theme]['name']}!")
            
            # Rehydrate with new theme immediately
            current_theme = history_db.get_setting(user_id, "bot_theme", "default")
            keyboard = Keyboards.theme_selection_menu(current_theme, user_id=user_id)
            
            try:
                await callback_query.message.edit_text(
                    Messages.settings_text(user_id=user_id) + "\\n\\n🎨 **Choose a Theme:**",
                    reply_markup=keyboard
                )
            except Exception:
                pass
"""
        content = content.replace(
            "        elif data == \"main_menu\":",
            theme_handlers + "\n        elif data == \"main_menu\":"
        )

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

if __name__ == "__main__":
    update_callbacks()
