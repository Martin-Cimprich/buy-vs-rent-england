# Buy versus Rent in England, 2005–2026

**A cash-flow-matched horse race** — paper, replication pipeline and calculator.

> Cimprich, M. (2026). *Buy versus Rent in England: A Cash-Flow-Matched Horse Race,
> 2005–2026.* Working paper, Queen Mary University of London.
> ([paper/buy-vs-rent-england-2026.pdf](paper/buy-vs-rent-england-2026.pdf))

### ▶ [Open the calculator](https://martin-cimprich.github.io/buy-vs-rent-england/)

It runs the paper's own model in your browser, on a phone or a laptop. Nothing to install.
You can also [download the single HTML file](#the-calculator) and use it offline.

## What the paper does

It compares two ways of paying for the same home, month by month from January 2005 to
June 2026, for a typical English first-time buyer. The buyer puts down a 10% deposit on a
30-year mortgage, initially fixed for five years and refinanced as the loan amortises, and
bears transaction costs, maintenance, depreciation and period-accurate stamp duty. The
renter occupies the same dwelling at market rent and invests the deposit and purchase
costs, plus every subsequent monthly difference in housing outlays, in a global equity index
fund (MSCI ACWI in sterling). The comparison is the owner's net equity after selling costs
against the value of the renter's portfolio.

The primary design is **199 entry cohorts, one per month, each holding for exactly five
years**, roughly the tenure of a first home. The exercise is repeated at every holding period
from one to ten years, and region by region.

## Headline results

- **There is no general financial winner.** Over the full sample renting produces
  substantially greater final wealth, leaving the renter 44% wealthier. Across five-year
  cohorts the comparison is much closer: buying produced greater terminal wealth in 102 of
  199 cohorts (51%), at a median renter-to-owner wealth ratio of 0.98 and a median gap of
  just £994 in the buyer's favour.
- **Buying does better over longer holds, but not by much.** It wins 62% of seven-year and
  61% of ten-year cohorts, yet median renter wealth stays within 8–11% of owner wealth. At
  ten years the median gap is £14,454 on a dwelling worth £319,488.
- **When you buy matters most.** Renting wins almost every cohort beginning between 2005
  and 2010, and every cohort beginning in 2016; buying wins most cohorts beginning in
  2011–2015 and again in 2017–2020. The price-to-rent ratio and mortgage rate at purchase
  jointly account for 56% of the cross-cohort variation.
- **Leverage is why buying stays competitive**, and why bad timing is so costly. Global
  equities returned 10.4% per year in sterling over the sample against house-price growth of
  3.2%, and the mortgage turns modest appreciation into a competitive return on the buyer's
  own capital. An unlevered cash buyer wins only 8% of cohorts, while the win rate peaks at
  54% with a 15–20% deposit. Eleven North East and five North West cohorts entering between
  mid-2007 and mid-2008 finished five years with negative net worth after selling costs.
- **Short holds lose on transaction costs.** Buying wins 30% of one-year cohorts; the
  round trip amounts to roughly thirty per cent of the buyer's initial outlay and takes
  about six years to amortise. The shape of the holding-period profile is a property of this
  sample — one housing crash, one long expansion of cheap credit, one exceptional global
  equity bull market — which is why the cohort comparison is not extended beyond ten years.
- **Regional outcomes differ widely**, from a 38% five-year buy-win rate in the North East
  to 63% in the West Midlands.
- **The official national price-to-rent ratio is biased.** UK HPI prices are a
  transaction-mix average while ONS PIPR rents are a tenancy-mix average dominated by London
  and the South East, so the national ratio (16.9 in June 2026) falls below the ratio of
  every individual region (17.7 to 22.4). The paper builds a composition-consistent
  representative dwelling instead, whose price and rent are the same population-weighted
  average of the nine English regions.
- **Forward-looking break-even.** The required appreciation rate is the annual house-price
  growth at which buying exactly matches renting and investing. Under June 2026 conditions a
  five-year buyer needs 2.3% per year to match a renter earning a cautious CAPE-implied 5.9%,
  and 3.2% per year to match the 10.4% equities actually returned over the sample.
- **International context.** BIS residential property prices put the UK mid-table over
  2005–2025: 95% cumulative nominal growth, 3.3% per year, against 356% in Hungary and 15%
  in Italy.

## Repository map

| Path | Contents |
|---|---|
| `paper/` | The working paper (PDF) |
| `code/` | Python pipeline: engine (`uk_horse_race_v2.py`), data prep, analysis run, figures |
| `code/tests/` | Engine unit + regression tests |
| `data/raw/` | Raw official inputs, exact vintages used (Open Government Licence v3.0) |
| `data/clean/` | Cleaned monthly datasets built by `prep_uk_data_v3.py` |
| `output/tables/` | All result tables and `uk_key_numbers.json` (every number in the paper) |
| `output/figures/` | Figures produced by the figure scripts |
| `calculator/` | The calculator: `index.html` is ready to use or download; the rest builds it |
| `index.html` | Site root, redirects to the calculator (GitHub Pages) |
| `scripts/` | Fetch script for the licence-restricted financial series (see below) |

## Reproducing the results

```bash
# 1. Python environment
pip install pandas numpy scipy matplotlib openpyxl xlrd

# 2. Fetch the two licence-restricted series (MSCI ACWI GBP, FTSE 100 ETF TR)
python scripts/fetch_financial_series.py

# 3. Build the clean datasets
python code/prep_uk_data_v3.py

# 4. Run all analyses (writes output/tables/)
python code/full_run_uk.py

# 5. Figures and the generated sensitivity table
python code/generate_paper_figures.py
python code/generate_sensitivity_tables.py
```

Every number quoted in the paper is written to `output/tables/uk_key_numbers.json`, so a
claim in the PDF can be traced to the run that produced it. The paper itself is distributed
as a PDF; its LaTeX sources are not part of this repository.

## Tests

```bash
python code/tests/test_uk_engine.py        # engine: SDLT, amortisation, end-to-end
python calculator/gen_test_fixtures.py     # regenerate the cross-language fixtures
node   calculator/engine.test.mjs          # JS calculator == Python engine
node   calculator/smoke.test.mjs           # the built HTML: wiring, defaults, self-containment
```

`test_uk_engine.py` checks 15 hand-computed stamp-duty cases against the HMRC rate tables,
an independent closed-form amortisation calculation, and then reproduces the published
headline numbers — sourced from `output/tables/uk_key_numbers.json` rather than written
inline, so an engine change that has not been carried into the results fails the suite.

`engine.test.mjs` verifies that the JavaScript calculator reproduces the Python engine. Its
expectations live in `calculator/engine.fixtures.json`, generated by `gen_test_fixtures.py`.
The two engines currently agree on the five-year cohort statistics to five decimal places
and on the cohort and win counts exactly.

`smoke.test.mjs` checks the built `index.html` rather than the engine: that it carries no
external scripts or stylesheets and so works from a download with no network, that every
form control is wired to a recompute, that the defaults are the paper's baseline, and that
the chart sizing cannot bake in a stale width.

## The calculator

**Use it in a browser:** https://martin-cimprich.github.io/buy-vs-rent-england/

**Or keep a copy.** It is one HTML file with no dependencies, so it works offline. Open
[`calculator/index.html`](https://github.com/Martin-Cimprich/buy-vs-rent-england/blob/main/calculator/index.html)
and use GitHub's **Download raw file** button (the ⤓ icon, top right of the file view), then
double-click the saved file. That is the whole installation.

It runs the same engine as the paper rather than a simplified version, and
`engine.test.mjs` is what backs that claim. Forward-looking break-even analysis, a 2005–2026
historical backtest on the paper's five-year cohort design, and regional presets.

To rebuild it after changing the engine or refreshing the data:

```bash
python calculator/build_calculator.py     # rewrites calculator/index.html
```

The mortgage side offers the baseline five-year fix (repriced by current loan-to-value), a
two-year fix, and the floating effective rate on all new advances, which after maintenance is
the parameter that moves the historical answer most.

## Data and licences

- **Code:** MIT License (see `LICENSE`).
- **UK House Price Index** (HM Land Registry), **Price Index of Private Rents** (ONS),
  **Bank of England** rate series: public sector information licensed under the
  [Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/).
  The exact vintages used are archived in `data/raw/`.
- **10-year gilt yields**: OECD (CC-BY-4.0), via FRED.
- **MSCI ACWI** and **FTSE 100** index *levels* are proprietary and are not included.
  `scripts/fetch_financial_series.py` re-downloads them from their public endpoints in
  about a minute, after which the full pipeline reproduces every number in the paper.
  What the repository does publish is the *derived* monthly total-return series in
  `output/tables/` and inside the built calculator. That series is a transformation of the
  index rather than the index itself, and it is in any case already implied by the
  month-by-month portfolio paths in `output/tables/uk_single_start_paths.csv`, which is
  what makes the published results checkable.

## Disclaimer

This is independent academic research and an educational tool. Nothing here is financial
advice. Historical outcomes do not predict future ones.

## Citation

See [`CITATION.cff`](CITATION.cff), or:

```bibtex
@techreport{cimprich2026buyrent,
  author      = {Cimprich, Martin},
  title       = {Buy versus Rent in England: A Cash-Flow-Matched Horse Race, 2005--2026},
  institution = {Queen Mary University of London},
  year        = {2026},
  type        = {Working Paper},
  url         = {https://github.com/Martin-Cimprich/buy-vs-rent-england}
}
```
