"""複合確認：籌碼 × 技術雙確認，減少假訊號。

進場需同時成立：
  1. 趨勢：短均線 > 長均線
  2. 籌碼：外資近 flow_window 日淨買超為正
  3. 不追高：RSI < rsi_max
出場：趨勢翻空（短均線 < 長均線）或 外資近 flow_window 日轉為淨賣超。
"""
from __future__ import annotations
import pandas as pd
from .base import Strategy
from .util import rsi, build_position


class TrendChip(Strategy):
    name = "trend_chip"
    PARAM_GRID = {
        "short": [5, 10, 20],
        "long": [20, 40, 60],
        "flow_window": [3, 5, 10],
        "rsi_max": [70, 80],
    }

    def __init__(self, short: int = 10, long: int = 40, flow_window: int = 5, rsi_max: int = 75):
        self.short = short
        self.long = long
        self.flow_window = flow_window
        self.rsi_max = rsi_max

    def positions(self, df: pd.DataFrame) -> pd.Series:
        sma_s = df["close"].rolling(self.short).mean()
        sma_l = df["close"].rolling(self.long).mean()
        flow = df["foreign"].rolling(self.flow_window).sum()
        r = rsi(df["close"], 14)

        entry = (sma_s > sma_l) & (flow > 0) & (r < self.rsi_max)
        exit = (sma_s < sma_l) | (flow < 0)
        return build_position(entry.fillna(False), exit.fillna(False))
