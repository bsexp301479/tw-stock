"""第 15 輪（不連網、不連資料庫）：F15-1 累計 EPS 年增基期與轉盈；F15-2 ETF 個股頁（etfp/）；
F15-3 價差 0 軸、結算日跨年元旦；F15-4 季報截止日遇週末。"""
import json, shutil, subprocess, sys
from datetime import date
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from twstock import export  # noqa: E402

APP = (ROOT / "site" / "app.js").read_text(encoding="utf-8")
STK = (ROOT / "site" / "stock.js").read_text(encoding="utf-8")
CSS = (ROOT / "site" / "app.css").read_text(encoding="utf-8")
SRC = (ROOT / "twstock" / "export.py").read_text(encoding="utf-8")
D = date
# 只有 2026 年的休市（同 test_iter14）：模擬「2027 年官方表還沒有」
CLOSED = {D(2026, 2, 16), D(2026, 2, 17), D(2026, 2, 18), D(2026, 2, 19), D(2026, 2, 20), D(2026, 12, 25)}


def node(script):
    return json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True, timeout=30).stdout)


def cut(src, start, end):
    i = src.index(start)
    return src[i:src.index(end, i)]


def test_f151_fin_cum_base():
    c = lambda *rows: {(y, q): (None, None, None, None, e) for y, q, e in rows}
    assert export.fin_cum_base(c((2025, 2, Decimal("0.02")), (2026, 2, Decimal("3.87")))) == 0.02          # 4416 型
    assert export.fin_cum_base(c((2025, 2, Decimal("0.10")), (2026, 2, 1))) == 0.1                          # 剛好門檻（畫面不算基期低）
    assert export.fin_cum_base(c((2025, 2, Decimal("0.09")), (2026, 2, 1))) == 0.09
    assert export.fin_cum_base(c((2025, 2, 0), (2026, 2, 1))) == 0.0 and export.fin_cum_base(c((2025, 2, -1.03), (2026, 2, 2.19))) == -1.03
    assert export.fin_cum_base(c((2025, 3, 1), (2026, 2, 1))) is None                                       # 沒有去年同期
    assert export.fin_cum_base(c((2025, 2, None), (2026, 2, 1))) is None and export.fin_cum_base({}) is None
    cum = c((2025, 1, 0.01), (2025, 2, 0.01), (2026, 1, -0.5), (2026, 2, -0.99))
    assert export.fin_stock(cum, "ci", None)["c"] == {"e": -0.99, "ey": -10000.0}                           # fin_stock 回傳不變（eb 在匯出時加）
    assert '"c": {**fb["c"], "eb": fin_cum_base(fin[code])}' in SRC


def test_f153_settle_closed():
    d = D(2026, 12, 17)
    assert export.next_settle(d, export.settle_closed(CLOSED, d)) == {"d": "2027-01-20", "n": 22}
    assert export.next_settle(d, CLOSED) == {"d": "2027-01-20", "n": 23}                                    # 反證：沒加元旦多 1 天
    e = D(2026, 12, 31)
    assert export.next_settle(e, export.settle_closed(CLOSED, e)) == {"d": "2027-01-20", "n": 13}
    f = D(2026, 11, 6)
    assert export.next_settle(f, export.settle_closed(CLOSED, f)) == {"d": "2026-11-18", "n": 8}            # 11 月不變
    with1 = CLOSED | {D(2027, 1, 1)}                                                                       # 已有 2027 官方表
    assert export.next_settle(d, export.settle_closed(with1, d)) == export.next_settle(d, with1)
    assert D(2027, 1, 1) not in CLOSED                                                                     # 不改傳入的集合
    assert "futures[\"stl\"] = next_settle(fd_, settle_closed(closed, fd_))" in SRC


def _etf_rows(c, ch):
    days = [f"2026-08-{d:02d}" for d in range(10, 10 + len(c))]
    return [(D.fromisoformat(d), x, x, x, x, None if x is None else 1500, y) for d, x, y in zip(days, c, ch)], days


def test_f152_etf_gaps_export():
    c = [Decimal("33.75"), Decimal("33.75"), Decimal("32.38"), None, Decimal("32.0"), Decimal("4.1"), Decimal("4.2")]
    ch = [Decimal("0.1"), Decimal("0"), Decimal("0"), None, Decimal("0"), Decimal("0.05"), None]
    rows, days = _etf_rows(c, ch)
    d_, _, _, _, cc, _, hh = zip(*rows)
    # 第 2 列：0、收盤 = 前收 → 不標；第 3 列：0、收盤 ≠ 前收 → 息；第 5 列：前一列無成交 → 不標；第 6 列：漲跌 ≠ 0 但參考價變了（分割）；第 7 列：漲跌 null → 不標
    assert export.etf_gaps(d_, cc, hh, "TWSE") == [days[2], days[5]]
    assert export.etf_gaps(d_, cc, hh, "TPEx") == []                                                      # 上櫃一律不標
    mrows = {D.fromisoformat(days[1]): (100, 120, 5000, 3, 4, None), D.fromisoformat(days[6]): (120, 150, 5000, 4, 2, "X")}
    srows = {D.fromisoformat(days[1]): (1000, 2600, None, None), D.fromisoformat(days[6]): (2600, 5400, None, None)}
    E = export.etf_export("00878", "國泰永續高股息", "TWSE", rows, mrows, srows,
                          D.fromisoformat(days[6]), D.fromisoformat(days[1]), D.fromisoformat(days[6]), D.fromisoformat(days[1]))
    P = E["prices"]
    assert P["d"] == days and P["c"][2] == 32.38 and P["v"] == [2, 2, 2, 0, 2, 2, 2]                          # 張
    assert P["ch"] == [0.1, 0.0, None, None, 0.0, 0.05, None]                                             # 推測除息日的官方 0 → null（不比價）；分割日保留官方漲跌
    assert E["gx"] == [days[2], days[5]]
    assert E["mg"] == {"mb": [None, 120, None, None, None, None, 150], "sb": [None, 4, None, None, None, None, 2],
                       "lb": [None, 3, None, None, None, None, 5]}                                         # 和 prices.d 對齊
    assert E["margin"] == {"d": days[6], "mb": 150, "m1": 30, "m5": 30, "sb": 2, "s1": -2, "sr": 1.33, "mu": 3.0, "nt": "X"}
    assert E["sbl"] == {"d": days[6], "lb": 5, "l1": 3, "l5": 3, "lx": 2.7}                                 # 沒有股數 → 沒有 lp
    T = export.etf_export("006201", "元大富櫃50", "TPEx", rows, {}, {}, None, None, None, None)
    assert "gx" not in T and T["prices"]["ch"][2] == 0.0 and set(T) == {"code", "name", "market", "prices"}  # 上櫃：官方漲跌照傳
    assert 'SITE_DATA_DIR / "etfp" / f"{code}.json"' in SRC and "ETF 個股 {n_etf} 檔" in SRC
    assert "epx, emg, esb, esd = _load_etf_hist(cur)" in SRC


def test_f15_site_source():
    # F15-1
    assert "epsLow(F.c.ey, F.c.eb) ? `基期低（去年同期 ${fmt(F.c.eb, 2)} 元）`" in STK and "年增 ${cy}" in STK
    assert "F.c.eb != null && F.c.eb <= 0 && F.c.e > 0 ? '轉盈'" in STK
    # F15-2
    assert "loadStock(code, E ? 'etfp' : 'stocks')" in STK and "async function loadStock(code, dir = 'stocks')" in APP
    assert "價格未還原除息：配息 ETF 在除息日會向下跳空，不是當天下跌" in STK and "上櫃 ETF 的漲跌可能含除息，本站無法辨識除息日" in STK
    assert "pick(Object.entries(App.latest.etfs?.rows || {}))" in APP and "esc(s.i ?? 'ETF')" in APP
    assert "location.hash = '#/stock/' + tr.dataset.etf" in APP and "location.replace('#/stock/' + code)" in APP
    assert 'href="#/stock/${code}">行情 →</a>' in APP and 'href="#/etf/${code}">持股 →</a>' in STK
    assert "${E ? '' : segHTML('adjSeg'" in STK and "const ic = $('#iC') ? mk('iC', false) : null;" in STK
    assert "${E ? '' : `<button class=\"star" in STK and "if (!E) renderSignals(" in STK and "const ETF_TABS = STOCK_TABS.slice(0, 2);" in STK
    assert ".tbl tr[data-etf]{cursor:pointer}" in CSS
    # F15-3
    spark = cut(APP, "function spreadSpark", "\n}\n")
    assert 'stroke="var(--text2)"' in spark and "--border2" not in spark and 'stroke="var(--text3)" stroke-dasharray="2 2"' in spark
    assert ":root{\n  --bg:#f3f2ee;--card:#ffffff;--card2:#f8f7f3;\n  --text:#1b1b1b;--text2:#5f5f5f;" in CSS           # 淺色 6.39:1
    assert "--bg:#0e0f11;--card:#17181b;--card2:#1e2023;\n    --text:#ececec;--text2:#a7a7a7;" in CSS           # 深色 7.38:1
    # F15-4
    assert "dueTxt(P.due, App.latest.date) + dueWk(P.due, App.latest.date)" in APP


def test_f15_node():
    if not shutil.which("node"):
        print("  （略過 node 部分：沒有 node）")
        return
    fmt = APP[APP.index("const fmt ="):APP.index("\n", APP.index("const sgn ="))]
    md = APP[APP.index("const md ="):APP.index("\n", APP.index("const md ="))]
    due = APP[APP.index("const dueTxt"):APP.index("\n\n", APP.index("const dueTxt"))]
    low = APP[APP.index("const REV_BASE"):APP.index("// 營收年增排行表下一行")]
    cy = cut(STK, "  const cy = ", "  const pc1")
    got = node(f"const isNum = v => typeof v === 'number';\n{fmt}\n{md}\n{due}\n{low}\n"
               f"const cyOf = c => {{ const F = {{c}};\n{cy} return cy; }};\n" + """
const G = ['2026-11-14', '2026-11-29'], line = (P, d) => dueTxt(P, d) + dueWk(P, d);
console.log(JSON.stringify({
  d1106: line(G, '2026-11-06'), d1116: line(G, '2026-11-16'), d1117: line(G, '2026-11-17'), d1201: line(G, '2026-12-01'),
  q4: line(['2027-03-31', '2027-03-31'], '2027-02-01'), q2: line(['2027-08-14', '2027-08-31'], '2027-08-01'),
  q1: line(['2026-05-15', '2026-05-30'], '2026-05-20'),
  old: [dueTxt(G, '2026-11-06'), dueTxt(G, '2026-11-14'), dueTxt(G, '2026-11-20'), dueTxt(G, '2026-12-01')],
  cy: [cyOf({e: 3.87, ey: 19250, eb: 0.02}), cyOf({e: -0.99, ey: -10000, eb: 0.01}), cyOf({e: 15.32, ey: 12666.7, eb: 0.12}),
       cyOf({e: 2, ey: 1900, eb: 0.1}), cyOf({e: 2, ey: 2122.2, eb: 0.09}), cyOf({e: 2.19, ey: null, eb: -1.03}), cyOf({e: 1, ey: null, eb: 0}),
       cyOf({e: -0.1, ey: null, eb: -0.5}), cyOf({e: 1, ey: null, eb: null}), cyOf({e: 49.33, ey: 68.3})],
}));""")
    assert got["d1106"] == "一般業 11/14、金融業 11/29 截止，分別是週六、週日，遇假日可能順延到 11/16、11/30"
    assert got["d1116"] == got["d1106"]                                                    # 11/16（一）不顯示已截止
    assert got["d1117"] == "一般業 11/14 已截止、金融業 11/29 截止，分別是週六、週日，金融業遇假日可能順延到 11/30"
    assert got["d1201"] == "一般業 11/14、金融業 11/29 已截止，分別是週六、週日"
    assert got["q4"] == "03/31 截止，當天是週三" and got["q4"].count("03/31") == 1 and "順延" not in got["q4"]
    assert got["q2"] == "一般業 08/14、金融業 08/31 截止，分別是週六、週二，一般業遇假日可能順延到 08/16"
    assert got["q1"] == "一般業 05/15 已截止、金融業 05/30 截止，分別是週五、週六，金融業遇假日可能順延到 06/01"
    assert got["old"] == ["一般業 11/14、金融業 11/29 截止", "一般業 11/14、金融業 11/29 截止",
                          "一般業 11/14 已截止、金融業 11/29 截止", "一般業 11/14、金融業 11/29 已截止"]   # test_iter14 的 4 種寫法不變
    assert got["cy"] == ["基期低（去年同期 0.02 元）", "基期低（去年同期 0.01 元）", "+12,666.7%", "+1,900.0%", "基期低（去年同期 0.09 元）",
                         "轉盈", "轉盈", "--", "--", "+68.3%"]                                     # 剛好 0.1 不算；本期虧損也寫基期低；舊 JSON 沒有 eb 照舊


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"✅ {name}")
    print("全部通過")
