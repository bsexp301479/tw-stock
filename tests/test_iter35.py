"""第 35 輪（不連網、不連資料庫）：F35-1 screen.json 股利欄、F35-2 選股股利條件、F35-3 殖利率條件多填息欄、F35-4 排行「近期除息」。
有 node 時逐字取出 app.js 的程式執行（node 14 可跑：不用 .at()、replaceAll）。"""
import hashlib
import json
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from twstock import export  # noqa: E402

SITE = ROOT / "site"
APP = (SITE / "app.js").read_text(encoding="utf-8")
HTML = (SITE / "index.html").read_text(encoding="utf-8")
EXP = (ROOT / "twstock" / "export.py").read_text(encoding="utf-8")
KEYS = ("dvd", "dvp", "dvn", "dvx", "dvk")


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


def _cond(cid):
    """SCREEN_CONDS 中 id 為 cid 的一行（物件字面）。"""
    m = re.search(rf"^  \{{ id: '{cid}', .*\}},$", APP, re.M)
    assert m, cid
    return m.group(0)


# ─── F35-1：匯出 ────────────────────────────────────────
def r(d, t="息", p=100.0, **kw):
    return {"d": d, "t": t, "p": p, **kw}


def test_div_screen():
    T = date(2026, 11, 19)
    none = dict(dvd=None, dvp=None, dvn=None, dvx=None, dvk=0)
    assert export.div_screen([], T) == none
    assert export.div_screen([r("2026-08-01", "權", k="s")], T) == none                        # 純配股不算
    assert export.div_screen([r("2025-11-18", f="2025-11-20", n=3)], T) == none                 # 第 366 天：不算
    assert export.div_screen([r("2025-11-19", f="2025-11-20", n=2)], T) == dict(dvd="2025-11-19", dvp=100.0, dvn=2, dvx=None, dvk=1)   # 第 365 天：算
    # 季配：只看最近一次；次數算近 365 天的息、權息（不含權）
    dv = [r("2025-10-31", f="2025-11-03", n=2), r("2026-03-17", f="2026-03-17", n=1), r("2026-06-11", "權", k="s"),
          r("2026-06-12", "權息", 50.5, k="sc", c=1.0), r("2026-09-16", p=80.0)]
    assert export.div_screen(dv, T) == dict(dvd="2026-09-16", dvp=80.0, dvn=None, dvx=None, dvk=3)
    # 中斷：x = [日期, 原因]
    assert export.div_screen([r("2026-07-01", x=["2026-08-10", "減資"])], T) == dict(dvd="2026-07-01", dvp=100.0, dvn=None, dvx="減資", dvk=1)
    # 最近一次是純配股時，用前一次的息
    assert export.div_screen([r("2026-07-01", f="2026-07-30", n=20), r("2026-08-01", "權", k="s")], T)["dvd"] == "2026-07-01"


def test_export_wiring():
    assert set(KEYS) <= set(export.SCREEN_KEYS) and len(set(export.SCREEN_KEYS)) == len(export.SCREEN_KEYS)
    # 個股 JSON 的 dv 不動（test_iter24 鎖定）；screen 用同一組參數再算一次，結果相同
    assert EXP.count("dividends(d_, c, ev, events.get(code, []))") == 2
    assert '"dv": dividends(d_, c, ev, events.get(code, [])),' in EXP
    assert "**div_screen(dividends(d_, c, ev, events.get(code, [])), latest_date),   # 第 35 輪" in EXP
    assert EXP.index("**div_screen(dividends(") < EXP.index("**osc_stats(o, h, l, c, af)}")
    # screen_build 輸出新欄（欄式）
    rows = {"1101": {**dict.fromkeys(export.SCREEN_KEYS), "rm": None, "dvd": "2026-09-16", "dvk": 1}}
    S = export.screen_build(rows, {"d": "2026-11-19"})
    assert S["dvd"] == ["2026-09-16"] and S["dvk"] == [1] and S["dvn"] == [None]


def test_real_data():
    """已匯出新欄位時：screen.json 每檔的股利欄 = 個股 JSON 的 dv 推導，0 差異（還沒匯出就略過）。"""
    p = SITE / "data" / "screen.json"
    if not p.exists():
        print("  （沒有 screen.json，略過）")
        return
    S = json.loads(p.read_text(encoding="utf-8"))
    if "dvd" not in S:
        print("  （screen.json 還沒有股利欄，略過）")
        return
    T, bad = date.fromisoformat(S["d"]), []
    for i, c in enumerate(S["codes"]):
        f = SITE / "data" / "stocks" / f"{c}.json"
        if not f.exists():
            continue
        want = export.div_screen(json.loads(f.read_text(encoding="utf-8"))["dv"], T)
        if {k: S[k][i] for k in KEYS} != want:
            bad.append(c)
    assert not bad, bad[:10]


# ─── 前端 ──────────────────────────────────────────────
NAMES = ["fmt", "sgn", "yi", "streakTxt", "isNum", "md", "spct", "int0", "MARGIN_BASE", "screenRow", "revMonth", "finQ", "finTag", "REV_BASE", "revLow", "epsLow", "SCR_COLS"]
HEAD = "const App = { screen: { rmd: {}, fqd: {} } };\n"


def test_screen_row_cols():
    S = {"d": "2026-11-19", "rows": {
        "A": {"dvd": "2026-09-16", "dvp": 80.0, "dvn": None, "dvx": None, "dvk": 3},   # 未填
        "B": {"dvd": "2026-11-19", "dvp": 50.0, "dvn": 1, "dvx": None, "dvk": 1},      # 當天填息
        "C": {"dvd": "2026-07-01", "dvp": 10.0, "dvn": None, "dvx": "減資", "dvk": 1},  # 中斷
        "D": {"dvd": None, "dvp": None, "dvn": None, "dvx": None, "dvk": 0},           # 沒有
        "E": {"dvd": "2026-10-01", "dvp": 20.0, "dvn": None, "dvx": None, "dvk": 1}}}  # 未填、今天無收盤
    LT = {"A": {"c": 60.0}, "B": {"c": 51.0}, "C": {"c": 8.0}, "D": {"c": 30.0}, "E": {"c": None}}
    o = _node("\n".join(_grab(APP, n) for n in NAMES) + HEAD + f"""
const S = {json.dumps(S)}, LT = {json.dumps(LT)}, out = {{}};
for (const c in LT) {{ const x = screenRow(c, LT[c], S), [, g, f] = SCR_COLS.dv, [, g2, f2] = SCR_COLS.dvg;
  out[c] = [x.dva === undefined ? 'u' : x.dva, x.dvg === undefined ? 'u' : x.dvg, g(x) == null ? null : f(g(x), x), g2(x) == null ? null : f2(g2(x), x)]; }}
out.noS = screenRow('A', LT.A, null).dva === undefined;
console.log(JSON.stringify(out));""")
    if o is None:
        return
    assert o["A"] == [64, -25, '09/16<span class="sub2">未填息</span>', "-25.00%"]
    assert o["B"] == [0, None, '11/19<span class="sub2">1 天填息</span>', None]
    assert o["C"] == [141, None, '07/01<span class="sub2">中斷（減資）</span>', None]
    assert o["D"] == ["u", "u", None, None]
    assert o["E"][:2] == [49, None]
    assert o["noS"] is True
    assert SCR_COLS_DIRS() == {"dv": 1, "dvg": 1}


def SCR_COLS_DIRS():
    return {k: int(re.search(rf"^  {k}: \[.*, (-?1)\],$", APP, re.M).group(1)) for k in ("dv", "dvg")}


def test_conds():
    lines = [_cond(c) for c in ("dy", "dvk", "dvf", "dvu", "dvr")]
    assert APP.index(lines[0]) < APP.index(lines[1]) < APP.index(lines[2]) < APP.index(lines[3]) < APP.index(lines[4]) < APP.index("  { id: 'pb', g: '基本面'")
    assert "cols: ['dy', 'dv', 'dvg'] }" in lines[0]
    X = [{"code": "A", "dvd": "2026-09-16", "dva": 64, "dvn": None, "dvx": None, "dvk": 3, "dy": 6, "cap": 0},
         {"code": "B", "dvd": "2026-11-19", "dva": 0, "dvn": 1, "dvx": None, "dvk": 1, "dy": 2, "cap": 0},
         {"code": "C", "dvd": "2026-07-01", "dva": 141, "dvn": None, "dvx": "減資", "dvk": 1, "dy": 5, "cap": 1},
         {"code": "D", "dvk": 0, "dy": 0, "cap": 0},
         {"code": "E", "dva": 91, "dvd": "2026-08-20", "dvn": 5, "dvk": 1, "dy": None, "cap": 0},
         {"code": "F", "dva": 60, "dvd": "2026-09-20", "dvn": None, "dvk": 1, "dy": 5, "cap": 0}]
    o = _node("\n".join(_grab(APP, n) for n in ("isNum", "valGuard", "DV_NOTE", "DV_TITLE")) + f"""
const C = [{",".join(l.rstrip(",") for l in lines)}], X = {json.dumps(X)}, out = {{}};
for (const c of C) for (const v of c.opts || [1]) out[c.id + v] = X.filter(x => c.f(x, v, {{ xc: 1 }})).map(x => x.code).join('');
out.cols = C.map(c => c.cols.join());
out.def = C.find(c => c.id === 'dvr').def;
console.log(JSON.stringify(out));""")
    if o is None:
        return
    assert o["dy5"] == "AF" and o["dy3"] == "AF"                 # C 股本變動排除
    assert o["dvk1"] == "ABCEF" and o["dvf1"] == "BE" and o["dvu1"] == "AF"
    assert o["dvr30"] == "B" and o["dvr60"] == "BF" and o["dvr90"] == "ABF"
    assert o["cols"] == ["dy,dv,dvg", "dv", "dv", "dv,dvg", "dv"] and o["def"] == 60
    assert "const SCREEN_GROUPS = ['流動性', '價量', '技術', '法人', '信用', '基本面', '排除'];" in APP      # 不加新組


def test_rank():
    assert "['dy', '殖利率', 'dy', -1, 'v'], ['dv', '近期除息', 'dva', 1, 'x'], ['pe', '本益比最低', 'pe', 1, 'v']," in APP
    assert "['基本面', ['ry', 'dy', 'dv', 'pe']]" in APP
    assert "dv: x => x.dva <= 90," in APP[APP.index("const RANK_FILTER"):APP.index("const RANK_COLS")]
    assert "dy: ['dy', 'pe', 'pb', 'dv'], dv: ['dv', 'dy']," in APP
    # 排行：isNum(x[field]) 篩選、dir * (a - b) 由近到遠、同天依成交額
    assert ".sort((a, b) => dir * (a[field] - b[field]) || (src === 'm' ? (a.code < b.code ? -1 : 1) : b.tv - a.tv)).slice(0, 50);" in APP
    assert "(by === 'dv' ? '近期除息 = 近 90 天內除息或除權息，依除息日由近到遠。' + DV_NOTE : '') +" in APP
    # 最近除息欄不依正負上色
    assert "'lb', 'lp', 'mc', 'to'].includes(k) || k === 'dv' ? '' : cls(v)" in APP


def test_notes():
    assert "融資增加率、券資比只計入融資 1,000 張以上的股票。${DV_NOTE}</div></section>`;" in APP
    note = _grab(APP, "DV_NOTE")
    for s in ("只看近 365 天最近一次", "純配股不算", "原始收盤回到除息前收盤", "填息天數含除息當天", "標「中斷」", "股價資料起點以前的除息不在範圍內",
              "殖利率用去年股利 ÷ 今天收盤，股價下跌時殖利率會變高"):
        assert s in note, s


def test_version():
    v = hashlib.sha1((SITE / "app.js").read_bytes()).hexdigest()[:8]
    assert f'src="app.js?v={v}"' in HTML, f"site/index.html 的 app.js 版本參數請改成 ?v={v}"


def test_no_advice_words():
    seg = "".join(l for l in APP.splitlines() if ("第 35 輪" in l or "DV_" in l or re.search(r"'dv[kfurg]?'|近期除息", l))
                  and "篩選結果只是條件的機械比對" not in l)                     # 選股頁說明（舊文字）只多接 ${DV_NOTE}，由 test_notes 檢查
    seg += EXP[EXP.index("def div_screen"):EXP.index("def amount_by_market")]
    assert "填息" in seg and "近期除息" in seg
    for w in ("買進", "賣出", "反彈", "見底", "買點", "超賣", "超買", "推薦", "強勢", "飆股", "勝率", "亮點", "建議", "低估", "高估",
              "便宜", "價值陷阱", "划算", "安全", "危險"):
        assert w not in seg, w


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_") and callable(f):
            print("==", n); f()
    print("全部通過")
