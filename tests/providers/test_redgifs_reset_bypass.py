import asyncio
import requests
import random

async def test_bypass():
    url = "https://media.redgifs.com/BowedSleepyNandine.mp4"
    http_url = "http://media.redgifs.com/BowedSleepyNandine.mp4"
    v3_url = "https://v3.redgifs.com/BowedSleepyNandine.mp4"
    
    uas = [
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_3_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3.1 Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Mobile Safari/537.36",
        "curl/8.5.0"
    ]
    
    tests = [
        ("HTTPS + Desktop UA", url, {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"}),
        ("HTTP + Desktop UA", http_url, {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"}),
        ("V3 + Desktop UA", v3_url, {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"}),
        ("HTTPS + iPhone UA", url, {"User-Agent": uas[0]}),
        ("HTTPS + Android UA", url, {"User-Agent": uas[1]}),
    ]
    
    for name, t_url, headers in tests:
        print(f"Testing {name}...")
        try:
            resp = requests.get(t_url, headers=headers, timeout=5, stream=True)
            print(f"  Result: {resp.status_code}")
            resp.close()
        except Exception as e:
            print(f"  Failed: {type(e).__name__}")
        print("-" * 10)

if __name__ == "__main__":
    asyncio.run(test_bypass())
