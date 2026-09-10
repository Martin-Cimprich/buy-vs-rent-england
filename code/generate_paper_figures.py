#!/usr/bin/env python3
"""
Journal figure set for the working paper (whitepaper/paper_wp/figures).

Design rules, following field-journal conventions:
  * A restrained two-hue palette: deep blue for the owner / the dwelling,
    burnt orange for the renter / equities. Line style and marker fill are
    retained alongside colour, so every figure still survives greyscale
    printing and remains readable under deuteranopia.
  * No figure-level titles or annotations; captions carry the description.
  * Serif type matching the manuscript; vector PDF output.
  * Eight main-text figures.

The colourful PNG set for the web/policy edition is produced separately by
generate_uk_figures.py; this script does not touch it.

Run:  python generate_paper_figures.py
"""
import sys, os, io, json

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Polygon as MplPolygon
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
import numpy as np
import pandas as pd

# ---------------------------------------------------------------- paths
HERE = os.path.dirname(os.path.abspath(__file__))
BASE = (os.path.dirname(os.path.dirname(HERE))
        if os.path.basename(HERE) == 'python' else os.path.dirname(HERE))
CLEAN = os.path.join(BASE, 'data', 'clean')
for cand in [os.path.join(BASE, 'output', 'tables', 'UK'),
             os.path.join(BASE, 'output', 'tables')]:
    if os.path.isdir(cand):
        TBL = cand
        break
# The repo ships the paper as a PDF, not as LaTeX sources, so figures go to
# output/figures here. The first candidate is the author's own paper tree.
for cand in [os.path.join(BASE, 'whitepaper', 'paper_wp', 'figures'),
             os.path.join(BASE, 'output', 'figures')]:
    if os.path.isdir(os.path.dirname(cand)):
        FIG = cand
        break
os.makedirs(FIG, exist_ok=True)
GEO = None
for cand in [os.path.join(BASE, 'data', 'raw', 'UK_Data', 'downloaded_2026-07-09',
                          'english_regions.geojson'),
             os.path.join(BASE, 'data', 'raw', 'geo', 'english_regions.geojson')]:
    if os.path.exists(cand):
        GEO = cand
        break

# ---------------------------------------------------------------- style
plt.rcParams.update({
    'font.family': 'serif',
    'font.serif': ['Times New Roman', 'Nimbus Roman No9 L', 'DejaVu Serif'],
    'font.size': 9,
    'axes.labelsize': 9,
    'axes.titlesize': 9,
    'xtick.labelsize': 8,
    'ytick.labelsize': 8,
    'legend.fontsize': 8,
    'axes.linewidth': 0.6,
    'axes.unicode_minus': False,
    'figure.dpi': 200,
})

# ---------------------------------------------------------------- palette
# Two hues carry the paper's central opposition; line style and marker fill are
# retained alongside them, so every figure still reads in greyscale. Blue and
# orange are separable under deuteranopia and differ in lightness (L* ~31 vs
# ~52), which is what makes the greyscale fallback work.
BUY = '#1D4E6B'        # deep blue      - owner / buying / the dwelling
RENT = '#C4622D'       # burnt orange   - renter / renting and investing
RENT2 = '#E0A472'      # light orange   - renter's alternative asset (FTSE 100)
NEUT = '#7C848C'       # cool grey      - benchmarks, OLS fits, reference lines
FAINT = '#B9BEC4'      # pale grey      - grid, sample-mean lines
INK = '#1A1A1A'        # near-black     - map labels and annotation text
W = 6.3                # text width in inches (A4, 25 mm margins)


def style(ax, xlabel=None, ylabel=None, grid=True):
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#333333')
    ax.spines['bottom'].set_color('#333333')
    ax.tick_params(colors='#333333', width=0.6, length=3)
    if grid:
        ax.grid(True, alpha=0.35, color=FAINT, linewidth=0.4)
        ax.set_axisbelow(True)
    if xlabel:
        ax.set_xlabel(xlabel)
    if ylabel:
        ax.set_ylabel(ylabel)


def years(ax, step=3):
    ax.xaxis.set_major_locator(mdates.YearLocator(step))
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))


def save(fig, name):
    path = os.path.join(FIG, name)
    fig.savefig(path, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    print(f"  {name}  ({os.path.getsize(path)/1024:.0f} KB)")


# ---------------------------------------------------------------- data
rep = pd.read_csv(os.path.join(CLEAN, 'uk_housing_monthly_representative.csv'),
                  parse_dates=['Date']).set_index('Date').loc['2005-01-31':'2026-06-30']
rets = pd.read_csv(os.path.join(CLEAN, 'uk_stock_returns_gbp.csv'),
                   parse_dates=['Date']).set_index('Date').loc['2005-01-31':'2026-06-30']
paths = pd.read_csv(os.path.join(TBL, 'uk_single_start_paths.csv'), parse_dates=['date'])
roll = pd.read_csv(os.path.join(TBL, 'uk_cohorts_5y.csv'), parse_dates=['start_date'])
hzp = pd.read_csv(os.path.join(TBL, 'uk_horizon_panel.csv'))
rarh = pd.read_csv(os.path.join(TBL, 'uk_rar_historical.csv'), parse_dates=['date'])
reg = pd.read_csv(os.path.join(TBL, 'uk_regional_results.csv'))

print("Journal figures ->", FIG)

# ================================================================ Figure 1
# Market inputs: price, rent, price-to-rent, mortgage rate (absorbs the old
# separate price-rent dynamics figure).
fig, axg = plt.subplots(2, 2, figsize=(W, 4.4))
ax = axg.ravel()
ax[0].plot(rep.index, rep['Purchase_Price_GBP'] / 1e3, color=BUY, lw=1.1)
style(ax[0], ylabel='£000s')
ax[0].set_title('A. House price', loc='left', fontsize=8.5, pad=3)

ax[1].plot(rep.index, rep['Rent_GBP'], color=RENT, lw=1.1)
style(ax[1], ylabel='£ per month')
ax[1].set_title('B. Private rent', loc='left', fontsize=8.5, pad=3)

pr = rep['Purchase_Price_GBP'] / (rep['Rent_GBP'] * 12)
ax[2].plot(pr.index, pr, color=NEUT, lw=1.1)
ax[2].axhline(pr.mean(), color=FAINT, ls='--', lw=0.9)
style(ax[2], ylabel='ratio')
ax[2].set_title('C. Price-to-rent ratio', loc='left', fontsize=8.5, pad=3)


ax[3].plot(rep.index, rep['Mortgage_Rate_pct'], color=BUY, lw=1.1)
style(ax[3], ylabel='per cent')
ax[3].set_title('D. FTB mortgage rate, 5y fix at 90% LTV', loc='left', fontsize=8.5, pad=3)
for a in ax:
    years(a, 5)
fig.tight_layout(h_pad=0.9, w_pad=1.4)
save(fig, 'fig1_market.pdf')

# ================================================================ Figure 2
# Cumulative asset performance.
acwi = (1 + rets['acwi_net_ter_gbp_ret']).cumprod() * 100
ftse = (1 + rets['ftse100_tr_ret']).cumprod() * 100
hp = rep['Purchase_Price_GBP'] / rep['Purchase_Price_GBP'].iloc[0] * 100
fig, ax = plt.subplots(figsize=(W, 3.3))
ax.plot(acwi.index, acwi, color=RENT, lw=1.3, ls='-', label='Global equities (MSCI ACWI, net TR, GBP)')
ax.plot(ftse.index, ftse, color=RENT2, lw=1.2, ls='--', label='UK equities (FTSE 100, total return)')
ax.plot(hp.index, hp, color=BUY, lw=1.3, ls=':', label='English house prices')
style(ax, ylabel='Index, January 2005 = 100')
years(ax)
ax.legend(frameon=False, loc='upper left')
save(fig, 'fig2_assets.pdf')

# ================================================================ Figure 3
# Wealth paths, 2005 entry cohort.
fig, ax = plt.subplots(figsize=(W, 3.3))
ax.plot(paths['date'], paths['buy_equity'] / 1e3, color=BUY, lw=1.3, ls='-',
        label='Buyer: home equity net of mortgage')
ax.plot(paths['date'], paths['portfolio'] / 1e3, color=RENT, lw=1.3, ls='--',
        label='Renter: investment portfolio')
style(ax, ylabel='£000s')
years(ax)
ax.legend(frameon=False, loc='upper left')
save(fig, 'fig3_wealth.pdf')

# ================================================================ Figure 4
# Rolling cohort outcomes.
fig, ax = plt.subplots(2, 1, figsize=(W, 5.6))

# Panel A: outcome by entry month, fixed five-year holds
for _, c in roll.iterrows():
    ax[0].bar(c['start_date'], c['R'] - 1, bottom=1, width=26,
              color=(BUY if c['R'] < 1 else RENT),
              edgecolor='none', linewidth=0)
ax[0].axhline(1, color=INK, lw=0.8)
style(ax[0], ylabel='Wealth ratio $R$')
years(ax[0], 2)
ax[0].set_title('A. Outcome by entry month, five-year holds', loc='left', pad=6)
ax[0].legend(handles=[Patch(facecolor=BUY, label='Buying won ($R<1$)'),
                      Patch(facecolor=RENT, label='Renting won ($R>1$)')],
             frameon=False, loc='upper right')

# Panel B: how the outcome depends on the holding period.
# Two series on two axes, because the count of wins and the size of the gap
# tell different stories: buying wins more often past five years, while the
# wealth ratio stays close to one throughout. The panel stops at ten years,
# the longest horizon this sample can support.
ax[1].plot(hzp['horizon_years'], hzp['buy_win_pct'], color=BUY, lw=1.4,
           marker='o', ms=3.4, label='Cohorts won by buying (left)')
ax[1].axhline(50, color=NEUT, ls='--', lw=0.9)
ax[1].set_ylim(-4, 100)
ax[1].set_xticks([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
ax[1].set_xlim(0.5, 10.5)
style(ax[1], xlabel='Holding period (years)',
      ylabel='Cohorts won by buying (%)')
ax[1].set_title('B. Outcome by holding period', loc='left', pad=6)

# Median R only. Mean R is deliberately not plotted here: at holds of one to
# four years the owner has paid the round-trip costs and amortised almost
# nothing, so R's denominator is small and the mean is unstable (it sits below
# the median at two years and spikes at three). The mean is reported in the
# text at the horizons where it is well behaved, with that caveat attached.
axr = ax[1].twinx()
axr.plot(hzp['horizon_years'], hzp['R_median'], color=RENT, lw=1.3, ls='-',
         marker='s', ms=3.0, label='Median $R$ (right)')
axr.axhline(1, color=RENT, lw=0.7, ls=':')
axr.set_ylabel('Median wealth ratio $R$', color=INK)
axr.set_ylim(0.82, 1.30)
axr.spines['top'].set_visible(False)
axr.tick_params(axis='y', labelsize=7.6)
h1, l1 = ax[1].get_legend_handles_labels()
h2, l2 = axr.get_legend_handles_labels()
ax[1].legend(h1 + h2, l1 + l2, frameon=False, loc='upper left', fontsize=7)
ax[1].annotate('round-trip costs\nnot yet amortised', xy=(1.25, 31), xytext=(2.15, 74),
               fontsize=7, color=INK, ha='left',
               arrowprops=dict(arrowstyle='->', color=NEUT, lw=0.7))
save(fig, 'fig4_cohorts.pdf')

# ================================================================ Figure 5
# Predictors: mortgage rate and price-to-rent ratio at entry (merged panels).
fig, axes = plt.subplots(1, 2, figsize=(W, 2.9), sharey=True)
for ax_, xvar, xlab, panel in [
        (axes[0], roll['mortgage_rate'] * 100, 'Effective mortgage rate at entry (%)', 'A'),
        (axes[1], roll['pr_ratio'], 'Price-to-rent ratio at entry', 'B')]:
    buy = roll['R'] < 1
    ax_.scatter(xvar[buy], roll['R'][buy], s=17, facecolors=BUY, edgecolors=BUY, linewidths=0.5)
    ax_.scatter(xvar[~buy], roll['R'][~buy], s=17, facecolors='none', edgecolors=RENT, linewidths=0.7)
    m, c = np.polyfit(xvar, roll['R'], 1)
    xs = np.linspace(xvar.min(), xvar.max(), 50)
    ax_.plot(xs, m * xs + c, color=NEUT, lw=0.9, ls='--')
    ax_.axhline(1, color='#999999', lw=0.6, ls=':')
    style(ax_, xlabel=xlab)
    ax_.set_title(panel, loc='left', fontsize=9, fontweight='bold', pad=3)
axes[0].set_ylabel('Wealth ratio $R$')
axes[0].legend(handles=[
    Line2D([], [], marker='o', ls='', markerfacecolor=BUY, markeredgecolor=BUY, markersize=4,
           label='Buying won'),
    Line2D([], [], marker='o', ls='', markerfacecolor='none', markeredgecolor=RENT, markersize=4,
           label='Renting won')], frameon=False, loc='upper left')
fig.tight_layout(w_pad=1.2)
save(fig, 'fig5_predictors.pdf')

# ================================================================ Figure 6
# Forward-looking required appreciation by horizon, under two equity assumptions.
# Replaces the historical-RAR figure: the historical subsection is cut, and RAR
# is now used only as a forward-looking metric.
fwd = pd.read_csv(os.path.join(TBL, 'uk_rar_forward_sensitivity.csv'))
fig, ax = plt.subplots(figsize=(W, 3.3))
ax.plot(fwd['horizon_years'], fwd['rar_stocks_pct'], color=RENT, lw=1.4, ls='-',
        marker='o', ms=3.4, label='Break-even vs equities at 5.9% (CAPE-implied)')
ax.plot(fwd['horizon_years'], fwd['rar_stocks_realised_pct'], color=RENT2, lw=1.4,
        ls='-.', marker='s', ms=3.4,
        label='Break-even vs equities at 10.4% (realised over the sample)')
ax.plot(fwd['horizon_years'], fwd['rar_gilts_pct'], color=NEUT, lw=1.2, ls='--',
        marker='^', ms=3.4, label='Break-even vs 10-year gilts at 4.9%')
# the realised appreciation of the representative dwelling, as the reference the
# reader should compare the break-evens against
ax.axhline(3.21, color=BUY, lw=1.2, ls=':')
ax.annotate('Realised 2005-2026 appreciation, 3.2% per year',
            xy=(4.6, 3.21), xytext=(4.6, 2.94), color=BUY, fontsize=7.4, ha='left')
style(ax, xlabel='Holding period (years)', ylabel='Required appreciation (% per year)')
ax.set_xticks([3, 5, 7, 10])
ax.set_xlim(2.6, 10.4)
ax.legend(frameon=False, loc='lower left', fontsize=7.4)
save(fig, 'fig6_rar.pdf')

# ================================================================ Figure 7
# Monthly cash flows of the two strategies (mechanism illustration).
fig, ax = plt.subplots(figsize=(W, 3.1))
ax.plot(paths['date'], paths['owner_outflow'], color=BUY, lw=1.2, ls='-',
        label='Owner: mortgage payment plus maintenance')
ax.plot(paths['date'], paths['rent'], color=RENT, lw=1.2, ls='--', label='Renter: market rent')
ax.fill_between(paths['date'], paths['owner_outflow'], paths['rent'],
                where=paths['owner_outflow'] >= paths['rent'],
                color=BUY, alpha=0.13, linewidth=0)
ax.fill_between(paths['date'], paths['owner_outflow'], paths['rent'],
                where=paths['owner_outflow'] < paths['rent'],
                color=RENT, alpha=0.13, linewidth=0)
style(ax, ylabel='£ per month')
years(ax)
ax.legend(frameon=False, loc='upper left')
save(fig, 'fig7_cashflows.pdf')

# ================================================================ Figure 8
# Regional required appreciation rate (greyscale choropleth).
if GEO:
    from matplotlib.colors import LinearSegmentedColormap
    import matplotlib.patheffects as pe

    gj = json.load(open(GEO, encoding='utf-8'))
    vals = dict(zip(reg['region'], reg['rar_stocks_pct']))
    cmap = LinearSegmentedColormap.from_list('buy_seq', ['#F4F7F9', '#A8C0CE', '#4E7F9C', BUY])
    norm = plt.Normalize(min(vals.values()) - 0.25, max(vals.values()) + 0.1)

    def centroid(ring):
        x, y = ring[:, 0], ring[:, 1]
        x1, y1 = np.roll(x, -1), np.roll(y, -1)
        cr = x * y1 - x1 * y
        A = cr.sum() / 2.0
        if abs(A) < 1e-9:
            return x.mean(), y.mean()
        return ((x + x1) * cr).sum() / (6 * A), ((y + y1) * cr).sum() / (6 * A)

    fig, ax = plt.subplots(figsize=(4.6, 5.8))
    pts = {}
    for feat in gj['features']:
        name = feat['properties']['RGN24NM']
        v = vals.get(name)
        geom = feat['geometry']
        polys = [geom['coordinates']] if geom['type'] == 'Polygon' else geom['coordinates']
        big, big_a = None, -1
        for poly in polys:
            ring = np.array(poly[0])
            ax.add_patch(MplPolygon(ring, closed=True,
                                    facecolor=cmap(norm(v)) if v is not None else '#EDEFF1',
                                    edgecolor='white', linewidth=0.8))
            a = abs(np.dot(ring[:, 0], np.roll(ring[:, 1], -1))
                    - np.dot(np.roll(ring[:, 0], -1), ring[:, 1])) / 2.0
            if a > big_a:
                big_a, big = a, ring
        pts[name] = centroid(big)

    short = {'Yorkshire and The Humber': 'Yorkshire &\nThe Humber', 'East of England': 'East of\nEngland',
             'North East': 'North\nEast', 'North West': 'North\nWest', 'West Midlands': 'West\nMidlands',
             'East Midlands': 'East\nMidlands', 'South East': 'South\nEast', 'South West': 'South\nWest'}
    halo = [pe.withStroke(linewidth=2.4, foreground='white')]
    for name, (lon, lat) in pts.items():
        v = vals.get(name)
        lab = f"{short.get(name, name)}\n{v:.1f}"
        if name == 'London':
            ax.annotate(lab, xy=(lon, lat), xytext=(2.2, 50.7), ha='center', va='center',
                        fontsize=7.2, color=INK, path_effects=halo,
                        arrowprops=dict(arrowstyle='-', color=NEUT, lw=0.7, shrinkA=0, shrinkB=2))
        else:
            if name == 'South East':
                lat -= 0.12
            ax.annotate(lab, (lon, lat), ha='center', va='center', fontsize=7.2,
                        color=INK, path_effects=halo)
    ax.set_xlim(-6.6, 2.7)
    ax.set_ylim(49.8, 55.9)
    ax.set_aspect(1.6)
    ax.axis('off')
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    cb = fig.colorbar(sm, ax=ax, shrink=0.45, pad=0.01)
    cb.set_label('Required appreciation (% per year)', fontsize=8)
    cb.ax.tick_params(labelsize=7)
    cb.outline.set_linewidth(0.5)
    save(fig, 'fig8_regional_map.pdf')

print("done")
