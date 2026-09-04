import json
import requests
from pathlib import Path
from datetime import datetime, timezone


PROJECT_ROOT = Path(__file__).resolve().parents[2]

OUTPUT_FILE = PROJECT_ROOT / "data" / "raw" / "startups.json"

# Public index built from Y Combinator's company directory.
# We use both AI-related tag collections to get well over 1000 candidates.
SOURCES = [
    "https://yc-oss.github.io/api/tags/ai.json",
    "https://yc-oss.github.io/api/tags/artificial-intelligence.json",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/140.0 Safari/537.36"
    )
}


def clean_text(value):
    if not value:
        return None

    value = str(value).strip()

    if not value:
        return None

    return value


def fetch_json(url):
    print(f"Fetching: {url}")

    response = requests.get(
        url,
        headers=HEADERS,
        timeout=60
    )

    response.raise_for_status()

    return response.json()


def convert_to_record(company):
    """
    Convert YC company data into the schema required by the assignment.
    """

    name = clean_text(company.get("name"))

    if not name:
        return None

    yc_url = clean_text(company.get("url"))

    # Prefer the official YC company page as the source URL.
    if not yc_url:
        slug = clean_text(company.get("slug"))

        if slug:
            yc_url = f"https://www.ycombinator.com/companies/{slug}"

    description = (
        clean_text(company.get("long_description"))
        or clean_text(company.get("one_liner"))
    )

    employee_count = company.get("team_size")

    if not isinstance(employee_count, int):
        employee_count = None

    return {
        "schemaVersion": "1.0",
        "recordType": "STARTUP",

        "source": {
            "name": "Y Combinator",
            "url": yc_url
        },

        "content": {
            "entityName": name,
            "description": description,

            "data": {
                "employeeCount": employee_count
            }
        },

        "collectedAt": datetime.now(timezone.utc).isoformat()
    }


def main():

    print("\n========================================")
    print("YC AI STARTUP CRAWLER")
    print("========================================\n")

    all_companies = {}

    for source_url in SOURCES:

        try:
            companies = fetch_json(source_url)

            print(
                f"Received {len(companies)} companies "
                f"from this source."
            )

            for company in companies:

                name = clean_text(company.get("name"))

                if not name:
                    continue

                # Deduplicate using YC company ID when available.
                company_id = company.get("id")

                if company_id:
                    key = f"id:{company_id}"
                else:
                    key = f"name:{name.lower()}"

                all_companies[key] = company

        except Exception as error:

            print(
                f"ERROR fetching {source_url}: {error}"
            )

    print(
        f"\nUnique companies collected: "
        f"{len(all_companies)}"
    )

    records = []

    for company in all_companies.values():

        record = convert_to_record(company)

        if record:
            records.append(record)

    # Sort alphabetically for reproducibility.
    records.sort(
        key=lambda x: (
            x["content"]["entityName"] or ""
        ).lower()
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

    print(
        f"\nSaved {len(records)} startup records."
    )

    print(
        f"Output: {OUTPUT_FILE}"
    )

    print("\nFirst 5 companies:")

    for record in records[:5]:

        print(
            "-",
            record["content"]["entityName"]
        )

    print("\nCrawler finished successfully.")


if __name__ == "__main__":
    
    main()