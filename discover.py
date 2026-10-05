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

from data.finmind import load
from run import load_env
from notify import send_line

# 預設掃描宇宙（台股中大型科技/半導體，價位分布廣）
DEFAULT_UNIVERSE = [
    "2303", "2379", "3034", "3711", "3661", "3035", "3443", "6415", "2408", "2344",
    "2337", "4919", "5269", "3529", "3006", "3016", "8016", "3260", "6147", "4961",
    "3105", "2401", "6239", "3532", "2451", "2049", "1590", "3037", "3017", "6488",
]

NAME_MAP = {
    "2303": "聯電", "2379": "瑞昱", "3034": "聯詠", "3711": "日月光", "3661": "世芯-KY",
    "3035": "智原", "3443": "創意", "6415": "矽力-KY", "2408": "南亞科", "2344": "華邦電",
    "2337": "旺宏", "4919": "新唐", "5269": "祥碩", "3529": "力旺", "3006": "晶豪科",
    "3016": "嘉晶", "8016": "矽創", "3260": "威剛", "6147": "頎邦", "4961": "天鈺",
    "3105": "穩懋", "2401": "凌陽", "6239": "力成", "3532": "台勝科", "2451": "創見",
    "2049": "上銀", "1590": "亞德客-KY", "3037": "欣興", "3017": "奇鋐", "6488": "環球晶",
}


LOOKBACK = 252  # 位階區間：滾動 252 個交易日（約一年）


def score(df, max_pctile: float = 0.5):
    close = df["close"].tail(LOOKBACK)
    if len(close) < 120:
        return None
    px = float(close.iloc[-1])
    lo, hi = float(close.min()), float(close.max())
    pctile = (px - lo) / (hi - lo) if hi > lo else 1.0
    # 硬門檻：必須是「低價」（位階在一年區間低檔）才納入
    if pctile >= max_pctile:
        return None
    sma20 = close.rolling(20).mean()
    above20 = px > float(sma20.iloc[-1])
    turning = float(sma20.iloc[-1]) > float(sma20.iloc[-6])
    foreign20 = float(df["foreign"].tail(20).sum())

    s = 0
    reasons = []
    if pctile < 0.35:
        s += 2; reasons.append(f"位階低（一年區間{pctile*100:.1f}%）")
    else:
        s += 1; reasons.append(f"位階偏低（{pctile*100:.1f}%）")
    if foreign20 > 0:
        s += 2; reasons.append(f"外資近20日買超+{foreign20:,.0f}張")
    if above20 and turning:
        s += 2; reasons.append("站上20MA且均線翻揚(止跌)")
    elif above20:
        s += 1; reasons.append("站上20MA")
    return {"close": round(px, 2), "pctile": round(pctile * 100, 1), "foreign20": round(foreign20),
            "score": s, "reasons": reasons}


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
    for t in tickers:
        try:
            df = load(t, args.start, None)
            r = score(df, args.max_pctile)
            if r and r["score"] >= args.min_score:
                r["ticker"] = t
                found.append(r)
        except Exception:
            continue

    found.sort(key=lambda x: x["score"], reverse=True)
    found = found[: args.top]

    def nm(t):
        return f"{t} {NAME_MAP[t]}" if t in NAME_MAP else t

    print(f"\n發掘低價潛力股（分數≥{args.min_score}，掃 {len(tickers)} 檔）\n")
    if not found:
        print("本次無符合標的。")
    for r in found:
        print(f"[{r['score']}分] {nm(r['ticker'])}  收{r['close']}  位階{r['pctile']}%")
        print("     " + "、".join(r["reasons"]))

    if args.line and found:
        lines = ["💎 低價潛力股發掘"]
        for r in found[:8]:
            lines.append(f"[{r['score']}分] {nm(r['ticker'])} 收{r['close']} 位階{r['pctile']}%")
        lines.append("（規則型篩選：位階低+籌碼進+止跌；僅供參考，非投資建議）")
        try:
            send_line("\n".join(lines))
            print("\n已推 LINE")
        except Exception as e:
            print(f"\nLINE 推播失敗：{e}")

    print("\n⚠️ 僅為規則型初篩，仍需搭配基本面/財報自行判斷。")


if __name__ == "__main__":
    main()
