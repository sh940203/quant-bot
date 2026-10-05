"""LINE 推播（Messaging API Push，只推給指定使用者；沿用 MarketPilot 的官方帳號 channel）。

環境變數：
  LINE_CHANNEL_ACCESS_TOKEN（必填）
  LINE_USER_ID（必填；推播對象。不再 broadcast 給所有好友，避免耗用訊息額度）
"""
from __future__ import annotations
import os
import requests

PUSH_URL = "https://api.line.me/v2/bot/message/push"


def send_line(text: str) -> dict:
    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
    to = os.environ.get("LINE_USER_ID")
    missing = [k for k, v in (("LINE_CHANNEL_ACCESS_TOKEN", token), ("LINE_USER_ID", to)) if not v]
    if missing:
        raise RuntimeError(f"缺少環境變數：{', '.join(missing)}（只想看結果請加 --no-line）")
    r = requests.post(
        PUSH_URL,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        json={"to": to, "messages": [{"type": "text", "text": text}]},
        timeout=15,
    )
    if not r.ok:
        raise RuntimeError(f"LINE 推播失敗 {r.status_code}: {r.text}")
    return {"ok": True}
