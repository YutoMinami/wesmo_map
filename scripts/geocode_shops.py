from __future__ import annotations

import argparse
import csv
import json
import re
import time
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

import jageocoder


ROOT_DIR = Path(__file__).resolve().parents[1]
RAW_CSV = ROOT_DIR / "data" / "shops_raw.csv"
GEOCODED_CSV = ROOT_DIR / "data" / "shops_geocoded.csv"
CACHE_CSV = ROOT_DIR / "data" / "geocode_cache.csv"
UNRESOLVED_CSV = ROOT_DIR / "data" / "geocode_unresolved.csv"
DEFAULT_PROVIDER = "jageocoder"
JAGEOCODER_SERVER_URL = "https://jageocoder.info-proto.com/jsonrpc"
MIN_JAGEOCODER_LEVEL = 7
BUILDING_TOKENS = (
    "ビル",
    "bld",
    "b1f",
    "f",
    "階",
    "号室",
    "号館",
    "棟",
    "タワー",
    "マンション",
    "ハイツ",
    "コート",
    "モール",
    "plaza",
    "プラザ",
)
RAW_REQUIRED_FIELDS = (
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
NON_EMPTY_RAW_FIELDS = (
    "shop_id",
    "chain_code",
    "chain_name",
    "shop_name",
    "address",
    "payment_tags",
)
CACHE_FIELDS = ("address", "lat", "lng", "raw_query", "provider")
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
UNRESOLVED_FIELDS = (
    "shop_id",
    "chain_code",
    "chain_name",
    "shop_name",
    "address",
    "payment_tags",
    "source_url",
)
USER_AGENT = "wesmo-map/0.1.0 (local geocoding tool)"


def main() -> None:
    args = parse_args()
    raw_rows = load_raw_rows(RAW_CSV)
    filtered_rows = filter_rows(raw_rows, args.only_chain, args.limit)
    target_ids = {row["shop_id"] for row in filtered_rows}
    cache = load_cache(CACHE_CSV, skip_cache=False)
    initialize_provider(args.provider)
    geocoded_rows = []
    unresolved_rows = []
    existing_coord_count = 0
    cache_hit_count = 0
    resolved_count = 0
    unresolved_count = 0

    for row in raw_rows:
        address = normalize_address(row["address"])
        lat = row["lat"]
        lng = row["lng"]

        if row["shop_id"] not in target_ids:
            geocoded_rows.append(
                {
                    "shop_id": row["shop_id"],
                    "chain_code": row["chain_code"],
                    "chain_name": row["chain_name"],
                    "shop_name": row["shop_name"],
                    "address": address,
                    "lat": lat,
                    "lng": lng,
                    "payment_tags": row["payment_tags"],
                    "source_url": row["source_url"],
                }
            )
            continue

        if lat or lng:
            if not (lat and lng):
                raise ValueError(
                    f"Both lat and lng must be provided together for shop_id={row['shop_id']}"
                )
            existing_coord_count += 1
        elif not args.skip_cache and address in cache:
            lat = cache[address]["lat"]
            lng = cache[address]["lng"]
            cache_hit_count += 1
        elif args.dry_run:
            unresolved_count += 1
            unresolved_rows.append(build_unresolved_row(row, address))
        else:
            result = geocode_address(address, args.provider, args.sleep_seconds)
            if result is not None:
                lat, lng = result
                cache[address] = {
                    "address": address,
                    "lat": lat,
                    "lng": lng,
                    "raw_query": address,
                    "provider": args.provider,
                }
                resolved_count += 1
            else:
                unresolved_count += 1
                unresolved_rows.append(build_unresolved_row(row, address))

        geocoded_rows.append(
            {
                "shop_id": row["shop_id"],
                "chain_code": row["chain_code"],
                "chain_name": row["chain_name"],
                "shop_name": row["shop_name"],
                "address": address,
                "lat": lat,
                "lng": lng,
                "payment_tags": row["payment_tags"],
                "source_url": row["source_url"],
            }
        )

    write_csv(GEOCODED_CSV, OUTPUT_FIELDS, geocoded_rows)
    write_csv(UNRESOLVED_CSV, UNRESOLVED_FIELDS, unresolved_rows)
    if not args.dry_run:
        write_csv(CACHE_CSV, CACHE_FIELDS, cache.values())

    print(
        "Processed "
        f"{len(filtered_rows)} shops: "
        f"{existing_coord_count} with existing coordinates, "
        f"{resolved_count} newly geocoded, "
        f"{cache_hit_count} from cache, "
        f"{unresolved_count} unresolved."
    )
    print(f"Wrote {len(unresolved_rows)} unresolved shops to {UNRESOLVED_CSV}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Geocode shops_raw.csv into shops_geocoded.csv"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not call the geocoding provider or update the cache.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process only the first N shops after filtering.",
    )
    parser.add_argument(
        "--skip-cache",
        action="store_true",
        help="Ignore existing geocode_cache.csv entries.",
    )
    parser.add_argument(
        "--only-chain",
        default=None,
        help="Process only one chain_code.",
    )
    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=0.3,
        help="Seconds to sleep after each provider request.",
    )
    parser.add_argument(
        "--provider",
        choices=("jageocoder", "nominatim"),
        default=DEFAULT_PROVIDER,
        help="Geocoding provider to use.",
    )
    return parser.parse_args()


def load_raw_rows(csv_path: Path) -> list[dict[str, str]]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        validate_header(reader.fieldnames, RAW_REQUIRED_FIELDS, csv_path)

        rows: list[dict[str, str]] = []
        seen_ids: set[str] = set()
        for line_number, row in enumerate(reader, start=2):
            normalized_row = {
                field: read_value(row, field)
                for field in RAW_REQUIRED_FIELDS
            }
            for field in NON_EMPTY_RAW_FIELDS:
                require_non_empty(normalized_row[field], field, line_number)
            shop_id = normalized_row["shop_id"]
            if shop_id in seen_ids:
                raise ValueError(
                    f"Duplicate shop_id in {csv_path} at line {line_number}: {shop_id}"
                )
            seen_ids.add(shop_id)
            rows.append(normalized_row)
        return rows


def filter_rows(
    rows: list[dict[str, str]], only_chain: str | None, limit: int | None
) -> list[dict[str, str]]:
    filtered = rows
    if only_chain:
        filtered = [row for row in filtered if row["chain_code"] == only_chain]
    if limit is not None:
        filtered = filtered[:limit]
    return filtered


def load_cache(
    csv_path: Path, skip_cache: bool
) -> dict[str, dict[str, str]]:
    if skip_cache or not csv_path.exists():
        return {}

    with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        validate_header(reader.fieldnames, CACHE_FIELDS, csv_path)
        cache: dict[str, dict[str, str]] = {}
        for line_number, row in enumerate(reader, start=2):
            address = require_value(row, "address", line_number)
            cache[address] = {
                "address": address,
                "lat": require_value(row, "lat", line_number),
                "lng": require_value(row, "lng", line_number),
                "raw_query": require_value(row, "raw_query", line_number),
                "provider": require_value(row, "provider", line_number),
            }
        return cache


def initialize_provider(provider: str) -> None:
    if provider == "jageocoder":
        jageocoder.init(url=JAGEOCODER_SERVER_URL)


def geocode_address(
    address: str, provider: str, sleep_seconds: float
) -> tuple[str, str] | None:
    if provider == "jageocoder":
        return geocode_with_jageocoder(address, sleep_seconds)
    if provider == "nominatim":
        return geocode_with_nominatim(address, sleep_seconds)
    raise ValueError(f"Unsupported provider: {provider}")


def geocode_with_jageocoder(
    address: str, sleep_seconds: float
) -> tuple[str, str] | None:
    for query in build_address_variants(address):
        result = jageocoder.search(query)
        candidate = pick_jageocoder_candidate(result, query)
        if candidate is not None:
            time.sleep(sleep_seconds)
            return str(candidate["y"]), str(candidate["x"])
        time.sleep(sleep_seconds)
    return None


def pick_jageocoder_candidate(
    result: dict[str, object], query: str
) -> dict[str, object] | None:
    matched = str(result.get("matched") or "")
    for candidate in result.get("candidates") or []:
        level = int(candidate.get("level") or 0)
        if level < MIN_JAGEOCODER_LEVEL:
            continue
        if matched and len(matched) / max(len(query), 1) < 0.6:
            continue
        return candidate
    return None


def geocode_with_nominatim(
    address: str, sleep_seconds: float
) -> tuple[str, str] | None:
    query = urllib.parse.urlencode(
        {
            "q": address,
            "format": "jsonv2",
            "limit": 1,
            "countrycodes": "jp",
        }
    )
    url = f"https://nominatim.openstreetmap.org/search?{query}"
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        },
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))

    time.sleep(sleep_seconds)

    if not payload:
        return None

    return payload[0]["lat"], payload[0]["lon"]


def write_csv(
    csv_path: Path, fieldnames: tuple[str, ...], rows: list[dict[str, str]] | object
) -> None:
    row_list = list(rows)
    with csv_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(row_list)


def validate_header(
    fieldnames: list[str] | None, required_fields: tuple[str, ...], csv_path: Path
) -> None:
    if fieldnames is None:
        raise ValueError(f"CSV header is missing: {csv_path}")

    missing_fields = [field for field in required_fields if field not in fieldnames]
    if missing_fields:
        missing = ", ".join(missing_fields)
        raise ValueError(f"Missing required fields in {csv_path}: {missing}")


def read_value(row: dict[str, str], field: str) -> str:
    return (row.get(field) or "").strip()


def require_value(row: dict[str, str], field: str, line_number: int) -> str:
    return require_non_empty(read_value(row, field), field, line_number)


def require_non_empty(value: str, field: str, line_number: int) -> str:
    if not value:
        raise ValueError(f"Missing value for {field} at line {line_number}")
    return value


def normalize_address(address: str) -> str:
    compact = unicodedata.normalize("NFKC", address)
    compact = " ".join(compact.replace("　", " ").split())
    compact = compact.replace("−", "-").replace("ー", "-").replace("―", "-")
    compact = compact.replace("‐", "-").replace("‑", "-").replace("–", "-")
    compact = compact.replace("（", "(").replace("）", ")")
    compact = compact.replace("丁目", "-").replace("番地", "-").replace("番", "-")
    compact = compact.replace("号", "")
    compact = compact.replace("(1-東)", "1-東")
    compact = re.sub(r"\s+", " ", compact)
    return compact.strip()


def build_address_variants(address: str) -> list[str]:
    normalized = normalize_address(address)
    variants = [normalized]

    for candidate in progressively_strip_suffixes(normalized):
        if candidate and candidate not in variants:
            variants.append(candidate)

    return variants


def progressively_strip_suffixes(address: str) -> list[str]:
    variants: list[str] = []
    current = address

    floor_stripped = re.sub(r"(?:\s*\d+F|\s*\d+階)$", "", current).strip(" ,-")
    if floor_stripped and floor_stripped != current:
        variants.append(floor_stripped)
        current = floor_stripped

    paren_stripped = re.sub(r"\([^)]*\)", "", current).strip(" ,-")
    if paren_stripped and paren_stripped != current:
        variants.append(paren_stripped)
        current = paren_stripped

    while True:
        next_value = strip_trailing_building_segment(current)
        if not next_value or next_value == current:
            break
        variants.append(next_value)
        current = next_value

    return variants


def strip_trailing_building_segment(address: str) -> str:
    parts = address.split()
    if len(parts) > 1:
        last = parts[-1].lower()
        if any(token in last for token in BUILDING_TOKENS):
            return " ".join(parts[:-1]).strip(" ,-")

    m = re.match(r"^(.*\d[-\d]*)[^\d-]+$", address)
    if m:
        return m.group(1).strip(" ,-")

    return address


def build_unresolved_row(row: dict[str, str], address: str) -> dict[str, str]:
    return {
        "shop_id": row["shop_id"],
        "chain_code": row["chain_code"],
        "chain_name": row["chain_name"],
        "shop_name": row["shop_name"],
        "address": address,
        "payment_tags": row["payment_tags"],
        "source_url": row["source_url"],
    }


if __name__ == "__main__":
    main()
