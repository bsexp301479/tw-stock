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
    """
    IF OBJECT_ID('futures_minute_prices') IS NULL
    CREATE TABLE futures_minute_prices (
        id          BIGINT IDENTITY(1,1) PRIMARY KEY,
        symbol      NVARCHAR(20)  NOT NULL,
        trade_date  DATE          NOT NULL,
        trade_time  TIME(0)       NOT NULL,
        session     NVARCHAR(5)   NOT NULL DEFAULT 'DAY',   -- DAY 日盤 / NIGHT 夜盤
        open_price  DECIMAL(10,2) NOT NULL,
        high_price  DECIMAL(10,2) NOT NULL,
        low_price   DECIMAL(10,2) NOT NULL,
        close_price DECIMAL(10,2) NOT NULL,
        volume      INT           NOT NULL,
        created_at  DATETIME      NOT NULL DEFAULT GETDATE(),
        CONSTRAINT UK_futures_minute_prices UNIQUE (symbol, trade_date, trade_time, session)
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
          "institutional_trades、futures_minute_prices")
