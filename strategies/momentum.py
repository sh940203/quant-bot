"""動能：過去 N 日報酬為正且接近 N 日高點才做多；跌破退出。"""
from __future__ import annotations
import pandas as pd
from .base import Strategy


class Momentum(Strategy):
    name = "momentum"
    PARAM_GRID = {"lookback": [10, 20, 40, 60], "near_high": [0.95, 0.98, 1.0]}

    def __init__(self, lookback: int = 20, near_high: float = 0.98):
        self.lookback = lookback
        self.near_high = near_high

    def positions(self, df: pd.DataFrame) -> pd.Series:
        ret = df["close"].pct_change(self.lookback)
        high = df["close"].rolling(self.lookback).max()
        long_cond = (ret > 0) & (df["close"] >= high * self.near_high)
        return long_cond.astype(float).fillna(0.0)
