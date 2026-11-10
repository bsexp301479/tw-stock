# 第 21 輪｜System Analyst：F21-1 近期新訊號 設計

- 撰寫日期：2026-11-10（週二）晚上
- 依據：
  - `21/02-pm.md`：範圍、驗收 10 條、第五節提示、D31 預設。
  - `21/01-analyst.md`：事件定義、回測口徑。
  - 使用者回覆「照建議，進 SA」：**D31 照 PM 預設**——門檻預設 ≥ 3 可切 ≥ 2、名稱由 SA 提案、放排行頁。
- 原型作業：
  - 在 scratchpad `r21/` 建立兩份專案副本：
    - `orig` = 目前工作目錄（含第 20 輪尚未 commit 的修改）。
    - `proj` = 本設計。
    - 兩份都**不含 `.env`**、`_archive`、`logs`、`.git`、`site/data`。
  - 唯讀模擬匯出：`orig`、`proj` 各執行一次 `export`，只執行 SELECT，輸出寫到各自的 `site/data`（scratchpad）。
    - **沒有寫專案的 `site/data`。**
    - 帳密由 `r21/run_export.py` 以 setdefault 讀專案 `.env` 到環境變數，沒有印出或複製 `.env`。
  - 8001 預覽 `r21/proj/site`，結束時已關閉；8000 沒有碰。瀏覽器已恢復桌面大小與淺色，預覽時新增的 `tw.hlmin` 已刪除（預覽前 localStorage 沒有任何鍵）。
  - **外部請求 0 次、資料庫寫入 0 次**；`collect_runs` 最大 15、沒有進行中的收集。沒有 commit。
- **名稱提案（D31-2）**：「新訊號」。
  - 排行頁模式切換：「排行／選股／新訊號」。
  - 表頭「近期新訊號」。
  - 不用「亮點」：「亮點」帶有評價，「新訊號」只說明是新出現的事件。

---

## 〇、變更總覽

| 檔案 | 內容 | ＋／− |
|---|---|---|
| `twstock/export.py` | `HL_DAYS`、`HL_REV_DAYS`；`highlights()`、`highlight_revenue()`、`highlight_active()`；月營收查詢多取 `created_at`；`latest.json` 每檔股票加 `hl` | ＋73／−3 |
| `site/app.js` | 路由 `#/rank/hl`；模式切換加「新訊號」；`HL_KINDS`、`hlTag`、`hlDims`、`renderHl` | ＋32／−3 |
| `site/app.css` | 標籤欄可換行 | ＋1 |
| `README.md` | 網站一覽加「近期新訊號」；新增一段說明 | ＋2／−1 |
| `tests/test_iter21.py`（新） | 7 個測試 | 175 行 |

- 程式＋README **＋108／−7**。PM 估約 115，上限 160。
- `collectors/` 不動；`screen.json`、`stocks/`、`etfp/`、`etfs/` 輸出不變。

---

## 一、口徑：和選股共用（PM 第五節第 3 點）

### 1-1 現有欄位的算法（`export.py`）

| 欄位 | 算法 | 位置 |
|---|---|---|
| `nh` | **還原收盤**；今天有成交且收盤 **大於**前 N 日最高（不含今天），取符合的最大 N（240／120／60／20） | `price_stats` |
| `vr` | **成交額**：今日成交額 ÷ 前 20 個交易日平均（無成交以 0 計），四捨五入到 2 位 | `price_stats` |
| `a20` | 近 20 個資料列平均成交額（億） | `price_stats` |
| `s`、`ts` | 法人、投信買賣超**金額**（張數 × 收盤）的連續同向天數，看最近 30 天；法人資料日以前 | `streak(net_value[-30:])` |
| `t5`／`t5r` | 投信 5 日買超金額；前端條件 `t5 ≥ a20 × 5 × v ÷ 100` | 匯出 `t5`、前端 `t5r` |
| `ry`、`rh` | 最新一個月營收年增 %；`rh` = 創新高的年數（> 0 為創新高） | `revenue_stats` |
| 主動 ETF「新」 | 同一檔 ETF 前一個持股日沒有、最新持股日有 | `holding_table` |

### 1-2 新出現的判定

`highlights()` 對每檔股票，從窗口前一個資料列起**逐日呼叫 `price_stats`**（傳入截到那天的序列），並以同樣的 `streak` 算連買天數。

- 新出現：當天符合、該股前一個資料列不符合。窗口內第一個被計算的列沒有前一列可比，不產生事件。
- 價量事件（`nh`、`vu`）看行情日最後 5 天。
- 法人事件（`s3`、`t3`、`t5`）看法人資料日最後 5 天，晚於法人資料日的列不產生法人事件。

| 種類 | 面向 | 條件（當天） | 對應選股 |
|---|---|---|---|
| `nh` | 價量 | `nh ≥ 60` 且 `vr ≥ 1.5` | 預設「帶量突破」的價量部分 |
| `vu` | 價量 | `vr ≥ 2` 且官方漲幅 ≥ 3% | `vr`、`p` |
| `s3` | 法人 | 法人連買天數 ≥ 3（由 2 變 3 的那天） | `s` |
| `t3` | 法人 | 投信連買天數 ≥ 3 | `ts` |
| `t5` | 法人 | `t5 ≥ a20 × 5 × 5 ÷ 100`（和前端 `t5r` 同一個算式、同樣先四捨五入） | `t5r = 5` |
| `rv` | 營收 | 最新一個月 `ry ≥ 30` 且 `rh > 0`；日期 = 收錄日（見 1-3），在最近 20 個交易日內 | `ry`、`rh` |
| `ae` | 主動 ETF | 相鄰兩個持股日前一日沒有、後一日有；持股日 ≥ 行情日倒數第 5 天 | 持股頁「新」 |

### 1-3 營收日期（Q21-5）

- 日期 = `monthly_revenue.created_at`（本站首次收錄日）。
- **補抓保護**：收錄日晚於法定期限（次月 10 日）5 天以上，就把日期改成次月 10 日。
  - 例：9 月營收在 10/28 一次補抓，日期改為 10/10，不在 11/10 的 20 個交易日窗口內，不會被當成新事件。
  - 10 月營收在 11/05～11/10 逐日收錄，照收錄日。
- 這是「本站收錄」的日期，不一定是公司公布日；README 與說明句都寫明。

### 1-4 和分析師回測的差異

| 項目 | 分析師回測 | 本設計 | 影響 |
|---|---|---|---|
| 量比 | 成交量（張） | **成交額**（同選股） | 價格大跌後放量的情況，成交量比較容易達標 |
| 新高 | 收盤 ≥ 前 60 日最高（含持平） | 收盤 **>** 前 N 日最高（同選股） | 持平不算 |
| 「近 5 日」 | 每檔股票自己最近 5 列 | 全市場最後 5 個交易日 | 停牌股不同 |
| 營收 | 次月 11 日起算、22 天 | 收錄日起算、20 個交易日 | 11/10 時分析師用的是 9 月營收，本設計用 10 月 |
| 法人連買 | 張數 | 金額（同選股） | 正負號相同，幾乎一樣 |

- 11/10 的結果（流動性門檻內、不含處置與無成交）：**面向 ≥ 3 有 8 檔、≥ 2 有 94 檔**。分析師的數字是 13、108（沒有排除處置、無成交）。
- 分析師的 13 檔中，本設計仍為 3 面向的有 4 檔（創意、騰輝電子-KY、藥華藥、廣豐）；其餘 9 檔是 2 面向。差在「價量」或「營收」：
  - 欣興：11/09 漲 4%，以成交量算量比 ≥ 2、以成交額不到 2。
  - 健鼎：分析師用的是 9 月營收；10 月營收沒有同時年增 ≥ 30% 且創新高。
- 驗收 #3 的差異說明到此為止；QA 以本設計的口徑獨立驗算（第八節）。

---

## 二、`latest.json` 的 `hl`

```json
"3443": { ..., "hl": [["vu", "2026-11-04"], ["rv", "2026-11-05", 202610], ["t5", "2026-11-09"]] }
"3661": { ..., "hl": [["rv", "2026-11-10", 202610], ["ae", "2026-11-10", "00992A"]] }
```

- `[種類, 日期 YYYY-MM-DD, 附加值]`，依日期排序（同日依價量、法人、營收、主動 ETF）。
- 附加值：`rv` 為年月（YYYYMM），`ae` 為 ETF 代號，其他沒有。
- 沒有事件的股票**不輸出 `hl` 鍵**。
- 量測（11/10）：931 檔有 `hl`，共 1,253 個事件：

  | 種類 | `s3` | `rv` | `vu` | `t3` | `nh` | `t5` | `ae` |
  |---|---|---|---|---|---|---|---|
  | 事件數 | 662 | 189 | 160 | 122 | 66 | 49 | 5 |

- `latest.json`：729 KB → 761 KB（＋32 KB）。
- 匯出時間：24.6 → 25.3 秒（驗收 #9 上限＋10 秒）。

---

## 三、畫面（`#/rank/hl`）

### 3-1 位置與路由

- 排行頁的模式切換由「排行／選股」改為「**排行／選股／新訊號**」。
- `onModeSeg` 改成 `rank → #/rank`，其他 → `#/rank/{值}`。
- 路由：`#/rank/screen…` → 選股；`#/rank/hl` → `renderHl()`；其他照舊。
- 排行頁的 `#/rank/{排行代號}` 不受影響，排行代號沒有 `hl`。

### 3-2 版面

```
[排行|選股|新訊號]                          [面向 ≥ 3|面向 ≥ 2]
面向 ≥ 3：8 檔；≥ 2：94 檔（20 日均成交額 ≥ 0.5 億，不含處置股、今日無成交）。行情 11/10、法人 11/10
┌──────────┬────┬──────────────────────────────┬──────┬──────┬────────┐
│ 股票       │面向 │ 近期新訊號                         │ 收盤  │ 漲跌  │20日均額 │
│ 創意 3443  │ 3  │ 量比 ≥ 2 漲 ≥ 3% 11/04  10 月營收創新高 11/05 … │7,170 │+6.94%│176.1億 │
```

- 欄位：股票（名稱、代號、產業、處置／注意小標）、面向、近期新訊號、收盤、漲跌、20 日均額。
  - **面向、標籤放在名稱後面**：375 寬時，名稱欄固定，往右第一眼就是標籤（原型第一版把標籤放在後面，手機要橫捲才看得到，已調整）。
- 標籤：`HL_KINDS` 的文字＋灰色日期（`MM/DD`）。

  | 種類 | 標籤文字 |
  |---|---|
  | `nh` | 60 日新高帶量 |
  | `vu` | 量比 ≥ 2 漲 ≥ 3% |
  | `s3` | 法人連買 3 日 |
  | `t3` | 投信連買 3 日 |
  | `t5` | 投信 5 日買超 ≥ 成交額 5% |
  | `rv` | 「10 月營收創新高」（月份取附加值） |
  | `ae` | 「00992A 新增」 |

- 篩選：`hl` 存在、`!dsp`、`!nt`、`a20 ≥ 0.5`（`a20` 取 `screen.json`，經 `screenRows()` 合併）。
- 排序：面向數遞減，再依 `a20` 遞減。
- 門檻：`tw.hlmin`，預設 `'3'`；切換只重畫本頁。
- 說明句（表下）：

  > 列出最近 5 個交易日（營收為最近 20 個交易日）在價量、法人、營收、主動 ETF 四個面向新出現的事件；同一面向有多個事件只算 1 個面向。「新出現」= 當天符合、前一個交易日不符合，口徑和選股條件相同；60 日新高帶量 = 創 60 日以上新高且量比 ≥ 1.5；營收創新高 = 單月營收創新高且年增 ≥ 30%。營收日期為本站首次收錄日（不一定是公司公布日）；主動 ETF 只涵蓋有持股資料的 8 檔。只描述發生了什麼，不代表之後的走勢。

- 空白：
  - `screen.json` 不存在 →「尚未產生選股資料（screen.json），無法計算 20 日均成交額。」
  - 0 檔 →「目前沒有符合的股票。」

### 3-3 監聽器（第 20 輪的教訓）

- 點列用既有的具名函式 `onRowClick`，`#view` 上重複登記只算一次。
- `hlSeg` 只在 `screen.json` 存在時才綁；`modeSeg` 一定存在。
- 實測：切換門檻兩次後點一列，hashchange **只有 1 次**。

---

## 四、邊界情況

| 情況 | 行為 |
|---|---|
| 法人資料比行情晚一天 | 價量事件到行情日，法人事件到法人資料日；說明列同時寫兩個日期 |
| 今天無成交、停牌 | 價量條件不成立；清單排除 `nt`；停牌（今天沒有資料列）不在 `latest.stocks` |
| 窗口前已連買 | 第 3 天在窗口外就不列（只列由 2 變 3 的那天） |
| 同一面向多個事件 | 標籤都列，面向只算 1 |
| 主動 ETF 第一個持股日、只有一個持股日 | 不產生事件 |
| 持股的海外股票、期貨 | 只看 `ST` 且是台股代號 |
| 營收補抓 | 見 1-3 |
| 12 月營收 | 期限 = 隔年 1/10（測試覆蓋） |
| 新上市不足 20 日 | `vr`、`a20` 為 None → 不成立、不列 |

---

## 五、驗證結果（原型）

| 項目 | 結果 |
|---|---|
| 既有輸出（驗收 #4） | `orig`、`proj` 的 `site/data`：檔案清單相同；`latest.json` 以外 **0 檔不同**（`screen.json`、`stocks/`、`etfp/`、`etfs/` 逐位元組相同）；`latest.json` 去掉 `hl`、`updated_at`、`status` 後相同（`r21/cmp.py`） |
| 和選股一致（驗收 #2） | 11/10 當天的事件逐一對照 `screen.json`、`latest.json`：`nh` → `nh ≥ 60` 且 `vr ≥ 1.5`；`vu` → `vr ≥ 2` 且 `p ≥ 3`；`s3` → `s = 3`；`t3` → `ts = 3`；`rv` → `ry ≥ 30` 且 `rh`。**0 筆矛盾** |
| 匯出（驗收 #9） | 24.6 → 25.3 秒；`latest.json` ＋32 KB |
| 測試 | `proj` 的 `test_iter01`～`21` **21 個全部通過** |
| 反證 | ① `orig` 跑 `test_iter21` → 失敗（沒有 `highlights`）；② 拿掉「前一列不符合」→ `test_price_events` 失敗（`nh` 連續兩天都列）；③ 拿掉 `!x.dsp` → `test_render_hl` 失敗（處置股 1104 出現在第一列） |
| 8001 預覽 | 1024 淺色：8 列、標籤換行、表頭靠左；真實點擊「面向 ≥ 2」→ 94 列、`tw.hlmin = 2`；真實點擊台達電列 → `#/stock/2308`，hashchange 1 次；切換門檻兩次後再點列仍 1 次。375 深色：頁面 `scrollWidth = 375`（表格在卡片內橫捲，和其他排行相同），標籤在名稱旁第 2、3 欄。主控台只有第 20 輪留下的舊紀錄（`renderWatch` 行號 1361，見 `20/04-dev.md`），本次 0 個新錯誤 |

---

## 六、測試案例（`tests/test_iter21.py`，全文見附錄 A）

| 測試 | 內容 |
|---|---|
| `test_price_events` | 自造 70 天序列：60 日新高＋量比 1.6 → `nh`；隔天仍符合不重複；未創新高但量比 2.5、漲 3% → `vu`；窗口前的事件不列 |
| `test_insti_events` | 連買由 2 變 3 → `s3`，第 4 天不列；投信 1 日買超 1.3 億 ≥ 0.25 億 → `t5`；窗口前已連買不列；法人資料晚一天時不產生法人事件 |
| `test_revenue_event` | 收錄日、窗口、年增 < 30、沒有創新高、補抓改用 10 日、12 月跨年 |
| `test_active_event` | 新增、非台股、期貨、第一個持股日、只有一個持股日、`since` |
| `test_export_source` | 常數、`created_at`、`hl` 只在有事件時輸出、逐日呼叫 `price_stats` |
| `test_app_source` | 路由、模式切換、篩選式、`tw.hlmin` 預設 3、說明句、CSS、README；新程式段落不含建議性字眼與「推薦、強勢股、飆股、勝率」 |
| `test_render_hl` | node 執行真正的 `renderHl`、`onSeg`（`$` stub 對畫面上不存在的元素回 null）：門檻 3／2 的列與順序、處置／無成交／均額不足排除、法人兩個事件只算 1 個面向、標籤文字 |

- 舊測試**沒有改**任何斷言（`modeSeg` 沒有被舊測試斷言）。

---

## 七、PG 實作順序

1. **基線**：
   - 記錄資料日、`collect_runs` 最大 `run_id`，確認沒有進行中的收集（`finished_at` 為 NULL 的列 0）。
   - 複製 `export.py`、`app.js`、`app.css`、`README.md` 到 `logs/iter21_before/`。
   - 把專案 `site/data` 複製到 `logs/iter21_base/`。
     - 這份就是目前網站資料；也可以先用基線程式 `export` 一次，讓兩邊只差新程式。
     - 建議先 `export` 一次，因為使用者 11/10 收集後的資料可能已經是最新，PG 要確認。
2. **套用**：附錄 A 的 diff（`patch -p1 --dry-run` 再正式套用），新增 `tests/test_iter21.py`。
3. **測試**：`node --check site/app.js`；`test_iter01`～`21`。
4. **反證**：用暫存副本（不含 `.env`）放 `logs/iter21_before/` 的檔案跑 `test_iter21` → 應失敗。
5. **匯出**：新程式 `python3 -u -m twstock export` 一次，記錄耗時與 `latest.json` 大小。
6. **比對**：
   - 用 `logs/iter21_cmp.py`（即 `r21/cmp.py`）比對 `logs/iter21_base/` 與 `site/data`：`latest.json` 以外 0 檔不同、`latest.json` 去掉 `hl` 後相同。
   - 再對照當天事件和 `screen.json`（第五節的 5 個對應）。
7. **8001 預覽**：專案 `site/`；375、1024，深淺色；項目同第五節。結束時刪除 `tw.hlmin`（若預覽前沒有值）、關閉 8001。
- **允許的寫入**：只有 `export`（1～2 次，寫 `site/data/`）。不執行 `collect`、`history`、`setup-db`、`backup`、還原。

---

## 八、給 QA 的提醒

1. **獨立驗算（驗收 #1）**：
   - 不要 import `highlights`。
   - 自己從個股 JSON（還原收盤、張數 × 收盤的成交額，或直接查 `daily_prices.trade_value`）、`institutional_trades`、`monthly_revenue`、`etf_holdings` 重算最近 5 個交易日的事件與日期，和 `latest.json` 的 `hl` 逐檔比對。
   - 注意口徑：量比用**成交額**、新高用**嚴格大於**、連買用**金額**、`vr` 與 `t5`、`a20` 先四捨五入到 2 位再比較。
   - 個股 JSON 的 `v` 是張（四捨五入），乘收盤會和官方成交額有誤差；量比建議直接用 `daily_prices.trade_value`。
2. **營收補抓**：
   - 9 月營收（10/28 補抓）不應出現任何 `rv`。
   - 10 月營收的日期應落在 11/05～11/10。
3. **主動 ETF**：
   - 11/10 應有 5 筆 `ae`：2891（00981A，11/05）、3045（00982A，11/06）、3044（00403A，11/09）、4551（00981A，11/10）、3661（00992A，11/10）。
   - 若期間有新的持股資料，數字會變。
4. 主控台的第 20 輪舊紀錄見第五節；判斷要看行號或掛錯誤攔截器。
5. 本輪尚未 commit；第 20 輪也尚未 commit，`git diff` 會含兩輪的檔案。只看本輪時，以 `logs/iter21_before/` 比對。

---

## 九、驗收對照（PM 第二節）

| # | 條件 | 設計／原型 |
|---|---|---|
| 1 | 事件判定正確 | 第一節口徑；QA 獨立驗算（第八節） |
| 2 | 和選股一致 | 逐日呼叫 `price_stats`、`streak`；原型 0 矛盾 |
| 3 | 11/10 數量合理 | 8／94；和分析師 13／108 的差異在 1-4 |
| 4 | 既有資料不變 | 原型 0 檔不同 |
| 5 | 篩選與排序 | `test_render_hl` |
| 6 | 點擊、不重複綁定 | 原型實測 hashchange 1 次 |
| 7 | 版面 | 375 深色、1024 淺色 |
| 8 | 用詞 | `test_app_source` |
| 9 | 匯出時間 | ＋0.7 秒 |
| 10 | 單元測試 | 21 個通過 |

---

## 十、對 PM 的調整

1. **名稱「新訊號」**（D31-2）：模式切換用「新訊號」，表頭「近期新訊號」。
2. **欄序**：PM 建議「名稱、收盤、漲跌、標籤、均額」，改為「名稱、**面向、標籤**、收盤、漲跌、均額」（375 寬可讀性）。
3. **營收補抓保護**（1-3）：PM 風險 5 的對策具體化為「晚於次月 10 日 5 天以上改用 10 日」。
4. 其他照 PM。

---

## 附錄 A：完整 diff（`orig` → `proj`；新測試檔全文在後）

```diff
--- a/twstock/export.py	2026-11-09 22:27:15
+++ b/twstock/export.py	2026-11-10 21:59:05
@@ -15,7 +15,7 @@
 import re
 import statistics
 import time
-from bisect import bisect_left
+from bisect import bisect_left, bisect_right
 from collections import Counter, defaultdict
 from datetime import date, timedelta
 from decimal import ROUND_HALF_UP, Decimal
@@ -46,6 +46,7 @@
 ACTIVE_TOP = 20                # 主動 ETF 彙總排行（第 7 輪 F7-2）各區塊的列數
 BREADTH_DAYS = 60              # 市場寬度走勢天數
 NH_DAYS = (240, 120, 60, 20)    # C3：創 N 日新高／新低的 N（由大到小，取符合的最大 N）
+HL_DAYS, HL_REV_DAYS = 5, 20     # 第 21 輪 F21-1：近期新訊號看最近 5 個交易日；營收看最近 20 個交易日
 CONV_MIN = 0.1                  # 融資融券換算：|k − 1| ≥ 10% 才視為官方已換算
 SCREEN_KEYS = ("a20", "vr", "r5", "r20", "r60", "rs20", "rs60", "b20", "b60", "nh", "nl",
                "rm", "ry", "rc", "rh", "r3", "cap", "mb", "m1", "m5", "sb", "s1", "s5", "sr", "mu", "mnt", "pbp",
@@ -1042,6 +1043,65 @@
     l3 = rows[-3:]
     r3 = len(l3) == 3 and l3[0][0] * 12 + l3[0][1] + 2 == y * 12 + m and all(r[4] is not None and r[4] > 0 for r in l3)
     return {"rm": y * 100 + m, "ry": yoy, "rc": cum, "rh": hi, "r3": int(r3)}
+
+
+# ─── 第 21 輪 F21-1：近期新訊號（latest.json stocks[代號].hl）──────────────
+def highlights(d_, adj, tv, pct, net, trust, days, flow_days, idx):
+    """
+    近 HL_DAYS 個交易日「新出現」的價量、法人事件 [[種類, 日期], ...]（舊到新）。
+    逐日用 price_stats、streak 重算，和選股的 nh、vr、a20、s、ts、t5r 同一套口徑；新出現 = 當天符合、該股前一個資料列不符合。
+      nh 創 60 日以上新高且量比 ≥ 1.5；vu 量比 ≥ 2 且漲幅 ≥ 3%；
+      s3 法人連買達 3 日；t3 投信連買達 3 日；t5 投信 5 日買超 ≥ 5 日成交額（20 日均額 × 5）的 5%。
+    價量看行情日 days 的最後 HL_DAYS 天；法人看法人資料日 flow_days 的最後 HL_DAYS 天（法人比行情晚公布）。
+    pct：官方漲跌幅（%）；net、trust：法人、投信買賣超（億，無資料 0）。
+    """
+    if len(days) < HL_DAYS or len(flow_days) < HL_DAYS:
+        return []
+    p_from, f_from, f_to = days[-HL_DAYS], flow_days[-HL_DAYS], flow_days[-1]
+    out, prev = [], {}
+    for i in range(len(d_)):
+        if i + 1 < len(d_) and d_[i + 1] < min(p_from, f_from):
+            continue                                   # 只從窗口前一個資料列開始算
+        st = price_stats(d_[:i + 1], adj[:i + 1], tv[:i + 1], days[:bisect_right(days, d_[i])], idx)
+        vr, a20, fl = st["vr"] or 0, st["a20"], d_[i] <= f_to
+        t5 = _f(sum(trust[max(0, i - 4):i + 1]))
+        now = {"nh": st["nh"] >= 60 and vr >= 1.5,
+               "vu": vr >= 2 and pct[i] is not None and pct[i] >= 3,
+               "s3": fl and streak(net[:i + 1][-30:]) >= 3,
+               "t3": fl and streak(trust[:i + 1][-30:]) >= 3,
+               "t5": fl and a20 is not None and a20 > 0 and t5 >= a20 * 5 * 5 / 100}
+        for k, v in now.items():
+            if v and not prev.get(k, True) and d_[i] >= (p_from if k in ("nh", "vu") else f_from):
+                out.append([k, str(d_[i])])
+        prev = now
+    return out
+
+
+def highlight_revenue(rows, seen, since):
+    """營收事件 [["rv", 日期, 年月]]：最新一個月年增 ≥ 30% 且創新高（同選股 ry、rh），日期 ≥ since。
+    日期 = 本站首次收錄日；晚於法定期限（次月 10 日）5 天以上視為補抓，改用法定期限。"""
+    if not rows:
+        return []
+    y, m, _, _, yoy, _, hi = rows[-1]
+    got = seen.get((y, m))
+    if got is None or yoy is None or yoy < 30 or not hi:
+        return []
+    due = date(y + (m == 12), m % 12 + 1, 10)
+    d = got if got <= due + timedelta(days=5) else due
+    return [["rv", str(d), y * 100 + m]] if d >= since else []
+
+
+def highlight_active(holdings, tw, since):
+    """{股票代號: [["ae", 持股日, ETF 代號], ...]}：主動 ETF 相鄰兩個持股日，前一日沒有、後一日有（同持股頁「新」）；持股日 ≥ since。
+    每檔 ETF 的第一個持股日沒有前一日，不產生事件。"""
+    out = defaultdict(list)
+    for e, (hdates, _, held) in holdings.items():
+        for a, b in zip(hdates, hdates[1:]):
+            if b >= since:
+                for kind, c in held[b]:
+                    if kind == "ST" and c in tw and (kind, c) not in held[a]:
+                        out[c].append(["ae", str(b), e])
+    return out
 
 
 # ─── 第 10 輪 B5：季報（資料庫存累計值，這裡相減成單季；個股與選股共用）──────
@@ -1319,12 +1379,14 @@
             FROM stock_fundamentals f JOIN stocks s ON s.stock_id = f.stock_id) x
         WHERE rn = 1""")}
 
-    revenue = defaultdict(list)
+    revenue, rev_seen = defaultdict(list), defaultdict(dict)
     for r in cur.execute("""
-        SELECT s.stock_code, m.revenue_year, m.revenue_month, m.revenue, m.revenue_mom, m.revenue_yoy
+        SELECT s.stock_code, m.revenue_year, m.revenue_month, m.revenue, m.revenue_mom, m.revenue_yoy, m.created_at
         FROM monthly_revenue m JOIN stocks s ON s.stock_id = m.stock_id
         ORDER BY s.stock_code, m.revenue_year, m.revenue_month"""):
         revenue[r[0]].append([r[1], r[2], r[3], _f(r[4]), _f(r[5])])
+        if r[6] is not None:
+            rev_seen[r[0]][(r[1], r[2])] = r[6].date()       # 第 21 輪 F21-1：本站首次收錄日
     chains, chain_of = _load_chains(cur)
     futures = _load_futures(cur)
     oi = load_oi(cur)
@@ -1396,6 +1458,7 @@
         _write(SITE_DATA_DIR / "etfs" / f"{code}.json", holding_export(code, hdates, summary, held, tw, *etf_names[code]))
     active = stock_active(holdings, tw)
     act_lots = active_trust(holdings, tw, dates[-1])            # B16（第 8 輪 F8-1）
+    hl_act = highlight_active(holdings, tw, b_days[-HL_DAYS])   # 第 21 輪 F21-1
     idx_close = {m: {d: c for d, c, _ in index_rows.get(code, []) if c is not None}
                  for m, code in (("TWSE", "TAIEX"), ("TPEx", "TPEX"))}
     screen = {}           # 條件選股：{代號: SCREEN_KEYS 欄位}
@@ -1514,6 +1577,12 @@
             insti_otc["foreign"] += f_value[-1]
             insti_otc["trust"] += t_value[-1]
             insti_otc["dealer"] += d_value[-1]
+        # 第 21 輪 F21-1：近期新訊號（價量、法人、營收、主動 ETF）
+        hl = sorted(highlights(d_, [float(c[i]) * af[i] if c[i] is not None else None for i in range(len(d_))], tv,
+                               [None if c[i] is None else _pct(c[i], chs[i]) for i in range(len(d_))],
+                               net_value, t_value, b_days, dates, idx_close[info["market"]])
+                    + highlight_revenue(rev_rows, rev_seen.get(code, {}), b_days[-HL_REV_DAYS]) + hl_act.get(code, []),
+                    key=lambda e: e[1])
         # 52 週高低用還原價（B1）
         w52 = [(float(h[i]) * af[i], float(l[i]) * af[i]) for i in range(len(d_))
                if d_[i] >= w52_start and h[i] is not None and l[i] is not None]
@@ -1540,6 +1609,7 @@
             **({"ntc": 1} if any(a["t"] == "notice" for a in alerts.get(code, [])) else {}),
             **({"pe": _f(fund[code][0]), "pb": _f(fund[code][1]), "dy": _f(fund[code][2])}
                if code in fund else {}),
+            **({"hl": hl} if hl else {}),
         }
         mkt = info["market"]
         screen[code] = {**price_stats(d_, [float(c[i]) * af[i] if c[i] is not None else None for i in range(len(d_))],
--- a/site/app.js	2026-11-10 21:33:44
+++ b/site/app.js	2026-11-10 22:02:13
@@ -60,7 +60,7 @@
 const routes = {
   today: renderToday,
   bubble: renderBubble,
-  rank: arg => arg && arg.startsWith('screen') ? renderScreen(arg.slice(6)) : renderRank(arg),   // 第 8 輪：#/rank/screen 條件選股
+  rank: arg => arg && arg.startsWith('screen') ? renderScreen(arg.slice(6)) : arg === 'hl' ? renderHl() : renderRank(arg),   // 第 8 輪：#/rank/screen 條件選股；第 21 輪：#/rank/hl 新訊號
   watch: renderWatch,
   etf: code => code === 'active' ? renderActive() : code ? renderHoldings(code) : renderEtf(),   // 第 7 輪：#/etf/active 彙總排行
   stock: code => window.renderStock(code),
@@ -800,8 +800,8 @@
 const RANK_FILTER = { ry: x => !(x.rm < revMonth()), nh: x => x.nh > 0, dy: x => isNum(x.pe) && x.pe > 0 && x.cap !== 1, pe: x => x.pe > 0 && x.cap !== 1, sr: x => isNum(x.mb) && x.mb >= MARGIN_BASE };
 const RANK_COLS = { vr: ['vr'], nh: ['nh'], rs20: ['rs20'], ry: ['ry'], dy: ['dy', 'pe', 'pb'], pe: ['pe', 'pb', 'dy'], to: ['to', 'mc'] };
 const streakTxt = v => v ? (v > 0 ? '買' : '賣') + Math.abs(v) : '--';
-const modeSeg = v => segHTML('modeSeg', [['rank', '排行'], ['screen', '選股']], v);
-const onModeSeg = () => onSeg('modeSeg', v => { location.hash = v === 'screen' ? '#/rank/screen' : '#/rank'; });
+const modeSeg = v => segHTML('modeSeg', [['rank', '排行'], ['screen', '選股'], ['hl', '新訊號']], v);
+const onModeSeg = () => onSeg('modeSeg', v => { location.hash = v === 'rank' ? '#/rank' : '#/rank/' + v; });
 
 function stockTable(list, span = '1') {
   const k = span === '5' ? '5' : '1', lbl = k === '5' ? '5日' : '1日';
@@ -908,6 +908,35 @@
     '</tbody></table></div>';
 }
 
+// ─── 第 21 輪 F21-1：近期新訊號（latest.json stocks[代號].hl；20 日均額取 screen.json）──────────
+const HL_KINDS = { nh: ['價量', '60 日新高帶量'], vu: ['價量', '量比 ≥ 2 漲 ≥ 3%'], s3: ['法人', '法人連買 3 日'], t3: ['法人', '投信連買 3 日'],
+  t5: ['法人', '投信 5 日買超 ≥ 成交額 5%'], rv: ['營收', '營收年增 ≥ 30% 創新高'], ae: ['主動ETF', '主動 ETF 新增'] };
+const hlTag = ([k, d, x]) => `<span class="hl-tag">${k === 'rv' ? `${x % 100} 月營收創新高` : k === 'ae' ? `${x} 新增` : HL_KINDS[k][1]} <i>${md(d)}</i></span>`;
+const hlDims = x => new Set(x.hl.map(e => HL_KINDS[e[0]]?.[0]).filter(Boolean)).size;
+async function renderHl() {
+  const S = await loadScreen(), min = localStore('hlmin', '3');
+  const base = S ? screenRows().filter(x => x.hl && !x.dsp && !x.nt && isNum(x.a20) && x.a20 >= 0.5).map(x => [x, hlDims(x)]) : [];
+  const cnt = n => base.filter(r => r[1] >= n).length;
+  const list = base.filter(r => r[1] >= Number(min)).sort((a, b) => b[1] - a[1] || b[0].a20 - a[0].a20);
+  const L = App.latest;
+  $('#view').innerHTML = `<section class="sec">
+      <div class="sec-h">${modeSeg('hl')}<span class="sp"></span>${segHTML('hlSeg', [['3', '面向 ≥ 3'], ['2', '面向 ≥ 2']], min)}</div>
+      <div class="muted small tbl-cap">面向 ≥ 3：${fmt(cnt(3))} 檔；≥ 2：${fmt(cnt(2))} 檔（20 日均成交額 ≥ 0.5 億，不含處置股、今日無成交）。行情 ${md(L.date)}、法人 ${md(L.flow_date)}</div>
+      <div class="card">${!S ? '<div class="empty">尚未產生選股資料（screen.json），無法計算 20 日均成交額。</div>'
+        : !list.length ? '<div class="empty">目前沒有符合的股票。</div>'
+        : `<div class="tbl-wrap"><table class="tbl"><thead><tr><th>股票</th><th>面向</th><th class="hl-th">近期新訊號</th><th>收盤</th><th>漲跌</th><th>20日均額</th></tr></thead><tbody>` +
+          list.map(([x, n]) => `<tr data-code="${x.code}">
+            <td class="nm"><b>${esc(x.n)}</b>${alertBadge(x)}<span>${x.code} ${esc(x.i)}</span></td>
+            <td class="num">${n}</td><td class="hl-tags">${x.hl.map(hlTag).join('')}</td>
+            <td class="num ${cls(x.p)}">${pfmt(x.c)}</td>${pctCell(x)}<td class="num">${fmt(x.a20, 1)}億</td></tr>`).join('') + '</tbody></table></div>'}</div>
+      <div class="muted small" style="margin-top:6px">列出最近 5 個交易日（營收為最近 20 個交易日）在價量、法人、營收、主動 ETF 四個面向新出現的事件；同一面向有多個事件只算 1 個面向。
+        「新出現」= 當天符合、前一個交易日不符合，口徑和選股條件相同；60 日新高帶量 = 創 60 日以上新高且量比 ≥ 1.5；營收創新高 = 單月營收創新高且年增 ≥ 30%。
+        營收日期為本站首次收錄日（不一定是公司公布日）；主動 ETF 只涵蓋有持股資料的 ${Object.keys(L.holdings || {}).length} 檔。只描述發生了什麼，不代表之後的走勢。</div></section>`;
+  onModeSeg();
+  if (S) onSeg('hlSeg', v => { localStore('hlmin', null, v); renderHl(); });
+  $('#view').addEventListener('click', onRowClick);
+}
+
 // ─── 第 8 輪 F8-2：條件選股（screen.json 與 latest.json stocks 合併）──────────
 const isNum = v => typeof v === 'number';       // null、undefined 一律不符合（null >= 0 在 JS 是 true）
 async function loadScreen() {
--- a/site/app.css	2026-11-09 21:14:56
+++ b/site/app.css	2026-11-10 22:02:13
@@ -260,3 +260,4 @@
 /* F14-4：原文已包含短句的說明（外層 .note-dup），展開時隱藏短句、只留「說明 ▴」；短句、原文都不改 */
 .note-dup .note[open] summary{font-size:0}
 .note-dup .note[open] summary i{font-size:12px;margin-left:0}
+.tbl td.hl-tags,.tbl th.hl-th{white-space:normal;min-width:12em;text-align:left}.hl-tag{display:inline-block;margin:1px 8px 1px 0;font-size:12px}.hl-tag i{font-style:normal;color:var(--text2)}   /* 第 21 輪 F21-1 */
--- a/README.md	2026-11-10 21:33:44
+++ b/README.md	2026-11-10 22:03:22
@@ -17,7 +17,7 @@
 | `twstock/health.py` | 資料完整性判斷、`check`、執行紀錄、通知 |
 | `twstock/export.py` | 匯出 `site/data/latest.json`、`screen.json`（條件選股與排行擴充用）、`stocks/{代號}.json`、`etfs/{代號}.json`、`etfp/{代號}.json`（第 15 輪 ETF 個股頁） |
 | `twstock/analysis/` | `flow` 資金流象限、`forecast` 依期貨法人未平倉的大盤漲跌預測、`chanlun` 纏論 |
-| `site/` | 網站：今日（含加權與櫃買指數、台指期日 K、期貨法人未平倉、籌碼因子觀察、信用交易、市場寬度）、泡泡圖、排行（含條件選股、融資融券排行、借券排行）、ETF（含主動型 ETF 持股頁、主動 ETF 彙總）、自選、個股頁（含主動 ETF 持有、融資融券與借券賣出圖、借券指標卡、季報卡）。今日頁指數卡下方分「總覽／法人資金／信用估值／期貨」四頁，個股頁頁首下方分「走勢／籌碼／基本面」三頁，瀏覽器會記住上次選的分頁；個股「基本面」的月營收可切換「今年 vs 去年」（逐月對照去年同月與同期累計）和「近 36 個月」。第 13 輪：表格第一欄（名稱）固定，排行、選股、ETF 表的排序欄放在名稱後的第 2 欄，手機不用橫向捲動；較長的口徑說明預設收合，點「說明」展開（防誤讀的句子保持可見）；個股頁頁首列出當天開、高、低、昨收、量，「走勢」分頁只留 52 週高低、市值、週轉率四張卡；首頁「錢流去哪」預設各顯示 5 個產業，可按「顯示全部」。第 14 輪：營收年增排行只列欄名月份與更新的月份（表下列出未列入的檔數），去年同月營收不到 1,000 萬元的標「基期低」；單季 EPS 年增在去年同季 EPS 大於 0、小於 0.1 元時改顯示「基期低（去年同季 X 元）」；期貨卡加期現貨價差、下次結算日、換月標示與價差迷你圖；殖利率一年位置加方向說明；季報進度附申報截止日。第 15 輪：個股季報卡的累計 EPS 年增套用和單季相同的基期規則（去年同期 > 0 且 < 0.1 元顯示「基期低（去年同期 X 元）」，去年同期 ≤ 0 且本期 > 0 顯示「轉盈」）；ETF 可從搜尋、ETF 列表、`#/stock/{ETF 代號}` 進入 ETF 個股頁（原始價 K 線、量、融資融券與借券；見下方 ETF 一段）；期貨卡價差迷你圖的 0 軸加深；季報截止日加星期與週末順延。第 16 輪：今日頁「總覽」最下方加處置／注意股清單（即將處置、處置中、今日注意三組；`latest.json` 的 `alerts`：`d` = [代號, 起日, 迄日, 措施, 原因]、`n` = [代號, 原因]，原因只取第一句、最多 60 字，完整原因在個股頁），注意組預設 10 檔可按「注意顯示全部」；同一檔多段處置重疊時，`dsp` 與清單合併為 [最早起日, 最晚迄日]。第 17 輪：清單加「接近處置（推算）」組（`latest.json` 的 `alerts.w` = [代號, 1 已達條件／0 差一次, 條件文字]），依注意原因的「第 N 款」推算：第一款（6 日累積漲跌幅）連 3 個交易日，或第 1～8 款連 5 日、10 個交易日內 6 次、30 個交易日內 12 次為「已達條件」，再 1 次即達為「差一次」；處置中、即將處置的股票不列；原因解析不到款別的那筆不計入。注意紀錄起點（上市 2026-10-12、上櫃 10-28）之前不足的天數不補，只會少算。只是推算，是否處置以官方公告為準；`export.COUNT_DOWN` = False 時第一款的跌幅不計入「第一款連續」。選股不提供此條件 |
+| `site/` | 網站：今日（含加權與櫃買指數、台指期日 K、期貨法人未平倉、籌碼因子觀察、信用交易、市場寬度）、泡泡圖、排行（含條件選股、融資融券排行、借券排行、近期新訊號）、ETF（含主動型 ETF 持股頁、主動 ETF 彙總）、自選、個股頁（含主動 ETF 持有、融資融券與借券賣出圖、借券指標卡、季報卡）。今日頁指數卡下方分「總覽／法人資金／信用估值／期貨」四頁，個股頁頁首下方分「走勢／籌碼／基本面」三頁，瀏覽器會記住上次選的分頁；個股「基本面」的月營收可切換「今年 vs 去年」（逐月對照去年同月與同期累計）和「近 36 個月」。第 13 輪：表格第一欄（名稱）固定，排行、選股、ETF 表的排序欄放在名稱後的第 2 欄，手機不用橫向捲動；較長的口徑說明預設收合，點「說明」展開（防誤讀的句子保持可見）；個股頁頁首列出當天開、高、低、昨收、量，「走勢」分頁只留 52 週高低、市值、週轉率四張卡；首頁「錢流去哪」預設各顯示 5 個產業，可按「顯示全部」。第 14 輪：營收年增排行只列欄名月份與更新的月份（表下列出未列入的檔數），去年同月營收不到 1,000 萬元的標「基期低」；單季 EPS 年增在去年同季 EPS 大於 0、小於 0.1 元時改顯示「基期低（去年同季 X 元）」；期貨卡加期現貨價差、下次結算日、換月標示與價差迷你圖；殖利率一年位置加方向說明；季報進度附申報截止日。第 15 輪：個股季報卡的累計 EPS 年增套用和單季相同的基期規則（去年同期 > 0 且 < 0.1 元顯示「基期低（去年同期 X 元）」，去年同期 ≤ 0 且本期 > 0 顯示「轉盈」）；ETF 可從搜尋、ETF 列表、`#/stock/{ETF 代號}` 進入 ETF 個股頁（原始價 K 線、量、融資融券與借券；見下方 ETF 一段）；期貨卡價差迷你圖的 0 軸加深；季報截止日加星期與週末順延。第 16 輪：今日頁「總覽」最下方加處置／注意股清單（即將處置、處置中、今日注意三組；`latest.json` 的 `alerts`：`d` = [代號, 起日, 迄日, 措施, 原因]、`n` = [代號, 原因]，原因只取第一句、最多 60 字，完整原因在個股頁），注意組預設 10 檔可按「注意顯示全部」；同一檔多段處置重疊時，`dsp` 與清單合併為 [最早起日, 最晚迄日]。第 17 輪：清單加「接近處置（推算）」組（`latest.json` 的 `alerts.w` = [代號, 1 已達條件／0 差一次, 條件文字]），依注意原因的「第 N 款」推算：第一款（6 日累積漲跌幅）連 3 個交易日，或第 1～8 款連 5 日、10 個交易日內 6 次、30 個交易日內 12 次為「已達條件」，再 1 次即達為「差一次」；處置中、即將處置的股票不列；原因解析不到款別的那筆不計入。注意紀錄起點（上市 2026-10-12、上櫃 10-28）之前不足的天數不補，只會少算。只是推算，是否處置以官方公告為準；`export.COUNT_DOWN` = False 時第一款的跌幅不計入「第一款連續」。選股不提供此條件 |
 | `tests/` | 純邏輯測試（不連網、不連資料庫）：`python3 tests/test_iter01.py`、`python3 tests/test_iter02.py`、`python3 tests/test_iter03.py`、`python3 tests/test_iter04.py`、`python3 tests/test_iter05.py`、`python3 tests/test_iter06.py`、`python3 tests/test_iter07.py`、`python3 tests/test_iter08.py`、`python3 tests/test_iter09.py`、`python3 tests/test_iter10.py` |
 | `docs/iterations/` | 持續優化流程：每一輪分析師、PM、SA、PG、QA 的文件 |
 | `data/concepts.csv` | 自訂概念股（只需放產業鏈沒有的題材，如 CoWoS、矽光子） |
@@ -129,6 +129,7 @@
 - 籌碼因子觀察（大盤漲跌預測）：以外資淨未平倉水位、外資 1 日／5 日增減、投信與自營商 1 日增減（相對近 60 日標準化）做羅吉斯迴歸，預測下一交易日台指期近月日盤漲跌。網站同時顯示 walk-forward 回測命中率與「永遠猜多數方向」的基準；模型沒有勝過基準時，首頁只顯示因子方向，機率與回測收在摺疊區；僅供籌碼面參考，非投資建議。
 - 個股法人：排行可切換 1 日／5 日，提供外資、投信、自營、法人合計的買超／賣超與連買排行；金額 = 張數 × 當日收盤（估算值，與官方公布的買賣金額可能不同）。
 - 條件選股（排行頁「選股」，`#/rank/screen`）：資料來自 `site/data/screen.json`（匯出時計算，0 個外部請求），在瀏覽器合併 `latest.json` 篩選，只做 AND。條件分流動性、價量、技術、法人、信用、基本面、排除七組（技術組為第 18 輪新增），另有 8 組預設（法人連買＋營收創新高、投信認養、帶量突破、多頭排列＋相對強勢、價值高息、營收高成長、籌碼換手、財報優於去年）與 3 組參考（融資追價、軋空觀察、本益比低但 EPS 下滑）。報酬、乖離、均線、新高新低用**還原價格**；量比 = 今日成交額 ÷ 前 20 個交易日平均（無成交日以 0 計），用成交額所以不受面額變更影響；相對大盤 = 個股報酬 − 指數報酬（上市對加權、上櫃對櫃買）。本益比、殖利率、淨值比條件**預設排除 90 天內股本變動**的股票（官方值可能尚未調整），可關閉，關閉後結果列標示「股本變動」。營收以各股最新公布的月份計算，頁面列出各月份檔數；每月 1～10 日是公布期間，各股月份不同，月份混雜時資料日一行加註說明，營收欄標出和欄名不同的月份。第 9 輪新增「淨值比一年位置 ≤ N%」（`screen.json` 的 `pbp`，見估值位置），和其他估值條件一樣預設排除股本變動。第 10 輪新增季報條件 5 個（基本面組）：單季 EPS 年增 ≥ N%、毛利率年增 ≥ N 百分點、近 4 季 EPS > 0、單季 EPS 創 N 季新高、單季 EPS 比去年同季下滑；預設「財報優於去年」= 單季 EPS 年增 ≥ 20% 且毛利率年增 ≥ 0、成交額 ≥ 0.5 億，參考「本益比低但 EPS 下滑」= 本益比 ≤ 15 且單季 EPS 下滑。`screen.json` 新欄：`eq` 最新一季單季 EPS、`ey` 單季 EPS 年增 %（去年同季 ≤ 0 為 null）、`e4` 近 4 季 EPS、`gm` 單季毛利率 %（金融業 null）、`gmy` 毛利率年增（百分點）、`fq` 最新季別（YYYYQQ）、`eh` 單季 EPS 創幾季新高、`fqd` 各季別檔數；null 一律不符合條件。各股最新一季可能不同（財報公布期間），欄名依檔數最多的季別，季別不同的列加小字季別，資料日一行列出各季別檔數，沒有任何季別 ≥ 98% 時加「財報公布期間，各股季別不同」。第 11 輪新增借券條件 2 個（信用組）：借券占股本 ≥ N%（3／5／8，預設 5）、借券 5 日增加 ≥ N 張（500／1,000／5,000，預設 1,000）；`screen.json` 新欄 `lb` 借券賣出餘額（張）、`l1`／`l5` 1 日／5 日增減（張）、`lp` 占股本 %（沒有股數為 null），`head.sd` 為各市場借券資料日。選股「毛利率」「毛利率年增」欄也和單季 EPS 一樣，季別不同的列加小字季別。「重設」回到預設（保留排除處置股、今日無成交、股本變動與預設排序），不是全部清空。條件存在瀏覽器，網址也會帶條件，可用「複製條件連結」分享。排行另加量比、創新高、20 日相對強勢、營收年增、殖利率、本益比最低（後兩者排除虧損與股本變動）。`screen.json` 不存在時這些功能不出現，既有排行照常。第 12 輪新增流動性條件 2 個：市值 ≥ N 億（50／100／500／1,000，預設 100）、週轉率 ≥ N%（1／3／5／10，預設 3）；`screen.json` 新欄 `mc` 市值（億元，收盤 × 目前發行股數）、`to` 週轉率（% = 今日成交股數 ÷ 目前發行股數，今天沒有成交為 0），沒有股數為 null，null 一律不符合。排行「價量」組加「週轉率」（欄位：週轉率、市值；成交額門檻同其他排行）。市值、週轉率都用目前股數，增資、減資前後可能失真。第 14 輪：排行「營收年增」只列營收月份 ≥ 欄名月份（檔數最多的月份）的股票，表下一行寫出未列入的檔數（市場、成交額門檻同排行）；選股的「營收年增 ≥」條件不排除舊月份。`screen.json` 新欄 `rb` 去年同月營收（千元，沒有去年同月為 null）、`eb` 最新一季的去年同季單季 EPS（元，和個股 `fin.q` 第 7 欄同一口徑）。營收年增有值且 `rb` < 10,000 千元（1,000 萬元）時，營收年增欄加「基期低」小標；單季 EPS 年增有值（去年同季 > 0）且 `eb` < 0.1 元時，EPS 年增欄改顯示「基期低」與去年同季 EPS（個股季報卡與柱狀圖提示同規則）。只標示，不排除、不改排序；去年同季 ≤ 0 照舊顯示「轉盈」。第 18 輪新增技術條件 3 個：KD 黃金交叉（K < 20／30／50，預設 20）、RSI(14) ≤ 20／30（預設 30）、RSI(14) ≥ 70／80（預設 70）；`screen.json` 新欄 `k`（K 值）、`kx`（今日 K 由下往上穿過 D 為 1，否則 0）、`rsi`，公式同個股頁，用還原價；今天無成交或根數不足為 null（不符合）。選了這些條件時，結果上方列「今日全市場」各條件的檔數與比例（分母 = 有 K 或 RSI 值的股票），因為急漲急跌時會一次出現上百檔（例：2026-11-06 KD 黃金交叉且 K < 20 有 220 檔、RSI ≤ 30 有 1,017 檔）。不提供預設組合。
+- 近期新訊號（排行頁「新訊號」，`#/rank/hl`，第 21 輪）：匯出時算出每檔股票最近 5 個交易日在四個面向「新出現」的事件，存在 `latest.json` 的 `stocks[代號].hl` = [[種類, 日期, 附加值], ...]（沒有事件的股票沒有這個鍵）。「新出現」= 當天符合、該股前一個交易日不符合，逐日用和選股相同的算法（`price_stats`、連買天數）重算。種類：價量 `nh` 創 60 日以上新高且量比 ≥ 1.5、`vu` 量比 ≥ 2 且漲幅 ≥ 3%；法人 `s3` 法人連買達 3 日、`t3` 投信連買達 3 日、`t5` 投信 5 日買超 ≥ 5 日成交額（20 日均額 × 5）的 5%（法人看法人資料日的最近 5 天）；營收 `rv` 最新一個月年增 ≥ 30% 且創新高，日期為本站首次收錄日（`monthly_revenue.created_at`，晚於次月 10 日 5 天以上視為補抓、改用次月 10 日），看最近 20 個交易日，附加值為年月；主動 ETF `ae` 有持股資料的主動 ETF 相鄰兩個持股日「前一日沒有、後一日有」（同持股頁「新」，每檔 ETF 第一個持股日不算），附加值為 ETF 代號。畫面列 20 日均成交額 ≥ 0.5 億、不含處置股與今日無成交的股票，依面向數（同一面向多個事件算 1 個）、再依 20 日均額排序，可切換面向 ≥ 3／≥ 2（記在瀏覽器 `tw.hlmin`，預設 ≥ 3）。只描述發生了什麼，不代表之後的走勢；不顯示回測數字（分析見 `docs/iterations/21/01-analyst.md`）。`screen.json` 不存在時無法取 20 日均額，頁面顯示尚未產生。
 - 今日頁三大法人卡：上市為證交所 BFI82U 官方買賣金額（含 ETF；外資 = 外資及陸資，不含外資自營商，外資自營商已計入自營商），附近 20 日外資買賣超與連買／連賣天數；上櫃為櫃買 `insti/summary` 官方買賣金額（第 9 輪，2026-07-31 起；`latest.json` 的 `insti_official_tpex`，結構同 `insti_official`），另列一行（合計、外資、投信、自營）與上櫃外資 20 日迷你圖，日期早於網站資料日時標示「尚未更新」；上櫃官方尚無任何資料時才退回張數 × 收盤估算（不含 ETF）。上市、上櫃同一天時可相加，卡片不另列合計。資料表 `insti_amount` 以 `market`（`TWSE`／`TPEx`）區分市場。
 - 今日頁估值位置卡（第 9 輪，`latest.json` 的 `valuation`）：上市、上櫃股票的官方本益比、淨值比、殖利率**中位數**在近一年的位置。窗口 = 最近 242 個有官方本益比資料的交易日；中位數每天分市場計算，本益比、淨值比只計入大於 0 的股票，殖利率計入非空值（含 0）；位置 = 窗口內中位數小於或等於今天的天數 ÷ 天數；今天是窗口最低／最高時顯示「一年最低／最高」；附上市本益比中位數近 60 日迷你圖。**不是加權指數本益比**；本益比用近 4 季 EPS，財報公布期間 EPS 變化也會改變位置；殖利率用去年股利；只是位置，不是買賣訊號。第 10 輪：季報窗口內、當季已有資料時，卡片下方加一行「第 3 季財報已收：上市 N、上櫃 M 家（前一季 X、Y 家）；本益比中位數會隨 EPS 更新而變動」（`latest.json` 的 `fin_progress`：`{q, n: {市場: 家數}, p: {市場: 前一季家數}}`；窗口外或當季 0 家為 null，不顯示）。第 14 輪：`fin_progress.due` = [一般業, 金融業] 申報截止日（取自 `health.FIN_DUE`，年報兩者都是 3/31，只寫一次），括號內加「一般業 11/14、金融業 11/29 截止」，資料日已過的寫「已截止」；殖利率的一年位置加「越高 = 殖利率相對越高」（方向和本益比、淨值比相反；今日頁與個股頁）。第 15 輪：截止日後面加星期（「分別是週六、週日」），截止日是週六、週日時寫「遇假日可能順延到 下週一」，「已截止」也用順延到下週一的日期判斷（例如 2026 Q3 一般業 11/14 是週六，11/16 當天仍寫「截止」，11/17 起「已截止」）；`fin_progress.due` 仍是名目日期。只處理週末，平日的國定假日不處理（網站沒有休市表）；行政程序法第 48 條規定期間末日為週六時以下週一上午為末日、週日或國定假日以次日為末日，但本站沒有查到證交所、金管會對財報申報期限的個別公告，所以寫「可能」，以官方公告為準。第 12 輪：卡片加「加權本益比（市值加權）」一行（`valuation.TWSE|TPEx.wpe`：`v` 今天值、`p` 一年位置 %、`lo`／`hi` 一年最低／最高、`cov` 計入市值占比 %、`t` [市值最大的計入股票, 占計入市值 %]）。加權本益比 = Σ 市值 ÷ Σ（市值 ÷ 官方本益比），市值 = 收盤 × `stocks.shares`（**目前股數**，歷史日期也用目前股數），只計本益比 > 0 的股票（不含虧損公司、不含 ETF）；窗口與位置定義同中位數。大型股影響大（上市台積電約占 43%），中位數反映一般股票；是本站計算，**不是證交所公布的數字**。
 - 個股頁估值位置（第 9 輪，`stocks/{代號}.json` 的 `val`：`{d, pe|pb|dy: [位置 %, 一年最低, 一年最高]}`）：本益比、淨值比、殖利率指標卡加「一年位置 N%（最低～最高）」，窗口同上，只計入大於 0 的官方值（殖利率 0 = 不配息，不算位置）。今天值為空或 ≤ 0（虧損、無股利）、窗口內有效天數少於 120 天（新上市），或 90 天內股本變動（官方值可能尚未調整）時不顯示。估值說明（第 10 輪改寫）：本益比 = 股價 ÷ 近 4 季 EPS；獲利下降時本益比會升高，獲利大增時本益比（淨值比也可能）會落到一年低點（例如景氣循環股在獲利高峰），不代表股價便宜；有季報卡時加「請對照下方季報卡的近 4 季 EPS 與一年前比較」。淨值比卡也標「資料 MM/DD」（股本變動註記照舊只在本益比、殖利率卡）。第 12 輪：個股頁指標卡加「市值」（≥ 1 萬億顯示兆）與「週轉率」（`stocks/{代號}.json` 的 `mt`：`{d, mc 億元, to %}`，目前股數計算；沒有股數的股票沒有 `mt`，兩張卡顯示 `--`）。
```

### `tests/test_iter21.py`（新檔）

```python
"""第 21 輪（不連網、不連資料庫）：F21-1 近期新訊號。
export 的 highlights、highlight_revenue、highlight_active 用自造資料測邊界；
有 node 時，逐字取出 app.js 的 renderHl 與相依函式，用假的 latest、screen 跑篩選與排序。"""
import json
import re
import shutil
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from twstock import export  # noqa: E402

APP = (ROOT / "site" / "app.js").read_text(encoding="utf-8")
CSS = (ROOT / "site" / "app.css").read_text(encoding="utf-8")
README = (ROOT / "README.md").read_text(encoding="utf-8")

D0 = date(2026, 9, 1)


def _days(n):
    out, d = [], D0
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def _run(adj, tv, pct, net, trust, n_flow=None):
    days = _days(len(adj))
    flow = days[:n_flow] if n_flow else days
    return export.highlights(days, adj, tv, pct, net[:len(flow)], trust[:len(flow)], days, flow, {}), days


def test_price_events():
    n = 70
    adj = [100.0] * n
    tv = [1e8] * n                                       # 每天 1 億
    pct = [0.0] * n
    adj[-3], tv[-3], pct[-3] = 110.0, 1.6e8, 10.0        # 倒數第 3 天：60 日新高、量比 1.6 → nh（vu 不成立：量比 < 2）
    adj[-2], tv[-2] = 111.0, 1.6e8                       # 前一天已符合 → 不是新出現
    adj[-1], tv[-1], pct[-1] = 111.0, 2.5e8, 3.0         # 沒有創新高（不大於前高）、量比 ≥ 2 且漲 3% → vu
    ev, d = _run(adj, tv, pct, [0.0] * n, [0.0] * n)
    assert ev == [["nh", str(d[-3])], ["vu", str(d[-1])]], ev
    # 窗口（最後 5 天）以前的事件不列
    adj2, tv2, pct2 = [100.0] * n, [1e8] * n, [0.0] * n
    adj2[-7], tv2[-7], pct2[-7] = 120.0, 3e8, 5.0
    assert _run(adj2, tv2, pct2, [0.0] * n, [0.0] * n)[0] == []


def test_insti_events():
    n = 40
    adj, tv, pct = [100.0] * n, [1e8] * n, [0.0] * n
    net = [-1.0] * n
    net[-4:] = [1.0, 1.0, 1.0, 1.0]                       # 倒數第 2 天連買達 3 日 → s3；最後一天第 4 日不再列
    trust = [0.0] * n
    trust[-1] = 1.3                                       # 5 日買超 1.3 億 ≥ 20 日均額 1 億 × 5 × 5% = 0.25 → t5（連買只有 1 日）
    ev, d = _run(adj, tv, pct, net, trust)
    assert ev == [["s3", str(d[-2])], ["t5", str(d[-1])]], ev
    # 連買在窗口前就達 3 日 → 不列
    net2 = [1.0] * n
    assert _run(adj, tv, pct, net2, [0.0] * n)[0] == []
    # 法人資料晚一天：最後一天沒有法人資料，不產生法人事件
    net3 = [-1.0] * n
    net3[-3:] = [1.0, 1.0, 1.0]
    assert _run(adj, tv, pct, net3, [0.0] * n, n_flow=n - 1)[0] == []


def test_revenue_event():
    rows = [[2026, 10, 1000, 1.0, 35.0, 20.0, 3]]
    seen = {(2026, 10): date(2026, 11, 6)}
    assert export.highlight_revenue(rows, seen, date(2026, 10, 14)) == [["rv", "2026-11-06", 202610]]
    assert export.highlight_revenue(rows, seen, date(2026, 11, 7)) == []                         # 窗口外
    assert export.highlight_revenue([[2026, 10, 1000, 1.0, 29.9, 20.0, 3]], seen, date(2026, 10, 1)) == []   # 年增 < 30
    assert export.highlight_revenue([[2026, 10, 1000, 1.0, 35.0, 20.0, 0]], seen, date(2026, 10, 1)) == []   # 沒有創新高
    # 補抓：收錄日晚於次月 10 日 5 天以上 → 日期改用次月 10 日
    late = {(2026, 9): date(2026, 10, 28)}
    assert export.highlight_revenue([[2026, 9, 1, 1.0, 40.0, 1.0, 2]], late, date(2026, 10, 1)) == [["rv", "2026-10-10", 202609]]
    assert export.highlight_revenue([[2026, 12, 1, 1.0, 40.0, 1.0, 2]], {(2026, 12): date(2027, 1, 8)}, date(2027, 1, 1)) == [["rv", "2027-01-08", 202612]]
    assert export.highlight_revenue([], {}, date(2026, 1, 1)) == []


def test_active_event():
    d1, d2, d3 = date(2026, 11, 6), date(2026, 11, 9), date(2026, 11, 10)
    held = {d1: {("ST", "2330"): 0}, d2: {("ST", "2330"): 0, ("ST", "3044"): 0, ("ST", "AAPL"): 0, ("FU", "TX"): 0},
            d3: {("ST", "2330"): 0, ("ST", "3044"): 0, ("ST", "2317"): 0}}
    H = {"00403A": ([d1, d2, d3], {}, held), "00999A": ([d3], {}, {d3: {("ST", "1101"): 0}})}   # 00999A 只有一個持股日
    out = export.highlight_active(H, {"2330", "3044", "2317", "1101"}, d2)
    assert dict(out) == {"3044": [["ae", "2026-11-09", "00403A"]], "2317": [["ae", "2026-11-10", "00403A"]]}
    assert dict(export.highlight_active(H, {"3044", "2317"}, d3)) == {"2317": [["ae", "2026-11-10", "00403A"]]}


def test_export_source():
    src = (ROOT / "twstock" / "export.py").read_text(encoding="utf-8")
    assert "HL_DAYS, HL_REV_DAYS = 5, 20" in src
    assert "m.revenue_yoy, m.created_at" in src and "rev_seen[r[0]][(r[1], r[2])] = r[6].date()" in src
    assert '**({"hl": hl} if hl else {}),' in src
    assert "st = price_stats(d_[:i + 1], adj[:i + 1], tv[:i + 1]" in src            # 和選股同一套


def test_app_source():
    assert "arg === 'hl' ? renderHl()" in APP
    assert "[['rank', '排行'], ['screen', '選股'], ['hl', '新訊號']]" in APP
    seg = APP[APP.index("// ─── 第 21 輪 F21-1"):APP.index("// ─── 第 8 輪 F8-2")]
    assert "!x.dsp && !x.nt && isNum(x.a20) && x.a20 >= 0.5" in seg
    assert "localStore('hlmin', '3')" in seg and "$('#view').addEventListener('click', onRowClick);" in seg
    assert "只描述發生了什麼，不代表之後的走勢。" in seg
    for w in ("買進", "賣出", "反彈", "見底", "買點", "超賣", "超買", "推薦", "強勢股", "飆股", "勝率"):
        assert w not in seg, w
    assert ".tbl td.hl-tags,.tbl th.hl-th{white-space:normal" in CSS
    assert "近期新訊號（排行頁「新訊號」，`#/rank/hl`，第 21 輪）" in README and "近期新訊號）" in README


def _grab(name):
    """取出 app.js 的頂層 function、async function 或 const（const 取到結尾為「;」的那一行）。"""
    m = re.search(rf"^(?:async )?function {name}\(", APP, re.M)
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


def test_render_hl():
    node = shutil.which("node")
    if not node:
        print("  （沒有 node，略過 renderHl 執行）"); return
    names = ["fmt", "pfmt", "sgn", "cls", "pctCell", "esc", "md", "alertBadge", "segHTML", "onSeg", "modeSeg", "onModeSeg",
             "screenRow", "screenRows", "MARGIN_BASE", "HL_KINDS", "hlTag", "hlDims", "renderHl"]
    st = lambda n, hl, **k: {"n": n, "i": "其他", "c": 10, "p": 1.0, "hl": hl, **k}
    ev = {"p": ["nh", "2026-11-10"], "f": ["s3", "2026-11-09"], "r": ["rv", "2026-11-06", 202610], "a": ["ae", "2026-11-10", "00981A"]}
    stocks = {"1101": st("甲", [ev["p"], ev["f"], ev["r"]]),                         # 3 面向
              "1102": st("乙", [ev["p"], ev["f"], ["t3", "2026-11-10"], ev["a"]]),   # 3 面向（法人 2 個事件只算 1）
              "1103": st("丙", [ev["p"], ev["r"]]),                                  # 2 面向
              "1104": st("丁", [ev["p"], ev["f"], ev["r"], ev["a"]], dsp=["2026-11-01", "2026-11-14"]),   # 處置 → 不列
              "1105": st("戊", [ev["p"], ev["f"], ev["r"]], nt="2026-11-07"),       # 今日無成交 → 不列
              "1106": st("己", [ev["p"], ev["f"], ev["r"]]),                         # 均額 < 0.5 → 不列
              "1107": {"n": "庚", "i": "其他", "c": 10, "p": 0}}                     # 沒有 hl
    a20 = {"1101": 5.0, "1102": 9.0, "1103": 50.0, "1104": 9.9, "1105": 9.9, "1106": 0.4, "1107": 99}
    js = "\n".join(_grab(n) for n in names) + f"""
const isNum = v => typeof v === 'number';
const App = {{ latest: {{ date: '2026-11-10', flow_date: '2026-11-10', holdings: {{ '00981A': {{}} }}, stocks: {json.dumps(stocks, ensure_ascii=False)} }} }};
const A20 = {json.dumps(a20)};
const view = {{ innerHTML: '', addEventListener() {{}} }};
const $ = s => s === '#view' ? view : view.innerHTML.includes(`id="${{s.slice(1)}}"`) ? {{ addEventListener() {{}}, querySelectorAll: () => [] }} : null;
let MIN = '3';
const localStore = (k, f) => k === 'hlmin' ? MIN : f, onRowClick = () => {{}};
const loadScreen = async () => (App.screen = {{ rows: Object.fromEntries(Object.entries(A20).map(([c, v]) => [c, {{ a20: v }}])) }});
(async () => {{
  const out = {{}};
  for (const m of ['3', '2']) {{ MIN = m; App.rows = null; await renderHl(); out[m] = view.innerHTML; }}
  console.log(JSON.stringify(out));
}})();"""
    o = json.loads(subprocess.run([node, "-e", js], capture_output=True, text=True, check=True).stdout)
    rows = lambda h: re.findall(r'<tr data-code="(\d+)">', h)
    assert rows(o["3"]) == ["1102", "1101"], rows(o["3"])            # 依面向數、再依 20 日均額
    assert rows(o["2"]) == ["1102", "1101", "1103"], rows(o["2"])    # 3 面向在前，2 面向在後
    assert "面向 ≥ 3：2 檔；≥ 2：3 檔" in o["3"]
    assert "00981A 新增 <i>11/10</i>" in o["3"] and "10 月營收創新高 <i>11/06</i>" in o["3"] and "60 日新高帶量 <i>11/10</i>" in o["3"]
    assert 'id="hlSeg"' in o["3"] and 'data-v="hl" class="on"' in o["3"]


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_") and callable(f):
            print("==", n); f()
    print("全部通過")
```
