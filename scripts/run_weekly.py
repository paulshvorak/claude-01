import logging
from datetime import datetime
from pathlib import Path

import db
import report
import telegram_bot
from sources.ai_news import AINewsSource
from sources.multiplex import MultiplexSource

LOG_PATH = Path(__file__).resolve().parent.parent / "logs" / "run_weekly.log"


def _run_multiplex(logger):
    source = MultiplexSource()
    db.ensure_table(source.name)
    seen_before_ids = {row["external_id"] for row in db.get_all(source.name)}

    try:
        items = source.fetch()
    except Exception:
        logger.exception("%s: source failed", source.name)
        items = []

    db.insert_new(source.name, items)
    logger.info("%s: fetched %d items", source.name, len(items))

    text = report.build_multiplex_digest(items, seen_before_ids, "Кінопрокат на наступний тиждень")
    if text is None:
        return

    if telegram_bot.send_message(text):
        ids = [item.external_id for item in items]
        db.mark_sent(source.name, ids, datetime.now().isoformat())
        logger.info("%s: sent digest, marked %d as sent", source.name, len(ids))
    else:
        logger.error("%s: failed to send digest", source.name)


def _run_ai_news(logger):
    # сам збір — щодня, у run_daily.py (накопичення за тиждень, бо HN/DOU — це
    # знімок "зараз", а не історія); тут лише дайджест із уже накопиченого
    table = AINewsSource.name
    db.ensure_table(table)

    text = report.build_ai_news_digest(table, "AI-дайджест тижня")
    if text is None:
        return

    if telegram_bot.send_message(text):
        ids = [item["external_id"] for item in db.get_unsent(table)]
        db.mark_sent(table, ids, datetime.now().isoformat())
        logger.info("%s: sent digest, marked %d as sent", table, len(ids))
    else:
        logger.error("%s: failed to send digest", table)


def main():
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=LOG_PATH,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logger = logging.getLogger("run_weekly")

    _run_multiplex(logger)
    _run_ai_news(logger)


if __name__ == "__main__":
    main()
