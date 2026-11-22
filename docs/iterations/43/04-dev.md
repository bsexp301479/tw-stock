# 第 43 輪｜PG：開發（集保股權分散 F43-1～F43-3）

- 撰寫日期：2026-11-22（週日）；網站資料日 2026-11-20（週五）。
- 依據：`43/01-analyst.md`（D114 = A、D114-1 = B、D114-2～D114-8 照建議）、`43/02-pm.md`（D115 = A、PM 自行決定 9 項照 PM）、`43/03-design.md`（D116 = A、D117 = A）、`43/03-design.diff`。
- 守則：資料庫 0 次、外部 API 0 次；沒有讀、印、複製 `.env`；沒有執行 backup／setup-db／collect／export／check；沒有安裝排程、改系統設定；沒有 commit、push、stash、checkout；沒有用 8000；沒有執行 `_archive/`。

---

## 一、套用結果

| 步驟 | 結果 |
|---|---|
| `git apply --check docs/iterations/43/03-design.diff` | 通過 |
| `git apply docs/iterations/43/03-design.diff` | 成功，無 reject、無 fuzz |
| 小幅修正 | **無**（照設計原樣套用，沒有改任何一行） |

## 二、改動檔案與行數（`git apply --numstat`）

| 檔案 | ＋ | − |
|---|---|---|
| `twstock/collectors/tdcc.py`（新檔） | 100 | — |
| `twstock/tradingcal.py` | 24 | 0 |
| `twstock/db.py` | 19 | 1 |
| `twstock/collectors/catchup.py` | 17 | 6 |
| `twstock/health.py` | 37 | 5 |
| `twstock/export.py` | 39 | 1 |
| `site/stock.js` | 33 | 0 |
| `site/index.html` | 1 | 1 |
| `README.md` | 4 | 2 |
| `docs/dblayout.md` | 57 | 2 |
| `docs/iterations/README.md` | 1 | 0 |
| `tests/test_iter43.py`（新檔） | 566 | — |

- 和設計第七節的檔案、行數完全相同。`site/app.js`、`site/tools.js`、`site/app.css`、`twstock/__main__.py` 0 行改動。
- 另新增本文件 `docs/iterations/43/04-dev.md`。

## 三、測試結果

| 項目 | 結果 |
|---|---|
| `for f in tests/test_iter*.py; do python3 -u $f >/dev/null 2>&1 \|\| echo FAIL $f; done` | 43 個（`test_iter01`～`43`）全部通過，沒有任何 `FAIL`（約 38 秒） |
| `python3 -u tests/test_iter43.py` | 14 個測試全部通過（印「全部通過」），含反證 20 種 |
| `git diff --stat tests/` | 空（舊測試 0 行改動；`tests/` 只多新檔 `test_iter43.py`） |

`?v=`（`site/index.html` 對 `shasum -a1` 前 8 碼）：

| 檔案 | sha1 前 8 碼 | `index.html` | 一致 |
|---|---|---|---|
| `app.js` | `0283995e` | `app.js?v=0283995e` | ✅ |
| `stock.js` | `a6ab2ef4` | `stock.js?v=a6ab2ef4` | ✅（本輪由 `d7c03cdc` 改） |
| `tools.js` | `05638786` | `tools.js?v=05638786` | ✅ |
| `app.css` | `55349eb3` | `app.css?v=55349eb3` | ✅ |

## 四、「資料表不存在時不啟用」的確認（今晚 11/22、明晚 11/23 排程）

目前資料庫還沒有 `share_distribution`（尚未 `setup-db`）。確認方式：讀程式＋測試＋獨立的小腳本（假 cursor，不連資料庫、不發請求）。

### 4-1 讀程式

| 位置 | 表不存在時的行為 |
|---|---|
| `health.share_exists` | 只下 `SELECT OBJECT_ID('share_distribution')`（SQL Server 表不存在時回傳一列 NULL，不會拋錯）→ False |
| `health.share_state` | 不存在 → 直接回傳 `(False, None, 0, 0)`，不查表 |
| `catchup._run_locked` | 第一個連線多 1 個 `share_state` 查詢（只有上面那個 `OBJECT_ID`）→ `make_plan(..., share=...)` |
| `catchup.make_plan` | `due = share and share[0] and …` → `share[0]` 為 False → `plan["tdcc"] = None` |
| `catchup.plan_is_empty` | 多看 `plan.get("tdcc")`，None 不影響 → 原本「沒有要抓的資料」照舊判斷 |
| `catchup.execute_plan` | `if plan.get("tdcc") and …` → 不呼叫 `collect_tdcc`，**0 次 opendata 請求**、不印任何「集保」字樣、`undated` 沒有 `tdcc` 鍵 |
| `_run_locked` 的 `changed` | 新加的那行只看 `undated["tdcc"]`，沒有 → 不影響「有新資料」與自動匯出 |
| `_undated_counts` | 不動（D115 = A），不查新表 → 不會因表不存在而失敗 |
| `export._load_share` | 不存在 → `[]`，只下 1 個 `OBJECT_ID` 查詢 → `sh_stock`、`sh_etf` 皆空 → 所有 JSON 不輸出 `sh` 鍵（逐位元組和改動前相同） |
| `collectors/tdcc.py` 匯入 | 只有常數與函式定義，匯入時不連網、不連資料庫 |

結論：表不存在時，`collect --catch-up` 只多 1 個唯讀的 `OBJECT_ID` 查詢（匯出時再多 1 個），**外部請求 +0**、輸出與回傳碼和改動前相同，不會因本輪程式失敗。

### 4-2 測試

- `test_iter43 test_world` 情境 17：`SdWorld(table=False)` 跑 `collect --catch-up`（11/28 週六）→ getOD 0 次、`undated` 無 `tdcc`、輸出沒有「集保」、沒有 MERGE 到 `share_distribution`。通過。
- `test_iter43 test_export`：表不存在時 `_load_share` 回 `[]`，且 SQL 只有 `SELECT OBJECT_ID('share_distribution')`。通過。
- `test_iter43 test_timing`：「表不存在也排」反證被擋下。
- 舊測試（`test_iter03`／`04`／`24` 的 World 假資料庫，`OBJECT_ID` 查詢落到 `self.result = []`）全部照過：`w.requests == []`、「不需要請求」、「不匯出」都不變。

### 4-3 獨立小腳本（scratchpad，不屬於專案）

`/private/tmp/claude-501/-Users-wudongliang-ClaudeWorkSpace/58df24da-3f54-4019-81b4-9a139a63dea9/scratchpad/r43pg/noTable.py`：假 cursor 對 `OBJECT_ID` 回 `(None,)`，`due_days` 換成空清單（只看 `tdcc` 判斷，它在 `if not days` 之前）。

```
share_state: (False, None, 0, 0) ["SELECT OBJECT_ID('share_distribution')"]
_load_share: [] ["SELECT OBJECT_ID('share_distribution')"]
2026-11-23 21:45:00 None tdcc = None empty = True
2026-11-23 21:45:00 (False, None, 0, 0) tdcc = None empty = True
  若表存在且空： {'latest': None} 2026-11-16
2026-11-24 21:45:00 None tdcc = None empty = True
2026-11-24 21:45:00 (False, None, 0, 0) tdcc = None empty = True
  若表存在且空： {'latest': None} 2026-11-16
```

- 11/23、11/24 晚上：表不存在 → 不排 `tdcc`；對照組「表存在但空」才會排（`last_full_week` = 11/16 那週，即官方 11/20 資料）。
- `check` 在表不存在時會多一行「集保股權分散：尚未建立資料表，請執行一次 python -m twstock setup-db」，不算異常、回傳碼不變（`test_iter43 test_lines`、`test_iter03:168` 照過）。

## 五、前端檢查（內建瀏覽器、`http://127.0.0.1:8001`）

### 5-0 環境與 localStorage

- 開始前先開 `http://127.0.0.1:8001/__none__`（404 頁、同源、不執行 app.js）讀 localStorage：**`{}`（沒有任何 key）**。
- 背景起 `python3 -u -m twstock serve --port 8001 --no-browser`；網址一律 `127.0.0.1`。
- 載入的是新版：`stock.js?v=a6ab2ef4`、`app.js?v=0283995e`、`tools.js?v=05638786`、`app.css?v=55349eb3`。

### 5-1 目前匯出資料（沒有 `sh`）：籌碼頁和改動前相同

| 頁面 | 組（順序） | 圖容器 | 「股權分散」字樣 |
|---|---|---|---|
| 2421 籌碼 | 法人買賣超、信用交易、借券組 | `cpC`、`ciC`、`cuC`、`fhC`、`cmC`、`clC`（6 張，`fhC` 為外資持股，原本就有） | 無 |
| 0050 籌碼（ETF） | 信用交易、借券組 | `cmC`、`clC` | 無 |

- `App.stockCache['2421']` 沒有 `sh` 鍵（匯出資料確實尚未含 `sh`）。
- console：唯一的錯誤是我自己開的 `/__none__` 404（network 紀錄確認），頁面本身 0 個錯誤。
- 新程式碼在沒有 `sh` 時：`renderStock` 的 `SH = null` → `''`；`buildChip` 的新行第一個條件 `data.sh` 為假，不建週圖。

### 5-2 模擬 `sh`（只在頁面記憶體：`App.stockCache[代號].sh = …` 後重呼 `renderStock(代號, 'chip')`，不改任何檔案）

模擬資料：最新一週 11/20 取第三節手算值（2421、0050、00406A），往前每週固定增減（`b` +0.12、`k` +0.04、`m` −0.05、`n` +312…），`r` = 100 − `b` − `m`。

| 情境 | 4 張卡 | 週圖 | 說明文字 | 組順序 |
|---|---|---|---|---|
| 2421 股票、6 週 | 持股超過 400 張 63.33%（1週 +0.12　4週 +0.48（百分點）／100 人）、持股超過 1,000 張 51.97%、50 張以下 22.99%（1週 -0.07　4週 -0.28）、**股東人數** 53,095 人（1週 +312　4週 +1,248（人）／未滿 1 張 32,045 人） | `shC`、`snC` 兩張（共 8 張圖）；圖例「11/20 超過 400 張 63.33% 50 張以下 22.99% 超過 50 至 400 張 13.68%」「11/20 股東 53,095 人」 | 股票版說明逐字和設計 `SH_NOTE[0]` 相同 | 法人買賣超 → **股權分散** → 信用交易 → 借券組 |
| 2421 股票、1 週 | 數字同上，1週／4週全為 `--` | 無週圖、無容器（圖仍 6 張，同 5-1） | 「自 11/20 起收錄，累積 2 週後顯示走勢。」＋股票說明 | 同上 |
| 0050 ETF、6 週 | 23.17%、21.51%、58.38%、**受益人數** 4,038,137 人 | `shC`、`snC`；圖例「受益人 4,038,137 人」 | ETF 版說明（「人數為受益人數…」） | **股權分散**排第一 → 信用交易 → 借券組 |
| 00406A ETF、1 週 | 23.09%、10.77%、受益人數 635,412 人；變化全 `--` | 無週圖 | 「自 11/20 起收錄…」＋ETF 說明 | 同上 |
| 00406A ETF、6 週 | 4 張卡、受益人數 | 兩張週圖、圖例「受益人」 | ETF 說明 | 同上 |

- 組標題右側小字：「資料日 11/20（每週一次，集保結算所）」。
- 線色：超過 400 張藍色實線、50 張以下橘色虛線、人數藍線，和設計 5-4 相符。

### 5-3 寬度、深淺色、console

| 寬 × 色 | 檢查 | `scrollWidth` |
|---|---|---|
| 1024 淺色 | 2421 6 週／1 週、0050 6 週、00406A 1 週／6 週（如上表）；截圖：卡片一列 4 張、兩張週圖正常 | 1024 = `innerWidth` |
| 1024 深色 | 0050 6 週截圖：卡片、週圖、圖例、虛線在深色底清楚；2421 1 週文字正常 | 1024 |
| 375 淺色 | 2421 6 週截圖：卡片 2 × 2、圖例換行不撐寬、兩張週圖正常；0050 6 週文字與圖例正常 | 375 |
| 375 深色 | 00406A 1 週截圖：卡片 2 × 2、「自 11/20 起收錄…」、ETF 說明 | 375 |

- 觀察（設計第九節已列）：375 寬時卡片副標「（百分點）」「（人）」會折到第二行，不影響閱讀，交 QA 觀察。
- console：全程除了 `/__none__` 404 之外 0 個錯誤。

### 5-4 結束清理

- 測試中 app 寫入了 `tw.stockTab = "chip"`；已 `localStorage.clear()` 還原成開始前的 `{}`，再到 `/__none__` 確認仍是 `{}`。
- 視窗已設回 desktop preset。
- `pkill -f "twstock serve --port 8001"`；`lsof -iTCP:8001 -sTCP:LISTEN`、`lsof -iTCP:8002 -sTCP:LISTEN` 都沒有輸出（沒有 LISTEN）。

## 六、和設計不同之處

- **無**。diff 原樣套用、未做任何修正；舊測試 0 行改動。

## 七、上線步驟（寫資料庫、打外部 API，**需使用者同意後才執行**）

時機：11/23（一）晚第 40 輪上線確認之後；**11/24～11/27 任一晚、排程跑完之後**（不要和排程同時跑），**11/28 前完成**（11/28 起官方檔換成 11/27 那週，就拿不到 11/20）。

1. `python3 -u -m twstock backup`
2. `python3 -u -m twstock setup-db`，再跑一次，確認可重複執行、不報錯（提示含 `share_distribution（第 43 輪）`）。
3. 記下 `collect_runs` 最近一筆的請求數，然後 `python3 -u -m twstock collect --catch-up`：
   - 輸出有一行 `  🏦 集保股權分散 2026-11-20：股票 N 檔、ETF M 檔`（預期 N ≈ 1,992、M ≈ 367）。
   - 請求數比同樣情況多 1（行情已齊時就是 1）；自動匯出（印出匯出耗時）。
4. 再跑一次 `python3 -u -m twstock collect --catch-up`：沒有 🏦 行、opendata 請求 +0。
5. 若第 3 步沒有自動匯出，才執行 `python3 -u -m twstock export`。
6. `python3 -u -m twstock check`：多一行 `集保股權分散最新一週：2026-11-20（股票 N 檔、ETF M 檔）`，回傳碼和套用前相同。
7. 抽查 `site/data/stocks/2421.json`、`site/data/etfp/00406A.json`、`site/data/etfp/0050.json` 的 `sh`，和設計第三節手算表相同（2421：b 63.33、k 51.97、m 13.68、r 22.99、n 53095、bn 100、z 32045；00406A：23.09、10.77、48.36、28.9、635412、5584、22555；0050：23.17、21.51、18.45、58.39、4038137、1054、1644997）。8001 冒煙測試 2421、0050 籌碼分頁：4 張卡、沒有週圖、「自 11/20 起收錄，累積 2 週後顯示走勢。」；測完關 8001。
8. D116 = A：上線確認時開集保查詢網頁看一次表頭（只看頁面），確認 12 級起於 400,001 股、15 級起於 1,000,001 股、8 級止於 50,000 股；不符只改畫面文字。
9. 11/30（一）晚之後：`check` 最新一週 11/27、籌碼頁出現兩張週圖。

- 不回補；不安裝排程、不改系統設定。
- 若程式已進專案但尚未 `setup-db`：排程照常（第四節），不必趕在同一晚做完。

## 八、交給 QA 的注意事項

1. 舊測試 0 行改動；`test_iter01～43` 全部通過；`?v=` 四個一致。
2. 「表不存在不啟用」是本輪上線安全的關鍵：請再以 `test_iter43` 情境 17、`_load_share` 只下 1 個查詢、`run_check` 印「尚未建立資料表」三點覆核；11/23 晚排程（第 40 輪上線確認）的輸出應和改動前完全相同（沒有「集保」字樣、請求數不變）。
3. 前端只能用模擬 `sh` 驗（匯出資料要等上線後才有）；模擬方式見 5-2（頁面記憶體注入，不改檔案）。真實資料的抽查在上線第 7 步。
4. 375 寬「（百分點）」折行（設計第九節已列），請判斷是否可接受。
5. `share_pct` 用整數運算（1.005 → 1.01）；`28.9` 去尾 0、整數 `100` 不帶 `.0`，`test_export` 已鎖。
6. `tdcc` 失敗只印 ⚠️、不列入 `undated_errors`、不通知、同一天下一次執行再試（`test_isolation`）；官方未更新時記 `tdcc_on`，同一天不再抓。
7. 收集時 `share_state` 會多 2 個走索引的查詢（表存在後），設計第八節差異 6 已說明。
8. 禁用詞：本文件與新程式已自查，無禁用詞（`test_wiring_and_words` 也檢查新程式）；本文件以「借券組」稱呼網站原有的借券那一組，避免禁用詞。

## 九、待使用者決定或同意

- 本輪 PG 沒有新的決策事項（已 grep `docs/`，目前最大 D117；沒有新增 D118）。
- **需使用者同意**：第七節上線步驟（backup → setup-db ×2 → collect --catch-up → 再跑一次 → 必要時 export → check → 抽查），11/24～11/27 任一晚排程跑完後執行，11/28 前完成。
