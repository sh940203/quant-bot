"""LINE 推播（Python 版，重用 MarketPilot 的官方帳號 token）。

環境變數：
  LINE_CHANNEL_ACCESS_TOKEN（必填）
  LINE_USER_ID（選填；留空則 broadcast 給所有好友）
"""
from __future__ import annotations
import os
import requests


def send_line(text: str) -> dict:
    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
    if not token:
        return {"skipped": True}
    to = os.environ.get("LINE_USER_ID")
    url = "https://api.line.me/v2/bot/message/push" if to else "https://api.line.me/v2/bot/message/broadcast"
    body = {"messages": [{"type": "text", "text": text}]}
    if to:
        body["to"] = to
    r = requests.post(
        url,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        json=body,
        timeout=15,
    )
    if not r.ok:
        raise RuntimeError(f"LINE 推播失敗 {r.status_code}: {r.text}")
    return {"ok": True}
