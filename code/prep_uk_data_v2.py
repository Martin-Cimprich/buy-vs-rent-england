#!/usr/bin/env python3
"""
Prepare UK data for the buy-vs-rent whitepaper (v2 pipeline).

Inputs (data/raw/UK_Data/, verified in-file 2026-07-08/09):
  1. UKHPI_full_file_2026-04.csv        — HM Land Registry UK HPI (all-dwellings
                                          average price, monthly, 405 geographies)
  2. priceindexofprivaterentsukhistoricalseries.xlsx
                                        — ONS PIPR historical series, Table 3 =
                                          average rent GBP/month, WIDE format,
                                          Jan 2005 - Feb 2025 (England + regions)
  3. pipr_monthly_2026-06.xlsx          — ONS PIPR live monthly file, Table 1 =
                                          LONG format, Jan 2015 - May 2026
  4. BoE_effective_rates_new_advances_CFMBJ95_2004plus.csv
                                        — BoE effective rate on new mortgage
                                          advances (CFMBJ95), Jan 2004 - May 2026
  5. msci_acwi_netr_gbp.csv / msci_acwi_grtr_gbp.csv
                                        — MSCI ACWI in GBP (net / gross TR levels)
  6. ftse100_tr_monthly.csv             — FTSE 100 TR proxy (ISF ETF NAV TR, GBP)
  7. fred_uk_10y_gilt_monthly.csv       — UK 10y gilt yield (OECD via FRED)

Transformations (documented inline):
  - All series normalised to month-END timestamps.
  - Rents: PIPR historical (2005-2014) spliced with live PIPR (2015+); the two
    are chain-consistent by construction — the script VERIFIES agreement over
    the 2015-01..2025-02 overlap and aborts if max abs diff > GBP 2.
  - Prices: UK HPI 'AveragePrice' used as-is (GBP level).
  - Index levels converted to simple monthly returns r_t = L_t / L_{t-1} - 1.

Outputs (data/clean/):
  - uk_housing_monthly_england.csv   (Date, Rent_GBP, Purchase_Price_GBP, Mortgage_Rate_pct)
  - uk_housing_monthly_regions.csv   (Date, Region, Rent_GBP, Price_GBP)
  - uk_stock_returns_gbp.csv         (Date, acwi_net_gbp_ret, acwi_gross_gbp_ret, ftse100_tr_ret)
  - uk_gilt_yield_10y.csv            (Date, yield_pct)
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import pandas as pd
import numpy as np
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
RAW = BASE / "data" / "raw"
D08 = RAW / "boe"
D09 = RAW / "financial"
CLEAN = BASE / "data" / "clean"
CLEAN.mkdir(parents=True, exist_ok=True)

SAMPLE_START = pd.Timestamp('2005-01-31')
# End at the last month for which prices, rents AND mortgage rates all exist
# (UK HPI prices are the binding constraint at April 2026).
SAMPLE_END = pd.Timestamp('2026-04-30')

# Ongoing charge of a cheap global-equity UCITS tracker (e.g. an MSCI ACWI ETF ~0.12% p.a.).
# Deducted from the MSCI ACWI net-of-withholding-tax index return to give the
# net-of-fees return an actual UK investor would realise.
ACWI_TER_ANNUAL = 0.0012

REGIONS = ['North East', 'North West', 'Yorkshire and The Humber',
           'East Midlands', 'West Midlands', 'East of England',
           'London', 'South East', 'South West']

def month_end(s):
    return pd.to_datetime(s).dt.to_period('M').dt.to_timestamp('M')


# ============================================================================
# 1. HOUSE PRICES — UK HPI all-dwellings average price
# ============================================================================
print("=" * 70)
print("1. UK HPI prices (England + 9 regions)")
print("=" * 70)
hpi = pd.read_csv(RAW / "ons" / "UKHPI_full_file_2026-04.csv",
                  usecols=['Date', 'RegionName', 'AveragePrice'],
                  parse_dates=['Date'], dayfirst=True)
geos = ['England'] + REGIONS
hpi = hpi[hpi['RegionName'].isin(geos)].copy()
hpi['Date'] = hpi['Date'].dt.to_period('M').dt.to_timestamp('M')
prices = hpi.pivot(index='Date', columns='RegionName', values='AveragePrice').sort_index()
missing_geo = [g for g in geos if g not in prices.columns]
assert not missing_geo, f"Missing geographies in UK HPI: {missing_geo}"
print(f"  England prices: {prices['England'].dropna().index[0]:%Y-%m} -> "
      f"{prices['England'].dropna().index[-1]:%Y-%m}; "
      f"Dec 2025 = GBP {prices.loc['2025-12-31', 'England']:,.0f}")

# ============================================================================
# 2. RENTS — PIPR historical (wide, Table 3) + live PIPR (long, Table 1)
# ============================================================================
print("\n" + "=" * 70)
print("2. PIPR rents (England + 9 regions), historical + live splice")
print("=" * 70)

# --- historical: Table 3, header at row idx 2, region-code row idx 3 ---
hist_raw = pd.read_excel(RAW / "ons" / "priceindexofprivaterentsukhistoricalseries.xlsx",
                         sheet_name='Table 3', header=None)
hdr = hist_raw.iloc[2].tolist()
hist = hist_raw.iloc[4:].copy()
hist.columns = hdr
hist = hist.rename(columns={'Time period and Region Code': 'Date',
                            'East ': 'East of England'})  # trailing-space name
hist['Date'] = month_end(hist['Date'])
hist = hist.set_index('Date')[['England'] + REGIONS]
hist = hist.apply(pd.to_numeric, errors='coerce')  # '[x]' -> NaN
print(f"  Historical: {hist.index[0]:%Y-%m} -> {hist.index[-1]:%Y-%m} "
      f"({len(hist)} months); England Jan 2005 = GBP {hist.iloc[0]['England']:.0f}")

# --- live: Table 1, long format, header row 3 (pandas header=2) ---
live_raw = pd.read_excel(RAW / "ons" / "pipr_monthly_2026-06.xlsx",
                         sheet_name='Table 1', header=2)
code_map = {'E92000001': 'England', 'E12000001': 'North East',
            'E12000002': 'North West', 'E12000003': 'Yorkshire and The Humber',
            'E12000004': 'East Midlands', 'E12000005': 'West Midlands',
            'E12000006': 'East of England', 'E12000007': 'London',
            'E12000008': 'South East', 'E12000009': 'South West'}
live = live_raw[live_raw['Area code'].isin(code_map)].copy()
live['Region'] = live['Area code'].map(code_map)
live['Date'] = month_end(live['Time period'])
live['Rent_GBP'] = pd.to_numeric(live['Rental price'], errors='coerce')
live_w = live.pivot(index='Date', columns='Region', values='Rent_GBP').sort_index()
live_w = live_w[['England'] + REGIONS]
print(f"  Live: {live_w.index[0]:%Y-%m} -> {live_w.index[-1]:%Y-%m} ({len(live_w)} months)")

# --- verify chain-consistency over the overlap, then splice ---
overlap = hist.index.intersection(live_w.index)
diff = (hist.loc[overlap] - live_w.loc[overlap]).abs()
print(f"  Overlap {overlap[0]:%Y-%m} -> {overlap[-1]:%Y-%m} ({len(overlap)} months): "
      f"max abs diff = GBP {diff.max().max():.2f}")
assert diff.max().max() <= 2.0, "PIPR historical and live series disagree on overlap!"

rents = pd.concat([hist.loc[hist.index < live_w.index[0]], live_w]).sort_index()
print(f"  Spliced rents: {rents.index[0]:%Y-%m} -> {rents.index[-1]:%Y-%m}; "
      f"England Dec 2025 = GBP {rents.loc['2025-12-31', 'England']:.0f}")

# ============================================================================
# 3. MORTGAGE RATE — BoE CFMBJ95 (effective rate on new advances)
# ============================================================================
print("\n" + "=" * 70)
print("3. BoE effective mortgage rate (CFMBJ95)")
print("=" * 70)
boe_raw = pd.read_csv(D08 / "BoE_effective_rates_new_advances_CFMBJ95_2004plus.csv",
                      header=None, names=range(7))
hdr_idx = boe_raw[boe_raw[0] == 'DATE'].index[0]
boe = boe_raw.iloc[hdr_idx + 1:].copy()
boe.columns = boe_raw.iloc[hdr_idx].tolist()
boe['Date'] = month_end(pd.to_datetime(boe['DATE'], format='%d %b %Y'))
boe['Mortgage_Rate_pct'] = pd.to_numeric(boe['CFMBJ95'], errors='coerce')
rate = boe.set_index('Date')['Mortgage_Rate_pct'].dropna().sort_index()
full_range = pd.date_range(SAMPLE_START, min(rate.index[-1], SAMPLE_END), freq='ME')
assert full_range.isin(rate.index).all(), "Gaps in CFMBJ95 over the sample!"
print(f"  CFMBJ95: {rate.index[0]:%Y-%m} -> {rate.index[-1]:%Y-%m}; "
      f"range {rate.min():.2f}%..{rate.max():.2f}%; Dec 2025 = {rate.loc['2025-12-31']:.2f}%")

# ============================================================================
# 4. RETURNS — MSCI ACWI GBP (net + gross), FTSE 100 TR proxy
# ============================================================================
print("\n" + "=" * 70)
print("4. Equity returns in GBP")
print("=" * 70)

def levels_to_returns(path, level_col='Level'):
    df = pd.read_csv(path)
    df['Date'] = month_end(df['Date'])
    s = df.set_index('Date')[level_col].sort_index()
    return s.pct_change().dropna()

acwi_net = levels_to_returns(D09 / "msci_acwi_netr_gbp.csv")
acwi_gross = levels_to_returns(D09 / "msci_acwi_grtr_gbp.csv")
ftse = levels_to_returns(D09 / "ftse100_tr_monthly.csv")
# Net-of-fees ACWI: subtract the ETF ongoing charge as a monthly drag. This is the
# baseline series the renter actually earns.
ter_monthly = (1 - ACWI_TER_ANNUAL) ** (1 / 12)
acwi_net_ter = (1 + acwi_net) * ter_monthly - 1
returns = pd.DataFrame({'acwi_net_ter_gbp_ret': acwi_net_ter,
                        'acwi_net_gbp_ret': acwi_net,
                        'acwi_gross_gbp_ret': acwi_gross,
                        'ftse100_tr_ret': ftse}).dropna(subset=['acwi_net_ter_gbp_ret'])
print(f"  ACWI net-of-fees GBP: {returns.index[0]:%Y-%m} -> {returns.index[-1]:%Y-%m} "
      f"({len(returns)} months); mean {returns['acwi_net_ter_gbp_ret'].mean()*100:.3f}%/mo "
      f"(TER {ACWI_TER_ANNUAL*100:.2f}% p.a. deducted from net-of-tax index)")
print(f"  FTSE 100 TR proxy:    mean {returns['ftse100_tr_ret'].mean()*100:.3f}%/mo")

# ============================================================================
# 5. GILTS — UK 10y yield
# ============================================================================
gilts = pd.read_csv(RAW / "gilts" / "fred_uk_10y_gilt_monthly.csv")
gilts.columns = ['Date', 'yield_pct']
gilts['Date'] = month_end(gilts['Date'])
gilts = gilts.set_index('Date').sort_index()
print(f"\n5. Gilt yields: {gilts.index[0]:%Y-%m} -> {gilts.index[-1]:%Y-%m}; "
      f"Dec 2025 = {gilts.loc['2025-12-31', 'yield_pct']:.2f}%")

# ============================================================================
# 6. MERGE & SAVE
# ============================================================================
print("\n" + "=" * 70)
print("6. Merge & save clean datasets")
print("=" * 70)

# --- England headline dataset (Jan 2005 - Dec 2025) ---
eng = pd.DataFrame({
    'Rent_GBP': rents['England'],
    'Purchase_Price_GBP': prices['England'],
    'Mortgage_Rate_pct': rate,
}).loc[SAMPLE_START:SAMPLE_END].dropna()
expected = pd.date_range(SAMPLE_START, SAMPLE_END, freq='ME')
assert len(eng) == len(expected) and eng.index.equals(expected), \
    f"England dataset incomplete: {len(eng)} months vs {len(expected)} expected"
out = eng.reset_index().rename(columns={'index': 'Date'})
out['Date'] = out['Date'].dt.strftime('%Y-%m-%d')
out.to_csv(CLEAN / "uk_housing_monthly_england.csv", index=False)
print(f"  uk_housing_monthly_england.csv: {len(eng)} months "
      f"({eng.index[0]:%Y-%m} -> {eng.index[-1]:%Y-%m})")
print(f"    Rent GBP {eng['Rent_GBP'].iloc[0]:.0f} -> {eng['Rent_GBP'].iloc[-1]:.0f}; "
      f"Price GBP {eng['Purchase_Price_GBP'].iloc[0]:,.0f} -> {eng['Purchase_Price_GBP'].iloc[-1]:,.0f}; "
      f"Rate {eng['Mortgage_Rate_pct'].iloc[0]:.2f}% -> {eng['Mortgage_Rate_pct'].iloc[-1]:.2f}%")

# --- Regional dataset (long) ---
reg_rows = []
for r in REGIONS:
    df_r = pd.DataFrame({'Rent_GBP': rents[r], 'Price_GBP': prices[r]}
                        ).loc[SAMPLE_START:SAMPLE_END].dropna()
    df_r['Region'] = r
    reg_rows.append(df_r.reset_index().rename(columns={'index': 'Date'}))
reg = pd.concat(reg_rows, ignore_index=True)[['Date', 'Region', 'Rent_GBP', 'Price_GBP']]
reg['Date'] = pd.to_datetime(reg['Date']).dt.strftime('%Y-%m-%d')
reg.to_csv(CLEAN / "uk_housing_monthly_regions.csv", index=False)
print(f"  uk_housing_monthly_regions.csv: {len(reg)} rows, {reg['Region'].nunique()} regions")

# --- Representative-England dataset (composition-consistent, population-weighted) ---
# The headline UK HPI England price (transaction-mix) and PIPR England rent (tenancy-mix,
# heavily weighted to London's large rental sector) weight the regions DIFFERENTLY, so
# dividing one by the other gives a national price-to-rent ratio BELOW that of any single
# region. To compare like with like, we build the price AND rent of a representative English
# dwelling as the SAME population-weighted average of the nine regions (fixed weights), so
# both share one regional composition. This is the model's national input.
# Weights: ONS mid-2023 regional population estimates (millions), approximate.
REGION_POP = {
    'North East': 2.65, 'North West': 7.52, 'Yorkshire and The Humber': 5.56,
    'East Midlands': 5.02, 'West Midlands': 6.11, 'East of England': 6.40,
    'London': 8.87, 'South East': 9.46, 'South West': 5.80,
}
wsum = sum(REGION_POP.values())
rep_price = sum(REGION_POP[r] / wsum * prices[r] for r in REGIONS)
rep_rent = sum(REGION_POP[r] / wsum * rents[r] for r in REGIONS)
repdf = pd.DataFrame({
    'Rent_GBP': rep_rent, 'Purchase_Price_GBP': rep_price, 'Mortgage_Rate_pct': rate,
}).loc[SAMPLE_START:SAMPLE_END].dropna()
assert repdf.index.equals(expected), "Representative dataset incomplete"
rep_out = repdf.reset_index().rename(columns={'index': 'Date'})
rep_out['Date'] = rep_out['Date'].dt.strftime('%Y-%m-%d')
rep_out.to_csv(CLEAN / "uk_housing_monthly_representative.csv", index=False)
pr_rep = repdf['Purchase_Price_GBP'].iloc[-1] / (repdf['Rent_GBP'].iloc[-1] * 12)
pr_eng = eng['Purchase_Price_GBP'].iloc[-1] / (eng['Rent_GBP'].iloc[-1] * 12)
print(f"  uk_housing_monthly_representative.csv: {len(repdf)} months")
print(f"    Rep price GBP {repdf['Purchase_Price_GBP'].iloc[0]:,.0f} -> {repdf['Purchase_Price_GBP'].iloc[-1]:,.0f}; "
      f"rent GBP {repdf['Rent_GBP'].iloc[0]:.0f} -> {repdf['Rent_GBP'].iloc[-1]:.0f}")
print(f"    Representative P/R (latest) = {pr_rep:.1f}  vs mismatched UK-HPI/PIPR England P/R = {pr_eng:.1f}")

# --- Returns & gilts ---
ret_out = returns.reset_index()
ret_out['Date'] = ret_out['Date'].dt.strftime('%Y-%m-%d')
ret_out.to_csv(CLEAN / "uk_stock_returns_gbp.csv", index=False)
print(f"  uk_stock_returns_gbp.csv: {len(ret_out)} months")

g_out = gilts.reset_index()
g_out['Date'] = g_out['Date'].dt.strftime('%Y-%m-%d')
g_out.to_csv(CLEAN / "uk_gilt_yield_10y.csv", index=False)
print(f"  uk_gilt_yield_10y.csv: {len(g_out)} months")

print("\nDONE.")
