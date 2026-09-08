#!/usr/bin/env python3
r"""
UK: Monthly Rent vs Buy Horse-Race Analysis (v2 — whitepaper engine)
====================================================================

Faithful UK port of the CZ whitepaper engine (cz_horse_race.py + full_rerun_v5.py
spec), adapted per Martin's decisions of 2026-07-09:

  Geography        : England (headline) + 9 English regions (forward RAR)
  Sample           : Jan 2005 - Dec 2025, monthly
  Prices           : UK HPI all-dwellings average price, England
  Rents            : ONS PIPR all-property average rent (GBP/month), England
                     (market rent every month — no annual-increase cap)
  Mortgage rate    : BoE effective rate on new advances (CFMBJ95), variable
                     monthly recast baseline; fixation as sensitivity
  Deposit          : 20% baseline (sensitivity incl. 100% = cash purchase)
  Term             : 25y baseline
  Maintenance      : 2% of current property value p.a. (all-in incl. insurance),
                     no separate depreciation drag (mirrors CZ v5 spec)
  Purchase costs   : 1.5% of price + period-accurate England SDLT (FTB rules)
  Selling costs    : 2% of sale price
  Renter portfolio : MSCI ACWI net total return in GBP (baseline);
                     FTSE 100 TR as robustness
  Bonds (RAR alt.) : UK 10y gilt yield

Differences from the CZ engine are ONLY: whole-property units (no m2),
parameterized purchase/selling costs, and the SDLT module. All simulation
mathematics (payment formula, monthly recast, cash-flow matching, terminal
wealth) is identical to cz_horse_race.py as run by full_rerun_v5.py.
"""

import pandas as pd
import numpy as np
from typing import Optional, Tuple, Dict, List

# ============================================================================
# SDLT (STAMP DUTY LAND TAX) — ENGLAND, FIRST-TIME BUYER, 2003-2026
# ============================================================================
# Chronology sources: GOV.UK "SDLT rates from 1 Dec 2003 to 31 Mar 2025",
# GOV.UK current rates page, HoC Library SN07050 / CBP-9814.
# Pre-Dec-2014 SDLT was a SLAB tax (rate applies to the WHOLE price);
# from 4 Dec 2014 it is a SLICE tax (marginal bands).

def _slab(price: float, bands: List[Tuple[float, float]]) -> float:
    """Slab SDLT: rate of the band the price falls in, applied to whole price.
    bands = [(upper_limit, rate), ...] ascending; last band upper = inf."""
    for upper, rate in bands:
        if price <= upper:
            return price * rate
    return 0.0


def _slice(price: float, bands: List[Tuple[float, float]]) -> float:
    """Slice (marginal) SDLT. bands = [(upper_limit, rate), ...] ascending."""
    tax, lower = 0.0, 0.0
    for upper, rate in bands:
        if price > lower:
            tax += (min(price, upper) - lower) * rate
        lower = upper
        if price <= upper:
            break
    return tax


def sdlt_england(price: float, date, first_time_buyer: bool = True) -> float:
    """SDLT payable in England on a residential purchase at `price` completed
    in month `date`, for a first-time buyer (main residence, no other property).

    Where FTB relief exists it is applied (falling back to standard rates when
    the price exceeds the relief cap). Returns GBP.
    """
    d = pd.Timestamp(date)

    INF = float('inf')

    # ---- standard schedules by period ----
    if d < pd.Timestamp('2005-03-17'):
        std = ('slab', [(60_000, 0.0), (250_000, 0.01), (500_000, 0.03), (INF, 0.04)])
    elif d < pd.Timestamp('2006-03-23'):
        std = ('slab', [(120_000, 0.0), (250_000, 0.01), (500_000, 0.03), (INF, 0.04)])
    elif d < pd.Timestamp('2008-09-03'):
        std = ('slab', [(125_000, 0.0), (250_000, 0.01), (500_000, 0.03), (INF, 0.04)])
    elif d < pd.Timestamp('2010-01-01'):
        # GFC holiday: nil-rate band raised to GBP 175k (3 Sep 2008 - 31 Dec 2009)
        std = ('slab', [(175_000, 0.0), (250_000, 0.01), (500_000, 0.03), (INF, 0.04)])
    elif d < pd.Timestamp('2011-04-06'):
        std = ('slab', [(125_000, 0.0), (250_000, 0.01), (500_000, 0.03), (INF, 0.04)])
    elif d < pd.Timestamp('2012-03-22'):
        std = ('slab', [(125_000, 0.0), (250_000, 0.01), (500_000, 0.03),
                        (1_000_000, 0.04), (INF, 0.05)])
    elif d < pd.Timestamp('2014-12-04'):
        std = ('slab', [(125_000, 0.0), (250_000, 0.01), (500_000, 0.03),
                        (1_000_000, 0.04), (2_000_000, 0.05), (INF, 0.07)])
    elif d < pd.Timestamp('2020-07-08'):
        std = ('slice', [(125_000, 0.0), (250_000, 0.02), (925_000, 0.05),
                         (1_500_000, 0.10), (INF, 0.12)])
    elif d < pd.Timestamp('2021-07-01'):
        # COVID holiday: nil-rate GBP 500k for all buyers
        std = ('slice', [(500_000, 0.0), (925_000, 0.05), (1_500_000, 0.10), (INF, 0.12)])
    elif d < pd.Timestamp('2021-10-01'):
        std = ('slice', [(250_000, 0.0), (925_000, 0.05), (1_500_000, 0.10), (INF, 0.12)])
    elif d < pd.Timestamp('2022-09-23'):
        std = ('slice', [(125_000, 0.0), (250_000, 0.02), (925_000, 0.05),
                         (1_500_000, 0.10), (INF, 0.12)])
    elif d < pd.Timestamp('2025-04-01'):
        std = ('slice', [(250_000, 0.0), (925_000, 0.05), (1_500_000, 0.10), (INF, 0.12)])
    else:
        std = ('slice', [(125_000, 0.0), (250_000, 0.02), (925_000, 0.05),
                         (1_500_000, 0.10), (INF, 0.12)])

    def standard_tax():
        kind, bands = std
        return _slab(price, bands) if kind == 'slab' else _slice(price, bands)

    if not first_time_buyer:
        return standard_tax()

    # ---- FTB relief windows ----
    # 25 Mar 2010 - 24 Mar 2012: FTB pays nothing up to GBP 250k
    if pd.Timestamp('2010-03-25') <= d <= pd.Timestamp('2012-03-24'):
        if price <= 250_000:
            return 0.0
        return standard_tax()

    # 22 Nov 2017 - 7 Jul 2020 and 1 Jul 2021 - 22 Sep 2022:
    # FTB 0% to 300k, 5% 300-500k; no relief above 500k
    if (pd.Timestamp('2017-11-22') <= d < pd.Timestamp('2020-07-08')) or \
       (pd.Timestamp('2021-07-01') <= d < pd.Timestamp('2022-09-23')):
        if price <= 500_000:
            return max(0.0, (price - 300_000)) * 0.05
        return standard_tax()

    # 8 Jul 2020 - 30 Jun 2021: COVID holiday (500k nil) is at least as good
    # as FTB relief — standard_tax() already reflects it.

    # 23 Sep 2022 - 31 Mar 2025: FTB 0% to 425k, 5% 425-625k; no relief above
    if pd.Timestamp('2022-09-23') <= d < pd.Timestamp('2025-04-01'):
        if price <= 625_000:
            return max(0.0, (price - 425_000)) * 0.05
        return standard_tax()

    # 1 Apr 2025 onwards: FTB 0% to 300k, 5% 300-500k; no relief above
    if d >= pd.Timestamp('2025-04-01'):
        if price <= 500_000:
            return max(0.0, (price - 300_000)) * 0.05
        return standard_tax()

    return standard_tax()


# ============================================================================
# DATA LOADING (MONTHLY)
# ============================================================================

def load_uk_housing(path: str,
                    start: Optional[str] = '2005-01-31',
                    end: Optional[str] = '2025-12-31') -> pd.DataFrame:
    """Load the clean England monthly dataset.

    Expected columns: Date, Rent_GBP (avg monthly rent, all properties),
    Purchase_Price_GBP (avg all-dwellings price), Mortgage_Rate_pct
    (annual nominal, percent).
    """
    df = pd.read_csv(path)
    if 'Date' not in df.columns:
        raise ValueError(f"'Date' column not found. Available: {df.columns.tolist()}")
    df['Date'] = pd.to_datetime(df['Date'])
    df = df.set_index('Date').sort_index()
    df.index = df.index.to_period('M').to_timestamp('M')

    col_map = {'Rent_GBP': 'rent_gbp',
               'Purchase_Price_GBP': 'purchase_price_gbp',
               'Mortgage_Rate_pct': 'mortgage_rate_pct'}
    for old in col_map:
        if old not in df.columns:
            raise ValueError(f"Expected column '{old}' not found. Available: {df.columns.tolist()}")

    # Optional loan-to-value rate bands (v3 pipeline). When present, the buy
    # simulation reprices at each refix according to the borrower's CURRENT LTV
    # rather than charging the origination-LTV premium for the whole term.
    opt_map = {'Rate_75LTV_pct': 'rate_75_pct',
               'Rate_90LTV_pct': 'rate_90_pct',
               'Rate_95LTV_pct': 'rate_95_pct',
               'Bank_Rate_pct': 'bank_rate_pct',
               'Mortgage_Rate_CFMBJ95_pct': 'mortgage_rate_cfmbj95_pct'}
    present_opt = {o: n for o, n in opt_map.items() if o in df.columns}
    keep = {**col_map, **present_opt}
    df = df.rename(columns=keep)[list(keep.values())].copy()

    if df['mortgage_rate_pct'].median() > 1.0:
        df['mortgage_rate_annual'] = df['mortgage_rate_pct'] / 100.0
    else:
        df['mortgage_rate_annual'] = df['mortgage_rate_pct']
    df = df.drop(columns=['mortgage_rate_pct'])

    df = df.dropna(subset=['rent_gbp', 'purchase_price_gbp', 'mortgage_rate_annual'])
    if start is not None:
        df = df[df.index >= pd.Timestamp(start)]
    if end is not None:
        df = df[df.index <= pd.Timestamp(end)]
    if len(df) == 0:
        raise ValueError("No valid data after cleaning")

    print(f"Housing data: {len(df)} months from {df.index[0]:%Y-%m} to {df.index[-1]:%Y-%m}")
    return df


def load_uk_returns(path: str, column: str = 'acwi_net_gbp_ret') -> pd.Series:
    """Load monthly GBP total returns (wide CSV: Date + return columns, decimals)."""
    df = pd.read_csv(path)
    df['Date'] = pd.to_datetime(df['Date'])
    df = df.set_index('Date').sort_index()
    df.index = df.index.to_period('M').to_timestamp('M')
    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found. Available: {df.columns.tolist()}")
    s = df[column].dropna()
    print(f"Returns data ({column}): {len(s)} months from {s.index[0]:%Y-%m} to {s.index[-1]:%Y-%m}")
    return s


def align_monthly_data(housing_df: pd.DataFrame,
                       returns: pd.Series) -> Tuple[pd.DataFrame, pd.Series]:
    """Align housing data and returns to the common month-end index."""
    common = housing_df.index.intersection(returns.index)
    if len(common) == 0:
        raise ValueError("No overlapping dates between housing and returns data")
    ha = housing_df.loc[common].sort_index()
    ar = returns.loc[common].sort_index()
    print(f"Aligned data: {len(common)} months from {common[0]:%Y-%m} to {common[-1]:%Y-%m}")
    return ha, ar


# ============================================================================
# MORTGAGE MATH (identical to CZ engine)
# ============================================================================

def compute_monthly_mortgage_rate(annual_rate: float) -> float:
    return (1 + annual_rate) ** (1 / 12) - 1


LTV_BAND_COLS = ('rate_75_pct', 'rate_90_pct', 'rate_95_pct')


def rate_for_ltv(row, ltv: float) -> float:
    """Quoted fixed rate for the borrower's CURRENT loan-to-value.

    Lenders price mortgages in LTV bands, and a first-time buyer moves between
    them: the loan amortises and the dwelling usually appreciates, so a buyer who
    starts at 90% LTV is typically well inside a cheaper band by their first
    refix. Charging the origination-LTV premium at every refix would overstate
    the cost of owning by up to 4pp over 2010-2014, when the high-LTV premium
    peaked at +2.2pp -- a Jan-2005 buyer is at 74.8% LTV by their Jan-2010 refix,
    so pricing them at 90% LTV then is simply wrong.

    Piecewise-linear between the three published bands. Below 75% LTV the 75%
    rate is used unchanged, which is mildly conservative: lenders price 60% LTV
    lower still, but the Bank of England publishes no band below 75%.
    """
    r75 = row['rate_75_pct'] / 100.0
    r90 = row['rate_90_pct'] / 100.0
    r95 = row['rate_95_pct'] / 100.0
    if ltv <= 0.75:
        return r75
    if ltv <= 0.90:
        return r75 + (r90 - r75) * (ltv - 0.75) / 0.15
    if ltv <= 0.95:
        return r90 + (r95 - r90) * (ltv - 0.90) / 0.05
    return r95


def compute_monthly_payment(balance: float, monthly_rate: float,
                            months_remaining: int) -> float:
    if balance <= 0:
        return 0.0
    if monthly_rate == 0:
        return balance / months_remaining if months_remaining > 0 else balance
    if months_remaining <= 0:
        return balance
    return balance * (monthly_rate * (1 + monthly_rate) ** months_remaining) / \
        ((1 + monthly_rate) ** months_remaining - 1)


# ============================================================================
# STRATEGY SIMULATIONS
# ============================================================================

def simulate_buy(housing_df: pd.DataFrame,
                 start_idx: int,
                 deposit_share: float = 0.20,
                 amort_years: int = 25,
                 maintenance_pct_of_value: float = 0.02,
                 depreciation_drag_annual: float = 0.0,
                 rate_fixation_years: Optional[int] = None,
                 purchase_costs_pct: float = 0.015,
                 selling_costs_pct: float = 0.02,
                 include_sdlt: bool = True) -> Dict:
    """Simulate BUY strategy at monthly frequency (England average property).

    Mirrors cz_horse_race.simulate_buy under the v5 whitepaper spec, with
    parameterized transaction costs and period-accurate England FTB SDLT.
    """
    df = housing_df.iloc[start_idx:].copy()
    n_months = len(df)

    home_values = np.zeros(n_months)
    mortgage_balances = np.zeros(n_months)
    mortgage_payments = np.zeros(n_months)
    maintenance_costs = np.zeros(n_months)
    owner_outflows = np.zeros(n_months)

    purchase_price = df.iloc[0]['purchase_price_gbp']
    purchase_date = df.index[0]

    sdlt = sdlt_england(purchase_price, purchase_date) if include_sdlt else 0.0
    closing_costs_purchase = purchase_costs_pct * purchase_price + sdlt

    deposit = deposit_share * purchase_price
    balance = purchase_price - deposit

    months_remaining = amort_years * 12
    home_value = purchase_price

    drag_monthly = 1 - (1 - depreciation_drag_annual) ** (1 / 12)

    fixation_months = rate_fixation_years * 12 if rate_fixation_years else 1
    fixed_annual_rate = None
    # Reprice by current LTV at each refix when the v3 rate bands are available.
    use_ltv_bands = all(c in df.columns for c in LTV_BAND_COLS)

    for i, (date, row) in enumerate(df.iterrows()):
        home_values[i] = home_value
        mortgage_balances[i] = balance

        monthly_maintenance = (maintenance_pct_of_value / 12) * home_value
        maintenance_costs[i] = monthly_maintenance

        if i % fixation_months == 0 or fixed_annual_rate is None:
            if use_ltv_bands:
                # At origination the LTV is set by the deposit; at every refix it
                # is the borrower's actual position.
                current_ltv = (1.0 - deposit_share) if i == 0 else (
                    balance / home_value if home_value > 0 else 0.0)
                fixed_annual_rate = rate_for_ltv(row, current_ltv)
            else:
                fixed_annual_rate = row['mortgage_rate_annual']
        monthly_rate = compute_monthly_mortgage_rate(fixed_annual_rate)

        payment = compute_monthly_payment(balance, monthly_rate, months_remaining)
        mortgage_payments[i] = payment
        owner_outflows[i] = payment + monthly_maintenance

        if balance > 0 and months_remaining > 0:
            interest = balance * monthly_rate
            principal = min(payment - interest, balance)
            balance = max(balance - principal, 0)
            months_remaining -= 1

        if i < n_months - 1:
            price_return = (df.iloc[i + 1]['purchase_price_gbp'] /
                            df.iloc[i]['purchase_price_gbp']) - 1
            home_value *= (1 + price_return) * (1 - drag_monthly)

    closing_costs_sale = selling_costs_pct * home_values[-1]
    net_sale_proceeds = home_values[-1] - closing_costs_sale
    final_nw = net_sale_proceeds - mortgage_balances[-1]

    total_initial_equity = deposit + closing_costs_purchase

    return {
        'home_values': home_values,
        'mortgage_balances': mortgage_balances,
        'mortgage_payments': mortgage_payments,
        'maintenance_costs': maintenance_costs,
        'owner_outflows': owner_outflows,
        'net_worth': final_nw,
        'initial_equity': total_initial_equity,
        'closing_costs_purchase': closing_costs_purchase,
        'sdlt_paid': sdlt,
        'closing_costs_sale': closing_costs_sale,
        'purchase_price': purchase_price,
        'dates': df.index,
    }


def simulate_rent_invest(housing_df: pd.DataFrame,
                         stock_returns: pd.Series,
                         buy_paths: Dict,
                         start_idx: int,
                         leverage: float = 1.0,
                         margin_spread: float = 0.015,
                         maintenance_margin: float = 0.30,
                         relever_after_call: bool = False) -> Dict:
    """Simulate RENT+INVEST with monthly cash-flow matching (mirrors CZ engine).

    Renter starts with the buyer's total initial cash outlay (deposit +
    purchase costs incl. SDLT) and each month invests/withdraws the
    difference between the owner's outflow and market rent.

    Optional margin leverage (comments.txt item 5). `leverage` = 1.0 is the
    unlevered baseline and leaves the original arithmetic untouched.

    The levered case is modelled as a ONE-OFF margin loan that is then left to
    ride, not as a constantly rebalanced constant-leverage position. That is what
    a buy-and-hold retail investor actually does, and it is the only version in
    which a margin call can occur: monthly rebalancing to a fixed leverage
    deleverages on the way down and so never gets called, at the cost of
    volatility drag. Monthly contributions go into equity, which naturally
    deleverages the position over time.

    Forced liquidation is modelled explicitly. If equity falls below
    `maintenance_margin` of the position, assets are sold to restore exactly that
    ratio and the debt is repaid from the proceeds. Interactive Brokers state
    they "generally will not issue margin calls" and "generally will liquidate
    positions ... without prior notice", so the investor does not choose the
    timing. By default the position is NOT re-levered afterwards.

    Margin interest accrues at Bank Rate + `margin_spread`, read from the
    `bank_rate_pct` column when present (IBKR U.K. Tier I is benchmark + 1.50%).
    Falls back to a flat `margin_spread` if Bank Rate is unavailable.

    Two caveats that belong in the text, not just here. Monthly observation
    understates drawdowns: month-end missed the daily trough by ~4pp in the
    financial crisis and ~9-11pp in 2020, and brokers liquidate in real time, so
    a monthly simulation will under-report margin calls. And sterling did much of
    the work in both episodes -- 2x survived 2020 only because GBP fell ~13% in a
    global equity crash, which is a property of the currency pair in those
    episodes, not of equity leverage.
    """
    df = housing_df.iloc[start_idx:].copy()
    returns = stock_returns.iloc[start_idx:].copy()
    n_months = len(df)

    portfolio_values = np.zeros(n_months)
    rent_payments = np.zeros(n_months)
    net_flows = np.zeros(n_months)
    debt_values = np.zeros(n_months)
    equity_ratios = np.ones(n_months)

    equity0 = buy_paths['initial_equity']
    position = equity0 * leverage          # gross assets
    debt = position - equity0              # margin borrowing
    external_cash_required = 0.0
    margin_calls = 0
    forced_sales_total = 0.0
    min_equity_ratio = 1.0

    has_bank_rate = 'bank_rate_pct' in df.columns

    for i, (date, row) in enumerate(df.iterrows()):
        equity = position - debt
        portfolio_values[i] = equity
        debt_values[i] = debt
        equity_ratios[i] = (equity / position) if position > 0 else 1.0

        monthly_rent = row['rent_gbp']
        rent_payments[i] = monthly_rent

        delta = buy_paths['owner_outflows'][i] - monthly_rent
        net_flows[i] = delta

        if delta > 0:
            position += delta                      # contribution buys assets
        else:
            withdrawal = abs(delta)
            sellable = position - debt             # cannot sell into negative equity
            if sellable >= withdrawal:
                position -= withdrawal
            else:
                external_cash_required += (withdrawal - max(sellable, 0.0))
                position = debt                    # equity exhausted

        if i < n_months - 1:
            r = returns.iloc[i]
            if not np.isnan(r):
                position *= (1 + r)
            if debt > 0:
                base = (row['bank_rate_pct'] / 100.0) if has_bank_rate else 0.0
                m_annual = max(base + margin_spread, 0.0)
                debt *= (1 + (1 + m_annual) ** (1 / 12) - 1)

            # --- maintenance-margin check, after returns and interest ---
            if debt > 0 and position > 0:
                equity = position - debt
                ratio = equity / position
                min_equity_ratio = min(min_equity_ratio, ratio)
                if ratio < maintenance_margin:
                    margin_calls += 1
                    if equity <= 0:
                        forced_sales_total += position   # wiped out
                        position, debt = 0.0, 0.0
                    else:
                        target_position = equity / maintenance_margin
                        sold = position - target_position
                        forced_sales_total += sold
                        position = target_position
                        debt = max(debt - sold, 0.0)
                        if not relever_after_call:
                            # repay in full and continue unlevered
                            position -= debt
                            debt = 0.0

    final_equity = max(position - debt, 0.0)

    return {
        'portfolio_values': portfolio_values,
        'rent_payments': rent_payments,
        'net_flows': net_flows,
        'debt_values': debt_values,
        'equity_ratios': equity_ratios,
        'external_cash_required': external_cash_required,
        'leverage': leverage,
        'margin_calls': margin_calls,
        'forced_sales_total': forced_sales_total,
        'min_equity_ratio': min_equity_ratio,
        'net_worth': final_equity,
        'dates': df.index,
    }


# ============================================================================
# RAR (REQUIRED APPRECIATION RATE)
# ============================================================================

def compute_rar(start_idx: int,
                housing_data: pd.DataFrame,
                stock_returns: pd.Series,
                horizon_months: int = 120,
                deposit_share: float = 0.20,
                amort_years: int = 25,
                maint_pct: float = 0.02,
                purchase_costs_pct: float = 0.015,
                selling_costs_pct: float = 0.02,
                include_sdlt: bool = True,
                use_stock_returns: bool = True,
                fixed_annual_return: Optional[float] = None) -> Optional[float]:
    """Historical RAR: annual appreciation A s.t. BUY NW == RENT NW over the
    horizon, holding actual mortgage-rate, rent and stock-return paths fixed.
    Mirrors rar_analysis.compute_rar with UK cost structure."""
    from scipy.optimize import brentq

    end_idx = min(start_idx + horizon_months, len(housing_data))
    if end_idx - start_idx < horizon_months:
        return None

    df = housing_data.iloc[start_idx:end_idx]
    n = len(df)

    purchase_price = df.iloc[0]['purchase_price_gbp']
    purchase_date = df.index[0]
    deposit = deposit_share * purchase_price
    sdlt = sdlt_england(purchase_price, purchase_date) if include_sdlt else 0.0
    closing_buy = purchase_costs_pct * purchase_price + sdlt
    initial_balance = purchase_price - deposit
    total_amort_months = amort_years * 12

    rets = stock_returns.iloc[start_idx:end_idx].values

    def net_worth_diff(annual_apprec):
        monthly_apprec = (1 + annual_apprec) ** (1 / 12) - 1

        home_value = purchase_price
        balance = initial_balance
        months_remaining = total_amort_months

        buy_outflows = []
        for i in range(n):
            rate_monthly = (1 + df.iloc[i]['mortgage_rate_annual']) ** (1 / 12) - 1
            maintenance = (maint_pct / 12) * home_value
            if balance > 0 and months_remaining > 0:
                payment = balance * rate_monthly / (1 - (1 + rate_monthly) ** (-months_remaining))
                interest = balance * rate_monthly
                principal = min(payment - interest, balance)
                balance = max(balance - principal, 0)
                months_remaining -= 1
            else:
                payment = 0
            buy_outflows.append(payment + maintenance)
            if i < n - 1:
                home_value *= (1 + monthly_apprec)

        buy_nw = home_value * (1 - selling_costs_pct) - balance

        portfolio = deposit + closing_buy
        for i in range(n):
            delta = buy_outflows[i] - df.iloc[i]['rent_gbp']
            portfolio += delta
            if use_stock_returns:
                ret = rets[i] if i < len(rets) else 0.0
            else:
                ret = (1 + fixed_annual_return) ** (1 / 12) - 1
            portfolio *= (1 + ret)

        return portfolio - buy_nw

    try:
        return brentq(net_worth_diff, -0.10, 0.30, xtol=1e-6)
    except Exception:
        return None


def forward_rar(price: float,
                rent_month: float,
                mortgage_rate: float,
                opp_cost_annual: float,
                horizon_years: int = 10,
                deposit_share: float = 0.20,
                amort_years: int = 25,
                maint_pct: float = 0.02,
                purchase_costs_pct: float = 0.015,
                selling_costs_pct: float = 0.02,
                sdlt_gbp: float = 0.0,
                rent_growth_annual: float = 0.03) -> Optional[float]:
    """Forward-looking RAR under current market conditions (mirrors
    rar_analysis.forward_rar). `sdlt_gbp` is passed explicitly so callers
    can price current-rules SDLT for the given price/geography."""
    from scipy.optimize import brentq

    deposit = deposit_share * price
    closing = purchase_costs_pct * price + sdlt_gbp
    balance0 = price - deposit
    n = horizon_years * 12
    total_amort = amort_years * 12
    monthly_opp = (1 + opp_cost_annual) ** (1 / 12) - 1
    monthly_rate = (1 + mortgage_rate) ** (1 / 12) - 1
    rent_growth_monthly = (1 + rent_growth_annual) ** (1 / 12) - 1

    def nw_diff(annual_apprec):
        monthly_apprec = (1 + annual_apprec) ** (1 / 12) - 1
        hv, bal, mr = price, balance0, total_amort
        portfolio = deposit + closing
        rent_m = rent_month

        for i in range(n):
            maint = (maint_pct / 12) * hv
            if bal > 0 and mr > 0:
                pmt = bal * monthly_rate / (1 - (1 + monthly_rate) ** (-mr))
                interest = bal * monthly_rate
                princ = min(pmt - interest, bal)
                bal = max(bal - princ, 0)
                mr -= 1
            else:
                pmt = 0
            delta = (pmt + maint) - rent_m
            portfolio += delta
            portfolio *= (1 + monthly_opp)
            hv *= (1 + monthly_apprec)
            rent_m *= (1 + rent_growth_monthly)

        buy_nw = hv * (1 - selling_costs_pct) - bal
        return portfolio - buy_nw

    try:
        return brentq(nw_diff, -0.10, 0.30, xtol=1e-6)
    except Exception:
        return None


# ============================================================================
# CONVENIENCE RUNNERS (mirror full_rerun_v5.py patterns)
# ============================================================================

# Baseline = the typical first-time buyer: 10% deposit, 30-year term, 1.5% all-in
# maintenance, variable effective rate, 1.5% purchase costs + FTB SDLT, 2% selling.
# Baseline = the typical English FIRST-TIME BUYER, calibrated to data wherever a
# figure exists. Every value here is a baseline, not a claim about any individual
# buyer; the robustness section reports the range around each.
#
#   deposit_share 0.10 (90% LTV)  FCA PSD001/PSD007 puts the FTB median at 84.8%
#       and the modal density band at >85-90%; 90% sits at the top of that band.
#       The median is held down by the ~13% of the FCA sample that is
#       scheme-assisted (Help-to-Buy borrowers take ~75% LTV mortgages on 5% cash
#       deposits), so it understates the unassisted FTB's leverage. Sensitivity
#       reports 75/85/90/95.
#   amort_years 30                FCA PSD median is exactly 360 months, and the
#       English Housing Survey 2024-25 (Annex Table 2.1) has 62% of recent
#       England FTBs on 30 years or more, up from 47% in 2019-20. Unchanged.
#   maintenance 1.5%              ONS MJX9 consumption of fixed capital on
#       dwellings over dwellings-plus-land = 1.20% of market value (1995-2024
#       mean), plus ~0.35% cash maintenance and buildings insurance. Band
#       1.2-1.8%. This is an ALL-IN charge, hence depreciation_drag_annual = 0.
#   rate_fixation_years 5         99.1% of FTB new lending in 2025 H1 was
#       fixed-rate, and the >3-5 year band is the FTB modal choice in six of
#       seven published periods. Refixes at the prevailing 5-year rate.
#   purchase_costs_pct 0.012      Conveyancing incl. disbursements GBP 1,421
#       (reallymoving Cost of Moving 2025, England FTBs) + RICS Level 2 survey
#       GBP 462 + mortgage product fee GBP 1,129 (Moneyfacts) on a GBP 250,000
#       purchase. Excludes SDLT, which is modelled separately and exactly.
#   selling_costs_pct 0.018       Agent commission 1.42% incl. VAT + conveyancing
#       GBP 929 + EPC GBP 65.
BASE_SPEC = dict(
    deposit_share=0.10,
    amort_years=30,
    maintenance_pct_of_value=0.015,
    depreciation_drag_annual=0.0,
    rate_fixation_years=5,
    purchase_costs_pct=0.012,
    selling_costs_pct=0.018,
    include_sdlt=True,
)


def sim_pair(ha: pd.DataFrame, ar: pd.Series, start: int,
             end_idx: Optional[int] = None, **overrides) -> Tuple[Dict, Dict]:
    """Run one BUY / RENT+INVEST pair. end_idx truncates the sample (for
    fixed-horizon runs), exactly as in full_rerun_v5.sim()."""
    p = {**BASE_SPEC, **overrides}
    # Route the renter-side arguments to simulate_rent_invest; everything else
    # belongs to simulate_buy.
    rent_keys = ('leverage', 'margin_spread', 'maintenance_margin', 'relever_after_call')
    rp = {k: p.pop(k) for k in rent_keys if k in p}
    h = ha if end_idx is None else ha.iloc[:end_idx]
    a = ar if end_idx is None else ar.iloc[:end_idx]
    b = simulate_buy(h, start, **p)
    r = simulate_rent_invest(h, a, b, start, **rp)
    return b, r


def run_rolling(ha: pd.DataFrame, ar: pd.Series,
                start_every_n_months: int = 1, **overrides) -> pd.DataFrame:
    """Rolling-start cohorts, all ending at the sample end.

    Monthly starts from revision round 4 (previously quarterly). Monthly removes
    an arbitrary grid at no cost, but it does NOT add independent information:
    the underlying sample is the same, and the number of non-overlapping
    holding-period windows is unchanged. Say so wherever the cohort count is
    reported, or 253 cohorts will be read as 253 observations.
    """
    n_months = len(ha)
    rows = []
    for start in range(0, n_months - 3, start_every_n_months):
        b, r = sim_pair(ha, ar, start, **overrides)
        nb, nr = b['net_worth'], r['net_worth']
        row = ha.iloc[start]
        rows.append({
            'start_date': ha.index[start],
            'months': n_months - start,
            'nw_buy': nb, 'nw_rent': nr, 'R': nr / nb,
            'winner': 'RENT' if nr > nb else 'BUY',
            'mortgage_rate': row['mortgage_rate_annual'],
            'pr_ratio': row['purchase_price_gbp'] / (row['rent_gbp'] * 12),
            'sdlt_paid': b['sdlt_paid'],
        })
    return pd.DataFrame(rows)


def run_rolling_fixed(ha: pd.DataFrame, ar: pd.Series,
                      horizon_months: int = 60,
                      start_every_n_months: int = 1, **overrides) -> pd.DataFrame:
    """Cohorts that each hold for exactly `horizon_months`, started every month.

    This is the paper's primary cohort design from revision round 4. Every cohort
    holds for the same length of time, so cohorts are comparable with one another
    and with the buyer's own decision problem: "if I buy and hold for five years,
    what happens?"

    The default horizon is five years because that is roughly how long a UK
    first-time buyer keeps their first home - Santander put the average at 4.5
    years. It also makes the selling-cost deduction the right treatment rather
    than an artefact: we are measuring the buyer's wealth at the point they move
    out of their first home, which is when those costs are actually incurred.

    Contrast run_rolling(), which runs every cohort to the sample end. That gives
    cohorts of wildly unequal length (258 months down to 4) and loads the average
    with short recent cohorts that cannot amortise their round-trip transaction
    costs, which pushes the buy-win share down for reasons that have nothing to
    do with tenure. Keep it as robustness, not as the headline.
    """
    n_months = len(ha)
    rows = []
    for start in range(0, n_months - horizon_months + 1, start_every_n_months):
        b, r = sim_pair(ha, ar, start, end_idx=start + horizon_months, **overrides)
        nb, nr = b['net_worth'], r['net_worth']
        row = ha.iloc[start]
        rows.append({
            'start_date': ha.index[start],
            'months': horizon_months,
            'nw_buy': nb, 'nw_rent': nr, 'R': nr / nb,
            'winner': 'RENT' if nr > nb else 'BUY',
            'mortgage_rate': row['mortgage_rate_annual'],
            'pr_ratio': row['purchase_price_gbp'] / (row['rent_gbp'] * 12),
            'sdlt_paid': b['sdlt_paid'],
        })
    return pd.DataFrame(rows)


def run_horizons(ha: pd.DataFrame, ar: pd.Series,
                 horizons_years: List[int] = (1, 2, 3, 5, 7, 10, 12, 15),
                 **overrides) -> Tuple[pd.DataFrame, Dict[int, np.ndarray]]:
    """Fixed-horizon runs started every month (CZ horizon analysis)."""
    n_months = len(ha)
    summary, all_R = [], {}
    for years in horizons_years:
        hm = years * 12
        Rs = []
        for start in range(0, n_months - hm, 1):
            b, r = sim_pair(ha, ar, start, end_idx=start + hm, **overrides)
            Rs.append(r['net_worth'] / b['net_worth'])
        arr = np.array(Rs)
        rent_wins = int(np.sum(arr > 1))
        total = len(arr)
        summary.append({'years': years, 'n': total,
                        'buy_pct': round(100 * (total - rent_wins) / total),
                        'rent_pct': round(100 * rent_wins / total),
                        'med_R': float(np.median(arr))})
        all_R[years] = arr
    return pd.DataFrame(summary), all_R
