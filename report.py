from __future__ import annotations

import html
import logging
import subprocess

from db import get_unsent

logger = logging.getLogger(__name__)

INSTAGRAM_SUMMARY_PROMPT = """Ось останні пости з Instagram-акаунтів, на які я підписаний:

{posts}

Напиши короткий зв'язний підсумок українською (3-6 речень) — що зараз у них відбувається. \
Без вступних кліше на кшталт "ось підсумок" чи "у вашій стрічці". Не вигадуй деталей, \
яких немає в текстах постів. Якщо пости геть не пов'язані між собою — просто перелічи суть \
кожного одним реченням."""


def build_instagram_digest(header: str) -> str | None:
    items = get_unsent("instagram_posts")
    if not items:
        return None

    posts = "\n\n".join(f"@{item['payload']['owner']}: {item['payload']['caption']}" for item in items)
    prompt = INSTAGRAM_SUMMARY_PROMPT.format(posts=posts)

    summary = None
    try:
        result = subprocess.run(
            ["claude", "-p", prompt, "--model", "claude-haiku-4-5-20251001"],
            capture_output=True, text=True, timeout=90,
        )
        if result.returncode == 0 and result.stdout.strip():
            summary = result.stdout.strip()
        else:
            logger.error("instagram digest: claude -p failed (code=%s): %s", result.returncode, result.stderr[:500])
    except (subprocess.TimeoutExpired, OSError):
        logger.exception("instagram digest: claude -p call failed")

    lines = [f"<b>{html.escape(header)}</b>", ""]
    if summary:
        lines.append(html.escape(summary))
    lines.append("")
    for item in items:
        owner = html.escape(item["payload"]["owner"])
        link = html.escape(item["payload"]["link"], quote=True)
        lines.append(f'• @{owner} — <a href="{link}">Детальніше</a>')
    return "\n".join(lines)


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
