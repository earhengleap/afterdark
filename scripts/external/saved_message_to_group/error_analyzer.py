from telethon import TelegramClient, types
import asyncio
import json
import os
from datetime import datetime

api_id = 22268900
api_hash = '6764e4d6dd12108e82105f355c6309d8'

session_file = 'my_telegram_session'
failed_messages_file = "failed_messages.json"
permanent_failed_file = "permanent_failed.json"
analysis_report_file = "failed_messages_analysis.txt"

client = TelegramClient(session_file, api_id, api_hash)

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

def load_failed_messages():
    """Load failed messages from JSON file"""
    if os.path.exists(failed_messages_file):
        try:
            with open(failed_messages_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading failed_messages.json: {e}")
            return []
    return []

def load_permanent_failed():
    """Load permanent failed messages"""
    if os.path.exists(permanent_failed_file):
        try:
            with open(permanent_failed_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading permanent_failed.json: {e}")
            return []
    return []

async def analyze_message(msg_id):
    """Fetch and analyze a message to determine its type"""
    try:
        message = await client.get_messages('me', ids=msg_id)
        
        if not message:
            return {
                'type': 'DELETED',
                'description': 'Message has been deleted from Saved Messages',
                'has_caption': False,
                'caption_preview': None,
                'file_size': None,
                'duration': None
            }
        
        analysis = {
            'type': 'UNKNOWN',
            'description': '',
            'has_caption': bool(message.text),
            'caption_preview': message.text[:100] if message.text else None,
            'file_size': None,
            'duration': None,
            'is_pinned': message.pinned
        }
        
        # Check for video
        if message.video:
            analysis['type'] = 'VIDEO'
            analysis['description'] = f"Video file"
            if message.video.size:
                analysis['file_size'] = f"{message.video.size / (1024*1024):.2f} MB"
            if message.video.duration:
                mins = message.video.duration // 60
                secs = message.video.duration % 60
                analysis['duration'] = f"{mins}:{secs:02d}"
        
        # Check for photo
        elif message.photo:
            analysis['type'] = 'PHOTO'
            analysis['description'] = "Photo/Image"
            if message.photo.sizes:
                largest = max(message.photo.sizes, key=lambda s: s.size if hasattr(s, 'size') else 0)
                if hasattr(largest, 'size'):
                    analysis['file_size'] = f"{largest.size / (1024*1024):.2f} MB"
        
        # Check for document/GIF
        elif message.document:
            if is_gif_document(message.document):
                analysis['type'] = 'GIF'
                analysis['description'] = "GIF/Animation"
            else:
                analysis['type'] = 'DOCUMENT'
                analysis['description'] = f"Document ({message.document.mime_type})"
            
            if message.document.size:
                analysis['file_size'] = f"{message.document.size / (1024*1024):.2f} MB"
        
        # Check for text
        elif message.text:
            analysis['type'] = 'TEXT'
            analysis['description'] = "Text message"
        
        return analysis
        
    except Exception as e:
        return {
            'type': 'ERROR',
            'description': f'Error fetching: {str(e)}',
            'has_caption': False,
            'caption_preview': None,
            'file_size': None,
            'duration': None
        }

async def main():
    print("\n" + "="*80)
    print("🔍 FAILED MESSAGES ANALYZER")
    print("="*80)
    print("This tool will analyze ALL your failed messages and tell you exactly what they are")
    print("="*80 + "\n")
    
    # Connect
    print("📡 Connecting to Telegram...")
    await client.start()
    me = await client.get_me()
    print(f"✅ Logged in as: {me.first_name} (@{me.username})\n")
    
    # Load failed messages
    failed_list = load_failed_messages()
    permanent_list = load_permanent_failed()
    
    if not failed_list and not permanent_list:
        print("✅ No failed messages found! Everything was sent successfully.\n")
        return
    
    print(f"📊 Found:")
    print(f"   ⚠️  Retryable failures: {len(failed_list)}")
    print(f"   ⛔ Permanent failures: {len(permanent_list)}")
    print(f"   📝 Total: {len(failed_list) + len(permanent_list)}\n")
    
    print("🔍 Analyzing messages... This may take a moment...\n")
    
    # Analyze retryable failures
    retryable_analysis = {}
    type_stats = {
        'VIDEO': 0,
        'PHOTO': 0,
        'GIF': 0,
        'TEXT': 0,
        'DOCUMENT': 0,
        'DELETED': 0,
        'ERROR': 0,
        'UNKNOWN': 0
    }
    
    # Group by message ID
    failures_by_msg = {}
    for entry in failed_list:
        msg_id = entry['msg_id']
        if msg_id not in failures_by_msg:
            failures_by_msg[msg_id] = []
        failures_by_msg[msg_id].append(entry)
    
    print(f"📋 Analyzing {len(failures_by_msg)} unique retryable message(s)...\n")
    
    analyzed_count = 0
    for msg_id, failures in failures_by_msg.items():
        analyzed_count += 1
        print(f"   Analyzing message {analyzed_count}/{len(failures_by_msg)}...", end='\r')
        
        analysis = await analyze_message(msg_id)
        type_stats[analysis['type']] += 1
        
        retryable_analysis[msg_id] = {
            'analysis': analysis,
            'failures': failures
        }
        
        await asyncio.sleep(0.5)  # Small delay to avoid rate limits
    
    print("\n")
    
    # Analyze permanent failures
    permanent_analysis = {}
    permanent_stats = {
        'VIDEO': 0,
        'PHOTO': 0,
        'GIF': 0,
        'TEXT': 0,
        'DOCUMENT': 0,
        'DELETED': 0,
        'ERROR': 0,
        'UNKNOWN': 0
    }
    
    if permanent_list:
        permanent_by_msg = {}
        for entry in permanent_list:
            msg_id = entry['msg_id']
            if msg_id not in permanent_by_msg:
                permanent_by_msg[msg_id] = []
            permanent_by_msg[msg_id].append(entry)
        
        print(f"📋 Analyzing {len(permanent_by_msg)} unique permanent failure(s)...\n")
        
        analyzed_count = 0
        for msg_id, failures in permanent_by_msg.items():
            analyzed_count += 1
            print(f"   Analyzing message {analyzed_count}/{len(permanent_by_msg)}...", end='\r')
            
            analysis = await analyze_message(msg_id)
            permanent_stats[analysis['type']] += 1
            
            permanent_analysis[msg_id] = {
                'analysis': analysis,
                'failures': failures
            }
            
            await asyncio.sleep(0.5)
        
        print("\n")
    
    # Generate report
    print("\n" + "="*80)
    print("📊 ANALYSIS RESULTS")
    print("="*80 + "\n")
    
    # Retryable failures summary
    if retryable_analysis:
        print("⚠️  RETRYABLE FAILURES (can be retried with 'y' option):")
        print("-" * 80)
        for msg_type, count in type_stats.items():
            if count > 0:
                icon = {
                    'VIDEO': '🎥',
                    'PHOTO': '📷',
                    'GIF': '🎞️',
                    'TEXT': '💬',
                    'DOCUMENT': '📄',
                    'DELETED': '🗑️',
                    'ERROR': '❌',
                    'UNKNOWN': '❓'
                }.get(msg_type, '❓')
                print(f"   {icon} {msg_type}: {count}")
        print()
    
    # Permanent failures summary
    if permanent_analysis:
        print("⛔ PERMANENT FAILURES (cannot be recovered):")
        print("-" * 80)
        for msg_type, count in permanent_stats.items():
            if count > 0:
                icon = {
                    'VIDEO': '🎥',
                    'PHOTO': '📷',
                    'GIF': '🎞️',
                    'TEXT': '💬',
                    'DOCUMENT': '📄',
                    'DELETED': '🗑️',
                    'ERROR': '❌',
                    'UNKNOWN': '❓'
                }.get(msg_type, '❓')
                print(f"   {icon} {msg_type}: {count}")
        print()
    
    # Detailed report
    print("="*80)
    print("📝 DETAILED REPORT")
    print("="*80 + "\n")
    
    report_lines = []
    report_lines.append("="*80)
    report_lines.append("FAILED MESSAGES DETAILED ANALYSIS")
    report_lines.append(f"Generated: {datetime.now().isoformat()}")
    report_lines.append("="*80)
    report_lines.append("")
    
    if retryable_analysis:
        report_lines.append("⚠️  RETRYABLE FAILURES")
        report_lines.append("="*80)
        report_lines.append("")
        
        for msg_id, data in retryable_analysis.items():
            analysis = data['analysis']
            failures = data['failures']
            
            report_lines.append(f"Message ID: {msg_id}")
            report_lines.append(f"Type: {analysis['type']} - {analysis['description']}")
            
            if analysis['file_size']:
                report_lines.append(f"Size: {analysis['file_size']}")
            if analysis['duration']:
                report_lines.append(f"Duration: {analysis['duration']}")
            if analysis['is_pinned']:
                report_lines.append(f"📌 This message was PINNED")
            if analysis['has_caption']:
                report_lines.append(f"Caption: {analysis['caption_preview']}")
            
            report_lines.append(f"Failed for {len(failures)} group(s):")
            for failure in failures:
                report_lines.append(f"   - {failure['group_name']}")
                report_lines.append(f"     Error: {failure['error'][:80]}")
            
            report_lines.append("-" * 80)
            report_lines.append("")
            
            # Print to console
            print(f"📌 Message ID: {msg_id}")
            print(f"   Type: {analysis['type']} - {analysis['description']}")
            if analysis['file_size']:
                print(f"   Size: {analysis['file_size']}")
            if analysis['duration']:
                print(f"   Duration: {analysis['duration']}")
            if analysis['is_pinned']:
                print(f"   📌 PINNED")
            if analysis['caption_preview']:
                print(f"   Caption: {analysis['caption_preview']}")
            print(f"   Failed for: {', '.join([f['group_name'] for f in failures])}")
            print()
    
    if permanent_analysis:
        report_lines.append("")
        report_lines.append("⛔ PERMANENT FAILURES")
        report_lines.append("="*80)
        report_lines.append("")
        
        for msg_id, data in permanent_analysis.items():
            analysis = data['analysis']
            failures = data['failures']
            
            report_lines.append(f"Message ID: {msg_id}")
            report_lines.append(f"Type: {analysis['type']} - {analysis['description']}")
            
            if analysis['file_size']:
                report_lines.append(f"Size: {analysis['file_size']}")
            if analysis['duration']:
                report_lines.append(f"Duration: {analysis['duration']}")
            if analysis['is_pinned']:
                report_lines.append(f"📌 This message was PINNED")
            if analysis['has_caption']:
                report_lines.append(f"Caption: {analysis['caption_preview']}")
            
            report_lines.append(f"Failed for {len(failures)} group(s):")
            for failure in failures:
                report_lines.append(f"   - {failure['group_name']}")
                report_lines.append(f"     Reason: {failure.get('reason', failure['error'][:80])}")
            
            report_lines.append("-" * 80)
            report_lines.append("")
            
            # Print to console
            print(f"⛔ Message ID: {msg_id}")
            print(f"   Type: {analysis['type']} - {analysis['description']}")
            if analysis['file_size']:
                print(f"   Size: {analysis['file_size']}")
            if analysis['duration']:
                print(f"   Duration: {analysis['duration']}")
            if analysis['is_pinned']:
                print(f"   📌 PINNED")
            if analysis['caption_preview']:
                print(f"   Caption: {analysis['caption_preview']}")
            print(f"   Failed for: {', '.join([f['group_name'] for f in failures])}")
            print()
    
    # Save report to file
    try:
        with open(analysis_report_file, "w", encoding="utf-8") as f:
            f.write("\n".join(report_lines))
        print(f"✅ Detailed report saved to: {analysis_report_file}\n")
    except Exception as e:
        print(f"⚠️  Could not save report file: {e}\n")
    
    # Final summary
    print("="*80)
    print("📊 SUMMARY")
    print("="*80)
    
    total_retryable = sum(type_stats.values())
    total_permanent = sum(permanent_stats.values())
    
    print(f"Total failed messages analyzed: {total_retryable + total_permanent}")
    print(f"   ⚠️  Retryable: {total_retryable} (run script and choose 'y' to retry)")
    print(f"   ⛔ Permanent: {total_permanent} (cannot be recovered)")
    print()
    
    if type_stats['DELETED'] > 0:
        print(f"⚠️  {type_stats['DELETED']} message(s) have been DELETED from Saved Messages")
        print("   These cannot be sent anymore.")
        print()
    
    if total_retryable > 0:
        print("💡 To retry failed messages:")
        print("   1. Run: python saved_to_group.py")
        print("   2. When asked 'retry failed messages?', type: y")
        print("   3. Script will refetch and retry all failures")
        print()
    
    print("="*80 + "\n")

if __name__ == "__main__":
    print("\n" + "="*80)
    print("🔍 FAILED MESSAGES ANALYZER")
    print("="*80)
    print("   This tool analyzes your failed messages and shows:")
    print("     • What type each message is (video, photo, GIF, text)")
    print("     • File size and duration (for media)")
    print("     • Which groups it failed for")
    print("     • Why it failed")
    print("     • Whether it can be retried")
    print("="*80 + "\n")
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⏹️  Analysis cancelled by user\n")
    except Exception as e:
        print(f"\n\n❌ Error: {type(e).__name__}: {e}\n")
    finally:
        try:
            if client.is_connected():
                asyncio.run(client.disconnect())
        except:
            pass
        print("✅ Session ended.\n")