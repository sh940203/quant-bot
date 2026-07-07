"""永豐 Shioaji 接口（即時行情 + 紙上/實盤下單）。

⚠️ 這是接口模板，需要你的永豐帳戶與 API 憑證才能實際運作，且尚未在本機實測。
   使用前請對照永豐官方文件確認 API 介面：https://sinotrade.github.io/

前置：
  1. 永豐證券開戶並「申請 API 交易」。
  2. 於永豐後台取得 API Key / Secret Key。
  3. pip install shioaji（可能需額外系統相依；Mac/Linux 可用）。
  4. 實盤下單需 CA 憑證（.pfx）；simulation=True 的紙上模式通常不需 CA。

環境變數：
  SHIOAJI_API_KEY, SHIOAJI_SECRET_KEY
  （實盤才需）SHIOAJI_CA_PATH, SHIOAJI_CA_PASSWD, SHIOAJI_PERSON_ID

安全原則：預設 simulation=True（紙上）。切到實盤請非常謹慎，並保留風控與人工確認。
"""
from __future__ import annotations
import os


class ShioajiClient:
    def __init__(self, simulation: bool = True):
        try:
            import shioaji as sj  # 延後匯入，未安裝時給清楚訊息
        except ImportError as e:
            raise RuntimeError("尚未安裝 shioaji：pip install shioaji") from e
        self.sj = sj
        self.simulation = simulation
        self.api = sj.Shioaji(simulation=simulation)
        self._logged_in = False

    def login(self):
        key = os.environ.get("SHIOAJI_API_KEY")
        secret = os.environ.get("SHIOAJI_SECRET_KEY")
        if not key or not secret:
            raise RuntimeError("缺少 SHIOAJI_API_KEY / SHIOAJI_SECRET_KEY")
        self.api.login(api_key=key, secret_key=secret)
        # 實盤下單需啟用 CA 憑證（紙上模式可略）
        ca_path = os.environ.get("SHIOAJI_CA_PATH")
        if not self.simulation and ca_path:
            self.api.activate_ca(
                ca_path=ca_path,
                ca_passwd=os.environ.get("SHIOAJI_CA_PASSWD", ""),
                person_id=os.environ.get("SHIOAJI_PERSON_ID", ""),
            )
        self._logged_in = True
        return self

    def _contract(self, ticker: str):
        # 先找上市(TSE)，再找上櫃(OTC)
        stocks = self.api.Contracts.Stocks
        if ticker in stocks.TSE:
            return stocks.TSE[ticker]
        if ticker in stocks.OTC:
            return stocks.OTC[ticker]
        raise RuntimeError(f"找不到合約 {ticker}")

    def snapshot(self, ticker: str) -> dict:
        """即時快照：回傳最新成交價等。"""
        c = self._contract(ticker)
        snap = self.api.snapshots([c])[0]
        return {"ticker": ticker, "close": snap.close, "volume": snap.total_volume,
                "ts": snap.ts}

    def place_order(self, ticker: str, action: str, quantity: int, price: float | None = None):
        """下單（單位：張）。action = 'Buy' | 'Sell'。price=None 用市價，否則限價 ROD。

        ⚠️ simulation=True 時送到永豐模擬環境（紙上）；實盤請務必人工確認。
        """
        sj = self.sj
        c = self._contract(ticker)
        order = self.api.Order(
            price=price or 0,
            quantity=quantity,
            action=sj.constant.Action.Buy if action == "Buy" else sj.constant.Action.Sell,
            price_type=sj.constant.StockPriceType.LMT if price else sj.constant.StockPriceType.MKT,
            order_type=sj.constant.OrderType.ROD,
            account=self.api.stock_account,
        )
        return self.api.place_order(c, order)

    def list_positions(self):
        return self.api.list_positions(self.api.stock_account)

    def logout(self):
        if self._logged_in:
            self.api.logout()
            self._logged_in = False
