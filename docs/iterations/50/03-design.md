# 第 50 輪｜System Analyst：設計

- 撰寫日期：2026-11-25（週三，實測於 23:53 台北時間）；資料日 2026-11-25（`latest.json` `date` = `flow_date` = 2026-11-25）。
- 依據：`50/01-analyst.md`（R73、Q50-1）、`50/02-pm.md`（二之一逐字規格、驗收 27 條、Q50-8；D186 = A、D187 = A；PM 自行決定 14 點全照 PM）。
- 產出：本檔＋`50/03-design.diff`（632 行；在專案根目錄 `git apply --check docs/iterations/50/03-design.diff` 已通過）。
- 做法：
  - `rsync -a --exclude .git --exclude .env --exclude _backups --exclude _archive --exclude logs` 把專案（含 `site/data`）複製到 scratchpad `r50sa/`（**副本沒有 `.env`**），`git init` 並 commit 當基準；修改都在副本，diff 由副本 `git diff` 產生（新檔用 `git add -N`）。另把 HEAD 的 7 個檔 `git archive` 到 `r50sc/` 再 `git apply`，結果和副本逐 byte 相同。
  - 改前 `tests/test_iter01～49` 全過；改後 `test_iter01～50` **50 個檔全過**，分別在「匯出前資料」（`r50sb/`，`site/data` 為專案現況的唯讀複本）與「副本 export 後資料」（`r50sa/`）兩種資料下各跑一次。
  - 副本 export（驗收 6、18 的端到端確認）：腳本只借專案 `config._load_env` 把連線設定載入行程內環境變數（**沒有讀、印、複製 `.env`**），import 的是副本的 `twstock`（`SITE_DATA_DIR` 已確認在副本內）；DB 連線包一層，`execute` 只允許 `SELECT`／`WITH`、`commit()` 直接拋錯。export 成功 35 秒，0 外部請求、0 寫入。
  - 資料庫：只有唯讀 SELECT（`market_breadth` 10/01 起、8 檔 `etf_holding_summary`＋`etf_daily`、`INFORMATION_SCHEMA.TABLES` 表數 31）。
  - 外部請求：只有 D184 的 2 次（第六節）。沒有用 8000／8001／8002、沒有開瀏覽器（畫面驗收留給 QA）、沒有執行 `_archive/`。
  - 專案目錄只新增本檔與 `03-design.diff`。

---

## 一、改了哪些檔（`git diff --numstat`）

| 檔案 | 加／減 | 內容 |
|---|---|---|
| `twstock/export.py` | 30／3 | `from decimal import ROUND_CEILING, ROUND_FLOOR` 1 行（新行）；`limit_flag` 18 行（`_tick_round` 之後）；`snapshot` `lm` 1 行；匯出訊息 4 行；`holding_export` 簽名＋註解＋`sum` 1 行；`:1749` 呼叫處 |
| `site/app.js` | 6／3 | `pctCell` 註解 1 行＋`:30` 改 1 行；排行說明 1 行；選股 `lm` 1 行；持股頁 `:1598`、`:1613` 各改 1 行 |
| `site/stock.js` | 1／0 | 頁頭 1 行 |
| `site/index.html` | 2／2 | `app.js`、`stock.js` 的 `?v=` |
| `tests/test_iter50.py`（新） | 422／0 | 12 個測試、20 個反證 |
| `tests/test_iter49.py` | 1／1 | D186 同意的 `:261` 1 行 |
| `README.md` | 2／0 | 測試指令 1 行、第 50 輪一段 |
| `docs/iterations/README.md` | 1／0 | 第 50 輪一行（PG／QA 之後補） |

- 0 變更：`app.css`、`tools.js`、`help.js`、`compare.js`、`twstock/collectors/`、`db.py`、`health.py`。

## 二、程式設計

### 2-1 `limit_flag`（`export.py:258`，R73）

```python
def limit_flag(close, change, new=False):
    """（docstring 同 PM 二之一 A-2）"""
    if close is None or change is None or new:
        return None
    c = Decimal(str(close))
    ref = c - Decimal(str(change))
    if ref <= 0:
        return None
    for sign, k, rnd in ((1, Decimal("1.1"), ROUND_FLOOR), (-1, Decimal("0.9"), ROUND_CEILING)):
        x = ref * k
        tick = next(t for limit, t in _TICKS if x < limit)
        if c == (x / tick).quantize(Decimal(1), rounding=rnd) * tick:
            return sign
    return None
```

- 升降單位取「參考價 × 1.1（或 × 0.9）」取整前所在級距；PM 已確認和「取整後再看級距」結果相同。
- `close` 收 `Decimal`（snapshot 的 `c[-1]`）或 float 都可；全部走 `Decimal(str(x))`。
- `ROUND_FLOOR`／`ROUND_CEILING` 用新增的一行 import（既有 `from decimal import ROUND_HALF_UP, Decimal` 不動）。

### 2-2 `snapshot`（`export.py:1920`，`rel` 之後）

PM 逐字：`**({"lm": lm} if (lm := None if no_trade else limit_flag(c[-1], chs[-1], d_[0] > db_first and len(d_) <= 5)) else {}),   # 第 50 輪 F50-1（R73）：收在漲停 1、跌停 -1`。`_tick_round`、`_changes`、`_side` 0 行改動（新測試以 sha1 鎖住）。

### 2-3 匯出訊息（`export.py:2049～2052`，「📌 還原事件」之後）

```python
    lm_n = lambda m, v: sum(x["m"] == m and x.get("lm") == v for x in snapshot.values())   # 第 50 輪 F50-1：本站推算家數
    lm_o = lambda m, k: "--" if (official_breadth.get(m) or {}).get(k) is None else official_breadth[m][k]   # 官方家數（沒有 → --）
    print(f"  📌 收在漲停 上市 {lm_n('TWSE', 1)}／上櫃 {lm_n('TPEx', 1)}、跌停 上市 {lm_n('TWSE', -1)}／上櫃 {lm_n('TPEx', -1)}"
          f"（本站推算；官方 漲停 上市 {lm_o('TWSE', 'ul')}／上櫃 {lm_o('TPEx', 'ul')}、跌停 上市 {lm_o('TWSE', 'dl')}／上櫃 {lm_o('TPEx', 'dl')}）")
```

副本 export 實際輸出：`📌 收在漲停 上市 4／上櫃 3、跌停 上市 46／上櫃 54（本站推算；官方 漲停 上市 4／上櫃 3、跌停 上市 46／上櫃 54）`。

### 2-4 `holding_export`（F50-12）與 `:1749`

```python
def holding_export(code, dates, summary, held, tw, name, market, close=None):
    """（原 docstring）"""
    # 第 50 輪 F50-12：close = 持股日收盤；有值且每單位淨值 > 0 時 sum 加 pc（收盤，元）、pm（折溢價 % = 收盤 ÷ 每單位淨值 − 1，正 = 溢價）
    ...
                    "fl": fl, "fa": _f(float(fa) / YI), **({"u1": u} if (u := unit_change(summary, dates)) is not None else {}),
                    **({"pc": _f(close), "pm": round((float(close) / float(nu) - 1) * 100, 2)} if close is not None and nu and nu > 0 else {})},
```

`:1749`（拆成 2 行）：`holding_export(code, hdates, summary, held, tw, *etf_names[code],` ＋ `close=dict(etf_px.get(code, ())).get(hdates[-1])))   # 第 50 輪 F50-12：持股日當天的收盤（沒有 → None，不拿別天補）`。不用 `last_close`。**def 行與 `sum` 那行是既有行，見第七節差異 1、D188。**

### 2-5 前端

- `app.js:29` 新註解；`:30` `pctCell` 有成交分支照 PM A-3 逐字，行尾仍是 `</td>\`;`、沒有註解、沒有引用新常數。
- `app.js:1018`（`:1016` 的 `dv` 行與 `:1017` 之間；`:1016` 原字不變）排行說明、`:1232`（`p` 之後、`r5` 之前）選股 `lm` 條件、`:1601` 每單位淨值卡第三欄、`:1616` 說明句：全部照 PM 逐字。
- `stock.js:299`（原 `:298` 與 `:299` 之間）：PM A-4 逐字。

### 2-6 `index.html`（`?v=` = `shasum` 前 8 碼）

| 檔案 | `?v=` |
|---|---|
| `app.js` | **692538e8**（原 54952a23） |
| `stock.js` | **da7fa6ff**（原 28633954） |
| `app.css`、`tools.js`、`help.js`、`compare.js` | ce1417aa、0a050889、a5a5a7e8、1c11197d（不變） |

`https://` 仍 2 個。PG 套用後若 `app.js`、`stock.js` 有任何一字不同，`?v=` 要重算。

## 三、測試設計（`tests/test_iter50.py`，不連網、不連資料庫）

沿用 `test_iter35._grab`、`test_iter34._node`／`HELPERS`、`test_iter05` 的持股假資料；用詞清單 = `test_iter47.ADVICE` ∪ `test_iter23.py:343～345`（從檔案讀，不重寫）。檢查函式都接受原始碼字串（Python 函式從改壞的 `export.py` 原始碼取出後在 `export` 模組名稱空間 `exec`），供反證重跑。

| 測試 | 內容 | 驗收 |
|---|---|---|
| `test_limit_flag` | PM 漲停 8 例、跌停 6 例（含 1.30 浮點陷阱）回傳 `1`／`-1`（型別 `int`，`Decimal` 收盤也可）；`new=True` 全部 None；`(92.8, -10.2)`、`(125.0, 10.5)`、None 輸入、`ref ≤ 0`（含 `(0, 0)`）→ None；原始碼用 `Decimal(str(…))`、`_TICKS`、不含 `float`；位置在 `_tick_round`、`_changes` 之間 | 1～4 |
| `test_snapshot` | `rel` 行之後緊接 PM 的 `lm` 行逐字；`limit_flag(` 只出現 2 次；`_tick_round`／`_changes`／`_side` sha1 不變；匯出訊息逐字＋用假 `snapshot`／`official_breadth` 執行，缺值寫 `--` | 5 |
| `test_data_1125` | 資料日 11/25 時：獨立用 `latest.json` 的 `c`、`ch` 與 `stocks/*.json` 第一筆日線套 `limit_flag` → 上市漲停 1598、2471、6614、7765，上櫃 3664、6140、7767；4 個家數 = `breadth.o` = 4／46／3／54；2313 = -1、6907、2330 沒有。已 export（有 `lm`）時再核對 `lm` = 獨立計算、`nt` 列沒有 `lm`、`etfs.rows` 沒有 `lm`、選股條件只套 `lm` → 7／100 檔；沒有 `lm` 時印「PG 套用後 export 再核對」 | 6、12 |
| `test_pct` | `pctCell` 單獨 grab（`HELPERS`＋`sgn`）在 node 跑 7 例逐字（漲停、跌停、沒有 `lm`、平盤、`null`、無成交誤帶 `lm`、`rel`＋`lm`）；最後一行 `</td>\`;`、不含 `//` | 8、9 |
| `test_head` | 頁頭行逐字在 PM 與 `stock.js`；位置在漲跌之後、`rel` 小字之前 | 10（字面） |
| `test_cond_note` | 條件行逐字、位置 `p` 之後 `r5` 之前；node 跑 `f`（`"1"`、`null` 不算）、`g`、`def`、chip 字；排行說明在 `:1016` 下一行、只出現 1 次；`SCREEN_GROUPS` 不變 | 11、12、13 |
| `test_holding` | 不傳 `close`／`close=None` → `sum` = `test_iter05` 的 dict；20.53／20.74 → `pc 20.53`、`pm -1.01`；8.87／8.49 → 4.48；7.02／7.02 → 0.0；`nu` 0 或 None → 沒有兩鍵；兩鍵在最後；`:1749` 的 `close=` 運算式用假 `etf_px` 執行：當天有收盤 → 該值，當天 None、沒有這天、沒有這檔 → None | 15、16 |
| `test_etf_data` | 資料日 11/25 且已 export 時：8 檔 `pm` = PM 值、`pc` = `etfp/{代號}.json` 持股日當天收盤、`sum` 鍵集合不多 | 18 |
| `test_holdings_page` | 假 DOM 在 node 跑 `renderHoldings`（node 14 沒有 `Array.prototype.at`，測試內補 polyfill；`app.js` 不改）：`-1.01`／`4.48`／`0`／沒有 `pm` 四種小字逐字、說明句只在有 `pm` 時出現、卡片不上色 | 17 |
| `test_words_node14` | 新增字串（`pctCell` 小字、條件、排行說明、淨值卡、說明句、頁頭、`export.py` 含「第 50 輪／本站推算／收在漲停」的行、README 段落）不含用詞清單；不含 `.at(` 等 | 20、21 |
| `test_version_and_docs` | 6 個 `?v=` = sha1、4 個不變值、舊 `app.js`／`stock.js` 值已不在、`https://` 2 個、README 指令與段落關鍵字、段落不含「第 23 輪」、`docs/iterations/README.md` 有第 50 輪 | 24 |
| `test_contrast` | 20 個反證 | 反證 |

### 反證清單（副本逐一確認都被擋下，並印出各自失敗原因）

| # | 改壞方式 | 擋下的檢查 |
|---|---|---|
| 1 | `x = Decimal(str(float(ref) * float(k)))`（float 乘法） | `check_limit`（1.30 例） |
| 2 | 級距改看參考價 | `check_limit` |
| 3 | 捨去／進位對調 | `check_limit` |
| 4 | 漲停改四捨五入 | `check_limit` |
| 5 | 不排除新上市 | `check_limit` |
| 6 | 拿掉 `ref ≤ 0` | `check_limit`（`(0, 0)`） |
| 7 | 新上市條件拿掉 `d_[0] > db_first` | `check_snapshot` |
| 8 | 無成交也呼叫 | `check_snapshot` |
| 9 | 官方缺值寫 0 | `check_snapshot` |
| 10 | `pctCell` 引用新的頂層常數 | `check_pct`（node `ReferenceError`） |
| 11 | 無成交也加小字 | `check_pct` |
| 12 | `pctCell` 行尾加註解 | `check_pct` |
| 13 | `x.lm == v` | `check_cond` |
| 14 | 條件放到 `r5` 之後 | `check_cond` |
| 15 | 不傳 `close` 也輸出 `pc`／`pm` | `check_holding` |
| 16 | 淨值 ÷ 收盤（倒過來） | `check_holding` |
| 17 | `:1749` 改用 `last_close` | `check_close` |
| 18 | `0` 寫成「溢價」 | `check_holdings_page` |
| 19 | 沒有 `pm` 也寫說明句 | `check_holdings_page` |
| 20 | 排行說明混入用詞清單中的詞 | `check_words` |

- 驗收 7（歷史 34 天）需要 `market_breadth`，測試不連資料庫，所以不放進 `test_iter50`；SA 已在副本做（第四節），QA 再做一次。

## 四、歷史核對與 11/25 實際資料

### 4-1 歷史 34 個市場日（11/03～11/25 × 上市／上櫃）

用副本 `limit_flag`＋`stocks/*.json` 的 `prices.c`、`prices.ch`（匯出的漲跌）＋新上市條件（第一筆 > 2025-10-30 且列數 ≤ 5），對唯讀 SELECT 的 `market_breadth`：**31／34 完全相同**，和 PM 數字一致；差異 3 天各 1 檔：

| 日期 | 市場 | 本站（漲停, 跌停） | 官方 |
|---|---|---|---|
| 11/09 | 上市 | (122, 2) | (121, 2) |
| 11/18 | 上市 | (21, 3) | (21, 4) |
| 11/24 | 上市 | (336, 4) | (335, 4) |

### 4-2 11/25

- 獨立計算與副本 export 後 `latest.json` 的 `lm` 完全相同：上市漲停 1598、2471、6614、7765；上櫃 3664、6140、7767；跌停上市 46、上櫃 54；四個數 = `breadth.o`。2313 = -1，6907、2330 沒有；`nt` 列 0 檔有 `lm`；`etfs.rows` 0 檔有 `lm`。
- 8 檔主動 ETF `pm`（副本 export 後 `etfs/*.json`，也和 DB 唯讀計算相同）：00403A −0.93、00411A 3.07（持股日 11/24）、00415A 0.47、00981A −1.01、00982A −0.47、00988A 1.58（11/24）、00992A −0.43、00997A 4.48（11/24）——**全部和 PM 相同**；00403A 11/20 淨值 7.02、收盤 7.02 → 0.00。`sum` 其他鍵和改前相同。
- 副本 export 後和專案現有 `site/data` 比：`latest.json` 只多 `lm`（另有 `status.exported_at` 不同），825,034 → 825,883 bytes（**+849 bytes**）；`etfs/` 8 檔只多 `pc`、`pm`；其他 JSON（含 2,000 個 `stocks/*.json`、`screen.json`）逐 byte 相同。

## 五、Q50-1 三天差 1 檔的原因、Q50-8

### 5-1 Q50-1

- **11/18 上市少 1 檔跌停：推測是 3593 力銘。** 11/16、11/17 無成交，11/18 收 8.60；本站走 `_changes` 分支 2（`rel`），參考價 = 最後成交收盤 9.68 → 跌停價 8.72，收盤 8.60 比跌停價還低，表示官方參考價不是 9.68。參考價 9.55 時跌停價正好是 8.60。推測：連續無成交時，官方次一日的開盤競價基準會依最後揭示的買賣申報價調整（依記憶的交易規則，**未查證**），本站沒有這筆資料。影響：連續無成交後第一個成交日可能少標（不會多標）。
- **11/09、11/24 上市各多 1 檔漲停：原因沒有找到。** 已排除：
  - 創新板：本站有算進，若官方不算，11/13、11/20 等多天會差很多檔，所以官方也有算。
  - 跨級距：差異日和相同日都有很多跨級距的股票。
  - 非 4 碼代號、前一日無成交、5 日內事件：差異日都沒有能單獨解釋的。
  - 差異日的漲停股都是「最高 = 收盤」。
- 只能列出候選：6924 榮惠-KY創（11/09、11/24 兩天都在本站漲停名單；11/09 開高低收都是 130.5、量 12 張），以及 1435 中福（11/24 量 14 張）。要確認需要官方逐檔的漲跌停標記（要另發請求，本輪不做）。
- 處理：說明與 `title` 已寫「本站推算，和官方家數偶爾差 1 檔」；新的匯出訊息每晚會並列推算家數與官方家數，上線後連看 5 個交易日（PM 第三節）。
- 邊界補充（PM 二之五「含現金增資的除權日」）：近一年本站事件中含現增的有 112 筆（「權」只有現增 101、「權息」股利＋現增 11）；其中事件日漲跌幅 > 10% 的有 6 筆：2464 9/02、3691 10/27、4991 2025-12-22、7610 7/13、6225 8/18（+62.4%）、6834 10/02。這些日子不會被標（可能漏標，不會誤標）。

### 5-2 Q50-8 減資、面額變更、轉上市是否也沒有漲跌幅限制（只依文件、既有知識與本站資料，不發請求）

- **減資、面額變更換發新股恢復買賣：本站資料顯示仍有 ±10% 限制。** 21 筆「減」、3 筆「面」事件，事件後 5 個交易日內用 `limit_flag` 剛好收在推算漲跌停價的有 16 次。例如：
  - 7780 面額變更後 4 天連續收在推算漲停價。
  - 2380 減資後 5 天內 4 次收在漲跌停價。
  - 6949 面額變更後 3 次收在跌停價。
  - 另有 8422、3593、1516、2323、8103。
  若沒有漲跌幅限制，連續幾天剛好停在推算價的機率很低；所有事件後 5 日漲跌幅也都沒有超過 10.2%。依既有知識，這兩種恢復買賣以官方公告的參考價計算 ±10%（未查證規章原文）。**結論：不比照新上市排除，本輪不改。**
- **上櫃轉上市：依既有知識（未查證）不屬於「新上市前 5 日無漲跌幅」，仍有 ±10% 限制。** 本站 `stocks` 只有目前市場，資料看不出哪些是轉上市。若轉上市後日線換成新的序列（第一筆晚於 `db_first`），前 5 天會被當成新上市而不標，結果可能漏標、不會誤標。34 天比對中沒有相關差異。F50-5 取得上市日期後再確認。
- 興櫃轉上市（上櫃）就是新上市，前 5 日無漲跌幅限制，已經由新上市條件涵蓋。處置股、全額交割股、創新板仍是 10%，照常判斷。

## 六、D184 重大訊息實測

- 執行前 `pgrep -fl twstock` 只有使用者的 `twstock serve`（8000），沒有 collect／export。
- 用 `twstock.fetch.request("GET", url, expect_json=False, isolated=True)`。`isolated=True` 讓失敗不重試，確保每個網址最多送出 1 次；預設 `request` 失敗會重試 3 次，可能超過 PM 上限。
- 原始回應只存在 scratchpad `r50w/d184/raw0.bin`、`raw1.bin`，專案目錄沒有。
- 解析用 `python3 -I`。

| # | 項目 | 上市 `openapi.twse.com.tw/v1/opendata/t187ap04_L` | 上櫃 `www.tpex.org.tw/openapi/v1/mopsfin_t187ap04_O` |
|---|---|---|---|
| 1 | 時間、狀態、型別、大小、送出次數 | 2026-11-25 23:53:03（台北）、HTTP 200、`application/json`、166,055 bytes、`request_count()` 前後差 **1** | 23:53:03、HTTP 200、`application/json`、98,308 bytes、差 **1**（合計 **2 次**） |
| 2 | 筆數、日期、一檔多筆 | 94 筆；`發言日期` 全部 1151124（只有前一天），`出表日期` 1151125；69 家，12 家一天多筆、最多 9 筆 | 57 筆；`發言日期` 全部 1151124，`Date` 1151125；56 家，1 家 2 筆 |
| 3 | 欄位（原文）、型別 | `出表日期`、`發言日期`、`發言時間`、`公司代號`、`公司名稱`、`主旨 `（**欄名結尾有一個空白**）、`符合條款`、`事實發生日`、`說明`，全部字串 | `Date`、`發言日期`、`發言時間`、`SecuritiesCompanyCode`、`CompanyName`、`主旨`、`符合條款`、`事實發生日`、`說明`，全部字串 |
| 3 | 日期、時間格式 | 民國 7 碼 `YYYMMDD`；時間 `HHMMSS`、有秒、**沒有前導 0**（例 `70004` = 07:00:04，5～6 碼） | 同左 |
| 4 | 有沒有各欄 | 代號、名稱、發言日期與時間、主旨、符合條款（例「第51款」）、事實發生日、說明全文都有 | 同左（欄名不同） |
| 5 | 字數（最短／中位數／最長） | 主旨 6／25／87；說明 67／416.5／1,899 | 主旨 11／23／69；說明 176／293／2,637 |
| 5 | 說明是否全文 | 是，分點的全文（「1.事實發生日…」）；依 R79 之後只存標題、日期、類別 | 同左 |
| 6 | 官方單筆連結 | 沒有連結或序號欄；`說明` 內含 http 的 1 筆 | 沒有；`說明` 內含 http 的 2 筆 |
| 7 | 能否帶日期查歷史 | 回應只有前一天，沒有日期參數或分頁欄位（沒有另外發請求試）→ 視為不能回補（同 R78） | 同左 |
| 8 | 大小估算 | 兩市場 151 筆／天；只存 `{代號, 日期, 時間, 主旨}` 的 JSON 約 **20 KB／天**（每筆約 136 bytes）；DB 一年約 5～7 MB。匯出近 30 天約 4,500 筆、約 **600 KB**，不適合放 `latest.json`（目前 825 KB）；放個股 JSON 平均每檔約 2 筆、約 **0.3 KB**，一天多筆的公司可到數 KB | |
| 9 | 樣本（代號、主旨字數／說明字數、主旨前 15 字） | 2072：72／456「公告本公司名稱由「世紀離岸風電」；6988：23／198「本公司受邀參加群益金鼎證券舉辦」 | 3489：66／530「公告本公司名稱由「森寶開發股份」 |
| 10 | SA 看法 | 見下 | |

- 其他觀察：
  - 23:53 抓到的是 11/24 的發言，11/25 的還沒出現。資料集看起來是隔天出表，晚上收集會拿到前一個交易日的資料。
  - `事實發生日` 有 1 筆 1201123（民國 120 年），是資料本身的異常。
  - TWSE 的 `主旨 ` 欄名結尾有空白，收集時要照原文取。
- SA 對 F22-7 的看法：
  - 官方只給前一天、不能回補，晚一天開始收就少一天。可以考慮先每天 2 次請求、只存標題（不畫畫面），請使用者在之後的輪次決定（PM 併入第三節 F22-7）。
  - 新表欄位草案（只寫在文件、不建）：`material_news(news_id INT IDENTITY PK, stock_code VARCHAR(6), market CHAR(4), speak_date DATE, speak_time TIME(0), subject NVARCHAR(200), clause NVARCHAR(10), fact_date DATE NULL, fetched_at DATETIME2)`。
  - 唯一鍵建議用 `(stock_code, speak_date, speak_time, clause)`：同一家公司一天最多 9 筆，TWSE 94 筆中發言時間有 93 種，所以只用時間可能撞。
- DB 表數：唯讀 `INFORMATION_SCHEMA.TABLES` = 31，本輪沒有建表。

## 七、和 PM 規格的差異（逐點）

1. **`export.py` 除了 `:1749` 還改了 2 個既有行**：
   - `holding_export` 的 def 行加 `close=None`。
   - `sum` 那行行尾的 `}` 移到新的一行。
   PM 二之一開頭要求「只新增行，除 `:1749` 外既有行不改」，但 B-1 指定的簽名 `holding_export(…, close=None)` 一定要改 def 行，`sum` 加鍵也要動那行的結尾，兩者互相矛盾。已 grep `tests/`：沒有測試逐字鎖這兩行，50 個測試全過。→ **D188**。
2. `:1749` 拆成 2 行（原行改、續行新增），新增 `close=` 參數；行為同 PM。
3. 匯出訊息用 2 個 lambda＋1 個分兩行的 `print`（共 4 行，PM 估 1～2 行），文字是 SA 定的（PM 授權）。
4. `ROUND_CEILING`／`ROUND_FLOOR` 用新增的 import 行，既有 import 行不動。
5. 新測試 422 行（PM 估 150～200 行，上限約 580 行）：多出的是 11/25 實際資料、假 DOM 跑 `renderHoldings`、20 個反證。
6. 驗收 7（歷史比對）不放進 `test_iter50`（要連資料庫），由 SA 原型與 QA 做。
7. D184 用 `isolated=True`、`expect_json=False`（說明見第六節），比 PM 寫的 `request("GET", url)` 更保守。
8. 其餘文字、位置、條件、`?v=` 和 PM 二之一逐字相同。

## 八、套用順序（PG）

1. `git apply docs/iterations/50/03-design.diff`。
2. `shasum site/app.js site/stock.js` 前 8 碼應為 `692538e8`、`da7fa6ff`（和 `index.html` 相同）。
3. `for f in tests/test_iter*.py; do python3 $f >/dev/null 2>&1 || echo FAIL $f; done` 沒有輸出（這時 `test_iter50` 會印「還沒有 lm／pm：PG 套用後 export 再核對」）。
4. D187：`python3 -u -m twstock export`。訊息應有 `📌 收在漲停 上市 4／上櫃 3、跌停 上市 46／上櫃 54（本站推算；官方 …相同）`（資料日仍是 11/25 時）。
5. 再跑一次 `python3 tests/test_iter50.py`：不應再印「還沒有」，會核對 `lm` 與 8 檔 `pm`。

## 九、需要使用者決定的事項

### D188 `holding_export` 要改 2 個既有行（PM 規則「只新增行」與 B-1 簽名互相矛盾）

| 選項 | 內容 | 影響 |
|---|---|---|
| **A（預設）** | 照 PM B-1：def 行加 `close=None`、`sum` 那行行尾 `}` 移到新的一行（本 diff 的做法） | `export.py` 既有行改 3 行（含 `:1749`）；沒有測試鎖這 2 行，50 個測試全過；驗收 5 的「`export.py` 只新增行」改讀為「除 `:1749` 與 `holding_export` 這 2 行」 |
| B | 不改 `holding_export`，另寫新函式（例 `holding_premium(H, close)` 在回傳的 `sum` 後面加 `pc`／`pm`），`:1749` 改成 `holding_premium(holding_export(…), close)` | `export.py` 只改 `:1749`；但和 PM B-1 簽名、驗收 15 的寫法不同，`test_iter50` 要改測新函式，約多 6 行程式 |

- 預設 A：這是 PM 規格本身就需要的改動，改的是簽名和字典結尾，行為只在傳 `close` 時改變；B 多一層函式，只是為了遵守「只新增行」的形式。
- **決定（2026-11-26）：A**。使用者指示各角色完成後依建議進入下一步，因此照 SA 預設 A；PG 原樣套用本 diff。

## 十、疑慮

- Q50-1 的 11/09、11/24 原因沒有找到（第五節），上線後看每晚匯出訊息。
- 11/18 的推測（無成交後參考價依最後揭示買賣價調整）沒有查證規章。
- 舊程式 `app.js:1616` 本來就有「買進」「加碼」字樣（既有說明「由經理人買進股票」「加碼會偏多」），本輪在同一行後面加字，所以 diff 的這一行含這兩個詞；新加的字串本身 0 命中，`test_iter41/42` 的既有用詞檢查也通過。
- 畫面驗收（驗收 10 畫面、14、26、27）SA 沒有開瀏覽器，留給 QA。
- `docs/iterations/README.md` 第 50 輪那一行只寫到設計，PG／QA 之後補。
