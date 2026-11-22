"""
第 43 輪 F43-1：集保股權分散表（集保結算所開放資料 getOD.ashx?id=1-5，CSV，全市場一週一份；沒有日期參數，只有最近一週，不能回補）。
collect --catch-up 在「最近一個過完的週」還沒入庫時抓一次（tradingcal.last_full_week；比週不比日期，資料日以官方檔為準），寫入 share_distribution。
寬表：一檔一週一列，存 1～16 級人數 n、股數 s（16 = 差異數調整）與 17 級合計；官方比例不存（匯出時由股數自算）。
"""
import csv
import re
from datetime import date

from .. import db
from ..fetch import SchemaError, is_etf_code, is_valid_stock_code, request

URL = "https://opendata.tdcc.com.tw/getOD.ashx?id=1-5"
HEAD = ("資料日期", "證券代號", "持股分級", "人數", "股數", "占集保庫存數比例%")
LEVELS = [str(i) for i in range(1, 18)]
N_COLS = [f"n{i}" for i in range(1, 17)] + ["n_total"]
S_COLS = [f"s{i}" for i in range(1, 17)] + ["s_total"]


def _count(x: str):
    """不帶小數的非負整數；其他（1.5、-3、空白）→ None。"""
    return int(x) if x.isascii() and x.isdigit() else None


def parse_tdcc(text: str) -> tuple:
    """
    官方 CSV（已去 BOM）→ (資料日, rows, skipped)。rows = [{code, n1..n16, s1..s16, n_total, s_total}]（代號已去空白）。
    表頭不符、沒有資料列、某列不是 6 欄、資料日不是唯一的 8 碼西元日期、某代號 1～17 級缺級或重複 → SchemaError（整份不寫）。
    只收一般股票與 ETF；合計驗算（R46：人數 1～15 級和 = 17 級；股數 1～15 級和 − 16 級 = 17 級；17 級股數 > 0）不成立或數字不是非負整數 → 略過該代號並計數。
    """
    lines = list(csv.reader(text.splitlines()))
    if not lines or tuple(c.strip() for c in lines[0]) != HEAD:
        raise SchemaError(f"集保股權分散表頭不符：{lines[0] if lines else []}")
    body = [r for r in lines[1:] if r]
    if not body:
        raise SchemaError("集保股權分散沒有資料列")
    by, dates = {}, set()
    for r in body:
        if len(r) != 6:
            raise SchemaError(f"集保股權分散欄數不符：{r}")
        d, code, lv, n, s = (x.strip() for x in r[:5])
        dates.add(d)
        if lv in by.setdefault(code, {}):
            raise SchemaError(f"集保股權分散 {code} 第 {lv} 級重複")
        by[code][lv] = (n, s)
    if len(dates) != 1 or not re.fullmatch(r"\d{8}", min(dates)):
        raise SchemaError(f"集保股權分散資料日不符：{sorted(dates)[:3]}")
    d = min(dates)
    data_date = date(int(d[:4]), int(d[4:6]), int(d[6:]))
    rows, skipped = [], 0
    for code, lv in by.items():
        if set(lv) != set(LEVELS):
            raise SchemaError(f"集保股權分散 {code} 分級不符：{sorted(lv)}")
        if not (is_valid_stock_code(code) or is_etf_code(code)):
            continue                                    # 特別股、受益證券、TDR 等不收、不驗算
        n, s = [_count(lv[k][0]) for k in LEVELS], [_count(lv[k][1]) for k in LEVELS]
        if None in n or None in s or sum(n[:15]) != n[16] or sum(s[:15]) - s[15] != s[16] or s[16] <= 0:
            skipped += 1
            continue
        rows.append({"code": code, **dict(zip(N_COLS, n)), **dict(zip(S_COLS, s))})
    return data_date, rows, skipped


def collect_tdcc(latest, today: date) -> dict:
    """
    抓一次並寫入（官方資料日 > latest 才寫；latest = 表中最新資料日，None = 空表）。只寫 stocks、etfs 表已有的代號，一個 MERGE、同一個交易。
    回傳 undated.tdcc：{"on": 抓取日, "d": 官方資料日}，寫入新的一週時另有 s、e（實際寫入的股票、ETF 檔數）。
    """
    data_date, rows, skipped = parse_tdcc(request("GET", URL, expect_json=False, isolated=True).content.decode("utf-8-sig"))
    rec = {"on": str(today), "d": str(data_date)}
    if latest is not None and data_date <= latest:
        print(f"  ℹ️  集保股權分散：官方尚未更新（仍是 {data_date} 那週），明天再試")
        return rec
    out = []
    if rows:
        conn = db.connect()
        try:
            out = conn.cursor().execute(f"""
                MERGE share_distribution AS t
                USING (
                    SELECT j.*, CAST(CASE WHEN et.etf_id IS NULL THEN 0 ELSE 1 END AS BIT) AS is_etf
                    FROM OPENJSON(?) WITH (code NVARCHAR(10), {", ".join([f"{c} INT" for c in N_COLS] + [f"{c} BIGINT" for c in S_COLS])}) AS j
                    LEFT JOIN stocks st ON st.stock_code = j.code
                    LEFT JOIN etfs et ON et.etf_code = j.code
                    WHERE st.stock_id IS NOT NULL OR et.etf_id IS NOT NULL
                ) AS s
                ON t.code = s.code AND t.data_date = ?
                WHEN MATCHED THEN UPDATE SET is_etf = s.is_etf, {", ".join(f"{c} = s.{c}" for c in N_COLS + S_COLS)}, fetched_at = GETDATE()
                WHEN NOT MATCHED THEN
                    INSERT (code, is_etf, data_date, {", ".join(N_COLS + S_COLS)})
                    VALUES (s.code, s.is_etf, ?, {", ".join(f"s.{c}" for c in N_COLS + S_COLS)})
                OUTPUT inserted.is_etf;
            """, db.to_json(rows), data_date, data_date).fetchall()
            conn.commit()
        finally:
            conn.close()
    e = sum(1 for r in out if r[0])
    s = len(out) - e
    bad = skipped and not rows                          # QA43-03：全部略過 = 官方格式可能改變
    print(f"  {'⚠️' if bad else '🏦'} 集保股權分散 {data_date}：股票 {s:,} 檔、ETF {e:,} 檔" + (f"，略過 {skipped:,} 檔（合計不符）" if skipped else "") + ("，官方格式可能改變，請檢查" if bad else ""))
    return {**rec, "s": s, "e": e}
