import logging
import re
from datetime import datetime

import feedparser
from playwright.sync_api import sync_playwright

from sources.base import Item

logger = logging.getLogger(__name__)

AI_KEYWORDS = [
    "ai", "llm", "claude", "gpt", "openai", "anthropic", "gemini", "agent",
    "model", "prompt", "ші", "штучний інтелект", "нейромереж", "llama", "copilot",
]

# (source, url, needs_keyword_filter) — GitHub releases - це вже 100% Claude Code,
# фільтр не потрібен; інші три - загальні стрічки без AI-тегу.
FEEDS = [
    ("github_releases", "https://github.com/anthropics/claude-code/releases.atom", False),
    ("simon_willison", "https://simonwillison.net/atom/everything/", True),
    ("hn", "https://hnrss.org/frontpage?points=200", True),
    ("dou", "https://dou.ua/feed/", True),
]

ANTHROPIC_NEWS_URL = "https://www.anthropic.com/news"

CATEGORY_WORDS = {"Announcements", "Science", "Features", "Product", "Policy", "Company", "Research", "Societal Impacts"}
DATE_LINE_RE = re.compile(r"^[A-Z][a-z]{2,8}\.? \d{1,2},? \d{4}$")

ANTHROPIC_EXTRACT_JS = """
() => {
    function findCard(anchor) {
        let el = anchor;
        for (let i = 0; i < 15 && el.parentElement; i++) {
            el = el.parentElement;
            const text = el.innerText || '';
            const siblingCount = el.parentElement ? el.parentElement.children.length : 0;
            if (text.length >= 40 && siblingCount >= 2) {
                return el;
            }
        }
        return el;
    }
    const skip = new Set(['/news', '/search', '/', '/research', '/policy', '/company', '/news/announcements']);
    const seen = new Set();
    const results = [];
    for (const a of document.querySelectorAll('a[href]')) {
        const href = a.getAttribute('href');
        if (!href || !href.startsWith('/') || skip.has(href) || seen.has(href)) continue;
        seen.add(href);
        results.push({href, text: findCard(a).innerText});
    }
    return results;
}
"""


def _is_relevant(title: str, summary: str) -> bool:
    text = f"{title} {summary}".lower()
    return any(kw in text for kw in AI_KEYWORDS)


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text or "").strip()


def _fetch_feed(source: str, url: str, needs_filter: bool) -> list:
    try:
        parsed = feedparser.parse(url)
    except Exception:
        logger.exception("ai_news: feed fetch failed for %s", source)
        return []

    items = []
    for entry in parsed.entries:
        title = entry.get("title", "")
        summary = _strip_html(entry.get("summary", ""))[:400]
        if needs_filter and not _is_relevant(title, summary):
            continue
        link = entry.get("link", "")
        items.append({
            "source": source,
            "external_id": f"{source}:{entry.get('id') or link}",
            "title": title,
            "link": link,
            "summary": summary,
        })
    return items


def _fetch_anthropic_blog() -> list:
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(ANTHROPIC_NEWS_URL, timeout=30000)
            page.wait_for_timeout(2000)
            raw_cards = page.evaluate(ANTHROPIC_EXTRACT_JS)
            browser.close()
    except Exception:
        logger.exception("ai_news: anthropic blog fetch failed")
        return []

    items = []
    for raw in raw_cards:
        lines = [line.strip() for line in raw["text"].split("\n") if line.strip()]
        content_lines = [
            line for line in lines
            if line not in CATEGORY_WORDS and not DATE_LINE_RE.match(line)
        ]
        if not content_lines:
            continue
        title = content_lines[0]
        if len(title) < 10:
            continue
        summary = " ".join(content_lines[1:])[:400]
        items.append({
            "source": "anthropic_blog",
            "external_id": f"anthropic_blog:{raw['href']}",
            "title": title,
            "link": f"https://www.anthropic.com{raw['href']}",
            "summary": summary,
        })
    return items


class AINewsSource:
    name = "ai_news_items"

    def fetch(self) -> list[Item]:
        raw_items = []
        for source, url, needs_filter in FEEDS:
            raw_items.extend(_fetch_feed(source, url, needs_filter))
        raw_items.extend(_fetch_anthropic_blog())

        fetched_at = datetime.now().isoformat()
        return [
            Item(
                external_id=raw["external_id"],
                fetched_at=fetched_at,
                payload={
                    "source": raw["source"],
                    "title": raw["title"],
                    "link": raw["link"],
                    "summary": raw["summary"],
                },
            )
            for raw in raw_items
        ]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    items = AINewsSource().fetch()
    from collections import Counter
    counts = Counter(item.payload["source"] for item in items)
    print("по джерелах:", dict(counts), "| всього:", len(items))
    for item in items[:30]:
        print(f"[{item.payload['source']}] {item.payload['title'][:80]}")
