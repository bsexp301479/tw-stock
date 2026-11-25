# 第 49 輪｜PG：實作紀錄

- 撰寫日期：2026-11-25（週三）；資料日 2026-11-25（週三）
- 依據：`49/01-analyst.md`、`49/02-pm.md`、`49/03-design.md`、`49/03-design.diff`（544 行）；D169～D176 全 A；PM 自行決定照 PM；使用者接受 SA 第七節差異（監聽掛 `#gZ`、新增 `gzFoot`、驗收 11 補充、新測試 305 行）。
- 守則：
  - 本輪不改 `twstock/`、不需 `export`（SA 文件第六節 4：`site/data` 不變）；沒有執行 `export`／`collect`，沒有連資料庫、沒有外部請求。
  - 沒有讀、印、複製 `.env`；沒有 git commit／push／stash／checkout（`git apply` 只套用到工作目錄，沒有 `--index`）。
  - 沒有碰 8000。8001 從專案目錄背景啟動做冒煙測試，結束時關閉（`lsof` 8001／8002 沒有 LISTEN）。

---

## 一、套用

- `git apply --check docs/iterations/49/03-design.diff` 通過後 `git apply`，**沒有手動修改**。
- 套用前 `git status --short` 只有 `?? docs/iterations/49/`。
- `git diff --numstat` 和設計第一節逐檔相同：

  | 檔案 | 加／減 |
  |---|---|
  | `site/tools.js` | 1／1 |
  | `site/app.js` | 14／2 |
  | `site/app.css` | 3／1 |
  | `site/index.html` | 3／3 |
  | `README.md` | 2／0 |
  | `docs/iterations/README.md` | 1／0 |
  | `tests/test_iter39.py` | 3／3 |
  | `tests/test_iter40.py` | 2／2 |
  | `tests/test_iter41.py` | 1／1 |
  | `tests/test_iter47.py` | 1／1 |
  | `tests/test_iter48.py` | 1／1 |
  | `tests/test_iter49.py`（新） | 305 行 |

- 舊測試改動只有使用者同意的 8 行：`test_iter39:262/263/265`、`test_iter40:400/404`、`test_iter41:437`、`test_iter47:380`、`test_iter48:301`（套用前逐行核對 diff 內容）。`test_iter39:266` 未改。
- `?v=` 和 `shasum` 前 8 碼相同，也和設計 2-5 相同：

  | 檔案 | `?v=` |
  |---|---|
  | `app.css` | **ce1417aa**（原 1ae7bbed） |
  | `app.js` | **54952a23**（原 d273c8c5） |
  | `tools.js` | **0a050889**（原 64e7360f） |
  | `stock.js` | 28633954（不變） |
  | `help.js` | a5a5a7e8（不變） |
  | `compare.js` | 1c11197d（不變） |

- `test_iter41:437` 雜湊：用最終 `tools.js` 重算 `OLD` 函式的 sha1 前 12 碼 = `81d223f49f68`，和 diff 寫入值一致。

## 二、測試

- `for f in tests/test_iter*.py; do python3 $f >/dev/null 2>&1 || echo FAIL $f; done`：共 **49 個檔，沒有 FAIL**（約 70 秒）。
- `python3 -u tests/test_iter49.py`：9 個測試全 `ok`（`test_dv`、`test_bubble`、`test_bubble_data`、`test_head_css`、`test_screen`、`test_screen_data`、`test_words_node14`、`test_version_and_docs`、`test_contrast`）；資料日是 2026-11-25，`test_bubble_data`、`test_screen_data` 實跑，沒有「略過」。

## 三、8001 冒煙（內建瀏覽器，`http://127.0.0.1:8001`）

- 載入的是新版：`app.css?v=ce1417aa`、`app.js?v=54952a23`、`stock.js?v=28633954`、`tools.js?v=0a050889`、`help.js?v=a5a5a7e8`、`compare.js?v=1c11197d`。
- 開始時 localStorage = `{"tw.todayTab":"ov","tw.stockTab":"k"}`。

| 頁面 | 結果 |
|---|---|
| `#/bubble`（1024×800），預設族群「通信網路」 | 92 列、可見 50 列，`#gTable` class `tbl gz`；表尾「另有 42 檔法人 1 日、5 日都是 0億　顯示」 |
| 點「顯示」 | 可見 92 列、class `tbl`、表尾「含 42 檔法人 1 日、5 日都是 0億　收合」；localStorage 沒有新鍵 |
| 再點「收合」 | 回到 50 列、class `tbl gz`、「另有 42 檔…顯示」；點一次切一次（沒有重複觸發） |
| 表尾位置 | 表尾 top 1221px ≥ `.panel-list` 下緣 1215px（在捲動框之外） |
| `#/rank/screen?nxd=14&o=nx` | 欄位「股票｜即將除息｜收盤｜漲跌｜成交額」，10 列；第一列 6523 達爾膚「11/26／1 天後」 |
| `#/tools/dv?c=2330` | 「近一年現金股利 = 2025/11/25 以後 4 次合計」（含年份） |
| `#/stock/00878`（320×700） | `.s-name` 17px、`.s-code` `inline-block`；代號在名稱下一行（名稱 top 117、代號 top 140）；`scrollWidth = innerWidth = 320` |
| 主控台 | 0 錯誤 |

- 結束：localStorage 設回 `{"tw.todayTab":"ov","tw.stockTab":"k"}`、`resize_window` preset desktop、`pkill -f "twstock serve --port 8001"`；`lsof -iTCP:8001 -iTCP:8002 -sTCP:LISTEN` 沒有輸出。

## 四、與設計的差異

- 程式、測試、文件：**0 處**，完全照 `03-design.diff` 套用。
- 冒煙路徑：任務說明寫 `#/screen?nxd=14&o=nx`，實際選股路由是 `#/rank/screen?…`（`#/screen` 會被導回 `#/today/ov`，是既有行為，本輪未改）；本輪用 `#/rank/screen?nxd=14&o=nx` 驗，和 SA 第四節 21 的路徑相同。
- 泡泡圖畫面驗的是預設族群「通信網路」（42／92），不是 SA 記錄的電子零組件、觀光餐旅；數字由 `test_bubble_data` 核對，其他族群留 QA。

## 五、留給 QA

1. 驗收 4：除權息試算四種分支各挑一檔看畫面（本輪只看 2330 有現金股利分支）。
2. 驗收 11：電子零組件 131／78、農業科技 0／4、觀光餐旅 6／44，產業鏈、概念股分組的表尾。
3. 驗收 13：全部 2,354 個名稱在 320／360／375 寬的行數（SA 只抽 4 檔、本輪只看 00878）。
4. 驗收 14：1024 寬個股頁頭目視不變。
5. 驗收 20：選股「複製條件連結」保留 `nxd`。
6. 驗收 28：1024／375／320 × 淺／深色組合；手機泡泡圖清單模式沒有 `#gZ`、圖模式有。
7. `docs/iterations/README.md` 第 49 輪那一行目前只寫到設計，PG／QA 結果待補（本輪 PG 依限制只新增本檔，未改該行）。
