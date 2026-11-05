"""
第 09 輪純邏輯測試（不連網、不連資料庫）：
F9-1 上櫃官方三大法人金額（insti/summary 解析、分市場寫入與讀取、資料集鍵、check、改鍵 DDL）＋ QA-05（main 攔截 pyodbc.Error）；
F9-2 月營收提前收集（revenue_month_for、make_plan、只有標題列的 CSV、check 的營收一行、一個月的請求量）；
F9-3 個股 margin.m5 換算（寶雅 5904）；
F9-4 估值一年位置（position、market_valuation、stock_valuation）。
數值以 2026-11-05 的官方回應與資料庫為範例（上櫃法人金額、10 月營收家數）。

  python3 tests/test_iter09.py      （也相容 pytest）
"""
import contextlib
import io
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest import mock

import pyodbc

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_iter03 as t3  # noqa: E402
from twstock import __main__ as cli  # noqa: E402
from twstock import db, export, health  # noqa: E402
from twstock.collectors import catchup, daily, history, revenue  # noqa: E402
from twstock.health import Row  # noqa: E402

D, T, CLOSED = t3.D, t3.T, t3.CLOSED

# 2026-11-05 上櫃 insti/summary 的原始回應（分析師 r9/insti_summary_20261105.json，notes 省略）
TPEX_1105 = {"stat": "ok", "date": "20261105", "tables": [{
    "title": "三大法人買賣金額彙總表", "date": "115/11/05", "fields": ["單位名稱", "買進金額(元)", "賣出金額(元)", "買賣超(元)"],
    "data": [["外資及陸資合計", "68,076,212,954", "69,660,322,744", "-1,584,109,790"],
             ["　外資及陸資(不含自營商)", "68,076,212,954", "69,660,322,744", "-1,584,109,790"],
             ["　外資自營商", "0", "0", "0"],
             ["投信", "4,007,623,069", "5,103,111,498", "-1,095,488,429"],
             ["自營商合計", "4,320,336,889", "5,490,900,232", "-1,170,563,343"],
             ["　自營商(自行買賣)", "1,702,055,844", "1,952,825,490", "-250,769,646"],
             ["　自營商(避險)", "2,618,281,045", "3,538,074,742", "-919,793,697"],
             ["三大法人合計*", "76,404,172,912", "80,254,334,474", "-3,850,161,562"]]}]}


# ─── F9-1：上櫃官方三大法人金額 ─────────────────────────
def test_f91_parse_tpex_amount():
    r = {x["unit"]: x for x in daily.parse_tpex_insti_amount(TPEX_1105, D(11, 5))}
    assert set(r) == {"foreign", "foreign_dealer", "trust", "dealer_self", "dealer_hedge", "total"}     # 兩個「合計」列不存
    assert all(x["market"] == "TPEx" and x["trade_date"] == "2026-11-05" for x in r.values())
    assert r["foreign"]["net_amount"] == -1584109790 and r["trust"]["net_amount"] == -1095488429
    assert r["dealer_self"]["net_amount"] == -250769646 and r["dealer_hedge"]["net_amount"] == -919793697
    assert r["total"]["net_amount"] == -3850161562 and r["total"]["buy_amount"] == 76404172912
    # 合計 = 外資（不含自營商）＋投信＋自營（自行＋避險）；外資自營商已含在自營商，不另加（和上市同口徑）
    assert sum(r[k]["net_amount"] for k in ("foreign", "trust", "dealer_self", "dealer_hedge")) == r["total"]["net_amount"]
    bad = lambda **kw: {**TPEX_1105, **kw}
    assert daily.parse_tpex_insti_amount(bad(stat="很抱歉，查無資料"), D(11, 5)) == []
    assert daily.parse_tpex_insti_amount(TPEX_1105, D(11, 4)) == []                      # 回應日期不是 d
    assert daily.parse_tpex_insti_amount(bad(tables=[]), D(11, 5)) == []                 # 休市：沒有表
    t = dict(TPEX_1105["tables"][0], fields=["單位名稱", "買進金額", "賣出金額", "買賣超"])
    assert daily.parse_tpex_insti_amount(bad(tables=[t]), D(11, 5)) == []                # 欄位改名
    t = dict(TPEX_1105["tables"][0], data=TPEX_1105["tables"][0]["data"][:-1])
    assert daily.parse_tpex_insti_amount(bad(tables=[t]), D(11, 5)) == []                # 6 個單位不齊


def test_f91_twse_rows_have_market():
    rows = daily.parse_insti_amount({
        "stat": "OK", "fields": ["單位名稱", "買進金額", "賣出金額", "買賣差額"],
        "data": [["外資及陸資(不含外資自營商)", "1", "2", "-1"], ["合計", "1", "2", "-1"]]}, D(10, 30))
    assert {x["market"] for x in rows} == {"TWSE"} and {x["unit"] for x in rows} == {"foreign", "total"}


def test_f91_merge_sql_has_market():
    class Cur:
        sql = None

        def execute(self, sql, *p):
            Cur.sql, Cur.params = sql, p
    daily.merge_insti_amount(Cur(), daily.parse_tpex_insti_amount(TPEX_1105, D(11, 5)))
    assert "t.market = s.market" in Cur.sql and "INSERT (trade_date, market, unit" in Cur.sql
    assert '"market": "TPEx"' in Cur.params[0]


def test_f91_amount_by_market():
    rows = [(D(11, 5), "TWSE", "foreign", -102460621838), (D(11, 5), "TWSE", "total", -123390000000),
            (D(11, 5), "TPEx", "foreign", -1584109790), (D(11, 5), "TPEx", "total", -3850161562)]
    a = export.amount_by_market(rows)
    o = export._insti_official(a["TWSE"])
    assert o["foreign"] == -1024.6 and o["date"] == "2026-11-05"                         # 同一天、同一單位：上市不被上櫃覆蓋
    p = export._insti_official(a["TPEx"])
    assert p["foreign"] == -15.8 and p["total"] == -38.5
    assert export._insti_official(export.amount_by_market([])["TPEx"]) is None           # 還沒補抓：上櫃為 null


def test_f91_keys_and_spec():
    assert daily.DAY_KEYS.index("amount.TPEx") == daily.DAY_KEYS.index("amount") + 1
    assert daily.DATASET_KEYS[daily.AMOUNT] == ("amount", "amount.TPEx")
    assert health.SPEC["amount.TPEx"].since == D(7, 31) and health.SPEC["amount.TPEx"].min_rows == 6
    assert health.SPEC["amount"].since is None and health.SPEC["amount"].label == "上市法人金額"     # 上市一列不變
    assert history.SECONDS_PER_KEY["amount.TPEx"] == 3.2


def test_f91_collect_waits_for_tpex_prices():
    w = t3.World(D(11, 4))
    w.publish(D(11, 5), "dailyQuotes", "insti/summary")                 # 上櫃行情、上櫃法人金額都還沒有
    with t3.env(w), contextlib.redirect_stdout(io.StringIO()):
        written, errors = daily.collect_for_date(D(11, 5), ("prices.TPEx", "amount", "amount.TPEx"))
    assert written["prices.TPEx"] == 0 and "amount.TPEx" not in written and not errors
    assert t3._hit(w, "insti/summary") == [] and len(t3._hit(w, "BFI82U")) == 1            # 上市照舊不等行情
    w.published["dailyQuotes"].add(D(11, 5))
    w.published["insti/summary"].add(D(11, 5))
    with t3.env(w), contextlib.redirect_stdout(io.StringIO()):
        written, errors = daily.collect_for_date(D(11, 5), ("prices.TPEx", "amount.TPEx"))
    assert written["amount.TPEx"] == 6 and w.rows["amount.TPEx"][D(11, 5)] == Row(6) and not errors
    assert w.rows["amount"][D(11, 5)] == Row(6)                                             # 上市列仍是 6，不是 12


def test_f91_history_only_amount_fills_tpex():
    w = t3.World(D(10, 30))
    for d in (D(10, 28), D(10, 29), D(10, 30)):
        w.rows["amount.TPEx"].pop(d)
        w.publish(d)
    with t3.env(w), contextlib.redirect_stdout(io.StringIO()):
        ok = history.run_history(D(10, 27), D(10, 30), datasets=("amount",), revenue=False)
    assert ok and len(t3._hit(w, "insti/summary")) == 3 and t3._hit(w, "BFI82U") == []     # 上市已齊：不重抓
    assert all(w.rows["amount.TPEx"][d] == Row(6) for d in (D(10, 28), D(10, 29), D(10, 30)))


def test_f91_check_rows():
    now = T(11, 5, 23)
    days = health.due_days(now, 20, CLOSED)
    snap = t3._full_snapshot(days, skip={("amount.TPEx", D(11, 4))})
    text, rc = health.check_report(days, snap, now, {"alerts_at": None, "revenue_on": None}, CLOSED)
    assert rc == 1 and "上櫃法人金額：缺 2026-11-04" in text
    line = next(ln for ln in text.splitlines() if ln.startswith("上市法人金額"))
    assert "      6      6" in line and "正常" in line                                       # 上市筆數、中位數仍為 6
    # 7/31 以前不判缺
    now = T(8, 5, 23)
    days = health.due_days(now, 10, CLOSED)
    snap = t3._full_snapshot(days, skip={("amount.TPEx", d) for d in days if d < D(7, 31)})
    items = [i for i in health.evaluate(days, snap, now) if i.key == "amount.TPEx"]
    assert {i.date for i in items} == {d for d in days if d >= D(7, 31)} and all(i.status == health.OK for i in items)


def test_f91_ddl_repeatable():
    ddl = "\n".join(db.DDL)
    i_add = ddl.index("IF COL_LENGTH('insti_amount', 'market') IS NULL")
    i_drop = ddl.index("ALTER TABLE insti_amount DROP CONSTRAINT UQ_insti_amount")
    i_new = ddl.index("ALTER TABLE insti_amount ADD CONSTRAINT UQ_insti_amount_market UNIQUE (trade_date, market, unit)")
    assert ddl.index("CREATE TABLE insti_amount") < i_add < i_drop < i_new                # 先加欄位、再刪舊鍵、最後建新鍵
    assert "IF EXISTS (SELECT 1 FROM sys.key_constraints WHERE name = 'UQ_insti_amount'" in ddl
    assert "IF NOT EXISTS (SELECT 1 FROM sys.key_constraints WHERE name = 'UQ_insti_amount_market'" in ddl
    assert "DEFAULT 'TWSE'" in ddl and "CONSTRAINT UQ_insti_amount UNIQUE (trade_date, unit)" not in ddl


def test_qa05_main_db_error():
    err = pyodbc.OperationalError("08001", "[08001] [Microsoft][ODBC Driver 18 for SQL Server]Login timeout expired (0) (SQLDriverConnect)")
    for argv, target in ((["export"], "twstock.export.export_all"),
                         (["history", "--start", "2026-10-30", "--end", "2026-10-30", "--only", "pe"], "twstock.db.acquire_lock")):
        buf = io.StringIO()
        with mock.patch(target, side_effect=err), contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            rc = cli.main(argv)
        assert rc == 2 and "連不上資料庫" in buf.getvalue() and "Traceback" not in buf.getvalue()


# ─── F9-2：月營收提前收集 ───────────────────────────────
def test_f92_revenue_month_for():
    for d in (D(11, 1), D(11, 5), D(11, 10), D(11, 30)):
        assert revenue.revenue_month_for(d) == (2026, 10)
    assert revenue.revenue_month_for(date(2027, 1, 3)) == (2026, 12)


STATE = {"alerts_at": datetime(2026, 11, 5, 19), "events_to": D(11, 5), "revenue_on": D(11, 4), "collected_at": None}


def _plan(now, counts, **st):
    days = health.due_days(now, 10, CLOSED)
    return catchup.make_plan(now, 10, t3._full_snapshot(days), dict(STATE, **st), CLOSED, counts)["revenue"]


def test_f92_make_plan():
    sep = {(2026, 8): 1983, (2026, 9): 1980}
    assert _plan(T(11, 5), sep) == [(2026, 10)]                                         # 10 月 0 家
    assert _plan(T(11, 5), {**sep, (2026, 10): 287}) == [(2026, 10)]                    # 287 < 1,940
    assert _plan(T(11, 5), {**sep, (2026, 10): 1945}) == []                             # ≥ 98%
    assert _plan(T(11, 5), {**sep, (2026, 10): 287}, revenue_on=D(11, 5)) == []         # 今天已收過
    assert _plan(T(11, 2), {**sep, (2026, 10): 0}) == [(2026, 10)]                      # 範圍含 10/30、11/02：9 月已齊，只排 10 月
    assert _plan(T(11, 2), {(2026, 8): 1983, (2026, 9): 1500}) == [(2026, 9), (2026, 10)]   # 上月沒齊：兩個月份分別判斷
    plan = catchup.plan_for_date(D(11, 2), T(11, 2), False)
    assert plan["revenue"] == [(2026, 10)]                                              # collect --date 月初也收上個月


def test_f92_header_only_csv():
    header = "出表日期,資料年月,公司代號,公司名稱,產業別,營業收入-當月營收,營業收入-上月營收,營業收入-去年當月營收," \
             "營業收入-上月比較增減(%),營業收入-去年同月增減(%),累計營業收入-當月累計營收,累計營業收入-去年累計營收,累計營業收入-前期比較增減(%),備註\r\n"
    resp = mock.Mock(content=("﻿" + header).encode("utf-8"))
    openapi = [{"資料年月": "11509", "公司代號": "2330"}]                                   # OpenAPI 仍是 9 月
    with mock.patch.object(revenue, "request", side_effect=[openapi, resp]):
        assert revenue.fetch_monthly_revenue("TWSE", 2026, 11) == {}
    # 0 家也算成功：revenue_on 記為當天，不是錯誤
    plan = {"by_date": [], "futures": None, "futures_oi": None, "tpex_months": [], "alerts": False, "events": None,
            "revenue": [(2026, 10)]}
    with mock.patch.object(catchup, "collect_monthly_revenue", lambda y, m: 0), contextlib.redirect_stdout(io.StringIO()):
        written, errors, undated = catchup.execute_plan(plan, T(11, 1, 17, 30))
    assert errors == {} and undated == {"revenue": "2026-11-01"}


def _rev(now, n10, revenue_on, n9=1980):
    return health.revenue_status(now.date(), {(2026, 9): n9, (2026, 10): n10}, revenue_on, CLOSED)


def test_f92_check_revenue():
    st, txt = _rev(T(11, 5), 287, D(11, 5))
    assert st == health.PENDING and txt == "月營收 2026/10：已收 287 家（前一月 1,980 家的 14%），⏳ 公布期間（每月 10 日前）"
    assert _rev(T(11, 2), 0, None)[0] == health.PENDING                                 # 月初 0 家、還沒收過
    assert _rev(T(11, 10), 1500, None)[0] == health.PENDING                             # 10 日當天仍是公布期間
    assert _rev(T(11, 12), 1945, D(11, 12))[0] == health.OK
    assert _rev(T(11, 13), 1500, D(11, 12))[0] == health.PENDING                        # 前一個交易日有收
    assert _rev(T(11, 16), 1500, D(11, 13))[0] == health.PENDING                        # 週一：前一個交易日是週五
    st, txt = _rev(T(11, 13), 1500, D(11, 9))
    assert st == health.ABNORMAL and "最後一次收集營收 2026-11-09" in txt
    assert health.revenue_status(date(2027, 1, 3), {(2026, 11): 1980, (2026, 12): 10}, None, CLOSED)[1].startswith("月營收 2026/12")
    # check_report：⏳ 不計入異常；❌ 計入並附建議指令
    now = T(11, 13, 23)
    days = health.due_days(now, 20, CLOSED)
    full = t3._full_snapshot(days)
    counts = {(2026, 9): 1980, (2026, 10): 1500}
    text, rc = health.check_report(days, full, now, {"alerts_at": None, "revenue_on": D(11, 12)}, CLOSED, revenue=counts)
    assert rc == 0 and "⏳ 晚交公司陸續補進" in text and "無異常" in text
    text, rc = health.check_report(days, full, now, {"alerts_at": None, "revenue_on": D(11, 9)}, CLOSED, revenue=counts)
    assert rc == 1 and "異常 1 項" in text and "collect --catch-up" in text
    text, rc = health.check_report(days, full, T(11, 5, 23), {"alerts_at": None, "revenue_on": None}, CLOSED,
                                   revenue={(2026, 9): 1980, (2026, 10): 287})
    assert rc == 0 and "公布期間" in text
    assert "月營收" not in health.check_report(days, full, now, {"alerts_at": None}, CLOSED)[0]   # 舊呼叫方式不印


def test_f92_month_requests():
    """一個完整月份（11/01～11/30，每天 18:00 跑一次 catch-up）：只在未達 98% 的日子排入營收，每天最多一次（2 市場 × 2 個請求）。"""
    published = lambda day: min(1980, 52 if day <= 4 else 287 if day == 5 else 287 + (day - 5) * 300)   # 前一晚收到的家數
    planned = []
    for day in range(1, 31):
        now = T(11, day)
        counts = {(2026, 8): 1983, (2026, 9): 1980, (2026, 10): published(day - 1) if day > 1 else 0}
        got = _plan(now, counts, revenue_on=now.date() - timedelta(days=1))
        assert got in ([], [(2026, 10)])
        if got:
            planned.append(day)
        assert _plan(now, counts, revenue_on=now.date()) == []                         # 同一天第二次不排
    # 11/01 是週日：評估範圍（交易日）都在 10 月，月份只有 9 月（已齊）→ 從 11/02（第一個交易日）開始；11/12 起已達 1,980
    assert planned == list(range(2, 12)) and len(planned) * 4 == 40


# ─── F9-3：個股 margin.m5 換算 ──────────────────────────
def test_f93_stock_margin_conv():
    # 寶雅 5904：8/10 面額 10 元改 1 元（上櫃反推「調」事件，參考價 72、前收 720）；官方 8/10 前日餘額 5,940 = 8/7 594 × 10
    ds = [D(8, 4), D(8, 5), D(8, 6), D(8, 7), D(8, 10), D(8, 11)]
    rows = {d: (594, 594, 0, 0, 0, None) for d in ds[:4]}
    rows[D(8, 10)] = (5940, 5935, 0, 0, 0, None)
    rows[D(8, 11)] = (5935, 5930, 0, 0, 0, None)
    ev = [{"d": "2026-08-10", "t": "調", "p": 720.0, "r": 72.0}]
    conv = export.margin_conv(rows, ev)
    assert conv == [{"d": "2026-08-10", "k": 10.0, "t": "調"}]
    m = export.stock_margin(rows, D(8, 11), D(8, 4), conv)
    assert m["m5"] == 5930 - 5940 == export.screen_margin(rows, D(8, 11), D(8, 4), conv, "TPEx")["m5"]
    assert export.stock_margin(rows, D(8, 11), D(8, 4))["m5"] == 5930 - 594          # 不傳 conv：舊行為（原始相減）
    assert export.stock_margin(rows, D(8, 11), D(8, 10), conv)["m5"] == 5930 - 5935    # 基期在換算之後：不乘係數


# ─── F9-4：估值一年位置 ─────────────────────────────────
def test_f94_position():
    assert export.position([1, 2, 3, 4], 1) == 25.0 and export.position([1, 2, 3, 4], 4) == 100.0
    assert export.position([5, 5, 5], 5) == 100.0                                       # 全部相同 → 100%
    assert export.position([], 5) is None and export.position([1, 2], None) is None


def test_f94_market_valuation():
    days = [D(11, 3), D(11, 4), D(11, 5)]
    rows = []
    for i, d in enumerate(days):
        rows += [(d, "TWSE", 10.0 + i, 1.0, 0.0), (d, "TWSE", 20.0 - i, 2.0, 2.0), (d, "TWSE", None, -1.0, 4.0),   # 虧損：pe null
                 (d, "TWSE", 0.0, 3.0, 6.0)]                                                                     # pe 0 不計入
    rows.append((D(11, 2), "TWSE", 99.0, 9.0, 9.0))                                       # 窗口外
    v = export.market_valuation(rows, days)["TWSE"]
    assert v["d"] == "2026-11-05" and v["from"] == "2026-11-03" and v["days"] == 3 and v["n"] == 2
    assert v["pe"] == {"v": 15.0, "p": 100.0, "lo": 15.0, "hi": 15.0}                     # 中位數每天都是 15
    assert v["pb"] == {"v": 2.0, "p": 100.0, "lo": 2.0, "hi": 2.0}                        # 淨值比 ≤ 0 不計入
    assert v["dy"] == {"v": 3.0, "p": 100.0, "lo": 3.0, "hi": 3.0}                        # 殖利率 0 計入
    assert v["s"] == [15.0, 15.0, 15.0] and v["sf"] == "2026-11-03"
    rows2 = [(d, "TPEx", p, 1.0, 1.0) for d, p in zip(days, (30.0, 20.0, 10.0))]
    t = export.market_valuation(rows2, days)["TPEx"]
    assert t["pe"]["p"] == 33.3 and t["pe"]["lo"] == 10.0 and t["pe"]["hi"] == 30.0      # 一年最低：1/3
    assert export.market_valuation([], days) == {}


def test_f94_stock_valuation():
    n = export.VAL_MIN
    s = {"pe": [10.0 + i for i in range(n)], "pb": [1.0] * n, "dy": [3.0] * (n - 1)}
    v = export.stock_valuation(s, {"pe": 10.0 + n - 1, "pb": 1.0, "dy": 3.0})
    assert v == {"pe": [100, 10.0, 10.0 + n - 1], "pb": [100, 1.0, 1.0]}                 # 殖利率有效天數不足 → 不輸出
    assert export.stock_valuation(s, {"pe": None, "pb": 1.0, "dy": 0.0}) == {"pb": [100, 1.0, 1.0]}   # 虧損、無股利
    assert export.stock_valuation(s, {"pe": 10.0}) == {"pe": [1, 10.0, 10.0 + n - 1]}   # 一年最低：1/120 → 1%
    assert export.stock_valuation({}, {"pe": 10.0}) is None


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"✅ {name}")
    print("全部通過")
