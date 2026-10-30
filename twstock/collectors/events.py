"""
價格調整事件：證交所除權息（TWT49U）、減資（TWTAUU）、面額變更（TWTB8U）、櫃買除權息（exDailyQ）。
四個端點都可用日期區間查詢；寫入 price_events（MERGE，可重跑）。上櫃減資類事件在匯出時由日線反推。
"""
from datetime import timedelta

from .. import db
from ..fetch import FetchError, clean_number, is_valid_stock_code, request
from .alerts import roc_date

EVENT_TYPES = ("息", "權", "權息", "減", "面")
CHUNK_DAYS = 183      # 每次查詢的日期區間（實測 TWT49U 10 個月、櫃買 1 年一次可查；保守取半年）
LOOKBACK_DAYS = 7     # 每日 collect 往回查的天數，補抓晚公告或前幾天漏抓的事件

# 來源：(方法, 網址, 日期參數格式, (日期欄, 代號欄, 前收欄, 參考價欄, 類型欄), 固定類型)
_SOURCES = {
    "TWT49U": ("GET", "https://www.twse.com.tw/rwd/zh/exRight/TWT49U", "%Y%m%d",
               ("資料日期", "股票代號", "除權息前收盤價", "除權息參考價", "權/息"), None),
    "TWTAUU": ("GET", "https://www.twse.com.tw/rwd/zh/reducation/TWTAUU", "%Y%m%d",
               ("恢復買賣日期", "股票代號", "停止買賣前收盤價格", "恢復買賣參考價", None), "減"),
    "TWTB8U": ("GET", "https://www.twse.com.tw/rwd/zh/change/TWTB8U", "%Y%m%d",
               ("恢復買賣日期", "股票代號", "停止買賣前收盤價格", "恢復買賣參考價", None), "面"),
    "TPEX_EX": ("POST", "https://www.tpex.org.tw/www/zh-tw/bulletin/exDailyQ", "%Y/%m/%d",
                ("除權息日期", "代號", "除權息前收盤價", "除權息參考價", "權/息"), None),
}


def parse_events(source: str, fields, rows) -> list:
    """官方事件表 → 寫入用 dict；非一般股票、日期或價格無法解析、類型不明的列略過；欄位缺漏回傳 []。"""
    names, fixed = _SOURCES[source][3], _SOURCES[source][4]
    idx = {f: i for i, f in enumerate(fields or [])}
    need = [n for n in names if n]
    if not all(n in idx for n in need):
        return []
    out = []
    for row in rows or []:
        if len(row) <= max(idx[n] for n in need):
            continue
        code, d = str(row[idx[names[1]]]).strip(), roc_date(row[idx[names[0]]])
        prev, ref = clean_number(row[idx[names[2]]]), clean_number(row[idx[names[3]]])
        kind = fixed or str(row[idx[names[4]]]).strip().lstrip("除")     # 櫃買為「除權息」→「權息」
        if not is_valid_stock_code(code) or d is None or not prev or not ref or kind not in EVENT_TYPES:
            continue
        out.append({"stock_code": code, "event_date": d.isoformat(), "event_type": kind,
                    "prev_close": prev, "ref_price": ref, "source": source})
    return out


def fetch_events(source: str, start, end) -> list:
    method, url, fmt = _SOURCES[source][:3]
    form = {"startDate": f"{start:{fmt}}", "endDate": f"{end:{fmt}}", "response": "json"}
    data = request(method, url, **({"params": form} if method == "GET" else {"data": form}))
    if not isinstance(data, dict):
        raise FetchError(f"事件回應格式不符：{source}")
    if source == "TPEX_EX":
        data = next((t for t in data.get("tables", []) if "代號" in (t.get("fields") or [])), {})
    return parse_events(source, data.get("fields"), data.get("data"))


def collect_events(start, end) -> int:
    """[start, end] 依 CHUNK_DAYS 切段，四個端點全部抓完才寫入；只寫入 stocks 表已有的股票。"""
    rows, s = [], start
    while s <= end:
        e = min(end, s + timedelta(days=CHUNK_DAYS - 1))
        for source in _SOURCES:
            rows += fetch_events(source, s, e)
        s = e + timedelta(days=1)
    # 同鍵只留一筆，避免 MERGE 同一列被更新兩次
    rows = list({(r["stock_code"], r["event_date"], r["source"]): r for r in rows}.values())
    if rows:
        conn = db.connect()
        try:
            conn.cursor().execute("""
                MERGE price_events AS t
                USING (
                    SELECT st.stock_id, j.*
                    FROM OPENJSON(?) WITH (
                        stock_code NVARCHAR(10), event_date DATE, event_type NVARCHAR(4),
                        prev_close DECIMAL(10,2), ref_price DECIMAL(10,2), source NVARCHAR(10)
                    ) AS j
                    JOIN stocks st ON st.stock_code = j.stock_code
                ) AS s
                ON t.stock_id = s.stock_id AND t.event_date = s.event_date AND t.source = s.source
                WHEN MATCHED THEN UPDATE SET
                    event_type = s.event_type, prev_close = s.prev_close, ref_price = s.ref_price
                WHEN NOT MATCHED THEN
                    INSERT (stock_id, event_date, event_type, prev_close, ref_price, source)
                    VALUES (s.stock_id, s.event_date, s.event_type, s.prev_close, s.ref_price, s.source);
            """, db.to_json(rows))
            conn.commit()
        finally:
            conn.close()
    print(f"  📌 除權息／減資／面額變更事件：{len(rows)} 筆（{start} ～ {end}）")
    return len(rows)
