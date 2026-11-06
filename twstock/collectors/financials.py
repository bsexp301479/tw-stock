"""
季報（第 10 輪 B5）：公開資訊觀測站舊版「綜合損益表彙總」mopsov ajax_t163sb04。
一個回應 = 一個市場、一季、全部業別（一般業、金控、銀行、證券、保險、其他各一張表），金額為「年初至今累計」（千元）。
資料庫只存累計值；單季值在匯出時相減（export.fin_single），公司更正累計值時不會留下不一致。
"""
import html
import re

from .. import db
from ..fetch import FetchError, SchemaError, clean_number, request

URL = "https://mopsov.twse.com.tw/mops/web/ajax_t163sb04"
TYPEK = {"TWSE": "sii", "TPEx": "otc"}
# 業別表：依表頭特徵辨識（不依賴表的順序），由上往下取第一個符合的
TABLES = (("ci", ("營業毛利（毛損）淨額",)),                 # 一般業
          ("fh", ("淨收益",)),                              # 金控（也有利息淨收益，所以排在銀行之前）
          ("basi", ("利息淨收益",)),                         # 銀行
          ("bd", ("收益", "支出及費用")),                     # 證券
          ("ins", ("繼續營業單位稅前純益（純損）",)),          # 保險（113 年有營業收入、115 年 IFRS 17 後沒有）
          ("mim", ("收入", "支出")))                          # 其他
FIN_TBLS = ("fh", "basi", "bd", "ins")                       # 金融業：沒有毛利；提前結束收集要等金融業齊
REVENUE = ("營業收入", "淨收益", "收益", "收入")             # 第一個存在的欄；銀行沒有合計欄、115 年起保險沒有收入欄 → NULL
OP_INCOME = ("營業利益（損失）", "營業利益")                 # 證券、保險、一般業才有
GROSS = "營業毛利（毛損）淨額"
# 沒有子公司（個體報表）的公司「淨利歸屬於母公司業主」是 --，本期淨利就是歸屬於母公司的淨利（115Q2 上市 74 家）
NET_ALONE = ("本期淨利（淨損）", "本期稅後淨利（淨損）")


def _cells(tr: str) -> list:
    return [html.unescape(re.sub(r"<[^>]+>", "", c)).replace("\xa0", "").strip()
            for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", tr, re.S)]


def _col(idx: dict, names) -> int | None:
    return next((idx[n] for n in names if n in idx), None)


def parse_financials(text: str) -> dict:
    """
    {代號: {industry_tbl, revenue, gross_profit, op_income, net_income, eps}}（千元、元）。
    表內只有標題列或還沒有任何公司公布 → {}；封鎖頁 → FetchError；
    認不出業別、缺公司代號／基本每股盈餘／淨利歸屬於母公司業主欄 → SchemaError（整個回應都不寫入）。
    """
    tables = re.findall(r"<table class='hasBorder'.*?</table>", text, re.S)
    if not tables:
        if re.search(r"<h2>(上市|上櫃)公司.*?資料</h2>", text) or "查無" in text:
            return {}                                       # 認得的頁面、還沒有公司公布
        if "SECURITY" in text.upper():
            raise FetchError("mopsov 回傳安全性封鎖頁面")
        raise SchemaError("mopsov 綜合損益表彙總：回應沒有表格")
    out = {}
    for tb in tables:
        rows = re.findall(r"<tr.*?</tr>", tb, re.S)
        head = _cells(rows[0]) if rows else []
        idx = {h: i for i, h in enumerate(head)}
        tbl = next((t for t, need in TABLES if all(n in idx for n in need)), None)
        eps = next((i for h, i in idx.items() if h.startswith("基本每股盈餘")), None)     # 保險業沒有「（元）」
        ni = next((i for h, i in idx.items() if h.startswith("淨利") and h.endswith("歸屬於母公司業主")), None)
        if tbl is None or "公司代號" not in idx or eps is None or ni is None:
            raise SchemaError(f"mopsov 綜合損益表彙總：表頭不符（{'、'.join(head[:4])}…）")
        rev, op, gp, alone = _col(idx, REVENUE), _col(idx, OP_INCOME), idx.get(GROSS), _col(idx, NET_ALONE)
        num = lambda c, i: clean_number(c[i], int) if i is not None else None
        for tr in rows[1:]:
            c = _cells(tr)
            if len(c) != len(head) or c[0] == "公司代號":
                continue                                    # 分頁重複的表頭
            out[c[idx["公司代號"]]] = {"industry_tbl": tbl, "revenue": num(c, rev), "gross_profit": num(c, gp),
                                       "op_income": num(c, op), "net_income": num(c, ni) if num(c, ni) is not None else num(c, alone),
                                       "eps": clean_number(c[eps])}
    return out


def fetch_financials(market: str, year: int, quarter: int) -> dict:
    """year：西元年；quarter：1～4（4 = 全年）。"""
    resp = request("POST", URL, expect_json=False, data={
        "encodeURIComponent": "1", "step": "1", "firstin": "1", "off": "1", "isQuery": "Y",
        "TYPEK": TYPEK[market], "year": str(year - 1911), "season": f"{quarter:02d}"})
    return parse_financials(resp.content.decode("utf-8", errors="replace"))


def merge_financials(cursor, year: int, quarter: int, rows: list, first_seen) -> int:
    """
    MERGE 覆寫（更正財報）；只有值不同才更新、記 updated_at。first_seen 只在新增時寫入（補抓為 NULL），更新時不動。
    只寫入 stocks 已有的股票（JOIN）。回傳新增＋更正的列數。
    """
    cursor.execute("""
        MERGE quarterly_financials AS t
        USING (
            SELECT st.stock_id, j.*
            FROM OPENJSON(?) WITH (
                stock_code NVARCHAR(10), industry_tbl NVARCHAR(10), revenue BIGINT, gross_profit BIGINT,
                op_income BIGINT, net_income BIGINT, eps DECIMAL(10,2)
            ) AS j
            JOIN stocks st ON st.stock_code = j.stock_code
        ) AS s
        ON t.stock_id = s.stock_id AND t.fin_year = ? AND t.fin_quarter = ?
        WHEN MATCHED AND EXISTS (SELECT s.industry_tbl, s.revenue, s.gross_profit, s.op_income, s.net_income, s.eps
                                 EXCEPT SELECT t.industry_tbl, t.revenue, t.gross_profit, t.op_income, t.net_income, t.eps)
            THEN UPDATE SET industry_tbl = s.industry_tbl, revenue = s.revenue, gross_profit = s.gross_profit,
                            op_income = s.op_income, net_income = s.net_income, eps = s.eps, updated_at = GETDATE()
        WHEN NOT MATCHED THEN
            INSERT (stock_id, fin_year, fin_quarter, industry_tbl, revenue, gross_profit, op_income, net_income, eps, first_seen)
            VALUES (s.stock_id, ?, ?, s.industry_tbl, s.revenue, s.gross_profit, s.op_income, s.net_income, s.eps, ?);
    """, db.to_json(rows), year, quarter, year, quarter, first_seen)
    return cursor.rowcount


def collect_financials(year: int, quarter: int, first_seen=None, markets=("TWSE", "TPEx")) -> int:
    """
    抓取並寫入一季（每個市場 1 個請求）。first_seen：日常收集傳今天、補抓傳 None。
    回傳回應家數（含 stocks 沒有的公司；0 = 還沒有公司公布，不是錯誤）。
    """
    total = 0
    for market in markets:
        got = fetch_financials(market, year, quarter)
        rows = [{"stock_code": c, **r} for c, r in got.items()]
        conn = db.connect()
        try:
            cur = conn.cursor()
            known = {r[0] for r in cur.execute("SELECT stock_code FROM stocks").fetchall()}
            skipped = sorted(c for c in got if c not in known)
            changed = merge_financials(cur, year, quarter, rows, first_seen) if rows else 0
            conn.commit()
        finally:
            conn.close()
        print(f"    📑 {market} {year}Q{quarter}：回應 {len(got)} 家，新增或更正 {changed} 家"
              + (f"，略過 {len(skipped)} 家（stocks 沒有：{'、'.join(skipped[:5])}{'…' if len(skipped) > 5 else ''}）" if skipped else ""))
        total += len(got)
    return total
