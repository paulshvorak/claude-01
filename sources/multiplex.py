import logging
import re
from datetime import date, datetime, timedelta

import requests
from bs4 import BeautifulSoup

from config import OMDB_API_KEY
from sources.base import Item

logger = logging.getLogger(__name__)

SCHEDULE_URL = "https://multiplex.ua/cinema/lutsk/promin"
MOVIE_URL = "https://multiplex.ua/movie/{id}"
OMDB_URL = "http://www.omdbapi.com/"
PREMIERCITY_URL = "https://premiercity.com.ua/rozklad/"
HEADERS = {"User-Agent": "Mozilla/5.0"}


_LATIN_TO_CYRILLIC = str.maketrans("aeiopcxyAEIOPCXY", "аеіорсхуАЕІОРСХУ")


def _normalize_title(title: str) -> str:
    # сайти інколи мають однакові на вигляд, але різні символи
    # (лат. "i" замість кир. "і" тощо) — зводимо до кирилиці перед порівнянням
    return title.strip().lower().translate(_LATIN_TO_CYRILLIC)


def _parse_schedule_date(value: str) -> date:
    return date(int(value[4:8]), int(value[2:4]), int(value[0:2]))


def _list_movies() -> list:
    response = requests.get(SCHEDULE_URL, headers=HEADERS, timeout=15)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    movies = {}
    for block in soup.select(".cinema_inside.sch_date"):
        block_date = _parse_schedule_date(block["data-date"])
        for a in block.select("a.title[href]"):
            match = re.search(r"/movie/(\d+)", a["href"])
            if not match:
                continue
            movie_id = match.group(1)
            if movie_id not in movies:
                movies[movie_id] = {
                    "id": movie_id,
                    "title": a["title"].strip(),
                    "link": f"https://multiplex.ua/movie/{movie_id}",
                    "earliest_date": block_date,
                }
            else:
                movies[movie_id]["earliest_date"] = min(movies[movie_id]["earliest_date"], block_date)

    # лише те, що йде найближчі 7 днів — не передпродаж майбутньої прем'єри
    cutoff = date.today() + timedelta(days=7)
    return [m for m in movies.values() if m["earliest_date"] <= cutoff]


def _premiercity_date(day: int, today: date) -> date:
    candidate = date(today.year, today.month, day)
    if candidate < today - timedelta(days=3):
        month, year = (1, today.year + 1) if today.month == 12 else (today.month + 1, today.year)
        candidate = date(year, month, day)
    return candidate


def _list_premiercity_movies() -> list:
    response = requests.get(PREMIERCITY_URL, headers=HEADERS, timeout=15)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    now_showing = None
    for section in soup.find_all("section"):
        title_el = section.select_one(".title-box__title")
        if title_el and "Зараз у прокаті" in title_el.get_text():
            now_showing = section
            break
    if now_showing is None:
        return []

    today = date.today()
    cutoff = today + timedelta(days=7)
    movies = []
    for figure in now_showing.select("figure.movie-hire"):
        link_el = figure.select_one(".movie-hire__title a")
        if not link_el:
            continue

        days = [int(c.split("_")[1]) for c in figure.get("class", []) if c.startswith("date_")]
        if not days:
            continue
        earliest_date = min(_premiercity_date(d, today) for d in days)
        if earliest_date > cutoff:
            continue

        match = re.search(r"-(\d+)$", link_el["href"].rstrip("/"))
        pc_id = match.group(1) if match else link_el["href"]
        movies.append({
            "id": f"pc_{pc_id}",
            "title": link_el.get_text(strip=True),
            "link": link_el["href"],
        })

    return movies


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

        known_titles = {_normalize_title(m["title"]) for m in movies}
        try:
            pc_movies = _list_premiercity_movies()
        except requests.RequestException:
            logger.exception("multiplex: premiercity fetch failed")
            pc_movies = []

        for movie in pc_movies:
            if _normalize_title(movie["title"]) in known_titles:
                continue
            items.append(Item(
                external_id=movie["id"],
                fetched_at=fetched_at,
                payload={
                    "title": movie["title"],
                    "link": movie["link"],
                    "original_title": None,
                    "year": None,
                    "rt_rating": None,
                    "imdb_rating": None,
                },
            ))

        return items


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    for item in MultiplexSource().fetch():
        p = item.payload
        print(f"{p['title']} ({p['original_title']}, {p['year']}) — IMDb {p['imdb_rating']} · RT {p['rt_rating']}")
