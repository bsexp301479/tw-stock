"""第 34 輪（不連網、不連資料庫）：試算工具 #/tools（tools.js）— 交易成本與當沖（含漲跌停）、複利、股票質借。
有 node 時取出 app.js 的共用函式＋整個 tools.js 執行（node 14 可跑：不用 .at()、replaceAll、??=）。"""
import hashlib
import json
import random
import re
import shutil
import subprocess
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
APP = (SITE / "app.js").read_text(encoding="utf-8")
STK = (SITE / "stock.js").read_text(encoding="utf-8")
CSS = (SITE / "app.css").read_text(encoding="utf-8")
HTML = (SITE / "index.html").read_text(encoding="utf-8")
TOOLS = (SITE / "tools.js").read_text(encoding="utf-8")
TODAY = "2026-11-19"


def _grab(src, name):
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


HELPERS = "\n".join(_grab(APP, n) for n in ("fmt", "pfmt", "esc", "cls", "md", "segHTML", "onSeg", "pageTabsHTML"))
LATEST = {"date": TODAY, "stocks": {"2330": {"n": "台積電"}, "2466": {"n": "冠西電"}, "4566": {"n": "時碩工業"}},
          "etfs": {"rows": {"0050": {"n": "元大台灣50"}}}}


def _js(body, latest=LATEST):
    return (HELPERS + "\nconst window = {};\nconst App = { latest: %s, stockCache: {} };\n" % json.dumps(latest, ensure_ascii=False)
            + TOOLS + "\n" + body)


def _dt(**kw):
    st = {"mode": "dt", "dir": "b", "k": "s", "b": "", "s": "", "n": "1000", "ref": "", "d": "10", "m": "20"}
    st.update({k: str(v) for k, v in kw.items()})
    return st


def _pl(**kw):
    st = {"p1": "2100", "p2": "", "q": "1", "u": "lot", "cap": "60", "loan": "", "rate": "2.5", "days": "30", "base": "365", "fee": "0", "call": "130"}
    st.update({k: str(v) for k, v in kw.items()})
    return st


def _cp(**kw):
    st = {"P": "0", "M": "5000", "at": "end", "r": "", "n": "10", "dv": "0", "y": ""}
    st.update({k: str(v) for k, v in kw.items()})
    return st


BAD = re.compile(r"NaN|Infinity|undefined|(?<![\d.,])-0(?![.,\d])")


# ─── F34-1：交易成本、損益兩平（驗收 1～4）────────────────────
# 分析師 7 組（PM 驗算複核）：(買價, 當沖, 商品, 折扣千分比, 理論兩平, 可成交兩平, 檔數, 該價淨損益)
CASES = [(2100, True, "s", 1000, "2109.16", 2110, 2, 837), (2100, True, "s", 600, "2106.76", 2110, 2, 3236),
         (2100, False, "s", 600, "2109.93", 2110, 2, 71), (52.3, True, "s", 600, "52.47", 52.5, 2, 34),
         (23.45, True, "s", 600, "23.53", 23.55, 2, 25), (8.12, True, "s", 600, "8.15", 8.18, 6, 8),
         (195.3, False, "e", 600, "195.83", 195.85, 11, 22)]


def test_trade_cases():
    q = [{"b": round(b * 100), "n": 1000, "dz": dz, "min": 20, "k": k, "dt": dt, "today": TODAY} for b, dt, k, dz, *_ in CASES]
    o = _node(_js(f"console.log(JSON.stringify({json.dumps(q)}.map(x => {{ const r = tlBreak(x); return [(r.th / 100).toFixed(2), r.p, r.n, r.net]; }})));"))
    if o is None:
        return
    for (b, dt, k, dz, th, p, n, net), (oth, op, on, onet) in zip(CASES, o):
        assert (oth, op, on, onet) == (th, round(p * 100), n, net * 100), (b, o)
    t = _node(_js("const r = tlTrade({ b: 210000, s: 211000, n: 1000, dz: 1000, min: 20, k: 's', dt: true, today: '%s' });"
                  "console.log(JSON.stringify([r.ba, r.sa, r.bf, r.sf, r.tax, r.net]));" % TODAY))
    assert t == [210000000, 211000000, 2992, 3006, 3165, 83700]                 # 元以下捨去、0.15%


def test_break_even_exhaustive():
    """兩平價 P 淨損益 ≥ 0，前一檔 < 0（先賣後買：P ≥ 0、上一檔 < 0）；各級距與邊界 × 當沖／一般 × 股票／ETF × 10／6／2.8 折。"""
    stock = [1.01, 5.55, 9.99, 10, 10.05, 23.45, 49.95, 50, 50.1, 75.3, 99.9, 100, 100.5, 250.5, 499.5, 500, 501, 750, 999, 1000, 1005, 2100, 2995]
    etf = [1.01, 9.99, 10, 23.45, 49.99, 50, 50.05, 120.55, 195.3, 999.95, 2100]
    js = """
const out = [];
for (const [k, ps] of [['s', %s], ['e', %s], ['b', %s]]) for (const x of ps) for (const dt of [true, false]) for (const dz of [1000, 600, 280]) for (const rev of [false, true]) {
  if (rev && !dt) continue;
  const p0 = Math.round(x * 100), e = k !== 's', o = { b: p0, s: p0, n: 1000, dz, min: 20, k, dt, rev, today: '%s' };
  const r = tlBreak(o), net = p => tlTrade(Object.assign({}, o, rev ? { b: p } : { s: p })).net;
  const nb = rev ? tlNext(r.p, e) : tlPrev(r.p, e);
  out.push([k, x, dt, dz, rev, r.p != null && net(r.p) >= 0 && (r.n === 0 || net(nb) < 0) && r.p %% tlTick(r.p, e) === 0]);
}
console.log(JSON.stringify(out));""" % (json.dumps(stock), json.dumps(etf), json.dumps(etf), TODAY)
    o = _node(_js(js))
    if o is None:
        return
    assert len(o) == 405 and all(x[-1] for x in o), [x for x in o if not x[-1]][:5]
    o = _node(_js("const f = (b, s, rev) => tlBreak({ b, s, n: 1000, dz: 600, min: 20, k: 's', dt: true, rev, today: '%s' });"
                  "console.log(JSON.stringify([f(0, 210000, true), f(0, 812, true)].map(r => [r.p, r.n])));" % TODAY))
    assert o[0][0] < 210000 and o[1][0] < 812 and all(n > 0 for _, n in o)      # 先賣後買往下找


def test_tick_cross():
    o = _node(_js("console.log(JSON.stringify([tlNext(4995, false), tlNext(5000, false), tlNext(4999, true), tlNext(5000, true), tlPrev(5000, false), tlPrev(5010, false), "
                  "tlPrev(5000, true), tlNext(99900, false), tlPrev(100000, false), tlPx(5000, true), tlPx(5000, false), tlPx(211000, false)]));"))
    if o is None:
        return
    assert o == [5000, 5010, 5000, 5005, 4995, 5000, 4999, 100000, 99900, "50.00", "50.0", "2,110"], o


def test_limit_price():
    """R9 定案：漲停依漲停價所在級距捨去、跌停依跌停價所在級距進位。後 8 組是本站歷史日線實例（2025-10-30～2026-11-19，
    價格達到這個漲跌停價，用參考價所在級距算會得到不可能的價位）。"""
    cases = [(2100, False, 2310, 1890), (108, False, 118.5, 97.2), (92.2, False, 101.0, 83.0), (49.6, False, 54.5, 44.65),
             (53.6, False, 58.9, 48.25), (10.25, False, 11.25, 9.23), (9.44, False, 10.35, 8.5), (104, False, 114.0, 93.6),
             (1085, False, 1190, 977), (195.3, True, 214.8, 175.8), (49.99, True, 54.95, 45.0)]
    o = _node(_js(f"console.log(JSON.stringify({json.dumps([[round(r * 100), e] for r, e, *_ in cases])}.map(([r, e]) => tlLimit(r, e))));"))
    if o is None:
        return
    assert o == [[round(u * 100), round(d * 100)] for _, _, u, d in cases], o
    # 3388 2026-05-15、8291 2026-06-02：參考價 108，最低／收盤 97.2（低於 97.5，證明不是用參考價級距 0.5 元進位）


def test_tax_and_expiry():
    """D48 = A：到期後提醒、稅率不自動改。"""
    js = """
const f = (st, t) => tlDtOut(Object.assign({ mode: 'dt', dir: 'b', k: 's', b: '100', s: '101', n: '1000', ref: '', d: '10', m: '20' }, st), null, t);
const tax = (k, dt, t) => tlTax(k, dt, t);
console.log(JSON.stringify({ b26: f({ k: 'b' }, '2026-12-31'), b27: f({ k: 'b' }, '2027-01-01'), d27: f({}, '2027-12-31'), d28: f({}, '2028-01-01'),
  g: f({ mode: 'g' }, '2028-01-01'), e: f({ k: 'e' }, '2028-01-01'),
  r: [tax('b', true, '2027-01-01'), tax('s', true, '2028-01-01'), tax('s', false, '2026-11-19'), tax('e', true, '2026-11-19')] }));"""
    o = _node(_js(js))
    if o is None:
        return
    assert "債券 ETF 停徵（至 2026/12/31）" in o["b26"] and "期限已過" not in o["b26"]
    assert "停徵期限已過，請確認最新稅率" in o["b27"] and "<th>證交稅</th><td class=\"num \">0</td>" in o["b27"]
    assert "股票現股當沖 0.15%（至 2027/12/31）" in o["d27"] and "期限已過" not in o["d27"]
    assert "減半期限已過，請確認最新稅率" in o["d28"] and "<th>證交稅</th><td class=\"num \">151</td>" in o["d28"]   # 101,000 × 0.15% 照舊
    assert "股票 0.3%" in o["g"] and "期限已過" not in o["g"] and "ETF 0.1%（當沖不減半）" in o["e"] and "期限已過" not in o["e"]
    assert [x["r"] for x in o["r"]] == [0, 15, 30, 10] and o["r"][0]["over"] and o["r"][1]["over"]


def test_dt_output():
    js = """
const I = { code: '2330', ex: '2026-11-20' };
const f = (st, i = null) => tlDtOut(Object.assign({ mode: 'dt', dir: 'b', k: 's', b: '', s: '', n: '1000', ref: '', d: '10', m: '20' }, st), i, '%s');
console.log(JSON.stringify([f({ b: '2100', ref: '2100' }, I), f({ b: '2100', s: '2120', ref: '2100' }), f({ b: '2100', s: '2400', ref: '2100' }),
  f({ dir: 's', s: '2100' }), f({ b: '52.33' }), f({ b: '2100', n: '500' }), f({ mode: 'g', b: '8.12', n: '3', m: '1' }), f({ b: '2105', ref: '1914' }),
  f({ mode: 'g', dir: 's', b: '2100' })]));""" % TODAY
    o = _node(_js(js))
    if o is None:
        return
    a, full, over, rev, off, odd, lot, hi, g = o
    assert "<b class=\"tl-big\">2,110</b>" in a and "<th>需上漲</th><td class=\"num \">2 檔</td>" in a and "+837 元" in a and "2,109.16" in a
    assert "參考價 2,100：漲停 2,310、跌停 1,890（漲跌幅 10%，試算）" in a and "11/20 除權息，參考價另計" in a
    assert "<th>買方金額</th>" not in a                                          # 只填買價：只算兩平
    assert "<th>買方金額</th><td class=\"num \">2,100,000</td>" in full and "<th>淨損益</th><td class=\"num up\">+10,807 元</td>" in full
    assert "賣價超出漲跌停範圍" in over and "買價超出" not in over
    assert "需下跌" in rev and "買價不高於此價" in rev and "先賣後買須在當日收盤前買回" in rev
    assert "不是可成交價位（此價位升降單位 0.1 元）" in off and "損益兩平價" not in off
    assert "現股當沖股數須為 1,000 的倍數（零股不能當沖）" in odd and "<table" not in odd
    assert "現股當沖需符合券商資格；處置股、全額交割股可能不能當沖。" in a and "現股當沖需符合" not in lot   # 一般模式不寫當沖提醒
    assert "<th>買方手續費</th>" not in lot and "股票 0.3%" in lot and "每筆最低 1 元" in lot
    assert "兩平價高於漲停，當日無法以此價成交" in hi
    assert "需上漲" in g and "需下跌" not in g                                   # 一般模式沒有先賣後買
    assert not any(BAD.search(x) for x in o)


# ─── F34-2：複利（驗收 6）──────────────────────────────────
def test_compound():
    js = """
const v = o => tlCompound(Object.assign({ P: 0, M: 0, r: 0, n: 1, y: 0 }, o)).pop();
console.log(JSON.stringify([v({ P: 100000, r: 6, n: 20 }), v({ M: 5000, r: 6, n: 20 }), v({ M: 5000, r: 6, n: 20, begin: true }), v({ P: 1000, M: 5000, r: 0, n: 10 }),
  v({ P: 100000, n: 10, y: 5, re: true }), v({ P: 100000, n: 10, y: 5 }), v({ P: 100000, r: 6, n: 20, y: 0, re: true })]));"""
    o = _node(_js(js))
    if o is None:
        return
    want = [(320714, 0), (2310204, 0), (2321755, 0), (601000, 0), (162889, 0), (100000, 50000), (320714, 0)]
    for (y, inv, v, paid), (wv, wp) in zip(o, want):
        assert abs(v - wv) <= 1 and abs(paid - wp) <= 1, o
    assert o[3][1] == 601000                                                     # r = 0：等於本金合計


def test_cp_output():
    js = """
const f = st => tlCpOut(Object.assign({ P: '0', M: '5000', at: 'end', r: '', n: '10', dv: '0', y: '' }, st));
console.log(JSON.stringify([f({}), f({ r: '6', n: '20' }), f({ P: '100000', M: '0', r: '0', dv: 'out', y: '5' }), f({ r: '6', dv: 're' }), f({ r: 'abc' }),
  f({ P: '', M: '', r: '6' }), f({ r: '6', n: '51' }), f({ r: '-100' }), f({ r: '6', n: '3' }),
  tlCpForm({ P: '0', M: '5000', at: 'end', r: '', n: '10', dv: 're', y: '1.05' }, { dy: 1.05 }), tlCpForm({ P: '0', M: '5000', at: 'end', r: '', n: '10', dv: '0', y: '' }, null)]));"""
    o = _node(_js(js))
    if o is None:
        return
    empty, m20, out, noy, bad, zero, n51, neg, n3, fy, fn = o
    assert "請輸入年報酬率（自行假設" in empty and "<table" not in empty               # 年報酬率空白：不顯示結果
    assert "2,310,204 元" in m20 and "1,200,000 元" in m20 and "+1,110,204 元" in m20 and m20.count('<tr class="tl-x">') == 16   # 手機只留 5、10、15、20 年
    assert "顯示每一年" in m20 and "顯示每一年" not in n3
    assert "<th>已領股利</th><td class=\"num \">50,000 元</td>" in out and "增加金額（含已領股利）" in out and "領出不再投入" in out
    assert "請輸入殖利率" in noy and "價格年變動率（%）" in fy and "本站資料：最新殖利率 1.05%（可改）" in fy and 'value="1.05"' in fy
    assert "年報酬率（%）" in fn and 'placeholder="自行假設，必填"' in fn and 'data-k="y"' not in fn and 'data-k="r" inputmode="decimal" autocomplete="off" value=""' in fn   # 不預填報酬率
    assert all("<table" not in x for x in (bad, zero, n51, neg)) and "年數請輸入 1～50 的整數" in n51
    assert "未計稅負、二代健保、ETF 內扣費用、交易手續費，也未做通膨調整" in m20
    assert not any(BAD.search(x) for x in o)


# ─── F34-7：股票質借（驗收 18～29）───────────────────────────
def _plj(st, I="null"):
    return "tlPlOut(Object.assign(%s, %s), %s)" % (json.dumps(_pl()), json.dumps({k: str(v) for k, v in st.items()}), I)


PL = {"T1": {}, "T2": {"loan": 1500000}, "T3": {"cap": 40}, "T4": {"p1": 1000, "q": 1, "loan": 100000, "rate": 6},
      "T5a": {"p1": 2000, "loan": 1000000, "rate": 3, "days": 180}, "T5b": {"p1": 2000, "loan": 1000000, "rate": 3, "days": 180, "base": 360},
      "T6": {"p1": 50, "p2": 38, "q": 10, "loan": 300000}, "T7": {"p1": 50, "p2": 39, "q": 10, "loan": 300000},
      "T7b": {"p1": 50, "p2": 38.99, "q": 10, "loan": 300000}, "T8": {"p1": 23.45, "q": 3},
      "T9": {"days": 180}, "T10": {"days": 200}, "T10b": {"days": 183}, "T10c": {"days": 184}, "T11": {"loan": 0}}


def test_pledge_cases():
    o = _node(_js("console.log(JSON.stringify({%s}));" % ", ".join(f"{k}: {_plj(v)}" for k, v in PL.items())))
    if o is None:
        return
    t1 = o["T1"]
    for s in ("1,260,000 元<br>", "<th>本次借款</th><td class=\"num \">1,260,000 元", "<th>利息</th><td class=\"num \">2,589 元", "1,262,589 元",
              "166.67%", "高於追繳門檻 130%", "<b class=\"tl-big\">1,638.00</b>", "收盤價低於 1,638.00 時，維持率低於 130%；與試算價格差 -22.0%"):
        assert s in t1, s
    assert "回到" not in t1 and "目前已低於" not in t1 and "超過可借上限" not in t1 and "2.50%" in t1
    assert "超過可借上限，以上限 1,260,000 計算" in o["T2"] and "1,262,589 元" in o["T2"]
    assert "840,000 元<br>" in o["T3"] and "250.00%" in o["T3"] and "1,092.00" in o["T3"] and "-48.0%" in o["T3"]
    assert "<th>利息</th><td class=\"num \">493 元" in o["T4"]
    assert "14,795 元" in o["T5a"] and "÷365" in o["T5a"] and "<th>利息</th><td class=\"num \">15,000 元" in o["T5b"] and "÷360" in o["T5b"]
    t6 = o["T6"]
    assert "126.67%" in t6 and "<b class=\"tl-warn\">低於</b>追繳門檻 130%" in t6 and "39.00" in t6 and "+2.6%（目前已低於）" in t6
    assert "回到 166%" in t6 and "需補擔保品市值 118,000 元<br>或償還本金 71,085 元" in t6 and "超過可借上限" not in t6   # D57：上限只看擔保價格
    t7 = o["T7"]
    assert "130.00%" in t7 and "等於追繳門檻 130%（低於才追繳）" in t7 and "低於</b>" not in t7 and "回到" not in t7 and "差 0.0%" in t7 and "目前已低於" not in t7
    assert "低於</b>追繳門檻" in o["T7b"] and "回到 166%" in o["T7b"]
    assert "42,210 元<br>" in o["T8"] and "18.30" in o["T8"]
    assert "15,534 元" in o["T9"] and "1,275,534 元" in o["T9"] and "每次最長" not in o["T9"]
    assert "17,260 元" in o["T10"] and "1,277,260 元" in o["T10"] and "每次最長 6 個月，超過需申請續借" in o["T10"]
    assert "每次最長" not in o["T10b"] and "每次最長 6 個月" in o["T10c"]
    t11 = o["T11"]
    assert "借款為 0，不計算維持率與追繳價" in t11 and "維持率</th>" not in t11 and "追繳價</th>" not in t11 and "<th>換算年化成本</th><td class=\"num \">--" in t11
    assert not any(BAD.search(x) for x in o.values())


def test_pledge_invalid():
    st = {"rate": "", "p1": "0", "q": "0", "cap": "101", "days": "549", "call": "99", "fee": "-1", "loan": "-5", "p2": "0", "x": ""}
    js = "console.log(JSON.stringify([%s]));" % ", ".join(_plj({k: v}) for k, v in st.items()) + ""
    o = _node(_js(js))
    if o is None:
        return
    rate, p1, q, cap, days, call, fee, loan, p2, ok = o
    assert "請輸入年利率（各券商不同，本站不預填）" in rate and "<table" not in rate      # 年利率空白：不顯示結果
    assert "請輸入擔保價格" in p1 and "請輸入數量" in q and "可借成數請輸入 0～100 的整數" in cap and "借款天數請輸入 1～548 的整數" in days
    assert "追繳門檻請輸入 100～999 的整數" in call and "手續費請輸入" in fee and "借款金額請輸入 0 以上" in loan
    assert all("<table" not in x for x in (p1, q, cap, days, call, fee, loan))
    assert "請輸入試算價格" in p2 and "維持率</th>" not in p2                         # 試算價格 0：不算維持率
    assert "維持率</th>" in ok
    o2 = _node(_js("console.log(JSON.stringify([%s, %s]));" % (_plj({"cap": 61}), _plj({"cap": 100}))))
    assert all("成數超過證券商不限用途借貸官方上限 60%（其他管道依各自契約）" in x for x in o2)
    assert not any(BAD.search(x) for x in o + o2)


def test_pledge_random():
    """1,000 組隨機：與 Python Fraction 獨立重算一致；追繳價滿足 門檻 × L ≤ Pc × S 且 (Pc − 0.01) × S < 門檻 × L。"""
    rnd = random.Random(34)
    qs = []
    for _ in range(1000):
        p1 = rnd.randint(100, 500000); p2 = rnd.choice([p1, rnd.randint(1, p1 * 2)])
        n = rnd.choice([1000, 2000, 3000, 10000, rnd.randint(1, 50000)]); cap = rnd.choice([60, 40, rnd.randint(0, 100)])
        loan = rnd.choice([None, rnd.randint(0, 3000000)]); call = rnd.choice([130, rnd.randint(100, 200)])
        qs.append({"p1": p1, "p2": p2, "n": n, "cap": cap, "loan": loan, "rate": rnd.randint(0, 9000), "days": rnd.randint(1, 548),
                   "base": rnd.choice([365, 360]), "call": call})
    o = _node(_js(f"console.log(JSON.stringify({json.dumps(qs)}.map(tlPledge)));"))
    if o is None:
        return
    for q, r in zip(qs, o):
        mx = Fraction(q["p1"] * q["n"] * q["cap"], 10000).__floor__()
        L = mx if q["loan"] is None or q["loan"] > mx else q["loan"]
        I = Fraction(L * q["rate"] * q["days"], 100000 * q["base"])
        assert r["max"] == mx and r["L"] == L and r["I"] == int(I + Fraction(1, 2)), (q, r)
        if not L:
            assert "pc" not in r and "ratio" not in r
            continue
        v, back = q["p2"] * q["n"], max(166, q["call"])
        assert r["below"] == (Fraction(v, 100) / L < Fraction(q["call"], 100)) and r["eq"] == (v == q["call"] * L)
        assert q["call"] * L <= r["pc"] * q["n"] and (r["pc"] - 1) * q["n"] < q["call"] * L, (q, r)
        assert r["ratio"] == int(Fraction(v * 100, L) + Fraction(1, 2)), (q, r)          # 0.01% 為單位，四捨五入
        if r["below"]:
            add, rep = r["add"], r["repay"]
            assert v + add * 100 >= back * L > v + (add - 1) * 100                                    # 補到 166% 的最小整數元
            assert v >= back * (L - rep) and v < back * (L - rep + 1)                                   # 償還後本金是最大整數元
        else:
            assert "add" not in r


def test_disposal_note():
    I = {"code": "2466", "al": [{"t": "disposal", "s": "2026-11-17", "e": "2026-11-23"}]}
    N = {"code": "4566", "al": [{"t": "notice"}]}
    o = _node(_js("console.log(JSON.stringify([%s, %s, %s, tlInfo(%s), tlInfo(%s)]));" % (
        _plj({}, json.dumps(I)), _plj({}, json.dumps(N)), _plj({}), json.dumps({**I, "name": "冠西電", "d": TODAY, "c": 30, "e": False}),
        json.dumps({**N, "name": "時碩", "d": TODAY, "c": 9, "e": False}))))
    if o is None:
        return
    assert "處置股可能不適用為擔保品，請洽券商" in o[0]
    assert "可能不適用為擔保品" not in o[1] and "可能不適用為擔保品" not in o[2]
    assert '<span class="pill al-d">處置中（至 11/23）</span>' in o[3] and '<span class="pill al-n">注意</span>' in o[4]


def test_pledge_texts():
    """驗收 21、27、28：待確認規則的文字、用詞。"""
    o = _node(_js("console.log(JSON.stringify([%s, tlPlForm(%s)]));" % (_plj({}), json.dumps(_pl()))))
    if o is None:
        return
    out, form = o
    for s in ("以元計，實際核撥金額以券商為準", "四捨五入到元，實際以券商計算為準", "銀行、證券金融公司依各自契約",
              "借滿 60% 時追繳價約為現價 −22%，借 40% 時約 −48%", "2 個營業日內補繳至 166%", "自第 3 營業日起處分擔保品（俗稱斷頭）",
              "不含利息", "全額交割股不得為擔保品", "前一營業日收盤價 × 60%"):
        assert s in out, s
    assert out.count("斷頭") == 1 and TOOLS.count("斷頭") == 1 and "斷頭價" not in TOOLS
    assert "必填，各券商不同" in form and "60%：得為融資融券" in form and "40%：其他" in form
    for k in ("cap", "rate", "days", "fee", "call", "loan", "p1", "p2", "q"):                 # 6 個規則欄位與價格欄都可改
        assert f'data-k="{k}"' in form, k
    assert "計息 ÷365" in form and "計息 ÷360" in form
    assert "跌到" not in out and "達到" not in out


# ─── 共通：儲存、路由、載入、版面（驗收 12～17）───────────────────
def test_fee_pref():
    raws = [None, "", "abc", '{"d":6,"m":20}', '{"d":2.8,"m":1}', '{"d":-1,"m":-5}', '{"d":"","m":""}', '{"d":11,"m":0}', '{"d":"6","m":"x"}', "[]", "null"]
    o = _node(_js(f"console.log(JSON.stringify({json.dumps(raws)}.map(tlFeePref)));"))
    if o is None:
        return
    assert o == [{"d": "10", "m": "20"}, {"d": "10", "m": "20"}, {"d": "10", "m": "20"}, {"d": "6", "m": "20"}, {"d": "2.8", "m": "1"},
                 {"d": "10", "m": "20"}, {"d": "10", "m": "20"}, {"d": "10", "m": "0"}, {"d": "6", "m": "20"}, {"d": "10", "m": "20"}, {"d": "10", "m": "20"}]
    js = _grab(APP, "localStore") + """
const localStorage = { getItem() { throw new Error('denied'); }, setItem() { throw new Error('denied'); } };
console.log(JSON.stringify([tlFeePref(localStore('fee', null)), localStore('fee', null, '{"d":6,"m":20}')]));"""
    o = _node(_js(js))
    assert o == [{"d": "10", "m": "20"}, None]                                    # 丟錯照常可用
    keys = re.findall(r"localStore\('(\w+)'", TOOLS)
    assert set(keys) == {"fee"} and "localStorage" not in TOOLS and "sessionStorage" not in TOOLS
    g = _grab(TOOLS, "tlDraw")
    assert "if (tab === 'dt' && (k === 'd' || k === 'm') && d > 0 && d <= 10 && m >= 0) localStore('fee', null, JSON.stringify({ d, m }));" in g   # 質借頁不存


def test_route():
    js = _grab(APP, "esc") + "\n" + _grab(APP, "scrollAt") + "\nlet scrollKey = null;\n" + _grab(APP, "route") + r"""
let hash = '', seen = [];
const location = { get hash() { return hash; } };
const history = { state: null, replaceState(s, t, u) { this.state = s; if (u) hash = u; } };
const window = { scrollTo() {} };
const document = { title: '', querySelectorAll: () => [] }, $ = () => null, App = {};
const disposeFuturesChart = () => {}, renderToday = async () => { seen.push(['today', hash]); };
const routes = { tools: async arg => { seen.push([arg, hash, document.title]); }, watch: async () => seen.push(['watch', hash]) };
(async () => {
  for (const h of ['#/tools', '#/tools/', '#/tools/xyz', '#/tools/sbl', '#/tools?c=2330', '#/tools/pl?c=2330', '#/tools/cp', '#/tools/dt/x?c=0050', '#/toolsx', '#/watch?add=2330'])
    { hash = h; history.state = null; await route(); }
  console.log(JSON.stringify(seen));
})();"""
    o = _node(js)
    if o is None:
        return
    t = "工具｜台股資金流"
    assert o == [["dt", "#/tools/dt", t], ["dt", "#/tools/dt", t], ["dt", "#/tools/dt", t], ["dt", "#/tools/dt", t],
                 ["dt?c=2330", "#/tools/dt?c=2330", t], ["pl?c=2330", "#/tools/pl?c=2330", t], ["cp", "#/tools/cp", t],
                 ["dt?c=0050", "#/tools/dt?c=0050", t], ["today", "#/toolsx"], ["watch", "#/watch"]], o
    assert "tools: arg => window.renderTools(arg)," in APP and "+ '｜台股資金流';" in APP


def test_render_tools():
    stock = {"name": "台積電", "prices": {"d": ["2026-11-18", "2026-11-19"], "c": [2175.0, 2100.0]}, "fund": {"dy": 1.05}, "dv": [{"d": "2026-09-16"}]}
    etf = {"name": "元大台灣50", "prices": {"d": ["2026-11-18", "2026-11-19"], "c": [70.1, None]}}
    js = """
const view = { innerHTML: '' }, els = {}, loads = [], urls = [], saved = [];
const $ = s => s === '#view' ? view : (els[s] = els[s] || { innerHTML: '', classList: { add() {} }, addEventListener(t, f) { this[t] = f; } });
const history = { replaceState(s, t, u) { urls.push(u); } };
const localStore = (k, f, v) => { if (v !== undefined) saved.push([k, v]); return f; };
const loadStock = async (c, dir) => { loads.push([c, dir]); if (c === '2330') return %s; if (c === '0050') return %s; throw new Error('404'); };
(async () => {
  const r = {};
  await window.renderTools('pl?c=2330'); r.pl = view.innerHTML;
  await window.renderTools('dt?c=2330'); r.dt = view.innerHTML; r.n = loads.length;
  els['#tlForm'].input({ target: { dataset: { k: 'd' }, value: '6' } }); r.out = els['#tlOut'].innerHTML;
  els['#tlForm'].input({ target: { dataset: { k: 'm' }, value: '-1' } });
  await window.renderTools('cp?c=2330'); r.cp = view.innerHTML; r.y = TL.cp.y;
  els['#toolTabSeg'].click({ target: { closest: () => ({ dataset: { v: 'pl' } }) } });
  await window.renderTools('dt?c=9999'); r.miss = view.innerHTML;
  await window.renderTools('dt?c=%%3Cx%%3E'); r.bad = view.innerHTML;
  await window.renderTools('dt?c=<b>x'); r.xss = view.innerHTML;
  await window.renderTools('dt?c=0050'); r.etf = view.innerHTML; r.k = TL.dt.k;
  await window.renderTools('zz'); r.zz = view.innerHTML;
  console.log(JSON.stringify(Object.assign(r, { loads, urls, saved })));
})();""" % (json.dumps(stock, ensure_ascii=False), json.dumps(etf, ensure_ascii=False))
    o = _node(_js(js))
    if o is None:
        return
    assert 'value="2100"' in o["pl"] and "台積電 2330</a> 11/19 收盤 <b class=\"num\">2,100</b>" in o["pl"] and "<h2>股票質借（單檔擔保品）</h2>" in o["pl"]
    assert '<button data-v="pl" class="on">股票質借</button>' in o["pl"] and "依各機構契約為準。本站不提供投資或借貸建議。" in o["pl"]
    assert 'data-k="b" inputmode="decimal" autocomplete="off" value="2100"' in o["dt"] and 'data-k="ref" inputmode="decimal" autocomplete="off" value="2100"' in o["dt"]
    assert o["n"] == 1                                                              # 同一檔只讀一次
    assert "× 6 折" in o["out"] and o["saved"] == [["fee", '{"d":6,"m":20}']]       # 壞值不存
    assert o["y"] == "1.05" and "本站資料：最新殖利率" not in o["cp"]                 # 殖利率預填 fund.dy；欄位只在開啟股利時顯示
    assert o["urls"] == ["#/tools/pl?c=2330"]                                       # 切分頁保留 ?c=
    assert "找不到 9999 的資料，請自行輸入價格" in o["miss"] and "找不到 &lt;x&gt;" not in o["bad"] and "找不到 %3Cx%3E 的資料" in o["bad"] and "找不到 &lt;b&gt;x 的資料" in o["xss"] and "<b>x" not in o["xss"]
    assert ["9999", "stocks"] not in o["loads"] and ["0050", "etfp"] in o["loads"] and len(o["loads"]) == 2   # 不在 latest.json 的代號不發請求
    assert o["k"] == "e" and 'value="70.1"' in o["etf"] and '<span class="pill">ETF</span>' in o["etf"]
    assert '<button data-v="dt" class="on">交易成本</button>' in o["zz"]
    assert "本站不提供投資建議。" in o["dt"] and "以券商與主管機關公告為準" in o["dt"] and "僅供參考" in o["dt"] and "試算" in o["dt"]


def test_wiring():
    v = hashlib.sha1((SITE / "tools.js").read_bytes()).hexdigest()[:8]
    want = f'<script src="tools.js?v={v}" defer></script>'
    assert want in HTML, "site/index.html 的 tools.js 版本參數和檔案內容不符，請改成：\n" + want
    assert HTML.index('src="app.js?v=') < HTML.index('src="stock.js?v=') < HTML.index('src="tools.js?v=')
    assert len(re.findall(r'src="tools\.js[?"]', HTML)) == 1 and HTML.count("https://") == 2          # 沒有新的外部資源
    top, bot = HTML[HTML.index('<nav class="tabs"'):HTML.index("</nav>")], HTML[HTML.index('<nav class="bottom"'):]
    assert top.count("data-tab=") == 6 and '<a href="#/tools" data-tab="tools">工具</a>' in top
    assert bot[:bot.index("</nav>")].count("data-tab=") == 6 and 'data-tab="tools"><svg viewBox="0 0 24 24">' in bot and "</svg>工具</a>" in bot
    i = STK.index('id="starBtn"')
    assert STK.index('<a class="tl-go" href="#/tools/dt?c=${code}">試算</a>', i) > i                     # 在 #starBtn 之後（test_iter22）
    assert "http" not in TOOLS and "fetch(" not in TOOLS and "XMLHttpRequest" not in TOOLS and "loadStock(code, E ? 'etfp' : 'stocks')" in TOOLS
    for s in (".tl-f input{width:100%;box-sizing:border-box;", "font-size:16px", "@media (max-width:520px){.tl-yr:not(.all) .tl-x{display:none}.tl-all{display:inline-block}}",
              "@media (max-width:720px){.s-head .tl-go{position:absolute;top:36px;right:0;", ".s-head .s-px{padding-right:56px}"):
        assert s in CSS, s
    for w in (".at(", "??=", "||=", "&&=", "replaceAll", "structuredClone"):
        assert w not in TOOLS, w                                                     # node 14 可執行


def test_no_advice_words():
    seg = TOOLS + "".join(l for l in APP.splitlines() if "第 34 輪" in l or "tools" in l) + "".join(l for l in CSS.splitlines() if "第 34 輪" in l or "tl-" in l)
    seg += "".join(l for l in STK.splitlines() + HTML.splitlines() if "tl-go" in l or "tools" in l)
    seg = seg.replace("投資或借貸建議", "").replace("投資建議", "")                  # 免責句
    for w in ("買進", "賣出", "反彈", "見底", "買點", "超賣", "超買", "推薦", "強勢", "飆股", "勝率", "亮點", "建議", "低估", "高估", "超跌", "便宜",
              "保證", "穩賺", "斷頭價", "安全", "危險", "划算", "賣出擔保品", "連帶保證人", "融資買進"):
        assert w not in seg, w
    assert seg.count("斷頭") == 1 and "（俗稱斷頭）" in seg


# ─── QA34 補強（05-qa.md 反向驗證沒擋下的項目）──────────────────
def test_qa_compound_monthly_dividend():
    """M19：股利要以（單筆＋定期）部位計算；與 Fraction 逐月獨立重算比對。"""
    def ref(P, M, r, n, y, re_):
        a, m, paid = Fraction(P), Fraction(0), Fraction(0)
        for _ in range(n):
            a *= 1 + Fraction(r, 100)
            for _ in range(12):
                m = m * (1 + Fraction(r, 1200)) + M
            dv = (a + m) * Fraction(y, 100)
            if re_:
                a += dv
            else:
                paid += dv
        return a + m, paid
    o = _node(_js("console.log(JSON.stringify([true, false].map(re => tlCompound({ P: 100000, M: 5000, r: 6, n: 10, y: 3, re }).pop())));"))
    if o is None:
        return
    for (_, _, v, paid), re_ in zip(o, (True, False)):
        wv, wp = ref(100000, 5000, 6, 10, 3, re_)
        assert abs(Fraction(v) - wv) < 1 and abs(Fraction(paid) - wp) < 1, (o, float(wv), float(wp))


def test_qa_defaults_not_prefilled():
    """M21：年報酬率、年利率的預設值必須空白（驗收 6、7、Q34-8、P11）。"""
    o = _node(_js("console.log(JSON.stringify([TL.cp.r, TL.pl.rate, tlCpForm(TL.cp, null), tlPlForm(TL.pl)]));"))
    if o is None:
        return
    assert o[0] == "" and o[1] == "", o[:2]
    assert 'data-k="r" inputmode="decimal" autocomplete="off" value=""' in o[2] and 'data-k="rate" inputmode="decimal" autocomplete="off" value=""' in o[3]


def test_qa_pledge_float_edges():
    """M23、M25：浮點數寫法在 130% × 998,000 ÷ 1,000 股（應為 1,297.40）與 115% 等於門檻時會出錯；逐一窮舉等於門檻的組合。"""
    o = _node(_js("console.log(JSON.stringify([%s, %s, tlPledge({ p1: 40000, p2: 23046, n: 1000, cap: 60, loan: 200400, rate: 2500, days: 30, base: 365, call: 115 })]));"
                  % (_plj({"p1": 2000, "loan": 998000}), _plj({"p1": 400, "p2": 230.46, "loan": 200400, "call": 115}))))
    if o is None:
        return
    assert "收盤價低於 1,297.40 時" in o[0], o[0]
    assert "等於追繳門檻 115%（低於才追繳）" in o[1] and "回到" not in o[1]
    assert o[2]["eq"] and not o[2]["below"] and o[2]["pc"] == 23046
    qs = [{"p1": 10 ** 7, "p2": c * L // n, "n": n, "cap": 60, "loan": L, "rate": 0, "days": 1, "base": 365, "call": c}
          for c in range(100, 200) for L in (1000, 200400, 998000, 1795600) for n in (1000, 2000) if c * L % n == 0]
    r = _node(_js(f"console.log(JSON.stringify({json.dumps(qs)}.map(tlPledge).map(x => [x.eq, x.below, x.pc])));"))
    assert all(eq and not below for eq, below, _ in r) and [x[2] for x in r] == [q["p2"] for q in qs]


def test_qa_ex_dividend_date():
    """M57：只有晚於最新資料日的除權息日才顯示「m/d 除權息，參考價另計」。"""
    def stock(dv):
        return {"name": "台積電", "prices": {"d": ["2026-11-18", "2026-11-19"], "c": [2175.0, 2100.0]}, "dv": [{"d": d} for d in dv]}
    js = """
const view = { innerHTML: '' }, els = {};
const $ = s => s === '#view' ? view : (els[s] = els[s] || { innerHTML: '', classList: { add() {} }, addEventListener(t, f) { this[t] = f; } });
const history = { replaceState() {} }, localStore = (k, f) => f;
let S = null;
const loadStock = async () => S;
(async () => {
  const r = [];
  for (const [c, s] of [['2330', %s], ['2466', %s]]) { S = s; await window.renderTools('dt?c=' + c); r.push(view.innerHTML); }
  console.log(JSON.stringify(r));
})();""" % (json.dumps(stock(["2026-09-16", "2026-11-19"])), json.dumps(stock(["2026-11-20"])))
    o = _node(_js(js))
    if o is None:
        return
    assert "除權息，參考價另計" not in o[0] and "11/20 除權息，參考價另計" in o[1]


def test_qa_no_minus_zero_and_huge():
    """M60、M64、QA34-01：差 % 不能顯示 -0.0%；增加金額、手續費不能顯示 -0；超大數字（≥ 1e12）視為不合法、不出現 Infinity。"""
    nine = "9" * 400
    o = _node(_js("console.log(JSON.stringify([%s, %s, %s, tlCpOut({ P: '0', M: '49.95', at: 'end', r: '0', n: '10', dv: '0', y: '' }),"
                  " tlCpOut({ P: '1', M: '0', at: 'end', r: '-1', n: '1', dv: '0', y: '' }),"
                  " tlDtOut({ mode: 'g', dir: 'b', k: 's', b: '%s', s: '', n: '1000', ref: '%s', d: '10', m: '-0' }, null, '%s'),"
                  " tlDtOut({ mode: 'g', dir: 'b', k: 's', b: '100', s: '', n: '1000', ref: '', d: '10', m: '-0' }, null, '%s')]));"
                  % (_plj({"p2": 1638.01}), _plj({"fee": "-0"}), _plj({"p1": nine}), nine, nine, TODAY, TODAY)))
    if o is None:
        return
    assert "差 0.0%" in o[0] and "-0.0%" not in o[0]
    assert "請輸入擔保價格" in o[2] and "請輸入買價" in o[5]
    assert "每筆最低 0 元" in o[6]
    bad = re.compile(r"NaN|Infinity|∞|undefined|(?<![\d.,])-0(?:\.0+)?(?![.,\d])")
    assert not any(bad.search(x) for x in o), [bad.search(x).group(0) for x in o if bad.search(x)]


# ─── QA 後修正（34/05-qa.md D59、D60）──────────────────────────
def test_fix_ref_label_and_layout():
    js = """
const I = { code: '2330', c: 2100, d: '%s' };
const f = (st, i) => tlDtOut(Object.assign({ mode: 'dt', dir: 'b', k: 's', b: '', s: '', n: '1000', ref: '', d: '10', m: '20' }, st), i, '%s');
console.log(JSON.stringify([f({ b: '2100', ref: '2100' }, I), f({ b: '2100', ref: '2175' }, I), f({ b: '2100', ref: '2100' }, null),
  tlDtForm(Object.assign({}, TL.dt, { mode: 'dt', dir: 'b' })), tlDtForm(Object.assign({}, TL.dt, { mode: 'dt', dir: 's' })), tlPlForm(TL.pl), %s]));""" % (TODAY, TODAY, _plj({}))
    o = _node(_js(js))
    if o is None:
        return
    same, other, none, dtf, dtr, plf, pl = o
    # D59：標籤不寫「昨收」；參考價等於帶入的收盤時，寫出是哪天的收盤、用於下一交易日；自行改的參考價或沒有帶入時照舊
    assert "參考價（算漲跌停）" in dtf and "昨收" not in dtf
    assert "參考價 2,100（11/19 收盤，用於下一交易日）：漲停 2,310、跌停 1,890（漲跌幅 10%，試算）" in same
    assert "參考價 2,175：漲停 2,390、跌停 1,960" in other and "用於下一交易日" not in other
    assert "參考價 2,100：漲停 2,310、跌停 1,890" in none
    # D60：375 寬不截斷的短 placeholder；長說明移到質借說明
    assert 'placeholder="空白 = 只算兩平"' in dtf and 'placeholder="空白 = 只算兩平"' in dtr and "只算損益兩平" not in dtf + dtr
    assert 'placeholder="空白 = 擔保價格"' in plf and "改低可看下跌時" not in plf and "試算價格可改低，看下跌時的維持率。" in pl
    # 使用者 11/19：成數快捷鈕放在可借成數正下方；質借表單頂端對齊，不把同列「數量」往下推
    assert '<div class="tl-f"><label class="tl-f"><span>可借成數（%）</span>' in plf and '<div data-g="cap" class="tl-chips"><button class="chip" data-v="60">' in plf
    assert ".tl-form.tl-pl{align-items:start}" in CSS and '<div class="tl-form tl-${tab}" id="tlForm">' in TOOLS
    # 使用者 11/19：質借欄位標題 375 寬一行放得下；結果表窄螢幕時數值放不下就整列換行（不把「元」擠到下一行）
    assert "擔保價格（算可借上限）" in plf and "試算價格（算維持率）" in plf and "（元，算" not in plf
    assert '<section class="sec card tl-out tl-o${tab}" id="tlOut">' in TOOLS
    assert "@media (max-width:520px){.tl-opl .tl-kv,.tl-opl .tl-kv tbody{display:block}.tl-opl .tl-kv tr{display:flex;flex-wrap:wrap;" in CSS
    assert ".tl-opl .tl-kv td .small{word-break:keep-all}}" in CSS
    # 使用者 11/19：複利「單筆金額」改「初始金額」
    assert "tlIn('P', '初始金額（元）', st.P)" in TOOLS and "單筆金額" not in TOOLS
    assert ".tl-f input::placeholder{font-size:14px}" in CSS                     # 375 寬「空白 = 以上限計算」「必填，各券商不同」不截斷


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_") and callable(f):
            print("==", n); f()
    print("全部通過")
