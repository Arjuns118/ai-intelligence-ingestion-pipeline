import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


FILES = {
    "STARTUP": PROJECT_ROOT / "data/raw/startups.json",
    "PRODUCT": PROJECT_ROOT / "data/raw/products.json",
    "RESEARCH_PAPER": PROJECT_ROOT / "data/processed/research_papers.json",
    "NEWS": PROJECT_ROOT / "data/processed/news.json",
    "JOB": PROJECT_ROOT / "data/raw/fresh_jobs.json",
}


# These fields must contain a real value.
# Other fields are allowed to be null when
# the original source does not provide them.
REQUIRED_NON_NULL = {

    "STARTUP": [
        ("schemaVersion",),
        ("recordType",),
        ("source", "name"),
        ("source", "url"),
        ("content", "entityName"),
        ("collectedAt",),
    ],

    "PRODUCT": [
        ("schemaVersion",),
        ("recordType",),
        ("source", "name"),
        ("source", "url"),
        ("content", "entityName"),
        ("collectedAt",),
    ],

    "RESEARCH_PAPER": [
        ("schemaVersion",),
        ("recordType",),
        ("content", "title"),
        ("content", "authors"),
        ("content", "paper_url"),
        ("content", "published_date"),
    ],

    "NEWS": [
        ("schemaVersion",),
        ("recordType",),
        ("source", "name"),
        ("source", "url"),
        ("content", "title"),
        ("collectedAt",),
    ],

    "JOB": [
        ("schemaVersion",),
        ("recordType",),
        ("source", "name"),
        ("source", "url"),
        ("content", "date"),
        ("content", "role_family"),
    ],
}


VALID_PRICING = {
    "FREE",
    "FREEMIUM",
    "PAID",
    "ENTERPRISE",
}


def get_nested(record, path):

    value = record

    for key in path:

        if not isinstance(value, dict):
            return None

        value = value.get(key)

    return value


def load_json(path):

    if not path.exists():

        print(f"❌ FILE NOT FOUND: {path}")

        return None

    try:

        with open(
            path,
            "r",
            encoding="utf-8"
        ) as file:

            return json.load(file)

    except Exception as error:

        print(f"❌ INVALID JSON: {path}")
        print(error)

        return None


def validate_record(
    record,
    record_type,
    index
):

    errors = []

    # -----------------------------------------
    # Record must be a dictionary
    # -----------------------------------------

    if not isinstance(record, dict):

        return [
            f"Record {index}: not an object"
        ]

    # -----------------------------------------
    # Required fields
    # -----------------------------------------

    for path in REQUIRED_NON_NULL[record_type]:

        value = get_nested(
            record,
            path
        )

        if value is None:

            errors.append(
                f"Record {index}: missing "
                f"{'.'.join(path)}"
            )

        elif isinstance(
            value,
            str
        ) and not value.strip():

            errors.append(
                f"Record {index}: empty "
                f"{'.'.join(path)}"
            )

    # -----------------------------------------
    # Correct record type
    # -----------------------------------------

    if record.get(
        "recordType"
    ) != record_type:

        errors.append(
            f"Record {index}: wrong recordType"
        )

    # -----------------------------------------
    # Source URL validation
    # -----------------------------------------

    source_url = get_nested(
        record,
        ("source", "url")
    )

    if source_url is not None:

        if not isinstance(
            source_url,
            str
        ):

            errors.append(
                f"Record {index}: "
                "source.url must be a string"
            )

        elif not source_url.startswith(
            (
                "http://",
                "https://"
            )
        ):

            errors.append(
                f"Record {index}: "
                "invalid source URL"
            )

    # -----------------------------------------
    # Product pricing validation
    # -----------------------------------------

    if record_type == "PRODUCT":

        pricing = get_nested(
            record,
            ("content", "pricingModel")
        )

        # None is valid because the source
        # may not expose pricing information.
        if (
            pricing is not None
            and pricing not in VALID_PRICING
        ):

            errors.append(
                f"Record {index}: "
                f"invalid pricingModel: {pricing}"
            )

    # -----------------------------------------
    # Research paper validation
    # -----------------------------------------

    if record_type == "RESEARCH_PAPER":

        authors = get_nested(
            record,
            ("content", "authors")
        )

        if not isinstance(
            authors,
            list
        ):

            errors.append(
                f"Record {index}: "
                "authors must be a list"
            )

        github_stars = get_nested(
            record,
            ("content", "github_stars")
        )

        # github_stars can legitimately be null
        # when no GitHub repository was found.
        if github_stars is not None:

            if not isinstance(
                github_stars,
                int
            ):

                errors.append(
                    f"Record {index}: "
                    "github_stars must be an integer "
                    "or null"
                )

            elif github_stars < 0:

                errors.append(
                    f"Record {index}: "
                    "github_stars cannot be negative"
                )

    # -----------------------------------------
    # Job validation
    # -----------------------------------------

    if record_type == "JOB":

        is_remote = get_nested(
            record,
            ("content", "is_remote")
        )

        if is_remote is not None and not isinstance(
            is_remote,
            bool
        ):

            errors.append(
                f"Record {index}: "
                "is_remote must be boolean"
            )

        role_family = get_nested(
            record,
            ("content", "role_family")
        )

        if role_family is not None:

            if not isinstance(
                role_family,
                str
            ):

                errors.append(
                    f"Record {index}: "
                    "role_family must be string"
                )

    return errors


def check_duplicates(
    records,
    record_type
):

    seen = set()
    duplicates = []

    for index, record in enumerate(
        records,
        start=1
    ):

        content = record.get(
            "content",
            {}
        )

        # -----------------------------------------
        # Research papers
        # -----------------------------------------

        if record_type == "RESEARCH_PAPER":

            key = content.get(
                "paper_url"
            )

        # -----------------------------------------
        # Jobs
        # -----------------------------------------

        elif record_type == "JOB":

            key = content.get(
                "job_url"
            )

            # If job_url is missing, use a
            # combination of job information.
            if not key:

                key = "|".join([
                    str(
                        content.get(
                            "company"
                        ) or ""
                    ),
                    str(
                        content.get(
                            "title"
                        ) or ""
                    ),
                    str(
                        content.get(
                            "date"
                        ) or ""
                    ),
                ])

        # -----------------------------------------
        # Everything else
        # -----------------------------------------

        else:

            key = (
                content.get(
                    "entityName"
                )
                or content.get(
                    "title"
                )
            )

        if not key:
            continue

        key = str(
            key
        ).lower().strip()

        if key in seen:

            duplicates.append(
                (
                    index,
                    key
                )
            )

        seen.add(key)

    return duplicates


def main():

    print("\n========================================")
    print("AI PIPELINE DATA VALIDATION")
    print("========================================\n")

    total_records = 0
    total_errors = 0

    summary = []

    # =========================================
    # CHECK EACH DATASET
    # =========================================

    for record_type, path in FILES.items():

        print(
            f"\nChecking {record_type}..."
        )

        records = load_json(
            path
        )

        if records is None:
            continue

        # -------------------------------------
        # Must be a list
        # -------------------------------------

        if not isinstance(
            records,
            list
        ):

            print(
                "❌ File must contain "
                "a JSON array."
            )

            total_errors += 1

            continue

        count = len(
            records
        )

        total_records += count

        errors = []

        # -------------------------------------
        # Validate records
        # -------------------------------------

        for index, record in enumerate(
            records,
            start=1
        ):

            record_errors = validate_record(
                record,
                record_type,
                index
            )

            errors.extend(
                record_errors
            )

        # -------------------------------------
        # Duplicate check
        # -------------------------------------

        duplicates = check_duplicates(
            records,
            record_type
        )

        # -------------------------------------
        # Print dataset results
        # -------------------------------------

        print(
            f"Records: {count}"
        )

        print(
            f"Schema errors: {len(errors)}"
        )

        print(
            f"Duplicates: {len(duplicates)}"
        )

        # -------------------------------------
        # Show errors
        # -------------------------------------

        if errors:

            print(
                "\nFirst 10 errors:"
            )

            for error in errors[:10]:

                print(
                    "  ❌",
                    error
                )

        # -------------------------------------
        # Show duplicates
        # -------------------------------------

        if duplicates:

            print(
                "\nFirst 5 duplicates:"
            )

            for index, key in duplicates[:5]:

                print(
                    f"  ⚠️ Record {index}: {key}"
                )

        total_errors += len(
            errors
        )

        summary.append(
            (
                record_type,
                count,
                len(errors),
                len(duplicates)
            )
        )

    # =========================================
    # FINAL SUMMARY
    # =========================================

    print(
        "\n========================================"
    )

    print(
        "FINAL VALIDATION SUMMARY"
    )

    print(
        "========================================"
    )

    print(
        f"Total records checked: "
        f"{total_records}"
    )

    print(
        f"Total schema errors: "
        f"{total_errors}"
    )

    print(
        "\nDataset summary:"
    )

    for (
        record_type,
        count,
        errors,
        duplicates
    ) in summary:

        if errors == 0:
            status = "✅"
        else:
            status = "❌"

        print(
            f"{status} "
            f"{record_type}: "
            f"{count} records | "
            f"{errors} errors | "
            f"{duplicates} duplicates"
        )

    print(
        "\n========================================"
    )

    if total_errors == 0:

        print(
            "✅ VALIDATION PASSED"
        )

    else:

        print(
            "⚠️ VALIDATION NEEDS ATTENTION"
        )

    print(
        "========================================\n"
    )


if __name__ == "__main__":
    main()