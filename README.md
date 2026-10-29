# Astana Housing Market: What Drives the Price per Square Meter

Exploratory data analysis of apartment-for-sale listings in Astana, Kazakhstan, from krisha.kz: from collecting the data with a scraper to a hedonic regression that estimates how district, building age, floor and finish affect the price per m² **all else equal**.

<!-- After running the notebook, add 2–3 key charts from reports/figures/, for example:
![Price per m² by district](reports/figures/02_districts.png)
![Effect of each factor](reports/figures/06_hedonic_effects.png)
-->

## Key findings

<!-- Fill in from the "Key numbers" table in the notebook. 3–5 bullets, each with a number. Example shape:
- **Esil is the most expensive district:** median N k KZT/m², X% above Saryarka.
- **The left-bank premium** shrinks from X% to Y% once building age is controlled for: part of the "premium" is simply new construction.
- **The first floor** is X% cheaper than a middle floor, all else equal; the top floor shows no significant difference.
-->

## Questions

1. How are prices distributed, and how wide is the spread?
2. Do districts differ, and how large is the left-bank premium?
3. How much is a newer building worth, and do monolithic, brick and panel buildings differ?
4. Is there a discount for the first and the top floor?
5. What does each factor contribute when the others are held constant?

## Data

- **Source:** public listings on krisha.kz, "Apartments for sale — Astana", search result cards.
- **Size:** <!-- N listings, collection date -->
- **Features:** price, area, rooms, floor / total floors, district, residential complex, building type, year built, condition, ceiling height.
- **Cleaning** (`src/clean.py`): duplicate ids and re-posted copies removed, implausible values filtered (area 12–300 m², price 150k–3.5M KZT/m²), 0.5% tails of price per m² trimmed. Every step logs how many rows remain. Russian values from the site are mapped to English labels.

## Methods

| Task | Method |
|---|---|
| Comparing districts | Kruskal–Wallis + ε², pairwise Mann–Whitney with Holm correction, rank-biserial r |
| Premiums (river bank, floor) | difference in medians with a 95% bootstrap interval |
| Contribution of each factor | OLS on ln(price per m²) with dummy variables, HC3 robust standard errors |

The regression and HC3 errors are implemented from scratch in numpy (`src/stats.py`): β = (XᵀX)⁻¹Xᵀy, covariance (XᵀX)⁻¹ Xᵀ diag(eᵢ²/(1−hᵢ)²) X (XᵀX)⁻¹.

## Project structure

```
├── src/
│   ├── scraper.py   # collects listings (requests + delays + retries)
│   ├── parse.py     # turns a listing card's HTML into a table row
│   ├── clean.py     # cleaning and feature engineering
│   └── stats.py     # bootstrap, tests, OLS with HC3
├── notebooks/01_eda_astana_housing.ipynb
├── tests/           # parser and cleaning tests on saved HTML
├── data/raw/        # raw CSVs (not committed)
├── data/processed/  # cleaned table
└── reports/figures/ # charts saved by the notebook
```

## How to run

```bash
python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m src.scraper --pages 300   # ~6,000 listings, ~15 minutes
python -m src.clean                 # -> data/processed/listings_clean.csv
pytest                              # parser tests
jupyter notebook notebooks/01_eda_astana_housing.ipynb
```

## Limitations

- Asking prices, not transaction prices: negotiation is not captured.
- A single snapshot in time, no dynamics.
- Overpriced listings stay online longer, so they are over-represented compared with the market.
- No coordinates or features such as view or parking.

## Data collection ethics

The scraper sends at most one request every 1.5–3.5 seconds and collects only public listing-card data, without seller contact details. Raw data is not published in this repository.
