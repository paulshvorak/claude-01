import logging
from datetime import datetime
from pathlib import Path

import db
import report
import telegram_bot
from sources.football import FootballSource

SOURCES = [FootballSource()]
DIGEST_HEADERS = {"football_articles": "Ліверпуль — новини за добу"}

LOG_PATH = Path(__file__).resolve().parent.parent / "logs" / "run_daily.log"


def main():
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=LOG_PATH,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logger = logging.getLogger("run_daily")

    for source in SOURCES:
        try:
            db.ensure_table(source.name)
            items = source.fetch()
            db.insert_new(source.name, items)
            logger.info("%s: fetched %d items", source.name, len(items))
        except Exception:
            logger.exception("%s: source failed", source.name)

    for table, header in DIGEST_HEADERS.items():
        text = report.build_digest(table, header)
        if text is None:
            continue
        if telegram_bot.send_message(text):
            ids = [item["external_id"] for item in db.get_unsent(table)]
            db.mark_sent(table, ids, datetime.now().isoformat())
            logger.info("%s: sent digest, marked %d as sent", table, len(ids))
        else:
            logger.error("%s: failed to send digest", table)


if __name__ == "__main__":
    main()
