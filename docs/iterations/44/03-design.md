# 第 44 輪｜SA：設計

- 撰寫日期：2026-11-22（週日）
- 依據：
  - `44/01-analyst.md`：第一節建議修法；第二節舊測試逐行。
  - `44/02-pm.md`：F44-1～F44-7，驗收 23 條。
  - D119～D127 全部 A。
- 做法：
  - 把 `site/`、`tests/`、`twstock/`、`scripts/`、`docs/`、`README.md` 複製到 scratchpad `r44sa/`，**沒有複製 `.env`**。
  - 在副本用 `git init` 記下原狀，再套用本設計。
  - 跑 `tests/test_iter01～44` 全部 44 個檔。
  - 產生 `03-design.diff`（514 行），在專案上 `git apply --check` 通過。
- 守則：
  - 沒有讀 `.env`、沒有連資料庫、沒有外部請求、沒有 `export`／`collect`、沒有開伺服器。
  - 專案只新增本檔與 `03-design.diff`。
  - `02-pm.md` 末尾補記 D127 = A。

---

## 重點摘要

| 項目 | 結果 |
|---|---|
| 程式 | 11 行：`tools.js` ±3、`stock.js` ±3、`app.js` ±1、`app.css` +1、`notices.py` ±1、`tdcc.py` +2／−1 |
| `index.html` | 4 個 `?v=` |
| 文件 | `README.md` +2（功能說明一條、測試指令一行）、`docs/iterations/README.md` +1 |
| 舊測試 | **13 行**，和分析師第二節逐字相同（D120～D125）；`test_iter41:437` 雜湊 = `ff151c62306c`（和分析師副本值相同） |
| 新測試 | `tests/test_iter44.py` 242 行、10 個測試；反證 16 種（Python 5、JS／CSS 11） |
| 原型結果 | 44 個測試檔全部通過；把程式還原成原版時，新測試的 8 個檢查函式全部失敗 |
| 和 PM 的差異 | 無 |

---

## 一、程式（逐行；字面同 PM 二之一）

| 檔案:行 | 原 | 新 |
|---|---|---|
| `site/tools.js:106` | `dt: { mode: 'dt', dir: 'b', …` | `dt: { mode: 'g', dir: 'b', …` |
| `site/tools.js:293` | `…起沒有除權息紀錄，請依公司公告填寫` | `…起沒有除權息紀錄，請依${e ? '發行人' : '公司'}公告填寫` |
| `site/tools.js:301` | `…（最近一次），下次請依公司公告修改` | `…（最近一次），下次請依${e ? '發行人' : '公司'}公告修改` |
| `site/stock.js:256` | `` subs(`5日 ${fhd(5)}　20日 ${fhd(20)}（百分點）`, … `` | `` subs(`<span class="nw">5日 ${fhd(5)}</span>　<span class="nw">20日 ${fhd(20)}</span>（百分點）`, … `` |
| `site/stock.js:745` | `` const pp = a => `1週 ${w(a, 1, 2)}　4週 ${w(a, 4, 2)}（百分點）`; `` | `` const pp = a => `<span class="nw">1週 ${w(a, 1, 2)}</span>　<span class="nw">4週 ${w(a, 4, 2)}</span>（百分點）`; `` |
| `site/stock.js:748` | `` `1週 ${w(sh.n, 1, 0)}　4週 ${w(sh.n, 4, 0)}（人）<br>… `` | `` `<span class="nw">1週 ${w(sh.n, 1, 0)}</span>　<span class="nw">4週 ${w(sh.n, 4, 0)}</span>（人）<br>… `` |
| `site/app.js:1819` | `元（${holdP(V.u, V.t)}）` | `元（<b class="${cls(Number(V.u))}">${holdP(V.u, V.t)}</b>）` |
| `site/app.css` 檔尾（新第 379 行） | — | `.dv-nx{word-break:keep-all}.tl-lg+.muted.small{text-wrap:pretty}   /* 第 44 輪：375 寬不拆「預告」、複利座標說明不剩單字 */` |
| `twstock/collectors/notices.py:49` | `num = lambda k: clean_number(r[names[k]], Decimal)` | `num = lambda k: x if (x := clean_number(r[names[k]], Decimal)) is None or x.is_finite() else None   # QA40-04：NaN、Infinity 當作沒有值` |
| `twstock/collectors/tdcc.py:99` | 一行 `print(f"  🏦 集保股權分散 …")` | `bad = skipped and not rows` 一行＋`print(f"  {'⚠️' if bad else '🏦'} …" + ("，官方格式可能改變，請檢查" if bad else ""))` |

- **選擇器 `.tl-lg+.muted.small`**：
  - `tools.js` 中 `tl-lg"` 只出現 1 次，在 `tlCpGraph:185`。
  - 圖例 `</div>` 後面緊接 `<div class="muted small">第 0～${n} 年；…`。
  - 所以只命中複利座標說明（`test_css` 鎖定）。
- **`.dv-nx`**：只有 `stock.js` 的股利卡 `<div class="small dv-nx">` 一處。
- **`?v=`**：

  | 檔案 | 新值 |
  |---|---|
  | `app.css` | 351d68e6 |
  | `app.js` | 29a4de94 |
  | `stock.js` | c2c7d916 |
  | `tools.js` | 9066111f |

  - 這是原型的 sha1 前 8 碼。PG 原樣套用 diff，值就相同；不同表示套用有差異。

## 二、舊測試（13 行，D120～D125；其他舊測試 0 行）

| 檔名:行號 | 改法 |
|---|---|
| `test_iter38.py:183` | 前面加 `TL.dt.mode = 'dt'; ` |
| `test_iter42.py:380` | 正規式結尾 `元（(.*?)）` → `元（<b class="\w+">(.*?)</b>）` |
| `test_iter42.py:513` | `assert HTML.count("https://") == 2                       # 第 42 輪 tools.js 0 行改動；之後 tools.js 的版本由上面 ?v= 比對` |
| `test_iter29.py:195` | 原始碼字面加兩個 `<span class=\"nw\">…</span>` |
| `test_iter39.py:422` | `("的股利（最近一次），", "的股利，")` |
| `test_iter40.py:406` | 00958B 期望字串「公司」→「發行人」 |
| `test_iter41.py:437` | `"f206966d85e5"` → `"ff151c62306c"` |
| `test_iter43.py:415、416、418、419、420、421` | 每個 `1週 X`、`4週 Y` 包 `<span class=\"nw\">…</span>`（12 個字串、24 個 `span`） |

- `git diff --numstat tests/`：29、38、39、40、41 各 1／1，42 2／2，43 6／6，共 13 行。

## 三、新測試 `tests/test_iter44.py`（10 個）

| 測試 | 驗收 | 內容 |
|---|---|---|
| `test_dt_default` | 1～3 | 驗以下各點：<br>• `TL.dt.mode === 'g'`<br>• 表單「非當沖」為 `class="on"`，沒有 `data-g="dir"`<br>• 預設輸出含 `證交稅：股票 0.3%`，不含 `當沖需符合券商資格` 與 `0.15%`<br>• `mode: 'dt'` 時含 `現股當沖 0.15%（至 2027/12/31）` 與當沖提示<br>• ETF、債券 ETF 預設輸出和 `mode: 'g'` 相同 |
| `test_css` | 4、5 | `app.css` 那一行恰好出現 1 次；選擇器只命中複利座標說明；`dv-nx` 只有一處 |
| `test_sh_cards` | 6 | 用 `test_iter43.CARDS` 的 3 組資料跑 `shCards`，每組 8 個 `.nw`，每個 `span` 內容只能是「1週／4週 ＋數字或 --」（單位不在裡面）；去標籤後和舊字串相同 |
| `test_fh_card` | 7 | 外資持股卡新字面恰好 1 次；去標籤後等於舊字面 |
| `test_hold_line` | 8 | 未實現損益 +5,000、−5,000、0 → 報酬率 `<b class>` 為 `up`／`dn`／`flat`，和未實現損益相同；數字 `+5.00%`／`-5.00%` |
| `test_nonfinite` | 9 | 先跑 `test_iter40.check_parse`（正常資料不變）。假資料：<br>• 上市 2 列：`NaN`、`nan`、`Infinity`、`-Infinity`、`sNaN`<br>• 上櫃 2 列：`-Infinity`、`inf`、`-inf`，另一列正常<br>預期：現金 `None`、配股 0、認購率 0、認購價 `None`；正常列照常 |
| `test_etf_wording` | 10 | `tlDvLoad` 沿用最近一次、沒有紀錄兩種情況 × ETF／股票，第一句逐字比對 |
| `test_tdcc_all_skipped` | 11、12 | 先跑 `test_iter43.check_write`（🏦 三種情況不變）。另測只有 2421（合計不符）與 01001T 的檔：<br>• 不連資料庫<br>• 回傳 `{on, d, s: 0, e: 0}`<br>• 輸出逐字為 ⚠️ 那一行 |
| `test_versions_docs_words` | 15、17 | 驗以下各點：<br>• 4 個 `?v=` 和內容一致<br>• README 有測試指令與「第 44 輪」<br>• `docs/iterations/README.md` 有第 44 輪<br>• 新文字不含 `test_iter42.ADVICE` 的禁用字 |
| `test_contrast` | — | 16 種改壞方式全部要被擋下（第四節） |

- 驗收 13、14、16 由 PG／QA 用 `git diff`、全部測試、`git status site/data` 確認；18～23（畫面）由 QA 做。

## 四、反證（`test_contrast`）

| # | 改壞方式 | 由誰擋下 |
|---|---|---|
| 1 | `notices` 不過濾非有限值 | `check_nonfinite` |
| 2 | 只濾 NaN、不濾 Infinity | `check_nonfinite` |
| 3 | 全部略過仍印 🏦（`bad = False`） | `check_tdcc` |
| 4 | 部分略過也印 ⚠️（`bad = skipped`） | `check_tdcc`（`test_iter43.check_write` 的部分略過情況） |
| 5 | 拿掉提示字 | `check_tdcc` |
| 6 | 預設仍是當沖 | `check_dt` |
| 7、8 | 293、301 任一句仍寫「公司」 | `check_dv` |
| 9 | 發行人與公司對調 | `check_dv` |
| 10、11 | 比例卡、人數卡拿掉 `.nw` | `check_sh` |
| 12 | `.nw` 連「（百分點）」一起包 | `check_sh` |
| 13 | 外資持股卡拿掉 `.nw` | `check_fh` |
| 14 | 報酬率不上色 | `check_hold` |
| 15 | 報酬率顏色改看今日損益 | `check_hold` |
| 16 | 拿掉 `app.css` 那一行 | `check_css` |

- 另外，在副本把 `site/`、`twstock/` 整個還原成原版（`git stash`）再呼叫 8 個檢查函式，**全部回報失敗**。

## 五、檔案與行數

| 檔案 | ＋／− |
|---|---|
| `site/tools.js` | +3／−3 |
| `site/stock.js` | +3／−3 |
| `site/app.js` | +1／−1 |
| `site/app.css` | +1 |
| `site/index.html` | +4／−4 |
| `twstock/collectors/notices.py` | +1／−1 |
| `twstock/collectors/tdcc.py` | +2／−1 |
| `README.md` | +2 |
| `docs/iterations/README.md` | +1 |
| `tests/test_iter29、38、39、40、41.py` | 各 +1／−1 |
| `tests/test_iter42.py` | +2／−2 |
| `tests/test_iter43.py` | +6／−6 |
| `tests/test_iter44.py` | +242（新增） |

## 六、和 PM 的差異

- 無。
- `test_iter44` 的上櫃假資料多涵蓋 `inf`、`-inf`。
- 反證多了「只濾 NaN」「`.nw` 連單位一起包」「顏色看今日損益」三種，都在 PM 範圍內。

## 七、風險

| 風險 | 處理 |
|---|---|
| 收集程式下一次排程就生效（D127 = A） | 正常資料輸出不變：`test_iter40`、`test_iter43` 全過，`check_tdcc` 也重跑了 🏦 三種情況 |
| `test_iter44` 匯入 `test_iter28／34／40～43` | 這些都是既有的匯入（`test_iter43` 也匯入 28、40），沒有新增依賴 |
| 沒有 node 時 JS 檢查略過 | 比照既有測試；`check_css`、`check_fh` 是純字串，沒有 node 時也會跑反證 |
| `text-wrap:pretty` 舊版 Safari 不支援（Q44-1） | 不支援時維持現狀；QA 只能在內建瀏覽器（Chromium）驗 |

## 八、PG 套用步驟

1. `git apply --check docs/iterations/44/03-design.diff`，通過後 `git apply`，不手動修改。
2. `shasum` 4 個前端檔，確認和第一節的 `?v=` 相同。
3. `git diff --numstat` 對照第五節。
4. 跑 `tests/test_iter01～44` 全部 44 個檔。
5. 8001 冒煙（從專案目錄背景啟動，測完 `pkill`，確認 `lsof` 沒有輸出）：
   - `#/tools` 預設非當沖。
   - `#/tools/dv?c=0050` 的提示寫「發行人」。
   - 今日頁小卡（有持股時）報酬率有顏色。
   - 主控台沒有錯誤。
6. 不 `export`、不 `collect`、不連資料庫；不 commit。

## 九、需要使用者決定的事項

- 無（已 grep `docs/iterations`，目前最大 D127）。
