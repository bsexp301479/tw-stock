"""第 45 輪（不連網、不連資料庫）：名詞說明 #/help（F45-1～F45-4）與 QA44-03（F45-5）。
名詞文字和 docs/iterations/45/02-pm.md 二之一逐字比對；關鍵數字和程式常數綁在一起（改算法沒改 help.js 會失敗）。
有 node 時逐字取出 help.js、app.js、tools.js 的程式執行；檢查函式都接受要檢查的原始碼，test_contrast 改壞後重跑，確認會失敗。"""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
import test_iter34 as T  # noqa: E402
import test_iter39 as T39  # noqa: E402
import test_iter42 as T42  # noqa: E402

SITE, HTML, TOOLS, APP, STK = T.SITE, T.HTML, T.TOOLS, T.APP, T.STK
HELP = (SITE / "help.js").read_text(encoding="utf-8")
EXPORT = (ROOT / "twstock" / "export.py").read_text(encoding="utf-8")
PM = (ROOT / "docs" / "iterations" / "45" / "02-pm.md").read_text(encoding="utf-8")
ADVICE = set(T42.ADVICE) | {"主力", "籌碼乾淨", "進場", "退場", "吸籌", "出貨", "值得", "看好", "安全", "危險", "支撐", "壓力", "目標價", "上檔", "下檔"}   # test_iter43:511


def _data(src=HELP):
    return T._node(T._grab(src, "HELP") + "\nconsole.log(JSON.stringify(HELP));")


def _want():
    """02-pm.md 二之一的 8 張表 → [[組代號, 組名, [[代號, 名詞, 定義(, 連結文字, 網址)]]]]"""
    sec = PM[PM.index("## 二之一"):PM.index("## 二之二")]
    parts, out = re.split(r"\n### (.+?)（`(\w+)`）\n", sec)[1:], []
    for i in range(0, len(parts), 3):
        rows = []
        for k, n, d, l in re.findall(r"^\| ([a-z0-9]+) \| (.+?) \| (.+?) \|(.*?)\|$", parts[i + 2], re.M):
            m = re.fullmatch(r"(.+?) → `(#/[^`]+)`", l.strip())
            rows.append([k, n, d] + ([m.group(1), m.group(2)] if m else []))
        out.append([parts[i + 1], parts[i], rows])
    return out


# ─── 名詞資料（驗收 1～4）────────────────────────────────────────
def check_data(src=HELP):
    H = _data(src)
    if H is None:
        return []
    bad, ids = [], [g[0] for g in H] + [x[0] for g in H for x in g[2]]
    if H != _want():
        bad.append("和 02-pm.md 二之一不同")
    if len(H) != 8 or sum(len(g[2]) for g in H) != 41 or len(ids) != len(set(ids)):
        bad.append(("數量或代號重複", len(H), len(ids)))
    ranks = set(re.findall(r"\['([^']+)', '[^']+', '[^']+', -?1", T._grab(APP, "RANKS")))
    today = set(re.findall(r"\['(\w+)', '", T._grab(APP, "TODAY_TABS")))
    tools = set(re.search(r"!\[([^\]]+)\]\.includes\(tl\[1\]\)", APP).group(1).replace("'", "").split(", "))
    ok = lambda u: (u in ("#/bubble", "#/etf", "#/etf/active") or re.fullmatch(r"#/rank/(.+)", u) and u[7:] in ranks | {"screen"}
                    or re.fullmatch(r"#/today/\w+", u) and u[8:] in today or re.fullmatch(r"#/tools/\w+", u) and u[8:] in tools)
    links = [x[4] for g in H for x in g[2] if len(x) == 5]
    if len(links) != 24 or not all(ok(u) for u in links):
        bad.append(("連結", [u for u in links if not ok(u)], len(links)))
    text = "".join(x[2] for g in H for x in g[2])
    for w in ("0.15%", "0.3%", "2.11%", "2027", "2 萬"):                                       # 驗收 4：法規數字不寫進辭典
        if w in text:
            bad.append(w)
    return bad


def test_data():
    assert check_data() == []


# 驗收 3：(辭典裡的字, 程式裡的字)。改了算法沒改辭典（或反過來）都會失敗
SYNC = [("KD(9,3,3)", "STK", "function calcKD(H, L, C, n = 9)"), ("RSI(14)", "STK", "function calcRSI(C, n = 14)"),
        ("12 日 EMA − 26 日 EMA", "STK", "ef = ema(closes, 12), es = ema(closes, 26)"), ("DIF 的 9 日 EMA", "STK", "dea = ema(dif, 9)"),
        ("今日成交額 ÷ 前 20 個交易日平均成交額", "EXPORT", "prior = yi[-21:-1]"), ("融資 1,000 張以上", "APP", "const MARGIN_BASE = 1000;"),
        ("超過 400 張或超過 1,000 張", "STK", "['持股超過 400 張', fmt(sh.b[i], 2)"), ("散戶指 50 張以下", "STK", "['50 張以下', fmt(sh.r[i], 2)"),
        ("約 242 個交易日", "STK", "valuation?.TWSE?.days ?? 242")]


def check_sync(src=HELP, **code):
    code = dict({"STK": STK, "APP": APP, "EXPORT": EXPORT}, **code)
    return [(a, b) for a, k, b in SYNC if a not in src or b not in code[k]]


def test_sync():
    assert check_sync() == []


# ─── 頁面（驗收 5～8）────────────────────────────────────────────
def _page(body, src=HELP):
    return T._node("const window = {}; let hash = '', rafs = [];\n"
                   "const history = { state: { k: 1 }, replaceState(s, t, u) { hash = u; } }, requestAnimationFrame = f => rafs.push(f);\n"
                   "let gone = false; const view = { innerHTML: '' }, el = {}, document = { getElementById: id => id === 'view' ? view : gone ? null : (el[id] = el[id] || { id, n: 0, scrollIntoView() { this.n++; } }) };\n"
                   + src + "\n" + body)


TOP = ('<section class="sec card"><div class="sec-h"><h2>名詞說明</h2></div><div class="muted small">本站各頁用到的名詞與本站的算法；官方或其他網站的定義可能不同。</div>'
       '<div class="help-g"><a class="chip" href="#/help/flow">資金流</a><a class="chip" href="#/help/px">價量與技術</a><a class="chip" href="#/help/credit">信用交易</a>'
       '<a class="chip" href="#/help/chip">籌碼</a><a class="chip" href="#/help/fund">基本面</a><a class="chip" href="#/help/div">股利</a>'
       '<a class="chip" href="#/help/fut">期貨</a><a class="chip" href="#/help/etf">ETF</a></div></section>')
END = '<div class="muted small">名詞說明只描述算法與定義，不是買賣訊號。</div>'
VR = ('<div class="help-t on" id="help-vr"><b>量比</b><div>今日成交額 ÷ 前 20 個交易日平均成交額（無成交日以 0 計）。大於 1 代表今天成交比平常多。'
      '　<a href="#/rank/vr">看量比排行 →</a></div></div>')
GRP = '<div class="help-t" id="help-grp"><b>類股、產業鏈、概念股</b><div>類股是證交所、櫃買中心的產業別；產業鏈與概念股是本站整理的分類，同一檔股票可能出現在多個族群。</div></div>'


def check_page(src=HELP):
    o = _page("""const out = [];
for (const a of ['vr', 'credit', 'xyz', undefined]) {
  hash = '#/help' + (a ? '/' + a : ''); rafs = []; for (const k in el) delete el[k];
  window.renderHelp(a); rafs.forEach(f => f());
  out.push([hash, view.innerHTML, Object.values(el).filter(e => e.n).map(e => e.id), rafs.length]);
}
window.renderHelp('vr'); gone = true; let err = ''; try { rafs.forEach(f => f()); } catch (e) { err = String(e); }   // 捲動前已換到別頁
console.log(JSON.stringify(out.concat([err])));""", src)
    if o is None:
        return []
    bad = ["已換頁仍捲：" + o[-1]] if o[-1] else []
    for (h, html, sc, nr), want in zip(o, (["#/help/vr", ["help-vr"], 1], ["#/help/credit", ["help-credit"], 1], ["#/help", [], 0], ["#/help", [], 0])):
        if [h, sc, nr] != want:
            bad.append((h, sc, nr))
        secs = re.findall(r'<section class="sec card" id="help-(\w+)"><div class="sec-h"><h2>(.+?)</h2></div>', html)
        if not (html.startswith(TOP) and html.endswith(END) and secs == [(g[0], g[1]) for g in _want()] and GRP in html
                and html.count('class="help-t') == 41 and html.count(' on"') == (h == "#/help/vr")):
            bad.append(("版面", h))
    if VR not in o[0][1] or VR in o[1][1] or VR.replace(" on", "") not in o[1][1]:
        bad.append("標示")
    return bad


def test_page():
    assert check_page() == []


def test_route():
    js = T._grab(APP, "esc") + "\n" + T._grab(APP, "scrollAt") + "\nlet scrollKey = null;\n" + T._grab(APP, "route") + r"""
let hash = '', seen = [];
const location = { get hash() { return hash; } };
const history = { state: null, replaceState(s, t, u) { this.state = s; if (u) hash = u; } };
const window = { scrollTo() {} };
const document = { title: '', querySelectorAll: () => [] }, $ = () => null, App = {};
const disposeFuturesChart = () => {}, renderToday = async () => {};
const routes = { help: async arg => { seen.push([arg, hash, document.title]); } };
(async () => {
  for (const h of ['#/help', '#/help/vr']) { hash = h; history.state = null; await route(); }
  console.log(JSON.stringify(seen));
})();"""
    o = T._node(js)
    if o is not None:
        assert o == [[None, "#/help", "名詞說明｜台股資金流"], ["vr", "#/help/vr", "名詞說明｜台股資金流"]], o
    assert "  help: arg => window.renderHelp(arg),                   // 第 45 輪：名詞說明 #/help、#/help/代號（help.js）\n" in APP


# ─── 入口（驗收 10）──────────────────────────────────────────────
def test_entry():
    top, bot = HTML[HTML.index('<header class="top">'):HTML.index("</header>")], HTML[HTML.index('<nav class="bottom"'):]
    btn = '<a class="theme-btn help-btn" href="#/help" aria-label="名詞說明" title="名詞說明">?</a>'
    assert btn in top and top.index(btn) < top.index('<button class="theme-btn" id="themeBtn" type="button"></button>')
    assert '<footer class="foot wrap"><a href="#/help">名詞說明</a>　資料來源：臺灣證券交易所' in HTML
    assert top.count("data-tab=") == 6 and bot[:bot.index("</nav>")].count("data-tab=") == 6
    assert HTML.index('src="tools.js?v=') < HTML.index('src="help.js?v=') and len(re.findall(r'src="help\.js[?"]', HTML)) == 1


# ─── QA44-03（驗收 11）───────────────────────────────────────────
NOTE = "可領現金元以下捨去；不足 1 股依{0}公告折付現金，可在期限內湊股；實際以{0}發放為準。"


def check_dv(src=TOOLS):
    o = T39._out([T39._st(p="100", c="1", k=k) for k in ("e", "s")], src)
    if o is None:
        return []
    return [] if NOTE.format("發行人") in o[0] and NOTE.format("公司") in o[1] and "發行人" not in o[1] else [o]


def test_dv_etf():
    assert check_dv() == []


# ─── ?v=、node 14、用詞、文件（驗收 14～16）────────────────────────
# ─── CSS（QA45-01）：本輪那一行整行鎖住（捲動留白、標示、連結藍色不拆行）─────────
CSS_LINE = (".help-btn{font-size:16px;font-weight:700;line-height:1;text-decoration:none}.help-g{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}"
            ".help-t{padding:8px 6px;border-top:1px solid var(--border);scroll-margin-top:calc(var(--top-h,56px) + 8px)}.sec-h+.help-t{border-top:0}"
            ".help-t a{color:var(--blue);white-space:nowrap}.help-t.on{background:var(--card2);box-shadow:inset 3px 0 0 var(--blue)}   /* 第 45 輪：名詞說明 */")


def check_css(css=T.CSS):
    return [] if css.splitlines().count(CSS_LINE) == 1 else ["app.css 第 45 輪那一行"]


def test_css():
    assert check_css() == []


def check_words(src=HELP):
    return [w for w in ADVICE if w in src.replace("借券賣出", "")] + \
        [w for w in ("?.", "??", ".at(", "replaceAll", "||=", "&&=", "structuredClone", "findLast") if w in src]


def test_versions_words_docs():
    for f in ("app.css", "app.js", "tools.js", "help.js"):
        v = hashlib.sha1((SITE / f).read_bytes()).hexdigest()[:8]
        assert f'{f}?v={v}"' in HTML, f"site/index.html 的 {f}?v= 請改成 {v}"
    assert HTML.count("https://") == 2 and "http" not in HELP and "fetch(" not in HELP and "localStorage" not in HELP
    assert check_words() == []
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "python3 tests/test_iter45.py" in readme and "第 45 輪" in readme and "help.js" in readme
    assert "第 45 輪" in (ROOT / "docs" / "iterations" / "README.md").read_text(encoding="utf-8")


# ─── 反證 ─────────────────────────────────────────────
MUTANTS = [  # (名稱, 原始碼, 原字串, 改壞後, 檢查)
    ("改錯一個字", HELP, "正為買超、負為賣超", "正為買超，負為賣超", check_data),
    ("少一個名詞", HELP, "    ['pb', '淨值比', '股價 ÷ 每股淨值，本站用證交所、櫃買中心公布的值。'],\n", "", check_data),
    ("連到不存在的排行", HELP, "'#/rank/vr'", "'#/rank/vol'", check_data),
    ("連到不存在的今日分頁", HELP, "'看今日期貨', '#/today/fut'],\n    ['near'", "'看今日期貨', '#/today/futures'],\n    ['near'", check_data),
    ("代號重複", HELP, "['near', '近月", "['basis', '近月", check_data),
    ("寫進稅率", HELP, "證交稅率與期限以「工具 › 交易成本」為準", "證交稅 0.15%", check_data),
    ("KD 參數不同步", HELP, "KD(9,3,3)", "KD(14,3,3)", check_sync),
    ("大戶門檻不同步", STK, "['持股超過 400 張', fmt(sh.b[i], 2)", "['持股超過 500 張', fmt(sh.b[i], 2)", lambda s: check_sync(STK=s)),
    ("量比天數不同步", EXPORT, "prior = yi[-21:-1]", "prior = yi[-11:-1]", lambda s: check_sync(EXPORT=s)),
    ("沒有標示", HELP, "${x[0] === id ? ' on' : ''}", "", check_page),
    ("組代號也標示", HELP, "x[0] === id ? ' on'", "(x[0] === id || id) ? ' on'", check_page),
    ("沒有延後捲動", HELP, "requestAnimationFrame(() => { const e = document.getElementById('help-' + id); if (e) e.scrollIntoView(); });",
     "{ const e = document.getElementById('help-' + id); if (e) e.scrollIntoView(); }", check_page),
    ("已換頁仍捲", HELP, "if (e) e.scrollIntoView();", "e.scrollIntoView();", check_page),
    ("不存在不改網址", HELP, "if (arg && !id) history.replaceState(history.state, '', '#/help');", "", check_page),
    ("沒有頁尾", HELP, "名詞說明只描述算法與定義，不是買賣訊號。", "", check_page),
    ("ETF 仍寫公司", TOOLS, "不足 1 股依${e ? '發行人' : '公司'}公告", "不足 1 股依公司公告", check_dv),
    ("發行人與公司對調", TOOLS, "實際以${e ? '發行人' : '公司'}發放", "實際以${e ? '公司' : '發行人'}發放", check_dv),
    ("用到禁用詞", HELP, "不等於看空", "不等於看好", check_words),
    ("node 14 不支援", HELP, "ids.indexOf(arg) >= 0 ? arg : ''", "ids.includes(arg) ? arg : (arg ?? '')", check_words),
    ("拿掉 CSS 那一行", T.CSS, CSS_LINE + "\n", "", check_css),                                                          # QA45-01
    ("沒有捲動留白", T.CSS, ";scroll-margin-top:calc(var(--top-h,56px) + 8px)}.sec-h", "}.sec-h", check_css),                  # QA45-01
]


def test_contrast():
    node = T._node("console.log('1')") is not None
    for name, src, a, b, check in MUTANTS:
        assert src.count(a) == 1, (name, a)
        if node or check in (check_words, check_css) or "同步" in name:
            assert check(src.replace(a, b)), "反證沒有擋下：" + name


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_") and callable(f):
            print("==", n); f()
    print("全部通過")
