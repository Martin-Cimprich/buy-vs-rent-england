#!/usr/bin/env python3
"""
Prepare UK data for the buy-vs-rent whitepaper (v3 pipeline, revision round 4).

Inputs (data/raw/UK_Data/, refreshed 2026-09-01):
  1. UKHPI_full_file_2026-06.csv        — HM Land Registry UK HPI (all-dwellings
                                          average price, monthly, 405 geographies)
  2. priceindexofprivaterentsukhistoricalseries.xlsx
                                        — ONS PIPR historical series, Table 3 =
                                          average rent GBP/month, WIDE format,
                                          Jan 2005 - Feb 2025 (England + regions)
  3. pipr_monthly_2026-08-19.xlsx       — ONS PIPR live monthly file, Table 1 =
                                          LONG format, Jan 2015 - May 2026
  4. BoE_quoted_rates_fixed_2y5y_75_90_95LTV.csv + BoE_quoted_5y_90LTV_IUMZO28.csv
                                        — BoE quoted fixed rates used to build the
                                          FTB 5-year 90% LTV rate (see section 3)
     BoE_effective_rates_new_advances_CFMBJ95.csv
                                        — CFMBJ95, retained for the floating case
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
  - uk_housing_monthly_england.csv   (Date, Rent_GBP, Purchase_Price_GBP,
                                       Mortgage_Rate_pct = FTB 5y 90% LTV,
                                       Mortgage_Rate_CFMBJ95_pct = floating case)
  - uk_housing_monthly_regions.csv   (Date, Region, Rent_GBP, Price_GBP)
  - uk_stock_returns_gbp.csv         (Date, acwi_net_gbp_ret, acwi_gross_gbp_ret, ftse100_tr_ret)
  - uk_gilt_yield_10y.csv            (Date, yield_pct)
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import pandas as pd
import numpy as np
from pathlib import Path

BASE = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAW = BASE / "data" / "raw"
D08 = RAW / "boe"
D09 = RAW / "financial"
D0901 = RAW / "ons"     # revision-round-4 refresh
CLEAN = BASE / "data" / "clean"
CLEAN.mkdir(parents=True, exist_ok=True)

SAMPLE_START = pd.Timestamp('2005-01-31')
# End at the last month for which prices, rents AND mortgage rates all exist.
# UK HPI is the binding constraint: the 2026-07 full file does not exist yet
# (404), so June 2026 is the latest vintage. PIPR reaches July 2026 but cannot
# extend the sample past the price series.
SAMPLE_END = pd.Timestamp('2026-06-30')

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
hpi = pd.read_csv(D0901 / "UKHPI_full_file_2026-06.csv",
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
live_raw = pd.read_excel(D0901 / "pipr_monthly_2026-08-19.xlsx",
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
# 3. MORTGAGE RATE — first-time-buyer 5-year fixed at 90% LTV
# ============================================================================
# The baseline borrower is a first-time buyer on a FIVE-YEAR FIXED rate at 90%
# LTV, refixing at the prevailing 5-year rate every 60 months. That is what
# English FTBs actually do: 99.1% of FTB new lending in 2025 H1 was fixed-rate
# (SVR at origination 0.018%), and the >3-5 year band is the FTB modal choice in
# six of the seven periods for which the FCA publishes the split. Source: FCA
# PSD001 via FOI2025/01252 Annex B, monthly Jan 2019 - Jun 2025.
#
# No single BoE series covers this for the whole sample, so it is CONSTRUCTED:
#
#   2019-02 .. end     IUMZO28 directly (5y, 90% LTV) — the published series
#   2008-05 .. 2019-01 IUMBV42 (5y, 75% LTV) + [IUMB482 - IUMBV34], i.e. the
#                      5-year 75% LTV rate plus the MEASURED 90-vs-75 LTV
#                      premium observed at the 2-year tenor
#   2005-01 .. 2008-04 IUMBV42 + k x [IUM2WTL - IUMBV34], where k is the median
#                      ratio of the 90-vs-75 premium to the 95-vs-75 premium
#                      over the months where both exist. The 90% LTV series
#                      begins 2008-05; the 95% LTV series reaches back to 1995.
#   2009-03 .. 2009-05 linear interpolation (3 months; IUMB482 missing)
#
# The 2-year-to-5-year tenor transplant is VALIDATED rather than assumed: over
# the 90 months where the true 5-year 90% LTV premium exists (2019-02..2026-07),
# the 2-year proxy premium has a mean bias of +0.003pp against it, sd 0.214pp,
# correlation 0.911. The script re-checks this and aborts if the bias exceeds
# 0.05pp.
#
# A CONSTANT add-on would not do. The measured 90-vs-75 premium averaged
# +2.20pp over 2010-14, when high-LTV credit was rationed, against +0.51pp over
# 2023-26 — a 1.7pp swing, concentrated in exactly the years that decide a
# buy-versus-rent result over this sample.
#
# CFMBJ95, the previous baseline, is retained as a second column. It is the
# volume-weighted effective rate on ALL new advances, blended across LTVs and
# fixation lengths; recasting it monthly removes the fixation cliff that is the
# main channel through which a UK first-time buyer is exposed to rate moves. It
# is kept for the floating-rate bounding case in the robustness section.
print("\n" + "=" * 70)
print("3. Mortgage rate — FTB 5-year fixed, 90% LTV (constructed)")
print("=" * 70)


def _load_boe(path, cols):
    """BoE IADB CSV: a preamble, then a header row whose first cell is DATE."""
    raw = pd.read_csv(path, header=None, names=range(12), dtype=str)
    hdr = raw[raw[0] == 'DATE'].index[0]
    df = raw.iloc[hdr + 1:].copy()
    df.columns = raw.iloc[hdr].tolist()
    df = df.loc[:, [c for c in df.columns if isinstance(c, str) and c.strip()]]
    df['Date'] = month_end(pd.to_datetime(df['DATE'], format='%d %b %Y', errors='coerce'))
    df = df.dropna(subset=['Date']).set_index('Date').sort_index()
    for c in cols:
        df[c] = pd.to_numeric(df[c], errors='coerce')
    return df[cols]


q = _load_boe(D0901 / "BoE_quoted_rates_fixed_2y5y_75_90_95LTV.csv",
              ['IUMBV34', 'IUMBV42', 'IUMB482', 'IUM2WTL', 'IUMTLMV'])
z = _load_boe(D0901 / "BoE_quoted_5y_90LTV_IUMZO28.csv", ['IUMZO28'])
# IUM5WTL: the 5-year 95% LTV series. Not in the current Bankstats headline set,
# but published back to 1995 - it is what makes an all-5-year construction possible.
w95 = _load_boe(D0901 / "BoE_quoted_95LTV_2y5y_IUM2WTL_IUM5WTL.csv", ['IUM5WTL'])
q = q.join(z, how='outer').join(w95, how='outer')

prem_2y = q['IUMB482'] - q['IUMBV34']          # 90-vs-75 LTV premium, 2y tenor
prem_95 = q['IUM2WTL'] - q['IUMBV34']          # 95-vs-75 LTV premium, 2y tenor
prem_5y_true = q['IUMZO28'] - q['IUMBV42']     # 90-vs-75 LTV premium, 5y tenor

# --- validate the tenor transplant on the overlap ---
val = pd.concat([prem_5y_true.rename('true'), prem_2y.rename('proxy')], axis=1).dropna()
bias = (val['proxy'] - val['true']).mean()
print(f"  tenor transplant check: n={len(val)} months "
      f"({val.index[0]:%Y-%m}..{val.index[-1]:%Y-%m}), "
      f"proxy-minus-true bias {bias:+.4f}pp, sd {(val['proxy']-val['true']).std():.3f}pp, "
      f"corr {val['true'].corr(val['proxy']):.3f}")
assert abs(bias) < 0.05, f"2y->5y premium transplant bias too large: {bias:+.4f}pp"

# --- scale factor for the pre-2008-05 window, where only 95% LTV exists ---
ratio_src = pd.concat([prem_2y.rename('p90'), prem_95.rename('p95')], axis=1).dropna()
ratio_src = ratio_src[ratio_src['p95'].abs() > 0.05]
k = float(ratio_src['p90'].div(ratio_src['p95']).median())
print(f"  90%/95% premium ratio k = {k:.3f} (median over {len(ratio_src)} overlapping months)")

# --- assemble the premium, then the rate ---
premium = prem_2y.copy()
early = premium.index < pd.Timestamp('2008-05-31')
premium.loc[early] = (k * prem_95).loc[early]
premium = premium.interpolate(limit_area='inside')      # fills 2009-03..2009-05

# --- three LTV bands, because lenders price in bands and the borrower moves
#     between them as the loan amortises. Charging the origination-LTV premium at
#     every refix would overstate the cost of owning badly: a Jan-2005 buyer at
#     90% LTV is at 74.8% LTV by their Jan-2010 refix.
#
# The 90% band is built from FIVE-YEAR data only, interpolating in LTV between
# the published 5-year 75% and 95% series. This replaces an earlier construction
# that added the 2-year LTV premium to the 5-year 75% rate. That transplant is
# unbiased after 2019 but fails badly in the credit crunch, because the LTV
# premium COMPRESSES at longer tenors when high-LTV credit is rationed: BoE's own
# data give a 5y-minus-2y term premium of +0.45pp at 75% LTV but only +0.27pp at
# 95% LTV, and London & Country measured the 5-year 90%-vs-low-LTV gap at 2.02pp
# in April 2009 against "over 3%" at two years. The transplant put Jan 2010 at
# 8.20%; the market was 6.5-7.5%, centring 6.8-6.9% (Yorkshire BS 6.49%,
# Nationwide 6.73%, Santander 6.89%, Halifax an outlier at 7.49%).
rate_75 = q['IUMBV42']                                   # published, full history
rate_95_5y = q['IUM5WTL']                                # published 5y 95% LTV

# weight fitted against the published 5-year 90% series on its 90-month overlap;
# 0.55 rather than the 0.75 that linear-in-LTV would imply, because the rate
# premium is convex in LTV and accelerates towards 95%.
W90 = 0.55
interp_90 = rate_75 + W90 * (rate_95_5y - rate_75)
_chk = (interp_90 - q['IUMZO28']).dropna()
print(f"  LTV interpolation check (w={W90}): n={len(_chk)}, bias {_chk.mean():+.4f}pp, "
      f"sd {_chk.std():.3f}pp")
assert abs(_chk.mean()) < 0.10, f"LTV interpolation bias too large: {_chk.mean():+.4f}pp"

# The 95% LTV market closed after the crisis: IUM5WTL is unpublished for all 61
# months Oct 2008 - Oct 2013 because fewer than three lenders offered the product
# (BoE suppression rule). Patch that window with the 2-year 90% series plus a
# 0.30pp term premium - the rule that best fits 30+ verified product quotes -
# then ramp a linear offset across the gap so the series joins continuously at
# both ends rather than stepping.
# IUMB482 is itself unpublished for Mar-May 2009, so interpolate those three
# months before using it as the patch. (Adding with fill_value=0 here would
# silently substitute a ZERO rate - it produced -0.32% before this was caught.)
iumb482 = q['IUMB482'].interpolate(limit_area='inside')
patch = iumb482 + 0.30
# The patch is used un-shifted. It disagrees with the LTV interpolation by about
# 0.3pp at the window edges, and the patch is the side to trust there: it is
# calibrated to 30+ verified product quotes over exactly this period, whereas the
# interpolation cannot be evaluated at all inside the window. The resulting ~0.3pp
# step at each seam is a real limitation and belongs in the data appendix.
rate_90 = q['IUMZO28'].combine_first(interp_90).combine_first(patch)
_seam_lo = float(interp_90.get(pd.Timestamp('2008-09-30'), float('nan'))
                 - patch.get(pd.Timestamp('2008-09-30'), float('nan')))
_seam_hi = float(interp_90.get(pd.Timestamp('2013-11-30'), float('nan'))
                 - patch.get(pd.Timestamp('2013-11-30'), float('nan')))
print(f"  61-month 95%-LTV gap patched from the 2-year 90% series +0.30pp; "
      f"seam step {_seam_lo:+.2f}pp at Sep 2008, {_seam_hi:+.2f}pp at Nov 2013")
print(f"  Jan 2010 = {rate_90.loc['2010-01-31']:.2f}% (verified market 6.8-6.9%)")
assert rate_90.loc[SAMPLE_START:SAMPLE_END].min() > 0.2, \
    f"Implausible 90% LTV rate: min {rate_90.loc[SAMPLE_START:SAMPLE_END].min():.3f}%"

# 95% band, for the high-LTV sensitivity. Observed where published; over the
# 61-month closure there was no 95% LTV market to observe, so the sensitivity
# cannot be run there and the series is left as the patched 90% band plus the
# measured 95-vs-90 gap. Flag this in the text rather than implying a rate existed.
_g = (rate_95_5y - interp_90).dropna()
rate_95 = rate_95_5y.combine_first(rate_90 + _g.median())
print(f"  95% band: {rate_95_5y.notna().sum()} months observed; "
      f"gap over the 90% band {_g.median():+.2f}pp used where unobserved")

bands = pd.DataFrame({'rate_75': rate_75, 'rate_90': rate_90, 'rate_95': rate_95})
bands = bands.loc[SAMPLE_START:SAMPLE_END].dropna()
rate = rate_90.loc[SAMPLE_START:SAMPLE_END].dropna()      # origination rate at 90% LTV
print(f"  band means over the sample: 75% {bands.rate_75.mean():.2f}%  "
      f"90% {bands.rate_90.mean():.2f}%  95% {bands.rate_95.mean():.2f}%")

full_range = pd.date_range(SAMPLE_START, min(rate.index[-1], SAMPLE_END), freq='ME')
missing = full_range.difference(rate.index)
assert len(missing) == 0, f"Gaps in the constructed FTB rate: {list(missing)[:6]}"
print(f"  FTB 5y 90% LTV rate: {rate.index[0]:%Y-%m} -> {rate.index[-1]:%Y-%m} "
      f"({len(rate)} months); range {rate.min():.2f}%..{rate.max():.2f}%; "
      f"mean {rate.mean():.2f}%")
for a, b in [('2005', '2007'), ('2010', '2014'), ('2015', '2019'), ('2023', '2026')]:
    w = rate.loc[a:b]
    print(f"    {a}-{b}: mean {w.mean():.2f}%  "
          f"(over the 75% band {(rate_90 - rate_75).loc[a:b].mean():+.2f}pp)")

# --- CFMBJ95, retained for the floating bounding case ---
cf = _load_boe(D0901 / "BoE_effective_rates_new_advances_CFMBJ95.csv", ['CFMBJ95'])
rate_float = cf['CFMBJ95'].dropna().sort_index()

# --- Bank Rate, for the renter-leverage sensitivity (comments.txt item 5) ------
# Interactive Brokers (U.K.) prices retail margin at benchmark + 1.50% on the
# first GBP 80,000 and + 1.00% above (live page, 1 Sep 2026). Bank Rate + 1.50%
# reproduces the current Tier I retail rate to within 2bp and is the only
# version implementable over a 2005-2026 backtest, so Bank Rate is carried
# through here and the spread applied in the engine. Do NOT backtest at today's
# flat 5.227%: Bank Rate averaged 2.00% over the sample.
br = _load_boe(D0901 / "BoE_bank_rate_IUMABEDR.csv", ['IUMABEDR'])
bank_rate = br['IUMABEDR'].dropna().sort_index()
print(f"  Bank Rate (IUMABEDR): {bank_rate.index[0]:%Y-%m} -> {bank_rate.index[-1]:%Y-%m}; "
      f"mean over sample {bank_rate.loc[SAMPLE_START:SAMPLE_END].mean():.2f}%, "
      f"{(bank_rate.loc[SAMPLE_START:SAMPLE_END] <= 0.5).sum()} of "
      f"{len(bank_rate.loc[SAMPLE_START:SAMPLE_END])} months at or below 0.50%")
print(f"  CFMBJ95 (floating bounding case): {rate_float.index[0]:%Y-%m} -> "
      f"{rate_float.index[-1]:%Y-%m}; mean over sample "
      f"{rate_float.loc[SAMPLE_START:SAMPLE_END].mean():.2f}%")
print(f"  FTB-minus-CFMBJ95 over the sample: "
      f"{(rate - rate_float).loc[SAMPLE_START:SAMPLE_END].mean():+.2f}pp mean")

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

acwi_net = levels_to_returns(D0901 / "msci_acwi_netr_gbp.csv")
acwi_gross = levels_to_returns(D0901 / "msci_acwi_grtr_gbp.csv")
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
gilts = pd.read_csv(D09 / "fred_uk_10y_gilt_monthly.csv")
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
    'Mortgage_Rate_CFMBJ95_pct': rate_float,
    'Rate_75LTV_pct': bands['rate_75'],
    'Rate_90LTV_pct': bands['rate_90'],
    'Rate_95LTV_pct': bands['rate_95'],
    'Bank_Rate_pct': bank_rate,
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
    'Rent_GBP': rep_rent, 'Purchase_Price_GBP': rep_price,
    'Mortgage_Rate_pct': rate, 'Mortgage_Rate_CFMBJ95_pct': rate_float,
    'Rate_75LTV_pct': bands['rate_75'],
    'Rate_90LTV_pct': bands['rate_90'],
    'Rate_95LTV_pct': bands['rate_95'],
    'Bank_Rate_pct': bank_rate,
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
