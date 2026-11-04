"""
第 08 輪純邏輯測試（不連網、不連資料庫）：
F8-1 單位數 1 日變化（unit_change、holding_export）、投信買超中的主動 ETF（active_trust、trust_share）；
F8-2 選股欄位（price_stats、revenue_stats、_cap_event 90 天邊界、screen_build）；
F8-3 融資融券換算與欄位（margin_conv、conv_k、screen_margin、margin_series）。
數值以 2026-11-04 的實際資料為範例（00982A 單位數、6672／2330 投信、寶雅 5904 面額變更、緯穎 6669 除權）。

  python3 tests/test_iter08.py      （也相容 pytest）
"""
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from twstock import export  # noqa: E402


def D(m, d, y=2026):
    return date(y, m, d)


def _days(n, end=D(11, 4)):
    """n 個平日（舊到新，最後一天 = end）；測試不需要休市日。"""
    out, d = [], end
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d -= timedelta(days=1)
    return out[::-1]


# ─── F8-1：單位數 1 日變化 ──────────────────────────────
def test_f81_unit_change():
    d3, d4 = D(11, 3), D(11, 4)
    row = lambda u: (1, 2, 3, 4, 5, 6, u)                       # 第 7 欄 = units
    assert export.unit_change({d3: row(2242436000), d4: row(2292436000)}, [d3, d4]) == 2.23   # 00982A
    assert export.unit_change({d3: row(1040877000), d4: row(1040877000)}, [d3, d4]) == 0.0    # 00997A
    assert export.unit_change({d3: row(10231209000), d4: row(10373709000)}, [d3, d4]) == 1.39  # 00981A
    assert export.unit_change({d4: row(100)}, [d4]) is None                                     # 只有一個持股日
    assert export.unit_change({d3: row(None), d4: row(100)}, [d3, d4]) is None                  # 前一日沒有單位數
    assert export.unit_change({d3: row(0), d4: row(100)}, [d3, d4]) is None                     # 前一日 0
    assert export.unit_change({d3: (1, 2, 3, 4, 5, 6), d4: (1, 2, 3, 4, 5, 6)}, [d3, d4]) is None   # 舊格式（6 欄）


def test_f81_holding_export_u1():
    d3, d4 = D(11, 3), D(11, 4)
    held = {d: {("ST", "2330"): ("台積電", 1_000_000, 8.0)} for d in (d3, d4)}
    s7 = {d3: (1e10, 19.0, 1, 8.0, 0, 0, 2242436000), d4: (1e10, 19.09, 1, 8.0, 0, 0, 2292436000)}
    H = export.holding_export("00982A", [d3, d4], s7, held, {"2330"}, "主動群益台灣強棒", "TWSE")
    assert H["sum"]["u1"] == 2.23 and H["sum"]["nu"] == 19.09
    s6 = {d: v[:6] for d, v in s7.items()}                                       # 第 5 輪測試的 6 欄：沒有 u1 鍵
    assert "u1" not in export.holding_export("00982A", [d3, d4], s6, held, {"2330"}, "x", "TWSE")["sum"]


# ─── F8-1：B16 投信買超中的主動 ETF ─────────────────────
def _h(dates, table):
    """table：{代號: [各持股日股數（None = 未持有）]}。"""
    held = {d: {("ST", c): (c, v[i], 1.0) for c, v in table.items() if v[i] is not None} for i, d in enumerate(dates)}
    return (dates, {}, held)


def test_f81_active_trust():
    d2, d3, d4 = D(11, 2), D(11, 3), D(11, 4)
    tw = {"6672", "2330", "3211", "1802", "9999"}
    H = {"00982A": _h([d3, d4], {"6672": [1_400_000, 2_236_000], "2330": [1_609_000, 1_609_000]}),   # 6672 +836
         "00981A": _h([d3, d4], {"2330": [14_464_000, 15_269_000], "3211": [150_000, None]}),       # 2330 +805、3211 出清 −150
         "00403A": _h([d2, d3], {"2330": [7_000_000, 9_000_000]}),                                  # 國內但停在 11/03 → 不計
         "00992A": _h([d4], {"1802": [500_000]}),                                                   # 只有一個持股日 → 不計
         "00997A": _h([d2, d3], {"9999": [0, 50_000]}),                                             # 跨境 → 不計
         "00415A": _h([d3, d4], {"1802": [None, 20_000], "AAPL US": [1, 2]})}                       # 新進 +20；海外不計
    act = export.active_trust(H, tw, d4)
    assert act == {"6672": 836, "2330": 805, "3211": -150, "1802": 20}
    assert "9999" not in act                                                     # 只有跨境 ETF 有變動 → 不顯示
    assert export.active_trust(H, tw, D(11, 5)) == {}                            # 持股日 ≠ 法人資料日


def test_f81_trust_share():
    assert export.trust_share(850, 836) == 98                                    # 騰輝
    assert export.trust_share(3715, 905) == 24                                   # 台積電
    assert export.trust_share(-385, -304) == 79                                  # 同為賣超
    assert export.trust_share(0, 120) is None                                    # 投信 0
    assert export.trust_share(500, -120) is None                                 # 方向相反
    assert export.trust_share(100, 150) is None                                  # 超過投信合計
    assert export.trust_share(100, 100) == 100


# ─── F8-2：價量欄位 ─────────────────────────────────────
def _stats(close, tv=None, idx=None, days=None, events=(), market="TWSE"):
    """close：每個交易日的原始收盤（None = 無成交）；用 export 的還原邏輯算 adj。"""
    days = days or _days(len(close))
    tv = tv or [1e8 if c is not None else 0 for c in close]
    ref = {e["d"]: e["r"] for e in events}
    prev = [None] + list(close[:-1])                                             # 官方漲跌：相對前一日收盤（事件日相對參考價）
    ch = [None if c is None or (p is None and days[i] not in ref) else round(c - ref.get(days[i], p), 2)
          for i, (c, p) in enumerate(zip(close, prev))]
    ev, _ = export._price_events(days, close, ch, market, list(events))
    af = export._adj_factors(len(days), ev)
    adj = [None if c is None else c * af[i] for i, c in enumerate(close)]
    return export.price_stats(days, adj, tv, days, idx or {d: 100.0 for d in days}), ev


def test_f82_price_basic():
    s, _ = _stats([100.0] * 69 + [110.0])                                        # 70 天：前 69 天 100、今天 110
    assert s["a20"] == 1.0 and s["vr"] == 1.0
    assert s["r5"] == s["r20"] == s["r60"] == 10.0 and s["rs20"] == 10.0 and s["rs60"] == 10.0
    assert s["b20"] == round((110 / 100.5 - 1) * 100, 2) == 9.45 and s["b60"] == round((110 / (100 + 10 / 60) - 1) * 100, 2)
    assert s["nh"] == 60 and s["nl"] == 0                                        # 不足 121 天 → 最大 60
    s, _ = _stats([100.0] * 69 + [110.0], idx={**{d: 100.0 for d in _days(70)}, D(11, 4): 105.0})
    assert s["rs20"] == 5.0                                                      # 相對指數：10% − 5%


def test_f82_new_listing():
    s, _ = _stats([50.0] * 30)                                                   # 新上市 30 天
    assert s["b60"] is None and s["r60"] is None and s["rs60"] is None and s["b20"] == 0.0 and s["r20"] == 0.0
    s, _ = _stats([50.0] * 10, days=_days(10))
    assert s["a20"] is None and s["vr"] is None and s["b20"] is None and s["nh"] == 0


def test_f82_par_change():
    # 寶雅 5904 型：面額 10 元 → 1 元，收盤 720 → 72 附近；還原後 r60、b60 不跳動、不會變成 60 日新低
    days = _days(80)
    close = [720.0] * 70 + [72.0, 72.5, 73.0, 72.0, 71.5, 72.0, 72.5, 73.0, 72.5, 72.0]
    ev = [{"d": days[70], "t": "面", "p": 720.0, "r": 72.0, "src": "TPEX"}]
    s, e = _stats(close, days=days, events=ev, market="TPEx")
    assert len(e) == 1 and abs(s["r60"]) < 1 and abs(s["b60"]) < 1 and s["nl"] == 0 and s["nh"] == 0


def test_f82_ex_rights_new_high():
    # 除權當天參考價 50 → 25：未還原會是「新低」，還原後今天 26 > 前 60 日最高（還原 25）→ 新高
    days = _days(70)
    close = [50.0] * 65 + [25.0, 25.0, 25.0, 25.0, 26.0]
    s, _ = _stats(close, days=days, events=[{"d": days[65], "t": "權", "p": 50.0, "r": 25.0, "src": "TWT49U"}])
    assert s["nh"] == 60 and s["nl"] == 0 and s["r20"] == 4.0


def test_f82_volume_ratio():
    tv = [1e8] * 20 + [3e8]
    s, _ = _stats([10.0] * 21, tv=tv, days=_days(21))
    assert s["vr"] == 3.0 and s["a20"] == 1.1
    tv = [0] * 10 + [1e8] * 10 + [1e8]                                           # 前 20 日有 10 天無成交：以 0 計入
    s, _ = _stats([None] * 10 + [10.0] * 11, tv=tv, days=_days(21))
    assert s["vr"] == 2.0
    s, _ = _stats([None] * 20 + [10.0], tv=[0] * 20 + [1e8], days=_days(21))   # 前 20 日全部無成交 → None
    assert s["vr"] is None


def test_f82_today_no_trade():
    s, _ = _stats([100.0] * 68 + [120.0, None], tv=[1e8] * 69 + [0])
    assert s["nh"] == 0 and s["nl"] == 0 and s["vr"] == 0.0 and s["r5"] == 20.0     # 報酬用最後成交收盤


def test_f82_revenue_stats():
    rows = export._revenue_rows([[2026, m, 100 + m, None, 10.0] for m in range(7, 10)])
    assert export.revenue_stats(rows) == {"rm": 202609, "ry": 10.0, "rc": None, "rh": 0, "r3": 1}
    rows = export._revenue_rows([[2026, 6, 100, None, 10.0], [2026, 8, 100, None, 10.0], [2026, 9, 100, None, 10.0]])
    assert export.revenue_stats(rows)["r3"] == 0                                 # 7 月缺 → 不連續
    rows = export._revenue_rows([[2026, 7, 100, None, 10.0], [2026, 8, 100, None, -1.0], [2026, 9, 100, None, 10.0]])
    assert export.revenue_stats(rows)["r3"] == 0
    assert export.revenue_stats([]) == {"rm": None, "ry": None, "rc": None, "rh": None, "r3": None}


def test_f82_cap_boundary():
    ev = [{"d": "2026-08-06", "t": "面", "p": 720.0, "r": 72.0}]
    assert export._cap_event(ev, D(11, 4)) == {"d": "2026-08-06", "t": "面"}    # 90 天
    assert export._cap_event(ev, D(11, 5)) is None                               # 91 天
    assert export._cap_event([{"d": "2026-10-01", "t": "息", "p": 50.0, "r": 40.0}], D(11, 4)) is None   # 除息不算


def test_f82_screen_build():
    a = {k: None for k in export.SCREEN_KEYS}
    rows = {"2330": {**a, "rm": 202609, "b20": -7.38}, "1101": {**a, "rm": 202609}, "9999": {**a, "rm": 202608}, "8888": a}
    S = export.screen_build(rows, {"d": "2026-11-04", "fd": "2026-11-04", "md": {"TWSE": "2026-11-04"}})
    assert S["codes"] == ["1101", "2330", "8888", "9999"] and S["b20"] == [None, -7.38, None, None]
    assert S["rmd"] == {"202609": 2, "202608": 1} and list(S["rmd"]) == ["202609", "202608"]
    assert set(S) == {"d", "fd", "md", "rmd", "codes", *export.SCREEN_KEYS}


# ─── F8-3：融資融券 ─────────────────────────────────────
def test_f83_conv_par_change():
    # 寶雅 5904：8/7 594 張 → 8/10 前日 5,940（官方已 ×10）、今日 5,935
    rows = {D(8, 6): (594, 594, 26610, 0, 0, None), D(8, 7): (594, 594, 266109, 0, 0, None),
            D(8, 10): (5940, 5935, 266109, 0, 5, None), D(8, 11): (5935, 4785, 266109, 5, 27, None)}
    ev = [{"i": 1, "d": "2026-08-10", "t": "調", "p": 720.0, "r": 72.0}]
    conv = export.margin_conv(rows, ev)
    assert conv == [{"d": "2026-08-10", "k": 10.0, "t": "調"}]
    assert export.conv_k(conv, D(8, 7)) == 10.0 and export.conv_k(conv, D(8, 10)) == 1.0
    m = export.screen_margin(rows, D(8, 11), D(8, 6), conv, "TPEx")
    assert m["m5"] == 4785 - 5940 and m["s5"] == 27 and m["m1"] == -1150 and m["mnt"] is None   # 不會是 +899%
    days = [D(8, 6), D(8, 7), D(8, 10), D(8, 11), D(8, 12)]
    assert export.margin_series(days, rows, conv) == {"mb": [594, 594, 5935, 4785, None], "sb": [0, 0, 5, 27, None], "k": conv}


def test_f83_ex_rights_not_converted():
    # 緯穎 6669 9/2 除權：官方前日餘額 = 前一日餘額 → 不換算（1,418 → 2,078 照原值）
    rows = {D(9, 1): (1420, 1418, 50000, 0, 10, None), D(9, 2): (1418, 2078, 50000, 10, 12, None)}
    ev = [{"i": 1, "d": "2026-09-02", "t": "權", "p": 7800.0, "r": 2614.99}]
    assert export.margin_conv(rows, ev) == []
    assert export.margin_series([D(9, 1), D(9, 2)], rows, []) == {"mb": [1418, 2078], "sb": [10, 12]}
    assert export.margin_series([D(9, 1)], {}, []) is None                       # 沒有任何融資融券列


def test_f83_margin_fields():
    d0, d5 = D(11, 4), D(10, 28)
    rows = {d5: (900, 1000, 0, 10, 20, None), D(11, 3): (1050, 1100, 0, 20, 25, None), d0: (1100, 1200, 0, 25, 300, "OX")}
    m = export.screen_margin(rows, d0, d5, [], "TWSE")
    assert m == {"mb": 1200, "m1": 100, "m5": 200, "sb": 300, "s1": 275, "s5": 280, "sr": 25.0, "mu": None, "mnt": "OX"}   # 限額 0 → mu None
    assert export.screen_margin(rows, d0, d5, [], "TPEx")["mnt"] is None         # 上櫃備註不解讀
    assert export.screen_margin(rows, D(11, 5), d5, [], "TWSE")["mb"] is None    # 當天沒有列（不在清單）
    assert export.screen_margin(rows, d0, None, [], "TWSE")["m5"] is None        # 不足 6 個融資融券日
    assert export.screen_margin({}, None, None, [], "TWSE")["mb"] is None        # 該市場沒有融資融券資料


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"✅ {name}")
    print("全部通過")
