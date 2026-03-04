"""
Format download history for display in Telegram
"""

from typing import List, Dict
from core.parsing.url_parser import shorten_url


def format_history_message(history_entries: List[Dict], page: int, total_pages: int, total_count: int) -> str:
    """
    Format history entries into a professional Telegram message
    
    Args:
        history_entries: List of history entry dictionaries
        page: Current page number
        total_pages: Total number of pages
        total_count: Total number of entries
        
    Returns:
        Formatted message string
    """
    if not history_entries:
        return (
            "📜 **Download History**\n\n"
            "No download history yet.\n"
            "Start downloading videos or images to see your history here!"
        )
    
    # Header
    message = f"📜 **Download History**\n"
    message += f"Page {page} of {total_pages}\n\n"
    message += f"**Total Downloads:** {total_count}\n"
    message += "━━━━━━━━━━━━━━━━━━━━\n\n"
    
    # Calculate global index
    start_index = (page - 1) * 10
    
    # Entries
    for idx, entry in enumerate(history_entries, start=start_index + 1):
        timestamp = entry['timestamp']
        status_icon = '✅' if entry['status'] == 'success' else '❌'
        type_icon = get_type_icon(entry['content_type'])
        
        # Entry header
        message += f"{idx}. {status_icon} **{entry['content_type'].title()}** - "
        message += f"{timestamp.strftime('%Y-%m-%d %H:%M')}\n"
        
        # Username (if available)
        if entry['source_username']:
            message += f"   👤 {entry['source_username']}\n"
        
        # URL (shortened)
        short_url = shorten_url(entry['url'], max_length=45)
        message += f"   🔗 `{short_url}`\n"
        
        # Filename and size (if successful)
        if entry['status'] == 'success' and entry['filename']:
            filename = entry['filename']
            if len(filename) > 35:
                filename = filename[:32] + '...'
            message += f"   {type_icon} `{filename}`"
            
            if entry['file_size']:
                size_mb = entry['file_size'] / (1024 * 1024)
                if size_mb >= 1024:
                    message += f" ({size_mb/1024:.2f} GB)"
                else:
                    message += f" ({size_mb:.1f} MB)"
            message += "\n"
        
        # Error message (if failed)
        elif entry['status'] == 'failed' and entry['error_message']:
            error = entry['error_message']
            if len(error) > 50:
                error = error[:47] + '...'
            message += f"   ⚠️ {error}\n"
        
        message += "\n"
    
    # Footer
    message += "━━━━━━━━━━━━━━━━━━━━\n"
    start_num = start_index + 1
    end_num = start_index + len(history_entries)
    message += f"Showing {start_num}-{end_num} of {total_count}"
    
    return message


def get_type_icon(content_type: str) -> str:
    """Get emoji icon for content type"""
    icons = {
        'video': '📹',
        'image': '📸',
        'unknown': '❓'
    }
    return icons.get(content_type, '📄')


def format_export_message(total_entries: int) -> str:
    """Format export selection message"""
    return (
        f"📊 **Export Download History**\n\n"
        f"Total entries: **{total_entries}**\n\n"
        f"Choose export format:"
    )


def format_clear_confirmation(total_entries: int) -> str:
    """Format clear history confirmation message"""
    return (
        f"⚠️ **Clear Download History?**\n\n"
        f"This will permanently delete all **{total_entries}** download records.\n"
        f"This action cannot be undone.\n\n"
        f"Are you sure you want to continue?"
    )
