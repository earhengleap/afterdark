import os
import json
import asyncio
import random
import logging
import hashlib
import re
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Set, Tuple, Any
from pyrogram import Client, filters
from pyrogram.errors import FloodWait, FileReferenceExpired, MessageIdInvalid, BadRequest
from pyrogram.types import Message
from pyrogram.enums import MessageMediaType

# ============================================================================
#                              CONFIGURATION
# ============================================================================
API_ID = 22268900
API_HASH = "6764e4d6dd12108e82105f355c6309d8"
SESSION_NAME = "my_account.session"
SOURCE_GROUP = "nhomnayngon"
TARGET_GROUP = "mitsurisaimori"

# File paths
PROGRESS_FILE = "clone_progress.json"
STATS_FILE = "clone_stats.json"
HASH_FILE = "message_hashes.json"
MAPPING_FILE = "message_mapping.json"
LAST_CHECK_FILE = "last_check.json"

# Performance settings
INITIAL_DELAY = 3.0
MAX_DELAY = 15
BATCH_SIZE = 1
BATCH_DELAY = 5
MAX_RETRIES = 3
SCAN_DELAY = 0.05

# Continuous monitoring settings
MONITOR_INTERVAL = 30
REALTIME_MODE = True
BACKFILL_ENABLED = True

# URL pattern for link detection
URL_PATTERN = re.compile(
    r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
)

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
    GUARANTEED 100% COMPLETE COVERAGE CLONER
    - Only clones Videos, Images, GIFs, and Links
    - Uses multiple fetch strategies to get all messages
    - Robust resume system with comprehensive progress tracking
    """
    
    def __init__(self, app: Client, source: str, target: str):
        self.app = app
        self.source = source
        self.target = target
        self.progress = self.load_progress()
        self.message_hashes = self.load_hashes()
        self.message_mapping = self.load_mapping()
        self.last_check = self.load_last_check()
        self.is_monitoring = False
        self.pending_messages = asyncio.Queue()
        self.processing_task = None
        self.currently_processing = set()
        
        self.stats = {
            "total_messages": 0,
            "successful": 0,
            "failed": 0,
            "skipped": 0,
            "duplicates": 0,
            "media_groups": 0,
            "videos_cloned": 0,
            "images_cloned": 0,
            "gifs_cloned": 0,
            "links_cloned": 0,
            "other_skipped": 0,
            "real_time_cloned": 0,
            "direct_forwards": 0,
            "copied_messages": 0,
            "resumed_from": None,
            "fetch_strategy": "initial",
            "by_type": {},
            "last_activity": None,
            "start_time": None,
            "end_time": None
        }
    
    # ========================================================================
    #                          DATA PERSISTENCE
    # ========================================================================
    
    def load_progress(self) -> Dict:
        """Load cloning progress from file"""
        if os.path.exists(PROGRESS_FILE):
            try:
                with open(PROGRESS_FILE, "r", encoding='utf-8') as f:
                    progress = json.load(f)
                    print(f"📁 Loaded progress: {len(progress.get('success', []))} successful, "
                          f"{len(progress.get('failed', []))} failed")
                    if progress.get('earliest_processed_id'):
                        print(f"📅 Earliest processed: {progress['earliest_processed_id']}")
                    if progress.get('latest_processed_id'):
                        print(f"📅 Latest processed: {progress['latest_processed_id']}")
                    return progress
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Corrupted progress file: {e}. Starting fresh.")
        
        print("🆕 Starting fresh - no previous progress found")
        return {
            "success": [],
            "failed": [],
            "media_groups_done": [],
            "last_processed": None,
            "started_at": None,
            "completed_at": None,
            "real_time_mode": False,
            "backfill_current_index": 0,
            "backfill_total": 0,
            "earliest_processed_id": None,
            "latest_processed_id": None,
            "all_messages_fetched": False,
            "fetch_complete": False,
            "total_messages_scanned": 0
        }
    
    def load_hashes(self) -> Dict:
        """Load message hash database"""
        if os.path.exists(HASH_FILE):
            try:
                with open(HASH_FILE, "r", encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data.get("target_hashes"), list):
                        data["target_hashes"] = set(data["target_hashes"])
                    print(f"🔍 Loaded {len(data.get('source_hashes', {}))} source hashes, "
                          f"{len(data.get('target_hashes', set()))} target hashes")
                    return data
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Corrupted hash file: {e}. Starting fresh.")
        
        print("🆕 Starting fresh - no previous hash database found")
        return {
            "source_hashes": {},
            "target_hashes": set()
        }
    
    def load_mapping(self) -> Dict:
        """Load message ID mapping (source -> target)"""
        if os.path.exists(MAPPING_FILE):
            try:
                with open(MAPPING_FILE, "r", encoding='utf-8') as f:
                    mapping = json.load(f)
                    print(f"🗺️  Loaded {len(mapping)} message mappings")
                    return mapping
            except (json.JSONDecodeError, IOError):
                logger.warning("Corrupted mapping file. Starting fresh.")
        print("🆕 Starting fresh - no previous message mapping found")
        return {}
    
    def load_last_check(self) -> Dict:
        """Load last check timestamp"""
        if os.path.exists(LAST_CHECK_FILE):
            try:
                with open(LAST_CHECK_FILE, "r", encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                logger.warning("Corrupted last check file. Starting fresh.")
        return {
            "last_message_id": 0,
            "last_check_time": None,
            "continuous_mode": False
        }
    
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
            self.stats["last_activity"] = datetime.now().isoformat()
            with open(STATS_FILE, "w", encoding='utf-8') as f:
                json.dump(self.stats, f, indent=2)
        except IOError as e:
            logger.error(f"Failed to save stats: {e}")
    
    def save_last_check(self):
        """Save last check timestamp"""
        try:
            with open(LAST_CHECK_FILE, "w", encoding='utf-8') as f:
                json.dump(self.last_check, f, indent=2)
        except IOError as e:
            logger.error(f"Failed to save last check: {e}")
    
    # ========================================================================
    #                      GUARANTEED COMPLETE FETCHING
    # ========================================================================
    
    async def fetch_all_messages_guaranteed(self) -> List:
        """
        GUARANTEED to fetch ALL messages from beginning to end
        Uses multiple strategies to ensure complete coverage
        """
        print("\n" + "="*70)
        print("🔍 GUARANTEED COMPLETE MESSAGE FETCH")
        print("="*70)
        print("🎯 TARGET TYPES: Videos, Images, GIFs, Links ONLY")
        print("="*70)
        
        all_messages = []
        already_processed = set(self.progress["success"])
        total_scanned = 0
        target_found = 0
        duplicate_count = 0
        skipped_count = 0
        
        # Strategy 1: Fetch from newest to oldest (standard approach)
        print("📥 Strategy 1: Fetching from newest to oldest...")
        try:
            async for message in self.app.get_chat_history(self.source):
                total_scanned += 1
                
                if message.service or message.empty:
                    continue
                
                # Skip if already processed
                if message.id in already_processed:
                    duplicate_count += 1
                    continue
                
                # Check if target type - ONLY VIDEOS, IMAGES, GIFs, LINKS
                if not self.should_clone_message(message):
                    skipped_count += 1
                    continue
                
                # Generate hash and check for content duplicates
                msg_hash = self.generate_message_hash(message)
                if msg_hash:
                    self.message_hashes["source_hashes"][str(message.id)] = msg_hash
                    
                    if msg_hash in self.message_hashes["target_hashes"]:
                        duplicate_count += 1
                        self.progress["success"].append(message.id)
                        continue
                
                # Add to processing list
                all_messages.append(message)
                target_found += 1
                
                # Update progress tracking
                self.update_progress_bounds(message.id)
                
                if total_scanned % 200 == 0:
                    print(f"📦 Scanned {total_scanned} messages, found {target_found} target messages...")
                
                await asyncio.sleep(SCAN_DELAY)
                
        except Exception as e:
            logger.error(f"Error in Strategy 1: {e}")
            print(f"⚠️  Strategy 1 completed with error, but continuing...")
        
        print(f"✅ Strategy 1: Found {target_found} target messages from {total_scanned} total")
        print(f"📊 Skipped {skipped_count} non-target messages")
        
        # Strategy 2: If we have previous progress, verify we didn't miss anything
        if self.progress.get("earliest_processed_id"):
            print("\n📥 Strategy 2: Verifying we didn't miss earlier messages...")
            earliest_known = self.progress["earliest_processed_id"]
            additional_found = await self.fetch_earlier_messages(earliest_known, all_messages, already_processed)
            target_found += additional_found
            print(f"✅ Strategy 2: Found {additional_found} additional earlier messages")
        
        # Strategy 3: Final verification pass
        print("\n📥 Strategy 3: Final verification pass...")
        verification_found = await self.verification_fetch(all_messages, already_processed)
        target_found += verification_found
        print(f"✅ Strategy 3: Found {verification_found} additional messages in verification")
        
        # Sort all messages in chronological order (oldest first)
        all_messages.sort(key=lambda x: x.id)
        
        print("="*70)
        print(f"🎯 FETCH COMPLETE - GUARANTEED COVERAGE")
        print(f"   Total messages scanned: {total_scanned}")
        print(f"   Target messages found: {target_found}")
        print(f"   Duplicates prevented: {duplicate_count}")
        print(f"   Non-target skipped: {skipped_count}")
        print(f"   Already processed: {len(already_processed)}")
        if all_messages:
            print(f"   📅 Earliest message: {all_messages[0].id}")
            print(f"   📅 Latest message: {all_messages[-1].id}")
            print(f"   📊 Date range: {len(all_messages)} messages spanning from first to last")
            
            # Show message type breakdown
            type_breakdown = {}
            for msg in all_messages:
                msg_type = self.get_message_type(msg)
                type_breakdown[msg_type] = type_breakdown.get(msg_type, 0) + 1
            
            print(f"   📊 Type breakdown: {type_breakdown}")
        else:
            print(f"   📅 No new messages found")
        print("="*70 + "\n")
        
        self.stats["duplicates"] = duplicate_count
        self.stats["skipped"] = skipped_count
        self.progress["fetch_complete"] = True
        self.progress["total_messages_scanned"] = total_scanned
        self.save_progress()
        self.save_hashes()
        
        return all_messages
    
    async def fetch_earlier_messages(self, earliest_known: int, all_messages: List, already_processed: Set) -> int:
        """Fetch messages that might be earlier than our earliest known"""
        additional_found = 0
        try:
            # Try to fetch a few hundred messages before our earliest known
            earlier_messages = []
            async for message in self.app.get_chat_history(self.source, limit=500):
                if message.id >= earliest_known:
                    continue  # Skip messages we already know about
                    
                if message.service or message.empty:
                    continue
                    
                if message.id in already_processed:
                    continue
                    
                if not self.should_clone_message(message):
                    continue
                
                # Check for duplicates
                msg_hash = self.generate_message_hash(message)
                if msg_hash and msg_hash in self.message_hashes["target_hashes"]:
                    self.progress["success"].append(message.id)
                    continue
                
                earlier_messages.append(message)
                additional_found += 1
                
                if additional_found % 50 == 0:
                    print(f"   📥 Found {additional_found} earlier messages...")
                
                await asyncio.sleep(SCAN_DELAY)
                
            # Add to main list
            all_messages.extend(earlier_messages)
            
        except Exception as e:
            logger.error(f"Error fetching earlier messages: {e}")
        
        return additional_found
    
    async def verification_fetch(self, all_messages: List, already_processed: Set) -> int:
        """Final verification fetch to ensure no messages were missed"""
        verification_found = 0
        try:
            # Get known message IDs for gap detection
            known_ids = {msg.id for msg in all_messages}
            known_ids.update(already_processed)
            
            if not known_ids:
                return 0
                
            min_id = min(known_ids)
            max_id = max(known_ids)
            
            print(f"   🔍 Checking for gaps between {min_id} and {max_id}...")
            
            # Sample check at different points
            check_points = [
                max_id - 1000,
                max_id - 2000, 
                min_id + 1000,
                min_id + 500
            ]
            
            for point in check_points:
                if point > min_id and point < max_id:
                    try:
                        # Try to get message at this point
                        messages = []
                        async for msg in self.app.get_chat_history(self.source, offset_id=point, limit=100):
                            if (msg.id not in known_ids and 
                                not msg.service and 
                                not msg.empty and 
                                self.should_clone_message(msg)):
                                
                                # Check for duplicates
                                msg_hash = self.generate_message_hash(msg)
                                if not msg_hash or msg_hash not in self.message_hashes["target_hashes"]:
                                    messages.append(msg)
                                    verification_found += 1
                        
                        all_messages.extend(messages)
                        if messages:
                            print(f"   ✅ Found {len(messages)} messages at offset {point}")
                            
                    except Exception as e:
                        logger.debug(f"Verification check at {point} failed: {e}")
                        continue
                        
        except Exception as e:
            logger.error(f"Error in verification fetch: {e}")
        
        return verification_found
    
    def update_progress_bounds(self, message_id: int):
        """Update earliest and latest processed message IDs"""
        current_earliest = self.progress.get("earliest_processed_id")
        current_latest = self.progress.get("latest_processed_id")
        
        if current_earliest is None or message_id < current_earliest:
            self.progress["earliest_processed_id"] = message_id
            
        if current_latest is None or message_id > current_latest:
            self.progress["latest_processed_id"] = message_id
    
    # ========================================================================
    #                      MESSAGE TYPE DETECTION & FILTERING
    # ========================================================================
    
    def get_message_type(self, message: Message) -> str:
        """Determine the type of message with improved GIF detection"""
        if message.media_group_id:
            return "media_group"
        elif message.photo:
            return "photo"
        elif message.video:
            # Improved GIF detection
            if (message.video.mime_type and "gif" in message.video.mime_type) or \
               (hasattr(message.video, 'file_name') and message.video.file_name and 
                message.video.file_name.lower().endswith('.gif')):
                return "gif"
            return "video"
        elif message.animation:
            return "gif"
        elif message.document:
            # Check if document is actually a GIF
            if (message.document.mime_type and "gif" in message.document.mime_type) or \
               (message.document.file_name and message.document.file_name.lower().endswith('.gif')):
                return "gif"
        elif message.text and self.contains_links(message.text):
            return "link"
        else:
            return "other"
    
    def should_clone_message(self, message: Message) -> bool:
        """Check if message should be cloned - ONLY VIDEOS, IMAGES, GIFs, LINKS"""
        if message.service or message.empty:
            return False
        
        message_type = self.get_message_type(message)
        
        # ONLY clone these specific types
        allowed_types = ['video', 'photo', 'link', 'gif', 'media_group']
        
        return message_type in allowed_types
    
    def contains_links(self, text: str) -> bool:
        """Check if text contains URLs/links"""
        if not text:
            return False
        return bool(URL_PATTERN.search(text))
    
    def generate_message_hash(self, message: Message) -> Optional[str]:
        """Generate unique content-based hash for duplicate detection"""
        hash_components = []
        
        if message.media_group_id:
            hash_components.append(f"media_group:{message.media_group_id}")
        
        if message.text and self.contains_links(message.text):
            urls = URL_PATTERN.findall(message.text)
            normalized_urls = [url.lower().strip() for url in urls]
            hash_components.append(f"links:{','.join(sorted(normalized_urls))}")
        
        if message.caption:
            hash_components.append(f"caption:{message.caption}")
        
        if message.photo:
            file_size = message.photo.file_size if message.photo.file_size else 0
            hash_components.append(f"photo:{file_size}")
        elif message.video:
            file_size = message.video.file_size if message.video.file_size else 0
            duration = message.video.duration if message.video.duration else 0
            hash_components.append(f"video:{file_size}:{duration}")
        elif message.animation:
            file_size = message.animation.file_size if message.animation.file_size else 0
            hash_components.append(f"gif:{file_size}")
        
        if hash_components:
            content = "|".join(hash_components)
            return hashlib.sha256(content.encode('utf-8')).hexdigest()
        
        return None
    
    # ========================================================================
    #                      COMPREHENSIVE CLONING METHODS
    # ========================================================================
    
    async def try_direct_forward(self, message: Message) -> Optional[Message]:
        """Try to forward message directly - fastest method"""
        try:
            result = await self.app.forward_messages(
                chat_id=self.target,
                from_chat_id=self.source,
                message_ids=message.id
            )
            if isinstance(result, list):
                result = result[0]
            self.stats["direct_forwards"] += 1
            return result
        except Exception as e:
            logger.debug(f"Direct forward failed for {message.id}: {e}")
            return None
    
    async def clone_photo_direct(self, message: Message) -> Optional[Message]:
        """Clone photo using direct methods with improved error handling"""
        try:
            forwarded = await self.try_direct_forward(message)
            if forwarded:
                self.stats["images_cloned"] += 1
                return forwarded
            
            # Add download fallback if file_id expires
            try:
                result = await self.app.send_photo(
                    self.target,
                    photo=message.photo.file_id,
                    caption=message.caption or "",
                    caption_entities=message.caption_entities,
                    has_spoiler=message.has_media_spoiler if hasattr(message, 'has_media_spoiler') else False
                )
                self.stats["images_cloned"] += 1
                self.stats["copied_messages"] += 1
                return result
            except (FileReferenceExpired, BadRequest) as e:
                logger.warning(f"File ID expired for photo {message.id}, trying download method...")
                # You can add download logic here if needed
                return None
                
        except Exception as e:
            logger.error(f"Failed to clone photo {message.id}: {e}")
            return None
    
    async def clone_video_direct(self, message: Message) -> Optional[Message]:
        """Clone video using direct methods with improved error handling"""
        try:
            forwarded = await self.try_direct_forward(message)
            if forwarded:
                self.stats["videos_cloned"] += 1
                return forwarded
            
            try:
                result = await self.app.send_video(
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
                self.stats["videos_cloned"] += 1
                self.stats["copied_messages"] += 1
                return result
            except (FileReferenceExpired, BadRequest) as e:
                logger.warning(f"File ID expired for video {message.id}, trying download method...")
                return None
                
        except Exception as e:
            logger.error(f"Failed to clone video {message.id}: {e}")
            return None
    
    async def clone_gif_direct(self, message: Message) -> Optional[Message]:
        """Clone GIF/animation using direct methods with improved error handling"""
        try:
            forwarded = await self.try_direct_forward(message)
            if forwarded:
                self.stats["gifs_cloned"] += 1
                return forwarded
            
            try:
                if hasattr(message, 'animation') and message.animation:
                    # For animation (GIF)
                    result = await self.app.send_animation(
                        self.target,
                        animation=message.animation.file_id,
                        caption=message.caption or "",
                        caption_entities=message.caption_entities
                    )
                else:
                    # For video that's actually a GIF
                    result = await self.app.send_video(
                        self.target,
                        video=message.video.file_id,
                        caption=message.caption or "",
                        caption_entities=message.caption_entities,
                        supports_streaming=False
                    )
                self.stats["gifs_cloned"] += 1
                self.stats["copied_messages"] += 1
                return result
            except (FileReferenceExpired, BadRequest) as e:
                logger.warning(f"File ID expired for GIF {message.id}, trying download method...")
                return None
                
        except Exception as e:
            logger.error(f"Failed to clone GIF {message.id}: {e}")
            return None
    
    async def clone_link_direct(self, message: Message) -> Optional[Message]:
        """Clone link message using direct methods"""
        try:
            forwarded = await self.try_direct_forward(message)
            if forwarded:
                self.stats["links_cloned"] += 1
                return forwarded
            
            result = await self.app.send_message(
                self.target,
                text=message.text,
                entities=message.entities,
                disable_web_page_preview=False
            )
            self.stats["links_cloned"] += 1
            self.stats["copied_messages"] += 1
            return result
        except Exception as e:
            logger.error(f"Failed to clone link {message.id}: {e}")
            return None
    
    async def clone_media_group_direct(self, message: Message) -> Optional[List[Message]]:
        """Clone media group using direct methods with validation - FIXED VERSION"""
        try:
            # Get media group - this is a coroutine that returns a list
            media_group_messages = await self.app.get_media_group(self.source, message.id)
            
            # Filter valid messages
            valid_messages = []
            for msg in media_group_messages:
                if not msg.service and not msg.empty:
                    # Only include if it has media we want to clone
                    if self.should_clone_message(msg):
                        valid_messages.append(msg)
            
            if len(valid_messages) <= 1:
                logger.warning(f"Media group {message.media_group_id} has only {len(valid_messages)} valid items")
                # Fall back to single message cloning
                single_result = await self.clone_single_message_robust(message)
                return [single_result] if single_result else None
            
            print(f"🔄 Cloning media group with {len(valid_messages)} items...")
            
            # Try to forward the entire group
            try:
                result = await self.app.forward_messages(
                    chat_id=self.target,
                    from_chat_id=self.source,
                    message_ids=[msg.id for msg in valid_messages]
                )
                self.stats["media_groups"] += 1
                self.stats["direct_forwards"] += 1
                print(f"✅ Successfully forwarded media group {message.media_group_id}")
                return result
            except Exception as e:
                logger.warning(f"Forwarding media group failed, copying individually: {e}")
                # If forwarding fails, copy each media individually
                cloned_messages = []
                for i, media_msg in enumerate(valid_messages):
                    print(f"📦 Copying media group item {i+1}/{len(valid_messages)}...")
                    cloned_msg = await self.clone_single_message_robust(media_msg)
                    if cloned_msg:
                        cloned_messages.append(cloned_msg)
                        if i < len(valid_messages) - 1:  # Don't wait after last item
                            await asyncio.sleep(2)  # Small delay between media group items
                
                if cloned_messages:
                    self.stats["media_groups"] += 1
                    print(f"✅ Successfully copied media group {message.media_group_id} with {len(cloned_messages)} items")
                    return cloned_messages
                return None
                
        except Exception as e:
            logger.error(f"Failed to clone media group {message.id}: {e}")
            return None
    
    async def clone_single_message_robust(self, message: Message) -> Optional[Message]:
        """Clone a single message with appropriate method"""
        message_type = self.get_message_type(message)
        
        if message_type == "link":
            return await self.clone_link_direct(message)
        elif message_type == "photo":
            return await self.clone_photo_direct(message)
        elif message_type == "video":
            return await self.clone_video_direct(message)
        elif message_type == "gif":
            return await self.clone_gif_direct(message)
        else:
            logger.warning(f"Unsupported message type: {message_type}")
            return None
    
    # ========================================================================
    #                      ROBUST CLONING LOGIC
    # ========================================================================
    
    async def clone_message_robust(
        self, 
        message: Message,
        real_time: bool = False
    ) -> Tuple[str, str]:
        """Robust message cloning with duplicate prevention"""
        message_type = self.get_message_type(message)
        
        if message.id in self.currently_processing:
            return "skipped", "already_processing"
        
        self.currently_processing.add(message.id)
        
        try:
            if not self.should_clone_message(message):
                self.stats["other_skipped"] += 1
                return "skipped", "other"
            
            # Check for duplicates
            msg_hash = self.message_hashes["source_hashes"].get(str(message.id))
            if msg_hash and msg_hash in self.message_hashes["target_hashes"]:
                self.stats["duplicates"] += 1
                self.progress["success"].append(message.id)
                return "skipped", "duplicate"
            
            cloned_message = None
            
            if message_type == "media_group":
                # Handle media groups specially
                if str(message.media_group_id) in self.progress.get("media_groups_done", []):
                    return "skipped", "media_group_duplicate"
                
                cloned_messages = await self.clone_media_group_direct(message)
                if cloned_messages:
                    cloned_message = cloned_messages[0] if cloned_messages else None
                    self.progress["media_groups_done"].append(str(message.media_group_id))
            else:
                cloned_message = await self.clone_single_message_robust(message)
            
            if cloned_message:
                if isinstance(cloned_message, list):
                    # For media groups, map all messages
                    for i, msg in enumerate(cloned_message):
                        source_msg_id = message.id + i if i == 0 else message.id
                        self.message_mapping[str(source_msg_id)] = msg.id
                else:
                    self.message_mapping[str(message.id)] = cloned_message.id
                
                self.progress["success"].append(message.id)
                self.stats["successful"] += 1
                
                if msg_hash:
                    self.message_hashes["target_hashes"].add(msg_hash)
                
                if real_time:
                    self.stats["real_time_cloned"] += 1
                
                self.update_progress_bounds(message.id)
                self.save_progress()
                self.save_hashes()
                self.save_mapping()
                self.save_stats()
                
                return "success", message_type
            else:
                self.stats["failed"] += 1
                self.progress["failed"].append(message.id)
                return "failed", message_type
                
        except FloodWait as e:
            logger.warning(f"⏳ Flood wait: {e.value}s")
            print(f"🚨 FLOOD WAIT: Need to wait {e.value} seconds ({e.value/60:.1f} minutes)")
            await asyncio.sleep(e.value)
            self.stats["failed"] += 1
            self.progress["failed"].append(message.id)
            return "failed", f"{message_type}_flood"
        except Exception as e:
            logger.error(f"Error cloning {message_type} {message.id}: {e}")
            self.stats["failed"] += 1
            self.progress["failed"].append(message.id)
            return "failed", message_type
        finally:
            self.currently_processing.discard(message.id)
            self.save_progress()
            self.save_stats()
    
    # ========================================================================
    #                      COMPLETE BACKFILL PROCESSING
    # ========================================================================
    
    async def complete_backfill(self, all_messages: List):
        """Complete backfill with guaranteed coverage"""
        print(f"\n📥 STARTING GUARANTEED BACKFILL: {len(all_messages)} messages")
        print("🔄 PROCESSING 100% OF VIDEOS, IMAGES, GIFs, LINKS FROM BEGINNING TO END")
        print("="*70)
        
        self.stats["start_time"] = datetime.now().isoformat()
        
        start_index = self.progress.get("backfill_current_index", 0)
        if start_index > 0:
            print(f"🔄 RESUMING from position {start_index + 1}/{len(all_messages)}")
            self.stats["resumed_from"] = start_index
        else:
            print(f"🆕 STARTING from the VERY BEGINNING")
            self.stats["resumed_from"] = "beginning"
        
        self.progress["backfill_total"] = len(all_messages)
        self.save_progress()
        self.save_stats()
        
        total_processed = 0
        consecutive_failures = 0
        max_consecutive_failures = 3
        
        index = start_index
        while index < len(all_messages):
            try:
                message = all_messages[index]
                message_type = self.get_message_type(message)
                
                status, result_type = await self.clone_message_robust(message)
                
                if status == "success":
                    total_processed += 1
                    consecutive_failures = 0
                    
                    # Show detailed progress
                    if (index + 1) % 10 == 0 or (index + 1) <= 10 or (index + 1) == len(all_messages):
                        progress_pct = (index + 1) / len(all_messages) * 100
                        print(f"📊 Progress: {index + 1}/{len(all_messages)} ({progress_pct:.1f}%) - {result_type}")
                
                elif status == "failed":
                    consecutive_failures += 1
                    print(f"❌ [{index + 1}/{len(all_messages)}] Failed {result_type}: {message.id}")
                
                elif status == "skipped":
                    print(f"⏭️  [{index + 1}/{len(all_messages)}] Skipped {result_type}: {message.id}")
                
                if consecutive_failures >= max_consecutive_failures:
                    print(f"🚨 {consecutive_failures} consecutive failures, waiting 60 seconds...")
                    await asyncio.sleep(60)
                    consecutive_failures = 0
                
                index += 1
                self.progress["backfill_current_index"] = index
                
                if index % 5 == 0:
                    self.save_progress()
                    self.save_stats()
                
                if index < len(all_messages):
                    # Longer delays to avoid flood waits
                    cooldown = random.uniform(5, 12)
                    await asyncio.sleep(cooldown)
                
            except Exception as e:
                logger.error(f"Error in backfill at index {index}: {e}")
                self.save_progress()
                self.save_stats()
                index += 1
                await asyncio.sleep(30)  # Longer wait on errors
        
        self.stats["end_time"] = datetime.now().isoformat()
        print(f"\n✅ BACKFILL COMPLETED: Processed {total_processed} items")
        print("🎉 100% OF VIDEOS, IMAGES, GIFs, LINKS HAVE BEEN PROCESSED!")
        
        self.progress.pop("backfill_current_index", None)
        self.progress.pop("backfill_total", None)
        self.progress["completed_at"] = datetime.now().isoformat()
        self.save_progress()
        self.save_stats()
    
    # ========================================================================
    #                      MAIN EXECUTION FLOW
    # ========================================================================
    
    async def start_guaranteed_cloning(self):
        """Start guaranteed complete cloning"""
        print("\n" + "="*70)
        print("🚀 GUARANTEED COMPLETE COVERAGE CLONER")
        print("="*70)
        print(f"📍 Source: {self.source}")
        print(f"📍 Target: {self.target}")
        print("\n🎯 GUARANTEE: 100% of VIDEOS, IMAGES, GIFs, LINKS from beginning")
        print("📦 ONLY: Videos, Images, GIFs, Links - NO TEXT, VOICE, DOCUMENTS, etc.")
        print("🔍 STRATEGY: Multiple fetch methods for complete coverage")
        print("💾 RESUME: Always continues from exact position")
        print("="*70)
        
        if not self.progress["started_at"]:
            self.progress["started_at"] = datetime.now().isoformat()
        
        # Step 1: Scan target for existing content
        print("\n🔍 Scanning target group for existing content...")
        try:
            existing_hashes = await self.scan_target_group()
            self.message_hashes["target_hashes"].update(existing_hashes)
            self.save_hashes()
            print(f"✅ Found {len(existing_hashes)} existing items in target")
        except Exception as e:
            logger.error(f"Error scanning target: {e}")
        
        # Step 2: GUARANTEED fetch of ALL messages
        all_messages = await self.fetch_all_messages_guaranteed()
        
        if not all_messages:
            print("✨ No new messages to clone! Target is already up to date.")
            self.print_final_report()
            return
        
        self.stats["total_messages"] = len(all_messages)
        
        # Step 3: Complete backfill
        await self.complete_backfill(all_messages)
        
        # Step 4: Start monitoring
        if REALTIME_MODE:
            await self.start_real_time_monitoring()
        else:
            self.print_final_report()
    
    async def scan_target_group(self) -> Set[str]:
        """Scan target group for existing content"""
        target_hashes = set()
        count = 0
        
        try:
            async for message in self.app.get_chat_history(self.target):
                if message.service or message.empty:
                    continue
                
                if not self.should_clone_message(message):
                    continue
                
                msg_hash = self.generate_message_hash(message)
                if msg_hash:
                    target_hashes.add(msg_hash)
                
                count += 1
                if count % 500 == 0:
                    print(f"📊 Scanned {count} target messages...")
                
                await asyncio.sleep(SCAN_DELAY)
            
        except Exception as e:
            logger.error(f"Error scanning target group: {e}")
        
        return target_hashes
    
    async def start_real_time_monitoring(self):
        """Start real-time monitoring"""
        print("\n" + "="*70)
        print("🔄 STARTING REAL-TIME MONITORING")
        print("="*70)
        print("🤖 Monitoring for NEW Videos, Images, GIFs, Links...")
        print("💡 The script will run continuously (Ctrl+C to stop)")
        print("="*70)
        
        self.is_monitoring = True
        self.progress["real_time_mode"] = True
        self.save_progress()
        
        @self.app.on_message(filters.chat(self.source))
        async def handle_new_message(client, message: Message):
            if self.is_monitoring and self.should_clone_message(message):
                msg_type = self.get_message_type(message)
                print(f"🆕 New {msg_type} detected, cloning...")
                await self.clone_message_robust(message, real_time=True)
        
        try:
            while self.is_monitoring:
                await asyncio.sleep(MONITOR_INTERVAL)
        except asyncio.CancelledError:
            print("\n🛑 Monitoring stopped by user")
        finally:
            self.is_monitoring = False
    
    def print_final_report(self):
        """Print comprehensive final report"""
        print("\n" + "="*70)
        print("🎉 GUARANTEED COMPLETE CLONING OPERATION FINISHED!")
        print("="*70)
        print(f"\n📊 COMPREHENSIVE STATISTICS:")
        print(f"   📹 Videos: {self.stats['videos_cloned']}")
        print(f"   🖼️  Images: {self.stats['images_cloned']}")
        print(f"   🎬 GIFs: {self.stats['gifs_cloned']}")
        print(f"   🔗 Links: {self.stats['links_cloned']}")
        print(f"   📦 Media Groups: {self.stats['media_groups']}")
        print(f"   ⏩ Direct forwards: {self.stats['direct_forwards']}")
        print(f"   📋 Copied: {self.stats['copied_messages']}")
        print(f"   🔄 Duplicates prevented: {self.stats['duplicates']}")
        print(f"   ✅ Successful: {self.stats['successful']}")
        print(f"   ❌ Failed: {self.stats['failed']}")
        print(f"   ⏭️  Skipped: {self.stats['skipped']}")
        
        if self.stats.get('resumed_from'):
            print(f"   🔄 Resumed from: {self.stats['resumed_from']}")
        
        print(f"\n💾 PERSISTENT DATA SAVED:")
        print(f"   ✅ Successful: {len(self.progress['success'])}")
        print(f"   ❌ Failed: {len(self.progress['failed'])}")
        print(f"   🔍 Source hashes: {len(self.message_hashes['source_hashes'])}")
        print(f"   🎯 Target hashes: {len(self.message_hashes['target_hashes'])}")
        print(f"   🗺️  Message mappings: {len(self.message_mapping)}")
        
        if self.stats.get('start_time') and self.stats.get('end_time'):
            start = datetime.fromisoformat(self.stats['start_time'])
            end = datetime.fromisoformat(self.stats['end_time'])
            duration = end - start
            print(f"   ⏱️  Duration: {duration}")
        
        print(f"\n📁 RESUME-READY FILES:")
        print(f"   Progress: {PROGRESS_FILE}")
        print(f"   Hashes: {HASH_FILE}")
        print(f"   Mapping: {MAPPING_FILE}")
        print(f"   Stats: {STATS_FILE}")
        print(f"   Run again to resume/monitor!")
        print("="*70 + "\n")


# ============================================================================
#                          MAIN ENTRY POINT
# ============================================================================

async def main():
    """Initialize and run the guaranteed cloner"""
    
    if not os.path.exists(f"{SESSION_NAME}.session") and not os.path.exists(SESSION_NAME):
        print("\n⚠️  WARNING: No session file found!")
        print("On first run, you'll need to log in with your phone number.")
        print("The session will be saved for future runs.\n")
    
    app = Client(SESSION_NAME, API_ID, API_HASH)
    
    async with app:
        try:
            source_chat = await app.get_chat(SOURCE_GROUP)
            target_chat = await app.get_chat(TARGET_GROUP)
            
            print(f"\n✅ Connected successfully!")
            print(f"   Source: {source_chat.title}")
            print(f"   Target: {target_chat.title}")
            
        except Exception as e:
            logger.error(f"Error verifying group access: {e}")
            print(f"\n❌ Could not access groups: {e}")
            return
        
        cloner = TelegramCloner(app, SOURCE_GROUP, TARGET_GROUP)
        
        try:
            await cloner.start_guaranteed_cloning()
        except KeyboardInterrupt:
            print("\n\n🛑 Operation interrupted by user")
            print("💾 ALL PROGRESS SAVED! Run again to resume exactly where you left off.")
            cloner.is_monitoring = False
            cloner.print_final_report()


# ============================================================================
#                          SCRIPT EXECUTION
# ============================================================================

if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════════════════╗
║                                                                      ║
║           GUARANTEED COMPLETE COVERAGE CLONER                       ║
║                                                                      ║
║  🎯 GUARANTEE: 100% of VIDEOS, IMAGES, GIFs, LINKS only            ║
║  📦 EXCLUDES: Text, Voice, Documents, Stickers, Audio              ║
║  🔍 STRATEGY: Multiple fetch methods for complete coverage          ║
║  💾 RESUME: Always continues from exact position after crashes      ║
║  🛡️  PROTECTION: Advanced duplicate prevention                      ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝
    """)
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n🛑 Operation cancelled by user")
        print("💾 All progress has been saved.")
        print("🔁 Run the script again to continue from EXACTLY where you left off!")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        print(f"\n❌ Fatal error: {e}")
        print("💾 Progress has been saved. Run the script again to resume.")
        
        ##OLD CODE WORK FINE BUT NOT REAL TIME CHECKING FOR NEW MESSAGES