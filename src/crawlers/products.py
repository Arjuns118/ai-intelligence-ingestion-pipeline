import json
import re
import requests
from pathlib import Path
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_FILE = PROJECT_ROOT / "data" / "raw" / "products.json"

BASE_URL = "https://www.producthunt.com/topics/artificial-intelligence"

MAX_PRODUCTS = 1200
MAX_PAGES = 100
WORKERS = 15

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0 Safari/537.36"
    )
}


def clean_text(text):
    if not text:
        return None

    text = re.sub(r"\s+", " ", text)
    return text.strip() or None


def fetch_page(page):
    url = f"{BASE_URL}?page={page}"

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=30
        )

        if response.status_code != 200:
            print(f"Page {page}: HTTP {response.status_code}")
            return None

        return response.text

    except Exception as error:
        print(f"Page {page}: {error}")
        return None


def extract_products(html):
    soup = BeautifulSoup(html, "html.parser")

    products = {}

    for link in soup.find_all("a", href=True):

        href = link["href"]

        # Product Hunt product URL
        match = re.match(
            r"^/products/([^/?#]+)$",
            href
        )

        if not match:
            continue

        slug = match.group(1)

        if slug in {
            "new",
            "categories",
            "collections",
            "alternatives"
        }:
            continue

        name = clean_text(
            link.get_text(" ", strip=True)
        )

        if not name:
            continue

        # Find nearby text containing the product description.
        parent = link.parent

        surrounding = ""

        if parent:
            surrounding = clean_text(
                parent.get_text(" ", strip=True)
            ) or ""

        product_url = (
            "https://www.producthunt.com" + href
        )

        products[product_url] = {
            "name": name,
            "description": surrounding,
            "url": product_url
        }

    return products


def detect_pricing(text):
    if not text:
        return None

    text = text.lower()

    if "enterprise" in text:
        return "ENTERPRISE"

    if "freemium" in text:
        return "FREEMIUM"

    if "free options" in text:
        return "FREEMIUM"

    if re.search(r"\bfree\b", text):
        return "FREE"

    if re.search(r"\bpaid\b", text):
        return "PAID"

    return None


def make_record(product):
    name = product["name"]

    description = clean_text(
        product.get("description")
    )

    pricing = detect_pricing(
        description
    )

    return {
        "schemaVersion": "1.0",
        "recordType": "PRODUCT",

        "source": {
            "name": "Product Hunt",
            "url": product["url"]
        },

        "content": {
            "entityName": name,
            "description": description,
            "startupName": None,
            "pricingModel": pricing
        },

        "collectedAt": datetime.now(
            timezone.utc
        ).isoformat()
    }


def main():

    print("\n========================================")
    print("FAST PRODUCT HUNT AI PRODUCT CRAWLER")
    print("========================================\n")

    all_products = {}

    # -------------------------------------
    # STEP 1: Collect listing pages
    # -------------------------------------

    print("Collecting product listing pages...\n")

    with ThreadPoolExecutor(
        max_workers=WORKERS
    ) as executor:

        futures = {
            executor.submit(fetch_page, page): page
            for page in range(1, MAX_PAGES + 1)
        }

        for future in as_completed(futures):

            page = futures[future]

            try:
                html = future.result()

                if not html:
                    continue

                products = extract_products(html)

                for url, product in products.items():
                    all_products[url] = product

                print(
                    f"Page {page}: "
                    f"{len(products)} products | "
                    f"Total: {len(all_products)}"
                )

                if len(all_products) >= MAX_PRODUCTS:
                    break

            except Exception as error:
                print(
                    f"Page {page} failed: {error}"
                )

    # -------------------------------------
    # STEP 2: Limit to required amount
    # -------------------------------------

    products = list(
        all_products.values()
    )[:MAX_PRODUCTS]

    print(
        f"\nCollected {len(products)} "
        "unique product URLs."
    )

    # -------------------------------------
    # STEP 3: Convert to canonical records
    # -------------------------------------

    records = []

    for product in products:

        record = make_record(product)

        if record:
            records.append(record)

    # -------------------------------------
    # STEP 4: Deduplicate by name
    # -------------------------------------

    unique = {}

    for record in records:

        name = (
            record["content"]["entityName"]
            .lower()
            .strip()
        )

        if name not in unique:
            unique[name] = record

    records = list(
        unique.values()
    )

    records.sort(
        key=lambda x: (
            x["content"]["entityName"]
            or ""
        ).lower()
    )

    # -------------------------------------
    # STEP 5: Save
    # -------------------------------------

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
        f"Saved {len(records)} product records."
    )
    print(
        f"Output: {OUTPUT_FILE}"
    )
    print("========================================")


if __name__ == "__main__":
    main()