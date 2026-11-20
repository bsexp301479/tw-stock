# 第 38 輪｜PG：實作紀錄

- 撰寫日期：2026-11-21（週六）
- 依據：
  - `38/03-design.md`、`38/03-design.diff`（738 行）。
  - 使用者回覆（記於設計文件末）：D79 = A（`test_iter34` 多改 238、243、252 行，共 15 行）、D80 = A（5 處文字照 SA 定稿）、D81 = A（對照線用點線）。
  - 使用者 11/21「請幫我接續完成第 38 輪的作業」。
- 守則：
  - 本輪只改前端與測試，**不需要 `export`**；資料庫 0 次、外部請求 0 次。
  - 沒有讀、印、複製 `.env`；沒有 git commit／push。
  - 沒有碰 8000；8001 從專案目錄啟動，測完已關閉（`lsof` 沒有輸出），伺服器 404 只有 `favicon.ico`。
  - 瀏覽器已恢復 preset desktop、淺色；localStorage 測試前後都是 `{"tw.todayTab":"ov"}`。

---

## 一、套用

- `git apply --check` 通過後 `git apply docs/iterations/38/03-design.diff`，**沒有手動修改**。D79～D81 都是 A，設計 diff 已照此做，不需要調整。

| 檔案 | ＋／−（`git diff --numstat`） |
|---|---|
| `site/tools.js` | ＋43／−25 |
| `site/app.css` | ＋2 |
| `site/index.html` | ＋2／−2 |
| `README.md` | ＋2 |
| `tests/test_iter34.py` | ＋16／−15（使用者同意的 15 行＋1 行新增斷言） |
| `tests/test_iter38.py` | ＋427（新增） |

- `?v=`：`app.css?v=cbb3fec1`、`tools.js?v=e587ec88`，和 `shasum` 前 8 碼相同。
- 和設計第一節的行數完全一致。

## 二、測試

- `test_iter01～38` 38 個全部通過（`logs/iter38_pg_tests.log`）。
- `test_iter38` 13 個測試全部通過，含 `test_contrast`（11 種反證全部擋下）。

## 三、8001 冒煙（375 淺色）

| 頁面 | 結果 |
|---|---|
| `#/tools/dt` | 分段鈕「非當沖」、標籤「手續費折扣（折）」等新文字出現；`scrollWidth` 375 |
| `#/tools/cp` | 填入 100,000／5,000／6%／10 年：摘要期末 998,482 元、投入 700,000 元；下方出現逐年成長圖（期末實線、累計投入虛線）與圖例、刻度說明，緊接「不代表本站預期」；`scrollWidth` 375 |
| `#/tools/pl` | 正常顯示；`scrollWidth` 375 |

- 主控台只有 1 筆 `ERR_CONNECTION_REFUSED`，是分頁在 8001 停止期間留下的，和本輪程式無關。
- 淺／深色對比、320 寬、極端值、各情境逐條驗收留給 QA（設計第五節對應表）。

## 四、和設計的差異

- 無。

## 五、待 commit 的檔案

- `site/tools.js`、`site/app.css`、`site/index.html`、`README.md`。
- `tests/test_iter34.py`、`tests/test_iter38.py`。
- `docs/iterations/38/`（01～04、`03-design.diff`）；QA 後更新 `docs/iterations/README.md`。
- `logs/` 不進 commit。
