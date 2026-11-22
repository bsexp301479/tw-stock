# TwStock 資料庫結構（DB Layout）

- 資料庫：`TwStock`（Docker 容器 `MySqlServer`，Azure SQL Edge）
- 依據：實際資料庫的 `sys.tables`／`sys.columns`／`sys.indexes`／`sys.foreign_keys`（唯讀查詢），欄位說明取自 `twstock/db.py` 的 DDL 註解
- 產生日期：2026-11-21（第 40 輪之後）；筆數是當天的概數，只供參考。第 43 輪的 `share_distribution` 依 DDL 補寫
- 建表／遷移：`python3 -u -m twstock setup-db`（可重複執行）

## 共通慣例

- 每張表都有自動編號主鍵（`id`／`*_id`，IDENTITY），實際的「業務鍵」是 `UQ_*` 唯一條件約束。
- 股票與 ETF 分開存放：股票表用 `stock_id → stocks`，ETF 表用 `etf_id → etfs`；個股統計不會讀到 ETF。
- `created_at`／`updated_at` 預設 `GETDATE()`，容器時區是 UTC；需要台灣時間的欄位（`collect_runs`、`market_holidays.fetched_at`）由 Python 傳入。
- 單位：成交量、法人買賣超、借券為「股」；融資融券為「張」；營收與季報為「千元」；金額另有標示。
- `market`／`market_type`：`TWSE` 上市、`TPEx` 上櫃。

## 資料表總覽

| 分類 | 資料表 | 說明 | 加入輪次 | 約略筆數 |
|---|---|---|---|---:|
| 基本資料 | [`stocks`](#stocks) | 股票基本資料 | 第 4 輪前 | 2,000 |
| 基本資料 | [`etfs`](#etfs) | ETF 基本資料 | 4 | 370 |
| 基本資料 | [`industry_chains`](#industry_chains) | 產業鏈族群 | 第 4 輪前 | 6,537 |
| 基本資料 | [`market_holidays`](#market_holidays) | 休市日 | 第 4 輪前 | 24 |
| 行情 | [`daily_prices`](#daily_prices) | 股票日成交 | 第 4 輪前 | 503,177 |
| 行情 | [`etf_daily`](#etf_daily) | ETF 日成交 | 4 | 86,623 |
| 行情 | [`market_index`](#market_index) | 大盤指數 | 第 4 輪前 | 532 |
| 行情 | [`market_breadth`](#market_breadth) | 漲跌家數 | 5 | 28 |
| 行情 | [`futures_daily_prices`](#futures_daily_prices) | 期貨每日行情 | 第 4 輪前 | 19,981 |
| 籌碼 | [`institutional_trades`](#institutional_trades) | 三大法人買賣超（股票，股） | 第 4 輪前 | 473,409 |
| 籌碼 | [`insti_amount`](#insti_amount) | 三大法人買賣金額（市場合計，元） | 第 4 輪前（第 9 輪加 market） | 912 |
| 籌碼 | [`futures_institutional`](#futures_institutional) | 期貨三大法人交易與未平倉 | 第 4 輪前 | 6,135 |
| 籌碼 | [`margin_trades`](#margin_trades) | 融資融券（股票，張） | 4 | 470,093 |
| 籌碼 | [`etf_margin`](#etf_margin) | 融資融券（ETF，張） | 4 | 85,108 |
| 籌碼 | [`margin_market`](#margin_market) | 融資融券市場合計 | 4 | 514 |
| 籌碼 | [`sbl_trades`](#sbl_trades) | 借券賣出（股票，股） | 11 | 474,753 |
| 籌碼 | [`etf_sbl`](#etf_sbl) | 借券賣出（ETF，股） | 11 | 85,165 |
| 籌碼 | [`foreign_holdings`](#foreign_holdings) | 外資及陸資持股（股票） | 29 | 504,077 |
| 籌碼 | [`share_distribution`](#share_distribution) | 集保股權分散（股票與 ETF，每週） | 43 | 0 |
| 基本面 | [`monthly_revenue`](#monthly_revenue) | 月營收 | 第 4 輪前 | 89,641 |
| 基本面 | [`stock_fundamentals`](#stock_fundamentals) | 本益比、淨值比、殖利率（每日） | 第 4 輪前 | 502,097 |
| 基本面 | [`quarterly_financials`](#quarterly_financials) | 季報（年初至今累計） | 10 | 21,498 |
| 除權息與公司事件 | [`price_events`](#price_events) | 股票價格調整事件（除權息、減資、面額變更） | 第 4 輪前 | 1,707 |
| 除權息與公司事件 | [`etf_events`](#etf_events) | ETF 除權息事件 | 24 | 1,224 |
| 除權息與公司事件 | [`dividend_notices`](#dividend_notices) | 除權除息預告表快照 | 40 | 0 |
| 除權息與公司事件 | [`stock_alerts`](#stock_alerts) | 處置／注意股 | 第 4 輪前 | 876 |
| ETF 持股 | [`etf_holdings`](#etf_holdings) | 主動型 ETF 持股明細 | 5 | 65,534 |
| ETF 持股 | [`etf_holding_summary`](#etf_holding_summary) | 主動型 ETF 持股彙總 | 5 | 1,334 |
| ETF 持股 | [`etf_holding_gaps`](#etf_holding_gaps) | ETF 確定沒有持股明細的日期 | 6 | 8 |
| 系統 | [`collect_runs`](#collect_runs) | 收集執行紀錄 | 第 4 輪前 | 25 |
| 非本專案管理 | [`futures_minute_prices`](#futures_minute_prices) | 期貨分鐘行情（非本專案建立） | — | 0 |

## 關聯（外鍵）

```text
stocks.stock_id
  └─ daily_prices
  └─ foreign_holdings
  └─ institutional_trades
  └─ margin_trades
  └─ monthly_revenue
  └─ price_events
  └─ quarterly_financials
  └─ sbl_trades
  └─ stock_alerts
  └─ stock_fundamentals
etfs.etf_id
  └─ etf_daily
  └─ etf_events
  └─ etf_holding_gaps
  └─ etf_holding_summary
  └─ etf_holdings
  └─ etf_margin
  └─ etf_sbl
```

沒有外鍵、以代號字串關聯的表：`industry_chains.stock_code`（含興櫃）、`dividend_notices.code`、`share_distribution.code`（股票與 ETF 同表，寫入時只收 `stocks`／`etfs` 已有代號）。

## 一、基本資料

### stocks

股票基本資料。約 2,000 筆。

| # | 欄位 | 型別 | NULL | 預設 | 說明 |
|---:|---|---|:---:|---|---|
| 1 | `stock_id` | INT |  |  | 自動編號主鍵；股票 ID（→ stocks.stock_id） |
| 2 | `stock_code` | NVARCHAR(10) |  |  | 股票代號 |
| 3 | `stock_name` | NVARCHAR(50) |  |  | 股票名稱 |
| 4 | `market_type` | NVARCHAR(10) |  |  | 市場：TWSE 上市／TPEx 上櫃 |
| 5 | `industry` | NVARCHAR(50) | Y |  | 產業別 |
| 6 | `listed_date` | DATE | Y |  | 上市櫃日期 |
| 7 | `created_at` | DATETIME |  | GETDATE() | 建立時間（容器 GETDATE()，UTC） |
| 8 | `updated_at` | DATETIME |  | GETDATE() | 更新時間（容器 GETDATE()，UTC） |
| 9 | `shares` | BIGINT | Y |  | 第 11 輪：發行股數（update_industry 一併寫入；目前股數，不保留歷史） |

**索引／條件約束**

- PK `PK__stocks__E8666862ECD74CB1`：(stock_id)
- UNIQUE `UQ_stock_code`：(stock_code)

### etfs

ETF 基本資料。約 370 筆。

| # | 欄位 | 型別 | NULL | 預設 | 說明 |
|---:|---|---|:---:|---|---|
| 1 | `etf_id` | INT |  |  | 自動編號主鍵；ETF ID（→ etfs.etf_id） |
| 2 | `etf_code` | NVARCHAR(10) |  |  | ETF 代號 |
| 3 | `etf_name` | NVARCHAR(50) |  |  | ETF 名稱 |
| 4 | `market_type` | NVARCHAR(10) |  |  | 市場：TWSE 上市／TPEx 上櫃 |
| 5 | `created_at` | DATETIME |  | GETDATE() | 建立時間（容器 GETDATE()，UTC） |
| 6 | `updated_at` | DATETIME |  | GETDATE() | 更新時間（容器 GETDATE()，UTC） |

**索引／條件約束**

- PK `PK__etfs__91787216CC324318`：(etf_id)
- UNIQUE `UQ_etf_code`：(etf_code)

### industry_chains

產業鏈族群。約 6,537 筆。

| # | 欄位 | 型別 | NULL | 預設 | 說明 |
|---:|---|---|:---:|---|---|
| 1 | `id` | INT |  |  | 自動編號主鍵 |
| 2 | `chain_id` | NVARCHAR(10) |  |  | 產業鏈代碼 |
| 3 | `chain_name` | NVARCHAR(50) |  |  | 半導體 |
| 4 | `segment_id` | NVARCHAR(10) |  |  | 上中下游區段代碼 |
| 5 | `segment_name` | NVARCHAR(100) |  |  | IC/晶圓製造 |
| 6 | `sub_id` | NVARCHAR(10) |  |  | 沒有細項時為空字串 |
| 7 | `sub_name` | NVARCHAR(100) |  |  | 晶圓製造 |
| 8 | `stock_code` | NVARCHAR(10) |  |  | 股票代號（含興櫃，不用外鍵） |
| 9 | `updated_at` | DATETIME |  | GETDATE() | 更新時間（容器 GETDATE()，UTC） |

**索引／條件約束**

- PK `PK__industry__3213E83F62D1C374`：(id)
- UNIQUE `UQ_industry_chains`：(chain_id,segment_id,sub_id,stock_code)
- INDEX `IX_industry_chains_code`：(stock_code)

### market_holidays

休市日。約 24 筆。

| # | 欄位 | 型別 | NULL | 預設 | 說明 |
|---:|---|---|:---:|---|---|
| 1 | `holiday_date` | DATE |  |  | 休市日 |
| 2 | `name` | NVARCHAR(100) |  |  | 休市名稱 |
| 3 | `source` | NVARCHAR(10) |  |  | official 官方休市表／adhoc 收集時判定的臨時休市 |
| 4 | `fetched_at` | DATETIME2(0) |  |  | 台灣時間 |

**索引／條件約束**

- PK `PK__market_h__30A67917C66527E2`：(holiday_date)

## 二、行情

### daily_prices

股票日成交。約 503,177 筆。

| # | 欄位 | 型別 | NULL | 預設 | 說明 |
|---:|---|---|:---:|---|---|
| 1 | `price_id` | BIGINT |  |  | 自動編號主鍵 |
| 2 | `stock_id` | INT |  |  | 股票 ID（→ stocks.stock_id） |
| 3 | `trade_date` | DATE |  |  | 交易日 |
| 4 | `open_price` | DECIMAL(10,2) | Y |  | 開盤價 |
| 5 | `high_price` | DECIMAL(10,2) | Y |  | 最高價 |
| 6 | `low_price` | DECIMAL(10,2) | Y |  | 最低價 |
| 7 | `close_price` | DECIMAL(10,2) | Y |  | 收盤價 |
| 8 | `volume` | BIGINT | Y |  | 成交量（股） |
| 9 | `trade_value` | BIGINT | Y |  | 成交金額（元） |
| 10 | `trade_count` | INT | Y |  | 成交筆數 |
| 11 | `change` | DECIMAL(10,2) | Y |  | 漲跌 |
| 12 | `created_at` | DATETIME |  | GETDATE() | 建立時間（容器 GETDATE()，UTC） |

**索引／條件約束**

- PK `PK__daily_pr__1681726D3B85AC4F`：(price_id)
- UNIQUE `UQ_daily_prices`：(stock_id,trade_date)
- INDEX `IX_daily_prices_date`：(trade_date)
- INDEX `IX_daily_prices_stock`：(stock_id,trade_date)

### etf_daily

ETF 日成交。約 86,623 筆。

| # | 欄位 | 型別 | NULL | 預設 | 說明 |
|---:|---|---|:---:|---|---|
| 1 | `id` | BIGINT |  |  | 自動編號主鍵 |
| 2 | `etf_id` | INT |  |  | ETF ID（→ etfs.etf_id） |
| 3 | `trade_date` | DATE |  |  | 交易日 |
| 4 | `open_price` | DECIMAL(10,2) | Y |  | 開盤價 |
| 5 | `high_price` | DECIMAL(10,2) | Y |  | 最高價 |
| 6 | `low_price` | DECIMAL(10,2) | Y |  | 最低價 |
| 7 | `close_price` | DECIMAL(10,2) | Y |  | 收盤價 |
| 8 | `volume` | BIGINT | Y |  | 股 |
| 9 | `trade_value` | BIGINT | Y |  | 元 |
| 10 | `trade_count` | INT | Y |  | 成交筆數 |
| 11 | `change` | DECIMAL(10,2) | Y |  | 漲跌 |
| 12 | `created_at` | DATETIME |  | GETDATE() | 建立時間（容器 GETDATE()，UTC） |

**索引／條件約束**

- PK `PK__etf_dail__3213E83F1CE4E516`：(id)
- UNIQUE `UQ_etf_daily`：(etf_id,trade_date)
- INDEX `IX_etf_daily_date`：(trade_date)

### market_index

大盤指數。約 532 筆。

| # | 欄位 | 型別 | NULL | 預設 | 說明 |
|---:|---|---|:---:|---|---|
| 1 | `id` | INT |  |  | 自動編號主鍵 |
| 2 | `index_code` | NVARCHAR(10) |  |  | TAIEX 加權指數 / TPEX 櫃買指數 |
| 3 | `trade_date` | DATE |  |  | 交易日 |
| 4 | `open_price` | DECIMAL(10,2) | Y |  | 開盤價 |
| 5 | `high_price` | DECIMAL(10,2) | Y |  | 最高價 |
| 6 | `low_price` | DECIMAL(10,2) | Y |  | 最低價 |
| 7 | `close_price` | DECIMAL(10,2) |  |  | 收盤指數 |
| 8 | `change` | DECIMAL(10,2) | Y |  | 漲跌 |
| 9 | `created_at` | DATETIME |  | GETDATE() | 建立時間（容器 GETDATE()，UTC） |

**索引／條件約束**

- PK `PK__market_i__3213E83FA8482E4C`：(id)
- UNIQUE `UQ_market_index`：(index_code,trade_date)

### market_breadth

漲跌家數。約 28 筆。

| # | 欄位 | 型別 | NULL | 預設 | 說明 |
|---:|---|---|:---:|---|---|
| 1 | `id` | INT |  |  | 自動編號主鍵 |
| 2 | `trade_date` | DATE |  |  | 交易日 |
| 3 | `market` | NVARCHAR(10) |  |  | 市場：TWSE 上市／TPEx 上櫃 |
| 4 | `up` | INT |  |  | 上漲家數 |
| 5 | `up_limit` | INT | Y |  | 漲停家數 |
| 6 | `down` | INT |  |  | 下跌家數 |
| 7 | `down_limit` | INT | Y |  | 跌停家數 |
| 8 | `flat` | INT |  |  | 平盤家數 |
| 9 | `no_trade` | INT | Y |  | 未成交（上櫃含暫停交易） |
| 10 | `created_at` | DATETIME |  | GETDATE() | 建立時間（容器 GETDATE()，UTC） |

**索引／條件約束**

- PK `PK__market_b__3213E83FC86B7CB4`：(id)
- UNIQUE `UQ_market_breadth`：(trade_date,market)

### futures_daily_prices

期貨每日行情。約 19,981 筆。

| # | 欄位 | 型別 | NULL | 預設 | 說明 |
|---:|---|---|:---:|---|---|
| 1 | `id` | BIGINT |  |  | 自動編號主鍵 |
| 2 | `trade_date` | DATE |  |  | 交易日 |
| 3 | `commodity_id` | NVARCHAR(10) |  |  | TX 台指期、MTX 小台… |
| 4 | `contract_month` | CHAR(6) |  |  | 202611 |
| 5 | `session` | NVARCHAR(5) |  |  | DAY 日盤 / NIGHT 夜盤 |
| 6 | `open_price` | DECIMAL(10,2) | Y |  | 開盤價 |
| 7 | `high_price` | DECIMAL(10,2) | Y |  | 最高價 |
| 8 | `low_price` | DECIMAL(10,2) | Y |  | 最低價 |
| 9 | `close_price` | DECIMAL(10,2) | Y |  | 收盤價 |
| 10 | `change` | DECIMAL(10,2) | Y |  | 漲跌 |
| 11 | `volume` | INT | Y |  | 成交量 |
| 12 | `settlement` | DECIMAL(10,2) | Y |  | 夜盤沒有 |
| 13 | `open_interest` | INT | Y |  | 未沖銷契約數，夜盤沒有 |
| 14 | `created_at` | DATETIME |  | GETDATE() | 建立時間（容器 GETDATE()，UTC） |

**索引／條件約束**

- PK `PK__futures___3213E83F7DAF531A`：(id)
- UNIQUE `UQ_futures_daily`：(commodity_id,contract_month,session,trade_date)

## 三、籌碼

### institutional_trades

三大法人買賣超（股票，股）。約 473,409 筆。

| # | 欄位 | 型別 | NULL | 預設 | 說明 |
|---:|---|---|:---:|---|---|
| 1 | `inst_id` | BIGINT |  |  | 自動編號主鍵 |
| 2 | `stock_id` | INT |  |  | 股票 ID（→ stocks.stock_id） |
| 3 | `trade_date` | DATE |  |  | 交易日 |
| 4 | `foreign_net` | BIGINT | Y |  | 外資及陸資（含外資自營商） |
| 5 | `trust_net` | BIGINT | Y |  | 投信 |
| 6 | `dealer_net` | BIGINT | Y |  | 自營商（自行買賣 + 避險） |
| 7 | `total_net` | BIGINT | Y |  | 三大法人合計 |
| 8 | `created_at` | DATETIME |  | GETDATE() | 建立時間（容器 GETDATE()，UTC） |

**索引／條件約束**

- PK `PK__institut__0206940D778DAD6C`：(inst_id)
- UNIQUE `UQ_institutional`：(stock_id,trade_date)
- INDEX `IX_institutional_date`：(trade_date)

### insti_amount

三大法人買賣金額（市場合計，元）。約 912 筆。

| # | 欄位 | 型別 | NULL | 預設 | 說明 |
|---:|---|---|:---:|---|---|
| 1 | `id` | INT |  |  | 自動編號主鍵 |
| 2 | `trade_date` | DATE |  |  | 交易日 |
| 3 | `unit` | NVARCHAR(20) |  |  | foreign 外資及陸資(不含外資自營商) / foreign_dealer 外資自營商 / |
| 4 | `buy_amount` | BIGINT | Y |  | 買進金額（元） |
| 5 | `sell_amount` | BIGINT | Y |  | 賣出金額（元） |
| 6 | `net_amount` | BIGINT | Y |  | 買賣差額（元） |
| 7 | `created_at` | DATETIME |  | GETDATE() | 建立時間（容器 GETDATE()，UTC） |
| 8 | `market` | NVARCHAR(10) |  | 'TWSE' | 第 9 輪遷移（既有資料庫）：加 market（既有列 = TWSE）→ 刪舊唯一鍵 → 建新唯一鍵；每一步都先判斷，可重複執行 |

**索引／條件約束**

- PK `PK__insti_am__3213E83F00C98B82`：(id)
- UNIQUE `UQ_insti_amount_market`：(trade_date,market,unit)

### futures_institutional

期貨三大法人交易與未平倉。約 6,135 筆。

| # | 欄位 | 型別 | NULL | 預設 | 說明 |
|---:|---|---|:---:|---|---|
| 1 | `id` | BIGINT |  |  | 自動編號主鍵 |
| 2 | `trade_date` | DATE |  |  | 交易日 |
| 3 | `commodity_id` | NVARCHAR(10) |  |  | TXF 大台、MXF 小台、TMF 微台 |
| 4 | `investor` | NVARCHAR(10) |  |  | foreign 外資及陸資 / trust 投信 / dealer 自營商 |
| 5 | `long_trade` | INT | Y |  | 多方交易口數 |
| 6 | `short_trade` | INT | Y |  | 空方交易口數 |
| 7 | `net_trade` | INT | Y |  | 多空交易淨額（口） |
| 8 | `long_oi` | INT | Y |  | 多方未平倉口數 |
| 9 | `short_oi` | INT | Y |  | 空方未平倉口數 |
| 10 | `net_oi` | INT | Y |  | 多空未平倉淨額 |
| 11 | `net_oi_amount` | BIGINT | Y |  | 多空未平倉契約金額淨額（千元） |
| 12 | `created_at` | DATETIME |  | GETDATE() | 建立時間（容器 GETDATE()，UTC） |

**索引／條件約束**

- PK `PK__futures___3213E83F9B42E84E`：(id)
- UNIQUE `UQ_futures_institutional`：(commodity_id,investor,trade_date)

### margin_trades

融資融券（股票，張）。約 470,093 筆。

| # | 欄位 | 型別 | NULL | 預設 | 說明 |
|---:|---|---|:---:|---|---|
| 1 | `id` | BIGINT |  |  | 自動編號主鍵 |
| 2 | `stock_id` | INT |  |  | 股票 ID（→ stocks.stock_id） |
| 3 | `trade_date` | DATE |  |  | 交易日 |
| 4 | `margin_buy` | INT | Y |  | 融資買進 |
| 5 | `margin_sell` | INT | Y |  | 融資賣出 |
| 6 | `margin_redeem` | INT | Y |  | 現金償還 |
| 7 | `margin_prev` | INT |  |  | 融資前日餘額 |
| 8 | `margin_balance` | INT |  |  | 融資今日餘額 |
| 9 | `margin_limit` | INT | Y |  | 融資限額（上市：次一營業日限額） |
| 10 | `short_sell` | INT | Y |  | 融券賣出 |
| 11 | `short_buy` | INT | Y |  | 融券買進（回補） |
| 12 | `short_redeem` | INT | Y |  | 現券償還 |
| 13 | `short_prev` | INT |  |  | 融券前日餘額 |
| 14 | `short_balance` | INT |  |  | 融券今日餘額 |
| 15 | `short_limit` | INT | Y |  | 融券限額 |
| 16 | `offset_lots` | INT | Y |  | 資券互抵（offset 是保留字） |
| 17 | `note` | NVARCHAR(20) | Y |  | 上市註記／上櫃備註原文 |
| 18 | `created_at` | DATETIME |  | GETDATE() | 建立時間（容器 GETDATE()，UTC） |

**索引／條件約束**

- PK `PK__margin_t__3213E83FE2246AEE`：(id)
- UNIQUE `UQ_margin_trades`：(stock_id,trade_date)
- INDEX `IX_margin_trades_date`：(trade_date)

### etf_margin

融資融券（ETF，張）。約 85,108 筆。

| # | 欄位 | 型別 | NULL | 預設 | 說明 |
|---:|---|---|:---:|---|---|
| 1 | `id` | BIGINT |  |  | 自動編號主鍵 |
| 2 | `etf_id` | INT |  |  | ETF ID（→ etfs.etf_id） |
| 3 | `trade_date` | DATE |  |  | 交易日 |
| 4 | `margin_buy` | INT | Y |  | 融資買進 |
| 5 | `margin_sell` | INT | Y |  | 融資賣出 |
| 6 | `margin_redeem` | INT | Y |  | 現金償還 |
| 7 | `margin_prev` | INT |  |  | 融資前日餘額 |
| 8 | `margin_balance` | INT |  |  | 融資今日餘額 |
| 9 | `margin_limit` | INT | Y |  | 融資限額（上市：次一營業日限額） |
| 10 | `short_sell` | INT | Y |  | 融券賣出 |
| 11 | `short_buy` | INT | Y |  | 融券買進（回補） |
| 12 | `short_redeem` | INT | Y |  | 現券償還 |
| 13 | `short_prev` | INT |  |  | 融券前日餘額 |
| 14 | `short_balance` | INT |  |  | 融券今日餘額 |
| 15 | `short_limit` | INT | Y |  | 融券限額 |
| 16 | `offset_lots` | INT | Y |  | 資券互抵（offset 是保留字） |
| 17 | `note` | NVARCHAR(20) | Y |  | 上市註記／上櫃備註原文 |
| 18 | `created_at` | DATETIME |  | GETDATE() | 建立時間（容器 GETDATE()，UTC） |

**索引／條件約束**

- PK `PK__etf_marg__3213E83F99CA1A6D`：(id)
- UNIQUE `UQ_etf_margin`：(etf_id,trade_date)

### margin_market

融資融券市場合計。約 514 筆。

| # | 欄位 | 型別 | NULL | 預設 | 說明 |
|---:|---|---|:---:|---|---|
| 1 | `id` | INT |  |  | 自動編號主鍵 |
| 2 | `trade_date` | DATE |  |  | 交易日 |
| 3 | `market` | NVARCHAR(10) |  |  | 市場：TWSE 上市／TPEx 上櫃 |
| 4 | `margin_prev` | BIGINT |  |  | 官方融資前日餘額（張，含 ETF 與其他證券） |
| 5 | `margin_balance` | BIGINT |  |  | 官方融資今日餘額（張） |
| 6 | `short_prev` | BIGINT |  |  | 官方融券（張） |
| 7 | `short_balance` | BIGINT |  |  | 官方融券今日餘額（張） |
| 8 | `amount_prev` | BIGINT |  |  | 官方融資金額（仟元） |
| 9 | `amount_balance` | BIGINT |  |  | 官方融資金額今日餘額（仟元） |
| 10 | `created_at` | DATETIME |  | GETDATE() | 建立時間（容器 GETDATE()，UTC） |

**索引／條件約束**

- PK `PK__margin_m__3213E83FC3C82726`：(id)
- UNIQUE `UQ_margin_market`：(trade_date,market)

### sbl_trades

借券賣出（股票，股）。約 474,753 筆。

| # | 欄位 | 型別 | NULL | 預設 | 說明 |
|---:|---|---|:---:|---|---|
| 1 | `id` | BIGINT |  |  | 自動編號主鍵 |
| 2 | `stock_id` | INT |  |  | 股票 ID（→ stocks.stock_id） |
| 3 | `trade_date` | DATE |  |  | 交易日 |
| 4 | `sbl_prev` | BIGINT |  |  | 前日餘額 |
| 5 | `sbl_sell` | BIGINT | Y |  | 當日賣出 |
| 6 | `sbl_return` | BIGINT | Y |  | 當日還券 |
| 7 | `sbl_adjust` | BIGINT | Y |  | 當日調整 |
| 8 | `sbl_balance` | BIGINT |  |  | 當日餘額 |
| 9 | `sbl_limit` | BIGINT | Y |  | 次一營業日可借券賣出限額 |
| 10 | `note` | NVARCHAR(20) | Y |  | 備註原文（X 停券、V 不得借券交易…） |
| 11 | `created_at` | DATETIME |  | GETDATE() | 建立時間（容器 GETDATE()，UTC） |

**索引／條件約束**

- PK `PK__sbl_trad__3213E83FE598C4CB`：(id)
- UNIQUE `UQ_sbl_trades`：(stock_id,trade_date)
- INDEX `IX_sbl_trades_date`：(trade_date)

### etf_sbl

借券賣出（ETF，股）。約 85,165 筆。

| # | 欄位 | 型別 | NULL | 預設 | 說明 |
|---:|---|---|:---:|---|---|
| 1 | `id` | BIGINT |  |  | 自動編號主鍵 |
| 2 | `etf_id` | INT |  |  | ETF ID（→ etfs.etf_id） |
| 3 | `trade_date` | DATE |  |  | 交易日 |
| 4 | `sbl_prev` | BIGINT |  |  | 前日餘額 |
| 5 | `sbl_sell` | BIGINT | Y |  | 當日賣出 |
| 6 | `sbl_return` | BIGINT | Y |  | 當日還券 |
| 7 | `sbl_adjust` | BIGINT | Y |  | 當日調整 |
| 8 | `sbl_balance` | BIGINT |  |  | 當日餘額 |
| 9 | `sbl_limit` | BIGINT | Y |  | 次一營業日可借券賣出限額 |
| 10 | `note` | NVARCHAR(20) | Y |  | 備註原文（X 停券、V 不得借券交易…） |
| 11 | `created_at` | DATETIME |  | GETDATE() | 建立時間（容器 GETDATE()，UTC） |

**索引／條件約束**

- PK `PK__etf_sbl__3213E83F6D1ACDAA`：(id)
- UNIQUE `UQ_etf_sbl`：(etf_id,trade_date)

### foreign_holdings

外資及陸資持股（股票）。約 504,077 筆。

| # | 欄位 | 型別 | NULL | 預設 | 說明 |
|---:|---|---|:---:|---|---|
| 1 | `id` | BIGINT |  |  | 自動編號主鍵 |
| 2 | `stock_id` | INT |  |  | 股票 ID（→ stocks.stock_id） |
| 3 | `trade_date` | DATE |  |  | 交易日 |
| 4 | `issued` | BIGINT | Y |  | 發行股數 |
| 5 | `fh_shares` | BIGINT | Y |  | 外資及陸資持有股數 |
| 6 | `fh_ratio` | DECIMAL(6,2) |  |  | 外資及陸資持股比率 % |
| 7 | `avail_ratio` | DECIMAL(6,2) | Y |  | 尚可投資比率 % |
| 8 | `limit_ratio` | DECIMAL(6,2) | Y |  | 法令投資上限比率 % |
| 9 | `created_at` | DATETIME |  | GETDATE() | 建立時間（容器 GETDATE()，UTC） |

**索引／條件約束**

- PK `PK__foreign___3213E83FDA9F8085`：(id)
- UNIQUE `UQ_foreign_holdings`：(stock_id,trade_date)
- INDEX `IX_foreign_holdings_date`：(trade_date)

### share_distribution

集保股權分散（第 43 輪；股票與 ETF 同表，每週一次，一檔一週一列）。套用 `setup-db` 前資料庫還沒有這張表，欄位依 `db.py` 的 DDL 補寫。

| # | 欄位 | 型別 | NULL | 預設 | 說明 |
|---:|---|---|:---:|---|---|
| 1 | `id` | BIGINT |  |  | 自動編號主鍵 |
| 2 | `code` | NVARCHAR(10) |  |  | 股票或 ETF 代號（寫入時只收 stocks、etfs 表已有的） |
| 3 | `is_etf` | BIT |  |  | 1 = ETF，0 = 股票（依寫入時命中的表） |
| 4 | `data_date` | DATE |  |  | 官方資料日期（每週最後一個營業日），不是抓取日 |
| 5 | `n1` | INT |  |  | 第 1 級人數 |
| 6 | `n2` | INT |  |  | 第 2 級人數 |
| 7 | `n3` | INT |  |  | 第 3 級人數 |
| 8 | `n4` | INT |  |  | 第 4 級人數 |
| 9 | `n5` | INT |  |  | 第 5 級人數 |
| 10 | `n6` | INT |  |  | 第 6 級人數 |
| 11 | `n7` | INT |  |  | 第 7 級人數 |
| 12 | `n8` | INT |  |  | 第 8 級人數 |
| 13 | `n9` | INT |  |  | 第 9 級人數 |
| 14 | `n10` | INT |  |  | 第 10 級人數 |
| 15 | `n11` | INT |  |  | 第 11 級人數 |
| 16 | `n12` | INT |  |  | 第 12 級人數 |
| 17 | `n13` | INT |  |  | 第 13 級人數 |
| 18 | `n14` | INT |  |  | 第 14 級人數 |
| 19 | `n15` | INT |  |  | 第 15 級人數 |
| 20 | `n16` | INT |  |  | 第 16 級人數（16 = 差異數調整） |
| 21 | `s1` | BIGINT |  |  | 第 1 級股數 |
| 22 | `s2` | BIGINT |  |  | 第 2 級股數 |
| 23 | `s3` | BIGINT |  |  | 第 3 級股數 |
| 24 | `s4` | BIGINT |  |  | 第 4 級股數 |
| 25 | `s5` | BIGINT |  |  | 第 5 級股數 |
| 26 | `s6` | BIGINT |  |  | 第 6 級股數 |
| 27 | `s7` | BIGINT |  |  | 第 7 級股數 |
| 28 | `s8` | BIGINT |  |  | 第 8 級股數 |
| 29 | `s9` | BIGINT |  |  | 第 9 級股數 |
| 30 | `s10` | BIGINT |  |  | 第 10 級股數 |
| 31 | `s11` | BIGINT |  |  | 第 11 級股數 |
| 32 | `s12` | BIGINT |  |  | 第 12 級股數 |
| 33 | `s13` | BIGINT |  |  | 第 13 級股數 |
| 34 | `s14` | BIGINT |  |  | 第 14 級股數 |
| 35 | `s15` | BIGINT |  |  | 第 15 級股數 |
| 36 | `s16` | BIGINT |  |  | 第 16 級股數（16 = 差異數調整） |
| 37 | `n_total` | INT |  |  | 17 級（合計）人數 = 1～15 級人數和 |
| 38 | `s_total` | BIGINT |  |  | 17 級（合計）股數 = 1～15 級股數和 − 16 級股數；比例的分母 |
| 39 | `fetched_at` | DATETIME |  | GETDATE() | 寫入時間（容器 GETDATE()，UTC） |

- 分級（股）：1 = 1～999（未滿 1 張）、2 = 1,000～5,000、3 = 5,001～10,000、4 = 10,001～15,000、5 = 15,001～20,000、6 = 20,001～30,000、7 = 30,001～40,000、8 = 40,001～50,000、9 = 50,001～100,000、10 = 100,001～200,000、11 = 200,001～400,000、12 = 400,001～600,000、13 = 600,001～800,000、14 = 800,001～1,000,000、15 = 1,000,001 以上。
- 官方「占集保庫存數比例%」不存（匯出時由股數自算）。

**索引／條件約束**

- UNIQUE `UQ_share_distribution`：(code,data_date)
- INDEX `IX_share_distribution_date`：(data_date)

## 四、基本面

### monthly_revenue

月營收。約 89,641 筆。

| # | 欄位 | 型別 | NULL | 預設 | 說明 |
|---:|---|---|:---:|---|---|
| 1 | `rev_id` | INT |  |  | 自動編號主鍵 |
| 2 | `stock_id` | INT |  |  | 股票 ID（→ stocks.stock_id） |
| 3 | `revenue_year` | INT |  |  | 營收年度（西元） |
| 4 | `revenue_month` | INT |  |  | 營收月份 |
| 5 | `revenue` | BIGINT | Y |  | 當月營收（千元） |
| 6 | `revenue_mom` | DECIMAL(10,2) | Y |  | 月增率 % |
| 7 | `revenue_yoy` | DECIMAL(10,2) | Y |  | 年增率 % |
| 8 | `created_at` | DATETIME |  | GETDATE() | 建立時間（容器 GETDATE()，UTC） |

**索引／條件約束**

- PK `PK__monthly___397465D6239C1B15`：(rev_id)
- UNIQUE `UQ_monthly_revenue`：(stock_id,revenue_year,revenue_month)
- INDEX `IX_monthly_rev_stock`：(stock_id,revenue_year,revenue_month)

### stock_fundamentals

本益比、淨值比、殖利率（每日）。約 502,097 筆。

| # | 欄位 | 型別 | NULL | 預設 | 說明 |
|---:|---|---|:---:|---|---|
| 1 | `fund_id` | INT |  |  | 自動編號主鍵 |
| 2 | `stock_id` | INT |  |  | 股票 ID（→ stocks.stock_id） |
| 3 | `trade_date` | DATE |  |  | 交易日 |
| 4 | `eps` | DECIMAL(10,2) | Y |  | EPS |
| 5 | `pe_ratio` | DECIMAL(10,2) | Y |  | 本益比 |
| 6 | `pb_ratio` | DECIMAL(10,2) | Y |  | 股價淨值比 |
| 7 | `dividend_yield` | DECIMAL(10,4) | Y |  | 殖利率 % |
| 8 | `created_at` | DATETIME |  | GETDATE() | 建立時間（容器 GETDATE()，UTC） |

**索引／條件約束**

- PK `PK__stock_fu__B3D22395151C000B`：(fund_id)
- UNIQUE `UQ_fundamentals`：(stock_id,trade_date)

### quarterly_financials

季報（年初至今累計）。約 21,498 筆。

| # | 欄位 | 型別 | NULL | 預設 | 說明 |
|---:|---|---|:---:|---|---|
| 1 | `id` | INT |  |  | 自動編號主鍵 |
| 2 | `stock_id` | INT |  |  | 股票 ID（→ stocks.stock_id） |
| 3 | `fin_year` | INT |  |  | 財報年度（西元） |
| 4 | `fin_quarter` | TINYINT |  |  | 季別 1～4 |
| 5 | `industry_tbl` | NVARCHAR(10) |  |  | 解析來源表：ci 一般業、fh 金控、basi 銀行、bd 證券、ins 保險、mim 其他 |
| 6 | `revenue` | BIGINT | Y |  | 營業收入（年初至今累計，千元） |
| 7 | `gross_profit` | BIGINT | Y |  | 營業毛利（累計，千元） |
| 8 | `op_income` | BIGINT | Y |  | 營業利益（累計，千元） |
| 9 | `net_income` | BIGINT | Y |  | 本期淨利（累計，千元） |
| 10 | `eps` | DECIMAL(10,2) | Y |  | 基本每股盈餘（累計，元） |
| 11 | `first_seen` | DATE | Y |  | 日常收集第一次收到的日期（補抓為 NULL） |
| 12 | `created_at` | DATETIME |  | GETDATE() | 建立時間（容器 GETDATE()，UTC） |
| 13 | `updated_at` | DATETIME |  | GETDATE() | 更新時間（容器 GETDATE()，UTC） |

**索引／條件約束**

- PK `PK__quarterl__3213E83F21749F43`：(id)
- UNIQUE `UQ_quarterly_financials`：(stock_id,fin_year,fin_quarter)

## 五、除權息與公司事件

### price_events

股票價格調整事件（除權息、減資、面額變更）。約 1,707 筆。

| # | 欄位 | 型別 | NULL | 預設 | 說明 |
|---:|---|---|:---:|---|---|
| 1 | `id` | INT |  |  | 自動編號主鍵 |
| 2 | `stock_id` | INT |  |  | 股票 ID（→ stocks.stock_id） |
| 3 | `event_date` | DATE |  |  | 官方日期（除權息日／恢復買賣日），可能是休市日 |
| 4 | `event_type` | NVARCHAR(4) |  |  | 息／權／權息／減（減資）／面（面額變更） |
| 5 | `prev_close` | DECIMAL(10,2) |  |  | 除權息前收盤價／停止買賣前收盤價格 |
| 6 | `ref_price` | DECIMAL(10,2) |  |  | 除權息參考價／恢復買賣參考價 |
| 7 | `source` | NVARCHAR(10) |  |  | TWT49U / TWTAUU / TWTB8U / TPEX_EX |
| 8 | `created_at` | DATETIME |  | GETDATE() | 建立時間（容器 GETDATE()，UTC） |
| 9 | `div_ref` | DECIMAL(10,2) | Y |  | 第 19 輪：減除股利參考價（只扣股利、不扣現金增資；TWT49U、TPEX_EX 才有，其他來源 NULL），分辨配股與現金增資 |
| 10 | `div_total` | DECIMAL(12,6) | Y |  | 第 24 輪 F24-5：股利金額（TWT49U、TPEX_EX 才有，其他來源 NULL）：權值+息值、每股現金股利（上市只有「息」）、每仟股無償配股（只有上櫃） |
| 11 | `div_cash` | DECIMAL(12,6) | Y |  | 每股現金股利（第 24 輪） |
| 12 | `stock_div` | DECIMAL(14,8) | Y |  | 每仟股無償配股（第 24 輪，只有上櫃） |

**索引／條件約束**

- PK `PK__price_ev__3213E83F4C8EC4EB`：(id)
- UNIQUE `UQ_price_events`：(stock_id,event_date,source)

### etf_events

ETF 除權息事件。約 1,224 筆。

| # | 欄位 | 型別 | NULL | 預設 | 說明 |
|---:|---|---|:---:|---|---|
| 1 | `id` | INT |  |  | 自動編號主鍵 |
| 2 | `etf_id` | INT |  |  | ETF ID（→ etfs.etf_id） |
| 3 | `event_date` | DATE |  |  | 官方除息日 |
| 4 | `event_type` | NVARCHAR(4) |  |  | 息／權／權息 |
| 5 | `prev_close` | DECIMAL(10,2) |  |  | 除息前收盤價 |
| 6 | `ref_price` | DECIMAL(10,2) |  |  | 除息參考價 |
| 7 | `div_cash` | DECIMAL(12,6) | Y |  | 每單位配息：上市「權值+息值」、上櫃「息值」 |
| 8 | `source` | NVARCHAR(10) |  |  | TWT49U / TPEX_EX |
| 9 | `created_at` | DATETIME |  | GETDATE() | 建立時間（容器 GETDATE()，UTC） |

**索引／條件約束**

- PK `PK__etf_even__3213E83FD10C57C0`：(id)
- UNIQUE `UQ_etf_events`：(etf_id,event_date,source)

### dividend_notices

除權除息預告表快照。約 0 筆。

| # | 欄位 | 型別 | NULL | 預設 | 說明 |
|---:|---|---|:---:|---|---|
| 1 | `id` | INT |  |  | 自動編號主鍵 |
| 2 | `code` | NVARCHAR(10) |  |  | 股票或 ETF 代號（寫入時只收 stocks、etfs 表已有的） |
| 3 | `market` | NVARCHAR(4) |  |  | 市場：TWSE 上市／TPEx 上櫃 |
| 4 | `is_etf` | BIT |  |  | 1 = ETF，0 = 股票 |
| 5 | `ex_date` | DATE |  |  | 除權除息日 |
| 6 | `event_type` | NVARCHAR(4) |  |  | 息／權／權息 |
| 7 | `cash_div` | DECIMAL(16,8) | Y |  | 每股現金股利；NULL = 待公告 |
| 8 | `stock_ratio` | DECIMAL(16,8) |  | 0 | 每股無償配股率（× 1,000 = 每千股配股） |
| 9 | `sub_ratio` | DECIMAL(16,8) |  | 0 | 現金增資配股率 |
| 10 | `sub_price` | DECIMAL(10,2) | Y |  | 現金增資認購價；尚未公告或沒有現增 = NULL |
| 11 | `first_seen` | DATE |  |  | 第一次在預告表看到的抓取日（台灣日期） |
| 12 | `last_seen` | DATE |  |  | 最近一次在預告表看到的抓取日 |
| 13 | `updated_at` | DATETIME |  | GETDATE() | 更新時間（容器 GETDATE()，UTC） |

**索引／條件約束**

- PK `PK__dividend__3213E83F173E4139`：(id)
- UNIQUE `UQ_dividend_notices`：(code,ex_date)

### stock_alerts

處置／注意股。約 876 筆。

| # | 欄位 | 型別 | NULL | 預設 | 說明 |
|---:|---|---|:---:|---|---|
| 1 | `id` | INT |  |  | 自動編號主鍵 |
| 2 | `stock_id` | INT |  |  | 股票 ID（→ stocks.stock_id） |
| 3 | `alert_type` | NVARCHAR(10) |  |  | 處置 / 注意 |
| 4 | `announce_date` | DATE |  |  | 公告日 |
| 5 | `start_date` | DATE | Y |  | 處置起日 |
| 6 | `end_date` | DATE | Y |  | 處置迄日 |
| 7 | `reason` | NVARCHAR(1000) | Y |  | 原因 |
| 8 | `measure` | NVARCHAR(200) | Y |  | 處置措施 |
| 9 | `created_at` | DATETIME |  | GETDATE() | 建立時間（容器 GETDATE()，UTC） |

**索引／條件約束**

- PK `PK__stock_al__3213E83FD88B0BB2`：(id)
- UNIQUE `UQ_stock_alerts`：(stock_id,alert_type,announce_date)

## 六、ETF 持股

### etf_holdings

主動型 ETF 持股明細。約 65,534 筆。

| # | 欄位 | 型別 | NULL | 預設 | 說明 |
|---:|---|---|:---:|---|---|
| 1 | `id` | BIGINT |  |  | 自動編號主鍵 |
| 2 | `etf_id` | INT |  |  | ETF ID（→ etfs.etf_id） |
| 3 | `hold_date` | DATE |  |  | 持股日（回應的 TranDate） |
| 4 | `asset_type` | NVARCHAR(10) |  |  | 官方 AssetCode：ST 股票、GD 期貨 |
| 5 | `code` | NVARCHAR(20) |  |  | 持股代號（官方原文，如 2330、BE US、TX） |
| 6 | `month` | NVARCHAR(10) |  | '' | 期貨契約年月（2026/11），其他為空字串 |
| 7 | `name` | NVARCHAR(100) |  |  | 持股名稱 |
| 8 | `shares` | BIGINT |  |  | 股；期貨為口 |
| 9 | `amount` | DECIMAL(20,2) | Y |  | 市值或名目本金（原幣，見 currency） |
| 10 | `weight` | DECIMAL(7,2) | Y |  | 占淨資產 % |
| 11 | `currency` | NVARCHAR(5) |  |  | NTD、USD… |
| 12 | `created_at` | DATETIME |  | GETDATE() | 建立時間（容器 GETDATE()，UTC） |

**索引／條件約束**

- PK `PK__etf_hold__3213E83F4226108C`：(id)
- UNIQUE `UQ_etf_holdings`：(etf_id,hold_date,asset_type,code,month)
- INDEX `IX_etf_holdings_code`：(code,hold_date)

### etf_holding_summary

主動型 ETF 持股彙總。約 1,334 筆。

| # | 欄位 | 型別 | NULL | 預設 | 說明 |
|---:|---|---|:---:|---|---|
| 1 | `id` | INT |  |  | 自動編號主鍵 |
| 2 | `etf_id` | INT |  |  | ETF ID（→ etfs.etf_id） |
| 3 | `hold_date` | DATE |  |  | 持股日 |
| 4 | `post_date` | DATE |  |  | 清單生效日（請求參數） |
| 5 | `nav` | DECIMAL(20,2) |  |  | 基金淨資產（元） |
| 6 | `units` | BIGINT | Y |  | 已發行受益權單位 |
| 7 | `nav_unit` | DECIMAL(12,4) | Y |  | 每單位淨值（元） |
| 8 | `n_stocks` | INT |  |  | 股票檔數 |
| 9 | `stock_weight` | DECIMAL(7,2) | Y |  | 股票權重合計 % |
| 10 | `futures_lots` | INT |  |  | 期貨口數 |
| 11 | `futures_amount` | DECIMAL(20,2) |  |  | 期貨名目本金（元） |
| 12 | `edited_at` | DATETIME2(0) | Y |  | 投信更新時間（台灣時間） |
| 13 | `created_at` | DATETIME |  | GETDATE() | 建立時間（容器 GETDATE()，UTC） |

**索引／條件約束**

- PK `PK__etf_hold__3213E83FE963181D`：(id)
- UNIQUE `UQ_etf_holding_summary`：(etf_id,hold_date)

### etf_holding_gaps

ETF 確定沒有持股明細的日期。約 8 筆。

| # | 欄位 | 型別 | NULL | 預設 | 說明 |
|---:|---|---|:---:|---|---|
| 1 | `id` | INT |  |  | 自動編號主鍵 |
| 2 | `etf_id` | INT |  |  | ETF ID（→ etfs.etf_id） |
| 3 | `hold_date` | DATE |  |  | 持股日 |
| 4 | `reason` | CHAR(1) |  |  | A 當日無持股清單／B 只有彙總沒有明細 |
| 5 | `src_date` | DATE |  |  | 回應的持股日（A 為前一個海外交易日；B 等於 hold_date） |
| 6 | `post_date` | DATE |  |  | 清單生效日（請求參數） |
| 7 | `nav` | DECIMAL(20,2) | Y |  | B 的彙總淨資產（元） |
| 8 | `created_at` | DATETIME |  | GETDATE() | 建立時間（容器 GETDATE()，UTC） |

**索引／條件約束**

- PK `PK__etf_hold__3213E83FE38ADD4B`：(id)
- UNIQUE `UQ_etf_holding_gaps`：(etf_id,hold_date)

## 七、系統

### collect_runs

收集執行紀錄。約 25 筆。

| # | 欄位 | 型別 | NULL | 預設 | 說明 |
|---:|---|---|:---:|---|---|
| 1 | `run_id` | INT |  |  | 自動編號主鍵；執行序號 |
| 2 | `command` | NVARCHAR(20) |  |  | catch-up / date |
| 3 | `started_at` | DATETIME2(0) |  |  | 開始時間（台灣時間） |
| 4 | `finished_at` | DATETIME2(0) |  |  | 結束時間（台灣時間） |
| 5 | `outcome` | NVARCHAR(10) |  |  | 結果：ok／pending／abnormal |
| 6 | `new_data` | BIT |  |  | 這次有新資料寫入（「更新於」的依據） |
| 7 | `requests` | INT | Y |  | 這次對外請求次數 |
| 8 | `export_seconds` | DECIMAL(7,1) | Y |  | 這次完整匯出耗時；沒有匯出為 NULL |
| 9 | `detail` | NVARCHAR(MAX) |  |  | JSON：written / items / errors / undated |

**索引／條件約束**

- PK `PK__collect___7D3D901B7CAABF04`：(run_id)

## 八、非本專案管理

### futures_minute_prices

期貨分鐘行情（非本專案建立）。約 0 筆。

| # | 欄位 | 型別 | NULL | 預設 | 說明 |
|---:|---|---|:---:|---|---|
| 1 | `id` | BIGINT |  |  | 自動編號主鍵 |
| 2 | `symbol` | NVARCHAR(20) |  |  | 商品代號 |
| 3 | `trade_date` | DATE |  |  | 交易日 |
| 4 | `trade_time` | TIME |  |  | 分鐘時間 |
| 5 | `session` | NVARCHAR(5) |  | 'DAY' | DAY／NIGHT |
| 6 | `open_price` | DECIMAL(10,2) |  |  | 開盤價 |
| 7 | `high_price` | DECIMAL(10,2) |  |  | 最高價 |
| 8 | `low_price` | DECIMAL(10,2) |  |  | 最低價 |
| 9 | `close_price` | DECIMAL(10,2) |  |  | 收盤價 |
| 10 | `volume` | INT |  |  | 成交量 |
| 11 | `created_at` | DATETIME |  | GETDATE() | 建立時間（容器 GETDATE()，UTC） |

**索引／條件約束**

- PK `PK_futures_minute_prices`：(id)
- UNIQUE `UK_futures_minute_prices`：(symbol,trade_date,trade_time,session)
- INDEX `IX_fmp_symbol_date`：(symbol,trade_date,trade_time)

> 這張表不在 `twstock/db.py` 的 DDL 裡，專案程式也沒有讀寫它（0 筆），應是早期或其他工具建立。保留現狀，未經同意不刪除。
