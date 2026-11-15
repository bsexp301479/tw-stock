# 第 27 輪｜PG 工程師：實作紀錄

- 依據：`docs/iterations/27/02-design.md`（第六節實作順序、附錄 A diff、附錄 B `tests/test_iter27.py`）
- 基準：HEAD `7562f10`；未 commit（交 QA）

## 一、套用方式

1. 前置比對：專案的 `site/*.js`、`site/*.css`、`site/index.html`、`tests/*.py` 與設計師原型 `ux27d/orig` 逐檔 `cmp`，**全部一致**。
2. 從設計文件取出附錄 A，與原型 `orig → proj` 的實際 diff 比對內容（扣除檔頭），**完全相同**；附錄 B 與原型 `proj/tests/test_iter27.py` **完全相同**。
3. 路徑前綴 `orig/`、`proj/` 改成 `a/`、`b/`，`patch -p1 --dry-run` 全部乾淨後正式套用；8 個檔案、無 `.rej`／`.orig`。
4. 新增 `tests/test_iter27.py`（附錄 B 全文）。
5. 套用後 `site/`、`tests/` 與原型 `proj` 逐檔一致。

## 二、實際改動（`git diff --numstat`）

| 檔案 | 新增 | 刪除 |
|---|---|---|
| `site/app.css` | 16 | 9 |
| `site/app.js` | 81 | 32 |
| `site/index.html` | 3 | 3 |
| `site/stock.js` | 19 | 20 |
| `tests/test_iter11.py` | 1 | 1 |
| `tests/test_iter12.py` | 1 | 1 |
| `tests/test_iter17.py` | 1 | 1 |
| `tests/test_iter23.py` | 2 | 2 |
| `tests/test_iter27.py`（新檔） | 231 | — |

- 未改 `twstock/`、`site/data/`；第 24 輪的未追蹤檔（`docs/iterations/24/`、3 個 `tests/fixtures/*_mini.json`）未動。

## 三、與設計的差異

- **程式內容無差異**（附錄 A 原樣套用）。
- 僅統計上的小差：設計第〇節寫 `app.js` ＋80／−32，`git diff --numstat` 為 ＋81／−32；因 diff 與原型逐字相同，屬設計文件的計數誤差，不影響內容。

## 四、`?v=`

套用後實算 `shasum | cut -c1-8`，與設計 4-3「只套第 27 輪」一致，附錄 A 已帶入，不需再改：

| 檔案 | `?v=` |
|---|---|
| `app.css` | `39f292f5` |
| `app.js` | `62040b25` |
| `stock.js` | `51cc333a` |

## 五、測試結果

- `node --check site/app.js`、`site/stock.js`（node v14.17.1）：通過。新增行未使用 `.at()`、`replaceAll`。
- `for f in tests/test_iter*.py`：**26 個檔案全數通過**（含 `test_iter23.test_version_hash`、`test_iter27` 13 項）。
- 用語：新增行唯一命中的是既有資料欄名「借券賣出」（官方欄名，`test_no_advice_words` 也已排除）。

## 六、反向驗證

在 scratchpad 複製專案（`rsync --exclude .env --exclude .git`，排除資料目錄），用 `git show HEAD:` 換回舊版 `app.js`、`app.css`、`stock.js`、`index.html`，保留新測試：

- `test_iter27` 13 項逐一執行：**12 項失敗**（D27-01～10 全部）；`test_no_advice_words` 通過，屬用語防護測試，舊程式本來就應通過。
- 改過的舊測試 `test_iter11`、`12`、`17`、`23` 對舊程式皆失敗，確認修改後的鎖定確實指向新行為。

## 七、8001 冒煙測試

- 強制重新抓取 `app.js`、`app.css`、`stock.js`、`index.html` 後重新整理，頁面載入 `app.css?v=39f292f5`、`app.js?v=62040b25`、`stock.js?v=51cc333a`。
- 375×812 與 1024×768（瀏覽器當時為深色）：今日 4 分頁、泡泡圖、排行、新訊號、選股、ETF、個股 2330、自選，`scrollWidth` 皆等於視窗寬；分頁標題皆符合 D27-10。
- 抽測結果（皆與設計期望值相符）：

| 項目 | 結果 |
|---|---|
| 處置摘要（375） | 「即將處置 0　處置中 5　接近處置（推算）9　今日注意 48」；`.al-near a` 為「台揚（第一款連 2 日）」，無 `title` |
| 日期列（375） | 高 18 |
| 排行／新訊號表頭 | 捲到表格中段，`thead th` 頂端 55 = `.top` 下緣 55（375、1024 皆是） |
| 新訊號 `tr.hl-sub` | 375 `table-row`、1024 `none` |
| 選股 `?ma=3&nh=60&xd=1&xn=1&xc=1` | 「條件 2 個＋排除 3 個」「符合 61 檔 ↓」，收合標籤含 ✕ |
| 泡泡圖 Y 軸 | 「↓ 偏流出　近 5 日日均 − 20 日日均（億/天）　偏流入 ↑」 |
| 個股 2330（375） | `.metrics.kv` 889、`#kC` 561；點「融券」後只有該鈕為選取、`tw.mgv=sb` |
| 期貨未平倉表（1024） | `.oi-tbl` 457 = `.tbl-wrap` 457 |
| `#/rank` | 正規化為 `#/rank/n+` |
| 自選空狀態 | 有「搜尋股票」鈕，點擊後 focus `#q`；搜尋 2330 點 ☆ → ★、清單不關、網址不變、`tw.watch` 含 2330 |
| 自選事件卡 | 2360「處置 11/09～11/13（最後一天）」、1709「注意：…」；事件卡在表格之後 |

- 主控台錯誤：0 則。
- 結束後：刪除本次新增的 localStorage 鍵（`tw.mgv`、`tw.watch`、`tw.rank2` 與暫存鍵），保留原有的 `tw.todayTab`、`tw.stockTab`；viewport 恢復 desktop；8001 已關閉（`lsof` 無 LISTEN）；8000 未碰。

## 八、給 QA 的注意事項

1. 本次冒煙只在**深色**下量測；淺色的對比值（象限卡、MA 圖例、泡泡透明度 1）請依設計 7-3 補測。
2. `#/today` 在同一次瀏覽中會回到上次分頁（例：先看過期貨，再點「今日」會到 `#/today/fut`），量「新開開總覽」要先重新整理清掉 `App.todayTab`。
3. 自選的 `tw.watch` 是頁面載入時讀取，直接改 localStorage 後要重新整理才會生效。
4. 未實測：375 編輯模式 ✕ 觸控範圍、拖曳到畫面邊緣自動捲動、`tw.mgv=lb` 開無借券股票退回融資、泡泡圖手機點泡泡捲到明細、8299／2421／0050 的數字列位置。這些請依 7-3 清單驗證。
5. 與第 24 輪：建議先 27 後 24；`index.html` 的 `?v=` 會衝突，套完第 24 輪後以 `test_iter23` 印出的 3 行為準（設計 4-3、4-4）。
