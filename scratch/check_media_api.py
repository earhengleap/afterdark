import urllib.request
import json

try:
    url = "http://127.0.0.1:5000/api/media?limit=50&offset=0&filter=all&sort=newest&search="
    response = urllib.request.urlopen(url, timeout=5)
    data = json.loads(response.read())
    print(f"Total items in response: {data.get('total')}")
    print(f"Number of items returned: {len(data.get('items', []))}")
    if data.get('items'):
        print(f"First item: {data['items'][0]['message_id']}")
except Exception as e:
    print(f"Error hitting media endpoint: {e}")
