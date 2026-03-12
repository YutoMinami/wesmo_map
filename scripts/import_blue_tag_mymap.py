from __future__ import annotations

import argparse
import csv
import hashlib
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT_DIR / "data" / "shops_scraped.csv"
OUTPUT_FIELDS = (
    "shop_id",
    "chain_code",
    "chain_name",
    "shop_name",
    "address",
    "lat",
    "lng",
    "payment_tags",
    "source_url",
)
NS = {
    "kml": "http://www.opengis.net/kml/2.2",
}
SOURCE_URL = (
    "https://www.google.com/maps/d/viewer?mid=1cuUtTOY_H5F84hIkz0_tNmcSV3GsBpk"
)


def main() -> None:
    args = parse_args()
    kml_path = Path(args.input).expanduser().resolve()
    rows = load_blue_tag_rows(kml_path)
    write_rows(args.output, rows)
    print(f"Wrote {len(rows)} BLUE tag shops to {args.output}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import Wesmo! BLUE tag stores from a Google My Maps KML or KMZ export."
    )
    parser.add_argument("input", help="Path to a Google My Maps .kml or .kmz export")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="CSV file to overwrite with imported rows",
    )
    return parser.parse_args()


def load_blue_tag_rows(path: Path) -> list[dict[str, str]]:
    xml_text = read_kml_text(path)
    root = ET.fromstring(xml_text)
    rows: list[dict[str, str]] = []

    for placemark in root.findall(".//kml:Placemark", NS):
        name = text_or_empty(placemark.find("kml:name", NS))
        metadata = extract_extended_data(placemark)
        address = (
            metadata.get("住所")
            or text_or_empty(placemark.find("kml:address", NS))
            or extract_address(text_or_empty(placemark.find("kml:description", NS)))
        )
        coordinates = text_or_empty(placemark.find(".//kml:Point/kml:coordinates", NS))
        lat, lng = parse_coordinates(coordinates) if coordinates else ("", "")
        chain_name = infer_chain_name(name, metadata)
        source_url = metadata.get("店舗サイトURL") or SOURCE_URL

        rows.append(
            {
                "shop_id": build_shop_id(name, address),
                "chain_code": slugify(chain_name) or "blue-tag",
                "chain_name": chain_name or "Wesmo! BLUE tag",
                "shop_name": name or "Unnamed BLUE tag shop",
                "address": address,
                "lat": lat,
                "lng": lng,
                "payment_tags": "blue_tag",
                "source_url": source_url,
            }
        )

    return rows


def read_kml_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".kml":
        return path.read_text(encoding="utf-8")
    if suffix == ".kmz":
        with zipfile.ZipFile(path) as archive:
            kml_names = [name for name in archive.namelist() if name.endswith(".kml")]
            if not kml_names:
                raise ValueError(f"No KML found in KMZ: {path}")
            return archive.read(kml_names[0]).decode("utf-8")
    raise ValueError(f"Unsupported file type: {path}")


def parse_coordinates(value: str) -> tuple[str, str]:
    parts = [part.strip() for part in value.split(",")]
    if len(parts) < 2 or not parts[0] or not parts[1]:
        raise ValueError(f"Placemark coordinates are missing or invalid: {value}")
    lng = parts[0]
    lat = parts[1]
    return lat, lng


def extract_address(description: str) -> str:
    normalized = strip_html(description)
    for line in normalized.splitlines():
        candidate = line.strip()
        if candidate.startswith("住所"):
            _, _, value = candidate.partition(":")
            return value.strip()
    return ""


def extract_extended_data(placemark: ET.Element) -> dict[str, str]:
    values: dict[str, str] = {}
    for data in placemark.findall("kml:ExtendedData/kml:Data", NS):
        key = data.attrib.get("name", "").strip()
        value = text_or_empty(data.find("kml:value", NS))
        if key:
            values[key] = value
    return values


def infer_chain_name(shop_name: str, metadata: dict[str, str]) -> str:
    category = metadata.get("カテゴリ", "").strip()
    industry = metadata.get("業種", "").strip()
    if category:
        return category
    if industry:
        return industry
    if " " in shop_name:
        return shop_name.split(" ", 1)[0]
    return shop_name


def build_shop_id(shop_name: str, address: str) -> str:
    base = slugify(shop_name) or "blue-tag-shop"
    digest = hashlib.sha1(f"{shop_name}|{address}".encode("utf-8")).hexdigest()[:10]
    return f"{base}-{digest}"


def slugify(value: str) -> str:
    ascii_like = re.sub(r"[^0-9A-Za-z]+", "-", value.strip().lower())
    return ascii_like.strip("-")


def strip_html(value: str) -> str:
    no_breaks = value.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
    return re.sub(r"<[^>]+>", "", no_breaks)


def text_or_empty(element: ET.Element | None) -> str:
    if element is None or element.text is None:
        return ""
    return element.text.strip()


def write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
