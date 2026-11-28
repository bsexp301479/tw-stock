# 第 53 輪｜System Analyst：設計

- 撰寫日期：2026-11-28（週六）；實測於 11/28 12:13（台北時間，使用者 11:34 決定改在週六立刻實測）；網站資料日 2026-11-27。
- 依據：`53/01-analyst.md`（R98～R108、Q53-1～Q53-10）、`53/02-pm.md`（二之一逐字規格、二之二資料契約、驗收 52 條；D222～D236 全 A；PM 自行決定 25 點全照 PM）。
- 產出：本檔＋`53/03-design.diff`（1,344 行；在專案根目錄 `git apply --check docs/iterations/53/03-design.diff` 已通過）。
- 結論：**實測沒有觸發停止條件**（第一節），照 PM 規格做完原型；舊測試 0 行。
- 做法：
  - `rsync -a --exclude .git --exclude .env --exclude _backups --exclude _archive --exclude logs` 把專案複製到 scratchpad `sa53/`（**副本沒有 `.env`**），原型在副本上改；另留一份未改的 `sa53orig/` 產生 diff。
  - diff 用 `diff -u` 對 `a/`、`b/` 逐檔產生（新檔對 `/dev/null`）。另把未改副本再複製成 `sa53c/` 後 `git apply`，和 `sa53/` 逐檔相同（`diff -rq` 沒有輸出），在 `sa53c/` 跑 `test_iter03`、`test_iter43`、`test_iter52`、`test_iter53` 都通過。
  - 改前 `tests/test_iter01～52` 全過；改後 `test_iter01～53` **53 個檔全過**（`for f in tests/test_iter*.py; do python3 $f …` 沒有 FAIL）。測試全用假資料，沒有連資料庫。
  - 資料庫：只有唯讀 SELECT（`stocks` 代號 2,001 個、`OBJECT_ID('material_news')` = NULL；另用目前程式的純函式 `make_plan` 預估週六 catch-up 會排哪些資料集，見第七節）。
  - 外部請求：**實際送出 3 次**（`fetch.request_count()` 前後差 = 3），全部經 `twstock.fetch.request(…, isolated=True)`。
  - 預覽：另複製 `site/` 到 scratchpad `sa53p/`，只在預覽副本的 `latest.json`、`stocks/2330.json` 放入 `mn`（今日卡用實測回應組成、個股卡用自製假主旨），以 `python3 -m http.server 8001 --bind 127.0.0.1` 看 1024 與 375 寬；看完已關（`lsof -i :8001`、`:8002` 沒有輸出）。8000 沒碰；localStorage 已恢復為 `{"tw.todayTab":"ov","tw.stockTab":"k"}`，視窗已設回 preset desktop。
  - 專案目錄只新增本檔與 `03-design.diff`。

---

## 一、第 53 輪實測（D222）

### 1-1 請求紀錄

執行前 `pgrep -fl twstock` 只有使用者的 `serve`（沒有收集在跑）；週六沒有排程時段。腳本在 scratchpad `r53s/probe.py`，原始回應存在 scratchpad `r53/`（不在專案目錄、沒寫 DB）。

| 次 | 時間 | 請求 | 結果 |
|---|---|---|---|
| 1 | 12:13:39 | `GET https://openapi.twse.com.tw/v1/opendata/t187ap04_L` | HTTP 200、`application/json`、195,485 bytes、JSON 陣列 **107 筆**、74 家 |
| 2 | 12:13:39 | `GET https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap04_O` | HTTP 200、`application/json`、138,526 bytes、JSON 陣列 **57 筆**、49 家 |
| 3 | 12:13:40 | `POST https://mopsov.twse.com.tw/mops/web/ajax_t05st02`（`encodeURIComponent=1&step=1&firstin=1&off=1&TYPEK=all&year=115&month=11&day=27`） | HTTP 200、`text/html`、2,653 bytes；**沒有表格**，頁面只有一句「資料庫中查無需求資料」 |

- 第 1、2 次都通過檢查（是陣列、必要欄齊、出表日期可解析），所以照順序送了第 3 次。
- 停止條件檢查：戊（第 1 次失敗）、己（第 2 次失敗）、辛（缺必要欄）、壬（缺出表日期或解析不到）**都沒有發生**。

### 1-2 欄名（每個鍵用 `repr`，順序照回應）

| 市場 | 鍵 |
|---|---|
| 上市 | `'出表日期'`、`'發言日期'`、`'發言時間'`、`'公司代號'`、`'公司名稱'`、`'主旨 '`（**結尾仍有一個空白**）、`'符合條款'`、`'事實發生日'`、`'說明'` |
| 上櫃 | `'Date'`、`'發言日期'`、`'發言時間'`、`'SecuritiesCompanyCode'`、`'CompanyName'`、`'主旨'`、`'符合條款'`、`'事實發生日'`、`'說明'` |

- 和 `50/03-design.md` 第六節完全相同，二之二 A 表欄名對照照用（A-1 結果庚不適用）。全部欄位值都是字串。

### 1-3 日期、筆數與 Q53 的答案

| 項目 | 上市 | 上櫃 |
|---|---|---|
| 出表日期（全部值） | `1151128`（**週六當天**）×107 | `Date` = `1151127`（週五）×57 |
| 發言日期（每天筆數） | `1151127`（週五）×107 | `1151126`（週四）×57 |
| 發言時間長度 | 6 碼 106、5 碼 1（`92041`）；沒有非數字寫法 | 6 碼 55、5 碼 2（`70003` ×2）；沒有非數字寫法 |
| 主旨字數 最短／中位數／最長 | 6／28／97 | 10／23／78 |
| 主旨含換行 | 34 筆 | 17 筆 |
| 符合條款前 5 名 | 第12款 28、第20款 22、第51款 13、第6款 12、第14款 6 | 第12款 19、第53款 9、第8款 6、第35款 5、第11款 4 |
| 主旨含「更正」／「補充」 | 2／7 | 3／1 |
| 代號不在 `stocks` | 0 | 0 |
| 一家多則 | 18 家（最多 1 家 9 則） | 7 家（最多 1 家 3 則） |
| 事實發生日 空白／解析不到／晚於發言日 1 年以上 | 0／0／0 | 0／0／0 |
| `(代號, 日, 時, 主旨)` 完全相同的組數 | 0 | 0 |
| `(代號, 日, 時)` 相同但主旨不同 | 0 | 0 |
| 主旨含 `< > & " '` | 0 | 0 |
| 主旨含禁用詞清單的字詞（只記筆數） | 0 | 3 |
| 代號長度 | 全部 4 碼、沒有前後空白 | 全部 4 碼 |
| 名稱最長 | 7 字 | 6 字 |

- **Q53-1**（出表日期何時換日）：只能記錄這個時點——週六 12:13，上市已是週六的出表（內容是週五的發言），上櫃仍是週五的出表（內容是週四的發言）。換日的時刻仍未知，留待上線後觀察。
- **Q53-2**（週一晚上的發言日）：使用者改在週六實測，週一的情況未觀察（使用者說「週一出表的情況等上線後再看」）。週六看到的是：**上市以日曆天出表**（週六出表、內容是前一天週五）；**上櫃晚一個交易日**（週六中午仍是週五出表、內容是週四）。
- **Q53-3**（依日期查詢）：推測端點回 200 但「查無需求資料」，不能用；沒有換網址、沒有重試（A-1 結果卯）。頁面不是封鎖頁。
- **Q53-4**：見上表（條款前 5 名、更正／補充筆數）。
- **Q53-5**：0 筆代號不在 `stocks`。
- **Q53-7**：事實發生日沒有異常值（`1201123` 這種情況本次沒有出現，仍照規格處理）。
- **Q53-9**：最長 97 字，遠低於 400（A-1 結果子不適用）。
- **Q53-6、Q53-8、Q53-10**：本次無法回答，維持待辦。

### 1-4 屬於 A-1 的哪一種結果與處理

| 結果 | 是否發生 | 處理 |
|---|---|---|
| 甲／乙 | **上市接近乙**（週五的發言在週六出表）；上櫃兩者都不是（週六仍是週四的發言） | 不停。規格照用；照 D224 = A 揭露：排程週六幾乎不跑，上市週五的發言可能漏收（要看週一晚上上市資料集的內容才知道，見第九節）。週末排程留給下一輪（F53-延伸e）。「前一天」的文字對上櫃不成立，另提 D237 |
| 丙 | 否（各市場都只有一個發言日） | 程式仍支援多日 |
| 丁 | 否 | fixture 用實測回應 |
| 戊、己、辛、壬 | 否 | — |
| 庚 | 否（欄名完全相同） | — |
| 癸 | 否 | — |
| 子 | 否（最長 97） | — |
| 丑 | 否（0 組） | 去重照做 |
| 寅 | 否 | — |
| 卯 | **是**（查無資料） | 只記錄；「不能回補」的前提維持 |
| 辰 | 否（差 = 3） | — |

### 1-5 fixture（只刪列；唯一例外：`說明` 的值改成空字串）

| 檔案 | 列數 | 留了什麼 |
|---|---|---|
| `tests/fixtures/t187ap04_L_mini.json` | 8 | 同一家同一天 3 則（8499）、5 碼時間 `92041`、事實發生日晚於發言日的列（`1151201`、`1151130`、`1151203`）、`"主旨 "` 鍵保留尾空白 |
| `tests/fixtures/mopsfin_t187ap04_O_mini.json` | 8 | 同一家同一天 3 則（8042）、5 碼時間 `70003` 兩則、事實發生日早於發言日的列 |

- 沒有的種類（兩份都沒有）：事實發生日異常（`1201123` 型）、代號不在 `stocks`、主旨含 `< > & " '`——實測回應本身沒有，這些情況改由 `test_iter53` 以組字的假列測試。
- 挑列時排除主旨含禁用詞清單（含「強」「弱」等單字）的列。其餘字元一字不改（JSON 以 UTF-8、`ensure_ascii=False` 寫出，換行等跳脫照 JSON 規則）。

---

## 二、改了哪些檔（diff 的 +／−；行號是目前專案檔案）

| 檔案 | +／− | 既有行改動 | 新增 |
|---|---|---|---|
| `twstock/collectors/news.py`（新檔） | +110 | — | `_time`、`parse_news`、`fetch_news`、`collect_news` |
| `twstock/collectors/catchup.py` | +12／−3 | `:41` def 加 `news=None`；`:108` `plan_is_empty` 加 `or plan.get("news")`；`:269` 呼叫加 `news=news` | `:28` 匯入；docstring 1 行；`:54` 之後 `plan["news"]`；`execute_plan` 集保段落之後 5 行；`:251` 之後 `news_exists`；`:305` 之後 `changed` 一行 |
| `twstock/db.py` | +21／−1 | `:663` 訊息加 `material_news（第 53 輪）、` | `quarterly_balance` 那段之後 DDL 一段（含 2 行 Python 註解） |
| `twstock/health.py` | +57／−2 | `:428` def 加 `news=None`；`:561` 呼叫加 `news=news` | `load_state` docstring 1 行、`state["news"] = {}`、迴圈 2 行；`check_report` 2 行；`news_exists`、`news_state`、`news_gaps`、`news_line`（放在 `revenue_counts` 之前）；`run_check` 1 行 |
| `twstock/export.py` | +47 | 無 | `:29` 之後匯入 1 行；`_load_news`、`mn_export`、`news_note`（放在 `_load_balance` 之前）；`:1896` 之後 2 行；`:2005` 之後 1 行；`:2189` 之後 2 行；`:2217` 之後 1 行 |
| `site/stock.js` | +18 | 無 | `mnCard`、`mnShowAll`（`renderSignals` 之前）；`:401` 之後 1 行 |
| `site/app.js` | +50／−1 | `:232` `${alertBoard(L)}` 後接 `${newsBoard(L)}` | `:272` 之後 `mnWire();`；`newsBoard`、`mnGap`、`mnApply`、`mnWire`（`watchGrp` 之後、`breadthCard` 之前） |
| `site/index.html` | +2／−2 | `app.js?v=6cde9106` → `8437a8c1`、`stock.js?v=7c592b0f` → `d889075b` | — |
| `README.md` | +2 | 無 | 第 53 輪一行（接在第 52 輪資產負債表之後）、測試指令一行 |
| `docs/iterations/README.md` | +1 | 無 | 第 53 輪一行（PG／QA 完成後再補結果） |
| `tests/test_iter53.py`（新檔） | +572 | — | 第四節 |
| 2 個 fixture（新檔） | +90、+90 | — | 第 1-5 節 |

- 程式（不含測試、文件、fixture）新增約 **315 行**、改既有 7 行；新測試 572 行；**舊測試 0 行**。
- `app.css`、`help.js`、`tools.js`、`compare.js`、`fetch.py`、`daily.py`、`history.py`、`__main__.py` 0 行。
- `?v=`：`app.js?v=8437a8c1`、`stock.js?v=d889075b`（= `shasum` 前 8 碼）；`app.css?v=d1508f41`、`tools.js?v=0a050889`、`help.js?v=a5a5a7e8`、`compare.js?v=f7e0bca5` 不變。

---

## 三、程式設計

### 3-1 `collectors/news.py`（F53-1）

- `_URLS`、`_FIELDS = {"TWSE": ("公司代號", "公司名稱", "出表日期"), "TPEx": ("SecuritiesCompanyCode", "CompanyName", "Date")}`；發言日期、發言時間、主旨、符合條款、事實發生日兩市場同名。
- `parse_news(market, data) -> (出表日期, rows, 略過數)`：照二之二 B-1。
  - 不是 list → `SchemaError`；`[]` → `(None, [], 0)`；第一列不是 dict 或第一列（鍵 `strip()` 後）缺代號／發言日期／發言時間／主旨／出表日期 → `SchemaError("… 欄位不符：[原始鍵]")`。
  - 每列 `{k.strip(): v}`；**不讀 `說明`**。略過（計入略過數）：非 dict、代號空白或超過 10 字、主旨空白或超過 400 字、發言日期解析不到、時間不合法。
  - `_time`：1～6 碼數字 `zfill(6)`，或 `HH:MM:SS`；時 < 24、分秒 < 60。
  - 名稱、條款：空白或超過 40 字 → None；事實發生日：解析不到或晚於發言日超過 366 天 → None。
  - 出表日期：所有可解析值取最大；全部解析不到 → `SchemaError`；最小 ≠ 最大 → 印二之一 C 的 ⚠️ 一次。
  - 去重鍵 `(code, 發言日, 時間, NFKC＋casefold(主旨))`，同鍵留最後一列（保留第一次出現的位置）。
- `fetch_news` = `parse_news(market, request("GET", url, isolated=True))`。
- `collect_news(market, seen)`：`rows` 空 → 印「官方目前沒有資料」、回傳 None、0 個 SQL；否則一次 MERGE（二之二 B-2 原文，參數 `j, market, out_date, market, out_date, seen`）、`fetchall()` 數 `INSERT`、commit；`pyodbc.Error`（含連線失敗）→ `RuntimeError("material_news 寫入失敗（請確認已執行 setup-db）：第一行前 120 字")`。成功行與回傳值照二之一 C、二之二 B-2；`n` = 解析後（去重、略過之後）的筆數。

### 3-2 DDL 與 setup-db（F53-2）

- 二之二 A 的 DDL 全文，放在 `quarterly_balance` 那段之後、`sbl_trades` 之前；字串內不含 `quarterly_balance`、`twse_index`、`CREATE TABLE market_index`、`CREATE TABLE etf_events`（說明寫在字串外的 Python 註解）。不加索引。
- `setup-db` 訊息：`…quarterly_balance（第 52 輪）、material_news（第 53 輪）、"`；結尾 `twse_index（第 51 輪）、etf_holding_gaps")` 不變。

### 3-3 catchup（F53-3，二之二 C）

- `make_plan(…, *, share=None, news=None)`；`plan["news"] = [mk for mk in ("TWSE", "TPEx") if news and (mk not in (state.get("news") or {}) or state["news"][mk][1] < now.date())]`，放在 `if not days: return plan` 之前。
- `plan_is_empty` 加 `or plan.get("news")`；`plan_for_date` 不加鍵（`collect --date` 不抓）。
- `execute_plan`：集保之後 `for mk in plan.get("news") or ():`，`_guard(f"news.{mk}", …)`；成功且回傳不是 None 才寫 `undated["news"][mk]`。`news.*` 不在 `undated_errors` → 不算異常、不通知、沒有 ❌ 行。
- `_run_locked`：`news = health.news_exists(cur)`、`make_plan(…, share=share, news=news)`、`changed = changed or any(v.get("new") …)`。

### 3-4 health（F53-3，二之二 D）

- `load_state`：字面不改，另起 `state["news"] = {}`；迴圈內 `setdefault(mk, (on, t, d, n))`（新到舊，取最新）；仍只 1 個 SQL。
- `news_exists`（`row and row[0] is not None`）、`news_state(cur, since)` → `(表存在, {市場: (第一個發言日, 最新發言日, {發言日: 筆數}, 全部筆數)})`（**多了第 4 項「全部筆數」**，給匯出 📌 用，見第六節）、`news_gaps`、`news_line`（二之一 C 全部文字；漏收範圍 `today − 29 天`；`lag` = 從最新發言日隔天到今天之前最近的交易日之間的交易日數，`≥ 2` 才提示）。
- `check_report(…, *, share=None, news=None)`：`news` 不是 None 才在集保行（沒有集保時是預告行）之後加一行；回傳碼不受影響。`run_check` 傳 `news_state(cur, 今天 − 45 天)`。

### 3-5 匯出（F53-4，二之二 E）

- `news = news_state(cur, 資料日 − 45 天)`；有列時 `_load_news(cur, 資料日 − 29 天)`（SQL 照 E-1，`ORDER BY speak_date DESC, speak_time DESC, code, id`）。
- `mn_export(rows, mks, latest_date, closed) -> (各市場 {"f","w","x"}, {代號: [[發言日, "HH:MM", 主旨]]}, latest.mn 或 None)`：
  - `w` = 資料日 − 29 天；`x` = `news_gaps(該市場, f, l, w, closed)`；列沒有上限日（資料日之後的休市日發言也列）；不含條款、名稱。
  - `latest.mn`：`w` 之後**交易日**發言日的最大值為 `d`（D236）；`r` = 該日全部列 `[代號, 市場, "HH:MM", 主旨, 官方名稱]`（代號不在 `stocks` 也列）；`n` 每個有資料的市場都列（0 也列）；沒有交易日的列 → None（不輸出）。
- 個股 JSON：`nx` 之後 `**({"mn": {**mn_base[mk_], "r": mn_rows.get(code, [])}} if mk_ in mn_base else {})`——該股市場有任何列就輸出（0 則是 `[]`），`mn` 是最後一個鍵。`etf_export` 不動。
- `latest["mn"]` 放在 `latest["ixr"]` 之後；📌 `news_note(news, mn_base, mn_latest)` 印在 `bs_note` 之後、`✅ 匯出完成` 之前。

### 3-6 畫面（F53-5、F53-6，二之一 A、B）

- `stock.js`：`mnCard(M, code)` 照 A-2～A-6 逐字（D237 的文字見第八節）；`mnShowAll()`；`:401` 之後 1 行（ETF 與沒有 `data.mn` 不出現）。說明用變數傳入 `noteHTML(short, full)`，`test_iter13` 的字面呼叫數不變。
- `app.js`：`newsBoard(L)` 照 B-2～B-6；`mnGap(x)`；`mnApply()`（隱藏一律 `style.display`；`#mnNone` 兩種文字）；`mnWire()`（`#mnQ` input、`mnSeg`、`details.mn-box` toggle，最後 `mnApply()`）。狀態 `App.mnOpen`、`App.mnW`、`App.mnQ` 只存在 App。
- 預覽（第 0 節）：1024 寬個股卡是走勢分頁最後一個 `section`（`sec card mn`），12 則時先藏 2 則、按鈕「顯示全部 12 則」，按下後全部顯示、按鈕移除；今日卡預設收合，summary「發言日 11/27　上市 107 則　上櫃 尚未收到」，篩選 `8499` 剩 9 列、打字時焦點留在 `#mnQ`、無結果時顯示「沒有符合的重大訊息」；375 寬兩頁 `scrollWidth = innerWidth`；主控台沒有錯誤。

---

## 四、新測試 `tests/test_iter53.py` 與反證

| 測試 | 內容（驗收） |
|---|---|
| `test_fixture` | 兩份 fixture 的出表日期、筆數、略過數、第一列 7 個值；`"主旨 "` 尾空白；`說明` 值為空字串（3、4） |
| `test_fields` | 必要欄改名 → `SchemaError`；選填欄刪掉 → None；時間 8 種寫法；日期與事實發生日；型別；出表日期不一致的 ⚠️ 逐字（5～8） |
| `test_dedup` | 大小寫／全形視為同一則、留最後一列；非 dict 略過；長度界線（9） |
| `test_collect` | MERGE 字串、參數、`OUTPUT $action`、更新段不含 `first_seen`、JSON 沒有說明鍵；新增／更新筆數；空陣列 0 SQL；`pyodbc.Error` 文字；兩市場請求 = `("GET", 網址)`＋`isolated=True`；DDL 全文、位置、`setup-db` 訊息（10～12） |
| `test_plan` | `news=None/False/True`、出表 = 昨天／今天／明天、休市日 12/25、週六、週日；舊呼叫；`plan_for_date`；`plan_is_empty`（13、14） |
| `test_world` | 假世界（`test_iter03.World`＋`NewsCursor`）週六 10:00 第一次執行恰好多 2 個請求、匯出 1 次；12:00 再跑只抓上櫃（上市出表已是今天）、新增 0 不匯出；兩市場出表都是今天 → 0 個請求（16、17） |
| `test_isolation` | 上市回 500：回傳碼、項目、通知和表不存在時相同；`errors` 有 `news.TWSE`、上櫃照寫；⚠️ 逐字、沒有 ❌／Traceback、主機沒被標記；下一次只再抓上市（15） |
| `test_state` | 三筆紀錄取最新；`notices`、`tdcc_on` 不受影響（19） |
| `test_line` | `news_line` 各種逐字、`lag` 1／3、漏收＋`lag`、範圍邊界；`news_gaps` 休市日與起點；`check_report` 新行位置、`news=None` 逐字不變；`run_check` 表不存在、0 請求、0 寫入（20～23） |
| `test_export` | `mn_export` 手算（`w`、`x`、邊界 11/19、休市日 12/19 在個股 `r` 但不是 `d`、同一秒順序、5 元素）；`news_note` 4 種逐字；接線位置（24～29） |
| `test_card` | node 執行 `mnCard` 3 則逐字（含跳脫）、11 則／10 則按鈕、`mnShowAll`、0 則兩種、收錄說明 0／2／6 天；`:401` 之後那一行（30～36） |
| `test_board` | node 執行 `newsBoard`：summary、`尚未收到`、`open`、自選 0 檔沒有切換鈕、列 HTML（`<a>`／`<div>`）、收錄說明兩市場不同與漏收；`mnApply` 假 DOM：代號、英文大小寫、只看自選、`#mnNone` 兩種（37～39） |
| `test_words_node14` | 新程式與「第 53 輪」行、README 該行的用詞；node 14 語法（40、41） |
| `test_version_and_docs` | `?v=`、其他 4 個版本不變、`https://` 仍 2 個、README 與文件（42、43） |
| `test_contrast` | 28 個反證（下表） |

反證（改壞後對應檢查失敗）：欄名不 `strip()`、讀了說明、時間不補 0、事實發生日不檢查年份、出表日期取最早、去重不正規化、不是 `isolated`、MERGE 更新 `first_seen`、空陣列也回傳紀錄、`pyodbc.Error` 不包、比發言日不比出表日期、`<` 改 `<=`、`news` 加進 `undated_errors`、`changed` 那一行拿掉、`load_state` 取最舊、`lag` 門檻 ≥ 1、漏收算到休市日、窗口用 30 天、`d` 取含休市日的最新發言日、輸出條款、個股卡主旨不 `esc`、隱藏用 `hidden`、顯示全部不還原、自選 0 檔仍顯示切換鈕、今日卡主旨不 `esc`、篩選不分大小寫拿掉、用詞、node 14 語法。

- PM 列的「放在 `if not days` 之後」**沒有做成反證**：`due_days` 對 `n ≥ 1` 永遠回傳最近 n 個交易日（休市日也不是空），`if not days` 只在 `--days 0` 時成立，改了位置測不出差別（見第六節）。
- `test_iter53` 單檔約 2 秒（含 node）；測試資料中需要「主旨含禁用詞」的情況本輪沒有用到。

---

## 五、PM 驗收 52 條對照

| # | 狀態 |
|---|---|
| 1 | 請求 3 次（第一節） |
| 2 | 第一節 |
| 3 | fixture 2 份（1-5）；沒有的種類已註明 |
| 4～12 | `test_fixture`、`test_fields`、`test_dedup`、`test_collect` |
| 13～19 | `test_plan`、`test_world`、`test_isolation`、`test_state`；18 由舊測試（`test_iter03`、`04`、`11`、`40`、`43`）不改且通過證明 |
| 20～23 | `test_line` |
| 24～27、29 | `test_export` |
| 28 | 需要真實資料匯出，交 PG（副本沒有 DB） |
| 30～34、36、37、39～41 | `test_card`、`test_board`、`test_words_node14`；舊鎖定由全部舊測試通過證明 |
| 35、38 | 預覽副本已看（第 3-6 節）；正式版交 QA |
| 42、43 | `test_version_and_docs` |
| 44 | 舊測試 0 行（diff 中 `tests/` 只有新檔與 2 個 fixture） |
| 45 | 改後 53 個測試全過 |
| 46～52 | 交 PG／QA（第七節）；46、48 依 D238 的第一次收集方式調整說法 |

---

## 六、和 PM 的差異（逐點理由）

| # | PM | 本設計 | 理由 |
|---|---|---|---|
| 1 | 卡片與今日卡、說明全文寫「官方只提供前一天的資料／公告」 | 「官方**每次只提供一天**的資料／公告」（D237） | 實測：上櫃在週六中午提供的是週四的發言，「前一天」不成立；新句對兩市場都正確 |
| 2 | `mn_export(news_rows, news[1], latest_date, closed, set(L.stocks))` 回傳 `(mn_stock, mn_latest)` | `mn_export(rows, mks, latest_date, closed)` 回傳 `(各市場 f/w/x, {代號: 列}, latest.mn)`，個股 JSON 那一行組 `{**base, "r": …}` | 「每檔都輸出、0 則也輸出」要知道該股市場，迴圈內已有 `mk_`；不需要代號集合（`latest.mn` 本來就照列不在 `stocks` 的代號） |
| 3 | `news_state` 每市場 3 項 | 4 項（多「全部筆數」，一個 `COUNT(*)` 併在原本的 MIN/MAX 查詢） | 📌 要寫「資料庫該市場全部列數」，原本的每日筆數只算近 45 天 |
| 4 | 📌 某市場沒有資料寫 `上櫃 尚無資料` | 第一段同 PM；「近 30 天漏收」那段該市場寫 `上櫃 --` | PM 沒寫漏收段的情況；`--` 和第 51、52 輪的 📌 一致 |
| 5 | 驗收 47「每市場列數 = 📰 筆數減略過數」 | 📰 的筆數本身就是寫入的筆數（去重、略過之後） | `n` 要和寫入的列一致，`check` 也顯示同一個數；列數 = 📰 筆數 |
| 6 | 反證「放在 `if not days` 之後」 | 不列 | 見第四節；位置照 PM 放在之前 |
| 7 | 第一次收集 `collect --catch-up` | 另提 D238，預設用專用指令只收重大訊息 | 週六的 catch-up 還會抓季報（4 個請求）與集保（1 個），見第七節 |

---

## 七、PG 上線步驟（寫 DB 的步驟要先取得使用者同意；使用者已同意備份、setup-db、開始收集）

| 步驟 | 指令 | 說明 |
|---|---|---|
| 0 | `pgrep -fl twstock` | 只能有 `serve`；避開 17:30、19:30、21:45、22:30 前後 20 分鐘 |
| 1 | `git apply docs/iterations/53/03-design.diff`，再跑 `for f in tests/test_iter*.py; do python3 -u $f >/dev/null 2>&1 \|\| echo FAIL $f; done` | 舊測試有任何失敗就停下回報 |
| 2 | `python3 -u -m twstock backup` | 記下檔名、大小、驗證結果 |
| 3 | `python3 -u -m twstock setup-db` | 「資料表已確認」一行有 `material_news（第 53 輪）` |
| 4 | 第一次收集（D238 = A，**只收重大訊息，2 個請求**）：`python3 -u -c "from twstock.config import tw_now; from twstock.collectors.news import collect_news; d = tw_now().date(); [collect_news(m, d) for m in ('TWSE', 'TPEx')]" 2>&1 \| tee logs/news_first_53.log` | 預期兩行 📰（週六：上市「出表 2026-11-28，發言日 2026-11-27」、上櫃「出表 2026-11-27，發言日 2026-11-26」或官方已更新的日子），請求恰好 2 個（各 1 個，`isolated`，失敗會丟例外並停止，不會重試）；不寫 `collect_runs` |
| 5 | `python3 -u -m twstock export` | 0 個外部請求；📌 `重大訊息：上市 2026-11-27 起 N 筆、上櫃 2026-11-26 起 N 筆；最新發言日 …；近 30 天漏收 上市 0 天、上櫃 0 天` |
| 6 | 唯讀 SELECT 核對：`SELECT market, COUNT(*), MIN(speak_date), MAX(speak_date), MIN(first_seen), MAX(out_date) FROM material_news GROUP BY market`；`python3 -u -m twstock check` | 列數 = 📰 筆數；`first_seen` 全部是當天；`check` 一行是「重大訊息最後成功：尚無執行紀錄」（步驟 4 不寫執行紀錄），結果仍「無異常」 |
| 7 | 全部測試再跑一次 | 驗收 45 |

- 之後第一次排程（週一 11/30 17:30）的 catch-up 會自動排重大訊息（沒有執行紀錄 → 兩市場都抓，+2 個請求；同一則 MERGE 不重複），`check` 從那次起顯示最後成功。週一那次也順帶回答 Q53-2。
- 若選 D238 = B（`python3 -u -m twstock collect --catch-up 2>&1 | tee logs/news_first_53.log`）：SA 以目前程式的純函式 `make_plan`（只 SELECT）在 11/28 14:10 預估，週六的 catch-up 會排：**季報 2026Q3**（`collect_financials`：損益表上市、上櫃＋資產負債表上市、上櫃，4 個請求）、**集保股權分散**（表中最新 11/20，1 個請求）、重大訊息 2 個，**共約 7 個請求**（休市表不到期、行情都已齊）；有新增 → 自動匯出。立刻再跑一次：上市出表已是今天 → 0 個；上櫃出表仍是 11/27 → 再 +1、新增 0。

---

## 八、需要使用者決定的事項（D237 起；目前最大 D236）

### D237 卡片與說明寫「前一天」還是其他說法

- 實測：週六中午上市提供週五的發言（前一天），上櫃仍提供週四的發言（前一個交易日的前一天）。PM 的文字是「官方只提供前一天的資料」（結果乙）或「前一個交易日」（結果甲），兩種都只對其中一個市場成立。
- **A**：改成「官方每次只提供一天的資料」（個股卡 A-5、今日卡 B-6），說明全文改成「官方每次只提供一天的公告」。
- **B**：維持 PM 的「前一天」。
- **C**：等週一晚上看過再定，本輪先用 B。
- **預設 A**：兩個市場都正確，也不依賴週一的觀察；字數相同、不增加程式。原型已用 A。

### D238 第一次收集用什麼方式

- **A**：專用一行指令只呼叫 `collect_news`（2 個請求，只寫 `material_news`），之後 `export`；執行紀錄要等下一次排程 catch-up 才有。
- **B**：`collect --catch-up`（約 7 個請求：另含季報 4、集保 1；寫執行紀錄、會自動匯出）。
- **預設 A**：指示是「只收重大訊息」；B 會在週六提前抓季報與集保（使用者原本排 11/29、11/30 後看這兩項），請求數也多。A 的代價是 `check` 在週一排程前顯示「尚無執行紀錄」，不影響收集與網站。

---

## 九、疑慮與備註

1. **上市週五的發言可能每週漏收**：週六上市資料集是週五的發言，排程週六幾乎不跑。週一晚上上市資料集是週日（多半 0 則或空陣列）還是週五，本次看不到。若週一是空陣列，程式不寫紀錄、每次執行都再抓（每晚 +1～2 個請求），且週五會出現在漏收；這屬於 D224 = A 已揭露的情況，下一輪提週末排程（F53-延伸e）。
2. **上櫃出表較晚**：週六中午仍是週五出表（週四的發言）；週末每次執行都會再抓上櫃（出表 < 今天），新增 0。一天最多約 10 個請求（同 PM 估計）。
3. **全部列都被略過時**：回應不是空陣列但每列都解析不到（例如時間格式全變），會印「官方目前沒有資料（0 筆）」而不是 ⚠️。實測沒有這種情況；若要區分需另加一個分支，本輪不做。
4. `if not days` 的位置：`due_days` 對 `n ≥ 1` 不會是空的，PM 擔心的「休市日排不到」本來就不會發生；照 PM 放在之前，行為相同。
5. 第 3 次實測的依日期查詢端點回「查無需求資料」，可能是參數不對而不是不提供；照規定不換參數、不重試，F53-延伸d 仍需另找來源。
6. fixture 的主旨含換行與官方原文，`test_iter53` 不掃 fixture（二之八 B）；本檔與程式自寫文字已對照禁用詞清單，0 命中（「借券賣出」除外）。
7. 預覽時今日卡的列取自實測原始回應，只在 scratchpad 的預覽副本，沒有進專案。

## 使用者決定（2026-11-28）

- 使用者 11/28 已指示「SA→PG→QA 一路做」、各角色 D 編號一律取預設。
- D237 = A：卡片與說明寫「官方每次只提供一天的資料／公告」。
- D238 = A：第一次收集用專用指令，只收重大訊息（2 個請求）。
- SA 與 PM 的差異（第六節）照 SA 接受。
