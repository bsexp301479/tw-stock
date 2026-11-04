"""
第 07 輪純邏輯測試（不連網、不連資料庫、不跳通知、不安裝排程）：
F7-1 群益投信主動 ETF 持股（解析、日期參數、分派、收集流程、history）；F7-2 主動 ETF 彙總排行（export.active_rank）。
假的官方網站與資料庫沿用 test_iter03 的 World（第 7 輪在 World 加了群益 buyback：和 GetPCF 共用已公布的持股日）。

  python3 tests/test_iter07.py      （也相容 pytest）
"""
import copy
import sys
from datetime import date
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_iter03 as t3  # noqa: E402
import test_iter05 as t5  # noqa: E402
from twstock import export, fetch, health  # noqa: E402
from twstock.collectors import holdings  # noqa: E402
from twstock.collectors.holdings import Gap  # noqa: E402
from twstock.fetch import SchemaError  # noqa: E402

D, T, World, run_world = t3.D, t3.T, t3.World, t3.run_world
CAP = ("00982A", "00992A", "00415A", "00997A")

# ─── 實際回應的片段（2026-11-04 分析師／SA 經 fetch.request(isolated=True) 取得，只刪減列數與 pcf 欄位、未改值）────
CAP_1104 = {"code": 200, "data": {"pcf": {"fundName": "群益台灣精選強棒主動式ETF基金", "date1": "2026-11-05", "date2": "2026-11-04", "nav": 43765013015.0, "totUnit": 2292436000.0, "pUnit": 19.09, "dollar": "TWD"}, "stocks": [{"date1": "2026/11/5 上午 12:00:00", "stocNo": "2330", "stocName": "台積電", "weight": 8.3087, "weightRound": 8.31, "share": 1609000.0, "shareFormat": "1,609,000", "stocEname": "TSMC", "replace": None, "smallStatus": None}, {"date1": "2026/11/5 上午 12:00:00", "stocNo": "3105", "stocName": "穩懋", "weight": 8.0807, "weightRound": 8.08, "share": 7059000.0, "shareFormat": "7,059,000", "stocEname": "Win", "replace": None, "smallStatus": None}], "bonds": [], "futures": [], "assets": [{"asDesc": "保證金", "asMoney": "TWD 33,240.00", "asEname": "Margin"}], "rps": [], "characteristics": []}, "message": None}   # 00982A 最新
CAP_997 = {"code": 200, "data": {"pcf": {"fundName": "群益美國增長主動式ETF基金", "date1": "2026-11-05", "date2": "2026-11-03", "nav": 10315579609.0, "totUnit": 1040877000.0, "pUnit": 9.91, "dollar": "TWD"}, "stocks": [{"date1": "2026/11/5 上午 12:00:00", "stocNo": "CRWD US", "stocName": "Crowdstrike控股公司", "weight": 4.9507, "weightRound": 4.95, "share": 63557.0, "shareFormat": "63,557", "stocEname": "CROWDSTRIKE HOLDINGS INC - A", "replace": None, "smallStatus": None}, {"date1": "2026/11/5 上午 12:00:00", "stocNo": "AAPL US", "stocName": "蘋果公司", "weight": 4.4136, "weightRound": 4.41, "share": 41772.0, "shareFormat": "41,772", "stocEname": "APPLE INC", "replace": None, "smallStatus": None}], "bonds": [], "futures": [], "assets": [{"asDesc": "應收付證券款", "asMoney": "KRW 5,083,081,867.00", "asEname": "Accounts Receivables\\Accounts Payables"}], "rps": [], "characteristics": []}, "message": None}   # 00997A 最新（跨境：生效日 11/05 → 持股日 11/03）
CAP_NONE = {"code": 400, "data": None, "message": "沒有查詢到該條件的數據"}   # 生效日 11/06（尚未公布）與 11/01（週日）都是這樣


# ─── F7-1：解析 ─────────────────────────────────────────
def test_f71_parse_published():
    s, rows = holdings.parse_capital(CAP_1104, D(11, 4), D(11, 5), D(11, 4))
    assert s == {"hold_date": "2026-11-04", "post_date": "2026-11-05", "nav": 43765013015.0, "units": 2292436000,
                 "nav_unit": 19.09, "n_stocks": 2, "stock_weight": 16.39, "futures_lots": 0, "futures_amount": 0, "edited_at": None}
    assert rows[0] == {"asset_type": "ST", "code": "2330", "month": "", "name": "台積電", "shares": 1609000, "amount": None,
                       "weight": 8.31, "currency": ""}                                  # D13 = A：沒有市值、不推算
    s, rows = holdings.parse_capital(CAP_997, D(11, 3), D(11, 5))                     # 跨境 delay 1
    assert s["hold_date"] == "2026-11-03" and rows[0]["code"] == "CRWD US" and rows[0]["shares"] == 63557


def test_f71_parse_unpublished_and_schema():
    assert holdings.parse_capital(CAP_NONE, D(11, 5), D(11, 6), D(11, 4)) is None
    for bad in ({"code": 400, "data": None, "message": "參數錯誤"}, {"code": 500, "data": None, "message": None},
                {"stat": "沒有資料"}, {"code": 200, "data": None, "message": None}, {"code": 200, "data": {"pcf": None, "stocks": []}},
                "<html>"):
        try:
            holdings.parse_capital(bad, D(11, 4), D(11, 5), D(11, 5))
            raise AssertionError(bad)
        except SchemaError:
            pass
    futures = copy.deepcopy(CAP_1104)
    futures["data"]["futures"] = [{"x": 1}]                                            # 期貨欄位尚未對應：不悄悄漏掉
    try:
        holdings.parse_capital(futures, D(11, 4), D(11, 5))
        raise AssertionError("futures")
    except SchemaError as e:
        assert "期貨" in str(e)


def test_f71_parse_gaps():
    # A：清單已公布（date1 = 要求的生效日），持股日卻不是 d
    assert holdings.parse_capital(CAP_997, D(11, 4), D(11, 5), D(11, 5)) == Gap("A", D(11, 3), D(11, 5), None)
    assert holdings.parse_capital(CAP_997, D(11, 4), D(11, 6), D(11, 6)) is None          # 生效日不同 → 不是這份清單
    # B：持股日是 d、只有彙總；今天 < 生效日時可能只是還沒寫完 → 仍是尚未公布
    only_sum = copy.deepcopy(CAP_1104)
    only_sum["data"]["stocks"] = []
    assert holdings.parse_capital(only_sum, D(11, 4), D(11, 5), D(11, 5)) == Gap("B", D(11, 4), D(11, 5), 43765013015.0)
    assert holdings.parse_capital(only_sum, D(11, 4), D(11, 5), D(11, 4)) is None
    only_sum["data"]["pcf"]["nav"] = 0
    assert holdings.parse_capital(only_sum, D(11, 4), D(11, 5), D(11, 5)) is None


def test_f71_date_and_dispatch():
    assert holdings.cap_date(D(6, 2)) == "2026-06-01T16:00:00.000Z" and holdings.cap_date(date(2026, 1, 1)) == "2025-12-31T16:00:00.000Z"
    with mock.patch.object(holdings, "request", return_value=CAP_1104) as req:
        s, _ = holdings.fetch_holdings("00982A", D(11, 4), t3.CLOSED)
    assert req.call_args == mock.call("POST", holdings.CAP_URL, json={"fundId": "399", "date": "2026-11-04T16:00:00.000Z"})
    assert s["n_stocks"] == 2
    with mock.patch.object(holdings, "request", return_value=CAP_997) as req:
        holdings.fetch_holdings("00997A", D(11, 3), t3.CLOSED)                        # 跨境：持股日 11/03 → 生效日 11/05
    assert req.call_args[1]["json"] == {"fundId": "502", "date": "2026-11-04T16:00:00.000Z"}
    with mock.patch.object(holdings, "request", return_value=t5.PCF_1103) as req:
        holdings.fetch_holdings("00981A", D(11, 3), t3.CLOSED)                        # 統一不變
    assert req.call_args == mock.call("POST", holdings.URL, json={"fundCode": "49YTW", "date": "115/11/04", "specificDate": True})


def test_f71_config():
    H = health.HOLDINGS
    assert list(H)[:4] == ["00981A", "00403A", "00411A", "00988A"] and all(H[c].trust == "統一" for c in list(H)[:4])
    assert {c: (H[c].fund, H[c].delay, H[c].since, H[c].trust) for c in CAP} == {
        "00982A": ("399", 0, None, "群益"), "00992A": ("500", 0, D(12, 30).replace(year=2025), "群益"),
        "00415A": ("504", 0, D(10, 20), "群益"), "00997A": ("502", 1, D(4, 14), "群益")}
    assert health.SPEC["holdings.00997A"].delay == 1 and health.SPEC["holdings.00415A"].since == D(10, 20)
    assert fetch.MIN_INTERVAL["www.capitalfund.com.tw"] == 3.0


# ─── F7-1：收集流程（假的 HTTP 與資料庫）─────────────────
def _cap_hits(w, fund=None):
    return [f for p, f in w.requests if "etf/buyback" in p and (fund is None or f["fundId"] == fund)]


def _world_1104():
    w = World(D(11, 3))
    for c, f in health.HOLDINGS.items():
        if f.delay:
            del w.rows[f"holdings.{c}"][D(11, 3)]            # 跨境：11/03 的持股要 11/04 才公布
    w.published["GetPCF"].add(D(11, 3))
    return w


def test_f71_collect_published():
    w = _world_1104()
    w.publish(D(11, 4))
    rc, out = run_world(w, T(11, 4, 17, 30))
    assert rc == 0 and "Traceback" not in out and len(_cap_hits(w)) == 4
    assert {(f["fundId"], f["date"]) for f in _cap_hits(w)} == {
        ("399", "2026-11-04T16:00:00.000Z"), ("500", "2026-11-04T16:00:00.000Z"), ("504", "2026-11-04T16:00:00.000Z"),
        ("502", "2026-11-04T16:00:00.000Z")}                                          # 00997A：持股日 11/03 → 生效日 11/05
    assert all(w.rows[f"holdings.{c}"][D(11, 4)].n == 50 for c in ("00982A", "00992A", "00415A"))
    assert w.rows["holdings.00997A"][D(11, 3)].n == 50 and D(11, 4) not in w.rows["holdings.00997A"]
    assert w.rows["holdings.00981A"][D(11, 4)].n == 50 and len(t5._pcf_hits(w)) == 4   # 統一照常
    rc, out = run_world(w, T(11, 4, 19, 30))
    assert rc == 0 and len(_cap_hits(w)) == 4                                         # 重跑：不再請求


def test_f71_collect_unpublished():
    w = _world_1104()
    w.publish(D(11, 4), "GetPCF")                                                     # 兩家投信都還沒公布 11/04
    rc, out = run_world(w, T(11, 4, 17, 30))
    assert rc == 0 and "⏳ 00982A持股：2026-11-04 尚未公布" in out and "Traceback" not in out
    rc, out = run_world(w, T(11, 4, 22, 30))
    assert rc == 1 and "❌ 00982A持股：缺 2026-11-04" in out


def test_f71_collect_errors_only_that_source():
    w = _world_1104()
    w.publish(D(11, 4))
    w.down.add("etf/buyback")                                                         # 群益主機失敗
    rc, out = run_world(w, T(11, 4, 17, 30))
    assert rc == 1 and "Traceback" not in out and "holdings.00982A 失敗" in out
    assert w.rows["holdings.00981A"][D(11, 4)].n == 50 and w.rows["prices.TWSE"][D(11, 4)].n == 1100
    w = _world_1104()
    w.publish(D(11, 4))
    orig = w._cap
    w._cap = lambda form: t3.Resp({"code": 500, "data": None, "message": "錯誤"}) if form["fundId"] == "399" else orig(form)
    rc, out = run_world(w, T(11, 4, 17, 30))
    assert rc == 1 and "holdings.00982A 失敗：群益 buyback 回應 code 500" in out and w.rows["holdings.00992A"][D(11, 4)].n == 50


def test_f71_history_since_and_rerun():
    w = World(D(10, 16))
    w.published["GetPCF"].update(t3.tradingcal.trading_days(D(10, 19), D(10, 30), t3.CLOSED))
    ok, out = t5._history(w, D(10, 19), D(10, 22))
    assert ok and "Traceback" not in out
    hold = lambda f: date.fromisoformat(f["date"][:10])
    assert [hold(f) for f in _cap_hits(w, "504")] == [D(10, 20), D(10, 21), D(10, 26)]   # 00415A 10/20 上市；10/22 → 生效日 10/27（10/23 颱風）
    assert all(D(10, 22) in w.rows[f"holdings.{c}"] for c in ("00982A", "00992A", "00415A"))
    n = len(_cap_hits(w))
    ok, out = t5._history(w, D(10, 19), D(10, 22))
    assert ok and len(_cap_hits(w)) == n and "待抓 0 天" in out


def test_f71_export_trust():
    summary = {t5.DATES[-1]: (43765013015, 19.09, 2, 16.39, 0, 0)}
    H = export.holding_export("00982A", t5.DATES, summary, t5.HELD, t5.TW, "主動群益台灣強棒", "TWSE")
    assert H["trust"] == "群益" and H["fund"] == "399" and H["sum"]["fa"] == 0.0
    assert export.holding_export("00981A", t5.DATES, summary, t5.HELD, t5.TW, "x", "TWSE")["trust"] == "統一"


# ─── F7-2：彙總排行 ─────────────────────────────────────
def _etf(dates, table):
    """table：{代號: [各持股日的股數（None = 未持有）]}，名稱 = 代號 + '名'、權重 = 1.5。"""
    held = {d: {("ST", c): (c + "名", s[i], 1.5) for c, s in table.items() if s[i] is not None} for i, d in enumerate(dates)}
    return dates, {}, held


DAYS = t3.tradingcal.trading_days(D(10, 27), D(11, 4), t3.CLOSED)                     # 10/27～11/04 共 7 天
TWC = {"2330", "2454", "1101"}
PX = {"2330": 1000.0, "2454": 1500.0}                                                # 1101 沒有收盤


def _holdings():
    d6 = DAYS[-6:]
    return {
        "00981A": _etf(d6, {"2330": [1_000_000] * 5 + [1_200_000], "2454": [500_000] * 5 + [None],
                            "1101": [None] * 5 + [300_000], "BE US": [10_000] * 6}),
        "00982A": _etf(DAYS[-2:], {"2330": [2_000_000, 1_900_000], "2454": [400_000, 400_000]}),
        "00988A": _etf(DAYS[-3:-1], {"2330": [None, 50_000]}),                           # 跨境：持股日 11/03
        "00403A": _etf(DAYS[-3:-1], {"2330": [1_000, 999_000]}),                           # 國內但停在 11/03 → 未更新
        "00415A": _etf(DAYS[-1:], {"2330": [100_000]}),                                    # 只有一天：只計入最多檔持有
    }


def test_f72_rank():
    R = export.active_rank(_holdings(), TWC, lambda c, d: PX.get(c))
    assert R["etfs"] == [{"c": "00415A", "t": "群益", "d": "2026-11-04"}, {"c": "00981A", "t": "統一", "d": "2026-11-04"},
                         {"c": "00982A", "t": "群益", "d": "2026-11-04"}, {"c": "00988A", "t": "統一", "d": "2026-11-03"}]
    assert R["stale"] == [{"c": "00403A", "t": "統一", "d": "2026-11-03"}]
    # 2330：+200（00981A）−100（00982A）+50（00988A 新進）＝ +150 張 × 1000 元 → 1.5 億；5 日只有 00981A 有 → +200
    assert R["buy"] == [{"c": "2330", "n": "2330名", "a": 1.5, "l1": 150, "l5": 200, "e": [
        {"e": "00981A", "d1": 200}, {"e": "00982A", "d1": -100}, {"e": "00988A", "d1": 50, "new": 1}]}]
    # 2454：00981A 出清 500 張 × 1500 元 → −7.5 億；00982A 不變不列；1101 沒有收盤不進排行
    assert R["sell"] == [{"c": "2454", "n": "2454名", "a": -7.5, "l1": -500, "l5": -500, "e": [{"e": "00981A", "d1": -500, "out": 1}]}]
    assert [(r["c"], r["k"], r["l"], r["v"]) for r in R["held"]] == [("2330", 4, 3250, 32.5), ("2454", 1, 400, 6.0), ("1101", 1, 300, 0.0)]
    assert R["held"][0]["e"] == [{"e": "00415A", "w": 1.5}, {"e": "00981A", "w": 1.5}, {"e": "00982A", "w": 1.5}, {"e": "00988A", "w": 1.5}]


def test_f72_edges():
    one = {"00981A": _holdings()["00981A"]}                                            # 只有 1 檔也能顯示
    R = export.active_rank(one, TWC, lambda c, d: PX.get(c))
    assert [r["c"] for r in R["buy"]] == ["2330"] and [r["c"] for r in R["sell"]] == ["2454"] and R["stale"] == []
    many = {"00981A": _etf(DAYS[-2:], {str(1000 + i): [None, 1000 * (i + 1)] for i in range(30)})}
    R = export.active_rank(many, {str(1000 + i) for i in range(30)}, lambda c, d: 10.0)
    assert len(R["buy"]) == export.ACTIVE_TOP == 20 and R["buy"][0]["c"] == "1029" and R["sell"] == []
    assert all(r["e"][0].get("new") == 1 for r in R["buy"])
    # PG 補：5 日要含「當天沒變動、5 天內有買賣」的 ETF（00982A 今天 0、5 日 +300）；e 只列當天有變動的
    two = {"00981A": _etf(DAYS[-6:], {"2330": [1_000_000] * 5 + [1_100_000]}),
           "00982A": _etf(DAYS[-6:], {"2330": [0, 0, 300_000, 300_000, 300_000, 300_000]})}
    R = export.active_rank(two, TWC, lambda c, d: PX.get(c))
    assert R["buy"][0]["l1"] == 100 and R["buy"][0]["l5"] == 400 and [x["e"] for x in R["buy"][0]["e"]] == ["00981A"]


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"✅ {name}")
    print("全部通過")
