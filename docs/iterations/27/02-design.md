# 第 27 輪｜UI/UX 設計師：版面與讀圖風險修正（投資工具化 第二階段）

- 撰寫日期：2026-11-15（週日）
- 依據：
  - `27/01-analyst.md`：U27-01～32、第三節口徑彙整、第五節「不建議改動」、第六節限制、第七節優先順序。
  - `25/02-design.md`（格式、token、第 4-2 節測試鎖定）、`25/04-qa.md`、`26/01-dev.md`（深淺色切換）。
  - `24/03-design.md` 附錄 A：第 24 輪待套用的 diff（`app.css`、`stock.js`、`index.html`）。
- 原型作業：
  - scratchpad `ux27d/` 建兩份副本：`orig`（HEAD `7562f10` 的工作目錄）、`proj`（本設計）。兩份都**不含 `.env`**、`.git`。
  - `proj` 的 diff 就是本文件附錄 A（`site/` 與 `tests/`），**PG 可以直接套用**（見第六節）；新測試全文在附錄 B。
  - 8001 預覽 `proj`，每次改檔後重算 `?v=`，開頁前用 `fetch(…, {cache:'reload'})` 強制重新驗證，確認載入的 `?v=` 與 `proj/site/index.html` 相同才量測。8000 沒有碰。
  - 結束時已 `pkill -f "twstock serve --port 8001"`，`lsof -iTCP:8001 -sTCP:LISTEN` 無輸出；localStorage 已刪除本次加的鍵（`tw.focus`、`tw.todayTab`、`tw.screen`、`tw.mgv`、`tw.watch`、`tw.rank2`），只留開始前就有的 `tw.stockTab=k`；視窗已恢復 desktop。
  - 沒有執行 `collect`、`history`、`export`、`setup-db`，沒有 DB 寫入，沒有修改專案程式與測試、沒有 commit。**本文件是唯一寫進專案的檔案。**
- 編號：本輪設計項目用 **D27-01～D27-10**。
- 用詞：照舊不用「買進、賣出、反彈、見底、買點、超賣、超買、推薦、強勢股、飆股、勝率、建議（投資）、低估、高估」；新文案只描述資料（`test_iter27.test_no_advice_words` 檢查本輪新增的行，「借券賣出」是官方資料欄名，扣除後再比對）。

---

## 〇、結論摘要

| 項目 | 結果 |
|---|---|
| 本輪範圍 | D27-01～10，涵蓋分析師前 10 名中的第 1～8、10 名（U27-12、13、17、18、19 文案、20、01、22、23、24、25、05、29、06、31、30），加上次要項 U27-03、07、08、10、11、16、28、32 |
| 不放本輪 | U27-02（只做了 `#/today`、`#/rank` 的網址正規化）、U27-04、U27-26、U25-35、U25-22、U25-07／13 |
| 需使用者決定 | U27-09、14、15、19（用詞確認，本輪先上預設文案）、21、27，以及「自選事件卡要不要列接近處置（推算）」 |
| 變更量 | `app.css` ＋16／−9、`app.js` ＋80／−32、`stock.js` ＋19／−20、`index.html` ＋3／−3：**程式＋CSS 新增 115 行、刪除 61 行** |
| 舊測試 | **改 4 個檔、5 行**（`test_iter11:224`、`test_iter12:82`、`test_iter17:132`、`test_iter23:257、260`），理由見 4-2 |
| 新測試 | `tests/test_iter27.py` 13 個測試（231 行）。`proj` 執行 `test_iter01～23、25、26、27` **全部通過**；用 `orig` 跑 `test_iter27`：12 個功能測試全部失敗、`test_no_advice_words` 通過（反向驗證成立） |
| 和第 24 輪 | **先套 27 再套 24**：第 24 輪的 `app.css`、`stock.js` 都能 `patch` 乾淨套用，只有 `index.html` 的 `?v=` 衝突。先套 24 再套 27：`app.css` 有 1 段（480px 那一行）要手動換 |
| 資料口徑 | 不新增欄位、不改 `site/data`、不改 `twstock/`。泡泡圖 Y 軸只改文案，定義（近 5 日日均 − 20 日日均）不變 |

---

## 一、設計原則與風格方向

### 1-1 延續第 25、26 輪的視覺語言

- 圓角卡片、膠囊分段鈕、紅漲綠跌、第 25 輪色彩 token、第 26 輪深淺色切換都不動。
- 新元件都由既有元件組成：
  - 選股條件標籤、「符合 N 檔 ↓」用 `.chip`。
  - 融資融券切換用 `segHTML`。
  - 圖例色塊用既有的 `.lg`（MACD／KD 圖例已在用）。
- 不新增色彩 token。新的顏色需求都用既有 token：`--on-fill`、`--amber`、`--blue`。

### 1-2 本輪的主軸：「讀錯」比「不好看」優先

分析師這輪找到的高、中嚴重度項目，多數是**會讓人讀反或讀漏的地方**，不是美觀問題。本輪處理順序依「讀錯的代價」：

| 類型 | 項目 | 原則 |
|---|---|---|
| 讀反 | K 線最新價標籤色（U27-22）、泡泡圖 Y 軸（U27-19）、融資融券單刻度（U27-24） | 同一張圖上的顏色、刻度只能有一種意思 |
| 讀漏 | 長表格底部被擋（U27-12）、處置摘要漏接近處置（U27-05）、主動 ETF 沒標持股日（U27-07） | 資料要在第一眼看得到的地方寫完整 |
| 找不到 | 選股結果數（U27-17）、手機估值列（U27-25）、泡泡圖點了沒回饋（U27-20） | 動作之後，結果要出現在畫面內 |
| 太慢 | 手機新訊號列高（U27-13）、自選新增入口（U27-31）、拖曳不會捲動（U27-30） | 減少捲動與進出頁面 |

### 1-3 不改的東西

第 25 輪、第 26 輪「不建議改動」清單全部保留（分析師第五節）。本輪特別避開：

- 第一欄固定（`.tbl th:first-child`）。
- `hlTag` 的輸出字串（`test_iter22`）。
- `tw.*` 既有鍵名，本輪只新增 `tw.mgv`。
- 圖表函式庫版本（Lightweight Charts 4.2.0、Plotly 2.35.2）。
- 前一夜盤刻意淡化的 4.26。

---

## 二、本輪範圍（D27-xx）

| D27 | 對應 U27 | 內容 | 檔案 | 新增行數（約） |
|---|---|---|---|---|
| D27-01 | U27-12 | 長表格改整頁捲動，表頭跟著頂欄（JS 位移 `thead th`） | css、app | 15 |
| D27-02 | U27-13 | 新訊號手機版：標籤改成第二列（整列寬），名稱欄只放名稱與代號 | css、app | 5 |
| D27-03 | U27-17、18 | 選股：條件列固定在頂欄下方，顯示「符合 N 檔 ↓」、條件與排除分開計數；收合時列出已選條件（可 ✕ 移除） | css、app | 14 |
| D27-04 | U27-19（文案）、U27-20 | 泡泡圖 Y 軸改「偏流入／偏流出」（定義不變）、標籤最小 10px、淺色不透明；手機點泡泡捲到明細 | app | 7 |
| D27-05 | U27-01、U27-02（部分） | `#/today` 沒指定分頁時開總覽，同一次瀏覽中才回到上次分頁；`#/rank` 同理；網址補成實際分頁 | app | 6 |
| D27-06 | U27-22、23、25 | K 線最新價標籤依漲跌上色、圖例 MA 改色塊＋正文色數字（期貨圖同步）、手機關鍵數字列移到 K 線正下方 | stock、app、css | 10 |
| D27-07 | U27-24 | 融資融券子圖一次一條線（融資／融券／借券賣出切換），右側刻度就是那條線 | stock | 12（刪 13） |
| D27-08 | U27-05、06、29、32 | 處置摘要加「接近處置（推算）N」；差一次的理由直接顯示；自選事件卡寫處置期間（最後一天）與注意原因；事件卡移到 ETF 表之後 | app | 6 |
| D27-09 | U27-31、30 | 搜尋清單每列 ☆ 直接加入／移除自選；自選空狀態加「搜尋股票」鈕；編輯鈕觸控範圍 ≥ 40px；拖到畫面邊緣自動捲動 | app、css | 24 |
| D27-10 | U27-03、07、08、10、11、16、28 | 分頁標題、主動 ETF 卡持股日、象限卡底色、期貨未平倉表欄距、手機日期列、名稱欄截斷、「持股尚未支援」改純文字 | app、stock、css | 11 |
| 合計 | 23 項 U27 | | | **約 115 行**（另刪 61 行） |

### 2-1 不放本輪的項目與理由

| 項目 | 理由 |
|---|---|
| U27-04／U25-29 指數卡迷你走勢顏色 | 迷你走勢用「近 60 日方向」上色是第 13 輪刻意的設計（`spark()` 的 `vals.at(-1) >= vals[0]`）。改中性色或各分頁都加說明列，會改變總覽以外分頁的指數卡高度（第 25 輪 D25-02 量過）。屬於「這條線要表達什麼」的決定，請 PM 決定後再做；本輪不動 |
| U25-35 新訊號面向色點 | 4 個面向各一種顏色，會和紅漲綠跌、象限 4 色衝突；`hlTag` 輸出被 `test_iter22` 鎖定。D27-02 已把手機列高從平均 233px 降到 108px，色點的必要性下降 |
| U25-22 子圖收合 | U27-24 改用 D27-07 的切換解決，U27-25 改用 D27-06 搬移解決。收合需要記住每張子圖的狀態（新的 localStorage 鍵），也會動到十字線同步的 `anchors`，風險比收益大 |
| U27-26、U25-07／13 籌碼分頁小卡分組、時間序列 | 要新增圖表，工作量估 80 行以上，超過本輪剩餘額度 |
| U27-02 其餘部分（`#/xyz`、`#/stock/2330/abc` 提示） | 本輪只做 `#/today/xxx`、`#/rank/xxx` 的網址正規化（D27-05）。未知路由提示要新增一種提示元件，留給下一輪和 U25-32 一起做 |
| U27-20「清單模式」 | 新增一種檢視，工作量大；本輪先做「點了捲到明細」與標籤字級 |
| U27-31「排行列尾 ☆」 | 手機排行的欄寬已滿（漲跌欄右緣 295／375）；本輪只做搜尋清單 ☆ 與空狀態入口 |

---

## 三、各項規格

> 量測環境：8001 預覽 `proj`；內建瀏覽器仿真 375×812、1024×768，色調用 `resize_window colorScheme` 切換；對比依 WCAG 2.x 公式，背景色由元素往上疊算（含半透明）。「原本」數值取自分析師附錄或本輪在 `orig` 實測。

### D27-01 長表格整頁捲動（U27-12）

**問題**：第 25 輪 D25-07 用 `.tbl-wrap:has(tbody tr:nth-child(25)){max-height:…;overflow:auto}` 讓表頭 sticky，結果變成框內捲動：手機排行框底 1006，可視下緣只到 758（底部選單擋住 248px）。

**做法**：

- CSS 拿掉兩條 `max-height`（桌面、≤720 各一條），表格回到整頁捲動。
- `.tbl-wrap` 要保留 `overflow-x:auto`（手機橫捲），CSS sticky 只能貼在框內。所以改成 `thead th{transform:translateY(var(--th-y,0px))}`，由 `stickHeads()` 算位移：
  - `--th-y = clamp(0, 頂欄下緣 − 表格框頂端, 表格高 − 2 × 表頭高)`。
  - 表頭最多跟到表格倒數兩列，不會蓋到下一張卡片。
- 觸發時機：
  - `scroll`（passive）、`resize`。
  - `#view` 的 `MutationObserver`（換頁、重畫時歸零）。
- 只處理 ≥ 25 列的表格，和第 25 輪的門檻相同。

| 量測 | 375 淺 | 1024 淺 | 1024 深 |
|---|---|---|---|
| 捲到表格中段時 `thead th` 頂端 | 55（頂欄下緣 55） | 55（頂欄 55） | 55 |
| 表頭底色 | `--card`，不透明 | 同左 | `rgb(23,24,27)`，表頭字對比 7.38 |
| 頁尾可見 | 頁尾底部 748 < 底部選單上緣 759 | 是 | 是 |
| `document.scrollingElement.scrollWidth` | 375（所有頁） | 1024 | 1024 |
| 表格框是否有內捲軸 | 無 | 無 | 無 |

**已知限制**：

- 手機慣性捲動時，`scroll` 事件晚一幀，表頭可能延遲一幀才跟上（不會錯位到表格外）。
- 內建瀏覽器窗格的 scroll 事件時序不穩，自動量測時請手動呼叫 `stickHeads()` 再量；用實際捲動截圖也已確認位置正確。

### D27-02 新訊號手機版：標籤改第二列（U27-13）

- `renderHl` 每檔輸出兩個 `<tr>`：
  - 第一列：名稱、面向數、收盤、漲跌、20 日均額。
  - 第二列：`<tr class="hl-sub" data-code><td colspan="6">標籤…</td></tr>`。
- ≤480：
  - 隱藏「近期新訊號」欄，顯示第二列（`display:table-row`）。
  - 第一列去掉底線、第二列 `padding-top:0`。
  - 每個 `.hl-tag` 不換行（「法人連買 3 日」不會被拆開）。
- >480：`.hl-sub{display:none}` 照舊（第 23 輪字面沒動），1024 版面與原本相同。
- 第二列有 `data-code`，點標籤列一樣進個股頁（沿用 `onRowClick` 的 `tr[data-code]`）。

| 量測（375 淺，36 檔） | 原本 | 本設計 |
|---|---|---|
| 每檔高度（兩列合計）平均／最高／最低 | 233／359／169 | **108／175／95** |
| 表格總高 | 8,404 | **3,900** |
| 名稱欄寬 | 93 | 87 |
| 漲跌欄右緣 | — | 277（< 375，不橫捲） |

名稱欄「代號 產業」改成單行、過長截斷（D27-10，U27-16），名稱欄 span 加 `width:0;min-width:100%`，避免長產業名撐寬表格（原本 314 > 309 會橫捲）。

### D27-03 選股條件列（U27-17、18）

- `<summary>` 改為 sticky：`top:var(--top-h)`，背景 `--card`，展開時下緣 1px 分隔線。
  - `--top-h` 由 `init` 依頂欄實際高度設定。
- 內容：`條件 N 個＋排除 M 個`、`符合 X 檔 ↓`、重設、複製條件連結。
  - 條件與排除分開計數；`nx = 0` 時不顯示「＋排除」。
- 「符合 X 檔 ↓」（`.chip.scr-go`，藍框藍字）：點了 `#scrRes`（結果標題）捲到頂欄下方（`scroll-margin-top`），不切換面板開合。
- 收合時，summary 下方列出已選的非排除條件（`.scr-tags`），每個是 `.chip`，文字如「均線 收盤 > MA20 > MA60 ✕」，點了移除該條件並重算。展開時隱藏（條件已在面板中）。
- 用 `scrollIntoView()` 不用 smooth：smooth 在部分情況不會捲動（實測）。

| 量測 | 1024 淺 | 1024 深 | 375 淺 |
|---|---|---|---|
| summary 捲動後頂端 | 55（貼頂欄） | 55 | 55 |
| 例：`?ma=3&nh=60&xd=1&xn=1&xc=1` | 「條件 2 個＋排除 3 個　符合 61 檔 ↓」 | 同左 | 同左，換行 |
| `.scr-go` 對比（字／底） | 5.21（`--blue` 對白，計算值） | 5.05（實測） | 同淺色 |
| `.scr-tags .chip` 對比 | 17.22（`--text` 對白，計算值） | 15.03（實測） | 同淺色 |
| 點「符合 N 檔 ↓」後結果標題頂端 | 頂欄下 8px | 同左 | 同左 |

### D27-04 泡泡圖（U27-19 文案、U27-20）

- **Y 軸文案**（定義不變，見 `twstock/analysis/flow.py`：Y = 近 5 日平均 − 近 20 日平均，億/天）：

| 位置 | 原本 | 本設計 |
|---|---|---|
| 副標 | Y：比 20 日平均加速或放緩 | Y：近 5 日日均比 20 日日均偏流入或偏流出 |
| 軸標題 | ↓ 放緩　　加速 ↑ | ↓ 偏流出　近 5 日日均 − 20 日日均（億/天）　偏流入 ↑ |
| 提示 | 加速度 +x 億/天 | 5日日均−20日日均 +x 億/天 |

  - 理由：「加速／放緩」在淨流出那半邊意思相反；「偏流入／偏流出」在四個象限都成立，且和象限說明（觀望：仍是淨流出，但賣壓比過去小）不矛盾。
  - 這是**防誤讀的文案修正，不改定義**；用詞列入第五節請使用者確認，未確認前以本文案為預設。
- 標籤：
  - 最小字級 8 → **10px**（放不下的泡泡不標，沿用既有的碰撞規則）。分析師建議 11px，本輪未實測 11px 的標籤數；10px 是「可讀」與「標籤數」的折衷，請 QA 回報手機實際觀感。
  - 白字不變。
- 透明度：淺色 `opacity:1`（不透明），深色維持 `.82`。
  - 淺色原本 .82 疊在白底，最淡的綠泡泡白字只有 3.58。
- 手機（`narrow`）點泡泡：更新明細後 `$('#gTitle').closest('.card').scrollIntoView()`。

| 量測 | 375 淺 | 375 深 | 1024 淺 | 1024 深 |
|---|---|---|---|---|
| 泡泡數／有標籤數 | 34／12（原本 15，8～9px） | 34／12 | 34／17 | 34／17 |
| 標籤最小字級 | 10 | 10 | 10 | 10 |
| 泡泡上白字最低對比 | 4.97 | 6.34（.82 疊卡片底） | 4.97 | 6.34 |
| 軸刻度、軸標題 | — | 7.38 | — | 7.38 |
| 象限角落字（漲潮／輪動／觀望／退潮） | — | 5.34／8.23／5.05／5.34 | — | 同左 |
| 點「半導體」後明細卡頂端 | 63（頂欄下） | 63 | 不捲動 | 不捲動 |

### D27-05 `#/today`、`#/rank` 預設與網址（U27-01、U27-02 部分）

- `renderToday(t)`：
  - `t` 是合法分頁 → 用 `t`。
  - 否則用 `App.todayTab`（同一次瀏覽中上次的分頁），沒有就 `'ov'`。
  - `t !== t0` 時 `history.replaceState` 補成 `#/today/t0`。
  - `tw.todayTab` 仍照舊寫入（鍵名不變），但**開站時不再讀它**。
- `renderRank(arg)`：同理用 `App.rank2 || 'n+'`，解構出 `by` 後 `arg !== by` 時補網址 `#/rank/by`。

| 操作 | 結果（1024 淺實測） |
|---|---|
| 新開 `#/today` | 總覽，網址 → `#/today/ov` |
| 切到期貨後點底部「今日」（`#/today`） | 期貨，網址 → `#/today/fut` |
| `#/today/insti`（打錯） | 目前的分頁，網址補正 |
| 新開 `#/rank` | 法人買超，網址 → `#/rank/n+` |
| `#/rank/zzz` | 目前的排行，網址補正 |

### D27-06 個股 K 線（U27-22、23、25）

- **最新價標籤**：
  - 關掉系列預設的 `lastValueVisible`、`priceLineVisible`（它依 K 棒「收盤對開盤」上色）。
  - 改用 `createPriceLine`，顏色依 `barChange` 的最後一根上色：日線是收盤對昨收，和頁首同色；週／月線是對上一根；無成交為 `--flat`。
  - 標籤文字色用 `axisLabelTextColor: css('--on-fill')`（淺色白、深色 #111）。

| 對比（標籤字／底） | 淺色 | 深色 |
|---|---|---|
| 漲 | 白／#cc3333 5.14 | #111／#ef5b5b **5.68**（函式庫預設白字只有 3.32） |
| 跌 | 白／#247b51 5.21 | #111／#349f6a 5.68 |
| 平、無成交 | 白／#6d6d6d 5.17 | #111／#8a8a8a 5.47 |

  - 實測：2330 頁首 ▲10 紅色，標籤 2,350 紅色（原本綠色）。

- **圖例 MA**：`<span class="lg"><i style="background:色"></i>MA20 <b>數字</b></span>`，線色只在 8px 色塊，文字與數字用正文色。期貨圖（`drawFutures`）同步改。

| 對比 | 原本（淺） | 本設計 淺 | 本設計 深 |
|---|---|---|---|
| MA 標籤文字 | MA20 2.17、MA5 3.61、MA60 3.76 | 6.39 | 7.38 |
| MA 數字 | 同上 | 17.22 | 15.03 |

- **手機關鍵數字列**（≤720）：從「K 線卡之後」（8299 原本 y=1626）搬到 `#kC` 正下方。
  - 用 `#kC+.kv` 固定 3 欄（`.chart-box+.kv` 的權重蓋不過 media 規則）。

| 375 淺 | 2330 | 8299 | 2421 | 0050 |
|---|---|---|---|---|
| K 線頂端 | 561 | 586 | 478 | 504 |
| 關鍵數字列頂端 | 889 | 914（原本 1626） | 806 | 832 |
| 數字列高 | 250（3 欄各 102px） | 250 | 250 | 75 |

  - 1024：K 線頂端 2330 495、8299 495、2421 468、0050 471，和第 25 輪相同（數字列照舊併進頁首卡）。

### D27-07 融資融券子圖單一序列（U27-24）

- 子圖標題改成分段鈕：`融資｜融券｜借券賣出`＋「餘額」。「借券賣出」只在 `data.mg.lb` 存在時出現。
- 一次只畫一條線，右側刻度就是那條線。
  - 原本三條線各自縮放、只有融資有刻度，借券常是融券的上百倍，形狀會看反。
- 選擇存在 `tw.mgv`（`mb`／`sb`／`lb`）。
  - 選了 `lb` 但該股沒有借券資料時，退回融資（`mgView`）。
- 圖例（`gLegend`）不變，仍同時列出三個數值；十字線錨點跟著所選的線。
- 單位說明只留「（張；面額變更、減資前的餘額依官方換算）」，刪掉「右側刻度只適用融資…」那句。
- 線色沿用 `#1C7ED6`／`#AE3EC9`／`#E8590C`。

### D27-08 處置資訊補齊（U27-05、06、29、32）

- **今日總覽摘要列**（收合時）：`11/13　即將處置 0　處置中 5　接近處置（推算）9　今日注意 48`。「（推算）」跟著，避免被當成官方資料。
- **差一次**：理由從 `title` 改成直接顯示，例如「台揚（第一款連 2 日）、冠西電（…）」，手機看得到。
- **自選事件卡**：
  - 處置股：`處置 11/09～11/13（最後一天）`；未開始的寫 `即將處置 11/14～11/25`。
  - 注意股：下一行 `注意：<原因>`（`.al-why`，單行截斷；對比 7.38 深色）。原因取自 `App.latest.alerts.n`，不新增欄位。
  - 事件卡移到 ETF 表之後，兩張表相鄰（U27-32）。
- 本輪**不在自選事件卡列「接近處置（推算）」**：`test_iter17` 的意圖是「推算」只出現在今日清單（`A.w` 次數受鎖定），列入第五節。

### D27-09 自選新增入口與編輯（U27-31、30）

- **搜尋清單 ☆**：
  - 每列最右加 `<span class="qstar" role="button" data-w="代號">☆</span>`；已在自選為 ★（`--amber`）。
  - 點 ☆ 只切換自選、重畫清單，清單不關、不進個股頁。
  - 若目前在自選頁，同時重畫自選頁。
  - 用 `span role=button` 而不是 `<button>`：`<a>` 裡放 `<button>` 不合法。
  - 原本兩個點擊監聽合併成一個（`[data-w]` 優先）。
- **空狀態**：文字加「；或在上方搜尋，按清單右側的 ☆ 直接加入。」，下面一個「搜尋股票」`.chip`，點了 focus 頂欄搜尋框。
- **編輯模式觸控範圍**（≤720）：
  - `.wdel`、`.wh` 加 `::after{inset:-10px}`，圖示不變大。
  - 實際可點範圍約 42×42（左側貼表格框邊時被裁到框內）。
  - ✕ 和 ≡ 間距 29px，兩者的擴大範圍不重疊。
- **拖曳自動捲動**：
  - 手指在畫面頂端或底端 90px 內時，每幀捲 10px（rAF）；放開時 `cancelAnimationFrame`。
  - 拖曳改用頁面座標，捲動時列仍跟著手指。

| 量測 | 375 深（實測） | 淺色（計算值） |
|---|---|---|
| ☆ 尺寸 | 26×42 | 同左 |
| ☆／★ 對比 | 6.79／7.57 | 6.39（`--text2`）／5.21（`--amber`） |
| 點 ☆ 後 | `tw.watch` 寫入、圖示變 ★、網址不變 | — |
| ✕／≡ 圖示 | 22×22／21×22（觸控範圍各外擴 10px） | — |

### D27-10 小項

| 項目 | 規格 | 量測 |
|---|---|---|
| U27-03 分頁標題 | `今日｜台股資金流`、`泡泡圖｜…`、`新訊號｜…`、`選股｜…`、`排行｜…`、`主動 ETF 彙總｜…`、`00981A 持股｜…`、`ETF｜…`、`自選｜…`；個股頁 `台積電 2330｜台股資金流` | 11 條路由實測正確 |
| U27-07 主動 ETF 卡 | 標題副字：`8 檔合計，持股日 11/13（3 檔 11/12）`；全部同一天時不寫括號 | 今日「法人資金」分頁實測 |
| U27-08 象限卡 | 底色改成 `linear-gradient(--q-*) var(--card)`：淡色疊在卡片底上，不再透出頁面底 | 淺：漲潮 4.68、輪動 4.92、觀望 4.80、退潮 4.87（原本 4.19～4.42）；深：4.89／7.22／4.58／4.85 |
| U27-10 期貨未平倉表 | ≥521 時欄左右 padding 6px | 1024：表 457 = 卡內 457，不橫捲（原本 470） |
| U27-11 手機日期列 | 拿掉 `nowrap; overflow-x:auto`，改成可換行；法人資料日 = 資料日時隱藏「法人資料」那段（`.fd-eq`，只在 ≤720） | 375：日期列高 18（一行），K 線頂端維持 561／586／478／504 |
| U27-16 名稱欄 | ≤520 第二行「代號 產業」單行截斷 | 名稱欄寬 87（新訊號）、84（排行／ETF／選股） |
| U27-28 持股尚未支援 | `.tbl .nm .pill.muted` 去框、去底、去 padding，變純文字 | 1024 深：框色透明、對比 7.38 |

---

## 四、不能破壞的事項

### 4-1 已確認

- 375／1024 × 淺／深：今日 4 分頁、泡泡圖、排行、新訊號、選股、ETF、主動 ETF 彙總、自選、個股（2330、8299、2421、0050），`scrollWidth` 都等於視窗寬（不橫捲）。
- 主控台錯誤 0 則。
- 第 26 輪切換深淺色後重畫：泡泡透明度、K 線標籤字色都在畫圖當下取 token，切換後正確。

### 4-2 避開的測試鎖定

| 鎖定 | 出處 | 本設計怎麼避開 |
|---|---|---|
| `disposeFuturesChart(); renderToday();` | `test_iter12:100` | 分頁鈕只在前面加 `App.todayTab = v`，字面保留 |
| `` $('#dateBar').innerHTML = `<span class="nw">資料日 ${esc(L.date)}</span> `` | `test_iter13:102` | 開頭字面不動；全形空白移進第二段 span（`.fd-eq` 才能連空白一起隱藏） |
| `.al-why{white-space:nowrap`、`.al-row` | `test_iter16:121` | 自選事件卡的注意原因沿用 `.al-why` |
| `renderHl` 在 node 裡執行 | `test_iter21:137` | 新 `<tr class="hl-sub">` 只用既有的 `hlTag`，不引用新函式 |
| `hlTag` 輸出字串 | `test_iter22` | 不改 |
| `<td class="hl-tags">${x.hl.map(hlTag).join('')}</td>`、`.hl-sub{display:none}` | `test_iter23:258、259` | 不動 |
| `renderWatch` 在 node 裡只帶部分函式執行 | `test_iter20`、`23`、`25` | 事件卡用到的 `hlTag`、`HL_KINDS` 只在有 `hl` 時才求值；新的 `App.latest.alerts?.n` 用 optional chaining（測試資料沒有 `alerts`）；`#watchFind` 用 `?.` |
| `kSer.setMarkers(` | `test_iter14:91` | K 線系列變數名不變 |
| 「已選」字面 | `test_iter26:59` 是深色測試的變數，與選股無關 | 無衝突 |
| node 14 沒有 `Array.prototype.at` | 測試在 node 裡執行的函式 | 本輪新增的 `activeCard` 用 `.sort().pop()`，不用 `.at(-1)` |

**非改不可的舊測試（5 行）**：

| 檔案：行 | 原本 | 改成 | 理由 |
|---|---|---|---|
| `test_iter11.py:224` | `"priceScaleId: 'lb'" in js` | `"lb: [LB, '#E8590C']" in js` | D27-07 不再用疊加軸；借券仍有自己的資料與顏色，原測試的意圖（借券有畫出來）保留 |
| `test_iter12.py:82` | `"右側刻度只適用融資；融券、借券各自縮放" in js` | `"segHTML('mgSeg'" in js and "右側刻度只適用融資" not in js` | 這句說明是為了單刻度的限制，D27-07 之後刻度就是所選的線，這句變成錯的 |
| `test_iter17.py:132` | `APP.count("A.w") == 1` | `APP.count("A.w") == 2 and "接近處置（推算）${(A.w \|\| []).length}" in APP` | U27-05 摘要列要顯示檔數；仍只在今日清單用，選股、自選不加（`alerts.w` 仍不可出現） |
| `test_iter23.py:257` | 名稱格內 `<div class="hl-sub">` | 名稱格只有 `<span>代號 產業</span></td>`，另有 `<tr class="hl-sub" …><td colspan="6">` | D27-02 改第二列 |
| `test_iter23.py:260` | `….tbl td.nm .hl-sub{display:block;white-space:normal}` | `….tbl tr.hl-sub{display:table-row}` | 同上 |

### 4-3 `index.html` 的 `?v=`

| 套用情境 | `app.css` | `app.js` | `stock.js` |
|---|---|---|---|
| 原本（HEAD `7562f10`） | `56df32ca` | `f9b7833d` | `eb734b38` |
| 只套第 27 輪（附錄 A） | `39f292f5` | `62040b25` | `51cc333a` |
| 第 27 輪＋第 24 輪附錄 A 的 `site/` | `025c4261` | `62040b25` | `370faf08` |

- PG 實際套用後若有差異，以 `test_iter23.test_version_hash` 失敗時印出的 3 行為準。

### 4-4 與第 24 輪的衝突點

- 已實測（scratchpad 副本，用 `patch -p1`）：

| 順序 | `app.css` | `stock.js` | `index.html` |
|---|---|---|---|
| 先 27 後 24（建議） | 第 24 輪 1 段乾淨套用 | 5 段乾淨套用 | `?v=` 衝突，重算 |
| 先 24 後 27 | 第 27 輪 4 段中 1 段失敗：480px 那一行（第 24 輪在它前面插了 `table.dv-tbl` 一行，前後文對不上）。手動把該行換成附錄 A 的新行即可 | 乾淨套用 | `?v=` 衝突 |

- 內容上沒有互相依賴：
  - 第 24 輪的 `divHTML`、`NET_TIP`、`dv-tbl` 不碰本輪修改的函式。
  - 第 24 輪新測試（`24/03-design.md` 附錄 A 的 `test_iter24.py`）沒有引用本輪改動的字面（已 grep `右側刻度`、`priceScaleId`、`mgSeg`、`hl-sub`、`gUnit`、`kv`、`document.title`）。
- 第 24 輪的 `dv-tbl`（股利表）在手機上的名稱欄不受 D27-10 的截斷影響：它不是 `td.nm`。

---

## 五、需使用者決定

| 編號 | 項目 | 選項 | 建議預設 | 本輪做法 |
|---|---|---|---|---|
| U27-19 | 泡泡圖 Y 軸用詞 | A「偏流入／偏流出」（本輪）；B 四個象限角落寫短說明、軸只寫「近 5 日日均 − 20 日日均」；C 維持「加速／放緩」 | **A**：四個象限都成立，不改定義，字數最少 | 已以 A 上線於原型；若選 B／C，只改 `app.js` 3 個字串與 `test_iter27.test_bubble_wording` |
| U27-09 | 期貨「籌碼因子觀察」長條顏色與說明句 | A 中性雙色（藍／琥珀）＋0 軸；B 維持紅綠但加圖例「紅＝高於 60 日常態」 | **A**：全站紅色＝漲／增加，負數畫紅色會讀反 | 不動（說明句屬文案，UI 不自行改寫） |
| U27-14 | 四捨五入為「0億」時要不要帶紅綠色 | A 顯示為 0 時一律 `--flat`；B 依原值正負上色（現狀） | **A**：看到的數字是 0，顏色也應該是平 | 不動（影響 `yi()`、多張表與測試字面） |
| U27-15（＋U25-15） | 全站小數位、單位位置、「百分點」 | A 單位移到表頭、儲存格只放數字；B 維持儲存格帶「億」，統一小數位規則（≥100 取整、<100 一位） | **B 先做**：改動面小、不動表頭鎖定；A 留到下一輪整體改版 | 不動 |
| U27-21 | 類股流向最大一檔占比 | A 匯出端新增欄位，明細標題寫「最大一檔占 N%」；B 前端用明細表計算；門檻（例如 ≥ 60% 才標） | **A＋門檻 60%**：前端沒有所有類股的個股明細 | 不動（需要新欄位） |
| U27-27 | ETF 折溢價、規模 | 需要每日淨值資料來源 | 先請 PM 評估資料來源與收集頻率 | 不動 |
| 新增 | 自選事件卡要不要列「接近處置（推算）」 | A 列（要再改 `test_iter17` 的 `A.w` 次數鎖定）；B 不列（現狀） | **B**：`test_iter17` 的意圖是推算資訊只在今日清單出現，避免被當成官方狀態 | B |

---

## 六、給 PG 的實作順序與行數

建議直接套用附錄 A（`patch -p1`，路徑前綴 `orig/`、`proj/` 改成 `a/`、`b/`），再新增附錄 B 的 `tests/test_iter27.py`。若要逐項手寫，順序如下（每步跑一次全部測試）：

| 步驟 | 項目 | 行數 | 驗證 |
|---|---|---|---|
| 1 | D27-10 小項 | 11 | `test_iter13`、`test_iter27.test_titles_and_small_fixes`、`test_quads_on_card` |
| 2 | D27-01 長表格（CSS 2 條刪除＋1 條新增、`stickHeads`、`init` 監聽） | 15 | `test_iter27.test_long_table_page_scroll`；375 實際捲動確認頁尾在底部選單上方 |
| 3 | D27-02 新訊號第二列 | 5 | 改 `test_iter23:257、260`；`test_iter21`、`test_iter27.test_hl_second_row` |
| 4 | D27-08 處置資訊 | 6 | 改 `test_iter17:132`；`test_iter16`、`test_iter27.test_alert_summary_and_reasons`、`test_watch_event_card` |
| 5 | D27-05 預設分頁與網址 | 6 | `test_iter12`、`test_iter27.test_default_tab_and_url` |
| 6 | D27-03 選股條件列 | 14 | `test_iter27.test_screen_summary` |
| 7 | D27-04 泡泡圖 | 7 | `test_iter27.test_bubble_wording` |
| 8 | D27-06 K 線 | 10 | `test_iter14`、`test_iter27.test_stock_chart_legend_and_price_line` |
| 9 | D27-07 融資融券 | 12（刪 13） | 改 `test_iter11:224`、`test_iter12:82`；`test_iter27.test_margin_single_series` |
| 10 | D27-09 搜尋 ☆、編輯觸控、拖曳捲動 | 24 | `test_iter20`、`23`、`25`、`test_iter27.test_search_star_and_drag` |
| 11 | `?v=` 重算 | 3 | `test_iter23.test_version_hash` |
| 合計 | | **約 115 行新增、61 行刪除；舊測試 5 行** | `for f in tests/test_iter*.py; do python3 $f; done` 全部通過；`node --check site/app.js site/stock.js` |

注意：

- node 是 v14，測試會在 node 裡執行 `renderWatch`、`renderHl`、`alertBoard`、`activeCard` 等函式。新程式不要在這些函式裡用 `.at()`、`replaceAll`。
- 新的 localStorage 鍵只有 `tw.mgv`。

---

## 七、給 QA 的佈局驗證清單

### 7-1 前置

1. 8001 啟動後，主控台 `await fetch('/app.js?v=…',{cache:'reload'})`（三個檔與 `index.html` 都要），確認 `document.scripts` 的 `?v=` 與 4-3 表相同。
2. 開始前記下 localStorage 的鍵；結束時刪除本次加的鍵（本輪新增 `tw.mgv`）。
3. 尺寸：`resize_window` 375×812、1024×768；色調：`colorScheme: 'light'／'dark'`。結束時 preset desktop。

### 7-2 量測工具（主控台）

```js
window.rgb=s=>s.match(/[\d.]+/g).map(Number);
window.Lm=c=>{const a=c.slice(0,3).map(v=>{v/=255;return v<=.03928?v/12.92:Math.pow((v+.055)/1.055,2.4)});return .2126*a[0]+.7152*a[1]+.0722*a[2]};
window.bgOf=el=>{let L=[];while(el){const b=rgb(getComputedStyle(el).backgroundColor);if(b.length<4||b[3]>0){L.push(b);if(b.length<4||b[3]>=1)break;}el=el.parentElement;}
  if(!el)L.push(rgb(getComputedStyle(document.body).backgroundColor));let c=L.pop().slice(0,3);while(L.length){const l=L.pop(),a=l.length>3?l[3]:1;c=c.map((v,i)=>l[i]*a+v*(1-a));}return c;};
window.CR=(f,b)=>{const a=Lm(f),c=Lm(b);return +((Math.max(a,c)+.05)/(Math.min(a,c)+.05)).toFixed(2)};
window.crEl=el=>CR(rgb(getComputedStyle(el).color),bgOf(el));
```

- `bgOf` 不處理 `background-image`。象限卡（`linear-gradient`）要手動把 `--q-*` 疊在 `--card` 上計算，或直接看 `test_iter27.test_quads_on_card`。
- 泡泡上白字：泡泡 `fill` 依 `opacity`（淺 1、深 .82）疊在卡片底上，再和白色比。

### 7-3 逐頁清單（每頁 × 375／1024 × 淺／深）

| 頁面 | 檢查 | 量測方法 | 期望值 |
|---|---|---|---|
| 全部頁 | 不橫捲 | `document.documentElement.scrollWidth` | = 視窗寬 |
| 全部頁 | 分頁標題 | `document.title` | 見 D27-10 表 |
| 全部頁（375） | 日期列一行、不截斷 | `#dateBar` 高 | 18（法人資料日 = 資料日時）；不同日時可換行 |
| 今日 `#/today` | 新開開總覽 | 清掉 `App.todayTab`（重新整理）後開 `#/today` | 網址變 `#/today/ov` |
| 今日 | 切期貨後點底部「今日」 | — | 停在期貨，網址 `#/today/fut` |
| 今日總覽 | 處置摘要列 | `.al-box summary` 文字 | 含「接近處置（推算）N」 |
| 今日總覽 | 差一次理由 | `.al-near a` | 名字後有「（第一款連 2 日）」，無 `title` |
| 今日總覽 | 象限卡標題對比 | 手動疊算 | 淺 ≥ 4.68、深 ≥ 4.58 |
| 今日法人資金 | 主動 ETF 卡 | `.sec-h` 文字 | 「持股日 11/13（3 檔 11/12）」 |
| 今日期貨（1024） | 未平倉表 | `.oi-tbl` 寬 vs `.tbl-wrap` `clientWidth` | 相等（457），不橫捲 |
| 今日期貨 | MA 圖例 | `#fLegend .lg` 與 `b` 的 `crEl` | 文字 ≥ 6.39、數字 ≥ 15 |
| 排行 `#/rank/n+` | 表頭跟頂欄 | 捲到表格中段，`thead th` 頂端 vs `.top` 下緣 | 相等（55） |
| 排行（375） | 頁尾不被擋 | 捲到底，`footer` 底 vs 底部選單上緣 | 748 < 759 |
| 排行 | `#/rank`、`#/rank/zzz` | 網址 | `#/rank/n+`／目前排行 |
| 新訊號 `#/rank/hl`（375） | 列高 | 每檔兩列合計 | 平均約 108、最高 ≤ 175；漲跌欄右緣 < 375 |
| 新訊號（1024） | 版面同原本 | `tr.hl-sub` 的 `display` | `none` |
| 選股 `#/rank/screen` | 條件列固定 | 捲動後 `summary` 頂端 | = 頂欄下緣 |
| 選股 | 計數 | 帶 `?ma=3&nh=60&xd=1&xn=1&xc=1` | 「條件 2 個＋排除 3 個」「符合 N 檔 ↓」 |
| 選股 | 捷徑 | 點「符合 N 檔 ↓」 | `#scrRes` 頂端 = 頂欄下 8px |
| 選股 | 收合後的標籤 | 收合面板，點標籤 ✕ | 條件移除、結果重算、網址參數更新 |
| 泡泡圖 | Y 軸文案 | `.g-ytitle text` | 「↓ 偏流出　近 5 日日均 − 20 日日均（億/天）　偏流入 ↑」 |
| 泡泡圖 | 標籤 | `.textpoint text` 有字者的 `font-size` | 最小 10；375 約 12 個、1024 約 17 個 |
| 泡泡圖 | 透明度 | `.scatterlayer .point` 的 `opacity` | 淺 1、深 0.82 |
| 泡泡圖（375） | 點泡泡 | 點「半導體」 | `#gTitle` 所在卡片頂端在頂欄下方（約 63） |
| 個股 2330 | 標題 | `document.title` | 「台積電 2330｜台股資金流」 |
| 個股 | 最新價標籤 | 截圖放大右側價格軸 | 和頁首同色（2330 紅）；深色時深字 |
| 個股 | MA 圖例 | `#kLegend .lg` | 淺：文字 6.39、數字 17.22；深：7.38／15.03 |
| 個股（375） | 數字列位置 | `.metrics.kv` 頂端 | 2330 889、8299 914、2421 806、0050 832 |
| 個股（375） | K 線頂端 | `#kC` 頂端＋`scrollY` | 561／586／478／504（不得超過 600） |
| 個股 | 融資融券切換 | 點「融券」 | 只剩一條紫線、右側刻度跟著變；`tw.mgv=sb`；重新整理後保留 |
| 個股 0050 | 無借券資料的股票 | `tw.mgv=lb` 開一檔沒有 `mg.lb` 的股票 | 退回融資 |
| ETF `#/etf` | 持股尚未支援 | `.tbl .nm .pill.muted` | 無框、無底 |
| 自選（空） | 入口 | — | 有「搜尋股票」鈕，點了 focus 搜尋框 |
| 搜尋 | ☆ | 輸入 2330，點 ☆ | 變 ★、`tw.watch` 含 2330、清單不關、網址不變 |
| 自選 | 事件卡 | 加入 2360、1709、3008 | 「處置 11/09～11/13（最後一天）」「注意：…」；事件卡在 ETF 表之後 |
| 自選（375，編輯） | 觸控範圍 | `elementFromPoint(✕ 上緣 − 8px)` | 命中 `.wdel` |
| 自選（375，編輯） | 拖曳自動捲動 | 加入 10 檔以上，按住 ≡ 拖到畫面底 90px 內 | 頁面持續往下捲，列跟著手指；放開後順序存檔 |
| 主控台 | 錯誤 | `read_console_messages onlyErrors` | 0 則 |

### 7-4 回歸

- 第 25 輪 QA 清單（`25/04-qa.md`）中長表格的項目：表頭現在由 JS 位移，量法改成上表的「表頭跟頂欄」。
- 第 26 輪：在每一頁切換深淺色，確認泡泡透明度、K 線價格標籤字色會跟著重畫。

---

## 附錄 A：完整 diff（`orig` → `proj`；`site/` 與 `tests/`，不含 `site/data`；新測試檔全文見附錄 B）

```diff
diff -ruN -x data orig/site/app.css proj/site/app.css
--- orig/site/app.css	2026-11-15 10:50:09
+++ proj/site/app.css	2026-11-15 15:32:52
@@ -104,10 +104,10 @@
 .quad .t{font-size:12px;font-weight:600}
 .quad .n{font-size:22px;font-weight:600}
 .quad .d{font-size:11px;color:var(--text2)}
-.q-漲潮{background:var(--q-rise)}.q-漲潮 .t{color:var(--up)}
-.q-輪動{background:var(--q-rot)}.q-輪動 .t{color:var(--amber)}
-.q-觀望{background:var(--q-watch)}.q-觀望 .t{color:var(--blue)}
-.q-退潮{background:var(--q-ebb)}.q-退潮 .t{color:var(--dn)}
+.q-漲潮{background:linear-gradient(var(--q-rise),var(--q-rise)) var(--card)}.q-漲潮 .t{color:var(--up)}
+.q-輪動{background:linear-gradient(var(--q-rot),var(--q-rot)) var(--card)}.q-輪動 .t{color:var(--amber)}
+.q-觀望{background:linear-gradient(var(--q-watch),var(--q-watch)) var(--card)}.q-觀望 .t{color:var(--blue)}
+.q-退潮{background:linear-gradient(var(--q-ebb),var(--q-ebb)) var(--card)}.q-退潮 .t{color:var(--dn)}
 
 /* 資金流長條 */
 .bars{display:flex;flex-direction:column;gap:6px}
@@ -264,7 +264,7 @@
 .al-box>summary{list-style:none;cursor:pointer;margin-bottom:0}.al-box>summary::-webkit-details-marker{display:none}.al-box[open]>summary{margin-bottom:6px}   /* D25-04 */
 .al-box>summary i{font-style:normal;color:var(--blue);font-size:12px}.al-box>summary i::after{content:'展開 ▾'}.al-box[open]>summary i::after{content:'收合 ▴'}
 .tbl thead th{position:sticky;top:0;z-index:2;background:var(--card)}.tbl thead th:first-child{z-index:3}   /* D25-07 固定表頭 */
-.tbl-wrap:has(tbody tr:nth-child(25)){max-height:calc(100vh - 140px);overflow:auto}
+.tbl-wrap:has(tbody tr:nth-child(25)) thead th{transform:translateY(var(--th-y,0px))}   /* 第 27 輪 D27-01：整頁捲動，表頭由 stickHeads() 位移到頂欄下方 */
 .metrics.kv{grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:0;background:var(--card);border:1px solid var(--border);border-radius:var(--radius);overflow:hidden}   /* D25-05 關鍵數字列 */
 .kv .card{border:0;border-radius:0;padding:6px 10px}.kv .s{font-size:11px;line-height:1.35}
 .s-head+.kv{margin:8px 0 0}.sec.page-tabs{margin:10px 0 0}
@@ -284,19 +284,26 @@
 .w-tip{margin-top:8px}
 .card.w-ev{margin-top:12px}.w-ev .sec-h{margin-bottom:4px}
 .rk-q{display:flex;flex-wrap:wrap;gap:6px;margin:0 0 8px}
+/* ─── 第 27 輪（D27-xx）────────────────────────── */
+#view .card,#scrRes{scroll-margin-top:calc(var(--top-h,56px) + 8px)}
+.scr-panel>summary{position:sticky;top:var(--top-h,56px);z-index:4;background:var(--card);margin:-6px -16px 0;padding:8px 16px;border-radius:var(--radius)}   /* D27-03 */
+.scr-panel[open]>summary{border-bottom:1px solid var(--border)}.scr-go{color:var(--blue);border-color:var(--blue)}
+.scr-tags{display:flex;flex-wrap:wrap;gap:6px;margin-top:6px;font-weight:400}.scr-panel[open] .scr-tags{display:none}
+#kC+.kv{margin:8px 0 4px;grid-template-columns:repeat(3,minmax(0,1fr))}                                                                                    /* D27-06 手機關鍵數字列在 K 線下方 */
+.qstar{cursor:pointer;padding:0 2px 0 8px;color:var(--text2);font-size:16px;line-height:1}.qstar.on{color:var(--amber)}   /* D27-09 */
+@media (min-width:521px){.oi-tbl th,.oi-tbl td{padding-left:6px;padding-right:6px}}.tbl .nm .pill.muted{border-color:transparent;background:none;padding:0}   /* D27-10 */
 @media (max-width:720px){
   .seg button{min-height:34px}.page-tabs .seg button{min-height:38px}.chip,.sel{min-height:34px}.scr-c input[type=checkbox]{width:18px;height:18px}   /* D25-12 觸控 */
   .hint{display:none}
-  .datebar{white-space:nowrap;overflow-x:auto;scrollbar-width:none}
-  .tbl-wrap:has(tbody tr:nth-child(25)){max-height:calc(100dvh - 170px)}
   .s-head{position:relative}.s-head .star{position:absolute;top:0;right:0;padding:4px 10px;font-size:13px}.s-nm{padding-right:112px}
   .qlist .ind{display:none}
   .metrics.kv{grid-template-columns:repeat(auto-fit,minmax(104px,1fr))}
   .sec-h .seg button{padding:4px 9px}.kleg{font-size:11px;gap:2px 8px}
+  .datebar .fd-eq{display:none}.wdel,.wh{position:relative}.wdel::after,.wh::after{content:'';position:absolute;inset:-10px}   /* D27-09 觸控範圍 ≥ 40px，圖示不變大 */
 }
 @media (max-width:520px){
   .tbl th,.tbl td{padding:8px 6px}
-  .tbl td.nm{white-space:normal;min-width:84px;max-width:124px}.tbl td.nm>span{display:block;margin-left:0}   /* D25-06 名稱欄兩行 */
+  .tbl td.nm{white-space:normal;min-width:84px;max-width:124px}.tbl td.nm>span{display:block;margin-left:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;width:0;min-width:100%}   /* D25-06 名稱欄兩行；D27-10 產業名過長截斷 */
 }
 /* 第 14 輪 F14-1、F14-2：營收、EPS 年增欄的第二行（月份、基期低、去年同季），欄寬不被撐開 */
 .tbl .sub2{display:block;font-size:11px;line-height:1.3;color:var(--text2)}
@@ -310,4 +317,4 @@
 .note-dup .note[open] summary i{font-size:12px;margin-left:0}
 .tbl td.hl-tags,.tbl th.hl-th{white-space:normal;min-width:12em;text-align:left}.hl-tag{display:inline-block;margin:1px 8px 1px 0;font-size:12px}.hl-tag i{font-style:normal;color:var(--text2)}   /* 第 21 輪 F21-1 */
 .hl-sub{display:none}table.pf-tbl{max-width:560px}.pf-tbl td span{display:block;color:var(--text2);font-size:11px}   /* 第 23 輪 F23-4a、F23-1 */
-@media (max-width:480px){.tbl th.hl-th,.tbl td.hl-tags{display:none}.tbl td.nm .hl-sub{display:block;white-space:normal}.tbl .nm .hl-sub span{color:var(--text);font-size:12px;margin:2px 8px 0 0}}
+@media (max-width:480px){.tbl th.hl-th,.tbl td.hl-tags{display:none}.tbl tr.hl-sub{display:table-row}.tbl tr:has(+.hl-sub) td{border-bottom:0;padding-bottom:2px}.tbl tr.hl-sub td{padding-top:0;white-space:normal;box-shadow:none}.hl-sub .hl-tag{white-space:nowrap}}   /* 第 27 輪 D27-02 */
diff -ruN -x data orig/site/app.js proj/site/app.js
--- orig/site/app.js	2026-11-15 10:50:09
+++ proj/site/app.js	2026-11-15 15:37:43
@@ -69,6 +69,9 @@
 async function route() {
   const [, page = 'today', arg, sub] = location.hash.split('/');
   if (page !== 'watch') App.watchUndo = App.watchEdit = null;   // 離開自選頁：清掉復原、結束編輯
+  // 第 27 輪 D27-10：瀏覽器分頁標題帶頁面名稱（個股頁由 renderStock 換成「名稱 代號」）
+  document.title = ({ today: '今日', bubble: '泡泡圖', rank: { hl: '新訊號', screen: '選股' }[String(arg).split('?')[0]] || '排行',
+    etf: arg === 'active' ? '主動 ETF 彙總' : arg ? arg + ' 持股' : 'ETF', watch: '自選' }[page] || (page === 'stock' ? arg : '今日')) + '｜台股資金流';
   document.querySelectorAll('[data-tab]').forEach(a => a.classList.toggle('on', a.dataset.tab === page));
   const view = $('#view');
   if (window.Plotly && $('#bubble')) Plotly.purge('bubble');
@@ -83,6 +86,15 @@
   window.scrollTo(0, 0);
 }
 
+// 第 27 輪 D27-01：25 列以上的表格不再關在固定高度的捲動框裡（整頁捲動，不會被畫面底部或底部選單擋住）。
+// .tbl-wrap 要保留橫向捲動，CSS sticky 只能貼在框內，所以捲動時把表頭位移到頂欄下方（--th-y，最多到表格最後兩列）
+function stickHeads() {
+  const top = $('.top').getBoundingClientRect().bottom;
+  [...document.querySelectorAll('#view .tbl-wrap')].filter(w => w.querySelector('tbody tr:nth-child(25)'))
+    .map(w => [w, w.getBoundingClientRect(), w.querySelector('thead')?.offsetHeight || 0])
+    .forEach(([w, r, h]) => w.style.setProperty('--th-y', Math.max(0, Math.min(top - r.top, r.height - 2 * h)) + 'px'));
+}
+
 // ─── 搜尋 ───────────────────────────────────────────────
 function setupSearch() {
   const input = $('#q'), list = $('#qList');
@@ -91,7 +103,8 @@
   const draw = () => {
     list.innerHTML = hits.map(([c, s], i) =>
       `<a href="#/stock/${c}" class="${i === active ? 'on' : ''}"><span class="code">${c}</span>${esc(s.n)}<span class="muted small ind" style="margin-left:auto">${esc(s.i ?? 'ETF')}</span>` +
-      `<span class="px num ${cls(s.p)}">${pfmt(s.c)}${s.p == null ? '' : ' ' + sgn(s.p) + '%'}</span></a>`).join('') ||
+      `<span class="px num ${cls(s.p)}">${pfmt(s.c)}${s.p == null ? '' : ' ' + sgn(s.p) + '%'}</span>` +
+      `<span class="qstar${App.watch.has(c) ? ' on' : ''}" role="button" data-w="${c}" title="${App.watch.has(c) ? '從自選移除' : '加入自選'}">${App.watch.has(c) ? '★' : '☆'}</span></a>`).join('') ||   // D27-09
       (input.value.trim() && App.latest ? `<div class="qnone">找不到「${esc(input.value.trim())}」，可輸入代號或名稱的一部分</div>` : '');   // 第 25 輪 D25-11
     list.hidden = !list.innerHTML;
   };
@@ -114,7 +127,15 @@
     } else if (e.key === 'Enter' && hits[active]) go(hits[active][0]);
     else if (e.key === 'Escape') { list.hidden = true; input.blur(); }
   });
-  list.addEventListener('click', e => { const a = e.target.closest('a'); if (a) { e.preventDefault(); go(a.getAttribute('href').split('/')[2]); } });
+  list.addEventListener('click', e => {
+    const a = e.target.closest('a'), w = e.target.closest('[data-w]');
+    if (w) {   // 第 27 輪 D27-09：☆ 直接加入／移除自選，不進個股頁、清單不關（stopPropagation：重畫後按鈕已不在 .search 裡）
+      e.preventDefault(); e.stopPropagation();
+      App.watch.has(w.dataset.w) ? App.watch.delete(w.dataset.w) : App.watch.add(w.dataset.w);
+      saveWatch(); draw();
+      if (location.hash.startsWith('#/watch')) renderWatch();
+    } else if (a) { e.preventDefault(); go(a.getAttribute('href').split('/')[2]); }
+  });
   document.addEventListener('click', e => { if (!e.target.closest('.search')) list.hidden = true; });
 }
 
@@ -125,7 +146,10 @@
 
 function renderToday(t) {
   const L = App.latest, groups = L.groups[App.group];
-  if (TODAY_TABS.some(x => x[0] === t)) localStore('todayTab', null, t);   // 第 25 輪 D25-08：#/today/分頁
+  // 第 25 輪 D25-08：#/today/分頁。第 27 輪 D27-05：沒指定分頁（#/today）時開總覽，同一次瀏覽中切回才用上次的分頁；網址補成實際顯示的分頁
+  const t0 = TODAY_TABS.some(x => x[0] === t) ? t : App.todayTab || 'ov';
+  localStore('todayTab', null, App.todayTab = t0);
+  if (t !== t0) history.replaceState(null, '', '#/today/' + t0);
   const span = localStore('span', '5');
   const key = span === '1' ? 'net_1d' : 'net_5d';
   const counts = Object.fromEntries(QUADS.map(([q]) => [q, groups.filter(g => g.quadrant === q).length]));
@@ -201,7 +225,7 @@
     ${pageTabsHTML('todayTabSeg', TODAY_TABS, tab)}
     ${body[tab]}`;
 
-  onSeg('todayTabSeg', v => { localStore('todayTab', null, v); history.replaceState(null, '', '#/today/' + v); disposeFuturesChart(); renderToday(); });
+  onSeg('todayTabSeg', v => { localStore('todayTab', null, App.todayTab = v); history.replaceState(null, '', '#/today/' + v); disposeFuturesChart(); renderToday(); });
   if ($('#grpSeg')) onSeg('grpSeg', v => { setGroup(v); renderToday(); });
   if ($('#spanSeg')) onSeg('spanSeg', v => { localStore('span', null, v); renderToday(); });
   $('#flowMore')?.addEventListener('click', () => { App.flowAll = !App.flowAll; renderToday(); });
@@ -345,7 +369,7 @@
   const nShow = App.alertAll ? A.n.length : 10;
   const grp = (t, list, n = list.length) => `<div class="al-grp"><h3>${t}　<span class="muted small">${n} 檔</span></h3>${list.join('') || '<div class="muted small">無</div>'}</div>`;
   return `<section class="sec card"><details class="al-box"${App.alOpen ? ' open' : ''}>
-      <summary class="sec-h"><h2>處置／注意股</h2><span class="muted small">${md(L.date)}　即將處置 ${up.length}　處置中 ${on.length}　今日注意 ${A.n.length}</span><span class="sp"></span><i></i></summary>
+      <summary class="sec-h"><h2>處置／注意股</h2><span class="muted small">${md(L.date)}　即將處置 ${up.length}　處置中 ${on.length}　接近處置（推算）${(A.w || []).length}　今日注意 ${A.n.length}</span><span class="sp"></span><i></i></summary>
       ${A.n.length > 10 ? `<button class="chip" id="alMore">${App.alertAll ? '注意只顯示 10 檔' : '注意顯示全部'}</button>` : ''}
       ${grp('即將處置', up.map(dsp))}${grp('處置中', on.map(dsp))}${watchGrp(A.w, S)}${grp('今日注意', A.n.slice(0, nShow).map(x => row(x[0], '', x[1])), A.n.length)}
       <div class="muted small">依證交所、櫃買中心公告；處置期間撮合間隔較長，買賣可能需預收款券。點股票看完整原因</div>
@@ -360,7 +384,7 @@
   return `<div class="al-grp"><h3>接近處置（推算）　<span class="muted small">已達條件 ${hit.length} 檔、差一次 ${near.length} 檔</span></h3>
       ${hit.map(x => `<a class="al-row" href="#/stock/${x[0]}"><div class="al-l"><b>${nm(x[0])}</b><span class="muted small">${x[0]}・${S[x[0]]?.m === 'TWSE' ? '上市' : '上櫃'}</span><span class="sp"></span><span class="small">已達條件</span></div>
         <div class="muted small al-why">${esc(x[2])}</div></a>`).join('')}
-      ${near.length ? `<div class="al-near small"><span class="muted">差一次：</span>${near.map(x => `<a href="#/stock/${x[0]}" title="${esc(x[2])}">${nm(x[0])}</a>`).join('、')}</div>` : ''}
+      ${near.length ? `<div class="al-near small"><span class="muted">差一次：</span>${near.map(x => `<a href="#/stock/${x[0]}">${nm(x[0])}<span class="muted">（${esc(x[2])}）</span></a>`).join('、')}</div>` : ''}
       ${W.length ? '' : '<div class="muted small">無</div>'}
       <div class="muted small">依注意款別推算（第一款連 3 日，或第 1～8 款連 5 日、10 日內 6 次、30 日內 12 次）；是否處置以官方公告為準</div></div>`;
 }
@@ -552,7 +576,7 @@
   const legend = $('#fLegend');
   const show = i => {
     const ch = F.ch[i], c = cls(ch), p = ch != null && F.c[i] !== ch ? ch / (F.c[i] - ch) * 100 : null;
-    const ma = (label, v, color) => v == null ? '' : `<span style="color:${color}">${label} <b style="color:${color}">${fmt(v)}</b></span>`;
+    const ma = (label, v, color) => v == null ? '' : `<span class="lg"><i style="background:${color}"></i>${label} <b>${fmt(v)}</b></span>`;   // D27-06：線色只放在色塊，數字用正文色
     legend.innerHTML = `<span><b>${T[i]}</b></span><span>開 <b>${fmt(F.o[i])}</b></span><span>高 <b class="up">${fmt(F.h[i])}</b></span>` +
       `<span>低 <b class="dn">${fmt(F.l[i])}</b></span><span>收 <b class="${c}">${fmt(F.c[i])}</b></span>` +
       `<span class="${c}">${sgn(ch, 0)} (${sgn(p)}%)</span><span>量 <b>${fmt(F.v[i])}</b></span>` +
@@ -652,7 +676,7 @@
   const focus = localStore('focus', '');
   $('#view').innerHTML = `
     <section class="sec">
-      <div class="sec-h"><h2>板塊資金泡泡圖</h2><span class="muted small">X：近 5 日法人淨流入　Y：比 20 日平均加速或放緩　大小：成交額　顏色：漲跌幅</span>
+      <div class="sec-h"><h2>板塊資金泡泡圖</h2><span class="muted small">X：近 5 日法人淨流入　Y：近 5 日日均比 20 日日均偏流入或偏流出　大小：成交額　顏色：漲跌幅</span>
         <span class="sp"></span>${groupSeg()}</div>
       <div class="card" style="padding:6px"><div id="bubble"></div></div>
     </section>
@@ -703,7 +727,7 @@
     const px = xs.map(x => M.l + (x + limX) / (2 * limX) * plotW);
     const py = ys.map(y => M.t + (limY - y) / (2 * limY) * plotH);
     const hit = (a, b) => a[0] < b[2] && b[0] < a[2] && a[1] < b[3] && b[1] < a[3];
-    const placed = [], text = gs.map(() => ''), font = d.map(v => Math.max(8, Math.min(14, v * 0.2)));
+    const placed = [], text = gs.map(() => ''), font = d.map(v => Math.max(10, Math.min(14, v * 0.2)));   // D27-04：最小 10px
     [...gs.keys()].sort((a, b) => d[b] - d[a]).forEach(i => {
       const f = font[i], room = d[i] - 6;
       let name = gs[i].name;
@@ -734,13 +758,13 @@
       text: lab.text, textposition: 'middle center',
       customdata: gs.map(g => [g.name, ...g.frames[k]]),
       textfont: { size: lab.font, color: '#fff' },
-      hovertemplate: '<b>%{customdata[0]}</b><br>近5日 %{customdata[1]:+.1f}億<br>加速度 %{customdata[2]:+.1f}億/天<br>漲跌 %{customdata[3]:+.2f}%<br>成交 %{customdata[4]:,.0f}億<extra></extra>',
+      hovertemplate: '<b>%{customdata[0]}</b><br>近5日 %{customdata[1]:+.1f}億<br>5日日均−20日日均 %{customdata[2]:+.1f}億/天<br>漲跌 %{customdata[3]:+.2f}%<br>成交 %{customdata[4]:,.0f}億<extra></extra>',
       marker: {
         size: d, sizemode: 'diameter',
         color: gs.map(g => g.frames[k][2]), cmin: -4, cmax: 4,
         // 色彩壓深，白字才看得清楚
         colorscale: [[0, '#17804a'], [0.5, '#5d636b'], [1, '#c23b3b']],
-        line: { width: 1, color: 'rgba(255,255,255,.45)' }, opacity: .82,
+        line: { width: 1, color: 'rgba(255,255,255,.45)' }, opacity: isDark() ? .82 : 1,   // D27-04：淺色底不透明，白字對比 ≥ 4.5
       },
     };
   };
@@ -759,7 +783,7 @@
     paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)', font: { color: text },
     margin: M, showlegend: false, hovermode: 'closest', dragmode: false,
     xaxis: axis(ticksX, limX, '← 流出　近 5 日法人累計（億）　流入 →', ''),
-    yaxis: axis(ticksY, limY, '↓ 放緩　　加速 ↑', ''),
+    yaxis: axis(ticksY, limY, '↓ 偏流出　近 5 日日均 − 20 日日均（億/天）　偏流入 ↑', ''),   // 第 27 輪 D27-04：左右兩半都成立（原「加速／放緩」在淨流出那半邊意思相反）
     shapes: [quad(0, limX, 0, limY, css('--q-rise')), quad(0, limX, -limY, 0, css('--q-rot')),
              quad(-limX, 0, 0, limY, css('--q-watch')), quad(-limX, 0, -limY, 0, css('--q-ebb'))],
     annotations: [qLabel(limX * .88, limY * .9, '漲潮', css('--up')), qLabel(limX * .88, -limY * .9, '輪動', css('--amber')),
@@ -785,7 +809,7 @@
     gd.on('plotly_click', ev => {
       const name = ev.points[0]?.customdata?.[0];
       const g = groups.find(x => x.name === name);
-      if (g) { localStore('focus', null, name); showGroup(g); }
+      if (g) { localStore('focus', null, name); showGroup(g); if (narrow) $('#gTitle').closest('.card').scrollIntoView(); }   // D27-04：手機點了捲到明細
     });
   });
 }
@@ -851,12 +875,14 @@
 
 async function renderRank(arg) {
   // 第 8 輪：#/rank/{排行代號}（例如信用交易卡的 #/rank/s-）→ 記住排行後把網址改回 #/rank
-  if (arg && RANKS.some(r => r[0] === arg)) localStore('rank2', null, arg);   // 第 25 輪 D25-08：網址保留排行代號（可分享）
+  // 第 25 輪 D25-08：網址保留排行代號（可分享）。第 27 輪 D27-05：#/rank 沒帶代號時開法人買超，同一次瀏覽中才回到上次的排行
+  localStore('rank2', null, App.rank2 = RANKS.some(r => r[0] === arg) ? arg : App.rank2 || 'n+');
   const S = await loadScreen();
   const avail = RANKS.filter(r => !r[4] || S);          // screen.json 不存在時，需要它的排行不出現
   const by0 = localStore('rank2', 'n+'), mkt = localStore('mkt', 'all'), span = localStore('rspan', '1');
   const minTv = localStore('rtv', '0.5');   // 成交額門檻（億），套用到所有排行
   const [by, , f, dir, src] = avail.find(r => r[0] === by0) || RANKS[0];
+  if (arg !== by) history.replaceState(null, '', '#/rank/' + by);   // D27-05：網址補成實際顯示的排行
   const unit = localStore('munit', 'amt'), byAmt = (by === 'm+' || by === 'm-') && unit === 'amt';
   const field = (byAmt ? 'ma*' : f).replace('*', span);
   let table, foot = '';
@@ -956,9 +982,10 @@
         : !list.length ? '<div class="empty">目前沒有符合的股票。</div>'
         : `<div class="tbl-wrap"><table class="tbl"><thead><tr><th>股票</th><th>面向</th><th class="hl-th">近期新訊號</th><th>收盤</th><th>漲跌</th><th>20日均額</th></tr></thead><tbody>` +
           list.map(([x, n]) => `<tr data-code="${x.code}">
-            <td class="nm"><b>${esc(x.n)}</b>${alertBadge(x)}<span>${x.code} ${esc(x.i)}</span><div class="hl-sub">${x.hl.map(hlTag).join('')}</div></td>
+            <td class="nm"><b>${esc(x.n)}</b>${alertBadge(x)}<span>${x.code} ${esc(x.i)}</span></td>
             <td class="num">${n}</td><td class="hl-tags">${x.hl.map(hlTag).join('')}</td>
-            <td class="num ${cls(x.p)}">${pfmt(x.c)}</td>${pctCell(x)}<td class="num">${fmt(x.a20, 1)}億</td></tr>`).join('') + '</tbody></table></div>'}</div>
+            <td class="num ${cls(x.p)}">${pfmt(x.c)}</td>${pctCell(x)}<td class="num">${fmt(x.a20, 1)}億</td></tr>
+            <tr class="hl-sub" data-code="${x.code}"><td colspan="6">${x.hl.map(hlTag).join('')}</td></tr>`).join('') + '</tbody></table></div>'}</div>
       <div class="muted small" style="margin-top:6px">列出最近 5 個交易日（營收、EPS 為最近 20 個交易日）在價量、法人、基本面（營收、EPS）、主動 ETF 四個面向新出現的事件；同一面向有多個事件只算 1 個面向。
         「新出現」= 當天符合、前一個交易日不符合，口徑和選股條件相同；60 日新高帶量 = 創 60 日以上新高且量比 ≥ 1.5；營收創新高 = 單月營收創新高且年增 ≥ 30%；
         EPS 只看全市場最新一季的單季 EPS：轉盈 = 去年同季 ≤ 0、本季 > 0，年增 ≥ 50% 不含去年同季 < 0.1 元（基期低）。
@@ -1221,6 +1248,10 @@
     const condHTML = c => { const [pre, post = ''] = c.label.split('{v}');
       return `<label class="scr-c"${c.title ? ` title="${c.title}"` : ''}><input type="checkbox" data-c="${c.id}"${c.id in st ? ' checked' : ''}>${pre}${ctl(c)}${post}` +
         `<span class="scr-n">${c.g === '排除' ? '排除' : '單獨'} ${fmt(cnt(c))}</span></label>`; };
+    // 第 27 輪 D27-03：條件與排除分開計數；收合時列出已選條件（可按 ✕ 移除）
+    const nx = conds.filter(c => c.g === '排除').length, cTxt = c => { const v = st[c.id], o = Array.isArray(c.opts) && c.opts.find(x => Array.isArray(x) && x[0] === v);
+      return c.label.replace('{v}', o ? o[1] : v.toLocaleString('zh-TW')); };
+    const tags = conds.filter(c => c.g !== '排除').map(c => `<button class="chip" data-x="${c.id}" aria-label="移除條件">${cTxt(c)} ✕</button>`).join('');
     const chip = ([id, name], ref) => `<button class="chip${ref ? ' ref' : ''}${st.ps === id ? ' on' : ''}" data-ps="${id}"${ref ? ' title="風險檢查，不是買進訊號"' : ''}>${name}</button>`;
     $('#view').innerHTML = `<section class="sec">
       <div class="sec-h">${modeSeg('screen')}</div>
@@ -1228,12 +1259,12 @@
       <div style="margin-top:8px">${notes}</div>
       <div class="sec-h" style="margin:8px 0 0;gap:6px"><span class="muted small">預設：</span>${SCREEN_PRESETS.filter(p => p[0][0] !== 'r').map(p => chip(p)).join('')}
         <span class="muted small">參考：</span>${SCREEN_PRESETS.filter(p => p[0][0] === 'r').map(p => chip(p, true)).join('')}</div>
-      <details class="scr-panel card"${open ? ' open' : ''}><summary>條件（已選 ${conds.length} 個）
-        <button class="chip" id="scrClear">重設</button> <button class="chip" id="scrCopy">複製條件連結</button></summary>
+      <details class="scr-panel card"${open ? ' open' : ''}><summary>條件 ${conds.length - nx} 個${nx ? `＋排除 ${nx} 個` : ''}
+        <button class="chip scr-go" id="scrGo">符合 ${fmt(hits.length)} 檔 ↓</button> <button class="chip" id="scrClear">重設</button> <button class="chip" id="scrCopy">複製條件連結</button>${tags ? `<div class="scr-tags">${tags}</div>` : ''}</summary>
         ${SCREEN_GROUPS.map(g => `<div class="scr-grp"><b>${g}</b><div>${SCREEN_CONDS.filter(c => c.g === g).map(condHTML).join('')}</div></div>`).join('')}
       </details>
       ${oscShare(conds, X, cnt, st)}
-      <div class="sec-h" style="margin:8px 0"><h2>符合 ${fmt(hits.length)} 檔</h2>${hits.length > 100 ? `<span class="muted small">依「${oName}」排序顯示前 100 檔</span>` : ''}</div>
+      <div class="sec-h" id="scrRes" style="margin:8px 0"><h2>符合 ${fmt(hits.length)} 檔</h2>${hits.length > 100 ? `<span class="muted small">依「${oName}」排序顯示前 100 檔</span>` : ''}</div>
       <div class="card">${hits.length ? screenTable(hits.slice(0, 100), cols, { sort: o, cap: conds.some(c => c.val) })
         : '<div class="empty">沒有同時符合所有條件的股票。參考各條件的「單獨」檔數，放寬最少的那一個。</div>'}</div>
       <div class="muted small" style="margin-top:6px">篩選結果只是條件的機械比對，不是投資建議。報酬、乖離、均線、新高新低、KD、RSI 都用還原價格（除權息、減資、面額變更不會造成跳動）；量比 = 今日成交額 ÷ 前 20 個交易日平均（無成交日以 0 計），不受面額變更影響。法人金額為張數 × 收盤估算，不含 ETF；投信買超會受主動 ETF 申購影響（申購的資金會被動買進股票，個股頁「主動 ETF 持有」卡列出已收主動 ETF 占投信買超的張數）。本益比、殖利率、淨值比為官方值，90 天內有除權、減資或面額變更的股票官方值可能尚未調整，預設排除。營收條件以各股最新公布的月份判斷：每月 1～10 日是公布期間，已公布的公司當天就換成新月份，各股月份不同（營收欄會標出和欄名不同的月份）。季報條件以各股最新一季判斷：單季 EPS 由累計相減，去年同季虧損時不計算年增，金融業沒有毛利率；財報公布期間各股季別不同（欄位會標出和欄名不同的季別）。融資融券為張；融資增加率、券資比只計入融資 1,000 張以上的股票。</div></section>`;
@@ -1263,6 +1294,8 @@
     }));
     const det = $('#view details.scr-panel');
     det.addEventListener('toggle', () => { open = det.open; });
+    $('#scrGo').addEventListener('click', e => { e.preventDefault(); $('#scrRes').scrollIntoView(); });
+    $('#view').querySelectorAll('[data-x]').forEach(b => b.addEventListener('click', e => { e.preventDefault(); delete st[b.dataset.x]; changed(); }));
     $('#scrClear').addEventListener('click', e => { e.preventDefault(); st = { ...SCREEN_DEFAULT }; save(); draw(); });   // P23：回到預設（保留共同排除）
     $('#scrCopy').addEventListener('click', e => {
       e.preventDefault();
@@ -1350,7 +1383,8 @@
   const tbl = (t, list) => `<div class="card"><div class="sec-h"><h2>${t}</h2><span class="muted small">億，估算</span></div>
     <div class="tbl-wrap"><table class="tbl"><thead><tr><th>股票</th><th>估算金額</th><th>張數</th></tr></thead><tbody>${actRows(list.slice(0, 5)) ||
     '<tr><td colspan="3" class="muted">無</td></tr>'}</tbody></table></div></div>`;
-  return `<section class="sec"><div class="sec-h"><h2>${actTitle(R)}主動 ETF 一起買了什麼</h2><span class="muted small">${R.etfs.length} 檔合計</span>
+  const top = R.etfs.map(x => x.d).sort().pop(), old = R.etfs.filter(x => x.d !== top);   // 第 27 輪 D27-10：各檔持股日可能不同
+  return `<section class="sec"><div class="sec-h"><h2>${actTitle(R)}主動 ETF 一起買了什麼</h2><span class="muted small">${R.etfs.length} 檔合計，持股日 ${md(top)}${old.length ? `（${old.length} 檔 ${[...new Set(old.map(x => md(x.d)))].join('、')}）` : ''}</span>
       <span class="sp"></span><a class="muted small" href="#/etf/active">完整排行 →</a></div>
     <div style="margin:-6px 0 10px">${unitsLine(App.latest)}</div>
     <div class="grid g2">${tbl('主動 ETF 合計加碼', R.buy)}${tbl('主動 ETF 合計減碼', R.sell)}</div></section>`;
@@ -1425,14 +1459,17 @@
       ${App.watchUndo ? `<div class="flow-note">已從自選移除 ${esc(App.watchUndo.filter(c => !App.watch.has(c)).map(c => (S[c] || R[c])?.n || c).join('、'))}　<button class="chip" id="watchUndo">復原</button></div>` : ''}
       <div class="sec-h">${stk ? '<h2>自選</h2>' : '<h2>自選 ETF</h2>'}<span class="muted small">存在這個瀏覽器裡，換裝置不會同步${stk ? '' : '。當日行情；成交量為張、成交額為億元'}</span><span class="sp"></span>${stk ? spanSeg(span) : ''}${list.length || etfs.length ? `<button class="chip" id="watchEdit">${App.watchEdit ? '完成' : '編輯'}</button>` : ''}</div>
       ${stk ? `<div class="card">${list.length ? stockTable(list, span, true)
-        : '<div class="empty">還沒有自選股。打開任一檔個股或 ETF，按名稱旁的「☆ 加入自選」。</div>'}</div>` : ''}
-      ${ev.length ? `<div class="card w-ev"><div class="sec-h"><h2>近期新訊號、處置／注意</h2><span class="muted small">只描述發生了什麼，不代表之後的走勢</span></div>${ev.map(([c, s]) =>
-        `<a class="al-row" href="#/stock/${c}"><b>${esc(s.n)}</b>${alertBadge(s)}　${s.hl ? s.hl.filter(e => HL_KINDS[e[0]]).map(hlTag).join('') : ''}</a>`).join('')}</div>` : ''}
+        : '<div class="empty">還沒有自選股。打開任一檔個股或 ETF，按名稱旁的「☆ 加入自選」；或在上方搜尋，按清單右側的 ☆ 直接加入。<div style="margin-top:10px"><button class="chip" id="watchFind">搜尋股票</button></div></div>'}</div>` : ''}
       ${etfs.length ? `${stk ? '<div class="sec-h" style="margin-top:12px"><h2>ETF</h2><span class="muted small">當日行情；成交量為張、成交額為億元</span></div>' : ''}
       <div class="card">${etfWatchTable(etfs)}</div>` : ''}
+      ${ev.length ? `<div class="card w-ev"><div class="sec-h"><h2>近期新訊號、處置／注意</h2><span class="muted small">只描述發生了什麼，不代表之後的走勢</span></div>${ev.map(([c, s]) => {
+        const d = s.dsp, r = s.ntc && App.latest.alerts?.n?.find(x => x[0] === c)?.[1];   // 第 27 輪 D27-08：處置期間（最後一天加註）、注意原因
+        return `<a class="al-row" href="#/stock/${c}"><b>${esc(s.n)}</b>${alertBadge(s)}${d ? `　<span class="small num">${d[0] > App.latest.date ? '即將處置' : '處置'} ${md(d[0])}～${md(d[1])}${d[1] === App.latest.date ? '（最後一天）' : ''}</span>` : ''}` +
+          `　${s.hl ? s.hl.filter(e => HL_KINDS[e[0]]).map(hlTag).join('') : ''}${r ? `<div class="muted small al-why">注意：${esc(r)}</div>` : ''}</a>`; }).join('')}</div>` : ''}
       ${list.length || etfs.length ? '<div class="muted small w-tip">按「✕」從自選移除；按住「≡」上下拖曳調整順序（也可按上下鍵）。完成後按「完成」</div>' : ''}</section>`;
   if (stk) onSeg('rspanSeg', v => { localStore('rspan', null, v); renderWatch(); });
   watchGestures($('#view .watch'));
+  $('#watchFind')?.addEventListener('click', () => $('#q').focus());
   $('#view').addEventListener('click', onRowClick);
   $('#view').addEventListener('click', onEtfRow);
 }
@@ -1464,22 +1501,30 @@
   };
   sec.querySelectorAll('.wh').forEach(h => {
     const tr = h.closest('tr'), tb = tr.parentElement;
-    let y0 = 0, top0 = 0;
+    let y0 = 0, top0 = 0, cy = 0, raf = 0;   // y0 用頁面座標（含捲動量）：拖到邊緣自動捲動時，列仍跟著手指
+    const move = () => {
+      const c = top0 + cy + scrollY - y0 + tr.offsetHeight / 2, mid = r => r.offsetTop + r.offsetHeight / 2;
+      let s;            // 搬動相鄰列、不搬被拖的列（被拖的列離開 DOM 會失去 pointer capture）；一次移動很遠時連跳多列
+      while ((s = tr.previousElementSibling) && c < mid(s)) flip(s, () => tr.after(s));
+      while ((s = tr.nextElementSibling) && c > mid(s)) flip(s, () => tr.before(s));
+      tr.style.setProperty('--dy', `${top0 + cy + scrollY - y0 - tr.offsetTop}px`);   // 被拖的列跟著手指走
+    };
+    // 第 27 輪 D27-09：手指在畫面上下 90px 內時自動捲動（底部有選單、頂部有頂欄）
+    const edge = () => { const v = cy < 90 ? -10 : cy > innerHeight - 90 ? 10 : 0;
+      raf = v && tr.classList.contains('dragging') ? (scrollBy(0, v), move(), requestAnimationFrame(edge)) : 0; };
     h.addEventListener('pointerdown', e => {
       e.preventDefault(); h.setPointerCapture(e.pointerId);
-      y0 = e.clientY; top0 = tr.offsetTop;
+      cy = e.clientY; y0 = cy + scrollY; top0 = tr.offsetTop;
       tr.classList.add('dragging');
     });
     h.addEventListener('pointermove', e => {
       if (!tr.classList.contains('dragging')) return;
-      const c = top0 + e.clientY - y0 + tr.offsetHeight / 2, mid = r => r.offsetTop + r.offsetHeight / 2;
-      let s;            // 搬動相鄰列、不搬被拖的列（被拖的列離開 DOM 會失去 pointer capture）；一次移動很遠時連跳多列
-      while ((s = tr.previousElementSibling) && c < mid(s)) flip(s, () => tr.after(s));
-      while ((s = tr.nextElementSibling) && c > mid(s)) flip(s, () => tr.before(s));
-      tr.style.setProperty('--dy', `${top0 + e.clientY - y0 - tr.offsetTop}px`);   // 被拖的列跟著手指走
+      cy = e.clientY; move();
+      if (!raf) edge();
     });
     const end = () => {
       if (!tr.classList.contains('dragging')) return;
+      cancelAnimationFrame(raf); raf = 0;
       const d = parseFloat(tr.style.getPropertyValue('--dy')) || 0;
       tr.classList.remove('dragging'); tr.style.removeProperty('--dy');
       if (d) tr.querySelectorAll('td').forEach(td => td.animate?.([{ transform: `translateY(${d}px)` }, { transform: 'none' }], { duration: 160, easing: 'ease-out' }));   // 放開後落回定位
@@ -1534,8 +1579,8 @@
 }
 function renderStatus() {
   const L = App.latest, when = (L.updated_at || '').slice(0, 16).replace('T', ' ');
-  $('#dateBar').innerHTML = `<span class="nw">資料日 ${esc(L.date)}</span>　<span class="nw">法人資料 ${esc(L.flow_date)}</span>　<span class="nw">更新於 ${esc(when)}` +
-    (L.status?.collected_src === 'db' ? '（依資料寫入時間）' : '') + '</span>';   // 第 13 輪 F13-5：每段不在中間斷行
+  $('#dateBar').innerHTML = `<span class="nw">資料日 ${esc(L.date)}</span><span class="nw${L.flow_date === L.date ? ' fd-eq' : ''}">　法人資料 ${esc(L.flow_date)}</span>　<span class="nw">更新於 ${esc(when)}` +
+    (L.status?.collected_src === 'db' ? '（依資料寫入時間）' : '') + '</span>';   // 第 13 輪 F13-5：每段不在中間斷行；D27-10 手機上法人資料日和資料日相同時不重複（.fd-eq）
   const lines = freshLines(L, App.now()).map(x => `<div>${esc(x)}</div>`);
   if (App.newDate) lines.push(`<div>網站資料已更新（資料日 ${md(App.newDate)}）<button id="reloadBtn">重新整理</button></div>`);
   const bar = $('#freshBar');
@@ -1599,6 +1644,10 @@
     return;
   }
   renderStatus();
+  // 第 27 輪：頂欄高度給固定表頭、選股條件列（--top-h）；畫面重畫、捲動、改變大小時重算表頭位置（D27-01）
+  const topH = () => { document.documentElement.style.setProperty('--top-h', $('.top').offsetHeight + 'px'); stickHeads(); };
+  topH(); addEventListener('resize', topH); addEventListener('scroll', stickHeads, { passive: true });
+  new MutationObserver(stickHeads).observe($('#view'), { childList: true });
   document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible') recheckLatest(); });
   window.addEventListener('hashchange', route);
   route();
diff -ruN -x data orig/site/index.html proj/site/index.html
--- orig/site/index.html	2026-11-15 10:50:09
+++ proj/site/index.html	2026-11-15 15:40:02
@@ -7,11 +7,11 @@
 <meta name="description" content="台股類股與概念股的三大法人資金流向、個股 K 線與籌碼">
 <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><circle cx='11' cy='19' r='8' fill='%23d64545'/><circle cx='22' cy='12' r='6' fill='%23e8a33d'/><circle cx='23' cy='24' r='4' fill='%2330a46c'/></svg>">
 <script>try{var t=localStorage.getItem('tw.theme');if(t==='light'||t==='dark')document.documentElement.dataset.theme=t}catch(e){}</script>
-<link rel="stylesheet" href="app.css?v=56df32ca">
+<link rel="stylesheet" href="app.css?v=39f292f5">
 <script src="https://cdn.jsdelivr.net/npm/plotly.js-basic-dist-min@2.35.2/plotly-basic.min.js" defer></script>
 <script src="https://cdn.jsdelivr.net/npm/lightweight-charts@4.2.0/dist/lightweight-charts.standalone.production.js" defer></script>
-<script src="app.js?v=f9b7833d" defer></script>
-<script src="stock.js?v=eb734b38" defer></script>
+<script src="app.js?v=62040b25" defer></script>
+<script src="stock.js?v=51cc333a" defer></script>
 </head>
 <body>
 <header class="top">
diff -ruN -x data orig/site/stock.js proj/site/stock.js
--- orig/site/stock.js	2026-11-15 00:08:19
+++ proj/site/stock.js	2026-11-15 15:36:54
@@ -53,6 +53,8 @@
   '上櫃 ETF：官方漲跌就是收盤減前一日收盤，除息日的漲跌含除息的跌幅，本站無法辨識除息日，不標示。'); };
 
 // 第 25 輪 D25-05：產業鏈、概念股標籤只顯示前 2 個，其餘收在「+N」（點了展開，展開後按「收合」收回）
+// 第 27 輪 D27-07：融資融券子圖一次只畫一條線（右側刻度就是這條線）；借券只在有資料時可選
+const mgView = G => { const v = localStore('mgv', 'mb'); return v === 'sb' || (v === 'lb' && G?.lb) ? v : 'mb'; };
 const tagFold = t => t.slice(0, 2).join('') + (t.length > 2 ? `<span class="tag-rest" hidden>${t.slice(2).join('')}</span><button class="pill more" id="tagMore" data-n="+${t.length - 2}">+${t.length - 2}</button>` : '');
 
 window.renderStock = async function (code, sub) {
@@ -62,6 +64,7 @@
   try { data = await loadStock(code, E ? 'etfp' : 'stocks'); }
   catch (e) { $('#view').innerHTML = `<div class="empty">找不到 ${esc(code)} 的資料。可用上方搜尋框查代號或名稱，或<a href="#/today" style="color:var(--blue)">回今日</a></div>`; return; }
   const P = data.prices, n = P.d.length;
+  document.title = `${data.name} ${code}｜台股資金流`;   // 第 27 輪 D27-10
   const last = n - 1;
   // 最新一天沒成交（開高低收為 --）時，改顯示最後成交日的收盤，不算漲跌
   const traded = P.c.map((c, i) => c != null ? i : -1).filter(i => i >= 0);
@@ -196,7 +199,7 @@
       <div id="vC" class="chart-box" style="height:80px"></div>
       ${E ? '' : `<div class="ch-label">三大法人買賣超（張，未還原）<span id="iLegend" style="display:contents"></span></div>
       <div id="iC" class="chart-box" style="height:90px"></div>`}
-      ${data.mg ? `<div class="ch-label">融資／融券${data.mg.lb ? '／借券賣出' : ''}餘額<span id="gUnit"></span><span id="gLegend" style="display:contents"></span></div>
+      ${data.mg ? `<div class="ch-label">${segHTML('mgSeg', [['mb', '融資'], ['sb', '融券'], ...data.mg.lb ? [['lb', '借券賣出']] : []], mgView(data.mg))}餘額<span id="gUnit"></span><span id="gLegend" style="display:contents"></span></div>
       <div id="gC" class="chart-box" style="height:90px"></div>` : ''}
       <div class="ch-label">${E ? '' : segHTML('oscSeg', OSC_OPTS, localStore('osc', 'MACD'))}<span id="oscLeg" style="display:contents"></span></div>
       <div id="mC" class="chart-box" style="height:120px"></div>
@@ -217,7 +220,7 @@
   if (tab === 'fund') { renderRevenue(data.revenue); if (F) renderFin(F); }
   if (tab !== 'k') return;
   // 第 25 輪 D25-05：關鍵數字列在寬螢幕併進頁首卡、手機放到 K 線卡下方，主圖進第一屏
-  if (matchMedia('(min-width:721px)').matches) $('#view .s-head').after($('#view .metrics.kv')); else $('#kC').closest('section').after($('#view .metrics.kv'));
+  if (matchMedia('(min-width:721px)').matches) $('#view .s-head').after($('#view .metrics.kv')); else $('#kC').after($('#view .metrics.kv'));   // 第 27 輪 D27-06：手機放在 K 線正下方（原本在 4 張子圖之後）
   if (!E) $('#adjSeg').title = '還原：依除權息、減資、面額變更調整歷史價格（現金增資除權也依官方參考價調整），最新收盤不變。均線訊號與 52 週高低一律以還原價格計算';
   // 日／週／月與還原／原始切換都重畫；技術面訊號一律用還原價（P13）
   const draw = () => {
@@ -226,6 +229,7 @@
     if (!E) renderSignals(aggregate(data, m, true), m);
   };
   onSeg('kSeg', m => { localStore('kmode', null, m); document.querySelectorAll('#kSeg button').forEach(b => b.classList.toggle('on', b.dataset.v === m)); draw(); });
+  if (data.mg) onSeg('mgSeg', v => { localStore('mgv', null, v); document.querySelectorAll('#mgSeg button').forEach(b => b.classList.toggle('on', b.dataset.v === v)); draw(); });
   if (!E) onSeg('oscSeg', v => { localStore('osc', null, v); document.querySelectorAll('#oscSeg button').forEach(b => b.classList.toggle('on', b.dataset.v === v)); draw(); });
   if (!E) onSeg('adjSeg', v => { localStore('kadj', null, v); document.querySelectorAll('#adjSeg button').forEach(b => b.classList.toggle('on', b.dataset.v === v)); draw(); });
   $('#latestBtn').addEventListener('click', () => { syncLeader = charts[0]; charts[0]?.timeScale().scrollToRealTime(); });
@@ -386,7 +390,11 @@
   };
 
   const kc = mk('kC', false, true);   // 圖表庫授權要求的 TradingView 標示，主圖保留一個
-  const kSer = kc.addCandlestickSeries({ upColor: UP, downColor: DN, borderUpColor: UP, borderDownColor: DN, wickUpColor: UP, wickDownColor: DN, priceFormat: priceFmt });
+  const kSer = kc.addCandlestickSeries({ upColor: UP, downColor: DN, borderUpColor: UP, borderDownColor: DN, wickUpColor: UP, wickDownColor: DN, priceFormat: priceFmt,
+    lastValueVisible: false, priceLineVisible: false });
+  // 第 27 輪 D27-06：最新價標籤依漲跌（日線 = 收盤對昨收，和頁首同色；週／月線 = 對上一根）上色，不依 K 棒（收盤對開盤）
+  const [lastCh] = barChange(raw, raw.length - 1, mode, adj);
+  kSer.createPriceLine({ price: C[C.length - 1], color: NT[NT.length - 1] || !lastCh ? FLAT : lastCh > 0 ? UP : DN, lineWidth: 1, lineStyle: 2, axisLabelVisible: true, axisLabelTextColor: css('--on-fill'), title: '' });
   // 無成交的一字線用灰色
   kSer.setData(raw.map((r, i) => ({ time: T[i], open: O[i], high: H[i], low: L[i], close: C[i],
     ...(NT[i] ? { color: FLAT, borderColor: FLAT, wickColor: FLAT } : {}) })));
@@ -417,27 +425,18 @@
     }
   }
 
-  // F8-3：融資（右軸）／融券（疊加軸、不顯示刻度）餘額；第 11 輪 B14：借券賣出（第三個疊加軸，不顯示刻度）
-  // 三條線各自一個座標軸：借券常是融券的上百倍，同軸會把融券壓平
+  // F8-3：融資融券餘額；第 11 輪 B14：借券賣出。第 27 輪 D27-07：一次一條線、用自己的右側刻度（原本三條線各自縮放、只有融資有刻度，量級差很多時會看反）
   const MB = raw.map(r => r.mb), SB = raw.map(r => r.sb), LB = raw.map(r => r.lb);
-  let gc = null, mbSer = null;
+  let gc = null, mbSer = null, GV = null;
   if (G && $('#gC')) {
     gc = mk('gC', false);
-    mbSer = gc.addLineSeries({ color: '#1C7ED6', lineWidth: 1, priceFormat: { type: 'volume' }, priceLineVisible: false, lastValueVisible: false });
-    mbSer.setData(MB.map((v, i) => v == null ? { time: T[i] } : { time: T[i], value: v }));
-    const sbSer = gc.addLineSeries({ color: '#AE3EC9', lineWidth: 1, priceScaleId: 'sb', priceFormat: { type: 'volume' }, priceLineVisible: false, lastValueVisible: false });
-    gc.priceScale('sb').applyOptions({ scaleMargins: { top: 0.1, bottom: 0.1 } });
-    sbSer.setData(SB.map((v, i) => v == null ? { time: T[i] } : { time: T[i], value: v }));
-    if (G.lb) {
-      const lbSer = gc.addLineSeries({ color: '#E8590C', lineWidth: 1, lineStyle: 2, priceScaleId: 'lb', priceFormat: { type: 'volume' }, priceLineVisible: false, lastValueVisible: false });
-      gc.priceScale('lb').applyOptions({ scaleMargins: { top: 0.1, bottom: 0.1 } });
-      lbSer.setData(LB.map((v, i) => v == null ? { time: T[i] } : { time: T[i], value: v }));
-    }
+    GV = { mb: [MB, '#1C7ED6'], sb: [SB, '#AE3EC9'], lb: [LB, '#E8590C'] }[mgView(G)];
+    mbSer = gc.addLineSeries({ color: GV[1], lineWidth: 1, priceFormat: { type: 'volume' }, priceLineVisible: false, lastValueVisible: false });
+    mbSer.setData(GV[0].map((v, i) => v == null ? { time: T[i] } : { time: T[i], value: v }));
     // 換算事件標在包含該日期的那一根（T 中 ≤ 事件日的最後一根）
     mbSer.setMarkers((G.k || []).map(x => { let j = -1; T.forEach((t, i) => { if (t <= x.d) j = i; }); return [j, x]; }).filter(([j]) => j >= 0)
       .sort((a, b) => a[0] - b[0]).map(([j, x]) => ({ time: T[j], position: 'aboveBar', shape: 'circle', color: css('--blue'), text: EV_LABEL[x.t] + (adj ? ' 已換算' : '') })));
-    $('#gUnit').textContent = (adj ? '（張；面額變更、減資前的餘額依官方換算）' : '（張，官方原始）') +
-      '　右側刻度只適用融資；融券、借券各自縮放，數值看圖例';     // 第 12 輪 P26
+    $('#gUnit').textContent = adj ? '（張；面額變更、減資前的餘額依官方換算）' : '（張，官方原始）';     // 第 12 輪 P26；D27-07 刻度即所選的線
   }
 
   const mc = mk('mC', true);
@@ -473,14 +472,14 @@
   }));
 
   // 十字線同步 + 上方資訊列
-  const anchors = [[kc, kSer, i => C[i]], [vc, vSer, i => V[i]], ...(ic ? [[ic, iSer, i => N[i]]] : []), ...(gc ? [[gc, mbSer, i => MB[i]]] : []), [mc, oSer, oVal]];
+  const anchors = [[kc, kSer, i => C[i]], [vc, vSer, i => V[i]], ...(ic ? [[ic, iSer, i => N[i]]] : []), ...(gc ? [[gc, mbSer, i => GV[0][i]]] : []), [mc, oSer, oVal]];
   const legend = $('#kLegend');
   const showLegend = i => {
     // 日線用匯出的漲跌（事件日相對參考價、前一日無成交相對最後成交）；找不到事件的不比價日為 null。週／月線用前一根收盤
     // 第 15 輪 QA-01：週／月線含推測價格調整（gx）的那一根不用原始價相減，改寫「不比價」，避免除息、分割被讀成下跌
     const gxBar = mode !== '日' && raw[i].gx, [chg, p, f] = barChange(raw, i, mode, adj);
     const c = cls(chg);
-    const ma = (label, v, color) => v == null ? '' : `<span style="color:${color}">${label} <b style="color:${color}">${pfmt(v)}</b></span>`;
+    const ma = (label, v, color) => v == null ? '' : `<span class="lg"><i style="background:${color}"></i>${label} <b>${pfmt(v)}</b></span>`;   // D27-06：線色只放在色塊，數字用正文色（淺色 MA20 原本 2.17）
     legend.innerHTML = `<span><b>${mode === '月' ? T[i].slice(0, 7) + ' 月' : mode === '週' ? T[i] + ' 當週' : T[i]}</b></span><span>開 <b>${pfmt(O[i])}</b></span><span>高 <b class="up">${pfmt(H[i])}</b></span>` +
       `<span>低 <b class="dn">${pfmt(L[i])}</b></span><span>收 <b class="${c}">${pfmt(C[i])}</b></span>` +
       (NT[i] ? '<span class="flat">無成交</span>'
diff -ruN -x test_iter27.py orig/tests/test_iter11.py proj/tests/test_iter11.py
--- orig/tests/test_iter11.py	2026-11-07 00:56:37
+++ proj/tests/test_iter11.py	2026-11-15 15:27:29
@@ -223,7 +223,7 @@
 # ─── 網站（原始碼檢查）───────────────────────────────────
 def test_f11_site():
     js = (ROOT / "site" / "stock.js").read_text(encoding="utf-8")
-    assert "不等於看空" in js and "priceScaleId: 'lb'" in js and "for (const k of ['mb', 'sb', 'lb'])" in js
+    assert "不等於看空" in js and "lb: [LB, '#E8590C']" in js and "for (const k of ['mb', 'sb', 'lb'])" in js   # 第 27 輪 D27-07：借券改成切換顯示（不再用疊加軸）
     assert "官方本益比以最新股數計算，期間有增資的公司" in js                                            # F11-3 第 1 點
     app = (ROOT / "site" / "app.js").read_text(encoding="utf-8")
     assert "['l+', '借券賣出增加', 'la*', -1, 'l'], ['lp', '借券占股本', 'lp', -1, 'l']" in app
diff -ruN -x test_iter27.py orig/tests/test_iter12.py proj/tests/test_iter12.py
--- orig/tests/test_iter12.py	2026-11-07 23:42:47
+++ proj/tests/test_iter12.py	2026-11-15 15:27:29
@@ -79,7 +79,7 @@
 # ─── 網站（原始碼檢查）───────────────────────────────────
 def test_f12_site():
     js = (ROOT / "site" / "stock.js").read_text(encoding="utf-8")
-    assert "右側刻度只適用融資；融券、借券各自縮放" in js                                                    # F12-1 P26
+    assert "segHTML('mgSeg'" in js and "右側刻度只適用融資" not in js                                       # F12-1 P26；第 27 輪 D27-07 改成一次一條線
     assert "...mtCards]" in js and "...mgCards, ...slCards]" in js and "MT?.mc == null ? '--'" in js        # F12-4（分頁後：市值在走勢、信用在籌碼）
     app = (ROOT / "site" / "app.js").read_text(encoding="utf-8")
     assert "function wpeLine(V)" in app and "${wpeLine(V)}" in app and "不是證交所公布的數字" in app            # F12-2
diff -ruN -x test_iter27.py orig/tests/test_iter17.py proj/tests/test_iter17.py
--- orig/tests/test_iter17.py	2026-11-08 23:25:00
+++ proj/tests/test_iter17.py	2026-11-15 15:27:29
@@ -129,7 +129,7 @@
     assert ".al-near{" in CSS
     src = (ROOT / "twstock" / "export.py").read_text(encoding="utf-8")
     assert 'latest["alerts"]["w"] = alert_watch(watch_notes, watch_days,' in src and "COUNT_DOWN = True" in src
-    assert APP.count("A.w") == 1 and "alerts.w" not in APP  # 只有今日清單用到；選股不加預警條件
+    assert APP.count("A.w") == 2 and "接近處置（推算）${(A.w || []).length}" in APP and "alerts.w" not in APP  # 只有今日清單用到（第 27 輪 D27-08 摘要列加檔數）；選股、自選不加預警條件
 
 
 if __name__ == "__main__":
diff -ruN -x test_iter27.py orig/tests/test_iter23.py proj/tests/test_iter23.py
--- orig/tests/test_iter23.py	2026-11-15 00:34:01
+++ proj/tests/test_iter23.py	2026-11-15 15:27:29
@@ -254,10 +254,10 @@
     assert '<a class="muted small" href="#/rank/${rk}">看排行 →</a>' in APP
     # F23-4a：≤ 480 px 時標籤在名稱格下方、隱藏標籤欄；1024 照舊（hl-sub 不顯示）
     hl = APP[APP.index("async function renderHl()"):APP.index("// ─── 第 8 輪 F8-2")]
-    assert "<span>${x.code} ${esc(x.i)}</span><div class=\"hl-sub\">${x.hl.map(hlTag).join('')}</div></td>" in hl
+    assert "<span>${x.code} ${esc(x.i)}</span></td>" in hl and '<tr class="hl-sub" data-code="${x.code}"><td colspan="6">${x.hl.map(hlTag).join(\'\')}</td></tr>' in hl   # 第 27 輪 D27-02：手機標籤改放第二列
     assert '<td class="hl-tags">${x.hl.map(hlTag).join(\'\')}</td>' in hl
     assert ".hl-sub{display:none}" in CSS
-    assert "@media (max-width:480px){.tbl th.hl-th,.tbl td.hl-tags{display:none}.tbl td.nm .hl-sub{display:block;white-space:normal}" in CSS
+    assert "@media (max-width:480px){.tbl th.hl-th,.tbl td.hl-tags{display:none}.tbl tr.hl-sub{display:table-row}" in CSS
 
 
 def test_watch_etf_only():
```

## 附錄 B：`tests/test_iter27.py` 全文

```python
"""第 27 輪：UI/UX 優化（不連網、不連資料庫）。
長表格改整頁捲動＋表頭跟著頂欄、新訊號手機標籤改第二列、選股條件列固定＋符合檔數捷徑、泡泡圖 Y 軸文案、
#/today、#/rank 預設與網址正規化、個股頁 MA 圖例／最新價標籤／融資融券單一序列、處置摘要與自選事件卡、
搜尋清單 ☆ 直接加入自選、分頁標題。有 node 時逐字取出 app.js／stock.js 的函式執行（node 14 可跑）。"""
import json
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "site" / "app.js").read_text(encoding="utf-8")
STK = (ROOT / "site" / "stock.js").read_text(encoding="utf-8")
CSS = (ROOT / "site" / "app.css").read_text(encoding="utf-8")
AT = "if (!Array.prototype.at) Array.prototype.at = function (i) { return this[i < 0 ? this.length + i : i]; };\n"   # node 14


def _grab(src, name):
    m = re.search(rf"^(?:async )?function {name}\(", src, re.M)
    if m:
        i, n = src.index("{", src.index(")", m.start())), 0
        for j in range(i, len(src)):
            n += {"{": 1, "}": -1}.get(src[j], 0)
            if n == 0:
                return src[m.start():j + 1]
    m = re.search(rf"^const {name}\b", src, re.M)          # const 取到去掉行尾註解後結尾為「;」的那一行
    assert m, name
    lines = src[m.start():].splitlines()
    k = next(i for i, l in enumerate(lines) if re.sub(r"\s+//[^'`]*$", "", l).rstrip().endswith(";"))
    return "\n".join(lines[:k + 1])


def _node(js):
    node = shutil.which("node")
    if not node:
        print("  （沒有 node，略過執行）")
        return None
    return json.loads(subprocess.run([node, "-e", AT + js], capture_output=True, text=True, check=True).stdout)


def _lum(c):
    c = [int(c[i:i + 2], 16) / 255 for i in (1, 3, 5)] if isinstance(c, str) else [x / 255 for x in c]
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def _cr(a, b):
    x = sorted([_lum(a), _lum(b)])
    return (x[1] + .05) / (x[0] + .05)


# ─── D27-01：長表格整頁捲動，表頭貼在頂欄下方 ───────────────
def test_long_table_page_scroll():
    assert "max-height:calc(100vh - 140px)" not in CSS and "max-height:calc(100dvh - 170px)" not in CSS   # 不再有框內捲動
    assert ".tbl-wrap:has(tbody tr:nth-child(25)) thead th{transform:translateY(var(--th-y,0px))}" in CSS
    assert "new MutationObserver(stickHeads).observe($('#view'), { childList: true });" in APP
    assert "addEventListener('scroll', stickHeads, { passive: true });" in APP
    js = _grab(APP, "stickHeads") + r"""
const mk = (top, height, rows) => ({ style: { v: null, setProperty(k, v) { this.v = v; } }, top, height,
  getBoundingClientRect() { return { top: this.top, height: this.height }; },
  querySelector(s) { return s === 'thead' ? { offsetHeight: 30 } : rows >= 25 ? {} : null; } });
const long = mk(400, 2000, 40), short = mk(400, 300, 10);
const document = { querySelectorAll: () => [long, short] };
const $ = () => ({ getBoundingClientRect: () => ({ bottom: 56 }) });
const out = [];
for (const t of [400, 56, -500, -1990]) { long.top = t; stickHeads(); out.push(long.style.v); }
console.log(JSON.stringify({ out, short: short.style.v }));"""
    o = _node(js)
    if o is not None:
        # 表格頂端還在頂欄下方 → 0；捲過頂欄 → 位移到頂欄下緣；最多到表格最後兩列（2000 − 2×30）
        assert o == {"out": ["0px", "0px", "556px", "1940px"], "short": None}, o


# ─── D27-02：新訊號手機版標籤放第二列 ────────────────────
def test_hl_second_row():
    hl = APP[APP.index("async function renderHl()"):APP.index("// ─── 第 8 輪 F8-2")]
    assert '<div class="hl-sub">' not in hl
    assert '<tr class="hl-sub" data-code="${x.code}"><td colspan="6">${x.hl.map(hlTag).join(\'\')}</td></tr>' in hl
    assert ".tbl tr:has(+.hl-sub) td{border-bottom:0;padding-bottom:2px}.tbl tr.hl-sub td{padding-top:0;white-space:normal;box-shadow:none}" in CSS
    # 名稱欄的「代號 產業」不撐寬表格（手機 375 不橫捲）
    assert ".tbl td.nm>span{display:block;margin-left:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;width:0;min-width:100%}" in CSS


# ─── D27-03：選股條件列 ─────────────────────────────────
def test_screen_summary():
    assert "<summary>條件 ${conds.length - nx} 個${nx ? `＋排除 ${nx} 個` : ''}" in APP and "條件（已選 ${conds.length} 個）" not in APP
    assert '<button class="chip scr-go" id="scrGo">符合 ${fmt(hits.length)} 檔 ↓</button>' in APP
    assert '<div class="sec-h" id="scrRes"' in APP and "$('#scrRes').scrollIntoView()" in APP
    assert "delete st[b.dataset.x]; changed();" in APP
    assert ".scr-panel>summary{position:sticky;top:var(--top-h,56px);" in CSS and ".scr-panel[open] .scr-tags{display:none}" in CSS


# ─── D27-04：泡泡圖 Y 軸文案與標籤 ──────────────────────
def test_bubble_wording():
    assert "'↓ 偏流出　近 5 日日均 − 20 日日均（億/天）　偏流入 ↑'" in APP and "'↓ 放緩　　加速 ↑'" not in APP
    assert "Y：近 5 日日均比 20 日日均偏流入或偏流出" in APP and "比 20 日平均加速或放緩" not in APP
    assert "加速度 %{customdata[2]" not in APP and "5日日均−20日日均 %{customdata[2]:+.1f}億/天" in APP
    assert "Math.max(10, Math.min(14, v * 0.2))" in APP
    assert "opacity: isDark() ? .82 : 1" in APP
    # 淺色底不透明時，最淡的綠色泡泡上白字 ≥ 4.5
    assert _cr("#ffffff", "#17804a") >= 4.5


# ─── D27-05：#/today、#/rank 預設與網址 ─────────────────
def test_default_tab_and_url():
    assert "const t0 = TODAY_TABS.some(x => x[0] === t) ? t : App.todayTab || 'ov';" in APP
    assert "if (t !== t0) history.replaceState(null, '', '#/today/' + t0);" in APP
    assert "localStore('rank2', null, App.rank2 = RANKS.some(r => r[0] === arg) ? arg : App.rank2 || 'n+');" in APP
    assert "if (arg !== by) history.replaceState(null, '', '#/rank/' + by);" in APP
    assert "disposeFuturesChart(); renderToday();" in APP


# ─── D27-06、07：個股頁 ─────────────────────────────────
def test_stock_chart_legend_and_price_line():
    assert "lastValueVisible: false, priceLineVisible: false" in STK
    assert "axisLabelTextColor: css('--on-fill')" in STK                   # 深色時標籤用深字（白字在 #ef5b5b 只有 3.3）
    for blk in re.findall(r'(?::root:not\(\[data-theme="light"\]\)|:root\[data-theme="dark"\])\{(.*?)\}', CSS, re.S):
        on = re.search(r"--on-fill:(#[0-9a-f]{3,6})", blk).group(1)
        on = "#111111" if on == "#111" else on
        for k in ("up", "dn", "flat"):
            assert _cr(on, re.search(rf"--{k}:(#[0-9a-f]{{6}})", blk).group(1)) >= 4.5, k
    assert '<span class="lg"><i style="background:${color}"></i>${label} <b>${fmt(v)}</b></span>' in APP
    assert "<b style=\"color:${color}\">" not in APP
    assert "$('#kC').after(" in STK and "#kC+.kv{" in CSS


def test_margin_single_series():
    assert "segHTML('mgSeg'" in STK and "右側刻度只適用融資" not in STK
    js = "let saved = {};\nconst localStore = (k, f) => k in saved ? saved[k] : f;\n" + _grab(STK, "mgView") + r"""
const out = [];
for (const [v, G] of [[undefined, { lb: [1] }], ['sb', {}], ['lb', { lb: [1] }], ['lb', {}], ['xx', { lb: [1] }]]) {
  saved = v === undefined ? {} : { mgv: v }; out.push(mgView(G));
}
console.log(JSON.stringify(out));"""
    o = _node(js)
    if o is not None:
        assert o == ["mb", "sb", "lb", "mb", "mb"], o                          # 沒有借券資料時退回融資


# ─── D27-08：處置摘要與自選事件卡 ───────────────────────
def test_alert_summary_and_reasons():
    S = {"2360": {"n": "致茂", "m": "TWSE"}, "2314": {"n": "台揚", "m": "TWSE"}, "1709": {"n": "和益", "m": "TWSE"}}
    L = {"date": "2026-11-13", "stocks": S,
         "alerts": {"d": [["2360", "2026-11-09", "2026-11-13", "約每二分鐘撮合一次", "連續三日"]],
                    "n": [["1709", "當日沖銷比率高"]], "w": [["2314", 0, "第一款連 2 日"], ["2360", 1, "第一款連 3 日"]]}}
    js = "\n".join(_grab(APP, n) for n in ("esc", "md", "watchGrp", "alertBoard")) + f"""
const App = {{ alertAll: false, alOpen: false }};
console.log(JSON.stringify(alertBoard({json.dumps(L, ensure_ascii=False)})));"""
    o = _node(js)
    if o is not None:
        assert "即將處置 0　處置中 1　接近處置（推算）2　今日注意 1</span>" in o, o
        assert '<a href="#/stock/2314">台揚<span class="muted">（第一款連 2 日）</span></a>' in o   # 差一次的理由直接顯示
        assert 'title="第一款連 2 日"' not in o


def test_watch_event_card():
    names = ["fmt", "pfmt", "sgn", "cls", "pctCell", "yi", "esc", "md", "streakTxt", "holdTag", "alertBadge", "hlTag",
             "segHTML", "onSeg", "flowNote", "wCtl", "stockTable", "spanSeg", "onEtfRow", "watchGestures", "renderWatch", "etfWatchTable"]
    st = {"c": 100, "p": 1.0, "tv": 1.5, "f1": 0, "t1": 0, "d1": 0, "n1": 0, "fs": 0, "ts": 0, "s": 0, "i": "電子"}
    latest = {"date": "2026-11-13", "flow_date": "2026-11-13", "holdings": {},
              "alerts": {"n": [["1709", "當日沖銷比率 63%"]]},
              "stocks": {"2360": {**st, "n": "致茂", "dsp": ["2026-11-09", "2026-11-13"]},
                         "3008": {**st, "n": "大立光", "dsp": ["2026-11-14", "2026-11-25"]},
                         "1709": {**st, "n": "和益", "ntc": 1}},
              "etfs": {"rows": {"0050": {"n": "元大台灣50", "m": "TWSE", "c": 70.1, "ch": 0.2, "p": 0.29, "v": 50000, "tv": 35.1}}}}
    js = "\n".join(_grab(APP, n) for n in names) + f"""
const HL_KINDS = {{}};
const App = {{ latest: {json.dumps(latest, ensure_ascii=False)}, watch: new Set(['2360', '3008', '1709', '0050']) }};
const view = {{ innerHTML: '', addEventListener() {{}} }};
const $ = s => s === '#view' ? view : view.innerHTML.includes(`id="${{s.slice(1)}}"`) ? {{ addEventListener() {{}} }} : null;
const localStore = (k, f) => f, onRowClick = () => {{}};
renderWatch(); const a = view.innerHTML;
App.watch = new Set(); view.innerHTML = ''; renderWatch();
console.log(JSON.stringify({{ a, empty: view.innerHTML }}));"""
    o = _node(js)
    if o is None:
        return
    a = o["a"]
    assert "處置 11/09～11/13（最後一天）</span>" in a and "即將處置 11/14～11/25</span>" in a
    assert '<div class="muted small al-why">注意：當日沖銷比率 63%</div>' in a
    assert a.index('data-etf="0050"') < a.index('class="card w-ev"')                 # 事件卡移到 ETF 表之後
    assert '<button class="chip" id="watchFind">搜尋股票</button>' in o["empty"] and "按清單右側的 ☆ 直接加入" in o["empty"]


# ─── D27-09：搜尋清單 ☆、拖曳自動捲動 ─────────────────────
def test_search_star_and_drag():
    assert '<span class="qstar${App.watch.has(c) ? \' on\' : \'\'}" role="button" data-w="${c}"' in APP
    assert "App.watch.has(w.dataset.w) ? App.watch.delete(w.dataset.w) : App.watch.add(w.dataset.w);" in APP
    assert APP.count("list.addEventListener('click'") == 1                          # 合併成一個監聽
    assert "const v = cy < 90 ? -10 : cy > innerHeight - 90 ? 10 : 0;" in APP and "cancelAnimationFrame(raf)" in APP
    assert ".wdel::after,.wh::after{content:'';position:absolute;inset:-10px}" in CSS   # 觸控範圍 ≥ 40px


# ─── D27-10：其他小項 ───────────────────────────────────
def test_titles_and_small_fixes():
    assert "+ '｜台股資金流';" in APP and "document.title = `${data.name} ${code}｜台股資金流`;" in STK
    assert "持股日 ${md(top)}" in APP and ".sort().pop(), old = R.etfs.filter(x => x.d !== top);" in APP
    assert '<span class="nw${L.flow_date === L.date ? \' fd-eq\' : \'\'}">　法人資料 ${esc(L.flow_date)}</span>' in APP
    assert ".datebar .fd-eq{display:none}" in CSS and ".datebar{white-space:nowrap;overflow-x:auto" not in CSS


def test_quads_on_card():
    """象限卡底色疊在卡片底上（不再透出頁面底色），標題字淺／深色都 ≥ 4.5。"""
    col = {"漲潮": ("q-rise", "up"), "輪動": ("q-rot", "amber"), "觀望": ("q-watch", "blue"), "退潮": ("q-ebb", "dn")}
    blocks = [CSS[CSS.index(":root{"):]] + re.findall(r'(?::root:not\(\[data-theme="light"\]\)|:root\[data-theme="dark"\])\{(.*?)\}', CSS, re.S)
    for q, (bgk, fk) in col.items():
        assert f".q-{q}{{background:linear-gradient(var(--{bgk}),var(--{bgk})) var(--card)}}" in CSS, q
        for b in blocks:
            r, g, bb, a = map(float, re.search(rf"--{bgk}:rgba\(([\d.]+),([\d.]+),([\d.]+),([\d.]+)\)", b).groups())
            card = re.search(r"--card:(#[0-9a-f]{6})", b).group(1)
            cc = [int(card[i:i + 2], 16) for i in (1, 3, 5)]
            bg = [round(v * a + w * (1 - a)) for v, w in zip((r, g, bb), cc)]
            assert _cr(re.search(rf"--{fk}:(#[0-9a-f]{{6}})", b).group(1), bg) >= 4.5, (q, b[:20])


def test_no_advice_words():
    seg = "".join(l for l in APP.splitlines() + STK.splitlines() + CSS.splitlines() if "第 27 輪" in l or "D27-" in l
                  or "qstar" in l or "scr-go" in l or "watchFind" in l or "偏流" in l or "接近處置（推算）" in l)
    assert seg
    seg = seg.replace("借券賣出", "")                                           # 資料欄名稱（官方「借券賣出餘額」），不是用語
    for w in ("買進", "賣出", "反彈", "見底", "買點", "超賣", "超買", "推薦", "強勢股", "飆股", "勝率", "低估", "高估", "建議"):
        assert w not in seg, w


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            print("==", name)
            fn()
            print("✅", name)
    print("全部通過")
```
