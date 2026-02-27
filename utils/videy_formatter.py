from typing import List, Dict


def format_videy_message(entries: List[Dict], page: int, total_pages: int, total_count: int) -> str:
    if not entries:
        return (
            "🔗 **Videy Links**\n\n"
            "No links found yet.\n\n"
            "Download a video first, then run `/videy`."
        )

    message = "🔗 **Your Videy Links (Read-only)**\n"
    message += f"Page {page} of {total_pages}\n\n"
    message += f"**Total Links:** {total_count}\n"
    message += "━━━━━━━━━━━━━━━━━━━━\n\n"

    start_index = (page - 1) * 10
    for idx, item in enumerate(entries, start=start_index + 1):
        link = item.get("link", "")
        source = item.get("source", "")
        ts = item.get("ts", "")
        message += f"{idx}. `{link}`\n"
        if source:
            short_source = source if len(source) <= 80 else source[:77] + "..."
            message += f"   Source: `{short_source}`\n"
        if ts:
            message += f"   Time: `{ts} UTC`\n"
        message += "\n"

    message += "━━━━━━━━━━━━━━━━━━━━\n"
    end_num = start_index + len(entries)
    message += f"Showing {start_index + 1}-{end_num} of {total_count}"
    return message


def format_videy_export_message(total_entries: int) -> str:
    return (
        "📊 **Export Videy Links**\n\n"
        f"Total links: **{total_entries}**\n\n"
        "Choose export format:"
    )
