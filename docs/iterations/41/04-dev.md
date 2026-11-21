# 第 41 輪｜PG：實作紀錄

- 撰寫日期：2026-11-21（週六）
- 依據：
  - `41/03-design.md`、`41/03-design.diff`（720 行）。
  - D91～D101 全部 A；D95 = A（只改 `tests/test_iter39.py:344` 一行）；D101 = A（520px 以下分頁列兩行）。
- 守則：
  - 本輪只改前端與測試，**不需要 `export`**；資料庫 0 次、外部請求 0 次。
  - 沒有讀、印、複製 `.env`；沒有 git commit／push。
  - 沒有碰 8000；8001 從專案目錄啟動，測完已關閉（`lsof` 沒有輸出），伺服器 404 只有 `favicon.ico`。
  - 瀏覽器已恢復 preset desktop、淺色；localStorage 測試後恢復為 `{"tw.todayTab":"ov"}`。

---

## 一、套用

- `git apply --check` 通過後 `git apply docs/iterations/41/03-design.diff`，**沒有手動修改**。

| 檔案 | ＋／−（`git diff --numstat`） |
|---|---|
| `site/tools.js` | ＋110／−4 |
| `site/app.js` | ＋1／−1 |
| `site/app.css` | ＋3 |
| `site/index.html` | ＋3／−3 |
| `README.md` | ＋2 |
| `docs/iterations/README.md` | ＋1 |
| `tests/test_iter39.py` | ＋1／−1（第 344 行，白名單加 `'ac'`，D95） |
| `tests/test_iter41.py` | ＋486（新增） |

- `?v=`：`app.css` d039dc67、`app.js` e571fb7b、`tools.js` 05638786（`stock.js` 00d41238 不變），和 `shasum` 前 8 碼相同。
- `git diff --stat tests/`：舊測試只有 `test_iter39.py` 改 1 行。

## 二、測試

- `test_iter01～41` 41 個檔案全部通過（`logs/iter41_pg_tests.log`）。
- `test_iter41` 13 個測試全部通過（含 `test_contrast` 反證）。

## 三、8001 冒煙（375）

| 項目 | 結果 |
|---|---|
| `#/tools/ac?c=2330` 進頁 | 標題列「台積電 2330 11/20 收盤 2,000」；目前價格帶入 2000；手續費欄位 10／20／1；預設 3 列 |
| 填兩筆（實際鍵盤輸入）：1,000 元 × 1,000 股、1,500 元 × 1,050 股 | 總股數 2,050（整股 2 張＋零股 50 股）；手續費 1,425、2,137＋106，合計 3,668；總成本 2,578,668；平均成交價 1,256.10；平均成本 1,257.89；兩平賣價理論 1,263.48、可成交 1,265（以此價出售淨損益 +3,108）；目前價格 2,000 註「11/20 收盤，不是即時價」；出售手續費 5,842（5,700＋142）、證交稅 12,300（12,000＋300）；未實現損益 +1,503,190；報酬率 +58.29%。全部和手算相同 |
| 新增到 10 筆 | 第 10 筆出現後「＋ 新增一筆」消失 |
| 第 3 筆填 900 × 10 後刪除第 2 筆 | 900 × 10 往前移到第 2 筆，剩 9 筆，新增鈕重新出現；明細手續費 12 元 |
| 切到「除權息」 | 頁籤列兩行（前 4 個一行、除權息第二行且為選取狀態）；`#toolTabSeg` 沒有溢出；頁面 `scrollWidth` 375 |

- 主控台沒有錯誤。
- 320 寬、深色、驗證訊息、ETF／債券 ETF 稅率、24 條驗收逐條核對留給 QA。

## 四、和設計的差異

- 無。

## 五、待 commit 的檔案

- `site/tools.js`、`site/app.js`、`site/app.css`、`site/index.html`、`README.md`、`docs/iterations/README.md`。
- `tests/test_iter39.py`、`tests/test_iter41.py`。
- `docs/iterations/41/`（01～04、`03-design.diff`）；QA 後補 `05-qa.md`。
- `logs/` 不進 commit。
