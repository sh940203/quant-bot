"""匯出訊號 JSON（給 n8n AI 小精靈讀取）。

產出（--out 預設 out/signals）：
  latest/summary.json              今日總覽：breakout 分類、潛力股排名、規則說明
  latest/tickers/{code}.json       個股明細：價量、籌碼、breakout 判斷依據、潛力股評分明細、近 N 日變化
  daily/{as_of}/...                同上一份存檔

數值欄位一律保留未四捨五入的原始值；給人看的字串放在 display 欄位。
breakout 與 alert.py 使用相同的起始日與參數，結果與當日推播一致。

範例：
    python export_signals.py
    python export_signals.py --out /tmp/signals --history 5
"""
from __future__ import annotations
import argparse
import json
import math
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from data.finmind import load
from strategies.breakout import Breakout
from discover import DEFAULT_UNIVERSE, LOOKBACK, MAX_SCORE, score_detail
from names import name_of
from run import load_env

SCHEMA_VERSION = 1
TPE = timezone(timedelta(hours=8))
BREAKOUT_TICKERS = ["2330", "2454", "3711", "3661", "3034", "2379"]  # 與 daily-signal.yml 一致
DISCLAIMER = "僅供參考，非投資建議"


def clean(x):
    """遞迴把 NaN/inf 轉成 None，numpy 數值轉成 Python 原生型別。"""
    if isinstance(x, dict):
        return {k: clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [clean(v) for v in x]
    if hasattr(x, "item"):  # numpy scalar
        x = x.item()
    if isinstance(x, float) and not math.isfinite(x):
        return None
    return x


def pct(x: float | None, digits: int = 1) -> str | None:
    return None if x is None else f"{x * 100:+.{digits}f}%"


def build_ticker(code: str, df, in_breakout: bool, in_discover: bool,
                 max_pctile: float, history: int) -> dict:
    close = df["close"]
    tail = close.tail(LOOKBACK)
    sma20 = close.rolling(20).mean()
    px = float(close.iloc[-1])
    prev_close = float(close.iloc[-2]) if len(close) > 1 else None
    change = px / prev_close - 1 if prev_close else None

    out = {
        "code": code,
        "name": name_of(code),
        "as_of": str(df.index[-1].date()),
        "in_breakout_basket": in_breakout,
        "in_discover_universe": in_discover,
        "price": {
            "close": px,
            "prev_close": prev_close,
            "change_pct": change,
            "high_252": float(tail.max()),
            "low_252": float(tail.min()),
            "sma20": float(sma20.iloc[-1]),
            "sma20_5d_ago": float(sma20.iloc[-6]) if len(sma20) > 5 else None,
            "volume_lots": float(df["volume"].iloc[-1]) / 1000.0,
            "display": f"收 {px:g}（{pct(change, 2) or '—'}）",
        },
        "chips": {
            "unit": "張",
            "foreign_1d": float(df["foreign"].iloc[-1]),
            "foreign_5d": float(df["foreign"].tail(5).sum()),
            "foreign_20d": float(df["foreign"].tail(20).sum()),
            "trust_20d": float(df["trust"].tail(20).sum()),
            "dealer_20d": float(df["dealer"].tail(20).sum()),
            # 法人資料缺值會被補 0；當日三者全為 0 多半代表資料尚未更新
            "latest_day_missing": bool((df[["foreign", "trust", "dealer"]].iloc[-1] == 0).all()),
        },
    }

    b = Breakout().explain(df, history=history)
    b["display"] = {
        "buy": "今日突破，新進場",
        "sell": "今日跌破出場線，出場",
        "hold": f"續抱中（{b['since']} 進場，持有 {b['holding_days']} 日，距出場線 {pct(b['pct_above_exit_level'])}）",
        "flat": f"空手（距進場線 {pct(b['pct_below_entry_level'])}）",
    }[b["action"]]
    out["breakout"] = b

    d = score_detail(df, max_pctile)
    if d is not None:
        d["display"] = (f"{d['score']}/{MAX_SCORE} 分" if d["eligible"]
                        else f"未列入：{d['excluded_reason']}")
        hist = []
        for i in range(len(df) - history, len(df)):
            h = score_detail(df.iloc[: i + 1], max_pctile)
            if h is not None:
                hist.append({"date": str(df.index[i].date()), "score": h["score"],
                             "eligible": h["eligible"], "pctile": h["pctile"]})
        d["history"] = hist
    out["discover"] = d
    return out


def build_summary(tickers: dict, as_of: str, warnings: list, min_score: int,
                  max_pctile: float, top: int) -> dict:
    breakout = {"buy": [], "sell": [], "hold": [], "flat": []}
    for code in BREAKOUT_TICKERS:
        t = tickers.get(code)
        if t:
            breakout[t["breakout"]["action"]].append(code)

    ranked = []
    for code in DEFAULT_UNIVERSE:  # 與 discover.py 相同順序（同分時保持宇宙順序）
        t = tickers.get(code)
        d = t and t["discover"]
        if d and d["eligible"] and d["score"] >= min_score:
            ranked.append({"code": code, "name": t["name"], "score": d["score"],
                           "close": d["close"], "pctile": d["pctile"],
                           "display": f"[{d['score']}分] {code} {t['name'] or ''} 收{d['close']:g} 位階{d['pctile']*100:.1f}%"})
    ranked.sort(key=lambda r: r["score"], reverse=True)

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(TPE).isoformat(timespec="seconds"),
        "as_of": as_of,
        "source": "FinMind（TaiwanStockPrice、TaiwanStockInstitutionalInvestorsBuySell）",
        "disclaimer": DISCLAIMER,
        "warnings": warnings,
        "universe": [
            {"code": c, "name": t["name"], "in_breakout_basket": t["in_breakout_basket"],
             "in_discover_universe": t["in_discover_universe"], "detail": f"tickers/{c}.json"}
            for c, t in tickers.items()
        ],
        "breakout": {
            "strategy": "唐奇安通道突破（breakout）",
            "params": {"entry": 20, "exit": 10},
            "rules": {
                "entry": "收盤價 ≥ 近20日最高收盤價（含當日）→ 進場",
                "exit": "收盤價 ≤ 近10日最低收盤價（含當日）→ 出場",
                "hold": "已進場且尚未觸發出場 → 續抱",
                "timing": "依當日收盤計算，供隔日手動下單參考",
            },
            "tickers": BREAKOUT_TICKERS,
            **breakout,
        },
        "discover": {
            "strategy": "低價潛力股（位階低＋籌碼進＋止跌）",
            "params": {"lookback_days": LOOKBACK, "max_pctile": max_pctile,
                       "min_score": min_score, "top": top},
            "max_score": MAX_SCORE,
            "rules": [
                {"key": "position", "max": 2,
                 "desc": f"位階＝(收盤−近{LOOKBACK}日最低收盤)/(最高−最低)；<35% 得2分、35%~{max_pctile*100:.0f}% 得1分、≥{max_pctile*100:.0f}% 不列入"},
                {"key": "foreign_flow", "max": 2, "desc": "外資近20日累計買超>0 得2分"},
                {"key": "stop_falling", "max": 2, "desc": "收盤站上20MA且20MA高於5日前得2分；只站上20MA得1分"},
            ],
            "push_schedule": "每週六推播（使用週五收盤資料）；此處為每日重算結果",
            "ranked": ranked[:top],
        },
    }


def write_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(clean(obj), ensure_ascii=False, indent=1, allow_nan=False))


def main():
    load_env()
    ap = argparse.ArgumentParser(description="匯出訊號 JSON（給 n8n 讀取）")
    ap.add_argument("--out", default="out/signals")
    ap.add_argument("--start", default="2024-01-01", help="與 alert.py 相同，breakout 結果才會一致")
    ap.add_argument("--history", type=int, default=10, help="附上最近幾個交易日的變化")
    ap.add_argument("--min-score", type=int, default=3)
    ap.add_argument("--max-pctile", type=float, default=0.5)
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--min-ok", type=float, default=0.8, help="成功載入比例低於此值則失敗")
    args = ap.parse_args()

    codes = list(dict.fromkeys(BREAKOUT_TICKERS + DEFAULT_UNIVERSE))
    tickers, warnings = {}, []
    for code in codes:
        try:
            df = load(code, args.start, None)
            tickers[code] = build_ticker(code, df, code in BREAKOUT_TICKERS, code in DEFAULT_UNIVERSE,
                                         args.max_pctile, args.history)
        except Exception as e:
            warnings.append(f"{code} 載入失敗：{e}")
            print(f"  略過 {code}：{e}")

    if len(tickers) < args.min_ok * len(codes):
        sys.exit(f"成功載入 {len(tickers)}/{len(codes)} 檔，低於門檻，不匯出")

    dates = {t["as_of"] for t in tickers.values()}
    as_of = max(dates)
    stale = [c for c, t in tickers.items() if t["as_of"] != as_of]
    if stale:
        warnings.append(f"以下標的資料日期落後 {as_of}：{', '.join(stale)}")

    missing = [c for c, t in tickers.items() if t["chips"]["latest_day_missing"]]
    if len(missing) > len(tickers) / 2:
        warnings.append(f"{as_of} 三大法人資料可能尚未更新（{len(missing)}/{len(tickers)} 檔當日為 0），籌碼分數可能偏低")

    summary = build_summary(tickers, as_of, warnings, args.min_score, args.max_pctile, args.top)

    out = Path(args.out)
    latest = out / "latest"
    shutil.rmtree(latest, ignore_errors=True)
    for base in (latest, out / "daily" / as_of):
        write_json(base / "summary.json", summary)
        for code, t in tickers.items():
            write_json(base / "tickers" / f"{code}.json", t)

    b = summary["breakout"]
    print(f"已匯出 {len(tickers)} 檔 @ {as_of} → {out}")
    print(f"  breakout 買進{b['buy']} 出場{b['sell']} 續抱{b['hold']}")
    print(f"  潛力股 {[r['display'] for r in summary['discover']['ranked']]}")
    for w in warnings:
        print(f"  ⚠️ {w}")


if __name__ == "__main__":
    main()
