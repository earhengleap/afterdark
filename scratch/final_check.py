import urllib.request
import json
import socket

# Try IPv4 and IPv6
for host in ["127.0.0.1", "localhost", "::1"]:
    print(f"Testing {host}:5000/api/media...")
    try:
        url = f"http://{host}:5000/api/media?limit=50&offset=0&filter=all&sort=newest&search="
        response = urllib.request.urlopen(url, timeout=10)
        data = json.loads(response.read())
        print(f"SUCCESS on {host} - Total: {data.get('total')}")
    except Exception as e:
        print(f"FAILED on {host}: {e}")

print("\nTesting port 3000 (Vite Proxy)...")
try:
    url = "http://localhost:3000/api/media?limit=50&offset=0&filter=all&sort=newest&search="
    response = urllib.request.urlopen(url, timeout=10)
    data = json.loads(response.read())
    print(f"SUCCESS on port 3000 - Total: {data.get('total')}")
except Exception as e:
    print(f"FAILED on port 3000: {e}")
