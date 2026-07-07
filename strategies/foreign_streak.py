"""純籌碼：外資連續 streak 日淨買超進場，連續 exit_streak 日淨賣超出場。"""
from __future__ import annotations
import pandas as pd
from .base import Strategy
from .util import build_position


def _streak_up(s: pd.Series, n: int) -> pd.Series:
    up = (s > 0).astype(int)
    return up.rolling(n).sum() >= n


def _streak_down(s: pd.Series, n: int) -> pd.Series:
    dn = (s < 0).astype(int)
    return dn.rolling(n).sum() >= n


class ForeignStreak(Strategy):
    name = "foreign_streak"
    PARAM_GRID = {"streak": [2, 3, 5], "exit_streak": [2, 3]}

    def __init__(self, streak: int = 3, exit_streak: int = 2):
        self.streak = streak
        self.exit_streak = exit_streak

    def positions(self, df: pd.DataFrame) -> pd.Series:
        entry = _streak_up(df["foreign"], self.streak)
        exit = _streak_down(df["foreign"], self.exit_streak)
        return build_position(entry.fillna(False), exit.fillna(False))
