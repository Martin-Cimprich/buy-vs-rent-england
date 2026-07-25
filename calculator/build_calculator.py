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

START, END = '2005-01-31', '2026-04-30'

rep = pd.read_csv(os.path.join(CLEAN, 'uk_housing_monthly_representative.csv'),
                  parse_dates=['Date']).set_index('Date').loc[START:END]
reg = pd.read_csv(os.path.join(CLEAN, 'uk_housing_monthly_regions.csv'), parse_dates=['Date'])
reg = reg[(reg.Date >= START) & (reg.Date <= END)]
rets = pd.read_csv(os.path.join(CLEAN, 'uk_stock_returns_gbp.csv'),
                   parse_dates=['Date']).set_index('Date').loc[START:END]

months = [d.strftime('%Y-%m') for d in rep.index]
ym = [[d.year, d.month] for d in rep.index]

series = {'England (representative)': {
    'prices': [round(float(x), 0) for x in rep['Purchase_Price_GBP']],
    'rents': [round(float(x), 0) for x in rep['Rent_GBP']],
}}
for name, g in reg.groupby('Region'):
    g = g.sort_values('Date')
    assert len(g) == len(rep), f"{name}: {len(g)} rows"
    series[name] = {'prices': [round(float(x), 0) for x in g['Price_GBP']],
                    'rents': [round(float(x), 0) for x in g['Rent_GBP']]}

data = {
    'months': months,
    'ym': ym,
    'series': series,
    'rates': [round(float(x) / 100.0, 6) for x in rep['Mortgage_Rate_pct']],
    'returns': [round(float(x), 6) for x in rets['acwi_net_ter_gbp_ret']],
    'meta': {
        'built_from': 'UK HPI (HM Land Registry), ONS PIPR, Bank of England CFMBJ95, MSCI ACWI net TR GBP less 0.12% fee',
        'window': f'{months[0]} to {months[-1]}',
    },
}
assert len(data['returns']) == len(months) == len(data['rates']) == 256

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
