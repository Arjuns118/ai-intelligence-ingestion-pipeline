import asyncio

from playwright.async_api import async_playwright


async def fetch_with_browser(url):
    """
    Fetch a JavaScript-rendered webpage using Chromium.

    Returns:
        HTML string if successful.
        None if the page cannot be loaded.
    """

    try:

        async with async_playwright() as p:

            browser = await p.chromium.launch(
                headless=True
            )

            page = await browser.new_page(
                user_agent=(
                    "Mozilla/5.0 "
                    "(Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 "
                    "(KHTML, like Gecko) "
                    "Chrome/140 Safari/537.36"
                ),
                viewport={
                    "width": 1440,
                    "height": 900
                }
            )

            print(
                f"Opening with browser: {url}"
            )

            await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=60000
            )

            # Give JavaScript time to render
            await page.wait_for_timeout(5000)

            html = await page.content()

            await browser.close()

            return html

    except Exception as error:

        print(
            f"Browser fallback failed: {error}"
        )

        return None


async def main():

    url = (
        "https://www.linkedin.com/jobs/"
        "search/?keywords=artificial%20intelligence"
    )

    html = await fetch_with_browser(url)

    if html:

        print(
            f"Browser successfully received "
            f"{len(html)} characters"
        )

    else:

        print(
            "Browser could not fetch the page."
        )


if __name__ == "__main__":
    asyncio.run(main())