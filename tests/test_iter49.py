"""第 49 輪（不連網、不連資料庫）：除權息試算起日寫年份 F47-9、泡泡圖成分股表 0 億列收合 F47-10（R72）、
窄螢幕個股頁頭 F47-11、選股「{v} 天內將除息」F47-12（R71）。
有 node 時逐字取出 app.js 的函式＋整個 tools.js 執行（node 14 可跑）；畫面文字和 docs/iterations/49/02-pm.md 二之一逐字比對。
檢查函式都接受原始碼，最後的 test_contrast 把原始碼改壞（反證），確認對應的檢查會失敗。"""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
import test_iter34 as T  # noqa: E402
import test_iter35 as T35  # noqa: E402
import test_iter47 as T47  # noqa: E402

SITE, HTML, APP, STK, CSS, TOOLS = T.SITE, T.HTML, T.APP, T.STK, T.CSS, T.TOOLS
README = (ROOT / "README.md").read_text(encoding="utf-8")
PM = (ROOT / "docs" / "iterations" / "49" / "02-pm.md").read_text(encoding="utf-8")
_grab = T35._grab
_T23 = (ROOT / "tests" / "test_iter23.py").read_text(encoding="utf-8")
_T23 = _T23[_T23.index('    for w in ("', _T23.index("assert seg.count(\"第 23 輪\")")):]
ADVICE = T47.ADVICE | set(re.findall(r'"([^"]+)"', _T23[:_T23.index("):")]))   # test_iter23:343～345 的清單（不在本檔重寫用詞）
FROM = "${from.replace(/-/g, '/')}"
DATA = SITE / "data"


def _ok(f, *a):
    try:
        return f(*a) is not False
    except Exception:   # node 拋錯或 assert 失敗都算檢查失敗
        return False


# ─── F47-9 除權息試算起日（驗收 1～3）──────────────────────────────
def _dv(d, dv):
    return {"market": "TWSE", "prices": {"d": ["2025-01-02", d]}, "dv": dv, "ev": [], "nx": []}


DV = {"a": [{"d": "2025-11-20", "t": "息", "c": 9}, {"d": "2026-03-01", "t": "息", "c": 2}, {"d": "2026-09-16", "t": "權息", "c": 3, "s": 1}],
      "m": [{"d": "2026-03-01", "t": "息", "c": None}, {"d": "2026-09-16", "t": "息", "c": 2}],
      "n": [{"d": "2026-09-16", "t": "息", "c": None, "a": None}],
      "z": [{"d": "2026-09-16", "t": "權", "c": None, "s": 1}]}


def check_dv(tools=TOOLS):
    cases = {k: _dv("2026-11-20", v) for k, v in DV.items()}
    cases.update({"y" + d: _dv(d, [{"d": d[:4] + "-01-01", "t": "息", "c": 1}]) for d in ("2027-01-05", "2028-03-01", "2026-11-25")})
    o = T._node(T.HELPERS + "\nconst window = {};\nconst App = { latest: %s, stockCache: {} };\n" % json.dumps(T.LATEST, ensure_ascii=False) + tools +
                "\nconst C = %s, r = {};\nfor (const k in C) { const [o, h] = tlDvLoad(C[k], false); r[k] = [o.y1, h[h.length - 1]]; }\nconsole.log(JSON.stringify(r));" % json.dumps(cases, ensure_ascii=False))
    if o is None:
        return True
    assert o["a"] == ["5", "近一年現金股利 = 2025/11/20 以後 2 次合計"], o["a"]   # 起日當天 9 元不計入
    assert o["m"] == ["2", "近一年現金股利 = 2025/11/20 以後 1 次合計；部分缺值，請自行確認"], o["m"]
    assert o["n"] == ["", "2025/11/20 以後的現金股利官方表沒有分項，請自行確認"], o["n"]
    assert o["z"] == ["", "2025/11/20 以後沒有現金股利"], o["z"]
    assert o["y2027-01-05"][1] == "近一年現金股利 = 2026/01/05 以後 1 次合計"
    assert o["y2028-03-01"][1] == "近一年現金股利 = 2027/03/02 以後 1 次合計"     # 365 天，不另處理閏年
    assert o["y2026-11-25"][1] == "近一年現金股利 = 2025/11/25 以後 1 次合計"
    assert not any(re.search(r"\d{4}-\d\d-\d\d|(?<!\d{4}/)\b\d\d/\d\d 以後", v[1]) for v in o.values())
    for s in ("`近一年現金股利 = 2025/11/25 以後 2 次合計`", "`2025/11/25 以後的現金股利官方表沒有分項，請自行確認`", "`2025/11/25 以後沒有現金股利`"):
        assert s in PM, s


def test_dv():
    check_dv()
    f = _grab(TOOLS, "tlDvLoad")
    assert "md(from)" not in f and f.count(FROM) == 3 and "v.d > from" in f
    assert hashlib.sha1(f.replace(FROM, "${md(from)}").encode()).hexdigest()[:12] == "55ab42fe3d80"   # 其他字面與改前相同


# ─── F47-10 成分股表（驗收 5～10）─────────────────────────────────
ROWS = {"A": (-0.04, 0.04), "B": (0, 0.05), "C": (None, 0), "D": (0, None), "E": (1, 2), "F": (0, 0)}
G5 = {"name": "測試", "codes": ["A", "B", "C", "D", "E", "F", "X"], "quadrant": "漲潮", "net_5d": 1, "streak": 2, "frames": [[1, 0, 0, 1]]}
G4 = {"name": "全零", "codes": ["A", "F"], "quadrant": "退潮", "net_5d": 0, "streak": -1, "frames": [[0, 0, 0, 1]]}
G0 = {"name": "沒有", "codes": ["E", "B"], "quadrant": "觀望", "net_5d": 0, "streak": 1, "frames": [[0, 0, 0, 1]]}
FAKE = r"""
const els = {}, $ = s => els[s] || (els[s] = { innerHTML: '', textContent: '', cls: [],
  classList: { toggle(c, on) { const L = els[s].cls.filter(x => x !== c); els[s].cls = on ? L.concat(c) : L; } },
  querySelectorAll(q) { const h = els[s].innerHTML; return { length: (h.match(q === 'tr.z' ? /<tr [^>]*class="z"/g : q === 'tbody tr' ? /<tr data-code=/g : /<tr[ >]/g) || []).length }; } });   // 其他選擇器（例如 'tr'）連表頭一起算
const txt = s => s.replace(/<[^>]+>/g, '');
"""
FN = ["fmt", "pfmt", "esc", "cls", "sgn", "md", "yi", "pctCell", "groupMeta", "groupRows", "showGroup", "gzFoot", "bubbleList"]


def _latest():
    st = {c: {"n": "名" + c, "c": 10, "p": 1, "n1": a, "n5": b} for c, (a, b) in ROWS.items()}
    return {"stocks": st, "dates": ["2026-11-25"], "flow_date": "2026-11-25"}


def _app_js(app, body):
    return "\n".join(_grab(app, n) for n in FN) + "\nconst App = { latest: %s, group: 'industry' };\n" % json.dumps(_latest(), ensure_ascii=False) + FAKE + body


def check_rows(app=APP):
    o = T._node(_app_js(app, "console.log(JSON.stringify((groupRows(%s).match(/<tr data-code=\"\\w\"[^>]*>/g))));" % json.dumps(G5, ensure_ascii=False)))
    if o is None:
        return True
    assert o == ['<tr data-code="E">', '<tr data-code="B">', '<tr data-code="A" class="z">', '<tr data-code="C">', '<tr data-code="D">', '<tr data-code="F" class="z">'], o   # 5 日由大到小（?? 0），只標記不重排


def check_foot(app=APP):
    o = T._node(_app_js(app, """const r = [], G = %s, st = () => r.push([txt($('#gZ').innerHTML), $('#gTable').cls.join()]);
st(); showGroup(G.g5); st(); App.gzAll = !App.gzAll; gzFoot(); st(); showGroup(G.g4); st(); App.gzAll = !App.gzAll; gzFoot(); st();
showGroup(G.g4); st(); showGroup(G.g0); st(); showGroup(G.g5); r.push($('#gZ').innerHTML); console.log(JSON.stringify(r));""" % json.dumps({"g5": G5, "g4": G4, "g0": G0}, ensure_ascii=False)))
    if o is None:
        return True
    Z = "檔法人 1 日、5 日都是 0億　"
    assert o[:7] == [["", ""], ["另有 2 " + Z + "顯示", "gz"], ["含 2 " + Z + "收合", ""], ["含 2 " + Z + "收合", ""],   # 換族群沿用展開
                     ["2 " + Z + "顯示", "gz"], ["2 " + Z + "顯示", "gz"], ["", "gz"]], o
    assert o[7] == '另有 2 檔法人 1 日、5 日都是 0億　<button type="button" class="chip" data-gz>顯示</button>'
    for s in ("`另有 ${z} 檔法人 1 日、5 日都是 0億　<button type=\"button\" class=\"chip\" data-gz>顯示</button>`",
              "`${z} 檔法人 1 日、5 日都是 0億　<button type=\"button\" class=\"chip\" data-gz>顯示</button>`",
              "`含 ${z} 檔法人 1 日、5 日都是 0億　<button type=\"button\" class=\"chip\" data-gz>收合</button>`"):
        assert s in PM, s


def check_wire(app=APP):
    i = app.index("function renderBubble()")
    seg = app[i:app.index("\nfunction drawBubble(", i)]
    assert '<div class="tbl-wrap panel-list"><table class="tbl" id="gTable"></table></div><div class="muted small g-z" id="gZ"></div></div>`}' in seg   # 捲動框外、同一張卡
    line = "  $('#gZ').addEventListener('click', e => { if (e.target.closest('[data-gz]')) { App.gzAll = !App.gzAll; gzFoot(); } });   // 第 49 輪 F47-10\n"
    assert seg.count(line) == 1 and seg.index("    return;\n  }\n") < seg.index(line) < seg.index("  drawBubble(groups, L.dates);")   # 只在圖模式
    assert "localStore" not in _grab(app, "gzFoot") and "gzAll" not in _grab(app, "bubbleList")


def check_mobile(app=APP):
    old = app.replace("${yi(s.n1) === '0億' && yi(s.n5) === '0億' ? ' class=\"z\"' : ''}", "", 1)
    assert old != app
    js = "const G = %s, r = [];\nfor (const a of [false, true]) { App.blAll = a; App.blOpen = '測試'; r.push(bubbleList(G)); }\nconsole.log(JSON.stringify(r));" % json.dumps([G5, G4], ensure_ascii=False)
    o, w = T._node(_app_js(app, js)), T._node(_app_js(old, js))
    if o is None:
        return True
    assert [s.replace(' class="z"', "") for s in o] == w and o != w


def check_css(css=CSS):
    assert css.endswith("#gTable.gz tr.z{display:none}.g-z{margin-top:6px}   /* 第 49 輪 F47-10 */\n")
    assert len(re.findall(r"tr\.z\b", css)) == 1                              # 只有 #gTable.gz 收起，手機清單不收
    for s in (".panel-list{max-height:420px;overflow:auto}\n", ".panel-list{--th-y:0px}   /* 展開的成分股表",
              ".bl-x .panel-list{max-height:none}.bl-x:not(:has([data-blall=\"1\"])) .panel-list tbody tr:nth-child(n+11){display:none}.bl-x .chip{margin-top:6px}   /* D30-08 */"):
        assert css.count(s) == 1, s


def test_bubble():
    for f in (check_rows, check_foot, check_mobile, check_css, check_wire):
        f()


def test_bubble_data():
    L = json.loads((DATA / "latest.json").read_text(encoding="utf-8"))
    if L["date"] != "2026-11-25":
        print("  （資料日不是 2026-11-25，略過實際筆數）")
        return
    o = T._node("\n".join(_grab(APP, n) for n in FN) + "\nconst App = { latest: JSON.parse(require('fs').readFileSync(%s, 'utf8')) };\n" % json.dumps(str(DATA / "latest.json")) + """
const r = {}, n = h => (h.match(/<tr data-code=/g) || []).length, z = h => (h.match(/ class="z"/g) || []).length;
for (const k in App.latest.groups) for (const g of App.latest.groups[k]) { const h = groupRows(g); r.all = (r.all || 0) + n(h); r.z = (r.z || 0) + z(h); if (k === 'industry') r[g.name] = [n(h), z(h)]; }
console.log(JSON.stringify(r));""")
    if o is None:
        return
    assert [o["all"], o["z"], o["電子零組件"], o["農業科技"], o["觀光餐旅"]] == [4768, 2175, [209, 78], [4, 4], [50, 44]], o


# ─── F47-11 頁頭（驗收 12）────────────────────────────────────────
def test_head_css():
    assert ".s-name{font-size:22px;font-weight:600}\n.s-code{color:var(--text2);margin-left:6px;display:inline-block}\n" in CSS
    i = CSS.index(".s-nm{padding-right:112px}")
    assert CSS.index("\n}\n@media (max-width:374px){.s-name{font-size:17px}}   /* 第 49 輪 F47-11 */\n", i) == CSS.index("\n}\n", i)   # 720 區塊之後
    assert CSS.count(".s-name{") == 2
    assert '<div class="s-nm"><span class="s-name">${esc(data.name)}</span><span class="s-code">${code}</span></div>' in STK
    assert "@media (max-width:720px){.s-head .tl-go{position:absolute;top:36px;right:0;padding:4px 10px;font-size:13px}.s-head .s-px{padding-right:56px}}" in CSS


# ─── F47-12 選股（驗收 15～19）────────────────────────────────────
NAMES = T35.NAMES
NX = {"A": ["2026-11-26", "息", 1], "B": ["2026-12-03", "權息", 1], "C": ["2026-12-04", "權", 0], "D": ["2026-12-05", "其他", 1], "E": ["2027-01-05", "息", None]}
COND = ("  { id: 'nxd', g: '基本面', label: '{v} 天內將除息', opts: [7, 14, 30], def: 14, f: (x, v) => isNum(x.nxa) && x.nxa <= v, cols: ['nx'], "
        "title: '證交所、櫃買中心除權除息預告表中，資料日之後的下一次除息或除權息；天數為日曆天；只有除權（多為現金增資）的不算；以公司公告為準' },")


def _nxd(app):
    return re.search(r"^  \{ id: 'nxd', .*\},(?=   // 第 49 輪)", app, re.M).group(0)


def check_screen(app=APP):
    S = {"d": "2026-11-25", "rows": {}}
    lt = {"date": "2026-11-24", "nx": NX}   # latest.date 故意和 S.d 不同：天數只看 S.d
    o = T._node("\n".join(_grab(app, n) for n in NAMES) + "\nconst App = { screen: { rmd: {}, fqd: {} }, latest: %s };\n" % json.dumps(lt, ensure_ascii=False) + """
const S = %s, out = {}, K = ['nxd', 'nxa', 'nxt'], [, g, f] = SCR_COLS.nx;
for (const c of ['A', 'B', 'C', 'D', 'E', 'Z']) { const x = screenRow(c, { c: 1 }, S); out[c] = K.map(k => k in x ? x[k] : 'u').concat(g(x) == null ? null : f(g(x), x)); }
out.noS = K.some(k => k in screenRow('A', { c: 1 }, null));
delete App.latest; out.noL = K.some(k => k in screenRow('A', { c: 1 }, S));
console.log(JSON.stringify(out));""" % json.dumps(S))
    if o is None:
        return True
    assert o["A"] == ["2026-11-26", 1, "息", '11/26<span class="sub2">1 天後</span>'], o["A"]
    assert o["B"] == ["2026-12-03", 8, "權息", '12/03<span class="sub2">8 天後（權息）</span>'], o["B"]
    assert o["E"][:3] == ["2027-01-05", 41, "息"]
    assert o["C"] == o["D"] == o["Z"] == ["u", "u", "u", None]
    assert o["noS"] is False and o["noL"] is False
    assert re.search(r"^  nx: \['即將除息', x => x\.nxa, .*'</span>', 1\],   // 第 49 輪", app, re.M)   # 近的在前


def check_cond(app=APP):
    line = _nxd(app)
    assert app.index("  { id: 'dvr', g: '基本面'") < app.index(line) < app.index("  { id: 'pb', g: '基本面'")
    o = T._node(_grab(app, "isNum") + "\nconst c = %s;\nconsole.log(JSON.stringify([7, 14, 30].map(v => [1, 7, 8, 14, 15, 30, 31, 41, null, undefined].filter(a => c.f({ nxa: a }, v)))));" % line.strip().rstrip(","))
    if o is None:
        return True
    assert o == [[1, 7], [1, 7, 8, 14], [1, 7, 8, 14, 15, 30]], o


def test_screen():
    check_screen()
    check_cond()
    assert COND + "   // 第 49 輪 F47-12（R71）" in APP.splitlines()
    assert "`" + COND.strip() + "`" in PM
    assert "const SCREEN_GROUPS = ['流動性', '價量', '技術', '法人', '信用', '基本面', '排除'];" in APP


def test_screen_data():
    L = json.loads((DATA / "latest.json").read_text(encoding="utf-8"))
    S = json.loads((DATA / "screen.json").read_text(encoding="utf-8"))
    if L["date"] != "2026-11-25" or S["d"] != "2026-11-25":
        print("  （資料日不是 2026-11-25，略過實際檔數）")
        return
    o = T._node("\n".join(_grab(APP, n) for n in NAMES) + "\nconst App = { screen: { rmd: {}, fqd: {} }, latest: JSON.parse(require('fs').readFileSync(%s, 'utf8')) };\n" % json.dumps(str(DATA / "latest.json")) + """
const S = { d: '%s', rows: {} }, X = Object.keys(App.latest.stocks).map(c => screenRow(c, App.latest.stocks[c], S)), c = [%s][0];
console.log(JSON.stringify([7, 14, 30].map(v => X.filter(x => c.f(x, v)).map(x => x.code).sort())));""" % (S["d"], _nxd(APP).strip().rstrip(",")))
    if o is None:
        return
    w7 = ["2543", "4735", "6523"]
    w14 = w7 + ["1437", "3701", "4749", "7780", "4414", "4912", "6277"]
    w30 = w14 + ["6438", "8942", "5278", "1817"]
    assert o == [sorted(w7), sorted(w14), sorted(w30)], o
    assert not {"3706", "6160", "2345", "2646"} & set(o[2])


# ─── 用詞、node 14、版本與文件（驗收 22、23、26）────────────────────
def _new_segs(app=APP):
    seg = _grab(app, "gzFoot") + "".join(l for l in app.splitlines() + CSS.splitlines() + TOOLS.splitlines() if "第 49 輪" in l)
    return seg + next(l for l in README.splitlines() if l.startswith("- 第 49 輪小項"))


def check_words(app=APP):
    seg = _new_segs(app)
    return all(w not in seg.replace("借券賣出", "") for w in ADVICE)


def test_words_node14():
    assert check_words()
    seg = _new_segs() + _grab(APP, "groupRows") + _grab(APP, "screenRow")
    for w in (".at(", "replaceAll", "||=", "&&=", "??="):
        assert w not in seg, w


def test_version_and_docs():
    for f in ("app.js", "stock.js", "app.css", "tools.js", "help.js", "compare.js"):
        v = hashlib.sha1((SITE / f).read_bytes()).hexdigest()[:8]
        assert f"{f}?v={v}" in HTML, f"index.html 要改成 {f}?v={v}"
    for s in ("help.js?v=a5a5a7e8", "compare.js?v=1c11197d"):
        assert s in HTML, s
    assert HTML.count("https://") == 2
    assert "python3 tests/test_iter49.py" in README
    r = next(l for l in README.splitlines() if l.startswith("- 第 49 輪小項"))
    for s in ("YYYY/MM/DD", "R71", "R72", "0億", "{v} 天內將除息", "17px"):
        assert s in r, s
    assert "第 23 輪" not in r


# ─── 反證 ─────────────────────────────────────────────────────
def test_contrast():
    def sub(src, a, b):
        assert a in src, a
        return src.replace(a, b)
    Z = "${yi(s.n1) === '0億' && yi(s.n5) === '0億' ? ' class=\"z\"' : ''}"
    bad = [
        (check_dv, sub(TOOLS, FROM, "${md(from)}")),                                                   # 起日沒有年份
        (check_dv, sub(TOOLS, "v.d > from", "v.d >= from")),                                           # 含起日當天
        (check_rows, sub(APP, Z, "${Math.abs(s.n1) < 0.1 && Math.abs(s.n5) < 0.1 ? ' class=\"z\"' : ''}")),   # 數值門檻
        (check_rows, sub(APP, Z, Z.replace("yi(s.n1)", "yi(s.n1 ?? 0)").replace("yi(s.n5)", "yi(s.n5 ?? 0)"))),   # null 當 0
        (check_rows, sub(APP, "(S[b].n5 ?? 0) - (S[a].n5 ?? 0)", "(S[a].n5 ?? 0) - (S[b].n5 ?? 0)")),          # 重排
        (check_css, sub(CSS, "#gTable.gz tr.z{display:none}", "tr.z{display:none}")),                    # 不分桌面手機
        (check_mobile, sub(APP, "' class=\"z\"' : ''}><td", "' class=\"z\" hidden' : ''}><td")),            # 手機清單也收起
        (check_foot, sub(APP, "z < n ? '另有 ' : ''", "'另有 '")),                                       # 全部 0 億也寫「另有」
        (check_foot, sub(APP, "t.classList.toggle('gz', !App.gzAll);", "t.classList.toggle('gz', App.gzAll);")),   # 預設展開
        (check_foot, sub(APP, "  gzFoot();\n}\n", "}\n")),                                              # 換族群不更新表尾
        (check_foot, sub(APP, "t.querySelectorAll('tbody tr').length", "t.querySelectorAll('tr').length")),   # 成分股列數含表頭
        (check_wire, sub(APP, "</table></div><div class=\"muted small g-z\" id=\"gZ\"></div></div>`}", "<div class=\"muted small g-z\" id=\"gZ\"></div></table></div></div>`}")),   # 放進捲動框
        (check_screen, sub(APP, "(n[1] === '息' || n[1] === '權息')", "n[1]")),                          # 「權」也算
        (check_screen, sub(APP, "Date.parse(n[0]) - Date.parse(S.d)", "Date.parse(n[0]) - Date.parse(App.latest.date)")),   # 錯誤基準
        (check_screen, sub(APP, "App.latest?.nx?.[code]", "App.latest.nx[code]")),                     # 假 App 沒有 latest 會拋錯
        (check_screen, sub(APP, "'（權息）' : '') + '</span>', 1],", "'（權息）' : '') + '</span>', -1],")),   # 遠的在前
        (check_cond, sub(APP, "isNum(x.nxa) && x.nxa <= v", "isNum(x.nxa) && x.nxa < v")),             # 邊界
        (check_words, sub(APP, "檔法人 1 日、5 日都是 0億　", "檔法人 1 日、5 日都是 0億，" + sorted(ADVICE)[0])),          # 用詞
    ]
    for i, (f, src) in enumerate(bad):
        assert src not in (TOOLS, APP, CSS), i
        assert not _ok(f, src), f"反證 {i} 沒有被擋下（{f.__name__}）"


if __name__ == "__main__":
    for k, v in list(globals().items()):
        if k.startswith("test_") and callable(v):
            v()
            print("ok", k)
