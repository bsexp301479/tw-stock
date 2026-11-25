"""第 47 輪（不連網、不連資料庫）：即將除權息提醒 F47-1（匯出 nx、頁頭標籤、自選頁卡與估計可領、今日卡）、指數卡起算日 F47-2、
法人卡自營 F47-3、夜盤時間 F47-4（R61）、自選 ETF 表現 F47-6、名詞「含息報酬」F47-7。
export.nx_latest 用 notice_export 的自造列測；有 node 時逐字取出 app.js、stock.js 的函式＋整個 tools.js 執行（node 14 可跑）；
畫面文字和 docs/iterations/47/02-pm.md 二之一逐字比對。最後的 test_contrast 把原始碼改壞（反證），確認對應的檢查會失敗。"""
import hashlib
import inspect
import json
import re
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
from twstock import export  # noqa: E402
import test_iter32 as T32  # noqa: E402
import test_iter34 as T  # noqa: E402
import test_iter42 as T42  # noqa: E402
import test_iter45 as T45  # noqa: E402

SITE, HTML, APP, STK, CSS, TOOLS = T.SITE, T.HTML, T.APP, T.STK, T.CSS, T.TOOLS
HELP = T45.HELP
SRC = (ROOT / "twstock" / "export.py").read_text(encoding="utf-8")
README = (ROOT / "README.md").read_text(encoding="utf-8")
PM = (ROOT / "docs" / "iterations" / "47" / "02-pm.md").read_text(encoding="utf-8")
ADVICE = set(T42.ADVICE) | T45.ADVICE | {"買進", "賣出", "反彈", "見底", "買點", "超賣", "超買", "推薦", "強勢股", "飆股", "勝率", "保證", "穩賺",
                                         "建議", "便宜", "亮點", "低估", "高估", "跑贏", "跑輸", "領先", "落後", "超額報酬", "搶息", "參加除息"}
DATE, D = "2026-11-23", date(2026, 11, 23)
_grab = T32._grab


# ─── F47-1a 匯出（驗收 1～3）──────────────────────────────────────
def _nrow(code, m, etf, d, t, cash, sub=0, price=None, seen=D):
    return (code, m, etf, d, t, cash, 0, sub, price, seen)


NROWS = [_nrow("1437", "TWSE", 0, date(2026, 12, 3), "息", Decimal("0.62465200")),
         _nrow("1437", "TWSE", 0, date(2027, 1, 5), "息", Decimal("1.00000000")),             # 同一檔較遠的那筆不放
         _nrow("6523", "TPEx", 0, date(2026, 11, 26), "息", Decimal("4.00000000")),
         _nrow("2330", "TWSE", 0, D, "息", Decimal("5")),                                      # 資料日當天：notice_export 已濾掉
         _nrow("2454", "TWSE", 0, date(2026, 12, 1), "息", Decimal("3"), seen=date(2026, 11, 20)),   # last_seen 不是最新
         _nrow("00953B", "TWSE", 1, date(2026, 12, 3), "息", None),
         _nrow("2345", "TWSE", 0, date(2026, 12, 4), "權", Decimal("0"), Decimal("0.1"), None)]
NX_WANT = {"00953B": ["2026-12-03", "息", None], "1437": ["2026-12-03", "息", 0.624652], "2345": ["2026-12-04", "權", 0], "6523": ["2026-11-26", "息", 4]}


def check_nx(fn=None):
    fn, bad = fn or export.nx_latest, []
    try:
        got = fn(*export.notice_export(NROWS, {"TWSE": D, "TPEx": D}, D))
        if got != NX_WANT or list(got) != sorted(NX_WANT):
            bad.append(("內容", got))
        if json.dumps(got.get("6523"), ensure_ascii=False) != '["2026-11-26", "息", 4]':
            bad.append("整數")
        if fn({}, {}) != {} or fn({"9999": []}, {}) != {}:
            bad.append("空")
    except Exception as e:  # noqa: BLE001  反證可能讓函式丟例外
        bad.append(repr(e))
    return bad


def test_nx():
    assert check_nx() == []


def check_wiring(src=SRC):
    w = '    if nx := nx_latest(nx_stock, nx_etf):\n        latest["nx"] = nx'
    return (src.index("def notice_export(") < src.index("def nx_latest(") < src.index("def share_pct(") and src.count("nx_latest(") == 2 and w in src
            and src.index('latest["etfs"]["ix"] = {') < src.index(w) < src.index('latest["alerts"]["w"] = alert_watch(') < src.index('_write(SITE_DATA_DIR / "latest.json", latest)'))


def test_wiring():
    assert check_wiring()
    assert hashlib.sha1(inspect.getsource(export.etf_export).encode()).hexdigest()[:12] == "711fa2b7790c"
    assert SRC.count('**({"nx": nx_stock[code]} if code in nx_stock else {}),') == 1 and SRC.count('                E["nx"] = nx_etf[code]') == 1


def test_site_data():
    p = SITE / "data" / "latest.json"
    L = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    if "nx" not in L:
        print("  （site/data 尚未用第 47 輪匯出，略過）"); return
    nx, n = L["nx"], 0
    assert nx and list(nx) == sorted(nx)
    for c, v in nx.items():
        assert len(v) == 3 and v[0] > L["date"] and v[1] in ("息", "權", "權息") and (v[2] is None or v[2] >= 0), (c, v)
        f = SITE / "data" / ("stocks" if c in L["stocks"] else "etfp") / f"{c}.json"
        x = json.loads(f.read_text(encoding="utf-8"))["nx"][0]
        assert [x["d"], x["t"], x["c"]] == v, c                                          # 和個股 JSON 的第一筆相同
    for d in ("stocks", "etfp"):
        n += sum(b'"nx":' in f.read_bytes() for f in (SITE / "data" / d).glob("*.json"))
    assert n == len(nx), (n, len(nx))                                                     # 每檔有 nx 的個股 JSON 都在
    if L["date"] == DATE:
        assert len(nx) == 37 and nx["1437"] == ["2026-12-03", "息", 0.624652] and nx["6523"] == ["2026-11-26", "息", 4]
        assert nx["00901"] == ["2026-11-24", "息", 7] and nx["00953B"] == ["2026-12-03", "息", None] and nx["2345"] == ["2026-12-04", "權", 0]


# ─── F47-1b 頁頭標籤（驗收 4）──────────────────────────────────────
def check_tag(stk=STK, app=APP):
    js = "\n".join(_grab(app, n) for n in ("esc", "md", "nxKind")) + "\n" + "\n".join(_grab(stk, n) for n in ("dfmt", "nxText", "nxTag")) + """
const n = (d, t, c, o) => Object.assign({ d, t, c }, o || {});
console.log(JSON.stringify([nxTag([n('2026-12-03', '息', 0.624652), n('2027-01-05', '息', 1)], '1437', false), nxTag([n('2026-12-03', '息', null)], '00953B', true),
  nxTag([n('2026-12-04', '權', 0, { sr: 0.1, sp: null })], '2345', false), nxTag([n('2026-12-10', '權息', 1, { s: 50 })], '9999', false), nxTag(undefined, '2330', false), nxTag([], '2330', false)]));"""
    o = T._node(js)
    if o is None:
        return True
    head = stk[stk.index('<div class="tags">'):stk.index('id="starBtn"')]
    return (o[0] == '<a class="pill pill-nx" href="#/tools/dv?c=1437" title="即將除息 12/03：現金股利 0.624652 元（預告，以公司公告為準）">即將除息 12/03</a>'
            and o[1] == '<a class="pill pill-nx" href="#/tools/dv?c=00953B" title="即將除息 12/03：金額待公告（預告，以發行人公告為準）">即將除息 12/03</a>'
            and o[2] == '<a class="pill pill-nx" href="#/tools/dv?c=2345" title="即將除權 12/04：含現金增資，認購價尚未公告（預告，以公司公告為準）">即將除權 12/04</a>'
            and o[3].endswith('>即將除權息 12/10</a>') and o[4] == o[5] == ''
            and "data-gk" not in _grab(stk, "nxTag") and -1 < head.find(".join('')}${nxTag(data.nx, code, E)}") < head.find("<span class=\"pill\">${data.market === 'TWSE'"))


def test_tag():
    assert check_tag()


# ─── 自選頁（驗收 5～8、13、14）──────────────────────────────────
ST = {"i": "電子", "tv": 1.5, "f1": 0, "t1": 0, "d1": 0, "n1": 0, "fs": 0, "ts": 0, "s": 0, "c": 100, "ch": 1, "p": 1.0}
NAMES = ["勤益控", "達爾膚", "智邦", "如興", "大眾控", "台積電", "聯發科", "穩懋", "富邦金", "測甲", "測乙", "測丙"]
CODES = ["1437", "6523", "2345", "4414", "3701", "2330", "2454", "3105", "2881", "9901", "9902", "9903"]
E_ = lambda n, m, c, ch, r: {"n": n, "m": m, "c": c, "ch": ch, "p": 1.0, "v": 1, "tv": 1.0, **dict(zip(("r20", "r60", "ry", "rw"), r))}   # noqa: E731
LATEST = {"date": DATE, "flow_date": DATE, "holdings": {}, "alerts": {},
          "stocks": {c: {**ST, "n": n, **({"dsp": [DATE, "2026-11-30"]} if c == "2881" else {})} for c, n in zip(CODES, NAMES)},
          "etfs": {"rows": {"0050": E_("元大台灣50", "TWSE", 87.0, 2.55, (-18.62, -16.18, 35.31, 48.31)),
                            "00878": E_("國泰永續高股息", "TWSE", 28.05, 0.02, (-17.28, -10.04, 44.42, 54.23)),
                            "00679B": E_("元大美債20年", "TPEx", 26.33, 0.18, (2.32, 3.03, 0.83, 0.13)),
                            "00953B": E_("群益優選非投等債", "TWSE", 9.59, 0.01, (0.84, 1.48, 6.64, 8.64)),
                            "00901": E_("永豐智能車供應鏈", "TWSE", 34.18, 1.16, (-23.09, -23.0, 36.28, 48.48)),
                            "00930": E_("永豐ESG低碳高息", "TWSE", 20.18, 0.48, (-13.2, -11.98, 25.41, 30.53)),
                            "00958B": E_("永豐ESG銀行債15+", "TPEx", 9.08, 0.04, (2.02, 1.23, 0.22, 1.29)),
                            "00632R": E_("元大台灣50反1", "TWSE", None, None, (None, 1.5, None, None))},
                   "ix": {"20": -20.05, "60": -17.76, "y": 27.1, "w": 39.25}},
          "nx": {"1437": ["2026-12-03", "息", 0.624652], "6523": ["2026-11-26", "息", 4], "00953B": ["2026-12-03", "息", None],
                 "2345": ["2026-12-04", "權", 0], "4414": ["2026-12-08", "息", 0.00915], "3701": ["2026-12-04", "息", 0.199892],
                 "00901": ["2026-11-24", "息", 7], "00930": ["2026-11-24", "息", 0.75], "00958B": ["2026-11-24", "息", 0.042],
                 "9901": ["2026-12-01", "息", 0.29], "9902": ["2026-12-01", "息", 0.57], "9903": ["2026-12-01", "息", 0.123456789]}}
W7 = ["2330", "2454", "3105", "1437", "2881", "6523", "0050", "00878", "00679B", "00953B"]
SCREEN = {"d": DATE, "rmd": {}, "fqd": {}, "rows": {}}
W_NAMES = T32.NAMES + [n for n in T42.HOLD if n not in T32.NAMES and n != "shareWatch"] + ["EPF_COLS", "etfWatchPerf", "nxKind", "watchNx"]
HARN = r"""
const HL_KINDS = {}; const window = {};
const view = { innerHTML: '', addEventListener() {} }, els = {};
const $ = s => s === '#view' ? view : view.innerHTML.includes(`id="${s.slice(1)}"`) ? (els[s] = els[s] || { addEventListener(t, f) { this.f = f; } }) : null;
let STORE = {}, loads = 0;
const localStore = (k, f, v) => v === undefined ? (k in STORE ? STORE[k] : f) : (STORE[k] = v, f);
const onRowClick = () => {}, saveWatch = () => {}, loadScreen = () => { loads++; return new Promise(() => {}); }, location = { hash: '#/watch' };
const App = { latest: %s, watch: new Set() }, LAT = JSON.parse(JSON.stringify(App.latest)), SCR = %s;
function run(w, o, hold, lat) { App.latest = lat || LAT; App.watch = new Set(w); App.watchCols = undefined; App.screen = SCR; Object.assign(App, o || {});
  STORE = hold ? { hold: JSON.stringify(hold) } : {}; for (const k in els) delete els[k]; view.innerHTML = ''; renderWatch(); return view.innerHTML; }
const card = h => { const i = h.indexOf('<div class="card w-nx">'); return i < 0 ? '' : h.slice(i, h.indexOf('</div></div>', h.lastIndexOf('<div class="muted small">來自')) + 12); };
"""


def _watch(body, app=APP, stk=STK, tools=TOOLS):
    js = "\n".join(_grab(app, n) for n in W_NAMES) + "\n" + _grab(stk, "dfmt") + "\n" + HARN % (json.dumps(LATEST, ensure_ascii=False), json.dumps(SCREEN)) + tools + "\n" + body
    return T._node(js)


HEAD = '<div class="card w-nx"><div class="sec-h"><h2>即將除權息</h2><span class="muted small">預告，以公司或發行人公告為準</span></div>'
FOOT = ('<div class="muted small">來自證交所、櫃買中心的除權除息預告表，只列資料日之後的下一次；除權息日當天起改看個股頁的股利卡。估計可領 = 持股股數 × 預告每股現金，元以下捨去；'
        '未扣二代健保補充保費與匯費，配股不估算股數，以實際入帳為準。</div></div>')
R6523 = '<div class="al-row"><a href="#/stock/6523"><b>達爾膚</b></a>　<span class="nw">11/26 除息</span>　<span class="nw">現金股利 4 元</span>　<a class="small" href="#/tools/dv?c=6523">試算 →</a></div>'
R2345 = '<div class="al-row"><a href="#/stock/2345"><b>智邦</b></a>　<span class="nw">12/04 除權</span>　<a class="small" href="#/tools/dv?c=2345">試算 →</a></div>'
EST = {"6523": (1000, "4,000"), "1437": (2500, "1,561"), "4414": (1000, "9"), "00901": (1000, "7,000"), "00930": (1500, "1,125"), "00958B": (333, "13"),
       "3701": (1234, "246"), "9901": (100, "29"), "9902": (100, "57"), "9903": (100, None), "00953B": (2000, None), "2345": (100, None), "2330": (500, None)}


def _row(card, c):
    m = re.search(rf'<div class="al-row"><a href="#/stock/{c}">.*?</div>', card)
    return m.group(0) if m else ""


def check_watch(app=APP, stk=STK, tools=TOOLS):
    o = _watch("""
const H = %s, H2 = Object.assign({}, H, { '1437': [1000, 100] }), all = Object.keys(H), out = {};
for (const wc of ['flow', 'perf', 'fund', 'hold']) out[wc] = run(%s, { watchCols: wc });
out.c7 = card(out.flow); out.est = card(run(all, {}, H)); out.est2 = card(run(all, {}, H2));
const plain = Object.assign({}, LAT); delete plain.nx;
out.none = run(%s, {}, null, plain); out.other = run(%s, {}, null, Object.assign({}, plain, { nx: { '9999': ['2026-12-01', '息', 1] } }));
out.etfPerf = run(['0050', '00679B', '00632R'], { watchCols: 'perf', screen: null }); out.etfFlow = run(['0050'], { screen: null });
const nopf = JSON.parse(JSON.stringify(plain)); Object.values(nopf.etfs.rows).forEach(r => { delete r.r20; delete r.r60; delete r.ry; delete r.rw; });
out.nopf = run(['0050'], { watchCols: 'perf', screen: null }, null, nopf); out.loads = loads; out.store = Object.keys(STORE);
out.wt = etfWatchTable(['0050', '00878', '00679B', '00953B'].map(c => [c, LAT.etfs.rows[c]]));
console.log(JSON.stringify(out));""" % (json.dumps({c: [q, 1000] for c, (q, _) in EST.items()}), json.dumps(W7), json.dumps(W7), json.dumps(W7)), app, stk, tools)
    if o is None:
        return []
    bad, c7 = [], o["c7"]
    if not (c7.startswith(HEAD) and c7.endswith(FOOT) and re.findall(r'<div class="al-row"><a href="#/stock/(\w+)">', c7) == ["6523", "1437", "00953B"]):
        bad.append(("卡片", c7))
    if _row(c7, "6523") != R6523 or "現金股利 0.624652 元" not in _row(c7, "1437") or "金額待公告" not in _row(c7, "00953B") or "配息" in _row(c7, "00953B") or '"nw">估計可領' in c7:
        bad.append("列")
    for wc in ("flow", "perf", "fund", "hold"):                                          # 四個欄組都在 ETF 表之後、w-ev 之前
        h = o[wc]
        if not (h.count('class="card w-nx"') == 1 and h.rindex('data-etf="00953B"') < h.index('class="card w-nx"') < h.index('class="card w-ev"')):
            bad.append(("位置", wc))
    est, est2 = o["est"], o["est2"]
    for c, (q, v) in EST.items():
        r = _row(est, c)
        if (v is None) != ("估計可領" not in r) or v and f"　<span class=\"nw\">估計可領 {v} 元</span>　<a class=\"small\"" not in r:
            bad.append(("估計", c, r))
    if "估計可領 624 元" not in _row(est2, "1437") or _row(est, "2345") != R2345 or "金額待公告" not in _row(est, "00953B") or "估計" in _row(est, "9903") or _row(est, "2330"):
        bad.append("估計 2")
    if ("配息 7 元" not in _row(est, "00901") or "配息 0.042 元" not in _row(est, "00958B") or "現金股利 0.00915 元" not in _row(est, "4414")
            or len(re.findall(r'　<a class="small" href="#/tools/dv\?c=\w+">試算 →</a></div>', est)) != est.count('<div class="al-row">') != 0):
        bad.append("金額")
    if "w-nx" in o["none"] or o["none"] != o["other"]:
        bad.append("沒有 nx 要和改前相同")
    p = o["perf"]
    pcap = ('<div class="muted small tbl-cap">含息報酬為 11/23 收盤；加權指數同期：20 日 -20.05%、60 日 -17.76%、今年以來 +27.10%、52 週 +39.25%（價格指數，不含股息）</div>'
            '<div class="tbl-wrap"><table class="tbl"><thead><tr><th>ETF</th><th>收盤</th><th>20 日</th><th>60 日</th><th>今年以來</th><th>52 週</th></tr></thead>')
    pnote = ('<div class="muted small h-note">含息報酬 = 配息在除息日以參考價再投入同一檔，算法同 ETF 列表「表現」，不含手續費與稅；「--」= 基準日時本站還沒有這檔的成交；'
             '今天無成交時用最後成交的收盤。加權指數是價格指數，不含股息。</div>')
    r0050 = '<td class="num up">87</td><td class="num dn">-18.62%</td><td class="num dn">-16.18%</td><td class="num up">+35.31%</td><td class="num up">+48.31%</td></tr>'
    r679 = '<td class="num up">26.33</td><td class="num up">+2.32%</td><td class="num up">+3.03%</td><td class="num up">+0.83%</td><td class="num up">+0.13%</td></tr>'
    if not (pcap in p and pnote in p and r0050 in p and r679 in p and "<th>成交額</th>" not in p and '<div class="sec-h" style="margin-top:12px"><h2>ETF</h2></div>' in p
            and o["wt"] in o["flow"] and o["wt"] in o["fund"] and "當日行情" not in p):
        bad.append("表現：股票＋ETF")
    e = o["etfPerf"]
    seg = '<div class="seg" id="wcolSeg"><button data-v="flow" class="">行情</button><button data-v="perf" class="on">表現</button><button data-v="hold" class="">持股</button></div>'
    if not (seg in e and "存在這個瀏覽器裡，換裝置不會同步</span>" in e and '<td class="num flat">無成交</td><td class="num flat">--</td><td class="num up">+1.50%</td><td class="num flat">--</td>' in e
            and e.count('data-unwatch="') == 3 and '<tr data-etf="00632R">' in e and "<th>近一年配息</th>" not in e):
        bad.append(("表現：只有 ETF", e[:400]))
    if not ('<button data-v="perf" class="">表現</button>' in o["etfFlow"] and "<th>近一年配息</th>" in o["etfFlow"] and "。當日行情；成交量為張" in o["etfFlow"]):
        bad.append("只有 ETF 行情")
    if '<div class="seg" id="wcolSeg"><button data-v="flow" class="on">行情</button><button data-v="hold" class="">持股</button></div>' not in o["nopf"] or "<th>20 日</th>" in o["nopf"]:
        bad.append("舊 latest 沒有含息欄")
    if o["loads"] != 0 or o["store"] != []:                                                 # 只有 ETF 的表現不載入 screen.json；不寫新鍵
        bad.append(("載入／儲存", o["loads"], o["store"]))
    if T42.BAD.search(o["est"] + o["perf"] + e):
        bad.append("NaN")
    return bad


def test_watch():
    assert check_watch() == []


def check_storage(app=APP):
    w, n = _grab(app, "renderWatch"), _grab(app, "watchNx")
    return set(re.findall(r"localStore\('(\w+)'", w)) <= {"rspan"} and "localStore" not in n and "const H = holdLoad();" in n and "if (!W.length) return '';\n  const H" in n


def test_storage():
    assert check_storage()


def check_edit(app=APP, tools=TOOLS):
    lat = json.loads(json.dumps(LATEST))
    lat["stocks"].update({"1538": {**ST, "n": "正峰"}})
    edit = T42.EDIT.replace("s === '.h-all' ? all :", "s === '.w-nx' ? nxc : s === '.h-all' ? all :").replace("const IN = {}", "const nxc = { outerHTML: 'x' }, IN = {}")
    js = T42._src(app, tools, T42.BASE + T42.HOLD + ["nxKind", "watchNx"]) + _grab(STK, "dfmt") + "\nconst App = { latest: %s, watch: new Set() };\n" % json.dumps(lat, ensure_ascii=False)
    o = T._node(js + edit + """App.watch = new Set(['2330', '1538', '6523']);
const a = (put('6523', '1000', '50'), nxc.outerHTML), b = (put('6523', '', ''), nxc.outerHTML);
console.log(JSON.stringify([a, b, STORE.hold]));""")
    if o is None:
        return True
    return "估計可領 4,000 元" in o[0] and "w-nx" in o[1] and '"nw">估計可領' not in o[1] and o[2] == "{}"


def test_edit():
    assert check_edit()


# ─── F47-1d 今日卡（驗收 9）─────────────────────────────────────
def check_today(app=APP, tools=TOOLS):
    o = T42._run(T42.ROWS + """
const out = {};
App.watch = new Set(%s); out.a = watchToday(App.latest, rows);
App.watch = new Set(['1437']); out.one = watchToday(App.latest, rows);
App.watch = new Set(['2330', '2454', '3105', '2881', '9901', '6523', '0050', '00878', '4414']); out.late = watchToday(App.latest, rows);
delete App.latest.nx; App.watch = new Set(['1437']); out.none = watchToday(App.latest, rows);
console.log(JSON.stringify(out));""" % json.dumps(W7), app, tools, latest=json.loads(json.dumps(LATEST)))
    if o is None:
        return True
    return ('<a class="w-ev-l" href="#/watch">處置／注意 1 檔、即將除權息 3 檔 →</a>' in o["a"] and '<a class="w-ev-l" href="#/watch">即將除權息 1 檔 →</a>' in o["one"]
            and "處置／注意 1 檔、即將除權息 3 檔 →" in o["late"] and "w-ev-l" not in o["none"])


def test_today():
    assert check_today()


# ─── F47-2 指數卡（驗收 10）、F47-3 法人卡（驗收 11）、F47-4 夜盤（驗收 12）──────
def check_index(app=APP):
    js = ("Array.prototype.at = function (i) { return this[i < 0 ? this.length + i : i]; };\nconst spark = () => '';\n"
          + "\n".join(_grab(app, n) for n in ("fmt", "sgn", "cls", "md", "indexCard")) + """
const App = { latest: { date: '2026-11-23' } };
const x = (s0, c, n, from) => ({ date: '2026-11-23', c, ch: 1, p: 1, from, s: [s0].concat(Array(n - 2).fill(c), [c]) });
console.log(JSON.stringify([indexCard(x(45169.46, 36811.89, 60, '2026-08-25'), '加權指數'), indexCard(x(389.41, 270.90, 60, '2026-08-25'), '櫃買指數'),
  indexCard(x(100, 110, 30, '2026-10-09'), '加權指數'), indexCard(x(45169.46, 36811.89, 60, '2026-08-25'), '加權指數', false)]));""")
    o = T._node(js)
    if o is None:
        return True
    return ('<div class="s"><span class="dn">自 08/25 起 -18.5%</span></div>' in o[0] and '<span class="dn">自 08/25 起 -30.4%</span></div>' in o[1]
            and '<span class="up">自 10/09 起 +10.0%</span>（30 個交易日）</div>' in o[2] and " 起 " not in o[3] and "近 60 個交易日" not in app)


def test_index():
    assert check_index()


def check_chip(stk=STK):
    o = T._node("\n".join(_grab(APP, n) for n in ("fmt", "sgn", "cls", "yi")) + "\nconsole.log(JSON.stringify([506.77, 54.21, 0.01, null].map(yi)));")
    return ("['法人5日', yi(s?.n5), cls(s?.n5), `自營 ${yi(s?.d5)}`]," in stk and "const inCards = E ? [] : [['法人1日'" in stk
            and (o is None or o == ["+507億", "+54.2億", "0億", "--"]))


def test_chip():
    assert check_chip()


def check_night(app=APP):
    js = "\n".join(_grab(app, n) for n in ("esc", "fmt", "sgn", "cls", "md", "futuresHTML")) + r"""
const spreadHTML = () => '';
const F = (d, nd) => ({ name: '台指期', d, c: d.map(() => 34000), ch: d.map(() => 10), m: d.map(() => '202612'), v: d.map(() => 1), oi: d.map(() => 1),
  night: { date: nd, c: 33919, ch: -1881 } });
const n = h => (h.match(/夜盤（[^）]*）/) || [''])[0];
console.log(JSON.stringify([F(['2026-11-19', '2026-11-20', '2026-11-23'], '2026-11-23'), F(['2026-11-18', '2026-11-19', '2026-11-20'], '2026-11-20'),
  F(['2026-11-27', '2026-11-30', '2026-12-01'], '2026-12-01'), F(['2026-12-30', '2026-12-31', '2027-01-04'], '2027-01-04'),
  F(['2027-02-04', '2027-02-05', '2027-02-15'], '2027-02-15'), F(['2026-11-23'], '2026-11-23'), F(['2026-11-19', '2026-11-20'], '2026-11-23')].map(f => [n(futuresHTML(f)), futuresHTML(f).includes('前一夜盤')])));"""
    o = T._node(js)
    if o is None:
        return True
    return o == [["夜盤（11/20 15:00～11/21 05:00）", True], ["夜盤（11/19 15:00～11/20 05:00）", True], ["夜盤（11/30 15:00～12/01 05:00）", True],
                 ["夜盤（12/31 15:00～01/01 05:00）", True], ["夜盤（02/05 15:00～02/06 05:00）", True], ["夜盤（11/23 05:00）", True], ["夜盤（11/20 15:00～11/21 05:00）", False]]


def test_night():
    assert check_night()


# ─── F47-7 名詞（驗收 15）───────────────────────────────────────
def check_help(src=HELP):
    if T45.check_data(src) or T45.check_page(src):
        return False
    o = T45._page("hash = '#/help/tr'; rafs = []; window.renderHelp('tr'); rafs.forEach(f => f()); console.log(JSON.stringify([hash, view.innerHTML, Object.values(el).filter(e => e.n).map(e => e.id)]));", src)
    H = T45._data(src)
    if o is None or H is None:
        return "ETF 個股頁用原始價" not in src
    etf = [g for g in H if g[0] == "etf"][0][2]
    return (o[0] == "#/help/tr" and o[2] == ["help-tr"] and '<div class="help-t on" id="help-tr"><b>含息報酬</b>' in o[1] and o[1].count('class="help-t') == 42
            and [x[0] for x in etf] == ["units", "issuer", "tr"] and len(etf[2]) == 3 and "ETF 個股頁用原始價" not in src)


def test_help():
    assert check_help()


# ─── 用詞、node 14、版本與文件（驗收 16、17、20）─────────────────────
def _new_segs(app=APP, stk=STK, help_=HELP):
    seg = "".join(_grab(app, n) for n in ("nxKind", "watchNx", "etfWatchPerf")) + _grab(stk, "nxTag")
    seg += "".join(l for l in app.splitlines() + stk.splitlines() + CSS.splitlines() if "第 47 輪" in l or "自營 ${yi(s?.d5)}" in l)
    seg += "".join(l for l in help_.splitlines() if "['tr'," in l or "['adj'," in l)
    return seg


def check_words(app=APP, stk=STK, help_=HELP):
    seg = _new_segs(app, stk, help_) + "".join(l for l in README.splitlines() + app.splitlines() if "第 47 輪" in l or "自 ${md(x.from)} 起" in l)
    return all(w not in seg.replace("借券賣出", "") for w in ADVICE)


def test_words():
    assert check_words()


def test_node14():
    seg = _new_segs()
    for w in (".at(", "replaceAll", "||=", "&&=", "??="):
        assert w not in seg, w


def test_version_and_docs():
    for f in ("app.js", "stock.js", "app.css", "tools.js", "help.js"):
        v = hashlib.sha1((SITE / f).read_bytes()).hexdigest()[:8]
        assert f"{f}?v={v}" in HTML, f"index.html 要改成 {f}?v={v}"
    assert HTML.count("https://") == 2
    assert "python3 tests/test_iter47.py" in README
    r = next(l for l in README.splitlines() if l.startswith("- 即將除權息提醒（第 47 輪"))
    for s in ("`nx", "元以下捨去", "二代健保", "R60", "R61", "自營", "含息報酬", "42 個名詞"):
        assert s in r, s
    assert "第 23 輪" not in r
    assert "第 47 輪" in (ROOT / "docs" / "iterations" / "README.md").read_text(encoding="utf-8")


def test_pm_text():
    """畫面文字和 47/02-pm.md 二之一相同（PM 表格裡的字串出現在程式裡）。"""
    for s in ("即將除權息", "預告，以公司或發行人公告為準", "金額待公告", "估計可領", "試算 →", "自營 ", "含息報酬為 "):
        assert s in PM, s
    assert FOOT[len('<div class="muted small">'):-len("</div></div>")] in PM


# ─── 反證：原始碼改壞，對應的檢查要失敗 ─────────────────────────
def _mut_fn(old, new):
    src = inspect.getsource(export.nx_latest)
    assert src.count(old) == 1, old
    ns = dict(vars(export))
    exec(src.replace(old, new), ns)
    return ns["nx_latest"]


MUTANTS = [
    ("匯出放最後一筆", "fn", 'v[0]["d"], v[0]["t"], v[0]["c"]', 'v[-1]["d"], v[-1]["t"], v[-1]["c"]'),
    ("匯出空陣列也放", "fn", " if v}", "}"),
    ("匯出空的也輸出 nx", "src", '    if nx := nx_latest(nx_stock, nx_etf):\n        latest["nx"] = nx', '    latest["nx"] = nx_latest(nx_stock, nx_etf)'),
    ("標籤加 data-gk", "stk", '<a class="pill pill-nx" href=', '<a class="pill pill-nx" data-gk="x" href='),
    ("標籤用最後一筆", "stk", "title=\"${esc(nxText(nx[0], etf))}\">即將${nxKind(nx[0].t)} ${md(nx[0].d)}", "title=\"${esc(nxText(nx[0], etf))}\">即將${nxKind(nx[nx.length - 1].t)} ${md(nx[nx.length - 1].d)}"),
    ("標籤放在上市之後", "stk", ".join('')}${nxTag(data.nx, code, E)}\n            <span class=\"pill\">${data.market === 'TWSE' ? '上市' : '上櫃'}</span>",
     ".join('')}\n            <span class=\"pill\">${data.market === 'TWSE' ? '上市' : '上櫃'}</span>${nxTag(data.nx, code, E)}"),
    ("估計用浮點", "app", "fmt(Number(BigInt(H[c][0]) * q / 10n ** 8n))", "fmt(Math.floor(H[c][0] * x))"),
    ("估計四捨五入", "app", "BigInt(H[c][0]) * q / 10n ** 8n", "(BigInt(H[c][0]) * q + 5n * 10n ** 7n) / 10n ** 8n"),
    ("9 位小數也估計", "app", "tlBig(String(x), 8)", "tlBig(String(x), 9)"),
    ("不依日期排序", "app", ".sort((a, b) => NX[a][0] < NX[b][0] ? -1 : NX[a][0] > NX[b][0] ? 1 : 0)", ""),
    ("只列股票", "app", "NX[c] && (L.stocks[c] || R[c])", "NX[c] && L.stocks[c]"),
    ("現金 0 也寫金額待公告", "app", "(x == null ? '　<span class=\"nw\">金額待公告</span>'", "(!(x > 0) ? '　<span class=\"nw\">金額待公告</span>'"),
    ("ETF 也寫現金股利", "app", "${L.stocks[c] ? '現金股利' : '配息'}", "現金股利"),
    ("試算連結帶股數", "app", "<a class=\"small\" href=\"#/tools/dv?c=${c}\">試算 →</a></div>`; })", "<a class=\"small\" href=\"#/tools/dv?c=${c}&q=${H[c] ? H[c][0] : ''}\">試算 →</a></div>`; })"),
    ("卡片放在 ETF 表之前", "app", "      ${etfs.length ? `${stk ? '<div class=\"sec-h\" style=\"margin-top:12px\"><h2>ETF</h2>'",
     "      ${App.latest.nx ? watchNx() : ''}${etfs.length ? `${stk ? '<div class=\"sec-h\" style=\"margin-top:12px\"><h2>ETF</h2>'"),
    ("renderWatch 直接讀持股", "app", "  const pf = Object.values(R)", "  localStore('hold', null); const pf = Object.values(R)"),
    ("沒有 nx 也先讀持股", "app", "  if (!W.length) return '';\n  const H = holdLoad();", "  const H = holdLoad();\n  if (!W.length) return '';"),
    ("改持股不更新估計", "app", "  if (nx) nx.outerHTML = watchNx();", "  if (nx) nx.outerHTML;"),
    ("今日卡只算前 5 檔", "app", "W.filter(c => L.nx[c]).length", "W.slice(0, 5).filter(c => L.nx[c]).length"),
    ("表現仍用行情表", "app", "ep ? etfWatchPerf(etfs, App.latest.etfs.ix) : etfWatchTable(etfs)", "etfWatchTable(etfs)"),
    ("舊資料也有表現", "app", "r.rw != null), ep = pf && wc === 'perf';", "r.rw != null) || true, ep = pf && wc === 'perf';"),
    ("表現仍寫當日行情", "app", "(HV || ep ? '' : '<span class=\"muted small\">當日行情", "(HV ? '' : '<span class=\"muted small\">當日行情"),
    ("表現缺值顯示 0", "app", "${r[k] == null ? '--' : sgn(r[k]) + '%'}", "${sgn(r[k] == null ? 0 : r[k]) + '%'}"),
    ("指數卡改回近 60 個交易日", "app", "自 ${md(x.from)} 起 ${sgn(", "${x.s.length >= 60 ? '近 60 個交易日' : `自 ${md(x.from)} 起`} ${sgn("),
    ("夜盤結束日用歸屬日", "app", "${md(to)} 05:00）", "${md(N.date)} 05:00）"),
    ("法人卡沒有自營", "stk", "`自營 ${yi(s?.d5)}`]", "'']"),
    ("名詞 tr 加連結", "help", "和指數的差距越偏向 ETF。'],", "和指數的差距越偏向 ETF。', '看 ETF 列表', '#/etf'],"),
    ("名詞 adj 改回原文", "help", "個股 K 線可切換「原始」。ETF 個股頁的 K 線、52 週高低用原始價，近期表現用含息報酬。", "個股 K 線可切換「原始」，ETF 個股頁用原始價。"),
    ("用詞", "app", "以實際入帳為準。", "以實際入帳為準，不是建議。"),
]
CHECKS = {"fn": lambda f: not check_nx(f), "src": check_wiring,
          "stk": lambda s: check_tag(stk=s) and check_chip(s) and check_words(stk=s),
          "app": lambda a: (not check_watch(app=a) and check_storage(a) and check_edit(app=a) and check_today(app=a) and check_index(a)
                            and check_night(a) and check_words(app=a)),
          "help": lambda h: check_help(h) and check_words(help_=h)}


def test_contrast():
    node = T._node("console.log('1')") is not None
    for name, kind, a, b in MUTANTS:
        if kind == "fn":
            assert not CHECKS[kind](_mut_fn(a, b)), "反證沒有擋下：" + name
            continue
        src = {"src": SRC, "stk": STK, "app": APP, "help": HELP}[kind]
        assert src.count(a) == 1, (name, a)
        ok = CHECKS[kind](src.replace(a, b))
        assert not ok or not node and kind != "src", "反證沒有擋下：" + name


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_") and callable(f):
            print("==", n); f()
    print("全部通過")
