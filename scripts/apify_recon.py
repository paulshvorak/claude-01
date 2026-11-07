import json
from pathlib import Path

import requests

from config import APIFY_TOKEN

FOLLOWING_PATH = Path(__file__).resolve().parent.parent / "data" / "following.json"
SAMPLE_SIZE = 5


def main():
    following = json.loads(FOLLOWING_PATH.read_text())
    usernames = [u["username"] for u in following if not u.get("is_private")][:SAMPLE_SIZE]
    print("test usernames:", usernames)

    url = "https://api.apify.com/v2/acts/apify~instagram-scraper/run-sync-get-dataset-items"
    payload = {
        "directUrls": [f"https://www.instagram.com/{u}/" for u in usernames],
        "resultsType": "posts",
        "resultsLimit": 3,
        "onlyPostsNewerThan": "7 days",
    }

    response = requests.post(url, params={"token": APIFY_TOKEN}, json=payload, timeout=120)
    response.raise_for_status()
    items = response.json()

    print(f"\nповернуто постів: {len(items)}\n")
    for item in items:
        caption = (item.get("caption") or "").replace("\n", " ")[:80]
        print(f"- @{item.get('ownerUsername')} | {item.get('timestamp')} | {caption!r} | {item.get('url')}")


if __name__ == "__main__":
    main()
