"""
月營收（整批下載：每個市場每月 1 個請求，單位千元）。

最新月份：證交所 / 櫃買 OpenAPI（t187ap05）
歷史月份：mopsov 彙總 CSV t21sc03_{民國年}_{月}.csv（同一檔含國內與外國企業）
"""
import csv
import io
from datetime import date

from .. import db
from ..fetch import FetchError, clean_number, request

_OPENAPI = {
    "TWSE": "https://openapi.twse.com.tw/v1/opendata/t187ap05_L",
    "TPEx": "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap05_O",
}
_MOPSOV_MARKET = {"TWSE": "sii", "TPEx": "otc"}


def _pct(val):
    v = clean_number(val)
    return round(v, 2) if v is not None else None


def _record(r: dict) -> dict:
    return {
        "revenue":     clean_number(r.get("營業收入-當月營收"), int),
        "revenue_mom": _pct(r.get("營業收入-上月比較增減(%)")),
        "revenue_yoy": _pct(r.get("營業收入-去年同月增減(%)")),
    }


def fetch_monthly_revenue(market: str, year: int, month: int) -> dict:
    """{股票代號: {revenue, revenue_mom, revenue_yoy}}；尚未公布回傳 {}。"""
    roc = year - 1911
    rows = request("GET", _OPENAPI[market])
    if rows and rows[0].get("資料年月") == f"{roc}{month:02d}":
        return {r["公司代號"].strip(): _record(r) for r in rows}

    url = f"https://mopsov.twse.com.tw/nas/t21/{_MOPSOV_MARKET[market]}/t21sc03_{roc}_{month}.csv"
    raw = request("GET", url, expect_json=False).content
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp950", errors="replace")
    if not text.startswith("出表日期"):
        if "SECURITY" in text.upper():
            raise FetchError("mopsov 回傳安全性封鎖頁面")
        raise FetchError(f"mopsov 月營收 CSV 格式不符：{url}")
    return {r["公司代號"].strip(): _record(r)
            for r in csv.DictReader(io.StringIO(text)) if r.get("公司代號")}   # 未公布只有標題列


def revenue_month_for(d: date):
    """每月 10 日前各公司營收才公布完；10 日以後才收上個月的營收。"""
    if d.day < 10:
        return None
    return (d.year - 1, 12) if d.month == 1 else (d.year, d.month - 1)


def collect_monthly_revenue(year: int, month: int, force: bool = False) -> int:
    """
    寫入指定月份營收，只補資料庫還沒有的公司（ETF 不在 stocks 表，不會寫入）。
    force=True 時已有的資料也以最新抓到的數字覆寫。
    """
    conn = db.connect()
    cursor = conn.cursor()
    total = 0
    try:
        for market in ("TWSE", "TPEx"):
            cursor.execute("""
                SELECT s.stock_code,
                       CASE WHEN EXISTS (
                           SELECT 1 FROM monthly_revenue mr
                           WHERE mr.stock_id = s.stock_id
                             AND mr.revenue_year = ? AND mr.revenue_month = ?
                       ) THEN 1 ELSE 0 END
                FROM stocks s WHERE s.market_type = ?
            """, year, month, market)
            pending = {code for code, has_row in cursor.fetchall() if force or not has_row}
            if not pending:
                print(f"    ℹ️  {market} {year}/{month:02d} 營收已齊全，略過")
                continue

            revenue = fetch_monthly_revenue(market, year, month)
            rows = [{"stock_code": c, **r} for c, r in revenue.items()
                    if c in pending and r["revenue"] is not None]
            if rows:
                cursor.execute("""
                    MERGE monthly_revenue AS t
                    USING (
                        SELECT st.stock_id, j.*
                        FROM OPENJSON(?) WITH (
                            stock_code NVARCHAR(10), revenue BIGINT,
                            revenue_mom DECIMAL(10,2), revenue_yoy DECIMAL(10,2)
                        ) AS j
                        JOIN stocks st ON st.stock_code = j.stock_code
                    ) AS s
                    ON t.stock_id = s.stock_id AND t.revenue_year = ? AND t.revenue_month = ?
                    WHEN MATCHED THEN UPDATE SET
                        revenue = s.revenue, revenue_mom = s.revenue_mom, revenue_yoy = s.revenue_yoy
                    WHEN NOT MATCHED THEN
                        INSERT (stock_id, revenue_year, revenue_month, revenue, revenue_mom, revenue_yoy)
                        VALUES (s.stock_id, ?, ?, s.revenue, s.revenue_mom, s.revenue_yoy);
                """, db.to_json(rows), year, month, year, month)
                conn.commit()
            print(f"    📋 {market} {year}/{month:02d}：{'重抓' if force else '待補'} {len(pending)} 家，寫入 {len(rows)} 家")
            total += len(rows)
    finally:
        conn.close()
    return total
