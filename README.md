# Buy versus Rent in England, 2005–2026

**A cash-flow-matched horse race for the first-time buyer** — full replication package.

This repository contains the paper, data pipeline, simulation engine, and interactive
calculator for:

> Cimprich, M. (2026). *Buy versus Rent in England: A Cash-Flow-Matched Horse Race
> for the First-Time Buyer, 2005–2026.* Working paper, Queen Mary University of London.
> ([paper/buy-vs-rent-england-2026.pdf](paper/buy-vs-rent-england-2026.pdf))

## What the paper does

It compares, month by month from January 2005 to June 2026 (258 months), a leveraged
English first-time buyer against an otherwise identical renter who invests the
deposit-equivalent and every monthly cost difference in a global equity tracker
(MSCI ACWI in GBP, net of taxes and fees).

The buyer is calibrated to what an English first-time buyer typically does: a 10%
deposit and a 30-year term, both at the regulator's median; a five-year fixed rate at
90% loan-to-value, **repriced at each refix by the loan-to-value the borrower has
amortised down to**; maintenance and depreciation of 1.5% of value per year, from the
national accounts; 1.2% purchase and 1.8% selling costs; and period-accurate
first-time-buyer stamp duty.

The primary design is **199 entry cohorts, one per month, each holding for exactly five
years** — roughly how long a first-time buyer keeps a first home. The exercise is
repeated at every holding period from one to ten years, and region by region.

**Headline results**

- **The two strategies were financially comparable, and not only at five years.** Over
  five-year holds buying produced greater terminal wealth in 102 of 199 cohorts (51%),
  at a median renter/owner wealth ratio of 0.98 and a median gap of £994 in the buyer's
  favour. At seven and ten years buying won more often (62% and 61%), but the median
  renter still finished within 8–11% of the owner: £14,454 short over a decade on a
  £319,488 dwelling.
- **Buying won more often; renting won bigger.** The mean five-year wealth ratio is
  1.22 against a median of 0.98, because renting's large proportional wins fall in
  cohorts where the owner's equity had collapsed — the November 2007 cohort finished at
  a ratio of 4.17 on an owner net worth of £15,769. The mean *pound* gap runs the other
  way, £1,744 in the owner's favour, because buying's wins landed on much larger
  balance sheets. Both statistics are reported throughout; the ratio alone overstates
  renting's case.
- **Timing decides it.** Renting won every cohort entering in 2006, 2007, 2008, 2009 and
  2016; buying won every cohort entering in 2011, 2012, 2013, 2018 and 2019.
- **Leverage is what makes ownership competitive**, and what makes bad timing
  catastrophic. Global equities returned 10.4% per year in sterling over the sample
  against the representative dwelling's 3.2%, and the mortgage closes that gap: an
  unlevered cash buyer wins only 8% of cohorts. But more is not better — buying does
  best at a 15–20% deposit — and eleven North East and five North West cohorts entering
  in 2007–08 ended five years with negative net worth after selling costs.
- **The official national price-to-rent ratio is biased.** UK HPI prices are
  transaction-weighted while ONS PIPR rents are tenancy-weighted, so the national ratio
  (16.9 in June 2026) falls *below every English region* (17.7–22.4) and flatters
  ownership. The paper builds a composition-consistent representative dwelling instead,
  whose price and rent are the same population-weighted average of the nine regions.
- **Entry conditions determine the outcome without forecasting it.** The price-to-rent
  ratio and mortgage rate at purchase jointly account for 56% of cross-cohort variation,
  but the same two variables account for 97% in a counterfactual with nothing to
  forecast, a circular-shift null already delivers a median R² of 0.29, and out of
  sample the model does worse than the historical mean.
- **Looking forward**, at June 2026 conditions the representative dwelling needs 2.3%
  annual appreciation over five years to match a global equity portfolio earning a
  cautious CAPE-implied 5.9%, and 3.2% to match one earning the 10.4% the same portfolio
  delivered over the sample. Realised appreciation was 3.2%, so the two assumptions
  bracket the historical outcome and a single break-even figure would make the case look
  settled when it is not.

## Repository map

| Path | Contents |
|---|---|
| `paper/` | Working-paper PDF and full LaTeX source |
| `code/` | Python pipeline: engine (`uk_horse_race_v2.py`), data prep, analysis run, figures |
| `code/tests/` | Engine unit + regression tests |
| `data/raw/` | Raw official inputs, exact vintages used (Open Government Licence v3.0) |
| `data/clean/` | Cleaned monthly datasets built by `prep_uk_data_v3.py` |
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
python code/prep_uk_data_v3.py

# 4. Run all analyses (writes output/tables/)
python code/full_run_uk.py
python code/ftb_matched_robustness.py

# 5. Generate the paper's figures and its sensitivity tables
python code/generate_paper_figures.py
python code/generate_sensitivity_tables.py

# 6. Compile the paper (XeLaTeX + biber)
cd paper/src && xelatex main && biber main && xelatex main && xelatex main
```

`code/generate_uk_figures.py` produces an alternative colour PNG set into
`output/figures/` for web use; the paper uses `generate_paper_figures.py`.

## Tests

```bash
python code/tests/test_uk_engine.py        # engine: SDLT, amortisation, end-to-end
python calculator/gen_test_fixtures.py     # regenerate the cross-language fixtures
node   calculator/engine.test.mjs          # JS calculator == Python engine
```

`test_uk_engine.py` checks 15 hand-computed stamp-duty cases against the HMRC rate
tables, an independent closed-form amortisation calculation, and then reproduces the
published headline numbers — sourced from `output/tables/uk_key_numbers.json` rather
than written inline, so an engine change that has not been carried into the paper fails
the suite.

`engine.test.mjs` verifies that the JavaScript calculator reproduces the Python engine.
Its expectations live in `calculator/engine.fixtures.json`, generated by
`gen_test_fixtures.py`. The two engines currently agree on the five-year cohort
statistics to five decimal places and on the cohort and win counts exactly.

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
analysis, a 2005–2026 historical backtest with the paper's five-year cohort design, and
regional presets — as one dependency-free HTML file. Build it with:

```bash
python calculator/build_calculator.py     # writes calculator/index.html
```

The mortgage side offers the baseline five-year fix (repriced by current loan-to-value),
a two-year fix, and the floating effective rate on all new advances, which is the single
parameter that moves the historical answer most after maintenance.

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
