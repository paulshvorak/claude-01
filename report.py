from __future__ import annotations

import html

from db import get_unsent


def build_digest(table: str, header: str) -> str | None:
    items = get_unsent(table)
    if not items:
        return None

    lines = [f"<b>{html.escape(header)}</b>", ""]
    for item in items:
        title = html.escape(item["payload"]["title"])
        link = html.escape(item["payload"]["link"], quote=True)
        lines.append(f'• {title} — <a href="{link}">Детальніше</a>')
    return "\n".join(lines)
