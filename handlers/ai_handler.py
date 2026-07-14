import asyncio
import logging
import json
import urllib.request
import urllib.error
import time
import os
from typing import Optional, Dict, Any

from pyrogram import Client
from pyrogram.types import Message
from pyrogram.errors import FloodWait, MessageNotModified

from core.uploader import safe_edit_text


logger = logging.getLogger("AIHandler")

class AIHandler:
    """Handles AI chat using Ollama directly."""

    @staticmethod
    async def process_chat(client: Client, message: Message, user_prompt: str) -> None:
        """Process a chat message, sending it to Ollama and streaming the response."""
        
        if not user_prompt:
            await message.reply_text("Please provide a message to the AI. Example: `/chat What can you do?`")
            return

        ollama_url = os.getenv("TWA_AI_OLLAMA_URL", "http://127.0.0.1:11434/api/generate").strip()
        ollama_model = os.getenv("TWA_AI_MODEL", "moondream:latest").strip() or "moondream:latest"
        
        status_msg = await message.reply_text("🧠 *Thinking...* 0s", quote=True)
        start_time = time.time()

        payload = {
            "model": ollama_model,
            "prompt": user_prompt,
            "stream": True
        }

        try:
            req = urllib.request.Request(
                ollama_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            
            full_response = ""
            last_edit_time = time.time()
            poll_count = 0
            
            async def _stream_response():
                nonlocal full_response, last_edit_time, poll_count
                
                def _read_stream():
                    with urllib.request.urlopen(req, timeout=120) as response:
                        for line in response:
                            yield line.decode("utf-8").strip()
                
                for line in await asyncio.to_thread(_read_stream):
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        if "response" in data:
                            full_response += data["response"]
                            poll_count += 1
                            elapsed = int(time.time() - start_time)
                            
                            if time.time() - last_edit_time >= 1.0:
                                dots = "." * ((poll_count % 3) + 1)
                                display_text = full_response
                                if len(display_text) > 3900:
                                    display_text = display_text[:3900] + "..."
                                await safe_edit_text(status_msg, f"🧠 *Thinking{dots}*\n\n{display_text}")
                                last_edit_time = time.time()
                        if data.get("done", False):
                            break
                    except json.JSONDecodeError:
                        continue
            
            await _stream_response()
            
            # Final response
            final_text = "🤖 **AfterDark Assistant**\n\n"
            final_text += full_response if full_response else "No response generated."
            
            if len(final_text) > 4000:
                final_text = final_text[:4000] + "\n\n...[Truncated]"
                
            await safe_edit_text(status_msg, final_text)
            
        except urllib.error.URLError as e:
            logger.error(f"Error connecting to Ollama: {e}")
            await safe_edit_text(status_msg, f"⚠️ **Connection Error**\nCould not reach Ollama at `{ollama_url}`.\n`{str(e)}`")
        except Exception as e:
            logger.error(f"Error in AI chat: {e}")
            await safe_edit_text(status_msg, f"⚠️ **Error**\n`{str(e)}`")