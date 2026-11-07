import logging

import requests

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

logger = logging.getLogger(__name__)

MAX_MESSAGE_LENGTH = 4000  # Telegram's limit is 4096; leave margin


def _chunk(text: str, limit: int) -> list:
    lines = text.split("\n")
    chunks = []
    current = ""
    for line in lines:
        candidate = f"{current}\n{line}" if current else line
        if len(candidate) > limit:
            if current:
                chunks.append(current)
            current = line
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def _send_single(text: str) -> bool:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        response = requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": text}, timeout=15)
    except requests.RequestException as e:
        # не логувати str(e)/traceback — може містити url із токеном
        logger.error("telegram: request failed (%s)", type(e).__name__)
        return False

    if response.status_code != 200:
        logger.error("telegram: send_message failed (status=%d): %s", response.status_code, response.text)
        return False
    return True


def send_message(text: str) -> bool:
    for chunk in _chunk(text, MAX_MESSAGE_LENGTH):
        if not _send_single(chunk):
            return False
    return True
