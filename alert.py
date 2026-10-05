"""每日訊號通知：算最新交易日訊號，分類「買進 / 出場 / 續抱」，推 LINE。
供兆豐（或任何券商）app 手動下單使用——機器人決策、你的手下單。

範例：
    python alert.py --strategy breakout
    python alert.py --strategy foreign_streak --tickers 2330,2454,3711 --no-line

推播或資料全數失敗時以非 0 結束碼離開，讓 GitHub Actions 顯示失敗。
"""
from __future__ import annotations
import argparse
import sys

from data.finmind import load
from strategies import REGISTRY
from run import load_env
from notify import send_line

NAME_MAP = {
    "2330": "台積電", "2454": "聯發科", "3711": "日月光投控", "3661": "世芯-KY",
    "3034": "聯詠", "2379": "瑞昱", "3037": "欣興", "3035": "智原", "3443": "創意",
    "6415": "矽力-KY", "2408": "南亞科", "3529": "力旺", "5269": "祥碩", "3006": "晶豪科",
}


def name(t: str) -> str:
    return f"{t} {NAME_MAP[t]}" if t in NAME_MAP else t


def main():
    load_env()
    ap = argparse.ArgumentParser(description="每日訊號通知（手動下單）")
    ap.add_argument("--strategy", default="breakout", choices=list(REGISTRY))
    ap.add_argument("--tickers", default="2330,2454,3711,3661,3034,2379")
    ap.add_argument("--start", default="2024-01-01")
    ap.add_argument("--no-line", action="store_true", help="只印出、不推 LINE")
    args = ap.parse_args()

    tickers = [t.strip() for t in args.tickers.split(",") if t.strip()]
    StratCls = REGISTRY[args.strategy]

    buys, sells, holds = [], [], []
    trade_date = None
    for t in tickers:
        try:
            df = load(t, args.start, None)
            pos = StratCls().positions(df)
            if len(pos) < 2:
                continue
            now, prev = pos.iloc[-1], pos.iloc[-2]
            trade_date = df.index[-1].date()
            if now > 0 and prev == 0:
                buys.append(t)
            elif now == 0 and prev > 0:
                sells.append(t)
            elif now > 0 and prev > 0:
                holds.append(t)
        except Exception as e:
            print(f"  略過 {t}：{e}")

    lines = [f"📈 quant-bot 今日訊號 {trade_date}（策略 {args.strategy}）"]
    if buys:
        lines.append("🔴 買進：" + "、".join(name(t) for t in buys))
    if sells:
        lines.append("🟢 出場：" + "、".join(name(t) for t in sells))
    if holds:
        lines.append("⚪ 續抱：" + "、".join(name(t) for t in holds))
    if not (buys or sells or holds):
        lines.append("今日無持倉訊號（空手觀望）")
    lines.append("（依昨日收盤訊號，請自行在券商 app 下單；僅供參考，非投資建議）")
    msg = "\n".join(lines)

    print("\n" + msg + "\n")
    if trade_date is None:
        sys.exit("所有標的資料皆載入失敗，不推播")
    if not args.no_line:
        try:
            send_line(msg)
            print("已推 LINE")
        except Exception as e:
            sys.exit(f"LINE 推播失敗：{e}")


if __name__ == "__main__":
    main()
