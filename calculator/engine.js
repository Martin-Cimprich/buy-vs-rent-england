// ============================================================================
// engine.js — Buy vs Rent England: simulation engine
// ----------------------------------------------------------------------------
// A line-by-line port of code/python/uk_horse_race_v2.py (the engine behind the
// paper). Dates are handled at month-end granularity as (year, month) pairs,
// matching the Python engine's month-end timestamp convention exactly.
// Regression-tested against the Python outputs in engine.test.mjs.
// ============================================================================

'use strict';

// ---- Stamp duty: England, first-time buyer, by (year, month) of purchase ----
// Slab = rate applies to the whole price; slice = marginal bands.
function _slab(price, bands) {
  for (const [upper, rate] of bands) if (price <= upper) return price * rate;
  return 0;
}
function _slice(price, bands) {
  let tax = 0, lower = 0;
  for (const [upper, rate] of bands) {
    if (price > lower) tax += (Math.min(price, upper) - lower) * rate;
    lower = upper;
    if (price <= upper) break;
  }
  return tax;
}
const INF = Infinity;

function sdltEnglandFTB(price, y, m) {
  const ym = y * 100 + m; // month-end convention, mirroring the Python engine
  let std;
  if (ym < 200503) std = ['slab', [[60000, 0], [250000, 0.01], [500000, 0.03], [INF, 0.04]]];
  else if (ym < 200603) std = ['slab', [[120000, 0], [250000, 0.01], [500000, 0.03], [INF, 0.04]]];
  else if (ym < 200809) std = ['slab', [[125000, 0], [250000, 0.01], [500000, 0.03], [INF, 0.04]]];
  else if (ym < 201001) std = ['slab', [[175000, 0], [250000, 0.01], [500000, 0.03], [INF, 0.04]]];
  else if (ym < 201104) std = ['slab', [[125000, 0], [250000, 0.01], [500000, 0.03], [INF, 0.04]]];
  else if (ym < 201203) std = ['slab', [[125000, 0], [250000, 0.01], [500000, 0.03], [1000000, 0.04], [INF, 0.05]]];
  else if (ym < 201412) std = ['slab', [[125000, 0], [250000, 0.01], [500000, 0.03], [1000000, 0.04], [2000000, 0.05], [INF, 0.07]]];
  else if (ym < 202007) std = ['slice', [[125000, 0], [250000, 0.02], [925000, 0.05], [1500000, 0.10], [INF, 0.12]]];
  else if (ym < 202107) std = ['slice', [[500000, 0], [925000, 0.05], [1500000, 0.10], [INF, 0.12]]];
  else if (ym < 202110) std = ['slice', [[250000, 0], [925000, 0.05], [1500000, 0.10], [INF, 0.12]]];
  else if (ym < 202209) std = ['slice', [[125000, 0], [250000, 0.02], [925000, 0.05], [1500000, 0.10], [INF, 0.12]]];
  else if (ym < 202504) std = ['slice', [[250000, 0], [925000, 0.05], [1500000, 0.10], [INF, 0.12]]];
  else std = ['slice', [[125000, 0], [250000, 0.02], [925000, 0.05], [1500000, 0.10], [INF, 0.12]]];

  const standardTax = () => (std[0] === 'slab' ? _slab(price, std[1]) : _slice(price, std[1]));

  // First-time-buyer relief windows (month-end convention)
  if (ym >= 201003 && ym <= 201202) {                    // 25 Mar 2010 - 24 Mar 2012
    return price <= 250000 ? 0 : standardTax();
  }
  if ((ym >= 201711 && ym < 202007) || (ym >= 202107 && ym < 202209)) { // 0 to 300k, 5% 300-500k
    return price <= 500000 ? Math.max(0, price - 300000) * 0.05 : standardTax();
  }
  if (ym >= 202209 && ym < 202504) {                     // 0 to 425k, 5% 425-625k
    return price <= 625000 ? Math.max(0, price - 425000) * 0.05 : standardTax();
  }
  if (ym >= 202504) {                                    // 0 to 300k, 5% 300-500k
    return price <= 500000 ? Math.max(0, price - 300000) * 0.05 : standardTax();
  }
  return standardTax();
}

// ---- Mortgage arithmetic (identical to the Python engine) ----
function monthlyRate(annual) { return Math.pow(1 + annual, 1 / 12) - 1; }

function monthlyPayment(balance, mRate, monthsRemaining) {
  if (balance <= 0) return 0;
  if (mRate === 0) return monthsRemaining > 0 ? balance / monthsRemaining : balance;
  if (monthsRemaining <= 0) return balance;
  return balance * (mRate * Math.pow(1 + mRate, monthsRemaining)) /
         (Math.pow(1 + mRate, monthsRemaining) - 1);
}

// ---- Historical simulation on data arrays [startIdx, endIdx) ----
// prices/rents: GBP levels; rates: annual decimals; returns: monthly decimals.
// ymArr: [[y,m], ...] aligned with the arrays.
function simulateBuy(prices, rates, ymArr, startIdx, endIdx, p) {
  const n = endIdx - startIdx;
  const purchasePrice = prices[startIdx];
  const [y0, m0] = ymArr[startIdx];
  const sdlt = p.includeSdlt ? sdltEnglandFTB(purchasePrice, y0, m0) : 0;
  const closingPurchase = p.purchaseCostsPct * purchasePrice + sdlt;
  const deposit = p.depositShare * purchasePrice;
  let balance = purchasePrice - deposit;
  let monthsRemaining = Math.round(p.amortYears * 12);
  let homeValue = purchasePrice;

  const fixationMonths = p.fixationYears ? p.fixationYears * 12 : 1;
  let fixedRate = null;

  const outflows = new Array(n);
  const homeValues = new Array(n);
  const balances = new Array(n);
  const payments = new Array(n);
  const maints = new Array(n);

  for (let i = 0; i < n; i++) {
    homeValues[i] = homeValue;
    balances[i] = balance;
    const maint = (p.maintPct / 12) * homeValue;
    maints[i] = maint;

    if (i % fixationMonths === 0 || fixedRate === null) {
      fixedRate = rates[startIdx + i] + (p.ratePremium || 0);
    }
    const mr = monthlyRate(fixedRate);
    const pay = monthlyPayment(balance, mr, monthsRemaining);
    payments[i] = pay;
    outflows[i] = pay + maint;

    if (balance > 0 && monthsRemaining > 0) {
      const interest = balance * mr;
      const principal = Math.min(pay - interest, balance);
      balance = Math.max(balance - principal, 0);
      monthsRemaining -= 1;
    }
    if (i < n - 1) {
      const g = prices[startIdx + i + 1] / prices[startIdx + i] - 1;
      homeValue *= (1 + g);
    }
  }
  const nw = homeValues[n - 1] * (1 - p.sellingCostsPct) - balances[n - 1];
  return {
    outflows, homeValues, balances, payments, maints,
    netWorth: nw, initialEquity: deposit + closingPurchase,
    sdlt, purchasePrice, deposit,
  };
}

function simulateRent(rents, returns, buy, startIdx, endIdx) {
  const n = endIdx - startIdx;
  let portfolio = buy.initialEquity;
  const portfolioPath = new Array(n);
  const rentPath = new Array(n);
  for (let i = 0; i < n; i++) {
    portfolioPath[i] = portfolio;
    const rent = rents[startIdx + i];
    rentPath[i] = rent;
    const delta = buy.outflows[i] - rent;
    portfolio = Math.max(portfolio + delta, 0);   // matches Python floor-at-zero
    if (i < n - 1) portfolio *= (1 + returns[startIdx + i]);
  }
  return { portfolioPath, rentPath, netWorth: portfolioPath[n - 1] };
}

function runPair(data, startIdx, endIdx, p) {
  const buy = simulateBuy(data.prices, data.rates, data.ym, startIdx, endIdx, p);
  const rent = simulateRent(data.rents, data.returns, buy, startIdx, endIdx);
  return { buy, rent, R: rent.netWorth / buy.netWorth };
}

// Rolling quarterly cohorts (Python: range(0, n-3, 3)), all ending at endIdx.
function runRolling(data, endIdx, p) {
  const out = [];
  for (let s = 0; s < endIdx - 3; s += 3) {
    const r = runPair(data, s, endIdx, p);
    out.push({
      startIdx: s, ym: data.ym[s], R: r.R,
      nwBuy: r.buy.netWorth, nwRent: r.rent.netWorth,
      winner: r.R > 1 ? 'RENT' : 'BUY',
    });
  }
  return out;
}

// ---- Forward-looking simulation & required appreciation rate ----
// Mirrors uk_horse_race_v2.forward_rar: fixed mortgage rate, constant rent
// growth, constant opportunity-cost return, constant price growth g.
function forwardSim(price, rentMonth, mortgageRate, oppAnnual, growthAnnual, horizonYears, p, sdltGbp) {
  const deposit = p.depositShare * price;
  const closing = p.purchaseCostsPct * price + sdltGbp;
  let bal = price - deposit;
  const n = Math.round(horizonYears * 12);
  const totalAmort = Math.round(p.amortYears * 12);
  const mOpp = monthlyRate(oppAnnual);
  const mRate = monthlyRate(mortgageRate);
  const mRentG = monthlyRate(p.rentGrowthAnnual);
  const mG = monthlyRate(growthAnnual);

  let hv = price, portfolio = deposit + closing, rent = rentMonth, mr = totalAmort;
  const ownerPath = new Array(n), renterPath = new Array(n);
  for (let i = 0; i < n; i++) {
    const maint = (p.maintPct / 12) * hv;
    let pmt = 0;
    if (bal > 0 && mr > 0) {
      pmt = bal * mRate / (1 - Math.pow(1 + mRate, -mr));
      const interest = bal * mRate;
      const principal = Math.min(pmt - interest, bal);
      bal = Math.max(bal - principal, 0);
      mr -= 1;
    }
    portfolio += (pmt + maint) - rent;
    portfolio *= (1 + mOpp);
    hv *= (1 + mG);
    rent *= (1 + mRentG);
    ownerPath[i] = hv * (1 - p.sellingCostsPct) - bal;
    renterPath[i] = portfolio;
  }
  return {
    buyNW: hv * (1 - p.sellingCostsPct) - bal,
    rentNW: portfolio,
    ownerPath, renterPath,
  };
}

// Bisection for the growth rate at which buyNW == rentNW (RAR).
function requiredAppreciationRate(price, rentMonth, mortgageRate, oppAnnual, horizonYears, p, sdltGbp) {
  const f = g => {
    const s = forwardSim(price, rentMonth, mortgageRate, oppAnnual, g, horizonYears, p, sdltGbp);
    return s.rentNW - s.buyNW;
  };
  let lo = -0.10, hi = 0.30;
  let flo = f(lo), fhi = f(hi);
  if (flo * fhi > 0) return null;
  for (let it = 0; it < 80; it++) {
    const mid = (lo + hi) / 2, fm = f(mid);
    if (Math.abs(fm) < 1e-7 || (hi - lo) < 1e-8) return mid;
    if (flo * fm <= 0) { hi = mid; fhi = fm; } else { lo = mid; flo = fm; }
  }
  return (lo + hi) / 2;
}

// Node export for tests; in the browser these are plain globals.
if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    sdltEnglandFTB, monthlyRate, monthlyPayment,
    simulateBuy, simulateRent, runPair, runRolling,
    forwardSim, requiredAppreciationRate,
  };
}
