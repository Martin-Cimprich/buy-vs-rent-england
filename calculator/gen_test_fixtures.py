#!/usr/bin/env python3
"""
Emit engine.fixtures.json: the numbers the JavaScript engine must reproduce.

The JS engine in engine.js is a hand port of code/uk_horse_race_v2.py. The two
have to agree, and the only way to know they do is to run both. This script
runs the Python engine and writes its answers to JSON; engine.test.mjs reads
that JSON and asserts the JS engine matches.

Fixtures are GENERATED, never hand-typed. The previous version of the test
carried its expectations as literals, and when the baseline was recalibrated
(five-year fix repriced by loan-to-value, 1.2% purchase and 1.8% selling costs)
the literals silently described a specification the engine no longer ran.

Run:  python calculator/gen_test_fixtures.py
Then: node calculator/engine.test.mjs
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'code'))

import pandas as pd  # noqa: E402

from uk_horse_race_v2 import (  # noqa: E402
    BASE_SPEC, align_monthly_data, forward_rar, load_uk_housing,
    load_uk_returns, run_rolling_fixed, sdlt_england, sim_pair,
)

CLEAN = os.path.join(ROOT, 'data', 'clean')
REP = os.path.join(CLEAN, 'uk_housing_monthly_representative.csv')
RET = os.path.join(CLEAN, 'uk_stock_returns_gbp.csv')

# Must match build_calculator.py, or the JS sees a different window.
START, END = '2005-01-31', '2026-06-30'

# The cautious CAPE-implied equity return used for the forward break-even.
EQUITY_OPP = 0.0588
RENT_GROWTH = 0.03


def main():
    housing = load_uk_housing(REP, start=START, end=END)
    returns = load_uk_returns(RET, 'acwi_net_ter_gbp_ret')
    ha, ar = align_monthly_data(housing, returns)

    fx = {
        'generated_from': 'code/uk_horse_race_v2.py',
        'window': {'start': START, 'end': END},
        'baseline': {k: v for k, v in BASE_SPEC.items()},
        'rent_growth_annual': RENT_GROWTH,
        'equity_opportunity_annual': EQUITY_OPP,
        'months': int(len(ha)),
    }

    # --- 1. SDLT spot checks across every schedule change in the sample ------
    cases = [
        (153030, '2008-02-28'), (153030, '2008-10-31'), (180000, '2009-06-30'),
        (200000, '2011-06-30'), (220000, '2013-06-30'), (220000, '2015-06-30'),
        (290000, '2019-06-30'), (310000, '2022-02-28'), (310000, '2023-12-31'),
        (310000, '2025-06-30'), (560000, '2019-06-30'), (560000, '2020-10-31'),
        (100000, '2005-02-28'), (100000, '2005-06-30'), (450000, '2023-06-30'),
    ]
    fx['sdlt'] = [
        {'price': p, 'date': d, 'expected': round(float(sdlt_england(p, pd.Timestamp(d))), 2)}
        for p, d in cases
    ]

    # --- 2. One long hold, January 2005 to the end of the sample ------------
    buy, rent = sim_pair(ha, ar, 0, **dict(BASE_SPEC))
    fx['single'] = {
        'R': round(rent['net_worth'] / buy['net_worth'], 6),
        'nw_buy': round(float(buy['net_worth']), 2),
        'nw_rent': round(float(rent['net_worth']), 2),
        'sdlt': round(float(buy['sdlt_paid']), 2),
        'purchase_price': round(float(buy['purchase_price']), 2),
    }

    # --- 3. The headline design: fixed five-year holds, monthly starts ------
    coh = run_rolling_fixed(ha, ar, horizon_months=60)
    gap = coh.nw_rent - coh.nw_buy
    fx['cohorts_5y'] = {
        'n': int(len(coh)),
        'buy_wins': int((coh.winner == 'BUY').sum()),
        'R_median': round(float(coh.R.median()), 6),
        'R_mean': round(float(coh.R.mean()), 6),
        'R_min': round(float(coh.R.min()), 6),
        'R_max': round(float(coh.R.max()), 6),
        'gap_median_gbp': round(float(gap.median()), 2),
        'nw_buy_min_gbp': round(float(coh.nw_buy.min()), 2),
    }
    coh10 = run_rolling_fixed(ha, ar, horizon_months=120)
    fx['cohorts_10y'] = {
        'n': int(len(coh10)),
        'buy_wins': int((coh10.winner == 'BUY').sum()),
        'R_median': round(float(coh10.R.median()), 6),
    }

    # --- 4. Forward-looking required appreciation, end-of-sample conditions --
    last = ha.iloc[-1]
    price_now = float(last['purchase_price_gbp'])
    rent_now = float(last['rent_gbp'])
    rate_now = float(last['mortgage_rate_annual'])
    sdlt_now = float(sdlt_england(price_now, ha.index[-1]))
    fwd_kw = dict(deposit_share=BASE_SPEC['deposit_share'],
                  amort_years=BASE_SPEC['amort_years'],
                  maint_pct=BASE_SPEC['maintenance_pct_of_value'],
                  purchase_costs_pct=BASE_SPEC['purchase_costs_pct'],
                  selling_costs_pct=BASE_SPEC['selling_costs_pct'],
                  rent_growth_annual=RENT_GROWTH)
    fx['forward'] = {
        'price_now': round(price_now, 2),
        'rent_now': round(rent_now, 2),
        'rate_now': round(rate_now, 6),
        'sdlt_now': round(sdlt_now, 2),
        'rar': {str(h): round(float(forward_rar(price_now, rent_now, rate_now,
                                                EQUITY_OPP, horizon_years=h,
                                                sdlt_gbp=sdlt_now, **fwd_kw)), 6)
                for h in (3, 5, 7, 10)},
    }

    out = os.path.join(HERE, 'engine.fixtures.json')
    io.open(out, 'w', encoding='utf-8', newline='\n').write(
        json.dumps(fx, indent=2) + '\n')
    print('wrote %s' % out)
    print('  months            %d' % fx['months'])
    print('  single R          %.4f' % fx['single']['R'])
    print('  5y cohorts        %d, buy wins %d, median R %.4f'
          % (fx['cohorts_5y']['n'], fx['cohorts_5y']['buy_wins'],
             fx['cohorts_5y']['R_median']))
    print('  10y cohorts       %d, buy wins %d, median R %.4f'
          % (fx['cohorts_10y']['n'], fx['cohorts_10y']['buy_wins'],
             fx['cohorts_10y']['R_median']))
    print('  forward RAR 5y    %.4f%%' % (100 * fx['forward']['rar']['5']))
    return 0


if __name__ == '__main__':
    sys.exit(main())
