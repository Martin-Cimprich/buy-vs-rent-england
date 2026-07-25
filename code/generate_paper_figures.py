#!/usr/bin/env python3
"""
Journal figure set for the working paper (whitepaper/paper_wp/figures).

Design rules, following field-journal conventions:
  * Monochrome. Series are distinguished by line style and marker fill, not
    colour, so every figure survives greyscale printing.
  * No figure-level titles or annotations; captions carry the description.
  * Serif type matching the manuscript; vector PDF output.
  * Six main-text figures and two appendix figures — see FIGURES below.

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
for cand in [os.path.join(BASE, 'whitepaper', 'paper_wp', 'figures'),
             os.path.join(BASE, 'paper', 'src', 'figures')]:
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

K = '#000000'          # primary series (owner / buying)
G = '#6E6E6E'          # secondary series (renter / renting)
LG = '#A8A8A8'         # tertiary series
W = 6.3                # text width in inches (A4, 25 mm margins)


def style(ax, xlabel=None, ylabel=None, grid=True):
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#333333')
    ax.spines['bottom'].set_color('#333333')
    ax.tick_params(colors='#333333', width=0.6, length=3)
    if grid:
        ax.grid(True, alpha=0.30, color='#BBBBBB', linewidth=0.4)
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
                  parse_dates=['Date']).set_index('Date').loc['2005-01-31':'2026-04-30']
rets = pd.read_csv(os.path.join(CLEAN, 'uk_stock_returns_gbp.csv'),
                   parse_dates=['Date']).set_index('Date').loc['2005-01-31':'2026-04-30']
paths = pd.read_csv(os.path.join(TBL, 'uk_single_start_paths.csv'), parse_dates=['date'])
roll = pd.read_csv(os.path.join(TBL, 'uk_rolling_cohorts.csv'), parse_dates=['start_date'])
rarh = pd.read_csv(os.path.join(TBL, 'uk_rar_historical.csv'), parse_dates=['date'])
reg = pd.read_csv(os.path.join(TBL, 'uk_regional_results.csv'))

print("Journal figures ->", FIG)

# ================================================================ Figure 1
# Market inputs: price, rent, price-to-rent, mortgage rate (absorbs the old
# separate price-rent dynamics figure).
fig, ax = plt.subplots(4, 1, figsize=(W, 7.4), sharex=True)
ax[0].plot(rep.index, rep['Purchase_Price_GBP'] / 1e3, color=K, lw=1.1)
style(ax[0], ylabel='£000s')
ax[0].set_title('A. House price', loc='left', fontsize=8.5, pad=3)

ax[1].plot(rep.index, rep['Rent_GBP'], color=K, lw=1.1)
style(ax[1], ylabel='£ per month')
ax[1].set_title('B. Private rent', loc='left', fontsize=8.5, pad=3)

pr = rep['Purchase_Price_GBP'] / (rep['Rent_GBP'] * 12)
ax[2].plot(pr.index, pr, color=K, lw=1.1)
ax[2].axhline(pr.mean(), color=G, ls='--', lw=0.8)
style(ax[2], ylabel='ratio')
ax[2].set_title('C. Price-to-rent ratio', loc='left', fontsize=8.5, pad=3)


ax[3].plot(rep.index, rep['Mortgage_Rate_pct'], color=K, lw=1.1)
style(ax[3], ylabel='per cent')
ax[3].set_title('D. Effective mortgage rate', loc='left', fontsize=8.5, pad=3)
years(ax[3])
fig.align_ylabels(ax)
fig.tight_layout(h_pad=0.7)
save(fig, 'fig1_market.pdf')

# ================================================================ Figure 2
# Cumulative asset performance.
acwi = (1 + rets['acwi_net_ter_gbp_ret']).cumprod() * 100
ftse = (1 + rets['ftse100_tr_ret']).cumprod() * 100
hp = rep['Purchase_Price_GBP'] / rep['Purchase_Price_GBP'].iloc[0] * 100
fig, ax = plt.subplots(figsize=(W, 3.3))
ax.plot(acwi.index, acwi, color=K, lw=1.2, ls='-', label='Global equities (MSCI ACWI, net TR, GBP)')
ax.plot(ftse.index, ftse, color=G, lw=1.1, ls='--', label='UK equities (FTSE 100, total return)')
ax.plot(hp.index, hp, color=K, lw=1.1, ls=':', label='English house prices')
style(ax, ylabel='Index, January 2005 = 100')
years(ax)
ax.legend(frameon=False, loc='upper left')
save(fig, 'fig2_assets.pdf')

# ================================================================ Figure 3
# Wealth paths, 2005 entry cohort.
fig, ax = plt.subplots(figsize=(W, 3.3))
ax.plot(paths['date'], paths['buy_equity'] / 1e3, color=K, lw=1.2, ls='-',
        label='Buyer: home equity net of mortgage')
ax.plot(paths['date'], paths['portfolio'] / 1e3, color=G, lw=1.2, ls='--',
        label='Renter: investment portfolio')
style(ax, ylabel='£000s')
years(ax)
ax.legend(frameon=False, loc='upper left')
save(fig, 'fig3_wealth.pdf')

# ================================================================ Figure 4
# Rolling cohort outcomes.
fig, ax = plt.subplots(figsize=(W, 3.3))
for _, c in roll.iterrows():
    ax.bar(c['start_date'], c['R'] - 1, bottom=1, width=75,
           color=('#4D4D4D' if c['R'] < 1 else '#C4C4C4'),
           edgecolor='#222222', linewidth=0.25)
ax.axhline(1, color=K, lw=0.8)
style(ax, ylabel='Wealth ratio $R$')
years(ax)
ax.legend(handles=[Patch(facecolor='#4D4D4D', edgecolor='#222222', label='Buying won ($R<1$)'),
                   Patch(facecolor='#C4C4C4', edgecolor='#222222', label='Renting won ($R>1$)')],
          frameon=False, loc='upper left')
save(fig, 'fig4_cohorts.pdf')

# ================================================================ Figure 5
# Predictors: mortgage rate and price-to-rent ratio at entry (merged panels).
fig, axes = plt.subplots(1, 2, figsize=(W, 2.9), sharey=True)
for ax_, xvar, xlab, panel in [
        (axes[0], roll['mortgage_rate'] * 100, 'Effective mortgage rate at entry (%)', 'A'),
        (axes[1], roll['pr_ratio'], 'Price-to-rent ratio at entry', 'B')]:
    buy = roll['R'] < 1
    ax_.scatter(xvar[buy], roll['R'][buy], s=16, facecolors=K, edgecolors=K, linewidths=0.5)
    ax_.scatter(xvar[~buy], roll['R'][~buy], s=16, facecolors='none', edgecolors=K, linewidths=0.6)
    m, c = np.polyfit(xvar, roll['R'], 1)
    xs = np.linspace(xvar.min(), xvar.max(), 50)
    ax_.plot(xs, m * xs + c, color=G, lw=0.9, ls='--')
    ax_.axhline(1, color='#999999', lw=0.6, ls=':')
    style(ax_, xlabel=xlab)
    ax_.set_title(panel, loc='left', fontsize=9, fontweight='bold', pad=3)
axes[0].set_ylabel('Wealth ratio $R$')
axes[0].legend(handles=[
    Line2D([], [], marker='o', ls='', markerfacecolor=K, markeredgecolor=K, markersize=4,
           label='Buying won'),
    Line2D([], [], marker='o', ls='', markerfacecolor='none', markeredgecolor=K, markersize=4,
           label='Renting won')], frameon=False, loc='upper left')
fig.tight_layout(w_pad=1.2)
save(fig, 'fig5_predictors.pdf')

# ================================================================ Figure 6
# Required versus realised ten-year appreciation.
fig, ax = plt.subplots(figsize=(W, 3.3))
ax.plot(rarh['date'], rarh['rar_stocks'] * 100, color=K, lw=1.2, ls='-',
        label='Required, versus global equities')
ax.plot(rarh['date'], rarh['rar_gilts'] * 100, color=G, lw=1.1, ls='--',
        label='Required, versus 10-year gilts')
ax.plot(rarh['date'], rarh['actual_appr'] * 100, color=K, lw=1.1, ls=':',
        label='Realised over the following ten years')
ax.axhline(0, color='#999999', lw=0.6)
style(ax, xlabel='Month of purchase', ylabel='Per cent per year')
years(ax, 2)
ax.legend(frameon=False, loc='upper left')
save(fig, 'fig6_rar.pdf')

# ============================================================== Appendix A1
# Monthly cash flows of the two strategies (mechanism illustration).
fig, ax = plt.subplots(figsize=(W, 3.1))
ax.plot(paths['date'], paths['owner_outflow'], color=K, lw=1.1, ls='-',
        label='Owner: mortgage payment plus maintenance')
ax.plot(paths['date'], paths['rent'], color=G, lw=1.1, ls='--', label='Renter: market rent')
ax.fill_between(paths['date'], paths['owner_outflow'], paths['rent'],
                where=paths['owner_outflow'] >= paths['rent'],
                color='#000000', alpha=0.10, linewidth=0)
ax.fill_between(paths['date'], paths['owner_outflow'], paths['rent'],
                where=paths['owner_outflow'] < paths['rent'],
                color='#000000', alpha=0.03, linewidth=0)
style(ax, ylabel='£ per month')
years(ax)
ax.legend(frameon=False, loc='upper left')
save(fig, 'figA1_cashflows.pdf')

# ============================================================== Appendix A2
# Regional required appreciation rate (greyscale choropleth).
if GEO:
    from matplotlib.colors import LinearSegmentedColormap
    import matplotlib.patheffects as pe

    gj = json.load(open(GEO, encoding='utf-8'))
    vals = dict(zip(reg['region'], reg['rar_stocks_pct']))
    cmap = LinearSegmentedColormap.from_list('greys_soft', ['#FFFFFF', '#111111'])
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
                                    facecolor=cmap(norm(v)) if v is not None else '#EEEEEE',
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
                        fontsize=7.2, color=K, path_effects=halo,
                        arrowprops=dict(arrowstyle='-', color='#666666', lw=0.7, shrinkA=0, shrinkB=2))
        else:
            if name == 'South East':
                lat -= 0.12
            ax.annotate(lab, (lon, lat), ha='center', va='center', fontsize=7.2,
                        color=K, path_effects=halo)
    ax.set_xlim(-6.6, 2.7)
    ax.set_ylim(49.8, 55.9)
    ax.set_aspect(1.6)
    ax.axis('off')
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    cb = fig.colorbar(sm, ax=ax, shrink=0.45, pad=0.01)
    cb.set_label('Required appreciation (% per year)', fontsize=8)
    cb.ax.tick_params(labelsize=7)
    cb.outline.set_linewidth(0.5)
    save(fig, 'figA2_regional_map.pdf')

print("done")
