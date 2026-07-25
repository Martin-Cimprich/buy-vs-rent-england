#!/usr/bin/env python3
"""
Fetch the licence-restricted financial series used by the paper.

The MSCI ACWI index levels and the Morningstar-sourced FTSE 100 ETF total-return
series are proprietary and are NOT redistributed in this repository. This script
re-downloads them from their public endpoints so that the full pipeline can be
reproduced locally. Everything else in data/raw/ is Open Government Licence data
and is committed.

Writes:
  data/raw/financial/msci_acwi_netr_gbp.csv     (Date, Level)
  data/raw/financial/msci_acwi_grtr_gbp.csv     (Date, Level)
  data/raw/financial/ftse100_tr_monthly.csv     (Date, Level)

Then run:  python code/prep_uk_data_v2.py

Notes
-----
* Endpoints occasionally change or rate-limit. If a download fails, the error
  message names the source page from which the series can be exported manually;
  save the file with the same columns and the pipeline will pick it up.
* These are public chart-data endpoints intended for interactive use. Please be
  considerate: this script fetches each series once.
"""
import io
import os
import sys
import json
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "data", "raw", "financial")
os.makedirs(OUT, exist_ok=True)

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
START, END = "20041201", "20260709"


def get(url, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except Exception as e:                      # noqa: BLE001
            if i == tries - 1:
                raise
            print(f"    retry {i+1}/{tries-1} after error: {e}")
            time.sleep(5)


def write_csv(path, rows):
    with io.open(path, "w", encoding="utf-8", newline="") as f:
        f.write("Date,Level\n")
        for d, v in rows:
            f.write(f"{d},{v}\n")
    print(f"    wrote {os.path.basename(path)}: {len(rows)} rows "
          f"({rows[0][0]} .. {rows[-1][0]})")


def fetch_msci(variant, fname):
    """MSCI ACWI (index code 892400) end-of-month levels, GBP.

    Manual fallback: https://www.msci.com/end-of-day-data-search
    (select ACWI, currency GBP, frequency monthly, the chosen variant).
    """
    url = ("https://app2.msci.com/products/service/index/indexmaster/"
           f"getLevelDataForGraph?currency_symbol=GBP&index_variant={variant}"
           f"&start_date={START}&end_date={END}"
           "&data_frequency=END_OF_MONTH&index_codes=892400")
    print(f"  MSCI ACWI {variant} (GBP) ...")
    payload = json.loads(get(url).decode("utf-8"))
    series = payload["indexes"]["INDEX_LEVELS"]
    rows = [(str(p["calc_date"])[:4] + "-" + str(p["calc_date"])[4:6] + "-"
             + str(p["calc_date"])[6:8], repr(p["level_eod"])) for p in series]
    write_csv(os.path.join(OUT, fname), rows)


def fetch_ftse():
    """iShares Core FTSE 100 UCITS ETF (ISF, IE0005042456) NAV total return, GBP.

    Morningstar UK public chart-data API ("growth of 10,000", monthly). This is a
    net-of-fee ETF proxy for the FTSE 100 total-return index; see the paper's
    data appendix. Manual fallback:
    https://www.morningstar.co.uk/uk/etf/snapshot/snapshot.aspx?id=0P0000M7GC
    """
    url = ("https://tools.morningstar.co.uk/api/rest.svc/timeseries_growth/"
           "t92wz0sj7c?currencyId=GBP&idtype=isin&frequency=monthly"
           "&startDate=2004-11-30&endDate=2026-07-09"
           "&outputType=COMPACTJSON&id=IE0005042456")
    print("  FTSE 100 ETF total return (GBP) ...")
    payload = json.loads(get(url).decode("utf-8"))
    import datetime as dt
    rows = [(dt.datetime.utcfromtimestamp(ms / 1000).strftime("%Y-%m-%d"), repr(v))
            for ms, v in payload]
    write_csv(os.path.join(OUT, "ftse100_tr_monthly.csv"), rows)


def main():
    print("Fetching licence-restricted financial series (not redistributed in this repo)")
    ok = True
    for fn, args in [(fetch_msci, ("NETR", "msci_acwi_netr_gbp.csv")),
                     (fetch_msci, ("GRTR", "msci_acwi_grtr_gbp.csv")),
                     (fetch_ftse, ())]:
        try:
            fn(*args)
        except Exception as e:                      # noqa: BLE001
            ok = False
            print(f"  FAILED: {e}\n  -> see the docstring above for a manual export route.")
    print("\nDone." if ok else "\nCompleted with errors; see messages above.")
    print("Next: python code/prep_uk_data_v2.py")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
