"""Cleaning raw listings and building features.

    python -m src.clean                 # uses every CSV in data/raw/
    python -m src.clean data/raw/x.csv  # specific files

Raw values come from krisha.kz in Russian; this module maps them to English labels.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed" / "listings_clean.csv"

# Astana districts. Left bank of the Ishim (Esil) river: Esil and Nura; right bank: the rest.
DISTRICTS = {
    "есил": "Esil",
    "нура": "Nura",
    "алматы": "Almaty",
    "алматин": "Almaty",
    "сарыарк": "Saryarka",
    "байкон": "Baikonur",
}
LEFT_BANK = {"Esil", "Nura"}

HOUSE_TYPES = {"монолитный": "monolithic", "кирпичный": "brick", "панельный": "panel", "иное": "other"}

CONDITION_GROUPS = [
    ("черн", "shell / no finish"),
    ("без отдел", "shell / no finish"),
    ("предчист", "pre-finish"),
    ("свобод", "open layout"),
    ("требует", "needs renovation"),
    ("аккурат", "average renovation"),
    ("не нов", "average renovation"),
    ("свеж", "good renovation"),
    ("евро", "good renovation"),
    ("хорош", "good renovation"),
]

ERA_ORDER = ["before 1990", "1990–2004", "2005–2014", "2015 and newer", "new build (≤2 years / under construction)"]

# Hard plausibility bounds: anything outside is almost certainly a data-entry error
BOUNDS = {"area_m2": (12, 300), "price_per_m2": (150_000, 3_500_000), "floor": (1, 60)}


def normalize_district(raw: object) -> object:
    if not isinstance(raw, str):
        return np.nan
    low = raw.lower()
    for stem, name in DISTRICTS.items():
        if stem in low:
            return name
    return np.nan


def group_condition(raw: object) -> object:
    if not isinstance(raw, str):
        return np.nan
    low = raw.lower()
    for stem, group in CONDITION_GROUPS:
        if stem in low:
            return group
    return "other"


def build_era(year: float, ref_year: int) -> object:
    if pd.isna(year):
        return np.nan
    if year >= ref_year - 1:
        return ERA_ORDER[4]
    if year >= 2015:
        return ERA_ORDER[3]
    if year >= 2005:
        return ERA_ORDER[2]
    if year >= 1990:
        return ERA_ORDER[1]
    return ERA_ORDER[0]


def floor_category(floor: float, total: float) -> object:
    if pd.isna(floor) or pd.isna(total):
        return np.nan
    if floor == 1:
        return "first"
    if floor == total:
        return "top"
    return "middle"


def clean(raw: pd.DataFrame, verbose: bool = True) -> pd.DataFrame:
    log: list[tuple[str, int]] = [("raw rows", len(raw))]
    df = raw.copy()

    df = df.drop_duplicates("id")
    log.append(("after dropping duplicate ids", len(df)))

    # the same listing re-posted under a new id
    df = df.drop_duplicates(["price_kzt", "area_m2", "floor", "floors_total", "address"])
    log.append(("after dropping re-posted copies", len(df)))

    df = df.dropna(subset=["price_kzt", "area_m2", "rooms"])
    log.append(("has price, area and rooms", len(df)))

    df["price_per_m2"] = df["price_kzt"] / df["area_m2"]
    for col, (lo, hi) in BOUNDS.items():
        df = df[df[col].isna() | df[col].between(lo, hi)]
    df = df[df["floors_total"].isna() | (df["floor"] <= df["floors_total"])]
    log.append(("after hard bounds", len(df)))

    if len(df) >= 200:  # a quantile cut only hurts on a tiny sample
        lo, hi = df["price_per_m2"].quantile([0.005, 0.995])
        df = df[df["price_per_m2"].between(lo, hi)]
        log.append(("after trimming 0.5% tails of price/m²", len(df)))

    ref_year = pd.to_datetime(df["scraped_on"]).dt.year.max()
    df["district"] = df["district_raw"].map(normalize_district)
    df["bank"] = np.where(df["district"].isin(LEFT_BANK), "left",
                          np.where(df["district"].notna(), "right", None))
    df["house_type"] = df["house_type"].map(HOUSE_TYPES)
    df["condition_group"] = df["condition"].map(group_condition)
    df["build_era"] = df["year_built"].map(lambda y: build_era(y, ref_year))
    df["building_age"] = (ref_year - df["year_built"]).clip(lower=0)
    df["floor_cat"] = [floor_category(f, t) for f, t in zip(df["floor"], df["floors_total"])]
    df["rooms_cat"] = df["rooms"].clip(upper=4).astype(int).astype(str).replace("4", "4+")
    df["is_owner"] = df["owner_type"].fillna("").str.contains("Хозяин")
    df["price_mln"] = df["price_kzt"] / 1e6
    df["ppm_k"] = df["price_per_m2"] / 1e3  # thousand KZT per m²
    df["log_ppm"] = np.log(df["price_per_m2"])

    if verbose:
        width = max(len(s) for s, _ in log)
        for step, n in log:
            print(f"{step:<{width}}  {n:>7,}")
    return df.reset_index(drop=True)


def load_raw(paths: list[Path] | None = None) -> pd.DataFrame:
    paths = paths or sorted(RAW_DIR.glob("*.csv"))
    if not paths:
        raise FileNotFoundError(f"No CSV files in {RAW_DIR}. Run first: python -m src.scraper")
    return pd.concat([pd.read_csv(p) for p in paths], ignore_index=True)


if __name__ == "__main__":
    files = [Path(p) for p in sys.argv[1:]] or None
    out = clean(load_raw(files))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False)
    print(f"-> {OUT} ({len(out):,} rows)")
