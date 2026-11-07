import logging
import re
from datetime import datetime

import requests
from bs4 import BeautifulSoup

from config import OMDB_API_KEY
from sources.base import Item

logger = logging.getLogger(__name__)

SCHEDULE_URL = "https://multiplex.ua/cinema/lutsk/promin"
MOVIE_URL = "https://multiplex.ua/movie/{id}"
OMDB_URL = "http://www.omdbapi.com/"
HEADERS = {"User-Agent": "Mozilla/5.0"}


def _list_movies() -> list:
    response = requests.get(SCHEDULE_URL, headers=HEADERS, timeout=15)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    movies = {}
    for a in soup.select(".cinema_schedule_films a.title[href]"):
        match = re.search(r"/movie/(\d+)", a["href"])
        if not match:
            continue
        movie_id = match.group(1)
        if movie_id not in movies:
            movies[movie_id] = {
                "id": movie_id,
                "title": a["title"].strip(),
                "link": f"https://multiplex.ua/movie/{movie_id}",
            }
    return list(movies.values())


def _fetch_details(movie_id: str) -> dict:
    response = requests.get(MOVIE_URL.format(id=movie_id), headers=HEADERS, timeout=15)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    info = {}
    for li in soup.select("li"):
        key_el = li.find("p", class_="key")
        val_el = li.find("p", class_="val")
        if key_el and val_el:
            info[key_el.get_text().strip().rstrip(":")] = val_el.get_text().strip()

    rt_match = re.search(r"\d+", info.get("Рейтинг критиків", ""))
    return {
        "original_title": info.get("Оригінальна назва"),
        "year": info.get("Рік"),
        "rt_rating": int(rt_match.group()) if rt_match else None,
    }


def _fetch_imdb_rating(original_title: str, year: str):
    if not original_title or not OMDB_API_KEY:
        return None
    params = {"apikey": OMDB_API_KEY, "t": original_title}
    if year:
        params["y"] = year
    response = requests.get(OMDB_URL, params=params, timeout=15)
    response.raise_for_status()
    data = response.json()
    if data.get("Response") != "True":
        return None
    try:
        return float(data["imdbRating"])
    except (KeyError, ValueError):
        return None


class MultiplexSource:
    name = "multiplex_movies"

    def fetch(self) -> list[Item]:
        try:
            movies = _list_movies()
        except requests.RequestException:
            logger.exception("multiplex: schedule fetch failed")
            return []

        fetched_at = datetime.now().isoformat()
        items = []
        for movie in movies:
            details = {"original_title": None, "year": None, "rt_rating": None}
            try:
                details = _fetch_details(movie["id"])
            except requests.RequestException:
                logger.exception("multiplex: details fetch failed for %s", movie["id"])

            imdb_rating = None
            try:
                imdb_rating = _fetch_imdb_rating(details["original_title"], details["year"])
            except requests.RequestException:
                logger.exception("multiplex: omdb lookup failed for %s", movie["id"])

            items.append(Item(
                external_id=movie["id"],
                fetched_at=fetched_at,
                payload={
                    "title": movie["title"],
                    "link": movie["link"],
                    "original_title": details["original_title"],
                    "year": details["year"],
                    "rt_rating": details["rt_rating"],
                    "imdb_rating": imdb_rating,
                },
            ))

        return items


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    for item in MultiplexSource().fetch():
        p = item.payload
        print(f"{p['title']} ({p['original_title']}, {p['year']}) — IMDb {p['imdb_rating']} · RT {p['rt_rating']}")
