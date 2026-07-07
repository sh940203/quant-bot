"""RSI 均值回歸：RSI 跌破 buy 進場，回升到 exit 出場（逆勢承接）。"""
from __future__ import annotations
import pandas as pd
from .base import Strategy
from .util import rsi, build_position


class RsiReversion(Strategy):
    name = "rsi_reversion"
    PARAM_GRID = {"buy": [25, 30, 35], "exit": [50, 55, 60], "period": [7, 14]}

    def __init__(self, buy: int = 30, exit: int = 55, period: int = 14):
        self.buy = buy
        self.exit_level = exit
        self.period = period

    def positions(self, df: pd.DataFrame) -> pd.Series:
        r = rsi(df["close"], self.period)
        entry = r < self.buy
        exit = r > self.exit_level
        return build_position(entry, exit)
