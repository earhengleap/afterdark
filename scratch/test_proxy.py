import urllib.request
import json

try:
    # Testing the proxy
    url = "http://127.0.0.1:3000/api/media?limit=50&offset=0&filter=all&sort=newest&search="
    response = urllib.request.urlopen(url, timeout=5)
    data = json.loads(response.read())
    print(f"Proxy test - Total items: {data.get('total')}")
    print(f"Proxy test - Items returned: {len(data.get('items', []))}")
except Exception as e:
    print(f"Proxy test failed: {e}")
