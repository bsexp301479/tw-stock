# 第 47 輪｜PG：實作紀錄

- 撰寫日期：2026-11-23（週一）；資料日 2026-11-23（週一）
- 依據：`47/03-design.md`、`47/03-design.diff`（734 行）；D147～D155 全 A；使用者同意 SA 第四節 7 點差異與 `test_iter47.py` 461 行。
- 守則：
  - 依 D150 = A 執行 `python3 -u -m twstock export` 1 次（只讀資料庫、只寫 `site/data/`）。外部請求 0 次、`collect` 0 次。
  - 沒有讀、印、複製 `.env`；沒有 git commit／push／stash／checkout／reset（`git apply` 只套用到工作目錄，沒有 `--index`）。
  - 沒有碰 8000。8001 從專案目錄背景啟動做冒煙測試，結束時關閉（`lsof` 沒有 LISTEN）。

---

## 一、套用

- `git apply --check docs/iterations/47/03-design.diff` 通過後 `git apply`，**沒有手動修改**。
- `git diff --numstat` 和設計第一節逐檔相同：

  | 檔案 | 加／減 |
  |---|---|
  | `twstock/export.py` | 8／0 |
  | `site/stock.js` | 4／2 |
  | `site/app.js` | 39／6 |
  | `site/help.js` | 2／1 |
  | `site/app.css` | 1／0 |
  | `site/index.html` | 4／4 |
  | `tests/test_iter45.py` | 3／3 |
  | `README.md` | 2／0 |
  | `docs/iterations/README.md` | 1／0 |
  | `tests/test_iter47.py`（新） | 461 行 |

  `git diff --stat`：9 files changed, 64 insertions(+), 16 deletions(-)（不含新檔）。
- 舊測試：`git diff --stat tests/` 只有 `tests/test_iter45.py | 6 +++---`，改的是 `:30`、`:49`、`:122` 三行（`git diff -U0` 的 hunk 標頭確認），和使用者同意的範圍相同。
- `?v=` 和 `shasum` 前 8 碼相同，也和設計第一節相同：

  | 檔案 | `?v=` |
  |---|---|
  | `app.css` | **07335b75**（原 7f4315c2） |
  | `app.js` | **9b18c12f**（原 14621fbf） |
  | `stock.js` | **7e6c6a13**（原 10ba5306） |
  | `tools.js` | 64e7360f（不變） |
  | `help.js` | **a5a5a7e8**（原 55e93876） |

## 二、測試

- 匯出前：`tests/test_iter01～47` 共 47 個檔全部通過（約 51 秒）；`test_iter47.test_site_data` 走「尚未用第 47 輪匯出，略過」。
- 匯出後：47 個檔再次全部通過；`test_iter47` 的 `test_site_data` 這次實際核對 37 檔與 5 個例子，`test_contrast` 29 個反證全過。

## 三、匯出（D150 = A）

- 執行前讀過呼叫鏈：`__main__.cmd_export` → `export.export_all`。`export.py` 39 個 `execute` 的 SQL 開頭全是 `SELECT`，沒有 `commit`／`executemany`；連線 `db.connect()` 預設 `autocommit=False`。用到的 `health.build_status`（`load_closed`、`load_state`、`collected_at`、`load_snapshot`、`dataset_status`、`site_closed`）、`health.share_exists`、`tradingcal.load_closed`／`is_trading_day`／`trading_days`、`analysis.forecast` 只有 `SELECT`；會寫資料庫的 `health.write_run`／`finish_run`、`tradingcal.update_calendar`／`add_adhoc`／`remove_adhoc` 不在匯出路徑。
- 匯出前備份到 scratchpad `r47pg/before/`：`latest.json`、`screen.json`，以及 `stocks/`、`etfp/`、`etfs/` 2,375 檔的 sha1（`sha1.txt`）；匯出後的 sha1 存 `r47pg/after_sha1.txt`。
- 結果：資料日 2026-11-23，個股 2000 檔，ETF 個股 367 檔 4.9 MB，`latest.json` 808 KB，耗時 28.2 秒（和 SA 副本相同）。上市「找不到事件」4 筆（1435、5236、8105、8908）為既有訊息。
- 核對：

  | 項目 | 結果 |
  |---|---|
  | `latest.json` 頂層 `nx` | 37 檔（股票 19、ETF 18），鍵依代號排序，是 `latest` 最後一個鍵 |
  | 和各檔 JSON `nx[0]` 一致 | 37／37；個股／ETF JSON 有 `nx` 的檔數也是 37 |
  | 1437 | `["2026-12-03","息",0.624652]` |
  | 6523 | `["2026-11-26","息",4]`（原始 JSON 是 `4`，不是 `4.0`） |
  | 00901 | `["2026-11-24","息",7]` |
  | 00953B | `["2026-12-03","息",null]` |
  | 2345 | `["2026-12-04","權",0]` |
  | `stocks/`、`etfp/`、`etfs/` 2,375 檔 | sha1 和匯出前 0 檔不同 |
  | `screen.json` | `cmp` 相同 |
  | `latest.json` 拿掉 `nx` | 只有 `status.exported_at` 不同（21:36:33 → 22:46:18） |
  | `latest.json` 大小 | 825,922 → 827,167 bytes（+1,245 bytes，和 SA 相同） |

- `site/data/` 在 `.gitignore` 內，`git status` 不顯示。

## 四、8001 冒煙（內建瀏覽器，`http://127.0.0.1:8001`）

- 載入的是新版：`app.js?v=9b18c12f`、`stock.js?v=7e6c6a13`、`tools.js?v=64e7360f`、`help.js?v=a5a5a7e8`、`app.css?v=07335b75`。
- 暫時設自選 2330、2454、3105、1437、2881、6523、0050、00878、00679B、00953B，持股 6523 1,000 股、1437 2,500 股、0050 2,000 股。

| 頁面 | 結果 |
|---|---|
| `#/stock/1437` 頁頭 | `即將除息 12/03`（`a.pill.pill-nx`，`href="#/tools/dv?c=1437"`，title「即將除息 12/03：現金股利 0.624652 元（預告，以公司公告為準）」），在「上市」之前；點了到 `#/tools/dv?c=1437`，試算頁帶出勤益控 |
| `#/stock/00901`、`6523`、`00953B`、`2345` | `即將除息 11/24`（配息 7 元）、`即將除息 11/26`（4 元）、`即將除息 12/03`（金額待公告）、`即將除權 12/04`（含現金增資）；都沒有 `data-gk` |
| `#/stock/2330` | 沒有標籤 |
| `#/watch` 即將除權息卡 | 在 ETF 表之後、`w-ev` 之前；3 列：達爾膚 11/26 除息 現金股利 4 元 估計可領 **4,000** 元；勤益控 12/03 除息 現金股利 0.624652 元 估計可領 **1,561** 元；群益優選非投等債 12/03 除息 金額待公告；「試算 →」只帶代號；卡頭、卡尾文字同 PM |
| `#/watch` 表現欄組 | ETF 表換成含息表：上方一行「含息報酬為 11/23 收盤；加權指數同期：20 日 -20.05%、60 日 -17.76%、今年以來 +27.10%、52 週 +39.25%（價格指數，不含股息）」；0050 `87 -18.62% -16.18% +35.31% +48.31%`；00679B `26.33 +2.32% +3.03% +0.83% +0.13%`；說明逐字同設計 |
| `#/today/ov` | 「我的自選」提示行 `近期新訊號 2 檔、即將除權息 3 檔 →`；指數卡 `自 08/25 起 -18.5%`、`自 08/25 起 -30.4%` |
| `#/stock/2330/chip` | 法人卡 `自營 +507億` |
| `#/today/fut` | `前一夜盤（11/20 15:00～11/21 05:00）　收 33,919 -1,881 (-5.25%)` |
| 只有 ETF 的自選（0050、00901、00679B） | 欄組「行情｜表現｜持股」（預設行情）；表現：標題右側只寫「存在這個瀏覽器裡，換裝置不會同步」，三列含息表；即將除權息卡只有 00901 `11/24 除息　配息 7 元`（持股 0050 沒有 `nx`，無估計） |
| `#/help/tr` | 「含息報酬」標示並捲動到該列；`adj` 新文字（「ETF 個股頁的 K 線、52 週高低用原始價，近期表現用含息報酬」） |

- 1024 寬淺色、1024 寬深色、375 寬淺色、375 寬深色：`#/today/ov`、`#/watch`、`#/stock/1437`／`00901`／`6523`、`#/stock/2330/chip`、`#/today/fut`、`#/help/tr` 都是 `scrollWidth = innerWidth`；375 寬自選表現表在表格容器內橫向捲動（和 ETF 列表相同）；即將除權息卡在 375 寬段落換行正常。主控台沒有錯誤。
- 只有 ETF 的自選測試時 `holdLoad` 依既有規則刪掉不在自選裡的持股（第 42 輪行為），屬預期。
- 本輪沒有在持股欄組手動改股數看估計即時更新（`test_iter47.test_edit` 已涵蓋），請 QA 補看。
- 結束：localStorage `{"tw.todayTab":"ov","tw.stockTab":"k"}`（清掉測試加的自選與持股；冒煙途中 `tw.todayTab` 曾變成 `fut`，已改回）、視窗 desktop／淺色、`pkill -f "twstock serve --port 8001"`（exit 0；背景工作結束碼 144），8001 沒有 LISTEN。

## 五、和設計的差異

- 無。

## 六、給 QA 的重點

1. `test_iter47.test_site_data` 只在資料日 2026-11-23 時核對 37 檔與 5 個例子；之後的資料日只核對格式與一致性。11/24、11/25 晚上線後確認 6655、00901、00930、00958B、00990B 從 `nx` 消失（PM 待辦「第 47 輪上線後確認」）。
2. PG 沒有看：320 寬、持股欄組改股數後估計即時更新（6523 1,000 → 清空）、1437 1,000 股 → 624、今日卡「第 6 檔之後才有 `nx`」的情況、舊 `latest.json`（`r47pg/before/latest.json`，沒有 `nx`）時自選頁與今日卡和改前相同。
3. 頁頭標籤在 1024 寬時和「上櫃」等標籤同一行，375 寬淺／深色藍框藍字可辨識；請 QA 再看 320 寬是否擠壓名稱（F47-11 舊問題）。
4. 自選只有 ETF 且舊 `latest.json`（沒有 `r20`～`rw`）時欄組只有「行情｜持股」。

## 七、待 commit 的檔案（使用者看完後再 commit）

- 程式：`twstock/export.py`、`site/app.js`、`site/stock.js`、`site/help.js`、`site/app.css`、`site/index.html`。
- 文件：`README.md`、`docs/iterations/README.md`、`docs/iterations/47/`（`test_iter47`、`test_iter45` 會讀 `47/02-pm.md`，必須一起 commit）。
- 測試：`tests/test_iter47.py`、`tests/test_iter45.py`。
