from __future__ import annotations

import csv
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
CHAINS_MASTER_CSV = ROOT_DIR / "data" / "chains_master.csv"
SMART_CODE_CHANGES_CSV = ROOT_DIR / "data" / "smart_code" / "chain_changes_latest.csv"
CHAIN_ALIASES_CSV = ROOT_DIR / "data" / "smart_code" / "chain_aliases.csv"
FETCH_QUEUE_CSV = ROOT_DIR / "data" / "smart_code" / "chains_fetch_queue_latest.csv"
FETCH_BLOCKED_CSV = ROOT_DIR / "data" / "smart_code" / "chains_fetch_blocked_latest.csv"

MASTER_FIELDS = [
    "chain_code",
    "chain_name",
    "enabled",
    "source_type",
    "source_url",
    "source_tags",
    "payment_tags",
    "first_seen_at",
    "last_seen_at",
    "deleted_at",
    "notes",
]
CHANGE_FIELDS = ["change_type", "snapshot_date", "section_name", "chain_name"]
ALIAS_FIELDS = ["smart_code_chain_name", "master_chain_name", "notes"]
QUEUE_FIELDS = [
    "snapshot_date",
    "chain_code",
    "chain_name",
    "source_type",
    "source_url",
    "payment_tags",
    "queue_reason",
]
BLOCKED_FIELDS = [
    "snapshot_date",
    "chain_name",
    "change_type",
    "blocked_reason",
    "source_type",
    "source_url",
    "enabled",
    "chain_code",
]


def main() -> None:
    master_rows = load_rows(CHAINS_MASTER_CSV, MASTER_FIELDS)
    change_rows = load_rows(SMART_CODE_CHANGES_CSV, CHANGE_FIELDS)
    aliases = load_aliases(CHAIN_ALIASES_CSV)

    changed_names = {
        canonical_name(row["chain_name"], aliases): row
        for row in change_rows
        if row["change_type"] in {"added", "removed"}
    }
    master_by_name = {row["chain_name"]: row for row in master_rows}

    queue_rows: list[dict[str, str]] = []
    blocked_rows: list[dict[str, str]] = []

    for canonical, change_row in sorted(changed_names.items()):
        master_row = master_by_name.get(canonical)
        if master_row is None:
            blocked_rows.append(
                build_blocked_row(change_row, "", "", "", "", "missing_master_row")
            )
            continue

        if change_row["change_type"] == "removed":
            blocked_rows.append(
                build_blocked_row(
                    change_row,
                    master_row["source_type"],
                    master_row["source_url"],
                    master_row["enabled"],
                    master_row["chain_code"],
                    "removed_from_smart_code",
                )
            )
            continue

        if master_row["deleted_at"]:
            blocked_rows.append(
                build_blocked_row(
                    change_row,
                    master_row["source_type"],
                    master_row["source_url"],
                    master_row["enabled"],
                    master_row["chain_code"],
                    "marked_deleted",
                )
            )
            continue

        blocked_reason = determine_blocked_reason(master_row)
        if blocked_reason:
            blocked_rows.append(
                build_blocked_row(
                    change_row,
                    master_row["source_type"],
                    master_row["source_url"],
                    master_row["enabled"],
                    master_row["chain_code"],
                    blocked_reason,
                )
            )
            continue

        queue_rows.append(
            {
                "snapshot_date": change_row["snapshot_date"],
                "chain_code": master_row["chain_code"],
                "chain_name": master_row["chain_name"],
                "source_type": master_row["source_type"],
                "source_url": master_row["source_url"],
                "payment_tags": master_row["payment_tags"],
                "queue_reason": "smart_code_changed",
            }
        )

    write_rows(FETCH_QUEUE_CSV, QUEUE_FIELDS, queue_rows)
    write_rows(FETCH_BLOCKED_CSV, BLOCKED_FIELDS, blocked_rows)

    print(
        f"Wrote {len(queue_rows)} fetch targets and {len(blocked_rows)} blocked rows."
    )


def load_rows(path: Path, expected_fields: list[str]) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != expected_fields:
            raise ValueError(
                f"Unexpected columns in {path}: {reader.fieldnames} != {expected_fields}"
            )
        return [{field: (row.get(field) or "").strip() for field in expected_fields} for row in reader]


def load_aliases(path: Path) -> dict[str, str]:
    rows = load_rows(path, ALIAS_FIELDS)
    return {
        row["smart_code_chain_name"]: row["master_chain_name"]
        for row in rows
        if row["smart_code_chain_name"] and row["master_chain_name"]
    }


def canonical_name(name: str, aliases: dict[str, str]) -> str:
    return aliases.get(name, name)


def determine_blocked_reason(row: dict[str, str]) -> str:
    if row["enabled"] != "TRUE":
        return "disabled"
    if not row["chain_code"]:
        return "missing_chain_code"
    if row["source_type"] in {"", "review_needed"}:
        return "source_type_review_needed"
    return ""


def build_blocked_row(
    change_row: dict[str, str],
    source_type: str,
    source_url: str,
    enabled: str,
    chain_code: str,
    blocked_reason: str,
) -> dict[str, str]:
    return {
        "snapshot_date": change_row["snapshot_date"],
        "chain_name": change_row["chain_name"],
        "change_type": change_row["change_type"],
        "blocked_reason": blocked_reason,
        "source_type": source_type,
        "source_url": source_url,
        "enabled": enabled,
        "chain_code": chain_code,
    }


def write_rows(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
