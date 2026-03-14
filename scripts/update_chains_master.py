from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
CHAINS_MASTER_CSV = ROOT_DIR / "data" / "chains_master.csv"
SMART_CODE_CHAINS_CSV = ROOT_DIR / "data" / "smart_code" / "chains_latest.csv"
SMART_CODE_CHANGES_CSV = ROOT_DIR / "data" / "smart_code" / "chain_changes_latest.csv"
CHAIN_ALIASES_CSV = ROOT_DIR / "data" / "smart_code" / "chain_aliases.csv"
CHAIN_REVIEW_CSV = ROOT_DIR / "data" / "smart_code" / "chains_review_latest.csv"
SMART_CODE_SHOPLIST_URL = "https://www.smart-code.jp/shoplist/"

MASTER_FIELDS = [
    "chain_code",
    "chain_name",
    "enabled",
    "source_type",
    "source_url",
    "source_tags",
    "source_category",
    "category",
    "payment_tags",
    "first_seen_at",
    "last_seen_at",
    "deleted_at",
    "notes",
]
LATEST_FIELDS = ["snapshot_date", "section_name", "chain_name"]
CHANGE_FIELDS = ["change_type", "snapshot_date", "section_name", "chain_name"]
ALIAS_FIELDS = ["smart_code_chain_name", "master_chain_name", "notes"]
REVIEW_FIELDS = ["snapshot_date", "section_name", "smart_code_chain_name", "suggested_master_chain_name", "review_status"]


def main() -> None:
    master_rows = load_rows(CHAINS_MASTER_CSV, MASTER_FIELDS)
    latest_rows = load_rows(SMART_CODE_CHAINS_CSV, LATEST_FIELDS)
    change_rows = load_rows(SMART_CODE_CHANGES_CSV, CHANGE_FIELDS)
    aliases = load_aliases(CHAIN_ALIASES_CSV)

    latest_by_name = index_latest_rows(latest_rows, aliases)
    latest_date = extract_latest_date(latest_rows)
    removed_names = {
        canonical_chain_name(row["chain_name"].strip(), aliases)
        for row in change_rows
        if row["change_type"].strip() == "removed"
    }

    master_rows = drop_alias_duplicate_rows(master_rows, aliases)

    seen_names: set[str] = set()
    added_count = 0
    updated_count = 0
    removed_count = 0
    reactivated_count = 0

    for row in master_rows:
        chain_name = row["chain_name"].strip()
        if not chain_name:
            continue

        if chain_name in latest_by_name:
            seen_names.add(chain_name)
            if update_existing_row(row, latest_by_name[chain_name], latest_date):
                updated_count += 1
            if row["deleted_at"]:
                row["deleted_at"] = ""
                reactivated_count += 1
        elif chain_name in removed_names and not row["deleted_at"]:
            row["deleted_at"] = latest_date
            removed_count += 1

    for chain_name in sorted(set(latest_by_name) - seen_names):
        latest_row = latest_by_name[chain_name]
        master_rows.append(
            {
                "chain_code": "",
                "chain_name": chain_name,
                "enabled": "FALSE",
                "source_type": "review_needed",
                "source_url": SMART_CODE_SHOPLIST_URL,
                "source_tags": "smart_code_site",
                "source_category": latest_row["section_name"],
                "category": "",
                "payment_tags": "smart_code",
                "first_seen_at": latest_row["snapshot_date"],
                "last_seen_at": latest_row["snapshot_date"],
                "deleted_at": "",
                "notes": f"Auto-added from Smart Code section: {latest_row['section_name']}",
            }
        )
        added_count += 1

    master_rows.sort(key=lambda row: (row["chain_name"], row["chain_code"]))
    write_rows(CHAINS_MASTER_CSV, MASTER_FIELDS, master_rows)
    write_rows(CHAIN_REVIEW_CSV, REVIEW_FIELDS, build_review_rows(master_rows, latest_by_name))

    print(
        "Updated chains_master.csv: "
        f"{added_count} added, "
        f"{updated_count} refreshed, "
        f"{removed_count} marked removed, "
        f"{reactivated_count} reactivated, "
        f"{len(build_review_rows(master_rows, latest_by_name))} need review."
    )


def load_rows(path: Path, expected_fields: list[str]) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != expected_fields:
            raise ValueError(
                f"Unexpected columns in {path}: {reader.fieldnames} != {expected_fields}"
            )
        return [normalize_row(row, expected_fields) for row in reader]


def normalize_row(row: dict[str, str | None], fields: list[str]) -> dict[str, str]:
    return {field: (row.get(field) or "").strip() for field in fields}


def index_latest_rows(
    rows: list[dict[str, str]], aliases: dict[str, str]
) -> dict[str, dict[str, str]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        chain_name = canonical_chain_name(row["chain_name"].strip(), aliases)
        if not chain_name:
            continue
        grouped[chain_name].append(row)

    indexed: dict[str, dict[str, str]] = {}
    for chain_name, grouped_rows in grouped.items():
        indexed[chain_name] = grouped_rows[0]
    return indexed


def load_aliases(path: Path) -> dict[str, str]:
    rows = load_rows(path, ALIAS_FIELDS)
    return {
        row["smart_code_chain_name"]: row["master_chain_name"]
        for row in rows
        if row["smart_code_chain_name"] and row["master_chain_name"]
    }


def canonical_chain_name(chain_name: str, aliases: dict[str, str]) -> str:
    return aliases.get(chain_name, chain_name)


def extract_latest_date(rows: list[dict[str, str]]) -> str:
    dates = {row["snapshot_date"].strip() for row in rows if row["snapshot_date"].strip()}
    if not dates:
        raise ValueError("No snapshot_date found in chains_latest.csv")
    if len(dates) > 1:
        raise ValueError(f"Multiple snapshot dates found: {sorted(dates)}")
    return dates.pop()


def update_existing_row(
    row: dict[str, str], latest_row: dict[str, str], latest_date: str
) -> bool:
    changed = False

    if row["last_seen_at"] != latest_date:
        row["last_seen_at"] = latest_date
        changed = True

    if not row["source_url"]:
        row["source_url"] = SMART_CODE_SHOPLIST_URL
        changed = True

    if merge_pipe_values(row, "source_tags", "smart_code_site"):
        changed = True

    if not row["source_category"] and latest_row["section_name"]:
        row["source_category"] = latest_row["section_name"]
        changed = True

    if merge_pipe_values(row, "payment_tags", "smart_code"):
        changed = True

    if not row["source_type"]:
        row["source_type"] = "review_needed"
        changed = True

    return changed


def drop_alias_duplicate_rows(
    rows: list[dict[str, str]], aliases: dict[str, str]
) -> list[dict[str, str]]:
    canonical_names = {row["chain_name"] for row in rows}
    filtered_rows: list[dict[str, str]] = []

    for row in rows:
        alias_target = aliases.get(row["chain_name"], "")
        should_drop = (
            alias_target
            and alias_target in canonical_names
            and not row["chain_code"]
            and row["source_type"] == "review_needed"
        )
        if not should_drop:
            filtered_rows.append(row)

    return filtered_rows


def merge_pipe_values(row: dict[str, str], field: str, value: str) -> bool:
    current_values = [item for item in row[field].split("|") if item]
    if value in current_values:
        return False

    current_values.append(value)
    row[field] = "|".join(sorted(set(current_values)))
    return True


def build_review_rows(
    master_rows: list[dict[str, str]], latest_by_name: dict[str, dict[str, str]]
) -> list[dict[str, str]]:
    exact_names = {row["chain_name"] for row in master_rows}
    review_rows: list[dict[str, str]] = []

    for chain_name, latest_row in sorted(latest_by_name.items()):
        matched_row = find_master_match(master_rows, chain_name)
        if matched_row and matched_row["chain_code"]:
            continue

        suggested_name = chain_name if chain_name not in exact_names else ""
        review_rows.append(
            {
                "snapshot_date": latest_row["snapshot_date"],
                "section_name": latest_row["section_name"],
                "smart_code_chain_name": latest_row["chain_name"],
                "suggested_master_chain_name": suggested_name,
                "review_status": "needs_review",
            }
        )

    return review_rows


def find_master_match(
    master_rows: list[dict[str, str]], chain_name: str
) -> dict[str, str] | None:
    for row in master_rows:
        if row["chain_name"] == chain_name:
            return row
    return None


def write_rows(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
