"""
第 30 輪 UI/UX 全站體檢（不連網、不連資料庫；只改 site/）：
D30-01 個股頁分頁列貼在頂欄下（帶名稱與價格），固定狀態換分頁時新分頁從分頁列下方開始；
D30-02 手機搜尋清單全寬、名稱單行；D30-03／05 今日頁信用、估值、市場寬度改「指標 × 市場」小表；
D30-04 ETF 列表預設 50 檔；D30-06 資金象限每格各自連結並在泡泡清單標示；D30-07 差一次一檔一列；
D30-08 手機泡泡清單展開成分股不限高（前 10 檔＋顯示全部）；D30-09 頁首新訊號手機只顯示 1 個；
D30-10 顯示「0億」時不上漲跌色；D30-11 排行種類選單併入快捷列；D30-12 基本面估值卡一列 3 張、股利表內距。
有 node 時逐字取出 app.js 的函式執行（node 14 可跑）。

  python3 tests/test_iter30.py      （也相容 pytest）
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_iter28 as t28  # noqa: E402

APP, STK, CSS = t28.APP, t28.STK, t28.CSS
G = lambda *names: "\n".join(t28._grab(APP, n) for n in names)
AT = ("if (!Array.prototype.at) Array.prototype.at = function (i) { return this[i < 0 ? this.length + i : i]; };\n"   # node 14 沒有 .at()、replaceAll
      "if (!String.prototype.replaceAll) String.prototype.replaceAll = function (a, b) { return this.split(a).join(b); };\n")


# ─── D30-01、09、12：個股頁 ─────────────────────────────────
def test_stock_page_source():
    assert "ptab.classList.add('pt-stick');" in STK and "<span class=\"pt-nm\">${esc(data.name)}" in STK
    assert "observe($('#view .s-head'))" in STK                                                     # 頁首捲出畫面才顯示名稱與價格
    assert "App.ptStuck = $('#view .s-head').getBoundingClientRect().bottom <= topH();" in STK     # 換分頁前在固定狀態
    assert "if (App.ptStuck) { App.ptStuck = false; ptab.style.position = 'static';" in STK         # 新分頁從分頁列下方開始
    assert ".page-tabs.pt-stick{position:sticky;top:var(--top-h,56px);z-index:15;" in CSS and ".pt-stick.stuck .pt-nm{display:block}" in CSS
    assert "$('#view .pt-stick')?.getBoundingClientRect().bottom ?? 0" in APP                        # 長表格的表頭貼在分頁列下
    # D30-09：新訊號超過 1 個時有「+N」，手機收合時只顯示第 1 個、免責句一起收
    assert "${HL.length > 1 ? `<button class=\"pill more hl-more\" id=\"hlMore\">+${HL.length - 1}</button>` : ''}" in STK
    assert "$('#hlMore')?.addEventListener('click', e => e.currentTarget.parentElement.classList.add('open'));" in STK
    assert ".s-hl:not(.open) .hl-tag~.hl-tag,.s-hl:has(.hl-more):not(.open)>span.muted{display:none}" in CSS
    # D30-12
    assert "<section class=\"sec metrics${tab === 'k' ? ' kv' : ' m3'}\">" in STK
    assert ".metrics.m3{grid-template-columns:repeat(3,minmax(0,1fr))}" in CSS and "table.dv-tbl th,table.dv-tbl td{padding-left:4px;padding-right:4px}" in CSS


def test_zero_color():
    # D30-10：yi 顯示 0億 時顏色為灰色；個股卡片也依顯示值
    assert ", ycls = n => cls(n != null && Math.abs(n) < 0.05 ? 0 : n);" in APP
    assert "${v === '0億' ? 'flat' : c || ''}" in STK
    assert "${cls(n5)}\">${yi(n5)}" not in APP and APP.count("ycls(") == 14
    o = t28._node(t28.HELPERS + "\nconsole.log(JSON.stringify([0.04, -0.04, 0.05, -0.2, null, 0].map(v => [yi(v), ycls(v)])));")
    if o is not None:
        assert o == [["0億", "flat"], ["0億", "flat"], ["+0.1億", "up"], ["-0.2億", "dn"], ["--", "flat"], ["0億", "flat"]], o


# ─── D30-02：搜尋清單 ─────────────────────────────────────
def test_search_list():
    assert '<span class="code">${c}</span><span class="qn">${esc(s.n)}</span>' in APP
    assert ".qn{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}" in CSS
    assert "@media (max-width:720px){.search{position:static}.qlist{left:8px;right:8px;top:calc(100% + 4px)}}" in CSS


# ─── D30-03、05：今日頁小表 ───────────────────────────────
L = {"date": "2026-11-16", "stocks": {"2330": {"n": "台積電"}},
     "margin": {"TWSE": {"d": "2026-11-16", "mb": 5926000, "m1": -75214, "mp": -1.25, "sb": 126000, "s1": 5524, "sr": 2.13, "mr": 158.6, "mr0": 171.0,
                         "amt": 5245.0, "amt1": -121.0, "sp": 4.0, "m20": [1, -2], "d20": ["2026-11-13", "2026-11-16"]},
                "TPEx": {"d": "2026-11-13", "mb": 2011000, "m1": -32735, "mp": -1.6, "sb": 39000, "s1": 2158, "sr": 1.94, "mr": None, "mr0": None,
                         "amt": 1677.3, "amt1": -42.9}},
     "sbl": {"TWSE": {"d": "2026-11-16", "lb": 13310000, "l1": 21387}},
     "breadth": {"TWSE": {"d": "2026-11-16", "ma20": 13.3, "ma60": 13.8, "hi": 25, "lo": 375, "vr": 0.87, "s20": [20.3, 13.3], "from": "2026-11-13", "n20": 1085},
                 "TPEx": {"d": "2026-11-16", "ma20": 17.4, "ma60": 17.3, "hi": 30, "lo": 289, "vr": 0.84, "s20": [26.0, 17.4], "n20": 873}},
     "valuation": {"TWSE": {"d": "2026-11-16", "days": 242, "from": "2025-11-14", "n": 900, "pe": {"v": 15.59, "p": 0.8, "lo": 15, "hi": 20},
                            "pb": {"v": 1.46, "p": 0, "lo": 1.46, "hi": 2}, "dy": {"v": 2.8, "p": 60.3, "lo": 2, "hi": 3},
                            "wpe": {"v": 19.48, "p": 1.2, "lo": 19, "hi": 25, "t": ["2330", 43.3]}},
                   "TPEx": {"d": "2026-11-16", "n": 700, "pe": {"v": 16.81, "p": 0, "lo": 16.81, "hi": 20}, "pb": {"v": 1.77, "p": 0.8, "lo": 1.5, "hi": 2},
                            "dy": {"v": 1.96, "p": 64.5, "lo": 1, "hi": 3}}}}


def test_today_tables_node():
    assert "const mxTbl = (cols, rows) => `<table class=\"mx num\">" in APP and "table.mx{width:100%;" in CSS
    js = AT + t28.HELPERS + "\n" + G("noteHTML", "mxTbl", "s2", "spark", "minibars", "sblLine", "etfSblLine", "marginCard", "breadthCard",
                                 "valCard", "wpeLine", "wpeRow", "finLine") + f"""
const App = {{ latest: {json.dumps(L, ensure_ascii=False)} }};
console.log(JSON.stringify({{ m: marginCard(App.latest), b: breadthCard(App.latest), v: valCard(App.latest) }}));"""
    o = t28._node(js)
    if o is None:
        return
    m, b, v = o["m"], o["b"], o["v"]
    assert '<thead><tr><th></th><th>上市</th><th>上櫃<span class="muted">（11/13）</span></th></tr></thead>' in m      # 上櫃資料日較舊時寫在欄名
    assert '<tr><th>融資</th><td><b title="5,926,000 張">592.6</b> 萬張<div class="s2"><span class="dn">-75,214</span>（-1.25%）</div></td>' in m
    assert '<tr><th>融資維持率<div class="s2">自算</div></th><td><b>158.6%</b><div class="s2">前日 171.0%</div></td><td>資料不足</td></tr>' in m
    assert '<tr><th>借券賣出餘額<div class="s2"><a class="muted" href="#/rank/l+">看排行 →</a></div></th>' in m and '<br>融券的 106 倍' in m
    assert m.index('<table class="mx num">') < m.index('借券賣出含避險、套利，不等於看空')
    assert '<tr><th>站上 MA20</th><td><b>13.3%</b><div class="s2">前日 20.3%</div></td><td><b>17.4%</b><div class="s2">前日 26.0%</div></td></tr>' in b
    assert '<tr><th>20 日新低</th><td><span class="dn">375</span></td><td><span class="dn">289</span></td></tr>' in b
    assert '<tr><th>本益比</th><td><b>15.59</b><div class="s2">一年位置 0.8%</div></td><td><b>16.81</b><div class="s2">一年最低</div></td></tr>' in v
    assert '<th>殖利率<div class="s2">一年位置，越高 = 殖利率相對越高</div></th>' in v
    assert '<tr><th>加權本益比<div class="s2">市值加權</div></th><td><b>19.48</b><div class="s2">一年位置 1.2%</div></td><td>--</td></tr>' in v
    assert "不是證交所公布的數字" in v and v.index("加權本益比") < v.index("不是證交所公布的數字")


# ─── D30-06、07、08：象限連結、差一次、泡泡展開 ────────────────
def test_quads_and_near_node():
    assert '<a class="quad q-${q}" href="#/bubble" data-q="${q}">' in APP and '<a class="quads"' not in APP
    assert "App.blQ = e.target.closest('[data-q]')?.dataset.q;" in APP and "App.blHit = App.blQ; App.blQ = null;" in APP
    assert "else if (App.blHit) requestAnimationFrame(() => $('#blBox tr.q-hit')?.scrollIntoView());" in APP
    W = {"date": "2026-11-16", "stocks": {"2314": {"n": "台揚", "m": "TWSE"}, "3374": {"n": "精材", "m": "TPEx"}, "2466": {"n": "冠西電", "m": "TWSE"}},
         "alerts": {"d": [], "n": [], "w": [["2466", 1, "第一款連 3 日、30 日內 12 次"], ["2314", 0, "第一款連 2 日"], ["3374", 0, "第 1～8 款連 4 日"]]}}
    js = "\n".join(t28._grab(APP, n) for n in ("esc", "md", "watchGrp", "alertBoard")) + f"""
const App = {{ alertAll: false, alOpen: true }};
console.log(JSON.stringify(alertBoard({json.dumps(W, ensure_ascii=False)})));"""
    o = t28._node(js)
    if o is not None:
        assert '<div class="al-near small muted">差一次：</div>' in o
        assert ('<a class="al-row" href="#/stock/3374"><div class="al-l"><b>精材</b><span class="muted small">3374・上櫃</span><span class="sp"></span><span class="small">差 1 次</span></div>\n'
                '        <div class="muted small al-why">目前 第 1～8 款連 4 日</div></a>') in o
        assert "目前 第 1 款連 2 日" in o and "第 1 款連 3 日、30 日內 12 次" in o and "第一款" not in o
        assert "依注意款別推算（第 1 款連 3 日" in o


def test_bubble_list_node():
    S = {str(1100 + i): {"n": f"股{i}", "c": 10, "p": 1, "n1": 0.01 * i, "n5": i} for i in range(12)}
    js = AT + t28.HELPERS + "\n" + G("pctCell", "groupMeta", "groupRows", "bubbleList") + f"""
const App = {{ group: 'industry', blOpen: 'A', blHit: '觀望', latest: {{ dates: ['2026-11-13', '2026-11-16'], flow_date: '2026-11-16', stocks: {json.dumps(S)} }} }};
const G = [{{ name: 'A', quadrant: '漲潮', frames: [null, [5, 1, 1.5, 100]], codes: {json.dumps(list(S))}, net_5d: 5, streak: 2 }},
  {{ name: 'B', quadrant: '觀望', frames: [null, [-3, 1, -0.5, 20]], codes: [], net_5d: -3, streak: -1 }}];
const h1 = bubbleList(G); App.blAll = true; const h2 = bubbleList(G);
console.log(JSON.stringify({{ h1, h2 }}));"""
    o = t28._node(js)
    if o is None:
        return
    h1, h2 = o["h1"], o["h2"]
    assert '<div class="small bl-hit">已標示「觀望」1 個</div>' in h1 and '<tr data-bl="B" class="q-hit">' in h1 and '<tr data-bl="A" class="on">' in h1
    assert '<div class="tbl-wrap panel-list"><table class="tbl"><thead>' in h1                       # 第 28 輪結構不變
    assert '<button class="chip" data-blall="0">顯示全部 12 檔</button>' in h1 and '<button class="chip" data-blall="1">只顯示前 10 檔</button>' in h2
    assert ".bl-x .panel-list{max-height:none}.bl-x:not(:has([data-blall=\"1\"])) .panel-list tbody tr:nth-child(n+11){display:none}" in CSS
    assert "<td class=\"num flat\">0億</td>" in h1                                                    # D30-10：股0 法人1日 0
    assert "App.blOpen = App.blOpen === name ? null : name; App.blAll = false;" in APP
    assert "if (e.target.closest('[data-blall]')) { App.blAll = !App.blAll; $('#blBox').innerHTML = bubbleList(groups); return; }" in APP   # 「顯示全部」有切換（QA30-01 補強）


# ─── D30-04、11：ETF、排行 ────────────────────────────────
def test_etf_and_rank_source():
    assert "const ETF_N = 50;" in APP
    assert "tr.hidden = q ? !(tr.dataset.etf.toLowerCase() + tr.cells[0].textContent.toLowerCase()).includes(q) : !App.etfAll && i >= ETF_N;" in APP
    assert "`顯示全部 ${list.length} 檔`" in APP and "`只顯示前 ${ETF_N} 檔`" in APP and "$('#etfMore').hidden = !!q;" in APP
    assert ".etf-tbl td.nm b{display:-webkit-box;-webkit-line-clamp:2;" in CSS
    assert '<div class="rk-q"><select id="rankSel" class="sel">' in APP and APP.count('id="rankSel"') == 1
    assert ".rk-q{flex-wrap:nowrap;overflow-x:auto;" in CSS


def test_no_advice_words():
    seg = "\n".join(l for l in (APP + STK + CSS).splitlines() if "第 30 輪" in l or "D30-" in l)
    seg += G("mxTbl", "marginCard", "breadthCard", "valCard", "wpeRow", "watchGrp", "bubbleList")
    for w in ("買進", "賣出", "反彈", "見底", "買點", "超賣", "超買", "推薦", "強勢股", "飆股", "勝率", "亮點", "低估", "高估", "建議"):
        assert w not in seg.replace("借券賣出", ""), w


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            print("==", name)
            fn()
            print("✅", name)
    print("全部通過")
