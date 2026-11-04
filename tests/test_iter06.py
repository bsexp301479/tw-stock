"""
第 06 輪純邏輯測試（不連網、不連資料庫、不跳通知、不安裝排程、不呼叫 docker）：
F6-1 投信確定沒有持股明細的日期不算缺（QA-01）；F6-2 隔離比對工具（QA-02）；S9 backup 指令。
假的官方網站與資料庫沿用 test_iter03 的 World（以子類別加上 etf_holding_gaps，不改 test_iter03）。

  python3 tests/test_iter06.py      （也相容 pytest）
"""
import argparse
import contextlib
import io
import json
import subprocess
import sys
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_iter03 as t3  # noqa: E402
import test_iter05 as t5  # noqa: E402
from twstock import __main__ as cli  # noqa: E402
from twstock import backup, db, health, tradingcal  # noqa: E402
from twstock.collectors import daily, history, holdings  # noqa: E402
from twstock.collectors.holdings import Gap  # noqa: E402
from twstock.health import Row  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
D, T, World, CLOSED = t3.D, t3.T, t3.World, t3.CLOSED
CROSS = ("00411A", "00988A")


def _y(m, d):
    return date(2025, m, d)


# ─── 實際回應的片段（2026-11-04 21:05 分析師經 fetch.request(isolated=True) 取得，只留 NAV 與第一列明細、未改值）────
def _a(tran, post, nav, detail):
    return {"pcf": [{"PCFCode": "NAV", "TranDate": tran, "PostDate": post, "Amount": nav}], "fund": {},
            "asset": [{"AssetCode": "GD", "Details": []}, {"AssetCode": "ST", "Details": [
                {"TranDate": tran, "AssetCode": "ST", "MoneyType": "USD", "MTH": "", **detail}]}]}


A_1127 = _a("/Date(1764086400000)/", "/Date(1764518400000)/", 9230516712.0,   # 00988A，115 前 → 114/12/01；持股日 11/26
            {"DetailCode": "GOOGL US", "DetailName": "ALPHABET INC-CL A(Alphabet公司)", "Share": 48100, "Amount": 15389595.0,
             "NavRate": 5.23, "EditTime": "/Date(1764229008000)/"})
A_0119 = _a("/Date(1768492800000)/", "/Date(1768924800000)/", 8435860750.0,   # 00988A 115/01/21；持股日 01/16
            {"DetailCode": "MU US", "DetailName": "MICRON TECHNOLOGY INC", "Share": 58000, "Amount": 21039500.0,
             "NavRate": 7.87, "EditTime": "/Date(1768808165000)/"})
A_0210 = _a("/Date(1770739200000)/", "/Date(1771776000000)/", 10792838238.0,  # 00988A 115/02/23；持股日 02/11（比要求日晚）
            {"DetailCode": "MU US", "DetailName": "MICRON TECHNOLOGY INC", "Share": 61000, "Amount": 25030740.0,
             "NavRate": 7.29, "EditTime": "/Date(1770881692000)/"})
A_0525 = _a("/Date(1779379200000)/", "/Date(1779811200000)/", 40138747381.0,  # 00988A 115/05/27；持股日 05/22
            {"DetailCode": "MU US", "DetailName": "MICRON TECHNOLOGY INC", "Share": 78500, "Amount": 58953500.0,
             "NavRate": 4.63, "EditTime": "/Date(1779697824000)/"})
A_0907 = _a("/Date(1788451200000)/", "/Date(1788883200000)/", 6233471648.0,   # 00411A 115/09/09；持股日 09/04
            {"DetailCode": "BE US", "DetailName": "BLOOM ENERGY CORP- A", "Share": 47354, "Amount": 11974405.98,
             "NavRate": 6.08, "EditTime": "/Date(1788769768000)/"})
B_0708 = {"pcf": [{"PCFCode": "NAV", "TranDate": "/Date(1783440000000)/", "PostDate": "/Date(1783872000000)/",   # 00988A 115/07/13
                   "Amount": 59853545462.0}], "fund": {}, "asset": []}                                          # 只有彙總
REAL_A = ((A_1127, _y(11, 27), _y(12, 1), _y(11, 26)), (A_0119, D(1, 19), D(1, 21), D(1, 16)),
          (A_0210, D(2, 10), D(2, 23), D(2, 11)), (A_0525, D(5, 25), D(5, 27), D(5, 22)), (A_0907, D(9, 7), D(9, 9), D(9, 4)))


# ─── F6-1：解析 ─────────────────────────────────────────
def test_f61_dates():
    """要求的生效日 = 第 5 輪 post_date（跨境 delay 1）；10/21、7/8 的下一個生效日跳過颱風臨時休市日。"""
    for _, d, post, _ in REAL_A:
        assert holdings.post_date(d, 1, CLOSED) == post, d
    assert holdings.post_date(D(7, 8), 1, CLOSED) == D(7, 13) and holdings.post_date(D(10, 21), 1, CLOSED) == D(10, 27)
    assert {D(7, 10), D(10, 23)} <= set(tradingcal.AD_HOC)


def test_f61_parse_a():
    for data, d, post, src in REAL_A:
        assert holdings.parse_pcf(data, d, post, D(11, 4)) == Gap("A", src, post, None), d
        assert holdings.parse_pcf(data, d) is None                       # 沒給生效日：維持第 5 輪行為
        assert holdings.parse_pcf(data, d, post + timedelta(days=1), D(11, 4)) is None   # 生效日對不上：當成未公布
    # 回應的持股日就是要求日：照常寫入（Gap 只在持股日不同時出現）
    s, rows = holdings.parse_pcf(A_1127, _y(11, 26), _y(12, 1), D(11, 4))
    assert s["hold_date"] == "2025-11-26" and rows[0]["code"] == "GOOGL US"


def test_f61_parse_b():
    post = D(7, 13)
    assert holdings.parse_pcf(B_0708, D(7, 8), post, D(11, 4)) == Gap("B", D(7, 8), post, 59853545462.0)
    assert holdings.parse_pcf(B_0708, D(7, 8), post, post) == Gap("B", D(7, 8), post, 59853545462.0)   # 生效日當天
    assert holdings.parse_pcf(B_0708, D(7, 8), post, D(7, 12)) is None   # 生效日之前：可能還沒寫完明細，當成未公布
    assert holdings.parse_pcf(B_0708, D(7, 8)) is None
    assert holdings.parse_pcf(B_0708, D(7, 7), post, D(11, 4)) is None  # 持股日不是 d
    assert holdings.parse_pcf(B_0708, D(7, 8), D(7, 14), D(11, 4)) is None
    zero = {**B_0708, "pcf": [{**B_0708["pcf"][0], "Amount": 0}]}
    assert holdings.parse_pcf(zero, D(7, 8), post, D(11, 4)) is None


def test_f61_parse_unpublished_and_normal():
    # 尚未公布（西元 1 年、金額 0）：給了生效日也不會變成 Gap
    assert holdings.parse_pcf(t5.PCF_EMPTY, D(11, 4), D(11, 5), D(11, 30)) is None
    assert holdings.parse_pcf({**t5.PCF_EMPTY, "pcf": []}, D(11, 4), D(11, 5), D(11, 30)) is None
    s, rows = holdings.parse_pcf(t5.PCF_1103, D(11, 3), D(11, 4), D(11, 4))     # 一般已公布
    assert s["n_stocks"] == 3 and len(rows) == 4
    # 國內 ETF 也適用 B（規則不限跨境）
    b = {**t5.PCF_1103, "asset": []}
    assert holdings.parse_pcf(b, D(11, 3), D(11, 4), D(11, 4)) == Gap("B", D(11, 3), D(11, 4), 254413288263.0)
    # 欄位不符仍是 SchemaError
    for bad in ({"pcf": []}, {**t5.PCF_1103, "pcf": [{"PCFCode": "P_UNIT", "TranDate": "x", "PostDate": "x", "Amount": 1}]}):
        try:
            holdings.parse_pcf(bad, D(11, 3), D(11, 4), D(11, 4))
            raise AssertionError(bad)
        except daily.PARSE_ERRORS:
            pass


class _Cur:
    def __init__(self, etf=True):
        self.sql, self.etf = [], etf

    def execute(self, sql, *p):
        self.sql.append((" ".join(sql.split()), p))
        self.one = (7,) if self.etf else None
        return self

    def fetchone(self):
        return self.one


def test_f61_merge():
    c = _Cur()
    g = Gap("A", D(11, 25), D(11, 30), None)
    assert holdings.merge_gap(c, "00988A", D(11, 26), g)
    sql, p = c.sql[1]
    assert sql.startswith("MERGE etf_holding_gaps AS t") and p == (7, D(11, 26), "A", D(11, 25), D(11, 30), None) * 2
    assert not holdings.merge_gap(_Cur(etf=False), "00988A", D(11, 26), g)
    # 之後真的拿到明細：寫明細時一併刪掉 gap 紀錄
    c = _Cur()
    s, rows = holdings.parse_pcf(t5.PCF_1103, D(11, 3))
    holdings.merge_holdings(c, "00981A", s, rows)
    assert ("DELETE FROM etf_holding_gaps WHERE etf_id = ? AND hold_date = ?", (7, "2026-11-03")) in c.sql
    src = (ROOT / "twstock/db.py").read_text(encoding="utf-8")
    assert "IF OBJECT_ID('etf_holding_gaps') IS NULL" in src and "UQ_etf_holding_gaps UNIQUE (etf_id, hold_date)" in src
    assert "CHECK (reason IN ('A','B'))" in src and "etf_holding_gaps\")" in src


# ─── F6-1：健康檢查 ─────────────────────────────────────
def test_f61_health():
    spec = health.SPEC["holdings.00988A"]
    assert health.assess(spec, Row(gap="A"), 50) is None and health.assess(spec, Row(gap="B"), 50) is None
    assert health.assess(spec, Row(), 50) == ("none", "無資料")
    days = tradingcal.trading_days(D(10, 1), D(11, 4), CLOSED)
    snap = t3._full_snapshot(days)
    for c in CROSS:
        snap[f"holdings.{c}"][D(10, 21)] = Row(gap="B")
    snap["holdings.00988A"][D(10, 13)] = Row(gap="A")
    items = health.evaluate(days, snap, T(11, 4, 23))
    assert [i for i in items if i.status != health.OK] == []
    med = health.medians(snap)
    assert med["holdings.00988A"] == 50                                            # gap 的 0 不拉低中位數
    assert health.missing_keys(D(10, 21), tuple(f"holdings.{c}" for c in CROSS), snap, med) == ()
    out, rc = health.check_report(days, snap, T(11, 4, 23), {}, CLOSED)
    assert rc == 0, out
    assert ("ℹ️  投信沒有持股明細（不算缺）：00411A持股 2026-10-21（只有彙總）、00988A持股 2026-10-13（無持股清單）、"
            "00988A持股 2026-10-21（只有彙總）") in out
    line = next(x for x in out.splitlines() if x.startswith("00988A持股"))
    assert f"{len(days) - 1}/{len(days) - 1}" in line.replace(" ", "")            # 涵蓋含 gap（跨境少最後一天）
    # 網站狀態：目標日是 gap → 正常
    snap["holdings.00411A"][D(11, 3)] = Row(gap="A")
    st = {x["k"]: x for x in health.dataset_status(snap, D(11, 4), T(11, 4, 23), CLOSED)}
    assert st["holdings.00411A"]["s"] == health.OK and "m" not in st["holdings.00411A"]
    # 沒有 gap 時第 5 輪行為不變
    snap = t3._full_snapshot(days, skip={("holdings.00411A", D(10, 21))})
    out, rc = health.check_report(days, snap, T(11, 4, 23), {}, CLOSED)
    assert rc == 1 and "不算缺" not in out


# ─── F6-1：收集流程（假的 HTTP 與資料庫）─────────────────
class World6(World):
    """gaps = {(基金代碼, 持股日): ("A", 回應持股日) 或 ("B",)}；etf_holding_gaps 的 MERGE 寫成 Row(gap=原因)。"""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.gaps, self.gap_rows = {}, {}

    def _pcf(self, form):
        y, m, dd = form["date"].split("/")
        post = date(int(y) + 1911, int(m), int(dd))
        hold = t5._hold(form)
        g = self.gaps.get((form["fundCode"], hold))
        if not g or hold not in self.published["GetPCF"]:
            return super()._pcf(form)
        if g[0] == "B":
            return t3.Resp({"pcf": [{"PCFCode": "NAV", "TranDate": f"{hold}T00:00:00", "PostDate": f"{post}T00:00:00", "Amount": 1e9}],
                            "fund": {}, "asset": []})
        src = g[1]
        r = super()._pcf(form)
        stocks = [{"TranDate": f"{src}T00:00:00", "DetailCode": "AAPL US", "DetailName": "APPLE", "Share": 1.0, "Amount": 1.0,
                   "NavRate": 1.0, "MoneyType": "USD", "MTH": "", "EditTime": f"{hold}T16:30:00"}]
        r.data["pcf"][0].update(TranDate=f"{src}T00:00:00", PostDate=f"{post}T00:00:00")
        r.data["asset"] = [{"AssetCode": "ST", "Details": stocks}]
        return r

    def apply_merge(self, table, sql, params):
        if table != "etf_holding_gaps":
            return super().apply_merge(table, sql, params)
        self.merges.append(table)
        code, d = params[0], params[1]                    # FakeCursor：etf_id 就是 ETF 代號
        self.gap_rows[(code, d)] = params[2:6]
        self.rows[f"holdings.{code}"][d] = Row(gap=params[2])


class _Today(date):
    value = None

    @classmethod
    def today(cls):
        return cls.value


@contextlib.contextmanager
def _today(d):
    _Today.value = d
    with mock.patch.object(holdings, "date", _Today):
        yield


def test_f61_m1_thanksgiving():
    """2026-11-26 美國感恩節（情況 A）：11/27 晚上收集即記錄，不算缺、不通知；重跑 0 請求。"""
    w = World6(D(11, 26))
    for c in CROSS:
        del w.rows[f"holdings.{c}"][D(11, 26)]
    w.published["GetPCF"].add(D(11, 26))
    w.gaps = {("61YTW", D(11, 26)): ("A", D(11, 25)), ("64YTW", D(11, 26)): ("A", D(11, 25))}
    w.publish(D(11, 27))
    with _today(D(11, 27)):
        rc, out = t3.run_world(w, T(11, 27, 17, 30))
    assert rc == 0 and "Traceback" not in out, out
    assert "ℹ️  來源無持股明細（不算缺）：holdings.00411A（投信當日無持股清單）、holdings.00988A（投信當日無持股清單）" in out
    assert "官方尚無資料：holdings.00411A" not in out and "缺 2026-11-26" not in out
    assert w.gap_rows[("00988A", D(11, 26))] == ("A", date(2026, 11, 25), D(11, 30), None)
    assert w.rows["holdings.00988A"][D(11, 26)] == Row(gap="A") and w.rows["holdings.00981A"][D(11, 27)].n == 50
    hits = len(t5._pcf_hits(w))
    with _today(D(11, 27)):
        rc, out = t3.run_world(w, T(11, 27, 22, 30))
    assert rc == 0 and w.notices == [] and len(t5._pcf_hits(w)) == hits         # 22:00 後也不異常；不再請求


def test_f61_m2_typhoon_history():
    """10/21（情況 B）以 history --only holdings 重抓：記錄 B；重跑待抓 0 天、0 請求。"""
    w = World6(D(11, 4))
    for c in CROSS:
        del w.rows[f"holdings.{c}"][D(10, 21)]
    w.published["GetPCF"].update(tradingcal.trading_days(D(10, 1), D(11, 4), CLOSED))
    w.gaps = {("61YTW", D(10, 21)): ("B",), ("64YTW", D(10, 21)): ("B",)}
    with _today(D(11, 4)):
        ok, out = t5._history(w, D(10, 20), D(10, 22))
    assert ok and "Traceback" not in out, out
    assert len(t5._pcf_hits(w)) == 2 and "待抓 1 天" in out
    assert w.gap_rows[("00411A", D(10, 21))] == ("B", D(10, 21), D(10, 27), 1e9)
    with _today(D(11, 4)):
        ok, out = t5._history(w, D(10, 20), D(10, 22))
    assert ok and "待抓 0 天" in out and len(t5._pcf_hits(w)) == 2
    with _today(D(11, 4)):
        rc, out = t3.run_world(w, T(11, 4, 23), days=20)                          # catch-up 也不再請求
    assert rc == 0 and len(t5._pcf_hits(w)) == 2


def test_f61_m3_b_before_post():
    """國內 ETF 情況 B：公布當晚（生效日之前）先當尚未公布；生效日起記成 B，不再算缺。"""
    w = World6(D(11, 3))
    w.publish(D(11, 4))
    w.gaps = {("49YTW", D(11, 4)): ("B",)}
    with _today(D(11, 4)):
        rc, out = t3.run_world(w, T(11, 4, 17, 30))
    assert rc == 0 and "⏳ 00981A持股：2026-11-04 尚未公布" in out and ("49YTW", D(11, 4)) not in w.gap_rows
    assert ("00981A", D(11, 4)) not in w.gap_rows
    w.publish(D(11, 5))
    with _today(D(11, 5)):
        rc, out = t3.run_world(w, T(11, 5, 17, 30))
    assert rc == 0 and "holdings.00981A（投信只公布彙總、沒有明細）" in out, out
    assert w.gap_rows[("00981A", D(11, 4))] == ("B", D(11, 4), D(11, 5), 1e9) and w.notices == []


def test_f61_m4_unpublished_unchanged():
    """回應前一持股日、生效日也不同（第 5 輪 _stale）：仍是尚未公布，22:00 後異常；不記 gap。"""
    w = World6(D(11, 3))
    w.publish(D(11, 4), "GetPCF")
    t5._stale(w)
    with _today(D(11, 4)):
        rc, out = t3.run_world(w, T(11, 4, 22, 30))
    assert rc == 1 and "❌ 00981A持股：缺 2026-11-04" in out and w.gap_rows == {}


# ─── F6-2：隔離比對工具 ─────────────────────────────────
def _compare(a, b):
    r = subprocess.run([sys.executable, str(ROOT / "logs/iter06_compare.py"), str(a), str(b)], capture_output=True, text=True, timeout=60)
    return r.returncode, r.stdout


def test_f62_compare():
    if not (ROOT / "logs/iter06_compare.py").exists():                       # logs/ 不在版本控制
        print("  （略過：logs/iter06_compare.py 不存在）")
        return
    with tempfile.TemporaryDirectory() as tmp:
        a, b = Path(tmp, "a"), Path(tmp, "b")
        for x, at in ((a, "2026-11-04T21:04:00+08:00"), (b, "2026-11-05T09:00:00+08:00")):
            (x / "stocks").mkdir(parents=True)
            (x / "etfs").mkdir()
            (x / "latest.json").write_text(json.dumps({"updated_at": at, "date": "2026-11-04", "status": {
                "exported_at": at, "collected_at": at, "collected_src": "run", "datasets": [{"k": "prices.TWSE", "s": "ok"}]}}))
            (x / "stocks/2330.json").write_text(json.dumps({"c": "2330", "p": [1, 2]}))
            (x / "etfs/00981A.json").write_text(json.dumps({"sum": {"d": "2026-11-04"}}))
        rc, out = _compare(a, b)
        assert rc == 0 and "✅ 相同" in out and "etfs 1 檔" in out, out
        (b / "etfs/00981A.json").write_text(json.dumps({"sum": {"d": "2026-11-03"}}))
        rc, out = _compare(a, b)
        assert rc == 1 and "etfs/00981A.json" in out
        (b / "etfs/00981A.json").write_text(json.dumps({"sum": {"d": "2026-11-04"}}))
        L = json.loads((b / "latest.json").read_text())
        L["status"]["collected_src"] = "schedule"
        (b / "latest.json").write_text(json.dumps(L))
        rc, out = _compare(a, b)
        assert rc == 1 and "status.collected_src" in out


# ─── S9：backup ────────────────────────────────────────
class _Docker:
    """假的 docker：記錄指令；ps／inspect 的回應可設定；cp 在主機建立檔案。"""

    def __init__(self, ps="MySqlServer", running="true", fail=None, missing=False):
        self.calls, self.ps, self.running, self.fail, self.missing = [], ps, running, fail, missing

    def __call__(self, cmd, capture_output=True, text=True, check=True):
        if self.missing:
            raise FileNotFoundError("docker")
        self.calls.append(cmd[1:])
        if self.fail == cmd[1]:
            raise subprocess.CalledProcessError(1, cmd, "", "Error response from daemon: boom")
        out = {"ps": self.ps, "inspect": self.running}.get(cmd[1], "")
        if cmd[1] == "cp":
            Path(cmd[3]).write_bytes(b"x" * 1048576)
        return subprocess.CompletedProcess(cmd, 0, out + "\n", "")


class _SqlCur:
    def __init__(self, log, no_compress):
        self.log, self.no_compress = log, no_compress

    def execute(self, sql):
        self.log.append(sql)
        if self.no_compress and "COMPRESSION" in sql:
            raise db.pyodbc.Error("42000", "BACKUP DATABASE WITH COMPRESSION is not supported on Express Edition")
        return self

    def nextset(self):
        return False


class _SqlConn:
    def __init__(self, log, no_compress=False):
        self.log, self.no_compress, self.closed = log, no_compress, False

    def cursor(self):
        return _SqlCur(self.log, self.no_compress)

    def close(self):
        self.closed = True


@contextlib.contextmanager
def _bk(docker=None, no_compress=False, env=None, connect_error=None):
    sql, conns = [], []

    def connect(autocommit=False):
        assert autocommit                                   # BACKUP 不能在交易中執行
        if connect_error:
            raise connect_error
        conns.append(_SqlConn(sql, no_compress))
        return conns[-1]
    with mock.patch.object(backup.subprocess, "run", docker or _Docker()), mock.patch.object(db, "connect", connect), \
            mock.patch.dict(backup.os.environ, env or {}, clear=False), \
            mock.patch.dict(backup.DB_CONFIG, {"server": "localhost,1433", "database": "TwStock"}):
        if not env:
            backup.os.environ.pop("DB_CONTAINER", None)
        yield sql, conns


def _run(out_dir, **kw):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = backup.run(out_dir, kw.pop("direct", False))
    return rc, buf.getvalue()


NOW = datetime(2026, 11, 5, 7, 30)


def test_s9_ok_and_cleanup():
    with tempfile.TemporaryDirectory() as tmp, mock.patch.object(backup, "datetime", mock.Mock(now=lambda: NOW)):
        dk = _Docker()
        with _bk(dk) as (sql, conns):
            rc, out = _run(Path(tmp, "sub"))
        f = Path(tmp, "sub", "TwStock_20261105_073000.bak")
        assert rc == 0 and f.exists() and "✅ 備份完成並通過 RESTORE VERIFYONLY" in out and "（1.0 MB）" in out, out
        disk = "/var/opt/mssql/data/TwStock_20261105_073000.bak"
        assert sql == [f"BACKUP DATABASE [TwStock] TO DISK = N'{disk}' WITH COPY_ONLY, INIT, COMPRESSION",
                       f"RESTORE VERIFYONLY FROM DISK = N'{disk}'"]
        assert all("RESTORE DATABASE" not in s for s in sql) and conns[0].closed
        assert dk.calls == [["ps", "--filter", "publish=1433", "--format", "{{.Names}}"],
                            ["inspect", "-f", "{{.State.Running}}", "MySqlServer"],
                            ["cp", f"MySqlServer:{disk}", str(f.resolve())],
                            ["exec", "MySqlServer", "rm", "-f", disk]]          # 只刪這次自己的暫存檔
        # 同一秒再跑（mock）：不覆寫、不連資料庫、不呼叫 docker
        dk = _Docker()
        with _bk(dk) as (sql, conns):
            rc, out = _run(Path(tmp, "sub"))
        assert rc == 1 and "已存在，不覆寫" in out and sql == [] and dk.calls == [] and f.stat().st_size == 1048576


def test_s9_no_compression_and_env_container():
    with tempfile.TemporaryDirectory() as tmp, mock.patch.object(backup, "datetime", mock.Mock(now=lambda: NOW)):
        dk = _Docker()
        with _bk(dk, no_compress=True, env={"DB_CONTAINER": "twstock-mssql"}) as (sql, _):
            rc, out = _run(tmp)
        assert rc == 0 and "不支援壓縮備份，改用不壓縮" in out
        assert sql[1].endswith("WITH COPY_ONLY, INIT") and sql[2].startswith("RESTORE VERIFYONLY")
        assert dk.calls[0] == ["inspect", "-f", "{{.State.Running}}", "twstock-mssql"]        # 有 DB_CONTAINER 就不找 ps


def test_s9_docker_problems():
    cases = ((dict(missing=True), "找不到 docker 指令"), (dict(ps=""), "找到 0 個"), (dict(ps="a\nb"), "找到 2 個"),
             (dict(running="false"), "容器 MySqlServer 沒有在執行"), (dict(fail="ps"), "docker ps 失敗"))
    for kw, msg in cases:
        with tempfile.TemporaryDirectory() as tmp:
            dk = _Docker(**kw)
            with _bk(dk) as (sql, _):
                rc, out = _run(tmp)
            assert rc == 1 and msg in out and "Traceback" not in out and sql == [] and not list(Path(tmp).iterdir()), (kw, out)
    # cp 失敗：訊息指出 docker cp，容器內的暫存檔照樣刪除（QA-03）
    with tempfile.TemporaryDirectory() as tmp:
        dk = _Docker(fail="cp")
        with _bk(dk) as (sql, _):
            rc, out = _run(tmp)
        assert rc == 1 and "docker cp 失敗" in out and len(sql) == 2
        assert dk.calls[-1][:4] == ["exec", "MySqlServer", "rm", "-f"] and not list(Path(tmp).iterdir())


def test_s9_cleanup_on_failure():
    """QA-03：VERIFYONLY 失敗 → 專屬訊息、rc=1、不複製、刪暫存檔；刪不掉 → 印出指令。"""
    orig = _SqlCur.execute

    def verify_fails(self, sql):
        if sql.startswith("RESTORE VERIFYONLY"):
            raise db.pyodbc.Error("42000", "The media set has 2 media families but only 1 are provided")
        return orig(self, sql)
    with tempfile.TemporaryDirectory() as tmp:
        dk = _Docker()
        with _bk(dk), mock.patch.object(_SqlCur, "execute", verify_fails):
            rc, out = _run(tmp)
        assert rc == 1 and "❌ 備份檔驗證失敗（RESTORE VERIFYONLY），這份備份不可用" in out and "連不上資料庫" not in out, out
        assert [c[0] for c in dk.calls] == ["ps", "inspect", "exec"] and not list(Path(tmp).iterdir())
    # BACKUP 本身失敗：cmd_backup 照舊 rc=2，暫存檔（可能不存在）照樣嘗試刪除
    with tempfile.TemporaryDirectory() as tmp:
        dk = _Docker()
        with _bk(dk), mock.patch.object(_SqlCur, "execute", side_effect=db.pyodbc.Error("42000", "disk full")):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = cli.cmd_backup(argparse.Namespace(out=tmp, direct=False))
        assert rc == 2 and "disk full" in buf.getvalue() and dk.calls[-1][0] == "exec"
    # cp 與 rm 都失敗：印出要自行執行的指令
    with tempfile.TemporaryDirectory() as tmp:
        dk = _Docker(fail="cp")
        dk_call = dk.__call__

        def call(cmd, **kw):
            if cmd[1] == "exec":
                raise subprocess.CalledProcessError(1, cmd, "", "boom")
            return dk_call(cmd, **kw)
        with _bk(call):
            rc, out = _run(tmp)
        assert rc == 1 and "⚠️  容器內的暫存備份檔沒有刪除，請自行執行：docker exec MySqlServer rm -f /var/opt/mssql/data/TwStock_" in out, out
    # --direct：不呼叫 docker
    with tempfile.TemporaryDirectory() as tmp:
        dk = _Docker(missing=True)
        with _bk(dk), mock.patch.object(_SqlCur, "execute", verify_fails):
            rc, out = _run(tmp, direct=True)
        assert rc == 1 and "備份檔驗證失敗" in out and dk.calls == []


def test_qa04_history_today():
    """QA-04：history 跑到今天時，跨境 ETF 今天的持股（明天才公布）不算待抓；昨天的照常補。"""
    w = World6(D(11, 3))
    for c in CROSS:
        del w.rows[f"holdings.{c}"][D(11, 3)]
    w.published["GetPCF"].add(D(11, 3))
    w.publish(D(11, 4))
    with mock.patch.object(history, "tw_now", lambda: T(11, 4, 21, 30)):
        ok, out = t5._history(w, D(11, 2), D(11, 4))
    assert ok and "Traceback" not in out, out
    assert sorted((f["fundCode"], t5._hold(f)) for f in t5._pcf_hits(w)) == [
        ("49YTW", D(11, 4)), ("61YTW", D(11, 3)), ("63YTW", D(11, 4)), ("64YTW", D(11, 3))]
    with mock.patch.object(history, "tw_now", lambda: T(11, 4, 21, 30)):
        ok, out = t5._history(w, D(11, 2), D(11, 4))
    assert ok and "待抓 0 天" in out and len(t5._pcf_hits(w)) == 4
    # 隔天：11/04 已公布，照常補
    with mock.patch.object(history, "tw_now", lambda: T(11, 5, 21, 30)):
        ok, out = t5._history(w, D(11, 2), D(11, 4))
    assert ok and "待抓 1 天" in out and len(t5._pcf_hits(w)) == 6


def test_s9_direct_and_db_errors():
    with tempfile.TemporaryDirectory() as tmp, mock.patch.object(backup, "datetime", mock.Mock(now=lambda: NOW)):
        dk = _Docker(missing=True)                                      # --direct 完全不用 docker
        with _bk(dk) as (sql, _):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                path = backup.backup(Path(tmp), direct=True, now=NOW)
        assert sql[0] == f"BACKUP DATABASE [TwStock] TO DISK = N'{path}' WITH COPY_ONLY, INIT, COMPRESSION"
        # 資料庫連不上：rc=2、沒有 Traceback
        with _bk(_Docker(), connect_error=db.pyodbc.OperationalError("08001", "Login timeout expired")):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = cli.cmd_backup(argparse.Namespace(out=tmp, direct=False))
        assert rc == 2 and "連不上資料庫或備份失敗" in buf.getvalue() and "Traceback" not in buf.getvalue()
        # 壓縮以外的錯誤不吞掉
        with _bk(_Docker()) as (sql, _):
            with mock.patch.object(_SqlCur, "execute", side_effect=db.pyodbc.Error("42000", "permission denied")):
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    rc = cli.cmd_backup(argparse.Namespace(out=Path(tmp, "x"), direct=False))
        assert rc == 2 and "permission denied" in buf.getvalue()


def test_s9_cli():
    p = mock.patch.object(cli, "cmd_backup", lambda a: (a.out, a.direct))
    with p:
        assert cli.main(["backup", "--out", "x"]) == ("x", False) and cli.main(["backup", "--direct"]) == (None, True)
    assert backup.BACKUP_DIR == ROOT.parent / "_backups"
    assert "python -m twstock backup" in (cli.__doc__ or "")
    src = (ROOT / "twstock/backup.py").read_text(encoding="utf-8")
    assert "RESTORE DATABASE" not in src and "COPY_ONLY" in src and "rm\", \"-f\", disk" in src


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"✅ {name}")
    print("全部通過")
