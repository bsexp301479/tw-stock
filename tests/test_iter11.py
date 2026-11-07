"""
第 11 輪純邏輯測試（不連網、不連資料庫）：
F11-1 借券賣出：TWT93U（上市）、margin/sbl（上櫃）解析（合計列、股票／ETF 分流、日期不符＝尚未公布、休市、欄位不符）、
      官方公式驗算、DDL、收集（行情保護、尚未公布、history --only sbl）、check 的兩行、股數寫入、匯出（張數換算、占股本、倍數、5 日、序列）；
F11-2 latest.json 的 sbl、screen.json 的 lb、l1、l5、lp、sd、排行與選股（原始碼檢查）；
F11-3 季報口徑說明、選股毛利率欄的季別小字（原始碼檢查）。
fixture：tests/fixtures/twt93u_2026110{6,7}_*.json、sbl_tpex_2026110{6,7}_*.json（官方原始回應的精簡版：欄位不變，只留幾列）。數值以 2026-11-06 為準。

  python3 tests/test_iter11.py      （也相容 pytest）
"""
import contextlib
import copy
import io
import json
import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_iter03 as t3  # noqa: E402
from twstock import db, export, health  # noqa: E402
from twstock.collectors import daily, history, industry  # noqa: E402
from twstock.fetch import SchemaError, is_etf_code, is_valid_stock_code  # noqa: E402

D, T = t3.D, t3.T
FIX = Path(__file__).resolve().parent / "fixtures"
ROOT = Path(__file__).resolve().parent.parent
load = lambda name: json.loads((FIX / name).read_text(encoding="utf-8"))
TW, OT = load("twt93u_20261106_mini.json"), load("sbl_tpex_20261106_mini.json")
N6, N7 = D(11, 6), D(11, 7)


# ─── F11-1：解析 ───────────────────────────────────────
def test_f111_parse_twse():
    rows = daily.parse_sbl(TW, N6, "TWSE")
    by = {r["stock_code"]: r for r in rows}
    assert "" not in by and len(rows) == 8                                         # 「合計」列略過
    assert by["2330"] == {"stock_code": "2330", "sbl_prev": 18412514, "sbl_sell": 1770000, "sbl_return": 0, "sbl_adjust": 0,
                          "sbl_balance": 20182514, "sbl_limit": 973912, "note": None}
    assert by["2408"]["sbl_prev"] == 96809884 and by["2408"]["sbl_return"] == 711000 and by["2408"]["sbl_balance"] == 96098884
    assert by["2303"]["sbl_balance"] == 128740952 and by["0050"]["sbl_balance"] == 261795000
    assert by["00400A"]["note"] is None and by["2330"]["sbl_limit"] == 973912
    stocks = sorted(c for c in by if is_valid_stock_code(c))
    etfs = sorted(c for c in by if is_etf_code(c))
    assert stocks == ["1538", "2303", "2330", "2408"] and etfs == ["00400A", "0050"]          # 2887I（特別股）、912000（TDR）都不寫
    assert daily.sbl_mismatch(rows) == []


def test_f111_parse_tpex():
    rows = daily.parse_sbl(OT, N6, "TPEx")
    by = {r["stock_code"]: r for r in rows}
    assert sorted(by) == ["00411A", "006201", "3064", "3066", "3071", "3073"]
    assert by["00411A"]["sbl_balance"] == 1566000 and by["006201"] == {
        "stock_code": "006201", "sbl_prev": 561000, "sbl_sell": 24000, "sbl_return": 0, "sbl_adjust": 0,
        "sbl_balance": 585000, "sbl_limit": 11173, "note": None}
    assert daily.sbl_mismatch(rows) == []


def test_f111_not_published_and_schema():
    assert daily.parse_sbl(TW, N7, "TWSE") == [] and daily.parse_sbl(OT, N7, "TPEx") == []          # 回應日期不是 d（前一個交易日的資料）
    assert daily.parse_sbl(load("twt93u_20261107_holiday.json"), N7, "TWSE") == []                  # 休市：日期相同、沒有資料列
    assert daily.parse_sbl(load("sbl_tpex_20261107_holiday.json"), N7, "TPEx") == []
    assert daily.parse_sbl({**TW, "stat": "很抱歉，沒有符合條件的資料!"}, N6, "TWSE") == []
    bad = copy.deepcopy(TW)
    bad["fields"][12] = "今日餘額"
    try:
        daily.parse_sbl(bad, N6, "TWSE")
        raise AssertionError("欄位不符要丟例外")
    except SchemaError as e:
        assert "12:當日餘額" in str(e)
    bad = copy.deepcopy(TW)
    bad["groups"][2]["title"] = "借券"
    try:
        daily.parse_sbl(bad, N6, "TWSE")
        raise AssertionError("groups 不符要丟例外")
    except SchemaError:
        pass
    bad = copy.deepcopy(OT)
    bad["tables"][0]["fields"][11] = "當日調整"
    try:
        daily.parse_sbl(bad, N6, "TPEx")
        raise AssertionError("上櫃欄位不符要丟例外")
    except SchemaError:
        pass
    rows = daily.parse_sbl(TW, N6, "TWSE")
    rows[0]["sbl_balance"] += 1
    assert daily.sbl_mismatch(rows) == [rows[0]["stock_code"]]


def test_f111_ddl_and_keys():
    src = (ROOT / "twstock" / "db.py").read_text(encoding="utf-8")
    for t in ("sbl_trades", "etf_sbl"):
        assert f"IF OBJECT_ID('{t}') IS NULL" in src and f"CONSTRAINT UQ_{t} UNIQUE" in src
    assert "IF COL_LENGTH('stocks', 'shares') IS NULL ALTER TABLE stocks ADD shares BIGINT NULL" in src
    assert "sbl_limit    BIGINT" in src                                                                   # 單檔餘額最大約 7.9 億股（3481），留餘裕
    assert daily.DATASET_KEYS["sbl"] == ("sbl.TWSE", "sbl.TPEx") and "sbl" not in daily.ALL_DATASETS       # 只有 --only sbl 才補
    k = list(daily.DAY_KEYS)
    assert k.index("margin.TPEx") < k.index("sbl.TWSE") < k.index("sbl.TPEx") < k.index("breadth.TWSE")
    assert health.SPEC["sbl.TWSE"].min_rows == 800 and health.SPEC["sbl.TPEx"].min_rows == 550
    assert set(history.SECONDS_PER_KEY) >= {"sbl.TWSE", "sbl.TPEx"}
    main = (ROOT / "twstock" / "__main__.py").read_text(encoding="utf-8")
    assert '"holdings", "sbl"]' in main and "--only sbl" in main and "sbl = 借券賣出" in main


# ─── F11-1：收集 ───────────────────────────────────────
def test_f111_collect():
    w = t3.World(D(10, 30))
    w.publish(D(11, 2))
    with t3.env(w), contextlib.redirect_stdout(io.StringIO()):
        written, errors = daily.collect_for_date(D(11, 2), ("prices.TWSE", "prices.TPEx", "etf.TWSE", "etf.TPEx", "sbl.TWSE", "sbl.TPEx"))
    assert errors == {} and written["sbl.TWSE"] == 1100 and written["sbl.TPEx"] == 900
    assert w.rows["sbl.TWSE"][D(11, 2)].n == 1100 and w.merges.count("sbl_trades") == 2 and w.merges.count("etf_sbl") == 2
    assert len(t3._hit(w, "TWT93U")) == 1 and len(t3._hit(w, "margin/sbl")) == 1
    # 行情 0 列（尚未公布）→ 不發借券請求；借券尚未公布（日期相同、沒有資料列）→ 0 筆、不是錯誤
    w2 = t3.World(D(10, 30))
    w2.publish(D(11, 2), "MI_INDEX", "TWT93U")
    with t3.env(w2), contextlib.redirect_stdout(io.StringIO()):
        written, errors = daily.collect_for_date(D(11, 2), ("prices.TWSE", "prices.TPEx", "sbl.TWSE", "sbl.TPEx"))
    assert written["prices.TWSE"] == 0 and "sbl.TWSE" not in written and t3._hit(w2, "TWT93U") == []
    w2.published["margin/sbl"].discard(D(11, 2))
    with t3.env(w2), contextlib.redirect_stdout(io.StringIO()):
        written, errors = daily.collect_for_date(D(11, 2), ("prices.TPEx", "sbl.TPEx"))
    assert errors == {} and written["sbl.TPEx"] == 0


def test_f111_before_2030():
    """20:30 前：官方仍回應前一個交易日（日期不符）→ 0 筆、不寫入、不算失敗；之後再抓。"""
    w = t3.World(D(10, 30))
    w.publish(D(11, 2))
    real = w.http

    def stale(method, url, **kw):
        r = real(method, url, **kw)
        if "TWT93U" in url and r.data:
            r.data = {**r.data, "date": "20261030"}
        return r
    with t3.env(w), mock.patch.object(t3.fetch._SESSION, "request", stale), \
            contextlib.redirect_stdout(io.StringIO()):
        written, errors = daily.collect_for_date(D(11, 2), ("prices.TWSE", "sbl.TWSE"))
    assert errors == {} and written["sbl.TWSE"] == 0 and D(11, 2) not in w.rows["sbl.TWSE"]


def test_f111_catchup_and_history():
    # catch-up：新的一天，22:00 前借券沒有 → 尚未公布（不是異常）；22:00 後仍沒有 → 異常
    w = t3.World(D(10, 30))
    w.publish(t3.FIRST_DAY, "TWT93U")
    rc, out = t3.run_world(w, T(11, 2, 21, 0))
    assert rc == 0 and "上市借券：2026-11-02 尚未公布" in out and t3.FIRST_DAY not in w.rows["sbl.TWSE"]
    assert w.rows["sbl.TPEx"][t3.FIRST_DAY].n == 900
    w.published["TWT93U"].add(t3.FIRST_DAY)
    w.requests.clear()
    rc, out = t3.run_world(w, T(11, 2, 22, 40))
    assert rc == 0 and [p for p in w.paths()] == ["/rwd/zh/marginTrading/TWT93U"] and w.rows["sbl.TWSE"][t3.FIRST_DAY].n == 1100
    # history --only sbl：只抓缺的日期、不抓行情
    w3 = t3.World(D(10, 30))
    for d in (D(10, 28), D(10, 29), D(10, 30)):
        w3.rows["sbl.TWSE"].pop(d)
        w3.rows["sbl.TPEx"].pop(d)
        w3.publish(d)
    with t3.env(w3), contextlib.redirect_stdout(io.StringIO()):
        assert history.run_history(D(10, 27), D(10, 30), datasets=("sbl",), revenue=False)
    assert len(t3._hit(w3, "TWT93U")) == 3 and len(t3._hit(w3, "margin/sbl")) == 3 and t3._hit(w3, "MI_INDEX", "dailyQuotes") == []
    w3.requests.clear()
    with t3.env(w3), contextlib.redirect_stdout(io.StringIO()):
        assert history.run_history(D(10, 27), D(10, 30), datasets=("sbl",), revenue=False)
    assert w3.requests == []                                                                       # 重跑 0 次請求


def test_f111_shares():
    L = [{"公司代號": "2330", "產業別": "24", "已發行普通股數或TDR原股發行股數": "25932370067"},
         {"公司代號": "2408", "產業別": "24", "已發行普通股數或TDR原股發行股數": "3450205894"},
         {"公司代號": "9999", "產業別": "24", "已發行普通股數或TDR原股發行股數": ""}]
    O = [{"SecuritiesCompanyCode": "6488", "SecuritiesIndustryCode": "24", "IssueShares": "186,000,000"}]
    seen = {}

    class Cur:
        rowcount = 3

        def execute(self, sql, *p):
            seen["sql"], seen["rows"] = sql, json.loads(p[0])

    class Conn:
        cursor = lambda self: Cur()
        commit = close = lambda self: None
    with mock.patch.object(industry, "request", side_effect=[L, O]), mock.patch.object(db, "connect", lambda: Conn()), \
            contextlib.redirect_stdout(io.StringIO()):
        industry.update_industry()
    by = {r["stock_code"]: r for r in seen["rows"]}
    assert by["2330"]["shares"] == 25932370067 and by["2408"]["shares"] == 3450205894 and by["6488"]["shares"] == 186000000
    assert by["9999"]["shares"] is None and "ISNULL(j.shares, st.shares)" in seen["sql"]           # 空值不蓋掉既有股數


# ─── F11-1、F11-2：匯出 ───────────────────────────────────
def test_f112_export_calc():
    assert [export.lots(x) for x in (20182514, 1770000, -711000, 499, 500, -500, -1500, None)] == \
        [20183, 1770, -711, 0, 1, -1, -2, None]
    d1, d5, d6 = D(10, 30), D(10, 31), N6
    rows = {d1: (17000000, 17500000, 0, None), d6: (18412514, 20182514, 973912, None)}
    r = export.stock_sbl(rows, d6, d1, 25932370067, 75)
    assert r == {"d": "2026-11-06", "lb": 20183, "l1": 1770, "l5": 2683, "lp": 0.08, "lx": 269.1}
    r = export.stock_sbl({d6: (96809884, 96098884, 1430681, "X")}, d6, None, None, 0)
    assert r == {"d": "2026-11-06", "lb": 96099, "l1": -711, "l5": None, "nt": "X"}             # 沒有股數 → 沒有 lp；融券 0 → 沒有 lx
    assert export.stock_sbl(rows, d5, None, 1, 1) is None                                       # 該市場最新借券日沒有這檔
    conv = [{"d": "2026-11-06", "k": 0.5, "t": "面"}]                                           # 面額變更：5 日前餘額 × 0.5
    assert export.stock_sbl(rows, d6, d1, None, None, conv)["l5"] == export.lots(20182514 - 17500000 * 0.5)
    m = export.market_sbl([d1, d6], {d6: [(18412514, 20182514), (96809884, 96098884)]})
    assert m == {"d": "2026-11-06", "lb": 116281, "l1": 1059, "n": 2}
    mg = export.margin_series([d1, d5, d6], {d1: (0, 10, 0, 0, 1, None)}, [], rows)
    assert mg == {"mb": [10, None, None], "sb": [1, None, None], "lb": [17500, None, 20183]}
    assert "lb" not in export.margin_series([d1], {d1: (0, 10, 0, 0, 1, None)}, [], {})
    assert export.margin_series([d1], {}, [], rows) is None                                     # 沒有融資融券：不畫圖
    assert set(export.SCREEN_KEYS) >= {"lb", "l1", "l5", "lp"}


def test_f112_export_source():
    src = (ROOT / "twstock" / "export.py").read_text(encoding="utf-8")
    assert '"sd": {m: str(d) for m, d in slast.items()}' in src and '**({"sbl": sbl} if sbl else {})' in src
    assert '"sbl": {m: market_sbl(sdates[m], srecent[m]) for m in ("TWSE", "TPEx") if sdates.get(m)} or None' in src


# ─── 網站（原始碼檢查）───────────────────────────────────
def test_f11_site():
    js = (ROOT / "site" / "stock.js").read_text(encoding="utf-8")
    assert "不等於看空" in js and "priceScaleId: 'lb'" in js and "for (const k of ['mb', 'sb', 'lb'])" in js
    assert "官方本益比以最新股數計算，期間有增資的公司" in js                                            # F11-3 第 1 點
    app = (ROOT / "site" / "app.js").read_text(encoding="utf-8")
    assert "['l+', '借券賣出增加', 'la*', -1, 'l'], ['lp', '借券占股本', 'lp', -1, 'l']" in app
    assert "{ id: 'lp', g: '信用'" in app and "{ id: 'l5', g: '信用'" in app and "function sblLine(L)" in app
    assert "gm: ['毛利率', x => x.gm, (v, x) => fmt(v, 1) + '%' + finTag(x)]" in app                  # F11-3 第 2 點
    assert "gmy: ['毛利率年增', x => x.gmy, (v, x) => sgn(v, 1) + '點' + finTag(x)]" in app


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"✅ {name}")
    print("全部通過")
