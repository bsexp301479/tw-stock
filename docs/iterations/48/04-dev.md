# 第 48 輪｜PG：實作紀錄

- 撰寫日期：2026-11-24（週二）；資料日 2026-11-24（週二）
- 依據：`48/01-analyst.md`、`48/02-pm.md`、`48/03-design.md`、`48/03-design.diff`（709 行）；D157～D167 全 A；使用者接受 SA 第四節 10 點差異與 `test_iter48.py` 384 行。
- 守則：
  - 依 D167 = A 執行 `python3 -u -m twstock export` 1 次（只讀資料庫、只寫 `site/data/`）。外部請求 0 次、`collect` 0 次。
  - 沒有讀、印、複製 `.env`；沒有 git commit／push／stash／checkout／reset（`git apply` 只套用到工作目錄，沒有 `--index`）。
  - 沒有碰 8000。8001 從專案目錄背景啟動做冒煙測試，結束時關閉（`lsof` 沒有 LISTEN）。

---

## 一、套用

- `git apply --check docs/iterations/48/03-design.diff` 通過後 `git apply`，**沒有手動修改**。
- `git diff --numstat` 和設計第一節逐檔相同：

  | 檔案 | 加／減 |
  |---|---|
  | `twstock/export.py` | 6／0 |
  | `site/app.js` | 2／1 |
  | `site/stock.js` | 2／0 |
  | `site/app.css` | 4／0 |
  | `site/index.html` | 4／3 |
  | `README.md` | 2／0 |
  | `docs/iterations/README.md` | 1／0 |
  | `site/compare.js`（新） | 170 行 |
  | `tests/test_iter48.py`（新） | 384 行 |

  `git diff --stat`：7 files changed, 21 insertions(+), 4 deletions(-)（不含新檔）。
- 舊測試：`git diff --stat tests/` 為空（0 行改動；`test_iter48.py` 是新檔，未追蹤）。
- `?v=` 和 `shasum` 前 8 碼相同，也和設計第一節相同：

  | 檔案 | `?v=` |
  |---|---|
  | `app.css` | **1ae7bbed**（原 07335b75） |
  | `app.js` | **d273c8c5**（原 5548b620） |
  | `stock.js` | **29bc6522**（原 7e6c6a13） |
  | `tools.js` | 64e7360f（不變） |
  | `help.js` | a5a5a7e8（不變） |
  | `compare.js`（新） | **6652dcfe** |

## 二、測試

- 匯出前：`tests/test_iter01～48` 共 48 個檔全部通過（約 66 秒）；`test_iter48` 印「尚未用第 48 輪匯出，略過 ix.json」（`test_site_data`）與「略過手算例」（`test_examples`）。
- 匯出後：48 個檔再次全部通過；`test_iter48` 14 個測試沒有任何「略過」，`test_site_data`、`test_examples` 這次實跑，`test_full`（2,354 檔、14,260 列）與 `test_contrast` 22 個反證通過。

## 三、匯出（D167 = A）

- 執行前讀過呼叫鏈：`__main__.cmd_export` → `export.export_all`。`export.py` 39 個 `execute` 的 SQL 開頭全是 `SELECT`，沒有 `commit`／`executemany`；`db.connect()` 預設 `autocommit=False`。匯出用到的 `health.build_status`（`load_closed`、`load_state`、`collected_at`、`load_snapshot`、`dataset_status`、`site_closed`）、`health.share_exists`、`tradingcal.load_closed`／`is_trading_day`／`trading_days`、`analysis.forecast.load_oi` 只有 `SELECT`；含 `INSERT`／`UPDATE`／`DELETE`／`MERGE`／`commit` 的只有 `health.write_run`／`finish_run`、`tradingcal.update_calendar`／`add_adhoc`／`remove_adhoc`，都不在匯出路徑。本輪新增的 `ix_export` 是純函式，用既有 `_write` 寫 `site/data/ix.json`。
- 匯出前備份到 scratchpad `r48pg/before/`：`site/data/` 全部 2,377 個檔的 sha1（`sha1.txt`）、`latest.json`、`screen.json`；匯出後的 sha1 存 `r48pg/after_sha1.txt`。
- 結果：資料日 2026-11-24，個股 2000 檔，ETF 個股 367 檔 4.9 MB，`latest.json` 801 KB，耗時 28.6 秒。上市「找不到事件」4 筆（1435、5236、8105、8908）為既有訊息。
- 核對：

  | 項目 | 結果 |
  |---|---|
  | `ix.json` | 5,692 bytes；鍵 `d`、`TAIEX`；259 天 2025-10-30～2026-11-24 |
  | `ix.json` `d` = `p_days` | 等於全部 `stocks/*.json` `prices.d` 聯集；最後一天 = `latest.date` |
  | `TAIEX` | 首 28287.53、末 40122.35、0 個 null |
  | 其他 2,377 個檔 sha1 | 只有 `latest.json` 不同；新增 `ix.json` 1 檔 |
  | `latest.json` 拿掉 `status.exported_at` | 完全相同（21:55:01 → 23:00:40）；大小 820,426 bytes 不變 |

- `site/data/` 在 `.gitignore` 內，`git status` 不顯示。

## 四、8001 冒煙（內建瀏覽器，`http://127.0.0.1:8001`）

- 載入的是新版：`app.js?v=d273c8c5`、`stock.js?v=29bc6522`、`tools.js?v=64e7360f`、`help.js?v=a5a5a7e8`、`compare.js?v=6652dcfe`、`app.css?v=1ae7bbed`；頁面標題 `報酬率比較｜台股資金流`。
- 暫時設自選 0056、2330、9999、00878。

| 頁面 | 結果 |
|---|---|
| `#/compare/2330,2454,0050/w` | `+64.17%`／`+261.15%`／`+63.97%`、加權 `+51.38%`；最大跌幅、年化波動同設計第五節；4 色＋加權虛線 |
| 區間 20／60／120／今年以來 | 四組數字和設計第五節逐一相同；點「60 日」按鈕 → `#/compare/2330,2454/60`，`history.length` 不變 |
| `#/compare/0050,00991A/w` | 起點 2025-12-18，共同起點那一行逐字；`+57.74%`／`+34.21%`／加權 `+46.07%`；換 `/20` 不出現共同起點 |
| `#/compare/0050,009833/20` | 共同起點 2026-11-19；`+6.10%`／`-0.10%`／`+4.41%`；年化波動三列 `--` |
| `#/compare/0052,0050/w` | `+61.26%`／`+63.97%`；十字線 2025/11/24 `0052 0.00%（無成交）`、2025/11/26 `+0.88%` |
| `#/compare/00625K,0050/w` | 共同起點 2025-12-05、`最後成交 11/05`、`-9.54%`；0050 `+55.60%`；加權 `+43.39%` |
| `#/compare/0056,00878,00919/w`、`00679B,00687B,0050/w` | 同設計第五節例 2、例 4 |
| 搜尋加入 | 輸入「元大高」→ 候選 0056 → ↓＋Enter 加入（接在最後）；輸入 `0050`＋Enter 加入 |
| 滿 4 檔 | 搜尋框 `disabled`、`已滿 4 檔`，自選列不顯示 |
| × 移除 | 移除 2454 → `#/compare/2330,0056,0050/60`，搜尋框恢復 |
| 自選快速加入 | `#/compare/2330/w` 自選列只有 0056、00878（9999 不列、2330 已選不列）；點 00878 → `#/compare/2330,00878/w`；`tw.watch` 沒被改 |
| 網址正規化 | `2330,2454,0050,0056,00878` → 保留前 4 檔＋`/w`、提示「最多比較 4 檔，已保留前 4 檔」；`9999` → `#/compare`＋「找不到 9999…」＋空狀態；`0050,00991a/Y` → `#/compare/0050,00991A/w` |
| `#/stock/2330`、`#/stock/00991A`、`#/stock/0056` | 「比較 →」在「近期表現」／「近期表現（含息）」標題列；`#/stock/2330/chip` 沒有；點 0056 的連結 → `#/compare/0056/w`，瀏覽器返回回到 `#/stock/0056`，圖表 0 個 |
| 1024 深色 `#/compare/0056,00878,00919,00890B/w` | 正常，`--cmp2` = `#ff922b` |
| 375 淺／深 | 4 檔、例 1、例 5、例 6、`#/compare`、`#/stock/2330`、`#/stock/0056` 都是 `scrollWidth = innerWidth`（375）；表格容器 308 = 308 不橫捲；區間按鈕一行 |

- 主控台沒有錯誤；離開比較頁後 `.tv-lightweight-charts` 0 個。
- 結束：localStorage `{"tw.todayTab":"ov","tw.stockTab":"k"}`（清掉測試加的自選）、視窗 desktop／淺色、`pkill -f "twstock serve --port 8001"`（exit 0；背景工作結束碼 144），8001 沒有 LISTEN。

## 五、和設計的差異

- 無（程式照 diff 套用，沒有改動）。
- 觀察（未修，交 QA／使用者判斷）：網址裡代號前後有空白時，瀏覽器會把空白編碼成 `%20`，`location.hash` 拿到的是 `%202330%20`，`cmpNorm` 的 `trim` 去不掉，結果提示「找不到 %202330%20、TSMC，已從比較清單移除」（實測 `#/compare/2330, 2330 ,tsmc,0050/xx` → `#/compare/2330,0050/w`）。PM 規格寫「去空白」；`test_norm` 是直接傳字串，沒有經過瀏覽器編碼，所以測試通過。最終網址正確，只是提示文字顯示 `%20`。

## 六、給 QA 的重點

1. 上面「觀察」：手動在網址列輸入含空白的代號時提示文字出現 `%20`，請判斷是否要在 `route()` 或 `cmpNorm` 解碼（`decodeURIComponent`），屬下一輪或本輪修正。
2. PG 沒有看：320 寬（SA 已看）、`ix.json` 讀取失敗時的提示、選字中 Enter 不加入（`isComposing`）、Esc 關閉清單、ETF 沒有 `epf` 的提示（目前 0 檔）。
3. `test_iter48.test_site_data`／`test_examples`／`test_full` 只在資料日 2026-11-24 時核對手算例與 2,354 檔、14,260 列；之後的資料日只核對格式與一致性。
4. 從個股頁「比較 →」進入後瀏覽器返回，回到 `#/stock/0056`（本次是直接開 `#/stock/0056`，沒有帶 `/k`），請確認從頂欄搜尋進入的情況。

## 七、待 commit 的檔案（使用者看完後再 commit）

- 程式：`twstock/export.py`、`site/compare.js`（新）、`site/app.js`、`site/stock.js`、`site/app.css`、`site/index.html`。
- 文件：`README.md`、`docs/iterations/README.md`、`docs/iterations/48/`（`test_iter48` 會讀 `48/02-pm.md`，必須一起 commit）。
- 測試：`tests/test_iter48.py`（新）。
