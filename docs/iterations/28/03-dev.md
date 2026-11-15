# 第 28 輪｜PG 工程師：實作紀錄

- 依據：`docs/iterations/28/02-design.md`（第六節實作順序、附錄 A diff、附錄 B `tests/test_iter28.py`、第四節不能破壞的事項）
- 基準：HEAD `7b2bafc`，加上工作目錄中未 commit 的第 27 輪泡泡圖 Y 軸箭頭修正（`site/app.js`、`site/index.html`、`tests/test_iter27.py`、`docs/iterations/27/04-qa.md`），已保留、沒有還原
- 狀態：未 commit（交 QA）

## 一、套用方式

1. 前置比對：專案的 `site/*.js`、`site/*.css`、`site/index.html`、`tests/*.py` 與設計師原型 `ux28d/orig` 逐檔 `diff -q`，**全部一致**。
2. 從設計文件取出附錄 A（2 個 diff 區塊），與原型的 `p28site.diff`＋`p28tests_old.diff` 比對，**完全相同**；附錄 B 與原型 `proj/tests/test_iter28.py` **完全相同**。
3. 路徑前綴 `orig/`、`proj/` 改成 `a/`、`b/`，`patch -p1 --dry-run` 全部乾淨後正式套用：8 個檔案，沒有 `.rej`／`.orig`。
4. 新增 `tests/test_iter28.py`（附錄 B 全文，239 行）。
5. 套用後 `site/`、`tests/` 與原型 `proj` 逐檔一致。

## 二、實際改動

本輪（相對於套用前的工作目錄）：

| 檔案 | 新增 | 刪除 |
|---|---|---|
| `site/app.css` | 8 | 1 |
| `site/app.js` | 62 | 17 |
| `site/stock.js` | 102 | 21 |
| `site/index.html`（`?v=`） | 3 | 3 |
| `tests/test_iter12.py` | 1 | 1 |
| `tests/test_iter13.py` | 1 | 1 |
| `tests/test_iter22.py` | 2 | 2 |
| `tests/test_iter27.py` | 2 | 2 |
| `tests/test_iter28.py`（新檔） | 239 | — |

與設計第〇節「`app.css` ＋8／−1、`app.js` ＋62／−17、`stock.js` ＋102／−21、`index.html` ＋3／−3」及「舊測試 4 個檔、6 行」相同。

`git diff --stat`（相對於 HEAD，含第 27 輪未 commit 的修正）：

```
 docs/iterations/27/04-qa.md |   8 +++
 site/app.css                |   9 +++-
 site/app.js                 |  81 ++++++++++++++++++++++-------
 site/index.html             |   6 +--
 site/stock.js               | 123 ++++++++++++++++++++++++++++++++++++--------
 tests/test_iter12.py        |   2 +-
 tests/test_iter13.py        |   2 +-
 tests/test_iter22.py        |   4 +-
 tests/test_iter27.py        |   7 +--
 9 files changed, 192 insertions(+), 50 deletions(-)
```

- 沒有改 `twstock/`、`site/data/`；第 24 輪的未追蹤檔（`docs/iterations/24/`、3 個 `tests/fixtures/*_mini.json`）沒有動。

## 三、與設計的差異

- **程式沒有差異**：附錄 A 乾淨套用，內容和原型 `proj` 逐字相同，沒有另外修改。
- `?v=` 不用另外重算：套用附錄 A 後 `index.html` 就是 `app.css?v=7b2bc0df`、`app.js?v=528d35a6`、`stock.js?v=2d561731`，與設計 4-3「只套第 28 輪」一致，`test_iter23.test_version_hash` 通過。

## 四、測試

- `node --check site/app.js`、`node --check site/stock.js`（node v14.17.1）：通過。
- `for f in tests/test_iter*.py; do python3 $f > /dev/null 2>&1 || echo FAIL $f; done`：**沒有 FAIL**（`test_iter01～23、25～28`；`test_iter24` 尚未加入）。
- `tests/test_iter28.py` 10 個測試全部通過。

## 五、反向驗證

- 在 scratchpad 用 `rsync -a --exclude .env --exclude .git`（另外排除 `site/data`）複製專案，再把 `site/` 換成 `ux28d/orig/site`（套用前的版本），保留新的 `tests/test_iter28.py`，逐一執行每個測試：
  - **9 個功能測試全部失敗**：`test_chip_groups_source`、`test_chip_charts_node`、`test_oi_table_padding`、`test_route_scroll_restore`、`test_bubble_list_node`、`test_bubble_source`、`test_k_tab_layout`、`test_margin_legend_node`、`test_unknown_routes`。
  - `test_no_advice_words` 通過（檢查用語，預期在舊版也通過）。
- 和設計第〇節的結果相同，反向驗證成立。沒有使用 git stash。

## 六、8001 冒煙（內建瀏覽器）

前置：在專案目錄背景執行 `python3 -u -m twstock serve --port 8001 --no-browser`；開頁後 `fetch(…, {cache:'reload'})` 強制重新驗證 `app.js`、`app.css`、`stock.js`、`index.html`、`/` 再重新整理；載入的 `?v=` 為 `7b2bc0df`／`528d35a6`／`2d561731`，與 `index.html` 相同。8000 沒有碰。

| 項目 | 375 | 1024 | 結果 |
|---|---|---|---|
| 個股 2330 籌碼：分組 | 法人買賣超、信用交易、借券賣出；卡片列數 2、2、1 | 1、1、1 | 符合 |
| 籌碼：日期只寫在組標題 | `.kv .s` 不含日期 | 同 | 符合 |
| 籌碼：區間 20 日 | — | `#ciCL` 外資 -206,526、投信 +49,235 | 與設計相同 |
| 籌碼：切換深淺色 | 淺→深：圖重畫（canvas 換新）、scrollY 613 不變；選 120 日、捲到 1,100 再切換：仍是 120 日、scrollY 1,100 | 深→淺：重畫、仍是 20 日、scrollY 不變 | 符合 |
| 籌碼 0050（ETF） | — | 2 組（信用、借券） | 符合 |
| 期貨未平倉表 | 表寬 309 = 框寬 309；「-1,297」「+1,022」「-2,584」完整（深色截圖確認） | 457 = 457 | 符合 |
| 泡泡圖 | 預設「清單」、沒有 `#bubble`；表頭 類股／近5日／日均差／漲跌／成交；三種分組表寬 309 = 309；展開後點的列位置不變（574 → 574） | 沒有 `#bvSeg`、泡泡圖照舊；提示框「近5日 -4.3億」「+286.7億/天」「+3.81%」「3,728億」 | 符合 |
| 返回位置：排行 | `#/rank/n+` 1,576 → 個股 0 → 返回 1,576 → 前進 0 | 1,000 → 0 → 1,000 | 符合（1024 見第七節第 1 點） |
| 返回位置：泡泡清單 | 展開、捲到 700 → 點成分股 → 返回 700，仍展開 | — | 符合 |
| 走勢分頁（375 淺色） | `#kC` 頂 561、`#vC` 頂 − `#kC` 底 = 28、數字列在 `#vC` 之後高 235、`.mg-l` 高 60 | — | 與設計相同 |
| 未知網址 | `#/stock/2330/abc`→`/k`、`#/stock/0050/fund`→`/k`、`#/watch/abc`→`#/watch`、`#/bubble/x`→`#/bubble`、`#/etf/zzz`「找不到 zzz 的資料…」標題「ETF｜台股資金流」、`#/etf/0050`→`#/stock/0050`、`#/stock/9999` 找不到頁 | 抽查 `#/stock/2330/abc`、`#/etf/zzz` | 符合 |
| 水平捲動 | 各頁 `scrollWidth` = 375 | = 1024 | 無 |
| 主控台錯誤 | 只有測 `#/stock/9999` 時的 2 筆 404（`data/stocks/9999.json`，既有行為） | 同 | 符合 |

收尾：`pkill -f "twstock serve --port 8001"`，`lsof -iTCP:8001 -sTCP:LISTEN` 無輸出；localStorage 刪除測試中寫入的 `tw.group`、`tw.focus`、`tw.rank2`、`tw.theme`，`tw.todayTab`、`tw.stockTab` 還原為開始時的 `ov`、`k`；`resize_window` 已恢復 preset desktop。

## 七、給 QA 的注意事項

1. **內建瀏覽器窗格隱藏時，程式化捲動不會觸發 `scroll` 事件**（`requestAnimationFrame` 0 次）。D28-03 靠 `scroll` 事件記錄位置，所以在隱藏窗格中用 `scrollTo()` 測「返回位置」會得到 0（假失敗）。本輪 1024 第一次就因此誤判，改用 `computer` 的滾輪動作捲動後確認正常（1,000 → 0 → 1,000）。建議 QA 用滾輪捲動，或確認窗格顯示中再測。
2. 375 泡泡清單展開的成分股小表（`.panel-list`，最高 420）表寬 318、框寬 299，**框內可橫向捲動 19px**（看到「法人5日」要往右滑）；頁面本身不橫捲。這是設計原型的現狀（程式與 `proj` 相同），請 QA 判斷是否可接受、是否列入下一輪。
3. 測試會改到的 localStorage 鍵：`tw.group`、`tw.focus`、`tw.rank2`、`tw.stockTab`、`tw.todayTab`、`tw.theme`（點右上角深淺色鈕）。開始前先記下，結束後還原。本輪程式沒有新增鍵。
4. 第 24 輪尚未套用；若之後套用，依設計 4-4「先 28 後 24」，只需重算 `index.html` 的 `?v=`。
