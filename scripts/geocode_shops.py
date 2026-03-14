"""Geocode shop rows into `shops_geocoded.csv`.

The script reads merged shop rows, applies provider-specific geocoding with
cache reuse, writes updated coordinates, and emits unresolved rows for later
manual review.
"""

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
MIN_MATCH_RATIO = 0.3
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
FACILITY_HINT_TOKENS = (
    "内",
    "モール",
    "SC",
    "タウン",
    "パーク",
    "1F",
    "2F",
    "3F",
    "4F",
    "5F",
    "1階",
    "2階",
    "3階",
    "4階",
    "5階",
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
CHAIN_VARIANT_BUILDERS = {
    "nishimatsuya": ("facility_trimmed",),
}


def main() -> None:
    """Run the geocoding pipeline for the requested shop subset."""
    args = parse_args()
    raw_rows = load_raw_rows(RAW_CSV)
    existing_geocoded = load_existing_geocoded(GEOCODED_CSV)
    filtered_rows = filter_rows(raw_rows, args.only_chain, args.limit, args.offset)
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
        previous = existing_geocoded.get(row["shop_id"], {})
        lat = row["lat"] or previous.get("lat", "")
        lng = row["lng"] or previous.get("lng", "")

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
            result = geocode_address(
                address, row["chain_code"], args.provider, args.sleep_seconds
            )
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
    """Parse command-line arguments for the geocoding workflow.

    Returns:
        Parsed CLI arguments.
    """
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
        "--offset",
        type=int,
        default=0,
        help="Skip the first N shops after filtering.",
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
    """Load and validate merged raw shop rows.

    Args:
        csv_path: Path to `shops_raw.csv`.

    Returns:
        Normalized rows.

    Raises:
        ValueError: If headers, required values, or duplicate ids are invalid.
    """
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
    rows: list[dict[str, str]],
    only_chain: str | None,
    limit: int | None,
    offset: int,
) -> list[dict[str, str]]:
    """Filter rows by chain and chunk arguments.

    Args:
        rows: Candidate rows.
        only_chain: Optional chain code filter.
        limit: Optional maximum number of rows after filtering.
        offset: Number of filtered rows to skip.

    Returns:
        Filtered rows.
    """
    filtered = rows
    if only_chain:
        filtered = [row for row in filtered if row["chain_code"] == only_chain]
    if offset:
        filtered = filtered[offset:]
    if limit is not None:
        filtered = filtered[:limit]
    return filtered


def load_cache(
    csv_path: Path, skip_cache: bool
) -> dict[str, dict[str, str]]:
    """Load cached geocoding results.

    Args:
        csv_path: Cache CSV path.
        skip_cache: Whether to ignore existing cache contents.

    Returns:
        Cache rows keyed by normalized address.
    """
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


def load_existing_geocoded(csv_path: Path) -> dict[str, dict[str, str]]:
    """Load existing geocoded rows to preserve prior results outside the chunk.

    Args:
        csv_path: Existing geocoded CSV path.

    Returns:
        Existing rows keyed by `shop_id`.
    """
    if not csv_path.exists():
        return {}

    with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        validate_header(reader.fieldnames, OUTPUT_FIELDS, csv_path)
        existing: dict[str, dict[str, str]] = {}
        for row in reader:
            shop_id = read_value(row, "shop_id")
            if not shop_id:
                continue
            existing[shop_id] = {field: read_value(row, field) for field in OUTPUT_FIELDS}
        return existing


def initialize_provider(provider: str) -> None:
    """Initialize the selected geocoding provider.

    Args:
        provider: Provider name.
    """
    if provider == "jageocoder":
        jageocoder.init(url=JAGEOCODER_SERVER_URL)


def geocode_address(
    address: str, chain_code: str, provider: str, sleep_seconds: float
) -> tuple[str, str] | None:
    """Geocode a single normalized address.

    Args:
        address: Address string to geocode.
        chain_code: Chain code used for chain-specific normalization variants.
        provider: Geocoding provider name.
        sleep_seconds: Sleep interval between provider requests.

    Returns:
        `(lat, lng)` strings when resolved, otherwise `None`.
    """
    if provider == "jageocoder":
        return geocode_with_jageocoder(address, chain_code, sleep_seconds)
    if provider == "nominatim":
        return geocode_with_nominatim(address, sleep_seconds)
    raise ValueError(f"Unsupported provider: {provider}")


def geocode_with_jageocoder(
    address: str, chain_code: str, sleep_seconds: float
) -> tuple[str, str] | None:
    """Resolve an address using `jageocoder`.

    Args:
        address: Normalized address.
        chain_code: Chain code for chain-specific variants.
        sleep_seconds: Sleep interval between lookups.

    Returns:
        `(lat, lng)` strings when resolved, otherwise `None`.
    """
    for query in build_address_variants(address, chain_code):
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
    """Choose the first acceptable `jageocoder` candidate.

    Args:
        result: Raw search result returned by `jageocoder.search`.
        query: Query string used to create the result.

    Returns:
        Candidate payload when acceptable, otherwise `None`.
    """
    matched = str(result.get("matched") or "")
    for candidate in result.get("candidates") or []:
        level = int(candidate.get("level") or 0)
        if level < MIN_JAGEOCODER_LEVEL:
            continue
        if candidate.get("x") == 999.9 or candidate.get("y") == 999.9:
            continue
        if matched and len(matched) / max(len(query), 1) < MIN_MATCH_RATIO:
            continue
        return candidate
    return None


def geocode_with_nominatim(
    address: str, sleep_seconds: float
) -> tuple[str, str] | None:
    """Resolve an address using Nominatim.

    Args:
        address: Normalized address.
        sleep_seconds: Sleep interval after the request.

    Returns:
        `(lat, lng)` strings when resolved, otherwise `None`.
    """
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
    """Write CSV rows to disk.

    Args:
        csv_path: Output path.
        fieldnames: Ordered CSV header.
        rows: Rows to write.
    """
    row_list = list(rows)
    with csv_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(row_list)


def validate_header(
    fieldnames: list[str] | None, required_fields: tuple[str, ...], csv_path: Path
) -> None:
    """Validate required CSV fields.

    Args:
        fieldnames: CSV header row.
        required_fields: Required field names.
        csv_path: CSV path for error reporting.

    Raises:
        ValueError: If the header is missing required fields.
    """
    if fieldnames is None:
        raise ValueError(f"CSV header is missing: {csv_path}")

    missing_fields = [field for field in required_fields if field not in fieldnames]
    if missing_fields:
        missing = ", ".join(missing_fields)
        raise ValueError(f"Missing required fields in {csv_path}: {missing}")


def read_value(row: dict[str, str], field: str) -> str:
    """Read and strip a CSV value.

    Args:
        row: Source row.
        field: Field name.

    Returns:
        Stripped field value or an empty string.
    """
    return (row.get(field) or "").strip()


def require_value(row: dict[str, str], field: str, line_number: int) -> str:
    """Read a required CSV value.

    Args:
        row: Source row.
        field: Required field name.
        line_number: CSV line number for errors.

    Returns:
        Non-empty field value.
    """
    return require_non_empty(read_value(row, field), field, line_number)


def require_non_empty(value: str, field: str, line_number: int) -> str:
    """Validate that a value is not empty.

    Args:
        value: Candidate value.
        field: Field name for errors.
        line_number: CSV line number for errors.

    Returns:
        The original non-empty value.

    Raises:
        ValueError: If the value is empty.
    """
    if not value:
        raise ValueError(f"Missing value for {field} at line {line_number}")
    return value


def normalize_address(address: str) -> str:
    """Normalize address text before geocoding.

    Args:
        address: Raw address string.

    Returns:
        Normalized address string.
    """
    compact = unicodedata.normalize("NFKC", address)
    compact = " ".join(compact.replace("　", " ").split())
    compact = compact.replace("−", "-").replace("ー", "-").replace("―", "-")
    compact = compact.replace("‐", "-").replace("‑", "-").replace("–", "-")
    compact = compact.replace("（", "(").replace("）", ")")
    compact = compact.replace("丁目", "-").replace("番地", "-").replace("番", "-")
    compact = compact.replace("号", "")
    compact = compact.replace("(1-東)", "1-東")
    compact = compact.replace("--", "-")
    compact = re.sub(r"\s*\d{1,2}/\d{1,2}\([^)]*\)をもちまして閉店致しました.*$", "", compact)
    compact = re.sub(r"\s*\d{1,2}/\d{1,2}\([^)]*\)をもちまして閉店致します.*$", "", compact)
    compact = re.sub(r"\s*永らくのご愛顧.*$", "", compact)
    compact = re.sub(r"\s+", " ", compact)
    return compact.strip()


def build_address_variants(address: str, chain_code: str = "") -> list[str]:
    """Build address variants for geocoding fallback.

    Args:
        address: Raw address string.
        chain_code: Optional chain code for chain-specific variants.

    Returns:
        Ordered candidate query strings from strict to relaxed.
    """
    normalized = normalize_address(address)
    variants = [normalized]

    for candidate in progressively_strip_suffixes(normalized):
        if candidate and candidate not in variants:
            variants.append(candidate)

    for candidate in build_chain_specific_variants(normalized, chain_code):
        if candidate and candidate not in variants:
            variants.append(candidate)

    return variants


def progressively_strip_suffixes(address: str) -> list[str]:
    """Progressively remove suffix noise such as floors and building names.

    Args:
        address: Normalized address.

    Returns:
        Relaxed variants with trailing suffixes removed step by step.
    """
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


def build_facility_trimmed_variants(address: str) -> list[str]:
    """Build variants by trimming facility-specific suffixes.

    Args:
        address: Normalized address.

    Returns:
        Address variants without facility or floor hints.
    """
    if not any(token in address for token in FACILITY_HINT_TOKENS):
        return []

    variants: list[str] = []

    for candidate in (
        trim_after_facility_separator(address),
        trim_after_uchi_marker(address),
        trim_after_store_floor_marker(address),
    ):
        if candidate and candidate != address and candidate not in variants:
            variants.append(candidate)

    return variants


def trim_after_facility_separator(address: str) -> str:
    """Trim suffix text after a space when it looks like facility metadata.

    Args:
        address: Normalized address.

    Returns:
        Trimmed address or the original address when no trim is applied.
    """
    if " " not in address:
        return address

    prefix, suffix = address.split(" ", 1)
    if any(token in suffix for token in FACILITY_HINT_TOKENS):
        return prefix.strip(" ,-")
    return address


def trim_after_uchi_marker(address: str) -> str:
    """Trim suffix text following facility `内` markers.

    Args:
        address: Normalized address.

    Returns:
        Trimmed address or the original address when no trim is applied.
    """
    if " " not in address or "内" not in address:
        return address

    prefix, suffix = address.split(" ", 1)
    if "内" in suffix and any(token in suffix for token in FACILITY_HINT_TOKENS):
        return prefix.strip(" ,-")
    return address


def trim_after_store_floor_marker(address: str) -> str:
    """Trim suffixes such as `店の1F`.

    Args:
        address: Normalized address.

    Returns:
        Trimmed address or the original address.
    """
    match = re.match(r"^(.*?)(?:店の\d+F|店の\d+階)$", address)
    if match:
        return match.group(1).strip(" ,-")
    return address


def strip_trailing_building_segment(address: str) -> str:
    """Drop trailing building-like segments from an address.

    Args:
        address: Normalized address.

    Returns:
        Trimmed address or the original address.
    """
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
    """Build a row for `geocode_unresolved.csv`.

    Args:
        row: Source shop row.
        address: Normalized address used for the failed lookup.

    Returns:
        Unresolved-row payload.
    """
    return {
        "shop_id": row["shop_id"],
        "chain_code": row["chain_code"],
        "chain_name": row["chain_name"],
        "shop_name": row["shop_name"],
        "address": address,
        "payment_tags": row["payment_tags"],
        "source_url": row["source_url"],
    }


def build_chain_specific_variants(address: str, chain_code: str) -> list[str]:
    """Build chain-specific relaxed address variants.

    Args:
        address: Normalized address.
        chain_code: Chain code to inspect.

    Returns:
        Chain-specific address variants.
    """
    variants: list[str] = []

    for strategy_name in CHAIN_VARIANT_BUILDERS.get(chain_code, ()):
        if strategy_name == "facility_trimmed":
            variants.extend(build_facility_trimmed_variants(address))

    return variants


if __name__ == "__main__":
    main()
