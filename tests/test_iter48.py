"""第 48 輪（不連網、不連資料庫）：多檔報酬率比較 F42-10（F48-1 匯出 ix.json、F48-2 compare.js 純函式、F48-3 比較頁、F48-4 入口）。
export.ix_export 用自造資料測；有 node 時取出 compare.js 的函式＋stock.js 的 adjFactors 執行（node 14 可跑）：全部 pf／epf 逐列比對、
docs/iterations/48/02-pm.md 的手算例逐位、網址正規化、假 DOM 跑 renderCompare 比對畫面文字。最後的 test_contrast 把原始碼改壞（反證），確認對應的檢查會失敗。"""
import hashlib
import inspect
import json
import re
import subprocess
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
from twstock import export  # noqa: E402
import test_iter34 as T  # noqa: E402
import test_iter47 as T47  # noqa: E402

SITE, HTML, APP, STK = T.SITE, T.HTML, T.APP, T.STK
CMP = (SITE / "compare.js").read_text(encoding="utf-8")
DATA = SITE / "data"
SRC = (ROOT / "twstock" / "export.py").read_text(encoding="utf-8")
README = (ROOT / "README.md").read_text(encoding="utf-8")
PM = (ROOT / "docs" / "iterations" / "48" / "02-pm.md").read_text(encoding="utf-8")
ADVICE = set(T47.ADVICE) | {"利多", "利空", "看多", "看空", "轉強", "轉弱", "強於大盤", "弱於大盤", "贏過", "輸給", "抗跌", "獲利能力佳", "惡化"}
DATE = "2026-11-24"
_grab = T._grab
FNS = ("cmpEvents", "cmpAdj", "cmpBase", "cmpAt", "cmpStats", "cmpLine", "cmpCalc", "cmpPick", "cmpNorm", "cmpR")


def _node(js):
    """node 執行；反證可能讓程式丟例外 → "ERR"（檢查失敗），沒有 node → None（略過）。"""
    try:
        return T._node(js)
    except subprocess.CalledProcessError:
        return "ERR"


def _js(cmp=CMP, stk=STK, app=APP):
    """node 片段：app.js 的格式函式＋stock.js 的 adjFactors＋compare.js 的純函式與常數。"""
    return "\n".join([_grab(app, n) for n in ("fmt", "sgn", "cls", "esc", "md")] + [_grab(stk, "adjFactors")] +
                     [_grab(cmp, n) for n in ("CMP_MAX",) + FNS + ("cmpUrl", "pc")]) + "\nconst fs = require('fs');\n"


# ─── F48-1 匯出 ix.json（驗收 1、2）────────────────────────────────
def check_ix(fn=None):
    fn = fn or export.ix_export
    d = [date(2025, 10, 30), date(2025, 10, 31), date(2025, 11, 3)]
    got = fn(d, {d[0]: Decimal("28287.53"), d[2]: Decimal("28500.10")})
    return (list(got) == ["d", "TAIEX"] and got == {"d": ["2025-10-30", "2025-10-31", "2025-11-03"], "TAIEX": [28287.53, None, 28500.1]}
            and json.dumps(got, separators=(",", ":")) == '{"d":["2025-10-30","2025-10-31","2025-11-03"],"TAIEX":[28287.53,null,28500.1]}')


def test_ix_export():
    assert check_ix()


def check_wiring(src=SRC):
    w = '    _write(SITE_DATA_DIR / "ix.json", ix_export(p_days, idx_close["TWSE"]))'
    i = src.find(w)
    return (src.count(w) == 1 and src.count("ix_export(") == 2 and src.index("def index_return(") < src.index("def ix_export(") < src.index("def stock_perf(")
            and src.index("    w52_start = latest_date - timedelta(days=365)") < i < src.index("    for code, rows in prices.items():\n        info = stocks.get(code)")
            and all(w not in src[src.index("def etf_export("):src.index("def _load_holdings(")] for w in ("ix.json", "ix_export")))


def test_wiring():
    assert check_wiring()
    assert hashlib.sha1(inspect.getsource(export.etf_export).encode()).hexdigest()[:12] == "711fa2b7790c"
    assert SRC.count("sh_stock") == 3 and SRC.count("sh_etf") == 3 and SRC.count('E["epf"] = epf') == 1


def test_site_data():
    f = DATA / "ix.json"
    if not f.exists():
        print("  （尚未用第 48 輪匯出，略過 ix.json）")
        return
    ix, L = json.loads(f.read_text(encoding="utf-8")), json.loads((DATA / "latest.json").read_text(encoding="utf-8"))
    days = sorted({d for p in (DATA / "stocks").glob("*.json") for d in json.loads(p.read_text(encoding="utf-8"))["prices"]["d"]})
    assert list(ix) == ["d", "TAIEX"] and ix["d"] == days and len(ix["TAIEX"]) == len(days) and ix["d"][-1] == L["date"]
    assert f.stat().st_size <= 8 * 1024
    if L["date"] == DATE:
        assert len(days) == 259 and ix["d"][0] == "2025-10-30" and ix["TAIEX"][0] == 28287.53 and ix["TAIEX"][-1] == 40122.35 and None not in ix["TAIEX"]


# ─── F48-2 純函式（驗收 3、11、12）─────────────────────────────────
FULL = r"""
const L = JSON.parse(fs.readFileSync(DIR + '/latest.json'));
let files = 0, rows = 0; const bad = [];
for (const [dir, codes, key] of [['stocks', Object.keys(L.stocks), 'pf'], ['etfp', Object.keys(L.etfs.rows), 'epf']]) for (const c of codes) {
  const d = JSON.parse(fs.readFileSync(`${DIR}/${dir}/${c}.json`)); if (!d[key]) continue; files++;
  const adj = cmpAdj(d), last = cmpAt(d.prices.d, adj, '9999-12-31');
  for (const r of d[key]) { rows++; const b = r[1] && d.prices.d[0] <= r[1] ? cmpAt(d.prices.d, adj, r[1]) : null;
    if (pc(b ? (last[1] / b[1] - 1) * 100 : null) !== sgn(r[2])) bad.push([c, r[0]]); }
}
console.log(JSON.stringify([files, rows, bad.slice(0, 5), bad.length]));"""


def check_full(cmp=CMP, stk=STK):
    """全部 pf／epf：純函式算的區間報酬顯示字串和匯出相同（R62；驗收 3）。"""
    if not (DATA / "latest.json").exists():
        return True
    o = _node(_js(cmp, stk) + f"const DIR = {json.dumps(str(DATA))};" + FULL)
    if o is None or o == "ERR":
        return o is None
    if json.loads((DATA / "latest.json").read_text(encoding="utf-8"))["date"] == DATE and o[:2] != [2354, 14260]:
        return False
    return o[3] == 0 and o[0] > 0


def test_full():
    assert check_full()


UNIT = r"""
const D = ['2025-11-20', '2025-11-21', '2025-11-24', '2025-11-25', '2025-12-31', '2026-01-02', '2026-11-23', '2026-11-24'];
const P = (d, c, ch) => ({ prices: { d, c, ch: ch || c.map(() => 0) } });
// ETF：dv 在非交易日 → 對到下一列；gx 漲跌 null → 參考價 = 收盤；gx 和 dv 同一列 → 只用官方；係數不合理略過；第 0 列略過
const e1 = Object.assign(P(['a1', 'a3', 'a4', 'a6', 'a7'], [10, 10, 20, 20, 5], [0, 0, null, 0, 0]), { dv: [{ d: 'a0', p: 9, r: 8 }, { d: 'a2', p: 10, r: 9 }, { d: 'a6', p: 20, r: 19 }], gx: ['a4', 'a6'] });
const e2 = Object.assign(P(['a1', 'a2', 'a3'], [10, 0.1, 0.1]), { dv: [{ d: 'a2', p: 10, r: 0.1 }], gx: [] });
const e3 = Object.assign(P(['a1', 'a2'], [10, 5]), { ev: [{ d: 'a2', t: '減', p: 10, r: 5 }], gx: ['a2'] });
const cl = [106.6, 108.65, 107.25, 104.95, 104.1, 100.6, 99.85, 97.15, 92.5, 97.45, 99.7, 103.2, 100.95, 102.5, 96.45, 94.0, 94.1, 90.2, 84.45, 87.0, 95.7];
const dd = cl.map((_, i) => 'b' + String(i).padStart(2, '0')), S = cmpStats(cl.map((v, i) => [dd[i], v]));
const ln = cmpLine(dd, dd, cl, dd[0]), up = cmpStats([1, 2, 3].map(v => ['x' + v, v]));
const gap = cmpLine(['c1', 'c2', 'c3', 'c4'], ['c0', 'c2', 'c4'], [50, 55, 60], 'c1');
const C4 = ['2026-01-05', '2026-01-06', '2026-01-07', '2026-01-08'], calc = cmpCalc({ d: C4, TAIEX: [100, 110, 120, 130] }, [{ c: 'A', d_: C4, adj: [10, 11, 12, 13] }, { c: 'B', d_: C4, adj: [null, null, 5, 6] }, { c: 'C', d_: C4.slice(2), adj: [7, 8] }], 'w');
const fx = v => Math.round(v * 1e6) / 1e6;
console.log(JSON.stringify({
  e1: cmpEvents(e1), e2: cmpEvents(e2), e3: cmpEvents(e3), adj: cmpAdj(e1).map(fx),
  base: ['20', '60', 'y', 'w', '5'].map(k => cmpBase(D, k)), base2: cmpBase(D, '2'),
  vol: [fx(S.vol), pc(S.ret), pc(S.dd[0]), S.dd[1], S.dd[2], fmt(cmpR(S.vol), 2), cmpStats(cl.slice(1).map((v, i) => [dd[i], v])).vol],
  ln: [fmt(cmpR(ln.vol), 2), ln.line.length, ln.last], up: up.dd, gap: gap.line.map(x => [x[0], fx(x[1]), x[2]]).concat([gap.last, fx(gap.ret)]),
  calc: [calc.b, calc.late, calc.rows.map(r => [r.c, fx(r.ret)]), fx(calc.ix.ret)],
  r: [-15.625, 15.625, -3.125, 53.125, 0.285, 1.005, 2.675].map(v => sgn(cmpR(v)))
}));"""
UNIT_WANT = {
    "e1": [{"d": "a3", "p": 10, "r": 9}, {"d": "a4", "p": 10, "r": 20}, {"d": "a6", "p": 20, "r": 19}], "e2": [], "e3": [{"d": "a2", "p": 10, "r": 5}],
    "adj": [17.1, 19, 19, 20, 5], "base": [None, None, "2025-12-31", "2025-11-24", "2025-11-24"], "base2": "2026-01-02",
    "vol": [63.874281, "-10.23", "-22.27", "b01", "b18", "63.87", None], "ln": ["63.87", 21, "b20"], "up": [0, None, None],
    "gap": [["c1", 0, True], ["c2", 10, False], ["c3", 10, True], ["c4", 20, False], "c4", 20],
    "calc": ["2026-01-07", ["B", "C"], [["A", 8.333333], ["B", 20], ["C", 14.285714]], 8.333333],
    "r": ["-15.62", "+15.62", "-3.12", "+53.12", "+0.28", "+1.00", "+2.67"]}


def check_unit(cmp=CMP, stk=STK):
    """自造資料：事件對列、推測調整參考價、起點日、樣本標準差（驗收 12：63.87、少一個收盤 --、母體 62.26 要失敗）、最大跌幅（驗收 11）、共同起點、半數取偶。"""
    o = _node(_js(cmp, stk) + UNIT)
    return o is None or o == UNIT_WANT


def test_unit():
    assert check_unit()


EX = r"""
const L = JSON.parse(fs.readFileSync(DIR + '/latest.json')), ix = JSON.parse(fs.readFileSync(DIR + '/ix.json'));
const ld = c => JSON.parse(fs.readFileSync(`${DIR}/${L.stocks[c] ? 'stocks' : 'etfp'}/${c}.json`));
console.log(JSON.stringify(CASES.map(([codes, k]) => { const S = codes.split(',').map(c => { const d = ld(c); return { c, d_: d.prices.d, adj: cmpAdj(d) }; });
  const X = cmpCalc(ix, S, k), f = r => [pc(r.ret), r.dd[1] ? pc(r.dd[0]) : '0.00', r.dd[1], r.dd[2], r.vol == null ? '--' : fmt(cmpR(r.vol), 2), r.last];
  return [X.b, X.late, X.rows.map(f), f(X.ix), X.rows.map(r => r.line.filter(p => ['2025-11-24', '2025-11-26', '2026-11-05', '2026-11-24'].includes(p[0])).map(p => [p[0], pc(p[1]), p[2]]))]; })));"""
EX_CASES = [("2330,2454,0050", "w"), ("2330,2454,0050", "y"), ("2330,2454,0050", "60"), ("2330,2454,0050", "20"), ("2330,2454,0050", "120"),
            ("0056,00878,00919", "w"), ("0052,0050", "w"), ("00679B,00687B,0050", "w"), ("0050,00991A", "w"), ("0050,00991A", "20"), ("0050,009833", "20"), ("00625K,0050", "w")]


def check_examples(cmp=CMP, stk=STK):
    """02-pm.md 二之四驗收 4～13（資料日 2026-11-24 才核對數字）。"""
    if not (DATA / "ix.json").exists() or json.loads((DATA / "latest.json").read_text(encoding="utf-8"))["date"] != DATE:
        print("  （資料日不是 2026-11-24 或沒有 ix.json，略過手算例）")
        return True
    o = _node(_js(cmp, stk) + f"const DIR = {json.dumps(str(DATA))}, CASES = {json.dumps(EX_CASES)};" + EX)
    if o is None or o == "ERR":
        return o is None
    ret = lambda x: [r[0] for r in x[2]] + [x[3][0]]   # noqa: E731
    w, y, s60, s20, s120, hi, p52, bd, late, late20, n4, nt = o
    return (w[0] == "2025-11-24" and w[1] == [] and w[2][0][:5] == ["+64.17", "-22.63", "2026-10-06", "2026-11-20", "34.93"]
            and w[2][1][:5] == ["+261.15", "-36.61", "2026-09-24", "2026-11-20", "68.82"] and w[2][2][:2] + [w[2][2][4]] == ["+63.97", "-27.51", "33.51"]
            and w[3][:2] + [w[3][4]] == ["+51.38", "-27.68", "31.93"]
            and y[0] == "2025-12-31" and ret(y) == ["+45.15", "+190.43", "+48.84", "+38.53"] and s60[0] == "2026-08-25" and ret(s60) == ["-6.81", "+8.43", "-8.33", "-11.17"]
            and s20[0] == "2026-10-27" and ret(s20) == ["-7.08", "+2.27", "-10.23", "-12.96"] and s20[2][2][1:5] == ["-22.27", "2026-10-28", "2026-11-20", "63.87"] and s20[3][4] == "61.48"
            and s120[0] == "2026-05-29" and ret(s120) == ["-4.77", "-5.47", "-8.65", "-10.31"]
            and [r[:5:4] for r in hi[2]] == [["+57.63", "27.16"], ["+67.51", "24.39"], ["+56.81", "22.05"]] and hi[2][0][1:3] == ["-23.41", "2026-10-14"] and hi[2][2][1:4] == ["-17.57", "2026-10-28", "2026-11-23"]
            and p52[2][0][:2] + [p52[2][0][4]] == ["+61.26", "-28.77", "35.60"] and p52[4][0][:2] == [["2025-11-24", "0.00", True], ["2025-11-26", "+0.88", False]] and p52[2][0][5] == DATE
            and bd[2][0][:4] == ["+0.04", "-11.34", "2026-03-02", "2026-10-07"] and bd[2][0][4] == "10.19" and bd[2][1][:2] + [bd[2][1][4]] == ["+0.17", "-11.31", "10.18"]
            and late[:2] == ["2025-12-18", ["00991A"]] and ret(late) == ["+57.74", "+34.21", "+46.07"] and [r[4] for r in late[2]] + [late[3][4]] == ["34.60", "52.83", "32.94"]
            and late[2][1][1:3] == ["-49.49", "2026-06-22"] and late20[:2] == ["2026-10-27", []]
            and n4[:2] == ["2026-11-19", ["009833"]] and ret(n4) == ["+6.10", "-0.10", "+4.41"] and [r[1] for r in n4[2]] + [n4[3][1]] == ["-6.37", "-6.84", "-6.23"]
            and [r[4] for r in n4[2]] + [n4[3][4]] == ["--"] * 3 and n4[2][1][3] == "2026-11-23"
            and nt[:2] == ["2025-12-05", ["00625K"]] and ret(nt) == ["-9.54", "+55.60", "+43.39"] and nt[2][0][5] == "2026-11-05" and nt[4][0][-1] == ["2026-11-24", "-9.54", True])


def test_examples():
    assert check_examples()


# ─── F48-3 網址正規化（驗收 14）與畫面（驗收 15～18、22）────────────────
NORM = [("2330,2454,0050", None, "#/compare/2330,2454,0050/w", []), ("00981a,2330", "y", "#/compare/00981A,2330/y", []),
        ("2330,2330,0050", "60", "#/compare/2330,0050/60", []), ("2330,,0050,", "20", "#/compare/2330,0050/20", []),
        ("2330,9999,1589", "20", "#/compare/2330/20", ["找不到 9999、1589，已從比較清單移除"]),
        ("2330,2454,0050,0056,00878", "w", "#/compare/2330,2454,0050,0056/w", ["最多比較 4 檔，已保留前 4 檔"]),
        ("2330", "5", "#/compare/2330/w", []), ("2330", "abc", "#/compare/2330/w", []), ("", None, "#/compare", []), ("", "w", "#/compare", []),
        ("9999", None, "#/compare", ["找不到 9999，已從比較清單移除"])]
NL = {"stocks": {c: {"n": n, "tv": tv} for c, n, tv in (("2330", "台積電", 9), ("2454", "聯發科", 5), ("2303", "聯電", 3), ("3711", "日月光投控", 2))},
      "etfs": {"rows": {c: {"n": n, "tv": tv} for c, n, tv in (("0050", "元大台灣50", 8), ("0056", "元大高股息", 4), ("00878", "國泰永續高股息", 6), ("00981A", "主動統一台股增長", 7))}}}


def check_norm(cmp=CMP):
    o = _node(_js(cmp) + f"const L = {json.dumps(NL)}, N = {json.dumps([n[:2] for n in NORM])};" + r"""
console.log(JSON.stringify({ n: N.map(([a, s]) => { const x = cmpNorm(a, s, L); return [cmpUrl(x.list, x.k), x.msg]; }),
  s: [cmpPick(Object.entries(L.stocks), '台積', []).map(x => x[0]), cmpPick(Object.entries(L.stocks), '2', ['2454']).map(x => x[0]), cmpPick(Object.entries(L.stocks), '聯', []).map(x => x[0])] }));""")
    return o is None or (o["n"] == [list(n[2:]) for n in NORM] and o["s"] == [["2330"], ["2303", "2330"], ["2454", "2303"]])


def test_norm():
    assert check_norm()


DOM = r"""
const E = {}, el = k => E[k] || (E[k] = { innerHTML: '', value: '', addEventListener() {} });
const $ = s => el(s), document = {}, window = {}, REP = [];
const location = { hash: '' }, history = { state: null, replaceState(s, t, u) { REP.push(u); location.hash = u; } };
let charts = [], IXOK = true; const disposeKCharts = () => {}, css = () => '';
const day = i => new Date(Date.UTC(2025, 9, 30 + i)).toISOString().slice(0, 10), DD = Array.from({ length: 30 }, (_, i) => day(i));
const IX = { d: DD, TAIEX: DD.map((_, i) => 100 + i) }, mk = (k, f) => ({ prices: { d: DD, c: DD.map((_, i) => 10 * (1 + k * i)), ch: DD.map(() => 0) }, ...f });
const DATA = { '2330': mk(0.01, { ev: [] }), '2454': mk(0.03, { ev: [] }), '0050': mk(0.02, { dv: [], epf: [] }), '0056': mk(-0.01, { dv: [], epf: [] }), '00878': mk(0, { dv: [], epf: [] }), '00981A': mk(0.01, { dv: [] }) };
async function getJSON(u) { if (u === 'data/ix.json' && IXOK) return IX; throw new Error('404 ' + u); }
const loadStock = async (c, dir) => DATA[c];
const App = { latest: Object.assign(LL, { date: DD[29] }), watch: new Set(['0056', '2330', '9999', '00878']), stockCache: {} };
""" + "\n".join(_grab(APP, n) for n in ("segHTML", "onSeg", "noteHTML")) + "\n"
DOM_RUN = r"""
(async () => { const out = [];
  for (const [h, a, s, ok] of CASES) { location.hash = h; REP.length = 0; IXOK = ok; App.cmpIx = null; await window.renderCompare(a, s);
    out.push([E['#view'].innerHTML, REP.slice(), E['#cmpL'] ? E['#cmpL'].innerHTML : '']); delete E['#cmpL']; }
  console.log(JSON.stringify(out)); })();"""
DOM_CASES = [("#/compare/0050,2454,2330/w", "0050,2454,2330", "w", True), ("#/compare/2330", "2330", None, True), ("#/compare/2330,00981A/w", "2330,00981A", "w", True),
             ("#/compare", "", None, True), ("#/compare/2330/w", "2330", "w", False), ("#/compare/2330,2454,0050,0056/w", "2330,2454,0050,0056", "w", True)]
NOTE_PM = PM[PM.index("- 全文（"):]
NOTE_PM = NOTE_PM[NOTE_PM.index("```\n") + 4:NOTE_PM.index("\n```", NOTE_PM.index("```\n") + 4)].replace("${ix.d[0]}", "2025-10-30")
PM_TXT = ["報酬率比較", "把最多 4 檔股票或 ETF 放在同一段期間比較，起點都是 0%。", "股票用還原價（含股息）、ETF 含配息；加權指數不含股息",
          "表格依加入順序排列。最大跌幅滑過可看高點與低點日期；年化波動在區間內少於 20 個交易日時不計算（--）。",
          '<span class="lg"><i class="dash"></i>加權指數（不含息）</span><span class="lg">實線 = 各檔（股票還原價、ETF 含息）</span>',
          "<th>名稱</th><th>區間報酬</th><th>最大跌幅</th><th>年化波動</th>", '<td><i class="cmp-dot cmp-ix"></i><b>加權指數（不含息）</b></td>']


def check_dom(cmp=CMP):
    js = "\n".join([_grab(APP, n) for n in ("fmt", "sgn", "cls", "esc", "md")] + [_grab(STK, "adjFactors")]) + "\n"
    o = _node(js + f"const LL = {json.dumps(NL)}, CASES = {json.dumps(DOM_CASES)};" + DOM + cmp + DOM_RUN)
    if o is None or o == "ERR":
        return o is None
    (h1, r1, l1), (h2, r2, _), (h3, r3, _), (h4, r4, _), (h5, _, _), (h6, _, _) = o
    rows = re.findall(r'<td><i class="cmp-dot"[^>]*></i><b>([^<]+)</b> <span class="muted small">(\w+)</span>', h1)
    chip = ('<span class="chip cmp-c"><i class="cmp-dot" style="background:var(--cmp3)"></i>2330 台積電<button type="button" class="cmp-x" data-x="2330" '
            'aria-label="移除 2330">×</button></span>')
    return (all(s in h1 for s in PM_TXT) and f"<div>{NOTE_PM}</div>" in h1 and "<summary>股票用還原價（含股息）、ETF 含配息；加權指數不含股息<i>說明</i>" in h1
            and [r[1] for r in rows] == ["0050", "2454", "2330"] and h1.index('cmp-ix"></i><b>加權指數') > h1.index("2330</span>") and chip in h1
            and "差距" not in h1 and "名次" not in h1 and r1 == [] and '<input id="cmpQ" type="search" placeholder="加入代號或名稱" autocomplete="off">' in h1
            and '<div class="cmp-w small"><span class="muted">自選：</span><a href="#" class="chip" data-add="0056">0056 元大高股息</a><a href="#" class="chip" data-add="00878">0878 國泰永續高股息</a></div>'.replace(">0878", ">00878") in h1
            and "<span><b>2025/11/28</b></span>" in l1 and '<i class="cmp-dot" style="background:var(--cmp1)"></i>0050 <b>' in l1 and "加權 <b>+29.00%</b>" in l1
            and '<button data-v="w" class="on">52 週</button>' in h1 and "自 2025-10-30 收盤起算，至 2025-11-28 收盤" in h1
            and r2 == ["#/compare/2330/w"] and r3 == ["#/compare/2330/w"] and '<div class="muted small cmp-msg">本站無法確認 00981A 的價格調整，暫不比較</div>' in h3
            and r4 == [] and '<div class="empty">輸入代號或名稱，加入要比較的股票或 ETF（最多 4 檔）。也可以從個股頁、ETF 頁的「近期表現」卡點「比較 →」進來。</div>' in h4
            and "<table" not in h4 and "cmpSeg" not in h4 and '<div class="empty">找不到交易日資料（data/ix.json），重新匯出資料後才能比較</div>' in h5 and "<table" not in h5
            and '<input id="cmpQ" type="search" placeholder="已滿 4 檔" autocomplete="off" disabled>' in h6 and "cmp-w" not in h6)


def test_dom():
    assert check_dom()


def test_pm_text():
    for s in PM_TXT[:4] + ["找不到交易日資料（data/ix.json），重新匯出資料後才能比較", "本站無法確認 ${代號} 的價格調整，暫不比較", "最多比較 4 檔，已保留前 4 檔",
                           "已從比較清單移除", "才有成交，比較起點改為", "（各檔與加權指數都從這天起算）", "比較 →"]:
        assert s in PM, s
    assert NOTE_PM.startswith("每條線 = 還原收盤") and NOTE_PM.endswith("不代表之後的走勢。")


# ─── F48-4 入口、路由、版本與文件（驗收 19、20、23～27）─────────────────
def check_entry(stk=STK):
    a = "  const pfh = [...document.querySelectorAll('#view .sec-h h2')].filter(h => h.textContent === (E ? '近期表現（含息）' : '近期表現'))[0];"
    b = "  if (pfh) pfh.parentElement.insertAdjacentHTML('beforeend', `<span class=\"sp\"></span><a class=\"small cmp-go\" href=\"#/compare/${code}\">比較 →</a>`);"
    return (stk.count(a) == stk.count(b) == 1 and stk.index("if (dvh && data.nx) dvh.parentElement") < stk.index(a) < stk.index(b) < stk.index("  onSeg('stockTabSeg'")
            and "cmp-go" not in _grab(stk, "perfHTML"))


def test_entry():
    assert check_entry()


def check_route(app=APP, html=HTML):
    r = "  compare: (arg, sub) => window.renderCompare(arg, sub),"
    s = [m.group(1) for m in re.finditer(r'<script src="(\w+)\.js', html)]
    return (app.count(r) == 1 and app.index("  help: arg => window.renderHelp(arg),") < app.index(r) < app.index("\n};", app.index("const routes = {"))
            and "help: '名詞說明', compare: '報酬率比較' }[page]" in app and s == ["app", "stock", "tools", "help", "compare"] and html.count("compare.js") == 1)


def test_route_and_version():
    assert check_route()
    for f in ("app.js", "stock.js", "app.css", "tools.js", "help.js", "compare.js"):
        v = hashlib.sha1((SITE / f).read_bytes()).hexdigest()[:8]
        assert f"{f}?v={v}" in HTML, f"index.html 要改成 {f}?v={v}"
    assert "tools.js?v=64e7360f" in HTML and "help.js?v=a5a5a7e8" in HTML and HTML.count("https://") == 2
    assert "python3 tests/test_iter48.py" in README and "第 48 輪" in (ROOT / "docs" / "iterations" / "README.md").read_text(encoding="utf-8")
    r = next(l for l in README.splitlines() if l.startswith("- 多檔報酬率比較（第 48 輪"))
    for s in ("ix.json", "#/compare/", "R62", "R64", "R67", "R68", "√250", "二代健保"):
        assert s in r, s
    assert "第 23 輪" not in r


def _new_segs(cmp=CMP, stk=STK, app=APP):
    return cmp + "".join(l for l in stk.splitlines() + app.splitlines() if "第 48 輪" in l)


def check_words(cmp=CMP, stk=STK, app=APP):
    seg = _new_segs(cmp, stk, app)
    rd = next(l for l in README.splitlines() if l.startswith("- 多檔報酬率比較（第 48 輪"))
    return all(w not in seg + rd for w in ADVICE) and all(w not in seg for w in ("差距", "名次", "第一名"))


def test_words():
    assert check_words()


def test_node14():
    for w in (".at(", "replaceAll", "||=", "&&=", "??="):
        assert w not in _new_segs(), w


# ─── 反證：原始碼改壞，對應的檢查要失敗 ─────────────────────────
def _mut_fn(old, new):
    src = inspect.getsource(export.ix_export)
    assert src.count(old) == 1, old
    ns = dict(vars(export))
    exec(src.replace(old, new), ns)
    return ns["ix_export"]


MUTANTS = [
    ("匯出缺值補 0", "fn", "_f(idx.get(d))", "_f(idx.get(d, 0))"),
    ("沒有寫 ix.json", "src", '    _write(SITE_DATA_DIR / "ix.json", ix_export(p_days, idx_close["TWSE"]))   # 第 48 輪 F48-1：比較頁的交易日曆＋加權收盤\n', ""),
    ("ETF 不加 gx 推測調整", "cmp", ".concat(gx)", ""),
    ("推測調整漲跌 null 時不用收盤", "cmp", "P.ch[i] == null ? P.c[i] :", "P.ch[i] == null ? P.c[i - 1] :"),
    ("事件不對到下一列", "cmp", "P.d.findIndex(d => d >= e.d)", "P.d.indexOf(e.d)"),
    ("係數不合理也採用", "cmp", "e.r / e.p >= 0.02 && e.r / e.p <= 20", "e.r / e.p > 0"),
    ("顯示不取偶數", "cmp", "(f + (f & 1)) / 100 :", "Number(v.toFixed(2)) :"),
    ("年化波動用母體標準差", "cmp", "/ (n - 1)", "/ n"),
    ("統計少了起點那一點", "cmp", "pts = [base];", "pts = [];"),
    ("無成交不標記", "cmp", "!(d in at)]", "false]"),
    ("共同起點只移晚上市那一檔", "cmp", "  if (late) b = late;\n", ""),
    ("52 週少一天", "cmp", "365 * 864e5", "364 * 864e5"),
    ("網址不轉大寫", "cmp", ".map(s => s.trim().toUpperCase())", ".map(s => s.trim())"),
    ("不去重", "cmp", "[...new Set((arg || '').split(',')", "[...((arg || '').split(',')"),
    ("表格依報酬排序", "cmp", "X.rows.map((r, j) => `<tr>", "X.rows.slice().sort((a, b) => b.ret - a.ret).map((r, j) => `<tr>"),
    ("自選列出已選的檔", "cmp", "(L.stocks[c] || R[c]) && !list.includes(c)", "(L.stocks[c] || R[c])"),
    ("ETF 沒有 epf 也比較", "cmp", "ix && !L.stocks[c] && !data[j].epf", "false"),
    ("說明寫差距", "cmp", "區間越長影響越大", "區間越長差距越大"),
    ("用詞", "cmp", "不代表之後的走勢。", "不代表之後的走勢，不是建議。"),
    ("入口加在卡片外", "stk", "pfh.parentElement.insertAdjacentHTML('beforeend'", "pfh.parentElement.insertAdjacentHTML('afterend'"),
    ("路由沒有標題", "app", ", compare: '報酬率比較' }[page]", " }[page]"),
    ("compare.js 放在 help.js 之前", "html", '<script src="help.js?v=a5a5a7e8" defer></script>\n<script src="compare.js', '<script src="compare.js'),
]
CHECKS = {"fn": lambda f: check_ix(f), "src": check_wiring, "stk": check_entry, "app": lambda a: check_route(app=a), "html": lambda h: check_route(html=h),
          "cmp": lambda c: check_unit(c) and check_full(c) and check_examples(c) and check_norm(c) and check_dom(c) and check_words(cmp=c)}


def test_contrast():
    node = T._node("console.log('1')") is not None
    for name, kind, a, b in MUTANTS:
        if kind == "fn":
            assert not CHECKS[kind](_mut_fn(a, b)), "反證沒有擋下：" + name
            continue
        src = {"src": SRC, "stk": STK, "app": APP, "html": HTML, "cmp": CMP}[kind]
        if kind == "html":                                        # 把 compare.js 那一行移到 help.js 之前
            c = re.search(r'<script src="compare\.js\?v=\w+" defer></script>\n', src).group(0)
            a, b = a + c[len('<script src="compare.js'):], c + a[:-len('\n<script src="compare.js')] + "\n"
        assert src.count(a) == 1, (name, a)
        ok = CHECKS[kind](src.replace(a, b))
        assert not ok or not node and kind == "cmp", "反證沒有擋下：" + name


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_") and callable(f):
            print("==", n); f()
    print("全部通過")
