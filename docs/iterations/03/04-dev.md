# 第 03 輪｜Programmer：實作紀錄

- 撰寫日期：2026-10-31（週六）
- 依據：`03-design.md`（實作依據，含附錄 C 程式、附錄 D 測試）、`02-pm.md`（範圍、驗收條件、範圍變更紀錄）
- 本輪項目：S1（含 P9）、S2、S3（含 A1-補漏、S7）、S4、S5、S6、F1，全部完成；README（R1～R12）與 `__main__.py`（M1～M8）已同步更新。
- 程式來源：附錄 C、D 的 diff 與新檔是用腳本從設計文件抽出後套用（`patch -p0`），不是手抄。**程式邏輯、函式名稱、資料表、文案與設計完全相同**；`export.py` 另以「原版＋設計 diff」比對最終檔案，無差異。
- 未 commit、未 push、未動 `.env`、`_archive/`、`_backups/`。**沒有安裝或移除排程**，也沒有執行 `install_schedule.sh`／`.bat`、`pmset`、`docker update`。測試用埠 8001 已關閉，埠 8000 未動。

> **結論**：`check` 回傳 0、結果「無異常」（`logs/iter03_check_final.log`）。三個測試檔全部通過。
> **執行中遇到一次外部異常**：`openapi.twse.com.tw` 至少在 13:09～13:15 回傳非 JSON，讓第一次 `collect --date` 回傳 1。13:37 確認恢復後重跑一次，回傳 0（見第二節之 3）。

---

## 一、各項目修改內容

### S1（含 P9）上櫃本益比、殖利率修復與回補
| 檔案 | 函式／位置 | 修改 |
|---|---|---|
| `twstock/fetch.py` | `SchemaError` | 新例外：有資料但欄位不符 |
| `twstock/collectors/daily.py` | 常數 `PE`、`TPEX_INDEX`、`ALL_DATASETS`、`DATASET_KEYS`、`DAY_KEYS`、`PARSE_ERRORS` | 本益比獨立成資料集，並定義分市場的細項鍵 |
| 同上 | `parse_tpex_pe()`、`fetch_tpex_pe()` | 改用實際欄位 `股票代號`、`殖利率(%)`；欄位不符丟 `SchemaError`，空表回傳 `{}` |
| 同上 | `merge_fundamentals()` | 新增 JOIN `daily_prices`，只寫當天有行情列的股票 |
| 同上 | `fetch_twse_daily()`、`fetch_tpex_daily()` | 找不到個股表時丟 `SchemaError`（原本靜默回傳空的） |
| `twstock/collectors/history.py` | 整檔取代：`load_status()`、`run_history()`、`SECONDS_PER_KEY` | 用 `missing_keys` 逐日、逐細項判斷還缺什麼；`FetchError` 或欄位不符立即停止 |
| `twstock/__main__.py` | `history --only` | 加 `pe`、`tpex_index` |
| `site/stock.js` | `renderStock()` 的 `fundSub` | 本益比、殖利率卡顯示「資料 MM/DD」；值為空時加「官方未提供」；與股本變動註記並列 |

### S2 收集完整性檢查與執行紀錄
| 檔案 | 函式／位置 | 修改 |
|---|---|---|
| `twstock/config.py` | `TW_TZ`、`tw_now()` | 固定 +08:00 |
| `twstock/fetch.py` | `_requests`、`request_count()` | 記錄請求次數 |
| `twstock/db.py` | `DDL`、`setup_database()` | 新表 `collect_runs` |
| `twstock/health.py`（新檔，289 行） | `SPECS`、`load_snapshot`、`medians`、`assess`、`missing_keys`、`due_days`、`evaluate`、`outcome`、`problem_lines`、`load_state`、`write_run`、`notify_once`、`check_report`、`run_check`、`collected_at`、`dataset_status`、`build_status` | 資料集模型與判斷；`check`、`--catch-up`、`history`、`status` 共用 |
| `twstock/__main__.py` | `cmd_check()`、子指令 `check` | 唯讀檢查；回傳 0／1／2 |

### S3（含 A1-補漏、S7）排程可靠化
| 檔案 | 函式／位置 | 修改 |
|---|---|---|
| `twstock/collectors/catchup.py`（新檔，322 行） | `make_plan`、`plan_for_date`、`execute_plan`、`status_changed`、`run`、`_run_locked` 等 | `collect` 的唯一入口；規劃是純函式 |
| `twstock/collectors/daily.py` | `collect_for_date()` 拆分、新增 `_collect_key()`、`_save()` | 各資料集獨立抓取與 commit；回傳 `(written, errors)` |
| 同上 | `parse_tpex_index()`、`fetch_tpex_index(year, month)`、`collect_tpex_index(year, month)`；移除 `TPEX_OPENAPI` | 櫃買指數改用 `indexInfo/inx` 月查詢 |
| `twstock/collectors/futures.py` | `fetch_futures_institutional()` | 查無資料頁（`futContractsDateView`）回傳 `[]`，不再誤報 `FetchError` |
| `twstock/fetch.py` | `_dead_hosts` | 重試用盡的主機，本次執行不再請求 |
| `twstock/db.py` | `acquire_lock()`、`release_lock()` | `sp_getapplock` 防重疊 |
| `twstock/export.py` | `_write()` | S7：先寫暫存檔再 `os.replace`，失敗時刪除暫存檔 |
| `twstock/__main__.py` | `cmd_collect()`、`cmd_history()`、`collect` 參數 | 移到 `catchup.run`；`history` 加鎖；`--catch-up`、`--days`、`--notify` |
| `scripts/mac/install_schedule.sh`、`collect.command` | 整檔取代 | 三個時間、`caffeinate -i`、`RunAtLoad`、`--print`；手動預設 `--catch-up` |
| `scripts/windows/install_schedule.bat`、`collect.bat` | 整檔取代（CRLF） | 三個工作、預設 `--catch-up` |

### S4 網站資料新鮮度提示
| 檔案 | 函式／位置 | 修改 |
|---|---|---|
| `twstock/export.py` | `export_all()` | 新增 `status`；`updated_at` 改為最後成功收集時間；回傳耗時並印 `⏱️` |
| `site/index.html` | `#freshBar` | 多一行 |
| `site/app.css` | `.fresh` | 橫幅樣式 |
| `site/app.js` | `twParts`、`expectedDate`、`freshLines`、`renderStatus`、`recheckLatest`；`init()` | 橫幅、局部提示、回前景重新檢查，不自動跳轉 |

### S5 官方交易日曆與臨時休市
| 檔案 | 函式／位置 | 修改 |
|---|---|---|
| `twstock/tradingcal.py`（新檔，121 行） | `HOLIDAYS`、`AD_HOC`（由 `history.py` 移入）；`closed_from_rows`、`load_closed`、`is_trading_day`、`trading_days`、`parse_holidays`、`calendar_due`、`update_calendar`、`warn_uncovered`、`is_adhoc_closure`、`add_adhoc`、`remove_adhoc` | 官方表＋手寫表＋臨時休市；`history` 仍保留舊的對外名稱 |
| `twstock/db.py` | `DDL` | 新表 `market_holidays` |

### S6 補抓舊日期不覆蓋名稱與市場別
| 檔案 | 函式 | 修改 |
|---|---|---|
| `twstock/collectors/daily.py` | `merge_stocks(cursor, rows, trade_date)` | `trade_date ≥ 最新日線日期` 才更新既有股票；新股票照常新增 |

### F1 小修正
| 檔案 | 函式 | 修改 |
|---|---|---|
| `twstock/export.py` | `_TICKS`、`_tick_round()`、`_changes()` | 事件日參考價依升降單位 half-up 取整；`_adj_factors` 不動 |
| 同上 | `export_all()` | 板塊 `pct` 改用 P14 的 `chs[i]` |
| `site/stock.js` | `renderSignals()` | 平手顯示「中性：x 多 x 空」，無多空配色 |
| `tests/test_iter02.py` | `test_changes` | 兩處預期值，見下 |

**`tests/test_iter02.py` 改了兩處預期值（規格變更，不是遷就）：**

| 位置 | 舊值 | 新值 | 原因 |
|---|---|---|---|
| 2317 7/02 情境：參考價 240.82、收 239 | `-1.82` | `-2.0` | 參考價取整為 241 |
| 5904 7/16 情境：參考價 651.5、收 623 | `-28.5` | `-29.0` | 參考價取整為 652（half-up） |

### 測試與文件
- `tests/test_iter03.py`（新檔）：**直接採用附錄 D 原文**，共 43 個測試，未修改。
- README：R1～R12 依設計第七節修改。
- `__main__.py`：M1～M8 依設計附錄 C 修改。`--help` 看得到 `check`、`--catch-up`、`--only pe`、`tpex_index`。

---

## 二、執行過的指令與回補結果

### 1. 依序執行的資料操作

| 順序 | 指令 | 結果 |
|---|---|---|
| 0 | T-PRE：複製 `latest.json` 與 5 檔個股到 `logs/iter03_before/` | 完成 |
| 1 | `python3 -m twstock setup-db` ×2 | 兩次皆成功，訊息含 `collect_runs`、`market_holidays` |
| 2 | `check`（基線，`logs/iter03_check_before.log`） | **rc=1**，異常 3 項，與設計完全相同（見下） |
| 4 | `caffeinate -i history --start 2025-10-30 --end 2026-10-30 --only pe`（背景，`logs/iter03_backfill_pe.log`） | 見第 2 小節 |
| 4 | 同一指令重跑（`logs/iter03_backfill_pe_rerun.log`） | **待抓 0 天**，rc=0，無外部請求 |
| 5 | `caffeinate -i history ... --only tpex_index`（`logs/iter03_backfill_tpex_index.log`） | **12 個月、12 次請求、34 秒（13:08:11～13:08:45）**，0 失敗，rc=0 |
| 6 | `check`（`logs/iter03_check_after.log`） | **rc=0**，「結果：無異常」 |
| 8 | `collect --date 2026-10-30`（`logs/iter03_collect_1030.log`） | **rc=1**：行情等全部寫入，`openapi.twse` 異常（見第 3 小節） |
| 8 | 同一指令重跑（`logs/iter03_collect_1030_rerun.log`） | **rc=0**，「全部齊全」，54 秒，24 次請求 |
| 9 | `collect --catch-up`（`logs/iter03_catchup_holiday.log`） | **rc=0**，見第 4 小節 |
| 10 | `/usr/bin/time -p python3 -m twstock export`（`logs/iter03_export_time.log`、`iter03_export_final.log`） | 見第三節 |

基線輸出的異常行（現在 2026-10-31 12:54）：

```
❌ 上櫃本益比：2026-09-30 ～ 2026-10-29 共 19 天，最新 殖利率填充率 0.2%（下限 50%）
❌ 上櫃本益比：2026-10-30 筆數 2（近 20 日中位數 888，門檻 710）
❌ 櫃買指數：缺 2026-09-30
結果：異常 3 項
```

### 2. S1 回補結果

| 項目 | 結果 |
|---|---|
| 時間 | 2026-10-31 12:55:31～13:07:36，**12 分 05 秒**（設計預估 12.9 分鐘） |
| 請求 | 242 次（只有櫃買 `peQryDate`），**0 失敗、0 重試、0 限流** |
| 待抓 | `pe.TPEx` 242 天、`pe.TWSE` 0 天 |
| 上櫃列數 | 148,872 → **213,094**（新增 64,222） |
| `stock_fundamentals` 總列數 | 408,166 → 472,388 |

**新增列橫跨 74 天，不是只有 15 天**：回補前有 15 天（2026-01-22～02-11）完全沒有上櫃列，另外 59 天（2025-10-30 起）只有 1 列，所以合計 74 天（242 − 168）。設計說的「15 天」本身沒有錯，只是沒有包含這 59 天。

**前後比對：**

| 比對 | 結果 |
|---|---|
| **上市列**（T-S1-4，`logs/iter03_fund_before.json`／`after.json`） | 259,294 → 259,294，**差異 0 筆** |
| 上櫃的本益比、淨值比（額外比對，`logs/iter03_fund_tpex_*.json`） | 原有的 148,872 列**變動 0 筆、非空轉空 0 筆、消失 0 列** |
| 上櫃殖利率 | 148,733 列由 NULL 補上（同樣是上面那份快照的比對結果） |
| 每日上櫃殖利率非空筆數（T-S1-3） | 242 天全部 ≥ 800，**最小 858、最大 896** |
| 轉上市前差異（S1-5 ★） | 0 筆，不需要列代號 |

> 上市列比對是在 S6（步驟 8）之前做的。S6 之後 5236、8908 改標 TWSE，如果 QA 用同一支腳本重新快照，會多出這兩檔的列，這是 S6 造成的，不是 S1 的回歸。

### 3. `openapi.twse.com.tw` 異常（至少 13:09～13:15）

**現象**：第一次 `collect --date 2026-10-30` 時，`openapi.twse.com.tw` 回傳非 JSON（`Expecting value: line 1 column 1`）。程式依既有規則退避 30／60／120 秒後放棄，主機被標記為失敗，本次不再請求。

**處理與影響：**
- 行情、本益比、法人、金額、指數、期貨、事件都照常寫入並完成匯出；`alerts`、`revenue`、`industry` 記為異常，回傳 1。這正是 S3 情境 6 的設計行為，等於在真實環境驗證了一次。
- 這次共 22 次請求，耗時 4 分 17 秒，其中約 3.5 分鐘是退避等待。
- 依「不要高頻重試」的要求，之後只送了 **2 次單次診斷請求**（`RETRY_BACKOFF=()`，都經過 `fetch.request`）：
  - 13:15：HTTP 200、`text/html`、947 bytes，內容是含聯絡電話變數的網頁，推測是防火牆或維護頁（這次只印了前 200 字元，未存檔）。
  - 13:37：HTTP 200、`application/json`，已恢復（`logs/iter03_openapi_probe.log`）。
- 13:37 重跑 `collect --date 2026-10-30`，rc=0。

**原因未確認**：不知道是維護還是暫時封鎖。回補只打櫃買，這個主機在回補期間沒有被請求；同一次 `collect` 中，證交所主站、櫃買、期交所都正常。13:15 到 13:37 之間沒有探測，實際恢復時間不明。

### 4. T-S3-14：非交易日 `collect --catch-up`

```
ℹ️  今天 2026-10-31 休市
✅ 最近 10 個交易日資料齊全，不需要請求
📊 收集結果（2026-10-30）
  ✅ 上市行情 1,092 筆 … ✅ 期貨法人 9 筆
ℹ️  沒有新資料，不匯出
✅ 全部齊全
rc=0
```

- `collect_runs`：`requests = 0`、`new_data = 0`、`export_seconds = NULL`、`outcome = ok`。
- `latest.json` 的 md5 前後相同（`03ec0d06…`）；各表筆數無差異（`logs/iter03_counts_a.json`／`b.json`）。

### 5. T-S3-R1：拆分回歸（`collect --date 2026-10-30` 前後）

`logs/iter03_counts_before.json` 與 `after.json` **完全相同**；重跑前後（`before2`、`after2`）也相同。

| 表 | 10/30 筆數 | | 表 | 總筆數 |
|---|---|---|---|---|
| `daily_prices` | 1,985 | | `stocks` | 1,999 |
| `stock_fundamentals` | 1,980 | | `daily_prices` | 473,393 |
| `institutional_trades` | 1,875 | | `stock_fundamentals` | 472,388 |
| `market_index` | 2 | | `institutional_trades` | 445,380 |
| `insti_amount` | 6 | | `market_index` | 502 |
| `futures_daily_prices` | 12 | | `stock_alerts` | 70 |
| `futures_institutional` | 9 | | `price_events` | 1,694 |
| | | | `monthly_revenue` | 87,669 |

`stock_alerts`、`price_events` 沒有增加（官方 MERGE 的都是既有列）。`update_industry` 重跑時「更新 1 檔」（沒有逐一查是哪一檔）。

### 6. T-S5-1：官方休市表與手寫表比對

```
官方多 [] 手寫多 [] 官方筆數 18
```

官方表共 24 筆，平日 18 筆，**與 `HOLIDAYS` 2026 零差異**。`trading_days(2025-10-30, 2026-10-30, load_closed(cur))` = **242**。

### 7. 測試與語法檢查（最後一次）

| 指令 | 結果 |
|---|---|
| `python3 tests/test_iter01.py` | 全部通過 |
| `python3 tests/test_iter02.py` | 全部通過 |
| `python3 tests/test_iter03.py` | 全部通過（43 個） |
| `python3 -m py_compile twstock/*.py twstock/collectors/*.py twstock/analysis/*.py tests/*.py` | 通過 |
| `node --check site/app.js`、`site/stock.js` | 通過 |
| `python3 -m twstock check`（`logs/iter03_check_final.log`） | **rc=0，「結果：無異常」** |
| T-S3-L（真實鎖） | rc=0，「另一個收集程序正在執行，這次略過」 |
| T-S2-4（台灣時間） | `finished_at` 2026-10-31 13:13:13，與當時台灣時間相差不到 1 分鐘 |
| T-S3-15 | `bash -n` 通過；plist 通過 `plutil -lint` 與內容斷言（做法見第四節第 1 點） |
| T-S3-16 | `launchctl list \| grep twstock`、`ls ~/Library/LaunchAgents \| grep com.twstock` 都沒有結果 |
| T-S3-17 | `.bat` 為 CRLF；內容含 17:30、19:30、21:45、`--catch-up`（靜態） |

---

## 三、檔案大小與匯出耗時

| 項目 | 數值 |
|---|---|
| **完整匯出耗時** | `real 14.90` 秒、`⏱️ 14.7` 秒（`iter03_export_time.log`）；最終 `real 14.67` 秒、`⏱️ 14.5` 秒（`iter03_export_final.log`）；`collect` 內 14.8、14.2 秒 |
| `latest.json` | 673,566 → **674,502 bytes，+936 B**（上限 5 KB） |
| `status` 區塊 | **913 B**（上限 5,120 B） |
| 個股 JSON 合計（1,999 檔） | 28,320,065 bytes（第 2 輪紀錄 28,320,851） |
| 匯出後暫存檔殘留 | 0 |

---

## 四、與設計文件不同之處

程式與文案都照設計。下面是執行方式或實測與設計描述不一致的地方：

1. **T-S3-15 沒有執行 `install_schedule.sh --print`**：本輪的硬性限制是不執行這支腳本。改用 `sed` 只取出 `render_plist` 函式（確認其中沒有 `launchctl`）來產生 plist，再跑 `plutil -lint` 與設計的斷言，全部通過。`--print` 分支本身沒有實際跑過，只由 `test_schedule_scripts_static` 靜態確認它排在 `launchctl bootout` 之前。**QA 可視權限實跑 `--print`。**
2. **`collect --date 2026-10-30` 執行了兩次**：第一次因 `openapi.twse` 異常回傳 1（第二節之 3）。設計只預期一次。
3. **`collect_runs` 多一筆異常紀錄**：`run_id=1` 是 `abnormal`，保留原樣沒有刪除。`run_id=2`（ok）、`run_id=3`（catch-up，ok）是之後的紀錄。
4. **「更新於」目前是 2026-10-31 13:13**，來自 `run_id=1`：這次 `new_data=1` 是因為 S6 改了 5236、8908 的市場別，快照因此不同，並不是收到新行情。後兩次 `new_data=0`，所以沒有再更新。這是設計規則的結果，不是錯誤。
5. **F1 的兩行延後啟用**：為了把 S6 與 F1 對家數的影響分開記錄，我先套用完整的 `export.py` diff，再暫時還原 `_changes`、板塊 `pct` 兩行，到步驟 10 才改回。最終檔案與設計 diff 完全相同。
6. **檔案修改順序**：回補期間就先修改了 `export.py`、前端、腳本與 README（只改檔、不執行，不影響已載入的回補程序）。**資料操作的順序完全照設計**。
7. **zsh 沒有 `PIPESTATUS`**：這台機器的 shell 是 zsh，設計範例的 `${PIPESTATUS[0]}` 取不到值。回傳碼改為重跑一次或用 `$?` 取得，並附加在 log 最後一行（`rc=…`）。
8. **S6 的連帶影響（設計未提及）**：見第六節第 3 點。匯出訊息由「還原事件 1721 筆（上櫃反推 29 筆）、未對到 2 筆」變成「**1719 筆（上櫃反推 27 筆）、未對到 4 筆**」。
9. **設計數字的小差異**：
   - S3-4 寫 2025-10 在驗收範圍外的櫃買指數是 21 筆，實際 **18 筆**（10/01～10/29；`TPEX` 共 260 列 = 242 + 18）。
   - S1-5 預期的開頭輸出正確；T-S2 回補後 `上櫃本益比` 筆數實際 894（S6 後 892），設計寫「約 890」。
   - S4-4 寫手機橫幅高約 59px，單行時實測 **35.5px**（橫幅文字較長或多行時會變高）；`left 16`、`right 359` 相同。
10. **A1-補漏的完成訊息**：`history --only tpex_index` 印「待抓 0 天」與「✅ 成功：0 天」，下面才列 12 個月。程式照設計，資料正確（第五節），只是訊息容易誤解，建議下一輪調整。

---

## 五、驗收範例實際數值

### S1
| 項目 | 實際值 | 預期 |
|---|---|---|
| 5904 2026-10-30 本益比／殖利率 | 20.14／3.51 | 相同 |
| 3564、6486、6147 2026-10-30 本益比 | 87.91、9.14、36.03 | 相同 |
| 1240 2025-10-30 本益比／淨值比／殖利率 | 11.63／1.69／5.94 | 相同 |
| 5904 2026-10-29 本益比／淨值比 | 20.22／9.37 | 相同 |
| 上櫃 `fund.date`=10/30 且 `fund.dy` 非空 | **892 檔** | ≥ 850 |
| 5904 個股頁 | 本益比 20.14、殖利率 3.51%；兩卡皆為「資料 10/30；08/10 股本變動，官方值可能尚未調整」；淨值比卡不動 | 相同 |
| 虧損股（1569、3086）本益比卡 | `--`，「官方未提供；資料 10/30」 | 相同 |

### S2
| 項目 | 實際值 |
|---|---|
| 基線 | rc=1；上櫃本益比 10/30 筆數 2、殖利率填充率 0.2%、櫃買指數缺 2026-09-30 |
| 回補後 | rc=0；上櫃本益比 76%／100%／100%；櫃買指數 20/20 |

### S3（A1-補漏）
| 項目 | 實際值 | 預期 |
|---|---|---|
| 櫃買指數 2025-10-30～2026-10-30 | 242 天，與 `trading_days` 差集為空 | 相同 |
| 2025-11-03 收盤 | 265.68 | 相同 |
| 2026-09-01 收盤／漲跌 | 410.77／+9.07 | 相同 |
| 2026-10-30 收盤／漲跌 | 370.26／**−17.11** | 相同 |
| 櫃買指數卡 | 「近 60 個交易日 +2.0%」（修改前「自 10/01 起 −11.6%」） | ±x.x% |

### S4（瀏覽器，時間與 `status` 都只在記憶體模擬）
| 情境 | 實際值 |
|---|---|
| 2026-10-31 週六、資料 10/30 | 不顯示 |
| 2026-11-02 17:00 | 不顯示 |
| 2026-11-02 18:30（含 `10:30Z` 寫法） | 「資料停在 10/30，最新交易日為 11/02，可能尚未收集」 |
| 2026-12-25 上午、晚上，資料 12/24 | 不顯示 |
| 2026-12-28 18:30，資料 12/24 | 「資料停在 12/24，最新交易日為 12/28，可能尚未收集」 |
| 2026-10-26 19:00，資料 10/22（連假＋臨時休市） | 不顯示 |
| 2026-10-27 18:30，資料 10/22 | 「資料停在 10/22，最新交易日為 10/27，可能尚未收集」 |
| 局部提示 | 「部分資料異常：上櫃本益比停在 10/29」，頁面其他部分正常 |
| 連續兩次 `export` | `updated_at` 皆為 13:13:13；`exported_at` 13:16:12、13:16:27 |
| `visibilitychange` 邏輯（呼叫 `recheckLatest`） | 「網站資料已更新（資料日 11/02）」＋按鈕，網址未變 |
| 舊版 `latest.json` | 橫幅隱藏，日期列正常 |
| 375px | 首頁、個股頁 `scrollWidth` 375；橫幅 left 16、right 359 |
| console | 首頁、5904、2330、5236 個股頁與其他分頁皆無 error |
| 日期列 | 「資料日 2026-10-30　法人資料 2026-10-30　更新於 2026-10-31 13:13」，來源 `run` |

### S5
官方與手寫表 2026 **零差異**（18 天）；`trading_days` = 242；端點失敗、2027 無日曆、同年不重複請求、10/23 臨時休市都由單元測試涵蓋。

### S6
| 項目 | 修改前 | 修改後 |
|---|---|---|
| 5236、8908 `market_type` | TPEx | **TWSE** |
| 上市 漲／跌／平 | 94／945／46 = 1,085 | 94／**947**／46 = **1,087** |
| 上櫃 漲／跌／平 | 127／693／56 = 876 | 127／**691**／56 = **874** |
| 合計 | 1,961 | **1,961** |
| 成交額 | 上市 8,148.1 億、上櫃 1,987.8 億 | 上市 8,148.2 億、上櫃 1,987.7 億 |

F1 之後家數相同，`latest` 的 `ch` 全部與修改前相同。

### F1
| 項目 | 實際值（收盤、漲跌、幅度） | 預期 |
|---|---|---|
| 6762 2026-07-13 | 170、**+2.5**、1.49% | 相同 |
| 4968 2026-07-13 | 108.5、**−1.5**、−1.36% | 相同 |
| 6669 2026-09-02 | 2,610、**−5**、−0.19% | 相同 |
| 2317 2026-07-02 | 239、**−2**、−0.83% | 相同 |
| 5904 2026-07-16 | 623、**−29**、−4.45% | 相同 |
| 事件日與官方比對（T-F1-2） | **61／61**，無差異 | 全部吻合 |
| 還原不變（T-F1-3） | 6669、5904、3086、2330、6762 的開高低收與 `ev` 完全相同 | 相同 |
| 52 週高低 | 6669 2,875／1,071.94；5904 92.3／37.77；3086 47.5／20.05 | 相同 |
| 5904 10/30 訊號卡 | 「**中性：3 多 3 空**」，class 只有 `signal` | 相同 |
| 偏多、偏空顯示 | 1569「偏多：4 多 2 空」；2330「偏空：0 多 6 空」，配色維持 | 不變 |

---

## 六、已知限制

1. **排程沒有安裝**，自動收集要等使用者執行（第八節）。真實排程環境下的 `RunAtLoad`、`caffeinate`、launchd 的路徑與環境都**沒有實測**。
2. **Windows 批次檔未實測**：只做靜態檢查（CRLF、時間、`--catch-up`）。`schtasks` 指令、`set ARGS=%*` 的引號處理都沒有在 Windows 跑過。
3. **S6 改變了 5236、8908 的還原結果**：這兩檔原本被錯標為上櫃，5236 的 2026-07-16、8908 的 2026-10-16（官方漲跌 0、收盤 ≠ 前收，推測是轉上市首日，未向官方確認）被反推成假事件。修正市場別後：
   - 這兩天改顯示「不比價」，漲跌家數算平盤。
   - 52 週高低改變：5236 179.64／100.47 → **184.35／103.1**；8908 47.37／37.74 → **46.9／37.37**。比例剛好等於假事件的係數（156.5／152.5、40.2／39.8）。
   - 全部 1,999 檔中，52 週高低有變動的**只有這兩檔**。
4. **一個主機異常會連帶影響同主機的資料集**：`openapi.twse` 同時供應處置／注意股、月營收、產業別，異常時三者都失敗（符合設計）。處置／注意股只查得到近幾日，如果異常持續超過窗口，那幾天的資料會永久缺少。
5. **週末 TWSE 注意股端點只回一筆空白佔位列**（`Code` 空字串，由 `is_valid_stock_code` 濾掉）。`stock_alerts` 的 `notice` 最新日期仍是 10/30。
6. **通知只有 mock 測試**：沒有實際跳過 `osascript` 通知，`logs/notify_state.json` 目前不存在。
7. **官方休市表只有當年**；2027 年要等官方切換，手寫表也沒有 2027 年。每年年底要確認（README 已寫）。
8. **臨時休市當晚**橫幅可能出現，隔天 catch-up 登記後才消失（設計 S4-5）。
9. **`--catch-up` 只看窗口內**（預設 10 個交易日）；窗口外的局部缺口要用 `check --days N` 查。`check` 的 `amount` 只看近期，2026-07-31 以前的官方法人金額沒有補。
10. `site/data/stocks/` 的 14 個停牌／下市股票檔、第 2 輪留下的邊界情況維持不動（PM 待辦）。

---

## 七、給 QA 的注意事項

1. **先強制載入新版 JS**：`await fetch('app.js', {cache:'reload'}); await fetch('stock.js', {cache:'reload'}); location.reload()`。CSS 也可能被快取。
2. 埠用 8001，結束時關閉。`python3 -m twstock setup-db` 已執行，本機不需再跑。
3. **不要同時跑 `history` 與 `collect`**：`history` 會回傳 1，`--catch-up` 會略過。
4. **T-S1-4 不要在現在重新快照比對**：S6 之後 5236、8908 會出現在 TWSE 快照中。用留存的 `logs/iter03_fund_before.json` 與 `iter03_fund_after.json`，或排除這兩檔。
5. **第 2 輪舊預期值已被取代**：6669 −4.99 → −5；2317 −1.82 → −2；另外 5904 7/16 −28.5 → −29；上市家數 94／945／46 → 94／947／46；上櫃 127／693／56 → 127／691／56。
6. **T-S3-15** 我沒有實跑 `--print`（第四節第 1 點），請依你的權限決定是否實跑。不帶參數或 `--uninstall` 都會動到 launchctl，**不可執行**。
7. **T-S3-14** 已在 `run_id=2` 之後做過；重跑時今天的月營收與處置注意股都已有紀錄，預期仍是 0 請求（2026-10-31 當天）。若跨到下一個交易日，結果會不同，屬正常。
8. **T-F1-5、T-S4-1** 依賴資料到 10/30。若已有新資料，依設計註解調整。
9. `recheckLatest` 有 60 秒節流，測試要先設 `App.checkedAt = 0`。S4 測試都只改記憶體。
10. **第 1 輪 A1 驗收 4**：`market_index` 10/30 的值已經過 `collect --date` MERGE，數值相同；`created_at` 不會被 MERGE 更新，可依 PM 第四節比對。
11. 外部請求節流：本輪對 `openapi.twse` 有一段異常（第二節之 3），驗收時如果再次遇到，不要高頻重試。

### 第 2 輪文件更正附註（歷史文件不回頭修改）
- **T-P14-8**：第一段的正確預期是「排除事件生效日後為 0」，或「22，且全部是事件日收盤＝參考價」。第 2 輪 `03-design.md` 寫的「印 0」是測試案例的錯誤。
- **`02/04-dev.md`「24 筆」的口徑**：當時的統計口徑沒有留下紀錄，本輪無法重現。**以第 2 輪 QA 的口徑為準（官方漲跌有數值且非 0：45 筆可比對、9 筆有差異）**。本輪 F1 後事件日與官方比對 61／61 吻合，這項差異已消失。

---

## 八、使用者需要自行執行的事項

**程式不會自動做這些事，我也沒有執行。**

| # | 動作 | 指令 | 不做的後果 |
|---|---|---|---|
| 1 | 安裝排程（安裝當下會立刻執行一次；只看內容不安裝可加 `--print`） | `bash scripts/mac/install_schedule.sh` | 沒有自動收集，只能手動；網站橫幅會提示資料落後 |
| 2 | 資料庫容器自動重啟，並在 Docker Desktop 設定開機啟動（目前 restart policy 是 `no`） | `docker update --restart unless-stopped MySqlServer` | 重開機後收集失敗（回傳 2），直到手動啟動容器 |
| 3 | （選用）固定喚醒，需要管理者權限 | `sudo pmset repeat wakeorpoweron MTWRF 17:25:00` | 只影響當天晚上是否有資料；喚醒後 `--catch-up` 會補齊 |
| 4 | Windows 主機（若有） | `scripts\windows\install_schedule.bat` | 未實測，建議先手動跑一次 `collect.bat` |

其他提醒：
- 其他電腦部署時要執行一次 `python -m twstock setup-db`（新表 `collect_runs`、`market_holidays`）。
- `_archive/config.py` 請維持改名後的狀態。
- PM 第六節提到的 `tw-stock-collector` skill 是否使用舊邏輯，目前仍未確認。它若直接寫同一個資料庫，可能又把資料蓋壞；`check` 能事後偵測，請考慮停用或確認。
- 資料庫備份：`_backups/TwStock_before_round3.bak` 是本輪回補前的狀態，之後的資料沒有備份（S9 排在第 4 輪）。

---

## 九、QA 修正（依 `05-qa.md`，2026-10-31）

只修 QA-01、QA-02 與第五節 (d) 的排程腳本參數；**QA-03～QA-07 留到第 4 輪，未修改**。未重新 `collect` 行情，`collect_runs` 最新仍是 `run_id=3`；沒有安裝或移除排程。

### 修改位置（檔案:行號）

**QA-01：休市表端點失敗不可拖累同主機的上市資料**

| 位置 | 修改 |
|---|---|
| `twstock/fetch.py:83`、`:90`、`:109` | `request` 新增 `isolated` 參數：失敗不重試、不加入 `_dead_hosts` |
| `twstock/tradingcal.py:73`、`:81` | `update_calendar` 用 `isolated=True` 請求 |
| `twstock/tradingcal.py:96-99` | 失敗時回傳警告文字；已有當年官方表時印「沿用已存的官方表」，沒有才印「改用手寫表」 |
| `twstock/collectors/catchup.py:215`、`:310-311` | 警告寫入 `collect_runs.detail.warnings`（新欄位，設計沒有；回傳碼仍依資料狀態） |

**QA-02：判定臨時休市後，網站要拿得到 `status.closed`**

| 位置 | 修改 |
|---|---|
| `twstock/health.py:282`、`:293` | 抽出 `site_closed()`，`build_status` 與收集流程共用同一份計算 |
| `twstock/collectors/catchup.py:147`、`:154` | `status_changed(status_now, closed_now=None)` 也比對 `closed` |
| `twstock/collectors/catchup.py:273` | 寫入判定後重新讀日曆 |
| `twstock/collectors/catchup.py:293-296` | 匯出判斷加入 `closed`；起點用兩市場最新日，與 `export` 的資料日相同 |
| `site/app.js:686` | `recheckLatest` 直接換新 `status`：已開著的頁面回到前景，橫幅就會消失，不用重新整理 |

沒有採用 QA 建議的「判定時設旗標」，因為比對 `closed` 還涵蓋：匯出失敗或 `--no-export` 後下次補匯出、官方休市表更新。兩者都**不計入 `changed`，所以「更新於」不變**。

**排程腳本：未知參數不可安裝**

| 位置 | 修改 |
|---|---|
| `scripts/mac/install_schedule.sh:8-15` | 開頭 `case`：只接受無參數、`--print`、`--uninstall`；其他情況（含多餘參數、空字串、`-h`）印用法，`exit 2`。第一個 `launchctl` 在第 50 行 |
| `scripts/windows/install_schedule.bat:5-12` | 同樣的問題：原本未知參數會先刪除工作再安裝。改為在任何 `schtasks` 之前檢查，`exit /b 2`；維持 CRLF |
| `README.md:77-78`、`:108` | 註明其他參數只印用法；更正休市表失敗時的行為 |

**測試（`tests/test_iter03.py`，不連網、不連資料庫、不安裝）**

| 位置 | 內容 |
|---|---|
| `:971` `test_request_isolated` | 200＋HTML、真實退避參數：`isolated` 只請求 1 次且不標記；一般請求 4 次並標記 |
| `:1008` `test_qa01_calendar_failure_isolated`（`:993` `CalBroken`） | 休市表回 500、HTML、欄位改名三種情況，用真實退避參數跑 `catchup.run`：上市五個資料集都寫入，rc=0，休市表只請求 1 次，主機未標記，已存官方表保留，`warnings` 有紀錄 |
| `:1066` `test_qa02_adhoc_reaches_site`（`:1034` `run_site`、`:1055` `fresh_lines`） | 週一颱風、週五颱風兩個情境：真實的 `status_changed`、`build_status`；匯出 1 次、`closed` 含該日、`collected_at` 不變、`new_data=0`、再跑不重複匯出；用 node 跑 `app.js` 真正的 `freshLines`（沒有 node 時跳過這部分） |
| `:1095` `test_qa02_status_changed_closed` | `closed` 相同、新增、移除、未傳、舊版 `latest.json` |
| `:1107` `test_schedule_unknown_arg` | 只執行第一個 `launchctl` 之前的副本（先斷言副本內沒有 `launchctl` 指令）；Windows 只做靜態順序檢查 |
| `:573`、`:601` | 配合修改：保留真的 `status_changed`；`env()` 的 mock 改收任意參數（第 2 個參數造成的必要修改，其他既有測試未動） |

`test_update_calendar` 等既有測試都沒有改預期值。

### 驗證結果

| 項目 | 結果 |
|---|---|
| `test_iter01`、`test_iter02`、`test_iter03` | 全部通過（`test_iter03` 由 43 個增為 **48 個**） |
| `py_compile`、`node --check`、`bash -n` | 通過；`.bat` 為 CRLF |
| `python3 -m twstock export`（`logs/iter03_export_qafix.log`） | `real 14.81` 秒、`⏱️ 14.6` 秒；`latest.json` 674,502 bytes、`status` 913 B；`updated_at` 仍是 13:13:13 |
| `python3 -m twstock check`（`logs/iter03_check_qafix.log`） | **rc=0，「結果：無異常」** |
| 不會重複匯出（唯讀，真實資料庫與 `latest.json`） | `status_changed(...)` = **False** |
| 變異檢查（暫存副本） | 拿掉 `isolated=True`、拿掉 `closed` 比對、拿掉未知參數分支，對應測試都會失敗 |

**瀏覽器（8001，時間與資料只在記憶體模擬，已關閉）：**

| 情境 | 結果 |
|---|---|
| 週一 11/02 颱風，週二 10:00，已開著的頁面 | 回前景前「資料停在 10/30，最新交易日為 11/02…」；`recheckLatest` 取得新 `closed` 後橫幅消失，沒有重新整理提示，網址未變 |
| 週五 11/06 颱風，資料日 11/05 | 沒有 `closed` 時週六會誤報；有 `closed` 時週六、週日、週一 17:59 都不顯示；週一 18:00 顯示「資料停在 11/05，最新交易日為 11/09…」 |
| 既有行為 | `latest.json` 讀取失敗時靜默；有新資料時仍提示重新整理；console 無 error |

**排程腳本如何驗證，沒有安裝：**
- Mac：`launchctl` 在第 50 行、參數檢查在第 8～15 行（靜態確認）。先由測試跑不含 `launchctl` 的副本，再以**真實腳本**帶 `--preview`、`-p`、`--Print` 各跑一次，環境是 stub `launchctl`（已確認 `command -v` 解析到 stub）與暫存 `HOME`。三次都 **rc=2、印用法**；stub 沒有被呼叫，暫存 `HOME` 是空的。
- 真實腳本**沒有**帶無參數、`--print`、`--uninstall` 執行；`--print` 只在副本上跑過。
- 之後 `launchctl list | grep twstock`、`~/Library/LaunchAgents` 都沒有結果。
- **Windows：只做靜態檢查，未實測**（`if`／`goto` 順序、`exit /b 2`、CRLF）。

### 限制與行為變更

- **休市表端點的失敗只有 mock 驗證**，真實端點目前正常，沒有等它壞掉。
- **臨時休市流程只有 mock**：資料庫沒有寫入任何 `adhoc` 列。
- `isolated` 不重試：喚醒後網路還沒好時，這次就跳過日曆更新，下次排程再試（30 天到期後，失敗期間每次多 1 個請求）。
- 官方休市表內容有變時，即使沒有新資料也會匯出一次。這是新行為，也是橫幅正確所必需的。
- 颱風**當晚**尚未判定時，橫幅仍可能出現（設計 S4-5，未改變）。
- `db.py` 的 `detail` 註解沒有列 `warnings`（在 DDL 字串內，未修改）。
- 附帶說明：變異檢查的暫存副本誤含一份 `.env`，檢查結束就隨副本刪除；專案的 `.env` 沒有變動，也沒有讀取或輸出內容。

## 十、QA 修正：QA-08（依 `05-qa.md` 第十節，2026-10-31）

**問題**：`export_all` 早於 `write_run`，匯出時讀到的「最後一次 `new_data=1`」是上一次收集，「更新於」落後一次。

**修法**：先寫紀錄再匯出，匯出後再補結果。`export_all` 簽名不變，`updated_at` 仍只由資料庫決定。

| 檔案:行號 | 修改 |
|---|---|
| `twstock/collectors/catchup.py:290`～`:299` | `finished`、`detail`、`write_run` 移到匯出前並 commit |
| `twstock/collectors/catchup.py:314`～`:321` | 有匯出時才呼叫 `finish_run`，寫入耗時與匯出失敗後的結果 |
| `twstock/health.py:166` | `write_run` 不再收 `export_seconds`，改為回傳 `run_id`（`OUTPUT INSERTED.run_id`） |
| `twstock/health.py:173` | 新增 `finish_run`，只更新 `outcome`、`export_seconds`，不動 `finished_at` |
| `tests/test_iter03.py:884` | `test_run_record` 配合新簽名，並檢查 `finish_run` 不動 `finished_at` |
| `tests/test_iter03.py:1120` | 新增 `test_qa08_updated_at_is_this_run`；`FakeCursor`、`run_site` 配合調整 |

**行為**（`test_qa08_updated_at_is_this_run`，真實執行順序與 `build_status`）：

| 情境 | `new_data` | 匯出 | 「更新於」 |
|---|---|---|---|
| 17:30 行情公布、19:30 法人公布 | 1 | 有 | 當次的 `finished_at` |
| 21:45 沒有新資料 | 0 | 無（也沒有 UPDATE） | 不變 |
| 全部來源失敗（rc=1） | 0 | 依原判斷 | 不變 |
| 部分失敗但有寫入新資料（rc=1） | 1 | 有 | 當次的 `finished_at` |
| 臨時休市判定後匯出（QA-02，既有測試未改） | 0 | 有 | 不變 |
| 匯出失敗（rc=1） | 1 | 失敗，`outcome` 改為 `abnormal`、`export_seconds` 為 NULL | 網站維持舊檔；下一次補匯出後為該次收集時間 |

**定義變更與已知後果**：

- `finished_at` 由「匯出完成」改為「收集完成、匯出之前」，不含匯出耗時。設計第 757 行「最後一次 `new_data=1` 的 `finished_at`」的算法不變。
- 匯出中途行程被強制終止時，紀錄已寫入，`outcome` 維持收集結果、`export_seconds` 為 NULL，不會標為異常。下次收集仍會由 `status_changed` 比對網站與現況來決定是否補匯出。此情境沒有測試。
- `collect --date` 重抓相同資料（一定匯出、`new_data=0`）走相同路徑，沒有單獨的測試。

**驗證**：

| 項目 | 結果 |
|---|---|
| `tests/test_iter01.py`／`02`／`03` | 5／8／49 通過，0 失敗 |
| `py_compile`、`node --check site/app.js site/stock.js` | rc=0 |
| `python3 -m twstock check` | rc=0，無異常 |
| `python3 -m twstock export` | rc=0，耗時 15.4 秒；`updated_at` 維持 `2026-10-31T13:13:13+08:00` |
| 變異檢查（副本只含 `twstock`、`tests`、`site`、`scripts`，未複製 `.env`，用畢刪除） | 恢復舊順序、`new_data` 一律為 1、匯出失敗不標異常，三者測試皆失敗 |
| 真實資料庫驗證 `write_run`＋`finish_run` 的 SQL（同一交易內執行後 rollback） | 取得 `run_id`、更新成功；rollback 後仍為 3 筆 |

**未驗證與副作用**：

- 未以真實收集跑過完整流程（依限制不重新 collect 行情），第一次實際驗證是 11/02 的收集。
- 上述 rollback 不會退回 IDENTITY，下一筆 `run_id` 會是 5（跳過 4），不影響功能：`load_state` 只依 `run_id` 排序。
