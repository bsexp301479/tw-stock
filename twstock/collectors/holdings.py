"""
主動型 ETF 每日持股（第 5 輪）：統一投信 GetPCF（申購買回清單）。

日期語意：參數 date 是清單「生效日」= 持股公布日的下一個交易日；回應的 TranDate 才是持股日。
國內 ETF 當天公布當天的持股（生效日 = 持股日後第 1 個交易日）；跨境 ETF 落後 1 天（第 2 個交易日）。
資料表以持股日為準；回應的 TranDate 與要求的持股日不同（尚未公布、連假）一律不寫入。
"""
from datetime import date, datetime, timedelta

from .. import db
from ..fetch import SchemaError, request
from ..health import HOLDINGS
from ..tradingcal import trading_days

URL = "https://www.ezmoney.com.tw/ETF/Transaction/GetPCF"
_EPOCH = datetime(1970, 1, 1) + timedelta(hours=8)      # /Date(毫秒)/ 是 UTC，換成台灣時間


def ez_time(s: str) -> datetime:
    """'2026-11-03T16:56:43' 或 '/Date(1761753600000)/'（歷史日期的格式）→ 台灣時間。"""
    if s.startswith("/Date("):
        return _EPOCH + timedelta(milliseconds=int(s[6:-2]))
    return datetime.fromisoformat(s[:19])


def ez_date(s: str) -> date:
    return ez_time(s).date()


def post_date(d: date, delay: int, closed) -> date:
    """持股日 d 的清單生效日：d 之後第 delay + 1 個交易日。"""
    return trading_days(d + timedelta(days=1), d + timedelta(days=40), closed)[delay]


def parse_pcf(data: dict, d: date):
    """GetPCF 回應 → (彙總, 明細列)；尚未公布或持股日不是 d 回傳 None。欄位不符 → SchemaError。"""
    if not isinstance(data, dict) or not {"pcf", "asset"} <= data.keys():
        raise SchemaError("GetPCF 回應缺少 pcf 或 asset")
    if not data["asset"]:
        return None                                     # 尚未公布：pcf 全是 0、asset 為空
    pcf = {p["PCFCode"]: p for p in data["pcf"]}
    if "NAV" not in pcf:
        raise SchemaError("GetPCF 的 pcf 缺少 NAV")
    if ez_date(pcf["NAV"]["TranDate"]) != d:
        return None
    rows, edited = [], None
    for a in data["asset"]:
        for x in a["Details"] or []:
            if ez_date(x["TranDate"]) != d:
                raise SchemaError(f"GetPCF 明細持股日 {x['TranDate']} 與彙總不同")
            rows.append({"asset_type": a["AssetCode"], "code": str(x["DetailCode"]).strip(),
                         "month": (x.get("MTH") or "").strip(), "name": str(x["DetailName"]).strip(),
                         "shares": int(x["Share"]), "amount": x["Amount"], "weight": x["NavRate"],
                         "currency": x["MoneyType"]})
            edited = edited or x.get("EditTime")
    stocks = [r for r in rows if r["asset_type"] == "ST"]
    futures = [r for r in rows if r["asset_type"] == "GD"]
    amount = lambda p: pcf[p]["Amount"] if p in pcf else None
    summary = {"hold_date": d.isoformat(), "post_date": ez_date(pcf["NAV"]["PostDate"]).isoformat(),
               "nav": amount("NAV"), "units": amount("OUT_UNIT"), "nav_unit": amount("P_UNIT"),
               "n_stocks": len(stocks), "stock_weight": round(sum(r["weight"] or 0 for r in stocks), 2),
               "futures_lots": sum(r["shares"] for r in futures), "futures_amount": sum(r["amount"] or 0 for r in futures),
               "edited_at": ez_time(edited).isoformat() if edited else None}
    return summary, rows


def fetch_holdings(code: str, d: date, closed):
    fund, delay, _ = HOLDINGS[code]
    post = post_date(d, delay, closed)
    data = request("POST", URL, json={"fundCode": fund, "date": f"{post.year - 1911}/{post:%m/%d}", "specificDate": True})
    return parse_pcf(data, d)


def merge_holdings(cursor, code: str, summary: dict, rows: list) -> bool:
    """同一檔同一持股日整批取代（持股會出清，不能只 MERGE）。etfs 沒有這檔回傳 False。"""
    row = cursor.execute("SELECT etf_id FROM etfs WHERE etf_code = ?", code).fetchone()
    if not row:
        return False
    etf_id, d = row[0], summary["hold_date"]
    cursor.execute("DELETE FROM etf_holdings WHERE etf_id = ? AND hold_date = ?", etf_id, d)
    cursor.execute("""
        INSERT INTO etf_holdings (etf_id, hold_date, asset_type, code, month, name, shares, amount, weight, currency)
        SELECT ?, ?, asset_type, code, month, name, shares, amount, weight, currency FROM OPENJSON(?) WITH (
            asset_type NVARCHAR(10), code NVARCHAR(20), month NVARCHAR(10), name NVARCHAR(100), shares BIGINT,
            amount DECIMAL(20,2), weight DECIMAL(7,2), currency NVARCHAR(5))
    """, etf_id, d, db.to_json(rows))
    cursor.execute("""
        MERGE etf_holding_summary AS t
        USING OPENJSON(?) WITH (
            hold_date DATE, post_date DATE, nav DECIMAL(20,2), units BIGINT, nav_unit DECIMAL(12,4), n_stocks INT,
            stock_weight DECIMAL(7,2), futures_lots INT, futures_amount DECIMAL(20,2), edited_at DATETIME2(0)
        ) AS s
        ON t.etf_id = ? AND t.hold_date = s.hold_date
        WHEN MATCHED THEN UPDATE SET
            post_date = s.post_date, nav = s.nav, units = s.units, nav_unit = s.nav_unit, n_stocks = s.n_stocks,
            stock_weight = s.stock_weight, futures_lots = s.futures_lots, futures_amount = s.futures_amount, edited_at = s.edited_at
        WHEN NOT MATCHED THEN
            INSERT (etf_id, hold_date, post_date, nav, units, nav_unit, n_stocks, stock_weight, futures_lots, futures_amount, edited_at)
            VALUES (?, s.hold_date, s.post_date, s.nav, s.units, s.nav_unit, s.n_stocks, s.stock_weight, s.futures_lots,
                    s.futures_amount, s.edited_at);
    """, db.to_json([summary]), etf_id, etf_id)
    return True
