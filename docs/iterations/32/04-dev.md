# 第 32 輪｜PG 工程師：實作紀錄

- 撰寫日期：2026-11-17（週二）晚上
- 依據：
  - `32/03-design.md`、`32/03-design.diff`。
  - 使用者 11/17「進 PG」。
- 守則：
  - 沒有 `export`，沒有寫資料庫，沒有外部請求。
  - 沒有動 `.env`、`_archive/`；沒有碰 8000；沒有 commit。

---

## 一、套用方式

1. 把改前的 `site/app.js`、`app.css`、`index.html` 備份到 `logs/iter32_before/`（= `930590a`）。
2. 套用：`git apply docs/iterations/32/03-design.diff`，沒有錯誤。
3. 套用後的 `site/app.js`、`app.css`、`index.html`、`tests/test_iter32.py`，都和設計原型 `r32d/proj` 逐位元組相同。

## 二、實際改動

| 檔案 | ＋／− | 內容 |
|---|---|---|
| `site/app.js` | ＋51／−8 | 路由解析 `#/watch?add=…`；`renderWatch` 加欄位組、分享鈕、確認列；新函式 `watchColTable`、`watchAddList`、`watchAddNote`、`shareWatch`；`screenTable` 加 `o.rm` |
| `site/app.css` | ＋1 | `.w-url` |
| `site/index.html` | ＋2／−2 | `app.css?v=65320274`、`app.js?v=9294a296` |
| `tests/test_iter32.py`（新） | 209 行 | 8 個測試 |

- 沒有動 `twstock/`、`export.py`、`site/data`、`stock.js`，舊測試也沒改。

## 三、與設計的差異

無。直接套用設計 diff，沒有手動調整。

## 四、測試（`logs/iter32_dev_tests.log`）

- `node --check site/app.js`：通過。
- `test_iter01`～`32`：**32 個全部通過**。
- `test_iter23`：`?v=` 和 sha1 前 8 碼一致。

## 五、8001 冒煙（內建瀏覽器，窗格顯示中）

### 前置

- 從專案目錄執行 `python3 -u -m twstock serve --port 8001 --no-browser`。
- 載入的版本：`app.css?v=65320274`、`app.js?v=9294a296`。
- 和設計的實測（375 深色、1024 淺色）錯開，PG 用 375 淺色、1024 深色。

### 結果

| 項目 | 結果 |
|---|---|
| 375 淺色：開啟 `#/watch?add=2330,2881,3008,00878,2330,abc` | 網址換回 `#/watch`；確認列「要把以下 4 檔加入自選嗎？台積電、富邦金、大立光、國泰永續高股息」「略過 1 個不認得的代號：ABC」（重複的 2330 只算一次） |
| 375 淺色：按「加入」 | `tw.watch` = 2330、2881、3008、00878 |
| 375 淺色：表現 | 表頭「股票 收盤 漲跌 5日報酬 20日報酬 60日報酬 距52週高 MA20乖離」；台積電 −5.03%、−10.33%、−8.55%、16.22%、−6.65%；`scrollWidth` 375 |
| 375 淺色：表現＋編輯 | ✕ 顯示；移除富邦金 →「已從自選移除 富邦金　復原」→ 復原後清單恢復原順序，欄位組仍是「表現」 |
| 1024 深色：基本面 | 富邦金「−63.80%（9月）」「+771.40%（Q2）」，月份、季別不同時有標示；`scrollWidth` 1024 |
| 1024 深色：分享清單 | 內建瀏覽器沒有 `navigator.share`。這次用程式觸發點擊，剪貼簿拒絕寫入，所以走到第三條路徑：「請複製這個連結，…」並顯示 `…#/watch?add=2330,2881,3008,00878` |
| 副本移走 `screen.json`：切到「表現」 | 分段鈕換成「表現、基本面資料尚未產生」，表格仍是資金欄，沒有錯誤 |
| 主控台錯誤 | 0 |

- 剪貼簿「複製成功」的路徑，在設計實測時已驗過（真實點擊）。

### 收尾

- localStorage 已還原成 `{"tw.todayTab":"credit","tw.stockTab":"k"}`；測試加入的 `tw.watch` 已刪除。
- 瀏覽器已恢復 preset desktop、淺色。
- 已執行 `pkill -f "twstock serve --port 8001"`；`lsof -iTCP:8001 -sTCP:LISTEN` 沒有輸出。
- 副本的 `screen.json` 已放回原位；專案的 `site/data` 沒動。

## 六、給 QA 的注意事項

1. 驗收用 PM 第二節 1～12 條與設計第七節。「距 52 週高」依設計 2-2 的定義：(52 週高 − 收盤) ÷ 52 週高，結果為正數。
2. 比對基線用 `logs/iter32_before/`（= `git HEAD` 的 `site/`）。
3. 不需要 `export`。
4. 手機開不了 `localhost` 連結，見設計第八節觀察 1。這是已知限制，不屬於本輪範圍。
