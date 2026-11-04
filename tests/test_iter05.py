"""
第 05 輪純邏輯測試（不連網、不連資料庫、不跳通知、不安裝排程）：
E2-1 統一投信主動 ETF 持股（日期語意、解析、資料集 since／delay、--catch-up 與 history 流程）；
E2-4 持股頁與個股卡的匯出；A3＋A8 官方漲跌家數與自算寬度。假的官方網站與資料庫沿用 test_iter03 的 World。

  python3 tests/test_iter05.py      （也相容 pytest）
"""
import argparse
import contextlib
import copy
import io
import json
import shutil
import subprocess
import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_iter03 as t3  # noqa: E402
from twstock import __main__ as cli  # noqa: E402
from twstock import db, export, fetch, health, tradingcal  # noqa: E402
from twstock.collectors import daily, history, holdings  # noqa: E402
from twstock.fetch import SchemaError  # noqa: E402
from twstock.health import Row  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
D, T, World, env, run_world, CLOSED = t3.D, t3.T, t3.World, t3.env, t3.run_world, t3.CLOSED
HKEYS = [f"holdings.{c}" for c in health.HOLDINGS]

# ─── 實際回應的片段（2026-11-03 SA 經 fetch.request(isolated=True) 取得，只刪減列數、未改值）────
PCF_1103 = {   # 00981A，date=115/11/04 → 持股日 11/03（當天的格式是 ISO 字串）
    "pcf": [{"PCFCode": "NAV", "TranDate": "2026-11-03T00:00:00", "PostDate": "2026-11-04T00:00:00", "Amount": 254413288263.0},
            {"PCFCode": "OUT_UNIT", "TranDate": "2026-11-03T00:00:00", "PostDate": "2026-11-04T00:00:00", "Amount": 10231209000.0},
            {"PCFCode": "P_UNIT", "TranDate": "2026-11-03T00:00:00", "PostDate": "2026-11-04T00:00:00", "Amount": 24.87}],
    "fund": {"sFundCode": "49YTW"},
    "asset": [{"AssetCode": "GD", "AssetName": "期貨(名目本金)", "Details": [
        {"TranDate": "2026-11-03T00:00:00", "AssetCode": "GD", "DetailCode": "TX", "DetailName": "台指期貨", "Share": 679.0, "Amount": 5887337400.0,
         "NavRate": 2.31, "MoneyType": "NTD", "MTH": "2026/11", "EditTime": "2026-11-03T16:56:43"}]},
              {"AssetCode": "ST", "AssetName": "股票", "Details": [
        {"TranDate": "2026-11-03T00:00:00", "AssetCode": "ST", "DetailCode": "2330", "DetailName": "台積電", "Share": 14464000.0,
         "Amount": 33194880000.0, "NavRate": 13.05, "MoneyType": "NTD", "MTH": "", "EditTime": "2026-11-03T16:56:43"},
        {"TranDate": "2026-11-03T00:00:00", "AssetCode": "ST", "DetailCode": "1802", "DetailName": "台玻", "Share": 8479000.0,
         "Amount": 574028300.0, "NavRate": 0.23, "MoneyType": "NTD", "MTH": "", "EditTime": "2026-11-03T16:56:43"},
        {"TranDate": "2026-11-03T00:00:00", "AssetCode": "ST", "DetailCode": "3376", "DetailName": "新日興", "Share": 1045000.0,
         "Amount": 132715000.0, "NavRate": 0.05, "MoneyType": "NTD", "MTH": "", "EditTime": "2026-11-03T16:56:43"}]}]}
PCF_20251030 = {   # 00981A，date=114/10/31 → 持股日 2025-10-30（歷史日期是 /Date(毫秒)/）
    "pcf": [{"PCFCode": "NAV", "TranDate": "/Date(1761753600000)/", "PostDate": "/Date(1761840000000)/", "Amount": 23452246994.0},
            {"PCFCode": "P_UNIT", "TranDate": "/Date(1761753600000)/", "PostDate": "/Date(1761840000000)/", "Amount": 15.42}],
    "fund": {}, "asset": [{"AssetCode": "GD", "Details": []}, {"AssetCode": "ST", "Details": [
        {"TranDate": "/Date(1761753600000)/", "AssetCode": "ST", "DetailCode": "2330", "DetailName": "台積電", "Share": 1412000,
         "Amount": 2125060000.0, "NavRate": 9.06, "MoneyType": "NTD", "MTH": "", "EditTime": "/Date(1761810315000)/"}]}]}
PCF_988 = {   # 00988A（跨境），date=115/11/04 → 持股日 11/02；海外股票代號保留原文、原幣
    "pcf": [{"PCFCode": "NAV", "TranDate": "/Date(1793548800000)/", "PostDate": "/Date(1793721600000)/", "Amount": 41817844467.0}],
    "fund": {}, "asset": [{"AssetCode": "ST", "Details": [
        {"TranDate": "/Date(1793548800000)/", "AssetCode": "ST", "DetailCode": "BE US", "DetailName": "BLOOM ENERGY CORP- A", "Share": 450000,
         "Amount": 88312500.0, "NavRate": 6.89, "MoneyType": "USD", "MTH": "", "EditTime": "/Date(1793694630000)/"},
        {"TranDate": "/Date(1793548800000)/", "AssetCode": "ST", "DetailCode": "3037", "DetailName": "欣興", "Share": 2600000,
         "Amount": 2592200000.0, "NavRate": 6.2, "MoneyType": "NTD", "MTH": "", "EditTime": "/Date(1793694630000)/"}]}]}
PCF_EMPTY = {"pcf": [{"PCFCode": "NAV", "TranDate": "/Date(-62135596800000)/", "PostDate": "/Date(-62135596800000)/", "Amount": 0}],
             "fund": {}, "asset": [], "assetDetailSchema": []}       # 尚未公布（date=115/11/05）與週六（115/10/31）
MI_BREADTH = {"title": "漲跌證券數合計", "fields": ["類型", "整體市場", "股票"],           # MI_INDEX 2026-11-03
              "data": [["上漲(漲停)", "1,783(6)", "58(2)"], ["下跌(跌停)", "13,979(312)", "1,000(33)"], ["持平", "341", "22"],
                       ["未成交", "20,831", "6"], ["無比價", "3,674", "2"]]}
TPEX_HL = [{"title": "上櫃股票當日彙總資訊", "date": "115/11/03",                       # afterTrading/highlight 2026-11-03
            "fields": ["上櫃家數", "總資本額(佰萬元)", "總市值(佰萬元)", "本日總成交值(佰萬元)", "本日總成交股數(張數)", "收市指數", "指數漲跌",
                       "上漲家數", "漲停家數", "下跌家數", "跌停家數", "平盤家數", "未成交(含暫停交易)家數"],
            "data": [["897", "846,779", "9,661,260", "197,539", "1,044,717", "345.52", "-23.72", "59", "11", "782", "41", "32", "24"]]}]


def _pcf_hits(w, fund=None):
    return [f for p, f in w.requests if "GetPCF" in p and (fund is None or f["fundCode"] == fund)]


def _hold(form):
    """請求的生效日（民國）→ 持股日。"""
    y, m, dd = form["date"].split("/")
    post = date(int(y) + 1911, int(m), int(dd))
    delay = next(v[1] for v in health.HOLDINGS.values() if v[0] == form["fundCode"])
    return tradingcal.trading_days(post - timedelta(days=30), post - timedelta(days=1), CLOSED)[-1 - delay]


# ─── E2-1：日期語意與解析 ─────────────────────────────────
def test_e2_dates():
    assert holdings.ez_date("2026-11-03T00:00:00") == D(11, 3)
    assert holdings.ez_date("/Date(1761753600000)/") == date(2025, 10, 30)          # UTC 10/29 16:00 = 台灣 10/30
    assert holdings.ez_date("/Date(1793548800000)/") == D(11, 2)
    assert holdings.ez_time("/Date(1761810315000)/").isoformat() == "2025-10-30T15:45:15"
    # 生效日 = 持股日之後第 delay + 1 個交易日：週五 → 週一；跨境再多一天；跳過休市日
    assert holdings.post_date(D(10, 30), 0, CLOSED) == D(11, 2) and holdings.post_date(D(10, 30), 1, CLOSED) == D(11, 3)
    assert holdings.post_date(D(11, 3), 0, CLOSED) == D(11, 4) and holdings.post_date(D(11, 2), 1, CLOSED) == D(11, 4)
    assert holdings.post_date(D(12, 24), 0, CLOSED) == D(12, 28)                    # 12/25 休市（行憲紀念日）


def test_e2_parse_real():
    s, rows = holdings.parse_pcf(PCF_1103, D(11, 3))
    assert s["hold_date"] == "2026-11-03" and s["post_date"] == "2026-11-04" and s["nav"] == 254413288263.0
    assert s["units"] == 10231209000.0 and s["nav_unit"] == 24.87 and s["edited_at"] == "2026-11-03T16:56:43"
    assert s["n_stocks"] == 3 and s["stock_weight"] == 13.33 and s["futures_lots"] == 679 and s["futures_amount"] == 5887337400.0
    tx = [r for r in rows if r["asset_type"] == "GD"][0]
    assert tx == {"asset_type": "GD", "code": "TX", "month": "2026/11", "name": "台指期貨", "shares": 679, "amount": 5887337400.0,
                  "weight": 2.31, "currency": "NTD"}
    tsmc = [r for r in rows if r["code"] == "2330"][0]
    assert tsmc["shares"] == 14464000 and tsmc["amount"] == 33194880000.0 and tsmc["weight"] == 13.05 and tsmc["month"] == ""
    # #5 歷史日期 /Date(毫秒)/
    s, rows = holdings.parse_pcf(PCF_20251030, date(2025, 10, 30))
    assert s["hold_date"] == "2025-10-30" and s["post_date"] == "2025-10-31" and s["futures_lots"] == 0 and rows[0]["shares"] == 1412000
    assert s["units"] is None                                   # 片段沒有 OUT_UNIT：欄位可缺，不是欄位不符
    # 海外持股：代號原文、原幣
    _, rows = holdings.parse_pcf(PCF_988, D(11, 2))
    assert [(r["code"], r["currency"]) for r in rows] == [("BE US", "USD"), ("3037", "NTD")]


def test_e2_parse_not_published_and_schema():
    assert holdings.parse_pcf(PCF_EMPTY, D(11, 4)) is None
    assert holdings.parse_pcf(PCF_1103, D(11, 4)) is None       # 回應是前一持股日：不寫入
    assert holdings.parse_pcf(PCF_1103, D(11, 2)) is None
    for bad in ({"pcf": []}, {"asset": []}, [], {"pcf": [{"PCFCode": "X", "TranDate": "2026-11-03T00:00:00"}], "asset": [{"Details": []}]}):
        try:
            holdings.parse_pcf(bad, D(11, 3))
            raise AssertionError(bad)
        except SchemaError:
            pass
    broken = copy.deepcopy(PCF_1103)
    del broken["asset"][1]["Details"][0]["DetailCode"]
    try:
        holdings.parse_pcf(broken, D(11, 3))
        raise AssertionError("DetailCode")
    except daily.PARSE_ERRORS:
        pass
    mixed = copy.deepcopy(PCF_1103)
    mixed["asset"][1]["Details"][0]["TranDate"] = "2026-11-02T00:00:00"
    try:
        holdings.parse_pcf(mixed, D(11, 3))
        raise AssertionError("mixed")
    except SchemaError:
        pass


def test_e2_real_file():
    """PG 補抓時保存的完整原始回應（logs/ 不在版本控制；沒有就略過）。"""
    for name, d, n, want in (("20261103", D(11, 3), 51, 94.43), ("20251030", date(2025, 10, 30), 50, None)):
        f = ROOT / f"logs/iter05_raw_GetPCF_00981A_{name}.json"
        if not f.exists():
            print(f"  （略過：{f.name} 不存在）")
            continue
        s, rows = holdings.parse_pcf(json.loads(f.read_text(encoding="utf-8")), d)
        assert s["n_stocks"] == n and (want is None or s["stock_weight"] == want)


# ─── E2-1：資料集（since、delay）──────────────────────────
def test_e2_specs():
    keys = [s.key for s in health.SPECS]
    assert keys[-6:] == ["breadth.TWSE", "breadth.TPEx", *HKEYS]
    assert daily.DAY_KEYS[-6:] == ("breadth.TWSE", "breadth.TPEx", *HKEYS)
    assert set(daily.DAY_KEYS) | {"index.TPEX", "futures", "futures_oi"} == set(keys)
    assert daily.DATASET_KEYS["holdings"] == tuple(HKEYS) and "holdings" not in daily.ALL_DATASETS     # 只有 --only holdings 才補
    assert health.SPEC["holdings.00411A"].since == D(8, 26) and health.SPEC["holdings.00411A"].delay == 1
    assert health.SPEC["holdings.00981A"].since is None and health.SPEC["holdings.00981A"].delay == 0
    assert fetch.MIN_INTERVAL["www.ezmoney.com.tw"] == 3.0
    assert set(history.SECONDS_PER_KEY) >= set(HKEYS)
    src = (ROOT / "twstock/db.py").read_text(encoding="utf-8")
    assert all(f"IF OBJECT_ID('{t}') IS NULL" in src for t in ("etf_holdings", "etf_holding_summary", "market_breadth"))


def test_e2_due_and_status():
    days = tradingcal.trading_days(D(10, 1), D(11, 4), CLOSED)
    snap = t3._full_snapshot(days, skip={("holdings.00411A", D(11, 3)), ("holdings.00981A", D(11, 4)), ("holdings.00411A", D(11, 4))})
    pick = lambda items, k, d: [i.status for i in items if i.key == k and i.date == d]
    items = health.evaluate(days, snap, T(11, 4, 18))
    assert pick(items, "holdings.00981A", D(11, 4)) == [health.PENDING]
    assert pick(items, "holdings.00411A", D(11, 3)) == [health.PENDING]          # 11/04 才公布 11/03 的持股
    assert pick(items, "holdings.00411A", D(11, 4)) == []                        # 11/05 才公布，還不該有
    items = health.evaluate(days, snap, T(11, 4, 22, 0))
    assert pick(items, "holdings.00411A", D(11, 3)) == [health.ABNORMAL] and pick(items, "holdings.00981A", D(11, 4)) == [health.ABNORMAL]
    # since：上市日之前不算缺；漲跌家數 11/03 起
    days = tradingcal.trading_days(D(8, 20), D(9, 1), CLOSED)
    items = health.evaluate(days, {k: {} for k in health.SPEC}, T(9, 1, 23))
    assert min(i.date for i in items if i.key == "holdings.00411A") == D(8, 26)
    assert not [i for i in items if i.key.startswith("breadth.")]
    # missing_keys：給 days 才看 delay（catch-up）；history 不給
    med = health.medians(snap)
    d4 = tradingcal.trading_days(D(10, 1), D(11, 4), CLOSED)
    assert health.missing_keys(D(11, 4), ("holdings.00411A",), t3._full_snapshot([]), med, d4) == ()
    assert health.missing_keys(D(11, 4), ("holdings.00411A",), t3._full_snapshot([]), med) == ("holdings.00411A",)
    assert health.missing_keys(D(8, 25), ("holdings.00411A",), {"holdings.00411A": {}}, {"holdings.00411A": 0}) == ()
    # 網站 status：跨境看前一交易日
    snap = t3._full_snapshot(d4, skip={("holdings.00411A", D(11, 4))})
    st = {x["k"]: x for x in health.dataset_status(snap, D(11, 4), T(11, 4, 18), CLOSED)}
    assert st["holdings.00411A"] == {"k": "holdings.00411A", "n": "00411A持股", "d": "2026-11-03", "s": "ok"}
    snap = t3._full_snapshot(d4, skip={("holdings.00411A", D(11, 3)), ("holdings.00411A", D(11, 4))})
    st = {x["k"]: x for x in health.dataset_status(snap, D(11, 4), T(11, 4, 22, 30), CLOSED)}
    assert st["holdings.00411A"]["s"] == health.ABNORMAL and st["holdings.00411A"]["m"] == "00411A持股停在 11/02"


def test_e2_all_missing_day():
    # 整天沒有收集：當天公布的資料集全部 0 筆即算，跨境持股（隔天才收）不影響判斷
    days = tradingcal.trading_days(D(10, 1), D(11, 3), CLOSED)
    core = [s.key for s in health.SPECS if not s.delay]
    snap = t3._full_snapshot(days, skip={(k, D(11, 2)) for k in core})
    items = health.evaluate(days, snap, T(11, 3, 23))
    assert health.all_missing_days(items) == [D(11, 2)]
    lines = health.problem_lines(items)
    assert lines[0].startswith("❌ 2026-11-02 全部資料集都沒有") and len(lines) == 1


# ─── E2-1：--catch-up 與 history 真實流程（假的 HTTP 與資料庫）──
def _world_1104():
    w = World(D(11, 3))
    for k in ("holdings.00411A", "holdings.00988A"):
        del w.rows[k][D(11, 3)]                 # 跨境：11/03 的持股要 11/04 才公布
    w.published["GetPCF"].add(D(11, 3))
    return w


def test_e2_m1_published():
    w = _world_1104()
    w.publish(D(11, 4))
    rc, out = run_world(w, T(11, 4, 17, 30))
    hits = _pcf_hits(w)
    assert rc == 0 and "Traceback" not in out and len(hits) == 4
    assert {(f["fundCode"], f["date"], f["specificDate"]) for f in hits} == {
        ("49YTW", "115/11/05", True), ("63YTW", "115/11/05", True), ("64YTW", "115/11/05", True), ("61YTW", "115/11/05", True)}
    assert all(w.rows[f"holdings.{c}"][D(11, 4)].n == 50 for c in ("00981A", "00403A"))
    assert all(w.rows[f"holdings.{c}"][D(11, 3)].n == 50 for c in ("00411A", "00988A")) and D(11, 4) not in w.rows["holdings.00411A"]
    rc, out = run_world(w, T(11, 4, 19, 30))
    assert rc == 0 and len(_pcf_hits(w)) == 4                   # 重跑：持股不再請求


def _stale(w):
    """未公布時回應前一持股日的清單（實際行為之一）：把生效日往前推一個交易日再回應。"""
    orig = w._pcf

    def pcf(form):
        if _hold(form) in w.published["GetPCF"]:
            return orig(form)
        y, m, dd = form["date"].split("/")
        prev = tradingcal.trading_days(date(int(y) + 1911, int(m), int(dd)) - timedelta(days=30), date(int(y) + 1911, int(m), int(dd)) - timedelta(days=1), CLOSED)[-1]
        return orig({**form, "date": f"{prev.year - 1911}/{prev:%m/%d}"})
    w._pcf = pcf


def test_e2_m2_m3_not_published():
    w = World(D(11, 3))
    w.publish(D(11, 4), "GetPCF")
    _stale(w)
    rc, out = run_world(w, T(11, 4, 17, 30))
    assert rc == 0 and "⏳ 00981A持股：2026-11-04 尚未公布" in out and "Traceback" not in out
    assert D(11, 4) not in w.rows["holdings.00981A"] and w.notices == []
    rc, out = run_world(w, T(11, 4, 22, 30))
    assert rc == 1 and "❌ 00981A持股：缺 2026-11-04" in out and "Traceback" not in out
    assert len(w.notices) == 1 and "holdings.00981A:2026-11-04" in w.notices[0]


def test_e2_m4_schema_only_that_etf():
    w = _world_1104()
    w.publish(D(11, 4))
    orig = w._pcf
    w._pcf = lambda form: t3.Resp({"pcf": [], "fund": {}}) if form["fundCode"] == "63YTW" else orig(form)
    rc, out = run_world(w, T(11, 4, 17, 30))
    assert rc == 1 and "Traceback" not in out and "holdings.00403A 失敗：GetPCF 回應缺少 pcf 或 asset" in out
    assert D(11, 4) not in w.rows["holdings.00403A"] and w.rows["holdings.00981A"][D(11, 4)].n == 50
    assert w.rows["prices.TWSE"][D(11, 4)].n == 1100 and w.rows["breadth.TWSE"][D(11, 4)].n == 1
    # DetailCode 不見：KeyError 也只影響該檔
    w = _world_1104()
    w.publish(D(11, 4))
    orig = w._pcf

    def no_code(form):
        r = orig(form)
        if form["fundCode"] == "49YTW":
            for x in r.data["asset"][0]["Details"]:
                del x["DetailCode"]
        return r
    w._pcf = no_code
    rc, out = run_world(w, T(11, 4, 17, 30))
    assert rc == 1 and "Traceback" not in out and "holdings.00981A 失敗" in out and w.rows["holdings.00403A"][D(11, 4)].n == 50


def _history(w, start, end, only=("holdings",)):
    buf = io.StringIO()
    with env(w), contextlib.redirect_stdout(buf):
        ok = history.run_history(start, end, datasets=only)
    return ok, buf.getvalue()


def test_e2_m6_before_listing():
    w = World(D(8, 21))
    w.published["GetPCF"].update(tradingcal.trading_days(D(8, 24), D(8, 31), CLOSED))
    ok, out = _history(w, D(8, 24), D(8, 28))
    assert ok and "Traceback" not in out
    assert [_hold(f) for f in _pcf_hits(w, "64YTW")] == [D(8, 26), D(8, 27), D(8, 28)]     # 00411A 8/26 上市，之前不請求
    assert len(_pcf_hits(w, "49YTW")) == 5 and all(D(8, 26) in w.rows[k] for k in HKEYS)
    ok, out = _history(w, D(8, 24), D(8, 28))
    assert ok and len(_pcf_hits(w)) == 18 and "待抓 0 天" in out             # 重跑：待抓 0 天、0 請求


def test_e2_m7_holiday():
    w = World(D(12, 24))
    rc, out = run_world(w, T(12, 25, 17, 30))
    assert rc == 0 and _pcf_hits(w) == [] and not t3._hit(w, "highlight") and "今天 2026-12-25 休市" in out


def test_e2_m8_history_schema():
    w = World(D(10, 30))
    w.published["GetPCF"].update({D(11, 2), D(11, 3)})
    w._pcf = lambda form: t3.Resp({"pcf": [], "fund": {}})
    args = argparse.Namespace(only=["holdings"], start=D(11, 2), end=D(11, 3), force=False, no_revenue=True, delay=0.0)
    buf = io.StringIO()
    with env(w), contextlib.redirect_stdout(buf):
        rc = cli.cmd_history(args)
    out = buf.getvalue()
    assert rc == 1 and "官方欄位不符（GetPCF 回應缺少 pcf 或 asset）" in out and "Traceback" not in out
    assert len(_pcf_hits(w)) == 4                                           # 第一天（4 檔）就停，不浪費第二天的請求


def test_e2_cli():
    src = (ROOT / "twstock/__main__.py").read_text(encoding="utf-8")
    assert '"margin", "holdings"]' in src and "--only holdings" in src


# ─── A3：官方漲跌家數 ─────────────────────────────────────
def test_a3_parse():
    tw = daily.parse_twse_breadth({"stat": "OK", "tables": [MI_BREADTH]}, D(11, 3))
    assert tw == {"trade_date": "2026-11-03", "market": "TWSE", "up": 58, "up_limit": 2, "down": 1000, "down_limit": 33, "flat": 22, "no_trade": 6}
    assert daily.parse_twse_breadth({"stat": "很抱歉，沒有符合條件的資料!"}, D(11, 3)) is None
    for bad in ({"stat": "OK", "tables": []}, {"stat": "OK", "tables": [{**MI_BREADTH, "fields": ["類型", "整體市場", "改名"]}]}):
        try:
            daily.parse_twse_breadth(bad, D(11, 3))
            raise AssertionError(bad)
        except SchemaError:
            pass
    tp = daily.parse_tpex_breadth(TPEX_HL, D(11, 3))
    assert tp == {"trade_date": "2026-11-03", "market": "TPEx", "up": 59, "up_limit": 11, "down": 782, "down_limit": 41, "flat": 32, "no_trade": 24}
    assert daily.parse_tpex_breadth([], D(11, 3)) is None


def test_a3_flow():
    # 上市家數 0 請求（與行情共用 MI_INDEX）；上櫃 +1；上櫃失敗只有 breadth.TPEx 異常
    w = World(D(11, 3))
    w.publish(D(11, 4))
    w.down.add("highlight")
    rc, out = run_world(w, T(11, 4, 22, 30))
    assert rc == 1 and len(t3._hit(w, "MI_INDEX")) == 1 and "Traceback" not in out
    assert w.rows["breadth.TWSE"][D(11, 4)].n == 1 and D(11, 4) not in w.rows["breadth.TPEx"]
    assert "❌ 上櫃漲跌家數" in out and "❌ 上市漲跌家數" not in out
    # 行情未公布：不打 highlight
    w = World(D(11, 3))
    rc, out = run_world(w, T(11, 4, 17, 30))
    assert rc == 0 and not t3._hit(w, "highlight")


# ─── E2-4：匯出 ───────────────────────────────────────────
HELD = {D(10, 26): {("ST", "2330"): ("台積電", 10000000, 10.0), ("ST", "3376"): ("新日興", 2000000, 0.1)},
        D(10, 27): {("ST", "2330"): ("台積電", 10000000, 10.0), ("ST", "3376"): ("新日興", 2000000, 0.1)},
        D(10, 28): {("ST", "2330"): ("台積電", 10000000, 10.0), ("ST", "3376"): ("新日興", 2000000, 0.1)},
        D(10, 29): {("ST", "2330"): ("台積電", 10000000, 10.0), ("ST", "3376"): ("新日興", 2000000, 0.1)},
        D(10, 30): {("ST", "2330"): ("台積電", 13251000, 11.84), ("ST", "3376"): ("新日興", 1740000, 0.09),
                    ("ST", "BE US"): ("BLOOM", 450000, 6.89), ("GD", "TX"): ("台指期貨", 679, 2.32)},
        D(11, 2): {("ST", "2330"): ("台積電", 13728000, 11.86), ("ST", "3376"): ("新日興", 1345000, 0.07),
                   ("ST", "BE US"): ("BLOOM", 450000, 6.0)},
        D(11, 3): {("ST", "2330"): ("台積電", 14464000, 13.05), ("ST", "1802"): ("台玻", 8479000, 0.23),
                   ("ST", "BE US"): ("BLOOM", 400000, 5.5), ("GD", "TX"): ("台指期貨", 679, 2.31)}}
DATES = sorted(HELD)
TW = {"2330", "3376", "1802"}


def test_e24_table():
    rows, out = export.holding_table(DATES, HELD, TW)
    by = {r["c"]: r for r in rows}
    assert [r["c"] for r in rows] == ["2330", "BE US", "1802"]                       # 依最新權重
    assert by["2330"] == {"c": "2330", "n": "台積電", "tw": 1, "s": [10000, 10000, 10000, 10000, 13251, 13728, 14464],
                          "w": [10.0, 10.0, 10.0, 10.0, 11.84, 11.86, 13.05], "l": 14464, "pw": 13.05, "d1": 736, "w1": 1.19, "d5": 4464}
    assert by["1802"]["new"] == 1 and by["1802"]["d1"] == 8479 and by["1802"]["w1"] == 0.23 and by["1802"]["d5"] == 8479
    assert by["BE US"]["tw"] == 0 and by["BE US"]["l"] == 400000 and by["BE US"]["d1"] == -50000      # 海外：股
    assert by["BE US"]["s"][:4] == [None] * 4 and by["BE US"]["d5"] == 400000
    assert out == [{"c": "3376", "n": "新日興", "tw": 1, "l": 1345, "pw": 0.07}]      # 出清；期貨不列入持股表
    rows, out = export.holding_table(DATES[-1:], HELD, TW)                         # 只有一天：沒有增減、沒有「新」
    assert all(r["d1"] is None and r["w1"] is None and "new" not in r for r in rows) and out == []


def test_e24_export_and_active():
    summary = {DATES[-1]: (Decimal("254413288263.00"), Decimal("24.8700"), 51, Decimal("94.43"), 679, Decimal("5887337400.00"))}
    H = export.holding_export("00981A", DATES, summary, HELD, TW, "主動統一台股增長", "TWSE")
    assert H["sum"] == {"d": "2026-11-03", "nav": 2544.13, "nu": 24.87, "n": 51, "sw": 94.43, "fl": 679, "fa": 58.87}
    assert H["fund"] == "49YTW" and H["delay"] == 0 and H["dates"][-1] == "2026-11-03" and len(H["rows"]) == 3
    act = export.stock_active({"00981A": (DATES, summary, HELD)}, TW)
    assert set(act) == {"2330", "1802"}                                            # 海外不進個股；出清的 3376 沒有卡片
    assert act["1802"] == [{"e": "00981A", "d": "2026-11-03", "l": 8479, "w": 0.23, "d1": 8479, "d5": 8479, "new": 1}]
    assert act["2330"][0]["d1"] == 736 and "new" not in act["2330"][0]


def test_a3_calc():
    days = tradingcal.trading_days(D(5, 1), D(11, 3), CLOSED)[-120:]
    up = {d: 10 + i * 0.1 for i, d in enumerate(days)}                              # 一路漲：站上均線、20 日新高
    down = {d: 100 - i * 0.1 for i, d in enumerate(days)}                           # 一路跌：20 日新低
    young = {d: 50.0 for d in days[-30:]}                                           # 只有 30 天：算 MA20 分母、不算 MA60
    tv = {d: 100.0 for d in days}
    tv[days[-1]] = 50.0
    B = export.breadth_calc({"TWSE": [up, down, young]}, days, {"TWSE": tv})["TWSE"]
    assert (B["d"], B["from"]) == ("2026-11-03", str(days[60])) and len(B["s20"]) == 60
    assert (B["n20"], B["n60"], B["ma20"], B["ma60"], B["hi"], B["lo"], B["vr"]) == (3, 2, 33.3, 50.0, 1, 1, 0.5)
    tv[days[-5]] = None
    assert export.breadth_calc({"TWSE": [up]}, days, {"TWSE": tv})["TWSE"]["vr"] is None      # 前 20 日有缺：不算


# ─── E2-4：網站（node 跑 app.js 真正的 holdTag；沒有 node 略過）────
def test_e24_hold_tag():
    if not shutil.which("node"):
        print("  （略過：沒有 node）")
        return
    js = (ROOT / "site/app.js").read_text(encoding="utf-8")
    line = js[js.index("const holdTag"):js.index("const HOLD_SORT")]
    script = ("const App = {latest: {holdings: {'00981A': {d: '2026-11-03'}}}};\n" + line +
              "\nconsole.log(JSON.stringify(['00981A', '00982A', '00406A', '0050'].map(holdTag)));")
    tags = json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True, timeout=30).stdout)
    assert tags == ['<a class="pill hold" href="#/etf/00981A">持股</a>', '<span class="pill muted">持股尚未支援</span>',
                    '<span class="pill muted">持股尚未支援</span>', '']


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"✅ {name}")
    print("全部通過")
