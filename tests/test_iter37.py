"""第 37 輪（不連網、不連資料庫）：F37-1 個股 JSON 的 band、F37-2～4 基本面分頁河流圖卡、F37-5 用詞。
有 node 時逐字取出 app.js、stock.js 的程式執行（node 14 可跑）。test_real_data 讀已匯出的 site/data（沒有 band 就略過）。"""
import hashlib
import json
import math
import re
import shutil
import subprocess
import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from twstock import export  # noqa: E402

SITE = ROOT / "site"
APP = (SITE / "app.js").read_text(encoding="utf-8")
STK = (SITE / "stock.js").read_text(encoding="utf-8")
CSS = (SITE / "app.css").read_text(encoding="utf-8")
HTML = (SITE / "index.html").read_text(encoding="utf-8")
EXP = (ROOT / "twstock" / "export.py").read_text(encoding="utf-8")
README = (ROOT / "README.md").read_text(encoding="utf-8")
D0 = date(2026, 1, 5)


def _grab(src, name):
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


def _node(js):
    node = shutil.which("node")
    if not node:
        print("  （沒有 node，略過執行）")
        return None
    return json.loads(subprocess.run([node, "-e", js], capture_output=True, text=True, check=True).stdout)


def _rows(n, close=100.0, pe=20.0, pb=2.0):
    """n 天的 (日期, 收盤, 本益比, 淨值比)；EPS = 5、每股淨值 = 50。"""
    return [(D0 + timedelta(days=i), close, pe, pb) for i in range(n)]


# ─── F37-1：band_series ──────────────────────────────────
def test_band_basic():
    rows = _rows(130)
    rows[60] = (rows[60][0], 110.0, 20.0, 2.0)                       # EPS 5 → 5.5：開新段
    b = export.band_series(list(reversed(rows)))                     # 不必排序
    assert b["pe"]["s"] == [["2026-01-05", 5.0], [str(rows[60][0]), 5.5], [str(rows[61][0]), 5.0]], b["pe"]["s"]
    assert b["pe"]["n"] == 130 and b["pe"]["k"] == [20.0] * 5 and b["pb"]["s"][0] == ["2026-01-05", 50.0]
    assert export.BAND_PCT == (10, 25, 50, 75, 90) and export.BAND_TOL == (0.005, 0.012) and export.BAND_SEG_MAX == 24


def test_band_tolerance():
    # 本益比 20：門檻 max(0.5%, 0.012 ÷ 20 = 0.06%) = 0.5%；EPS 5 → 5.02（+0.4%）不切、5.03（+0.6%）切
    rows = _rows(120)
    rows[10] = (rows[10][0], 100.4, 20.0, 2.0)
    rows[20] = (rows[20][0], 100.6, 20.0, 2.0)
    s = export.band_series(rows)["pe"]["s"]
    assert [x[1] for x in s] == [5.0, 5.03, 5.0], s
    # 淨值比 0.5：門檻 0.012 ÷ 0.5 = 2.4%；每股淨值 200 → 204（+2%）不切、205（+2.5%）切
    rows = _rows(120, close=100.0, pb=0.5)
    rows[10] = (rows[10][0], 102.0, 20.0, 0.5)
    rows[20] = (rows[20][0], 102.5, 20.0, 0.5)
    assert [x[1] for x in export.band_series(rows)["pb"]["s"]] == [200.0, 205.0, 200.0]
    # 比較的是這一段已輸出的值（不是前一天）：慢慢漂移超過門檻才切
    rows = [(D0 + timedelta(days=i), 100.0 * (1 + 0.0005 * i), 20.0, 2.0) for i in range(120)]
    s = export.band_series(rows)["pe"]["s"]
    assert all(abs(c / v / x - 1) <= 0.005 for (d, c, v, _) in rows for x in [next(y[1] for y in reversed(s) if y[0] <= str(d))]), s
    assert 8 <= len(s) <= export.BAND_SEG_MAX


def test_band_sig_digits():
    rows = _rows(120, close=24.35, pe=69.57)                         # EPS 0.35001…：4 位有效數字，不是 2 位小數
    assert export.band_series(rows)["pe"]["s"] == [["2026-01-05", 0.35]]
    rows = _rows(120, close=7860.0, pe=50.64, pb=33.03)
    b = export.band_series(rows)
    assert b["pe"]["s"][0][1] == 155.2 and b["pb"]["s"][0][1] == 238.0


def test_band_no_trade_and_loss():
    rows = _rows(140)
    for i in (5, 6, 7):
        rows[i] = (rows[i][0], None, 30.0, 3.0)                      # 無成交：沿用前一段，不切
    for i in range(50, 60):
        rows[i] = (rows[i][0], 100.0, None, 2.0)                     # 虧損：None 段
    rows[60] = (rows[60][0], None, 25.0, 2.0)                        # 轉盈第一天無成交：等到有收盤才開段
    b = export.band_series(rows)
    assert b["pe"]["s"] == [["2026-01-05", 5.0], [str(rows[50][0]), None], [str(rows[61][0]), 5.0]], b["pe"]["s"]
    assert b["pe"]["n"] == 130 and len(b["pb"]["s"]) == 1
    rows[140 - 1] = (rows[-1][0], 100.0, 0.0, 2.0)                   # ≤ 0 也是 None
    assert export.band_series(rows)["pe"]["s"][-1] == [str(rows[-1][0]), None]


def test_band_percentile():
    # 最近序位法：由小到大第 ceil(P × n ÷ 100) 個
    vals = [float(v) for v in range(1, 201)]                         # 1～200
    rows = [(D0 + timedelta(days=i), v * 5, v, 2.0) for i, v in enumerate(vals)]
    k = export.band_series(rows)["pe"]["k"]
    assert k == [20.0, 50.0, 100.0, 150.0, 180.0], k
    vals = [float(v) for v in range(1, 122)]                         # n = 121
    rows = [(D0 + timedelta(days=i), v * 5, v, 2.0) for i, v in enumerate(vals)]
    assert export.band_series(rows)["pe"]["k"] == [vals[math.ceil(p * 121 / 100) - 1] for p in (10, 25, 50, 75, 90)] == [13.0, 31.0, 61.0, 91.0, 109.0]
    # 只計 > 0；k 落在 val 的一年最低、最高之間
    rows += [(D0 + timedelta(days=200 + i), 100.0, None, 2.0) for i in range(30)]
    b, v = export.band_series(rows), export.stock_valuation({"pe": vals}, {"pe": 60.0})
    assert b["pe"]["n"] == 121 and v["pe"][1] <= b["pe"]["k"][0] and b["pe"]["k"][4] <= v["pe"][2]
    rows += [(D0 + timedelta(days=300 + i), 100.0, 0.0, 2.0) for i in range(30)]          # QA37：官方 0 也不計入 k、n
    assert export.band_series(rows)["pe"]["n"] == 121 and export.band_series(rows)["pe"]["k"] == [13.0, 31.0, 61.0, 91.0, 109.0]
    rows = [(D0 + timedelta(days=i), v * 5, float(v), 2.0) for i, v in enumerate(range(1, 243))]   # QA37：窗口 242 天全部計入
    assert export.band_series(rows)["pe"]["n"] == 242 and export.band_series(rows)["pe"]["k"] == [25.0, 61.0, 121.0, 182.0, 218.0]


def test_band_min_days_and_cap():
    assert export.band_series(_rows(119)) is None                       # 不足 VAL_MIN
    rows = _rows(119) + [(D0 + timedelta(days=200), 100.0, None, 2.0)]
    assert set(export.band_series(rows)) == {"pb"}                      # 本益比 119 天、淨值比 120 天
    # 段數上限：每天跳動 → 超過 BAND_SEG_MAX 不輸出該指標
    noisy = [(D0 + timedelta(days=i), 100.0 + (i % 2) * 5, 20.0, (100.0 + (i % 2) * 5) / 50) for i in range(130)]   # EPS 5 ↔ 5.25 每天換、每股淨值不變
    assert set(export.band_series(noisy)) == {"pb"} and len(export.band_series(noisy)["pb"]["s"]) == 1
    ok = [(D0 + timedelta(days=i), 100.0 + (i // 6 % 2) * 5, 20.0, 2.0) for i in range(6 * 24)]   # 剛好 24 段
    assert len(export.band_series(ok)["pe"]["s"]) == 24


def test_load_valuation_same_query():
    """_load_valuation：仍是 2 個查詢；val 不變；第 4 個回傳值 = band_series。"""
    days = [D0 + timedelta(days=i) for i in range(130)]

    class Cur:
        def __init__(self):
            self.sql = []

        def execute(self, sql, *a):
            self.sql.append(sql)
            if "DISTINCT TOP" in sql:
                return iter([(d,) for d in reversed(days)])
            rows = [(d, "TWSE", "1111", Decimal("20.00"), Decimal("2.00"), Decimal("3.00"), Decimal("100.00")) for d in days]
            rows += [(d, "TPEx", "2222", None, Decimal("1.50"), None, None if i % 9 == 0 else Decimal("30.00")) for i, d in enumerate(days)]
            return iter(rows)
    cur = Cur()
    mv, sv, last, band = export._load_valuation(cur, {"1111": 1000})
    assert len(cur.sql) == 2 and all(s.lstrip().upper().startswith("SELECT") for s in cur.sql)
    assert last == days[-1] and sv["1111"] == export.stock_valuation({"pe": [20.0] * 130, "pb": [2.0] * 130, "dy": [3.0] * 130}, {"pe": 20.0, "pb": 2.0, "dy": 3.0})
    assert band["1111"]["pe"]["s"] == [[str(days[0]), 5.0]] and band["2222"] == {"pb": {"s": [[str(days[1]), 20.0]], "k": [1.5] * 5, "n": 130}}
    assert export._load_valuation(type("E", (), {"execute": lambda self, *a: iter([])})()) == (None, {}, None, {})


def test_export_wiring():
    assert "valuation, stock_val, val_date, stock_band = _load_valuation(cur, shares)" in EXP
    line = next(l for l in EXP.splitlines() if '"band"' in l)
    assert '**({"band": {"d": str(val_date), **stock_band[code]}} if stock_band.get(code) and not cap else {}),' in line   # 和 val 同一個股本變動判斷
    i = EXP.index('**({"val": {"d": str(val_date)')
    assert i < EXP.index(line) < EXP.index('"dv": dividends(d_, c, ev')                                                   # 個股 JSON，val 之後
    assert EXP.count('"band"') == 1 and "band" not in export.SCREEN_KEYS                                    # 只進 stocks/，不進 screen.json、etfp/


# ─── F37-2～4：前端 ─────────────────────────────────────
HELPERS = "\n".join(_grab(APP, n) for n in ("esc", "fmt", "pfmt", "md", "noteHTML", "segHTML"))
BAND = "\n".join(_grab(STK, n) for n in ("disposeKCharts", "BAND_PCT", "BAND_NM", "bandView", "BAND_NOTE", "bandHTML", "renderBand"))
MOCK = r"""
let charts = [], store = {};
const localStore = (k, f, v) => v === undefined ? (k in store ? store[k] : f) : (store[k] = v, f);
const css = n => n === '--blue' ? '#00f' : n === '--text' ? '#111' : '#888', created = [], els = {};
const $ = s => s in els ? els[s] : (els[s] = { innerHTML: '', textContent: '' });
const window = { LightweightCharts: { createChart: (el, opt) => {
  const c = { el, opt, ser: [], kinds: [], addLineSeries(o) { const s = { o, setData(d) { this.data = d; } }; this.ser.push(s); this.kinds.push('line'); return s; },
    timeScale: () => ({ fitContent() {} }), subscribeCrosshairMove(f) { this.cb = f; }, remove() { this.removed = true; } };
  created.push(c); return c; } } };
const D = ['2026-11-13', '2026-11-16', '2026-11-17', '2026-11-18', '2026-11-19', '2026-11-20'];
const mk = (o = {}) => Object.assign({ industry: '半導體', fund: { pe: 20, pb: 2, date: '2026-11-20' }, val: { d: '2026-11-20', pe: [38, 15, 30], pb: [50, 1, 3] },
  prices: { d: D, c: [95, 100, null, 104, 102, 100] }, ev: [{ d: '2026-11-18', t: '息', p: 104, r: 100 }],
  band: { d: '2026-11-19', pe: { s: [['2026-11-16', 5], ['2026-11-18', null], ['2026-11-19', 5.1]], k: [10, 12, 15, 18, 20], n: 242 },
          pb: { s: [['2026-11-13', 50]], k: [1.5, 1.8, 2, 2.2, 2.5], n: 242 } } }, o);
"""


def test_js_states():
    js = HELPERS + "\n" + BAND + MOCK + r"""
const out = {};
out.cap = bandHTML(mk({ band: undefined }), '09/29 減資，官方值可能尚未調整');
out.none = bandHTML(mk({ band: undefined }), '');
out.card = bandHTML(mk(), '');
out.view = [mk(), mk({ fund: { pe: null, pb: 0.8, date: 'x' } }), mk({ band: { d: 'x', pb: mk().band.pb } }), mk({ band: { d: 'x', pe: mk().band.pe } })].map(bandView);
store.bandV = 'pb'; out.view2 = [mk(), mk({ band: { d: 'x', pe: mk().band.pe } })].map(bandView); store = {};
const msg = (d, k) => { renderBand(d, k); return els['#bandBox'].innerHTML; };
out.loss = msg(mk({ fund: { pe: null, pb: 2, date: '2026-11-20' } }), 'pe');
out.short = msg(mk({ band: { d: 'x', pb: mk().band.pb } }), 'pe');
out.nopb = msg(mk({ fund: { pe: 20, pb: null, date: '2026-11-20' } }), 'pb');
out.n = created.length;
console.log(JSON.stringify(out));"""
    o = _node(js)
    if o is None:
        return
    assert o["cap"].endswith('<div class="muted small">09/29 減資，官方值可能尚未調整；股本變動後 90 天內不畫河流圖</div></section>') and "bandSeg" not in o["cap"]
    assert "近一年有官方本益比、淨值比的天數都不足 120 天，不畫河流圖" in o["none"] and "bandSeg" not in o["none"]
    assert '<div class="seg" id="bandSeg"><button data-v="pe" class="on">本益比</button><button data-v="pb" class="">淨值比</button></div>' in o["card"]
    assert o["card"].startswith('<section class="sec card"><div class="sec-h"><h2 id="bandT">本益比河流圖（近一年）</h2>') and '<div id="bandBox"></div>' in o["card"]
    assert o["view"] == ["pe", "pb", "pb", "pe"], o["view"]          # 今天虧損、沒有 band.pe → 淨值比；沒有 band.pb → 本益比
    assert o["view2"] == ["pb", "pe"], o["view2"]                    # 記住淨值比；淨值比畫不出來時改本益比
    assert o["loss"] == '<div class="muted small">近 4 季 EPS ≤ 0，官方不計算本益比</div>'
    assert o["short"] == '<div class="muted small">近一年有官方本益比的天數不足 120 天，或反推值變動過於頻繁，不畫河流圖</div>'
    assert o["nopb"] == '<div class="muted small">官方沒有提供今天的淨值比</div>' and o["n"] == 0


def test_js_render():
    js = HELPERS + "\n" + BAND + MOCK + r"""
const out = {};
charts = [{ remove() { out.old = true; } }];
renderBand(mk(), 'pe');
const c = created[0];
out.title = els['#bandT'].textContent; out.box = els['#bandBox'].innerHTML; out.charts = charts.length === 1 && charts[0] === c;
out.kinds = c.kinds; out.opt = [c.opt.handleScroll, c.opt.handleScale, c.opt.rightPriceScale.entireTextOnly, c.opt.layout.attributionLogo];
out.ser = c.ser.map(s => [s.o.color, s.o.lineStyle, s.o.lineWidth, s.data.map(p => p.time), s.data.map(p => p.value === undefined ? null : p.value)]);
out.leg = els['#bandL'].innerHTML; c.cb({ logical: 0, time: D[1] }); out.leg0 = els['#bandL'].innerHTML; c.cb({ logical: null }); out.legx = els['#bandL'].innerHTML;
out.lo = (renderBand(mk({ val: { pe: [0, 20, 30] } }), 'pe'), els['#bandBox'].innerHTML); out.hi = (renderBand(mk({ val: { pe: [100, 15, 20] } }), 'pe'), els['#bandBox'].innerHTML);
renderBand(mk(), 'pb'); out.pb = [els['#bandT'].textContent, els['#bandBox'].innerHTML, created[0].removed, created.length];
renderBand(mk({ industry: '金融保險', fund: { pe: 120, pb: 2, date: '2026-11-20' }, val: { pe: [99, 15, 130] } }), 'pe'); out.fin = els['#bandBox'].innerHTML;
console.log(JSON.stringify(out));"""
    o = _node(js)
    if o is None:
        return
    assert o["old"] and o["charts"] and o["title"] == "本益比河流圖（近一年）"
    assert o["kinds"] == ["line"] * 6 and o["opt"] == [False, False, True, False], o   # 只有線（不塗色）
    T = ["2026-11-16", "2026-11-17", "2026-11-18", "2026-11-19"]                  # 從第一段起日到 band.d
    close = o["ser"][5]
    assert close[0] == "#111" and close[3] == T and close[4] == [100, None, 104, 102], close   # 原始收盤 prices.c，無成交留空
    for j, (k, sty, w) in enumerate(zip((10, 12, 15, 18, 20), (2, 0, 0, 0, 2), (1, 1, 2, 1, 1))):
        s = o["ser"][j]                                                            # 第 i 天 = 當天的階梯值 × k；虧損期間 None：線斷開
        assert s[:4] == ["#00f", sty, w, T] and s[4][:3] == [5 * k, 5 * k, None] and abs(s[4][3] - 5.1 * k) < 1e-9, s
    b = o["box"]
    assert b.index('id="bandL"') < b.index('id="bandC"') < b.index("band-lg")       # 十字線讀數在上、圖例在圖下方
    assert re.findall(r"第 (\d+) 百分位 ([\d.]+) 倍", b) == [("90", "20.00"), ("75", "18.00"), ("50", "15.00"), ("25", "12.00"), ("10", "10.00")]
    assert '<i class="dash"></i>第 90' in b and '<i class="mid"></i>第 50' in b and '<i class="cl"></i>收盤（原始價）' in b
    assert "11/20 收盤 100 元 = 近 4 季 EPS 5.00 元 × 20.00 倍（近一年第 38 百分位）" in b                # 倍數用 fund.pe、位置用 val.pe
    assert "線斷開 = 當時近 4 季 EPS ≤ 0，官方不計算本益比" in b and "金融業" not in b and "間距很寬" not in b
    assert "<summary>倍數是用近一年的資料算的，不代表股價會回到某條線<i>說明</i></summary>" in b and "近 242 個有官方值的交易日" in b
    assert "<b>11/19</b>" in o["leg"] and "近 4 季 EPS <b>5.10 元</b>" in o["leg"] and "本益比約 <b>20.00 倍</b>" in o["leg"]
    assert "<b>11/16</b>" in o["leg0"] and "收 <b>100</b>" in o["leg0"] and "本益比約 <b>20.00 倍</b>" in o["leg0"] and o["legx"] == o["leg"]
    for w in ("不是股價的評價", "不代表股價會回到某條線", "不能用來回測", "不是投資建議"):
        assert w in b, w                                                           # QA37：免責句在卡片上（不只在 README）
    assert "× 20.00 倍（近一年最低）" in o["lo"] and "× 20.00 倍（近一年最高）" in o["hi"]             # QA37：等於最低／最高時同頁首
    t, box, removed, n = o["pb"]
    assert t == "淨值比河流圖（近一年）" and removed and n == 4 and "每股淨值 50.00 元 × 2.00 倍（近一年第 50 百分位）" in box and "線斷開" not in box
    assert "金融業獲利受利率、匯率影響較大，常搭配淨值比觀察" in o["fin"] and "EPS 很小時本益比會很大，倍數線間距很寬" in o["fin"] and "（近一年最低）" not in o["fin"]


def test_layout_and_hooks():
    i = STK.index("${bandHTML(data, capSub)}")
    assert STK.index("${finUp ? `<div class=\"small val-note fin-note\">") < i < STK.index("<section class=\"sec grid ${F ? 'g2' : 'g-one'}\">") < STK.index("${data.dv ? divHTML(data.dv, data.market, P) : ''}")
    assert "if (tab === 'fund' && data.band) { renderBand(data, bandView(data));" in STK
    assert "localStore('bandV', null, v);" in STK and "renderBand(data, v); }); }" in STK
    rb = _grab(STK, "renderBand")
    assert rb.count("disposeKCharts();") == 1 and "charts = [c];" in rb                # disposeStockCharts 一併釋放
    assert "data.prices" in rb and "adjFactors" not in rb and "aggregate" not in rb    # 原始收盤，和還原切換無關
    for w in ("addAreaSeries", "addBaselineSeries", "addHistogramSeries", "topColor", "fillColor", "rgba(", "gradient"):
        assert w not in rb, w                                                         # 不塗色
    assert not re.search(r'style="[^"]*background', rb)                                 # QA37：圖區也不用 CSS 底色
    for w in (".at(", "??", "?.", "||=", "&&=", "replaceAll", "structuredClone"):
        assert w not in BAND, w                                                        # node 14 可跑
    assert len(re.findall(r"noteHTML\((['`])(.+?)\1,", APP + STK)) == 8 and "noteHTML(short, BAND_NOTE(k, B.n))" in rb
    assert not re.search(r"#band[A-Za-z]*[^{]*\{[^}]*background", CSS)                          # QA37：圖區沒有底色
    assert ".band-lg{margin:6px 0 4px}" in CSS and ".band-lg i.dash{background:none;height:0;border-top:2px dashed var(--blue);border-radius:0}" in CSS


def test_version():
    for f in ("stock.js", "app.css"):
        v = hashlib.sha1((SITE / f).read_bytes()).hexdigest()[:8]
        assert (f'src="{f}?v={v}"' if f.endswith(".js") else f'href="{f}?v={v}"') in HTML, f"site/index.html 的 {f} 版本參數請改成 ?v={v}"


# ─── F37-5：用詞 ─────────────────────────────────────────
WORDS = ("買進", "賣出", "反彈", "見底", "買點", "超賣", "超買", "推薦", "強勢", "飆股", "勝率", "亮點", "建議", "低估", "高估", "超跌", "便宜",
         "合理價", "昂貴", "目標價", "上檔", "下檔", "支撐", "壓力", "安全邊際", "賣點", "河道", "歷史本益比", "超漲")


def _scope():
    seg = BAND + "\n" + EXP[EXP.index("def band_series"):EXP.index("def _load_valuation")]
    seg += "\n".join(l for l in (STK + CSS + EXP).splitlines() if "第 37 輪" in l)
    seg += "".join(l[l.index("第 37 輪"):] for l in README.splitlines() if "第 37 輪" in l)
    return seg


def test_no_advice_words():
    seg = _scope()
    assert seg.count("第 37 輪") >= 5 and "不是股價的評價" in seg and "不代表股價會回到某條線" in seg and "不能用來回測" in seg
    seg = seg.replace("不是投資建議", "").replace("非投資建議", "")
    for w in WORDS:
        assert w not in seg, w
    assert "便宜" in STK                                         # 第 240 行舊說明不在掃描範圍（test_iter10、test_iter13 要求保留）


# ─── 實際匯出資料（有才測）────────────────────────────────
def test_real_data():
    d = SITE / "data" / "stocks"
    files = sorted(d.glob("*.json")) if d.exists() else []
    objs = [json.loads(p.read_text(encoding="utf-8")) for p in files]
    if not any("band" in o for o in objs):
        print("  （尚未用第 37 輪匯出，略過）")
        return
    n = {"pe": 0, "pb": 0}
    for o in objs:
        B = o.get("band")
        if o.get("capchg"):
            assert not B, o["code"]
        if not B:
            continue
        assert set(B) <= {"d", "pe", "pb"} and len(B) >= 2 and (o.get("val") or {}).get("d", B["d"]) == B["d"], o["code"]
        assert len(json.dumps(B, ensure_ascii=False, separators=(",", ":"))) <= 3000, o["code"]
        for k in ("pe", "pb"):
            b = B.get(k)
            if not b:
                continue
            n[k] += 1
            ds = [x[0] for x in b["s"]]
            assert b["n"] >= export.VAL_MIN and len(b["s"]) <= export.BAND_SEG_MAX and ds == sorted(set(ds)) and ds[-1] <= B["d"], o["code"]
            assert b["k"] == sorted(b["k"]) and len(b["k"]) == 5 and all(v > 0 for v in b["k"]), o["code"]
            assert all(x[1] is None or x[1] > 0 for x in b["s"]), o["code"]
            v = (o.get("val") or {}).get(k)
            if v:
                assert v[1] <= b["k"][0] and b["k"][4] <= v[2], o["code"]
    assert n["pe"] > 1000 and n["pb"] > 1500, n


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_") and callable(f):
            print("==", n); f()
    print("全部通過")
