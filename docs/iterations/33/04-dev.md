# 第 33 輪｜PG 工程師：實作紀錄

- 撰寫日期：2026-11-18（週三）
- 依據：
  - `33/03-design.md`、`33/03-design.diff`。
  - 使用者 11/18「進 PG」。
- 守則：
  - 沒有 `export`，沒有寫資料庫，沒有外部請求。
  - 沒有動 `.env`、`_archive/`；沒有碰 8000；沒有 commit。

---

## 一、套用方式

1. 把改前的 `site/stock.js`、`app.css`、`index.html` 備份到 `logs/iter33_before/`（= `446a975`）。
2. 套用：`git apply docs/iterations/33/03-design.diff`，沒有錯誤。
3. 套用後的 `site/stock.js`、`app.css`、`index.html`、`tests/test_iter33.py`，都和設計原型 `r33d/proj` 逐位元組相同。

## 二、實際改動

| 檔案 | ＋／− | 內容 |
|---|---|---|
| `site/stock.js` | ＋37／−2 | `evLabelPos`；`buildCharts` 清除舊標籤；週／月 K 的 `setMarkers` 不寫文字；建立與定位標籤 |
| `site/app.css` | ＋3／−1 | `.chart-box` 加 `position:relative`；`.ev-lbls`、`.ev-lbl` |
| `site/index.html` | ＋2／−2 | `app.css?v=38e9e084`、`stock.js?v=2c94e005` |
| `tests/test_iter33.py`（新） | 112 行 | 5 個測試 |

- 沒有動 `twstock/`、`export.py`、`site/data`、`app.js`，舊測試也沒改。

## 三、與設計的差異

無。直接套用設計 diff，沒有手動調整。

## 四、測試（`logs/iter33_dev_tests.log`）

- `node --check site/stock.js`：通過。
- `test_iter01`～`33`：**33 個全部通過**。
- `test_iter23`：`?v=` 和 sha1 前 8 碼一致。

## 五、8001 冒煙（內建瀏覽器，窗格顯示中）

### 前置

- 從專案目錄執行 `python3 -u -m twstock serve --port 8001 --no-browser`。
- 載入的版本：`stock.js?v=2c94e005`。
- 和設計錯開，用 375 深色、1024 淺色。

### 結果

| 項目 | 結果 |
|---|---|
| 375 深：2421 週 K | 「2/24 現增」「6/10 息」都顯示，標籤中心和 K 棒差 0.5、0.5 px |
| 375 深：拖曳（`scrollToPosition(-10)`） | 差 0.5、0.5 px |
| 375 深：2421 月 K | 差 0.1、0.5 px |
| 375 深：日 K | `#kC` 裡 0 個標籤 |
| 375 深：週 → 原始 → 還原 → RSI → MACD | 1 層、2 個標籤，不殘留 |
| 375 深：00985B 週 K／月 K | 13 個標籤，顯示 12／8 個，0 處重疊，沒有蓋到右側刻度 |
| 375 深：`scrollWidth` | 375 |
| 1024 淺：2421 週 K | 差 −0.4、0.5 px；截圖確認兩個標籤有白底、細框，位在上影線之上 |
| 1024 淺：標籤顏色 | 字 `rgb(40,109,191)`、底 `rgb(255,255,255)` |
| 1024 淺：標籤中心 `elementFromPoint` | `CANVAS`（不擋拖曳與十字線） |
| 1024 淺：換主題（淺 → 深） | 1 層、2 個標籤，差 −0.4、0.5 px |
| 1024 淺：`scrollWidth` | 1024 |
| 伺服器 404 | 只有既有的 `favicon.ico` |

- 主控台另有 `ERR_CONNECTION_REFUSED`，是之前 8001 關閉時分頁留下的舊紀錄，和本輪無關。

### 收尾

- localStorage 已還原成 `{"tw.todayTab":"credit","tw.stockTab":"k"}`（測試中 `tw.kmode` 等鍵已刪除）。
- 瀏覽器已恢復 preset desktop、淺色。
- 已執行 `pkill -f "twstock serve --port 8001"`；`lsof -iTCP:8001 -sTCP:LISTEN` 沒有輸出。

## 六、給 QA 的注意事項

1. 驗收用 PM 第二節 1～10 條與設計第六節。
2. 比對基線用 `logs/iter33_before/`（= `git HEAD` 的 `site/`）。
3. **測試前先顯示瀏覽器窗格**，否則 rAF 不跑，標籤不會定位。
4. 不需要 `export`。
