"""Walk-forward 滾動最佳化：每段用「前 train 日」訓練選參，套到「後 test 日」，
一段段往前滾，串成完整的『樣本外』權益曲線——最接近實戰的驗證方式。

範例：
    python walkforward.py --ticker 2330 --strategy momentum --start 2019-01-01
    python walkforward.py --ticker 3711 --strategy foreign_streak --train 252 --test 63
"""
from __future__ import annotations
import argparse
import pandas as pd

from data.finmind import load
from strategies import REGISTRY
from backtest.engine import run_backtest
from backtest.metrics import compute, format_report
from run import load_env
from sweep import combos


def walk_forward(df: pd.DataFrame, StratCls, train: int, test: int):
    oos = pd.Series(0.0, index=df.index)
    picks = []
    i = train
    while i + test <= len(df):
        train_df = df.iloc[i - train : i]
        best, best_s = None, -1e18
        for params in combos(StratCls):
            m = compute(run_backtest(train_df, StratCls(**params).positions(train_df)))
            if m["sharpe"] > best_s:
                best_s, best = m["sharpe"], params
        # 用含暖身的完整歷史算部位，再取本測試段（rolling 指標不會用到未來）
        pos_full = StratCls(**best).positions(df.iloc[: i + test])
        idx = df.index[i : i + test]
        oos.loc[idx] = pos_full.loc[idx].values
        picks.append((df.index[i].date(), best))
        i += test

    bt = run_backtest(df, oos).iloc[train:]  # 只看實際滾動的樣本外期間
    return bt, picks


def main():
    load_env()
    ap = argparse.ArgumentParser(description="Walk-forward 滾動最佳化")
    ap.add_argument("--ticker", default="2330")
    ap.add_argument("--strategy", default="momentum", choices=list(REGISTRY))
    ap.add_argument("--start", default="2019-01-01")
    ap.add_argument("--end", default=None)
    ap.add_argument("--train", type=int, default=252, help="訓練窗（交易日，約 1 年）")
    ap.add_argument("--test", type=int, default=63, help="測試窗（交易日，約 1 季）")
    args = ap.parse_args()

    df = load(args.ticker, args.start, args.end)
    if len(df) < args.train + args.test + 10:
        print("資料期間太短，請拉長 --start 或縮小 --train/--test")
        return

    bt, picks = walk_forward(df, REGISTRY[args.strategy], args.train, args.test)

    print(f"\nWalk-forward｜{args.strategy} @ {args.ticker}｜訓練 {args.train} / 測試 {args.test} 日"
          f"｜共 {len(picks)} 段滾動\n")
    print(format_report(f"滾動樣本外（{bt.index[0].date()} ~ {bt.index[-1].date()}）", compute(bt)))

    print("\n每段選到的參數（看穩不穩定）：")
    for d, p in picks:
        print("  " + str(d) + "  " + ", ".join(f"{k}={v}" for k, v in p.items()))

    print("\n判讀：滾動樣本外若能穩定為正、參數不亂跳，才比較可能在實盤存活。")


if __name__ == "__main__":
    main()
