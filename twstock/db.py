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
          "institutional_trades、futures_daily_prices、futures_institutional、industry_chains")
