"""每日紙上模擬（forward paper trading）。

維護一個紙上投組（現金＋持倉）於 paper_state.json，每次執行把「昨日訊號」
在最新收盤等權再平衡、計入台股成本，累積真實的前進式績效紀錄。可排程每日跑。

範例：
    python paper.py --strategy breakout --capital 1000000 --start 2024-01-01 --reset
    python paper.py --strategy breakout        # 之後每日執行，往前推進
"""
from __future__ import annotations
import argparse
import json
import pathlib

import pandas as pd

from data.finmind import load
from strategies import REGISTRY
from run import load_env

FEE = 0.001425
TAX = 0.003
SLIP = 0.001
STATE_FILE = pathlib.Path(__file__).parent / "paper_state.json"


class PaperPortfolio:
    def __init__(self, cash: float):
        self.cash = float(cash)
        self.positions: dict[str, float] = {}  # ticker -> 股數（紙上允許分數）

    def nav(self, prices: dict[str, float]) -> float:
        return self.cash + sum(sh * prices.get(t, 0.0) for t, sh in self.positions.items())

    def rebalance(self, weights: dict[str, float], prices: dict[str, float]):
        nav = self.nav(prices)
        # 先賣（釋放現金），再買
        for t in list(self.positions):
            px = prices.get(t)
            if not px:
                continue
            target = weights.get(t, 0.0) * nav
            cur = self.positions[t] * px
            if target < cur:
                sell_val = cur - target
                self.cash += sell_val * (1 - FEE - TAX - SLIP)
                self.positions[t] -= sell_val / px
                if self.positions[t] < 1e-6:
                    del self.positions[t]
        for t, w in weights.items():
            px = prices.get(t)
            if not px or w <= 0:
                continue
            target = w * nav
            cur = self.positions.get(t, 0.0) * px
            if target > cur:
                buy_val = min(target - cur, self.cash / (1 + FEE + SLIP))
                if buy_val <= 0:
                    continue
                self.cash -= buy_val * (1 + FEE + SLIP)
                self.positions[t] = self.positions.get(t, 0.0) + buy_val / px


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return None


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2))


def main():
    load_env()
    ap = argparse.ArgumentParser(description="每日紙上模擬")
    ap.add_argument("--strategy", default="breakout", choices=list(REGISTRY))
    ap.add_argument("--tickers", default="2330,2454,3711,3661,3034,2379")
    ap.add_argument("--capital", type=float, default=1_000_000)
    ap.add_argument("--start", default="2024-01-01")
    ap.add_argument("--reset", action="store_true", help="清空重來")
    ap.add_argument("--max-weight", type=float, default=0.34, help="單一標的上限權重")
    args = ap.parse_args()

    tickers = [t.strip() for t in args.tickers.split(",") if t.strip()]
    StratCls = REGISTRY[args.strategy]

    # 載入資料與（含暖身的）訊號
    data = {}
    signals = {}
    for t in tickers:
        try:
            df = load(t, args.start, None)
            data[t] = df
            signals[t] = StratCls().positions(df)
        except Exception as e:
            print(f"  略過 {t}：{e}")
    if not data:
        print("無可用資料")
        return

    all_dates = sorted(set().union(*[df.index for df in data.values()]))

    state = None if args.reset else load_state()
    if state is None:
        state = {"strategy": args.strategy, "cash": args.capital, "positions": {},
                 "nav_history": [], "last_date": None}
    port = PaperPortfolio(state["cash"])
    port.positions = {k: float(v) for k, v in state["positions"].items()}
    last_date = state["last_date"]

    # 處理所有「比 last_date 新」的交易日
    todo = [d for d in all_dates if last_date is None or str(d.date()) > last_date]
    if not todo:
        print("已是最新，無新交易日可推進。")
        _print_status(port, data, all_dates[-1])
        return

    for d in todo:
        prev = _prev_date(all_dates, d)
        if prev is None:
            continue
        # 昨日訊號 → 今日收盤執行（避免同棒未來函數）
        signaled = [t for t in tickers if t in signals and prev in signals[t].index and signals[t].loc[prev] > 0
                    and d in data[t].index]
        if signaled:
            w = min(args.max_weight, 1.0 / len(signaled))
            weights = {t: w for t in signaled}
        else:
            weights = {}
        prices = {t: float(data[t].loc[d, "close"]) for t in tickers if d in data[t].index}
        port.rebalance(weights, prices)
        nav = port.nav(prices)
        state["nav_history"].append({"date": str(d.date()), "nav": round(nav, 0)})

    state["cash"] = port.cash
    state["positions"] = port.positions
    state["last_date"] = str(todo[-1].date())
    save_state(state)

    _print_status(port, data, todo[-1], state, args.capital)


def _prev_date(all_dates, d):
    i = all_dates.index(d)
    return all_dates[i - 1] if i > 0 else None


def _print_status(port, data, d, state=None, capital=None):
    prices = {t: float(data[t].loc[d, "close"]) for t in data if d in data[t].index}
    nav = port.nav(prices)
    print(f"\n── 紙上投組 @ {d.date()} ──")
    print(f"  現金 {port.cash:,.0f}｜總值 NAV {nav:,.0f}")
    if capital:
        print(f"  累積報酬 {(nav / capital - 1) * 100:+.2f}%")
    if port.positions:
        print("  持倉：")
        for t, sh in port.positions.items():
            px = prices.get(t, 0)
            print(f"    {t}  {sh:,.0f} 股  市值 {sh*px:,.0f}")
    else:
        print("  持倉：空手")
    if state and len(state["nav_history"]) > 1:
        navs = [h["nav"] for h in state["nav_history"]]
        peak = navs[0]
        mdd = 0.0
        for v in navs:
            peak = max(peak, v)
            mdd = min(mdd, v / peak - 1)
        print(f"  紀錄天數 {len(navs)}｜期間最大回撤 {mdd*100:.1f}%")
    print("\n⚠️ 紙上模擬，不涉及真實下單。可每日排程執行以累積前進式績效。")


if __name__ == "__main__":
    main()
