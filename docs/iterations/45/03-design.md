# 第 45 輪｜System Analyst：設計

- 撰寫日期：2026-11-22（週日）
- 依據：`45/01-analyst.md`（D128～D133 = A）、`45/02-pm.md`（F45-1～F45-5、驗收 21 條）。
- 產出：本檔＋`45/03-design.diff`（445 行，可直接 `git apply`；在專案目錄 `git apply --check` 已通過）。
- 做法：
  - 用 `git ls-files` 把專案檔案與 `site/data` 複製到 scratchpad `r45sa/`，**沒有 `.env`**；在副本 `git init` 當基準，所有修改都在副本完成，diff 由副本產生。
  - `help.js` 的名詞資料**用程式從 `02-pm.md` 二之一的 8 張表產生**（不手抄），`test_iter45` 也直接拿同一份表比對。
  - 副本跑 `tests/test_iter01～45` 共 45 個檔，**全部通過**。
  - 畫面：在副本目錄背景起 `python3 -u -m twstock serve --port 8001 --no-browser`（服務副本的 `site/`），內建瀏覽器看 320／375／1024 寬、淺色／深色。
  - 結束後 localStorage 設回 `{"tw.todayTab":"ov"}`、視窗 desktop／淺色、`pkill`，8001 沒有 LISTEN。
- 守則：沒有讀 `.env`、沒有連資料庫、沒有外部請求、沒有 `export`／`collect`、沒有用 8000；專案目錄只新增本檔與 `03-design.diff`。

---

## 一、改了哪些檔（`git diff --numstat`）

| 檔案 | 加／減 | 內容 |
|---|---|---|
| `site/help.js`（新） | 79／0 | `HELP` 名詞資料、`helpHTML`、`window.renderHelp` |
| `site/app.js` | 2／1 | `routes` 加 `help`；分頁標題加 `help: '名詞說明'` |
| `site/app.css` | 1／0 | 檔尾一行：`.help-btn`、`.help-g`、`.help-t`（含 `on` 標示、連結藍色不換行） |
| `site/tools.js` | 1／1 | QA44-03（`:258`） |
| `site/index.html` | 6／4 | 頂欄「?」、頁尾連結、`help.js` 的 `<script>`、3 個 `?v=` |
| `tests/test_iter41.py` | 1／1 | `:437` 雜湊（D130） |
| `tests/test_iter45.py`（新） | 231／0 | 9 個測試、19 個反證 |
| `README.md` | 2／0 | 第 45 輪說明一段、測試指令一行 |
| `docs/iterations/README.md` | 1／0 | 第 45 輪一行 |

- `index.html` 的 `?v=`（和 `shasum` 前 8 碼相同）：

  | 檔案 | `?v=` |
  |---|---|
  | `app.css` | 7f4315c2 |
  | `app.js` | c7bb2119 |
  | `stock.js` | c2c7d916（不變） |
  | `tools.js` | 64e7360f |
  | `help.js` | 55e93876 |

- `test_iter41:437` 新雜湊：**`4aec4a83de78`**（和分析師副本值相同；`tools.js` 只改這 1 行）。

## 二、程式設計

### 2-1 `site/help.js`

- `HELP = [[組代號, 組名, [[代號, 名詞, 定義, 連結文字, 網址], …]], …]`：8 組、41 個名詞、24 個連結，文字和 `02-pm.md` 二之一逐字相同。
- `helpHTML(id)`：純函式，回傳整頁 HTML。
  - 標題卡：`sec-h` 標題「名詞說明」、說明一行、8 個 `.chip` 分組按鈕（`#/help/組代號`）。
  - 每組 `<section class="sec card" id="help-組代號">`，每個名詞 `<div class="help-t" id="help-代號"><b>名詞</b><div>定義　<a href="網址">連結文字 →</a></div></div>`。
  - `id` 等於某個名詞代號時，那一列 class 加 `on`；組代號、空字串不標示。
  - 最後一行 `<div class="muted small">名詞說明只描述算法與定義，不是買賣訊號。</div>`（見第四節差異 1）。
  - 名詞文字是固定字串、不含 `<`、`&`，不需要 `esc`。
- `window.renderHelp(arg)`：
  - 代號（名詞或組）存在 → 畫整頁、標示，然後 `requestAnimationFrame` 裡 `scrollIntoView()`（照泡泡圖做法，在 `route()` 捲到頂端之後才捲）。
  - 捲動前先確認元素還在：已經換到別頁時不捲（第四節差異 3）。
  - 代號不存在 → `history.replaceState(history.state, '', '#/help')`、畫整頁、不捲動。
  - 不用 `?.`、`??`、`.at(` 等，node 14 可直接執行。
- 不讀資料、不用 `localStorage`、不連網。

### 2-2 `site/app.js`（2 行）

```
  help: arg => window.renderHelp(arg),                   // 第 45 輪：名詞說明 #/help、#/help/代號（help.js）
```
- 分頁標題對照表：`watch: '自選', tools: '工具', help: '名詞說明' }` → `名詞說明｜台股資金流`。
- 主選單沒有 `help`，所以頂欄、底部都不會有 `on`。

### 2-3 `site/index.html`

- 頂欄深淺色按鈕前：`<a class="theme-btn help-btn" href="#/help" aria-label="名詞說明" title="名詞說明">?</a>`（深淺色按鈕那一行不改）。
- 頁尾：`<footer class="foot wrap"><a href="#/help">名詞說明</a>　資料來源：…`。
- `tools.js` 之後：`<script src="help.js?v=55e93876" defer></script>`。

### 2-4 `site/app.css`（檔尾 1 行）

```
.help-btn{font-size:16px;font-weight:700;line-height:1;text-decoration:none}.help-g{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}.help-t{padding:8px 6px;border-top:1px solid var(--border);scroll-margin-top:calc(var(--top-h,56px) + 8px)}.sec-h+.help-t{border-top:0}.help-t a{color:var(--blue);white-space:nowrap}.help-t.on{background:var(--card2);box-shadow:inset 3px 0 0 var(--blue)}   /* 第 45 輪：名詞說明 */
```

- 組卡片的 `scroll-margin-top` 沿用 `app.css:292` 既有的 `#view .card`。

### 2-5 `site/tools.js:258`（QA44-03）

```
    `可領現金元以下捨去；不足 1 股依${e ? '發行人' : '公司'}公告折付現金，可在期限內湊股；實際以${e ? '發行人' : '公司'}發放為準。`,
```

## 三、測試設計（`tests/test_iter45.py`）

| 測試 | 驗收 | 內容 |
|---|---|---|
| `test_data` | 1、2、4 | 用 node 取出 `HELP`，和 `02-pm.md` 二之一（程式解析 8 張表）逐字比對；8 組 41 個、代號不重複；24 個連結都在 `RANKS`＋`screen`、`TODAY_TABS`、`route()` 的工具分頁清單或三個固定頁；不含 0.15%、0.3%、2.11%、2027、2 萬 |
| `test_sync` | 3 | 9 組「辭典文字 ↔ 程式字面」：KD(9,3,3) ↔ `calcKD(… n = 9)`、RSI(14)、MACD 12／26／9、量比 20 日 ↔ `export.py` `prior = yi[-21:-1]`、券資比 1,000 張 ↔ `MARGIN_BASE`、大戶 400／1,000 張與散戶 50 張 ↔ `shCards`、一年位置 242 |
| `test_page` | 5～8 | 用替身 `document`、`history`、`requestAnimationFrame` 執行 `renderHelp`：`vr`（標示、捲到 `help-vr`）、`credit`（捲到組、不標示）、`xyz`（網址改 `#/help`、不捲）、沒有參數；版面開頭、8 張組卡順序、41 列、頁尾逐字；**捲動前已換頁不報錯** |
| `test_route` | 9 | 沿用 `test_iter41` 的 `route()` 替身：`#/help`、`#/help/vr` 的參數與分頁標題 |
| `test_entry` | 10 | 「?」在深淺色按鈕前；頁尾連結；頂欄與底部 `data-tab` 各 6 個；`help.js` 在 `tools.js` 後只載入一次 |
| `test_dv_etf` | 11 | 沿用 `test_iter39._out`：ETF 寫「發行人」兩處、股票照舊「公司」 |
| `test_versions_words_docs` | 14～16 | 4 個 `?v=`；`https://` 仍 2 個；`help.js` 不連網、不用 `localStorage`；禁用詞（去掉「借券賣出」後，`test_iter42.ADVICE`＋`test_iter43:511` 清單）；node 14 語法；README、總表 |
| `test_contrast` | — | 19 個反證，每個都要讓對應檢查失敗 |

- 反證：改錯一個字、少一個名詞、連到不存在的排行、連到不存在的今日分頁、代號重複、寫進稅率、KD 參數不同步、大戶門檻不同步（改 `stock.js`）、量比天數不同步（改 `export.py`）、沒有標示、組代號也標示、沒有延後捲動、已換頁仍捲、不存在不改網址、沒有頁尾、ETF 仍寫公司、發行人與公司對調、用到禁用詞、node 14 不支援。
- `test_iter45` 會讀 `docs/iterations/45/02-pm.md`，所以這份文件要和程式一起 commit。

## 四、和 PM 規格的差異（SA 決定，請使用者確認）

1. **頁尾一句改字**：PM 二之二寫「名詞說明只描述算法與定義，不構成投資建議。」，但「建議」在禁用詞清單，D133 只允許「借券賣出」當例外。改成**「名詞說明只描述算法與定義，不是買賣訊號。」**（全站估值卡已有「不是買賣訊號」的說法）。網站頁尾原本的「不構成投資建議」在 `index.html`，不受影響。
2. **連結藍色、不拆行**：PM 沒有指定樣式。實測 320 寬時連結和內文同色、不易看出可以點，「看創新高排行 →」還會被拆成兩行；加 `.help-t a{color:var(--blue);white-space:nowrap}` 後 41 列連結都不超出卡片、不拆行。
3. **捲動前確認元素還在**：內建瀏覽器面板隱藏時 `requestAnimationFrame` 不會執行，等使用者換到別頁才執行就找不到元素、主控台報錯（實測發現）。改成找不到就不捲，`test_page` 加這個情況，反證「已換頁仍捲」。

## 五、畫面（副本 8001）

| 項目 | 結果 |
|---|---|
| `#/help`（1024、375、320） | 41 列、8 張組卡；`scrollWidth = innerWidth`；分頁標題 `名詞說明｜台股資金流`；主選單沒有 `on` |
| `#/help/vr` | `help-vr` 標示（淺色、深色都可見）；手動 `scrollIntoView` 後列頂端在頂欄下方 63px（頂欄 55px） |
| `#/help/xyz` | 網址變 `#/help`、沒有標示 |
| 頂欄（今日、工具、個股、辭典；375） | 高度 55px 不變；「?」和深淺色按鈕同為 34×34、同一高度；搜尋框 217px（320 寬 162px） |
| 連結（320） | 0 個超出、0 個拆行 |
| `#/tools/dv?c=0050` | 說明「不足 1 股依發行人公告折付現金…實際以發行人發放為準」 |
| 主控台 | 新版沒有錯誤（只有改版前舊檔的錯誤與 8001 重啟時的連線失敗） |

- **沒驗到**：面板隱藏時 `requestAnimationFrame` 不執行，所以「打開 `#/help/vr` 自動捲到量比」這一步在 SA 沒有實際看到（只驗了手動捲動的位置、和測試中的排程）。**QA 請在面板顯示時看一次**（驗收 18）。

## 六、給 PG

- `git apply docs/iterations/45/03-design.diff`，不需要手動改。
- 套用後：
  - `shasum` 確認 5 個 `?v=` 如第一節；`test_iter41:437` 的雜湊用最終 `tools.js` 重算，應為 `4aec4a83de78`。
  - 跑 `tests/test_iter01～45`。
- 舊測試只動 `test_iter41:437`（D130），其他舊測試不得改。
- 本輪不需要 `export`、`collect`，不碰資料庫；`site/data` 不變。

## 使用者決定（2026-11-22）

- 同意第四節 3 處和 PM 規格的差異（頁尾改「不是買賣訊號」、連結藍色不拆行、捲動前確認元素還在），進 PG。
