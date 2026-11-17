"""第 32 輪（不連網、不連資料庫）：F32-1 自選頁「資金／表現／基本面」欄位組、F32-2 自選清單分享連結。
有 node 時逐字取出 app.js 的函式執行（node 14 可跑：不用 .at()、replaceAll）。"""
import json
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "site" / "app.js").read_text(encoding="utf-8")
CSS = (ROOT / "site" / "app.css").read_text(encoding="utf-8")


def _grab(src, name):
    if name == "SCR_COLS":                                     # 多行物件，內含以「;」結尾的行
        i = src.index("const SCR_COLS = {")
        return src[i:src.index("\n};", i) + 3]
    m = re.search(rf"^(?:async )?function {name}\(", src, re.M)
    if m:
        i, n = src.index("{", src.index(")", m.start())), 0
        for j in range(i, len(src)):
            n += {"{": 1, "}": -1}.get(src[j], 0)
            if n == 0:
                return src[m.start():j + 1]
    m = re.search(rf"^(?:const|let) {name}\b", src, re.M)
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


NAMES = ["fmt", "pfmt", "sgn", "cls", "pctCell", "yi", "esc", "md", "streakTxt", "holdTag", "alertBadge", "hlTag",
         "segHTML", "onSeg", "flowNote", "wCtl", "stockTable", "spanSeg", "onEtfRow", "watchGestures", "renderWatch", "etfWatchTable",
         "isNum", "MARGIN_BASE", "screenRow", "revMonth", "finQ", "finTag", "REV_BASE", "revLow", "epsLow", "spct", "int0", "SCR_COLS",
         "CAP_TAG", "screenTable", "WATCH_COLS", "watchColTable", "watchAddList", "watchAddNote"]
ST = {"i": "半導體", "tv": 10.5, "f1": 1, "t1": 0, "d1": 0, "n1": 1, "fs": 1, "ts": 0, "s": 1}
LATEST = {"date": "2026-11-17", "flow_date": "2026-11-17", "holdings": {},
          "stocks": {"2330": {**ST, "n": "台積電", "c": 1400, "p": -1.0, "h52": 1500, "pe": 25.31, "dy": 1.5, "pb": 7.1},
                     "2317": {**ST, "n": "鴻海", "c": 200, "p": 2.0, "h52": 250, "pe": None, "dy": None, "pb": None},
                     "6666": {**ST, "n": "測<試>", "c": 50, "p": 0.0, "h52": None}},
          "etfs": {"rows": {"0050": {"n": "元大台灣50", "m": "TWSE", "c": 70.1, "ch": 0.2, "p": 0.29, "v": 50000, "tv": 35.1}}}}
SCREEN = {"d": "2026-11-17", "rmd": {"202610": 2}, "fqd": {"202603": 2},
          "rows": {"2330": {"r5": -5.03, "r20": -10.33, "r60": -8.55, "b20": -6.65, "rm": 202610, "ry": 59.71, "rb": 367473051,
                            "fq": 202603, "ey": 68.7, "eb": 17.44, "pbp": 14, "cap": 0},
                   "2317": {"r5": 1.5, "r20": None, "r60": 3, "b20": 0.5, "rm": 202609, "ry": 3.2, "rb": 99999999,
                            "fq": 202602, "ey": None, "eq": -0.2, "eb": 0.3, "pbp": None, "cap": 1}}}
HARNESS = """
const HL_KINDS = {};
const App = { latest: %s, watch: new Set() };
const view = { innerHTML: '', addEventListener() {} }, els = {};
const $ = s => s === '#view' ? view : view.innerHTML.includes(`id="${s.slice(1)}"`) ? (els[s] = els[s] || { addEventListener(t, f) { this.f = f; } }) : null;
let saved = [], loads = 0;
const localStore = (k, f) => f, onRowClick = () => {}, saveWatch = () => saved.push([...App.watch]);
const loadScreen = () => { loads++; return new Promise(() => {}); };
const location = { hash: '#/watch' };
function run(w, o) { App.watch = new Set(w); Object.assign(App, o); for (const k in els) delete els[k]; view.innerHTML = ''; renderWatch(); return view.innerHTML; }
""" % json.dumps(LATEST, ensure_ascii=False)


def _js(body):
    return "\n".join(_grab(APP, n) for n in NAMES) + HARNESS + body


# ─── F32-1：欄位組 ───────────────────────────────────────
def test_col_sets():
    o = _node(_js(f"""
const S = {json.dumps(SCREEN, ensure_ascii=False)};
const w = ['2330', '2317', '0050'];
console.log(JSON.stringify({{
  flow: run(w, {{ screen: S, watchCols: undefined }}), perf: run(w, {{ watchCols: 'perf' }}), fund: run(w, {{ watchCols: 'fund' }}),
  edit: run(w, {{ watchCols: 'perf', watchEdit: true }}), loads }}));"""))
    if o is None:
        return
    f, p, u = o["flow"], o["perf"], o["fund"]
    # 資金：照舊（法人欄、1日／5日），欄位組鈕「資金」選中
    assert "<th>外資1日</th>" in f and "rspanSeg" in f and '<div class="seg" id="wcolSeg"><button data-v="flow" class="on">資金</button>' in f
    # 表現：5／20／60 日報酬、距 52 週高、MA20 乖離；沒有 1日／5日
    assert "<th>5日報酬</th><th>20日報酬</th><th>60日報酬</th><th>距52週高</th><th>MA20乖離</th>" in p
    assert "rspanSeg" not in p and "<th>外資1日</th>" not in p and '<button data-v="perf" class="on">表現</button>' in p
    assert '<td class="num dn">-5.03%</td><td class="num dn">-10.33%</td><td class="num dn">-8.55%</td><td class="num ">6.67%</td><td class="num dn">-6.65%</td>' in p
    assert '<td class="num up">+1.50%</td><td class="num flat">--</td><td class="num up">+3.00%</td><td class="num ">20.00%</td>' in p   # 缺值 --
    assert "報酬、乖離為 11/17 收盤；距 52 週高 = (52 週高 − 收盤) ÷ 52 週高" in p
    # 基本面：營收年增（月）、EPS 年增（季）、本益比、殖利率、淨值比位置；月份、季別不同時標示；缺值 --；股本變動
    assert "<th>營收年增（10 月）</th><th>EPS年增（Q3）</th><th>本益比</th><th>殖利率</th><th>淨值比位置</th>" in u
    assert '<td class="num up">+59.71%</td><td class="num up">+68.70%</td><td class="num ">25.31</td><td class="num up">+1.50%</td><td class="num ">14%</td>' in u
    assert "+3.20%<span class=\"sub2\">（9月）</span>" in u and '<td class="num flat">--</td><td class="num ">--</td><td class="num flat">--</td><td class="num ">--</td>' in u
    assert p.count("<th>成交額</th>") == u.count("<th>成交額</th>") == 1 and f.count("<th>成交額</th>") == 2   # 表現、基本面的股票表不列成交額（ETF 表照舊）
    assert "股本變動" in u and "data-unwatch" in u                              # 編輯用的 ✕、≡ 在每列（隱藏，編輯模式才顯示）
    assert '<section class="sec watch editing">' in o["edit"] and o["edit"].count('class="wh"') == 3   # 股票 2 列＋ETF 1 列
    # ETF 表三組都一樣
    assert all('data-etf="0050"' in x for x in (f, p, u))
    assert o["loads"] == 0                                                      # 已載入時不重載


def test_screen_loading_and_missing():
    o = _node(_js("""
const w = ['2330'];
const loading = run(w, { screen: undefined, watchCols: 'fund' }), l1 = loads;
const none = run(w, { screen: null, watchCols: 'fund' });
console.log(JSON.stringify({ loading, l1, none }));"""))
    if o is None:
        return
    assert '<div class="empty">載入中…</div>' in o["loading"] and o["l1"] == 1    # 第一次切到表現、基本面才載入 screen.json
    n = o["none"]                                                               # screen.json 不存在：只有資金
    assert "wcolSeg" not in n and "表現、基本面資料尚未產生" in n and "<th>外資1日</th>" in n and "rspanSeg" in n


def test_no_new_storage_keys():
    for n in ("renderWatch", "watchColTable", "watchAddList", "watchAddNote", "shareWatch"):
        g = _grab(APP, n)
        assert "localStorage" not in g and "sessionStorage" not in g
        assert set(re.findall(r"localStore\('(\w+)'", g)) <= {"rspan"}, n
    assert "App.watchCols = v; renderWatch();" in APP


# ─── F32-2：分享連結 ─────────────────────────────────────
def test_add_list():
    big = [str(1000 + i) for i in range(205)]
    o = _node(_js(f"""
const S = App.latest.stocks, R = App.latest.etfs.rows;
const t = (a, w) => {{ App.watch = new Set(w); App.watchAdd = a; return watchAddList(S, R); }};
console.log(JSON.stringify([
  t(['2317', '0050', '2317', '9999', '', '0050'], ['2330']),
  t(['2330', '2317'], ['2330', '2317']),
  t(['<img src=x onerror=1>', '23 30', '00050a', '2317"'], []),
  t({json.dumps(big)}, []),
  t(['0050', '2330'], ['2317']),
]));"""))
    if o is None:
        return
    a, b, c, d, e = o
    assert a == {"more": False, "ok": ["2317", "0050"], "add": ["2317", "0050"], "bad": ["9999"]}   # 去重、空字串不算
    assert b["add"] == [] and b["ok"] == ["2330", "2317"]
    assert c["add"] == [] and len(c["bad"]) == 4
    assert d["more"] is True and len(d["bad"]) == 200                         # 只讀前 200 個
    assert e["add"] == ["0050", "2330"]                                        # 照連結順序


def test_add_confirm_and_merge():
    o = _node(_js("""
const a = run(['6666', '2330'], { watchAdd: ['2317', '0050', '2330', '9999', '<b>x'] });
els['#watchAddOk'].f(); const after = [...App.watch], left = App.watchAdd, b = view.innerHTML;
run(['2330'], { watchAdd: ['2317'] }); els['#watchAddNo'].f(); const cancel = [...App.watch], c = view.innerHTML;
const d = run(['2330'], { watchAdd: ['2330', 'abc'] });
console.log(JSON.stringify({ a, after, left, b, saved, cancel, c, d }));"""))
    if o is None:
        return
    a = o["a"]
    assert "要把以下 2 檔加入自選嗎？鴻海、元大台灣50　<button class=\"chip\" id=\"watchAddOk\">加入</button>" in a
    assert "1 檔已在自選" in a and "略過 2 個不認得的代號：9999、&lt;B&gt;X" in a and "<b>x" not in a.lower().replace("<b>台", "")
    assert o["after"] == ["6666", "2330", "2317", "0050"] and o["saved"] == [o["after"]]   # 原順序保留，新的接在後面，存一次
    assert o["left"] is None and "watchAddOk" not in o["b"]
    assert o["cancel"] == ["2330"] and "watchAddNo" not in o["c"]                       # 取消不加入
    assert "分享連結裡沒有可以加入的股票。" in o["d"] and "watchAddOk" not in o["d"]


def test_route_share_link():
    js = _grab(APP, "esc") + "\n" + _grab(APP, "scrollAt") + "\nlet scrollKey = null;\n" + _grab(APP, "route") + r"""
let hash = '', seen = [];
const location = { get hash() { return hash; } };
const history = { state: null, replaceState(s, t, u) { this.state = s; if (u) hash = u; } };
const window = { scrollTo() {} };
const document = { title: '', querySelectorAll: () => [] }, $ = () => null, App = {};
const disposeFuturesChart = () => {}, renderToday = async () => { seen.push('today'); };
const routes = { watch: async () => { seen.push(['watch', hash, App.watchAdd]); } };
(async () => {
  hash = '#/watch?add=2330,0050,%3Cx%3E'; await route(); const a = hash;
  hash = '#/watch/abc'; history.state = null; await route(); const b = [hash, App.watchAdd];
  hash = '#/today'; await route(); const c = App.watchAdd;
  console.log(JSON.stringify({ seen, a, b, c }));
})();"""
    o = _node(js)
    if o is None:
        return
    assert o["seen"][0] == ["watch", "#/watch", ["2330", "0050", "%3Cx%3E"]] and o["a"] == "#/watch"   # 開自選頁、網址換回
    assert o["b"] == ["#/watch", ["2330", "0050", "%3Cx%3E"]]                 # D28-08 照舊；還沒回答前留著
    assert o["c"] is None                                                      # 離開自選頁就不再詢問
    assert "if ((page === 'watch' || page === 'bubble') && arg) history.replaceState(history.state, '', '#/' + page);" in APP


def test_share_source():
    g = _grab(APP, "shareWatch")
    assert "'#/watch?add=' + [...App.watch].filter(c => S[c] || R[c]).join(',')" in g          # 只帶代號
    assert "navigator.share" in g and "navigator.clipboard.writeText(url)" in g and "e.name === 'AbortError'" in g
    w = _grab(APP, "renderWatch")
    assert '<button class="chip" id="watchShare">分享清單</button>' in w and '<input class="w-url" readonly value="${esc(App.watchShare.url)}">' in w
    assert ".w-url{display:block;width:100%" in CSS


def test_no_advice_words():
    seg = "".join(_grab(APP, n) for n in ("renderWatch", "watchColTable", "watchAddList", "watchAddNote", "shareWatch", "WATCH_COLS"))
    seg += "".join(l for l in APP.splitlines() + CSS.splitlines() if "第 32 輪" in l)
    for w in ("買進", "賣出", "反彈", "見底", "買點", "超賣", "超買", "推薦", "強勢", "飆股", "勝率", "亮點", "建議", "低估", "高估", "超跌", "便宜"):
        assert w not in seg, w


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_") and callable(f):
            print("==", n); f()
    print("全部通過")
