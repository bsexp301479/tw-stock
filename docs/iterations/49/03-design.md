# 第 49 輪｜System Analyst：設計

- 撰寫日期：2026-11-25（週三）；資料日 2026-11-25（`latest.json` `date` = `flow_date` = `screen.json` `d` = 2026-11-25）。
- 依據：`49/01-analyst.md`（F47-9～F47-12、R71、R72、D169～D175 全 A）、`49/02-pm.md`（二之一逐字規格、驗收 29 條；PM 自行決定 11 點使用者全部同意，含手機「圖」模式也收 0 億列）。
- 產出：本檔＋`49/03-design.diff`（544 行，可直接 `git apply`；在專案根目錄 `git apply --check docs/iterations/49/03-design.diff` 已通過）。
- 做法：
  - `rsync -a --exclude .git --exclude .env --exclude _backups --exclude _archive --exclude logs` 把專案（含 `site/data`）複製到 scratchpad `sa49/`（**副本沒有 `.env`**），`git init` 並 commit 當基準；所有修改在副本完成，diff 由副本 `git diff` 產生（新檔用 `git add -N`），路徑為 `a/`、`b/` 前綴、相對專案根目錄。
  - 改前先跑 `tests/test_iter01～48` 全部通過；改後跑 `test_iter01～49` 共 **49 個檔全部通過**。
  - 舊測試只改使用者同意的 8 行；F47-10 表尾、F47-12 `screenRow` 實作後再跑一次全部舊測試，**沒有其他舊測試要改**。
  - 畫面：副本目錄背景起 `python3 -u -m twstock serve --port 8001 --no-browser`，內建瀏覽器開 `http://127.0.0.1:8001`（確認載入新 `?v=`）。量完 localStorage 設回開始時的 `{"tw.todayTab":"ov","tw.stockTab":"k"}`、視窗設回 desktop preset、`pkill` 關掉 8001，`lsof -i :8001 -i :8002` 沒有輸出。
- 守則：沒有讀、印、複製 `.env`；沒有連資料庫、沒有 `export`／`collect`、沒有外部請求、沒有用 8000、沒有執行 `_archive/`；專案目錄只新增本檔與 `03-design.diff`。

---

## 一、改了哪些檔（`git diff --numstat`）

| 檔案 | 加／減 | 內容 |
|---|---|---|
| `site/tools.js` | 1／1 | F47-9：`tlDvLoad` 最後一個 `h.push` 的三處 `md(from)` → `from.replace(/-/g, '/')` |
| `site/app.js` | 14／2 | F47-10：成分股卡加表尾 `#gZ`、`#gZ` 點擊、`groupRows` 列標記、`showGroup` 呼叫新函式 `gzFoot`；F47-12：`screenRow` 2 行、`SCR_COLS.nx` 1 行、`SCREEN_CONDS` `nxd` 1 行 |
| `site/app.css` | 3／1 | F47-11：`.s-code` 加 `display:inline-block`、`@media (max-width:374px)` 1 行；F47-10：檔尾 1 行 |
| `site/index.html` | 3／3 | `app.css`、`app.js`、`tools.js` 的 `?v=` |
| `tests/test_iter49.py`（新） | 305／0 | 9 個測試、17 個反證 |
| `tests/test_iter39.py`、`40`、`41`、`47`、`48` | 8／8 | 使用者同意的 8 行（第五節） |
| `README.md` | 2／0 | 測試指令一行、第 49 輪一段 |
| `docs/iterations/README.md` | 1／0 | 第 49 輪一行（PG／QA 之後補完） |

- 程式合計 **21 行加、7 行減**（`tools.js` 1、`app.js` 14、`app.css` 3、`index.html` 3；PM 估約 16 行＋`?v=` 3 行，多出的是 `gzFoot` 函式的宣告與註解 3 行）。新測試 305 行（PM 估 80～100 行；多在反證與實際資料核對；上限約 580 行）。

## 二、程式設計

### 2-1 F47-9 除權息試算起日（`site/tools.js:305`）

```js
h.push(k ? `近一年現金股利 = ${from.replace(/-/g, '/')} 以後 ${k} 次合計${miss ? '；部分缺值，請自行確認' : ''}` : miss ? `${from.replace(/-/g, '/')} 以後的現金股利官方表沒有分項，請自行確認` : `${from.replace(/-/g, '/')} 以後沒有現金股利`);
```

- `from` 仍是 `資料日 − 365 × 864e5` 的 `YYYY-MM-DD`，`v.d > from` 不變（起日當天不計入）；只有顯示改成 `YYYY/MM/DD`。函式其他字面不變（把三處換回 `${md(from)}` 後 sha1 前 12 碼 = 改前 `55ab42fe3d80`）。

### 2-2 F47-10 泡泡圖成分股表（`site/app.js`、`site/app.css`）

- `renderBubble` 成分股卡（`:757`）：`</table></div>` 之後、卡片 `</div>` 之前加 `<div class="muted small g-z" id="gZ"></div>`（捲動框 `.panel-list` 之外、同一張卡內）。
- `renderBubble` 圖模式（`if (list) {…return;}` 之後、`drawBubble` 之前）加 1 行：

  ```js
  $('#gZ').addEventListener('click', e => { if (e.target.closest('[data-gz]')) { App.gzAll = !App.gzAll; gzFoot(); } });   // 第 49 輪 F47-10
  ```
  監聽掛在 `#gZ`（每次 `renderBubble` 重建），不掛 `#view`（見第七節差異 2）。
- `groupRows(g)`：`<tr data-code="${c}"${yi(s.n1) === '0億' && yi(s.n5) === '0億' ? ' class="z"' : ''}>`；順序、欄位不變（R72：以畫面字為準，`null` → `--` 不算）。
- `showGroup(g)`：畫表後呼叫 `gzFoot()`。
- 新函式（放在 `showGroup` 之後）：

  ```js
  function gzFoot() {
    const t = $('#gTable'), z = t.querySelectorAll('tr.z').length, n = t.querySelectorAll('tbody tr').length;
    t.classList.toggle('gz', !App.gzAll);
    $('#gZ').innerHTML = z ? `${App.gzAll ? '含 ' : z < n ? '另有 ' : ''}${z} 檔法人 1 日、5 日都是 0億　<button type="button" class="chip" data-gz>${App.gzAll ? '收合' : '顯示'}</button>` : '';
  }
  ```
  - 四種情況照 PM 二之一表格逐字（`z = 0` 空字串；未展開 `z < n`「另有」；未展開 `z = n` 沒有「另有」；已展開「含 … 收合」）。
  - 展開／收合只換 `#gTable` 的 class `gz` 與表尾，不重畫列、不重畫泡泡圖、不捲動；`App.gzAll` 初值 `undefined` = 未展開，只在這次瀏覽記住，不寫 localStorage。
- `app.css` 檔尾：`#gTable.gz tr.z{display:none}.g-z{margin-top:6px}   /* 第 49 輪 F47-10 */`。手機清單（`bubbleList`）的表沒有 `#gTable`、沒有 `gz`，只多 ` class="z"`，畫面不變；`:351` D30-08 的 `nth-child(n+11)` 不受 class 影響。

### 2-3 F47-11 窄螢幕個股頁頭（`site/app.css`）

- `:150` → `.s-code{color:var(--text2);margin-left:6px;display:inline-block}`。
- `:305` 那個 `@media (max-width:720px){…}` 區塊的 `}` 之後新增 `@media (max-width:374px){.s-name{font-size:17px}}   /* 第 49 輪 F47-11 */`。`stock.js` 0 行改動。

### 2-4 F47-12 選股「{v} 天內將除息」（`site/app.js`）

- `screenRow`（`dva` 區塊之後）：

  ```js
  const n = S && App.latest?.nx?.[code];   // 第 49 輪 F47-12（R71）：…
  if (n && (n[1] === '息' || n[1] === '權息')) { x.nxd = n[0]; x.nxt = n[1]; x.nxa = Math.round((Date.parse(n[0]) - Date.parse(S.d)) / 864e5); }
  ```
  `S` 為 `null`、`App.latest` 不存在（`test_iter35.py:114` 的假 `App`）、`nx` 沒有該檔時不加欄、不拋錯。之後的 `for (const n of [1, 5])` 是自己的區塊作用域，不衝突（舊測試全過）。
- `SCR_COLS`（`dvg` 之後）：`nx: ['即將除息', x => x.nxa, (v, x) => md(x.nxd) + '<span class="sub2">' + v + ' 天後' + (x.nxt === '權息' ? '（權息）' : '') + '</span>', 1],`
- `SCREEN_CONDS`（`dvr` 之後、`pb` 之前）：PM 二之一 `nxd` 一行逐字，行尾加註解 `// 第 49 輪 F47-12（R71）`。
- `SCREEN_GROUPS`、`SCREEN_PRESETS`、`scrParse`、`scrQuery` 不改。

### 2-5 `index.html`、README

| 檔案 | `?v=`（= `shasum` 前 8 碼） |
|---|---|
| `app.css` | **ce1417aa**（原 1ae7bbed） |
| `app.js` | **54952a23**（原 d273c8c5） |
| `tools.js` | **0a050889**（原 64e7360f） |
| `stock.js` | 28633954（不變） |
| `help.js` | a5a5a7e8（不變） |
| `compare.js` | 1c11197d（不變） |

- `https://` 仍 2 個。
- README：測試指令表加 `python3 tests/test_iter49.py`；「多檔報酬率比較（第 48 輪）」段之後新增「第 49 輪小項」一段（不改既有段落、不含「第 23 輪」字樣）。`docs/iterations/README.md` 第 48 輪之後加一行（PG／QA 結果由後續角色補）。
- PG 套用後若 `app.js`、`app.css`、`tools.js` 和本 diff 有任何一字不同，`?v=` 與 `test_iter41:437` 雜湊都要重算。

## 三、測試設計（`tests/test_iter49.py`，不連網、不連資料庫）

沿用 `test_iter35._grab`、`test_iter34._node`／`HELPERS`；檢查函式都接受原始碼字串，供反證重跑。用詞清單 = `test_iter47.ADVICE` ∪ 從 `test_iter23.py` 檔案讀出的清單（本檔不重寫用詞字面）。

| 測試 | 內容 | 對應驗收 |
|---|---|---|
| `test_dv` | 整個 `tools.js` 跑 `tlDvLoad`：資料日 2026-11-20 四個分支（有現金股利、部分缺值、全部沒有分項、只有「權」）逐字＋`y1`（起日當天那筆 9 元不計入，`y1 = 5`）；資料日 2027-01-05 → `2026/01/05`、2028-03-01 → `2027/03/02`、2026-11-25 → `2025/11/25`；字串不含 `YYYY-MM-DD` 與沒有年份的 `MM/DD 以後`；PM 文字在 `02-pm.md`；`tlDvLoad` 不含 `md(from)`、`FROM` 3 次、`v.d > from`；換回後雜湊 = 改前 | 1、2、3 |
| `test_bubble` | `check_rows`：6 檔假資料（`-0.04/0.04` 算、`0/0.05` 不算、`null/0`、`0/null` 不算、`1/2`、`0/0` 算），輸出列順序 = 5 日由大到小、只有 A、F 有 `class="z"`、其他列沒有 class；`check_foot`：假 DOM 跑 `showGroup`／`gzFoot`，空表、5 列 2 列 0 億、展開、換族群沿用、全部 0 億、沒有 0 億 7 種狀態的表尾文字與 `gz` class，HTML 逐字；`check_wire`：表尾在捲動框外、監聽只在圖模式、`gzFoot` 不碰 localStorage；`check_mobile`：`bubbleList`（`blAll` 兩種）新輸出拿掉 ` class="z"` 後 = 拿掉標記的舊 `groupRows` 輸出；`check_css`：檔尾一行逐字、`tr.z` 只出現 1 次、`:145`、`:335`、`:351` 字串不變 | 5～10 |
| `test_bubble_data` | 資料日 2026-11-25 時：三種分組 4,768 列、0 億 2,175 列；電子零組件 209／78、農業科技 4／4、觀光餐旅 50／44 | 11（資料） |
| `test_head_css` | `.s-name` 22px 不變、`.s-code` 新字串、`@media (max-width:374px)` 緊接在 720 區塊之後、`.s-name{` 共 2 處、`stock.js` 頁頭與 `:372` 字串不變 | 12 |
| `test_screen` | `check_screen`：`nx` 假資料「息」「權息」加 `nxd`／`nxa`／`nxt`，「權」、未知類型、沒有這檔不加；`S = null`、刪掉 `App.latest` 不拋錯不加；`latest.date` 故意設成和 `S.d` 不同，天數只看 `S.d`（1、8、41 天）；`SCR_COLS.nx` 輸出逐字、方向 `1`；`check_cond`：`nxd` 位置在 `dvr`、`pb` 之間，`v = 7/14/30` 對 1、7、8、14、15、30、31、41、`null` 的邊界；條件行逐字在 `02-pm.md`；`SCREEN_GROUPS` 不變 | 15～18 |
| `test_screen_data` | 資料日 2026-11-25 時：真實 `latest.json` 全部股票跑 `screenRow`＋`nxd`：7 天 3 檔、14 天 10 檔、30 天 14 檔（代號同 PM 驗收 19），「權」4 檔不出現 | 19 |
| `test_words_node14` | 新段落（`gzFoot`、各檔含「第 49 輪」的行、README 段落）不含用詞清單；`gzFoot`／`groupRows`／`screenRow` 不用 `.at(`、`replaceAll`、`\|\|=`、`&&=`、`??=` | 22、23 |
| `test_version_and_docs` | 6 個 `?v=` = sha1 前 8 碼、`stock.js`／`help.js`／`compare.js` 值不變、`https://` 2 個、README 指令與段落關鍵字 | 26 |
| `test_contrast` | 17 個反證，每個都要讓對應檢查失敗（node 拋錯也算失敗） | 反證 |

### 反證清單（`test_contrast`，副本逐一確認都被擋下）

| # | 改壞方式 | 擋下的檢查 |
|---|---|---|
| 1 | F47-9 換回 `md(from)` | `check_dv`（驗收 1） |
| 2 | `v.d > from` → `>=`（含起日當天） | `check_dv`（驗收 3，次數 3、`y1 = 14`） |
| 3 | 0 億判斷改成數值門檻 `Math.abs(n) < 0.1` | `check_rows`（驗收 5） |
| 4 | `null` 當成 0（`yi(s.n1 ?? 0)`） | `check_rows` |
| 5 | 排序反過來 | `check_rows`（驗收 10） |
| 6 | CSS 寫成 `tr.z{display:none}`（不分桌面手機） | `check_css`（驗收 8／9） |
| 7 | 標記多加 `hidden`（手機清單也收起） | `check_mobile`（驗收 9） |
| 8 | 全部 0 億也寫「另有」 | `check_foot`（驗收 6） |
| 9 | 預設展開（`toggle('gz', App.gzAll)`） | `check_foot`（驗收 7） |
| 10 | `showGroup` 不呼叫 `gzFoot`（換族群表尾不更新） | `check_foot` |
| 11 | 表尾放進捲動框內 | `check_wire` |
| 12 | 「權」也算 | `check_screen`（驗收 15） |
| 13 | 天數基準改用 `App.latest.date` | `check_screen`（驗收 16） |
| 14 | 直接取 `App.latest.nx[code]`（假 `App` 沒有 `latest` 會拋錯） | `check_screen`（驗收 15） |
| 15 | `SCR_COLS.nx` 方向改 `-1` | `check_screen`（驗收 17） |
| 16 | `x.nxa <= v` → `<` | `check_cond`（驗收 16） |
| 17 | 表尾文字混入用詞清單中的詞 | `check_words`（驗收 22） |

## 四、PM 驗收 29 條對照

| # | 項目 | SA 對應 | 副本結果 |
|---|---|---|---|
| 1 | F47-9 四個分支 | 2-1；`test_dv` | 通過 |
| 2 | 跨年與閏年 | `test_dv` | 通過（`2027/03/02`） |
| 3 | 口徑不變 | `test_dv`、反證 2 | 通過 |
| 4 | F47-9 畫面 4 檔 | QA 畫面 | SA 未逐檔看（PG／QA） |
| 5 | 列標記 | 2-2；`check_rows` | 通過 |
| 6 | 表尾文字 | `check_foot` | 通過 |
| 7 | 展開／收合、沿用、不寫 localStorage | `check_foot`、`check_wire`；畫面 | 通過；畫面 1024 寬點「顯示」→ 50 列、「含 44 檔…收合」；換電子零組件仍展開 209 列；再點收回 131 列；localStorage 沒有新鍵 |
| 8 | CSS | `check_css` | 通過 |
| 9 | 手機不變 | `check_mobile`；`test_iter28`、`test_iter30` 0 行改動且通過 | 通過 |
| 10 | 順序不變 | `check_rows`、反證 5 | 通過 |
| 11 | 畫面 1024×800 | `test_bubble_data`；畫面 | 電子零組件可見 131 列、「另有 78 檔…」；農業科技 0 列、「4 檔…」；觀光餐旅 6 列、「另有 44 檔…」；表尾在 `.panel-list` 下緣之下（1055 ≥ 1049）。產業鏈、概念股由 `test_bubble_data` 合計核對，畫面留 QA。見第七節差異 4 |
| 12 | F47-11 CSS | 2-3；`test_head_css` | 通過 |
| 13 | 全部名稱量測 | QA | SA 只抽 4 檔（320 寬，17px）：國泰永續高股息、國泰股利精選30、北極星藥業-KY 一行，009818 兩行；全量照分析師方法由 QA 量 |
| 14 | F47-11 例 | QA 畫面 | 320 寬 00878 代號在名稱下一行、`scrollWidth = 320`；1024 寬留 QA 目視 |
| 15 | 欄位 | `check_screen` | 通過 |
| 16 | 天數 | `check_screen`、`check_cond` | 通過 |
| 17 | 欄位顯示 | `check_screen` | 通過 |
| 18 | 條件定義 | `test_screen`；`test_iter35:147～148`、`:168` 0 行改動且通過 | 通過 |
| 19 | 實際資料 | `test_screen_data` | 通過（3／10／14 檔） |
| 20 | 連結 | 既有 `scrParse`／`scrQuery` | 畫面 `?nxd=14` 已勾、值 14、網址保留 `nxd=14`；「複製條件連結」留 QA |
| 21 | 畫面排序 | 見第七節差異 1（D176） | `?nxd=14` 預設依成交額排序（10 檔）；`?nxd=30&o=nx` 第一列 6523「1 天後」 |
| 22 | 禁用詞 | `test_words_node14`、反證 17 | 通過；diff 全部新增行 0 命中 |
| 23 | node 14 | `test_words_node14`；本機 node v14.17.1 跑全部測試 | 通過 |
| 24 | 舊測試 | 第五節 | 8 行；`test_iter39:266` 未改 |
| 25 | 全部測試 | 49 個檔 | 全部通過 |
| 26 | `?v=` | 2-5；`test_version_and_docs` | 通過 |
| 27 | 不碰資料 | 本 diff 不含 `twstock/`、`site/data/` | 通過 |
| 28 | 畫面 1024／375／320 × 淺／深 | QA | SA 看過 1024 泡泡圖、1024 選股、320 個股、320 泡泡圖（清單→圖：`#gZ`「另有 42 檔…」、`gz`；清單模式沒有 `#gZ`），`scrollWidth = innerWidth`，主控台 0 錯誤；深色與其他組合留 QA |
| 29 | 測試後恢復 | 做法 | 8001 已關、8002 未用、8000 未碰、preset desktop、localStorage 恢復 |

## 五、舊測試（使用者已同意 8 行，其他 0 行）

| # | 檔名:行號 | 改後 |
|---|---|---|
| 1 | `tests/test_iter39.py:262` | `"近一年現金股利 = 2025/11/20 以後 4 次合計"` |
| 2 | `tests/test_iter39.py:263` | `"近一年現金股利 = 2025/11/20 以後 1 次合計<"` |
| 3 | `tests/test_iter39.py:265` | `"近一年現金股利 = 2025/11/20 以後 1 次合計；部分缺值，請自行確認"` |
| 4 | `tests/test_iter40.py:400` | `"近一年現金股利 = 2025/11/20 以後 1 次合計"], "2026-12-03"),` |
| 5 | `tests/test_iter40.py:404` | `…"近一年現金股利 = 2025/11/20 以後 1 次合計"], "2026-12-10"),` |
| 6 | `tests/test_iter41.py:437` | 雜湊 `4aec4a83de78` → **`81d223f49f68`**（SA 最終 `tools.js` 重算，和分析師副本相同；行尾註解不改） |
| 7 | `tests/test_iter47.py:380` | `assert HTML.count("https://") == 2` |
| 8 | `tests/test_iter48.py:301` | `assert "help.js?v=a5a5a7e8" in HTML and HTML.count("https://") == 2` |

- `git diff --numstat tests/`：`test_iter39` 3／3、`test_iter40` 2／2、`test_iter41` 1／1、`test_iter47` 1／1、`test_iter48` 1／1，合計 8 行；另新檔 `test_iter49.py`。
- `tests/test_iter39.py:266` 未改（子字串仍成立）。

## 六、套用順序（PG）

1. `git apply docs/iterations/49/03-design.diff`。
2. `shasum site/app.css site/app.js site/tools.js` 前 8 碼應為 `ce1417aa`、`54952a23`、`0a050889`（和 `index.html` 相同）。
3. `for f in tests/test_iter*.py; do python3 $f >/dev/null 2>&1 || echo FAIL $f; done` 沒有輸出。
4. 不需要 `export`（`site/data` 不變）。

## 七、和 PM 規格的差異（逐點）

1. **驗收 21「第一列是天數最小的」：只勾條件時做不到**。選股結果的預設排序是成交額（`o` 沒指定時 `'tv'`，`dvr` 等既有條件也一樣），勾條件不會換排序欄；`#/rank/screen?nxd=14` 第一列是新應材（9 天後）。要近的在前，需點「即將除息」欄頭或用 `?nxd=14&o=nx`（副本實測第一列 6523「1 天後」）。SA 沒有改排序邏輯（PM 範圍沒有，且會牽動既有條件的排序行為），列為 **D176**。
2. **表尾點擊監聽掛在 `#gZ`，不掛 `#view` 事件委派**（PM 二之九）：`#view` 在換頁、換分組時不重建，匿名監聽會一直累積（QA25-01 同類問題），點一次會切換兩次變成沒反應；`#gZ` 每次 `renderBubble` 重建，和 `data-blall` 掛在 `#blBox` 是同一種做法。既有 `onRowClick` 不改。
3. **展開／收合不重畫成分股表**（PM 寫「重新套用目前族群」）：新函式 `gzFoot` 只依目前 `#gTable` 內容換 class 與表尾，結果相同，不需要另記目前族群；`showGroup` 也呼叫它。
4. **驗收 11「表尾不用捲動就看得到」**：表尾在 `.panel-list` 捲動框之外，不用捲動表格就看得到；但 1024×800 時整張成分股卡本來就在泡泡圖下方（表尾 top 1055px），要捲動頁面才看得到卡片，這點和改前相同。
5. **新測試 305 行**（PM 估 80～100 行）：多了實際資料核對（驗收 11、19）與 17 個反證；在上限內。
6. 其餘（文字、位置、CSS、條件、欄位）和 PM 二之一逐字相同。

## 八、需要使用者決定的事項

### D176 選股勾「{v} 天內將除息」時的排序

| 選項 | 內容 | 影響 |
|---|---|---|
| **A（預設）** | 不改排序：照既有選股行為預設依成交額；要近的在前點「即將除息」欄頭或用 `?nxd=14&o=nx`。驗收 21 改成「`?nxd=14&o=nx` 第一列是 1 天後那檔；只用 `?nxd=14` 時有『即將除息』欄」 | 0 行；和 `dvr`「近 {v} 天內除息」一致 |
| B | 網址沒有 `o` 而條件含 `nxd` 時，預設排序改 `nx` | `app.js` 約 1 行；多一個「依勾選條件決定預設排序」的特例，其他條件不同；要多 1～2 個測試 |

- 預設 A 的理由：本輪是小項輪，PM 範圍沒有排序改動；既有條件都不自動換排序，單獨為 `nxd` 開特例會讓行為不一致；表頭一點即可。

## 九、疑慮

- 驗收 13（全部 2,354 個名稱在 320／360／375 寬的行數）SA 只抽 4 檔，全量照分析師方法由 QA 量。
- `test_bubble_data`、`test_screen_data` 只在資料日 2026-11-25 時核對筆數；之後資料日不同會印「略過」，定義與一致性仍由其他測試檢查。
- `docs/iterations/README.md` 第 49 輪那一行只寫到設計，PG／QA 之後補。

## 使用者決定（2026-11-25）

- D176：A。不改排序，維持成交額排序，驗收 21 改用 `?nxd=14&o=nx`。
- SA 與 PM 的差異全部接受：
  - 監聽掛在 `#gZ`。
  - 新增 `gzFoot`。
  - 驗收 11 的補充說明。
  - 新測試 305 行。
