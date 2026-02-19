#!/usr/bin/env python3
"""
Script to force AI analysis on all existing media.
This triggers the background worker to scan all items and generate missing titles.
"""

import json
import time
import urllib.request
import urllib.error
import sys

SERVER_URL = "http://localhost:5000"

def check_server():
    """Check if the Mini App server is running."""
    print("reconnecting to server...")
    try:
        with urllib.request.urlopen(f"{SERVER_URL}/api/health", timeout=2) as response:
            data = json.loads(response.read())
            if data.get("ok"):
                print("Server is online!")
                return True
    except urllib.error.URLError:
        print("Server is offline.")
        print("Please start the server first: python telegram-bot-websites/server.py")
        return False
    except Exception as e:
        print(f"Error connecting to server: {e}")
        return False

def trigger_analysis():
    """Trigger AI analysis for all items with missing titles."""
    print("Triggering AI analysis for all items...")
    
    # mode="missing" means only generate for items that don't have titles yet
    # recent_limit=0 means scan ALL items in the index, not just recent ones
    params = json.dumps({
        # These are query params in the API, but let's try sending as correct query string
        # actually the endpoint takes query params, not body json for these args usually?
        # Let's check server.py: 
        # async def api_ai_titles(
        #     batch_size: int = Query(...),
        #     recent_limit: int = Query(...),
        #     mode: str = Query(...)
        # )
        # So they must be query parameters.
    })
    
    url = f"{SERVER_URL}/api/ai-titles?mode=missing&recent_limit=0&batch_size=10"
    
    try:
        req = urllib.request.Request(url, method="POST")
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read())
            
        if data.get("ok"):
            generated = data.get("generated", 0)
            titled_count = data.get("ai_titled_count", 0)
            total_cached = data.get("cached_items", 0)
            timed_out = data.get("timed_out", False)
            
            print(f"Request successful!")
            if timed_out:
                print("Analysis started in background (request timed out waiting for completion).")
            else:
                print(f"Processed batch: {generated} titles generating/generated.")
            
            print(f"Current Status:")
            print(f"- Total items: {total_cached}")
            print(f"- Items with AI titles: {titled_count}")
            print(f"- Remaining: {max(0, total_cached - titled_count)}")
            
            if total_cached - titled_count > 0:
                print("\nThe background worker is now processing the queue.")
                print("You can see progress in the server console/logs.")
            else:
                print("\nAll items appear to have titles!")
                
    except urllib.error.HTTPError as e:
        print(f"Error triggering analysis: HTTP {e.code} - {e.reason}")
        try:
            body = e.read().decode()
            print(f"Response: {body}")
        except:
            pass
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    if check_server():
        trigger_analysis()
    else:
        sys.exit(1)
