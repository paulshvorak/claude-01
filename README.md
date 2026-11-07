# Social Context Digest

Особистий агент, що збирає сигнал із джерел, які я більше не гортаю вручну (Instagram, Threads), і кілька локальних/робочих джерел — і щодня/щотижня присилає стислий дайджест у Telegram. Другорядна мета — вчитись будувати агентів на Claude Code на живому прикладі.

Інструмент тільки для себе: без авторизації, без масштабування, без зайвої абстракції. Деталі задуму — `docs/brief.md`; чекліст тем Claude Code, які вивчаємо по ходу — `docs/claude-code-learning.md`.

## Архітектура

```
джерело → fetch() → SQLite (своя таблиця) → report.py (LLM, де треба судження) → Telegram → mark_sent()
```

Кожне джерело — модуль у `sources/` з однаковим контрактом (`name` + `fetch() -> list[Item]`), незалежний від інших: збій одного не валить решту. Судження (LLM) живе лише в `report.py`, і лише там, де дані самі не відфільтровані.

| Джерело | Що | Ритм | LLM? |
|---|---|---|---|
| `sources/football.py` | Новини «Ліверпуля» з football.ua | щодня | ні — просто список |
| `sources/instagram.py` | Останній пост з 12 куратованих акаунтів (Apify) | щодня | так — відбирає тільки варте уваги |
| `sources/threads.py` | Теми з алгоритмічної стрічки «Для вас» + топ-коментарі під ними (Playwright) | щодня | так, двома кроками + Sonnet на опис |
| `sources/multiplex.py` | У прокаті в Луцьку (Multiplex + Premier City), сортовано за IMDb/RT | щотижня | ні |
| `sources/ai_news.py` | GitHub-релізи Claude Code, Simon Willison, HN, DOU, блог Anthropic | збір щодня, дайджест щотижня | так — кластеризація + фільтр за ефектом |

Живу блок-схему з позначками «готово/заплановано» дивись в артефакті, посилання — в чаті з Claude.

## Запуск

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/playwright install chromium
cp .env.example .env   # і заповнити токени
```

Потрібні в `.env`: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `APIFY_TOKEN`, `OMDB_API_KEY`.

Для Threads — одноразовий ручний логін у Playwright-профіль:
```bash
.venv/bin/python scripts/threads_login.py
```

Щоденний і щотижневий прогін:
```bash
.venv/bin/python -m scripts.run_daily
.venv/bin/python -m scripts.run_weekly
```

Crontab поки не налаштований навмисно — проєкт ще в режимі «ручний запуск і спостереження», автоматизація прийде пізніше.

## Безпека

Хук (`.claude/settings.json` + `scripts/check_no_secrets.py`) блокує `git add`/`commit`, якщо в застейджених змінах опиняється `.env` чи значення токена бота.
