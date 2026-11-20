# 第 39 輪｜PG：實作紀錄

- 撰寫日期：2026-11-21（週六）
- 依據：
  - `39/03-design.md`、`39/03-design.diff`（601 行）。
  - 使用者 11/21「照建議，進 PG」：**D84 = A**（二代健保單次上限 1,000 萬元）、**D84-1 = A**（換股票時清空持有成本）、**D84-2 = A**（加「股票／ETF」分段鈕）。
- 守則：
  - 本輪只改前端與測試，**不需要 `export`**；資料庫 0 次、外部請求 0 次。
  - 沒有讀、印、複製 `.env`；沒有 git commit／push。
  - 沒有碰 8000；8001 從專案目錄啟動，測完已關閉（`lsof` 沒有輸出），伺服器 404 只有 `favicon.ico`。
  - 瀏覽器已恢復 preset desktop、淺色；localStorage 測試後恢復為 `{"tw.todayTab":"ov"}`。

---

## 一、套用

- `git apply --check` 通過後 `git apply docs/iterations/39/03-design.diff`，**沒有手動修改**。D84～D84-2 都是 A，設計 diff 已照此做。

| 檔案 | ＋／−（`git diff --numstat`） |
|---|---|
| `site/tools.js` | ＋72／−4 |
| `site/app.js` | ＋1／−1 |
| `site/stock.js` | ＋2 |
| `site/app.css` | ＋1 |
| `site/index.html` | ＋4／−4 |
| `README.md` | ＋2 |
| `tests/test_iter39.py` | ＋399（新增） |

- `?v=`：`app.css` 16263394、`app.js` a88e48d3、`stock.js` a88a6b25、`tools.js` 2a957b9a，和 `shasum` 前 8 碼相同。
- 和設計第四節的行數完全一致。

## 二、測試

- `test_iter01～39` 39 個全部通過（`logs/iter39_pg_tests.log`）。
- `test_iter39` 13 個測試全部通過：
  - 官方參考價全量比對：上市息 830、上櫃息 603、上櫃配股 60、上市配股 1、上市 ETF 545、上櫃 ETF 668，全部相同。
  - 反證 15 種全部擋下。

## 三、8001 冒煙（375 淺色）

| 頁面 | 結果 |
|---|---|
| `#/tools/dv?c=2330` | 帶入前收 2,000、現金 7.000001、近一年 24.000082；提示「已帶入 09/16 的股利（最近一次）」「上次官方參考價 2,377.99（09/16，前收 2,385）」。前收改成 2,385 → 參考價 **2,377.99**，和官方相同；`scrollWidth` 375 |
| `#/tools/dv?c=0056` | 股票／ETF 自動選 ETF；帶入現金 1.72、近一年 4.936；表下有「國外成分、槓反 ETF 漲跌幅規定不同」；持有成本空白；`scrollWidth` 375 |
| 個股 2063「基本面」 | 「股利與填息」標題列有「試算 →」，點了進 `#/tools/dv?c=2063`，帶入配股 99.99999376 |

- 主控台只有 `ERR_CONNECTION_REFUSED`，是分頁在 8001 停止期間留下的，和本輪程式無關。
- 320 寬、深色、驗證訊息、各帶入情況逐條驗收留給 QA（設計第三節對應表）。

## 四、和設計的差異

- 設計 diff：無差異。
- 另加第五節「額外修正」（使用者 11/21 PG 階段提出，不在設計 diff 內）。

## 五、額外修正：個股搜尋框 Enter（F39-5）

- 使用者 11/21：「現在一按 enter 就會送出，應該要實際有點選到個股再送出」。
- 原因（`site/app.js` `setupSearch`）：
  - 每次輸入後 `active = 0`，第一筆候選會自動選取，所以一按 Enter 就進第一筆。
  - 用注音、倉頡輸入時，按 Enter 確認選字也會觸發 keydown，同樣會跳頁。
- 改法（`app.js` ＋10／−4；連同 F39-1 路由那 1 行，本輪 `app.js` 合計 ＋11／−5）：
  - 預設 `active = -1`，不選取任何候選，也不顯示反白。
  - 先用 ↓／↑ 選到候選後，Enter 進該檔。
  - 沒選到時，只有輸入的內容就是某一檔候選的完整代號（不分大小寫、前後空白不計，例：`2330`、`00981a`）才進該檔；只打代號開頭或名稱時 Enter 不動作（`preventDefault`），清單保持開著。
  - 選字中（`isComposing` 或 `keyCode 229`）的按鍵直接略過。
  - ↓ 從未選取開始是第 1 筆，↑ 從未選取開始是最後一筆，到頭會循環。
  - 滑鼠點候選、☆ 加入自選不變。
- `index.html`：`app.js?v=5ebf1056`。
- 測試：`test_iter39` 加 `test_search_enter`，用 node 執行 `setupSearch` 並模擬 DOM。
  - 涵蓋：沒選取時 Enter、選字中 Enter、方向鍵循環、選到後 Enter、完整代號＋Enter（含大小寫、空白）、代號開頭＋Enter、沒有候選、滑鼠點選。
  - 反證 5 種（預設選第一筆、選字中也送出、↑ 從未選取跳錯、完整代號不送出、代號開頭也送出）都擋下。
  - `test_iter39` 共 14 個測試、450 行；`test_iter01～39` 全部通過（`logs/iter39_pg_tests.log` 已重跑）。
- 8001 實測（實際鍵盤輸入）：
  - 輸入 2330 按 Enter → 留在 `#/today/ov`，清單開著、沒有反白。
  - 按 ↓ 再按 Enter → 進 `#/stock/2330`，搜尋框清空。
  - 輸入 0056 後滑鼠點候選 → 進 `#/stock/0056`。
  - 輸入 233 按 Enter → 不跳頁；補成 2330 按 Enter → 進 `#/stock/2330`；輸入 00981a 按 Enter → 進 `#/stock/00981A`。
  - 主控台沒有錯誤；測完 localStorage 恢復為 `{"tw.todayTab":"ov"}`，8001 已關閉。
- 使用者 11/21 補充：完整代號＋Enter 要直接進入（已加上，見上）。

## 六、待 commit 的檔案

- `site/tools.js`、`site/app.js`、`site/stock.js`、`site/app.css`、`site/index.html`、`README.md`。
- `tests/test_iter39.py`。
- `docs/iterations/39/`（01～04、`03-design.diff`）；QA 後更新 `docs/iterations/README.md`。
- `logs/` 不進 commit。
