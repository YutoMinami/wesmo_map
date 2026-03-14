"""Fetch Nishimatsuya stores from the official prefecture listing pages.

The script stores chain-specific review CSVs and updates the shared
`shops_scraped.csv` used by downstream merge, geocode, and publish steps.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup


ROOT_DIR = Path(__file__).resolve().parent.parent
SCRAPED_CSV = ROOT_DIR / "data" / "shops_scraped.csv"
NISHIMATSUYA_CSV = ROOT_DIR / "data" / "smart_code" / "nishimatsuya_shops_latest.csv"
NISHIMATSUYA_CLOSED_CSV = ROOT_DIR / "data" / "smart_code" / "nishimatsuya_closed_latest.csv"

BASE_URL = "https://www.24028.jp/tenpo/"
LIST_URL = urljoin(BASE_URL, "shoplist.php")
CHAIN_CODE = "nishimatsuya"
CHAIN_NAME = "西松屋"
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


def main() -> None:
    """Fetch active and closed Nishimatsuya stores and update CSV outputs."""
    shops = fetch_all_shops()
    active_shops = [shop for shop in shops if shop["is_closed"] != "TRUE"]
    closed_shops = [shop for shop in shops if shop["is_closed"] == "TRUE"]
    write_rows(NISHIMATSUYA_CSV, active_shops)
    write_rows(NISHIMATSUYA_CLOSED_CSV, closed_shops)
    update_scraped_csv(active_shops)
    print(
        f"Wrote {len(active_shops)} active Nishimatsuya shops to {NISHIMATSUYA_CSV}, "
        f"{len(closed_shops)} closed shops to {NISHIMATSUYA_CLOSED_CSV}, "
        f"and updated {SCRAPED_CSV}."
    )


def fetch_all_shops() -> list[dict[str, str]]:
    """Fetch all Nishimatsuya stores across all prefectures.

    Returns:
        Deduplicated shop rows sorted by `shop_id`.
    """
    session = requests.Session()
    session.headers["User-Agent"] = "wesmo_map/0.1"

    shops_by_id: dict[str, dict[str, str]] = {}

    for cid in range(1, 48):
        response = session.get(LIST_URL, params={"cid": cid}, timeout=30)
        response.raise_for_status()
        response.encoding = response.apparent_encoding or response.encoding

        for row in parse_shop_rows(response.text):
            shops_by_id[row["shop_id"]] = row

    return [shops_by_id[key] for key in sorted(shops_by_id)]


def parse_shop_rows(html: str) -> list[dict[str, str]]:
    """Parse Nishimatsuya shop rows from a prefecture listing page.

    Args:
        html: Raw HTML response text.

    Returns:
        Parsed shop rows including chain-specific review fields.
    """
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []

    for tr in soup.select("div.table-main table tr")[1:]:
        cells = tr.find_all("td")
        if len(cells) < 4:
            continue

        name_cell = cells[0]
        address_cell = cells[1]
        hours_cell = cells[2]
        parking_cell = cells[3]

        link = name_cell.find("a", href=True)
        if link is None:
            continue

        source_url = urljoin(BASE_URL, link["href"])
        doc_id = extract_doc_id(link["href"])
        address_lines = list(address_cell.stripped_strings)
        if not address_lines:
            continue

        phone = extract_phone(address_lines)
        address_parts = [line for line in address_lines if line != phone]
        address = normalize_text(" ".join(address_parts))

        rows.append(
            {
                "shop_id": f"{CHAIN_CODE}-{doc_id}",
                "chain_code": CHAIN_CODE,
                "chain_name": CHAIN_NAME,
                "shop_name": normalize_text(name_cell.get_text(" ", strip=True)),
                "address": normalize_text(address),
                "lat": "",
                "lng": "",
                "payment_tags": PAYMENT_TAGS,
                "source_url": source_url,
                "is_closed": "TRUE" if is_closed(name_cell, address) else "FALSE",
                # Keep extra fields in the chain-specific CSV for review.
                "phone": phone,
                "hours": normalize_text(hours_cell.get_text(" ", strip=True)),
                "parking": normalize_text(parking_cell.get_text(" ", strip=True)),
            }
        )

    return rows


def extract_doc_id(href: str) -> str:
    """Extract the `doc` identifier from a shop detail URL.

    Args:
        href: Relative or absolute detail URL.

    Returns:
        Extracted document id.

    Raises:
        ValueError: If the identifier cannot be extracted.
    """
    parsed = urlparse(href)
    doc = parse_qs(parsed.query).get("doc", [""])[0]
    if doc:
        return doc

    match = re.search(r"doc=(\d+)", href)
    if match:
        return match.group(1)

    raise ValueError(f"Could not extract doc id from {href}")


def normalize_text(value: str) -> str:
    """Collapse whitespace in a text fragment.

    Args:
        value: Source text.

    Returns:
        Normalized text.
    """
    return " ".join(value.split())


def extract_phone(lines: list[str]) -> str:
    """Extract a phone number from parsed address lines.

    Args:
        lines: Text lines from the address cell.

    Returns:
        Phone number if present, otherwise an empty string.
    """
    for line in lines:
        if re.fullmatch(r"0\d{1,4}-\d{1,4}-\d{3,4}", line):
            return line
    return ""


def is_closed(name_cell: BeautifulSoup, address: str) -> bool:
    """Detect closure notices embedded in the row text.

    Args:
        name_cell: Shop-name cell element.
        address: Normalized address string.

    Returns:
        `True` when the row appears to represent a closed store.
    """
    shop_name = normalize_text(name_cell.get_text(" ", strip=True))
    text = f"{shop_name} {address}"
    return "閉店致しました" in text or "閉店致します" in text


def write_rows(path: Path, shops: list[dict[str, str]]) -> None:
    """Write Nishimatsuya review rows to a CSV file.

    Args:
        path: Output CSV path.
        shops: Rows to write.
    """
    fieldnames = CSV_FIELDS + ["is_closed", "phone", "hours", "parking"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(shops)


def update_scraped_csv(new_rows: list[dict[str, str]]) -> None:
    """Replace Nishimatsuya rows inside the shared scraped CSV.

    Args:
        new_rows: Active Nishimatsuya rows to publish into `shops_scraped.csv`.
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
