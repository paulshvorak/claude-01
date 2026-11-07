from pathlib import Path

from playwright.sync_api import sync_playwright

PROFILE_DIR = Path(__file__).resolve().parent.parent / "data" / "threads_profile"


def main():
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(str(PROFILE_DIR), headless=False)
        page = context.new_page()
        page.goto("https://www.threads.com/")
        input("Залогинься в цьому вікні браузера, тоді натисни Enter тут, у терміналі...")
        context.close()
    print("Готово — сесія збережена в", PROFILE_DIR)


if __name__ == "__main__":
    main()
