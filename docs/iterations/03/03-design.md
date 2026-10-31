# 第 03 輪｜System Analyst：設計文件

- 撰寫日期：2026-10-31
- 輸入：`02-pm.md` 本輪範圍 S1（含 P9）、S2、S3（含 A1-補漏、S7）、S4、S5、S6、F1（沿用 PM 編號）；`01-analyst.md`；第 2 輪 `03-design.md`（格式）、`05-qa.md`（QA-01）
- 依據：閱讀 `twstock/__main__.py`、`collectors/*.py`、`db.py`、`export.py`、`fetch.py`、`config.py`、`scripts/mac|windows`、`site/app.js`、`stock.js`、`index.html`、`app.css`、`tests/test_iter01|02.py`、README；資料庫唯讀查詢；2026-10-31 經 `fetch.request`（`RETRY_BACKOFF=()`，不重試）實測 11 個端點，每個至多 2 次（附錄 A）。
- **所有設計都先在專案外的暫存副本做成原型，並實際跑過**：`test_iter01`、`test_iter02`、`test_iter03`（43 個測試）全過；`check` 對真實資料庫唯讀跑出基線；寫入類 SQL 只在工作階段暫存表（`#table`）驗證語法與行為；前端在 8001 以注入模擬資料驗過桌機與 375px。專案程式與資料庫**沒有任何修改**，排程沒有安裝（`launchctl list | grep twstock`、`~/Library/LaunchAgents/com.twstock*` 皆無）。
- 本文件只描述設計。附錄 C、D 是原型的完整程式與測試，**可以直接套用**；要改寫法可以，但**函式名稱、資料表、判斷式、畫面文案、輸出訊息請照本文件**，`test_iter03.py` 與 QA 會照著驗。

> **影響設計的實測發現（PM 文件沒有預期到）**
> 1. **`futContractsDateDown` 查無資料時回 HTTP 200 ＋ HTML alert ＋ `window.location.replace("futContractsDateView")`**。現行程式把它當成「不是 CSV」丟 `FetchError`，導致每個休市日、未公布時都誤報異常，而且會讓 `taifex.com.tw` 整台主機被判定失敗。已設計修正（S3）。
> 2. **`holidaySchedule` 的 `queryYear` 參數無效**：預設與 `queryYear=116` 都回 2026。所以官方日曆**只能取得當年**，隔年要等官方切換（S5）。
> 3. **pyodbc 有連線池，`conn.close()` 不會釋放 `sp_getapplock`**（實測 close 後另一條連線仍回 −1）。`release_lock` 必須明確呼叫 `sp_releaseapplock`（S3）。
> 4. **櫃買指數缺的 223 天分布在 2025-10～2026-09 共 12 個月**，A1-補漏是 **12 次請求**，不是 PM 寫的 13 次（10 月已完整）。
> 5. **S1 的回補依賴 `collect_for_date` 的拆分與 `health` 的判斷**，所以「S1 修程式」要連同 S3 的 `daily.py` 拆分一起做，實作順序比 PM 版略有調整（見下）。

---

## 〇、變更總覽

### 檔案 × 項目對照表

| 檔案 | S1（含 P9） | S2 | S3（含 A1-補漏、S7） | S4 | S5 | S6 | F1 |
|---|---|---|---|---|---|---|---|
| `twstock/config.py` | | `TW_TZ`、`tw_now()` | | | | | |
| `twstock/fetch.py` | `SchemaError` | `request_count()` | `_dead_hosts` | | | | |
| `twstock/db.py` | | 新表 `collect_runs` | `acquire_lock`、`release_lock` | | 新表 `market_holidays` | | |
| `twstock/tradingcal.py`（新檔） | | | | | 全部；`HOLIDAYS`、`trading_days` 由 `history.py` 移入 | | |
| `twstock/health.py`（新檔） | 判斷缺漏 | `SPECS`、`assess`、`evaluate`、`check_report`、`run_check`、通知、執行紀錄 | `missing_keys`、`due_days` | `build_status` | | | |
| `twstock/collectors/catchup.py`（新檔） | | | `make_plan`、`execute_plan`、`run` | | 臨時休市判定 | | |
| `twstock/collectors/daily.py` | `parse_tpex_pe`、`PE`、`DATASET_KEYS` | | `collect_for_date` 拆分、`parse_tpex_index`、`collect_tpex_index(y, m)`、移除 `tpex_index` | | | `merge_stocks` | |
| `twstock/collectors/history.py` | `--only pe`、用 `missing_keys` | | `tpex_index`、共用判斷 | | 匯入 `tradingcal` | | |
| `twstock/collectors/futures.py` | | | 查無資料頁回傳 `[]` | | | | |
| `twstock/export.py` | | | `_write` 原子寫入、回傳耗時 | `status`、`updated_at` | | | `_tick_round`、`_changes`、板塊 `pct` |
| `twstock/__main__.py` | `--only pe` | `check` | `collect --catch-up`、`history` 加鎖 | | | | |
| `scripts/mac/*`、`scripts/windows/*` | | | 排程與手動腳本 | | | | |
| `site/index.html`、`site/app.css`、`site/app.js` | | | | 橫幅、更新於、重新檢查 | | | |
| `site/stock.js` | P9 副標 | | | | | | P17 平手 |
| `tests/test_iter03.py`（新檔） | ✓ | ✓ | ✓ | `dataset_status` | ✓ | ✓ | ✓ |
| `tests/test_iter02.py` | | | | | | | 兩處預期值（第 F1 節） |
| `README.md` | 見第七節清單 | 同左 | 同左 | 同左 | 同左 | 同左 | 同左 |

### 建議實作順序

與 PM 版的差異只有一處：`history --only pe` 要用拆分後的 `collect_for_date` 與 `missing_keys`，所以 S1、S3 的 `daily.py`、S2 的 `health.py`、S5 的 `tradingcal.py` 要先寫好才能回補。**基線仍在回補之前，回補、A1-補漏依序執行，不同時跑**（`history` 有鎖，同時跑第二個會回傳 1）。

| 步驟 | 內容 | 驗證 |
|---|---|---|
| 0 | 留存修改前狀態（T-PRE，第八節）：`latest.json` 與抽樣個股 | 檔案存在 |
| 1 | `config.py`、`fetch.py`、`db.py`、`tradingcal.py`、`health.py` → `python3 -m twstock setup-db`（兩次）；`__main__.py` 全部 | T-S2-1 |
| 2 | **基線**：`python3 -m twstock check 2>&1 \| tee logs/iter03_check_before.log` | T-S2-2（必須回傳 1，三項異常） |
| 3 | `daily.py`、`history.py`、`futures.py`、`catchup.py`、`test_iter03.py` | `test_iter01`、`test_iter02` 全過；`test_iter03` 除 S7、F1、排程腳本的測試之外通過（見下方說明） |
| 4 | **S1 回補**：快照 → `history --only pe`（約 13 分鐘）→ 比對 | T-S1-2～T-S1-5 |
| 5 | **A1-補漏**：`history --only tpex_index`（12 次，不到 1 分鐘） | T-S3-13 |
| 6 | `check 2>&1 \| tee logs/iter03_check_after.log` | T-S2-3（回傳 0） |
| 7 | `export.py` 的 S7、`status`、`updated_at`、回傳耗時（`catchup` 要用到，**必須在 `collect` 之前**） | `test_atomic_write`、T-S4-3 |
| 8 | **S6**：`collect --date 2026-10-30`（這次也是 `collect_for_date` 拆分的回歸測試，同時建立第一筆 alerts、events 紀錄） | T-S6-2、T-S3-R1、T-S2-4、T-S5-1 |
| 9 | 真實環境驗收：**非交易日**執行 `collect --catch-up`（必須排在步驟 8 之後） | T-S3-14 |
| 10 | F1：`export.py`、`stock.js`（P17，同時做 P9）、`test_iter02.py` 兩處預期值 → `/usr/bin/time -p python3 -m twstock export` | T-EXPORT、T-F1-* |
| 11 | S4 前端：`index.html`、`app.css`、`app.js` | 瀏覽器 T-S4-*、T-S1-6、T-S1-7、T-F1-5 |
| 12 | 排程腳本（只驗語法與預覽，不安裝） | T-S3-15～T-S3-17；`test_iter03` 全部通過 |
| 13 | README、`__main__.py` docstring；`serve --port 8001 --no-browser` 自測；**關閉伺服器** | 第七節清單 |

**步驟 3 的測試**：`python3 tests/test_iter03.py` 遇到第一個失敗就停，而 `test_atomic_write`、`test_changes_tick`、`test_group_pct_source`、`test_schedule_scripts_static`、`test_tick_round` 要到步驟 7、10、12 才會過（這台機器沒有 pytest）。在此之前用下面的腳本看未過清單，應該只有這 5 個；步驟 12 之後要 `全部通過`。

```bash
python3 - <<'EOF'
import sys; sys.path[:0] = ["tests", "."]
import contextlib, io, test_iter03 as t
fails = []
for k in sorted(vars(t)):
    if k.startswith("test_"):
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                getattr(t, k)()
        except Exception:
            fails.append(k)
print("未過：", fails)
EOF
```

> 工作量：程式約 870 行（新檔 730 行、既有檔淨增約 140 行）＋測試約 980 行。原型已跑通，**不需要依 PM 第五節第 13 點延後任何項目**。

### 共通約定

- **台灣時間**：Python 一律用 `config.tw_now()`（固定 +08:00，不依賴 tzdata，Windows 也能用）。寫入資料庫的時間由 Python 傳入，**不可用 `GETDATE()`**（容器是 UTC）。
- **資料庫是唯一事實**：是否齊全一律由資料庫現況判斷。抓完之後重新讀資料庫判狀態，不依賴「剛才寫了幾筆」。
- **錯誤分類**：`FetchError`（網路、封鎖）→ 該主機本次不再請求；`SchemaError`（有資料但欄位不符）→ 只影響該資料集；`pyodbc.Error` → 整次結束、回傳 2。
- **寫入粒度**：每個資料集各自抓完、各自 commit；同一個資料集仍然「全部抓完才寫入」。
- 外部請求一律經過 `fetch.request`。測試不可實際跳通知、不可安裝排程。
- 日期一律 `YYYY-MM-DD` 字串匯出，畫面用 `md()`。「更新於」的 `collected_at`、資料日 `date`、法人資料日 `flow_date`、本益比資料日 `fund.date`、匯出時間 `status.exported_at` 是五個不同的東西，**不可混用**。

### 資料集模型（`health.SPECS`，S1～S4 共用）

`check`、`--catch-up`、`history`、`status` 全部用這張表與 `assess()`，沒有第二套判斷。

| 鍵 | 名稱 | 資料表（市場依 `stocks.market_type`） | 端點 | 筆數下限 | 查填充率 | 回補 |
|---|---|---|---|---|---|---|
| `prices.TWSE` | 上市行情 | `daily_prices` | 證交所 `MI_INDEX` | 800 | | `history --only prices` |
| `prices.TPEx` | 上櫃行情 | `daily_prices` | 櫃買 `dailyQuotes` | 650 | | 同上 |
| `pe.TWSE` | 上市本益比 | `stock_fundamentals` | 證交所 `BWIBBU_d` | 800 | 三欄 | `history --only pe` |
| `pe.TPEx` | 上櫃本益比 | `stock_fundamentals` | 櫃買 `peQryDate` | 650 | 三欄 | 同上 |
| `insti.TWSE` | 上市法人 | `institutional_trades` | 證交所 `T86` | 800 | | `history --only insti` |
| `insti.TPEx` | 上櫃法人 | `institutional_trades` | 櫃買 `dailyTrade` | 550 | | 同上 |
| `amount` | 上市法人金額 | `insti_amount` | 證交所 `BFI82U` | 6 | | `history --only amount` |
| `index.TAIEX` | 加權指數 | `market_index` | 與 `MI_INDEX` 同一回應 | 1 | | `history --only index` |
| `index.TPEX` | 櫃買指數 | `market_index` | 櫃買 `indexInfo/inx`（**月查詢**） | 1 | | `history --only tpex_index` |
| `futures` | 台指期 | `futures_daily_prices`（TX、**只看 DAY**） | 期交所 `futDataDown`（區間） | 1 | | `futures --start` |
| `futures_oi` | 期貨法人 | `futures_institutional` | 期交所 `futContractsDateDown`（區間） | 9 | | 同上 |

**期貨只看日盤（PM 提示 6）**：夜盤的日期是歸屬日，日盤未公布前就可能有當天夜盤列，看全部會太早算齊。

**沒有日期的資料**（不在表內，另由執行紀錄追蹤，見 S3-4）：處置／注意股、除權息事件、月營收；`industry`、`chains` 只在有寫入行情時更新。

**齊全的定義（`assess`）**：`筆數 ≥ max(下限, 近 20 個有資料日的中位數 × 80%)`，且本益比類的本益比、淨值比、殖利率**填充率都 ≥ 50%**。

| 門檻 | 依據（242 交易日實查，附錄 B） |
|---|---|
| 80% 中位數 | 滾動回測唯一觸發是 `pe.TPEx` 2026-10-30（2 筆 vs 888），**沒有誤報** |
| 下限 800／650／550 | 低於歷史最小值（上市行情 1056、上櫃 858、上櫃法人 720），用來防止「資料少到中位數也失真」 |
| 填充率 50% | 歷史最低：上市本益比 73.9%、上櫃本益比 69.5%（虧損股是正常的），上櫃殖利率 0～0.2%（S1 的問題）。門檻剛好把問題與正常分開 |

**狀態與時間分界**（每個資料集 × 每個交易日；依序判斷，先符合先算）：

| 順序 | 條件 | 狀態 |
|---|---|---|
| 1 | 日曆上休市（週末、官方、手寫、臨時） | **不列入**（不算缺漏） |
| 2 | 今天且現在 < 15:00（`COLLECT_FROM`） | **不列入** |
| 3 | 本次抓取或解析失敗，且該資料確實還缺 | **異常**（不論時間） |
| 4 | `assess` 通過 | **正常** |
| 5 | 今天且現在 < 22:00（`DEADLINE`） | **尚未公布** |
| 6 | 其他（22:00 後、隔日之後） | **異常**；若符合 S5 臨時休市則改記休市 |

---

## S1. 上櫃本益比、殖利率修復與回補（優先 1，含 P9）

### S1-1 對應驗收條件（SA 修訂處標 ★）

| PM # | 驗收 | 測試 |
|---|---|---|
| 1 | 回補後 242 個交易日，每天上櫃殖利率非空 ≥ 800；重跑待抓 0 天 | T-S1-3、T-S1-5 |
| 2 | 5904 20.14／3.51、3564 87.91、6486 9.14、6147 36.03；2025-10-30 的 1240 11.63／1.69／5.94 | T-S1-3 |
| 3 ★ | 回歸：10/29 5904 20.22／9.37；上市列筆數與數值回補前後相同（★ 差異判讀見 S1-5） | T-S1-4 |
| 4 | 匯出後上櫃 `fund.date`=10/30 且 `fund.dy` 非空 ≥ 850 檔 | T-S1-7 |
| 5 | 5904 個股頁兩卡有「資料 10/30」與股本變動註記 | T-S1-6 |
| 6 | 實際欄位樣本的解析（`N/A`、空值）；欄位改名時其他資料集照常、無 Traceback | T-S1-1 |
| 7 | README、`__main__.py` 同步 | 第七節 R4、R12、M3 |

### S1-2 資料來源（2026-10-31 實測）

`POST https://www.tpex.org.tw/www/zh-tw/afterTrading/peQryDate`，`data={"date": "2026/10/29", "response": "json"}`

- 欄位：`股票代號, 公司名稱, 本益比, 每股股利, 股利年度, 殖利率(%), 股價淨值比, 財報年/季`。**現行程式找 `代號`、`殖利率`，所以永遠 0 筆**。
- 2026-10-29：891 筆。與資料庫比對：**本益比差異 0、淨值比差異 0、非空轉空 0**，殖利率非空 891（資料庫是 2）。
- 5904：20.22／3.50／9.37；3564：173.06／0.43／2.66。非數字本益比是字串 `N/A`（`clean_number` 回 `None`）。
- 休市（10/31）：`stat:"ok"`，表存在但 `data` 空 → `_tpex_tables` 濾掉 → 回傳 `{}`。
- 回應中沒有任何代號在 `stocks` 被標為 TWSE。資料庫上櫃 893 列多出的是 5236、8908（實為上市，由 S6 修正）。

### S1-3 資料庫

不改資料表。`stock_fundamentals` 的 MERGE 鍵不變：`(stock_id, trade_date)`。`merge_fundamentals` **新增 JOIN `daily_prices`**：只寫當天有行情列的股票。理由：現行程式的 `funds` 只含當天有行情的股票；拆開後若直接靠 `stocks` JOIN，會多寫沒有成交的股票，筆數與語意都會變。

### S1-4 程式

`daily.py`：

```python
def parse_tpex_pe(tables: list) -> dict: ...   # 有資料但欄位不符丟 SchemaError；空表回傳 {}
def fetch_tpex_pe(d: date) -> dict: return parse_tpex_pe(_tpex_tables("afterTrading/peQryDate", d))
PRICES, PE, INSTI, INDEX, AMOUNT, TPEX_INDEX = "prices", "pe", "insti", "index", "amount", "tpex_index"
ALL_DATASETS = (PRICES, PE, INSTI)
DATASET_KEYS = {PRICES: ("prices.TWSE", "prices.TPEx"), PE: ("pe.TWSE", "pe.TPEx"),
                INSTI: ("insti.TWSE", "insti.TPEx"), INDEX: ("index.TAIEX",), AMOUNT: ("amount",)}
```

`history.py`：每一天用 `missing_keys(d, keys, snap, med)` 算出**還缺的細項**，只抓那些細項。完整內容見附錄 C。

> **行為變更**：`history --only prices` 不再順帶寫本益比（現在是獨立資料集 `pe`）。不帶 `--only` 時預設 `prices`、`pe`、`insti`，與之前涵蓋相同。寫進 README（R4）。

### S1-5 一次性回補（PG 執行）

**會不會覆寫既有正確值？** 會重寫 `pe_ratio`、`pb_ratio`、`dividend_yield`、`eps`（OPENJSON 沒有 eps，結果 NULL），風險評估：

| 項目 | 結論 |
|---|---|
| 上櫃本益比、淨值比 | 10/29 實測與官方差異 0，不會變 |
| `eps` | 全表 NULL，不會遺失 |
| 官方為 `N/A` 的值 | 寫成 NULL，與官方一致；10/29 非空轉空 0 筆 |
| 上市列 | `pe.TWSE` 待抓 0 天（實算），且 `peQryDate` 只有上櫃代號 |
| 新增列 | 只新增「當天有行情列」的股票（全期有 15 個交易日完全沒有上櫃列，會補上） |
| 備份 | 使用者已備份：`../_backups/TwStock_before_round3.bak` |

**執行範圍（對真實資料庫實算）**：`pe.TPEx` 242 天、`pe.TWSE` 0 天、其他 0 天。只會發 242 次櫃買請求。

**預估時間**：242 × 3.2 秒 ≈ **13 分鐘**。

**冪等與續跑**：每天獨立 commit。中斷（Ctrl-C、闔上電腦、被封鎖）後**用同一個指令重跑**，已齊全的日期因 `assess` 通過而跳過；MERGE 重跑也不會產生重複列。`FetchError`（已含 30／60／120 秒退避）或欄位不符時立刻停止並回傳 1，不把剩下的請求浪費掉。鎖的 Session 在程序結束時自動釋放。

**回補指令**（這台 Mac 閒置 1 分鐘就睡眠，用 `caffeinate -i` 包住；只在執行期間生效，不改設定）：

```bash
python3 logs/snap_fund.py logs/iter03_fund_before.json        # 腳本見 T-S1-2
caffeinate -i python3 -m twstock history --start 2025-10-30 --end 2026-10-30 --only pe 2>&1 | tee logs/iter03_backfill_pe.log
```

預期開頭輸出：

```
📅 補抓範圍：2025-10-30 ~ 2026-10-30，資料集：pe
📊 交易日 242 天，待抓 242 天；⏱️  預估約 12.9 分鐘
   pe.TPEx：242 天
```

**上市列比對的差異判讀（★）**：比對腳本會列出所有差異。預期 **0 筆**。若出現差異，只有一種合理原因：該代號當時是上櫃、之後才轉上市（目前 `market_type` 是 TWSE，但當天 `peQryDate` 有列）。這種差異是修正、不是回歸，要在 `04-dev.md` 列出代號與日期；其他差異都算失敗，用備份還原調查。資料庫實查：過去一年 TWSE 標記且無基本面列的只有 4 檔 DR（9103、9105、9110、9136），沒有看到轉上市跡象，預期不會發生。

### S1-6 匯出

`fund` 欄位不變（`pe`、`pb`、`dy`、`date`）。

### S1-7 畫面：P9（`stock.js` 指標卡）

```js
const fundSub = v => [v == null && fund.date ? '官方未提供' : '', fund.date ? '資料 ' + md(fund.date) : '', capSub].filter(Boolean).join('；');
```

| 卡 | 值 | 副標 |
|---|---|---|
| 本益比 | `20.14` | `資料 10/30；08/10 股本變動，官方值可能尚未調整` |
| 殖利率 | `3.51%` | 同上 |
| 本益比（虧損股） | `--` | `官方未提供；資料 10/30` |
| 沒有 `fund` 的股票 | `--` | 空白（`fund.date` 不存在） |

PM 範圍是「本益比、殖利率卡」，**股價淨值比卡不動**。375px：副標沿用既有 `.s` 樣式換行，個股頁驗過無水平捲動。

### S1-8 邊界情況

| 情況 | 行為 |
|---|---|
| `N/A`、空字串 | `clean_number` 回 `None`，寫 NULL |
| 表有資料但必要欄位缺一個 | `SchemaError`；`collect` 只標該資料集異常；`history` 立刻停止 |
| 休市或未公布（空表） | 回傳 `{}`，`pe.TPEx` 無資料 |
| 當天上櫃行情失敗或為空 | 不打 `peQryDate`（本益比只寫有行情列的股票） |
| 非一般股票代號（`00679B`） | `is_valid_stock_code` 濾掉 |

### S1-9 測試案例

**T-S1-1（純邏輯）**：`python3 tests/test_iter03.py`，涵蓋 `test_parse_tpex_pe`、`test_s3_07_schema_change`、`test_history_pe_only`（只打櫃買、上市列不動、可中斷重跑、重跑 0 天、欄位不符停止）。

**T-S1-2（回補前快照，腳本放 `logs/`，不進版控）**：

```python
# logs/snap_fund.py：python3 logs/snap_fund.py logs/iter03_fund_before.json
import json, sys
sys.path.insert(0, ".")
from twstock import db
out, c = {}, db.connect().cursor()
for code, d, pe, pb, dy in c.execute("""SELECT s.stock_code, f.trade_date, f.pe_ratio, f.pb_ratio, f.dividend_yield
    FROM stock_fundamentals f JOIN stocks s ON s.stock_id = f.stock_id WHERE s.market_type = 'TWSE'""").fetchall():
    out[f"{d}|{code}"] = [str(pe), str(pb), str(dy)]
json.dump(out, open(sys.argv[1], "w"))
print(len(out), "列")
```

（實測 259,294 列，不到 2 秒。）

**T-S1-3（回補後數值）**：

```python
from datetime import date
from decimal import Decimal as D
from twstock import db
from twstock.collectors.history import trading_days
c = db.connect().cursor()
days = trading_days(date(2025, 10, 30), date(2026, 10, 30))
assert len(days) == 242
n = dict(c.execute("""SELECT f.trade_date, COUNT(f.dividend_yield) FROM stock_fundamentals f JOIN stocks s ON s.stock_id = f.stock_id
    WHERE s.market_type = 'TPEx' AND f.trade_date BETWEEN '2025-10-30' AND '2026-10-30' GROUP BY f.trade_date""").fetchall())
low = [(d, n.get(d, 0)) for d in days if n.get(d, 0) < 800]
assert not low, low
q = lambda code, d: tuple(c.execute("""SELECT f.pe_ratio, f.pb_ratio, f.dividend_yield FROM stock_fundamentals f JOIN stocks s ON s.stock_id = f.stock_id
    WHERE s.stock_code = ? AND f.trade_date = ?""", code, d).fetchone())
assert q("5904", "2026-10-30")[0] == D("20.14") and q("5904", "2026-10-30")[2] == D("3.51")
assert q("3564", "2026-10-30")[0] == D("87.91") and q("6486", "2026-10-30")[0] == D("9.14") and q("6147", "2026-10-30")[0] == D("36.03")
assert q("1240", "2025-10-30") == (D("11.63"), D("1.69"), D("5.94"))
assert q("5904", "2026-10-29")[:2] == (D("20.22"), D("9.37"))
print("OK")
```

**T-S1-4（上市列比對）**：再跑一次 `snap_fund.py` 存成 `logs/iter03_fund_after.json`，然後：

```python
import json
a, b = json.load(open("logs/iter03_fund_before.json")), json.load(open("logs/iter03_fund_after.json"))
diff = sorted(k for k in a.keys() | b.keys() if a.get(k) != b.get(k))
print("列數", len(a), len(b), "差異", len(diff), diff[:20])       # 預期 差異 0；非 0 依 S1-5 判讀
```

**T-S1-5（重跑）**：同一個 `history` 指令再跑一次，輸出 `待抓 0 天`，外部請求 0 次，回傳 0。

**T-S1-6（瀏覽器，匯出後）**：先確認拿到新版 JS（見第八節快取提醒）。

```js
// 開 #/stock/5904，等畫面完成
const t = document.querySelector('.metrics').innerText;
[t.includes('20.14'), t.includes('3.51%'), (t.match(/資料 10\/30/g) || []).length >= 2, t.includes('08/10') && t.includes('官方值可能尚未調整')]   // 全部 true
```

**T-S1-7（匯出後）**：

```python
import json, glob
n = 0
for p in glob.glob("site/data/stocks/*.json"):
    s = json.load(open(p, encoding="utf-8"))
    f = s.get("fund") or {}
    n += s.get("market") == "TPEx" and f.get("date") == "2026-10-30" and f.get("dy") is not None
print(n); assert n >= 850
```

---

## S2. 收集完整性檢查與執行紀錄（優先 2）

### S2-1 對應驗收條件

| PM # | 驗收 | 測試 |
|---|---|---|
| 1 | `setup-db` 建表，重複執行不報錯 | T-S2-1 |
| 2 | 基線：回補前回傳 1，三項異常，存 `logs/iter03_check_before.log` | T-S2-2 |
| 3 | 回補與 A1-補漏後回傳 0，存 `logs/iter03_check_after.log` | T-S2-3 |
| 4 | `check` 不發外部請求、不寫資料庫 | `test_run_check_readonly`、`test_check_baseline` |
| 5 | 筆數、填充率、時間分界、休市日的單元測試 | `test_assess`、`test_status_boundary`、`test_due_days`、`test_check_baseline` |
| 6 | 通知：異常一次、同日不重複、正常不呼叫（mock `subprocess`） | `test_notify_once` |
| 7 | 紀錄時間是台灣時間 | `test_run_record`、T-S2-4 |
| 8 | README、`__main__.py` | R3、R4、R12、M2 |

### S2-2 資料庫（`db.py` 的 `DDL`，放在 `insti_amount` 之後、索引之前）

```sql
IF OBJECT_ID('collect_runs') IS NULL
CREATE TABLE collect_runs (
    run_id         INT IDENTITY(1,1) PRIMARY KEY,
    command        NVARCHAR(20)  NOT NULL,   -- catch-up / date
    started_at     DATETIME2(0)  NOT NULL,   -- 台灣時間，由 Python 傳入
    finished_at    DATETIME2(0)  NOT NULL,
    outcome        NVARCHAR(10)  NOT NULL CHECK (outcome IN ('ok','pending','abnormal')),
    new_data       BIT           NOT NULL,   -- 這次有新資料寫入（「更新於」的依據）
    requests       INT           NULL,       -- 這次對外請求次數
    export_seconds DECIMAL(7,1)  NULL,       -- 這次完整匯出耗時；沒有匯出為 NULL
    detail         NVARCHAR(MAX) NOT NULL    -- JSON
)
```

- 每次 `collect` 結束時 **INSERT 一筆**（不做「開始時寫、結束時更新」：中途程序被殺就留一筆沒有結束的列，判斷會變複雜；而資料本身已 commit，下次規劃看資料庫就好）。沒有 MERGE。
- `detail` JSON：`written`＝`{鍵: {日期: 筆數}}`；`items`＝非正常項目 `[{k, d, s, n, m}]`；`errors`＝`{鍵: 訊息}`；`undated`＝`{alerts: ISO 時間, events_to: 日期, revenue: 日期}`（只有成功才有）。
- `history` 不寫紀錄（它不是日常收集，不該更新「更新於」）；被鎖略過的那次也不寫。
- 累積公布時間的查詢（PM 第四節的「需確認」）：`SELECT finished_at, JSON_QUERY(detail, '$.written') FROM collect_runs ORDER BY run_id`。

### S2-3 `check` 指令

```
python -m twstock check [--days 20]
```

唯讀、不連外。`run_check(n, now)`：讀日曆與快照 → `check_report`（純函式，回傳 `(文字, 回傳碼)`）→ 印出。查詢範圍至少 20 個交易日（`--days` 小於 20 時中位數才有意義）。

| 回傳碼 | 意義 |
|---|---|
| 0 | 無異常（含「尚未公布」） |
| 1 | 有異常 |
| 2 | 連不上資料庫或資料表不存在（一行訊息，無 Traceback） |

**基線實際輸出**（真實資料庫，原型，模擬現在 2026-10-31 12:30）：

```
📋 資料完整性檢查：近 20 個交易日 2026-09-30 ～ 2026-10-30（現在 2026-10-31 12:30，台灣時間）
ℹ️  今天 2026-10-31 休市

資料集          涵蓋         最新日     筆數    中位數  本益比/淨值比/殖利率  狀態
上市行情      20/20   2026-10-30  1,090  1,086                        ✅ 正常
上櫃行情      20/20   2026-10-30    895    889                        ✅ 正常
上市本益比     20/20   2026-10-30  1,086  1,082  80% / 100% / 100%     ✅ 正常
上櫃本益比     20/20   2026-10-30      2    888  100% / 100% / 100%    ❌ 異常
上市法人      20/20   2026-10-30  1,077  1,077                        ✅ 正常
上櫃法人      20/20   2026-10-30    798    784                        ✅ 正常
上市法人金額    20/20   2026-10-30      6      6                        ✅ 正常
加權指數      20/20   2026-10-30      1      1                        ✅ 正常
櫃買指數      19/20   2026-10-30      1      1                        ❌ 異常
台指期       20/20   2026-10-30      6      6                        ✅ 正常
期貨法人      20/20   2026-10-30      9      9                        ✅ 正常

處置／注意股最後成功：尚無執行紀錄

❌ 上櫃本益比：2026-09-30 ～ 2026-10-29 共 19 天，最新 殖利率填充率 0.2%（下限 50%）
❌ 上櫃本益比：2026-10-30 筆數 2（近 20 日中位數 888，門檻 710）
❌ 櫃買指數：缺 2026-09-30

結果：異常 3 項
```

> 表格欄寬以 Python 字元數計，中文顯示會略微不齊，**可接受，不要為此加套件**。

回補與 A1-補漏後預期：`上櫃本益比` 列最新日 10/30、筆數約 890、填充率約 `76% / 100% / 100%`；`櫃買指數` 20/20；最後一行 `結果：無異常`，回傳 0。

**處置／注意股**：端點只有近幾日，錯過無法回補，所以 `check` 也看 `collect_runs`：最後成功落後 **2 個交易日以上**算異常；沒有紀錄不算（還沒跑過）。

**休市狀態**：今天休市印 `ℹ️  今天 2026-10-31 休市`；窗口內有自動判定的臨時休市時列出日期與復原方式。`check` **不判定**臨時休市（唯讀），只使用已登記的。

### S2-4 `collect` 結束時的輸出（`_print_summary`）

```
📊 收集結果（2026-11-02）
  ✅ 上市行情 1,090 筆
  ✅ 上櫃行情 895 筆
  ✅ 上市本益比 1,086 筆
  ...
  ⏳ 上市法人：2026-11-02 尚未公布
⏳ 部分尚未公布，下次排程會再補
```

### S2-5 通知

`health.notify_once(problems, today)`，`problems = {問題鍵: 說明}`，問題鍵 `資料集:日期`（或 `db`、`export`、`gap`、`alerts`…）。

- 只有 `--notify`（排程傳入）且結果為異常才呼叫；`尚未公布`不通知。手動執行不跳通知。
- 只有 `sys.platform == "darwin"`，呼叫 `/usr/bin/osascript -e 'display notification "…" with title "台股資料收集異常"'`，逾時 10 秒；失敗只印警告。
- 去重放在 `logs/notify_state.json`（`{"date": "...", "keys": [...]}`），**不放資料庫**：資料庫掛掉是最需要通知的情況。隔天、或同一天出現新問題會再通知。
- Windows 只寫紀錄。

### S2-6 邊界情況

| 情況 | 行為 |
|---|---|
| `--days 5` | 只列 5 天，但中位數仍用近 20 個交易日 |
| 資料庫還沒有 `collect_runs` | 回傳 2，訊息提示 `setup-db` |
| `logs/` 不存在 | `notify_once` 會建立 |
| 通知文字含引號 | 替換掉，避免 AppleScript 語法錯誤 |
| 連假中執行 | 窗口自動往前移，今天列為休市 |
| 新市場變動造成筆數突然變化 | 超過 20% 才報；S6 只移動 2 檔，不影響 |

### S2-7 測試案例

**T-S2-1**：

```bash
python3 -m twstock setup-db && python3 -m twstock setup-db     # 兩次都成功，訊息含 collect_runs、market_holidays
```

**T-S2-2（基線）**：`python3 -m twstock check 2>&1 | tee logs/iter03_check_before.log; echo "rc=${PIPESTATUS[0]}"` → `rc=1`；內容含 `2026-10-30 筆數 2`、`殖利率填充率`、`櫃買指數：缺 2026-09-30`、`異常 3 項`。（若在 11/02 之後才做，還會多列新日期的缺漏，屬正常，`04-dev.md` 註明。）

**T-S2-3**：回補與 A1-補漏後，同一指令 `rc=0`，含 `結果：無異常`，存 `logs/iter03_check_after.log`。

**T-S2-4（台灣時間，步驟 8 之後）**：

```python
from datetime import datetime
from twstock import db
from twstock.config import tw_now
r = db.connect().cursor().execute("SELECT TOP 1 started_at, finished_at FROM collect_runs ORDER BY run_id DESC").fetchone()
print(r, tw_now())   # 與現在的台灣時間相差不超過幾分鐘（不是差 8 小時）
assert abs((tw_now().replace(tzinfo=None) - r.finished_at).total_seconds()) < 3600
```

---

## S3. 排程可靠化（優先 3，含 A1-補漏、S7）

### S3-1 對應驗收條件

情境 1～12（mock，`tests/test_iter03.py`）對應：

| # | 情境 | 測試函式 |
|---|---|---|
| 1 | 行情已公布、上市 `T86` 未公布 | `test_s3_01_t86_late`（第二次請求清單只有 `/rwd/zh/fund/T86`） |
| 2 | 交易日 `MI_INDEX` 未公布 vs 休市 | `test_s3_02_not_published_vs_holiday` |
| 3 | 週一缺口，週二早上才執行 | `test_s3_03_next_morning` |
| 4 | 週五缺，週一執行 | `test_s3_04_friday_and_monday` |
| 5 | 上櫃行情回傳空的 | `test_s3_05_tpex_empty` |
| 6 | 單一端點 `FetchError` | `test_s3_06_fetch_error` |
| 7 | 官方欄位改名 | `test_s3_07_schema_change` |
| 8 | 資料庫連線失敗 | `test_s3_08_db_down` |
| 9 | 全部齊全 | `test_s3_09_complete` |
| 10 | 同一天連續兩次 | `test_s3_10_run_twice` |
| 11 | 兩個程序同時執行 | `test_s3_11_locked` |
| 12 | 11/02 補 10/30 櫃買指數 | `test_s3_12_tpex_index_old_month` |
| 補充 | 臨時休市流程、`--date` 相容、缺口提示、純函式規劃、期貨無資料頁、status 變動 | `test_s3_adhoc_closure_flow`、`test_s3_collect_date_compat`、`test_s3_gap_hint`、`test_plan_pure`、`test_futures_no_data_page`、`test_status_changed`、`test_dead_host` |

> 這些測試用假的 HTTP（`World.http`）與假的資料庫（`FakeCursor`），跑的是**真實流程**（`catchup.run` → `collect_for_date` → 解析 → MERGE 參數）。只有 `requests.Session.request`、`db.connect`、`export_all`、`notify_once` 是假的。

真實環境驗收 13～20 對應 T-S3-13～T-S3-20。★ PM 第 15 項的 ProgramArguments 多一個 `--notify`（通知要靠它）。★ A1-補漏是 12 次請求。

### S3-2 指令

```
python -m twstock collect                     # 今天（全部重抓覆寫），與之前相容
python -m twstock collect --date 2026-10-28   # 指定日期（全部重抓覆寫）
python -m twstock collect --catch-up          # 最近 10 個交易日，缺什麼補什麼
python -m twstock collect --catch-up --days 20
```

`--date` 與 `--catch-up` 互斥；`--days` 只能配 `--catch-up`，範圍 1～30。`--no-revenue`、`--no-export`、`--notify` 兩者皆可。

### S3-3 流程（`catchup.run` 是 `collect` 的唯一入口）

```
連線（catch-up 失敗等 60 秒重試一次）→ 取得鎖（被占用：印訊息，回傳 0）
→ update_calendar（需要時 1 個請求）→ 讀現況快照與執行紀錄
→ make_plan（純函式）或 plan_for_date（--date）
→ execute_plan（各資料集獨立抓取、寫入）
→ 重新讀資料庫 → 臨時休市判定 → evaluate → 印結果
→ 需要時匯出（有新資料，或 status 變動；--date 一律匯出）
→ 寫 collect_runs → 通知 → 釋放鎖 → 回傳碼
```

`make_plan(now, n, snap, state, closed, revenue_counts) -> dict`：輸入全部是資料，**不連網、不連資料庫**。輸出：

| 鍵 | 內容 |
|---|---|
| `days` | 評估窗口（`due_days`：最近 n 個應有資料的交易日） |
| `by_date` | `[(日期, 缺的鍵)]`，鍵的順序是 `DAY_KEYS`（行情先於本益比、法人） |
| `tpex_months` | 還有缺的月份 `[(年, 月)]` |
| `futures`、`futures_oi` | `(起, 迄)`：涵蓋所有缺口的區間，沒缺為 `None` |
| `alerts` | bool |
| `events` | `(起, 迄)` 或 `None` |
| `revenue` | `[(年, 月)]` |

**「缺什麼補什麼」的判斷**：

- **各資料集獨立**：`missing_keys(d, DAY_KEYS, snap, med)` 逐鍵判斷。
- **同市場相依（省請求）**：同市場行情回 0 筆就不打該市場的本益比、法人（官方不可能先有）；行情**錯誤**只跳過本益比（本益比要 JOIN 行情列），法人仍打。
- **尚未公布 vs 真缺漏**：只差在時間，見〇節狀態表。
- **休市日**：`due_days` 依日曆，根本不列入窗口，**不發請求**。
- **回溯上限**：預設 10、上限 30 個交易日。最舊窗口之前若最新日線還更舊（`latest_price < days[0]` 且中間有交易日），印 `python -m twstock history --start … --end …` 並回傳 1。只看「整段行情沒有」的情況，窗口外的局部缺口用 `check --days N` 查。
- **一天多次冪等**：齊全就 0 請求、不匯出；MERGE 重跑也不會產生重複列。

**沒有日期的資料**（靠 `collect_runs.detail.undated`，基準日 = 窗口最後一天）：

| 資料 | 何時要抓 | 一個基準日最多 |
|---|---|---|
| 處置／注意股 | 基準日 15:00 後抓一次；19:00 後再抓一次（當日公告底定） | 2 次 |
| 除權息事件 | `events_to < 基準日`。區間起點 = min(最舊缺口, 上次成功日) − `LOOKBACK_DAYS`，**涵蓋最舊缺口** | 1 次 |
| 月營收 | 窗口日期落在 `revenue_month_for` 規則內，該月筆數 < 前月 × 98%（或 0），且今天還沒抓過（月份規則維持現有） | 每天 1 次 |
| 產業別、產業鏈 | 本次有寫入行情；產業鏈 30 天更新一次 | — |

**錯誤處理**：

| 錯誤 | 行為 |
|---|---|
| `FetchError`（已退避 30／60／120 秒） | `fetch._dead_hosts` 記錄主機；本程序內該主機直接丟 `FetchError` 不再連線；其他主機照常 |
| 欄位不符（`SchemaError` 等 `PARSE_ERRORS`） | 只影響該資料集，**主機不停** |
| `pyodbc.Error` | 印兩行提示（Docker、容器、`setup-db`），無 Traceback，回傳 2，**不動 `site/data`**，不寫紀錄 |
| 匯出失敗 | 紀錄為異常、回傳 1；資料已寫入，下次 `status_changed` 會再匯出 |

**結束代碼**：

| 代碼 | 情況 |
|---|---|
| 0 | 全部齊全；部分尚未公布；休市；另一個程序正在執行 |
| 1 | 任一資料集異常（含抓取失敗、欄位不符、缺口超過窗口、匯出失敗） |
| 2 | 連不上資料庫或資料表不存在 |

`history` 被鎖住回傳 1（使用者要知道沒做事）。

**防重疊**：`db.acquire_lock()`（`sp_getapplock`，`@LockOwner='Session'`，`@LockTimeout=0`，跨平台）；持鎖連線貫穿整次執行；程序死掉鎖自動釋放。`release_lock` 要明確呼叫 `sp_releaseapplock`（連線池，見開頭發現 3）。

**`--date` 相容**：`plan_for_date` 把該日所有鍵列入、一律匯出（行為同舊版），只是粒度改成資料集、可部分成功。行事曆休市日不發行情請求；被自動判定為臨時休市的日期**可以**重查（復原用）。`collect`（不帶參數）= 今天。

**匯出判斷**：`changed = 快照前後不同 or 沒有日期資料的筆數改變`；另外 `status_changed`：網站 `status.datasets` 的 `(s, d)` 與現況不同也要匯出（例如尚未公布轉異常，橫幅才會更新）。

### S3-4 A1-補漏（`daily.py`）

`POST /indexInfo/inx`，`data={"date": "2026/10/01", "response": "json"}`，欄位 `日期, 開市, 最高, 最低, 收市, 漲/跌`；日期是西元 `2026/10/30`；**負值直接帶負號**（`['2026/10/30','384.20','384.20','365.70','370.26','-17.11']`）。未來月份回空表。MERGE 鍵不變：`(index_code, trade_date)`。

- 移除 `TPEX_OPENAPI`、舊 `fetch_tpex_index()`（OpenAPI，只有當月）。
- `collect_tpex_index(year, month)`：寫入該月全部日期。
- **一次性回補**（在 S1 回補完成後）：`python3 -m twstock history --start 2025-10-30 --end 2026-10-30 --only tpex_index`，**12 次請求**，約 40 秒。2025-10 整月都會寫入，10/30 之前的 21 筆在驗收範圍外，無害。

### S3-5 期貨修正（`futures.py`）

```python
if "futContractsDateView" in text:      # 查無資料（休市、尚未公布）：200 ＋ alert 後導回查詢頁，不是封鎖
    return []
```

真的被限流（不是 CSV，也沒有這個字樣）仍然丟 `FetchError`。

### S3-6 S7 原子寫入（`export.py`）

`_write`：先寫 `.{檔名}.{pid}.tmp`，再 `os.replace`；任何例外都刪暫存檔再往外丟。暫存檔在同一目錄，`os.replace` 才是原子操作（Windows 也可）。

### S3-7 排程腳本

**Mac**：`install_schedule.sh`（附錄 C）。

| 參數 | 行為 |
|---|---|
| （無） | 寫 plist、`launchctl bootstrap`。**安裝當下就會執行一次**（`RunAtLoad`） |
| `--print` | 只輸出 plist。**在 `launchctl bootout` 之前就結束**，不動 `~/Library/LaunchAgents` |
| `--uninstall` | `bootout` 並刪除 plist |

- `ProgramArguments`：`/usr/bin/caffeinate -i <絕對路徑 Python> -m twstock collect --catch-up --notify`。
- `StartCalendarInterval`：週一～五 × 17:30、19:30、21:45 共 15 組。
- `RunAtLoad`：開機登入補跑。副作用：安裝當下跑一次、登入時 Docker 可能還沒起來 → 程式等 60 秒重試一次；仍失敗回傳 2、跳通知，下次排程會補。
- 喚醒後網路未就緒：`fetch.request` 既有的 30／60／120 秒退避接住；真的失敗就記異常，下次補。臨時休市判定在查詢失敗時**不會觸發**。
- 這台 Mac 閒置 1 分鐘睡眠、沒有固定喚醒，排程時間多半睡著，launchd 喚醒後合併為一次。實際效果是「**下次打開電腦時補齊**」；S4 橫幅會說清楚。

**手動腳本**：`collect.command`、`collect.bat` 沒帶參數時預設 `--catch-up`，帶參數照傳（`--date` 仍可用）。

**Windows**：`install_schedule.bat` 建立三個工作 `TwStockCollect1730`、`1930`、`2145`（schtasks 一個工作只有一個時間），同時刪掉舊的 `TwStockCollect`。

- `.gitattributes` 規定 `*.bat eol=crlf`，存檔要是 CRLF。
- 不做登入補跑：`schtasks /SC ONLOGON` 常需要管理者權限。錯過排程要在工作排程器手動勾選（既有 README 就是這樣），訊息有提示。
- **未在 Windows 實測**，只做靜態檢查（`05-qa.md` 註明）。

### S3-8 邊界情況

| 情況 | 行為 |
|---|---|
| 15:00 前執行 | 今天不列入窗口，不打今天的端點 |
| 窗口內有臨時休市 | 判定後移出窗口，見 S5 |
| 假日早上喚醒 | 週五都齊全：0 請求；週五沒收到：補齊並匯出 |
| 同時手動與排程 | 後者印 `⏭️  另一個收集程序正在執行，這次略過`，回傳 0 |
| 法人公布前跑 `--catch-up` | 行情先寫入、匯出；網站由現有 `flowNote()` 提示；法人公布後下次補上再匯出 |
| 上櫃先於上市公布 | 各自獨立；資料日 `latest_date` 仍依既有匯出邏輯 |
| `latest.json` 被手動刪除 | `status_changed` 回 True，下次重新匯出 |
| 第一次 catch-up（沒有紀錄） | alerts、events 算缺；月營收看筆數，9 月已齊全不會請求 |
| 官方回 200 但全是 `--` | 視為 0 筆，時間到了算異常；不會寫入假資料 |

### S3-9 測試案例

**T-S3-1**：`python3 tests/test_iter01.py && python3 tests/test_iter02.py && python3 tests/test_iter03.py`，全部通過。

**T-S3-R1（拆分回歸，PM 風險 1）**：`collect --date 2026-10-30` 前後各跑一次下列腳本，比對。預期除 `stock_fundamentals`（10/30 已由回補寫入，不變）外各表 10/30 筆數相同；`stock_alerts`、`price_events` 可能因官方新資料增加，要說明。

```python
# logs/counts.py：python3 logs/counts.py logs/iter03_counts_before.json
import json, sys
sys.path.insert(0, ".")
from twstock import db
c, out = db.connect().cursor(), {}
for t in ("daily_prices", "stock_fundamentals", "institutional_trades", "market_index", "insti_amount", "futures_daily_prices", "futures_institutional"):
    out[t + "@1030"] = c.execute(f"SELECT COUNT(*) FROM {t} WHERE trade_date = '2026-10-30'").fetchone()[0]
for t in ("stocks", "daily_prices", "stock_fundamentals", "institutional_trades", "market_index", "stock_alerts", "price_events", "monthly_revenue"):
    out[t] = c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
json.dump(out, open(sys.argv[1], "w"), indent=1); print(out)
```

**T-S3-13（A1-補漏）**：

```python
from datetime import date
from decimal import Decimal as D
from twstock import db
from twstock.collectors.history import trading_days
c = db.connect().cursor()
days = trading_days(date(2025, 10, 30), date(2026, 10, 30))
have = {r[0] for r in c.execute("SELECT trade_date FROM market_index WHERE index_code = 'TPEX' AND trade_date BETWEEN '2025-10-30' AND '2026-10-30'").fetchall()}
assert len(have) == 242 and have == set(days), sorted(set(days) ^ have)
q = lambda d: tuple(c.execute("SELECT close_price, change FROM market_index WHERE index_code = 'TPEX' AND trade_date = ?", d).fetchone())
assert q("2025-11-03")[0] == D("265.68") and q("2026-09-01") == (D("410.77"), D("9.07")) and q("2026-10-30") == (D("370.26"), D("-17.11"))
print("OK")
```

匯出後首頁櫃買指數卡顯示「近 60 個交易日 ±x.x%」：`document.querySelector('.g-stats').innerText.includes('近 60 個交易日')`。

**T-S3-14（非交易日，步驟 8 之後）**：

```bash
md5 site/data/latest.json; python3 logs/counts.py logs/iter03_counts_a.json
python3 -m twstock collect --catch-up 2>&1 | tee logs/iter03_catchup_holiday.log; echo "rc=${PIPESTATUS[0]}"
md5 site/data/latest.json; python3 logs/counts.py logs/iter03_counts_b.json; diff logs/iter03_counts_a.json logs/iter03_counts_b.json
```

預期：`rc=0`；訊息含 `今天 … 休市`、`資料齊全，不需要請求`、`沒有新資料，不匯出`；筆數無差異；`latest.json` 不變；`SELECT TOP 1 requests FROM collect_runs ORDER BY run_id DESC` ≤ 1（只有日曆更新）。

> 順序：必須先跑過步驟 8。否則沒有 alerts、events 成功紀錄，第一次 catch-up 會請求這兩項（這是正確行為，只是不符合本項驗收）。

**T-S3-15（語法與預覽）**：

```bash
bash -n scripts/mac/install_schedule.sh && bash -n scripts/mac/collect.command
bash scripts/mac/install_schedule.sh --print > /tmp/twstock.plist && plutil -lint /tmp/twstock.plist
python3 - <<'EOF'
import plistlib
p = plistlib.load(open("/tmp/twstock.plist", "rb"))
a = p["ProgramArguments"]
assert a[:2] == ["/usr/bin/caffeinate", "-i"] and a[2].startswith("/") and a[3:] == ["-m", "twstock", "collect", "--catch-up", "--notify"]
t = {(x["Weekday"], x["Hour"], x["Minute"]) for x in p["StartCalendarInterval"]}
assert t == {(w, h, m) for w in range(1, 6) for h, m in ((17, 30), (19, 30), (21, 45))}
assert p["RunAtLoad"] is True and p["StandardOutPath"].endswith("logs/collect.log")
print("OK")
EOF
```

**T-S3-16（沒有安裝）**：`launchctl list | grep twstock`、`ls ~/Library/LaunchAgents | grep com.twstock` 都沒有結果（grep 回傳 1）。

**T-S3-17（Windows 靜態）**：`test_schedule_scripts_static`；`file scripts/windows/*.bat` 為 CRLF；內容有 17:30、19:30、21:45、`--catch-up`。

**T-S3-18（S7）**：`test_atomic_write`。

**T-S3-19、20**：第七節清單。

**T-S3-L（選用，真實鎖）**：`--catch-up` 被鎖時不會發請求。

```python
import subprocess, sys
from twstock import db
lock = db.acquire_lock(); assert lock is not None
r = subprocess.run([sys.executable, "-m", "twstock", "collect", "--catch-up"], capture_output=True, text=True)
db.release_lock(lock)
print(r.returncode, r.stdout); assert r.returncode == 0 and "另一個收集程序" in r.stdout
```

### S3-10 記錄完整匯出耗時（PM 第一節）

- `export_all()` 回傳耗時（秒），並印 `⏱️  匯出耗時 X 秒`；`catchup` 寫入 `collect_runs.export_seconds`。
- **T-EXPORT**（PG 在 `04-dev.md` 記錄）：`/usr/bin/time -p python3 -m twstock export 2>&1 | tee logs/iter03_export_time.log`，記錄 `real` 與 `⏱️` 兩個數字、`latest.json` 大小。之後可查：`SELECT TOP 20 finished_at, export_seconds FROM collect_runs WHERE export_seconds IS NOT NULL ORDER BY run_id DESC`。
- 只記錄，不優化。

---

## S4. 網站資料新鮮度提示（優先 4）

### S4-1 對應驗收條件

| PM # | 驗收 | 測試 |
|---|---|---|
| 1～3 | 10/31 不顯示；11/02 17:00 不顯示、18:30 顯示；12/25 不顯示 | T-S4-1 |
| 4 | 局部提示 | T-S4-2 |
| 5 | 連續 `export`，「更新於」不變 | T-S4-3 |
| 6 | `visibilitychange` 提示，不自動跳轉 | T-S4-4 |
| 7 | 舊版 `latest.json` 不報錯 | T-S4-5 |
| 8 | 375px、console、`latest.json` ≤ 5 KB | T-S4-6 |
| 9 | README | R12 |

### S4-2 匯出（`latest.json`）

```json
{
  "updated_at": "2026-11-02T19:31:05+08:00",
  "status": {
    "collected_at": "2026-11-02T19:31:05+08:00",
    "collected_src": "run",
    "exported_at": "2026-11-02T19:31:40+08:00",
    "datasets": [
      {"k": "prices.TWSE", "n": "上市行情", "d": "2026-11-02", "s": "ok"},
      {"k": "pe.TPEx", "n": "上櫃本益比", "d": "2026-10-29", "s": "abnormal", "m": "上櫃本益比停在 10/29"}
    ],
    "closed": ["2026-09-25", "2026-09-28", "2026-10-09", "2026-10-23", "2026-10-26", "2026-12-25"]
  },
  ...
}
```

| 欄位 | 規則 |
|---|---|
| `updated_at`、`collected_at` | **最後一次 `new_data=1` 的 `finished_at`**（台灣時間）。與匯出無關 |
| `collected_src` | `run` = 來自執行紀錄；`db` = 尚無紀錄，退回 `daily_prices MAX(created_at)` 換算台灣時間，畫面標「（依資料寫入時間）」 |
| `datasets[].s` | 以**資料日**為基準：`ok`／`pending`（資料日是今天且 22:00 前）／`abnormal`。整站落後由橫幅處理，不重複提示 |
| `datasets[].d` | 該資料集最後一個齊全的日期（近 45 天內） |
| `datasets[].m` | 只在 `abnormal` 時有：`{名稱}停在 MM/DD`、`{名稱}近期資料不足`、或 `{名稱} MM/DD 殖利率填充率 0.2%` |
| `closed` | **平日**休市日，從資料日前 45 天起（含未來）。週末前端自己算。靜態網站由此得知官方日曆與臨時休市 |

實測大小：`status` 全部 **961 B**（上限 5 KB）。

### S4-3 前端判斷（`app.js`）

```js
const FRESH_HOUR = 18;
App.now = () => new Date();         // 測試可替換
function twParts(t) { ... }         // Intl.DateTimeFormat + timeZone: 'Asia/Taipei'，不依賴瀏覽器時區
function expectedDate(t, closed) { ... }   // 今天開市且 ≥ 18:00 → 今天；否則往前找最近開市日
function freshLines(L, t) { ... }   // 回傳要顯示的文字陣列；舊版 latest.json 回 []
function renderStatus() { ... }
async function recheckLatest() { ... }
```

**靜態網站如何知道「今天」**：瀏覽器時間 → `Asia/Taipei`。**如何知道官方日曆**：`status.closed` ＋ 週末規則。不再另外請求。

規則與文字（完整程式見附錄 C）：

| 條件 | 文字 |
|---|---|
| `L.date < expectedDate` | `資料停在 10/30，最新交易日為 11/02，可能尚未收集` |
| 有 `abnormal` 且有 `m` | `部分資料異常：上櫃本益比停在 10/29`（最多列 3 項，超過加 `等 N 項`） |
| `visibilitychange` 後 `date`／`flow_date`／`updated_at` 有變 | `網站資料已更新（資料日 11/02）` ＋ 按鈕 `重新整理` |

- 日期列：`資料日 2026-10-30　法人資料 2026-10-30　更新於 2026-11-02 19:31`，退回時加 `（依資料寫入時間）`。
- 不用「失敗」這個字（PM 提示 9）。
- `recheckLatest`：每次回前景都重新計算橫幅（時間過了 18:00 也會出現）；`latest.json` 60 秒內只查一次（`getJSON` 已是 `cache: 'no-cache'`）；讀取失敗靜默，下次再查；**不自動重新整理**。

### S4-4 畫面

`index.html`，`#dateBar` 之後加：

```html
<div class="fresh" id="freshBar" role="status" hidden></div>
```

（★ PM 表沒有列 `index.html`，只多這一行。）

| 版面 | 規格 |
|---|---|
| 桌機 | 與內容同寬（`margin: 8px max(16px, calc((100% - 1088px)/2)) 0`）；左側 3px 橘色邊 `var(--amber)`、底色 `color-mix(… 14%, var(--card))`、13px；多行各佔一個 `<div>` |
| 375px | 左右各 16px（實測 `left 16`、`right 359`），文字換行（`overflow-wrap: anywhere`），高約 59px；`scrollWidth == 375` |
| 沒有提示 | `hidden`，不佔空間 |

深色模式跟著 CSS 變數，不需另寫。

### S4-5 邊界情況

| 情況 | 行為 |
|---|---|
| 週末、連假、官方休市 | `expectedDate` 往前找最近開市日，不誤報 |
| 臨時休市（颱風）**當晚** | 還沒判定（當天不判定），18:00 後可能顯示橫幅。文字是「可能尚未收集」，不算錯；隔天 catch-up 登記後消失 |
| 2027 年還沒有日曆 | 平日視為交易日，元旦可能誤報一次；後端印警告 |
| 使用者電腦時區不是台灣 | `twParts` 一律換算（已驗 `new Date('2026-11-02T10:30:00Z')` 同 18:30） |
| 舊版 `latest.json` | `freshLines` 回 `[]`，日期列用既有欄位，無 error |
| `updated_at` 為 `null`（資料庫完全沒有資料） | 日期列顯示空字串 |
| 回補後還沒有 `new_data=1` 的紀錄 | 「更新於」維持退回值＋「（依資料寫入時間）」，下次有新資料就切換。`history` 不算收集 |
| 匯出中讀到 | S7 保證不會讀到半個檔案 |

### S4-6 測試案例

先**強制載入新版 JS**（見第八節）。以下都不改檔案，只在記憶體模擬。

**T-S4-1**（時間與休市邏輯；前提是 `status` 的資料集都正常，否則陣列會多一行局部提示）：

```js
(() => {
  const base = { ...App.latest, date: '2026-10-30' };
  const at = (date, s) => freshLines({ ...base, date }, new Date(s));
  return {
    sat:    at('2026-10-30', '2026-10-31T12:00:00+08:00'),   // []
    mon17:  at('2026-10-30', '2026-11-02T17:00:00+08:00'),   // []
    mon18:  at('2026-10-30', '2026-11-02T18:30:00+08:00'),   // ['資料停在 10/30，最新交易日為 11/02，可能尚未收集']
    utc:    at('2026-10-30', '2026-11-02T10:30:00Z'),        // 同上
    xmasAm: at('2026-12-24', '2026-12-25T10:00:00+08:00'),   // []
    xmasPm: at('2026-12-24', '2026-12-25T19:00:00+08:00'),   // []
    after:  at('2026-12-24', '2026-12-28T18:30:00+08:00'),   // ['資料停在 12/24，最新交易日為 12/28，可能尚未收集']
    typhoon:at('2026-10-22', '2026-10-26T19:00:00+08:00'),   // []（連假＋臨時休市）
    tue:    at('2026-10-22', '2026-10-27T18:30:00+08:00'),   // ['資料停在 10/22，最新交易日為 10/27，可能尚未收集']
  };
})()
```

實際畫面：

```js
App.now = () => new Date('2026-11-02T18:30:00+08:00'); App.latest = { ...App.latest, date: '2026-10-30' }; renderStatus();
const shown = !document.querySelector('#freshBar').hidden && document.querySelector('#freshBar').innerText;
App.now = () => new Date(); renderStatus(); shown      // 含「資料停在 10/30」
```

**T-S4-2（局部提示）**：

```js
const st = structuredClone(App.latest.status), old = App.latest.status;
const x = st.datasets.find(d => d.k === 'pe.TPEx'); x.s = 'abnormal'; x.m = '上櫃本益比停在 10/29';
App.latest.status = st; renderStatus();
const r = [document.querySelector('#freshBar').innerText, !!document.querySelector('#view').children.length];
App.latest.status = old; renderStatus(); r     // ['部分資料異常：上櫃本益比停在 10/29', true]
```

**T-S4-3**：

```bash
python3 -m twstock export >/dev/null; python3 -c "import json;L=json.load(open('site/data/latest.json'));print(L['updated_at'],L['status']['exported_at'])"
python3 -m twstock export >/dev/null; python3 -c "import json;L=json.load(open('site/data/latest.json'));print(L['updated_at'],L['status']['exported_at'])"
# updated_at 兩次相同；exported_at 不同
```

**T-S4-4**：

```js
const orig = window.getJSON, before = location.href;
window.getJSON = async () => ({ ...App.latest, date: '2026-11-02', updated_at: 'x' });
App.checkedAt = 0; await recheckLatest();
const r = [document.querySelector('#freshBar').innerText.includes('網站資料已更新（資料日 11/02）'), !!document.querySelector('#reloadBtn'), location.href === before];
window.getJSON = orig; App.newDate = null; renderStatus(); r      // [true, true, true]
```

**T-S4-5**：

```js
const old = App.latest; App.latest = { ...old }; delete App.latest.status; renderStatus();
const r = [document.querySelector('#freshBar').hidden, document.querySelector('#dateBar').innerText.includes('更新於')];
App.latest = old; renderStatus(); r      // [true, true]；console 無 error
```

**T-S4-6**：viewport 375×812，模擬 T-S4-1 的畫面後 `document.documentElement.scrollWidth === 375`，`#freshBar` 的 `getBoundingClientRect()` left 16、right 359；首頁、個股頁都檢查。`read_console_messages` 無 error。大小：

```bash
python3 -c "import json;L=json.load(open('site/data/latest.json'));print(len(json.dumps(L['status'],ensure_ascii=False,separators=(',',':')).encode()))"   # ≤ 5120，原型 961
```

---

## S5. 官方交易日曆與臨時休市判斷（優先 5）

### S5-1 對應驗收條件

| PM # | 驗收 | 測試 |
|---|---|---|
| 1 | 官方與 `HOLIDAYS` 2026 逐日比對，差異列在 `04-dev.md` | T-S5-1（SA 人工比對：**零差異**） |
| 2 | `trading_days(2025-10-30, 2026-10-30)` 仍是 242 | `test_trading_days` |
| 3 | 端點失敗退回手寫表；2027 平日視為交易日且警告；同年第二次不發請求 | `test_update_calendar`、`test_trading_days`、`test_calendar_due`、`test_s3_09_complete` |
| 4 | 10/23 不被 `check` 列為缺漏；期交所有資料不判定休市 | `test_check_baseline`、`test_adhoc_closure`、`test_s3_adhoc_closure_flow` |
| 5 | README、`setup-db` | R3、R12 |

### S5-2 資料來源

`GET https://www.twse.com.tw/rwd/zh/holidaySchedule/holidaySchedule?response=json`

- 欄位：`日期, 名稱, 說明`；日期是 ISO `2026-01-01`；27 筆。
- **`queryYear` 無效**（116 仍回 2026），所以只取當年。`date=` 參數未測（已達 2 次上限）。
- 過濾名稱含「開始交易」「最後交易」的列後，平日休市 18 天，**與 `HOLIDAYS` 2026（排除 7/10、10/23）零差異**。
- 名稱含「市場無交易，僅辦理結算交割作業」的列是休市（2/12、2/13 等），要保留。

### S5-3 資料庫（`db.py` 的 `DDL`，接在 `collect_runs` 之後）

```sql
IF OBJECT_ID('market_holidays') IS NULL
CREATE TABLE market_holidays (
    holiday_date DATE          NOT NULL PRIMARY KEY,
    name         NVARCHAR(100) NOT NULL,
    source       NVARCHAR(10)  NOT NULL CHECK (source IN ('official','adhoc')),
    fetched_at   DATETIME2(0)  NOT NULL      -- 台灣時間
)
```

MERGE 鍵：`holiday_date`。官方每次先 `DELETE ... source='official' AND YEAR=…` 再寫入（官方取消休市日才會消失）。`adhoc` 不被官方更新刪除。

### S5-4 休市日的組成（`closed_from_rows`）

```
有官方資料的年度：官方表 ∪ AD_HOC ∪ adhoc
沒有官方資料的年度：手寫 HOLIDAYS ∪ AD_HOC ∪ adhoc
都沒有：平日一律視為交易日，warn_uncovered 印警告
```

`is_trading_day(d, closed=None)`、`trading_days(start, end, closed=None)`：`closed=None` 用手寫表（單元測試、舊呼叫相容）。`collect`、`check`、`history` 都傳 `load_closed(cur)`。

更新時機（`calendar_due`）：今年沒有官方資料，或最後更新超過 30 天。失敗只印 `⚠️  官方休市表更新失敗，改用手寫表`，不影響收集。

### S5-5 臨時休市

**判定**（只在 `--catch-up` 抓完之後，用剛重讀的資料庫）：

```python
def is_adhoc_closure(d, today, n_twse, n_tpex, n_futures, failed) -> bool:
    return d < today and not failed and n_twse == 0 and n_tpex == 0 and n_futures == 0
```

**保守的理由**：三個來源分屬不同主機（證交所、櫃買、期交所）；**任一查詢失敗都不判定**，所以官方端點短暫異常不會變成永久缺口；當天不判定；有任何一邊有資料就不是休市（改記異常）。比 PM 的「上市、期交所」多看一個上櫃，代價只是多一個端點已經會打的查詢。

**登記**：寫入 `market_holidays`（`source='adhoc'`，名稱 `臨時休市（自動判定）`），從窗口移除，不再發請求；`check` 列出。

**錯判復原**：`python -m twstock collect --date 2026-11-02`。`--date` 會略過 `adhoc` 判定重新查詢，查到上市行情就 `remove_adhoc` 並印 `↩️  … 有資料，移除臨時休市判定`。README 寫明（R12）。

`check` 唯讀，不判定。手寫 `AD_HOC`（7/10、10/23）永遠算休市，不會被官方更新蓋掉。

### S5-6 邊界情況

| 情況 | 行為 |
|---|---|
| 每年 1 月官方尚未切換 | 每次執行多 1 個請求（`calendar_due` 仍為 True），並印 `官方尚未提供 2027 年休市表`；平日視為交易日 |
| 官方欄位改名 | `SchemaError` 被接住，改用手寫表 |
| 官方表有週末日期 | 無影響（`weekday` 已先判斷）；`status.closed` 只列平日 |
| 官方把手寫 adhoc 日期也列入 | 改為 `official`（MERGE），行為相同 |
| 2027 元旦前 `HOLIDAYS` 沒資料 | 警告；README 提醒 |

### S5-7 測試案例

**T-S5-1**（步驟 8 之後）：

```python
from twstock import db, tradingcal
c = db.connect().cursor()
off = {r[0] for r in c.execute("SELECT holiday_date FROM market_holidays WHERE source = 'official' AND YEAR(holiday_date) = 2026").fetchall() if r[0].weekday() < 5}
hand = {h for h in tradingcal.HOLIDAYS if h.year == 2026}
print("官方多", sorted(off - hand), "手寫多", sorted(hand - off), "官方筆數", len(off))    # 預期都是空、18
assert len(tradingcal.trading_days(__import__("datetime").date(2025, 10, 30), __import__("datetime").date(2026, 10, 30), tradingcal.load_closed(c))) == 242
```

---

## S6. 補抓舊日期不覆蓋名稱與市場別（優先 6）

### S6-1 對應驗收條件

| PM # | 驗收 | 測試 |
|---|---|---|
| 1 | 舊日期不更新、新股票新增、最新日期更新 | `test_merge_stocks_flag`；暫存表實測（附錄 B） |
| 2 | `collect --date 2026-10-30` 後 5236、8908 = TWSE | T-S6-2 |
| 3 | 家數合計相同，兩檔計入上市 | T-S6-3 |
| 4 | 再補舊日期仍 TWSE | `test_merge_stocks_flag`、T-S6-4 |
| 5 | README | R12 |

### S6-2 設計

```python
def merge_stocks(cursor, rows: list, trade_date: date):
    latest = cursor.execute("SELECT MAX(trade_date) FROM daily_prices").fetchone()[0]
    cursor.execute("""
        MERGE stocks AS t
        USING OPENJSON(?) WITH (...) AS s
        ON t.stock_code = s.stock_code
        WHEN MATCHED AND ? = 1 THEN
            UPDATE SET stock_name = s.stock_name, market_type = s.market_type, updated_at = GETDATE()
        WHEN NOT MATCHED THEN
            INSERT (stock_code, stock_name, market_type) VALUES (s.stock_code, s.stock_name, s.market_type);
    """, db.to_json(rows), 1 if latest is None or trade_date >= latest else 0)
```

`trade_date >= latest`：用「已知最新日線」比，所以順序要是**先 `merge_stocks` 再 `merge_daily_prices`**（現況即是）。新日期（> latest）與補最新日（= latest）都更新；空資料庫也更新。呼叫端是 `_collect_key`，每個市場各呼叫一次。

**範圍外**：市場別歷史。`stocks.updated_at` 的 `GETDATE()` 是既有欄位（UTC），不動。

### S6-3 測試案例

**T-S6-2**：

```bash
python3 logs/counts.py logs/iter03_counts_before.json
python3 -m twstock collect --date 2026-10-30 2>&1 | tee logs/iter03_collect_1030.log
python3 logs/counts.py logs/iter03_counts_after.json
python3 -c "
from twstock import db
print(db.connect().cursor().execute(\"SELECT stock_code, market_type FROM stocks WHERE stock_code IN ('5236','8908')\").fetchall())"
# [('5236', 'TWSE'), ('8908', 'TWSE')]
```

**T-S6-3**：修改前（T-PRE）`market`：上市 94／945／46 = 1,085；上櫃 127／693／56 = 876；合計 1,961。修改後合計仍 1,961；預期上市 1,087、上櫃 874（前後數字記在 `04-dev.md`）。F1 也會改變部分個股的漲跌分類，但 10/30 只有 5 檔差異，**只比家數合計**。

```python
import json
for p in ("logs/iter03_before/latest.json", "site/data/latest.json"):
    m = json.load(open(p, encoding="utf-8"))["market"]
    n = {k: m[k]["up"] + m[k]["down"] + m[k]["flat"] for k in m}
    print(p, n, sum(n.values()))
```

**T-S6-4**：單元測試涵蓋。PG 不需要真的再跑一次舊日期（避免多餘請求）。

---

## F1. 小修正組（優先 7）

### F1-1 對應驗收條件

| PM # | 驗收 | 測試 |
|---|---|---|
| 1 | 6762 7/13 +2.5、4968 −1.5；事件日全部吻合官方 | `test_changes_tick`、T-F1-1、T-F1-2 |
| 2 | 6669 9/02 −5（−0.19%）；**2317 7/02 新預期值 −2（−0.83%）** | T-F1-1 |
| 3 | 還原不變：6669、5904（92.3／37.77）、3086（47.5／20.05）、3 檔 K 線 | T-F1-3 |
| 4 | half-up：650.5 → 651 | `test_tick_round` |
| 5 | 板塊 `pct` 等於 P14 漲跌幅 | `test_changes_tick`、`test_group_pct_source` |
| 6 | 5904 10/30「中性：3 多 3 空」無多方配色 | T-F1-5 |
| 7 | README | R10 |

### F1-2 QA-01：依升降單位取整

```python
_TICKS = ((Decimal(10), Decimal("0.01")), (Decimal(50), Decimal("0.05")), (Decimal(100), Decimal("0.1")),
          (Decimal(500), Decimal("0.5")), (Decimal(1000), Decimal(1)), (Decimal("Infinity"), Decimal(5)))

def _tick_round(price: float) -> float:
    p = Decimal(str(price))
    tick = next(t for limit, t in _TICKS if p < limit)
    return float((p / tick).quantize(Decimal(1), rounding=ROUND_HALF_UP) * tick)
```

**升降單位由取整前的價格決定**。

| 價格 | 單位 | 結果 | | 價格 | 單位 | 結果 |
|---|---|---|---|---|---|---|
| 9.994 | 0.01 | 9.99 | | 100.25 | 0.5 | 100.5 |
| 9.995 | 0.01 | 10.00 | | 167.62 | 0.5 | 167.5 |
| 10.02 | 0.05 | 10.00 | | 240.82 | 0.5 | 241 |
| 49.97 | 0.05 | 49.95 | | 499.75 | 0.5 | 500 |
| 50.04 | 0.1 | 50.0 | | 650.5 | 1 | **651**（內建 `round` 得 650） |
| 50.05 | 0.1 | 50.1 | | 999.5 | 1 | 1000 |
| 99.96 | 0.1 | 100.0 | | 1002.5 | 5 | 1005 |
| 100.2 | 0.5 | 100.0 | | 2614.99 | 5 | 2615 |

`_changes` 分支 1 改為 `round(float(c[i]) - _tick_round(e["r"]), 2)`。**只改這一行**：`_adj_factors` 仍用未取整的官方值，還原結果完全不變。

**新預期值（對真實資料庫實算）**：

| 股票 | 日期 | 收盤 | 參考價 → 取整 | 漲跌 | 幅度 | 修改前 |
|---|---|---|---|---|---|---|
| 6762 | 2026-07-13 | 170 | 167.62 → 167.5 | **+2.5** | 1.49% | +2.38 |
| 4968 | 2026-07-13 | | | **−1.5** | −1.36% | |
| 6669 | 2026-09-02 | 2,610 | 2,614.99 → 2,615 | **−5** | −0.19% | −4.99 |
| 2317 | 2026-07-02 | 239 | 240.82 → 241 | **−2** | **−0.83%** | −1.82 |
| 5904 | 2026-07-16 | 623 | 651.5 → 652 | **−29** | −4.45% | −28.5 |

**影響範圍**：事件日漲跌變動 687 筆、方向改變 32 筆。官方比對 **61／61 吻合**（口徑：官方非空，且「官方非 0 或 收盤＝取整參考價」，排除「調」；第 2 輪 QA 的官方參考比對口徑 69／69 也適用，用哪個都可以，`05-qa.md` 註明）。

**`tests/test_iter02.py` 要改兩處預期值**（`test_changes`）：`-1.82 → -2.0`、`-28.5 → -29.0`。這是規格變更，不是遷就。PG 在 `04-dev.md` 逐項說明。

**前端**：`stock.js` 沒有自行計算日線漲跌（`aggregate` 用匯出的 `ch`，`prev = close − change` 自動變成取整後的參考價），不用改。事件資訊列「參考價 2,614.99」仍是官方計算值，屬 P18，範圍外。

### F1-3 板塊漲跌幅

`export.py`：`"pct": _pct(c[i], ch[i])` → `"pct": _pct(c[i], chs[i])`。

影響（實算）：個股×日差異 1,981 筆，集中在除權息旺季（7/09 57 筆、7/16 48 筆）；類股×日差異 ≥ 0.1 個百分點 218／8,228，最大橡膠 6/17 −6.78、塑膠 7/08 +6.26。實際只影響泡泡圖窗口（`WINDOW` 39 天）與回放 20 天；**10/30 只有 5 檔差異，類股差 0.0**，QA 看不出畫面變化是正常的。

### F1-4 P17

`stock.js`：`isBull` 改為 `lean`（`bull`／`bear`／`''`）。平手文字 `中性：3 多 3 空`，class 只有 `signal`（無 `bull`、`bear` 配色）。偏多、偏空不變。總數不足的「資料不足」分支不變。

### F1-5 測試案例

**T-F1-1（匯出後）**：

```python
import json
def ch(code, d):
    p = json.load(open(f"site/data/stocks/{code}.json", encoding="utf-8"))["prices"]
    i = p["d"].index(d)
    return p["c"][i], p["ch"][i], round(p["ch"][i] / (p["c"][i] - p["ch"][i]) * 100, 2)
assert ch("6762", "2026-07-13")[1:] == (2.5, 1.49)
assert ch("4968", "2026-07-13")[1:] == (-1.5, -1.36)
assert ch("6669", "2026-09-02")[1:] == (-5.0, -0.19)
assert ch("2317", "2026-07-02")[1:] == (-2.0, -0.83)
print("OK")
```

**T-F1-2（事件日比對官方）**：

```python
# logs/f1check.py：預期印「事件日與官方吻合 61/61 []」（S6、新資料可能讓總數略變，要全部吻合）
import sys
sys.path.insert(0, ".")
from collections import defaultdict
from twstock import db
from twstock.export import _changes, _price_events, _tick_round
c = db.connect().cursor()
market = dict(c.execute("SELECT stock_code, market_type FROM stocks").fetchall())
ev, pr = defaultdict(list), defaultdict(list)
for code, d, t, p, r, src in c.execute("""SELECT s.stock_code, e.event_date, e.event_type, e.prev_close, e.ref_price, e.source
    FROM price_events e JOIN stocks s ON s.stock_id = e.stock_id ORDER BY 1, 2""").fetchall():
    ev[code].append({"d": d, "t": t, "p": float(p), "r": float(r), "src": src})
for code, d, cl, ch in c.execute("""SELECT s.stock_code, x.trade_date, x.close_price, x.change
    FROM daily_prices x JOIN stocks s ON s.stock_id = x.stock_id ORDER BY 1, 2""").fetchall():
    pr[code].append((d, cl, ch))
ok, total, bad = 0, 0, []
for code, rows in pr.items():
    d_, cl, ch = zip(*rows)
    E, _ = _price_events(d_, cl, ch, market[code], ev.get(code, []))
    chs, _, _ = _changes(d_, cl, ch, market[code], E)
    for e in E:
        i = e["i"]
        if cl[i] is None or ch[i] is None or e["t"] == "調":
            continue
        if float(ch[i]) != 0 or float(cl[i]) == _tick_round(e["r"]):
            total += 1
            if abs(float(ch[i]) - chs[i]) < 0.005:
                ok += 1
            else:
                bad.append((code, str(d_[i]), float(ch[i]), chs[i], e["r"]))
print(f"事件日與官方吻合 {ok}/{total}", bad[:10])
```

**T-F1-3（還原不變，T-PRE 留存的檔案）**：

```python
import json
for code in ("6669", "5904", "3086", "2330", "6762"):
    a = json.load(open(f"logs/iter03_before/stocks/{code}.json", encoding="utf-8"))
    b = json.load(open(f"site/data/stocks/{code}.json", encoding="utf-8"))
    for k in "dohlc":
        assert a["prices"][k] == b["prices"][k], (code, k)
    assert a["ev"] == b["ev"], code                # 事件的 p、r 不變 → 還原係數不變
L = json.load(open("site/data/latest.json", encoding="utf-8"))["stocks"]
assert (L["5904"]["h52"], L["5904"]["l52"]) == (92.3, 37.77)
assert (L["3086"]["h52"], L["3086"]["l52"]) == (47.5, 20.05)
A = json.load(open("logs/iter03_before/latest.json", encoding="utf-8"))["stocks"]
assert (A["6669"]["h52"], A["6669"]["l52"]) == (L["6669"]["h52"], L["6669"]["l52"])
print("OK")
```

**T-F1-5（瀏覽器，開 `#/stock/5904`）**：

```js
const s = document.querySelector('#sigBox .signal');
[s.innerText.includes('中性：3 多 3 空'), s.classList.contains('bull'), s.classList.contains('bear')]   // [true, false, false]
```

（前提：資料仍到 10/30；資料更新後訊號可能變化，改用當天的多空數比對。）

---

## 七、README 與 `__main__.py` 修改清單

PG 依清單修改，QA 逐條核對。

### README

| # | 位置（現行行號） | 修改 |
|---|---|---|
| R1 | 第 15～16 行專案結構 | 新增列：`twstock/tradingcal.py`｜交易日曆（官方休市表、手寫表、臨時休市）；`twstock/health.py`｜資料完整性判斷、`check`、執行紀錄、通知。`collectors/` 說明加 `catchup` 缺什麼補什麼 |
| R2 | 第 19 行 | 加 `python3 tests/test_iter03.py` |
| R3 | 第 38 行 | 括號加「第 3 輪的 `collect_runs`、`market_holidays`」，並把「否則 `export` 會失敗」改為「否則 `collect`、`check`、`export` 會失敗」 |
| R4 | 第 45～50、60 行指令區 | 見下方替換內容 |
| R5 | 第 63 行 | `collect.command`、`collect.bat` 改為「補齊最近缺的資料（等同 `collect --catch-up`）；帶參數時照傳」 |
| R6 | 第 65～70 行排程章節 | **全部改寫**，見下方 |
| R7 | 第 74 行 | 接著加：「各資料集獨立收集：行情公布、法人還沒公布時，會先寫入行情並更新網站（不再全有全無），下次排程補上法人。」 |
| R8 | 第 83 行 | 改為：「加權指數取自證交所 MI_INDEX（與上市行情同一個請求）；櫃買指數取自櫃買 `indexInfo/inx`（月查詢，可查歷史），缺的月份由 `collect --catch-up` 或 `history --only tpex_index` 補。」 |
| R9 | 第 84 行 | 「每次 `collect` 更新」改為「端點只有近幾日，錯過無法回補；`--catch-up` 每個交易日 15:00 後、19:00 後各抓一次」 |
| R10 | 第 87 行 | 第一句改為：「漲跌：除權息、減資、面額變更當天以『收盤 − 參考價』計算，參考價依升降單位四捨五入（與官方一致，例如 2,614.99 → 2,615；還原係數仍用未取整的官方值）；」，其餘不變。板塊泡泡圖的漲跌幅也用這個值 |
| R11 | 第 88 行 | 接著加：「本益比、殖利率卡會顯示資料日（例如『資料 10/30』）；官方沒有提供時標示『官方未提供』。」 |
| R12 | 注意事項新增 | 見下方「資料完整性」段落 |

**R4 替換內容**（第 45～50 行）：

```bash
python -m twstock collect --catch-up             # 補齊最近 10 個交易日缺的資料（可重複執行；齊全時 0 個請求、不匯出）。排程用這個
python -m twstock collect --catch-up --days 20   # 回溯 20 個交易日（上限 30，更早用 history）
python -m twstock collect                        # 今天全部重抓覆寫（含指數、台指期、處置／注意股、除權息事件、三大法人金額）並匯出網站 JSON
python -m twstock collect --date 2026-10-28      # 指定日期全部重抓覆寫；也用來復原被誤判的臨時休市
python -m twstock check                          # 檢查近 20 個交易日各資料集的完整性（唯讀、不連外）；有異常回傳 1
python -m twstock history --start 2026-01-02     # 補抓歷史（行情、本益比、法人），只補缺的，可中斷重跑
python -m twstock history --start 2026-01-02 --only insti   # 只補法人
python -m twstock history --start 2025-10-30 --only pe      # 只補本益比／淨值比／殖利率（--only prices 不再順帶寫入）
python -m twstock history --start 2026-02-23 --only index   # 只補加權指數歷史（一天一個請求）
python -m twstock history --start 2025-10-30 --only tpex_index  # 只補櫃買指數（一個月一個請求）
python -m twstock history --start 2026-07-31 --only amount  # 只補上市三大法人買賣金額（一天一個請求）
```

第 60 行後加 `python3 tests/test_iter03.py                     # 第 3 輪測試`。

**R6 排程章節**：

```markdown
### 自動排程（週一至週五 17:30、19:30、21:45）

**以下步驟由使用者自行執行**，程式不會自動安裝。排程執行 `collect --catch-up`：缺什麼補什麼，一天多次也不會重抓。

- Mac：`bash scripts/mac/install_schedule.sh`（只看內容不安裝：`--print`；移除：`--uninstall`）。**安裝當下會立刻執行一次**，之後每次登入也會補跑一次。排程以 `caffeinate -i` 執行，只在執行期間防止睡眠，不改系統設定。有異常時發本機通知，同一天同一問題只通知一次。
- Windows：執行 `scripts\windows\install_schedule.bat`（移除：加上 `/uninstall`）。會建立三個工作；要補跑錯過的排程，請在工作排程器勾選各工作的「錯過排程時儘快執行」。異常只寫紀錄。

執行紀錄寫入 `logs/collect.log` 與資料表 `collect_runs`。

**電腦設定（由使用者決定、自行執行）：**

- Mac 睡眠：電腦睡著時排程不會執行，喚醒後合併補跑一次，所以資料通常是「下次打開電腦時補齊」，不會遺失（處置／注意股例外，只查得到近幾日）。要當天晚上就有資料，可固定喚醒（需要管理者權限）：`sudo pmset repeat wakeorpoweron MTWRF 17:25:00`。
- 資料庫容器：重開機後容器沒啟動時收集會失敗（回傳 2、提示啟動）。可設定自動重啟：`docker update --restart unless-stopped MySqlServer`，並在 Docker Desktop 設定開機啟動。
```

**R12 新增（注意事項）**：

```markdown
- 資料完整性：每個資料集分市場判斷。**齊全** = 筆數 ≥ max(下限, 近 20 日中位數 × 80%)，且本益比、淨值比、殖利率的非空比例都 ≥ 50%。狀態：**正常**；**尚未公布**（當天 22:00 前還沒有）；**異常**（22:00 後或隔日仍缺、抓取失敗、欄位不符）；**休市**（不列入）。`collect --catch-up` 回傳 0 = 正常、尚未公布、休市或另一個程序正在執行；1 = 有異常；2 = 連不上資料庫。
- 交易日曆：優先用證交所官方休市表（`market_holidays`，只有當年，30 天更新一次），抓不到或沒有該年資料時用程式內的手寫表；都沒有時平日一律視為交易日並印警告，**每年年底請確認新年度的休市表**。
- 臨時休市（颱風假）：日期已過，且上市、上櫃、期交所都沒有資料、查詢都沒有失敗時，自動登記為臨時休市，不再算缺漏。判定錯誤時執行 `python -m twstock collect --date 該日`，查到資料就會移除判定。
- 網站的「更新於」是**最後一次收集到新資料的時間**，不是匯出時間；還沒有執行紀錄時退回資料寫入時間，並標示「（依資料寫入時間）」。`history` 補抓不算。依交易日曆資料落後時（交易日 18:00 前看前一交易日，之後看當天，台灣時間），顯示橘色提示；部分資料異常時顯示局部提示。分頁回到前景時會重新檢查，有新資料會提示重新整理，不會自動跳轉。
- 補抓舊日期（`collect --date`、`history`）不會覆蓋股票的名稱與市場別；只有最新日期的資料會更新。
- `_archive/` 是舊腳本，**不要再執行**：它連同一個資料庫，會把上櫃殖利率覆寫成 NULL，並蓋掉名稱與市場別。目前已把 `_archive/config.py` 改名為 `config.py.disabled` 使它無法執行，請不要改回來。
```

### `twstock/__main__.py`

| # | 位置 | 修改 |
|---|---|---|
| M1 | docstring | `collect` 列加「全部重抓覆寫」；新增 `collect --catch-up [--days 10]` 一列 |
| M2 | docstring | 新增 `check [--days 20]` 一列 |
| M3 | docstring | `history` 列改「只補缺的，可中斷重跑」；新增 `--only pe`、`--only tpex_index` |
| M4 | `collect` 子指令 | `--date`、`--catch-up` 互斥；`--days`、`--notify`；help 文字見附錄 C |
| M5 | `history` 子指令 | `--only` 加 `pe`、`tpex_index` |
| M6 | 新子指令 | `check --days` |
| M7 | `cmd_collect` | 全部移到 `catchup.run`，移除 `CHAINS_REFRESH_DAYS`（搬到 `catchup.py`） |
| M8 | `cmd_history` | 加鎖；預設日期改 `tw_now().date()` |

---

## 八、給 PG、QA 的提醒

### PG

1. **不要 commit、不要動 `.env`、不要安裝排程、不要 `pmset`、不要 `docker update`**。測試用埠 8001，結束時關閉（8000 是使用者的伺服器）。
2. **T-PRE（步驟 0，改任何程式之前）**：

   ```bash
   mkdir -p logs/iter03_before/stocks
   cp site/data/latest.json logs/iter03_before/
   for c in 6669 5904 3086 2330 6762; do cp site/data/stocks/$c.json logs/iter03_before/stocks/; done
   ```
3. 執行順序不能亂：`check` 基線 → `history --only pe` → `history --only tpex_index` → `check` → `export.py` 的 `status` 與回傳耗時 → `collect --date 2026-10-30` → 非交易日 `--catch-up`。舊版 `export_all()` 回傳 `None`，`catchup` 會把它當成匯出失敗，所以 `export.py` 要先改。
4. 回補一定要用 `caffeinate -i` 包住（這台 Mac 閒置 1 分鐘就睡）。回補中斷就重跑同一個指令。
5. `tests/test_iter02.py` 改兩處預期值（F1），`04-dev.md` 說明。
6. `collect_tpex_index()` 的無參數呼叫要全部移除（`__main__.py`）；`fetch_tpex_index` 簽名改了。
7. `history.py` 的 `HOLIDAYS`、`is_trading_day`、`trading_days` 移到 `tradingcal.py`，但保留從 `history` 匯入的對外名稱（`test_iter01`、`test_iter02` 用到）。
8. `*.bat` 要 CRLF、`*.sh`／`*.command` 要 LF（`.gitattributes`）。
9. `logs/` 已在 `.gitignore`，一次性腳本（`snap_fund.py`、`counts.py`、`f1check.py`）放那裡，不進版控。
10. **`04-dev.md` 要記錄**：T-S1 回補時間與比對結果；`iter03_check_before.log`、`iter03_check_after.log`；T-S5-1 差異；S6 前後家數；T-EXPORT 耗時與 `latest.json` 大小；T-S3-14 輸出；`test_iter02.py` 兩處；第 2 輪文件更正附註（T-P14-8 預期值、「24 筆」口徑，PM 第四節）。

### QA

1. **瀏覽器驗證前先強制載入新版 JS**：`python3 -m http.server` 沒有 no-cache，8001 的舊 `app.js` 會被快取，症狀是 `renderStatus is not defined`。執行 `await fetch('app.js', {cache:'reload'}); await fetch('stock.js', {cache:'reload'}); location.reload()`。
2. 第 2 輪的舊預期值已被取代：6669 −4.99 → −5；2317 −1.82 → −2。
3. 第 1 輪 A1 驗收 4 結案：SQL 複查 `market_index` 10/30 兩列（TAIEX 45,211.83 −1,156.50、TPEX 370.26 −17.11），MERGE 不更新 `created_at`，寫入時間仍可比對；`latest.json` 與首頁兩張指數卡都是 10/30 即通過（PM 第四節）。
4. T-F1-5、T-S4-1 依賴「資料到 10/30」。若驗證時已有新資料，依註解調整。
5. S4 測試都只改記憶體；`recheckLatest` 有 60 秒節流，測試要先設 `App.checkedAt = 0`。

---

## 九、對 PM 範圍的調整建議

| # | 建議 | 理由 |
|---|---|---|
| 1 | S3 的 A1-補漏改為 **12 次請求** | 實查缺口分布在 12 個月，10 月已完整 |
| 2 | 實作順序：`daily.py` 拆分提前到回補之前 | `history --only pe` 依賴它；基線仍在回補前 |
| 3 | S5：官方日曆**只取當年** | `queryYear` 無效；隔年靠官方切換＋手寫表＋警告 |
| 4 | 範圍表補上：新表 `market_holidays`、新檔 `tradingcal.py`、`health.py`、`catchup.py`、`site/index.html`（1 行）、`futures.py`（1 個條件） | PM 留給 SA 決定或未列 |
| 5 | S3 驗收 15：ProgramArguments 多 `--notify` | 通知由排程傳入，手動執行不跳通知 |
| 6 | S1 驗收 3：允許「轉上市前」的差異（預期 0 筆） | 代號當時確實在櫃買；比對腳本會列出 |
| 7 | `check` 增加處置／注意股落後 2 交易日算異常 | 這是唯一無法回補的資料，錯過就永遠缺；代價只有一個查詢 |
| 8 | 工作量：**不需要延後任何項目** | 原型已完整跑通 |

---

## 附錄 A：資料來源驗證紀錄（2026-10-31，`fetch.request`，`RETRY_BACKOFF=()`）

| 端點 | 次數 | 查詢 | 結果 |
|---|---|---|---|
| `MI_INDEX` | 1 | 20261031 | `stat="很抱歉，沒有符合條件的資料!"` |
| `BWIBBU_d` | 1 | 20261031 | 同上 |
| `fund/T86` | 1 | 20261031 | 同上 |
| `fund/BFI82U` | 1 | 20261031 | 同上 |
| `afterTrading/dailyQuotes` | 1 | 2026/10/31 | `stat:"ok"`，2 個表，`data` 空 |
| `afterTrading/peQryDate` | 2 | 2026/10/31；2026/10/29 | 空表；891 筆（S1-2） |
| `insti/dailyTrade` | 1 | 2026/10/31 | `stat:"ok"`，2 個表，`data` 空 |
| `indexInfo/inx` | 2 | 2026/11/01；2026/10/01 | 空表；19 筆，日期 `2026/10/30`，`-17.11` |
| `futDataDown` | 2 | 10/31；10/23 | 只有標題列（1 行），**臨時休市沒有夜盤列** |
| `futContractsDateDown` | 2 | 10/31；10/23 | 200 ＋ HTML alert ＋ `futContractsDateView` |
| `holidaySchedule` | 2 | 預設；`queryYear=116` | 都是 2026，27 筆 |

**休市與未公布，回應長得一樣**，只能靠日曆區分（所以 S2、S3 先查日曆，再看回應）。

## 附錄 B：資料庫基線（2026-10-31 唯讀；242 交易日）

| 資料集 | 中位數／最小 | 近 20 日中位數 | 待抓（S1 規劃） |
|---|---|---|---|
| `prices.TWSE` | 1076／1056 | 1086 | 0 |
| `prices.TPEx` | 883.5／858 | 889 | 0 |
| `insti.TWSE` | 1066／1012 | 1077 | 0 |
| `insti.TPEx` | 781／720 | 783.5 | 0 |
| `pe.TWSE` | 1072／1052 | 1082 | 0 |
| `pe.TPEx` | — | 888 | **242** |
| `amount` | 6（61 天） | 6 | 不適用（只補過近 61 天） |
| `index.TAIEX` | 242 天 | 1 | 0 |
| `index.TPEX` | 19 天 | 1 | **223（12 個月）** |
| `futures` 日盤 | 6 | 6 | |
| `futures_oi` | 9 | 9 | |

其他：基本面 408,166 列，`eps` 全 NULL；伺服器 UTC 偏移 0；日線最後寫入 2026-10-30 22:25:48（台灣）；月營收 8 月 1983、9 月 1980；事件 1,694 筆；上市 `market` 94／945／46，上櫃 127／693／56。

**SQL 行為驗證（工作階段暫存表，交易回滾，未寫入任何資料表）**：`write_run`、`load_state`、`add_adhoc`（重複呼叫不報錯）、`remove_adhoc`、官方 MERGE；`merge_stocks`：5236、8908 舊日期維持 TPEx、10/30 變 TWSE；`merge_fundamentals`：10/30 5904 寫入、不存在代號略過、10/31（無行情列）不寫；`acquire_lock`：第二次回 `None`、`release_lock` 後可再取得。

---

## 附錄 C：完整程式（原型，已通過測試）

新檔直接建立；既有檔是相對於目前專案的 unified diff，可以 `patch -p0` 或手動套用。

### `twstock/tradingcal.py`（新檔）

```python
"""
交易日曆：官方休市表（證交所 holidaySchedule）＋手寫表（備援與歷史）＋臨時休市。

官方表只有「今年」（2026-10-31 實測：queryYear 參數無效，一律回傳今年），每 30 天更新一次；
某年沒有官方資料時用手寫表，手寫表也沒有時平日一律視為交易日並印警告。
"""
from datetime import date, timedelta

from . import db
from .fetch import SchemaError, request

# ─── 手寫表（來源：證交所公告）。有官方資料的年度以官方為準 ────
HOLIDAYS = {
    # 2024
    date(2024, 1, 1), date(2024, 2, 8), date(2024, 2, 9), date(2024, 2, 12), date(2024, 2, 13),
    date(2024, 2, 14), date(2024, 4, 4), date(2024, 4, 5), date(2024, 5, 1), date(2024, 6, 10),
    date(2024, 9, 17), date(2024, 10, 10),
    # 2025
    date(2025, 1, 1), date(2025, 1, 27), date(2025, 1, 28), date(2025, 1, 29), date(2025, 1, 30),
    date(2025, 1, 31), date(2025, 2, 28), date(2025, 4, 3), date(2025, 4, 4), date(2025, 5, 1),
    date(2025, 5, 30), date(2025, 10, 6), date(2025, 10, 10), date(2025, 10, 24), date(2025, 10, 25),
    date(2025, 12, 25),
    # 2026
    date(2026, 1, 1), date(2026, 2, 12), date(2026, 2, 13), date(2026, 2, 16), date(2026, 2, 17),
    date(2026, 2, 18), date(2026, 2, 19), date(2026, 2, 20), date(2026, 2, 27), date(2026, 4, 3),
    date(2026, 4, 6), date(2026, 5, 1), date(2026, 6, 19), date(2026, 9, 25), date(2026, 9, 28),
    date(2026, 10, 9), date(2026, 10, 26), date(2026, 12, 25),
}
AD_HOC = {date(2026, 7, 10), date(2026, 10, 23)}   # 證交所當日無交易資料（臨時休市），官方休市表不會有
CAL_URL = "https://www.twse.com.tw/rwd/zh/holidaySchedule/holidaySchedule"
CAL_REFRESH_DAYS = 30


def closed_from_rows(rows) -> set:
    """rows: market_holidays 的 (日期, source)。有官方資料的年度不用手寫表；AD_HOC 與 adhoc 一律算休市。"""
    official = {d.year for d, source in rows if source == "official"}
    return {h for h in HOLIDAYS if h.year not in official} | AD_HOC | {d for d, _ in rows}


def load_closed(cur) -> set:
    return closed_from_rows([tuple(r) for r in cur.execute("SELECT holiday_date, source FROM market_holidays").fetchall()])


def is_trading_day(d: date, closed=None) -> bool:
    return d.weekday() < 5 and d not in (HOLIDAYS | AD_HOC if closed is None else closed)


def trading_days(start: date, end: date, closed=None) -> list:
    return [start + timedelta(n) for n in range((end - start).days + 1)
            if is_trading_day(start + timedelta(n), closed)]


def parse_holidays(data: dict) -> list:
    """官方休市表 → [(日期, 名稱)]；過濾「開始交易日」「最後交易日」等仍有交易的列。"""
    idx = {f: i for i, f in enumerate(data.get("fields") or [])}
    if not {"日期", "名稱"} <= idx.keys():
        raise SchemaError("holidaySchedule 欄位不符")
    out = []
    for row in data.get("data") or []:
        name = str(row[idx["名稱"]]).strip()
        if "開始交易" in name or "最後交易" in name:
            continue
        out.append((date.fromisoformat(str(row[idx["日期"]]).strip()), name))
    return out


def calendar_due(rows, now) -> bool:
    """rows: [(日期, source, fetched_at)]。今年沒有官方資料，或最後更新超過 30 天。"""
    fetched = [f for d, source, f in rows if source == "official" and d.year == now.year]
    return not fetched or (now.replace(tzinfo=None) - max(fetched)).days > CAL_REFRESH_DAYS


def update_calendar(now) -> None:
    """需要時更新官方休市表（1 個請求）。失敗只印警告，退回手寫表，不影響收集。"""
    conn = db.connect()
    try:
        cur = conn.cursor()
        rows = [tuple(r) for r in cur.execute("SELECT holiday_date, source, fetched_at FROM market_holidays").fetchall()]
        if calendar_due(rows, now):
            holidays = parse_holidays(request("GET", CAL_URL, params={"response": "json"}))
            years = {d.year for d, _ in holidays}
            for y in years:
                cur.execute("DELETE FROM market_holidays WHERE source = 'official' AND YEAR(holiday_date) = ?", y)
            for d, name in holidays:
                cur.execute("""
                    MERGE market_holidays AS t USING (SELECT ? AS holiday_date) AS s ON t.holiday_date = s.holiday_date
                    WHEN MATCHED THEN UPDATE SET name = ?, source = 'official', fetched_at = ?
                    WHEN NOT MATCHED THEN INSERT (holiday_date, name, source, fetched_at) VALUES (?, ?, 'official', ?);
                """, d, name, now.replace(tzinfo=None), d, name, now.replace(tzinfo=None))
            conn.commit()
            print(f"  🗓️  官方休市表：{sorted(years)} 年 {len(holidays)} 筆")
            if now.year not in years:
                print(f"  ⚠️  官方尚未提供 {now.year} 年休市表")
    except Exception as e:      # FetchError、欄位不符都不可中斷收集；資料庫錯誤下一步就會浮現
        print(f"  ⚠️  官方休市表更新失敗，改用手寫表：{e}")
    finally:
        conn.close()


def warn_uncovered(closed, now) -> None:
    if not any(d.year == now.year for d in closed):
        print(f"  ⚠️  沒有 {now.year} 年的休市資料，平日一律視為交易日；請更新官方休市表或手寫表")


def is_adhoc_closure(d: date, today: date, n_twse: int, n_tpex: int, n_futures: int, failed: bool) -> bool:
    """
    臨時休市：日期已過、上市與上櫃都沒有行情、期交所也沒有日盤，而且這些查詢都沒有失敗。
    三個來源分屬不同主機；任一查詢失敗（failed）都不判定，官方端點短暫異常不會變成永久缺口。
    """
    return d < today and not failed and n_twse == 0 and n_tpex == 0 and n_futures == 0


def add_adhoc(cur, d: date, now) -> None:
    cur.execute("""
        MERGE market_holidays AS t USING (SELECT ? AS holiday_date) AS s ON t.holiday_date = s.holiday_date
        WHEN NOT MATCHED THEN INSERT (holiday_date, name, source, fetched_at) VALUES (?, N'臨時休市（自動判定）', 'adhoc', ?);
    """, d, d, now.replace(tzinfo=None))


def remove_adhoc(cur, d: date) -> None:
    cur.execute("DELETE FROM market_holidays WHERE holiday_date = ? AND source = 'adhoc'", d)
```

### `twstock/health.py`（新檔）

```python
"""
資料完整性：check、collect --catch-up、history、export 的 status 共用同一張資料集表與同一套判斷。

一個資料集在某交易日「齊全」= 筆數 ≥ max(下限, 近 20 日中位數 × 80%)，且本益比類的三個欄位填充率都 ≥ 50%。
不齊全時：當天 22:00 前算「尚未公布」，之後算「異常」。
"""
import json
import statistics
import subprocess
import sys
from collections import namedtuple
from datetime import date, datetime, time, timedelta

from .config import LOG_DIR
from .tradingcal import load_closed, trading_days

COLLECT_FROM = time(15, 0)      # 當天資料最早的收集時間；之前「今天」不列入
DEADLINE = time(22, 0)          # 之前算尚未公布，之後算異常
ALERTS_SETTLED = time(19, 0)    # 處置／注意股當日公告大致底定的時間
COUNT_RATIO, FILL_MIN, MEDIAN_DAYS = 0.8, 0.5, 20
OK, PENDING, ABNORMAL = "ok", "pending", "abnormal"

Row = namedtuple("Row", "n pe pb dy", defaults=(0, 0, 0, 0))
Spec = namedtuple("Spec", "key label min_rows fills")
Item = namedtuple("Item", "key label date status n reason")
FILLS = (("pe", "本益比"), ("pb", "淨值比"), ("dy", "殖利率"))

SPECS = (
    Spec("prices.TWSE", "上市行情", 800, False), Spec("prices.TPEx", "上櫃行情", 650, False),
    Spec("pe.TWSE", "上市本益比", 800, True), Spec("pe.TPEx", "上櫃本益比", 650, True),
    Spec("insti.TWSE", "上市法人", 800, False), Spec("insti.TPEx", "上櫃法人", 550, False),
    Spec("amount", "上市法人金額", 6, False),
    Spec("index.TAIEX", "加權指數", 1, False), Spec("index.TPEX", "櫃買指數", 1, False),
    Spec("futures", "台指期", 1, False), Spec("futures_oi", "期貨法人", 9, False),
)
SPEC = {s.key: s for s in SPECS}

_MARKET_SQL = {
    "prices": "SELECT x.trade_date, s.market_type, COUNT(*), 0, 0, 0 FROM daily_prices x",
    "pe": "SELECT x.trade_date, s.market_type, COUNT(*), COUNT(x.pe_ratio), COUNT(x.pb_ratio), COUNT(x.dividend_yield) "
          "FROM stock_fundamentals x",
    "insti": "SELECT x.trade_date, s.market_type, COUNT(*), 0, 0, 0 FROM institutional_trades x",
}


def load_snapshot(cur, start: date, end: date) -> dict:
    """{鍵: {日期: Row}}，一個資料庫查詢一張表，不發外部請求。"""
    snap = {s.key: {} for s in SPECS}
    for name, sql in _MARKET_SQL.items():
        for d, market, n, pe, pb, dy in cur.execute(
                f"{sql} JOIN stocks s ON s.stock_id = x.stock_id WHERE x.trade_date BETWEEN ? AND ? "
                "GROUP BY x.trade_date, s.market_type", start, end).fetchall():
            snap[f"{name}.{market}"][d] = Row(n, pe, pb, dy)
    for d, code, n in cur.execute("SELECT trade_date, index_code, COUNT(*) FROM market_index "
                                  "WHERE trade_date BETWEEN ? AND ? GROUP BY trade_date, index_code", start, end).fetchall():
        snap[f"index.{code}"][d] = Row(n)
    for key, sql in (("amount", "SELECT trade_date, COUNT(*) FROM insti_amount WHERE trade_date BETWEEN ? AND ? GROUP BY trade_date"),
                     # 只看日盤：夜盤的日期是歸屬日，不代表該日資料已齊
                     ("futures", "SELECT trade_date, COUNT(*) FROM futures_daily_prices WHERE commodity_id = 'TX' AND session = 'DAY' "
                                 "AND trade_date BETWEEN ? AND ? GROUP BY trade_date"),
                     ("futures_oi", "SELECT trade_date, COUNT(*) FROM futures_institutional WHERE trade_date BETWEEN ? AND ? GROUP BY trade_date")):
        for d, n in cur.execute(sql, start, end).fetchall():
            snap[key][d] = Row(n)
    return snap


def medians(snap: dict) -> dict:
    """每個資料集最近 MEDIAN_DAYS 個有資料日期的筆數中位數；完全沒有資料為 0。"""
    out = {}
    for key, rows in snap.items():
        recent = [rows[d].n for d in sorted(rows)[-MEDIAN_DAYS:] if rows[d].n]
        out[key] = statistics.median(recent) if recent else 0
    return out


def assess(spec: Spec, row: Row, median: float):
    """齊全回傳 None；否則回傳 (種類, 說明)。種類：none 無資料 / count 筆數偏低 / fill:欄位 填充率偏低。"""
    if not row.n:
        return ("none", "無資料")
    need = max(spec.min_rows, median * COUNT_RATIO)
    if row.n < need:
        return ("count", f"筆數 {row.n:,}（近 {MEDIAN_DAYS} 日中位數 {median:,.0f}，門檻 {need:,.0f}）")
    if spec.fills:
        for f, label in FILLS:
            rate = getattr(row, f) / row.n
            if rate < FILL_MIN:
                return (f"fill:{label}", f"{label}填充率 {rate:.1%}（下限 {FILL_MIN:.0%}）")
    return None


def missing_keys(d: date, keys, snap: dict, med: dict) -> tuple:
    return tuple(k for k in keys if assess(SPEC[k], snap[k].get(d, Row()), med[k]))


def due_days(now: datetime, n: int, closed: set) -> list:
    """最近 n 個應該有資料的交易日（舊到新）；今天要過了 COLLECT_FROM 才算。"""
    today = now.date()
    last = today if now.time() >= COLLECT_FROM else today - timedelta(days=1)
    return trading_days(last - timedelta(days=n * 2 + 30), last, closed)[-n:]


def evaluate(days, snap: dict, now: datetime, errors=None) -> list:
    """每個資料集 × 每個交易日的狀態。errors = {(鍵, 日期) 或 鍵: 例外}：抓取失敗一律算異常，不論時間。"""
    errors, med, items = errors or {}, medians(snap), []
    for spec in SPECS:
        for d in days:
            row = snap[spec.key].get(d, Row())
            bad = assess(spec, row, med[spec.key])
            # (鍵, 日期)：這天抓取失敗；鍵：範圍查詢失敗（期貨、櫃買指數），只影響還缺資料的日期
            err = errors.get((spec.key, d)) or (errors.get(spec.key) if bad else None)
            if err is not None:
                items.append(Item(spec.key, spec.label, d, ABNORMAL, row.n, ("error", str(err))))
            elif bad is None:
                items.append(Item(spec.key, spec.label, d, OK, row.n, None))
            elif d == now.date() and now.time() < DEADLINE:
                items.append(Item(spec.key, spec.label, d, PENDING, row.n, bad))
            else:
                items.append(Item(spec.key, spec.label, d, ABNORMAL, row.n, bad))
    return items


def outcome(items) -> str:
    states = {i.status for i in items}
    return ABNORMAL if ABNORMAL in states else PENDING if PENDING in states else OK


def problem_lines(items) -> list:
    """把異常與尚未公布的項目彙總成一行一項（同資料集同原因合併）。"""
    groups = {}
    for i in items:
        if i.status != OK:
            groups.setdefault((i.status, i.key, i.reason[0]), []).append(i)
    lines = []
    for (status, _, kind), its in sorted(groups.items(), key=lambda g: (g[0][0] != ABNORMAL, list(SPEC).index(g[0][1]))):
        mark, label = ("❌", its[0].label) if status == ABNORMAL else ("⏳", its[0].label)
        days = [i.date for i in its]
        if status == PENDING:
            lines.append(f"{mark} {label}：{days[-1]} 尚未公布")
        elif kind == "none":
            lines.append(f"{mark} {label}：缺 " + "、".join(map(str, days[:8])) + (f" 等 {len(days)} 天" if len(days) > 8 else ""))
        elif len(days) == 1:
            lines.append(f"{mark} {label}：{days[0]} {its[0].reason[1]}")
        else:
            lines.append(f"{mark} {label}：{days[0]} ～ {days[-1]} 共 {len(days)} 天，最新 {its[-1].reason[1]}")
    return lines


# ─── 執行紀錄 ─────────────────────────────────────────────
def load_state(cur) -> dict:
    """由最近 200 筆執行紀錄整理：處置注意股、事件、營收最後成功的時間，與最後一次有新資料的時間。"""
    state = {"alerts_at": None, "events_to": None, "revenue_on": None, "collected_at": None}
    for finished, new_data, detail in cur.execute(
            "SELECT TOP 200 finished_at, new_data, detail FROM collect_runs ORDER BY run_id DESC").fetchall():
        if new_data and state["collected_at"] is None:
            state["collected_at"] = finished
        und = json.loads(detail).get("undated", {})
        if und.get("alerts") and state["alerts_at"] is None:
            state["alerts_at"] = datetime.fromisoformat(und["alerts"])
        if und.get("events_to") and state["events_to"] is None:
            state["events_to"] = date.fromisoformat(und["events_to"])
        if und.get("revenue") and state["revenue_on"] is None:
            state["revenue_on"] = date.fromisoformat(und["revenue"])
    return state


def write_run(cur, command, started, finished, result, new_data, requests, export_seconds, detail) -> None:
    cur.execute("INSERT INTO collect_runs (command, started_at, finished_at, outcome, new_data, requests, export_seconds, detail) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)", command, started.replace(tzinfo=None), finished.replace(tzinfo=None),
                result, 1 if new_data else 0, requests, export_seconds, json.dumps(detail, ensure_ascii=False, default=str))


# ─── 通知（只有 Mac；同一天同一問題只通知一次）──────────────
NOTIFY_FILE = LOG_DIR / "notify_state.json"


def notify_once(problems, today: date) -> bool:
    """problems: {問題鍵: 說明}。回傳是否真的發了通知。"""
    if not problems or sys.platform != "darwin":
        return False
    try:
        state = json.loads(NOTIFY_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        state = {}
    seen = set(state.get("keys", [])) if state.get("date") == str(today) else set()
    new = {k: v for k, v in problems.items() if k not in seen}
    if not new:
        return False
    text = "；".join(list(new.values())[:3]).replace('"', "'").replace("\\", "")
    try:
        subprocess.run(["/usr/bin/osascript", "-e", f'display notification "{text}" with title "台股資料收集異常"'],
                       timeout=10, check=False)
    except (OSError, subprocess.SubprocessError) as e:
        print(f"  ⚠️  通知失敗：{e}")
    NOTIFY_FILE.parent.mkdir(parents=True, exist_ok=True)
    NOTIFY_FILE.write_text(json.dumps({"date": str(today), "keys": sorted(seen | set(new))}), encoding="utf-8")
    return True


# ─── check 指令 ───────────────────────────────────────────
def check_report(days, snap, now, state, closed, adhoc=()) -> tuple:
    """回傳 (輸出文字, 回傳碼)。純函式：不連資料庫、不發請求。"""
    items, med = evaluate(days, snap, now), medians(snap)
    out = [f"📋 資料完整性檢查：近 {len(days)} 個交易日 {days[0]} ～ {days[-1]}（現在 {now:%Y-%m-%d %H:%M}，台灣時間）"]
    if now.weekday() >= 5 or now.date() in closed:
        out.append(f"ℹ️  今天 {now.date()} 休市")
    if adhoc:
        out.append("ℹ️  臨時休市（自動判定，判定錯誤可用 collect --date 復原）：" + "、".join(map(str, adhoc)))
    out.append(f"\n{'資料集':<8}{'涵蓋':>7}{'最新日':>12}{'筆數':>7}{'中位數':>7}  本益比/淨值比/殖利率  狀態")
    mark = {OK: "✅ 正常", PENDING: "⏳ 尚未公布", ABNORMAL: "❌ 異常"}
    for spec in SPECS:
        mine = [i for i in items if i.key == spec.key]
        have = [i for i in mine if i.n]
        last = have[-1] if have else None
        fill = ""
        if spec.fills and last:
            r = snap[spec.key][last.date]
            fill = f"{r.pe / r.n:.0%} / {r.pb / r.n:.0%} / {r.dy / r.n:.0%}"
        worst = outcome(mine)
        out.append(f"{spec.label:<8}{len(have):>4}/{len(mine):<3}{str(last.date) if last else '--':>12}"
                   f"{last.n if last else 0:>7,}{med[spec.key]:>7,.0f}  {fill:<20}  {mark[worst]}")
    alerts = state.get("alerts_at")
    out.append(f"\n處置／注意股最後成功：{alerts:%Y-%m-%d %H:%M}" if alerts else "\n處置／注意股最後成功：尚無執行紀錄")
    lines = problem_lines(items)
    # 處置／注意股端點只有近幾日，錯過無法回補：落後 2 個交易日以上算異常；沒有紀錄不算（還沒跑過）
    stale = alerts and len(trading_days(alerts.date() + timedelta(days=1), days[-1], closed)) >= 2
    if stale:
        lines.insert(0, f"❌ 處置／注意股：最後成功 {alerts.date()}，端點只有近幾日，請盡快執行 collect --catch-up")
    abnormal = sum(ln.startswith("❌") for ln in lines)
    out += ["", *lines] if lines else []
    out.append(f"\n結果：異常 {abnormal} 項" if abnormal else "\n結果：無異常")
    return "\n".join(out), (1 if abnormal else 0)


def run_check(n: int, now: datetime) -> int:
    from . import db
    conn = db.connect()
    try:
        cur = conn.cursor()
        closed = load_closed(cur)
        days = due_days(now, n, closed)
        # 至少載入 MEDIAN_DAYS 個交易日，--days 小於 20 時中位數才有意義
        start = due_days(now, max(n, MEDIAN_DAYS), closed)[0]
        snap, state = load_snapshot(cur, start, days[-1]), load_state(cur)
        adhoc = [r[0] for r in cur.execute("SELECT holiday_date FROM market_holidays WHERE source = 'adhoc' AND holiday_date BETWEEN ? AND ? "
                                           "ORDER BY holiday_date", start, days[-1]).fetchall()]
    finally:
        conn.close()
    text, rc = check_report(days, snap, now, state, closed, adhoc)
    print(text)
    return rc


# ─── 匯出 latest.json 的 status ───────────────────────────
def collected_at(cur, state: dict) -> tuple:
    """(時間字串, 來源)：run = 執行紀錄；db = 尚無紀錄，退回日線最後寫入時間（換算成台灣時間）。"""
    if state["collected_at"]:
        return state["collected_at"].isoformat(timespec="seconds") + "+08:00", "run"
    t = cur.execute("SELECT DATEADD(hour, 8 - DATEDIFF(hour, GETUTCDATE(), GETDATE()), MAX(created_at)) FROM daily_prices").fetchone()[0]
    return (t.isoformat(timespec="seconds") + "+08:00", "db") if t else (None, "db")


def dataset_status(snap: dict, data_date: date, now: datetime) -> list:
    """以「資料日」為基準判斷各資料集（整站落後由橫幅處理）；m 只在異常時有。"""
    med, out = medians(snap), []
    for spec in SPECS:
        rows = snap[spec.key]
        bad = assess(spec, rows.get(data_date, Row()), med[spec.key])
        good = [d for d in sorted(rows) if not assess(spec, rows[d], med[spec.key])]
        last = good[-1] if good else None
        item = {"k": spec.key, "n": spec.label, "d": str(last) if last else None, "s": OK}
        if bad:
            item["s"] = PENDING if data_date == now.date() and now.time() < DEADLINE else ABNORMAL
        if item["s"] == ABNORMAL:
            if bad[0].startswith("fill"):
                item["m"] = f"{spec.label} {data_date:%m/%d} {bad[1].split('（')[0]}"
            else:
                item["m"] = f"{spec.label}停在 {last:%m/%d}" if last else f"{spec.label}近期資料不足"
        out.append(item)
    return out


def build_status(cur, data_date: date, now: datetime) -> dict:
    closed, state = load_closed(cur), load_state(cur)
    at, src = collected_at(cur, state)
    snap = load_snapshot(cur, data_date - timedelta(days=45), data_date)
    return {"collected_at": at, "collected_src": src, "exported_at": now.isoformat(timespec="seconds"),
            "datasets": dataset_status(snap, data_date, now),
            # 判斷「最新交易日」用：只列平日；往回 45 天夠找到上一個交易日
            "closed": sorted(str(d) for d in closed if d.weekday() < 5 and d >= data_date - timedelta(days=45))}
```

### `twstock/collectors/catchup.py`（新檔）

```python
"""
collect --catch-up：找出最近 N 個交易日各資料集缺什麼，只補缺的，可一天重複執行。
collect --date：指定日期全部重抓（MERGE 覆寫），與 catch-up 共用同一個執行流程。

流程：取得鎖 → 更新日曆 → 規劃（純函式 make_plan）→ 依序抓取 → 重新讀資料庫判斷狀態 → 需要時匯出 → 寫紀錄 → 通知。
結束代碼：0 = 齊全、尚未公布、休市或另一個程序正在執行；1 = 有異常；2 = 連不上資料庫。
"""
import json
import time
from datetime import date, datetime, timedelta

import pyodbc

from .. import db, fetch, health
from ..config import DB_CONFIG, SITE_DATA_DIR, tw_now
from ..fetch import FetchError
from ..health import Row, due_days, evaluate, load_snapshot, load_state, medians, missing_keys
from ..tradingcal import (add_adhoc, is_adhoc_closure, is_trading_day, load_closed, remove_adhoc, trading_days,
                          update_calendar, warn_uncovered)
from .alerts import collect_alerts
from .chains import chains_age_days, update_chains
from .daily import DAY_KEYS, PARSE_ERRORS, collect_for_date, collect_tpex_index
from .events import LOOKBACK_DAYS, collect_events
from .futures import collect_futures, collect_futures_institutional
from .industry import update_industry
from .revenue import collect_monthly_revenue, revenue_month_for

DEFAULT_DAYS, MAX_DAYS = 10, 30
CHAINS_REFRESH_DAYS = 30
DB_RETRY_SECONDS = 60       # 開機登入時 Docker 可能還沒起來，等一下再試一次
REVENUE_DONE_RATIO = 0.98   # 該月筆數 ≥ 前一月 × 98% 視為公布完成


def month_key(d: date) -> tuple:
    return d.year, d.month


def make_plan(now: datetime, n: int, snap: dict, state: dict, closed: set, revenue_counts=None) -> dict:
    """
    純函式：輸入現在時間、資料現況、執行紀錄、日曆；輸出待抓清單（不連網、不連資料庫）。
    days：評估範圍；by_date：[(日期, 鍵)]；tpex_months；futures、futures_oi：(起, 迄)；alerts：bool；
    events：(起, 迄)；revenue：[(年, 月)]。
    """
    days = due_days(now, n, closed)
    plan = {"days": days, "by_date": [], "tpex_months": [], "futures": None, "futures_oi": None,
            "alerts": False, "events": None, "revenue": []}
    if not days:
        return plan
    med = medians(snap)
    for d in days:
        keys = missing_keys(d, DAY_KEYS, snap, med)
        if keys:
            plan["by_date"].append((d, keys))
    plan["tpex_months"] = sorted({month_key(d) for d in days if missing_keys(d, ("index.TPEX",), snap, med)})
    for key in ("futures", "futures_oi"):
        gap = [d for d in days if missing_keys(d, (key,), snap, med)]
        if gap:
            plan[key] = (gap[0], gap[-1])

    # 沒有日期的資料：以「最後一個應有資料的交易日」為基準
    anchor = days[-1]
    settled = datetime.combine(anchor, health.ALERTS_SETTLED)
    first = datetime.combine(anchor, health.COLLECT_FROM)
    need_after = settled if now.replace(tzinfo=None) >= settled else first
    plan["alerts"] = state["alerts_at"] is None or state["alerts_at"].replace(tzinfo=None) < need_after
    if state["events_to"] is None or state["events_to"] < anchor:
        oldest = plan["by_date"][0][0] if plan["by_date"] else anchor
        since = min(oldest, state["events_to"] or anchor)
        plan["events"] = (since - timedelta(days=LOOKBACK_DAYS), anchor)
    if state["revenue_on"] != now.date() and revenue_counts is not None:
        for y, m in sorted({x for x in map(revenue_month_for, days) if x}):
            prev = (y - 1, 12) if m == 1 else (y, m - 1)
            if revenue_counts.get((y, m), 0) < revenue_counts.get(prev, 0) * REVENUE_DONE_RATIO or not revenue_counts.get((y, m)):
                plan["revenue"].append((y, m))
    return plan


def plan_for_date(d: date, now: datetime, closed_by_calendar: bool) -> dict:
    """collect --date：該日全部重抓；行事曆上的休市日只處理沒有日期的資料。"""
    plan = {"days": [] if closed_by_calendar else [d], "by_date": [] if closed_by_calendar else [(d, DAY_KEYS)],
            "tpex_months": [] if closed_by_calendar else [month_key(d)],
            "futures": None if closed_by_calendar else (d, d), "futures_oi": None if closed_by_calendar else (d, d),
            "alerts": not closed_by_calendar, "events": None if closed_by_calendar else (d - timedelta(days=LOOKBACK_DAYS), d),
            "revenue": []}
    month = revenue_month_for(d)
    if month and not closed_by_calendar:
        plan["revenue"] = [month]
    return plan


def plan_is_empty(plan: dict) -> bool:
    return not (plan["by_date"] or plan["tpex_months"] or plan["futures"] or plan["futures_oi"]
                or plan["alerts"] or plan["events"] or plan["revenue"])


def _guard(key, errors, fn, *args):
    """跑一個資料集；抓取失敗或欄位不符只記錄，不影響其他資料集。回傳 True = 成功。"""
    try:
        fn(*args)
        return True
    except (FetchError, RuntimeError, *PARSE_ERRORS) as e:     # RuntimeError：update_chains 解析不到產業鏈
        errors[key] = e
        print(f"  ⚠️  {key} 失敗：{e}")
        return False


def execute_plan(plan: dict, now: datetime, no_revenue=False) -> tuple:
    """依序抓取；回傳 (written, errors, undated)。written = {鍵: {日期字串: 筆數}}。"""
    written, errors, undated = {}, {}, {}
    wrote_prices = False
    for d, keys in plan["by_date"]:
        w, e = collect_for_date(d, keys)
        for k, v in w.items():
            written.setdefault(k, {})[str(d)] = v
        errors.update({(k, d): x for k, x in e.items()})
        wrote_prices = wrote_prices or any(k.startswith("prices.") and v for k, v in w.items())
    if plan["futures"]:
        _guard("futures", errors, collect_futures, *plan["futures"])
    if plan["futures_oi"]:
        _guard("futures_oi", errors, collect_futures_institutional, *plan["futures_oi"])
    for y, m in plan["tpex_months"]:
        _guard("index.TPEX", errors, collect_tpex_index, y, m)
    if plan["alerts"] and _guard("alerts", errors, collect_alerts):
        undated["alerts"] = now.isoformat(timespec="seconds")
    if plan["events"] and _guard("events", errors, collect_events, *plan["events"]):
        undated["events_to"] = str(plan["events"][1])
    if plan["revenue"] and not no_revenue:
        if all([_guard("revenue", errors, collect_monthly_revenue, y, m) for y, m in plan["revenue"]]):
            undated["revenue"] = str(now.date())
    if wrote_prices:        # 新股票要有產業別；產業鏈 30 天更新一次
        _guard("industry", errors, update_industry)
        age = chains_age_days()
        if age is None or age >= CHAINS_REFRESH_DAYS:
            _guard("chains", errors, update_chains)
    return written, errors, undated


def _undated_counts(cur) -> tuple:
    return tuple(cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("stock_alerts", "price_events", "monthly_revenue"))


def _revenue_counts(cur) -> dict:
    return {(y, m): n for y, m, n in cur.execute(
        "SELECT revenue_year, revenue_month, COUNT(*) FROM monthly_revenue GROUP BY revenue_year, revenue_month").fetchall()}


def status_changed(status_now: list) -> bool:
    """網站上的 status 與現況不同（例如尚未公布轉異常）時，沒有新資料也要匯出，橫幅才會更新。"""
    try:
        old = json.loads((SITE_DATA_DIR / "latest.json").read_text(encoding="utf-8")).get("status", {}).get("datasets", [])
    except (OSError, ValueError):
        return True
    pick = lambda rows: {x["k"]: (x["s"], x["d"]) for x in rows}
    return pick(old) != pick(status_now)


def _print_summary(items, days):
    last = days[-1] if days else None
    if last:
        print(f"\n📊 收集結果（{last}）")
        for i in items:
            if i.date == last and i.status == health.OK:
                print(f"  ✅ {i.label} {i.n:,} 筆")
    lines = health.problem_lines(items)
    for ln in lines:
        print(f"  {ln}")


def _connect_or_fail(retry: bool):
    try:
        return db.connect()
    except pyodbc.Error:
        if not retry:
            raise
        print(f"⏳ 連不上資料庫，{DB_RETRY_SECONDS} 秒後再試一次")
        time.sleep(DB_RETRY_SECONDS)
        return db.connect()


def _db_failed(e, notify, now) -> int:
    print(f"\n❌ 連不上資料庫（{DB_CONFIG['server']}）或資料表不存在：{str(e).splitlines()[0][:200]}\n"
          "   1. 確認 Docker Desktop 已啟動、資料庫容器已啟動（例如 docker start MySqlServer）\n"
          "   2. 更新程式後請執行一次 python -m twstock setup-db\n"
          "   資料庫恢復後重跑 collect --catch-up 會自動補齊；網站資料沒有變動。")
    if notify:
        health.notify_once({"db": "連不上資料庫，請確認 Docker 與容器已啟動"}, now.date())
    return 2


def run(days=DEFAULT_DAYS, date_=None, no_revenue=False, no_export=False, notify=False, now=None) -> int:
    """collect 的唯一入口：date_ 有值 = collect --date；否則 = catch-up。"""
    from ..export import export_all
    now = now or tw_now()
    try:
        _connect_or_fail(retry=date_ is None).close()
        lock = db.acquire_lock()
    except pyodbc.Error as e:
        return _db_failed(e, notify, now)
    if lock is None:
        print("⏭️  另一個收集程序正在執行，這次略過")
        return 0
    try:
        return _run_locked(days, date_, no_revenue, no_export, notify, now, export_all)
    except pyodbc.Error as e:
        return _db_failed(e, notify, now)
    finally:
        try:
            db.release_lock(lock)
        except pyodbc.Error:
            pass        # 連線已斷：程序結束時鎖會自動釋放


def _run_locked(days, date_, no_revenue, no_export, notify, now, export_all) -> int:
    t0, n0 = now, fetch.request_count()
    update_calendar(now)
    conn = db.connect()
    try:
        cur = conn.cursor()
        closed = load_closed(cur)
        warn_uncovered(closed, now)
        state = load_state(cur)
        # 中位數需要 20 個交易日
        base = due_days(now, max(days, health.MEDIAN_DAYS), closed)[0]
        end = date_ or now.date()
        start = min(base, (date_ or base) - timedelta(days=45))
        before = load_snapshot(cur, start, end)
        undated_before = _undated_counts(cur)
        adhoc_dates = {r[0] for r in cur.execute("SELECT holiday_date FROM market_holidays WHERE source = 'adhoc'").fetchall()}
        latest_price = cur.execute("SELECT MAX(trade_date) FROM daily_prices").fetchone()[0]
        if not date_ and not is_trading_day(now.date(), closed):
            print(f"ℹ️  今天 {now.date()} 休市")
        if date_:
            closed_for_run = closed - adhoc_dates       # 復原錯判：--date 可以重新查臨時休市日
            is_closed = not is_trading_day(date_, closed_for_run)
            if is_closed:
                print(f"ℹ️  {date_} 休市，不發行情請求")
            plan = plan_for_date(date_, now, is_closed)
        else:
            plan = make_plan(now, days, before, state, closed, _revenue_counts(cur))
    finally:
        conn.close()

    gap_hint = None
    if not date_ and plan["days"] and latest_price and latest_price < plan["days"][0]:
        between = trading_days(latest_price + timedelta(days=1), plan["days"][0] - timedelta(days=1), closed)
        if between:
            gap_hint = between[0]

    if plan_is_empty(plan):
        print(f"✅ 最近 {len(plan['days'])} 個交易日資料齊全，不需要請求")
        written, errors, undated = {}, {}, {}
    else:
        written, errors, undated = execute_plan(plan, now, no_revenue)

    conn = db.connect()
    try:
        cur = conn.cursor()
        after = load_snapshot(cur, start, end)
        # 臨時休市判定（不含 collect --date：明確指定日期時由使用者判斷）
        day_list = list(plan["days"])
        if not date_:
            for d in list(day_list):
                failed = any(k in errors or (k, d) in errors for k in ("prices.TWSE", "prices.TPEx", "futures"))
                n = [after[k].get(d, Row()).n for k in ("prices.TWSE", "prices.TPEx", "futures")]
                if is_adhoc_closure(d, now.date(), *n, failed):
                    add_adhoc(cur, d, now)
                    day_list.remove(d)
                    print(f"  🌀 {d} 上市、上櫃、期交所都沒有資料，判定為臨時休市")
        elif date_ in adhoc_dates and after["prices.TWSE"].get(date_, Row()).n:
            remove_adhoc(cur, date_)
            print(f"  ↩️  {date_} 有資料，移除臨時休市判定")
        conn.commit()
        changed = any(before[k] != after[k] for k in before) or _undated_counts(cur) != undated_before
        items = evaluate(day_list, after, now, errors)
        result = health.outcome(items)
        undated_errors = [k for k in errors if k in ("alerts", "events", "revenue", "industry", "chains")]
        if undated_errors:
            result = health.ABNORMAL
    finally:
        conn.close()

    _print_summary(items, day_list)
    for k in undated_errors:
        print(f"  ❌ {k}：{errors[k]}")
    if gap_hint:
        result = health.ABNORMAL
        print(f"  ❌ 資料缺口超過 {days} 個交易日。請補抓：python -m twstock history --start {gap_hint} --end {plan['days'][0]}")

    export_seconds, export_failed = None, False
    data_date = max((d for d, r in after["prices.TWSE"].items() if r.n), default=None)
    need_export = not no_export and (date_ is not None or changed or
                                     (data_date is not None and status_changed(health.dataset_status(after, data_date, now))))
    if need_export:
        try:
            export_seconds = round(export_all(), 1)
        except (Exception, SystemExit) as e:
            export_failed = True
            result = health.ABNORMAL
            print(f"  ❌ 匯出失敗：{e}")
    elif not no_export:
        print("ℹ️  沒有新資料，不匯出")

    finished = tw_now()
    detail = {"written": written, "undated": undated, "errors": {str(k): str(v) for k, v in errors.items()},
              "items": [{"k": i.key, "d": str(i.date), "s": i.status, "n": i.n, "m": i.reason[1]} for i in items if i.status != health.OK]}
    conn = db.connect()
    try:
        cur = conn.cursor()
        health.write_run(cur, "date" if date_ else "catch-up", t0, finished, result, changed, fetch.request_count() - n0, export_seconds, detail)
        conn.commit()
    finally:
        conn.close()
    if notify and result == health.ABNORMAL:
        problems = {f"{i.key}:{i.date}": f"{i.label} {i.date:%m/%d} {i.reason[1]}" for i in items if i.status == health.ABNORMAL}
        problems.update({k: f"{k} 失敗" for k in undated_errors})
        if export_failed:
            problems["export"] = "網站資料匯出失敗"
        if gap_hint:
            problems["gap"] = "資料缺口過大，需要 history 補抓"
        health.notify_once(problems, now.date())
    print(f"\n{ {'ok': '✅ 全部齊全', 'pending': '⏳ 部分尚未公布，下次排程會再補', 'abnormal': '❌ 有異常，請看上方訊息'}[result] }")
    return 1 if result == health.ABNORMAL else 0
```

### `twstock/collectors/history.py`（整檔取代）

```python
"""
補抓歷史資料（指定日期範圍）。

資料庫已有的日期會自動跳過，所以中途被封鎖時，稍後用同樣的指令重跑即可接續；
加 force=True 則已存在的日期也重新抓取並覆寫。
"""
import time
from datetime import date

from .. import db
from ..fetch import FetchError
from ..health import load_snapshot, medians, missing_keys
from ..tradingcal import HOLIDAYS, is_trading_day, load_closed, trading_days  # noqa: F401（沿用的對外名稱）
from .daily import ALL_DATASETS, DATASET_KEYS, INDEX, PRICES, TPEX_INDEX, collect_for_date, collect_tpex_index
from .revenue import collect_monthly_revenue, revenue_month_for

# 依網站節流間隔 + 回應時間的實測值（秒，每個細項）
SECONDS_PER_KEY = {"prices.TWSE": 4, "prices.TPEx": 4, "pe.TWSE": 4, "pe.TPEx": 3.2, "insti.TWSE": 4, "insti.TPEx": 3.2,
                   "index.TAIEX": 4, "amount": 4}
SECONDS_PER_MONTH = 3.2


def load_status(start: date, end: date) -> tuple:
    """(休市日, 現況快照, 中位數)。中位數要有近期資料，快照多載入 45 天之前的範圍也不影響判斷。"""
    conn = db.connect()
    try:
        cur = conn.cursor()
        closed = load_closed(cur)
        snap = load_snapshot(cur, start, end)
        return closed, snap, medians(snap)
    finally:
        conn.close()


def run_history(start: date, end: date, datasets=ALL_DATASETS, force=False,
                revenue=True, delay=0.0) -> bool:
    """回傳 True = 全部完成；False = 中途疑似被封鎖或欄位不符而停止。"""
    closed, snap, med = load_status(start, end)
    days = trading_days(start, end, closed)
    keys = tuple(k for ds in datasets if ds != TPEX_INDEX for k in DATASET_KEYS[ds])
    # 每一天只抓還缺的細項（分市場、看筆數與填充率）；順序照 DATASET_KEYS，行情先於本益比
    todo = [(d, keys if force else missing_keys(d, keys, snap, med)) for d in days]
    todo = [(d, ks) for d, ks in todo if ks]
    months = []
    if TPEX_INDEX in datasets:
        months = sorted({(d.year, d.month) for d in days if force or missing_keys(d, ("index.TPEX",), snap, med)})

    est = (sum(sum(SECONDS_PER_KEY[k] for k in ks) + delay for _, ks in todo) + SECONDS_PER_MONTH * len(months)) / 60
    print(f"📅 補抓範圍：{start} ~ {end}，資料集：{'、'.join(datasets)}")
    print(f"📊 交易日 {len(days)} 天，待抓 {len(todo)} 天；⏱️  預估約 {est:.1f} 分鐘")
    for k in keys:
        n = sum(k in ks for _, ks in todo)
        if n:
            print(f"   {k}：{n} 天")
    if months:
        print(f"   櫃買指數：{len(months)} 個月")

    success, no_data, blocked_at, schema_err = 0, [], None, None
    for i, (d, ks) in enumerate(todo, 1):
        print(f"[{i}/{len(todo)}]", end="")
        written, errors = collect_for_date(d, ks)
        if any(isinstance(e, FetchError) for e in errors.values()):
            # 已退避重試仍失敗 → 幾乎確定被封鎖，繼續打只會延長封鎖時間
            blocked_at = d
            break
        if errors:
            # 欄位不符每天都會失敗：停下來，不要把 242 天的請求都浪費掉
            schema_err = (d, next(iter(errors.values())))
            break
        if any(written.values()):
            success += 1
        else:
            no_data.append(d)
        if delay:
            time.sleep(delay)

    if blocked_at is None and schema_err is None:
        for y, m in months:
            try:
                collect_tpex_index(y, m)
            except FetchError as e:
                print(f"  ❌ {e}")
                blocked_at = date(y, m, 1)
                break

    # 月營收：每個月份只抓一次（每市場 1 個請求）
    revenue_months = sorted({m for m in map(revenue_month_for, days) if m})
    if revenue and PRICES in datasets and revenue_months and blocked_at is None and schema_err is None:
        print(f"\n💰 月營收：{len(revenue_months)} 個月份")
        for y, m in revenue_months:
            try:
                collect_monthly_revenue(y, m, force=force)
            except FetchError as e:
                print(f"  ❌ {e}")
                blocked_at = end
                break

    print(f"\n{'=' * 50}\n✅ 成功：{success} 天")
    if no_data:
        print(f"ℹ️  無資料（未列入休市表的休市日或尚未公布）：{', '.join(map(str, no_data))}")
    if schema_err:
        print(f"❌ 在 {schema_err[0]} 停止：官方欄位不符（{schema_err[1]}），需要修改程式")
        return False
    if blocked_at:
        print(f"❌ 在 {blocked_at} 停止：疑似被限流封鎖\n"
              "   建議等 30 分鐘以上，再用同樣的指令重跑；已寫入的日期會自動跳過。")
        return False
    print("🎉 補抓完成！")
    return True
```

### `twstock/collectors/daily.py`

```diff
--- twstock/collectors/daily.py
+++ twstock/collectors/daily.py
@@ -7,16 +7,19 @@
 from datetime import date
 
 from .. import db
-from ..fetch import FetchError, clean_number, is_valid_stock_code, request
+from ..fetch import FetchError, SchemaError, clean_number, is_valid_stock_code, request
 
 TWSE = "https://www.twse.com.tw/rwd/zh"
 TPEX = "https://www.tpex.org.tw/www/zh-tw"
-TPEX_OPENAPI = "https://www.tpex.org.tw/openapi/v1"
 
-# collect_for_date 的資料集名稱；INDEX 只在補抓加權指數時單獨指定（抓 PRICES 時會一併寫入）；
-# AMOUNT 只在補抓或 collect 單獨呼叫時指定
-PRICES, INSTI, INDEX, AMOUNT = "prices", "insti", "index", "amount"
-ALL_DATASETS = (PRICES, INSTI)
+# history --only 的資料集名稱；INDEX = 加權指數（抓行情時會一併寫入），TPEX_INDEX = 櫃買指數（月查詢）
+PRICES, PE, INSTI, INDEX, AMOUNT, TPEX_INDEX = "prices", "pe", "insti", "index", "amount", "tpex_index"
+ALL_DATASETS = (PRICES, PE, INSTI)
+# 每個資料集對應的細項（分市場），也是 collect_for_date 與 health.SPECS 共用的鍵；順序：行情先於本益比、法人
+DATASET_KEYS = {PRICES: ("prices.TWSE", "prices.TPEx"), PE: ("pe.TWSE", "pe.TPEx"),
+                INSTI: ("insti.TWSE", "insti.TPEx"), INDEX: ("index.TAIEX",), AMOUNT: ("amount",)}
+DAY_KEYS = ("prices.TWSE", "prices.TPEx", "index.TAIEX", "pe.TWSE", "pe.TPEx", "insti.TWSE", "insti.TPEx", "amount")
+PARSE_ERRORS = (SchemaError, KeyError, IndexError, TypeError, ValueError, AttributeError)
 
 
 # ─── 上市 ─────────────────────────────────────────────────
@@ -77,7 +80,7 @@
                 "change":      change,
             })
         return results, taiex
-    return [], taiex
+    raise SchemaError("MI_INDEX 找不到含「證券代號」的個股表")
 
 
 def fetch_twse_pe(d: date) -> dict:
@@ -124,7 +127,8 @@
 
 
 def fetch_tpex_daily(d: date) -> list:
-    for table in _tpex_tables("afterTrading/dailyQuotes", d):
+    tables = _tpex_tables("afterTrading/dailyQuotes", d)
+    for table in tables:
         idx = {f: i for i, f in enumerate(table["fields"])}
         if "代號" not in idx:
             continue
@@ -139,42 +143,61 @@
             "trade_value": clean_number(row[idx["成交金額(元)"]], int),
             "trade_count": clean_number(row[idx["成交筆數"]], int),
         } for row in table["data"] if is_valid_stock_code(str(row[idx["代號"]]))]
+    if tables:
+        raise SchemaError("dailyQuotes 找不到含「代號」的行情表")
     return []
 
 
-def fetch_tpex_index() -> list:
-    """櫃買指數：OpenAPI 只提供本月每日開高低收（Date 為西元 YYYYMMDD）。"""
-    data = request("GET", f"{TPEX_OPENAPI}/tpex_index")
-    if not isinstance(data, list):
-        raise FetchError("櫃買指數回應格式不符")
-    rows = []
-    for r in data:
-        ds, close = str(r.get("Date") or ""), clean_number(r.get("Close"))
-        if close is None or not (ds.isdigit() and len(ds) == 8):
+def parse_tpex_index(tables: list) -> list:
+    """櫃買指數月查詢（日期為西元 2026/10/30，漲跌本身帶正負號）→ 寫入用 dict。"""
+    need = ("日期", "開市", "最高", "最低", "收市", "漲/跌")
+    for table in tables:
+        idx = {f: i for i, f in enumerate(table["fields"])}
+        if not set(need) <= idx.keys():
             continue
-        rows.append({"index_code": "TPEX", "trade_date": f"{ds[:4]}-{ds[4:6]}-{ds[6:]}",
-                     "open_price": clean_number(r.get("Open")), "high_price": clean_number(r.get("High")),
-                     "low_price": clean_number(r.get("Low")), "close_price": close,
-                     "change": clean_number(r.get("Change"))})
-    return rows
+        rows = []
+        for r in table["data"]:
+            close = clean_number(r[idx["收市"]])
+            if close is not None:
+                rows.append({"index_code": "TPEX", "trade_date": str(r[idx["日期"]]).strip().replace("/", "-"),
+                             "open_price": clean_number(r[idx["開市"]]), "high_price": clean_number(r[idx["最高"]]),
+                             "low_price": clean_number(r[idx["最低"]]), "close_price": close,
+                             "change": clean_number(r[idx["漲/跌"]])})
+        return rows
+    if tables:
+        raise SchemaError("indexInfo/inx 欄位不符：" + "、".join(map(str, tables[0]["fields"])))
+    return []
 
 
-def fetch_tpex_pe(d: date) -> dict:
-    for table in _tpex_tables("afterTrading/peQryDate", d):
+def fetch_tpex_index(year: int, month: int) -> list:
+    """櫃買指數：可查歷史，一次一個月（尚未有資料的月份回傳 []）。"""
+    return parse_tpex_index(_tpex_tables("indexInfo/inx", date(year, month, 1)))
+
+
+def parse_tpex_pe(tables: list) -> dict:
+    """櫃買本益比表 → {代號: {pe_ratio, pb_ratio, dividend_yield}}。有資料但欄位不符丟 SchemaError；空表回傳 {}。"""
+    need = ("股票代號", "本益比", "殖利率(%)", "股價淨值比")
+    for table in tables:
         idx = {f: i for i, f in enumerate(table["fields"])}
-        if "本益比" not in idx or "代號" not in idx:
+        if not set(need) <= idx.keys():
             continue
         return {
-            str(row[idx["代號"]]).strip(): {
+            str(row[idx["股票代號"]]).strip(): {
                 "pe_ratio":       clean_number(row[idx["本益比"]]),
-                "dividend_yield": clean_number(row[idx["殖利率"]]),
+                "dividend_yield": clean_number(row[idx["殖利率(%)"]]),
                 "pb_ratio":       clean_number(row[idx["股價淨值比"]]),
             }
-            for row in table["data"] if is_valid_stock_code(str(row[idx["代號"]]))
+            for row in table["data"] if is_valid_stock_code(str(row[idx["股票代號"]]))
         }
+    if tables:
+        raise SchemaError("peQryDate 欄位不符：" + "、".join(map(str, tables[0]["fields"])))
     return {}
 
 
+def fetch_tpex_pe(d: date) -> dict:
+    return parse_tpex_pe(_tpex_tables("afterTrading/peQryDate", d))
+
+
 def fetch_tpex_insti(d: date) -> dict:
     """
     上櫃三大法人買賣超（股）。欄位名稱重複，依位置取值：
@@ -195,20 +218,24 @@
 
 
 # ─── 批次寫入 ─────────────────────────────────────────────
-def merge_stocks(cursor, rows: list):
-    """rows: [{stock_code, stock_name, market_type}]。新股票新增，既有股票更新名稱與市場別。"""
+def merge_stocks(cursor, rows: list, trade_date: date):
+    """
+    rows: [{stock_code, stock_name, market_type}]。新股票新增；既有股票的名稱與市場別
+    只在 trade_date ≥ 資料庫最新日線日期時更新（補抓舊日期不可蓋掉最新值）。
+    """
+    latest = cursor.execute("SELECT MAX(trade_date) FROM daily_prices").fetchone()[0]
     cursor.execute("""
         MERGE stocks AS t
         USING OPENJSON(?) WITH (
             stock_code NVARCHAR(10), stock_name NVARCHAR(50), market_type NVARCHAR(10)
         ) AS s
         ON t.stock_code = s.stock_code
-        WHEN MATCHED THEN
+        WHEN MATCHED AND ? = 1 THEN
             UPDATE SET stock_name = s.stock_name, market_type = s.market_type, updated_at = GETDATE()
         WHEN NOT MATCHED THEN
             INSERT (stock_code, stock_name, market_type)
             VALUES (s.stock_code, s.stock_name, s.market_type);
-    """, db.to_json(rows))
+    """, db.to_json(rows), 1 if latest is None or trade_date >= latest else 0)
 
 
 def merge_daily_prices(cursor, trade_date, rows: list):
@@ -240,6 +267,7 @@
 
 
 def merge_fundamentals(cursor, trade_date, rows: list):
+    """只寫入當天有行情列的股票（與拆分前相同），所以要先寫行情。"""
     cursor.execute("""
         MERGE stock_fundamentals AS t
         USING (
@@ -250,6 +278,7 @@
                 pb_ratio   DECIMAL(10,2), dividend_yield DECIMAL(10,4)
             ) AS j
             JOIN stocks st ON st.stock_code = j.stock_code
+            JOIN daily_prices dp ON dp.stock_id = st.stock_id AND dp.trade_date = ?
         ) AS s
         ON t.stock_id = s.stock_id AND t.trade_date = ?
         WHEN MATCHED THEN UPDATE SET
@@ -257,7 +286,7 @@
         WHEN NOT MATCHED THEN
             INSERT (stock_id, trade_date, eps, pe_ratio, pb_ratio, dividend_yield)
             VALUES (s.stock_id, ?, s.eps, s.pe_ratio, s.pb_ratio, s.dividend_yield);
-    """, db.to_json(rows), trade_date, trade_date)
+    """, db.to_json(rows), trade_date, trade_date, trade_date)
 
 
 def merge_institutional(cursor, trade_date, rows: list):
@@ -358,95 +387,87 @@
     """, db.to_json(rows))
 
 
-def collect_tpex_index() -> int:
-    """寫入本月全部日期（MERGE，可重複執行）。"""
-    rows = fetch_tpex_index()
+def _save(fn, *args):
+    conn = db.connect()
+    try:
+        fn(conn.cursor(), *args)
+        conn.commit()
+    finally:
+        conn.close()
+
+
+def collect_tpex_index(year: int, month: int) -> int:
+    """寫入該月全部日期（MERGE，可重複執行）。"""
+    rows = fetch_tpex_index(year, month)
     if rows:
-        conn = db.connect()
-        try:
-            merge_market_index(conn.cursor(), rows)
-            conn.commit()
-        finally:
-            conn.close()
-    print(f"  📈 櫃買指數：{len(rows)} 天")
+        _save(merge_market_index, rows)
+    print(f"  📈 櫃買指數 {year}/{month:02d}：{len(rows)} 天")
     return len(rows)
 
 
 # ─── 單日收集 ─────────────────────────────────────────────
-def collect_for_date(d: date, datasets=ALL_DATASETS) -> bool:
-    """
-    收集單日資料。回傳 True = 已寫入；False = 休市或尚未公布。
-    抓取失敗丟 FetchError，且不寫入任何該日資料（全部抓完才連資料庫，一次 commit）。
-    """
-    print(f"\n📅 {d}  [{' + '.join(datasets)}]")
-    stocks, prices, funds, insti = {}, {}, {}, {}
-    counts = {}
-    taiex = None
+def _collect_key(key: str, d: date, cache: dict) -> int:
+    """抓取並寫入一個資料集，回傳筆數（0 = 官方尚無資料）。"""
+    dataset, _, market = key.partition(".")
+    if key == "prices.TWSE" or key == "index.TAIEX":
+        if "mi" not in cache:                       # 上市行情與加權指數來自同一個 MI_INDEX 回應
+            cache["mi"] = fetch_twse_daily(d)
+        rows, taiex = cache["mi"]
+        if taiex:
+            _save(merge_market_index, [taiex])
+        elif rows:
+            print("  ⚠️  MI_INDEX 找不到加權指數表")
+        if key == "index.TAIEX":
+            return 1 if taiex else 0
+    elif key == "prices.TPEx":
+        rows = fetch_tpex_daily(d)
+    if dataset == "prices":
+        if rows:
+            stocks = [{"stock_code": r["stock_code"], "stock_name": r["stock_name"], "market_type": market} for r in rows]
+            _save(lambda cur: (merge_stocks(cur, stocks, d), merge_daily_prices(cur, d, rows)))
+        return len(rows)
+    if dataset == "pe":
+        pe = (fetch_twse_pe if market == "TWSE" else fetch_tpex_pe)(d)
+        if pe:
+            _save(merge_fundamentals, d, [{"stock_code": c, **r} for c, r in pe.items()])
+        return len(pe)
+    if dataset == "insti":
+        insti = (fetch_twse_insti if market == "TWSE" else fetch_tpex_insti)(d)
+        if insti:
+            _save(merge_institutional, d, [{"stock_code": c, **r} for c, r in insti.items()])
+        return len(insti)
+    amount = fetch_twse_insti_amount(d)
+    if amount:
+        _save(merge_insti_amount, amount)
+    return len(amount)
 
-    if PRICES in datasets:
-        for market, fetch_q, fetch_pe in (("TWSE", fetch_twse_daily, fetch_twse_pe),
-                                          ("TPEx", fetch_tpex_daily, fetch_tpex_pe)):
-            rows = fetch_q(d)
-            if market == "TWSE":
-                rows, taiex = rows      # 上市行情與加權指數來自同一個 MI_INDEX 回應
-                if rows and taiex is None:
-                    print("  ⚠️  MI_INDEX 找不到加權指數表")
-            if market == "TWSE" and not rows:
-                print("  ℹ️  上市無資料（休市或尚未公布），略過此日")
-                return False
-            pe_map = fetch_pe(d)
-            for item in rows:
-                code = item["stock_code"]
-                stocks[code] = {"stock_code": code, "stock_name": item["stock_name"], "market_type": market}
-                prices[code] = item
-                if pe_map.get(code):
-                    funds[code] = {"stock_code": code, **pe_map[code]}
-            counts[market] = len(rows)
-    elif INDEX in datasets:
-        _, taiex = fetch_twse_daily(d)      # 只補指數：同一個請求，個股列不寫入
-        if taiex is None:
-            print("  ℹ️  無加權指數（休市或尚未公布），略過此日")
-            return False
-    if taiex:
-        counts["加權指數"] = 1
 
-    if INSTI in datasets:
-        for market, fetch in (("TWSE", fetch_twse_insti), ("TPEx", fetch_tpex_insti)):
-            rows = fetch(d)
-            if market == "TWSE" and not rows:
-                print("  ℹ️  上市法人無資料（休市或尚未公布），略過此日")
-                return False
-            for code, r in rows.items():
-                insti[code] = {"stock_code": code, **r}
-            counts[f"法人{market}"] = len(rows)
+def collect_for_date(d: date, keys=DAY_KEYS) -> tuple:
+    """
+    收集單日，各資料集獨立抓取、寫入：一個失敗或未公布不影響其他。
+    回傳 (written, errors)：written = {鍵: 筆數}（0 = 官方尚無資料）；errors = {鍵: 例外}。
+    資料庫錯誤（pyodbc.Error）不攔截，由呼叫端處理。
+    """
+    print(f"\n📅 {d}  [{' + '.join(keys)}]")
+    written, errors, cache = {}, {}, {}
+    for key in keys:
+        dataset, _, market = key.partition(".")
+        if dataset in ("pe", "insti") and written.get(f"prices.{market}") == 0:
+            continue                # 同市場行情還沒有：本益比、法人不可能先有，不發請求
+        if dataset == "pe" and f"prices.{market}" in errors:
+            continue                # 本益比只寫入有行情列的股票
+        try:
+            written[key] = _collect_key(key, d, cache)
+        except (FetchError, *PARSE_ERRORS) as e:
+            errors[key] = e
+            print(f"  ⚠️  {key} 失敗：{e}")
+    done = "、".join(f"{k} {v} 筆" for k, v in written.items() if v)
+    none = "、".join(k for k, v in written.items() if not v)
+    if done:
+        print(f"  ✅ 寫入：{done}")
+    if none:
+        print(f"  ℹ️  官方尚無資料：{none}")
+    return written, errors
 
-    amount = []
-    if AMOUNT in datasets:
-        amount = fetch_twse_insti_amount(d)
-        if amount:
-            counts["法人金額"] = len(amount)
-        elif not (prices or insti or taiex):
-            print("  ℹ️  無三大法人買賣金額（休市或尚未公布），略過此日")
-            return False
 
-    conn = db.connect()
-    try:
-        cursor = conn.cursor()
-        if prices:
-            merge_stocks(cursor, list(stocks.values()))
-            merge_daily_prices(cursor, d, list(prices.values()))
-            merge_fundamentals(cursor, d, list(funds.values()))
-        if insti:
-            merge_institutional(cursor, d, list(insti.values()))
-        if taiex:
-            merge_market_index(cursor, [taiex])
-        if amount:
-            merge_insti_amount(cursor, amount)
-        conn.commit()
-    finally:
-        conn.close()
-    print("  ✅ 寫入：" + "、".join(f"{k} {v} 筆" for k, v in counts.items()))
-    return True
-
-
-__all__ = ["collect_for_date", "FetchError", "PRICES", "INSTI", "ALL_DATASETS"]
+__all__ = ["collect_for_date", "FetchError", "PRICES", "PE", "INSTI", "ALL_DATASETS"]
```

### `twstock/config.py`

```diff
--- twstock/config.py
+++ twstock/config.py
@@ -3,6 +3,7 @@
 所有路徑都以專案根目錄為基準，Mac / Windows 通用。
 """
 import os
+from datetime import datetime, timedelta, timezone
 from pathlib import Path
 
 ROOT = Path(__file__).resolve().parent.parent
@@ -11,8 +12,13 @@
 SITE_DATA_DIR = SITE_DIR / "data"    # export 產生的 JSON
 OUTPUT_DIR = ROOT / "output"         # 其他產出（纏論 SVG 等）
 LOG_DIR = ROOT / "logs"
+TW_TZ = timezone(timedelta(hours=8))   # 台灣沒有日光節約時間；固定位移不需要 tzdata（Windows 沒有內建）
 
 
+def tw_now() -> datetime:
+    return datetime.now(TW_TZ)
+
+
 def _load_env(path: Path):
     """極簡 .env 解析：KEY=VALUE，# 開頭為註解；已存在的環境變數優先。"""
     if not path.exists():
```

### `twstock/fetch.py`

```diff
--- twstock/fetch.py
+++ twstock/fetch.py
@@ -22,6 +22,10 @@
     """抓取失敗（被封鎖、網路錯誤）；與「休市沒資料」區分。"""
 
 
+class SchemaError(Exception):
+    """官方回應有資料，但欄位與預期不符（改版）；只影響該資料集，主機本身沒問題。"""
+
+
 # ─── SSL：證交所/櫃買憑證不符合 Python 3.13 的嚴格檢查 ─────────
 def _build_ssl_context() -> ssl.SSLContext:
     ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
@@ -68,16 +72,26 @@
 DEFAULT_INTERVAL = 3.0
 RETRY_BACKOFF = (30, 60, 120)   # 失敗後依序等待秒數，用完仍失敗就放棄
 _last_request: dict = {}
+_requests = 0                   # 本次執行的請求次數（寫入執行紀錄）
+_dead_hosts: set = set()        # 本次執行已重試用盡的主機，不再請求（避免延長封鎖、每個資料集都等 3.5 分鐘）
 
 
+def request_count() -> int:
+    return _requests
+
+
 def request(method: str, url: str, expect_json: bool = True, **kwargs):
+    global _requests
     host = urlparse(url).hostname
+    if host in _dead_hosts:
+        raise FetchError(f"{host} 本次執行已連續失敗，不再請求")
     last_err = None
     for attempt in range(len(RETRY_BACKOFF) + 1):
         wait = MIN_INTERVAL.get(host, DEFAULT_INTERVAL) - (time.monotonic() - _last_request.get(host, 0))
         if wait > 0:
             time.sleep(wait)
         _last_request[host] = time.monotonic()
+        _requests += 1
         try:
             resp = _SESSION.request(method, url, timeout=30, **kwargs)
             if resp.status_code in (403, 429) or resp.status_code >= 500:
@@ -90,6 +104,7 @@
                 pause = RETRY_BACKOFF[attempt]
                 print(f"  ⏳ {host} 請求失敗（{e}），{pause} 秒後重試 [{attempt + 1}/{len(RETRY_BACKOFF)}]")
                 time.sleep(pause)
+    _dead_hosts.add(host)
     raise FetchError(f"{host} 連續失敗，可能已被封鎖，請稍後再跑：{last_err}")
 
 
```

### `twstock/db.py`

```diff
--- twstock/db.py
+++ twstock/db.py
@@ -31,6 +31,27 @@
     return json.dumps([{k: clean(v) for k, v in r.items()} for r in rows], ensure_ascii=False)
 
 
+def acquire_lock():
+    """
+    防重疊：SQL Server 應用程式鎖（跨平台，程序結束會自動釋放）。
+    取得回傳持有鎖的連線，已被其他程序持有回傳 None。用完要呼叫 release_lock。
+    """
+    conn = connect(autocommit=True)
+    got = conn.cursor().execute(
+        "SET NOCOUNT ON; DECLARE @r INT; EXEC @r = sp_getapplock @Resource=N'twstock_collect', "
+        "@LockMode=N'Exclusive', @LockOwner=N'Session', @LockTimeout=0; SELECT @r").fetchone()[0]
+    if got < 0:
+        conn.close()
+        return None
+    return conn
+
+
+def release_lock(conn):
+    # pyodbc 有連線池，close() 不會真的斷線，鎖要明確釋放
+    conn.cursor().execute("EXEC sp_releaseapplock @Resource=N'twstock_collect', @LockOwner=N'Session'")
+    conn.close()
+
+
 # ─── 資料表 ───────────────────────────────────────────────
 DDL = [
     """
@@ -224,8 +245,33 @@
         net_amount  BIGINT        NULL,
         created_at  DATETIME      NOT NULL DEFAULT GETDATE(),
         CONSTRAINT UQ_insti_amount UNIQUE (trade_date, unit)
+    )
+    """,
+    # 收集執行紀錄（時間為台灣時間，由 Python 傳入；容器的 GETDATE() 是 UTC，不可使用）
+    """
+    IF OBJECT_ID('collect_runs') IS NULL
+    CREATE TABLE collect_runs (
+        run_id         INT IDENTITY(1,1) PRIMARY KEY,
+        command        NVARCHAR(20)  NOT NULL,   -- catch-up / date
+        started_at     DATETIME2(0)  NOT NULL,
+        finished_at    DATETIME2(0)  NOT NULL,
+        outcome        NVARCHAR(10)  NOT NULL CHECK (outcome IN ('ok','pending','abnormal')),
+        new_data       BIT           NOT NULL,   -- 這次有新資料寫入（「更新於」的依據）
+        requests       INT           NULL,       -- 這次對外請求次數
+        export_seconds DECIMAL(7,1)  NULL,       -- 這次完整匯出耗時；沒有匯出為 NULL
+        detail         NVARCHAR(MAX) NOT NULL    -- JSON：written / items / errors / undated
     )
     """,
+    # 休市日：official 官方休市表（每年整批更新）；adhoc 收集時判定的臨時休市（颱風假）
+    """
+    IF OBJECT_ID('market_holidays') IS NULL
+    CREATE TABLE market_holidays (
+        holiday_date DATE          NOT NULL PRIMARY KEY,
+        name         NVARCHAR(100) NOT NULL,
+        source       NVARCHAR(10)  NOT NULL CHECK (source IN ('official','adhoc')),
+        fetched_at   DATETIME2(0)  NOT NULL      -- 台灣時間
+    )
+    """,
     # 索引
     "IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_daily_prices_date') "
     "CREATE INDEX IX_daily_prices_date ON daily_prices(trade_date)",
@@ -256,4 +302,4 @@
     conn.close()
     print("✅ 資料表已確認：stocks、daily_prices、monthly_revenue、stock_fundamentals、"
           "institutional_trades、futures_daily_prices、futures_institutional、industry_chains、"
-          "market_index、stock_alerts、price_events、insti_amount")
+          "market_index、stock_alerts、price_events、insti_amount、collect_runs、market_holidays")
```

### `twstock/collectors/futures.py`

```diff
--- twstock/collectors/futures.py
+++ twstock/collectors/futures.py
@@ -105,6 +105,8 @@
         "queryStartDate": f"{start:%Y/%m/%d}", "queryEndDate": f"{end:%Y/%m/%d}", "commodityId": commodity,
     })
     text = resp.content.decode("cp950", errors="replace")
+    if "futContractsDateView" in text:      # 查無資料（休市、尚未公布）：200 ＋ alert 後導回查詢頁，不是封鎖
+        return []
     if not text.lstrip().startswith(INSTI_HEADER):
         raise FetchError("期交所回傳的不是三大法人 CSV（可能被限流或查詢區間錯誤）")
     rows = []
```

### `twstock/export.py`

```diff
--- twstock/export.py
+++ twstock/export.py
@@ -6,14 +6,18 @@
   stocks/{代號}.json 個股：完整日線、法人買賣超、月營收、本益比、所屬產業鏈
 """
 import json
+import os
+import time
 from bisect import bisect_left
 from collections import defaultdict
-from datetime import date, datetime, timedelta
+from datetime import date, timedelta
+from decimal import ROUND_HALF_UP, Decimal
 
 from . import db
 from .analysis.flow import LONG, group_flows, load_concepts, streak
 from .analysis.forecast import build_forecast, load_oi
-from .config import SITE_DATA_DIR
+from .config import SITE_DATA_DIR, tw_now
+from .health import build_status
 
 REPLAY = 20                    # 泡泡圖回放天數
 FUTURES_DAYS = 500             # 首頁台指期日 K 匯出天數
@@ -27,6 +31,9 @@
 _SRC_RANK = {"TWTAUU": 0, "TWTB8U": 0}   # 同一列有多筆官方事件時優先（恢復買賣參考價已含同日除權）
 CAP_TYPES = ("權", "權息", "減", "面", "調")
 CAP_DAYS = 90
+# 升降單位（一般股票）：(價格上限, 單位)
+_TICKS = ((Decimal(10), Decimal("0.01")), (Decimal(50), Decimal("0.05")), (Decimal(100), Decimal("0.1")),
+          (Decimal(500), Decimal("0.5")), (Decimal(1000), Decimal(1)), (Decimal("Infinity"), Decimal(5)))
 
 
 def _f(v, nd=2):
@@ -35,8 +42,15 @@
 
 def _write(path, obj):
     path.parent.mkdir(parents=True, exist_ok=True)
-    # separators 去掉空白，檔案小約 15%
-    path.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
+    # 先寫暫存檔再取代：匯出途中開網頁、或寫到一半失敗，都不會讀到不完整的 JSON
+    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
+    try:
+        # separators 去掉空白，檔案小約 15%
+        tmp.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
+        os.replace(tmp, path)
+    except BaseException:
+        tmp.unlink(missing_ok=True)
+        raise
 
 
 def _pct(close, change):
@@ -118,6 +132,13 @@
     return af
 
 
+def _tick_round(price: float) -> float:
+    """參考價依升降單位四捨五入（half-up）：官方漲跌相對取整後的開盤參考價。升降單位由取整前的價格決定。"""
+    p = Decimal(str(price))
+    tick = next(t for limit, t in _TICKS if p < limit)
+    return float((p / tick).quantize(Decimal(1), rounding=ROUND_HALF_UP) * tick)
+
+
 def _changes(d_, c, ch, market, ev):
     """
     每日漲跌（P14）。回傳 (chs, rel, miss)：
@@ -134,7 +155,7 @@
         if c[i] is not None:
             e = next((at[k] for k in range(i, -1 if j is None else j, -1) if k in at), None)
             if e is not None:
-                x = round(float(c[i]) - e["r"], 2)
+                x = round(float(c[i]) - _tick_round(e["r"]), 2)
             elif market == "TWSE" and j is not None and j != i - 1:
                 x, r = round(float(c[i]) - float(c[j]), 2), d_[j]
             else:
@@ -237,7 +258,10 @@
             **{k: [round(oi[x][k]) for x in recent] for k in ("foreign", "trust", "dealer")}}
 
 
-def export_all():
+def export_all() -> float:
+    """回傳完整匯出耗時（秒）。"""
+    t0 = time.monotonic()
+    now = tw_now()
     conn = db.connect()
     cur = conn.cursor()
 
@@ -307,6 +331,7 @@
         FROM price_events e JOIN stocks s ON s.stock_id = e.stock_id
         ORDER BY s.stock_code, e.event_date"""):
         events[code].append({"d": d, "t": t, "p": float(p), "r": float(r), "src": src})
+    status = build_status(cur, latest_date, now)
     conn.close()
 
     concepts = load_concepts()
@@ -364,7 +389,7 @@
             net = (total[i] or 0) * close / YI if close else 0.0
             if day in window:
                 daily.setdefault(code, {})[day] = {
-                    "net": net, "turnover": (tv[i] or 0) / YI, "pct": _pct(c[i], ch[i])}
+                    "net": net, "turnover": (tv[i] or 0) / YI, "pct": _pct(c[i], chs[i])}
             net_value.append(net)
             for arr, src in ((f_value, fn), (t_value, tn), (d_value, dn)):
                 arr.append((src[i] or 0) * close / YI if close else 0.0)
@@ -428,7 +453,8 @@
 
     replay_dates = [str(d) for d in dates[-REPLAY:]]
     latest = {
-        "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
+        "updated_at": status["collected_at"],     # 最後成功收集時間，不是匯出時間
+        "status": status,
         "date": str(latest_date),
         "flow_date": str(dates[-1]),
         "dates": replay_dates,
@@ -467,3 +493,6 @@
           f"latest.json {size:.0f} KB")
     if str(dates[-1]) != str(latest_date):
         print(f"⚠️  法人資料只到 {dates[-1]}，資金流以該日為準")
+    seconds = time.monotonic() - t0
+    print(f"⏱️  匯出耗時 {seconds:.1f} 秒")
+    return seconds
```

### `twstock/__main__.py`

```diff
--- twstock/__main__.py
+++ twstock/__main__.py
@@ -2,9 +2,13 @@
 台股資料收集與網站產生工具（Mac / Windows 通用）
 
   python -m twstock setup-db                         建立資料庫與資料表
-  python -m twstock collect [--date 2026-10-28]      收集單日（行情、本益比、法人、月營收、指數、台指期、處置／注意股、除權息事件、三大法人金額）並匯出網站資料
-  python -m twstock history --start 2026-01-01       補抓歷史（已有的日期自動跳過）
+  python -m twstock collect [--date 2026-10-28]      收集單日（全部重抓覆寫：行情、本益比、法人、月營收、指數、台指期、處置／注意股、除權息事件、三大法人金額）並匯出網站資料
+  python -m twstock collect --catch-up [--days 10]   補齊最近 N 個交易日缺的資料（各資料集獨立判斷，可重複執行），有新資料才匯出；排程用這個
+  python -m twstock check [--days 20]                檢查各資料集的完整性（唯讀、不連外）；有異常回傳 1
+  python -m twstock history --start 2026-01-01       補抓歷史（只補缺的，可中斷重跑）
+  python -m twstock history --start 2025-10-30 --only pe      只補本益比／淨值比／殖利率
   python -m twstock history --start 2026-02-23 --only index   只補加權指數歷史
+  python -m twstock history --start 2025-10-30 --only tpex_index  只補櫃買指數（一個月一個請求）
   python -m twstock history --start 2026-07-31 --only amount  只補上市三大法人買賣金額
   python -m twstock revenue --year 2026 --month 9    收集指定月份營收
   python -m twstock events --start 2025-10-30        補抓除權息／減資／面額變更事件（還原價格用）
@@ -16,9 +20,11 @@
 """
 import argparse
 import sys
-from datetime import date, datetime, timedelta
+from datetime import date, datetime
 
+from .config import tw_now
 
+
 def _utf8_console():
     # Windows 主控台或排程把輸出導向檔案時預設 cp950，印出 emoji 會 UnicodeEncodeError
     for stream in (sys.stdout, sys.stderr):
@@ -37,74 +43,44 @@
     setup_database()
 
 
-CHAINS_REFRESH_DAYS = 30
-
-
 def cmd_collect(args):
-    from .collectors.chains import chains_age_days, update_chains
-    from .collectors.alerts import collect_alerts
-    from .collectors.daily import AMOUNT, collect_for_date, collect_tpex_index
-    from .collectors.events import LOOKBACK_DAYS, collect_events
-    from .collectors.futures import collect_futures, collect_futures_institutional
-    from .collectors.industry import update_industry
-    from .collectors.revenue import collect_monthly_revenue, revenue_month_for
-    from .fetch import FetchError
+    from .collectors.catchup import DEFAULT_DAYS, MAX_DAYS, run
+    if args.days is not None and not args.catch_up:
+        print("❌ --days 只能和 --catch-up 一起用")
+        return 1
+    days = DEFAULT_DAYS if args.days is None else args.days
+    if not 1 <= days <= MAX_DAYS:
+        print(f"❌ --days 上限 {MAX_DAYS}（更早的缺口請用 python -m twstock history）")
+        return 1
+    # 不帶參數 = 今天（台灣時間）
+    date_ = None if args.catch_up else args.date or tw_now().date()
+    return run(days=days, date_=date_, no_revenue=args.no_revenue, no_export=args.no_export, notify=args.notify)
 
-    d = args.date or date.today()
+
+def cmd_check(args):
+    from .health import run_check
+    import pyodbc
     try:
-        traded = collect_for_date(d)
-        if traded:
-            update_industry()
-            month = revenue_month_for(d)
-            if month and not args.no_revenue:
-                print(f"  💰 月營收 {month[0]}/{month[1]:02d}")
-                try:
-                    collect_monthly_revenue(*month)
-                except FetchError as e:
-                    print(f"  ⚠️  月營收抓取失敗，下次執行會再補：{e}")
-            # 期貨與產業鏈失敗不影響當日股票資料，下次執行會再補
-            try:
-                collect_futures(d)
-                collect_futures_institutional(d)
-            except FetchError as e:
-                print(f"  ⚠️  台指期抓取失敗：{e}")
-            try:
-                collect_tpex_index()
-            except FetchError as e:
-                print(f"  ⚠️  櫃買指數抓取失敗：{e}")
-            try:
-                collect_alerts()
-            except FetchError as e:
-                print(f"  ⚠️  處置／注意股抓取失敗：{e}")
-            try:
-                collect_for_date(d, (AMOUNT,))
-            except FetchError as e:
-                print(f"  ⚠️  三大法人金額抓取失敗：{e}")
-            try:
-                collect_events(d - timedelta(days=LOOKBACK_DAYS), d)
-            except FetchError as e:
-                print(f"  ⚠️  除權息／減資事件抓取失敗，下次執行會再補：{e}")
-            age = chains_age_days()
-            if age is None or age >= CHAINS_REFRESH_DAYS:
-                try:
-                    update_chains()
-                except (FetchError, RuntimeError) as e:
-                    print(f"  ⚠️  產業鏈更新失敗：{e}")
-    except FetchError as e:
-        print(f"\n❌ {e}")
-        return 1
-    if not args.no_export:
-        from .export import export_all
-        export_all()
-    return 0
+        return run_check(args.days, tw_now())
+    except pyodbc.Error as e:
+        print(f"❌ 連不上資料庫或資料表不存在（請確認 Docker 與容器已啟動，並執行過 setup-db）：{str(e).splitlines()[0][:200]}")
+        return 2
 
 
 def cmd_history(args):
     from .collectors.daily import ALL_DATASETS
     from .collectors.history import run_history
+    from .db import acquire_lock, release_lock
     datasets = tuple(args.only) if args.only else ALL_DATASETS
-    ok = run_history(args.start, args.end or date.today(), datasets=datasets,
-                     force=args.force, revenue=not args.no_revenue, delay=args.delay)
+    lock = acquire_lock()
+    if lock is None:
+        print("⏭️  另一個收集程序正在執行，請稍後再跑（同時跑會超過網站節流）")
+        return 1
+    try:
+        ok = run_history(args.start, args.end or tw_now().date(), datasets=datasets,
+                         force=args.force, revenue=not args.no_revenue, delay=args.delay)
+    finally:
+        release_lock(lock)
     return 0 if ok else 1
 
 
@@ -188,8 +164,12 @@
 
     sub.add_parser("setup-db", help="建立資料庫與資料表").set_defaults(fn=cmd_setup_db)
 
-    s = sub.add_parser("collect", help="收集單日資料並匯出網站 JSON")
-    s.add_argument("--date", type=_date, help="YYYY-MM-DD，預設今天")
+    s = sub.add_parser("collect", help="收集資料並匯出網站 JSON（單日，或 --catch-up 補齊最近的缺口）")
+    g = s.add_mutually_exclusive_group()
+    g.add_argument("--date", type=_date, help="YYYY-MM-DD，預設今天；該日全部重抓覆寫")
+    g.add_argument("--catch-up", action="store_true", help="找出最近 N 個交易日各資料集的缺口，只補缺的；有新資料才匯出")
+    s.add_argument("--days", type=int, help="--catch-up 回溯的交易日數，預設 10，上限 30")
+    s.add_argument("--notify", action="store_true", help="有異常時發 Mac 本機通知（排程用；同一天同一問題只通知一次）")
     s.add_argument("--no-revenue", action="store_true", help="略過月營收")
     s.add_argument("--no-export", action="store_true", help="收集後不匯出網站資料")
     s.set_defaults(fn=cmd_collect)
@@ -197,8 +177,9 @@
     s = sub.add_parser("history", help="補抓歷史資料")
     s.add_argument("--start", type=_date, required=True)
     s.add_argument("--end", type=_date, help="預設今天")
-    s.add_argument("--only", nargs="+", choices=["prices", "insti", "index", "amount"],
-                   help="只抓指定資料集（index = 只補加權指數，amount = 只補上市三大法人買賣金額）")
+    s.add_argument("--only", nargs="+", choices=["prices", "pe", "insti", "index", "amount", "tpex_index"],
+                   help="只抓指定資料集（pe = 本益比／淨值比／殖利率，index = 加權指數，tpex_index = 櫃買指數，"
+                        "amount = 上市三大法人買賣金額）")
     s.add_argument("--force", action="store_true", help="已存在的日期也重抓覆寫")
     s.add_argument("--no-revenue", action="store_true")
     s.add_argument("--delay", type=float, default=0.0, help="每日之間額外暫停秒數")
@@ -215,6 +196,10 @@
     s.add_argument("--end", type=_date, help="預設今天")
     s.set_defaults(fn=cmd_events)
 
+    s = sub.add_parser("check", help="檢查近 N 個交易日各資料集的完整性（唯讀、不連外）；有異常回傳 1")
+    s.add_argument("--days", type=int, default=20, help="預設 20")
+    s.set_defaults(fn=cmd_check)
+
     sub.add_parser("export", help="匯出網站 JSON 到 site/data").set_defaults(fn=cmd_export)
 
     s = sub.add_parser("serve", help="本機預覽網站")
```

### `site/index.html`

```diff
--- site/index.html
+++ site/index.html
@@ -31,6 +31,7 @@
 </header>
 
 <div class="datebar" id="dateBar"></div>
+<div class="fresh" id="freshBar" role="status" hidden></div>
 <main id="view" class="wrap"><div class="loading">載入中…</div></main>
 
 <nav class="bottom" aria-label="主選單">
```

### `site/app.css`

```diff
--- site/app.css
+++ site/app.css
@@ -56,6 +56,10 @@
 .tabs a{padding:6px 12px;border-radius:999px;color:var(--text2)}
 .tabs a.on{background:var(--text);color:var(--bg)}
 .datebar{max-width:1120px;margin:10px auto 0;padding:0 16px;color:var(--text2);font-size:12px}
+.fresh{margin:8px max(16px,calc((100% - 1088px)/2)) 0;padding:8px 12px;border-left:3px solid var(--amber);border-radius:6px;
+  background:color-mix(in srgb,var(--amber) 14%,var(--card));font-size:13px;overflow-wrap:anywhere}
+.fresh div+div{margin-top:4px}
+.fresh button{margin-left:8px;padding:2px 10px;border:1px solid var(--border2);border-radius:999px;background:var(--card);font-size:12px}
 
 /* 手機底部選單 */
 .bottom{display:none;position:fixed;bottom:0;left:0;right:0;z-index:20;background:var(--card);border-top:1px solid var(--border);
```

### `site/app.js`

```diff
--- site/app.js
+++ site/app.js
@@ -633,7 +633,58 @@
   onSeg('rspanSeg', v => { localStore('rspan', null, v); renderWatch(); });
   $('#view').addEventListener('click', onRowClick);
 }
+
+// ─── 資料新鮮度（S4）────────────────────────────────────
+const FRESH_HOUR = 18;              // 交易日 18:00 後才要求有當天資料
+App.now = () => new Date();         // 測試可替換：App.now = () => new Date('2026-11-02T18:30:00+08:00')
+App.checkedAt = 0;
+App.newDate = null;
 
+function twParts(t) {               // 一律換算成台灣時間，不依賴瀏覽器時區
+  const p = Object.fromEntries(new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Taipei', year: 'numeric', month: '2-digit',
+    day: '2-digit', hour: '2-digit', hourCycle: 'h23' }).formatToParts(t).map(x => [x.type, x.value]));
+  return { date: `${p.year}-${p.month}-${p.day}`, hour: Number(p.hour) };
+}
+// 依交易日曆，現在應該有哪一天的資料；closed = 平日休市日（YYYY-MM-DD）
+function expectedDate(t, closed) {
+  const open = d => { const w = new Date(d + 'T00:00:00Z').getUTCDay(); return w > 0 && w < 6 && !closed.has(d); };
+  const prev = d => new Date(Date.parse(d + 'T00:00:00Z') - 864e5).toISOString().slice(0, 10);
+  const { date, hour } = twParts(t);
+  let d = open(date) && hour >= FRESH_HOUR ? date : prev(date);
+  while (!open(d)) d = prev(d);
+  return d;
+}
+function freshLines(L, t) {
+  const st = L.status;
+  if (!st) return [];               // 舊版 latest.json：維持原本的日期列
+  const lines = [], exp = expectedDate(t, new Set(st.closed || []));
+  if (L.date < exp) lines.push(`資料停在 ${md(L.date)}，最新交易日為 ${md(exp)}，可能尚未收集`);
+  const bad = (st.datasets || []).filter(x => x.s === 'abnormal' && x.m).map(x => x.m);
+  if (bad.length) lines.push(`部分資料異常：${bad.slice(0, 3).join('、')}${bad.length > 3 ? ` 等 ${bad.length} 項` : ''}`);
+  return lines;
+}
+function renderStatus() {
+  const L = App.latest, when = (L.updated_at || '').slice(0, 16).replace('T', ' ');
+  $('#dateBar').textContent = `資料日 ${L.date}　法人資料 ${L.flow_date}　更新於 ${when}` +
+    (L.status?.collected_src === 'db' ? '（依資料寫入時間）' : '');
+  const lines = freshLines(L, App.now()).map(x => `<div>${esc(x)}</div>`);
+  if (App.newDate) lines.push(`<div>網站資料已更新（資料日 ${md(App.newDate)}）<button id="reloadBtn">重新整理</button></div>`);
+  const bar = $('#freshBar');
+  bar.innerHTML = lines.join('');
+  bar.hidden = !lines.length;
+  $('#reloadBtn')?.addEventListener('click', () => location.reload());
+}
+// 分頁回到前景：重新判斷新鮮度；latest.json 有變就提示重新整理，不自動跳轉
+async function recheckLatest() {
+  renderStatus();
+  if (Date.now() - App.checkedAt < 60000) return;
+  App.checkedAt = Date.now();
+  let fresh;
+  try { fresh = await getJSON('data/latest.json'); } catch (e) { return; }     // 匯出中或離線：下次再檢查
+  const key = x => [x.date, x.flow_date, x.updated_at].join('|');
+  if (key(fresh) !== key(App.latest)) { App.newDate = fresh.date; renderStatus(); }
+}
+
 // ─── 啟動 ───────────────────────────────────────────────
 async function init() {
   setupSearch();
@@ -643,8 +694,8 @@
     $('#view').innerHTML = '<div class="empty">找不到 data/latest.json，請先執行 <code>python -m twstock export</code></div>';
     return;
   }
-  const L = App.latest;
-  $('#dateBar').innerHTML = `資料日 ${L.date}　法人資料 ${L.flow_date}　更新於 ${L.updated_at.slice(0, 16).replace('T', ' ')}`;
+  renderStatus();
+  document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible') recheckLatest(); });
   window.addEventListener('hashchange', route);
   route();
 }
```

### `site/stock.js`

```diff
--- site/stock.js
+++ site/stock.js
@@ -34,6 +34,8 @@
   const fund = data.fund || {};
   // P16：股本變動事件 90 天內，本益比與殖利率加註
   const cap = data.capchg, capSub = cap ? `${md(cap.d)} ${EV_LABEL[cap.t]}，官方值可能尚未調整` : '';
+  // P9：本益比、殖利率卡的資料日（與 P16 註記並列）；值為空時說明是官方未提供
+  const fundSub = v => [v == null && fund.date ? '官方未提供' : '', fund.date ? '資料 ' + md(fund.date) : '', capSub].filter(Boolean).join('；');
   const watching = App.watch.has(code);
   const fd = md(App.latest.flow_date);
   const hlFrom = s?.hf ?? App.latest.hl_from;          // null → 已滿 52 週
@@ -64,8 +66,8 @@
 
     <section class="sec metrics">
       ${[['開盤', pfmt(P.o[last])], ['最高', pfmt(P.h[last]), 'up'], ['最低', pfmt(P.l[last]), 'dn'], ['昨收', pfmt(prev)],
-         ['成交量', fmt(P.v[last]) + ' 張'], ['本益比', fmt(fund.pe, 2), '', capSub], ['股價淨值比', fmt(fund.pb, 2)],
-         ['殖利率', fund.dy != null ? fmt(fund.dy, 2) + '%' : '--', '', capSub],
+         ['成交量', fmt(P.v[last]) + ' 張'], ['本益比', fmt(fund.pe, 2), '', fundSub(fund.pe)], ['股價淨值比', fmt(fund.pb, 2)],
+         ['殖利率', fund.dy != null ? fmt(fund.dy, 2) + '%' : '--', '', fundSub(fund.dy)],
          [hlFrom ? '區間高' : '52週高', pfmt(s?.h52), '', hlFrom ? hlSub + '，還原' : '還原權值'],
          [hlFrom ? '區間低' : '52週低', pfmt(s?.l52), '', hlFrom ? hlSub + '，還原' : '還原權值'],
          ['法人1日', yi(s?.n1), cls(s?.n1), fd], ['法人5日', yi(s?.n5), cls(s?.n5), '至 ' + fd],
@@ -339,15 +341,15 @@
     chk(dif[i] > dea[i], 'DIF > DEA', 'DIF < DEA');
     chk(hist[i] > hist[i - 1], 'MACD 柱放大', 'MACD 柱縮小');
   }
-  const total = bull.length + bear.length, isBull = bull.length >= bear.length;
+  const total = bull.length + bear.length, lean = bull.length > bear.length ? 'bull' : bull.length < bear.length ? 'bear' : '';
   const tags = `<div>${bull.map(t => `<span class="tag up">${t}</span>`).join('')}${bear.map(t => `<span class="tag dn">${t}</span>`).join('')}</div>`;
   const note = (n < rows.length && n ? `最後一根（${md(rows.at(-1).d)}）無成交，以 ${md(rows[i].d)} 判讀。` : '') +
     '依均線與 MACD 機械判讀（還原價格），僅供參考。';
   $('#sigBox').innerHTML = total < SIG_MIN
     ? `<div class="signal"><div style="font-weight:600;margin-bottom:6px">資料不足，無法判讀</div>${tags}
         <div class="muted small" style="margin-top:8px">${period}只有 ${n} 根 K 棒，有效訊號 ${total} 項（至少需 ${SIG_MIN} 項；MACD 需 ${MACD_MIN} 根以上）。${note}</div></div>`
-    : `<div class="signal ${isBull ? 'bull' : 'bear'}">
-        <div style="font-weight:600;margin-bottom:6px">${isBull ? '偏多' : '偏空'}：${bull.length} 多 ${bear.length} 空</div>
+    : `<div class="signal ${lean}">
+        <div style="font-weight:600;margin-bottom:6px">${{ bull: '偏多', bear: '偏空', '': '中性' }[lean]}：${bull.length} 多 ${bear.length} 空</div>
         ${tags}<div class="muted small" style="margin-top:8px">${note}</div></div>`;
 }
 
```

### `tests/test_iter02.py`

```diff
--- tests/test_iter02.py
+++ tests/test_iter02.py
@@ -123,11 +123,11 @@
     # 事件生效日當天無成交 → 下一個成交日相對參考價（不是相對最後成交）
     chs, rel, _ = _changes((D(7, 1), D(7, 2), D(7, 3)), N(248, None, 239), N(1, 0, 0), "TWSE",
                            [{"i": 1, "d": "2026-07-02", "t": "息", "p": 248.0, "r": 240.82}])
-    assert chs == [1.0, None, -1.82] and rel == [None] * 3
+    assert chs == [1.0, None, -2.0] and rel == [None] * 3
     # 上櫃：除權息日官方漲跌是文字（None）→ 收盤 − 參考價；一般日照官方
     chs, rel, miss = _changes((D(7, 15), D(7, 16), D(7, 17), D(7, 20)), N(677, 623, None, 630),
                               N(2, None, None, 1.5), "TPEx", [{"i": 1, "d": "2026-07-16", "t": "息", "p": 677.0, "r": 651.5}])
-    assert chs == [2.0, -28.5, None, 1.5] and rel == [None] * 4 and miss == []
+    assert chs == [2.0, -29.0, None, 1.5] and rel == [None] * 4 and miss == []
     # 漲跌家數歸類：不比價（None）算平盤
     assert [_side(x) for x in (-0.07, 0.1, 0.0, None)] == ["down", "up", "flat", "flat"]
 
```

### `scripts/mac/install_schedule.sh`（整檔取代）

```bash
#!/bin/bash
# launchd 排程：週一到週五 17:30、19:30、21:45，以及登入時，執行 collect --catch-up
#   bash install_schedule.sh             安裝（安裝當下與之後每次登入都會補跑一次）
#   bash install_schedule.sh --print     只印出 plist 內容，不安裝、不動 launchctl
#   bash install_schedule.sh --uninstall 移除
set -e
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
LABEL=com.twstock.collect
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
PY="$ROOT/.venv/bin/python"; [ -x "$PY" ] || PY="$(command -v python3)"

render_plist() {
  local times="" wd t
  for wd in 1 2 3 4 5; do
    for t in "17 30" "19 30" "21 45"; do
      set -- $t
      times="$times<dict><key>Weekday</key><integer>$wd</integer><key>Hour</key><integer>$1</integer><key>Minute</key><integer>$2</integer></dict>"
    done
  done
  cat <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key><array><string>/usr/bin/caffeinate</string><string>-i</string><string>$PY</string><string>-m</string><string>twstock</string><string>collect</string><string>--catch-up</string><string>--notify</string></array>
  <key>WorkingDirectory</key><string>$ROOT</string>
  <key>StartCalendarInterval</key><array>$times</array>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>$ROOT/logs/collect.log</string>
  <key>StandardErrorPath</key><string>$ROOT/logs/collect.log</string>
  <key>EnvironmentVariables</key><dict><key>PYTHONUNBUFFERED</key><string>1</string></dict>
</dict></plist>
EOF
}

if [ "$1" = "--print" ]; then
  render_plist
  exit 0
fi

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
if [ "$1" = "--uninstall" ]; then
  rm -f "$PLIST"
  echo "✅ 已移除排程"
  exit 0
fi

mkdir -p "$ROOT/logs" "$HOME/Library/LaunchAgents"
render_plist > "$PLIST"
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "✅ 已安裝排程：週一至週五 17:30、19:30、21:45，以及登入時；紀錄寫入 logs/collect.log"
echo "   安裝當下會立刻執行一次（RunAtLoad）。立即再測一次：launchctl kickstart gui/$(id -u)/$LABEL"
```

### `scripts/mac/collect.command`（整檔取代）

```bash
#!/bin/bash
# 雙擊：補齊最近缺的資料（缺什麼補什麼），有新資料才匯出網站 JSON。帶參數時照傳，例如 --date 2026-10-28
cd "$(dirname "$0")/../.."
PY=.venv/bin/python; [ -x "$PY" ] || PY=python3
[ $# -gt 0 ] || set -- --catch-up
"$PY" -m twstock collect "$@"
read -n 1 -s -r -p "按任意鍵關閉…"
```

### `scripts/windows/collect.bat`（整檔取代，CRLF）

```bat
@echo off
chcp 65001 >nul
rem 補齊最近缺的資料（缺什麼補什麼），有新資料才匯出網站 JSON（排程也是呼叫這個檔案）。帶參數時照傳，例如 --date 2026-10-28
cd /d "%~dp0..\.."
set PY=.venv\Scripts\python.exe
if not exist %PY% set PY=python
if not exist logs mkdir logs
set PYTHONUNBUFFERED=1
set ARGS=%*
if "%ARGS%"=="" set ARGS=--catch-up
%PY% -m twstock collect %ARGS% >> logs\collect.log 2>&1
```

### `scripts/windows/install_schedule.bat`（整檔取代，CRLF）

```bat
@echo off
chcp 65001 >nul
rem 安裝工作排程器：週一到週五 17:30、19:30、21:45 執行 collect.bat（解除安裝：加上 /uninstall）
set TASK=TwStockCollect
schtasks /Delete /TN %TASK% /F >nul 2>&1
schtasks /Delete /TN %TASK%1730 /F >nul 2>&1
schtasks /Delete /TN %TASK%1930 /F >nul 2>&1
schtasks /Delete /TN %TASK%2145 /F >nul 2>&1
if /i "%~1"=="/uninstall" (
  echo ✅ 已移除排程
  goto :eof
)
schtasks /Create /TN %TASK%1730 /TR "\"%~dp0collect.bat\"" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 17:30 /F
schtasks /Create /TN %TASK%1930 /TR "\"%~dp0collect.bat\"" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 19:30 /F
schtasks /Create /TN %TASK%2145 /TR "\"%~dp0collect.bat\"" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 21:45 /F
echo ✅ 已安裝排程：週一至週五 17:30、19:30、21:45，紀錄寫入 logs\collect.log
echo    錯過排程要補跑：請在工作排程器勾選各工作的「錯過排程時儘快執行」
echo    立即測試一次：schtasks /Run /TN %TASK%1730
pause
```

---

## 附錄 D：`tests/test_iter03.py`（完整內容）

不連網、不連資料庫、不跳通知、不安裝排程。`python3 tests/test_iter03.py`，預期最後一行 `全部通過`（43 個測試）。

```python
"""
第 03 輪純邏輯測試（不連網、不連資料庫、不跳通知、不安裝排程）：
S1 上櫃本益比解析；S2 完整性判斷、check、通知；S3 --catch-up 全部失敗情境（用假的 HTTP 與資料庫跑真實流程）；
S5 交易日曆與臨時休市；S6 補抓不覆蓋市場別；S7 原子寫入；F1 升降單位取整。

  python3 tests/test_iter03.py      （也相容 pytest）
"""
import contextlib
import io
import json
import re
import sys
import tempfile
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from unittest import mock

import pyodbc

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from twstock import db, export, fetch, health, tradingcal  # noqa: E402
from twstock.collectors import catchup, daily, futures, history  # noqa: E402
from twstock.config import TW_TZ  # noqa: E402
from twstock.fetch import FetchError, SchemaError  # noqa: E402
from twstock.health import Row  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def D(m, d, y=2026):
    return date(y, m, d)


def T(m, d, hh=18, mm=0, y=2026):
    return datetime(y, m, d, hh, mm, tzinfo=TW_TZ)


PE_FIELDS = ["股票代號", "公司名稱", "本益比", "每股股利", "股利年度", "殖利率(%)", "股價淨值比", "財報年/季"]
CLOSED = tradingcal.closed_from_rows([])


# ─── S1：上櫃本益比解析 ───────────────────────────────────
def test_parse_tpex_pe():
    rows = [["5904", "寶雅", "20.14", "22.80000000", 114, "3.51", "9.33", "115Q2"],
            ["3564", "其陽", "87.91", "0.75000000", 114, "0.43", "2.66", "115Q3"],
            ["1240", "茂生農經", "N/A", "0.50000000", 114, "0.93", "1.59", "115Q2"],     # 虧損股本益比 N/A
            ["1259", "安心", "18.25", "1.2", 114, "", "0.75", "115Q2"],                 # 空值
            ["00679B", "債券 ETF", "1", "1", 114, "1", "1", "115Q2"]]                   # 不是一般股票
    r = daily.parse_tpex_pe([{"fields": PE_FIELDS, "data": rows}])
    assert r["5904"] == {"pe_ratio": 20.14, "dividend_yield": 3.51, "pb_ratio": 9.33}
    assert r["3564"]["pe_ratio"] == 87.91
    assert r["1240"]["pe_ratio"] is None and r["1240"]["dividend_yield"] == 0.93
    assert r["1259"]["dividend_yield"] is None and "00679B" not in r
    assert daily.parse_tpex_pe([]) == {}                                            # 休市：表是空的
    renamed = ["股票代號", "本益比", "現金殖利率", "股價淨值比"]
    for fields in (renamed, ["代號", "本益比", "殖利率(%)", "股價淨值比"]):
        try:
            daily.parse_tpex_pe([{"fields": fields, "data": [["5904", "1", "1", "1"]]}])
            assert False, "欄位不符要丟 SchemaError"
        except SchemaError as e:
            assert "peQryDate" in str(e)


def test_parse_tpex_index():
    f = ["日期", "開市", "最高", "最低", "收市", "漲/跌"]
    r = daily.parse_tpex_index([{"fields": f, "data": [["2026/10/29", "396.40", "397.17", "385.26", "387.37", "-7.24"],
                                                       ["2026/10/30", "384.20", "384.20", "365.70", "370.26", "-17.11"],
                                                       ["2026/10/31", "--", "--", "--", "--", "--"]]}])
    assert [x["trade_date"] for x in r] == ["2026-10-29", "2026-10-30"]
    assert r[1] == {"index_code": "TPEX", "trade_date": "2026-10-30", "open_price": 384.2, "high_price": 384.2,
                    "low_price": 365.7, "close_price": 370.26, "change": -17.11}
    assert daily.parse_tpex_index([]) == []
    try:
        daily.parse_tpex_index([{"fields": ["日期", "收盤"], "data": [["2026/10/30", "1"]]}])
        assert False
    except SchemaError:
        pass


# ─── S2：完整性判斷 ───────────────────────────────────────
def test_assess():
    s = health.SPEC["pe.TPEx"]
    assert health.assess(s, Row(892, 680, 892, 892), 888) is None
    assert health.assess(s, Row(0), 888)[0] == "none"
    assert health.assess(s, Row(2, 2, 2, 2), 888)[0] == "count"                     # 10/30 的實際情況
    assert health.assess(s, Row(711, 500, 711, 711), 888) is None                   # 門檻 710.4
    assert health.assess(s, Row(710, 500, 710, 710), 888)[0] == "count"
    assert health.assess(s, Row(600, 500, 600, 600), 0)[0] == "count"               # 沒有中位數時看下限 650
    assert health.assess(s, Row(893, 676, 893, 2), 888)[0] == "fill:殖利率"          # 10/29 的實際情況：只比筆數抓不到
    assert health.assess(s, Row(892, 446, 892, 892), 888) is None                   # 剛好 50%
    assert health.assess(s, Row(892, 445, 892, 892), 888)[0] == "fill:本益比"
    assert health.assess(health.SPEC["prices.TPEx"], Row(895), 889) is None         # 行情沒有填充率檢查


def _full_snapshot(days, skip=()):
    ok = {"prices.TWSE": Row(1086), "prices.TPEx": Row(889), "pe.TWSE": Row(1082, 870, 1082, 1082),
          "pe.TPEx": Row(888, 675, 888, 888), "insti.TWSE": Row(1077), "insti.TPEx": Row(784), "amount": Row(6),
          "index.TAIEX": Row(1), "index.TPEX": Row(1), "futures": Row(6), "futures_oi": Row(9)}
    return {k: {d: v for d in days if (k, d) not in skip} for k, v in ok.items()}


def test_status_boundary():
    days = tradingcal.trading_days(D(10, 1), D(11, 2), CLOSED)
    snap = _full_snapshot(days, skip={("insti.TWSE", D(11, 2))})
    pick = lambda items: [i.status for i in items if i.key == "insti.TWSE" and i.date == D(11, 2)][0]
    assert pick(health.evaluate(days, snap, T(11, 2, 21, 59))) == health.PENDING
    assert pick(health.evaluate(days, snap, T(11, 2, 22, 0))) == health.ABNORMAL
    assert pick(health.evaluate(days, snap, T(11, 3, 9, 0))) == health.ABNORMAL     # 隔日才算異常
    # 抓取失敗不論時間都是異常；範圍查詢失敗（鍵）只影響還缺資料的日期
    assert health.outcome(health.evaluate(days, snap, T(11, 2, 21, 59), {("insti.TWSE", D(11, 2)): FetchError("x")})) == health.ABNORMAL
    assert health.outcome(health.evaluate(days, snap, T(11, 2, 21, 59), {"insti.TWSE": FetchError("x")})) == health.ABNORMAL
    assert health.outcome(health.evaluate(days, snap, T(11, 2, 21, 59), {"futures": FetchError("x")})) == health.PENDING
    assert health.outcome(health.evaluate(days, _full_snapshot(days), T(11, 2, 18))) == health.OK


def test_due_days():
    assert health.due_days(T(11, 2, 14, 59), 1, CLOSED) == [D(10, 30)]              # 15:00 前今天不列入
    assert health.due_days(T(11, 2, 15, 0), 1, CLOSED) == [D(11, 2)]
    assert health.due_days(T(10, 31, 12), 2, CLOSED) == [D(10, 29), D(10, 30)]      # 週六
    assert D(10, 23) not in health.due_days(T(10, 28, 18), 5, CLOSED)               # 臨時休市
    assert D(10, 26) not in health.due_days(T(10, 28, 18), 5, CLOSED)               # 連假補假


def test_check_baseline():
    """用 2026-10-31 資料庫的實際數字重現基線：上櫃本益比 10/30 筆數、殖利率填充率、櫃買指數缺 9/30。"""
    now = T(10, 31, 12, 30)
    days = health.due_days(now, 20, CLOSED)
    assert days[0] == D(9, 30) and days[-1] == D(10, 30) and len(days) == 20
    snap = _full_snapshot(days, skip={("index.TPEX", D(9, 30))})
    snap["pe.TPEx"] = {d: Row(888, 675, 888, 2) for d in days}
    snap["pe.TPEx"][D(10, 30)] = Row(2, 2, 2, 2)
    state = {"alerts_at": None, "events_to": None, "revenue_on": None, "collected_at": None}
    with mock.patch.object(fetch._SESSION, "request") as http, mock.patch.object(db, "connect") as conn:
        text, rc = health.check_report(days, snap, now, state, CLOSED)
    assert rc == 1 and http.call_count == 0 and conn.call_count == 0
    assert "2026-10-30 筆數 2" in text and "殖利率填充率" in text and "櫃買指數：缺 2026-09-30" in text
    assert "異常 3 項" in text and "今天 2026-10-31 休市" in text
    # 回補後
    text, rc = health.check_report(days, _full_snapshot(days), now, state, CLOSED)
    assert rc == 0 and "無異常" in text
    # 休市日（週末、連假、臨時休市）不算缺漏：days 本來就不含
    assert not {D(10, 23), D(10, 24), D(10, 25), D(10, 26)} & set(days)
    # 處置／注意股落後 2 個交易日以上才算異常；沒有紀錄不算
    state2 = dict(state, alerts_at=datetime(2026, 10, 28, 19, 30))
    text, rc = health.check_report(days, _full_snapshot(days), now, state2, CLOSED)
    assert rc == 1 and "處置／注意股" in text
    state3 = dict(state, alerts_at=datetime(2026, 10, 29, 19, 30))
    assert health.check_report(days, _full_snapshot(days), now, state3, CLOSED)[1] == 0


def test_run_check_readonly():
    w = World(D(10, 30))
    runs = list(w.runs)
    buf = io.StringIO()
    with env(w), mock.patch.object(health, "load_snapshot", w.snapshot), contextlib.redirect_stdout(buf):
        rc = health.run_check(20, T(10, 31, 12))
    assert rc == 0 and "無異常" in buf.getvalue()
    assert w.requests == [] and w.merges == [] and w.runs == runs       # 不連外、不寫資料庫


def test_notify_once():
    with tempfile.TemporaryDirectory() as tmp, mock.patch.object(health, "NOTIFY_FILE", Path(tmp) / "n.json"), \
            mock.patch.object(health.subprocess, "run") as run, mock.patch.object(health.sys, "platform", "darwin"):
        assert health.notify_once({}, D(11, 2)) is False and run.call_count == 0       # 正常不通知
        assert health.notify_once({"a": "上櫃本益比 11/02 筆數 2"}, D(11, 2)) is True and run.call_count == 1
        assert health.notify_once({"a": "上櫃本益比 11/02 筆數 2"}, D(11, 2)) is False and run.call_count == 1  # 同日不重複
        assert health.notify_once({"a": "x", "b": "新問題"}, D(11, 2)) is True and run.call_count == 2            # 新問題要通知
        assert "新問題" in run.call_args[0][0][2] and "x" not in run.call_args[0][0][2]
        assert health.notify_once({"a": "x"}, D(11, 3)) is True and run.call_count == 3                          # 隔天再通知
    with tempfile.TemporaryDirectory() as tmp, mock.patch.object(health, "NOTIFY_FILE", Path(tmp) / "n.json"), \
            mock.patch.object(health.subprocess, "run") as run, mock.patch.object(health.sys, "platform", "win32"):
        assert health.notify_once({"a": "x"}, D(11, 2)) is False and run.call_count == 0  # Windows 只寫紀錄


def test_dataset_status():
    days = tradingcal.trading_days(D(10, 1), D(10, 30), CLOSED)
    snap = _full_snapshot(days, skip={("pe.TPEx", D(10, 30))})
    st = {x["k"]: x for x in health.dataset_status(snap, D(10, 30), T(11, 2, 18))}
    assert st["pe.TPEx"]["s"] == "abnormal" and st["pe.TPEx"]["m"] == "上櫃本益比停在 10/29"
    assert st["prices.TWSE"] == {"k": "prices.TWSE", "n": "上市行情", "d": "2026-10-30", "s": "ok"}
    st = {x["k"]: x for x in health.dataset_status(snap, D(10, 30), T(10, 30, 19))}
    assert st["pe.TPEx"]["s"] == "pending" and "m" not in st["pe.TPEx"]             # 當天 22:00 前
    assert len(json.dumps(health.dataset_status(snap, D(10, 30), T(11, 2, 18)), ensure_ascii=False)) < 1500


# ─── S5：交易日曆與臨時休市 ───────────────────────────────
CAL = {"stat": "ok", "fields": ["日期", "名稱", "說明"], "queryYear": 2026, "data": [
    ["2026-01-01", "中華民國開國紀念日", ""], ["2026-01-02", "國曆新年開始交易日", ""],
    ["2026-02-11", "農曆春節前最後交易日", ""], ["2026-02-12", "市場無交易，僅辦理結算交割作業", ""],
    ["2026-02-23", "農曆春節後開始交易日", ""], ["2026-02-28", "和平紀念日", ""]]}


def test_parse_holidays():
    assert tradingcal.parse_holidays(CAL) == [(D(1, 1), "中華民國開國紀念日"), (D(2, 12), "市場無交易，僅辦理結算交割作業"),
                                               (D(2, 28), "和平紀念日")]
    try:
        tradingcal.parse_holidays({"fields": ["date"], "data": []})
        assert False
    except SchemaError:
        pass


def test_trading_days():
    assert len(tradingcal.trading_days(D(10, 30, 2025), D(10, 30))) == 242
    # 有官方資料的年度以官方為準，但手寫的臨時休市仍然有效
    official = [(d, "official") for d in sorted(h for h in tradingcal.HOLIDAYS if h.year == 2026)]
    assert len(tradingcal.trading_days(D(10, 30, 2025), D(10, 30), tradingcal.closed_from_rows(official))) == 242
    closed = tradingcal.closed_from_rows([(D(12, 24), "official")])
    assert not tradingcal.is_trading_day(D(12, 24), closed) and tradingcal.is_trading_day(D(12, 25), closed)
    assert not tradingcal.is_trading_day(D(10, 23), closed)
    # 自動判定的臨時休市
    assert not tradingcal.is_trading_day(D(11, 4), tradingcal.closed_from_rows([(D(11, 4), "adhoc")]))
    # 2027 沒有日曆：平日視為交易日，並印警告
    assert tradingcal.is_trading_day(date(2027, 2, 8), CLOSED)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        tradingcal.warn_uncovered(CLOSED, datetime(2027, 1, 4, 18, tzinfo=TW_TZ))
    assert "2027" in buf.getvalue()


def test_adhoc_closure():
    f = tradingcal.is_adhoc_closure
    assert f(D(10, 23), D(10, 27), 0, 0, 0, False) is True
    assert f(D(10, 23), D(10, 23), 0, 0, 0, False) is False     # 當天不判定
    assert f(D(10, 23), D(10, 27), 0, 0, 6, False) is False     # 期交所有資料
    assert f(D(10, 23), D(10, 27), 0, 880, 0, False) is False   # 上櫃有資料
    assert f(D(10, 23), D(10, 27), 0, 0, 0, True) is False      # 查詢失敗不判定


def test_calendar_due():
    now = T(10, 31, 12)
    assert tradingcal.calendar_due([], now) is True
    assert tradingcal.calendar_due([(D(1, 1), "official", datetime(2026, 10, 20))], now) is False
    assert tradingcal.calendar_due([(D(1, 1), "official", datetime(2026, 9, 20))], now) is True
    assert tradingcal.calendar_due([(D(1, 1), "adhoc", datetime(2026, 10, 20))], now) is True
    assert tradingcal.calendar_due([(D(1, 1), "official", datetime(2026, 10, 20))],
                                   datetime(2027, 1, 4, tzinfo=TW_TZ)) is True    # 新年度


def test_update_calendar():
    now = T(10, 31, 12)
    w = World(D(10, 30))
    w.holidays = []
    buf = io.StringIO()
    with env(w), contextlib.redirect_stdout(buf):
        tradingcal.update_calendar(now)                                 # 缺當年資料：1 個請求
        assert w.paths() == ["/rwd/zh/holidaySchedule/holidaySchedule"] and "官方休市表" in buf.getvalue()
        assert [(d, s) for d, s, _ in w.holidays] == [(D(1, 1), "official"), (D(2, 12), "official"), (D(2, 28), "official")]
        tradingcal.update_calendar(now)                                 # 同一年第二次：不發請求
    assert len(w.paths()) == 1
    # 端點失敗：印警告、退回手寫表，收集照常
    w = World(D(10, 30))
    w.holidays = []
    w.down.add("holidaySchedule")
    rc, out = run_world(w, now)
    assert rc == 0 and "改用手寫表" in out and len(w.paths()) == 1


# ─── S6：補抓舊日期不覆蓋市場別 ───────────────────────────
def test_merge_stocks_flag():
    class Cur:
        def __init__(self, latest):
            self.latest, self.calls = latest, []

        def execute(self, sql, *p):
            self.calls.append((sql, p))
            return self

        def fetchone(self):
            return (self.latest,)
    rows = [{"stock_code": "5236", "stock_name": "凌陽創新", "market_type": "TPEx"}]
    for latest, d, flag in ((D(10, 30), D(1, 5), 0), (D(10, 30), D(10, 30), 1), (D(10, 30), D(11, 2), 1), (None, D(1, 5), 1)):
        cur = Cur(latest)
        daily.merge_stocks(cur, rows, d)
        sql, params = cur.calls[-1]
        assert "WHEN MATCHED AND ? = 1" in sql and "WHEN NOT MATCHED" in sql and params[1] == flag


# ─── S7：原子寫入 ─────────────────────────────────────────
def test_atomic_write():
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "latest.json"
        export._write(p, {"a": 1})
        assert json.loads(p.read_text()) == {"a": 1}
        with mock.patch.object(export.os, "replace", side_effect=OSError("磁碟已滿")):
            try:
                export._write(p, {"a": 2})
                assert False
            except OSError:
                pass
        assert json.loads(p.read_text()) == {"a": 1}                    # 原檔完好
        assert [x.name for x in Path(tmp).iterdir()] == ["latest.json"]  # 沒有殘留暫存檔


# ─── F1：升降單位取整、板塊漲跌 ───────────────────────────
def test_tick_round():
    cases = {650.5: 651, 2614.99: 2615, 240.82: 241, 167.62: 167.5, 651.5: 652, 9.994: 9.99, 9.995: 10.0,
             10.02: 10.0, 49.97: 49.95, 50.04: 50.0, 50.05: 50.1, 99.96: 100.0, 100.2: 100.0, 100.25: 100.5,
             499.75: 500.0, 500.4: 500.0, 999.5: 1000.0, 1002.5: 1005.0, 7800.0: 7800.0}
    for price, want in cases.items():
        assert export._tick_round(price) == want, (price, export._tick_round(price))


def _N(*v):
    return tuple(None if x is None else Decimal(str(x)) for x in v)


def test_changes_tick():
    def one(close, prev, ref, off=0):
        chs, _, _ = export._changes((D(7, 10), D(7, 13)), _N(prev, close), _N(0, off), "TWSE",
                                    [{"i": 1, "d": "2026-07-13", "t": "息", "p": prev, "r": ref}])
        return chs[1]
    assert one(170, 172, 167.62) == 2.5                 # 6762 2026-07-13 官方 +2.5
    assert one(2610, 7800, 2614.99) == -5.0             # 6669 2026-09-02
    assert one(239, 248, 240.82) == -2.0                # 2317 2026-07-02
    assert export._pct(2610, -5.0) == -5 / 2615 * 100
    # 還原係數仍用未取整的官方值
    assert export._adj_factors(2, [{"i": 1, "p": 7800.0, "r": 2614.99}])[0] == 2614.99 / 7800.0


def test_group_pct_source():
    # 板塊漲跌幅改用 P14 值：事件日官方 0 不再讓泡泡顏色失真
    assert export._pct(2610, -5.0) != export._pct(2610, 0)
    src = (ROOT / "twstock/export.py").read_text(encoding="utf-8")
    assert '"pct": _pct(c[i], chs[i])' in src and '"pct": _pct(c[i], ch[i])' not in src


# ─── S3：--catch-up（真實流程，只有 HTTP 與資料庫是假的）───
class Resp:
    def __init__(self, data=None, text=None, status=200):
        self.data, self.status_code = data, status
        self.content = (text or "").encode("cp950", errors="replace")

    def json(self):
        if self.data is None:
            raise ValueError("不是 JSON")
        return self.data

    def raise_for_status(self):
        pass


TWSE_CODES = [str(c) for c in range(1100, 2200)]      # 1100 檔
TPEX_CODES = [str(c) for c in range(3000, 3900)]      # 900 檔
MI_FIELDS = ["證券代號", "證券名稱", "成交股數", "成交筆數", "成交金額", "開盤價", "最高價", "最低價", "收盤價",
             "漲跌(+/-)", "漲跌價差"]
T86_FIELDS = ["證券代號", "外陸資買賣超股數(不含外資自營商)", "外資自營商買賣超股數", "投信買賣超股數", "自營商買賣超股數", "三大法人買賣超股數"]
Q_FIELDS = ["代號", "名稱", "收盤", "漲跌", "開盤", "最高", "最低", "成交股數", "成交金額(元)", "成交筆數"]
INX_FIELDS = ["日期", "開市", "最高", "最低", "收市", "漲/跌"]
FUT_HEAD = "交易日期,契約,到期月份(週別),開盤價,最高價,最低價,收盤價,漲跌價,漲跌%,成交量,結算價,未沖銷契約數,最後最佳買價,最後最佳賣價,歷史最高價,歷史最低價,是否因訊息面暫停交易,交易時段,價差對單式委託成交量\r\n"
OI_HEAD = "日期,商品名稱,身份別,多方交易口數,多方交易契約金額(千元),空方交易口數,空方交易契約金額(千元),多空交易口數淨額,多空交易契約金額淨額(千元),多方未平倉口數,多方未平倉契約金額(千元),空方未平倉口數,空方未平倉契約金額(千元),多空未平倉口數淨額,多空未平倉契約金額淨額(千元)\r\n"
ALL_EP = ("MI_INDEX", "BWIBBU_d", "fund/T86", "BFI82U", "dailyQuotes", "peQryDate", "dailyTrade", "futDataDown", "futContractsDateDown")


class World:
    """假的官方網站與資料庫。published = {端點: 已公布的日期}；rows 由真實的 MERGE 語句寫入。"""

    def __init__(self, seed_until, unsettled=False):
        self.published = {ep: set() for ep in ALL_EP}
        self.renamed, self.down, self.requests, self.merges = set(), set(), [], []
        self.cells = defaultdict(lambda: defaultdict(dict))     # {表: {日期: {鍵: 列}}}
        self.rows = {s.key: {} for s in health.SPECS}
        self.runs, self.holidays, self.exports, self.notices = [], [], 0, []
        self.revenue = {(2026, 8): 1980, (2026, 9): 1980}
        days = tradingcal.trading_days(seed_until - timedelta(days=45), seed_until, CLOSED)
        self.rows.update(_full_snapshot(days))
        if not unsettled:       # 沒有日期的資料：seed_until 當晚都已成功
            self.runs.append((datetime.combine(seed_until, datetime.min.time()).replace(hour=19, minute=35), 1, json.dumps(
                {"undated": {"alerts": f"{seed_until}T19:35:00+08:00", "events_to": str(seed_until), "revenue": str(seed_until)}})))
        # 官方日曆新鮮，不發請求
        self.holidays = [(h, "official", datetime(2026, 10, 20)) for h in sorted(tradingcal.HOLIDAYS) if h.year == 2026]

    def publish(self, d, *skip):
        for ep in ALL_EP:
            if ep not in skip:
                self.published[ep].add(d)

    def paths(self):
        return [p for p, _ in self.requests]

    # ── HTTP ──
    def http(self, method, url, timeout=30, params=None, data=None):
        form = params or data or {}
        path = re.sub(r"https://[^/]+", "", url)
        self.requests.append((path, form))
        for ep in self.down:
            if ep in url:
                return Resp(status=500)
        if "holidaySchedule" in url:
            return Resp(CAL)
        for key, fn in (("MI_INDEX", self._mi), ("BWIBBU_d", self._bwi), ("fund/T86", self._t86), ("BFI82U", self._bfi),
                        ("dailyQuotes", self._quotes), ("peQryDate", self._pe), ("dailyTrade", self._tpex_insti),
                        ("indexInfo/inx", self._inx), ("futDataDown", self._fut), ("futContractsDateDown", self._oi)):
            if key in url:
                return fn(form)
        return Resp([]) if "openapi" in url else Resp({"stat": "沒有資料", "tables": []})

    @staticmethod
    def _date(form, key="date"):
        s = form.get(key) or form.get("dayDate") or form.get("queryStartDate")
        s = s.replace("/", "")
        return date(int(s[:4]), int(s[4:6]), int(s[6:8]))

    def _no(self, ep, form, key="date"):
        return self._date(form, key) not in self.published[ep]

    def _mi(self, form):
        if self._no("MI_INDEX", form):
            return Resp({"stat": "很抱歉，沒有符合條件的資料!"})
        fields = ["欄位改名"] + MI_FIELDS[1:] if "MI_INDEX" in self.renamed else MI_FIELDS
        rows = [[c, "名", "1000", "10", "10000", "10", "11", "9", "10.5", "+", "0.5"] for c in TWSE_CODES]
        idx = {"title": "價格指數(臺灣證券交易所)", "fields": ["指數", "收盤指數", "漲跌(+/-)", "漲跌點數", "漲跌百分比(%)"],
               "data": [["發行量加權股價指數", "45,211.83", "<p>-</p>", "1,156.50", "-2.49"]]}
        return Resp({"stat": "OK", "tables": [idx, {"fields": fields, "data": rows}]})

    def _bwi(self, form):
        if self._no("BWIBBU_d", form):
            return Resp({"stat": "很抱歉，沒有符合條件的資料!"})
        return Resp({"stat": "OK", "fields": ["證券代號", "證券名稱", "殖利率(%)", "股利年度", "本益比", "股價淨值比", "財報年/季"],
                     "data": [[c, "名", "3.5", 114, "15", "1.5", "115/2"] for c in TWSE_CODES]})

    def _t86(self, form):
        if self._no("fund/T86", form):
            return Resp({"stat": "很抱歉，沒有符合條件的資料!"})
        fields = ["改名"] + T86_FIELDS[1:] if "fund/T86" in self.renamed else T86_FIELDS
        return Resp({"stat": "OK", "fields": fields, "data": [[c, "1,000", "0", "0", "0", "1,000"] for c in TWSE_CODES]})

    def _bfi(self, form):
        if self._no("BFI82U", form):
            return Resp({"stat": "很抱歉，沒有符合條件的資料!"})
        names = ["自營商(自行買賣)", "自營商(避險)", "投信", "外資及陸資(不含外資自營商)", "外資自營商", "合計"]
        return Resp({"stat": "OK", "fields": ["單位名稱", "買進金額", "賣出金額", "買賣差額"], "data": [[n, "1", "1", "0"] for n in names]})

    def _empty_tables(self, fields):
        return Resp({"stat": "ok", "tables": [{"fields": fields, "data": []}]})

    def _quotes(self, form):
        if self._no("dailyQuotes", form):
            return self._empty_tables(Q_FIELDS)
        return Resp({"stat": "ok", "tables": [{"fields": Q_FIELDS, "data": [[c, "名", "10.5", "0.5", "10", "11", "9", "1000", "10000", "10"] for c in TPEX_CODES]}]})

    def _pe(self, form):
        if self._no("peQryDate", form):
            return self._empty_tables(PE_FIELDS)
        fields = [f.replace("股票代號", "證券代碼") for f in PE_FIELDS] if "peQryDate" in self.renamed else PE_FIELDS
        return Resp({"stat": "ok", "tables": [{"fields": fields, "data": [[c, "名", "15", "1", 114, "3.5", "1.5", "115Q2"] for c in TPEX_CODES]}]})

    def _tpex_insti(self, form):
        if self._no("dailyTrade", form):
            return self._empty_tables(["代號"])
        return Resp({"stat": "ok", "tables": [{"fields": ["代號"], "data": [[c] + ["1"] * 23 for c in TPEX_CODES]}]})

    def _inx(self, form):
        y, m = self._date(form).year, self._date(form).month
        days = sorted(d for d in self.published["MI_INDEX"] if d.year == y and d.month == m)
        rows = [[f"{d:%Y/%m/%d}", "384.20", "384.20", "365.70", "370.26", "-17.11"] for d in days]
        return Resp({"stat": "ok", "tables": [{"fields": INX_FIELDS, "data": rows}]})

    def _fut(self, form):
        s, e = self._date(form, "queryStartDate"), datetime.strptime(form["queryEndDate"], "%Y/%m/%d").date()
        text = FUT_HEAD
        for d in sorted(self.published["futDataDown"]):
            if s <= d <= e:
                for m in ("202611", "202612", "202701", "202703", "202706", "202709"):
                    text += f"{d:%Y/%m/%d},TX,{m},1,2,1,2,0,0,10,2,100,,,,,,一般,0\r\n"
        return Resp(text=text)

    def _oi(self, form):
        s, e = self._date(form, "queryStartDate"), datetime.strptime(form["queryEndDate"], "%Y/%m/%d").date()
        days = [d for d in sorted(self.published["futContractsDateDown"]) if s <= d <= e]
        if not days:        # 實測：查無資料時是 200 ＋ alert 後導回查詢頁
            return Resp(text='<html><script>alert("x");window.location.replace("futContractsDateView");</script></html>')
        text = OI_HEAD
        for d in days:
            for who in ("自營商", "投信", "外資及陸資"):
                text += f"{d:%Y/%m/%d},臺股期貨,{who},1,1,1,1,0,0,1,1,1,1,0,0\r\n"
        return Resp(text=text)

    # ── 資料庫 ──
    def apply_merge(self, table, sql, params):
        self.merges.append(table)
        rows = json.loads(params[0])
        pd = next((p for p in params[1:] if isinstance(p, date)), None)
        market = lambda c: "TWSE" if c < "3000" else "TPEx"
        if table in ("daily_prices", "stock_fundamentals", "institutional_trades"):
            name = {"daily_prices": "prices", "stock_fundamentals": "pe", "institutional_trades": "insti"}[table]
            for mk in ("TWSE", "TPEx"):
                mine = [r for r in rows if market(r["stock_code"]) == mk]
                if mine:
                    cnt = lambda f: sum(r.get(f) is not None for r in mine)
                    self.rows[f"{name}.{mk}"][pd] = Row(len(mine), cnt("pe_ratio"), cnt("pb_ratio"), cnt("dividend_yield"))
        elif table == "market_index":
            for r in rows:
                self.rows[f"index.{r['index_code']}"][date.fromisoformat(r["trade_date"])] = Row(1)
        elif table == "insti_amount":
            self.rows["amount"][date.fromisoformat(rows[0]["trade_date"])] = Row(len(rows))
        elif table == "futures_daily_prices":
            for d in {r["trade_date"] for r in rows}:
                self.rows["futures"][date.fromisoformat(d)] = Row(sum(r["trade_date"] == d for r in rows))
        elif table == "futures_institutional":
            for d in {r["trade_date"] for r in rows}:
                cur = self.rows["futures_oi"].get(date.fromisoformat(d), Row()).n
                self.rows["futures_oi"][date.fromisoformat(d)] = Row(cur + sum(r["trade_date"] == d for r in rows))

    def snapshot(self, cur, start, end):
        return {k: {d: r for d, r in v.items() if start <= d <= end} for k, v in self.rows.items()}


class FakeCursor:
    def __init__(self, world):
        self.w, self.result, self.rowcount = world, [], 0

    def execute(self, sql, *params):
        w, self.result = self.w, []
        m = re.search(r"MERGE (\w+)", sql)
        if m and m.group(1) == "market_holidays":
            if "'adhoc'" in sql:
                w.holidays.append((params[0], "adhoc", params[2]))
            else:
                w.holidays.append((params[0], "official", params[2]))
        elif m and m.group(1) != "stocks":
            w.apply_merge(m.group(1), sql, params)
        elif m:
            w.merges.append("stocks")
        elif "SELECT MAX(trade_date) FROM daily_prices" in sql:
            ds = sorted(w.rows["prices.TWSE"])
            self.result = [(ds[-1] if ds else None,)]
        elif "holiday_date, source, fetched_at" in sql:
            self.result = list(w.holidays)
        elif "SELECT holiday_date, source" in sql:
            self.result = [(d, s) for d, s, _ in w.holidays]
        elif "SELECT holiday_date FROM market_holidays" in sql:
            self.result = [(d,) for d, s, _ in w.holidays if s == "adhoc"]
        elif sql.startswith("DELETE FROM market_holidays") and "adhoc" in sql:
            w.holidays = [h for h in w.holidays if not (h[0] == params[0] and h[1] == "adhoc")]
        elif "FROM collect_runs" in sql:
            self.result = list(reversed(w.runs))
        elif sql.startswith("INSERT INTO collect_runs"):
            w.runs.append((params[2], params[4], params[7]))
        elif "SELECT COUNT(*) FROM" in sql:
            self.result = [(0,)]
        elif "revenue_year, revenue_month, COUNT" in sql:
            self.result = [(y, m, n) for (y, m), n in w.revenue.items()]
        return self

    def fetchone(self):
        return self.result[0] if self.result else None

    def fetchall(self):
        return self.result


class FakeConn:
    def __init__(self, world):
        self.w = world

    def cursor(self):
        return FakeCursor(self.w)

    def commit(self):
        pass

    def close(self):
        pass


@contextlib.contextmanager
def env(world, lock=True, connect_error=None):
    fetch._dead_hosts.clear()

    def fake_connect(autocommit=False):
        if connect_error:
            raise connect_error
        return FakeConn(world)

    def fake_export():
        world.exports += 1
        return 1.0

    def fake_notify(problems, today):
        world.notices.append(problems)
        return True

    with mock.patch.object(fetch._SESSION, "request", world.http), mock.patch.object(fetch, "RETRY_BACKOFF", ()), \
            mock.patch.object(fetch, "MIN_INTERVAL", {}), mock.patch.object(fetch, "DEFAULT_INTERVAL", 0), \
            mock.patch.object(db, "connect", fake_connect), \
            mock.patch.object(db, "acquire_lock", lambda: FakeConn(world) if lock else None), \
            mock.patch.object(db, "release_lock", lambda c: None), \
            mock.patch.object(catchup, "load_snapshot", world.snapshot), \
            mock.patch.object(history, "load_snapshot", world.snapshot), \
            mock.patch.object(catchup, "chains_age_days", lambda: 1), \
            mock.patch.object(catchup, "status_changed", lambda s: False), \
            mock.patch.object(catchup.time, "sleep", lambda s: None), \
            mock.patch.object(export, "export_all", fake_export), \
            mock.patch.object(health, "notify_once", fake_notify):
        yield


def run_world(world, now, days=10, date_=None, lock=True, connect_error=None):
    buf = io.StringIO()
    with env(world, lock, connect_error), contextlib.redirect_stdout(buf):
        rc = catchup.run(days=days, date_=date_, now=now, notify=True)
    return rc, buf.getvalue()


def _hit(world, *names):
    return [p for p in world.paths() if any(n in p for n in names)]


FIRST_DAY = D(11, 2)    # 週一


def test_s3_01_t86_late():
    w = World(D(10, 30))
    w.publish(FIRST_DAY, "fund/T86")
    rc, out = run_world(w, T(11, 2, 17, 30))
    assert rc == 0 and w.rows["prices.TWSE"][FIRST_DAY].n == 1100 and w.rows["pe.TWSE"][FIRST_DAY].n == 1100
    assert FIRST_DAY not in w.rows["insti.TWSE"] and "上市法人：2026-11-02 尚未公布" in out
    assert w.exports == 1
    w.requests.clear()
    w.published["fund/T86"].add(FIRST_DAY)
    rc, out = run_world(w, T(11, 2, 18, 30))
    assert rc == 0 and w.paths() == ["/rwd/zh/fund/T86"] and w.rows["insti.TWSE"][FIRST_DAY].n == 1100
    assert w.exports == 2


def test_s3_02_not_published_vs_holiday():
    w = World(D(10, 30))
    rc, out = run_world(w, T(11, 2, 17, 30))
    assert rc == 0 and "上市行情：2026-11-02 尚未公布" in out and "休市" not in out
    assert _hit(w, "MI_INDEX") and not _hit(w, "BWIBBU_d", "fund/T86", "peQryDate", "dailyTrade")     # 行情還沒有，不打同市場的本益比與法人
    w = World(D(12, 24))
    rc, out = run_world(w, T(12, 25, 17, 30))
    assert rc == 0 and not _hit(w, "MI_INDEX") and "今天 2026-12-25 休市" in out and w.exports == 0


def test_s3_03_next_morning():
    w = World(D(10, 30))
    w.publish(FIRST_DAY)
    rc, _ = run_world(w, T(11, 3, 9, 0))
    assert rc == 0 and FIRST_DAY in w.rows["prices.TWSE"] and D(11, 3) not in w.rows["prices.TWSE"]
    assert [f["date"] for p, f in w.requests if "MI_INDEX" in p] == ["20261102"]


def test_s3_04_friday_and_monday():
    w = World(D(10, 29))
    w.publish(D(10, 30))
    w.publish(FIRST_DAY)
    rc, _ = run_world(w, T(11, 2, 18, 0))
    assert rc == 0 and [f["date"] for p, f in w.requests if "MI_INDEX" in p] == ["20261030", "20261102"]
    assert D(10, 30) in w.rows["insti.TPEx"] and FIRST_DAY in w.rows["insti.TPEx"]


def test_s3_05_tpex_empty():
    w = World(D(10, 30))
    w.publish(FIRST_DAY, "dailyQuotes")
    rc, out = run_world(w, T(11, 2, 22, 30))
    assert rc == 1 and FIRST_DAY in w.rows["prices.TWSE"] and FIRST_DAY not in w.rows["prices.TPEx"]
    assert "上櫃行情：缺 2026-11-02" in out and not _hit(w, "peQryDate", "dailyTrade")
    w.requests.clear()
    w.published["dailyQuotes"].add(FIRST_DAY)
    rc, _ = run_world(w, T(11, 3, 9, 0))
    assert rc == 0 and w.rows["prices.TPEx"][FIRST_DAY].n == 900 and "/www/zh-tw/afterTrading/dailyQuotes" in w.paths()
    # history 共用同一套判斷：有上市、沒上櫃的日期不跳過
    snap = {k: dict(v) for k, v in w.rows.items()}
    del snap["prices.TPEx"][FIRST_DAY]
    assert health.missing_keys(FIRST_DAY, ("prices.TWSE", "prices.TPEx"), snap, health.medians(snap)) == ("prices.TPEx",)


def test_s3_06_fetch_error():
    w = World(D(10, 30))
    w.publish(FIRST_DAY)
    w.down.add("BWIBBU_d")
    rc, out = run_world(w, T(11, 2, 18, 0))
    assert rc == 1 and len(_hit(w, "BWIBBU_d")) == 1            # 重試用盡（測試設為不重試）只打一次
    assert not _hit(w, "fund/T86", "BFI82U")                    # 同主機本次不再請求
    assert _hit(w, "dailyTrade", "futDataDown")                 # 其他主機照常
    assert FIRST_DAY in w.rows["prices.TWSE"] and FIRST_DAY in w.rows["insti.TPEx"]
    assert w.exports == 1 and "上市本益比" in out               # 已寫入的資料有匯出
    assert w.notices and any("pe.TWSE" in k for k in w.notices[0])


def test_s3_07_schema_change():
    for ep, label in (("peQryDate", "上櫃本益比"), ("fund/T86", "上市法人"), ("MI_INDEX", "上市行情")):
        w = World(D(10, 30))
        w.publish(FIRST_DAY)
        w.renamed.add(ep)
        rc, out = run_world(w, T(11, 2, 18, 0))
        assert rc == 1 and "Traceback" not in out and f"❌ {label}" in out, ep
        assert FIRST_DAY in w.rows["prices.TPEx"] and FIRST_DAY in w.rows["insti.TPEx"], ep    # 其他資料集照常
        assert w.exports == 1, ep
    # 上櫃本益比欄位不符：其他同主機資料照常（欄位不符不是主機問題）
    w = World(D(10, 30))
    w.publish(FIRST_DAY)
    w.renamed.add("peQryDate")
    run_world(w, T(11, 2, 18, 0))
    assert FIRST_DAY in w.rows["pe.TWSE"] and FIRST_DAY not in w.rows["pe.TPEx"]


def test_s3_08_db_down():
    w = World(D(10, 30))
    w.publish(FIRST_DAY)
    rc, out = run_world(w, T(11, 2, 18, 0), connect_error=pyodbc.OperationalError("HYT00", "timeout"))
    assert rc == 2 and "Docker" in out and "Traceback" not in out and w.exports == 0 and w.requests == []
    assert w.notices and "db" in w.notices[0]


def test_s3_09_complete():
    w = World(D(11, 2))
    rc, out = run_world(w, T(11, 2, 19, 40))
    assert rc == 0 and w.requests == [] and w.exports == 0 and w.merges == [] and "不匯出" in out


def test_s3_10_run_twice():
    w = World(D(10, 30))
    w.publish(FIRST_DAY)
    assert run_world(w, T(11, 2, 18, 0))[0] == 0
    n = w.rows["prices.TWSE"][FIRST_DAY].n
    w.requests.clear(), w.merges.clear()
    rc, _ = run_world(w, T(11, 2, 18, 5))
    assert rc == 0 and w.requests == [] and w.merges == [] and w.rows["prices.TWSE"][FIRST_DAY].n == n and w.exports == 1


def test_s3_11_locked():
    w = World(D(10, 30))
    w.publish(FIRST_DAY)
    rc, out = run_world(w, T(11, 2, 18, 0), lock=False)
    assert rc == 0 and "另一個收集程序" in out and w.requests == [] and w.exports == 0 and len(w.runs) == 1


def test_s3_12_tpex_index_old_month():
    w = World(D(10, 30))
    del w.rows["index.TPEX"][D(10, 30)]
    w.published["MI_INDEX"].add(D(10, 30))
    w.publish(FIRST_DAY)
    rc, _ = run_world(w, T(11, 2, 18, 0))
    assert rc == 0 and D(10, 30) in w.rows["index.TPEX"] and FIRST_DAY in w.rows["index.TPEX"]
    assert sorted(f["date"] for p, f in w.requests if "indexInfo/inx" in p) == ["2026/10/01", "2026/11/01"]


def test_s3_adhoc_closure_flow():
    # 11/02 全部沒有資料（颱風假），11/03 補跑 → 判定臨時休市，不再列為缺漏，下次不再請求
    w = World(D(10, 30))
    w.publish(D(11, 3))
    rc, out = run_world(w, T(11, 3, 18, 0))
    assert rc == 0 and "判定為臨時休市" in out and (FIRST_DAY, "adhoc") in [(d, s) for d, s, _ in w.holidays]
    w.requests.clear()
    rc, _ = run_world(w, T(11, 3, 18, 10))
    assert rc == 0 and w.requests == []
    # 期交所有資料：不判定，算異常
    w = World(D(10, 30))
    w.published["futDataDown"].add(FIRST_DAY)
    w.publish(D(11, 3))
    rc, out = run_world(w, T(11, 3, 18, 0))
    assert rc == 1 and "判定為臨時休市" not in out and not [h for h in w.holidays if h[1] == "adhoc"]
    # 查詢失敗：不判定
    w = World(D(10, 30))
    w.down.add("MI_INDEX")
    rc, out = run_world(w, T(11, 3, 18, 0))
    assert rc == 1 and not [h for h in w.holidays if h[1] == "adhoc"]
    # 錯判復原：collect --date 查到資料就移除判定
    w = World(D(10, 30))
    w.holidays.append((FIRST_DAY, "adhoc", datetime(2026, 11, 3, 18)))
    w.publish(FIRST_DAY)
    rc, out = run_world(w, T(11, 4, 9, 0), date_=FIRST_DAY)
    assert rc == 0 and "移除臨時休市判定" in out and FIRST_DAY in w.rows["prices.TWSE"]
    assert not [h for h in w.holidays if h[1] == "adhoc"]


def test_s3_collect_date_compat():
    # --date：已有資料也全部重抓覆寫；一定匯出；舊日期不影響今天
    w = World(D(10, 30))
    w.publish(D(10, 30))
    rc, _ = run_world(w, T(11, 2, 18, 0), date_=D(10, 30))
    assert rc == 0 and w.exports == 1
    assert [f["date"] for p, f in w.requests if "MI_INDEX" in p] == ["20261030"]
    assert _hit(w, "BWIBBU_d") and _hit(w, "fund/T86") and _hit(w, "peQryDate") and _hit(w, "dailyTrade") and _hit(w, "BFI82U")
    # 休市日：不發行情請求，仍匯出，回傳 0
    w = World(D(10, 30))
    rc, out = run_world(w, T(10, 31, 12, 0), date_=D(10, 31))
    assert rc == 0 and not _hit(w, "MI_INDEX") and "休市" in out and w.exports == 1


def test_s3_gap_hint():
    w = World(D(10, 2))
    for d in tradingcal.trading_days(D(10, 5), FIRST_DAY, CLOSED):
        w.publish(d)
    rc, out = run_world(w, T(11, 2, 18, 0), days=3)
    assert rc == 1 and "python -m twstock history --start 2026-10-05" in out


def test_history_pe_only():
    # S1 回補：只打櫃買本益比端點；上市列不動；可中斷重跑；重跑待抓 0 天
    days = [D(10, 28), D(10, 29), D(10, 30)]
    w = World(D(10, 30))
    for d in days[:2]:
        w.rows["pe.TPEx"][d] = Row(893, 676, 893, 2)    # 舊腳本寫的：列都在，殖利率幾乎全空
    w.rows["pe.TPEx"][days[2]] = Row(2, 2, 2, 2)
    twse_before = dict(w.rows["pe.TWSE"])
    w.published["peQryDate"].update(days[:2])           # 10/30 暫時失敗
    w.down.add("/nothing")
    buf = io.StringIO()
    with env(w), contextlib.redirect_stdout(buf):
        assert history.run_history(days[0], days[2], ("pe",)) is True
    assert "待抓 3 天" in buf.getvalue() and "pe.TPEx：3 天" in buf.getvalue() and "pe.TWSE" not in buf.getvalue().split("[1/3]")[0]
    assert set(w.paths()) == {"/www/zh-tw/afterTrading/peQryDate"} and len(w.paths()) == 3
    assert w.rows["pe.TPEx"][days[0]].dy == 900 and w.rows["pe.TWSE"] == twse_before
    # 中斷：端點失敗就停在該日，已寫入的不重抓
    w.requests.clear()
    w.down.add("peQryDate")
    with env(w), contextlib.redirect_stdout(io.StringIO()):
        assert history.run_history(days[0], days[2], ("pe",)) is False
    assert len(w.paths()) == 1 and w.requests[0][1]["date"] == "2026/10/30"
    # 重跑接續
    w.requests.clear()
    w.down.clear()
    w.published["peQryDate"].add(days[2])
    with env(w), contextlib.redirect_stdout(io.StringIO()):
        assert history.run_history(days[0], days[2], ("pe",)) is True
    assert [f["date"] for _, f in w.requests] == ["2026/10/30"]
    # 全部齊全：待抓 0 天，不發請求
    w.requests.clear()
    buf = io.StringIO()
    with env(w), contextlib.redirect_stdout(buf):
        assert history.run_history(days[0], days[2], ("pe",)) is True
    assert "待抓 0 天" in buf.getvalue() and w.requests == []
    # 欄位不符：停下來，不把每天的請求都浪費掉
    w = World(D(10, 30))
    for d in days:
        w.rows["pe.TPEx"][d] = Row(893, 676, 893, 2)
    w.publish(days[0])
    w.renamed.add("peQryDate")
    with env(w), contextlib.redirect_stdout(io.StringIO()):
        assert history.run_history(days[0], days[2], ("pe",)) is False
    assert len(w.paths()) == 1


def test_history_tpex_index():
    w = World(D(10, 30))
    w.rows["index.TPEX"] = {d: r for d, r in w.rows["index.TPEX"].items() if d.month == 10}
    w.published["MI_INDEX"].update(tradingcal.trading_days(D(9, 25), D(9, 30), CLOSED))
    buf = io.StringIO()
    with env(w), contextlib.redirect_stdout(buf):
        assert history.run_history(D(9, 29), D(10, 30), ("tpex_index",)) is True
    assert [f["date"] for _, f in w.requests] == ["2026/09/01"] and D(9, 30) in w.rows["index.TPEX"]   # 10 月已齊全，不打


def test_plan_pure():
    days = tradingcal.trading_days(D(10, 1), D(11, 2), CLOSED)
    snap = _full_snapshot(days, skip={("insti.TWSE", D(10, 30)), ("futures", D(10, 29)), ("futures", D(10, 30))})
    state = {"alerts_at": datetime(2026, 11, 2, 18), "events_to": D(11, 2), "revenue_on": D(11, 2), "collected_at": None}
    p = catchup.make_plan(T(11, 2, 18, 30), 10, snap, state, CLOSED, {(2026, 8): 1980, (2026, 9): 1980})
    assert p["by_date"] == [(D(10, 30), ("insti.TWSE",))] and p["futures"] == (D(10, 29), D(10, 30))
    assert p["alerts"] is False and p["events"] is None and p["revenue"] == []
    # 19:00 後再抓一次處置／注意股；已抓過就不再抓
    assert catchup.make_plan(T(11, 2, 19, 30), 10, snap, state, CLOSED, {})["alerts"] is True
    state2 = dict(state, alerts_at=datetime(2026, 11, 2, 19, 30))
    assert catchup.make_plan(T(11, 2, 21, 45), 10, snap, state2, CLOSED, {})["alerts"] is False
    # 事件查詢區間涵蓋最舊缺口
    state3 = dict(state, events_to=D(10, 28))
    assert catchup.make_plan(T(11, 2, 18, 30), 10, snap, state3, CLOSED, {})["events"] == (D(10, 21), D(11, 2))
    # 月營收：10 日後才收上個月，公布完成（≥ 前月 98%）就不再請求
    snap2 = _full_snapshot(tradingcal.trading_days(D(10, 15), D(11, 12), CLOSED))
    st = dict(state, revenue_on=None)
    assert catchup.make_plan(T(11, 12, 18), 10, snap2, st, CLOSED, {(2026, 9): 1980, (2026, 10): 1000})["revenue"] == [(2026, 10)]
    assert catchup.make_plan(T(11, 12, 18), 10, snap2, st, CLOSED, {(2026, 9): 1980, (2026, 10): 1950})["revenue"] == []
    st = dict(state, revenue_on=D(11, 12))
    assert catchup.make_plan(T(11, 12, 21), 10, snap2, st, CLOSED, {(2026, 9): 1980, (2026, 10): 1000})["revenue"] == []


def test_run_record():
    # 執行紀錄的時間是台灣時間；有新資料才標 new_data；「更新於」取最後一次有新資料的時間
    calls = []

    class Cur:
        def execute(self, sql, *p):
            calls.append((sql, p))
    t0 = T(11, 2, 17, 30)
    health.write_run(Cur(), "catch-up", t0, t0 + timedelta(minutes=2), "pending", True, 12, 95.4, {"written": {"prices.TWSE": {"2026-11-02": 1090}}})
    sql, p = calls[0]
    assert "GETDATE" not in sql and p[1] == datetime(2026, 11, 2, 17, 30) and p[2] == datetime(2026, 11, 2, 17, 32) and p[4] == 1
    assert json.loads(p[7])["written"]["prices.TWSE"]["2026-11-02"] == 1090

    class Cur2:
        def execute(self, sql, *p):
            return self

        def fetchall(self):     # 新到舊
            return [(datetime(2026, 11, 2, 21, 45), 0, "{}"),
                    (datetime(2026, 11, 2, 19, 31), 1, json.dumps({"undated": {"alerts": "2026-11-02T19:30:00+08:00"}})),
                    (datetime(2026, 11, 2, 17, 32), 1, json.dumps({"undated": {"events_to": "2026-11-02", "revenue": "2026-11-02"}}))]
    st = health.load_state(Cur2())
    assert st["collected_at"] == datetime(2026, 11, 2, 19, 31) and st["events_to"] == D(11, 2) and st["alerts_at"].hour == 19
    assert health.collected_at(None, st) == ("2026-11-02T19:31:00+08:00", "run")


def test_guard_runtime_error():
    errors = {}

    def boom():
        raise RuntimeError("產業鏈解析不到")
    with contextlib.redirect_stdout(io.StringIO()):
        assert catchup._guard("chains", errors, boom) is False
    assert "chains" in errors


def test_schedule_scripts_static():
    # 只讀檔案內容，不執行、不安裝
    sh = (ROOT / "scripts/mac/install_schedule.sh").read_text(encoding="utf-8")
    assert sh.index('"--print"') < sh.index("launchctl bootout")          # 預覽模式在任何 launchctl 之前結束
    for t in ('"17 30"', '"19 30"', '"21 45"', "/usr/bin/caffeinate", "<string>--catch-up</string>", "RunAtLoad", "logs/collect.log"):
        assert t in sh, t
    bat = (ROOT / "scripts/windows/install_schedule.bat").read_text(encoding="utf-8")
    for t in ("17:30", "19:30", "21:45", "/uninstall"):
        assert t in bat, t
    assert "--catch-up" in (ROOT / "scripts/windows/collect.bat").read_text(encoding="utf-8")
    assert "--catch-up" in (ROOT / "scripts/mac/collect.command").read_text(encoding="utf-8")


def test_futures_no_data_page():
    # 期交所法人端點查無資料回 200 ＋ alert 頁，不是封鎖；真的不是 CSV 才是 FetchError
    w = World(D(10, 30))
    with env(w):
        assert futures.fetch_futures_institutional(D(10, 23), D(10, 23)) == []
    with mock.patch.object(futures, "request", lambda *a, **k: Resp(text="<html>Forbidden</html>")):
        try:
            futures.fetch_futures_institutional(D(10, 23), D(10, 23))
            assert False
        except FetchError:
            pass


def test_status_changed():
    with tempfile.TemporaryDirectory() as tmp, mock.patch.object(catchup, "SITE_DATA_DIR", Path(tmp)):
        now = [{"k": "a", "s": "ok", "d": "2026-10-30"}]
        assert catchup.status_changed(now) is True      # 沒有 latest.json
        (Path(tmp) / "latest.json").write_text(json.dumps({"status": {"datasets": now}}), encoding="utf-8")
        assert catchup.status_changed(now) is False
        assert catchup.status_changed([{"k": "a", "s": "abnormal", "d": "2026-10-30"}]) is True


def test_dead_host():
    fetch._dead_hosts.clear()
    calls = []

    def boom(*a, **k):
        calls.append(1)
        return Resp(status=503)
    with mock.patch.object(fetch._SESSION, "request", boom), mock.patch.object(fetch, "RETRY_BACKOFF", ()), \
            mock.patch.object(fetch, "MIN_INTERVAL", {}), mock.patch.object(fetch, "DEFAULT_INTERVAL", 0):
        for _ in range(3):
            try:
                fetch.request("GET", "https://www.twse.com.tw/x")
                assert False
            except FetchError:
                pass
    assert len(calls) == 1
    fetch._dead_hosts.clear()


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"✅ {fn.__name__}")
    print("全部通過")
```
