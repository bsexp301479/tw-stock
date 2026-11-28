# 第 53 輪｜PG：實作與上線紀錄

- 撰寫日期：2026-11-28（週六，19:03～19:25 台北時間；週六沒有排程時段）；網站資料日 2026-11-27（`export` 訊息）。
- 依據：`53/01-analyst.md`、`53/02-pm.md`（驗收 52 條）、`53/03-design.md`（含第七節 PG 上線步驟、使用者決定 D237 = A、D238 = A）、`53/03-design.diff`（1,344 行）。使用者同意本輪 PG 做備份、`setup-db`、第一次收集（只收重大訊息）、`export`。
- 守則：
  - 沒有讀、印、複製 `.env`；沒有 git commit／push／stash／checkout／reset（`git apply` 只套用到工作目錄）。
  - DB 寫入只有 `setup-db`（建 `material_news`）與第一次收集（`collect_news` 兩市場各一次 MERGE）；其餘只有唯讀 SELECT、`check` 與 `export`（只讀 DB、寫 `site/data/`）。沒有跑 `collect`、`history`、`_archive/`，沒有回補。
  - 對外請求只有第一次收集的 **2 次**（上市、上櫃各 1 次，經 `twstock.fetch.request(…, isolated=True)`）；`export`、`check` 沒有外部請求。
  - 沒有碰 8000（使用者的 `twstock serve`，PID 4743，全程都在）。8001 背景啟動做預覽，結束時關閉。沒有改系統設定、沒有安裝排程。

---

## 〇、執行前

- 19:03 `pgrep -fl twstock` 只有 PID 4743 `python -m twstock serve`（`127.0.0.1:8000` LISTEN），沒有 collect／history／export 在跑。
- `git status --short` 只有 `?? docs/iterations/53/`。

## 一、套用

- `git apply --check docs/iterations/53/03-design.diff` 通過後 `git apply`，沒有警告，**沒有手動修改**；和 SA diff 沒有差異。
- `git diff --numstat`（既有檔）與新檔行數：

  | 檔案 | 加／減 |
  |---|---|
  | `twstock/collectors/catchup.py` | 13／3 |
  | `twstock/db.py` | 21／1 |
  | `twstock/health.py` | 59／2 |
  | `twstock/export.py` | 47／0 |
  | `site/app.js` | 50／1 |
  | `site/stock.js` | 18／0 |
  | `site/index.html` | 2／2 |
  | `README.md` | 2／0 |
  | `docs/iterations/README.md` | 1／0 |
  | `twstock/collectors/news.py`（新） | 110 行 |
  | `tests/test_iter53.py`（新） | 572 行 |
  | `tests/fixtures/t187ap04_L_mini.json`（新） | 89 行（diff +90，含結尾） |
  | `tests/fixtures/mopsfin_t187ap04_O_mini.json`（新） | 89 行（diff +90，含結尾） |

- 備註：`03-design.md` 第二節表中 `catchup.py` 寫 +12、`health.py` 寫 +57；實際 numstat 為 +13、+59。diff 是原樣套用，只是 SA 表格的計數略少，不影響內容。
- 程式（不含測試、文件、fixture）：新增 320 行（news.py 110＋既有檔 210）、改既有 9 行（減號行；其中 `index.html` 2 行是 `?v=`）；新測試 572 行；**舊測試（`tests/test_iter01～52`）修改 0 行**。

## 二、測試

- 套用後：`for f in tests/test_iter*.py; do python3 -u $f >/dev/null 2>&1 || echo FAIL $f; done` → 53 個檔，**0 FAIL**（約 75 秒）。
- 上線與預覽後再跑一次：**0 FAIL**（驗收 45）。

## 三、備份

- `python3 -u -m twstock backup` → `✅ 備份完成並通過 RESTORE VERIFYONLY：/Users/wudongliang/ClaudeWorkSpace/_backups/TwStock_20261128_190509.bak（125.5 MB）`。

## 四、`setup-db`

- `✅ 資料庫 [TwStock] 已確認存在`；「資料表已確認」一行含 `quarterly_balance（第 52 輪）、material_news（第 53 輪）、sbl_trades…`，結尾 `twse_index（第 51 輪）、etf_holding_gaps` 不變。

## 五、第一次收集（D238 = A，只收重大訊息）

- 指令照設計第七節步驟 4，log 在 `logs/news_first_53.log`，全文兩行：

  ```
    📰 上市重大訊息 107 筆（出表 2026-11-28，發言日 2026-11-27，新增 107 筆）
    📰 上櫃重大訊息 47 筆（出表 2026-11-28，發言日 2026-11-27，新增 47 筆）
  ```

- 請求 2 次（每市場 1 次），沒有錯誤、沒有 ⚠️、沒有重試；不寫 `collect_runs`。
- 和設計預期的差別：設計寫上櫃可能是「出表 2026-11-27，發言日 2026-11-26，或官方已更新的日子」。19:0x 時上櫃已更新為出表 11/28、發言日 11/27（47 筆；SA 中午實測時是 11/26 的 57 筆）。屬於設計允許的「官方已更新」，不是停止條件。**副作用**：上櫃 11/26 的發言在中午實測時看得到，但本站沒有收（第一次收集已經是 11/27），所以上櫃最早發言日是 11/27。
- 補充 Q53-1：上櫃的出表日期在週六 12:13 之後、19:05 之前換日（從 11/27 換到 11/28）。

## 六、`export`

- 0 個外部請求；新增一行：
  `📌 重大訊息：上市 2026-11-27 起 107 筆、上櫃 2026-11-27 起 47 筆；最新發言日 2026-11-27；近 30 天漏收 上市 0 天、上櫃 0 天`
- `✅ 匯出完成：資料日 2026-11-27，個股 2001 檔，類股 34、產業鏈 39、概念 14，台指期 500 天，latest.json 818 KB`（耗時 33.3 秒）。
- 另有既有的 ⚠️「上市官方漲跌 0、收盤 ≠ 前收，但找不到除權息／減資事件 4 筆」（1435、5236、8105、8908），是舊程式的既有訊息（diff 中只是上下文），本輪沒有動。
- 輸出抽查：`site/data/latest.json` 的 `mn.d = 2026-11-27`、`mn.n = {TPEx: 47, TWSE: 107}`、`r` 154 列；`site/data/stocks/2303.json` 最後一個鍵是 `mn`，`f = 2026-11-27`、`r` 3 則（驗收 28）。

## 七、唯讀核對

- `SELECT market, COUNT(*), MIN/MAX(speak_date), MIN/MAX(first_seen), MIN/MAX(out_date), COUNT(DISTINCT code) FROM material_news GROUP BY market`：

  | 市場 | 列數 | 發言日 | first_seen | out_date | 公司數 |
  |---|---|---|---|---|---|
  | TWSE | 107 | 11/27～11/27 | 11/28 | 11/28 | 74 |
  | TPEx | 47 | 11/27～11/27 | 11/28 | 11/28 | 40 |

- 列數 = 📰 筆數（驗收 47，依 SA 差異第 5 點）；`first_seen` 全部是當天。
- 代號不在 `stocks`：0；`fact_date IS NULL`：0；`clause IS NULL`：0；一家最多則數：8499 9 則、8422 5 則、2303／2409／3005 各 3 則。
- `python3 -u -m twstock check`：集保行之後出現「重大訊息最後成功：尚無執行紀錄」；其餘各行與先前相同，結果「**無異常**」。

## 八、`?v=`

- `site/index.html`：`app.js?v=8437a8c1`、`stock.js?v=d889075b`，等於 `shasum` 前 8 碼；`app.css?v=d1508f41`、`tools.js?v=0a050889`、`help.js?v=a5a5a7e8`、`compare.js?v=f7e0bca5` 不變且也相符。PG 沒有改程式，不需更新。

## 九、8001 預覽（內建瀏覽器，`http://127.0.0.1:8001`）

- 載入的 script 為 `app.js?v=8437a8c1`、`stock.js?v=d889075b`（已 reload）。
- 個股 2303（1024 寬）：走勢分頁最後一個 `section` 是 `sec card mn`；標題「重大訊息　11/27 起，公開資訊觀測站」；3 列 `11/27 16:05　公告本公司以租地委建方式興建廠房相關工程` 等；說明「本站自 2026/11/27 起收錄。官方每次只提供一天的資料，沒收到的日子本站目前無法補」（D237 = A 文字）、「原文請到公開資訊觀測站以代號 2303 與發言日查詢」、「只列官方主旨，不含說明全文；內容以原文為準」＋「說明」。
- 個股 8499：9 則全部顯示、沒有「顯示全部」按鈕（≤ 10 則）。
- ETF 0050：沒有重大訊息卡。
- 今日總覽（1024 寬）：`details.mn-box` 預設收合，summary「重大訊息　發言日 11/27　上市 107 則　上櫃 47 則」；展開後 154 列；篩選 `8499` 剩 9 列、焦點留在 `#mnQ`；輸入 `zzzz` 顯示「沒有符合的重大訊息」；清空恢復 154 列。自選 0 檔，沒有「只看自選」切換鈕（照規格）。
- 375 寬：今日卡預設收合、展開後每列兩行（名稱／代號・市場／時間；主旨一行以「…」截斷，照 B-3 規格）；個股 2303 卡主旨可換行；兩頁 `scrollWidth = innerWidth = 375`。
- 主控台沒有錯誤。
- 收尾：localStorage 為 `{"tw.todayTab":"ov","tw.stockTab":"k"}`；`resize_window` preset desktop；`pkill -f "twstock serve --port 8001"`，8001、8002 都沒有 LISTEN；8000（PID 4743）仍在。

## 十、禁用詞

- 對 `git diff` 中 `twstock/`、`site/`、`README.md`、`docs/iterations/README.md` 的新增行，加上 `news.py`、`test_iter53.py` 全文（「借券賣出」先移除）掃禁用詞清單：0 命中。

## 十一、和設計的差異

- 程式與測試：無（diff 原樣套用）。
- 上線結果：上櫃第一次收集到的發言日是 11/27（設計預期 11/26 或官方已更新的日子），見第五節。

## 十二、留給 QA

- 驗收 35、38 正式版畫面（本檔第九節已看過一次）。
- 驗收 46～52 依 D238 = A 的方式核對（第五～七節）。
- 週一 11/30 17:30 第一次排程 catch-up 應自動排重大訊息（兩市場，+2 個請求），之後 `check` 顯示最後成功；同時可觀察 Q53-2（週一上市資料集的發言日）與上市週五（11/27 已收）之後的週末情形。

## 十三、需要使用者決定的事項

- 無（本輪 PG 沒有新的 D 編號）。上櫃 11/26 的發言沒有收到，屬於 D224 = A 已揭露的「官方每次只提供一天、無法補」範圍，只記錄。
