# 第 35 輪｜PG 工程師：實作紀錄

- 撰寫日期：2026-11-20（週五）
- 依據：
  - `35/03-design.md`、`35/03-design.diff`。
  - 使用者 11/20「進 PG」；D62 = A（PG 階段直接 `export`）。
- 守則：
  - 只跑了一次 `export`（PG 允許）；沒有寫資料庫、沒有收集、沒有外部請求。
  - 沒有動 `.env`、`_archive/`，沒有碰 8000，沒有 commit。

---

## 一、套用方式

1. 備份改前的檔案到 `logs/iter35_before/`：`twstock/export.py`、`site/app.js`、`site/index.html`。
2. 執行 `git apply docs/iterations/35/03-design.diff`，沒有錯誤。
3. 套用後的四個檔和設計原型 `r35/proj` **逐位元組相同**。

## 二、實際改動

| 檔案 | ＋／− | 內容 |
|---|---|---|
| `twstock/export.py` | ＋14／−1 | `SCREEN_KEYS` 加 `dvd`、`dvp`、`dvn`、`dvx`、`dvk`；`div_screen()`；`screen` 接線 |
| `site/app.js` | ＋23／−7 | 衍生欄、欄位、4 個條件、殖利率多欄、排行「近期除息」、`DV_NOTE` |
| `site/index.html` | ＋1／−1 | `app.js?v=acd783df` |
| `tests/test_iter35.py` | ＋210 | 新增 |

- 和設計沒有差異。舊測試沒有改。

## 三、測試

| 時機 | 結果 | 紀錄 |
|---|---|---|
| 套用後、匯出前 | `node --check` 通過；`test_iter01～35` **35 個全部通過**（`test_real_data` 因尚未匯出而略過） | `logs/iter35_dev_tests.log` |
| 匯出後 | `test_iter01～35` **35 個全部通過**；`test_real_data` 執行，1,986 檔 0 差異 | `logs/iter35_dev_tests2.log` |

## 四、匯出（`logs/iter35_export.log`）

- 匯出前把整個 `site/data/`（51 MB）備份到 `logs/iter35_before/data/`，給 QA 比對。
- `python3 -u -m twstock export`：
  - 資料日 2026-11-19，個股 2,000 檔，耗時 27.8 秒。
  - `screen.json` 463 KB（改前 411 KB），和設計原型相同。
  - 警告「找不到除權息／減資事件 4 筆」是第 2／8 輪就有的已知狀況。

### 匯出前後比對（`site/data/` 共 2,377 檔）

| 項目 | 結果 |
|---|---|
| `screen.json` | 新增 5 個鍵；**舊的鍵逐值相同** |
| `latest.json` | 只有 `status.exported_at` 不同 |
| 其他 2,375 檔（個股 JSON 含 `dv`、`fh`，ETF、`etfp/`） | 逐位元組相同 |
| 新增或消失的檔案 | 0 |

- 新欄位分布：已填息 921、尚未填息 506、中斷 14、近一年沒有 545，和分析師統計相同。

## 五、8001 冒煙（從專案目錄啟動）

| 項目 | 結果 |
|---|---|
| 載入版本 | `app.js?v=acd783df` |
| 選股四個條件的單獨檔數 | 1,441／921／506／41 |
| 價值高息組合 | 75 檔；欄位：本益比、殖利率、最近除息、距填息價 |
| 排行「近期除息」 | 50 檔，前 12 檔代號和設計原型相同（2344、3680、3289、3563…） |
| 伺服器 404 | 只有 `favicon.ico` |

### 收尾

- localStorage 已還原成開始時的 `{"tw.todayTab":"ov"}`。
- 瀏覽器維持 preset desktop、淺色。
- 已執行 `pkill -f "twstock serve --port 8001"`；`lsof -iTCP:8001 -sTCP:LISTEN` 沒有輸出。

## 六、給 QA 的注意事項

1. 匯出前備份：`logs/iter35_before/data/`；改前程式：`logs/iter35_before/*.{py,js,html}`。
2. 驗收 1 請自己從個股 JSON 的 `dv` 推導，不要呼叫 `div_screen`。
3. 設計的反證腳本在 scratchpad `r35/contrast.py`（12 種改壞方式）。
4. 今晚（11/20）每晚收集會用工作目錄的程式匯出，新欄位會照常產生。
