"""第 53 輪（不連網、不連資料庫）：重大訊息（F53-1～F53-7）。
解析用 tests/fixtures/t187ap04_L_mini.json、mopsfin_t187ap04_O_mini.json（SA 2026-11-28 實測原始回應只刪列，「說明」值改成空字串）；
收集以 test_iter03 的假世界執行（只有 HTTP 與資料庫是假的）；check、匯出測純函式；畫面取出 stock.js、app.js 的函式在 node 執行（node 14 可跑）。
檢查函式都接受原始碼字串，最後的 test_contrast 把原始碼改壞（反證），確認對應的檢查會失敗。

  python3 tests/test_iter53.py
"""
import contextlib
import hashlib
import io
import json
import re
import sys
from datetime import date, time
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
from twstock import db, export, fetch, health  # noqa: E402
from twstock.collectors import catchup, news  # noqa: E402
from twstock.fetch import SchemaError  # noqa: E402
import test_iter03 as t3  # noqa: E402
import test_iter40 as t40  # noqa: E402
import test_iter52 as T52  # noqa: E402

D, TM, CLOSED = t3.D, t3.T, t3.CLOSED
SITE, HTML, APP, STK = T52.SITE, T52.HTML, T52.APP, T52.STK
FIX = ROOT / "tests" / "fixtures"
SRC = lambda p: (ROOT / p).read_text(encoding="utf-8")
NEWS, CAT, HEA, EXP, DBS, README = (SRC(p) for p in ("twstock/collectors/news.py", "twstock/collectors/catchup.py", "twstock/health.py",
                                                     "twstock/export.py", "twstock/db.py", "README.md"))
ADVICE = T52.ADVICE | {"利多", "利空"}
_grab, _grab_py, _fn, _fns, _node, _raises, _mut = T52._grab, T52._grab_py, T52._fn, T52._fns, T52._node, T52._raises, T52._mut
L_RAW = json.loads((FIX / "t187ap04_L_mini.json").read_text(encoding="utf-8"))
O_RAW = json.loads((FIX / "mopsfin_t187ap04_O_mini.json").read_text(encoding="utf-8"))
NEWS_FNS = ("_time", "parse_news", "fetch_news", "collect_news")
ONE = {"出表日期": "1151128", "發言日期": "1151127", "發言時間": "153000", "公司代號": "2330", "公司名稱": "台積電", "主旨 ": "公告本公司董事會決議",
       "符合條款": "第12款", "事實發生日": "1151127", "說明": ""}


def _parse(src=NEWS):
    return _fns(news, src, NEWS_FNS)[1]


# ─── 解析（驗收 3～9）────────────────────────────────────────
def check_fixture(src=NEWS):
    parse = _parse(src)
    (ol, rl, kl), (oo, ro, ko) = parse("TWSE", L_RAW), parse("TPEx", O_RAW)
    keys = {"code", "name", "speak_date", "speak_time", "subject", "clause", "fact_date"}
    first = rl[0]
    return (ol == D(11, 28) and len(rl) == 8 and kl == 0 and oo == D(11, 27) and len(ro) == 8 and ko == 0
            and all(set(r) == keys for r in rl + ro) and "主旨 " in L_RAW[0] and "主旨" in O_RAW[0]
            and first == {"code": "7855", "name": L_RAW[0]["公司名稱"], "speak_date": D(11, 27), "speak_time": time(9, 20, 41),
                          "subject": L_RAW[0]["主旨 "], "clause": L_RAW[0]["符合條款"], "fact_date": D(12, 1)}
            and ro[0]["speak_time"] == time(7, 0, 3) and ro[0]["speak_date"] == D(11, 26) and ro[0]["code"] == "3489"
            and [r["code"] for r in rl].count("8499") == 3 and all(x["說明"] == "" for x in L_RAW + O_RAW))


def test_fixture():
    assert check_fixture()


def check_fields(src=NEWS):
    parse = _parse(src)
    row = lambda **k: [{**ONE, **k}]
    ren = lambda old, new: [{(new if k == old else k): v for k, v in ONE.items()}]
    drop = lambda *ks: [{k: v for k, v in ONE.items() if k not in ks}]
    t = lambda s: parse("TWSE", row(發言時間=s))
    ok_t = [t(s)[1][0]["speak_time"] for s in ("70004", "4", "153000", "07:00:04")]
    bad_t = [t(s)[1:] for s in ("250000", "076000", "abc", "")]
    fd = lambda s: parse("TWSE", row(事實發生日=s))[1][0]["fact_date"]
    o, r, k = parse("TWSE", drop("公司名稱", "符合條款", "事實發生日"))
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        o2, _, _ = parse("TWSE", row() + row(出表日期="1151127", 發言時間="070000"))
    return (ok_t == [time(7, 0, 4), time(0, 0, 4), time(15, 30), time(7, 0, 4)] and all(x == ([], 1) for x in bad_t)
            and parse("TWSE", row(發言日期="115/11/24"))[1][0]["speak_date"] == D(11, 24) and parse("TWSE", row(發言日期="x"))[1:] == ([], 1)
            and fd("1201123") is None and fd("") is None and fd("1151123") == D(11, 23)
            and all(_raises(lambda: parse("TWSE", ren(a, a + "x")), SchemaError) for a in ("公司代號", "發言日期", "發言時間", "主旨 ", "出表日期"))
            and o == D(11, 28) and len(r) == 1 and (r[0]["name"], r[0]["clause"], r[0]["fact_date"]) == (None, None, None)
            and parse("TPEx", [{"Date": "1151127", "發言日期": "1151126", "發言時間": "70003", "SecuritiesCompanyCode": "6488", "CompanyName": "環球晶",
                                "主旨": "x"}])[1][0]["code"] == "6488"
            and _raises(lambda: parse("TWSE", {"a": 1}), SchemaError) and parse("TWSE", []) == (None, [], 0)
            and _raises(lambda: parse("TWSE", ["x"]), SchemaError) and _raises(lambda: parse("TWSE", row(出表日期="")), SchemaError)
            and o2 == D(11, 28) and buf.getvalue() == "  ⚠️  上市重大訊息的出表日期不一致（2026-11-27 ～ 2026-11-28），以最晚的為準\n")


def test_fields():
    assert check_fields()


def check_dedup(src=NEWS):
    parse = _parse(src)
    a = {**ONE, "主旨 ": "ABC 公告", "公司名稱": "舊"}
    _, r, _ = parse("TWSE", [a, {**a, "公司名稱": "中"}, {**a, "主旨 ": "ａｂｃ 公告", "公司名稱": "新"}, {**a, "主旨 ": "另一則"}, ["x"]])
    _, r2, k2 = parse("TWSE", [{**ONE, "主旨 ": "字" * 401}, {**ONE, "公司代號": " "}, {**ONE, "公司代號": "1" * 11},
                               {**ONE, "公司名稱": "名" * 41}])
    return ([x["subject"] for x in r] == ["ａｂｃ 公告", "另一則"] and r[0]["name"] == "新" and len(r2) == 1 and k2 == 3 and r2[0]["name"] is None)


def test_dedup():
    assert check_dedup()


# ─── 抓取、MERGE、DDL（驗收 10～12）─────────────────────────────
class NCur:
    def __init__(self, log, result=None, err=None):
        self.log, self.result, self.err = log, result, err

    def cursor(self):
        return self

    def execute(self, s, *p):
        if self.err:
            raise self.err
        self.log.append((s, p))
        return self

    def fetchall(self):
        return self.result

    def commit(self):
        self.log.append("commit")

    def close(self):
        pass


def _collect(src=NEWS, data=L_RAW, result=None, err=None):
    log, out, calls = [], io.StringIO(), []
    req = lambda *a, **k: (calls.append((a, k)), data)[1]
    _, _, _, collect = _fns(news, src, NEWS_FNS)
    with mock.patch.dict(collect.__globals__, {"request": req}), mock.patch.object(db, "connect", lambda: NCur(log, result, err)), \
            contextlib.redirect_stdout(out):
        try:
            r = collect("TWSE", D(11, 28))
        except Exception as e:
            r = e
    return r, log, out.getvalue(), calls


def check_collect(src=NEWS):
    r, log, out, calls = _collect(src, result=[("INSERT",)] * 8)
    s, p = log[0]
    upd = s[s.index("THEN UPDATE"):s.index("WHEN NOT MATCHED")]
    r2, _, out2, _ = _collect(src, result=[("UPDATE",)] * 8)
    r3, log3, out3, _ = _collect(src, data=[])
    r4, _, _, _ = _collect(src, err=db.pyodbc.Error("42S02", "[42S02] Invalid object name 'material_news'."))
    j = json.loads(p[0])
    return (r == {"on": "2026-11-28", "t": "2026-11-28", "d": "2026-11-27", "n": 8, "new": 8} and log[1] == "commit"
            and out == "  📰 上市重大訊息 8 筆（出表 2026-11-28，發言日 2026-11-27，新增 8 筆）\n"
            and "MERGE material_news" in s and "OUTPUT $action" in s and "first_seen" not in upd
            and "ON t.market = ? AND t.code = s.code AND t.speak_date = s.speak_date AND t.speak_time = s.speak_time AND t.subject = s.subject" in s
            and p[1:] == ("TWSE", D(11, 28), "TWSE", D(11, 28), D(11, 28)) and j[0]["speak_time"] == "09:20:41" and "說明" not in s and all(set(x) == {"code", "name", "speak_date", "speak_time", "subject", "clause", "fact_date"} for x in j)
            and "description" not in s and r2["new"] == 0 and r3 is None and log3 == []
            and out3 == "  📰 上市重大訊息：官方目前沒有資料（0 筆），下次執行再抓\n"
            and isinstance(r4, RuntimeError) and str(r4) == "material_news 寫入失敗（請確認已執行 setup-db）：('42S02', \"[42S02] Invalid object name 'material_news'.\")"
            and calls == [(("GET", "https://openapi.twse.com.tw/v1/opendata/t187ap04_L"), {"isolated": True})])


def test_collect():
    assert check_collect()
    calls = []
    with mock.patch.object(news, "request", lambda *a, **k: (calls.append((a, k)), [])[1]):
        news.fetch_news("TPEx")
    assert calls == [(("GET", "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap04_O"), {"isolated": True})]
    ddl = "\n".join(db.DDL)
    blk = next(d for d in db.DDL if "material_news" in d)
    for s in ("CREATE TABLE material_news (", "market      NVARCHAR(4)    NOT NULL CHECK (market IN ('TWSE','TPEx')),", "speak_time  TIME(0)        NOT NULL,",
              "subject     NVARCHAR(400)  NOT NULL,", "first_seen  DATE           NOT NULL,",
              "CONSTRAINT UQ_material_news UNIQUE (market, code, speak_date, speak_time, subject)"):
        assert s in blk, s
    pos = lambda t: next(k for k, d in enumerate(db.DDL) if f"CREATE TABLE {t} " in d)
    assert pos("material_news") == pos("quarterly_balance") + 1 and "說明" not in blk and "description" not in ddl
    assert all(w not in blk for w in ("quarterly_balance", "twse_index", "CREATE TABLE market_index", "CREATE TABLE etf_events"))
    assert "quarterly_balance（第 52 輪）、material_news（第 53 輪）、\"" in DBS and "twse_index（第 51 輪）、etf_holding_gaps\")" in DBS


# ─── 時機（驗收 13～19）────────────────────────────────────────
def _plan(now, news_=True, recs=None, src=CAT, closed=CLOSED):
    mp = _fn(catchup, src, "make_plan")
    st = {"alerts_at": None, "events_to": None, "revenue_on": None, **({"news": recs} if recs is not None else {})}
    return mp(now, 10, t3._full_snapshot(health.due_days(now, 10, closed)), st, closed, {}, news=news_)


def check_plan(src=CAT):
    rec = lambda t: (D(11, 28), t, D(11, 27), 1)
    now = TM(11, 30, 18)
    p_empty = {**_plan(now, None, src=src), "news": []}
    return (_plan(now, None, src=src)["news"] == [] and _plan(now, False, src=src)["news"] == [] and _plan(now, src=src)["news"] == ["TWSE", "TPEx"]
            and _plan(now, recs={"TWSE": rec(D(11, 29)), "TPEx": rec(D(11, 30))}, src=src)["news"] == ["TWSE"]
            and _plan(now, recs={"TWSE": rec(D(11, 30)), "TPEx": rec(D(12, 1))}, src=src)["news"] == []
            and _plan(TM(12, 25, 10), recs={"TWSE": rec(D(12, 24))}, src=src)["news"] == ["TWSE", "TPEx"]
            and _plan(TM(11, 28, 10), src=src)["news"] == ["TWSE", "TPEx"] and _plan(TM(11, 29, 10), src=src)["news"] == ["TWSE", "TPEx"]
            and _plan(TM(12, 26, 10), src=src, closed=CLOSED | {D(d, m) for d, m in ()})["news"] == ["TWSE", "TPEx"]
            and not catchup.plan_is_empty({**p_empty, "by_date": [], "news": ["TWSE"]}))


def test_plan():
    assert check_plan()
    now = TM(11, 28, 10)
    old = catchup.make_plan(now, 10, t3._full_snapshot(health.due_days(now, 10, CLOSED)), {"alerts_at": None, "events_to": None, "revenue_on": None}, CLOSED, {})
    assert old["news"] == [] and "news" not in catchup.plan_for_date(D(11, 27), TM(11, 28), False)
    assert catchup.plan_is_empty({**old, "by_date": [], "alerts": False, "events": None, "revenue": [], "financials": None, "tdcc": None})


class NewsWorld(t3.World):
    """test_iter03 的 World 加上兩個重大訊息端點（out = 各市場官方的出表日期民國字串）與 material_news（table = 表是否存在）。"""

    def __init__(self, seed, table=True):
        super().__init__(seed)
        self.table, self.keys, self.out = table, set(), {"TWSE": "1151128", "TPEx": "1151127"}
        self.revenue[(2026, 10)] = 1980

    def http(self, method, url, timeout=30, params=None, data=None, json=None):
        for mk, ep, raw, k in (("TWSE", "t187ap04_L", L_RAW, "出表日期"), ("TPEx", "mopsfin_t187ap04_O", O_RAW, "Date")):
            if ep in url:
                self.requests.append(("/" + ep, {}))
                return t3.Resp(status=500) if ep in self.down else t3.Resp([{**r, k: self.out[mk]} for r in raw])
        return super().http(method, url, timeout, params, data, json)


class NewsCursor(t3.FakeCursor):
    def execute(self, sql, *p):
        w = self.w
        if "OBJECT_ID('material_news')" in sql:
            self.result = [(1 if w.table else None,)]
        elif "MERGE material_news" in sql:
            ks = [(p[1], r["code"], r["speak_date"], r["speak_time"], r["subject"]) for r in json.loads(p[0])]
            self.result = [("UPDATE",) if k in w.keys else ("INSERT",) for k in ks]
            w.keys |= set(ks)
        else:
            return super().execute(sql, *p)
        return self


def run_news(w, now, src=None):
    w.requests.clear()
    buf = io.StringIO()
    with mock.patch.object(t3.FakeConn, "cursor", lambda self: NewsCursor(self.w)), t3.env(w), contextlib.ExitStack() as st:
        if src:
            st.enter_context(mock.patch.object(catchup, "_run_locked", _fns(catchup, src, ("make_plan", "execute_plan", "_run_locked"))[2]))
        st.enter_context(contextlib.redirect_stdout(buf))
        rc = catchup.run(days=10, now=now, notify=True)
    return rc, buf.getvalue(), [p for p, _ in w.requests if "t187ap04" in p], json.loads(w.runs[-1][2])


def check_world(src=CAT):
    bad = []
    base = NewsWorld(D(11, 27), table=False)
    rc0, out0, n0, d0 = run_news(base, TM(11, 28, 10), src)
    w = NewsWorld(D(11, 27))
    rc, out, n, d = run_news(w, TM(11, 28, 10), src)
    if (n0, rc, n, w.exports, len(w.requests)) != ([], rc0, ["/t187ap04_L", "/mopsfin_t187ap04_O"], 1, len(base.requests) + 2) or \
            d["undated"].get("news") != {"TWSE": {"on": "2026-11-28", "t": "2026-11-28", "d": "2026-11-27", "n": 8, "new": 8},
                                         "TPEx": {"on": "2026-11-28", "t": "2026-11-27", "d": "2026-11-26", "n": 8, "new": 8}} or \
            "  📰 上櫃重大訊息 8 筆（出表 2026-11-27，發言日 2026-11-26，新增 8 筆）\n" not in out or "重大訊息" in out0:
        bad.append(("首次", n, w.exports, out[-400:]))
    rc, out, n, d = run_news(w, TM(11, 28, 12), src)                 # 上市已是今天的出表：只再抓上櫃，新增 0 → 不匯出
    if n != ["/mopsfin_t187ap04_O"] or w.exports != 1 or "ℹ️  沒有新資料，不匯出" not in out or d["undated"]["news"]["TPEx"]["new"] != 0:
        bad.append(("同一天", n, w.exports))
    w.out["TPEx"] = "1151128"
    run_news(w, TM(11, 28, 13), src)
    if run_news(w, TM(11, 28, 14), src)[2] != []:
        bad.append("出表 = 今天不再抓")
    return bad


def test_world():
    assert check_world() == []


def check_isolation(src=CAT):
    base = NewsWorld(D(11, 27), table=False)
    rc0, _, _, d0 = run_news(base, TM(11, 30, 17, 30), src)
    w = NewsWorld(D(11, 27))
    w.down.add("t187ap04_L")
    w.out = {"TWSE": "1151130", "TPEx": "1151130"}                          # 兩市場都已是今天的出表
    rc, out, n, d = run_news(w, TM(11, 30, 17, 30), src)
    bad = []
    if (rc, d["items"], w.notices) != (rc0, d0["items"], base.notices) or "news.TWSE" not in d["errors"] \
            or "TWSE" in d["undated"].get("news", {}) or "TPEx" not in d["undated"].get("news", {}):
        bad.append(("隔離", rc, rc0, d["errors"]))
    if "  ⚠️  news.TWSE 失敗：openapi.twse.com.tw 附屬查詢失敗（不重試，收集繼續）" not in out or "❌ news" in out or "Traceback" in out \
            or "openapi.twse.com.tw" in fetch._dead_hosts or n != ["/t187ap04_L", "/mopsfin_t187ap04_O"]:
        bad.append(("輸出", out[-400:]))
    w.down.clear()
    if run_news(w, TM(11, 30, 18), src)[2] != ["/t187ap04_L"]:
        bad.append("下一次再抓上市")
    return bad


def test_isolation():
    assert check_isolation() == []


def check_state(src=HEA):
    fn = _fn(health, src, "load_state")
    j = lambda **k: json.dumps(k)
    v = lambda on, t, d, n: {"on": on, "t": t, "d": d, "n": n, "new": 0}
    rows = [(TM(11, 30, 22), 0, j(undated={"news": {"TPEx": v("2026-11-30", "2026-11-30", "2026-11-27", 57)}}), "catch-up", "ok", None),
            (TM(11, 29, 22), 0, j(undated={"news": {"TWSE": v("2026-11-29", "2026-11-29", "2026-11-28", 9), "TPEx": v("2026-11-29", "2026-11-28", "2026-11-26", 50)}}),
             "catch-up", "ok", None),
            (TM(11, 28, 22), 1, j(undated={"events_to": "2026-11-27"}), "catch-up", "ok", 20.0)]
    s = fn(t40.Rows(rows))
    return (s["news"] == {"TPEx": (D(11, 30), D(11, 30), D(11, 27), 57), "TWSE": (D(11, 29), D(11, 29), D(11, 28), 9)}
            and s["notices"] == {} and s["tdcc_on"] is None and fn(t40.Rows([]))["news"] == {})


def test_state():
    assert check_state()


# ─── check（驗收 20～23）─────────────────────────────────────────
NS = (True, {"TWSE": (D(11, 30), D(12, 18), {}, 900), "TPEx": (D(11, 30), D(12, 18), {}, 600)})
REC = {"TWSE": (D(12, 21), D(12, 21), D(12, 18), 94), "TPEx": (D(12, 21), D(12, 21), D(12, 18), 57)}


def _ns(gaps=(), mk_gaps=(), l=D(12, 18)):
    days = [d for d in health.trading_days(D(11, 30), l, CLOSED)]
    c = lambda skip: {d: 3 for d in days if d not in skip}
    return True, {"TWSE": (D(11, 30), l, c(set(gaps)), 900), "TPEx": (D(11, 30), l, c(set(mk_gaps)), 600)}


def check_line(src=HEA):
    fn = _fns(health, src, ("news_gaps", "news_line"))[1]
    head = "重大訊息最後成功：上市 2026-12-21（出表 12/21，發言日 12/18，94 筆）、上櫃 2026-12-21（出表 12/21，發言日 12/18，57 筆）"
    t = D(12, 21)
    return (fn((False, {}), {}, t, CLOSED) == "重大訊息：尚未建立資料表，請執行一次 python -m twstock setup-db"
            and fn(_ns(), {}, t, CLOSED) == "重大訊息最後成功：尚無執行紀錄"
            and fn(_ns(), REC, t, CLOSED) == head
            and fn(_ns(), {"TWSE": REC["TWSE"]}, t, CLOSED) == head.split("、上櫃")[0] + "、上櫃 尚無紀錄"
            and fn(_ns((D(12, 4), D(12, 11), D(12, 6))), REC, t, CLOSED) == head + "；⚠️ 近 30 天漏收：上市 12/04、12/11，漏收的日子無法回補"
            and fn(_ns((D(12, 4),), (D(12, 4),)), REC, t, CLOSED) == head + "；⚠️ 近 30 天漏收：上市 12/04，上櫃 12/04，漏收的日子無法回補"
            and fn(_ns(l=D(12, 17)), REC, t, CLOSED) == head                                    # lag = 1：不提示
            and fn(_ns((D(12, 4),), l=D(12, 15)), REC, t, CLOSED) == head + "；⚠️ 近 30 天漏收：上市 12/04，漏收的日子無法回補；⚠️ 上市已 3 個交易日沒有收到新的發言日；⚠️ 上櫃已 3 個交易日沒有收到新的發言日"
            and "漏收" not in fn(_ns((D(11, 30),)), REC, D(12, 30), CLOSED) and "漏收：上市 11/30" in fn(_ns((D(11, 30),)), REC, D(12, 21), CLOSED))                     # 11/30 在 今天 − 29 天之前，不算


def test_line():
    assert check_line()
    assert health.news_gaps({D(12, 1): 1}, D(11, 30), D(12, 2), D(11, 30), CLOSED) == [D(11, 30), D(12, 2)]
    assert health.news_gaps({}, D(11, 30), D(12, 2), D(12, 2), CLOSED) == [D(12, 2)] and health.news_gaps({}, None, None, D(1, 1), CLOSED) == []
    assert health.news_gaps({}, D(12, 24), D(12, 28), D(12, 1), CLOSED) == [D(12, 24), D(12, 28)]          # 12/25 休市、週末不算
    now = TM(12, 21, 10)
    days = health.due_days(now, 20, CLOSED)
    snap, st = t3._full_snapshot(days), {"alerts_at": TM(12, 18, 19), "events_to": days[-1], "news": REC}
    (t0, rc0), (t1, rc1) = health.check_report(days, snap, now, st, CLOSED), health.check_report(days, snap, now, st, CLOSED, news=_ns((D(12, 4),)))
    L1 = t1.splitlines()
    i = next(k for k, l in enumerate(L1) if l.startswith("重大訊息"))
    assert rc0 == rc1 == 0 and L1[i - 1].startswith("除權除息預告") and L1[:i] + L1[i + 1:] == t0.splitlines() and "重大訊息" not in t0
    w, buf = NewsWorld(D(11, 27), table=False), io.StringIO()
    with t3.env(w), mock.patch.object(health, "load_snapshot", w.snapshot), contextlib.redirect_stdout(buf):
        rc = health.run_check(20, TM(11, 30, 12))
    assert rc == 0 and "重大訊息：尚未建立資料表，請執行一次 python -m twstock setup-db" in buf.getvalue() and w.requests == [] and w.merges == []


# ─── 匯出（驗收 24～29）─────────────────────────────────────────
def _rows():
    r = lambda mk, c, d, t, s, n="名": (mk, c, n, d, t, s)
    return [r("TWSE", "2330", D(12, 19), time(10, 0), "休市日的一則"), r("TWSE", "2330", D(12, 18), time(14, 35), "B"), r("TWSE", "2330", D(12, 18), time(14, 35), "A"),
            r("TPEx", "9999", D(12, 18), time(7, 0, 4), "官方名稱", "某公司"), r("TWSE", "2330", D(11, 19), time(8, 0), "邊界")]


def check_export(src=EXP):
    mn, note = _fns(export, src, ("mn_export", "news_note"))
    c = {d: 1 for d in health.trading_days(D(11, 30), D(12, 18), CLOSED) if d not in (D(12, 4), D(12, 11))}
    mks = {"TWSE": (D(11, 30), D(12, 19), c, 900), "TPEx": (D(12, 18), D(12, 18), {D(12, 18): 1}, 1)}
    base, by, top = mn(_rows(), mks, D(12, 18), CLOSED)
    one = mn([_rows()[0]], {"TWSE": (D(12, 19), D(12, 19), {}, 1)}, D(12, 18), CLOSED)
    return (base == {"TWSE": {"f": "2026-11-30", "w": "2026-11-19", "x": ["2026-12-04", "2026-12-11"]}, "TPEx": {"f": "2026-12-18", "w": "2026-11-19", "x": []}}
            and by["2330"] == [["2026-12-19", "10:00", "休市日的一則"], ["2026-12-18", "14:35", "B"], ["2026-12-18", "14:35", "A"], ["2026-11-19", "08:00", "邊界"]]
            and top == {"d": "2026-12-18", "f": {"TWSE": "2026-11-30", "TPEx": "2026-12-18"}, "x": {"TWSE": ["2026-12-04", "2026-12-11"], "TPEx": []},
                        "n": {"TWSE": 2, "TPEx": 1}, "r": [["2330", "TWSE", "14:35", "B", "名"], ["2330", "TWSE", "14:35", "A", "名"], ["9999", "TPEx", "07:00", "官方名稱", "某公司"]]}
            and one[2] is None and mn([], {}, D(12, 18), CLOSED) == ({}, {}, None)
            and note((True, mks), base, top) == "  📌 重大訊息：上市 2026-11-30 起 900 筆、上櫃 2026-12-18 起 1 筆；最新發言日 2026-12-18；近 30 天漏收 上市 2 天、上櫃 0 天"
            and note((True, {"TWSE": mks["TWSE"]}), {"TWSE": base["TWSE"]}, None) == "  📌 重大訊息：上市 2026-11-30 起 900 筆、上櫃 尚無資料；最新發言日 --；近 30 天漏收 上市 2 天、上櫃 --"
            and note((False, {}), {}, None) == "  📌 重大訊息：尚未建立 material_news（請執行 setup-db），mn 不輸出"
            and note((True, {}), {}, None) == "  📌 重大訊息：material_news 還沒有資料，mn 不輸出")


def test_export():
    assert check_export()
    assert export._load_news(t40.Rows([1]), D(11, 19)) == [1]
    for s in ("    print(bs_note(bal is not None, bs_all))", "    print(news_note(news, mn_base, mn_latest))", '    print(f"✅ 匯出完成'):
        assert s in EXP, s
    assert EXP.index("    print(bs_note(bal is not None, bs_all))") < EXP.index("    print(news_note(news, mn_base, mn_latest))") < EXP.index('    print(f"✅ 匯出完成')
    assert '**({"nx": nx_stock[code]} if code in nx_stock else {}),     # 第 40 輪 F40-2：下一次除權除息預告\n            **({"mn": {**mn_base[mk_], "r": mn_rows.get(code, [])}} if mk_ in mn_base else {}),' in EXP
    assert "ORDER BY speak_date DESC, speak_time DESC, code, id" in _grab_py(EXP, "_load_news") and "clause" not in _grab_py(EXP, "mn_export")
    assert EXP.index("    news = news_state(cur, latest_date - timedelta(days=45))") < EXP.index("    conn.close()\n    mlast")
    assert "mn" not in _grab_py(EXP, "etf_export")


def check_qa(exp=EXP, src=NEWS):
    """QA53-01：匯出去掉主旨的排版換行；QA53-02：每一列都無法解析時印 ⚠️，不寫入、不記錄。"""
    line, mn = _fns(export, exp, ("mn_line", "mn_export"))
    _, by, top = mn([("TWSE", "2330", "名", D(12, 18), time(9), "臨\r\n時股東會"), ("TWSE", "2330", "名", D(12, 18), time(8), "A\r\nB")],
                    {"TWSE": (D(12, 18), D(12, 18), {D(12, 18): 2}, 2)}, D(12, 18), CLOSED)
    r, log, out, _ = _collect(src, data=[dict(ONE, 發言時間="abc"), dict(ONE, 公司代號="")])
    return (line("INTERNATIONAL\r\nFUND對沖") == "INTERNATIONAL FUND對沖" and line("更名為 \r\n「長耀」，期間：\n115年") == "更名為「長耀」，期間：115年"
            and line("a  b") == "a  b" and [x[2] for x in by["2330"]] == ["臨時股東會", "A B"] and [x[3] for x in top["r"]] == ["臨時股東會", "A B"]
            and r is None and log == [] and out == "  ⚠️  上市重大訊息 2 筆都無法解析，下次執行再抓\n")


def test_qa():
    assert check_qa()


# ─── 畫面（驗收 30～41）─────────────────────────────────────────
SHORT = "只列官方主旨，不含說明全文；內容以原文為準"
FULL = ("重大訊息是上市櫃公司依規定在公開資訊觀測站發布的公告。本站只列發言日、時間與主旨，不含說明全文，也不分類、不加註解；同一件事的更正或補充，官方會另發一則，兩則都會列出。"
        "資料來自證交所、櫃買中心的開放資料，官方每次只提供一天的公告，本站沒收到的日子目前無法補；「沒有收到」是指那個交易日本站一則都沒有收到。時間是公司的發言時間。")
TAIL = "。官方每次只提供一天的資料，沒收到的日子本站目前無法補"
LINK = '<a href="https://mops.twse.com.tw/" target="_blank" rel="noopener noreferrer">公開資訊觀測站</a>'
NASTY = "<b>a&b</b>\"'"


def _js(stk, app, body):
    return "\n".join([_grab(app, n) for n in ("fmt", "esc", "md", "noteHTML", "segHTML", "mnGap", "newsBoard", "mnApply")] +
                     [_grab(stk, n) for n in ("mnCard", "mnShowAll")]) + "\n" + body


def check_card(stk=STK, app=APP):
    r = lambda n: [["2026-12-18", f"{i % 24:02d}:00", f"主旨{i}"] for i in range(n)]
    cases = [{"f": "2026-11-30", "w": "2026-11-19", "x": [], "r": [["2026-12-18", "14:35", NASTY], ["2026-12-18", "07:00", "B"], ["2026-12-04", "07:00", "C"]]},
             {"f": "2026-11-30", "w": "2026-11-19", "x": ["2026-12-04", "2026-12-11"], "r": r(11)},
             {"f": "2026-11-30", "w": "2026-11-19", "x": [f"2026-12-{d:02d}" for d in (1, 2, 3, 4, 8, 18)], "r": r(10)},
             {"f": "2026-11-10", "w": "2026-11-19", "x": [], "r": []}, {"f": "2026-11-30", "w": "2026-11-19", "x": [], "r": []}]
    got = _node(_js(stk, app, f"console.log(JSON.stringify({json.dumps(cases)}.map(M => mnCard(M, '2330'))));"))
    if got is None:
        return True
    if got == "ERR":
        return False
    row = lambda d, t, s, hide=False: f'<div class="al-row mn-row"{" style=\"display:none\"" if hide else ""}><span class="small muted num">{d} {t}</span>　<span class="mn-s">{s}</span></div>'
    want = lambda sub, rows, btn, g: (f'<section class="sec card mn"><div class="sec-h"><h2>重大訊息</h2><span class="muted small">{sub}，公開資訊觀測站</span></div>\n{rows}\n{btn}\n'
                                      f'<div class="muted small" style="margin-top:6px">本站自 2026/11/30 起收錄{g}{TAIL}</div>\n'
                                      f'<div class="muted small">原文請到{LINK}以代號 2330 與發言日查詢</div>\n'
                                      f'<div class="muted small" style="margin-top:6px"><details class="note"><summary>{SHORT}<i>說明</i></summary><div>{FULL}</div></details></div></section>')
    w0 = want("11/30 起", row("12/18", "14:35", "&lt;b&gt;a&amp;b&lt;/b&gt;&quot;&#39;") + row("12/18", "07:00", "B") + row("12/04", "07:00", "C"), "", "")
    return (got[0] == w0 and "<b>" not in got[0] and got[1].count('style="display:none"') == 1 and '<button class="chip" id="mnMore" style="margin-top:8px">顯示全部 11 則</button>' in got[1]
            and "本站自 2026/11/30 起收錄；12/04、12/11 沒有收到。" in got[1] and "mnMore" not in got[2]
            and "本站自 2026/11/30 起收錄；近 30 天有 6 個交易日沒有收到，最近一次 12/18。" in got[2]
            and '<span class="muted small">近 30 天，公開資訊觀測站</span></div>\n<div class="muted small">近 30 天沒有重大訊息</div>' in got[3].replace("2026/11/10", "2026/11/30")
            and '<span class="muted small">11/30 起，公開資訊觀測站</span></div>\n<div class="muted small">11/30 起沒有重大訊息</div>' in got[4])


def check_show_all(stk=STK, app=APP):
    got = _node(_js(stk, app, """const rows = [{ style: { display: 'none' } }, { style: { display: '' } }]; let gone = 0;
global.document = { querySelectorAll: s => s === '#view .mn-row' ? rows : [] }; const $ = s => s === '#mnMore' ? { remove: () => { gone++; } } : null;
mnShowAll(); console.log(JSON.stringify([rows.map(r => r.style.display), gone]));"""))
    return got is None or got == [["", ""], 1]


def test_card():
    assert check_card() and check_show_all()
    k = STK.index("  if (tab !== 'k') return;\n")
    assert STK[k:].startswith("  if (tab !== 'k') return;\n  if (!E && data.mn) { $('#view').insertAdjacentHTML('beforeend', mnCard(data.mn, code)); $('#mnMore')?.addEventListener('click', mnShowAll); }")
    assert "const STOCK_TABS = [['k', '走勢'], ['chip', '籌碼'], ['fund', '基本面']];" in STK


L0 = {"stocks": {"2330": {"n": "台積電"}}, "mn": {"d": "2026-11-27", "f": {"TWSE": "2026-11-28", "TPEx": "2026-11-28"}, "x": {"TWSE": [], "TPEx": []},
                                                 "n": {"TWSE": 2, "TPEx": 0}, "r": [["2330", "TWSE", "14:35", NASTY, "台積電"], ["9999", "TWSE", "07:00", "主旨", "某公司"]]}}


def check_board(stk=STK, app=APP):
    L1 = json.loads(json.dumps(L0))
    L1["mn"]["f"]["TPEx"], L1["mn"]["x"]["TPEx"] = "2026-11-30", ["2026-12-04"]
    js = _js(stk, app, f"""const L0 = {json.dumps(L0)}, L1 = {json.dumps(L1)};
let App = {{ watch: new Set() }}; const a = newsBoard(L0); App = {{ watch: new Set(['2330']), mnOpen: true, mnW: true, mnQ: 'x"' }}; const b = newsBoard(L0);
console.log(JSON.stringify([a, b, newsBoard(L1), newsBoard({{ stocks: {{}} }})]));""")
    got = _node(js)
    if got is None:
        return True
    if got == "ERR":
        return False
    a, b, c, e = got
    s = "&lt;b&gt;a&amp;b&lt;/b&gt;&quot;&#39;"
    return (a.startswith('<section class="sec card"><details class="al-box mn-box">\n  <summary class="sec-h"><h2>重大訊息</h2><span class="muted small">發言日 11/27　上市 2 則　上櫃 尚未收到</span><span class="sp"></span><i></i></summary>')
            and "mnSeg" not in a and 'placeholder="篩選代號、名稱或主旨" aria-label="篩選重大訊息" value=""' in a
            and f'<a class="al-row mn-r" href="#/stock/2330" data-c="2330"><div class="al-l"><b>台積電</b><span class="muted small">2330・上市</span><span class="sp"></span><span class="small num">14:35</span></div><div class="muted small al-why mn-s" title="{s}">{s}</div></a>' in a
            and '<div class="al-row mn-r" data-c="9999"><div class="al-l"><b>某公司</b>' in a and "<b>a&b" not in a
            and f'本站自 2026/11/28 起收錄{TAIL}</div>' in a and f"原文請到{LINK}以代號與發言日 11/27 查詢</div>\n</details></section>" in a
            and '<details class="al-box mn-box" open>' in b and '<div class="seg" id="mnSeg"><button data-v="all" class="">全部</button><button data-v="w" class="on">只看自選</button></div>' in b
            and 'value="x&quot;"' in b and f"本站自 上市 2026/11/28、上櫃 2026/11/30 起收錄；上櫃 12/04 沒有收到{TAIL}" in c and e == "")


def check_filter(stk=STK, app=APP):
    js = _js(stk, app, """const mk = (c, t) => ({ dataset: { c }, textContent: t, style: {} });
const rows = [mk('2330', '台積電2330・上市14:35公告 KY 子公司'), mk('9999', '某公司9999・上市07:00董事會 Abc')], none = { style: {}, textContent: '' };
const box = { querySelectorAll: () => rows }; const $ = s => s === '#view details.mn-box' ? box : s === '#mnNone' ? none : null;
let App; const run = a => { App = Object.assign({ watch: new Set(), latest: { mn: { d: '2026-11-27' } } }, a); mnApply(); return [rows.map(r => r.style.display).join(','), none.style.display, none.textContent]; };
console.log(JSON.stringify([run({ mnQ: ' 2330 ' }), run({ mnQ: 'ky' }), run({ mnW: true, watch: new Set(['9999']) }), run({ mnW: true, watch: new Set(['1234']) }),
  run({ mnQ: 'zzz' }), run({ mnW: true }), run({}), run({ mnQ: 'aBC' })]));""")
    got = _node(js)
    return got is None or got == [[",none", "none", "沒有符合的重大訊息"], [",none", "none", "沒有符合的重大訊息"], ["none,", "none", "沒有符合的重大訊息"],
                                  ["none,none", "", "自選股在 11/27 沒有重大訊息"], ["none,none", "", "沒有符合的重大訊息"], [",", "none", "沒有符合的重大訊息"], [",", "none", "沒有符合的重大訊息"], ["none,", "none", "沒有符合的重大訊息"]]


def test_board():
    assert check_board() and check_filter()
    assert "    ${alertBoard(L)}${newsBoard(L)}`,   // 第 53 輪 F53-6\n" in APP
    assert "  $('#view details.al-box')?.addEventListener('toggle', e => { App.alOpen = e.target.open; });\n  mnWire();" in APP
    assert all("newsBoard" not in _grab(APP, n) for n in ("alertBoard", "watchGrp", "renderWatch"))
    assert APP.index("function watchGrp(") < APP.index("function newsBoard(") < APP.index("function breadthCard(")


# ─── 用詞、node 14、?v=、文件（驗收 40～45）─────────────────────────
def _segs(stk=STK, app=APP, src=NEWS):
    segs = [src] + [_grab(stk, n) for n in ("mnCard", "mnShowAll")] + [_grab(app, n) for n in ("newsBoard", "mnGap", "mnWire", "mnApply")]
    segs += [_grab_py(HEA, n) for n in ("news_exists", "news_state", "news_gaps", "news_line")] + [_grab_py(EXP, n) for n in ("_load_news", "mn_export", "news_note")]
    segs += [l for f in (app, stk, CAT, HEA, EXP, DBS) for l in f.splitlines() if "第 53 輪" in l]
    segs += [l for l in README.splitlines() if l.startswith("- 第 53 輪重大訊息")]
    return "\n".join(segs).replace("借券賣出", "")


def check_words(stk=STK, app=APP, src=NEWS):
    seg, js = _segs(stk, app, src), "\n".join([_grab(stk, n) for n in ("mnCard", "mnShowAll")] + [_grab(app, n) for n in ("newsBoard", "mnGap", "mnWire", "mnApply")])
    return all(w not in seg for w in ADVICE) and all(w not in js for w in (".at(", "replaceAll", "||=", "&&=", "??="))


def test_words_node14():
    assert check_words()


def test_version_and_docs():
    for f in ("app.js", "stock.js", "app.css", "tools.js", "help.js", "compare.js"):
        v = hashlib.sha1((SITE / f).read_bytes()).hexdigest()[:8]
        assert f"{f}?v={v}" in HTML, f"index.html 要改成 {f}?v={v}"
    for s in ("app.css?v=d1508f41", "tools.js?v=0a050889", "help.js?v=a5a5a7e8", "compare.js?v=f7e0bca5"):
        assert s in HTML, s
    assert "app.js?v=6cde9106" not in HTML and "stock.js?v=7c592b0f" not in HTML and HTML.count("https://") == 2
    assert "python3 tests/test_iter53.py" in README and "第 53 輪" in (ROOT / "docs" / "iterations" / "README.md").read_text(encoding="utf-8")
    r = next(l for l in README.splitlines() if l.startswith("- 第 53 輪重大訊息"))
    for s in ("material_news", "`news`", "出表日期", "休市日", "⚠️", "說明", "`mn`", "`latest.mn`", "走勢", "總覽", "check", "無法補"):
        assert s in r, s
    assert not re.search(r"第 (?!53 輪)\d+ 輪", r)


def test_contrast():
    rows = [
        ("欄名不 strip()", check_fixture, NEWS, "{k.strip(): v for k, v in raw.items()}", "dict(raw)"),
        ("讀了說明", check_fixture, NEWS, '"subject": subject,', '"subject": subject, "說明": r.get("說明"),'),
        ("時間不補 0", check_fields, NEWS, "        s = s.zfill(6)\n", ""),
        ("事實發生日不檢查年份", check_fields, NEWS, " and (fd - sd).days <= 366", ""),
        ("出表日期取最早", check_fields, NEWS, "return max(outs), list", "return min(outs), list"),
        ("去重不正規化", check_dedup, NEWS, 'unicodedata.normalize("NFKC", subject).casefold()', "subject"),
        ("不是 isolated", check_collect, NEWS, 'request("GET", _URLS[market], isolated=True)', 'request("GET", _URLS[market])'),
        ("MERGE 更新 first_seen", check_collect, NEWS, "out_date = ?\n", "out_date = ?, first_seen = ?\n"),
        ("空陣列也回傳紀錄", check_collect, NEWS, '（0 筆），下次執行再抓")\n        return None\n', '（0 筆），下次執行再抓")\n        return {}\n'),
        ("pyodbc.Error 不包", check_collect, NEWS, "except pyodbc.Error as e:", "except ZeroDivisionError as e:"),
        ("比發言日不比出表日期", check_plan, CAT, 'state["news"][mk][1] < now.date()', 'state["news"][mk][2] < now.date()'),
        ("< 改 <=", check_plan, CAT, 'state["news"][mk][1] < now.date()', 'state["news"][mk][1] <= now.date()'),
        ("news 加進 undated_errors", lambda s: check_isolation(s) == [], CAT, '("alerts", "events", "revenue", "financials", "industry", "chains")]', '("alerts", "events", "revenue", "financials", "industry", "chains") or k.startswith("news")]'),
        ("changed 那一行拿掉", lambda s: check_world(s) == [], CAT, '        changed = changed or any(v.get("new")', '        changed = changed and any(v.get("new")'),
        ("load_state 取最舊", check_state, HEA, 'state["news"].setdefault(mk, ', 'state["news"].__setitem__(mk, '),
        ("lag 門檻 ≥ 1", check_line, HEA, "        if lag >= 2:", "        if lag >= 1:"),
        ("漏收算到休市日", check_line, HEA, "return [d for d in trading_days(max(f, start), l, closed) if not counts.get(d)]",
         "return [f + timedelta(n) for n in range((l - max(f, start)).days + 1) if not counts.get(f + timedelta(n)) and f + timedelta(n) >= start]"),
        ("窗口用 30 天", check_export, EXP, "    w = latest_date - timedelta(days=29)\n", "    w = latest_date - timedelta(days=30)\n"),
        ("d 取含休市日的最新發言日", check_export, EXP, "if r[3] >= w and is_trading_day(r[3], closed)]", "if r[3] >= w]"),
        ("輸出條款", check_export, EXP, 'by_code[code].append([str(d), f"{t:%H:%M}", mn_line(s)])', 'by_code[code].append([str(d), f"{t:%H:%M}", mn_line(s), None])'),
        ("主旨換行沒去掉", check_qa, EXP, '[str(d), f"{t:%H:%M}", mn_line(s)]', '[str(d), f"{t:%H:%M}", s]'),
        ("全部無法解析仍寫沒有資料", lambda n: check_qa(src=n), NEWS, "    if not rows and skipped:", "    if False:"),
        ("主旨不 esc", check_card, STK, '<span class="mn-s">${esc(r[2])}</span>', '<span class="mn-s">${r[2]}</span>'),
        ("隱藏用 hidden 屬性", check_card, STK, """${i >= 10 ? ' style="display:none"' : ''}""", "${i >= 10 ? ' hidden' : ''}"),
        ("顯示全部不還原", check_show_all, STK, "e.style.display = '';", "e.hidden = false;"),
        ("自選 0 檔仍顯示切換鈕", lambda a: check_board(app=a), APP, "${App.watch.size ? segHTML(", "${1 ? segHTML("),
        ("今日卡主旨不 esc", lambda a: check_board(app=a), APP, 'title="${esc(s)}">${esc(s)}</div>', 'title="${esc(s)}">${s}</div>'),
        ("篩選不分大小寫拿掉", lambda a: check_filter(app=a), APP, "r.textContent.toUpperCase().includes(q)", "r.textContent.includes(q)"),
        ("用詞（清單中的任一詞）", check_words, STK, "只列官方主旨", f"{sorted(ADVICE)[0]}只列官方主旨"),
        ("node 14 不支援的寫法", lambda a: check_words(app=a), APP, "md(x[x.length - 1])", "md(x.at(-1))"),
    ]
    for name, check, src, old, new in rows:
        bad = _mut(src, old, new)
        try:
            ok = check(bad)
        except Exception:
            ok = False
        assert not ok, f"反證沒有被擋下：{name}"
        print(f"  ✔ 反證擋下：{name}")


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_") and callable(f):
            f()
            print(f"✅ {n}")
