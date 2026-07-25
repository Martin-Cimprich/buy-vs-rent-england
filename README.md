# Buy versus Rent in England, 2005–2026

**A cash-flow-matched horse race for the first-time buyer** — full replication package.

This repository contains the paper, data pipeline, simulation engine, and interactive
calculator for:

> Cimprich, M. (2026). *Buy versus Rent in England: A Cash-Flow-Matched Horse Race
> for the First-Time Buyer, 2005–2026.* Working paper, Queen Mary University of London.
> ([paper/buy-vs-rent-england-2026.pdf](paper/buy-vs-rent-england-2026.pdf))

## What the paper does

It compares, month by month from January 2005 to April 2026, a leveraged English
first-time buyer (10% deposit, 30-year mortgage at the Bank of England effective rate,
period-accurate stamp duty) against an otherwise identical renter who invests the
deposit-equivalent and every monthly cost difference in a global equity tracker
(MSCI ACWI in GBP, net of taxes and fees) — for 85 quarterly entry cohorts and each
of the nine English regions.

**Headline results**

- The race is close to a tie: buying produced greater terminal wealth in **53% of
  entry cohorts**; the disciplined renter won the single longest (2005) race by 9%.
- Entry conditions dominate: the **price-to-rent ratio and mortgage rate at purchase
  explain 74%** of the cross-cohort variation in outcomes.
- **Leverage is what keeps buying competitive** — an all-cash buyer never beats the renter.
- The official national price-to-rent ratio (UK HPI price ÷ ONS PIPR rent) is **biased
  below every region's ratio** because the two aggregates weight regions differently;
  the paper builds a composition-consistent representative dwelling instead.
- At April 2026 conditions, England needs only ≈**1% annual house-price growth** for
  buying to break even against a conservatively parameterised equity investor.

## Repository map

| Path | Contents |
|---|---|
| `paper/` | Working-paper PDF and full LaTeX source |
| `code/` | Python pipeline: engine (`uk_horse_race_v2.py`), data prep, analysis run, figures |
| `code/tests/` | Engine unit + regression tests |
| `data/raw/` | Raw official inputs, exact vintages used (Open Government Licence v3.0) |
| `data/clean/` | Cleaned monthly datasets built by `prep_uk_data_v2.py` |
| `output/tables/` | All result tables and `uk_key_numbers.json` (every number in the paper) |
| `calculator/` | Source of the free online calculator (single self-contained HTML) |
| `scripts/` | Fetch script for the licence-restricted financial series (see below) |

## Reproducing the paper

```bash
# 1. Python environment
pip install pandas numpy scipy matplotlib openpyxl xlrd

# 2. Fetch the two licence-restricted series (MSCI ACWI GBP, FTSE 100 ETF TR)
python scripts/fetch_financial_series.py

# 3. Build the clean datasets
python code/prep_uk_data_v2.py

# 4. Run all analyses (writes output/tables/)
python code/full_run_uk.py

# 5. Generate figures (add --journal for the paper's PDF figures)
python code/generate_uk_figures.py --journal

# 6. Compile the paper (XeLaTeX + biber)
cd paper/src && xelatex main && biber main && xelatex main && xelatex main
```

The engine is regression-tested: `python code/tests/test_uk_engine.py` verifies the
simulation against an independent implementation and 15 hand-computed SDLT cases, and
`node calculator/engine.test.mjs` verifies that the JavaScript calculator reproduces
the Python engine's results to four decimal places.

## Data and licences

- **Code:** MIT License (see `LICENSE`).
- **UK House Price Index** (HM Land Registry), **Price Index of Private Rents** (ONS),
  **Bank of England** rate series: public sector information licensed under the
  [Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/).
  The exact vintages used are archived in `data/raw/`.
- **10-year gilt yields**: OECD (CC-BY-4.0), via FRED.
- **MSCI ACWI index levels** and the **Morningstar-sourced FTSE 100 ETF series** are
  proprietary and are **not redistributed** here. `scripts/fetch_financial_series.py`
  re-downloads them from their public endpoints in about a minute, after which the
  full pipeline reproduces every number in the paper. (For the same reason, the built
  calculator with embedded return data is not committed; `calculator/build_calculator.py`
  produces it locally.)

## The calculator

A free educational tool implementing the paper's framework — forward-looking break-even
analysis, an 2005–2026 historical backtest, and regional presets — as one dependency-free
HTML file. Build it with `python calculator/build_calculator.py` after step 2 above.

## Disclaimer

This is independent academic research and an educational tool. Nothing here is
financial advice. Historical outcomes do not predict future ones.

## Citation

See [`CITATION.cff`](CITATION.cff), or:

```bibtex
@techreport{cimprich2026buyrent,
  author      = {Cimprich, Martin},
  title       = {Buy versus Rent in England: A Cash-Flow-Matched Horse Race
                 for the First-Time Buyer, 2005--2026},
  institution = {Queen Mary University of London},
  year        = {2026},
  type        = {Working Paper},
  url         = {https://github.com/Martin-Cimprich/buy-vs-rent-england}
}
```
