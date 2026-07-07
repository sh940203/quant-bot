"""參數掃描：在「樣本內」挑最佳參數，回報其「樣本外」表現（避免偷看未來）。

範例：
    python sweep.py --ticker 2330 --strategy momentum --start 2020-01-01 --split 0.6
"""
from __future__ import annotations
import argparse
import itertools

from data.finmind import load
from strategies import REGISTRY
from backtest.engine import run_backtest
from backtest.metrics import compute
from run import load_env


def combos(StratCls):
    grid = getattr(StratCls, "PARAM_GRID", {})
    keys = list(grid)
    if not keys:
        return [{}]
    return [dict(zip(keys, vals)) for vals in itertools.product(*[grid[k] for k in keys])]


def main():
    load_env()
    ap = argparse.ArgumentParser(description="參數掃描（訓練內選參、測試外驗證）")
    ap.add_argument("--ticker", default="2330")
    ap.add_argument("--strategy", default="momentum", choices=list(REGISTRY))
    ap.add_argument("--start", default="2020-01-01")
    ap.add_argument("--end", default=None)
    ap.add_argument("--split", type=float, default=0.6)
    ap.add_argument("--top", type=int, default=6)
    args = ap.parse_args()

    df = load(args.ticker, args.start, args.end)
    StratCls = REGISTRY[args.strategy]
    k = int(len(df) * args.split)
    df_in, df_out = df.iloc[:k], df.iloc[k:]

    rows = []
    for params in combos(StratCls):
        strat = StratCls(**params)
        m_in = compute(run_backtest(df_in, strat.positions(df_in)))
        m_out = compute(run_backtest(df_out, strat.positions(df_out)))
        rows.append((params, m_in, m_out))

    # 只用樣本內 Sharpe 排名選參（不偷看樣本外）
    rows.sort(key=lambda r: r[1]["sharpe"], reverse=True)

    print(f"\n{args.strategy} @ {args.ticker}｜{df.index[0].date()}~{df.index[-1].date()}"
          f"｜訓練 {len(df_in)} / 測試 {len(df_out)} 日｜共 {len(rows)} 組參數\n")
    print(f"{'參數':<40}{'訓練Sharpe':>10}{'訓練報酬':>10}{'測試Sharpe':>12}{'測試報酬':>10}")
    print("-" * 82)
    for params, m_in, m_out in rows[: args.top]:
        p = ",".join(f"{k}={v}" for k, v in params.items())
        print(f"{p:<40}{m_in['sharpe']:>10.2f}{m_in['total_return']*100:>9.1f}%"
              f"{m_out['sharpe']:>12.2f}{m_out['total_return']*100:>9.1f}%")

    best = rows[0]
    bh = compute(run_backtest(df_out, StratCls(**best[0]).positions(df_out)))["buy_hold_return"]
    print("-" * 82)
    print(f"★ 訓練最佳參數的『樣本外』表現：Sharpe {best[2]['sharpe']:.2f}、"
          f"報酬 {best[2]['total_return']*100:+.1f}%（同期買進持有 {bh*100:+.1f}%）")
    print("\n判讀：訓練漂亮但測試崩壞＝過度擬合；訓練/測試都穩才有參考價值。")


if __name__ == "__main__":
    main()
