import asyncio
import aiohttp
import ssl
import certifi
import json
from pathlib import Path

from bs4 import BeautifulSoup


# ==================================================
# CONFIGURATION
# ==================================================

ARXIV_API_URL = "https://export.arxiv.org/api/query"

PAPERS_TO_COLLECT = 1000

BATCH_SIZE = 100

REQUEST_TIMEOUT = 60

OUTPUT_FILE = Path("data/raw/arxiv_papers.json")


# ==================================================
# SSL
# ==================================================

def create_ssl_context():

    return ssl.create_default_context(
        cafile=certifi.where()
    )


# ==================================================
# FETCH ONE BATCH
# ==================================================

async def fetch_batch(
    session,
    start,
    max_results
):

    params = {
        "search_query": "cat:cs.AI",
        "start": start,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }

    try:

        print(
            f"Fetching papers "
            f"{start + 1} - "
            f"{start + max_results}..."
        )

        async with session.get(
            ARXIV_API_URL,
            params=params
        ) as response:

            response.raise_for_status()

            xml_data = await response.text()

            return xml_data

    except asyncio.TimeoutError:

        print(
            f"Timeout while fetching "
            f"batch starting at {start}"
        )

        return None

    except aiohttp.ClientError as error:

        print(
            f"Request failed for batch "
            f"{start}: {error}"
        )

        return None


# ==================================================
# PARSE PAPERS
# ==================================================

def parse_papers(xml_data):

    if not xml_data:

        return []

    soup = BeautifulSoup(
        xml_data,
        "xml"
    )

    papers = []

    for entry in soup.find_all("entry"):

        title_tag = entry.find("title")

        published_tag = entry.find(
            "published"
        )

        id_tag = entry.find("id")

        title = (
            title_tag.get_text(
                " ",
                strip=True
            )
            if title_tag
            else None
        )

        published_date = (
            published_tag.get_text(
                strip=True
            )
            if published_tag
            else None
        )

        paper_url = (
            id_tag.get_text(
                strip=True
            )
            if id_tag
            else None
        )

        authors = []

        for author in entry.find_all(
            "author"
        ):

            name_tag = author.find(
                "name"
            )

            if name_tag:

                authors.append(
                    name_tag.get_text(
                        strip=True
                    )
                )

        if not paper_url:

            continue

        paper = {

            "schemaVersion": "1.0",

            "recordType": "RESEARCH_PAPER",

            "content": {

                "title": title,

                "authors": authors,

                "paper_url": paper_url,

                "github_url": None,

                "github_stars": None,

                "published_date": published_date
            }
        }

        papers.append(paper)

    return papers


# ==================================================
# SAVE DATA
# ==================================================

def save_papers(papers):

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
            papers,
            file,
            indent=2,
            ensure_ascii=False
        )

    print(
        f"\nSaved {len(papers)} papers to:"
    )

    print(OUTPUT_FILE)


# ==================================================
# MAIN CRAWLER
# ==================================================

async def collect_papers():

    ssl_context = create_ssl_context()

    connector = aiohttp.TCPConnector(
        ssl=ssl_context
    )

    timeout = aiohttp.ClientTimeout(
        total=REQUEST_TIMEOUT
    )

    async with aiohttp.ClientSession(
        connector=connector,
        timeout=timeout
    ) as session:

        all_papers = []

        seen_urls = set()

        for start in range(
            0,
            PAPERS_TO_COLLECT,
            BATCH_SIZE
        ):

            remaining = (
                PAPERS_TO_COLLECT
                - start
            )

            batch_size = min(
                BATCH_SIZE,
                remaining
            )

            xml_data = await fetch_batch(
                session,
                start,
                batch_size
            )

            batch = parse_papers(
                xml_data
            )

            for paper in batch:

                url = paper["content"][
                    "paper_url"
                ]

                if url in seen_urls:

                    continue

                seen_urls.add(url)

                all_papers.append(
                    paper
                )

            print(
                f"Total unique papers: "
                f"{len(all_papers)}"
            )

            # Small pause between batches
            await asyncio.sleep(1)

            if len(all_papers) >= PAPERS_TO_COLLECT:

                break

        return all_papers[
            :PAPERS_TO_COLLECT
        ]


# ==================================================
# ENTRY POINT
# ==================================================

async def main():

    print("=" * 70)

    print(
        "AI ENGINEER DATA PIPELINE"
    )

    print(
        "Research Paper Collection"
    )

    print("=" * 70)

    papers = await collect_papers()

    print("\n" + "=" * 70)

    print(
        f"FINAL COUNT: {len(papers)}"
    )

    print("=" * 70)

    if papers:

        save_papers(papers)

        print(
            "\nFirst paper:"
        )

        print(
            json.dumps(
                papers[0],
                indent=2,
                ensure_ascii=False
            )
        )

    else:

        print(
            "No papers were collected."
        )


if __name__ == "__main__":

    asyncio.run(main())