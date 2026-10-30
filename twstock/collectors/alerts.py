"""
處置股與注意股（證交所、櫃買 OpenAPI）。端點只提供最近的公告，每天收一次、保留歷史。
"""
import re
from datetime import date

from .. import db
from ..fetch import FetchError, is_valid_stock_code, request

# (網址, 類型, 代號欄, 公告日欄, 處置期間欄, 長文欄, 簡短原因欄)
_SOURCES = (
    ("https://openapi.twse.com.tw/v1/announcement/punish", "disposal",
     "Code", "Date", "DispositionPeriod", "Detail", "ReasonsOfDisposition"),
    ("https://openapi.twse.com.tw/v1/announcement/notice", "notice",
     "Code", "Date", None, "TradingInfoForAttention", None),
    ("https://www.tpex.org.tw/openapi/v1/tpex_disposal_information", "disposal",
     "SecuritiesCompanyCode", "Date", "DispositionPeriod", "DisposalCondition", "DispositionReasons"),
    ("https://www.tpex.org.tw/openapi/v1/tpex_trading_warning_information", "notice",
     "SecuritiesCompanyCode", "Date", None, "TradingInformation", None),
)
_REASON = re.compile(r"處置原因：(.+?)。")
_MATCHING = re.compile(r"約每[^，。；;()（）]{1,5}分鐘撮合一次")


def roc_date(s):
    """民國日期 1151029、115/10/29 或 115年10月29日 → date；空白或格式不符回傳 None。"""
    s = str(s or "").strip().replace("年", "/").replace("月", "/").replace("日", "")
    if "/" in s:
        parts = s.split("/")
    elif s.isdigit() and len(s) == 7:
        parts = (s[:3], s[3:5], s[5:])
    else:
        return None
    try:
        y, m, d = (int(x) for x in parts)
        return date(y + 1911, m, d)
    except ValueError:
        return None


def roc_period(s):
    """處置期間「115/10/28～115/11/03」或「1151030~1151105」→ (起日, 迄日)；無法解析為 (None, None)。"""
    parts = re.split(r"[～~]", str(s or ""))
    return (roc_date(parts[0]), roc_date(parts[1])) if len(parts) == 2 else (None, None)


def parse_alert(row, kind, code_f, date_f, period_f, text_f, reason_f):
    """單筆公告 → 寫入用 dict；非一般股票、佔位資料、日期無法解析時回傳 None。"""
    code, announce = str(row.get(code_f) or "").strip(), roc_date(row.get(date_f))
    if not is_valid_stock_code(code) or announce is None:
        return None
    text = str(row.get(text_f) or "")
    item = {"stock_code": code, "alert_type": kind, "announce_date": announce.isoformat(),
            "start_date": None, "end_date": None, "reason": None, "measure": None}
    if kind == "notice":
        item["reason"] = text.strip()[:1000] or None
        return item
    start, end = roc_period(row.get(period_f))
    if start is None or end is None:
        return None
    m = _REASON.search(text)
    matching = _MATCHING.search(text)
    item.update(start_date=start.isoformat(), end_date=end.isoformat(),
                reason=(m.group(1) if m else str(row.get(reason_f) or "").strip())[:1000] or None,
                measure="、".join(x for x in (matching and matching.group(0),
                                               "預收款券" if "全部之買進價金" in text else None) if x) or None)
    return item


def fetch_alerts() -> list:
    rows = []
    for url, kind, *fields in _SOURCES:
        data = request("GET", url)
        if not isinstance(data, list):
            raise FetchError(f"處置／注意股回應格式不符：{url}")
        rows += [a for a in (parse_alert(r, kind, *fields) for r in data) if a]
    # 同一檔同一天同類型只留一筆，避免 MERGE 同一列被更新兩次
    return list({(a["stock_code"], a["alert_type"], a["announce_date"]): a for a in rows}.values())


def collect_alerts() -> int:
    """4 個端點全部抓完才寫入；只寫入 stocks 表已有的股票。"""
    rows = fetch_alerts()
    if rows:
        conn = db.connect()
        try:
            conn.cursor().execute("""
                MERGE stock_alerts AS t
                USING (
                    SELECT st.stock_id, j.*
                    FROM OPENJSON(?) WITH (
                        stock_code NVARCHAR(10), alert_type NVARCHAR(10), announce_date DATE,
                        start_date DATE, end_date DATE, reason NVARCHAR(1000), measure NVARCHAR(200)
                    ) AS j
                    JOIN stocks st ON st.stock_code = j.stock_code
                ) AS s
                ON t.stock_id = s.stock_id AND t.alert_type = s.alert_type AND t.announce_date = s.announce_date
                WHEN MATCHED THEN UPDATE SET
                    start_date = s.start_date, end_date = s.end_date, reason = s.reason, measure = s.measure
                WHEN NOT MATCHED THEN
                    INSERT (stock_id, alert_type, announce_date, start_date, end_date, reason, measure)
                    VALUES (s.stock_id, s.alert_type, s.announce_date, s.start_date, s.end_date, s.reason, s.measure);
            """, db.to_json(rows))
            conn.commit()
        finally:
            conn.close()
    n = sum(a["alert_type"] == "disposal" for a in rows)
    print(f"  🚨 處置 {n} 筆、注意 {len(rows) - n} 筆（未在股票清單的代號不寫入）")
    return len(rows)
