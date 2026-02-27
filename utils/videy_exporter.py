import csv
import io
from datetime import datetime
from typing import List, Dict


def export_videy_to_csv(entries: List[Dict]) -> io.BytesIO:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["#", "CDN Link", "Source URL", "UTC Timestamp"])

    for idx, item in enumerate(entries, 1):
        writer.writerow([
            idx,
            item.get("link", ""),
            item.get("source", ""),
            item.get("ts", ""),
        ])

    output.seek(0)
    return io.BytesIO(output.getvalue().encode("utf-8-sig"))


def export_videy_to_text(entries: List[Dict]) -> io.BytesIO:
    output = io.StringIO()
    for item in entries:
        link = str(item.get("link", "")).strip()
        if link:
            output.write(link + "\n")
    output.seek(0)
    return io.BytesIO(output.getvalue().encode("utf-8"))
