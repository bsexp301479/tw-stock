"""
每日資料：上市 + 上櫃的收盤行情、本益比/殖利率、三大法人買賣超、ETF 行情、融資融券、官方漲跌家數、主動 ETF 持股。

寫入採批次：整批資料序列化成一個 JSON 參數，由 OPENJSON 展開後 MERGE；
每張表一次資料庫往返，取代逐筆查詢/更新的上萬次往返。
"""
import json
from datetime import date

from .. import db
from ..fetch import FetchError, SchemaError, clean_number, is_etf_code, is_valid_stock_code, request
from ..health import HOLDINGS
from ..tradingcal import load_closed
from .holdings import fetch_holdings, merge_holdings

TWSE = "https://www.twse.com.tw/rwd/zh"
TPEX = "https://www.tpex.org.tw/www/zh-tw"

# history --only 的資料集名稱；INDEX = 加權指數（抓行情時會一併寫入），TPEX_INDEX = 櫃買指數（月查詢）
PRICES, PE, INSTI, INDEX, AMOUNT, TPEX_INDEX = "prices", "pe", "insti", "index", "amount", "tpex_index"
ETF, MARGIN, HOLDINGS_DS = "etf", "margin", "holdings"
ALL_DATASETS = (PRICES, PE, INSTI, ETF, MARGIN)
HOLDINGS_KEYS = tuple(f"holdings.{c}" for c in HOLDINGS)
# 每個資料集對應的細項（分市場），也是 collect_for_date 與 health.SPECS 共用的鍵
DATASET_KEYS = {PRICES: ("prices.TWSE", "prices.TPEx"), PE: ("pe.TWSE", "pe.TPEx"),
                INSTI: ("insti.TWSE", "insti.TPEx"), INDEX: ("index.TAIEX",), AMOUNT: ("amount",),
                ETF: ("etf.TWSE", "etf.TPEx"), MARGIN: ("margin.TWSE", "margin.TPEx"), HOLDINGS_DS: HOLDINGS_KEYS}
# 一天之內的收集順序：行情先於本益比、法人；ETF 行情先於融資融券與持股（兩者都只寫入 etfs 已有的 ETF）
# 漲跌家數不補歷史（health.BREADTH_FROM），所以不在 DATASET_KEYS；上市家數與行情共用同一個 MI_INDEX 回應
DAY_KEYS = ("prices.TWSE", "prices.TPEx", "index.TAIEX", "etf.TWSE", "etf.TPEx", "pe.TWSE", "pe.TPEx",
            "insti.TWSE", "insti.TPEx", "amount", "margin.TWSE", "margin.TPEx", "breadth.TWSE", "breadth.TPEx") + HOLDINGS_KEYS
PARSE_ERRORS = (SchemaError, KeyError, IndexError, TypeError, ValueError, AttributeError)


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


def _twse_quote(row: list, idx: dict) -> dict:
    """MI_INDEX 行情表的一列（股票與 ETF 共用）。"""
    # 漲跌價差是絕對值，正負號在「漲跌(+/-)」欄（HTML 片段，如 <p style= color:green>-</p>）
    change = clean_number(row[idx["漲跌價差"]])
    if change is not None and "-" in str(row[idx["漲跌(+/-)"]]):
        change = -change
    return {
        "stock_code": str(row[idx["證券代號"]]).strip(), "stock_name": str(row[idx["證券名稱"]]).strip(),
        "open_price":  clean_number(row[idx["開盤價"]]),
        "high_price":  clean_number(row[idx["最高價"]]),
        "low_price":   clean_number(row[idx["最低價"]]),
        "close_price": clean_number(row[idx["收盤價"]]),
        "volume":      clean_number(row[idx["成交股數"]], int),
        "trade_value": clean_number(row[idx["成交金額"]], int),
        "trade_count": clean_number(row[idx["成交筆數"]], int),
        "change":      change,
    }


def _mi_index(d: date) -> dict:
    return request("GET", f"{TWSE}/afterTrading/MI_INDEX",
                   params={"response": "json", "date": f"{d:%Y%m%d}", "type": "ALLBUT0999"})


def fetch_twse_daily(d: date, data=None):
    """
    上市每日收盤行情、加權指數、ETF 原始列 → (股票列, 指數, (欄位索引, ETF 原始列))；休市回傳 ([], None, ({}, []))。
    data：已取得的 MI_INDEX 回應（與漲跌家數共用），None 時才發請求。
    """
    data = _mi_index(d) if data is None else data
    if data.get("stat") != "OK":
        return [], None, ({}, [])
    taiex = parse_taiex(data, d)
    for table in data.get("tables", []):
        fields = table.get("fields", [])
        if "證券代號" not in fields:
            continue
        idx = {f: i for i, f in enumerate(fields)}
        code = lambda row: str(row[idx["證券代號"]]).strip()
        rows = table.get("data", [])
        results = [_twse_quote(r, idx) for r in rows if is_valid_stock_code(code(r))]
        return results, taiex, (idx, [r for r in rows if is_etf_code(code(r))])
    raise SchemaError("MI_INDEX 找不到含「證券代號」的個股表")


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


def _count(text) -> tuple:
    """'1,000(33)' → (1000, 33)；沒有括號 → (數字, None)。"""
    head, _, tail = str(text).partition("(")
    return clean_number(head, int), clean_number(tail.rstrip(")"), int) if tail else None


def parse_twse_breadth(data: dict, d: date):
    """MI_INDEX 的「漲跌證券數合計」股票欄 → 一列；休市回傳 None；有行情卻沒有這張表 → SchemaError。"""
    if data.get("stat") != "OK":
        return None
    for table in data.get("tables", []):
        if (table.get("title") or "").strip() != "漲跌證券數合計":
            continue
        fields = table.get("fields", [])
        if "股票" not in fields or "類型" not in fields:
            raise SchemaError("漲跌證券數合計 缺少「類型」或「股票」欄")
        rows = {str(r[fields.index("類型")]).strip(): r[fields.index("股票")] for r in table.get("data", [])}
        (up, up_limit), (down, down_limit) = _count(rows["上漲(漲停)"]), _count(rows["下跌(跌停)"])
        return {"trade_date": d.isoformat(), "market": "TWSE", "up": up, "up_limit": up_limit, "down": down,
                "down_limit": down_limit, "flat": _count(rows["持平"])[0], "no_trade": _count(rows["未成交"])[0]}
    raise SchemaError("MI_INDEX 找不到「漲跌證券數合計」表")


# ─── 上櫃 ─────────────────────────────────────────────────
def _tpex_tables(path: str, d: date) -> list:
    data = request("POST", f"{TPEX}/{path}", data={"date": f"{d:%Y/%m/%d}", "response": "json"})
    return [t for t in data.get("tables", []) if t.get("fields") and t.get("data")]


def _tpex_quote(row: list, idx: dict) -> dict:
    """dailyQuotes 行情表的一列（股票與 ETF 共用）。"""
    return {
        "stock_code": str(row[idx["代號"]]).strip(), "stock_name": str(row[idx["名稱"]]).strip(),
        "close_price": clean_number(row[idx["收盤"]]),
        "open_price":  clean_number(row[idx["開盤"]]),
        "high_price":  clean_number(row[idx["最高"]]),
        "low_price":   clean_number(row[idx["最低"]]),
        "change":      clean_number(row[idx["漲跌"]]),          # 上櫃的漲跌本身帶正負號
        "volume":      clean_number(row[idx["成交股數"]], int),
        "trade_value": clean_number(row[idx["成交金額(元)"]], int),
        "trade_count": clean_number(row[idx["成交筆數"]], int),
    }


def fetch_tpex_daily(d: date) -> tuple:
    """上櫃每日行情 → (股票列, None, (欄位索引, ETF 原始列))；與 fetch_twse_daily 同形。"""
    tables = _tpex_tables("afterTrading/dailyQuotes", d)
    for table in tables:
        idx = {f: i for i, f in enumerate(table["fields"])}
        if "代號" not in idx:
            continue
        code = lambda row: str(row[idx["代號"]]).strip()
        return ([_tpex_quote(r, idx) for r in table["data"] if is_valid_stock_code(code(r))], None,
                (idx, [r for r in table["data"] if is_etf_code(code(r))]))
    if tables:
        raise SchemaError("dailyQuotes 找不到含「代號」的行情表")
    return [], None, ({}, [])


def parse_tpex_breadth(tables: list, d: date):
    """afterTrading/highlight 的「上櫃股票當日彙總資訊」→ 一列；未公布（沒有資料表）回傳 None。"""
    if not tables:
        return None
    idx = {f: i for i, f in enumerate(tables[0]["fields"])}
    row = tables[0]["data"][0]
    get = lambda f: clean_number(row[idx[f]], int)
    return {"trade_date": d.isoformat(), "market": "TPEx", "up": get("上漲家數"), "up_limit": get("漲停家數"),
            "down": get("下跌家數"), "down_limit": get("跌停家數"), "flat": get("平盤家數"),
            "no_trade": get("未成交(含暫停交易)家數")}


def fetch_tpex_breadth(d: date):
    return parse_tpex_breadth(_tpex_tables("afterTrading/highlight", d), d)


def parse_etf_quotes(raw: tuple, market: str) -> list:
    """(欄位索引, ETF 原始列) → 寫入用 dict（鍵與股票行情相同）。股票列存在卻沒有任何 ETF 列 → SchemaError。"""
    idx, rows = raw
    if not rows:
        raise SchemaError(f"{market} 行情回應沒有任何 ETF 列")
    quote = _twse_quote if market == "TWSE" else _tpex_quote
    return [quote(r, idx) for r in rows]


def parse_tpex_index(tables: list) -> list:
    """櫃買指數月查詢（日期為西元 2026/10/30，漲跌本身帶正負號）→ 寫入用 dict。"""
    need = ("日期", "開市", "最高", "最低", "收市", "漲/跌")
    for table in tables:
        idx = {f: i for i, f in enumerate(table["fields"])}
        if not set(need) <= idx.keys():
            continue
        rows = []
        for r in table["data"]:
            close = clean_number(r[idx["收市"]])
            if close is not None:
                rows.append({"index_code": "TPEX", "trade_date": str(r[idx["日期"]]).strip().replace("/", "-"),
                             "open_price": clean_number(r[idx["開市"]]), "high_price": clean_number(r[idx["最高"]]),
                             "low_price": clean_number(r[idx["最低"]]), "close_price": close,
                             "change": clean_number(r[idx["漲/跌"]])})
        return rows
    if tables:
        raise SchemaError("indexInfo/inx 欄位不符：" + "、".join(map(str, tables[0]["fields"])))
    return []


def fetch_tpex_index(year: int, month: int) -> list:
    """櫃買指數：可查歷史，一次一個月（尚未有資料的月份回傳 []）。"""
    return parse_tpex_index(_tpex_tables("indexInfo/inx", date(year, month, 1)))


def parse_tpex_pe(tables: list) -> dict:
    """櫃買本益比表 → {代號: {pe_ratio, pb_ratio, dividend_yield}}。有資料但欄位不符丟 SchemaError；空表回傳 {}。"""
    need = ("股票代號", "本益比", "殖利率(%)", "股價淨值比")
    for table in tables:
        idx = {f: i for i, f in enumerate(table["fields"])}
        if not set(need) <= idx.keys():
            continue
        return {
            str(row[idx["股票代號"]]).strip(): {
                "pe_ratio":       clean_number(row[idx["本益比"]]),
                "dividend_yield": clean_number(row[idx["殖利率(%)"]]),
                "pb_ratio":       clean_number(row[idx["股價淨值比"]]),
            }
            for row in table["data"] if is_valid_stock_code(str(row[idx["股票代號"]]))
        }
    if tables:
        raise SchemaError("peQryDate 欄位不符：" + "、".join(map(str, tables[0]["fields"])))
    return {}


def fetch_tpex_pe(d: date) -> dict:
    return parse_tpex_pe(_tpex_tables("afterTrading/peQryDate", d))


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


# ─── 融資融券（上市 MI_MARGN、上櫃 margin/balance；張；股票、ETF、其他證券同一個回應）──
TWSE_MARGIN_GROUPS = [("股票", 2), ("融資", 6), ("融券", 6)]
# 上市明細表欄名重複，依位置取值；位置 → 欄名（用來驗證沒有改版）
TWSE_MARGIN_POS = {0: "代號", 2: "買進", 3: "賣出", 4: "現金償還", 5: "前日餘額", 6: "今日餘額", 7: "次一營業日限額",
                   8: "買進", 9: "賣出", 10: "現券償還", 11: "前日餘額", 12: "今日餘額", 13: "次一營業日限額",
                   14: "資券互抵", 15: "註記"}
MARGIN_COLS = ("margin_buy", "margin_sell", "margin_redeem", "margin_prev", "margin_balance", "margin_limit",
               "short_sell", "short_buy", "short_redeem", "short_prev", "short_balance", "short_limit", "offset_lots")
TPEX_MARGIN_COLS = dict(zip(MARGIN_COLS, ("資買", "資賣", "現償", "前資餘額(張)", "資餘額", "資限額",
                                          "券賣", "券買", "券償", "前券餘額(張)", "券餘額", "券限額", "資券相抵(張)")))
TWSE_MARGIN_IDX = dict(zip(MARGIN_COLS, (2, 3, 4, 5, 6, 7, 9, 8, 10, 11, 12, 13, 14)))   # 融券：9 賣出、8 買進


def _margin_row(code: str, get, note) -> dict:
    """get(欄) → 原始字串；前日餘額或今日餘額無法解析的列回傳 None（略過）。"""
    row = {"stock_code": code, **{c: clean_number(get(c), int) for c in MARGIN_COLS},
           "note": str(note or "").strip()[:20] or None}
    if None in (row["margin_prev"], row["margin_balance"], row["short_prev"], row["short_balance"]):
        return None
    return row


def _margin_total(mp, mb, sp, sb, ap, ab) -> dict:
    vals = [clean_number(v, int) for v in (mp, mb, sp, sb, ap, ab)]
    if None in vals:
        raise SchemaError("融資融券官方合計有空值：" + "、".join(map(str, (mp, mb, sp, sb, ap, ab))))
    return dict(zip(("margin_prev", "margin_balance", "short_prev", "short_balance", "amount_prev", "amount_balance"), vals))


def parse_twse_margin(data: dict) -> tuple:
    """
    MI_MARGN（selectType=ALL）→ (列, 官方合計)。列含股票、ETF、其他證券，由呼叫端分流；
    官方合計 = 信用交易統計（含 ETF）：融資、融券（張）、融資金額（仟元）的前日與今日餘額。
    stat 不是 OK 或明細沒有列 → ([], None)（官方尚無資料）；明細欄位、groups 或統計表不符 → SchemaError。
    """
    if data.get("stat") != "OK":
        return [], None
    tables = data.get("tables") or []
    detail = next((t for t in tables if (t.get("fields") or [None])[0] == "代號"), None)
    if detail is None:
        if any(t.get("data") for t in tables):
            raise SchemaError("MI_MARGN 找不到「代號」開頭的明細表")
        return [], None
    if not detail.get("data"):
        return [], None
    fields = detail["fields"]
    groups = [(g.get("title"), g.get("span")) for g in detail.get("groups") or []][:3]
    bad = [f"{i}:{name}" for i, name in TWSE_MARGIN_POS.items() if i >= len(fields) or fields[i] != name]
    if groups != TWSE_MARGIN_GROUPS or bad:
        raise SchemaError(f"MI_MARGN 欄位不符：groups {groups}，位置 {'、'.join(bad) or '正常'}")
    rows = []
    for r in detail["data"]:
        if len(r) < 16:
            continue
        row = _margin_row(str(r[0]).strip(), lambda c: r[TWSE_MARGIN_IDX[c]], r[15])
        if row:
            rows.append(row)
    total_t = next((t for t in tables if (t.get("fields") or [None])[0] == "項目"), None)
    if total_t is None or not {"前日餘額", "今日餘額"} <= set(total_t["fields"]):
        raise SchemaError("MI_MARGN 找不到信用交易統計")
    i, j = total_t["fields"].index("前日餘額"), total_t["fields"].index("今日餘額")
    by = {}
    for r in total_t.get("data") or []:
        label = str(r[0])
        key = "amount" if label.startswith("融資金額") else "margin" if label.startswith("融資(") else \
            "short" if label.startswith("融券(") else None
        if key and len(r) > max(i, j):
            by[key] = (r[i], r[j])
    if set(by) != {"margin", "short", "amount"}:
        raise SchemaError("MI_MARGN 信用交易統計列不符：" + "、".join(str(r[0]) for r in total_t.get("data") or []))
    return rows, _margin_total(*by["margin"], *by["short"], *by["amount"])


def parse_tpex_margin(data: dict) -> tuple:
    """
    櫃買 margin/balance → (列, 官方合計)。欄名不重複，依名稱取值；官方合計在 summary（實測是陣列，
    舊格式可能是字串化陣列，兩種都接受），與 fields 同欄位對齊：「合計(張)」列、「融資金(仟元)」列。
    沒有資料列 → ([], None)；欄位或 summary 不符 → SchemaError。
    """
    tables = [t for t in data.get("tables") or [] if t.get("data")]
    if not tables:
        return [], None
    t = tables[0]
    idx = {f: i for i, f in enumerate(t.get("fields") or [])}
    need = ("代號", "備註", *TPEX_MARGIN_COLS.values())
    miss = [f for f in need if f not in idx]
    if miss:
        raise SchemaError("margin/balance 欄位不符，缺：" + "、".join(miss))
    rows = []
    for r in t["data"]:
        if len(r) < len(idx):
            continue
        row = _margin_row(str(r[idx["代號"]]).strip(), lambda c: r[idx[TPEX_MARGIN_COLS[c]]], r[idx["備註"]])
        if row:
            rows.append(row)
    summary = t.get("summary") or []
    if isinstance(summary, str):
        summary = json.loads(summary)
    lots = next((s for s in summary if any("合計" in str(x) for x in s)), None)
    amount = next((s for s in summary if any("融資金" in str(x) for x in s)), None)
    if lots is None or amount is None or min(len(lots), len(amount)) < len(idx):
        raise SchemaError(f"margin/balance summary 不符：{str(summary)[:200]}")
    mp, mb, sp, sb = (idx[f] for f in ("前資餘額(張)", "資餘額", "前券餘額(張)", "券餘額"))
    return rows, _margin_total(lots[mp], lots[mb], lots[sp], lots[sb], amount[mp], amount[mb])


def fetch_twse_margin(d: date) -> tuple:
    return parse_twse_margin(request("GET", f"{TWSE}/marginTrading/MI_MARGN",
                                     params={"response": "json", "date": f"{d:%Y%m%d}", "selectType": "ALL"}))


def fetch_tpex_margin(d: date) -> tuple:
    return parse_tpex_margin(request("POST", f"{TPEX}/margin/balance", data={"date": f"{d:%Y/%m/%d}", "response": "json"}))


# ─── 批次寫入 ─────────────────────────────────────────────
def merge_stocks(cursor, rows: list, trade_date: date):
    """
    rows: [{stock_code, stock_name, market_type}]。新股票新增；既有股票的名稱與市場別
    只在 trade_date ≥ 資料庫最新日線日期時更新（補抓舊日期不可蓋掉最新值）。
    """
    latest = cursor.execute("SELECT MAX(trade_date) FROM daily_prices").fetchone()[0]
    cursor.execute("""
        MERGE stocks AS t
        USING OPENJSON(?) WITH (
            stock_code NVARCHAR(10), stock_name NVARCHAR(50), market_type NVARCHAR(10)
        ) AS s
        ON t.stock_code = s.stock_code
        WHEN MATCHED AND ? = 1 THEN
            UPDATE SET stock_name = s.stock_name, market_type = s.market_type, updated_at = GETDATE()
        WHEN NOT MATCHED THEN
            INSERT (stock_code, stock_name, market_type)
            VALUES (s.stock_code, s.stock_name, s.market_type);
    """, db.to_json(rows), 1 if latest is None or trade_date >= latest else 0)


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
    """只寫入當天有行情列的股票（與拆分前相同），所以要先寫行情。"""
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
            JOIN daily_prices dp ON dp.stock_id = st.stock_id AND dp.trade_date = ?
        ) AS s
        ON t.stock_id = s.stock_id AND t.trade_date = ?
        WHEN MATCHED THEN UPDATE SET
            eps = s.eps, pe_ratio = s.pe_ratio, pb_ratio = s.pb_ratio, dividend_yield = s.dividend_yield
        WHEN NOT MATCHED THEN
            INSERT (stock_id, trade_date, eps, pe_ratio, pb_ratio, dividend_yield)
            VALUES (s.stock_id, ?, s.eps, s.pe_ratio, s.pb_ratio, s.dividend_yield);
    """, db.to_json(rows), trade_date, trade_date, trade_date)


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


def merge_etfs(cursor, rows: list, market: str, trade_date: date):
    """ETF 清單（與 stocks 分開）。名稱、市場別只在 trade_date ≥ ETF 日線最新日期時更新（同 merge_stocks）。"""
    cursor.execute("""
        DECLARE @latest DATE = (SELECT MAX(trade_date) FROM etf_daily);
        MERGE etfs AS t
        USING OPENJSON(?) WITH (stock_code NVARCHAR(10), stock_name NVARCHAR(50)) AS s
        ON t.etf_code = s.stock_code
        WHEN MATCHED AND (@latest IS NULL OR ? >= @latest) THEN
            UPDATE SET etf_name = s.stock_name, market_type = ?, updated_at = GETDATE()
        WHEN NOT MATCHED THEN
            INSERT (etf_code, etf_name, market_type) VALUES (s.stock_code, s.stock_name, ?);
    """, db.to_json([{"stock_code": r["stock_code"], "stock_name": r["stock_name"]} for r in rows]),
        trade_date, market, market)


def merge_etf_daily(cursor, trade_date, rows: list):
    cursor.execute("""
        MERGE etf_daily AS t
        USING (
            SELECT e.etf_id, j.*
            FROM OPENJSON(?) WITH (
                stock_code  NVARCHAR(10),
                open_price  DECIMAL(10,2), high_price  DECIMAL(10,2),
                low_price   DECIMAL(10,2), close_price DECIMAL(10,2),
                volume      BIGINT,        trade_value BIGINT,
                trade_count INT,           change      DECIMAL(10,2)
            ) AS j
            JOIN etfs e ON e.etf_code = j.stock_code
        ) AS s
        ON t.etf_id = s.etf_id AND t.trade_date = ?
        WHEN MATCHED THEN UPDATE SET
            open_price = s.open_price, high_price = s.high_price,
            low_price  = s.low_price,  close_price = s.close_price,
            volume = s.volume, trade_value = s.trade_value,
            trade_count = s.trade_count, change = s.change
        WHEN NOT MATCHED THEN
            INSERT (etf_id, trade_date, open_price, high_price, low_price, close_price,
                    volume, trade_value, trade_count, change)
            VALUES (s.etf_id, ?, s.open_price, s.high_price, s.low_price, s.close_price,
                    s.volume, s.trade_value, s.trade_count, s.change);
    """, db.to_json(rows), trade_date, trade_date)


# 融資融券個股表：股票寫 margin_trades（只寫 stocks 已有的），ETF 寫 etf_margin（只寫 etfs 已有的）
_MARGIN_TABLE = {"stock": ("margin_trades", "stocks", "stock_id", "stock_code"),
                 "etf": ("etf_margin", "etfs", "etf_id", "etf_code")}


def merge_margin(cursor, trade_date, rows: list, kind: str):
    table, ref, key, code = _MARGIN_TABLE[kind]
    cols = ", ".join(MARGIN_COLS)
    cursor.execute(f"""
        MERGE {table} AS t
        USING (
            SELECT r.{key}, j.*
            FROM OPENJSON(?) WITH (
                stock_code NVARCHAR(10),
                margin_buy INT, margin_sell INT, margin_redeem INT, margin_prev INT, margin_balance INT, margin_limit INT,
                short_sell INT, short_buy INT, short_redeem INT, short_prev INT, short_balance INT, short_limit INT,
                offset_lots INT, note NVARCHAR(20)
            ) AS j
            JOIN {ref} r ON r.{code} = j.stock_code
        ) AS s
        ON t.{key} = s.{key} AND t.trade_date = ?
        WHEN MATCHED THEN UPDATE SET
            {", ".join(f"{c} = s.{c}" for c in MARGIN_COLS)}, note = s.note
        WHEN NOT MATCHED THEN
            INSERT ({key}, trade_date, {cols}, note)
            VALUES (s.{key}, ?, {", ".join(f"s.{c}" for c in MARGIN_COLS)}, s.note);
    """, db.to_json(rows), trade_date, trade_date)


def merge_margin_market(cursor, trade_date, market: str, total: dict):
    cursor.execute("""
        MERGE margin_market AS t
        USING OPENJSON(?) WITH (
            trade_date DATE, market NVARCHAR(10),
            margin_prev BIGINT, margin_balance BIGINT, short_prev BIGINT, short_balance BIGINT,
            amount_prev BIGINT, amount_balance BIGINT
        ) AS s
        ON t.trade_date = s.trade_date AND t.market = s.market
        WHEN MATCHED THEN UPDATE SET
            margin_prev = s.margin_prev, margin_balance = s.margin_balance, short_prev = s.short_prev,
            short_balance = s.short_balance, amount_prev = s.amount_prev, amount_balance = s.amount_balance
        WHEN NOT MATCHED THEN
            INSERT (trade_date, market, margin_prev, margin_balance, short_prev, short_balance, amount_prev, amount_balance)
            VALUES (s.trade_date, s.market, s.margin_prev, s.margin_balance, s.short_prev, s.short_balance,
                    s.amount_prev, s.amount_balance);
    """, db.to_json([{"trade_date": str(trade_date), "market": market, **total}]))


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


def merge_breadth(cursor, row: dict):
    cursor.execute("""
        MERGE market_breadth AS t
        USING OPENJSON(?) WITH (
            trade_date DATE, market NVARCHAR(10), up INT, up_limit INT, down INT, down_limit INT, flat INT, no_trade INT
        ) AS s
        ON t.trade_date = s.trade_date AND t.market = s.market
        WHEN MATCHED THEN UPDATE SET
            up = s.up, up_limit = s.up_limit, down = s.down, down_limit = s.down_limit, flat = s.flat, no_trade = s.no_trade
        WHEN NOT MATCHED THEN
            INSERT (trade_date, market, up, up_limit, down, down_limit, flat, no_trade)
            VALUES (s.trade_date, s.market, s.up, s.up_limit, s.down, s.down_limit, s.flat, s.no_trade);
    """, db.to_json([row]))


def _save(fn, *args):
    conn = db.connect()
    try:
        result = fn(conn.cursor(), *args)
        conn.commit()
        return result
    finally:
        conn.close()


def collect_tpex_index(year: int, month: int) -> int:
    """寫入該月全部日期（MERGE，可重複執行）。"""
    rows = fetch_tpex_index(year, month)
    if rows:
        _save(merge_market_index, rows)
    print(f"  📈 櫃買指數 {year}/{month:02d}：{len(rows)} 天")
    return len(rows)


# ─── 單日收集 ─────────────────────────────────────────────
def _quotes(market: str, d: date, cache: dict) -> tuple:
    """同一市場的行情回應只抓一次：股票行情、加權指數、ETF 共用；失敗也快取，同一次執行不重打。"""
    if market not in cache:
        try:
            if market == "TWSE":
                cache["MI_INDEX"] = _mi_index(d)                # 漲跌家數也從這個回應解析
                cache[market] = fetch_twse_daily(d, cache["MI_INDEX"])
            else:
                cache[market] = fetch_tpex_daily(d)
        except (FetchError, *PARSE_ERRORS) as e:
            cache[market] = e
    if isinstance(cache[market], Exception):
        raise cache[market]
    return cache[market]


def _collect_key(key: str, d: date, cache: dict) -> int:
    """抓取並寫入一個資料集，回傳筆數（0 = 官方尚無資料）。"""
    dataset, _, market = key.partition(".")
    if dataset in (PRICES, INDEX, ETF):
        rows, taiex, etf_raw = _quotes("TPEx" if market == "TPEx" else "TWSE", d, cache)
    if dataset == ETF:
        if not rows:
            return 0                                # 行情未公布
        etfs = parse_etf_quotes(etf_raw, market)    # 有股票列卻沒有 ETF 列 → SchemaError，只影響 etf.*
        _save(lambda cur: (merge_etfs(cur, etfs, market, d), merge_etf_daily(cur, d, etfs)))
        return len(etfs)
    if key == "prices.TWSE" or key == "index.TAIEX":
        if taiex:
            _save(merge_market_index, [taiex])
        elif rows:
            print("  ⚠️  MI_INDEX 找不到加權指數表")
        if key == "index.TAIEX":
            return 1 if taiex else 0
    if dataset == "prices":
        if rows:
            stocks = [{"stock_code": r["stock_code"], "stock_name": r["stock_name"], "market_type": market} for r in rows]
            _save(lambda cur: (merge_stocks(cur, stocks, d), merge_daily_prices(cur, d, rows)))
        return len(rows)
    if dataset == "pe":
        pe = (fetch_twse_pe if market == "TWSE" else fetch_tpex_pe)(d)
        if pe:
            _save(merge_fundamentals, d, [{"stock_code": c, **r} for c, r in pe.items()])
        return len(pe)
    if dataset == "insti":
        insti = (fetch_twse_insti if market == "TWSE" else fetch_tpex_insti)(d)
        if insti:
            _save(merge_institutional, d, [{"stock_code": c, **r} for c, r in insti.items()])
        return len(insti)
    if dataset == "breadth":
        if market == "TWSE":
            _quotes("TWSE", d, cache)                   # 行情抓取失敗時這裡丟出同一個例外
            row = parse_twse_breadth(cache["MI_INDEX"], d)
        else:
            row = fetch_tpex_breadth(d)
        if row:
            _save(merge_breadth, row)
        return 1 if row else 0
    if dataset == HOLDINGS_DS:
        if "closed" not in cache:
            conn = db.connect()
            try:
                cache["closed"] = load_closed(conn.cursor())
            finally:
                conn.close()
        got = fetch_holdings(market, d, cache["closed"])
        if not got:
            return 0                                    # 尚未公布，或回應的持股日不是 d
        summary, rows = got
        if not _save(merge_holdings, market, summary, rows):
            print(f"  ⚠️  etfs 沒有 {market}，持股未寫入")
            return 0
        return summary["n_stocks"]
    if dataset == MARGIN:
        rows, total = (fetch_twse_margin if market == "TWSE" else fetch_tpex_margin)(d)
        stocks = [r for r in rows if is_valid_stock_code(r["stock_code"])]
        etfs = [r for r in rows if is_etf_code(r["stock_code"])]
        if not stocks:
            return 0
        _save(lambda cur: (merge_margin(cur, d, stocks, "stock"), etfs and merge_margin(cur, d, etfs, "etf"),
                           merge_margin_market(cur, d, market, total)))
        return len(stocks)
    amount = fetch_twse_insti_amount(d)
    if amount:
        _save(merge_insti_amount, amount)
    return len(amount)


def collect_for_date(d: date, keys=DAY_KEYS) -> tuple:
    """
    收集單日，各資料集獨立抓取、寫入：一個失敗或未公布不影響其他。
    回傳 (written, errors)：written = {鍵: 筆數}（0 = 官方尚無資料）；errors = {鍵: 例外}。
    資料庫錯誤（pyodbc.Error）不攔截，由呼叫端處理。
    """
    print(f"\n📅 {d}  [{' + '.join(keys)}]")
    written, errors, cache = {}, {}, {}
    for key in keys:
        dataset, _, market = key.partition(".")
        if dataset in ("pe", "insti", MARGIN, "breadth") and written.get(f"prices.{market}") == 0:
            continue                # 同市場行情還沒有：本益比、法人、融資融券、漲跌家數不可能先有，不發請求
        if dataset == "pe" and f"prices.{market}" in errors:
            continue                # 本益比只寫入有行情列的股票
        try:
            written[key] = _collect_key(key, d, cache)
        except (FetchError, *PARSE_ERRORS) as e:
            errors[key] = e
            print(f"  ⚠️  {key} 失敗：{e}")
    done = "、".join(f"{k} {v} 筆" for k, v in written.items() if v)
    none = "、".join(k for k, v in written.items() if not v)
    if done:
        print(f"  ✅ 寫入：{done}")
    if none:
        print(f"  ℹ️  官方尚無資料：{none}")
    return written, errors


__all__ = ["collect_for_date", "FetchError", "PRICES", "PE", "INSTI", "ETF", "MARGIN", "HOLDINGS_DS", "ALL_DATASETS"]
