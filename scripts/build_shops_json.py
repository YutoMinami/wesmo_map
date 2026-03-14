from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
INPUT_CSV = ROOT_DIR / "data" / "shops_geocoded.csv"
OUTPUT_JSON = ROOT_DIR / "data" / "shops.json"
CATEGORY_MASTER_CSV = ROOT_DIR / "data" / "category_master.csv"
CHAINS_MASTER_CSV = ROOT_DIR / "data" / "chains_master.csv"
REQUIRED_FIELDS = (
    "shop_id",
    "chain_code",
    "chain_name",
    "shop_name",
    "address",
    "lat",
    "lng",
    "payment_tags",
)


def main() -> None:
    category_labels = load_category_labels(CATEGORY_MASTER_CSV)
    chain_categories = load_chain_categories(CHAINS_MASTER_CSV)
    shops, skipped_count = load_shops(INPUT_CSV, chain_categories, category_labels)
    OUTPUT_JSON.write_text(
        json.dumps(shops, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"Wrote {len(shops)} shops to {OUTPUT_JSON} "
        f"(skipped {skipped_count} unresolved rows)"
    )


def load_shops(
    csv_path: Path,
    chain_categories: dict[str, str],
    category_labels: dict[str, str],
) -> tuple[list[dict[str, object]], int]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        validate_header(reader.fieldnames, csv_path)

        shops: list[dict[str, object]] = []
        seen_ids: set[str] = set()
        skipped_count = 0

        for index, row in enumerate(reader, start=2):
            shop_id = require_value(row, "shop_id", index)
            if shop_id in seen_ids:
                raise ValueError(f"Duplicate shop_id at line {index}: {shop_id}")

            seen_ids.add(shop_id)
            lat_value = read_value(row, "lat")
            lng_value = read_value(row, "lng")
            if not lat_value or not lng_value:
                skipped_count += 1
                continue
            chain_code = require_value(row, "chain_code", index)
            category = chain_categories.get(chain_code, "")
            shops.append(
                {
                    "id": shop_id,
                    "chainCode": chain_code,
                    "chain": require_value(row, "chain_name", index),
                    "name": require_value(row, "shop_name", index),
                    "address": require_value(row, "address", index),
                    "lat": parse_float(lat_value, "lat", index),
                    "lng": parse_float(lng_value, "lng", index),
                    "category": category,
                    "categoryLabel": category_labels.get(category, ""),
                    "paymentTags": parse_payment_tags(
                        require_value(row, "payment_tags", index)
                    ),
                }
            )

    return shops, skipped_count


def validate_header(fieldnames: list[str] | None, csv_path: Path) -> None:
    if fieldnames is None:
        raise ValueError(f"CSV header is missing: {csv_path}")

    missing_fields = [field for field in REQUIRED_FIELDS if field not in fieldnames]
    if missing_fields:
        missing = ", ".join(missing_fields)
        raise ValueError(f"Missing required fields in {csv_path}: {missing}")


def load_category_labels(csv_path: Path) -> dict[str, str]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        return {
            (row.get("category") or "").strip(): (row.get("label_ja") or "").strip()
            for row in reader
            if (row.get("category") or "").strip()
        }


def load_chain_categories(csv_path: Path) -> dict[str, str]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        return {
            (row.get("chain_code") or "").strip(): (row.get("category") or "").strip()
            for row in reader
            if (row.get("chain_code") or "").strip()
        }


def require_value(row: dict[str, str], field: str, line_number: int) -> str:
    value = read_value(row, field)
    if not value:
        raise ValueError(f"Missing value for {field} at line {line_number}")
    return value


def read_value(row: dict[str, str], field: str) -> str:
    return (row.get(field) or "").strip()


def parse_float(value: str, field: str, line_number: int) -> float:
    try:
        return float(value)
    except ValueError as error:
        raise ValueError(
            f"Invalid float for {field} at line {line_number}: {value}"
        ) from error


def parse_payment_tags(value: str) -> list[str]:
    return [tag.strip() for tag in value.split("|") if tag.strip()]


if __name__ == "__main__":
    main()
