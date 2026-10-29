"""Collects apartment-for-sale listings in Astana from krisha.kz.

Usage:
    python -m src.scraper --pages 300            # ~6,000 listings, ~15 minutes
    python -m src.scraper --pages 50 --start 51  # continue from page 51

The scraper is polite: it waits between requests, retries on errors and stops
at the first empty page. Progress is saved every 25 pages, so an interrupted
run does not lose data.
"""
from __future__ import annotations

import argparse
import random
import time
from datetime import date
from pathlib import Path

import pandas as pd
import requests

from src.parse import parse_page

BASE_URL = "https://krisha.kz/prodazha/kvartiry/astana/"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9",
}
RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"


def fetch(session: requests.Session, page: int, retries: int = 3) -> str | None:
    params = {"page": page} if page > 1 else None
    for attempt in range(1, retries + 1):
        try:
            r = session.get(BASE_URL, params=params, headers=HEADERS, timeout=20)
            if r.status_code == 200:
                return r.text
            print(f"  page {page}: HTTP {r.status_code}, attempt {attempt}")
        except requests.RequestException as e:
            print(f"  page {page}: {e.__class__.__name__}, attempt {attempt}")
        time.sleep(5 * attempt)
    return None


def scrape(pages: int, start: int = 1, delay: tuple[float, float] = (1.5, 3.5)) -> Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    today = date.today()
    out = RAW_DIR / f"krisha_astana_{today:%Y%m%d}_p{start}-{start + pages - 1}.csv"
    rows: list[dict] = []

    with requests.Session() as session:
        for page in range(start, start + pages):
            html = fetch(session, page)
            if html is None:
                print(f"Page {page} failed to load, stopping.")
                break
            cards = parse_page(html, scraped_on=today)
            if not cards:
                print(f"Page {page} is empty, no more listings.")
                break
            rows.extend(cards)
            print(f"page {page}: +{len(cards)} (total {len(rows)})")
            if page % 25 == 0:
                pd.DataFrame(rows).to_csv(out, index=False)
            time.sleep(random.uniform(*delay))

    df = pd.DataFrame(rows).drop_duplicates("id")
    df.to_csv(out, index=False)
    print(f"Saved {len(df)} listings -> {out}")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pages", type=int, default=300, help="number of pages to collect (~20 listings each)")
    ap.add_argument("--start", type=int, default=1, help="page to start from")
    args = ap.parse_args()
    scrape(args.pages, args.start)
