"""均線交叉 + 籌碼過濾：短均線 > 長均線，且外資近 N 日淨買超為正才做多。"""
from __future__ import annotations
import pandas as pd
from .base import Strategy


class MACrossInstitutional(Strategy):
    name = "ma_cross"
    PARAM_GRID = {"short": [5, 10, 20], "long": [20, 40, 60], "inst_window": [3, 5, 10]}

    def __init__(self, short: int = 5, long: int = 20, inst_window: int = 5):
        self.short = short
        self.long = long
        self.inst_window = inst_window

    def positions(self, df: pd.DataFrame) -> pd.Series:
        sma_s = df["close"].rolling(self.short).mean()
        sma_l = df["close"].rolling(self.long).mean()
        foreign_flow = df["foreign"].rolling(self.inst_window).sum()
        long_cond = (sma_s > sma_l) & (foreign_flow > 0)
        return long_cond.astype(float).fillna(0.0)
