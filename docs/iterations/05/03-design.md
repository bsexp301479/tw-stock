# 第 05 輪｜System Analyst：設計文件

- 撰寫日期：2026-11-03（週二）深夜
- 輸入：`02-pm.md` 的本輪範圍，包括 E2-1、E2-4、A3＋A8，編號沿用 PM；另參考 `01-analyst.md` 與第 4 輪 `03-design.md`（格式比照）。使用者決定：D6 = 不做 00406A；「照建議，進 SA」= 採用 PM 暫定的 D7～D9；SA 初稿後使用者決定 **D10 = 照建議改說明文字**，並要求**一併修正首頁卡片排版**（F1）。
- 依據：
  - 閱讀了 `twstock/{__main__,fetch,db,health,export,tradingcal}.py`、`collectors/{catchup,history,daily}.py`、`site/{app.css,app.js,stock.js}`、`tests/test_iter01～04.py`、README。
  - 資料庫只做唯讀查詢，沒有執行 `setup-db`。
  - 外部請求都經過 `fetch.request(isolated=True)`，不重試：SA 階段共 7 次（附錄 A）；上市漲跌家數改用第 4 輪 PG 保存的 `logs/iter04_raw_MI_INDEX_20261103.json`，0 次。
- **所有設計都已在專案外、不含 `.env` 的暫存副本做成原型並實際跑過**：
  - 測試：`test_iter01`～`test_iter05` 全部通過。`test_iter05.py` 有 22 個測試，其中 `test_e2_real_file` 另外用完整的真實回應驗過（51 檔、94.43%）。
  - 原型與真實資料：用唯讀的正式資料庫執行原型的 `export_all`。三張新表還沒建立，這部分改由 SA 保存的 6 份真實 `GetPCF` 回應與 2 份官方家數回應提供。PM 的驗收數值全部重現（附錄 B）。
  - 隔離：同一份資料庫分別用「修改前程式」與「原型」各匯出一次。`stocks/*.json` 共 1,999 檔，除了新增的 `active` 以外差異 0 檔。`latest.json` 只多 `holdings`、`breadth` 兩個鍵，`status.datasets` 只多 6 個新資料集，增加 1.6 KB。
  - 前端：在 8001 埠用原型匯出的資料逐頁檢查，包括今日、ETF 列表、00981A／00403A／00411A／00988A 持股頁、未支援的 00982A、個股 1802／2330／1101。375px 寬度下 6 個頁面都沒有整頁水平捲動，console 沒有新的 error。檢查完已關閉 8001。
  - **專案程式、資料庫、排程都沒有修改。**
- 本文件只描述設計：
  - 附錄 C 是原型對現有程式的完整 diff，附錄 D 是完整的 `tests/test_iter05.py`，附錄 E 是 PG 用的 `logs/` 小工具，**都可以直接套用**。
  - 寫法可以改，但**函式名稱、資料表、判斷式、畫面文案、輸出訊息請照本文件**，`test_iter05.py` 與 QA 會照著驗。

> **影響設計的實測發現（PM 文件沒有預期到）**
> 1. **D9 的說明文字與資料不符，使用者已決定照建議修改（D10，第九節）。**
>    - 統一這 4 檔是現金申購買回，持股**不會**隨申購按比例增減。
>    - 例 1：00981A 10/30 → 11/02，受益權單位 +1.92%，50 檔裡有 41 檔張數完全不變。
>    - 例 2：11/02 → 11/03，單位 +0.54%，51 檔裡有 47 檔張數不變。
>    - 這些張數不變的股票，權重照樣在變，例如 3037 欣興 −0.29 百分點。權重變化反映的是股價漲跌。
>    - 所以實際情況和 D9 相反：**張數增減才是經理人的買賣**，權重變化含股價影響。
>    - 原型仍照 D9 同時顯示兩欄，只把說明文字改成符合資料的寫法（E2-4-4）。
> 2. **PM E2-1 #4「其他 48 檔股數不變」應為 47 檔**：51 − 新增 1（1802）− 變動 3（2330、3376、8210）= 47。逐檔比對見附錄 B-2。
> 3. **跨境 ETF 的持股日落後 1 個交易日**。在 11/03 晚上：
>    - 00981A、00403A 公布的是 11/03 的持股。
>    - 00411A、00988A 公布的是 **11/02** 的持股（`TranDate` 11/02、`PostDate` 11/04、`EditDate` 11/03 16:30～16:56）。
>    - 所以 `holdings.*` 需要 `delay` 屬性，`check` 與網站狀態才不會每天把跨境 ETF 的「今天」誤報為尚未公布（E2-1-3）。
> 4. **日期格式不固定**：00981A 當天的回應是 ISO 字串、歷史日期是 `/Date(毫秒)/`；00988A、00411A 連當天的回應都是 `/Date(毫秒)/`。兩種都要接受。未公布時回應 `asset: []`，`pcf` 每列的日期都是 `/Date(-62135596800000)/`（西元 1 年）、金額都是 0。
> 5. **`MI_INDEX?type=ALLBUT0999` 確實含「漲跌證券數合計」表**（PM 第四節列為未確認）。上市官方家數 0 請求，只要讓行情與家數共用同一個回應（A3-2）。
> 6. **「上市網站家數比官方多 3 家」拆解完成**。11/03 網站自算 61 漲／1,003 跌，官方股票欄 58／1,000：
>    - 4 檔 TDR（9103、9110 漲，9105、9136 跌）在網站算股票，官方股票欄不含。
>    - 2 檔「無比價」（6671 漲、6952 跌）網站依參考價算出漲跌，官方另列「無比價」。
>    - 合計 +3／+3。上櫃完全一致（59／782／32）。
> 7. **自算寬度和分析師試算不同**：上市站上 MA20 為 11.1%，分析師是 11.7%；20 日新低 691 檔，分析師是 582 檔。原因是分母不同：
>    - 分析師只取近 60 日沒有除權息的 865 檔、用原始收盤。
>    - 本設計依 PM 用還原收盤，取全部 1,083 檔。
>    - 計算邏輯已用 SQL 獨立核對：同一個「無事件」子集合，SQL 與原型函式的四個指標在兩天、兩市場都完全相同（附錄 B-4）。

---

## 〇、變更總覽

### 檔案 × 項目對照表

| 檔案 | E2-1 持股收集 | E2-4 持股匯出與畫面 | A3＋A8 寬度與量能 |
|---|---|---|---|
| `twstock/fetch.py` | `MIN_INTERVAL["www.ezmoney.com.tw"] = 3.0` | | |
| `twstock/db.py` | 新表 `etf_holdings`、`etf_holding_summary`、索引 `IX_etf_holdings_code` | | 新表 `market_breadth` |
| `twstock/health.py` | `HOLDINGS`、`Spec` 加 `since`、`delay`；`is_due`；`SPECS` 加 4 鍵；`load_snapshot`、`missing_keys(…, days)`、`evaluate`、`all_missing_days`、`dataset_status(…, closed)`、`build_status` | | `BREADTH_FROM`；`SPECS` 加 2 鍵；`load_snapshot` |
| `twstock/collectors/holdings.py`（新檔） | `ez_time`、`ez_date`、`post_date`、`parse_pcf`、`fetch_holdings`、`merge_holdings` | | |
| `twstock/collectors/daily.py` | `HOLDINGS_DS`、`HOLDINGS_KEYS`、`DATASET_KEYS`、`DAY_KEYS`、`_collect_key` 持股分支、`_save` 回傳值 | | `_mi_index`、`fetch_twse_daily(d, data=None)`、`parse_twse_breadth`、`parse_tpex_breadth`、`fetch_tpex_breadth`、`merge_breadth`、`_quotes` 快取原始回應、`collect_for_date` 的行情前置條件 |
| `twstock/collectors/history.py` | `SECONDS_PER_KEY` 加 4 鍵 | | |
| `twstock/collectors/catchup.py` | `missing_keys(…, days)`、`dataset_status(…, closed)` | | |
| `twstock/export.py` | | `HOLD_DAYS`、`_load_holdings`、`holding_table`、`holding_export`、`stock_active`；`etfs/{代號}.json`、個股 `active`、`latest.holdings` | `BREADTH_DAYS`、`breadth_calc`、`_load_breadth`；`latest.breadth` |
| `twstock/__main__.py` | `--only holdings`、docstring | | |
| `site/app.js` | | 路由 `etf/{代號}`、`holdTag`、`HOLD_SORT`、`renderHoldings`；ETF 列表標示與點擊 | 成交額卡改用官方家數、`breadthCard` |
| `site/stock.js` | | 「主動 ETF 持有」卡 | |
| `site/app.css` | | `.al-new`、`.pill.hold`、`.tbl .nm .pill` | |
| `site/app.js`、`site/app.css`（F1） | 首頁成交額＋三大法人卡改為固定 4 欄：`.g-mk`、`.g-mk .insti`；估算版三大法人卡加 `insti` class | | |
| `tests/test_iter05.py`（新檔） | 附錄 D | 同左 | 同左 |
| `tests/test_iter03.py` | `World` 加 `GetPCF` 端點、`json=` 參數、持股與家數的假資料表 | | `World` 的 `MI_INDEX` 加家數表、加 `highlight` |
| `tests/test_iter04.py` | `test_t26` 的位置斷言（`SPECS` 後面多了新鍵） | | |
| `README.md`、`__main__.py` docstring | 第七節清單 | 同左 | 同左 |

**工作量**：

| 項目 | 程式 | 測試 |
|---|---|---|
| 新增（附錄 C） | 567 行（含新檔 `holdings.py` 102 行） | `test_iter05.py` 430 行、`test_iter03.py` +37 行 |
| 刪改 | 48 行 | `test_iter03.py` 5 行、`test_iter04.py` 1 行 |
| README（PG 依第七節） | 約 25 行 | — |

合計約 1,060 行，低於 PM 上限（程式 800＋測試 550），**不需要依 PM 第五節第 9 點延後任何項目**。

### 建議實作順序

| 步驟 | 內容 | 驗證 |
|---|---|---|
| 0 | **PG 手動備份**（PM 範圍內作業）：`BACKUP DATABASE … WITH COPY_ONLY` → `_backups/TwStock_before_round5.bak` | 新檔 > 55 MB；round3、round4 兩個備份的大小與時間不變 |
| 1 | **隔離基線（舊程式，改任何程式之前）**：`python3 -m twstock export`，然後 `mkdir -p logs/iter05_before && cp site/data/latest.json logs/iter05_before/ && cp -R site/data/stocks logs/iter05_before/`；SQL 記錄既有表筆數 | 檔案存在 |
| 2 | 套用附錄 C 的 `fetch.py`、`db.py` → `python3 -m twstock setup-db` 執行兩次 | 兩次都不報錯；既有表筆數不變；3 張新表存在且是空的（E2-1 #1） |
| 3 | 套用其餘 Python 與測試（附錄 C、D），以及附錄 E 的兩個 `logs/` 小工具 | `test_iter01`～`05` 全過（`test_e2_real_file` 先略過） |
| 4 | **check 基線**：`python3 -m twstock check 2>&1 \| tee logs/iter05_check_before.log; echo rc=$?` | rc=1；4 個 `00xxxA持股` 缺 20 天；2 個漲跌家數只缺 11/03（`BREADTH_FROM`） |
| 5 | **隔離比對 1**（新程式、新表為空）：`python3 -m twstock export` → `python3 logs/iter05_compare.py logs/iter05_before site/data` | 「除新增鍵外相同」。此時 `holdings` 是 `{}`，`breadth.*.o` 是 null |
| 6 | **補抓持股**：`python3 logs/iter05_history.py 2>&1 \| tee -a logs/iter05_history.log`（約 648 次、35 分鐘）。中斷或被限流時，等 30 分鐘以上再用同一指令重跑。**期間不要執行 `collect` 或其他 `history`** | 「待抓 0 天」；`logs/iter05_raw_GetPCF_00981A_{20251030,20261102,20261103}.json` |
| 7 | **補官方家數 11/03**：`python3 -m twstock collect --catch-up`（上市 1 次 `MI_INDEX`、上櫃 1 次 `highlight`；其他資料集已齊，不發請求） | `market_breadth` 2 列（A3 #1） |
| 8 | `python3 -m twstock check 2>&1 \| tee logs/iter05_check_after.log; echo rc=$?`；附錄 B 的 SQL；`python3 tests/test_iter05.py`（這時會讀到原始回應） | rc=0（E2-1 #8，例外見 E2-1-7）；E2-1 #2～#5 |
| 9 | **隔離比對 2**：`python3 -m twstock export` → `python3 logs/iter05_compare.py logs/iter05_before site/data` | E2-4 #5、#6 |
| 10 | 前端（`app.js`、`stock.js`、`app.css`，含 F1）→ `serve --port 8001 --no-browser`，桌機與 375px | E2-4 #1～#4、A3 #3～#4；**完成後關閉伺服器** |
| 11 | README、`__main__.py` docstring（第七節） | 第七節清單 |

> 步驟 1 到步驟 9 之間只執行步驟 7 的那一次 `collect --catch-up`。它只寫 `market_breadth`，不影響既有鍵；E2-4 #5 的比對照樣成立，因為 `logs/iter05_compare.py` 只排除新增鍵與 `status`。

### 共通約定（本輪新增）

- **持股日 T、生效日 P**：
  - 投信在交易日 T 傍晚公布「生效日 P」的申購買回清單。P = T 之後的下一個交易日。
  - 清單裡的持股：國內 ETF（00981A、00403A）是 T 當天收盤後的持股；跨境 ETF（00411A、00988A）是 T 的前一個交易日。
  - 本設計**以持股日為準**。持股日 d 的請求參數是 `post_date(d, delay)` = d 之後第 `delay + 1` 個交易日，例如週五 → 週一、連假跳過。
  - 回應的 `TranDate` 不等於 d 時一律不寫入，包括尚未公布、遇到連假、回應前一持股日等情況。
- **單位**：
  - 股數存原值（股；期貨為口）。台股匯出時轉成**張**（股 ÷ 1,000，四捨五入），海外股票維持**股**。
  - 金額存原幣（`currency`）。淨資產與期貨名目本金匯出為**億元**。
  - 權重是占淨資產的 %，權重變化以**百分點**表示。
- **台股的判斷**：持股代號存在於 `stocks` 表 = 台股，可以點進個股頁，也會出現在個股的「主動 ETF 持有」卡。其他代號（海外股票如 `BE US`、期貨 `TX`）只在 ETF 持股頁顯示原文。
- **增減的基準**：1 日 = 前一個有資料的持股日；5 日 = 往前第 5 個有資料的持股日（不足時為 null）。「新」= 前一持股日沒有、今天有。「出清」= 前一持股日有、今天沒有。期貨不列入持股表，只出現在摘要。
- **一天內的收集順序**（`DAY_KEYS`）：
  - 既有 12 鍵 → `breadth.TWSE` → `breadth.TPEx` → `holdings.00981A`、`00403A`、`00411A`、`00988A`。
  - 持股要寫進 `etfs` 已有的 ETF，所以排在 `etf.*` 之後。
  - 上市家數與上市行情共用同一個 `MI_INDEX` 回應。

### 資料集模型（`health.SPECS` 新增 6 鍵；`Spec` 新增 `since`、`delay`，預設 None、0）

| 鍵 | 名稱 | 資料表 | 端點 | 筆數 | 下限 | since | delay | 回補 |
|---|---|---|---|---|---|---|---|---|
| `breadth.TWSE` | 上市漲跌家數 | `market_breadth` | 與上市行情同一個 `MI_INDEX` | 1 列 | 1 | 2026-11-03 | 0 | 不補 |
| `breadth.TPEx` | 上櫃漲跌家數 | 同上 | 櫃買 `afterTrading/highlight`（POST） | 1 列 | 1 | 2026-11-03 | 0 | 不補 |
| `holdings.00981A` | 00981A持股 | `etf_holdings`（只算 `asset_type='ST'`） | 統一 `GetPCF`（POST JSON） | 股票檔數 | 1 | None | 0 | `history --only holdings` |
| `holdings.00403A` | 00403A持股 | 同上 | 同上 | 同上 | 1 | 2026-05-12 | 0 | 同上 |
| `holdings.00411A` | 00411A持股 | 同上 | 同上 | 同上 | 1 | 2026-08-26 | **1** | 同上 |
| `holdings.00988A` | 00988A持股 | 同上 | 同上 | 同上 | 1 | 2025-11-05 | **1** | 同上 |

- **since = 上市日**，取自 `etf_daily` 每檔最早一筆（唯讀 SQL，附錄 B-1）。00981A 在 2025-05-15 上市，早於資料起點，所以是 None。
- **筆數門檻**：下限 1，另外沿用「近 20 日中位數 × 80%」。11/03 的實際檔數是 00981A 51、00403A 50、00411A 30、00988A 34。主動 ETF 一天少掉 20% 以上的持股很少見；真的發生時，「筆數偏低」是值得注意的訊號。新上市 ETF 建倉期的檔數是遞增的，不會誤報。
- **delay 的判斷**（`health.is_due`）：days 是交易日清單（舊到新）。
  - 日期 d 要在 d 之後再過 `delay` 個交易日、且那一天也在 days 裡，才算「該有」。
  - 公布日 = `days[i + delay]`。公布日當天 22:00 前算「尚未公布」，之後算「異常」，與既有規則相同。
  - 所以 11/04 18:00 的 `check`：00411A 的 11/04 不列出（11/05 才公布）；11/03 若還沒有，算「尚未公布」。
- **哪裡用到 delay**：
  - `evaluate`：`check`、`--catch-up` 結束後的狀態。
  - `missing_keys(…, days)`：`--catch-up` 規劃時不請求還不該有的日期。`history` 不傳 days，只看 since，最後一天若還沒公布就記「無資料」。
  - `dataset_status(…, closed)`：網站 status 改看資料日往前 delay 個交易日。
  - `all_missing_days`：判斷「整天沒收集」時不看 delay 資料集，因為它們隔天才收。

### 口徑表（PM 第五節第 1 點：每個畫面數字）

| 位置 | 數字 | 口徑 | 單位 | 計算式 | 資料日 |
|---|---|---|---|---|---|
| ETF 持股頁・摘要 | 淨資產 | 投信官方 | 億（1 位） | `pcf` 的 `NAV` ÷ 10⁸ | 持股日 |
| 同上 | 每單位淨值 | 投信官方 | 元（2 位） | `P_UNIT` | 同上 |
| 同上 | 股票權重合計 | 投信官方 | %（2 位） | Σ股票明細 `NavRate`（11/03 = 94.43） | 同上 |
| 同上 | 持股檔數 | 投信官方 | 檔 | 股票明細列數（含海外） | 同上 |
| 同上 | 期貨 | 投信官方 | 口、億 | Σ期貨 `Share`；Σ`Amount` ÷ 10⁸ | 同上 |
| ETF 持股頁・持股表 | 持有 | 投信官方 | 台股張、海外股 | `Share` ÷ 1,000（四捨五入）；海外不換算 | 最新持股日 |
| 同上 | 權重 | 投信官方 | %（2 位） | `NavRate` | 同上 |
| 同上 | 1 日增減 | 自算 | 張（海外股） | 今 − 前一持股日（前一日沒有 = 0） | 前一持股日 → 最新 |
| 同上 | 1 日權重變化 | 自算 | 百分點（2 位） | 今權重 − 前一日權重（沒有 = 0） | 同上 |
| 同上 | 5 日增減 | 自算 | 張 | 今 − 往前第 5 個持股日（沒有 = 0；不足 6 個持股日為 `--`） | — |
| 同上 | 新 | 自算 | — | 前一持股日沒有持有 | — |
| 同上・出清 | 前一日持有、權重 | 投信官方 | 張、% | 前一持股日的值 | 前一持股日 |
| 個股頁・主動 ETF 持有 | 張數、權重、1 日、5 日、持股日 | 同持股表 | 張、%、張 | 同上；只列持有該股的已支援 ETF | 各 ETF 最新持股日 |
| 今日・成交額卡 | 漲（漲停）、跌（跌停）、平、未成交 | **官方，股票** | 家 | 上市「漲跌證券數合計」股票欄；上櫃 `highlight`。沒有官方家數時退回網站自算並註明 | 資料日 |
| 同上 | 成交額 | 網站自算（不變） | 億 | Σ股票成交金額 | 資料日 |
| 今日・市場寬度卡 | 站上 MA20、MA60 | 自算，股票 | %（1 位） | 還原收盤 > 含當天的 20（60）日均價的檔數 ÷ 分母；分母 = 當天有收盤、且含當天至少有 20（60）個收盤 | 資料日 |
| 同上 | 前日 MA20 | 自算 | % | 走勢的倒數第 2 天 | 前一交易日 |
| 同上 | 20 日新高、新低 | 自算 | 家 | 還原收盤高於（低於）前 20 個收盤的最高（最低）；當天之前至少要有 20 個收盤 | 資料日 |
| 同上 | 量能 | 自算 | 倍（2 位） | 當天股票成交額 ÷ 前 20 個交易日平均；前 20 日有任一天缺就是 `--` | 資料日 |
| 同上 | 60 日走勢 | 自算 | % | 上市站上 MA20 比例，近 60 個交易日 | — |

---

## E2-1. 統一投信主動型 ETF 每日持股（優先 1）

### E2-1-1 對應驗收條件（SA 修訂處標 ★）

| PM # | 驗收 | 設計對應 | 測試／QA |
|---|---|---|---|
| 1 | `setup-db` 建立新表，可重複執行 | `db.DDL` 3 張表（`IF OBJECT_ID … IS NULL`）＋1 個索引 | 步驟 2；`test_e2_specs` |
| 2 | 補抓完整，重跑 0 請求 | `history --only holdings`；since；`missing_keys` | 附錄 B-1；`test_e2_m6_before_listing`（重跑待抓 0 天） |
| 2★ | 「到 2026-11-03」 | **跨境 2 檔要 11/04 傍晚之後才有 11/03 的持股**。PG 若在 11/04 16:30 前補抓，00411A、00988A 只會到 11/02，11/03 記「無資料」；之後 `collect --catch-up` 會自動補上。QA 依補抓時間判斷 | 附錄 B-1 |
| 3 | 11/03 00981A：51 檔、2330 14,464,000 股 33,194,880,000 元 13.05%、TX 679 口、NAV 254,413,288,263、94.43% | `parse_pcf` | 附錄 B-2；`test_e2_parse_real`、`test_e2_real_file` |
| 4★ | 11/02 → 11/03 異動 | 新增 1802 8,479 張；出清 0；2330 +736、3376 −300、8210 −100；**其他 47 檔不變**（PM 寫 48） | 附錄 B-2 |
| 5 | 2025-10-30 股票 50 檔，逐列比對原始回應 | 同上 | 附錄 B-2；`test_e2_real_file` |
| 6 | `TranDate` 與要求的持股日不同 → 不寫入 | `parse_pcf` 回傳 None → 0 筆 → 22:00 前「尚未公布」，之後「異常」 | `test_e2_parse_not_published_and_schema`、`test_e2_m2_m3_not_published` |
| 7 | mock #1～#8 | 見 E2-1-6 | `test_iter05.py` |
| 8 | `check` 補抓前 rc=1、補抓後 rc=0 | 4＋2 個新資料集列在既有之後 | 步驟 4、8 |
| 9 | README、`__main__.py` | 第七節 | QA 逐條 |

### E2-1-2 資料來源（2026-11-03 實測，附錄 A）

- `POST https://www.ezmoney.com.tw/ETF/Transaction/GetPCF`，JSON 本文 `{"fundCode": "49YTW", "date": "115/11/04", "specificDate": true}`。
  - `date` 是民國年的生效日。
  - 只用 `fetch` 既有的 Session 標頭，**不送偽造的來源標頭**。
  - `MIN_INTERVAL` 設 3 秒。
- **基金代碼：寫死在 `health.HOLDINGS`**。不從 `DataFundList` 取得，因為那要每天多發請求，而統一的主動 ETF 一年只新增幾檔。
  - 新上市的統一主動 ETF 要加入時，在 `HOLDINGS` 加一列：代號 → (基金代碼, delay, 上市日)。
  - 基金代碼可以在統一 ETF 網站的 PCF 頁原始碼裡找到；上市日以 `etf_daily` 最早一筆為準。
  - 加入後執行 `history --start 上市日 --only holdings`。
- 回應結構：

| 欄位 | 內容 | 用法 |
|---|---|---|
| `pcf[]` | `PCFCode`／`TranDate`／`PostDate`／`Amount`。`NAV` 淨資產、`OUT_UNIT` 已發行單位、`P_UNIT` 每單位淨值，另有 `DIFF_UNIT` 等 | `NAV` 必要，持股日、生效日都取自這一列；其他可缺 |
| `asset[]` | `AssetCode`：`ST` 股票、`GD` 期貨（11/03 只看到這兩類） | 其他類別也會存進明細，但不列入檔數與持股表 |
| `asset[].Details[]` | `DetailCode`、`DetailName`、`Share`、`Amount`、`NavRate`、`MoneyType`、`MTH`（期貨契約年月）、`TranDate`、`EditTime` | 明細；`Details` 可能是 null（沒有期貨時） |

- **已公布的判斷**：`asset` 非空，而且 `pcf` 的 `NAV.TranDate` == 要求的持股日。
- **欄位不符**（`SchemaError`）：
  - 回應不是物件，或缺 `pcf`、`asset`。
  - `pcf` 沒有 `NAV`。
  - 明細的持股日與 `NAV` 不同。
- 明細缺 `DetailCode` 等欄位會是 `KeyError`，同樣在 `PARSE_ERRORS` 裡，只影響該檔。
- **公布時間**：
  - 11/03：00981A 16:56、00403A 16:17、00411A 16:55、00988A 16:30。
  - 11/02：00981A 16:30。
  - 17:30 的排程大致趕得上；趕不上時 19:30、21:45 會再試，22:30 仍沒有就算異常。

### E2-1-3 資料庫（`db.py` 的 `DDL`，接在 `margin_market` 之後、索引之前；完整 DDL 見附錄 C）

| 表 | 欄位 | 唯一鍵 | 寫入 |
|---|---|---|---|
| `etf_holdings` | `etf_id`（FK `etfs`）、`hold_date`、`asset_type`、`code`（原文，`NVARCHAR(20)`）、`month`（期貨契約年月，其他為 `''`）、`name`、`shares`（BIGINT）、`amount`（原幣）、`weight`、`currency` | (`etf_id`, `hold_date`, `asset_type`, `code`, `month`) | 同一檔、同一持股日**先刪後插**，與彙總在同一個交易裡（持股會出清，不能只 MERGE） |
| `etf_holding_summary` | `etf_id`、`hold_date`、`post_date`、`nav`、`units`、`nav_unit`、`n_stocks`、`stock_weight`、`futures_lots`、`futures_amount`、`edited_at` | (`etf_id`, `hold_date`) | MERGE |
| 索引 `IX_etf_holdings_code` | (`code`, `hold_date`) | — | 給 QA 依股票查詢 |

`etfs` 沒有這檔 ETF 時，`merge_holdings` 回傳 False，什麼都不寫，並印「⚠️ etfs 沒有 00981A，持股未寫入」，以 0 筆計。這種情況只會發生在 `etf.*` 從沒收過的資料庫。

### E2-1-4 解析與收集（`collectors/holdings.py`、`daily.py`）

```text
_collect_key("holdings.00981A", d, cache)
  cache["closed"] ← tradingcal.load_closed（一次執行只查一次資料庫）
  fetch_holdings(code, d, closed)
    post = post_date(d, delay, closed)               # d 之後第 delay+1 個交易日
    data = request("POST", URL, json={fundCode, date: 民國 post, specificDate: True})
    parse_pcf(data, d) → None（尚未公布／持股日不符）或 (彙總, 明細)
  None → 回傳 0 筆
  _save(merge_holdings, code, 彙總, 明細) → False（etfs 沒有）→ 0 筆
  回傳 彙總["n_stocks"]
```

- 持股和行情無關，不受 `collect_for_date` 的「同市場行情還沒有就不請求」限制。
- 休市日本來就不在 `due_days`、`trading_days` 裡，所以不發請求（mock #7）。
- `_save` 改為回傳寫入函式的結果，原本的呼叫端都沒有使用回傳值，不受影響。

### E2-1-5 history 與 catch-up

- `history --only holdings`：`DATASET_KEYS["holdings"]` = 4 鍵。**不加入預設的 `ALL_DATASETS`**，所以不帶 `--only` 的 `history` 行為不變（`test_t26` 仍驗證預設 5 項）。
  - 每鍵估 3.2 秒，648 次約 35 分鐘。
  - 欄位不符時沿用既有流程：印「❌ 在 … 停止：官方欄位不符（…）」，rc=1，第一天就停（mock #8）。
- `--catch-up`：`make_plan` 呼叫 `missing_keys(d, DAY_KEYS, snap, med, days)`，跨境 ETF 最後一個交易日的持股不請求。
  - 因此 17:30 的請求數是 4 次：國內 2 檔的今天，加上跨境 2 檔的前一交易日。
  - 結束後判斷「網站 status 是否改變」時，`dataset_status` 也傳入 `closed`，與匯出時一致。否則每次執行都會因為跨境 ETF 被判為「有變動」而重新匯出。這個問題是原型實測時發現的，`test_qa08` 能抓到。

### E2-1-6 邊界情況與 mock（PM #7）

| # | 情境 | 預期 | 測試 |
|---|---|---|---|
| 1 | 11/04 17:30 已公布 | 4 檔寫入、`GetPCF` 4 次（參數都是 `115/11/05`）；19:30 重跑 0 次 | `test_e2_m1_published` |
| 2 | 11/04 17:30 未公布（回應前一持股日的清單） | `⏳ 00981A持股：2026-11-04 尚未公布`，rc=0，不寫入、不通知 | `test_e2_m2_m3_not_published` |
| 3 | 11/04 22:30 仍未公布 | `❌ 00981A持股：缺 2026-11-04`，rc=1，`--notify` 一次（鍵 `holdings.00981A:2026-11-04`） | 同上 |
| 4 | 某檔回應缺 `asset` 或明細缺 `DetailCode` | `⚠️ holdings.00403A 失敗：GetPCF 回應缺少 pcf 或 asset`，只有該檔異常；行情、家數、其他 3 檔照常；無 Traceback | `test_e2_m4_schema_only_that_etf` |
| 5 | 歷史日期 `/Date(毫秒)/` | 2025-10-30（UTC 10/29 16:00 換成台灣時間） | `test_e2_dates`、`test_e2_parse_real` |
| 6 | 00411A 上市日之前 | `history --start 8/24` 不請求 8/24、8/25 | `test_e2_m6_before_listing` |
| 7 | 休市日 | 12/25 執行 `--catch-up`：`GetPCF` 0 次、`highlight` 0 次 | `test_e2_m7_holiday` |
| 8 | `history --only holdings` 欄位不符 | 印「官方欄位不符」、rc=1、無 Traceback、只請求第一天 4 次 | `test_e2_m8_history_schema` |
| — | 週五持股、連假 | 生效日跳到下一個交易日（10/30 → 11/02；12/24 → 12/28） | `test_e2_dates` |
| — | 整天沒收集 | 「❌ 11/02 全部資料集都沒有」，不受跨境持股影響 | `test_e2_all_missing_day` |
| — | 跨境 ETF 遇到台灣休市、海外有交易 | 回應的持股日不是要求的那天 → 不寫入；過 22:00 算異常。**本輪無實例可驗**，QA 檢查補抓 log 的「無資料」清單，若出現台灣交易日就回報 | QA |

### E2-1-7 `check` 整合

- 新資料集列在既有 15 列之後。補抓前：4 檔持股缺 20 天（00411A 上市未滿 20 個交易日時，缺的天數 = 上市以來的交易日數）。補抓後應該是 rc=0。
- 例外：步驟 8 若在 11/04 16:30 之前執行，跨境 2 檔的 11/03 不會出現在 `check` 裡（那時還不該有），rc 不受影響。

---

## E2-4. ETF 持股頁與個股「主動 ETF 持有」卡（優先 1）

### E2-4-1 對應驗收條件

| PM # | 驗收 | 設計對應 |
|---|---|---|
| 1 | 00981A 頁：摘要與 SQL 一致；51 列；1802「新」+8,479；2330 +736；依權重第一列 2330 13.05% | `holding_export`、`renderHoldings`；原型實測一致（附錄 B-3） |
| 2 | 00988A 海外持股、代號不可點；00403A、00411A 可開啟 | `tw` 旗標：`stocks` 表沒有的代號不加 `data-code`，名稱後標「（海外）」，單位「股」 |
| 3 | ETF 列表：4 檔可點；00982A、00406A「持股尚未支援」 | `holdTag`：`latest.holdings` 有 → 「持股」連結，整列可點；代號 `A` 結尾其他 → 「持股尚未支援」 |
| 4 | 個股 1802、2330 卡片；未被持有的股票不顯示卡片 | `stock_active`；**SA 指定 1101 台泥**（4 檔最新持股日都沒有持有）。2330 被 3 檔持有：00403A 7,800 張、00981A 14,464 張、00988A 320 張 |
| 5 | 隔離 | `logs/iter05_compare.py`（附錄 E） |
| 6 | `latest.json` +≤ 20 KB；每檔 ETF JSON ≤ 300 KB；375px；console | 原型 +1.6 KB；60 個持股日估 00981A 約 40 KB |

### E2-4-2 匯出（`export.py`）

- `site/data/etfs/{代號}.json`（只產生 `HOLDINGS` 裡、有持股資料的 ETF）：

```text
{code, n（名稱）, m（市場）, fund（基金代碼）, delay, dates: [近 HOLD_DAYS=60 個持股日],
 sum: {d, nav（億）, nu（元）, n（檔）, sw（%）, fl（口）, fa（億）},
 rows: [{c, n, tw（1=台股）, s: [各持股日數量，未持有 null], w: [各持股日權重], l, pw, d1, w1, d5, new?}]（依最新權重排序）,
 out: [{c, n, tw, l, pw}]（出清，前一持股日的值）}
```

- `stocks/{代號}.json` 新增 `active`：`[{e（ETF）, d（持股日）, l（張）, w（%）, d1, d5, new?}]`，依 ETF 代號排序。**沒有任何已支援 ETF 持有時不加這個鍵**，所以 1,929 檔個股檔案完全不變。
- `latest.json` 新增：
  - `holdings: {代號: {d: 最新持股日, n: 名稱}}`：支援清單，前端靠它決定可不可以點。
  - `breadth`：見 A3-3。
- 純函式 `holding_table`、`holding_export`、`stock_active` 不連資料庫，`test_iter05` 直接測。

### E2-4-3 畫面

- **路由**：`#/etf` = 列表（不變）；`#/etf/{代號}` = 持股頁。不在 `latest.holdings` 裡的代號**不發請求**，直接顯示「{代號} 的持股資料尚未支援（目前只有統一投信 4 檔主動 ETF）」，避免 404 出現在 console。
- **持股頁**：
  - 標題列：名稱、代號、市場、「持股日 11/03」。跨境 ETF 加「（跨境，晚一個交易日公布）」。右側有「← ETF 列表」。
  - 摘要 5 張卡：淨資產、每單位淨值、股票權重合計、持股檔數、期貨（沒有期貨顯示「無」）。
  - 持股表欄位：股票、持有、權重、1 日增減、1 日權重變化、5 日增減。可依權重、張數增減、權重變化排序（`localStorage` 的 `tw.holdSort`），預設權重。
  - 標「新」的是藍色小標。台股整列可點進個股頁。
  - 出清區只在有出清時出現。
  - 說明文字見 E2-4-4。
- **ETF 列表**：名稱下的代號後面加標示。已支援 → 藍框「持股」連結，整列可點；其他 `A` 結尾 → 灰框「持股尚未支援」。其他 ETF 不變。
- **個股頁**：在指標卡之後、K 線之前加「主動 ETF 持有」卡。
  - 欄位：ETF（連到持股頁）、張數、權重、1 日、5 日、持股日。
  - 副標「目前只含統一投信 4 檔主動 ETF」。
  - 沒有 `active` 時整張卡不出現。

### E2-4-4 說明文字（D9 → D10，使用者已確認採用右欄）

| 位置 | PM／D9 原意 | 原型採用（符合資料） |
|---|---|---|
| 持股頁底部 | 「張數增減含申購買回造成的被動變動，權重變化才代表經理人主動調整」 | 「本基金為現金申購買回，持股不會隨申購按比例增減：**張數增減就是經理人的買賣**；權重變化另含股價漲跌的影響（張數不變、權重也會變）。」 |
| 個股卡底部 | （同上） | 「張數增減為經理人買賣（現金申購買回，不會按比例被動增減）；權重為占該 ETF 淨資產 %，含股價漲跌影響。」 |

**欄位不變**：張數增減與權重變化兩欄都保留，D9「同時顯示」的決定不受影響。PG 照右欄文字實作（附錄 C 已是這版），QA 逐字核對。

---

## A3＋A8. 市場寬度與量能（優先 2）

### A3-1 對應驗收條件

| PM # | 驗收 | 設計對應 |
|---|---|---|
| 1 | 11/03 官方家數 上市 58(2)／1,000(33)／22／6；上櫃 59(11)／782(41)／32／24 | `parse_twse_breadth`、`parse_tpex_breadth`；`test_a3_parse` 用實際回應片段 |
| 2 | 自算寬度與量能，提供 11/03、11/02 預期值與 SQL | 附錄 B-4 |
| 3 | 上櫃未公布或異常 → 只有該資料集異常，卡片不影響其他卡 | `test_a3_flow`。★ 成交額卡**退回網站自算家數**並註明「官方家數尚未取得，顯示自算」，不顯示「--」（PM 寫「--」）。這樣頭條不會整個空掉 |
| 4 | 375px、console | 原型實測 |
| 5 | README（口徑、官方與自算的差別） | 第七節 |

### A3-2 資料來源與收集（`daily.py`）

- **上市**：`MI_INDEX?type=ALLBUT0999`，也就是行情本來就抓的回應，裡面的 `title == "漲跌證券數合計"` 表。
  - 取「股票」欄。上漲、下跌的格式是 `"1,000(33)"`，括號內是漲停、跌停；持平、未成交沒有括號；「無比價」不存。
  - 實作上 `_quotes` 把原始回應存在 `cache["MI_INDEX"]`，`fetch_twse_daily(d, data)` 和 `parse_twse_breadth` 共用它，**0 個額外請求**。
  - `fetch_twse_daily` 的回傳型別不變，第 4 輪的測試照常通過。
  - 有行情（`stat == "OK"`）卻找不到這張表或欄位 → `SchemaError`，只影響 `breadth.TWSE`。
- **上櫃**：`POST afterTrading/highlight`，表單 `date=2026/11/03`，取「上櫃股票當日彙總資訊」的 6 個家數欄。沒有資料表 → None（尚未公布）。
- **行情前置條件**：同市場行情 0 筆時不發請求，`collect_for_date` 的條件加上 `"breadth"`。
- **不補歷史**：`since = BREADTH_FROM = 2026-11-03`，不在 `DATASET_KEYS`，所以 `history` 不會抓。上櫃每天 +1 個請求。

### A3-3 匯出（`export.py`）

- 個股迴圈裡順便累積近 `BREADTH_DAYS + 60 = 120` 個交易日的**還原收盤**（`c × af`，與 52 週高低相同）與成交額。迴圈結束後用 `breadth_calc` 計算。
- `latest.breadth = {TWSE|TPEx: {o: 官方 {up, ul, dn, dl, fl, nt} 或 null, d, ma20, ma60, n20, n60, hi, lo, vr, s20: [60 天], from}}`。
- 既有 `latest.market` **不變**（隔離），前端自己決定頭條要用官方還是自算。

### A3-4 畫面（`app.js`）

- **成交額卡**：
  - 有 `breadth[市場].o` 時，顯示「漲 58（停 2）　跌 1,000（停 33）　平 22　未成交 6」，副標「家數為官方（股票）；成交額為網站自算，不含 ETF」。
  - 沒有時沿用原本的自算家數，副標加「官方家數尚未取得，顯示自算」。
- **市場寬度卡**（信用交易卡之後，佔滿一列）：
  - 上市、上櫃各一行：「站上 MA20 11.1%（前日 20.5%）　MA60 19.9%　20 日新高 11、新低 691　量能 0.97 倍」。
  - 下方是上市 MA20 比例的 60 日迷你線，重用 `spark`。
  - 最後一行寫明分母與定義。
- 官方家數與自算家數的差異（實測發現 6）寫進 README，畫面不另外說明。

---

## F1. 首頁卡片排版修正（使用者追加）

### F1-1 問題與原因

- 現象（使用者截圖，第 4 輪現行網站）：今日頁「上市成交額／上櫃成交額／三大法人」只佔版面左半，右邊整片留空；三大法人卡被擠成窄長條，同列的兩張成交額卡被拉得一樣高，下半部全是空白。
- 原因：這一區沿用 `.g-stats`（`repeat(auto-fit, minmax(150px, 1fr))`）。內容寬 1,088px 時會切出 6 欄，但這列只有 3 張卡（信用交易卡、市場寬度卡各自佔滿一列），所以剩 3 欄空著；三大法人卡內容最多，只分到 1 欄 175px。指數卡那一列只有 2 張，`auto-fit` 會收掉空欄，所以沒事。

### F1-2 設計

| 寬度 | 欄數 | 上市成交額 | 上櫃成交額 | 三大法人 | 信用交易、市場寬度 |
|---|---|---|---|---|---|
| > 720px | 4 | 1 欄 | 1 欄 | **2 欄** | 整列（不變） |
| ≤ 720px | 2 | 1 欄 | 1 欄 | 整列 | 整列（不變） |

- 第二個 `<section>` 加 class `g-mk`；`.g-mk{grid-template-columns:repeat(4,minmax(0,1fr))}`、`.g-mk .insti{grid-column:span 2}`、720px 以下改 2 欄且 `.insti` 佔整列。
- 尚無官方三大法人時的估算版卡片也加 `insti` class，寬度一致。
- 只改這一區；指數卡、其他頁面不動。

### F1-3 驗收（原型 8001 實測）

| 視窗寬 | 成交額卡 | 三大法人卡 | 整頁水平捲動 |
|---|---|---|---|
| 1280px | 265 × 222 各 1 張 | 539 × 222（三張同高、填滿整列） | 無 |
| 800px | 185 × 240 | 379 × 240 | 無 |
| 600px | 279 × 156 | 568（整列） | 無 |
| 375px | 167 × 192 | 343（整列） | 無 |

QA：桌機寬度下這一列沒有空欄、三張卡底部對齊且卡內不出現大片空白；720px、375px 各看一次。

---

## 七、README 與 `__main__.py` 修改清單

### README（PG 依清單修改，QA 逐條核對）

1. 專案結構表：`collectors/` 加「`holdings` 主動型 ETF 持股（統一投信）」；`daily` 加「官方漲跌家數」。`site/` 加「ETF 持股頁」與「市場寬度」。
2. 安裝：新增資料表清單加「第 5 輪的 `etf_holdings`、`etf_holding_summary`、`market_breadth`」。
3. 日常使用：加一行 `python -m twstock history --start 2025-10-30 --only holdings   # 只補主動型 ETF 持股（統一投信 4 檔；上市日之前自動略過；一年約 650 個請求、35 分鐘）`。
4. 注意事項新增「主動型 ETF 持股」一條：
   - 資料來源是統一投信每日申購買回清單（`GetPCF`）。支援 00981A、00403A、00411A、00988A。
   - **00406A（中信）與其他投信尚未支援**，網站標「持股尚未支援」。
   - 日期語意：以持股日為準，國內 ETF 當天傍晚公布、跨境 ETF 晚一個交易日。
   - 單位：台股張、海外股。
   - 張數增減就是經理人的買賣（現金申購買回，不會按比例被動增減）；權重變化另含股價漲跌的影響（D10）。
   - 新增 ETF 的方式：`health.HOLDINGS` 加一列，再執行 `history --only holdings`。
5. 注意事項新增「市場寬度」一條：
   - 官方家數來源：上市與行情同一個回應、上櫃 `highlight` +1 請求，歷史不補。
   - 自算的定義與分母：還原收盤、股票、不含 ETF。
   - **官方與網站自算家數的差別**：上市官方股票欄不含 TDR、另列「無比價」。2026-11-03 網站自算多 3 漲 3 跌。
6. 資料完整性一條加：「第 5 輪新增上市／上櫃漲跌家數（2026-11-03 起）與 4 檔主動 ETF 持股 6 個資料集；持股在 ETF 上市日之前不算缺；跨境 ETF（00411A、00988A）的持股日晚一個交易日，公布日 22:00 後仍沒有才算異常」。

### `twstock/__main__.py`（附錄 C 的 diff 已包含）

- docstring 加 `history … --only holdings` 一行。
- `history --only` 的 choices 加 `holdings`，help 加「holdings = 主動型 ETF 持股」。

---

## 八、給 PG、QA 的提醒

### PG

- 第〇節步驟 1 的隔離基線**一定要在改任何程式之前**產生。
- 補抓請用 `logs/iter05_history.py`。它等同 `history --start 2025-10-30 --only holdings`，另外順手保存 3 份原始回應，**不多發請求**；之後 `test_e2_real_file` 會讀這些檔。
- 補抓期間不要執行 `collect` 或其他 `history`：同一主機有節流，鎖也會擋。
- `www.ezmoney.com.tw` 不是交易所。被拒（FetchError）時 `history` 會停，**等 30 分鐘以上再重跑，不要改標頭或加快間隔**。
- 不要動 `.env`、不要 commit、不要安裝排程；測試用 8001，結束時關閉。

### QA

- 附錄 B 的 SQL 都是唯讀。B-4 的「子集合核對」證明計算邏輯，原型口徑的總數則依附錄 B-4 第 1 表。
- console 檢查請用**新開的分頁**：未支援 ETF 不再發請求，但同一分頁先前的 404 紀錄會留著。
- 「無資料」清單若出現台灣交易日（E2-1-6 最後一列）、或補抓後某檔某天的檔數 < 近 20 日中位數 × 80%，請列為觀察事項並附日期。
- 網站驗收建議順序：ETF 列表 → 00981A → 1802 → 2330 → 1101 → 00988A → 00982A（未支援）→ 今日。

---

## 九、使用者決定事項

| # | 問題 | 決定 |
|---|---|---|
| **D10** | D9 的說明「權重變化才代表經理人主動調整」與資料不符（實測發現 1） | **使用者 2026-11-03 決定照建議修改**：「張數增減就是經理人的買賣；權重變化含股價影響」。兩欄照常同時顯示（E2-4-4） |

目前沒有待決事項。其他沿用第 4、5 輪 PM 第六節（使用者自行執行的排程、Docker 自動重啟等）。

---

## 附錄 A：資料來源驗證紀錄（2026-11-03 23:16，`fetch.request(isolated=True)`，不重試）

| # | 端點與參數 | 結果 | 用途 |
|---|---|---|---|
| 1 | `GetPCF` 49YTW `115/10/31`（週六） | 200，22,374 B，`asset: []`、`pcf` 日期為西元 1 年 | 非生效日 → 未公布格式 |
| 2 | `GetPCF` 49YTW `115/11/02` | 200，36,502 B，`TranDate` 2026-10-30（週五） | 週五 → 週一 |
| 3 | `GetPCF` 49YTW `115/11/05` | 200，22,374 B，`asset: []` | 尚未公布格式（mock #2、#3） |
| 4 | `GetPCF` 63YTW `115/11/04` | 200，35,338 B，`TranDate` 11/03，股票 50 檔 | 00403A delay 0 |
| 5 | `GetPCF` 64YTW `115/11/04` | 200，28,149 B，`TranDate` **11/02**，股票 30 檔（25 檔海外） | 00411A delay 1 |
| 6 | `GetPCF` 61YTW `115/11/04` | 200，35,948 B，`TranDate` **11/02**（`/Date` 格式），股票 34 檔（24 檔海外） | 00988A delay 1 |
| 7 | 櫃買 `afterTrading/highlight` `2026/11/03` | 200，710 B，「上櫃股票當日彙總資訊」 | A3 上櫃 |

- 分析師階段的 5 份 00981A 回應也有使用，SA 沒有重抓：`115/11/04`、`115/11/03`、`115/10/15`、`115/06/02`、`114/10/31`。
- 上市家數使用第 4 輪 PG 保存的 `logs/iter04_raw_MI_INDEX_20261103.json`。
- 原始回應保存在 SA 的暫存資料夾，不在專案內。測試需要的片段已原樣嵌入附錄 D，PG 補抓時會另外保存完整的 00981A 回應。

---

## 附錄 B：預期值與 QA 用 SQL（全部唯讀）

### B-1. 上市日與補抓完整性（E2-1 #2）

上市日（SA 已執行）：

```sql
SELECT e.etf_code, e.market_type, MIN(x.trade_date) AS first_day, COUNT(*) AS days
FROM etf_daily x JOIN etfs e ON e.etf_id = x.etf_id
WHERE e.etf_code IN ('00981A','00403A','00411A','00988A') GROUP BY e.etf_code, e.market_type;
-- 00981A TWSE 2025-10-30 244；00988A TWSE 2025-11-05 240；00403A TWSE 2026-05-12 119；00411A TPEx 2026-08-26 45
```

補抓後（QA）：每檔、每個 `etf_daily` 交易日都要有彙總列與至少 1 列股票。預期差異 0。跨境 2 檔若在 11/04 傍晚前補抓，11/03 例外（E2-1-1 #2★）。

```sql
SELECT e.etf_code, COUNT(*) AS missing
FROM etf_daily x JOIN etfs e ON e.etf_id = x.etf_id
WHERE e.etf_code IN ('00981A','00403A','00411A','00988A') AND x.trade_date <= '2026-11-03'
  AND (NOT EXISTS (SELECT 1 FROM etf_holding_summary s WHERE s.etf_id = x.etf_id AND s.hold_date = x.trade_date)
       OR NOT EXISTS (SELECT 1 FROM etf_holdings h WHERE h.etf_id = x.etf_id AND h.hold_date = x.trade_date AND h.asset_type = 'ST'))
GROUP BY e.etf_code;          -- 預期：沒有任何列
```

### B-2. 00981A 持股（E2-1 #3～#5；預期值來自 SA 保存的原始回應）

```sql
DECLARE @e INT = (SELECT etf_id FROM etfs WHERE etf_code = '00981A');
SELECT hold_date, post_date, nav, units, nav_unit, n_stocks, stock_weight, futures_lots, futures_amount
FROM etf_holding_summary WHERE etf_id = @e AND hold_date IN ('2025-10-30', '2026-10-30', '2026-11-02', '2026-11-03') ORDER BY hold_date;
SELECT hold_date, asset_type, code, month, name, shares, amount, weight FROM etf_holdings
WHERE etf_id = @e AND hold_date = '2026-11-03' AND code IN ('2330', '1802', 'TX');
-- 11/02 → 11/03 異動
WITH a AS (SELECT code, shares FROM etf_holdings WHERE etf_id = @e AND hold_date = '2026-11-02' AND asset_type = 'ST'),
     b AS (SELECT code, shares FROM etf_holdings WHERE etf_id = @e AND hold_date = '2026-11-03' AND asset_type = 'ST')
SELECT COALESCE(a.code, b.code) AS code, (ISNULL(b.shares, 0) - ISNULL(a.shares, 0)) / 1000 AS lots,
       CASE WHEN a.code IS NULL THEN 'new' WHEN b.code IS NULL THEN 'out' ELSE '' END AS kind
FROM a FULL JOIN b ON a.code = b.code WHERE ISNULL(a.shares, -1) <> ISNULL(b.shares, -1);
```

| 持股日 | 生效日 | 淨資產 | 單位 | 每單位淨值 | 股票檔數 | 股票權重 | 期貨口數 | 期貨名目本金 |
|---|---|---|---|---|---|---|---|---|
| 2025-10-30 | 2025-10-31 | 23,452,246,994 | 1,521,209,000 | 15.42 | **50** | 96.03 | 0 | 0 |
| 2026-10-30 | 2026-11-02 | 265,207,018,549 | 9,985,209,000 | 26.56 | 50 | 95.06 | 679 | 6,151,740,000 |
| 2026-11-02 | 2026-11-03 | 269,808,518,511 | 10,176,709,000 | 26.51 | 50 | 94.35 | 679 | 6,141,826,600 |
| 2026-11-03 | 2026-11-04 | **254,413,288,263** | 10,231,209,000 | 24.87 | **51** | **94.43** | **679** | 5,887,337,400 |

- 11/03 明細：
  - 2330 台積電：`shares` **14,464,000**、`amount` **33,194,880,000**、`weight` **13.05**。
  - 1802 台玻：8,479,000、574,028,300、0.23。
  - TX 台指期貨：`month` `2026/11`、679 口、5,887,337,400、2.31。
- 異動查詢預期**正好 4 列**：
  - 1802：+8,479，`new`。
  - 2330：+736。
  - 3376：−300。
  - 8210：−100。
- **其他 47 檔股數不變**，出清 0。
- 權重變化最大的 5 檔：2330 +1.19、3037 −0.29、6223 −0.20、8046 −0.17、2327 −0.16。除了 2330，另外 4 檔的張數都沒變（D10 的依據）。
- 其他 3 檔最新持股日：

| ETF | 持股日 | 股票檔數 | 海外 | 股票權重 | 淨資產（億） |
|---|---|---|---|---|---|
| 00403A | 11/03 | 50 | 0 | 85.85 | 1,185.23 |
| 00411A | 11/02 | 30 | 25 | 93.37 | 41.96 |
| 00988A | 11/02 | 34 | 24 | 92.50 | 418.18 |

### B-3. 網站（E2-4；原型匯出實測值）

- `etfs/00981A.json` 的 `sum` = `{d: "2026-11-03", nav: 2544.13, nu: 24.87, n: 51, sw: 94.43, fl: 679, fa: 58.87}`。
- `rows` 共 51 列，第一列 2330：`l` 14464、`pw` 13.05、`d1` 736、`w1` 1.19。1802：`new` 1、`d1` 8479、`w1` 0.23。`out` 為 `[]`。
- `stocks/1802.json` 的 `active` = `[{e: "00981A", d: "2026-11-03", l: 8479, w: 0.23, d1: 8479, d5: null, new: 1}]`。補抓後 `d5` 會是 8479：往前第 5 個持股日也沒有持有。
- `stocks/2330.json` 的 `active`：00403A 7,800 張 15.10%；00981A 14,464 張 13.05%（+736）；00988A 320 張 1.78%。
- `stocks/1101.json` 沒有 `active`。
- `latest.holdings` = 00981A、00403A（11/03），00411A、00988A（11/02）。

### B-4. 市場寬度與量能（A3 #2）

**原型口徑（還原收盤，全部股票）**：

| 資料日 | 市場 | 站上 MA20（分母） | 站上 MA60（分母） | 20 日新高 | 20 日新低 | 量能 |
|---|---|---|---|---|---|---|
| 11/03 | 上市 | **11.1%**（1,083） | **19.9%**（1,080） | 11 | 691 | **0.97** |
| 11/03 | 上櫃 | **12.1%**（867） | **19.0%**（863） | 16 | 560 | **0.86** |
| 11/02 | 上市 | 20.5%（1,086） | 29.3%（1,083） | 31 | 250 | 0.81 |
| 11/02 | 上櫃 | 18.7%（855） | 27.0%（851） | 38 | 233 | 0.66 |

**獨立核對（SQL；近 120 個交易日沒有任何 `price_events` 的股票、原始收盤；原型的 `breadth_calc` 套在同一個子集合，結果完全相同）**：

| 資料日 | 市場 | MA20 | MA60 | 新高 | 新低 |
|---|---|---|---|---|---|
| 11/03 | 上市 | 40／294 = 13.6% | 60／291 = 20.6% | 5 | 183 |
| 11/03 | 上櫃 | 44／317 = 13.9% | 71／314 = 22.6% | 4 | 183 |
| 11/02 | 上市 | 62／296 = 20.9% | 85／293 = 29.0% | 11 | 68 |
| 11/02 | 上櫃 | 66／309 = 21.4% | 90／306 = 29.4% | 12 | 75 |

```sql
DECLARE @end DATE = '2026-11-03';     -- 11/02 時改這裡
DECLARE @first DATE = (SELECT MIN(trade_date) FROM (SELECT DISTINCT TOP 120 trade_date FROM daily_prices
                                                     WHERE trade_date <= @end ORDER BY trade_date DESC) t);
WITH w AS (
    SELECT s.stock_code, s.market_type, d.trade_date, d.close_price
    FROM daily_prices d JOIN stocks s ON s.stock_id = d.stock_id
    WHERE d.trade_date BETWEEN @first AND @end AND d.close_price IS NOT NULL
      AND NOT EXISTS (SELECT 1 FROM price_events e WHERE e.stock_id = d.stock_id AND e.event_date BETWEEN @first AND @end)),
x AS (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY stock_code ORDER BY trade_date) AS j,
           AVG(close_price) OVER (PARTITION BY stock_code ORDER BY trade_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS ma20,
           AVG(close_price) OVER (PARTITION BY stock_code ORDER BY trade_date ROWS BETWEEN 59 PRECEDING AND CURRENT ROW) AS ma60,
           MAX(close_price) OVER (PARTITION BY stock_code ORDER BY trade_date ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING) AS hi20,
           MIN(close_price) OVER (PARTITION BY stock_code ORDER BY trade_date ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING) AS lo20
    FROM w)
SELECT market_type,
       SUM(CASE WHEN j >= 20 THEN 1 ELSE 0 END) AS n20, SUM(CASE WHEN j >= 20 AND close_price > ma20 THEN 1 ELSE 0 END) AS a20,
       SUM(CASE WHEN j >= 60 THEN 1 ELSE 0 END) AS n60, SUM(CASE WHEN j >= 60 AND close_price > ma60 THEN 1 ELSE 0 END) AS a60,
       SUM(CASE WHEN j >= 21 AND close_price > hi20 THEN 1 ELSE 0 END) AS hi, SUM(CASE WHEN j >= 21 AND close_price < lo20 THEN 1 ELSE 0 END) AS lo
FROM x WHERE trade_date = @end GROUP BY market_type;
-- 量能
WITH t AS (SELECT s.market_type, d.trade_date, SUM(CAST(d.trade_value AS FLOAT)) AS v
           FROM daily_prices d JOIN stocks s ON s.stock_id = d.stock_id WHERE d.trade_date <= @end GROUP BY s.market_type, d.trade_date),
     r AS (SELECT *, ROW_NUMBER() OVER (PARTITION BY market_type ORDER BY trade_date DESC) AS k FROM t)
SELECT market_type, MAX(CASE WHEN k = 1 THEN v END) / AVG(CASE WHEN k BETWEEN 2 AND 21 THEN v END) AS ratio
FROM r WHERE k <= 21 GROUP BY market_type;
-- 11/03：TWSE 0.97（當日 8,530 億）、TPEx 0.86（1,975 億）；11/02：0.81（7,185 億）、0.66（1,549 億）
```

- QA 要確認「QA 自己的分母口徑」和「網站寫的分母」一致。
- 原型口徑的總數，請把子集合 SQL 去掉 `NOT EXISTS` 條件，改用網站 `stocks/*.json` 的還原價（`prices.c` × 還原係數，與 52 週高低相同）重算；或直接以本表為準。
- 官方家數（A3 #1）：`SELECT * FROM market_breadth WHERE trade_date = '2026-11-03'`。上市 58／2／1000／33／22／6，上櫃 59／11／782／41／32／24。

### B-5. 既有表筆數不變（E2-1 #1）

步驟 1 與步驟 2 後各執行一次，數字要相同：

```sql
SELECT 'daily_prices', COUNT(*) FROM daily_prices UNION ALL SELECT 'etf_daily', COUNT(*) FROM etf_daily UNION ALL
SELECT 'margin_trades', COUNT(*) FROM margin_trades UNION ALL SELECT 'institutional_trades', COUNT(*) FROM institutional_trades UNION ALL
SELECT 'etfs', COUNT(*) FROM etfs;
```

---

## 附錄 C：原型對現有程式的完整 diff（已通過 `test_iter01`～`05`）

套用方式：在專案根目錄把下列各段存成一個 patch 檔，再執行 `git apply`；也可以照內容逐段手改。`twstock/collectors/holdings.py` 是新檔，完整內容就在 diff 裡。

```diff
diff --git a/site/app.css b/site/app.css
index d74588d..fbbd83c 100644
--- a/site/app.css
+++ b/site/app.css
@@ -187,8 +187,14 @@ table.tbl{width:100%;border-collapse:collapse;font-size:13px}
 .rel{text-decoration:underline dotted;text-underline-offset:3px;cursor:help}
 @media (max-width:520px){.g-stats .insti{grid-column:1/-1}}   /* 手機佔滿一列，三行數字不擠成 166px */
 .g-stats .margin{grid-column:1/-1}   /* 信用交易卡：行數多，佔滿一列 */
+.g-mk{grid-template-columns:repeat(4,minmax(0,1fr))}   /* 成交額 2 張＋三大法人 2 格寬，不留空欄 */
+.g-mk .insti{grid-column:span 2}
+@media (max-width:720px){.g-mk{grid-template-columns:repeat(2,minmax(0,1fr))}.g-mk .insti{grid-column:1/-1}}
 .night-old{opacity:.7}               /* P20：前一夜盤淡化 */
 .al{display:inline-block;font-style:normal;font-size:10px;line-height:15px;padding:0 3px;border-radius:3px;margin-left:4px;color:#fff;vertical-align:1px}
 .al-d{background:var(--up)}.al-n{background:var(--amber)}
 .pill.al-d{background:var(--up-bg);border-color:var(--up);color:var(--up)}
 .pill.al-n{background:color-mix(in srgb,var(--amber) 15%,transparent);border-color:var(--amber);color:var(--amber)}
+.al-new{background:var(--blue)}                                  /* E2-4：新建倉 */
+.pill.hold{margin-left:6px;border-color:var(--blue);color:var(--blue)}
+.tbl .nm .pill{font-size:10px;margin-left:6px}
diff --git a/site/app.js b/site/app.js
index ba03bfe..8368c99 100644
--- a/site/app.js
+++ b/site/app.js
@@ -62,7 +62,7 @@ const routes = {
   bubble: renderBubble,
   rank: renderRank,
   watch: renderWatch,
-  etf: renderEtf,
+  etf: code => code ? renderHoldings(code) : renderEtf(),
   stock: code => window.renderStock(code),
 };
 
@@ -131,12 +131,16 @@ function renderToday() {
   const topBuy = [...stocks].sort((a, b) => b[1].n1 - a[1].n1).slice(0, 10);
   const topSell = [...stocks].sort((a, b) => a[1].n1 - b[1].n1).slice(0, 10);
 
-  const mk = (m, label) => `<div class="card stat">
+  // A3：有官方家數時頭條改用官方（含漲停、跌停）；沒有時沿用網站自算
+  const mk = (m, label) => { const o = L.breadth?.[m]?.o, x = L.market[m];
+    return `<div class="card stat">
       <div class="l">${label}成交額</div>
-      <div class="v num">${fmt(L.market[m].turnover)}<span class="small muted"> 億</span></div>
-      <div class="s num">漲 <span class="up">${L.market[m].up}</span>　跌 <span class="dn">${L.market[m].down}</span>　平 <span class="flat">${L.market[m].flat}</span> 家</div>
-      <div class="s">一般股票，不含 ETF</div>
-    </div>`;
+      <div class="v num">${fmt(x.turnover)}<span class="small muted"> 億</span></div>
+      ${o ? `<div class="s num">漲 <span class="up">${fmt(o.up)}</span>（停 ${fmt(o.ul)}）　跌 <span class="dn">${fmt(o.dn)}</span>（停 ${fmt(o.dl)}）　平 <span class="flat">${fmt(o.fl)}</span>　未成交 ${fmt(o.nt)}</div>
+      <div class="s">家數為官方（股票）；成交額為網站自算，不含 ETF</div>`
+      : `<div class="s num">漲 <span class="up">${x.up}</span>　跌 <span class="dn">${x.down}</span>　平 <span class="flat">${x.flat}</span> 家</div>
+      <div class="s">一般股票，不含 ETF${L.breadth ? '；官方家數尚未取得，顯示自算' : ''}</div>`}
+    </div>`; };
   const bar = (g, color) => `<div class="bar-row" data-group="${esc(g.name)}">
       <span class="nm">${esc(g.name)}</span>
       <span class="bar-track"><span class="bar-fill" style="width:${Math.abs(g[key]) / maxAbs * 100}%;background:${color}"></span></span>
@@ -148,10 +152,11 @@ function renderToday() {
 
   $('#view').innerHTML = `
     <section class="sec grid g-stats">${indexCard(L.index?.TAIEX, '加權指數')}${indexCard(L.index?.TPEX, '櫃買指數')}</section>
-    <section class="sec grid g-stats">
+    <section class="sec grid g-stats g-mk">
       ${mk('TWSE', '上市')}${mk('TPEx', '上櫃')}
       ${instiCard(L)}
       ${marginCard(L)}
+      ${breadthCard(L)}
     </section>
 
     ${futuresHTML(L.futures)}
@@ -262,11 +267,26 @@ function marginCard(L) {
     </div>`;
 }
 
+// 市場寬度卡（A3＋A8）：全部為網站自算（還原收盤、股票、不含 ETF）；官方家數在成交額卡
+function breadthCard(L) {
+  const B = L.breadth;
+  if (!B) return '';
+  const pct = v => v == null ? '--' : fmt(v, 1) + '%';
+  const row = (x, name) => !x ? '' : `<div class="s num">${name}　站上 MA20 <b>${pct(x.ma20)}</b>（前日 ${pct(x.s20.at(-2))}）　MA60 <b>${pct(x.ma60)}</b>　20 日新高 <span class="up">${fmt(x.hi)}</span>、新低 <span class="dn">${fmt(x.lo)}</span>　量能 <b>${x.vr == null ? '--' : fmt(x.vr, 2) + ' 倍'}</b></div>`;
+  const T = B.TWSE, s = T?.s20.filter(v => v != null) || [];
+  return `<div class="card stat idx margin">
+      <div class="l">市場寬度 ${md(T?.d || B.TPEx?.d)}（自算，股票，不含 ETF）</div>
+      ${row(T, '上市')}${row(B.TPEx, '上櫃')}
+      ${spark(s)}${s.length ? `<div class="s">上市站上 MA20 比例，近 ${s.length} 個交易日（${md(T.from)} 起）</div>` : ''}
+      <div class="s">分母 = 當天有收盤、且有 20（MA60 為 60）個以上收盤的股票（上市 ${fmt(T?.n20)}、上櫃 ${fmt(B.TPEx?.n20)} 檔）；新高／新低 = 收盤高於／低於前 20 個收盤；量能 = 成交額 ÷ 前 20 日平均</div>
+    </div>`;
+}
+
 // 三大法人卡：上市用證交所官方金額（A2），上櫃另列估算值；尚無官方資料時維持第 1 輪估算卡
 function instiCard(L) {
   const O = L.insti_official, X = L.insti_otc, I = L.insti;
   const yi1 = v => v == null ? '--' : sgn(v, 1) + '億';
-  if (!O) return `<div class="card stat"><div class="l">三大法人（${md(L.flow_date)}）</div>
+  if (!O) return `<div class="card stat insti"><div class="l">三大法人（${md(L.flow_date)}）</div>
       <div class="v num ${cls(I.foreign + I.trust + I.dealer)}">${yi(I.foreign + I.trust + I.dealer)}</div>
       <div class="s num">外資 <span class="${cls(I.foreign)}">${yi(I.foreign)}</span>　投信 <span class="${cls(I.trust)}">${yi(I.trust)}</span>　自營 <span class="${cls(I.dealer)}">${yi(I.dealer)}</span></div>
       <div class="s">估算：買賣超張數 × 收盤價，不含 ETF</div></div>`;
@@ -671,7 +691,7 @@ function renderEtf() {
         <select id="etfSel" class="sel" aria-label="排序">${ETF_SORT.map(x => `<option value="${x[0]}"${x[0] === by ? ' selected' : ''}>${x[1]}</option>`).join('')}</select></div>
       <div class="card"><div class="tbl-wrap"><table class="tbl"><thead><tr>
         <th>ETF</th><th>收盤</th><th>漲跌</th><th>成交量</th><th>成交額</th><th>融資餘額</th><th>融資增減</th><th>融券餘額</th><th>融券增減</th></tr></thead><tbody>` +
-      list.map(([c, r]) => `<tr><td class="nm"><b>${esc(r.n)}</b><span>${c} ${r.m === 'TWSE' ? '上市' : '上櫃'}</span></td>
+      list.map(([c, r]) => `<tr${App.latest.holdings?.[c] ? ` data-etf="${c}"` : ''}><td class="nm"><b>${esc(r.n)}</b><span>${c} ${r.m === 'TWSE' ? '上市' : '上櫃'}</span>${holdTag(c)}</td>
         <td class="num ${cls(r.ch)}">${pfmt(r.c)}</td>
         <td class="num ${cls(r.ch)}">${r.c == null ? '無成交' : sgn(r.p) + '%'}</td>
         <td class="num">${fmt(r.v)}</td><td class="num">${fmt(r.tv, 2)}億</td>
@@ -681,6 +701,45 @@ function renderEtf() {
       <div class="muted small" style="margin-top:6px">共 ${list.length} 檔。成交量為張、成交額為億元；融資融券為張，增減 = 今日餘額 − 前日餘額，「--」表示不在信用交易清單。ETF 不計入首頁家數、成交額、類股資金流、排行、自選與股票口徑的融資融券。</div></section>`;
   $('#etfSel').addEventListener('change', e => { localStore('etfSort', null, e.target.value); renderEtf(); });
   onSeg('etfMktSeg', v => { localStore('etfMkt', null, v); renderEtf(); });
+  $('#view').addEventListener('click', e => { const tr = e.target.closest('tr[data-etf]'); if (tr) location.hash = '#/etf/' + tr.dataset.etf; });
+}
+
+// E2-4：已支援持股的主動 ETF 可點；其他主動型（代號 A 結尾）標示尚未支援
+const holdTag = c => App.latest.holdings?.[c] ? `<a class="pill hold" href="#/etf/${c}">持股</a>`
+  : /A$/.test(c) ? '<span class="pill muted">持股尚未支援</span>' : '';
+
+const HOLD_SORT = [['pw', '權重'], ['d1', '張數增減'], ['w1', '權重變化']];
+
+async function renderHoldings(code) {
+  // 不在支援清單就不請求（避免 404）
+  const H = App.latest.holdings?.[code] && await getJSON(`data/etfs/${code}.json`);
+  if (!H) { $('#view').innerHTML = `<div class="empty">${esc(code)} 的持股資料尚未支援（目前只有統一投信 4 檔主動 ETF）</div>`; return; }
+  const S = H.sum, by = localStore('holdSort', 'pw'), unit = r => r.tw ? '張' : '股';
+  const rows = [...H.rows].sort((a, b) => (b[by] ?? -Infinity) - (a[by] ?? -Infinity));
+  const prev = H.dates.at(-2), d5 = H.dates.length > 5 ? H.dates.at(-6) : null;
+  const chg = (v, d = 0) => `<td class="num ${cls(v)}">${v == null ? '--' : sgn(v, d)}</td>`;
+  const name = r => r.tw ? `<b>${esc(r.n)}</b><span>${esc(r.c)}</span>` : `<b>${esc(r.n)}</b><span>${esc(r.c)}（海外）</span>`;
+  $('#view').innerHTML = `<section class="sec card">
+      <div class="sec-h"><h2>${esc(H.n)}</h2><span class="muted small">${code}　${H.m === 'TWSE' ? '上市' : '上櫃'}　持股日 ${md(S.d)}${H.delay ? '（跨境，晚一個交易日公布）' : ''}</span>
+        <span class="sp"></span><a class="muted small" href="#/etf">← ETF 列表</a></div>
+      <div class="grid g-stats">
+        ${[['淨資產', fmt(S.nav, 1) + ' 億'], ['每單位淨值', fmt(S.nu, 2) + ' 元'], ['股票權重合計', fmt(S.sw, 2) + '%'], ['持股檔數', fmt(S.n) + ' 檔'],
+           ['期貨', S.fl ? `${fmt(S.fl)} 口（${fmt(S.fa, 1)} 億）` : '無']].map(([l, v]) => `<div class="card stat"><div class="l">${l}</div><div class="v num" style="font-size:16px">${v}</div></div>`).join('')}
+      </div></section>
+    <section class="sec card">
+      <div class="sec-h"><h2>持股</h2><span class="muted small">${prev ? `1 日：相對 ${md(prev)}` : '只有一個持股日'}${d5 ? `；5 日：相對 ${md(d5)}` : ''}</span><span class="sp"></span>${segHTML('holdSeg', HOLD_SORT, by)}</div>
+      <div class="tbl-wrap"><table class="tbl"><thead><tr><th>股票</th><th>持有</th><th>權重</th><th>1 日增減</th><th>1 日權重變化</th><th>5 日增減</th></tr></thead><tbody>` +
+      rows.map(r => `<tr${r.tw ? ` data-code="${esc(r.c)}"` : ''}><td class="nm">${name(r)}${r.new ? '<i class="al al-new">新</i>' : ''}</td>
+        <td class="num">${fmt(r.l)} ${unit(r)}</td><td class="num">${fmt(r.pw, 2)}%</td>${chg(r.d1)}${chg(r.w1, 2)}${chg(r.d5)}</tr>`).join('') +
+      `</tbody></table></div>
+      ${H.out.length ? `<div class="sec-h" style="margin-top:12px"><h2>出清</h2><span class="muted small">${md(prev)} 持有、${md(S.d)} 已無</span></div>
+        <div class="tbl-wrap"><table class="tbl"><thead><tr><th>股票</th><th>${md(prev)} 持有</th><th>權重</th></tr></thead><tbody>` +
+        H.out.map(r => `<tr${r.tw ? ` data-code="${esc(r.c)}"` : ''}><td class="nm">${name(r)}</td><td class="num">${fmt(r.l)} ${unit(r)}</td><td class="num">${fmt(r.pw, 2)}%</td></tr>`).join('') +
+        '</tbody></table></div>' : ''}
+      <div class="muted small" style="margin-top:6px">資料來源：統一投信每日申購買回清單。台股為張、海外為股；權重為占基金淨資產 %，權重變化為百分點。
+        本基金為現金申購買回，持股不會隨申購按比例增減：<b>張數增減就是經理人的買賣</b>；權重變化另含股價漲跌的影響（張數不變、權重也會變）。標「新」= 前一持股日沒有持有。</div></section>`;
+  onSeg('holdSeg', v => { localStore('holdSort', null, v); renderHoldings(code); });
+  $('#view').addEventListener('click', onRowClick);
 }
 
 function renderWatch() {
diff --git a/site/stock.js b/site/stock.js
index 4517df4..1994301 100644
--- a/site/stock.js
+++ b/site/stock.js
@@ -51,6 +51,17 @@ window.renderStock = async function (code) {
        ['券資比', MG.sr == null ? '--' : fmt(MG.sr, 2) + '%', '', '資料 ' + md(MG.d)],
        ['融資使用率', MG.mu == null ? '--' : fmt(MG.mu, 2) + '%', '', mgNote ? '次一營業日' + mgNote : '資料 ' + md(MG.d)]];
 
+  // E2-4：主動 ETF 持有（只含統一投信 4 檔；沒有任何一檔持有時不顯示）
+  const AC = data.active;
+  const acHTML = !AC ? '' : `<section class="sec card">
+      <div class="sec-h"><h2>主動 ETF 持有</h2><span class="muted small">目前只含統一投信 4 檔主動 ETF</span></div>
+      <div class="tbl-wrap"><table class="tbl"><thead><tr><th>ETF</th><th>張數</th><th>權重</th><th>1 日</th><th>5 日</th><th>持股日</th></tr></thead><tbody>` +
+      AC.map(a => `<tr><td class="nm"><a href="#/etf/${a.e}"><b>${esc(App.latest.holdings?.[a.e]?.n || a.e)}</b><span>${a.e}</span></a>${a.new ? '<i class="al al-new">新</i>' : ''}</td>
+        <td class="num">${fmt(a.l)}</td><td class="num">${fmt(a.w, 2)}%</td>
+        <td class="num ${cls(a.d1)}">${a.d1 == null ? '--' : sgn(a.d1, 0)}</td><td class="num ${cls(a.d5)}">${a.d5 == null ? '--' : sgn(a.d5, 0)}</td>
+        <td class="num">${md(a.d)}</td></tr>`).join('') +
+      '</tbody></table></div><div class="muted small" style="margin-top:6px">張數增減為經理人買賣（現金申購買回，不會按比例被動增減）；權重為占該 ETF 淨資產 %，含股價漲跌影響。</div></section>';
+
   $('#view').innerHTML = `
     <section class="sec card">
       <div class="s-head">
@@ -84,6 +95,7 @@ window.renderStock = async function (code) {
          ['外資5日', yi(s?.f5), cls(s?.f5), '至 ' + fd], ['投信5日', yi(s?.t5), cls(s?.t5), '至 ' + fd], ...mgCards]
         .map(([l, v, c, sub]) => `<div class="card stat"><div class="l">${l}</div><div class="v num ${c || ''}" style="font-size:16px">${v}</div>${sub ? `<div class="s">${sub}</div>` : ''}</div>`).join('')}
     </section>
+    ${acHTML}
 
     <section class="sec card">
       <div class="sec-h">
diff --git a/tests/test_iter03.py b/tests/test_iter03.py
index a5b3406..2fff917 100644
--- a/tests/test_iter03.py
+++ b/tests/test_iter03.py
@@ -102,7 +102,8 @@ def _full_snapshot(days, skip=()):
     ok = {"prices.TWSE": Row(1086), "prices.TPEx": Row(889), "pe.TWSE": Row(1082, 870, 1082, 1082),
           "pe.TPEx": Row(888, 675, 888, 888), "insti.TWSE": Row(1077), "insti.TPEx": Row(784), "amount": Row(6),
           "index.TAIEX": Row(1), "index.TPEX": Row(1), "futures": Row(6), "futures_oi": Row(9),
-          "etf.TWSE": Row(250), "etf.TPEx": Row(120), "margin.TWSE": Row(1100), "margin.TPEx": Row(900)}   # 第 4 輪
+          "etf.TWSE": Row(250), "etf.TPEx": Row(120), "margin.TWSE": Row(1100), "margin.TPEx": Row(900),   # 第 4 輪
+          "breadth.TWSE": Row(1), "breadth.TPEx": Row(1), **{f"holdings.{c}": Row(50) for c in health.HOLDINGS}}   # 第 5 輪
     return {k: {d: v for d in days if (k, d) not in skip} for k, v in ok.items()}
 
 
@@ -357,7 +358,7 @@ INX_FIELDS = ["日期", "開市", "最高", "最低", "收市", "漲/跌"]
 FUT_HEAD = "交易日期,契約,到期月份(週別),開盤價,最高價,最低價,收盤價,漲跌價,漲跌%,成交量,結算價,未沖銷契約數,最後最佳買價,最後最佳賣價,歷史最高價,歷史最低價,是否因訊息面暫停交易,交易時段,價差對單式委託成交量\r\n"
 OI_HEAD = "日期,商品名稱,身份別,多方交易口數,多方交易契約金額(千元),空方交易口數,空方交易契約金額(千元),多空交易口數淨額,多空交易契約金額淨額(千元),多方未平倉口數,多方未平倉契約金額(千元),空方未平倉口數,空方未平倉契約金額(千元),多空未平倉口數淨額,多空未平倉契約金額淨額(千元)\r\n"
 ALL_EP = ("MI_INDEX", "BWIBBU_d", "fund/T86", "BFI82U", "dailyQuotes", "peQryDate", "dailyTrade", "futDataDown", "futContractsDateDown",
-          "MI_MARGN", "margin/balance")
+          "MI_MARGN", "margin/balance", "highlight", "GetPCF")     # 第 5 輪：GetPCF 的日期是持股日
 # 第 4 輪：行情回應含 ETF 列（另有權證、TDR 等其他證券，兩邊都不可寫入）；融資融券回應含股票與 ETF
 TWSE_ETFS = [f"00{n:03d}" for n in range(100, 350)]          # 250 檔，如 00100
 TPEX_ETFS = [f"00{n:03d}B" for n in range(700, 820)]         # 120 檔，如 00700B
@@ -399,8 +400,8 @@ class World:
         return [p for p, _ in self.requests]
 
     # ── HTTP ──
-    def http(self, method, url, timeout=30, params=None, data=None):
-        form = params or data or {}
+    def http(self, method, url, timeout=30, params=None, data=None, json=None):
+        form = params or data or json or {}
         path = re.sub(r"https://[^/]+", "", url)
         self.requests.append((path, form))
         for ep in self.down:
@@ -411,7 +412,7 @@ class World:
         for key, fn in (("MI_INDEX", self._mi), ("BWIBBU_d", self._bwi), ("fund/T86", self._t86), ("BFI82U", self._bfi),
                         ("dailyQuotes", self._quotes), ("peQryDate", self._pe), ("dailyTrade", self._tpex_insti),
                         ("indexInfo/inx", self._inx), ("futDataDown", self._fut), ("futContractsDateDown", self._oi),
-                        ("MI_MARGN", self._mgn), ("margin/balance", self._tpex_mgn)):
+                        ("MI_MARGN", self._mgn), ("margin/balance", self._tpex_mgn), ("highlight", self._hl), ("GetPCF", self._pcf)):
             if key in url:
                 return fn(form)
         return Resp([]) if "openapi" in url else Resp({"stat": "沒有資料", "tables": []})
@@ -433,7 +434,30 @@ class World:
         rows = [[c, "名", "1000", "10", "10000", "10", "11", "9", "10.5", "+", "0.5"] for c in TWSE_CODES + etfs + OTHERS]
         idx = {"title": "價格指數(臺灣證券交易所)", "fields": ["指數", "收盤指數", "漲跌(+/-)", "漲跌點數", "漲跌百分比(%)"],
                "data": [["發行量加權股價指數", "45,211.83", "<p>-</p>", "1,156.50", "-2.49"]]}
-        return Resp({"stat": "OK", "tables": [idx, {"fields": fields, "data": rows}]})
+        breadth = {"title": "漲跌證券數合計", "fields": ["類型", "整體市場", "股票"],                     # 第 5 輪
+                   "data": [["上漲(漲停)", "1(0)", "58(2)"], ["下跌(跌停)", "1(0)", "1,000(33)"], ["持平", "1", "22"], ["未成交", "1", "6"]]}
+        return Resp({"stat": "OK", "tables": [idx, breadth, {"fields": fields, "data": rows}]})
+
+    def _hl(self, form):
+        if self._no("highlight", form):
+            return Resp({"stat": "ok", "tables": []})
+        fields = ["上漲家數", "漲停家數", "下跌家數", "跌停家數", "平盤家數", "未成交(含暫停交易)家數"]
+        return Resp({"stat": "ok", "tables": [{"fields": fields, "data": [["59", "11", "782", "41", "32", "24"]]}]})
+
+    def _pcf(self, form):
+        """date 是生效日（民國）：往回第 delay + 1 個交易日才是持股日。"""
+        y, m, dd = form["date"].split("/")
+        post = date(int(y) + 1911, int(m), int(dd))
+        delay = next(v[1] for v in health.HOLDINGS.values() if v[0] == form["fundCode"])
+        hold = tradingcal.trading_days(post - timedelta(days=30), post - timedelta(days=1), CLOSED)[-1 - delay]
+        if hold not in self.published["GetPCF"]:
+            return Resp({"pcf": [{"PCFCode": "NAV", "TranDate": "/Date(-62135596800000)/", "PostDate": "/Date(-62135596800000)/",
+                                  "Amount": 0}], "fund": {}, "asset": []})
+        t = f"{hold}T00:00:00"
+        stocks = [{"TranDate": t, "DetailCode": str(c), "DetailName": "名", "Share": 1000.0, "Amount": 1.0, "NavRate": 1.0,
+                   "MoneyType": "NTD", "MTH": "", "EditTime": f"{hold}T16:30:00"} for c in range(1100, 1150)]
+        return Resp({"pcf": [{"PCFCode": "NAV", "TranDate": t, "PostDate": f"{post}T00:00:00", "Amount": 1e9}], "fund": {},
+                     "asset": [{"AssetCode": "ST", "Details": stocks}, {"AssetCode": "GD", "Details": None}]})
 
     def _bwi(self, form):
         if self._no("BWIBBU_d", form):
@@ -539,6 +563,10 @@ class World:
                 if mine:
                     cnt = lambda f: sum(r.get(f) is not None for r in mine)
                     self.rows[f"{name}.{mk}"][pd] = Row(len(mine), cnt("pe_ratio"), cnt("pb_ratio"), cnt("dividend_yield"))
+        elif table == "market_breadth":                         # 第 5 輪
+            self.rows[f"breadth.{rows[0]['market']}"][date.fromisoformat(rows[0]["trade_date"])] = Row(1)
+        elif table == "etf_holding_summary":                    # etf_id 就是 ETF 代號（見 FakeCursor）
+            self.rows[f"holdings.{params[1]}"][date.fromisoformat(rows[0]["hold_date"])] = Row(rows[0]["n_stocks"])
         elif table == "market_index":
             for r in rows:
                 self.rows[f"index.{r['index_code']}"][date.fromisoformat(r["trade_date"])] = Row(1)
@@ -572,6 +600,8 @@ class FakeCursor:
             w.apply_merge(m.group(1), sql, params)
         elif m:
             w.merges.append("stocks")
+        elif "SELECT etf_id FROM etfs WHERE etf_code" in sql:
+            self.result = [(params[0],)]
         elif "SELECT MAX(trade_date) FROM daily_prices" in sql:
             ds = sorted(w.rows["prices.TWSE"])
             self.result = [(ds[-1] if ds else None,)]
diff --git a/tests/test_iter04.py b/tests/test_iter04.py
index 160faea..05e7371 100644
--- a/tests/test_iter04.py
+++ b/tests/test_iter04.py
@@ -513,7 +513,7 @@ def test_t25_banner_text():
 
 def test_t26_specs_and_keys():
     keys = [s.key for s in health.SPECS]
-    assert keys[-4:] == ["etf.TWSE", "etf.TPEx", "margin.TWSE", "margin.TPEx"]
+    assert keys[keys.index("etf.TWSE"):][:4] == ["etf.TWSE", "etf.TPEx", "margin.TWSE", "margin.TPEx"]     # 第 5 輪之後還有新鍵
     assert daily.DAY_KEYS.index("etf.TWSE") < daily.DAY_KEYS.index("margin.TWSE")
     assert set(daily.DAY_KEYS) | {"index.TPEX", "futures", "futures_oi"} == set(keys)
     assert daily.ALL_DATASETS == ("prices", "pe", "insti", "etf", "margin")
diff --git a/twstock/__main__.py b/twstock/__main__.py
index b9997b2..703d9ef 100644
--- a/twstock/__main__.py
+++ b/twstock/__main__.py
@@ -11,6 +11,7 @@
   python -m twstock history --start 2025-10-30 --only tpex_index  只補櫃買指數（一個月一個請求）
   python -m twstock history --start 2026-07-31 --only amount  只補上市三大法人買賣金額
   python -m twstock history --start 2025-10-30 --only etf margin  只補 ETF 行情與融資融券（同一天 ETF 先於融資融券）
+  python -m twstock history --start 2025-10-30 --only holdings    只補主動型 ETF 持股（統一投信 4 檔；上市日之前自動略過）
   python -m twstock revenue --year 2026 --month 9    收集指定月份營收
   python -m twstock events --start 2025-10-30        補抓除權息／減資／面額變更事件（還原價格用）
   python -m twstock export                           從資料庫匯出網站 JSON（site/data）
@@ -181,9 +182,10 @@ def main(argv=None):
     s = sub.add_parser("history", help="補抓歷史資料")
     s.add_argument("--start", type=_date, required=True)
     s.add_argument("--end", type=_date, help="預設今天")
-    s.add_argument("--only", nargs="+", choices=["prices", "pe", "insti", "index", "amount", "tpex_index", "etf", "margin"],
+    s.add_argument("--only", nargs="+", choices=["prices", "pe", "insti", "index", "amount", "tpex_index", "etf", "margin", "holdings"],
                    help="只抓指定資料集（pe = 本益比／淨值比／殖利率，index = 加權指數，tpex_index = 櫃買指數，"
-                        "amount = 上市三大法人買賣金額，etf = ETF 行情，margin = 融資融券）；預設 prices pe insti etf margin")
+                        "amount = 上市三大法人買賣金額，etf = ETF 行情，margin = 融資融券，holdings = 主動型 ETF 持股）；"
+                        "預設 prices pe insti etf margin")
     s.add_argument("--force", action="store_true", help="已存在的日期也重抓覆寫")
     s.add_argument("--no-revenue", action="store_true")
     s.add_argument("--delay", type=float, default=0.0, help="每日之間額外暫停秒數")
diff --git a/twstock/collectors/catchup.py b/twstock/collectors/catchup.py
index 5e667b9..287dbfd 100644
--- a/twstock/collectors/catchup.py
+++ b/twstock/collectors/catchup.py
@@ -48,7 +48,7 @@ def make_plan(now: datetime, n: int, snap: dict, state: dict, closed: set, reven
         return plan
     med = medians(snap)
     for d in days:
-        keys = missing_keys(d, DAY_KEYS, snap, med)
+        keys = missing_keys(d, DAY_KEYS, snap, med, days)       # 跨境 ETF 持股要等下一個交易日才抓
         if keys:
             plan["by_date"].append((d, keys))
     plan["tpex_months"] = sorted({month_key(d) for d in days if missing_keys(d, ("index.TPEX",), snap, med)})
@@ -306,7 +306,7 @@ def _run_locked(days, date_, no_revenue, no_export, notify, now, export_all) ->
     # closed 的起點要和匯出時相同（export 的資料日是兩市場的最新日），否則只有上櫃公布時會誤判為變動
     site_date = max((d for k in ("prices.TWSE", "prices.TPEx") for d, r in after[k].items() if r.n), default=None)
     need_export = not no_export and (date_ is not None or changed or
-                                     (data_date is not None and status_changed(health.dataset_status(after, data_date, now),
+                                     (data_date is not None and status_changed(health.dataset_status(after, data_date, now, closed),
                                                                                health.site_closed(closed, site_date))))
     if need_export:
         export_seconds = None
diff --git a/twstock/collectors/daily.py b/twstock/collectors/daily.py
index f46d58c..4233e27 100644
--- a/twstock/collectors/daily.py
+++ b/twstock/collectors/daily.py
@@ -1,5 +1,5 @@
 """
-每日資料：上市 + 上櫃的收盤行情、本益比/殖利率、三大法人買賣超、ETF 行情、融資融券。
+每日資料：上市 + 上櫃的收盤行情、本益比/殖利率、三大法人買賣超、ETF 行情、融資融券、官方漲跌家數、主動 ETF 持股。
 
 寫入採批次：整批資料序列化成一個 JSON 參數，由 OPENJSON 展開後 MERGE；
 每張表一次資料庫往返，取代逐筆查詢/更新的上萬次往返。
@@ -9,21 +9,26 @@ from datetime import date
 
 from .. import db
 from ..fetch import FetchError, SchemaError, clean_number, is_etf_code, is_valid_stock_code, request
+from ..health import HOLDINGS
+from ..tradingcal import load_closed
+from .holdings import fetch_holdings, merge_holdings
 
 TWSE = "https://www.twse.com.tw/rwd/zh"
 TPEX = "https://www.tpex.org.tw/www/zh-tw"
 
 # history --only 的資料集名稱；INDEX = 加權指數（抓行情時會一併寫入），TPEX_INDEX = 櫃買指數（月查詢）
 PRICES, PE, INSTI, INDEX, AMOUNT, TPEX_INDEX = "prices", "pe", "insti", "index", "amount", "tpex_index"
-ETF, MARGIN = "etf", "margin"
+ETF, MARGIN, HOLDINGS_DS = "etf", "margin", "holdings"
 ALL_DATASETS = (PRICES, PE, INSTI, ETF, MARGIN)
+HOLDINGS_KEYS = tuple(f"holdings.{c}" for c in HOLDINGS)
 # 每個資料集對應的細項（分市場），也是 collect_for_date 與 health.SPECS 共用的鍵
 DATASET_KEYS = {PRICES: ("prices.TWSE", "prices.TPEx"), PE: ("pe.TWSE", "pe.TPEx"),
                 INSTI: ("insti.TWSE", "insti.TPEx"), INDEX: ("index.TAIEX",), AMOUNT: ("amount",),
-                ETF: ("etf.TWSE", "etf.TPEx"), MARGIN: ("margin.TWSE", "margin.TPEx")}
-# 一天之內的收集順序：行情先於本益比、法人；ETF 行情先於融資融券（融資融券的 ETF 列只寫入 etfs 已有的 ETF）
+                ETF: ("etf.TWSE", "etf.TPEx"), MARGIN: ("margin.TWSE", "margin.TPEx"), HOLDINGS_DS: HOLDINGS_KEYS}
+# 一天之內的收集順序：行情先於本益比、法人；ETF 行情先於融資融券與持股（兩者都只寫入 etfs 已有的 ETF）
+# 漲跌家數不補歷史（health.BREADTH_FROM），所以不在 DATASET_KEYS；上市家數與行情共用同一個 MI_INDEX 回應
 DAY_KEYS = ("prices.TWSE", "prices.TPEx", "index.TAIEX", "etf.TWSE", "etf.TPEx", "pe.TWSE", "pe.TPEx",
-            "insti.TWSE", "insti.TPEx", "amount", "margin.TWSE", "margin.TPEx")
+            "insti.TWSE", "insti.TPEx", "amount", "margin.TWSE", "margin.TPEx", "breadth.TWSE", "breadth.TPEx") + HOLDINGS_KEYS
 PARSE_ERRORS = (SchemaError, KeyError, IndexError, TypeError, ValueError, AttributeError)
 
 
@@ -71,10 +76,17 @@ def _twse_quote(row: list, idx: dict) -> dict:
     }
 
 
-def fetch_twse_daily(d: date):
-    """上市每日收盤行情、加權指數、ETF 原始列 → (股票列, 指數, (欄位索引, ETF 原始列))；休市回傳 ([], None, ({}, []))。"""
-    data = request("GET", f"{TWSE}/afterTrading/MI_INDEX",
+def _mi_index(d: date) -> dict:
+    return request("GET", f"{TWSE}/afterTrading/MI_INDEX",
                    params={"response": "json", "date": f"{d:%Y%m%d}", "type": "ALLBUT0999"})
+
+
+def fetch_twse_daily(d: date, data=None):
+    """
+    上市每日收盤行情、加權指數、ETF 原始列 → (股票列, 指數, (欄位索引, ETF 原始列))；休市回傳 ([], None, ({}, []))。
+    data：已取得的 MI_INDEX 回應（與漲跌家數共用），None 時才發請求。
+    """
+    data = _mi_index(d) if data is None else data
     if data.get("stat") != "OK":
         return [], None, ({}, [])
     taiex = parse_taiex(data, d)
@@ -127,6 +139,29 @@ def fetch_twse_insti(d: date) -> dict:
     return result
 
 
+def _count(text) -> tuple:
+    """'1,000(33)' → (1000, 33)；沒有括號 → (數字, None)。"""
+    head, _, tail = str(text).partition("(")
+    return clean_number(head, int), clean_number(tail.rstrip(")"), int) if tail else None
+
+
+def parse_twse_breadth(data: dict, d: date):
+    """MI_INDEX 的「漲跌證券數合計」股票欄 → 一列；休市回傳 None；有行情卻沒有這張表 → SchemaError。"""
+    if data.get("stat") != "OK":
+        return None
+    for table in data.get("tables", []):
+        if (table.get("title") or "").strip() != "漲跌證券數合計":
+            continue
+        fields = table.get("fields", [])
+        if "股票" not in fields or "類型" not in fields:
+            raise SchemaError("漲跌證券數合計 缺少「類型」或「股票」欄")
+        rows = {str(r[fields.index("類型")]).strip(): r[fields.index("股票")] for r in table.get("data", [])}
+        (up, up_limit), (down, down_limit) = _count(rows["上漲(漲停)"]), _count(rows["下跌(跌停)"])
+        return {"trade_date": d.isoformat(), "market": "TWSE", "up": up, "up_limit": up_limit, "down": down,
+                "down_limit": down_limit, "flat": _count(rows["持平"])[0], "no_trade": _count(rows["未成交"])[0]}
+    raise SchemaError("MI_INDEX 找不到「漲跌證券數合計」表")
+
+
 # ─── 上櫃 ─────────────────────────────────────────────────
 def _tpex_tables(path: str, d: date) -> list:
     data = request("POST", f"{TPEX}/{path}", data={"date": f"{d:%Y/%m/%d}", "response": "json"})
@@ -163,6 +198,22 @@ def fetch_tpex_daily(d: date) -> tuple:
     return [], None, ({}, [])
 
 
+def parse_tpex_breadth(tables: list, d: date):
+    """afterTrading/highlight 的「上櫃股票當日彙總資訊」→ 一列；未公布（沒有資料表）回傳 None。"""
+    if not tables:
+        return None
+    idx = {f: i for i, f in enumerate(tables[0]["fields"])}
+    row = tables[0]["data"][0]
+    get = lambda f: clean_number(row[idx[f]], int)
+    return {"trade_date": d.isoformat(), "market": "TPEx", "up": get("上漲家數"), "up_limit": get("漲停家數"),
+            "down": get("下跌家數"), "down_limit": get("跌停家數"), "flat": get("平盤家數"),
+            "no_trade": get("未成交(含暫停交易)家數")}
+
+
+def fetch_tpex_breadth(d: date):
+    return parse_tpex_breadth(_tpex_tables("afterTrading/highlight", d), d)
+
+
 def parse_etf_quotes(raw: tuple, market: str) -> list:
     """(欄位索引, ETF 原始列) → 寫入用 dict（鍵與股票行情相同）。股票列存在卻沒有任何 ETF 列 → SchemaError。"""
     idx, rows = raw
@@ -617,11 +668,27 @@ def merge_insti_amount(cursor, rows: list):
     """, db.to_json(rows))
 
 
+def merge_breadth(cursor, row: dict):
+    cursor.execute("""
+        MERGE market_breadth AS t
+        USING OPENJSON(?) WITH (
+            trade_date DATE, market NVARCHAR(10), up INT, up_limit INT, down INT, down_limit INT, flat INT, no_trade INT
+        ) AS s
+        ON t.trade_date = s.trade_date AND t.market = s.market
+        WHEN MATCHED THEN UPDATE SET
+            up = s.up, up_limit = s.up_limit, down = s.down, down_limit = s.down_limit, flat = s.flat, no_trade = s.no_trade
+        WHEN NOT MATCHED THEN
+            INSERT (trade_date, market, up, up_limit, down, down_limit, flat, no_trade)
+            VALUES (s.trade_date, s.market, s.up, s.up_limit, s.down, s.down_limit, s.flat, s.no_trade);
+    """, db.to_json([row]))
+
+
 def _save(fn, *args):
     conn = db.connect()
     try:
-        fn(conn.cursor(), *args)
+        result = fn(conn.cursor(), *args)
         conn.commit()
+        return result
     finally:
         conn.close()
 
@@ -640,7 +707,11 @@ def _quotes(market: str, d: date, cache: dict) -> tuple:
     """同一市場的行情回應只抓一次：股票行情、加權指數、ETF 共用；失敗也快取，同一次執行不重打。"""
     if market not in cache:
         try:
-            cache[market] = fetch_twse_daily(d) if market == "TWSE" else fetch_tpex_daily(d)
+            if market == "TWSE":
+                cache["MI_INDEX"] = _mi_index(d)                # 漲跌家數也從這個回應解析
+                cache[market] = fetch_twse_daily(d, cache["MI_INDEX"])
+            else:
+                cache[market] = fetch_tpex_daily(d)
         except (FetchError, *PARSE_ERRORS) as e:
             cache[market] = e
     if isinstance(cache[market], Exception):
@@ -681,6 +752,30 @@ def _collect_key(key: str, d: date, cache: dict) -> int:
         if insti:
             _save(merge_institutional, d, [{"stock_code": c, **r} for c, r in insti.items()])
         return len(insti)
+    if dataset == "breadth":
+        if market == "TWSE":
+            _quotes("TWSE", d, cache)                   # 行情抓取失敗時這裡丟出同一個例外
+            row = parse_twse_breadth(cache["MI_INDEX"], d)
+        else:
+            row = fetch_tpex_breadth(d)
+        if row:
+            _save(merge_breadth, row)
+        return 1 if row else 0
+    if dataset == HOLDINGS_DS:
+        if "closed" not in cache:
+            conn = db.connect()
+            try:
+                cache["closed"] = load_closed(conn.cursor())
+            finally:
+                conn.close()
+        got = fetch_holdings(market, d, cache["closed"])
+        if not got:
+            return 0                                    # 尚未公布，或回應的持股日不是 d
+        summary, rows = got
+        if not _save(merge_holdings, market, summary, rows):
+            print(f"  ⚠️  etfs 沒有 {market}，持股未寫入")
+            return 0
+        return summary["n_stocks"]
     if dataset == MARGIN:
         rows, total = (fetch_twse_margin if market == "TWSE" else fetch_tpex_margin)(d)
         stocks = [r for r in rows if is_valid_stock_code(r["stock_code"])]
@@ -706,8 +801,8 @@ def collect_for_date(d: date, keys=DAY_KEYS) -> tuple:
     written, errors, cache = {}, {}, {}
     for key in keys:
         dataset, _, market = key.partition(".")
-        if dataset in ("pe", "insti", MARGIN) and written.get(f"prices.{market}") == 0:
-            continue                # 同市場行情還沒有：本益比、法人、融資融券不可能先有，不發請求
+        if dataset in ("pe", "insti", MARGIN, "breadth") and written.get(f"prices.{market}") == 0:
+            continue                # 同市場行情還沒有：本益比、法人、融資融券、漲跌家數不可能先有，不發請求
         if dataset == "pe" and f"prices.{market}" in errors:
             continue                # 本益比只寫入有行情列的股票
         try:
@@ -724,4 +819,4 @@ def collect_for_date(d: date, keys=DAY_KEYS) -> tuple:
     return written, errors
 
 
-__all__ = ["collect_for_date", "FetchError", "PRICES", "PE", "INSTI", "ETF", "MARGIN", "ALL_DATASETS"]
+__all__ = ["collect_for_date", "FetchError", "PRICES", "PE", "INSTI", "ETF", "MARGIN", "HOLDINGS_DS", "ALL_DATASETS"]
diff --git a/twstock/collectors/history.py b/twstock/collectors/history.py
index 664edbc..1d69285 100644
--- a/twstock/collectors/history.py
+++ b/twstock/collectors/history.py
@@ -11,13 +11,14 @@ from .. import db
 from ..fetch import FetchError
 from ..health import load_snapshot, medians, missing_keys
 from ..tradingcal import HOLIDAYS, is_trading_day, load_closed, trading_days  # noqa: F401（沿用的對外名稱）
-from .daily import (ALL_DATASETS, DATASET_KEYS, DAY_KEYS, INDEX, PARSE_ERRORS, PRICES, TPEX_INDEX, collect_for_date,  # noqa: F401
-                    collect_tpex_index)
+from .daily import (ALL_DATASETS, DATASET_KEYS, DAY_KEYS, HOLDINGS_KEYS, INDEX, PARSE_ERRORS, PRICES, TPEX_INDEX,  # noqa: F401
+                    collect_for_date, collect_tpex_index)
 from .revenue import collect_monthly_revenue, revenue_month_for
 
 # 依網站節流間隔 + 回應時間的實測值（秒，每個細項）
 SECONDS_PER_KEY = {"prices.TWSE": 4, "prices.TPEx": 4, "pe.TWSE": 4, "pe.TPEx": 3.2, "insti.TWSE": 4, "insti.TPEx": 3.2,
-                   "index.TAIEX": 4, "amount": 4, "etf.TWSE": 4, "etf.TPEx": 1, "margin.TWSE": 4, "margin.TPEx": 0.5}
+                   "index.TAIEX": 4, "amount": 4, "etf.TWSE": 4, "etf.TPEx": 1, "margin.TWSE": 4, "margin.TPEx": 0.5,
+                   **{k: 3.2 for k in HOLDINGS_KEYS}}
 SHARED = {"etf.TWSE": "prices.TWSE", "etf.TPEx": "prices.TPEx"}   # 同一天也要抓行情時共用回應，不另計時
 SECONDS_PER_MONTH = 3.2
 
diff --git a/twstock/collectors/holdings.py b/twstock/collectors/holdings.py
new file mode 100644
index 0000000..5f6b76a
--- /dev/null
+++ b/twstock/collectors/holdings.py
@@ -0,0 +1,102 @@
+"""
+主動型 ETF 每日持股（第 5 輪）：統一投信 GetPCF（申購買回清單）。
+
+日期語意：參數 date 是清單「生效日」= 持股公布日的下一個交易日；回應的 TranDate 才是持股日。
+國內 ETF 當天公布當天的持股（生效日 = 持股日後第 1 個交易日）；跨境 ETF 落後 1 天（第 2 個交易日）。
+資料表以持股日為準；回應的 TranDate 與要求的持股日不同（尚未公布、連假）一律不寫入。
+"""
+from datetime import date, datetime, timedelta
+
+from .. import db
+from ..fetch import SchemaError, request
+from ..health import HOLDINGS
+from ..tradingcal import trading_days
+
+URL = "https://www.ezmoney.com.tw/ETF/Transaction/GetPCF"
+_EPOCH = datetime(1970, 1, 1) + timedelta(hours=8)      # /Date(毫秒)/ 是 UTC，換成台灣時間
+
+
+def ez_time(s: str) -> datetime:
+    """'2026-11-03T16:56:43' 或 '/Date(1761753600000)/'（歷史日期的格式）→ 台灣時間。"""
+    if s.startswith("/Date("):
+        return _EPOCH + timedelta(milliseconds=int(s[6:-2]))
+    return datetime.fromisoformat(s[:19])
+
+
+def ez_date(s: str) -> date:
+    return ez_time(s).date()
+
+
+def post_date(d: date, delay: int, closed) -> date:
+    """持股日 d 的清單生效日：d 之後第 delay + 1 個交易日。"""
+    return trading_days(d + timedelta(days=1), d + timedelta(days=40), closed)[delay]
+
+
+def parse_pcf(data: dict, d: date):
+    """GetPCF 回應 → (彙總, 明細列)；尚未公布或持股日不是 d 回傳 None。欄位不符 → SchemaError。"""
+    if not isinstance(data, dict) or not {"pcf", "asset"} <= data.keys():
+        raise SchemaError("GetPCF 回應缺少 pcf 或 asset")
+    if not data["asset"]:
+        return None                                     # 尚未公布：pcf 全是 0、asset 為空
+    pcf = {p["PCFCode"]: p for p in data["pcf"]}
+    if "NAV" not in pcf:
+        raise SchemaError("GetPCF 的 pcf 缺少 NAV")
+    if ez_date(pcf["NAV"]["TranDate"]) != d:
+        return None
+    rows, edited = [], None
+    for a in data["asset"]:
+        for x in a["Details"] or []:
+            if ez_date(x["TranDate"]) != d:
+                raise SchemaError(f"GetPCF 明細持股日 {x['TranDate']} 與彙總不同")
+            rows.append({"asset_type": a["AssetCode"], "code": str(x["DetailCode"]).strip(),
+                         "month": (x.get("MTH") or "").strip(), "name": str(x["DetailName"]).strip(),
+                         "shares": int(x["Share"]), "amount": x["Amount"], "weight": x["NavRate"],
+                         "currency": x["MoneyType"]})
+            edited = edited or x.get("EditTime")
+    stocks = [r for r in rows if r["asset_type"] == "ST"]
+    futures = [r for r in rows if r["asset_type"] == "GD"]
+    amount = lambda p: pcf[p]["Amount"] if p in pcf else None
+    summary = {"hold_date": d.isoformat(), "post_date": ez_date(pcf["NAV"]["PostDate"]).isoformat(),
+               "nav": amount("NAV"), "units": amount("OUT_UNIT"), "nav_unit": amount("P_UNIT"),
+               "n_stocks": len(stocks), "stock_weight": round(sum(r["weight"] or 0 for r in stocks), 2),
+               "futures_lots": sum(r["shares"] for r in futures), "futures_amount": sum(r["amount"] or 0 for r in futures),
+               "edited_at": ez_time(edited).isoformat() if edited else None}
+    return summary, rows
+
+
+def fetch_holdings(code: str, d: date, closed):
+    fund, delay, _ = HOLDINGS[code]
+    post = post_date(d, delay, closed)
+    data = request("POST", URL, json={"fundCode": fund, "date": f"{post.year - 1911}/{post:%m/%d}", "specificDate": True})
+    return parse_pcf(data, d)
+
+
+def merge_holdings(cursor, code: str, summary: dict, rows: list) -> bool:
+    """同一檔同一持股日整批取代（持股會出清，不能只 MERGE）。etfs 沒有這檔回傳 False。"""
+    row = cursor.execute("SELECT etf_id FROM etfs WHERE etf_code = ?", code).fetchone()
+    if not row:
+        return False
+    etf_id, d = row[0], summary["hold_date"]
+    cursor.execute("DELETE FROM etf_holdings WHERE etf_id = ? AND hold_date = ?", etf_id, d)
+    cursor.execute("""
+        INSERT INTO etf_holdings (etf_id, hold_date, asset_type, code, month, name, shares, amount, weight, currency)
+        SELECT ?, ?, asset_type, code, month, name, shares, amount, weight, currency FROM OPENJSON(?) WITH (
+            asset_type NVARCHAR(10), code NVARCHAR(20), month NVARCHAR(10), name NVARCHAR(100), shares BIGINT,
+            amount DECIMAL(20,2), weight DECIMAL(7,2), currency NVARCHAR(5))
+    """, etf_id, d, db.to_json(rows))
+    cursor.execute("""
+        MERGE etf_holding_summary AS t
+        USING OPENJSON(?) WITH (
+            hold_date DATE, post_date DATE, nav DECIMAL(20,2), units BIGINT, nav_unit DECIMAL(12,4), n_stocks INT,
+            stock_weight DECIMAL(7,2), futures_lots INT, futures_amount DECIMAL(20,2), edited_at DATETIME2(0)
+        ) AS s
+        ON t.etf_id = ? AND t.hold_date = s.hold_date
+        WHEN MATCHED THEN UPDATE SET
+            post_date = s.post_date, nav = s.nav, units = s.units, nav_unit = s.nav_unit, n_stocks = s.n_stocks,
+            stock_weight = s.stock_weight, futures_lots = s.futures_lots, futures_amount = s.futures_amount, edited_at = s.edited_at
+        WHEN NOT MATCHED THEN
+            INSERT (etf_id, hold_date, post_date, nav, units, nav_unit, n_stocks, stock_weight, futures_lots, futures_amount, edited_at)
+            VALUES (?, s.hold_date, s.post_date, s.nav, s.units, s.nav_unit, s.n_stocks, s.stock_weight, s.futures_lots,
+                    s.futures_amount, s.edited_at);
+    """, db.to_json([summary]), etf_id, etf_id)
+    return True
diff --git a/twstock/db.py b/twstock/db.py
index c47bd94..eb579f2 100644
--- a/twstock/db.py
+++ b/twstock/db.py
@@ -368,6 +368,61 @@ DDL = [
         CONSTRAINT UQ_margin_market UNIQUE (trade_date, market)
     )
     """,
+    # 主動型 ETF 持股（第 5 輪；統一投信 GetPCF）：以持股日為準，代號保留官方原文（海外股票 'BE US'、期貨 'TX'）
+    """
+    IF OBJECT_ID('etf_holdings') IS NULL
+    CREATE TABLE etf_holdings (
+        id          BIGINT IDENTITY(1,1) PRIMARY KEY,
+        etf_id      INT            NOT NULL REFERENCES etfs(etf_id),
+        hold_date   DATE           NOT NULL,     -- 持股日（回應的 TranDate）
+        asset_type  NVARCHAR(10)   NOT NULL,     -- 官方 AssetCode：ST 股票、GD 期貨
+        code        NVARCHAR(20)   NOT NULL,
+        month       NVARCHAR(10)   NOT NULL DEFAULT '',  -- 期貨契約年月（2026/11），其他為空字串
+        name        NVARCHAR(100)  NOT NULL,
+        shares      BIGINT         NOT NULL,     -- 股；期貨為口
+        amount      DECIMAL(20,2)  NULL,         -- 市值或名目本金（原幣，見 currency）
+        weight      DECIMAL(7,2)   NULL,         -- 占淨資產 %
+        currency    NVARCHAR(5)    NOT NULL,     -- NTD、USD…
+        created_at  DATETIME       NOT NULL DEFAULT GETDATE(),
+        CONSTRAINT UQ_etf_holdings UNIQUE (etf_id, hold_date, asset_type, code, month)
+    )
+    """,
+    """
+    IF OBJECT_ID('etf_holding_summary') IS NULL
+    CREATE TABLE etf_holding_summary (
+        id             INT IDENTITY(1,1) PRIMARY KEY,
+        etf_id         INT            NOT NULL REFERENCES etfs(etf_id),
+        hold_date      DATE           NOT NULL,
+        post_date      DATE           NOT NULL,  -- 清單生效日（請求參數）
+        nav            DECIMAL(20,2)  NOT NULL,  -- 基金淨資產（元）
+        units          BIGINT         NULL,      -- 已發行受益權單位
+        nav_unit       DECIMAL(12,4)  NULL,      -- 每單位淨值（元）
+        n_stocks       INT            NOT NULL,
+        stock_weight   DECIMAL(7,2)   NULL,      -- 股票權重合計 %
+        futures_lots   INT            NOT NULL,
+        futures_amount DECIMAL(20,2)  NOT NULL,  -- 期貨名目本金（元）
+        edited_at      DATETIME2(0)   NULL,      -- 投信更新時間（台灣時間）
+        created_at     DATETIME       NOT NULL DEFAULT GETDATE(),
+        CONSTRAINT UQ_etf_holding_summary UNIQUE (etf_id, hold_date)
+    )
+    """,
+    # 官方漲跌家數（第 5 輪；股票）：上市 MI_INDEX「漲跌證券數合計」、上櫃 afterTrading/highlight
+    """
+    IF OBJECT_ID('market_breadth') IS NULL
+    CREATE TABLE market_breadth (
+        id          INT IDENTITY(1,1) PRIMARY KEY,
+        trade_date  DATE          NOT NULL,
+        market      NVARCHAR(10)  NOT NULL CHECK (market IN ('TWSE','TPEx')),
+        up          INT           NOT NULL,
+        up_limit    INT           NULL,
+        down        INT           NOT NULL,
+        down_limit  INT           NULL,
+        flat        INT           NOT NULL,
+        no_trade    INT           NULL,      -- 未成交（上櫃含暫停交易）
+        created_at  DATETIME      NOT NULL DEFAULT GETDATE(),
+        CONSTRAINT UQ_market_breadth UNIQUE (trade_date, market)
+    )
+    """,
     # 索引
     "IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_daily_prices_date') "
     "CREATE INDEX IX_daily_prices_date ON daily_prices(trade_date)",
@@ -383,6 +438,8 @@ DDL = [
     "CREATE INDEX IX_margin_trades_date ON margin_trades(trade_date)",
     "IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_etf_daily_date') "
     "CREATE INDEX IX_etf_daily_date ON etf_daily(trade_date)",
+    "IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_etf_holdings_code') "
+    "CREATE INDEX IX_etf_holdings_code ON etf_holdings(code, hold_date)",
 ]
 
 
@@ -403,4 +460,4 @@ def setup_database():
     print("✅ 資料表已確認：stocks、daily_prices、monthly_revenue、stock_fundamentals、"
           "institutional_trades、futures_daily_prices、futures_institutional、industry_chains、"
           "market_index、stock_alerts、price_events、insti_amount、collect_runs、market_holidays、"
-          "etfs、etf_daily、margin_trades、etf_margin、margin_market")
+          "etfs、etf_daily、margin_trades、etf_margin、margin_market、etf_holdings、etf_holding_summary、market_breadth")
diff --git a/twstock/export.py b/twstock/export.py
index 8822436..566c7a3 100644
--- a/twstock/export.py
+++ b/twstock/export.py
@@ -2,8 +2,10 @@
 把資料庫內容匯出成靜態 JSON（site/data/），網站只讀這些檔案、不需要後端：
 
   latest.json        今日總覽：大盤統計、台指期日 K、類股/產業鏈/概念股資金流（含回放用的每日座標）、
-                     每檔股票最新指標、融資融券（margin）、ETF（etfs，與股票完全分開）
-  stocks/{代號}.json 個股：完整日線、法人買賣超、月營收、本益比、所屬產業鏈、最新融資融券
+                     每檔股票最新指標、融資融券（margin）、ETF（etfs，與股票完全分開）、
+                     已支援持股的主動 ETF（holdings）、市場寬度（breadth）
+  stocks/{代號}.json 個股：完整日線、法人買賣超、月營收、本益比、所屬產業鏈、最新融資融券、主動 ETF 持有（active）
+  etfs/{代號}.json   主動 ETF 持股：近 HOLD_DAYS 個持股日的張數與權重、最新一天的增減
 """
 import json
 import os
@@ -17,7 +19,7 @@ from . import db
 from .analysis.flow import LONG, group_flows, load_concepts, streak
 from .analysis.forecast import build_forecast, load_oi
 from .config import SITE_DATA_DIR, tw_now
-from .health import build_status
+from .health import HOLDINGS, build_status
 
 REPLAY = 20                    # 泡泡圖回放天數
 FUTURES_DAYS = 500             # 首頁台指期日 K 匯出天數
@@ -34,6 +36,8 @@ CAP_DAYS = 90
 # 升降單位（一般股票）：(價格上限, 單位)
 MARGIN_DAYS = 20               # 首頁上市股票融資增減迷你柱天數
 COVER_MIN = 99.0               # 維持率分子涵蓋的融資張數 ÷ 官方融資張數（%）低於此值不顯示
+HOLD_DAYS = 60                 # ETF 持股 JSON 的持股日數
+BREADTH_DAYS = 60              # 市場寬度走勢天數
 _TICKS = ((Decimal(10), Decimal("0.01")), (Decimal(50), Decimal("0.05")), (Decimal(100), Decimal("0.1")),
           (Decimal(500), Decimal("0.5")), (Decimal(1000), Decimal(1)), (Decimal("Infinity"), Decimal(5)))
 
@@ -332,6 +336,127 @@ def etf_block(latest, margin_rows):
     return {"dates": {m: str(d) for m, (d, _) in latest.items()}, "rows": rows}
 
 
+def _load_holdings(cur):
+    """{ETF 代號: (持股日 [舊到新], {持股日: 彙總列}, {持股日: {(類別, 代號): (名稱, 股數, 權重)}})}，各取最近 HOLD_DAYS 個持股日。"""
+    summary = defaultdict(dict)
+    for code, d, *v in cur.execute("""
+        SELECT e.etf_code, s.hold_date, s.nav, s.nav_unit, s.n_stocks, s.stock_weight, s.futures_lots, s.futures_amount
+        FROM etf_holding_summary s JOIN etfs e ON e.etf_id = s.etf_id ORDER BY s.hold_date"""):
+        summary[code][d] = v
+    if not summary:
+        return {}
+    since = min(sorted(v)[-HOLD_DAYS:][0] for v in summary.values())
+    held = defaultdict(lambda: defaultdict(dict))
+    for code, d, kind, c, name, shares, w in cur.execute("""
+        SELECT e.etf_code, h.hold_date, h.asset_type, h.code, h.name, h.shares, h.weight
+        FROM etf_holdings h JOIN etfs e ON e.etf_id = h.etf_id WHERE h.hold_date >= ?""", since):
+        held[code][d][(kind, c)] = (name, shares, w)
+    return {code: (sorted(v)[-HOLD_DAYS:], v, held[code]) for code, v in summary.items() if code in HOLDINGS}
+
+
+def holding_table(dates, held, tw):
+    """
+    ETF 持股頁的列（最新持股日）。dates：持股日（舊到新）；held：{持股日: {(類別, 代號): (名稱, 股數, 權重)}}；
+    tw：台股代號集合（張 = 股 ÷ 1000、可點進個股頁；其他如海外股票單位為股）。
+    回傳 (rows, out)：rows 每列 {c, n, tw, s: [各持股日數量，未持有 null], w: [權重], l, pw, d1, w1, d5, new}；
+    out：前一持股日有、最新一天沒有（出清）。1 日、5 日以「前 1、前 5 個有資料的持股日」為基準。
+    """
+    last, prev = dates[-1], dates[-2] if len(dates) > 1 else None
+    d5 = dates[-6] if len(dates) > 5 else None
+    names = {}
+    for d in dates:
+        for (kind, c), (name, _, _) in held[d].items():
+            if kind == "ST":
+                names[c] = name
+    qty = lambda c, d: None if d is None or ("ST", c) not in held[d] else (
+        round(held[d][("ST", c)][1] / 1000) if c in tw else held[d][("ST", c)][1])
+    wt = lambda c, d: None if d is None or ("ST", c) not in held[d] else _f(held[d][("ST", c)][2])
+    rows, out = [], []
+    for c, name in names.items():
+        now, before = qty(c, last), qty(c, prev)
+        if now is None:
+            if before is not None:
+                out.append({"c": c, "n": name, "tw": int(c in tw), "l": before, "pw": wt(c, prev)})
+            continue
+        r = {"c": c, "n": name, "tw": int(c in tw), "s": [qty(c, d) for d in dates], "w": [wt(c, d) for d in dates],
+             "l": now, "pw": wt(c, last), "d1": now - (before or 0) if prev else None,
+             "w1": _f(wt(c, last) - (wt(c, prev) or 0)) if prev else None,
+             "d5": now - (qty(c, d5) or 0) if d5 else None}
+        if prev and before is None:
+            r["new"] = 1
+        rows.append(r)
+    rows.sort(key=lambda r: -(r["pw"] or 0))
+    return rows, out
+
+
+def holding_export(code, dates, summary, held, tw, name, market):
+    """etfs/{代號}.json。金額單位：億元；nu 每單位淨值（元）；sw 股票權重合計（%）；fl 期貨口數。"""
+    nav, nu, n, sw, fl, fa = summary[dates[-1]]
+    rows, out = holding_table(dates, held, tw)
+    fund, delay, _ = HOLDINGS[code]
+    return {"code": code, "n": name, "m": market, "fund": fund, "delay": delay, "dates": [str(d) for d in dates],
+            "sum": {"d": str(dates[-1]), "nav": _f(float(nav) / YI), "nu": _f(nu), "n": n, "sw": _f(sw),
+                    "fl": fl, "fa": _f(float(fa) / YI)},
+            "rows": rows, "out": out}
+
+
+def stock_active(holdings, tw):
+    """{股票代號: [主動 ETF 持有]}：各 ETF 最新持股日有持有的台股；張、權重（%）、1 日／5 日張數增減。"""
+    out = defaultdict(list)
+    for code, (dates, _, held) in sorted(holdings.items()):
+        for r in holding_table(dates, held, tw)[0]:
+            if r["tw"]:
+                out[r["c"]].append({"e": code, "d": str(dates[-1]), "l": r["l"], "w": r["pw"], "d1": r["d1"], "d5": r["d5"],
+                                    **({"new": 1} if r.get("new") else {})})
+    return out
+
+
+def breadth_calc(series, days, turnover):
+    """
+    自算市場寬度。series：{市場: [每檔股票 {日期: 還原收盤}]}（只含股票）；days：交易日（舊到新，最後 BREADTH_DAYS 天輸出）；
+    turnover：{市場: {日期: 成交額（億）}}。分母 = 當天有收盤、且之前（含當天）至少有 20／60 個收盤的股票。
+    回傳 {市場: {d, ma20, ma60（%）, n20, n60（分母）, hi, lo（20 日新高／新低家數）, vr（成交額 ÷ 前 20 日平均）, s20（MA20 比例走勢）, from}}。
+    20 日新高／新低：收盤高於（低於）前 20 個收盤的最高（最低）。
+    """
+    out_days = days[-BREADTH_DAYS:]
+    pos = {d: i for i, d in enumerate(out_days)}
+    out = {}
+    for m, stocks in series.items():
+        cnt = {k: [0] * len(out_days) for k in ("a20", "n20", "a60", "n60", "hi", "lo")}
+        for closes in stocks:
+            ds = sorted(closes)
+            px = [closes[d] for d in ds]
+            acc = [0.0]
+            for x in px:
+                acc.append(acc[-1] + x)
+            for j, d in enumerate(ds):
+                i = pos.get(d)
+                if i is None:
+                    continue
+                for n, a, k in ((20, "a20", "n20"), (60, "a60", "n60")):
+                    if j >= n - 1:
+                        cnt[k][i] += 1
+                        cnt[a][i] += px[j] > (acc[j + 1] - acc[j + 1 - n]) / n
+                if j >= 20:
+                    window = px[j - 20:j]
+                    cnt["hi"][i] += px[j] > max(window)
+                    cnt["lo"][i] += px[j] < min(window)
+        pct = lambda a, n: round(a / n * 100, 1) if n else None
+        tv = [turnover[m].get(d) for d in days]
+        prior = tv[-21:-1]
+        out[m] = {"d": str(out_days[-1]), "ma20": pct(cnt["a20"][-1], cnt["n20"][-1]), "ma60": pct(cnt["a60"][-1], cnt["n60"][-1]),
+                  "n20": cnt["n20"][-1], "n60": cnt["n60"][-1], "hi": cnt["hi"][-1], "lo": cnt["lo"][-1],
+                  "vr": round(tv[-1] / (sum(prior) / len(prior)), 2) if tv[-1] and len(prior) == 20 and all(prior) else None,
+                  "s20": [pct(a, n) for a, n in zip(cnt["a20"], cnt["n20"])], "from": str(out_days[0])}
+    return out
+
+
+def _load_breadth(cur, d):
+    """官方漲跌家數：{市場: {up, ul（漲停）, dn, dl（跌停）, fl（平盤）, nt（未成交）}}，只取資料日當天。"""
+    return {m: dict(zip(("up", "ul", "dn", "dl", "fl", "nt"), v)) for m, *v in cur.execute(
+        "SELECT market, up, up_limit, down, down_limit, flat, no_trade FROM market_breadth WHERE trade_date = ?", d)}
+
+
 def _load_chains(cur):
     """回傳 ({產業鏈: [代號...]}, {代號: [[產業鏈, 區段, [細項...]], ...]})。"""
     groups, tags = defaultdict(list), defaultdict(dict)
@@ -470,6 +595,11 @@ def export_all() -> float:
     mdates, mofficial, mstocks, metfs, mper = _load_margin(cur)
     first_m = min((ds[0] for ds in mdates.values()), default=latest_date)
     etf_px, etf_latest = _load_etfs(cur, first_m - timedelta(days=60))
+    holdings = _load_holdings(cur)
+    etf_names = {code: (name, m) for code, name, m in cur.execute("SELECT etf_code, etf_name, market_type FROM etfs")}
+    official_breadth = _load_breadth(cur, latest_date)
+    # 寬度輸出 BREADTH_DAYS 天，前面多 60 天給 MA60
+    b_days = [r[0] for r in cur.execute(f"SELECT DISTINCT TOP {BREADTH_DAYS + 60} trade_date FROM daily_prices ORDER BY trade_date DESC")][::-1]
     status = build_status(cur, latest_date, now)
     conn.close()
     mlast = {m: ds[-1] for m, ds in mdates.items()}
@@ -481,8 +611,16 @@ def export_all() -> float:
         for c in codes:
             concept_of[c].append(name)
 
+    # ── ETF 持股檔（台股 = stocks 表的代號）──
+    tw = set(stocks)
+    for code, (hdates, summary, held) in holdings.items():
+        _write(SITE_DATA_DIR / "etfs" / f"{code}.json", holding_export(code, hdates, summary, held, tw, *etf_names[code]))
+    active = stock_active(holdings, tw)
+
     # ── 個股檔 + 最新指標 ──
     window = set(dates)
+    b_from = b_days[0]
+    b_series, b_turnover = defaultdict(list), defaultdict(lambda: defaultdict(float))
     daily = {}            # 板塊計算用：{代號: {日期: {net, turnover, pct}}}
     snapshot = {}
     market = {m: {"up": 0, "down": 0, "flat": 0, "turnover": 0.0} for m in ("TWSE", "TPEx")}
@@ -524,7 +662,13 @@ def export_all() -> float:
             # 該市場有融資融券資料時才有 margin；null = 不在信用交易清單（無信用交易）
             **({"margin": stock_margin(mper.get(code, {}), mlast[info["market"]], m5[info["market"]])}
                if info["market"] in mlast else {}),
+            **({"active": active[code]} if code in active else {}),
         })
+        # 市場寬度：還原收盤（無成交日不列入）、成交額
+        b_series[info["market"]].append({d_[i]: float(c[i]) * af[i] for i in range(len(d_)) if d_[i] >= b_from and c[i] is not None})
+        for i in range(len(d_)):
+            if d_[i] >= b_from:
+                b_turnover[info["market"]][d_[i]] += (tv[i] or 0) / YI
 
         # 板塊計算用的近 WINDOW 天
         net_value, f_value, t_value, d_value = [], [], [], []
@@ -624,6 +768,9 @@ def export_all() -> float:
         "forecast": forecast,
         "margin": margin,
         "etfs": etf_block(etf_latest, etf_margin_rows),
+        "holdings": {code: {"d": str(hd[-1]), "n": etf_names[code][0]} for code, (hd, _, _) in holdings.items()},
+        # o：官方家數（資料日當天沒有為 null）；其餘為自算
+        "breadth": {m: {"o": official_breadth.get(m), **b} for m, b in breadth_calc(b_series, b_days, b_turnover).items()},
         "groups": {
             "industry": group_flows(industries, daily, dates, REPLAY),
             "chain": group_flows(chains, daily, dates, REPLAY),
diff --git a/twstock/fetch.py b/twstock/fetch.py
index e69774b..6c9d706 100644
--- a/twstock/fetch.py
+++ b/twstock/fetch.py
@@ -69,6 +69,7 @@ MIN_INTERVAL = {
     "mopsov.twse.com.tw":  3.0,
     "www.taifex.com.tw":   3.0,
     "ic.tpex.org.tw":      2.0,
+    "www.ezmoney.com.tw":  3.0,   # 統一投信（主動型 ETF 持股）
 }
 DEFAULT_INTERVAL = 3.0
 RETRY_BACKOFF = (30, 60, 120)   # 失敗後依序等待秒數，用完仍失敗就放棄
diff --git a/twstock/health.py b/twstock/health.py
index b00ae35..014dcb0 100644
--- a/twstock/health.py
+++ b/twstock/health.py
@@ -2,7 +2,8 @@
 資料完整性：check、collect --catch-up、history、export 的 status 共用同一張資料集表與同一套判斷。
 
 一個資料集在某交易日「齊全」= 筆數 ≥ max(下限, 近 20 日中位數 × 80%)，且本益比類的三個欄位填充率都 ≥ 50%。
-不齊全時：當天 22:00 前算「尚未公布」，之後算「異常」。
+不齊全時：公布日 22:00 前算「尚未公布」，之後算「異常」。公布日通常是當天；跨境 ETF 持股落後 1 個交易日（delay）。
+since 之前的日期不算缺（ETF 上市前、開始收集前）。
 """
 import json
 import statistics
@@ -22,10 +23,16 @@ COUNT_RATIO, FILL_MIN, MEDIAN_DAYS = 0.8, 0.5, 20
 OK, PENDING, ABNORMAL = "ok", "pending", "abnormal"
 
 Row = namedtuple("Row", "n pe pb dy", defaults=(0, 0, 0, 0))
-Spec = namedtuple("Spec", "key label min_rows fills")
+Spec = namedtuple("Spec", "key label min_rows fills since delay", defaults=(None, 0))
 Item = namedtuple("Item", "key label date status n reason")
 FILLS = (("pe", "本益比"), ("pb", "淨值比"), ("dy", "殖利率"))
 
+# 統一投信主動型 ETF（第 5 輪）：代號 → (基金代碼, 持股公布落後的交易日數, 上市日)
+# 上市日 = etf_daily 最早一筆（2025-10-30 之前上市的填 None）；跨境 ETF 的持股日是前一個交易日
+HOLDINGS = {"00981A": ("49YTW", 0, None), "00403A": ("63YTW", 0, date(2026, 5, 12)),
+            "00411A": ("64YTW", 1, date(2026, 8, 26)), "00988A": ("61YTW", 1, date(2025, 11, 5))}
+BREADTH_FROM = date(2026, 11, 3)        # 官方漲跌家數不補歷史，從這天開始收集
+
 SPECS = (
     Spec("prices.TWSE", "上市行情", 800, False), Spec("prices.TPEx", "上櫃行情", 650, False),
     Spec("pe.TWSE", "上市本益比", 800, True), Spec("pe.TPEx", "上櫃本益比", 650, True),
@@ -35,7 +42,8 @@ SPECS = (
     Spec("futures", "台指期", 1, False), Spec("futures_oi", "期貨法人", 9, False),
     Spec("etf.TWSE", "上市ETF", 150, False), Spec("etf.TPEx", "上櫃ETF", 80, False),
     Spec("margin.TWSE", "上市融資融券", 800, False), Spec("margin.TPEx", "上櫃融資融券", 550, False),
-)
+    Spec("breadth.TWSE", "上市漲跌家數", 1, False, BREADTH_FROM), Spec("breadth.TPEx", "上櫃漲跌家數", 1, False, BREADTH_FROM),
+) + tuple(Spec(f"holdings.{c}", f"{c}持股", 1, False, since, delay) for c, (_, delay, since) in HOLDINGS.items())
 SPEC = {s.key: s for s in SPECS}
 
 _MARKET_SQL = {
@@ -61,6 +69,15 @@ def load_snapshot(cur, start: date, end: date) -> dict:
     for d, market, n in cur.execute("SELECT x.trade_date, e.market_type, COUNT(*) FROM etf_daily x JOIN etfs e ON e.etf_id = x.etf_id "
                                     "WHERE x.trade_date BETWEEN ? AND ? GROUP BY x.trade_date, e.market_type", start, end).fetchall():
         snap[f"etf.{market}"][d] = Row(n)
+    # 持股筆數 = 股票檔數（期貨不算）
+    for d, code, n in cur.execute("SELECT h.hold_date, e.etf_code, COUNT(*) FROM etf_holdings h JOIN etfs e ON e.etf_id = h.etf_id "
+                                  "WHERE h.asset_type = 'ST' AND h.hold_date BETWEEN ? AND ? GROUP BY h.hold_date, e.etf_code",
+                                  start, end).fetchall():
+        if f"holdings.{code}" in snap:
+            snap[f"holdings.{code}"][d] = Row(n)
+    for d, market, n in cur.execute("SELECT trade_date, market, COUNT(*) FROM market_breadth WHERE trade_date BETWEEN ? AND ? "
+                                    "GROUP BY trade_date, market", start, end).fetchall():
+        snap[f"breadth.{market}"][d] = Row(n)
     for key, sql in (("amount", "SELECT trade_date, COUNT(*) FROM insti_amount WHERE trade_date BETWEEN ? AND ? GROUP BY trade_date"),
                      # 只看日盤：夜盤的日期是歸屬日，不代表該日資料已齊
                      ("futures", "SELECT trade_date, COUNT(*) FROM futures_daily_prices WHERE commodity_id = 'TX' AND session = 'DAY' "
@@ -95,8 +112,15 @@ def assess(spec: Spec, row: Row, median: float):
     return None
 
 
-def missing_keys(d: date, keys, snap: dict, med: dict) -> tuple:
-    return tuple(k for k in keys if assess(SPEC[k], snap[k].get(d, Row()), med[k]))
+def is_due(spec: Spec, d: date, days=None) -> bool:
+    """這天該不該有資料：since 之前不算；delay > 0 要等 days（交易日，舊到新）裡再過 delay 天才公布。days=None 不看 delay。"""
+    if spec.since and d < spec.since:
+        return False
+    return not spec.delay or days is None or (d in days and days.index(d) + spec.delay < len(days))
+
+
+def missing_keys(d: date, keys, snap: dict, med: dict, days=None) -> tuple:
+    return tuple(k for k in keys if is_due(SPEC[k], d, days) and assess(SPEC[k], snap[k].get(d, Row()), med[k]))
 
 
 def due_days(now: datetime, n: int, closed: set) -> list:
@@ -110,7 +134,9 @@ def evaluate(days, snap: dict, now: datetime, errors=None) -> list:
     """每個資料集 × 每個交易日的狀態。errors = {(鍵, 日期) 或 鍵: 例外}：抓取失敗一律算異常，不論時間。"""
     errors, med, items = errors or {}, medians(snap), []
     for spec in SPECS:
-        for d in days:
+        for i, d in enumerate(days):
+            if not is_due(spec, d, days):
+                continue
             row = snap[spec.key].get(d, Row())
             bad = assess(spec, row, med[spec.key])
             # (鍵, 日期)：這天抓取失敗；鍵：範圍查詢失敗（期貨、櫃買指數），只影響還缺資料的日期
@@ -119,7 +145,7 @@ def evaluate(days, snap: dict, now: datetime, errors=None) -> list:
                 items.append(Item(spec.key, spec.label, d, ABNORMAL, row.n, ("error", str(err))))
             elif bad is None:
                 items.append(Item(spec.key, spec.label, d, OK, row.n, None))
-            elif d == now.date() and now.time() < DEADLINE:
+            elif days[i + spec.delay] == now.date() and now.time() < DEADLINE:    # 公布日當天
                 items.append(Item(spec.key, spec.label, d, PENDING, row.n, bad))
             else:
                 items.append(Item(spec.key, spec.label, d, ABNORMAL, row.n, bad))
@@ -136,12 +162,16 @@ def _day_list(days) -> str:
 
 
 def all_missing_days(items) -> list:
-    """所有資料集都是「異常且 0 筆」的交易日（整天沒有收集）；休市日本來就不在 items 裡。"""
+    """
+    當天公布的資料集全部「異常且 0 筆」的交易日（整天沒有收集）；休市日本來就不在 items 裡。
+    落後公布的持股（delay）是隔天才收，不列入判斷。
+    """
     by_day = {}
     for i in items:
-        by_day.setdefault(i.date, []).append(i)
+        if not SPEC[i.key].delay:
+            by_day.setdefault(i.date, []).append(i)
     return sorted(d for d, its in by_day.items()
-                  if len(its) == len(SPECS) and all(i.status == ABNORMAL and not i.n for i in its))
+                  if len(its) == sum(is_due(s, d) for s in SPECS if not s.delay) and all(i.status == ABNORMAL and not i.n for i in its))
 
 
 def problem_lines(items, last_run=None) -> list:
@@ -336,12 +366,19 @@ def collected_at(cur, state: dict) -> tuple:
     return (t.isoformat(timespec="seconds") + "+08:00", "db") if t else (None, "db")
 
 
-def dataset_status(snap: dict, data_date: date, now: datetime) -> list:
-    """以「資料日」為基準判斷各資料集（整站落後由橫幅處理）；m 只在異常時有。"""
+def dataset_status(snap: dict, data_date: date, now: datetime, closed=None) -> list:
+    """
+    以「資料日」為基準判斷各資料集（整站落後由橫幅處理）；m 只在異常時有。
+    落後公布的持股（delay）看資料日往前 delay 個交易日（closed = 休市日；未提供時只排除週末與內建休市表）。
+    """
     med, out = medians(snap), []
+    days = trading_days(data_date - timedelta(days=45), data_date, closed)
     for spec in SPECS:
+        target = days[-1 - spec.delay] if spec.delay else data_date
+        if not is_due(spec, target):
+            continue
         rows = snap[spec.key]
-        bad = assess(spec, rows.get(data_date, Row()), med[spec.key])
+        bad = assess(spec, rows.get(target, Row()), med[spec.key])
         good = [d for d in sorted(rows) if not assess(spec, rows[d], med[spec.key])]
         last = good[-1] if good else None
         item = {"k": spec.key, "n": spec.label, "d": str(last) if last else None, "s": OK}
@@ -349,7 +386,7 @@ def dataset_status(snap: dict, data_date: date, now: datetime) -> list:
             item["s"] = PENDING if data_date == now.date() and now.time() < DEADLINE else ABNORMAL
         if item["s"] == ABNORMAL:
             if bad[0].startswith("fill"):
-                item["m"] = f"{spec.label} {data_date:%m/%d} {bad[1].split('（')[0]}"
+                item["m"] = f"{spec.label} {target:%m/%d} {bad[1].split('（')[0]}"
             else:
                 item["m"] = f"{spec.label}停在 {last:%m/%d}" if last else f"{spec.label}近期資料不足"
         out.append(item)
@@ -366,5 +403,5 @@ def build_status(cur, data_date: date, now: datetime) -> dict:
     at, src = collected_at(cur, state)
     snap = load_snapshot(cur, data_date - timedelta(days=45), data_date)
     return {"collected_at": at, "collected_src": src, "exported_at": now.isoformat(timespec="seconds"),
-            "datasets": dataset_status(snap, data_date, now),
+            "datasets": dataset_status(snap, data_date, now, closed),
             "closed": site_closed(closed, data_date)}
```

## 附錄 D：`tests/test_iter05.py`（完整）

```python
"""
第 05 輪純邏輯測試（不連網、不連資料庫、不跳通知、不安裝排程）：
E2-1 統一投信主動 ETF 持股（日期語意、解析、資料集 since／delay、--catch-up 與 history 流程）；
E2-4 持股頁與個股卡的匯出；A3＋A8 官方漲跌家數與自算寬度。假的官方網站與資料庫沿用 test_iter03 的 World。

  python3 tests/test_iter05.py      （也相容 pytest）
"""
import argparse
import contextlib
import copy
import io
import json
import shutil
import subprocess
import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_iter03 as t3  # noqa: E402
from twstock import __main__ as cli  # noqa: E402
from twstock import db, export, fetch, health, tradingcal  # noqa: E402
from twstock.collectors import daily, history, holdings  # noqa: E402
from twstock.fetch import SchemaError  # noqa: E402
from twstock.health import Row  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
D, T, World, env, run_world, CLOSED = t3.D, t3.T, t3.World, t3.env, t3.run_world, t3.CLOSED
HKEYS = [f"holdings.{c}" for c in health.HOLDINGS]

# ─── 實際回應的片段（2026-11-03 SA 經 fetch.request(isolated=True) 取得，只刪減列數、未改值）────
PCF_1103 = {   # 00981A，date=115/11/04 → 持股日 11/03（當天的格式是 ISO 字串）
    "pcf": [{"PCFCode": "NAV", "TranDate": "2026-11-03T00:00:00", "PostDate": "2026-11-04T00:00:00", "Amount": 254413288263.0},
            {"PCFCode": "OUT_UNIT", "TranDate": "2026-11-03T00:00:00", "PostDate": "2026-11-04T00:00:00", "Amount": 10231209000.0},
            {"PCFCode": "P_UNIT", "TranDate": "2026-11-03T00:00:00", "PostDate": "2026-11-04T00:00:00", "Amount": 24.87}],
    "fund": {"sFundCode": "49YTW"},
    "asset": [{"AssetCode": "GD", "AssetName": "期貨(名目本金)", "Details": [
        {"TranDate": "2026-11-03T00:00:00", "AssetCode": "GD", "DetailCode": "TX", "DetailName": "台指期貨", "Share": 679.0, "Amount": 5887337400.0,
         "NavRate": 2.31, "MoneyType": "NTD", "MTH": "2026/11", "EditTime": "2026-11-03T16:56:43"}]},
              {"AssetCode": "ST", "AssetName": "股票", "Details": [
        {"TranDate": "2026-11-03T00:00:00", "AssetCode": "ST", "DetailCode": "2330", "DetailName": "台積電", "Share": 14464000.0,
         "Amount": 33194880000.0, "NavRate": 13.05, "MoneyType": "NTD", "MTH": "", "EditTime": "2026-11-03T16:56:43"},
        {"TranDate": "2026-11-03T00:00:00", "AssetCode": "ST", "DetailCode": "1802", "DetailName": "台玻", "Share": 8479000.0,
         "Amount": 574028300.0, "NavRate": 0.23, "MoneyType": "NTD", "MTH": "", "EditTime": "2026-11-03T16:56:43"},
        {"TranDate": "2026-11-03T00:00:00", "AssetCode": "ST", "DetailCode": "3376", "DetailName": "新日興", "Share": 1045000.0,
         "Amount": 132715000.0, "NavRate": 0.05, "MoneyType": "NTD", "MTH": "", "EditTime": "2026-11-03T16:56:43"}]}]}
PCF_20251030 = {   # 00981A，date=114/10/31 → 持股日 2025-10-30（歷史日期是 /Date(毫秒)/）
    "pcf": [{"PCFCode": "NAV", "TranDate": "/Date(1761753600000)/", "PostDate": "/Date(1761840000000)/", "Amount": 23452246994.0},
            {"PCFCode": "P_UNIT", "TranDate": "/Date(1761753600000)/", "PostDate": "/Date(1761840000000)/", "Amount": 15.42}],
    "fund": {}, "asset": [{"AssetCode": "GD", "Details": []}, {"AssetCode": "ST", "Details": [
        {"TranDate": "/Date(1761753600000)/", "AssetCode": "ST", "DetailCode": "2330", "DetailName": "台積電", "Share": 1412000,
         "Amount": 2125060000.0, "NavRate": 9.06, "MoneyType": "NTD", "MTH": "", "EditTime": "/Date(1761810315000)/"}]}]}
PCF_988 = {   # 00988A（跨境），date=115/11/04 → 持股日 11/02；海外股票代號保留原文、原幣
    "pcf": [{"PCFCode": "NAV", "TranDate": "/Date(1793548800000)/", "PostDate": "/Date(1793721600000)/", "Amount": 41817844467.0}],
    "fund": {}, "asset": [{"AssetCode": "ST", "Details": [
        {"TranDate": "/Date(1793548800000)/", "AssetCode": "ST", "DetailCode": "BE US", "DetailName": "BLOOM ENERGY CORP- A", "Share": 450000,
         "Amount": 88312500.0, "NavRate": 6.89, "MoneyType": "USD", "MTH": "", "EditTime": "/Date(1793694630000)/"},
        {"TranDate": "/Date(1793548800000)/", "AssetCode": "ST", "DetailCode": "3037", "DetailName": "欣興", "Share": 2600000,
         "Amount": 2592200000.0, "NavRate": 6.2, "MoneyType": "NTD", "MTH": "", "EditTime": "/Date(1793694630000)/"}]}]}
PCF_EMPTY = {"pcf": [{"PCFCode": "NAV", "TranDate": "/Date(-62135596800000)/", "PostDate": "/Date(-62135596800000)/", "Amount": 0}],
             "fund": {}, "asset": [], "assetDetailSchema": []}       # 尚未公布（date=115/11/05）與週六（115/10/31）
MI_BREADTH = {"title": "漲跌證券數合計", "fields": ["類型", "整體市場", "股票"],           # MI_INDEX 2026-11-03
              "data": [["上漲(漲停)", "1,783(6)", "58(2)"], ["下跌(跌停)", "13,979(312)", "1,000(33)"], ["持平", "341", "22"],
                       ["未成交", "20,831", "6"], ["無比價", "3,674", "2"]]}
TPEX_HL = [{"title": "上櫃股票當日彙總資訊", "date": "115/11/03",                       # afterTrading/highlight 2026-11-03
            "fields": ["上櫃家數", "總資本額(佰萬元)", "總市值(佰萬元)", "本日總成交值(佰萬元)", "本日總成交股數(張數)", "收市指數", "指數漲跌",
                       "上漲家數", "漲停家數", "下跌家數", "跌停家數", "平盤家數", "未成交(含暫停交易)家數"],
            "data": [["897", "846,779", "9,661,260", "197,539", "1,044,717", "345.52", "-23.72", "59", "11", "782", "41", "32", "24"]]}]


def _pcf_hits(w, fund=None):
    return [f for p, f in w.requests if "GetPCF" in p and (fund is None or f["fundCode"] == fund)]


def _hold(form):
    """請求的生效日（民國）→ 持股日。"""
    y, m, dd = form["date"].split("/")
    post = date(int(y) + 1911, int(m), int(dd))
    delay = next(v[1] for v in health.HOLDINGS.values() if v[0] == form["fundCode"])
    return tradingcal.trading_days(post - timedelta(days=30), post - timedelta(days=1), CLOSED)[-1 - delay]


# ─── E2-1：日期語意與解析 ─────────────────────────────────
def test_e2_dates():
    assert holdings.ez_date("2026-11-03T00:00:00") == D(11, 3)
    assert holdings.ez_date("/Date(1761753600000)/") == date(2025, 10, 30)          # UTC 10/29 16:00 = 台灣 10/30
    assert holdings.ez_date("/Date(1793548800000)/") == D(11, 2)
    assert holdings.ez_time("/Date(1761810315000)/").isoformat() == "2025-10-30T15:45:15"
    # 生效日 = 持股日之後第 delay + 1 個交易日：週五 → 週一；跨境再多一天；跳過休市日
    assert holdings.post_date(D(10, 30), 0, CLOSED) == D(11, 2) and holdings.post_date(D(10, 30), 1, CLOSED) == D(11, 3)
    assert holdings.post_date(D(11, 3), 0, CLOSED) == D(11, 4) and holdings.post_date(D(11, 2), 1, CLOSED) == D(11, 4)
    assert holdings.post_date(D(12, 24), 0, CLOSED) == D(12, 28)                    # 12/25 休市（行憲紀念日）


def test_e2_parse_real():
    s, rows = holdings.parse_pcf(PCF_1103, D(11, 3))
    assert s["hold_date"] == "2026-11-03" and s["post_date"] == "2026-11-04" and s["nav"] == 254413288263.0
    assert s["units"] == 10231209000.0 and s["nav_unit"] == 24.87 and s["edited_at"] == "2026-11-03T16:56:43"
    assert s["n_stocks"] == 3 and s["stock_weight"] == 13.33 and s["futures_lots"] == 679 and s["futures_amount"] == 5887337400.0
    tx = [r for r in rows if r["asset_type"] == "GD"][0]
    assert tx == {"asset_type": "GD", "code": "TX", "month": "2026/11", "name": "台指期貨", "shares": 679, "amount": 5887337400.0,
                  "weight": 2.31, "currency": "NTD"}
    tsmc = [r for r in rows if r["code"] == "2330"][0]
    assert tsmc["shares"] == 14464000 and tsmc["amount"] == 33194880000.0 and tsmc["weight"] == 13.05 and tsmc["month"] == ""
    # #5 歷史日期 /Date(毫秒)/
    s, rows = holdings.parse_pcf(PCF_20251030, date(2025, 10, 30))
    assert s["hold_date"] == "2025-10-30" and s["post_date"] == "2025-10-31" and s["futures_lots"] == 0 and rows[0]["shares"] == 1412000
    assert s["units"] is None                                   # 片段沒有 OUT_UNIT：欄位可缺，不是欄位不符
    # 海外持股：代號原文、原幣
    _, rows = holdings.parse_pcf(PCF_988, D(11, 2))
    assert [(r["code"], r["currency"]) for r in rows] == [("BE US", "USD"), ("3037", "NTD")]


def test_e2_parse_not_published_and_schema():
    assert holdings.parse_pcf(PCF_EMPTY, D(11, 4)) is None
    assert holdings.parse_pcf(PCF_1103, D(11, 4)) is None       # 回應是前一持股日：不寫入
    assert holdings.parse_pcf(PCF_1103, D(11, 2)) is None
    for bad in ({"pcf": []}, {"asset": []}, [], {"pcf": [{"PCFCode": "X", "TranDate": "2026-11-03T00:00:00"}], "asset": [{"Details": []}]}):
        try:
            holdings.parse_pcf(bad, D(11, 3))
            raise AssertionError(bad)
        except SchemaError:
            pass
    broken = copy.deepcopy(PCF_1103)
    del broken["asset"][1]["Details"][0]["DetailCode"]
    try:
        holdings.parse_pcf(broken, D(11, 3))
        raise AssertionError("DetailCode")
    except daily.PARSE_ERRORS:
        pass
    mixed = copy.deepcopy(PCF_1103)
    mixed["asset"][1]["Details"][0]["TranDate"] = "2026-11-02T00:00:00"
    try:
        holdings.parse_pcf(mixed, D(11, 3))
        raise AssertionError("mixed")
    except SchemaError:
        pass


def test_e2_real_file():
    """PG 補抓時保存的完整原始回應（logs/ 不在版本控制；沒有就略過）。"""
    for name, d, n, want in (("20261103", D(11, 3), 51, 94.43), ("20251030", date(2025, 10, 30), 50, None)):
        f = ROOT / f"logs/iter05_raw_GetPCF_00981A_{name}.json"
        if not f.exists():
            print(f"  （略過：{f.name} 不存在）")
            continue
        s, rows = holdings.parse_pcf(json.loads(f.read_text(encoding="utf-8")), d)
        assert s["n_stocks"] == n and (want is None or s["stock_weight"] == want)


# ─── E2-1：資料集（since、delay）──────────────────────────
def test_e2_specs():
    keys = [s.key for s in health.SPECS]
    assert keys[-6:] == ["breadth.TWSE", "breadth.TPEx", *HKEYS]
    assert daily.DAY_KEYS[-6:] == ("breadth.TWSE", "breadth.TPEx", *HKEYS)
    assert set(daily.DAY_KEYS) | {"index.TPEX", "futures", "futures_oi"} == set(keys)
    assert daily.DATASET_KEYS["holdings"] == tuple(HKEYS) and "holdings" not in daily.ALL_DATASETS     # 只有 --only holdings 才補
    assert health.SPEC["holdings.00411A"].since == D(8, 26) and health.SPEC["holdings.00411A"].delay == 1
    assert health.SPEC["holdings.00981A"].since is None and health.SPEC["holdings.00981A"].delay == 0
    assert fetch.MIN_INTERVAL["www.ezmoney.com.tw"] == 3.0
    assert set(history.SECONDS_PER_KEY) >= set(HKEYS)
    src = (ROOT / "twstock/db.py").read_text(encoding="utf-8")
    assert all(f"IF OBJECT_ID('{t}') IS NULL" in src for t in ("etf_holdings", "etf_holding_summary", "market_breadth"))


def test_e2_due_and_status():
    days = tradingcal.trading_days(D(10, 1), D(11, 4), CLOSED)
    snap = t3._full_snapshot(days, skip={("holdings.00411A", D(11, 3)), ("holdings.00981A", D(11, 4)), ("holdings.00411A", D(11, 4))})
    pick = lambda items, k, d: [i.status for i in items if i.key == k and i.date == d]
    items = health.evaluate(days, snap, T(11, 4, 18))
    assert pick(items, "holdings.00981A", D(11, 4)) == [health.PENDING]
    assert pick(items, "holdings.00411A", D(11, 3)) == [health.PENDING]          # 11/04 才公布 11/03 的持股
    assert pick(items, "holdings.00411A", D(11, 4)) == []                        # 11/05 才公布，還不該有
    items = health.evaluate(days, snap, T(11, 4, 22, 0))
    assert pick(items, "holdings.00411A", D(11, 3)) == [health.ABNORMAL] and pick(items, "holdings.00981A", D(11, 4)) == [health.ABNORMAL]
    # since：上市日之前不算缺；漲跌家數 11/03 起
    days = tradingcal.trading_days(D(8, 20), D(9, 1), CLOSED)
    items = health.evaluate(days, {k: {} for k in health.SPEC}, T(9, 1, 23))
    assert min(i.date for i in items if i.key == "holdings.00411A") == D(8, 26)
    assert not [i for i in items if i.key.startswith("breadth.")]
    # missing_keys：給 days 才看 delay（catch-up）；history 不給
    med = health.medians(snap)
    d4 = tradingcal.trading_days(D(10, 1), D(11, 4), CLOSED)
    assert health.missing_keys(D(11, 4), ("holdings.00411A",), t3._full_snapshot([]), med, d4) == ()
    assert health.missing_keys(D(11, 4), ("holdings.00411A",), t3._full_snapshot([]), med) == ("holdings.00411A",)
    assert health.missing_keys(D(8, 25), ("holdings.00411A",), {"holdings.00411A": {}}, {"holdings.00411A": 0}) == ()
    # 網站 status：跨境看前一交易日
    snap = t3._full_snapshot(d4, skip={("holdings.00411A", D(11, 4))})
    st = {x["k"]: x for x in health.dataset_status(snap, D(11, 4), T(11, 4, 18), CLOSED)}
    assert st["holdings.00411A"] == {"k": "holdings.00411A", "n": "00411A持股", "d": "2026-11-03", "s": "ok"}
    snap = t3._full_snapshot(d4, skip={("holdings.00411A", D(11, 3)), ("holdings.00411A", D(11, 4))})
    st = {x["k"]: x for x in health.dataset_status(snap, D(11, 4), T(11, 4, 22, 30), CLOSED)}
    assert st["holdings.00411A"]["s"] == health.ABNORMAL and st["holdings.00411A"]["m"] == "00411A持股停在 11/02"


def test_e2_all_missing_day():
    # 整天沒有收集：當天公布的資料集全部 0 筆即算，跨境持股（隔天才收）不影響判斷
    days = tradingcal.trading_days(D(10, 1), D(11, 3), CLOSED)
    core = [s.key for s in health.SPECS if not s.delay]
    snap = t3._full_snapshot(days, skip={(k, D(11, 2)) for k in core})
    items = health.evaluate(days, snap, T(11, 3, 23))
    assert health.all_missing_days(items) == [D(11, 2)]
    lines = health.problem_lines(items)
    assert lines[0].startswith("❌ 2026-11-02 全部資料集都沒有") and len(lines) == 1


# ─── E2-1：--catch-up 與 history 真實流程（假的 HTTP 與資料庫）──
def _world_1104():
    w = World(D(11, 3))
    for k in ("holdings.00411A", "holdings.00988A"):
        del w.rows[k][D(11, 3)]                 # 跨境：11/03 的持股要 11/04 才公布
    w.published["GetPCF"].add(D(11, 3))
    return w


def test_e2_m1_published():
    w = _world_1104()
    w.publish(D(11, 4))
    rc, out = run_world(w, T(11, 4, 17, 30))
    hits = _pcf_hits(w)
    assert rc == 0 and "Traceback" not in out and len(hits) == 4
    assert {(f["fundCode"], f["date"], f["specificDate"]) for f in hits} == {
        ("49YTW", "115/11/05", True), ("63YTW", "115/11/05", True), ("64YTW", "115/11/05", True), ("61YTW", "115/11/05", True)}
    assert all(w.rows[f"holdings.{c}"][D(11, 4)].n == 50 for c in ("00981A", "00403A"))
    assert all(w.rows[f"holdings.{c}"][D(11, 3)].n == 50 for c in ("00411A", "00988A")) and D(11, 4) not in w.rows["holdings.00411A"]
    rc, out = run_world(w, T(11, 4, 19, 30))
    assert rc == 0 and len(_pcf_hits(w)) == 4                   # 重跑：持股不再請求


def _stale(w):
    """未公布時回應前一持股日的清單（實際行為之一）：把生效日往前推一個交易日再回應。"""
    orig = w._pcf

    def pcf(form):
        if _hold(form) in w.published["GetPCF"]:
            return orig(form)
        y, m, dd = form["date"].split("/")
        prev = tradingcal.trading_days(date(int(y) + 1911, int(m), int(dd)) - timedelta(days=30), date(int(y) + 1911, int(m), int(dd)) - timedelta(days=1), CLOSED)[-1]
        return orig({**form, "date": f"{prev.year - 1911}/{prev:%m/%d}"})
    w._pcf = pcf


def test_e2_m2_m3_not_published():
    w = World(D(11, 3))
    w.publish(D(11, 4), "GetPCF")
    _stale(w)
    rc, out = run_world(w, T(11, 4, 17, 30))
    assert rc == 0 and "⏳ 00981A持股：2026-11-04 尚未公布" in out and "Traceback" not in out
    assert D(11, 4) not in w.rows["holdings.00981A"] and w.notices == []
    rc, out = run_world(w, T(11, 4, 22, 30))
    assert rc == 1 and "❌ 00981A持股：缺 2026-11-04" in out and "Traceback" not in out
    assert len(w.notices) == 1 and "holdings.00981A:2026-11-04" in w.notices[0]


def test_e2_m4_schema_only_that_etf():
    w = _world_1104()
    w.publish(D(11, 4))
    orig = w._pcf
    w._pcf = lambda form: t3.Resp({"pcf": [], "fund": {}}) if form["fundCode"] == "63YTW" else orig(form)
    rc, out = run_world(w, T(11, 4, 17, 30))
    assert rc == 1 and "Traceback" not in out and "holdings.00403A 失敗：GetPCF 回應缺少 pcf 或 asset" in out
    assert D(11, 4) not in w.rows["holdings.00403A"] and w.rows["holdings.00981A"][D(11, 4)].n == 50
    assert w.rows["prices.TWSE"][D(11, 4)].n == 1100 and w.rows["breadth.TWSE"][D(11, 4)].n == 1
    # DetailCode 不見：KeyError 也只影響該檔
    w = _world_1104()
    w.publish(D(11, 4))
    orig = w._pcf

    def no_code(form):
        r = orig(form)
        if form["fundCode"] == "49YTW":
            for x in r.data["asset"][0]["Details"]:
                del x["DetailCode"]
        return r
    w._pcf = no_code
    rc, out = run_world(w, T(11, 4, 17, 30))
    assert rc == 1 and "Traceback" not in out and "holdings.00981A 失敗" in out and w.rows["holdings.00403A"][D(11, 4)].n == 50


def _history(w, start, end, only=("holdings",)):
    buf = io.StringIO()
    with env(w), contextlib.redirect_stdout(buf):
        ok = history.run_history(start, end, datasets=only)
    return ok, buf.getvalue()


def test_e2_m6_before_listing():
    w = World(D(8, 21))
    w.published["GetPCF"].update(tradingcal.trading_days(D(8, 24), D(8, 31), CLOSED))
    ok, out = _history(w, D(8, 24), D(8, 28))
    assert ok and "Traceback" not in out
    assert [_hold(f) for f in _pcf_hits(w, "64YTW")] == [D(8, 26), D(8, 27), D(8, 28)]     # 00411A 8/26 上市，之前不請求
    assert len(_pcf_hits(w, "49YTW")) == 5 and all(D(8, 26) in w.rows[k] for k in HKEYS)
    ok, out = _history(w, D(8, 24), D(8, 28))
    assert ok and len(_pcf_hits(w)) == 18 and "待抓 0 天" in out             # 重跑：待抓 0 天、0 請求


def test_e2_m7_holiday():
    w = World(D(12, 24))
    rc, out = run_world(w, T(12, 25, 17, 30))
    assert rc == 0 and _pcf_hits(w) == [] and not t3._hit(w, "highlight") and "今天 2026-12-25 休市" in out


def test_e2_m8_history_schema():
    w = World(D(10, 30))
    w.published["GetPCF"].update({D(11, 2), D(11, 3)})
    w._pcf = lambda form: t3.Resp({"pcf": [], "fund": {}})
    args = argparse.Namespace(only=["holdings"], start=D(11, 2), end=D(11, 3), force=False, no_revenue=True, delay=0.0)
    buf = io.StringIO()
    with env(w), contextlib.redirect_stdout(buf):
        rc = cli.cmd_history(args)
    out = buf.getvalue()
    assert rc == 1 and "官方欄位不符（GetPCF 回應缺少 pcf 或 asset）" in out and "Traceback" not in out
    assert len(_pcf_hits(w)) == 4                                           # 第一天（4 檔）就停，不浪費第二天的請求


def test_e2_cli():
    src = (ROOT / "twstock/__main__.py").read_text(encoding="utf-8")
    assert '"margin", "holdings"]' in src and "--only holdings" in src


# ─── A3：官方漲跌家數 ─────────────────────────────────────
def test_a3_parse():
    tw = daily.parse_twse_breadth({"stat": "OK", "tables": [MI_BREADTH]}, D(11, 3))
    assert tw == {"trade_date": "2026-11-03", "market": "TWSE", "up": 58, "up_limit": 2, "down": 1000, "down_limit": 33, "flat": 22, "no_trade": 6}
    assert daily.parse_twse_breadth({"stat": "很抱歉，沒有符合條件的資料!"}, D(11, 3)) is None
    for bad in ({"stat": "OK", "tables": []}, {"stat": "OK", "tables": [{**MI_BREADTH, "fields": ["類型", "整體市場", "改名"]}]}):
        try:
            daily.parse_twse_breadth(bad, D(11, 3))
            raise AssertionError(bad)
        except SchemaError:
            pass
    tp = daily.parse_tpex_breadth(TPEX_HL, D(11, 3))
    assert tp == {"trade_date": "2026-11-03", "market": "TPEx", "up": 59, "up_limit": 11, "down": 782, "down_limit": 41, "flat": 32, "no_trade": 24}
    assert daily.parse_tpex_breadth([], D(11, 3)) is None


def test_a3_flow():
    # 上市家數 0 請求（與行情共用 MI_INDEX）；上櫃 +1；上櫃失敗只有 breadth.TPEx 異常
    w = World(D(11, 3))
    w.publish(D(11, 4))
    w.down.add("highlight")
    rc, out = run_world(w, T(11, 4, 22, 30))
    assert rc == 1 and len(t3._hit(w, "MI_INDEX")) == 1 and "Traceback" not in out
    assert w.rows["breadth.TWSE"][D(11, 4)].n == 1 and D(11, 4) not in w.rows["breadth.TPEx"]
    assert "❌ 上櫃漲跌家數" in out and "❌ 上市漲跌家數" not in out
    # 行情未公布：不打 highlight
    w = World(D(11, 3))
    rc, out = run_world(w, T(11, 4, 17, 30))
    assert rc == 0 and not t3._hit(w, "highlight")


# ─── E2-4：匯出 ───────────────────────────────────────────
HELD = {D(10, 26): {("ST", "2330"): ("台積電", 10000000, 10.0), ("ST", "3376"): ("新日興", 2000000, 0.1)},
        D(10, 27): {("ST", "2330"): ("台積電", 10000000, 10.0), ("ST", "3376"): ("新日興", 2000000, 0.1)},
        D(10, 28): {("ST", "2330"): ("台積電", 10000000, 10.0), ("ST", "3376"): ("新日興", 2000000, 0.1)},
        D(10, 29): {("ST", "2330"): ("台積電", 10000000, 10.0), ("ST", "3376"): ("新日興", 2000000, 0.1)},
        D(10, 30): {("ST", "2330"): ("台積電", 13251000, 11.84), ("ST", "3376"): ("新日興", 1740000, 0.09),
                    ("ST", "BE US"): ("BLOOM", 450000, 6.89), ("GD", "TX"): ("台指期貨", 679, 2.32)},
        D(11, 2): {("ST", "2330"): ("台積電", 13728000, 11.86), ("ST", "3376"): ("新日興", 1345000, 0.07),
                   ("ST", "BE US"): ("BLOOM", 450000, 6.0)},
        D(11, 3): {("ST", "2330"): ("台積電", 14464000, 13.05), ("ST", "1802"): ("台玻", 8479000, 0.23),
                   ("ST", "BE US"): ("BLOOM", 400000, 5.5), ("GD", "TX"): ("台指期貨", 679, 2.31)}}
DATES = sorted(HELD)
TW = {"2330", "3376", "1802"}


def test_e24_table():
    rows, out = export.holding_table(DATES, HELD, TW)
    by = {r["c"]: r for r in rows}
    assert [r["c"] for r in rows] == ["2330", "BE US", "1802"]                       # 依最新權重
    assert by["2330"] == {"c": "2330", "n": "台積電", "tw": 1, "s": [10000, 10000, 10000, 10000, 13251, 13728, 14464],
                          "w": [10.0, 10.0, 10.0, 10.0, 11.84, 11.86, 13.05], "l": 14464, "pw": 13.05, "d1": 736, "w1": 1.19, "d5": 4464}
    assert by["1802"]["new"] == 1 and by["1802"]["d1"] == 8479 and by["1802"]["w1"] == 0.23 and by["1802"]["d5"] == 8479
    assert by["BE US"]["tw"] == 0 and by["BE US"]["l"] == 400000 and by["BE US"]["d1"] == -50000      # 海外：股
    assert by["BE US"]["s"][:4] == [None] * 4 and by["BE US"]["d5"] == 400000
    assert out == [{"c": "3376", "n": "新日興", "tw": 1, "l": 1345, "pw": 0.07}]      # 出清；期貨不列入持股表
    rows, out = export.holding_table(DATES[-1:], HELD, TW)                         # 只有一天：沒有增減、沒有「新」
    assert all(r["d1"] is None and r["w1"] is None and "new" not in r for r in rows) and out == []


def test_e24_export_and_active():
    summary = {DATES[-1]: (Decimal("254413288263.00"), Decimal("24.8700"), 51, Decimal("94.43"), 679, Decimal("5887337400.00"))}
    H = export.holding_export("00981A", DATES, summary, HELD, TW, "主動統一台股增長", "TWSE")
    assert H["sum"] == {"d": "2026-11-03", "nav": 2544.13, "nu": 24.87, "n": 51, "sw": 94.43, "fl": 679, "fa": 58.87}
    assert H["fund"] == "49YTW" and H["delay"] == 0 and H["dates"][-1] == "2026-11-03" and len(H["rows"]) == 3
    act = export.stock_active({"00981A": (DATES, summary, HELD)}, TW)
    assert set(act) == {"2330", "1802"}                                            # 海外不進個股；出清的 3376 沒有卡片
    assert act["1802"] == [{"e": "00981A", "d": "2026-11-03", "l": 8479, "w": 0.23, "d1": 8479, "d5": 8479, "new": 1}]
    assert act["2330"][0]["d1"] == 736 and "new" not in act["2330"][0]


def test_a3_calc():
    days = tradingcal.trading_days(D(5, 1), D(11, 3), CLOSED)[-120:]
    up = {d: 10 + i * 0.1 for i, d in enumerate(days)}                              # 一路漲：站上均線、20 日新高
    down = {d: 100 - i * 0.1 for i, d in enumerate(days)}                           # 一路跌：20 日新低
    young = {d: 50.0 for d in days[-30:]}                                           # 只有 30 天：算 MA20 分母、不算 MA60
    tv = {d: 100.0 for d in days}
    tv[days[-1]] = 50.0
    B = export.breadth_calc({"TWSE": [up, down, young]}, days, {"TWSE": tv})["TWSE"]
    assert (B["d"], B["from"]) == ("2026-11-03", str(days[60])) and len(B["s20"]) == 60
    assert (B["n20"], B["n60"], B["ma20"], B["ma60"], B["hi"], B["lo"], B["vr"]) == (3, 2, 33.3, 50.0, 1, 1, 0.5)
    tv[days[-5]] = None
    assert export.breadth_calc({"TWSE": [up]}, days, {"TWSE": tv})["TWSE"]["vr"] is None      # 前 20 日有缺：不算


# ─── E2-4：網站（node 跑 app.js 真正的 holdTag；沒有 node 略過）────
def test_e24_hold_tag():
    if not shutil.which("node"):
        print("  （略過：沒有 node）")
        return
    js = (ROOT / "site/app.js").read_text(encoding="utf-8")
    line = js[js.index("const holdTag"):js.index("const HOLD_SORT")]
    script = ("const App = {latest: {holdings: {'00981A': {d: '2026-11-03'}}}};\n" + line +
              "\nconsole.log(JSON.stringify(['00981A', '00982A', '00406A', '0050'].map(holdTag)));")
    tags = json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True, timeout=30).stdout)
    assert tags == ['<a class="pill hold" href="#/etf/00981A">持股</a>', '<span class="pill muted">持股尚未支援</span>',
                    '<span class="pill muted">持股尚未支援</span>', '']


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"✅ {name}")
    print("全部通過")
```

## 附錄 E：PG 用 `logs/` 小工具

### E-1. `logs/iter05_history.py`（等同 `history --start 2025-10-30 --only holdings`，另保存 3 份 00981A 原始回應）

```python
"""
第 5 輪一次性補抓：等同 python3 -m twstock history --start 2025-10-30 --only holdings，
另外把 QA 要比對的 00981A 原始回應在「本來就要抓」的那一次順手存到 logs/（不多發請求）：
  持股日 2025-10-30、2026-11-02、2026-11-03 → logs/iter05_raw_GetPCF_00981A_YYYYMMDD.json（tests/test_iter05.py 會讀）
用法（專案根目錄）：python3 logs/iter05_history.py 2>&1 | tee -a logs/iter05_history.log
中斷或被限流時用同一指令重跑：只補缺的；已存的原始回應不會被刪除。
"""
import json
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from twstock import __main__ as cli  # noqa: E402
from twstock import fetch  # noqa: E402
from twstock.collectors import daily, holdings  # noqa: E402

KEEP = {date(2025, 10, 30), date(2026, 11, 2), date(2026, 11, 3)}
_fetch, _request, _now = daily.fetch_holdings, holdings.request, {}


def fetching(code, d, closed):
    _now["k"] = (code, d)
    return _fetch(code, d, closed)


def saving(method, url, **kw):
    data = _request(method, url, **kw)
    code, d = _now["k"]
    if code == "00981A" and d in KEEP:
        out = ROOT / "logs" / f"iter05_raw_GetPCF_00981A_{d:%Y%m%d}.json"
        out.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        print(f"  💾 已保存原始回應 {out.name}")
    return data


if __name__ == "__main__":
    daily.fetch_holdings, holdings.request = fetching, saving
    t0 = time.monotonic()
    rc = cli.main(["history", "--start", "2025-10-30", "--only", "holdings"])
    print(f"🌐 外部請求 {fetch.request_count()} 次，耗時 {(time.monotonic() - t0) / 60:.1f} 分鐘（rc={rc}）")
    sys.exit(rc)
```

### E-2. `logs/iter05_compare.py`（隔離比對：除新增鍵與 status 外必須相同）

用法：`python3 logs/iter05_compare.py logs/iter05_before site/data`；相同時印「除新增鍵外相同」、rc=0。

```python
# 用法：python3 logs/iter05_compare.py logs/iter05_before site/data —— 除了第 5 輪新增鍵以外完全相同（E2-4 #5）
import json, sys
from pathlib import Path
a, b = Path(sys.argv[1]), Path(sys.argv[2])
NEW_LATEST, NEW_STOCK = {"holdings", "breadth"}, {"active"}
A, B = json.loads((a / "latest.json").read_text()), json.loads((b / "latest.json").read_text())
assert set(B) - set(A) == NEW_LATEST and not set(A) - set(B), (set(B) ^ set(A))
for k in A:
    if k == "status":
        sa, sb = dict(A[k]), dict(B[k])
        sa.pop("exported_at"); sb.pop("exported_at")
        da = sa.pop("datasets"); db_ = [x for x in sb.pop("datasets") if not x["k"].startswith(("holdings.", "breadth."))]
        assert sa == sb and da == db_, k
    else:
        assert A[k] == B[k], k
diff, extra = 0, 0
for f in sorted((a / "stocks").glob("*.json")):
    x, y = json.loads(f.read_text()), json.loads((b / "stocks" / f.name).read_text())
    extra += "active" in y
    if {k: v for k, v in y.items() if k not in NEW_STOCK} != x:
        diff += 1
print(f"latest.json：除 {sorted(NEW_LATEST)} 與 status 新資料集外相同；stocks {len(list((a / 'stocks').glob('*.json')))} 檔，差異 {diff} 檔，有 active {extra} 檔")
print(f"latest.json 增加 {((b / 'latest.json').stat().st_size - (a / 'latest.json').stat().st_size) / 1024:.1f} KB")
```
