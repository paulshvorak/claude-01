import csv
import logging
from datetime import datetime
from pathlib import Path

import requests

from config import APIFY_TOKEN
from sources.base import Item

logger = logging.getLogger(__name__)

ACCOUNTS_PATH = Path(__file__).resolve().parent.parent / "data" / "accounts_to_classify-compact.csv"
ACTOR_URL = "https://api.apify.com/v2/acts/apify~instagram-scraper/run-sync-get-dataset-items"


def _load_usernames() -> list:
    with open(ACCOUNTS_PATH, newline="", encoding="utf-8") as f:
        return [row["username"] for row in csv.DictReader(f)]


class InstagramSource:
    name = "instagram_posts"

    def fetch(self) -> list[Item]:
        usernames = _load_usernames()
        payload = {
            "directUrls": [f"https://www.instagram.com/{u}/" for u in usernames],
            "resultsType": "posts",
            "resultsLimit": 1,
        }

        try:
            response = requests.post(ACTOR_URL, params={"token": APIFY_TOKEN}, json=payload, timeout=180)
            response.raise_for_status()
        except requests.RequestException:
            logger.exception("instagram: apify call failed")
            return []

        fetched_at = datetime.now().isoformat()
        items = []
        for post in response.json():
            if "error" in post:
                continue

            items.append(Item(
                external_id=post["shortCode"],
                fetched_at=fetched_at,
                payload={
                    "owner": post.get("ownerUsername"),
                    "caption": post.get("caption") or "",
                    "link": post["url"],
                    "timestamp": post.get("timestamp"),
                    "likes": post.get("likesCount"),
                },
            ))

        return items


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    for item in InstagramSource().fetch():
        print(item.payload["owner"], "|", item.payload["caption"][:80], "|", item.payload["link"])
