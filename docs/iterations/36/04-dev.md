# 第 36 輪｜PG：實作紀錄

- 撰寫日期：2026-11-20（週五）
- 依據：
  - `36/03-design.md`、`36/03-design.diff`。
  - 使用者 11/20「照建議，進 PG」：
    - **D64-1 = B**：新欄放在 ETF 列表最後（排序時由 `keyCol` 搬到名稱旁）。
    - **D65 同意**：改 `test_iter15:94`、`test_iter24:233` 兩行。
- 守則：
  - 只跑一次 `export`（D64 = A），資料庫唯讀；外部請求 0 次。
  - 沒有開 8000／8001（8000 是使用者自己的伺服器，照常在跑，沒有碰）。

---

## 一、套用

- `git apply docs/iterations/36/03-design.diff`，沒有手動修改。
- 套用後 7 個檔案和 SA 原型副本逐位元組相同。

| 檔案 | ＋／− |
|---|---|
| `twstock/export.py` | ＋59／−7 |
| `site/stock.js` | ＋29／−18 |
| `site/app.js` | ＋12／−5 |
| `site/index.html` | ＋2／−2（`app.js?v=d175c222`、`stock.js?v=55bdf502`） |
| `tests/test_iter15.py` | ＋1／−1（使用者同意） |
| `tests/test_iter24.py` | ＋1／−1（使用者同意） |
| `tests/test_iter36.py` | ＋279（新增） |

## 二、匯出

- 備份：`site/data/` → `logs/iter36_before/`（51 MB）。
- `python3 -u -m twstock export`：27.9 秒，資料日 2026-11-20，ETF 個股 367 檔 4.8 MB（`logs/iter36_export.log`）。

## 三、比對（驗收 3、11）

| 項目 | 結果 |
|---|---|
| 檔案數 | 前後都是 2,377 個，沒有新增或刪除 |
| 有變動的檔案 | `etfp/` 219 檔＋`latest.json`，其他（股票個股 JSON 含外資持股 `fh`、`screen.json` 含第 35 輪股利欄）逐位元組相同 |
| `etfp/` 219 檔 | 拿掉 `dv` 後和匯出前完全相同；148 檔沒有除息紀錄的 ETF 沒有 `dv` 鍵、檔案不變 |
| `latest.json` | 只多 219 檔 ETF 的 `dvd`、`dvn`、`dvx`、`dvc`，以及 `status.exported_at` |
| 和 SA 原型資料 | `etfp/` 367 檔逐位元組相同 |

## 四、統計（驗收 2）

| 狀態（最近一次） | 檔數 | 分析師 |
|---|---|---|
| 已填息 | 112 | 112 |
| 尚未填息 | 107 | 107 |
| 中斷 | 0 | — |

- 已填息天數中位數 6，和分析師相同。

## 五、測試

- `test_iter01～36` 36 個全部通過（`logs/iter36_pg_tests.log`）。
- `test_iter36` 的 `test_real_data` 已用本次匯出實際執行：每檔列表欄 = 由 `dv` 重算，每筆填息日和原始收盤對得上。

## 六、上線後

- 每晚收集後的自動匯出會帶出 `dv` 與列表欄；8000 重新整理即可看到（`index.html` 已更新 `?v=`）。

## 七、待 commit 的檔案

- `twstock/export.py`、`site/app.js`、`site/stock.js`、`site/index.html`。
- `tests/test_iter15.py`、`tests/test_iter24.py`、`tests/test_iter36.py`。
- `docs/iterations/36/`（01～04、`03-design.diff`）；QA 後更新 `docs/iterations/README.md`。
- `site/data/`、`logs/` 不進 commit。
