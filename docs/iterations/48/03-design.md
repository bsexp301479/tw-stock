# 第 48 輪｜System Analyst：設計

- 撰寫日期：2026-11-24（週二）；資料日 2026-11-24。
- 依據：`48/01-analyst.md`（F48-1～F48-5、R62～R70、D157～D167 全 A）、`48/02-pm.md`（畫面文字逐字定稿、驗收 30 條；PM 自行決定 17 點使用者全部同意）。
- 產出：本檔＋`48/03-design.diff`（709 行，可直接 `git apply`；在專案目錄 `git apply --check docs/iterations/48/03-design.diff` 已通過）。
- 做法：
  - `rsync -a --exclude .git --exclude .env --exclude _backups --exclude _archive --exclude logs` 把專案複製到 scratchpad `r48sa/proj`（**副本沒有 `.env`**），`git init` 並 commit 當基準；所有修改在副本完成，diff 由副本 `git diff` 產生（新檔用 `git add -N`）。
  - 匯出前先確認整條路徑只有 SELECT：`export.py` 的 39 個 `execute` 都是 `SELECT`／`WITH`、沒有 `commit`；`health.build_status`／`load_state`／`share_exists`、`tradingcal.load_closed`／`trading_days`／`is_trading_day` 只查詢或純計算；會寫入的 `health.write_run`／`finish_run`、`tradingcal.update_calendar`／`add_adhoc`／`remove_adhoc` 不在匯出路徑。之後才在副本匯出：scratchpad 的小程式用專案 `twstock/config.py` 的 `_load_env` 把連線設定載入環境變數（沒有讀出、印出或複製內容），再匯入副本的 `twstock`、確認 `SITE_DATA_DIR` 在副本內，呼叫 `export_all()`（32.4 秒，只寫副本 `site/data`）。
  - 匯出前把副本 `site/data/` 全部 2,377 個 JSON 的 sha1 與 `latest.json` 存到 `r48sa/before/` 當比對基準。
  - 副本跑 `tests/test_iter01～48` 共 48 個檔，**全部通過**；舊測試 0 行改動。
  - 畫面：副本目錄背景起 `python3 -u -m twstock serve --port 8001 --no-browser`，內建瀏覽器開 `http://127.0.0.1:8001`（確認載入的是新 `?v=`）。
- 守則：沒有讀、印、複製 `.env`；資料庫只有匯出的 SELECT；沒有外部請求、沒有 `collect`、沒有用 8000、沒有執行 `_archive/`；專案目錄只新增本檔與 `03-design.diff`。

---

## 一、改了哪些檔（`git diff --numstat`）

| 檔案 | 加／減 | 內容 |
|---|---|---|
| `twstock/export.py` | 6／0 | 新純函式 `ix_export`（`index_return` 之後）；`export_all` 在 `w52_start = …` 下一行寫 `ix.json` |
| `site/compare.js`（新） | 170／0 | 純函式 `cmpEvents`、`cmpAdj`、`cmpBase`、`cmpAt`、`cmpStats`、`cmpLine`、`cmpCalc`、`cmpPick`、`cmpNorm`、`cmpR`；畫面 `window.renderCompare` |
| `site/app.js` | 2／1 | `routes` 在 `help:` 之後加 `compare:` 一行；頁面標題字典加 `compare: '報酬率比較'` |
| `site/stock.js` | 2／0 | `dvh` 三行之後、`onSeg('stockTabSeg'` 之前：近期表現卡標題列「比較 →」 |
| `site/app.css` | 4／0 | 淺色、兩段深色主題區塊各加 1 行 `--cmp1`～`--cmp4`；檔尾 1 行比較頁樣式 |
| `site/index.html` | 4／3 | `compare.js` 在 `help.js` 之後；`app.css`、`app.js`、`stock.js` 的 `?v=` |
| `tests/test_iter48.py`（新） | 384／0 | 14 個測試、22 個反證 |
| `README.md` | 2／0 | 測試指令一行、第 48 輪說明一段 |
| `docs/iterations/README.md` | 1／0 | 第 48 輪一行（PG／QA 之後補完） |

- 程式合計 188 行加、4 行減（`export.py` 6、`compare.js` 170、`app.js` 2、`stock.js` 2、`app.css` 4、`index.html` 4；PM 估約 140 行，多在 `compare.js` 的搜尋鍵盤操作與圖表設定）；新測試 384 行（PM 估約 400 行；上限約 580 行）。
- `index.html` 的 `?v=`（和 `shasum` 前 8 碼相同）：

  | 檔案 | `?v=` |
  |---|---|
  | `app.css` | **1ae7bbed**（原 07335b75） |
  | `app.js` | **d273c8c5**（原 5548b620） |
  | `stock.js` | **29bc6522**（原 7e6c6a13） |
  | `tools.js` | 64e7360f（不變） |
  | `help.js` | a5a5a7e8（不變） |
  | `compare.js`（新） | **6652dcfe** |

## 二、程式設計

### 2-1 `twstock/export.py`（F48-1）

```python
def ix_export(days, idx) -> dict:
    return {"d": [str(d) for d in days], "TAIEX": [_f(idx.get(d)) for d in days]}
```

- `export_all`：`w52_start = latest_date - timedelta(days=365)` 下一行 `_write(SITE_DATA_DIR / "ix.json", ix_export(p_days, idx_close["TWSE"]))`，在個股迴圈與 ETF 迴圈之外；`idx_close["TWSE"]` 只放非空值，缺的日子 `get` → `None` → JSON `null`。用既有 `_write`（暫存檔＋`os.replace`）。
- 不動：`etf_export`（雜湊仍 `711fa2b7790c`）、`etf_perf`、`E["nx"]`／`E["sh"]`／`E["epf"]`／`_write(p, E)` 順序、`latest.json`、`screen.json`；新程式不提 `sh_stock`、`sh_etf`。

### 2-2 `site/compare.js` 純函式（F48-2）

- `cmpEvents(data)`：股票用 `ev`；ETF 用 `dv`（`{d, p, r}`）＋`gx` 中不在 `dv` 的日子（`p = c[i-1]`，`r = ch[i] == null ? c[i] : Math.round((c[i] − ch[i]) × 100) / 100`）。依日期排序（同日官方在前，sort 穩定），`findIndex(d >= 事件日)` 對到生效列；第 0 列、找不到列、同一列第二筆、`r ÷ p` 在 0.02～20 以外都略過（同 `_price_events`）。回傳 `{d: 生效列日期, p, r}`，餵 `stock.js` 的 `adjFactors`（不改）。
- `cmpAdj(data)` = `prices.c × adjFactors`（`c` null → null）。
- `cmpBase(days, k)`：`20`／`60`／`120` = `days[n−1−N]`（不足 → null）；`y` = 終點年 1/1 之前最後一天；`w` = 終點往前 365 天（UTC 毫秒相減）以前最後一天。同 `stock_perf`。
- `cmpAt(d_, adj, b)`：`b`（含）以前最後一個有成交的 `[日期, 還原收盤]`（不用 `indexOf`，0052 起點日沒有資料列也找得到）。
- `cmpStats(pts)`：`pts[0]` 是起點；區間報酬、最大跌幅 `[%, 高點日, 低點日]`（高點用 `>` 更新，同值保留較早的日子；沒有下跌 → `[0, null, null]`）、年化波動（樣本標準差 ÷ (n − 1) × √250 × 100，n < 20 → null）。
- `cmpLine(days, d_, adj, b)`：`line` = `days` 中 `b`～終點每天 `[日期, %, 無成交]`（無成交沿用前值）；統計樣本 = 起點那一點＋`b` 之後有成交的日子；`last` = 最後成交日。
- `cmpCalc(ix, S, k)`：起點 `cmpBase(ix.d, k) || ix.d[0]`；任一檔第一個成交日 > 起點 → 起點改為各檔第一個成交日中最晚的那天，`late` = 第一個成交日等於新起點的代號（依網址順序）；加權指數用 `cmpLine(ix.d, ix.d, ix.TAIEX, b)`。
- `cmpNorm(arg, sub, L)`：切 `,`、trim、轉大寫、去空、去重（`Set` 保留第一次）、只留 `L.stocks` 或 `L.etfs.rows` 有的；「找不到」「最多 4 檔」提示依 PM 順序；區間不認得 → `w`。`cmpUrl(list, k)`：空 → `#/compare`。
- `cmpPick(all, q, skip)`：同頂欄 `pick`（代號開頭 → 名稱開頭 → 名稱包含，後兩組依成交額），排除已選。
- `cmpR(v)`：顯示前四捨五入到 2 位，**二進位值剛好一半時取偶數**（同 Python `round`，見第四節差異 1）；`pc(v) = sgn(cmpR(v))`。

### 2-3 `site/compare.js` 畫面（F48-3）

- `window.renderCompare(arg, sub)`：先 `disposeKCharts()`；`cmpNorm` → 載入 `data/ix.json`（存在 `App.cmpIx`，同一次瀏覽只抓一次；失敗不快取，顯示 PM 的「找不到交易日資料…」）→ 各檔 `loadStock(c, L.stocks[c] ? 'stocks' : 'etfp')`（共用 `App.stockCache`）→ ETF 沒有 `epf` 移除並提示 → 正規網址和 `location.hash` 不同才 `history.replaceState(history.state, '', 正規網址)`（不增加 `history.length`，提示在同一次 render 畫出）。
- 加入（搜尋、自選）、移除（×）、換區間：`history.replaceState(null, '', 新網址)` 後直接 `renderCompare`（同個股頁換分頁）；加入的檔接在最後。
- 版面與文字照 PM 二之一逐字：標題列、頁首說明、chip（`var(--cmpN)` 圓點）、搜尋框（滿 4 檔 `disabled`、`已滿 4 檔`）、自選快速加入（`App.watch` 依序、只列今天行情有的、不在清單中、最多 8 檔；滿 4 檔或沒有不輸出；只讀不寫）、提示、`segHTML('cmpSeg', …)`、起點說明與共同起點那一行、十字線圖例 `#cmpL`、圖下方圖例、表格（依網址順序，加權指數最後一列）、表格下方一行、`noteHTML(short, note)`（短句用變數；全文的本站起日用 `ix.d[0]`）。
- 搜尋：`input` 事件比對、方向鍵選、Enter（`isComposing`／`keyCode 229` 不送出；選到候選或輸入完整代號才加入）、Esc 關閉；清單 `mousedown` `preventDefault` 讓點選時輸入框不失焦，輸入框 `blur` 時關閉清單（不在 `document` 掛監聽，重畫不會累積）。頂欄 `#q` 不動。
- 線圖：Lightweight Charts（已載入的 4.2.0）設定同 `renderBand`（`autoSize`、透明底、`--border` 格線、`--text2` 字、`zh-TW`、`handleScroll`／`handleScale` 關閉）；加權指數先畫（`--text2`、虛線 `lineStyle 2`、寬 1），再依網址順序畫各檔（`--cmp1`～`--cmp4`、實線、寬 2）；0% 用加權指數那條的 `createPriceLine`（`--border2`、無標籤）；刻度 `sgn(v) + '%'`；十字線用 `p.logical` 取索引（所有線同長度）。
- **圖表釋放**：圖表放進 `stock.js` 的 `charts`（`charts = [c]`，和河流圖 `renderBand` 同一做法），`route()` 既有的 `window.disposeStockCharts?.()` 換頁時一併釋放；`route()` 一字不改。實測離開比較頁後 `.tv-lightweight-charts` 0 個、主控台沒有錯誤。

### 2-4 `site/stock.js`（F48-4）、`site/app.js`、`site/app.css`、`site/index.html`

- `stock.js`：`dvh` 三行之後加 2 行：找 `#view .sec-h h2` 文字等於 `E ? '近期表現（含息）' : '近期表現'` 的標題，在它的 `.sec-h` `beforeend` 加 `<span class="sp"></span><a class="small cmp-go" href="#/compare/${code}">比較 →</a>`。`perfHTML`、`:366～367`、`dvh` 三行不動；籌碼、基本面分頁沒有這張卡，所以沒有連結。
- `app.js`：`routes` 在 `help:` 那一行之後加 `compare: (arg, sub) => window.renderCompare(arg, sub),`；標題字典 `help: '名詞說明'` 後加 `, compare: '報酬率比較'`。路徑式網址由 `route()` 既有的 `split('/')` 拆出 `arg`、`sub`。
- `app.css`：淺色 `:root` 與兩段深色區塊各加一行顏色變數（見第四節差異 3）；檔尾一行 `.cmp-dot`、`.cmp-ix`、`.cmp i.dash`、`.cmp-pick`、`.cmp-c`、`.cmp-x`、`.cmp-q`（含 `.qlist` 疊層）、`.cmp-w`、`.cmp .seg`（不換行、必要時框內橫捲）、`.cmp-s`、`.cmp-ch`（260／手機 220px）、`.cmp-tbl` 名稱欄可換行、手機搜尋框獨占一行與 16px 字（避免 iOS 放大）、≤ 360px 區間按鈕左右 6px。
- 顏色（不用 `--up`／`--dn`）：

  | 變數 | 淺色 | 對 `#fff` | 深色 | 對 `#17181b` |
  |---|---|---|---|---|
  | `--cmp1` 藍 | `#4c6ef5` | 4.32 | `#748ffc` | 5.98 |
  | `--cmp2` 橘 | `#c56a00` | 3.86 | `#ff922b` | 7.95 |
  | `--cmp3` 紫 | `#ae3ec9` | 4.85 | `#da77f2` | 6.68 |
  | `--cmp4` 青 | `#0c8599` | 4.35 | `#3bc9db` | 8.93 |

  分析師原色 `#F08C00`（2.48）、`#0CA678`（3.12，且偏綠易和跌色混淆）改為上表；4 色都 ≥ 3:1。
- `index.html`：`<script src="compare.js?v=6652dcfe" defer></script>` 放在 `help.js` 那一行之後；`https://` 仍 2 個。

## 三、測試設計（`tests/test_iter48.py`，不連網、不連資料庫）

| 測試 | 內容 | 對應驗收 |
|---|---|---|
| `test_ix_export` | 自造 3 天（中間缺值）→ 鍵順序 `d`、`TAIEX`，`null`，緊湊 JSON 字串逐字 | 1 |
| `test_wiring` | `ix_export` 位置、呼叫 2 次（定義＋寫檔）、寫檔在 `w52_start` 之後與個股迴圈之前、`etf_export`～`_load_holdings` 不提 `ix`；`etf_export` 雜湊、`sh_stock`／`sh_etf` 各 3 次、`E["epf"]` 1 次 | 2 |
| `test_site_data` | 讀實際 `site/data/ix.json`（沒有時印「尚未用第 48 輪匯出」略過）：`d` = 全部 `stocks/*.json` `prices.d` 聯集、最後一天 = `latest.date`、≤ 8 KB；資料日 2026-11-24 時 259 天與首尾值、沒有 null | 1 |
| `test_full` | node 跑純函式，全部股票 `pf`＋ETF `epf` 每列的 `pc(值)` = `sgn(匯出第 3 欄)`；資料日 2026-11-24 時要剛好 2,354 檔、14,260 列 | 3 |
| `test_unit` | 自造：dv 非交易日對到下一列、第 0 列略過、gx 漲跌 null 參考價 = 收盤、gx 和 dv 同列只用官方、係數 0.01 略過、股票 `ev` 不看 `gx`；還原收盤；起點日（含不足 N 日 → null、`y`、`w`）；驗收 12 的 21 個收盤 → 63.87、少一個收盤 → null；驗收 11(b) −22.27 與高低日；每天上漲 → `[0, null, null]`；無成交標記與持平；共同起點兩檔同日；`cmpR` 7 個（含 −15.625、15.625、2.675） | 11、12、13 |
| `test_examples` | 資料日 2026-11-24 時：例 1 五個區間、例 2～6、00625K（數字、title 日期、起點、共同起點代號、0052 十字線 11/24 無成交與 11/26 +0.88、00625K 最後成交 11/05） | 4～10、13 |
| `test_norm` | 11 種網址 → 正規網址與提示逐字；搜尋排序與排除已選 | 14、16 |
| `test_dom` | 假 DOM 跑整個 `compare.js` 的 `renderCompare`：PM 文字逐字（含說明全文從 `02-pm.md` 解析）、chip HTML、表格依網址順序、加權指數最後、沒有差距／名次、自選列只列 0056、00878、圖例日期 `YYYY/MM/DD`、區間按鈕、起點說明、`replaceState` 只在網址不正規時呼叫、ETF 沒有 `epf` 提示與移除、空狀態、`ix.json` 不存在、滿 4 檔 | 15、17、18、22 |
| `test_pm_text` | 本檔引用的字串都在 `02-pm.md` | 18 |
| `test_entry` | `stock.js` 2 行字面、在 `dvh` 之後與 `onSeg('stockTabSeg'` 之前、`perfHTML` 不含 `cmp-go` | 19 |
| `test_route_and_version` | `routes` 新行在 `help:` 之後、標題字典、script 順序 app → stock → tools → help → compare、6 個 `?v=`、`tools.js`／`help.js` 不變、`https://` 2 個；README 指令與段落、docs 索引 | 20、27 |
| `test_words`、`test_node14` | `compare.js` 全檔＋`stock.js`／`app.js` 第 48 輪新行＋README 段落不含禁用詞（`test_iter47.ADVICE` ∪ `test_iter23` 清單），`compare.js` 與新行不含「差距」「名次」「第一名」；不用 `.at(`、`replaceAll`、`\|\|=`、`&&=`、`??=` | 23、24 |
| `test_contrast` | 22 個反證，每個都要讓對應檢查失敗（node 丟例外也算失敗） | 反證 |

反證：匯出缺值補 0、沒有寫 `ix.json`、ETF 不加 gx 推測調整、漲跌 null 時不用收盤、事件不對到下一列、係數不合理也採用、顯示不取偶數、年化波動用母體標準差、統計少了起點那一點、無成交不標記、共同起點只移晚上市那一檔、52 週少一天、網址不轉大寫、不去重、表格依報酬排序、自選列出已選的檔、ETF 沒有 `epf` 也比較、說明寫差距、用詞、入口加在卡片外、路由沒有標題、`compare.js` 放在 `help.js` 之前。

- 匯出前（沒有 `ix.json`）跑：`test_site_data`、`test_examples` 印略過，其餘照跑，反證仍全部擋下（副本已實測）。

## 四、和 PM 規格的差異（SA 決定，請使用者確認）

1. **顯示數字用「剛好一半取偶數」的四捨五入（`cmpR`）**：不這樣做時驗收 3 有 **5 列不同**——2345 20 日（−15.625 → 畫面 `-15.63`、匯出 `-15.62`）、2509 5 日、3663 120 日、6438 60 日、6596 120 日（都是二進位剛好一半的值；Python `round` 取偶數，瀏覽器 `toLocaleString` 遠離 0）。加 `cmpR` 後 14,260 列 0 列不同，比較頁和個股頁同一區間數字一致。`cmpR` 只用在畫面數字（區間報酬、最大跌幅、年化波動、十字線）；線圖刻度仍 `sgn`。
2. **0% 顯示 `0.00%`，不是驗收 7 寫的 `+0.00%`**：沿用全站 `sgn`（0 不加正負號）；0052 52 週十字線 `2025/11/24` 為 `0052 0.00%（無成交）`。
3. **顏色變數放進既有三個主題區塊各 1 行，不另寫深色區塊**：`test_iter26.py:84～85`、`test_iter27.py:118` 用 regex 要求深色區塊剛好 2 段；另寫一段會讓舊測試失敗。改為在淺色 `:root`、兩段深色區塊尾端各加一行 `--cmp1`～`--cmp4`（既有變數一字不改）。色碼依對比調整（見 2-4）。
4. **圖表放進 `stock.js` 的 `charts`**（PM 二之二交 SA 定）：同河流圖做法，`route()` 不改即可在換頁時釋放。
5. **區間按鈕在 ≤ 360px 縮小左右留白**：320 寬原本「20 日」等會斷成兩行；改為不換行＋≤ 360px 左右 6px，320 寬 5 個按鈕 239px 剛好一行（框內橫捲只是保險）。
6. **搜尋清單用輸入框 `blur` 關閉**，不在 `document` 掛點擊監聽（每次重畫會累積）；點清單項目時用 `mousedown` 防止先失焦。
7. **`ix.json` 讀取失敗不快取**：下次進比較頁會再試一次（匯出後不必重新整理）。
8. **多檔 ETF 沒有 `epf` 時合成一行**：`本站無法確認 X、Y 的價格調整，暫不比較`（目前 0 檔）。
9. **手機搜尋框字級 16px**：iOS 小於 16px 會自動放大畫面（工具頁輸入框同樣 16px）。
10. 搜尋結果排除已選的檔：清單已有 2330 時輸入「台積」沒有結果、顯示「找不到」（驗收 16 的「第一筆 2330」是在清單沒有 2330 時，`test_norm` 照此測）。

## 五、核對結果（副本匯出，資料日 2026-11-24）

- **`ix.json`**：5,692 bytes；鍵 `d`、`TAIEX`；259 天 2025-10-30～2026-11-24（= 全部 `stocks/*.json` `prices.d` 聯集 = `p_days`）；`TAIEX[0]` 28287.53、最後 40122.35、0 個 null。
- **逐位元組**：匯出前後 2,377 個 JSON（`stocks/`、`etfp/`、`etfs/`、`screen.json`、`latest.json`）只有 `latest.json` 不同，差異只有 `status.exported_at`；新增 `ix.json` 一個檔。
- **純函式 = 匯出值（驗收 3）**：2,354 檔、14,260 列，0 列不同（未加 `cmpR` 時 5 列，見第四節差異 1）。
- **手算例逐位（驗收 4～13，畫面也逐一核對）**：
  - 例 1 52 週：2330 `+64.17%`／`-22.63%`（2026-10-06 → 2026-11-20）／`34.93%`；2454 `+261.15%`／`-36.61%`（09-24 → 11-20）／`68.82%`；0050 `+63.97%`／`-27.51%`／`33.51%`；加權 `+51.38%`／`-27.68%`／`31.93%`。今年以來 `+45.15%`、`+190.43%`、`+48.84%`、`+38.53%`；60 日 `-6.81%`、`+8.43%`、`-8.33%`、`-11.17%`；20 日 `-7.08%`、`+2.27%`、`-10.23%`、`-12.96%`；120 日 `-4.77%`、`-5.47%`、`-8.65%`、`-10.31%`。
  - 例 2：0056 `+57.63%`／`-23.41%`（10-14 → 11-20）／`27.16%`；00878 `+67.51%`／`-18.22%`／`24.39%`；00919 `+56.81%`／`-17.57%`（10-28 → 11-23）／`22.05%`。
  - 例 3：0052 `+61.26%`／`-28.77%`／`35.60%`，十字線 2025/11/24 `0.00%（無成交）`、2025/11/26 `+0.88%`，沒有斷崖。
  - 例 4：00679B `+0.04%`／`-11.34%`（03-02 → 10-07）／`10.19%`；00687B `+0.17%`／`-11.31%`／`10.18%`。
  - 例 5：起點 2025-12-18、共同起點那一行逐字；0050 `+57.74%`／`34.60%`；00991A `+34.21%`／`-49.49%`（06-22 → 11-20）／`52.83%`；加權 `+46.07%`／`32.94%`；換 20 日不出現共同起點。
  - 例 6：共同起點 2026-11-19；0050 `+6.10%`／`-6.37%`；009833 `-0.10%`／`-6.84%`（11-19 → 11-23）；加權 `+4.41%`／`-6.23%`；年化波動三列 `--`。
  - 驗收 11、12：0050 20 日最大跌幅 `-22.27%`（2026-10-28 高點 → 2026-11-20）、年化波動 `63.87%`、加權 `61.48%`；母體標準差反證 62.26% 被擋下。
  - 驗收 13：00625K 共同起點 2025-12-05、`最後成交 11/05`、`-9.54%`、十字線 2026/11/24 `-9.54%（無成交）`；0050 `+55.60%`；加權 `+43.39%`。
- **全部測試**：`tests/test_iter01～48` 48 個檔全部通過；`git diff --stat tests/` 只有新檔 `test_iter48.py`。

## 六、畫面檢查（副本 8001，內建瀏覽器）

暫時設自選 0056、2330、9999、00878。

| 頁面 | 1024 | 375 淺 | 320 深 | 結果 |
|---|---|---|---|---|
| `#/compare/2330,2454,0050/w` | ✓（淺、深） | ✓ | ✓ | 數字同第五節；4 色＋加權灰虛線、刻度 `+xx.xx%`、十字線圖例 `YYYY/MM/DD` 隨滑鼠更新 |
| `#/compare/0050,00991A/w`、`/20` | ✓ | ✓ | ✓ | 共同起點那一行（20 日不出現） |
| `#/compare/0050,009833/20` | ✓ | ✓ | ✓ | 年化波動 `--` |
| `#/compare/0056,00878,00919,00890B/w` | ✓ | ✓ | ✓ | 4 檔＋最長名稱；表格不橫捲（375：309＝309；320：254＝254），名稱欄換行 |
| `#/compare/0052,0050/w`、`00679B,00687B,0050`、`00625K,0050` | ✓ | | | 同第五節；00625K 名稱下方 `最後成交 11/05` |
| 網址正規化 11 種 | ✓ | | | 結果與提示逐字同驗收 14；只設一次 `location.hash` 時 `history.length` 不變 |
| 搜尋／自選加入／移除／換區間／滿 4 檔 | ✓ | | | `0050`＋Enter 加入（選字中的 Enter 不加入）；自選列只有 0056、00878；加入接在最後；滿 4 檔搜尋框停用、`已滿 4 檔`、自選列不顯示；× 移除；換區間只改最後一段；這些操作 `history.length` 都不變；自選 localStorage 沒被改 |
| `#/compare` | ✓ | ✓ | ✓ | 只有標題、搜尋框、自選列、空狀態文字 |
| `ix.json` 讀取失敗（主控台暫時替換 `getJSON`） | ✓ | | | `找不到交易日資料（data/ix.json），重新匯出資料後才能比較` |
| `#/stock/2330`、`0056`、`00991A` | ✓ | ✓ | ✓ | 「比較 →」在標題列同一行最右；`#/stock/2330/chip` 沒有；點 0056 的連結到 `#/compare/0056/w`，瀏覽器返回回到 `#/stock/0056/k` |

- 三種寬度各路由 `scrollWidth = innerWidth`；320 寬區間按鈕 239px 一行；頁面標題 `報酬率比較｜台股資金流`、頂欄沒有分頁亮起；離開比較頁後圖表 0 個；主控台沒有錯誤。
- 結束：localStorage `{"tw.todayTab":"ov","tw.stockTab":"k"}`、視窗 desktop／淺色、`pkill -f "twstock serve --port 8001"`（exit 144），8001 沒有 LISTEN（8000 未碰）。

## 七、需要使用者決定的事項

- 無。舊測試 0 行；本輪沒有新增 D 編號（已 grep `docs/`，最大 D167，下一個仍從 D168 起）。第四節 10 點差異請使用者確認（第 1、3 點和 PM 驗收文字有關：第 1 點是為了讓驗收 3 的 0 列不同成立；第 3 點是避開 `test_iter26`、`test_iter27` 的深色區塊數量鎖定）。

## 八、給 PG

1. 在專案目錄 `git apply docs/iterations/48/03-design.diff`（`--check` 已通過）。
2. 匯出前把 `site/data/` 全部 JSON 的 sha1 與 `latest.json` 存到 scratchpad（驗收 2 的基準，路徑寫在 `04-dev.md`），同一晚不要先跑 `collect`。
3. 跑 `for f in tests/test_iter*.py; do python3 $f >/dev/null 2>&1 || echo FAIL $f; done`：48 個檔全過（匯出前 `test_iter48` 印「尚未用第 48 輪匯出」「略過手算例」）。
4. 依 D167 執行 `python3 -m twstock export`（只讀資料庫、只寫 `site/data/`），再跑一次全部測試（資料日 2026-11-24 時 `test_examples` 核對全部手算例、`test_full` 要剛好 2,354 檔 14,260 列）。
5. 比對：除 `latest.json` 的 `status.exported_at` 之外逐位元組不變；新增 `ix.json` 約 5.7 KB、259 天。
6. 8001 冒煙：`#/compare/2330,2454,0050/w`、`#/compare/0050,00991A/w`、`#/compare/0050,009833/20`、`#/compare/0056,00878,00919,00890B/w`、`#/compare`、`#/stock/2330`、`#/stock/0056`（1024／375／320、淺／深）；結束時 localStorage 恢復、視窗 desktop、`pkill`、8001 沒有 LISTEN。

## 使用者決定（2026-11-24）

- 和 PM 規格的 10 點差異：全部接受。
- 舊測試 0 行；新測試 `test_iter48.py` 384 行；無新 D 編號（下一個 D168）。
