"""發掘低價潛力股：掃描一籃子股票，篩出「位階低 + 籌碼進場 + 開始止跌」的標的。

判準（規則型、可解釋）：
  1. 位階低：現價在近一年（滾動 252 個交易日）收盤區間的低檔（低百分位）
  2. 籌碼進：外資近 20 日累計買超為正
  3. 止跌訊號：站上 20 日均線，且均線翻揚

範例：
    python discover.py                       # 掃預設宇宙、印出排名
    python discover.py --top 8 --line        # 推前 8 名到 LINE
    python discover.py --tickers 2344,2337,3006
"""
from __future__ import annotations
import argparse
import sys

from data.finmind import load
from run import load_env
from notify import send_line
from names import label

# 預設掃描宇宙（台股中大型科技/半導體，價位分布廣）
DEFAULT_UNIVERSE = [
    "2303", "2379", "3034", "3711", "3661", "3035", "3443", "6415", "2408", "2344",
    "2337", "4919", "5269", "3529", "3006", "3016", "8016", "3260", "6147", "4961",
    "3105", "2401", "6239", "3532", "2451", "2049", "1590", "3037", "3017", "6488",
]

LOOKBACK = 252  # 位階區間：滾動 252 個交易日（約一年）
MAX_SCORE = 6


def score_detail(df, max_pctile: float = 0.5):
    """完整評分明細（數值皆未四捨五入）。資料不足 120 日回傳 None。

    未達位階門檻（pctile >= max_pctile）的股票也會回傳明細，eligible=False、score=None，
    並附 excluded_reason，讓 AI 能解釋「為什麼沒上榜」。
    """
    close = df["close"].tail(LOOKBACK)
    if len(close) < 120:
        return None
    px = float(close.iloc[-1])
    lo, hi = float(close.min()), float(close.max())
    pctile = (px - lo) / (hi - lo) if hi > lo else 1.0
    sma20 = close.rolling(20).mean()
    sma20_now, sma20_prev = float(sma20.iloc[-1]), float(sma20.iloc[-6])
    above20 = px > sma20_now
    turning = sma20_now > sma20_prev
    foreign20 = float(df["foreign"].tail(20).sum())
    # 硬門檻：必須是「低價」（位階在一年區間低檔）才納入
    eligible = pctile < max_pctile

    if not eligible:
        pos_pts, pos_text = 0, f"位階{pctile*100:.1f}%，未低於門檻{max_pctile*100:.0f}%（不列入）"
    elif pctile < 0.35:
        pos_pts, pos_text = 2, f"位階低（一年區間{pctile*100:.1f}%）"
    else:
        pos_pts, pos_text = 1, f"位階偏低（{pctile*100:.1f}%）"
    if foreign20 > 0:
        f_pts, f_text = 2, f"外資近20日買超+{foreign20:,.0f}張"
    else:
        f_pts, f_text = 0, f"外資近20日賣超{foreign20:,.0f}張" if foreign20 < 0 else "外資近20日買賣超為0"
    if above20 and turning:
        t_pts, t_text = 2, "站上20MA且均線翻揚(止跌)"
    elif above20:
        t_pts, t_text = 1, "站上20MA"
    else:
        t_pts, t_text = 0, "未站上20MA"

    breakdown = [
        {"key": "position", "points": pos_pts, "max": 2,
         "value": {"pctile": pctile, "close": px, "low": lo, "high": hi},
         "rule": f"位階<35% 得2分、35%~{max_pctile*100:.0f}% 得1分、≥{max_pctile*100:.0f}% 不列入",
         "display": pos_text},
        {"key": "foreign_flow", "points": f_pts, "max": 2,
         "value": {"foreign20": foreign20},
         "rule": "外資近20日累計買超>0 得2分", "display": f_text},
        {"key": "stop_falling", "points": t_pts, "max": 2,
         "value": {"close": px, "sma20": sma20_now, "sma20_5d_ago": sma20_prev,
                   "above_sma20": above20, "sma20_rising": turning},
         "rule": "收盤站上20MA且20MA高於5日前得2分；只站上20MA得1分", "display": t_text},
    ]
    total = sum(b["points"] for b in breakdown)
    return {
        "close": px, "pctile": pctile, "foreign20": foreign20,
        "eligible": eligible,
        "excluded_reason": None if eligible else pos_text,
        "score": total if eligible else None,
        "max_score": MAX_SCORE,
        "breakdown": breakdown,
    }


def score(df, max_pctile: float = 0.5):
    d = score_detail(df, max_pctile)
    if d is None or not d["eligible"]:
        return None
    return {"close": round(d["close"], 2), "pctile": round(d["pctile"] * 100, 1),
            "foreign20": round(d["foreign20"]), "score": d["score"],
            "reasons": [b["display"] for b in d["breakdown"] if b["points"] > 0]}


def main():
    load_env()
    ap = argparse.ArgumentParser(description="發掘低價潛力股")
    ap.add_argument("--tickers", default=",".join(DEFAULT_UNIVERSE))
    ap.add_argument("--start", default="2024-06-01")
    ap.add_argument("--min-score", type=int, default=3)
    ap.add_argument("--max-pctile", type=float, default=0.5, help="位階上限（0.5=一年區間半數以下才算低價）")
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--line", action="store_true", help="把結果推 LINE")
    args = ap.parse_args()

    tickers = [t.strip() for t in args.tickers.split(",") if t.strip()]
    found = []
    failed = []
    for t in tickers:
        try:
            df = load(t, args.start, None)
        except Exception as e:
            failed.append(t)
            print(f"  略過 {t}：{e}")
            continue
        r = score(df, args.max_pctile)
        if r and r["score"] >= args.min_score:
            r["ticker"] = t
            found.append(r)
    if len(failed) == len(tickers):
        sys.exit("所有標的資料皆載入失敗")

    found.sort(key=lambda x: x["score"], reverse=True)
    found = found[: args.top]

    print(f"\n發掘低價潛力股（分數≥{args.min_score}，掃 {len(tickers)} 檔）\n")
    if not found:
        print("本次無符合標的。")
    for r in found:
        print(f"[{r['score']}分] {label(r['ticker'])}  收{r['close']}  位階{r['pctile']}%")
        print("     " + "、".join(r["reasons"]))

    if args.line and found:
        lines = ["💎 低價潛力股發掘"]
        for r in found[:8]:
            lines.append(f"[{r['score']}分] {label(r['ticker'])} 收{r['close']} 位階{r['pctile']}%")
        lines.append("（規則型篩選：位階低+籌碼進+止跌；僅供參考，非投資建議）")
        try:
            send_line("\n".join(lines))
            print("\n已推 LINE")
        except Exception as e:
            sys.exit(f"LINE 推播失敗：{e}")

    print("\n⚠️ 僅為規則型初篩，仍需搭配基本面/財報自行判斷。")


if __name__ == "__main__":
    main()
