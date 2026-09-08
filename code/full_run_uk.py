#!/usr/bin/env python3
"""
Full England run — generates ALL key numbers for the whitepaper.

Design (revised 2026-07-09c):
  * NATIONAL result is run on a composition-consistent REPRESENTATIVE-England
    series: the population-weighted average of the nine regions' price and rent
    (same weights for both), built in prep_uk_data_v2.py. This fixes the
    mismatch between the transaction-weighted UK HPI England price and the
    London-heavy PIPR England rent, which made the naive national P/R fall below
    every region's.
  * A REGIONAL block runs the race region-by-region (each internally consistent)
    and reports a population-weighted aggregate + a per-region table.
  * Baseline = the typical FIRST-TIME BUYER: 10% deposit, 30-year term, 1.5%
    maintenance, 5-year fixed FTB rate at 90% LTV, 1.2% purchase costs + period-accurate
    England FTB SDLT, 1.8% selling, renter in MSCI ACWI net-of-tax GBP less a
    0.12% ETF fee. Sample Jan 2005 - Jun 2026 (258 months).
  * Forward-RAR opportunity cost = 6.0% nominal CAPE minus 0.12% TER = 5.88%.

Outputs -> output/tables/UK/  (CSVs + uk_key_numbers.json)
"""
import sys, io, os, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd
from scipy import stats

from uk_horse_race_v2 import (load_uk_housing, load_uk_returns, align_monthly_data,
                              sim_pair, run_rolling, run_rolling_fixed, compute_rar, forward_rar,
                              sdlt_england, BASE_SPEC)

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REP = os.path.join(BASE, "data", "clean", "uk_housing_monthly_representative.csv")
ENG = os.path.join(BASE, "data", "clean", "uk_housing_monthly_england.csv")
R = os.path.join(BASE, "data", "clean", "uk_stock_returns_gbp.csv")
REG = os.path.join(BASE, "data", "clean", "uk_housing_monthly_regions.csv")
GILT = os.path.join(BASE, "data", "clean", "uk_gilt_yield_10y.csv")
OUT = os.path.join(BASE, "output", "tables")
os.makedirs(OUT, exist_ok=True)

SAMPLE_END = '2026-06-30'
EQUITY_OPP = 0.06 - 0.0012          # 6% CAPE-implied nominal, net of 0.12% ETF fee = 5.88%
RENT_GROWTH = 0.03
REGION_POP = {'North East': 2.65, 'North West': 7.52, 'Yorkshire and The Humber': 5.56,
              'East Midlands': 5.02, 'West Midlands': 6.11, 'East of England': 6.40,
              'London': 8.87, 'South East': 9.46, 'South West': 5.80}

KEY = {}

housing = load_uk_housing(REP, end=SAMPLE_END)
acwi = load_uk_returns(R, 'acwi_net_ter_gbp_ret')
ftse = load_uk_returns(R, 'ftse100_tr_ret')
acwi_gross = load_uk_returns(R, 'acwi_gross_gbp_ret')
ha, ar = align_monthly_data(housing, acwi)
_, ar_ftse = align_monthly_data(housing, ftse)
_, ar_gross = align_monthly_data(housing, acwi_gross)
n_months = len(ha)
print(f"\nBaseline spec: {BASE_SPEC}")
print(f"Representative sample: {ha.index[0]:%Y-%m} -> {ha.index[-1]:%Y-%m} ({n_months} months)")
# Derive the expected length from the sample bounds rather than hard-coding it,
# so extending the sample does not require editing a magic number.
_expected = pd.date_range(ha.index[0], pd.Timestamp(SAMPLE_END), freq='ME')
assert n_months == len(_expected) and ha.index.equals(_expected), (
    f"Sample is not a complete month-end run: {n_months} months vs "
    f"{len(_expected)} expected to {SAMPLE_END}")

gilts = pd.read_csv(GILT, parse_dates=['Date']).set_index('Date')['yield_pct']
rate_now = ha.iloc[-1]['mortgage_rate_annual']
gilt_now = gilts[gilts.index <= ha.index[-1]].iloc[-1] / 100

# ============ 1. SINGLE START ============
print("\n" + "=" * 60 + "\n1. SINGLE START (Jan 2005 - Apr 2026, representative England)\n" + "=" * 60)
b, r = sim_pair(ha, ar, 0)
R_single = r['net_worth'] / b['net_worth']
print(f"  Purchase {b['purchase_price']:,.0f}  deposit {0.10*b['purchase_price']:,.0f}  "
      f"SDLT {b['sdlt_paid']:,.0f}  initial equity {b['initial_equity']:,.0f}")
print(f"  NW_buy {b['net_worth']:,.0f}  NW_rent {r['net_worth']:,.0f}  "
      f"diff {r['net_worth']-b['net_worth']:+,.0f}  R={R_single:.3f}")
KEY['single'] = {
    'purchase_price': b['purchase_price'], 'deposit': 0.10 * b['purchase_price'],
    'initial_equity': b['initial_equity'], 'sdlt_paid': b['sdlt_paid'],
    'nw_buy': b['net_worth'], 'nw_rent': r['net_worth'], 'diff': r['net_worth'] - b['net_worth'],
    'R': R_single, 'external_cash': r['external_cash_required'],
    'final_home_value': b['home_values'][-1], 'final_balance': b['mortgage_balances'][-1],
    'closing_purchase': b['closing_costs_purchase'], 'closing_sale': b['closing_costs_sale'],
    'months_owner_cheaper': int((r['net_flows'] < 0).sum()),
    'first_payment': b['mortgage_payments'][0], 'last_payment': b['mortgage_payments'][-1],
    'peak_payment': float(b['mortgage_payments'].max()),
    'first_rent': r['rent_payments'][0], 'last_rent': r['rent_payments'][-1],
    'first_maint': b['maintenance_costs'][0], 'last_maint': b['maintenance_costs'][-1],
}
pd.DataFrame({
    'date': b['dates'], 'home_value': b['home_values'], 'mortgage_balance': b['mortgage_balances'],
    'mortgage_payment': b['mortgage_payments'], 'maintenance': b['maintenance_costs'],
    'owner_outflow': b['owner_outflows'], 'rent': r['rent_payments'],
    'portfolio': r['portfolio_values'], 'net_flow': r['net_flows'],
    'buy_equity': b['home_values'] - b['mortgage_balances'],
}).to_csv(os.path.join(OUT, 'uk_single_start_paths.csv'), index=False)

# ============ 2. ROLLING COHORTS ============
print("\n" + "=" * 60 +
      "\n2. PRIMARY COHORT RESULT: fixed 5-year holds, monthly starts\n" + "=" * 60)
# Five years because that is roughly how long a UK first-time buyer keeps their
# first home (Santander put the average at 4.5 years). It also makes deducting
# selling costs the correct treatment rather than an artefact: we measure the
# buyer's wealth at the point they move out.
HEADLINE_HORIZON_MONTHS = 60
cohorts = run_rolling_fixed(ha, ar, horizon_months=HEADLINE_HORIZON_MONTHS)
cw = (cohorts.winner == 'BUY').sum()
KEY['cohorts_5y'] = {
    'horizon_months': HEADLINE_HORIZON_MONTHS,
    'n': len(cohorts), 'buy_wins': int(cw), 'rent_wins': int(len(cohorts) - cw),
    'buy_pct': round(100 * cw / len(cohorts)),
    # Median leads; see the regional note on why mean R is fragile.
    'R_mean': cohorts.R.mean(), 'R_median': cohorts.R.median(),
    'gap_mean_gbp': float((cohorts.nw_rent - cohorts.nw_buy).mean()),
    'gap_median_gbp': float((cohorts.nw_rent - cohorts.nw_buy).median()),
    'negative_equity_cohorts': int((cohorts.nw_buy < 0).sum()),
    'R_min': cohorts.R.min(), 'R_max': cohorts.R.max(),
    'R_min_start': str(cohorts.loc[cohorts.R.idxmin(), 'start_date'])[:7],
    'R_max_start': str(cohorts.loc[cohorts.R.idxmax(), 'start_date'])[:7],
    'first_cohort': str(cohorts.start_date.iloc[0])[:7],
    'last_cohort': str(cohorts.start_date.iloc[-1])[:7],
    'sdlt_paying_cohorts': int((cohorts.sdlt_paid > 0).sum()),
}
print(f"  N={len(cohorts)} ({KEY['cohorts_5y']['first_cohort']}..{KEY['cohorts_5y']['last_cohort']})"
      f"  BUY wins {cw} ({KEY['cohorts_5y']['buy_pct']}%)  "
      f"R-bar {cohorts.R.mean():.3f}  median {cohorts.R.median():.3f}")
print(f"  R range {cohorts.R.min():.3f} ({KEY['cohorts_5y']['R_min_start']}) - "
      f"{cohorts.R.max():.3f} ({KEY['cohorts_5y']['R_max_start']})")
cohorts.to_csv(os.path.join(OUT, 'uk_cohorts_5y.csv'), index=False)

# --- dispersion and the shape of the renting tail ---------------------------
# Buying wins slightly more often than it loses, but the two sides of the
# distribution are not symmetric, so the count of wins understates what is
# happening. Renting's wins are proportionally much larger than buying's:
# mean R sits well above median R. Both statistics are reported because they
# answer different questions, and because the gap between them IS a result.
#
# Mean R is usable here only because the representative English dwelling never
# leaves the owner in negative equity (min net worth is positive), so R has no
# small denominator to explode through. That is not true region by region,
# where negative-equity cohorts make mean R meaningless and the median plus
# the pound gap are the only defensible summaries.
_gap = cohorts.nw_rent - cohorts.nw_buy
assert cohorts.nw_buy.min() > 0, 'mean R is not safe to report if any owner net worth <= 0'
KEY['cohorts_5y'].update({
    'R_p10': float(cohorts.R.quantile(0.10)),
    'R_p90': float(cohorts.R.quantile(0.90)),
    'n_R_above_2': int((cohorts.R > 2).sum()),
    'n_R_above_3': int((cohorts.R > 3).sum()),
    'n_R_above_4': int((cohorts.R > 4).sum()),
    'R_max_gap_gbp': float(_gap.max()),
    'R_min_gap_gbp': float(_gap.min()),
    'nw_buy_min_gbp': float(cohorts.nw_buy.min()),
})
# Entry-year regimes: which vintages buying won, and by how much.
_yr = cohorts.assign(yr=cohorts.start_date.astype(str).str[:4]).groupby('yr')
regime = _yr.agg(n=('R', 'size'), R_mean=('R', 'mean'), R_median=('R', 'median'),
                 buy_win_pct=('winner', lambda s: 100 * (s == 'BUY').mean())).reset_index()
regime.to_csv(os.path.join(OUT, 'uk_entry_year_regimes.csv'), index=False)
KEY['entry_year_regimes'] = regime.to_dict('records')
_allrent = regime[regime.buy_win_pct == 0]['yr'].tolist()
_allbuy = regime[regime.buy_win_pct == 100]['yr'].tolist()
KEY['cohorts_5y']['years_renting_won_every_cohort'] = _allrent
KEY['cohorts_5y']['years_buying_won_every_cohort'] = _allbuy
print(f"  mean R {cohorts.R.mean():.3f} vs median {cohorts.R.median():.3f}; "
      f"R in [{cohorts.R.min():.2f}, {cohorts.R.max():.2f}]")
print(f"  renting won by >2x in {(cohorts.R > 2).sum()} cohorts, >3x in {(cohorts.R > 3).sum()}, "
      f">4x in {(cohorts.R > 4).sum()}")
print(f"  mean gap {_gap.mean():+,.0f} vs median {_gap.median():+,.0f} (renter minus owner)")
print(f"  renting won every cohort entering in {', '.join(_allrent)}; "
      f"buying won every cohort entering in {', '.join(_allbuy)}")

# --- horizon panel, 1 to 10 years -------------------------------------------
# Short holds are dominated by round-trip transaction costs (stamp duty, 1.2%
# purchase costs, 1.8% selling costs), which the buyer cannot amortise.
#
# The panel stops at ten years. Beyond that the sample cannot support the
# estimate: a 15-year hold is available only for cohorts entering in the first
# 79 months and a 20-year hold only for the first 19, so those points describe
# one pre-crisis entry window rather than the effect of holding longer. Ten
# years still rests on 139 cohorts spanning eleven and a half years of entry
# dates, which is the longest horizon this sample can speak to.
MAX_HORIZON_YEARS = 10
print("\n  Horizon panel (monthly starts at each horizon):")
print(f"  {'years':>5} {'cohorts':>8} {'buy-win':>8} {'mean R':>8} {'median R':>9} {'med gap':>10}")
hz_rows = []
for yrs in range(1, MAX_HORIZON_YEARS + 1):
    hm = yrs * 12
    if len(ha) - hm + 1 < 12:
        continue
    hc = run_rolling_fixed(ha, ar, horizon_months=hm)
    bw = 100 * (hc.winner == 'BUY').mean()
    gap = hc.nw_rent - hc.nw_buy
    hz_rows.append({'horizon_years': yrs, 'n_cohorts': len(hc), 'buy_win_pct': bw,
                    'R_mean': hc.R.mean(), 'R_median': hc.R.median(),
                    'gap_mean_gbp': float(gap.mean()),
                    'gap_median_gbp': float(gap.median()),
                    # Diagnostic for whether mean R is safe to report at this
                    # horizon. R = W_rent / W_own, so a small owner net worth
                    # inflates it. At short holds the owner has paid the
                    # transaction costs and amortised almost nothing, so the
                    # denominator can be tiny and mean R becomes unstable.
                    'nw_buy_min_gbp': float(hc.nw_buy.min()),
                    'first_cohort': str(hc.start_date.iloc[0])[:7],
                    'last_cohort': str(hc.start_date.iloc[-1])[:7]})
    print(f"  {yrs:>5} {len(hc):>8} {bw:>7.0f}% {hc.R.mean():>8.3f} {hc.R.median():>9.3f} "
          f"{gap.median():>10,.0f}")
hz_df = pd.DataFrame(hz_rows)
hz_df.to_csv(os.path.join(OUT, 'uk_horizon_panel.csv'), index=False)
KEY['horizon_panel'] = hz_rows

print("\n" + "=" * 60 +
      "\n2b. ROBUSTNESS: cohorts run to the sample end (unequal lengths)\n" + "=" * 60)
rolling = run_rolling(ha, ar)
buy_wins = (rolling.winner == 'BUY').sum()
KEY['rolling'] = {
    'n': len(rolling), 'buy_wins': int(buy_wins), 'rent_wins': int(len(rolling) - buy_wins),
    'buy_pct': round(100 * buy_wins / len(rolling)),
    'R_mean': rolling.R.mean(), 'R_median': rolling.R.median(),
    'R_min': rolling.R.min(), 'R_max': rolling.R.max(),
    'R_min_start': str(rolling.loc[rolling.R.idxmin(), 'start_date'])[:7],
    'R_max_start': str(rolling.loc[rolling.R.idxmax(), 'start_date'])[:7],
    'last_cohort': str(rolling.start_date.iloc[-1])[:7],
    'sdlt_paying_cohorts': int((rolling.sdlt_paid > 0).sum()),
}
print(f"  N={len(rolling)}  BUY wins {buy_wins} ({KEY['rolling']['buy_pct']}%)  "
      f"R-bar {rolling.R.mean():.3f}  median {rolling.R.median():.3f}")
print(f"  R range {rolling.R.min():.3f} ({KEY['rolling']['R_min_start']}) - "
      f"{rolling.R.max():.3f} ({KEY['rolling']['R_max_start']})")
rolling.to_csv(os.path.join(OUT, 'uk_rolling_cohorts.csv'), index=False)

# ============ 3. PREDICTORS ============
print("\n" + "=" * 60 + "\n3. PREDICTORS\n" + "=" * 60)
# Run on the FIXED-horizon cohorts, not the to-end ones. With unequal cohort
# lengths the outcome is mechanically related to length, and length correlates
# with entry conditions, so a to-end regression conflates the two.
pred = cohorts
r_rate, p_rate = stats.pearsonr(pred['mortgage_rate'], pred['R'])
r_pr, p_pr = stats.pearsonr(pred['pr_ratio'], pred['R'])
X = np.column_stack([np.ones(len(pred)), pred['mortgage_rate'], pred['pr_ratio']])
coefs, _, _, _ = np.linalg.lstsq(X, pred['R'].values, rcond=None)
r2_combined = 1 - np.sum((pred['R'].values - X @ coefs) ** 2) / np.sum((pred['R'].values - pred['R'].mean()) ** 2)
print(f"  rate r={r_rate:.3f} (R2={r_rate**2:.3f})  P/R r={r_pr:.3f} (R2={r_pr**2:.3f})  combined R2={r2_combined:.3f}")
pr_buy = pred[pred.R < 1]['pr_ratio']; pr_rent = pred[pred.R > 1]['pr_ratio']
KEY['predictors'] = {'r_rate': r_rate, 'r_pr': r_pr, 'r2_rate': r_rate**2, 'r2_pr': r_pr**2,
                     'r2_combined': r2_combined, 'p_rate': p_rate, 'p_pr': p_pr,
                     'pr_buy_always_below': float(pr_rent.min()) if len(pr_rent) else None,
                     'pr_rent_always_above': float(pr_buy.max()) if len(pr_buy) else None}
print(f"  BUY always won for P/R < {KEY['predictors']['pr_buy_always_below']}; "
      f"RENT always won for P/R > {KEY['predictors']['pr_rent_always_above']}")

# ============ 4. SENSITIVITY ============
print("\n" + "=" * 60 + "\n4. SENSITIVITY\n" + "=" * 60)

def scenario(returns_series=None, housing_df=None, **ov):
    rr = ar if returns_series is None else returns_series
    hh = ha if housing_df is None else housing_df
    b1, r1 = sim_pair(hh, rr, 0, **ov)
    # Measured on the fixed 5-year cohorts so the sensitivity matches the headline.
    roll = run_rolling_fixed(hh, rr, horizon_months=HEADLINE_HORIZON_MONTHS, **ov)
    # MEDIAN, not mean: R is a ratio and the levered buyer's terminal net worth can
    # approach zero, which makes the mean unstable. See the note in Section 5.
    return r1['net_worth'] / b1['net_worth'], roll.R.median(), (roll.winner == 'BUY').mean()

sens_rows = []
def add_sens(group, label, **kw):
    Rs, Rbar, bs = scenario(**kw)
    sens_rows.append({'group': group, 'label': label, 'R_single': Rs,
                      'R_cohort_median': Rbar, 'buy_win_share': bs})
    print(f"  {group:<15} {label:<16} R={Rs:.3f} Rbar={Rbar:.3f} buy={bs*100:.0f}%")

add_sens('base', 'base')
for d in [0.05, 0.15, 0.20, 0.25, 0.50, 1.00]:
    add_sens('deposit', f'{d:.0%}', deposit_share=d)
# 1.2-1.8% is the range UK data supports: ONS MJX9 depreciation on dwellings over
# dwellings-plus-land is 1.20% of market value (1995-2024 mean, 1.47% at its 1995
# peak), plus ~0.35% cash maintenance and buildings insurance. 1.0% and 2.0% are
# reported as bounds OUTSIDE that evidence, not as equally supported alternatives.
for m in [0.012, 0.018]:
    add_sens('maintenance (UK-grounded)', f'{m*100:.1f}%', maintenance_pct_of_value=m)
for m in [0.010, 0.020, 0.025, 0.030]:
    add_sens('maintenance (beyond evidence)', f'{m*100:.1f}%', maintenance_pct_of_value=m)
for yt in [25, 35]:
    add_sens('term', f'{yt}y', amort_years=yt)
for f in [2, 5, 10]:
    add_sens('fixation', f'{f}y', rate_fixation_years=f)
# Floating-rate bounding case: CFMBJ95, the effective rate on all new advances,
# recast monthly. Not a product any FTB holds - it is blended across LTVs and
# fixation lengths - but it bounds how much the fixation cliff matters.
_raw = pd.read_csv(REP, parse_dates=['Date']).set_index('Date')
ha_float = ha.copy()
ha_float['mortgage_rate_annual'] = (_raw['Mortgage_Rate_CFMBJ95_pct'] / 100.0
                                    ).reindex(ha_float.index).values
ha_float = ha_float.drop(columns=[c for c in ('rate_75_pct', 'rate_90_pct', 'rate_95_pct')
                                  if c in ha_float.columns])
add_sens('rate design', 'CFMBJ95 floating', housing_df=ha_float, rate_fixation_years=None)

# Renter leverage (comments.txt item 5). Margin interest = Bank Rate + 1.50%
# (Interactive Brokers U.K. Tier I), 30% maintenance margin, forced liquidation
# modelled. No cohort is liquidated even at 2x, because cash-flow matching
# deleverages the position: the renter contributes GBP 32,764 over 60 months
# against an initial stake of GBP 24,314. The minimum equity ratio is 31.9%,
# which is marginal against a 30% floor - see the caveat in the text about
# monthly observation understating drawdowns.
for L in [1.25, 1.50, 1.75, 2.00]:
    add_sens('renter leverage', f'{L:.2f}x', leverage=L)
for pc in [0.010, 0.020]:
    add_sens('purchase_costs', f'{pc*100:.1f}%', purchase_costs_pct=pc)
for sc in [0.010, 0.040]:
    add_sens('selling_costs', f'{sc*100:.1f}%', selling_costs_pct=sc)
add_sens('sdlt', 'excluded', include_sdlt=False)
add_sens('index', 'ACWI gross', returns_series=ar_gross)
add_sens('index', 'FTSE 100', returns_series=ar_ftse)
pd.DataFrame(sens_rows).to_csv(os.path.join(OUT, 'uk_sensitivity.csv'), index=False)
KEY['sensitivity'] = sens_rows

# ============ 5. HISTORICAL RAR (representative) ============
print("\n" + "=" * 60 + "\n5. HISTORICAL RAR (10y horizon, representative)\n" + "=" * 60)
rar_kw = dict(horizon_months=120, deposit_share=0.10, amort_years=30, maint_pct=0.015,
              purchase_costs_pct=0.012, selling_costs_pct=0.018, include_sdlt=True)
rar_rows = []
for start in range(0, n_months - 120):
    date = ha.index[start]; row = ha.iloc[start]
    rs = compute_rar(start, ha, ar, use_stock_returns=True, **rar_kw)
    gy = gilts[gilts.index <= date]
    gyv = gy.iloc[-1] / 100 if len(gy) else None
    rb = compute_rar(start, ha, ar, use_stock_returns=False, fixed_annual_return=gyv, **rar_kw) if gyv else None
    end_price = ha.iloc[start + 120]['purchase_price_gbp']
    actual = (end_price / row['purchase_price_gbp']) ** (12 / 120) - 1
    rar_rows.append({'date': date, 'rate': row['mortgage_rate_annual'],
                     'pr': row['purchase_price_gbp'] / (row['rent_gbp'] * 12),
                     'gilt_yield': gyv, 'rar_stocks': rs, 'rar_gilts': rb, 'actual_appr': actual})
rar_df = pd.DataFrame(rar_rows)
rar_df['verdict_stocks'] = np.where(rar_df.rar_stocks > rar_df.actual_appr, 'RENT', 'BUY')
rar_df.to_csv(os.path.join(OUT, 'uk_rar_historical.csv'), index=False)
n_rent_s = (rar_df.verdict_stocks == 'RENT').sum()
print(f"  {len(rar_df)} cohorts; mean RAR vs stocks {rar_df.rar_stocks.mean()*100:.2f}% "
      f"(range {rar_df.rar_stocks.min()*100:.2f}..{rar_df.rar_stocks.max()*100:.2f}); "
      f"BUY ex-post right {len(rar_df)-n_rent_s}/{len(rar_df)}")
print(f"  mean RAR vs gilts {rar_df.rar_gilts.mean()*100:.2f}%; mean actual appr {rar_df.actual_appr.mean()*100:.2f}%")
KEY['rar_hist'] = {'n': len(rar_df), 'mean_stocks': rar_df.rar_stocks.mean(),
                   'min_stocks': rar_df.rar_stocks.min(), 'max_stocks': rar_df.rar_stocks.max(),
                   'mean_gilts': rar_df.rar_gilts.mean(), 'mean_actual': rar_df.actual_appr.mean(),
                   'buy_right_stocks': int(len(rar_df) - n_rent_s)}

# ============ 6. FORWARD RAR (representative, Apr 2026) ============
print("\n" + "=" * 60 + "\n6. FORWARD RAR (Apr 2026, representative)\n" + "=" * 60)
last = ha.iloc[-1]
price_now, rent_now = last['purchase_price_gbp'], last['rent_gbp']
sdlt_now = sdlt_england(price_now, ha.index[-1]); pr_now = price_now / (rent_now * 12)
# Costs match the baseline. Every other assumption is held at the baseline too:
# 10% deposit, 30-year term, 1.5% maintenance, and the CURRENT FTB 5-year fixed
# rate at 90% LTV (rate_now), held constant over the horizon.
fwd_kw = dict(deposit_share=0.10, amort_years=30, maint_pct=0.015,
              purchase_costs_pct=0.012, selling_costs_pct=0.018, rent_growth_annual=RENT_GROWTH)
print(f"  price {price_now:,.0f}  rent {rent_now:.0f}  P/R {pr_now:.1f}  rate {rate_now*100:.2f}%  "
      f"gilt {gilt_now*100:.2f}%  yield {rent_now*12/price_now*100:.2f}%  SDLT {sdlt_now:,.0f}")

# TWO equity scenarios (comments.txt item 13). A single CAPE-implied figure is a
# pessimistic view of forward equity returns and makes the buy case look better
# than a symmetric treatment would. The optimistic leg uses the return the renter
# actually realised over this sample, so the reader sees the range rather than one
# assumption dressed as a forecast.
EQUITY_REALISED = (1 + ar).prod() ** (12 / len(ar)) - 1
print(f"  equity assumptions: CAPE-implied {EQUITY_OPP*100:.2f}% (cautious), "
      f"realised over the sample {EQUITY_REALISED*100:.2f}% (optimistic), "
      f"gilt {gilt_now*100:.2f}%")
fwd_sens = []
for hyr in [3, 5, 7, 10]:
    rs = forward_rar(price_now, rent_now, rate_now, EQUITY_OPP, horizon_years=hyr, sdlt_gbp=sdlt_now, **fwd_kw)
    rr_ = forward_rar(price_now, rent_now, rate_now, EQUITY_REALISED, horizon_years=hyr, sdlt_gbp=sdlt_now, **fwd_kw)
    rb = forward_rar(price_now, rent_now, rate_now, gilt_now, horizon_years=hyr, sdlt_gbp=sdlt_now, **fwd_kw)
    fwd_sens.append({'horizon_years': hyr, 'rar_stocks_pct': rs * 100,
                     'rar_stocks_realised_pct': rr_ * 100, 'rar_gilts_pct': rb * 100})
    print(f"    {hyr:>2}y: stocks (CAPE) {rs*100:>6.2f}%  "
          f"stocks (realised) {rr_*100:>6.2f}%  gilts {rb*100:>6.2f}%")
pd.DataFrame(fwd_sens).to_csv(os.path.join(OUT, 'uk_rar_forward_sensitivity.csv'), index=False)
r10 = [d for d in fwd_sens if d['horizon_years'] == 10][0]
KEY['rar_fwd'] = {'price': price_now, 'rent': rent_now, 'rate': rate_now, 'pr': pr_now,
                  'gilt': gilt_now, 'sdlt': sdlt_now, 'gross_yield': rent_now * 12 / price_now,
                  'rar_stocks': r10['rar_stocks_pct'] / 100, 'rar_gilts': r10['rar_gilts_pct'] / 100,
                  'rar_stocks_realised': r10['rar_stocks_realised_pct'] / 100,
                  'equity_opp': EQUITY_OPP, 'equity_realised': float(EQUITY_REALISED),
                  'rent_growth': RENT_GROWTH}
KEY['rar_fwd_sens'] = fwd_sens

# ============ 7. REGIONAL BLOCK (historical + forward, per region + pop-weighted) ============
print("\n" + "=" * 60 + "\n7. REGIONAL RESULTS (9 regions, pop-weighted aggregate)\n" + "=" * 60)
reg = pd.read_csv(REG, parse_dates=['Date'])
reg['Date'] = reg['Date'].dt.to_period('M').dt.to_timestamp('M')
natrate = load_uk_housing(ENG, end=SAMPLE_END)['mortgage_rate_annual']
reg_rows = []
for name, g in reg.groupby('Region'):
    g = g.set_index('Date').sort_index()
    df = pd.DataFrame({'rent_gbp': g['Rent_GBP'], 'purchase_price_gbp': g['Price_GBP'],
                       'mortgage_rate_annual': natrate.reindex(g.index)}).dropna()
    hr, arr = align_monthly_data(df, acwi)
    br, rr_ = sim_pair(hr, arr, 0)
    # Fixed 5-year cohorts, matching the headline design.
    roll_r = run_rolling_fixed(hr, arr, horizon_months=HEADLINE_HORIZON_MONTHS)
    pnow, rnow = hr.iloc[-1]['purchase_price_gbp'], hr.iloc[-1]['rent_gbp']
    sd = sdlt_england(pnow, ha.index[-1])
    # Reported at the 5-year headline horizon, under both equity assumptions.
    rk = dict(horizon_years=5, sdlt_gbp=sd, **fwd_kw)
    rar_s = forward_rar(pnow, rnow, rate_now, EQUITY_OPP, **rk) * 100
    rar_r = forward_rar(pnow, rnow, rate_now, EQUITY_REALISED, **rk) * 100
    rar_g = forward_rar(pnow, rnow, rate_now, gilt_now, **rk) * 100
    appr = (pnow / hr.iloc[0]['purchase_price_gbp']) ** (12 / (len(hr) - 1)) - 1
    reg_rows.append({'region': name, 'pop': REGION_POP[name], 'price': pnow, 'rent': rnow,
                     'pr_ratio': pnow / (rnow * 12), 'sdlt': sd,
                     'R_single': rr_['net_worth'] / br['net_worth'],
                     'buy_win': (roll_r.winner == 'BUY').mean(),
                     # MEDIAN, not mean. R is a ratio and the levered buyer's net
                     # worth can cross zero - North East 2007 entrants were in
                     # negative equity by 2012 after selling costs - so R ranges
                     # from -82 to +9567 there and the mean is meaningless. The
                     # buy-win share and the median are both well behaved; the
                     # mean wealth GAP in pounds is reported alongside as the
                     # magnitude measure.
                     'R_median': roll_r.R.median(),
                     'gap_mean_gbp': float((roll_r.nw_rent - roll_r.nw_buy).mean()),
                     'gap_median_gbp': float((roll_r.nw_rent - roll_r.nw_buy).median()),
                     'negative_equity_cohorts': int((roll_r.nw_buy < 0).sum()),
                     'rar_stocks_pct': rar_s, 'rar_stocks_realised_pct': rar_r,
                     'rar_gilts_pct': rar_g, 'appreciation_pct': appr * 100})
reg_df = pd.DataFrame(reg_rows).sort_values('rar_stocks_pct')
reg_df.to_csv(os.path.join(OUT, 'uk_regional_results.csv'), index=False)
w = reg_df['pop'].values
# hist_rar_pct dropped: the historical RAR subsection is cut (comments.txt items
# 8 and 10), so the regional table reports the FORWARD break-even under both
# equity assumptions alongside each region's actual realised appreciation.
print(reg_df[['region', 'price', 'rent', 'pr_ratio', 'buy_win', 'R_median',
              'gap_median_gbp', 'negative_equity_cohorts',
              'rar_stocks_pct', 'rar_stocks_realised_pct', 'appreciation_pct']].to_string(
    index=False, formatters={'price': '{:,.0f}'.format, 'rent': '{:,.0f}'.format,
    'pr_ratio': '{:.1f}'.format, 'buy_win': '{:.0%}'.format, 'R_median': '{:.3f}'.format,
    'gap_median_gbp': '{:,.0f}'.format,
    'rar_stocks_pct': '{:.2f}'.format, 'rar_stocks_realised_pct': '{:.2f}'.format,
    'appreciation_pct': '{:.2f}'.format}))
KEY['regional'] = reg_df.to_dict('records')
KEY['regional_popwtd'] = {k: float(np.average(reg_df[k], weights=w))
                          for k in ['R_single', 'buy_win', 'R_median', 'gap_median_gbp',
                                    'rar_stocks_pct', 'rar_stocks_realised_pct',
                                    'rar_gilts_pct', 'appreciation_pct', 'pr_ratio']}
print(f"\n  POP-WEIGHTED regional aggregate: single R={KEY['regional_popwtd']['R_single']:.2f}  "
      f"buy-win={KEY['regional_popwtd']['buy_win']*100:.0f}%  fwd RAR={KEY['regional_popwtd']['rar_stocks_pct']:.2f}%")
print(f"  (national representative-series figures above should sit close to this)")

def _clean(o):
    if isinstance(o, dict): return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)): return [_clean(v) for v in o]
    if isinstance(o, (np.floating, np.integer)): return o.item()
    if isinstance(o, pd.Timestamp): return str(o)
    return o
with open(os.path.join(OUT, 'uk_key_numbers.json'), 'w', encoding='utf-8') as f:
    json.dump(_clean(KEY), f, indent=2, default=str)
print(f"\nSaved all tables + uk_key_numbers.json to {OUT}")
