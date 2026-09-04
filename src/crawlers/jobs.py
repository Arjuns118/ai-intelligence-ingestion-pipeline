import asyncio
import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urljoin

import aiohttp
from bs4 import BeautifulSoup

try:
    from dateutil import parser as date_parser
except ImportError:
    date_parser = None

try:
    from .browser import fetch_with_browser
except ImportError:
    from browser import fetch_with_browser


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_FILE = PROJECT_ROOT / "data" / "raw" / "fresh_jobs.json"

FRESHNESS_HOURS = 24
MAX_PER_SOURCE = 100
CONCURRENCY = 8


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/140.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


# Five distinct job sources.
SOURCES = [
    {
        "name": "Indeed AI Jobs",
        "url": "https://www.indeed.com/jobs?q=artificial+intelligence&fromage=1",
    },
    {
        "name": "Wellfound AI Jobs",
        "url": "https://wellfound.com/jobs",
    },
    {
        "name": "Hugging Face Jobs",
        "url": "https://huggingface.co/jobs",
    },
    {
        "name": "AI Jobs",
        "url": "https://aijobs.ai/",
    },
    {
        "name": "LinkedIn AI Jobs",
        "url": (
            "https://www.linkedin.com/jobs/search/"
            "?keywords=artificial%20intelligence"
            "&f_TPR=r86400"
        ),
    },
]


def clean_text(value):
    if value is None:
        return None

    value = re.sub(
        r"\s+",
        " ",
        str(value)
    ).strip()

    return value or None


def normalize_url(url, base_url=None):
    if not url:
        return None

    url = url.strip()

    if url.startswith("//"):
        return "https:" + url

    if base_url:
        return urljoin(base_url, url)

    if url.startswith("/"):
        return "https://www.indeed.com" + url

    return url


def parse_date(value):
    """
    Parse absolute and relative job dates.
    Returns timezone-aware UTC datetime or None.
    """

    if not value:
        return None

    text = clean_text(value)

    if not text:
        return None

    now = datetime.now(timezone.utc)

    lower = text.lower()

    # Relative formats.
    if lower in {"just now", "now", "today"}:
        return now

    match = re.search(
        r"(\d+)\s*(minute|minutes|min|mins)\s*ago",
        lower
    )

    if match:
        return now - timedelta(
            minutes=int(match.group(1))
        )

    match = re.search(
        r"(\d+)\s*(hour|hours|hr|hrs)\s*ago",
        lower
    )

    if match:
        return now - timedelta(
            hours=int(match.group(1))
        )

    match = re.search(
        r"(\d+)\s*(day|days)\s*ago",
        lower
    )

    if match:
        return now - timedelta(
            days=int(match.group(1))
        )

    if date_parser:

        try:
            parsed = date_parser.parse(
                text
            )

            if parsed.tzinfo is None:
                parsed = parsed.replace(
                    tzinfo=timezone.utc
                )

            return parsed.astimezone(
                timezone.utc
            )

        except Exception:
            pass

    # Common ISO format fallback.
    try:

        parsed = datetime.fromisoformat(
            text.replace("Z", "+00:00")
        )

        if parsed.tzinfo is None:
            parsed = parsed.replace(
                tzinfo=timezone.utc
            )

        return parsed.astimezone(
            timezone.utc
        )

    except Exception:
        return None


def is_fresh(date_value):
    parsed = parse_date(date_value)

    if parsed is None:
        return False

    now = datetime.now(timezone.utc)

    # Reject future dates.
    if parsed > now:
        return False

    age = now - parsed

    return age <= timedelta(
        hours=FRESHNESS_HOURS
    )


def role_family(title):
    """
    Conservative role classification.
    """

    if not title:
        return None

    text = title.lower()

    if any(
        x in text
        for x in [
            "machine learning",
            "ml engineer",
            "ml scientist",
        ]
    ):
        return "MACHINE_LEARNING"

    if any(
        x in text
        for x in [
            "data scientist",
            "data science",
        ]
    ):
        return "DATA_SCIENCE"

    if any(
        x in text
        for x in [
            "research scientist",
            "research engineer",
            "researcher",
        ]
    ):
        return "RESEARCH"

    if any(
        x in text
        for x in [
            "ai engineer",
            "artificial intelligence engineer",
            "ai developer",
        ]
    ):
        return "AI_ENGINEERING"

    if any(
        x in text
        for x in [
            "software engineer",
            "software developer",
            "backend",
            "frontend",
            "full stack",
            "full-stack",
        ]
    ):
        return "SOFTWARE_ENGINEERING"

    if any(
        x in text
        for x in [
            "product manager",
            "product management",
        ]
    ):
        return "PRODUCT"

    if any(
        x in text
        for x in [
            "designer",
            "ux",
            "ui",
        ]
    ):
        return "DESIGN"

    if any(
        x in text
        for x in [
            "sales",
            "business development",
        ]
    ):
        return "SALES"

    return "OTHER"


def extract_jsonld_jobs(
    html,
    source_name,
    source_url
):
    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    records = []

    scripts = soup.find_all(
        "script",
        type="application/ld+json"
    )

    for script in scripts:

        raw = script.string

        if not raw:
            continue

        try:
            data = json.loads(raw)
        except Exception:
            continue

        objects = []

        if isinstance(data, list):
            objects = data

        elif isinstance(data, dict):

            if "@graph" in data:
                objects = data["@graph"]

            else:
                objects = [data]

        for item in objects:

            if not isinstance(item, dict):
                continue

            item_type = item.get("@type")

            if isinstance(
                item_type,
                list
            ):
                is_job = (
                    "JobPosting"
                    in item_type
                )
            else:
                is_job = (
                    item_type
                    == "JobPosting"
                )

            if not is_job:
                continue

            title = clean_text(
                item.get("title")
            )

            if not title:
                continue

            date_value = (
                item.get("datePosted")
                or item.get("dateCreated")
            )

            if not is_fresh(date_value):
                continue

            company = None

            hiring = item.get(
                "hiringOrganization"
            )

            if isinstance(hiring, dict):

                company = clean_text(
                    hiring.get("name")
                )

            location_text = None

            job_location = item.get(
                "jobLocation"
            )

            if isinstance(
                job_location,
                dict
            ):
                address = job_location.get(
                    "address"
                )

                if isinstance(
                    address,
                    dict
                ):

                    location_text = clean_text(
                        " ".join(
                            str(v)
                            for v in address.values()
                            if v
                        )
                    )

            elif isinstance(
                job_location,
                list
            ):

                parts = []

                for loc in job_location:

                    if not isinstance(
                        loc,
                        dict
                    ):
                        continue

                    address = loc.get(
                        "address"
                    )

                    if isinstance(
                        address,
                        dict
                    ):

                        parts.extend(
                            str(v)
                            for v in address.values()
                            if v
                        )

                location_text = clean_text(
                    " ".join(parts)
                )

            remote = (
                item.get(
                    "jobLocationType"
                )
                == "TELECOMMUTE"
            )

            description = clean_text(
                BeautifulSoup(
                    str(
                        item.get(
                            "description",
                            ""
                        )
                    ),
                    "html.parser"
                ).get_text(
                    " ",
                    strip=True
                )
            )

            job_url = (
                clean_text(
                    item.get("url")
                )
                or source_url
            )

            records.append(
                make_record(
                    source_name=source_name,
                    source_url=source_url,
                    company=company,
                    date_value=date_value,
                    is_remote=remote,
                    role_title=title,
                    job_url=job_url,
                    description=description,
                    location=location_text,
                )
            )

    return records


def extract_html_jobs(
    html,
    source_name,
    source_url
):
    """
    Conservative fallback for pages without JSON-LD.
    """

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    records = []

    # Common job-title patterns.
    selectors = [
        "a[href*='/jobs/']",
        "a[href*='/job/']",
        "a[href*='jobs/view']",
        "h2",
        "h3",
    ]

    seen = set()

    for selector in selectors:

        for element in soup.select(
            selector
        ):

            title = clean_text(
                element.get_text(
                    " ",
                    strip=True
                )
            )

            if not title:
                continue

            # Avoid navigation and irrelevant headings.
            if len(title) < 5:
                continue

            if len(title) > 180:
                continue

            lower = title.lower()

            if not any(
                keyword in lower
                for keyword in [
                    "engineer",
                    "developer",
                    "scientist",
                    "research",
                    "data",
                    "machine learning",
                    "artificial intelligence",
                    "ai ",
                    "product",
                ]
            ):
                continue

            parent = element.parent

            context = ""

            if parent:

                context = clean_text(
                    parent.get_text(
                        " ",
                        strip=True
                    )
                ) or ""

            date_match = re.search(
                r"(\d+\s*(?:minute|minutes|min|"
                r"hour|hours|hr|hrs|day|days)\s*ago|"
                r"today|just now)",
                context,
                re.IGNORECASE
            )

            if not date_match:
                continue

            date_value = date_match.group(1)

            if not is_fresh(date_value):
                continue

            href = element.get(
                "href"
            )

            job_url = normalize_url(
                href,
                source_url
            )

            if not job_url:
                job_url = source_url

            key = (
                title.lower(),
                job_url
            )

            if key in seen:
                continue

            seen.add(key)

            records.append(
                make_record(
                    source_name=source_name,
                    source_url=source_url,
                    company=None,
                    date_value=date_value,
                    is_remote=(
                        "remote"
                        in context.lower()
                    ),
                    role_title=title,
                    job_url=job_url,
                    description=context,
                    location=None,
                )
            )

            if len(records) >= MAX_PER_SOURCE:
                return records

    return records


def make_record(
    source_name,
    source_url,
    company,
    date_value,
    is_remote,
    role_title,
    job_url,
    description,
    location,
):

    return {
        "schemaVersion": "1.0",
        "recordType": "JOB",

        "source": {
            "name": source_name,
            "url": source_url,
        },

        "content": {
            "company": company,
            "date": date_value,
            "is_remote": bool(is_remote),
            "role_family": role_family(
                role_title
            ),
            "title": role_title,
            "job_url": job_url,
            "description": description,
            "location": location,
        },

        "collectedAt": datetime.now(
            timezone.utc
        ).isoformat(),
    }


async def fetch_http(
    session,
    source
):
    try:

        async with session.get(
            source["url"],
            headers=HEADERS,
            timeout=aiohttp.ClientTimeout(
                total=45
            ),
        ) as response:

            html = await response.text(
                errors="ignore"
            )

            print(
                f"{source['name']}: "
                f"HTTP {response.status}"
            )

            return html, response.status

    except Exception as error:

        print(
            f"{source['name']}: "
            f"HTTP error: {error}"
        )

        return None, None


async def process_source(
    session,
    source
):

    html, status = await fetch_http(
        session,
        source
    )

    # Browser fallback for blocked / JS pages.
    if html is None or status != 200:

        print(
            f"{source['name']}: "
            "using Playwright fallback..."
        )

        try:

            html = await fetch_with_browser(
                source["url"]
            )

        except Exception as error:

            print(
                f"{source['name']}: "
                f"browser failed: {error}"
            )

            return []

    if not html:
        return []

    records = extract_jsonld_jobs(
        html,
        source["name"],
        source["url"]
    )

    if not records:

        records = extract_html_jobs(
            html,
            source["name"],
            source["url"]
        )

    print(
        f"{source['name']}: "
        f"{len(records)} fresh jobs"
    )

    return records[:MAX_PER_SOURCE]


async def main_async():

    print("\n========================================")
    print("FRESH AI JOB CRAWLER")
    print("========================================\n")

    connector = aiohttp.TCPConnector(
        limit=CONCURRENCY,
        ssl=False
    )

    async with aiohttp.ClientSession(
        connector=connector
    ) as session:

        tasks = [
            process_source(
                session,
                source
            )
            for source in SOURCES
        ]

        results = await asyncio.gather(
            *tasks,
            return_exceptions=True
        )

    all_records = []

    for result in results:

        if isinstance(
            result,
            Exception
        ):

            print(
                f"Source failed: {result}"
            )

            continue

        all_records.extend(
            result
        )

    # Final strict freshness check.
    fresh_records = []

    for record in all_records:

        date_value = record[
            "content"
        ].get("date")

        if is_fresh(date_value):
            fresh_records.append(record)

    # Deduplicate.
    unique = {}

    for record in fresh_records:

        content = record[
            "content"
        ]

        key = (
            str(
                content.get(
                    "job_url"
                )
            ).lower().strip()
            + "|"
            + str(
                content.get(
                    "company"
                )
            ).lower().strip()
            + "|"
            + str(
                content.get(
                    "title"
                )
            ).lower().strip()
        )

        unique[key] = record

    records = list(
        unique.values()
    )

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
            records,
            file,
            indent=2,
            ensure_ascii=False
        )

    print("\n========================================")
    print(
        f"Saved {len(records)} fresh job records."
    )
    print(
        f"Output: {OUTPUT_FILE}"
    )
    print("========================================")


def main():
    asyncio.run(main_async())


if __name__ == "__main__":
    main()