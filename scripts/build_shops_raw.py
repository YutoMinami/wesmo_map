from __future__ import annotations

import csv
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
MANUAL_CSV = ROOT_DIR / "data" / "shops_manual.csv"
SCRAPED_CSV = ROOT_DIR / "data" / "shops_scraped.csv"
OUTPUT_CSV = ROOT_DIR / "data" / "shops_raw.csv"
FIELDS = (
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
NON_EMPTY_FIELDS = (
    "shop_id",
    "chain_code",
    "chain_name",
    "shop_name",
    "address",
    "payment_tags",
)


def main() -> None:
    manual_rows = load_rows(MANUAL_CSV)
    scraped_rows = load_rows(SCRAPED_CSV)
    merged_rows = merge_rows(manual_rows, scraped_rows)
    write_rows(OUTPUT_CSV, merged_rows)
    print(
        f"Wrote {len(merged_rows)} merged shops to {OUTPUT_CSV} "
        f"(manual={len(manual_rows)}, scraped={len(scraped_rows)})"
    )


def load_rows(csv_path: Path) -> list[dict[str, str]]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        validate_header(reader.fieldnames, csv_path)

        rows: list[dict[str, str]] = []
        seen_ids: set[str] = set()

        for line_number, row in enumerate(reader, start=2):
            normalized = {field: read_value(row, field) for field in FIELDS}
            for field in NON_EMPTY_FIELDS:
                require_non_empty(normalized[field], field, line_number, csv_path)

            shop_id = normalized["shop_id"]
            if shop_id in seen_ids:
                raise ValueError(
                    f"Duplicate shop_id in {csv_path} at line {line_number}: {shop_id}"
                )
            seen_ids.add(shop_id)
            validate_coordinates(normalized, line_number, csv_path)
            rows.append(normalized)

    return rows


def merge_rows(
    manual_rows: list[dict[str, str]], scraped_rows: list[dict[str, str]]
) -> list[dict[str, str]]:
    merged: dict[str, dict[str, str]] = {
        row["shop_id"]: dict(row) for row in scraped_rows
    }

    for manual_row in manual_rows:
        shop_id = manual_row["shop_id"]
        if shop_id not in merged:
            merged[shop_id] = dict(manual_row)
            continue

        merged[shop_id] = merge_pair(manual_row, merged[shop_id])

    return sorted(
        merged.values(),
        key=lambda row: (row["chain_code"], row["shop_name"], row["shop_id"]),
    )


def merge_pair(manual_row: dict[str, str], scraped_row: dict[str, str]) -> dict[str, str]:
    merged = dict(scraped_row)
    for field in FIELDS:
        manual_value = manual_row[field]
        scraped_value = scraped_row[field]

        if field == "payment_tags":
            merged[field] = merge_payment_tags(manual_value, scraped_value)
            continue

        merged[field] = manual_value or scraped_value

    return merged


def merge_payment_tags(manual_value: str, scraped_value: str) -> str:
    tags = []
    for value in (scraped_value, manual_value):
        for tag in value.split("|"):
            normalized = tag.strip()
            if normalized and normalized not in tags:
                tags.append(normalized)
    return "|".join(tags)


def write_rows(csv_path: Path, rows: list[dict[str, str]]) -> None:
    with csv_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def validate_header(fieldnames: list[str] | None, csv_path: Path) -> None:
    if fieldnames is None:
        raise ValueError(f"CSV header is missing: {csv_path}")

    missing_fields = [field for field in FIELDS if field not in fieldnames]
    if missing_fields:
        missing = ", ".join(missing_fields)
        raise ValueError(f"Missing required fields in {csv_path}: {missing}")


def validate_coordinates(row: dict[str, str], line_number: int, csv_path: Path) -> None:
    lat = row["lat"]
    lng = row["lng"]
    if not lat and not lng:
        return
    if not lat or not lng:
        raise ValueError(
            f"Both lat and lng must be provided together in {csv_path} at line {line_number}"
        )
    float(lat)
    float(lng)


def read_value(row: dict[str, str], field: str) -> str:
    return (row.get(field) or "").strip()


def require_non_empty(value: str, field: str, line_number: int, csv_path: Path) -> None:
    if not value:
        raise ValueError(f"Missing value for {field} at line {line_number} in {csv_path}")


if __name__ == "__main__":
    main()
