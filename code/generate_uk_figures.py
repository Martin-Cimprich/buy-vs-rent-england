#!/usr/bin/env python3
"""
Generate ALL figures for whitepaper/overleaf_uk/figures/ (uk_v1_*.png).

Mirrors generate_overleaf_v5_figures.py (CZ) with a neutral academic palette.
Reads clean data + output/tables/UK/ results produced by full_run_uk.py.
"""
import sys, os, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as mticker
from matplotlib.patches import Polygon as MplPolygon
from matplotlib.collections import PatchCollection
import numpy as np
import pandas as pd

plt.rcParams['font.family'] = 'DejaVu Sans'
plt.rcParams['axes.unicode_minus'] = False

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "code"))
CLEAN = os.path.join(BASE, "data", "clean")
TBL = os.path.join(BASE, "output", "tables")

# --journal: vector PDFs without figure-level titles (titles live in LaTeX
# captions), written to the working-paper folder. Default: styled PNGs for the
# web/policy edition.
JOURNAL = '--journal' in sys.argv
FIG = os.path.join(BASE, "paper", "src", "figures") if JOURNAL else os.path.join(BASE, "output", "figures")
GEO = os.path.join(BASE, "data", "raw", "geo", "english_regions.geojson")
os.makedirs(FIG, exist_ok=True)


def T(s):
    """Figure-level title: suppressed in journal mode (caption carries it)."""
    return None if JOURNAL else s

# --- palette (neutral academic) ---
NAVY = "#1F4E79"     # BUY
CLARET = "#8B2E3D"   # RENT+INVEST
TEAL = "#2E7D6B"     # tertiary (gilts / FTSE)
GOLD = "#B8860B"
BLACK = "#1A1A1A"
GRAY = "#6B6B6B"
DPI = 200


def style_ax(ax, title=None, xlabel=None, ylabel=None, grid=True):
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color(GRAY)
    ax.spines['bottom'].set_color(GRAY)
    ax.tick_params(colors=GRAY, labelsize=9)
    if grid:
        ax.grid(True, alpha=0.25, color=GRAY, linewidth=0.5)
    if title:
        ax.set_title(title, fontsize=12, fontweight='bold', color=BLACK, pad=10)
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=10, color=GRAY)
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=10, color=GRAY)


def save(fig, name):
    if JOURNAL:
        name = name.replace('.png', '.pdf')
    path = os.path.join(FIG, name)
    fig.savefig(path, dpi=DPI, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    print(f"  SAVED  {name}  ({os.path.getsize(path)/1024:.0f} KB)")


# --- data (national analysis uses the representative-England series) ---
eng = pd.read_csv(os.path.join(CLEAN, 'uk_housing_monthly_representative.csv'), parse_dates=['Date']).set_index('Date')
rets = pd.read_csv(os.path.join(CLEAN, 'uk_stock_returns_gbp.csv'), parse_dates=['Date']).set_index('Date')
paths = pd.read_csv(os.path.join(TBL, 'uk_single_start_paths.csv'), parse_dates=['date'])
rolling = pd.read_csv(os.path.join(TBL, 'uk_rolling_cohorts.csv'), parse_dates=['start_date'])
rar_hist = pd.read_csv(os.path.join(TBL, 'uk_rar_historical.csv'), parse_dates=['date'])
rar_reg = pd.read_csv(os.path.join(TBL, 'uk_regional_results.csv'))
KEY = json.load(open(os.path.join(TBL, 'uk_key_numbers.json'), encoding='utf-8'))

sample = eng.loc['2005-01-31':'2026-04-30']

print("=" * 70)
print("UK WHITEPAPER FIGURES")
print("=" * 70)

# ----------------------------------------------------------------------------
# 1. Market overview (3 panels)
# ----------------------------------------------------------------------------
print("[ 1/12] uk_v1_market_overview.png")
fig, axes = plt.subplots(3, 1, figsize=(10, 9), sharex=True)
if not JOURNAL:
    fig.suptitle("The English housing market (2005-2026)",
                 fontsize=14, fontweight='bold', color=BLACK, y=0.98)
axes[0].plot(sample.index, sample['Purchase_Price_GBP'] / 1e3, color=NAVY, lw=2)
style_ax(axes[0], title="Average house price (all dwellings, England)", ylabel="GBP thousand")
axes[1].plot(sample.index, sample['Rent_GBP'], color=CLARET, lw=2)
style_ax(axes[1], title="Average private rent (England)", ylabel="GBP / month")
axes[2].plot(sample.index, sample['Mortgage_Rate_pct'], color=TEAL, lw=2)
style_ax(axes[2], title="Effective mortgage rate on new advances (CFMBJ95)", ylabel="% p.a.")
axes[2].xaxis.set_major_locator(mdates.YearLocator(2))
axes[2].xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
fig.tight_layout(rect=[0, 0, 1, 0.97])
save(fig, 'uk_v1_market_overview.png')

# ----------------------------------------------------------------------------
# 2. Stock market vs house prices (indexed)
# ----------------------------------------------------------------------------
print("[ 2/12] uk_v1_stock_returns.png")
common = rets.loc['2005-01-31':'2026-04-30']
acwi_idx = (1 + common['acwi_net_gbp_ret']).cumprod() * 100
ftse_idx = (1 + common['ftse100_tr_ret']).cumprod() * 100
price_idx = sample['Purchase_Price_GBP'] / sample['Purchase_Price_GBP'].iloc[0] * 100
fig, ax = plt.subplots(figsize=(10, 5.5))
ax.plot(acwi_idx.index, acwi_idx, color=CLARET, lw=2, label='MSCI ACWI (net TR, GBP)')
ax.plot(ftse_idx.index, ftse_idx, color=TEAL, lw=1.8, label='FTSE 100 (total return)')
ax.plot(price_idx.index, price_idx, color=NAVY, lw=2, label='England house prices')
style_ax(ax, title=T("Global equities, UK equities and English house prices (Jan 2005 = 100)"),
         ylabel="Index (Jan 2005 = 100)")
ax.legend(frameon=False, fontsize=9)
ax.xaxis.set_major_locator(mdates.YearLocator(2))
ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
save(fig, 'uk_v1_stock_returns.png')

# ----------------------------------------------------------------------------
# 3. Single-start wealth paths
# ----------------------------------------------------------------------------
print("[ 3/12] uk_v1_single_wealth.png")
fig, ax = plt.subplots(figsize=(10, 5.5))
ax.plot(paths['date'], paths['buy_equity'] / 1e3, color=NAVY, lw=2, label='BUY (home equity)')
ax.plot(paths['date'], paths['portfolio'] / 1e3, color=CLARET, lw=2, label='RENT+INVEST (portfolio)')
ax.axhline(0, color=GRAY, ls='--', alpha=0.5, lw=0.8)
style_ax(ax, title=T("Wealth accumulation: buying vs renting with investing (Jan 2005 cohort)"),
         ylabel="GBP thousand")
ax.legend(frameon=False, fontsize=9, loc='upper left')
ax.xaxis.set_major_locator(mdates.YearLocator(2))
ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
save(fig, 'uk_v1_single_wealth.png')

# ----------------------------------------------------------------------------
# 4. Single-start cash flows
# ----------------------------------------------------------------------------
print("[ 4/12] uk_v1_single_cashflows.png")
fig, ax = plt.subplots(figsize=(10, 5.5))
ax.plot(paths['date'], paths['owner_outflow'], color=NAVY, lw=1.8,
        label='Owner outflow (mortgage + maintenance)')
ax.plot(paths['date'], paths['rent'], color=CLARET, lw=1.8, label='Rent')
ax.fill_between(paths['date'], paths['owner_outflow'], paths['rent'],
                where=paths['owner_outflow'] >= paths['rent'],
                color=CLARET, alpha=0.12, label='Renter invests the difference')
ax.fill_between(paths['date'], paths['owner_outflow'], paths['rent'],
                where=paths['owner_outflow'] < paths['rent'],
                color=NAVY, alpha=0.12, label='Renter withdraws the difference')
style_ax(ax, title=T("Monthly housing cash flows (Jan 2005 cohort)"), ylabel="GBP / month")
ax.legend(frameon=False, fontsize=9, loc='upper left')
ax.xaxis.set_major_locator(mdates.YearLocator(2))
ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
save(fig, 'uk_v1_single_cashflows.png')

# ----------------------------------------------------------------------------
# 5. Payments vs prices (2 panels)
# ----------------------------------------------------------------------------
print("[ 5/12] uk_v1_single_payments_prices.png")
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), sharex=True)
ax1.plot(paths['date'], paths['mortgage_payment'], color=NAVY, lw=1.8, label='Mortgage payment')
ax1.plot(paths['date'], paths['maintenance'], color=GOLD, lw=1.5, label='Maintenance & depreciation')
ax1.plot(paths['date'], paths['rent'], color=CLARET, lw=1.8, label='Rent')
style_ax(ax1, title="Components of monthly costs (Jan 2005 cohort)", ylabel="GBP / month")
ax1.legend(frameon=False, fontsize=9, loc='upper left')
ax2.plot(paths['date'], paths['home_value'] / 1e3, color=NAVY, lw=2, label='Property value')
ax2.plot(paths['date'], paths['mortgage_balance'] / 1e3, color=GRAY, lw=1.6, ls='--',
         label='Mortgage balance')
style_ax(ax2, title="Property value and mortgage balance", ylabel="GBP thousand")
ax2.legend(frameon=False, fontsize=9)
ax2.xaxis.set_major_locator(mdates.YearLocator(2))
ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
fig.tight_layout()
save(fig, 'uk_v1_single_payments_prices.png')

# ----------------------------------------------------------------------------
# 6. Rolling cohorts: R by start date
# ----------------------------------------------------------------------------
print("[ 6/12] uk_v1_rolling_distribution.png")
fig, ax = plt.subplots(figsize=(11, 5.5))
colors = [CLARET if w == 'RENT' else NAVY for w in rolling['winner']]
ax.bar(rolling['start_date'], rolling['R'] - 1, bottom=1, width=80, color=colors, alpha=0.85)
ax.axhline(1, color=BLACK, lw=1)
style_ax(ax, title=T("Renter/owner wealth ratio R by cohort start date (all cohorts end Apr 2026)"),
         ylabel="R = renter wealth / owner wealth")
from matplotlib.patches import Patch
ax.legend(handles=[Patch(color=NAVY, label='BUY wins (R < 1)'),
                   Patch(color=CLARET, label='RENT+INVEST wins (R > 1)')],
          frameon=False, fontsize=9, loc='upper left')
ax.xaxis.set_major_locator(mdates.YearLocator(2))
ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
save(fig, 'uk_v1_rolling_distribution.png')

n_coh = len(rolling)
colors = [CLARET if w == 'RENT' else NAVY for w in rolling['winner']]

# ----------------------------------------------------------------------------
# 7. Predictor: mortgage rate
# ----------------------------------------------------------------------------
print("[ 7/11] uk_v1_mortgage_predictor.png")
fig, ax = plt.subplots(figsize=(10, 6))
ax.scatter(rolling['mortgage_rate'] * 100, rolling['R'], c=colors, s=42, alpha=0.85,
           edgecolors='white', linewidths=0.6)
m, c = np.polyfit(rolling['mortgage_rate'] * 100, rolling['R'], 1)
xs = np.linspace(rolling['mortgage_rate'].min() * 100, rolling['mortgage_rate'].max() * 100, 50)
ax.plot(xs, m * xs + c, color=BLACK, lw=1.4, ls='--')
ax.axhline(1, color=GRAY, ls=':', lw=1)
style_ax(ax, title=T(f"Mortgage rate at purchase vs final wealth ratio ({n_coh} cohorts)"),
         xlabel="Effective mortgage rate at cohort start (% p.a.)",
         ylabel="R = renter wealth / owner wealth")
save(fig, 'uk_v1_mortgage_predictor.png')

# ----------------------------------------------------------------------------
# 8. Predictor: price/rent ratio
# ----------------------------------------------------------------------------
print("[ 8/11] uk_v1_priceratio_predictor.png")
fig, ax = plt.subplots(figsize=(10, 6))
ax.scatter(rolling['pr_ratio'], rolling['R'], c=colors, s=42, alpha=0.85,
           edgecolors='white', linewidths=0.6)
m, c = np.polyfit(rolling['pr_ratio'], rolling['R'], 1)
xs = np.linspace(rolling['pr_ratio'].min(), rolling['pr_ratio'].max(), 50)
ax.plot(xs, m * xs + c, color=BLACK, lw=1.4, ls='--')
ax.axhline(1, color=GRAY, ls=':', lw=1)
style_ax(ax, title=T(f"Price-to-rent ratio at purchase vs final wealth ratio ({n_coh} cohorts)"),
         xlabel="Price / annual rent at cohort start",
         ylabel="R = renter wealth / owner wealth")
save(fig, 'uk_v1_priceratio_predictor.png')

# ----------------------------------------------------------------------------
# 9. Price/rent dynamics (2 panels)
# ----------------------------------------------------------------------------
print("[ 9/11] uk_v1_price_rent_dynamics.png")
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), sharex=True)
p_idx = sample['Purchase_Price_GBP'] / sample['Purchase_Price_GBP'].iloc[0] * 100
r_idx = sample['Rent_GBP'] / sample['Rent_GBP'].iloc[0] * 100
ax1.plot(p_idx.index, p_idx, color=NAVY, lw=2, label='House prices')
ax1.plot(r_idx.index, r_idx, color=CLARET, lw=2, label='Rents')
style_ax(ax1, title="House prices and rents in England (Jan 2005 = 100)", ylabel="Index")
ax1.legend(frameon=False, fontsize=9, loc='upper left')
pr = sample['Purchase_Price_GBP'] / (sample['Rent_GBP'] * 12)
ax2.plot(pr.index, pr, color=BLACK, lw=2)
ax2.axhline(pr.mean(), color=GRAY, ls='--', lw=1, label=f'2005-2026 mean ({pr.mean():.1f})')
style_ax(ax2, title="Price-to-rent ratio (price / annual rent)", ylabel="P/R ratio")
ax2.legend(frameon=False, fontsize=9)
ax2.xaxis.set_major_locator(mdates.YearLocator(2))
ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
fig.tight_layout()
save(fig, 'uk_v1_price_rent_dynamics.png')

# ----------------------------------------------------------------------------
# 10. Regional historical results (single-start R + cohort buy-win %)
# ----------------------------------------------------------------------------
print("[10/12] uk_v1_regional_results.png")
rd = rar_reg.sort_values('R_single')
short = {'Yorkshire and The Humber': 'Yorkshire & Humber'}
labels = [short.get(x, x) for x in rd['region']]
y = np.arange(len(rd))
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 5.2), sharey=True)
ax1.barh(y, rd['R_single'], color=[CLARET if v > 1 else NAVY for v in rd['R_single']], alpha=0.85)
ax1.axvline(1, color=BLACK, lw=1)
ax1.set_yticks(y, labels, fontsize=9)
style_ax(ax1, title="Single-start wealth ratio R (2005 cohort)", xlabel="R = renter / owner", grid=False)
ax1.grid(True, axis='x', alpha=0.25, color=GRAY, linewidth=0.5)
ax2.barh(y, rd['buy_win'] * 100, color=NAVY, alpha=0.85)
ax2.axvline(50, color=GRAY, ls='--', lw=0.8)
style_ax(ax2, title="Cohorts won by buying (%)", xlabel="% of 85 cohorts", grid=False)
ax2.grid(True, axis='x', alpha=0.25, color=GRAY, linewidth=0.5)
if not JOURNAL:
    fig.suptitle("Historical buy-vs-rent outcomes by English region (2005-2026)",
                 fontsize=13, fontweight='bold', color=BLACK, y=1.0)
fig.tight_layout(rect=[0, 0, 1, 0.96])
save(fig, 'uk_v1_regional_results.png')

# ----------------------------------------------------------------------------
# 11. Historical RAR
# ----------------------------------------------------------------------------
print("[11/12] uk_v1_historical_rar.png")
fig, ax = plt.subplots(figsize=(10, 5.5))
ax.plot(rar_hist['date'], rar_hist['rar_stocks'] * 100, color=CLARET, lw=2,
        label='Required appreciation vs global stocks')
ax.plot(rar_hist['date'], rar_hist['rar_gilts'] * 100, color=TEAL, lw=2,
        label='Required appreciation vs 10y gilts')
ax.plot(rar_hist['date'], rar_hist['actual_appr'] * 100, color=NAVY, lw=2, ls='--',
        label='Actual appreciation over the next 10 years')
ax.axhline(0, color=GRAY, ls=':', lw=1)
style_ax(ax, title=T("Required vs actual 10-year house price appreciation (England)"),
         xlabel="Purchase month", ylabel="% p.a.")
ax.legend(frameon=False, fontsize=9)
ax.xaxis.set_major_locator(mdates.YearLocator(2))
ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
save(fig, 'uk_v1_historical_rar.png')

# ----------------------------------------------------------------------------
# 11. Regional RAR map (choropleth, matplotlib-only) — muted palette, in-region labels
# ----------------------------------------------------------------------------
print("[12/12] uk_v1_regional_rar_map.png")
import matplotlib.patheffects as pe
from matplotlib.colors import LinearSegmentedColormap

gj = json.load(open(GEO, encoding='utf-8'))
rar_by_region = dict(zip(rar_reg['region'], rar_reg['rar_stocks_pct']))

# Muted parchment -> terracotta -> claret sequential, in keeping with the paper palette
cmap = LinearSegmentedColormap.from_list(
    'muted_claret', ['#EDE6DA', '#DCC2A0', '#C68F6E', '#A85A4E', '#7E2A38'])
vals = list(rar_by_region.values())
norm = plt.Normalize(min(vals) - 0.15, max(vals) + 0.1)


def ring_centroid(ring):
    """Area-weighted centroid of a polygon ring (shoelace)."""
    x, y = ring[:, 0], ring[:, 1]
    x1, y1 = np.roll(x, -1), np.roll(y, -1)
    cross = x * y1 - x1 * y
    A = cross.sum() / 2.0
    if abs(A) < 1e-9:
        return ring[:, 0].mean(), ring[:, 1].mean()
    cx = ((x + x1) * cross).sum() / (6 * A)
    cy = ((y + y1) * cross).sum() / (6 * A)
    return cx, cy


fig, ax = plt.subplots(figsize=(8.4, 10.5))
label_pts = {}
for feat in gj['features']:
    name = feat['properties']['RGN24NM']
    val = rar_by_region.get(name)
    color = cmap(norm(val)) if val is not None else '#eeeeee'
    geom = feat['geometry']
    polys = [geom['coordinates']] if geom['type'] == 'Polygon' else geom['coordinates']
    biggest, biggest_area = None, -1
    for poly in polys:
        ring = np.array(poly[0])
        ax.add_patch(MplPolygon(ring, closed=True, facecolor=color,
                                edgecolor='white', linewidth=1.1))
        area = abs(np.dot(ring[:, 0], np.roll(ring[:, 1], -1)) -
                   np.dot(np.roll(ring[:, 0], -1), ring[:, 1])) / 2.0
        if area > biggest_area:
            biggest_area, biggest = area, ring
    label_pts[name] = ring_centroid(biggest)

short = {'Yorkshire and The Humber': 'Yorkshire &\nThe Humber',
         'East of England': 'East of\nEngland', 'North East': 'North\nEast',
         'North West': 'North\nWest', 'West Midlands': 'West\nMidlands',
         'East Midlands': 'East\nMidlands', 'South East': 'South\nEast',
         'South West': 'South\nWest'}
halo = [pe.withStroke(linewidth=2.6, foreground='white')]
for name, (lon, lat) in label_pts.items():
    val = rar_by_region.get(name)
    lab = f"{short.get(name, name)}\n{val:.1f}%"
    if name == 'London':
        # London is tiny; place the label to the SE with a leader line
        ax.annotate(lab, xy=(lon, lat), xytext=(2.1, 50.7), ha='center', va='center',
                    fontsize=8.5, fontweight='bold', color=BLACK, path_effects=halo,
                    arrowprops=dict(arrowstyle='-', color=GRAY, lw=0.9,
                                    shrinkA=0, shrinkB=2))
    else:
        if name == 'South East':
            lat -= 0.12  # nudge off the London hole
        ax.annotate(lab, (lon, lat), ha='center', va='center', fontsize=8.6,
                    fontweight='bold', color=BLACK, path_effects=halo)

ax.set_xlim(-6.6, 2.6)
ax.set_ylim(49.8, 55.9)
ax.set_aspect(1.6)
ax.axis('off')
ax.set_title("Required annual house-price growth for buying to match\n"
             "renting-and-investing, by English region (April 2026, 10-year horizon)",
             fontsize=12.5, fontweight='bold', color=BLACK, pad=12)
sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
cbar = fig.colorbar(sm, ax=ax, shrink=0.5, pad=0.01)
cbar.set_label('Required appreciation (% p.a.)', fontsize=9, color=GRAY)
cbar.ax.tick_params(labelsize=8, colors=GRAY)
cbar.outline.set_edgecolor(GRAY)
save(fig, 'uk_v1_regional_rar_map.png')

print("\nALL FIGURES DONE.")
