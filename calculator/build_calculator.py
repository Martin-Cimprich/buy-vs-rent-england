#!/usr/bin/env python3
"""
Build the self-contained Buy vs Rent England calculator.

Reads the clean datasets, emits calculator_data.js (historical series used by
the backtest tab), and injects engine.js + data into template.html to produce
index.html — one self-contained file with no external dependencies.
"""
import sys, io, os, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pandas as pd

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLEAN = os.path.join(BASE, "data", "clean")
HERE = os.path.dirname(os.path.abspath(__file__))

START, END = '2005-01-31', '2026-06-30'

rep = pd.read_csv(os.path.join(CLEAN, 'uk_housing_monthly_representative.csv'),
                  parse_dates=['Date']).set_index('Date').loc[START:END]
reg = pd.read_csv(os.path.join(CLEAN, 'uk_housing_monthly_regions.csv'), parse_dates=['Date'])
reg = reg[(reg.Date >= START) & (reg.Date <= END)]
rets = pd.read_csv(os.path.join(CLEAN, 'uk_stock_returns_gbp.csv'),
                   parse_dates=['Date']).set_index('Date').loc[START:END]

months = [d.strftime('%Y-%m') for d in rep.index]
ym = [[d.year, d.month] for d in rep.index]

# Two decimals, not whole pounds. The crash cohorts finish with owner net
# worth around GBP 15,800, so rounding the price series to the nearest pound
# moves the wealth ratio in the third decimal and the JS engine then fails its
# regression test against Python. The UI rounds for display instead.
series = {'England (representative)': {
    'prices': [round(float(x), 2) for x in rep['Purchase_Price_GBP']],
    'rents': [round(float(x), 2) for x in rep['Rent_GBP']],
}}
for name, g in reg.groupby('Region'):
    g = g.sort_values('Date')
    assert len(g) == len(rep), f"{name}: {len(g)} rows"
    series[name] = {'prices': [round(float(x), 2) for x in g['Price_GBP']],
                    'rents': [round(float(x), 2) for x in g['Rent_GBP']]}

pct = lambda col: [round(float(x) / 100.0, 6) for x in rep[col]]

data = {
    'months': months,
    'ym': ym,
    'series': series,
    # The baseline five-year fix is repriced at each refix by the borrower's
    # current loan-to-value, so the engine needs all three published bands
    # rather than one rate series. `rates` is the 90% LTV band, which is where
    # a 10%-deposit buyer starts, and is also the fallback when a caller does
    # not pass bands.
    'rates': pct('Rate_90LTV_pct'),
    'bands': {'r75': pct('Rate_75LTV_pct'),
              'r90': pct('Rate_90LTV_pct'),
              'r95': pct('Rate_95LTV_pct')},
    # Retained for the floating-rate comparison in the robustness tab.
    'ratesFloating': pct('Mortgage_Rate_CFMBJ95_pct'),
    'returns': [round(float(x), 6) for x in rets['acwi_net_ter_gbp_ret']],
    'meta': {
        'built_from': ('UK HPI (HM Land Registry), ONS PIPR, Bank of England quoted '
                       'fixed rates at 75/90/95% LTV, MSCI ACWI net TR GBP less 0.12% fee'),
        'window': f'{months[0]} to {months[-1]}',
        'baseline': ('10% deposit, 30-year term, five-year fix repriced by current LTV, '
                     '1.5% maintenance, 1.2% purchase and 1.8% selling costs, '
                     'period-accurate England FTB stamp duty'),
    },
}
n = len(months)
assert len(data['returns']) == n == len(data['rates']) == len(data['ratesFloating'])
for k, v in data['bands'].items():
    assert len(v) == n, f'band {k}: {len(v)} != {n}'
assert n == 258, f'expected 258 months, got {n}'

data_js = 'const CALC_DATA = ' + json.dumps(data, separators=(',', ':')) + ';\n'
with open(os.path.join(HERE, 'calculator_data.js'), 'w', encoding='utf-8') as f:
    f.write(data_js)
print(f"calculator_data.js: {len(data_js)/1024:.0f} KB, {len(months)} months, {len(series)} series")

tpl_path = os.path.join(HERE, 'template.html')
if os.path.exists(tpl_path):
    tpl = open(tpl_path, encoding='utf-8').read()
    engine = open(os.path.join(HERE, 'engine.js'), encoding='utf-8').read()
    out = tpl.replace('/*__ENGINE__*/', engine).replace('/*__DATA__*/', data_js)
    assert '/*__ENGINE__*/' not in out and '/*__DATA__*/' not in out
    with open(os.path.join(HERE, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(out)
    print(f"index.html: {os.path.getsize(os.path.join(HERE, 'index.html'))/1024:.0f} KB (self-contained)")
else:
    print("template.html not found — data only")
