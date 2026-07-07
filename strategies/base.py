"""策略介面。positions() 回傳每日目標部位（1=做多、0=空手），
使用「當日收盤前可得資訊」計算；回測引擎會延後一日執行以避免未來函數。"""
from __future__ import annotations
from abc import ABC, abstractmethod
import pandas as pd


class Strategy(ABC):
    name: str = "base"

    @abstractmethod
    def positions(self, df: pd.DataFrame) -> pd.Series:
        ...
