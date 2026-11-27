# 第 52 輪｜System Analyst：設計

- 撰寫日期：2026-11-27～11-28（實測於 11/27 23:44 起，台北時間；週五晚上排程時段已過）；資料日 2026-11-27。
- 依據：`52/01-analyst.md`（R88～R97、Q52-1～Q52-8）、`52/02-pm.md`（二之一逐字規格、二之二資料契約、驗收 42 條；D207～D219 全 A，D212 = A1＋B1；PM 自行決定 20 點全照 PM）。
- 產出：本檔＋`52/03-design.diff`（1,295 行；在專案根目錄 `git apply --check docs/iterations/52/03-design.diff` 已通過，只有 fixture 原始 HTML 的行尾空白警告，字元照原樣保留）。
- 做法：
  - `rsync -a --exclude .git --exclude .env --exclude _backups --exclude _archive --exclude logs` 把專案複製到 scratchpad `sa52/`（**副本沒有 `.env`**），原型在副本上改。
  - diff 用 `diff -u --label a/… --label b/…` 對專案現有檔案逐檔產生，新檔對 `/dev/null`。另把專案再複製一份 `sa52c/` 後 `git apply`，結果和 `sa52/` 逐檔相同（`diff -rq` 沒有輸出），在 `sa52c/` 跑 `test_iter10`、`test_iter51`、`test_iter52` 都通過。
  - 改前 `tests/test_iter01～51` 全過；改後 `test_iter01～52` **52 個檔全過**（`for f in tests/test_iter*.py; do python3 $f …` 沒有 FAIL）。
  - 資料庫：只有唯讀 SELECT 1 次連線（`OBJECT_ID('quarterly_balance')` = NULL、`stocks` 代號、`quarterly_financials` 2026Q3 各市場代號）。
  - 外部請求：**實際送出 2 次**（第一節）。
  - 預覽：另複製 `site/` 到 scratchpad `sa52p/`，在 2330、2881、7869 的個股 JSON 與 `screen.json` 放入**假的** `bs`／`roe`／`dr`（只在預覽副本），用 `python3 -m http.server 8001 --bind 127.0.0.1` 看；看完已關（`lsof -i :8001`、`:8002` 沒有輸出）。8000 沒碰；localStorage 已恢復為 `{"tw.todayTab":"ov","tw.stockTab":"k"}`，視窗已設回 preset desktop。
  - 專案目錄只新增本檔與 `03-design.diff`。

---

## 一、第 52 輪實測（D207）

### 1-1 請求紀錄

- 一律經 `twstock.fetch.request`（`POST https://mopsov.twse.com.tw/mops/web/ajax_t163sb05`，`expect_json=False`），表單參數和 `fetch_financials` 相同：`encodeURIComponent=1、step=1、firstin=1、off=1、isQuery=Y、TYPEK、year（民國年）、season（01～04）`。每次前後以 `fetch.request_count()` 相減。執行前 `pgrep -fl twstock` 只有使用者的 `twstock serve`（沒有收集在跑）。
- 原始回應只存 scratchpad `raw52/`，不進專案、不寫 DB。

| 次 | 請求 | 結果 | `request_count` 差 |
|---|---|---|---|
| 1 | 上市 115Q3（`TYPEK=sii`、`year=115`、`season=03`） | HTTP 200、`text/html; charset=UTF-8`、**1,365,922 bytes**、1.8 秒；`<h2>上市公司第三季資料</h2>`；`hasBorder` 表 **6 張**、共 **1,085 家** | 1 |
| 2 | 上櫃 115Q3（`TYPEK=otc`） | HTTP 200、**1,069,439 bytes**、1.1 秒；`<h2>上櫃公司第三季資料</h2>`；表 **2 張**、共 **899 家** | 1 |
| 3 | 上市 113Q1 | **沒有送出**：這個指令兩次都被 Claude Code 的權限判斷拒絕（不是網站拒絕）。依規定不繞過，改列 D220 交使用者 | 0 |

- **實際送出 2 次**，沒有重試。另外第 2 次之前有一次執行在 `import` 階段就失敗（scratchpad 腳本檔名 `inspect.py` 蓋到標準函式庫），還沒有走到 `request`，送出 0 次。
- 二之三 A-1 的停止條件：第 1、2 次都**沒有**觸發（有每股參考淨值、有母公司權益欄、有資產與負債欄、單位是千元），所以照常做原型。

### 1-2 表格與欄名（Q52-1、Q52-5）

表的順序和損益表不同（銀行在前、金控在第 4 張），所以解析**不依表的順序、也不辨識業別**（R89），只依欄名取值。每張表第一列是 `<tr class='tblHead'>` 表頭（`公司<br>代號` 去標籤後是「公司代號」）；**兩份回應都沒有分頁重複表頭**（測試以插入一列模擬）。

| 市場 | 表 | 業別（依公司判斷） | 欄數 | 家數 | 資產 | 負債 | 母公司權益 | 權益 |
|---|---|---|---|---|---|---|---|---|
| 上市 | 0 | 銀行（2801…） | 61 | 10 | 資產總額 | 負債總額 | 歸屬於母公司業主之權益合計 | 權益總額 |
| 上市 | 1 | 證券（2855…） | 23 | 3 | 資產總計 | 負債總計 | 歸屬於母公司業主**權益合計**（沒有「之」） | 權益總計 |
| 上市 | 2 | 一般業（1101…） | 23 | 1,053 | 資產總計 | 負債總計 | 歸屬於母公司業主之權益合計 | 權益總計 |
| 上市 | 3 | 金控（2880…） | 58 | 10 | 資產總額 | 負債總額 | 歸屬於母公司業主之權益（沒有「合計」） | 權益總額 |
| 上市 | 4 | 保險（2816…） | 53 | 5 | 資產總計 | 負債總計 | 歸屬於母公司業主之權益合計 | 權益總計 |
| 上市 | 5 | 其他（1409…） | 22 | 4 | 資產總計 | 負債總計 | 歸屬於母公司業主之權益合計 | 權益總額 |
| 上櫃 | 0 | 證券（5864…） | 23 | 7 | 資產總計 | 負債總計 | 歸屬於母公司業主權益合計 | 權益總計 |
| 上櫃 | 1 | 一般業（1240…） | 23 | 892 | 資產總計 | 負債總計 | 歸屬於母公司業主之權益合計 | 權益總計 |

- 每張表最後一欄都是「每股參考淨值」；前面有「待註銷股本股數」「預收股款…約當發行股數」「母公司暨子公司（所）持有之母公司庫藏股股數」（單位：股，不存）。金控表有一欄表頭是空字串（不影響）。
- **上櫃只有證券、一般業 2 張表**（Q52-5 是）。
- 家數和 DB 的 `quarterly_financials` 2026Q3 **代號完全相同**（唯讀 SELECT：上市 1,085、上櫃 899，兩邊互相沒有多出的代號；PM 記的業別家數 ci 1,053、fh 10、basi 10、bd 3、ins 5、mim 4、上櫃 ci 892、bd 7 也一致），全部代號都在 `stocks` 裡（略過 0 家）。
- 2881 富邦金 **不在 115Q3 回應中**（金控 Q3 截止日 11/29，尚未申報；DB 2881 最新也是 2026Q2），所以 2881 的 5 個值沒有樣本，金控用同表的 2880 華南金代替。

### 1-3 單位、數值與答案

- 單位：頁面上金額單位只有一處「單位：新台幣仟元」，股數欄另註「單位：股」。KY 公司上市 91 家、上櫃 30 家，和其他公司同一張表、同一單位（Q52-4：是新台幣千元；1590 亞德客-KY 每股參考淨值 290.23，數量級合理）。
- 金額最大值 10,367,179,018（千元，金控表）→ BIGINT 足夠；每股參考淨值一律 **2 位小數**，範圍上市 −2.25～1,462.73、上櫃 0.12～734.34 → DECIMAL(10,2) 足夠；兩份回應每股參考淨值都沒有「--」。
- **資產 − 負債 − 權益總計 ≠ 0：0 家**（上市、上櫃各表都是 0）。
- **Q52-2（個體報表公司的母公司權益）**：是「--」。上市 70 家（一般業 62、銀行 3、保險 5 家全部）、上櫃 103 家（一般業 102、證券 1）；母公司權益 = 權益總計的另有上市 373、上櫃 382 家。→ R90 的代換會用到，**A-4 說明全文「，沒有子公司的公司用權益總計」保留**。
- **Q52-6（和 TWT48U 申報每股淨值是否相同）**：完全相同 → **A-4「，和頂端股價淨值比用的每股淨值是同一份申報資料」保留**。

| 代號 | 資產總計 | 負債總計 | 母公司權益 | 權益總計 | 每股參考淨值 | 對照 |
|---|---|---|---|---|---|---|
| 2330 台積電 | 10,052,887,514 | 3,009,660,084 | 6,997,901,424 | 7,043,227,430 | 269.85 | 驗收 37 區間 269.63～269.97 內 |
| 2345 智邦 | 228,712,646 | 146,620,328 | 82,013,742 | 82,092,318 | 146.74 | TWT48U 146.74 |
| 3706 神達 | 188,748,110 | 108,172,030 | 78,609,365 | 80,576,080 | 53.84 | TWT48U 53.84 |
| 1437 勤益控 | 14,230,483 | 5,475,311 | 8,753,147 | 8,755,172 | 43.61 | TWT48U 43.61 |
| 6655 科定（上市） | 10,428,438 | 7,032,668 | 3,395,770 | 3,395,770 | 42.87 | TWT48U 42.87 |
| 2880 華南金（金控） | 4,706,062,835 | 4,454,087,914 | 251,972,225 | 251,974,921 | 17.93 | 2881 尚未申報 |
| 2801 彰銀（銀行） | 3,578,823,619 | 3,347,599,244 | 231,224,375 | 231,224,375 | 19.17 | |
| 2851 中再保（保險） | 61,616,617 | 34,855,259 | -- | 26,761,358 | 33.44 | 保險 5 家母公司權益都是 -- |
| 1590 亞德客-KY | 63,788,306 | 5,736,657 | 58,045,663 | 58,051,649 | 290.23 | KY |
| 1413 宏洲（個體報表） | 2,464,436 | 1,346,649 | -- | 1,117,787 | 8.46 | |
| 2314 台揚（負權益） | 2,691,959 | 2,936,456 | -244,497 | -244,497 | -2.25 | 負債比 109.1% |
| 6488 環球晶（上櫃） | 301,635,986 | 155,767,745 | 145,868,241 | 145,868,241 | 276.21 | |

- 6655 在上市回應（PM 表列在第 2 次），值和 TWT48U 相同。
- Q52-3（特別股、面額不是 10 元）回應本身看不出來，照 PM 由 QA 驗收 38 分類列出。

### 1-4 fixture（只刪列，不改字元）

| 檔名 | 大小 | 內容 |
|---|---|---|
| `tests/fixtures/t163sb05_sii_115_03_mini.html` | 54,787 bytes | 6 張表的表頭全留；銀行 2801、2820（--）；證券 2855；一般業 1101、1413（--）、1437、1590（KY）、2314（負權益）、2330、2345、3706、6655；金控 2880；保險 2816、2851（--）；其他 1409；共 16 家 |
| `tests/fixtures/t163sb05_otc_115_03_mini.html` | 17,753 bytes | 2 張表的表頭；證券 5864（--）、6015；一般業 1240、1591（KY）、1777（--）、5347、6488；共 7 家 |

- 精簡腳本 `scratchpad/scripts52/make_fixture52.py`（不進專案）：每張 `hasBorder` 表保留表頭與第一家，再保留指定代號的 `<tr>`，其餘 `<tr>` 刪掉，其他字元原樣。
- 和 PM 的差異：只有 2 個 fixture（113Q1 沒有樣本，D220）；沒有 2881（尚未申報，以 2880 代替）；原始回應沒有分頁重複表頭，所以 fixture 也沒有，由測試在一般業表中間插入表頭列。

---

## 二、改了哪些檔（diff 的 +／−）

| 檔案 | 加／減 | 內容（行號是改後檔案） |
|---|---|---|
| `twstock/collectors/balance.py`（新） | 112／0 | `URL`、`COLS`、`NEED`、`parse_balance`、`fetch_balance`、`merge_balance`、`collect_balance`、`collect_balance_safe` |
| `twstock/collectors/financials.py` | 2／0 | `collect_financials` 的 `return total` 之前：函式內匯入＋呼叫 `collect_balance_safe`（`:129～130`）；既有行一字不改 |
| `twstock/db.py` | 21／1 | `DDL` 在 `quarterly_financials` 之後新增 `quarterly_balance`（`:487～506`，含 2 行註解）；`setup-db` 訊息 1 行（`:663`） |
| `twstock/collectors/history.py` | 48／1 | 匯入 `collect_balance`（`:17`）；`BALANCE`（`:23`）；`run_financials` 預估行（D219，`:76`）；`load_balance_have`、`run_balance`（`:87～118`）；`run_history` 資產負債表段落（`:132～143`） |
| `twstock/__main__.py` | 2／1 | 說明 1 行（`:19`）；`--only` choices 加 `"balance"`（`:214`） |
| `twstock/export.py` | 83／1 | `SCREEN_KEYS` 結尾加 `"roe", "dr"`（`:57～59`）；`fin_ni4`、`bs_equity`、`bs_roe`、`bs_dr`、`bs_stock`、`bs_screen`、`bs_note`、`_load_balance`（`:1602～1678`，在 `screen_build` 之前）；讀表 1 行（`:1889`）；`bs_all` 1 行（`:1936`）；個股 `bs` 1 行（`:1983`）；`screen` 1 行（`:2092`）；📌 1 行（`:2217`） |
| `site/stock.js` | 23／0 | `:395` 呼叫 1 行；`renderBs`（`:937～958`，在 `renderFin` 之後、`renderRevenue` 之前） |
| `site/app.js` | 6／2 | `SCR_COLS` 1 行（`:1208`）；不上色清單改 1 行（`:1236`）；選股條件註解＋2 行（`:1302～1304`）；底部說明改 1 行（`:1421`，只插入 B-3 一句） |
| `site/index.html` | 2／2 | `app.js?v=6cde9106`、`stock.js?v=7c592b0f` |
| `README.md` | 2／0 | 測試指令 1 行、第 52 輪一段 |
| `docs/iterations/README.md` | 1／0 | 第 52 輪一行（PG／QA 之後補） |
| `tests/test_iter52.py`（新） | 580／0 | 17 個測試、24 個反證 |
| `tests/fixtures/t163sb05_*_mini.html`（新） | 95＋95 | 第 1-4 節 |

- 程式合計 **+299／−8**（PM 估 290～330，上限約 770）；新測試 580 行（上限約 580）。**舊測試 0 行**。
- 0 變更：`app.css`、`help.js`、`tools.js`、`compare.js`、`health.py`、`catchup.py`、`fetch.py`、`backup.py`、`daily.py`；`fin_e4`、`fin_stock`、`fin_screen`、`fin_base`、`fin_cum_base`、`fin_single`、`parse_financials`、`merge_financials`、`fetch_financials`、`renderFin`（新測試以 sha1 鎖住；`collect_financials` 拿掉新增的 2 行後 sha1 和改前相同）。

## 三、程式設計

### 3-1 解析 `parse_balance`（F52-1，二之二 B-1）

- 找表、表頭、略過 `len(c) != len(head) or c[0] == "公司代號"`、同代號後者覆寫、無表格時的三種處理（認得的 `<h2>上市／上櫃公司…資料</h2>` 或「查無」→ `{}`；`SECURITY` → `FetchError`；其他 → `SchemaError("mopsov 資產負債表彙總：回應沒有表格")`）都比照 `parse_financials`。`_cells`、`_col`、`TYPEK` 直接從 `financials` 匯入。
- 別名（依實測，取第一個存在的）：

| 鍵 | 別名 | 必要 |
|---|---|---|
| `total_assets` | 資產總計、資產總額 | 是 |
| `total_liab` | 負債總計、負債總額 | 是 |
| `parent_equity` | 歸屬於母公司業主之權益合計、**歸屬於母公司業主權益合計**（實測新增）、歸屬於母公司業主之權益 | 否（整欄沒有 → 全部 None） |
| `total_equity` | 權益總計、權益總額 | 是 |
| `bvps` | 每股參考淨值 | 是 |

- `公司代號` 或任一必要欄缺 → `SchemaError("mopsov 資產負債表彙總：表頭不符（前 4 欄…）")`，整個回應不寫入。
- 數字：金額 `clean_number(…, int)`，每股淨值 `clean_number(…, float)`；「--」、空白 → None。
- 封鎖頁訊息寫「mopsov 回傳封鎖頁面（SECURITY）」（和損益表的文字不同：損益表那句含用詞檢查清單中的詞，新程式不用）。

### 3-2 寫入與附掛（F52-1，B-2、B-3）

- `merge_balance`：`MERGE quarterly_balance … OPENJSON … JOIN stocks st ON st.stock_code = j.stock_code`；`WHEN MATCHED AND EXISTS (SELECT s.五欄 EXCEPT SELECT t.五欄) THEN UPDATE SET 五欄, updated_at = GETDATE()`；`WHEN NOT MATCHED THEN INSERT (…, first_seen)`；參數順序同 `merge_financials`（json, 年, 季, 年, 季, first_seen）。
- `collect_balance(year, quarter, first_seen=None, markets=…)`：每個市場 1 個請求、自己開連線、commit；印 `    📑 {market} {y}Q{q} 資產負債表：回應 N 家，新增或更正 M 家`（有 `stocks` 沒有的公司時接 `，略過 K 家`）；**失敗往外丟**。
- `collect_balance_safe`：對每個市場各自 `try`：
  - `except db.pyodbc.Error` → `    ⚠️  quarterly_balance 寫入失敗（請確認已執行 setup-db）：{str(e) 第一行前 120 字}`
  - `except (FetchError, *PARSE_ERRORS)` → `    ⚠️  資產負債表 {market} {y}Q{q} 未寫入（損益表照常）：{同上}`
  - 不丟例外、沒有回傳值。上市失敗時上櫃照樣抓（被限流時 `fetch.request` 已把主機標成失敗，上櫃那次會立刻 `FetchError`，只多印一行 ⚠️，不會再等退避）。
- **`pyodbc` 用 `db.pyodbc.Error`**（同第 51 輪）。**`PARSE_ERRORS` 從 `daily` 匯入**（`balance.py` 頂端 `from .daily import PARSE_ERRORS`；`daily` 不匯入 `financials`／`balance`，沒有循環）。
- **附掛**（`financials.py`，`return total` 之前新增 2 行）：

```python
    from .balance import collect_balance_safe          # 第 52 輪 F52-1（函式內匯入：balance 匯入本模組的 _cells）
    collect_balance_safe(year, quarter, first_seen, markets)   # 兩個市場的損益表都寫完才抓資產負債表；失敗只 ⚠️，回傳值不變
```

  - 函式內匯入：`balance` 要從 `financials` 取 `_cells`、`_col`、`TYPEK`，放在頂端會循環匯入。
  - 順序 = 損益表 TWSE → 損益表 TPEx → 資產負債表 TWSE → 資產負債表 TPEx（PM 二之十第 2 點）；損益表失敗時例外照舊往外，資產負債表不抓。
  - `collect_financials` 的參數、`run_financials` 的呼叫、`catchup.py:156` 都不改（`test_iter10.py:234`、`:291` 照過）。

### 3-3 DDL 與 setup-db（F52-2）

- 二之二 A 全文，放在 `quarterly_financials` 那段之後（前面 2 行註解）。字串不含 `twse_index`、`CREATE TABLE market_index`、`CREATE TABLE etf_events`；`market_index` 與 `twse_index` 仍相鄰。
- `setup-db` 訊息：`…market_breadth、quarterly_financials、quarterly_balance（第 52 輪）、"`；結尾 `twse_index（第 51 輪）、etf_holding_gaps")` 不變。

### 3-4 history --only balance（F52-3、D219）

- `BALANCE = "balance"`（不進 `DATASET_KEYS`、`ALL_DATASETS`）；`__main__.py` choices `[…, "financials", "balance", "etf", "qfii", "margin", "holdings", "sbl"]`，說明 1 行（PM 逐字）。
- `load_balance_have()`：先 `SELECT OBJECT_ID('quarterly_balance')`，NULL → `None`；否則 `(年, 季, 市場)` 集合。
- `run_balance(start, end, force=False) -> (完成, 錯誤說明, 被限流時該季第一天)`：
  - 資料表不存在 → 印 `❌ 尚未建立 quarterly_balance，請先執行 python3 -m twstock setup-db`，回傳 `(False, "", None)`，0 個請求（`--force` 也一樣先檢查）。
  - 其他同 `run_financials`：`fin_quarters` × `("TWSE", "TPEx")`、已有的略過（`force` 才重抓）、`collect_balance(y, q, None, (m,))` 位置參數；印 `\n📑 資產負債表：待抓 N 次（季別 × 市場）；⏱️  預估約 {N × 4.5 ÷ 60:.1f} 分鐘`。
  - `FetchError` → `"在 {y}Q{q} {m} 停止：疑似被限流封鎖（{e}）"` 與 `date(y, 3q−2, 1)`；`PARSE_ERRORS` → `"在 … 停止：官方欄位不符（{e}），需要修改程式"`。
- `run_history`：季報段落之後新增同樣結構的段落；有說明時印 `❌ {why}`，被限流時下一行接季報段落同一句等待重跑提示，帶 `--force` 時再多一行 `   這次有 --force：重跑會從頭重抓，請改用 --start {該季第一天} 接續。`；做完把 `BALANCE` 拿掉，沒有剩下的就印 `🎉 補抓完成！`。`--only financials balance` → 先季報後資產負債表。
- D219 = A：`run_financials` 的預估行改為 `📑 季報：待抓 N 次（季別 × 市場，每次另抓資產負債表）；⏱️  預估約 {N × 2 × 4.5 ÷ 60:.1f} 分鐘`。

### 3-5 匯出（F52-4）

| 函式 | 規則 |
|---|---|
| `fin_ni4(cum, y, q)` | 近 4 季淨利（`cum` 第 4 欄）：Q4 = 全年；其他 = 本季累計 + 去年全年 − 去年同季累計；缺一 → None |
| `bs_equity(row)` | `row[2]`（母公司權益）不是 None → 它；否則 `row[3]`（權益總計）；row None → None |
| `bs_roe(cum, bal, y, q)` | 檢查順序 `c` → `a` → `i` → `e`；否則 `(_r1(ni4 × 2, e0 + e1), None)`（整數進 Decimal，`ROUND_HALF_UP`） |
| `bs_dr(row)` | 資產 None 或 ≤ 0、負債 None → None；否則 `_r1(負債, 資產)` |
| `bs_stock(cum, bal, tbl)` | `(y, q) = max(cum)`；沒有季報、`bal` 空或 None、`bal` 沒有該季 → None；一般業 `q, roe, roep, (rn), dr, drp, bv, bvp`，其他業別 `q, bv, bvp` |
| `bs_screen(cum, bal, tbl)` | `{"roe", "dr"}`；非一般業、沒有資料 → None |
| `bs_note(exists, bs)` | 📌 一行（二之一 C 兩種，逐字） |
| `_load_balance(cur)` | `OBJECT_ID` NULL → None；否則 `{代號: {(年, 季): (資產, 負債, 母公司權益, 權益總計, 每股淨值)}}` |

- 串接：`_load_financials` 之後 `bal = _load_balance(cur)`；迴圈前 `bs_all = {代號: bs}`（只算 `stocks` 有的代號）；個股 JSON 在 `fin` 那兩行之後 `**({"bs": bs_all[code]} if code in bs_all else {})`；`screen[code]` 在 `fin_screen` 之後 `**bs_screen(…)`；`SCREEN_KEYS` 最後加 `"roe", "dr"`。
- 業別一律用 `fin_meta[code][0]`（最新一季 `industry_tbl`）。

### 3-6 畫面（F52-5）

- `stock.js:395`：`  if (tab === 'fund' && F && data.bs) renderBs(data.bs, F);`（`:394` 與季報卡模板一字不改）。
- `renderBs(B, F)`：`B.q !== F.q[F.q.length - 1][0]` 就 return；3 格的標籤、數值、副標、title 與說明短句、全文完全照 PM 二之一 A-2～A-4（全文兩句【實測】都保留，第 1-3 節）。`$('#finBox > .metrics').insertAdjacentHTML('afterend', row)`；說明 `$('#finBox').insertAdjacentHTML('beforeend', …)`，`noteHTML(short, full)` 用變數（字面呼叫仍 8 個）。只用 `fmt`、`noteHTML`；沒有 `.at(`。
- `app.js`：選股 2 個條件（`et` 之後、`pe` 之前，前面 1 行註解）、`SCR_COLS` 1 行（`gmy`／`eh` 之後）、不上色清單插 `'roe', 'dr'`（`'eh'` 與 `'lb'` 之間）、底部說明插 B-3 一句，全部逐字照 PM。
- 預覽（假資料，1024 寬）：季報卡 6 格下一列 3 格（3 格 top 相同），說明在原說明之後；選股 `#/rank/screen?roe=15&dr=50` 有 ROE、負債比兩欄，`<td class="num ">` 沒有漲跌色；主控台沒有錯誤。
- 手機（A-5）：375 寬、320 寬都是 2＋1；「ROE（近 4 季）」標籤高度 18 px（**沒有換行**）；`scrollWidth = innerWidth`（375、320）。

---

## 四、新測試 `tests/test_iter52.py` 與反證

| 測試 | 驗收 | 內容 |
|---|---|---|
| `test_parse` | 3、4 | 2 個 fixture 家數 16／7；2330、2880、6488 的 5 個值；--（1413、2851、2820、5864、1777）→ None；負權益 2314；4 檔與 TWT48U 對照值；插入的分頁表頭不算一家；同代號後者覆寫 |
| `test_abnormal` | 5 | 只有頁頭、只有表頭、「查無」→ `{}`；`SECURITY` → `FetchError`；未知頁 → `SchemaError`；每股參考淨值、資產、負債、權益、公司代號任一改名 → `SchemaError`；母公司權益 3 種欄名都改掉 → 照常解析、全部 None |
| `test_fetch_params` | — | URL 與表單參數 |
| `test_merge_and_ddl` | 6 | MERGE 字串、更新段不含 `first_seen`、參數順序；DDL 全文、位置、三段鄰接；`setup-db` 訊息 |
| `test_attach` | 7、10 | 假請求＋假連線執行 `collect_financials(2026, 3, D, 兩市場)`：URL 順序 sb04 sii → sb04 otc → sb05 sii → sb05 otc、回傳值 = 損益表家數、DB commit 順序、2 行資產負債表 📑 逐字；`collect_financials` 既有行、`parse_financials` 等 sha1 不變 |
| `test_isolation` | 8 | `FetchError`、`SchemaError`、`KeyError`、`pyodbc.Error` 各一次：回傳值不變、損益表已 commit、⚠️ 逐字、上櫃照抓；`catchup.execute_plan` 時 `undated["financials"]` 照寫、`errors` 為空 |
| `test_income_failure` | 9 | 上市損益表 `FetchError` → 例外往外、0 個資產負債表請求 |
| `test_history` | 11～13 | 22 次（位置參數、`first_seen` None）、全部已有 0 次、缺一個只抓一個、`force` 22 次、資料表不存在 0 次＋訊息、限流訊息（含 `--force` 那行）、欄位不符、`financials balance` 先後、D219 預估行（22 次 → 3.3 分鐘）；`BALANCE` 不在資料集；choices 與說明 |
| `test_export` | 14～21 | `fin_ni4`、ROE（20.0、四捨五入 16.7、混用代換）、`rn` 4 種與順序、負債比、`bs` 鍵與順序、非一般業、不輸出、`screen`；舊函式 sha1；`SCREEN_KEYS[-2:]` |
| `test_note_and_wiring` | 22 | 📌 3 種逐字；串接位置 |
| `test_load` | — | `_load_balance` 表不存在 → None、列轉字典 |
| `test_card` | 23～27、31 | node 執行 `renderFin`＋`renderBs`：一般業 3 格逐字、位置、說明逐字；`fh`「不適用」；`rn` a／c／i／e／未知；null 副標；負數；季別不同與沒有 `bs` 時和只跑 `renderFin` 逐字相同；沒有 `--%`、`null`、`undefined`、`NaN`；`renderFin` sha1、呼叫行、`noteHTML` 字面 8 個 |
| `test_screen` | 28、29 | 條件字面逐字與位置；`roe ≥ 15`、`dr ≤ 50` 篩選（null 不選）；`scrQuery`／`scrParse`；欄位格式與 `（Q2）`；不上色清單；底部說明 |
| `test_words_node14` | 30、31 | 新程式片段、README 新段落不含用詞清單（`test_iter48`／`test_iter45` 清單＋強、弱、名次、安全、危險、惡化、獲利能力）；新前端片段沒有 `.at(` 等 |
| `test_version_and_docs` | 32、35 | 6 個 `?v=`、舊值不在、`https://` 2 個、script 順序；README 段落關鍵字、測試指令、不寫其他輪次 |
| `test_site_data` | 37 | 匯出後才檢查（`bs` 緊接 `fin`、`bs.q` = `fin.q` 最後一列、2330 `bv` 區間、`screen` 對應）；尚未匯出時略過並印一行 |
| `test_contrast` | — | 24 個反證（下表） |

| 反證（原始碼改壞） | 被哪個檢查擋下 |
|---|---|
| 用損益表的業別表頭辨識 | `check_parse` |
| 不略過重複表頭 | `check_parse` |
| 母公司權益欄列為必要 | `check_abnormal` |
| 封鎖頁當成 0 家 | `check_abnormal` |
| 資產負債表放在每個市場損益表之後（順序錯） | `check_attach` |
| 資產負債表家數算進回傳值 | `check_attach` |
| 不攔 `pyodbc.Error` | `check_isolation` |
| 只抓第一個市場 | `check_isolation` |
| 回補用關鍵字參數 | `check_history` |
| 資料表不存在仍發請求 | `check_history` |
| 季報預估沒有乘 2（D219） | `check_history` |
| `--force` 不提示改用 `--start` | `check_history` |
| ROE 用單季年化 | `check_export` |
| ROE 只用期末權益 | `check_export` |
| `rn` 順序反過來 | `check_export` |
| 非一般業也輸出 `roe` | `check_export` |
| 母公司權益 -- 不改用權益總計 | `check_export` |
| 📌 缺季別寫 0 | `check_note` |
| `fmt(null, 1) + '%'`（出現 `--%`） | `check_card` |
| 季別不同仍顯示 | `check_card` |
| 3 格插在說明之後 | `check_card` |
| 負債比門檻用 `<` | `check_screen` |
| 用詞（清單中的任一詞） | `check_words` |
| node 14 不支援的 `.at(` | `check_words` |

- PM 列的「用關鍵字參數改 `run_financials` 的呼叫」由 `test_iter10.py:291`（`lambda *a`）與本檔 `check_history` 的 `k == {}` 共同擋；「`renderBs` 改到 `renderFin`」由 `renderFin` sha1 擋；「新增 `noteHTML('…'` 字面呼叫」由字面 8 個擋（這三項不另列反證）。
- 驗收 10「`test_iter03.World` 請求清單和改前相同」：`test_iter03`、`test_iter10` 不改且通過（假世界季報已齊，不會進 `collect_financials`）。

---

## 五、PM 驗收 42 條對照

| # | 狀態 | 說明 |
|---|---|---|
| 1 | 符合 | 實際 2 次（≤ 3）；第 3 次沒有送出（D220）；原始回應只在 scratchpad |
| 2 | 符合 | 第一節；停止條件都沒有觸發 |
| 3 | **部分** | fixture 2 個（不是 3 個，D220）；沒有 2881（尚未申報，改 2880）；重複表頭由測試插入 |
| 4、5 | 符合 | `test_parse`、`test_abnormal` |
| 6～9 | 符合 | `test_merge_and_ddl`、`test_attach`、`test_isolation`、`test_income_failure` |
| 10 | 符合 | 舊測試通過 |
| 11～13 | 符合 | `test_history` |
| 14～21 | 符合 | `test_export`、`test_load` |
| 22 | **位置不同** | 📌 逐字符合；位置在「⚠️ 還原係數」「⚠️ 上市官方漲跌」兩種條件式警告之後、「✅ 匯出完成」之前（第六節差異 1） |
| 23～29、31 | 符合 | `test_card`、`test_screen`、`test_words_node14` |
| 30 | 符合 | 新字串用詞檢查；本檔也已逐一比對 |
| 32 | 符合 | `app.js?v=6cde9106`、`stock.js?v=7c592b0f`（= `shasum` 前 8 碼）；其他 4 個不變 |
| 33 | 符合 | 舊測試 0 行；新檔 `test_iter52.py`＋2 個 fixture |
| 34 | 符合 | 52 個測試全過（PG 回補、匯出前後再各跑一次） |
| 35 | 符合 | README 段落、測試指令、`docs/iterations/README.md` 一行、`__main__.py` 說明 |
| 36～40 | PG／QA | 實際資料；`test_site_data` 在匯出後自動檢查 37 的一部分 |
| 41 | 符合（SA 部分） | SA 2 次；專案目錄沒有原始回應 |
| 42 | 符合（SA 部分） | 8001 已關、8000 沒碰、desktop、localStorage 已恢復 |

---

## 六、和 PM 的差異（逐點理由）

1. **📌 位置**：PM 要「接在 📌 證交所指數（及類股名稱對不到）之後」。原型照放時 `test_iter51.py:303～309`（`check_wiring`）會失敗：它把「📌 ETF 個股」到 `    if bad_all:` 之間的原始碼抽出來 `exec`，新的一行用到 `bs_note` 等名稱 → `NameError`。不改舊測試的做法是把新行放到 `if miss_all:` 區塊之後、`✅ 匯出完成` 之前。平常沒有那兩種 ⚠️ 時，畫面上仍然緊接在證交所指數之後。
2. **fixture 2 個、沒有 2881**：第 3 次請求沒有送出（D220）；2881 尚未申報 Q3，以同表的 2880 代替；原始回應沒有分頁重複表頭，改由測試插入。檔名照 PM（`t163sb05_sii_115_03_mini.html`、`t163sb05_otc_115_03_mini.html`）。
3. **別名多一個**：母公司權益加「歸屬於母公司業主權益合計」（證券業表，上市、上櫃都是這個寫法；PM 授權依實測增減）。
4. **封鎖頁訊息文字**：損益表那句含「安全」（用詞清單中的詞），新程式改寫「mopsov 回傳封鎖頁面（SECURITY）」。只是訊息文字。
5. **`bs_all` 先算好**：PM 寫法是在個股 JSON 那行用 `:=`。改成迴圈前先算一個字典（1 行），個股 JSON 與 📌 共用同一份結果，迴圈內不必多一行收集；`screen` 照 PM 呼叫 `bs_screen`。結果相同。
6. **`run_balance` 回傳 3 個值**（多「該季第一天」）：PM 要 `--force` 停下時提示 `--start 該季第一天`，`run_history` 需要知道停在哪一季。
7. **測試行數**：580 行，PM 估 330～400（上限約 580）。為了逐字驗 3 格的 4 種 `rn`、title、說明全文、24 個反證；沒有超過上限。
8. **`financials.py` 用函式內匯入**：PM 說只在 `return total` 之前新增呼叫；匯入放在函式內的同一處（理由見 3-2），沒有動檔案頂端。

---

## 七、PG 上線步驟（寫 DB 的步驟要先取得使用者同意）

| 步驟 | 指令 | 說明 |
|---|---|---|
| 0 | `pgrep -fl twstock` | 確認沒有收集在跑；避開排程（週一至週五 17:30、19:30、21:45、22:30 前後 20 分鐘） |
| 1 | `git apply docs/iterations/52/03-design.diff` → `for f in tests/test_iter*.py; do python3 -u $f >/dev/null 2>&1 \|\| echo FAIL $f; done` | 52 個全過才往下；有失敗就停下回報 |
| 2 | （**徵求同意**）`python3 -u -m twstock backup` | 記檔名、大小、VERIFYONLY 結果 |
| 3 | （**徵求同意**）`python3 -u -m twstock setup-db` | 建 `quarterly_balance`；套用後盡快做（之前排程收到也只會 ⚠️） |
| 4 | （**徵求同意**）`python3 -u -m twstock history --start 2024-01-01 --only balance 2>&1 \| tee logs/backfill_balance_52.log` | 22 次，預估約 1.6 分鐘。**第 1 個請求就是上市 113Q1**（D220）：若欄名不同會在第 1 次印「官方欄位不符」並停下，不會再送請求 → 回報，不要跳過那一季 |
| 5 | 唯讀 SELECT | 驗收 36、37（每個季別 × 市場的列數和 `quarterly_financials` 比較、資產 − 負債 − 權益 ≠ 0 的列數、`parent_equity` NULL 列數） |
| 6 | `python3 -u -m twstock export` | 0 外部請求；看 📌 `資產負債表 2026Q3：個股 N 檔；一般業 ROE …` |
| 7 | 全部測試再跑一次 | `test_site_data` 會檢查 2330 的 `bs` |

- 被限流停下：等 30 分鐘以上用同一個指令重跑（已寫入的季別 × 市場會略過）；先回報實際請求數與停下的季別。
- 金融業 2026Q3（截止 11/29）：回補時多數金控還沒有 Q3；之後每晚季報收集會連同資產負債表一起補（窗口到 11/30）。

---

## 八、需要使用者決定的事項

### D220 上市 113Q1 的實測沒有做，怎麼確認舊季別的欄名

- 現況：D207 的第 3 次請求（上市 113Q1）在 SA 階段被 Claude Code 的權限判斷擋下兩次，沒有送出；依規定沒有繞過。115Q3 兩份樣本完全符合，但 113Q1～115Q2 的欄名沒有看過（損益表 113 年保險業欄名曾不同）。
- **A（預設）**：不另外實測。PG 回補（步驟 4）的第 1 個請求就是上市 113Q1；欄名不同時 `parse_balance` 丟 `SchemaError`，`history` 印「官方欄位不符」並停下，不寫入、不再送請求，損失最多 1 個請求。之後再由 SA 依該回應加別名。理由：回補本身就是同一個請求，不必多送一次；停下機制已有測試（`test_history`）。
- **B**：PG 套用前，由使用者自己在終端機執行一次 113Q1 請求（經 `fetch.request`），SA 看完再補 fixture 與別名。多 1 個請求、多一次交接。
- **C**：回補範圍縮成 2025Q1 起（`--start 2025-01-01`，18 次）。ROE 的 `roep`（一年前 ROE）需要 2024Q3 權益，2026Q3 的 `roep` 會全部是 null。

---

## 九、疑慮與備註

- 實測只看了 115Q3；中間 9 季的欄名同 D220 的風險，靠回補時的「欄位不符就停」處理。
- 2881 等金控的 Q3 資產負債表沒有樣本；金控表欄名（資產總額、歸屬於母公司業主之權益）已由 2880 等 10 家確認。
- `collect_balance_safe` 在上市被限流時，上櫃那一次也會立刻失敗（`fetch` 已標記主機），兩行 ⚠️；季報收集期間隔晚會再抓。
- 開發原型時有一次反證寫法錯誤，讓 scratchpad 副本的 `history.load_balance_have` 真的呼叫了 `db.connect()`；副本沒有 `.env`，連線以登入失敗結束（沒有任何查詢或寫入）。已改正，現在的測試全部用假資料，不連資料庫。
- `git apply --check` 會列出 fixture 的行尾空白警告（原始 HTML 本來就有，保留原樣；第 10 輪 fixture 相同）。

## 使用者決定（2026-11-28）

- D220：A。舊季別不另外實測。PG 回補的第 1 個請求就是上市 113Q1；如果欄位不符，回補會停下來、不寫入，PG 要回報。
- SA 與 PM 的 8 點差異全部接受。
