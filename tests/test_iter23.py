"""第 23 輪（不連網、不連資料庫）：F23-1 個股頁近期表現、F23-2 稅後淨利率、F23-3 版本參數與 serve 快取標頭、F23-4 小修 5 項。
export 的 stock_perf、fin_stock 用自造資料測邊界（120 日要第 121 天、新上市、今天無成交、事件日剛好是基準日、跨年、和選股同一套）；
有 node 時，逐字取出 stock.js、app.js 的函式執行（perfHTML、renderFin、streakTxt、renderWatch）；serve 在 127.0.0.1 的隨機埠啟動後本機請求。"""
import hashlib
import http.client
import json
import re
import shutil
import socket
import subprocess
import sys
import time
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from twstock import export  # noqa: E402

APP = (ROOT / "site" / "app.js").read_text(encoding="utf-8")
STK = (ROOT / "site" / "stock.js").read_text(encoding="utf-8")
CSS = (ROOT / "site" / "app.css").read_text(encoding="utf-8")
HTML = (ROOT / "site" / "index.html").read_text(encoding="utf-8")
README = (ROOT / "README.md").read_text(encoding="utf-8")
SRC = (ROOT / "twstock" / "export.py").read_text(encoding="utf-8")
MAIN = (ROOT / "twstock" / "__main__.py").read_text(encoding="utf-8")


def _weekdays(a, b, skip=()):
    out, d = [], a
    while d <= b:
        if d.weekday() < 5 and d not in skip:
            out.append(d)
        d += timedelta(days=1)
    return out


DAYS = _weekdays(date(2025, 10, 30), date(2026, 11, 13), skip={date(2026, 1, 1)})   # 測試用交易日：週一～五，元旦休市
W52 = DAYS[-1] - timedelta(days=365)                                                  # 2025-11-13（同匯出端 w52_start）
IDX = {d: 100.0 + i for i, d in enumerate(DAYS)}                                      # 指數每天 +1


def _pf(close, days=DAYS, idx=IDX, ev=()):
    """close：該股日線（對齊 days 的最後 len(close) 天，None = 無成交）；ev = [(列索引, 前收, 參考價)]。"""
    d_ = days[-len(close):]
    af = export._adj_factors(len(d_), [{"i": i, "p": p, "r": r} for i, p, r in ev])
    adj = [None if c is None else c * af[i] for i, c in enumerate(close)]
    return {r[0]: r for r in export.stock_perf(d_, adj, days, idx, W52)}, d_, adj


def _ir(b, last=DAYS[-1]):
    return (IDX[last] / IDX[b] - 1) * 100


# ─── F23-1：近期表現 ─────────────────────────────────────
def test_perf_full():
    pf, _, _ = _pf([100.0] * (len(DAYS) - 1) + [110.0])
    assert list(pf) == [5, 20, 60, 120, "y", "w"]                                      # 有完整歷史 → 沒有「上市以來」
    bases = {5: DAYS[-6], 20: DAYS[-21], 60: DAYS[-61], 120: DAYS[-121], "y": date(2025, 12, 31), "w": date(2025, 11, 13)}
    for k, b in bases.items():
        assert pf[k][1] == str(b), (k, pf[k])
        assert pf[k][2] == 10.0 and pf[k][3] == round(_ir(b), 2) and pf[k][4] == round(10 - _ir(b), 2), (k, pf[k])
    # 120 日要第 121 天：只給 120 天（b_days）時算不出來，所以匯出端改用完整交易日序列 p_days
    assert _pf([100.0] * 120 + [110.0], days=DAYS[-121:])[0][120][2] == 10.0
    assert _pf([100.0] * 119 + [110.0], days=DAYS[-120:])[0][120][1:] == [None, None, None, None]
    assert "p_days = sorted({r[0] for rows in prices.values() for r in rows})" in SRC
    assert "stock_perf(d_, [float(c[i]) * af[i] if c[i] is not None else None for i in range(len(d_))], p_days," in SRC


def test_perf_new_listing():
    pf, d_, _ = _pf([78.5] * 76 + [61.69])                                             # 6947 型：77 個交易日
    assert [k for k in pf] == [5, 20, 60, 120, "y", "w", "s"]
    for k in (120, "y", "w"):
        assert pf[k][2:] == [None, None, None], pf[k]                                  # 上市前的區間：本股、指數、差距都是 --
    assert pf["s"] == ["s", str(d_[0]), round((61.69 / 78.5 - 1) * 100, 2), round(_ir(d_[0]), 2),
                       round((61.69 / 78.5 - 1) * 100 - _ir(d_[0]), 2)]                # 從第一個成交日的收盤起算
    assert pf[60][2] is not None
    # 7827 型：120 日的基準日早於第一個成交日 1 天 → --；剛好是第一個成交日 → 有值
    assert _pf([50.0] * 119 + [55.0])[0][120][2] is None and "s" in _pf([50.0] * 119 + [55.0])[0]
    assert _pf([50.0] * 120 + [55.0])[0][120][2] == 10.0
    # 前幾列無成交：上市以來從第一個「有成交」的日子起算
    pf, d_, _ = _pf([None, None] + [40.0] * 30 + [44.0])
    assert pf["s"][1] == str(d_[2]) and pf["s"][2] == 10.0


def test_perf_no_trade_and_index():
    close = [100.0] * (len(DAYS) - 8) + [105.0] + [None] * 7                           # 4406 型：最後成交在 5 日基準日之前
    pf, d_, adj = _pf(close)
    assert pf[5][2] == 0.0 and pf[5][3] == round(_ir(DAYS[-6]), 2) and pf[5][4] == round(-_ir(DAYS[-6]), 2)   # 照算 0%（D35-2）
    assert pf[20][2] == 5.0                                                            # 用最後成交的收盤
    idx = {d: v for d, v in IDX.items() if d != DAYS[-21]}                             # 基準日沒有指數 → 指數、差距 --，本股照列
    pf, _, _ = _pf([100.0] * (len(DAYS) - 1) + [110.0], idx=idx)
    assert pf[20][2:] == [10.0, None, None] and pf[5][3] is not None
    # 差距用未四捨五入的值相減（同 rs20）：10.004 − 5.006 = 4.998 → 5.0，不是 10.0 − 5.01 = 4.99
    idx = {**{d: 100.0 for d in DAYS}, DAYS[-1]: 105.006}
    pf, _, _ = _pf([100.0] * (len(DAYS) - 1) + [110.004], idx=idx)
    assert pf[5][2:] == [10.0, 5.01, 5.0], pf[5]


def test_perf_event_and_year():
    i = DAYS.index(date(2025, 12, 31))                                                 # 6488 型：除息日剛好是今年以來的基準日
    close = [100.0] * i + [96.0] * (len(DAYS) - i - 1) + [114.0]
    pf, _, _ = _pf(close, ev=[(i, 100.0, 95.0)])
    assert pf["y"][1] == "2025-12-31" and pf["y"][2] == 18.75                          # 基準 = 12/31 實際收盤 96（事件當天係數 1），不是 96 × 0.95
    assert pf["w"][2] == 20.0                                                          # 52 週基準在事件前：100 × 0.95 = 95
    # 跨年：新年第一個交易日的今年以來 = 1 日報酬
    days = _weekdays(date(2025, 10, 30), date(2026, 1, 2), skip={date(2026, 1, 1)})
    d_ = days
    adj = [100.0] * (len(days) - 1) + [103.0]
    pf = {r[0]: r for r in export.stock_perf(d_, adj, days, IDX, days[-1] - timedelta(days=365))}
    assert pf["y"][1] == "2025-12-31" and pf["y"][2] == 3.0 and pf["y"][3] == round((IDX[days[-1]] / IDX[days[-2]] - 1) * 100, 2)
    assert pf["w"][2] is None and "s" in pf                                            # 全市場資料不到 52 週時沒有 52 週


def test_perf_same_as_screen():
    # 和選股同一套：pf 的 5／20／60 日 = price_stats 的 r5／r20／r60（price_stats 用 b_days 的 120 天），20／60 日差距 = rs20／rs60
    close = [None if i % 17 == 5 else round(50 + 10 * ((i * 37) % 23) / 23 + i * 0.03, 2) for i in range(len(DAYS))]
    close[-1] = None                                                                   # 今天無成交
    pf, d_, adj = _pf(close, ev=[(100, 60.0, 57.5), (200, 55.0, 27.6)])
    st = export.price_stats(d_, adj, [1e8] * len(d_), DAYS[-120:], IDX)
    for n in (5, 20, 60):
        assert pf[n][2] == st[f"r{n}"], (n, pf[n], st)
    for n in (20, 60):
        assert pf[n][4] == st[f"rs{n}"], (n, pf[n], st)
    assert "raw[n] = period_return(d_, adj, lc, days[-1 - n] if len(days) > n else None)" in SRC        # price_stats 也用同一個函式
    assert "ir = index_return(idx, days[-1 - n] if len(days) > n else None, days[-1])" in SRC
    assert "pf" not in export.SCREEN_KEYS


def test_perf_export_source():
    # 停牌、下市（最後一列不是資料日）或從沒成交 → 不輸出 pf（和 latest.stocks 同條件）；ETF 的 etfp/ 不加
    assert 'idx_close[info["market"]], w52_start)} if d_[-1] == latest_date and any(x is not None for x in c) else {}),' in SRC
    assert SRC.index('"pf": stock_perf(') < SRC.index("if d_[-1] != latest_date:")
    assert "pf" not in SRC[SRC.index("def etf_export"):SRC.index("def _load_holdings")]
    assert "PF_DAYS = (5, 20, 60, 120)" in SRC


# ─── F23-2：稅後淨利率 ───────────────────────────────────
def _cum(rows):
    """rows = {(年, 季): (單季營收, 單季淨利)} → 累計值（毛利、營益用 0，EPS 用 1）。"""
    out, acc = {}, {}
    for (y, q), (rev, net) in sorted(rows.items()):
        a = acc.get(y, (0, 0)) if q > 1 else (0, 0)
        acc[y] = (None if rev is None or a[0] is None else a[0] + rev, None if net is None or a[1] is None else a[1] + net)
        out[(y, q)] = (acc[y][0], 0, 0, acc[y][1], q)
    return out


def test_net_margin():
    rows = {(2025, q): (5000000, 700000) for q in (1, 2)} | {(2025, 3): (6000000, 846000), (2025, 4): (5000000, 500000),
            (2026, 1): (5000000, 650000), (2026, 2): (5500000, 700000), (2026, 3): (6142510, 898565)}
    f = export.fin_stock(_cum(rows), "ci", None)
    assert len(f["nm"]) == len(f["q"]) == 7 and f["nm"][-1] == 14.6 and f["nm"][2] == 14.1   # 2421 型：26Q3 14.6%、去年同季 14.1%
    assert len(f["q"][-1]) == 7 and f["c"] == {"e": 3, "ey": 0.0}                     # q、c 不變
    for t in ("fh", "basi", "bd", "ins", "mim"):
        assert "nm" not in export.fin_stock(_cum(rows), t, None)                        # 只有一般業
    assert export.fin_stock(_cum({(2026, 1): (37, -15239)}), "ci", None)["nm"] == [-41186.5]   # 極端值照實（3521 型）
    assert export.fin_stock(_cum({(2026, 1): (0, 100)}), "ci", None)["nm"] == [None]           # 營收 ≤ 0
    assert export.fin_stock(_cum({(2026, 1): (None, 100)}), "ci", None)["nm"] == [None]        # 營收 NULL（銀行型）
    assert export.fin_stock(_cum({(2026, 1): (100, None)}), "ci", None)["nm"] == [None]        # 淨利 NULL
    # 上一季缺 → 單季淨利 None（不以累計頂替）
    c = _cum({(2026, 1): (100, 10), (2026, 2): (100, 20), (2026, 3): (100, 30)})
    del c[(2026, 2)]
    assert export.fin_stock(c, "ci", None)["nm"] == [10.0, None]


# ─── node：stock.js、app.js ──────────────────────────────
def _grab(src, name):
    """取出頂層 function 或 const（const 取到去掉行尾註解後結尾為「;」的那一行）。"""
    m = re.search(rf"^(?:async )?function {name}\(", src, re.M)
    if m:
        i, n = src.index("{", src.index(")", m.start())), 0
        for j in range(i, len(src)):
            n += {"{": 1, "}": -1}.get(src[j], 0)
            if n == 0:
                return src[m.start():j + 1]
    m = re.search(rf"^const {name}\b", src, re.M)
    assert m, name
    lines = src[m.start():].splitlines()
    k = next(i for i, l in enumerate(lines) if re.sub(r"\s+//[^'`]*$", "", l).rstrip().endswith(";"))
    return "\n".join(lines[:k + 1])


AT = "if (!Array.prototype.at) Array.prototype.at = function (i) { return this[i < 0 ? this.length + i : i]; };\n"   # node 14


def _node(js):
    node = shutil.which("node")
    if not node:
        print("  （沒有 node，略過執行）")
        return None
    return json.loads(subprocess.run([node, "-e", AT + js], capture_output=True, text=True, check=True).stdout)


def test_perf_html():
    js = "\n".join(_grab(APP, n) for n in ("fmt", "sgn", "cls", "md", "noteHTML")) + "\n" + \
        "\n".join(_grab(STK, n) for n in ("PF_NAME", "perfHTML")) + """
const App = { latest: { date: '2026-11-13' } };
const full = [[5, '2026-11-06', 7.2, 10.01, -2.81], [20, '2026-10-14', -21.64, -10.18, -11.46], [60, '2026-08-14', -8.22, -4.66, -3.56],
  [120, '2026-05-20', -3.11, 9.13, -12.25], ['y', '2025-12-31', -13.06, 50.79, -63.86], ['w', '2025-11-13', -24.17, 56.52, -80.69]];
const fresh = [[5, '2026-11-06', -1.45, 10.01, -11.46], [120, '2026-05-20', null, null, null], ['y', '2025-12-31', null, null, null],
  ['w', '2025-11-13', null, null, null], ['s', '2026-07-23', -21.42, -2.62, -18.8]];
console.log(JSON.stringify([perfHTML(full, 'TWSE', null), perfHTML(fresh, 'TWSE', null), perfHTML(full, 'TPEx', '2026-11-05'), perfHTML(fresh, 'TPEx', null)]));"""
    o = _node(js)
    if o is None:
        return
    a, b, c, d = o
    assert "<h2>近期表現</h2>" in a and "<th>區間</th><th>本股</th><th>加權指數</th><th>差距</th>" in a and "至 11/13</span>" in a
    assert '<tr><td>20 日</td><td class="num dn">-21.64%</td><td class="num dn">-10.18%</td><td class="num dn">-11.46</td></tr>' in a
    assert '<td>今年以來</td><td class="num dn">-13.06%</td><td class="num up">+50.79%</td>' in a and "上市以來" not in a
    assert "還原價（含股息）；指數不含股息，長區間的差距會偏向個股" in a and "今年以來從 2025-12-31 收盤起算；52 週從 2025-11-13 收盤起算" in a
    assert '<tr><td>120 日</td><td class="num flat">--</td><td class="num flat">--</td><td class="num flat">--</td></tr>' in b
    assert "<td>上市以來<span>07/23 起</span></td>" in b and "不是承銷價" in b and "本站第一個成交日 2026-07-23" in b
    assert "<th>櫃買指數</th>" in c and "至 11/13，本股最後成交 11/05</span>" in c and "上櫃以來<span>07/23 起</span>" in d
    # 位置：走勢分頁 K 線卡之後、技術面訊號之前；不在頂端指標卡（test_iter13 的統計卡區段）；ETF 沒有 pf
    assert "${data.pf ? perfHTML(data.pf, data.market, noTrade ? P.d[lt] : null) : ''}" in STK
    assert STK.index('id="mC"') < STK.index("perfHTML(data.pf") < STK.index('id="sigTitle"')
    assert "table.pf-tbl{max-width:560px}.pf-tbl td span{display:block;" in CSS


def test_fin_card():
    js = "\n".join(_grab(APP, n) for n in ("fmt", "sgn", "cls", "isNum", "REV_BASE", "epsLow", "noteHTML")) + "\n" + \
        "\n".join(_grab(STK, n) for n in ("qName", "qShort", "renderFin")) + """
const box = {}, $ = s => (box[s] = box[s] || {});
const q = [[202503, 2.55, 10, 31.3, 15.6, 6000000, 2.0], [202602, 2.9, 12, 32, 17, 5500000, 2.6], [202603, 3.15, 23.5, 32.7, 18.4, 6142510, 2.55]];
const F = (t, nm) => ({ t, q, c: { e: 7.93, ey: 40.4 }, e4: 10.22, e4p: 7.25, ...(nm ? { nm } : {}) });
const out = [F('ci', [14.1, 12.7, 14.6]), F('ci'), F('fh'), F('ci', [null, 12.7, null]), { ...F('ci', [12.7, 14.6]), q: q.slice(1) }]
  .map(f => { renderFin(f); return box['#finBox'].innerHTML; });
console.log(JSON.stringify(out));"""
    o = _node(js)
    if o is None:
        return
    card = lambda h: re.findall(r'<div class="l">([^<]*)</div><div class="v num [^"]*" style="font-size:16px">([^<]*)</div><div class="s">([^<]*)</div>', h)
    a = card(o[0])
    assert [x[0] for x in a] == ["單季 EPS", "累計 EPS", "毛利率", "營益率", "稅後淨利率", "近 4 季 EPS"], a   # 營益率之後，1024 寬 3＋3
    assert a[4] == ("稅後淨利率", "14.6%", "去年同季 14.1%")
    assert "稅後淨利率" not in [x[0] for x in card(o[1])] and "稅後淨利率" not in [x[0] for x in card(o[2])]   # 舊 JSON、金融業不顯示
    assert card(o[3])[4] == ("稅後淨利率", "--", "去年同季 --")                       # 一般業但沒有值 → --
    assert card(o[4])[4] == ("稅後淨利率", "14.6%", "去年同季 --")                    # 去年同季不在近 8 季內
    assert "單季 = 本季累計 − 上一季累計（第 4 季 = 全年 − 前三季）" in o[0]
    assert "稅後淨利率（只有一般業）= 單季歸屬母公司業主的淨利 ÷ 單季營收，不含非控制權益；部分網站用合併總淨利，數字會不同。" in o[0]


def test_small_fixes():
    o = _node(_grab(APP, "streakTxt") + "\nconsole.log(JSON.stringify([30, -30, 29, -3, 0, undefined].map(streakTxt)));")
    if o is not None:
        assert o == ["買30+", "賣30+", "買29", "賣3", "--", "--"], o                    # F23-4d
    assert "const streakTxt = v => v ? (v > 0 ? '買' : '賣') + Math.abs(v) + (Math.abs(v) >= 30 ? '+' : '') : '--';" in APP
    # F23-4b：日 K 照舊在下方，週／月 K 在上方；ETF 推測標記同規則；標記文字不變
    assert "const mkPos = mode === '日' ? { position: 'belowBar', shape: 'arrowUp' } : { position: 'aboveBar', shape: 'arrowDown' };" in STK
    assert STK.count("{ time: T[i], ...mkPos,") == 2 and "position: 'belowBar', shape: 'arrowUp'," not in STK
    # F23-4e：「近期新訊號 →」和站內「看排行 →」同寫法
    assert '<div class="s-hl"><a class="muted small" href="#/rank/hl">近期新訊號 →</a>' in STK
    assert '<a class="muted small" href="#/rank/${rk}">看排行 →</a>' in APP
    # F23-4a：≤ 480 px 時標籤在名稱格下方、隱藏標籤欄；1024 照舊（hl-sub 不顯示）
    hl = APP[APP.index("async function renderHl()"):APP.index("// ─── 第 8 輪 F8-2")]
    assert "<span>${x.code} ${esc(x.i)}</span><div class=\"hl-sub\">${x.hl.map(hlTag).join('')}</div></td>" in hl
    assert '<td class="hl-tags">${x.hl.map(hlTag).join(\'\')}</td>' in hl
    assert ".hl-sub{display:none}" in CSS
    assert "@media (max-width:480px){.tbl th.hl-th,.tbl td.hl-tags{display:none}.tbl td.nm .hl-sub{display:block;white-space:normal}" in CSS


def test_watch_etf_only():
    names = ["fmt", "pfmt", "sgn", "cls", "pctCell", "yi", "esc", "md", "streakTxt", "holdTag", "alertBadge",
             "segHTML", "onSeg", "flowNote", "stockTable", "spanSeg", "onEtfRow", "renderWatch", "etfWatchTable"]
    latest = {"date": "2026-11-13", "flow_date": "2026-11-13", "holdings": {"00981A": {}},
              "stocks": {"2330": {"n": "台積電", "i": "半導體", "c": 1460, "p": 1.2, "tv": 300.5, "f1": 10, "t1": 1, "d1": 0, "n1": 11, "fs": 2, "ts": 30, "s": 2}},
              "etfs": {"rows": {"0050": {"n": "元大台灣50", "m": "TWSE", "c": 70.1, "ch": 0.2, "p": 0.29, "v": 50000, "tv": 35.1},
                                "00981A": {"n": "主動統一台股增長", "m": "TWSE", "c": 15.1, "ch": 0.1, "p": 0.67, "v": 90000, "tv": 13.6}}}}
    js = "\n".join(_grab(APP, n) for n in names) + f"""
const App = {{ latest: {json.dumps(latest, ensure_ascii=False)}, watch: new Set() }};
const view = {{ innerHTML: '', addEventListener() {{}} }};
const $ = s => s === '#view' ? view : view.innerHTML.includes(`id="${{s.slice(1)}}"`) ? {{ addEventListener() {{}} }} : null;
const localStore = (k, f) => f, onRowClick = () => {{}};
const out = {{}};
for (const [k, w] of Object.entries({{ etf: ['0050', '00981A'], both: ['2330', '0050'], stock: ['2330'], none: [] }})) {{
  App.watch = new Set(w); view.innerHTML = ''; renderWatch(); out[k] = view.innerHTML;
}}
console.log(JSON.stringify(out));"""
    o = _node(js)
    if o is None:
        return
    e = o["etf"]
    assert e.count("<h2>") == 1 and "<h2>自選 ETF</h2>" in e and "<h2>ETF</h2>" not in e                    # 只有一個標題列
    assert "存在這個瀏覽器裡，換裝置不會同步。當日行情；成交量為張、成交額為億元</span>" in e
    assert e.index("自選 ETF") < e.index('data-etf="0050"') and "rspanSeg" not in e
    assert o["both"].count("<h2>") == 2 and "<h2>自選</h2>" in o["both"] and "<h2>ETF</h2>" in o["both"]   # 股票＋ETF 照舊
    assert "<h2>自選 ETF</h2>" not in o["stock"] + o["none"] and "買30+" in o["stock"]


# ─── F23-3：版本參數、serve 快取標頭 ─────────────────────
def test_version_hash():
    v = {f: hashlib.sha1((ROOT / "site" / f).read_bytes()).hexdigest()[:8] for f in ("app.css", "app.js", "stock.js")}
    want = [f'<link rel="stylesheet" href="app.css?v={v["app.css"]}">', f'<script src="app.js?v={v["app.js"]}" defer></script>',
            f'<script src="stock.js?v={v["stock.js"]}" defer></script>']
    miss = [w for w in want if w not in HTML]
    assert not miss, "site/index.html 的版本參數和檔案內容不符（改了 js／css 要更新），請把這 3 行換成：\n" + "\n".join(want)
    assert len(re.findall(r'(?:href|src)="(?:app\.css|app\.js|stock\.js)[?"]', HTML)) == 3      # 每個檔只引用一次
    assert "plotly.js-basic-dist-min@2.35.2" in HTML and "lightweight-charts@4.2.0" in HTML     # CDN 照舊


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_serve_cache():
    assert 'self.send_header("Cache-Control", "no-cache")' in MAIN and "functools.partial(Handler, directory=str(SITE_DIR))" in MAIN
    port = _free_port()                                    # 系統配的空埠（不用 8000、8001）
    p = subprocess.Popen([sys.executable, "-m", "twstock", "serve", "--port", str(port), "--no-browser"], cwd=ROOT,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        def get(path, headers=None):
            for _ in range(50):
                try:
                    c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
                    c.request("GET", path, headers=headers or {})
                    r = c.getresponse()
                    return r.status, dict(r.getheaders()), r.read()
                except ConnectionRefusedError:
                    time.sleep(0.1)
            raise AssertionError("serve 沒有啟動")
        st, h, body = get("/")
        assert st == 200 and h.get("Cache-Control") == "no-cache" and b"app.js?v=" in body
        v = hashlib.sha1((ROOT / "site" / "app.js").read_bytes()).hexdigest()[:8]
        st, h, body = get(f"/app.js?v={v}")
        assert st == 200 and h.get("Cache-Control") == "no-cache" and body == (ROOT / "site" / "app.js").read_bytes()
        st, h2, _ = get("/app.js", {"If-Modified-Since": h["Last-Modified"]})
        assert st == 304 and h2.get("Cache-Control") == "no-cache"                    # 沒改的檔回 304
    finally:
        p.terminate()
        p.wait(timeout=10)


# ─── 用詞 ───────────────────────────────────────────────
def test_no_advice_words():
    seg = _grab(STK, "PF_NAME") + _grab(STK, "perfHTML") + _grab(APP, "streakTxt")
    seg += "".join(l for l in STK.splitlines() if "稅後淨利率" in l or "mkPos" in l or "s-hl" in l)
    seg += APP[APP.index("async function renderHl()"):APP.index("// ─── 第 8 輪 F8-2")] + _grab(APP, "renderWatch")
    seg += "".join(l[l.index("第 23 輪"):] for l in README.splitlines() if "第 23 輪" in l)
    assert seg.count("第 23 輪") >= 4, seg.count("第 23 輪")                        # README 4 段都有取到
    for w in ("買進", "賣出", "反彈", "見底", "買點", "超賣", "超買", "推薦", "強勢股", "飆股", "勝率",
              "利多", "利空", "看多", "看空", "轉強", "轉弱",
              "跑贏", "跑輸", "強於大盤", "弱於大盤", "贏過", "輸給", "領先", "落後", "抗跌", "超額報酬", "獲利能力佳", "惡化"):
        assert w not in seg, w


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_") and callable(f):
            print("==", n); f()
    print("全部通過")
