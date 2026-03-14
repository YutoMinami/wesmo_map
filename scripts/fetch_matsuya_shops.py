"""Fetch Matsuya stores from the official Matsuben shop listing.

The script stores chain-specific review CSVs and updates the shared
`shops_scraped.csv` used by downstream merge, geocode, and publish steps.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import subprocess
from pathlib import Path
from urllib.parse import urlencode, urljoin

from bs4 import BeautifulSoup, Tag


ROOT_DIR = Path(__file__).resolve().parent.parent
SCRAPED_CSV = ROOT_DIR / "data" / "shops_scraped.csv"
MATSUYA_CSV = ROOT_DIR / "data" / "smart_code" / "matsuya_shops_latest.csv"
MATSUYA_CLOSED_CSV = ROOT_DIR / "data" / "smart_code" / "matsuya_closed_latest.csv"

BASE_URL = "https://bento.matsuyafoods.co.jp"
LIST_PATH = "/matsuben-net/shop"
LIST_URL = urljoin(BASE_URL, LIST_PATH)
CHAIN_CODE = "matsuya"
CHAIN_NAME = "松屋"
PAYMENT_TAGS = "smart_code"
CSV_FIELDS = [
    "shop_id",
    "chain_code",
    "chain_name",
    "shop_name",
    "address",
    "lat",
    "lng",
    "payment_tags",
    "source_url",
]
RESULTS_PATTERN = re.compile(r"検索結果.*?<span>([\d,]+)</span>件", re.S)
SHOPS_ARRAY_PATTERN = re.compile(r"var shops = (\[.*?\]);", re.S)


def main() -> None:
    """Fetch active and closed Matsuya stores and update CSV outputs."""
    shops = fetch_all_shops()
    active_shops = [shop for shop in shops if shop["is_closed"] != "TRUE"]
    closed_shops = [shop for shop in shops if shop["is_closed"] == "TRUE"]
    write_rows(MATSUYA_CSV, active_shops)
    write_rows(MATSUYA_CLOSED_CSV, closed_shops)
    update_scraped_csv(active_shops)
    print(
        f"Wrote {len(active_shops)} active Matsuya shops to {MATSUYA_CSV}, "
        f"{len(closed_shops)} closed shops to {MATSUYA_CLOSED_CSV}, "
        f"and updated {SCRAPED_CSV}."
    )


def fetch_all_shops() -> list[dict[str, str]]:
    """Fetch all Matsuya stores across paginated shop results.

    Returns:
        Deduplicated shop rows sorted by `shop_id`.
    """
    first_page_html = fetch_page_html(page=1)
    total_pages = extract_total_pages(first_page_html)
    shops_by_id: dict[str, dict[str, str]] = {}
    print(f"Fetching {total_pages} Matsuya pages...")

    for page in range(1, total_pages + 1):
        html = first_page_html if page == 1 else fetch_page_html(page=page)
        for row in parse_shop_rows(html, build_page_url(page)):
            shops_by_id[row["shop_id"]] = row
        if page == 1 or page == total_pages or page % 20 == 0:
            print(f"Fetched page {page}/{total_pages}")

    return [shops_by_id[key] for key in sorted(shops_by_id)]


def fetch_page_html(page: int) -> str:
    """Fetch one paginated Matsuya shop list page.

    Args:
        page: 1-based page number.

    Returns:
        HTML response text.
    """
    command = [
        "curl",
        "-sS",
        "-L",
        "-A",
        "wesmo_map/0.1",
        build_page_url(page),
    ]
    result = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
    )
    return result.stdout


def extract_total_pages(html: str) -> int:
    """Extract the total number of paginated shop-list pages.

    Args:
        html: Raw HTML response text.

    Returns:
        Number of pages to fetch.

    Raises:
        ValueError: If the result count cannot be found.
    """
    match = RESULTS_PATTERN.search(html)
    if match is None:
        raise ValueError("Could not find total Matsuya shop count in shop list page.")
    total_count = int(match.group(1).replace(",", ""))
    return max(1, math.ceil(total_count / 10))


def parse_shop_rows(html: str, page_url: str) -> list[dict[str, str]]:
    """Parse Matsuya shop rows from one paginated result page.

    Args:
        html: Raw HTML response text.
        page_url: Canonical URL for the current page.

    Returns:
        Parsed shop rows including chain-specific review fields.
    """
    soup = BeautifulSoup(html, "html.parser")
    areas = soup.select("div.shopArea")
    pins = extract_pin_rows(html)
    if len(areas) != len(pins):
        raise ValueError(
            f"Expected shop areas and pin rows to match: {len(areas)} != {len(pins)}"
        )

    rows: list[dict[str, str]] = []
    for area, pin in zip(areas, pins):
        row = parse_shop_area(area, pin, page_url)
        if row is not None:
            rows.append(row)
    return rows


def extract_pin_rows(html: str) -> list[dict[str, str]]:
    """Extract the embedded pin array from a Matsuya shop list page.

    Args:
        html: Raw HTML response text.

    Returns:
        Parsed pin dictionaries in the same order as rendered shop blocks.

    Raises:
        ValueError: If the embedded array cannot be found.
    """
    match = SHOPS_ARRAY_PATTERN.search(html)
    if match is None:
        raise ValueError("Could not find embedded Matsuya pin array.")
    return json.loads(match.group(1))


def parse_shop_area(area: Tag, pin: dict[str, object], page_url: str) -> dict[str, str] | None:
    """Parse a rendered Matsuya shop block and its matching map pin.

    Args:
        area: Shop block element.
        pin: Embedded map-pin payload for the same visual row.
        page_url: Canonical URL for the current page.

    Returns:
        Parsed shop row, or `None` when the row is not a Matsuya store.
    """
    title_node = area.select_one("dt span")
    address_node = area.select_one("dl.address dd")
    tel_node = area.select_one("dl.tel dd")
    hours_node = area.select_one("dl.time dd")
    info_node = area.select_one("dl.shopInfo dd")
    link = area.select_one("a.shopLink[href]")

    if title_node is None or address_node is None:
        return None

    shop_name = normalize_text(title_node.get_text(" ", strip=True))
    if not shop_name.startswith(CHAIN_NAME):
        return None

    address = normalize_text(address_node.get_text(" ", strip=True))
    phone = normalize_text(tel_node.get_text(" ", strip=True)) if tel_node else ""
    hours = normalize_text(hours_node.get_text(" ", strip=True)) if hours_node else ""
    note = normalize_text(info_node.get_text(" ", strip=True)) if info_node else ""
    source_url = urljoin(BASE_URL, link["href"]) if link else page_url
    lat = str((pin.get("position") or {}).get("lat", ""))  # type: ignore[union-attr]
    lng = str((pin.get("position") or {}).get("lon", ""))  # type: ignore[union-attr]

    return {
        "shop_id": build_shop_id(shop_name, address),
        "chain_code": CHAIN_CODE,
        "chain_name": CHAIN_NAME,
        "shop_name": shop_name,
        "address": address,
        "lat": lat,
        "lng": lng,
        "payment_tags": PAYMENT_TAGS,
        "source_url": source_url,
        "is_closed": "TRUE" if is_closed(shop_name, note) else "FALSE",
        "accepts_online": "TRUE" if link is not None else "FALSE",
        "phone": phone,
        "hours": hours,
        "note": note,
    }


def build_page_url(page: int) -> str:
    """Build the canonical URL for one Matsuya result page.

    Args:
        page: 1-based page number.

    Returns:
        Absolute page URL.
    """
    query = urlencode({"page": page, "sort": "Shop.id", "direction": "asc"})
    return f"{LIST_URL}?{query}"


def build_shop_id(shop_name: str, address: str) -> str:
    """Build a stable shop id from the rendered name and address.

    Args:
        shop_name: Rendered shop name.
        address: Rendered address.

    Returns:
        Stable hashed shop id.
    """
    digest = hashlib.sha1(f"{shop_name}\n{address}".encode("utf-8")).hexdigest()[:12]
    return f"{CHAIN_CODE}-{digest}"


def normalize_text(value: str) -> str:
    """Collapse whitespace in a text fragment.

    Args:
        value: Source text.

    Returns:
        Normalized text.
    """
    return " ".join(value.split())


def is_closed(shop_name: str, note: str) -> bool:
    """Detect closure notices embedded in the row text.

    Args:
        shop_name: Normalized shop name.
        note: Normalized shop note text.

    Returns:
        `True` when the row appears to represent a closed store.
    """
    text = f"{shop_name} {note}"
    return "閉店" in text or "ご愛顧ありがとうございました" in text


def write_rows(path: Path, shops: list[dict[str, str]]) -> None:
    """Write Matsuya review rows to a CSV file.

    Args:
        path: Output CSV path.
        shops: Rows to write.
    """
    fieldnames = CSV_FIELDS + ["is_closed", "accepts_online", "phone", "hours", "note"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(shops)


def update_scraped_csv(new_rows: list[dict[str, str]]) -> None:
    """Replace Matsuya rows inside the shared scraped CSV.

    Args:
        new_rows: Active Matsuya rows to publish into `shops_scraped.csv`.
    """
    existing_rows: list[dict[str, str]] = []
    if SCRAPED_CSV.exists():
        with SCRAPED_CSV.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            existing_rows = [row for row in reader if row["chain_code"] != CHAIN_CODE]

    merged_rows = existing_rows + [
        {field: row.get(field, "") for field in CSV_FIELDS} for row in new_rows
    ]

    with SCRAPED_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(merged_rows)


if __name__ == "__main__":
    main()
