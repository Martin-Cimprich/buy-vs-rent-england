// Regression tests: the JS engine must reproduce the Python engine's numbers.
// Run: node engine.test.mjs   (after build_calculator.py has emitted the data)
import { createRequire } from 'module';
import { readFileSync } from 'fs';
const require = createRequire(import.meta.url);
const E = require('./engine.js');

// Load data (plain script defining CALC_DATA)
const dataSrc = readFileSync(new URL('./calculator_data.js', import.meta.url), 'utf-8');
const CALC_DATA = eval(dataSrc + '; CALC_DATA');

let failures = 0;
function check(name, got, want, tol = 0) {
  const ok = typeof want === 'number' ? Math.abs(got - want) <= tol : got === want;
  if (!ok) failures++;
  console.log(`${ok ? 'OK  ' : 'FAIL'} ${name}: got ${got}, want ${want}${tol ? ' ±' + tol : ''}`);
}

// ---- 1. SDLT spot checks (values from the Python unit tests) ----
const sdltCases = [
  [153030, 2008, 2, 1530.30], [153030, 2008, 10, 0], [180000, 2009, 6, 1800],
  [200000, 2011, 6, 0], [220000, 2013, 6, 2200], [220000, 2015, 6, 1900],
  [290000, 2019, 6, 0], [310000, 2022, 2, 500], [310000, 2023, 12, 0],
  [310000, 2025, 6, 500], [560000, 2019, 6, 18000], [560000, 2020, 10, 3000],
  [100000, 2005, 2, 1000], [100000, 2005, 6, 0], [450000, 2023, 6, 1250],
];
for (const [price, y, m, want] of sdltCases) {
  check(`SDLT ${y}-${String(m).padStart(2, '0')} £${price}`, E.sdltEnglandFTB(price, y, m), want, 0.51);
}

// ---- 2. Historical engine vs Python (baseline params, representative series) ----
const P = {
  depositShare: 0.10, amortYears: 30, maintPct: 0.015,
  purchaseCostsPct: 0.015, sellingCostsPct: 0.02, includeSdlt: true,
  fixationYears: null, rentGrowthAnnual: 0.03,
};
const S = CALC_DATA.series['England (representative)'];
const data = { prices: S.prices, rents: S.rents, rates: CALC_DATA.rates,
               returns: CALC_DATA.returns, ym: CALC_DATA.ym };
const n = data.prices.length;
check('months', n, 256);

const single = E.runPair(data, 0, n, P);
check('single-start R', single.R, 1.0886, 0.002);              // Python: 1.0886
check('single NW buy', single.buy.netWorth, 252768, 600);      // Python: 252,768
check('single NW rent', single.rent.netWorth, 275171, 700);    // Python: 275,171
check('single SDLT', single.buy.sdlt, 1623, 2);                // Python: 1,623

const rolling = E.runRolling(data, n, P);
check('cohorts', rolling.length, 85);
check('buy wins', rolling.filter(c => c.winner === 'BUY').length, 45);
const rbar = rolling.reduce((a, c) => a + c.R, 0) / rolling.length;
check('R-bar', rbar, 1.064, 0.003);                            // Python: 1.064

// ---- 3. Forward RAR vs Python (Apr 2026 conditions) ----
const priceNow = data.prices[n - 1], rentNow = data.rents[n - 1], rateNow = data.rates[n - 1];
check('price now', priceNow, 317738, 1);
const sdltNow = E.sdltEnglandFTB(priceNow, 2026, 4);
check('SDLT now', sdltNow, 887, 2);                            // Python: 887
const rar10 = E.requiredAppreciationRate(priceNow, rentNow, rateNow, 0.0588, 10, P, sdltNow);
check('forward RAR 10y', rar10, 0.0096, 0.0005);               // Python: 0.96%
const rar3 = E.requiredAppreciationRate(priceNow, rentNow, rateNow, 0.0588, 3, P, sdltNow);
check('forward RAR 3y', rar3, 0.0216, 0.0006);                 // Python: 2.16%

console.log(failures === 0 ? '\nALL ENGINE TESTS PASSED' : `\n${failures} FAILURES`);
process.exit(failures === 0 ? 0 : 1);
