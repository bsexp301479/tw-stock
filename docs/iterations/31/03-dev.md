# 第 31 輪｜PG 工程師：實作紀錄

- 撰寫日期：2026-11-17（週二）
- 依據：
  - `31/02-design.md`、`31/02-design.diff`。
  - 使用者 11/17「進 PG」。
- 守則：
  - 沒有 `export`，沒有寫資料庫，沒有外部請求。
  - 沒有動 `.env`、`_archive/`；沒有碰 8000；沒有 commit。

---

## 一、套用方式

1. 把改前的 `site/app.js`、`site/index.html` 備份到 `logs/iter31_before/`。
   - 這是第 30 輪改動之後的狀態，不是 `git HEAD`。
2. 套用：`patch -p1 < docs/iterations/31/02-design.diff`，3 個檔都沒有 offset 或 fuzz。
3. 套用後的 `site/app.js`、`site/index.html`、`tests/test_iter31.py`，都和設計師原型 `proj` 逐位元組相同。

## 二、實際改動（相對第 30 輪套用後）

| 檔案 | ＋／− | 內容 |
|---|---|---|
| `site/app.js` | ＋5／−3 | `oiHTML`：新增 `bar(f)`。降級模式用 z 分數（±3 截斷、`--blue`），並改說明文字 |
| `site/index.html` | ＋1／−1 | `app.js?v=0bde7e1c` |
| `tests/test_iter31.py`（新） | 82 行 | 3 個測試 |

- 沒有動 `twstock/`、`export.py`、`site/data`，舊測試也沒改。

## 三、與設計的差異

無。直接套用設計 diff，沒有手動調整。

## 四、測試（`logs/iter31_dev_tests.log`）

- `test_iter01`～`31`：**31 個全部通過**。
- `node --check site/app.js`：通過。
- `test_iter23`：`?v=` 和 sha1 前 8 碼一致。

## 五、8001 冒煙（內建瀏覽器，窗格顯示中）

### 前置

- 從專案目錄執行 `python3 -u -m twstock serve --port 8001 --no-browser`。
- 對 5 個檔 `fetch(…, {cache:'reload'})` 後重新整理。
- 載入的版本：`app.css?v=a69df04b`、`app.js?v=0bde7e1c`、`stock.js?v=41db19b1`。

### 結果

| 項目 | 結果 |
|---|---|
| 375 淺色：今日 → 期貨「籌碼因子觀察」 | 5 列長條都是藍色 `rgb(40, 109, 191)` |
| 375 淺色：長條方向與長度 | z −1.54 往左 25.7%；z +0.71 往右 11.8%；z +0.70 往右 11.7%；z −4.49 往左 50%（`title` 有「長條截在 3」）；z +3.06 往右 50%（截斷） |
| 375 淺色：說明文字 | 和設計第二節相同 |
| 375 淺色：舊文字 | 頁面中沒有「對隔日上漲有利」 |
| 375 淺色：版面 | `scrollWidth` 375 |
| 1024 深色：長條顏色 | `rgb(72, 139, 217)` |
| 1024 深色：摺疊區 | 打開後是「中性 下一交易日上漲機率 53.2% 依 11/16 收盤後未平倉」，最近 10 次 10 個 |
| 1024 深色：其他頁 | 總覽、期貨、泡泡、個股 2330 的 `scrollWidth` 都是 1024 |
| 錯誤攔截器 | 0 個 |

### 收尾

- localStorage：測試中 `tw.todayTab` 變成 `fut`，已還原成 `{"tw.todayTab":"credit","tw.stockTab":"k"}`。
- 瀏覽器已恢復 preset desktop、淺色。
- 已執行 `pkill -f "twstock serve --port 8001"`；`lsof -iTCP:8001 -sTCP:LISTEN` 沒有輸出。

## 六、給 QA 的注意事項

1. 驗證清單用設計第六節。
2. 目前模型沒有勝過基準，所以頁面上只看得到降級模式。勝過基準時的顯示要靠 `test_iter31.test_beat_mode_unchanged`（node 執行 `oiHTML`）驗。
3. 本輪疊在第 30 輪尚未 commit 的改動上。反證或比對基線時，用 `logs/iter31_before/`，不要用 `git HEAD`。
4. 不需要 `export`。
