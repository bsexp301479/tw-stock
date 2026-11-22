"""第 43 輪（不連網、不連資料庫）：F43-1 集保股權分散收集（share_distribution）、F43-2 匯出 sh、F43-3 籌碼分頁「股權分散」4 卡＋2 張週圖。
OD 是 2026-11-22 分析師實測 getOD.ashx?id=1-5 原始回應（20261120）的節錄：7 個代號各 17 列，欄位、空白、數字不變（每個代號的「人數,股數,比例」以 ; 相連，
組回 CSV 時補上資料日、代號、分級與 CRLF）；標「假資料」的不是官方資料。收集流程沿用 test_iter03 的 World；有 node 時逐字取出 stock.js 的程式執行（node 14 可跑）。
檢查函式都接受要檢查的函式或原始碼，test_contrast 把程式改壞後重跑，確認會失敗。"""
import contextlib
import hashlib
import inspect
import io
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
import test_iter03 as t3  # noqa: E402
import test_iter28 as t28  # noqa: E402
import test_iter40 as t40  # noqa: E402
from twstock import db, export, fetch, health, tradingcal  # noqa: E402
from twstock.collectors import catchup, tdcc  # noqa: E402
from twstock.fetch import SchemaError  # noqa: E402

D, TM, CLOSED = t3.D, t3.T, t3.CLOSED | {date(2027, 1, 1)}
STK, HTML = t28.STK, (ROOT / "site" / "index.html").read_text(encoding="utf-8")
HEAD = "﻿資料日期,證券代號,持股分級,人數,股數,占集保庫存數比例%"
OD = {  # 檔案順序：000218（is_etf_code 為真、etfs 表沒有）、ETF、ETF（代號補 2 個空白）、受益證券、股票、股票、特別股
    "000218": "0,0,0.00;0,0,0.00;0,0,0.00;0,0,0.00;0,0,0.00;0,0,0.00;0,0,0.00;0,0,0.00;0,0,0.00;0,0,0.00;0,0,0.00;0,0,0.00;0,0,0.00;0,0,0.00;1,422278902,100.00;0,0,0.00;1,422278902,100.00",
    "00406A": "22555,7404057,0.03;214185,578311907,2.58;106407,898883581,4.02;49807,654390265,2.92;46184,872616679,3.90;49115,1294736819,5.79;28516,1041710036,4.65;23542,1113909909,4.98;51271,3826704709,17.11;27079,3857334998,17.25;11167,3127858324,13.98;2937,1449373681,6.48;1111,780499456,3.49;578,524261857,2.34;958,2408389925,10.77;10,77324203,0.34;635412,22359062000,100.00",
    "0050  ": "1644997,502311489,1.96;1553803,3563667803,13.95;395572,2906308037,11.38;161752,2004505144,7.85;87589,1546787207,6.05;83050,2044451357,8.00;39177,1367223846,5.35;21523,971454395,3.80;35463,2427218738,9.50;11270,1511012469,5.91;2887,771396075,3.02;534,257872834,1.01;157,109587125,0.42;61,55572211,0.21;302,5491706174,21.50;4,74904,0.00;4038137,25531000000,100.00",
    "01001T": "46,5917,0.00;557,1334147,0.22;179,1610277,0.27;57,781466,0.13;86,1659833,0.28;78,2100462,0.36;35,1288000,0.22;58,2822000,0.48;109,8863500,1.52;46,7183000,1.23;36,10475000,1.79;27,13576000,2.32;5,3327398,0.57;4,3890000,0.66;28,524083000,89.89;0,0,0.00;1351,583000000,100.00",
    "2330  ": "2740735,326779743,1.26;481835,922329783,3.55;55675,397398274,1.53;18232,223326194,0.86;8495,149208138,0.57;8048,196800644,0.75;3736,129784255,0.50;2091,94278134,0.36;4193,292288142,1.12;2062,288386866,1.11;1332,373477762,1.44;577,281112919,1.08;339,235160967,0.90;224,201266777,0.77;1469,21820989424,84.14;7,217955,0.00;3329043,25932370067,100.00",
    "2421  ": "32045,2313502,0.80;18196,31718248,11.05;1471,10972883,3.82;416,5138572,1.79;245,4447526,1.54;203,5059665,1.76;105,3625632,1.26;59,2700483,0.94;104,7465065,2.60;82,11861260,4.13;69,19915810,6.94;32,15787769,5.50;16,11260432,3.92;6,5539654,1.93;46,149137168,51.97;0,0,0.00;53095,286943669,100.00",
    "2881A ": "11034,1859129,0.30;5308,11439171,1.90;871,6477838,1.07;221,2769478,0.46;168,3090863,0.51;132,3423213,0.57;87,3076779,0.51;60,2810228,0.46;123,8866475,1.47;40,5587229,0.93;25,7433000,1.23;14,6754000,1.12;7,4885000,0.81;4,3681931,0.61;43,527845666,87.97;0,0,0.00;18137,600000000,100.00"}


def lines(d="20261120", od=None):
    return [f"{d},{c},{i},{x}" for c, v in (od or OD).items() for i, x in enumerate(v.split(";"), 1)]


def csv_text(ls=None, head=HEAD):
    return "\r\n".join([head] + (lines() if ls is None else ls)) + "\r\n"


def raw(code):
    v = [x.split(",") for x in OD[code].split(";")]
    return {**{f"n{i}": int(v[i - 1][0]) for i in range(1, 17)}, **{f"s{i}": int(v[i - 1][1]) for i in range(1, 17)},
            "n_total": int(v[16][0]), "s_total": int(v[16][1]), "code": code.strip()}


def edit(code, lv, n=None, s=None):   # 假資料：改節錄中某代號某級的人數或股數
    v = [x.split(",") for x in OD[code].split(";")]
    v[lv - 1][0], v[lv - 1][1] = (str(n) if n is not None else v[lv - 1][0]), (str(s) if s is not None else v[lv - 1][1])
    return lines(od=dict(OD, **{code: ";".join(",".join(x) for x in v)}))


# ─── 解析（驗收 1～3）──────────────────────────────────────
def check_parse(parse=tdcc.parse_tdcc):
    bad = []
    d, rows, skipped = parse(csv_text().lstrip("﻿"))
    by = {r["code"]: r for r in rows}
    if d != D(11, 20) or list(by) != ["000218", "00406A", "0050", "2330", "2421"] or skipped:
        bad.append(("保留的代號", d, list(by), skipped))
    bad += [c for c in ("00406A", "0050  ", "2421  ", "2330  ") if by.get(c.strip()) != raw(c)]
    for name, ls in (("17 級人數 +1", edit("2421  ", 17, n=53096)), ("16 級股數不平", edit("2421  ", 16, s=5)), ("17 級股數 0", edit("2421  ", 17, s=0)),
                     ("人數 1.5", edit("2421  ", 3, n="1.5")), ("人數負數", edit("2421  ", 3, n=-1))):
        d, rows, skipped = parse(csv_text(ls).lstrip("﻿"))
        if skipped != 1 or [r["code"] for r in rows] != ["000218", "00406A", "0050", "2330"]:
            bad.append((name, skipped, [r["code"] for r in rows]))
    ls = lines()
    schema = {"表頭少一欄": csv_text(head=HEAD.rsplit(",", 1)[0]), "表頭改名": csv_text(head=HEAD.replace("人數", "股東數")),
              "兩個資料日": csv_text(ls[:17] + lines("20261127")[17:]), "缺 9 級": csv_text(ls[:8] + ls[9:]),
              "3 級重複": csv_text(ls[:17] + [ls[19]] + ls[17:]), "0 列": csv_text([]), "某列 5 欄": csv_text(ls[:40] + [ls[40].rsplit(",", 1)[0]] + ls[41:])}
    for name, text in schema.items():
        try:
            parse(text.lstrip("﻿"))
            bad.append(name)
        except SchemaError:
            pass
    return bad


def test_parse():
    assert check_parse() == []


# ─── 寫入（驗收 4、5）──────────────────────────────────────
class Conn(t40.Conn):
    def execute(self, sql, *p):
        self.sql.append((sql, p))
        return self

    def fetchall(self):
        return [(False,), (False,), (True,), (True,)]       # 假資料庫：2330、2421 命中 stocks，00406A、0050 命中 etfs（000218 被 WHERE 擋掉）


def _resp(text):
    r = t3.Resp()
    r.content = text.encode("utf-8")
    return r


def check_write(collect=tdcc.collect_tdcc):
    bad, conns, calls = [], [], []

    def connect():
        conns.append(Conn())
        return conns[-1]

    def run(text, latest):
        buf = io.StringIO()
        req = lambda *a, **k: calls.append((a, k)) or _resp(text)
        with mock.patch.object(tdcc, "request", req), mock.patch.object(db, "connect", connect), contextlib.redirect_stdout(buf):
            return collect(latest, D(11, 23)), buf.getvalue()
    rec, out = run(csv_text(), D(11, 13))
    if rec != {"on": "2026-11-23", "d": "2026-11-20", "s": 2, "e": 2} or out != "  🏦 集保股權分散 2026-11-20：股票 2 檔、ETF 2 檔\n":
        bad.append((rec, out))
    if calls[0] != (("GET", "https://opendata.tdcc.com.tw/getOD.ashx?id=1-5"), {"expect_json": False, "isolated": True}):
        bad.append(("請求", calls[0]))
    sql, p = conns[0].sql[0]
    j = {r["code"]: r for r in json.loads(p[0])}
    if len(conns) != 1 or len(conns[0].sql) != 1 or p[1:] != (D(11, 20), D(11, 20)) or j["0050"]["s_total"] != 25531000000 or '"s_total": 25531000000' not in p[0]:
        bad.append(("參數、BIGINT 不轉浮點", p[1:]))
    for s in ("MERGE share_distribution AS t", "LEFT JOIN stocks st ON st.stock_code = j.code", "LEFT JOIN etfs et ON et.etf_code = j.code",
              "WHERE st.stock_id IS NOT NULL OR et.etf_id IS NOT NULL", "THEN 0 ELSE 1 END AS BIT) AS is_etf", "ON t.code = s.code AND t.data_date = ?",
              "n_total INT, s1 BIGINT", "s16 BIGINT, s_total BIGINT)", "OUTPUT inserted.is_etf;"):
        if s not in sql:
            bad.append(s)
    for latest in (D(11, 20), D(11, 27)):                                  # 官方未更新、回退：不連資料庫
        conns.clear()
        rec, out = run(csv_text(), latest)
        if conns or rec != {"on": "2026-11-23", "d": "2026-11-20"} or out != "  ℹ️  集保股權分散：官方尚未更新（仍是 2026-11-20 那週），明天再試\n":
            bad.append(("未更新", latest, rec, out))
    conns.clear()
    rec, out = run(csv_text(edit("2421  ", 17, n=1)), None)
    if "  🏦 集保股權分散 2026-11-20：股票 2 檔、ETF 2 檔，略過 1 檔（合計不符）\n" != out:
        bad.append(out)
    conns.clear()
    rec, out = run(csv_text([x for x in lines() if ",01001T," in x or ",2881A ," in x]), None)      # 0 列可寫：不連資料庫
    if conns or rec.get("s") != 0 or rec.get("e") != 0 or "股票 0 檔、ETF 0 檔" not in out:
        bad.append(("0 列", rec, out))
    return bad


def test_write():
    assert check_write() == []


# ─── 抓取時機（驗收 6、7、10、17）：情境表，closed 由測試自己組 ──────────────
NO1023 = CLOSED - {D(10, 23)}
SCEN = [  # (#, 現在, latest, tdcc_on, closed, target, 排不排)
    (1, TM(11, 24, 21, 45), None, None, CLOSED, D(11, 16), True), (2, TM(11, 30, 17, 30), D(11, 20), None, CLOSED, D(11, 23), True),
    (3, TM(11, 27, 22, 30), D(11, 20), None, CLOSED, D(11, 16), False), (4, TM(11, 28, 10), D(11, 20), None, CLOSED, D(11, 23), True),
    (5, TM(11, 28, 11), D(11, 20), D(11, 28), CLOSED, D(11, 23), False), (6, TM(11, 29, 10), D(11, 20), D(11, 28), CLOSED, D(11, 23), True),
    (7, TM(12, 1, 17, 30), D(11, 27), None, CLOSED, D(11, 23), False), (8, TM(10, 8, 22, 30), D(10, 2), None, CLOSED, D(9, 28), False),
    (9, TM(10, 9, 17, 30), D(10, 2), None, CLOSED, D(10, 5), True), (9.1, TM(10, 12, 17, 30), D(10, 8), None, CLOSED, D(10, 5), False),
    (10, TM(10, 23, 17, 30), D(10, 16), None, NO1023, D(10, 12), False), (11, TM(10, 24, 10), D(10, 16), None, NO1023, D(10, 19), True),
    (11.1, TM(10, 27, 18), D(10, 22), None, NO1023, D(10, 19), False), (12, TM(2, 23, 17, 30), D(2, 11), None, CLOSED, D(2, 9), False),
    (13, TM(3, 2, 17, 30), D(2, 11), None, CLOSED, D(2, 23), True), (14, TM(12, 1, 17, 30), D(11, 27), None, CLOSED, D(11, 23), False),
    (15, TM(1, 4, 17, 30, 2027), D(12, 24), None, CLOSED, D(12, 28), True)]


def _plan(now, closed, share, tdcc_on=None):
    st = {"alerts_at": None, "events_to": None, "revenue_on": None, "tdcc_on": tdcc_on}
    return catchup.make_plan(now, 10, t3._full_snapshot(health.due_days(now, 10, closed)), st, closed, {}, share=share)


def check_timing():
    bad = []
    for no, now, latest, on, closed, target, due in SCEN:
        got = tradingcal.last_full_week(now.date(), closed), _plan(now, closed, (True, latest, 0, 0), on)["tdcc"]
        if got != (target, {"latest": latest} if due else None):
            bad.append((no, got))
    st = {"alerts_at": None, "events_to": None, "revenue_on": None}                                   # 舊 state 沒有 tdcc_on、舊呼叫沒有 share
    if catchup.make_plan(TM(11, 28, 10), 10, t3._full_snapshot(health.due_days(TM(11, 28, 10), 10, CLOSED)), st, CLOSED, {})["tdcc"] is not None or _plan(TM(11, 28, 10), CLOSED, (False, None, 0, 0))["tdcc"] is not None:
        bad.append("17 表不存在或舊呼叫不排")
    p = catchup.plan_for_date(D(11, 20), TM(11, 30), False)
    if "tdcc" in p or catchup.plan_is_empty({**_plan(TM(11, 28, 10), CLOSED, None), "tdcc": {"latest": None}}):
        bad.append("16 collect --date 沒有 tdcc；只有 tdcc 也要執行")
    return bad


def test_timing():
    assert check_timing() == []
    main = (ROOT / "twstock" / "__main__.py").read_text(encoding="utf-8") + (ROOT / "twstock" / "collectors" / "history.py").read_text(encoding="utf-8")
    assert "tdcc" not in main and "share_distribution" not in main                          # history、events 子命令不抓


class SdWorld(t3.World):
    """test_iter03 的 World 加上 getOD.ashx（od = 官方檔的資料日）與 share_distribution（table = 表是否存在；latest = 表中最新資料日）。"""

    def __init__(self, seed, latest=None, od=D(11, 20), table=True):
        super().__init__(seed)
        self.latest, self.od, self.table, self.sd = latest, od, table, []
        self.revenue[(2026, 10)] = 1980                                       # 10 月營收已齊：不發營收請求

    def http(self, method, url, timeout=30, params=None, data=None, json=None):
        if "getOD.ashx" not in url:
            return super().http(method, url, timeout, params, data, json)
        self.requests.append(("/getOD.ashx", params or {}))
        return t3.Resp(status=500) if "getOD" in self.down else _resp(csv_text(lines(f"{self.od:%Y%m%d}")))


class SdCursor(t3.FakeCursor):
    def execute(self, sql, *p):
        w = self.w
        if "OBJECT_ID('share_distribution')" in sql:
            self.result = [(1 if w.table else None,)]
        elif "SELECT MAX(data_date) FROM share_distribution" in sql:
            self.result = [(w.latest,)]
        elif "MERGE share_distribution" in sql:
            w.latest = p[1]
            w.sd.append(p[1])
            self.result = [(False,), (False,), (True,)]
        else:
            return super().execute(sql, *p)
        return self


def run_sd(w, now, date_=None, adhoc=tradingcal.AD_HOC):
    w.requests.clear()
    with mock.patch.object(t3.FakeConn, "cursor", lambda self: SdCursor(self.w)), mock.patch.object(tradingcal, "AD_HOC", adhoc):
        rc, out = t3.run_world(w, now, date_=date_)
    return rc, out, len(t3._hit(w, "getOD")), json.loads(w.runs[-1][2])["undated"].get("tdcc")


def check_world():
    bad = []
    w = SdWorld(D(11, 27), latest=D(11, 20))
    rc, out, n, und = run_sd(w, TM(11, 28, 10))                                                # 4：週六補跑，官方仍是 11/20
    if (n, und, w.sd, w.exports, w.runs[-1][1]) != (1, {"on": "2026-11-28", "d": "2026-11-20"}, [], 0, 0) or \
            "  ℹ️  集保股權分散：官方尚未更新（仍是 2026-11-20 那週），明天再試\n" not in out:
        bad.append(("4", n, und, w.exports, out[-300:]))
    if run_sd(w, TM(11, 28, 11))[2:] != (0, None):                                             # 5：同一天不再抓
        bad.append("5")
    w.od = D(11, 27)
    rc, out, n, und = run_sd(w, TM(11, 29, 10))                                                # 6：隔天再試，寫入 11/27
    if (n, und, w.sd, w.exports, w.runs[-1][1]) != (1, {"on": "2026-11-29", "d": "2026-11-27", "s": 2, "e": 1}, [D(11, 27)], 1, 1) or \
            "  🏦 集保股權分散 2026-11-27：股票 2 檔、ETF 1 檔\n" not in out:
        bad.append(("6", n, und, w.exports))
    w = SdWorld(D(11, 27), latest=D(11, 20), od=D(11, 27))
    if run_sd(w, TM(11, 30, 17, 30))[2:] != (1, {"on": "2026-11-30", "d": "2026-11-27", "s": 2, "e": 1}):   # 2：週一
        bad.append("2")
    w = SdWorld(D(11, 27), latest=D(11, 20), od=D(11, 27))
    if run_sd(w, TM(11, 30, 18), date_=D(11, 27))[2:] != (0, None):                            # 16：collect --date
        bad.append("16")
    w = SdWorld(D(10, 22), latest=D(10, 16), od=D(10, 22))                                     # 11：颱風休市事前不在 closed
    a = run_sd(w, TM(10, 24, 10), adhoc=set())[2:]
    b = run_sd(w, TM(10, 27, 18), adhoc=set())[2:]
    if a != (1, {"on": "2026-10-24", "d": "2026-10-22", "s": 2, "e": 1}) or b != (0, None):
        bad.append(("11", a, b))
    w = SdWorld(D(11, 27), table=False)                                                        # 17：表不存在
    rc, out, n, und = run_sd(w, TM(11, 28, 10))
    if n or und or "集保" in out or "share_distribution" in w.merges:
        bad.append(("17", n, out[-300:]))
    return bad


def test_world():
    assert check_world() == []


def check_isolation():
    base = SdWorld(D(11, 27), table=False)
    rc0, _, _, _ = run_sd(base, TM(11, 30, 17, 30))
    w = SdWorld(D(11, 27), latest=D(11, 20))
    w.down.add("getOD")
    rc, out, n, und = run_sd(w, TM(11, 30, 17, 30))
    d, d0, bad = json.loads(w.runs[-1][2]), json.loads(base.runs[-1][2]), []
    if (rc, w.runs[-1][1], d["items"], w.notices, w.exports) != (rc0, base.runs[-1][1], d0["items"], base.notices, base.exports):
        bad.append(("回傳碼、結果、通知、匯出要和沒有這功能時相同", rc, rc0, w.notices, base.notices))
    if n != 1 or "opendata.tdcc.com.tw" in fetch._dead_hosts or "  ⚠️  tdcc 失敗：opendata.tdcc.com.tw 附屬查詢失敗（不重試，收集繼續）" not in out:
        bad.append(("只打一次、不標記主機", n, fetch._dead_hosts))
    if und or "tdcc" not in d["errors"] or "❌ tdcc" in out or [run_sd(w, TM(11, 30, 18))[2]] != [1]:
        bad.append(("只記錄；同一天下一次再試", und))
    return bad


def test_isolation():
    assert check_isolation() == []


# ─── load_state、check（驗收 11～13）──────────────────────────────
class Rows(t40.Rows):
    def execute(self, sql, *a):
        self.sql = getattr(self, "sql", []) + [sql]
        return self


def check_state(fn=health.load_state):
    j = lambda **k: json.dumps(k)
    rows = [(datetime(2026, 11, 29, 10), 0, j(undated={}), "catch-up", "ok", None),
            (datetime(2026, 11, 28, 11), 0, j(undated={"tdcc": {"on": "2026-11-28", "d": "2026-11-20"}}), "catch-up", "ok", None),
            (datetime(2026, 11, 23, 22), 1, j(undated={"tdcc": {"on": "2026-11-23", "d": "2026-11-20", "s": 1992, "e": 367}}), "catch-up", "ok", 20.0),
            (datetime(2026, 11, 20, 22), 1, j(undated={"events_to": "2026-11-20"}), "catch-up", "ok", 20.0)]
    cur = Rows(rows)
    got = [fn(cur)["tdcc_on"], fn(Rows(rows[3:]))["tdcc_on"], fn(Rows([]))["tdcc_on"]]
    return [] if got == [D(11, 28), None, None] and len(cur.sql) == 1 and "FROM collect_runs" in cur.sql[0] else [got, cur.sql]


def test_state():
    assert check_state() == []


def check_lines(fn=health.check_report):
    bad = []
    for now, share, line in ((TM(12, 1, 10), (True, D(11, 20), 1992, 367), "集保股權分散最新一週：2026-11-20（股票 1,992 檔、ETF 367 檔）"),
                             (TM(12, 7, 10), (True, D(11, 20), 1992, 367), "集保股權分散最新一週：2026-11-20（股票 1,992 檔、ETF 367 檔），⚠️ 已落後 2 週，漏收的週無法回補"),
                             (TM(12, 1, 10), (True, None, 0, 0), "集保股權分散最新一週：尚無資料"),
                             (TM(12, 1, 10), (False, None, 0, 0), "集保股權分散：尚未建立資料表，請執行一次 python -m twstock setup-db")):
        days = health.due_days(now, 20, CLOSED)
        snap = t3._full_snapshot(days)
        st = {"alerts_at": datetime.combine(days[-1], datetime.min.time()).replace(hour=19), "events_to": days[-1]}
        (t0, rc0), (text, rc) = fn(days, snap, now, st, CLOSED), fn(days, snap, now, st, CLOSED, share=share)
        L = text.splitlines()
        i = L.index(line) if line in L else -1
        if i < 0 or rc != rc0 or not L[i - 1].startswith("除權除息預告") or L[:i] + L[i + 1:] != t0.splitlines() or "集保" in t0:
            bad.append((line, text))
    for d, today, want in ((D(2, 11), D(3, 2), ""), (D(2, 11), D(3, 9), "，⚠️ 已落後 2 週，漏收的週無法回補")):          # 春節整週休市那週不算
        if health.share_line((True, d, 1, 1), today, CLOSED) != f"集保股權分散最新一週：{d}（股票 1 檔、ETF 1 檔）{want}":
            bad.append((d, today))
    w = SdWorld(D(11, 27), table=False)
    buf = io.StringIO()
    with t3.env(w), mock.patch.object(health, "load_snapshot", w.snapshot), contextlib.redirect_stdout(buf):
        rc = health.run_check(20, TM(11, 30, 12))
    if rc != 0 or "集保股權分散：尚未建立資料表，請執行一次 python -m twstock setup-db" not in buf.getvalue() or w.requests:
        bad.append(("run_check", rc))
    return bad


def test_lines():
    assert check_lines() == []


# ─── 匯出（驗收 14～17）──────────────────────────────────────
def _row(r, d=D(11, 20), etf=None):
    return (r["code"], int(r["code"].startswith("00") if etf is None else etf), d, *[r[f"s{i}"] for i in range(1, 16)], r["s_total"], r["n1"],
            *[r[f"n{i}"] for i in range(12, 16)], r["n_total"])


WANT = {"2421": (63.33, 51.97, 13.68, 22.99, 53095, 100, 32045), "2330": (86.91, 84.15, 3.68, 9.41, 3329043, 2609, 2740735),
        "00406A": (23.09, 10.77, 48.36, 28.9, 635412, 5584, 22555), "0050": (23.17, 21.51, 18.45, 58.39, 4038137, 1054, 1644997),
        "000218": (100, 100, 0, 0, 1, 1, 0)}


def check_export(fn=export.share_export):
    bad = []
    stock, etf = fn([_row(r) for r in tdcc.parse_tdcc(csv_text().lstrip("﻿"))[1]])
    for c, v in WANT.items():
        got = (etf if c.startswith("00") else stock).get(c)
        if got != {"d": ["2026-11-20"], **{k: [x] for k, x in zip(("b", "k", "m", "r", "n", "bn", "z"), v)}}:
            bad.append((c, got))
    if set(stock) != {"2330", "2421"} or json.dumps(etf["00406A"]["r"]) != "[28.9]" or json.dumps(etf["000218"]["b"]) != "[100]":
        bad.append(("分流、去尾 0", list(stock), list(etf)))
    base = {**{f"s{i}": 0 for i in range(1, 17)}, **{f"n{i}": 1 for i in range(1, 17)}, "n_total": 15, "s_total": 100000}
    weeks = [date.fromordinal(D(1, 2).toordinal() + 7 * k) for k in range(53)]                                   # 假資料：53 週
    rows = [_row({**base, "code": "9999", "s15": 1005}, d) for d in weeks] + [_row({**base, "code": "8888", "s15": 2}, d) for d in weeks[-3:] if d != weeks[-2]]
    rows += [_row({**base, "code": "00999", "s15": 3}, weeks[-1], etf=1)]
    stock, etf = fn(rows[::-1])
    x = stock["9999"]
    if x["d"] != [str(d) for d in weeks[1:]] or any(len(v) != 52 for v in x.values()) or x["k"][0] != 1.01 or x["b"][0] != 1.01:   # 1.005 進位
        bad.append(("52 週、整數四捨五入", len(x["d"]), x["k"][0]))
    if stock["8888"]["d"] != [str(weeks[-3]), str(weeks[-1])] or "00999" in stock or etf["00999"]["k"] != [0] or fn([]) != ({}, {}):
        bad.append(("缺週不補、ETF 只進 etfp", stock["8888"]["d"]))
    return bad


def test_export():
    assert check_export() == []
    assert export.share_pct(1005, 100000) == 1.01 and export.share_pct(1, 1) == 100 and isinstance(export.share_pct(1, 1), int)


def test_export_wiring():
    src = (ROOT / "twstock" / "export.py").read_text(encoding="utf-8")
    i = src.index('**({"fh": [fhr.get(x) for x in d_]} if (fhr := fh.get(code)) else {}),')
    assert src.index('**({"sh": sh_stock[code]} if code in sh_stock else {}),') > i                                 # 沒有 sh 不輸出鍵，舊檔不變
    assert src.index('                E["nx"] = nx_etf[code]') < src.index('                E["sh"] = sh_etf[code]') < src.index("            _write(p, E)")
    assert src.count("sh_stock") == 3 and src.count("sh_etf") == 3                                                    # 不進 screen.json、latest.json
    assert src.index("eev = _load_etf_events(cur)") < src.index("sh_stock, sh_etf = share_export(_load_share(cur))") < src.index("conn.close()", src.index("eev ="))

    class Cur:
        sql = []

        def execute(self, sql, *p):
            self.sql.append(sql)
            return self

        def fetchone(self):
            return (None,)
    assert export._load_share(Cur()) == [] and Cur.sql == ["SELECT OBJECT_ID('share_distribution')"]                 # 表不存在：不讀表
    assert re.search(r"SELECT DISTINCT TOP \{SH_WEEKS\} data_date FROM share_distribution ORDER BY data_date DESC", inspect.getsource(export._load_share))


def test_setup_db():
    ddl = "\n".join(db.DDL)
    for s in ("IF OBJECT_ID('share_distribution') IS NULL", "CONSTRAINT UQ_share_distribution UNIQUE (code, data_date)", "n16 INT NOT NULL",
              "s16 BIGINT NOT NULL", "s_total      BIGINT        NOT NULL", "n_total      INT           NOT NULL",
              "CREATE INDEX IX_share_distribution_date ON share_distribution(data_date)"):
        assert s in ddl, s
    assert "n17" not in ddl and "ratio" not in ddl[ddl.index("share_distribution"):ddl.index("UQ_share_distribution")]   # 官方比例不存
    for f, words in (("README.md", ("share_distribution", "test_iter43", "集保股權分散")), ("docs/dblayout.md", ("### share_distribution", "UQ_share_distribution"))):
        text = (ROOT / f).read_text(encoding="utf-8")
        assert all(w in text for w in words), f


# ─── 前端（驗收 18～21）──────────────────────────────────────
SH2 = {"d": ["2026-11-20", "2026-11-27"], "b": [63.33, 63.45], "k": [51.97, 52.01], "m": [13.68, 13.6], "r": [22.99, 22.95],   # 假資料（第 2 週）
       "n": [53095, 53407], "bn": [100, 101], "z": [32045, 32210]}
SH1 = {k: v[:1] for k, v in SH2.items()}
SH5 = {"d": ["2026-11-20", "2026-11-27", "2026-12-04", "2026-12-11", "2026-12-18"], "b": [60, 61.5, 62, 62.25, 63], "k": [50, 50, 50, 50, 50],
       "m": [10, 10, 10, 10, 10], "r": [30.1, 30.05, 29.9, 29.8, 29.7], "n": [100, 110, 90, 95, 120], "bn": [5, 5, 5, 5, 6], "z": [1, 1, 1, 1, 2]}
P = "（百分點）"
CARDS = [(SH2, False, [["持股超過 400 張", "63.45%", "", f"<span class=\"nw\">1週 +0.12</span>　<span class=\"nw\">4週 --</span>{P}<br>101 人"], ["持股超過 1,000 張", "52.01%", "", f"<span class=\"nw\">1週 +0.04</span>　<span class=\"nw\">4週 --</span>{P}"],
                       ["50 張以下", "22.95%", "", f"<span class=\"nw\">1週 -0.04</span>　<span class=\"nw\">4週 --</span>{P}"], ["股東人數", "53,407 人", "", "<span class=\"nw\">1週 +312</span>　<span class=\"nw\">4週 --</span>（人）<br>未滿 1 張 32,210 人"]]),
         (SH2, True, "受益人數"),
         (SH1, False, [["持股超過 400 張", "63.33%", "", f"<span class=\"nw\">1週 --</span>　<span class=\"nw\">4週 --</span>{P}<br>100 人"], ["持股超過 1,000 張", "51.97%", "", f"<span class=\"nw\">1週 --</span>　<span class=\"nw\">4週 --</span>{P}"],
                       ["50 張以下", "22.99%", "", f"<span class=\"nw\">1週 --</span>　<span class=\"nw\">4週 --</span>{P}"], ["股東人數", "53,095 人", "", "<span class=\"nw\">1週 --</span>　<span class=\"nw\">4週 --</span>（人）<br>未滿 1 張 32,045 人"]]),
         (SH5, False, [["持股超過 400 張", "63.00%", "", f"<span class=\"nw\">1週 +0.75</span>　<span class=\"nw\">4週 +3.00</span>{P}<br>6 人"], ["持股超過 1,000 張", "50.00%", "", f"<span class=\"nw\">1週 0.00</span>　<span class=\"nw\">4週 0.00</span>{P}"],
                       ["50 張以下", "29.70%", "", f"<span class=\"nw\">1週 -0.10</span>　<span class=\"nw\">4週 -0.40</span>{P}"], ["股東人數", "120 人", "", "<span class=\"nw\">1週 +25</span>　<span class=\"nw\">4週 +20</span>（人）<br>未滿 1 張 2 人"]])]
NOTE_S = "以集保戶每週最後一個營業日的餘額，依身分歸戶後分級；大戶包含外資、法人、ETF 與公司大股東，融資、借券以專戶計。比例 = 各級股數 ÷ 集保庫存合計，增資、減資、合併時會跳動。官方每週公布一次，本站通常在下週一晚上更新；本站從上線起逐週累積，之前的週無法回補。比例的變化只描述持股結構，不代表之後的走勢。"
NOTE_E = "以集保戶每週最後一個營業日的餘額，依身分歸戶後分級；人數為受益人數，大額持有人包含法人、壽險與其他基金。比例 = 各級受益權單位 ÷ 集保庫存合計，申購、贖回時會跳動。官方每週公布一次，本站通常在下週一晚上更新；本站從上線起逐週累積，之前的週無法回補。比例的變化只描述持有結構，不代表之後的走勢。"


def _inner(src, start):
    """renderStock 裡從 start 那行起、到去掉行尾註解後以 ; 或 : ''} 結尾的那幾行。"""
    ls = src[src.index(start):].splitlines()
    k = next(i for i, l in enumerate(ls) if re.sub(r"\s+//[^'`]*$", "", l).rstrip().endswith((";", ": ''}")))
    return "\n".join(ls[:k + 1])


def check_cards(src=STK):
    tpl = _inner(src, "    ${SH ? chipSec('股權分散'")
    js = t28.HELPERS + "\n" + "\n".join([t28._grab(src, "cardsHTML"), t28._grab(src, "shCards"), t28._grab(src, "SH_NOTE"),
                                         _inner(src, "  const chipSec"), _inner(src, "  const chLeg")]) + """
const out = %s.map(([sh, E]) => { const data = sh ? { sh } : {};
%s
  return [sh ? shCards(sh, E) : null, `%s`]; });
console.log(JSON.stringify(out));""" % (json.dumps([[sh, e] for sh, e, _ in CARDS] + [[None, False], [{**SH1, "d": []}, False]]), _inner(src, "  const SH = "), tpl.strip())
    o = t28._node(js)
    if o is None:
        return []
    bad = [(want, got) for (_, _, want), (got, _) in zip(CARDS, o) if want != got and (not isinstance(want, str) or got[3][0] != want)]
    h = [x[1] for x in o]
    if '<h2>股權分散</h2><span class="muted small">資料日 11/27（每週一次，集保結算所）</span>' not in h[0] or 'id="shC"' not in h[0] or \
            "股東人數（人，每週）" not in h[0] or NOTE_S not in h[0] or "受益人數（人，每週）" not in h[1] or NOTE_E not in h[1]:
        bad.append(("2 週", h[0][:300]))
    if 'id="shC"' in h[2] or '<div class="muted small">自 11/20 起收錄，累積 2 週後顯示走勢。</div>' not in h[2] or h[4] or h[5]:
        bad.append(("1 週、沒有 sh", h[2][-300:], h[4], h[5]))
    return bad


def test_cards():
    assert check_cards() == []


def check_charts(src=STK):
    js = t28.HELPERS + "\n" + "\n".join(t28._grab(src, n) for n in ("INVESTORS", "CHIP_I", "disposeKCharts", "adjFactors", "aggregate", "buildChip", "shChart")) + r"""
let charts = [], chipN = '2', chipI = 'f';
const css = () => '#888', created = [], els = {};
const $ = s => s in els ? els[s] : (els[s] = { innerHTML: '' });
const window = { LightweightCharts: { createChart: (el, opt) => {
  const c = { el, opt, ser: [], addHistogramSeries(o) { return this.addLineSeries(o); }, addLineSeries(o) { const s = { o, setData(d) { this.data = d; }, createPriceLine() {} }; this.ser.push(s); return s; },
    timeScale: () => ({ fitContent() {} }), subscribeCrosshairMove(f) { this.cb = f; }, setCrosshairPosition() {}, clearCrosshairPosition() {}, remove() { this.removed = true; } };
  created.push(c); return c; } } };
const D = ['2026-11-09', '2026-11-10', '2026-11-11', '2026-11-12', '2026-11-13'];
const base = { market: 'TWSE', prices: { d: D, o: [10, 11, 12, 13, 14], h: [10, 11, 12, 13, 14], l: [10, 11, 12, 13, 14], c: [10, 11, 12, 13, 14], v: [1, 1, 1, 1, 1], ch: [0, 1, 1, 1, 1] },
  insti: { f: [10, -20, 30, 5, null], t: [1, 1, 1, 1, null], dl: [0, 0, 0, -2, null] }, mg: { mb: [100, 110, 120, 130, 140], sb: [1, 2, 3, 4, 5], lb: [50, 60, 70, null, null] }, ev: [] };
const run = (sh, E) => { created.length = 0; buildChip(Object.assign({}, base, sh ? { sh } : {}), E);
  const wk = created.filter(c => c.el === els['#shC'] || c.el === els['#snC']);
  return { n: created.length, inCharts: charts.length, wk: wk.map(c => c.ser.map(s => [s.o.color, s.o.lineStyle, s.data.length, s.data[0].time, s.data[0].value])),
    sh: els['#shCL'].innerHTML, sn: els['#snCL'].innerHTML, wk0: wk[0] }; };
els['#shCL'] = { innerHTML: '' }; els['#snCL'] = { innerHTML: '' };
const s5 = run(%s, false); s5.wk0.cb({ logical: 1, time: '2026-11-27' }); const hover = [els['#shCL'].innerHTML, els['#snCL'].innerHTML]; const prev = created.slice();
const one = run(%s, false), none = run(null, false); const removed = prev.every(c => c.removed);
els['#cpC'] = null; const etf = run(%s, {});
delete s5.wk0; delete one.wk0; delete none.wk0; delete etf.wk0;
console.log(JSON.stringify({ s5, hover, one, none, etf, removed }));""" % (json.dumps(SH5), json.dumps(SH1), json.dumps(SH2))
    o = t28._node(js)
    if o is None:
        return []
    bad, s5 = [], o["s5"]
    if s5["n"] != 7 or s5["inCharts"] != 7 or s5["wk"] != [[["#4C6EF5", 0, 5, "2026-11-20", 60], ["#DB6E00", 2, 5, "2026-11-20", 30.1]], [["#1C7ED6", 0, 5, "2026-11-20", 100]]]:
        bad.append(("5 週：多 2 張圖，點數 = sh.d 長度（和 chipN 無關）", s5))
    if '<span><b>12/18</b></span><span class="lg"><i style="background:#4C6EF5"></i>超過 400 張 <b class="num">63.00%</b></span>' not in s5["sh"] or \
            'border-top:2px dashed #DB6E00"></i>50 張以下 <b class="num">29.70%</b></span><span>超過 50 至 400 張 <b class="num">10.00%</b></span>' not in s5["sh"] or \
            '<b>12/18</b></span><span class="lg"><i style="background:#1C7ED6"></i>股東 <b class="num">120 人</b>' not in s5["sn"]:
        bad.append(("圖例", s5["sh"], s5["sn"]))
    if "<b>11/27</b>" not in o["hover"][0] or "61.50%" not in o["hover"][0] or "股東 <b class=\"num\">110 人</b>" not in o["hover"][1] or not o["removed"]:
        bad.append(("十字線換週、重建時釋放", o["hover"]))
    if (o["one"]["n"], o["one"]["wk"], o["none"]["n"], o["etf"]["n"]) != (5, [], 5, 4) or "受益人 <b class=\"num\">53,407 人</b>" not in o["etf"]["sn"]:
        bad.append(("1 週不畫、沒有 sh 和舊版相同、ETF", o["one"]["n"], o["none"]["n"], o["etf"]))
    return bad


def test_charts():
    assert check_charts() == []


def test_wiring_and_words():
    for f in ("tools.js", "app.js", "stock.js", "app.css"):
        v = hashlib.sha1((ROOT / "site" / f).read_bytes()).hexdigest()[:8]
        assert f'{f}?v={v}"' in HTML, f"site/index.html 的 {f}?v= 請改成 {v}"
    js = "".join(t28._grab(STK, n) for n in ("shCards", "SH_NOTE", "shChart")) + _inner(STK, "    ${SH ? chipSec('股權分散'") + _inner(STK, "  const SH = ")
    js += next(x for x in STK.splitlines() if "shChart(data.sh, E, mk)" in x)
    for w in (".at(", "??", "?.", "||=", "&&=", "replaceAll", "structuredClone", "Object.hasOwn", "findLast", "parseFloat("):
        assert w not in js, w                                                                                    # node 14
    py = inspect.getsource(tdcc) + "".join(inspect.getsource(f) for f in (health.share_line, health.share_state, health.share_exists, export.share_export,
                                                                           export._load_share, export.share_pct, tradingcal.last_full_week, tradingcal.weeks_behind))
    for w in ("買進", "賣出", "反彈", "見底", "買點", "超賣", "超買", "推薦", "強勢", "飆股", "勝率", "保證", "穩賺", "主力", "籌碼乾淨", "進場", "退場", "吸籌",
              "出貨", "值得", "看好", "亮點", "建議", "低估", "高估", "便宜", "安全", "危險", "支撐", "壓力", "目標價", "上檔", "下檔"):
        assert w not in js + py, w


# ─── 反證（驗收 25）：改壞後上面的檢查要失敗 ─────────────────────
PY_MUTANTS = [
    ("比日期不比週", catchup, "make_plan", "week_of(share[1]) < last_full_week(now.date(), closed)",
     "share[1] < last_full_week(now.date(), closed) + timedelta(days=4)", lambda f: check_timing() + check_world()),
    ("tdcc 失敗算進 undated_errors", catchup, "_run_locked", '("alerts", "events", "revenue", "financials", "industry", "chains")',
     '("alerts", "events", "revenue", "financials", "industry", "chains", "tdcc")', lambda f: check_isolation()),
    ("不是 isolated", tdcc, "collect_tdcc", "isolated=True", "isolated=False", lambda f: check_isolation() + check_write(f)),
    ("同一天抓到舊週後再抓", catchup, "make_plan", ' and state.get("tdcc_on") != now.date()', "", lambda f: check_timing() + check_world()),
    ("load_state 取最舊", health, "load_state", 'if und.get("tdcc") and state["tdcc_on"] is None:', 'if und.get("tdcc"):', lambda f: check_state(f)),
    ("collect --date 也抓", catchup, "plan_for_date", '"revenue": [], "financials": None}', '"revenue": [], "financials": None, "tdcc": {"latest": None}}',
     lambda f: check_timing() + check_world()),
    ("表不存在也排", catchup, "make_plan", "due = share and share[0] and", "due = share and", lambda f: check_timing()),
    ("合計驗算不扣 16 級", tdcc, "parse_tdcc", "sum(s[:15]) - s[15] != s[16]", "sum(s[:15]) != s[16]", lambda f: check_parse(f)),
    ("strip() 拿掉", tdcc, "parse_tdcc", "(x.strip() for x in r[:5])", "(x for x in r[:5])", lambda f: check_parse(f)),
    ("分母改用 1～15 級股數和", export, "share_export", "v[:15], v[15], v[16:]", "v[:15], sum(v[:15]), v[16:]", lambda f: check_export(f)),
    ("週數上限改 26", export, "share_export", "[-SH_WEEKS:]", "[-26:]", lambda f: check_export(f)),
    ("浮點四捨五入", export, "share_pct", "q = (2 * x * 10000 + t) // (2 * t)", "q = round(x / t * 10000)", lambda f: check_export() + ([] if export.share_pct(1005, 100000) == 1.01 else ["1.005"])),
    ("新週不算有新資料", catchup, "_run_locked", 'changed = changed or any((undated.get("tdcc") or {}).get(k) for k in ("s", "e"))', "pass",
     lambda f: check_world()),
    ("落後門檻改 1 週", health, "share_line", "if lag >= 2", "if lag >= 1", lambda f: check_lines()),
]
JS_MUTANTS = [
    ("ETF 卡片寫股東人數", "[etf ? '受益人數' : '股東人數'", "['股東人數'", check_cards),
    ("少於 2 週也畫圖", "if (data.sh && data.sh.d.length >= 2 && $('#shC'))", "if (data.sh && $('#shC'))", check_charts),
    ("少於 2 週也放圖的容器", "shN >= 2 ? chLeg('持股比例", "shN >= 1 ? chLeg('持股比例", check_cards),
    ("週圖跟 chipN 連動", "s.setData(vals.map((v, i) => ({ time: T[i], value: v })))", "s.setData(vals.slice(-chipN).map((v, i) => ({ time: T[i], value: v })))", check_charts),
    ("4 週改成和第 3 筆比", "4週 ${w(a, 4, 2)}", "4週 ${w(a, 3, 2)}", check_cards),
    ("50 張以下改成實線", "line(a, sh.r, R, pct, 2)", "line(a, sh.r, R, pct, 0)", check_charts),
]


def test_contrast():
    for name, mod, fn, a, b, check in PY_MUTANTS:
        with t40._mutate(mod, fn, a, b) as f, contextlib.redirect_stdout(io.StringIO()):
            try:
                fails = check(f)
            except Exception as e:                                                                             # 改壞到執行失敗也算擋下
                fails = [repr(e)]
        assert fails, "反證沒有擋下：" + name
    if t28._node("console.log('1')") is None:
        return
    for name, a, b, check in JS_MUTANTS:
        assert STK.count(a) == 1, (name, a)
        assert check(STK.replace(a, b)), "反證沒有擋下：" + name


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_") and callable(f):
            print("==", n); f()
    print("全部通過")
