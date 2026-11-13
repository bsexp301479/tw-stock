"""第 22 輪（不連網、不連資料庫）：F22-10 MACD 柱用詞、F22-11 EPS 事件與選股「轉盈」、F22-1 連續天數、F22-12 個股頁新訊號。
export 的 highlight_eps、_load_financials 用自造資料測邊界（UTC、週六對齊、基期、補抓、最新季別）；
有 node 時，逐字取出 stock.js、app.js 的函式執行（macdBar、renderSignals、runTxt、balStreak、hlTag、epsTurn）。"""
import json
import re
import shutil
import subprocess
import sys
from datetime import date, datetime, timedelta
from decimal import Decimal as D
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from twstock import export  # noqa: E402

APP = (ROOT / "site" / "app.js").read_text(encoding="utf-8")
STK = (ROOT / "site" / "stock.js").read_text(encoding="utf-8")
CSS = (ROOT / "site" / "app.css").read_text(encoding="utf-8")
README = (ROOT / "README.md").read_text(encoding="utf-8")
SRC = (ROOT / "twstock" / "export.py").read_text(encoding="utf-8")


def _weekdays(a, b):
    out, d = [], a
    while d <= b:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


DAYS = _weekdays(date(2026, 9, 1), date(2026, 11, 13))      # 交易日（測試用：週一～五）；最後一天 11/13（週五）
FQ = (2026, 3)


def _cum(cur, base, q2=D("0")):
    """2026Q3 單季 = cur、2025Q3 單季 = base（Q2 累計 q2，Q3 累計 = q2 + 單季）。"""
    return {(2026, 2): (None,) * 4 + (q2,), (2026, 3): (None,) * 4 + (q2 + cur,),
            (2025, 2): (None,) * 4 + (D("0"),), (2025, 3): (None,) * 4 + (base,)}


def _eps(cur, base, seen, fq=FQ, days=DAYS):
    return export.highlight_eps(_cum(D(cur), D(base)), seen, fq, days)


def test_eps_kinds():
    fs = date(2026, 11, 12)
    assert _eps("0.90", "-0.10", (fs, None)) == [["et", "2026-11-12", 202603]]          # 台塑型：轉盈
    assert _eps("0.25", "0", (fs, None)) == [["et", "2026-11-12", 202603]]              # 去年同季 0 也算轉盈
    assert _eps("29.42", "17.44", (fs, None)) == [["eg", "2026-11-12", 202603]]        # +68.7%
    assert _eps("0.36", "0.24", (fs, None)) == [["eg", "2026-11-12", 202603]]          # 剛好 +50.0%（≥，同選股 scrGe）
    assert _eps("0.65", "0.10", (fs, None)) == [["eg", "2026-11-12", 202603]]          # 去年同季剛好 0.1 元不是基期低（同前端 b < 0.1）
    assert _eps("1.00", "0.05", (fs, None)) == []                                      # 基期低
    assert _eps("3.15", "2.55", (fs, None)) == []                                      # 建準型 +23.5%
    assert _eps("-0.20", "-0.50", (fs, None)) == []                                    # 仍虧損
    assert _eps("0.10", "0.20", (fs, None)) == []                                      # 衰退
    # 去年同季缺、本季缺、該股最新一季不是全市場最新季（金融業 Q2）→ 不產生
    cum = _cum(D("1"), D("0.5"))
    del cum[(2025, 3)]
    assert export.highlight_eps(cum, (fs, None), FQ, DAYS) == []
    q2_only = {k: v for k, v in _cum(D("1"), D("-1")).items() if k != (2026, 3)}
    assert export.highlight_eps(q2_only, (None, datetime(2026, 11, 6, 15, 48)), FQ, DAYS) == []
    assert export.highlight_eps(_cum(D("1"), D("-1")), None, FQ, DAYS) == []


def test_eps_dates():
    utc = lambda *a: (None, datetime(*a))                       # 補抓：first_seen NULL，created_at 為 UTC
    assert _eps("0.08", "-0.16", utc(2026, 11, 6, 15, 48)) == [["et", "2026-11-06", 202603]]    # 中鋼型：COALESCE 生效
    assert _eps("0.08", "-0.16", utc(2026, 11, 9, 17, 0)) == [["et", "2026-11-10", 202603]]     # UTC 11/09 17:00 = 台灣 11/10
    assert _eps("0.08", "-0.16", utc(2026, 11, 6, 16, 30)) == [["et", "2026-11-06", 202603]]    # 台灣 11/07（週六）→ 11/06
    assert _eps("29.42", "17.44", (date(2026, 11, 14), datetime(2026, 11, 13, 16, 26))) == [["eg", "2026-11-13", 202603]]   # 台積電型：first_seen 週六 → 11/13
    # 窗口：最近 20 個交易日（10/19 起）
    assert DAYS[-export.HL_REV_DAYS] == date(2026, 10, 19)
    assert _eps("0.9", "-0.1", (date(2026, 10, 19), None)) == [["et", "2026-10-19", 202603]]
    assert _eps("0.9", "-0.1", (date(2026, 10, 18), None)) == []                     # 週日 → 10/16，窗口外
    assert _eps("0.9", "-0.1", (date(2026, 8, 31), None), days=DAYS[:5]) == []       # 交易日不足 20 天
    # 補抓防呆：first_seen NULL 且晚於金融業截止日（11/29）5 天以上 → 改用 11/29，對齊 11/27（週五），12/31 時在窗口外
    dec = _weekdays(date(2026, 9, 1), date(2026, 12, 31))
    assert _eps("0.9", "-0.1", utc(2026, 12, 20, 2, 0), days=dec) == []
    assert _eps("0.9", "-0.1", utc(2026, 12, 3, 2, 0), days=dec[:dec.index(date(2026, 12, 10)) + 1]) == [["et", "2026-12-03", 202603]]   # 截止日 + 4 天：照收錄日
    assert _eps("0.9", "-0.1", (date(2026, 12, 20), None), days=dec) == [["et", "2026-12-18", 202603]]   # 日常收集的晚申報：照收錄日


def test_load_financials():
    class Cur:
        def execute(self, sql):
            assert "f.eps, f.first_seen, f.created_at" in sql
            return iter([("2002", "TWSE", 2026, 2, "ci", 1, 2, 3, 4, D("0.1"), None, datetime(2026, 11, 6, 15, 48)),
                         ("2002", "TWSE", 2026, 3, "ci", 1, 2, 3, 4, D("0.18"), None, datetime(2026, 11, 6, 15, 48)),
                         ("2330", "TWSE", 2026, 3, "ci", 1, 2, 3, 4, D("50"), date(2026, 11, 14), datetime(2026, 11, 13, 16, 26))])
    fin, meta, counts, seen = export._load_financials(Cur())
    assert fin["2002"][(2026, 3)] == (1, 2, 3, 4, D("0.18"))                           # 既有回傳不變
    assert meta == {"2002": ("ci", None), "2330": ("ci", date(2026, 11, 14))}
    assert counts[(2026, 3, "TWSE")] == 2
    assert seen["2330"][(2026, 3)] == (date(2026, 11, 14), datetime(2026, 11, 13, 16, 26))


def test_export_source():
    assert "HL_EPS_YOY, HL_EPS_BASE = 50, 0.1" in SRC
    assert "fq_all = max(((y, q) for y, q, _ in fin_counts), default=None)" in SRC          # 全市場最新季別
    assert "+ highlight_eps(fin.get(code, {}), fin_seen[code].get(fq_all), fq_all, b_days) + hl_act.get(code, [])," in SRC
    assert "(ca + timedelta(hours=8)).date()" in SRC                                         # created_at 是 UTC


def _grab(src, name):
    """取出頂層 function 或 const（const 取到去掉行尾註解後結尾為「;」的那一行）。"""
    m = re.search(rf"^(?:async )?function {name}\(", src, re.M)
    if m:
        i, n = src.index("{", src.index(")", m.start())), 0
        for j in range(i, len(src)):
            n += {"{": 1, "}": -1}.get(src[j], 0)
            if n == 0:
                return src[m.start():j + 1]
    m = re.search(rf"^const {name}\b", src, re.M)
    assert m, name
    lines = src[m.start():].splitlines()
    k = next(i for i, l in enumerate(lines) if re.sub(r"\s+//[^'`]*$", "", l).rstrip().endswith(";"))
    return "\n".join(lines[:k + 1])


def _node(js):
    node = shutil.which("node")
    if not node:
        return None
    return json.loads(subprocess.run([node, "-e", js], capture_output=True, text=True, check=True).stdout)


def test_macd_words():
    js = "\n".join(_grab(STK, n) for n in ("macdBar", "SIG_MIN", "calcMA", "calcMACD", "calcKD", "calcRSI", "oscLine", "renderSignals")) + \
        "\n" + "\n".join(_grab(APP, n) for n in ("fmt", "md")) + """
const box = {}, $ = s => (box[s] = box[s] || {});
const cases = [[0.32, 0.39], [0.62, 0.52], [-1.57, -1.13], [-0.26, -0.29], [-0.34, 0.03], [1.38, -0.29], [0.2, 0.2], [-0.5, 0], [0.5, 0], [0, 0.1], [0, -0.1]];
const C = [...Array(60).fill(100), ...Array.from({ length: 15 }, (_, i) => 99 - i * 2), 72, 72.5];   // 下跌後止跌：負柱縮短
const rows = C.map((c, i) => ({ d: '2026-11-' + String(i % 28 + 1).padStart(2, '0'), o: c, h: c, l: c, c, nt: false }));
const { hist } = calcMACD(C), n = C.length;
renderSignals(rows, '日');
console.log(JSON.stringify({ w: cases.map(([a, b]) => macdBar(a, b)), h: [hist[n - 2], hist[n - 1]], html: box['#sigBox'].innerHTML }));"""
    o = _node(js)
    if o is None:
        print("  （沒有 node，略過 MACD 執行）"); return
    assert o["w"] == ["MACD 正柱加長", "MACD 正柱縮短", "MACD 負柱縮短", "MACD 負柱加長", "MACD 柱由負翻正", "MACD 柱由正翻負",
                      "MACD 柱持平", "MACD 負柱縮短", "MACD 正柱縮短", "MACD 正柱加長", "MACD 負柱加長"], o["w"]
    a, b = o["h"]
    assert a < b < 0, o["h"]                                                     # 樣本本身：負柱、柱值上升
    assert '<span class="tag up">MACD 負柱縮短</span>' in o["html"] and "柱放大" not in o["html"]
    assert "MACD 柱放大" not in STK and "MACD 柱縮小" not in STK
    assert "chk(hist[i] > hist[i - 1], macdBar(hist[i - 1], hist[i]), macdBar(hist[i - 1], hist[i]));" in STK   # 多空歸類不變


def test_streak():
    js = "\n".join(_grab(STK, n) for n in ("runTxt", "balStreak")) + """
const D = Array.from({ length: 40 }, (_, i) => new Date(Date.UTC(2026, 8, 1 + i)).toISOString().slice(0, 10));
const up = D.map((_, i) => 1000 + i);
const r = {
  t: [[30, '買', '賣'], [-3, '買', '賣'], [1, '買', '賣'], [0, '買', '賣'], [undefined, '買', '賣'], [5, '增', '減'], [-31, '增', '減']].map(a => runTxt(...a)),
  cap: balStreak({ mb: up }, D, 'mb', D[39]),
  to: balStreak({ mb: up.map((v, i) => i > 35 ? 0 : v) }, D, 'mb', D[35]),
  zero: balStreak({ mb: up.map((v, i) => i === 37 ? up[36] : v) }, D, 'mb', D[39]),
  gap: balStreak({ mb: up.map((v, i) => i === 37 ? null : v) }, D, 'mb', D[39]),
  conv: balStreak({ lb: [5000, 4000, 1000, 1010, 1020, 103, 104], k: [{ d: D[5], k: 0.1 }] }, D.slice(0, 7), 'lb', D[6]),
  noConv: balStreak({ lb: [5000, 4000, 1000, 1010, 1020, 103, 104] }, D.slice(0, 7), 'lb', D[6]),
  none: [balStreak(undefined, D, 'mb', D[39]), balStreak({ mb: [1] }, D.slice(0, 1), 'mb', D[0]), balStreak({ mb: [5, 4, 3] }, D.slice(0, 3), 'lb', D[2])],
};
console.log(JSON.stringify(r));"""
    o = _node(js)
    if o is None:
        print("  （沒有 node，略過連續天數執行）"); return
    assert o["t"] == ["連買 30 日以上", "連賣 3 日", "", "", "", "連增 5 日", "連減 30 日以上"], o["t"]
    assert o["cap"] == 30                       # 最多看 30 日
    assert o["to"] == 30                        # 只算到 to（之後的 0 不影響）
    assert o["zero"] == 2 and o["gap"] == 1     # 增減 0、缺值中斷
    assert o["conv"] == 4 and o["noConv"] == 1  # 面額變更：換算前 1000、1010、1020 → 100、101、102，連增 4 日（不換算只有 1 日）
    assert o["none"] == [0, 0, 0]               # 沒有融資資料、只有 1 天、沒有借券


def test_stock_source():
    assert "subs(fd, runTxt(s?.s, '買', '賣'))" in STK
    assert "subs('至 ' + fd, runTxt(s?.fs, '買', '賣'))" in STK and "subs('至 ' + fd, runTxt(s?.ts, '買', '賣'))" in STK
    assert "!E && runTxt(balStreak(data.mg, P.d, 'mb', MG.d), '增', '減')" in STK              # ETF 頁不加
    assert "!E && runTxt(balStreak(data.mg, P.d, 'lb', SL.d), '增', '減')" in STK
    # F22-12：頁首、共用 hlTag；舊 app.js 沒有 hlTag 或不認得的種類不列
    assert "const HL = typeof hlTag === 'function' ? (s?.hl || []).filter(e => HL_KINDS[e[0]]) : [];" in STK
    assert '${HL.length ? `<div class="s-hl"><a class="small" href="#/rank/hl">近期新訊號</a>${HL.map(hlTag).join(\'\')}' in STK
    head = STK[STK.index('<div class="s-head">'):STK.index('id="starBtn"')]
    assert head.index('<div class="tags">') < head.index('s-hl')                    # 族群標籤下方、頁首內
    assert ".s-hl{margin-top:6px}" in CSS


def test_app_hl():
    js = "\n".join(_grab(APP, n) for n in ("md", "HL_KINDS", "hlTag", "hlDims", "isNum", "epsTurn")) + """
const tags = [['et', '2026-11-12', 202603], ['eg', '2026-11-13', 202603], ['rv', '2026-11-10', 202610], ['nh', '2026-11-13']].map(hlTag);
const t = [{ eq: 0.08, eb: -0.16 }, { eq: 0.5, eb: 0 }, { eq: 0, eb: -1 }, { eq: 1, eb: 0.01 }, { eq: 1, eb: null }, { eq: 1 }].map(epsTurn);
console.log(JSON.stringify({ tags, dims: [hlDims({ hl: [['rv', 'x'], ['et', 'x'], ['eg', 'x']] }), hlDims({ hl: [['rv', 'x'], ['s3', 'x'], ['eg', 'x']] })], t }));"""
    o = _node(js)
    if o is not None:
        assert o["tags"] == ['<span class="hl-tag">26Q3 EPS 轉盈 <i>11/12</i></span>', '<span class="hl-tag">26Q3 EPS 年增 ≥ 50% <i>11/13</i></span>',
                             '<span class="hl-tag">10 月營收創新高 <i>11/10</i></span>', '<span class="hl-tag">60 日新高帶量 <i>11/13</i></span>'], o["tags"]
        assert o["dims"] == [1, 2]                                                   # 營收、EPS 同屬「基本面」
        assert o["t"] == [True, True, False, False, False, False]
    assert "{ id: 'et', g: '基本面', label: '單季 EPS 轉盈', sw: true, f: epsTurn, cols: ['eq', 'eb']" in APP
    assert "eb: ['去年同季EPS', x => x.eb, (v, x) => fmt(v, 2) + finTag(x)]," in APP
    assert "營收、EPS 日期為本站首次收錄日" in APP


def test_no_advice_words():
    seg = "".join(_grab(STK, n) for n in ("macdBar", "runTxt", "balStreak"))
    seg += "".join(l for l in STK.splitlines() if "const HL = " in l or "s-hl" in l)
    seg += APP[APP.index("// ─── 第 21 輪 F21-1"):APP.index("// ─── 第 8 輪 F8-2")] + _grab(APP, "epsTurn")
    seg += "".join(re.findall(r"\{ id: 'et'.*?\},\n", APP, re.S))
    seg += "".join(l[l.index("第 22 輪"):] for l in README.splitlines() if "第 22 輪" in l)
    assert seg.count("第 22 輪") >= 4, seg.count("第 22 輪")                       # README 4 段都有取到
    seg = seg.replace("借券賣出", "")                                               # 官方資料名稱（借券賣出餘額），不是建議
    for w in ("買進", "賣出", "反彈", "見底", "買點", "超賣", "超買", "推薦", "強勢股", "飆股", "勝率",
              "利多", "利空", "看多", "看空", "轉強", "轉弱"):
        assert w not in seg, w


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_") and callable(f):
            print("==", n); f()
    print("全部通過")
