"""
Export download history to various formats
"""

import csv
import io
from datetime import datetime
from typing import List, Dict


def export_to_csv(history_entries: List[Dict]) -> io.BytesIO:
    """
    Export history to CSV format (Excel-compatible)
    
    Args:
        history_entries: List of history entry dictionaries
        
    Returns:
        BytesIO object containing CSV data
    """
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow([
        '#', 'Date', 'Time', 'Username', 'URL', 
        'Filename', 'Type', 'Size (MB)', 'Status', 'Error'
    ])
    
    # Write data rows
    for idx, entry in enumerate(history_entries, 1):
        timestamp = entry['timestamp']
        size_mb = f"{entry['file_size'] / (1024*1024):.2f}" if entry['file_size'] else '0.00'
        
        writer.writerow([
            idx,
            timestamp.strftime('%Y-%m-%d'),
            timestamp.strftime('%H:%M:%S'),
            entry['source_username'] or 'N/A',
            entry['url'],
            entry['filename'] or 'N/A',
            entry['content_type'],
            size_mb,
            entry['status'],
            entry['error_message'] or ''
        ])
    
    # Convert to bytes with UTF-8 BOM for Excel compatibility
    output.seek(0)
    return io.BytesIO(output.getvalue().encode('utf-8-sig'))


def export_to_text(history_entries: List[Dict]) -> io.BytesIO:
    """
    Export history to formatted text file
    
    Args:
        history_entries: List of history entry dictionaries
        
    Returns:
        BytesIO object containing text data
    """
    output = io.StringIO()
    
    # Header
    output.write("═" * 70 + "\n")
    output.write(" " * 20 + "DOWNLOAD HISTORY\n")
    output.write("═" * 70 + "\n\n")
    output.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    output.write(f"Total Entries: {len(history_entries)}\n")
    output.write("═" * 70 + "\n\n")
    
    # Entries
    for idx, entry in enumerate(history_entries, 1):
        timestamp = entry['timestamp']
        output.write(f"{idx}. {timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n")
        output.write(f"   {'─' * 60}\n")
        
        # Username
        if entry['source_username']:
            output.write(f"   👤 User: {entry['source_username']}\n")
        
        # URL
        output.write(f"   🔗 URL: {entry['url']}\n")
        
        # Filename
        if entry['filename']:
            output.write(f"   📄 File: {entry['filename']}\n")
        
        # Type and Status
        status_icon = '✅' if entry['status'] == 'success' else '❌'
        output.write(f"   {status_icon} Type: {entry['content_type']} | Status: {entry['status']}\n")
        
        # File size
        if entry['file_size']:
            size_mb = entry['file_size'] / (1024 * 1024)
            if size_mb >= 1024:
                output.write(f"   💾 Size: {size_mb/1024:.2f} GB\n")
            else:
                output.write(f"   💾 Size: {size_mb:.2f} MB\n")
        
        # Error message
        if entry['error_message']:
            output.write(f"   ⚠️ Error: {entry['error_message']}\n")
        
        output.write("\n")
    
    # Footer
    output.write("═" * 70 + "\n")
    output.write(f"End of report - {len(history_entries)} total entries\n")
    output.write("═" * 70 + "\n")
    
    # Convert to bytes
    output.seek(0)
    return io.BytesIO(output.getvalue().encode('utf-8'))
