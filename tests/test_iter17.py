"""第 17 輪（不連網、不連資料庫）：F17-1 收集輸出「近 30 天」、上市注意失敗不拖累其他來源；
F17-2 注意累計預警（款別解析、規則 B、差一次、處置中不列）。"""
import sys
from contextlib import contextmanager, redirect_stdout
from datetime import date, timedelta
from io import StringIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from twstock import export  # noqa: E402
from twstock.collectors import alerts  # noqa: E402
from twstock.fetch import FetchError  # noqa: E402

APP = (ROOT / "site" / "app.js").read_text(encoding="utf-8")
CSS = (ROOT / "site" / "app.css").read_text(encoding="utf-8")


@contextmanager
def patched(**kw):
    """暫時換掉 alerts 模組的函式（不連網、不連資料庫）。"""
    old = {k: getattr(alerts, k) for k in kw}
    for k, v in kw.items():
        setattr(alerts, k, v)
    try:
        yield
    finally:
        for k, v in old.items():
            setattr(alerts, k, v)


TPEX_N = [{"SecuritiesCompanyCode": "8099", "Date": "1151106", "TradingInformation": "第一款"}]


def _openapi(m, url, **kw):
    return TPEX_N if "tpex_trading_warning" in url else []


def test_twse_notice_failure_isolated():
    def boom(end, days=30):
        raise FetchError("www.twse.com.tw 連續失敗")
    written, buf = [], StringIO()
    with patched(fetch_twse_notice=boom, request=_openapi, write_alerts=written.extend), redirect_stdout(buf):
        n = alerts.collect_alerts()
    assert n == 1 and [a["stock_code"] for a in written] == ["8099"]          # 上櫃照寫
    out = buf.getvalue()
    assert "上市注意股抓取失敗，本次略過" in out and "下次收集會補最近 30 天" in out


def test_openapi_failure_still_all_or_nothing():
    def bad(m, url, **kw):
        return {"oops": 1} if "punish" in url else []
    written = []
    with patched(fetch_twse_notice=lambda end, days=30: [], request=bad, write_alerts=written.extend):
        try:
            alerts.collect_alerts()
            raise AssertionError("應丟 FetchError")
        except FetchError:
            pass
    assert written == []


def test_summary_days_label():
    rows = [{"market": "TWSE", "alert_type": "notice"}, {"market": "TPEx", "alert_type": "notice"}]
    assert "注意 上市 1（近 30 天）／上櫃 1 筆" in alerts.alert_summary(rows, days_label=True)[0]
    assert "注意 上市 1／上櫃 1 筆" in alerts.alert_summary(rows)[0]                 # 預設不變（第 16 輪格式）
    buf = StringIO()
    with patched(fetch_alerts=lambda: rows, write_alerts=lambda r: None), redirect_stdout(buf):
        alerts.collect_alerts()
    assert "（近 30 天）" in buf.getvalue()


def test_clauses():
    assert export.clauses("最近六個營業日累積收盤價跌幅達45.70%。且價差達550.00元﹝第一款﹞。") == ({1}, True)
    assert export.clauses("漲幅達33.07%﹝第一款﹞。且成交量﹝第三款﹞。且週轉率﹝第四款﹞。") == ({1, 3, 4}, False)
    assert export.clauses("當沖比率﹝第十三款﹞。另跌幅達30%﹝第一款﹞") == ({1, 13}, True)
    assert export.clauses("(第十款)") == ({10}, False) and export.clauses("第十一款") == ({11}, False)
    assert export.clauses("本益比﹝第六款﹞") == ({6}, False)
    assert export.clauses("沒有款別") == (set(), False) and export.clauses(None) == (set(), False)


D = [date(2026, 10, 1) + timedelta(days=i) for i in range(40)]      # 假的交易日序列（只看順序）
C1, C1D, C6, C13 = ({1}, False), ({1}, True), ({6}, False), ({13}, False)


def test_watch_counts_and_rules():
    days = D[:30]
    n = {days[-1]: C1, days[-2]: C1, days[-3]: C1}
    assert export.watch_counts(n, days) == [3, 3, 3, 3]
    assert export.alert_watch({"2466": n}, days, set()) == [["2466", 1, "第一款連 3 日"]]
    n = {days[-1]: C1, days[-2]: C1, days[-4]: C1}                                   # 中間斷一天
    assert export.watch_counts(n, days)[:2] == [2, 2]
    assert export.alert_watch({"x": n}, days, set()) == [["x", 0, "第一款連 2 日"]]
    six = {days[-i]: C6 for i in (1, 2, 4, 6, 8, 10)}                                 # 10 日內 6 次（第六款）
    assert export.alert_watch({"6213": six}, days, set()) == [["6213", 1, "10 日內 6 次"]]
    five = {days[-i]: C6 for i in (1, 2, 3, 4, 5)}
    assert export.alert_watch({"y": five}, days, set())[0][1:] == [1, "第 1～8 款連 5 日"]
    twelve = {days[-i]: C6 for i in range(1, 30, 2)[:12]}                              # 30 日內 12 次、不連續
    assert export.alert_watch({"z": twelve}, days, set())[0][2] == "30 日內 12 次"
    only13 = {d: C13 for d in days}                                                     # 第十三款不計
    assert export.alert_watch({"w": only13}, days, set()) == []
    assert export.alert_watch({"8099": n}, days, {"8099"}) == []                        # 處置中不列
    short = {days[-1]: C6, days[-2]: C6}                                               # 歷史不足（例如上櫃 10/28 起）：沒紀錄的日子當成沒注意，只會少算
    assert export.watch_counts(short, days) == [0, 2, 2, 2] and export.alert_watch({"v": short}, days, set()) == []


def test_count_down_switch():
    days = D[:30]
    n = {days[-1]: C1D, days[-2]: C1D, days[-3]: C1D}
    assert export.alert_watch({"2360": n}, days, set())[0][1] == 1
    old, export.COUNT_DOWN = export.COUNT_DOWN, False
    try:
        assert export.alert_watch({"2360": n}, days, set()) == []                       # 跌幅不算第一款連續；1～8 款只連 3
        assert export.watch_counts(n, days) == [0, 3, 3, 3]
    finally:
        export.COUNT_DOWN = old


def test_watch_sort():
    days = D[:30]
    hit = {days[-1]: C1, days[-2]: C1, days[-3]: C1}
    near = {days[-1]: C1, days[-2]: C1}
    assert [x[0] for x in export.alert_watch({"9999": hit, "1111": near, "2222": hit}, days, set())] == ["2222", "9999", "1111"]


def test_site_source():
    assert "function watchGrp(W, S)" in APP and "${watchGrp(A.w, S)}" in APP
    assert "接近處置（推算）" in APP and "是否處置以官方公告為準" in APP and "差一次：" in APP
    assert ".al-near{" in CSS
    src = (ROOT / "twstock" / "export.py").read_text(encoding="utf-8")
    assert 'latest["alerts"]["w"] = alert_watch(watch_notes, watch_days,' in src and "COUNT_DOWN = True" in src
    assert APP.count("A.w") == 1 and "alerts.w" not in APP  # 只有今日清單用到；選股不加預警條件


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"✅ {name}")
    print("全部通過")
