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
  * Baseline = the typical FIRST-TIME BUYER: 10% deposit, 30-year term, 2%
    maintenance, variable CFMBJ95 rate, 1.5% purchase costs + period-accurate
    England FTB SDLT, 2% selling, renter in MSCI ACWI net-of-tax GBP less a
    0.12% ETF fee. Sample Jan 2005 - Apr 2026 (256 months).
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
                              sim_pair, run_rolling, compute_rar, forward_rar,
                              sdlt_england, BASE_SPEC)

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REP = os.path.join(BASE, "data", "clean", "uk_housing_monthly_representative.csv")
ENG = os.path.join(BASE, "data", "clean", "uk_housing_monthly_england.csv")
R = os.path.join(BASE, "data", "clean", "uk_stock_returns_gbp.csv")
REG = os.path.join(BASE, "data", "clean", "uk_housing_monthly_regions.csv")
GILT = os.path.join(BASE, "data", "clean", "uk_gilt_yield_10y.csv")
OUT = os.path.join(BASE, "output", "tables")
os.makedirs(OUT, exist_ok=True)

SAMPLE_END = '2026-04-30'
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
assert n_months == 256

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
print("\n" + "=" * 60 + "\n2. ROLLING QUARTERLY COHORTS (representative England)\n" + "=" * 60)
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
r_rate, p_rate = stats.pearsonr(rolling['mortgage_rate'], rolling['R'])
r_pr, p_pr = stats.pearsonr(rolling['pr_ratio'], rolling['R'])
X = np.column_stack([np.ones(len(rolling)), rolling['mortgage_rate'], rolling['pr_ratio']])
coefs, _, _, _ = np.linalg.lstsq(X, rolling['R'].values, rcond=None)
r2_combined = 1 - np.sum((rolling['R'].values - X @ coefs) ** 2) / np.sum((rolling['R'].values - rolling['R'].mean()) ** 2)
print(f"  rate r={r_rate:.3f} (R2={r_rate**2:.3f})  P/R r={r_pr:.3f} (R2={r_pr**2:.3f})  combined R2={r2_combined:.3f}")
pr_buy = rolling[rolling.R < 1]['pr_ratio']; pr_rent = rolling[rolling.R > 1]['pr_ratio']
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
    roll = run_rolling(hh, rr, **ov)
    return r1['net_worth'] / b1['net_worth'], roll.R.mean(), (roll.winner == 'BUY').mean()

sens_rows = []
def add_sens(group, label, **kw):
    Rs, Rbar, bs = scenario(**kw)
    sens_rows.append({'group': group, 'label': label, 'R_single': Rs, 'R_rolling_mean': Rbar, 'buy_win_share': bs})
    print(f"  {group:<15} {label:<16} R={Rs:.3f} Rbar={Rbar:.3f} buy={bs*100:.0f}%")

add_sens('base', 'base')
for d in [0.05, 0.15, 0.20, 0.25, 0.50, 1.00]:
    add_sens('deposit', f'{d:.0%}', deposit_share=d)
for m in [0.010, 0.020, 0.025, 0.030]:
    add_sens('maintenance', f'{m*100:.1f}%', maintenance_pct_of_value=m)
for yt in [25, 35]:
    add_sens('term', f'{yt}y', amort_years=yt)
for f in [2, 5, 10]:
    add_sens('fixation', f'{f}y', rate_fixation_years=f)
# FTB higher-LTV rate premium (FTBs pay a bit more than the all-borrower CFMBJ95)
ha_prem = ha.copy(); ha_prem['mortgage_rate_annual'] = ha_prem['mortgage_rate_annual'] + 0.004
add_sens('rate_premium', '+0.4pp (high-LTV)', housing_df=ha_prem)
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
              purchase_costs_pct=0.015, selling_costs_pct=0.02, include_sdlt=True)
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
fwd_kw = dict(deposit_share=0.10, amort_years=30, maint_pct=0.015,
              purchase_costs_pct=0.015, selling_costs_pct=0.02, rent_growth_annual=RENT_GROWTH)
print(f"  price {price_now:,.0f}  rent {rent_now:.0f}  P/R {pr_now:.1f}  rate {rate_now*100:.2f}%  "
      f"gilt {gilt_now*100:.2f}%  yield {rent_now*12/price_now*100:.2f}%  SDLT {sdlt_now:,.0f}")
fwd_sens = []
for hyr in [3, 5, 7, 10]:
    rs = forward_rar(price_now, rent_now, rate_now, EQUITY_OPP, horizon_years=hyr, sdlt_gbp=sdlt_now, **fwd_kw)
    rb = forward_rar(price_now, rent_now, rate_now, gilt_now, horizon_years=hyr, sdlt_gbp=sdlt_now, **fwd_kw)
    fwd_sens.append({'horizon_years': hyr, 'rar_stocks_pct': rs * 100, 'rar_gilts_pct': rb * 100})
    print(f"    {hyr:>2}y: stocks {rs*100:>6.2f}%  gilts {rb*100:>6.2f}%")
pd.DataFrame(fwd_sens).to_csv(os.path.join(OUT, 'uk_rar_forward_sensitivity.csv'), index=False)
r10 = [d for d in fwd_sens if d['horizon_years'] == 10][0]
KEY['rar_fwd'] = {'price': price_now, 'rent': rent_now, 'rate': rate_now, 'pr': pr_now,
                  'gilt': gilt_now, 'sdlt': sdlt_now, 'gross_yield': rent_now * 12 / price_now,
                  'rar_stocks': r10['rar_stocks_pct'] / 100, 'rar_gilts': r10['rar_gilts_pct'] / 100,
                  'equity_opp': EQUITY_OPP, 'rent_growth': RENT_GROWTH}
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
    roll_r = run_rolling(hr, arr)
    pnow, rnow = hr.iloc[-1]['purchase_price_gbp'], hr.iloc[-1]['rent_gbp']
    sd = sdlt_england(pnow, ha.index[-1])
    rar_s = forward_rar(pnow, rnow, rate_now, EQUITY_OPP, horizon_years=10, sdlt_gbp=sd, **fwd_kw) * 100
    rar_g = forward_rar(pnow, rnow, rate_now, gilt_now, horizon_years=10, sdlt_gbp=sd, **fwd_kw) * 100
    hist = [compute_rar(s, hr, arr, use_stock_returns=True, **rar_kw) for s in range(0, len(hr) - 120)]
    hist = np.nanmean([x for x in hist if x is not None]) * 100
    reg_rows.append({'region': name, 'pop': REGION_POP[name], 'price': pnow, 'rent': rnow,
                     'pr_ratio': pnow / (rnow * 12), 'sdlt': sd,
                     'R_single': rr_['net_worth'] / br['net_worth'],
                     'buy_win': (roll_r.winner == 'BUY').mean(), 'Rbar': roll_r.R.mean(),
                     'R_min': roll_r.R.min(), 'R_max': roll_r.R.max(),
                     'rar_stocks_pct': rar_s, 'rar_gilts_pct': rar_g, 'hist_rar_pct': hist})
reg_df = pd.DataFrame(reg_rows).sort_values('rar_stocks_pct')
reg_df.to_csv(os.path.join(OUT, 'uk_regional_results.csv'), index=False)
w = reg_df['pop'].values
print(reg_df[['region', 'price', 'rent', 'pr_ratio', 'R_single', 'buy_win', 'rar_stocks_pct', 'hist_rar_pct']].to_string(
    index=False, formatters={'price': '{:,.0f}'.format, 'rent': '{:,.0f}'.format, 'pr_ratio': '{:.1f}'.format,
    'R_single': '{:.2f}'.format, 'buy_win': '{:.0%}'.format, 'rar_stocks_pct': '{:.2f}'.format, 'hist_rar_pct': '{:.2f}'.format}))
KEY['regional'] = reg_df.to_dict('records')
KEY['regional_popwtd'] = {k: float(np.average(reg_df[k], weights=w))
                          for k in ['R_single', 'buy_win', 'Rbar', 'rar_stocks_pct', 'rar_gilts_pct', 'hist_rar_pct', 'pr_ratio']}
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
