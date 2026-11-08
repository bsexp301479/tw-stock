"""第 16 輪（不連網、不連資料庫）：F16-1 上市注意股（證交所網站查詢）、分市場輸出與 0 筆提醒；
F16-2 重疊處置合併區間；F16-3 今日頁處置／注意清單。"""
import sys
from contextlib import contextmanager
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from twstock import export  # noqa: E402
from twstock.collectors import alerts  # noqa: E402
from twstock.fetch import FetchError  # noqa: E402

APP = (ROOT / "site" / "app.js").read_text(encoding="utf-8")
CSS = (ROOT / "site" / "app.css").read_text(encoding="utf-8")


@contextmanager
def fake_request(fn):
    """暫時換掉 alerts.request（不連網）。"""
    old, alerts.request = alerts.request, fn
    try:
        yield
    finally:
        alerts.request = old


FIELDS = ["編號", "證券代號", "證券名稱", "累計次數", "注意交易資訊", "日期", "收盤價", "本益比"]
# 取自 2026-11-08 查詢 115/10/21～115/11/06 的真實回應（節錄）
SAMPLE = {"stat": "OK", "fields": FIELDS, "total": 3, "data": [
    [1, "040609", "川湖統一6A購01", "1", "最近六個營業日累積收盤價跌幅達36.06%﹝第一款﹞。", "115.11.04", "4.05", "-----"],
    [73, "6213", "聯茂", "8", "最近六個營業日累積收盤價跌幅達33.02%。且六個營業日起迄兩個營業日收盤價價差達194.00元﹝第一款﹞。"
     "11月04日之最近六個營業日之當日沖銷成交量占最近六個營業日總成交量比率66.17%<font color='#FF0000'>﹝第十三款﹞</font>。",
     "115.11.05", "551.00", "85.43"],
    [74, "2466", "冠西電", "6", "最近六個營業日累積收盤價漲幅達32.5%﹝第一款﹞。", "115.10.27", "60.10", "20.1"]]}


def test_roc_date_dot():
    assert alerts.roc_date("115.11.05") == date(2026, 11, 5)
    assert alerts.roc_date("1151105") == date(2026, 11, 5) and alerts.roc_date("115/11/05") == date(2026, 11, 5)
    assert alerts.roc_date("") is None


def test_parse_twse_notice():
    rows = alerts.parse_twse_notice(SAMPLE)
    assert [(a["stock_code"], a["announce_date"]) for a in rows] == [("6213", "2026-11-05"), ("2466", "2026-10-27")]  # 權證略過
    a = rows[0]
    assert a["alert_type"] == "notice" and a["start_date"] is None and a["measure"] is None
    assert "<font" not in a["reason"] and "﹝第十三款﹞" in a["reason"]
    assert alerts.parse_twse_notice({"stat": "OK", "fields": FIELDS, "data": []}) == []   # 假日：stat OK、data 空
    assert alerts.parse_twse_notice({"stat": "很抱歉，沒有符合條件的資料!"}) == []        # 當作 0 筆，由提醒處理
    for bad in ([], None, "<html>", {"stat": "OK", "data": "x"}):
        try:
            alerts.parse_twse_notice(bad)
            raise AssertionError(bad)
        except FetchError:
            pass


def test_fetch_twse_notice_range():
    seen = {}
    with fake_request(lambda m, url, **kw: seen.update(url=url, **kw["params"]) or SAMPLE):
        assert len(alerts.fetch_twse_notice(date(2026, 11, 9))) == 2
    assert seen["url"] == alerts.TWSE_NOTICE[0]
    assert (seen["startDate"], seen["endDate"], seen["response"]) == ("20261010", "20261109", "json")


def test_fetch_alerts_market_and_dedup():
    def fake(m, url, **kw):
        if "params" in kw:
            return SAMPLE
        if "tpex_trading_warning" in url:
            return [{"SecuritiesCompanyCode": "8099", "Date": "1151106", "TradingInformation": "第一款"}]
        if url.endswith("/notice"):     # OpenAPI 上市注意：佔位列
            return [{"Number": "0", "Code": "", "Name": "", "TradingInfoForAttention": "", "Date": ""}]
        return []
    with fake_request(fake):
        rows = alerts.fetch_alerts()
    assert sorted((a["market"], a["stock_code"]) for a in rows) == [("TPEx", "8099"), ("TWSE", "2466"), ("TWSE", "6213")]
    out = alerts.alert_summary(rows)
    assert out[0].strip() == "🚨 處置 上市 0／上櫃 0 筆、注意 上市 2／上櫃 1 筆（未在股票清單的代號不寫入）"
    assert len(out) == 1


def test_alert_summary_zero_warning():
    out = alerts.alert_summary([{"market": "TPEx", "alert_type": "notice"}])
    assert "注意 上市 0／上櫃 1" in out[0] and len(out) == 2 and "上市注意股最近 30 天 0 筆" in out[1]
    out = alerts.alert_summary([])
    assert len(out) == 3 and "上櫃注意股 0 筆" in out[2]


def _d(a, s, e, m="約每2分鐘撮合一次", r="連續3個營業日"):
    return {"t": "disposal", "a": a, "s": s, "e": e, "m": m, "r": r}


def test_disposal_span():
    two = [_d("2026-10-30", "2026-11-02", "2026-11-06"), _d("2026-11-04", "2026-11-05", "2026-11-11")]
    assert export.disposal_span(two) == ["2026-11-02", "2026-11-11"]                       # 8099：重疊
    assert export.disposal_span([_d("2026-11-04", "2026-11-05", "2026-11-11")]) == ["2026-11-05", "2026-11-11"]
    up = [_d("2026-11-05", "2026-11-09", "2026-11-13"), _d("2026-10-30", "2026-11-02", "2026-11-06")]
    assert export.disposal_span(up) == ["2026-11-02", "2026-11-13"]                        # 處置中＋即將：仍是處置中
    assert export.disposal_span([{"t": "notice", "a": "2026-11-06"}]) is None and export.disposal_span([]) is None


def test_alert_board():
    al = {"8099": [_d("2026-10-30", "2026-11-02", "2026-11-06"), _d("2026-11-04", "2026-11-05", "2026-11-11", r="連續3日，且30日內曾處置。其他")],
          "6213": [{"t": "notice", "a": "2026-11-06", "s": None, "e": None, "m": None, "r": "該有價證券之交易，" + "甲" * 70 + "。乙"}],
          "2466": [_d("2026-11-03", "2026-11-04", "2026-11-10", m=None)],
          "1569": [{"t": "notice", "a": "2026-11-06", "s": None, "e": None, "m": None, "r": "當沖比率"}]}
    b = export.alert_board(al)
    assert b["d"] == [["2466", "2026-11-04", "2026-11-10", None, "連續3個營業日"],
                      ["8099", "2026-11-02", "2026-11-11", "約每2分鐘撮合一次", "連續3日，且30日內曾處置"]]
    assert b["n"] == [["1569", "當沖比率"], ["6213", "甲" * 60 + "…"]]
    assert export.alert_board({}) == {"d": [], "n": []}


def test_site_source():
    assert "function alertBoard(L)" in APP and "${alertBoard(L)}" in APP
    assert "App.alertAll" in APP and "A.n.slice(0, nShow)" in APP and "nShow = App.alertAll ? A.n.length : 10" in APP
    assert "依證交所、櫃買中心公告" in APP and "'即將處置'" in APP and "'處置中'" in APP and "'今日注意'" in APP
    assert ".al-row" in CSS and ".al-why{white-space:nowrap" in CSS and "text-overflow:ellipsis" in CSS
    assert 'class="muted small al-r"' not in APP          # .al-r 是期貨「今天換月」藍底標籤，不可共用
    assert "A.n.length)}" in APP                           # 今日注意組顯示全部檔數，不是切片後的 10
    src = (ROOT / "twstock" / "export.py").read_text(encoding="utf-8")
    assert '"dsp": disposal_span(alerts[code])' in src and '"alerts": alert_board(alerts)' in src


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"✅ {name}")
    print("全部通過")
