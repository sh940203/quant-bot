# n8n：LINE AI 小精靈

LINE 使用者傳訊息 → LINE 平台呼叫 webhook → Cloudflare Tunnel → 本機 n8n → 回覆。

## 需求
- Docker（Mac 建議 OrbStack：`brew install --cask orbstack`）
- LINE Messaging API channel（Channel access token、Channel secret）

## 啟動
```bash
cd n8n
cp .env.example .env          # 填入 N8N_ENCRYPTION_KEY（openssl rand -hex 32）
docker compose up -d
docker compose exec -T n8n n8n import:workflow --input=/workflows/line-echo.json
docker compose logs tunnel | grep trycloudflare.com   # 查對外網址
```
- n8n 介面：http://localhost:5678（只開給本機）
- Webhook 網址：`<tunnel 網址>/webhook/line`

## 第一次設定（n8n 介面）
1. 開 http://localhost:5678 建立 owner 帳號
2. 左側 **Credentials → Add credential → Header Auth**
   - Name 欄：`Authorization`；Value 欄：`Bearer <Channel access token>`
   - Credential 名稱取 `LINE Channel Access Token`
3. 打開 workflow「LINE 小精靈（階段2：echo）」→ 點 **LINE Reply** 節點 → 選剛建的 credential → 儲存
4. 右上角切成 **Active**（Published）

## 第一次設定（LINE）
1. LINE Developers → channel → **Messaging API** 分頁
   - Webhook URL 填 `<tunnel 網址>/webhook/line` → **Update** → **Verify**（應顯示 Success）
   - **Use webhook** 打開
2. 同頁「Auto-reply messages」→ 進 LINE Official Account Manager
   - 回應設定：**Webhook 開**、**自動回應訊息關**、加入好友歡迎訊息可保留
   - 不關自動回應會出現「重複回覆」

## ⚠️ quick tunnel 的限制
目前用 Cloudflare **quick tunnel**（免網域、免帳號），代價是：
- 每次 `docker compose up`／重開機，**網址都會變** → 要重新到 LINE Developers 更新 Webhook URL 並 Verify
- 沒有 SLA，Cloudflare 隨時可能中斷；Mac 睡眠時 Bot 不會回應

## 之後換成 named tunnel（需在 Cloudflare 有一個網域）
1. Cloudflare Zero Trust → **Networks → Tunnels → Create a tunnel**（Cloudflared）→ 複製 tunnel token
2. 同一個 tunnel 加 **Public Hostname**：例如 `bot.你的網域` → Service `HTTP` `n8n:5678`
3. `.env` 加上 `TUNNEL_TOKEN=<token>`、`WEBHOOK_URL=https://bot.你的網域`
4. `docker-compose.yml` 的 tunnel 服務改成：
   ```yaml
   command: tunnel --no-autoupdate run
   environment:
     - TUNNEL_TOKEN=${TUNNEL_TOKEN}
   ```
5. `docker compose up -d`，LINE Webhook URL 改成 `https://bot.你的網域/webhook/line`（之後就不會再變）

同一份 compose 也可以原封搬到 VPS，達成 24 小時在線。

## 常用指令
```bash
docker compose ps                 # 狀態
docker compose logs -f n8n        # n8n log
docker compose restart tunnel     # 重開 tunnel（網址會變！）
docker compose down               # 停止（資料保留在 n8n_data volume）
```

## 階段 3：AI 小精靈（`workflows/line-ai-sprite.json`）
workflow JSON 由 `scripts/build_ai_workflow.py` 產生（系統提示詞、工具描述都在裡面，方便 review）：
```bash
python3 n8n/scripts/build_ai_workflow.py
docker compose exec -T n8n n8n import:workflow --input=/workflows/line-ai-sprite.json
docker compose exec -T n8n n8n publish:workflow --id=WdMd52HM3w0w546g
docker compose restart n8n          # CLI 發布後需重啟 n8n 才生效（tunnel 不用重啟，網址不變）
```
- `.env` 需要 `SIGNALS_BASE_URL`（R2 公開網域 + 路徑前綴）
- n8n 需先建好兩個 credential：Header Auth（LINE token）、Google Gemini(PaLM) API
- 流程：整理輸入 → AI Agent（Gemini 2.5 Flash + 對話記憶 10 輪 + 3 個 HTTP 工具）→ 整理回覆（去 Markdown、附免責聲明）→ Reply API；
  AI 失敗時走「降級回覆」，同時另一條支線呼叫 loading 動畫 API 顯示「輸入中」
- ⚠️ Gemini 免費額度很小（2.5 Flash 每專案每天 20 次請求、每題約 2 次）；正式展示前需開啟計費或改用其他模型
