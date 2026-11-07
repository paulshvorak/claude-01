from dataclasses import dataclass
from typing import Protocol


@dataclass
class Item:
    external_id: str
    fetched_at: str  # ISO 8601
    payload: dict


class Source(Protocol):
    name: str  # = назва таблиці в SQLite, напр. "football_articles"

    def fetch(self) -> list[Item]: ...
