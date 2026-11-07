import logging
from datetime import date, datetime

import requests
from bs4 import BeautifulSoup

from sources.base import Item

logger = logging.getLogger(__name__)

URL = "https://football.ua/club/5-liverpool.html"
HEADERS = {"User-Agent": "Mozilla/5.0"}

MONTHS = {
    "січня": 1, "лютого": 2, "березня": 3, "квітня": 4,
    "травня": 5, "червня": 6, "липня": 7, "серпня": 8,
    "вересня": 9, "жовтня": 10, "листопада": 11, "грудня": 12,
}


def _parse_news_date(text: str) -> date:
    day, month_name, year = text.strip().split()
    return date(int(year), MONTHS[month_name], int(day))


class FootballSource:
    name = "football_articles"

    def fetch(self) -> list[Item]:
        try:
            response = requests.get(URL, headers=HEADERS, timeout=15)
            response.raise_for_status()
        except requests.RequestException:
            logger.exception("football.ua: fetch failed")
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        feed = soup.find("article", class_="news-feed")
        if feed is None:
            logger.error("football.ua: news-feed block not found")
            return []

        fetched_at = datetime.now().isoformat()
        current_date = date.today()
        items = []

        for li in feed.find_all("li"):
            if "news-date" in li.get("class", []):
                current_date = _parse_news_date(li.get_text())
                continue

            time_el = li.find("div", class_="time")
            link_el = li.find("a", href=True)
            if time_el is None or link_el is None:
                continue

            hour, minute = time_el.get_text().strip().split(":")[:2]
            published_at = datetime(
                current_date.year, current_date.month, current_date.day,
                int(hour), int(minute[:2]),
            ).isoformat()

            items.append(Item(
                external_id=link_el["href"],
                fetched_at=fetched_at,
                payload={
                    "title": link_el.get_text().strip(),
                    "link": link_el["href"],
                    "published_at": published_at,
                },
            ))

        return items


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    for item in FootballSource().fetch():
        print(item.payload["published_at"], item.payload["title"], item.payload["link"])
