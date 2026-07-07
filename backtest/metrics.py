"""績效指標：總報酬、CAGR、Sharpe、最大回撤、勝率、曝險、交易次數。"""
from __future__ import annotations
import numpy as np
import pandas as pd

PPY = 252  # 每年交易日約數


def _trades(bt: pd.DataFrame) -> list[float]:
    """把連續持有切成一段段交易，回傳每段複利報酬。"""
    trades: list[float] = []
    acc = 1.0
    in_pos = False
    for h, g in zip(bt["held"], bt["gross"]):
        if h > 0:
            in_pos = True
            acc *= (1 + g)
        elif in_pos:
            trades.append(acc - 1)
            acc = 1.0
            in_pos = False
    if in_pos:
        trades.append(acc - 1)
    return trades


def compute(bt: pd.DataFrame) -> dict:
    ret = bt["ret"]
    equity = bt["equity"]
    n = len(ret)
    total = float(equity.iloc[-1] - 1) if n else 0.0
    cagr = float(equity.iloc[-1] ** (PPY / n) - 1) if n > 1 else 0.0
    vol = float(ret.std() * np.sqrt(PPY))
    sharpe = float(ret.mean() * PPY / vol) if vol > 0 else 0.0
    dd = equity / equity.cummax() - 1
    mdd = float(dd.min())
    exposure = float(bt["held"].mean())
    trades = _trades(bt)
    win_rate = float(np.mean([t > 0 for t in trades])) if trades else 0.0
    bench_total = float(bt["benchmark"].iloc[-1] - 1) if n else 0.0
    return {
        "total_return": total,
        "cagr": cagr,
        "sharpe": sharpe,
        "max_drawdown": mdd,
        "win_rate": win_rate,
        "num_trades": len(trades),
        "exposure": exposure,
        "buy_hold_return": bench_total,
    }


def format_report(title: str, m: dict) -> str:
    pct = lambda x: f"{x * 100:+.2f}%"
    return (
        f"── {title} ──\n"
        f"  總報酬      {pct(m['total_return'])}   （買進持有 {pct(m['buy_hold_return'])}）\n"
        f"  年化 CAGR   {pct(m['cagr'])}\n"
        f"  Sharpe      {m['sharpe']:.2f}\n"
        f"  最大回撤    {pct(m['max_drawdown'])}\n"
        f"  勝率        {m['win_rate'] * 100:.1f}%   交易 {m['num_trades']} 次\n"
        f"  持倉曝險    {m['exposure'] * 100:.1f}%"
    )
