import asyncio
import aiohttp
import feedparser
import json
import ssl
import certifi

from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta
from pathlib import Path


# ============================================================
# CONFIGURATION
# ============================================================

OUTPUT_FILE = Path(
    "data/raw/fresh_news.json"
)

REQUEST_TIMEOUT = 30

FRESHNESS_HOURS = 24


# ============================================================
# NEWS SOURCES
# ============================================================

NEWS_SOURCES = {

    "TechCrunch": (
        "https://techcrunch.com/feed/"
    ),

    "VentureBeat": (
        "https://venturebeat.com/feed/"
    ),

    "Google AI": (
        "https://blog.google/technology/ai/rss/"
    ),

    "OpenAI": (
        "https://openai.com/news/rss.xml"
    ),

    "Google Research": (
        "https://research.google/blog/rss/"
    )
}


# ============================================================
# SSL
# ============================================================

def create_ssl_context():

    return ssl.create_default_context(
        cafile=certifi.where()
    )


# ============================================================
# DATE PARSER
# ============================================================

def parse_feed_date(entry):

    # feedparser gives us parsed time information
    # when available.

    if hasattr(
        entry,
        "published_parsed"
    ) and entry.published_parsed:

        return datetime(
            *entry.published_parsed[:6],
            tzinfo=timezone.utc
        )

    if hasattr(
        entry,
        "updated_parsed"
    ) and entry.updated_parsed:

        return datetime(
            *entry.updated_parsed[:6],
            tzinfo=timezone.utc
        )

    return None


# ============================================================
# FULL TEXT EXTRACTION
# ============================================================

def extract_full_text(html):

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    # Remove unnecessary elements

    for element in soup([
        "script",
        "style",
        "nav",
        "header",
        "footer",
        "aside",
        "form"
    ]):

        element.decompose()

    # Try article first

    article = soup.find(
        "article"
    )

    if article:

        text = article.get_text(
            " ",
            strip=True
        )

    else:

        text = soup.get_text(
            " ",
            strip=True
        )

    return text


# ============================================================
# FETCH ARTICLE
# ============================================================

async def fetch_article(
    session,
    url
):

    try:

        async with session.get(
            url,
            timeout=aiohttp.ClientTimeout(
                total=REQUEST_TIMEOUT
            )
        ) as response:

            if response.status != 200:

                print(
                    f"Article returned "
                    f"HTTP {response.status}: "
                    f"{url}"
                )

                return None

            html = await response.text()

            return extract_full_text(
                html
            )

    except Exception as error:

        print(
            f"Article fetch failed: "
            f"{error}"
        )

        return None


# ============================================================
# FETCH RSS FEED
# ============================================================

async def fetch_feed(
    session,
    source_name,
    feed_url
):

    print(
        f"\nFetching: {source_name}"
    )

    try:

        async with session.get(
            feed_url,
            timeout=aiohttp.ClientTimeout(
                total=REQUEST_TIMEOUT
            )
        ) as response:

            response.raise_for_status()

            content = await response.text()

    except Exception as error:

        print(
            f"Feed failed: {error}"
        )

        return []

    feed = feedparser.parse(
        content
    )

    articles = []

    now = datetime.now(
        timezone.utc
    )

    for entry in feed.entries:

        published_date = parse_feed_date(
            entry
        )

        if not published_date:

            continue

        age = now - published_date

        # ----------------------------------------------------
        # 24-HOUR FILTER
        # ----------------------------------------------------

        if age < timedelta(
            hours=0
        ):

            # Future date — reject
            continue

        if age > timedelta(
            hours=FRESHNESS_HOURS
        ):

            # Older than 24 hours
            continue

        title = entry.get(
            "title",
            ""
        ).strip()

        url = entry.get(
            "link",
            ""
        ).strip()

        if not title or not url:

            continue

        articles.append({

            "source": source_name,

            "title": title,

            "url": url,

            "published_date":
                published_date.isoformat(),

            "content": None
        })

    print(
        f"Fresh articles found: "
        f"{len(articles)}"
    )

    return articles


# ============================================================
# MAIN NEWS CRAWLER
# ============================================================

async def collect_news():

    ssl_context = create_ssl_context()

    connector = aiohttp.TCPConnector(
        limit=10,
        ssl=ssl_context
    )

    timeout = aiohttp.ClientTimeout(
        total=REQUEST_TIMEOUT
    )

    all_articles = []

    async with aiohttp.ClientSession(
        connector=connector,
        timeout=timeout,
        headers={
            "User-Agent":
                "AI-Intelligence-Pipeline/1.0"
        }
    ) as session:

        # ----------------------------------------------------
        # FETCH ALL FEEDS CONCURRENTLY
        # ----------------------------------------------------

        tasks = []

        for source_name, feed_url in (
            NEWS_SOURCES.items()
        ):

            tasks.append(
                fetch_feed(
                    session,
                    source_name,
                    feed_url
                )
            )

        results = await asyncio.gather(
            *tasks
        )

        for result in results:

            all_articles.extend(
                result
            )

        print(
            f"\nTotal fresh articles: "
            f"{len(all_articles)}"
        )

        # ----------------------------------------------------
        # FETCH FULL ARTICLE TEXT
        # ----------------------------------------------------

        print(
            "\nFetching full article text..."
        )

        article_tasks = []

        for article in all_articles:

            article_tasks.append(
                fetch_article(
                    session,
                    article["url"]
                )
            )

        contents = await asyncio.gather(
            *article_tasks
        )

        for article, content in zip(
            all_articles,
            contents
        ):

            article[
                "content"
            ] = content

    return all_articles


# ============================================================
# SAVE
# ============================================================

def save_news(articles):

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            articles,
            file,
            indent=2,
            ensure_ascii=False
        )

    print(
        f"\nSaved {len(articles)} "
        f"fresh articles to:"
    )

    print(
        OUTPUT_FILE
    )


# ============================================================
# ENTRY POINT
# ============================================================

async def main():

    print("=" * 70)

    print(
        "AI ENGINEER DATA PIPELINE"
    )

    print(
        "AI News Crawler"
    )

    print("=" * 70)

    articles = await collect_news()

    if articles:

        save_news(
            articles
        )

        print(
            "\nExample article:"
        )

        print(
            json.dumps(
                articles[0],
                indent=2,
                ensure_ascii=False
            )
        )

    else:

        print(
            "\nNo fresh articles found."
        )


if __name__ == "__main__":

    asyncio.run(
        main()
    )