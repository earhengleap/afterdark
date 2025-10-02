# get_group_id.py

import requests
from config import BOT_TOKEN

url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"

def get_updates():
    response = requests.get(url)
    data = response.json()
    print(data)  # Print full response to see group info

if __name__ == "__main__":
    print("Send a message in your private group, then run this script.")
    get_updates()
