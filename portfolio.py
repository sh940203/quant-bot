"""多標的等權組合回測：同一策略跑一籃子股票，等權合併每日報酬。

範例：
    python portfolio.py --strategy foreign_streak --start 2021-01-01
    python portfolio.py --strategy momentum --tickers 2330,2454,3711 --start 2020-01-01
"""
from __future__ import annotations
import argparse
import pandas as pd

from data.finmind import load
from strategies import REGISTRY
from backtest.engine import run_backtest
from backtest.metrics import compute, format_report
from run import load_env

# 預設半導體籃子
DEFAULT_BASKET = ["2330", "2454", "3711", "3661", "3034", "2379", "3037", "6446"]


def main():
    load_env()
    ap = argparse.ArgumentParser(description="多標的等權組合回測")
    ap.add_argument("--strategy", default="foreign_streak", choices=list(REGISTRY))
    ap.add_argument("--tickers", default=",".join(DEFAULT_BASKET))
    ap.add_argument("--start", default="2021-01-01")
    ap.add_argument("--end", default=None)
    args = ap.parse_args()

    tickers = [t.strip() for t in args.tickers.split(",") if t.strip()]
    StratCls = REGISTRY[args.strategy]

    cols = {"ret": [], "gross": [], "held": [], "benchmark_ret": []}
    used = []
    for t in tickers:
        try:
            df = load(t, args.start, args.end)
            bt = run_backtest(df, StratCls().positions(df))
            for c in cols:
                cols[c].append(bt[c].rename(t))
            used.append(t)
        except Exception as e:
            print(f"  略過 {t}：{e}")

    if not used:
        print("沒有可用標的")
        return

    ret = pd.concat(cols["ret"], axis=1).fillna(0.0).mean(axis=1)
    gross = pd.concat(cols["gross"], axis=1).fillna(0.0).mean(axis=1)
    held = pd.concat(cols["held"], axis=1).fillna(0.0).mean(axis=1)
    bret = pd.concat(cols["benchmark_ret"], axis=1).fillna(0.0).mean(axis=1)

    port = pd.DataFrame(
        {"ret": ret, "gross": gross, "held": held,
         "equity": (1 + ret).cumprod(), "benchmark": (1 + bret).cumprod()}
    )

    print(f"\n組合回測｜策略 {args.strategy}｜{len(used)} 檔等權：{', '.join(used)}")
    print(f"期間 {port.index[0].date()} ~ {port.index[-1].date()}\n")
    print(format_report(f"等權組合（{len(used)}檔）", compute(port)))
    print("\n⚠️ 等權每日再平衡為簡化假設，未計入實際換股成本與資金限制。")


if __name__ == "__main__":
    main()
