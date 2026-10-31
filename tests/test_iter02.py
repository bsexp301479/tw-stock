"""
第 02 輪純邏輯測試（不連網、不連資料庫）：
民國日期、除權息／減資／面額變更事件解析、事件對應與還原係數、上櫃參考價反推、
P14 漲跌三分支與漲跌家數、P16 股本變動註記、A2 三大法人金額解析與連續天數。

  python3 tests/test_iter02.py      （也相容 pytest）
"""
import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from twstock.collectors.alerts import roc_date  # noqa: E402
from twstock.collectors.daily import parse_insti_amount  # noqa: E402
from twstock.collectors.events import parse_events  # noqa: E402
from twstock.export import (_adj_factors, _cap_event, _changes, _insti_official,  # noqa: E402
                            _price_events, _side)


def D(m, d, y=2026):
    return date(y, m, d)


def N(*v):
    """模擬資料庫的 DECIMAL 欄位（None = 無成交或官方未提供）。"""
    return tuple(None if x is None else Decimal(str(x)) for x in v)


# ─── B1：民國日期、事件解析 ───────────────────────────────
def test_roc_date():
    assert roc_date("115年09月02日") == D(9, 2)
    assert roc_date("114/11/03") == D(11, 3, 2025)
    assert roc_date("115/07/10") == D(7, 10)
    assert roc_date("1151029") == D(10, 29)                 # 第 1 輪格式不受影響
    assert roc_date("115年13月01日") is None and roc_date("") is None


T49 = ["資料日期", "股票代號", "股票名稱", "除權息前收盤價", "除權息參考價", "權值+息值", "權/息"]
AUU = ["恢復買賣日期", "股票代號", "名稱", "停止買賣前收盤價格", "恢復買賣參考價", "漲停價格", "跌停價格",
       "開盤競價基準", "除權參考價", "減資原因", "詳細資料"]
B8U = ["恢復買賣日期", "股票代號", "名稱", "停止買賣前收盤價格", "恢復買賣參考價", "漲停價格", "跌停價格",
       "開盤競價基準", "詳細資料"]
TPX = ["除權息日期", "代號", "名稱", "除權息前收盤價", "除權息參考價", "權值", "息值", "權值+息值", "權/息"]


def test_parse_events():
    r = parse_events("TWT49U", T49, [
        ["115年09月02日", "6669", "緯穎", "7,800.00", "2,614.99", "5,185.002642", "權"],
        ["115年09月01日", "00939", "統一台灣高息動能", "23.17", "23.04", "0.125000", "息"],   # ETF
        ["115年09月01日", "1732", "毛寶", "26.45", "25.85", "0.600000", "息"],
        ["115年09月03日", "1234", "測試", "--", "10.00", "", "息"],                           # 前收無法解析
        ["115年09月03日", "1235", "測試"]])                                                   # 列太短
    assert r == [{"stock_code": "6669", "event_date": "2026-09-02", "event_type": "權",
                  "prev_close": 7800.0, "ref_price": 2614.99, "source": "TWT49U"},
                 {"stock_code": "1732", "event_date": "2026-09-01", "event_type": "息",
                  "prev_close": 26.45, "ref_price": 25.85, "source": "TWT49U"}]
    r = parse_events("TWTAUU", AUU, [["114/11/03", "2832", "台產", "36.00", "47.14", "51.80", "42.45", "47.15",
                                      "--", "退還股款", "2832  ,20251021"]])
    assert [(x["event_type"], x["event_date"], x["prev_close"], x["ref_price"]) for x in r] == \
        [("減", "2025-11-03", 36.0, 47.14)]
    r = parse_events("TWTB8U", B8U, [["115/09/07", "6949", "沛爾生醫-創", "1,490.00", "74.50", "81.90", "67.10",
                                      "74.50", "6949,20260827,20260907"]])
    assert [(x["event_type"], x["prev_close"], x["ref_price"]) for x in r] == [("面", 1490.0, 74.5)]
    r = parse_events("TPEX_EX", TPX, [
        ["115/07/09", "5511", "德昌              ", "79.70", "63.48", "12.623647", "3.600000", "16.223647", "除權息"],
        ["115/07/10", "6223", "旺矽", "6460.00", "6438.00", "0.000000", "22.000000", "22.000000", "除息"],
        ["115/07/10", "00950B", "債券", "10.00", "9.90", "0", "0.1", "0.1", "除息"]])
    assert [(x["stock_code"], x["event_type"], x["event_date"]) for x in r] == \
        [("5511", "權息", "2026-07-09"), ("6223", "息", "2026-07-10")]
    # 空回應、欄位缺漏
    assert parse_events("TWT49U", None, None) == []
    assert parse_events("TWT49U", ["資料日期", "股票代號"], [["115年09月02日", "6669"]]) == []
    assert parse_events("TPEX_EX", TPX, []) == []


# ─── B1：事件對應、上櫃反推、還原係數 ─────────────────────
def test_price_events():
    # 7/10 休市日的除息 → 生效於 7/13；資料之前、之後的事件略過
    d = (D(7, 8), D(7, 9), D(7, 13), D(7, 14))
    c, ch = N(100, 100, 97, 98), N(1, 0, 0.45, 1)
    off = [{"d": D(7, 10), "t": "息", "p": 100.0, "r": 96.55, "src": "TWT49U"},
           {"d": D(7, 20), "t": "息", "p": 98.0, "r": 97.0, "src": "TWT49U"},
           {"d": D(7, 1), "t": "權", "p": 50.0, "r": 40.0, "src": "TWT49U"}]
    ev, bad = _price_events(d, c, ch, "TWSE", off)
    assert ev == [{"i": 2, "d": "2026-07-13", "t": "息", "p": 100.0, "r": 96.55}] and bad == []
    # 同一列兩筆官方事件 → 取減資
    off = [{"d": D(7, 13), "t": "權", "p": 100.0, "r": 90.0, "src": "TWT49U"},
           {"d": D(7, 13), "t": "減", "p": 100.0, "r": 120.0, "src": "TWTAUU"}]
    assert [(e["t"], e["r"]) for e in _price_events(d, c, ch, "TWSE", off)[0]] == [("減", 120.0)]
    # 係數超出 0.02～20 → 不採用
    ev, bad = _price_events(d, c, ch, "TWSE", [{"d": D(7, 13), "t": "面", "p": 1000.0, "r": 10.0, "src": "TWTB8U"}])
    assert ev == [] and bad == [("2026-07-13", 0.01)]
    # 上櫃反推：參考價 = 收盤 − 官方漲跌；前一列無成交、官方漲跌為 None 時不反推；漲跌停不產生事件
    d = (D(8, 6), D(8, 7), D(8, 10), D(8, 11), D(8, 12), D(8, 13))
    c, ch = N(700, 720, 79.2, None, 80, 81), N(5, 20, 7.2, None, 0.5, None)
    assert _price_events(d, c, ch, "TPEx", [])[0] == [{"i": 2, "d": "2026-08-10", "t": "調", "p": 720.0, "r": 72.0}]
    # 與官方事件同一列 → 以官方為準；上市不反推
    off = [{"d": D(8, 10), "t": "息", "p": 720.0, "r": 72.0, "src": "TPEX_EX"}]
    assert [e["t"] for e in _price_events(d, c, ch, "TPEx", off)[0]] == ["息"]
    assert _price_events(d, c, ch, "TWSE", [])[0] == []


def test_adj_factors():
    ev = [{"i": 2, "p": 100.0, "r": 96.0}, {"i": 4, "p": 50.0, "r": 75.0}]      # 現金股利 0.96、減資 1.5
    assert [round(x, 4) for x in _adj_factors(6, ev)] == [1.44, 1.44, 1.5, 1.5, 1.0, 1.0]
    assert _adj_factors(3, []) == [1.0, 1.0, 1.0]
    # 6669：6/22 除息 4,985.6/5,130、9/2 除權 2,614.99/7,800；3/31 最低 3,290 → 1,071.94
    af = _adj_factors(3, [{"i": 1, "p": 5130.0, "r": 4985.6}, {"i": 2, "p": 7800.0, "r": 2614.99}])
    assert round(3290 * af[0], 2) == 1071.94 and af[2] == 1.0


# ─── P14：漲跌三分支與漲跌家數 ───────────────────────────
def test_changes():
    # 上市：一般日、平盤、無成交、前一列無成交（分支 2）、不比價（分支 3）、事件日（分支 1）
    d = (D(10, 26), D(10, 27), D(10, 28), D(10, 29), D(10, 30), D(11, 2), D(11, 3))
    c, ch = N(7.21, 7.44, 7.44, None, 7.37, 8.00, 7.00), N(0.1, 0.23, 0, 0, 0, 0, 0)
    ev = [{"i": 6, "d": "2026-11-03", "t": "息", "p": 8.0, "r": 7.5}]
    chs, rel, miss = _changes(d, c, ch, "TWSE", ev)
    assert chs == [0.1, 0.23, 0.0, None, -0.07, None, -0.5]
    assert rel == [None, None, None, None, D(10, 28), None, None] and miss == [D(11, 2)]
    # 事件生效日當天無成交 → 下一個成交日相對參考價（不是相對最後成交）
    chs, rel, _ = _changes((D(7, 1), D(7, 2), D(7, 3)), N(248, None, 239), N(1, 0, 0), "TWSE",
                           [{"i": 1, "d": "2026-07-02", "t": "息", "p": 248.0, "r": 240.82}])
    assert chs == [1.0, None, -2.0] and rel == [None] * 3
    # 上櫃：除權息日官方漲跌是文字（None）→ 收盤 − 參考價；一般日照官方
    chs, rel, miss = _changes((D(7, 15), D(7, 16), D(7, 17), D(7, 20)), N(677, 623, None, 630),
                              N(2, None, None, 1.5), "TPEx", [{"i": 1, "d": "2026-07-16", "t": "息", "p": 677.0, "r": 651.5}])
    assert chs == [2.0, -29.0, None, 1.5] and rel == [None] * 4 and miss == []
    # 漲跌家數歸類：不比價（None）算平盤
    assert [_side(x) for x in (-0.07, 0.1, 0.0, None)] == ["down", "up", "flat", "flat"]


# ─── P16：股本變動註記 ───────────────────────────────────
def test_cap_event():
    ev = [{"i": 1, "d": "2026-06-22", "t": "息", "p": 5130.0, "r": 4985.6},
          {"i": 2, "d": "2026-09-02", "t": "權", "p": 7800.0, "r": 2614.99}]
    assert _cap_event(ev, D(10, 30)) == {"d": "2026-09-02", "t": "權"}
    assert _cap_event(ev, D(12, 1)) == {"d": "2026-09-02", "t": "權"}       # 第 90 天
    assert _cap_event(ev, D(12, 2)) is None                                     # 第 91 天
    assert _cap_event(ev[:1], D(6, 30)) is None                                 # 只有現金股利
    assert _cap_event([{"i": 1, "d": "2026-09-01", "t": "權息", "p": 100.0, "r": 95.0}], D(9, 2)) is None
    assert _cap_event([{"i": 1, "d": "2026-06-30", "t": "調", "p": 208.0, "r": 360.0}], D(7, 1)) == \
        {"d": "2026-06-30", "t": "調"}
    assert _cap_event([], D(10, 30)) is None


# ─── A2：官方三大法人金額 ─────────────────────────────────
BFI = {"stat": "OK", "fields": ["單位名稱", "買進金額", "賣出金額", "買賣差額"], "data": [
    ["自營商(自行買賣)", "9,031,429,661", "12,871,788,307", "-3,840,358,646"],
    ["自營商(避險)", "32,728,302,266", "80,257,041,536", "-47,528,739,270"],
    ["投信", "36,336,431,234", "12,717,634,927", "23,618,796,307"],
    ["外資及陸資(不含外資自營商)", "340,478,117,346", "452,945,367,240", "-112,467,249,894"],
    ["外資自營商", "0", "0", "0"],
    ["合計", "418,574,280,507", "558,791,832,010", "-140,217,551,503"]]}


def test_parse_insti_amount():
    r = {x["unit"]: x for x in parse_insti_amount(BFI, D(10, 30))}
    assert set(r) == {"dealer_self", "dealer_hedge", "trust", "foreign", "foreign_dealer", "total"}
    assert r["dealer_self"]["net_amount"] == -3840358646 and r["foreign"]["net_amount"] == -112467249894
    assert r["total"]["buy_amount"] == 418574280507 and r["total"]["trade_date"] == "2026-10-30"
    # 合計 = 自營自行 + 自營避險 + 投信 + 外資及陸資（外資自營商已含在自營商，不另加）
    assert sum(r[k]["net_amount"] for k in ("dealer_self", "dealer_hedge", "trust", "foreign")) == \
        r["total"]["net_amount"]
    assert parse_insti_amount({"stat": "很抱歉，沒有符合條件的資料!"}, D(10, 31)) == []
    assert parse_insti_amount({"stat": "OK", "fields": ["單位名稱"], "data": [["合計"]]}, D(10, 30)) == []


def test_insti_official():
    days = [D(9, 1) + timedelta(k) for k in range(25)]
    nets = [5e8] * 21 + [-1e8, -2e8, 0, -3e8]
    amount = {d: {"foreign": v, "foreign_dealer": 0, "trust": 1e8, "dealer_self": -2e7, "dealer_hedge": -3e7,
                  "total": v + 5e7} for d, v in zip(days, nets)}
    o = _insti_official(amount)
    assert o["date"] == "2026-09-25" and o["d"][-1] == "2026-09-25"
    assert len(o["d"]) == len(o["f"]) == len(o["t"]) == 20
    assert (o["foreign"], o["trust"], o["dealer"], o["total"]) == (-3.0, 1.0, -0.5, -2.5)
    assert o["fs"] == -1                                       # 前一天差額 0 → 只連賣 1 日
    amount[days[-2]]["foreign"] = -1e8
    assert _insti_official(amount)["fs"] == -4
    assert _insti_official({}) is None


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"✅ {name}")
    print("全部通過")
