# 第 44 輪｜PG：實作紀錄

- 撰寫日期：2026-11-22（週日）
- 依據：`44/03-design.md`、`44/03-design.diff`（514 行）；D119～D127 全部 A。
- 守則：
  - 本輪不需要 `export`。資料庫 0 次、外部請求 0 次、`collect` 0 次。
  - 沒有讀、印、複製 `.env`；沒有 git commit／push。
  - 沒有碰 8000。8001 從專案目錄背景啟動，供 QA 接著使用，QA 結束時關閉（見 `05-qa.md`）。

---

## 一、套用

- `git apply --check` 通過後 `git apply docs/iterations/44/03-design.diff`，**沒有手動修改**。
- `git diff --numstat` 和設計第五節逐檔相同：
  - 程式：`tools.js` 3／3、`stock.js` 3／3、`app.js` 1／1、`app.css` +1、`notices.py` 1／1、`tdcc.py` 2／1。
  - `index.html` 4／4；README +2、`docs/iterations/README.md` +1。
  - 舊測試 13 行；新檔 `tests/test_iter44.py`。
- `?v=` 和 `shasum` 前 8 碼相同，也和設計第一節相同：

  | 檔案 | `?v=` |
  |---|---|
  | `app.css` | 351d68e6 |
  | `app.js` | 29a4de94 |
  | `stock.js` | c2c7d916 |
  | `tools.js` | 9066111f |

- `git status site/data` 沒有變化。

## 二、測試

- `tests/test_iter01～44` 共 44 個檔全部通過（`logs/iter44_pg_tests.log`）。
- `test_iter44` 的 10 個測試全部通過（含 `test_contrast` 16 種反證）。

## 三、8001 冒煙（內建瀏覽器，desktop 寬度）

| 項目 | 結果 |
|---|---|
| 進頁時 localStorage | `{}`（結束後依守則設回 `{"tw.todayTab":"ov"}`） |
| 載入的 `?v=` | 4 個都是新值 |
| `#/tools` 預設 | 選中「非當沖」，沒有「先買後賣」那組；規則行 `證交稅：股票 0.3%`；沒有當沖提示 |
| 點「現股當沖」 | 規則行 `證交稅：股票現股當沖 0.15%（至 2027/12/31）`，出現「先買後賣」那組與當沖提示（和改版前相同） |
| `#/tools/dv?c=0050`（ETF） | `已帶入 07/21 的股利（最近一次），下次請依發行人公告修改` |
| `#/tools/dv?c=2330`（股票） | `已帶入 09/16 的股利（最近一次），下次請依公司公告修改` |
| 今日頁小卡（暫存 `tw.watch`、`tw.hold` 兩檔） | 報酬率 `<b class="dn">-97.93%</b>`，顏色和未實現損益相同（綠） |

- 主控台沒有錯誤；伺服器 404 只有 `favicon.ico`。
- 375／320 寬、深色、股利卡與籌碼卡斷行，留給 QA。

## 四、和設計的差異

- 無。

## 五、待 commit 的檔案（使用者看完後再 commit）

- 程式：`site/tools.js`、`site/stock.js`、`site/app.js`、`site/app.css`、`site/index.html`、`twstock/collectors/notices.py`、`twstock/collectors/tdcc.py`。
- 文件：`README.md`、`docs/iterations/README.md`、`docs/iterations/44/`。
- 測試：`tests/test_iter29、38、39、40、41、42、43.py`、`tests/test_iter44.py`。
- `logs/` 不進 commit。
