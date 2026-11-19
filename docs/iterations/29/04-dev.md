# 第 29 輪｜Programmer：實作紀錄

- 撰寫日期：2026-11-17（週二）
- 依據：
  - `03-design.md` 第七節步驟、附錄 A `03-design-A.diff`。
  - `02-pm.md`：範圍與驗收。
  - 使用者回覆「同意，進 PG」：**D39-1 已同意**，可以改 `test_iter28` 16 行（階段一）、`test_iter03` 4 處（階段二）。
- 本次只做**階段一**（F29-1～3）。
  - 階段二（F29-4）照 PM 規定，等使用者回報 11/19 第 24 輪確認正常後才開始，見第五節。
- 資料日 **2026-11-16**；`collect_runs` 最大 `run_id` 從頭到尾都是 **18**，沒有進行中的收集。
- 守則：
  - **外部請求 0 次、資料庫寫入 0 次**；只有唯讀 SELECT（`collect_runs`、`daily_prices`）。
  - 沒有執行 `export`（階段一不需要）、`collect`、`history`、`setup-db`、`backup`、還原。
  - 沒有動 `.env`，沒有讀出或印出帳密；沒有動、也沒有執行 `_archive/`。
  - 沒有 commit、push。
  - 8001 測完已關閉，沒有碰 8000。
  - 瀏覽器已恢復桌面大小與淺色。8001 的 localStorage 預覽前沒有任何鍵，預覽時新增的 `tw.stockTab` 已刪除。

---

## 一、階段一：修改的檔案與行數

| 檔案 | ＋／−（`git diff --numstat`） | 內容 |
|---|---|---|
| `site/stock.js` | ＋24／−11 | `CHIP_I`、`chipI`；`chipN = '20'`；法人組切換、每日柱、區間累計小面板、讀法說明 |
| `site/app.css` | ＋1／−1 | `.chip-inv` |
| `site/index.html` | ＋2／−2 | `app.css?v=d654f1a6`、`stock.js?v=01859664` |
| `README.md` | ＋1／−1 | 「個股法人」一段加第 29 輪說明 |
| `tests/test_iter28.py` | ＋16／−16 | 設計第五節列出的 16 行（D39-1 已同意） |
| `tests/test_iter29.py`（新） | 70 行 | 階段一的 3 個測試 |

- 程式＋README **＋28／−15**。
- `docs/iterations/README.md` 的 ＋1 是上一個工作階段寫的「第 29 輪已排入」，不是本次改的。
- 基線副本：`logs/iter29_before/`（`stock.js`、`app.css`、`index.html`、`test_iter28.py`、`README.md`）。

---

## 二、執行步驟與結果

| 步驟 | 結果 |
|---|---|
| 1 基線 | `collect_runs` 最大 18、`daily_prices` 最新 11/16；複製改前檔案 |
| 2 套用 | `patch -p1 --dry-run` 通過後正式套用；6 個檔和 SA 原型（scratchpad `r29/Afull/`）**逐位元組相同** |
| 3 測試 | `node --check site/stock.js` 通過；`test_iter01`～`29` **29 個全部通過**（`logs/iter29_tests.log`） |
| 4 預覽 | 見第三節 |

---

## 三、8001 預覽（專案 `site/`，真實資料 11/16）

### 3-1 數值：4 檔 × 4 種區間 × 4 種法人 = 64 種組合，0 差異

- 方法：在頁面上依序切換區間與法人，讀圖例的當日值、區間累計、標題的起算日。和頁面另外取得的 `stocks/{代號}.json` 自己重算的結果比對。
- 樣本（PM 驗收 #1）：

  | 代號 | 選的理由 | 20 日外資累計（張） |
  |---|---|---|
  | 2421 建準 | 使用者回報的案例 | −3,153 |
  | 1802 台玻 | 累計與近期同向（20 日、近 5 日都是外資買超） | ＋221,692 |
  | 2408 南亞科 | 投信主導（20 日投信 −18,920，是外資的 2 倍以上） | — |
  | 3105 穩懋 | 上櫃 | ＋20,593 |

- 合計用官方 `insti.n`；起算日跨年時寫年份（「全部」為「2025/10/30」）。

### 3-2 操作與版面

| 項目 | 結果 |
|---|---|
| 預設 | 新開籌碼分頁：區間 20 日、法人外資 |
| 真實點擊 | 2408 點「投信」再點「60 日」→ 圖例「投信 −1,181」「累計 −39,860」、標題「自 08/18 起加總」；每個圖框只有 1 張圖；hashchange 0 次 |
| 十字線 | 滑鼠移到柱狀圖中間 → 收盤、每日柱、累計、融資四個圖例都跳到 9/23；投信 −180、累計 −3,534，和 JSON 重算相同 |
| 1024 淺色 | 2421、2408 正常 |
| 375 深色 | 3105：`scrollWidth = 375`，柱、累計、說明都在卡片內 |
| ETF 0050（375） | 沒有法人組與切換，只有融資（`cmC`）、借券（`clC`）兩張圖 |
| 主控台 | 沒有 JS 錯誤。有 2 筆 `ERR_CONNECTION_REFUSED`，是伺服器啟動前第一次導覽失敗留下的 |

---

## 四、和設計的差異

無。附錄 A 原樣套用。

---

## 五、階段二（尚未開始）

開始條件（`02-pm.md` 第一節、`03-design.md` 第七節）：

1. **使用者回報 11/17～11/19 第 24 輪上線確認正常**：事件筆數一行、`check` 筆數、不重複匯出。
2. 開始前確認沒有收集在跑，並先 `backup`。

之後照設計第七節「階段二」執行：

- 套用 `03-design-B.diff`。
- `setup-db`。
- 試補 1 天（2 次請求，確認證交所能不能查歷史）。
- 回補（約 506 次請求、30 分鐘）。
- `check`。
- `export` 並比對既有輸出。
- 8001 預覽。

---

## 六、給 QA 的提醒（階段一）

1. 改前程式：`logs/iter29_before/`。階段一不需要 `export`，`site/data` 沒有變。
2. 驗收 #1～#6 可以直接驗；#7～#12、#15 屬於階段二。
3. 使用者的 8000：
   - 若服務的是專案 `site/`，重新整理就會看到新的法人圖。
   - `index.html` 的 `?v=` 已更新；瀏覽器若還是舊畫面，強制重新整理。
4. `git status`：
   - 修改 `README.md`、`site/app.css`、`site/index.html`、`site/stock.js`、`tests/test_iter28.py`、`docs/iterations/README.md`（上一個工作階段）。
   - 新增 `tests/test_iter29.py`、`docs/iterations/29/`。

---

## 七、階段二（F29-4）：套用、setup-db、試補 1 天（2026-11-19 晚上）

- 依據：`03-design.md` 第三節、第七節「階段二」步驟 1～6；附錄 B `03-design-B.diff`。
- 開始條件：使用者 11/19 21:58 已完成當晚收集，協調者確認可以進行；**D39-1 已同意**（`test_iter03` 4 處）。
- 本次只做步驟 1～6，**沒有**執行完整回補（步驟 7，約 506 次請求，待使用者同意）、`export`，`site/data` 沒有變。
- 守則：
  - 外部請求 **2 次**（試補，上市、上櫃各 1 次），都經過 `fetch.request`，沒有重試。
  - 資料庫寫入：`backup`、`setup-db`（只新增 `foreign_holdings`）、試補 1 天寫入 `foreign_holdings`。
  - 沒有執行 restore、沒有刪除任何備份；沒有動 `.env`、`_archive/`；沒有 commit、push、stash、切分支；沒有碰 8000，也沒有開預覽。
  - 改前基線：用 `git archive HEAD`（c85b74f）匯出到 scratchpad `r29b/base/`（不含 `.env`），供步驟 9 匯出比對使用；`logs/iter29_before/` 是階段一前的舊程式，**不能**當階段二的基線。

### 7-1 步驟與結果

| 步驟 | 結果 |
|---|---|
| 1 確認沒有收集在跑 | `collect_runs` 最大 `run_id` = 25（11/19 21:58，`ok`），`finished_at` 為 NULL 的列 **0**；`daily_prices` 最新 11/19；`foreign_holdings` 尚不存在 |
| 2 `backup` | `_backups/TwStock_20261119_220414.bak`，**104.6 MB**（109,731,840 bytes），**RESTORE VERIFYONLY 通過** |
| 3 D39-1 | 使用者已同意 |
| 4 套用 B diff | 先在 scratchpad 副本（HEAD＋B）套用並跑完測試，再對專案 `patch -p1`；結果與副本逐位元組相同。見 7-2 |
| 4 測試 | `node --check site/stock.js`、`site/app.js` 通過（node v14.17.1）；`test_iter01`～`33` **33 個全部通過** |
| 5 `setup-db` | 完成訊息多了「foreign_holdings（第 29 輪）」（在 `etf_holding_gaps` 前）；資料表 28 → **29**、索引 64 → **67**，新增的只有 `foreign_holdings` 的 PK、`UQ_foreign_holdings`、`IX_foreign_holdings_date`；欄位型別與 NULL 和設計 3-2 相同 |
| 6 試補 1 天 | 見 7-3 |

### 7-2 套用情形與和 diff 的差異

`patch -p1 --dry-run`：13 個檔中 12 個可以套用，`site/index.html` 1 個 hunk 失敗（預期，`?v=` 已被第 30～33 輪改過）。

| 檔案 | 情形 | 處理 |
|---|---|---|
| `site/stock.js` | hunk 1、2 原位；hunk 3 **offset 45 行**（第 30～33 輪在前面加了程式） | 照套。已確認上下文仍是 `buildChip` 的法人段（`anchors.push([ci, bar, V], [cu, cl, cum]);` 之後），內容不變 |
| `tests/test_iter29.py` | hunk 2 offset 1 行（QA29-01 補強多 1 行） | 照套 |
| `site/index.html` | **reject**：diff 預期改前是 `stock.js?v=01859664`、`app.js?v=656083f0`，目前是 `stock.js?v=d65e3485`、`app.js?v=c38094b2` | 手動只改 `stock.js` 一行：`?v=d65e3485` → **`?v=8b31b331`**（新 `stock.js` 的 sha1 前 8 碼）。`app.js`、`app.css` 沒有改，`?v=` 不動。`test_iter23` 通過 |
| 其他 10 個檔 | 原位套用，沒有 offset、fuzz | — |

- 除了 `index.html` 的雜湊值，內容與 diff 完全相同。沒有因為第 30～33 輪而需要改其他舊測試。
- `git diff --numstat`（＋／−）：`README.md` 3／1、`site/index.html` 1／1、`site/stock.js` 12／2、`tests/test_iter03.py` 23／4、`tests/test_iter29.py` 110／2、`twstock/__main__.py` 3／2、`twstock/collectors/daily.py` 75／5、`twstock/collectors/history.py` 1／1、`twstock/db.py` 19／1、`twstock/export.py` 10／0、`twstock/health.py` 2／0；新增 `tests/fixtures/insti_qfii_20261116_mini.json`、`tests/fixtures/mi_qfiis_20261116_mini.json`。
  - 設計 3-7 表寫 `daily.py` ＋67、`export.py` ＋8、`test_iter03` ＋22，和 diff 檔實際行數（＋75、＋10、＋23）略有出入；是設計表格的計數，不是套用差異。

### 7-3 試補 1 天

```bash
python3 -u -m twstock history --start 2025-10-30 --end 2025-10-30 --only qfii
```

- 輸出（`logs/iter29b_trial.log`）：`✅ 寫入：qfii.TWSE 1059 筆、qfii.TPEx 860 筆`，成功 1 天。
- **證交所 `MI_QFIIS` 可以查歷史日期**（設計第四節風險 2 解除）。
- 請求數：**2 次**（上市 GET 1、上櫃 POST 1）。沒有出現「⏳ 請求失敗…重試」訊息；`history` 的交易日取自資料庫，沒有其他請求。兩市寫入時間相隔約 1.2 秒，符合各 1 次。
- 資料檢查（唯讀 SELECT）：

  | 項目 | 結果 |
  |---|---|
  | 2025-10-30 有行情、沒有外資持股的股票 | **0 檔** |
  | 依目前 `stocks.market_type` 分組 | 上市 1,060、上櫃 859（行情 1,059／858）；和收集輸出差 1 檔，是之後由上櫃轉上市的股票（`market_type` 是目前值），不是缺漏 |
  | 比率 ≈ 持有 ÷ 發行（差 ≥ 0.01 的列） | **0 列** |
  | 比率範圍 | 上市 0.00～99.36、上櫃 0.00～87.79 |
  | 抽樣 | 2330 73.41%、2421 37.77%、3105 17.09%、6488 22.63%（投資上限都是 100.00） |

### 7-4 下一步（寫於步驟 6 之後；使用者已回覆「同意回補」（D39-5），結果見 7-5 起）

1. 步驟 7 回補：`python3 -u -m twstock history --start 2025-10-30 --only qfii`，約 506 次請求、30 分鐘（2025-10-30 已有，會略過或覆寫，實際次數以輸出為準）。
2. 步驟 8～11：`check`、用 scratchpad `r29b/base/`（c85b74f）另匯出基線後比對、8001 預覽、人工核對。
3. 回補前的注意：今晚之後的排程收集會開始每天多 2 次請求寫入 `foreign_holdings`（`DAY_KEYS` 已含 `qfii`）；`check` 在回補前會顯示外資持股兩行有缺口，屬預期。

### 7-5 步驟 7：回補

- 使用者回覆「同意回補」（D39-5），協調者轉達並複核步驟 1～6 後開始。
- 指令（背景執行，輸出 `logs/iter29b_backfill.log`）：

  ```bash
  python3 -u -m twstock history --start 2025-10-30 --only qfii
  ```

  - 為了取得精確的請求數，用一個包裝：`runpy` 執行同一個 `twstock` 指令（參數相同），結束時 `atexit` 印 `fetch.request_count()`（`fetch.request` 每發一次就加 1，含重試）。沒有改任何程式、沒有繞過 `fetch.request`。
- 結果：
  - 交易日 256 天，2025-10-30 已有、**待抓 255 天，全部成功**。
  - **請求數 510 次**（`REQUESTS 510` = 255 天 × 上市、上櫃各 1）；沒有任何「⏳ 請求失敗…重試」、沒有主機標記；上限 520 內。
  - 耗時 **917 秒（約 15.3 分鐘）**，22:08:02～22:23:19；比預估 30.6 分鐘快（`SECONDS_PER_KEY` 的估計偏保守）。
- 資料庫（唯讀 SELECT）：

  | 項目 | 結果 |
  |---|---|
  | `foreign_holdings` | **502,087 列、256 天**（2025-10-30～2026-11-19） |
  | 每天檔數 | 1,919～1,991 |
  | 有行情、沒有外資持股的（股票, 日） | **0**（256 天全部） |
  | 有行情、沒有任何外資持股的日期 | **0** |
  | 比率與「持有 ÷ 發行」差 ≥ 0.01 | **0 列** |
  | `collect_runs` | 仍是 25（`history` 不寫收集紀錄；期間沒有其他收集） |

### 7-6 步驟 8：`check`

- `logs/iter29b_check.log`：「上市外資持股 20/20、2026-11-19、1,092 筆（中位數 1,093）✅ 正常」「上櫃外資持股 20/20、898 筆（中位數 897）✅ 正常」，結果「無異常」。
- `check` 只看近 20 個交易日；更早的日期用 7-5 的 SQL 確認 256 天都沒有缺口。

### 7-7 步驟 9：匯出比對

- 基線：scratchpad `r29b/base/`（`git archive HEAD`，c85b74f）。
  - 用包裝腳本 `scratchpad/tools/base_export.py`：先 import 專案的 `twstock.config` 讓它把 `.env` 載入環境變數（不讀出、不印、不複製 `.env`），再清掉 `twstock` 模組、改從 `r29b/base/` import，斷言 `SITE_DATA_DIR` 在 `r29b/base/site/data`，才呼叫 `export_all()`。
  - 輸出在 `r29b/base/site/data`，沒有寫到專案 `site/data`。
- 新程式：專案目錄 `python3 -u -m twstock export`（`logs/iter29b_export.log`）。兩次匯出之間資料庫沒有變動。
- 時間（`export_all` 自己印的耗時）：**基線 26.7 秒、新 27.3 秒（＋0.6 秒）**。
- 比對（`scratchpad/tools/cmp_export.py`，JSON 解析後逐值比對）：

  | 範圍 | 結果 |
  |---|---|
  | `stocks/` | 2,000 檔都在兩邊；**2,000 檔都有 `fh`**，長度都等於 `prices.d`；刪掉 `fh` 後 **0 檔不同** |
  | `etfp/` | 367 檔，0 不同，沒有 `fh` |
  | `etfs/` | 8 檔，0 不同 |
  | `screen.json` | 相同 |
  | `latest.json` | 只有 `status` 不同：① `status.exported_at`（匯出時間戳）；② `status.datasets` 多了 `qfii.TWSE`、`qfii.TPEx` 兩項（`{'n': '上市外資持股', 'd': '2026-11-19', 's': 'ok'}` 等）。排除這兩處後**相同** |

- 和設計的差異：設計 3-5 寫「`latest.json` 不變」，實際 `status.datasets` 多兩項。原因是 `status.datasets` 由 `health.SPECS` 產生，B diff 在 `SPECS` 加了兩行；這是同一個 diff 的必然結果，不是額外修改。前端只在 `s === 'abnormal'` 時把它放進新鮮度橫幅（`app.js:1704`），正常時畫面不變；外資持股異常時橫幅會多一行，屬預期。
- `site/stocks` 合計 41 MB → 44 MB（約 ＋3 MB，和設計估計相同）；2421 的 JSON 23.9 KB。

### 7-8 步驟 10：8001 預覽（JSON／資源層級）

- `python3 -u -m twstock serve --port 8001 --no-browser` 背景啟動（啟動前確認 8001 沒有在聽）。
- `curl` 檢查：`/`、`app.css?v=afb40d48`、`app.js?v=c38094b2`、`stock.js?v=8b31b331`、`latest.json`、`screen.json`、`stocks/2421.json`、`2330.json`、`6488.json`（上櫃）、`etfp/0050.json` 都是 200；`index.html` 引用 `stock.js?v=8b31b331`，與伺服器送出的 `stock.js` sha1 前 8 碼相同；`Cache-Control: no-cache`。
- 個股 JSON 的 `fh`：

  | 代號 | 長度／`prices.d` | null | 11/19 | 5 日 | 20 日（百分點） |
  |---|---|---|---|---|---|
  | 2421 | 256／256 | 0 | 35.79 | −0.46 | −1.22 |
  | 2330 | 256／256 | 0 | 67.88 | −0.22 | −0.78 |
  | 6488（上櫃） | 256／256 | 0 | 30.43 | ＋0.79 | ＋0.01 |
  | 0050（ETF，`etfp/`） | 沒有 `fh` | — | — | — | — |

- 畫面（卡片、持股比率圖、375／1024、深淺色）沒有用瀏覽器預覽，由協調者做。
- 結束：`pkill -f "twstock serve --port 8001"`，確認 8001 沒有在聽；8000（使用者的伺服器）沒有動，仍在聽。

### 7-9 步驟 11：人工核對（官方來源）

- 方法：最新交易日 2026-11-19 在回補時已抓過（22:23 左右，已過櫃買 22:00 更新）。再經 `fetch.request` 各打 1 次官方 API（**額外 2 次**，`request_count()` = 2），取原始回應的對應欄位（上市位置 3／5／6／7／8、上櫃同位置，代號欄上市 0、上櫃 1），和資料庫逐欄比對。原始回應存 `logs/iter29b_verify_raw.json`、比對輸出 `logs/iter29b_verify.log`。
- 回應：上市 `stat OK`、`date 20261119`；上櫃 `stat ok`、`date 20261119`。

  | 市場 | 代號 | 發行股數 | 外資持有股數 | 持股比率 | 尚可投資 | 上限 | 結果 |
  |---|---|---|---|---|---|---|---|
  | 上市 | 2421 | 286,943,669 | 102,719,075 | 35.79 | 64.20 | 100.00 | ✅ 相同 |
  | 上市 | 2330 | 25,932,370,067 | 17,605,480,440 | 67.88 | 32.11 | 100.00 | ✅ 相同 |
  | 上市 | 2317 | 14,028,648,626 | 5,582,215,165 | 39.79 | 60.20 | 100.00 | ✅ 相同 |
  | 上櫃 | 6488 | 528,113,725 | 160,749,417 | 30.43 | 69.56 | 100.00 | ✅ 相同 |
  | 上櫃 | 3105 | 423,940,384 | 190,156,278 | 44.85 | 55.15 | 100.00 | ✅ 相同 |
  | 上櫃 | 8069 | 1,154,360,555 | 476,624,251 | 41.28 | 58.71 | 100.00 | ✅ 相同 |

### 7-10 階段二合計

- 外部請求：試補 2 ＋ 回補 510 ＋ 核對 2 = **514 次**，全部經過 `fetch.request`，0 次重試。
- 資料庫寫入：`backup`（`TwStock_20261119_220414.bak`）、`setup-db`（新增 `foreign_holdings`）、`foreign_holdings` 502,087 列。
- `site/data` 已用新程式匯出（含 `fh`）。8000 若服務專案 `site/`，重新整理就會看到外資持股卡與圖（`index.html` 已更新 `?v=`）。
- 尚未 commit；是否 commit 由使用者決定。`git status` 另有 `docs/iterations/34/`（未追蹤），不是本次產生的。
