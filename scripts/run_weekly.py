import logging
from datetime import datetime
from pathlib import Path

import db
import report
import telegram_bot
from sources.multiplex import MultiplexSource

LOG_PATH = Path(__file__).resolve().parent.parent / "logs" / "run_weekly.log"


def main():
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=LOG_PATH,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logger = logging.getLogger("run_weekly")

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

    text = report.build_multiplex_digest(items, seen_before_ids, "Промінь Луцьк — у прокаті")
    if text is None:
        return

    if telegram_bot.send_message(text):
        ids = [item.external_id for item in items]
        db.mark_sent(source.name, ids, datetime.now().isoformat())
        logger.info("%s: sent digest, marked %d as sent", source.name, len(ids))
    else:
        logger.error("%s: failed to send digest", source.name)


if __name__ == "__main__":
    main()
