# 台股資金流 tw-stock

收集上市、上櫃個股的行情、本益比、三大法人與月營收，寫入 SQL Server，再匯出成靜態 JSON 給網站使用。
網站是純前端（`site/`），不需要後端伺服器，日後可直接部署到 Cloudflare Pages 等靜態主機。

```
資料來源 API ──► twstock collect ──► SQL Server ──► twstock export ──► site/data/*.json ──► 瀏覽器
```

## 專案結構

| 路徑 | 說明 |
|---|---|
| `twstock/fetch.py` | HTTP 請求：每個主機各自節流、被封鎖時退避重試 |
| `twstock/collectors/` | `daily` 行情／本益比／法人、`revenue` 月營收、`industry` 產業別、`history` 補抓歷史、`futures` 台指期分鐘線 |
| `twstock/analysis/` | `flow` 類股資金流象限、`chanlun` 纏論結構圖 |
| `twstock/export.py` | 匯出 `site/data/latest.json` 與 `site/data/stocks/{代號}.json` |
| `site/` | 網站：今日、泡泡圖、排行、自選、個股頁 |
| `data/concepts.csv` | 概念股分類（可自行編輯） |
| `scripts/mac/`、`scripts/windows/` | 安裝、預覽、手動收集、排程 |

## 安裝

需要 Python 3.10 以上、Docker、Microsoft ODBC Driver 18 for SQL Server。

1. 複製 `.env.example` 為 `.env`，填入 `DB_PASSWORD`（至少 8 碼，含大小寫英文、數字、符號）。
2. 啟動資料庫（已有自建的 SQL Server 容器就略過）：
   ```bash
   docker compose up -d
   ```
   Windows 或 Intel Mac 請先在 `.env` 加上 `MSSQL_IMAGE=mcr.microsoft.com/mssql/server:2022-latest`。
3. 執行安裝腳本，建立 `.venv`、安裝套件並建立資料表：
   - Mac：`bash scripts/mac/setup.sh`
   - Windows：雙擊 `scripts\windows\setup.bat`

## 日常使用

指令在 Mac 用 `.venv/bin/python`，在 Windows 用 `.venv\Scripts\python`：

```bash
python -m twstock collect                        # 收集今天的資料並匯出網站 JSON
python -m twstock collect --date 2026-10-28      # 指定日期
python -m twstock history --start 2026-01-02     # 補抓歷史，已有的日期會自動跳過
python -m twstock history --start 2026-01-02 --only insti   # 只補法人
python -m twstock revenue --year 2026 --month 9 --force     # 重抓某月營收
python -m twstock export                         # 只重新匯出網站 JSON
python -m twstock serve                          # 本機預覽 http://localhost:8000
python -m twstock chanlun 2330                   # 產生 output/chanlun_2330.svg
```

也可以直接雙擊：Mac 的 `scripts/mac/preview.command`、`collect.command`，Windows 的 `scripts\windows\preview.bat`、`collect.bat`。

### 自動排程（週一至週五 18:30）

- Mac：`bash scripts/mac/install_schedule.sh`（移除：加上 `--uninstall`）
- Windows：執行 `scripts\windows\install_schedule.bat`（移除：加上 `/uninstall`）

執行紀錄寫入 `logs/collect.log`。電腦在排程時間處於睡眠狀態時，Mac 會在喚醒後補跑，Windows 則需在工作排程器勾選「錯過排程時儘快執行」。

## 注意事項

- 法人資料通常比收盤行情晚公布，網站上的「法人資料」日期可能比「資料日」早一天。資金流與象限都以法人資料日為準。
- 抓取間隔已依各主機設定（證交所 3.5 秒、櫃買 3 秒），請勿調短，否則容易被暫時封鎖。
- `.env` 含資料庫密碼，已列在 `.gitignore`，請勿提交。
- `futures`（台指期分鐘線）使用期交所未公開的端點，目前回傳 404，尚待更換資料來源。
- 資料僅供研究參考，不構成投資建議。
