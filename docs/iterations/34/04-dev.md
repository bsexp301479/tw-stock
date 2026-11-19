# 第 34 輪｜PG：試算工具 `#/tools` 實作紀錄

- 日期：2026-11-19（週四）
- 依據：`34/03-design.md`、`34/03-design.diff`（基線 HEAD `c773840`）、`34/02-pm.md`（含文末使用者回覆）。
- 守則：外部請求 0 次、資料庫 0 次；沒有 collect／export，沒有改 `site/data`；沒有讀 `.env`；沒有 commit／push／stash／checkout；沒碰 8000 埠。

## 一、改動檔案

| 檔案 | ＋／− | 內容 |
|---|---|---|
| `site/tools.js`（新） | ＋260 | 照設計 diff |
| `site/app.js` | ＋4／−1 | 照設計 diff：`routes.tools`、`route()` 補正 `#/tools…`、分頁標題「工具」 |
| `site/stock.js` | ＋1 | 照設計 diff：`#starBtn` 之後加「試算」連結 |
| `site/app.css` | ＋13 | 照設計 diff：`.tl-*` 樣式 |
| `site/index.html` | ＋6／−3 | 照設計 diff：頂欄、底欄加「工具」，載入 `tools.js`，4 個 `?v=` |
| `tests/test_iter34.py`（新） | ＋460 | 照設計 diff |
| `README.md` | ＋4／−3 | 見下 |

- 套用方式：`git apply --check docs/iterations/34/03-design.diff` 通過後 `git apply`，沒有手動修改。
- README 四處：
  1. 專案結構表 `site/` 一列末尾加「第 34 輪」工具頁說明（三個分頁、個股頁「試算」連結、只讀同站 JSON、不預填報酬率與利率、只記 `tw.fee`、質借頁不存）。
  2. 專案結構表 `tests/` 一列加 `python3 tests/test_iter34.py`。
  3. 指令區塊加 `python3 tests/test_iter34.py  # 第 34 輪測試（試算工具）`。
  4. 「網站更新與快取（第 23 輪）」一條補一句：`tools.js` 不在 `test_iter23` 範圍，改了要更新 `index.html` 的 `tools.js?v=`，由 `test_iter34` 檢查。
- `__main__.py`：設計第七節寫明指令說明不變，未改任何 Python。

## 二、與設計的差異

- 程式、測試：**無差異**（diff 原樣套用）。
- README：測試清單原本只列到 `test_iter10`（第 11～33 輪沒有補），本輪只依交辦加 `test_iter34`，沒有補中間各輪。

## 三、`?v=`（皆為檔案 SHA-1 前 8 碼，已逐一比對）

| 檔案 | `?v=` |
|---|---|
| `app.css` | `6846a88a` |
| `app.js` | `ecbf5d0a` |
| `stock.js` | `003f936e` |
| `tools.js` | `5822c16e` |

- 載入順序 `app.js` → `stock.js` → `tools.js`，皆 `defer`。

## 四、測試結果

- `node --check site/app.js site/stock.js site/tools.js`（node v14.17.1）：通過。
- `for f in tests/test_iter*.py; do python3 $f >/dev/null 2>&1 || echo FAIL $f; done`：34 個檔全部通過，無 FAIL。
- 舊測試一行未改。

## 五、冒煙測試（8001，`python3 -u -m twstock serve --port 8001 --no-browser`）

### curl

- `/`、`index.html`、`app.js?v=ecbf5d0a`、`app.css?v=6846a88a`、`stock.js?v=003f936e`、`tools.js?v=5822c16e`、`data/latest.json`、`data/stocks/2330.json`：200；`data/stocks/9999.json`：404（預期）。
- 伺服器回傳的 `tools.js` SHA-1 前 8 碼 `5822c16e`，與 `index.html` 一致；回應帶 `Cache-Control: no-cache`。

### 瀏覽器（內建瀏覽器窗格）

| 項目 | 結果 |
|---|---|
| `#/tools/dt?c=2330`（1024 淺） | 標題「工具｜台股資金流」；帶入收盤 2,100；理論兩平 2,109.16、可成交 2,110、需上漲 2 檔、淨損益 +837；漲停 2,310、跌停 1,890；無 NaN／Infinity／undefined |
| 驗收 9（375） | `#/tools/dt`、`cp`、`pl`（含 `?c=2330`、`?c=9999`）與 `#/stock/2330` 的 `scrollWidth` 皆 375；底欄 6 格在 375 每格 63px、在 320 每格 53px（「泡泡圖」文字 33px），6 個文字節點各 1 行，未截斷；320 寬 `scrollWidth` 320 |
| 驗收 10 | 375 淺、1024 深（系統深色）三個分頁截圖可讀；在深色下按色調切換鈕切為淺色，質借結果卡、「低於」標示正常 |
| 驗收 15 | 見第四節 |
| 驗收 16（路由，實測部分） | `#/tools`、`#/tools/xyz`、`#/tools/sbl` → `#/tools/dt`；`#/tools/pl?c=9999` 顯示「找不到 9999 的資料，請自行輸入價格」；頂欄與底欄「工具」為 `on` |
| 驗收 17 | 個股頁 `#/stock/2330` 捲到 y = 600，按「試算」進入 `#/tools/dt?c=2330`（y = 0、帶入 2,100），瀏覽器返回後回到 `#/stock/2330` 且 y = 600 |
| 質借實測 | 年利率 2.5%：上限 1,260,000、利息 15,534、維持率 166.67%、追繳價 1,638.00、差 −22.0%；試算價格改 1,600：維持率 126.98%「低於追繳門檻 130%」、「（目前已低於）」、回到 166% 需補擔保品市值 491,600 或償還本金 296,145（手算相符） |
| `tw.fee` | 折扣改 6 後寫入 `{"d":6,"m":20}`，理論兩平變 2,106.76；質借頁輸入後 localStorage 沒有新增鍵 |
| 外部請求 | 只有同源與既有 2 個 CDN（Plotly 2.35.2、Lightweight Charts 4.2.0），無新增 |

- 結束：`pkill -f "twstock serve --port 8001"`，確認 8001 沒有程序在聽；8000 未動。
- 瀏覽器 8001 來源的 localStorage 已清回只剩 `tw.todayTab=ov`、`tw.stockTab=k`；視窗已恢復桌面大小、淺色。

## 六、觀察（不影響驗收）

1. 375 寬質借頁表單：「可借成數」欄下方有 60%／40% 兩個快捷鈕，使同一列左邊的「數量（張）」欄往下對齊，左欄上方留一段空白。可讀、不水平捲動；若要更整齊可在之後調整排列。
2. 質借頁的輸入在同一次開啟頁面期間切到別的分頁再回來仍保留（記憶體內，重新整理後的行為未實測），沒有寫入 localStorage，符合「質借頁不存任何輸入」。
