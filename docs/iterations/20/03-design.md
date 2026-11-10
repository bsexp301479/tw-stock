# 第 20 輪｜System Analyst：ETF 加入自選（F20-1）設計

- 撰寫日期：2026-11-10（週二）晚上
- 依據：`02-pm.md`（F20-1 範圍、10 條驗收、D29-1～3 預設）、`01-analyst.md` Q20-3。
- 作業方式：
  - 在 scratchpad 建兩份副本（**不含 `.env`、`.git`、`logs`、`data`**）：`r20/orig`（目前版本）、`r20/proj`（原型）。預覽時把 `site/data` 以符號連結指向專案的資料（唯讀），結束後已移除連結。
  - **外部請求 0 次、資料庫 0 次存取**；專案檔案沒有修改。
  - 8001 預覽 `r20/proj/site`，結束時已關閉；8000 沒有碰。瀏覽器已恢復桌面大小與淺色，`tw.watch` 恢復成預覽前的「沒有值」。
- 原型規模：程式＋README **＋24／−9**（PM 估計約 45、上限 60）；測試 `tests/test_iter20.py` 94 行。
- **有一個要使用者決定的衝突**：`test_iter15.py` 第 99 行斷言 ETF 頁**沒有**自選鈕（第十節 D29-4）。

---

## 〇、變更總覽

| 檔案 | 變更 | ＋／− |
|---|---|---|
| `site/stock.js` | 自選鈕不再用 `E` 排除 ETF 頁 | ＋1／−1 |
| `site/app.js` | `onEtfRow`（ETF 列點擊，抽成具名函式，ETF 列表與自選頁共用）；`renderWatch` 分股票、ETF 兩張表；`etfWatchTable`；ETF 列表說明句刪「自選」 | ＋22／−7 |
| `README.md` | ETF 段：「不計入」刪「自選」；「沒有……自選鈕」改成「第 20 輪起可加入自選」 | ＋1／−1 |
| `tests/test_iter20.py`（新） | 4 個測試；其中 1 個用 node 執行真正的 `renderWatch` | 94 行 |
| `app.css` | **不用改**：`.tbl tr[data-etf]{cursor:pointer}`（第 15 輪）在自選頁也適用 | 0 |

- `twstock/`、`site/data` 都不變。

---

## 一、自選鈕（`stock.js` 第 123 行）

- 改前：``${E ? '' : `<button class="star …" id="starBtn">…</button>`}``
- 改後：`<button class="star …" id="starBtn">…</button>`（股票、ETF 都輸出）。
- 點擊處理（第 169～175 行）原本就不分股票或 ETF，**不用改**。代號存進同一個 `tw.watch`；股票與 ETF 代號不會重複（ETF 一律 `00` 開頭，`stocks` 表沒有 ETF）。
- 375 寬：ETF 頁頭部的按鈕和股票頁一樣靠右；上櫃 ETF 多一行「上櫃 ETF 的漲跌可能含除息……」，按鈕排在下一列，頭部高 212 px，沒有水平捲動（截圖確認）。

---

## 二、自選頁（`app.js` `renderWatch`）

### 2-1 清單

| 清單 | 來源 | 條件 |
|---|---|---|
| 股票 `list` | `latest.stocks` | 照舊：`filter(c => S[c])` |
| ETF `etfs` | `latest.etfs.rows` | `!S[c] && R[c]`；`latest.etfs` 不存在時 `R = {}`，ETF 表不出現 |

- 兩份清單都照 `tw.watch` 的加入順序（和現在的股票一樣，不排序）。
- 兩邊都沒有的代號（下市、打錯）不顯示、不報錯、**不從 `tw.watch` 刪除**（現行行為）。

### 2-2 畫面組合

| 自選內容 | 標題列 | 股票卡 | ETF 區 |
|---|---|---|---|
| 股票＋ETF | 「自選」＋1 日／5 日 | 股票表（和改前逐字相同） | 「ETF」小標題＋表 |
| 只有股票 | 「自選」＋1 日／5 日 | 股票表 | 不顯示 |
| 只有 ETF | 「自選」，**沒有** 1 日／5 日 | **不顯示** | 「ETF」小標題＋表 |
| 都沒有 | 「自選」＋1 日／5 日 | 空白提示 | 不顯示 |

- 以 `stk = list.length || !etfs.length` 判斷股票卡與 1 日／5 日要不要出現。**「都沒有」時維持改前的畫面**（只改標題與提示句）。
- `onSeg('rspanSeg', …)` 也要用 `stk` 判斷：只有 ETF 時頁面上沒有 `#rspanSeg`，`onSeg` 會對 `null` 呼叫 `addEventListener` 而整頁「載入失敗」。**原型第一版就有這個錯誤，8001 預覽時發現**；單元測試原本把 `onSeg` 換成空函式，所以沒抓到。已修正，測試也改成用真正的 `onSeg`（第八節）。

### 2-3 ETF 表（`etfWatchTable`）

| 欄 | 內容 | 和 ETF 列表的關係 |
|---|---|---|
| ETF | 名稱、代號、上市／上櫃、`holdTag(c)`（8 檔主動 ETF 的「持股」連結；其他 `A` 結尾的主動 ETF 是「持股尚未支援」） | 相同 |
| 收盤 | `pfmt(r.c)`，顏色依 `r.ch` | 相同 |
| 漲跌 | `sgn(r.p)%`；`r.c == null` 時「無成交」 | 相同 |
| 成交量 | `fmt(r.v)`（張） | 相同 |
| 成交額 | `fmt(r.tv, 2)億` | 相同 |

- D29-1 照 PM 預設：4 欄，不放融資融券、借券（要看可點進 ETF 頁或 ETF 列表）。
- 小標題列：「ETF」＋「當日行情；成交量為張、成交額為億元」，說明這張表沒有 1 日／5 日之分。
- 上櫃 ETF 的漲跌照 `latest.etfs.rows`（可能含除息），和 ETF 列表相同；ETF 頁本身已有提示句，自選頁不再重複。

### 2-4 點擊

- `#view` 這個元素在換頁時不會被換掉，各頁用 `addEventListener` 加的監聽器會一直留著（現行寫法）。
- 所以 ETF 列的點擊抽成具名函式 `onEtfRow`，ETF 列表與自選頁都登記**同一個函式**：瀏覽器對同一個函式重複 `addEventListener` 只會登記一次，不會越加越多。
- ETF 列用 `tr[data-etf]`（不是 `data-code`）：
  - `onRowClick` 只處理 `tr[data-code]`，不會攔到 ETF 列。
  - `onEtfRow` 遇到「持股」連結（`<a>`）不處理，只讓連結本身換頁。如果 ETF 列用 `data-code`，點「持股」時會先換到 ETF 個股頁、再換到持股頁，兩個非同步的畫面可能互相蓋掉。
- 8001 實測：點「持股」→ 只發生 1 次換頁，到 `#/etf/00981A`；點 006201 列 → `#/stock/006201`。

### 2-5 文字對照

| 位置 | 改前 | 改後 |
|---|---|---|
| 自選頁標題 | 自選股 | 自選（D29-2） |
| 空白提示 | 還沒有自選股。打開任一檔個股，按名稱旁的「☆ 加入自選」。 | 還沒有自選股。打開任一檔個股或 ETF，按名稱旁的「☆ 加入自選」。（保留 `test_iter13` 斷言的句子） |
| ETF 小標題 | — | ETF　當日行情；成交量為張、成交額為億元 |
| ETF 列表說明句 | ……ETF 不計入首頁家數、成交額、類股資金流、排行、**自選**與股票口徑的融資融券。 | ……ETF 不計入首頁家數、成交額、類股資金流、排行與股票口徑的融資融券。 |
| README ETF 段 1 | ……泡泡圖、排行、**自選**、法人估算…… | ……泡泡圖、排行、法人估算…… |
| README ETF 段 2 | ……技術面訊號、**自選鈕**。 | ……技術面訊號（第 20 輪起可加入自選，自選頁另列 ETF 表：收盤、漲跌、成交量、成交額）。 |

- 底部導覽列本來就寫「自選」，不用改。

---

## 三、邊界情況

| 情況 | 處理 |
|---|---|
| `latest.etfs` 不存在（ETF 尚未收集） | `R = {}`，ETF 表不出現；ETF 頁本身也不存在，不會加入 |
| ETF 今日無成交 | 收盤「--」、漲跌「無成交」（實測 00625K） |
| ETF 下市後 `etfs.rows` 沒有它 | 不顯示、不刪除儲存值 |
| 舊版快取的 `app.js` 讀到含 ETF 的 `tw.watch` | 舊版只讀 `latest.stocks`，ETF 被略過，不報錯 |
| 只有 ETF | 見 2-2；不綁定 `#rspanSeg` |
| 同一代號重複加入 | `Set`，不會重複 |

---

## 四、驗證結果（原型）

| 項目 | 結果 |
|---|---|
| `test_iter20` | 通過；反證：`orig` 跑同一份測試 → `test_star_on_etf_page` 失敗 ✅ |
| `onSeg` 防呆反證 | 拿掉 `if (stk)` → `test_render_watch` 失敗（node 丟出錯誤），加回 → 通過 ✅ |
| 舊測試 `test_iter01`～`19` | **只有 `test_iter15` 失敗**：第 99 行斷言 ETF 頁沒有自選鈕（D29-4）。在副本中暫時拿掉這一段，`test_iter15` 其餘全部通過；其他 18 個都通過 |
| `node --check` | `app.js`、`stock.js` 通過 |
| 股票表不變 | `r20/q_watch_compare.js`：用真實 `latest.json`、自選放入全部 1,986 檔股票，新舊 `renderWatch` 的股票卡**逐字相同**（785,067 字元）；只有標題「自選股 → 自選」不同。反證：只改新版一邊的 1 個字 → 判定不同 ✅ |
| ETF 表 | 自選放入股票 3 檔＋ETF 全部 363 檔：ETF 列 363、「持股」連結 8、「無成交」3（11/10） |
| 8001 預覽 | 375 深色：真實點擊 0056、006201 的「☆ 加入自選」→ 文字與樣式切換、`tw.watch` 寫入；自選頁兩張表、無水平捲動；只有 ETF、都沒有兩種情況正確。點 006201 列 → ETF 頁且按鈕是「★ 已加入自選」；真實點擊取消後，自選頁不再列 006201；點「持股」→ 持股頁。1024 淺色版面正常 |

- 實際數值（11/10）：0056 收盤 52.3、+1.06%、42,027 張、22.08 億；006201 35.44、+5.35%、700 張、0.25 億；00981A 24.27、+5.25%、412,344 張、99.81 億。

---

## 五、測試案例（`tests/test_iter20.py`，全文見附錄 A）

| 測試 | 內容 | 對應驗收 |
|---|---|---|
| `test_star_on_etf_page` | 自選鈕不再用 `E` 排除；點擊處理不變 | #1 |
| `test_watch_source` | `renderWatch` 讀 `latest.etfs.rows`、兩個標題、ETF 表頭 4 欄、空白提示舊句、兩個監聽器；`onEtfRow` 在 ETF 列表與自選頁共用 | #2、#5、#10 |
| `test_texts` | ETF 列表說明句不含「自選」；README ETF 段 | #8 |
| `test_render_watch` | node 執行真正的 `renderWatch`（相依函式逐字取出，`$` 只回傳畫面上存在的元素）：股票＋ETF（含不存在的代號 9999、無成交、持股連結）、只有 ETF、只有股票、都沒有 | #2～#6 |

- 本機 node 是 v14；`test_render_watch` 用到的函式沒有 `.at()`，不需要 polyfill。沒有 node 時略過這個測試（比照 `test_iter18`）。

---

## 六、PG 實作順序

1. 記錄 `collect_runs` 最大 `run_id`（11/10 為 15）；把 `site/app.js`、`site/stock.js`、`README.md` 複製到 `logs/iter20_before/`；記錄 `site/data` 各檔雜湊（`logs/iter20_data_before.txt`）。
2. **等使用者決定 D29-4** 後，套用附錄 A（`patch -p1 --dry-run` 先試）。
3. `node --check`；`test_iter01`～`20` 全部通過（D29-4 選 A 時含修改後的 `test_iter15`）。
4. 反證：暫存副本放 `logs/iter20_before/` 的檔案跑 `test_iter20`，應失敗。
5. `logs/iter20_watch_compare.js`（即 `r20/q_watch_compare.js`）：股票卡逐字相同。
6. `site/data` 雜湊和第 1 步相同（若期間使用者收集了，記錄 `run_id`，改以「本輪沒有執行 export」說明）。
7. 8001 預覽：375、1024，深淺色；項目同第四節。結束時恢復 `tw.watch` 為預覽前的值、關閉 8001。

---

## 七、對 PM 的調整

| # | 調整 | 理由 |
|---|---|---|
| 1 | 只有 ETF 時不顯示 1 日／5 日 | 這個切換只影響股票表；沒有股票表時顯示會誤導 |
| 2 | ETF 列點擊抽成 `onEtfRow`，ETF 列表也改用它 | 避免監聽器重複累加；`renderEtf` 行為不變（`test_iter15` 第 96 行的字串仍在） |
| 3 | 不改 `app.css` | 既有 `.tbl tr[data-etf]` 游標樣式已涵蓋 |
| 4 | 行數 ＋24／−9，低於 PM 估計 | 沿用既有函式（`holdTag`、`pfmt`、`sgn`），ETF 表只有 4 欄 |

---

## 八、給 PG、QA 的提醒

- **單元測試的 stub 要盡量用真的函式**：本輪原型的錯誤就是 stub 太寬鬆漏掉的。`test_render_watch` 的 `$` 對畫面上沒有的 id 回傳 `null`，和瀏覽器一致。
- 預覽前先記下 8001 的 `tw.watch`（本次是沒有值），結束時恢復；不要清掉 `tw.screen`、`todayTab`。
- 瀏覽器主控台的錯誤紀錄重新載入後不會清掉；判斷錯誤是否還在時，看堆疊行號是否對得上目前檔案，或改用頁面是否出現「載入失敗」。
- 本輪不需要 `export`；`site/data` 應完全不變。

---

## 九、驗收對照

| PM 驗收 | 設計／驗證 |
|---|---|
| #1 三種 ETF 頁有自選鈕、狀態保留 | 第一節；預覽 0056、006201 實測；00981A 用同一行程式 |
| #2 股票表和改前逐字相同 | 第四節 `q_watch_compare.js` |
| #3 ETF 表數值 = `latest.etfs.rows` | 2-3；第四節實際數值 |
| #4 三種情況 | 2-2；`test_render_watch` |
| #5 點擊 | 2-4；預覽實測 |
| #6 不存在的代號 | 第三節；`test_render_watch`（9999） |
| #7 375、深淺色、主控台 | 預覽 |
| #8 文字 | 2-5；`test_texts` |
| #9 `site/data` 不變、不含 `twstock/` | 第〇節；PG 第 1、6 步 |
| #10 單元測試 | 第五節 |

---

## 十、需要使用者決定：D29-4（舊測試衝突）

`tests/test_iter15.py` 第 99 行：

```python
assert "${E ? '' : `<button class=\"star" in STK and "if (!E) renderSignals(" in STK and "const ETF_TABS = STOCK_TABS.slice(0, 2);" in STK
```

- 第一段斷言「ETF 頁不輸出自選鈕」，是第 15 輪的行為；F20-1 正是要改這件事，所以一定衝突。
- 專案守則是「舊測試的斷言不改，只能新增」，所以要由使用者決定。

| 選項 | 做法 | 取捨 |
|---|---|---|
| **A（建議）** | 只刪掉第 99 行的第一段（`"${E ? '' : `<button class=\"star" in STK and `），保留後兩段；`test_iter20` 已新增相反的斷言（ETF 頁要有自選鈕） | 測試反映目前的需求；其他第 15 輪的 ETF 頁斷言都不動 |
| B | 不改舊測試：股票頁那一行原樣保留，另外加一行只在 ETF 頁輸出的按鈕 | 舊斷言字面上會通過，但它想保護的「ETF 頁沒有自選鈕」實際上已經不成立；按鈕寫兩份，等於為了讓測試通過而繞過它。**不建議** |
| C | 取消 ETF 頁的自選鈕，只做自選頁的 ETF 表 | 沒有入口可以加入 ETF，F20-1 失去意義 |

---

## 附錄 A：完整 diff（`orig` → `proj`；新測試檔全文在後）

```diff
--- a/README.md
+++ b/README.md
@@ -155,7 +155,7 @@
 - 融資融券排行（排行頁）：融資增加／減少（可切換估算金額與張數，預設估算金額 = 張數 × 1,000 × 收盤，**是估算，不是官方融資金額**）、融資增加率、融券增加／減少、券資比、融資使用率，可切換 1 日／5 日。融資增加率的基期（1 或 5 日前餘額）至少 1,000 張；券資比只列融資 1,000 張以上。面額變更、減資時，官方會把融資融券餘額換算成新單位（例：寶雅 5904 2026-08-10 面額 10 元改 1 元，融資 594 張 → 前日餘額 5,940 張）：網站以「事件後第一天的官方前日餘額 ÷ 前一天餘額」為換算係數，5 日增減與個股圖的「還原」都用換算後的值；除權不換算。個股頁 K 線組新增「融資／融券餘額」圖（`stocks/{代號}.json` 的 `mg`：與日線對齊的官方原始餘額，`k` 為換算紀錄），和 K 線同步拖曳，跟著「還原／原始」切換。今日頁信用交易卡加「看排行 →」，並註明維持率的參考值是經驗值、非官方門檻。
 - 借券賣出（第 11 輪，資料表 `sbl_trades`、ETF 另存 `etf_sbl`，2025-10-30 起）：上市取自證交所 `TWT93U`、上櫃取自櫃買 `margin/sbl`，每市場每日 1 個請求，排在融資融券之後；同市場當天行情還沒有時不發請求。存「借券賣出」6 欄（前日餘額、當日賣出、當日還券、當日調整、當日餘額、次一營業日可借券賣出限額，**單位股**）與備註原文，融券欄不重複存；匯出、畫面一律換成張（四捨五入，正負對稱）。**借券資料晚上 8 點半以後才有**：回應日期不是當天（前一個交易日）或沒有資料列都當成尚未公布，22:00 前記「尚未公布」，之後才算異常；證交所 22:30 的第二版（加入次日轉上市的股票）不重抓。「前日 ＋ 賣出 − 還券 ＋ 調整 ＝ 餘額」不符時照存並印警告。`check` 多「上市借券」「上櫃借券」兩行。發行股數存在 `stocks.shares`（`update_industry` 一併寫入：上市「已發行普通股數或TDR原股發行股數」、上櫃 `IssueShares`；**只存目前股數，沒有歷史**）。個股頁融資融券圖加第三條線「借券賣出」（`mg.lb`，獨立座標軸，所以融券線不會被壓平），並加「借券賣出餘額」「借券占股本」指標卡（`stocks/{代號}.json` 的 `sbl`：`d` 資料日、`lb` 餘額、`l1`／`l5` 1 日／5 日增減（張；5 日前依面額變更換算）、`lp` 占股本 %（沒有股數不輸出）、`lx` 借券 ÷ 融券倍數（融券 0 不輸出）、`nt` 備註）。排行加「借券賣出增加」（依估算金額 = 張數 × 1,000 × 收盤，1 日／5 日）與「借券占股本」，不含 ETF。今日頁信用交易卡加一行上市、上櫃股票的借券賣出餘額合計、1 日增減與融券的倍數（`latest.json` 的 `sbl`：`{市場: {d, lb, l1, n}}`，股票口徑、先加總股數再換算張數）。**借券賣出包含避險、套利（ETF、權證、可轉債避險），不等於看空，只能當作空方部位的上限**；占股本用目前股數。第 12 輪：ETF 借券上線。`latest.json` 的 `sbl_etf`（`{市場: {d, lb, l1, n}}`，上市、上櫃 ETF 各自的最新借券日，先加總股數再換算張數），今日頁信用交易卡另一行「ETF 借券賣出」（上市、上櫃分開寫，附「多為造市、套利與避險，不等於看空」）；ETF 頁加借券兩欄（見 ETF）。個股頁融資融券圖單位文字加「右側刻度只適用融資；融券、借券各自縮放，數值看圖例」。
 - 大盤融資維持率（**自算、非官方**）= Σ(融資張數 × 1,000 × 收盤) ÷ 官方融資金額，分子含股票與 ETF；當日無成交用最近一次收盤；有收盤的融資張數 ÷ 官方融資張數（涵蓋率）不足 99% 時顯示「資料不足」。
-- ETF：代號 `00` 開頭、4～6 碼、數字後最多一個英文字尾（例：0050、00878、006201、00406A、00679B）；ETN、受益證券、TDR、權證、特別股不算。ETF 存在獨立的資料表（`etfs`、`etf_daily`、`etf_margin`），`stocks` 表沒有任何 ETF。行情取自與股票同一個 `MI_INDEX`／`dailyQuotes` 回應，**每日不增加請求**；歷史需用 `history --only etf` 補抓。ETF 頁（`#/etf`）列出全部 ETF 的收盤、漲跌、成交量（張）、成交額（億）、融資融券餘額與增減（張），可依成交額、漲幅、跌幅、融資增減、融券增減排序並篩選上市／上櫃。**ETF 不計入**首頁家數與成交額、類股／產業鏈／概念股資金流與泡泡圖、排行、自選、法人估算、股票口徑的融資融券；只計入大盤融資維持率的分子。上市官方三大法人金額本來就含 ETF。第 12 輪：ETF 頁加「借券餘額」「借券增減」兩欄（張；`latest.json` 的 `etfs.rows.*.lb`、`l1`，沒有借券資料顯示 `--`），排序加借券增加、借券減少、借券餘額。第 15 輪 ETF 個股頁：`site/data/etfp/{代號}.json`（`latest.json` 的 `etfs.rows` 每檔一個，已下市的不匯出；247 天約 9～17 KB、363 檔合計約 4.5 MB），內容 `prices`（完整日線，格式同個股；**原始價**，量為張，`ch` 為官方漲跌）、`gx`（上市 ETF 推測的價格調整日）、`margin`、`sbl`、`mg`（同個股的融資融券、借券格式；沒有占股本）。搜尋（股票在前、ETF 在後，結果標「ETF」）、ETF 列表點列、`#/stock/{代號}` 都進入 ETF 個股頁；8 檔主動 ETF 的頁首有「持股 →」，持股頁有「行情 →」；其他 ETF 的 `#/etf/{代號}` 會轉到 ETF 個股頁。頁面只有「走勢」「籌碼」兩頁：K 線（日／週／月）、均線、量、融資融券與借券圖、MACD，以及融資融券、借券賣出卡；沒有還原切換、法人、基本面、估值、技術面訊號、自選鈕。價格**未還原除息**（本站沒有 ETF 除息資料），配息 ETF 在除息日會向下跳空，均線、MACD、52 週高低也用原始價。上市 ETF：前一個資料列有成交、官方漲跌有值，且「收盤 − 官方漲跌」和前一日收盤差 ≥ 0.005 元的日子記為推測的價格調整日：官方漲跌 0（不比價，多為除息）在 K 線標「息?」、`ch` 改為 null，漲跌不是 0（參考價改變，多為分割）標「調?」；只是推測，沒有配息金額。上櫃 ETF：櫃買的漲跌就是收盤 − 前一日收盤，除息日的漲跌含除息跌幅，無法辨識，不標示，頁首與 K 線旁註明。
+- ETF：代號 `00` 開頭、4～6 碼、數字後最多一個英文字尾（例：0050、00878、006201、00406A、00679B）；ETN、受益證券、TDR、權證、特別股不算。ETF 存在獨立的資料表（`etfs`、`etf_daily`、`etf_margin`），`stocks` 表沒有任何 ETF。行情取自與股票同一個 `MI_INDEX`／`dailyQuotes` 回應，**每日不增加請求**；歷史需用 `history --only etf` 補抓。ETF 頁（`#/etf`）列出全部 ETF 的收盤、漲跌、成交量（張）、成交額（億）、融資融券餘額與增減（張），可依成交額、漲幅、跌幅、融資增減、融券增減排序並篩選上市／上櫃。**ETF 不計入**首頁家數與成交額、類股／產業鏈／概念股資金流與泡泡圖、排行、法人估算、股票口徑的融資融券；只計入大盤融資維持率的分子。上市官方三大法人金額本來就含 ETF。第 12 輪：ETF 頁加「借券餘額」「借券增減」兩欄（張；`latest.json` 的 `etfs.rows.*.lb`、`l1`，沒有借券資料顯示 `--`），排序加借券增加、借券減少、借券餘額。第 15 輪 ETF 個股頁：`site/data/etfp/{代號}.json`（`latest.json` 的 `etfs.rows` 每檔一個，已下市的不匯出；247 天約 9～17 KB、363 檔合計約 4.5 MB），內容 `prices`（完整日線，格式同個股；**原始價**，量為張，`ch` 為官方漲跌）、`gx`（上市 ETF 推測的價格調整日）、`margin`、`sbl`、`mg`（同個股的融資融券、借券格式；沒有占股本）。搜尋（股票在前、ETF 在後，結果標「ETF」）、ETF 列表點列、`#/stock/{代號}` 都進入 ETF 個股頁；8 檔主動 ETF 的頁首有「持股 →」，持股頁有「行情 →」；其他 ETF 的 `#/etf/{代號}` 會轉到 ETF 個股頁。頁面只有「走勢」「籌碼」兩頁：K 線（日／週／月）、均線、量、融資融券與借券圖、MACD，以及融資融券、借券賣出卡；沒有還原切換、法人、基本面、估值、技術面訊號（第 20 輪起可加入自選，自選頁另列 ETF 表：收盤、漲跌、成交量、成交額）。價格**未還原除息**（本站沒有 ETF 除息資料），配息 ETF 在除息日會向下跳空，均線、MACD、52 週高低也用原始價。上市 ETF：前一個資料列有成交、官方漲跌有值，且「收盤 − 官方漲跌」和前一日收盤差 ≥ 0.005 元的日子記為推測的價格調整日：官方漲跌 0（不比價，多為除息）在 K 線標「息?」、`ch` 改為 null，漲跌不是 0（參考價改變，多為分割）標「調?」；只是推測，沒有配息金額。上櫃 ETF：櫃買的漲跌就是收盤 − 前一日收盤，除息日的漲跌含除息跌幅，無法辨識，不標示，頁首與 K 線旁註明。
 - 主動型 ETF 持股：取自投信每日申購買回清單，間隔 3 秒：統一投信（`www.ezmoney.com.tw` 的 `GetPCF`）00981A、00403A、00411A、00988A；群益投信（`www.capitalfund.com.tw` 的 `CFWeb/api/etf/buyback`，第 7 輪）00982A、00992A、00415A、00997A。群益的明細只有股數與權重，**沒有市值**（資料庫存 NULL，不推算）。**00406A（中信）與其他投信尚未支援**，ETF 頁標示「持股尚未支援」。日期以**持股日**為準：國內 ETF（00981A、00403A、00982A、00992A、00415A）當天傍晚公布當天的持股；跨境 ETF（00411A、00988A、00997A）晚一個交易日（11/03 晚上公布的是 11/02 的持股）。單位：台股為張（股數 ÷ 1,000）、海外股票為股，海外與期貨只在 ETF 持股頁顯示原文。持股頁（`#/etf/代號`）列淨資產、每單位淨值、股票權重合計、持股檔數、期貨，以及每檔的持有張數、權重、1 日增減、1 日權重變化、5 日增減、「新」與出清；個股頁「主動 ETF 持有」卡列出持有該股的已支援 ETF。這 8 檔都是現金申購買回：申購的資金由經理人買進股票，**申購多的日子加碼會偏多**（例：2026-11-04 00982A 單位數 +2.23%，31 檔加碼中 24 檔的增幅在 1.1%～2.9%），所以張數增減不全是經理人看好或看壞。持股頁摘要、主動 ETF 彙總與今日小卡列出各檔「單位數 1 日」變化（相對前一持股日），可對照。權重變化另含股價漲跌的影響。個股頁「主動 ETF 持有」卡另列「投信買超中已收主動 ETF 的張數」：只計入國內 5 檔、持股日與法人資料日相同的 ETF（含新進與出清），同向且不超過投信合計時顯示百分比；投信買賣超（T86）含所有投信基金與 ETF。新增統一或群益投信的主動 ETF：在 `twstock/health.py` 的 `HOLDINGS` 加一列（代號 → 基金代碼、delay、上市日、投信），再執行 `history --start 上市日 --only holdings`。**海外休市日**（跨境 ETF 當天沒有持股清單，例如美國感恩節）與**臺股臨時休市前一個交易日**（投信只公布彙總、沒有明細）會記在 `etf_holding_gaps`，`check` 視為正常並另列一行，不再請求；持股頁與 1 日增減以前一個有明細的持股日為準。臨時休市前一日的明細在生效日之前都當成尚未公布，所以當晚 22:00 後可能先顯示異常，隔天收集後自動消失。
 - 主動 ETF 彙總（`#/etf/active`，今日頁另有加碼、減碼前 5 名小卡；第 7 輪）：把已支援持股的主動 ETF 最新一天的張數增減合計（只算台股），列出合計加碼、減碼各 20 名與被最多檔持有的 20 檔。**估算金額 = 各 ETF 張數增減 × 該 ETF 持股日收盤**（無成交用最近收盤），不是實際成交金額；沒有收盤的股票不列入加減碼排行。各 ETF 用自己的最新持股日（跨境 ETF 晚一個交易日）；某檔當天還沒收到持股（持股日比同類 ETF 舊）時不列入，頁首標示「未更新」。標題寫明「統一、群益 8 檔」，頂端列出各檔單位數 1 日變化（多檔同時淨申購的日子，合計加碼會偏多）。5 日張數只計入最新或前一持股日仍持有的股票（5 天前持有、這兩天都已出清的不列入）。
 - 市場寬度：今日頁成交額卡的漲跌家數改用**官方**（股票）：上市取自與行情同一個 `MI_INDEX` 回應的「漲跌證券數合計」（不增加請求）、上櫃取自櫃買 `afterTrading/highlight`（每日 +1 請求），2026-11-03 起，歷史不補；沒有官方家數時退回網站自算並註明。**官方與網站自算的差別**：上市官方「股票」欄不含 TDR、另列「無比價」，網站自算把 TDR 算成股票、無比價依參考價算漲跌，2026-11-03 網站自算多 3 漲 3 跌（上櫃一致）。市場寬度卡為自算（股票，不含 ETF，還原收盤）：站上 MA20／MA60 = 收盤 > 含當天的 20／60 日均價的比例，分母 = 當天有收盤且有 20／60 個以上收盤的股票；20 日新高／新低 = 收盤高於／低於前 20 個收盤；量能 = 當天成交額 ÷ 前 20 個交易日平均。
--- a/site/app.js	2026-11-09 21:14:56
+++ b/site/app.js	2026-11-10 21:29:25
@@ -1216,6 +1216,9 @@
 const ETF_SORT = [['tv', '成交額', -1], ['p+', '漲幅', -1], ['p-', '跌幅', 1], ['m1', '融資增減', -1], ['s1', '融券增減', -1],
   ['l1+', '借券增加', -1], ['l1-', '借券減少', 1], ['lb', '借券餘額', -1]];     // 第 12 輪 ETF-借券
 
+// ETF 列（tr[data-etf]）→ ETF 個股頁；列內的「持股」小標（<a>）照舊連到持股頁。第 20 輪：ETF 列表與自選頁共用
+const onEtfRow = e => { const tr = e.target.closest('tr[data-etf]'); if (tr && !e.target.closest('a')) location.hash = '#/stock/' + tr.dataset.etf; };
+
 function renderEtf() {
   const E = App.latest.etfs;
   if (!E) {
@@ -1243,12 +1246,12 @@
         <td class="num">${r.sb == null ? '--' : fmt(r.sb)}</td>${lots(r.s1)}
         <td class="num">${r.lb == null ? '--' : fmt(r.lb)}</td>${lots(r.l1)}</tr>`).join('') +
       `</tbody></table></div></div>
-      <div class="muted small" style="margin-top:6px">共 ${list.length} 檔。成交量為張、成交額為億元；融資融券為張，增減 = 今日餘額 − 前日餘額，「--」表示不在信用交易清單。借券為借券賣出（張，資料晚上 8 點半以後更新），多為造市、套利與避險，不等於看空。ETF 不計入首頁家數、成交額、類股資金流、排行、自選與股票口徑的融資融券。</div></section>`;
+      <div class="muted small" style="margin-top:6px">共 ${list.length} 檔。成交量為張、成交額為億元；融資融券為張，增減 = 今日餘額 − 前日餘額，「--」表示不在信用交易清單。借券為借券賣出（張，資料晚上 8 點半以後更新），多為造市、套利與避險，不等於看空。ETF 不計入首頁家數、成交額、類股資金流、排行與股票口徑的融資融券。</div></section>`;
   keyCol({ tv: 4, p: 2, m1: 6, s1: 8, l1: 10, lb: 9 }[f]);
   $('#etfSel').addEventListener('change', e => { localStore('etfSort', null, e.target.value); renderEtf(); });
   onSeg('etfMktSeg', v => { localStore('etfMkt', null, v); renderEtf(); });
   // 第 15 輪 F15-2：整列 → ETF 個股頁；列內的「持股」小標（<a>）照舊連到持股頁
-  $('#view').addEventListener('click', e => { const tr = e.target.closest('tr[data-etf]'); if (tr && !e.target.closest('a')) location.hash = '#/stock/' + tr.dataset.etf; });
+  $('#view').addEventListener('click', onEtfRow);
 }
 
 // ─── F7-2：主動 ETF 彙總排行 ─────────────────────────────
@@ -1346,14 +1349,26 @@
 }
 
 function renderWatch() {
-  const S = App.latest.stocks, span = localStore('rspan', '1');
+  const S = App.latest.stocks, span = localStore('rspan', '1'), R = App.latest.etfs?.rows || {};
   const list = [...App.watch].filter(c => S[c]).map(c => [c, S[c]]);
+  const etfs = [...App.watch].filter(c => !S[c] && R[c]).map(c => [c, R[c]]);     // 第 20 輪 F20-1：自選的 ETF 另列一張表
+  const stk = list.length || !etfs.length;                                         // 只有 ETF 時不顯示股票表與 1 日／5 日
   $('#view').innerHTML = `<section class="sec">
-      <div class="sec-h"><h2>自選股</h2><span class="muted small">存在這個瀏覽器裡，換裝置不會同步</span><span class="sp"></span>${spanSeg(span)}</div>
-      <div class="card">${list.length ? stockTable(list, span)
-        : '<div class="empty">還沒有自選股。打開任一檔個股，按名稱旁的「☆ 加入自選」。</div>'}</div></section>`;
-  onSeg('rspanSeg', v => { localStore('rspan', null, v); renderWatch(); });
+      <div class="sec-h"><h2>自選</h2><span class="muted small">存在這個瀏覽器裡，換裝置不會同步</span><span class="sp"></span>${stk ? spanSeg(span) : ''}</div>
+      ${stk ? `<div class="card">${list.length ? stockTable(list, span)
+        : '<div class="empty">還沒有自選股。打開任一檔個股或 ETF，按名稱旁的「☆ 加入自選」。</div>'}</div>` : ''}
+      ${etfs.length ? `<div class="sec-h" style="margin-top:12px"><h2>ETF</h2><span class="muted small">當日行情；成交量為張、成交額為億元</span></div>
+      <div class="card">${etfWatchTable(etfs)}</div>` : ''}</section>`;
+  if (stk) onSeg('rspanSeg', v => { localStore('rspan', null, v); renderWatch(); });
   $('#view').addEventListener('click', onRowClick);
+  $('#view').addEventListener('click', onEtfRow);
+}
+// 第 20 輪 F20-1：自選頁的 ETF 表（ETF 列表的前 4 欄，資料為 latest.etfs.rows）
+function etfWatchTable(list) {
+  return '<div class="tbl-wrap"><table class="tbl"><thead><tr><th>ETF</th><th>收盤</th><th>漲跌</th><th>成交量</th><th>成交額</th></tr></thead><tbody>' +
+    list.map(([c, r]) => `<tr data-etf="${c}"><td class="nm"><b>${esc(r.n)}</b><span>${c} ${r.m === 'TWSE' ? '上市' : '上櫃'}</span>${holdTag(c)}</td>
+      <td class="num ${cls(r.ch)}">${pfmt(r.c)}</td><td class="num ${cls(r.ch)}">${r.c == null ? '無成交' : sgn(r.p) + '%'}</td>
+      <td class="num">${fmt(r.v)}</td><td class="num">${fmt(r.tv, 2)}億</td></tr>`).join('') + '</tbody></table></div>';
 }
 
 // ─── 資料新鮮度（S4）────────────────────────────────────
--- a/site/stock.js	2026-11-09 22:27:15
+++ b/site/stock.js	2026-11-10 21:27:08
@@ -120,7 +120,7 @@
           </div>
           <div class="s-ohlc small num muted"><span class="nw">開 <b>${pfmt(P.o[last])}</b></span>　<span class="nw">高 <b class="up">${pfmt(P.h[last])}</b></span>　<span class="nw">低 <b class="dn">${pfmt(P.l[last])}</b></span>　<span class="nw">昨收 <b>${pfmt(prev)}</b></span>　<span class="nw">量 <b>${fmt(P.v[last])}</b> 張</span></div>
         </div>
-        ${E ? '' : `<button class="star ${watching ? 'on' : ''}" id="starBtn">${watching ? '★ 已加入自選' : '☆ 加入自選'}</button>`}
+        <button class="star ${watching ? 'on' : ''}" id="starBtn">${watching ? '★ 已加入自選' : '☆ 加入自選'}</button>
       </div>
     </section>
 
```

### `tests/test_iter20.py`（新檔）

```python
"""第 20 輪（不連網、不連資料庫）：F20-1 ETF 加入自選。
有 node 時，逐字取出 app.js 的 renderWatch 與相依函式，用假的 latest 跑四種自選清單。"""
import json
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "site" / "app.js").read_text(encoding="utf-8")
STK = (ROOT / "site" / "stock.js").read_text(encoding="utf-8")
README = (ROOT / "README.md").read_text(encoding="utf-8")


def test_star_on_etf_page():
    # ETF 頁也輸出自選鈕（不再用 E 判斷）；點擊處理不分股票、ETF
    assert re.search(r"^\s*<button class=\"star \$\{watching", STK, re.M)
    assert "${E ? '' : `<button class=\"star" not in STK
    assert "App.watch.has(code) ? App.watch.delete(code) : App.watch.add(code);" in STK


def test_watch_source():
    w = APP[APP.index("function renderWatch()"):APP.index("// ─── 資料新鮮度")]
    assert "App.latest.etfs?.rows || {}" in w and "filter(c => !S[c] && R[c])" in w
    assert "<h2>自選</h2>" in w and "<h2>ETF</h2>" in w
    assert "按名稱旁的「☆ 加入自選」" in w                                       # test_iter13 的舊句保留
    assert "addEventListener('click', onEtfRow)" in w and "addEventListener('click', onRowClick)" in w
    assert "<th>ETF</th><th>收盤</th><th>漲跌</th><th>成交量</th><th>成交額</th>" in w
    # ETF 列表改用同一個具名函式（重複 addEventListener 只登記一次）
    assert APP.count("addEventListener('click', onEtfRow)") == 2
    assert "const onEtfRow = e =>" in APP


def test_texts():
    note = APP[APP.index("function renderEtf()"):APP.index("function renderWatch()")]
    assert "自選" not in note.split("<div class=\"muted small\" style=\"margin-top:6px\">共 ")[1].split("</div>")[0]
    etf = next(l for l in README.splitlines() if l.startswith("- ETF：代號"))
    assert "排行、自選" not in etf and "自選鈕" not in etf and "第 20 輪起可加入自選" in etf


def _grab(name):
    """取出 app.js 的頂層 function 或 const（const 取到結尾為「;」的那一行）。"""
    m = re.search(rf"^function {name}\(", APP, re.M)
    if m:
        i, n = APP.index("{", APP.index(")", m.start())), 0
        for j in range(i, len(APP)):
            n += {"{": 1, "}": -1}.get(APP[j], 0)
            if n == 0:
                return APP[m.start():j + 1]
    m = re.search(rf"^const {name} =", APP, re.M)
    lines = APP[m.start():].splitlines()
    k = next(i for i, l in enumerate(lines) if l.rstrip().endswith(";"))
    return "\n".join(lines[:k + 1])


def test_render_watch():
    node = shutil.which("node")
    if not node:
        print("  （沒有 node，略過 renderWatch 執行）"); return
    names = ["fmt", "pfmt", "sgn", "cls", "pctCell", "yi", "esc", "md", "streakTxt", "holdTag", "alertBadge",
             "segHTML", "onSeg", "flowNote", "stockTable", "spanSeg", "onEtfRow", "renderWatch", "etfWatchTable"]
    latest = {"date": "2026-11-10", "flow_date": "2026-11-10", "holdings": {"00981A": {}},
              "stocks": {"2330": {"n": "台積電", "i": "半導體", "c": 1460, "p": 1.2, "tv": 300.5, "f1": 10, "t1": 1, "d1": 0, "n1": 11, "fs": 2, "ts": 1, "s": 2}},
              "etfs": {"rows": {"0056": {"n": "元大高股息", "m": "TWSE", "c": 36.5, "ch": -0.2, "p": -0.54, "v": 30000, "tv": 11.02},
                                "00981A": {"n": "主動統一台股增長", "m": "TWSE", "c": 15.1, "ch": 0.1, "p": 0.67, "v": 90000, "tv": 13.6},
                                "00625K": {"n": "富邦上証+R", "m": "TWSE", "c": None, "ch": None, "p": None, "v": 0, "tv": 0}}}}
    js = "\n".join(_grab(n) for n in names) + f"""
const App = {{ latest: {json.dumps(latest, ensure_ascii=False)}, watch: new Set() }};
const view = {{ innerHTML: '', n: 0, addEventListener() {{ this.n++; }} }};
const $ = s => s === '#view' ? view : view.innerHTML.includes(`id="${{s.slice(1)}}"`) ? {{ addEventListener() {{}} }} : null;   // 畫面上沒有的元素回傳 null
const localStore = (k, f) => f, onRowClick = () => {{}};
const out = {{}};
for (const [k, w] of Object.entries({{ both: ['2330', '0056', '00981A', '00625K', '9999'], etf: ['0056'], stock: ['2330'], none: [] }})) {{
  App.watch = new Set(w); view.innerHTML = ''; renderWatch(); out[k] = view.innerHTML;
}}
console.log(JSON.stringify(out));"""
    o = json.loads(subprocess.run([node, "-e", js], capture_output=True, text=True, check=True).stdout)
    for k in o:
        assert "<h2>自選</h2>" in o[k]
    b = o["both"]
    assert 'data-code="2330"' in b and b.count("data-etf=") == 3 and "9999" not in b      # 不存在的代號不顯示
    assert '<a class="pill hold" href="#/etf/00981A">持股</a>' in b and "rspanSeg" in b
    assert ">無成交</td>" in b and '<td class="num">11.02億</td>' in b and '<td class="num dn">-0.54%</td>' in b
    assert b.index('data-code="2330"') < b.index('data-etf="0056"')                       # 股票在上
    assert "data-code" not in o["etf"] and "還沒有自選股" not in o["etf"] and "rspanSeg" not in o["etf"]
    assert "<h2>ETF</h2>" not in o["stock"] and "rspanSeg" in o["stock"]
    assert "還沒有自選股" in o["none"] and "<h2>ETF</h2>" not in o["none"] and "rspanSeg" in o["none"]


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_") and callable(f):
            print("==", n); f()
    print("全部通過")
```

### D29-4 選 A 時 `tests/test_iter15.py` 的修改（只刪第 99 行第一段）

```diff
-    assert "${E ? '' : `<button class=\"star" in STK and "if (!E) renderSignals(" in STK and "const ETF_TABS = STOCK_TABS.slice(0, 2);" in STK
+    assert "if (!E) renderSignals(" in STK and "const ETF_TABS = STOCK_TABS.slice(0, 2);" in STK
```
