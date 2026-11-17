# 第 33 輪｜PG 工程師：補強實作紀錄（D33-QA-1）

- 撰寫日期：2026-11-18（週三）
- 依據：
  - `33/06-design-fix.md`、`33/06-design-fix.diff`。
  - 使用者 11/18「進 PG」。
- 守則：
  - 沒有 `export`，沒有寫資料庫，沒有外部請求。
  - 沒有動 `.env`、`_archive/`，沒有碰 8000，沒有 commit。

---

## 一、套用方式

1. 備份改前的檔案到 `logs/iter33_fix_before/`：`site/stock.js`、`site/index.html`、`tests/test_iter33.py`。這三個檔就是第一次 PG 套用後的版本。
2. 執行 `git apply docs/iterations/33/06-design-fix.diff`，沒有錯誤。
3. 套用後的 `site/stock.js`、`index.html`、`tests/test_iter33.py`，以及沒有改動的 `app.css`，都和設計原型 `r33f/proj` 逐位元組相同。

## 二、實際改動

| 檔案 | ＋／− | 內容 |
|---|---|---|
| `site/stock.js` | ＋12／−8 | `evLabelPos(items, W, bars = [], h = 18)`：依標籤寬度範圍內的最高點決定高度；錯開改成「放到相撞標籤的上方一層」；`buildCharts` 傳入 `bars` |
| `site/index.html` | ＋1／−1 | `stock.js?v=d65e3485`（和 sha1 前 8 碼一致） |
| `tests/test_iter33.py` | ＋24／−3 | 新增 `test_label_bars`；`test_wiring` 改成檢查新的接線 |

- 和設計沒有差異。
- 舊測試沒有改。

## 三、測試（`logs/iter33_fix_dev_tests.log`）

- `node --check site/stock.js`：通過。
- `test_iter01～33`：**33 個全部通過**。

## 四、8001 冒煙（從專案目錄啟動，1024 淺色，窗格在前景）

- 載入的版本：`stock.js?v=d65e3485`。

| 項目 | 結果 |
|---|---|
| 週 K 像素檢查（6138、6465、6186、4155、2421） | 5 檔都沒有標籤蓋到 K 棒。6465 有 104 個像素，只落在 1～2 列，是最新價的價格虛線 |
| 標籤顯示與重疊 | 全部顯示，0 處重疊（6186 兩個標籤都有顯示） |
| 2421 標籤中心和箭頭的差 | 預設 −0.3、0.7 px；縮放到 30 根後 0.2、0.2 px |
| 月 → 日 → 週 | 1 層／2 個 → 0／0 → 1 層／2 個，不殘留 |
| 標籤中心的 `elementFromPoint` | `CANVAS`，不擋操作 |
| `scrollWidth` | 1024 |
| 離開到今日頁 | 0 個標籤 |
| 伺服器 404 | 只有 `favicon.ico` |

### 收尾

- localStorage 已還原成 `{"tw.todayTab":"credit","tw.stockTab":"k"}`。
- 瀏覽器已恢復 preset desktop、淺色。
- 已執行 `pkill -f "twstock serve --port 8001"`；`lsof -iTCP:8001 -sTCP:LISTEN` 沒有輸出。

## 五、給 QA 的注意事項

1. 重驗 D33-QA-1：
   - 375 深色，週 K 39 檔做像素檢查。
   - 只落在 1～2 列的命中是價格線，要排除。
2. 回歸 PM 驗收 1～10。
3. 反證腳本 `logs/iter33_qa_contrast.py` 的「不限一層錯開」要換成新的字面。
4. 比對基線用 `logs/iter33_fix_before/`。
5. 窗格要顯示在前景，否則 rAF 不跑，標籤不會定位。
