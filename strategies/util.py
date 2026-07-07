"""策略共用工具。"""
from __future__ import annotations
import numpy as np
import pandas as pd


def build_position(entry: pd.Series, exit: pd.Series) -> pd.Series:
    """進出不對稱時，用狀態機建部位：entry 為真進場、exit 為真出場，其餘持有。"""
    pos = np.zeros(len(entry))
    holding = False
    e = entry.to_numpy()
    x = exit.to_numpy()
    for i in range(len(entry)):
        if holding:
            if x[i]:
                holding = False
        elif e[i]:
            holding = True
        pos[i] = 1.0 if holding else 0.0
    return pd.Series(pos, index=entry.index)


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(50.0)
