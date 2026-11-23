# 第 47 輪｜System Analyst：設計

- 撰寫日期：2026-11-23（週一）；資料日 2026-11-23。
- 依據：`47/01-analyst.md`（F47-1～F47-12、R59～R61、D147～D155 全 A）、`47/02-pm.md`（畫面文字逐字定稿、驗收 23 條；PM 自行決定 12 點使用者全部同意）。
- 產出：本檔＋`47/03-design.diff`（734 行，可直接 `git apply`；在專案目錄 `git apply --check docs/iterations/47/03-design.diff` 已通過）。
- 做法：
  - `rsync -a --exclude .git --exclude .env --exclude _backups --exclude _archive --exclude logs` 把專案複製到 scratchpad `r47sa/proj`（**副本沒有 `.env`**），`git init` 並 commit 當基準；所有修改在副本完成，diff 由副本 `git diff` 產生（新檔用 `git add -N`）。
  - 匯出前先確認整條路徑只有 SELECT：`export.py` 的 39 個 `execute` 都是 `SELECT`／`WITH`、沒有 `commit`；`health.build_status`／`load_state`／`share_exists` 只查詢；`tradingcal.update_calendar`／`add_adhoc`／`remove_adhoc`、`health.write_run`／`finish_run` 不在匯出路徑。之後才在副本匯出：scratchpad 的小程式用專案 `twstock/config.py` 的 `_load_env` 把連線設定載入環境變數（沒有讀出、印出或複製內容），再匯入副本的 `twstock`、確認 `SITE_DATA_DIR` 在副本內，呼叫 `export_all()`（28.1 秒，只寫副本 `site/data`）。
  - 匯出前把副本的 `latest.json`、`screen.json` 與 `stocks/`、`etfp/` 2,367 檔的 sha1 存到 `r47sa/before/` 當比對基準。
  - 副本跑 `tests/test_iter01～47` 共 47 個檔，**全部通過**。
  - 畫面：副本目錄背景起 `python3 -u -m twstock serve --port 8001 --no-browser`，內建瀏覽器開 `http://127.0.0.1:8001`（確認載入的是新 `?v=`）。
- 守則：沒有讀、印、複製 `.env`；資料庫只有匯出的 SELECT；沒有外部請求、沒有 `collect`、沒有用 8000、沒有執行 `_archive/`；專案目錄只新增本檔與 `03-design.diff`。

---

## 一、改了哪些檔（`git diff --numstat`）

| 檔案 | 加／減 | 內容 |
|---|---|---|
| `twstock/export.py` | 8／0 | 新純函式 `nx_latest`（`notice_export` 之後）；`latest["etfs"]["ix"]` 之後加頂層 `nx`（空的不輸出） |
| `site/stock.js` | 4／2 | 新 `nxTag`（`nxText` 之後）；頁頭 `.tags` 呼叫一次；法人卡「法人5日」第 4 欄 `自營 ${yi(s?.d5)}` |
| `site/app.js` | 39／6 | 指數卡 1 行（F47-2）；夜盤 2 行（F47-4）；`renderWatch` 接線 5 行；新 `etfWatchPerf`、`nxKind`、`watchNx`；`holdEdit` 2 行；`watchToday` 2 行 |
| `site/help.js` | 2／1 | `adj` 改字；`etf` 組加 `tr`（不帶連結） |
| `site/app.css` | 1／0 | 檔尾 1 行：`.w-nx` 卡間距、列高、「試算 →」藍字不斷行；`a.pill.pill-nx` 藍框藍字 |
| `site/index.html` | 4／4 | `app.css`、`app.js`、`stock.js`、`help.js` 的 `?v=` |
| `tests/test_iter45.py` | 3／3 | 使用者已同意的 `:30`、`:49`、`:122`（見第四節） |
| `tests/test_iter47.py`（新） | 461／0 | 17 個測試、29 個反證 |
| `README.md` | 2／0 | 測試指令一行、第 47 輪說明一段 |
| `docs/iterations/README.md` | 1／0 | 第 47 輪一行 |

- 程式合計 58 行加、13 行減（PM 估約 80 行）；新測試 461 行（PM 估約 180 行；上限約 580 行）。
- `index.html` 的 `?v=`（和 `shasum` 前 8 碼相同）：

  | 檔案 | `?v=` |
  |---|---|
  | `app.css` | **07335b75**（原 7f4315c2） |
  | `app.js` | **9b18c12f**（原 14621fbf） |
  | `stock.js` | **7e6c6a13**（原 10ba5306） |
  | `tools.js` | 64e7360f（不變） |
  | `help.js` | **a5a5a7e8**（原 55e93876） |

## 二、程式設計

### 2-1 `twstock/export.py`（F47-1a）

```python
def nx_latest(*parts) -> dict:
    return {c: [v[0]["d"], v[0]["t"], v[0]["c"]] for c, v in sorted(x for p in parts for x in p.items()) if v}
```

- `parts` = `notice_export` 回傳的 `(nx_stock, nx_etf)`；`notice_export` 已依（代號、除權息日）排序、只留 `d > 資料日` 且 `last_seen` 是該市場最新的列，所以每檔取 `v[0]` 就是下一次。`c` 沿用 `_num` 的值（`4`、`0.624652`、`0`、`None`），不另外四捨五入。
- `export_all`：`latest["etfs"]["ix"] = …` 那個 `if` 之後、`alerts.w` 之前：
  ```python
      if nx := nx_latest(nx_stock, nx_etf):
          latest["nx"] = nx
  ```
  空的時候不輸出鍵（舊 `latest.json` 結構不變）。`nx` 是 `latest` 最後一個鍵。
- `notice_export`、`etf_export`（雜湊仍 `711fa2b7790c`）、股票 `**({"nx": …})`、ETF `E["nx"] = …`、`sh_stock`／`sh_etf` 次數都不動。

### 2-2 `site/stock.js`（F47-1b、F47-3）

- `nxTag(nx, code, etf)`：`nx` 有資料時輸出 `<a class="pill pill-nx" href="#/tools/dv?c=${code}" title="${esc(nxText(nx[0], etf))}">即將${nxKind(nx[0].t)} ${md(nx[0].d)}</a>`，否則空字串（頁頭 HTML 和改前逐字相同）。沒有 `data-gk`，`.tags` 的點擊監聽不處理它，照一般連結到除權息試算。
- 頁頭：`(data.alerts || []).map(…).join('')}` 後面直接接 `${nxTag(data.nx, code, E)}`，在處置／注意之後、「上市／上櫃」之前；只用個股 JSON 已有的 `data.nx`，不依賴匯出。
- 法人卡：`['法人5日', yi(s?.n5), cls(s?.n5), `自營 ${yi(s?.d5)}`]`；ETF 仍是 `inCards = []`。`chipSec('法人買賣超', …, inCards,` 字面不動。
- `nxText` 不改（`test_iter40` 鎖住），類型字另由 `app.js` 的 `nxKind` 提供（兩個檔共用，規則同 `nxText`）。

### 2-3 `site/app.js`

- **F47-2 指數卡**：`${x.s.length >= 60 ? '近 60 個交易日' : `自 ${md(x.from)} 起`}` → 一律 `自 ${md(x.from)} 起`；`（N 個交易日）` 仍只在不足 60 點時輸出；`${full && x.s.length >= 2 ?` 字面保留。
- **F47-4 夜盤**：`from` 下一行 `const to = from ? new Date(Date.parse(from + 'T00:00:00Z') + 864e5).toISOString().slice(0, 10) : N.date;`，結束時間改 `${md(to)} 05:00`。UTC 加一天，不受瀏覽器時區影響；`old` 判斷不變（R61）。
- **F47-6 自選 ETF 表現**：
  - `renderWatch` 在 `HV` 下一行：`const pf = Object.values(R).some(r => r.r20 != null || r.r60 != null || r.ry != null || r.rw != null), ep = pf && wc === 'perf';`（判斷和 ETF 列表 `hasPf` 相同，鍵直接寫出來，見第四節差異 1）。
  - 股票＋ETF：`ep` 時 ETF 表用 `etfWatchPerf(etfs, App.latest.etfs.ix)`，ETF 小標不輸出「當日行情；…」；資金、基本面照舊 `etfWatchTable`，持股照舊持股表。
  - 只有 ETF：欄組 `[['flow', '行情'], ...pf ? [['perf', '表現']] : [], ['hold', '持股']]`，選中 `HV ? 'hold' : ep ? 'perf' : 'flow'`；`ep` 時標題右側只寫「存在這個瀏覽器裡，換裝置不會同步」。不載入 `screen.json`，欄組只記在 `App.watchCols`。
  - `etfWatchPerf(list, ix)`（`etfWatchTable` 之後；`etfWatchTable` 一字不改）：上方 `tbl-cap` 一行、`EPF_COLS` 表頭、名稱欄同 `etfWatchTable`（含 `wCtl`、`holdTag`、`data-etf`）、收盤 `無成交`／`pfmt`、數字欄缺值 `--`、下方 `h-note`，文字和 PM 二之一第 7 節逐字相同。
- **F47-1c 自選頁卡**：
  - `renderWatch` 在 ETF 卡之後、`w-ev` 卡之前加 `${App.latest.nx ? watchNx() : ''}`（沒有 `nx` 時完全不呼叫新函式）。
  - `nxKind(t)`：`息`→`除息`、`權`→`除權`、其餘→`除權息`。
  - `watchNx()`：自選中認得的股票＋ETF 且在 `L.nx` 裡的代號，依自選順序再依除權息日穩定排序；沒有就回空字串（**不呼叫 `holdLoad`**）。有才 `holdLoad()` 取持股。每列 `<div class="al-row">`：名稱連結、`MM/DD 除息`、第 2 段（現金 > 0：股票「現金股利」、ETF「配息」＋`dfmt(x, 8)`；`null`：「金額待公告」；`0`：不輸出）、第 3 段估計可領、「試算 →」（只帶代號）。卡頭、卡尾文字照 PM。
  - 估計可領（R60）：`q = x > 0 && H[c] ? tlBig(String(x), 8) : null`；有 `q` 時 `fmt(Number(BigInt(H[c][0]) * q / 10n ** 8n))`。BigInt 除法向下取整 = 元以下捨去；超過 8 位小數 `tlBig` 回 `null` → 不顯示。`dfmt`（`stock.js`）、`tlBig`（`tools.js`）都在執行時才取，和既有持股用 `tlSell` 的做法相同。
  - `holdEdit` 最後 2 行：`const nx = sec.querySelector('.w-nx'); if (nx) nx.outerHTML = watchNx();`——在持股欄組改股數後估計立即更新（PM 二之二允許；`test_iter42` 的假 `sec` 對 `.w-nx` 回 `null`，舊測試照舊通過）。
- **F47-1d 今日卡**：`const x = L.nx ? W.filter(c => L.nx[c]).length : 0;`，`ev` 陣列加第 3 段 `x && \`即將除權息 ${x} 檔\``（`W` 是全部認得的自選，不只前 5 檔）。

### 2-4 `site/help.js`、`site/app.css`

- `adj` 定義、`tr` 一列和 PM 二之一第 8 節逐字相同；`tr` 放在 `etf` 組 `issuer` 之後、不帶連結（連結仍 24 個）。
- `app.css` 檔尾一行：`.card.w-nx{margin-top:12px}.w-nx .sec-h{margin-bottom:4px}.w-nx .al-row{line-height:1.7}.w-nx a.small{color:var(--blue);white-space:nowrap}a.pill.pill-nx{border-color:var(--blue);color:var(--blue)}`（只用既有變數）。

## 三、測試設計（`tests/test_iter47.py`，不連網、不連資料庫）

| 測試 | 內容 | 對應驗收 |
|---|---|---|
| `test_nx`（`check_nx`） | 自造 7 列預告經 `notice_export` → `nx_latest`：同檔兩筆只放近的、資料日當天與 `last_seen` 舊的不出現、`null`／`0`／整數 `4`（JSON 是 `4` 不是 `4.0`）、鍵依代號排序、全空與空陣列 → `{}` | 2 |
| `test_wiring` | `nx_latest` 位置、呼叫 1 次、`nx` 在 `etfs.ix` 之後／`alerts.w` 之前／寫檔之前；`etf_export` 雜湊、個股與 ETF 的 `nx` 行各 1 次 | 3 |
| `test_site_data` | 讀實際 `site/data`（沒有 `nx` 時印「尚未用第 47 輪匯出，略過」）：格式、日期 > 資料日、和個股 JSON `nx[0]` 相同、個股 JSON 有 `nx` 的檔數 = `nx` 檔數；資料日 2026-11-23 時 37 檔與 5 個例子 | 1 |
| `test_tag` | node 跑 `nxTag`：1437、00953B（ETF、`null`）、2345（權、現增）、權息、`undefined`／`[]` 空字串、多筆只看第一筆；沒有 `data-gk`；位置在處置之後、上市之前 | 4 |
| `test_watch` | node 跑 `renderWatch`（`test_iter32` 的函式清單＋持股函式＋`tools.js`＋`dfmt`）：驗收 7 的自選 → 卡頭卡尾逐字、3 列順序 6523、1437、00953B、6523 整列逐字；四個欄組都在 ETF 表之後、`w-ev` 之前；驗收 5 全部 13 個例子（含 0.29 → 29、0.57 → 57、9 位小數不估、`null`、`0`、沒有 `nx` 的持股）；1437 改 1,000 股 → 624；試算連結只帶代號；沒有 `nx` 與 `nx` 不含自選時輸出相同；表現表上方一行、表頭、0050／00679B 列、說明逐字、沒有成交額欄、資金／基本面 ETF 表 = `etfWatchTable`；只有 ETF：欄組、標題、無成交、缺值 `--`、✕ 3 個、不載 `screen.json`、不寫 localStorage；舊 `latest.json`（沒有含息欄）欄組只有行情、持股 | 5～8、13、14 |
| `test_storage` | `renderWatch` 只有 `localStore('rspan'`；`watchNx` 不直接用 `localStore`、先判斷有沒有列才 `holdLoad()` | 8 |
| `test_edit` | 用 `test_iter42` 的 `EDIT` 假物件（加 `.w-nx`）：持股欄組填 6523 1,000 股 → 卡片立即顯示 4,000 元；清空 → 不顯示 | 二之二 |
| `test_today` | 驗收 7 的自選 → `處置／注意 1 檔、即將除權息 3 檔 →`；只有 1437 → `即將除權息 1 檔 →`；第 6 檔之後才有 `nx` 也算；沒有 `nx` 不輸出 | 9 |
| `test_index` | 60 點加權 `自 08/25 起 -18.5%`、櫃買 `-30.4%`；30 點 `（30 個交易日）`；`full = false` 不顯示；`近 60 個交易日` 不在 `app.js` | 10 |
| `test_chip` | 卡片字面；`yi` 506.77／54.21／0.01／`null` → `+507億`、`+54.2億`、`0億`、`--`；ETF `inCards = []` | 11 |
| `test_night` | 週五夜盤 → 11/21、週四 → 11/20、跨月 12/01、跨年 01/01、連假前 02/05 → 02/06、沒有 `from`、最新夜盤；「前一夜盤」判斷 | 12 |
| `test_help` | `test_iter45.check_data`／`check_page`（已改成 42 個）；`#/help/tr` 標示並捲動；`etf` 組 `units、issuer、tr`、`tr` 沒有連結；`ETF 個股頁用原始價` 不再出現 | 15 |
| `test_words`、`test_node14` | 新函式、新增行、`tr`／`adj`、README 第 47 輪不含禁用詞（`test_iter42`、`test_iter45` 的詞＋任務清單）；新程式沒有 `.at(`、`replaceAll`、`||=`、`&&=`、`??=` | 16、17 |
| `test_version_and_docs`、`test_pm_text` | 5 個 `?v=`、`tools.js` 不變、外部資源仍 2 個；README 指令與段落、docs 索引；卡尾等字串和 PM 相同 | 20 |
| `test_contrast` | 29 個反證，每個都要讓對應檢查失敗 | 反證 |

反證：匯出放最後一筆、匯出空陣列也放、空的也輸出 `nx`、標籤加 `data-gk`、標籤用最後一筆、標籤放在上市之後、估計用浮點（`Math.floor(股數 × c)`）、估計四捨五入、9 位小數也估計、不依日期排序、只列股票、現金 0 也寫金額待公告、ETF 也寫現金股利、試算連結帶股數、卡片放在 ETF 表之前、`renderWatch` 直接 `localStore('hold'`、沒有 `nx` 也先讀持股、改持股不更新估計、今日卡只算前 5 檔、表現仍用行情表、舊資料也有表現、表現仍寫當日行情、表現缺值顯示 0、指數卡改回近 60 個交易日、夜盤結束日用歸屬日、法人卡沒有自營、名詞 `tr` 加連結、`adj` 改回原文、用詞。

- 驗收 3 的逐位元組比對、22、23 由 PG／QA 實跑；SA 在副本已先做過，結果見第五節。

## 四、和 PM 規格的差異（SA 決定，請使用者確認）

1. **舊測試只改 3 行（`test_iter45:30`、`:49`、`:122`），已同意的另外 7 行不改**：`renderWatch` 的 `pf` 判斷把 `EPF_COLS` 的四個鍵直接寫出來（`r.r20 != null || r.r60 != null || r.ry != null || r.rw != null`），`etfWatchPerf` 與 `watchNx` 只在有含息欄／有 `nx` 時才呼叫；舊測試的資料都沒有這些欄，走原本路徑，所以 `test_iter32:95`、`test_iter42:343` 與 5 個函式清單都照舊通過。代價是鍵寫了兩處；`test_iter47` 的「舊資料也有表現」等反證會擋下判斷寫錯。
   - `test_iter45:30` 的改法（一行）：仍解析 `45/02-pm.md` 二之一，再用 `re.sub` 把 `| adj |` 那列換成本輪 `47/02-pm.md` 的 `adj` 列、在 `| issuer |` 之後加 `tr` 列。`:49`、`:122` 是 41 → 42。
2. **自選 ETF 表現表的說明字串分兩段相接**（`…不含手續費與稅' + '；「--」= …`）：畫面文字和 PM 逐字相同，但 `test_iter46` 的反證要 `不含手續費與稅；` 在 `app.js` 只出現一次（`ETF_PF_NOTE`）。同理，名稱欄用區域函式 `nm(c, r)`（`test_iter25:88`、`test_iter42:507` 數 `<td class="nm">${wCtl(c)}` 只有 1 個），無成交儲存格用反引號（`test_iter46` 數單引號字面只有 1 個）。
3. **0050 收盤顯示 `87`，不是驗收 13 寫的 `87.00`**：收盤沿用 `pfmt`（最多兩位、不補 0），和 ETF 列表「表現」、自選行情表相同。
4. **持股欄組改股數後，即將除權息卡的估計立即更新**（`holdEdit` 加 2 行），不用等重繪；PM 二之二允許，未動到被舊測試鎖住的字面。
5. **類型字用新的 `nxKind`**（`app.js`），頁頭標籤與自選卡共用；`nxText` 不改（被 `test_iter40` 鎖住），兩者規則相同。頁頭標籤抽成 `stock.js` 的小函式 `nxTag`，方便單獨測試。
6. **`app.css` 加 1 行**：標籤藍框藍字（和「持股 →」同色，表示可點）、卡片間距同 `w-ev`、「試算 →」藍字不斷行。
7. **`README.md` 第 45 輪那段的「8 組 41 個名詞」不改**（歷史敘述）；第 47 輪新段寫「8 組 42 個名詞」。

## 五、核對結果（副本匯出，資料日 2026-11-23）

- **`nx` 37 檔**（股票 19、ETF 18），鍵依代號排序；`1437 ["2026-12-03","息",0.624652]`、`6523 ["2026-11-26","息",4]`、`00901 ["2026-11-24","息",7]`、`00953B ["2026-12-03","息",null]`、`2345 ["2026-12-04","權",0]`、`4414 [...,0.00915]`、`3701 [...,0.199892]`、`00930 [...,0.75]`、`00958B [...,0.042]`。每檔都和個股 JSON 的 `nx[0]` 相同；個股 JSON 有 `nx` 的檔數也是 37。
- **逐位元組**：`stocks/`、`etfp/` 2,367 檔 sha1 和匯出前 0 檔不同；`screen.json` 相同；`latest.json` 拿掉 `nx` 後只有 `status.exported_at` 不同；大小 +1,245 bytes（≤ 3 KB）。
- **估計可領（逐元）**：6523 1,000 股 → 4,000；1437 2,500 → 1,561、1,000 → 624；4414 1,000 → 9；00901 1,000 → 7,000；00930 1,500 → 1,125；00958B 333 → 13；3701 1,234 → 246；0.29 × 100 → **29**、0.57 × 100 → **57**（浮點 `Math.floor` 會是 28、56，反證已擋下）；9 位小數不顯示；00953B（`null`）、2345（`0`）不顯示。
- **指數卡**：加權 `自 08/25 起 -18.5%`、櫃買 `自 08/25 起 -30.4%`（數字不變，只改寫法）。
- **法人卡**（2330 籌碼）：`法人5日 -684億　自營 +507億｜外資5日 -1,296億｜投信5日 +105億`，−1,296 ＋ 105 ＋ 507 = −684。
- **夜盤**：`前一夜盤（11/20 15:00～11/21 05:00）　收 33,919 -1,881 (-5.25%)`。
- **自選 ETF 表現**：上方一行 `含息報酬為 11/23 收盤；加權指數同期：20 日 -20.05%、60 日 -17.76%、今年以來 +27.10%、52 週 +39.25%（價格指數，不含股息）`；0050 `87　-18.62%　-16.18%　+35.31%　+48.31%`；00679B `26.33　+2.32%　+3.03%　+0.83%　+0.13%`。
- **全部測試**：`tests/test_iter01～47` 47 個檔全部通過；`git diff --stat tests/` 只有新檔 `test_iter47.py` 與 `test_iter45.py` 3 行。

## 六、畫面檢查（副本 8001，內建瀏覽器）

暫時設自選 2330、2454、3105、1437、2881、6523、0050、00878、00679B、00953B，持股 6523 1,000 股、1437 2,500 股、0050 2,000 股。

| 頁面 | 1024 淺 | 375 淺 | 320 深 | 結果 |
|---|---|---|---|---|
| `#/today` 總覽 | ✓ | ✓ | ✓ | 提示行 `近期新訊號 2 檔、即將除權息 3 檔 →`；指數卡 `自 08/25 起` |
| `#/watch` 資金／表現／持股 | ✓ | ✓ | ✓ | 即將除權息卡 3 列（達爾膚估計 4,000、勤益控 1,561、群益優選非投等債金額待公告），每段 `.nw` 不斷字、段與段之間換行；表現欄組 ETF 表換成含息表 |
| 只有 ETF 的自選（0050、00901、00679B） | | | ✓ | 欄組「行情｜表現｜持股」；00901 `11/24 除息　配息 7 元` |
| `#/stock/1437`、`00901`、`6523`、`00953B`、`2345`、`00878` | ✓ | ✓ | ✓ | 頁頭 `即將除息 12/03` 等標籤在「上市」之前、滑過看金額；2330 沒有標籤 |
| `#/stock/2330/chip` | ✓ | ✓ | ✓ | `自營 +507億` |
| `#/today/fut` | ✓ | ✓ | ✓ | `11/20 15:00～11/21 05:00` |
| `#/help/tr` | ✓ | ✓ | ✓ | 42 個名詞，「含息報酬」標示；`adj` 新文字 |

- 三種寬度 12 個路由／欄組都是 `scrollWidth = innerWidth`；主控台沒有錯誤。
- 只有 ETF 的自選測試時 `holdLoad` 依既有規則刪掉不在自選裡的持股（第 42 輪行為），所以之後 320 寬截圖沒有估計，屬預期。
- 結束：localStorage `{"tw.todayTab":"ov","tw.stockTab":"k"}`、視窗 desktop／淺色、`pkill -f "twstock serve --port 8001"`（exit 144），8001 沒有 LISTEN。

## 七、需要使用者決定的事項

- 無。舊測試只用了已同意 10 行中的 3 行，沒有需要再問的舊測試行；本輪沒有新增 D 編號（下一個仍從 D156 起）。第四節 7 點差異請使用者確認。

## 八、給 PG

1. 在專案目錄 `git apply docs/iterations/47/03-design.diff`（`--check` 已通過）。
2. 匯出前把 `site/data/latest.json`、`screen.json` 與 `stocks/`、`etfp/` 的 sha1 存到 scratchpad（驗收 3 的基準），同一晚不要先跑 `collect`。
3. 跑 `for f in tests/test_iter*.py; do python3 $f >/dev/null 2>&1 || echo FAIL $f; done`：47 個檔全過（匯出前 `test_iter47.test_site_data` 會印「尚未用第 47 輪匯出，略過」）。
4. 依 D150 執行 `python3 -m twstock export`（只讀資料庫、只寫 `site/data/`），再跑一次全部測試（資料日 2026-11-23 時 `test_site_data` 核對 37 檔與 5 個例子；之後的資料日只核對格式與一致性）。
5. 比對：`stocks/`、`etfp/`、`screen.json` 逐位元組不變；`latest.json` 拿掉 `nx` 後只有 `status.exported_at` 不同；大小增加約 1.2 KB。
6. 8001 冒煙：`#/today`、`#/watch`（資金／表現／持股，改持股看估計即時更新）、只有 ETF 的自選、`#/stock/1437`、`#/stock/00953B`、`#/stock/2330/chip`、`#/today/fut`、`#/help/tr`；結束時 localStorage 恢復、視窗 desktop、`pkill`、8001 沒有 LISTEN。

## 使用者決定（2026-11-23）

- 和 PM 的 7 點差異：全部接受。
- 新測試 `test_iter47.py` 461 行：接受。
- 舊測試實際只改 `test_iter45:30`、`:49`、`:122` 3 行（在已同意的 10 行內）；無新 D 編號（下一個 D156）。
