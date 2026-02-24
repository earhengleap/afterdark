import asyncio
import logging
import json
import urllib.request
import urllib.error
import time
from typing import Optional, Dict, Any

from pyrogram import Client
from pyrogram.types import Message
from pyrogram.errors import FloodWait, MessageNotModified

from core.uploader import safe_edit_text


logger = logging.getLogger("AIHandler")

class AIHandler:
    """Handles routing Telegram messages to the Web App's Ollama AI API."""

    @staticmethod
    async def process_chat(client: Client, message: Message, user_prompt: str) -> None:
        """Process a chat message, sending it to the Web App API and streaming the response."""
        
        if not user_prompt:
            await message.reply_text("Please provide a message to the AI. Example: `/chat What can you do?`")
            return

        import os
        
        twa_port = os.getenv("TWA_PORT", "5000").strip() or "5000"
        base_url = f"http://127.0.0.1:{twa_port}"
        chat_api_url = f"{base_url}/api/chat"
        
        status_msg = await message.reply_text("🧠 *Thinking...* 0s", quote=True)
        start_time = time.time()

        # 2. Start the chat task
        def _start_chat():
            req = urllib.request.Request(
                chat_api_url, 
                data=json.dumps({"message": user_prompt}).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                return json.loads(response.read().decode("utf-8"))

        try:
            result = await asyncio.to_thread(_start_chat)
            if not result.get("ok"):
                await safe_edit_text(status_msg, f"⚠️ **AI Error:** {result.get('error', 'Unknown error starting chat')}")
                return
            task_id = result.get("task_id")
        except Exception as e:
            logger.error(f"Error connecting to AI API: {e}")
            await safe_edit_text(status_msg, f"⚠️ **Connection Error**\nCould not reach the Web App AI API.\n`{str(e)}`")
            return

        # 3. Poll for the result
        poll_api_url = f"{base_url}/api/chat/result/{task_id}"
        poll_count = 0
        last_edit_time = time.time()
        
        def _poll_chat():
            req = urllib.request.Request(poll_api_url)
            with urllib.request.urlopen(req, timeout=10) as response:
                return json.loads(response.read().decode("utf-8"))
        
        while True:
            await asyncio.sleep(1.0)
            poll_count += 1
            elapsed = int(time.time() - start_time)
            
            try:
                poll_result = await asyncio.to_thread(_poll_chat)
                
                if not poll_result.get("ok"):
                    await safe_edit_text(status_msg, f"⚠️ **AI Error:** {poll_result.get('error', 'Unknown error during polling')}")
                    return
                    
                status = poll_result.get("status")
                
                if status == "pending":
                    # Update UI with partial text if available, capped at once every 1.0 second to avoid FloodWait
                    if time.time() - last_edit_time >= 1.0:
                        dots = "." * ((poll_count % 3) + 1)
                        partial_text = poll_result.get("reply", "")
                        
                        if partial_text:
                            # Truncate partial text just in case it gets massive during streaming
                            if len(partial_text) > 3900:
                                partial_text = partial_text[:3900] + "..."
                            await safe_edit_text(status_msg, f"🧠 *Thinking{dots}*\n\n{partial_text}")
                        else:
                            await safe_edit_text(status_msg, f"🧠 *Thinking{dots}* {elapsed}s")
                            
                        last_edit_time = time.time()
                    continue
                    
                elif status == "done":
                    reply_text = poll_result.get("reply", "No response generated.")
                    model_used = poll_result.get("model", "unknown")
                    
                    # Format final message
                    final_text = f"🤖 **Vault Assistant** (`{model_used}`)\n\n"
                    final_text += reply_text
                    
                    # Telegram message limits
                    if len(final_text) > 4000:
                        final_text = final_text[:4000] + "\n\n...[Truncated]"
                        
                    await safe_edit_text(status_msg, final_text)
                    return
                    
                elif status == "error":
                    await safe_edit_text(status_msg, f"⚠️ **AI Generation Error:** {poll_result.get('error', 'AI could not generate a response.')}")
                    return
                else:
                    await safe_edit_text(status_msg, f"⚠️ **Unknown Status:** `{status}`")
                    return

            except Exception as e:
                logger.error(f"Error polling AI API: {e}")
                # Don't fail immediately on a single poll error, try a few times.
                if poll_count > 40: # Give up after ~60 seconds of failures
                    await safe_edit_text(status_msg, f"⚠️ **Connection Error**\nPolling the Web App timed out.\n`{str(e)}`")
                    return
