from datetime import datetime, timezone, timedelta
import re


# ============================================================
# FRESHNESS CONFIGURATION
# ============================================================

FRESHNESS_HOURS = 24


# ============================================================
# CURRENT UTC TIME
# ============================================================

def get_current_utc():
    """
    Return the current UTC time.
    """

    return datetime.now(timezone.utc)


# ============================================================
# NORMALIZE ISO DATE
# ============================================================

def parse_iso_date(date_string):
    """
    Parse an ISO-8601 date.

    Example:
        2026-09-02T17:59:40Z
    """

    if not date_string:
        return None

    try:

        # Convert Z to +00:00
        normalized = date_string.replace(
            "Z",
            "+00:00"
        )

        date = datetime.fromisoformat(
            normalized
        )

        # Make sure date is UTC-aware
        if date.tzinfo is None:

            date = date.replace(
                tzinfo=timezone.utc
            )

        return date.astimezone(
            timezone.utc
        )

    except ValueError:

        return None


# ============================================================
# PARSE RELATIVE DATE
# ============================================================

def parse_relative_date(
    date_string,
    now=None
):
    """
    Convert relative dates into an absolute UTC timestamp.

    Examples:

        "2 hours ago"
        "30 minutes ago"
        "5 days ago"
        "1 hour ago"
    """

    if not date_string:
        return None

    if now is None:
        now = get_current_utc()

    text = date_string.lower().strip()

    # --------------------------------------------
    # Number + unit
    # --------------------------------------------

    pattern = r"(\d+)\s*(second|minute|hour|day|week)s?\s*ago"

    match = re.search(
        pattern,
        text
    )

    if not match:
        return None

    amount = int(
        match.group(1)
    )

    unit = match.group(2)

    if unit == "second":

        delta = timedelta(
            seconds=amount
        )

    elif unit == "minute":

        delta = timedelta(
            minutes=amount
        )

    elif unit == "hour":

        delta = timedelta(
            hours=amount
        )

    elif unit == "day":

        delta = timedelta(
            days=amount
        )

    elif unit == "week":

        delta = timedelta(
            weeks=amount
        )

    else:

        return None

    return now - delta


# ============================================================
# PARSE COMMON RELATIVE WORDS
# ============================================================

def parse_special_date(
    date_string,
    now=None
):

    if not date_string:
        return None

    if now is None:
        now = get_current_utc()

    text = date_string.lower().strip()

    if text in [
        "just now",
        "now"
    ]:

        return now

    if text == "yesterday":

        return now - timedelta(
            days=1
        )

    return None


# ============================================================
# UNIVERSAL DATE PARSER
# ============================================================

def parse_date(
    date_string,
    now=None
):
    """
    Try multiple date formats.

    Order:

    1. ISO date
    2. Relative date
    3. Special expressions
    """

    if not date_string:
        return None

    if now is None:
        now = get_current_utc()

    # Try ISO
    parsed = parse_iso_date(
        date_string
    )

    if parsed:
        return parsed

    # Try relative date
    parsed = parse_relative_date(
        date_string,
        now
    )

    if parsed:
        return parsed

    # Try special expressions
    parsed = parse_special_date(
        date_string,
        now
    )

    if parsed:
        return parsed

    return None


# ============================================================
# CHECK 24-HOUR FRESHNESS
# ============================================================

def is_fresh(
    published_date,
    now=None
):
    """
    Return True if content was published within
    the last 24 hours.
    """

    if not published_date:
        return False

    if now is None:
        now = get_current_utc()

    parsed_date = parse_date(
        published_date,
        now
    )

    if not parsed_date:
        return False

    age = now - parsed_date

    # Future dates are suspicious
    if age.total_seconds() < 0:
        return False

    return age <= timedelta(
        hours=FRESHNESS_HOURS
    )


# ============================================================
# GET CONTENT AGE
# ============================================================

def get_age_hours(
    published_date,
    now=None
):
    """
    Return the age of content in hours.
    """

    if not published_date:
        return None

    if now is None:
        now = get_current_utc()

    parsed_date = parse_date(
        published_date,
        now
    )

    if not parsed_date:
        return None

    age = now - parsed_date

    return round(
        age.total_seconds() / 3600,
        2
    )


# ============================================================
# TEST
# ============================================================

def main():

    now = datetime(
        2026,
        9,
        4,
        12,
        0,
        0,
        tzinfo=timezone.utc
    )

    test_dates = [
        "2 hours ago",
        "30 minutes ago",
        "23 hours ago",
        "25 hours ago",
        "2 days ago",
        "2026-09-04T10:00:00Z",
        "2026-09-03T10:00:00Z",
        "invalid date"
    ]

    print("=" * 70)
    print("FRESHNESS DETECTOR TEST")
    print("=" * 70)

    for date_string in test_dates:

        fresh = is_fresh(
            date_string,
            now
        )

        age = get_age_hours(
            date_string,
            now
        )

        print(
            f"\nDate: {date_string}"
        )

        print(
            f"Age: {age} hours"
        )

        print(
            f"Fresh: {fresh}"
        )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()