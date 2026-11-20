"""第 38 輪（不連網、不連資料庫）：工具頁文字簡化（F38-2）、零股提示（D72）、複利逐年成長圖（F38-3a）。
有 node 時取出 app.js 的共用函式＋整個 tools.js 執行（node 14 可跑）；共用 test_iter34 的取函式與執行工具。
檢查函式都接受 src（tools.js 內容），test_contrast 把 tools.js 改壞後重跑，確認會失敗。"""
import hashlib
import json
import re
import sys
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_iter34 as T  # noqa: E402

SITE, CSS, HTML, TOOLS, TODAY = T.SITE, T.CSS, T.HTML, T.TOOLS, "2026-11-21"
BAD = re.compile(r"NaN|Infinity|∞|undefined|(?<![\d.,])-0(?:\.0+)?(?![.,\d])")
ADVICE = ("買進", "賣出", "反彈", "見底", "買點", "超賣", "超買", "推薦", "強勢", "飆股", "勝率", "亮點", "建議", "低估", "高估", "超跌", "便宜",
          "保證", "穩賺", "斷頭價", "安全", "危險", "划算", "賣出擔保品", "連帶保證人", "融資買進", "獲利區", "預期報酬")   # test_iter34 詞表＋成長圖
DMSG = "手續費折扣請填大於 0、最多 10 的折數，小數最多 2 位（不打折為 10）"
ODD = "零股多數券商每筆最低 1 元，可在「最低手續費」改"


def _js(body, src=TOOLS):
    return (T.HELPERS + "\nconst window = {};\nconst App = { latest: %s, stockCache: {} };\n" % json.dumps(T.LATEST, ensure_ascii=False)
            + src + "\n" + body)


def _run(expr, src=TOOLS):
    return T._node(_js("console.log(JSON.stringify(%s));" % expr, src))


def _dt(I=None, **kw):
    st = {"mode": "dt", "dir": "b", "k": "s", "b": "", "s": "", "n": "1000", "ref": "", "d": "10", "m": "20"}
    st.update({k: str(v) for k, v in kw.items()})
    return "tlDtOut(%s, %s, '%s')" % (json.dumps(st, ensure_ascii=False), json.dumps(I), TODAY)


def _cp(**kw):
    st = {"P": "0", "M": "5000", "at": "end", "r": "6", "n": "10", "dv": "0", "y": ""}
    st.update({k: str(v) for k, v in kw.items()})
    return "tlCpOut(%s)" % json.dumps(st)


def _w(s):
    """顯示寬度（全形字 = 1，半形約 0.55）；標籤 ≤ 11 才能在 1024／375 一行放下（38/01 Q38-1）。"""
    return sum(1 if ord(c) > 0x2E7F else 0.55 for c in s)


def _num(s):
    return int(s.replace(",", "")) if re.fullmatch(r"\d{1,3}(,\d{3})*", s or "") else None


def _ok(fails):
    assert not fails, fails


# ─── F38-2：文字（驗收 1、5、6、10）─────────────────────────────
def check_dt_texts(src=TOOLS):
    I = {"code": "2330", "c": 2000, "d": "2026-11-20"}
    o = _run("[%s]" % ", ".join([
        "tlDtForm(Object.assign({}, TL.dt, { d: '10', m: '20', mode: 'dt', dir: 's' }))", "tlDtForm(Object.assign({}, TL.dt, { d: '', m: '20', mode: 'g' }))",
        _dt(I, b=2000, ref=2000),
        _dt(b=2000, ref=2100), _dt(dir="s", s=2000, b=1990, ref=2000), _dt(b="2000.5"), _dt(k="e", b=50, ref=50), _dt(mode="g", b=2000, d=6)]), src)
    if o is None:
        return []
    fr, fg, same, other, rev, off, etf, g6 = o
    f = []
    want = [(fr, "['g', '非當沖']" in src and "一般（非當沖）" not in fr, "T1"), (fr, "<span>手續費折扣（折）</span>" in fr, "T2"),
            (fg, 'data-k="d" inputmode="decimal" autocomplete="off" value="" placeholder="不打折 = 10"' in fg, "T2 placeholder"),
            (fr, "<span>最低手續費（元）</span>" in fr and "不打折為 10）</span>" not in fr, "T3"),
            (same, "下一交易日漲停 2,200、跌停 1,800（參考價 11/20 收盤 2,000，±10%）" in same, "T8 帶入"),
            (other, "漲停 2,310、跌停 1,890（參考價 2,100，±10%）" in other and "下一交易日" not in other and "試算）" not in other, "T8 自填"),
            (etf, "；國外成分、槓反 ETF 漲跌幅規定不同" in etf and "部分 ETF" not in etf, "T9"),
            (same, "升降單位：2,000 元價位每檔 5 元</div>" in same and "（股票）" not in same, "T10"),
            (off, "買價 2,000.5 不在升降單位上（每檔 5 元），無法算兩平" in off, "T11"),
            (rev, "<th>兩平買價上限（可成交）</th>" in rev and "買價不高於此價" not in rev and "先賣後買須當日收盤前買回。" in rev, "T12、T7"),
            (same, "當沖需符合券商資格；處置、全額交割股可能不能當沖。" in same and "現股當沖需符合" not in same, "T7"),
            (g6, "手續費：成交金額 × 0.1425% × 6 折（以退還後計），元以下捨去，每筆最低 20 元</div>" in g6 and "依券商）" not in g6, "T6"),
            (same, "× 10 折，元以下捨去" in same and "以退還後計" not in same, "T6 不打折不寫退還"),
            (g6, "<th>報酬率（÷ 買方金額）</th>" in _run(_dt(mode="g", b=2000, s=2100), src) and "<th>損益兩平價（可成交）</th>" in g6, "T13 不改")]
    f += [n for _, ok, n in want if not ok]
    if "2,000 檔內仍未打平" not in src or "現股當沖股數須為 1,000 的倍數（零股不能當沖）" not in src:
        f.append("T5、T14 不改")
    for x in re.findall(r"<span>([^<]+)</span><input", fr + fg):
        if _w(x) > 11:
            f.append("標籤過長 " + x)
    for x in re.findall(r"<th>([^<]+)</th>", "".join(o[2:])):
        if _w(x) > 11:
            f.append("結果表標題過長 " + x)
    return f


def test_dt_texts():
    _ok(check_dt_texts())


def check_discount(src=TOOLS):
    bad = ["0", "-1", "10.01", "1.685", "abc", "", "-0"]
    good = ["10", "0.01", "1.68", "2.8"]
    o = _run("[%s]" % ", ".join([_dt(b=2000, d=x) for x in bad + good] + [_dt(b=2000, m=x) for x in ("-1", "1.5", "0")]), src)
    if o is None:
        return []
    f = []
    for x, h in zip(bad, o):
        if DMSG not in h or "<table" in h or h.count("tl-msg") != 1:
            f.append("折扣 %r 應顯示訊息" % x)
    for x, h in zip(good, o[len(bad):]):
        if "<table" not in h or "手續費折扣請" in h:
            f.append("折扣 %r 應正常計算" % x)
    if "0～10 折" in src or "0～10 折" in "".join(o):
        f.append("訊息仍寫 0～10 折")
    full = _run(_dt(mode="g", b=2000, s=2000, d="2.8"), src)
    if full is not None and "<th>買方手續費</th><td class=\"num \">798</td>" not in full:
        f.append("2.8 折手續費應為 798")
    mm = o[len(bad) + len(good):]
    if not all("最低手續費請輸入 0 以上的整數" in h and "<table" not in h for h in mm[:2]) or "<table" not in mm[2]:
        f.append("最低手續費驗證")
    return f


def test_discount_validation():
    _ok(check_discount())
    form = _run("tlDtForm(TL.dt)")
    if form is None:
        return
    assert '<input data-k="d"' in form and '<input data-k="m"' in form and "<select" not in TOOLS            # 驗收 2：維持輸入框
    assert hashlib.sha1(T._grab(TOOLS, "tlFeePref").encode()).hexdigest()[:12] == "c48656094555"          # tlFeePref 一字不改
    assert "if (!(d > 0 && d <= 10)) msg.push(" in TOOLS                                                    # D76 = A：判斷式不變


def check_odd(src=TOOLS):
    cases = [(dict(mode="g", b=2000, n=500), True), (dict(mode="g", b=2000, n="1,500"), True), (dict(mode="g", b=2000, n=1000), False),
             (dict(mode="g", b=2000, n=2000), False), (dict(mode="g", b=2000, n=500, m=1), False), (dict(mode="g", b=2000, n=500, m=0), False),
             (dict(b=2000, n=500), False), (dict(b=2000, n=1000), False), (dict(mode="g", b=2000, n=0), False), (dict(mode="g", b=2000, n="abc"), False),
             (dict(mode="g", b=2000, n=500, d=0), True)]
    o = _run("[%s]" % ", ".join(_dt(**c) for c, _ in cases), src)
    if o is None:
        return []
    f = ["零股提示 %s" % c for (c, want), h in zip(cases, o) if (ODD in h) != want]
    if "每筆最低 20 元" not in o[0]:
        f.append("提示時最低手續費不應被改")
    return f


def test_odd_lot_hint():
    _ok(check_odd())
    assert TOOLS.count(ODD) == 1


def test_cp_pl_texts():
    I = {"dy": 1.1}
    o = _run("[%s]" % ", ".join([
        "tlCpForm(Object.assign({}, TL.cp, { dv: 're', y: '1.1' }), %s)" % json.dumps(I), _cp(), _cp(P="", M=""), _cp(P="-1"), _cp(r="abc"),
        T._plj({}), T._plj({"loan": "-5"}), T._plj({"p1": "", "x": ""})]))
    if o is None:
        return
    form, cp, empty, neg, rbad, pl, loan, plbad = o
    assert "['end', '期末投入'], ['begin', '期初投入']" in TOOLS and "每月期末投入" not in TOOLS and "每月期初投入" not in TOOLS   # C1
    assert "本站最新殖利率 1.10%</div>" in form and "（可改）" not in form                                         # C2
    assert all("初始金額、每月投入請填 0 以上，至少一項大於 0" in x and "<table" not in x for x in (empty, neg))   # C3
    assert "未計稅負、二代健保、內扣費用、手續費與通膨；結果依你填的假設計算，不代表本站預期。" in cp                 # C4
    assert "請輸入年報酬率（自行假設，-99～100%）" in rbad and "股利以每年年底市值 × 殖利率計算" in TOOLS            # 不改
    for s in ("證券商不限用途借貸：維持率低於 130% 須於 2 個營業日內補繳至 166%；未補繳且仍低於 130%，自第 3 營業日起處分擔保品（俗稱斷頭）。銀行、證券金融公司依各自契約。",
              "借滿 60% 時追繳價約為現價 −22%，借 40% 時約 −48%。</div>",
              "維持率 = 擔保品市值 ÷ 借款本金（不含利息），實際每日以收盤價整戶計算；本頁只算單檔，可把試算價格改低看變化；除權息後維持率也會下降。",
              "可借成數上限：得為融資融券的股票為前一營業日收盤價 × 60%，其餘 40%，券商可再調低；全額交割股不得為擔保品，處置股、槓反 ETF 請洽券商。",
              "<th>可借金額上限</th><td class=\"num \">1,260,000 元</td>", "÷365，四捨五入到元</span>"):
        assert s in pl, s                                                                                     # P1～P6
    assert "借得越多" not in pl and "試算價格可改低" not in pl and "以券商計算為準" not in pl and "核撥" not in pl
    assert "借款金額請輸入 0 以上的整數，或留空" in loan and "請輸入擔保價格" in plbad                              # P7（保留 test_iter34:270 的字串）
    assert "到期應還（本金＋利息）" in pl and "總成本（利息＋手續費）" in pl                                          # P8 不改
    assert not any(BAD.search(x) for x in o)


def test_disclaimers_kept():
    """驗收 5：免責、規則出處用語都還在畫面上。"""
    stock = {"name": "台積電", "prices": {"d": ["2026-11-20"], "c": [2000.0]}, "fund": {"dy": 1.1}}
    js = """
const view = { innerHTML: '' }, els = {};
const $ = s => s === '#view' ? view : (els[s] = els[s] || { innerHTML: '', classList: { add() {} }, addEventListener(t, f) { this[t] = f; } });
const history = { replaceState() {} }, localStore = (k, f) => f, loadStock = async () => (%s);
(async () => {
  const r = {};
  await window.renderTools('dt?c=2330'); r.dt = view.innerHTML;
  TL.dt.k = 'b'; TL.dt.mode = 'g'; await window.renderTools('dt?c=2330'); r.b = view.innerHTML;
  TL.cp.r = '6'; TL.cp.dv = 're'; await window.renderTools('cp?c=2330'); r.cp = view.innerHTML;
  await window.renderTools('pl?c=2330'); r.pl = view.innerHTML;
  console.log(JSON.stringify(r));
})();""" % json.dumps(stock, ensure_ascii=False)
    o = T._node(_js(js))
    if o is None:
        return
    foot = "試算僅供參考，不代表實際成交、扣款或核貸金額；費率、稅率、折扣與規則以券商與主管機關公告為準。"
    for k in ("dt", "b", "cp"):
        assert foot + "本站不提供投資建議。" in o[k], k
    assert foot + "成數、利率、計息與追繳門檻依各機構契約為準。本站不提供投資或借貸建議。" in o["pl"]
    assert "不代表本站預期" in o["cp"] and "僅供參考" in o["pl"]
    for s in ("130%", "166%", "2 個營業日", "第 3 營業日", "（俗稱斷頭）", "不含利息", "整戶", "本頁只算單檔", "前一營業日收盤價 × 60%", "40%", "全額交割股不得為擔保品"):
        assert s in o["pl"], s
    assert o["pl"].count("斷頭") == 1
    for s in ("0.1425%", "元以下捨去", "現股當沖 0.15%（至 2027/12/31）", "下一交易日", "升降單位"):
        assert s in o["dt"], s
    assert "債券 ETF 停徵（至 2026/12/31）" in o["b"]
    assert not any(BAD.search(x) for x in o.values())


def test_no_advice_words38():
    """驗收 10：新文字（含零股提示、圖例、CSS 註解）不含禁用詞；整個 tools.js 由 test_iter34 掃。"""
    seg = TOOLS.replace("投資或借貸建議", "").replace("投資建議", "") + "".join(l for l in CSS.splitlines() if "第 38 輪" in l)
    for w in ADVICE:
        assert w not in seg, w


# ─── D74：手機結果表換行（驗收 8）────────────────────────────────
NEW_CSS = ("@media (max-width:520px){:is(.tl-odt,.tl-ocp) .tl-kv,:is(.tl-odt,.tl-ocp) .tl-kv tbody{display:block}:is(.tl-odt,.tl-ocp) .tl-kv tr{display:flex;"
           "flex-wrap:wrap;justify-content:space-between;column-gap:12px;border-bottom:1px solid var(--border)}:is(.tl-odt,.tl-ocp) .tl-kv th,"
           ":is(.tl-odt,.tl-ocp) .tl-kv td{border-bottom:0}:is(.tl-odt,.tl-ocp) .tl-kv td{flex:1 1 auto;white-space:nowrap}}")
GR_CSS = (".tl-gr{display:block;width:100%;height:160px;margin:12px 0 6px}.tl-lg i{height:0;border-radius:0;border-top:2px solid var(--blue)}"
          ".tl-lg i.d{border-top:2px dashed var(--text2)}.tl-lg i.v{border-top:2px dotted var(--violet)}")


def test_css():
    assert NEW_CSS in CSS and GR_CSS in CSS
    assert "@media (max-width:520px){.tl-opl .tl-kv,.tl-opl .tl-kv tbody{display:block}" in CSS                        # .tl-opl 那行不動
    new = "".join(l for l in CSS.splitlines() if "第 38 輪" in l)
    assert new.count("第 38 輪") == 2 and "background" not in new and not re.search(r"fill:(?!none)", new)        # 驗收 13
    assert "--up" not in new and "--dn" not in new


# ─── F38-3a：複利成長圖（驗收 11～17）────────────────────────────
def _ref(P, M, r, n, y, re_, begin=False):
    """與 tlCompound 同規則的 Fraction 獨立實作（test_iter34 test_qa_compound_monthly_dividend）。回傳第 1～n 年 [累計投入, 期末, 已領]。"""
    a, m, paid, out = Fraction(P), Fraction(0), Fraction(0), []
    for k in range(1, n + 1):
        a *= 1 + Fraction(r) / 100
        for _ in range(12):
            m = (m + M) * (1 + Fraction(r) / 1200) if begin else m * (1 + Fraction(r) / 1200) + M
        dv = (a + m) * Fraction(y) / 100
        if re_:
            a += dv
        else:
            paid += dv
        out.append((Fraction(P) + Fraction(M) * 12 * k, a + m, paid))
    return out


def _parse(h):
    svg = h[h.index("<svg"):h.index("</svg>")]
    lines = [[tuple(map(float, p.split(","))) for p in pts.split()] for pts in re.findall(r'<polyline points="([^"]*)"', svg)]
    styles = re.findall(r'<polyline [^>]*stroke="var\(--(\w+)\)"', svg)
    lg = re.findall(r'<span class="lg"><i class="(\w*)"></i>([^<]+) <b>([^<]+)</b> 元</span>', h)
    ax = re.search(r"第 0～(\d+) 年；縱軸 0～([\d,]+) 元，每格 ([\d,]+) 元", h)
    cells = dict(re.findall(r"<tr><th>([^<]+)</th><td class=\"num [^\"]*\">([^<]+) 元</td></tr>", h[:h.index("<svg")]))
    return svg, dict(zip(styles, lines)), lg, ax, cells


GRAPH = [dict(), dict(r=6, n=20), dict(P=100000, M=0, r=0, dv="out", y=5), dict(P=100000, M=5000, r=6, dv="re", y=3),
         dict(P=100000, M=5000, r=6, dv="out", y=3), dict(M=5000, r=6, n=20, at="begin", dv="re", y=4), dict(P=1, M=0, r=-99, n=50),
         dict(P=0, M=1, r=100, n=50, dv="re", y=100), dict(P=1000000, M=0, r=0, n=1), dict(P=0, M=5000, r=0, n=5, dv="out", y=0),
         dict(P="0.5", M="49.95", r="-1", n=3)]


def check_graph(src=TOOLS):
    o = _run("[%s]" % ", ".join(_cp(**c) for c in GRAPH), src)
    if o is None:
        return []
    f = []
    for c, h in zip(GRAPH, o):
        st = dict(P="0", M="5000", r="6", n="10", dv="0", y="", at="end")
        st.update({k: str(v) for k, v in c.items()})
        P, M, r, n, dv, y = Fraction(st["P"]), Fraction(st["M"]), Fraction(st["r"]), int(st["n"]), st["dv"], Fraction(st["y"] or 0)
        R = _ref(P, M, r, n, y if dv != "0" else 0, dv == "re", st["at"] == "begin")
        A = _ref(P, M, r, n, y, dv != "re", st["at"] == "begin") if dv != "0" else None
        svg, L, lg, ax, cells = _parse(h)
        if BAD.search(h) or "nan" in svg.lower():
            f.append(("NaN／Infinity", c)); continue
        if not ax or int(ax.group(1)) != n:
            f.append(("座標說明", c)); continue
        top, step = int(ax.group(2).replace(",", "")), int(ax.group(3).replace(",", ""))
        main = [P] + [x[1] + (x[2] if dv == "out" else 0) for x in R]
        inv = [P] + [x[0] for x in R]
        want = {"blue": main, "text2": inv}
        if A:
            want["violet"] = [P] + [x[1] + (x[2] if dv == "re" else 0) for x in A]
        if set(L) != set(want):
            f.append(("線數", c, sorted(L))); continue
        if not (top >= max(max(v) for v in want.values()) and top % step == 0 and 1 <= top // step <= 4):
            f.append(("縱軸", c, top, step))
        if not re.fullmatch(r"[125]0*", str(step)):
            f.append(("格線間距", c, step))
        for k, v in want.items():                                                                         # 每一點反推回金額，誤差 ≤ 座標 0.01
            pts = L[k]
            if len(pts) != n + 1 or any(abs(px - i / n * 100) > 0.006 for i, (px, _) in enumerate(pts)):
                f.append(("橫座標", k, c)); continue
            if any(abs(Fraction(py) - (2 + (1 - Fraction(val) / top) * 96)) > Fraction(6, 1000) for (_, py), val in zip(pts, v)):
                f.append(("縱座標", k, c))
            if any(not 0 <= q <= 100 for p in pts for q in p):
                f.append(("超出範圍", k, c))
        fin = {i: b for i, _, b in lg}
        if dv == "out":                                                                                   # 期末金額＋已領股利 = 表格兩格相加
            okm = _num(fin.get("")) == _num(cells["期末金額"]) + _num(cells["已領股利"])
        else:
            okm = fin.get("") == cells["期末金額"]
        if not okm or fin.get("d") != cells["投入本金合計"]:
            f.append(("圖例與摘要表", c, fin, cells))
        if A:
            av = A[-1][1] if dv == "out" else round(A[-1][1]) + round(A[-1][2])
            if _num(fin.get("v")) is None or abs(_num(fin["v"]) - av) > max(1, av / 10 ** 12):   # 浮點：相對誤差 1e-12
                f.append(("對照線第 n 年", c, fin["v"], float(av)))
        names = [x[1] for x in lg]
        wantn = {"0": ["期末金額", "累計投入"], "re": ["期末金額", "累計投入", "對照：股利領出（期末金額＋已領股利）"],
                 "out": ["期末金額＋已領股利", "累計投入", "對照：股利再投入"]}[dv]
        if names != wantn:
            f.append(("圖例名稱", c, names))
        if h.index("</svg>") > h.index("不代表本站預期") or h.index("</svg>") > h.index('id="tlYr"'):
            f.append(("位置：摘要表之下、說明與逐年表之上", c))
    return f


def test_graph_numbers():
    _ok(check_graph())


def test_graph_invalid_and_extremes():
    """驗收 16：驗證不通過時沒有圖；極端值沒有 NaN／Infinity（座標都在 0～100）。"""
    bad = [dict(n=51), dict(n=0), dict(r=-100), dict(r=101), dict(P=0, M=0), dict(r=""), dict(dv="re", y=""), dict(dv="re", y=101)]
    o = _run("[%s]" % ", ".join(_cp(**c) for c in bad))
    if o is None:
        return
    assert all("<svg" not in h and "<table" not in h for h in o)
    ext = [dict(r=-99, n=50, P=1e11, M=0), dict(r=100, n=50, P="999999999999", M="999999999999", dv="re", y=100), dict(r=0, P=0, M="0.000000001", n=1),
           dict(r=100, n=50, dv="out", y=100), dict(r=-99, n=1, M=1), dict(r=0, n=50, dv="re", y=0)]
    o = _run("[%s]" % ", ".join(_cp(**c) for c in ext))
    for c, h in zip(ext, o):
        assert "<svg" in h and not BAD.search(h), c
        nums = [float(x) for x in re.findall(r'(?:points|y1|y2)="([^"]+)"', h) for x in re.split(r"[ ,]", x)]
        assert nums and all(0 <= x <= 100 for x in nums), c


def check_no_fill(src=TOOLS):
    f = []
    g = T._grab(src, "tlCpGraph")
    if re.search(r"<polygon|<path|<rect|gradient|fill-opacity|style=", g + "".join(T._grab(src, "tlCpOut").split("tlCompound"))):
        f.append("圖有面積元素或行內樣式")
    if any(x != "none" for x in re.findall(r'fill="([^"]*)"', src)):
        f.append("fill 不是 none")
    if "<polyline" in g and g.count("fill=\"none\"") != g.count("<polyline"):
        f.append("polyline 缺 fill=none")
    if "--up" in src or "--dn" in src or 'aria-hidden="true"' not in g or 'preserveAspectRatio="none"' not in g:
        f.append("顏色或屬性")
    if re.search(r"<text|<tspan", src):
        f.append("SVG 內有文字")
    return f


def test_graph_no_fill():
    _ok(check_no_fill())
    o = _run(_cp(dv="re", y=3))
    if o is None:
        return
    svg = o[o.index("<svg"):o.index("</svg>")]
    assert set(re.findall(r'stroke="var\(--([\w-]+)\)"', svg)) == {"border", "border2", "blue", "text2", "violet"}   # 顏色都用 CSS 變數（深淺色不用重畫）
    assert not re.search(r"#[0-9a-fA-F]{3,6}|rgb", svg)


def _lum(h):
    c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def test_graph_contrast():
    """驗收 14：淺色、深色的線與卡片底 ≥ 3:1，圖例文字（--text2）≥ 4.5:1。"""
    light = dict(re.findall(r"--([\w-]+):(#[0-9a-f]{6})", CSS[CSS.index(":root{"):CSS.index("}", CSS.index(":root{"))]))
    d0 = CSS.index(':root[data-theme="dark"]{')
    dark = dict(re.findall(r"--([\w-]+):(#[0-9a-f]{6})", CSS[d0:CSS.index("}", d0)]))
    for t in (light, dark):
        ratio = lambda a, b: (max(_lum(t[a]), _lum(t[b])) + 0.05) / (min(_lum(t[a]), _lum(t[b])) + 0.05)
        assert all(ratio(k, "card") >= 3 for k in ("blue", "text2", "violet")), t
        assert ratio("text2", "card") >= 4.5 and ratio("text", "card") >= 4.5


# ─── 共通（驗收 17～21）─────────────────────────────────────────
def test_unchanged_and_wiring():
    assert hashlib.sha1(T._grab(TOOLS, "tlCompound").encode()).hexdigest()[:12] == "ab8bc2344348"         # 驗收 17：tlCompound 不改
    assert TOOLS.count("tlCompound(") == 3                                                                 # 定義＋摘要＋對照線
    assert '<button class="chip tl-all" id="tlAll">顯示每一年</button>' in TOOLS
    for f, n in (("tools.js", "tools"), ("app.css", "app")):
        v = hashlib.sha1((SITE / f).read_bytes()).hexdigest()[:8]
        assert f'{f}?v={v}"' in HTML, f"site/index.html 的 {f}?v= 請改成 {v}"
    assert HTML.count("https://") == 2 and "http" not in TOOLS and "fetch(" not in TOOLS
    for w in (".at(", "??", "?.", "||=", "&&=", "replaceAll", "structuredClone", "Object.hasOwn", "findLast"):
        assert w not in T._grab(TOOLS, "tlCpGraph") + T._grab(TOOLS, "tlCpOut") + T._grab(TOOLS, "tlDtOut"), w   # node 14


# ─── 反證（驗收 20）：改壞 tools.js 後，上面的檢查要失敗 ─────────────
MUTANTS = [
    ("折扣訊息改回 0～10 折", DMSG, "手續費折扣請輸入 0～10 折（不打折為 10）", check_discount),
    ("T12 改回 18 字", "tlRow(rev ? '兩平買價上限（可成交）' : '損益兩平價（可成交）',", "tlRow(`損益兩平價（可成交${rev ? '，買價不高於此價' : ''}）`,", check_dt_texts),
    ("圖加 fill", '" fill="none" ${G[j][4]}', '" fill="var(--blue)" fill-opacity=".1" ${G[j][4]}', check_no_fill),
    ("圖改用 polygon", "s += `<polyline points=", "s += `<polygon points=", check_no_fill),
    ("圖例最終值格式不同", "fmt(o ? Math.round(x[2]) + Math.round(x[3]) : x[2])", "fmt(o ? x[2] + x[3] : x[2], 2)", check_graph),
    ("領出模式圖例改用期末金額", "fin = (x, o) => fmt(o ? Math.round(x[2]) + Math.round(x[3]) : x[2])", "fin = (x, o) => fmt(x[2])", check_graph),
    ("對照線少畫", "  if (A) G.push(", "  if (0) G.push(", check_graph),
    ("第 0 年不從初始金額起", "[P].concat(R.map(x => x[1]))", "R.map(x => x[1])", check_graph),
    ("零股提示在整股出現", "!dt && n > 0 && n % 1000 && m === TL_RULES.minFee", "!dt && n > 0 && m === TL_RULES.minFee", check_odd),
    ("零股提示在當沖出現", "!dt && n > 0 && n % 1000 && m === TL_RULES.minFee", "n > 0 && n % 1000 && m === TL_RULES.minFee", check_odd),
    ("T8 改回舊句", "out.push(`${rd ? '下一交易日' : ''}漲停", "out.push(`參考價 ${pfmt(ref / 100)}：漲停", check_dt_texts),
]


def test_contrast():
    if T._node("console.log('1')") is None:
        return
    for name, a, b, check in MUTANTS:
        assert TOOLS.count(a) == 1, name
        try:
            fails = check(TOOLS.replace(a, b))
        except Exception as e:                                                                             # 改壞到執行失敗也算擋下
            fails = [repr(e)]
        assert fails, "反證沒有擋下：" + name


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_") and callable(f):
            print("==", n); f()
    print("全部通過")
