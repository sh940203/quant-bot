"""回測 CLI。

範例：
    python run.py --ticker 2330 --strategy ma_cross --start 2021-01-01
    python run.py --ticker 3481 --strategy momentum --start 2020-01-01 --split 0.7
"""
from __future__ import annotations
import argparse
import os
import pathlib

from data.finmind import load
from strategies import REGISTRY
from backtest.engine import run_backtest, run_backtest_risk
from backtest.metrics import compute, format_report


def load_env():
    """最小 .env 讀取（FINMIND_TOKEN）。"""
    p = pathlib.Path(__file__).parent / ".env"
    if p.exists():
        for line in p.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def main():
    load_env()
    ap = argparse.ArgumentParser(description="台股規則型策略回測（P0）")
    ap.add_argument("--ticker", default="2330")
    ap.add_argument("--strategy", default="ma_cross", choices=list(REGISTRY))
    ap.add_argument("--start", default="2021-01-01")
    ap.add_argument("--end", default=None)
    ap.add_argument("--split", type=float, default=0.7, help="樣本內比例（其餘為樣本外）")
    ap.add_argument("--stop", type=float, default=None, help="停損 %（如 0.08）")
    ap.add_argument("--take", type=float, default=None, help="停利 %（如 0.15）")
    ap.add_argument("--risk", type=float, default=None, help="每筆風險預算（如 0.02，配合 --stop 決定部位）")
    args = ap.parse_args()

    use_risk = args.stop is not None or args.take is not None or args.risk is not None

    def bt(d, p):
        if use_risk:
            return run_backtest_risk(d, p, stop_loss=args.stop, take_profit=args.take,
                                     risk_per_trade=args.risk)
        return run_backtest(d, p)

    print(f"載入 {args.ticker} 資料（{args.start} ~ {args.end or '最新'}）...")
    df = load(args.ticker, args.start, args.end)
    strat = REGISTRY[args.strategy]()
    pos = strat.positions(df)

    risk_note = ""
    if use_risk:
        risk_note = f"｜停損 {args.stop}、停利 {args.take}、風險 {args.risk}"
    print(f"\n策略：{strat.name}｜標的：{args.ticker}｜{df.index[0].date()} ~ {df.index[-1].date()}｜{len(df)} 交易日{risk_note}\n")

    # 全期
    print(format_report("全期", compute(bt(df, pos))))

    # 樣本內 / 樣本外（避免過度擬合的基本檢查）
    k = int(len(df) * args.split)
    if 20 < k < len(df) - 20:
        df_in, df_out = df.iloc[:k], df.iloc[k:]
        print()
        print(format_report(f"樣本內（前 {int(args.split*100)}%）", compute(bt(df_in, strat.positions(df_in)))))
        print()
        print(format_report("樣本外（後段，未參與調參）", compute(bt(df_out, strat.positions(df_out)))))

    print("\n⚠️ 回測績效不代表未來；未計入停損、資金配置與流動性衝擊。下一步應做紙上模擬驗證。")


if __name__ == "__main__":
    main()
