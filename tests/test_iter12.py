"""
第 12 輪純邏輯測試（不連網、不連資料庫）：
F12-1 P26 融資融券圖刻度說明（原始碼檢查）；
F12-2 市值加權本益比 market_wpe（公式、虧損／0／空白排除、沒有股數、位置與區間、覆蓋率、最大權重、沒有資料不輸出）與估值卡；
F12-3 ETF 借券 etf_block 的 lb、l1、latest.json 的 sbl_etf、今日頁與 ETF 頁；
F12-4 市值、週轉率 cap_turnover、個股 JSON 的 mt、screen.json 的 mc、to、排行與選股（原始碼檢查）。

  python3 tests/test_iter12.py      （也相容 pytest）
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_iter03 as t3  # noqa: E402
from twstock import export  # noqa: E402

D = t3.D
ROOT = Path(__file__).resolve().parent.parent
d1, d2, d3 = D(11, 4), D(11, 5), D(11, 6)


# ─── F12-2：市值加權本益比 ───────────────────────────────
def test_f122_wpe_formula():
    rows = [(d3, "TWSE", "A", 20.0, 300.0), (d3, "TWSE", "B", 10.0, 100.0),
            (d3, "TWSE", "C", None, 50.0), (d3, "TWSE", "D", 0.0, 30.0), (d3, "TWSE", "E", -5.0, 20.0),   # 空白、0、負 → 不計入
            (d3, "TWSE", "F", 15.0, None), (d3, "TWSE", "G", 15.0, 0.0)]                                # 沒有市值 → 全部不算
    r = export.market_wpe(rows, [d3])["TWSE"]
    v = 400 / (300 / 20 + 100 / 10)                                                                     # 16.0
    assert r == {"v": round(v, 2), "p": 100.0, "lo": 16.0, "hi": 16.0, "cov": round(400 / 500 * 100, 1), "t": ["A", 75.0]}


def test_f122_wpe_position_and_markets():
    rows = [(d1, "TWSE", "A", 10.0, 100.0), (d2, "TWSE", "A", 20.0, 100.0), (d3, "TWSE", "A", 15.0, 100.0),
            (d3, "TPEx", "X", 30.0, 10.0), (D(10, 1), "TWSE", "A", 99.0, 100.0)]                          # 窗口外略過
    out = export.market_wpe(rows, [d1, d2, d3])
    assert out["TWSE"] == {"v": 15.0, "p": round(2 / 3 * 100, 1), "lo": 10.0, "hi": 20.0, "cov": 100.0, "t": ["A", 100.0]}
    assert out["TPEx"]["v"] == 30.0 and out["TPEx"]["p"] == 100.0
    assert export.market_wpe([], [d3]) == {}                                                           # 沒有資料 → 不輸出
    assert export.market_wpe([(d3, "TWSE", "A", None, 100.0)], [d3]) == {}                              # 全部虧損 → 不輸出
    # 某天全部虧損：那天跳過，不當成 0
    out = export.market_wpe([(d1, "TWSE", "A", 10.0, 1.0), (d2, "TWSE", "A", None, 1.0)], [d1, d2])
    assert out["TWSE"]["v"] == 10.0 and out["TWSE"]["lo"] == out["TWSE"]["hi"] == 10.0


def test_f122_wpe_export_source():
    src = (ROOT / "twstock" / "export.py").read_text(encoding="utf-8")
    assert "LEFT JOIN daily_prices p ON p.stock_id" in src and 'mv[m]["wpe"]' in src


# ─── F12-3：ETF 借券 ───────────────────────────────────
def test_f123_etf_block():
    latest = {"TWSE": (d3, [("0050", "元大台灣50", 60.0, 0.5, 1000000, 6e8), ("0056", "高股息", 35.0, 0, 0, 0)])}
    e = export.etf_block(latest, {"0050": (100, 110, 5, 4)}, {"0050": (5000000, 6500400)})
    r = e["rows"]["0050"]
    assert r["lb"] == 6500 and r["l1"] == 1500 and r["mb"] == 110
    assert "lb" not in e["rows"]["0056"] and "l1" not in e["rows"]["0056"]                             # 沒有借券列 → 不輸出
    assert export.etf_block(latest, {}) == export.etf_block(latest, {}, None)                           # 舊呼叫相容
    m = export.market_sbl([d3], {d3: [(5000000, 6500400), (1000, 0)]})
    assert m == {"d": "2026-11-06", "lb": 6500, "l1": 1499, "n": 2}                                    # 先合計股數再換張


def test_f123_export_source():
    src = (ROOT / "twstock" / "export.py").read_text(encoding="utf-8")
    assert "def _load_etf_sbl(cur)" in src and '"sbl_etf"' in src


# ─── F12-4：市值、週轉率 ───────────────────────────────
def test_f124_cap_turnover():
    assert export.cap_turnover(1000.0, 11094000, 25932370067) == (259323.7, 0.04)
    assert export.cap_turnover(10.0, 5000000, 10000000) == (1.0, 50.0)
    assert export.cap_turnover(10.0, None, 10000000) == (1.0, None)                                    # 今天沒有成交資料
    assert export.cap_turnover(None, 5, 10) == (None, 50.0)
    assert export.cap_turnover(10.0, 5, None) == (None, None) == export.cap_turnover(10.0, 5, 0)       # 沒有股數
    assert set(export.SCREEN_KEYS) >= {"mc", "to"}


# ─── 網站（原始碼檢查）───────────────────────────────────
def test_f12_site():
    js = (ROOT / "site" / "stock.js").read_text(encoding="utf-8")
    assert "右側刻度只適用融資；融券、借券各自縮放" in js                                                    # F12-1 P26
    assert "...mtCards, ...mgCards, ...slCards" in js and "MT?.mc == null ? '--'" in js                   # F12-4
    app = (ROOT / "site" / "app.js").read_text(encoding="utf-8")
    assert "function wpeLine(V)" in app and "${wpeLine(V)}" in app and "不是證交所公布的數字" in app            # F12-2
    assert "function etfSblLine(B)" in app and "${etfSblLine(L.sbl_etf)}" in app and "不等於看空" in app      # F12-3
    assert "<th>借券餘額</th><th>借券增減</th>" in app and "['l1+', '借券增加', -1]" in app
    assert "['to', '週轉率', 'to', -1, 'x']" in app and "'rs20', 'to']]" in app and "to: ['to', 'mc']" in app
    assert "{ id: 'mc', g: '流動性'" in app and "{ id: 'to', g: '流動性'" in app
    assert "'lb', 'lp', 'mc', 'to'].includes(k)" in app


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"✅ {name}")
    print("全部通過")
