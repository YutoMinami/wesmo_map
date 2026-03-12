from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
INPUT_CSV = ROOT_DIR / "data" / "shops_geocoded.csv"
OUTPUT_JSON = ROOT_DIR / "data" / "shops.json"
REQUIRED_FIELDS = (
    "shop_id",
    "chain_name",
    "shop_name",
    "address",
    "lat",
    "lng",
)


def main() -> None:
    shops = load_shops(INPUT_CSV)
    OUTPUT_JSON.write_text(
        json.dumps(shops, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(shops)} shops to {OUTPUT_JSON}")


def load_shops(csv_path: Path) -> list[dict[str, object]]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        validate_header(reader.fieldnames, csv_path)

        shops: list[dict[str, object]] = []
        seen_ids: set[str] = set()

        for index, row in enumerate(reader, start=2):
            shop_id = require_value(row, "shop_id", index)
            if shop_id in seen_ids:
                raise ValueError(f"Duplicate shop_id at line {index}: {shop_id}")

            seen_ids.add(shop_id)
            shops.append(
                {
                    "id": shop_id,
                    "chain": require_value(row, "chain_name", index),
                    "name": require_value(row, "shop_name", index),
                    "address": require_value(row, "address", index),
                    "lat": parse_float(require_value(row, "lat", index), "lat", index),
                    "lng": parse_float(require_value(row, "lng", index), "lng", index),
                }
            )

    return shops


def validate_header(fieldnames: list[str] | None, csv_path: Path) -> None:
    if fieldnames is None:
        raise ValueError(f"CSV header is missing: {csv_path}")

    missing_fields = [field for field in REQUIRED_FIELDS if field not in fieldnames]
    if missing_fields:
        missing = ", ".join(missing_fields)
        raise ValueError(f"Missing required fields in {csv_path}: {missing}")


def require_value(row: dict[str, str], field: str, line_number: int) -> str:
    value = (row.get(field) or "").strip()
    if not value:
        raise ValueError(f"Missing value for {field} at line {line_number}")
    return value


def parse_float(value: str, field: str, line_number: int) -> float:
    try:
        return float(value)
    except ValueError as error:
        raise ValueError(
            f"Invalid float for {field} at line {line_number}: {value}"
        ) from error


if __name__ == "__main__":
    main()
