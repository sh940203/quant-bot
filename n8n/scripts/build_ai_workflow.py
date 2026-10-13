"""產生 n8n/workflows/line-ai-sprite.json（LINE AI 小精靈）。

用程式產生 workflow JSON，系統提示詞與工具描述才能在 git 裡被 review。
執行：python3 n8n/scripts/build_ai_workflow.py
"""
import json
import pathlib
import uuid

WORKFLOW_ID = "WdMd52HM3w0w546g"          # 沿用階段 2 的 workflow（匯入時覆蓋）
WEBHOOK_ID = None                           # 由既有 echo workflow 讀取，保持 webhook 註冊不變
CRED_LINE = {"httpHeaderAuth": {"id": "hEfjdqV0KBEEzSHk", "name": "Header Auth account"}}
CRED_GEMINI = {"googlePalmApi": {"id": "zaRFi5kqulYsIVMI", "name": "Google Gemini(PaLM) Api account"}}
DISCLAIMER = "※ 小精靈只解釋 quant-bot 的規則型訊號，僅供參考，非投資建議。"

ROOT = pathlib.Path(__file__).resolve().parents[1]
echo = json.loads((ROOT / "workflows/line-echo.json").read_text())
WEBHOOK_ID = next(n["webhookId"] for n in echo["nodes"] if n["name"] == "LINE Webhook")

SYSTEM_PROMPT = """你是「書浩專屬投資機器人」裡的 AI 小精靈，負責用白話解釋 quant-bot 每天產生的台股規則型訊號。
現在時間（台北）：{{ $now.setZone('Asia/Taipei').toFormat('yyyy-MM-dd HH:mm') }}

## 你能用的工具
1. get_signal_summary：今日總覽（breakout 買進/出場/續抱/空手、低價潛力股排名、評分規則、追蹤清單的代號與名稱、資料日期 as_of、warnings）
2. get_ticker_detail：單一股票明細（價量、三大法人、breakout 判斷依據、潛力股評分明細與未入選原因、近 10 個交易日變化）
3. get_realtime_quote：證交所/櫃買即時報價（盤中延遲數秒；收盤後為當日收盤）

## 回答規則
- 每一則新問題都要先呼叫工具取得最新資料再回答；即使先前對話出現過，也不可憑記憶回答數字或訊號狀態。對話記憶只用來理解「它」「那檔」指的是哪一檔股票。
- 數字一律來自工具結果，不可自行推測或編造。回答時註明資料日期（as_of）。
- 使用者用股票名稱（如「智原」）時，先用 get_signal_summary 的 universe 找到代號，再查明細。
- get_ticker_detail 回傳錯誤或找不到時，代表該股不在 quant-bot 追蹤清單；可改用 get_realtime_quote 提供報價，並說明沒有訊號資料。
- JSON 中的比例欄位是 0~1 的小數（pctile、change_pct、pct_above_exit_level、return_since_entry），回答時換成百分比、保留 1 位小數。籌碼單位是「張」。
- breakout 每日推播只涵蓋 summary.breakout.tickers 這 6 檔（明細中 in_breakout_basket=true）。其他股票明細裡的 breakout 欄位只是「套用同一規則的參考狀態」，不是 quant-bot 發出的訊號：不可說它「觸發進場/出場訊號」，要說「若套用 breakout 規則，目前會是…，但它不在每日推播清單」。
- 解釋 breakout：進場＝收盤 ≥ 近 20 日最高收盤；出場＝收盤 ≤ 近 10 日最低收盤；續抱＝已進場且未跌破出場線。說明 entry_level、exit_level、進場日 since、距出場線多少。
- 解釋潛力股分數：逐項列出 breakdown 的得分（位階、外資、止跌，各滿分 2 分，總分 6 分），並用 value 裡的原始數值說明為何得分。若位階在 35% 或 50% 門檻附近，要講出精確數值。未入選要說明 excluded_reason。
- 問「這週／最近有什麼變化」時，用 get_signal_summary 的 breakout.recent_changes（進出場事件）與 discover.ranked_history（每日入選潛力股）回答；沒有事件的股票就說狀態未變。資料涵蓋近 10 個交易日，回答時說明起訖日期。個股的變化用明細裡的 history。
- summary 有 warnings 時要提醒使用者。
- 即時報價欄位：z＝成交價（"-" 表示尚無成交）、y＝昨收、o＝開盤、h＝最高、l＝最低、v＝累積成交量（張）、t＝時間、d＝日期。msgArray 中空白的那筆忽略。

## 絕對不能做
- 不給買進、賣出、加碼、停損等操作建議，不給目標價或持股比例，不預測漲跌。
- 不用帶評價或暗示操作的字眼，例如「安全」「危險」「值得關注」「需要留意」「偏保守」「強勢／弱勢」「機會」；只陳述數字與規則（例如「距出場線 0.6%」）。
- 回答「這週變化」時只根據工具回傳的 history 數值，不推測原因（例如不要說「因為股價反彈」）。
- 被問「要不要買／該不該賣」時，禮貌說明你只負責解釋規則與資料，並提供該股目前的訊號狀態與依據。
- 不回答與台股、quant-bot 無關的問題（簡短婉拒，並說明你能做什麼）。

## 格式（LINE 純文字）
- 繁體中文，口吻親切簡潔，通常 150～300 字。
- 不要用 Markdown（不要 **粗體**、# 標題、表格）；條列用「・」，可適度使用 emoji。
- 不需要自己加免責聲明，系統會自動附上。"""

SUMMARY_DESC = ("取得 quant-bot 今日訊號總覽 JSON。包含：as_of 資料日期、warnings、universe（追蹤清單代號與名稱，"
                "用來把股票名稱轉成代號）、breakout（策略規則、buy/sell/hold/flat 代號清單、recent_changes 近10日進出場事件）、"
                "discover（評分規則、ranked 今日排名、ranked_history 近10日每日入選名單）。"
                "回答「今天訊號」「哪些續抱」「潛力股有哪些」「這週有什麼變化」或需要把股票名稱轉代號時使用。不需要參數。")
DETAIL_DESC = ("取得單一股票的訊號明細 JSON。包含 price（收盤、252 日高低、20MA）、chips（三大法人近 1/5/20 日買賣超，單位張）、"
               "breakout（action、entry_level、exit_level、since 進場日、holding_days、pct_above_exit_level、history 近10日部位）、"
               "discover（eligible、score、excluded_reason、breakdown 各項得分與原始數值、history 近10日分數）。"
               "回答「為什麼續抱 X」「X 為什麼幾分」「X 位階多少」「X 最近變化」時使用。參數 code 是 4 位數台股代號。")
QUOTE_DESC = ("查詢台股即時報價（證交所 MIS，上市與上櫃都可查）。回傳 msgArray，其中有資料的那筆欄位：z 成交價、y 昨收、o 開、h 高、l 低、"
              "v 累積成交量（張）、n 名稱、d 日期、t 時間。回答「現在價格」「今天漲跌」時使用。參數 code 是 4 位數台股代號。")

CODE_PREPARE = """// 取出 LINE 事件中需要的欄位，交給 AI Agent
const e = $input.item.json;
return {
  json: {
    chatInput: e.message.text,
    sessionId: e.source.userId,      // 每位使用者各自的對話記憶
    replyToken: e.replyToken,
  },
};"""

CODE_FORMAT = f"""// LINE 不支援 Markdown：去掉 **、#、` 等符號；限制長度；固定附上免責聲明
let text = String($json.output ?? '').trim();
text = text
  .replace(/\\*\\*(.+?)\\*\\*/g, '$1')
  .replace(/^#+\\s*/gm, '')
  .replace(/`/g, '')
  .replace(/^\\s*[-*]\\s+/gm, '・');
if (!text) text = '小精靈這次想不出答案，請換個問法再試一次 🙏';
if (text.length > 4500) text = text.slice(0, 4500) + '…（內容過長已截斷）';
return {{
  json: {{
    replyToken: $('整理輸入').item.json.replyToken,
    text: text + '\\n\\n{DISCLAIMER}',
  }},
}};"""

CODE_FALLBACK = """// AI Agent 失敗（模型逾時、額度用完、工具錯誤）時的降級回覆
return {
  json: {
    replyToken: $('整理輸入').item.json.replyToken,
    text: '小精靈暫時無法回答（AI 服務忙碌或資料讀取失敗），請稍後再試 🙏',
  },
};"""


def node(name, type_, version, pos, params, **extra):
    n = {"id": str(uuid.uuid4()), "name": name, "type": type_, "typeVersion": version,
         "position": pos, "parameters": params}
    n.update(extra)
    return n


def tool(name, pos, url, desc):
    return node(name, "n8n-nodes-base.httpRequestTool", 4.2, pos, {
        "toolDescription": desc,
        "url": url,
        "options": {"response": {"response": {"neverError": True}}, "timeout": 10000},
    })


nodes = [
    node("LINE Webhook", "n8n-nodes-base.webhook", 2, [0, 0],
         {"httpMethod": "POST", "path": "line", "responseMode": "responseNode", "options": {}},
         webhookId=WEBHOOK_ID),
    node("回應 200", "n8n-nodes-base.respondToWebhook", 1.1, [220, 0],
         {"respondWith": "noData", "options": {}}),
    node("拆開 events", "n8n-nodes-base.splitOut", 1, [440, 0],
         {"fieldToSplitOut": "body.events", "options": {}}),
    node("只留文字訊息", "n8n-nodes-base.filter", 2, [660, 0], {
        "conditions": {
            "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict"},
            "conditions": [
                {"id": str(uuid.uuid4()), "leftValue": "={{ $json.type }}", "rightValue": "message",
                 "operator": {"type": "string", "operation": "equals"}},
                {"id": str(uuid.uuid4()), "leftValue": "={{ $json.message.type }}", "rightValue": "text",
                 "operator": {"type": "string", "operation": "equals"}}],
            "combinator": "and"},
        "options": {}}),
    node("整理輸入", "n8n-nodes-base.code", 2, [880, 0],
         {"mode": "runOnceForEachItem", "jsCode": CODE_PREPARE}),
    node("顯示輸入中", "n8n-nodes-base.httpRequest", 4.2, [1100, -200], {
        "method": "POST", "url": "https://api.line.me/v2/bot/chat/loading/start",
        "authentication": "genericCredentialType", "genericAuthType": "httpHeaderAuth",
        "sendBody": True, "specifyBody": "json",
        "jsonBody": "={{ JSON.stringify({ chatId: $json.sessionId, loadingSeconds: 20 }) }}",
        "options": {}}, credentials=CRED_LINE, onError="continueRegularOutput"),
    node("AI Agent", "@n8n/n8n-nodes-langchain.agent", 3.1, [1100, 0], {
        "promptType": "define", "text": "={{ $json.chatInput }}",
        "options": {"systemMessage": "=" + SYSTEM_PROMPT, "maxIterations": 6}},
        onError="continueErrorOutput"),
    node("Gemini", "@n8n/n8n-nodes-langchain.lmChatGoogleGemini", 1.2, [940, 260], {
        "modelName": "models/gemini-2.5-flash",
        "options": {"temperature": 0.3, "maxOutputTokens": 2048}}, credentials=CRED_GEMINI),
    node("對話記憶", "@n8n/n8n-nodes-langchain.memoryBufferWindow", 1.4, [1080, 260],
         {"sessionIdType": "fromInput", "sessionKey": "={{ $json.sessionId }}", "contextWindowLength": 10}),
    tool("get_signal_summary", [1220, 260],
         "={{ $env.SIGNALS_BASE_URL }}/latest/summary.json", SUMMARY_DESC),
    tool("get_ticker_detail", [1360, 260],
         "={{ $env.SIGNALS_BASE_URL }}/latest/tickers/{{ $fromAI('code', '4 位數台股代號，例如 2330', 'string') }}.json",
         DETAIL_DESC),
    tool("get_realtime_quote", [1500, 260],
         "=https://mis.twse.com.tw/stock/api/getStockInfo.jsp?json=1&delay=0&ex_ch=tse_{{ $fromAI('code', '4 位數台股代號，例如 2330', 'string') }}.tw%7Cotc_{{ $fromAI('code', '4 位數台股代號，例如 2330', 'string') }}.tw",
         QUOTE_DESC),
    node("整理回覆", "n8n-nodes-base.code", 2, [1500, -60],
         {"mode": "runOnceForEachItem", "jsCode": CODE_FORMAT}),
    node("降級回覆", "n8n-nodes-base.code", 2, [1500, 120],
         {"mode": "runOnceForEachItem", "jsCode": CODE_FALLBACK}),
    node("LINE Reply", "n8n-nodes-base.httpRequest", 4.2, [1740, 0], {
        "method": "POST", "url": "https://api.line.me/v2/bot/message/reply",
        "authentication": "genericCredentialType", "genericAuthType": "httpHeaderAuth",
        "sendBody": True, "specifyBody": "json",
        "jsonBody": "={{ JSON.stringify({ replyToken: $json.replyToken, messages: [{ type: 'text', text: $json.text }] }) }}",
        "options": {}}, credentials=CRED_LINE),
]


def main(*targets):
    return {"main": [[{"node": t, "type": "main", "index": 0} for t in targets]]}


connections = {
    "LINE Webhook": main("回應 200"),
    "回應 200": main("拆開 events"),
    "拆開 events": main("只留文字訊息"),
    "只留文字訊息": main("整理輸入"),
    "整理輸入": main("AI Agent", "顯示輸入中"),
    "AI Agent": {"main": [[{"node": "整理回覆", "type": "main", "index": 0}],
                          [{"node": "降級回覆", "type": "main", "index": 0}]]},
    "整理回覆": main("LINE Reply"),
    "降級回覆": main("LINE Reply"),
    "Gemini": {"ai_languageModel": [[{"node": "AI Agent", "type": "ai_languageModel", "index": 0}]]},
    "對話記憶": {"ai_memory": [[{"node": "AI Agent", "type": "ai_memory", "index": 0}]]},
}
for t in ["get_signal_summary", "get_ticker_detail", "get_realtime_quote"]:
    connections[t] = {"ai_tool": [[{"node": "AI Agent", "type": "ai_tool", "index": 0}]]}

wf = {"id": WORKFLOW_ID, "name": "LINE AI 小精靈", "nodes": nodes, "connections": connections,
      "settings": {"executionOrder": "v1"}, "active": False}
out = ROOT / "workflows/line-ai-sprite.json"
out.write_text(json.dumps(wf, ensure_ascii=False, indent=2))
print(f"寫入 {out}（{len(nodes)} 個節點）")
