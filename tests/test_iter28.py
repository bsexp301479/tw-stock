"""第 28 輪：UI/UX 優化（不連網、不連資料庫）。
籌碼分頁分組小卡＋時間序列圖（張）、期貨未平倉表手機欄距、返回時還原捲動位置、泡泡圖手機清單、
手機關鍵數字列移到成交量之後、融資融券子圖標題區、法人子圖對稱刻度、泡泡提示框格式、未知分頁網址補正。
有 node 時逐字取出 app.js／stock.js 的函式執行（node 14 可跑：不用 .at()、replaceAll）。"""
import json
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "site" / "app.js").read_text(encoding="utf-8")
STK = (ROOT / "site" / "stock.js").read_text(encoding="utf-8")
CSS = (ROOT / "site" / "app.css").read_text(encoding="utf-8")


def _grab(src, name):
    m = re.search(rf"^(?:async )?function {name}\(", src, re.M)
    if m:
        i, n = src.index("{", src.index(")", m.start())), 0
        for j in range(i, len(src)):
            n += {"{": 1, "}": -1}.get(src[j], 0)
            if n == 0:
                return src[m.start():j + 1]
    m = re.search(rf"^(?:const|let) {name}\b", src, re.M)      # const／let 取到去掉行尾註解後結尾為「;」的那一行
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


HELPERS = "\n".join(_grab(APP, n) for n in ("esc", "fmt", "pfmt", "sgn", "cls", "yi", "md"))


# ─── D28-01：籌碼分頁分組小卡＋時間序列 ─────────────────────
def test_chip_groups_source():
    assert "const CHIP_N = [['20', '20 日'], ['60', '60 日'], ['120', '120 日'], ['all', '全部']];" in STK
    assert "let chipN = '60';" in STK and "localStore('chipN'" not in STK                     # 預設 60 日，不新增 localStorage 鍵
    assert "${chipSec('法人買賣超', `${fd}，億，估算（張數 × 收盤）`, inCards," in STK          # 卡片：億（估算）
    assert "chLeg('區間累計買賣超（張，未還原；從區間第一天起加總）', 'ciC', 150)" in STK        # 圖：張
    assert "${chipSec('信用交易', MG ? md(MG.d) : '', mgCards," in STK
    assert "${chipSec('借券賣出', SL ? `${md(SL.d)}，晚上 8 點半以後更新` : '', slCards," in STK
    assert "'資料 ' + md(MG.d)" not in STK and "'資料 ' + md(SL.d)" not in STK                # 日期只寫在組標題
    assert "if (tab === 'chip') buildChip(data, E);" in STK and "charts = anchors.map(a => a[0]);" in STK   # disposeStockCharts 一併釋放
    assert ".chip-g .kv{grid-template-columns:none;grid-auto-flow:column;" in CSS               # 寬螢幕一組一列
    assert "@media (max-width:520px){.chip-g .kv{grid-auto-flow:row;grid-template-columns:repeat(2,minmax(0,1fr))}" in CSS


def test_chip_charts_node():
    js = HELPERS + "\n" + "\n".join(_grab(STK, n) for n in ("INVESTORS", "disposeKCharts", "adjFactors", "aggregate", "buildChip")) + r"""
let charts = [], chipN = 'all';
const css = () => '#888', created = [], els = {};
const $ = s => s in els ? els[s] : (els[s] = { innerHTML: '' });
const window = { LightweightCharts: { createChart: (el, opt) => {
  const c = { el, opt, ser: [], addLineSeries(o) { const s = { o, setData(d) { this.data = d; }, createPriceLine(p) { this.pl = p; } }; this.ser.push(s); return s; },
    timeScale: () => ({ fitContent() {} }), subscribeCrosshairMove(f) { this.cb = f; }, setCrosshairPosition(v, t) { this.cross = [v, t]; },
    clearCrosshairPosition() { this.cross = null; }, remove() { this.removed = true; } };
  created.push(c); return c; } } };
const D = ['2026-11-09', '2026-11-10', '2026-11-11', '2026-11-12', '2026-11-13'];
const data = { market: 'TWSE', prices: { d: D, o: [10, 11, 12, 13, 14], h: [10, 11, 12, 13, 14], l: [10, 11, 12, 13, 14], c: [10, 11, 12, 13, 14], v: [1, 1, 1, 1, 1], ch: [0, 1, 1, 1, 1] },
  insti: { f: [10, -20, 30, 5, null], t: [1, 1, 1, 1, null], dl: [0, 0, 0, -2, null] }, mg: { mb: [100, 110, 120, 130, 140], sb: [1, 2, 3, 4, 5], lb: [50, 60, 70, null, null] }, ev: [] };
buildChip(data, false);
const all = { n: created.length, ids: created.map(c => c.el === els['#cpC'] ? 'cp' : c.el === els['#ciC'] ? 'ci' : c.el === els['#cmC'] ? 'cm' : 'cl'),
  scroll: created.map(c => c.opt.handleScroll || c.opt.handleScale), entire: created.every(c => c.opt.rightPriceScale.entireTextOnly),
  cum: created[1].ser.map(s => s.data.map(p => p.value ?? null)), zero: created[1].ser[0].pl.price,
  ci: els['#ciCL'].innerHTML, cm: els['#cmCL'].innerHTML, cl: els['#clCL'].innerHTML, cp: els['#cpCL'].innerHTML };
created[1].cb({ logical: 1, time: D[1] });
const hover = { ci: els['#ciCL'].innerHTML, cross: created[0].cross, cm: created[2].cross };
const before = created.slice();
chipN = '2'; created.length = 0; buildChip(data, false);
const two = { removed: before.every(c => c.removed), cum: created[1].ser[0].data.map(p => p.value ?? null), ci: els['#ciCL'].innerHTML };
created.length = 0; els['#cpC'] = null; chipN = 'all'; buildChip(data, true);   // ETF：沒有法人圖
console.log(JSON.stringify({ all, hover, two, etf: created.length }));"""
    o = _node(js)
    if o is None:
        return
    a = o["all"]
    assert a["n"] == 4 and a["ids"] == ["cp", "ci", "cm", "cl"] and a["scroll"] == [False] * 4 and a["entire"], a
    assert a["cum"] == [[10, -10, 20, 25, None], [1, 2, 3, 4, None], [0, 0, 0, -2, None]], a["cum"]      # 從區間第一天起加總；缺值不補
    assert a["zero"] == 0
    # 最新一天法人還沒有：圖例改顯示最近有資料的那天，並寫出日期
    assert a["ci"].startswith('<span class="muted">11/12</span>') and '外資 <b class="num up">+25</b><span class="muted">（當日 +5）</span>' in a["ci"], a["ci"]
    assert '自營 <b class="num dn">-2</b>' in a["ci"]
    assert "融資 <b class=\"num\">140</b>" in a["cm"] and "券資比 <b class=\"num\">3.57%</b>" in a["cm"] and "<b>11/13</b>" in a["cm"]
    assert "<b>11/11</b>" in a["cl"] and "借券賣出 <b class=\"num\">70</b>" in a["cl"]
    assert "收 <b>14</b>" in a["cp"]
    h = o["hover"]
    assert '外資 <b class="num dn">-10</b><span class="muted">（當日 -20）</span>' in h["ci"] and h["cross"] == [11, D1] and h["cm"] == [110, D1], h
    t = o["two"]
    assert t["removed"] and t["cum"] == [5, None] and '外資 <b class="num up">+5</b>' in t["ci"], t
    assert o["etf"] == 2                                            # ETF：只有融資、借券兩張


D1 = "2026-11-10"


# ─── D28-02：期貨未平倉表 375 不橫捲 ──────────────────────
def test_oi_table_padding():
    # 原本 ≤520 的 5px 被後面的 .tbl 6px 蓋掉（表 321 > 框 309，「增減」最後一位數被切）；提高權重改成 4px
    assert "@media (max-width:520px){table.oi-tbl th,table.oi-tbl td{padding:8px 4px}" in CSS
    assert CSS.index("table.oi-tbl th,table.oi-tbl td{padding:8px 4px}") > CSS.index("@media (max-width:520px){\n  .tbl th,.tbl td{padding:8px 6px}")


# ─── D28-03：返回時還原捲動位置 ───────────────────────────
def test_route_scroll_restore():
    assert "history.scrollRestoration = 'manual';" in APP
    assert "addEventListener('scroll', saveScroll, { passive: true }); document.addEventListener('click', saveScroll, true);" in APP   # QA28-01
    assert "window.scrollTo(0, 0);" not in _grab(APP, "route")
    js = _grab(APP, "esc") + "\n" + _grab(APP, "scrollAt") + "\nlet scrollKey = null;\n" + _grab(APP, "route") + r"""
let hash = '', during = [];
const location = { get hash() { return hash; } };
const history = { state: null, replaceState(s, t, u) { this.state = s; if (u) hash = u; } };
const scrolls = [], window = { scrollTo: (x, y) => scrolls.push(y) };
const document = { title: '', querySelectorAll: () => [] }, $ = () => null, App = {};
const disposeFuturesChart = () => {}, renderToday = async () => {};
const page = async () => { during.push(scrollKey); };
const routes = { rank: page, stock: page, watch: page, bubble: page };
(async () => {
  hash = '#/rank/n+'; await route(); const k1 = history.state.k;
  scrollAt[scrollKey] = 1576;                                       // 捲動監聽記下的位置
  hash = '#/stock/2330'; history.state = null; await route(); const k2 = history.state.k;
  hash = '#/rank/n+'; history.state = { k: k1 }; await route();     // 返回
  hash = '#/stock/2330'; history.state = { k: k2 }; await route();  // 前進：個股頁沒捲過 → 頂端
  hash = '#/watch/abc'; history.state = null; await route(); const w = hash;
  hash = '#/bubble/x'; history.state = null; await route();
  console.log(JSON.stringify({ scrolls, during, same: k1 === k2, w, b: hash, k: typeof history.state.k }));
})();"""
    o = _node(js)
    if o is None:
        return
    assert o["scrolls"] == [0, 0, 1576, 0, 0, 0], o            # 新頁到頂端，返回還原
    assert o["during"] == [None] * 6 and o["same"] is False      # 換頁中不記錄；每筆紀錄的鍵不同
    assert o["w"] == "#/watch" and o["b"] == "#/bubble" and o["k"] == "number"


def test_scroll_key_restored_after_replace_null():
    """QA28-01：同頁切換用 replaceState(null, …) 清掉鍵後，捲動或點擊時把鍵補回（不帶網址），返回才找得到位置。"""
    js = "const scrollAt = {};\nlet scrollKey = null;\n" + _grab(APP, "saveScroll") + r"""
const history = { state: null, calls: [], replaceState(s, t, u) { this.state = s; this.calls.push(u); } };
const window = { scrollY: 800 };
saveScroll();                                         // route() 執行中（scrollKey 是 null）：不記、不補
const a = { st: history.state, n: history.calls.length };
scrollKey = 7; history.state = { k: 7 }; saveScroll(); // 鍵一致：只記位置
const b = { at: scrollAt[7], n: history.calls.length };
history.state = null; window.scrollY = 600; saveScroll();   // 切換 1日／5日後被清成 null
console.log(JSON.stringify({ a, b, c: { st: history.state, at: scrollAt[7], url: history.calls } }));"""
    o = _node(js)
    if o is None:
        return
    assert o["a"] == {"st": None, "n": 0}, o
    assert o["b"] == {"at": 800, "n": 0}, o
    assert o["c"] == {"st": {"k": 7}, "at": 600, "url": [None]}, o          # 補回鍵、不改網址


def test_bubble_list_mobile_fit():
    """QA28-02：手機展開的成分股表字級 12px、欄距 4px（≤380 再縮 3px），360 寬外層清單欄距 4px，數字不被切。"""
    assert "@media (max-width:520px){.bl-x table.tbl{font-size:12px}.bl-x table.tbl th,.bl-x table.tbl td{padding-left:4px;padding-right:4px}}" in CSS
    assert "@media (max-width:380px){table.bl-tbl>*>tr>*{padding-left:4px;padding-right:4px}.bl-x table.tbl th,.bl-x table.tbl td{padding-left:3px;padding-right:3px}}" in CSS


# ─── D28-04、07：泡泡圖手機清單、提示框格式 ─────────────────
def test_bubble_list_node():
    js = HELPERS + "\n" + _grab(APP, "pctCell") + "\n" + "\n".join(_grab(APP, n) for n in ("groupMeta", "groupRows", "bubbleList")) + r"""
const App = { group: 'industry', blOpen: 'B', latest: { dates: ['2026-11-12', '2026-11-13'], flow_date: '2026-11-13',
  stocks: { 1101: { n: '台泥', c: 30, p: 1.2, n1: 0.5, n5: 2 } } } };
const G = [{ name: 'B', quadrant: '退潮', frames: [null, [-3, -1, -0.5, 2000]], codes: [], net_5d: -3, streak: -2 },
  { name: 'A', quadrant: '漲潮', frames: [null, [5, 1, 1.5, 100]], codes: ['1101'], net_5d: 5, streak: 2 },
  { name: 'C', quadrant: '輪動', frames: [[1, 1, 1, 1], null], codes: [], net_5d: 1, streak: 1 }];
const h1 = bubbleList(G); App.blOpen = null; App.group = 'chain';
console.log(JSON.stringify({ h1, h2: bubbleList(G) }));"""
    o = _node(js)
    if o is None:
        return
    h = o["h1"]
    assert "<th>類股</th><th>近5日</th><th>日均差</th><th>漲跌</th><th>成交</th>" in h and "資料日 11/13" in h
    assert h.index('data-bl="A"') < h.index('data-bl="B"') and 'data-bl="C"' not in h       # 近 5 日由大到小；最新一天沒有值的不列
    assert '<td class="num up">+5.0億</td><td class="num up">+1.0</td><td class="num up">+1.50%</td><td class="num">100</td>' in h
    assert '<tr data-bl="B" class="on">' in h and '<i style="color:var(--dn)">退潮</i>' in h
    assert '<tr class="bl-x"><td colspan="5">' in h and h.index('<tr class="bl-x">') > h.index('data-bl="B"')
    assert '<div class="tbl-wrap panel-list"><table class="tbl"><thead><tr><th>股票</th>' in h
    assert "bl-x" not in o["h2"] and "<th>產業鏈</th>" in o["h2"]


def test_bubble_source():
    assert "const mob = matchMedia('(max-width:720px)').matches, list = mob && App.bubbleView !== 'chart';" in APP   # 手機預設清單
    assert "segHTML('bvSeg', [['chart', '圖'], ['list', '清單']]" in APP and "localStore('bubbleView'" not in APP
    assert "App.blOpen = g.dataset.group; App.blJump = 1;" in APP                                # 今日頁點族群：展開並捲到那一列
    assert "'#view .tbl-wrap:not(.panel-list)'" in APP and ".panel-list{--th-y:0px}" in CSS        # 內層捲動框不位移表頭
    assert ".bl-x .tbl-wrap{width:0;min-width:100%}" in CSS                                        # 展開的表不撐寬清單
    tpl = re.search(r"hovertemplate: '(<b>%\{customdata\[0\]\}.*?)'", APP).group(1)
    assert ":+" not in tpl and ":," not in tpl and "%{customdata[1]}" in tpl                       # Plotly basic 不認得 +.1f
    assert "return [g.name, amount(f[0]), sgn(f[1], 1) + '億/天', sgn(f[2]) + '%', fmt(f[3]) + '億'];" in APP   # 近 5 日和泡泡上的字同一種格式


# ─── D28-05、06：個股走勢分頁 ─────────────────────────────
def test_k_tab_layout():
    assert "else $('#vC').after($('#view .metrics.kv'));" in STK and "$('#kC').after(" not in STK
    assert "#vC+.kv .card:last-child:nth-child(3n+1){grid-column:span 3}" in CSS
    assert "$('#gUnit').textContent = adj ? '餘額（張）' : '餘額（張，官方原始）';" in STK
    assert "$('#gUnit').title = adj ? '面額變更、減資前的餘額依官方換算' : '';" in STK
    assert "mgView(data.mg))}<span id=\"gUnit\"></span>" in STK and "（張；面額變更、減資前的餘額依官方換算）" not in STK
    assert ".ch-label{row-gap:2px}.mg-l{align-items:center}" in CSS
    assert "autoscaleInfoProvider: symScale" in STK and "entireTextOnly: true" in STK
    line = next(l for l in STK.splitlines() if "const symScale = " in l).strip()
    js = line + r"""
const r = symScale(() => ({ priceRange: { minValue: -400, maxValue: 120 }, margins: { above: 1 } }));
console.log(JSON.stringify([r, symScale(() => null), symScale(() => ({ priceRange: { minValue: 0, maxValue: 0 } }))]));"""
    o = _node(js)
    if o is not None:
        assert o[0] == {"priceRange": {"minValue": -400, "maxValue": 400}, "margins": {"above": 1}}, o
        assert o[1] is None and o[2] == {"priceRange": {"minValue": 0, "maxValue": 0}}


def test_margin_legend_node():
    blk = STK[STK.index("      const gv = mgView(G);"):STK.index("    }\n  };\n  let crossSyncing")]
    js = HELPERS + "\n" + _grab(STK, "mgView") + r"""
let v = 'mb'; const localStore = () => v, els = {}, $ = s => (els[s] = els[s] || {});
const T = ['2026-11-12', '2026-11-13'], MB = [100, 200], SB = [1, 4], LB = [7, 8], G = { lb: [7, 8] }, out = [];
for (const k of ['mb', 'sb', 'lb']) { v = k; const g = 1, i = 1, GV = { mb: [MB, '#1C7ED6'], sb: [SB, '#AE3EC9'], lb: [LB, '#E8590C'] }[k];
""" + blk + r"""
  out.push($('#gLegend').innerHTML); }
console.log(JSON.stringify(out));"""
    o = _node(js)
    if o is None:
        return
    assert o[0] == '<span class="lg"><i style="background:#1C7ED6"></i>融資 <b class="num">200</b></span><span class="lg">券資比 <b class="num">2.00%</b></span>', o[0]
    assert "融券 <b class=\"num\">4</b>" in o[1] and "券資比" in o[1] and "融資" not in o[1]
    assert "借券 <b class=\"num\">8</b>" in o[2] and "券資比" not in o[2]


# ─── D28-08：未知分頁、非 ETF 代號 ─────────────────────────
def test_unknown_routes():
    assert "if (sub && sub !== tab) history.replaceState(history.state, '', `#/stock/${code}/${tab}`);" in STK
    assert "if ((page === 'watch' || page === 'bubble') && arg) history.replaceState(history.state, '', '#/' + page);" in APP
    assert "的持股資料尚未支援（目前支援統一、群益投信 8 檔主動 ETF）" not in APP
    assert "找不到 ${esc(code)} 的資料。可用上方搜尋框查代號或名稱，或<a href=\"#/etf\"" in APP and "document.title = 'ETF｜台股資金流';" in APP


def test_no_advice_words():
    seg = "".join(l for l in APP.splitlines() + STK.splitlines() + CSS.splitlines() if "第 28 輪" in l or "D28-" in l)
    for n in ("bubbleList", "buildChip", "groupMeta"):
        if re.search(rf"^(?:const |function ){n}\b", APP + "\n" + STK, re.M):
            seg += _grab(APP if n != "buildChip" else STK, n)
    assert seg or "第 28 輪" not in APP + STK + CSS
    seg = seg.replace("借券賣出", "")                                           # 資料欄名稱（官方「借券賣出餘額」），不是用語
    for w in ("買進", "賣出", "反彈", "見底", "買點", "超賣", "超買", "推薦", "強勢股", "飆股", "勝率", "低估", "高估", "建議"):
        assert w not in seg, w


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            print("==", name)
            fn()
            print("✅", name)
    print("全部通過")
