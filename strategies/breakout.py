"""唐奇安通道突破：收盤創 entry 日新高進場，跌破 exit 日低點出場（順勢）。"""
from __future__ import annotations
import pandas as pd
from .base import Strategy
from .util import build_position


class Breakout(Strategy):
    name = "breakout"
    PARAM_GRID = {"entry": [20, 40, 55], "exit": [10, 20]}

    def __init__(self, entry: int = 20, exit: int = 10):
        self.entry = entry
        self.exit_lb = exit

    def positions(self, df: pd.DataFrame) -> pd.Series:
        hi = df["close"].rolling(self.entry).max()
        lo = df["close"].rolling(self.exit_lb).min()
        entry = df["close"] >= hi
        exit = df["close"] <= lo
        return build_position(entry.fillna(False), exit.fillna(False))

    def explain(self, df: pd.DataFrame, history: int = 10) -> dict:
        """最新一日的訊號與判斷依據（數值未四捨五入），供匯出給 AI 解釋。

        action 與 alert.py 分類一致：buy（今持有、昨空手）、sell（今空手、昨持有）、
        hold（連兩日持有）、flat（連兩日空手）。
        """
        close = df["close"]
        pos = self.positions(df)
        hi = close.rolling(self.entry).max()
        lo = close.rolling(self.exit_lb).min()
        now = float(pos.iloc[-1])
        prev = float(pos.iloc[-2]) if len(pos) > 1 else 0.0
        action = {(1, 0): "buy", (0, 1): "sell", (1, 1): "hold"}.get((int(now > 0), int(prev > 0)), "flat")

        since = entry_close = None
        holding_days = 0
        if now > 0:
            # 往回找本段持有的進場日
            i = len(pos) - 1
            while i > 0 and pos.iloc[i - 1] > 0:
                i -= 1
            since = str(pos.index[i].date())
            entry_close = float(close.iloc[i])
            holding_days = len(pos) - i

        px = float(close.iloc[-1])
        entry_level, exit_level = float(hi.iloc[-1]), float(lo.iloc[-1])
        return {
            "params": {"entry": self.entry, "exit": self.exit_lb},
            "action": action,
            "position": now,
            "prev_position": prev,
            "close": px,
            "entry_level": entry_level,          # 近 entry 日最高收盤（含當日）
            "exit_level": exit_level,            # 近 exit 日最低收盤（含當日）
            "pct_above_exit_level": px / exit_level - 1 if exit_level else None,
            "pct_below_entry_level": px / entry_level - 1 if entry_level else None,
            "since": since,
            "entry_close": entry_close,
            "return_since_entry": px / entry_close - 1 if entry_close else None,
            "holding_days": holding_days,
            "history": [
                {"date": str(d.date()), "position": float(p), "close": float(c)}
                for d, p, c in zip(pos.index[-history:], pos.iloc[-history:], close.iloc[-history:])
            ],
        }
