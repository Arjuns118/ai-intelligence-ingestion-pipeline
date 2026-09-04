import json
import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

FILES = {
    "STARTUP": PROJECT_ROOT / "data/raw/startups.json",
    "PRODUCT": PROJECT_ROOT / "data/raw/products.json",
    "RESEARCH_PAPER": PROJECT_ROOT / "data/processed/research_papers.json",
    "NEWS": PROJECT_ROOT / "data/processed/news.json",
    "JOB": PROJECT_ROOT / "data/raw/fresh_jobs.json",
}


def load_json(path):

    with open(
        path,
        "r",
        encoding="utf-8"
    ) as file:

        return json.load(file)


def save_json(path, data):

    with open(
        path,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            data,
            file,
            indent=2,
            ensure_ascii=False
        )


def normalize(value):

    if value is None:
        return ""

    value = str(value).lower().strip()

    # Remove punctuation and extra spaces.
    value = re.sub(
        r"[^a-z0-9]+",
        " ",
        value
    )

    value = re.sub(
        r"\s+",
        " ",
        value
    )

    return value.strip()


def startup_key(record):

    content = record.get(
        "content",
        {}
    )

    return normalize(
        content.get(
            "entityName"
        )
    )


def product_key(record):

    content = record.get(
        "content",
        {}
    )

    # Product name + source URL.
    return (
        normalize(
            content.get(
                "entityName"
            )
        )
        + "|"
        + normalize(
            record.get(
                "source",
                {}
            ).get(
                "url"
            )
        )
    )


def paper_key(record):

    content = record.get(
        "content",
        {}
    )

    paper_url = normalize(
        content.get(
            "paper_url"
        )
    )

    if paper_url:
        return paper_url

    return normalize(
        content.get(
            "title"
        )
    )


def news_key(record):

    content = record.get(
        "content",
        {}
    )

    title = normalize(
        content.get(
            "title"
        )
    )

    source = normalize(
        record.get(
            "source",
            {}
        ).get(
            "url"
        )
    )

    return (
        title
        + "|"
        + source
    )


def job_key(record):

    content = record.get(
        "content",
        {}
    )

    title = normalize(
        content.get(
            "title"
        )
    )

    company = normalize(
        content.get(
            "company"
        )
    )

    date = normalize(
        content.get(
            "date"
        )
    )

    location = normalize(
        content.get(
            "location"
        )
    )

    # IMPORTANT:
    # Do NOT use job_url alone because LinkedIn
    # can give the same search-page URL for
    # multiple different jobs.
    return (
        title
        + "|"
        + company
        + "|"
        + date
        + "|"
        + location
    )


def deduplicate(
    records,
    record_type
):

    if record_type == "STARTUP":
        key_function = startup_key

    elif record_type == "PRODUCT":
        key_function = product_key

    elif record_type == "RESEARCH_PAPER":
        key_function = paper_key

    elif record_type == "NEWS":
        key_function = news_key

    elif record_type == "JOB":
        key_function = job_key

    else:
        return records

    unique = {}
    duplicate_count = 0

    for record in records:

        key = key_function(
            record
        )

        # Don't remove records when
        # we cannot construct a meaningful key.
        if not key or key == "|||":
            unique[
                f"unknown-{len(unique)}"
            ] = record
            continue

        if key in unique:

            duplicate_count += 1

            # Keep the first legitimate record.
            continue

        unique[key] = record

    return (
        list(unique.values()),
        duplicate_count
    )


def main():

    print(
        "\n========================================"
    )

    print(
        "DATA DEDUPLICATION"
    )

    print(
        "========================================\n"
    )

    total_before = 0
    total_after = 0

    for record_type, path in FILES.items():

        print(
            f"Checking {record_type}..."
        )

        if not path.exists():

            print(
                f"❌ Missing: {path}"
            )

            continue

        records = load_json(
            path
        )

        before = len(
            records
        )

        total_before += before

        result = deduplicate(
            records,
            record_type
        )

        cleaned_records, removed = result

        after = len(
            cleaned_records
        )

        total_after += after

        # Only rewrite the file if something
        # was actually removed.
        if removed > 0:

            save_json(
                path,
                cleaned_records
            )

        print(
            f"  Before: {before}"
        )

        print(
            f"  Removed: {removed}"
        )

        print(
            f"  After: {after}"
        )

        print()

    print(
        "========================================"
    )

    print(
        f"Total before: {total_before}"
    )

    print(
        f"Total after:  {total_after}"
    )

    print(
        f"Removed:      "
        f"{total_before - total_after}"
    )

    print(
        "========================================"
    )

    print(
        "\n✅ Deduplication completed."
    )


if __name__ == "__main__":
    main()