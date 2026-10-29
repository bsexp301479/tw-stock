"""
每日資料：上市 + 上櫃的收盤行情、本益比/殖利率、三大法人買賣超。

寫入採批次：整批資料序列化成一個 JSON 參數，由 OPENJSON 展開後 MERGE；
每張表一次資料庫往返，取代逐筆查詢/更新的上萬次往返。
"""
from datetime import date

from .. import db
from ..fetch import FetchError, clean_number, is_valid_stock_code, request

TWSE = "https://www.twse.com.tw/rwd/zh"
TPEX = "https://www.tpex.org.tw/www/zh-tw"

PRICES, INSTI = "prices", "insti"     # collect_for_date 的資料集名稱
ALL_DATASETS = (PRICES, INSTI)


# ─── 上市 ─────────────────────────────────────────────────
def fetch_twse_daily(d: date) -> list:
    """上市每日收盤行情；休市回傳 []。"""
    data = request("GET", f"{TWSE}/afterTrading/MI_INDEX",
                   params={"response": "json", "date": f"{d:%Y%m%d}", "type": "ALLBUT0999"})
    if data.get("stat") != "OK":
        return []
    for table in data.get("tables", []):
        fields = table.get("fields", [])
        if "證券代號" not in fields:
            continue
        idx = {f: i for i, f in enumerate(fields)}
        results = []
        for row in table.get("data", []):
            code = str(row[idx["證券代號"]]).strip()
            if not is_valid_stock_code(code):
                continue
            # 漲跌價差是絕對值，正負號在「漲跌(+/-)」欄（HTML 片段，如 <p style= color:green>-</p>）
            change = clean_number(row[idx["漲跌價差"]])
            if change is not None and "-" in str(row[idx["漲跌(+/-)"]]):
                change = -change
            results.append({
                "stock_code": code, "stock_name": str(row[idx["證券名稱"]]).strip(),
                "open_price":  clean_number(row[idx["開盤價"]]),
                "high_price":  clean_number(row[idx["最高價"]]),
                "low_price":   clean_number(row[idx["最低價"]]),
                "close_price": clean_number(row[idx["收盤價"]]),
                "volume":      clean_number(row[idx["成交股數"]], int),
                "trade_value": clean_number(row[idx["成交金額"]], int),
                "trade_count": clean_number(row[idx["成交筆數"]], int),
                "change":      change,
            })
        return results
    return []


def fetch_twse_pe(d: date) -> dict:
    data = request("GET", f"{TWSE}/afterTrading/BWIBBU_d",
                   params={"response": "json", "date": f"{d:%Y%m%d}", "selectType": "ALL"})
    if data.get("stat") != "OK":
        return {}
    idx = {f: i for i, f in enumerate(data.get("fields", []))}
    return {
        str(row[idx["證券代號"]]).strip(): {
            "pe_ratio":       clean_number(row[idx["本益比"]]),
            "pb_ratio":       clean_number(row[idx["股價淨值比"]]),
            "dividend_yield": clean_number(row[idx["殖利率(%)"]]),
        }
        for row in data.get("data", [])
    }


def fetch_twse_insti(d: date) -> dict:
    """上市三大法人買賣超（股）。外資 = 外陸資（不含外資自營商）+ 外資自營商。"""
    data = request("GET", f"{TWSE}/fund/T86",
                   params={"response": "json", "date": f"{d:%Y%m%d}", "selectType": "ALLBUT0999"})
    if data.get("stat") != "OK":
        return {}
    idx = {f: i for i, f in enumerate(data["fields"])}
    num = lambda row, f: clean_number(row[idx[f]], int) or 0
    result = {}
    for row in data["data"]:
        code = str(row[idx["證券代號"]]).strip()
        if is_valid_stock_code(code):
            result[code] = {
                "foreign_net": num(row, "外陸資買賣超股數(不含外資自營商)") + num(row, "外資自營商買賣超股數"),
                "trust_net":   num(row, "投信買賣超股數"),
                "dealer_net":  num(row, "自營商買賣超股數"),
                "total_net":   num(row, "三大法人買賣超股數"),
            }
    return result


# ─── 上櫃 ─────────────────────────────────────────────────
def _tpex_tables(path: str, d: date) -> list:
    data = request("POST", f"{TPEX}/{path}", data={"date": f"{d:%Y/%m/%d}", "response": "json"})
    return [t for t in data.get("tables", []) if t.get("fields") and t.get("data")]


def fetch_tpex_daily(d: date) -> list:
    for table in _tpex_tables("afterTrading/dailyQuotes", d):
        idx = {f: i for i, f in enumerate(table["fields"])}
        if "代號" not in idx:
            continue
        return [{
            "stock_code": str(row[idx["代號"]]).strip(), "stock_name": str(row[idx["名稱"]]).strip(),
            "close_price": clean_number(row[idx["收盤"]]),
            "open_price":  clean_number(row[idx["開盤"]]),
            "high_price":  clean_number(row[idx["最高"]]),
            "low_price":   clean_number(row[idx["最低"]]),
            "change":      clean_number(row[idx["漲跌"]]),          # 上櫃的漲跌本身帶正負號
            "volume":      clean_number(row[idx["成交股數"]], int),
            "trade_value": clean_number(row[idx["成交金額(元)"]], int),
            "trade_count": clean_number(row[idx["成交筆數"]], int),
        } for row in table["data"] if is_valid_stock_code(str(row[idx["代號"]]))]
    return []


def fetch_tpex_pe(d: date) -> dict:
    for table in _tpex_tables("afterTrading/peQryDate", d):
        idx = {f: i for i, f in enumerate(table["fields"])}
        if "本益比" not in idx or "代號" not in idx:
            continue
        return {
            str(row[idx["代號"]]).strip(): {
                "pe_ratio":       clean_number(row[idx["本益比"]]),
                "dividend_yield": clean_number(row[idx["殖利率"]]),
                "pb_ratio":       clean_number(row[idx["股價淨值比"]]),
            }
            for row in table["data"] if is_valid_stock_code(str(row[idx["代號"]]))
        }
    return {}


def fetch_tpex_insti(d: date) -> dict:
    """
    上櫃三大法人買賣超（股）。欄位名稱重複，依位置取值：
    4 外資(不含外資自營商) / 7 外資自營商 / 10 外資合計 / 13 投信 /
    16 自營商自行買賣 / 19 自營商避險 / 22 自營商合計 / 23 三大法人合計
    """
    data = request("GET", f"{TPEX}/insti/dailyTrade",
                   params={"type": "Daily", "sect": "EW", "date": f"{d:%Y/%m/%d}", "response": "json"})
    tables = data.get("tables") or [{}]
    num = lambda row, i: clean_number(row[i], int) or 0
    return {
        row[0].strip(): {
            "foreign_net": num(row, 10), "trust_net": num(row, 13),
            "dealer_net": num(row, 22), "total_net": num(row, 23),
        }
        for row in tables[0].get("data", []) if is_valid_stock_code(row[0])
    }


# ─── 批次寫入 ─────────────────────────────────────────────
def merge_stocks(cursor, rows: list):
    """rows: [{stock_code, stock_name, market_type}]。新股票新增，既有股票更新名稱與市場別。"""
    cursor.execute("""
        MERGE stocks AS t
        USING OPENJSON(?) WITH (
            stock_code NVARCHAR(10), stock_name NVARCHAR(50), market_type NVARCHAR(10)
        ) AS s
        ON t.stock_code = s.stock_code
        WHEN MATCHED THEN
            UPDATE SET stock_name = s.stock_name, market_type = s.market_type, updated_at = GETDATE()
        WHEN NOT MATCHED THEN
            INSERT (stock_code, stock_name, market_type)
            VALUES (s.stock_code, s.stock_name, s.market_type);
    """, db.to_json(rows))


def merge_daily_prices(cursor, trade_date, rows: list):
    cursor.execute("""
        MERGE daily_prices AS t
        USING (
            SELECT st.stock_id, j.*
            FROM OPENJSON(?) WITH (
                stock_code  NVARCHAR(10),
                open_price  DECIMAL(10,2), high_price  DECIMAL(10,2),
                low_price   DECIMAL(10,2), close_price DECIMAL(10,2),
                volume      BIGINT,        trade_value BIGINT,
                trade_count INT,           change      DECIMAL(10,2)
            ) AS j
            JOIN stocks st ON st.stock_code = j.stock_code
        ) AS s
        ON t.stock_id = s.stock_id AND t.trade_date = ?
        WHEN MATCHED THEN UPDATE SET
            open_price = s.open_price, high_price = s.high_price,
            low_price  = s.low_price,  close_price = s.close_price,
            volume = s.volume, trade_value = s.trade_value,
            trade_count = s.trade_count, change = s.change
        WHEN NOT MATCHED THEN
            INSERT (stock_id, trade_date, open_price, high_price, low_price, close_price,
                    volume, trade_value, trade_count, change)
            VALUES (s.stock_id, ?, s.open_price, s.high_price, s.low_price, s.close_price,
                    s.volume, s.trade_value, s.trade_count, s.change);
    """, db.to_json(rows), trade_date, trade_date)


def merge_fundamentals(cursor, trade_date, rows: list):
    cursor.execute("""
        MERGE stock_fundamentals AS t
        USING (
            SELECT st.stock_id, j.*
            FROM OPENJSON(?) WITH (
                stock_code NVARCHAR(10),
                eps        DECIMAL(10,2), pe_ratio       DECIMAL(10,2),
                pb_ratio   DECIMAL(10,2), dividend_yield DECIMAL(10,4)
            ) AS j
            JOIN stocks st ON st.stock_code = j.stock_code
        ) AS s
        ON t.stock_id = s.stock_id AND t.trade_date = ?
        WHEN MATCHED THEN UPDATE SET
            eps = s.eps, pe_ratio = s.pe_ratio, pb_ratio = s.pb_ratio, dividend_yield = s.dividend_yield
        WHEN NOT MATCHED THEN
            INSERT (stock_id, trade_date, eps, pe_ratio, pb_ratio, dividend_yield)
            VALUES (s.stock_id, ?, s.eps, s.pe_ratio, s.pb_ratio, s.dividend_yield);
    """, db.to_json(rows), trade_date, trade_date)


def merge_institutional(cursor, trade_date, rows: list):
    """只寫入 stocks 表已有的股票（新股票由當天行情建立）。"""
    cursor.execute("""
        MERGE institutional_trades AS t
        USING (
            SELECT st.stock_id, j.*
            FROM OPENJSON(?) WITH (
                stock_code NVARCHAR(10),
                foreign_net BIGINT, trust_net BIGINT, dealer_net BIGINT, total_net BIGINT
            ) AS j
            JOIN stocks st ON st.stock_code = j.stock_code
        ) AS s
        ON t.stock_id = s.stock_id AND t.trade_date = ?
        WHEN MATCHED THEN UPDATE SET
            foreign_net = s.foreign_net, trust_net = s.trust_net,
            dealer_net = s.dealer_net, total_net = s.total_net
        WHEN NOT MATCHED THEN
            INSERT (stock_id, trade_date, foreign_net, trust_net, dealer_net, total_net)
            VALUES (s.stock_id, ?, s.foreign_net, s.trust_net, s.dealer_net, s.total_net);
    """, db.to_json(rows), trade_date, trade_date)


# ─── 單日收集 ─────────────────────────────────────────────
def collect_for_date(d: date, datasets=ALL_DATASETS) -> bool:
    """
    收集單日資料。回傳 True = 已寫入；False = 休市或尚未公布。
    抓取失敗丟 FetchError，且不寫入任何該日資料（全部抓完才連資料庫，一次 commit）。
    """
    print(f"\n📅 {d}  [{' + '.join(datasets)}]")
    stocks, prices, funds, insti = {}, {}, {}, {}
    counts = {}

    if PRICES in datasets:
        for market, fetch_q, fetch_pe in (("TWSE", fetch_twse_daily, fetch_twse_pe),
                                          ("TPEx", fetch_tpex_daily, fetch_tpex_pe)):
            rows = fetch_q(d)
            if market == "TWSE" and not rows:
                print("  ℹ️  上市無資料（休市或尚未公布），略過此日")
                return False
            pe_map = fetch_pe(d)
            for item in rows:
                code = item["stock_code"]
                stocks[code] = {"stock_code": code, "stock_name": item["stock_name"], "market_type": market}
                prices[code] = item
                if pe_map.get(code):
                    funds[code] = {"stock_code": code, **pe_map[code]}
            counts[market] = len(rows)

    if INSTI in datasets:
        for market, fetch in (("TWSE", fetch_twse_insti), ("TPEx", fetch_tpex_insti)):
            rows = fetch(d)
            if market == "TWSE" and not rows:
                print("  ℹ️  上市法人無資料（休市或尚未公布），略過此日")
                return False
            for code, r in rows.items():
                insti[code] = {"stock_code": code, **r}
            counts[f"法人{market}"] = len(rows)

    conn = db.connect()
    try:
        cursor = conn.cursor()
        if prices:
            merge_stocks(cursor, list(stocks.values()))
            merge_daily_prices(cursor, d, list(prices.values()))
            merge_fundamentals(cursor, d, list(funds.values()))
        if insti:
            merge_institutional(cursor, d, list(insti.values()))
        conn.commit()
    finally:
        conn.close()
    print("  ✅ 寫入：" + "、".join(f"{k} {v} 筆" for k, v in counts.items()))
    return True


__all__ = ["collect_for_date", "FetchError", "PRICES", "INSTI", "ALL_DATASETS"]
