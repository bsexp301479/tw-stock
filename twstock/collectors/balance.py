"""
資產負債表（第 52 輪 F52-1）：公開資訊觀測站舊版「資產負債表彙總」mopsov ajax_t163sb05。
一個回應 = 一個市場、一季、全部業別（115Q3 實測：上市 6 張表、上櫃 2 張表），金額為季底時點數字（新台幣仟元），每股參考淨值為元。
不辨識業別（業別看同季損益表）；資料庫照原樣存，「--」存 NULL；母公司權益是「--」時改用權益總計，在匯出時代換（export.bs_equity）。
"""
import re

from .. import db
from ..fetch import FetchError, SchemaError, clean_number, request
from .daily import PARSE_ERRORS
from .financials import TYPEK, _cells, _col

URL = "https://mopsov.twse.com.tw/mops/web/ajax_t163sb05"
# 欄名別名（取第一個存在的）：115Q3 實測金控、銀行用「總額」，母公司權益有 3 種寫法；個體報表公司的母公司權益是 --
COLS = (("total_assets", ("資產總計", "資產總額")),
        ("total_liab", ("負債總計", "負債總額")),
        ("parent_equity", ("歸屬於母公司業主之權益合計", "歸屬於母公司業主權益合計", "歸屬於母公司業主之權益")),
        ("total_equity", ("權益總計", "權益總額")),
        ("bvps", ("每股參考淨值",)))
NEED = ("total_assets", "total_liab", "total_equity", "bvps")      # 缺任一 → SchemaError；母公司權益整欄沒有 → NULL


def parse_balance(text: str) -> dict:
    """
    {代號: {total_assets, total_liab, parent_equity, total_equity, bvps}}（千元、元；「--」→ None）。
    表內只有標題列或還沒有任何公司公布 → {}；封鎖頁 → FetchError；缺公司代號、資產、負債、權益、每股參考淨值欄 → SchemaError（整個回應都不寫入）。
    """
    tables = re.findall(r"<table class='hasBorder'.*?</table>", text, re.S)
    if not tables:
        if re.search(r"<h2>(上市|上櫃)公司.*?資料</h2>", text) or "查無" in text:
            return {}                                       # 認得的頁面、還沒有公司公布
        if "SECURITY" in text.upper():
            raise FetchError("mopsov 回傳封鎖頁面（SECURITY）")
        raise SchemaError("mopsov 資產負債表彙總：回應沒有表格")
    out = {}
    for tb in tables:
        rows = re.findall(r"<tr.*?</tr>", tb, re.S)
        head = _cells(rows[0]) if rows else []
        idx = {h: i for i, h in enumerate(head)}
        col = {k: _col(idx, names) for k, names in COLS}
        if "公司代號" not in idx or any(col[k] is None for k in NEED):
            raise SchemaError(f"mopsov 資產負債表彙總：表頭不符（{'、'.join(head[:4])}…）")
        for tr in rows[1:]:
            c = _cells(tr)
            if len(c) != len(head) or c[0] == "公司代號":
                continue                                    # 分頁重複的表頭
            out[c[idx["公司代號"]]] = {k: None if i is None else clean_number(c[i], float if k == "bvps" else int) for k, i in col.items()}
    return out


def fetch_balance(market: str, year: int, quarter: int) -> dict:
    """year：西元年；quarter：1～4。參數同損益表（fetch_financials）。"""
    resp = request("POST", URL, expect_json=False, data={
        "encodeURIComponent": "1", "step": "1", "firstin": "1", "off": "1", "isQuery": "Y",
        "TYPEK": TYPEK[market], "year": str(year - 1911), "season": f"{quarter:02d}"})
    return parse_balance(resp.content.decode("utf-8", errors="replace"))


def merge_balance(cursor, year: int, quarter: int, rows: list, first_seen) -> int:
    """同 merge_financials：值不同才更新、記 updated_at；first_seen 只在新增時寫入；只寫入 stocks 已有的股票。回傳新增＋更正的列數。"""
    cursor.execute("""
        MERGE quarterly_balance AS t
        USING (
            SELECT st.stock_id, j.*
            FROM OPENJSON(?) WITH (
                stock_code NVARCHAR(10), total_assets BIGINT, total_liab BIGINT, parent_equity BIGINT,
                total_equity BIGINT, bvps DECIMAL(10,2)
            ) AS j
            JOIN stocks st ON st.stock_code = j.stock_code
        ) AS s
        ON t.stock_id = s.stock_id AND t.fin_year = ? AND t.fin_quarter = ?
        WHEN MATCHED AND EXISTS (SELECT s.total_assets, s.total_liab, s.parent_equity, s.total_equity, s.bvps
                                 EXCEPT SELECT t.total_assets, t.total_liab, t.parent_equity, t.total_equity, t.bvps)
            THEN UPDATE SET total_assets = s.total_assets, total_liab = s.total_liab, parent_equity = s.parent_equity,
                            total_equity = s.total_equity, bvps = s.bvps, updated_at = GETDATE()
        WHEN NOT MATCHED THEN
            INSERT (stock_id, fin_year, fin_quarter, total_assets, total_liab, parent_equity, total_equity, bvps, first_seen)
            VALUES (s.stock_id, ?, ?, s.total_assets, s.total_liab, s.parent_equity, s.total_equity, s.bvps, ?);
    """, db.to_json(rows), year, quarter, year, quarter, first_seen)
    return cursor.rowcount


def collect_balance(year: int, quarter: int, first_seen=None, markets=("TWSE", "TPEx")) -> int:
    """抓取並寫入一季（每個市場 1 個請求、各自 commit）；失敗往外丟（history --only balance 靠它停下）。回傳回應家數。"""
    total = 0
    for market in markets:
        got = fetch_balance(market, year, quarter)
        rows = [{"stock_code": c, **r} for c, r in got.items()]
        conn = db.connect()
        try:
            cur = conn.cursor()
            known = {r[0] for r in cur.execute("SELECT stock_code FROM stocks").fetchall()}
            skipped = sum(c not in known for c in got)
            changed = merge_balance(cur, year, quarter, rows, first_seen) if rows else 0
            conn.commit()
        finally:
            conn.close()
        print(f"    📑 {market} {year}Q{quarter} 資產負債表：回應 {len(got)} 家，新增或更正 {changed} 家" + (f"，略過 {skipped} 家" if skipped else ""))
        total += len(got)
    return total


def collect_balance_safe(year: int, quarter: int, first_seen=None, markets=("TWSE", "TPEx")) -> None:
    """附掛在 collect_financials（R91）：每個市場各自攔例外，只印 ⚠️，不往外丟、不影響損益表。"""
    first = lambda e: (str(e).splitlines() or [""])[0][:120]
    for market in markets:
        try:
            collect_balance(year, quarter, first_seen, (market,))
        except db.pyodbc.Error as e:
            print(f"    ⚠️  quarterly_balance 寫入失敗（請確認已執行 setup-db）：{first(e)}")
        except (FetchError, *PARSE_ERRORS) as e:
            print(f"    ⚠️  資產負債表 {market} {year}Q{quarter} 未寫入（損益表照常）：{first(e)}")
