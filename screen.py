"""穩健策略篩選：對一籃子股票 × 各策略跑 walk-forward，依「樣本外」表現排名。
找的是『多檔都穩、不是靠單一標的僥倖』的策略。

範例：
    python screen.py --start 2019-01-01
    python screen.py --tickers 2330,2454,3711 --strategies trend_chip,foreign_streak
"""
from __future__ import annotations
import argparse
import numpy as np
import pandas as pd

from data.finmind import load
from strategies import REGISTRY
from backtest.metrics import compute
from walkforward import walk_forward
from run import load_env

DEFAULT_BASKET = ["2330", "2454", "3711", "3661", "3034", "2379"]


def main():
    load_env()
    ap = argparse.ArgumentParser(description="穩健策略篩選（跨標的 walk-forward）")
    ap.add_argument("--tickers", default=",".join(DEFAULT_BASKET))
    ap.add_argument("--strategies", default="")
    ap.add_argument("--start", default="2019-01-01")
    ap.add_argument("--end", default=None)
    ap.add_argument("--train", type=int, default=252)
    ap.add_argument("--test", type=int, default=63)
    args = ap.parse_args()

    tickers = [t.strip() for t in args.tickers.split(",") if t.strip()]
    strategies = [s.strip() for s in args.strategies.split(",") if s.strip()] or list(REGISTRY)

    cache: dict[str, pd.DataFrame] = {}

    def get(t):
        if t not in cache:
            cache[t] = load(t, args.start, args.end)
        return cache[t]

    print(f"篩選 {len(strategies)} 策略 × {len(tickers)} 檔（walk-forward 訓練{args.train}/測試{args.test}）...\n")
    rows = []
    for strat in strategies:
        StratCls = REGISTRY[strat]
        sharpes, rets = [], []
        for t in tickers:
            try:
                df = get(t)
                if len(df) < args.train + args.test + 10:
                    continue
                bt, _ = walk_forward(df, StratCls, args.train, args.test)
                m = compute(bt)
                sharpes.append(m["sharpe"])
                rets.append(m["total_return"])
            except Exception:
                continue
        if sharpes:
            rows.append({
                "策略": strat,
                "平均OOS_Sharpe": round(float(np.mean(sharpes)), 2),
                "中位OOS報酬%": round(float(np.median(rets)) * 100, 1),
                "正報酬比例": f"{np.mean([r > 0 for r in rets]) * 100:.0f}%",
                "檔數": len(sharpes),
            })

    out = pd.DataFrame(rows).sort_values("平均OOS_Sharpe", ascending=False)
    print(out.to_string(index=False))
    print("\n判讀：平均 OOS Sharpe 高、正報酬比例高（多檔都賺）＝較穩健，值得再深入。")


if __name__ == "__main__":
    main()
