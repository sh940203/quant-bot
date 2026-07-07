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
