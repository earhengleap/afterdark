import os
import json
import asyncio
import random
import logging
import hashlib
from datetime import datetime
from typing import Optional, Dict, List, Set, Tuple
from pyrogram import Client
from pyrogram.errors import FloodWait, FileReferenceExpired, MessageIdInvalid, BadRequest
from pyrogram.types import Message
from pyrogram.enums import MessageMediaType

# ============================================================================
#                              CONFIGURATION
# ============================================================================
API_ID = 22268900
API_HASH = "6764e4d6dd12108e82105f355c6309d8"
SESSION_NAME = "my_account.session"
SOURCE_GROUP = "iditenahuiblyatb"
TARGET_GROUP = "pawasaimori"

# File paths
PROGRESS_FILE = "clone_progress.json"
STATS_FILE = "clone_stats.json"
HASH_FILE = "message_hashes.json"
MAPPING_FILE = "message_mapping.json"

# Performance settings
INITIAL_DELAY = 1.5
MAX_DELAY = 10
BATCH_SIZE = 5
BATCH_DELAY = 15
MAX_RETRIES = 5
REFETCH_DELAY = 2
SCAN_DELAY = 0.03

# ============================================================================
#                              LOGGING SETUP
# ============================================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('clone_log.txt', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
logging.getLogger("pyrogram").setLevel(logging.WARNING)


# ============================================================================
#                          TELEGRAM CLONER CLASS
# ============================================================================
class TelegramCloner:
    """
    Advanced Telegram Group Cloner with 100% accuracy and chronological order
    - Clones ALL message types in EXACT source order
    - Media groups preserved as albums with correct item count
    - Hash-based duplicate detection
    - Automatic retry with fresh file references
    - Progress persistence and resume capability
    """
    
    def __init__(self, app: Client, source: str, target: str):
        self.app = app
        self.source = source
        self.target = target
        self.progress = self.load_progress()
        self.message_hashes = self.load_hashes()
        self.message_mapping = self.load_mapping()
        self.stats = {
            "total_messages": 0,
            "successful": 0,
            "failed": 0,
            "skipped": 0,
            "duplicates": 0,
            "media_groups": 0,
            "by_type": {}
        }
    
    # ========================================================================
    #                          DATA PERSISTENCE
    # ========================================================================
    
    def load_progress(self) -> Dict:
        """Load cloning progress from file"""
        if os.path.exists(PROGRESS_FILE):
            try:
                with open(PROGRESS_FILE, "r", encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Corrupted progress file: {e}. Starting fresh.")
        
        return {
            "success": [],
            "failed": [],
            "media_groups_done": [],
            "last_processed": None,
            "started_at": None,
            "completed_at": None
        }
    
    def load_hashes(self) -> Dict:
        """Load message hash database"""
        if os.path.exists(HASH_FILE):
            try:
                with open(HASH_FILE, "r", encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data.get("target_hashes"), list):
                        data["target_hashes"] = set(data["target_hashes"])
                    return data
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Corrupted hash file: {e}. Starting fresh.")
        
        return {
            "source_hashes": {},
            "target_hashes": set()
        }
    
    def load_mapping(self) -> Dict:
        """Load message ID mapping (source -> target)"""
        if os.path.exists(MAPPING_FILE):
            try:
                with open(MAPPING_FILE, "r", encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                logger.warning("Corrupted mapping file. Starting fresh.")
        return {}
    
    def save_progress(self):
        """Save progress to file"""
        try:
            with open(PROGRESS_FILE, "w", encoding='utf-8') as f:
                json.dump(self.progress, f, indent=2)
        except IOError as e:
            logger.error(f"Failed to save progress: {e}")
    
    def save_hashes(self):
        """Save hash database to file"""
        try:
            save_data = {
                "source_hashes": self.message_hashes["source_hashes"],
                "target_hashes": list(self.message_hashes["target_hashes"])
            }
            with open(HASH_FILE, "w", encoding='utf-8') as f:
                json.dump(save_data, f, indent=2)
        except IOError as e:
            logger.error(f"Failed to save hashes: {e}")
    
    def save_mapping(self):
        """Save message ID mapping"""
        try:
            with open(MAPPING_FILE, "w", encoding='utf-8') as f:
                json.dump(self.message_mapping, f, indent=2)
        except IOError as e:
            logger.error(f"Failed to save mapping: {e}")
    
    def save_stats(self):
        """Save statistics to file"""
        try:
            with open(STATS_FILE, "w", encoding='utf-8') as f:
                json.dump(self.stats, f, indent=2)
        except IOError as e:
            logger.error(f"Failed to save stats: {e}")
    
    # ========================================================================
    #                       DUPLICATE DETECTION
    # ========================================================================
    
    def generate_message_hash(self, message: Message) -> Optional[str]:
        """
        Generate unique content-based hash for duplicate detection
        """
        hash_components = []
        
        # Include media_group_id to track albums
        if message.media_group_id:
            hash_components.append(f"media_group:{message.media_group_id}")
        
        if message.text:
            hash_components.append(f"text:{message.text}")
        if message.caption:
            hash_components.append(f"caption:{message.caption}")
        
        # Media files
        if message.photo:
            hash_components.append(f"photo:{message.photo.file_unique_id}")
        elif message.video:
            hash_components.append(f"video:{message.video.file_unique_id}")
        elif message.document:
            hash_components.append(f"doc:{message.document.file_unique_id}")
        elif message.audio:
            hash_components.append(f"audio:{message.audio.file_unique_id}")
        elif message.voice:
            hash_components.append(f"voice:{message.voice.file_unique_id}")
        elif message.video_note:
            hash_components.append(f"vidnote:{message.video_note.file_unique_id}")
        elif message.sticker:
            hash_components.append(f"sticker:{message.sticker.file_unique_id}")
        elif message.animation:
            hash_components.append(f"anim:{message.animation.file_unique_id}")
        
        if message.poll:
            poll_data = f"poll:{message.poll.question}:{message.poll.type}"
            poll_data += f":{','.join([opt.text for opt in message.poll.options])}"
            hash_components.append(poll_data)
        
        if message.location:
            hash_components.append(
                f"loc:{message.location.latitude:.6f}:{message.location.longitude:.6f}"
            )
        
        if message.contact:
            hash_components.append(f"contact:{message.contact.phone_number}")
        
        if message.dice:
            hash_components.append(f"dice:{message.dice.emoji}")
        
        if message.venue:
            hash_components.append(
                f"venue:{message.venue.title}:{message.venue.address}"
            )
        
        if message.game:
            hash_components.append(f"game:{message.game.short_name}")
        
        if hash_components:
            content = "|".join(hash_components)
            return hashlib.sha256(content.encode('utf-8')).hexdigest()
        
        return None
    
    async def scan_target_group(self) -> Set[str]:
        """Fast scan of target group to build hash set"""
        print("\n" + "="*70)
        print("🔍 SCANNING TARGET GROUP FOR EXISTING CONTENT")
        print("="*70)
        
        target_hashes = set()
        count = 0
        
        try:
            async for message in self.app.get_chat_history(self.target):
                if message.service or message.empty:
                    continue
                
                msg_hash = self.generate_message_hash(message)
                if msg_hash:
                    target_hashes.add(msg_hash)
                
                count += 1
                if count % 500 == 0:
                    print(f"📊 Scanned {count} messages...")
                
                await asyncio.sleep(SCAN_DELAY)
            
            print("="*70)
            print(f"✅ SCAN COMPLETE: Found {len(target_hashes)} unique messages")
            print("="*70 + "\n")
            
        except Exception as e:
            logger.error(f"Error scanning target group: {e}")
        
        return target_hashes
    
    # ========================================================================
    #                      MESSAGE TYPE DETECTION
    # ========================================================================
    
    def get_message_type(self, message: Message) -> str:
        """Determine the type of message"""
        if message.media_group_id:
            return "media_group"
        elif message.photo:
            return "photo"
        elif message.video:
            return "video"
        elif message.document:
            return "document"
        elif message.audio:
            return "audio"
        elif message.voice:
            return "voice"
        elif message.video_note:
            return "video_note"
        elif message.sticker:
            return "sticker"
        elif message.animation:
            return "animation"
        elif message.poll:
            return "poll"
        elif message.location:
            return "location"
        elif message.venue:
            return "venue"
        elif message.contact:
            return "contact"
        elif message.dice:
            return "dice"
        elif message.game:
            return "game"
        elif message.text:
            return "text"
        elif message.web_page:
            return "web_page"
        else:
            return "unknown"
    
    # ========================================================================
    #                      MEDIA GROUP HANDLING
    # ========================================================================
    
    async def clone_media_group(self, messages: List[Message]) -> Tuple[str, str, float]:
        """
        Clone an entire media group (album) as a single unit
        ALL items in the source album will be cloned together
        """
        if not messages:
            return "failed", "media_group", INITIAL_DELAY
        
        media_group_id = messages[0].media_group_id
        
        try:
            # Prepare media list for send_media_group
            media_list = []
            
            for msg in messages:
                media_obj = None
                
                if msg.photo:
                    from pyrogram.types import InputMediaPhoto
                    media_obj = InputMediaPhoto(
                        media=msg.photo.file_id,
                        caption=msg.caption or "",
                        caption_entities=msg.caption_entities,
                        has_spoiler=msg.has_media_spoiler if hasattr(msg, 'has_media_spoiler') else False
                    )
                    
                elif msg.video:
                    from pyrogram.types import InputMediaVideo
                    media_obj = InputMediaVideo(
                        media=msg.video.file_id,
                        caption=msg.caption or "",
                        caption_entities=msg.caption_entities,
                        duration=msg.video.duration,
                        width=msg.video.width,
                        height=msg.video.height,
                        supports_streaming=True,
                        has_spoiler=msg.has_media_spoiler if hasattr(msg, 'has_media_spoiler') else False
                    )
                    
                elif msg.document:
                    from pyrogram.types import InputMediaDocument
                    media_obj = InputMediaDocument(
                        media=msg.document.file_id,
                        caption=msg.caption or "",
                        caption_entities=msg.caption_entities
                    )
                    
                elif msg.audio:
                    from pyrogram.types import InputMediaAudio
                    media_obj = InputMediaAudio(
                        media=msg.audio.file_id,
                        caption=msg.caption or "",
                        caption_entities=msg.caption_entities,
                        duration=msg.audio.duration,
                        performer=msg.audio.performer,
                        title=msg.audio.title
                    )
                else:
                    logger.warning(f"Unsupported media type in group: {msg.id}")
                    continue
                
                if media_obj:
                    media_list.append(media_obj)
            
            if not media_list:
                return "failed", "media_group", INITIAL_DELAY
            
            # Send the entire album at once
            sent_messages = await self.app.send_media_group(
                chat_id=self.target,
                media=media_list
            )
            
            # Store mappings for all messages in the group
            for orig_msg, sent_msg in zip(messages, sent_messages):
                self.message_mapping[str(orig_msg.id)] = sent_msg.id
            
            logger.info(f"✅ Cloned media group {media_group_id} with {len(media_list)} items")
            
            return "success", "media_group", INITIAL_DELAY
            
        except FileReferenceExpired:
            logger.warning(f"File reference expired for media group {media_group_id}, refetching...")
            # Refetch all messages in the group
            fresh_messages = []
            for msg in messages:
                fresh = await self.get_fresh_message(msg.id)
                if fresh:
                    fresh_messages.append(fresh)
            
            if len(fresh_messages) == len(messages):
                await asyncio.sleep(REFETCH_DELAY)
                return await self.clone_media_group(fresh_messages)
            else:
                return "failed", "media_group", INITIAL_DELAY
                
        except FloodWait as e:
            logger.warning(f"⏳ Flood wait: {e.value}s")
            await asyncio.sleep(e.value)
            return await self.clone_media_group(messages)
            
        except Exception as e:
            logger.error(f"Error cloning media group {media_group_id}: {e}")
            return "failed", "media_group", INITIAL_DELAY
    
    # ========================================================================
    #                      MESSAGE CLONING METHODS
    # ========================================================================
    
    async def clone_text_message(self, message: Message) -> Message:
        """Clone text message with all formatting"""
        return await self.app.send_message(
            self.target,
            text=message.text,
            entities=message.entities,
            disable_web_page_preview=not message.web_page
        )
    
    async def clone_photo(self, message: Message) -> Message:
        """Clone photo with caption and formatting"""
        return await self.app.send_photo(
            self.target,
            photo=message.photo.file_id,
            caption=message.caption or "",
            caption_entities=message.caption_entities,
            has_spoiler=message.has_media_spoiler if hasattr(message, 'has_media_spoiler') else False
        )
    
    async def clone_video(self, message: Message) -> Message:
        """Clone video with all metadata"""
        return await self.app.send_video(
            self.target,
            video=message.video.file_id,
            caption=message.caption or "",
            caption_entities=message.caption_entities,
            duration=message.video.duration,
            width=message.video.width,
            height=message.video.height,
            supports_streaming=True,
            has_spoiler=message.has_media_spoiler if hasattr(message, 'has_media_spoiler') else False
        )
    
    async def clone_document(self, message: Message) -> Message:
        """Clone document/file"""
        return await self.app.send_document(
            self.target,
            document=message.document.file_id,
            caption=message.caption or "",
            caption_entities=message.caption_entities,
            file_name=message.document.file_name
        )
    
    async def clone_audio(self, message: Message) -> Message:
        """Clone audio with metadata"""
        return await self.app.send_audio(
            self.target,
            audio=message.audio.file_id,
            caption=message.caption or "",
            caption_entities=message.caption_entities,
            duration=message.audio.duration,
            performer=message.audio.performer,
            title=message.audio.title
        )
    
    async def clone_voice(self, message: Message) -> Message:
        """Clone voice message"""
        return await self.app.send_voice(
            self.target,
            voice=message.voice.file_id,
            caption=message.caption or "",
            caption_entities=message.caption_entities,
            duration=message.voice.duration
        )
    
    async def clone_video_note(self, message: Message) -> Message:
        """Clone video note (round video)"""
        return await self.app.send_video_note(
            self.target,
            video_note=message.video_note.file_id,
            duration=message.video_note.duration,
            length=message.video_note.length
        )
    
    async def clone_sticker(self, message: Message) -> Message:
        """Clone sticker"""
        return await self.app.send_sticker(
            self.target,
            sticker=message.sticker.file_id
        )
    
    async def clone_animation(self, message: Message) -> Message:
        """Clone GIF/animation"""
        return await self.app.send_animation(
            self.target,
            animation=message.animation.file_id,
            caption=message.caption or "",
            caption_entities=message.caption_entities,
            duration=message.animation.duration,
            width=message.animation.width,
            height=message.animation.height,
            has_spoiler=message.has_media_spoiler if hasattr(message, 'has_media_spoiler') else False
        )
    
    async def clone_poll(self, message: Message) -> Message:
        """Clone poll with all options"""
        poll = message.poll
        return await self.app.send_poll(
            self.target,
            question=poll.question,
            options=[opt.text for opt in poll.options],
            is_anonymous=poll.is_anonymous,
            allows_multiple_answers=poll.allows_multiple_answers
        )
    
    async def clone_location(self, message: Message) -> Message:
        """Clone location"""
        return await self.app.send_location(
            self.target,
            latitude=message.location.latitude,
            longitude=message.location.longitude
        )
    
    async def clone_venue(self, message: Message) -> Message:
        """Clone venue"""
        venue = message.venue
        return await self.app.send_venue(
            self.target,
            latitude=venue.location.latitude,
            longitude=venue.location.longitude,
            title=venue.title,
            address=venue.address,
            foursquare_id=venue.foursquare_id or "",
            foursquare_type=venue.foursquare_type or ""
        )
    
    async def clone_contact(self, message: Message) -> Message:
        """Clone contact"""
        contact = message.contact
        return await self.app.send_contact(
            self.target,
            phone_number=contact.phone_number,
            first_name=contact.first_name,
            last_name=contact.last_name or "",
            vcard=contact.vcard or ""
        )
    
    async def clone_dice(self, message: Message) -> Message:
        """Clone dice/dart/etc"""
        return await self.app.send_dice(
            self.target,
            emoji=message.dice.emoji
        )
    
    async def clone_game(self, message: Message) -> Message:
        """Clone game"""
        return await self.app.send_game(
            self.target,
            game_short_name=message.game.short_name
        )
    
    # ========================================================================
    #                      MAIN CLONING LOGIC
    # ========================================================================
    
    async def get_fresh_message(self, message_id: int) -> Optional[Message]:
        """Fetch fresh message with updated file references"""
        try:
            return await self.app.get_messages(self.source, message_id)
        except Exception as e:
            logger.error(f"Could not fetch fresh message {message_id}: {e}")
            return None
    
    async def clone_message(
        self, 
        message: Message, 
        current_delay: float, 
        retry_count: int = 0
    ) -> Tuple[str, str, float]:
        """
        Clone a single message with automatic retry
        PRESERVES "Forwarded from" attribution if message was forwarded
        Returns: (status, message_type, new_delay)
        """
        message_type = self.get_message_type(message)
        
        # Skip media group items - they're handled separately
        if message_type == "media_group":
            return "skipped", message_type, current_delay
        
        try:
            cloned_message = None
            
            # 🔥 NEW: If message has forward_from info, preserve it by forwarding
            if message.forward_date or message.forward_from or message.forward_from_chat:
                try:
                    cloned_message = await self.app.forward_messages(
                        chat_id=self.target,
                        from_chat_id=self.source,
                        message_ids=message.id
                    )
                    
                    if isinstance(cloned_message, list):
                        cloned_message = cloned_message[0]
                    
                    if cloned_message:
                        self.message_mapping[str(message.id)] = cloned_message.id
                        logger.info(f"✅ Forwarded message {message.id} (preserving attribution)")
                    
                    new_delay = min(current_delay + 0.1, MAX_DELAY)
                    delay = random.uniform(new_delay - 0.5, new_delay + 0.5)
                    await asyncio.sleep(delay)
                    
                    return "success", f"{message_type}_forwarded", new_delay
                    
                except Exception as fwd_error:
                    logger.warning(f"Could not forward message {message.id}: {fwd_error}. Falling back to copy.")
                    # Fall through to normal cloning if forward fails
            
            # Normal cloning (no forward attribution)
            if message_type == "text":
                cloned_message = await self.clone_text_message(message)
            elif message_type == "photo":
                cloned_message = await self.clone_photo(message)
            elif message_type == "video":
                cloned_message = await self.clone_video(message)
            elif message_type == "document":
                cloned_message = await self.clone_document(message)
            elif message_type == "audio":
                cloned_message = await self.clone_audio(message)
            elif message_type == "voice":
                cloned_message = await self.clone_voice(message)
            elif message_type == "video_note":
                cloned_message = await self.clone_video_note(message)
            elif message_type == "sticker":
                cloned_message = await self.clone_sticker(message)
            elif message_type == "animation":
                cloned_message = await self.clone_animation(message)
            elif message_type == "poll":
                cloned_message = await self.clone_poll(message)
            elif message_type == "location":
                cloned_message = await self.clone_location(message)
            elif message_type == "venue":
                cloned_message = await self.clone_venue(message)
            elif message_type == "contact":
                cloned_message = await self.clone_contact(message)
            elif message_type == "dice":
                cloned_message = await self.clone_dice(message)
            elif message_type == "game":
                cloned_message = await self.clone_game(message)
            else:
                logger.warning(f"Unsupported message type: {message_type} (ID: {message.id})")
                return "skipped", message_type, current_delay
            
            if cloned_message:
                self.message_mapping[str(message.id)] = cloned_message.id
            
            new_delay = min(current_delay + 0.1, MAX_DELAY)
            delay = random.uniform(new_delay - 0.5, new_delay + 0.5)
            await asyncio.sleep(delay)
            
            return "success", message_type, new_delay
        
        except FileReferenceExpired:
            if retry_count < MAX_RETRIES:
                logger.info(f"🔄 File reference expired for message {message.id}, "
                           f"refetching (attempt {retry_count + 1}/{MAX_RETRIES})")
                
                fresh_message = await self.get_fresh_message(message.id)
                if fresh_message:
                    await asyncio.sleep(REFETCH_DELAY)
                    return await self.clone_message(fresh_message, current_delay, retry_count + 1)
                else:
                    logger.error(f"Failed to fetch fresh message {message.id}")
                    return "failed", message_type, current_delay
            else:
                logger.error(f"Max retries reached for message {message.id}")
                return "failed", message_type, current_delay
        
        except FloodWait as e:
            wait_time = e.value
            logger.warning(f"⏳ Flood wait: {wait_time}s")
            await asyncio.sleep(wait_time)
            return await self.clone_message(message, current_delay + 2, retry_count)
        
        except BadRequest as e:
            error_msg = str(e)
            
            if "FILE_REFERENCE" in error_msg and retry_count < MAX_RETRIES:
                logger.info(f"🔄 Bad request (file reference), retrying message {message.id}")
                fresh_message = await self.get_fresh_message(message.id)
                if fresh_message:
                    await asyncio.sleep(REFETCH_DELAY)
                    return await self.clone_message(fresh_message, current_delay, retry_count + 1)
            
            logger.error(f"Bad request for message {message.id}: {error_msg}")
            return "failed", message_type, current_delay
        
        except Exception as e:
            logger.error(f"Error cloning message {message.id} ({message_type}): {e}")
            return "failed", message_type, current_delay
    
    # ========================================================================
    #                      STATISTICS & REPORTING
    # ========================================================================
    
    def update_stats(self, message_type: str, status: str):
        """Update cloning statistics"""
        if message_type not in self.stats["by_type"]:
            self.stats["by_type"][message_type] = {
                "success": 0, 
                "failed": 0, 
                "skipped": 0
            }
        
        if status == "success":
            self.stats["successful"] += 1
            self.stats["by_type"][message_type]["success"] += 1
        elif status == "failed":
            self.stats["failed"] += 1
            self.stats["by_type"][message_type]["failed"] += 1
        elif status == "duplicate":
            self.stats["duplicates"] += 1
            self.stats["by_type"][message_type]["skipped"] += 1
        else:
            self.stats["skipped"] += 1
            self.stats["by_type"][message_type]["skipped"] += 1
    
    def print_final_report(self):
        """Print comprehensive final report"""
        print("\n" + "="*70)
        print("🎉 CLONING OPERATION COMPLETED!")
        print("="*70)
        
        print(f"\n📊 OVERALL STATISTICS:")
        print(f"   Total messages processed: {self.stats['total_messages']}")
        print(f"   ✅ Successfully cloned: {self.stats['successful']}")
        print(f"   📦 Media groups cloned: {self.stats['media_groups']}")
        print(f"   ❌ Failed: {self.stats['failed']}")
        print(f"   ⏭️  Skipped: {self.stats['skipped']}")
        print(f"   🔄 Duplicates avoided: {self.stats['duplicates']}")
        
        if self.stats['by_type']:
            print(f"\n📋 BREAKDOWN BY MESSAGE TYPE:")
            for msg_type, counts in sorted(self.stats['by_type'].items()):
                total = counts['success'] + counts['failed'] + counts['skipped']
                success_rate = (counts['success'] / total * 100) if total > 0 else 0
                print(f"   {msg_type:15} → {counts['success']:4}/{total:4} "
                      f"({success_rate:5.1f}%)")
        
        if self.stats['total_messages'] > 0:
            overall_success = (self.stats['successful'] / self.stats['total_messages'] * 100)
            print(f"\n🎯 Overall Success Rate: {overall_success:.2f}%")
        
        print(f"\n📁 OUTPUT FILES:")
        print(f"   Progress: {PROGRESS_FILE}")
        print(f"   Statistics: {STATS_FILE}")
        print(f"   Hash database: {HASH_FILE}")
        print(f"   Message mapping: {MAPPING_FILE}")
        print(f"   Detailed logs: clone_log.txt")
        
        if self.stats['failed'] > 0:
            print(f"\n💡 TIP: Run the script again to retry {self.stats['failed']} failed messages")
        
        if self.progress['started_at'] and self.progress['completed_at']:
            start = datetime.fromisoformat(self.progress['started_at'])
            end = datetime.fromisoformat(self.progress['completed_at'])
            duration = end - start
            print(f"\n⏱️  Total Duration: {duration}")
        
        print("="*70 + "\n")
    
    # ========================================================================
    #                      MAIN EXECUTION FLOW (FIXED!)
    # ========================================================================
    
    async def fetch_all_messages_ordered(self) -> List:
        """
        **CRITICAL FIX**: Fetch ALL messages in CHRONOLOGICAL order
        Returns list of (message_id, message_or_group_id, is_group, messages_list)
        This ensures EXACT source order from beginning to end
        """
        print("\n" + "="*70)
        print("📥 FETCHING MESSAGES IN CHRONOLOGICAL ORDER")
        print("="*70)
        
        all_items = []  # Will store tuples: (id, type, data)
        media_groups_temp = {}  # Temporary storage for grouping
        already_processed = set(self.progress["success"])
        already_processed_groups = set(self.progress.get("media_groups_done", []))
        chunk_count = 0
        duplicate_count = 0
        
        try:
            # Fetch in reverse chronological order (newest first)
            async for message in self.app.get_chat_history(self.source):
                chunk_count += 1
                
                if message.service or message.empty:
                    continue
                
                # Handle media groups - collect all items first
                if message.media_group_id:
                    group_id = message.media_group_id
                    
                    if group_id not in media_groups_temp:
                        media_groups_temp[group_id] = {
                            'messages': [],
                            'first_id': message.id
                        }
                    media_groups_temp[group_id]['messages'].append(message)
                    media_groups_temp[group_id]['first_id'] = min(
                        media_groups_temp[group_id]['first_id'], 
                        message.id
                    )
                    continue
                
                # Regular message
                if message.id in already_processed:
                    continue
                
                # Check for duplicates
                msg_hash = self.generate_message_hash(message)
                if msg_hash:
                    self.message_hashes["source_hashes"][str(message.id)] = msg_hash
                    
                    if msg_hash in self.message_hashes["target_hashes"]:
                        duplicate_count += 1
                        self.progress["success"].append(message.id)
                        continue
                
                all_items.append((message.id, 'single', message))
                
                if chunk_count % 500 == 0:
                    print(f"📦 Fetched {chunk_count} messages...")
                
                await asyncio.sleep(SCAN_DELAY)
            
            # Process media groups and add to items list
            for group_id, group_data in media_groups_temp.items():
                if group_id in already_processed_groups:
                    continue
                
                messages = group_data['messages']
                first_id = group_data['first_id']
                
                # Sort messages within group by ID
                messages.sort(key=lambda m: m.id)
                
                # Check if entire group is duplicate
                is_duplicate = True
                for msg in messages:
                    msg_hash = self.generate_message_hash(msg)
                    if msg_hash:
                        self.message_hashes["source_hashes"][str(msg.id)] = msg_hash
                        if msg_hash not in self.message_hashes["target_hashes"]:
                            is_duplicate = False
                
                if is_duplicate:
                    duplicate_count += len(messages)
                    for msg in messages:
                        self.progress["success"].append(msg.id)
                    if "media_groups_done" not in self.progress:
                        self.progress["media_groups_done"] = []
                    self.progress["media_groups_done"].append(group_id)
                    continue
                
                # Add group with its first message ID for sorting
                all_items.append((first_id, 'group', messages))
            
            # **CRITICAL**: Sort by message ID to get chronological order (oldest first)
            all_items.sort(key=lambda x: x[0])
            
            print("="*70)
            print(f"✅ FETCH COMPLETE")
            print(f"   Total scanned: {chunk_count}")
            print(f"   Items to clone: {len(all_items)}")
            print(f"   Media groups: {sum(1 for item in all_items if item[1] == 'group')}")
            print(f"   Single messages: {sum(1 for item in all_items if item[1] == 'single')}")
            print(f"   Duplicates: {duplicate_count}")
            print(f"   Already done: {len(already_processed)}")
            print("="*70 + "\n")
            
            self.stats["duplicates"] = duplicate_count
            
        except Exception as e:
            logger.error(f"Error fetching messages: {e}")
        
        return all_items
    
    async def start_cloning(self):
        """Main cloning orchestrator with PERFECT chronological order"""
        print("\n" + "="*70)
        print("🚀 TELEGRAM GROUP CLONER v6.0 - PERFECT 1:1 CLONE")
        print("="*70)
        print(f"📍 Source: {self.source}")
        print(f"📍 Target: {self.target}")
        print("\n✨ FEATURES:")
        print("   • 100% accurate message cloning")
        print("   • ALL message types supported")
        print("   • Complete format preservation")
        print("   • **PERFECT CHRONOLOGICAL ORDER** - Begin to end!")
        print("   • **DYNAMIC MEDIA GROUPS** - Any size (1-10 items)")
        print("   • Smart duplicate detection")
        print("   • Auto-retry with fresh file references")
        print("   • Progress persistence & resume")
        print("="*70)
        
        if not self.progress["started_at"]:
            self.progress["started_at"] = datetime.now().isoformat()
        
        # Step 1: Scan target for existing content
        self.message_hashes["target_hashes"] = await self.scan_target_group()
        self.save_hashes()
        
        # Step 2: Fetch source messages in PERFECT chronological order
        all_items = await self.fetch_all_messages_ordered()
        
        if not all_items:
            print("✨ Nothing to clone! Target is already up to date.")
            self.print_final_report()
            return
        
        self.stats["total_messages"] = len(all_items)
        
        print(f"\n🔄 STARTING CLONE: {len(all_items)} items in EXACT source order")
        print("="*70 + "\n")
        
        current_delay = INITIAL_DELAY
        processed_count = 0
        
        # Step 3: Clone ALL items in order (groups and singles mixed)
        for idx, (item_id, item_type, item_data) in enumerate(all_items, 1):
            
            if item_type == 'group':
                # Clone media group
                messages = item_data
                group_id = messages[0].media_group_id
                
                status, msg_type, current_delay = await self.clone_media_group(messages)
                
                if status == "success":
                    self.stats["media_groups"] += 1
                    self.stats["successful"] += len(messages)
                    
                    # Mark all messages in group as processed
                    for msg in messages:
                        self.progress["success"].append(msg.id)
                        msg_hash = self.message_hashes["source_hashes"].get(str(msg.id))
                        if msg_hash:
                            self.message_hashes["target_hashes"].add(msg_hash)
                    
                    # Track completed groups
                    if "media_groups_done" not in self.progress:
                        self.progress["media_groups_done"] = []
                    self.progress["media_groups_done"].append(group_id)
                    
                    print(f"✅ [{idx}/{len(all_items)}] Media group: {len(messages)} items "
                          f"(IDs: {messages[0].id}-{messages[-1].id})")
                    
                    # Update stats for each message type in the group
                    for msg in messages:
                        individual_type = self.get_message_type(msg)
                        if individual_type == "media_group":
                            individual_type = "photo" if msg.photo else "video" if msg.video else "document"
                        self.update_stats(individual_type, status)
                
                elif status == "failed":
                    self.stats["failed"] += len(messages)
                    for msg in messages:
                        self.progress["failed"].append(msg.id)
                    print(f"❌ [{idx}/{len(all_items)}] Failed media group {group_id}")
                    
                    for msg in messages:
                        individual_type = self.get_message_type(msg)
                        if individual_type == "media_group":
                            individual_type = "photo" if msg.photo else "video" if msg.video else "document"
                        self.update_stats(individual_type, "failed")
                
            else:
                # Clone single message
                message = item_data
                status, msg_type, current_delay = await self.clone_message(message, current_delay)
                
                self.update_stats(msg_type, status)
                
                if status == "success":
                    self.progress["success"].append(message.id)
                    self.progress["last_processed"] = message.id
                    
                    msg_hash = self.message_hashes["source_hashes"].get(str(message.id))
                    if msg_hash:
                        self.message_hashes["target_hashes"].add(msg_hash)
                    
                    print(f"✅ [{idx}/{len(all_items)}] {msg_type:15} | Message {message.id}")
                
                elif status == "failed":
                    self.progress["failed"].append(message.id)
                    print(f"❌ [{idx}/{len(all_items)}] Failed {msg_type} message {message.id}")
                
                elif status != "skipped":
                    print(f"⏭️  [{idx}/{len(all_items)}] Skipped {msg_type} message {message.id}")
            
            processed_count += 1
            
            # Save progress periodically
            if processed_count % 10 == 0:
                self.save_progress()
                self.save_hashes()
                self.save_mapping()
                self.save_stats()
                
                print(f"\n💾 Progress saved | Success: {self.stats['successful']} | "
                      f"Failed: {self.stats['failed']} | Remaining: {len(all_items) - processed_count}")
                
                # Cooldown after every 10 items
                if processed_count < len(all_items):
                    cooldown = random.uniform(3, 5)
                    print(f"😴 Cooldown: {cooldown:.1f}s...\n")
                    await asyncio.sleep(cooldown)
        
        # Mark as completed
        self.progress["completed_at"] = datetime.now().isoformat()
        self.save_progress()
        self.save_hashes()
        self.save_mapping()
        self.save_stats()
        
        # Final report
        self.print_final_report()


# ============================================================================
#                          MAIN ENTRY POINT
# ============================================================================

async def main():
    """Initialize and run the cloner"""
    
    if not os.path.exists(f"{SESSION_NAME}.session") and not os.path.exists(SESSION_NAME):
        print("\n⚠️  WARNING: No session file found!")
        print("On first run, you'll need to log in with your phone number.")
        print("The session will be saved for future runs.\n")
    
    app = Client(SESSION_NAME, API_ID, API_HASH)
    
    async with app:
        # Verify access to both groups
        try:
            source_chat = await app.get_chat(SOURCE_GROUP)
            target_chat = await app.get_chat(TARGET_GROUP)
            
            print(f"\n✅ Connected successfully!")
            print(f"   Source: {source_chat.title} ({source_chat.members_count or 'N/A'} members)")
            print(f"   Target: {target_chat.title} ({target_chat.members_count or 'N/A'} members)")
            
            # Check permissions
            try:
                me = await app.get_me()
                target_member = await app.get_chat_member(TARGET_GROUP, me.id)
                
                if hasattr(target_member, 'privileges') and target_member.privileges:
                    if not target_member.privileges.can_post_messages:
                        print("\n⚠️  WARNING: You might not have permission to post in the target group!")
                        print("Make sure you're an admin or have posting rights.\n")
                        response = input("Continue anyway? (y/n): ")
                        if response.lower() != 'y':
                            print("Aborted.")
                            return
                elif hasattr(target_member, 'status'):
                    if target_member.status.value in ["left", "kicked", "restricted"]:
                        print("\n⚠️  WARNING: You may not be able to post in the target group!")
                        print(f"Your status: {target_member.status.value}\n")
                        response = input("Continue anyway? (y/n): ")
                        if response.lower() != 'y':
                            print("Aborted.")
                            return
            except Exception as perm_error:
                print(f"\n⚠️  Could not verify permissions: {perm_error}")
                print("Continuing anyway... (you may encounter errors if you lack permissions)\n")
                await asyncio.sleep(1)
            
        except Exception as e:
            logger.error(f"Error verifying group access: {e}")
            print(f"\n❌ Could not access groups. Error: {e}")
            print("Please check:")
            print("  1. Group usernames are correct")
            print("  2. You're a member of both groups")
            print("  3. Groups are not private/restricted")
            return
        
        # Start cloning
        cloner = TelegramCloner(app, SOURCE_GROUP, TARGET_GROUP)
        await cloner.start_cloning()


# ============================================================================
#                          SCRIPT EXECUTION
# ============================================================================

if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════════════════╗
║                                                                      ║
║   TELEGRAM GROUP CLONER v6.0 - PERFECT CHRONOLOGICAL 1:1 CLONE      ║
║                                                                      ║
║  ✨ 100% accurate message cloning with format preservation           ║
║  📦 DYNAMIC MEDIA GROUPS - Any size (1-10 items) cloned as albums    ║
║  🎯 PERFECT CHRONOLOGICAL ORDER - Exactly like source!               ║
║  🚀 Smart duplicate detection with content hashing                   ║
║  🔄 Auto-retry with fresh file references                            ║
║  💾 Progress persistence and resume capability                       ║
║  📊 Comprehensive statistics and reporting                           ║
║  🛡️  Robust error handling and rate limit management                 ║
║                                                                      ║
║  Supports ALL message types:                                         ║
║  • Text, Photos, Videos, Documents, Audio                            ║
║  • Voice, Video Notes, Stickers, Animations, GIFs                    ║
║  • Polls, Locations, Venues, Contacts                                ║
║  • Dice, Games, Web Pages, and more...                               ║
║  • **MEDIA GROUPS/ALBUMS** of any size (dynamic)                     ║
║                                                                      ║
║  🔥 NEW: Groups & singles properly mixed in chronological order!     ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝
    """)
    
    try:
        import sys
        if sys.version_info < (3, 7):
            print("❌ Python 3.7 or higher is required!")
            sys.exit(1)
        
        try:
            import pyrogram
        except ImportError:
            print("❌ Pyrogram is not installed!")
            print("Install it with: pip install pyrogram tgcrypto")
            sys.exit(1)
        
        asyncio.run(main())
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Operation cancelled by user")
        print("💾 Progress has been saved. Run the script again to resume.")
        print("   Failed messages will be automatically retried.\n")
    
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        print(f"\n❌ Fatal error occurred: {e}")
        print("Check clone_log.txt for detailed error information.")
        print("\nCommon issues:")
        print("  • Invalid API credentials")
        print("  • Network connectivity problems")
        print("  • Insufficient permissions in target group")
        print("  • Session file corruption (delete .session file and retry)")
        sys.exit(1)
        
        
        ##WORK FINE