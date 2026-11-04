# 第 05 輪｜Programmer：實作紀錄

- 撰寫日期：2026-11-04（週三）凌晨
- 依據：
  - `03-design.md`：實作依據，含附錄 B SQL、附錄 C diff、附錄 D 測試、附錄 E 工具。
  - `02-pm.md`：範圍與驗收條件。
- 本輪項目：E2-1（統一投信主動 ETF 每日持股）、E2-4（持股頁與個股「主動 ETF 持有」卡）、A3＋A8（官方漲跌家數、市場寬度與量能）、F1（首頁卡片排版），全部完成。README 已照設計第七節修改。
- **使用者追加需求（PG 期間）**：首頁「信用交易」與「市場寬度」改成左右並排。
  - 只改 `site/app.css` 3 行，見第一節 F1-b。
  - 這是本輪唯一與設計不同的程式修改。
- 程式來源：
  - 附錄 C 的 diff 用 `git apply` 套用：先套 `fetch.py`、`db.py`，執行 `setup-db` 後再套其餘部分。
  - `tests/test_iter05.py`、`logs/iter05_history.py`、`logs/iter05_compare.py` 直接從附錄 D、E 取出。
  - 收尾時逐檔比對：程式、網站、測試除了 `site/app.css` 的 F1-b 3 行以外，**與 SA 原型完全相同**。
- 守則：
  - 沒有 commit、push，沒有動 `.env`、`_archive/`。
  - 沒有安裝排程、沒有改系統或 Docker 設定（restart policy 仍是 `no`），沒有執行還原。
  - 測試用的 8001 埠已關閉，8000 埠沒有動。

> **結論**
> - 補抓 244 個交易日成功，共 648 次請求，耗時 32.4 分鐘，沒有重試、沒有被拒。
> - 附錄 B 的驗收數值全部相符：00981A 11/03 是 51 檔；2330 為 14,464,000 股、13.05%；TX 679 口；11/02 → 11/03 異動正好 4 檔，其他 **47 檔**不變。官方家數 58／1,000 與 59／782。
> - 兩次隔離比對：既有資料與 `stocks` 1,999 檔都相同。第 2 次多出 `updated_at` 不同，原因見二-3。
> - `test_iter01`～`05` 全部通過，`test_e2_real_file` 已讀到真實回應。
> - **`check` 補抓後 rc=1，與設計預期的 rc=0 不同**：00411A、00988A 的 10/21 在資料來源端就沒有持股明細，見第三節。**需要 QA／使用者判斷。**

---

## 一、各項目修改內容

| 項目 | 檔案 | 修改 |
|---|---|---|
| E2-1 | `twstock/fetch.py` | `www.ezmoney.com.tw` 間隔 3 秒 |
| E2-1、A3 | `twstock/db.py` | 新表 `etf_holdings`、`etf_holding_summary`、`market_breadth`，索引 `IX_etf_holdings_code` |
| E2-1、A3 | `twstock/health.py` | `HOLDINGS`、`BREADTH_FROM`；`Spec` 加 `since`、`delay`；`is_due`；`SPECS` 加 6 鍵；`missing_keys(…, days)`、`dataset_status(…, closed)` |
| E2-1 | `twstock/collectors/holdings.py`（新檔） | `ez_time`、`ez_date`、`post_date`、`parse_pcf`、`fetch_holdings`、`merge_holdings` |
| E2-1、A3 | `twstock/collectors/daily.py`、`history.py`、`catchup.py` | 持股與家數分支、`MI_INDEX` 共用回應、`--only holdings`、catch-up 傳入 days 與 closed |
| E2-4、A3 | `twstock/export.py` | `etfs/{代號}.json`、個股 `active`、`latest.holdings`、`latest.breadth` |
| 文件 | `twstock/__main__.py` | `--only holdings` 與 docstring |
| E2-4、A3、F1 | `site/app.js`、`site/stock.js`、`site/app.css` | 持股頁、ETF 列表標示、個股卡、官方家數、市場寬度卡、`.g-mk` 4 欄。說明文字採用 D10 定案版 |
| **F1-b（使用者追加）** | `site/app.css` | 見下方 |
| 測試 | `tests/test_iter05.py`（新檔，430 行）、`tests/test_iter03.py`、`tests/test_iter04.py` | 附錄 C、D |
| 文件 | `README.md` | 設計第七節 1～6 全部；另在專案結構表與日常使用加 `test_iter05.py`（比照前幾輪） |

**F1-b 加在 `.g-mk .insti` 之後：**

```css
.g-mk .margin{grid-column:span 2}                      /* 信用交易、市場寬度左右並排 */
.g-mk .insti + .margin:last-child{grid-column:1/-1}    /* 只有其中一張時佔滿一列 */
@media (max-width:900px){.g-mk .margin{grid-column:1/-1}}
```

- 市場寬度卡沿用 `margin` class，所以兩張卡各佔 2 欄。
- 只有其中一張卡時（沒有 `breadth` 或沒有融資資料），那張卡仍佔滿整列，不會留下半列空白。
- 900px 以下維持上下排列：信用交易每行字較長，並排後每行會折成 2～3 行。

---

## 二、執行過的指令與結果（台灣時間）

### 1. 依序執行的資料操作

| 時間 | 步驟 | 結果 | 紀錄 |
|---|---|---|---|
| 11/03 23:52 | 備份（第 0 步） | `_backups/TwStock_before_round5.bak` 81,129,472 B（> 55 MB）。round3（54,378,496 B，10/31 12:16）、round4（56,651,776 B，11/03 21:26）都沒變；restart policy = `no` | 指令見下方 |
| 23:53:10 | 既有表筆數基線、**以舊程式**匯出隔離基線 | `latest.json` 721,890 B；`stocks` 1,999 檔 | `logs/iter05_counts_before.json`、`iter05_export_before.log`、`iter05_before/` |
| 23:53:37 | 套用 `fetch.py`、`db.py`，執行 `setup-db` 兩次 | 22 張表都確認存在，沒有錯誤；3 張新表 0 筆；既有表筆數不變 | `logs/iter05_setupdb.log`、`iter05_counts_after_setupdb.json` |
| 23:53:50 | 套用其餘 diff 與附錄 D、E | `test_iter01`～`05` 全部通過（`real_file` 略過） | — |
| 23:53:56 | `check` 基線 | rc=1：6 個新資料集異常。家數缺 11/03；持股缺 20 天（跨境 2 檔 19 天，因為 11/03 還不該有） | `logs/iter05_check_before.log` |
| 23:54 | 新程式匯出、第 1 次隔離比對 | ✅ 除 `breadth`、`holdings` 與新資料集外相同；差異 0 檔；+1.5 KB | `logs/iter05_export_cmp1.log`、`iter05_compare1.log` |
| 23:54:20～00:26:50 | `python3 logs/iter05_history.py` | 244 天成功，rc=0；3 份 00981A 原始回應已保存 | `logs/iter05_history.log` |
| 00:27:16 | `collect --catch-up`（第 7 步） | 寫入 `breadth.TWSE`、`breadth.TPEx` 各 1 筆；重試 00411A、00988A 的 10/21 仍無資料；**rc=1** | `logs/iter05_catchup.log` |
| 00:28:21 | `check` | **rc=1**：只剩 00411A、00988A 缺 10/21（第三節） | `logs/iter05_check_after.log` |
| 00:28 | 附錄 B SQL、`test_iter05`（含 `real_file`） | 見第四節；全部通過 | `logs/iter05_sql_after.log` |
| 00:28:40 | `export`、第 2 次隔離比對 | 見二-3 | `logs/iter05_export_after.log`、`iter05_compare2.log`、`iter05_counts_after.json` |

**備份指令**（比照第 4 輪，加 `COPY_ONLY`）：

- 用 `db.connect(autocommit=True)` 執行 `BACKUP DATABASE TwStock TO DISK = N'/var/opt/mssql/data/TwStock_before_round5.bak' WITH COPY_ONLY, INIT, COMPRESSION`。
- `msdb.dbo.backupset` 顯示 `is_copy_only = 1`、壓縮後 77.4 MB。
- 先確認 `_backups/` 沒有同名檔，再用 `docker cp MySqlServer:/var/opt/mssql/data/TwStock_before_round5.bak ../_backups/` 複製出來。

### 2. 補抓與外部請求統計

| 項目 | 請求數 | 說明 |
|---|---|---|
| 補抓 | 648 | 設計估計約 648 次、35 分鐘，實際 32.4 分鐘。沒有重試、沒有「疑似被封鎖」、沒有中斷重跑 |
| `collect --catch-up` | 4 | 上市 `MI_INDEX` 1 次（行情與家數共用）、櫃買 `highlight` 1 次、10/21 跨境持股 2 次 |
| PG 診斷 10/21 | 2 | `fetch.request(isolated=True)`，不重試，回應保存在 `logs/iter05_raw_GetPCF_00411A_post20261027.json`、`…_post20261023.json` |

`collect_runs` 從 4 筆變成 5 筆（就是那一次 catch-up）。除此之外，既有表筆數完全不變（`logs/iter05_counts_*.json`）。

### 3. 隔離比對（E2-4 #5）

- 第 1 次：✅ 除新增鍵外相同。
- 第 2 次：`logs/iter05_compare.py` 停在 `AssertionError: updated_at`。
  - 原因：第 7 步的 `collect --catch-up` 寫入了新的家數資料，「最後一次收集到新資料的時間」從 11/03 20:52 變成 11/04 00:27。設計假設這一步不影響比對，但沒有考慮到這兩個時間欄位。
  - 逐鍵檢查（附在 `logs/iter05_compare2.log` 下方）：
    - 頂層不同的鍵只有 `updated_at`；新增鍵是 `breadth`、`holdings`。
    - `status` 不同的鍵只有 `collected_at`、`exported_at` 與 `datasets`；舊資料集的狀態完全相同。
    - `stocks` 1,999 檔除了 `active` 以外差異 0 檔，有 `active` 的 70 檔。
  - **結論：資料面隔離成立。**
- `latest.json` 723,528 B，比基線增加 1.6 KB（上限 20 KB）。
- `etfs/*.json`：00981A 32 KB、00403A 33 KB、00988A 26 KB、00411A 17 KB，都遠低於 300 KB 上限。

### 4. 測試

- `python3 tests/test_iter01.py`～`test_iter05.py` 全部通過。
- `test_iter05`：`test_e2_real_file` 讀到 `logs/iter05_raw_GetPCF_00981A_{20251030,20261103}.json` 並通過。

---

## 三、與設計預期不同：跨境 ETF 部分日期資料來源沒有持股明細

### 1. 現象

補抓的「官方尚無資料」清單中，有 8 筆落在台灣交易日（設計第八節要求 QA 列為觀察事項）：

| ETF | 持股日 |
|---|---|
| 00988A | 2025-11-27、2026-01-19、2026-02-10、2026-05-25、2026-07-08、**2026-10-21** |
| 00411A | 2026-09-07、**2026-10-21** |

國內 2 檔（00981A、00403A）沒有任何缺漏。B-1 的 SQL 同樣列出這些日期，另外加上跨境 2 檔的 11/03（還沒公布，正常）。

### 2. 原因（PG 診斷，2 次請求）

- 00411A 持股日 10/21 → 參數 `115/10/27`：`pcf` 有真實數值（`NAV` 4,684,340,379、`TranDate` 10/21、`PostDate` 10/27），但 `asset: []`。也就是**投信有公布彙總，卻沒有持股明細**。
- 改用參數 `115/10/23` 一樣是 `asset: []`。10/23 沒有行情，也不在 `market_holidays` 裡。
- 依 `parse_pcf` 的設計，`asset` 為空就視為「尚未公布」，不寫入。程式行為與設計一致。
- 其他 7 天多數是美國休市日（感恩節 11/27、MLK 1/19、陣亡將士紀念日 5/25、勞動節 9/7），推測海外市場休市那天沒有持股清單。這部分**沒有逐一發請求驗證**，2/10、7/8 的原因也不確定。

### 3. 影響

- 10/21 在 `check` 的 20 日視窗內，所以：
  - `check` 與 `collect --catch-up` 會回傳 rc=1，直到 10/21 移出視窗（約 11/18）。
  - 每次 `--catch-up` 都會多發 2 次請求去重抓。
  - 如果使用者安裝了排程並用 `--notify`，每天會收到一次通知。
- 網站 `status` 只看最新持股日，所以 4 檔都是 `ok`，網站沒有橫幅。
- 持股頁的 1 日增減以「前一個有資料的持股日」為基準，所以 10/22 會和 10/20 比較，數字仍然正確。

### 4. PG 沒有修改程式，交給 QA／使用者判斷

設計沒有「資料來源確定不會有」的處理方式。可能的方向，由 SA 決定：

- (a) `pcf` 有數值、`asset` 為空時，記為「來源無明細」，不算缺漏。
- (b) 這種日期登記成這檔 ETF 的「休市」。
- (c) 維持現狀，等 10/21 移出視窗。

---

## 四、驗收數值（`logs/iter05_sql_after.log`）

| 驗收 | 預期（設計附錄 B） | 實際 |
|---|---|---|
| E2-1 #1 新表、可重跑 | 3 張表，既有表筆數不變 | ✅ |
| E2-1 #2 補抓完整 | 缺漏 0 | ⚠️ 00988A 6 天、00411A 2 天（第三節）；跨境 11/03 尚未公布 |
| 持股日數 | — | 00981A 244（2025-10-30～11/03）、00988A 233（2025-11-05～11/02）、00403A 119（2026-05-12～11/03）、00411A 42（2026-08-26～11/02） |
| E2-1 #3 00981A 11/03 | 51 檔；2330 14,464,000 股、33,194,880,000、13.05；TX `2026/11` 679 口、5,887,337,400、2.31；NAV 254,413,288,263；94.43 | ✅ 全部相同 |
| E2-1 #4 11/02 → 11/03 | 1802 +8,479 new；2330 +736；3376 −300；8210 −100；其他 47 檔不變 | ✅ 4 列；不變 47 |
| E2-1 #5 2025-10-30 | 50 檔、96.03、NAV 23,452,246,994 | ✅（`test_e2_real_file` 逐列比對原始回應） |
| 附錄 B-2 彙總 4 天 | 表格值 | ✅ 4 列完全相同 |
| 其他 3 檔最新持股日 | 00403A 11/03 50 檔 85.85% 1,185.23 億；00411A 11/02 30 檔 93.37% 41.96 億；00988A 11/02 34 檔 92.50% 418.18 億 | ✅ |
| A3 #1 官方家數 | 上市 58／2／1000／33／22／6；上櫃 59／11／782／41／32／24 | ✅ |
| A3 #2 寬度（`latest.breadth`） | 上市 11.1%（1,083）／19.9%／新高 11／新低 691／0.97；上櫃 12.1%（867）／19.0%／16／560／0.86 | ✅ |
| E2-4 `etfs/00981A.json` `sum` | `{nav 2544.13, nu 24.87, n 51, sw 94.43, fl 679, fa 58.87}` | ✅；`rows` 51 列、第一列 2330 `d1` 736；`out` [] |
| `stocks/1802.json` `active` | 00981A 8,479 張、0.23%、`d1` 8,479、`new`；補抓後 `d5` 為 8,479 | ✅ |
| `stocks/2330.json` `active` | 00403A 7,800 張 15.10%、00981A 14,464 張 13.05%、00988A 320 張 1.78% | ✅；`d1` 分別為 100、736、0 |
| `stocks/1101.json` | 沒有 `active` | ✅ |

---

## 五、前端檢查（8001 埠，`?v=` 避免快取）

| 頁面 | 結果 |
|---|---|
| 今日 1280px | 成交額卡 265 × 222 兩張；三大法人卡 539 × 222。信用交易與市場寬度左右並排，各 539 × 248（並排前上下兩張分別高 230、170） |
| 今日 1000px | 235／235／479 × 222；信用交易、市場寬度各 479 × 338 |
| 今日 880px | 信用交易、市場寬度各佔一列（848 寬） |
| 今日 375px | 沒有整頁水平捲動；成交額卡 2 欄，三大法人、信用交易、市場寬度各佔一列 |
| 成交額卡 | 「漲 58（停 2）　跌 1,000（停 33）　平 22　未成交 6」，副標「家數為官方（股票）…」 |
| ETF 列表 | 4 個「持股」連結；其他 `A` 結尾的 31 檔標「持股尚未支援」 |
| 00981A 持股頁 | 51 列，依權重第一列「台積電 2330 14,464 張 13.05% +736 +1.19 +1,418」；1802 標「新」+8,479；底部說明是 D10 定案文字 |
| 00988A、00411A | 標示「（跨境，晚一個交易日公布）」。00988A 24 檔標「（海外）」、不可點；可點的台股 10 檔 |
| 00403A | 正常 |
| 00982A | 「00982A 的持股資料尚未支援（目前只有統一投信 4 檔主動 ETF）」，不發請求 |
| 個股 1802、2330 | 有「主動 ETF 持有」卡 |
| 個股 1101 | 沒有卡片 |
| 375px 各頁 | 上列 10 個頁面的 `scrollWidth` 都是 375，沒有整頁水平捲動 |
| console | 新分頁瀏覽全部頁面後，沒有 error |

檢查完已關閉伺服器（`curl` 8001 無回應），檢視大小已重設。

---

## 六、給 QA

- 第三節的 10/21 缺漏請判斷要列為缺陷還是觀察事項。
  - 診斷用的原始回應在 `logs/iter05_raw_GetPCF_00411A_post2026102{3,7}.json`。
  - 如果要驗證其他 7 天，每天每檔需要 1 次請求。PG 沒有發。
- 第 2 次隔離比對請以 `logs/iter05_compare2.log` 下方的逐鍵檢查為準（二-3）。
- F1-b（左右並排）是使用者在 PG 期間追加的需求，不在設計驗收表裡。請在 1280、1000、880、375px 各看一次。
