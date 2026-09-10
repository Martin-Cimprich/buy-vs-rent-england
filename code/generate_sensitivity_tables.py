#!/usr/bin/env python3
"""
Emit the robustness tables as a LaTeX fragment, straight from the sensitivity CSV.

The tables in whitepaper/paper_wp/sections/07_robustness.tex used to be typed by
hand, which is how they came to carry numbers from three baselines ago. They are
now generated into

    whitepaper/paper_wp/tables/sensitivity_generated.tex

which 07_robustness.tex \\inputs, so re-running full_run_uk.py and this script
updates them and they cannot silently go stale again.

Run:  python generate_sensitivity_tables.py
"""
import io
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(HERE)
TBL = os.path.join(BASE, 'output', 'tables')
# The repo ships the paper as a PDF, so the generated LaTeX table lands in
# output/tables for inspection rather than being \input by a local build.
OUT_DIR = os.path.join(BASE, 'output', 'tables')
os.makedirs(OUT_DIR, exist_ok=True)
OUT = os.path.join(OUT_DIR, 'sensitivity_generated.tex')

BS = chr(92)
PCT = BS + '%'

# group key in the CSV -> (heading, {label -> display label})
BLOCK_1 = [
    ('maintenance (UK-grounded)', 'Maintenance and depreciation, UK-grounded range (' + PCT + ' of value p.a.)',
     [('1.2%', '1.2'), (None, '1.5 (baseline)'), ('1.8%', '1.8')]),
    ('maintenance (beyond evidence)', 'Maintenance and depreciation, beyond the UK evidence',
     [('1.0%', '1.0'), ('2.0%', '2.0'), ('2.5%', '2.5'), ('3.0%', '3.0')]),
    ('deposit', 'Deposit (' + PCT + ' of purchase price)',
     [('5%', '5'), (None, '10 (baseline)'), ('15%', '15'), ('20%', '20'),
      ('25%', '25'), ('50%', '50'), ('100%', '100 (cash)')]),
]

BLOCK_2 = [
    ('term', 'Mortgage term',
     [('25y', '25 years'), (None, '30 years (baseline)'), ('35y', '35 years')]),
    ('fixation', 'Rate fixation',
     [('2y', '2-year fixes'), (None, '5-year fixes (baseline)'), ('10y', '10-year fixes')]),
    ('rate design', 'Mortgage rate series',
     [(None, 'FTB 5y fix at 90' + PCT + ' LTV (baseline)'),
      ('CFMBJ95 floating', 'CFMBJ95 effective rate, floating')]),
    ('renter leverage', "Renter's leverage",
     [(None, '1.00$' + BS + 'times$ (baseline, unlevered)'),
      ('1.25x', '1.25$' + BS + 'times$'),
      ('1.50x', '1.50$' + BS + 'times$'), ('1.75x', '1.75$' + BS + 'times$'),
      ('2.00x', '2.00$' + BS + 'times$')]),
    ('purchase_costs', 'Transaction costs',
     [('1.0%', 'Purchase costs 1.0' + PCT), (None, 'Purchase costs 1.2' + PCT + ' (baseline)'),
      ('2.0%', 'Purchase costs 2.0' + PCT)]),
    ('selling_costs', None,
     [('1.0%', 'Selling costs 1.0' + PCT), (None, 'Selling costs 1.8' + PCT + ' (baseline)'),
      ('4.0%', 'Selling costs 4.0' + PCT)]),
    ('sdlt', None, [('excluded', 'Stamp duty excluded')]),
    ('index', "Renter's portfolio",
     [(None, 'MSCI ACWI net, less fee (baseline)'),
      ('ACWI gross', 'MSCI ACWI gross, no fee'),
      ('FTSE 100', 'FTSE 100 total return')]),
]


def build(df, blocks, caption, label, notes):
    base = df[(df.group == 'base')].iloc[0]
    rows = []
    rows.append(BS + 'begin{table}[H]')
    rows.append('  ' + BS + 'centering')
    rows.append('  ' + BS + 'caption{' + caption + '}')
    rows.append('  ' + BS + 'label{' + label + '}')
    rows.append('  ' + BS + 'begin{threeparttable}')
    rows.append('  ' + BS + 'begin{tabular}{@{}lrrr@{}}')
    rows.append('    ' + BS + 'toprule')
    rows.append('    ' + BS + 'textbf{Parameter} & ' + BS + 'textbf{$R$ (2005)} & '
                + BS + 'textbf{Median $R$} & ' + BS + 'textbf{Buy-win ' + PCT + '} ' + BS + BS)
    rows.append('    ' + BS + 'midrule')

    first = True
    for gkey, heading, items in blocks:
        if heading:
            if not first:
                rows.append('    ' + BS + 'addlinespace')
            rows.append('    ' + BS + 'multicolumn{4}{@{}l}{' + BS + 'textit{'
                        + heading + '}} ' + BS + BS)
        first = False
        for csv_label, disp in items:
            if csv_label is None:
                r = base
            else:
                m = df[(df.group == gkey) & (df.label == csv_label)]
                if len(m) != 1:
                    print('  MISSING: group=%r label=%r (%d matches)'
                          % (gkey, csv_label, len(m)))
                    continue
                r = m.iloc[0]
            rows.append('    ' + BS + 'quad ' + disp
                        + ' & %.2f & %.2f & %.0f ' % (r.R_single, r.R_cohort_median,
                                                      100 * r.buy_win_share)
                        + BS + BS)
    rows.append('    ' + BS + 'bottomrule')
    rows.append('  ' + BS + 'end{tabular}')
    rows.append('  ' + BS + 'begin{tablenotes}')
    rows.append('    ' + BS + 'small')
    rows.append('    ' + BS + 'item ' + BS + 'textit{Notes:} ' + notes)
    rows.append('  ' + BS + 'end{tablenotes}')
    rows.append('  ' + BS + 'end{threeparttable}')
    rows.append(BS + 'end{table}')
    return '\n'.join(rows)


def main():
    path = os.path.join(TBL, 'uk_sensitivity.csv')
    df = pd.read_csv(path)
    # the CSV stores the cohort statistic under R_rolling_mean; since round 4 it
    # is the MEDIAN over the fixed five-year cohorts, not a mean.
    n1 = ('$R > 1$: renting-and-investing produced greater terminal wealth. $R$ (2005) is '
          'the January 2005 entry cohort held to June 2026. Median $R$ and buy-win '
          + PCT + ' are taken over the 199 fixed five-year cohorts. All other parameters '
          'at baseline. The maintenance range of 1.2--1.8' + PCT + ' is what UK national-'
          'accounts evidence supports (Section~' + BS + 'ref{sec:framework}); the values '
          'below and above it are reported as bounds, not as equally supported alternatives.')
    n2 = ('As Table~' + BS + 'ref{tab:sensitivity_main}. The renter-leverage rows charge '
          'margin interest at Bank Rate plus 1.50' + PCT + ' and impose a 30' + PCT
          + ' maintenance margin with forced liquidation; no cohort is liquidated, for the '
          'reason given in the text.')
    parts = [
        build(df, BLOCK_1, 'Sensitivity to maintenance and deposit',
              'tab:sensitivity_main', n1),
        '',
        build(df, BLOCK_2, 'Sensitivity to other parameters',
              'tab:sensitivity_other', n2),
    ]
    io.open(OUT, 'w', encoding='utf-8', newline='\n').write('\n'.join(parts) + '\n')
    print('wrote %s' % OUT)
    return 0


if __name__ == '__main__':
    sys.exit(main())
