import re

def update_callbacks():
    filepath = "d:\\Project\\AfterDark\\handlers\\callback_handlers.py"
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Find the settings_theme endpoint to inject settings_language nearby
    if "elif data == \"settings_language\":" not in content:
        language_handlers = """
        elif data == "settings_language":
            from resources.languages import language_manager
            
            keyboard = language_manager.get_language_keyboard(user_id=user_id)
            
            await callback_query.message.edit_text(
                Messages.settings_text(user_id=user_id) + "\\n\\n🌐 **Choose a Language:**",
                reply_markup=keyboard
            )
            await callback_query.answer()
            
        elif data.startswith("lang_"):
            from core.database import history_db
            from resources.languages import language_manager
            
            new_lang = data.split("_")[1]
            if new_lang in language_manager.LANGUAGES:
                history_db.set_setting(user_id, "bot_language", new_lang)
                await callback_query.answer(f"✅ Language changed to {language_manager.LANGUAGES[new_lang]}!")
            
            # Rehydrate with new language immediately
            keyboard = language_manager.get_language_keyboard(user_id=user_id)
            
            try:
                # Also redraw the text in the newly selected language!
                await callback_query.message.edit_text(
                    Messages.settings_text(user_id=user_id) + "\\n\\n🌐 **Choose a Language:**",
                    reply_markup=keyboard
                )
            except Exception:
                pass
"""
        content = content.replace(
            "        elif data == \"settings_theme\":",
            language_handlers + "\n        elif data == \"settings_theme\":"
        )

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

if __name__ == "__main__":
    update_callbacks()
