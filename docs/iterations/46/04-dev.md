# 第 46 輪｜PG：實作紀錄

- 撰寫日期：2026-11-22（週日）；資料日 2026-11-20（週五）
- 依據：`46/03-design.md`、`46/03-design.diff`（628 行）；D134～D144 全部照使用者決定（D141 = C、D144 = A）；使用者同意 SA 第四節的 4 處差異與 `test_iter46.py` 390 行。
- 守則：
  - 依 D143 = A 執行 `python3 -u -m twstock export` 1 次（只讀資料庫、只寫 `site/data/`）。外部請求 0 次、`collect` 0 次。
  - 沒有讀、印、複製 `.env`；沒有 git commit／push／stash／checkout／reset（`git apply` 只套用到工作目錄，沒有 `--index`）。
  - 沒有碰 8000。8001 從專案目錄背景啟動做冒煙測試，結束時關閉（`lsof` 沒有 LISTEN）。

---

## 一、套用

- `git apply --check docs/iterations/46/03-design.diff` 通過後 `git apply`，**沒有手動修改**。
- `git diff --numstat` 和設計第一節逐檔相同：

  | 檔案 | 加／減 |
  |---|---|
  | `twstock/export.py` | 33／0 |
  | `site/app.js` | 32／6 |
  | `site/stock.js` | 11／6 |
  | `site/index.html` | 2／2 |
  | `README.md` | 2／0 |
  | `docs/iterations/README.md` | 1／0 |
  | `tests/test_iter46.py`（新） | 390 行 |

  `git diff --stat`：6 files changed, 81 insertions(+), 14 deletions(-)（不含新檔）。舊測試改 0 行；`app.css` 不改。
- `?v=` 和 `shasum` 前 8 碼相同，也和設計第一節相同：

  | 檔案 | `?v=` |
  |---|---|
  | `app.css` | 7f4315c2（不變） |
  | `app.js` | **45ded7be**（原 c7bb2119） |
  | `stock.js` | **2cb335d6**（原 c2c7d916） |
  | `tools.js` | 64e7360f（不變） |
  | `help.js` | 55e93876（不變） |

## 二、測試

- 匯出前：`tests/test_iter01～46` 共 46 個檔全部通過；`test_iter46.test_site_data` 印「（尚未用第 46 輪匯出，略過）」。
- 匯出後：46 個檔再次全部通過；`test_iter46` 8 個測試全跑（`test_site_data` 這次核對 2.6 手算例，`test_contrast` 21 個反證）。

## 三、匯出（D143 = A）

- 執行前讀過呼叫鏈：`__main__.cmd_export` → `export.export_all`。`export.py` 39 個 `execute` 全是 `SELECT`，沒有 `commit`／`executemany`；連線 `db.connect()` 預設 `autocommit=False`。用到的 `health.load_state`／`build_status`／`share_exists`、`tradingcal.load_closed`、`forecast.load_oi` 只有 `SELECT`；會寫資料庫的 `health.write_run`／`finish_run`、`tradingcal.update_calendar`／`add_adhoc` 不在匯出路徑。
- 匯出前把 `site/data/etfp/`（367 檔）與 `latest.json` 複製到 scratchpad `r46pg/before/` 當比對基準。
- 結果：資料日 2026-11-20，個股 2000 檔，ETF 個股 367 檔 4.9 MB，`latest.json` 809 KB，耗時 28.2 秒（和 SA 副本相同）。上市「找不到事件」4 筆（1435、5236、8105、8908）為既有訊息。
- 核對（資料日和分析時相同，數字逐位相同）：

  | 項目 | 結果 |
  |---|---|
  | `etfp/*.json` 有 `epf` | 367／367 |
  | 0050 52 週 | +39.20%（加權 +31.38%，差距 +7.82） |
  | 0056 52 週 | +38.48% |
  | 00878 52 週 | +52.32% |
  | 00679B 52 週 | +0.17% |
  | 0052 52 週 | +41.52%（差距 +10.14） |
  | `etfs.ix` | `{"20": -23.15, "60": -20.32, "y": 24.41, "w": 31.38}`（加權 52 週 +31.38%） |
  | 0050 列 | `r20` −21.91、`r60` −19.3、`ry` 31.35、`rw` 39.2，在 `dvc` 之後 |
  | 有新欄的 ETF 列 | 360／367（009833 四鍵都沒有；00991A 沒有 `rw`） |
  | 367 檔拿掉 `epf` 後逐位元組 | 和匯出前 0 檔不同 |
  | `latest.json` 拿掉 `r20`～`rw` 與 `etfs.ix` | 只有 `status.exported_at` 不同 |
  | `latest.json` 大小 | 813,424 → 828,631 bytes（+15.2 KB） |

- `site/data/` 在 `.gitignore` 內，`git status` 不顯示。

## 四、8001 冒煙（內建瀏覽器，`http://127.0.0.1:8001`）

| 頁面 | 結果 |
|---|---|
| 0050 走勢分頁 | K 線卡 → 「近期表現（含息）至 11/20」→ 配息與填息；表頭「區間｜本檔｜加權指數｜差距」；52 週 +39.20%／+31.38%／+7.82；沒有提示行 |
| 00679B | 提示「債券 ETF 和股價指數走勢不同，差距只能當參考。」（375 寬 1 行）；5 日 +1.27% |
| 00631L、00674R | 槓桿、反向提示；00674R 52 週 +11.44%、00631L +41.73% |
| 00642U | 期貨 ETF 提示；52 週 +89.71% |
| 2330（股票） | 仍是「近期表現」、本股，輸出同改前 |
| `#/etf` 預設 | 「行情」欄組、14 欄表頭同改前；排序選單多 4 種「含息 20 日／60 日／今年以來／52 週」（在「配息率」之前） |
| `#/etf` 表現 | 加權同期一行；表頭「ETF｜收盤｜20 日｜60 日｜今年以來｜52 週」；0050 列 84.45、−21.91%、−19.30%、+31.35%、+39.20%；頁尾「共 367 檔。含息報酬（%）…」 |
| 4 種含息排序（表現） | 對應欄移到第 2 欄；r20 首位 00686R +29.17%、r60 00674R +28.78%、ry 00715L +206.22%、rw 00715L +189.95% |
| 切回行情（排序 rw） | 表頭不移動 |
| 欄組 | 不寫 localStorage（只有排序照原規則寫 `tw.etfSort`，結束已清） |

- 375 寬：各頁 `scrollWidth = innerWidth = 375`；ETF 卡表 309／309；表現表在 `.tbl-wrap` 內橫向捲動（D144 = A）。1024 寬、淺色／深色顏色正常。主控台沒有錯誤。
- 注意：內建瀏覽器分頁沿用 SA 留下的同一頁面記憶體，第一次用 hash 切到 `#/etf` 時欄組停在「表現」；重新整理後預設是「行情」，符合設計（欄組只記在這次瀏覽）。
- 結束：localStorage `{"tw.todayTab":"ov","tw.stockTab":"k"}`、視窗 desktop／淺色、`pkill -f "twstock serve --port 8001"`（這次 exit 0），8001 沒有 LISTEN。

## 五、和設計的差異

- 無。

## 六、給 QA 的重點

1. `test_iter46` 的 `test_site_data` 只在資料日 2026-11-20 時逐位核對；下次 `collect` 後只做格式檢查。
2. 320 寬、`#/stock/009833`（六列「--」＋上市以來 11/19 起）、`#/stock/00986B`（標題右側最後成交 11/12）PG 沒有再看，請 QA 補。
3. 篩選框、「顯示全部」、點列進 ETF 頁在「表現」欄組下的行為。
4. 舊 `latest.json`（`r46pg/before/` 或 SA 的 `r46sa/before/`）時不顯示欄組與 4 種含息排序。

## 七、待 commit 的檔案（使用者看完後再 commit）

- 程式：`twstock/export.py`、`site/app.js`、`site/stock.js`、`site/index.html`。
- 文件：`README.md`、`docs/iterations/README.md`、`docs/iterations/46/`（`test_iter46` 會讀 `02-pm.md`，必須一起 commit）。
- 測試：`tests/test_iter46.py`。
