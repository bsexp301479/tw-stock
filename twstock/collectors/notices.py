"""
第 40 輪 F40-1：除權除息預告表（上市證交所 TWT48U、上櫃櫃買 OpenAPI tpex_exright_prepost）。
兩個來源都只有當下快照（不能回補）；collect --catch-up 每個新交易日抓一次（和除權息事件同一個條件），寫入 dividend_notices。
鍵 = (代號, 除權息日)；不刪除，改日期或消失的舊列靠 last_seen 停在舊日自然失效（匯出只取最近一次成功快照）。
"""
from decimal import Decimal

from .. import db
from ..fetch import SchemaError, clean_number, is_etf_code, is_valid_stock_code, request
from .alerts import roc_date

NOTICE_TYPES = ("息", "權", "權息")
_URLS = {"TWSE": ("https://www.twse.com.tw/rwd/zh/exRight/TWT48U", {"response": "json"}),
         "TPEx": ("https://www.tpex.org.tw/openapi/v1/tpex_exright_prepost", None)}
# (除權除息日, 代號, 類型, 現金股利, 無償配股率, 現增配股率, 現增認購價)；上櫃欄名照官方拼法 ExRrights
_FIELDS = {"TWSE": ("除權除息日期", "股票代號", "除權息", "現金股利", "無償配股率", "現金增資配股率", "現金增資認購價"),
           "TPEx": ("ExRrightsExDividendDate", "SecuritiesCompanyCode", "ExRrightsExDividend", "CashDividend", "StockDividendRatio",
                    "SubscriptionRatioToNewSharesIssued", "SubscriptionPricePerShare")}
_LABEL = {"TWSE": "上市", "TPEx": "上櫃"}


def parse_notices(market: str, data) -> list:
    """官方回應 → [{code, ex_date, event_type, cash_div, stock_ratio, sub_ratio, sub_price}]（Decimal；cash_div、sub_price 可為 None）。
    沒有資料（上市 stat 不是 OK 且沒有 fields/data、上櫃空陣列）→ []；有資料但欄位不符 → SchemaError。
    只收一般股票與 ETF（ETN、受益證券等不收）；日期或類型無法解析的列略過；同鍵只留最後一筆。"""
    names = _FIELDS[market]
    if market == "TWSE":
        if not isinstance(data, dict):
            raise SchemaError("TWT48U 回應不是 JSON 物件")
        fields, rows = data.get("fields"), data.get("data")
        if data.get("stat") != "OK" and not fields and not rows:
            return []
        idx = {f: i for i, f in enumerate(fields or [])}
        if not all(n in idx for n in names):
            raise SchemaError(f"TWT48U 欄位不符：{fields}")
        rows = [dict(zip(names, (r[idx[n]] if idx[n] < len(r) else None for n in names))) for r in rows or []]
    else:
        if not isinstance(data, list):
            raise SchemaError("tpex_exright_prepost 回應不是陣列")
        if data and not (isinstance(data[0], dict) and all(n in data[0] for n in names)):
            raise SchemaError(f"tpex_exright_prepost 欄位不符：{list(data[0]) if isinstance(data[0], dict) else data[0]}")
        rows = [r for r in data if isinstance(r, dict)]
    out = {}
    for r in rows:
        code, d = str(r[names[1]] or "").strip(), roc_date(r[names[0]])
        kind = str(r[names[2]] or "").strip().lstrip("除")       # 櫃買「除息／除權／除權息」→ 去掉「除」
        if d is None or kind not in NOTICE_TYPES or not (is_valid_stock_code(code) or is_etf_code(code)):
            continue
        num = lambda k: x if (x := clean_number(r[names[k]], Decimal)) is None or x.is_finite() else None   # QA40-04：NaN、Infinity 當作沒有值
        sub = num(5) or Decimal(0)
        out[(code, d)] = {"code": code, "ex_date": d, "event_type": kind, "cash_div": num(3), "stock_ratio": num(4) or Decimal(0),
                          "sub_ratio": sub, "sub_price": num(6) if sub else None}     # 「待公告」「尚未公告」「註4」→ None
    return list(out.values())


def fetch_notices(market: str) -> list:
    url, params = _URLS[market]
    return parse_notices(market, request("GET", url, isolated=True, **({"params": params} if params else {})))


def collect_notices(market: str, seen) -> int:
    """抓一個市場的預告表並 MERGE（只寫 stocks、etfs 表已有的代號；first_seen 只在新增時寫）。seen = 抓取日（台灣日期）。回傳解析後的筆數。"""
    rows = fetch_notices(market)
    if rows:
        conn = db.connect()
        try:
            # 小數轉成不帶指數的字串，OPENJSON 轉 DECIMAL 不會遇到 1E-8 這種寫法
            j = db.to_json([{**{k: format(v, "f") if isinstance(v, Decimal) else v for k, v in r.items()},
                             "ex_date": r["ex_date"].isoformat()} for r in rows])
            conn.cursor().execute("""
                MERGE dividend_notices AS t
                USING (
                    SELECT j.*, CAST(CASE WHEN et.etf_id IS NULL THEN 0 ELSE 1 END AS BIT) AS is_etf
                    FROM OPENJSON(?) WITH (
                        code NVARCHAR(10), ex_date DATE, event_type NVARCHAR(4), cash_div DECIMAL(16,8),
                        stock_ratio DECIMAL(16,8), sub_ratio DECIMAL(16,8), sub_price DECIMAL(10,2)
                    ) AS j
                    LEFT JOIN stocks st ON st.stock_code = j.code
                    LEFT JOIN etfs et ON et.etf_code = j.code
                    WHERE st.stock_id IS NOT NULL OR et.etf_id IS NOT NULL
                ) AS s
                ON t.code = s.code AND t.ex_date = s.ex_date
                WHEN MATCHED THEN UPDATE SET
                    market = ?, is_etf = s.is_etf, event_type = s.event_type, cash_div = s.cash_div, stock_ratio = s.stock_ratio,
                    sub_ratio = s.sub_ratio, sub_price = s.sub_price, last_seen = ?, updated_at = GETDATE()
                WHEN NOT MATCHED THEN
                    INSERT (code, market, is_etf, ex_date, event_type, cash_div, stock_ratio, sub_ratio, sub_price, first_seen, last_seen)
                    VALUES (s.code, ?, s.is_etf, s.ex_date, s.event_type, s.cash_div, s.stock_ratio, s.sub_ratio, s.sub_price, ?, ?);
            """, j, market, seen, market, seen, seen)
            conn.commit()
        finally:
            conn.close()
    span = f"（除權息日 {min(r['ex_date'] for r in rows)} ～ {max(r['ex_date'] for r in rows)}）" if rows else ""
    print(f"  📅 {_LABEL[market]}除權除息預告 {len(rows)} 筆{span}")
    return len(rows)
