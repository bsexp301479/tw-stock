"""第 50 輪（不連網、不連資料庫）：收在漲停／跌停 F50-1（R73：export.limit_flag、snapshot 的 lm、表格小字、頁頭、選股條件、
排行說明）、主動 ETF 折溢價 F50-12（holding_export 的 close → sum.pc、sum.pm；持股頁淨值卡與說明）。
有 node 時逐字取出 app.js 的函式執行（node 14 可跑）；畫面文字和 docs/iterations/50/02-pm.md 二之一逐字比對。
檢查函式都接受原始碼，最後的 test_contrast 把原始碼改壞（反證），確認對應的檢查會失敗。
實際資料（11/25）的檢查只在資料日 2026-11-25 時核對筆數，其他日子印「略過」。"""
import hashlib
import json
import re
import sys
from decimal import ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP, Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
import test_iter05 as T05  # noqa: E402
import test_iter34 as T  # noqa: E402
import test_iter35 as T35  # noqa: E402
import test_iter47 as T47  # noqa: E402
from twstock import export  # noqa: E402

SITE, HTML, APP, STK = T.SITE, T.HTML, T.APP, T.STK
EXP = (ROOT / "twstock" / "export.py").read_text(encoding="utf-8")
README = (ROOT / "README.md").read_text(encoding="utf-8")
DOCS = (ROOT / "docs" / "iterations" / "README.md").read_text(encoding="utf-8")
PM = (ROOT / "docs" / "iterations" / "50" / "02-pm.md").read_text(encoding="utf-8")
DATA = SITE / "data"
_grab = T35._grab
_T23 = (ROOT / "tests" / "test_iter23.py").read_text(encoding="utf-8")
_T23 = _T23[_T23.index('    for w in ("', _T23.index("assert seg.count(\"第 23 輪\")")):]
ADVICE = T47.ADVICE | set(re.findall(r'"([^"]+)"', _T23[:_T23.index("):")]))   # test_iter23:343～345 的清單（不在本檔重寫用詞）
LATEST = json.loads((DATA / "latest.json").read_text(encoding="utf-8")) if (DATA / "latest.json").exists() else None
IS_1125 = bool(LATEST) and LATEST.get("date") == "2026-11-25"


def _ok(f, *a):
    try:
        return f(*a) is not False
    except Exception:   # node 拋錯或 assert 失敗都算檢查失敗
        return False


def _sub(src, a, b):
    assert a in src, a
    return src.replace(a, b)


def _pyfunc(src, name):
    m = re.search(rf"^def {name}\(.*?(?=^\S)", src, re.M | re.S)
    assert m, name
    return m.group(0).rstrip()


def _pyload(src, name):
    """從（可能改壞的）export.py 原始碼取出函式，在 export 模組的名稱空間執行。"""
    ns = dict(vars(export))
    exec(_pyfunc(src, name), ns)
    return ns[name]


# ─── F50-1a limit_flag（驗收 1～4）──────────────────────────────
UP = [(1015, 88), (19.8, 1.8), (7.78, 0.7), (106.5, 9.3), (100.0, 8.7), (1085, 95), (10.0, 0.9), (50.0, 4.5)]
DN = [(153.0, -16.5), (101.5, -11.0), (92.7, -10.3), (11.5, -1.25), (914, -101), (1.17, -0.13)]
NONE = [(92.8, -10.2), (125.0, 10.5), (None, 1.0), (10.0, None), (None, None), (5.0, 5.0), (5.0, 6.0), (0, 0), (0.0, 0.0), (19.7, 1.8), (153.5, -16.5)]


def check_limit(src=EXP):
    f = _pyload(src, "limit_flag")
    for c, ch in UP:
        assert f(c, ch) == 1 and type(f(c, ch)) is int, (c, ch)
        assert f(Decimal(str(c)), ch) == 1, (c, ch)                       # snapshot 傳 Decimal 收盤
        assert f(c, ch, True) is None, (c, ch)                            # 新上市前 5 日不標
    for c, ch in DN:
        assert f(c, ch) == -1 and type(f(c, ch)) is int, (c, ch)
        assert f(c, ch, True) is None, (c, ch)
    for c, ch in NONE:
        assert f(c, ch) is None, (c, ch)
    return True


def test_limit_flag():
    assert check_limit()
    fn = _pyfunc(EXP, "limit_flag")
    assert "Decimal(str(close))" in fn and "Decimal(str(change))" in fn and "_TICKS" in fn and "float" not in fn
    assert "ROUND_FLOOR" in fn and "ROUND_CEILING" in fn
    assert EXP.index("def _tick_round(") < EXP.index("def limit_flag(") < EXP.index("def _changes(")
    assert float(Decimal("1.30") * Decimal("0.9")) == 1.17 and 1.30 * 0.9 != 1.17    # 浮點陷阱存在（所以要 Decimal）


# ─── F50-1a snapshot 接法、匯出訊息（驗收 5）─────────────────────────
LM_LINE = ('            **({"lm": lm} if (lm := None if no_trade else limit_flag(c[-1], chs[-1], d_[0] > db_first and len(d_) <= 5)) else {}),'
           '   # 第 50 輪 F50-1（R73）：收在漲停 1、跌停 -1\n')
REL_LINE = '            **({"rel": str(rel[-1])} if not no_trade and rel[-1] else {}),\n'
LOCKED = {"_tick_round": "fd737ff5b81b", "_changes": "34897f07a8a6", "_side": "f0725ca1cd87"}


def check_snapshot(src=EXP):
    assert REL_LINE + LM_LINE in src
    assert src.count("limit_flag(") == 2                       # 定義＋snapshot 一處
    for n, h in LOCKED.items():
        assert hashlib.sha1(_pyfunc(src, n).encode()).hexdigest()[:12] == h, n
    i = src.index('    print(f"  📌 還原事件 ')
    seg = src[i:src.index("\n    print(f\"  📌 ETF 個股", i)]
    assert "收在漲停 上市 {lm_n('TWSE', 1)}／上櫃 {lm_n('TPEx', 1)}、跌停 上市 {lm_n('TWSE', -1)}／上櫃 {lm_n('TPEx', -1)}" in seg
    assert "（本站推算；官方 漲停 上市 {lm_o('TWSE', 'ul')}／上櫃 {lm_o('TPEx', 'ul')}、跌停 上市 {lm_o('TWSE', 'dl')}／上櫃 {lm_o('TPEx', 'dl')}）" in seg
    ns = {"snapshot": {"a": {"m": "TWSE", "lm": 1}, "b": {"m": "TWSE"}, "c": {"m": "TPEx", "lm": -1}, "d": {"m": "TPEx", "lm": -1}},
          "official_breadth": {"TWSE": {"ul": 1, "dl": 0}}}   # 官方 0 要寫 0（不是 --）；TPEx 沒有 → --
    out = []
    ns["print"] = lambda *a: out.append(" ".join(map(str, a)))
    exec("\n".join(l[4:] for l in seg.splitlines()[1:]), ns)
    assert out == ["  📌 收在漲停 上市 1／上櫃 0、跌停 上市 0／上櫃 2（本站推算；官方 漲停 上市 1／上櫃 --、跌停 上市 0／上櫃 --）"], out
    return True


def test_snapshot():
    assert check_snapshot()


# ─── F50-1 實際資料 11/25（驗收 6、12）──────────────────────────
def _calc_1125():
    """用 latest.json 的 c、ch 與 stocks/*.json 的第一筆日線，獨立套 limit_flag（和 export 是否已跑無關）。"""
    first = "2025-10-30"
    out = {}
    for code, s in LATEST["stocks"].items():
        if s.get("nt"):
            continue
        d = json.loads((DATA / "stocks" / f"{code}.json").read_text(encoding="utf-8"))["prices"]["d"]
        if (x := export.limit_flag(s["c"], s["ch"], d[0] > first and len(d) <= 5)) is not None:
            out[code] = x
    return out


def test_data_1125():
    if not IS_1125:
        print("  （資料日不是 2026-11-25，略過 11/25 筆數核對）")
        return
    S, o = LATEST["stocks"], {m: LATEST["breadth"][m]["o"] for m in ("TWSE", "TPEx")}
    calc = _calc_1125()
    by = lambda d, m, v: sorted(c for c, x in d.items() if x == v and S[c]["m"] == m)
    assert by(calc, "TWSE", 1) == ["1598", "2471", "6614", "7765"] and by(calc, "TPEx", 1) == ["3664", "6140", "7767"]
    assert [len(by(calc, m, v)) for m in ("TWSE", "TPEx") for v in (1, -1)] == [o["TWSE"]["ul"], o["TWSE"]["dl"], o["TPEx"]["ul"], o["TPEx"]["dl"]] == [4, 46, 3, 54]
    assert calc.get("2313") == -1 and "6907" not in calc and "2330" not in calc
    lm = {c: s["lm"] for c, s in S.items() if "lm" in s}
    if not lm:
        print("  （latest.json 還沒有 lm：PG 套用後 export 再核對）")
        return
    assert lm == calc                                           # export 的 lm = 獨立計算
    assert not any("nt" in S[c] for c in lm) and set(lm.values()) <= {1, -1}
    assert not any("lm" in r for r in LATEST["etfs"]["rows"].values())
    cond = _cond()
    if cond is not None:
        rows = [dict(s, code=c) for c, s in S.items()]
        assert _node_cond(cond, rows, [1, -1]) == [7, 100]       # 驗收 12：只套 lm 的檔數


# ─── F50-1b 表格小字（驗收 8、9）──────────────────────────────
def _pct_js(app):
    return T.HELPERS + "\n" + _grab(app, "sgn") + "\n" + _grab(app, "pctCell") + "\n"


PCT_CASES = [({"p": 10, "c": 19.8, "lm": 1}, '<td class="num up">+10.00%<span class="sub2">漲停</span></td>'),
             ({"p": -9.73, "c": 153, "lm": -1}, '<td class="num dn">-9.73%<span class="sub2">跌停</span></td>'),
             ({"p": -9.9, "c": 92.8}, '<td class="num dn">-9.90%</td>'),
             ({"p": 0, "c": 10}, '<td class="num flat">0.00%</td>'),
             ({"p": None, "c": 10}, '<td class="num flat">--%</td>'),
             ({"nt": "2026-11-20", "c": 10, "lm": 1}, '<td class="flat small" title="最後成交 2026-11-20">無成交</td>'),
             ({"p": 9.95, "c": 10, "rel": "2026-11-20", "lm": 1},
              '<td class="num up rel" title="相對 11/20 收盤（前一交易日無成交）">+9.95%<span class="sub2">漲停</span></td>')]


def check_pct(app=APP):
    seg = _grab(app, "pctCell")
    assert seg.endswith("</td>`;") and "//" not in seg          # 最後一行以「;」結尾、不加行尾註解
    o = T._node(_pct_js(app) + "console.log(JSON.stringify(%s.map(pctCell)));" % json.dumps([c for c, _ in PCT_CASES], ensure_ascii=False))
    if o is None:
        return True
    assert o == [e for _, e in PCT_CASES], o
    return True


def test_pct():
    assert check_pct()
    assert "// 第 50 輪 F50-1（R73）：有成交且收在漲停價／跌停價" in APP[APP.index("// 表格的漲跌欄；"):APP.index("const pctCell")]
    assert "${sgn(s.p)}%${s.lm === 1 ? '<span class=\"sub2\">漲停</span>' : s.lm === -1 ? '<span class=\"sub2\">跌停</span>' : ''}</td>`" in PM


# ─── F50-1c 頁頭（驗收 10 的字面）、F50-1d 選股（驗收 11、12）、F50-1e 排行說明（驗收 13）─────
HEAD = ("            ${!noTrade && !gxLast && s?.lm ? `<span class=\"small ${s.lm > 0 ? 'up' : 'dn'}\" style=\"white-space:nowrap\" title=\"收盤等於本站依參考價推算的"
        "${s.lm > 0 ? '漲停價' : '跌停價'}\">${s.lm > 0 ? '收在漲停價' : '收在跌停價'}</span>` : ''}")
COND = ("  { id: 'lm', g: '價量', label: '今日收在{v}', opts: [[1, '漲停價'], [-1, '跌停價']], def: 1, f: (x, v) => x.lm === v, "
        "title: '收盤等於當天的漲停價或跌停價（本站依參考價 ±10% 與升降單位推算，和官方家數偶爾差 1 檔）；新上市前 5 個交易日沒有漲跌幅限制、今日無成交，都不列入' },"
        "   // 第 50 輪 F50-1（R73）")
NOTE = ("    (by === 'p+' || by === 'p-' ? '漲跌欄的「漲停」「跌停」= 收盤等於當天的漲停價、跌停價（本站依參考價 ±10% 與升降單位推算，"
        "和官方家數偶爾差 1 檔）；新上市前 5 個交易日沒有漲跌幅限制，不標。' : '') +")
DV_LINE = "    (by === 'dv' ? '近期除息 = 近 90 天內除息或除權息，依除息日由近到遠。' + DV_NOTE : '') +"


def test_head():
    assert HEAD in PM and STK.count(HEAD + "\n") == 1
    i = STK.index(HEAD)
    assert STK[:i].rstrip().endswith("(${sgn(pct)}%)</span>`}")                       # 接在漲跌之後
    assert STK[i + len(HEAD):].lstrip().startswith("${!noTrade && s?.rel ?")         # rel 小字之前


def _cond(app=APP):
    m = re.search(r"^  (\{ id: 'lm', .*\}),   // 第 50 輪 F50-1（R73）$", app, re.M)
    assert m
    return m.group(1)


def _node_cond(cond, rows, vs):
    return T._node("const c = %s, R = %s;\nconsole.log(JSON.stringify(%s.map(v => R.filter(x => c.f(x, v)).length)));"
                   % (cond, json.dumps(rows, ensure_ascii=False), json.dumps(vs)))


def check_cond(app=APP):
    assert COND + "\n" in app
    i, j, k = (app.index(s) for s in ("  { id: 'p', g: '價量'", "  { id: 'lm', g: '價量'", "  { id: 'r5', g: '價量'"))
    assert i < j < k and app[i:j].count("\n") == 1 and app[j:k].count("\n") == 1   # p 之後、r5 之前
    rows = [{"lm": 1}, {"lm": -1}, {"lm": -1}, {}, {"lm": None}, {"lm": "1"}]
    o = _node_cond(_cond(app), rows, [1, -1])
    assert o is None or o == [1, 2], o
    o = T._node("const c = %s;\nconsole.log(JSON.stringify([c.g, c.def, c.opts.map(o => c.label.replace('{v}', o[1]))]));" % _cond(app))
    assert o is None or o == ["價量", 1, ["今日收在漲停價", "今日收在跌停價"]], o          # 已選條件 chip 的字（cTxt）
    return True


def test_cond_note():
    assert check_cond()
    assert COND in PM and NOTE in PM
    assert DV_LINE + "\n" + NOTE + "\n" in APP and APP.count(NOTE) == 1             # :1016 原字不變，下一行新增
    assert "const SCREEN_GROUPS = ['流動性', '價量', '技術', '法人', '信用', '基本面', '排除'];" in APP


# ─── F50-12a holding_export、:1749（驗收 15、16）─────────────────────────
SUM0 = {"d": "2026-11-03", "nav": 2544.13, "nu": 24.87, "n": 51, "sw": 94.43, "fl": 679, "fa": 58.87}


def _sum(nu):
    return {T05.DATES[-1]: (Decimal("254413288263.00"), nu, 51, Decimal("94.43"), 679, Decimal("5887337400.00"))}


def check_holding(src=EXP):
    f = _pyload(src, "holding_export")
    h = lambda nu, **kw: f("00981A", T05.DATES, _sum(nu), T05.HELD, T05.TW, "主動統一台股增長", "TWSE", **kw)["sum"]
    assert h(Decimal("24.8700")) == SUM0 and h(Decimal("24.8700"), close=None) == SUM0     # 不傳 close：和改前逐字相同
    assert h(Decimal("20.7400"), close=Decimal("20.53")) == dict(SUM0, nu=20.74, pc=20.53, pm=-1.01)
    assert h(Decimal("8.4900"), close=Decimal("8.87"))["pm"] == 4.48
    assert h(Decimal("7.0200"), close=Decimal("7.02"))["pm"] == 0.0
    assert h(Decimal("12.0100"), close=12.2)["pm"] == 1.58
    for nu in (Decimal("0"), None):
        s = h(nu, close=Decimal("7.02"))
        assert "pc" not in s and "pm" not in s
    assert list(h(Decimal("20.7400"), close=Decimal("20.53")))[-2:] == ["pc", "pm"]      # 加在 sum 最後
    return True


def _close_expr(src):
    m = re.search(r"holding_export\(code, hdates, summary, held, tw, \*etf_names\[code\],\s*close=(.+?)\)\)   # 第 50 輪", src)
    assert m
    return m.group(1)


def check_close(src=EXP):
    d1, d2, d3 = (export.date(2026, 11, x) for x in (20, 21, 24))
    px = {"A": [(d1, Decimal("10.0")), (d2, None)], "B": [(d1, Decimal("10.0")), (d2, Decimal("10.5"))]}
    ev = lambda code, last: eval(_close_expr(src), {**vars(export), "etf_px": px, "code": code, "hdates": [d1, last]})
    assert ev("B", d2) == Decimal("10.5")                       # 持股日當天的收盤
    assert ev("A", d2) is None                                  # 當天收盤 None → None（不拿前一天補）
    assert ev("B", d3) is None                                  # 當天沒有列 → None
    assert ev("C", d2) is None                                  # 沒有這檔的價格
    return True


def test_holding():
    assert check_holding() and check_close()
    assert "last_close" not in _close_expr(EXP)


# ─── F50-12 實際資料（驗收 18）──────────────────────────────────
PM8 = {"00403A": -0.93, "00411A": 3.07, "00415A": 0.47, "00981A": -1.01, "00982A": -0.47, "00988A": 1.58, "00992A": -0.43, "00997A": 4.48}


def test_etf_data():
    if not IS_1125:
        print("  （資料日不是 2026-11-25，略過 8 檔折溢價核對）")
        return
    keys = {"d", "nav", "nu", "n", "sw", "fl", "fa", "u1"}
    got = {}
    for code in PM8:
        S = json.loads((DATA / "etfs" / f"{code}.json").read_text(encoding="utf-8"))["sum"]
        if "pm" not in S:
            print(f"  （{code} 還沒有 pm：PG 套用後 export 再核對）")
            return
        assert set(S) <= keys | {"pc", "pm"} and list(S)[-2:] == ["pc", "pm"]
        p = json.loads((DATA / "etfp" / f"{code}.json").read_text(encoding="utf-8"))["prices"]
        assert S["pc"] == p["c"][p["d"].index(S["d"])]                               # 持股日當天的收盤（不是資料日收盤）
        got[code] = S["pm"]
    assert got == PM8, got


# ─── F50-12b 持股頁（驗收 17）──────────────────────────────────
H0 = {"n": "測試", "m": "TWSE", "delay": 0, "trust": "統一", "dates": ["2026-11-24", "2026-11-25"], "rows": [], "out": [],
      "sum": {"d": "2026-11-25", "nav": 10, "nu": 20.74, "n": 1, "sw": 90, "fl": 0, "fa": 0}}
PM_NOTE = "折溢價 = 持股日收盤 ÷ 每單位淨值 − 1，正值為溢價、負值為折價；每單位淨值只有兩位小數，折溢價可能有約 0.1 個百分點的誤差。跨境 ETF 的淨值晚一個交易日公布，比的是同一個持股日的收盤。"


def _holdings(app, sums):
    js = (T.HELPERS + "\n" + _grab(app, "sgn") + "\n" + _grab(app, "HOLD_SORT") + "\n" + _grab(app, "renderHoldings") + "\n" +
          "Array.prototype.at = function (i) { return this[i < 0 ? this.length + i : i]; };\n"
          "const view = { innerHTML: '', addEventListener() {} }, $ = s => s === '#view' ? view : { addEventListener() {} };\n"
          "const document = { title: '' }, location = { replace() {} }, onRowClick = () => {}, localStore = (k, d) => d;\n"
          "const App = { latest: { date: '2026-11-25', holdings: { X: 1 }, etfs: { rows: {} } } };\n"
          "let H; const getJSON = async () => H;\n"
          "(async () => { const out = []; for (const s of %s) { H = Object.assign({}, %s, { sum: Object.assign({}, %s, s) }); "
          "await renderHoldings('X'); out.push(view.innerHTML); } console.log(JSON.stringify(out)); })();"
          % (json.dumps(sums), json.dumps(H0, ensure_ascii=False), json.dumps(H0["sum"])))
    return T._node(js)


def _card(html):
    i = html.index('<div class="l">每單位淨值</div>')
    return html[i:html.index('<div class="card stat">', i)]


def check_holdings_page(app=APP):
    o = _holdings(app, [{"pc": 20.53, "pm": -1.01}, {"d": "2026-11-24", "pc": 8.87, "nu": 8.49, "pm": 4.48},
                        {"d": "2026-11-20", "pc": 7.02, "nu": 7.02, "pm": 0}, {}])
    if o is None:
        return True
    subs = [re.findall(r'<div class="s">(.*?)</div>', _card(h)) for h in o]
    assert subs == [["11/25 收盤 20.53，折價 1.01%"], ["11/24 收盤 8.87，溢價 4.48%"], ["11/20 收盤 7.02，折溢價 0.00%"], []], subs
    assert all(PM_NOTE in h for h in o[:3]) and "折溢價 =" not in o[3]
    assert all(" up" not in _card(h) and " dn" not in _card(h) for h in o)           # 不上色
    assert all(h.count("標「新」= 前一持股日沒有持有。") == 1 for h in o)
    return True


def test_holdings_page():
    assert check_holdings_page()
    assert PM_NOTE in PM and "${S.pm == null ? '' : '" + PM_NOTE + "'}</div></section>`;" in APP
    assert ("['每單位淨值', fmt(S.nu, 2) + ' 元', S.pm == null ? '' : `${md(S.d)} 收盤 ${fmt(S.pc, 2)}，${S.pm > 0 ? '溢價' : S.pm < 0 ? '折價' : '折溢價'} "
            "${fmt(Math.abs(S.pm), 2)}%`]") in APP


# ─── 用詞、node 14（驗收 20、21）────────────────────────────────
def _new_segs(app=APP, stk=STK, exp=EXP):
    segs = []
    for src, anchors in ((app, ("${s.lm === 1 ?", "{ id: 'lm'", "(by === 'p+' || by === 'p-'", "S.pm == null ? '' : `", "${S.pm == null ? '' : '")),
                         (stk, ("${!noTrade && !gxLast && s?.lm ?",))):
        for a in anchors:
            i = src.index(a)
            segs.append(src[i:src.index("\n", i)])
    segs += [l for l in exp.splitlines() if "第 50 輪" in l or "本站推算" in l or "收在漲停" in l]
    segs.append(next(l for l in README.splitlines() if l.startswith("- 第 50 輪")))
    return "\n".join(segs)


def check_words(app=APP):
    seg = _new_segs(app)
    return all(w not in seg for w in ADVICE)


def test_words_node14():
    assert check_words()
    seg = _new_segs() + _grab(APP, "pctCell")
    for w in (".at(", "replaceAll", "||=", "&&=", "??="):
        assert w not in seg, w


# ─── ?v=、文件（驗收 24）────────────────────────────────────
def test_version_and_docs():
    for f in ("app.js", "stock.js", "app.css", "tools.js", "help.js", "compare.js"):
        v = hashlib.sha1((SITE / f).read_bytes()).hexdigest()[:8]
        assert f"{f}?v={v}" in HTML, f"index.html 要改成 {f}?v={v}"
    for s in ("app.css?v=ce1417aa", "tools.js?v=0a050889", "help.js?v=a5a5a7e8", "compare.js?v=1c11197d"):
        assert s in HTML, s
    assert "app.js?v=54952a23" not in HTML and "stock.js?v=28633954" not in HTML
    assert HTML.count("https://") == 2
    assert "python3 tests/test_iter50.py" in README
    r = next(l for l in README.splitlines() if l.startswith("- 第 50 輪"))
    for s in ("R73", "`lm`", "新上市前 5 個交易日", "今日收在 {漲停價／跌停價}", "`pc`", "`pm`", "D184"):
        assert s in r, s
    assert "第 23 輪" not in r
    assert any(l.startswith("- 第 50 輪（") for l in DOCS.splitlines())


# ─── 反證 ─────────────────────────────────────────────────────
def test_contrast():
    PCT = "${s.lm === 1 ? '<span class=\"sub2\">漲停</span>' : s.lm === -1 ? '<span class=\"sub2\">跌停</span>' : ''}</td>`;"
    bad = [
        (check_limit, _sub(EXP, "        x = ref * k\n", "        x = Decimal(str(float(ref) * float(k)))\n")),          # float 乘法（1.30 × 0.9）
        (check_limit, _sub(EXP, "if x < limit)\n        if c ==", "if ref < limit)\n        if c ==")),                  # 級距看參考價
        (check_limit, _sub(EXP, "(1, Decimal(\"1.1\"), ROUND_FLOOR), (-1, Decimal(\"0.9\"), ROUND_CEILING)",
                           "(1, Decimal(\"1.1\"), ROUND_CEILING), (-1, Decimal(\"0.9\"), ROUND_FLOOR)")),                     # 捨去／進位對調
        (check_limit, _sub(EXP, "(1, Decimal(\"1.1\"), ROUND_FLOOR)", "(1, Decimal(\"1.1\"), ROUND_HALF_UP)")),               # 漲停四捨五入
        (check_limit, _sub(EXP, "if close is None or change is None or new:", "if close is None or change is None:")),     # 新上市沒排除
        (check_limit, _sub(EXP, "    if ref <= 0:\n        return None\n", "")),                                            # 參考價 ≤ 0
        (check_snapshot, _sub(EXP, "d_[0] > db_first and len(d_) <= 5", "len(d_) <= 5")),                                   # 舊股也當新上市
        (check_snapshot, _sub(EXP, "lm := None if no_trade else limit_flag(", "lm := limit_flag(")),                        # 無成交也算
        (check_snapshot, _sub(EXP, '"--" if (official_breadth', '0 if (official_breadth')),                                  # 官方缺值寫 0
        (check_snapshot, _sub(EXP, '"--" if (official_breadth.get(m) or {}).get(k) is None else official_breadth[m][k]', '(official_breadth.get(m) or {}).get(k) or "--"')),   # 官方 0 也寫 --
        (check_pct, _sub(APP, PCT, "${LM_TXT[s.lm] || ''}</td>`;\nconst LM_TXT = { 1: '<span class=\"sub2\">漲停</span>', '-1': '<span class=\"sub2\">跌停</span>' };")),   # 引用新的頂層常數
        (check_pct, _sub(APP, '>無成交</td>`', '>無成交${s.lm ? \'<span class="sub2">漲停</span>\' : \'\'}</td>`')),          # 無成交也標
        (check_pct, _sub(APP, PCT, PCT[:-1] + "   // 第 50 輪")),                                                           # 行尾註解
        (check_cond, _sub(APP, "f: (x, v) => x.lm === v,", "f: (x, v) => x.lm == v,")),                                  # 字串 "1" 也算
        (check_cond, _sub(APP, "\n" + COND, "").replace("  { id: 'r20', g: '價量'", COND + "\n  { id: 'r20', g: '價量'", 1)),   # 位置錯（r5 之後）
        (check_holding, _sub(EXP, "if close is not None and nu and nu > 0 else {}", "if nu and nu > 0 else {}")),          # 不傳 close 也輸出
        (check_holding, _sub(EXP, "round((float(close) / float(nu) - 1) * 100, 2)", "round((float(nu) / float(close) - 1) * 100, 2)")),   # 倒過來除
        (check_close, _sub(EXP, "close=dict(etf_px.get(code, ())).get(hdates[-1])", "close=last_close(etf_px.get(code, []), hdates[-1])")),   # 用 last_close
        (check_holdings_page, _sub(APP, "S.pm > 0 ? '溢價' : S.pm < 0 ? '折價' : '折溢價'", "S.pm >= 0 ? '溢價' : '折價'")),    # 0 寫成溢價
        (check_holdings_page, _sub(APP, "${S.pm == null ? '' : '折溢價 =", "${'折溢價 =")),                                      # 沒有 pm 也寫說明
        (check_words, _sub(APP, "，不標。' : '') +", "，不標。" + sorted(ADVICE)[0] + "' : '') +")),                           # 用詞
    ]
    for i, (f, src) in enumerate(bad):
        assert src not in (EXP, APP), i
        assert not _ok(f, src), f"反證 {i} 沒有被擋下（{f.__name__}）"


if __name__ == "__main__":
    for k, v in list(globals().items()):
        if k.startswith("test_") and callable(v):
            v()
