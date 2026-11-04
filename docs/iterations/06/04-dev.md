# 第 06 輪｜Programmer：實作紀錄

- 撰寫日期：2026-11-04（週三）晚間
- 依據：
  - `03-design.md`：實作依據，含附錄 B SQL、附錄 C diff、附錄 D 測試、附錄 E 工具。
  - `02-pm.md`：範圍與驗收條件。
- 本輪項目：F6-1（來源無持股清單／無明細不算缺，QA-01）、F6-2（隔離比對工具，QA-02）、S9（`backup` 指令），全部完成。README、`.env.example` 已照設計第七節修改。
- 程式來源：
  - 附錄 C 的 diff 用 `git apply` 分兩次套用。
    - 先套 `twstock/backup.py`、`twstock/__main__.py`，用新指令備份。
    - 再套 `db.py`、`collectors/holdings.py`、`collectors/daily.py`、`health.py`，然後執行 `setup-db`。
  - `tests/test_iter06.py`、`logs/iter06_compare.py` 直接從附錄 D、E 取出。
  - 收尾時逐檔比對：6 個程式檔、測試與工具都**與 SA 原型完全相同**。
- 守則：
  - 沒有 commit、push，沒有動 `.env`（只改 `.env.example`）與 `_archive/`。
  - 沒有安裝排程，沒有改系統或 Docker 設定。
  - **沒有執行任何還原**，沒有刪除既有備份。
  - 本輪沒有前端變更，沒有開 8001 埠；8000 埠沒有動。

> **結論**
> - **改表前的備份就用新指令**：`../_backups/TwStock_20261104_213027.bak`，79.5 MB，`RESTORE VERIFYONLY` 通過，`is_copy_only = 1`（S9 #7）。
> - **標記 8 個已知日期**：`history` 標記 8 筆，原因全部正確（A 5 筆、B 3 筆）。接著 `check` **rc=0**，第 5 輪 QA-01 解決。
> - 附錄 B-1～B-3 的 SQL 全部相符。00988A 10/21 的 `nav` 實際值是 47,148,508,495（設計只要求 > 0）。
> - 隔離比對「✅ 相同」：`latest.json`、`stocks` 1,999 檔、`etfs` 4 檔。
> - `test_iter01`～`06` 全部通過。
> - **與設計不同的地方只有 1 處**：設計步驟 5 的指令沒有加 `--end`，預設跑到今天，所以多發 2 次請求，重跑也不是 0 次。原因與驗證見第三節。程式沒有修改。

---

## 一、各項目修改內容

| 項目 | 檔案 | 內容 |
|---|---|---|
| F6-1 | `twstock/db.py` | 新表 `etf_holding_gaps`；`setup_database` 的列表加上這張表 |
| F6-1 | `twstock/collectors/holdings.py` | `Gap`、`GAP_REASON`、`parse_pcf(data, d, post, today)` 的 A／B 判斷、`fetch_holdings` 傳入生效日與今天、`merge_holdings` 寫明細時一併刪 gap、`merge_gap` |
| F6-1 | `twstock/collectors/daily.py` | `_collect_key` 收到 `Gap` 時寫入並回傳 0；`collect_for_date` 另印「來源無持股明細（不算缺）」 |
| F6-1 | `twstock/health.py` | `Row.gap`；`load_snapshot` 讀 gap 表；`assess` 遇 gap 為齊全；`check_report` 的涵蓋數與「不算缺」一行 |
| S9 | `twstock/backup.py`（新檔，92 行） | `find_container`、`backup`、`run` |
| S9 | `twstock/__main__.py` | `cmd_backup`、子指令 `backup --out --direct`、docstring |
| F6-2 | `logs/iter06_compare.py`（不進版本控制） | 附錄 E |
| 測試 | `tests/test_iter06.py`（新檔，485 行，16 個測試） | 附錄 D |
| 文件 | `README.md` | 設計第七節 7 項：`tests/` 列、新增資料表、`backup` 指令列、測試列、主動型 ETF 持股、資料完整性、新段落「備份與還原」 |
| 文件 | `.env.example` | `DB_CONTAINER` 註解範例 2 行 |

本輪程式差異（相對第 5 輪完成時）：新增 185 行、刪改 11 行（不含測試）。

---

## 二、執行過的指令與結果（台灣時間）

### 1. 依序執行的資料操作

| 時間 | 設計步驟 | 指令 | 結果 | 紀錄 |
|---|---|---|---|---|
| 21:30 | 0 | `git apply` 只套 `backup.py`、`__main__.py` → `python3 -m twstock backup` | `✅ 備份完成並通過 RESTORE VERIFYONLY：…/_backups/TwStock_20261104_213027.bak（79.5 MB）`。既有 3 份大小與時間不變 | `logs/iter06_backup.log` |
| 21:30 | 1 | `export`，複製 `latest.json`、`stocks/`、`etfs/` 到 `logs/iter06_before/` | 資料日 11/04 | — |
| 21:31 | 2 | `check` | rc=1，只有 `00411A持股：缺 2026-10-21`、`00988A持股：缺 2026-10-21`（涵蓋 18/19） | `logs/iter06_check_before.log` |
| 21:31 | 3 | `git apply` 其餘 4 檔 → `setup-db` 兩次 | 兩次 rc=0；`etf_holding_gaps` 0 筆；既有 7 張表的筆數不變（見下方說明） | `logs/iter06_counts_*.log` |
| 21:31 | 4 | `test_iter01`～`06` | 全部通過 | `logs/iter06_test_0*.log` |
| 21:31 | 5 | `history --start 2025-10-30 --only holdings` | 待抓 8 天，10 次 `GetPCF`。8 個已知日期都印「ℹ️  來源無持股明細（不算缺）」，原因正確；另外 11/04 印「官方尚無資料：holdings.00411A、holdings.00988A」（第三節） | `logs/iter06_history.log` |
| 21:32 | 6 | 同一指令重跑 | 待抓 1 天（11/04，跨境 2 檔），2 次 `GetPCF`（第三節） | `logs/iter06_history_rerun.log` |
| 21:32 | 6' | `history --start 2025-10-30 --end 2026-11-03 --only holdings` | **待抓 0 天，0 次請求**（F6-1 #2） | `logs/iter06_history_rerun_end1103.log` |
| 21:32 | 7 | `check`；附錄 B 的 SQL | **rc=0**，「結果：無異常」；00411A、00988A 的涵蓋都是 19/19；另列「ℹ️  投信沒有持股明細（不算缺）：00411A持股 2026-10-21（只有彙總）、00988A持股 2026-10-21（只有彙總）」 | `logs/iter06_check_after.log`、`logs/iter06_sql.log` |
| 21:32 | 8 | `collect --catch-up` | 「✅ 最近 10 個交易日資料齊全，不需要請求」，0 次請求，「沒有新資料，不匯出」，rc=0（F6-1 #3） | `logs/iter06_catchup.log` |
| 21:32 | 9 | `export` → `python3 logs/iter06_compare.py logs/iter06_before site/data` | 「✅ 相同」，rc=0 | `logs/iter06_compare.log` |
| 21:32 | 10 | S9 其餘驗收（第四節） | 全部符合 | `logs/iter06_s9.log` |

- 步驟 0 的 log 沒有記到 rc：zsh 的 `PIPESTATUS` 是空的，之後改用 `pipestatus`。輸出「✅ 備份完成」只在 `run()` 回傳 0 時才會印出，而且步驟 10 用同一個指令連跑兩次，兩次都是 rc=0。
- 步驟 3：`logs/iter06_counts_before.log` 最後一行的 `???` 是 PG 查詢腳本把中文「不存在」放在 `varchar` 裡造成的亂碼。表示當時這張表還不存在，和程式無關。
- 既有表筆數（`setup-db` 前後相同）：

  | 表 | 筆數 |
  |---|---|
  | `stocks` | 1,999 |
  | `daily_prices` | 479,348 |
  | `etf_holdings` | 30,525 |
  | `etf_holding_summary` | 642 |
  | `market_breadth` | 4 |
  | `collect_runs` | 6 |
  | `market_holidays` | 24 |

### 2. 外部請求統計

| 指令 | `GetPCF` | 其他 |
|---|---|---|
| `history`（步驟 5） | 10：8 個已知日期 8 次，加上跨境 2 檔的 11/04 2 次 | 0 |
| `history` 重跑（步驟 6） | 2：跨境 2 檔的 11/04 | 0 |
| `history --end 2026-11-03`（步驟 6'） | 0 | 0 |
| `collect --catch-up`（步驟 8） | 0 | 0 |
| **合計** | **12** | **0** |

- 全部經過 `fetch.request`，有節流（間隔 3 秒）。沒有重試、沒有被拒。
- `backup`、`check`、`export` 都不連外。

### 3. 測試

- `test_iter01`～`test_iter06` 全部通過。`test_iter06` 有 16 個測試。
- `pytest` 沒有安裝，用 `python3 tests/test_iter0N.py` 執行。

---

## 三、與設計不同：步驟 5、6 多出 11/04 的請求

### 1. 現象

設計步驟 5、6 的指令是 `history --start 2025-10-30 --only holdings`，預期「8 次請求、重跑 0 次」。實際是第一次 10 次、重跑 2 次，多出來的都是**跨境 2 檔的 11/04**。

### 2. 原因

- 沒有 `--end` 時，`history` 會跑到今天，也就是 11/04。
- 跨境 ETF 11/04 的持股要到 11/05 晚上才公布，但 `history` 判斷待抓時不考慮 `delay`。這是第 5 輪就有的行為：`missing_keys` 沒有傳 `days`，見第 5 輪設計 E2-1-5 與 `test_e2_due_and_status`。
- 所以 11/04 被當成待抓。回應是「尚未公布」，程式照規則印「官方尚無資料」，**不寫入、也不記 gap**。這部分的判斷是正確的。
- 本輪的 gap 判斷沒有問題：8 個已知日期第一次就全部記錄，重跑時都沒有再請求。

### 3. 驗證與處理

- 改用 `--end 2026-11-03` 重跑：**待抓 0 天、0 次請求**，符合 F6-1 #2 的本意。
- PG **沒有修改程式**。這是設計文件指令的疏漏：應該寫成 `--end` 前一個交易日。
- 建議 QA 重跑時使用：

  ```bash
  python3 -m twstock history --start 2025-10-30 --end 2026-11-03 --only holdings
  ```

- 若 QA 在 11/05 晚上 17:30 後執行，`--end` 也可以改成 11/04。
- 是否讓 `history` 對跨境 ETF 也考慮 `delay`，交給 QA／PM 判斷（本輪範圍外）。

---

## 四、驗收數值

### F6-1（`logs/iter06_sql.log`）

**B-1** `etf_holding_gaps`，8 列，和設計附錄 B-1 相同：

| etf_code | hold_date | reason | src_date | post_date | nav |
|---|---|---|---|---|---|
| 00988A | 2025-11-27 | A | 2025-11-26 | 2025-12-01 | NULL |
| 00988A | 2026-01-19 | A | 2026-01-16 | 2026-01-21 | NULL |
| 00988A | 2026-02-10 | A | 2026-02-11 | 2026-02-23 | NULL |
| 00988A | 2026-05-25 | A | 2026-05-22 | 2026-05-27 | NULL |
| 00988A | 2026-07-08 | B | 2026-07-08 | 2026-07-13 | 59853545462.00 |
| 00411A | 2026-09-07 | A | 2026-09-04 | 2026-09-09 | NULL |
| 00411A | 2026-10-21 | B | 2026-10-21 | 2026-10-27 | 4684340379.00 |
| 00988A | 2026-10-21 | B | 2026-10-21 | 2026-10-27 | 47148508495.00 |

- A 的 `src_date` 已存的明細列數：52、38、46、47、36，和預期相同。
- **B-2**：gap 日期的明細 0 列、彙總 0 列（F6-1 #4）。
- **B-3**：4 檔的天數、起訖日、明細列數和設計的 21:30 值完全相同（00403A 120／6,014、00411A 43／1,420、00981A 245／12,482、00988A 234／10,609）。

### S9（`logs/iter06_s9.log`）

| 驗收 | 結果 |
|---|---|
| #1 | 步驟 0：83,398,656 B，VERIFYONLY 通過；既有 3 份不變 |
| #2 | 連跑兩次 `--out <scratchpad>`：`TwStock_20261104_213255.bak`、`TwStock_20261104_213301.bak`，兩次 rc=0、不同檔名。同名衝突由 `test_s9_ok_and_cleanup` 驗證 |
| #3 | `--out` 正常（同上）。驗完已刪除這 2 份暫存備份 |
| #4 | 實測 `DB_CONTAINER=no-such-container`：`❌ docker inspect 失敗（Docker 是否已啟動？）：Error: No such object: no-such-container`，rc=1，沒有產生檔案、沒有 Traceback。沒有 docker、找不到或找到多個容器、容器沒在跑：由 `test_s9_docker_problems` 驗證（沒有真的停掉容器） |
| #5 | 由 `test_s9_direct_and_db_errors` 驗證，rc=2（沒有真的停掉資料庫） |
| #6 | `msdb.dbo.backupset` 最新 3 筆（21:30、21:32、21:33）都是 `is_copy_only = True` |
| #7 | 本輪改表前的備份就用這個指令（步驟 0） |
| #8 | `--help` 列出 `backup`，docstring 有一行，`backup --help` 列出 `--out`、`--direct`；README 已更新 |
| #9 | 沒有執行任何還原 |

- 容器內的 `.bak` 仍然只有第 3～5 輪的 3 份，本輪的備份暫存檔都已刪除。
- `../_backups/` 現在有 4 份：既有 3 份，加上本輪的 `TwStock_20261104_213027.bak`。

### F6-2

| 驗收 | 結果 |
|---|---|
| #1 | 步驟 9「✅ 相同」。基線在 21:30 匯出，比對時重新匯出，`exported_at` 不同，但工具判定相同 |
| #2 | 刻意改鍵會回報「不同」並指出鍵名：`test_f62_compare` 驗證；SA 也已用真實匯出實測（3 處） |

---

## 五、給 QA

- 重跑 `history` 時請加 `--end` 前一個交易日（第三節）。
- 本輪的 log 都在 `logs/iter06_*`。基線在 `logs/iter06_before/`；比對工具是 `logs/iter06_compare.py`。
- 已知、可接受的現象（設計第八節）：
  - 臨時休市前一日的 B，當晚 22:00 後會先顯示異常，到生效日收集後才記成 B。
  - 標記時，`history` 結尾的「無資料」會列出 gap 日期（`logs/iter06_history.log` 可以看到）。
- S9：
  - 請用 `--out` 指定暫存資料夾，驗完可以刪除自己產生的檔案。
  - `../_backups/` 與容器內既有的備份請不要動。
  - 不要執行還原。
- **期限**：11/26（美國感恩節）前要完成 QA。11/27 17:30 的收集應該會印「來源無持股明細（不算缺）：holdings.00411A（投信當日無持股清單）、holdings.00988A（…）」。
