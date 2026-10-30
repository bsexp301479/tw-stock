# 第 02 輪｜System Analyst：設計文件

- 撰寫日期：2026-10-30
- 輸入：`02-pm.md` 本輪範圍 B1-核心、P14、P16、P13、A2、P15（沿用 PM 編號）；`01-analyst.md`；第 1 輪 `03-design.md`（格式與 P5、A1 的設計決定）
- 依據：閱讀 `twstock/collectors/*.py`、`db.py`、`export.py`、`__main__.py`、`fetch.py`、`site/app.js`、`stock.js`、`app.css`、`tests/test_iter01.py`、README；查詢資料庫；2026-10-30 經 `fetch.request`（`RETRY_BACKOFF=()`，不重試）實測 6 個端點共 8 次請求（見附錄 A）；以實測回應＋資料庫日線寫原型程式，算出本文件所有預期數值。
- 本文件只描述設計，不含程式修改。程式碼片段是給 Programmer 的規格，寫法比照既有程式；**欄位名稱、資料表、判斷式、畫面文案請照本文件**，QA 會照著驗。

> **影響設計的兩個實測發現（PM 文件沒有預期到）**
> 1. **上櫃除權息日的官方漲跌是文字**（`除息`、`除權`、`除權息`），`clean_number` 解析成 NULL。資料庫有 704 筆（625 檔，集中在 6～8 月），所以「參考價 = 收盤 − 漲跌」**反推不到上櫃的除權息**，只能反推減資、面額變更（29 筆）。其中 47 筆跳空超過 10%（例：5386 青雲 7/20 −38%、5314 世紀 8/14 −74%），不還原就會重演 P12。→ 本設計**新增櫃買除權息計算結果表 `bulletin/exDailyQ`**（實測可用日期區間查詢，一年一次請求 1,341 筆）。上櫃反推只用來補減資、面額變更。
> 2. **上櫃前一日無成交時，官方漲跌不是相對最後收盤**（櫃買以最後揭示買賣價當參考價），反推會產生 1,155 筆假事件。→ 反推只在「前一個資料列有成交」時進行。

---

## 〇、變更總覽

### 檔案 × 項目對照表

| 檔案 | B1-核心 | P14 | P16 | P13 | A2 | P15 |
|---|---|---|---|---|---|---|
| `twstock/db.py` | 新表 `price_events` | | | | 新表 `insti_amount` | |
| `twstock/collectors/alerts.py` | `roc_date()` 支援 `115年09月02日` | | | | | |
| `twstock/collectors/events.py`（新檔） | 四個事件端點的解析、抓取、寫入 | | | | | |
| `twstock/collectors/daily.py` | | | | | `AMOUNT`、`parse_insti_amount`、`fetch_twse_insti_amount`、`merge_insti_amount`；`collect_for_date` 支援 `AMOUNT` | |
| `twstock/collectors/history.py` | | | | | `AMOUNT` 資料集 | |
| `twstock/__main__.py` | 新指令 `events`；`collect` 加呼叫；docstring | | | | `history --only amount`；`collect` 加呼叫；docstring | |
| `twstock/export.py` | `_price_events`、`_adj_factors`；個股 `ev`；`h52`／`l52` 用還原價；未對到事件的印出 | `_changes`、`_side`；`prices.ch`、`latest` 的 `ch`／`p`／`rel`、漲跌家數 | `_cap_event`；個股 `capchg` | | `_insti_official`；`latest.insti_official`、`latest.insti_otc` | |
| `site/stock.js` | `adjFactors()`、`aggregate()` 加還原、「還原／原始」切換、事件標記、資訊列事件內容、52 週副標、量與法人標「未還原」 | 資訊列「相對 MM/DD 收盤」、標頭說明 | 本益比、殖利率卡副標 | `renderSignals()` 改寫、標題加週期 | | |
| `site/app.js` | | `pctCell()` 的 tooltip | | | `instiCard()`、`minibars()`，取代今日頁三大法人卡 | `indexCard()` 底行 |
| `site/app.css` | `.ev-note` | `.rel` | | | `.insti` 手機全寬 | |
| `tests/test_iter02.py`（新檔） | 民國日期、事件解析、事件對應、還原係數 | 三分支、漲跌家數 | 近期規則 | （前端，以瀏覽器驗） | 金額解析、匯總與連續天數 | |
| `README.md` | 見第七節清單 | 同左 | 同左 | | 同左 | |

### 建議實作順序

PM 要求兩個補抓不要同時跑：先跑事件（約 40 秒），再跑 A2（約 4 分鐘）。

| 步驟 | 內容 | 驗證 |
|---|---|---|
| 1 | `db.py` 兩張新表 → `python3 -m twstock setup-db`（執行兩次） | T-B1-2 |
| 2 | `alerts.roc_date`、新檔 `events.py`、`__main__.py` 的 `events` 指令與 `collect` 呼叫 → 執行 `python3 -m twstock events --start 2025-10-30 --end 2026-10-30` | T-B1-1（解析部分）、T-B1-3、T-B1-4 |
| 3 | `daily.py`、`history.py`、`__main__.py` 的 A2 部分 → 執行 `python3 -m twstock history --start 2026-07-31 --end 2026-10-30 --only amount`（可在步驟 4 進行時於背景跑） | T-A2-1、T-A2-2 |
| 4 | `export.py`：B1 → P14 → P16 → A2（同一個迴圈，一起改） | `python3 tests/test_iter02.py`、T-B1-5、T-B1-6、T-P14-2、T-P14-3 |
| 5 | `stock.js`：B1 → P14 → P16 → P13；`app.js`：P14 → A2 → P15；`app.css` | 瀏覽器 T-* |
| 6 | README、`__main__.py` docstring；`python3 -m twstock export`；`serve --port 8001 --no-browser` 自測；關閉伺服器 | 全部 T-*、第七節清單 |

> 工作量評估：B1 新增一個約 90 行的收集器、export 約 80 行、stock.js 約 60 行；A2 約 50＋40＋40 行；P14／P16／P13／P15 各 10～40 行。可在一個工作階段完成，**不需要延後 P15 或 A2 的 20 日走勢**。

### 共通約定

- 日期一律以 `YYYY-MM-DD` 字串匯出，畫面用 `md()`。本輪新增的日期（事件生效日 `ev[].d`、相對日 `rel`、官方法人資料日 `insti_official.date`）都帶自己的欄位，**不與 `date`、`flow_date` 混用**。
- 「資料日」= `latest.json` 的 `date`（Python 端 `latest_date`）。
- 新的收集步驟失敗一律 `except FetchError` 印 `⚠️` 後繼續，不影響已寫入的當日行情（比照 `collect_tpex_index`）。解析一律檢查欄位存在、列長度足夠，缺漏時略過該列。
- 外部請求一律經過 `fetch.request`。

---

## B1-核心. 除權息／減資／面額變更：還原 K 線與 52 週高低、事件標記（優先 1，解決 P12）

### B1-1 對應驗收條件（PM 原文，SA 修訂處標 ★）

1. `setup-db` 建立事件表，重複執行不報錯。
2. 補抓 2025-10-30～2026-10-30 後，事件表至少包含：6669 2026-09-02 權 7,800 → 2,614.99；8422 2025-11-17 面 250 → 25；6949 2026-09-07 面 1,490 → 74.5；2832 2025-11-03 減 36 → 47.14。★ `TWT49U` 2026/08～09 寫入筆數 = **208**（回應 301 筆扣掉 ETF、受益證券等 93 筆；208 檔都在 `stocks` 表）。重跑不產生重複。
3. 6669：52 週高 **2,875**（9/2），副標「還原權值」；9/1→9/2 沒有 −66% 缺口；9/2 有「權」標記，資訊列「除權　前收 7,800　參考價 2,614.99」。
4. ★ 5904：52 週高 **92.30**（8/12）、52 週低 **37.77**（2026-01-27，PM 原寫 39.25；差異來自 7/16 除息，見 B1-5 計算過程）；3086：52 週高 **47.50**（4/23）、52 週低 **20.05**（1/9）。5904 的 7/16「息」、8/10「股本變動」，3086 的 4/20「股本變動」有標記。
5. ★ 週／月線資訊列不再有假崩跌：5904 2026-08-10 那一週 **+9.72%**（原始 −89.03%）；3086 2026-04 月線 **+33.10%**（原始 −86.69%）。PM 原寫「絕對值 < 20%」，但 3086 四月是**真實上漲**（3/31 收 290 → 4/30 收 38.60，相當於分割前 386，+33.1%），驗收改為「等於本文件數值，且與日線還原價一致」。
6. 切換「原始」後 K 線開高低收與修改前完全相同，重新整理保留選擇；所有股票最新收盤不變。
7. 2330 還原 MA60 = 2,427.82、原始 2,431.58，相差 0.15%（< 2%）；四個除息日（2025-12-11、2026-03-17、06-11、09-16）有「息」標記。
8. 三個（★ 本設計為四個）事件端點失敗時，`collect` 照常寫入當日行情、印警告、回傳碼 0。
9. 匯出印出「上市官方漲跌 0、收盤 ≠ 前收、前一列有成交，但找不到事件」的筆數與前幾筆。★ 預估 **2 筆**：1435 2026-06-18、8105 2026-08-27，兩者都是**停止買賣後恢復交易**（前一個資料列分別是 4/28、8/18，中間沒有資料列），不是除權息（以 2025-10-30～2026-09-30 實測回應比對；10 月以補抓後為準）。
10. `tests/test_iter02.py` 涵蓋民國日期兩種格式、千分位、係數累乘（含 > 1）、上櫃反推（含前一列無成交）、空回應。
11. 個股 JSON 總大小增加 ≤ 5%（★ 目前實際為 28,220,699 bytes；`du` 顯示的 31 MB 是磁碟區塊）。預估 +0.1 MB（+0.4%）。
12. README 與 `__main__.py` 依第七節清單更新。

### B1-2 資料來源（2026-10-30 實測，回應欄位照抄）

| 來源代號 | 請求 | 回應位置 | 取用欄位 | 類型 |
|---|---|---|---|---|
| `TWT49U` | `GET https://www.twse.com.tw/rwd/zh/exRight/TWT49U?startDate=YYYYMMDD&endDate=YYYYMMDD&response=json` | 頂層 `fields`／`data`；`stat == "OK"` | `資料日期`（`115年09月02日`）、`股票代號`、`除權息前收盤價`、`除權息參考價`、`權/息`（`息`／`權`／`權息`） | 照 `權/息` |
| `TWTAUU` | `GET https://www.twse.com.tw/rwd/zh/reducation/TWTAUU?startDate=&endDate=&response=json` | 同上 | `恢復買賣日期`（`114/11/03`）、`股票代號`、`停止買賣前收盤價格`、`恢復買賣參考價` | `減` |
| `TWTB8U` | `GET https://www.twse.com.tw/rwd/zh/change/TWTB8U?startDate=&endDate=&response=json` | 同上 | 同 `TWTAUU` | `面` |
| `TPEX_EX`（★新增） | `POST https://www.tpex.org.tw/www/zh-tw/bulletin/exDailyQ`，form：`startDate=YYYY/MM/DD`、`endDate=YYYY/MM/DD`、`response=json` | `tables[]` 中 `fields` 含 `代號` 的表 | `除權息日期`（`115/07/09`）、`代號`、`除權息前收盤價`、`除權息參考價`、`權/息`（`除息`／`除權`／`除權息`，去掉「除」） | 照 `權/息` |

實測重點：

- `TWT49U` 2026/09 一個月 109 筆（息 90、權息 12、權 7），其中 51 筆是 ETF 等非一般股票；`20251030～20260831` **10 個月一次查詢成功**（1,321 筆）。數字含千分位（`7,800.00`）。
- `TWTAUU`、`TWTB8U` 一年一次查詢成功，20 筆、3 筆。`TWTAUU` 的 `除權參考價` 全部是 `--`。**決定：一律用 `恢復買賣參考價`**（恢復買賣當天的實際基準，已包含同時除權的影響）。
- `TPEX_EX` 2026/07 一個月 318 筆；`2025/10/30～2026/10/30` **一年一次查詢成功**（1,341 筆）。代號欄含 `00950B` 等債券 ETF，要過濾。名稱欄有尾端空白。
- **事件日可能是休市日**：2026-07-10 臨時休市，`TWT49U`、`TPEX_EX` 的除權息日期仍是 7/10，實際生效在 7/13（上市 2008、3034 等 9 檔 7/13 官方漲跌已相對參考價，例：2008 收 29.30、漲跌 +0.45 = 29.30 − 參考價 28.85）。
- 空回應：`TWT49U` 等 `stat` 不是 `OK` 時沒有 `fields`；`TPEX_EX` 的 `data` 為空陣列。兩者都回傳 `[]`。

**上櫃反推（不打端點，匯出時計算）**：參考價 = 收盤 − 官方漲跌，只在「前一個資料列有成交、官方漲跌有數值」時計算；≠ 前收時視為一次事件，類型 `調`（畫面顯示「股本變動」）。實測 29 筆，全部是減資、面額變更或其他參考價調整（5904、3086、8937、4747、8932、3152、4950…）。

**選擇：上櫃反推事件「匯出時即時計算」，不寫入事件表。** 理由：(1) 反推完全由 `daily_prices` 決定，補抓或修正日線後自動一致，不需維護第二份資料；(2) 上櫃除權息已改由 `TPEX_EX` 寫入事件表，A9／B6 需要的股利事件已經在表內，反推只剩 29 筆減資類事件；(3) 前端拿到的 `ev` 格式與官方事件相同。

### B1-3 資料庫（`db.py` 的 `DDL`，放在 `stock_alerts` 之後、索引之前）

```sql
-- 價格調整事件（官方）：除權息、減資、面額變更。上櫃的減資類事件在匯出時由日線反推，不存表
IF OBJECT_ID('price_events') IS NULL
CREATE TABLE price_events (
    id          INT IDENTITY(1,1) PRIMARY KEY,
    stock_id    INT           NOT NULL REFERENCES stocks(stock_id),
    event_date  DATE          NOT NULL,   -- 官方日期（除權息日／恢復買賣日），可能是休市日
    event_type  NVARCHAR(4)   NOT NULL CHECK (event_type IN (N'息', N'權', N'權息', N'減', N'面')),
    prev_close  DECIMAL(10,2) NOT NULL,   -- 除權息前收盤價／停止買賣前收盤價格
    ref_price   DECIMAL(10,2) NOT NULL,   -- 除權息參考價／恢復買賣參考價
    source      NVARCHAR(10)  NOT NULL,   -- TWT49U / TWTAUU / TWTB8U / TPEX_EX
    created_at  DATETIME      NOT NULL DEFAULT GETDATE(),
    CONSTRAINT UQ_price_events UNIQUE (stock_id, event_date, source)
)
```

- MERGE 鍵：`(stock_id, event_date, source)`；MATCHED 更新 `event_type`、`prev_close`、`ref_price`。
- `setup_database()` 的完成訊息加上 `price_events`、`insti_amount`。
- 唯一鍵已涵蓋查詢，不另建索引（全表約 2,000 筆／年）。

### B1-4 收集流程

**`alerts.py` `roc_date()`**：第一行改為

```python
s = str(s or "").strip().replace("年", "/").replace("月", "/").replace("日", "")
```

docstring 改為「民國日期 1151029、115/10/29 或 115年10月29日 → date」。第 1 輪測試不受影響。

**新檔 `twstock/collectors/events.py`**

```python
"""
價格調整事件：證交所除權息（TWT49U）、減資（TWTAUU）、面額變更（TWTB8U）、櫃買除權息（exDailyQ）。
四個端點都可用日期區間查詢；寫入 price_events（MERGE，可重跑）。上櫃減資類事件在匯出時由日線反推。
"""
from datetime import timedelta

from .. import db
from ..fetch import FetchError, clean_number, is_valid_stock_code, request
from .alerts import roc_date

EVENT_TYPES = ("息", "權", "權息", "減", "面")
CHUNK_DAYS = 183      # 每次查詢的日期區間（實測 TWT49U 10 個月、櫃買 1 年一次可查；保守取半年）
LOOKBACK_DAYS = 7     # 每日 collect 往回查的天數，補抓晚公告或前幾天漏抓的事件

# 來源：(方法, 網址, 日期參數格式, (日期欄, 代號欄, 前收欄, 參考價欄, 類型欄), 固定類型)
_SOURCES = {
    "TWT49U": ("GET", "https://www.twse.com.tw/rwd/zh/exRight/TWT49U", "%Y%m%d",
               ("資料日期", "股票代號", "除權息前收盤價", "除權息參考價", "權/息"), None),
    "TWTAUU": ("GET", "https://www.twse.com.tw/rwd/zh/reducation/TWTAUU", "%Y%m%d",
               ("恢復買賣日期", "股票代號", "停止買賣前收盤價格", "恢復買賣參考價", None), "減"),
    "TWTB8U": ("GET", "https://www.twse.com.tw/rwd/zh/change/TWTB8U", "%Y%m%d",
               ("恢復買賣日期", "股票代號", "停止買賣前收盤價格", "恢復買賣參考價", None), "面"),
    "TPEX_EX": ("POST", "https://www.tpex.org.tw/www/zh-tw/bulletin/exDailyQ", "%Y/%m/%d",
                ("除權息日期", "代號", "除權息前收盤價", "除權息參考價", "權/息"), None),
}


def parse_events(source: str, fields, rows) -> list:
    """官方事件表 → 寫入用 dict；非一般股票、日期或價格無法解析、類型不明的列略過；欄位缺漏回傳 []。"""
    names, fixed = _SOURCES[source][3], _SOURCES[source][4]
    idx = {f: i for i, f in enumerate(fields or [])}
    need = [n for n in names if n]
    if not all(n in idx for n in need):
        return []
    out = []
    for row in rows or []:
        if len(row) <= max(idx[n] for n in need):
            continue
        code, d = str(row[idx[names[1]]]).strip(), roc_date(row[idx[names[0]]])
        prev, ref = clean_number(row[idx[names[2]]]), clean_number(row[idx[names[3]]])
        kind = fixed or str(row[idx[names[4]]]).strip().lstrip("除")     # 櫃買為「除權息」→「權息」
        if not is_valid_stock_code(code) or d is None or not prev or not ref or kind not in EVENT_TYPES:
            continue
        out.append({"stock_code": code, "event_date": d.isoformat(), "event_type": kind,
                    "prev_close": prev, "ref_price": ref, "source": source})
    return out


def fetch_events(source: str, start, end) -> list:
    method, url, fmt = _SOURCES[source][:3]
    form = {"startDate": f"{start:{fmt}}", "endDate": f"{end:{fmt}}", "response": "json"}
    data = request(method, url, **({"params": form} if method == "GET" else {"data": form}))
    if not isinstance(data, dict):
        raise FetchError(f"事件回應格式不符：{source}")
    if source == "TPEX_EX":
        data = next((t for t in data.get("tables", []) if "代號" in (t.get("fields") or [])), {})
    return parse_events(source, data.get("fields"), data.get("data"))


def collect_events(start, end) -> int:
    """[start, end] 依 CHUNK_DAYS 切段，四個端點全部抓完才寫入；只寫入 stocks 表已有的股票。"""
    rows, s = [], start
    while s <= end:
        e = min(end, s + timedelta(days=CHUNK_DAYS - 1))
        for source in _SOURCES:
            rows += fetch_events(source, s, e)
        s = e + timedelta(days=1)
    # 同鍵只留一筆，避免 MERGE 同一列被更新兩次
    rows = list({(r["stock_code"], r["event_date"], r["source"]): r for r in rows}.values())
    if rows:
        conn = db.connect()
        try:
            conn.cursor().execute("""
                MERGE price_events AS t
                USING (
                    SELECT st.stock_id, j.*
                    FROM OPENJSON(?) WITH (
                        stock_code NVARCHAR(10), event_date DATE, event_type NVARCHAR(4),
                        prev_close DECIMAL(10,2), ref_price DECIMAL(10,2), source NVARCHAR(10)
                    ) AS j
                    JOIN stocks st ON st.stock_code = j.stock_code
                ) AS s
                ON t.stock_id = s.stock_id AND t.event_date = s.event_date AND t.source = s.source
                WHEN MATCHED THEN UPDATE SET
                    event_type = s.event_type, prev_close = s.prev_close, ref_price = s.ref_price
                WHEN NOT MATCHED THEN
                    INSERT (stock_id, event_date, event_type, prev_close, ref_price, source)
                    VALUES (s.stock_id, s.event_date, s.event_type, s.prev_close, s.ref_price, s.source);
            """, db.to_json(rows))
            conn.commit()
        finally:
            conn.close()
    print(f"  📌 除權息／減資／面額變更事件：{len(rows)} 筆（{start} ～ {end}）")
    return len(rows)
```

**`__main__.py`**

- 檔頭：`from datetime import date, datetime, timedelta`。
- `cmd_collect`：在 `collect_alerts()` 的 `try` 區塊之後、產業鏈之前加（A2 的呼叫也放這裡，見 A2-4）：

```python
            try:
                collect_events(d - timedelta(days=LOOKBACK_DAYS), d)
            except FetchError as e:
                print(f"  ⚠️  除權息／減資事件抓取失敗，下次執行會再補：{e}")
```

  並在函式開頭 `from .collectors.events import LOOKBACK_DAYS, collect_events`。
- 新指令（放在 `revenue` 之後）：

```python
def cmd_events(args):
    from .collectors.events import collect_events
    from .fetch import FetchError
    try:
        collect_events(args.start, args.end or date.today())
    except FetchError as e:
        print(f"\n❌ {e}\n   稍後用同樣的指令重跑即可（MERGE 覆寫，不會重複）")
        return 1
    return 0
```

```python
    s = sub.add_parser("events", help="補抓除權息／減資／面額變更事件（還原價格用）")
    s.add_argument("--start", type=_date, required=True)
    s.add_argument("--end", type=_date, help="預設今天")
    s.set_defaults(fn=cmd_events)
```

**補抓指令與時間**（先跑這個，再跑 A2）：

```bash
python3 -m twstock events --start 2025-10-30 --end 2026-10-30
```

- 366 天切成 2 段 × 4 個端點 = **8 次請求**；證交所 6 次 × 3.5 秒＋櫃買 2 次 × 3 秒 ≈ **30～40 秒**。
- 全部抓完才寫入；中途被封會印 `❌` 並回傳 1，30 分鐘後用同一指令重跑。
- 每日 `collect` 增加 4 次請求（約 15 秒）。
- **日後往前補抓日線（B1-前置-延伸）時，必須用同一區間執行 `events`**，否則補抓區段不會還原（寫進 README）。

### B1-5 還原計算與匯出（`export.py`）

#### 還原公式（向後還原：最新收盤不變，調整歷史價格）

每個事件 e 的係數 **f = 參考價 ÷ 事件前收盤**。各類事件的參考價由官方算好，本系統不自行計算股利，只用比值：

| 類型 | 官方參考價的意義 | f | 例 |
|---|---|---|---|
| 息（現金股利 D） | 前收 − D | (P − D) ÷ P < 1 | 2330 2026-09-16：2,377.99 ÷ 2,385 = 0.99706 |
| 權（股票股利，每股配 s 股；含現金增資認購） | P ÷ (1 + s) | < 1 | 6669 2026-09-02：2,614.99 ÷ 7,800 = 0.33526 |
| 權息 | (P − D) ÷ (1 + s) | < 1 | 5511 2026-07-09：63.48 ÷ 79.70 = 0.79649 |
| 減（減資，彌補虧損或退還股款） | 依換發比率重算，通常**高於**前收 | 常 > 1 | 2832 2025-11-03：47.14 ÷ 36 = 1.30944 |
| 面（面額變更／分割） | P × 新面額 ÷ 舊面額 | 1/10、1/20… | 6949 2026-09-07：74.5 ÷ 1,490 = 0.05 |
| 調（上櫃反推） | 收盤 − 官方漲跌 | 任意 | 3152 2026-06-30：360 ÷ 208 = 1.73077 |

**累乘**：第 i 個資料列的還原係數 `af[i]` = 生效列索引 > i 的所有事件係數的乘積；**事件生效當天及之後為 1**（當天的價格已是除權息後的價格）。還原價 = 原始價 × `af[i]`，開高低收都乘；成交量、法人張數**不還原**（B1-延伸）。

例（6669）：9/2 之前的價格乘 0.33526；6/22 之前再乘 0.97185，即 0.32582。3/31 原始最低 3,290 → 還原 1,071.94。

**異常係數防護**：f 不在 **0.02～20** 之間的事件不採用，匯出時印警告。★ PM 建議 0.05～20，但 6949 面額變更的係數正好是 0.05（1:20 分割），邊界太緊，改為 0.02。

#### 兩條路徑的合併（`_price_events`）

1. **官方事件**（事件表，兩市場）：依日期排序，以 `bisect_left` 找「事件日當天或之後第一個資料列」為生效列 i。
   - i = 0（第一筆資料之前，例：2832 減資 11/03 就是它的第一筆資料）或 i = 列數（最後一筆之後）→ 略過，不影響任何價格。
   - 同一列有兩筆官方事件 → 只取一筆，優先 `TWTAUU`／`TWTB8U`（恢復買賣參考價已含同日除權），否則取日期較早的那筆。
2. **上櫃反推**（只有 `TPEx`）：i ≥ 1、該列與前一列都有成交、官方漲跌有數值、`round(收盤 − 漲跌, 2)` 與前一列收盤差 ≥ 0.005 → 事件 `調`。**同一列已有官方事件時以官方為準**（例：3467 7/13 反推 58.30 與櫃買 7/10 除息參考價相同）。
3. 兩者合併後依 i 排序；每列最多一筆事件。

**避免把一般漲跌停、無成交誤判為事件**：

| 情況 | 為什麼不會被當成事件 |
|---|---|
| 上市漲跌停、大漲大跌 | 上市不做反推，事件只來自官方端點 |
| 上市不比價（官方漲跌 0、收盤 ≠ 前收） | 不視為事件；對不到官方事件的只列入「未對到」清單（P14 分支 3） |
| 上櫃漲跌停 | 官方漲跌 = 收盤 − 前收，反推參考價 = 前收，不產生事件 |
| 上櫃前一日無成交 | 櫃買改用最後揭示買賣價當參考價（實測 1,155 筆差 < 2%），**前一列無成交時不反推** |
| 上櫃除權息日（漲跌欄是文字） | 漲跌為 NULL 不反推，事件改由 `TPEX_EX` 提供 |
| 休市日事件（7/10） | 對應到 7/13；7/13 若也被反推，同一列以官方為準 |

#### 匯出

在個股迴圈前載入事件（放在 `alerts` 查詢之後）：

```python
events = defaultdict(list)
for code, d, t, p, r, src in cur.execute("""
    SELECT s.stock_code, e.event_date, e.event_type, e.prev_close, e.ref_price, e.source
    FROM price_events e JOIN stocks s ON s.stock_id = e.stock_id
    ORDER BY s.stock_code, e.event_date"""):
    events[code].append({"d": d, "t": t, "p": float(p), "r": float(r), "src": src})
```

新增常數與純函式（`from bisect import bisect_left`）：

```python
ADJ_MIN, ADJ_MAX = 0.02, 20     # 還原係數合理範圍；超出視為資料錯誤，不採用
_SRC_RANK = {"TWTAUU": 0, "TWTB8U": 0}   # 同一列有多筆官方事件時優先（恢復買賣參考價已含同日除權）


def _price_events(d_, c, ch, market, official):
    """
    個股的價格調整事件（舊到新）：[{i, d, t, p, r}]。i = 生效的資料列索引（事件日當天或之後第一列），
    d = 該列日期字串，t = 類型，p = 事件前收盤，r = 參考價。另回傳因係數不合理而略過的 [(日期, 係數)]。
    官方事件在第一筆資料之前或最後一筆之後的略過；上櫃另以「收盤 − 官方漲跌」反推（類型「調」），
    只在前一列有成交、漲跌有數值時計算，與官方事件同一列時以官方為準。
    """
    at, bad = {}, []

    def add(i, t, p, r):
        f = r / p
        if ADJ_MIN <= f <= ADJ_MAX:
            at[i] = {"i": i, "d": str(d_[i]), "t": t, "p": p, "r": r}
        else:
            bad.append((str(d_[i]), round(f, 4)))

    for e in sorted(official, key=lambda e: (e["d"], _SRC_RANK.get(e["src"], 1))):
        i = bisect_left(d_, e["d"])
        if 0 < i < len(d_) and i not in at:
            add(i, e["t"], e["p"], e["r"])
    if market == "TPEx":
        for i in range(1, len(d_)):
            if i in at or c[i] is None or c[i - 1] is None or ch[i] is None:
                continue
            p, r = float(c[i - 1]), round(float(c[i]) - float(ch[i]), 2)
            if abs(r - p) >= 0.005:
                add(i, "調", p, r)
    return [at[i] for i in sorted(at)], bad


def _adj_factors(n, ev):
    """每個資料列的還原係數 = 該列之後所有事件（參考價 ÷ 前收）的乘積；事件當天與之後為 1。"""
    af, k, j = [1.0] * n, 1.0, len(ev) - 1
    for i in range(n - 1, -1, -1):
        while j >= 0 and ev[j]["i"] > i:
            k *= ev[j]["r"] / ev[j]["p"]
            j -= 1
        af[i] = k
    return af
```

個股迴圈內（取代原本 `chs` 的計算，P14 的 `_changes` 見下一節）：

```python
ev, bad = _price_events(d_, c, ch, info["market"], events.get(code, []))
af = _adj_factors(len(d_), ev)
chs, rel, miss = _changes(d_, c, ch, info["market"], ev)
bad_all += [(code, *x) for x in bad]
miss_all += [(code, x) for x in miss]
n_ev += len(ev); n_inferred += sum(e["t"] == "調" for e in ev)
```

個股 JSON 新增（放在 `"prices"` 之後）：

| 欄位 | 型別 | 單位 | 範例 | 說明 |
|---|---|---|---|---|
| `ev` | object[] | | `[{"d":"2026-06-22","t":"息","p":5130,"r":4985.6},{"d":"2026-09-02","t":"權","p":7800,"r":2614.99}]` | 舊到新；**一律輸出**，沒有事件為 `[]` |
| `ev[].d` | string | 日期 | `"2026-07-13"` | **生效日** = 事件日當天或之後第一個資料列的日期（7/10 休市的事件為 7/13）；前端以此還原、標記 |
| `ev[].t` | string | | `"權"` | `息`／`權`／`權息`／`減`／`面`／`調` |
| `ev[].p` | number | 元 | `7800` | 事件前收盤（官方值；`調` 為前一列收盤） |
| `ev[].r` | number | 元 | `2614.99` | 參考價 |

寫法：`"ev": [{k: e[k] for k in ("d", "t", "p", "r")} for e in ev]`。

`latest.json` 的 `h52`／`l52` 改用還原價（取代原本的 `w52`）：

```python
w52 = [(float(h[i]) * af[i], float(l[i]) * af[i]) for i in range(len(d_))
       if d_[i] >= w52_start and h[i] is not None and l[i] is not None]
...
"h52": _f(max(x[0] for x in w52)) if w52 else None,
"l52": _f(min(x[1] for x in w52)) if w52 else None,
```

迴圈結束後（`conn.close()` 之後的匯出完成訊息前）印出：

```python
print(f"  📌 還原事件 {n_ev} 筆（上櫃反推 {n_inferred} 筆）")
if bad_all:
    print(f"⚠️  還原係數超出 {ADJ_MIN}～{ADJ_MAX}，未採用 {len(bad_all)} 筆：" +
          "、".join(f"{c} {d}（{f}）" for c, d, f in bad_all[:10]))
if miss_all:
    print(f"⚠️  上市官方漲跌 0、收盤 ≠ 前收，但找不到除權息／減資事件 {len(miss_all)} 筆（維持「不比價」）：" +
          "、".join(f"{c} {d}" for c, d in miss_all[:10]))
```

**檔案大小**：一年約 1,700 筆事件 × 約 47 bytes ＋ 每檔 `"ev":[]` 8 bytes × 1,999 ≈ **0.1 MB（+0.4%）**，`capchg`（P16）約 40 檔 × 35 bytes 可忽略。符合驗收 11（≤ 5%）。不採用「另存還原價陣列」：開高低收四個陣列會使個股 JSON 增加約 35%。

**預期數值**（以實測回應＋資料庫日線計算；QA 以此對照）：

| 代號 | 事件（生效日 類型 前收→參考價） | 52 週高 | 52 週低 | 原始（修改前） |
|---|---|---|---|---|
| 6669 | 2026-06-22 息 5,130→4,985.6；2026-09-02 權 7,800→2,614.99 | **2,875**（9/2，原始 2,875 × 1） | **1,071.94**（3/31，3,290 × 0.32582） | 7,800／1,770 |
| 5904 | 2026-07-16 息 677→651.5；2026-08-10 調 720→72 | **92.30**（8/12） | **37.77**（2026-01-27，392.5 × 0.96233 × 0.1） | 767／68.2 |
| 3086 | 2026-04-20 調 325→32.5 | **47.50**（4/23） | **20.05**（1/9，200.5 × 0.1） | 337.5／24.9 |
| 2330 | 2025-12-11、2026-03-17、06-11、09-16 息（前收→參考價 1,505→1,499.99、1,845→1,838.99、2,255→2,248.99、2,385→2,377.99） | **2,590**（10/06） | **1,358.31**（2025-11-24，1,375 × 0.98786） | 2,590／1,375 |
| 2317 | 2026-07-02 息 248→240.82 | **304.91**（6/03） | **182.07**（3/31） | 314／187.5 |

### B1-6 畫面（`stock.js`）

#### 還原係數與聚合

新增（放在 `aggregate` 之前）：

```js
// 每天的還原係數 = 該日之後所有事件（參考價 ÷ 前收）的乘積；事件生效日與之後為 1（向後還原，最新收盤不變）
function adjFactors(dates, ev) {
  const af = new Array(dates.length).fill(1);
  let k = 1, j = ev.length - 1;
  for (let i = dates.length - 1; i >= 0; i--) {
    while (j >= 0 && ev[j].d > dates[i]) { k *= ev[j].r / ev[j].p; j--; }
    af[i] = k;
  }
  return af;
}
const EV_LABEL = { '息': '除息', '權': '除權', '權息': '除權息', '減': '減資', '面': '面額變更', '調': '股本變動' };
```

`aggregate(data, mode)` 改為 `aggregate(data, mode, adj)`：

```js
function aggregate(data, mode, adj) {
  const P = data.prices, I = data.insti, ev = data.ev || [];
  const af = adj ? adjFactors(P.d, ev) : P.d.map(() => 1);
  const evAt = Object.fromEntries(ev.map(e => [e.d, e]));
  const rows = [];
  let prevC = null, lastD = null;
  P.d.forEach((d, i) => {
    ...（inst 不變）
    const e = evAt[d] ? [evAt[d]] : [];
    if (P.c[i] != null && P.o[i] != null) {
      const k = af[i], ch = P.ch?.[i] ?? null;
      // P14：上市前一個資料列無成交、中間沒有事件 → 漲跌相對最後成交日
      const rel = data.market === 'TWSE' && i && P.c[i - 1] == null && lastD
        && !ev.some(x => x.d > lastD && x.d <= d) ? lastD : null;
      rows.push({ d, o: P.o[i] * k, h: P.h[i] * k, l: P.l[i] * k, c: P.c[i] * k, v: P.v[i],
        ch: ch == null ? null : ch * k,                                         // 還原後的漲跌（元）
        pc: ch == null || P.c[i] === ch ? null : ch / (P.c[i] - ch) * 100,       // 漲跌幅以原始價計算（不受係數影響）
        rel, ev: e, ...inst, nt: false });
      prevC = P.c[i] * k; lastD = d;
    } else if (prevC != null) {
      rows.push({ d, o: prevC, h: prevC, l: prevC, c: prevC, v: P.v[i] ?? 0, ch: null, pc: null, rel: null, ev: e, ...inst, nt: true });
    }
  });
  if (mode === '日') return rows;
  ...（週／月分組不變，另外合併事件）
    if (!g) out.set(key, { ...r, d: key, ev: [...r.ev] });
    else { ...; g.ev = g.ev.concat(r.ev); }
}
```

> 事件日當天：還原後漲跌 = (收盤 − 參考價) × af，正好等於「還原收盤 − 前一日還原收盤」，所以日線、週線、月線的漲跌口徑一致。

#### 「還原／原始」切換

`renderStock()`：

- 讀取：`const adjMode = localStore('kadj', '還原');`（比照 `kmode`）。
- K 線卡 `sec-h`，在 `kSeg` 之後插入 `${segHTML('adjSeg', [['還原', '還原'], ['原始', '原始']], adjMode)}`；渲染後設定 `$('#adjSeg').title = '還原：依除權息、減資、面額變更調整歷史價格，最新收盤不變。均線訊號與 52 週高低一律以還原價格計算';`。
- 繪圖集中到一個函式，日／週／月與還原／原始切換都呼叫它：

```js
  const draw = () => {
    const m = localStore('kmode', '日'), adj = localStore('kadj', '還原') === '還原';
    buildCharts(aggregate(data, m, adj), m);
    renderSignals(aggregate(data, m, true), m);     // P13：訊號一律用還原價
  };
  onSeg('kSeg', m => { localStore('kmode', null, m); document.querySelectorAll('#kSeg button').forEach(b => b.classList.toggle('on', b.dataset.v === m)); draw(); });
  onSeg('adjSeg', v => { localStore('kadj', null, v); document.querySelectorAll('#adjSeg button').forEach(b => b.classList.toggle('on', b.dataset.v === v)); draw(); });
  ...
  renderRevenue(data.revenue);
  draw();
```

- `buildCharts()` 末尾的 `renderSignals(C, ma5, …)` **刪除**（改由 `draw()` 呼叫）。

**MA、MACD 線條隨切換**（★ 與 PM 建議不同）：圖上的 MA5／20／60 與 MACD 以「目前顯示的價格」計算。理由：原始模式下若畫還原 MA，6669 9/2 之前的 K 棒在 7,800 附近、MA 在 2,600 附近，價格軸被拉開、均線脫離 K 棒，比假訊號更難讀。**技術面訊號卡與 52 週高低固定用還原價**，原始模式不會出現假訊號結論。

位置與版面：

- 桌機：`[日 週 月] [還原 原始] [回到最新] ……… 拖曳平移、滾輪縮放` 一行。
- 手機 375px：三組按鈕約 320px，放得下一行；「拖曳平移、滾輪縮放」換到第二行（`sec-h` 已有 `flex-wrap`）。

#### 事件標記與資訊列

`buildCharts()` 在 `kSer.setData(...)` 之後：

```js
  // 除權息、減資、面額變更標記（還原／原始都顯示）；週／月線同一根有多筆時合併文字
  kSer.setMarkers(raw.flatMap((r, i) => r.ev.length ? [{ time: T[i], position: 'belowBar', shape: 'arrowUp',
    color: css('--blue'), text: [...new Set(r.ev.map(e => e.t))].join('・') }] : []));
```

標記文字：`息`、`權`、`權息`、`減`、`面`、`調`。

`showLegend(i)`：

```js
    const chg = mode === '日' ? raw[i].ch : i ? C[i] - C[i - 1] : 0;
    const p = mode === '日' ? raw[i].pc : i ? chg / C[i - 1] * 100 : 0;
    ...
      (NT[i] ? '<span class="flat">無成交</span>'
        : chg == null ? '<span class="flat" title="官方未提供漲跌，且找不到對應的除權息、減資、面額變更事件">不比價</span>'
        : `<span class="${c}">${psgn(chg)} (${sgn(p)}%)</span>`) +
      (mode === '日' && raw[i].rel ? `<span class="muted">相對 ${md(raw[i].rel)} 收盤</span>` : '') +
      raw[i].ev.map(e => `<span class="ev-note"${e.t === '調' ? ' title="依櫃買官方漲跌反推的參考價調整（減資、面額變更等）"' : ''}>` +
        `${mode === '日' ? '' : md(e.d) + ' '}${EV_LABEL[e.t]}　前收 ${pfmt(e.p)}　參考價 ${pfmt(e.r)}</span>`).join('') +
      `<span>量 <b>${fmt(V[i])}</b> 張</span>` + ...
```

- 前收、參考價顯示**官方原始價格**（不乘係數），與券商公告一致。
- 例（6669 日線 9/2，還原模式）：`2026-09-02　開 … 收 2,610　-4.99 (-0.19%)　除權　前收 7,800　參考價 2,614.99　量 …`。

#### 指標卡與圖表標籤

- 52 週卡副標：`hlFrom ? hlSub + '，還原' : '還原權值'`（`hlSub` 為「自 YYYY/MM/DD」）。標籤文字不變（「52週高／52週低」或「區間高／區間低」）。
- 成交量標籤 `成交量（張）` → `成交量（張，未還原）`；法人標籤 `三大法人買賣超（張）` → `三大法人買賣超（張，未還原）`（PM 風險 4：6669 除權前的張數看起來偏少）。

CSS（`app.css`）：

```css
.ev-note{color:var(--blue)}
```

#### 無資料時

- `ev` 為空或舊快取沒有 `ev`：`data.ev || []`，沒有標記；「還原」與「原始」畫面相同，切換仍保留。
- 個股 JSON 沒有 `ev` 欄位（尚未重新匯出）：同上，不報錯。

### B1-7 邊界情況

| 情況 | 處理 |
|---|---|
| 事件日是休市日（7/10） | 生效日 = 下一個資料列（7/13）；`ev[].d` 匯出 7/13 |
| 事件在第一筆日線之前或當天（2832 11/03 是它的第一筆） | 略過，不輸出（事件表仍保存） |
| 事件日晚於最後一筆日線（例：當天行情尚未寫入） | 略過；下次匯出自動生效 |
| 事件生效當天無成交 | 係數照樣作用在之前的價格；下一個成交日的漲跌相對參考價（P14 分支 1） |
| 同一列多筆官方事件 | 優先減資／面額變更，其餘略過 |
| 係數 > 1（減資） | 正常累乘，之前的價格被調高（例 2832 ×1.309） |
| 係數 < 0.02 或 > 20 | 不採用，匯出印 ⚠️ |
| 上櫃停牌期間有「無成交」資料列，恢復交易當天 | 前一列無成交 → 不反推（可能漏掉減資事件，匯出不會發現；列入已知限制） |
| 上市停止買賣後恢復交易（1435、8105） | 不是事件；P14 分支 3「不比價」，列入未對到清單 |
| 端點回 HTML／被限流 | `request` 重試後丟 `FetchError`：`collect` 印 ⚠️ 繼續；`events` 指令回傳 1 |
| 端點欄位改名 | `parse_events` 回傳 `[]`，印「0 筆」；不丟 `KeyError` |
| `stocks` 表沒有的代號 | MERGE 的 JOIN 不寫入 |
| 日線往前補抓但沒有補事件 | 補抓區段不還原；README 提醒用同一區間執行 `events` |

### B1-8 測試案例

| 編號 | 步驟 | 預期結果 |
|---|---|---|
| T-B1-1 | `python3 tests/test_iter02.py`；`python3 tests/test_iter01.py` | 兩者都印「全部通過」；`test_roc_date`、`test_parse_events`、`test_price_events`、`test_adj_factors` 通過（附錄 B） |
| T-B1-2 | 連續執行 `python3 -m twstock setup-db` 兩次 | 不報錯；`python3 -c "from twstock import db;c=db.connect().cursor();print(c.execute(\"SELECT OBJECT_ID('price_events'), OBJECT_ID('insti_amount')\").fetchone())"` 兩個值都不是 None |
| T-B1-3 | `python3 -m twstock events --start 2025-10-30 --end 2026-10-30`，接著執行下方腳本 A | 指令印「📌 除權息／減資／面額變更事件：N 筆」（N ≈ 1,700）；腳本 A 印 `ok` |
| T-B1-4 | 記下 `SELECT COUNT(*) FROM price_events`，再執行一次 T-B1-3 的指令 | 筆數不變；腳本 A 的 `TWT49U` 8～9 月筆數仍為 208 |
| T-B1-5 | `python3 -m twstock export` 後執行腳本 B | 印 `ok`；匯出訊息含「📌 還原事件 N 筆（上櫃反推 29 筆）」（± 視當日新事件） |
| T-B1-6 | `#/stock/6669`，Console：`(()=>{const m=[...document.querySelectorAll('.metrics .stat')].find(e=>e.querySelector('.l').textContent==='52週高');return [m.querySelector('.v').textContent,m.querySelector('.s').textContent]})()` | `["2,875", "還原權值"]` |
| T-B1-7 | 同頁 Console：`(async()=>{const r=aggregate(await loadStock('6669'),'日',true),i=r.findIndex(x=>x.d==='2026-09-02');return [+(r[i].c/r[i-1].c-1).toFixed(4), r[i].ev[0].t, r.filter(x=>x.ev.length).map(x=>x.d)]})()` | `[-0.0019, "權", ["2026-06-22","2026-09-02"]]`（沒有 −66% 缺口）；畫面 6/22、9/2 的 K 棒下方有藍色「息」「權」標記 |
| T-B1-8 | 6669 日線，游標移到 2026/09/02 | 資訊列含「-4.99 (-0.19%)」與「除權　前收 7,800　參考價 2,614.99」 |
| T-B1-9 | `#/stock/5904`、`#/stock/3086` 看 52 週卡；Console：`(async()=>[(await loadStock('5904')).ev.map(e=>e.d+e.t),(await loadStock('3086')).ev.map(e=>e.d+e.t)])()` | 5904「92.3」「37.77」；3086「47.5」「20.05」；事件 `["2026-07-16息","2026-08-10調"]`、`["2026-04-20調"]`；畫面有對應標記，8/10 游標資訊列「股本變動　前收 720　參考價 72」 |
| T-B1-10 | Console：`(async()=>{const w=async(c,m,d,a)=>{const r=aggregate(await loadStock(c),m,a),i=r.findIndex(x=>x.d===d);return +((r[i].c/r[i-1].c-1)*100).toFixed(2)};return [await w('5904','週','2026-08-10',true),await w('3086','月','2026-04-01',true),await w('6669','週','2026-08-31',true),await w('5904','週','2026-08-10',false)]})()` | `[9.72, 33.1, 6.26, -89.03]`；切到週線、游標移到 5904 的 2026/08/10 那一週，資訊列為「+… (+9.72%)」 |
| T-B1-11 | 6669 按「原始」，再重新整理 | Console：`(async()=>{const d=await loadStock('6669'),r=aggregate(d,'日',false),P=d.prices;return r.filter(x=>!x.nt).every(x=>{const i=P.d.indexOf(x.d);return x.o===P.o[i]&&x.h===P.h[i]&&x.l===P.l[i]&&x.c===P.c[i]})})()` 為 `true`；重新整理後「原始」仍為選取狀態（`localStorage['tw.kadj']==='原始'`）；K 線 9/2 出現原始跳空；技術面訊號卡內容與「還原」時相同。測完按回「還原」 |
| T-B1-12 | 執行腳本 C（最新收盤不變） | 印 `ok` |
| T-B1-13 | `#/stock/2330`，Console：`(async()=>{const d=await loadStock('2330'),ma=r=>r.slice(-60).reduce((a,x)=>a+x.c,0)/60,a=ma(aggregate(d,'日',true)),b=ma(aggregate(d,'日',false));return [a.toFixed(2),b.toFixed(2),Math.abs(a/b-1)<0.02,d.ev.map(e=>e.d+e.t)]})()` | `["2427.82","2431.58",true,["2025-12-11息","2026-03-17息","2026-06-11息","2026-09-16息"]]` |
| T-B1-14 | 模擬事件與金額端點失敗（下方腳本 D） | 輸出依序有「✅ 寫入：TWSE …」、「⚠️  三大法人金額抓取失敗：模擬失敗」、「⚠️  除權息／減資事件抓取失敗，下次執行會再補：模擬失敗」、「✅ 匯出完成」；最後一行 `exit=0`；`daily_prices` 10/30 筆數與執行前相同 |
| T-B1-15 | `python3 -m twstock export` 的輸出 | 有「⚠️  上市官方漲跌 0、收盤 ≠ 前收，但找不到除權息／減資事件 N 筆」，預估 N = 2，含「1435 2026-06-18」「8105 2026-08-27」；PG 在 `04-dev.md` 記錄實際 N 與原因 |
| T-B1-16 | 執行腳本 E（大小） | 印出的比例 ≤ 0.05（預估約 0.004） |
| T-B1-17 | DevTools 375×812 開 `#/stock/6669` | 「日週月」「還原原始」「回到最新」不溢出；資訊列換行顯示事件內容 |

腳本 A（事件表內容）：

```bash
python3 - <<'EOF'
from twstock import db
c = db.connect().cursor()
rows = {(r[0], str(r[1])): r[2:] for r in c.execute("""
    SELECT s.stock_code, e.event_date, e.event_type, e.prev_close, e.ref_price, e.source
    FROM price_events e JOIN stocks s ON s.stock_id = e.stock_id""")}
exp = {("6669", "2026-09-02"): ("權", 7800, 2614.99, "TWT49U"), ("8422", "2025-11-17"): ("面", 250, 25, "TWTB8U"),
       ("6949", "2026-09-07"): ("面", 1490, 74.5, "TWTB8U"), ("2832", "2025-11-03"): ("減", 36, 47.14, "TWTAUU")}
for k, (t, p, r, src) in exp.items():
    got = rows[k]
    assert (got[0], float(got[1]), float(got[2]), got[3]) == (t, p, r, src), (k, got)
n = c.execute("SELECT COUNT(*) FROM price_events WHERE source='TWT49U' AND event_date BETWEEN '2026-08-01' AND '2026-09-30'").fetchone()[0]
assert n == 208, n
print("ok")
EOF
```

腳本 B（匯出的 52 週與事件）：

```bash
python3 - <<'EOF'
import json
S = json.load(open("site/data/latest.json"))["stocks"]
exp = {"6669": (2875, 1071.94), "5904": (92.3, 37.77), "3086": (47.5, 20.05), "2330": (2590, 1358.31), "2317": (304.91, 182.07)}
for code, (h, l) in exp.items():
    assert abs(S[code]["h52"] - h) < 0.011 and abs(S[code]["l52"] - l) < 0.011, (code, S[code]["h52"], S[code]["l52"])
ev = json.load(open("site/data/stocks/6669.json"))["ev"]
assert ev == [{"d": "2026-06-22", "t": "息", "p": 5130, "r": 4985.6}, {"d": "2026-09-02", "t": "權", "p": 7800, "r": 2614.99}], ev
print("ok")
EOF
```

腳本 C（最新收盤沒有被還原）：

```bash
python3 - <<'EOF'
import json
S = json.load(open("site/data/latest.json"))["stocks"]
for code, s in S.items():
    P = json.load(open(f"site/data/stocks/{code}.json"))["prices"]
    assert s["c"] == [x for x in P["c"] if x is not None][-1], code
print("ok")
EOF
```

腳本 D（失敗模擬；會重新抓 10/30 行情，約 1 分鐘）：

```bash
python3 -c "
import twstock.collectors.daily as d, twstock.collectors.events as e
from twstock.fetch import FetchError
def boom(*a, **k): raise FetchError('模擬失敗')
d.fetch_twse_insti_amount = boom; e.fetch_events = boom
from twstock.__main__ import main
raise SystemExit(main(['collect', '--date', '2026-10-30', '--no-revenue']))"; echo "exit=$?"
```

腳本 E（大小增量，基準為修改前 28,220,699 bytes）：

```bash
python3 - <<'EOF'
import glob, json
dump = lambda o: len(json.dumps(o, ensure_ascii=False, separators=(",", ":")).encode())
add = 0
for f in glob.glob("site/data/stocks/*.json"):
    s = json.load(open(f))
    add += dump({"ev": s["ev"]}) - 1                      # 去掉大括號、加一個逗號
    if "capchg" in s:
        add += dump({"capchg": s["capchg"]}) - 1
print(add, round(add / 28220699, 4))
EOF
```

---

## P14. 不比價日與前一日無成交的漲跌改為正確值（優先 2，含 P11）

### P14-1 對應驗收條件

1. 10/30 的 1213 大飲在首頁／排行／自選／個股頁顯示 **−0.07（−0.94%）**，看得到「相對 10/28 收盤」說明。另外 4 檔：7732 **+0.10（+0.30%）**、8481 **+0.20（+0.50%）**、8487 **−1.40（−2.07%）**、9918 **−0.05（−0.12%）**。
2. 10/30 上市漲跌家數由「漲 92、跌 942、平 51」變為 **漲 94、跌 945、平 46**，合計 1,085 不變；上櫃 127／693／56 不變。
3. 2317 日線 2026-07-02 資訊列 **−1.82（−0.76%）**（240.82 為 `TWT49U` 參考價）；6669 的 9/2 **−4.99（−0.19%）**。
4. 單元測試涵蓋三種分支與漲跌家數歸類。
5. README 依第七節更新；`__main__.py` 不需為本項修改。

### P14-2 資料來源／P14-3 資料庫／P14-4 收集流程

使用 B1 的事件（官方＋上櫃反推）與既有 `daily_prices`。無新端點、無新表。

### P14-5 匯出（`export.py`）

**判斷式**（每個有成交的資料列 i；j = 前一個有成交的資料列）：

| 順序 | 條件 | 漲跌 | `rel` |
|---|---|---|---|
| 1 | (j, i] 之間有事件（兩市場） | 收盤 − 最後一筆事件的參考價 | — |
| 2 | 上市，且 j ≠ i − 1（前一個資料列無成交） | 收盤 − 第 j 列收盤 | 第 j 列日期 |
| 3 | 其他 | 官方漲跌；上市官方 0 且收盤 ≠ 第 j 列收盤 → `None`（不比價），列入未對到清單 | — |

- 分支 1 對**兩市場**都適用：上櫃除權息日官方漲跌是文字（NULL），原本匯出 `null`、算成平盤，現在改為相對參考價（例：5904 7/16 收 623、參考價 651.5 → −28.5）。上櫃有數值的官方漲跌，結果與官方相同（反推事件的參考價本來就是收盤 − 漲跌）。★ PM 寫上櫃不在範圍，但這是同一個判斷式，分開寫反而多一個市場判斷，所以一起套用。
- 分支 2 只限上市：實測上市前一日無成交時官方漲跌**一律為 0**（438 筆）；上櫃前一日無成交時官方漲跌相對櫃買參考價（2,210 筆有數值），維持官方值。
- 漲跌幅公式不變：`_pct(收盤, 漲跌)` = 漲跌 ÷ (收盤 − 漲跌)，分支 1 的分母即參考價，分支 2 的分母即最後成交收盤。

```python
def _changes(d_, c, ch, market, ev):
    """
    每日漲跌（P14）。回傳 (chs, rel, miss)：
      chs[i] 漲跌（元），無成交或無法判定為 None；rel[i] 分支 2 所相對的最後成交日（date），其他 None；
      miss   上市「官方漲跌 0、收盤 ≠ 前一個成交收盤」但找不到事件的日期（維持不比價）。
    判斷順序：1. 前一個成交列（不含）到今天（含）之間有事件 → 收盤 − 參考價
              2. 上市且前一個資料列無成交 → 收盤 − 最後成交日收盤
              3. 官方漲跌（上市官方 0 且收盤 ≠ 前收 → None）
    """
    at = {e["i"]: e for e in ev}
    chs, rel, miss, j = [], [], [], None
    for i in range(len(d_)):
        x = r = None
        if c[i] is not None:
            e = next((at[k] for k in range(i, -1 if j is None else j, -1) if k in at), None)
            if e is not None:
                x = round(float(c[i]) - e["r"], 2)
            elif market == "TWSE" and j is not None and j != i - 1:
                x, r = round(float(c[i]) - float(c[j]), 2), d_[j]
            else:
                x = _f(ch[i])
                if x == 0 and market == "TWSE" and j is not None and c[i] != c[j]:
                    x = None
                    miss.append(d_[i])
            j = i
        chs.append(x)
        rel.append(r)
    return chs, rel, miss


def _side(x):
    """漲跌家數歸類；None（不比價、官方未提供）沿用既有做法算平盤。"""
    return "up" if (x or 0) > 0 else "down" if (x or 0) < 0 else "flat"
```

個股迴圈內的修改（`chs` 由 B1 段落的 `_changes` 產生，刪除原本的 `chs` 迴圈）：

```python
        pct = None if no_trade else _pct(c[-1], chs[-1])
        ...
        if not no_trade:                    # 無成交不計入漲跌家數
            m[_side(chs[-1])] += 1
        ...
            "c": _f(c[j]), "ch": None if no_trade else chs[-1], "p": _f(pct),
            **({"nt": str(d_[j])} if no_trade else {}),
            **({"rel": str(rel[-1])} if not no_trade and rel[-1] else {}),
```

| 檔案 | 欄位 | 型別 | 單位 | 範例 | 說明 |
|---|---|---|---|---|---|
| `latest.json` | `stocks.X.ch` | number\|null | 元 | `-0.07` | 依上表三分支 |
| `latest.json` | `stocks.X.p` | number\|null | % | `-0.94` | `_pct(c, ch)` |
| `latest.json` | `stocks.X.rel` | string | 日期 | `"2026-10-28"` | 只在分支 2 輸出（10/30 有 5 檔）；約 +100 bytes |
| 個股 JSON | `prices.ch` | (number\|null)[] | 元 | | 同三分支；大小不變 |

`daily[code][day]["pct"]`（板塊漲跌幅、泡泡圖顏色）**不在本項範圍**，維持 `_pct(c[i], ch[i])`（見文末建議）。

### P14-6 畫面

**`app.js` `pctCell`**（今日頁、排行、自選、泡泡圖成分股共用）：

```js
const pctCell = s => s.nt ? `<td class="flat small" title="最後成交 ${s.nt}">無成交</td>`
  : `<td class="num ${cls(s.p)}${s.rel ? ' rel' : ''}"${s.rel ? ` title="相對 ${md(s.rel)} 收盤（前一交易日無成交）"` : ''}>${sgn(s.p)}%</td>`;
```

**`stock.js` 標頭**：漲跌 `<span class="s-chg …">` 之後加

```js
${!noTrade && s?.rel ? `<span class="muted small">相對 ${md(s.rel)} 收盤（前一交易日無成交）</span>` : ''}
```

「昨收」卡沿用 `close − change`，分支 1 顯示參考價、分支 2 顯示最後成交收盤（PM：定義維持現狀）。

**K 線資訊列**：見 B1-6（日線 `rel` 時加「相對 MM/DD 收盤」；不比價的 `title` 改為「官方未提供漲跌，且找不到對應的除權息、減資、面額變更事件」）。

CSS：

```css
.rel{text-decoration:underline dotted;text-underline-offset:3px;cursor:help}
```

- 桌機：滑鼠移到漲跌幅看到 tooltip；虛線底線提示有說明。
- 手機 375px：表格沒有 hover，以個股頁標頭的文字說明為準。

### P14-7 邊界情況

| 情況 | 處理 |
|---|---|
| 上市除權息日，事件表對得到 | 收盤 − 參考價（取代第 1 輪「不比價」） |
| 上市除權息日但事件表對不到 | 「不比價」，算平盤，列入未對到清單 |
| 上市停止買賣後恢復交易（中間沒有資料列） | 前一個資料列有成交 → 分支 3 → 不比價（1435、8105） |
| 上市連續多日無成交 | 相對最後一個成交日（`rel` 可能是一週前） |
| 上市前一日無成交，且中間有事件生效 | 分支 1 優先，相對參考價 |
| 股票第一筆資料 | j 為 None → 官方漲跌 |
| 上櫃除權息日 | 分支 1；上櫃停牌後恢復交易 → 官方值 |
| 今天無成交 | 維持 `nt`，`ch`／`p` 為 null，不計家數 |

### P14-8 測試案例

| 編號 | 步驟 | 預期結果 |
|---|---|---|
| T-P14-1 | `python3 tests/test_iter02.py` | `test_changes` 通過（三分支、事件日當天無成交、上櫃文字漲跌、`_side`） |
| T-P14-2 | `python3 -c "import json;S=json.load(open('site/data/latest.json'))['stocks'];exp={'1213':(-0.07,-0.94),'7732':(0.1,0.3),'8481':(0.2,0.5),'8487':(-1.4,-2.07),'9918':(-0.05,-0.12)};assert all((S[k]['ch'],S[k]['p'],S[k]['rel'])==(*v,'2026-10-28') for k,v in exp.items());print('ok')"` | `ok`（資料日仍為 10/30 時） |
| T-P14-3 | `python3 -c "import json;M=json.load(open('site/data/latest.json'))['market'];print(M['TWSE'],M['TPEx'])"` | 上市 `up 94, down 945, flat 46`；上櫃 `up 127, down 693, flat 56` |
| T-P14-4 | `#/stock/1213` | 標頭「▼ 0.07 (-0.94%)」旁有「相對 10/28 收盤（前一交易日無成交）」；「昨收」7.44 |
| T-P14-5 | Console：`App.watch.add('1213'); saveWatch(); location.hash='#/watch'`，再執行 `document.querySelector('tr[data-code="1213"] td.rel').title` | `"相對 10/28 收盤（前一交易日無成交）"`，儲存格文字 `-0.94%`。測完 `App.watch.delete('1213'); saveWatch()` |
| T-P14-6 | `#/stock/1213` 日線游標停在最後一根 | 資訊列「-0.07 (-0.94%)　相對 10/28 收盤」 |
| T-P14-7 | Console：`(async()=>[aggregate(await loadStock('2317'),'日',true).find(r=>r.d==='2026-07-02'),aggregate(await loadStock('6669'),'日',true).find(r=>r.d==='2026-09-02')].map(r=>[+r.ch.toFixed(2),+r.pc.toFixed(2)]))()` | `[[-1.82,-0.76],[-4.99,-0.19]]`；游標移到 2317 的 2026/07/02，資訊列「-1.82 (-0.76%)　除息　前收 248　參考價 240.82」，不再顯示「不比價」 |
| T-P14-8 | 第 1 輪 T-P5-5 腳本（上市 `ch == 0` 且收盤 ≠ 前收的筆數） | 印 `0`（不比價已匯出為 null）。另將腳本中 `ch == 0` 改為 `ch is None and c is not None`，印出的數字 = T-B1-15 的 N ＋ 上市「第一筆資料官方為 null」的筆數（預估等於 N） |

---

## P16. 股本變動後本益比／殖利率加註（優先 3）

### P16-1 對應驗收條件
1. 6669 本益比、殖利率卡看得到「09/02 除權，官方值可能尚未調整」。
2. 2330 不顯示註記。
3. 單元測試驗證：事件超過 90 天後註記消失。
4. README 注意事項說明此註記。

### P16-2 規則（「近期」與「股本變動」的定義）

- **股本變動事件**：類型為 `權`、`權息`、`減`、`面`、`調`，且參考價變動 |f − 1| ≥ 10%。純現金股利 `息` 不改變股數，不算；配股很少（例如 f = 0.95）的權息對 EPS 影響小，不加註。
- **近期**：**事件生效日起 90 天內**（資料日 − 事件日 ≤ 90）。
  - 不選「最近一次季報申報截止日之後」的理由：除權息集中在 7～9 月，Q2 截止日 8/14 前一兩週除權的股票，依截止日規則只會加註幾天，但官方 EPS 要到 11/14 的 Q3 財報才會反映新股本；90 天規則涵蓋到約一個季報週期。殖利率的股利也可能更晚才更新，所以文字用「可能」。
- 只看最近一次股本變動事件；它超過 90 天就不加註。
- 數值照官方值顯示，不重算。

### P16-3 匯出（`export.py`）

```python
CAP_TYPES = ("權", "權息", "減", "面", "調")
CAP_DAYS = 90


def _cap_event(ev, today):
    """P16：最近一次股本變動事件（參考價變動 ≥ 10%）在 CAP_DAYS 天內 → {"d", "t"}；否則 None。"""
    for e in reversed(ev):
        if e["t"] in CAP_TYPES and abs(e["r"] / e["p"] - 1) >= 0.1:
            return {"d": e["d"], "t": e["t"]} if (today - date.fromisoformat(e["d"])).days <= CAP_DAYS else None
    return None
```

個股 JSON（放在 `"fund"` 之後）：`**({"capchg": cap} if (cap := _cap_event(ev, latest_date)) else {})`

| 欄位 | 型別 | 範例 | 說明 |
|---|---|---|---|
| `capchg` | object | `{"d":"2026-09-02","t":"權"}` | 只有符合規則的股票才有；預估約 40 檔，合計 < 2 KB |

10/30 預期：6669（9/2 權）、6949（9/7 面）、5904（8/10 調）有；2330、3086（4/20，已 193 天）、8422（2025-11-17）沒有。

### P16-4 畫面（`stock.js` 指標卡）

```js
  const cap = data.capchg, capSub = cap ? `${md(cap.d)} ${EV_LABEL[cap.t]}，官方值可能尚未調整` : '';
  ...
  ['本益比', fmt(fund.pe, 2), '', capSub], ['股價淨值比', fmt(fund.pb, 2)],
  ['殖利率', fund.dy != null ? fmt(fund.dy, 2) + '%' : '--', '', capSub],
```

- 例：6669「本益比 5.8」下方小字「09/02 除權，官方值可能尚未調整」；5904「08/10 股本變動，官方值可能尚未調整」。
- 桌機：卡片寬約 130px，小字換成 2～3 行。手機 375px：每列約 3 張卡，同樣換行，不溢出。
- 本益比為「--」時仍顯示註記（說明數字為何可能不可靠）。股價淨值比不加註（淨值會隨股本同步調整）。

### P16-5 邊界情況
- 事件生效日與資料日同一天：天數 0，加註。
- 第 90 天加註、第 91 天消失。
- 最近一次是現金股利、更早有一次 30 天內的除權：`reversed` 先遇到除權（息不符合會被跳過），仍加註。
- 沒有 `fund`（官方沒有本益比）：卡片值為「--」，註記照樣顯示。

### P16-6 測試案例

| 編號 | 步驟 | 預期結果 |
|---|---|---|
| T-P16-1 | `python3 tests/test_iter02.py` | `test_cap_event` 通過（第 90 天有、第 91 天無、只有息無、f = 0.95 無、減資 f > 1 有） |
| T-P16-2 | `python3 -c "import json;g=lambda c:json.load(open(f'site/data/stocks/{c}.json')).get('capchg');print(g('6669'),g('5904'),g('2330'),g('3086'))"` | `{'d': '2026-09-02', 't': '權'} {'d': '2026-08-10', 't': '調'} None None` |
| T-P16-3 | `#/stock/6669`，Console：`[...document.querySelectorAll('.metrics .stat')].filter(e=>/本益比|殖利率/.test(e.querySelector('.l').textContent)).map(e=>e.querySelector('.s')?.textContent)` | `["09/02 除權，官方值可能尚未調整","09/02 除權，官方值可能尚未調整"]` |
| T-P16-4 | `#/stock/2330` 同上 | `[undefined, undefined]` |

---

## P13. 技術訊號：資料不足時不下結論，並標示週期（優先 4，含 P6）

### P13-1 對應驗收條件
1. 2330 月線：標題「技術面訊號（月線）」，顯示「資料不足，無法判讀」，沒有「偏多」「偏空」。
2. 2330 週線：有 MACD 類訊號、沒有 MA60 訊號，標題「（週線）」。
3. 2330 日線：訊號項目與修改前相同（6 項），標題「（日線）」。
4. 最後一根是無成交一字線時，不納入判讀。
5. 沒有新指令或資料表；README 沒有提及技術訊號的段落，不需修改（還原規則的說明見 B1）。

### P13-2 規則
- 訊號一律以**還原價格**計算，不隨「還原／原始」切換（`draw()` 傳入 `aggregate(data, m, true)`）。
- 最後連續的無成交 K 棒（`nt`）從尾端去掉；以最後一根有成交的 K 棒判讀，並註明日期。
- K 棒數 < 35 時不計 MACD 類訊號（DIF > DEA、MACD 柱放大）。均線訊號只在均線有值時計入（現況）。
- 有效訊號 < 3 項 → 「資料不足，無法判讀」，不顯示偏多／偏空。

實際結果（10/30 資料）：2330 月線 13 根 → 只有「收盤 vs MA5」1 項 → 資料不足；週線 53 根 → MA5、MA20、MA5 vs MA20、DIF vs DEA、MACD 柱，共 5 項；日線 242 根 → 6 項。

### P13-3 畫面（`stock.js`）

模板中的標題改為 `<h2 id="sigTitle">技術面訊號</h2>`。

```js
const SIG_MIN = 3, MACD_MIN = 35;   // 有效訊號至少 3 項才下結論；MACD 需 26 + 9 根

function renderSignals(rows, mode) {
  const period = { '日': '日線', '週': '週線', '月': '月線' }[mode];
  $('#sigTitle').textContent = `技術面訊號（${period}）`;
  let n = rows.length;
  while (n > 0 && rows[n - 1].nt) n--;          // 最後一根無成交的一字線不納入判讀
  const C = rows.slice(0, n).map(r => r.c), i = n - 1, c = C[i];
  const ma5 = calcMA(C, 5), ma20 = calcMA(C, 20), ma60 = calcMA(C, 60);
  const bull = [], bear = [];
  const chk = (ok, yes, no) => (ok ? bull : bear).push(ok ? yes : no);
  if (ma5[i] != null) chk(c > ma5[i], '收盤 > MA5', '收盤 < MA5');
  if (ma20[i] != null) chk(c > ma20[i], '收盤 > MA20', '收盤 < MA20');
  if (ma60[i] != null) chk(c > ma60[i], '收盤 > MA60', '收盤 < MA60');
  if (ma5[i] != null && ma20[i] != null) chk(ma5[i] > ma20[i], 'MA5 > MA20', 'MA5 < MA20');
  if (n >= MACD_MIN) {
    const { dif, dea, hist } = calcMACD(C);
    chk(dif[i] > dea[i], 'DIF > DEA', 'DIF < DEA');
    chk(hist[i] > hist[i - 1], 'MACD 柱放大', 'MACD 柱縮小');
  }
  const total = bull.length + bear.length, isBull = bull.length >= bear.length;
  const tags = `<div>${bull.map(t => `<span class="tag up">${t}</span>`).join('')}${bear.map(t => `<span class="tag dn">${t}</span>`).join('')}</div>`;
  const note = (n < rows.length && n ? `最後一根（${md(rows.at(-1).d)}）無成交，以 ${md(rows[i].d)} 判讀。` : '') +
    '依均線與 MACD 機械判讀（還原價格），僅供參考。';
  $('#sigBox').innerHTML = total < SIG_MIN
    ? `<div class="signal"><div style="font-weight:600;margin-bottom:6px">資料不足，無法判讀</div>${tags}
        <div class="muted small" style="margin-top:8px">${period}只有 ${n} 根 K 棒，有效訊號 ${total} 項（至少需 ${SIG_MIN} 項；MACD 需 ${MACD_MIN} 根以上）。${note}</div></div>`
    : `<div class="signal ${isBull ? 'bull' : 'bear'}">
        <div style="font-weight:600;margin-bottom:6px">${isBull ? '偏多' : '偏空'}：${bull.length} 多 ${bear.length} 空</div>
        ${tags}<div class="muted small" style="margin-top:8px">${note}</div></div>`;
}
```

- 資料不足時用中性樣式（`.signal` 沒有 `bull`／`bear` 背景）。
- 文案：
  - 月線：「資料不足，無法判讀」／標籤「收盤 > MA5」／「月線只有 13 根 K 棒，有效訊號 1 項（至少需 3 項；MACD 需 35 根以上）。依均線與 MACD 機械判讀（還原價格），僅供參考。」
- 桌機與手機版面沿用現有卡片（`g2` 在 720px 以下變單欄）。
- 無資料（`rows` 為空）：n = 0、total = 0 → 「資料不足，無法判讀」「日線只有 0 根 K 棒…」，不報錯（`C[i]` 為 undefined，均線條件都不成立）。

### P13-4 邊界情況
- 一般股票最新一天無成交：日線最後一根 `nt` → 去掉，註明「最後一根（10/30）無成交，以 10/29 判讀」。
- 週／月線只有整週／整月無成交才是 `nt`（現行聚合規則），所以週線一般不會觸發。
- 新上市股票日線不足 35 根：沒有 MACD 類；均線不足時可能 < 3 項 → 資料不足。
- 原始模式：訊號卡內容與還原模式完全相同。

### P13-5 測試案例

| 編號 | 步驟 | 預期結果 |
|---|---|---|
| T-P13-1 | `#/stock/2330`，點「月」，Console：`[$('#sigTitle').textContent, /偏多|偏空/.test($('#sigBox').textContent), $('#sigBox').textContent.includes('資料不足，無法判讀')]` | `["技術面訊號（月線）", false, true]` |
| T-P13-2 | 點「週」，Console：`[$('#sigTitle').textContent, [...document.querySelectorAll('#sigBox .tag')].map(e=>e.textContent)]` | 標題「技術面訊號（週線）」；標籤含 `DIF` 與 `MACD 柱`，不含 `MA60`，共 5 個 |
| T-P13-3 | 點「日」 | 標題「技術面訊號（日線）」；`document.querySelectorAll('#sigBox .tag').length === 6`；有「偏多」或「偏空」 |
| T-P13-4 | 日線下 Console：`(async()=>{const r=aggregate(await loadStock('2330'),'日',true);const before=$('#sigBox .signal').className+[...document.querySelectorAll('#sigBox .tag')].map(e=>e.textContent);renderSignals([...r,{...r.at(-1),d:'2026-11-02',o:1,h:1,l:1,c:1,nt:true}],'日');const after=$('#sigBox .signal').className+[...document.querySelectorAll('#sigBox .tag')].map(e=>e.textContent);return [before===after,$('#sigBox').textContent.includes('最後一根（11/02）無成交，以 10/30 判讀')]})()` | `[true, true]`（一字線 c=1 沒有影響判讀） |
| T-P13-5 | 2330 切到「原始」 | 訊號卡內容與「還原」時相同 |

---

## A2. 官方三大法人買賣金額（上市）＋近 20 日走勢（優先 5）

### A2-1 對應驗收條件（SA 修訂處標 ★）
1. `setup-db` 建立新表，重複執行不報錯。
2. 10/30 今日頁上市外資、投信、自營、合計 = `BFI82U` 買賣差額換算億元（四捨五入到 0.1 億）：★ **外資 −1,124.7 億、投信 +236.2 億、自營 −513.7 億、合計 −1,402.2 億**。自營 = 自營商（自行買賣）−3,840,358,646 ＋ 自營商（避險）−47,528,739,270。
3. 卡片看得到「上市，官方，含 ETF」與資料日；上櫃估算另列並註明口徑。
4. 20 日柱狀圖剛好 20 根、最後一根 10/30；「外資連買／連賣 N 日」與資料庫逐日正負號一致。
5. 補抓重跑跳過已有日期；`BFI82U` 失敗時 `collect` 照常完成並印警告。
6. 官方資料日早於行情資料日時顯示「（尚未更新）」。
7. README 與 `__main__.py` 依第七節更新。

### A2-2 資料來源（2026-10-30 實測）

`GET https://www.twse.com.tw/rwd/zh/fund/BFI82U?type=day&dayDate=YYYYMMDD&response=json`

- `stat == "OK"`；`fields`：`['單位名稱', '買進金額', '賣出金額', '買賣差額']`；6 列，金額單位元、含千分位：

| 單位名稱 | 買賣差額（元） | 代碼 |
|---|---|---|
| 自營商(自行買賣) | −3,840,358,646 | `dealer_self` |
| 自營商(避險) | −47,528,739,270 | `dealer_hedge` |
| 投信 | 23,618,796,307 | `trust` |
| 外資及陸資(不含外資自營商) | −112,467,249,894 | `foreign` |
| 外資自營商 | 0 | `foreign_dealer` |
| 合計 | −140,217,551,503 | `total` |

- **實際加總驗證**：自行 ＋ 避險 ＋ 投信 ＋ 外資及陸資 = −140,217,551,503 = 合計。回應 `notes` 寫明「外資自營商買賣金額已計入自營商買賣金額，故不納入三大法人買賣金額之合計數計算」。
- **決定（★ 與 PM 不同）**：**外資 = 外資及陸資（不含外資自營商）**，不加外資自營商。若照 PM 寫的「外資及陸資＋外資自營商」，外資自營商會同時算在外資與自營，四個數字加不回合計。這也是新聞「外資賣超 1,124.67 億」的口徑。外資自營商仍寫入資料表，不顯示。
- 休市或尚未公布：`stat` 不是 `OK`（例：「很抱歉，沒有符合條件的資料!」）→ 回傳 `[]`。

### A2-3 資料庫（`db.py`，放在 `price_events` 之後）

```sql
-- 上市三大法人買賣金額（證交所 BFI82U，單位：元；含 ETF 等全部證券）
IF OBJECT_ID('insti_amount') IS NULL
CREATE TABLE insti_amount (
    id          INT IDENTITY(1,1) PRIMARY KEY,
    trade_date  DATE          NOT NULL,
    unit        NVARCHAR(20)  NOT NULL,   -- foreign 外資及陸資(不含外資自營商) / foreign_dealer 外資自營商 /
                                          -- dealer_self 自營商(自行買賣) / dealer_hedge 自營商(避險) / trust 投信 / total 合計
    buy_amount  BIGINT        NULL,
    sell_amount BIGINT        NULL,
    net_amount  BIGINT        NULL,
    created_at  DATETIME      NOT NULL DEFAULT GETDATE(),
    CONSTRAINT UQ_insti_amount UNIQUE (trade_date, unit)
)
```

MERGE 鍵：`(trade_date, unit)`。

### A2-4 收集流程

**`daily.py`**

- 常數：`PRICES, INSTI, INDEX, AMOUNT = "prices", "insti", "index", "amount"`；註解加「AMOUNT 只在補抓或 collect 單獨呼叫時指定」；`ALL_DATASETS` **不變**。
- 新增：

```python
def _amount_unit(name: str):
    """BFI82U 單位名稱 → 代碼。「外資及陸資(不含外資自營商)」也含「外資自營商」字樣，判斷順序不可對調。"""
    if name.startswith("外資及陸資"):
        return "foreign"
    if name.startswith("外資自營商"):
        return "foreign_dealer"
    if name.startswith("自營商"):
        return "dealer_hedge" if "避險" in name else "dealer_self"
    if name.startswith("投信"):
        return "trust"
    if name.startswith("合計"):
        return "total"
    return None


def parse_insti_amount(data: dict, d: date) -> list:
    """BFI82U 回應 → [{trade_date, unit, buy_amount, sell_amount, net_amount}]（元）；休市或欄位不符回傳 []。"""
    if data.get("stat") != "OK":
        return []
    idx = {f: i for i, f in enumerate(data.get("fields", []))}
    need = ("單位名稱", "買進金額", "賣出金額", "買賣差額")
    if not set(need) <= idx.keys():
        return []
    rows = {}
    for row in data.get("data", []):
        if len(row) <= max(idx[f] for f in need):
            continue
        unit = _amount_unit(str(row[idx["單位名稱"]]).strip())
        if unit:
            rows[unit] = {"trade_date": d.isoformat(), "unit": unit,
                          "buy_amount": clean_number(row[idx["買進金額"]], int),
                          "sell_amount": clean_number(row[idx["賣出金額"]], int),
                          "net_amount": clean_number(row[idx["買賣差額"]], int)}
    return list(rows.values())


def fetch_twse_insti_amount(d: date) -> list:
    data = request("GET", f"{TWSE}/fund/BFI82U",
                   params={"response": "json", "type": "day", "dayDate": f"{d:%Y%m%d}"})
    return parse_insti_amount(data, d)


def merge_insti_amount(cursor, rows: list):
    cursor.execute("""
        MERGE insti_amount AS t
        USING OPENJSON(?) WITH (
            trade_date DATE, unit NVARCHAR(20), buy_amount BIGINT, sell_amount BIGINT, net_amount BIGINT
        ) AS s
        ON t.trade_date = s.trade_date AND t.unit = s.unit
        WHEN MATCHED THEN UPDATE SET
            buy_amount = s.buy_amount, sell_amount = s.sell_amount, net_amount = s.net_amount
        WHEN NOT MATCHED THEN
            INSERT (trade_date, unit, buy_amount, sell_amount, net_amount)
            VALUES (s.trade_date, s.unit, s.buy_amount, s.sell_amount, s.net_amount);
    """, db.to_json(rows))
```

- `collect_for_date()`：在 `INSTI` 區塊之後加

```python
    amount = []
    if AMOUNT in datasets:
        amount = fetch_twse_insti_amount(d)
        if amount:
            counts["法人金額"] = len(amount)
        elif not (prices or insti or taiex):
            print("  ℹ️  無三大法人買賣金額（休市或尚未公布），略過此日")
            return False
```

  寫入區加 `if amount: merge_insti_amount(cursor, amount)`（同一交易內）。

**`history.py`**：`from .daily import ALL_DATASETS, AMOUNT, INDEX, INSTI, PRICES, collect_for_date`；`_TABLE[AMOUNT] = "insti_amount"`；`SECONDS_PER_DAY[AMOUNT] = 4`。

**`__main__.py`**

- `cmd_collect`：import 改為 `from .collectors.daily import AMOUNT, collect_for_date, collect_tpex_index`；在 B1 的事件 `try` 之前加：

```python
            try:
                collect_for_date(d, (AMOUNT,))
            except FetchError as e:
                print(f"  ⚠️  三大法人金額抓取失敗：{e}")
```

  （每日 1 次請求，約 4 秒。當天尚未公布時印「ℹ️ 無三大法人買賣金額…」，隔天 `history --only amount` 或下次 `collect --date` 可補。）
- `history --only`：`choices=["prices", "insti", "index", "amount"]`，help 改為「只抓指定資料集（index = 只補加權指數，amount = 只補上市三大法人買賣金額）」。

**補抓指令與時間**（事件補抓結束後執行）：

```bash
python3 -m twstock history --start 2026-07-31 --end 2026-10-30 --only amount
```

- 61 個交易日 × 約 4 秒 ≈ **4 分鐘**；重跑時已有的日期跳過（印「待抓 0 天」）。
- 補到一年（約 242 天、16 分鐘）不在本輪驗收，使用者可自行執行 `--start 2025-10-30`。

### A2-5 匯出（`export.py`）

常數 `INSTI_DAYS = 20`。查詢（放在 `index_rows` 之後）：

```python
amount = defaultdict(dict)
for d, unit, net in cur.execute("SELECT trade_date, unit, net_amount FROM insti_amount"):
    amount[d][unit] = net
```

```python
def _insti_official(amount):
    """A2：amount = {日期: {單位: 買賣差額(元)}}；有「合計」的最後一天為資料日。外資 = 外資及陸資（外資自營商已含在自營商）。"""
    days = [d for d in sorted(amount) if amount[d].get("total") is not None]
    if not days:
        return None
    yi = lambda v: round((v or 0) / YI, 1)
    a, recent = amount[days[-1]], days[-INSTI_DAYS:]
    foreign = [amount[d].get("foreign") or 0 for d in days]
    return {"date": str(days[-1]), "foreign": yi(a.get("foreign")), "trust": yi(a.get("trust")),
            "dealer": yi((a.get("dealer_self") or 0) + (a.get("dealer_hedge") or 0)), "total": yi(a["total"]),
            "d": [str(d) for d in recent], "f": [yi(v) for v in foreign[-INSTI_DAYS:]],
            "t": [yi(amount[d]["total"]) for d in recent], "fs": streak(foreign)}
```

上櫃估算：個股迴圈內另累加 `insti_otc`（與 `insti_total` 同一段，`if n and info["market"] == "TPEx"`）。

`latest.json` 新增（放在 `"insti"` 之後；`insti` 保留，給沒有官方資料時的舊卡片用）：

| 欄位 | 型別 | 單位 | 範例 | 說明 |
|---|---|---|---|---|
| `insti_official` | object\|null | | | 資料表沒有資料時為 null |
| `.date` | string | 日期 | `"2026-10-30"` | 官方資料日（可能早於 `date`） |
| `.foreign`／`.trust`／`.dealer`／`.total` | number | 億 | `-1124.7`／`236.2`／`-513.7`／`-1402.2` | 0.1 億；自營 = 自行＋避險 |
| `.d` | string[] | 日期 | | 最近至多 20 個有資料的日期，舊到新 |
| `.f`／`.t` | number[] | 億 | | 對應 `d` 的外資、合計差額 |
| `.fs` | number | 天 | `-3` | 外資連續買（正）／賣（負）天數，以資料表全部日期計算；當天差額 0 → 0 |
| `insti_otc` | object | 億 | `{"foreign":-75.2,"trust":35.0,"dealer":10.1}` | 上櫃估算（張數 × 收盤，不含 ETF），法人資料日 = `flow_date` |

大小：約 0.6 KB（`latest.json` 671 KB → +0.1%）。

### A2-6 畫面（`app.js` 今日頁第二列第三張卡）

`renderToday()` 中原本的三大法人卡換成 `${instiCard(L)}`。新增（放在 `indexCard` 之後）：

```js
// 迷你柱狀圖：正值紅（買超）、負值綠（賣超），零軸置中
function minibars(vals) {
  if (!vals?.length) return '';
  const m = Math.max(...vals.map(Math.abs)) || 1, w = 100 / vals.length;
  return `<svg class="spark" viewBox="0 0 100 34" preserveAspectRatio="none" aria-hidden="true">
    <line x1="0" x2="100" y1="17" y2="17" stroke="var(--border2)" stroke-width="1" vector-effect="non-scaling-stroke"/>` +
    vals.map((v, i) => { const h = Math.abs(v) / m * 16;
      return `<rect x="${(i * w + w * 0.15).toFixed(2)}" y="${(v >= 0 ? 17 - h : 17).toFixed(2)}" width="${(w * 0.7).toFixed(2)}" height="${h.toFixed(2)}" fill="var(--${v >= 0 ? 'up' : 'dn'})"/>`; }).join('') +
    '</svg>';
}

function instiCard(L) {
  const O = L.insti_official, X = L.insti_otc, I = L.insti;
  const yi1 = v => v == null ? '--' : sgn(v, 1) + '億';
  if (!O) return `<div class="card stat"><div class="l">三大法人（${md(L.flow_date)}）</div>
      <div class="v num ${cls(I.foreign + I.trust + I.dealer)}">${yi(I.foreign + I.trust + I.dealer)}</div>
      <div class="s num">外資 <span class="${cls(I.foreign)}">${yi(I.foreign)}</span>　投信 <span class="${cls(I.trust)}">${yi(I.trust)}</span>　自營 <span class="${cls(I.dealer)}">${yi(I.dealer)}</span></div>
      <div class="s">估算：買賣超張數 × 收盤價，不含 ETF</div></div>`;     // 尚無官方資料：維持舊卡
  const stale = O.date < L.date, fs = O.fs;
  return `<div class="card stat idx insti">
      <div class="l">三大法人　上市，官方，含 ETF<span class="muted">　${md(O.date)}${stale ? '（尚未更新）' : ''}</span></div>
      <div class="v num ${cls(O.total)}">${yi1(O.total)}</div>
      <div class="s num">外資 <span class="${cls(O.foreign)}">${yi1(O.foreign)}</span>　投信 <span class="${cls(O.trust)}">${yi1(O.trust)}</span>　自營 <span class="${cls(O.dealer)}">${yi1(O.dealer)}</span></div>
      ${minibars(O.f)}
      <div class="s">外資近 ${O.f.length} 日（${md(O.d[0])}～${md(O.d.at(-1))}）<b class="${cls(fs)}">${fs > 0 ? `連買 ${fs} 日` : fs < 0 ? `連賣 ${-fs} 日` : '當日持平'}</b></div>
      ${X ? `<div class="s num">上櫃估算（${md(L.flow_date)}）：外資 <span class="${cls(X.foreign)}">${yi(X.foreign)}</span>　投信 <span class="${cls(X.trust)}">${yi(X.trust)}</span>　自營 <span class="${cls(X.dealer)}">${yi(X.dealer)}</span></div>
      <div class="s">上櫃為張數 × 收盤估算、不含 ETF，不可與上市官方值相加</div>` : ''}
    </div>`;
}
```

- `idx` class 沿用指數卡的 `.idx .spark` 尺寸（寬 100%、高 36px）。
- 數字到 0.1 億：「外資 -1,124.7億　投信 +236.2億　自營 -513.7億」，主數字「-1,402.2億」。

畫面文案：

| 狀態 | 顯示 |
|---|---|
| 正常 | 「三大法人　上市，官方，含 ETF　10/30」／大字「-1,402.2億」／三法人／20 根柱／「外資近 20 日（10/02～10/30）連賣 N 日」／「上櫃估算（10/30）：外資 … 投信 … 自營 …」／「上櫃為張數 × 收盤估算、不含 ETF，不可與上市官方值相加」 |
| 官方日 < 資料日 | 標題列「… 10/29（尚未更新）」 |
| 補抓不到 20 天 | 柱數 = 實際天數，文字「外資近 N 日」 |
| 沒有官方資料（尚未補抓） | 顯示第 1 輪的估算卡（不變） |

CSS：

```css
@media (max-width:520px){.g-stats .insti{grid-column:1/-1}}   /* 手機佔滿一列，三行數字不擠成 166px */
```

- 桌機：第二列三張卡各約 360px，法人卡內容最多，整列高度隨它增加。
- 手機 375px：上市、上櫃成交額兩張並排，法人卡獨佔下一列（343px），三法人一行放得下（約 290px）。

### A2-7 邊界情況

| 情況 | 處理 |
|---|---|
| 18:30 `BFI82U` 已公布 | 正常；若尚未公布 → 「ℹ️ 無三大法人買賣金額」，卡片顯示前一日＋「（尚未更新）」 |
| `BFI82U` 被限流 | `collect` 印 ⚠️ 繼續；行情已寫入 |
| 單位名稱改版、找不到合計 | 該日沒有 `total` → `_insti_official` 不採用該日 |
| 外資當日差額 0 | `fs = 0`，顯示「當日持平」 |
| 資料表中間缺日（補抓不完整） | 柱狀圖與連續天數以「有資料的日期」計算（不補 0） |
| 外資連續天數等於全部資料天數 | 照實顯示（例：補抓 61 天、連賣 61 日）；補抓滿一年可避免 |
| 官方資料日晚於法人個股資料日 | 卡片標各自日期：上市官方 `O.date`、上櫃估算 `flow_date` |

### A2-8 測試案例

| 編號 | 步驟 | 預期結果 |
|---|---|---|
| T-A2-1 | `python3 tests/test_iter02.py` | `test_parse_insti_amount`、`test_insti_official` 通過 |
| T-A2-2 | 執行補抓指令；完成後 SQL：`SELECT COUNT(DISTINCT trade_date), COUNT(*) FROM insti_amount WHERE trade_date BETWEEN '2026-07-31' AND '2026-10-30'` | `61, 366`（每天 6 列）；再執行一次補抓，印「待抓 0 天」 |
| T-A2-3 | SQL：`SELECT unit, net_amount FROM insti_amount WHERE trade_date='2026-10-30'` | 6 列，`dealer_self` = −3840358646、`foreign` = −112467249894、`total` = −140217551503 |
| T-A2-4 | `python3 -c "import json;o=json.load(open('site/data/latest.json'))['insti_official'];assert (o['date'],o['foreign'],o['trust'],o['dealer'],o['total'])==('2026-10-30',-1124.7,236.2,-513.7,-1402.2);assert len(o['d'])==len(o['f'])==20 and o['d'][-1]=='2026-10-30';print(o['fs'])"` | 印出外資連續天數 |
| T-A2-5 | 執行下方腳本 F（以 SQL 重算連續天數） | 印出的數字 = T-A2-4 的 `fs` |
| T-A2-6 | 開今日頁，Console：`(()=>{const c=document.querySelector('.insti');return [c.textContent.includes('上市，官方，含 ETF'),c.textContent.includes('10/30'),c.querySelectorAll('svg rect').length,c.textContent.includes('上櫃估算'),c.querySelector('.v').textContent]})()` | `[true, true, 20, true, "-1,402.2億"]`；卡片看得到「自營 -513.7億」 |
| T-A2-7 | Console：`App.latest.insti_official.date='2026-10-29'; renderToday()` | 標題列「10/29（尚未更新）」；重新整理還原 |
| T-A2-8 | Console：`delete App.latest.insti_official; renderToday()` | 顯示第 1 輪估算卡（「估算：買賣超張數 × 收盤價，不含 ETF」），頁面不報錯 |
| T-A2-9 | 失敗模擬：T-B1-14 腳本 D | 見 T-B1-14 |
| T-A2-10 | 連續執行 `setup-db` 兩次 | 見 T-B1-2 |
| T-A2-11 | DevTools 375×812 開今日頁 | 法人卡獨佔一列，三法人數字一行、不溢出；20 根柱可辨識 |

腳本 F：

```bash
python3 - <<'EOF'
from twstock import db
v = [r[0] for r in db.connect().cursor().execute(
    "SELECT net_amount FROM insti_amount WHERE unit='foreign' ORDER BY trade_date DESC")]
n = 0
for x in v:
    if x == 0 or (n and (x > 0) != (n > 0)):
        break
    n += 1 if x > 0 else -1
print(n)
EOF
```

---

## P15. 指數卡走勢線標示 60 日漲跌幅（優先 6）

### P15-1 對應驗收條件
1. 加權指數卡顯示的 60 日漲跌幅 = `s` 最後一點 ÷ 第一點 − 1，正負號與走勢線顏色一致。
2. 櫃買指數卡（目前 19 天）顯示「自 10/01 起 +x.x%」。
3. 無新指令或資料表，README 不需修改。

### P15-2～P15-4
不需新資料；使用 `latest.index.X.s`、`from`。

### P15-5 畫面（`app.js` `indexCard()`）

把最後一行 `<div class="s">…</div>` 換成：

```js
      ${x.s.length >= 2 ? `<div class="s"><span class="${x.s.at(-1) >= x.s[0] ? 'up' : 'dn'}">${x.s.length >= 60 ? '近 60 個交易日' : `自 ${md(x.from)} 起`} ${sgn((x.s.at(-1) / x.s[0] - 1) * 100, 1)}%</span>${x.s.length < 60 ? `（${x.s.length} 個交易日）` : ''}</div>` : ''}
```

- 顏色規則與 `spark()` 相同（最後一點 ≥ 第一點為紅），用 `<span>` 包住，否則 `.stat .s` 的灰色優先權較高。
- 10/30 文案：加權「近 60 個交易日 +4.2%」（紅；43,386.41 → 45,211.83）；櫃買「自 10/01 起 -11.6%（19 個交易日）」（綠；418.82 → 370.26）。
- `s` 只有 1 點：不顯示（走勢線也不畫）。

### P15-6 測試案例

| 編號 | 步驟 | 預期結果 |
|---|---|---|
| T-P15-1 | 今日頁 Console：`[...document.querySelectorAll('.idx')].slice(0,2).map(e=>{const s=e.querySelector('.s:last-child span');return [s.textContent,s.className,e.querySelector('polyline').getAttribute('stroke')]})` | `[["近 60 個交易日 +4.2%","up","var(--up)"],["自 10/01 起 -11.6%","dn","var(--dn)"]]` |
| T-P15-2 | Console：`const t=App.latest.index.TAIEX;((t.s.at(-1)/t.s[0]-1)*100).toFixed(1)` | `"4.2"`，與卡片一致 |

---

## 七、README 與 `__main__.py` 更新清單（PG 依此修改，QA 逐條核對）

### `README.md`

| # | 位置 | 修改 |
|---|---|---|
| R1 | 第一段 | 「收集上市、上櫃個股的行情、本益比、三大法人、月營收、處置／注意股」→ 加上「、除權息／減資／面額變更事件，上市三大法人買賣金額」 |
| R2 | 專案結構表 `twstock/collectors/` 列 | 加「`events` 除權息／減資／面額變更事件（還原價格用）」；`daily` 說明加「、上市三大法人買賣金額」 |
| R3 | 專案結構表 `tests/` 列 | 改為「`python3 tests/test_iter01.py`、`python3 tests/test_iter02.py`」 |
| R4 | 安裝段「更新程式後若有新增資料表…」 | 例子改為「（例如第 1 輪的 `market_index`、`stock_alerts`，第 2 輪的 `price_events`、`insti_amount`）」 |
| R5 | 日常使用指令區塊 | `collect` 註解改為「（含指數、台指期、處置／注意股、除權息事件、三大法人金額）」；新增三行：`python -m twstock events --start 2025-10-30   # 補抓除權息／減資／面額變更事件（約 1 分鐘，可重跑）`、`python -m twstock history --start 2026-07-31 --only amount   # 只補上市三大法人買賣金額（一天一個請求）`、`python3 tests/test_iter02.py   # 第 2 輪測試` |
| R6 | 注意事項：「個股的『區間高／低』…價格未還原除權息。」 | 改為：「個股價格預設**還原**（向後還原，最新收盤不變）：除權息、減資、面額變更以官方參考價 ÷ 事件前收盤為係數，事件之前的開高低收乘上之後所有事件係數的乘積。上市事件取自證交所 TWT49U、TWTAUU、TWTB8U，上櫃除權息取自櫃買除權除息計算結果表，上櫃減資、面額變更以「收盤 − 官方漲跌」反推。K 線可切換「原始」；52 週高低與技術面訊號一律用還原價；成交量、法人張數未還原。日線未滿一年時顯示「區間高／低」與起始日。」 |
| R7 | 注意事項：「上市股除權息、減資等不比價日…顯示『不比價』。」 | 改為：「漲跌：除權息、減資、面額變更當天以「收盤 − 參考價」計算；上市股前一交易日無成交時，以最後成交日收盤計算並標示「相對 MM/DD 收盤」；官方未提供漲跌且找不到對應事件（例如停止買賣後恢復交易）時顯示「不比價」，漲跌家數算平盤。」 |
| R8 | 注意事項新增一條（放在 R7 之後） | 「除權、減資、面額變更等股本變動（參考價變動 10% 以上）後 90 天內，個股頁的本益比、殖利率會加註「官方值可能尚未調整」：官方值的 EPS、股利可能仍是舊股本的數字。」 |
| R9 | 注意事項新增一條（放在「個股法人…估算值」之後） | 「今日頁三大法人卡：上市為證交所 BFI82U 官方買賣金額（含 ETF；外資 = 外資及陸資，不含外資自營商，外資自營商已計入自營商），附近 20 日外資買賣超與連買／連賣天數；上櫃仍為張數 × 收盤估算（不含 ETF），另列一行，不與上市相加。」 |
| R10 | 注意事項新增一條（放在最後「資料僅供研究參考」之前） | 「往前補抓日線時，請用同一區間執行 `python -m twstock events --start …`，否則補抓區段的價格不會還原。」 |

### `twstock/__main__.py`

| # | 位置 | 修改 |
|---|---|---|
| M1 | docstring `collect` 行 | 括號內改為「行情、本益比、法人、月營收、指數、台指期、處置／注意股、除權息事件、三大法人金額」 |
| M2 | docstring | `history … --only index` 之後加：`  python -m twstock history --start 2026-07-31 --only amount  只補上市三大法人買賣金額` |
| M3 | docstring | `revenue` 行之後加：`  python -m twstock events --start 2025-10-30         補抓除權息／減資／面額變更事件（還原價格用）` |
| M4 | `history --only` | `choices` 加 `"amount"`，help 見 A2-4 |
| M5 | 新子指令 `events` | 見 B1-4 |
| M6 | `cmd_collect` | 加 A2、B1 兩個 `try` 區塊（見 A2-4、B1-4），檔頭 import `timedelta` |

QA 核對方式：`python3 -m twstock --help` 看得到 `events`；`python3 -m twstock history --help` 的 `--only` 有 `amount`；README 逐條比對 R1～R10。

---

## 附錄 A：資料源驗證紀錄（2026-10-30，經 `fetch.request`、`RETRY_BACKOFF=()`，不重試）

| 端點 | 次數 | 結果 | 用途 |
|---|---|---|---|
| `www.tpex.org.tw/www/zh-tw/afterTrading/dailyQuotes`（POST `date=2026/07/09`） | 1 | 成功；5511 德昌 `漲跌` 為 `除權息 `、6223 旺矽為 `除息 `（文字，解析成 NULL），一般股 `-0.60 `；另有 `次日 參考價` 欄（本輪未使用） | 發現上櫃反推的限制 |
| `www.tpex.org.tw/www/zh-tw/bulletin/exDailyQ`（POST 2026/07/01～07/31） | 1 | 成功；318 筆（除息 289、除權息 21、除權 8），21 個欄位，含 `除權息前收盤價`、`除權息參考價`、`權/息` | B1 上櫃除權息 |
| 同上（2025/10/30～2026/10/30） | 1 | 成功；1,341 筆，一年一次可查 | 驗證區間上限、計算預期值 |
| `www.twse.com.tw/rwd/zh/exRight/TWT49U`（20260901～20260930） | 1 | 成功；109 筆；6669 9/2 權 7,800 → 2,614.99 | B1、P14 |
| 同上（20251030～20260831） | 1 | 成功；1,321 筆，10 個月一次可查 | 驗證區間、計算預期值 |
| `www.twse.com.tw/rwd/zh/reducation/TWTAUU`（20251030～20261030） | 1 | 成功；20 筆；`除權參考價` 全為 `--` | B1 |
| `www.twse.com.tw/rwd/zh/change/TWTB8U`（20251030～20261030） | 1 | 成功；3 筆（8422、7780、6949） | B1 |
| `www.twse.com.tw/rwd/zh/fund/BFI82U`（`type=day&dayDate=20261030`） | 1 | 成功；6 列；四列相加 = 合計，外資自營商不在合計內 | A2 |

原型計算（不連網）：以上回應＋資料庫日線，跑完全部 1,999 檔：事件 1,702 筆（上市 958、上櫃 744，其中上櫃反推 29）；沒有係數超出範圍的事件；上市未對到事件 2 筆（≤ 9/30）＋ 10 月 18 筆（未抓 10 月 `TWT49U`，補抓後應全部對到）。

## 附錄 B：`tests/test_iter02.py` 規格

- 比照 `test_iter01.py`：只用標準函式庫與專案模組，`python3 tests/test_iter02.py` 直接執行（末尾依序呼叫所有 `test_*`、印「全部通過」），相容 pytest；不連網、不連資料庫。
- P13 的門檻與 P15 是前端邏輯，以 T-P13-*、T-P15-* 的瀏覽器步驟驗證。
- 內容（PG 可直接使用；樣本取自 2026-10-30 實測回應）：

```python
"""
第 02 輪純邏輯測試（不連網、不連資料庫）：
民國日期、除權息／減資／面額變更事件解析、事件對應與還原係數、上櫃參考價反推、
P14 漲跌三分支與漲跌家數、P16 股本變動註記、A2 三大法人金額解析與連續天數。

  python3 tests/test_iter02.py      （也相容 pytest）
"""
import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from twstock.collectors.alerts import roc_date  # noqa: E402
from twstock.collectors.daily import parse_insti_amount  # noqa: E402
from twstock.collectors.events import parse_events  # noqa: E402
from twstock.export import (_adj_factors, _cap_event, _changes, _insti_official,  # noqa: E402
                            _price_events, _side)


def D(m, d, y=2026):
    return date(y, m, d)


def N(*v):
    """模擬資料庫的 DECIMAL 欄位（None = 無成交或官方未提供）。"""
    return tuple(None if x is None else Decimal(str(x)) for x in v)


# ─── B1：民國日期、事件解析 ───────────────────────────────
def test_roc_date():
    assert roc_date("115年09月02日") == D(9, 2)
    assert roc_date("114/11/03") == D(11, 3, 2025)
    assert roc_date("115/07/10") == D(7, 10)
    assert roc_date("1151029") == D(10, 29)                 # 第 1 輪格式不受影響
    assert roc_date("115年13月01日") is None and roc_date("") is None


T49 = ["資料日期", "股票代號", "股票名稱", "除權息前收盤價", "除權息參考價", "權值+息值", "權/息"]
AUU = ["恢復買賣日期", "股票代號", "名稱", "停止買賣前收盤價格", "恢復買賣參考價", "漲停價格", "跌停價格",
       "開盤競價基準", "除權參考價", "減資原因", "詳細資料"]
B8U = ["恢復買賣日期", "股票代號", "名稱", "停止買賣前收盤價格", "恢復買賣參考價", "漲停價格", "跌停價格",
       "開盤競價基準", "詳細資料"]
TPX = ["除權息日期", "代號", "名稱", "除權息前收盤價", "除權息參考價", "權值", "息值", "權值+息值", "權/息"]


def test_parse_events():
    r = parse_events("TWT49U", T49, [
        ["115年09月02日", "6669", "緯穎", "7,800.00", "2,614.99", "5,185.002642", "權"],
        ["115年09月01日", "00939", "統一台灣高息動能", "23.17", "23.04", "0.125000", "息"],   # ETF
        ["115年09月01日", "1732", "毛寶", "26.45", "25.85", "0.600000", "息"],
        ["115年09月03日", "1234", "測試", "--", "10.00", "", "息"],                           # 前收無法解析
        ["115年09月03日", "1235", "測試"]])                                                   # 列太短
    assert r == [{"stock_code": "6669", "event_date": "2026-09-02", "event_type": "權",
                  "prev_close": 7800.0, "ref_price": 2614.99, "source": "TWT49U"},
                 {"stock_code": "1732", "event_date": "2026-09-01", "event_type": "息",
                  "prev_close": 26.45, "ref_price": 25.85, "source": "TWT49U"}]
    r = parse_events("TWTAUU", AUU, [["114/11/03", "2832", "台產", "36.00", "47.14", "51.80", "42.45", "47.15",
                                      "--", "退還股款", "2832  ,20251021"]])
    assert [(x["event_type"], x["event_date"], x["prev_close"], x["ref_price"]) for x in r] == \
        [("減", "2025-11-03", 36.0, 47.14)]
    r = parse_events("TWTB8U", B8U, [["115/09/07", "6949", "沛爾生醫-創", "1,490.00", "74.50", "81.90", "67.10",
                                      "74.50", "6949,20260827,20260907"]])
    assert [(x["event_type"], x["prev_close"], x["ref_price"]) for x in r] == [("面", 1490.0, 74.5)]
    r = parse_events("TPEX_EX", TPX, [
        ["115/07/09", "5511", "德昌              ", "79.70", "63.48", "12.623647", "3.600000", "16.223647", "除權息"],
        ["115/07/10", "6223", "旺矽", "6460.00", "6438.00", "0.000000", "22.000000", "22.000000", "除息"],
        ["115/07/10", "00950B", "債券", "10.00", "9.90", "0", "0.1", "0.1", "除息"]])
    assert [(x["stock_code"], x["event_type"], x["event_date"]) for x in r] == \
        [("5511", "權息", "2026-07-09"), ("6223", "息", "2026-07-10")]
    # 空回應、欄位缺漏
    assert parse_events("TWT49U", None, None) == []
    assert parse_events("TWT49U", ["資料日期", "股票代號"], [["115年09月02日", "6669"]]) == []
    assert parse_events("TPEX_EX", TPX, []) == []


# ─── B1：事件對應、上櫃反推、還原係數 ─────────────────────
def test_price_events():
    # 7/10 休市日的除息 → 生效於 7/13；資料之前、之後的事件略過
    d = (D(7, 8), D(7, 9), D(7, 13), D(7, 14))
    c, ch = N(100, 100, 97, 98), N(1, 0, 0.45, 1)
    off = [{"d": D(7, 10), "t": "息", "p": 100.0, "r": 96.55, "src": "TWT49U"},
           {"d": D(7, 20), "t": "息", "p": 98.0, "r": 97.0, "src": "TWT49U"},
           {"d": D(7, 1), "t": "權", "p": 50.0, "r": 40.0, "src": "TWT49U"}]
    ev, bad = _price_events(d, c, ch, "TWSE", off)
    assert ev == [{"i": 2, "d": "2026-07-13", "t": "息", "p": 100.0, "r": 96.55}] and bad == []
    # 同一列兩筆官方事件 → 取減資
    off = [{"d": D(7, 13), "t": "權", "p": 100.0, "r": 90.0, "src": "TWT49U"},
           {"d": D(7, 13), "t": "減", "p": 100.0, "r": 120.0, "src": "TWTAUU"}]
    assert [(e["t"], e["r"]) for e in _price_events(d, c, ch, "TWSE", off)[0]] == [("減", 120.0)]
    # 係數超出 0.02～20 → 不採用
    ev, bad = _price_events(d, c, ch, "TWSE", [{"d": D(7, 13), "t": "面", "p": 1000.0, "r": 10.0, "src": "TWTB8U"}])
    assert ev == [] and bad == [("2026-07-13", 0.01)]
    # 上櫃反推：參考價 = 收盤 − 官方漲跌；前一列無成交、官方漲跌為 None 時不反推；漲跌停不產生事件
    d = (D(8, 6), D(8, 7), D(8, 10), D(8, 11), D(8, 12), D(8, 13))
    c, ch = N(700, 720, 79.2, None, 80, 81), N(5, 20, 7.2, None, 0.5, None)
    assert _price_events(d, c, ch, "TPEx", [])[0] == [{"i": 2, "d": "2026-08-10", "t": "調", "p": 720.0, "r": 72.0}]
    # 與官方事件同一列 → 以官方為準；上市不反推
    off = [{"d": D(8, 10), "t": "息", "p": 720.0, "r": 72.0, "src": "TPEX_EX"}]
    assert [e["t"] for e in _price_events(d, c, ch, "TPEx", off)[0]] == ["息"]
    assert _price_events(d, c, ch, "TWSE", [])[0] == []


def test_adj_factors():
    ev = [{"i": 2, "p": 100.0, "r": 96.0}, {"i": 4, "p": 50.0, "r": 75.0}]      # 現金股利 0.96、減資 1.5
    assert [round(x, 4) for x in _adj_factors(6, ev)] == [1.44, 1.44, 1.5, 1.5, 1.0, 1.0]
    assert _adj_factors(3, []) == [1.0, 1.0, 1.0]
    # 6669：6/22 除息 4,985.6/5,130、9/2 除權 2,614.99/7,800；3/31 最低 3,290 → 1,071.94
    af = _adj_factors(3, [{"i": 1, "p": 5130.0, "r": 4985.6}, {"i": 2, "p": 7800.0, "r": 2614.99}])
    assert round(3290 * af[0], 2) == 1071.94 and af[2] == 1.0


# ─── P14：漲跌三分支與漲跌家數 ───────────────────────────
def test_changes():
    # 上市：一般日、平盤、無成交、前一列無成交（分支 2）、不比價（分支 3）、事件日（分支 1）
    d = (D(10, 26), D(10, 27), D(10, 28), D(10, 29), D(10, 30), D(11, 2), D(11, 3))
    c, ch = N(7.21, 7.44, 7.44, None, 7.37, 8.00, 7.00), N(0.1, 0.23, 0, 0, 0, 0, 0)
    ev = [{"i": 6, "d": "2026-11-03", "t": "息", "p": 8.0, "r": 7.5}]
    chs, rel, miss = _changes(d, c, ch, "TWSE", ev)
    assert chs == [0.1, 0.23, 0.0, None, -0.07, None, -0.5]
    assert rel == [None, None, None, None, D(10, 28), None, None] and miss == [D(11, 2)]
    # 事件生效日當天無成交 → 下一個成交日相對參考價（不是相對最後成交）
    chs, rel, _ = _changes((D(7, 1), D(7, 2), D(7, 3)), N(248, None, 239), N(1, 0, 0), "TWSE",
                           [{"i": 1, "d": "2026-07-02", "t": "息", "p": 248.0, "r": 240.82}])
    assert chs == [1.0, None, -1.82] and rel == [None] * 3
    # 上櫃：除權息日官方漲跌是文字（None）→ 收盤 − 參考價；一般日照官方
    chs, rel, miss = _changes((D(7, 15), D(7, 16), D(7, 17), D(7, 20)), N(677, 623, None, 630),
                              N(2, None, None, 1.5), "TPEx", [{"i": 1, "d": "2026-07-16", "t": "息", "p": 677.0, "r": 651.5}])
    assert chs == [2.0, -28.5, None, 1.5] and rel == [None] * 4 and miss == []
    # 漲跌家數歸類：不比價（None）算平盤
    assert [_side(x) for x in (-0.07, 0.1, 0.0, None)] == ["down", "up", "flat", "flat"]


# ─── P16：股本變動註記 ───────────────────────────────────
def test_cap_event():
    ev = [{"i": 1, "d": "2026-06-22", "t": "息", "p": 5130.0, "r": 4985.6},
          {"i": 2, "d": "2026-09-02", "t": "權", "p": 7800.0, "r": 2614.99}]
    assert _cap_event(ev, D(10, 30)) == {"d": "2026-09-02", "t": "權"}
    assert _cap_event(ev, D(12, 1)) == {"d": "2026-09-02", "t": "權"}       # 第 90 天
    assert _cap_event(ev, D(12, 2)) is None                                     # 第 91 天
    assert _cap_event(ev[:1], D(6, 30)) is None                                 # 只有現金股利
    assert _cap_event([{"i": 1, "d": "2026-09-01", "t": "權息", "p": 100.0, "r": 95.0}], D(9, 2)) is None
    assert _cap_event([{"i": 1, "d": "2026-06-30", "t": "調", "p": 208.0, "r": 360.0}], D(7, 1)) == \
        {"d": "2026-06-30", "t": "調"}
    assert _cap_event([], D(10, 30)) is None


# ─── A2：官方三大法人金額 ─────────────────────────────────
BFI = {"stat": "OK", "fields": ["單位名稱", "買進金額", "賣出金額", "買賣差額"], "data": [
    ["自營商(自行買賣)", "9,031,429,661", "12,871,788,307", "-3,840,358,646"],
    ["自營商(避險)", "32,728,302,266", "80,257,041,536", "-47,528,739,270"],
    ["投信", "36,336,431,234", "12,717,634,927", "23,618,796,307"],
    ["外資及陸資(不含外資自營商)", "340,478,117,346", "452,945,367,240", "-112,467,249,894"],
    ["外資自營商", "0", "0", "0"],
    ["合計", "418,574,280,507", "558,791,832,010", "-140,217,551,503"]]}


def test_parse_insti_amount():
    r = {x["unit"]: x for x in parse_insti_amount(BFI, D(10, 30))}
    assert set(r) == {"dealer_self", "dealer_hedge", "trust", "foreign", "foreign_dealer", "total"}
    assert r["dealer_self"]["net_amount"] == -3840358646 and r["foreign"]["net_amount"] == -112467249894
    assert r["total"]["buy_amount"] == 418574280507 and r["total"]["trade_date"] == "2026-10-30"
    # 合計 = 自營自行 + 自營避險 + 投信 + 外資及陸資（外資自營商已含在自營商，不另加）
    assert sum(r[k]["net_amount"] for k in ("dealer_self", "dealer_hedge", "trust", "foreign")) == \
        r["total"]["net_amount"]
    assert parse_insti_amount({"stat": "很抱歉，沒有符合條件的資料!"}, D(10, 31)) == []
    assert parse_insti_amount({"stat": "OK", "fields": ["單位名稱"], "data": [["合計"]]}, D(10, 30)) == []


def test_insti_official():
    days = [D(9, 1) + timedelta(k) for k in range(25)]
    nets = [5e8] * 21 + [-1e8, -2e8, 0, -3e8]
    amount = {d: {"foreign": v, "foreign_dealer": 0, "trust": 1e8, "dealer_self": -2e7, "dealer_hedge": -3e7,
                  "total": v + 5e7} for d, v in zip(days, nets)}
    o = _insti_official(amount)
    assert o["date"] == "2026-09-25" and o["d"][-1] == "2026-09-25"
    assert len(o["d"]) == len(o["f"]) == len(o["t"]) == 20
    assert (o["foreign"], o["trust"], o["dealer"], o["total"]) == (-3.0, 1.0, -0.5, -2.5)
    assert o["fs"] == -1                                       # 前一天差額 0 → 只連賣 1 日
    amount[days[-2]]["foreign"] = -1e8
    assert _insti_official(amount)["fs"] == -4
    assert _insti_official({}) is None


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"✅ {name}")
    print("全部通過")
```

## 附錄 C：給 Programmer 的提醒

1. **先執行 `python3 -m twstock setup-db`**；`export` 會查 `price_events`、`insti_amount`，沒建表會失敗。`04-dev.md` 要提醒使用者。
2. 補抓順序：`events`（約 40 秒）→ `history --only amount`（約 4 分鐘），不要同時跑。
3. `aggregate()` 多了第三個參數；個股頁所有呼叫都要傳（`draw()` 兩處）。`buildCharts()` 不再呼叫 `renderSignals()`。
4. `_changes` 取代原本的 `chs` 迴圈，`m[...] += 1` 與 `snapshot` 的 `ch`／`p` 都改用 `chs[-1]`；`daily[...]["pct"]` 不動。
5. `_f(_pct(...))` 等既有函式不變；`h52`／`l52` 改用 `_f` 四捨五入到 0.01。
6. 測試用埠 8001，結束時關閉；不要動 `.env`、不要 commit。

---

## PM 範圍調整建議

1. **新增櫃買除權息端點 `bulletin/exDailyQ`**（B1 上櫃路徑）。PM 假設「上櫃以官方漲跌反推即可、不打新端點」，但實測上櫃除權息日官方漲跌是文字，反推只抓得到減資、面額變更 29 筆，704 筆除權息（含 47 筆 >10% 跳空）會漏掉。新端點一年只需 2 次請求、每日 1 次。
2. **B1 驗收 4**：5904 52 週低改為 **37.77**（PM 的 39.25 沒算到 7/16 除息）。
3. **B1 驗收 5**：3086 2026-04 月線還原後是 **+33.10%**（真實漲幅），無法「< 20%」；改為「等於本文件數值、與日線還原價一致」。5904 週線 +9.72% 符合原條件。
4. **A2 外資口徑**：外資 = 外資及陸資（不含外資自營商）。外資自營商已含在自營商，合計列也不含它；照 PM 寫法會重複計算。
5. **MA／MACD 線條隨「還原／原始」切換**，只有技術訊號卡與 52 週高低固定用還原價（PM 建議全部固定用還原價；原始模式下會出現均線脫離 K 棒）。
6. **異常係數防護改為 0.02～20**（PM 建議 0.05～20，6949 面額變更係數正好 0.05）。
7. **P14 事件分支兩市場共用**：上櫃除權息日原本 `ch` 為 null、算平盤，同一個判斷式一併修正。停止買賣後恢復交易（1435、8105）仍顯示「不比價」。
8. **P16 選「事件日起 90 天」**，理由見 P16-2。
9. 待辦建議：板塊漲跌幅（`daily[...]["pct"]`，泡泡圖顏色）仍用官方漲跌，上市除權息日會是 0，建議第 3 輪改用 `chs`（一個變數）。
