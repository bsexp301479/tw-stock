"""
第 53 輪 F53-1：上市、上櫃重大訊息（證交所 OpenAPI t187ap04_L、櫃買 OpenAPI mopsfin_t187ap04_O）。
官方每次只提供一天的公告（不能回補）；collect --catch-up 依「出表日期」判斷要不要抓，休市日、週末也抓，寫入 material_news。
只存發言日、時間、主旨等短欄位，不讀、不存「說明」。鍵 = (市場, 代號, 發言日, 發言時間, 主旨)；不刪除，first_seen 只在新增時寫。
"""
import re
import unicodedata
from datetime import time

import pyodbc

from .. import db
from ..fetch import SchemaError, request
from .alerts import roc_date

_URLS = {"TWSE": "https://openapi.twse.com.tw/v1/opendata/t187ap04_L",
         "TPEx": "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap04_O"}
# (代號, 名稱, 出表日期)；其餘欄名兩市場相同。上市「主旨 」欄名結尾有空白，比對前每個鍵先 strip()
_FIELDS = {"TWSE": ("公司代號", "公司名稱", "出表日期"), "TPEx": ("SecuritiesCompanyCode", "CompanyName", "Date")}
_LABEL = {"TWSE": "上市", "TPEx": "上櫃"}


def _time(s):
    """1～6 碼數字（補 0 到 6 碼）或 HH:MM:SS → time；其他寫法或超出範圍 → None。"""
    s = str(s or "").strip()
    if re.fullmatch(r"\d{1,6}", s):
        s = s.zfill(6)
        h, m, x = int(s[:2]), int(s[2:4]), int(s[4:])
    elif re.fullmatch(r"\d{2}:\d{2}:\d{2}", s):
        h, m, x = (int(v) for v in s.split(":"))
    else:
        return None
    return time(h, m, x) if h < 24 and m < 60 and x < 60 else None


def parse_news(market: str, data) -> tuple:
    """官方回應 → (出表日期, rows, 略過列數)。空陣列 → (None, [], 0)；不是陣列、缺必要欄、出表日期全部解析不到 → SchemaError。
    rows = [{code, name, speak_date, speak_time, subject, clause, fact_date}]；同一則（主旨以 NFKC＋casefold 比較）只留最後一列。"""
    c_code, c_name, c_out = _FIELDS[market]
    if not isinstance(data, list):
        raise SchemaError(f"{market} 重大訊息回應不是陣列")
    if not data:
        return None, [], 0
    if not isinstance(data[0], dict):
        raise SchemaError(f"{market} 重大訊息欄位不符：{data[0]!r}"[:200])
    first = {k.strip() for k in data[0]}
    if not all(k in first for k in (c_code, "發言日期", "發言時間", "主旨", c_out)):
        raise SchemaError(f"{market} 重大訊息欄位不符：{list(data[0])}")
    outs, out, skipped = [], {}, 0
    for raw in data:
        if not isinstance(raw, dict):
            skipped += 1
            continue
        r = {k.strip(): v for k, v in raw.items()}
        if (o := roc_date(r.get(c_out))) is not None:
            outs.append(o)
        code, subject = str(r.get(c_code) or "").strip(), str(r.get("主旨") or "").strip()
        sd, st = roc_date(r.get("發言日期")), _time(r.get("發言時間"))
        if not code or len(code) > 10 or not subject or len(subject) > 400 or sd is None or st is None:
            skipped += 1
            continue
        name, clause = str(r.get(c_name) or "").strip(), str(r.get("符合條款") or "").strip()
        fd = roc_date(r.get("事實發生日"))
        out[(code, sd, st, unicodedata.normalize("NFKC", subject).casefold())] = {
            "code": code, "name": name if 0 < len(name) <= 40 else None, "speak_date": sd, "speak_time": st, "subject": subject,
            "clause": clause if 0 < len(clause) <= 40 else None,
            "fact_date": fd if fd is not None and (fd - sd).days <= 366 else None}        # 1201123 這種年份打錯的日子存 NULL
    if not outs:
        raise SchemaError(f"{market} 重大訊息出表日期無法解析")
    if min(outs) != max(outs):
        print(f"  ⚠️  {_LABEL[market]}重大訊息的出表日期不一致（{min(outs)} ～ {max(outs)}），以最晚的為準")
    return max(outs), list(out.values()), skipped


def fetch_news(market: str) -> tuple:
    return parse_news(market, request("GET", _URLS[market], isolated=True))


def collect_news(market: str, seen):
    """抓一個市場並 MERGE；seen = 抓取日（台灣日期）。官方沒有資料 → None（不記錄，下次執行再抓）；
    否則回傳 {"on": 抓取日, "t": 出表日期, "d": 最新發言日, "n": 筆數, "new": 新增筆數}。寫入失敗包成 RuntimeError（_guard 只印 ⚠️）。"""
    out_date, rows, skipped = fetch_news(market)
    if not rows and skipped:                                       # 第 53 輪 QA53-02：有資料但每一列都無法解析
        print(f"  ⚠️  {_LABEL[market]}重大訊息 {skipped:,} 筆都無法解析，下次執行再抓")
        return None
    if not rows:
        print(f"  📰 {_LABEL[market]}重大訊息：官方目前沒有資料（0 筆），下次執行再抓")
        return None
    j = db.to_json([{**r, "speak_date": r["speak_date"].isoformat(), "speak_time": r["speak_time"].isoformat(),
                     "fact_date": r["fact_date"] and r["fact_date"].isoformat()} for r in rows])
    try:
        conn = db.connect()
        try:
            got = conn.cursor().execute("""
                MERGE material_news AS t
                USING (SELECT * FROM OPENJSON(?) WITH (code NVARCHAR(10), name NVARCHAR(40), speak_date DATE, speak_time TIME(0),
                       subject NVARCHAR(400), clause NVARCHAR(40), fact_date DATE)) AS s
                ON t.market = ? AND t.code = s.code AND t.speak_date = s.speak_date AND t.speak_time = s.speak_time AND t.subject = s.subject
                WHEN MATCHED THEN UPDATE SET name = s.name, clause = s.clause, fact_date = s.fact_date, out_date = ?
                WHEN NOT MATCHED THEN INSERT (market, code, name, speak_date, speak_time, subject, clause, fact_date, out_date, first_seen)
                     VALUES (?, s.code, s.name, s.speak_date, s.speak_time, s.subject, s.clause, s.fact_date, ?, ?)
                OUTPUT $action;
            """, j, market, out_date, market, out_date, seen).fetchall()
            conn.commit()
        finally:
            conn.close()
    except pyodbc.Error as e:
        raise RuntimeError(f"material_news 寫入失敗（請確認已執行 setup-db）：{str(e).splitlines()[0][:120]}") from e
    new = sum(r[0] == "INSERT" for r in got)
    lo, hi = min(r["speak_date"] for r in rows), max(r["speak_date"] for r in rows)
    print(f"  📰 {_LABEL[market]}重大訊息 {len(rows):,} 筆（出表 {out_date}，發言日 {lo}{f' ～ {hi}' if hi != lo else ''}，新增 {new:,} 筆"
          + (f"，略過 {skipped:,} 筆無法解析" if skipped else "") + "）")
    return {"on": str(seen), "t": str(out_date), "d": str(hi), "n": len(rows), "new": new}
