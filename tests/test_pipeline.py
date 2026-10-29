"""Parser and cleaning tests. Run: pytest   (or: python tests/test_pipeline.py)"""
from datetime import date
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.parse import parse_page, parse_preview, parse_title  # noqa: E402
from src.clean import clean, normalize_district, group_condition  # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures" / "krisha_page_sample.html"


def rows():
    return parse_page(FIXTURE.read_text(encoding="utf-8"), scraped_on=date(2026, 10, 27))


def test_parses_all_cards():
    assert [r["id"] for r in rows()] == ["1001", "1002", "1003", "1004"]


def test_card_fields():
    r = rows()[0]
    assert r["price_kzt"] == 67_700_000
    assert (r["rooms"], r["area_m2"], r["floor"], r["floors_total"]) == (3, 89.5, 6, 8)
    assert r["district_raw"] == "Есильский р-н"
    assert r["address"] == "Турар Рыскулов 24а"
    assert r["complex_name"] == "ABYROI"
    assert r["house_type"] == "кирпичный"
    assert r["year_built"] == 2026
    assert r["condition"] == "черновая отделка"
    assert r["ceiling_m"] == 3.0
    assert r["is_mortgaged"] and r["is_urgent"]
    assert r["owner_type"] == "Крыша Агент"
    assert r["views"] == 98


def test_missing_district_and_old_title_format():
    r3, r4 = rows()[2], rows()[3]
    assert r3["district_raw"] is None and r3["address"] == "Ахмет Байтурсынулы 10/3"
    assert parse_title("1-комнатная квартира, 38 м², 1/5 этаж")["area_m2"] == 38
    assert r4["house_type"] == "панельный" and r4["condition"] == "требует ремонта"


def test_title_without_floor():
    assert parse_title("2-комнатная квартира · 44 м²") == {
        "rooms": 2, "area_m2": 44.0, "floor": None, "floors_total": None}


def test_malformed_ceiling_does_not_crash():
    # real case from krisha.kz: "потолки" followed by punctuation instead of a number
    for text in ["потолки .м", "потолки ,м", "потолки 2,7м.", "потолки 3.м"]:
        parse_preview(text)
    assert parse_preview("потолки .м")["ceiling_m"] is None
    assert parse_preview("потолки 2,7м.")["ceiling_m"] == 2.7
    assert parse_preview("потолки 3.м")["ceiling_m"] == 3.0


def test_bad_card_is_skipped_not_fatal():
    html = FIXTURE.read_text(encoding="utf-8").replace("потолки 3м.", "потолки .м")
    assert len(parse_page(html)) == 4


def test_normalizers():
    assert normalize_district("Есильский р-н") == "Esil"
    assert normalize_district("Нура р-н") == "Nura"
    assert normalize_district("Алматинский р-н") == "Almaty"
    assert group_condition("свежий ремонт") == "good renovation"
    assert group_condition("черновая отделка") == "shell / no finish"


def test_clean_features():
    df = clean(pd.DataFrame(rows() * 2), verbose=False)  # duplicates must be dropped
    assert len(df) == 4
    by_id = df.set_index("id")
    assert by_id.loc["1001", "bank"] == "left"
    assert by_id.loc["1002", "bank"] == "right"
    assert by_id.loc["1001", "house_type"] == "brick"
    assert by_id.loc["1004", "floor_cat"] == "first"
    assert by_id.loc["1001", "build_era"].startswith("new build")
    assert by_id.loc["1004", "build_era"] == "before 1990"
    assert abs(by_id.loc["1002", "price_per_m2"] - 28_500_000 / 60.2) < 1


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok ", name)
