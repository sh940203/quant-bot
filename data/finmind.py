"""FinMind 歷史資料抓取（回測用）。回傳合併好的 pandas DataFrame。"""
from __future__ import annotations
import os
import requests
import pandas as pd

BASE = "https://api.finmindtrade.com/api/v4/data"


def _fetch(dataset: str, data_id: str, start: str, end: str | None = None) -> pd.DataFrame:
    params = {"dataset": dataset, "data_id": data_id, "start_date": start}
    if end:
        params["end_date"] = end
    token = os.environ.get("FINMIND_TOKEN")
    if token:
        params["token"] = token
    r = requests.get(BASE, params=params, timeout=30)
    if r.status_code == 402:
        raise RuntimeError("FinMind 流量已達上限（設定 FINMIND_TOKEN 可提高到 600/hr）")
    r.raise_for_status()
    js = r.json()
    if js.get("status") != 200:
        raise RuntimeError(f"FinMind 錯誤：{js.get('msg')}")
    return pd.DataFrame(js.get("data", []))


def load_price(ticker: str, start: str, end: str | None = None) -> pd.DataFrame:
    """個股日 K：index=date，欄位 open/high/low/close/volume。"""
    df = _fetch("TaiwanStockPrice", ticker, start, end)
    if df.empty:
        raise RuntimeError(f"找不到 {ticker} 的價量資料")
    df = df.rename(columns={"max": "high", "min": "low", "Trading_Volume": "volume"})
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()
    return df[["open", "high", "low", "close", "volume"]].astype(float)


def load_institutional(ticker: str, start: str, end: str | None = None) -> pd.DataFrame:
    """三大法人「淨買賣超（張）」：index=date，欄位 foreign/trust/dealer/total。"""
    df = _fetch("TaiwanStockInstitutionalInvestorsBuySell", ticker, start, end)
    if df.empty:
        return pd.DataFrame(columns=["foreign", "trust", "dealer", "total"])
    df["date"] = pd.to_datetime(df["date"])
    df["net"] = (df["buy"] - df["sell"]) / 1000.0  # 股 → 張

    def net_of(names: list[str]) -> pd.Series:
        sub = df[df["name"].isin(names)]
        return sub.groupby("date")["net"].sum()

    out = pd.DataFrame(
        {
            "foreign": net_of(["Foreign_Investor", "Foreign_Dealer_Self"]),
            "trust": net_of(["Investment_Trust"]),
            "dealer": net_of(["Dealer_self", "Dealer_Hedging"]),
        }
    ).fillna(0.0)
    out["total"] = out.sum(axis=1)
    return out.sort_index()


def load(ticker: str, start: str, end: str | None = None) -> pd.DataFrame:
    """價量 + 籌碼 合併（籌碼欄位對齊交易日，缺值補 0）。"""
    price = load_price(ticker, start, end)
    inst = load_institutional(ticker, start, end)
    df = price.join(inst, how="left")
    for c in ["foreign", "trust", "dealer", "total"]:
        if c not in df:
            df[c] = 0.0
    df[["foreign", "trust", "dealer", "total"]] = df[["foreign", "trust", "dealer", "total"]].fillna(0.0)
    return df
