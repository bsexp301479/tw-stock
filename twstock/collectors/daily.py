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
TPEX_OPENAPI = "https://www.tpex.org.tw/openapi/v1"

# collect_for_date 的資料集名稱；INDEX 只在補抓加權指數時單獨指定（抓 PRICES 時會一併寫入）；
# AMOUNT 只在補抓或 collect 單獨呼叫時指定
PRICES, INSTI, INDEX, AMOUNT = "prices", "insti", "index", "amount"
ALL_DATASETS = (PRICES, INSTI)


# ─── 上市 ─────────────────────────────────────────────────
def parse_taiex(data: dict, d: date):
    """MI_INDEX 回應中的發行量加權股價指數；找不到或欄位格式不符回傳 None（不可影響個股寫入）。"""
    need = ("指數", "收盤指數", "漲跌(+/-)", "漲跌點數")
    for table in data.get("tables", []):
        if "價格指數(臺灣證券交易所)" not in (table.get("title") or ""):
            continue
        idx = {f: i for i, f in enumerate(table.get("fields", []))}
        if not set(need) <= idx.keys():
            continue                                    # 欄位改名：視為找不到指數表
        for row in table.get("data", []):
            if len(row) <= max(idx[f] for f in need):
                continue                                # 列太短：略過
            if str(row[idx["指數"]]).strip() != "發行量加權股價指數":
                continue
            # 漲跌點數是絕對值，正負號在「漲跌(+/-)」欄（HTML 片段），與個股相同
            change = clean_number(row[idx["漲跌點數"]])
            if change is not None and "-" in str(row[idx["漲跌(+/-)"]]):
                change = -change
            close = clean_number(row[idx["收盤指數"]])
            return {"index_code": "TAIEX", "trade_date": d.isoformat(),
                    "close_price": close, "change": change} if close is not None else None
    return None


def fetch_twse_daily(d: date):
    """上市每日收盤行情與加權指數；休市回傳 ([], None)。"""
    data = request("GET", f"{TWSE}/afterTrading/MI_INDEX",
                   params={"response": "json", "date": f"{d:%Y%m%d}", "type": "ALLBUT0999"})
    if data.get("stat") != "OK":
        return [], None
    taiex = parse_taiex(data, d)
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
        return results, taiex
    return [], taiex


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


def fetch_tpex_index() -> list:
    """櫃買指數：OpenAPI 只提供本月每日開高低收（Date 為西元 YYYYMMDD）。"""
    data = request("GET", f"{TPEX_OPENAPI}/tpex_index")
    if not isinstance(data, list):
        raise FetchError("櫃買指數回應格式不符")
    rows = []
    for r in data:
        ds, close = str(r.get("Date") or ""), clean_number(r.get("Close"))
        if close is None or not (ds.isdigit() and len(ds) == 8):
            continue
        rows.append({"index_code": "TPEX", "trade_date": f"{ds[:4]}-{ds[4:6]}-{ds[6:]}",
                     "open_price": clean_number(r.get("Open")), "high_price": clean_number(r.get("High")),
                     "low_price": clean_number(r.get("Low")), "close_price": close,
                     "change": clean_number(r.get("Change"))})
    return rows


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


def merge_market_index(cursor, rows: list):
    cursor.execute("""
        MERGE market_index AS t
        USING OPENJSON(?) WITH (
            index_code NVARCHAR(10), trade_date DATE,
            open_price DECIMAL(10,2), high_price DECIMAL(10,2), low_price DECIMAL(10,2),
            close_price DECIMAL(10,2), change DECIMAL(10,2)
        ) AS s
        ON t.index_code = s.index_code AND t.trade_date = s.trade_date
        WHEN MATCHED THEN UPDATE SET
            open_price = s.open_price, high_price = s.high_price, low_price = s.low_price,
            close_price = s.close_price, change = s.change
        WHEN NOT MATCHED THEN
            INSERT (index_code, trade_date, open_price, high_price, low_price, close_price, change)
            VALUES (s.index_code, s.trade_date, s.open_price, s.high_price, s.low_price,
                    s.close_price, s.change);
    """, db.to_json(rows))


def _amount_unit(name: str):
    """BFI82U 單位名稱 → 代碼。「外資及陸資(不含外資自營商)」也含「外資自營商」字樣，判斷順序不可對調。"""
    if name.startswith("外資及陸資"):
        return "foreign"
    if name.startswith("外資自營商"):
        return "foreign_dealer"
    if name.startswith("自營商"):
        return "dealer_hedge" if "避險" in name else "dealer_self"
    if name.startswith("投信"):
        return "trust"
    if name.startswith("合計"):
        return "total"
    return None


def parse_insti_amount(data: dict, d: date) -> list:
    """BFI82U 回應 → [{trade_date, unit, buy_amount, sell_amount, net_amount}]（元）；休市或欄位不符回傳 []。"""
    if data.get("stat") != "OK":
        return []
    idx = {f: i for i, f in enumerate(data.get("fields", []))}
    need = ("單位名稱", "買進金額", "賣出金額", "買賣差額")
    if not set(need) <= idx.keys():
        return []
    rows = {}
    for row in data.get("data", []):
        if len(row) <= max(idx[f] for f in need):
            continue
        unit = _amount_unit(str(row[idx["單位名稱"]]).strip())
        if unit:
            rows[unit] = {"trade_date": d.isoformat(), "unit": unit,
                          "buy_amount": clean_number(row[idx["買進金額"]], int),
                          "sell_amount": clean_number(row[idx["賣出金額"]], int),
                          "net_amount": clean_number(row[idx["買賣差額"]], int)}
    return list(rows.values())


def fetch_twse_insti_amount(d: date) -> list:
    data = request("GET", f"{TWSE}/fund/BFI82U",
                   params={"response": "json", "type": "day", "dayDate": f"{d:%Y%m%d}"})
    return parse_insti_amount(data, d)


def merge_insti_amount(cursor, rows: list):
    cursor.execute("""
        MERGE insti_amount AS t
        USING OPENJSON(?) WITH (
            trade_date DATE, unit NVARCHAR(20), buy_amount BIGINT, sell_amount BIGINT, net_amount BIGINT
        ) AS s
        ON t.trade_date = s.trade_date AND t.unit = s.unit
        WHEN MATCHED THEN UPDATE SET
            buy_amount = s.buy_amount, sell_amount = s.sell_amount, net_amount = s.net_amount
        WHEN NOT MATCHED THEN
            INSERT (trade_date, unit, buy_amount, sell_amount, net_amount)
            VALUES (s.trade_date, s.unit, s.buy_amount, s.sell_amount, s.net_amount);
    """, db.to_json(rows))


def collect_tpex_index() -> int:
    """寫入本月全部日期（MERGE，可重複執行）。"""
    rows = fetch_tpex_index()
    if rows:
        conn = db.connect()
        try:
            merge_market_index(conn.cursor(), rows)
            conn.commit()
        finally:
            conn.close()
    print(f"  📈 櫃買指數：{len(rows)} 天")
    return len(rows)


# ─── 單日收集 ─────────────────────────────────────────────
def collect_for_date(d: date, datasets=ALL_DATASETS) -> bool:
    """
    收集單日資料。回傳 True = 已寫入；False = 休市或尚未公布。
    抓取失敗丟 FetchError，且不寫入任何該日資料（全部抓完才連資料庫，一次 commit）。
    """
    print(f"\n📅 {d}  [{' + '.join(datasets)}]")
    stocks, prices, funds, insti = {}, {}, {}, {}
    counts = {}
    taiex = None

    if PRICES in datasets:
        for market, fetch_q, fetch_pe in (("TWSE", fetch_twse_daily, fetch_twse_pe),
                                          ("TPEx", fetch_tpex_daily, fetch_tpex_pe)):
            rows = fetch_q(d)
            if market == "TWSE":
                rows, taiex = rows      # 上市行情與加權指數來自同一個 MI_INDEX 回應
                if rows and taiex is None:
                    print("  ⚠️  MI_INDEX 找不到加權指數表")
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
    elif INDEX in datasets:
        _, taiex = fetch_twse_daily(d)      # 只補指數：同一個請求，個股列不寫入
        if taiex is None:
            print("  ℹ️  無加權指數（休市或尚未公布），略過此日")
            return False
    if taiex:
        counts["加權指數"] = 1

    if INSTI in datasets:
        for market, fetch in (("TWSE", fetch_twse_insti), ("TPEx", fetch_tpex_insti)):
            rows = fetch(d)
            if market == "TWSE" and not rows:
                print("  ℹ️  上市法人無資料（休市或尚未公布），略過此日")
                return False
            for code, r in rows.items():
                insti[code] = {"stock_code": code, **r}
            counts[f"法人{market}"] = len(rows)

    amount = []
    if AMOUNT in datasets:
        amount = fetch_twse_insti_amount(d)
        if amount:
            counts["法人金額"] = len(amount)
        elif not (prices or insti or taiex):
            print("  ℹ️  無三大法人買賣金額（休市或尚未公布），略過此日")
            return False

    conn = db.connect()
    try:
        cursor = conn.cursor()
        if prices:
            merge_stocks(cursor, list(stocks.values()))
            merge_daily_prices(cursor, d, list(prices.values()))
            merge_fundamentals(cursor, d, list(funds.values()))
        if insti:
            merge_institutional(cursor, d, list(insti.values()))
        if taiex:
            merge_market_index(cursor, [taiex])
        if amount:
            merge_insti_amount(cursor, amount)
        conn.commit()
    finally:
        conn.close()
    print("  ✅ 寫入：" + "、".join(f"{k} {v} 筆" for k, v in counts.items()))
    return True


__all__ = ["collect_for_date", "FetchError", "PRICES", "INSTI", "ALL_DATASETS"]
