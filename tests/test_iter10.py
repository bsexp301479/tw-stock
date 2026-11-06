"""
第 10 輪純邏輯測試（不連網、不連資料庫）：
F10-1 季 EPS：mopsov ajax_t163sb04 解析（6 種業別、個體報表淨利、保險業 EPS 欄名、封鎖頁、欄位不符、0 家）、MERGE 與 DDL、
      單季相減（Q1、Q4、上一季缺、去年同季 ≤ 0、近 4 季）、收集窗口與排程、check 的季報一行、補抓季別；
F10-2 選股欄（eq、ey、e4、gm、gmy、fq、eh）、fqd、今日頁 fin_progress；
F10-3 上市法人金額的行情保護、淨值比卡日期與估值說明（原始碼檢查）。
fixture：tests/fixtures/t163sb04_*_mini.html（mopsov 原始回應的精簡版：表頭不變，每張表只留幾家）。數值以 2026-11-06 為準。

  python3 tests/test_iter10.py      （也相容 pytest）
"""
import contextlib
import io
import sys
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_iter03 as t3  # noqa: E402
from twstock import db, export, health  # noqa: E402
from twstock.collectors import catchup, daily, financials, history  # noqa: E402
from twstock.fetch import FetchError, SchemaError  # noqa: E402

D, T, CLOSED = t3.D, t3.T, t3.CLOSED
FIX = Path(__file__).resolve().parent / "fixtures"
ROOT = Path(__file__).resolve().parent.parent
html = lambda name: (FIX / f"t163sb04_{name}_mini.html").read_text(encoding="utf-8")
Q2, Q3 = financials.parse_financials(html("sii_115_02")), financials.parse_financials(html("sii_115_03"))


# ─── F10-1：解析 ───────────────────────────────────────
def test_f101_parse_industries():
    assert len(Q2) == 15
    tbl = {c: r["industry_tbl"] for c, r in Q2.items()}
    assert {t: sorted(c for c in tbl if tbl[c] == t) for t in set(tbl.values())} == {
        "basi": ["2801", "2820"], "bd": ["2855", "6005"], "ci": ["1215", "1342", "2303", "2330", "2408"],
        "fh": ["2881", "2882"], "ins": ["2816", "2832"], "mim": ["1409", "2207"]}
    assert Q2["2408"] == {"industry_tbl": "ci", "revenue": 131636005, "gross_profit": 98935333, "op_income": 90937560,
                          "net_income": 76251525, "eps": 23.38}
    assert Q2["2330"]["eps"] == 49.33 and Q2["1215"]["revenue"] == 14401643
    assert Q2["2881"]["eps"] == 6.67 and Q2["2881"]["gross_profit"] is None and Q2["2881"]["op_income"] is None
    assert Q2["2881"]["revenue"] == 172468262                                         # 金控：淨收益
    assert Q2["2801"]["revenue"] is None and Q2["2801"]["op_income"] is None          # 銀行：沒有合計欄
    assert Q2["6005"]["revenue"] == 19197814 and Q2["6005"]["op_income"] == 6593675   # 證券：收益、營業利益
    assert Q2["2816"]["eps"] is not None and Q2["2816"]["revenue"] is None            # 保險：EPS 欄名沒有「（元）」；IFRS 17 後沒有收入欄
    assert Q2["2820"]["net_income"] == 1436196 and Q2["1342"]["net_income"] == 318976   # 個體報表：本期淨利
    assert all(r["gross_profit"] is None for r in Q2.values() if r["industry_tbl"] != "ci")
    assert Q3["2408"]["eps"] == 49.28 and Q3["2303"]["eps"] == 6.0 and Q3["1215"]["revenue"] == 21866426


def test_f101_parse_old_and_otc():
    old = financials.parse_financials(html("sii_113_01"))
    assert old["2408"]["eps"] == -0.39 and old["2408"]["gross_profit"] == -276624
    assert old["2816"]["industry_tbl"] == "ins" and old["2816"]["revenue"] is not None   # 113 年保險業有營業收入、EPS 有「（元）」
    assert old["2881"]["industry_tbl"] == "fh" and old["2881"]["eps"] == 2.34
    otc = financials.parse_financials(html("otc_115_02"))
    assert {r["industry_tbl"] for r in otc.values()} == {"ci", "bd"} and otc["6488"]["eps"] == 11.87


def test_f101_parse_errors():
    page = html("sii_115_02")
    head = page[:page.index("<table class='hasBorder'")]
    assert financials.parse_financials(head + "</div></body></html>") == {}            # 認得的頁面、還沒有表：0 家
    only_head = financials.parse_financials(page.split("<tr class='even'>")[0] + "</table></body></html>")
    assert only_head == {}                                                             # 只有標題列：0 家
    for bad in (page.replace("基本每股盈餘", "每股盈餘"), page.replace("公司<br>代號", "代號"),
                page.replace("營業毛利（毛損）淨額", "毛利").replace("淨收益", "收益合計")):
        try:
            financials.parse_financials(bad)
            assert False, "欄位不符要丟 SchemaError"
        except SchemaError:
            pass
    for text, err in (("<html>THE REQUESTED URL WAS REJECTED. SECURITY</html>", FetchError), ("<html>其他</html>", SchemaError)):
        try:
            financials.parse_financials(text)
            assert False
        except err:
            pass


def test_f101_fetch_params():
    resp = mock.Mock(content=html("sii_115_03").encode("utf-8"))
    with mock.patch.object(financials, "request", return_value=resp) as req:
        got = financials.fetch_financials("TPEx", 2026, 3)
    assert got["2408"]["eps"] == 49.28
    args, kw = req.call_args
    assert args[:2] == ("POST", financials.URL) and kw["expect_json"] is False
    assert kw["data"]["TYPEK"] == "otc" and kw["data"]["year"] == "115" and kw["data"]["season"] == "03"


def test_f101_merge_and_ddl():
    sql = []

    class Cur:
        rowcount = 2

        def execute(self, s, *p):
            sql.append((s, p))
            return self
    n = financials.merge_financials(Cur(), 2026, 3, [{"stock_code": "2408", **Q3["2408"]}], date(2026, 11, 10))
    s, p = sql[0]
    assert n == 2 and "JOIN stocks st ON st.stock_code = j.stock_code" in s
    upd, ins = s.split("WHEN NOT MATCHED")
    assert "first_seen" not in upd and "updated_at = GETDATE()" in upd and "EXCEPT" in upd   # 更新時不動首次收錄日、值相同不更新
    assert "first_seen" in ins and p[1:] == (2026, 3, 2026, 3, date(2026, 11, 10))
    ddl = "\n".join(db.DDL)
    assert "IF OBJECT_ID('quarterly_financials') IS NULL" in ddl
    assert "CONSTRAINT UQ_quarterly_financials UNIQUE (stock_id, fin_year, fin_quarter)" in ddl
    assert "first_seen    DATE           NULL" in ddl


# ─── F10-1：單季相減 ───────────────────────────────────
def _cum(*rows):
    """(年, 季, EPS, 營收, 毛利) → cum；營益、淨利用 None。"""
    return {(y, q): (rev, gp, None, None, Decimal(str(e)) if e is not None else None) for y, q, e, rev, gp in rows}


def test_f101_single_rules():
    c = _cum((2025, 1, 1.0, 100, 30), (2025, 2, 2.5, 220, 70), (2025, 3, 4.0, 330, 100), (2025, 4, 6.0, 460, 140),
             (2026, 2, 3.0, 250, 80))
    assert export.fin_single(c, 2025, 1)[4] == Decimal("1.0")                          # Q1 = 累計
    assert export.fin_single(c, 2025, 4)[4] == Decimal("2.0") and export.fin_single(c, 2025, 4)[0] == 130   # Q4 = 全年 − Q3
    assert export.fin_single(c, 2026, 2) == [None] * 5                                  # 上一季（2026Q1）缺 → null，不以累計頂替
    assert export.fin_single(c, 2026, 1) is None
    c2 = dict(c)
    c2[(2025, 2)] = (220, None, None, None, Decimal("2.5"))
    assert export.fin_single(c2, 2025, 3)[1] is None and export.fin_single(c2, 2025, 3)[4] == Decimal("1.5")   # 該欄 NULL → 該欄 null
    assert export.fin_yoy(Decimal("1.5"), Decimal("-0.2")) is None and export.fin_yoy(Decimal("1.5"), 0) is None
    assert export.fin_yoy(Decimal("1.32"), Decimal("1.0")) == 32.0 and export.fin_yoy(None, Decimal(1)) is None
    assert export.fin_margin(5, 0) is None and export.fin_margin(None, 10) is None and export.fin_margin(1, 8) == 12.5
    assert export._r1(17575, 100000) == 17.6                                            # ROUND_HALF_UP（不是 17.5）


def test_f101_e4():
    c = _cum((2024, 3, 3.0, 1, 1), (2024, 4, 4.0, 1, 1), (2025, 3, 5.0, 1, 1), (2025, 4, 7.0, 1, 1), (2026, 3, 6.0, 1, 1))
    assert export.fin_e4(c, 2026, 3) == Decimal("8.0")          # 6 + 7 − 5
    assert export.fin_e4(c, 2025, 3) == Decimal("6.0")          # 5 + 4 − 3（一年前）
    assert export.fin_e4(c, 2025, 4) == Decimal("7.0")          # Q4 = 全年
    assert export.fin_e4(c, 2024, 3) is None                    # 四項缺一


def test_f101_numbers_1106():
    """PM 驗收 F10-1 #5（11/06 的值；QA 時以 SQL 重算為準）。"""
    rows = lambda code: (Q2[code], Q3[code])
    for code, eps, gm in (("2408", 25.90, 85.7), ("2303", 1.32, 34.0)):
        a, b = rows(code)
        c = {(2026, 2): tuple(a[k] for k in ("revenue", "gross_profit", "op_income", "net_income")) + (Decimal(str(a["eps"])),),
             (2026, 3): tuple(b[k] for k in ("revenue", "gross_profit", "op_income", "net_income")) + (Decimal(str(b["eps"])),)}
        s = export.fin_single(c, 2026, 3)
        assert float(s[4]) == eps and export.fin_margin(s[1], s[0]) == gm
    assert Q3["1215"]["revenue"] - Q2["1215"]["revenue"] == 7464783
    # 台光電、大立光（mopsov 115Q2 與 OpenAPI 115Q3 的值）
    for (r2, g2, e2), (r3, g3, e3), eps, gm in (((80342455, 25732144, "42.46"), (141226994, 48682931, "82.92"), 40.46, 37.7),
                                                 ((29208838, 14432503, "82.35"), (44859658, 21039356, "121.98"), 39.63, 42.2)):
        c = {(2026, 2): (r2, g2, None, None, Decimal(e2)), (2026, 3): (r3, g3, None, None, Decimal(e3))}
        s = export.fin_single(c, 2026, 3)
        assert float(s[4]) == eps and export.fin_margin(s[1], s[0]) == gm


def test_f101_fin_stock():
    c = _cum(*[(y, q, 1.0 * q, 100 * q, 30 * q) for y in (2024, 2025) for q in (1, 2, 3, 4)], (2026, 1, 2.0, 100, 50))
    f = export.fin_stock(c, "ci", None)
    assert [r[0] for r in f["q"]] == [202402, 202403, 202404, 202501, 202502, 202503, 202504, 202601]   # 近 8 季
    assert f["q"][-1] == [202601, 2.0, 100.0, 50.0, None, 100, 1.0] and "fs" not in f["c"]  # 補抓：沒有首次收錄日；最後一欄去年同季單季 EPS
    assert f["q"][3][6] == 1.0 and f["q"][0][6] is None                               # QA-01：202501 的去年同季 202401 不在 q 內也要帶；202302 沒有資料 → null
    assert f["c"] == {"e": 2.0, "ey": 100.0} and f["e4"] == 5.0 and f["e4p"] == 4.0 and f["t"] == "ci"
    assert export.fin_stock(c, "ci", date(2026, 5, 2))["c"]["fs"] == "2026-05-02"
    assert export.fin_stock({}, "ci", None) is None and export.fin_stock(None, None, None) is None
    gap = {k: v for k, v in c.items() if k != (2025, 3)}
    assert [r[0] for r in export.fin_stock(gap, "ci", None)["q"]] == [202402, 202403, 202404, 202501, 202502, 202504, 202601]
    assert export.fin_stock(gap, "ci", None)["q"][-2][1] is None                       # Q4 少了 Q3 累計 → 單季 null


# ─── F10-1：收集窗口、排程、check ──────────────────────
def test_f101_windows():
    q = health.fin_quarter_for
    assert q(D(10, 14)) is None and q(D(10, 15)) == (2026, 3) and q(D(12, 6)) == (2026, 3) and q(D(12, 7)) is None
    assert q(date(2027, 1, 15)) == (2026, 4) and q(date(2027, 4, 7)) == (2026, 4) and q(date(2027, 4, 8)) is None
    assert q(date(2027, 4, 15)) == (2027, 1) and q(date(2027, 9, 7)) == (2027, 2) and q(date(2027, 7, 14)) is None
    assert health.fin_latest_quarter(D(12, 10)) == (2026, 3, False) and health.fin_latest_quarter(D(11, 6)) == (2026, 3, True)
    assert health.fin_latest_quarter(D(10, 1)) == (2026, 2, False)
    gen, fin, gen_td, fin_td = health.fin_due(2026, 3, CLOSED)
    assert (gen, fin, gen_td, fin_td) == (D(11, 14), D(11, 29), D(11, 16), D(11, 30))   # 週六、週日 → 下一個交易日
    assert health.fin_due(2026, 4, CLOSED)[:2] == (date(2027, 3, 31), date(2027, 3, 31))


PREV = {(2026, 2): (1950, 38)}
FSTATE = {"alerts_at": datetime(2026, 11, 5, 19), "events_to": D(11, 5), "revenue_on": D(11, 5), "financials_on": None, "collected_at": None}


def _fplan(now, counts, **st):
    days = health.due_days(now, 10, CLOSED)
    return catchup.make_plan(now, 10, t3._full_snapshot(days), dict(FSTATE, **st), CLOSED, None, counts)["financials"]


def test_f101_make_plan():
    assert _fplan(T(10, 14), PREV) is None
    assert _fplan(T(10, 15), PREV) == (2026, 3) and _fplan(T(12, 6), PREV) == (2026, 3)
    assert _fplan(T(12, 7), PREV) is None and _fplan(datetime(2027, 1, 15, 18), PREV) == (2026, 4)
    assert _fplan(T(11, 10), {**PREV, (2026, 3): (900, 0)}, financials_on=D(11, 10)) is None    # 同一天只抓一次
    assert _fplan(T(11, 20), {**PREV, (2026, 3): (1921, 0)}) == (2026, 3)                      # 98.5%、金融業 0 家 → 仍排入
    assert _fplan(T(12, 1), {**PREV, (2026, 3): (1921, 38)}) is None                           # 金融業已齊 → 不排入
    assert _fplan(T(12, 1), {**PREV, (2026, 3): (1921, 30)}) is None                           # 已過金融業截止後第一個交易日（11/30）
    assert _fplan(T(11, 30), {**PREV, (2026, 3): (1921, 30)}) == (2026, 3)
    assert _fplan(T(11, 10), {(2026, 3): (900, 0)}) == (2026, 3)                               # 上一季沒有資料：不算齊
    assert catchup.make_plan(T(11, 10), 10, t3._full_snapshot(health.due_days(T(11, 10), 10, CLOSED)), FSTATE, CLOSED)["financials"] is None
    d = catchup.plan_for_date(D(11, 10), T(11, 10), False, PREV, CLOSED)
    assert d["financials"] == (2026, 3) and catchup.plan_for_date(D(12, 10), T(12, 10), False, PREV, CLOSED)["financials"] is None
    assert catchup.plan_for_date(D(11, 10), T(11, 10), True, PREV, CLOSED)["financials"] is None    # 休市日只處理沒有日期的資料


def test_f101_window_requests():
    """第 3 季窗口（10/15～12/06）每天 18:00 跑一次 catch-up：每天最多 2 個請求；收齊後 0 次。"""
    def published(day):                     # 前一晚收到的總家數、金融業家數
        n = 0 if day < D(10, 20) else min(1950, 60 + (day - D(10, 20)).days * 70)
        return n, (38 if day >= D(11, 28) else 31)
    planned, d = [], D(10, 10)
    while d <= D(12, 10):
        counts = {**PREV, (2026, 3): published(d - timedelta(days=1))}
        got = _fplan(T(d.month, d.day), counts, financials_on=d - timedelta(days=1))
        assert _fplan(T(d.month, d.day), counts, financials_on=d) is None
        if got:
            planned.append(d)
        d += timedelta(days=1)
    assert planned[0] == D(10, 15) and planned[-1] == D(11, 28) and len(planned) * 2 == 90   # 11/29 起已齊（金融業 38）


def test_f101_zero_rows_is_success():
    plan = {"by_date": [], "futures": None, "futures_oi": None, "tpex_months": [], "alerts": False, "events": None,
            "revenue": [], "financials": (2026, 3)}
    with mock.patch.object(catchup, "collect_financials", lambda y, q, seen: 0), contextlib.redirect_stdout(io.StringIO()):
        written, errors, undated = catchup.execute_plan(plan, T(10, 15))
    assert errors == {} and undated == {"financials": "2026-10-15"}
    with mock.patch.object(catchup, "collect_financials", side_effect=SchemaError("x")), contextlib.redirect_stdout(io.StringIO()):
        written, errors, undated = catchup.execute_plan(plan, T(10, 15))
    assert "financials" in errors and undated == {}


def test_f101_load_state():
    class Cur:
        def execute(self, *a):
            return self

        def fetchall(self):
            return [(datetime(2026, 11, 10, 22), 1, '{"undated": {"financials": "2026-11-10"}}', "catch-up"),
                    (datetime(2026, 11, 9, 22), 1, '{"undated": {"financials": "2026-11-09", "revenue": "2026-11-09"}}', "catch-up")]
    st = health.load_state(Cur())
    assert st["financials_on"] == D(11, 10) and st["revenue_on"] == D(11, 9)


def _fin(now, n, fin_on, nf=0):
    return health.financials_status(now.date(), {(2026, 2): (1950, 38), (2026, 3): (n, nf)}, fin_on, CLOSED)


def test_f101_check():
    st, txt = _fin(T(11, 6), 281, D(11, 6))
    assert st == health.PENDING and txt == ("第 3 季財報 2026Q3：已收 281 家（前一季 1,950 家的 14%），金融業 0／38 家，"
                                            "⏳ 公布期間（一般業 11/14、金融業 11/29 截止）")
    assert _fin(T(11, 16), 1800, D(11, 16))[0] == health.PENDING                        # 11/14 是週六
    assert _fin(T(11, 17), 1900, D(11, 16))[0] == health.PENDING and "晚交" in _fin(T(11, 17), 1900, D(11, 16))[1]
    st, txt = _fin(T(11, 17), 1900, D(11, 12))
    assert st == health.ABNORMAL and "最後一次收集季報 2026-11-12" in txt
    assert _fin(T(11, 20), 1921, D(11, 12), 30)[0] == health.PENDING                     # 只差金融業：11/30 前仍是公布期間
    assert _fin(T(12, 1), 1921, D(11, 30), 38)[0] == health.OK
    st, txt = _fin(T(12, 10), 1900, D(12, 6), 38)
    assert st == "info" and "收集期間已結束（12/06）" in txt
    assert health.financials_status(date(2027, 2, 1), {}, None, CLOSED)[1].startswith("年報 2026Q4：已收 0 家")
    now = T(11, 17, 23)
    days = health.due_days(now, 20, CLOSED)
    full = t3._full_snapshot(days)
    counts = {(2026, 2): (1950, 38), (2026, 3): (1900, 31)}
    text, rc = health.check_report(days, full, now, {"alerts_at": None, "financials_on": D(11, 16)}, CLOSED, financials=counts)
    assert rc == 0 and "⏳ 晚交公司陸續補進" in text and "無異常" in text
    text, rc = health.check_report(days, full, now, {"alerts_at": None, "financials_on": D(11, 12)}, CLOSED, financials=counts)
    assert rc == 1 and "異常 1 項" in text and "collect --catch-up" in text and "已過申報截止日仍未收齊" in text
    text, rc = health.check_report(days, full, T(12, 10, 23), {"alerts_at": None, "financials_on": D(12, 6)}, CLOSED, financials=counts)
    assert rc == 0 and "ℹ️" in text and "無異常" in text
    assert "季財報" not in health.check_report(days, full, now, {"alerts_at": None}, CLOSED)[0]   # 舊呼叫方式不印


def test_f101_history_quarters():
    q = history.fin_quarters(date(2024, 1, 1), D(11, 6), D(11, 6))
    assert q[0] == (2024, 1) and q[-1] == (2026, 3) and len(q) == 11                       # 113Q1～115Q3
    assert history.fin_quarters(date(2024, 1, 1), D(10, 14), D(10, 14))[-1] == (2026, 2)    # 115Q3 窗口還沒開始
    calls = []
    have = {(y, qq, m) for y, qq in q for m in ("TWSE", "TPEx")}
    with mock.patch.object(history, "load_fin_have", lambda: have), mock.patch.object(history, "tw_now", lambda: T(11, 6)), \
            mock.patch.object(history, "collect_financials", lambda *a: calls.append(a)), contextlib.redirect_stdout(io.StringIO()):
        assert history.run_history(date(2024, 1, 1), D(11, 6), datasets=("financials",)) and calls == []   # 重跑：全部跳過
        have.discard((2026, 3, "TPEx"))
        assert history.run_history(date(2024, 1, 1), D(11, 6), datasets=("financials",)) and calls == [(2026, 3, None, ("TPEx",))]
        calls.clear()
        with mock.patch.object(history, "load_fin_have", lambda: set()):
            history.run_history(date(2024, 1, 1), D(11, 6), datasets=("financials",))
        assert len(calls) == 22 and all(c[2] is None for c in calls)                     # 補抓：首次收錄日一律 NULL
    for err, word in ((FetchError("x"), "封鎖"), (SchemaError("y"), "欄位不符")):
        buf = io.StringIO()
        with mock.patch.object(history, "load_fin_have", set), mock.patch.object(history, "tw_now", lambda: T(11, 6)), \
                mock.patch.object(history, "collect_financials", side_effect=err), contextlib.redirect_stdout(buf):
            assert history.run_history(date(2024, 1, 1), D(11, 6), datasets=("financials",)) is False
        assert word in buf.getvalue()


# ─── F10-2：選股欄、今日頁 ─────────────────────────────
def test_f102_screen_fields():
    c = _cum((2025, 2, 2.0, 200, 60), (2025, 3, 3.0, 300, 90), (2026, 1, 1.0, 100, 40), (2026, 2, 2.2, 210, 84),
             (2026, 3, 4.0, 330, 132), (2025, 4, 4.5, 400, 120))
    s = export.fin_screen(c)
    assert s == {"eq": 1.8, "ey": 80.0, "e4": 5.5, "gm": 40.0, "gmy": 10.0, "fq": 202603, "eh": 4}   # eh：高於 26Q2、26Q1、25Q4、25Q3（25Q2 缺 Q1 → 停）
    assert export.fin_screen({}) == dict.fromkeys(("eq", "ey", "e4", "gm", "gmy", "fq", "eh"))
    fh = {k: (v[0], None, None, None, v[4]) for k, v in c.items()}
    assert export.fin_screen(fh)["gm"] is None and export.fin_screen(fh)["gmy"] is None          # 金融業沒有毛利率
    loss = dict(c)
    loss[(2025, 3)] = (300, 90, None, None, Decimal("1.5"))                               # 去年 Q3 單季 −0.5
    assert export.fin_screen(loss)["ey"] is None
    rows = {"1101": {**dict.fromkeys(export.SCREEN_KEYS), "rm": None, "fq": 202603},
            "1102": {**dict.fromkeys(export.SCREEN_KEYS), "rm": None, "fq": 202602},
            "1103": {**dict.fromkeys(export.SCREEN_KEYS), "rm": None, "fq": 202602}}
    assert export.screen_build(rows, {})["fqd"] == {"202603": 1, "202602": 2}


def test_f102_progress():
    counts = {(2026, 3, "TWSE"): 231, (2026, 3, "TPEx"): 50, (2026, 2, "TWSE"): 1088, (2026, 2, "TPEx"): 896}
    assert export.fin_progress(counts, D(11, 6)) == {"q": 202603, "n": {"TWSE": 231, "TPEx": 50}, "p": {"TWSE": 1088, "TPEx": 896}}
    assert export.fin_progress(counts, D(12, 10)) is None                                  # 窗口外
    assert export.fin_progress({(2026, 2, "TWSE"): 1088}, D(10, 16)) is None               # 當季 0 家


# ─── F10-3 ────────────────────────────────────────────
def test_f103_twse_amount_waits_for_prices():
    w = t3.World(D(11, 4))
    w.publish(D(11, 5), "MI_INDEX", "BFI82U")                                             # 上市行情、法人金額都還沒有
    with t3.env(w), contextlib.redirect_stdout(io.StringIO()):
        written, errors = daily.collect_for_date(D(11, 5), ("prices.TWSE", "amount", "amount.TPEx"))
    assert written["prices.TWSE"] == 0 and "amount" not in written and not errors
    assert t3._hit(w, "BFI82U") == [] and len(t3._hit(w, "insti/summary")) == 1          # 上櫃照舊（上櫃有自己的保護）
    w.published["MI_INDEX"].add(D(11, 5))
    w.published["BFI82U"].add(D(11, 5))
    with t3.env(w), contextlib.redirect_stdout(io.StringIO()):
        written, errors = daily.collect_for_date(D(11, 5), ("prices.TWSE", "amount"))
    assert written["amount"] == 6 and w.rows["amount"][D(11, 5)].n == 6
    w2 = t3.World(D(11, 4))
    w2.publish(D(11, 5))
    w2.renamed.add("MI_INDEX")                                                            # 行情欄位不符（例外）→ 照舊發請求
    with t3.env(w2), contextlib.redirect_stdout(io.StringIO()):
        written, errors = daily.collect_for_date(D(11, 5), ("prices.TWSE", "amount"))
    assert "prices.TWSE" in errors and written["amount"] == 6 and len(t3._hit(w2, "BFI82U")) == 1
    w3 = t3.World(D(10, 30))
    for d in (D(10, 28), D(10, 29), D(10, 30)):
        w3.rows["amount"].pop(d)
        w3.publish(d)
    with t3.env(w3), contextlib.redirect_stdout(io.StringIO()):
        assert history.run_history(D(10, 27), D(10, 30), datasets=("amount",), revenue=False)
    assert len(t3._hit(w3, "BFI82U")) == 3 and t3._hit(w3, "MI_INDEX") == []               # history --only amount 不抓行情、照舊寫入


def test_f103_site_text():
    js = (ROOT / "site" / "stock.js").read_text(encoding="utf-8")
    assert "請一併看淨值比" not in js and "獲利大增時本益比（淨值比也可能）會落到一年低點" in js and "不代表股價便宜" in js
    assert "subs(fundSub(fund.pb, false), valSub('pb', fund.pb))" in js


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"✅ {name}")
    print("全部通過")
