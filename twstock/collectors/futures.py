"""
期貨每日行情（期交所「每日行情下載」CSV）→ futures_daily_prices。

一次請求最多一個月；同一交易日分「一般」（日盤）與「盤後」（夜盤）兩列。
盤後的交易日期是成交量歸屬日：標示 10/29 的夜盤 = 10/28 15:00 ~ 10/29 05:00。
"""
import calendar
import csv
import io
from datetime import date, datetime, timedelta

from .. import db
from ..fetch import FetchError, clean_number, request

URL = "https://www.taifex.com.tw/cht/3/futDataDown"
HEADER = "交易日期"
SESSION = {"一般": "DAY", "盤後": "NIGHT"}


def fetch_futures_daily(start: date, end: date, commodity: str = "TX") -> list:
    resp = request("POST", URL, expect_json=False, data={
        "down_type": "1", "commodity_id": commodity, "commodity_id2": "",
        "queryStartDate": f"{start:%Y/%m/%d}", "queryEndDate": f"{end:%Y/%m/%d}",
    })
    text = resp.content.decode("cp950", errors="replace")
    if not text.lstrip().startswith(HEADER):
        raise FetchError("期交所回傳的不是行情 CSV（可能被限流或查詢區間錯誤）")

    rows = []
    for r in csv.reader(io.StringIO(text)):
        r = [x.strip() for x in r]
        if len(r) < 18 or r[0] == HEADER:
            continue
        month = r[2]
        if not (month.isdigit() and len(month) == 6):
            continue    # 跳過週選（202611W1）與價差單（202611/202612）
        rows.append({
            "trade_date": datetime.strptime(r[0], "%Y/%m/%d").date().isoformat(),
            "commodity_id": r[1], "contract_month": month, "session": SESSION.get(r[17], r[17]),
            "open_price": clean_number(r[3]), "high_price": clean_number(r[4]),
            "low_price": clean_number(r[5]), "close_price": clean_number(r[6]),
            "change": clean_number(r[7]), "volume": clean_number(r[9], int),
            "settlement": clean_number(r[10]), "open_interest": clean_number(r[11], int),
        })
    return rows


def merge_futures(cursor, rows: list):
    cursor.execute("""
        MERGE futures_daily_prices AS t
        USING OPENJSON(?) WITH (
            trade_date DATE, commodity_id NVARCHAR(10), contract_month CHAR(6), session NVARCHAR(5),
            open_price DECIMAL(10,2), high_price DECIMAL(10,2), low_price DECIMAL(10,2),
            close_price DECIMAL(10,2), change DECIMAL(10,2), volume INT,
            settlement DECIMAL(10,2), open_interest INT
        ) AS s
        ON t.commodity_id = s.commodity_id AND t.contract_month = s.contract_month
           AND t.session = s.session AND t.trade_date = s.trade_date
        WHEN MATCHED THEN UPDATE SET
            open_price = s.open_price, high_price = s.high_price, low_price = s.low_price,
            close_price = s.close_price, change = s.change, volume = s.volume,
            settlement = s.settlement, open_interest = s.open_interest
        WHEN NOT MATCHED THEN
            INSERT (trade_date, commodity_id, contract_month, session, open_price, high_price,
                    low_price, close_price, change, volume, settlement, open_interest)
            VALUES (s.trade_date, s.commodity_id, s.contract_month, s.session, s.open_price, s.high_price,
                    s.low_price, s.close_price, s.change, s.volume, s.settlement, s.open_interest);
    """, db.to_json(rows))


def collect_futures(start: date, end: date = None, commodity: str = "TX") -> int:
    """依月份切段下載（期交所限制一次最多一個月）。"""
    end = end or start
    total = 0
    conn = db.connect()
    try:
        cursor = conn.cursor()
        d = start
        while d <= end:
            seg_end = min(end, d.replace(day=calendar.monthrange(d.year, d.month)[1]))
            rows = fetch_futures_daily(d, seg_end, commodity)
            if rows:
                merge_futures(cursor, rows)
                conn.commit()
            days = len({r["trade_date"] for r in rows})
            print(f"  📈 {commodity} {d:%Y/%m/%d}~{seg_end:%m/%d}：{days} 個交易日、{len(rows)} 筆")
            total += len(rows)
            d = seg_end + timedelta(days=1)
    finally:
        conn.close()
    return total


# ─── 期貨三大法人（交易口數與未平倉）────────────────────────
INSTI_URL = "https://www.taifex.com.tw/cht/3/futContractsDateDown"
INSTI_HEADER = "日期"
INVESTOR = {"自營商": "dealer", "投信": "trust", "外資及陸資": "foreign"}
INSTI_COMMODITIES = ("TXF", "MXF", "TMF")    # 大台、小台、微台；約當大台 = TXF + MXF/4 + TMF/20
INSTI_MONTHS_PER_REQUEST = 3
INSTI_LISTED = {"TMF": date(2024, 7, 29)}    # 上市前的區間期交所回傳錯誤頁，不能查


def fetch_futures_institutional(start: date, end: date, commodity: str = "TXF") -> list:
    resp = request("POST", INSTI_URL, expect_json=False, data={
        "queryStartDate": f"{start:%Y/%m/%d}", "queryEndDate": f"{end:%Y/%m/%d}", "commodityId": commodity,
    })
    text = resp.content.decode("cp950", errors="replace")
    if not text.lstrip().startswith(INSTI_HEADER):
        raise FetchError("期交所回傳的不是三大法人 CSV（可能被限流或查詢區間錯誤）")
    rows = []
    for r in csv.reader(io.StringIO(text)):
        r = [x.strip() for x in r]
        if len(r) < 15 or r[0] == INSTI_HEADER or r[2] not in INVESTOR:
            continue
        n = lambda i: clean_number(r[i], int)
        rows.append({
            "trade_date": datetime.strptime(r[0], "%Y/%m/%d").date().isoformat(),
            "commodity_id": commodity, "investor": INVESTOR[r[2]],
            "long_trade": n(3), "short_trade": n(5), "net_trade": n(7),
            "long_oi": n(9), "short_oi": n(11), "net_oi": n(13), "net_oi_amount": n(14),
        })
    return rows


def merge_futures_institutional(cursor, rows: list):
    cursor.execute("""
        MERGE futures_institutional AS t
        USING OPENJSON(?) WITH (
            trade_date DATE, commodity_id NVARCHAR(10), investor NVARCHAR(10),
            long_trade INT, short_trade INT, net_trade INT,
            long_oi INT, short_oi INT, net_oi INT, net_oi_amount BIGINT
        ) AS s
        ON t.commodity_id = s.commodity_id AND t.investor = s.investor AND t.trade_date = s.trade_date
        WHEN MATCHED THEN UPDATE SET
            long_trade = s.long_trade, short_trade = s.short_trade, net_trade = s.net_trade,
            long_oi = s.long_oi, short_oi = s.short_oi, net_oi = s.net_oi, net_oi_amount = s.net_oi_amount
        WHEN NOT MATCHED THEN
            INSERT (trade_date, commodity_id, investor, long_trade, short_trade, net_trade,
                    long_oi, short_oi, net_oi, net_oi_amount)
            VALUES (s.trade_date, s.commodity_id, s.investor, s.long_trade, s.short_trade, s.net_trade,
                    s.long_oi, s.short_oi, s.net_oi, s.net_oi_amount);
    """, db.to_json(rows))


def collect_futures_institutional(start: date, end: date = None) -> int:
    """大台、小台、微台的三大法人未平倉；每次請求最多抓三個月。期交所只提供近 3 年。"""
    end = end or start
    total = 0
    conn = db.connect()
    try:
        cursor = conn.cursor()
        d = start
        while d <= end:
            m = d.month - 1 + INSTI_MONTHS_PER_REQUEST
            seg_end = min(end, date(d.year + m // 12, m % 12 + 1, 1) - timedelta(days=1))
            for commodity in INSTI_COMMODITIES:
                if seg_end < INSTI_LISTED.get(commodity, d):
                    continue
                rows = fetch_futures_institutional(max(d, INSTI_LISTED.get(commodity, d)), seg_end, commodity)
                if rows:
                    merge_futures_institutional(cursor, rows)
                    conn.commit()
                total += len(rows)
                print(f"  🏦 {commodity} 法人 {d:%Y/%m/%d}~{seg_end:%m/%d}：{len({r['trade_date'] for r in rows})} 天")
            d = seg_end + timedelta(days=1)
    finally:
        conn.close()
    return total
