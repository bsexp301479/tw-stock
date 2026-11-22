"""第 42 輪（不連網、不連資料庫）：自選頁持股 F42-1、今日頁我的自選 F42-2、個股頁族群標籤 F42-3、ETF 頁頭配息卡 F42-4、
自選 ETF 配息欄 F42-5、河流圖 EPS 說明 F42-6、ETF「除息」字樣 F42-7。
有 node 時逐字取出 app.js、stock.js 的函式＋整個 tools.js 執行（node 14 可跑）；檢查函式都接受原始碼，反證把原始碼改壞後重跑，確認會失敗。"""
import hashlib
import json
import random
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_iter32 as T32  # noqa: E402
import test_iter34 as T  # noqa: E402
import test_iter37 as T37  # noqa: E402
import test_iter41 as T41  # noqa: E402

ROOT, SITE = T.ROOT, T.SITE
APP, STK, CSS, HTML, TOOLS = T.APP, T.STK, T.CSS, T.HTML, T.TOOLS
README = (ROOT / "README.md").read_text(encoding="utf-8")
DOCS = (ROOT / "docs" / "iterations" / "README.md").read_text(encoding="utf-8")
BAD = T41.BAD
ADVICE = T41.ADVICE + ("反彈", "見底", "強勢股", "價值陷阱", "填息機率", "貼息", "存股", "配息穩定", "穩定配息", "高息", "搶息", "參加除息", "值得",
                       "必填息", "確定配發", "應認購", "吃虧", "稀釋", "合理價", "昂貴", "上檔", "下檔", "支撐", "壓力", "安全邊際", "賣點", "河道",
                       "歷史本益比", "超漲")
DATE = "2026-11-20"
EX_TIP = "除息日的開盤參考價扣掉配息，收盤減前一日收盤會含配息"

BASE = ["fmt", "pfmt", "sgn", "esc", "cls", "md", "yi", "pctCell", "alertBadge", "wCtl", "holdTag", "HL_KINDS"]
HOLD = ["EX_TIP", "etfPct", "holdLoad", "holdSave", "holdKind", "holdCalc", "holdSum", "holdView", "holdY", "holdP", "holdTd", "holdQ", "holdK",
        "holdIn", "holdTds", "holdFoot", "holdAll", "holdCap", "holdTable", "holdWire", "holdEdit", "holdLine", "watchToday", "etfWatchTable", "shareWatch"]
MOCK = r"""
const window = {};
let STORE = {}, BROKEN = false;
const localStore = (k, f, v) => v === undefined ? (k in STORE ? STORE[k] : f) : ((BROKEN || (STORE[k] = v)), f);
let ELS = {};
const $ = s => ELS[s] || null;
"""
# PM 二之九：範例 1～5 的 latest 與持股（tw.hold 的值是「分」）
LATEST = {"date": DATE, "flow_date": DATE, "holdings": {},
          "stocks": {"2330": {"n": "台積電", "i": "半導體", "c": 2000, "ch": -100, "p": -4.76, "n1": 12.3},
                     "1538": {"n": "正峰", "i": "鋼鐵工業", "c": 7.24, "ch": None, "p": None, "nt": "2026-11-09", "n1": None},
                     "9105": {"n": "泰金寶-DR", "i": "存託憑證", "c": 10, "ch": 0.1, "p": 1.01, "n1": 0}},
          "etfs": {"rows": {"0056": {"n": "元大高股息", "m": "TWSE", "c": 44.31, "ch": -3.1, "p": -6.54, "v": 1, "tv": 84.74,
                                     "dvc": 4.936, "dvd": "2026-10-22", "dvn": None, "dvx": None},
                            "00878": {"n": "國泰永續高股息", "m": "TWSE", "c": 28.03, "ch": -1.75, "p": -5.88, "v": 1, "tv": 30.1},
                            "00679B": {"n": "元大美債20年", "m": "TPEx", "c": 26.15, "ch": None, "p": None, "v": 1, "tv": 5.2, "dvc": 1.2,
                                       "dvd": DATE, "dvn": None, "dvx": None},
                            "00632R": {"n": "元大台灣50反1", "m": "TWSE", "c": None, "ch": None, "p": None, "v": 0, "tv": None}}}}
H = {"2330": [1350, 151235], "0056": [2500, 3680], "00878": [350, 2215], "00679B": [1000, 2750], "1538": [2000, 800]}
FEE = {"2330": 6, "0056": 10, "00878": 2.8, "00679B": 10, "1538": 10}
EXAMPLES = {   # 代號: (出售手續費, 證交稅, 市值～報酬率 4 格)
    "2330": ([1710, 598], [6000, 2100], '<td class="num">2,700,000</td><td class="num dn">-135,000</td><td class="num up">+647,919.50</td><td class="num up">+31.73%</td>'),
    "0056": ([126, 31], [88, 22], '<td class="num">110,775</td><td class="num dn">-7,750</td><td class="num up">+18,508</td><td class="num up">+20.12%</td>'),
    "00878": ([3], [9], '<td class="num">9,810.50</td><td class="num dn">-612.50</td><td class="num up">+2,046</td><td class="num up">+26.39%</td>'),
    "00679B": ([37], [0], f'<td class="num">26,150</td><td class="num flat" title="{EX_TIP}">除息</td><td class="num dn">-1,387</td><td class="num dn">-5.04%</td>'),
    "1538": ([20], [43], '<td class="num">14,480</td><td class="num flat">無成交</td><td class="num dn">-1,583</td><td class="num dn">-9.89%</td>'),
}


def _src(app=APP, tools=TOOLS, names=BASE + HOLD):
    return "\n".join(T32._grab(app, n) for n in names) + MOCK + tools + "\n"


def _run(body, app=APP, tools=TOOLS, latest=LATEST):
    return T._node(_src(app, tools) + "const App = { latest: %s, watch: new Set() };\n" % json.dumps(latest, ensure_ascii=False) + body)


def _fee(d, m=20):
    return json.dumps({"d": d, "m": m})


# ─── 驗收 1、4、6：手算範例 1～7 ─────────────────────────────────
def check_examples(app=APP, tools=TOOLS):
    o = _run("""
const H = %s, FEE = %s, one = c => { const V = holdCalc(App.latest, [c], H, JSON.stringify({ d: FEE[c], m: 20 }), '%s'); return V.s.rows.concat(V.e.rows)[0]; };
const rows = ['2330', '1538', '0056', '00878', '00679B'].map(one), S = holdSum(rows.slice(0, 2)), E = holdSum(rows.slice(2)), all = holdSum(rows);
console.log(JSON.stringify({ rows: rows.map(r => [r.c, r.f, r.tx, holdTds(r)]), foot: [holdFoot(S), holdFoot(E)], all: holdAll({ s: { sum: S }, e: { sum: E }, all }),
  line: holdLine(all, App.latest) }));""" % (json.dumps(H), json.dumps(FEE), DATE), app, tools)
    if o is None:
        return
    for c, f, x, tds in o["rows"]:
        assert [f, x, tds] == list(EXAMPLES[c]), (c, f, x, tds)
    assert o["foot"][0] == ('<tr><td class="nm"><b>合計</b><span>2 檔</span></td><td></td><td></td><td></td><td class="num">2,714,480</td>'
                            '<td class="num dn">-135,000<span class="sub2">不含 1 檔</span></td><td class="num up">+646,336.50</td><td class="num up">+31.41%</td></tr>'), o["foot"][0]
    assert o["foot"][1] == ('<tr><td class="nm"><b>合計</b><span>3 檔</span></td><td></td><td></td><td></td><td class="num">146,735.50</td>'
                            '<td class="num dn">-8,362.50<span class="sub2">不含 1 檔</span></td><td class="num up">+19,167</td><td class="num up">+15.06%</td></tr>'), o["foot"][1]
    assert o["all"] == ('全部持股（股票＋ETF）　市值 2,861,215.50 元　今日損益 <span class="dn">-143,362.50</span> 元　'
                        '未實現損益 <span class="up">+665,503.50</span> 元（<span class="up">+30.46%</span>）'), o["all"]
    txt = re.sub(r"<[^>]+>", "", o["line"])
    assert txt == "持股 5 檔　今日損益 -143,362.50 元　未實現損益 +665,503.50 元（+30.46%）（今日損益不含無成交、除息 2 檔）以 11/20 收盤全部出售試算，已扣出售手續費與證交稅", txt
    assert not BAD.search(json.dumps(o, ensure_ascii=False))
    return True


def test_examples():
    check_examples()


# ─── 驗收 2：隨機 200 組和 Python 整數參考實作逐分相同；和平均成本工具的出售手續費、證交稅相同 ─────
def _fmt(n, d):
    s = f"{abs(n):,.{d}f}"
    return ("-" if n < 0 and s.strip("0.,") else "") + s


def _sgn(x, d):   # tlS：> 0 加 +，四捨五入後為 0 不帶負號
    return ("+" if x > 0 else "") + _fmt(x, d)


def _ref(P, q, k, dz, m, r, chc):
    lots = [(a, mn) for a, mn in ((q - q % 1000, m), (q % 1000, 1)) if a > 0]
    f = [max(mn, P * a * 1425 * dz // 10 ** 11) for a, mn in lots]
    x = [P * a * r // 10 ** 6 for a, _ in lots]
    v, T_ = P * q, q * k
    u = v - (sum(f) + sum(x)) * 100 - T_
    cc = lambda n: _sgn(n / 100, 2 if n % 100 else 0)
    return f, x, [_fmt(v / 100, 2 if v % 100 else 0), cc(chc * q), cc(u), _sgn(u / T_ * 100, 2) + "%"]


def _cases(seed=42, n=200):
    rnd, out = random.Random(seed), []
    for i in range(n):
        kd = ("s", "e", "b", "dr")[i % 4]
        P = rnd.choice([rnd.randint(1, 999), rnd.randint(1000, 99999), rnd.randint(100000, 999999)])
        q = rnd.choice([rnd.randint(1, 999), 1000 * rnd.randint(1, 10 ** rnd.randint(1, 6)), rnd.randint(1001, 10 ** rnd.randint(4, 9))])
        k = max(1, int(P * rnd.uniform(0.3, 1.7)))
        d, m = rnd.randint(1, 1000) / 100, rnd.randint(0, 50)
        chc = rnd.randint(-P // 10, P // 10)
        code = {"s": "1101", "e": "0050", "b": "00679B", "dr": "9105"}[kd]
        out.append((code, kd, P, q, k, d, m, chc))
    return out


def test_random_200():
    cs = _cases()
    lat = {"date": DATE, "stocks": {}, "etfs": {"rows": {}}}
    js = []
    for i, (code, kd, P, q, k, d, m, chc) in enumerate(cs):
        row = {"n": "測試-DR" if kd == "dr" else "測試", "i": "x", "c": P / 100, "ch": chc / 100, "p": 1, "m": "TWSE"}
        L = {**lat, "stocks": {code: row} if kd in ("s", "dr") else {}, "etfs": {"rows": {} if kd in ("s", "dr") else {code: row}}}
        js.append("(() => { const V = holdCalc(%s, ['%s'], { '%s': [%d, %d] }, '%s', '%s'), r = V.s.rows.concat(V.e.rows)[0]; return [r.f, r.tx, holdTds(r)]; })()"
                  % (json.dumps(L, ensure_ascii=False), code, code, q, k, _fee(d, m), DATE))
    o = _run("console.log(JSON.stringify([%s]));" % ",".join(js))
    if o is None:
        return
    for (code, kd, P, q, k, d, m, chc), (f, x, tds) in zip(cs, o):
        r = {"s": 30, "dr": 10, "e": 10, "b": 0}[kd]
        rf, rx, cells = _ref(P, q, k, round(d * 100), m, r, chc)
        got = re.findall(r"<td[^>]*>([^<]*)</td>", tds)
        assert (f, x, got) == (rf, rx, cells), (code, P, q, k, d, m, chc, f, x, got, rf, rx, cells)
    # 同一組股數、成本：平均成本工具「該價格 1 列、目前價格 = 收盤」的出售手續費、證交稅相同（前 24 組）
    sts = [T41._st({"s": "s", "dr": "e", "e": "e", "b": "b"}[kd], [(f"{P // 100}.{P % 100:02d}", str(q))], d=str(d), m=str(m), cur=f"{P // 100}.{P % 100:02d}")
           for code, kd, P, q, k, d, m, chc in cs[:24]]
    html = T41._out(sts, today=DATE)
    num = lambda s: int(re.match(r"[\d,]+", s).group(0).replace(",", ""))
    for h, (f, x, _) in zip(html, o[:24]):
        assert num(T41._row(h, "出售手續費")) == sum(f) and num(T41._row(h, "證交稅")) == sum(x), (T41._row(h, "出售手續費"), f, x)


# ─── 驗收 5、6：手續費設定、證交稅商品別（D110 = A）─────────────────
def test_fee_and_tax_kind():
    o = _run("""
const L = App.latest, H = { '2330': [1000, 100000], '9105': [1000, 1000], '0056': [1000, 4000], '00679B': [1000, 2500] }, w = ['2330', '9105', '0056', '00679B'];
const fee = raw => { const V = holdCalc(L, ['2330'], H, raw, '%s'); return [V.f, V.s.rows[0].f]; };
const V = holdCalc(L, w, H, null, '%s'), late = holdCalc(L, w, H, null, '2027-01-05'), noB = holdCalc(L, ['2330'], H, null, '2027-01-05');
console.log(JSON.stringify({ good: fee('{"d":6,"m":30}'), bad: ['abc', '{"d":0}', '{"d":11}', '{"m":-1}', null].map(fee),
  kd: V.s.rows.concat(V.e.rows).map(r => [r.c, r.kd, r.tx]), cap: holdCap(V, L), late: [holdCap(late, L), late.e.rows[1].tx], noB: holdCap(noB, L),
  cap6: holdCap(holdCalc(L, w, H, '{"d":6,"m":30}', '%s'), L) }));""" % (DATE, DATE, DATE))
    if o is None:
        return
    assert o["good"] == [{"d": "6", "m": "30"}, [1710]]                                # 2,000,000 × 0.1425% × 0.6
    assert all(b == [{"d": "10", "m": "20"}, [2850]] for b in o["bad"]), o["bad"]      # 壞值回 10 折、20 元
    assert o["kd"] == [["2330", "s", [6000]], ["9105", "e", [10]], ["0056", "e", [44]], ["00679B", "b", [0]]], o["kd"]
    c = o["cap"]
    assert "手續費 10 折、整股最低 20 元、零股最低 1 元；折扣與整股最低值取自「工具 › 交易成本」" in c and "手續費 6 折、整股最低 30 元" in o["cap6"]
    assert "<div>證交稅：股票 0.3%、存託憑證 0.1%、ETF 0.1%、債券 ETF 停徵（至 2026/12/31）。</div>" in c and "期限已過" not in c
    assert "<div>債券 ETF 證交稅停徵期限已過，請確認最新稅率（本表仍以 0 試算）。</div>" in o["late"][0] and o["late"][1] == [0]
    assert "期限已過" not in o["noB"]                                                   # 沒有債券 ETF 持股不提醒


# ─── 驗收 7、8、9、10：輸入、儲存、移除連動 ─────────────────────────
EDIT = r"""
const mkIn = v => ({ value: v, a: {}, setAttribute(k, x) { this.a[k] = x; }, removeAttribute(k) { delete this.a[k]; }, focus() { this.f = 1; }, closest: () => wrap });
const box = { lines: [], querySelector(s) { const id = s.match(/data-m="(.*)"/)[1], i = this.lines.findIndex(l => l.id === id);
  return i < 0 ? null : { remove: () => this.lines.splice(i, 1) }; }, insertAdjacentHTML(p, h) { this.lines.push({ id: h.match(/data-m="(.*?)"/)[1], h }); } };
const wrap = { nextElementSibling: box }, cap = { outerHTML: '' }, all = { innerHTML: '' };
const hv = () => [{ innerHTML: '' }, { innerHTML: '' }];
const mkTr = c => ({ dataset: { code: c }, cells: [1, 2, 3, 4, 5, 6, 7, 8], v: hv(), querySelectorAll() { return this.v; }, deleteCell(i) { this.cells.splice(i, 1); },
  insertAdjacentHTML(p, h) { this.extra = h; this.cells.push(5, 6, 7, 8); } });
const tb = { tBodies: [{ rows: [mkTr('2330'), mkTr('1538')] }], tFoot: { innerHTML: '' } };
const IN = {}, sec = { cl: new Set(), classList: { add(c) { sec.cl.add(c); } }, h: {}, addEventListener(t, f) { this.h[t] = f; },
  querySelector(s) { const m = s.match(/^\[data-h([qc])="(.*)"\]$/); if (m) return IN[m[1] + m[2]];
    return s === '.h-cap' ? cap : s === '.h-all' ? all : s === '.h-tbl[data-h="s"]' ? tb : null; } };
const put = (c, q, k) => { IN['q' + c] = mkIn(q); IN['c' + c] = mkIn(k); holdEdit(sec, c);
  return { s: STORE.hold, m: box.lines.map(l => l.h), q: IN['q' + c].a['aria-invalid'] || '', k: IN['c' + c].a['aria-invalid'] || '' }; };
App.watch = new Set(['2330', '1538', '0056']);
"""
MSG_Q, MSG_C = "台積電 2330：股數請填正整數", "台積電 2330：平均成本請填大於 0 的數字，小數最多 2 位"
MSG_B = "台積電 2330：請同時填股數與平均成本；兩格都清空即刪除這檔持股"
MSG_S = "這個瀏覽器無法儲存持股（可能是私密視窗或封鎖網站資料），重新整理後會消失"


def check_inputs(app=APP):
    bad_q = ["0", "1.5", "-3", "abc", "1e3", "1000000000000"]
    bad_c = ["0", "-1", "1.234", "abc"]
    o = _run(EDIT + """
STORE.hold = '{"2330":[1000,50000]}';
const out = { q: %s.map(v => put('2330', v, '500')), c: %s.map(v => put('2330', '1000', v)),
  onlyQ: put('2330', '1000', ''), onlyC: put('2330', '', '500') };
out.ok = put('2330', ' 1,350 ', ' 1512.35 ');
out.patch = [tb.tBodies[0].rows[0].v.map(x => x.innerHTML), tb.tBodies[0].rows[0].extra, tb.tFoot.innerHTML, cap.outerHTML, tb.tBodies[0].rows[0].cells.length];
out.seven = put('1538', ' 7 ', '8');
out.clear = put('2330', '', '  ');
out.clearRow = [tb.tBodies[0].rows[0].v.map(x => x.innerHTML), tb.tBodies[0].rows[0].extra];
BROKEN = true; out.broken = put('0056', '100', '30'); BROKEN = false; out.fixed = put('0056', '100', '30');
console.log(JSON.stringify(out));""" % (json.dumps(bad_q), json.dumps(bad_c)), app)
    if o is None:
        return
    keep = '{"2330":[1000,50000]}'
    for r in o["q"]:
        assert r["s"] == keep and r["q"] == "true" and r["k"] == "" and r["m"] == [f'<div data-m="2330">{MSG_Q}</div>'], r
    for r in o["c"]:
        assert r["s"] == keep and r["q"] == "" and r["k"] == "true" and r["m"] == [f'<div data-m="2330">{MSG_C}</div>'], r
    assert o["onlyQ"]["m"] == [f'<div data-m="2330">{MSG_B}</div>'] and o["onlyQ"]["k"] == "true" and o["onlyQ"]["q"] == "" and o["onlyQ"]["s"] == keep
    assert o["onlyC"]["m"] == [f'<div data-m="2330">{MSG_B}</div>'] and o["onlyC"]["q"] == "true" and o["onlyC"]["s"] == keep
    assert o["ok"] == {"s": '{"2330":[1350,151235]}', "m": [], "q": "", "k": ""}, o["ok"]             # 千分位、前後空白可接受；改對後訊息消失
    v, extra, foot, capx, n = o["patch"]
    assert v == ["1,350", "1,512.35"] and n == 8 and extra.startswith('<td class="num">2,700,000</td>') and "<b>合計</b><span>1 檔</span>" in foot
    assert "還沒有填持股" not in capx and capx.startswith('<div class="muted small tbl-cap h-cap">')
    assert o["seven"]["s"] == '{"1538":[7,800],"2330":[1350,151235]}' and o["seven"]["m"] == []
    assert o["clear"]["s"] == '{"1538":[7,800]}' and o["clear"]["m"] == []                           # 兩格清空 → 刪除
    assert o["clearRow"][0][0].startswith('<button class="chip h-fill" data-hfill="2330">填入</button>') and o["clearRow"][0][1] == "--"
    assert o["clearRow"][1] == '<td class="num">--</td><td class="num">--</td><td class="num">--</td><td class="num">--</td>'
    assert o["broken"]["m"] == [f'<div data-m="_">{MSG_S}</div>'] and o["fixed"]["m"] == []          # 寫入後讀回不同 → 無法儲存
    return True


def test_inputs():
    check_inputs()


def check_storage(app=APP):
    o = _run("""
App.watch = new Set(['2330', '0056', 'ABCD12']);
const ld = raw => { STORE = raw == null ? {} : { hold: raw }; const h = holdLoad(); return [h, STORE.hold === undefined ? null : STORE.hold]; };
const good = '{"2330":[1350,151235],"0056":[2500,3680]}';
const out = { good: ld(good), none: ld(null), broken: ['abc', '[1,2]', '"x"', 'null', '7'].map(ld),
  mixed: ld('{"2330":[1350,151235],"abc":[1,1],"<x>":[1,1],"0056":[1.5,100],"ABCD12":[0,100],"1101":[1,1]}'),
  vals: ['[100,0]', '"x"', '[1,2,3]', '[1e12,1]', '[1,1e14]', '[-1,5]', '[1,"2"]'].map(v => ld('{"2330":' + v + '}')[0]),
  edge: ld('{"2330":[999999999999,99999999999999]}')[0] };
App.watch = new Set(['2330']); App.watchUndo = ['2330', '0056'];
out.undo = ld(good);                          // 可復原：剛移除的 0056 還在
App.watch = new Set(['2330', '0056']); App.watchUndo = null; STORE = { hold: good };
out.restored = holdLoad();                    // 按復原後照舊
App.watch = new Set(['2330']); out.after = ld(good);   // 不在可復原狀態：刪掉不在自選的代號並寫回
console.log(JSON.stringify(out));""", app)
    if o is None:
        return
    g = {"2330": [1350, 151235], "0056": [2500, 3680]}
    assert o["good"] == [g, '{"2330":[1350,151235],"0056":[2500,3680]}'] and o["none"] == [{}, None]   # 好的不重寫；沒有存不寫
    assert all(b == [{}, "{}"] for b in o["broken"]), o["broken"]                                         # 整串壞掉 → {}
    assert o["mixed"] == [{"2330": [1350, 151235]}, '{"2330":[1350,151235]}'], o["mixed"]                 # 丟掉壞的筆、不在自選的代號
    assert all(v == {} for v in o["vals"]), o["vals"]
    assert o["edge"] == {"2330": [999999999999, 99999999999999]}
    assert o["undo"] == [g, '{"2330":[1350,151235],"0056":[2500,3680]}'] and o["restored"] == g
    assert o["after"] == [{"2330": [1350, 151235]}, '{"2330":[1350,151235]}']
    return True


def test_storage_and_remove_link():
    check_storage()


def test_fill_button():
    o = _run(EDIT + """
const btn = { dataset: { hfill: '2330' } }, wbtn = { textContent: '編輯' }; ELS['#watchEdit'] = wbtn; IN.q2330 = mkIn(''); IN.c2330 = mkIn('');
holdWire(sec); let stop = 0;
sec.h.click({ target: { closest: s => s === '[data-hfill]' ? btn : null }, stopPropagation() { stop++; } });
const other = sec.h.click({ target: { closest: () => null }, stopPropagation() { stop += 10; } });
console.log(JSON.stringify({ edit: App.watchEdit, cl: [...sec.cl], txt: wbtn.textContent, focus: IN.q2330.f, stop, ch: typeof sec.h.change }));""")
    if o is None:
        return
    assert o == {"edit": True, "cl": ["editing"], "txt": "完成", "focus": 1, "stop": 1, "ch": "function"}, o   # 進編輯模式、焦點在股數、不往 #view 傳（不進個股頁）


# ─── 驗收 11：隱私 ───────────────────────────────────────────
def check_privacy(app=APP):
    o = _run("""
STORE.hold = '{"2330":[1357,151235]}'; App.watch = new Set(['2330', '0056']);
const location = { href: 'http://x/#/watch' }, navigator = { clipboard: { writeText(u) { this.u = u; } } };
let drawn = 0; const renderWatch = () => drawn++;
shareWatch().then(() => console.log(JSON.stringify({ url: App.watchShare.url, drawn })));""", app)
    if o is None:
        return
    assert o["url"] == "http://x/#/watch?add=2330,0056" and o["drawn"] == 1, o
    return True


def test_privacy():
    check_privacy()
    seg = "".join(T32._grab(APP, n) for n in HOLD[:-2])
    for w in ("fetch(", "XMLHttpRequest", "console.log", "location", "history", "sendBeacon", "localStorage"):
        assert w not in seg, w
    assert set(re.findall(r"localStore\('(\w+)'", seg)) == {"hold", "fee"}
    for f in (ROOT / "twstock").rglob("*.py"):
        assert "tw.hold" not in f.read_text(encoding="utf-8"), f                    # 匯出、收集不碰持股
    for n in ("renderWatch", "watchColTable", "watchAddList", "watchAddNote", "shareWatch"):   # 第 32 輪限制照舊
        assert set(re.findall(r"localStore\('(\w+)'", T32._grab(APP, n))) <= {"rspan"}, n


# ─── 驗收 12、13：欄位組、持股表、空狀態 ─────────────────────────
def test_col_sets_and_tables():
    js = T32._js("").replace("const localStore = (k, f) => f, ", "let STORE = {};\nconst localStore = (k, f, v) => v === undefined ? (k in STORE ? STORE[k] : f) : (STORE[k] = v, f), ")
    js = js.replace("const HL_KINDS = {};", "const HL_KINDS = {};\nconst window = {};\n" + "\n".join(T32._grab(APP, n) for n in HOLD[:-2]) + "\n" + TOOLS)
    lat = {"date": DATE, "flow_date": DATE, "holdings": {}, "stocks": {k: {**v, "tv": 1, "f1": 0, "t1": 0, "d1": 0, "fs": 0, "ts": 0, "s": 0}
                                                                         for k, v in LATEST["stocks"].items()}, "etfs": LATEST["etfs"]}
    js = js.replace("const App = { latest: %s" % json.dumps(T32.LATEST, ensure_ascii=False), "const App = { latest: %s" % json.dumps(lat, ensure_ascii=False))
    o = T._node(js + """
const S = { d: '%s', rmd: {}, fqd: {}, rows: {} };
const out = { flow: run(['2330', '0056'], { screen: S }), none: run(['2330'], { screen: null, watchCols: 'hold' }) };
out.hold = run(['2330', '1538', '0056', '00679B', '00632R'], { screen: S, watchCols: 'hold' }); out.st0 = STORE.hold === undefined ? null : STORE.hold;
STORE.hold = '%s'; out.hold2 = run(['2330', '1538', '0056', '00679B', '00632R'], { screen: S, watchCols: 'hold' });
STORE.hold = '{"00632R":[1000,2000],"0056":[2500,3680]}';
out.etf = run(['0056', '00632R'], { screen: null, watchCols: 'hold' }); out.etfFlow = run(['0056'], { screen: null, watchCols: 'flow' });
out.loads = loads; out.store = Object.keys(STORE);
console.log(JSON.stringify(out));""" % (DATE, json.dumps(H)))
    if o is None:
        return
    seg4 = '<div class="seg" id="wcolSeg"><button data-v="flow" class="on">資金</button><button data-v="perf" class="">表現</button><button data-v="fund" class="">基本面</button><button data-v="hold" class="">持股</button></div>'
    assert seg4 in o["flow"] and "rspanSeg" in o["flow"] and "h-tbl" not in o["flow"]
    assert "wcolSeg" not in o["none"] and "h-tbl" not in o["none"]                                     # screen.json 不存在：照舊只有資金
    h, h2 = o["hold"], o["hold2"]
    assert '<button data-v="hold" class="on">持股</button>' in h and "rspanSeg" not in h and "<th>外資1日</th>" not in h and o["loads"] == 0
    assert h.count('class="tbl h-tbl"') == 2 and h.count("h-cap") == 1 and h.index("h-cap") < h.index('data-h="s"') < h.index('data-h="e"')
    assert "<div>還沒有填持股。按「編輯」或各列的「填入」，輸入股數與平均成本。</div>" in h and o["st0"] is None   # 空狀態；沒有存就不寫
    assert h.count('data-hfill="') == 5 and '<td class="nm h-nm"><button class="wdel" data-unwatch="2330"' in h
    assert "<th>股票</th><th>股數</th><th>平均成本</th><th>收盤</th><th>市值</th><th>今日損益</th><th>未實現損益</th><th>報酬率</th>" in h
    assert '<input class="h-in" data-hq="2330" inputmode="numeric" autocomplete="off" placeholder="股數" aria-label="台積電 股數" value="1350">' in h2
    assert '<input class="h-in" data-hc="2330" inputmode="decimal" autocomplete="off" placeholder="平均成本" aria-label="台積電 平均成本" value="1512.35">' in h2
    assert '<input class="h-in" data-hc="1538" inputmode="decimal" autocomplete="off" placeholder="平均成本" aria-label="正峰 平均成本" value="8.00">' in h2
    assert '7.24<span class="sub2">最後成交 11/09</span>' in h2 and "還沒有填持股" not in h2 and "全部持股（股票＋ETF）" in h2
    assert "<b>合計</b><span>2 檔</span>" in h2 and "<b>合計</b><span>2 檔</span>" in h2.split('data-h="e"')[1]   # 00632R 無持股，ETF 合計 2 檔
    e = o["etf"]
    assert '<div class="seg" id="wcolSeg"><button data-v="flow" class="">行情</button><button data-v="hold" class="on">持股</button></div>' in e
    assert e.count("h-cap") == 1 and e.index("h-cap") < e.index('data-h="e"') and "全部持股" not in e.split("h-all")[1][:80]
    r632 = e.split('data-etf="00632R"')[1].split("</tr>")[0]
    assert '<td class="num">--</td><td class="num">--</td><td class="num flat">無成交</td><td class="num">--</td><td class="num">--</td>' in r632   # 無成交 4～8 欄
    assert "<b>合計</b><span>1 檔</span>" in e                                                       # 無成交不計入合計
    assert '<button data-v="flow" class="on">行情</button>' in o["etfFlow"] and "<th>近一年配息</th>" in o["etfFlow"]
    assert o["store"] == ["hold"]                                                                    # 欄位組不寫 localStorage
    assert not BAD.search(h + h2 + e)
    assert "<h2>ETF</h2></div>" in h and "當日行情" not in h and "當日行情" not in e                      # QA42-02：持股欄組不寫「當日行情；成交量…」
    assert '<h2>ETF</h2><span class="muted small">當日行情；成交量為張、成交額為億元</span></div>' in o["flow"]
    assert "存在這個瀏覽器裡，換裝置不會同步。當日行情；成交量為張、成交額為億元</span>" in o["etfFlow"]


# ─── 驗收 14：今日小卡 ───────────────────────────────────────
ROWS = re.search(r"  const rows = list => .*?\.join\(''\);\n", APP, re.S).group(0)


def test_today_card():
    st = {"c": 10, "ch": 0.1, "p": 1.0, "n1": 0.3, "i": "x"}
    lat = {"date": DATE, "flow_date": "2026-11-19", "alerts": {}, "stocks": {
        "2330": LATEST["stocks"]["2330"], "1538": LATEST["stocks"]["1538"], "1101": {**st, "n": "台泥", "hl": [["s3", DATE], ["zz", DATE]]},
        "1102": {**st, "n": "亞泥", "dsp": [DATE, "2026-11-30"]}, "1103": {**st, "n": "嘉泥", "ntc": 1, "hl": [["zz", DATE]]}, "1104": {**st, "n": "環泥"}},
        "etfs": LATEST["etfs"]}
    o = _run(ROWS + """
STORE = { hold: '%s', fee: '{"d":10,"m":20}' };
const out = { none: watchToday(App.latest, rows) };
App.watch = new Set(['00679B', '2330', '9999', '0056', '1538', '1101', '1102', '1103', '1104']); out.card = watchToday(App.latest, rows);
out.all = holdAll(holdView());
App.latest.flow_date = App.latest.date; STORE.hold = '{}'; App.watch = new Set(['2330']); out.small = watchToday(App.latest, rows);
console.log(JSON.stringify(out));""" % json.dumps({k: v for k, v in H.items() if k != "00878"}), latest=lat)
    if o is None:
        return
    c = o["card"]
    assert o["none"] == "" and c.startswith('<section class="sec card w-today"><div class="sec-h"><h2>我的自選</h2><span class="muted small">11/20 收盤、法人 11/19</span>')
    assert re.findall(r'<tr data-code="(\w+)">', c) == ["00679B", "2330", "0056", "1538", "1101"]                    # 前 5 個認得的，依自選順序、混排
    assert f'<tr data-code="00679B"><td class="nm"><b>元大美債20年</b><span>00679B</span></td><td class="num flat">26.15</td><td class="num flat" title="{EX_TIP}">除息</td><td class="num">--</td></tr>' in c
    assert '<td class="nm"><b>台積電</b><span>2330</span></td>' in c and '<td class="num dn">2,000</td><td class="num dn">-4.76%</td>' in c   # 沿用 rows
    m = re.search(r'<a class="w-hold" href="#/watch">持股 (\d+) 檔　今日損益 <b class="\w+">(.*?)</b> 元　未實現損益 <b class="\w+">(.*?)</b> 元（<b class="\w+">(.*?)</b>）', c)
    a = re.search(r"今日損益 <span class=\"\w+\">(.*?)</span> 元　未實現損益 <span class=\"\w+\">(.*?)</span> 元（<span class=\"\w+\">(.*?)</span>）", o["all"])
    assert m and a and m.groups()[1:] == a.groups() and m.group(1) == "4", (m and m.groups(), a and a.groups())      # 和自選頁全部持股同一個數字
    assert "（今日損益不含無成交、除息 2 檔）" in c and "以 11/20 收盤全部出售試算，已扣出售手續費與證交稅" in c
    assert '<a class="w-ev-l" href="#/watch">近期新訊號 1 檔、處置／注意 2 檔 →</a>' in c                              # 不只前 5 檔；不認得的訊號不算
    assert "共 8 檔，顯示前 5 檔（依自選順序）。法人1日 = 三大法人當日買賣超（億，估算），ETF 不計。" in c
    s = o["small"]
    assert '<span class="muted small">11/20 收盤</span>' in s and "w-hold" not in s and "w-ev-l" not in s and "共 " not in s
    # D108 = B：分頁鈕之下、總覽第一個區塊；指數卡、分頁鈕兩句不改；只在總覽
    assert "    ov: `${tab === 'ov' ? watchToday(L, rows) : ''}${sumStrip(L)}<section class=\"sec grid g-stats g-mk\">" in APP
    assert "<section class=\"sec grid g-stats\">${indexCard(L.index?.TAIEX, '加權指數', tab === 'ov')}" in APP and "${pageTabsHTML('todayTabSeg', TODAY_TABS, tab)}" in APP
    assert "$('#view .w-hold')?.addEventListener('click', () => { App.watchCols = 'hold'; });" in APP
    assert "ycls(" not in T32._grab(APP, "watchToday") and not BAD.search(c + s)


# ─── 驗收 15：族群標籤 ───────────────────────────────────────
TAG_ON = re.search(r"  \$\('#view \.tags'\)\.addEventListener.*?\} \}\);\n", STK, re.S)


def check_tags(stk=STK):
    on = re.search(r"  \$\('#view \.tags'\)\.addEventListener.*?\} \}\);\n", stk, re.S)
    assert on, "找不到標籤監聽"
    js = "\n".join(T32._grab(APP, n) for n in ("esc",)) + "\n" + "\n".join(T32._grab(stk, n) for n in ("GRP_NM", "grpTag", "tagFold")) + r"""
const App = { latest: { groups: { industry: [{ name: '半導體' }], chain: [{ name: '半導體' }], concept: [{ name: 'IC設計' }] } } }, store = {};
const localStore = (k, f, v) => (store[k] = v, f), setGroup = g => { App.group = g; store.group = g; };
let fn; const $ = () => ({ addEventListener(t, f) { fn = f; } });
""" + on.group(0) + r"""
const t = [grpTag('industry', '半導體', '半導體'), grpTag('chain', '半導體', '半導體 › 消費性IC、電源管理IC…', '半導體 › IC設計：消費性IC、電源管理IC、記憶體'),
  grpTag('concept', 'IC設計', 'IC設計'), grpTag('industry', '其他', '其他'), grpTag('chain', '光電', '光電 › 面板', '光電 › 面板'), grpTag('concept', '<x>', '&lt;x&gt;')];
const a = { dataset: { gk: 'chain', gn: '半導體' } };
fn({ target: { closest: s => s === 'a[data-gk]' ? a : null } }); const r1 = Object.assign({}, App, { latest: 0 }), s1 = Object.assign({}, store);
fn({ target: { closest: () => null } });
console.log(JSON.stringify({ t, r1, s1, s2: store, fold: tagFold(t) }));"""
    o = T._node(js)
    if o is None:
        return
    t = o["t"]
    assert t[0] == '<a class="pill grp" href="#/bubble" data-gk="industry" data-gn="半導體" title="看泡泡圖「半導體」類股">半導體</a>', t[0]
    assert t[1] == ('<a class="pill chain grp" href="#/bubble" data-gk="chain" data-gn="半導體" title="半導體 › IC設計：消費性IC、電源管理IC、記憶體'
                    '（點了看泡泡圖「半導體」整條產業鏈）">半導體 › 消費性IC、電源管理IC…</a>'), t[1]
    assert t[2] == '<a class="pill grp" href="#/bubble" data-gk="concept" data-gn="IC設計" title="看泡泡圖「IC設計」概念股">IC設計</a>', t[2]
    assert t[3:] == ['<span class="pill">其他</span>', '<span class="pill chain" title="光電 › 面板">光電 › 面板</span>', '<span class="pill">&lt;x&gt;</span>'], t[3:]
    r = o["r1"]
    assert r.get("group") == "chain" and r.get("blOpen") == "半導體" and r.get("blAll") is False and r.get("blJump") == 1, r
    assert o["s1"] == {"group": "chain", "focus": "半導體"} and o["s2"] == o["s1"]                 # 點標籤以外不動
    assert '<span class="tag-rest" hidden>' in o["fold"] and 'data-gk="concept"' in o["fold"].split("tag-rest")[1]   # 摺疊在 +N 裡也是可點的 <a>
    return True


def test_group_tags():
    check_tags()
    assert "${E ? '<span class=\"pill\">ETF</span>' : grpTag('industry', data.industry, esc(data.industry))}" in STK
    assert "...(data.concepts || []).map(c => grpTag('concept', c, esc(c)))])}" in STK and "data-group" not in T32._grab(STK, "grpTag")
    assert STK.count("$('#view .tags').addEventListener('click'") == 1 and "onRowClick" not in TAG_ON.group(0)
    assert "a.pill.grp{cursor:pointer}a.pill.grp:hover,a.pill.grp:focus-visible{border-color:var(--blue);outline:none}" in CSS


# ─── 驗收 16、17、19：ETF 頁頭、自選 ETF 表、除息字樣 ─────────────────
def check_etf(app=APP, stk=STK):
    E = LATEST["etfs"]["rows"]
    js = "\n".join(T32._grab(app, n) for n in ("fmt", "pfmt", "sgn", "esc", "cls", "md", "wCtl", "holdTag", "EX_TIP", "etfPct", "etfDiv", "etfWatchTable"))
    js += "\n" + T32._grab(stk, "etfCards") + "\nconst App = { latest: %s };\n" % json.dumps(LATEST, ensure_ascii=False) + r"""
const R = App.latest.etfs.rows, X = Object.assign({}, R['0056'], { ch: -0.5 });
const pct = [etfPct(R['0056'], '%s'), etfPct(R['00679B'], '%s'), etfPct(R['00632R'], '%s'), etfPct(R['00679B'], '2026-11-19')];
console.log(JSON.stringify({ cards: ['0056', '00878', '00679B', '00632R'].map(c => etfCards(R[c])), x: etfCards(X), dvr: etfDiv(Object.assign({}, X), '%s').dvr,
  tbl: etfWatchTable(['0056', '00878', '00679B', '00632R'].map(c => [c, R[c]])), xt: etfWatchTable([['0056', X]]), pct }));""" % ((DATE,) * 4)
    o = T._node(js)
    if o is None:
        return
    c = o["cards"]
    assert c[0] == [["近一年配息", "4.936 元", "", "每單位，近 365 天合計"], ["配息率", "11.14%", "", "近一年配息 ÷ 今日收盤；股價下跌時會變高"],
                    ["最近除息", "10/22", "", "未填息"], ["成交額", "84.74 億", "", "當日"]], c[0]
    assert c[1] == [["成交額", "30.10 億", "", "當日"]] and c[3] == [["成交額", "--", "", "當日"]]                 # 沒有配息：只有成交額
    assert c[2][1] == ["配息率", "4.59%", "", "近一年配息 ÷ 今日收盤；股價下跌時會變高"] and c[2][2][2:] == ["", "未填息"]
    assert etf_nt() and o["x"][1][1] == "%.2f%%" % o["dvr"] == "11.14%"                                      # 同 ETF 列表的 dvr（今日收盤，不用前一日）
    t = o["tbl"]
    assert "<th>ETF</th><th>收盤</th><th>漲跌</th><th>成交量</th><th>成交額</th><th>近一年配息</th><th>配息率</th><th>最近除息</th></tr>" in t
    r0 = t.split('data-etf="0056"')[1].split("</tr>")[0]
    assert '<td class="num">4.936</td><td class="num">11.14%</td>\n      <td class="num">10/22<span class="sub2">未填息</span></td>' in r0
    assert '<td class="num">--</td><td class="num">--</td>\n      <td class="num">--</td>' in t.split('data-etf="00878"')[1].split("</tr>")[0]
    assert f'<td class="num flat" title="{EX_TIP}">除息</td>' in t.split('data-etf="00679B"')[1].split("</tr>")[0]
    assert ">無成交</td>" in t.split('data-etf="00632R"')[1].split("</tr>")[0] and '<td class="num dn">-6.54%</td>' in r0
    assert t.endswith('<div class="muted small h-note">配息率 = 近一年配息 ÷ 今日收盤，股價下跌時會變高；最近除息的第二行是填息狀態，算法同 ETF 列表。</div>')
    assert "11.14%" in o["xt"]
    p = o["pct"]
    assert p == ['<td class="num dn">-6.54%</td>', f'<td class="num flat" title="{EX_TIP}">除息</td>', '<td class="num flat">無成交</td>',
                 '<td class="num flat">--%</td>'], p                                                          # 除息要「除息日 = 資料日」
    return True


def etf_nt():
    """今天無成交（c null）而有配息：配息率 --、小字「今天無成交」。"""
    js = T32._grab(APP, "fmt") + "\n" + T32._grab(APP, "md") + "\n" + T32._grab(STK, "etfCards") + \
        "\nconsole.log(JSON.stringify(etfCards({ c: null, dvc: 1.2, dvd: '2026-10-01', dvn: 3, tv: null })));"
    r = T._node(js)
    return r == [["近一年配息", "1.2 元", "", "每單位，近 365 天合計"], ["配息率", "--", "", "今天無成交"], ["最近除息", "10/01", "", "3 天填息"], ["成交額", "--", "", "當日"]]


def test_etf():
    check_etf()
    assert "  const mtCards = E ? etfCards(E) : [['市值'," in STK and "...mtCards]" in STK                    # 接在 52 週高、低之後；股票頁不變
    assert "        ${etfPct(r, App.latest.date)}\n" in APP and APP.count("etfPct(") == 2                      # ETF 列表、今日小卡
    for l in (APP + STK).splitlines():
        if "配息率" in l:
            assert "殖利率" not in l, l                                                                    # test_iter36 的限制


# ─── 驗收 18：河流圖 ─────────────────────────────────────────
def test_band_note():
    js = T37.HELPERS + "\n" + T37.BAND + T37.MOCK + r"""
renderBand(mk(), 'pe'); const pe = els['#bandBox'].innerHTML; renderBand(mk(), 'pb');
console.log(JSON.stringify([pe, els['#bandBox'].innerHTML]));"""
    o = T._node(js)
    if o is None:
        return
    s = '<div class="muted small">本卡的 EPS 由官方本益比反推（收盤 ÷ 本益比），和季報卡的近 4 季 EPS（財報累計相減）算法不同，數字可能略有差異。</div>'
    assert s in o[0] and "本卡的 EPS" not in o[1]
    assert o[0].index("× 20.00 倍（近一年第 38 百分位）</div>") < o[0].index(s)                               # 緊接在「收盤 = …」說明列之後
    assert "BAND_NM" in STK and "'近 4 季 EPS'" in STK and "本卡的 EPS" not in T32._grab(STK, "BAND_NOTE")


# ─── 驗收 3、21、22、23、24：呼叫不複製、字面計數、用詞、接線 ─────────────
def test_call_not_copy_and_counts():
    calc = T32._grab(APP, "holdCalc")
    assert "tlSell(" in calc and "tlTax(" in calc and "tlFeePref(fee)" in calc and "1425" not in calc and "1000000n" not in calc and "tlLot" not in calc
    assert "mo: 1 }" in calc                                                                  # 零股最低固定 1 元
    assert APP.count("ycls(") == 14 and APP.count('class="note-dup"') == 3 and STK.count("note-dup") == 2
    assert APP.count("addEventListener('click', onEtfRow)") == 2 and APP.count("rm ? wCtl(c) : ''") == 1 and APP.count('<td class="nm">${wCtl(c)}') == 1
    new = "".join(T32._grab(APP, n) for n in HOLD[:-2]) + T32._grab(STK, "grpTag") + T32._grab(STK, "etfCards")
    assert "noteHTML(" not in new and "data-group" not in new and "tl-" not in new
    v = {f: hashlib.sha1((SITE / f).read_bytes()).hexdigest()[:8] for f in ("app.js", "stock.js", "app.css", "tools.js")}
    for f, h in v.items():
        assert f'{f}?v={h}"' in HTML, f"site/index.html 的 {f}?v= 請改成 {h}"
    assert HTML.count("https://") == 2                       # 第 42 輪 tools.js 0 行改動；之後 tools.js 的版本由上面 ?v= 比對


def test_no_advice_words():
    seg = "".join(T32._grab(APP, n) for n in HOLD[:-2]) + "".join(T32._grab(STK, n) for n in ("GRP_NM", "grpTag", "etfCards"))
    seg += "".join(l for l in (APP + STK + CSS).splitlines() if "第 42 輪" in l)
    seg += "".join(l[l.index("第 42 輪"):] for l in README.splitlines() if "第 42 輪" in l)
    assert seg.count("第 42 輪") >= 10
    for w in ADVICE:
        assert w not in seg, w


def test_css_and_docs():
    for s in (".watch:not(.editing) .h-in,.watch.editing .h-v{display:none}", "font-size:16px;text-align:right", ".h-tbl tfoot td{", ".w-hold{display:block"):
        assert s in CSS, s
    new = [l for l in CSS.splitlines() if "第 42 輪" in l]
    assert len(new) == 4 and not any(re.search(r"#[0-9a-fA-F]{3,6}\b", l) for l in new)       # 只用既有色票
    assert "第 38 輪" not in "".join(new) and "第 41 輪" not in "".join(new)
    assert "第 42 輪" in README and "test_iter42" in README and "- 第 42 輪" in DOCS


# ─── QA42-01：上市 ETF 除息日官方漲跌記 0（不比價）也寫「除息」、不計入今日損益合計；QA42-03：名稱跳脫 ──
def check_qa42(app=APP, stk=STK):
    lat = json.loads(json.dumps(LATEST))
    lat["etfs"]["rows"]["0051"] = {"n": "元大中型100", "m": "TWSE", "c": 105.95, "ch": 0.0, "p": 0.0, "v": 303, "tv": 0.32, "dvc": 7.5, "dvd": DATE}
    lat["etfs"]["rows"]["0050"] = {"n": "<i>&\"'", "m": "TWSE", "c": 50, "ch": 0.0, "p": 0.0, "v": 1, "tv": 1, "dvd": "2026-10-01"}
    lat["stocks"]["9999"] = {"n": "<img src=x>", "i": "<b>", "c": 10, "ch": 0, "p": 0, "n1": 0}
    o = T._node(_src(app) + "const App = { latest: %s, watch: new Set(['9999', '0051', '0050']) };\n" % json.dumps(lat, ensure_ascii=False) + r"""
const R = App.latest.etfs.rows, V = holdCalc(App.latest, ['9999', '0051', '0050'], { '9999': [1000, 1000], '0051': [1000, 10000], '0050': [1000, 5000] }, 'x', '%s');
console.log(JSON.stringify({ pct: [etfPct(R['0051'], '%s'), etfPct(R['0050'], '%s')], wt: etfWatchTable([['0051', R['0051']]]), sum: [V.e.sum.n, V.e.sum.k],
  r: holdTds(V.e.rows[0]), html: holdTable(V.s, false, V) + holdTable(V.e, true, V) + etfWatchTable([['0050', R['0050']]]) }));""" % ((DATE,) * 3))
    if o is None:
        return
    assert o["pct"] == [f'<td class="num flat" title="{EX_TIP}">除息</td>', '<td class="num flat">0.00%</td>'], o["pct"]   # 非除息日照舊
    assert f'<td class="num flat" title="{EX_TIP}">除息</td>' in o["wt"]
    assert o["sum"] == [2, 1] and f'<td class="num flat" title="{EX_TIP}">除息</td>' in o["r"], o
    assert "<img" not in o["html"] and "<i>" not in o["html"] and "&lt;img src=x&gt;" in o["html"] and "&lt;i&gt;&amp;&quot;&#39;" in o["html"]
    t = T._node(T32._grab(app, "esc") + "\nconst App = { latest: { groups: { concept: [{ name: '<x>\"' }] } } };\n" + T32._grab(stk, "GRP_NM") + "\n" + T32._grab(stk, "grpTag") +
                "\nconsole.log(JSON.stringify(grpTag('concept', '<x>\"', '&lt;x&gt;&quot;')));")
    assert "<x>" not in t and 'data-gn="&lt;x&gt;&quot;"' in t, t
    return True


def test_qa42():
    check_qa42()


# ─── 驗收 25：反證（改壞後上面的檢查要失敗） ─────────────────────────
MUTANTS = [
    ("未實現損益不扣出售成本", "app", "u: S.net - T,", "u: S.sa - T,", check_examples),
    ("出售不拆整股零股", "tools", "const L = tlLot(N, o.m, o.mo), a", "const L = [[N, o.m]], a", check_examples),
    ("零股最低改用整股最低", "app", "m: +f.m, mo: 1 }", "m: +f.m, mo: +f.m }", check_examples),
    ("ETF 證交稅用 0.3%", "app", "e ? (/B$/.test(c) ? 'b' : 'e')", "e ? (/B$/.test(c) ? 'b' : 's')", check_examples),
    ("債券 ETF 以 0.1% 試算（範例 7）", "app", "e ? (/B$/.test(c) ? 'b' : 'e')", "e ? (/B$/.test(c) ? 'e' : 'e')", check_examples),
    ("今日損益除息日當 0 計入合計", "app", "k: S.k + (x.d == null ? 1 : 0)", "k: S.k", check_examples),
    ("tw.hold 讀取不驗證", "app", "/^[0-9A-Z]{4,6}$/.test(c) && keep(c) && Array.isArray(v)", "true", check_storage),
    ("移除自選不刪持股", "app", "keep(c) && Array.isArray(v)", "Array.isArray(v)", check_storage),
    ("分享連結帶持股", "app", ".filter(c => S[c] || R[c]).join(',');", ".filter(c => S[c] || R[c]).join(',') + localStore('hold', '');", check_privacy),
    ("族群標籤不切換分組", "stk", "setGroup(a.dataset.gk); ", "", check_tags),
    ("配息率用前一日收盤", "stk", "fmt(E.dvc / E.c * 100, 2)", "fmt(E.dvc / (E.c - E.ch) * 100, 2)", check_etf),
    ("自選 ETF 表配息率用前一日收盤", "app", "fmt(r.dvc / r.c * 100, 2)", "fmt(r.dvc / (r.c - r.ch) * 100, 2)", check_etf),
    ("除息條件漏掉 dvd === date", "app", "!r.p && r.dvd === d ?", "!r.p ?", check_etf),
    ("除息條件只認官方漲跌為空（QA42-01）", "app", "!r.p && r.dvd === d ?", "r.p == null && r.dvd === d ?", check_qa42),
    ("持股除息條件只認官方漲跌為空（QA42-01）", "app", "(!x.p && x.dvd === L.date ?", "(x.p == null && x.dvd === L.date ?", check_qa42),
    ("持股表名稱不跳脫（QA42-03）", "app", "<b>${esc(x.x.n)}</b>${e ?", "<b>${x.x.n}</b>${e ?", check_qa42),
    ("族群 data-gn 不跳脫（QA42-03）", "stk", 'data-gn="${esc(gn)}"', 'data-gn="${gn}"', check_qa42),
    ("驗證順序錯（只填一格當成合法）", "app", "const m = !a !== !b ?", "const m = false ?", check_inputs),
]


def test_contrast():
    src = {"app": APP, "tools": TOOLS, "stk": STK}
    for name, k, a, b, fn in MUTANTS:
        assert src[k].count(a) == 1, name
        s = dict(src, **{k: src[k].replace(a, b)})
        try:
            r = fn(**{"app": s["app"], "tools": s["tools"]} if fn is check_examples else {"app": s["app"]} if fn in (check_storage, check_privacy, check_inputs)
                   else {"stk": s["stk"]} if fn is check_tags else {"app": s["app"], "stk": s["stk"]})   # check_etf、check_qa42
        except AssertionError:
            continue
        assert r is None, "反證沒有擋下：" + name                                     # 沒有 node 時 r 為 None，略過


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_") and callable(f):
            print("==", n); f()
    print("全部通過")
