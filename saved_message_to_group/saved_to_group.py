from telethon import TelegramClient, types
from telethon.errors import FloodWaitError, RPCError, PersistentTimestampOutdatedError
import asyncio
import json
import os
from datetime import datetime
import sys

api_id = 22268900
api_hash = '6764e4d6dd12108e82105f355c6309d8'

# Dictionary of groups with their settings
groups = {
    '1': {
        'id': -1002088860676,
        'name': 'Group 1',
        'send_caption': True,
        'send_text_messages': True,
        'send_links': True,
        'pin_messages': True
    },
    '2': {
        'id': -1002072611905,
        'name': 'Group 2',
        'send_caption': False,
        'send_text_messages': False,
        'send_links': False,
        'pin_messages': False
    },
    '3': {
        'id': -1001990110341,
        'name': 'Group 3',
        'send_caption': False,
        'send_text_messages': False,
        'send_links': False,
        'pin_messages': False
    },
}

session_file = 'my_telegram_session'
log_file = "sent_videos.log"
checkpoint_file = "upload_checkpoint.json"
error_log_file = "error_log.txt"
failed_messages_file = "failed_messages.json"
retry_success_file = "retry_success.log"
permanent_failed_file = "permanent_failed.json"

client = TelegramClient(session_file, api_id, api_hash)

def truncate_caption(text, max_length=1024):
    """Truncate caption to Telegram's limit with ellipsis"""
    if not text or len(text) <= max_length:
        return text
    return text[:max_length-3] + "..."

def log_error(error_msg):
    """Log errors to file for debugging"""
    try:
        with open(error_log_file, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().isoformat()}] {error_msg}\n")
    except:
        pass

def save_permanent_failed(msg_id, group_id, group_name, error_reason):
    """Save permanently failed messages (file reference expired, etc.)"""
    failed_entry = {
        "timestamp": datetime.now().isoformat(),
        "msg_id": msg_id,
        "group_id": group_id,
        "group_name": group_name,
        "error": error_reason,
        "reason": "FILE_REFERENCE_EXPIRED_OR_SELF_DESTRUCTING"
    }
    try:
        perm_failed = []
        if os.path.exists(permanent_failed_file):
            with open(permanent_failed_file, "r", encoding="utf-8") as f:
                try:
                    perm_failed = json.load(f)
                except:
                    perm_failed = []
        
        perm_failed.append(failed_entry)
        
        with open(permanent_failed_file, "w", encoding="utf-8") as f:
            json.dump(perm_failed, f, indent=2, ensure_ascii=False)
    except Exception as e:
        log_error(f"Could not save permanent failed message: {e}")

def save_failed_message(msg_id, group_id, group_name, error_reason):
    """Save failed message details for manual review"""
    failed_entry = {
        "timestamp": datetime.now().isoformat(),
        "msg_id": msg_id,
        "group_id": group_id,
        "group_name": group_name,
        "error": error_reason
    }
    try:
        failed_list = []
        if os.path.exists(failed_messages_file):
            with open(failed_messages_file, "r", encoding="utf-8") as f:
                try:
                    failed_list = json.load(f)
                except:
                    failed_list = []
        
        failed_list.append(failed_entry)
        
        with open(failed_messages_file, "w", encoding="utf-8") as f:
            json.dump(failed_list, f, indent=2, ensure_ascii=False)
    except Exception as e:
        log_error(f"Could not save failed message: {e}")

def log_retry_success(msg_id, group_id, group_name, message_type):
    """Log successfully retried messages"""
    try:
        with open(retry_success_file, "a", encoding="utf-8") as f:
            entry = {
                "timestamp": datetime.now().isoformat(),
                "msg_id": msg_id,
                "group_id": group_id,
                "group_name": group_name,
                "message_type": message_type
            }
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        log_error(f"Could not log retry success: {e}")

def load_failed_messages():
    """Load failed messages from JSON file"""
    if os.path.exists(failed_messages_file):
        try:
            with open(failed_messages_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            log_error(f"Could not load failed messages: {e}")
            return []
    return []

def remove_from_failed_messages(msg_id, group_id):
    """Remove a successfully retried message from failed list"""
    try:
        failed_list = load_failed_messages()
        failed_list = [
            entry for entry in failed_list 
            if not (entry['msg_id'] == msg_id and entry['group_id'] == group_id)
        ]
        
        with open(failed_messages_file, "w", encoding="utf-8") as f:
            json.dump(failed_list, f, indent=2, ensure_ascii=False)
    except Exception as e:
        log_error(f"Could not update failed messages: {e}")

def load_sent_history():
    """Load sent message history from JSON log file"""
    sent_history = {}
    
    if os.path.exists(log_file):
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            data = json.loads(line)
                            saved_msg_id = data.get('saved_msg_id')
                            group_id = data.get('group_id')
                            message_type = data.get('message_type', 'unknown')
                            
                            if saved_msg_id not in sent_history:
                                sent_history[saved_msg_id] = {}
                            
                            sent_history[saved_msg_id][group_id] = message_type
                            
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            print(f"Warning: Could not load history: {e}")
    
    return sent_history

def save_checkpoint(current_index, total_messages):
    """Save current progress checkpoint"""
    checkpoint = {
        "last_processed_index": current_index,
        "total_messages": total_messages,
        "timestamp": datetime.now().isoformat()
    }
    try:
        with open(checkpoint_file, "w", encoding="utf-8") as f:
            json.dump(checkpoint, f)
    except Exception as e:
        log_error(f"Could not save checkpoint: {e}")

def load_checkpoint():
    """Load progress checkpoint"""
    if os.path.exists(checkpoint_file):
        try:
            with open(checkpoint_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            log_error(f"Could not load checkpoint: {e}")
    return None

def save_to_log(saved_msg_id, group_id, group_msg_id, group_name, message_type, has_caption, is_pinned):
    """Save sent message info to JSON log"""
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "saved_msg_id": saved_msg_id,
        "group_id": group_id,
        "group_name": group_name,
        "group_msg_id": group_msg_id,
        "message_type": message_type,
        "has_caption": has_caption,
        "is_pinned": is_pinned
    }
    
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
    except Exception as e:
        log_error(f"Could not save to log: {e}")

def is_gif_document(document):
    """Check if a document is a GIF/animation"""
    if not document:
        return False
    
    if document.mime_type:
        if 'image/gif' in document.mime_type:
            return True
        if 'video/mp4' in document.mime_type:
            if document.attributes:
                return any(isinstance(attr, types.DocumentAttributeAnimated) 
                          for attr in document.attributes)
    
    if document.attributes:
        return any(isinstance(attr, types.DocumentAttributeAnimated) 
                  for attr in document.attributes)
    
    return False

async def refetch_message(msg_id):
    """Refetch message from saved messages to get fresh file reference - ALWAYS RETURNS FRESH"""
    max_refetch_attempts = 5
    for attempt in range(max_refetch_attempts):
        try:
            print(f"      🔄 Refetching message {msg_id} (attempt {attempt + 1}/{max_refetch_attempts})...")
            message = await client.get_messages('me', ids=msg_id)
            if message:
                await asyncio.sleep(2)  # Give Telegram time to process
                print(f"      ✅ Successfully refetched message {msg_id}")
                return message
        except Exception as e:
            log_error(f"Refetch attempt {attempt + 1} failed for message {msg_id}: {e}")
            if attempt < max_refetch_attempts - 1:
                await asyncio.sleep(5)
    
    print(f"      ❌ Failed to refetch message {msg_id} after {max_refetch_attempts} attempts")
    return None

async def send_with_retry(send_func, operation_name="operation", max_attempts=15):
    """Execute a function with aggressive retry logic"""
    attempt = 0
    last_error = None
    
    while attempt < max_attempts:
        attempt += 1
        try:
            result = await send_func()
            return result
            
        except FloodWaitError as e:
            wait_time = e.seconds + 10
            mins, secs = divmod(wait_time, 60)
            hours, mins = divmod(mins, 60)
            
            print(f"\n{'='*70}")
            print(f"⏳ TELEGRAM FLOOD CONTROL - Attempt {attempt}/{max_attempts}")
            print(f"{'='*70}")
            print(f"   Required wait: {hours}h {mins}m {secs}s")
            print(f"   Operation: {operation_name}")
            print(f"   ⚠️  Waiting automatically...")
            print(f"{'='*70}\n")
            
            for remaining in range(wait_time, 0, -1):
                h, remainder = divmod(remaining, 3600)
                m, s = divmod(remainder, 60)
                percentage = ((wait_time - remaining) / wait_time) * 100
                bar_length = 40
                filled = int(bar_length * percentage / 100)
                bar = '█' * filled + '░' * (bar_length - filled)
                
                sys.stdout.write(f"\r   ⏱️  [{bar}] {percentage:.1f}% - {h:02d}:{m:02d}:{s:02d} left")
                sys.stdout.flush()
                await asyncio.sleep(1)
            
            print(f"\n   ✅ Retrying {operation_name}...\n")
            
        except PersistentTimestampOutdatedError as e:
            log_error(f"PersistentTimestampOutdatedError: {e}")
            await asyncio.sleep(5)
            
        except ConnectionError as e:
            log_error(f"ConnectionError: {e}")
            print(f"\n⚠️  Connection lost (Attempt {attempt}/{max_attempts})")
            print(f"   Reconnecting in 30 seconds...")
            await asyncio.sleep(30)
            
            try:
                if client.is_connected():
                    await client.disconnect()
                await asyncio.sleep(5)
                await client.connect()
                print(f"   ✅ Reconnected")
            except Exception as reconnect_err:
                log_error(f"Reconnect error: {reconnect_err}")
                await asyncio.sleep(10)
            
        except TimeoutError as e:
            log_error(f"TimeoutError: {e}")
            print(f"\n⚠️  Timeout (Attempt {attempt}/{max_attempts})")
            print(f"   Retrying in 20 seconds...")
            await asyncio.sleep(20)
            
        except RPCError as e:
            log_error(f"RPCError: {e}")
            error_msg = str(e).upper()
            
            # FILE REFERENCE EXPIRED - Return special code
            if "FILE_REFERENCE" in error_msg or "REFERENCE_EXPIRED" in error_msg or "SELF-DESTRUCTING" in error_msg:
                print(f"\n🔄 File reference expired detected")
                return "REFETCH_NEEDED"
                
            elif "FLOOD_WAIT" in error_msg:
                print(f"\n⏳ Rate limit: {e}")
                print(f"   Waiting 30 minutes...")
                await asyncio.sleep(1800)
            elif "SLOWMODE_WAIT" in error_msg:
                print(f"\n⏳ Slow mode active: {e}")
                print(f"   Waiting 5 minutes...")
                await asyncio.sleep(300)
            elif "MSG_WAIT" in error_msg:
                print(f"\n⏳ Message rate limit: {e}")
                print(f"   Waiting 2 minutes...")
                await asyncio.sleep(120)
            # CAPTION TOO LONG ERROR - Handle specifically
            elif "CAPTION TOO LONG" in error_msg:
                print(f"\n📝 Caption too long detected: {e}")
                return "CAPTION_TOO_LONG"
            else:
                print(f"\n⚠️  RPC error (Attempt {attempt}/{max_attempts}): {e}")
                print(f"   Waiting 60 seconds...")
                await asyncio.sleep(60)
            
        except Exception as e:
            last_error = e
            log_error(f"Unexpected error: {type(e).__name__}: {e}")
            print(f"\n⚠️  Error (Attempt {attempt}/{max_attempts}): {type(e).__name__}: {e}")
            
            if attempt < max_attempts:
                wait = min(30 * attempt, 300)
                print(f"   Retrying in {wait} seconds...")
                await asyncio.sleep(wait)
            else:
                print(f"   ❌ Max attempts reached")
                break
    
    if last_error:
        print(f"\n❌ Failed after {max_attempts} attempts: {last_error}")
    return None

async def send_message_to_group_with_refetch(message, group_id, group_config, max_refetch=5):
    """Send message with automatic refetching on file reference errors"""
    
    for refetch_attempt in range(max_refetch):
        sent_msg = None
        message_type = "unknown"
        has_caption = False
        is_pinned = False
        
        caption = None
        if group_config['send_caption'] and message.text:
            # Truncate caption if too long to prevent "caption too long" errors
            caption = truncate_caption(message.text)
            if len(message.text) > 1024:
                print(f"      ⚠️  Truncated caption from {len(message.text)} to 1024 chars")
            has_caption = True
        
        # Try to send based on message type
        if message.video:
            message_type = "video"
            sent_msg = await send_with_retry(
                lambda: client.send_file(group_id, message.video, caption=caption, force_document=False),
                f"Sending video to {group_config['name']}"
            )
        
        elif message.photo:
            message_type = "photo"
            sent_msg = await send_with_retry(
                lambda: client.send_file(group_id, message.photo, caption=caption),
                f"Sending photo to {group_config['name']}"
            )
        
        elif message.document:
            if is_gif_document(message.document):
                message_type = "gif"
                sent_msg = await send_with_retry(
                    lambda: client.send_file(group_id, message.document, caption=caption, force_document=False),
                    f"Sending GIF to {group_config['name']}"
                )
            elif group_config['send_text_messages']:
                message_type = "document"
                sent_msg = await send_with_retry(
                    lambda: client.send_file(group_id, message.document, caption=caption),
                    f"Sending document to {group_config['name']}"
                )
        
        elif message.text and group_config['send_text_messages']:
            message_type = "text"
            # For text messages, check if it's too long and handle accordingly
            if len(message.text) > 4096:
                print(f"      ⚠️  Text message too long ({len(message.text)} chars), truncating...")
                truncated_text = truncate_caption(message.text, 4096)
                sent_msg = await send_with_retry(
                    lambda: client.send_message(group_id, truncated_text),
                    f"Sending truncated text to {group_config['name']}"
                )
            else:
                sent_msg = await send_with_retry(
                    lambda: client.send_message(group_id, message.text),
                    f"Sending text to {group_config['name']}"
                )
            has_caption = True
        
        # Handle caption too long error specifically
        if sent_msg == "CAPTION_TOO_LONG":
            print(f"      📝 Caption still too long, sending without caption...")
            # Retry without caption
            if message.video:
                sent_msg = await send_with_retry(
                    lambda: client.send_file(group_id, message.video, force_document=False),
                    f"Sending video without caption to {group_config['name']}"
                )
            elif message.photo:
                sent_msg = await send_with_retry(
                    lambda: client.send_file(group_id, message.photo),
                    f"Sending photo without caption to {group_config['name']}"
                )
            elif message.document and is_gif_document(message.document):
                sent_msg = await send_with_retry(
                    lambda: client.send_file(group_id, message.document, force_document=False),
                    f"Sending GIF without caption to {group_config['name']}"
                )
            elif message.document and group_config['send_text_messages']:
                sent_msg = await send_with_retry(
                    lambda: client.send_file(group_id, message.document),
                    f"Sending document without caption to {group_config['name']}"
                )
            has_caption = False  # No caption was sent
        
        # Check if we need to refetch
        if sent_msg == "REFETCH_NEEDED":
            if refetch_attempt < max_refetch - 1:
                print(f"      🔄 Refetch needed (attempt {refetch_attempt + 1}/{max_refetch}), getting fresh message...")
                fresh_message = await refetch_message(message.id)
                if fresh_message:
                    message = fresh_message  # Update message with fresh reference
                    await asyncio.sleep(2)
                    continue  # Try again with fresh message
                else:
                    print(f"      ❌ Could not refetch message")
                    return "PERMANENT_FAIL", message_type, has_caption, False
            else:
                print(f"      ⛔ Max refetch attempts reached")
                return "PERMANENT_FAIL", message_type, has_caption, False
        
        # If send was successful
        if sent_msg and sent_msg != "REFETCH_NEEDED" and sent_msg != "CAPTION_TOO_LONG":
            # Pin if needed
            if group_config['pin_messages'] and message.pinned:
                try:
                    await send_with_retry(
                        lambda: client.pin_message(group_id, sent_msg.id, notify=False),
                        f"Pinning in {group_config['name']}",
                        max_attempts=5
                    )
                    is_pinned = True
                except Exception as pin_error:
                    log_error(f"Pin error: {pin_error}")
            
            return sent_msg, message_type, has_caption, is_pinned
        
        # If sent_msg is None (other failure)
        if sent_msg is None:
            return None, message_type, has_caption, False
    
    # If we exhausted all refetch attempts
    return "PERMANENT_FAIL", message_type, has_caption, False

def print_progress(scan_stats, upload_stats, current_msg=""):
    """Print progress"""
    print("\n" + "="*70)
    print(f"📊 REAL-TIME PROGRESS")
    print("="*70)
    
    if scan_stats:
        print(f"\n🔍 FOUND IN SAVED MESSAGES:")
        print(f"  🎥 Videos: {scan_stats['videos']:>5}  |  📷 Photos: {scan_stats['photos']:>5}  |  🎞️  GIFs: {scan_stats['gifs']:>5}  |  💬 Text: {scan_stats['text']:>5}")
        print(f"  📌 Pinned: {scan_stats['pinned']:>5}  |  📊 Total: {scan_stats['total']:>5}")
    
    if upload_stats:
        print(f"\n⬆️  UPLOADED TO GROUP(S):")
        print(f"  🎥 Videos: {upload_stats['videos']:>5}  |  📷 Photos: {upload_stats['photos']:>5}  |  🎞️  GIFs: {upload_stats['gifs']:>5}  |  💬 Text: {upload_stats['text']:>5}")
        total_sent = upload_stats['videos'] + upload_stats['photos'] + upload_stats['gifs'] + upload_stats['text']
        print(f"  📌 Pinned: {upload_stats['pinned']:>5}  |  ⏭️  Skipped: {upload_stats['skipped']:>5}  |  ✅ Total: {total_sent:>5}")
        if upload_stats.get('failed', 0) > 0:
            print(f"  ❌ Failed: {upload_stats['failed']:>5}")
        if upload_stats.get('permanent_failed', 0) > 0:
            print(f"  ⛔ Permanent fails: {upload_stats['permanent_failed']:>5}")
    
    if current_msg:
        print(f"\n⏳ {current_msg}")
    
    print("="*70 + "\n")

async def retry_failed_messages():
    """Retry all failed messages with FRESH refetch for EACH group"""
    
    print("\n" + "="*70)
    print("🔄 RETRY FAILED MESSAGES MODE - FRESH REFETCH PER GROUP")
    print("="*70 + "\n")
    
    failed_list = load_failed_messages()
    
    if not failed_list:
        print("✅ No failed messages found! Nothing to retry.\n")
        return
    
    print(f"📊 Found {len(failed_list)} failed message(s) to retry\n")
    
    # Group failures by message ID
    failures_by_msg = {}
    for entry in failed_list:
        msg_id = entry['msg_id']
        if msg_id not in failures_by_msg:
            failures_by_msg[msg_id] = []
        failures_by_msg[msg_id].append(entry)
    
    print(f"📋 Retrying {len(failures_by_msg)} unique message(s) with FRESH refetch per group...\n")
    
    retry_stats = {
        'total_attempts': 0,
        'successes': 0,
        'still_failed': 0,
        'permanent_failed': 0
    }
    
    sent_history = load_sent_history()
    
    for msg_id, failures in failures_by_msg.items():
        print(f"\n{'='*70}")
        print(f"🔄 Retrying Message ID: {msg_id}")
        print(f"{'='*70}")
        
        # Try to send to each failed group - REFETCH BEFORE EACH GROUP
        for failure_entry in failures:
            retry_stats['total_attempts'] += 1
            group_id = failure_entry['group_id']
            group_name = failure_entry['group_name']
            
            # Check if already sent (skip if yes)
            if msg_id in sent_history and group_id in sent_history[msg_id]:
                print(f"  ⏭️  Already sent to {group_name} - SKIPPING")
                retry_stats['successes'] += 1  # Count as success since it's already there
                remove_from_failed_messages(msg_id, group_id)
                continue
            
            # Find group config
            group_config = None
            for g in groups.values():
                if g['id'] == group_id:
                    group_config = g
                    break
            
            if not group_config:
                print(f"  ⚠️  Group config not found for {group_name}")
                retry_stats['still_failed'] += 1
                continue
            
            print(f"\n  🔄 Attempting: {group_name}")
            print(f"     Previous error: {failure_entry['error'][:80]}")
            
            # REFETCH FRESH MESSAGE FOR THIS SPECIFIC GROUP
            print(f"  🔄 Fetching FRESH message for {group_name}...")
            message = await refetch_message(msg_id)
            
            if not message:
                print(f"  ⚠️  Message {msg_id} not found (may have been deleted)")
                retry_stats['permanent_failed'] += 1
                save_permanent_failed(msg_id, group_id, group_name, "Message deleted or not found")
                remove_from_failed_messages(msg_id, group_id)
                continue
            
            # Try to send with FRESH message and auto-refetch
            sent_msg, message_type, has_caption, is_pinned = await send_message_to_group_with_refetch(
                message, group_id, group_config
            )
            
            if sent_msg == "PERMANENT_FAIL":
                # Permanent failure
                retry_stats['permanent_failed'] += 1
                print(f"  ⛔ PERMANENT FAIL - Cannot recover this file")
                save_permanent_failed(msg_id, group_id, group_name, 
                                    "File reference permanently expired or self-destructing media")
                remove_from_failed_messages(msg_id, group_id)
                
            elif sent_msg:
                # SUCCESS!
                retry_stats['successes'] += 1
                icon_map = {'video': '🎥', 'photo': '📷', 'gif': '🎞️', 'text': '💬', 'document': '📄'}
                icon = icon_map.get(message_type, '❓')
                
                print(f"  ✅ {icon} SUCCESS! Sent {message_type} to {group_name}")
                
                # Log success
                save_to_log(msg_id, group_id, sent_msg.id, group_name, message_type, has_caption, is_pinned)
                log_retry_success(msg_id, group_id, group_name, message_type)
                
                # Update history
                if msg_id not in sent_history:
                    sent_history[msg_id] = {}
                sent_history[msg_id][group_id] = message_type
                
                # Remove from failed list
                remove_from_failed_messages(msg_id, group_id)
                
                await asyncio.sleep(3)
            else:
                # Still failed
                retry_stats['still_failed'] += 1
                print(f"  ❌ Still failed after retry")
    
    # Summary
    print("\n" + "="*70)
    print("📊 RETRY SUMMARY")
    print("="*70)
    print(f"  Total retry attempts: {retry_stats['total_attempts']}")
    print(f"  ✅ Successful: {retry_stats['successes']}")
    print(f"  ❌ Still failed: {retry_stats['still_failed']}")
    print(f"  ⛔ Permanent failures: {retry_stats['permanent_failed']}")
    print("="*70 + "\n")
    
    if retry_stats['successes'] > 0:
        print(f"✅ Successfully retried {retry_stats['successes']} message(s)!")
        print(f"📝 Success log saved to: {retry_success_file}\n")
    
    if retry_stats['permanent_failed'] > 0:
        print(f"⛔ {retry_stats['permanent_failed']} message(s) permanently failed")
        print(f"📝 Check {permanent_failed_file} for details\n")
    
    remaining_failed = load_failed_messages()
    if remaining_failed:
        print(f"⚠️  {len(remaining_failed)} message(s) still in failed list")
        print(f"📝 Check {failed_messages_file} for details\n")
    else:
        print(f"🎉 All retryable messages successfully sent!\n")

async def main():
    """Main function - ULTIMATE VERSION with fresh refetch per group"""
    
    print("\n" + "="*70)
    print("🚀 TELEGRAM MESSAGE SENDER - ULTIMATE EDITION")
    print("="*70)
    print("✅ Fetches 100% of saved messages")
    print("✅ Fresh refetch for EACH group (never uses stale references)")
    print("✅ Checks sent history - skips already sent")
    print("✅ Retries all failed messages from logs")
    print("✅ Never crashes - runs until 100% done")
    print("="*70 + "\n")
    
    # Connect with unlimited retries
    connected = False
    connect_attempts = 0
    while not connected:
        connect_attempts += 1
        try:
            await client.start()
            connected = True
        except Exception as e:
            log_error(f"Connection attempt {connect_attempts} failed: {e}")
            print(f"⚠️  Connection attempt {connect_attempts} failed: {e}")
            print("   Retrying in 30 seconds...")
            await asyncio.sleep(30)
    
    me = await client.get_me()
    print(f"✅ Logged in as: {me.first_name} (@{me.username})\n")

    # Check for failed messages
    failed_list = load_failed_messages()
    if failed_list:
        print(f"⚠️  FOUND {len(failed_list)} FAILED MESSAGE(S) FROM PREVIOUS RUN!")
        print(f"{'='*70}\n")
        try:
            retry_choice = input("Do you want to retry failed messages first? (y/n): ").strip().lower()
            if retry_choice == 'y':
                await retry_failed_messages()
                print("\nContinuing to main upload...\n")
        except (EOFError, KeyboardInterrupt):
            print("\nSkipping retry, continuing to main upload...\n")

    # Load history
    sent_history = load_sent_history()
    total_history = sum(len(groups) for groups in sent_history.values())
    print(f"📊 LOADED HISTORY:")
    print(f"   🔢 Unique messages: {len(sent_history)}")
    print(f"   📤 Total sends tracked: {total_history}")
    
    if sent_history:
        type_counts = {'video': 0, 'photo': 0, 'gif': 0, 'text': 0, 'document': 0}
        for msg_id, groups_data in sent_history.items():
            for group_id, msg_type in groups_data.items():
                if msg_type in type_counts:
                    type_counts[msg_type] += 1
        
        print(f"   📊 By type: 🎥 {type_counts['video']}, 📷 {type_counts['photo']}, 🎞️  {type_counts['gif']}, 💬 {type_counts['text']}\n")
    else:
        print(f"   ℹ️  No previous history - will send all messages\n")

    # Check checkpoint
    checkpoint = load_checkpoint()
    if checkpoint:
        print(f"🔄 Checkpoint found: {checkpoint['last_processed_index']}/{checkpoint['total_messages']}")
        try:
            resume = input("   Resume? (y/n): ").strip().lower()
            if resume != 'y':
                checkpoint = None
                print("   Starting fresh...\n")
        except (EOFError, KeyboardInterrupt):
            print("   Resuming from checkpoint...\n")

    # Select groups
    print("Select groups:")
    print(f"1. {groups['1']['name']} - EVERYTHING + PINS")
    print(f"2. {groups['2']['name']} - MEDIA ONLY")
    print(f"3. {groups['3']['name']} - MEDIA ONLY")
    print("4. All groups")
    
    choice = None
    while choice not in ['1', '2', '3', '4']:
        try:
            choice = input("\nChoice (1/2/3/4): ").strip()
            if choice not in ['1', '2', '3', '4']:
                print("❌ Invalid. Enter 1, 2, 3, or 4.")
        except (EOFError, KeyboardInterrupt):
            print("\n⚠️  Please choose a group.")
            continue
    
    selected_groups = []
    if choice == '4':
        selected_groups = [(g['id'], g['name'], g) for g in groups.values()]
    else:
        g = groups[choice]
        selected_groups = [(g['id'], g['name'], g)]

    print(f"\n🚀 Processing messages...\n")
    print("="*70)
    print("⚠️  IMPORTANT: LEAVE THIS WINDOW OPEN")
    print("⚠️  Script will handle all errors automatically")
    print("⚠️  Fresh refetch for EACH group (no stale references)")
    print("⚠️  Already-sent messages will be skipped")
    print("⚠️  Will run until 100% complete")
    print("="*70 + "\n")
    
    # Stats
    scan_stats = {
        'videos': 0,
        'photos': 0,
        'gifs': 0,
        'text': 0,
        'pinned': 0,
        'total': 0
    }
    
    upload_stats = {
        'videos': 0,
        'photos': 0,
        'gifs': 0,
        'text': 0,
        'documents': 0,
        'skipped': 0,
        'pinned': 0,
        'failed': 0,
        'permanent_failed': 0
    }
    
    # Scan with unlimited retries
    print("🔍 Phase 1: Scanning ALL saved messages...\n")
    messages_to_send = []
    
    scan_complete = False
    scan_attempts = 0
    while not scan_complete:
        scan_attempts += 1
        try:
            # Fetch ALL messages from saved messages
            async for message in client.iter_messages('me', limit=None):
                scan_stats['total'] += 1
                
                if message.pinned:
                    scan_stats['pinned'] += 1
                
                # Check for videos
                if message.video:
                    scan_stats['videos'] += 1
                    messages_to_send.append(message)
                # Check for photos
                elif message.photo:
                    scan_stats['photos'] += 1
                    messages_to_send.append(message)
                # Check for GIFs
                elif message.document:
                    if is_gif_document(message.document):
                        scan_stats['gifs'] += 1
                        messages_to_send.append(message)
                    elif any(g[2]['send_text_messages'] for g in selected_groups):
                        messages_to_send.append(message)
                # Check for text
                elif message.text:
                    if any(g[2]['send_text_messages'] for g in selected_groups):
                        scan_stats['text'] += 1
                        messages_to_send.append(message)
                
                if scan_stats['total'] % 100 == 0:
                    print(f"  📡 Scanned {scan_stats['total']}... (Found {len(messages_to_send)})", end='\r')
            
            scan_complete = True
            print(f"\n✅ Scan complete! Found {len(messages_to_send)} messages to process\n")
            print_progress(scan_stats, None)
            
        except Exception as e:
            log_error(f"Scan error attempt {scan_attempts}: {e}")
            print(f"\n⚠️  Scan error (Attempt {scan_attempts}): {e}")
            print("   Retrying in 30 seconds...")
            await asyncio.sleep(30)
    
    if len(messages_to_send) == 0:
        print("✅ Nothing to send!")
        return
    
    # Upload
    print("⬆️  Phase 2: Uploading with fresh refetch per group...\n")
    
    messages_to_send.reverse()
    start_idx = checkpoint.get('last_processed_index', 0) if checkpoint else 0
    
    if start_idx > 0:
        print(f"📍 Resuming from message {start_idx + 1}/{len(messages_to_send)}\n")
    
    for idx in range(start_idx, len(messages_to_send)):
        original_message = messages_to_send[idx]
        
        for group_id, group_name, group_config in selected_groups:
            
            # Check if already sent (SKIP if yes)
            if original_message.id in sent_history and group_id in sent_history[original_message.id]:
                upload_stats['skipped'] += 1
                skip_type = sent_history[original_message.id][group_id]
                skip_icon = {"video": "🎥", "photo": "📷", "gif": "🎞️", "text": "💬"}.get(skip_type, "📄")
                remaining = len(messages_to_send) - idx - 1
                print(f"⏭️  [{idx+1:>5}/{len(messages_to_send)}] {skip_icon} SKIPPED → {group_name:<10} | {remaining:>5} left")
                continue
            
            # REFETCH FRESH MESSAGE FOR EACH GROUP
            print(f"🔄 [{idx+1:>5}/{len(messages_to_send)}] Refetching fresh message for {group_name}...")
            message = await refetch_message(original_message.id)
            
            if not message:
                upload_stats['permanent_failed'] += 1
                error_reason = "Message deleted or not found in Saved Messages"
                log_error(f"Message {original_message.id} not found")
                save_permanent_failed(original_message.id, group_id, group_name, error_reason)
                print(f"  ⛔ Message deleted - cannot send")
                continue
            
            # Send message with full error handling and auto-refetch
            try:
                sent_msg, message_type, has_caption, is_pinned = await send_message_to_group_with_refetch(
                    message, group_id, group_config
                )
                
                if sent_msg == "PERMANENT_FAIL":
                    # Permanent failure
                    upload_stats['permanent_failed'] += 1
                    error_reason = "File reference permanently expired or self-destructing media"
                    log_error(f"Permanent fail for message {message.id} to {group_name}: {error_reason}")
                    save_permanent_failed(message.id, group_id, group_name, error_reason)
                    print(f"  ⛔ PERMANENT FAIL [{idx+1}/{len(messages_to_send)}] → {group_name} (logged)")
                    
                elif sent_msg:
                    # Success!
                    icon_map = {
                        'video': '🎥',
                        'photo': '📷',
                        'gif': '🎞️',
                        'text': '💬',
                        'document': '📄'
                    }
                    icon = icon_map.get(message_type, '❓')
                    
                    if message_type == 'video':
                        upload_stats['videos'] += 1
                    elif message_type == 'photo':
                        upload_stats['photos'] += 1
                    elif message_type == 'gif':
                        upload_stats['gifs'] += 1
                    elif message_type == 'text':
                        upload_stats['text'] += 1
                    elif message_type == 'document':
                        upload_stats['documents'] += 1
                    
                    if is_pinned:
                        upload_stats['pinned'] += 1
                    
                    remaining = len(messages_to_send) - idx - 1
                    caption_status = "📝" if has_caption else "⭕"
                    pin_status = " 📌" if is_pinned else ""
                    
                    print(f"{icon} [{idx+1:>5}/{len(messages_to_send)}] {message_type.upper():<8} → {group_name:<10} {caption_status}{pin_status} | {remaining:>5} left")
                    
                    # Log success
                    save_to_log(message.id, group_id, sent_msg.id, group_name, message_type, has_caption, is_pinned)
                    
                    # Update in-memory history
                    if message.id not in sent_history:
                        sent_history[message.id] = {}
                    sent_history[message.id][group_id] = message_type
                    
                    # Safe delay
                    if message_type in ['video', 'photo', 'gif']:
                        await asyncio.sleep(3)
                    else:
                        await asyncio.sleep(1.5)
                else:
                    # Failed after all retries
                    upload_stats['failed'] += 1
                    error_reason = "Max retry attempts reached"
                    log_error(f"Failed to send message {message.id} to {group_name}: {error_reason}")
                    save_failed_message(message.id, group_id, group_name, error_reason)
                    print(f"  ❌ FAILED [{idx+1}/{len(messages_to_send)}] → {group_name} (logged)")
                    
            except Exception as e:
                # Critical unexpected error
                upload_stats['failed'] += 1
                error_reason = f"{type(e).__name__}: {str(e)}"
                log_error(f"Critical error sending message {message.id} to {group_name}: {error_reason}")
                save_failed_message(message.id, group_id, group_name, error_reason)
                print(f"  ❌ ERROR: {e}")
        
        # Save checkpoint after EVERY message
        save_checkpoint(idx + 1, len(messages_to_send))
        
        if (idx + 1) % 10 == 0:
            print_progress(scan_stats, upload_stats, f"Progress: {idx+1}/{len(messages_to_send)}")

    # Final summary
    print("\n" + "="*70)
    print("🎉 MISSION COMPLETE!")
    print("="*70)
    
    total_sent = upload_stats['videos'] + upload_stats['photos'] + upload_stats['gifs'] + upload_stats['text']
    print(f"\n📊 FINAL STATS:")
    print(f"  ✅ Successfully sent: {total_sent}")
    print(f"  ⏭️  Skipped (already sent): {upload_stats['skipped']}")
    if upload_stats['failed'] > 0:
        print(f"  ❌ Failed: {upload_stats['failed']}")
        print(f"     (Check failed_messages.json for details)")
        print(f"     💡 Run script again and choose 'Retry failed messages' option!")
    if upload_stats['permanent_failed'] > 0:
        print(f"  ⛔ Permanent failures: {upload_stats['permanent_failed']}")
        print(f"     (Check permanent_failed.json - these cannot be recovered)")
    print(f"\n📊 BREAKDOWN:")
    print(f"  🎥 Videos: {upload_stats['videos']}")
    print(f"  📷 Photos: {upload_stats['photos']}")
    print(f"  🎞️  GIFs: {upload_stats['gifs']}")
    print(f"  💬 Text: {upload_stats['text']}")
    if upload_stats['pinned'] > 0:
        print(f"  📌 Pinned: {upload_stats['pinned']}")
    print("="*70 + "\n")
    
    # Cleanup checkpoint
    if os.path.exists(checkpoint_file):
        try:
            os.remove(checkpoint_file)
            print("✅ Checkpoint cleaned up")
        except:
            pass

if __name__ == "__main__":
    print("\n" + "="*70)
    print("🚀 TELEGRAM MESSAGE SENDER - ULTIMATE EDITION")
    print("="*70)
    print("   Version: 7.0 - ULTIMATE FIX")
    print("   Features:")
    print("     ✓ Fetches ALL saved messages (100%)")
    print("     ✓ Fresh refetch for EACH group (no stale refs)")
    print("     ✓ Checks sent history - skips already sent")
    print("     ✓ Retries failed messages from logs")
    print("     ✓ Auto-refetch on file reference errors")
    print("     ✓ Separates permanent failures")
    print("     ✓ Never crashes - runs until 100% done")
    print("     ✓ Progress saved every single message")
    print("="*70 + "\n")
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n" + "="*70)
        print("⏹️  STOPPED BY USER")
        print("="*70)
        print("✅ Progress has been saved!")
        print("💡 Run the script again to resume from where you left off.")
        print("="*70)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {type(e).__name__}: {e}")
        log_error(f"Main error: {type(e).__name__}: {e}")
        print("📝 Error logged to error_log.txt")
        print("💡 Try running the script again - progress is saved!")
    finally:
        try:
            if client.is_connected():
                asyncio.run(client.disconnect())
        except:
            pass
        print("\n✅ Session ended safely.\n")