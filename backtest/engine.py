"""回測引擎（含台股交易成本，延後一日執行避免未來函數）。"""
from __future__ import annotations
import numpy as np
import pandas as pd

# 台股成本：手續費 0.1425%（買/賣各一次），證交稅 0.3%（賣出）
FEE = 0.001425
TAX = 0.003


def _finish(df: pd.DataFrame, held: pd.Series, slippage: float) -> pd.DataFrame:
    """由每日有效部位 held 算出報酬、成本、權益（held 已延後一日、無未來函數）。"""
    ret = df["close"].pct_change().fillna(0.0)
    gross = held * ret
    change = held.diff().fillna(held)
    buys = change.clip(lower=0)
    sells = (-change).clip(lower=0)
    cost = buys * (FEE + slippage) + sells * (FEE + TAX + slippage)
    net = gross - cost
    return pd.DataFrame(
        {"ret": net, "gross": gross, "cost": cost, "equity": (1 + net).cumprod(),
         "held": held, "benchmark_ret": ret, "benchmark": (1 + ret).cumprod()},
        index=df.index,
    )


def run_backtest(df: pd.DataFrame, positions: pd.Series, slippage: float = 0.001) -> pd.DataFrame:
    """向量化回測（全有全無、無停損），供掃描/組合快速使用。"""
    pos = positions.reindex(df.index).fillna(0.0).clip(0, 1)
    held = pos.shift(1).fillna(0.0)  # 昨日決定，今日實現
    return _finish(df, held, slippage)


def run_backtest_risk(
    df: pd.DataFrame,
    positions: pd.Series,
    stop_loss: float | None = 0.08,
    take_profit: float | None = None,
    risk_per_trade: float | None = None,
    slippage: float = 0.001,
) -> pd.DataFrame:
    """有狀態回測：策略進出訊號 + 停損/停利 + 部位控管（路徑相依，逐日模擬）。

    - stop_loss / take_profit：距進場價的百分比（如 0.08 = 8%）。觸價當日出場。
    - risk_per_trade：每筆風險預算（如 0.02），配合 stop_loss 決定部位大小
      size = min(1, risk_per_trade / stop_loss)；未設定則進場即滿倉。
    """
    close = df["close"].to_numpy()
    tgt = positions.reindex(df.index).fillna(0.0).clip(0, 1).to_numpy()
    n = len(df)
    held = np.zeros(n)
    size = 0.0
    entry = None

    for i in range(n):
        held[i] = size  # 由昨日收盤決定，實現今日報酬
        px = close[i]
        # ── 當日收盤後決策（影響明日 held）──
        if size > 0 and entry is not None:
            if stop_loss and px <= entry * (1 - stop_loss):
                size, entry = 0.0, None
            elif take_profit and px >= entry * (1 + take_profit):
                size, entry = 0.0, None
        want = tgt[i]
        if size == 0 and want > 0:
            entry = px
            size = min(1.0, risk_per_trade / stop_loss) if (risk_per_trade and stop_loss) else 1.0
        elif size > 0 and want == 0:
            size, entry = 0.0, None

    return _finish(df, pd.Series(held, index=df.index), slippage)
