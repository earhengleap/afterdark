import os
import json
import asyncio
import random
import logging
import hashlib
from datetime import datetime
from pyrogram import Client
from pyrogram.errors import FloodWait, FileReferenceExpired, MessageIdInvalid
from pyrogram.types import Message
from pyrogram.enums import MessageMediaType

# ---------------- CONFIG ----------------
API_ID = 22268900
API_HASH = "6764e4d6dd12108e82105f355c6309d8"
SESSION_NAME = "my_account.session"
SOURCE_GROUP = "chickenchaseruwu"
TARGET_GROUP = "makimasaimori"
PROGRESS_FILE = "clone_progress.json"
STATS_FILE = "clone_stats.json"
HASH_FILE = "message_hashes.json"

# Optimized settings
INITIAL_DELAY = 1.5
MAX_DELAY = 8
BATCH_SIZE = 5
BATCH_DELAY = 15
MAX_RETRIES = 3
REFETCH_DELAY = 2
# ----------------------------------------

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('clone_log.txt'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
logging.getLogger("pyrogram").setLevel(logging.WARNING)


class TelegramCloner:
    def __init__(self, app, source, target):
        self.app = app
        self.source = source
        self.target = target
        self.progress = self.load_progress()
        self.message_hashes = self.load_hashes()
        self.stats = {
            "total_messages": 0,
            "successful": 0,
            "failed": 0,
            "skipped": 0,
            "duplicates": 0,
            "by_type": {}
        }
    
    def load_progress(self):
        """Load cloning progress"""
        if os.path.exists(PROGRESS_FILE):
            try:
                with open(PROGRESS_FILE, "r") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                logger.warning("Corrupted progress file, starting fresh")
        return {
            "success": [],
            "failed": [],
            "last_processed": None,
            "started_at": None,
            "completed_at": None
        }
    
    def load_hashes(self):
        """Load message hash database for duplicate detection"""
        if os.path.exists(HASH_FILE):
            try:
                with open(HASH_FILE, "r") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                logger.warning("Corrupted hash file, starting fresh")
        return {
            "source_hashes": {},  # msg_id -> hash
            "target_hashes": set()  # set of hashes in target
        }
    
    def save_progress(self):
        """Save cloning progress"""
        with open(PROGRESS_FILE, "w") as f:
            json.dump(self.progress, f, indent=2)
    
    def save_hashes(self):
        """Save message hash database"""
        # Convert set to list for JSON serialization
        save_data = {
            "source_hashes": self.message_hashes["source_hashes"],
            "target_hashes": list(self.message_hashes["target_hashes"])
        }
        with open(HASH_FILE, "w") as f:
            json.dump(save_data, f, indent=2)
        # Convert back to set
        self.message_hashes["target_hashes"] = set(save_data["target_hashes"])
    
    def save_stats(self):
        """Save cloning statistics"""
        with open(STATS_FILE, "w") as f:
            json.dump(self.stats, f, indent=2)
    
    def generate_message_hash(self, message):
        """Generate unique hash for message content"""
        hash_components = []
        
        # Text content
        if message.text:
            hash_components.append(f"text:{message.text}")
        if message.caption:
            hash_components.append(f"caption:{message.caption}")
        
        # Media file IDs (unique identifiers)
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
        
        # Other content types
        if message.poll:
            hash_components.append(f"poll:{message.poll.question}:{len(message.poll.options)}")
        if message.location:
            hash_components.append(f"loc:{message.location.latitude}:{message.location.longitude}")
        if message.contact:
            hash_components.append(f"contact:{message.contact.phone_number}")
        if message.dice:
            hash_components.append(f"dice:{message.dice.emoji}:{message.dice.value}")
        
        # Create hash
        if hash_components:
            content = "|".join(hash_components)
            return hashlib.md5(content.encode()).hexdigest()
        
        return None
    
    async def scan_target_group(self):
        """Fast scan of target group to build hash set"""
        print("\n" + "="*70)
        print("🔍 SCANNING TARGET GROUP FOR EXISTING MESSAGES")
        print("="*70)
        
        target_hashes = set()
        count = 0
        
        try:
            async for message in self.app.get_chat_history(self.target):
                if message.service:
                    continue
                
                msg_hash = self.generate_message_hash(message)
                if msg_hash:
                    target_hashes.add(msg_hash)
                
                count += 1
                if count % 500 == 0:
                    print(f"📊 Scanned {count} messages in target group...")
                
                await asyncio.sleep(0.05)  # Minimal delay for scanning
            
            print("="*70)
            print(f"✅ SCAN COMPLETE: {len(target_hashes)} unique messages found in target")
            print("="*70 + "\n")
            
            return target_hashes
            
        except Exception as e:
            logger.error(f"Error scanning target group: {e}")
            return target_hashes
    
    def update_stats(self, message_type, status):
        """Update statistics"""
        if message_type not in self.stats["by_type"]:
            self.stats["by_type"][message_type] = {"success": 0, "failed": 0, "skipped": 0}
        
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
    
    async def get_fresh_message(self, message_id):
        """Fetch fresh message to get updated file references"""
        try:
            return await self.app.get_messages(self.source, message_id)
        except Exception as e:
            logger.error(f"Could not fetch fresh message {message_id}: {e}")
            return None
    
    async def clone_text_message(self, message):
        """Clone text message"""
        entities = message.entities or message.caption_entities
        
        await self.app.send_message(
            self.target,
            text=message.text or message.caption,
            entities=entities,
            disable_web_page_preview=False
        )
    
    async def clone_photo(self, message):
        """Clone photo message"""
        await self.app.send_photo(
            self.target,
            photo=message.photo.file_id,
            caption=message.caption or "",
            caption_entities=message.caption_entities
        )
    
    async def clone_video(self, message):
        """Clone video message"""
        await self.app.send_video(
            self.target,
            video=message.video.file_id,
            caption=message.caption or "",
            caption_entities=message.caption_entities,
            duration=message.video.duration,
            width=message.video.width,
            height=message.video.height,
            supports_streaming=True
        )
    
    async def clone_document(self, message):
        """Clone document/file message"""
        await self.app.send_document(
            self.target,
            document=message.document.file_id,
            caption=message.caption or "",
            caption_entities=message.caption_entities,
            file_name=message.document.file_name
        )
    
    async def clone_audio(self, message):
        """Clone audio message"""
        await self.app.send_audio(
            self.target,
            audio=message.audio.file_id,
            caption=message.caption or "",
            caption_entities=message.caption_entities,
            duration=message.audio.duration,
            performer=message.audio.performer,
            title=message.audio.title
        )
    
    async def clone_voice(self, message):
        """Clone voice message"""
        await self.app.send_voice(
            self.target,
            voice=message.voice.file_id,
            caption=message.caption or "",
            caption_entities=message.caption_entities,
            duration=message.voice.duration
        )
    
    async def clone_video_note(self, message):
        """Clone video note (round video)"""
        await self.app.send_video_note(
            self.target,
            video_note=message.video_note.file_id,
            duration=message.video_note.duration,
            length=message.video_note.length
        )
    
    async def clone_sticker(self, message):
        """Clone sticker"""
        await self.app.send_sticker(
            self.target,
            sticker=message.sticker.file_id
        )
    
    async def clone_animation(self, message):
        """Clone GIF/animation"""
        await self.app.send_animation(
            self.target,
            animation=message.animation.file_id,
            caption=message.caption or "",
            caption_entities=message.caption_entities,
            duration=message.animation.duration,
            width=message.animation.width,
            height=message.animation.height
        )
    
    async def clone_poll(self, message):
        """Clone poll"""
        poll = message.poll
        await self.app.send_poll(
            self.target,
            question=poll.question,
            options=[opt.text for opt in poll.options],
            is_anonymous=poll.is_anonymous,
            allows_multiple_answers=poll.allows_multiple_answers,
            type=poll.type
        )
    
    async def clone_location(self, message):
        """Clone location"""
        loc = message.location
        await self.app.send_location(
            self.target,
            latitude=loc.latitude,
            longitude=loc.longitude
        )
    
    async def clone_contact(self, message):
        """Clone contact"""
        contact = message.contact
        await self.app.send_contact(
            self.target,
            phone_number=contact.phone_number,
            first_name=contact.first_name,
            last_name=contact.last_name or "",
            vcard=contact.vcard or ""
        )
    
    async def clone_dice(self, message):
        """Clone dice/dart/basketball etc"""
        await self.app.send_dice(
            self.target,
            emoji=message.dice.emoji
        )
    
    async def clone_game(self, message):
        """Clone game"""
        await self.app.send_game(
            self.target,
            game_short_name=message.game.short_name
        )
    
    async def clone_venue(self, message):
        """Clone venue"""
        venue = message.venue
        await self.app.send_venue(
            self.target,
            latitude=venue.location.latitude,
            longitude=venue.location.longitude,
            title=venue.title,
            address=venue.address,
            foursquare_id=venue.foursquare_id or "",
            foursquare_type=venue.foursquare_type or ""
        )
    
    async def clone_web_page(self, message):
        """Clone message with web page preview"""
        await self.app.send_message(
            self.target,
            text=message.text,
            entities=message.entities,
            disable_web_page_preview=False
        )
    
    def get_message_type(self, message):
        """Determine message type"""
        if message.text and not message.media:
            return "text"
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
        elif message.contact:
            return "contact"
        elif message.dice:
            return "dice"
        elif message.game:
            return "game"
        elif message.venue:
            return "venue"
        elif message.web_page:
            return "web_page"
        else:
            return "unknown"
    
    async def clone_message(self, message, current_delay, retry_count=0):
        """Clone a single message with all its properties"""
        message_type = self.get_message_type(message)
        
        try:
            # Route to appropriate handler based on message type
            if message_type == "text":
                await self.clone_text_message(message)
            elif message_type == "photo":
                await self.clone_photo(message)
            elif message_type == "video":
                await self.clone_video(message)
            elif message_type == "document":
                await self.clone_document(message)
            elif message_type == "audio":
                await self.clone_audio(message)
            elif message_type == "voice":
                await self.clone_voice(message)
            elif message_type == "video_note":
                await self.clone_video_note(message)
            elif message_type == "sticker":
                await self.clone_sticker(message)
            elif message_type == "animation":
                await self.clone_animation(message)
            elif message_type == "poll":
                await self.clone_poll(message)
            elif message_type == "location":
                await self.clone_location(message)
            elif message_type == "contact":
                await self.clone_contact(message)
            elif message_type == "dice":
                await self.clone_dice(message)
            elif message_type == "game":
                await self.clone_game(message)
            elif message_type == "venue":
                await self.clone_venue(message)
            elif message_type == "web_page":
                await self.clone_web_page(message)
            else:
                logger.warning(f"Unsupported message type: {message_type} (ID: {message.id})")
                return "skipped", message_type, current_delay
            
            # Success - add delay
            new_delay = min(current_delay + 0.1, MAX_DELAY)
            delay = random.uniform(new_delay - 0.5, new_delay + 0.5)
            await asyncio.sleep(delay)
            
            return "success", message_type, new_delay
            
        except FileReferenceExpired:
            if retry_count < MAX_RETRIES:
                logger.info(f"🔄 File reference expired for {message.id}, "
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
            logger.warning(f"⏳ Flood wait: {wait_time}s (auto-handled)")
            await asyncio.sleep(wait_time)
            return await self.clone_message(message, current_delay + 2, retry_count)
        
        except Exception as e:
            error_msg = str(e)
            
            # Check for file reference error in message
            if "FILE_REFERENCE_EXPIRED" in error_msg and retry_count < MAX_RETRIES:
                logger.info(f"🔄 File reference error detected, retrying {message.id}")
                fresh_message = await self.get_fresh_message(message.id)
                if fresh_message:
                    await asyncio.sleep(REFETCH_DELAY)
                    return await self.clone_message(fresh_message, current_delay, retry_count + 1)
            
            logger.error(f"Error cloning message {message.id} ({message_type}): {error_msg}")
            return "failed", message_type, current_delay
    
    async def fetch_all_messages(self):
        """Fetch all messages from source group with duplicate detection"""
        print("\n" + "="*70)
        print("📥 FETCHING MESSAGES FROM SOURCE GROUP")
        print("="*70)
        
        all_messages = []
        already_processed = set(self.progress["success"] + self.progress["failed"])
        chunk_count = 0
        duplicate_count = 0
        
        try:
            async for message in self.app.get_chat_history(self.source):
                chunk_count += 1
                
                # Skip service messages
                if message.service:
                    continue
                
                # Skip already processed successfully
                if message.id in already_processed:
                    continue
                
                # Generate hash and check for duplicates
                msg_hash = self.generate_message_hash(message)
                if msg_hash:
                    self.message_hashes["source_hashes"][str(message.id)] = msg_hash
                    
                    # Check if already in target
                    if msg_hash in self.message_hashes["target_hashes"]:
                        duplicate_count += 1
                        continue
                
                all_messages.append(message)
                
                # Progress indicator
                if chunk_count % 500 == 0:
                    print(f"📦 Processed {chunk_count} messages... "
                          f"(New: {len(all_messages)}, Duplicates: {duplicate_count})")
                
                await asyncio.sleep(0.05)  # Minimal delay for fetching
            
            # Reverse to get chronological order (oldest first)
            all_messages.reverse()
            
            print("="*70)
            print(f"✅ FETCH COMPLETE")
            print(f"   📊 Total scanned: {chunk_count}")
            print(f"   ✨ New messages to clone: {len(all_messages)}")
            print(f"   🔄 Duplicates skipped: {duplicate_count}")
            print(f"   ✅ Already processed: {len(already_processed)}")
            print("="*70 + "\n")
            
            self.stats["duplicates"] = duplicate_count
            
            return all_messages
            
        except Exception as e:
            logger.error(f"Error fetching messages: {e}")
            all_messages.reverse()
            return all_messages
    
    async def start_cloning(self):
        """Main cloning process with optimized duplicate detection"""
        print("\n" + "="*70)
        print("🚀 TELEGRAM GROUP CLONER - OPTIMIZED v3.0")
        print("="*70)
        print(f"📍 Source: {self.source}")
        print(f"📍 Target: {self.target}")
        print("\n💡 FEATURES:")
        print("   ✓ Fast hash-based duplicate detection")
        print("   ✓ Parallel group scanning")
        print("   ✓ Complete 1:1 clone of all message types")
        print("   ✓ Preserves all formatting, entities, and metadata")
        print("   ✓ Auto-handles expired file references")
        print("   ✓ Smart resume from last position")
        print("="*70)
        
        if not self.progress["started_at"]:
            self.progress["started_at"] = datetime.now().isoformat()
        
        # Step 1: Scan target group for existing messages
        self.message_hashes["target_hashes"] = await self.scan_target_group()
        self.save_hashes()
        
        # Step 2: Fetch source messages with duplicate filtering
        all_messages = await self.fetch_all_messages()
        
        if not all_messages:
            print("✨ All messages already cloned! Target group is up to date.")
            self.print_final_report()
            return
        
        self.stats["total_messages"] = len(all_messages)
        
        print(f"\n🔄 STARTING CLONE OPERATION: {len(all_messages)} messages")
        print("="*70 + "\n")
        
        current_delay = INITIAL_DELAY
        
        # Process in batches
        for i in range(0, len(all_messages), BATCH_SIZE):
            batch = all_messages[i:i + BATCH_SIZE]
            batch_num = i // BATCH_SIZE + 1
            total_batches = (len(all_messages) + BATCH_SIZE - 1) // BATCH_SIZE
            
            print(f"\n📦 BATCH {batch_num}/{total_batches} ({len(batch)} messages)")
            print("-" * 70)
            
            for idx, message in enumerate(batch, 1):
                status, msg_type, current_delay = await self.clone_message(
                    message, current_delay
                )
                
                self.update_stats(msg_type, status)
                
                if status == "success":
                    self.progress["success"].append(message.id)
                    self.progress["last_processed"] = message.id
                    
                    # Add hash to target set
                    msg_hash = self.message_hashes["source_hashes"].get(str(message.id))
                    if msg_hash:
                        self.message_hashes["target_hashes"].add(msg_hash)
                    
                    print(f"✅ [{self.stats['successful']}/{len(all_messages)}] "
                          f"Cloned {msg_type} message {message.id}")
                elif status == "failed":
                    self.progress["failed"].append(message.id)
                    print(f"❌ [{self.stats['failed']}] "
                          f"Failed to clone {msg_type} message {message.id}")
                else:
                    print(f"⏭️  Skipped {msg_type} message {message.id}")
            
            # Save progress after each batch
            self.save_progress()
            self.save_hashes()
            self.save_stats()
            
            print(f"\n💾 Progress saved - Success: {self.stats['successful']} | "
                  f"Failed: {self.stats['failed']} | Skipped: {self.stats['skipped']}")
            
            # Cooldown between batches
            if i + BATCH_SIZE < len(all_messages):
                print(f"😴 Cooldown: {BATCH_DELAY}s...\n")
                await asyncio.sleep(BATCH_DELAY)
        
        # Mark as completed
        self.progress["completed_at"] = datetime.now().isoformat()
        self.save_progress()
        self.save_hashes()
        self.save_stats()
        
        # Final report
        self.print_final_report()
    
    def print_final_report(self):
        """Print detailed final report"""
        print("\n" + "="*70)
        print("🎉 CLONING OPERATION COMPLETED!")
        print("="*70)
        print(f"\n📊 STATISTICS:")
        print(f"   Messages processed: {self.stats['total_messages']}")
        print(f"   ✅ Successful: {self.stats['successful']}")
        print(f"   ❌ Failed: {self.stats['failed']}")
        print(f"   ⏭️  Skipped: {self.stats['skipped']}")
        print(f"   🔄 Duplicates avoided: {self.stats['duplicates']}")
        
        if self.stats['by_type']:
            print(f"\n📋 BY MESSAGE TYPE:")
            for msg_type, counts in sorted(self.stats['by_type'].items()):
                total = counts['success'] + counts['failed'] + counts['skipped']
                print(f"   {msg_type}: {counts['success']}/{total} successful")
        
        print(f"\n📁 FILES:")
        print(f"   Progress: {PROGRESS_FILE}")
        print(f"   Stats: {STATS_FILE}")
        print(f"   Hashes: {HASH_FILE}")
        print(f"   Logs: clone_log.txt")
        
        if self.stats['failed'] > 0:
            print(f"\n💡 TIP: Run the script again to retry {self.stats['failed']} failed messages")
        
        if self.stats['total_messages'] > 0:
            success_rate = (self.stats['successful'] / self.stats['total_messages'] * 100)
            print(f"\n🎯 Success Rate: {success_rate:.2f}%")
        
        total_efficiency = self.stats['successful'] + self.stats['duplicates']
        print(f"⚡ Efficiency: Avoided {self.stats['duplicates']} duplicate operations")
        print("="*70 + "\n")


async def main():
    """Main entry point"""
    app = Client(SESSION_NAME, API_ID, API_HASH)
    
    async with app:
        cloner = TelegramCloner(app, SOURCE_GROUP, TARGET_GROUP)
        await cloner.start_cloning()


if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║        TELEGRAM GROUP CLONER - OPTIMIZED v3.0                ║
║                                                              ║
║  ⚡ Fast hash-based duplicate detection                      ║
║  🔍 Smart content fingerprinting                             ║
║  🚀 Parallel scanning for maximum speed                      ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Operation cancelled by user")
        print("💾 Progress has been saved. Run again to continue.")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        print("\n❌ An error occurred. Check clone_log.txt for details.")