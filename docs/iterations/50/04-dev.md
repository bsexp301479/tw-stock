# 第 50 輪｜PG：實作紀錄

- 撰寫日期：2026-11-26（週四，凌晨 02:00 前後台北時間）；資料日 2026-11-25（週三，`latest.json` `date` = `flow_date` = 2026-11-25）。
- 依據：`50/01-analyst.md`、`50/02-pm.md`（D186 = A、D187 = A）、`50/03-design.md`、`50/03-design.diff`（632 行）；D188 = A（原樣套用 diff）。
- 守則：
  - 沒有讀、印、複製 `.env`（`export` 由程式自己讀）；沒有 git commit／push／stash／checkout（`git apply` 只套用到工作目錄，沒有 `--index`）。
  - 除 `export` 本身外沒有連資料庫；`export` 只有 SELECT（`export.py` 沒有 INSERT／UPDATE／DELETE／commit，CLI `cmd_export` 只呼叫 `export_all`）。
  - 外部請求 **0 次**：`export.py` 與其 import 的模組只有 `tradingcal.update_calendar` 會發請求，`export` 路徑沒有呼叫它（`export.py` 只 import `is_trading_day`、`load_closed`、`trading_days`）。
  - 沒有碰 8000（使用者的 `twstock serve`，PID 42150，全程都在）。8001 從專案目錄背景啟動做冒煙，結束時關閉。沒有執行 `_archive/`、沒有改系統設定。

---

## 一、套用

- 套用前 `git status --short` 只有 `?? docs/iterations/50/`。
- `git apply --check docs/iterations/50/03-design.diff` 通過後 `git apply`，**沒有手動修改**。
- `git diff --numstat` 和設計第一節逐檔相同：

  | 檔案 | 加／減 |
  |---|---|
  | `twstock/export.py` | 30／3 |
  | `site/app.js` | 6／3 |
  | `site/stock.js` | 1／0 |
  | `site/index.html` | 2／2 |
  | `tests/test_iter49.py` | 1／1 |
  | `README.md` | 2／0 |
  | `docs/iterations/README.md` | 1／0 |
  | `tests/test_iter50.py`（新） | 422 行 |

- 0 變更：`site/app.css`、`tools.js`、`help.js`、`compare.js`、`twstock/collectors/`、`twstock/db.py`、`twstock/health.py`（`git diff --stat` 沒有輸出）。
- 舊測試只改 `tests/test_iter49.py:261` 1 行（拿掉 `"stock.js?v=28633954", `，保留 `help.js`、`compare.js` 兩個鎖），和 D186 一致。
- `?v=` 和 `shasum` 前 8 碼相同，也和設計 2-6 相同：

  | 檔案 | `?v=` |
  |---|---|
  | `app.js` | **692538e8**（原 54952a23） |
  | `stock.js` | **da7fa6ff**（原 28633954） |
  | `app.css` | ce1417aa（不變） |
  | `tools.js` | 0a050889（不變） |
  | `help.js` | a5a5a7e8（不變） |
  | `compare.js` | 1c11197d（不變） |

- `index.html` 的 `https://` 仍 2 個。

## 二、測試（log：`logs/iter50_pg_tests.log`，不 commit）

| 時機 | 範圍 | 結果 |
|---|---|---|
| 套用後、export 前 | `tests/test_iter01.py`～`test_iter50.py` 逐一執行 | **50 個檔全過**；`test_iter50` 印「（latest.json 還沒有 lm：PG 套用後 export 再核對）」「（00403A 還沒有 pm：PG 套用後 export 再核對）」，和設計第八節 3 相同 |
| export 後 | `python3 tests/test_iter50.py` | 通過，**沒有再印「還沒有」**（`test_data_1125`、`test_etf_data` 實際核對 `lm` 與 8 檔 `pm`） |
| export 後 | 50 個檔再跑一次 | **50 個檔全過** |

## 三、export（D187；log：`logs/iter50_pg_export.log`，不 commit）

- 執行前 `pgrep -fl twstock` 只有使用者的 `python -m twstock serve`（8000），沒有 collect／export 在跑。
- `python3 -u -m twstock export`：結束碼 0，耗時 40.1 秒；`✅ 匯出完成：資料日 2026-11-25，個股 2000 檔，類股 34、產業鏈 39、概念 14，台指期 500 天，latest.json 807 KB`。
- 本輪新增的訊息（逐字）：

  ```
    📌 收在漲停 上市 4／上櫃 3、跌停 上市 46／上櫃 54（本站推算；官方 漲停 上市 4／上櫃 3、跌停 上市 46／上櫃 54）
  ```

  本站推算 4 個數和官方完全相同，也和設計 2-3 的副本輸出逐字相同。
- 其他訊息和以往相同（`screen.json 462 KB`、還原事件 1738 筆、ETF 個股 367 檔 5.0 MB、上市「不比價」4 筆的既有警示）。
- `latest.json` 825,883 bytes，和設計 4-2 副本 export 後的大小相同。

## 四、資料核對（唯讀讀 `site/data/`）

- `latest.json` `stocks` 中有 `lm` 的共 107 檔：

  | | 上市 | 上櫃 |
  |---|---|---|
  | `lm = 1`（收在漲停） | 4：1598、2471、6614、7765 | 3：3664、6140、7767 |
  | `lm = -1`（收在跌停） | 46 | 54 |
  | 官方 `breadth.{市場}.o` | `ul` 4、`dl` 46 | `ul` 3、`dl` 54 |

- 2313 = -1；6907、2330 沒有 `lm`；有 `nt` 的列 0 檔有 `lm`；`etfs.rows` 0 檔有 `lm`。和設計 4-2 相同。
- 8 檔主動 ETF（`etfs/*.json` 的 `sum`）：

  | 代號 | `nu` | `pc` | `pm` |
  |---|---|---|---|
  | 00403A | 7.55 | 7.48 | −0.93 |
  | 00411A | 8.15 | 8.40 | 3.07 |
  | 00415A | 6.40 | 6.43 | 0.47 |
  | 00981A | 20.74 | 20.53 | −1.01 |
  | 00982A | 14.95 | 14.88 | −0.47 |
  | 00988A | 12.01 | 12.20 | 1.58 |
  | 00992A | 11.71 | 11.66 | −0.43 |
  | 00997A | 8.49 | 8.87 | 4.48 |

  `pm` 全部和 PM／設計 4-2 相同。

## 五、8001 冒煙（內建瀏覽器，`http://127.0.0.1:8001`，1024 寬、淺色）

- 載入的是新版：`app.js?v=692538e8`、`stock.js?v=da7fa6ff`、`tools.js?v=0a050889`、`help.js?v=a5a5a7e8`、`compare.js?v=1c11197d`。
- 開始前 localStorage = `{}`（分頁原本停在舊的 `#/tools/dt`；進首頁後為 `{"tw.todayTab":"ov"}`）。

| 頁面 | 結果 |
|---|---|
| `#/rank/p+`（漲幅排行） | 6614、6140、2471、7765、7767 的漲跌欄有小字「漲停」（`<span class="sub2">漲停</span>`）；1598、3664 不在預設成交額門檻 0.5 億內的前列，未出現（屬篩選結果，非錯誤）；表尾有排行說明「漲跌欄的「漲停」「跌停」= 收盤等於當天的漲停價、跌停價（本站依參考價 ±10%…）…不標。」 |
| `#/rank/p-`（跌幅排行） | 50 格有小字「跌停」，例 2337 旺宏 `-10.00%跌停`；排行說明同上 |
| `#/today/ov` | 0 個小字（總覽頁的表格沒有收在漲跌停的股票列；`pctCell` 用在排行、族群、選股等 7 處） |
| `#/rank/screen?lm=1` | 條件「今日收在 [漲停價／跌停價]」；符合 **7 檔**（2471、7765、6614、6140、7767、1598、3664） |
| `#/rank/screen?lm=-1` | 符合 **100 檔**（46＋54） |
| `#/stock/6614` | 頁頭漲跌之後有紅色「收在漲停價」（`small up`，`title` = 收盤等於本站依參考價推算的漲停價） |
| `#/stock/2313` | 「收在跌停價」（`small dn`） |
| `#/stock/2330` | 沒有標記 |
| `#/etf/00981A` | 每單位淨值卡「20.74 元｜11/25 收盤 20.53，折價 1.01%」；說明句末尾有「折溢價 = 持股日收盤 ÷ 每單位淨值 − 1，正值為溢價、負值為折價；…跨境 ETF 的淨值晚一個交易日公布，比的是同一個持股日的收盤。」 |
| `#/etf/00997A` | 「8.49 元｜11/24 收盤 8.87，溢價 4.48%」（持股日 11/24） |
| `#/etf/00411A` | 「8.15 元｜11/24 收盤 8.40，溢價 3.07%」 |
| `#/etf/00403A` | 「7.55 元｜11/25 收盤 7.48，折價 0.93%」 |
| 淨值卡小字 class | `s`（沒有上色） |
| 主控台 | 0 錯誤（伺服器 log 只有既有的 `favicon.ico` 404） |

- 結束：localStorage 設回 `{"tw.todayTab":"ov","tw.stockTab":"k"}`（結束前多了 `tw.rank2: "p+"`，已清掉）；`resize_window` preset desktop、colorScheme light；`pkill -f "twstock serve --port 8001"`；`lsof -iTCP:8001 -sTCP:LISTEN` 沒有輸出；8000 仍在。
- 窄螢幕、深色、平盤 `0` 的「折溢價 0%」畫面留給 QA（本輪資料日 8 檔都不是 0）。

## 六、與設計的差異

- 程式、測試、文件：**0 處**，完全照 `03-design.diff` 套用（D188 = A）。
- 冒煙路徑：任務說明「今日頁漲跌排行」實際在 `#/rank/p+`、`#/rank/p-`（今日總覽頁 0 個小字，見第五節），本輪以排行頁驗。
- 沒有其他意外狀況。

## 七、待 commit 檔案（`logs/` 不進 commit；`site/data/` 在 `.gitignore`）

- 修改：`twstock/export.py`、`site/app.js`、`site/stock.js`、`site/index.html`、`tests/test_iter49.py`、`README.md`、`docs/iterations/README.md`
- 新增：`tests/test_iter50.py`、`docs/iterations/50/01-analyst.md`、`02-pm.md`、`03-design.md`、`03-design.diff`、`04-dev.md`

## 八、留給 QA

1. 驗收 7：34 個市場日和 `market_breadth` 的歷史比對（需連資料庫，不在 `test_iter50`）。
2. 驗收 10、14、26、27：1024／375／320 × 淺／深色畫面；`pm = 0` 的「折溢價 0%」寫法只有假資料能看（`test_holdings_page` 已測）。
3. 上線後連看 5 個交易日的「📌 收在漲停…」訊息，追 Q50-1（11/09、11/24 上市各多 1 檔）。
