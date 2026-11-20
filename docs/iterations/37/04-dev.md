# 第 37 輪｜PG：實作紀錄

- 撰寫日期：2026-11-20（週五）
- 依據：
  - `37/03-design.md`、`37/03-design.diff`（545 行）。
  - 使用者回覆：D66 = A、D66-1 = A、D66-2 = A、D66-3 = A、D66-4 = B、D66-5 = A、D67 = A（PG 直接 `export`）；**D68 = A**（刻度包含 5 條線，維持原型）。
- 守則：
  - 資料庫只讀（`export` 只有 SELECT，另 1 次唯讀查 `collect_runs`）；外部請求 0 次。
  - 沒有 setup-db、collect、history；沒有讀、印、複製 `.env`；沒有 git commit／push／stash／checkout。
  - 沒有碰 8000（使用者的 `serve` 照常在跑）；8001 測完已關閉。

---

## 一、匯出前確認

- 23:39 唯讀查 `collect_runs`：`finished_at IS NULL` 0 列（此欄 NOT NULL，紀錄只在收集結束時寫入，所以另外確認 `pgrep` 沒有 collect／history 程序）。
- 最新 run：#26 `catch-up`，11/20 22:17:34～22:18:41，ok、有新資料、匯出 27.3 秒。
- 資料日：`daily_prices`、`stock_fundamentals` 都到 2026-11-20；匯出前 `latest.json` 的 `exported_at` = 22:40:31。

## 二、備份

- `site/data/` → `logs/iter37_before/site_data/`（51 MB，2,377 個檔案）。
- `git archive HEAD`（`a264719`）→ scratchpad `r37pg/base/`，作為基準程式（不含 `.env`，只有 `.env.example`）。

## 三、套用

- `git apply --check` 通過後 `git apply docs/iterations/37/03-design.diff`，沒有手動修改。

| 檔案 | ＋／−（`git diff --numstat`） |
|---|---|
| `twstock/export.py` | ＋35／−4 |
| `site/stock.js` | ＋67／−0 |
| `site/app.css` | ＋1 |
| `site/index.html` | ＋2／−2 |
| `README.md` | ＋1（第 37 輪河流圖一段，接在第 9 輪估值位置之後） |
| `tests/test_iter37.py` | ＋330（新增，14 個測試） |

- 與設計差異：無。設計文件寫 `export.py` ＋36／−5，`numstat` 為 ＋35／−4，是計數方式不同（內容就是 diff 原樣）。
- `?v=`：`app.css?v=5922ab8d`、`stock.js?v=94125fde`，和 `shasum` 前 8 碼相符；`app.js?v=d175c222`、`tools.js?v=9f5f495d` 未變也相符。
- `__main__.py` 指令沒有變，不用改說明。

## 四、匯出（D67 = A）

| 次序 | 程式 | 輸出位置 | 耗時 |
|---|---|---|---|
| 1 | HEAD 基準（scratchpad `r37pg/base`） | scratchpad `r37pg/base/site/data/` | 27.2 秒（程式內計時；含 import 27.39 秒） |
| 2 | 新程式 `python3 -u -m twstock export` | 專案 `site/data/` | 28.1 秒（`real` 28.52 秒） |

- 背靠背執行（同一晚、同一份資料），差 ＋0.9 秒（驗收 10 ≤ 3 秒）。
- 輸出紀錄：`logs/iter37_export.log`（資料日 2026-11-20，個股 2,000 檔）。
- 基準程式連資料庫的方式比照 SA：先 import 專案 `twstock.config` 載入連線環境變數，再換成基準副本的 `twstock`；沒有讀、印、複製 `.env`。

## 五、比對（PM 驗收 1、9、10）

| 項目 | 結果 |
|---|---|
| 基準 vs 匯出前備份 | 2,377 個中只有 `latest.json` 不同（只差 `exported_at`）→ 同一資料日、可直接比 |
| 檔案數 | 基準／新／備份都是 2,377，檔名集合相同 |
| 新 vs 基準 | 456 個相同；1,921 個不同 = 1,920 個 `stocks/*.json` ＋ `latest.json` |
| `stocks/*.json` 拿掉 `band` | 1,920 檔全部和基準逐位元組相同（`json.dumps(…, ensure_ascii=False, separators=(",", ":"))`） |
| `latest.json` | 只差 `status.exported_at` |
| `etfp/`（367）、`etfs/`（8）、`screen.json` | 逐位元組相同 |
| `stocks/` 合計 | 42.038 → 42.597 MB，**＋0.559 MB**（≤ 1.0） |
| 單檔增量 | 最大 **＋386 bytes**（3152），最小 ＋98（1314），平均 ＋291（≤ 3 KB） |
| `band` 檔數 | 1,920（`pe` 1,452、`pb` 1,920）；沒有 `band` 80 檔 |
| 段數 | 最多 7（上限 24 未觸發） |
| 2330 | `band.d` = `val.d` = 2026-11-20；`pe.k` = [24.02, 27.59, 28.76, 31.4, 32.8]、5 段、`n` = 242 |

- 和設計 4-2 的原型數字（＋0.559 MB、最大 ＋386 bytes、1,920／1,452／1,920、80 檔）完全一致。
- 比對腳本：scratchpad `r37pg/tools/cmp.py`。

## 六、測試

- `node --check site/*.js` 全過。
- 套用後、匯出前：`test_iter01～37` 37 個全過（`test_iter37` 的 `test_real_data` 當時沒有 `band` 會略過）。
- 匯出後再跑一次：37 個全過（`logs/iter37_pg_tests.log`），`test_real_data` 已用真實資料執行。
- 舊測試 0 行改動。

## 七、8001 冒煙

- `python3 -u -m twstock serve --port 8001 --no-browser`，內建瀏覽器開 `http://127.0.0.1:8001`。

| 股票 | 預設 | 結果 |
|---|---|---|
| 2330 | 本益比 | 圖 1 個；今天一行「EPS 98.23 元 × 20.36 倍（近一年最低）」；十字線讀數 98.24（設計觀察 1） |
| 2881 | 本益比 | 多一行金融業說明；位置「第 50 百分位」 |
| 5274 | 本益比 | 375 淺色：右側刻度 28,000 完整；圖例在圖下方換行 |
| 1213（今天虧損） | 淨值比 | 按本益比：「近 4 季 EPS ≤ 0，官方不計算本益比」、圖 0 個；切回淨值比圖 1 個 |
| 1441（股本變動） | — | 一行「09/29 減資，官方值可能尚未調整；股本變動後 90 天內不畫河流圖」，沒有切換鈕 |
| 1303（倍數寬） | 本益比 | 線斷開說明；第 90 百分位 151.23 倍，刻度到 2,000、收盤擠在下方（D68 = A 預期） |
| 2317、2454、2891、3105、1101 | 淨值比（記住上次選擇） | 各 1 個圖、無錯誤 |

- 375 淺色、375 深色、1024 深色：`scrollWidth` = 視窗寬，沒有頁面層級橫向捲動。
- 切換深淺色（頂欄按鈕）後重畫、圖仍 1 個；切換記住 `tw.bandV`。
- 走勢／籌碼／基本面來回 10 次、換 5 檔：`.tv-lightweight-charts` 都是 0 或 1 個。
- 主控台錯誤 0；伺服器 404 只有 `favicon.ico`，沒有 5xx。
- 結束：`pkill -f "twstock serve --port 8001"`，`lsof -iTCP:8001` 無輸出；8000（使用者）照常在跑。
- localStorage 清回 `{"tw.todayTab":"ov","tw.stockTab":"k"}`（`tw.bandV`、`tw.theme` 已清）；視窗恢復 desktop，分頁已關。

## 八、上線後

- 每晚收集後的自動匯出會帶出 `band`（匯出約多 1 秒）；8000 重新整理即可看到（`index.html` 已更新 `?v=`）。

## 九、待 commit 的檔案

- `twstock/export.py`、`site/stock.js`、`site/app.css`、`site/index.html`、`README.md`。
- `tests/test_iter37.py`。
- `docs/iterations/37/`（01～04、`03-design.diff`）；QA 後更新 `docs/iterations/README.md`。
- `site/data/`、`logs/` 不進 commit。
