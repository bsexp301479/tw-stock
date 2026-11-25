"""第 39 輪（不連網、不連資料庫）：除權息試算 #/tools/dv（F39-1）、?c= 帶入（F39-2）、股利卡「試算 →」（F39-3）。
有 node 時取出 app.js 的共用函式＋整個 tools.js 執行（node 14 可跑）；共用 test_iter34 的取函式與執行工具。
檢查函式都接受 src（tools.js 內容），test_contrast 把 tools.js 改壞後重跑，確認會失敗。"""
import hashlib
import json
import random
import re
import sys
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_iter34 as T  # noqa: E402

SITE, CSS, HTML, TOOLS, APP, STK = T.SITE, T.CSS, T.HTML, T.TOOLS, T.APP, T.STK
BAD = re.compile(r"NaN|Infinity|∞|undefined|(?<![\d.,])-0(?:\.0+)?(?![.,\d])")
ADVICE = ("買進", "賣出", "反彈", "見底", "買點", "超賣", "超買", "推薦", "強勢", "飆股", "勝率", "亮點", "建議", "低估", "高估", "超跌", "便宜",
          "保證", "穩賺", "安全", "危險", "划算", "填息機率", "貼息", "存股", "配息穩定", "穩定配息", "高息", "價值陷阱")
# 分析師 1-3 節的測試答案（本站官方參考價）：前收、現金、每千股配股、上市？、參考價。1110（15.95 − 0.3）用浮點 × 100 會得到 1564.99… → 15.64
ANS = [("2385", "7.000001", "0", True, "2,377.99"), ("34.8", "2.3", "0", True, "32.50"), ("2550", "46.084461", "0", False, "2,503.92"),
       ("15.95", "0.3", "0", True, "15.65"), ("24.35", "0.500021", "99.99999376", False, "21.68"), ("58", "0", "50.00000791", False, "55.24"), ("41.4", "0", "30.43406242", True, "40.18")]


def _run(expr, src=TOOLS):
    return T._node(T.HELPERS + "\nconst window = {};\nconst App = { latest: %s, stockCache: {} };\n" % json.dumps(T.LATEST, ensure_ascii=False)
                   + src + "\nconsole.log(JSON.stringify(%s));" % expr)


def _st(**kw):
    st = {"mk": "l", "k": "s", "p": "", "c": "", "s": "0", "n": "1000", "cost": "", "y1": ""}
    st.update({k: str(v) for k, v in kw.items()})
    return st


def _out(sts, src=TOOLS, I=None):
    return _run("[%s]" % ",".join("tlDvOut(%s, %s)" % (json.dumps(s, ensure_ascii=False), json.dumps(I, ensure_ascii=False)) for s in sts), src)


def _ref(html):
    return re.search(r'<th>除權息參考價</th><td class="num "><b class="tl-big">([\d,.]+)</b>', html).group(1)


def _row(html, th):
    m = re.search(r"<th>%s</th><td[^>]*>(.*?)</td></tr>" % re.escape(th), html)
    return m and m.group(1)


# ─── 參考價（驗收 1、2）──────────────────────────────────────
def check_answers(src=TOOLS):
    o = _out([_st(mk="l" if tw else "o", p=p, c=c, s=s) for p, c, s, tw, _ in ANS], src)
    if o is None:
        return []
    return [(a, _ref(h)) for a, h in zip(ANS, o) if _ref(h) != a[4]]


def test_answers():
    assert check_answers() == []


def _official_rows():
    """本站每一筆除權息（股票 ev.r、ETF dv.r）：[市場, 種類, 前收, 現金, 配股, 官方參考價]；k = sc、上市只有合計 a 的略過。"""
    lp = SITE / "data" / "latest.json"
    if not lp.exists():
        return None
    rows = []
    for d in ("stocks", "etfp"):
        for f in sorted((SITE / "data" / d).glob("*.json")):
            j = json.loads(f.read_text(encoding="utf-8"))
            ev = {(e["d"], e["t"]): e.get("r") for e in j.get("ev") or []}
            for x in j.get("dv") or []:
                r = x.get("r", ev.get((x["d"], x["t"])))
                if r is None or x.get("k") == "sc" or (x.get("c") is None and x.get("s") is None):
                    continue
                kind = "etf" if d == "etfp" else x["t"] == "息" and "息" or "權"
                rows.append([j["market"], kind, repr(x["p"]), repr(x.get("c") or 0), repr(x.get("s") or 0), r])
    return rows


def check_official(src=TOOLS, rows=None):
    rows = rows if rows is not None else _official_rows()
    if not rows:
        return []
    js = "%s.map(r => Number(tlExRef(tlBig(r[2], 2), tlBig(r[3], 6), tlBig(r[4], 8), r[0] === 'TWSE')))" % json.dumps(rows)
    o = _run(js, src)
    if o is None:
        return []
    return [(r, v) for r, v in zip(rows, o) if v != round(r[5] * 100)]


def test_official_all():
    rows = _official_rows()
    if rows is None:
        print("  （沒有 site/data，略過）")
        return
    n = {}
    for r in rows:
        n[(r[0], r[1])] = n.get((r[0], r[1]), 0) + 1
    assert n[("TWSE", "息")] > 500 and n[("TPEx", "息")] > 400 and n[("TPEx", "權")] > 30 and n[("TWSE", "etf")] + n[("TPEx", "etf")] > 800, n
    assert n.get(("TWSE", "權"), 0) >= 1, n                                                          # 8908：上市配股四捨五入
    bad = check_official(rows=rows)
    assert bad == [], bad[:5]
    print("  官方參考價全部相同：", sorted(n.items()))


# ─── 漲跌停、股數、健保、殖利率（驗收 3～6）─────────────────────
def test_limit_same_as_dt():
    cases = [(p, k) for p in ("9.99", "10", "49.95", "50", "99.9", "100", "499.5", "500", "999", "1000", "4995", "5000") for k in ("s", "e")]
    sts = [_st(p=p, c="0.01", k=k) for p, k in cases]
    o = _out(sts)
    if o is None:
        return
    for (p, k), h in zip(cases, o):
        r = _ref(h).replace(",", "")
        dt = _run("tlDtOut(%s, null, '2026-11-21')" % json.dumps({"mode": "g", "dir": "b", "k": k, "b": r, "s": "", "n": "1000", "ref": r, "d": "10", "m": "20"}))
        m = re.search(r"漲停 ([\d,.]+)、跌停 ([\d,.]+)（參考價", dt)
        assert _row(h, "下一交易日漲跌停") == f"漲停 {m.group(1)}、跌停 {m.group(2)}", (p, k)
        assert ("國外成分、槓反 ETF" in h) == (k == "e")


def _ref_frac(p, c, s, tw):
    v = (Fraction(p) - Fraction(c)) / (1 + Fraction(s) / 1000) * 100
    return (v.numerator // v.denominator) if tw and Fraction(s) == 0 else int(v + Fraction(1, 2))


def check_random(src=TOOLS, N=200):
    rnd, cases = random.Random(39), []
    for _ in range(N):
        p = f"{rnd.randint(100, 500000) / 100:.2f}"
        c = f"{rnd.randint(0, 2000000) / 1e6:.6f}" if rnd.random() < .8 else "0"
        s = f"{rnd.randint(0, 30000000000) / 1e8:.8f}" if rnd.random() < .4 or c == "0" else "0"
        if Fraction(c) == 0 and Fraction(s) == 0:
            s = "1.5"
        if Fraction(c) >= Fraction(p):
            c = "0.5"
        cases.append((p, c, s, rnd.random() < .5, str(rnd.choice([1, 999, 1000, 1500, 12345, 1000000, 37]))))
    o = _out([_st(mk="l" if tw else "o", p=p, c=c, s=s, n=n) for p, c, s, tw, n in cases], src)
    if o is None:
        return []
    bad = []
    for (p, c, s, tw, n), h in zip(cases, o):
        r = _ref_frac(p, c, s, tw)
        sh = int(n) * Fraction(s) / 1000
        cash = int(int(n) * Fraction(c))
        nhi = "未達 2 萬元，不扣" if cash < 20000 else f"{int(min(cash, 10 ** 7) * Fraction(211, 10000) + Fraction(1, 2)):,} 元（2.11%）"
        after = int((int(n) + sh) * Fraction(r, 100) + int(n) * Fraction(c) + Fraction(1, 2))
        want = [f"{r / 100:,.2f}", f"{cash:,} 元", nhi, f"{after:,} 元"]
        got = [_ref(h), _row(h, "可領現金股利"), _row(h, "二代健保補充保費"), _row(h, "除權息後市值＋現金股利")]
        if Fraction(s):
            w, fr = int(sh), sh - int(sh)
            want.append(f"{w:,} 股" + (f'<br><span class="small">另有不足 1 股 {_dec(fr)} 股</span>' if fr else ""))
            got.append(_row(h, "配發股數"))
        if want != got or BAD.search(h):
            bad.append((p, c, s, tw, n, want, got))
    return bad


def _dec(fr):
    """Fraction（分母整除 10^11）→ 去尾 0 的小數字串。"""
    v = fr * 10 ** 11
    assert v.denominator == 1
    return ("0." + str(v.numerator).rjust(11, "0")).rstrip("0")


def test_random_fraction():
    """驗收 4：200 組隨機輸入，參考價、可領現金、配股、健保、權益和 Fraction 獨立重算相同。"""
    bad = check_random()
    assert bad == [], bad[:3]


def check_shares_nhi(src=TOOLS):
    o = _out([_st(mk="o", p="24.35", c="0.500021", s="99.99999376"), _st(p="100", c="19.999"), _st(p="100", c="20"),
              _st(p="1000", c="10", n="1000000"), _st(p="1000", c="11", n="1000000"), _st(p="100", c="0", s="50")], src)
    if o is None:
        return []
    want = [("配發股數", '99 股<br><span class="small">另有不足 1 股 0.99999376 股</span>'), ("可領現金股利", "500 元"), ("除權後股數", "1,099 股")]
    bad = [(k, _row(o[0], k)) for k, v in want if _row(o[0], k) != v]
    for h, v in zip(o[1:5], ("未達 2 萬元，不扣", "422 元（2.11%）", "211,000 元（2.11%）", "211,000 元（2.11%）")):
        if _row(h, "二代健保補充保費") != v:
            bad.append((v, _row(h, "二代健保補充保費")))
    if _row(o[5], "二代健保補充保費") != "未達 2 萬元，不扣" or "本次現金股利" in o[5]:
        bad.append("純配股")
    for h in o:
        if not all(w in h for w in ("同一基準日的股票股利以面額一起計入，本頁只算現金股利", "單次以 1,000 萬元為上限", "不足 1 股依公司公告折付現金")):
            bad.append("說明")
    return bad


def test_shares_nhi():
    """驗收 4、5：1,000 股 × 每千股 99.99999376 股；健保 19,999 不扣、20,000 → 422、上限 1,000 萬。"""
    assert check_shares_nhi() == []


def test_cost_yield():
    o = _out([_st(p="50", c="2"), _st(p="50", c="2", cost="40"), _st(p="50", c="2", y1="3"), _st(p="50", c="2", cost="40", y1="3"), _st(p="50", c="2", cost="40", y1="0")])
    if o is None:
        return
    assert all("成本殖利率" not in h for h in o[:3])
    assert _row(o[3], "成本殖利率（近一年 ÷ 成本）") == "7.50%" and _row(o[4], "成本殖利率（近一年 ÷ 成本）") == "0.00%"
    assert _row(o[0], "本次現金股利 ÷ 前收") == "4.00%"


# ─── 驗證（驗收 7）──────────────────────────────────────────
def test_validation():
    bad = [(dict(p=""), "請輸入除權息前收盤"), (dict(p="0"), "請輸入除權息前收盤"), (dict(p="-5"), "請輸入除權息前收盤"), (dict(p="abc"), "請輸入除權息前收盤"),
           (dict(p="10.123"), "請輸入除權息前收盤"), (dict(c="-1"), "現金股利請填 0 以上"), (dict(c="1.1234567"), "現金股利請填 0 以上"),
           (dict(s="-1"), "每千股配股請填 0 以上"), (dict(n="0"), "持有股數請輸入正整數"), (dict(n="1.5"), "持有股數請輸入正整數"), (dict(n=""), "持有股數請輸入正整數"),
           (dict(cost="0"), "持有成本請填大於 0"), (dict(cost="abc"), "持有成本請填大於 0"), (dict(y1="-1"), "近一年現金股利請填 0 以上"),
           (dict(c="0", s="0"), "請輸入現金股利或配股"), (dict(c="", s=""), "請輸入現金股利或配股"), (dict(c="50"), "現金股利須小於除權息前收盤")]
    base = dict(p="50", c="2")
    o = _out([_st(**{**base, **kw}) for kw, _ in bad] + [_st(p="50", c="", s="100"), _st(p="1,000", c="1", n="1,000")])
    if o is None:
        return
    for (kw, m), h in zip(bad, o):
        assert m in h and "tl-kv" not in h and not BAD.search(h), (kw, h[:200])
    assert _ref(o[-2]) == "45.45" and _ref(o[-1]) == "999.00"                                     # 現金空白 = 0；千分位可輸入


# ─── 帶入（驗收 8、9）與路由（驗收 11）─────────────────────────
DAYS = ["2026-11-19", "2026-11-20"]
FIX = {
    "2330": {"name": "台積電", "market": "TWSE", "prices": {"d": DAYS, "c": [1450.0, 1460.0]}, "fund": {"dy": 1.5},
             "dv": [{"d": "2025-11-13", "t": "息", "c": 5.0, "p": 1450}, {"d": "2025-11-20", "t": "息", "c": 5.0, "p": 1450},   # QA D85：剛好 365 天前不計
                    {"d": "2025-12-11", "t": "息", "c": 5.0, "p": 1500},
                    {"d": "2026-03-12", "t": "息", "c": 5.000004, "p": 1800}, {"d": "2026-06-11", "t": "息", "c": 6.000035, "p": 2255.0},
                    {"d": "2026-09-16", "t": "息", "c": 7.000001, "p": 2385.0}],
             "ev": [{"d": "2026-09-16", "t": "息", "p": 2385.0, "r": 2377.99}]},
    "2063": {"name": "世鎧", "market": "TPEx", "prices": {"d": DAYS, "c": [22.0, 22.5]},
             "dv": [{"d": "2026-05-01", "t": "權", "k": "s", "c": 0.0, "s": 50.0, "p": 30.0},
                    {"d": "2026-10-28", "t": "權息", "k": "s", "c": 0.500021, "s": 99.99999376, "p": 24.35}],
             "ev": [{"d": "2026-10-28", "t": "權息", "p": 24.35, "r": 21.68, "k": "s"}, {"d": "2026-11-05", "t": "減", "p": 23.0, "r": 25.0}]},   # QA D85：之後的減資不是上次股利
    "5876": {"name": "上海商銀", "market": "TWSE", "prices": {"d": DAYS, "c": [46.0, 46.2]},
             "dv": [{"d": "2026-01-10", "t": "息", "c": 1.2, "p": 45}, {"d": "2026-07-28", "t": "權息", "k": "s", "a": 2.247525, "p": 47.0}],
             "ev": [{"d": "2026-07-28", "t": "權息", "k": "s", "p": 47.0, "r": 44.75}]},
    "2464": {"name": "盟立", "market": "TWSE", "prices": {"d": DAYS, "c": [180.0, 181.0]},
             "dv": [{"d": "2026-09-02", "t": "權息", "k": "sc", "a": 2.192145, "p": 184.5}]},
    "1213": {"name": "大飲", "market": "TWSE", "prices": {"d": DAYS, "c": [10.0, 10.1]}},
    "0056": {"name": "元大高股息", "market": "TWSE", "prices": {"d": DAYS, "c": [37.0, 37.2]},
             "dv": [{"d": "2026-07-21", "t": "息", "c": 1.35, "p": 49.95, "r": 48.6}, {"d": "2026-10-22", "t": "息", "c": 1.72, "p": 58.75, "r": 57.03}]},
    "006201": {"name": "元大富櫃50", "market": "TPEx", "prices": {"d": DAYS, "c": [30.0, 30.5]},
               "dv": [{"d": "2026-11-18", "t": "息", "c": 0.4, "p": 31.0, "r": 30.6}]},
}
LATEST39 = {"date": "2026-11-20", "stocks": {k: {"n": v["name"]} for k, v in FIX.items() if k not in ("0056", "006201")},
            "etfs": {"rows": {"0056": {"n": "元大高股息"}, "006201": {"n": "元大富櫃50"}}}}


def check_load(src=TOOLS):
    js = """
const view = { innerHTML: '' }, els = {};
const $ = s => s === '#view' ? view : (els[s] = els[s] || { innerHTML: '', classList: { add() {} }, addEventListener(t, f) { this[t] = f; } });
const history = { replaceState() {} }, localStore = (k, f) => f, FIX = %s;
const loadStock = async c => JSON.parse(JSON.stringify(FIX[c]));
(async () => {
  const r = {};
  for (const c of Object.keys(FIX)) { TL.dv.cost = '99'; await window.renderTools('dv?c=' + c); r[c] = { html: view.innerHTML, dv: Object.assign({}, TL.dv), dt: Object.assign({}, TL.dt), pl: Object.assign({}, TL.pl), y: TL.cp.y }; }
  console.log(JSON.stringify(r));
})();""" % json.dumps(FIX, ensure_ascii=False)
    o = T._node(T.HELPERS + "\nconst window = {};\nconst App = { latest: %s, stockCache: {} };\n" % json.dumps(LATEST39, ensure_ascii=False) + src + "\n" + js)
    if o is None:
        return []
    want = {   # 代號：帶入值、要出現的提示
        "2330": ({"mk": "l", "k": "s", "p": "1460", "c": "7.000001", "s": "0", "y1": "23.00004"},
                 ["已帶入 09/16 的股利（最近一次），下次請依公司公告修改", "上次官方參考價 2,377.99（09/16，前收 2,385）", "近一年現金股利 = 2025/11/20 以後 4 次合計"]),
        "2063": ({"mk": "o", "k": "s", "p": "22.5", "c": "0.500021", "s": "99.99999376", "y1": "0.500021"}, ["已帶入 10/28 的股利", "上次官方參考價 21.68（10/28，前收 24.35）", "近一年現金股利 = 2025/11/20 以後 1 次合計<"]),   # 純權不計
        "5876": ({"mk": "l", "c": "", "s": "0", "y1": "1.2"},
                 ["上市官方表只有 07/28 的權值＋息值合計 2.247525 元，請依公告填現金股利與配股", "上次官方參考價 44.75", "近一年現金股利 = 2025/11/20 以後 1 次合計；部分缺值，請自行確認"]),
        "2464": ({"mk": "l", "c": "", "s": "0", "y1": ""}, ["最近一次（09/02）含現金增資，參考價請看官方公告；現金股利、配股沒有帶入", "11/20 以後的現金股利官方表沒有分項，請自行確認"]),
        "1213": ({"mk": "l", "c": "", "s": "0", "y1": "", "p": "10.1"}, ["2026-11-19 起沒有除權息紀錄，請依公司公告填寫"]),
        "0056": ({"mk": "l", "k": "e", "c": "1.72", "s": "0", "y1": "3.07", "p": "37.2"}, ["已帶入 10/22 的股利", "上次官方參考價 57.03（10/22，前收 58.75）"]),
        "006201": ({"mk": "o", "k": "e", "c": "0.4", "y1": "0.4"}, ["上次官方參考價 30.6（11/18，前收 31）"]),
    }
    bad = []
    for c, (st, hs) in want.items():
        x = o[c]
        bad += [(c, k, x["dv"][k]) for k, v in st.items() if x["dv"][k] != v]
        bad += [(c, h) for h in hs if h not in x["html"]]
        if "<h2>除權息試算</h2>" not in x["html"] or '<button data-v="dv" class="on">除權息</button>' not in x["html"] or BAD.search(x["html"]):
            bad.append((c, "畫面"))
        if x["dv"]["cost"] != "" or x["dv"]["n"] != "1000":
            bad.append((c, "持有成本不帶入、換股票時清空"))                                          # D83-1 = A
        p = x["dv"]["p"]                                                                           # 其他分頁帶入不變
        if x["dt"]["b"] != p or x["dt"]["ref"] != p or x["pl"]["p1"] != p or x["dt"]["k"] != x["dv"]["k"]:
            bad.append((c, "其他分頁"))
    if o["2330"]["y"] != "1.5":
        bad.append("cp.y")
    return bad


def test_load():
    assert check_load() == []


def test_route():
    js = T._grab(APP, "esc") + "\n" + T._grab(APP, "scrollAt") + "\nlet scrollKey = null;\n" + T._grab(APP, "route") + r"""
let hash = '', seen = [];
const location = { get hash() { return hash; } };
const history = { state: null, replaceState(s, t, u) { this.state = s; if (u) hash = u; } };
const window = { scrollTo() {} };
const document = { title: '', querySelectorAll: () => [] }, $ = () => null, App = {};
const disposeFuturesChart = () => {}, renderToday = async () => {};
const routes = { tools: async arg => { seen.push([arg, hash]); } };
(async () => {
  for (const h of ['#/tools/dv', '#/tools/dv?c=2330', '#/tools/dvx', '#/tools/dv/x?c=0056'])
    { hash = h; history.state = null; await route(); }
  console.log(JSON.stringify(seen));
})();"""
    o = T._node(js)
    if o is None:
        return
    assert o == [["dv", "#/tools/dv"], ["dv?c=2330", "#/tools/dv?c=2330"], ["dt", "#/tools/dt"], ["dt?c=0056", "#/tools/dt?c=0056"]], o   # 不認得的照第 34 輪補成 dt（保留 ?c=）
    assert "onSeg('toolTabSeg', t => { history.replaceState(null, '', '#/tools/' + t + (TL.code ? '?c=' + TL.code : '')); tlDraw(t); });" in TOOLS   # 切分頁保留 ?c=


# ─── 卡片連結（驗收 10）、既有不變（驗收 12）──────────────────────
def test_card_link():
    assert hashlib.sha1(T._grab(STK, "divHTML").encode()).hexdigest()[:12] == "ce48816af767"                   # 卡片字面不變
    i = STK.index("const dvh = [...document.querySelectorAll('#view .sec-h h2')].filter(h => h.textContent === (E ? '配息與填息' : '股利與填息'))[0];")
    assert STK.index("ptab.insertAdjacentHTML('beforeend'") < i
    assert "if (dvh) dvh.insertAdjacentHTML('afterend', `<span class=\"sp\"></span><a class=\"small dv-go\" href=\"#/tools/dv?c=${code}\">試算 →</a>`);" in STK
    js = """
const h = { textContent: '%s', html: '', insertAdjacentHTML(p, s) { this.html += p + s; } }, other = { textContent: '季報', insertAdjacentHTML() { throw 1; } };
const document = { querySelectorAll: () => [other, h] }, code = '2330';
for (const E of [%s]) { %s }
console.log(JSON.stringify(h.html));"""
    lines = "\n".join(STK[i:].splitlines()[:2])
    for title, E in (("股利與填息", "false"), ("配息與填息", "true")):
        o = T._node(js % (title, E, lines))
        if o is None:
            return
        assert o == 'afterend<span class="sp"></span><a class="small dv-go" href="#/tools/dv?c=2330">試算 →</a>', o


LOCK = {"tlInfo": "360bb4f2bff7", "tlDtOut": "cc4e8edb6ce4", "tlCpOut": "c6db343e01c3", "tlPlOut": "33b2e3009b0c", "tlDtForm": "d267f7c32afa",
        "tlCpForm": "5826c3388754", "tlPlForm": "bfdf0335b02c", "tlLimit": "8e0b8894bb56", "tlDraw": "eb9b1465b1a1", "tlTrade": "a1601f39951f", "tlPledge": "08b656bbdbf8"}


def test_unchanged_and_wiring():
    for n, h in LOCK.items():
        assert hashlib.sha1(T._grab(TOOLS, n).encode()).hexdigest()[:12] == h, n                                 # 第 34、38 輪的函式一字不改
    for f in ("tools.js", "app.js", "stock.js", "app.css"):
        v = hashlib.sha1((SITE / f).read_bytes()).hexdigest()[:8]
        assert f'{f}?v={v}"' in HTML, f"site/index.html 的 {f}?v= 請改成 {v}"
    assert HTML.count("https://") == 2 and "http" not in TOOLS and "fetch(" not in TOOLS
    assert "@media (max-width:520px){.tl-odv .tl-kv,.tl-odv .tl-kv tbody{display:block}" in CSS and ".tl-odv .tl-kv td{flex:1 1 auto;white-space:nowrap}}" in CSS   # 驗收 13
    assert "if (tl && !['dt', 'ac', 'cp', 'pl', 'dv'].includes(tl[1]))" in APP
    seg = "".join(T._grab(TOOLS, n) for n in ("tlExRef", "tlBig", "tlDec", "tlDvOut", "tlDvForm", "tlDvLoad", "tlLoad"))
    for w in (".at(", "??", "?.", "||=", "&&=", "replaceAll", "structuredClone", "Object.hasOwn", "findLast", "Number.parseFloat(", "parseFloat("):
        assert w not in seg, w                                                                                   # node 14、不用浮點解析


def test_no_advice_words():
    seg = "".join(T._grab(TOOLS, n) for n in ("tlDvOut", "tlDvForm", "tlDvLoad")) + "".join(l for l in STK.splitlines() if "dv-go" in l or "第 39 輪" in l)
    o = _out([_st(p="50", c="2", cost="40", y1="3"), _st(p="50", c="0", s="100", k="e", mk="o")])
    seg += "".join(o or [])
    for w in ADVICE:
        assert w not in seg, w


# ─── 額外修正：個股搜尋框 Enter（使用者 11/21）─────────────────────
def check_search(app=APP):
    """沒用方向鍵或滑鼠選到候選、也不是完整代號時 Enter 不送出；注音選字中的 Enter 不送出；方向鍵可上下循環；點候選送出。"""
    js = T._grab(app, "esc") + "\n" + "\n".join(T._grab(app, n) for n in ("fmt", "pfmt", "sgn", "cls", "setupSearch")) + r"""
const mk = () => ({ hidden: true, value: '', innerHTML: '', ev: {}, addEventListener(t, f) { this.ev[t] = f; }, blur() {} });
const input = mk(), list = mk(), docEv = {};
const $ = s => s === '#q' ? input : list;
const document = { addEventListener(t, f) { docEv[t] = f; } };
const location = { hash: '#/today' };
const App = { watch: new Set(), latest: { stocks: { '2330': { n: '台積電', i: '半導體', c: 1460, p: 1, tv: 9 }, '2303': { n: '聯電', i: '半導體', c: 50, p: 0, tv: 5 } }, etfs: { rows: { '00981A': { n: '主動統一台股增長', c: 15, p: 0 } } } } };
setupSearch();
const r = [], key = (k, o = {}) => { let pd = false; input.ev.keydown(Object.assign({ key: k, preventDefault() { pd = true; } }, o)); return pd; };
const type = v => { input.value = v; input.ev.input(); };
type('23'); r.push(location.hash, (list.innerHTML.match(/class="on"/g) || []).length);   // 0：沒有預設選取
r.push(key('Enter'), location.hash);                                                     // Enter 不送出（但擋掉預設）
type('台'); key('ArrowDown'); key('Enter', { isComposing: true }); key('Enter', { keyCode: 229 }); r.push(location.hash);   // 已選到候選，但選字中的 Enter 不送出
type('23'); key('ArrowDown'); key('ArrowDown'); key('ArrowDown'); r.push((list.innerHTML.match(/<a href="#\/stock\/(\d+)" class="on"/) || [])[1]);   // 循環回第 1 筆
key('ArrowUp'); r.push((list.innerHTML.match(/<a href="#\/stock\/(\d+)" class="on"/) || [])[1]);
key('Enter'); r.push(location.hash, input.value);
type('23'); key('ArrowUp'); r.push((list.innerHTML.match(/<a href="#\/stock\/(\d+)" class="on"/) || [])[1]);   // 從未選取往上 = 最後一筆
type('zzz'); key('ArrowDown'); key('Enter'); r.push(location.hash);                       // 沒有候選
location.hash = '#/today'; type(' 2303 '); key('Enter'); r.push(location.hash);                // 完整代號＋Enter 直接進（前後空白不計）
location.hash = '#/today'; type('00981a'); key('Enter'); r.push(location.hash);               // 代號不分大小寫
location.hash = '#/today'; type('230'); key('Enter'); r.push(location.hash);                  // 只是代號開頭：不送出
location.hash = '#/today'; type('23');
list.ev.click({ target: { closest: s => s === 'a' ? { getAttribute: () => '#/stock/2303' } : null }, preventDefault() {}, stopPropagation() {} });
r.push(location.hash);
console.log(JSON.stringify(r));"""
    o = T._node(js)
    if o is None:
        return []
    want = ["#/today", 0, True, "#/today", "#/today", "2303", "2330", "#/stock/2330", "", "2330", "#/stock/2330",
            "#/stock/2303", "#/stock/00981A", "#/today", "#/stock/2303"]   # 候選順序 2303、2330
    return [] if o == want else [o]


def test_search_enter():
    assert check_search() == []


SEARCH_MUTANTS = [
    ("預設選第一筆", "    active = -1;                                                        // 第 39 輪", "    active = 0;                                                        // 第 39 輪"),
    ("選字中也送出", "    if (e.isComposing || e.keyCode === 229) return;", "    if (0) return;"),
    ("往上從未選取跳錯", "(active <= 0 ? n : active) - 1", "(active + n - 1) % n"),
    ("完整代號不送出", "hits[active] || hits.filter(([c]) => c.toLowerCase() === q)[0]", "hits[active]"),
    ("代號開頭也送出", "hits.filter(([c]) => c.toLowerCase() === q)[0]", "hits.filter(([c]) => c.toLowerCase().startsWith(q))[0]"),
]

# ─── 反證（驗收 17）：改壞後上面的檢查要失敗 ─────────────────────
MUTANTS = [
    ("參考價一律四捨五入", [("return tw && !S ? num / den :", "return false ? num / den :")], check_answers),
    ("參考價一律捨去", [("return tw && !S ? num / den :", "return true ? num / den :")], check_answers),
    ("改用浮點相減", [("  return tw && !S ? num / den : (2n * num + den) / (2n * den);",
                    "  const f = (Number(P) / 100 - Number(C) / 1e6) / (1 + Number(S) / 1e11) * 100; return BigInt(tw && !S ? Math.floor(f) : Math.round(f));")], check_answers),
    ("改用浮點相減（全量）", [("  return tw && !S ? num / den : (2n * num + den) / (2n * den);",
                    "  const f = (Number(P) / 100 - Number(C) / 1e6) / (1 + Number(S) / 1e11) * 100; return BigInt(tw && !S ? Math.floor(f) : Math.round(f));")], check_official),
    ("配股不除 1,000", [("den = (10n ** 11n + S) * 10000n", "den = (10n ** 8n + S) * 10000n")], check_answers),
    ("健保門檻改 > 20,000", [("cash >= 20000n ?", "cash > 20000n ?")], check_shares_nhi),
    ("健保沒有上限", [("(cash < 10000000n ? cash : 10000000n)", "cash")], check_shares_nhi),
    ("健保改捨去", [("* 211n + 5000n) / 10000n", "* 211n) / 10000n")], check_random),
    ("可領現金四捨五入", [("cash = n * C / 1000000n", "cash = (n * C + 500000n) / 1000000n")], check_random),
    ("上市權息合計當現金", [("else if (tw && x.c == null && x.a != null) h.push(", "else if (false) h.push("),
                        ("o.c = x.c != null ? String(x.c) : '0'", "o.c = String(x.c != null ? x.c : x.a || 0)")], check_load),
    ("近一年包含純權", [("(v.t === '息' || v.t === '權息')", "v.t")], check_load),
    ("沒寫最近一次", [("的股利（最近一次），", "的股利，")], check_load),
    ("帶入持有成本", [("Object.assign(TL.dv, o, { p: c, k: E ? 'e' : 's' });", "Object.assign(TL.dv, o, { p: c, cost: c, k: E ? 'e' : 's' });")], check_load),
    ("換股票沿用持有成本", [("y1: '', cost: '' }, h = [];", "y1: '' }, h = [];")], check_load),
    ("拿掉面額說明", [("同一基準日的股票股利以面額一起計入，本頁只算現金股利。", "本頁只算現金股利。")], check_shares_nhi),
]


def test_contrast():
    if T._node("console.log('1')") is None:
        return
    for name, reps, check in MUTANTS:
        src = TOOLS
        for a, b in reps:
            assert src.count(a) == 1, (name, a)
            src = src.replace(a, b)
        try:
            fails = check(src)
        except Exception as e:                                                                             # 改壞到執行失敗也算擋下
            fails = [repr(e)]
        assert fails, "反證沒有擋下：" + name
    for name, a, b in SEARCH_MUTANTS:
        assert APP.count(a) == 1, name
        assert check_search(APP.replace(a, b)), "反證沒有擋下：" + name


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_") and callable(f):
            print("==", n); f()
    print("全部通過")
