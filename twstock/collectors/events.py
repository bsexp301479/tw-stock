"""
價格調整事件：證交所除權息（TWT49U）、減資（TWTAUU）、面額變更（TWTB8U）、櫃買除權息（exDailyQ）。
四個端點都可用日期區間查詢；寫入 price_events（MERGE，可重跑）。上櫃減資類事件在匯出時由日線反推。
"""
from datetime import timedelta

from .. import db
from ..fetch import FetchError, clean_number, is_etf_code, is_valid_stock_code, request
from .alerts import roc_date

EVENT_TYPES = ("息", "權", "權息", "減", "面")
CHUNK_DAYS = 183      # 每次查詢的日期區間（實測 TWT49U 10 個月、櫃買 1 年一次可查；保守取半年）
LOOKBACK_DAYS = 7     # 每日 collect 往回查的天數，補抓晚公告或前幾天漏抓的事件

# 來源：(方法, 網址, 日期參數格式, (日期欄, 代號欄, 前收欄, 參考價欄, 類型欄), 固定類型, 減除股利參考價欄)
# 第 19 輪：減除股利參考價是選用欄位，找不到時存 NULL，其他欄位照常寫入
_SOURCES = {
    "TWT49U": ("GET", "https://www.twse.com.tw/rwd/zh/exRight/TWT49U", "%Y%m%d",
               ("資料日期", "股票代號", "除權息前收盤價", "除權息參考價", "權/息"), None, "減除股利參考價"),
    "TWTAUU": ("GET", "https://www.twse.com.tw/rwd/zh/reducation/TWTAUU", "%Y%m%d",
               ("恢復買賣日期", "股票代號", "停止買賣前收盤價格", "恢復買賣參考價", None), "減", None),
    "TWTB8U": ("GET", "https://www.twse.com.tw/rwd/zh/change/TWTB8U", "%Y%m%d",
               ("恢復買賣日期", "股票代號", "停止買賣前收盤價格", "恢復買賣參考價", None), "面", None),
    "TPEX_EX": ("POST", "https://www.tpex.org.tw/www/zh-tw/bulletin/exDailyQ", "%Y/%m/%d",
                ("除權息日期", "代號", "除權息前收盤價", "除權息參考價", "權/息"), None, "減除股利參考價"),
}
# 第 24 輪 F24-5：股利金額欄（選用，找不到或無法解析存 NULL）：(權值+息值, 現金股利, 每仟股無償配股)；ETF 只取這兩個來源的「息」
# 上市只有「權值+息值」：「息」= 現金股利，「權」「權息」混了配股與現增，現金股利存 NULL
_AMOUNTS = {"TWT49U": ("權值+息值", None, None), "TPEX_EX": ("權值+息值", "息值", "每仟股無償配股")}


def parse_events(source: str, fields, rows) -> list:
    """官方事件表 → 寫入用 dict；非一般股票、日期或價格無法解析、類型不明的列略過；必要欄位缺漏回傳 []（減除股利參考價缺漏只存 None）。
    第 24 輪：回傳不變（不含股利金額、ETF）；收集用 parse_events_all。"""
    return [{k: v for k, v in r.items() if k not in ("div_total", "div_cash", "stock_div")} for r in parse_events_all(source, fields, rows)[0]]


def parse_events_all(source: str, fields, rows) -> tuple:
    """第 24 輪 F24-5：(股票, ETF)。股票 dict 另帶有值的 div_total、div_cash、stock_div；ETF 只收 TWT49U、TPEX_EX 的「息」，
    {etf_code, event_date, event_type, prev_close, ref_price, source, div_cash}。ETN、受益證券、特別股等兩邊都不收。"""
    names, fixed, dcol = _SOURCES[source][3:6]
    idx = {f: i for i, f in enumerate(fields or [])}
    j = idx.get(dcol)
    amt = [idx.get(n) if n else None for n in _AMOUNTS.get(source, (None,) * 3)]
    need = [n for n in names if n]
    if not all(n in idx for n in need):
        return [], []
    out, etfs = [], []
    for row in rows or []:
        if len(row) <= max(idx[n] for n in need):
            continue
        code, d = str(row[idx[names[1]]]).strip(), roc_date(row[idx[names[0]]])
        prev, ref = clean_number(row[idx[names[2]]]), clean_number(row[idx[names[3]]])
        kind = fixed or str(row[idx[names[4]]]).strip().lstrip("除")     # 櫃買為「除權息」→「權息」
        div = clean_number(row[j]) if j is not None and j < len(row) else None
        total, cash, stock = (clean_number(row[k]) if k is not None and k < len(row) else None for k in amt)
        if source == "TWT49U" and kind == "息":
            cash = total
        if d is None or not prev or not ref or kind not in EVENT_TYPES:
            continue
        base = {"event_date": d.isoformat(), "event_type": kind, "prev_close": prev, "ref_price": ref, "source": source}
        if is_valid_stock_code(code):
            out.append({"stock_code": code, **base, **({"div_ref": div} if div else {}),
                        **{k: v for k, v in (("div_total", total), ("div_cash", cash), ("stock_div", stock)) if v is not None}})
        elif is_etf_code(code) and source in _AMOUNTS and kind == "息":
            etfs.append({"etf_code": code, **base, **({"div_cash": cash} if cash is not None else {})})
    return out, etfs


def fetch_events(source: str, start, end) -> list:
    method, url, fmt = _SOURCES[source][:3]
    form = {"startDate": f"{start:{fmt}}", "endDate": f"{end:{fmt}}", "response": "json"}
    data = request(method, url, **({"params": form} if method == "GET" else {"data": form}))
    if not isinstance(data, dict):
        raise FetchError(f"事件回應格式不符：{source}")
    if source == "TPEX_EX":
        data = next((t for t in data.get("tables", []) if "代號" in (t.get("fields") or [])), {})
    return parse_events_all(source, data.get("fields"), data.get("data"))


def collect_events(start, end) -> dict:
    """[start, end] 依 CHUNK_DAYS 切段，四個端點全部抓完才寫入；只寫入 stocks、etfs 表已有的代號。回傳 {"stocks": 筆數, "etfs": 筆數}。"""
    rows, etfs, s = [], [], start
    while s <= end:
        e = min(end, s + timedelta(days=CHUNK_DAYS - 1))
        for source in _SOURCES:
            got = fetch_events(source, s, e)
            rows += got[0]
            etfs += got[1]
        s = e + timedelta(days=1)
    # 同鍵只留一筆，避免 MERGE 同一列被更新兩次
    rows = list({(r["stock_code"], r["event_date"], r["source"]): r for r in rows}.values())
    etfs = list({(r["etf_code"], r["event_date"], r["source"]): r for r in etfs}.values())
    if rows or etfs:
        conn = db.connect()
        try:
            conn.cursor().execute("""
                MERGE price_events AS t
                USING (
                    SELECT st.stock_id, j.*
                    FROM OPENJSON(?) WITH (
                        stock_code NVARCHAR(10), event_date DATE, event_type NVARCHAR(4),
                        prev_close DECIMAL(10,2), ref_price DECIMAL(10,2), div_ref DECIMAL(10,2), source NVARCHAR(10),
                        div_total DECIMAL(12,6), div_cash DECIMAL(12,6), stock_div DECIMAL(14,8)
                    ) AS j
                    JOIN stocks st ON st.stock_code = j.stock_code
                ) AS s
                ON t.stock_id = s.stock_id AND t.event_date = s.event_date AND t.source = s.source
                WHEN MATCHED THEN UPDATE SET
                    event_type = s.event_type, prev_close = s.prev_close, ref_price = s.ref_price,
                    div_total = COALESCE(s.div_total, t.div_total), div_cash = COALESCE(s.div_cash, t.div_cash),
                    stock_div = COALESCE(s.stock_div, t.stock_div),
                    div_ref = COALESCE(s.div_ref, t.div_ref)     -- 欄位暫時找不到時不清掉已存的值
                WHEN NOT MATCHED THEN
                    INSERT (stock_id, event_date, event_type, prev_close, ref_price, div_ref, source, div_total, div_cash, stock_div)
                    VALUES (s.stock_id, s.event_date, s.event_type, s.prev_close, s.ref_price, s.div_ref, s.source,
                            s.div_total, s.div_cash, s.stock_div);
            """, db.to_json(rows))
            # 第 24 輪 F24-5：ETF 除息（只寫 etfs 表已有的 ETF；金額缺漏時不清掉已存的值）
            conn.cursor().execute("""
                MERGE etf_events AS t
                USING (
                    SELECT et.etf_id, j.*
                    FROM OPENJSON(?) WITH (
                        etf_code NVARCHAR(10), event_date DATE, event_type NVARCHAR(4),
                        prev_close DECIMAL(10,2), ref_price DECIMAL(10,2), div_cash DECIMAL(12,6), source NVARCHAR(10)
                    ) AS j
                    JOIN etfs et ON et.etf_code = j.etf_code
                ) AS s
                ON t.etf_id = s.etf_id AND t.event_date = s.event_date AND t.source = s.source
                WHEN MATCHED THEN UPDATE SET
                    event_type = s.event_type, prev_close = s.prev_close, ref_price = s.ref_price,
                    div_cash = COALESCE(s.div_cash, t.div_cash)
                WHEN NOT MATCHED THEN
                    INSERT (etf_id, event_date, event_type, prev_close, ref_price, div_cash, source)
                    VALUES (s.etf_id, s.event_date, s.event_type, s.prev_close, s.ref_price, s.div_cash, s.source);
            """, db.to_json(etfs))
            conn.commit()
        finally:
            conn.close()
    print(f"  📌 除權息／減資／面額變更事件：股票 {len(rows)} 筆、ETF {len(etfs)} 筆（{start} ～ {end}）")
    return {"stocks": len(rows), "etfs": len(etfs)}
