"""Parsing krisha.kz listing cards.

Pure functions with no network calls, so they are easy to test on saved HTML.
If the site changes its markup, only the SELECTORS dict needs updating.
The regular expressions match Russian text because that is the site's language.
"""
from __future__ import annotations

import re
from datetime import date

from bs4 import BeautifulSoup, Tag

SELECTORS = {
    "card": "div.a-card[data-id]",
    "title": ".a-card__title",
    "price": ".a-card__price",
    "subtitle": ".a-card__subtitle",
    "preview": ".a-card__text-preview",
    "owner": ".a-card__owner",
    "stats_item": ".a-card__stats-item",
    "views": ".a-view-count",
}

# "3-комнатная квартира · 89.5 м² · 6/8 этаж"  (older format uses commas)
TITLE_RE = re.compile(
    r"(?P<rooms>\d+)-комнатн\w*\s+квартир\w*"
    r"[\s·,]+(?P<area>\d+(?:[.,]\d+)?)\s*м²"
    r"(?:[\s·,]+(?P<floor>\d+)(?:/(?P<floors>\d+))?\s*этаж)?",
    re.IGNORECASE,
)


def _text(el: Tag | None) -> str:
    return re.sub(r"\s+", " ", el.get_text(" ", strip=True)).strip() if el else ""


def _num(s: str | None) -> float | None:
    if not s:
        return None
    digits = re.sub(r"[^\d.,]", "", s).replace(",", ".")
    try:
        return float(digits) if digits else None
    except ValueError:
        return None


def parse_title(title: str) -> dict:
    m = TITLE_RE.search(title or "")
    if not m:
        return {"rooms": None, "area_m2": None, "floor": None, "floors_total": None}
    return {
        "rooms": int(m["rooms"]),
        "area_m2": float(m["area"].replace(",", ".")),
        "floor": int(m["floor"]) if m["floor"] else None,
        "floors_total": int(m["floors"]) if m["floors"] else None,
    }


def parse_subtitle(subtitle: str) -> dict:
    """"Есильский р-н, Турар Рыскулов 24а" -> district + address. District may be missing."""
    parts = [p.strip() for p in (subtitle or "").split(",")]
    if parts and "р-н" in parts[0]:
        return {"district_raw": parts[0], "address": ", ".join(parts[1:]) or None}
    return {"district_raw": None, "address": subtitle or None}


def parse_preview(preview: str) -> dict:
    """Extracts residential complex, building type, year built, condition, ceiling, bathroom."""
    p = preview or ""

    def grab(pattern: str) -> str | None:
        m = re.search(pattern, p, re.IGNORECASE)
        return m.group(1).strip() if m else None

    ceiling = grab(r"потолки\s*([\d.,]+)\s*м")
    year = grab(r"(\d{4})\s*г\.п\.")
    return {
        "complex_name": grab(r"жил\.\s*комплекс\s+([^,]+)"),
        "house_type": grab(r"(монолитный|кирпичный|панельный|иное)\s*дом"),
        "year_built": int(year) if year else None,
        "condition": grab(r"состояние:\s*([^,]+)"),
        "ceiling_m": _num(ceiling.rstrip(".,")) if ceiling else None,
        "bathroom": grab(r"санузел\s+([^,]+)"),
        "is_mortgaged": "в залоге" in p.lower(),
    }


def parse_card(card: Tag, scraped_on: date | None = None) -> dict:
    title = _text(card.select_one(SELECTORS["title"]))
    subtitle = _text(card.select_one(SELECTORS["subtitle"]))
    preview = _text(card.select_one(SELECTORS["preview"]))
    stats = [_text(s) for s in card.select(SELECTORS["stats_item"])]
    stats = [s for s in stats if s]

    row = {
        "id": card.get("data-id"),
        "title": title,
        "price_kzt": _num(_text(card.select_one(SELECTORS["price"]))),
        **parse_title(title),
        **parse_subtitle(subtitle),
        **parse_preview(preview),
        "owner_type": _text(card.select_one(SELECTORS["owner"])) or None,
        "city": stats[0] if stats else None,
        "posted": stats[1] if len(stats) > 1 else None,
        "views": _num(_text(card.select_one(SELECTORS["views"]))),
        "is_urgent": "is-urgent" in (card.get("class") or []),
        "preview": preview,
        "scraped_on": (scraped_on or date.today()).isoformat(),
    }
    if row["price_kzt"] is not None:
        row["price_kzt"] = int(row["price_kzt"])
    return row


def parse_page(html: str, scraped_on: date | None = None) -> list[dict]:
    """Parses every card on a page. A card that fails to parse is skipped, not fatal."""
    soup = BeautifulSoup(html, "lxml")
    rows = []
    for card in soup.select(SELECTORS["card"]):
        try:
            rows.append(parse_card(card, scraped_on))
        except Exception as e:  # one malformed card must not stop the whole run
            print(f"  skipped card {card.get('data-id')}: {e.__class__.__name__}: {e}")
    return rows
