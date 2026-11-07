from __future__ import annotations

from db import get_unsent


def build_digest(table: str, header: str) -> str | None:
    items = get_unsent(table)
    if not items:
        return None

    lines = [header, ""]
    lines += [f"• {item['payload']['title']} — {item['payload']['link']}" for item in items]
    return "\n".join(lines)
