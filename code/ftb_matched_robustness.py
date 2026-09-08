#!/usr/bin/env python3
"""
Robustness: first-time-buyer prices matched to a bedroom-matched rent.

The headline analysis uses the all-dwellings price against the all-property
rent, which is composition-consistent but not first-time-buyer-specific. This
check swaps in the UK HPI first-time-buyer price series and matches it to a
bedroom-specific PIPR rent, so both sides describe the kind of dwelling a
first-time buyer actually occupies.

Why it is a robustness check and not the headline: the FTB price series begins
January 2012 and the PIPR bedroom series January 2015, so the matched sample
starts in 2015 and loses the financial crisis and the 2010-2014 recovery -
exactly the episodes that drive the headline result.

Which bedroom category. Substituting the FTB price while keeping the
all-property rent would be an error, not a refinement: it prices a cheap
dwelling against a whole-market rent and overstates the cost of renting by
roughly the FTB discount. The category is therefore chosen on the same
composition-consistency principle used for the representative dwelling - the
rent whose discount to the all-property rent best matches the FTB price's
discount to the all-dwellings price - and the result is reported for the
neighbouring category too, since the choice is not clear-cut.

Writes output/tables/UK/uk_ftb_matched_robustness.csv. Does not touch the
headline pipeline.
"""
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import numpy as np
import pandas as pd

from uk_horse_race_v2 import align_monthly_data, load_uk_returns, run_rolling_fixed

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(BASE, "data", "raw")
D0708 = os.path.join(RAW, "downloaded_2026-07-08")
D0901 = os.path.join(RAW, "downloaded_2026-09-01")
CLEAN = os.path.join(BASE, "data", "clean")
OUT = os.path.join(BASE, "output", "tables")

REGIONS = ['North East', 'North West', 'Yorkshire and The Humber',
           'East Midlands', 'West Midlands', 'East of England',
           'London', 'South East', 'South West']
CODES = {'E92000001': 'England', 'E12000001': 'North East',
         'E12000002': 'North West', 'E12000003': 'Yorkshire and The Humber',
         'E12000004': 'East Midlands', 'E12000005': 'West Midlands',
         'E12000006': 'East of England', 'E12000007': 'London',
         'E12000008': 'South East', 'E12000009': 'South West'}
START, END = pd.Timestamp('2015-01-31'), pd.Timestamp('2026-06-30')
HORIZON = 60


def month_end(s):
    return pd.to_datetime(s).dt.to_period('M').dt.to_timestamp('M')


def main():
    # ---- FTB prices (UK HPI full file, current vintage; FTB series from 2012-01)
    ftb = pd.read_csv(os.path.join(D0901, "UKHPI_full_file_2026-06.csv"),
                      usecols=['Date', 'RegionName', 'FTBPrice'],
                      parse_dates=['Date'], dayfirst=True)
    ftb = ftb[ftb.RegionName.isin(['England'] + REGIONS)].copy()
    ftb['Date'] = month_end(ftb['Date'])
    ftb['FTBPrice'] = pd.to_numeric(ftb['FTBPrice'], errors='coerce')
    p_ftb = ftb.pivot_table(index='Date', columns='RegionName',
                            values='FTBPrice').sort_index().dropna(how='all')

    # ---- rents by bedroom count (PIPR, from 2015-01) ----------------------
    raw = pd.read_excel(os.path.join(D0901, "pipr_monthly_2026-08-19.xlsx"),
                        sheet_name='Table 1', header=2)
    raw = raw[raw['Area code'].isin(CODES)].copy()
    raw['Region'] = raw['Area code'].map(CODES)
    raw['Date'] = month_end(raw['Time period'])
    rents = {}
    for key, col in [('all', 'Rental price'), ('one', 'Rental price one bed'),
                     ('two', 'Rental price two bed')]:
        raw[col] = pd.to_numeric(raw[col], errors='coerce')
        rents[key] = raw.pivot_table(index='Date', columns='Region',
                                     values=col).sort_index()

    # ---- all-dwellings price, for the discount comparison -----------------
    allp = pd.read_csv(os.path.join(CLEAN, 'uk_housing_monthly_regions.csv'),
                       parse_dates=['Date'])
    allp['Date'] = month_end(allp['Date'])
    p_all = allp.pivot_table(index='Date', columns='Region', values='Price_GBP').sort_index()
    # the regional file holds only the nine regions; England comes from its own file
    _eng = pd.read_csv(os.path.join(CLEAN, 'uk_housing_monthly_england.csv'),
                       parse_dates=['Date']).set_index('Date')
    _eng.index = month_end(pd.Series(_eng.index)).values
    p_all['England'] = _eng['Purchase_Price_GBP']

    # ---- choose the bedroom category by composition consistency -----------
    # latest month all four series share, rather than assuming the sample end
    m = (p_ftb.index.intersection(p_all.index)
         .intersection(rents['all'].index).intersection(rents['one'].index)).max()
    print("Choosing the bedroom category (England, %s):" % m.strftime('%Y-%m'))
    disc_price = p_ftb.loc[m, 'England'] / p_all.loc[m, 'England']
    print("  FTB price / all-dwellings price          %.3f" % disc_price)
    for key in ('one', 'two'):
        d = rents[key].loc[m, 'England'] / rents['all'].loc[m, 'England']
        print("  %s-bed rent / all-property rent          %.3f   (gap %+0.3f)"
              % (key, d, d - disc_price))
    print("  -> one-bed is the closer match; two-bed reported alongside\n")

    # ---- run the race, both rent bases, England + regions -----------------
    ar = load_uk_returns(os.path.join(CLEAN, 'uk_stock_returns_gbp.csv'),
                         'acwi_net_ter_gbp_ret')
    rate = pd.read_csv(os.path.join(CLEAN, 'uk_housing_monthly_england.csv'),
                       parse_dates=['Date']).set_index('Date')

    # A national FTB pair must be built the same way as the headline
    # representative dwelling: a population-weighted average of the NINE regions
    # on both sides. Using the England headline aggregates instead reintroduces
    # exactly the composition mismatch Section 3 corrects - it puts the England
    # price-to-rent ratio at 17.3 against a regional range of 21.9 to 26.4, and
    # makes buying win every single cohort.
    POP = {'North East': 2.65, 'North West': 7.52, 'Yorkshire and The Humber': 5.56,
           'East Midlands': 5.02, 'West Midlands': 6.11, 'East of England': 6.40,
           'London': 8.87, 'South East': 9.46, 'South West': 5.80}
    wsum = sum(POP.values())
    p_ftb['Representative'] = sum(POP[r] / wsum * p_ftb[r] for r in REGIONS)
    for k in rents:
        rents[k]['Representative'] = sum(POP[r] / wsum * rents[k][r] for r in REGIONS)

    rows = []
    for basis in ('one', 'two', 'all'):
        for geo in ['Representative'] + REGIONS:
            df = pd.DataFrame({
                'rent_gbp': rents[basis][geo],
                'purchase_price_gbp': p_ftb[geo],
                'mortgage_rate_annual': rate['Mortgage_Rate_pct'] / 100.0,
                'rate_75_pct': rate['Rate_75LTV_pct'],
                'rate_90_pct': rate['Rate_90LTV_pct'],
                'rate_95_pct': rate['Rate_95LTV_pct'],
                'bank_rate_pct': rate['Bank_Rate_pct'],
            }).loc[START:END].dropna()
            if len(df) < HORIZON + 12:
                print("  skip %s / %s: only %d months" % (geo, basis, len(df)))
                continue
            hr, arr = align_monthly_data(df, ar)
            c = run_rolling_fixed(hr, arr, horizon_months=HORIZON)
            rows.append({
                'rent_basis': basis, 'geography': geo, 'n_cohorts': len(c),
                'first_cohort': str(c.start_date.iloc[0])[:7],
                'last_cohort': str(c.start_date.iloc[-1])[:7],
                'buy_win_pct': 100 * (c.winner == 'BUY').mean(),
                'R_median': c.R.median(),
                'gap_median_gbp': float((c.nw_rent - c.nw_buy).median()),
                'pr_ratio_latest': hr['purchase_price_gbp'].iloc[-1] / (hr['rent_gbp'].iloc[-1] * 12),
            })

    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(OUT, 'uk_ftb_matched_robustness.csv'), index=False)

    print("\nFTB price matched to each rent basis, 5-year holds, 2015-2026:")
    print(out[out.geography == 'Representative'][
        ['rent_basis', 'n_cohorts', 'first_cohort', 'last_cohort',
         'pr_ratio_latest', 'buy_win_pct', 'R_median', 'gap_median_gbp']
    ].to_string(index=False, float_format=lambda v: '%.2f' % v))
    print("\nBy region (one-bed basis):")
    print(out[out.rent_basis == 'one'][
        ['geography', 'pr_ratio_latest', 'buy_win_pct', 'R_median']
    ].to_string(index=False, float_format=lambda v: '%.2f' % v))

    with open(os.path.join(OUT, 'uk_ftb_matched_robustness.json'), 'w') as fh:
        json.dump({'sample': ['2015-01', '2026-06'], 'horizon_months': HORIZON,
                   'ftb_price_discount_to_all': float(disc_price),
                   'rows': out.to_dict('records')}, fh, indent=2, default=float)
    print("\n  -> %s" % OUT)
    return 0


if __name__ == '__main__':
    sys.exit(main())
