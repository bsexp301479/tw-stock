"""第 24 輪（不連網、不連資料庫）：F24-5 股利金額與 ETF 除息入表、F24-6 個股頁股利與填息、F24-7a～f 小修、F24-8 法人合計用官方值。
fixture：tests/fixtures/twt49u_div_mini.json、exdailyq_div_mini.json（官方原始回應的精簡版：欄位不變，只留幾列；
2026-11-14 分析師取得的 2025-10-30～2026-11-14 區間），dv_prices_mini.json（7 檔的日線 d、c、ch，取自第 23 輪程式的匯出）。
收集流程沿用 test_iter03 的 World、env、run_site；有 node 時逐字取出 stock.js、app.js 的函式執行。"""
import contextlib
import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
import test_iter03 as t3  # noqa: E402
from twstock import db, export, fetch, health, tradingcal  # noqa: E402
from twstock.collectors import catchup, events, history  # noqa: E402
from twstock.fetch import FetchError  # noqa: E402

D, T, World, CLOSED = t3.D, t3.T, t3.World, t3.CLOSED
FIX = Path(__file__).resolve().parent / "fixtures"
T49 = json.loads((FIX / "twt49u_div_mini.json").read_text(encoding="utf-8"))
EXQ = json.loads((FIX / "exdailyq_div_mini.json").read_text(encoding="utf-8"))["tables"][0]
PX = json.loads((FIX / "dv_prices_mini.json").read_text(encoding="utf-8"))
APP = (ROOT / "site" / "app.js").read_text(encoding="utf-8")
STK = (ROOT / "site" / "stock.js").read_text(encoding="utf-8")
README = (ROOT / "README.md").read_text(encoding="utf-8")
SRC = (ROOT / "twstock" / "export.py").read_text(encoding="utf-8")
EVSRC = (ROOT / "twstock" / "collectors" / "events.py").read_text(encoding="utf-8")
OLD_KEYS = {"stock_code", "event_date", "event_type", "prev_close", "ref_price", "source", "div_ref"}


# ─── F24-5：解析、寫入、DDL ─────────────────────────────
def test_parse_amounts():
    st, et = events.parse_events_all("TWT49U", T49["fields"], T49["data"])
    by = {(r["stock_code"], r["event_date"]): r for r in st}
    assert by[("2330", "2025-12-11")] == {"stock_code": "2330", "event_date": "2025-12-11", "event_type": "息", "prev_close": 1505.0,
                                          "ref_price": 1499.99, "source": "TWT49U", "div_ref": 1499.99, "div_total": 5.000011, "div_cash": 5.000011}
    assert by[("2421", "2026-06-10")]["div_cash"] == 5.24042
    r = by[("6669", "2026-09-02")]                                                     # 上市「權」：只有權值+息值，現金股利不存
    assert r["event_type"] == "權" and r["div_total"] == 5185.002642 and "div_cash" not in r and "stock_div" not in r
    r = by[("8112", "2026-07-06")]
    assert r["event_type"] == "權息" and r["div_total"] == 5.36055 and "div_cash" not in r
    # ETF 另成一份，只收「息」；ETN（020036）、受益證券（01007T）、特別股（2882A）兩邊都不收
    assert {r["etf_code"] for r in et} == {"0056", "00401A"} and {r["event_type"] for r in et} == {"息"}
    assert {"etf_code": "00401A", "event_date": "2026-11-13", "event_type": "息", "prev_close": 12.42, "ref_price": 12.28,
            "source": "TWT49U", "div_cash": 0.138} in et
    codes = {r["stock_code"] for r in st} | {r["etf_code"] for r in et}
    assert not codes & {"020036", "01007T", "2882A", "0056 ", "00401A "} and "0056" not in {r["stock_code"] for r in st}
    st2, et2 = events.parse_events_all("TPEX_EX", EXQ["fields"], EXQ["data"])
    by = {(r["stock_code"], r["event_date"]): r for r in st2}
    r = by[("6703", "2026-07-16")]
    assert r["event_type"] == "權" and r["div_cash"] == 0.0 and r["stock_div"] == 100.00000916
    r = by[("5511", "2026-07-09")]
    assert r["event_type"] == "權息" and r["div_cash"] == 3.6 and r["stock_div"] == 198.87165021
    assert by[("6488", "2026-07-16")]["div_cash"] == 5.7 and by[("6488", "2026-07-16")]["stock_div"] == 0.0     # 0 照存（dv 才省略）
    assert len(et2) == 12 and {r["etf_code"] for r in et2} == {"00937B"} and et2[0]["div_cash"] == 0.072
    assert not {r["stock_code"] for r in st2} & {"8349A", "020035", "00937B"}
    # 預設的 parse_events 不變：不含股利金額、不含 ETF（test_iter02、test_iter19 整個 dict 比對）
    for src, f, rows, full in (("TWT49U", T49["fields"], T49["data"], st), ("TPEX_EX", EXQ["fields"], EXQ["data"], st2)):
        old = events.parse_events(src, f, rows)
        assert old == [{k: v for k, v in r.items() if k in OLD_KEYS} for r in full] and all(set(r) <= OLD_KEYS for r in old)
    # 欄位缺漏、值為 --：照常回傳，金額不放鍵
    f = [x if x != "權值+息值" else "改名" for x in T49["fields"]]
    st3, et3 = events.parse_events_all("TWT49U", f, T49["data"])
    assert len(st3) == len(st) and len(et3) == len(et) and all("div_total" not in r and "div_cash" not in r for r in st3 + et3)
    rows = [list(r) for r in EXQ["data"]]
    k = EXQ["fields"].index("息值")
    for r in rows:
        r[k] = "--"
    st4, et4 = events.parse_events_all("TPEX_EX", EXQ["fields"], rows)
    assert all("div_cash" not in r for r in st4 + et4) and len(et4) == 12 and by[("5511", "2026-07-09")]["div_total"] == \
        next(r for r in st4 if r["stock_code"] == "5511")["div_total"]
    # 必要欄位缺漏：兩份都是空的；減資、面額變更沒有股利欄、不收 ETF
    assert events.parse_events_all("TWT49U", T49["fields"][1:], T49["data"]) == ([], [])
    fields = ["恢復買賣日期", "股票代號", "停止買賣前收盤價格", "恢復買賣參考價"]
    assert events.parse_events_all("TWTAUU", fields, [["115年07月01日", "0056", "30.00", "36.00"], ["115年07月01日", "1101", "30.00", "36.00"]]) == \
        ([{"stock_code": "1101", "event_date": "2026-07-01", "event_type": "減", "prev_close": 30.0, "ref_price": 36.0, "source": "TWTAUU"}], [])


class _Conn:
    def __init__(self, log):
        self.log = log

    def cursor(self):
        return self

    def execute(self, sql, *params):
        self.log.append((sql, params))
        return self

    def commit(self):
        self.log.append(("commit", ()))

    def close(self):
        pass


def _fake_fetch(source, s, e):
    if source == "TWT49U":
        return events.parse_events_all(source, T49["fields"], T49["data"])
    if source == "TPEX_EX":
        return events.parse_events_all(source, EXQ["fields"], EXQ["data"])
    return [], []


def test_merge_sql():
    # 新欄位另起一行，舊的兩段逐字保留（test_iter19）；金額缺漏時 COALESCE 不清掉已存的值
    for s in ("div_total = COALESCE(s.div_total, t.div_total), div_cash = COALESCE(s.div_cash, t.div_cash),",
              "stock_div = COALESCE(s.stock_div, t.stock_div),", "div_ref = COALESCE(s.div_ref, t.div_ref)",
              "div_total DECIMAL(12,6), div_cash DECIMAL(12,6), stock_div DECIMAL(14,8)",
              "MERGE etf_events AS t", "JOIN etfs et ON et.etf_code = j.etf_code"):
        assert s in EVSRC, s
    assert "div_cash = COALESCE(s.div_cash, t.div_cash)\n" in EVSRC[EVSRC.index("MERGE etf_events"):]               # ETF 那段也不清掉
    log, buf = [], io.StringIO()
    with mock.patch.object(events, "fetch_events", _fake_fetch), mock.patch.object(db, "connect", lambda: _Conn(log)), \
            contextlib.redirect_stdout(buf):
        n = events.collect_events(D(10, 30, 2025), D(11, 14))          # 2 段：同一列抓到兩次也只寫一次
    assert n == {"stocks": 15, "etfs": 20}
    assert "股票 15 筆、ETF 20 筆（2025-10-30 ～ 2026-11-14）" in buf.getvalue()
    (s1, p1), (s2, p2), (c, _) = log
    assert "MERGE price_events" in s1 and "MERGE etf_events" in s2 and c == "commit"         # 同一個連線、一次 commit
    rows, etfs = json.loads(p1[0]), json.loads(p2[0])
    assert len(rows) == 15 and all("etf_code" not in r for r in rows) and not {r["stock_code"] for r in rows} & {"0056", "00401A", "00937B"}
    assert len(etfs) == 20 and {r["etf_code"] for r in etfs} == {"0056", "00401A", "00937B"} and all("stock_code" not in r for r in etfs)
    # 沒有任何事件：不連資料庫
    log.clear()
    with mock.patch.object(events, "fetch_events", lambda *a: ([], [])), mock.patch.object(db, "connect", lambda: _Conn(log)), \
            contextlib.redirect_stdout(io.StringIO()):
        assert events.collect_events(D(11, 7), D(11, 14)) == {"stocks": 0, "etfs": 0}
    assert log == []


def test_setup_db_ddl():
    ddl = [s.strip() for s in db.DDL]
    i = next(k for k, s in enumerate(ddl) if "CREATE TABLE etf_events" in s)
    assert ddl[i].startswith("IF OBJECT_ID('etf_events') IS NULL") and "REFERENCES etfs(etf_id)" in ddl[i]
    assert "CONSTRAINT UQ_etf_events UNIQUE (etf_id, event_date, source)" in ddl[i] and "div_cash    DECIMAL(12,6) NULL" in ddl[i]
    assert i > next(k for k, s in enumerate(ddl) if "CREATE TABLE etfs" in s)                    # 外鍵表先建
    for col, typ in (("div_total", "DECIMAL(12,6)"), ("div_cash", "DECIMAL(12,6)"), ("stock_div", "DECIMAL(14,8)")):
        assert f"IF COL_LENGTH('price_events', '{col}') IS NULL ALTER TABLE price_events ADD {col} {typ} NULL" in ddl, col
    # 可重複執行：每一條都有存在檢查
    new = [s for s in ddl if "etf_events" in s or "div_total" in s or "'div_cash'" in s or "stock_div" in s]
    assert len(new) == 4 and all(s.startswith("IF ") for s in new)


# ─── F24-6：股利與填息 ───────────────────────────────────
def _official():
    out = {}
    for src, f, rows in (("TWT49U", T49["fields"], T49["data"]), ("TPEX_EX", EXQ["fields"], EXQ["data"])):
        for r in events.parse_events_all(src, f, rows)[0]:          # 同匯出端讀 price_events 的 dict
            out.setdefault(r["stock_code"], []).append({
                "d": date.fromisoformat(r["event_date"]), "t": r["event_type"], "p": r["prev_close"], "r": r["ref_price"], "src": src,
                "k": export.rights_kind(r["event_type"], r["prev_close"], r["ref_price"], r.get("div_ref")),
                "a": (r.get("div_total"), r.get("div_cash"), r.get("stock_div"))})
    return out


def _dv(code):
    v, off = PX[code], sorted(_official().get(code, []), key=lambda e: e["d"])
    d_ = [date.fromisoformat(s) for s in v["d"]]
    ev, _ = export._price_events(d_, v["c"], v["ch"], v["market"], off)
    assert all(set(e) <= {"i", "d", "t", "p", "r", "k"} for e in ev)                    # ev 元素不加鍵（test_iter02、08、19）
    return export.dividends(d_, v["c"], ev, off)


def test_dividends_real():
    assert _dv("2421") == [{"d": "2026-06-10", "t": "息", "c": 5.24042, "p": 160.0, "f": "2026-08-28", "n": 56}]    # 2/24 現增（k=c）不列
    assert [(r["c"], r["f"], r["n"]) for r in _dv("2330")] == [(5.000011, "2025-12-26", 11), (6.000035, "2026-03-17", 1),
                                                               (6.000035, "2026-06-12", 2), (7.000001, "2026-09-17", 2)]
    assert _dv("6488") == [{"d": "2025-12-31", "t": "息", "c": 2.0, "p": 413.0, "f": "2026-01-05", "n": 3},
                           {"d": "2026-07-16", "t": "息", "c": 5.7, "p": 1480.0}]                                  # 尚未填息
    assert _dv("6669") == [{"d": "2026-06-22", "t": "息", "c": 144.391544, "p": 5130.0, "f": "2026-07-02", "n": 9},
                           {"d": "2026-09-02", "t": "權", "k": "s", "a": 5185.002642, "p": 7800.0}]               # 純配股：只列，不算填權
    assert _dv("8112") == [{"d": "2026-07-06", "t": "權息", "k": "sc", "a": 5.36055, "p": 92.9, "f": "2026-08-11", "n": 26}]
    assert _dv("6703") == [{"d": "2026-03-26", "t": "息", "c": 4.8, "p": 120.5, "x": ["2026-07-16", "配股"]},
                           {"d": "2026-07-16", "t": "權", "k": "s", "c": 0.0, "s": 100.00000916, "p": 117.0}]
    assert _dv("5511") == [{"d": "2026-07-09", "t": "權息", "k": "s", "c": 3.6, "s": 198.87165021, "p": 79.7}]


def test_dividends_edges():
    d_ = [D(7, 1) + timedelta(days=i) for i in range(10)]
    ev = lambda i, t, p=100.0, k=None: {"i": i, "d": str(d_[i]), "t": t, "p": p, "r": p - 2, **({"k": k} if k else {})}
    off = lambda i, t, a=(2.0, 2.0, None), p=100.0: {"d": d_[i], "t": t, "p": p, "r": p - 2, "src": "TWT49U", "a": a}
    c = [100.0, 100.0, None, 97.0, 99.99, 100.0, 101.0, 95.0, 96.0, 97.0]
    # 除息日當天沒有成交、無成交日也算天數
    assert export.dividends(d_, c, [ev(2, "息")], [off(2, "息")]) == [{"d": str(d_[2]), "t": "息", "c": 2.0, "p": 100.0, "f": str(d_[5]), "n": 4}]
    # 當天就填息
    assert export.dividends(d_, [98.0] * 3 + [100.0] * 7, [ev(3, "息")], [])[0] == {"d": str(d_[3]), "t": "息", "p": 100.0, "f": str(d_[3]), "n": 1}
    # 沒有官方金額（對不到）：沒有 c、s、a；最後一天才除息且未填息
    assert export.dividends(d_, c, [ev(9, "息")], [off(8, "息")]) == [{"d": str(d_[9]), "t": "息", "p": 100.0}]
    # 停止原因：填息前遇到之後的股本變動；同一天又填息又股本變動 → 不再比較；只有現增（k=c）不算
    for t, k, word in (("減", None, "減資"), ("面", None, "面額變更"), ("調", None, "股本變動"), ("權", "s", "配股"),
                       ("權", "sc", "除權"), ("權", None, "除權"), ("權息", "sc", "除權息"), ("權息", None, "除權息")):
        dv = export.dividends(d_, c, [ev(2, "息"), ev(5, t, 100.0, k)], [off(2, "息")])
        assert dv[0] == {"d": str(d_[2]), "t": "息", "c": 2.0, "p": 100.0, "x": [str(d_[5]), word]}, (t, k, dv)
    dv = export.dividends(d_, c, [ev(2, "息"), ev(4, "權", 100.0, "c")], [off(2, "息")])
    assert dv == [{"d": str(d_[2]), "t": "息", "c": 2.0, "p": 100.0, "f": str(d_[5]), "n": 4}]          # 現增不列、不停
    # 自己這一列是權息：不被自己停住
    dv = export.dividends(d_, c, [ev(2, "權息", 100.0, "sc")], [off(2, "權息", (5.0, None, None))])
    assert dv == [{"d": str(d_[2]), "t": "權息", "k": "sc", "a": 5.0, "p": 100.0, "f": str(d_[5]), "n": 4}]
    # a 只在沒有現金股利時輸出；配股 0 不輸出；上櫃權息有 c、s
    dv = export.dividends(d_, c, [ev(2, "權息", 100.0, "s")], [off(2, "權息", (3.0, 2.0, 0.0))])
    assert dv[0] == {"d": str(d_[2]), "t": "權息", "k": "s", "c": 2.0, "p": 100.0, "f": str(d_[5]), "n": 4}
    # 對應官方事件要同一列、同類型、同前收與參考價
    assert "c" not in export.dividends(d_, c, [ev(2, "息")], [off(2, "息", p=101.0)])[0]
    # 列入的類型：息、權息、權（k=s、sc）；權（k=c 或不明）、減、面、調不列
    assert [r["t"] for r in export.dividends(d_, c, [ev(1, "權", 100.0, "c"), ev(2, "權"), ev(3, "減"), ev(4, "面"), ev(5, "調"),
                                                    ev(6, "權", 100.0, "sc")], [])] == ["權"]
    assert export.dividends(d_, c, [], []) == []
    # 純配股：之後收盤回到前收也不算填權
    assert export.dividends(d_, c, [ev(2, "權", 100.0, "s")], [off(2, "權", (3.0, None, None))]) == [
        {"d": str(d_[2]), "t": "權", "k": "s", "a": 3.0, "p": 100.0}]
    # 事件在資料第一列：_price_events 不收（沒有前一天），所以不會出現在 dv
    ev0, _ = export._price_events(d_, c, [0.0] * 10, "TWSE", [off(0, "息")])
    assert ev0 == [] and export.dividends(d_, c, ev0, [off(0, "息")]) == []


def test_export_source():
    for s in ('"dv": dividends(d_, c, ev, events.get(code, [])),',
              '"n": [round(x / 1000) if x is not None else None for x in total]},',
              "e.div_total, e.div_cash, e.stock_div", "for code, d, t, p, r, src, dr, *amt in cur.execute(",
              '"a": tuple(None if x is None else float(x) for x in amt)})',
              '"ev": [{k: e[k] for k in ("d", "t", "p", "r", "k") if k in e} for e in ev],'):
        assert s in SRC, s
    etf = SRC[SRC.index("def etf_export"):]
    etf = etf[:etf.index("\ndef ")]
    assert "dividends(d_, c, ev, " not in etf and "etf_dividends(d_, c, events, gx)" in etf   # 第 36 輪：ETF 用官方除息表 etf_events（使用者同意改；原為 D37-4 只入表）


# ─── node：stock.js ─────────────────────────────────────
def _grab(src, name):
    m = re.search(rf"^(?:async )?function {name}\(", src, re.M)
    if m:
        i, n = src.index("{", src.index(")", m.start())), 0
        for j in range(i, len(src)):
            n += {"{": 1, "}": -1}.get(src[j], 0)
            if n == 0:
                return src[m.start():j + 1]
    m = re.search(rf"^const {name}\b", src, re.M)
    assert m, name
    lines = src[m.start():].splitlines()
    k = next(i for i, l in enumerate(lines) if re.sub(r"\s+//[^'`]*$", "", l).rstrip().endswith(";"))
    return "\n".join(lines[:k + 1])


PF = ("if (!Array.prototype.at) Array.prototype.at = function (i) { return this[i < 0 ? this.length + i : i]; };\n"     # node 14
      "if (!String.prototype.replaceAll) String.prototype.replaceAll = function (a, b) { return this.split(a).join(b); };\n")


def _node(js):
    node = shutil.which("node")
    if not node:
        print("  （沒有 node，略過執行）")
        return None
    return json.loads(subprocess.run([node, "-e", PF + js], capture_output=True, text=True, check=True).stdout)


def test_js_dividend_card():
    js = "\n".join(_grab(APP, n) for n in ("fmt", "pfmt", "md", "noteHTML")) + "\n" + \
        "\n".join(_grab(STK, n) for n in ("EV_LABEL", "dfmt", "divHTML")) + """
const App = { latest: { date: '2026-11-13' } };
const P = { d: ['2025-10-30', '2026-11-12', '2026-11-13'], c: [90, 80, 100] }, S = { d: P.d, c: [90, 80, null] };
const dv = [{ d: '2026-06-10', t: '息', c: 5.24042, p: 160, f: '2026-08-28', n: 56 }, { d: '2026-07-01', t: '息', c: 1, p: 50, f: '2026-07-01', n: 1 },
  { d: '2026-03-26', t: '息', c: 4.8, p: 120.5, x: ['2026-07-16', '配股'] }, { d: '2026-07-16', t: '息', c: 5.7, p: 125 },
  { d: '2026-07-06', t: '權息', k: 'sc', a: 5.36055, p: 92.9, f: '2026-08-11', n: 26 }, { d: '2026-09-02', t: '權', k: 's', a: 5185.002642, p: 7800 }];
const tpex = [{ d: '2026-07-16', t: '權', k: 's', c: 0, s: 100.00000916, p: 117 }, { d: '2026-07-09', t: '權息', k: 's', c: 3.6, s: 198.87165021, p: 79.7 }];
console.log(JSON.stringify([divHTML([], 'TWSE', P), divHTML(dv, 'TWSE', P), divHTML(dv.slice(3, 4), 'TWSE', S), divHTML(tpex, 'TPEx', P)]));"""
    o = _node(js)
    if o is None:
        return
    empty, tw, stop, tp = o
    assert "2025-10-30 起沒有除權息紀錄" in empty and "<table" not in empty and "<h2>股利與填息</h2>" in empty
    assert "<th>除權息日</th><th>現金股利<br>（元）</th><th>配股<br>每千股</th><th>除權息<br>前收盤</th><th>填息</th>" in tw
    rows = re.findall(r"<tr><td>(.*?)</tr>", tw)
    assert [r[:10] for r in rows] == ["2026/09/02", "2026/07/06", "2026/07/16", "2026/03/26", "2026/07/01", "2026/06/10"]   # 新到舊
    assert "08/28<span>第 56 個交易日</span>" in tw and "當天<span>第 1 個交易日</span>" in tw
    assert "不再比較<span>07/16 配股後</span>" in tw and "尚未填息<span>還差 25.00 元，+25.00%</span>" in tw
    assert "2026/07/06<span>除權息</span>" in tw and "上市除權息的官方表只有權值＋息值合計 5.36055 元，無法拆分現金與配股" in tw
    assert '<span title="純配股不計算填權">--</span>' in tw and "權值＋息值 5,185.002642 元\">有</span>" in tw
    assert '<td class="num">5.2404</td>' in tw and '<td class="num">160</td>' in tw                                      # 最多 4 位、去尾 0
    assert "尚未填息<span>還差 45.00 元，+56.25%，最後成交 11/12</span>" in stop                                          # 停牌：寫最後成交
    assert '<td class="num">100.00</td>' in tp and '<td class="num">198.87</td>' in tp and '<td class="num">3.6</td>' in tp
    assert "<span>除權</span></td><td class=\"num\"><span>--</span></td>" in tp                                          # 上櫃純配股：現金 0 → --
    # 卡片在基本面分頁、季報卡之後；說明用變數傳入（test_iter13 數 noteHTML 字面呼叫）
    i = STK.index("${data.dv ? divHTML(data.dv, data.market, P) : ''}")
    assert STK.index("<h2>季報</h2>") < i < STK.index("<section class=\"sec card\">", i) and "noteHTML(short, full)" in _grab(STK, "divHTML")
    assert len(re.findall(r"noteHTML\((['`])(.+?)\1,", APP + STK)) == 8


def test_js_insti_net():
    lines = [l.strip() for l in STK.splitlines() if l.strip().startswith(("const has = I?.f[i] != null", "const inst = { f: has", "inst.net = has"))]
    assert len(lines) == 3 and "I.n?.[i] ??" in lines[2]
    js = "function net(I, i) {\n" + "\n".join(lines) + "\nreturn inst.net; }\n" + """
const I = { f: [10, 3, null], t: [null, 1, null], dl: [2, null, null], n: [13, null, null] }, Old = { f: [10], t: [1], dl: [2] };
console.log(JSON.stringify([net(I, 0), net(I, 1), net(I, 2), net(Old, 0), net(undefined, 0)]));"""
    o = _node(js)
    if o is not None:
        assert o == [13, 4, None, 13, None]                     # 官方合計；n 為 null 時三者相加；舊 JSON 沒有 n；ETF 沒有法人
    assert "const NET_TIP = '合計 = 官方三大法人合計" in STK and "合計${mode === '日' ? '' : '（每日相加）'}" in STK


# ─── F24-7a：收集紀錄的事件筆數 ─────────────────────────
class EvWorld(World):
    """事件端點：TWT49U 回 3 檔股票（含 1 列現增）、2 檔 ETF；其他三個端點沒有資料。"""

    def http(self, method, url, timeout=30, params=None, data=None, json=None):
        if "TWT49U" in url and "TWT49U" not in self.down:
            self.requests.append(("/rwd/zh/exRight/TWT49U", params or {}))
            keep = [r for r in T49["data"] if r[1] in ("2421", "6669")] + [r for r in T49["data"] if r[1] == "0056"][:2]
            return t3.Resp({"stat": "OK", "fields": T49["fields"], "data": keep})
        return super().http(method, url, timeout, params, data, json)


def test_detail_events_count():
    w = EvWorld(D(10, 30))
    w.publish(t3.FIRST_DAY)
    rc, out = t3.run_world(w, T(11, 2, 18, 0))
    und = json.loads(w.runs[-1][2])["undated"]
    assert rc == 0 and und["events_to"] == "2026-11-02" and und["events"] == {"stocks": 4, "etfs": 2}
    assert "股票 4 筆、ETF 2 筆" in out and "price_events" in w.merges and "etf_events" in w.merges
    # 端點失敗：沒有 events_to、events，errors 有 events
    w = EvWorld(D(10, 30))
    w.publish(t3.FIRST_DAY)
    w.down.add("TWT49U")
    rc, out = t3.run_world(w, T(11, 2, 18, 0))
    d = json.loads(w.runs[-1][2])
    assert rc == 1 and "events" in d["errors"] and "events" not in d["undated"] and "events_to" not in d["undated"]


# ─── F24-7b：check 的新行 ───────────────────────────────
def test_check_lines():
    now = T(11, 3, 10, 0)
    days = health.due_days(now, 20, CLOSED)
    snap = t3._full_snapshot(days)
    base = {"alerts_at": datetime(2026, 11, 2, 19, 35), "events_to": D(11, 2), "revenue_on": D(11, 2), "collected_at": None,
            "last_run": {"at": datetime(2026, 11, 2, 19, 35), "command": "catch-up", "new_data": True}}
    ok = lambda s: health.check_report(days, snap, now, s, CLOSED)
    text, rc = ok({})
    assert rc == 0 and "除權息事件最後成功：尚無執行紀錄" in text
    text, rc = ok(base)                                                                 # 舊格式：沒有時間與筆數
    assert rc == 0 and "除權息事件最後成功：至 2026-11-02\n" in text + "\n"
    s = dict(base, events_at=datetime(2026, 11, 2, 19, 36), events_n={"stocks": 1678, "etfs": 1138},
             warnings=["官方休市表更新失敗（沿用已存的官方表）：HTTP 500"])
    text, rc = ok(s)
    lines = text.splitlines()
    assert rc == 0 and "除權息事件最後成功：至 2026-11-02（2026-11-02 19:36），股票 1,678 筆、ETF 1,138 筆（含往回 7 天重查）" in lines
    assert "⚠️  最後一次收集的警告：官方休市表更新失敗（沿用已存的官方表）：HTTP 500" in lines
    i = lines.index("除權息事件最後成功：至 2026-11-02（2026-11-02 19:36），股票 1,678 筆、ETF 1,138 筆（含往回 7 天重查）")
    assert lines[i - 1].startswith("處置／注意股最後成功") and i > 2 and i < len(lines) - 1 and "無異常" in text
    old = ok(base)[0].splitlines()
    assert not any(l.startswith("❌") for l in lines) and lines[:i] + lines[i + 2:] == [l for l in old if not l.startswith("除權息事件")]   # 其他行不變


class _Cur:
    def __init__(self, rows):
        self.rows = rows

    def execute(self, *a):
        return self

    def fetchall(self):
        return self.rows


def test_load_state_new_keys():
    j = lambda **k: json.dumps(k)
    rows = [(datetime(2026, 11, 3, 21, 45), 0, j(undated={}, warnings=["官方休市表更新失敗"]), "catch-up", "ok", None),
            (datetime(2026, 11, 3, 19, 30), 1, j(undated={"events_to": "2026-11-03", "events": {"stocks": 5, "etfs": 2}}), "catch-up", "abnormal", None),
            (datetime(2026, 11, 2, 19, 30), 1, j(undated={"events_to": "2026-11-02"}), "catch-up", "ok", 25.1)]
    s = health.load_state(_Cur(rows))
    assert s["events_to"] == D(11, 3) and s["events_at"] == datetime(2026, 11, 3, 19, 30) and s["events_n"] == {"stocks": 5, "etfs": 2}
    assert s["warnings"] == ["官方休市表更新失敗"] and s["export_failed"] is True
    s = health.load_state(_Cur(rows[1:2] + [rows[2][:5] + (25.1,)]))
    assert s["export_failed"] is True and s["warnings"] == []
    s = health.load_state(_Cur([rows[0], (datetime(2026, 11, 3, 19, 30), 1, j(undated={}), "catch-up", "abnormal", 24.0)]))
    assert s["export_failed"] is False                                                  # 有匯出耗時：匯出成功（異常是資料集）
    s = health.load_state(_Cur([r[:4] for r in rows]))                                 # 舊的 4 欄、3 欄假資料
    assert s["export_failed"] is False and s["events_n"] == {"stocks": 5, "etfs": 2}
    s = health.load_state(_Cur([r[:3] for r in rows[2:]]))
    assert s["export_failed"] is False and s["events_n"] is None and s["events_at"] == datetime(2026, 11, 2, 19, 30)
    s = health.load_state(_Cur([]))
    assert s["export_failed"] is None and s["events_n"] is None and s["warnings"] == []


# ─── F24-7d（QA-03）：只有上櫃公布時不重複匯出 ──────────────
def test_qa03_tpex_only():
    with tempfile.TemporaryDirectory() as tmp:
        site = Path(tmp)
        w = World(D(10, 30))
        t3.run_site(w, T(10, 30, 22, 0), site)
        twse = ("MI_INDEX", "BWIBBU_d", "fund/T86", "BFI82U", "MI_MARGN", "TWT93U")
        w.publish(t3.FIRST_DAY, *twse)
        rc, _, L = t3.run_site(w, T(11, 2, 17, 0), site, T(11, 2, 17, 1))
        assert w.exports == 1 and L["date"] == "2026-11-02" and t3.FIRST_DAY not in w.rows["prices.TWSE"]
        for h in (17, 18):
            rc, out, _ = t3.run_site(w, T(11, 2, h, 30), site, T(11, 2, h, 31))
            assert w.exports == 1 and "沒有新資料，不匯出" in out, h
        for ep in twse:
            w.published[ep].add(t3.FIRST_DAY)
        rc, _, L = t3.run_site(w, T(11, 2, 19, 30), site, T(11, 2, 19, 31))
        assert rc == 0 and w.exports == 2 and t3.FIRST_DAY in w.rows["prices.TWSE"]
        rc, out, _ = t3.run_site(w, T(11, 2, 20, 0), site, T(11, 2, 20, 1))
        assert w.exports == 2


# ─── F24-7e（QA-09）：匯出失敗後下一次補匯出 ────────────────
class Cursor24(t3.FakeCursor):
    """collect_runs 回 6 欄（含 outcome、export_seconds）；種子紀錄視為已匯出成功。"""

    def execute(self, sql, *params):
        w = self.w
        meta = w.__dict__.setdefault("meta24", {})
        if "FROM collect_runs" in sql:
            self.result = [(f, n, d, "catch-up", *meta.get(i, ("ok", 1.0))) for i, (f, n, d) in enumerate(w.runs, 1)][::-1]
            return self
        super().execute(sql, *params)
        if sql.startswith("INSERT INTO collect_runs"):
            meta[len(w.runs)] = (params[3], None)
        elif sql.startswith("UPDATE collect_runs"):
            meta[params[2]] = (params[0], params[1])
        return self


def _run24(w, now, export_error=None, no_export=False):
    def exporter():
        w.exports += 1
        if export_error:
            raise export_error
        return 1.0
    buf = io.StringIO()
    with t3.env(w), mock.patch.object(t3, "FakeCursor", Cursor24), mock.patch.object(export, "export_all", exporter), \
            contextlib.redirect_stdout(buf):
        rc = catchup.run(now=now, no_export=no_export)
    return rc, buf.getvalue()


def test_qa09_retry_export():
    # 處置股有新資料（只有沒有日期的資料變動）、匯出失敗 → 下一次（沒有新資料、狀態沒變）補匯出；補匯出又失敗 → 再下一次繼續補；成功後不再匯出
    def counts(*seq):
        return mock.patch.object(catchup, "_undated_counts", mock.Mock(side_effect=list(seq) + [seq[-1]] * 40))
    w = World(D(10, 30))
    with mock.patch.object(catchup, "collect_alerts", lambda: None), counts((1,), (2,)):
        rc, out = _run24(w, T(10, 31, 10, 0), export_error=OSError("磁碟已滿"))
        assert rc == 1 and w.exports == 1 and "匯出失敗" in out and w.runs[-1][1] == 1 and w.meta24[len(w.runs)] == ("abnormal", None)
        rc, out = _run24(w, T(10, 31, 11, 0), export_error=OSError("磁碟已滿"))
        assert rc == 1 and w.exports == 2 and w.runs[-1][1] == 0 and w.meta24[len(w.runs)] == ("abnormal", None)
        rc, out = _run24(w, T(10, 31, 12, 0))
        assert rc == 0 and w.exports == 3 and w.meta24[len(w.runs)] == ("ok", 1.0)
        rc, out = _run24(w, T(10, 31, 13, 0))
        assert rc == 0 and w.exports == 3 and "沒有新資料，不匯出" in out
    # --no-export 那次不補，下一次補
    w = World(D(10, 30))
    with mock.patch.object(catchup, "collect_alerts", lambda: None), counts((1,), (2,)):
        _run24(w, T(10, 31, 10, 0), export_error=OSError("磁碟已滿"))
        rc, out = _run24(w, T(10, 31, 11, 0), no_export=True)
        assert w.exports == 1
        rc, out = _run24(w, T(10, 31, 12, 0))
        assert rc == 0 and w.exports == 2
    # 沒有新資料、上次匯出成功（env 之下）：0 次匯出（舊行為不變）
    w = World(D(10, 30))
    rc, out = _run24(w, T(10, 31, 10, 0))
    assert rc == 0 and w.exports == 0


# ─── F24-7c：訊息 ───────────────────────────────────────
def test_qa07_messages():
    w = World(D(12, 24))
    rc, out = t3.run_world(w, T(12, 25, 18, 0), date_=D(12, 25))
    assert "休市日沒有要抓的資料，不需要請求" in out and "最近 0 個交易日" not in out
    w = World(D(10, 30))
    w.rows["index.TPEX"] = {d: r for d, r in w.rows["index.TPEX"].items() if d.month == 10}
    buf = io.StringIO()
    with t3.env(w), contextlib.redirect_stdout(buf):
        assert history.run_history(D(9, 29), D(10, 30), ("tpex_index",)) is True
    assert "待抓 1 個月" in buf.getvalue() and "✅ 成功：1 個月" in buf.getvalue() and "待抓 0 天" not in buf.getvalue()
    fetch._dead_hosts.clear()
    with mock.patch.object(fetch._SESSION, "request", lambda *a, **k: t3.Resp(status=500)), mock.patch.object(fetch, "RETRY_BACKOFF", (30,)), \
            mock.patch.object(fetch, "MIN_INTERVAL", {}), mock.patch.object(fetch, "DEFAULT_INTERVAL", 0), \
            mock.patch.object(fetch.time, "sleep", lambda s: None), contextlib.redirect_stdout(io.StringIO()):
        for isolated, words in ((True, ("附屬查詢失敗（不重試，收集繼續）",)), (False, ("連續失敗，可能已被封鎖",))):
            try:
                fetch.request("GET", "https://www.twse.com.tw/x", isolated=isolated)
                assert False
            except FetchError as e:
                assert all(x in str(e) for x in words) and (not isolated or "封鎖" not in str(e)), str(e)
    fetch._dead_hosts.clear()


# ─── F24-7f：events 加鎖 ────────────────────────────────
def test_events_lock():
    from twstock import __main__ as cli
    calls, rel = [], []

    def run(lock, effect=None):
        calls.clear()
        rel.clear()

        def fake(s, e):
            calls.append((s, e))
            if effect:
                raise effect
            return {"stocks": 0, "etfs": 0}
        buf = io.StringIO()
        with mock.patch.object(db, "acquire_lock", lambda: "L" if lock else None), mock.patch.object(db, "release_lock", rel.append), \
                mock.patch.object(events, "collect_events", fake), mock.patch.object(db, "connect", mock.Mock(side_effect=AssertionError)), \
                mock.patch.object(fetch._SESSION, "request", mock.Mock(side_effect=AssertionError)), contextlib.redirect_stdout(buf):
            rc = cli.main(["events", "--start", "2026-11-07", "--end", "2026-11-14"])
        return rc, buf.getvalue()
    rc, out = run(False)
    assert rc == 1 and calls == [] and rel == [] and "另一個收集程序正在執行" in out
    assert run(True) == (0, "") and calls == [(D(11, 7), D(11, 14))] and rel == ["L"]
    rc, out = run(True, FetchError("www.twse.com.tw 連續失敗"))
    assert rc == 1 and rel == ["L"] and "MERGE 覆寫" in out
    try:
        run(True, RuntimeError("x"))
        assert False
    except RuntimeError:
        assert rel == ["L"]


# ─── 用詞、README ───────────────────────────────────────
def test_no_advice_words():
    seg = _grab(STK, "divHTML") + _grab(STK, "NET_TIP") + _grab(STK, "dfmt")
    seg += "".join(l[l.index("第 24 輪"):] for l in README.splitlines() if "第 24 輪" in l)
    assert seg.count("第 24 輪") >= 4, seg.count("第 24 輪")
    for w in ("買進", "賣出", "反彈", "見底", "買點", "超賣", "超買", "推薦", "強勢股", "飆股", "勝率",
              "利多", "利空", "看多", "看空", "轉強", "轉弱",
              "跑贏", "跑輸", "強於大盤", "弱於大盤", "贏過", "輸給", "領先", "落後", "抗跌", "超額報酬", "獲利能力佳", "惡化",
              "填息行情", "貼息", "填息機率", "配息穩定", "高殖利率首選", "存股"):
        assert w not in seg, w
    for s in ("etf_events", "div_total", "stock_div", "insti.n"):
        assert s in README, s


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_") and callable(f):
            f()
            print("ok", n)
