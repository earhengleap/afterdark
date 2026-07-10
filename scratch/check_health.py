import urllib.request
import json

try:
    response = urllib.request.urlopen("http://127.0.0.1:5000/api/health", timeout=5)
    data = json.loads(response.read())
    print(json.dumps(data, indent=2))
except Exception as e:
    print(f"Error hitting health endpoint: {e}")
