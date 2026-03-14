from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
OUTPUT_CSV = ROOT_DIR / "data" / "smart_code" / "lawson_shop_urls_latest.csv"

LAWSON_TOP_URL = "https://www.e-map.ne.jp/p/lawson/?"


@dataclass(frozen=True)
class LawsonShopUrl:
    shop_id: str
    shop_url: str
    discovery_method: str
    notes: str = ""


def main() -> None:
    args = parse_args()

    if args.discovery_method == "placeholder":
        rows = []
    else:
        raise ValueError(f"Unsupported discovery method: {args.discovery_method}")

    write_rows(OUTPUT_CSV, rows)
    print(
        f"Wrote {len(rows)} Lawson shop URLs to {OUTPUT_CSV} "
        f"using discovery_method={args.discovery_method}."
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Collect Lawson shop detail URLs before building a full store scraper. "
            "This script is intentionally kept in a research stage."
        )
    )
    parser.add_argument(
        "--discovery-method",
        default="placeholder",
        choices=["placeholder"],
        help=(
            "URL discovery strategy. "
            "Add methods such as xhr, prefecture_index, or sitemap after investigation."
        ),
    )
    return parser.parse_args()


def write_rows(path: Path, rows: list[LawsonShopUrl]) -> None:
    fieldnames = ["shop_id", "shop_url", "discovery_method", "notes"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "shop_id": row.shop_id,
                    "shop_url": row.shop_url,
                    "discovery_method": row.discovery_method,
                    "notes": row.notes,
                }
            )


if __name__ == "__main__":
    main()
