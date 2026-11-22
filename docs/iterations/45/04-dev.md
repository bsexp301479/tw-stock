# 第 45 輪｜PG：實作紀錄

- 撰寫日期：2026-11-22（週日）
- 依據：`45/03-design.md`、`45/03-design.diff`（445 行）；D128～D133 全部 A；使用者同意 SA 第四節的 3 處差異。
- 守則：
  - 本輪不需要 `export`。資料庫 0 次、外部請求 0 次、`collect` 0 次。
  - 沒有讀、印、複製 `.env`；沒有 git commit／push。
  - 沒有碰 8000。8001 從專案目錄背景啟動做冒煙測試，結束時關閉（`lsof` 沒有輸出）。

---

## 一、套用

- `git apply --check` 通過後 `git apply docs/iterations/45/03-design.diff`，**沒有手動修改**。
- `git diff --numstat` 和設計第一節逐檔相同：
  - 程式：`app.css` +1、`app.js` 2／1、`tools.js` 1／1、`index.html` 6／4、新檔 `help.js`。
  - README +2、`docs/iterations/README.md` +1。
  - 舊測試 `test_iter41.py` 1／1；新檔 `tests/test_iter45.py`。
- `?v=` 和 `shasum` 前 8 碼相同，也和設計第一節相同：

  | 檔案 | `?v=` |
  |---|---|
  | `app.css` | 7f4315c2 |
  | `app.js` | c7bb2119 |
  | `stock.js` | c2c7d916（不變） |
  | `tools.js` | 64e7360f |
  | `help.js` | 55e93876 |

- `test_iter41:437` 用最終 `tools.js` 重算：`4aec4a83de78`，和 diff 相同。
- `git status site/data` 沒有變化。

## 二、測試

- `tests/test_iter01～45` 共 45 個檔全部通過（`logs/iter45_pg_tests.log`）。
- `test_iter45` 的 9 個測試全部通過（含 `test_contrast` 19 種反證）。

## 三、8001 冒煙（內建瀏覽器，desktop 寬度，面板顯示中）

| 項目 | 結果 |
|---|---|
| 進頁時 localStorage | `{"tw.todayTab":"ov"}`（結束時相同） |
| 載入的 `?v=` | 5 個都是新值（伺服器紀錄） |
| `#/help/vr` | 41 列；`help-vr` 有 `on`；**自動捲到量比**（`scrollY` 672）；分頁標題 `名詞說明｜台股資金流` |
| `#/help/xyz` | 網址改成 `#/help`、沒有標示、`scrollY` 0 |
| 點頂欄「?」 | 進 `#/help` |
| 頁尾連結 | `href="#/help"` |
| `#/tools/dv?c=0050`（ETF） | `可領現金元以下捨去；不足 1 股依發行人公告折付現金，可在期限內湊股；實際以發行人發放為準。` |
| `#/tools/dv?c=2330`（股票） | `可領現金元以下捨去；不足 1 股依公司公告折付現金，可在期限內湊股；實際以公司發放為準。` |

- SA 在面板隱藏時沒看到的「自動捲動」，這次面板顯示中已確認會捲。
- 主控台：新版沒有錯誤（只有 SA 原型舊檔 `help.js?v=5bca0ad2` 留下的紀錄）；伺服器 404 只有 `favicon.ico`。
- 320／375 寬、深色、各頁頂欄與連結，留給 QA。

## 四、和設計的差異

- 無。

## 五、待 commit 的檔案（使用者看完後再 commit）

- 程式：`site/help.js`、`site/app.js`、`site/app.css`、`site/tools.js`、`site/index.html`。
- 文件：`README.md`、`docs/iterations/README.md`、`docs/iterations/45/`（`test_iter45` 會讀 `02-pm.md`，必須一起 commit）。
- 測試：`tests/test_iter41.py`、`tests/test_iter45.py`。
- `logs/` 不進 commit。
