"""資料庫連線與資料表建立（SQL Server / Azure SQL Edge）。"""
import json
import math
from decimal import Decimal

import pyodbc

from .config import DB_CONFIG, connection_string


def connect(autocommit: bool = False) -> pyodbc.Connection:
    # Docker 容器剛啟動時第一次連線可能逾時，給長一點的 timeout
    return pyodbc.connect(connection_string(), autocommit=autocommit, timeout=30)


def to_json(rows: list) -> str:
    """
    把批次資料序列化成 OPENJSON 用的 JSON 參數：
    NaN/Infinity 不是合法 JSON → null；Decimal → float；
    整數值的 float（如 10900.0）→ int，否則 OPENJSON 轉 BIGINT 會失敗。
    """
    def clean(v):
        if isinstance(v, Decimal):
            v = float(v)
        if isinstance(v, float):
            if not math.isfinite(v):
                return None
            if v.is_integer():
                return int(v)
        return v
    return json.dumps([{k: clean(v) for k, v in r.items()} for r in rows], ensure_ascii=False)


def acquire_lock():
    """
    防重疊：SQL Server 應用程式鎖（跨平台，程序結束會自動釋放）。
    取得回傳持有鎖的連線，已被其他程序持有回傳 None。用完要呼叫 release_lock。
    """
    conn = connect(autocommit=True)
    got = conn.cursor().execute(
        "SET NOCOUNT ON; DECLARE @r INT; EXEC @r = sp_getapplock @Resource=N'twstock_collect', "
        "@LockMode=N'Exclusive', @LockOwner=N'Session', @LockTimeout=0; SELECT @r").fetchone()[0]
    if got < 0:
        conn.close()
        return None
    return conn


def release_lock(conn):
    # pyodbc 有連線池，close() 不會真的斷線，鎖要明確釋放
    conn.cursor().execute("EXEC sp_releaseapplock @Resource=N'twstock_collect', @LockOwner=N'Session'")
    conn.close()


# ─── 資料表 ───────────────────────────────────────────────
DDL = [
    """
    IF OBJECT_ID('stocks') IS NULL
    CREATE TABLE stocks (
        stock_id    INT IDENTITY(1,1) PRIMARY KEY,
        stock_code  NVARCHAR(10)  NOT NULL,
        stock_name  NVARCHAR(50)  NOT NULL,
        market_type NVARCHAR(10)  NOT NULL CHECK (market_type IN ('TWSE','TPEx')),
        industry    NVARCHAR(50)  NULL,
        listed_date DATE          NULL,
        created_at  DATETIME      NOT NULL DEFAULT GETDATE(),
        updated_at  DATETIME      NOT NULL DEFAULT GETDATE(),
        CONSTRAINT UQ_stock_code UNIQUE (stock_code)
    )
    """,
    """
    IF OBJECT_ID('daily_prices') IS NULL
    CREATE TABLE daily_prices (
        price_id    BIGINT IDENTITY(1,1) PRIMARY KEY,
        stock_id    INT            NOT NULL REFERENCES stocks(stock_id),
        trade_date  DATE           NOT NULL,
        open_price  DECIMAL(10,2)  NULL,
        high_price  DECIMAL(10,2)  NULL,
        low_price   DECIMAL(10,2)  NULL,
        close_price DECIMAL(10,2)  NULL,
        volume      BIGINT         NULL,
        trade_value BIGINT         NULL,
        trade_count INT            NULL,
        change      DECIMAL(10,2)  NULL,
        created_at  DATETIME       NOT NULL DEFAULT GETDATE(),
        CONSTRAINT UQ_daily_prices UNIQUE (stock_id, trade_date)
    )
    """,
    """
    IF OBJECT_ID('monthly_revenue') IS NULL
    CREATE TABLE monthly_revenue (
        rev_id        INT IDENTITY(1,1) PRIMARY KEY,
        stock_id      INT            NOT NULL REFERENCES stocks(stock_id),
        revenue_year  INT            NOT NULL,
        revenue_month INT            NOT NULL CHECK (revenue_month BETWEEN 1 AND 12),
        revenue       BIGINT         NULL,
        revenue_mom   DECIMAL(10,2)  NULL,
        revenue_yoy   DECIMAL(10,2)  NULL,
        created_at    DATETIME       NOT NULL DEFAULT GETDATE(),
        CONSTRAINT UQ_monthly_revenue UNIQUE (stock_id, revenue_year, revenue_month)
    )
    """,
    """
    IF OBJECT_ID('stock_fundamentals') IS NULL
    CREATE TABLE stock_fundamentals (
        fund_id        INT IDENTITY(1,1) PRIMARY KEY,
        stock_id       INT            NOT NULL REFERENCES stocks(stock_id),
        trade_date     DATE           NOT NULL,
        eps            DECIMAL(10,2)  NULL,
        pe_ratio       DECIMAL(10,2)  NULL,
        pb_ratio       DECIMAL(10,2)  NULL,
        dividend_yield DECIMAL(10,4)  NULL,
        created_at     DATETIME       NOT NULL DEFAULT GETDATE(),
        CONSTRAINT UQ_fundamentals UNIQUE (stock_id, trade_date)
    )
    """,
    # 三大法人買賣超（單位：股；正數 = 買超）
    """
    IF OBJECT_ID('institutional_trades') IS NULL
    CREATE TABLE institutional_trades (
        inst_id     BIGINT IDENTITY(1,1) PRIMARY KEY,
        stock_id    INT      NOT NULL REFERENCES stocks(stock_id),
        trade_date  DATE     NOT NULL,
        foreign_net BIGINT   NULL,   -- 外資及陸資（含外資自營商）
        trust_net   BIGINT   NULL,   -- 投信
        dealer_net  BIGINT   NULL,   -- 自營商（自行買賣 + 避險）
        total_net   BIGINT   NULL,   -- 三大法人合計
        created_at  DATETIME NOT NULL DEFAULT GETDATE(),
        CONSTRAINT UQ_institutional UNIQUE (stock_id, trade_date)
    )
    """,
    # 期貨每日行情（每個合約月份一列；夜盤的 trade_date 是成交量歸屬日，即隔天）
    """
    IF OBJECT_ID('futures_daily_prices') IS NULL
    CREATE TABLE futures_daily_prices (
        id             BIGINT IDENTITY(1,1) PRIMARY KEY,
        trade_date     DATE          NOT NULL,
        commodity_id   NVARCHAR(10)  NOT NULL,   -- TX 台指期、MTX 小台…
        contract_month CHAR(6)       NOT NULL,   -- 202611
        session        NVARCHAR(5)   NOT NULL,   -- DAY 日盤 / NIGHT 夜盤
        open_price     DECIMAL(10,2) NULL,
        high_price     DECIMAL(10,2) NULL,
        low_price      DECIMAL(10,2) NULL,
        close_price    DECIMAL(10,2) NULL,
        change         DECIMAL(10,2) NULL,
        volume         INT           NULL,
        settlement     DECIMAL(10,2) NULL,       -- 夜盤沒有
        open_interest  INT           NULL,       -- 未沖銷契約數，夜盤沒有
        created_at     DATETIME      NOT NULL DEFAULT GETDATE(),
        CONSTRAINT UQ_futures_daily UNIQUE (commodity_id, contract_month, session, trade_date)
    )
    """,
    # 期貨三大法人交易與未平倉（口數；金額單位千元）
    """
    IF OBJECT_ID('futures_institutional') IS NULL
    CREATE TABLE futures_institutional (
        id             BIGINT IDENTITY(1,1) PRIMARY KEY,
        trade_date     DATE          NOT NULL,
        commodity_id   NVARCHAR(10)  NOT NULL,   -- TXF 大台、MXF 小台、TMF 微台
        investor       NVARCHAR(10)  NOT NULL,   -- foreign 外資及陸資 / trust 投信 / dealer 自營商
        long_trade     INT           NULL,
        short_trade    INT           NULL,
        net_trade      INT           NULL,
        long_oi        INT           NULL,       -- 多方未平倉口數
        short_oi       INT           NULL,       -- 空方未平倉口數
        net_oi         INT           NULL,       -- 多空未平倉淨額
        net_oi_amount  BIGINT        NULL,       -- 多空未平倉契約金額淨額（千元）
        created_at     DATETIME      NOT NULL DEFAULT GETDATE(),
        CONSTRAINT UQ_futures_institutional UNIQUE (commodity_id, investor, trade_date)
    )
    """,
    # 產業鏈族群（櫃買中心產業價值鏈平台）；含興櫃，所以存代號而非 stocks 外鍵
    """
    IF OBJECT_ID('industry_chains') IS NULL
    CREATE TABLE industry_chains (
        id           INT IDENTITY(1,1) PRIMARY KEY,
        chain_id     NVARCHAR(10)  NOT NULL,
        chain_name   NVARCHAR(50)  NOT NULL,    -- 半導體
        segment_id   NVARCHAR(10)  NOT NULL,
        segment_name NVARCHAR(100) NOT NULL,    -- IC/晶圓製造
        sub_id       NVARCHAR(10)  NOT NULL,    -- 沒有細項時為空字串
        sub_name     NVARCHAR(100) NOT NULL,    -- 晶圓製造
        stock_code   NVARCHAR(10)  NOT NULL,
        updated_at   DATETIME      NOT NULL DEFAULT GETDATE(),
        CONSTRAINT UQ_industry_chains UNIQUE (chain_id, segment_id, sub_id, stock_code)
    )
    """,
    # 大盤指數每日收盤（TAIEX 取自 MI_INDEX，沒有開高低；TPEX 取自櫃買 OpenAPI）
    """
    IF OBJECT_ID('market_index') IS NULL
    CREATE TABLE market_index (
        id          INT IDENTITY(1,1) PRIMARY KEY,
        index_code  NVARCHAR(10)  NOT NULL,   -- TAIEX 加權指數 / TPEX 櫃買指數
        trade_date  DATE          NOT NULL,
        open_price  DECIMAL(10,2) NULL,
        high_price  DECIMAL(10,2) NULL,
        low_price   DECIMAL(10,2) NULL,
        close_price DECIMAL(10,2) NOT NULL,
        change      DECIMAL(10,2) NULL,
        created_at  DATETIME      NOT NULL DEFAULT GETDATE(),
        CONSTRAINT UQ_market_index UNIQUE (index_code, trade_date)
    )
    """,
    # 處置／注意股公告（保留歷史；注意股沒有起訖日）
    """
    IF OBJECT_ID('stock_alerts') IS NULL
    CREATE TABLE stock_alerts (
        id            INT IDENTITY(1,1) PRIMARY KEY,
        stock_id      INT            NOT NULL REFERENCES stocks(stock_id),
        alert_type    NVARCHAR(10)   NOT NULL CHECK (alert_type IN ('disposal','notice')),  -- 處置 / 注意
        announce_date DATE           NOT NULL,
        start_date    DATE           NULL,
        end_date      DATE           NULL,
        reason        NVARCHAR(1000) NULL,
        measure       NVARCHAR(200)  NULL,
        created_at    DATETIME       NOT NULL DEFAULT GETDATE(),
        CONSTRAINT UQ_stock_alerts UNIQUE (stock_id, alert_type, announce_date)
    )
    """,
    # 價格調整事件（官方）：除權息、減資、面額變更。上櫃的減資類事件在匯出時由日線反推，不存表
    """
    IF OBJECT_ID('price_events') IS NULL
    CREATE TABLE price_events (
        id          INT IDENTITY(1,1) PRIMARY KEY,
        stock_id    INT           NOT NULL REFERENCES stocks(stock_id),
        event_date  DATE          NOT NULL,   -- 官方日期（除權息日／恢復買賣日），可能是休市日
        event_type  NVARCHAR(4)   NOT NULL CHECK (event_type IN (N'息', N'權', N'權息', N'減', N'面')),
        prev_close  DECIMAL(10,2) NOT NULL,   -- 除權息前收盤價／停止買賣前收盤價格
        ref_price   DECIMAL(10,2) NOT NULL,   -- 除權息參考價／恢復買賣參考價
        source      NVARCHAR(10)  NOT NULL,   -- TWT49U / TWTAUU / TWTB8U / TPEX_EX
        created_at  DATETIME      NOT NULL DEFAULT GETDATE(),
        CONSTRAINT UQ_price_events UNIQUE (stock_id, event_date, source)
    )
    """,
    # 三大法人買賣金額（單位：元；含 ETF 等全部證券）：上市證交所 BFI82U、上櫃櫃買 insti/summary（第 9 輪加 market）
    """
    IF OBJECT_ID('insti_amount') IS NULL
    CREATE TABLE insti_amount (
        id          INT IDENTITY(1,1) PRIMARY KEY,
        trade_date  DATE          NOT NULL,
        market      NVARCHAR(10)  NOT NULL CONSTRAINT DF_insti_amount_market DEFAULT 'TWSE'
                                  CONSTRAINT CK_insti_amount_market CHECK (market IN ('TWSE','TPEx')),
        unit        NVARCHAR(20)  NOT NULL,   -- foreign 外資及陸資(不含外資自營商) / foreign_dealer 外資自營商 /
                                              -- dealer_self 自營商(自行買賣) / dealer_hedge 自營商(避險) / trust 投信 / total 合計
        buy_amount  BIGINT        NULL,
        sell_amount BIGINT        NULL,
        net_amount  BIGINT        NULL,
        created_at  DATETIME      NOT NULL DEFAULT GETDATE(),
        CONSTRAINT UQ_insti_amount_market UNIQUE (trade_date, market, unit)
    )
    """,
    # 第 9 輪遷移（既有資料庫）：加 market（既有列 = TWSE）→ 刪舊唯一鍵 → 建新唯一鍵；每一步都先判斷，可重複執行
    "IF COL_LENGTH('insti_amount', 'market') IS NULL "
    "ALTER TABLE insti_amount ADD market NVARCHAR(10) NOT NULL CONSTRAINT DF_insti_amount_market DEFAULT 'TWSE' "
    "CONSTRAINT CK_insti_amount_market CHECK (market IN ('TWSE','TPEx'))",
    "IF EXISTS (SELECT 1 FROM sys.key_constraints WHERE name = 'UQ_insti_amount' AND parent_object_id = OBJECT_ID('insti_amount')) "
    "ALTER TABLE insti_amount DROP CONSTRAINT UQ_insti_amount",
    "IF NOT EXISTS (SELECT 1 FROM sys.key_constraints WHERE name = 'UQ_insti_amount_market' AND parent_object_id = OBJECT_ID('insti_amount')) "
    "ALTER TABLE insti_amount ADD CONSTRAINT UQ_insti_amount_market UNIQUE (trade_date, market, unit)",
    # 收集執行紀錄（時間為台灣時間，由 Python 傳入；容器的 GETDATE() 是 UTC，不可使用）
    """
    IF OBJECT_ID('collect_runs') IS NULL
    CREATE TABLE collect_runs (
        run_id         INT IDENTITY(1,1) PRIMARY KEY,
        command        NVARCHAR(20)  NOT NULL,   -- catch-up / date
        started_at     DATETIME2(0)  NOT NULL,
        finished_at    DATETIME2(0)  NOT NULL,
        outcome        NVARCHAR(10)  NOT NULL CHECK (outcome IN ('ok','pending','abnormal')),
        new_data       BIT           NOT NULL,   -- 這次有新資料寫入（「更新於」的依據）
        requests       INT           NULL,       -- 這次對外請求次數
        export_seconds DECIMAL(7,1)  NULL,       -- 這次完整匯出耗時；沒有匯出為 NULL
        detail         NVARCHAR(MAX) NOT NULL    -- JSON：written / items / errors / undated
    )
    """,
    # 休市日：official 官方休市表（每年整批更新）；adhoc 收集時判定的臨時休市（颱風假）
    """
    IF OBJECT_ID('market_holidays') IS NULL
    CREATE TABLE market_holidays (
        holiday_date DATE          NOT NULL PRIMARY KEY,
        name         NVARCHAR(100) NOT NULL,
        source       NVARCHAR(10)  NOT NULL CHECK (source IN ('official','adhoc')),
        fetched_at   DATETIME2(0)  NOT NULL      -- 台灣時間
    )
    """,
    # ETF（第 4 輪）：與 stocks 分開，所有個股統計都不會讀到
    """
    IF OBJECT_ID('etfs') IS NULL
    CREATE TABLE etfs (
        etf_id      INT IDENTITY(1,1) PRIMARY KEY,
        etf_code    NVARCHAR(10)  NOT NULL,
        etf_name    NVARCHAR(50)  NOT NULL,
        market_type NVARCHAR(10)  NOT NULL CHECK (market_type IN ('TWSE','TPEx')),
        created_at  DATETIME      NOT NULL DEFAULT GETDATE(),
        updated_at  DATETIME      NOT NULL DEFAULT GETDATE(),
        CONSTRAINT UQ_etf_code UNIQUE (etf_code)
    )
    """,
    """
    IF OBJECT_ID('etf_daily') IS NULL
    CREATE TABLE etf_daily (
        id          BIGINT IDENTITY(1,1) PRIMARY KEY,
        etf_id      INT            NOT NULL REFERENCES etfs(etf_id),
        trade_date  DATE           NOT NULL,
        open_price  DECIMAL(10,2)  NULL,
        high_price  DECIMAL(10,2)  NULL,
        low_price   DECIMAL(10,2)  NULL,
        close_price DECIMAL(10,2)  NULL,
        volume      BIGINT         NULL,     -- 股
        trade_value BIGINT         NULL,     -- 元
        trade_count INT            NULL,
        change      DECIMAL(10,2)  NULL,
        created_at  DATETIME       NOT NULL DEFAULT GETDATE(),
        CONSTRAINT UQ_etf_daily UNIQUE (etf_id, trade_date)
    )
    """,
    # 融資融券（第 4 輪；張）：股票 margin_trades、ETF etf_margin 欄位相同；官方合計（含 ETF）margin_market
    """
    IF OBJECT_ID('margin_trades') IS NULL
    CREATE TABLE margin_trades (
        id             BIGINT IDENTITY(1,1) PRIMARY KEY,
        stock_id       INT           NOT NULL REFERENCES stocks(stock_id),
        trade_date     DATE          NOT NULL,
        margin_buy     INT           NULL,    -- 融資買進
        margin_sell    INT           NULL,    -- 融資賣出
        margin_redeem  INT           NULL,    -- 現金償還
        margin_prev    INT           NOT NULL,-- 融資前日餘額
        margin_balance INT           NOT NULL,-- 融資今日餘額
        margin_limit   INT           NULL,    -- 融資限額（上市：次一營業日限額）
        short_sell     INT           NULL,    -- 融券賣出
        short_buy      INT           NULL,    -- 融券買進（回補）
        short_redeem   INT           NULL,    -- 現券償還
        short_prev     INT           NOT NULL,
        short_balance  INT           NOT NULL,
        short_limit    INT           NULL,
        offset_lots    INT           NULL,    -- 資券互抵（offset 是保留字）
        note           NVARCHAR(20)  NULL,    -- 上市註記／上櫃備註原文
        created_at     DATETIME      NOT NULL DEFAULT GETDATE(),
        CONSTRAINT UQ_margin_trades UNIQUE (stock_id, trade_date)
    )
    """,
    """
    IF OBJECT_ID('etf_margin') IS NULL
    CREATE TABLE etf_margin (
        id             BIGINT IDENTITY(1,1) PRIMARY KEY,
        etf_id         INT           NOT NULL REFERENCES etfs(etf_id),
        trade_date     DATE          NOT NULL,
        margin_buy     INT           NULL,
        margin_sell    INT           NULL,
        margin_redeem  INT           NULL,
        margin_prev    INT           NOT NULL,
        margin_balance INT           NOT NULL,
        margin_limit   INT           NULL,
        short_sell     INT           NULL,
        short_buy      INT           NULL,
        short_redeem   INT           NULL,
        short_prev     INT           NOT NULL,
        short_balance  INT           NOT NULL,
        short_limit    INT           NULL,
        offset_lots    INT           NULL,
        note           NVARCHAR(20)  NULL,
        created_at     DATETIME      NOT NULL DEFAULT GETDATE(),
        CONSTRAINT UQ_etf_margin UNIQUE (etf_id, trade_date)
    )
    """,
    """
    IF OBJECT_ID('margin_market') IS NULL
    CREATE TABLE margin_market (
        id             INT IDENTITY(1,1) PRIMARY KEY,
        trade_date     DATE          NOT NULL,
        market         NVARCHAR(10)  NOT NULL CHECK (market IN ('TWSE','TPEx')),
        margin_prev    BIGINT        NOT NULL,   -- 官方融資前日餘額（張，含 ETF 與其他證券）
        margin_balance BIGINT        NOT NULL,
        short_prev     BIGINT        NOT NULL,   -- 官方融券（張）
        short_balance  BIGINT        NOT NULL,
        amount_prev    BIGINT        NOT NULL,   -- 官方融資金額（仟元）
        amount_balance BIGINT        NOT NULL,
        created_at     DATETIME      NOT NULL DEFAULT GETDATE(),
        CONSTRAINT UQ_margin_market UNIQUE (trade_date, market)
    )
    """,
    # 主動型 ETF 持股（第 5 輪；統一投信 GetPCF）：以持股日為準，代號保留官方原文（海外股票 'BE US'、期貨 'TX'）
    """
    IF OBJECT_ID('etf_holdings') IS NULL
    CREATE TABLE etf_holdings (
        id          BIGINT IDENTITY(1,1) PRIMARY KEY,
        etf_id      INT            NOT NULL REFERENCES etfs(etf_id),
        hold_date   DATE           NOT NULL,     -- 持股日（回應的 TranDate）
        asset_type  NVARCHAR(10)   NOT NULL,     -- 官方 AssetCode：ST 股票、GD 期貨
        code        NVARCHAR(20)   NOT NULL,
        month       NVARCHAR(10)   NOT NULL DEFAULT '',  -- 期貨契約年月（2026/11），其他為空字串
        name        NVARCHAR(100)  NOT NULL,
        shares      BIGINT         NOT NULL,     -- 股；期貨為口
        amount      DECIMAL(20,2)  NULL,         -- 市值或名目本金（原幣，見 currency）
        weight      DECIMAL(7,2)   NULL,         -- 占淨資產 %
        currency    NVARCHAR(5)    NOT NULL,     -- NTD、USD…
        created_at  DATETIME       NOT NULL DEFAULT GETDATE(),
        CONSTRAINT UQ_etf_holdings UNIQUE (etf_id, hold_date, asset_type, code, month)
    )
    """,
    """
    IF OBJECT_ID('etf_holding_summary') IS NULL
    CREATE TABLE etf_holding_summary (
        id             INT IDENTITY(1,1) PRIMARY KEY,
        etf_id         INT            NOT NULL REFERENCES etfs(etf_id),
        hold_date      DATE           NOT NULL,
        post_date      DATE           NOT NULL,  -- 清單生效日（請求參數）
        nav            DECIMAL(20,2)  NOT NULL,  -- 基金淨資產（元）
        units          BIGINT         NULL,      -- 已發行受益權單位
        nav_unit       DECIMAL(12,4)  NULL,      -- 每單位淨值（元）
        n_stocks       INT            NOT NULL,
        stock_weight   DECIMAL(7,2)   NULL,      -- 股票權重合計 %
        futures_lots   INT            NOT NULL,
        futures_amount DECIMAL(20,2)  NOT NULL,  -- 期貨名目本金（元）
        edited_at      DATETIME2(0)   NULL,      -- 投信更新時間（台灣時間）
        created_at     DATETIME       NOT NULL DEFAULT GETDATE(),
        CONSTRAINT UQ_etf_holding_summary UNIQUE (etf_id, hold_date)
    )
    """,
    # 官方漲跌家數（第 5 輪；股票）：上市 MI_INDEX「漲跌證券數合計」、上櫃 afterTrading/highlight
    """
    IF OBJECT_ID('market_breadth') IS NULL
    CREATE TABLE market_breadth (
        id          INT IDENTITY(1,1) PRIMARY KEY,
        trade_date  DATE          NOT NULL,
        market      NVARCHAR(10)  NOT NULL CHECK (market IN ('TWSE','TPEx')),
        up          INT           NOT NULL,
        up_limit    INT           NULL,
        down        INT           NOT NULL,
        down_limit  INT           NULL,
        flat        INT           NOT NULL,
        no_trade    INT           NULL,      -- 未成交（上櫃含暫停交易）
        created_at  DATETIME      NOT NULL DEFAULT GETDATE(),
        CONSTRAINT UQ_market_breadth UNIQUE (trade_date, market)
    )
    """,
    # 投信確定沒有持股明細的持股日（第 6 輪）：A 當日無持股清單（海外休市等）、B 只有彙總沒有明細（臺股臨時休市前一日）
    """
    IF OBJECT_ID('etf_holding_gaps') IS NULL
    CREATE TABLE etf_holding_gaps (
        id          INT IDENTITY(1,1) PRIMARY KEY,
        etf_id      INT            NOT NULL REFERENCES etfs(etf_id),
        hold_date   DATE           NOT NULL,
        reason      CHAR(1)        NOT NULL CHECK (reason IN ('A','B')),
        src_date    DATE           NOT NULL,  -- 回應的持股日（A 為前一個海外交易日；B 等於 hold_date）
        post_date   DATE           NOT NULL,  -- 清單生效日（請求參數）
        nav         DECIMAL(20,2)  NULL,      -- B 的彙總淨資產（元）
        created_at  DATETIME       NOT NULL DEFAULT GETDATE(),
        CONSTRAINT UQ_etf_holding_gaps UNIQUE (etf_id, hold_date)
    )
    """,
    # 季報（第 10 輪 B5）：mopsov 綜合損益表彙總的「年初至今累計」（千元、元），單季在匯出時相減；
    # industry_tbl = 解析自哪一張表（ci 一般業、fh 金控、basi 銀行、bd 證券、ins 保險、mim 其他）；
    # first_seen = 日常收集第一次收到的日期（補抓寫入為 NULL，更新時不動）
    """
    IF OBJECT_ID('quarterly_financials') IS NULL
    CREATE TABLE quarterly_financials (
        id            INT IDENTITY(1,1) PRIMARY KEY,
        stock_id      INT            NOT NULL REFERENCES stocks(stock_id),
        fin_year      INT            NOT NULL,
        fin_quarter   TINYINT        NOT NULL CHECK (fin_quarter BETWEEN 1 AND 4),
        industry_tbl  NVARCHAR(10)   NOT NULL CHECK (industry_tbl IN ('ci','fh','basi','bd','ins','mim')),
        revenue       BIGINT         NULL,
        gross_profit  BIGINT         NULL,
        op_income     BIGINT         NULL,
        net_income    BIGINT         NULL,
        eps           DECIMAL(10,2)  NULL,
        first_seen    DATE           NULL,
        created_at    DATETIME       NOT NULL DEFAULT GETDATE(),
        updated_at    DATETIME       NOT NULL DEFAULT GETDATE(),
        CONSTRAINT UQ_quarterly_financials UNIQUE (stock_id, fin_year, fin_quarter)
    )
    """,
    # 索引
    "IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_daily_prices_date') "
    "CREATE INDEX IX_daily_prices_date ON daily_prices(trade_date)",
    "IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_daily_prices_stock') "
    "CREATE INDEX IX_daily_prices_stock ON daily_prices(stock_id, trade_date DESC)",
    "IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_monthly_rev_stock') "
    "CREATE INDEX IX_monthly_rev_stock ON monthly_revenue(stock_id, revenue_year DESC, revenue_month DESC)",
    "IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_institutional_date') "
    "CREATE INDEX IX_institutional_date ON institutional_trades(trade_date)",
    "IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_industry_chains_code') "
    "CREATE INDEX IX_industry_chains_code ON industry_chains(stock_code)",
    "IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_margin_trades_date') "
    "CREATE INDEX IX_margin_trades_date ON margin_trades(trade_date)",
    "IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_etf_daily_date') "
    "CREATE INDEX IX_etf_daily_date ON etf_daily(trade_date)",
    "IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_etf_holdings_code') "
    "CREATE INDEX IX_etf_holdings_code ON etf_holdings(code, hold_date)",
]


def setup_database():
    """建立資料庫（若不存在）與所有資料表；重複執行安全。"""
    name = DB_CONFIG["database"]
    conn = pyodbc.connect(connection_string("master"), autocommit=True, timeout=30)
    conn.cursor().execute(f"IF DB_ID(N'{name}') IS NULL CREATE DATABASE [{name}]")
    conn.close()
    print(f"✅ 資料庫 [{name}] 已確認存在")

    conn = connect()
    cursor = conn.cursor()
    for ddl in DDL:
        cursor.execute(ddl)
    conn.commit()
    conn.close()
    print("✅ 資料表已確認：stocks、daily_prices、monthly_revenue、stock_fundamentals、"
          "institutional_trades、futures_daily_prices、futures_institutional、industry_chains、"
          "market_index、stock_alerts、price_events、insti_amount、collect_runs、market_holidays、"
          "etfs、etf_daily、margin_trades、etf_margin、margin_market、etf_holdings、etf_holding_summary、market_breadth、quarterly_financials、"
          "etf_holding_gaps")
