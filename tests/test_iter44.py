"""第 44 輪（不連網、不連資料庫）：小項整理 F44-1～F44-7。
F44-1 交易成本預設非當沖、F44-2a／2b 斷行 CSS、F44-2c／F44-7 籌碼卡 .nw、F44-3 今日小卡報酬率上色、
F44-4 預告表 NaN／Infinity、F44-5 ETF「發行人」、F44-6 集保全部略過印 ⚠️。
有 node 時逐字取出 app.js、stock.js、tools.js 的程式執行；檢查函式都接受要檢查的原始碼或函式，test_contrast 改壞後重跑，確認會失敗。"""
import contextlib
import hashlib
import io
import json
import re
import sys
from decimal import Decimal
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
import test_iter28 as t28  # noqa: E402
import test_iter34 as T  # noqa: E402
import test_iter40 as t40  # noqa: E402
import test_iter41 as T41  # noqa: E402
import test_iter42 as T42  # noqa: E402
import test_iter43 as t43  # noqa: E402
from twstock import db  # noqa: E402
from twstock.collectors import notices, tdcc  # noqa: E402

SITE, HTML, TOOLS, APP, STK, CSS = T.SITE, T.HTML, T.TOOLS, T.APP, T.STK, T.CSS
TODAY = "2026-11-21"
tag = lambda s: re.sub(r"<[^>]+>", "", s)


def _tools(body, src=TOOLS):
    return T._node(T.HELPERS + "\nconst window = {};\nconst App = { latest: %s, stockCache: {} };\n" % json.dumps(T.LATEST, ensure_ascii=False)
                   + src + "\n" + body)


# ─── F44-1 交易成本預設非當沖（驗收 1～3）──────────────────────────
def check_dt(src=TOOLS):
    o = _tools("""const f = x => tlDtOut(Object.assign({}, TL.dt, { b: '100', d: '10', m: '20' }, x), null, '%s');
console.log(JSON.stringify({ mode: TL.dt.mode, form: tlDtForm(TL.dt), g: f({}), dt: f({ mode: 'dt' }),
  e: [f({ k: 'e' }), f({ k: 'e', mode: 'g' }), f({ k: 'b' }), f({ k: 'b', mode: 'g' })] }));""" % TODAY, src)
    if o is None:
        return []
    bad = []
    if o["mode"] != "g" or '<button data-v="g" class="on">非當沖</button>' not in o["form"] or 'data-g="dir"' in o["form"]:
        bad.append(("預設表單", o["mode"]))
    if "證交稅：股票 0.3%" not in o["g"] or "當沖需符合券商資格" in o["g"] or "0.15%" in o["g"]:
        bad.append("預設規則行")
    if "現股當沖 0.15%（至 2027/12/31）" not in o["dt"] or "當沖需符合券商資格；處置、全額交割股可能不能當沖。" not in o["dt"]:
        bad.append("切到當沖")
    if o["e"][0] != o["e"][1] or o["e"][2] != o["e"][3]:
        bad.append("ETF／債券 ETF 預設和非當沖不同")
    return bad


def test_dt_default():
    assert check_dt() == []


# ─── F44-2a／2b CSS（驗收 4、5）─────────────────────────────────
LINE = ".dv-nx{word-break:keep-all}.tl-lg+.muted.small{text-wrap:pretty}.chip-g .stat .s{word-break:keep-all}   /* 第 44 輪：375 寬不拆「預告」、複利座標說明不剩單字、籌碼卡不拆「（百分點）」（QA44-01） */"


def check_css(css=CSS):
    return [] if css.splitlines().count(LINE) == 1 else ["app.css 第 44 輪那一行"]


def test_css():
    assert check_css() == []
    assert TOOLS.count('tl-lg">') == 1 and TOOLS.count('</div><div class="muted small">第 0～${n} 年；縱軸 0～') == 1   # 選擇器只命中複利座標說明
    assert STK.count('<div class="small dv-nx">') == 1


# ─── F44-2c 股權分散卡、F44-7 外資持股卡（驗收 6、7）──────────────
NW = re.compile(r'<span class="nw">([^<]*)</span>')


def check_sh(src=STK):
    o = t28._node(t28.HELPERS + "\n" + t28._grab(src, "shCards") + "\nconsole.log(JSON.stringify(%s.map(([sh, E]) => shCards(sh, E))));"
                  % json.dumps([[sh, e] for sh, e, w in t43.CARDS if not isinstance(w, str)]))
    if o is None:
        return []
    bad = []
    for got, want in zip(o, [w for _, _, w in t43.CARDS if not isinstance(w, str)]):
        subs = [c[3] for c in got]
        spans = [x for s in subs for x in NW.findall(s)]
        if len(spans) != 8 or not all(re.fullmatch(r"[14]週 (?:--|[-+]?[\d,.]+)", x) for x in spans) or [tag(s) for s in subs] != [tag(c[3]) for c in want]:
            bad.append(subs)
    return bad


def test_sh_cards():
    assert check_sh() == []


FH_NEW = '`<span class="nw">5日 ${fhd(5)}</span>　<span class="nw">20日 ${fhd(20)}</span>（百分點）`'


def check_fh(src=STK):
    return [] if src.count(FH_NEW) == 1 and tag(FH_NEW) == "`5日 ${fhd(5)}　20日 ${fhd(20)}（百分點）`" else ["外資持股卡"]


def test_fh_card():
    assert check_fh() == []


# ─── F44-3 今日小卡報酬率上色（驗收 8）────────────────────────────
def check_hold(app=APP):
    o = T42._run("console.log(JSON.stringify(%s.map(u => holdLine({ n: 1, d: '0', u, t: '100000', k: 0 }, App.latest))));"
                 % json.dumps(["5000", "-5000", "0"]), app)
    if o is None:
        return []
    bad = []
    for h, c, p in zip(o, ("up", "dn", "flat"), ("+5.00%", "-5.00%")):
        m = re.search(r'未實現損益 <b class="(\w+)">[^<]+</b> 元（<b class="(\w+)">([^<]+)</b>）', h)
        if not m or m.group(1) != c or m.group(2) != c or (c != "flat" and m.group(3) != p):
            bad.append(h)
    return bad


def test_hold_line():
    assert check_hold() == []


# ─── F44-4 預告表 NaN／Infinity（驗收 9）──────────────────────────
Z = Decimal(0)
TW_BAD = [  # 假資料：1437 那一列改成非有限值
    ["115年12月03日", "1437", "勤益控", "息", "Infinity", "-Infinity", "52.00000000", "NaN", "", "", "", "", ""],
    ["115年12月04日", "2345", "智邦", "權", "0.00000000", "sNaN", "52.00000000", "nan", "", "", "", "", ""]]
TP_BAD = [t40._tp("1151126", "6523", "假資料", "除權息", "inf", "-inf", "62.00", "-Infinity"),
          t40._tp("1151127", "6524", "假資料", "除息", "0.00000000", "0.00000000", "0.00", "4.00000000")]


def check_nonfinite(parse=notices.parse_notices):
    bad = t40.check_parse(parse)
    got = parse("TWSE", dict(t40.TWSE, data=TW_BAD)) + parse("TPEx", TP_BAD)
    want = [t40.N("1437", t40.D(12, 3), "息", None), t40.N("2345", t40.D(12, 4), "權", None),
            t40.N("6523", t40.D(11, 26), "權息", None), t40.N("6524", t40.D(11, 27), "息", Decimal(4))]
    if got != want:
        bad.append(got)
    return bad


def test_nonfinite():
    assert check_nonfinite() == []


# ─── F44-5 ETF「發行人」（驗收 10）────────────────────────────────
DV = {"dv": [{"d": "2026-08-20", "t": "息", "c": 0.5, "s": None}], "market": "TWSE", "prices": {"d": ["2025-11-19", "2026-11-19"]}}
WANT_DV = [("已帶入 08/20 的股利（最近一次），下次請依發行人公告修改", "已帶入 08/20 的股利（最近一次），下次請依公司公告修改"),
           ("2025-11-19 起沒有除權息紀錄，請依發行人公告填寫", "2025-11-19 起沒有除權息紀錄，請依公司公告填寫")]


def check_dv(src=TOOLS):
    o = _tools("console.log(JSON.stringify(%s.map(d => [tlDvLoad(d, true)[1], tlDvLoad(d, false)[1]])));" % json.dumps([DV, dict(DV, dv=[])]), src)
    if o is None:
        return []
    return [] if [tuple(h[0] for h in x) for x in o] == WANT_DV else [o]


def test_etf_wording():
    assert check_dv() == []


# ─── F44-6 集保全部略過（驗收 11、12）─────────────────────────────
WARN = "  ⚠️ 集保股權分散 2026-11-20：股票 0 檔、ETF 0 檔，略過 1 檔（合計不符），官方格式可能改變，請檢查\n"


class Conn0(t43.Conn):
    def fetchall(self):
        return []                                           # 假資料庫：可寫的列都不在 stocks、etfs


def check_tdcc(collect=tdcc.collect_tdcc):
    bad = t43.check_write(collect)

    def run(ls, conn):
        conns, buf = [], io.StringIO()
        with mock.patch.object(tdcc, "request", lambda *a, **k: t43._resp(t43.csv_text(ls))), \
                mock.patch.object(db, "connect", lambda: conns.append(conn()) or conns[-1]), contextlib.redirect_stdout(buf):
            return collect(None, t43.D(11, 23)), conns, buf.getvalue()
    ed = t43.edit("2421  ", 17, n=1)
    for ls, conn, n, want in (
            ([x for x in ed if ",2421  ," in x or ",01001T," in x], None, 0, WARN),                     # 唯一要收的 2421 合計不符 → 全部略過
            ([x for x in ed if ",01001T," in x or ",2881A ," in x], None, 0,                           # QA：0 列可寫、沒有略過 → 仍是 🏦
             "  🏦 集保股權分散 2026-11-20：股票 0 檔、ETF 0 檔\n"),
            ([x for x in ed if ",2421  ," in x or ",000218," in x], Conn0, 1,                         # QA：有可寫的列但都不在本站、另有略過 → 仍是 🏦
             "  🏦 集保股權分散 2026-11-20：股票 0 檔、ETF 0 檔，略過 1 檔（合計不符）\n")):
        rec, conns, out = run(ls, conn)
        if len(conns) != n or rec != {"on": "2026-11-23", "d": "2026-11-20", "s": 0, "e": 0} or out != want:
            bad.append((len(conns), rec, out))
    return bad


def test_tdcc_all_skipped():
    assert check_tdcc() == []


# ─── ?v=、文件、用詞（驗收 15、17）────────────────────────────────
def test_versions_docs_words():
    for f in ("app.css", "app.js", "stock.js", "tools.js"):
        v = hashlib.sha1((SITE / f).read_bytes()).hexdigest()[:8]
        assert f'{f}?v={v}"' in HTML, f"site/index.html 的 {f}?v= 請改成 {v}"
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "python3 tests/test_iter44.py" in readme and "第 44 輪" in readme
    assert "第 44 輪" in (ROOT / "docs" / "iterations" / "README.md").read_text(encoding="utf-8")
    new = "".join(WANT_DV[0] + WANT_DV[1]) + WARN
    assert not [w for w in T42.ADVICE if w in new]


# ─── 反證 ─────────────────────────────────────────────
PY_MUTANTS = [
    ("NaN 不過濾", notices, "parse_notices", "x if (x := clean_number(r[names[k]], Decimal)) is None or x.is_finite() else None",
     "clean_number(r[names[k]], Decimal)", check_nonfinite),
    ("只濾 NaN 不濾 Infinity", notices, "parse_notices", "x.is_finite()", "not x.is_nan()", check_nonfinite),
    ("全部略過仍印 🏦", tdcc, "collect_tdcc", "bad = skipped and not rows", "bad = False", check_tdcc),
    ("部分略過也印 ⚠️", tdcc, "collect_tdcc", "bad = skipped and not rows", "bad = skipped", check_tdcc),
    ("沒有提示字", tdcc, "collect_tdcc", '("，官方格式可能改變，請檢查" if bad else "")', '""', check_tdcc),
    ("0 列可寫也印 ⚠️", tdcc, "collect_tdcc", "bad = skipped and not rows", "bad = not rows", check_tdcc),                 # QA 補
    ("改看寫入結果 out", tdcc, "collect_tdcc", "bad = skipped and not rows", "bad = skipped and not out", check_tdcc),   # QA 補
]
JS_MUTANTS = [  # (名稱, 原始碼, 原字串, 改壞後, 檢查)
    ("預設仍是當沖", TOOLS, "dt: { mode: 'g',", "dt: { mode: 'dt',", check_dt),
    ("沒有紀錄仍寫公司", TOOLS, "請依${e ? '發行人' : '公司'}公告填寫", "請依公司公告填寫", check_dv),
    ("最近一次仍寫公司", TOOLS, "下次請依${e ? '發行人' : '公司'}公告修改", "下次請依公司公告修改", check_dv),
    ("發行人與公司對調", TOOLS, "下次請依${e ? '發行人' : '公司'}公告修改", "下次請依${e ? '公司' : '發行人'}公告修改", check_dv),
    ("比例卡沒有 nw", STK, '`<span class="nw">1週 ${w(a, 1, 2)}</span>　<span class="nw">4週 ${w(a, 4, 2)}</span>（百分點）`',
     "`1週 ${w(a, 1, 2)}　4週 ${w(a, 4, 2)}（百分點）`", check_sh),
    ("人數卡沒有 nw", STK, '`<span class="nw">1週 ${w(sh.n, 1, 0)}</span>　<span class="nw">4週 ${w(sh.n, 4, 0)}</span>（人）',
     "`1週 ${w(sh.n, 1, 0)}　4週 ${w(sh.n, 4, 0)}（人）", check_sh),
    ("nw 連單位一起包", STK, '4週 ${w(a, 4, 2)}</span>（百分點）', '4週 ${w(a, 4, 2)}（百分點）</span>', check_sh),
    ("外資持股卡沒有 nw", STK, FH_NEW, "`5日 ${fhd(5)}　20日 ${fhd(20)}（百分點）`", check_fh),
    ("報酬率沒有上色", APP, '元（<b class="${cls(Number(V.u))}">${holdP(V.u, V.t)}</b>）', "元（${holdP(V.u, V.t)}）", check_hold),
    ("報酬率顏色看今日損益", APP, '元（<b class="${cls(Number(V.u))}">', '元（<b class="${cls(Number(V.d))}">', check_hold),
    ("拿掉 CSS 那一行", CSS, LINE + "\n", "", check_css),
    ("籌碼卡沒有 keep-all", CSS, ".chip-g .stat .s{word-break:keep-all}", "", check_css),                                    # QA44-01
]


def test_contrast():
    for name, mod, fn, a, b, check in PY_MUTANTS:
        with t40._mutate(mod, fn, a, b) as f, contextlib.redirect_stdout(io.StringIO()):
            try:
                fails = check(f)
            except Exception as e:                                                                             # 改壞到執行失敗也算擋下
                fails = [repr(e)]
        assert fails, "反證沒有擋下：" + name
    node = t28._node("console.log('1')") is not None
    for name, src, a, b, check in JS_MUTANTS:
        assert src.count(a) == 1, (name, a)
        if node or check is check_css or check is check_fh:
            assert check(src.replace(a, b)), "反證沒有擋下：" + name


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_") and callable(f):
            print("==", n); f()
    print("全部通過")
