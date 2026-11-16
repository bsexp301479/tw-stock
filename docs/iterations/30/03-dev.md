# 第 30 輪｜PG 工程師：實作紀錄

- 撰寫日期：2026-11-17（週二）
- 依據：
  - `30/02-design.md`、`30/02-design.diff`。
  - 使用者 11/17「同意，進 PG」：同意改 `test_iter14:94`、`test_iter27:153` 兩行舊測試。
- 守則：
  - 沒有 `export`，沒有寫資料庫，沒有外部請求。
  - 沒有動 `.env`、`_archive/`；沒有碰 8000；沒有 commit。

---

## 一、套用方式

1. 備份改前檔案到 `logs/iter30_before/`：`app.css`、`app.js`、`stock.js`、`index.html`、`test_iter14.py`、`test_iter27.py`。`logs/` 在 `.gitignore` 中。
2. `patch -p1 < docs/iterations/30/02-design.diff`：7 個檔都沒有 offset 或 fuzz。
3. 套用後 `site/app.css`、`app.js`、`stock.js` 和設計師原型 `proj` 逐位元組相同（`diff -q`）。

## 二、實際改動（`git diff --numstat`）

| 檔案 | ＋／− | 內容 |
|---|---|---|
| `site/app.js` | ＋80／−51 | D30-02～08、10、11；`stickHeads` 起點（D30-01） |
| `site/stock.js` | ＋10／−4 | D30-01 分頁列、D30-09 新訊號收合、D30-10 `cardsHTML`、D30-12 `.m3` |
| `site/app.css` | ＋20／−0 | 檔尾「第 30 輪 UI/UX 全站體檢」一段 |
| `site/index.html` | ＋3／−3 | `app.css?v=a69df04b`、`app.js?v=895b2037`、`stock.js?v=41db19b1` |
| `tests/test_iter14.py` | ＋1／−1 | 第 94 行，使用者同意 |
| `tests/test_iter27.py` | ＋1／−1 | 第 153 行，使用者同意 |
| `tests/test_iter30.py`（新） | 162 行 | 8 個測試 |

- 沒有動 `twstock/`、`collectors/`、`site/data`。
- 第 29 輪的 `buildChip`、籌碼分頁沒有動。

## 三、與設計的差異

無。直接套用設計 diff，沒有手動調整。

## 四、測試（`logs/iter30_dev_tests.log`）

- `test_iter01`～`30`：**30 個全部通過**。
- `node --check site/app.js site/stock.js`：通過。
- `test_iter23`：`?v=` 和 sha1 前 8 碼一致。

## 五、反向驗證

- 設計師已在副本用 `orig` 跑 `test_iter30`：8 個全部失敗。
- 本輪套用的程式和原型相同，所以沒有重做。

## 六、8001 冒煙（內建瀏覽器）

### 前置

- 在專案目錄背景執行 `python3 -u -m twstock serve --port 8001 --no-browser`。
- 對 `/`、`index.html`、`app.js`、`app.css`、`stock.js` 執行 `fetch(…, {cache:'reload'})` 後重新整理。
- 載入的 `?v=` 是 `a69df04b`／`895b2037`／`41db19b1`，和 `index.html` 相同。
- 開始時 localStorage 是 `{"tw.todayTab":"credit","tw.stockTab":"k"}`。

### 375 淺色

| 項目 | 結果 |
|---|---|
| 信用估值 | 兩張小表：融資～借券賣出餘額 6 列；本益比～加權本益比 4 列；`scrollWidth` 375 |
| 總覽 | 市場寬度小表 5 列；象限 4 格 `data-q` 齊全；差一次 15 列 |
| 象限「觀望」 | 進 `#/bubble`，標示「電子零組件」，上方顯示「已標示「觀望」1 個」 |
| 泡泡清單 0 億 | 顯示「0億」且帶漲跌色的格數：0 |
| 泡泡成分股 | 半導體展開 10 列＋「顯示全部 207 檔」，`max-height: none`；點了全部出現 |
| ETF | 可見 50 列，頁高 4,452，按鈕「顯示全部 364 檔」 |
| 排行 | 表格頂端 282；`#rankSel` 在 `.rk-q` 內；`scrollWidth` 375 |
| 搜尋「中信」 | 清單寬 359、12 筆、每列 40 |
| 個股 2421 走勢 | K 線頂端 486（當天沒有新訊號） |
| 個股 2330 新訊號 | 2 個只顯示 1 個＋「+1」，點了 2 個都出現 |
| 個股 2421 分頁列 | 捲到頁底時分頁列頂端 55 = 頂欄高 |
| 頁底換「籌碼」 | 分頁列仍在 55，顯示「建準 127 -5.22%」；新內容從 117 開始；網址 `#/stock/2421/chip`；圖 5 張，沒有重複 |
| 基本面 | 估值卡 1 列；`scrollWidth` 375 |

### 1024 深色

- 信用估值、總覽、泡泡、ETF、排行、個股走勢／籌碼／基本面：`scrollWidth` 都是 1024。
- 個股頁捲到下方時，分頁列頂端 55，背景和頁面背景相同（`rgb(14, 15, 17)`）。

### 錯誤

- 錯誤攔截器：0 個。
- 主控台只有一筆 `ERR_CONNECTION_REFUSED`。這是上次 8001 關閉後，分頁還留著舊頁面時留下的，和本輪程式無關。

### 收尾

- 測試中寫入了 `tw.todayTab`、`tw.stockTab`、`tw.focus`、`tw.rank2`，都是既有鍵。已還原成開始時的 `{"tw.todayTab":"credit","tw.stockTab":"k"}`。
- 已恢復 preset desktop、淺色。
- 已執行 `pkill -f "twstock serve --port 8001"`；`lsof -iTCP:8001 -sTCP:LISTEN` 沒有輸出。

## 七、給 QA 的注意事項

1. 驗證清單用設計第七節。D30-01 的 `.pt-nm` 要在瀏覽器窗格顯示時才會出現，因為 IntersectionObserver 在窗格隱藏時不觸發；換分頁的捲動位置不受影響。
2. 2421 當天沒有新訊號，D30-09 請用 2330（2 個新訊號）驗。
3. 泡泡清單已展開的類股會記在 `App.blOpen`，再點同一列是收合。測展開時先確認目前狀態。
4. `valCard` 在 node 14 執行要靠測試裡的 `replaceAll` polyfill。這是原本的程式，沒有改。
5. 本輪不需要 `export`。
6. 第 29 輪階段二的 B diff 要以本輪套用後的程式重做（`stock.js` 行號位移、`?v=`）。
