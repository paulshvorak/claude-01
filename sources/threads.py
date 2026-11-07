import logging
import re
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

from sources.base import Item

logger = logging.getLogger(__name__)

PROFILE_DIR = Path(__file__).resolve().parent.parent / "data" / "threads_profile"
SCROLL_ROUNDS = 18

EXTRACT_POSTS_JS = """
() => {
    function findPostContainer(anchor) {
        let el = anchor;
        for (let i = 0; i < 25 && el.parentElement; i++) {
            el = el.parentElement;
            const text = el.innerText || '';
            const siblingCount = el.parentElement ? el.parentElement.children.length : 0;
            if (text.length >= 40 && siblingCount >= 2) {
                return el;
            }
        }
        return el;
    }
    const anchors = Array.from(document.querySelectorAll('a[href]'))
        .filter(a => /^\\/@[^/]+\\/post\\/[^/]+$/.test(a.getAttribute('href')));
    return anchors.map(a => ({href: a.getAttribute('href'), text: findPostContainer(a).innerText}));
}
"""

PERMALINK_RE = re.compile(r"^/@([^/]+)/post/([^/]+)$")
COUNT_LINE_RE = re.compile(r"^(\d{1,3}(?:,\d{3})*|\d+)(\.\d+)?(K|M)?$")


def _parse_count(line: str):
    match = COUNT_LINE_RE.match(line)
    if not match:
        return None
    whole, frac, suffix = match.groups()
    value = float(whole.replace(",", "") + (frac or ""))
    if suffix == "K":
        value *= 1_000
    elif suffix == "M":
        value *= 1_000_000
    return int(value)


THREAD_PART_RE = re.compile(r"^\d+/\d+$")
CYRILLIC_RE = re.compile(r"[Ѐ-ӿ]")
LETTER_RE = re.compile(r"[^\W\d_]", re.UNICODE)


def _is_cyrillic(text: str) -> bool:
    letters = LETTER_RE.findall(text)
    if len(letters) < 10:
        return False
    cyrillic = CYRILLIC_RE.findall(text)
    return len(cyrillic) / len(letters) > 0.3


def _parse_post(raw_text: str):
    lines = [line.strip() for line in raw_text.split("\n") if line.strip()]
    body_lines = []
    counts = []
    is_reply = False
    for line in lines[2:]:
        if line == "Translate":
            continue
        if line.startswith("Replying to"):
            is_reply = True
            continue
        count = _parse_count(line)
        if count is not None:
            counts.append(count)
        else:
            body_lines.append(line)
    body = "\n".join(body_lines).strip()
    likes = counts[0] if len(counts) > 0 else None
    replies = counts[1] if len(counts) > 1 else None
    is_thread_part = any(THREAD_PART_RE.match(line) for line in body_lines)
    return {
        "body": body,
        "likes": likes,
        "replies": replies,
        "is_reply": is_reply,
        "is_thread_part": is_thread_part,
        "is_cyrillic": _is_cyrillic(body),
    }


class ThreadsSource:
    name = "threads_posts"

    def fetch(self) -> list[Item]:
        posts = {}
        try:
            with sync_playwright() as p:
                context = p.chromium.launch_persistent_context(str(PROFILE_DIR), headless=True)
                page = context.new_page()
                page.goto("https://www.threads.com/", timeout=30000)
                page.wait_for_timeout(2000)

                for _ in range(SCROLL_ROUNDS):
                    for raw in page.evaluate(EXTRACT_POSTS_JS):
                        match = PERMALINK_RE.match(raw["href"])
                        if not match:
                            continue
                        author, shortcode = match.groups()
                        parsed = _parse_post(raw["text"])
                        if parsed["body"]:
                            posts[shortcode] = {"author": author, "shortcode": shortcode, **parsed}

                    page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
                    page.wait_for_timeout(1200)

                context.close()
        except Exception:
            logger.exception("threads: fetch failed")
            return []

        fetched_at = datetime.now().isoformat()
        return [
            Item(
                external_id=post["shortcode"],
                fetched_at=fetched_at,
                payload={
                    "author": post["author"],
                    "text": post["body"],
                    "likes": post["likes"],
                    "replies": post["replies"],
                    "is_reply": post["is_reply"],
                    "is_thread_part": post["is_thread_part"],
                    "is_cyrillic": post["is_cyrillic"],
                    "link": f"https://www.threads.com/@{post['author']}/post/{post['shortcode']}",
                },
            )
            for post in posts.values()
        ]


def fetch_comments(post_url: str, limit: int = 5) -> list:
    root_match = PERMALINK_RE.match(post_url.replace("https://www.threads.com", ""))
    root_shortcode = root_match.group(2) if root_match else None

    comments = {}
    try:
        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(str(PROFILE_DIR), headless=True)
            page = context.new_page()
            page.goto(post_url, timeout=30000)
            page.wait_for_timeout(2000)

            for _ in range(3):
                for raw in page.evaluate(EXTRACT_POSTS_JS):
                    match = PERMALINK_RE.match(raw["href"])
                    if not match:
                        continue
                    author, shortcode = match.groups()
                    if shortcode == root_shortcode:
                        continue
                    parsed = _parse_post(raw["text"])
                    body = parsed["body"]
                    if body and body not in ("Show replies", "Hide replies") and len(body) >= 3:
                        comments[shortcode] = {"author": author, "text": body, "likes": parsed["likes"]}

                page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
                page.wait_for_timeout(1000)

            context.close()
    except Exception:
        logger.exception("threads: fetch_comments failed for %s", post_url)
        return []

    return sorted(comments.values(), key=lambda c: c["likes"] or 0, reverse=True)[:limit]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    items = ThreadsSource().fetch()
    print(f"знайдено постів: {len(items)}\n")
    for item in items:
        p = item.payload
        print(f"@{p['author']}: {p['text'][:100]!r}")
