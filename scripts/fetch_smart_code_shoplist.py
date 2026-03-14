from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup


ROOT_DIR = Path(__file__).resolve().parents[1]
CACHE_DIR = ROOT_DIR / "data" / "_cache" / "smart_code"
OUTPUT_DIR = ROOT_DIR / "data" / "smart_code"
SOURCE_URL = "https://www.smart-code.jp/shoplist/"
LATEST_HTML = CACHE_DIR / "shoplist_latest.html"
LATEST_CSV = OUTPUT_DIR / "chains_latest.csv"
CSV_FIELDS = ("snapshot_date", "section_name", "chain_name")
USER_AGENT = "wesmo-map/0.1.0 (smart-code snapshot)"


def main() -> None:
    html = fetch_html(SOURCE_URL)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    snapshot_date = datetime.now().strftime("%Y-%m-%d")
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    snapshot_path = CACHE_DIR / f"shoplist_{timestamp}.html"
    snapshot_path.write_text(html, encoding="utf-8")
    LATEST_HTML.write_text(html, encoding="utf-8")

    rows = extract_chain_rows(html, snapshot_date)
    write_csv(LATEST_CSV, rows)

    print(f"Saved HTML snapshot to {snapshot_path}")
    print(f"Wrote {len(rows)} chains to {LATEST_CSV}")


def fetch_html(url: str) -> str:
    response = requests.get(
        url,
        timeout=30,
        headers={"User-Agent": USER_AGENT},
    )
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    return response.text


def extract_chain_rows(html: str, snapshot_date: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    section = soup.select_one("section .sec-shoplist")
    if section is None:
        raise ValueError("Could not find `.sec-shoplist` in Smart Code shoplist page")

    rows: list[dict[str, str]] = []
    for accordion in section.select(".orderBlock.p-accordion_wrap"):
        section_name = extract_section_name(accordion)
        for body in accordion.select(".p-accordion_body"):
            for name_node in body.select(".shopCard .shopCard--item .shopCard--shopName"):
                chain_name = normalize_text(name_node.get_text())
                if not chain_name:
                    continue
                rows.append(
                    {
                        "snapshot_date": snapshot_date,
                        "section_name": section_name,
                        "chain_name": chain_name,
                    }
                )

    deduped = {(row["section_name"], row["chain_name"]): row for row in rows}
    return sorted(
        deduped.values(),
        key=lambda row: (row["section_name"], row["chain_name"]),
    )


def extract_section_name(accordion) -> str:
    header = accordion.select_one(".orderBlock--title.p-accordion_button")
    if header is None:
        return ""
    return normalize_text(header.get_text())


def normalize_text(value: str) -> str:
    return " ".join(value.replace("\u3000", " ").split())


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
