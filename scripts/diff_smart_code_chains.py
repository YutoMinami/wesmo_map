from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
INPUT_DIR = ROOT_DIR / "data" / "smart_code"
LATEST_CSV = INPUT_DIR / "chains_latest.csv"
PREVIOUS_CSV = INPUT_DIR / "chains_previous.csv"
CHANGES_CSV = INPUT_DIR / "chain_changes_latest.csv"
ARCHIVE_CHANGES_DIR = INPUT_DIR / "changes"
INPUT_FIELDS = ("snapshot_date", "section_name", "chain_name")
CHANGE_FIELDS = (
    "change_type",
    "snapshot_date",
    "section_name",
    "chain_name",
)


def main() -> None:
    latest_rows = load_rows(LATEST_CSV)
    previous_rows = load_rows(PREVIOUS_CSV) if PREVIOUS_CSV.exists() else []
    changes = build_changes(previous_rows, latest_rows)

    ARCHIVE_CHANGES_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_path = ARCHIVE_CHANGES_DIR / f"chain_changes_{timestamp}.csv"

    write_rows(CHANGES_CSV, changes)
    write_rows(archive_path, changes)
    LATEST_CSV.replace(PREVIOUS_CSV)
    write_rows(LATEST_CSV, latest_rows)

    print(f"Wrote {len(changes)} chain changes to {CHANGES_CSV}")


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        validate_header(reader.fieldnames, path)
        return [
            {
                "snapshot_date": (row.get("snapshot_date") or "").strip(),
                "section_name": (row.get("section_name") or "").strip(),
                "chain_name": (row.get("chain_name") or "").strip(),
            }
            for row in reader
        ]


def validate_header(fieldnames: list[str] | None, path: Path) -> None:
    if fieldnames is None:
        raise ValueError(f"CSV header is missing: {path}")

    missing = [field for field in INPUT_FIELDS if field not in fieldnames]
    if missing:
        raise ValueError(f"Missing required fields in {path}: {', '.join(missing)}")


def build_changes(
    previous_rows: list[dict[str, str]],
    latest_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    previous_keys = {(row["section_name"], row["chain_name"]) for row in previous_rows}
    latest_keys = {(row["section_name"], row["chain_name"]) for row in latest_rows}
    snapshot_date = latest_rows[0]["snapshot_date"] if latest_rows else ""

    added = latest_keys - previous_keys
    removed = previous_keys - latest_keys

    changes = [
        {
            "change_type": "added",
            "snapshot_date": snapshot_date,
            "section_name": section_name,
            "chain_name": chain_name,
        }
        for section_name, chain_name in sorted(added)
    ]
    changes.extend(
        {
            "change_type": "removed",
            "snapshot_date": snapshot_date,
            "section_name": section_name,
            "chain_name": chain_name,
        }
        for section_name, chain_name in sorted(removed)
    )
    return changes


def write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = CHANGE_FIELDS if rows and "change_type" in rows[0] else INPUT_FIELDS
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
