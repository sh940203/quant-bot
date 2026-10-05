# quant-bot — 台股量化交易機器人（P0：回測引擎）

規則型策略的回測框架。用 FinMind 免費歷史資料驗證策略，**先確認策略有效再談實盤**。

> ⚠️ 量化交易高風險，多數策略在真實市場會失效、回測易過度擬合。本專案路線是
> **回測 → 紙上模擬 → 半自動（人工確認）→ 才考慮全自動**，且未來實盤下單一律
> 跑在你自己電腦、用你自己的券商憑證。本工具不構成投資建議。

## 結構
```
data/finmind.py        FinMind 歷史價量 + 三大法人籌碼
strategies/            規則型策略（可回測、可解釋）
  ma_cross.py          均線交叉 + 外資近 N 日淨買超過濾
  momentum.py          動能（近 N 日報酬 + 接近新高）
backtest/engine.py     向量化回測（含台股手續費/證交稅/滑價，延後一日執行避免未來函數）
backtest/metrics.py    總報酬 / CAGR / Sharpe / 最大回撤 / 勝率 / 曝險
run.py                 CLI，含樣本內/樣本外切分
```

## 安裝
```bash
cd quant-bot
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
cp .env.example .env        # 填入 FINMIND_TOKEN（選填，提高流量上限）
```

## 網頁介面（推薦）
```bash
./.venv/bin/streamlit run app.py
```
瀏覽器開 http://localhost:8501 —— 側邊欄選標的/策略/日期、勾選停損停利，
四個頁籤：回測（含權益曲線＋回撤圖）、參數掃描、Walk-forward、多標的組合。

## 命令列
```bash
./.venv/bin/python run.py --ticker 2330 --strategy ma_cross --start 2021-01-01
./.venv/bin/python run.py --ticker 3481 --strategy momentum --start 2020-01-01 --stop 0.08 --take 0.15
./.venv/bin/python sweep.py --ticker 2330 --strategy momentum --start 2020-01-01
./.venv/bin/python portfolio.py --strategy foreign_streak --start 2021-01-01
./.venv/bin/python walkforward.py --ticker 2330 --strategy momentum --start 2019-01-01
./.venv/bin/python screen.py --start 2019-01-01        # 跨標的×策略穩健度排名
./.venv/bin/python paper.py --strategy breakout --start 2024-01-01 --reset   # 紙上模擬
./.venv/bin/python discover.py --top 10                # 發掘低價潛力股（位階低+籌碼進+止跌）
./.venv/bin/python alert.py --strategy breakout        # 產生今日訊號並推 LINE（手動下單用）
```

## 自動排程（GitHub Actions，免開電腦）
- `.github/workflows/daily-signal.yml`：每交易日 14:30 跑 `alert.py` 推 LINE 訊號。
- `.github/workflows/weekly-discover.yml`：每週六跑 `discover.py` 推低價潛力股。
- 需在 GitHub repo 設 Secrets：`LINE_CHANNEL_ACCESS_TOKEN`、`FINMIND_TOKEN`。

## 策略（6 種，規則型可回測）
`ma_cross`（均線＋籌碼）、`momentum`（動能）、`rsi_reversion`（RSI 回歸）、
`breakout`（唐奇安突破）、`foreign_streak`（外資連買）、`trend_chip`（趨勢×籌碼×不追高 複合確認）

> 篩選器實測（2019–2026，6 檔半導體，walk-forward）：**breakout / foreign_streak 最穩健**
> （多檔都正報酬）；momentum / rsi_reversion 不可靠。詳見 `screen.py`。

## 變更紀錄
- **2026-10 位階計算修正**（`discover.py`）：位階原本是用 `--start`（2024-06-01）至今的收盤區間，
  區間會隨時間越拉越長，與「一年區間」的說法不符；現改為**滾動 252 個交易日**，顯示到小數 1 位。
  ⚠️ 修正後分數與名單會改變：以 2026-10-05 資料為例，入選從 4 檔（祥碩 6、天鈺 6、智原 5、凌陽 3）
  變為 1 檔（凌陽 3，位階 43%→47.3%）。

## 讀報表
- **對照買進持有**：策略總報酬要跟 buy & hold 比，贏不了大盤/個股長多就沒優勢。
- **樣本內 vs 樣本外**：樣本外（沒參與調參的後段）才是接近真實的表現；若樣本內漂亮、樣本外崩壞＝過度擬合。
- **Sharpe / 最大回撤**：報酬要看「承擔多少波動與回撤換來的」。

## 路線圖
- **P0**：回測引擎 ✅
- **P1**：6 策略 + 參數掃描 + 多標的組合 + 停損停利/部位控管 + walk-forward + 穩健篩選 + Streamlit ✅
- **P1.5**：每日紙上模擬引擎（`paper.py`，FinMind 資料、可排程）✅
- **P2（進行中）**：接永豐 Shioaji 即時行情（`broker/shioaji_client.py` 接口已備，需你的憑證）
- **P3**：風控層 + 半自動（訊號推 LINE，人工確認才送單）
- **P4（選配）**：長期穩定後才全自動，保留熔斷與每日虧損上限

## 券商接口（P2，需你的永豐帳戶）
`broker/shioaji_client.py` 已寫好接口（含 `simulation=True` 紙上模式）。前置：
永豐開戶並申請 API、取得 API Key/Secret、`pip install shioaji`。詳見該檔頂部說明。
**此模組尚未在本機實測**（需憑證），請對照永豐官方文件 https://sinotrade.github.io/ 確認。
