#!/usr/bin/env python3
"""
Tests for the simulation engine (code/uk_horse_race_v2.py).

1. Stamp duty: 15 hand-computed cases spanning every England first-time-buyer
   regime from 2005 to the present, checked against the HMRC rate tables.
2. Mortgage arithmetic: an independent closed-form amortisation check.
3. End-to-end: the published headline numbers are reproduced from the clean
   dataset (skipped automatically if the licence-restricted returns series has
   not been fetched — see scripts/fetch_financial_series.py).

Run:  python code/tests/test_uk_engine.py
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CODE = os.path.dirname(HERE)
ROOT = os.path.dirname(CODE)
sys.path.insert(0, CODE)

from uk_horse_race_v2 import (BASE_SPEC, sdlt_england, compute_monthly_payment,
                              compute_monthly_mortgage_rate,
                              load_uk_housing, load_uk_returns,
                              align_monthly_data, sim_pair, run_rolling,
                              run_rolling_fixed)

failures = []


def check(name, got, want, tol=0.0):
    ok = abs(got - want) <= tol if isinstance(want, (int, float)) else got == want
    print(f"{'OK  ' if ok else 'FAIL'} {name}: got {got}, want {want}")
    if not ok:
        failures.append(name)


# ---------------------------------------------------------------- 1. SDLT
print("\n--- Stamp duty (England, first-time buyer) ---")
SDLT_CASES = [
    # (price, date, expected, note)
    (100_000, '2005-02-28', 1_000.0, 'slab 1%, nil band still 60k'),
    (100_000, '2005-06-30', 0.0, 'nil band raised to 120k'),
    (153_030, '2008-02-29', 1_530.30, 'slab 1% pre-holiday'),
    (153_030, '2008-10-31', 0.0, 'GFC holiday, nil band 175k'),
    (180_000, '2009-06-30', 1_800.0, 'holiday but above 175k'),
    (200_000, '2011-06-30', 0.0, 'FTB relief to 250k'),
    (220_000, '2013-06-30', 2_200.0, 'relief withdrawn, slab 1%'),
    (220_000, '2015-06-30', 1_900.0, 'slice: 2% of 95k'),
    (290_000, '2019-06-30', 0.0, 'FTB relief to 300k'),
    (560_000, '2019-06-30', 18_000.0, 'above FTB cap, standard slice'),
    (560_000, '2020-10-31', 3_000.0, 'COVID holiday, 5% of 60k'),
    (310_000, '2022-02-28', 500.0, 'FTB 5% of 10k over 300k'),
    (450_000, '2023-06-30', 1_250.0, 'FTB 5% of 25k over 425k'),
    (310_000, '2023-12-31', 0.0, 'FTB nil to 425k'),
    (310_000, '2025-06-30', 500.0, 'threshold back to 300k'),
]
for price, date, want, note in SDLT_CASES:
    check(f"SDLT {date} GBP{price:,} ({note})", sdlt_england(price, date), want, 0.51)

# ------------------------------------------------------ 2. Mortgage arithmetic
print("\n--- Mortgage arithmetic ---")
# A 30-year loan at 6% nominal: closed-form annuity payment, computed independently.
bal, annual, months = 200_000.0, 0.06, 360
mr = compute_monthly_mortgage_rate(annual)
want_pay = bal * mr / (1 - (1 + mr) ** -months)
check("annuity payment", compute_monthly_payment(bal, mr, months), want_pay, 1e-9)
check("zero balance -> zero payment", compute_monthly_payment(0.0, mr, months), 0.0)
# Amortising the loan over its full term (remaining term shrinking each month,
# as the engine does) must retire the balance exactly.
b = bal
for i in range(months):
    pay = compute_monthly_payment(b, mr, months - i)
    b = b - (pay - b * mr)
check("balance after full term", round(b, 6), 0.0, 1e-4)

# ----------------------------------------------------------- 3. End-to-end
print("\n--- End-to-end (published headline numbers) ---")
REP = os.path.join(ROOT, 'data', 'clean', 'uk_housing_monthly_representative.csv')
RET = os.path.join(ROOT, 'data', 'clean', 'uk_stock_returns_gbp.csv')
KEY = os.path.join(ROOT, 'output', 'tables', 'uk_key_numbers.json')
if not os.path.exists(RET):
    print("SKIP: returns series absent — run scripts/fetch_financial_series.py "
          "then code/prep_uk_data_v3.py to enable these checks.")
elif not os.path.exists(KEY):
    print("SKIP: output/tables/uk_key_numbers.json absent — run "
          "code/full_run_uk.py to enable these checks.")
else:
    # Expectations come from uk_key_numbers.json, the published record of every
    # number in the paper. They are deliberately not literals here: this block
    # previously carried them inline, and when the baseline was recalibrated the
    # literals went on describing the old specification. Sourcing them from the
    # published file means an engine change that is not reflected in the paper
    # fails the suite.
    with io.open(KEY, encoding='utf-8') as fh:
        K = json.load(fh)
    c5 = K['cohorts_5y']

    housing = load_uk_housing(REP, end='2026-06-30')
    acwi = load_uk_returns(RET, 'acwi_net_ter_gbp_ret')
    ha, ar = align_monthly_data(housing, acwi)
    check("sample months", len(ha), 258)

    # BASE_SPEC must be passed explicitly. sim_pair's own defaults are a 20%
    # deposit over 25 years at 2% maintenance with no fixation, which is not the
    # paper's baseline; calling it bare silently tests a different model.
    b_, r_ = sim_pair(ha, ar, 0, **dict(BASE_SPEC))
    R = r_['net_worth'] / b_['net_worth']
    check("single-start purchase price", round(b_['purchase_price']), 162_312, 1)
    check("single-start SDLT", round(b_['sdlt_paid']), 1_623, 1)
    check("single-start owner wealth", round(b_['net_worth']), 254_658, 2)
    check("single-start renter wealth", round(r_['net_worth']), 367_821, 2)
    check("single-start R", R, 1.4444, 0.001)

    # The headline design: every entry month held for exactly five years.
    coh = run_rolling_fixed(ha, ar, horizon_months=60, **dict(BASE_SPEC))
    check("5y cohorts", len(coh), c5['n'])
    check("5y cohorts won by buying", int((coh.winner == 'BUY').sum()), c5['buy_wins'])
    check("5y median wealth ratio", coh.R.median(), c5['R_median'], 0.0005)
    check("5y mean wealth ratio", coh.R.mean(), c5['R_mean'], 0.0005)
    check("5y median gap (GBP)", float((coh.nw_rent - coh.nw_buy).median()),
          c5['gap_median_gbp'], 1.0)
    # Mean R is only meaningful while the owner's net worth stays clear of zero.
    check("5y minimum owner net worth positive", bool(coh.nw_buy.min() > 0), True)

    # The to-end design is retained as robustness, not as the headline.
    roll = run_rolling(ha, ar, **dict(BASE_SPEC))
    check("to-end cohorts", len(roll), K['rolling']['n'])
    check("to-end cohorts won by buying", int((roll.winner == 'BUY').sum()),
          K['rolling']['buy_wins'])

print("\n" + ("ALL TESTS PASSED" if not failures
              else f"{len(failures)} FAILURE(S): " + ", ".join(failures)))
sys.exit(1 if failures else 0)
