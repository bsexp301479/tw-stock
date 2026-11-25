"""第 41 輪（不連網、不連資料庫）：工具頁「平均成本」#/tools/ac（F41-1）、?c= 帶入目前價格（F41-2）。
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

SITE, CSS, HTML, TOOLS, APP = T.SITE, T.CSS, T.HTML, T.TOOLS, T.APP
TODAY = "2026-11-21"
BAD = re.compile(r"NaN|Infinity|∞|undefined|(?<![\d.,])-0(?:\.0+)?(?![.,\d])")
ADVICE = ("買進", "賣出", "反彈", "見底", "買點", "超賣", "超買", "推薦", "強勢", "飆股", "勝率", "亮點", "建議", "低估", "高估", "超跌", "便宜",
          "保證", "穩賺", "斷頭價", "安全", "危險", "划算", "賣出擔保品", "連帶保證人", "融資買進", "獲利區", "預期報酬",
          "攤平", "加碼", "解套", "回本", "套牢", "停損", "停利", "目標價", "獲利了結")


def _js(body, src=TOOLS, latest=None):
    return (T.HELPERS + "\nconst window = {};\nconst App = { latest: %s, stockCache: {} };\n" % json.dumps(latest or T.LATEST, ensure_ascii=False)
            + src + "\n" + body)


def _run(expr, src=TOOLS):
    return T._node(_js("console.log(JSON.stringify(%s));" % expr, src))


def _st(k="s", rows=(), d="10", m="20", mo="1", cur="", r=None):
    st = {"k": k, "r": str(r or max(3, len(rows))), "d": d, "m": m, "mo": mo, "cur": cur}
    for i, (p, n) in enumerate(rows):
        st["p%d" % i], st["n%d" % i] = p, n
    return st


def _out(sts, src=TOOLS, I=None, today=TODAY):
    return _run("[%s]" % ",".join("tlAcOut(%s, %s, '%s')" % (json.dumps(s, ensure_ascii=False), json.dumps(I, ensure_ascii=False), today) for s in sts), src)


def _row(html, th):
    m = re.search(r"<th>%s</th><td[^>]*>(.*?)</td></tr>" % re.escape(th), html)
    return m and m.group(1)


def _detail(html):
    return re.findall(r'<tr><td>(\d+)</td><td class="num">([^<]+)</td><td class="num">([^<]+)</td><td class="num">([^<]+)</td></tr>', html)


# ─── 手算範例（驗收 1、3、8）────────────────────────────────────
SM = '<br><span class="small">%s</span>'
EX = [  # (狀態, {標題: 內容}, 明細手續費)
    (_st("s", [("52.3", "1000"), ("49.85", "300"), ("47.1", "50")], d="6", cur="53.4"),
     {"總股數": "1,350 股" + SM % "整股 1 張＋零股 350 股", "成交金額合計": "69,610 元", "買入手續費合計": "58 元", "總成本（含手續費）": "69,668 元",
      "平均成交價": "51.56" + SM % "不含手續費", "平均成本（含手續費）": '<b class="tl-big">51.61</b>', "損益兩平賣價（理論）": "51.81",
      "損益兩平賣價（可成交）": '<b class="tl-big">51.9</b>' + SM % "平均成本進位到 51.7，再上漲 2 檔", "以此價出售淨損益": "+129 元",
      "目前價格": "53.4", "出售金額": "72,090 元", "出售手續費": "60 元" + SM % "整股 45＋零股 15", "證交稅": "216 元" + SM % "整股 160＋零股 56",
      "未實現損益": "+2,146 元", "報酬率（÷ 總成本）": "+3.08%"}, ["44", "12", "2"]),
    (_st("e", [("70.15", "100"), ("68.5", "200"), ("66.95", "100")], d="2.8", cur="71.2"),
     {"總股數": "400 股" + SM % "零股 400 股", "買入手續費合計": "9 元", "總成本（含手續費）": "27,419 元", "平均成交價": "68.53" + SM % "不含手續費",
      "平均成本（含手續費）": '<b class="tl-big">68.55</b>', "損益兩平賣價（理論）": "68.64",
      "損益兩平賣價（可成交）": '<b class="tl-big">68.65</b>' + SM % "平均成本進位到 68.55，再上漲 2 檔", "以此價出售淨損益": "+4 元",
      "出售金額": "28,480 元", "出售手續費": "11 元", "證交稅": "28 元", "未實現損益": "+1,022 元", "報酬率（÷ 總成本）": "+3.73%"}, ["2", "5", "2"]),
    (_st("s", [("9.87", "1500"), ("10.5", "20")], cur="9.5"),
     {"總股數": "1,520 股" + SM % "整股 1 張＋零股 520 股", "成交金額合計": "15,015 元", "買入手續費合計": "28 元", "總成本（含手續費）": "15,043 元",
      "平均成交價": "9.88" + SM % "不含手續費", "平均成本（含手續費）": '<b class="tl-big">9.90</b>', "損益兩平賣價（理論）": "9.94",
      "損益兩平賣價（可成交）": '<b class="tl-big">9.95</b>' + SM % "平均成本進位到 9.90，再上漲 5 檔", "以此價出售淨損益": "+10 元",
      "出售手續費": "27 元" + SM % "整股 20＋零股 7", "證交稅": "42 元" + SM % "整股 28＋零股 14", "未實現損益": "-672 元", "報酬率（÷ 總成本）": "-4.47%"},
     ["20＋7", "1"]),
    (_st("s", [("9.87", "1500"), ("10.5", "20")], cur="9.5", mo="20"),   # 3'：零股最低 20（D92 對照）
     {"買入手續費合計": "60 元", "總成本（含手續費）": "15,075 元", "平均成本（含手續費）": '<b class="tl-big">9.92</b>', "未實現損益": "-717 元",
      "報酬率（÷ 總成本）": "-4.76%"}, ["20＋20", "20"]),
    (_st("s", [("100.5", "2000"), ("98", "1000")], cur="99"),
     {"總股數": "3,000 股" + SM % "整股 3 張", "買入手續費合計": "425 元", "總成本（含手續費）": "299,425 元", "平均成交價": "99.67" + SM % "不含手續費",
      "平均成本（含手續費）": '<b class="tl-big">99.81</b>', "損益兩平賣價（理論）": "100.25",
      "損益兩平賣價（可成交）": '<b class="tl-big">100.5</b>' + SM % "平均成本進位到 99.9，再上漲 2 檔", "以此價出售淨損益": "+742 元",
      "出售手續費": "423 元", "證交稅": "891 元", "未實現損益": "-3,739 元", "報酬率（÷ 總成本）": "-1.25%"}, ["286", "139"]),
    (_st("b", [("40", "100")], d="0.01", m="0", mo="0"),
     {"買入手續費合計": "0 元", "平均成本（含手續費）": '<b class="tl-big">40.00</b>', "損益兩平賣價（理論）": "40.00",
      "損益兩平賣價（可成交）": '<b class="tl-big">40.00</b>' + SM % "平均成本進位到 40.00 即打平", "以此價出售淨損益": "0 元"}, ["0"]),
]


def check_examples(src=TOOLS):
    o = _out([s for s, _, _ in EX], src)
    if o is None:
        return []
    bad = []
    for (s, want, fee), h in zip(EX, o):
        bad += [(k, v, _row(h, k)) for k, v in want.items() if _row(h, k) != v]
        if [x[3] for x in _detail(h)] != fee or BAD.search(h):
            bad.append(("明細", fee, _detail(h)))
    if any(_row(o[5], k) for k in ("目前價格", "出售金額", "出售手續費", "證交稅", "未實現損益", "報酬率（÷ 總成本）")):
        bad.append("範例 5 沒有目前價格，不應有第 10～15 行")                                  # 驗收 7
    if [x[:3] for x in _detail(o[0])] != [("1", "52.3", "1,000"), ("2", "49.85", "300"), ("3", "47.1", "50")]:
        bad.append("明細欄位")
    return bad


def test_examples():
    assert check_examples() == []


def test_split():
    """驗收 3：1,500 股拆兩份各自套最低；2,000 股只有整股；500 股只有零股，不收整股最低值。"""
    o = _out([_st(rows=[("10", "1500")], m="20", mo="1"), _st(rows=[("10", "2000")], m="20", mo="1"), _st(rows=[("10", "500")], m="20", mo="1"),
              _st(rows=[("10", "500")], m="20", mo="1", cur="10")])
    if o is None:
        return
    assert [x[3] for x in _detail(o[0])] == ["20＋7"] and [x[3] for x in _detail(o[1])] == ["28"] and [x[3] for x in _detail(o[2])] == ["7"]
    assert _row(o[3], "出售手續費") == "7 元" and _row(o[3], "證交稅") == "15 元"                     # 只有零股：沒有整股＋零股小字


def check_far(src=TOOLS):
    """驗收 4（QA D102 = A）：上漲 400 檔才打平；2,000 檔內打不平時只顯示訊息、沒有淨損益行。"""
    o = _out([_st(rows=[("10", "1")], m="20", mo="20"), _st(rows=[("0.01", "1")], m="1000000", mo="1000000")], src)
    return [] if o is None or (_row(o[0], "損益兩平賣價（可成交）") == '<b class="tl-big">50.0</b>' + SM % "平均成本進位到 30.00，再上漲 400 檔"
                               and _row(o[1], "損益兩平賣價（可成交）") == "2,000 檔內仍未打平" and _row(o[1], "以此價出售淨損益") is None) else ["2,000 檔"]


def test_far():
    assert check_far() == []


# ─── Fraction 參考實作（驗收 2、4）──────────────────────────────
def _tick(p, e):
    for lim, t in (((5000, 1),) if e else ((1000, 1), (5000, 5), (10000, 10), (50000, 50), (100000, 100))):
        if p < lim:
            return t
    return 5 if e else 500


def _fee(a, dz, mn):
    return max(mn, a * 1425 * dz // 10 ** 11)


def _lots(q, m, mo):
    return [(k, mn) for k, mn in ((q - q % 1000, m), (q % 1000, mo)) if k > 0]


def _sell(p, N, dz, m, mo, r):
    f = [_fee(p * k, dz, mn) for k, mn in _lots(N, m, mo)]
    x = [p * k * r // 10 ** 6 for k, _ in _lots(N, m, mo)]
    return p * N - (sum(f) + sum(x)) * 100, f, x


def _half(X, N):
    return int(Fraction(X, N) + Fraction(1, 2))


def _px(p, e):
    t = _tick(p, e)
    d = 2 if t < 10 else 1 if t < 100 else 0
    return f"{Fraction(p, 100):,.{d}f}" if d else f"{p // 100:,}"


def _yen(c):
    s = f"{abs(c) // 100:,}" + (f".{abs(c) % 100:02d}" if c % 100 else "")
    return ("+" if c > 0 else "-" if c < 0 else "") + s + " 元"


def _ref(st):
    rows = [(round(Fraction(st["p%d" % i]) * 100), int(st["n%d" % i])) for i in range(int(st["r"])) if st.get("p%d" % i)]
    dz, m, mo, e = round(Fraction(st["d"]) * 100), int(st["m"]), int(st["mo"]), st["k"] != "s"
    r = {"s": 30, "e": 10, "b": 0}[st["k"]]
    A, N = sum(p * q for p, q in rows), sum(q for _, q in rows)
    F = sum(_fee(p * k, dz, mn) for p, q in rows for k, mn in _lots(q, m, mo))
    Tc = A + F * 100
    c = -(-Tc // N)
    p0 = c if c % _tick(c, e) == 0 else c + _tick(c, e) - c % _tick(c, e)
    p = c                                                                          # 暴力解：從平均成本下方 50 檔起逐檔往上
    for _ in range(50):
        p = max(1, p - _tick(p - 1, e))
    p += -p % _tick(p, e)                                                          # 對齊到升降單位
    while _sell(p, N, dz, m, mo, r)[0] - Tc < 0:
        p += _tick(p, e)
    k, q = 0, p0
    while q < p:
        q += _tick(q, e); k += 1
    want = {"買入手續費合計": f"{F:,} 元", "平均成交價": f"{_half(A, N) / 100:,.2f}" + SM % "不含手續費",
            "平均成本（含手續費）": f'<b class="tl-big">{_half(Tc, N) / 100:,.2f}</b>',
            "損益兩平賣價（可成交）": f'<b class="tl-big">{_px(p, e)}</b>' + SM % (f"平均成本進位到 {_px(p0, e)}" + (f"，再上漲 {k} 檔" if k else " 即打平")),
            "以此價出售淨損益": _yen(_sell(p, N, dz, m, mo, r)[0] - Tc)}
    th = Fraction(Tc, N) / (1 - Fraction(1425 * dz, 10 ** 9) - Fraction(r, 10 ** 4)) / 100
    if st["cur"]:
        cu = round(Fraction(st["cur"]) * 100)
        U = _sell(cu, N, dz, m, mo, r)[0] - Tc
        want.update({"未實現損益": _yen(U), "出售金額": f"{cu * N / 100:,.{2 if cu * N % 100 else 0}f} 元"})
        return want, th, Fraction(U * 100, Tc)
    return want, th, None


def _rand_st(rnd):
    k = rnd.choice("seb")
    n = rnd.randint(1, 10)
    rows = []
    for _ in range(n):
        q = rnd.choice([rnd.randint(1, 999), rnd.randint(1, 30) * 1000, rnd.randint(1001, 30000)])
        rows.append((f"{rnd.randint(100, 300000) / 100:.2f}".rstrip("0").rstrip("."), str(q)))
    cur = rnd.choice(["", f"{rnd.randint(100, 300000) / 100:.2f}"])
    return _st(k, rows, d=rnd.choice(["10", "6", "2.8", "0.01", "7.77", "1.68"]), m=rnd.choice(["20", "0", "1", "50"]), mo=rnd.choice(["1", "0", "20"]), cur=cur, r=n)


def check_random(src=TOOLS, N=200):
    rnd = random.Random(41)
    sts = [_rand_st(rnd) for _ in range(N)]
    o = _out(sts, src)
    if o is None:
        return []
    bad = []
    for st, h in zip(sts, o):
        want, th, ret = _ref(st)
        got = {k: _row(h, k) for k in want}
        tv = _row(h, "損益兩平賣價（理論）")
        if got != want or abs(Fraction(tv.replace(",", "")) - th) > Fraction(51, 10000) or BAD.search(h):
            bad.append((st, want, got, tv, float(th)))
        if ret is not None and abs(Fraction(_row(h, "報酬率（÷ 總成本）")[:-1].replace(",", "")) - ret) > Fraction(51, 10000):
            bad.append((st, "報酬率"))
    return bad


def test_random_fraction():
    """驗收 2、4：200 組隨機（整股、零股、混合，不同折扣、最低值、商品別）和 Fraction 參考實作、暴力兩平解相同。"""
    bad = check_random()
    assert bad == [], bad[:2]


def check_half(src=TOOLS):
    """驗收 2：平均剛好在 0.005 上要進位。1.01 × 500＋1 × 500 → 1.005：浮點 (1005 ÷ 1000).toFixed(2) 是 1.00，整數四捨五入是 1.01。"""
    o = _out([_st("e", [("1.01", "500"), ("1", "500")], d="0.01", m="0", mo="0"), _st("e", [("70.15", "100"), ("68.5", "200"), ("66.95", "100")], d="2.8")], src)
    if o is None:
        return []
    got = [_row(o[0], "平均成交價"), _row(o[0], "平均成本（含手續費）"), _row(o[1], "平均成交價")]
    want = ["1.01" + SM % "不含手續費", '<b class="tl-big">1.01</b>', "68.53" + SM % "不含手續費"]
    return [] if got == want else [got]


def test_half():
    assert check_half() == []
    o = T._node("console.log(JSON.stringify([(1005 / 1000).toFixed(2), (27410 / 400).toFixed(2)]));")
    assert o is None or o == ["1.00", "68.53"], o                                                  # 68.525 在 node 剛好不出錯，1.005 會
    o = _out([_st("e", [("68.525", "1")])])
    assert o is None or "第 1 筆價格請填大於 0 的數字，小數最多 2 位" in o[0]                         # 價格最多 2 位小數


# ─── 驗證（驗收 5、6、7）─────────────────────────────────────────
VAL = [(dict(rows=[]), "請至少填一筆價格與股數"), (dict(rows=[("10", "1"), ("10", "")]), "第 2 筆請填股數"),
       (dict(rows=[("10", "1"), ("", "5")]), "第 2 筆請填價格")] + \
      [(dict(rows=[(p, "1")]), "第 1 筆價格請填大於 0 的數字，小數最多 2 位") for p in ("0", "-1", "1.234", "abc")] + \
      [(dict(rows=[("10", n)]), "第 1 筆股數請填正整數") for n in ("0", "1.5", "-3", "abc")] + \
      [(dict(rows=[("10", "1")], d=d), "手續費折扣請填大於 0、最多 10 的折數（不打折為 10），小數最多 2 位") for d in ("0", "10.01", "abc")] + \
      [(dict(rows=[("10", "1")], m=m), "整股最低手續費請輸入 0 以上的整數") for m in ("-1", "1.5")] + \
      [(dict(rows=[("10", "1")], mo="-1"), "零股最低手續費請輸入 0 以上的整數")] + \
      [(dict(rows=[("10", "1")], cur=c), "目前價格請填大於 0 的數字（小數最多 2 位），或留空") for c in ("abc", "0", "1.234")]


def test_validation():
    o = _out([_st(**kw) for kw, _ in VAL] + [_st(rows=[("abc", "0")]), _st(rows=[("10", "1"), ("", ""), ("20", "1,000")]), _st(rows=[("10", "1")], d="")])
    if o is None:
        return
    for (kw, m), h in zip(VAL, o):
        assert m in h and "tl-kv" not in h and "<table" not in h and not BAD.search(h), (kw, h[:300])
        assert "本頁以全部持股一次出售計算" in h                                                   # 訊息時說明照常顯示
    assert "第 1 筆價格請填" in o[len(VAL)] and "第 1 筆股數請填正整數" in o[len(VAL)]                    # 同一列兩則都出
    assert [x[0] for x in _detail(o[len(VAL) + 1])] == ["1", "3"] and _row(o[len(VAL) + 1], "總股數").startswith("1,001 股")   # 驗收 6：中間空白列
    assert "× -- 折" in o[-1]                                                                     # 不合法顯示 --


# ─── 證交稅與說明（驗收 13、14）────────────────────────────────
def test_tax_and_notes():
    sts = [_st(k, [("100", "1000")], cur="100") for k in "seb"]
    o = _out(sts, today="2026-11-21") + _out([sts[2]], today="2027-01-01") + _out([_st("s", [("100", "1000")], d="6")], I={"ex": "2026-12-03"})
    if o is None:
        return
    assert [_row(h, "證交稅") for h in o[:3]] == ["300 元", "100 元", "0 元"]
    assert "停徵期限已過，請確認最新稅率" in o[3] and "停徵期限已過" not in o[2]
    for s in ("手續費：成交金額 × 0.1425% × 6 折（以退還後計），元以下捨去；整股每筆最低 20 元、零股每筆最低 1 元（各券商不同，零股多數 1 元、部分 20 元）。股數不是 1,000 的倍數時，拆成整股與零股兩筆計算。",
              "平均成本含買入手續費，不含出售成本；兩平賣價與未實現損益已扣出售手續費與證交稅。",
              "本頁以全部持股一次出售計算，不含部分出售、當沖與融資；除權息後的現金股利與配股不調整成本，可到「除權息」分頁試算。",
              "各券商手續費計算方式不同（逐筆或合併計算），請以對帳單為準；交易成本分頁以一筆計算，和本頁拆成整股與零股的結果可能差幾元。",
              "12/03 除權息，參考價另計", "證交稅：股票 0.3%"):
        assert s in o[4], s
    assert "以退還後計" not in o[0] and "除權息，參考價另計" not in o[0]
    assert all(not BAD.search(h) for h in o)


# ─── 畫面流程：增刪列、折扣初值、帶入（驗收 9、10、11）─────────────
HARNESS = """
const view = { innerHTML: '' }, els = {}, saved = [];
const $ = s => s === '#view' ? view : (els[s] = els[s] || { innerHTML: '', classList: { add() {} }, addEventListener(t, f) { this[t] = f; } });
const history = { replaceState() {} }, localStore = (k, f, v) => { if (v !== undefined) saved.push([k, v]); return f; }, FIX = %s;
const loadStock = async c => JSON.parse(JSON.stringify(FIX[c]));
const clk = (g, v) => els['#tlForm'].click({ target: { closest: () => ({ dataset: { v: String(v) }, closest: () => ({ dataset: { g } }) }) } });
const inp = (k, v) => els['#tlForm'].input({ target: { dataset: { k }, value: v } });
const ac = () => Object.assign({}, TL.ac), n = s => (view.innerHTML.match(new RegExp(s, 'g')) || []).length;
(async () => {
  const r = {};
%s
  console.log(JSON.stringify(r));
})();"""


def _flow(body, src=TOOLS, fix=None, latest=None):
    return T._node(_js(HARNESS % (json.dumps(fix or {}, ensure_ascii=False), body), src, latest))


def check_rows(src=TOOLS):
    o = _flow("""
  await window.renderTools('ac'); r.a = [n('data-k="p'), n('>刪除</button>'), n('data-v="4">＋ 新增一筆'), n('aria-label="第 3 筆股數"')];
  for (let i = 4; i <= 10; i++) clk('r', i);
  r.b = [TL.ac.r, n('data-k="p'), n('＋ 新增一筆')];
  for (const v of ['11', '0', 'abc']) { TL.ac.r = v; await window.renderTools('ac'); r['r' + v] = [TL.ac.r, n('data-k="n')]; }
  inp('p0', '10'); inp('n0', '1000'); inp('p1', '20'); inp('n1', '2000'); inp('p2', '30'); inp('n2', '3000');
  clk('x', 0); r.c = [ac(), view.innerHTML];
  clk('r', 3); r.d = ac();
  clk('x', 5); r.e = ac();
  clk('x', 2); clk('x', 0); r.f = [ac(), n('>刪除</button>'), view.innerHTML];
  clk('x', 0); r.g = ac();
""", src)
    if o is None:
        return []
    bad = []
    if o["a"] != [3, 3, 1, 1] or o["b"] != ["10", 10, 0] or [o["r11"], o["r0"], o["rabc"]] != [["10", 10], ["3", 3], ["3", 3]]:
        bad.append(("列數", o["a"], o["b"], o["r11"], o["r0"], o["rabc"]))
    c, h = o["c"]
    if [c.get(k) for k in ("p0", "n0", "p1", "n1", "p2", "n2", "r")] != ["20", "2000", "30", "3000", "", "", "2"] or "x" in c:
        bad.append(("刪除第 1 列", c))
    if [x[:3] for x in _detail(h)] != [("1", "20", "2,000"), ("2", "30", "3,000")] or not _row(h, "總股數").startswith("5,000 股"):
        bad.append("刪除後結果區用移動後的資料")                                                      # tlDraw 先表單、後結果
    if [o["d"].get(k) for k in ("r", "p2", "n2")] != ["3", "", ""]:
        bad.append(("新增的列不是空白", o["d"]))
    if o["e"]["r"] != "3" or "x" in o["e"] or o["e"]["p1"] != "30":
        bad.append(("超出範圍的刪除", o["e"]))
    f, nd, _ = o["f"]
    if f["r"] != "1" or f["p0"] != "30" or nd != 0:
        bad.append(("只剩 1 列", f, nd))
    if o["g"]["r"] != "1" or o["g"]["p0"] != "30":
        bad.append(("1 列時刪除", o["g"]))
    return bad


def test_rows():
    assert check_rows() == []


def test_fee_init_not_saved():
    """驗收 10（D97 = A）：第一次顯示時取交易成本頁的值；本頁修改不存、不改交易成本頁。"""
    o = _flow("""
  TL.dt.d = '6'; TL.dt.m = '30'; await window.renderTools('ac'); r.a = view.innerHTML;
  inp('d', '5'); inp('m', '1'); r.dt = [TL.dt.d, TL.dt.m, TL.ac.d, TL.ac.m];
  await window.renderTools('dt'); r.b = view.innerHTML; await window.renderTools('ac'); r.c = view.innerHTML; r.saved = saved;
""")
    if o is None:
        return
    assert 'data-k="d" inputmode="decimal" autocomplete="off" value="6"' in o["a"] and 'data-k="m" inputmode="decimal" autocomplete="off" value="30"' in o["a"]
    assert 'data-k="mo" inputmode="decimal" autocomplete="off" value="1"' in o["a"] and 'placeholder="選填"' in o["a"]
    assert o["dt"] == ["6", "30", "5", "1"] and o["saved"] == []
    assert 'data-k="d" inputmode="decimal" autocomplete="off" value="6"' in o["b"] and 'data-k="d" inputmode="decimal" autocomplete="off" value="5"' in o["c"]
    for s in ("<h2>平均成本（多筆合計）</h2>", '<div class="tl-form tl-ac" id="tlForm">', '<section class="sec card tl-out tl-oac" id="tlOut">',
              "<span>手續費折扣（折）</span>", "<span>整股最低手續費（元）</span>", "<span>零股最低手續費（元）</span>", "<span>目前價格（元）</span>",
              '<span>價格（元）</span><span>股數</span>', 'inputmode="numeric"', 'aria-label="刪除第 1 筆"', "本站不提供投資建議。", "以券商與主管機關公告為準"):
        assert s in o["a"], s
    assert re.search(r'<div class="seg" id="toolTabSeg"><button data-v="dt" class="">交易成本</button><button data-v="ac" class="on">平均成本</button>'
                     r'<button data-v="cp" class="">複利</button><button data-v="pl" class="">股票質借</button><button data-v="dv" class="">除權息</button></div>', o["a"])


DAYS = ["2026-11-19", "2026-11-20"]
FIX = {"2330": {"name": "台積電", "market": "TWSE", "prices": {"d": DAYS, "c": [1450.0, 1460.0]}, "nx": [{"d": "2026-12-11", "t": "息", "c": 6}]},
       "0056": {"name": "元大高股息", "market": "TWSE", "prices": {"d": DAYS, "c": [37.0, 37.2]}}}
LATEST41 = {"date": "2026-11-20", "stocks": {"2330": {"n": "台積電"}}, "etfs": {"rows": {"0056": {"n": "元大高股息"}}}}


def check_load(src=TOOLS):
    o = _flow("""
  await window.renderTools('ac?c=2330'); r.a = ac(); inp('p0', '1400'); inp('n0', '1000'); r.out = els['#tlOut'].innerHTML;
  inp('cur', '1465'); r.out2 = els['#tlOut'].innerHTML;
  await window.renderTools('dt?c=2330'); r.dt = [TL.dt.b, TL.dt.k, TL.pl.p1, TL.dv.p]; await window.renderTools('ac?c=2330'); r.b = ac();
  clk('r', 4); await window.renderTools('ac?c=0056'); r.c = ac();
  inp('p0', '30'); await window.renderTools('ac'); r.d = ac();
  inp('p0', '30'); inp('cur', '31'); await window.renderTools('ac?c=9999'); r.e = ac(); r.miss = view.innerHTML;
""", src, FIX, LATEST41)
    if o is None:
        return []
    bad = []
    if (o["a"]["cur"], o["a"]["k"]) != ("1460", "s") or o["dt"] != ["1460", "s", "1460", "1460"]:
        bad.append(("帶入", o["a"], o["dt"]))
    if _row(o["out"], "目前價格") != "1,460" + SM % "11/20 收盤，不是即時價" or "12/11 除權息，參考價另計" not in o["out"]:
        bad.append(("收盤小字", _row(o["out"], "目前價格")))
    if _row(o["out2"], "目前價格") != "1,465":
        bad.append("改了目前價格後小字要消失")
    if (o["b"]["p0"], o["b"]["n0"], o["b"]["cur"]) != ("1400", "1000", "1465"):
        bad.append(("同代號切分頁要保留", o["b"]))
    for k, cur, kk in (("c", "37.2", "e"), ("d", "", None), ("e", "", None)):
        x = o[k]
        if any(x.get("p%d" % i, "") or x.get("n%d" % i, "") for i in range(10)) or x["r"] != "3" or x["cur"] != cur or (kk and x["k"] != kk):
            bad.append(("換代號清空", k, x))
    if "找不到 9999 的資料" not in o["miss"]:
        bad.append("找不到")
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
  for (const h of ['#/tools/ac', '#/tools/ac?c=2330', '#/tools/acx', '#/tools/dv'])
    { hash = h; history.state = null; await route(); }
  console.log(JSON.stringify(seen));
})();"""
    o = T._node(js)
    if o is None:
        return
    assert o == [["ac", "#/tools/ac"], ["ac?c=2330", "#/tools/ac?c=2330"], ["dt", "#/tools/dt"], ["dv", "#/tools/dv"]], o
    assert "  if (tl && !['dt', 'ac', 'cp', 'pl', 'dv'].includes(tl[1])) history.replaceState(history.state, '', '#/tools/dt' + (tl[2] || ''));" in APP
    assert "const TL_TABS = [['dt', '交易成本'], ['ac', '平均成本'], ['cp', '複利'], ['pl', '股票質借'], ['dv', '除權息']];" in TOOLS


# ─── 既有不變、接線、用詞（驗收 15～21）────────────────────────────
OLD = ("tlFee", "tlTax", "tlTick", "tlNext", "tlPx", "tlNum", "tlC", "tlY", "tlRow", "tlMsg", "tlNote", "tlIn", "tlSeg", "tlTaxTxt", "tlBreak",
       "tlDvOut", "tlDvForm", "tlDvLoad", "tlNx", "tlExRef", "tlBig", "tlCpGraph", "TL_FOOT")
NEW = ("tlLot", "tlAvg", "tlSell", "tlAcBreak", "tlAcN", "tlAcV", "tlAcOut", "tlAcForm")


def test_unchanged_and_wiring():
    assert hashlib.sha1("".join(T._grab(TOOLS, n) for n in OLD).encode()).hexdigest()[:12] == "81d223f49f68"   # 只呼叫、不修改
    for f in ("tools.js", "app.js", "stock.js", "app.css"):
        v = hashlib.sha1((SITE / f).read_bytes()).hexdigest()[:8]
        assert f'{f}?v={v}"' in HTML, f"site/index.html 的 {f}?v= 請改成 {v}"
    assert HTML.count("https://") == 2
    for s in ("@media (max-width:520px){.tl-opl .tl-kv,.tl-opl .tl-kv tbody{display:block}", "@media (max-width:520px){:is(.tl-odt,.tl-ocp) .tl-kv,",
              "@media (max-width:520px){.tl-odv .tl-kv,.tl-odv .tl-kv tbody{display:block}",
              ".tl-f.tl-rows{grid-column:1/-1;display:grid;grid-template-columns:auto minmax(0,1fr) minmax(0,1fr) auto;gap:6px 8px;align-items:center}",
              "@media (max-width:520px){.tl-oac .tl-kv,.tl-oac .tl-kv tbody{display:block}", ".tl-oac .tl-kv td{flex:1 1 auto;white-space:nowrap}.tl-oac .tl-kv td .small{white-space:normal}}",
              "@media (max-width:520px){#toolTabSeg{flex-wrap:wrap;border-radius:18px}}"):
        assert s in CSS, s
    new = "".join(l for l in CSS.splitlines() if "第 41 輪" in l)
    assert new.count("第 41 輪") == 3 and "第 38 輪" not in new and "第 39 輪" not in new
    seg = "".join(T._grab(TOOLS, n) for n in NEW + ("tlLoad",))
    for w in (".at(", "??", "?.", "||=", "&&=", "replaceAll", "structuredClone", "Object.hasOwn", "findLast", "parseFloat(", "toFixed("):
        assert w not in seg, w                                                                     # 驗收 20：node 14、不用浮點解析與 toFixed
    assert set(re.findall(r"localStore\('(\w+)'", TOOLS)) == {"fee"}                                # 驗收 18
    for w in ("localStorage", "sessionStorage", "http", "fetch(", "XMLHttpRequest", "<select"):
        assert w not in TOOLS, w


def test_no_advice_words():
    o = _out([s for s, _, _ in EX] + [_st()])
    seg = TOOLS.replace("投資或借貸建議", "").replace("投資建議", "") + "".join(l for l in CSS.splitlines() if "第 41 輪" in l) + "".join(o or [])
    for w in ADVICE:
        assert w not in seg, w
    assert TOOLS.count("斷頭") == 1


# ─── 反證（驗收 23）：改壞後上面的檢查要失敗 ─────────────────────
MUTANTS = [
    ("拆單改成一筆", "[[q - q % 1000, m], [q % 1000, mo]].filter(x => x[0] > 0)", "[[q, q >= 1000 ? m : mo]]", check_examples),
    ("零股份用整股最低值", "[q % 1000, mo]]", "[q % 1000, m]]", check_examples),
    ("兩平起點改用理論值", "  let p = p0;\n", "  let p = Math.ceil(th); p += p % tlTick(p, e) ? tlTick(p, e) - p % tlTick(p, e) : 0;\n", check_random),
    ("兩平起點不進位到升降單位", "p0 = c % u ? c + u - c % u : c;", "p0 = c;", check_examples),
    ("平均成本改用浮點四捨五入", "half = X => Number((2n * X + n) / (2n * n));", "half = X => Math.round(+(Number(X) / N / 100).toFixed(2) * 100);", check_half),
    ("刪除列不往前移", "for (let i = x; i < r - 1; i++) {", "for (let i = x; i < x; i++) {", check_rows),
    ("刪除後沒清最後一列", "for (let i = r; i < 10; i++) st['p' + i]", "for (let i = r + 1; i < 10; i++) st['p' + i]", check_rows),
    ("2,000 檔改 200 檔", "for (let k = 0; k < 2000; k++) {", "for (let k = 0; k < 200; k++) {", check_far),   # QA D102 = A
    ("證交稅合計後才捨去","x = a.map(v => Number(v * BigInt(o.r) / 1000000n))", "x = [Number(BigInt(p) * BigInt(N) * BigInt(o.r) / 1000000n)]", check_examples),
    ("換代號不清列", "  for (let i = 0; i < 10; i++) TL.ac['p' + i] = TL.ac['n' + i] = '';", "", check_load),
    ("不帶入目前價格", "  Object.assign(TL.ac, { cur: c, k: E ? 'e' : 's' });", "", check_load),
]


def test_contrast():
    if T._node("console.log('1')") is None:
        return
    for name, a, b, check in MUTANTS:
        assert TOOLS.count(a) == 1, (name, a)
        try:
            fails = check(TOOLS.replace(a, b))
        except Exception as e:                                                                     # 改壞到執行失敗也算擋下
            fails = [repr(e)]
        assert fails, "反證沒有擋下：" + name


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_") and callable(f):
            print("==", n); f()
    print("全部通過")
