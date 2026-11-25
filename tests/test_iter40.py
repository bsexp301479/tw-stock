"""第 40 輪（不連網、不連資料庫）：F40-1 除權除息預告表收集、F40-2 匯出 nx、F40-3 工具頁帶入與股利卡一行。
上市 TWT48U、上櫃 tpex_exright_prepost 的回應是 2026-11-21 分析師實測的原始回應節錄（欄位與內容不變，只留幾列）；標「假資料」的列不是官方資料。
收集流程沿用 test_iter03 的 World、env、run_world；有 node 時逐字取出 app.js、stock.js、tools.js 的程式執行（node 14 可跑）。
檢查函式都接受要檢查的函式或原始碼，test_contrast 把程式改壞後重跑，確認會失敗。"""
import contextlib
import hashlib
import inspect
import io
import json
import re
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
import test_iter03 as t3  # noqa: E402
import test_iter34 as T  # noqa: E402
from twstock import db, export, fetch, health, tradingcal  # noqa: E402
from twstock.collectors import catchup, notices  # noqa: E402
from twstock.fetch import SchemaError  # noqa: E402

D, TM, CLOSED = t3.D, t3.T, t3.CLOSED
SITE, HTML, TOOLS, APP, STK = T.SITE, T.HTML, T.TOOLS, T.APP, T.STK
TW_FIELDS = ["除權除息日期", "股票代號", "名稱", "除權息", "無償配股率", "現金增資配股率", "現金增資認購價", "現金股利", "詳細資料", "參考價<br>試算",
             "最近一次申報資料 季別/日期", "最近一次申報每股 (單位)淨值", "最近一次申報每股 (單位)盈餘"]
TW_ROWS = [  # TWT48U 節錄：待公告 ETF、ETF、受益證券、ETN、股票息、現增（認購價尚未公告）、現增、股票息
    ["115年12月02日", "00406A", "主動中信台灣收益", "息", "0.00000000", "0.00000000", "0.00000000", "<p style= text-align:center;>待公告實際收益分配金額</p>", "00406A,20261202", "", "", "0.00", ""],
    ["115年11月24日", "00901", "永豐智能車供應鏈", "息", "0.00000000", "0.00000000", "0.00000000", "7.00000000", "00901,20261124", ",7.00000000,0.00000000,0.00000000,0.00000000", "115年11月20日(https://mops.twse.com.tw/mops/web/t78sb35)", "32.64", "N/A"],
    ["115年11月19日", "01007T", "兆豐國泰R2", "息", "0.00000000", "0.00000000", "0.00000000", "0.21531300", "01007T,20261119", ",0.21531300,0.00000000,0.00000000,0.00000000", "115年11月20日(https://mops.twse.com.tw/mops/web/t112sb01_q5)", "23.70", "N/A"],
    ["115年12月03日", "020038", "元大ESG配息N", "息", "0.00000000", "0.00000000", "0.00000000", "0.49100000", "020038,20261203", ",0.49100000,0.00000000,0.00000000,0.00000000", "", "0.00", ""],
    ["115年12月03日", "1437", "勤益控", "息", "0.00000000", "0.00000000", "0.00000000", "0.62465200", "1437,20261203", ",0.62465200,0.00000000,0.00000000,0.00000000", "115年第3季(https://mops.twse.com.tw/mops/web/t163sb01)", "43.61", "2.87"],
    ["115年12月04日", "2345", "智邦", "權", "0.00000000", "0.01782156", "尚未公告", "0.00000000", "2345,20261204", "", "115年第3季(https://mops.twse.com.tw/mops/web/t163sb01)", "146.74", "58.09"],
    ["115年11月27日", "3706", "神達", "權", "0.00000000", "0.08219551", "52.00000000", "0.00000000", "3706,20261127", ",0.00000000,0.00000000,0.08219551,52.00000000", "115年第3季(https://mops.twse.com.tw/mops/web/t163sb01)", "53.84", "3.77"],
    ["115年11月24日", "6655", "科定", "息", "0.00000000", "0.00000000", "0.00000000", "2.60000000", "6655,20261124", ",2.60000000,0.00000000,0.00000000,0.00000000", "115年第3季(https://mops.twse.com.tw/mops/web/t163sb01)", "42.87", "4.26"]]
TWSE = {"stat": "OK", "title": "除權除息預告表", "fields": TW_FIELDS, "data": TW_ROWS}
_O = ("AllocatedForPublicUnderwriting", "SubscribedByEmployees", "SubscribedByExistingShareholders", "SubscribedProRataInThousandShares")


def _tp(d, code, name, kind, stock, sub, price, cash, other=("0", "0", "0", "0.00000000")):
    return {"ExRrightsExDividendDate": d, "SecuritiesCompanyCode": code, "CompanyName": name, "ExRrightsExDividend": kind, "StockDividendRatio": stock,
            "SubscriptionRatioToNewSharesIssued": sub, "SubscriptionPricePerShare": price, "CashDividend": cash, **dict(zip(_O, other))}


TPEX = [  # tpex_exright_prepost 節錄：現增、股票息（8 位小數）、債券 ETF 尚未公告、股票息、現增（認購價「註4」）、跨年
    _tp("1151111", "8390", "金益鼎", "除權", "0.00000000", "0.08323265", "62.00", "0.00000000", ("800000", "1200000", "6000000", "62.42448718")),
    _tp("1151112", "3680", "家登", "除息", "0.00000000", "0.00000000", "0.00", "9.91474560"),
    _tp("1151124", "00958B", "永豐ESG銀行債15+", "除息", "0.00000000", "0.00000000", "0.00", "尚未公告"),
    _tp("1151126", "6523", "達爾膚", "除息", "0.00000000", "0.00000000", "0.00", "4.00000000"),
    _tp("1151203", "6160", "欣技", "除權", "0.00000000", "0.16060945", "註4", "0.00000000", ("1100000", "1650000", "8250000", "120.45708866")),
    _tp("1160105", "5483", "中美晶", "除息", "0.00000000", "0.00000000", "0.00", "2.80000000")]
FAKE_TP = _tp("1151210", "8942", "假資料", "除權息", "0.05000000", "0.00000000", "0.00", "1.00000000")   # 假資料：這份快照沒有「除權息」與配股的樣本
Z = Decimal(0)


def N(code, d, kind, cash, stock=Z, sub=Z, price=None):
    return {"code": code, "ex_date": d, "event_type": kind, "cash_div": cash, "stock_ratio": stock, "sub_ratio": sub, "sub_price": price}


# ─── 解析（驗收 1～3）──────────────────────────────────────
def check_parse(parse=notices.parse_notices):
    bad = []
    want_tw = [N("00406A", D(12, 2), "息", None), N("00901", D(11, 24), "息", Decimal(7)), N("1437", D(12, 3), "息", Decimal("0.624652")),
               N("2345", D(12, 4), "權", Z, sub=Decimal("0.01782156")), N("3706", D(11, 27), "權", Z, sub=Decimal("0.08219551"), price=Decimal(52)),
               N("6655", D(11, 24), "息", Decimal("2.6"))]                                                   # 01007T 受益證券、020038 ETN 不收
    want_tp = [N("8390", D(11, 11), "權", Z, sub=Decimal("0.08323265"), price=Decimal(62)), N("3680", D(11, 12), "息", Decimal("9.9147456")),
               N("00958B", D(11, 24), "息", None), N("6523", D(11, 26), "息", Decimal(4)), N("6160", D(12, 3), "權", Z, sub=Decimal("0.16060945")),
               N("5483", date(2027, 1, 5), "息", Decimal("2.8")), N("8942", D(12, 10), "權息", Decimal(1), stock=Decimal("0.05"))]
    for got, want in ((parse("TWSE", TWSE), want_tw), (parse("TPEx", TPEX + [FAKE_TP]), want_tp)):
        if got != want:
            bad.append((got, want))
    if not bad and (parse("TPEx", TPEX)[2]["cash_div"] is not None or parse("TWSE", TWSE)[0]["cash_div"] is not None):
        bad.append("待公告要是 None")
    # 沒有資料 = 0 筆成功；欄位不符 = SchemaError
    for mk, data in (("TWSE", {"stat": "很抱歉，沒有符合條件的資料!"}), ("TWSE", {"stat": "沒有資料", "tables": []}), ("TWSE", dict(TWSE, data=[])), ("TPEx", [])):
        if parse(mk, data) != []:
            bad.append(("沒有資料", mk, data))
    for mk, data in (("TWSE", dict(TWSE, fields=TW_FIELDS[:7])), ("TPEx", [{"Date": "1151203"}]), ("TPEx", {"x": 1}), ("TWSE", [])):
        try:
            parse(mk, data)
            bad.append(("欄位不符", mk))
        except SchemaError:
            pass
    # 同鍵只留最後一筆；配股率解析不了 = 0；沒有現增時認購價 = None
    dup = parse("TPEx", [_tp("1151203", "6523", "x", "除息", "--", "0.00000000", "62.00", "3.00000000"), _tp("1151203", "6523", "x", "除息", "", "", "", "4.00000000")])
    if dup != [N("6523", D(12, 3), "息", Decimal(4))]:
        bad.append(("同鍵", dup))
    if parse("TPEx", [_tp("1151203", "6523", "x", "除息", "--", "0.00000000", "62.00", "3.00000000")])[0]["sub_price"] is not None:
        bad.append("sub_ratio = 0 時 sub_price 要是 None")
    if parse("TWSE", dict(TWSE, data=[["11512", "1437", "x", "息"] + ["0"] * 9, ["115年12月03日", "1437", "x", "減"] + ["0"] * 9])) != []:
        bad.append("日期、類型不明要略過")
    return bad


def test_parse():
    assert check_parse() == []


# ─── 寫入（驗收 4）──────────────────────────────────────────
class Conn:
    def __init__(self):
        self.sql = []

    def cursor(self):
        return self

    def execute(self, sql, *p):
        self.sql.append((sql, p))

    def commit(self):
        pass

    def close(self):
        pass


def check_write(collect=notices.collect_notices):
    bad, conns = [], []

    def connect():
        conns.append(Conn())
        return conns[-1]
    rows = notices.parse_notices("TWSE", TWSE) + [N("9999", D(12, 9), "息", Decimal("0.00000001"))]   # 假資料：最小單位
    buf = io.StringIO()
    with mock.patch.object(notices, "fetch_notices", lambda m: rows), mock.patch.object(db, "connect", connect), contextlib.redirect_stdout(buf):
        n = collect("TWSE", D(11, 23))
    if n != 7 or len(conns) != 1 or len(conns[0].sql) != 1:
        return ["筆數或連線次數", n, len(conns)]
    sql, p = conns[0].sql[0]
    upd = sql[sql.index("WHEN MATCHED"):sql.index("WHEN NOT MATCHED")]
    ins = sql[sql.index("WHEN NOT MATCHED"):]
    j = json.loads(p[0])
    if "first_seen" in upd or "last_seen = ?" not in upd or "first_seen, last_seen" not in ins or "DELETE" in sql.upper():
        bad.append("first_seen 只在新增時寫、更新 last_seen、不刪除")
    if "JOIN stocks st ON st.stock_code = j.code" not in sql or "JOIN etfs et ON et.etf_code = j.code" not in sql or \
            "WHERE st.stock_id IS NOT NULL OR et.etf_id IS NOT NULL" not in sql or "THEN 0 ELSE 1 END AS BIT) AS is_etf" not in sql:
        bad.append("只收 stocks、etfs 已有的代號，is_etf 由命中的表決定")
    if p[1:] != ("TWSE", D(11, 23), "TWSE", D(11, 23), D(11, 23)):
        bad.append(("參數", p[1:]))
    if j[-1]["cash_div"] != "0.00000001" or "E-" in p[0] or j[2]["cash_div"] != "0.62465200" or j[0]["cash_div"] is not None or j[2]["ex_date"] != "2026-12-03":
        bad.append(("JSON", p[0][:200]))
    if "📅 上市除權除息預告 7 筆（除權息日 2026-11-24 ～ 2026-12-09）" not in buf.getvalue():
        bad.append(buf.getvalue())
    conns.clear()
    with mock.patch.object(notices, "fetch_notices", lambda m: []), mock.patch.object(db, "connect", connect), contextlib.redirect_stdout(buf):
        if collect("TPEx", D(11, 23)) != 0 or conns:
            bad.append("0 筆不連資料庫")
    if "📅 上櫃除權除息預告 0 筆\n" not in buf.getvalue():
        bad.append("0 筆的輸出")
    return bad


def test_write():
    assert check_write() == []


# ─── 收集時機與失敗隔離（驗收 5～7）───────────────────────────
class NxWorld(t3.World):
    """預告表回真實節錄（其他端點同 test_iter03）。"""

    def http(self, method, url, timeout=30, params=None, data=None, json=None):
        if "TWT48U" in url and "TWT48U" not in self.down:
            self.requests.append(("/rwd/zh/exRight/TWT48U", params or {}))
            return t3.Resp(TWSE)
        if "tpex_exright_prepost" in url and "prepost" not in self.down:
            self.requests.append(("/openapi/v1/tpex_exright_prepost", params or {}))
            return t3.Resp(TPEX)
        return super().http(method, url, timeout, params, data, json)


def _nx_hits(w):
    return t3._hit(w, "TWT48U", "tpex_exright_prepost")


def check_timing():
    bad = []
    w = NxWorld(D(10, 30))
    w.publish(t3.FIRST_DAY)
    rc, out = t3.run_world(w, TM(11, 2, 18, 0))
    und = json.loads(w.runs[-1][2])["undated"]
    if rc != 0 or _nx_hits(w) != ["/rwd/zh/exRight/TWT48U", "/openapi/v1/tpex_exright_prepost"] or w.merges.count("dividend_notices") != 2:
        bad.append(("新交易日抓一次", rc, _nx_hits(w), w.merges.count("dividend_notices")))
    if [f for p, f in w.requests if "TWT48U" in p] != [{"response": "json"}]:
        bad.append("TWT48U 參數")
    if und.get("notices") != {"TWSE": {"on": "2026-11-02", "n": 6}, "TPEx": {"on": "2026-11-02", "n": 6}}:
        bad.append(("undated", und.get("notices")))
    if "📅 上市除權除息預告 6 筆（除權息日 2026-11-24 ～ 2026-12-04）" not in out or "📅 上櫃除權除息預告 6 筆（除權息日 2026-11-11 ～ 2027-01-05）" not in out:
        bad.append(out[-600:])
    w.requests.clear()
    t3.run_world(w, TM(11, 2, 18, 30))                                                    # 同一晚重跑
    if _nx_hits(w):
        bad.append("同一晚重跑")
    w = NxWorld(D(10, 30))
    t3.run_world(w, TM(10, 31, 18))                                                       # 週六（休市）
    if _nx_hits(w):
        bad.append("休市日")
    w = NxWorld(D(10, 30))
    w.publish(t3.FIRST_DAY)
    t3.run_world(w, TM(11, 2, 18, 0), date_=t3.FIRST_DAY)                                 # collect --date
    if _nx_hits(w) or not t3._hit(w, "TWT49U"):
        bad.append("collect --date 不抓預告（事件照抓）")
    p = catchup.make_plan(TM(11, 2, 18, 30), 10, t3._full_snapshot(health.due_days(TM(11, 2, 18, 30), 10, CLOSED)),
                          {"alerts_at": None, "events_to": D(11, 2), "revenue_on": None}, CLOSED, {})
    if p["notices"] or p["events"]:
        bad.append("make_plan：沒有排 events 就沒有 notices")
    p = catchup.make_plan(TM(11, 2, 18, 30), 10, t3._full_snapshot(health.due_days(TM(11, 2, 18, 30), 10, CLOSED)),
                          {"alerts_at": None, "events_to": D(10, 30), "revenue_on": None}, CLOSED, {})
    if p["notices"] is not True or not p["events"]:
        bad.append("make_plan：排了 events 就排 notices")
    return bad


def test_timing():
    assert check_timing() == []
    main = (ROOT / "twstock" / "__main__.py").read_text(encoding="utf-8") + (ROOT / "twstock" / "collectors" / "events.py").read_text(encoding="utf-8")
    assert "notice" not in main                                                           # cli events 不抓預告


def check_isolation():
    base = NxWorld(D(10, 30))
    base.publish(t3.FIRST_DAY)
    rc0, _ = t3.run_world(base, TM(11, 2, 18, 0))
    w = NxWorld(D(10, 30))
    w.publish(t3.FIRST_DAY)
    w.down.add("TWT48U")
    rc, out = t3.run_world(w, TM(11, 2, 18, 0))
    d, d0 = json.loads(w.runs[-1][2]), json.loads(base.runs[-1][2])
    bad = []
    if (rc, w.runs[-1][1], d["items"], w.notices, w.exports) != (rc0, base.runs[-1][1], d0["items"], base.notices, base.exports):
        bad.append(("回傳碼、結果、通知、匯出要和沒有失敗時相同", rc, rc0, w.notices))
    if len(t3._hit(w, "TWT48U")) != 1 or "www.twse.com.tw" in fetch._dead_hosts or "  ⚠️  notices.TWSE 失敗" not in out:
        bad.append(("只打一次、不標記主機", t3._hit(w, "TWT48U"), fetch._dead_hosts))
    if list(d["undated"].get("notices", {})) != ["TPEx"] or "notices.TWSE" not in d["errors"] or "❌ notices" in out:
        bad.append(("上櫃照抓、只記錄", d["undated"].get("notices")))
    return bad


def test_isolation():
    assert check_isolation() == []


def check_counts(fn=catchup._undated_counts):
    tables = []

    class Cur:
        def execute(self, sql):
            tables.append(sql.split()[-1])
            return self

        def fetchone(self):
            return (0,)
    fn(Cur())
    return [] if tables == ["stock_alerts", "price_events", "monthly_revenue", "quarterly_financials"] else [tables]   # D86-5：預告有變不觸發匯出


def test_counts():
    assert check_counts() == []


# ─── load_state、check（驗收 8、9）──────────────────────────────
class Rows:
    def __init__(self, rows):
        self.rows = rows

    def execute(self, *a):
        return self

    def fetchall(self):
        return self.rows


def check_state(fn=health.load_state):
    j = lambda **k: json.dumps(k)
    rows = [(datetime(2026, 11, 24, 22), 1, j(undated={"notices": {"TPEx": {"on": "2026-11-24", "n": 60}}}), "catch-up", "ok", 20.0),
            (datetime(2026, 11, 23, 22), 1, j(undated={"notices": {"TWSE": {"on": "2026-11-23", "n": 25}, "TPEx": {"on": "2026-11-23", "n": 66}}}), "catch-up", "ok", 20.0),
            (datetime(2026, 11, 20, 22), 1, j(undated={"events_to": "2026-11-20"}), "catch-up", "ok", 20.0)]
    got = [fn(Rows(r))["notices"] for r in (rows, rows[2:], [])]
    want = [{"TPEx": (D(11, 24), 60), "TWSE": (D(11, 23), 25)}, {}, {}]
    return [] if got == want else [got]


def test_state():
    assert check_state() == []


def check_lines(fn=health.check_report):
    now = TM(11, 25, 10)
    days = health.due_days(now, 20, CLOSED)
    td = tradingcal.trading_days(D(10, 1), days[-1], CLOSED)
    snap, bad = t3._full_snapshot(days), []
    base = {"alerts_at": datetime.combine(days[-1], datetime.min.time()).replace(hour=19), "events_to": days[-1]}
    cases = [({}, "除權除息預告最後成功：尚無執行紀錄"),
             ({"TWSE": (td[-1], 25), "TPEx": (td[-1], 1066)}, f"除權除息預告最後成功：上市 {td[-1]}（25 筆）、上櫃 {td[-1]}（1,066 筆）"),
             ({"TWSE": (td[-3], 25)}, f"除權除息預告最後成功：上市 {td[-3]}（25 筆）、上櫃 尚無紀錄"),                     # 2 個交易日：不提醒
             ({"TWSE": (td[-1], 25), "TPEx": (td[-4], 66)}, f"除權除息預告最後成功：上市 {td[-1]}（25 筆）、上櫃 {td[-4]}（66 筆，⚠️ 已 3 個交易日沒有更新）")]
    t0, rc0 = fn(days, snap, now, base, CLOSED)
    for nt, line in cases:
        text, rc = fn(days, snap, now, dict(base, notices=nt), CLOSED)
        L, L0 = text.splitlines(), t0.splitlines()
        i = L.index(line) if line in L else -1
        if i < 0 or rc != rc0 or not L[i - 1].startswith("除權息事件最後成功") or L[:i] + L[i + 1:] != [x for x in L0 if not x.startswith("除權除息預告")]:
            bad.append((nt, line, text))
    if "除權除息預告最後成功：尚無執行紀錄" not in fn(days, snap, now, {}, CLOSED)[0]:
        bad.append("state = {}")
    return bad


def test_lines():
    assert check_lines() == []


# ─── 匯出（驗收 10～12）──────────────────────────────────────
def _r(code, mk, etf, d, t, cash, stock="0", sub="0", price=None, seen=D(11, 23)):
    return (code, mk, int(etf), d, t, None if cash is None else Decimal(cash), Decimal(stock), Decimal(sub), None if price is None else Decimal(price), seen)


ROWS = [_r("1437", "TWSE", 0, D(12, 3), "息", "0.62465200"), _r("2543", "TWSE", 0, D(11, 23), "息", "0.50000000"),   # 除權息日 = 資料日：不匯出
        _r("2345", "TWSE", 0, D(12, 4), "權", "0.00000000", sub="0.01782156"), _r("3706", "TWSE", 0, D(11, 27), "權", "0E-8", sub="0.08219551", price="52.00"),
        _r("1817", "TWSE", 0, D(12, 21), "息", "1.80000000", seen=D(11, 20)), _r("1817", "TWSE", 0, D(12, 28), "息", "1.80000000"),   # 改日期
        _r("1707", "TWSE", 0, D(12, 30), "息", "1.90000000"), _r("1707", "TWSE", 0, D(12, 10), "息", "0.10000000"),
        _r("8942", "TPEx", 0, D(12, 10), "權息", "1.00000000", stock="0.05000000"), _r("6523", "TPEx", 0, D(11, 26), "息", "4.00000000"),
        _r("00406A", "TWSE", 1, D(12, 2), "息", None), _r("00901", "TWSE", 1, D(11, 24), "息", "7.00000000"), _r("00958B", "TPEx", 1, D(11, 24), "息", None)]


def check_export(fn=export.notice_export):
    bad, on = [], {"TWSE": D(11, 23), "TPEx": D(11, 23)}
    s, e = fn(ROWS, on, D(11, 23))
    want_s = {"1437": [{"d": "2026-12-03", "t": "息", "c": 0.624652}], "2345": [{"d": "2026-12-04", "t": "權", "c": 0, "sr": 0.01782156, "sp": None}],
              "3706": [{"d": "2026-11-27", "t": "權", "c": 0, "sr": 0.08219551, "sp": 52}], "1817": [{"d": "2026-12-28", "t": "息", "c": 1.8}],
              "1707": [{"d": "2026-12-10", "t": "息", "c": 0.1}, {"d": "2026-12-30", "t": "息", "c": 1.9}],
              "8942": [{"d": "2026-12-10", "t": "權息", "c": 1, "s": 50}], "6523": [{"d": "2026-11-26", "t": "息", "c": 4}]}
    want_e = {"00406A": [{"d": "2026-12-02", "t": "息", "c": None}], "00901": [{"d": "2026-11-24", "t": "息", "c": 7}], "00958B": [{"d": "2026-11-24", "t": "息", "c": None}]}
    if (s, e) != (want_s, want_e):
        bad.append(("全部成功", s, e))
    txt = json.dumps(s, ensure_ascii=False, separators=(",", ":"))
    if '"c":0.624652}' not in txt or '"c":4}' not in txt or '"s":50}' not in txt or "0000" in txt:
        bad.append(("去尾 0", txt))
    s, e = fn(ROWS, {"TWSE": D(11, 20), "TPEx": D(11, 23)}, D(11, 23))                    # 上市這晚失敗：沿用 11/20 的快照
    if set(s) != {"1817", "8942", "6523"} or s["1817"] != [{"d": "2026-12-21", "t": "息", "c": 1.8}] or set(e) != {"00958B"}:
        bad.append(("沿用上次快照", s, e))
    s, e = fn(ROWS, {"TWSE": D(11, 24)}, D(11, 23))                                       # 上市 11/24 成功但 0 筆、上櫃從沒成功
    if s or e:
        bad.append(("0 筆、沒有紀錄", s, e))
    s, _ = fn(ROWS, on, D(11, 27))
    if "3706" in s or "1437" not in s:
        bad.append("到了除權息日改看 dv")
    return bad


def test_export():
    assert check_export() == []


def test_export_wiring():
    src = (ROOT / "twstock" / "export.py").read_text(encoding="utf-8")
    assert 'state = load_state(cur)\n    status = build_status(cur, latest_date, now, state)' in src                  # 和 build_status 共用，不多查
    assert "FROM dividend_notices WHERE ex_date > ?\"\"\", latest_date).fetchall(), {m: d for m, (d, _) in state[\"notices\"].items()}, latest_date)" in src
    i = src.index('"dv": dividends(d_, c, ev, events.get(code, [])),      # 第 24 輪 F24-6')
    assert src.index('**({"nx": nx_stock[code]} if code in nx_stock else {}),') > i                                # 沒有 nx 不輸出鍵，舊檔不變
    assert "            _write(p, E)" in src and src.index('                E["nx"] = nx_etf[code]') < src.index("            _write(p, E)")
    assert hashlib.sha1(inspect.getsource(export.etf_export).encode()).hexdigest()[:12] == "711fa2b7790c"          # etf_export 一字不改
    status = health.build_status.__code__.co_varnames[:4]
    assert status == ("cur", "data_date", "now", "state")
    assert "dividend_notices" not in (ROOT / "twstock" / "collectors" / "catchup.py").read_text(encoding="utf-8")


def test_setup_db():
    ddl = "\n".join(db.DDL)
    for s in ("IF OBJECT_ID('dividend_notices') IS NULL", "CONSTRAINT UQ_dividend_notices UNIQUE (code, ex_date)", "cash_div     DECIMAL(16,8) NULL",
              "CHECK (event_type IN (N'息', N'權', N'權息'))", "first_seen   DATE          NOT NULL", "last_seen    DATE          NOT NULL"):
        assert s in ddl, s
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for s in ("dividend_notices", "test_iter40", "除權除息預告"):
        assert s in readme, s


# ─── 前端（驗收 13～17）──────────────────────────────────────
DAYS = ["2026-11-19", "2026-11-20"]
FIX = {
    "1437": {"name": "勤益控", "market": "TWSE", "prices": {"d": DAYS, "c": [43.0, 43.5]},
             "dv": [{"d": "2025-12-05", "t": "息", "c": 0.5, "p": 40.0, "r": 39.5}], "nx": [{"d": "2026-12-03", "t": "息", "c": 0.624652}]},
    "6523": {"name": "達爾膚", "market": "TPEx", "prices": {"d": DAYS, "c": [60.0, 61.0]}, "nx": [{"d": "2026-11-26", "t": "息", "c": 4}]},
    "3706": {"name": "神達", "market": "TWSE", "prices": {"d": DAYS, "c": [52.0, 53.0]},
             "dv": [{"d": "2026-07-01", "t": "息", "c": 2.0, "p": 55.0, "r": 53.0}], "nx": [{"d": "2026-11-27", "t": "權", "c": 0, "sr": 0.08219551, "sp": 52}]},
    "6655": {"name": "科定", "market": "TWSE", "prices": {"d": DAYS, "c": [80.0, 81.0]},
             "dv": [{"d": "2026-05-01", "t": "息", "c": 2.0, "p": 82.0}], "nx": [{"d": "2026-11-24", "t": "息", "c": 2.12345678}]},   # 假資料：8 位小數
    "8942": {"name": "森鉅", "market": "TPEx", "prices": {"d": DAYS, "c": [20.0, 20.5]}, "dv": [{"d": "2026-03-02", "t": "息", "c": 1.0, "p": 21.0}],
             "nx": [{"d": "2026-12-10", "t": "權息", "c": 1, "s": 50}]},                                                      # 假資料：配股
    "00901": {"name": "永豐智能車供應鏈", "market": "TWSE", "prices": {"d": DAYS, "c": [33.0, 33.2]}, "nx": [{"d": "2026-11-24", "t": "息", "c": 7}]},
    "00958B": {"name": "永豐ESG銀行債15+", "market": "TPEx", "prices": {"d": DAYS, "c": [9.0, 9.1]},
               "dv": [{"d": "2026-08-20", "t": "息", "c": 0.15, "p": 9.3, "r": 9.15}], "nx": [{"d": "2026-11-24", "t": "息", "c": None}]},
}
LATEST40 = {"date": "2026-11-20", "stocks": {k: {"n": v["name"]} for k, v in FIX.items() if not k.startswith("00")},
            "etfs": {"rows": {k: {"n": v["name"]} for k, v in FIX.items() if k.startswith("00")}}}
WANT = {   # 代號：帶入值、要出現的提示（依序）、TL.info.ex
    "1437": ({"c": "0.624652", "s": "0"}, ["已帶入 12/03 除息的預告股利（證交所預告表，僅供參考，以公司公告為準）", "上次官方參考價 39.5（12/05，前收 40）",
                                           "近一年現金股利 = 2025/11/20 以後 1 次合計"], "2026-12-03"),
    "6523": ({"c": "4", "s": "0", "mk": "o"}, ["已帶入 11/26 除息的預告股利（櫃買中心預告表，僅供參考，以公司公告為準）", "2026-11-19 起沒有除權息紀錄，請依公司公告填寫"], "2026-11-26"),
    "3706": ({"c": "2", "s": "0"}, ["已帶入 07/01 的股利（最近一次），下次請依公司公告修改", "11/27 除權含現金增資，參考價請看官方公告", "上次官方參考價 53"], "2026-11-27"),
    "6655": ({"c": "2", "s": "0"}, ["已帶入 05/01 的股利（最近一次），下次請依公司公告修改", "11/24 除息的預告現金股利 2.12345678 元超過 6 位小數，請依公告填寫"], "2026-11-24"),
    "8942": ({"c": "1", "s": "50", "mk": "o"}, ["已帶入 12/10 除權息的預告股利（櫃買中心預告表，僅供參考，以公司公告為準）", "近一年現金股利 = 2025/11/20 以後 1 次合計"], "2026-12-10"),
    "00901": ({"c": "7", "s": "0", "k": "e"}, ["已帶入 11/24 除息的預告股利（證交所預告表，僅供參考，以發行人公告為準）", "2026-11-19 起沒有除權息紀錄"], "2026-11-24"),
    "00958B": ({"c": "0.15", "k": "e", "mk": "o"}, ["已帶入 08/20 的股利（最近一次），下次請依發行人公告修改", "11/24 除息，金額待公告", "上次官方參考價 9.15"], "2026-11-24"),
}


def check_load(src=TOOLS):
    js = """
const view = { innerHTML: '' }, els = {};
const $ = s => s === '#view' ? view : (els[s] = els[s] || { innerHTML: '', classList: { add() {} }, addEventListener(t, f) { this[t] = f; } });
const history = { replaceState() {} }, localStore = (k, f) => f, FIX = %s;
const loadStock = async c => JSON.parse(JSON.stringify(FIX[c]));
(async () => {
  const r = {};
  for (const c of Object.keys(FIX)) { await window.renderTools('dv?c=' + c); const dv = view.innerHTML; await window.renderTools('dt?c=' + c);
    r[c] = { html: dv, dt: view.innerHTML, dv: Object.assign({}, TL.dv), ex: TL.info.ex }; }
  console.log(JSON.stringify(r));
})();""" % json.dumps(FIX, ensure_ascii=False)
    o = T._node(T.HELPERS + "\nconst window = {};\nconst App = { latest: %s, stockCache: {} };\n" % json.dumps(LATEST40, ensure_ascii=False) + src + "\n" + js)
    if o is None:
        return []
    bad = []
    for c, (st, hs, ex) in WANT.items():
        x = o[c]
        bad += [(c, k, x["dv"][k]) for k, v in st.items() if x["dv"][k] != v]
        pos = [x["html"].find(h) for h in hs]
        if -1 in pos or pos != sorted(pos):
            bad.append((c, hs, pos))
        if x.get("ex") != ex or f"{ex[5:7]}/{ex[8:]} 除權息，參考價另計" not in x["dt"]:
            bad.append((c, "ex", x.get("ex")))
        if re.search(r"NaN|undefined|Infinity", x["html"] + x["dt"]):
            bad.append((c, "畫面"))
    return bad


def test_load():
    assert check_load() == []


CARD = [({"d": "2026-12-03", "t": "息", "c": 0.624652}, False, "即將除息 12/03：現金股利 0.624652 元（預告，以公司公告為準）"),
        ({"d": "2026-11-24", "t": "息", "c": 7}, True, "即將除息 11/24：配息 7 元（預告，以發行人公告為準）"),
        ({"d": "2026-12-02", "t": "息", "c": None}, True, "即將除息 12/02：金額待公告（預告，以發行人公告為準）"),
        ({"d": "2026-11-27", "t": "權", "c": 0, "sr": 0.08219551, "sp": 52}, False, "即將除權 11/27：含現金增資，認購價 52 元（預告，以公司公告為準）"),
        ({"d": "2026-12-03", "t": "權", "c": 0, "sr": 0.16060945, "sp": None}, False, "即將除權 12/03：含現金增資，認購價尚未公告（預告，以公司公告為準）"),
        ({"d": "2026-12-10", "t": "權息", "c": 1, "s": 50}, False, "即將除權息 12/10：現金股利 1 元、每千股配股 50 股（預告，以公司公告為準）"),
        ({"d": "2026-12-09", "t": "息", "c": 1e-8}, False, "即將除息 12/09：現金股利 0.00000001 元（預告，以公司公告為準）")]   # 不出現科學記號


def check_card(src=STK):
    js = T.HELPERS + "\n" + "\n".join(T._grab(src, n) for n in ("dfmt", "nxText")) + "\nconsole.log(JSON.stringify(%s.map(([n, e]) => nxText(n, e))));" % \
        json.dumps([[n, e] for n, e, _ in CARD], ensure_ascii=False)
    o = T._node(js)
    if o is None:
        return []
    bad = [(w, g) for (_, _, w), g in zip(CARD, o) if g != w]
    line = next((x for x in src.splitlines() if "dv-nx" in x), "")
    dom = """
const h = { parentElement: { html: '', insertAdjacentHTML(p, s) { this.html += p + s; } } }, code = '1437';
for (const [E, data] of [[null, { nx: [%s] }], [{}, { nx: [%s] }], [null, {}]]) { const dvh = h;
%s
}
console.log(JSON.stringify(h.parentElement.html));""" % (json.dumps(CARD[0][0]), json.dumps(CARD[2][0]), line)
    o = T._node(T.HELPERS + "\n" + "\n".join(T._grab(src, n) for n in ("dfmt", "nxText")) + dom)
    if o != 'afterend<div class="small dv-nx">%s</div>afterend<div class="small dv-nx">%s</div>' % (CARD[0][2], CARD[2][2]):
        bad.append(("DOM", o))
    return bad


def test_card():
    assert check_card() == []
    i = STK.index("if (dvh) dvh.insertAdjacentHTML('afterend', `<span class=\"sp\"></span><a class=\"small dv-go\"")
    j = STK.index("if (dvh && data.nx) dvh.parentElement.insertAdjacentHTML('afterend'")
    assert STK.index("const dvh = [...document.querySelectorAll") < i < j < STK.index("onSeg('stockTabSeg'")          # 第 39 輪的兩行不動、接在後面
    assert hashlib.sha1(T._grab(STK, "divHTML").encode()).hexdigest()[:12] == "ce48816af767"                     # 卡片字面不變


def test_wiring_and_words():
    for f in ("tools.js", "app.js", "stock.js", "app.css"):
        v = hashlib.sha1((SITE / f).read_bytes()).hexdigest()[:8]
        assert f'{f}?v={v}"' in HTML, f"site/index.html 的 {f}?v= 請改成 {v}"
    seg = "".join(T._grab(TOOLS, n) for n in ("tlNx", "tlDvLoad", "tlLoad")) + T._grab(STK, "nxText")
    for w in (".at(", "??", "?.", "||=", "&&=", "replaceAll", "structuredClone", "Object.hasOwn", "findLast", "parseFloat("):
        assert w not in seg, w                                                                                    # node 14、不用浮點解析
    src = seg + inspect.getsource(notices) + "".join(w for _, _, w in CARD) + "".join(h for _, hs, _ in WANT.values() for h in hs)
    for w in ("買進", "賣出", "反彈", "見底", "買點", "超賣", "超買", "推薦", "強勢股", "飆股", "勝率", "保證", "穩賺", "建議", "搶息", "參加除息", "值得",
              "划算", "高息", "必填息", "確定配發"):
        assert w not in src, w


# ─── 反證（驗收 19）：改壞後上面的檢查要失敗 ─────────────────────
@contextlib.contextmanager
def _mutate(mod, name, a, b):
    """把 mod.name 函式的原始碼換掉一段後在 mod 的命名空間重新定義（流程測試會用到），結束時換回原函式。"""
    fn = getattr(mod, name)
    src = inspect.getsource(fn)
    assert src.count(a) == 1, (name, a)
    exec(compile(src.replace(a, b), mod.__file__, "exec"), mod.__dict__)
    try:
        yield getattr(mod, name)
    finally:
        setattr(mod, name, fn)


PY_MUTANTS = [
    ("匯出不比 last_seen", export, "notice_export", " or seen != on[market]", "", lambda f: check_export(f)),
    ("配股率不乘 1,000", export, "notice_export", "_num(ratio * 1000)", "_num(ratio)", lambda f: check_export(f)),
    ("除權息日 = 資料日也匯出", export, "notice_export", "if d <= today", "if d < today", lambda f: check_export(f)),
    ("待公告存成 0", notices, "parse_notices", '"cash_div": num(3),', '"cash_div": num(3) or Decimal(0),', lambda f: check_parse(f)),
    ("認購價不看現增", notices, "parse_notices", '"sub_price": num(6) if sub else None', '"sub_price": num(6)', lambda f: check_parse(f)),
    ("MERGE 更新 first_seen", notices, "collect_notices", "sub_price = s.sub_price, last_seen = ?", "sub_price = s.sub_price, first_seen = ?, last_seen = ?",
     lambda f: check_write(f)),
    ("不是 isolated", notices, "fetch_notices", "isolated=True", "isolated=False", lambda f: check_isolation()),
    ("notices 失敗算異常", catchup, "_run_locked", '("alerts", "events", "revenue", "financials", "industry", "chains")',
     '("alerts", "events", "revenue", "financials", "industry", "chains", "notices.TWSE")', lambda f: check_isolation()),
    ("_undated_counts 加入新表", catchup, "_undated_counts", '"quarterly_financials")', '"quarterly_financials", "dividend_notices")', lambda f: check_counts(f)),
    ("每次都排預告", catchup, "make_plan", '"financials": None, "notices": False}', '"financials": None, "notices": True}', lambda f: check_timing()),
    ("collect --date 也抓", catchup, "execute_plan", 'if plan.get("notices")', 'if plan.get("events")', lambda f: check_timing()),
    ("load_state 取最舊", health, "load_state", 'state["notices"].setdefault(mk, (date.fromisoformat(v["on"]), v["n"]))',
     'state["notices"][mk] = (date.fromisoformat(v["on"]), v["n"])', lambda f: check_state(f)),
    ("過期門檻 2 個交易日", health, "notices_line", "if lag >= 3", "if lag >= 2", lambda f: check_lines()),
]
JS_MUTANTS = [
    ("現增也帶入", TOOLS, "  if (n.sr) return [false,", "  if (0) return [false,", check_load),
    ("待公告也帶入", TOOLS, "  if (n.c == null) return [false,", "  if (0) return [false,", check_load),
    ("超過 6 位也帶入", TOOLS, "tlBig(String(n.c), 6) === null", "tlBig(String(n.c), 8) === null", check_load),
    ("ETF 也寫公司", TOOLS, "以${e ? '發行人' : '公司'}公告為準", "以公司公告為準", check_load),
    ("ex 不看 nx", TOOLS, "ex: d.nx ? d.nx[0].d : (d.dv", "ex: (d.dv", check_load),
    ("卡片 ETF 也寫公司", STK, "（預告，以${etf ? '發行人' : '公司'}公告為準）", "（預告，以公司公告為準）", check_card),
    ("卡片四捨五入到 2 位", STK, "dfmt(n.c, 8)", "dfmt(n.c, 2)", check_card),
]


def test_contrast():
    for name, mod, fn, a, b, check in PY_MUTANTS:
        with _mutate(mod, fn, a, b) as f, contextlib.redirect_stdout(io.StringIO()):
            try:
                fails = check(f)
            except Exception as e:                                                                             # 改壞到執行失敗也算擋下
                fails = [repr(e)]
        assert fails, "反證沒有擋下：" + name
    if T._node("console.log('1')") is None:
        return
    for name, src, a, b, check in JS_MUTANTS:
        assert src.count(a) == 1, (name, a)
        assert check(src.replace(a, b)), "反證沒有擋下：" + name


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_") and callable(f):
            print("==", n); f()
    print("全部通過")
