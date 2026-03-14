from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
INPUT_CSV = ROOT_DIR / "data" / "shops_geocoded.csv"
OUTPUT_JSON = ROOT_DIR / "data" / "shops.json"
PREFECTURES_DIR = ROOT_DIR / "data" / "prefectures"
PREFECTURE_INDEX_JSON = PREFECTURES_DIR / "index.json"
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
PREFECTURE_CODES = {
    "北海道": "hokkaido",
    "青森県": "aomori",
    "岩手県": "iwate",
    "宮城県": "miyagi",
    "秋田県": "akita",
    "山形県": "yamagata",
    "福島県": "fukushima",
    "茨城県": "ibaraki",
    "栃木県": "tochigi",
    "群馬県": "gunma",
    "埼玉県": "saitama",
    "千葉県": "chiba",
    "東京都": "tokyo",
    "神奈川県": "kanagawa",
    "新潟県": "niigata",
    "富山県": "toyama",
    "石川県": "ishikawa",
    "福井県": "fukui",
    "山梨県": "yamanashi",
    "長野県": "nagano",
    "岐阜県": "gifu",
    "静岡県": "shizuoka",
    "愛知県": "aichi",
    "三重県": "mie",
    "滋賀県": "shiga",
    "京都府": "kyoto",
    "大阪府": "osaka",
    "兵庫県": "hyogo",
    "奈良県": "nara",
    "和歌山県": "wakayama",
    "鳥取県": "tottori",
    "島根県": "shimane",
    "岡山県": "okayama",
    "広島県": "hiroshima",
    "山口県": "yamaguchi",
    "徳島県": "tokushima",
    "香川県": "kagawa",
    "愛媛県": "ehime",
    "高知県": "kochi",
    "福岡県": "fukuoka",
    "佐賀県": "saga",
    "長崎県": "nagasaki",
    "熊本県": "kumamoto",
    "大分県": "oita",
    "宮崎県": "miyazaki",
    "鹿児島県": "kagoshima",
    "沖縄県": "okinawa",
}


def main() -> None:
    category_labels = load_category_labels(CATEGORY_MASTER_CSV)
    chain_categories = load_chain_categories(CHAINS_MASTER_CSV)
    shops, skipped_count = load_shops(INPUT_CSV, chain_categories, category_labels)
    PREFECTURES_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(
        json.dumps(shops, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    write_prefecture_json(shops, category_labels)
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
            address = require_value(row, "address", index)
            prefecture = extract_prefecture(address)
            shops.append(
                {
                    "id": shop_id,
                    "chainCode": chain_code,
                    "chain": require_value(row, "chain_name", index),
                    "name": require_value(row, "shop_name", index),
                    "address": address,
                    "lat": parse_float(lat_value, "lat", index),
                    "lng": parse_float(lng_value, "lng", index),
                    "prefecture": prefecture,
                    "prefectureCode": prefecture_code(prefecture),
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


def extract_prefecture(address: str) -> str:
    for prefecture in PREFECTURE_CODES:
        if address.startswith(prefecture):
            return prefecture
    return ""


def prefecture_code(prefecture: str) -> str:
    return PREFECTURE_CODES.get(prefecture, "unknown")


def write_prefecture_json(
    shops: list[dict[str, object]], category_labels: dict[str, str]
) -> None:
    for path in PREFECTURES_DIR.glob("*.json"):
        path.unlink()

    prefecture_groups: dict[str, list[dict[str, object]]] = {}
    for shop in shops:
        code = str(shop.get("prefectureCode") or "unknown")
        prefecture_groups.setdefault(code, []).append(shop)

    index_rows = []
    for code, group in sorted(prefecture_groups.items()):
        output_path = PREFECTURES_DIR / f"{code}.json"
        output_path.write_text(
            json.dumps(group, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        index_rows.append(
            {
                "code": code,
                "name": str(group[0].get("prefecture") or ""),
                "file": f"./{code}.json",
                "count": len(group),
                "minLat": min(float(shop["lat"]) for shop in group),
                "maxLat": max(float(shop["lat"]) for shop in group),
                "minLng": min(float(shop["lng"]) for shop in group),
                "maxLng": max(float(shop["lng"]) for shop in group),
            }
        )

    categories = [
        {"value": code, "label": label}
        for code, label in sorted(category_labels.items(), key=lambda item: item[1])
        if code
    ]
    PREFECTURE_INDEX_JSON.write_text(
        json.dumps(
            {
                "totalShops": len(shops),
                "prefectures": index_rows,
                "categories": categories,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
