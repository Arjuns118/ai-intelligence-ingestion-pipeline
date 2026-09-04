import json
import re
from pathlib import Path

import pandas as pd


# ============================================================
# PROJECT PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
EXPORT_DIR = PROJECT_ROOT / "data" / "exports"

EXPORT_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# INPUT FILES
# ============================================================

FILES = {
    "Startups": RAW_DIR / "startups.json",
    "Products": RAW_DIR / "products.json",
    "Research Papers": PROCESSED_DIR / "research_papers.json",
    "Jobs": RAW_DIR / "fresh_jobs.json",
    "News": PROCESSED_DIR / "news.json",
    "Entity Mapping Log": PROCESSED_DIR / "entity_mapping.json",
}


# ============================================================
# EXCEL CHARACTER CLEANER
# ============================================================

def clean_excel_value(value):
    """
    Remove characters that Excel/openpyxl cannot store.

    Also safely converts lists and dictionaries to strings.
    """

    if value is None:
        return None

    # Lists
    if isinstance(value, list):

        cleaned_items = []

        for item in value:

            cleaned_items.append(
                clean_excel_value(item)
            )

        return ", ".join(
            str(item)
            for item in cleaned_items
            if item is not None
        )

    # Dictionaries
    if isinstance(value, dict):

        return json.dumps(
            value,
            ensure_ascii=False
        )

    # Convert everything else to string
    value = str(value)

    # Remove Excel-illegal control characters.
    # Allowed:
    # tab       \x09
    # newline   \x0A
    # carriage  \x0D
    #
    # Remove everything else from U+0000-U+001F.

    value = re.sub(
        r"[\x00-\x08\x0B\x0C\x0E-\x1F]",
        "",
        value
    )

    return value


# ============================================================
# LOAD JSON
# ============================================================

def load_json(path):

    if not path.exists():

        print(
            f"❌ Missing file: {path}"
        )

        return []

    try:

        with open(
            path,
            "r",
            encoding="utf-8"
        ) as file:

            data = json.load(file)

    except Exception as error:

        print(
            f"❌ Could not read {path}"
        )

        print(error)

        return []

    if not isinstance(data, list):

        print(
            f"❌ Expected a JSON list: {path}"
        )

        return []

    return data


# ============================================================
# FLATTEN JSON
# ============================================================

def flatten_record(record):

    result = {}

    for key, value in record.items():

        # Nested dictionary
        if isinstance(value, dict):

            for nested_key, nested_value in value.items():

                # Second-level dictionary
                if isinstance(
                    nested_value,
                    dict
                ):

                    for inner_key, inner_value in nested_value.items():

                        column_name = (
                            f"{key}_"
                            f"{nested_key}_"
                            f"{inner_key}"
                        )

                        result[column_name] = (
                            clean_excel_value(
                                inner_value
                            )
                        )

                else:

                    column_name = (
                        f"{key}_"
                        f"{nested_key}"
                    )

                    result[column_name] = (
                        clean_excel_value(
                            nested_value
                        )
                    )

        else:

            result[key] = clean_excel_value(
                value
            )

    return result


# ============================================================
# EXPORT ONE DATASET
# ============================================================

def export_dataset(
    sheet_name,
    file_path
):

    print(
        f"\nProcessing {sheet_name}..."
    )

    records = load_json(
        file_path
    )

    if not records:

        print(
            f"⚠️ {sheet_name}: no records"
        )

        return None

    rows = []

    for record in records:

        if not isinstance(
            record,
            dict
        ):
            continue

        rows.append(
            flatten_record(
                record
            )
        )

    if not rows:

        print(
            f"⚠️ {sheet_name}: "
            "no valid records"
        )

        return None

    dataframe = pd.DataFrame(
        rows
    )

    # ========================================================
    # COLUMN ORDER
    # ========================================================

    preferred_columns = [

        "schemaVersion",
        "recordType",

        "source_name",
        "source_url",

        "content_entityName",
        "content_title",

        "content_company",
        "content_startupName",

        "content_pricingModel",

        "content_data_employeeCount",

        "content_authors",

        "content_paper_url",
        "content_github_url",
        "content_github_stars",
        "content_published_date",

        "content_date",
        "content_is_remote",
        "content_role_family",

        "content_job_url",

        "content_description",

        "collectedAt",
    ]

    existing_columns = [
        column
        for column in preferred_columns
        if column in dataframe.columns
    ]

    remaining_columns = [
        column
        for column in dataframe.columns
        if column not in existing_columns
    ]

    dataframe = dataframe[
        existing_columns + remaining_columns
    ]

    # ========================================================
    # FINAL EXCEL CLEANING
    # ========================================================

    for column in dataframe.columns:

        dataframe[column] = dataframe[
            column
        ].apply(
            clean_excel_value
        )

    # ========================================================
    # FILE NAMES
    # ========================================================

    safe_name = (
        sheet_name
        .replace(" ", "_")
        .lower()
    )

    excel_file = (
        EXPORT_DIR
        / f"{safe_name}.xlsx"
    )

    csv_file = (
        EXPORT_DIR
        / f"{safe_name}.csv"
    )

    # ========================================================
    # WRITE EXCEL
    # ========================================================

    dataframe.to_excel(
        excel_file,
        index=False,
        sheet_name=sheet_name[:31]
    )

    # ========================================================
    # WRITE CSV
    # ========================================================

    dataframe.to_csv(
        csv_file,
        index=False,
        encoding="utf-8-sig"
    )

    print(
        f"✅ {sheet_name}: "
        f"{len(dataframe)} records"
    )

    print(
        f"   Excel: {excel_file}"
    )

    print(
        f"   CSV:   {csv_file}"
    )

    return dataframe


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "\n========================================"
    )

    print(
        "AI INTELLIGENCE DATA EXPORT"
    )

    print(
        "========================================\n"
    )

    exported = {}

    # ========================================================
    # EXPORT ALL SIX DATASETS
    # ========================================================

    for sheet_name, file_path in FILES.items():

        dataframe = export_dataset(
            sheet_name,
            file_path
        )

        if dataframe is not None:

            exported[
                sheet_name
            ] = dataframe

    # ========================================================
    # COMBINED WORKBOOK
    # ========================================================

    workbook = (
        EXPORT_DIR
        / "AI_Intelligence_Dataset.xlsx"
    )

    print(
        "\nCreating combined workbook..."
    )

    with pd.ExcelWriter(
        workbook,
        engine="openpyxl"
    ) as writer:

        for sheet_name, dataframe in exported.items():

            actual_sheet_name = sheet_name[:31]

            dataframe.to_excel(
                writer,
                index=False,
                sheet_name=actual_sheet_name
            )

            worksheet = writer.sheets[
                actual_sheet_name
            ]

            # Freeze header
            worksheet.freeze_panes = "A2"

            # Auto filter
            worksheet.auto_filter.ref = (
                worksheet.dimensions
            )

            # Make columns readable
            for column_cells in worksheet.columns:

                max_length = 0

                column_letter = (
                    column_cells[0].column_letter
                )

                for cell in column_cells:

                    if cell.value is not None:

                        cell_length = len(
                            str(cell.value)
                        )

                        if cell_length > max_length:
                            max_length = cell_length

                # Keep width reasonable
                width = min(
                    max(max_length + 2, 12),
                    50
                )

                worksheet.column_dimensions[
                    column_letter
                ].width = width

    print(
        "\n========================================"
    )

    print(
        "EXPORT COMPLETED SUCCESSFULLY"
    )

    print(
        "========================================"
    )

    print(
        f"\nCombined workbook:"
    )

    print(
        workbook
    )

    print(
        "\nSheets created:"
    )

    for sheet_name in exported:

        dataframe = exported[
            sheet_name
        ]

        print(
            f"  ✅ {sheet_name}: "
            f"{len(dataframe)} records"
        )

    print(
        "\n========================================\n"
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    main()