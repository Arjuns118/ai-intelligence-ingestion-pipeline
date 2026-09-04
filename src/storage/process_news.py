import json
import sys
import time
from pathlib import Path
from datetime import datetime, timezone


# ============================================================
# PROJECT PATH
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

sys.path.append(str(PROJECT_ROOT / "src"))

from llm.extractor import extract_with_fallback


# ============================================================
# FILE PATHS
# ============================================================

INPUT_FILE = PROJECT_ROOT / "data" / "raw" / "fresh_news.json"

OUTPUT_FILE = PROJECT_ROOT / "data" / "processed" / "news.json"


# ============================================================
# SETTINGS
# ============================================================

# Wait between articles to reduce API rate-limit pressure.
DELAY_BETWEEN_ARTICLES = 3


# ============================================================
# EMPTY LLM RESULT
# ============================================================

def empty_extraction():

    return {
        "entityName": None,
        "description": None,
        "company": None,
        "url": None,
        "category": None,
        "pricingModel": None,
        "employeeCount": None,
        "publishedDate": None,
        "isRemote": None,
        "roleFamily": None
    }


# ============================================================
# PROCESS NEWS
# ============================================================

def process_news():

    print("Loading fresh news...")

    # --------------------------------------------------------
    # Check input file
    # --------------------------------------------------------

    if not INPUT_FILE.exists():

        print(
            f"ERROR: Input file not found:\n{INPUT_FILE}"
        )

        return

    # --------------------------------------------------------
    # Load JSON
    # --------------------------------------------------------

    with open(
        INPUT_FILE,
        "r",
        encoding="utf-8"
    ) as file:

        news_items = json.load(file)

    print(
        f"Found {len(news_items)} fresh news articles."
    )

    processed = []

    total = len(news_items)

    # ========================================================
    # PROCESS EACH ARTICLE
    # ========================================================

    for index, item in enumerate(
        news_items,
        start=1
    ):

        print("\n" + "=" * 60)

        print(
            f"Processing article "
            f"{index}/{total}"
        )

        print("=" * 60)

        # ----------------------------------------------------
        # Safely read fields
        # ----------------------------------------------------

        source = item.get(
            "source"
        )

        title = item.get(
            "title"
        )

        url = item.get(
            "url"
        )

        published_date = item.get(
            "published_date"
        )

        # IMPORTANT:
        # content may be None.
        # "or ''" converts None into an empty string.
        raw_content = item.get(
            "content"
        ) or ""

        print(
            f"Source: {source}"
        )

        print(
            f"Title: {title}"
        )

        print(
            f"URL: {url}"
        )

        print(
            f"Text length: "
            f"{len(raw_content)} characters"
        )

        # ====================================================
        # LLM EXTRACTION
        # ====================================================

        if raw_content.strip():

            try:

                extracted = extract_with_fallback(
                    raw_content
                )

            except Exception as error:

                print(
                    f"LLM extraction failed: {error}"
                )

                print(
                    "Continuing with empty "
                    "extraction result."
                )

                extracted = empty_extraction()

        else:

            print(
                "Warning: article has no content."
            )

            print(
                "Skipping LLM extraction."
            )

            extracted = empty_extraction()

        # Make sure extracted is a dictionary
        if not isinstance(
            extracted,
            dict
        ):

            extracted = empty_extraction()

        # ====================================================
        # CANONICAL RECORD
        # ====================================================

        canonical_record = {

            "schemaVersion": "1.0",

            "recordType": "NEWS",

            "source": {

                "name": source,

                "url": url
            },

            "content": {

                "title": title,

                "entityName":
                    extracted.get(
                        "entityName"
                    ),

                "description":
                    extracted.get(
                        "description"
                    ),

                "company":
                    extracted.get(
                        "company"
                    ),

                # Keep original article URL
                # if LLM did not return another URL.
                "url":
                    extracted.get(
                        "url"
                    ) or url,

                "category":
                    extracted.get(
                        "category"
                    ),

                "pricingModel":
                    extracted.get(
                        "pricingModel"
                    ),

                "employeeCount":
                    extracted.get(
                        "employeeCount"
                    ),

                "publishedDate":
                    extracted.get(
                        "publishedDate"
                    ) or published_date,

                "isRemote":
                    extracted.get(
                        "isRemote"
                    ),

                "roleFamily":
                    extracted.get(
                        "roleFamily"
                    )
            },

            "collectedAt":
                datetime.now(
                    timezone.utc
                ).isoformat()
        }

        # ====================================================
        # ADD RECORD
        # ====================================================

        processed.append(
            canonical_record
        )

        # ====================================================
        # SAVE AFTER EVERY ARTICLE
        # ====================================================

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
                processed,
                file,
                indent=2,
                ensure_ascii=False
            )

        print(
            f"Saved {len(processed)} records."
        )

        # ====================================================
        # DELAY BETWEEN REQUESTS
        # ====================================================

        if index < total:

            print(
                f"Waiting "
                f"{DELAY_BETWEEN_ARTICLES}s "
                f"before next article..."
            )

            time.sleep(
                DELAY_BETWEEN_ARTICLES
            )

    # ========================================================
    # COMPLETE
    # ========================================================

    print("\n" + "=" * 60)

    print(
        "NEWS PROCESSING COMPLETE"
    )

    print("=" * 60)

    print(
        f"Processed: {len(processed)}"
    )

    print(
        f"Saved to:\n{OUTPUT_FILE}"
    )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    process_news()