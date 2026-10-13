"""用合成資料測評分明細、breakout 判斷依據與匯出 schema（不連網）。"""
import json

import numpy as np
import pandas as pd
import pytest

from discover import score, score_detail
from strategies.breakout import Breakout
from export_signals import build_ticker, build_summary, clean


def make_df(closes, foreign=0.0):
    idx = pd.bdate_range("2025-01-01", periods=len(closes))
    df = pd.DataFrame({"close": closes}, index=idx, dtype=float)
    for c in ["open", "high", "low"]:
        df[c] = df["close"]
    df["volume"] = 1_000_000.0
    df["foreign"] = foreign
    df["trust"] = 0.0
    df["dealer"] = 0.0
    df["total"] = df["foreign"]
    return df


def low_and_turning(final_close):
    """剛好 252 日、區間 100~200，最後 30 日從 100 緩升到 final_close（站上且翻揚的 20MA）。"""
    base = list(np.linspace(200, 100, 222))
    tail = list(np.linspace(100, final_close, 30))
    return base + tail


def test_score_detail_full_marks_and_raw_pctile():
    # 位階 = (134.6-100)/(200-100) = 0.346 → 顯示會是 34.6%，仍 <35% 拿 2 分
    df = make_df(low_and_turning(134.6), foreign=10.0)
    d = score_detail(df)
    assert d["eligible"] and d["score"] == 6
    assert d["pctile"] == pytest.approx(0.346)
    assert sum(b["points"] for b in d["breakdown"]) == d["score"]
    assert [b["key"] for b in d["breakdown"]] == ["position", "foreign_flow", "stop_falling"]
    s = score(df)
    assert s["score"] == 6 and s["pctile"] == 34.6
    assert s["reasons"][0] == "位階低（一年區間34.6%）"


def test_score_detail_mid_position_and_foreign_selling():
    df = make_df(low_and_turning(140.0), foreign=-5.0)
    d = score_detail(df)
    pts = {b["key"]: b["points"] for b in d["breakdown"]}
    assert pts == {"position": 1, "foreign_flow": 0, "stop_falling": 2}
    assert d["score"] == 3
    assert score(df)["reasons"] == ["位階偏低（40.0%）", "站上20MA且均線翻揚(止跌)"]


def test_score_detail_excluded_keeps_breakdown():
    df = make_df(low_and_turning(180.0), foreign=10.0)
    d = score_detail(df)
    assert not d["eligible"] and d["score"] is None
    assert "未低於門檻" in d["excluded_reason"]
    assert d["breakdown"][1]["points"] == 2  # 其他條件仍有明細，AI 可解釋
    assert score(df) is None


def test_lookback_uses_last_252_days():
    # 很久以前的高點 1000 不應影響位階
    closes = [1000.0] * 50 + low_and_turning(134.6)
    assert score_detail(make_df(closes))["pctile"] == pytest.approx(0.346)


def test_too_short_returns_none():
    assert score_detail(make_df([100.0] * 100)) is None


def test_breakout_explain_hold_and_sell():
    closes = list(np.linspace(100, 150, 60))  # 持續創高 → 進場並續抱
    e = Breakout().explain(make_df(closes))
    assert e["action"] == "hold"
    assert e["entry_level"] == pytest.approx(150)
    assert e["since"] is not None and e["holding_days"] > 1
    assert len(e["history"]) == 10

    e2 = Breakout().explain(make_df(closes + [120.0]))  # 跌破 10 日低 → 出場
    assert e2["action"] == "sell" and e2["since"] is None


def test_export_schema_is_strict_json():
    df = make_df(low_and_turning(134.6), foreign=10.0)
    t = build_ticker("3035", df, in_breakout=True, in_discover=True, max_pctile=0.5, history=5)
    assert t["name"] == "智原"
    assert len(t["discover"]["history"]) == 5
    json.dumps(clean(t), allow_nan=False)  # 不可含 NaN

    s = build_summary({"3035": t}, t["as_of"], [], min_score=3, max_pctile=0.5, top=10)
    assert s["schema_version"] == 1
    assert s["discover"]["ranked"][0]["code"] == "3035"
    assert s["discover"]["ranked"][0]["pctile"] == pytest.approx(0.346)
    json.dumps(clean(s), allow_nan=False)


def test_summary_recent_changes():
    closes = list(np.linspace(100, 150, 60)) + [120.0]   # 最後一天跌破 10 日低 → 出場
    t = build_ticker("2330", make_df(closes), in_breakout=True, in_discover=False, max_pctile=0.5, history=5)
    s = build_summary({"2330": t}, t["as_of"], [], min_score=3, max_pctile=0.5, top=10)
    ch = s["breakout"]["recent_changes"]
    assert ch == [{"date": t["as_of"], "code": "2330", "name": "台積電", "event": "出場", "close": 120.0}]
    assert s["discover"]["ranked_history"] == []
