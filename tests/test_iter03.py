"""
第 03 輪純邏輯測試（不連網、不連資料庫、不跳通知、不安裝排程）：
S1 上櫃本益比解析；S2 完整性判斷、check、通知；S3 --catch-up 全部失敗情境（用假的 HTTP 與資料庫跑真實流程）；
S5 交易日曆與臨時休市；S6 補抓不覆蓋市場別；S7 原子寫入；F1 升降單位取整。

  python3 tests/test_iter03.py      （也相容 pytest）
"""
import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from unittest import mock

import pyodbc

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from twstock import db, export, fetch, health, tradingcal  # noqa: E402
from twstock.collectors import catchup, daily, futures, history  # noqa: E402
from twstock.config import TW_TZ  # noqa: E402
from twstock.fetch import FetchError, SchemaError  # noqa: E402
from twstock.health import Row  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def D(m, d, y=2026):
    return date(y, m, d)


def T(m, d, hh=18, mm=0, y=2026):
    return datetime(y, m, d, hh, mm, tzinfo=TW_TZ)


PE_FIELDS = ["股票代號", "公司名稱", "本益比", "每股股利", "股利年度", "殖利率(%)", "股價淨值比", "財報年/季"]
CLOSED = tradingcal.closed_from_rows([])


# ─── S1：上櫃本益比解析 ───────────────────────────────────
def test_parse_tpex_pe():
    rows = [["5904", "寶雅", "20.14", "22.80000000", 114, "3.51", "9.33", "115Q2"],
            ["3564", "其陽", "87.91", "0.75000000", 114, "0.43", "2.66", "115Q3"],
            ["1240", "茂生農經", "N/A", "0.50000000", 114, "0.93", "1.59", "115Q2"],     # 虧損股本益比 N/A
            ["1259", "安心", "18.25", "1.2", 114, "", "0.75", "115Q2"],                 # 空值
            ["00679B", "債券 ETF", "1", "1", 114, "1", "1", "115Q2"]]                   # 不是一般股票
    r = daily.parse_tpex_pe([{"fields": PE_FIELDS, "data": rows}])
    assert r["5904"] == {"pe_ratio": 20.14, "dividend_yield": 3.51, "pb_ratio": 9.33}
    assert r["3564"]["pe_ratio"] == 87.91
    assert r["1240"]["pe_ratio"] is None and r["1240"]["dividend_yield"] == 0.93
    assert r["1259"]["dividend_yield"] is None and "00679B" not in r
    assert daily.parse_tpex_pe([]) == {}                                            # 休市：表是空的
    renamed = ["股票代號", "本益比", "現金殖利率", "股價淨值比"]
    for fields in (renamed, ["代號", "本益比", "殖利率(%)", "股價淨值比"]):
        try:
            daily.parse_tpex_pe([{"fields": fields, "data": [["5904", "1", "1", "1"]]}])
            assert False, "欄位不符要丟 SchemaError"
        except SchemaError as e:
            assert "peQryDate" in str(e)


def test_parse_tpex_index():
    f = ["日期", "開市", "最高", "最低", "收市", "漲/跌"]
    r = daily.parse_tpex_index([{"fields": f, "data": [["2026/10/29", "396.40", "397.17", "385.26", "387.37", "-7.24"],
                                                       ["2026/10/30", "384.20", "384.20", "365.70", "370.26", "-17.11"],
                                                       ["2026/10/31", "--", "--", "--", "--", "--"]]}])
    assert [x["trade_date"] for x in r] == ["2026-10-29", "2026-10-30"]
    assert r[1] == {"index_code": "TPEX", "trade_date": "2026-10-30", "open_price": 384.2, "high_price": 384.2,
                    "low_price": 365.7, "close_price": 370.26, "change": -17.11}
    assert daily.parse_tpex_index([]) == []
    try:
        daily.parse_tpex_index([{"fields": ["日期", "收盤"], "data": [["2026/10/30", "1"]]}])
        assert False
    except SchemaError:
        pass


# ─── S2：完整性判斷 ───────────────────────────────────────
def test_assess():
    s = health.SPEC["pe.TPEx"]
    assert health.assess(s, Row(892, 680, 892, 892), 888) is None
    assert health.assess(s, Row(0), 888)[0] == "none"
    assert health.assess(s, Row(2, 2, 2, 2), 888)[0] == "count"                     # 10/30 的實際情況
    assert health.assess(s, Row(711, 500, 711, 711), 888) is None                   # 門檻 710.4
    assert health.assess(s, Row(710, 500, 710, 710), 888)[0] == "count"
    assert health.assess(s, Row(600, 500, 600, 600), 0)[0] == "count"               # 沒有中位數時看下限 650
    assert health.assess(s, Row(893, 676, 893, 2), 888)[0] == "fill:殖利率"          # 10/29 的實際情況：只比筆數抓不到
    assert health.assess(s, Row(892, 446, 892, 892), 888) is None                   # 剛好 50%
    assert health.assess(s, Row(892, 445, 892, 892), 888)[0] == "fill:本益比"
    assert health.assess(health.SPEC["prices.TPEx"], Row(895), 889) is None         # 行情沒有填充率檢查


def _full_snapshot(days, skip=()):
    ok = {"prices.TWSE": Row(1086), "prices.TPEx": Row(889), "pe.TWSE": Row(1082, 870, 1082, 1082),
          "pe.TPEx": Row(888, 675, 888, 888), "insti.TWSE": Row(1077), "insti.TPEx": Row(784), "amount": Row(6),
          "index.TAIEX": Row(1), "index.TPEX": Row(1), "futures": Row(6), "futures_oi": Row(9)}
    return {k: {d: v for d in days if (k, d) not in skip} for k, v in ok.items()}


def test_status_boundary():
    days = tradingcal.trading_days(D(10, 1), D(11, 2), CLOSED)
    snap = _full_snapshot(days, skip={("insti.TWSE", D(11, 2))})
    pick = lambda items: [i.status for i in items if i.key == "insti.TWSE" and i.date == D(11, 2)][0]
    assert pick(health.evaluate(days, snap, T(11, 2, 21, 59))) == health.PENDING
    assert pick(health.evaluate(days, snap, T(11, 2, 22, 0))) == health.ABNORMAL
    assert pick(health.evaluate(days, snap, T(11, 3, 9, 0))) == health.ABNORMAL     # 隔日才算異常
    # 抓取失敗不論時間都是異常；範圍查詢失敗（鍵）只影響還缺資料的日期
    assert health.outcome(health.evaluate(days, snap, T(11, 2, 21, 59), {("insti.TWSE", D(11, 2)): FetchError("x")})) == health.ABNORMAL
    assert health.outcome(health.evaluate(days, snap, T(11, 2, 21, 59), {"insti.TWSE": FetchError("x")})) == health.ABNORMAL
    assert health.outcome(health.evaluate(days, snap, T(11, 2, 21, 59), {"futures": FetchError("x")})) == health.PENDING
    assert health.outcome(health.evaluate(days, _full_snapshot(days), T(11, 2, 18))) == health.OK


def test_due_days():
    assert health.due_days(T(11, 2, 14, 59), 1, CLOSED) == [D(10, 30)]              # 15:00 前今天不列入
    assert health.due_days(T(11, 2, 15, 0), 1, CLOSED) == [D(11, 2)]
    assert health.due_days(T(10, 31, 12), 2, CLOSED) == [D(10, 29), D(10, 30)]      # 週六
    assert D(10, 23) not in health.due_days(T(10, 28, 18), 5, CLOSED)               # 臨時休市
    assert D(10, 26) not in health.due_days(T(10, 28, 18), 5, CLOSED)               # 連假補假


def test_check_baseline():
    """用 2026-10-31 資料庫的實際數字重現基線：上櫃本益比 10/30 筆數、殖利率填充率、櫃買指數缺 9/30。"""
    now = T(10, 31, 12, 30)
    days = health.due_days(now, 20, CLOSED)
    assert days[0] == D(9, 30) and days[-1] == D(10, 30) and len(days) == 20
    snap = _full_snapshot(days, skip={("index.TPEX", D(9, 30))})
    snap["pe.TPEx"] = {d: Row(888, 675, 888, 2) for d in days}
    snap["pe.TPEx"][D(10, 30)] = Row(2, 2, 2, 2)
    state = {"alerts_at": None, "events_to": None, "revenue_on": None, "collected_at": None}
    with mock.patch.object(fetch._SESSION, "request") as http, mock.patch.object(db, "connect") as conn:
        text, rc = health.check_report(days, snap, now, state, CLOSED)
    assert rc == 1 and http.call_count == 0 and conn.call_count == 0
    assert "2026-10-30 筆數 2" in text and "殖利率填充率" in text and "櫃買指數：缺 2026-09-30" in text
    assert "異常 3 項" in text and "今天 2026-10-31 休市" in text
    # 回補後
    text, rc = health.check_report(days, _full_snapshot(days), now, state, CLOSED)
    assert rc == 0 and "無異常" in text
    # 休市日（週末、連假、臨時休市）不算缺漏：days 本來就不含
    assert not {D(10, 23), D(10, 24), D(10, 25), D(10, 26)} & set(days)
    # 處置／注意股落後 2 個交易日以上才算異常；沒有紀錄不算
    state2 = dict(state, alerts_at=datetime(2026, 10, 28, 19, 30))
    text, rc = health.check_report(days, _full_snapshot(days), now, state2, CLOSED)
    assert rc == 1 and "處置／注意股" in text
    state3 = dict(state, alerts_at=datetime(2026, 10, 29, 19, 30))
    assert health.check_report(days, _full_snapshot(days), now, state3, CLOSED)[1] == 0


def test_run_check_readonly():
    w = World(D(10, 30))
    runs = list(w.runs)
    buf = io.StringIO()
    with env(w), mock.patch.object(health, "load_snapshot", w.snapshot), contextlib.redirect_stdout(buf):
        rc = health.run_check(20, T(10, 31, 12))
    assert rc == 0 and "無異常" in buf.getvalue()
    assert w.requests == [] and w.merges == [] and w.runs == runs       # 不連外、不寫資料庫


def test_notify_once():
    with tempfile.TemporaryDirectory() as tmp, mock.patch.object(health, "NOTIFY_FILE", Path(tmp) / "n.json"), \
            mock.patch.object(health.subprocess, "run") as run, mock.patch.object(health.sys, "platform", "darwin"):
        assert health.notify_once({}, D(11, 2)) is False and run.call_count == 0       # 正常不通知
        assert health.notify_once({"a": "上櫃本益比 11/02 筆數 2"}, D(11, 2)) is True and run.call_count == 1
        assert health.notify_once({"a": "上櫃本益比 11/02 筆數 2"}, D(11, 2)) is False and run.call_count == 1  # 同日不重複
        assert health.notify_once({"a": "x", "b": "新問題"}, D(11, 2)) is True and run.call_count == 2            # 新問題要通知
        assert "新問題" in run.call_args[0][0][2] and "x" not in run.call_args[0][0][2]
        assert health.notify_once({"a": "x"}, D(11, 3)) is True and run.call_count == 3                          # 隔天再通知
    with tempfile.TemporaryDirectory() as tmp, mock.patch.object(health, "NOTIFY_FILE", Path(tmp) / "n.json"), \
            mock.patch.object(health.subprocess, "run") as run, mock.patch.object(health.sys, "platform", "win32"):
        assert health.notify_once({"a": "x"}, D(11, 2)) is False and run.call_count == 0  # Windows 只寫紀錄


def test_dataset_status():
    days = tradingcal.trading_days(D(10, 1), D(10, 30), CLOSED)
    snap = _full_snapshot(days, skip={("pe.TPEx", D(10, 30))})
    st = {x["k"]: x for x in health.dataset_status(snap, D(10, 30), T(11, 2, 18))}
    assert st["pe.TPEx"]["s"] == "abnormal" and st["pe.TPEx"]["m"] == "上櫃本益比停在 10/29"
    assert st["prices.TWSE"] == {"k": "prices.TWSE", "n": "上市行情", "d": "2026-10-30", "s": "ok"}
    st = {x["k"]: x for x in health.dataset_status(snap, D(10, 30), T(10, 30, 19))}
    assert st["pe.TPEx"]["s"] == "pending" and "m" not in st["pe.TPEx"]             # 當天 22:00 前
    assert len(json.dumps(health.dataset_status(snap, D(10, 30), T(11, 2, 18)), ensure_ascii=False)) < 1500


# ─── S5：交易日曆與臨時休市 ───────────────────────────────
CAL = {"stat": "ok", "fields": ["日期", "名稱", "說明"], "queryYear": 2026, "data": [
    ["2026-01-01", "中華民國開國紀念日", ""], ["2026-01-02", "國曆新年開始交易日", ""],
    ["2026-02-11", "農曆春節前最後交易日", ""], ["2026-02-12", "市場無交易，僅辦理結算交割作業", ""],
    ["2026-02-23", "農曆春節後開始交易日", ""], ["2026-02-28", "和平紀念日", ""]]}


def test_parse_holidays():
    assert tradingcal.parse_holidays(CAL) == [(D(1, 1), "中華民國開國紀念日"), (D(2, 12), "市場無交易，僅辦理結算交割作業"),
                                               (D(2, 28), "和平紀念日")]
    try:
        tradingcal.parse_holidays({"fields": ["date"], "data": []})
        assert False
    except SchemaError:
        pass


def test_trading_days():
    assert len(tradingcal.trading_days(D(10, 30, 2025), D(10, 30))) == 242
    # 有官方資料的年度以官方為準，但手寫的臨時休市仍然有效
    official = [(d, "official") for d in sorted(h for h in tradingcal.HOLIDAYS if h.year == 2026)]
    assert len(tradingcal.trading_days(D(10, 30, 2025), D(10, 30), tradingcal.closed_from_rows(official))) == 242
    closed = tradingcal.closed_from_rows([(D(12, 24), "official")])
    assert not tradingcal.is_trading_day(D(12, 24), closed) and tradingcal.is_trading_day(D(12, 25), closed)
    assert not tradingcal.is_trading_day(D(10, 23), closed)
    # 自動判定的臨時休市
    assert not tradingcal.is_trading_day(D(11, 4), tradingcal.closed_from_rows([(D(11, 4), "adhoc")]))
    # 2027 沒有日曆：平日視為交易日，並印警告
    assert tradingcal.is_trading_day(date(2027, 2, 8), CLOSED)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        tradingcal.warn_uncovered(CLOSED, datetime(2027, 1, 4, 18, tzinfo=TW_TZ))
    assert "2027" in buf.getvalue()


def test_adhoc_closure():
    f = tradingcal.is_adhoc_closure
    assert f(D(10, 23), D(10, 27), 0, 0, 0, False) is True
    assert f(D(10, 23), D(10, 23), 0, 0, 0, False) is False     # 當天不判定
    assert f(D(10, 23), D(10, 27), 0, 0, 6, False) is False     # 期交所有資料
    assert f(D(10, 23), D(10, 27), 0, 880, 0, False) is False   # 上櫃有資料
    assert f(D(10, 23), D(10, 27), 0, 0, 0, True) is False      # 查詢失敗不判定


def test_calendar_due():
    now = T(10, 31, 12)
    assert tradingcal.calendar_due([], now) is True
    assert tradingcal.calendar_due([(D(1, 1), "official", datetime(2026, 10, 20))], now) is False
    assert tradingcal.calendar_due([(D(1, 1), "official", datetime(2026, 9, 20))], now) is True
    assert tradingcal.calendar_due([(D(1, 1), "adhoc", datetime(2026, 10, 20))], now) is True
    assert tradingcal.calendar_due([(D(1, 1), "official", datetime(2026, 10, 20))],
                                   datetime(2027, 1, 4, tzinfo=TW_TZ)) is True    # 新年度


def test_update_calendar():
    now = T(10, 31, 12)
    w = World(D(10, 30))
    w.holidays = []
    buf = io.StringIO()
    with env(w), contextlib.redirect_stdout(buf):
        tradingcal.update_calendar(now)                                 # 缺當年資料：1 個請求
        assert w.paths() == ["/rwd/zh/holidaySchedule/holidaySchedule"] and "官方休市表" in buf.getvalue()
        assert [(d, s) for d, s, _ in w.holidays] == [(D(1, 1), "official"), (D(2, 12), "official"), (D(2, 28), "official")]
        tradingcal.update_calendar(now)                                 # 同一年第二次：不發請求
    assert len(w.paths()) == 1
    # 端點失敗：印警告、退回手寫表，收集照常
    w = World(D(10, 30))
    w.holidays = []
    w.down.add("holidaySchedule")
    rc, out = run_world(w, now)
    assert rc == 0 and "改用手寫表" in out and len(w.paths()) == 1


# ─── S6：補抓舊日期不覆蓋市場別 ───────────────────────────
def test_merge_stocks_flag():
    class Cur:
        def __init__(self, latest):
            self.latest, self.calls = latest, []

        def execute(self, sql, *p):
            self.calls.append((sql, p))
            return self

        def fetchone(self):
            return (self.latest,)
    rows = [{"stock_code": "5236", "stock_name": "凌陽創新", "market_type": "TPEx"}]
    for latest, d, flag in ((D(10, 30), D(1, 5), 0), (D(10, 30), D(10, 30), 1), (D(10, 30), D(11, 2), 1), (None, D(1, 5), 1)):
        cur = Cur(latest)
        daily.merge_stocks(cur, rows, d)
        sql, params = cur.calls[-1]
        assert "WHEN MATCHED AND ? = 1" in sql and "WHEN NOT MATCHED" in sql and params[1] == flag


# ─── S7：原子寫入 ─────────────────────────────────────────
def test_atomic_write():
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "latest.json"
        export._write(p, {"a": 1})
        assert json.loads(p.read_text()) == {"a": 1}
        with mock.patch.object(export.os, "replace", side_effect=OSError("磁碟已滿")):
            try:
                export._write(p, {"a": 2})
                assert False
            except OSError:
                pass
        assert json.loads(p.read_text()) == {"a": 1}                    # 原檔完好
        assert [x.name for x in Path(tmp).iterdir()] == ["latest.json"]  # 沒有殘留暫存檔


# ─── F1：升降單位取整、板塊漲跌 ───────────────────────────
def test_tick_round():
    cases = {650.5: 651, 2614.99: 2615, 240.82: 241, 167.62: 167.5, 651.5: 652, 9.994: 9.99, 9.995: 10.0,
             10.02: 10.0, 49.97: 49.95, 50.04: 50.0, 50.05: 50.1, 99.96: 100.0, 100.2: 100.0, 100.25: 100.5,
             499.75: 500.0, 500.4: 500.0, 999.5: 1000.0, 1002.5: 1005.0, 7800.0: 7800.0}
    for price, want in cases.items():
        assert export._tick_round(price) == want, (price, export._tick_round(price))


def _N(*v):
    return tuple(None if x is None else Decimal(str(x)) for x in v)


def test_changes_tick():
    def one(close, prev, ref, off=0):
        chs, _, _ = export._changes((D(7, 10), D(7, 13)), _N(prev, close), _N(0, off), "TWSE",
                                    [{"i": 1, "d": "2026-07-13", "t": "息", "p": prev, "r": ref}])
        return chs[1]
    assert one(170, 172, 167.62) == 2.5                 # 6762 2026-07-13 官方 +2.5
    assert one(2610, 7800, 2614.99) == -5.0             # 6669 2026-09-02
    assert one(239, 248, 240.82) == -2.0                # 2317 2026-07-02
    assert export._pct(2610, -5.0) == -5 / 2615 * 100
    # 還原係數仍用未取整的官方值
    assert export._adj_factors(2, [{"i": 1, "p": 7800.0, "r": 2614.99}])[0] == 2614.99 / 7800.0


def test_group_pct_source():
    # 板塊漲跌幅改用 P14 值：事件日官方 0 不再讓泡泡顏色失真
    assert export._pct(2610, -5.0) != export._pct(2610, 0)
    src = (ROOT / "twstock/export.py").read_text(encoding="utf-8")
    assert '"pct": _pct(c[i], chs[i])' in src and '"pct": _pct(c[i], ch[i])' not in src


# ─── S3：--catch-up（真實流程，只有 HTTP 與資料庫是假的）───
class Resp:
    def __init__(self, data=None, text=None, status=200):
        self.data, self.status_code = data, status
        self.content = (text or "").encode("cp950", errors="replace")

    def json(self):
        if self.data is None:
            raise ValueError("不是 JSON")
        return self.data

    def raise_for_status(self):
        pass


TWSE_CODES = [str(c) for c in range(1100, 2200)]      # 1100 檔
TPEX_CODES = [str(c) for c in range(3000, 3900)]      # 900 檔
MI_FIELDS = ["證券代號", "證券名稱", "成交股數", "成交筆數", "成交金額", "開盤價", "最高價", "最低價", "收盤價",
             "漲跌(+/-)", "漲跌價差"]
T86_FIELDS = ["證券代號", "外陸資買賣超股數(不含外資自營商)", "外資自營商買賣超股數", "投信買賣超股數", "自營商買賣超股數", "三大法人買賣超股數"]
Q_FIELDS = ["代號", "名稱", "收盤", "漲跌", "開盤", "最高", "最低", "成交股數", "成交金額(元)", "成交筆數"]
INX_FIELDS = ["日期", "開市", "最高", "最低", "收市", "漲/跌"]
FUT_HEAD = "交易日期,契約,到期月份(週別),開盤價,最高價,最低價,收盤價,漲跌價,漲跌%,成交量,結算價,未沖銷契約數,最後最佳買價,最後最佳賣價,歷史最高價,歷史最低價,是否因訊息面暫停交易,交易時段,價差對單式委託成交量\r\n"
OI_HEAD = "日期,商品名稱,身份別,多方交易口數,多方交易契約金額(千元),空方交易口數,空方交易契約金額(千元),多空交易口數淨額,多空交易契約金額淨額(千元),多方未平倉口數,多方未平倉契約金額(千元),空方未平倉口數,空方未平倉契約金額(千元),多空未平倉口數淨額,多空未平倉契約金額淨額(千元)\r\n"
ALL_EP = ("MI_INDEX", "BWIBBU_d", "fund/T86", "BFI82U", "dailyQuotes", "peQryDate", "dailyTrade", "futDataDown", "futContractsDateDown")


class World:
    """假的官方網站與資料庫。published = {端點: 已公布的日期}；rows 由真實的 MERGE 語句寫入。"""

    def __init__(self, seed_until, unsettled=False):
        self.published = {ep: set() for ep in ALL_EP}
        self.renamed, self.down, self.requests, self.merges = set(), set(), [], []
        self.cells = defaultdict(lambda: defaultdict(dict))     # {表: {日期: {鍵: 列}}}
        self.rows = {s.key: {} for s in health.SPECS}
        self.runs, self.holidays, self.exports, self.notices = [], [], 0, []
        self.run_updates = []                                   # finish_run：(outcome, export_seconds, run_id)
        self.revenue = {(2026, 8): 1980, (2026, 9): 1980}
        days = tradingcal.trading_days(seed_until - timedelta(days=45), seed_until, CLOSED)
        self.rows.update(_full_snapshot(days))
        if not unsettled:       # 沒有日期的資料：seed_until 當晚都已成功
            self.runs.append((datetime.combine(seed_until, datetime.min.time()).replace(hour=19, minute=35), 1, json.dumps(
                {"undated": {"alerts": f"{seed_until}T19:35:00+08:00", "events_to": str(seed_until), "revenue": str(seed_until)}})))
        # 官方日曆新鮮，不發請求
        self.holidays = [(h, "official", datetime(2026, 10, 20)) for h in sorted(tradingcal.HOLIDAYS) if h.year == 2026]

    def publish(self, d, *skip):
        for ep in ALL_EP:
            if ep not in skip:
                self.published[ep].add(d)

    def paths(self):
        return [p for p, _ in self.requests]

    # ── HTTP ──
    def http(self, method, url, timeout=30, params=None, data=None):
        form = params or data or {}
        path = re.sub(r"https://[^/]+", "", url)
        self.requests.append((path, form))
        for ep in self.down:
            if ep in url:
                return Resp(status=500)
        if "holidaySchedule" in url:
            return Resp(CAL)
        for key, fn in (("MI_INDEX", self._mi), ("BWIBBU_d", self._bwi), ("fund/T86", self._t86), ("BFI82U", self._bfi),
                        ("dailyQuotes", self._quotes), ("peQryDate", self._pe), ("dailyTrade", self._tpex_insti),
                        ("indexInfo/inx", self._inx), ("futDataDown", self._fut), ("futContractsDateDown", self._oi)):
            if key in url:
                return fn(form)
        return Resp([]) if "openapi" in url else Resp({"stat": "沒有資料", "tables": []})

    @staticmethod
    def _date(form, key="date"):
        s = form.get(key) or form.get("dayDate") or form.get("queryStartDate")
        s = s.replace("/", "")
        return date(int(s[:4]), int(s[4:6]), int(s[6:8]))

    def _no(self, ep, form, key="date"):
        return self._date(form, key) not in self.published[ep]

    def _mi(self, form):
        if self._no("MI_INDEX", form):
            return Resp({"stat": "很抱歉，沒有符合條件的資料!"})
        fields = ["欄位改名"] + MI_FIELDS[1:] if "MI_INDEX" in self.renamed else MI_FIELDS
        rows = [[c, "名", "1000", "10", "10000", "10", "11", "9", "10.5", "+", "0.5"] for c in TWSE_CODES]
        idx = {"title": "價格指數(臺灣證券交易所)", "fields": ["指數", "收盤指數", "漲跌(+/-)", "漲跌點數", "漲跌百分比(%)"],
               "data": [["發行量加權股價指數", "45,211.83", "<p>-</p>", "1,156.50", "-2.49"]]}
        return Resp({"stat": "OK", "tables": [idx, {"fields": fields, "data": rows}]})

    def _bwi(self, form):
        if self._no("BWIBBU_d", form):
            return Resp({"stat": "很抱歉，沒有符合條件的資料!"})
        return Resp({"stat": "OK", "fields": ["證券代號", "證券名稱", "殖利率(%)", "股利年度", "本益比", "股價淨值比", "財報年/季"],
                     "data": [[c, "名", "3.5", 114, "15", "1.5", "115/2"] for c in TWSE_CODES]})

    def _t86(self, form):
        if self._no("fund/T86", form):
            return Resp({"stat": "很抱歉，沒有符合條件的資料!"})
        fields = ["改名"] + T86_FIELDS[1:] if "fund/T86" in self.renamed else T86_FIELDS
        return Resp({"stat": "OK", "fields": fields, "data": [[c, "1,000", "0", "0", "0", "1,000"] for c in TWSE_CODES]})

    def _bfi(self, form):
        if self._no("BFI82U", form):
            return Resp({"stat": "很抱歉，沒有符合條件的資料!"})
        names = ["自營商(自行買賣)", "自營商(避險)", "投信", "外資及陸資(不含外資自營商)", "外資自營商", "合計"]
        return Resp({"stat": "OK", "fields": ["單位名稱", "買進金額", "賣出金額", "買賣差額"], "data": [[n, "1", "1", "0"] for n in names]})

    def _empty_tables(self, fields):
        return Resp({"stat": "ok", "tables": [{"fields": fields, "data": []}]})

    def _quotes(self, form):
        if self._no("dailyQuotes", form):
            return self._empty_tables(Q_FIELDS)
        return Resp({"stat": "ok", "tables": [{"fields": Q_FIELDS, "data": [[c, "名", "10.5", "0.5", "10", "11", "9", "1000", "10000", "10"] for c in TPEX_CODES]}]})

    def _pe(self, form):
        if self._no("peQryDate", form):
            return self._empty_tables(PE_FIELDS)
        fields = [f.replace("股票代號", "證券代碼") for f in PE_FIELDS] if "peQryDate" in self.renamed else PE_FIELDS
        return Resp({"stat": "ok", "tables": [{"fields": fields, "data": [[c, "名", "15", "1", 114, "3.5", "1.5", "115Q2"] for c in TPEX_CODES]}]})

    def _tpex_insti(self, form):
        if self._no("dailyTrade", form):
            return self._empty_tables(["代號"])
        return Resp({"stat": "ok", "tables": [{"fields": ["代號"], "data": [[c] + ["1"] * 23 for c in TPEX_CODES]}]})

    def _inx(self, form):
        y, m = self._date(form).year, self._date(form).month
        days = sorted(d for d in self.published["MI_INDEX"] if d.year == y and d.month == m)
        rows = [[f"{d:%Y/%m/%d}", "384.20", "384.20", "365.70", "370.26", "-17.11"] for d in days]
        return Resp({"stat": "ok", "tables": [{"fields": INX_FIELDS, "data": rows}]})

    def _fut(self, form):
        s, e = self._date(form, "queryStartDate"), datetime.strptime(form["queryEndDate"], "%Y/%m/%d").date()
        text = FUT_HEAD
        for d in sorted(self.published["futDataDown"]):
            if s <= d <= e:
                for m in ("202611", "202612", "202701", "202703", "202706", "202709"):
                    text += f"{d:%Y/%m/%d},TX,{m},1,2,1,2,0,0,10,2,100,,,,,,一般,0\r\n"
        return Resp(text=text)

    def _oi(self, form):
        s, e = self._date(form, "queryStartDate"), datetime.strptime(form["queryEndDate"], "%Y/%m/%d").date()
        days = [d for d in sorted(self.published["futContractsDateDown"]) if s <= d <= e]
        if not days:        # 實測：查無資料時是 200 ＋ alert 後導回查詢頁
            return Resp(text='<html><script>alert("x");window.location.replace("futContractsDateView");</script></html>')
        text = OI_HEAD
        for d in days:
            for who in ("自營商", "投信", "外資及陸資"):
                text += f"{d:%Y/%m/%d},臺股期貨,{who},1,1,1,1,0,0,1,1,1,1,0,0\r\n"
        return Resp(text=text)

    # ── 資料庫 ──
    def apply_merge(self, table, sql, params):
        self.merges.append(table)
        rows = json.loads(params[0])
        pd = next((p for p in params[1:] if isinstance(p, date)), None)
        market = lambda c: "TWSE" if c < "3000" else "TPEx"
        if table in ("daily_prices", "stock_fundamentals", "institutional_trades"):
            name = {"daily_prices": "prices", "stock_fundamentals": "pe", "institutional_trades": "insti"}[table]
            for mk in ("TWSE", "TPEx"):
                mine = [r for r in rows if market(r["stock_code"]) == mk]
                if mine:
                    cnt = lambda f: sum(r.get(f) is not None for r in mine)
                    self.rows[f"{name}.{mk}"][pd] = Row(len(mine), cnt("pe_ratio"), cnt("pb_ratio"), cnt("dividend_yield"))
        elif table == "market_index":
            for r in rows:
                self.rows[f"index.{r['index_code']}"][date.fromisoformat(r["trade_date"])] = Row(1)
        elif table == "insti_amount":
            self.rows["amount"][date.fromisoformat(rows[0]["trade_date"])] = Row(len(rows))
        elif table == "futures_daily_prices":
            for d in {r["trade_date"] for r in rows}:
                self.rows["futures"][date.fromisoformat(d)] = Row(sum(r["trade_date"] == d for r in rows))
        elif table == "futures_institutional":
            for d in {r["trade_date"] for r in rows}:
                cur = self.rows["futures_oi"].get(date.fromisoformat(d), Row()).n
                self.rows["futures_oi"][date.fromisoformat(d)] = Row(cur + sum(r["trade_date"] == d for r in rows))

    def snapshot(self, cur, start, end):
        return {k: {d: r for d, r in v.items() if start <= d <= end} for k, v in self.rows.items()}


class FakeCursor:
    def __init__(self, world):
        self.w, self.result, self.rowcount = world, [], 0

    def execute(self, sql, *params):
        w, self.result = self.w, []
        m = re.search(r"MERGE (\w+)", sql)
        if m and m.group(1) == "market_holidays":
            if "'adhoc'" in sql:
                w.holidays.append((params[0], "adhoc", params[2]))
            else:
                w.holidays.append((params[0], "official", params[2]))
        elif m and m.group(1) != "stocks":
            w.apply_merge(m.group(1), sql, params)
        elif m:
            w.merges.append("stocks")
        elif "SELECT MAX(trade_date) FROM daily_prices" in sql:
            ds = sorted(w.rows["prices.TWSE"])
            self.result = [(ds[-1] if ds else None,)]
        elif "holiday_date, source, fetched_at" in sql:
            self.result = list(w.holidays)
        elif "SELECT holiday_date, source" in sql:
            self.result = [(d, s) for d, s, _ in w.holidays]
        elif "SELECT holiday_date FROM market_holidays" in sql:
            self.result = [(d,) for d, s, _ in w.holidays if s == "adhoc"]
        elif sql.startswith("DELETE FROM market_holidays") and "adhoc" in sql:
            w.holidays = [h for h in w.holidays if not (h[0] == params[0] and h[1] == "adhoc")]
        elif "FROM collect_runs" in sql:
            self.result = list(reversed(w.runs))
        elif sql.startswith("INSERT INTO collect_runs"):
            w.runs.append((params[2], params[4], params[6]))
            self.result = [(len(w.runs),)]
        elif sql.startswith("UPDATE collect_runs"):
            w.run_updates.append(params)
        elif "SELECT COUNT(*) FROM" in sql:
            self.result = [(0,)]
        elif "revenue_year, revenue_month, COUNT" in sql:
            self.result = [(y, m, n) for (y, m), n in w.revenue.items()]
        return self

    def fetchone(self):
        return self.result[0] if self.result else None

    def fetchall(self):
        return self.result


class FakeConn:
    def __init__(self, world):
        self.w = world

    def cursor(self):
        return FakeCursor(self.w)

    def commit(self):
        pass

    def close(self):
        pass


REAL_STATUS_CHANGED = catchup.status_changed     # env() 會換掉它；QA-02 的測試要用真的


@contextlib.contextmanager
def env(world, lock=True, connect_error=None):
    fetch._dead_hosts.clear()

    def fake_connect(autocommit=False):
        if connect_error:
            raise connect_error
        return FakeConn(world)

    def fake_export():
        world.exports += 1
        return 1.0

    def fake_notify(problems, today):
        world.notices.append(problems)
        return True

    with mock.patch.object(fetch._SESSION, "request", world.http), mock.patch.object(fetch, "RETRY_BACKOFF", ()), \
            mock.patch.object(fetch, "MIN_INTERVAL", {}), mock.patch.object(fetch, "DEFAULT_INTERVAL", 0), \
            mock.patch.object(db, "connect", fake_connect), \
            mock.patch.object(db, "acquire_lock", lambda: FakeConn(world) if lock else None), \
            mock.patch.object(db, "release_lock", lambda c: None), \
            mock.patch.object(catchup, "load_snapshot", world.snapshot), \
            mock.patch.object(history, "load_snapshot", world.snapshot), \
            mock.patch.object(catchup, "chains_age_days", lambda: 1), \
            mock.patch.object(catchup, "status_changed", lambda *a: False), \
            mock.patch.object(catchup.time, "sleep", lambda s: None), \
            mock.patch.object(export, "export_all", fake_export), \
            mock.patch.object(health, "notify_once", fake_notify):
        yield


def run_world(world, now, days=10, date_=None, lock=True, connect_error=None):
    buf = io.StringIO()
    with env(world, lock, connect_error), contextlib.redirect_stdout(buf):
        rc = catchup.run(days=days, date_=date_, now=now, notify=True)
    return rc, buf.getvalue()


def _hit(world, *names):
    return [p for p in world.paths() if any(n in p for n in names)]


FIRST_DAY = D(11, 2)    # 週一


def test_s3_01_t86_late():
    w = World(D(10, 30))
    w.publish(FIRST_DAY, "fund/T86")
    rc, out = run_world(w, T(11, 2, 17, 30))
    assert rc == 0 and w.rows["prices.TWSE"][FIRST_DAY].n == 1100 and w.rows["pe.TWSE"][FIRST_DAY].n == 1100
    assert FIRST_DAY not in w.rows["insti.TWSE"] and "上市法人：2026-11-02 尚未公布" in out
    assert w.exports == 1
    w.requests.clear()
    w.published["fund/T86"].add(FIRST_DAY)
    rc, out = run_world(w, T(11, 2, 18, 30))
    assert rc == 0 and w.paths() == ["/rwd/zh/fund/T86"] and w.rows["insti.TWSE"][FIRST_DAY].n == 1100
    assert w.exports == 2


def test_s3_02_not_published_vs_holiday():
    w = World(D(10, 30))
    rc, out = run_world(w, T(11, 2, 17, 30))
    assert rc == 0 and "上市行情：2026-11-02 尚未公布" in out and "休市" not in out
    assert _hit(w, "MI_INDEX") and not _hit(w, "BWIBBU_d", "fund/T86", "peQryDate", "dailyTrade")     # 行情還沒有，不打同市場的本益比與法人
    w = World(D(12, 24))
    rc, out = run_world(w, T(12, 25, 17, 30))
    assert rc == 0 and not _hit(w, "MI_INDEX") and "今天 2026-12-25 休市" in out and w.exports == 0


def test_s3_03_next_morning():
    w = World(D(10, 30))
    w.publish(FIRST_DAY)
    rc, _ = run_world(w, T(11, 3, 9, 0))
    assert rc == 0 and FIRST_DAY in w.rows["prices.TWSE"] and D(11, 3) not in w.rows["prices.TWSE"]
    assert [f["date"] for p, f in w.requests if "MI_INDEX" in p] == ["20261102"]


def test_s3_04_friday_and_monday():
    w = World(D(10, 29))
    w.publish(D(10, 30))
    w.publish(FIRST_DAY)
    rc, _ = run_world(w, T(11, 2, 18, 0))
    assert rc == 0 and [f["date"] for p, f in w.requests if "MI_INDEX" in p] == ["20261030", "20261102"]
    assert D(10, 30) in w.rows["insti.TPEx"] and FIRST_DAY in w.rows["insti.TPEx"]


def test_s3_05_tpex_empty():
    w = World(D(10, 30))
    w.publish(FIRST_DAY, "dailyQuotes")
    rc, out = run_world(w, T(11, 2, 22, 30))
    assert rc == 1 and FIRST_DAY in w.rows["prices.TWSE"] and FIRST_DAY not in w.rows["prices.TPEx"]
    assert "上櫃行情：缺 2026-11-02" in out and not _hit(w, "peQryDate", "dailyTrade")
    w.requests.clear()
    w.published["dailyQuotes"].add(FIRST_DAY)
    rc, _ = run_world(w, T(11, 3, 9, 0))
    assert rc == 0 and w.rows["prices.TPEx"][FIRST_DAY].n == 900 and "/www/zh-tw/afterTrading/dailyQuotes" in w.paths()
    # history 共用同一套判斷：有上市、沒上櫃的日期不跳過
    snap = {k: dict(v) for k, v in w.rows.items()}
    del snap["prices.TPEx"][FIRST_DAY]
    assert health.missing_keys(FIRST_DAY, ("prices.TWSE", "prices.TPEx"), snap, health.medians(snap)) == ("prices.TPEx",)


def test_s3_06_fetch_error():
    w = World(D(10, 30))
    w.publish(FIRST_DAY)
    w.down.add("BWIBBU_d")
    rc, out = run_world(w, T(11, 2, 18, 0))
    assert rc == 1 and len(_hit(w, "BWIBBU_d")) == 1            # 重試用盡（測試設為不重試）只打一次
    assert not _hit(w, "fund/T86", "BFI82U")                    # 同主機本次不再請求
    assert _hit(w, "dailyTrade", "futDataDown")                 # 其他主機照常
    assert FIRST_DAY in w.rows["prices.TWSE"] and FIRST_DAY in w.rows["insti.TPEx"]
    assert w.exports == 1 and "上市本益比" in out               # 已寫入的資料有匯出
    assert w.notices and any("pe.TWSE" in k for k in w.notices[0])


def test_s3_07_schema_change():
    for ep, label in (("peQryDate", "上櫃本益比"), ("fund/T86", "上市法人"), ("MI_INDEX", "上市行情")):
        w = World(D(10, 30))
        w.publish(FIRST_DAY)
        w.renamed.add(ep)
        rc, out = run_world(w, T(11, 2, 18, 0))
        assert rc == 1 and "Traceback" not in out and f"❌ {label}" in out, ep
        assert FIRST_DAY in w.rows["prices.TPEx"] and FIRST_DAY in w.rows["insti.TPEx"], ep    # 其他資料集照常
        assert w.exports == 1, ep
    # 上櫃本益比欄位不符：其他同主機資料照常（欄位不符不是主機問題）
    w = World(D(10, 30))
    w.publish(FIRST_DAY)
    w.renamed.add("peQryDate")
    run_world(w, T(11, 2, 18, 0))
    assert FIRST_DAY in w.rows["pe.TWSE"] and FIRST_DAY not in w.rows["pe.TPEx"]


def test_s3_08_db_down():
    w = World(D(10, 30))
    w.publish(FIRST_DAY)
    rc, out = run_world(w, T(11, 2, 18, 0), connect_error=pyodbc.OperationalError("HYT00", "timeout"))
    assert rc == 2 and "Docker" in out and "Traceback" not in out and w.exports == 0 and w.requests == []
    assert w.notices and "db" in w.notices[0]


def test_s3_09_complete():
    w = World(D(11, 2))
    rc, out = run_world(w, T(11, 2, 19, 40))
    assert rc == 0 and w.requests == [] and w.exports == 0 and w.merges == [] and "不匯出" in out


def test_s3_10_run_twice():
    w = World(D(10, 30))
    w.publish(FIRST_DAY)
    assert run_world(w, T(11, 2, 18, 0))[0] == 0
    n = w.rows["prices.TWSE"][FIRST_DAY].n
    w.requests.clear(), w.merges.clear()
    rc, _ = run_world(w, T(11, 2, 18, 5))
    assert rc == 0 and w.requests == [] and w.merges == [] and w.rows["prices.TWSE"][FIRST_DAY].n == n and w.exports == 1


def test_s3_11_locked():
    w = World(D(10, 30))
    w.publish(FIRST_DAY)
    rc, out = run_world(w, T(11, 2, 18, 0), lock=False)
    assert rc == 0 and "另一個收集程序" in out and w.requests == [] and w.exports == 0 and len(w.runs) == 1


def test_s3_12_tpex_index_old_month():
    w = World(D(10, 30))
    del w.rows["index.TPEX"][D(10, 30)]
    w.published["MI_INDEX"].add(D(10, 30))
    w.publish(FIRST_DAY)
    rc, _ = run_world(w, T(11, 2, 18, 0))
    assert rc == 0 and D(10, 30) in w.rows["index.TPEX"] and FIRST_DAY in w.rows["index.TPEX"]
    assert sorted(f["date"] for p, f in w.requests if "indexInfo/inx" in p) == ["2026/10/01", "2026/11/01"]


def test_s3_adhoc_closure_flow():
    # 11/02 全部沒有資料（颱風假），11/03 補跑 → 判定臨時休市，不再列為缺漏，下次不再請求
    w = World(D(10, 30))
    w.publish(D(11, 3))
    rc, out = run_world(w, T(11, 3, 18, 0))
    assert rc == 0 and "判定為臨時休市" in out and (FIRST_DAY, "adhoc") in [(d, s) for d, s, _ in w.holidays]
    w.requests.clear()
    rc, _ = run_world(w, T(11, 3, 18, 10))
    assert rc == 0 and w.requests == []
    # 期交所有資料：不判定，算異常
    w = World(D(10, 30))
    w.published["futDataDown"].add(FIRST_DAY)
    w.publish(D(11, 3))
    rc, out = run_world(w, T(11, 3, 18, 0))
    assert rc == 1 and "判定為臨時休市" not in out and not [h for h in w.holidays if h[1] == "adhoc"]
    # 查詢失敗：不判定
    w = World(D(10, 30))
    w.down.add("MI_INDEX")
    rc, out = run_world(w, T(11, 3, 18, 0))
    assert rc == 1 and not [h for h in w.holidays if h[1] == "adhoc"]
    # 錯判復原：collect --date 查到資料就移除判定
    w = World(D(10, 30))
    w.holidays.append((FIRST_DAY, "adhoc", datetime(2026, 11, 3, 18)))
    w.publish(FIRST_DAY)
    rc, out = run_world(w, T(11, 4, 9, 0), date_=FIRST_DAY)
    assert rc == 0 and "移除臨時休市判定" in out and FIRST_DAY in w.rows["prices.TWSE"]
    assert not [h for h in w.holidays if h[1] == "adhoc"]


def test_s3_collect_date_compat():
    # --date：已有資料也全部重抓覆寫；一定匯出；舊日期不影響今天
    w = World(D(10, 30))
    w.publish(D(10, 30))
    rc, _ = run_world(w, T(11, 2, 18, 0), date_=D(10, 30))
    assert rc == 0 and w.exports == 1
    assert [f["date"] for p, f in w.requests if "MI_INDEX" in p] == ["20261030"]
    assert _hit(w, "BWIBBU_d") and _hit(w, "fund/T86") and _hit(w, "peQryDate") and _hit(w, "dailyTrade") and _hit(w, "BFI82U")
    # 休市日：不發行情請求，仍匯出，回傳 0
    w = World(D(10, 30))
    rc, out = run_world(w, T(10, 31, 12, 0), date_=D(10, 31))
    assert rc == 0 and not _hit(w, "MI_INDEX") and "休市" in out and w.exports == 1


def test_s3_gap_hint():
    w = World(D(10, 2))
    for d in tradingcal.trading_days(D(10, 5), FIRST_DAY, CLOSED):
        w.publish(d)
    rc, out = run_world(w, T(11, 2, 18, 0), days=3)
    assert rc == 1 and "python -m twstock history --start 2026-10-05" in out


def test_history_pe_only():
    # S1 回補：只打櫃買本益比端點；上市列不動；可中斷重跑；重跑待抓 0 天
    days = [D(10, 28), D(10, 29), D(10, 30)]
    w = World(D(10, 30))
    for d in days[:2]:
        w.rows["pe.TPEx"][d] = Row(893, 676, 893, 2)    # 舊腳本寫的：列都在，殖利率幾乎全空
    w.rows["pe.TPEx"][days[2]] = Row(2, 2, 2, 2)
    twse_before = dict(w.rows["pe.TWSE"])
    w.published["peQryDate"].update(days[:2])           # 10/30 暫時失敗
    w.down.add("/nothing")
    buf = io.StringIO()
    with env(w), contextlib.redirect_stdout(buf):
        assert history.run_history(days[0], days[2], ("pe",)) is True
    assert "待抓 3 天" in buf.getvalue() and "pe.TPEx：3 天" in buf.getvalue() and "pe.TWSE" not in buf.getvalue().split("[1/3]")[0]
    assert set(w.paths()) == {"/www/zh-tw/afterTrading/peQryDate"} and len(w.paths()) == 3
    assert w.rows["pe.TPEx"][days[0]].dy == 900 and w.rows["pe.TWSE"] == twse_before
    # 中斷：端點失敗就停在該日，已寫入的不重抓
    w.requests.clear()
    w.down.add("peQryDate")
    with env(w), contextlib.redirect_stdout(io.StringIO()):
        assert history.run_history(days[0], days[2], ("pe",)) is False
    assert len(w.paths()) == 1 and w.requests[0][1]["date"] == "2026/10/30"
    # 重跑接續
    w.requests.clear()
    w.down.clear()
    w.published["peQryDate"].add(days[2])
    with env(w), contextlib.redirect_stdout(io.StringIO()):
        assert history.run_history(days[0], days[2], ("pe",)) is True
    assert [f["date"] for _, f in w.requests] == ["2026/10/30"]
    # 全部齊全：待抓 0 天，不發請求
    w.requests.clear()
    buf = io.StringIO()
    with env(w), contextlib.redirect_stdout(buf):
        assert history.run_history(days[0], days[2], ("pe",)) is True
    assert "待抓 0 天" in buf.getvalue() and w.requests == []
    # 欄位不符：停下來，不把每天的請求都浪費掉
    w = World(D(10, 30))
    for d in days:
        w.rows["pe.TPEx"][d] = Row(893, 676, 893, 2)
    w.publish(days[0])
    w.renamed.add("peQryDate")
    with env(w), contextlib.redirect_stdout(io.StringIO()):
        assert history.run_history(days[0], days[2], ("pe",)) is False
    assert len(w.paths()) == 1


def test_history_tpex_index():
    w = World(D(10, 30))
    w.rows["index.TPEX"] = {d: r for d, r in w.rows["index.TPEX"].items() if d.month == 10}
    w.published["MI_INDEX"].update(tradingcal.trading_days(D(9, 25), D(9, 30), CLOSED))
    buf = io.StringIO()
    with env(w), contextlib.redirect_stdout(buf):
        assert history.run_history(D(9, 29), D(10, 30), ("tpex_index",)) is True
    assert [f["date"] for _, f in w.requests] == ["2026/09/01"] and D(9, 30) in w.rows["index.TPEX"]   # 10 月已齊全，不打


def test_plan_pure():
    days = tradingcal.trading_days(D(10, 1), D(11, 2), CLOSED)
    snap = _full_snapshot(days, skip={("insti.TWSE", D(10, 30)), ("futures", D(10, 29)), ("futures", D(10, 30))})
    state = {"alerts_at": datetime(2026, 11, 2, 18), "events_to": D(11, 2), "revenue_on": D(11, 2), "collected_at": None}
    p = catchup.make_plan(T(11, 2, 18, 30), 10, snap, state, CLOSED, {(2026, 8): 1980, (2026, 9): 1980})
    assert p["by_date"] == [(D(10, 30), ("insti.TWSE",))] and p["futures"] == (D(10, 29), D(10, 30))
    assert p["alerts"] is False and p["events"] is None and p["revenue"] == []
    # 19:00 後再抓一次處置／注意股；已抓過就不再抓
    assert catchup.make_plan(T(11, 2, 19, 30), 10, snap, state, CLOSED, {})["alerts"] is True
    state2 = dict(state, alerts_at=datetime(2026, 11, 2, 19, 30))
    assert catchup.make_plan(T(11, 2, 21, 45), 10, snap, state2, CLOSED, {})["alerts"] is False
    # 事件查詢區間涵蓋最舊缺口
    state3 = dict(state, events_to=D(10, 28))
    assert catchup.make_plan(T(11, 2, 18, 30), 10, snap, state3, CLOSED, {})["events"] == (D(10, 21), D(11, 2))
    # 月營收：10 日後才收上個月，公布完成（≥ 前月 98%）就不再請求
    snap2 = _full_snapshot(tradingcal.trading_days(D(10, 15), D(11, 12), CLOSED))
    st = dict(state, revenue_on=None)
    assert catchup.make_plan(T(11, 12, 18), 10, snap2, st, CLOSED, {(2026, 9): 1980, (2026, 10): 1000})["revenue"] == [(2026, 10)]
    assert catchup.make_plan(T(11, 12, 18), 10, snap2, st, CLOSED, {(2026, 9): 1980, (2026, 10): 1950})["revenue"] == []
    st = dict(state, revenue_on=D(11, 12))
    assert catchup.make_plan(T(11, 12, 21), 10, snap2, st, CLOSED, {(2026, 9): 1980, (2026, 10): 1000})["revenue"] == []


def test_run_record():
    # 執行紀錄的時間是台灣時間；有新資料才標 new_data；「更新於」取最後一次有新資料的時間
    calls = []

    class Cur:
        def execute(self, sql, *p):
            calls.append((sql, p))
            return self

        def fetchone(self):
            return (7,)
    t0 = T(11, 2, 17, 30)
    assert health.write_run(Cur(), "catch-up", t0, t0 + timedelta(minutes=2), "pending", True, 12, {"written": {"prices.TWSE": {"2026-11-02": 1090}}}) == 7
    sql, p = calls[0]
    assert "GETDATE" not in sql and p[1] == datetime(2026, 11, 2, 17, 30) and p[2] == datetime(2026, 11, 2, 17, 32) and p[4] == 1
    assert json.loads(p[6])["written"]["prices.TWSE"]["2026-11-02"] == 1090
    health.finish_run(Cur(), 7, "abnormal", None)
    sql, p = calls[1]
    assert p == ("abnormal", None, 7) and "finished_at" not in sql     # 不可改動「更新於」的依據

    class Cur2:
        def execute(self, sql, *p):
            return self

        def fetchall(self):     # 新到舊
            return [(datetime(2026, 11, 2, 21, 45), 0, "{}"),
                    (datetime(2026, 11, 2, 19, 31), 1, json.dumps({"undated": {"alerts": "2026-11-02T19:30:00+08:00"}})),
                    (datetime(2026, 11, 2, 17, 32), 1, json.dumps({"undated": {"events_to": "2026-11-02", "revenue": "2026-11-02"}}))]
    st = health.load_state(Cur2())
    assert st["collected_at"] == datetime(2026, 11, 2, 19, 31) and st["events_to"] == D(11, 2) and st["alerts_at"].hour == 19
    assert health.collected_at(None, st) == ("2026-11-02T19:31:00+08:00", "run")


def test_guard_runtime_error():
    errors = {}

    def boom():
        raise RuntimeError("產業鏈解析不到")
    with contextlib.redirect_stdout(io.StringIO()):
        assert catchup._guard("chains", errors, boom) is False
    assert "chains" in errors


def test_schedule_scripts_static():
    # 只讀檔案內容，不執行、不安裝
    sh = (ROOT / "scripts/mac/install_schedule.sh").read_text(encoding="utf-8")
    assert sh.index('"--print"') < sh.index("launchctl bootout")          # 預覽模式在任何 launchctl 之前結束
    for t in ('"17 30"', '"19 30"', '"21 45"', "/usr/bin/caffeinate", "<string>--catch-up</string>", "RunAtLoad", "logs/collect.log"):
        assert t in sh, t
    bat = (ROOT / "scripts/windows/install_schedule.bat").read_text(encoding="utf-8")
    for t in ("17:30", "19:30", "21:45", "/uninstall"):
        assert t in bat, t
    assert "--catch-up" in (ROOT / "scripts/windows/collect.bat").read_text(encoding="utf-8")
    assert "--catch-up" in (ROOT / "scripts/mac/collect.command").read_text(encoding="utf-8")


def test_futures_no_data_page():
    # 期交所法人端點查無資料回 200 ＋ alert 頁，不是封鎖；真的不是 CSV 才是 FetchError
    w = World(D(10, 30))
    with env(w):
        assert futures.fetch_futures_institutional(D(10, 23), D(10, 23)) == []
    with mock.patch.object(futures, "request", lambda *a, **k: Resp(text="<html>Forbidden</html>")):
        try:
            futures.fetch_futures_institutional(D(10, 23), D(10, 23))
            assert False
        except FetchError:
            pass


def test_status_changed():
    with tempfile.TemporaryDirectory() as tmp, mock.patch.object(catchup, "SITE_DATA_DIR", Path(tmp)):
        now = [{"k": "a", "s": "ok", "d": "2026-10-30"}]
        assert catchup.status_changed(now) is True      # 沒有 latest.json
        (Path(tmp) / "latest.json").write_text(json.dumps({"status": {"datasets": now}}), encoding="utf-8")
        assert catchup.status_changed(now) is False
        assert catchup.status_changed([{"k": "a", "s": "abnormal", "d": "2026-10-30"}]) is True


def test_dead_host():
    fetch._dead_hosts.clear()
    calls = []

    def boom(*a, **k):
        calls.append(1)
        return Resp(status=503)
    with mock.patch.object(fetch._SESSION, "request", boom), mock.patch.object(fetch, "RETRY_BACKOFF", ()), \
            mock.patch.object(fetch, "MIN_INTERVAL", {}), mock.patch.object(fetch, "DEFAULT_INTERVAL", 0):
        for _ in range(3):
            try:
                fetch.request("GET", "https://www.twse.com.tw/x")
                assert False
            except FetchError:
                pass
    assert len(calls) == 1
    fetch._dead_hosts.clear()


# ─── QA 修正（05-qa.md 的 QA-01、QA-02、第五節 (d)）──────────
def test_request_isolated():
    # 附屬查詢：失敗不重試、不標記主機；一般請求維持退避後標記
    fetch._dead_hosts.clear()
    calls = []

    def html(*a, **k):
        calls.append(1)
        return Resp(text="<html>維護中</html>")
    with mock.patch.object(fetch._SESSION, "request", html), mock.patch.object(fetch, "RETRY_BACKOFF", (30, 60, 120)), \
            mock.patch.object(fetch, "MIN_INTERVAL", {}), mock.patch.object(fetch, "DEFAULT_INTERVAL", 0), \
            mock.patch.object(fetch.time, "sleep", lambda s: None), contextlib.redirect_stdout(io.StringIO()):
        for isolated, n, dead in ((True, 1, False), (False, 4, True)):
            calls.clear()
            try:
                fetch.request("GET", "https://www.twse.com.tw/x", isolated=isolated)
                assert False
            except FetchError:
                pass
            assert len(calls) == n and ("www.twse.com.tw" in fetch._dead_hosts) is dead
    fetch._dead_hosts.clear()


class CalBroken(World):
    """休市表端點壞掉（其他端點正常），官方表已超過 30 天未更新。"""

    def __init__(self, seed_until, cal):
        super().__init__(seed_until)
        self.cal = cal
        self.holidays = [(d, s, datetime(2026, 9, 1)) for d, s, _ in self.holidays]

    def http(self, method, url, **k):
        if "holidaySchedule" in url:
            self.requests.append(("holidaySchedule", {}))
            return self.cal
        return super().http(method, url, **k)


def test_qa01_calendar_failure_isolated():
    # 回 500、回 HTML、欄位改名：上市資料都要照收，主機不標記，沿用已存的官方表並記錄警告
    for cal in (Resp(status=500), Resp(text="<html>維護中</html>"), Resp({"fields": ["改名"], "data": []})):
        w = CalBroken(D(10, 30), cal)
        n_official = len(w.holidays)
        w.publish(FIRST_DAY)
        buf = io.StringIO()
        # 用真實的退避參數：休市表不可重試，否則每次排程多等 3.5 分鐘
        with env(w), mock.patch.object(fetch, "RETRY_BACKOFF", (30, 60, 120)), contextlib.redirect_stdout(buf):
            rc = catchup.run(now=T(11, 2, 18, 0), notify=True)
            assert "www.twse.com.tw" not in fetch._dead_hosts
        out = buf.getvalue()
        assert rc == 0 and w.paths().count("holidaySchedule") == 1 and w.paths()[0] == "holidaySchedule"
        assert _hit(w, "MI_INDEX", "BWIBBU_d", "fund/T86", "BFI82U")
        for k in ("prices.TWSE", "pe.TWSE", "insti.TWSE", "amount", "index.TAIEX"):
            assert FIRST_DAY in w.rows[k], k
        assert "沿用已存的官方表" in out and len(w.holidays) == n_official
        assert "官方休市表更新失敗" in json.loads(w.runs[-1][2])["warnings"][0]
        assert w.exports == 1 and w.notices == []
    # 端點正常時不留警告
    w = World(D(10, 30))
    w.publish(FIRST_DAY)
    run_world(w, T(11, 2, 18, 0))
    assert "warnings" not in json.loads(w.runs[-1][2])


def run_site(world, now, site, finished=None, export_error=None):
    """真實的 status_changed、build_status；假匯出只寫 status，與真實匯出用同一個函式。finished：固定 tw_now。"""
    def write():
        data_date = max(d for k in ("prices.TWSE", "prices.TPEx") for d in world.rows[k])
        status = health.build_status(FakeCursor(world), data_date, now)
        (site / "latest.json").write_text(json.dumps({"date": str(data_date), "status": status}), encoding="utf-8")

    def exporter():
        world.exports += 1
        if export_error:
            raise export_error
        write()
        return 1.0
    buf = io.StringIO()
    with env(world), mock.patch.object(catchup, "status_changed", REAL_STATUS_CHANGED), mock.patch.object(catchup, "SITE_DATA_DIR", site), \
            mock.patch.object(health, "load_snapshot", world.snapshot), mock.patch.object(export, "export_all", exporter), \
            mock.patch.object(catchup, "tw_now", lambda: finished or T(12, 31)), contextlib.redirect_stdout(buf):
        if not (site / "latest.json").exists():
            write()
        rc = catchup.run(now=now)
    return rc, buf.getvalue(), json.loads((site / "latest.json").read_text(encoding="utf-8"))


def fresh_lines(latest, *times):
    """用 node 跑 app.js 真正的 freshLines；沒有 node 回傳 None。"""
    if not shutil.which("node"):
        return None
    js = (ROOT / "site/app.js").read_text(encoding="utf-8")
    code = js[js.index("function twParts"):js.index("function renderStatus")]
    script = ("const FRESH_HOUR = 18, md = d => d.slice(5).replace('-', '/');\n" + code +
              f"\nconsole.log(JSON.stringify({json.dumps(times)}.map(t => freshLines({json.dumps(latest)}, new Date(t)))));")
    return json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True, timeout=30).stdout)


def test_qa02_adhoc_reaches_site():
    with tempfile.TemporaryDirectory() as tmp:
        # 週一 11/02 颱風，週二早上補跑：判定後要匯出，closed 含 11/02，「更新於」不變
        w = World(D(10, 30))
        rc, out, first = run_site(w, T(10, 30, 22, 0), Path(tmp))
        assert rc == 0 and w.exports == 0 and "2026-11-02" not in first["status"]["closed"]
        lines = fresh_lines(first, "2026-11-03T10:00:00+08:00")
        assert lines is None or lines == [["資料停在 10/30，最新交易日為 11/02，可能尚未收集"]]    # 修正前的誤報
        rc, out, L = run_site(w, T(11, 3, 9, 0), Path(tmp))
        assert rc == 0 and "判定為臨時休市" in out and w.exports == 1 and "2026-11-02" in L["status"]["closed"]
        assert L["status"]["collected_at"] == first["status"]["collected_at"] and w.runs[-1][1] == 0
        lines = fresh_lines(L, "2026-11-03T10:00:00+08:00", "2026-11-03T17:59:00+08:00")
        assert lines is None or lines == [[], []]
        # 再跑一次：沒有變動，不重複匯出
        rc, out, _ = run_site(w, T(11, 3, 10, 0), Path(tmp))
        assert rc == 0 and w.exports == 1 and "沒有新資料，不匯出" in out
    with tempfile.TemporaryDirectory() as tmp:
        # 週五 11/06 颱風，週六早上補跑：整個週末到週一 18:00 前都不可誤報
        w = World(D(11, 5))
        rc, out, first = run_site(w, T(11, 5, 22, 0), Path(tmp))
        rc, out, L = run_site(w, T(11, 7, 10, 0), Path(tmp))
        assert rc == 0 and "判定為臨時休市" in out and w.exports == 1 and "2026-11-06" in L["status"]["closed"]
        lines = fresh_lines(L, "2026-11-07T10:00:00+08:00", "2026-11-08T20:00:00+08:00", "2026-11-09T17:59:00+08:00",
                            "2026-11-09T18:00:00+08:00")
        assert lines is None or lines == [[], [], [], ["資料停在 11/05，最新交易日為 11/09，可能尚未收集"]]
        rc, out, _ = run_site(w, T(11, 8, 10, 0), Path(tmp))
        assert rc == 0 and w.exports == 1


def test_qa02_status_changed_closed():
    with tempfile.TemporaryDirectory() as tmp, mock.patch.object(catchup, "SITE_DATA_DIR", Path(tmp)):
        rows = [{"k": "a", "s": "ok", "d": "2026-10-30"}]
        (Path(tmp) / "latest.json").write_text(json.dumps({"status": {"datasets": rows, "closed": ["2026-10-23"]}}), encoding="utf-8")
        assert catchup.status_changed(rows, ["2026-10-23"]) is False
        assert catchup.status_changed(rows, ["2026-10-23", "2026-11-02"]) is True      # 臨時休市、官方休市表更新
        assert catchup.status_changed(rows, []) is True                                 # 移除錯判
        assert catchup.status_changed(rows) is False                                    # 沒有傳 closed：只比資料集
        (Path(tmp) / "latest.json").write_text(json.dumps({"status": {"datasets": rows}}), encoding="utf-8")
        assert catchup.status_changed(rows, ["2026-10-23"]) is True                     # 舊版 latest.json 沒有 closed


def test_qa08_updated_at_is_this_run():
    # 真實的執行順序與 build_status：「更新於」= 最後一次 new_data=1 的 finished_at，匯出時就要是這次的時間
    at = lambda L: L["status"]["collected_at"]
    with tempfile.TemporaryDirectory() as tmp:
        site = Path(tmp)
        w = World(D(10, 30))
        _, _, L0 = run_site(w, T(10, 30, 22, 0), site)
        assert at(L0) == "2026-10-30T19:35:00+08:00"
        # 17:30 行情公布（法人未公布）：這次的匯出就要是這次的時間，不可出現「資料日 11/02、更新於 10/30」
        w.publish(FIRST_DAY, "fund/T86")
        rc, _, L = run_site(w, T(11, 2, 17, 30), site, T(11, 2, 17, 31))
        assert rc == 0 and w.exports == 1 and w.runs[-1][1] == 1 and L["date"] == "2026-11-02" and at(L) == "2026-11-02T17:31:00+08:00"
        assert w.run_updates[-1] == ("pending", 1.0, len(w.runs))     # 匯出後補上耗時
        # 19:30 法人公布
        w.published["fund/T86"].add(FIRST_DAY)
        rc, _, L = run_site(w, T(11, 2, 19, 30), site, T(11, 2, 19, 31))
        assert rc == 0 and w.exports == 2 and at(L) == "2026-11-02T19:31:00+08:00"
        # 21:45 沒有新資料：不匯出、不推進
        n = len(w.run_updates)
        rc, out, L = run_site(w, T(11, 2, 21, 45), site, T(11, 2, 21, 46))
        assert rc == 0 and w.exports == 2 and w.runs[-1][1] == 0 and at(L) == "2026-11-02T19:31:00+08:00" and "不匯出" in out
        assert len(w.run_updates) == n                                # 沒有匯出就沒有 UPDATE
        # 單獨重新匯出（export 指令）：時間不變
        with env(w), mock.patch.object(health, "load_snapshot", w.snapshot):
            again = health.build_status(FakeCursor(w), FIRST_DAY, T(11, 2, 23, 0))
        assert again["collected_at"] == "2026-11-02T19:31:00+08:00"
        # 隔天收集全部失敗：回傳非 0、new_data=0，不推進
        w.down.update(ALL_EP)
        rc, _, L = run_site(w, T(11, 3, 18, 0), site, T(11, 3, 18, 1))
        assert rc == 1 and w.runs[-1][1] == 0 and at(L) == "2026-11-02T19:31:00+08:00"
    with tempfile.TemporaryDirectory() as tmp:
        # 部分失敗但有寫入新資料：算收集到新資料，要推進
        site = Path(tmp)
        w = World(D(10, 30))
        run_site(w, T(10, 30, 22, 0), site)
        w.publish(FIRST_DAY)
        w.down.add("fund/T86")
        rc, _, L = run_site(w, T(11, 2, 18, 0), site, T(11, 2, 18, 1))
        assert rc == 1 and w.runs[-1][1] == 1 and at(L) == "2026-11-02T18:01:00+08:00"
    with tempfile.TemporaryDirectory() as tmp:
        # 匯出失敗：紀錄改為異常、沒有耗時；網站維持舊檔（不會提前顯示新時間），下次匯出才是這次的時間
        site = Path(tmp)
        w = World(D(10, 30))
        _, _, L0 = run_site(w, T(10, 30, 22, 0), site)
        w.publish(FIRST_DAY)
        rc, out, L = run_site(w, T(11, 2, 18, 0), site, T(11, 2, 18, 1), export_error=OSError("磁碟已滿"))
        assert rc == 1 and "匯出失敗" in out and w.runs[-1][1] == 1 and w.run_updates[-1] == ("abnormal", None, len(w.runs))
        assert at(L) == at(L0) and L["date"] == "2026-10-30"
        rc, _, L = run_site(w, T(11, 2, 19, 0), site, T(11, 2, 19, 1))        # 沒有新資料，但網站與現況不同：補匯出
        assert rc == 0 and w.runs[-1][1] == 0 and L["date"] == "2026-11-02" and at(L) == "2026-11-02T18:01:00+08:00"


def test_schedule_unknown_arg():
    # 只執行第一個 launchctl 之前的副本（確認裡面沒有 launchctl 指令），不可能安裝或移除
    sh = (ROOT / "scripts/mac/install_schedule.sh").read_text(encoding="utf-8")
    head = sh[:sh.index("launchctl bootout")]
    assert not [ln for ln in head.splitlines() if "launchctl" in ln and not ln.lstrip().startswith("#")]
    if shutil.which("bash"):
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "head.sh"
            script.write_text(head + "echo REACHED_INSTALL\n", encoding="utf-8")
            run = lambda *a: subprocess.run(["bash", str(script), *a], capture_output=True, text=True, timeout=30,
                                            env={**os.environ, "HOME": tmp})
            for bad in (["--preview"], ["-p"], ["--Print"], ["--print", "x"], ["--uninstall", "x"], ["uninstall"], [""], ["-h"]):
                r = run(*bad)
                assert r.returncode == 2 and "用法" in r.stderr and "REACHED_INSTALL" not in r.stdout, bad
            r = run("--print")
            assert r.returncode == 0 and "<plist" in r.stdout and "REACHED_INSTALL" not in r.stdout
            assert "REACHED_INSTALL" in run().stdout and "REACHED_INSTALL" in run("--uninstall").stdout
    # Windows 只做靜態檢查：參數檢查要在任何 schtasks 之前，未知參數走到 usage 後 exit /b 非 0
    bat = (ROOT / "scripts/windows/install_schedule.bat").read_text(encoding="utf-8")
    usage, start = bat.index("\n:usage"), bat.index("\n:start")
    assert bat.index('if not "%~2"=="" goto :usage') < usage < bat.index("exit /b 2") < start < bat.index("schtasks")
    assert bat.index('if "%~1"=="" goto :start') < usage and bat.index('if /i "%~1"=="/uninstall" goto :start') < usage


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"✅ {fn.__name__}")
    print("全部通過")
