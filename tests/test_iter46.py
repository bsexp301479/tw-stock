"""第 46 輪（不連網、不連資料庫）：ETF 近期表現（含息報酬，對照加權指數）F46-1～F46-4。
export.etf_perf 用自造資料測除息、上市推測分割、上櫃不反推、D138 防呆（只對上櫃）、從沒成交；有實際 site/data 且資料日是 2026-11-20 時核對分析師 2.6 的手算例。
有 node 時逐字取出 stock.js 的 perfHTML、app.js 的 etfPerfHTML 執行；卡片與列表文字和 docs/iterations/46/02-pm.md 二之一逐字比對。
最後的 test_contrast 把原始碼改壞（反證），確認對應的檢查會失敗。"""
import hashlib
import inspect
import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
from twstock import export  # noqa: E402
import test_iter34 as T  # noqa: E402
import test_iter42 as T42  # noqa: E402

SITE, HTML, APP, STK = T.SITE, T.HTML, T.APP, T.STK
SRC = (ROOT / "twstock" / "export.py").read_text(encoding="utf-8")
README = (ROOT / "README.md").read_text(encoding="utf-8")
PM = (ROOT / "docs" / "iterations" / "46" / "02-pm.md").read_text(encoding="utf-8")
ADVICE = set(T42.ADVICE) | {"買進", "賣出", "反彈", "見底", "買點", "超賣", "超買", "推薦", "強勢股", "飆股", "勝率", "保證", "穩賺", "建議",
                            "便宜", "亮點", "低估", "高估", "跑贏", "跑輸", "強於大盤", "弱於大盤", "贏過", "輸給", "領先", "落後", "超額報酬"}

DAYS = [d for d in (date(2025, 10, 30) + timedelta(days=i) for i in range(400)) if d.weekday() < 5 and d <= date(2026, 11, 13)]
W52 = DAYS[-1] - timedelta(days=365)
IDX = {d: 100.0 + i for i, d in enumerate(DAYS)}


def _rows(c, ch=None):
    """收盤串列 → _load_etf_hist 格式 (日期, 開, 高, 低, 收, 量, 官方漲跌)；ch 預設 = 收盤 − 前一個收盤（第一天 0）。"""
    if ch is None:
        ch = [0.0] + [None if b is None or a is None else round(b - a, 2) for a, b in zip(c, c[1:])]
    return [(d, x, x, x, x, 1000 if x is not None else 0, h) for d, x, h in zip(DAYS, c, ch)]


def _w(pf):
    return next(r for r in pf if r[0] == "w")


# ─── F46-1：etf_perf ─────────────────────────────────────
def check_perf(fn=None):
    """自造資料。fn：要檢查的 etf_perf（反證時傳改壞的版本）。回傳 True／False。"""
    fn = fn or export.etf_perf
    n, k = len(DAYS), len(DAYS) - 30
    try:
        # 1. 上市除息：除息前 100、參考價 98，之後收盤 98（官方漲跌 0 = 不比價）→ 含息報酬 0%
        c = [100.0] * k + [98.0] * (n - k)
        ch = [0.0] * n
        ev = [(DAYS[k], 100, 98, 2)]
        pf = fn(_rows(c, ch), "TWSE", ev, DAYS, IDX, W52)
        assert all(r[2] == 0 for r in pf), pf
        assert pf == export.stock_perf(DAYS, [98.0] * n, DAYS, IDX, W52)                       # 和股票同一套
        assert [r[3] for r in pf] == [r[3] for r in export.stock_perf(DAYS, c, DAYS, IDX, W52)]  # 指數欄就是傳入的指數
        # 2. 上市推測分割（不在除息表；漲跌 +0.5 → 參考價 20.0，係數 0.2）：52 週 = 20.5 ÷ (100 × 0.2) − 1 = +2.5%
        c = [100.0] * k + [20.5] * (n - k)
        ch = [0.0] + [0.0] * (k - 1) + [0.5] + [0.0] * (n - k - 1)
        assert _w(fn(_rows(c, ch), "TWSE", (), DAYS, IDX, W52))[2] == 2.5
        # 3. 上櫃除息（官方漲跌空白、在除息表）→ 照常輸出 0%；除息表沒有那天（可疑分割日）→ None（D138）
        c = [100.0] * k + [98.0] * (n - k)
        ch = [0.0] + [0.0] * (k - 1) + [None] + [0.0] * (n - k - 1)
        assert all(r[2] == 0 for r in fn(_rows(c, ch), "TPEx", ev, DAYS, IDX, W52))
        assert fn(_rows(c, ch), "TPEx", (), DAYS, IDX, W52) is None
        # 4. 上櫃不做「收盤 − 漲跌」反推：漲跌和收盤差不一致的一天不調整 → 52 週 = 101 ÷ 100 − 1 = +1%
        c = [100.0] * k + [101.0] * (n - k)
        ch = [0.0] * k + [0.5] + [0.0] * (n - k - 1)
        assert _w(fn(_rows(c, ch), "TPEx", (), DAYS, IDX, W52))[2] == 1.0
        # 5. 還原後單日 +31%：上櫃 → None；上市（期貨、槓桿 ETF 的真實漲跌）→ 照常輸出
        c = [100.0] * k + [131.0] * (n - k)
        assert fn(_rows(c), "TPEx", (), DAYS, IDX, W52) is None
        assert _w(fn(_rows(c), "TWSE", (), DAYS, IDX, W52))[2] == 31.0
        assert _w(fn(_rows([100.0] * k + [129.0] * (n - k)), "TPEx", (), DAYS, IDX, W52))[2] == 29.0   # 29% 不擋
        # 6. 從沒成交 → None；新上市 → 最後加 "s"
        assert fn(_rows([None] * n, [None] * n), "TWSE", (), DAYS, IDX, W52) is None
        pf = fn(_rows([None] * (n - 3) + [10.0, 10.5, 11.0]), "TWSE", (), DAYS, IDX, W52)
        assert pf[-1][:3] == ["s", str(DAYS[-3]), 10.0] and pf[0][2] is None, pf
    except (AssertionError, TypeError):          # TypeError：該輸出的回了 None
        return False
    return True


def test_etf_perf():
    assert check_perf()


def check_wiring(src=SRC):
    """etf_perf 的位置與接法、etf_export 不變、latest.json 的接法。"""
    try:
        assert src.index("def etf_gaps(") < src.index("def etf_perf(") < src.index("def etf_export(")
        assert "pf" not in src[src.index("def etf_export"):src.index("def _load_holdings")]                       # test_iter23
        assert src.count("sh_etf") == 3                                                                             # test_iter43
        assert src.count('E["epf"]') == 1
        i = src.index('E["epf"] = epf')
        assert src.index('                E["sh"] = sh_etf[code]') < i < src.index("            _write(p, E)")
        assert 'if (epf := etf_perf(epx[code], m, eev.get(code, ()), p_days, idx_close["TWSE"], w52_start)) is not None:' in src
        assert src.index("            edv[code] = etf_div_row(E.get(\"dv\", []), latest_date)") < src.index("edv[code][EPF_KEYS[k]] = r")
        assert "if k in EPF_KEYS and r is not None:\n                    edv[code][EPF_KEYS[k]] = r" in src             # QA46-01：缺值不輸出
        assert 'EPF_KEYS = {20: "r20", 60: "r60", "y": "ry", "w": "rw"}' in src
        assert 'latest["etfs"]["ix"] = {str(k): eix[k] for k in EPF_KEYS if k in eix}' in src
        assert src.index('"etfs": etf_block(etf_latest, etf_margin_rows, esbl, edv),') < src.index('latest["etfs"]["ix"]')
        f = src[src.index("def etf_perf("):src.index("def etf_export(")]
        assert '_price_events(d_, c, ch, "TWSE", ev)' in f and 'market == "TPEx" and' in f and "> 0.30" in f
    except (AssertionError, ValueError):
        return False
    return True


def test_wiring():
    assert check_wiring()
    assert hashlib.sha1(inspect.getsource(export.etf_export).encode()).hexdigest()[:12] == "711fa2b7790c"          # etf_export 一字不改
    assert "epf" not in export.SCREEN_KEYS and "epf" not in inspect.getsource(export.screen_build)


# ─── 實際匯出（site/data；資料日 2026-11-20 時核對手算例）──────
WANT = {
    "0050": [[5, "2026-11-13", -17.61, -17.5, -0.11], [20, "2026-10-21", -21.91, -23.15, 1.24], [60, "2026-08-21", -19.3, -20.32, 1.02],
             [120, "2026-05-27", -17.15, -18.58, 1.43], ["y", "2025-12-31", 31.35, 24.41, 6.94], ["w", "2025-11-20", 39.2, 31.38, 7.82]],
    "0056": [[5, "2026-11-13", -16.4, -17.5, 1.1], [20, "2026-10-21", -22.3, -23.15, 0.85], [60, "2026-08-21", -12.89, -20.32, 7.43],
             [120, "2026-05-27", -5.49, -18.58, 13.09], ["y", "2025-12-31", 33.84, 24.41, 9.44], ["w", "2025-11-20", 38.48, 31.38, 7.1]],
    "00878": [[5, "2026-11-13", -13.23, -17.5, 4.26], [20, "2026-10-21", -17.62, -23.15, 5.53], [60, "2026-08-21", -9.96, -20.32, 10.36],
              [120, "2026-05-27", -1.63, -18.58, 16.95], ["y", "2025-12-31", 44.32, 24.41, 19.91], ["w", "2025-11-20", 52.32, 31.38, 20.94]],
    "00679B": [[5, "2026-11-13", 1.27, -17.5, 18.76], [20, "2026-10-21", 2.56, -23.15, 25.71], [60, "2026-08-21", 2.29, -20.32, 22.61],
               [120, "2026-05-27", 1.46, -18.58, 20.04], ["y", "2025-12-31", 0.14, 24.41, -24.27], ["w", "2025-11-20", 0.17, 31.38, -31.21]],
    "0052": [[5, "2026-11-13", -18.04, -17.5, -0.54], [20, "2026-10-21", -23.05, -23.15, 0.1], [60, "2026-08-21", -20.46, -20.32, -0.14],
             [120, "2026-05-27", -19.93, -18.58, -1.35], ["y", "2025-12-31", 30.88, 24.41, 6.47], ["w", "2025-11-20", 41.52, 31.38, 10.14]],
}


def test_site_data():
    lp = SITE / "data" / "latest.json"
    if not lp.exists():
        print("  （沒有 site/data，略過）")
        return
    L = json.loads(lp.read_text(encoding="utf-8"))
    E = L.get("etfs") or {}
    if "ix" not in E:
        print("  （尚未用第 46 輪匯出，略過）")
        return
    n = 0
    for code, r in E["rows"].items():
        p = SITE / "data" / "etfp" / f"{code}.json"
        if not p.exists():
            continue
        pf = json.loads(p.read_text(encoding="utf-8")).get("epf")
        if pf is None:
            assert not any(k in r for k in ("r20", "r60", "ry", "rw")), code
            continue
        n += 1
        assert [x[0] for x in pf[:6]] == [5, 20, 60, 120, "y", "w"] and (len(pf) == 6 or pf[6][0] == "s"), code
        want = {v: x[2] for x in pf for k, v in export.EPF_KEYS.items() if x[0] == k and x[2] is not None}
        assert {k: r[k] for k in ("r20", "r60", "ry", "rw") if k in r} == want, code               # 列表 = epf 第 3 欄，缺值不輸出
        assert list(r)[-len(want):] == list(want) if want else True, code                           # 新欄放在最後
        for x in pf:
            if x[2] is not None and str(x[0]) in E["ix"]:
                assert x[3] == E["ix"][str(x[0])], (code, x)                                         # 上市、上櫃都對照加權
    assert n > 0
    if L["date"] != "2026-11-20":
        print("  （資料日不是 2026-11-20，只檢查格式與一致性）")
        return
    epf = {c: json.loads((SITE / "data" / "etfp" / f"{c}.json").read_text(encoding="utf-8")).get("epf")
           for c in ("0050", "0056", "00878", "00679B", "0052", "009833", "00991A", "00674R", "00631L", "00775B", "00986B")}
    for c, w in WANT.items():
        assert epf[c] == w, (c, epf[c])
    assert epf["009833"][:6] == [[k, b, None, None, None] for k, b in (x[:2] for x in WANT["0050"])]
    assert epf["009833"][6] == ["s", "2026-11-19", -5.05, -6.23, 1.17]
    assert epf["00991A"][5][2:] == [None, None, None] and epf["00991A"][6] == ["s", "2025-12-18", 11.52, 31.18, -19.66]
    assert _w(epf["00674R"])[2] == 11.44 and _w(epf["00631L"])[2] == 41.73 and _w(epf["00775B"])[2] == 0.92
    assert epf["00986B"][0][2:4] == [0.0, -17.5]
    assert E["ix"] == {"20": -23.15, "60": -20.32, "y": 24.41, "w": 31.38}
    r = E["rows"]["0050"]
    assert [r["r20"], r["r60"], r["ry"], r["rw"]] == [-21.91, -19.3, 31.35, 39.2] and list(r)[-5:] == ["dvc", "r20", "r60", "ry", "rw"]
    assert "rw" not in E["rows"]["00991A"] and not any(k in E["rows"]["009833"] for k in ("r20", "r60", "ry", "rw"))
    assert n == len(E["rows"]) == 367, n


# ─── F46-2：ETF 個股頁卡片（perfHTML 的 etf 參數）─────────────
def _pm_cell(label):
    """02-pm.md 二之一表格：第一欄以 label 開頭那一列的最後一個 `…`。"""
    m = re.search(rf"^\| {re.escape(label)}.*`([^`]+)` \|$", PM, re.M)
    assert m, label
    return m.group(1)


PM_FULL = PM[PM.index("完整說明（"):].split("```\n")[1].split("```")[0].strip()
S_EXPR = "${at('s') ? `；${ls}從本站第一個成交日 ${at('s')} 的收盤起算，不是發行價（本站日線從 2025-10-30 起）` : ''}"
assert PM_FULL.count(S_EXPR) == 1
PM_SHORT = _pm_cell("短句")
PM_TIP = {"B": _pm_cell("`B`"), "L": _pm_cell("`L`、`R`"), "U": _pm_cell("`U`")}
PM_FOOT = _pm_cell("表現表頁尾")
PF = [[5, "2026-11-13", 1.27, -17.5, 18.76], [20, "2026-10-21", 2.56, -23.15, 25.71], [60, "2026-08-21", 2.29, -20.32, 22.61],
      [120, "2026-05-27", 1.46, -18.58, 20.04], ["y", "2025-12-31", 0.14, 24.41, -24.27], ["w", "2025-11-20", 0.17, 31.38, -31.21]]
FRESH = [[k, b, None, None, None] for k, b, *_ in PF] + [["s", "2026-11-19", -5.05, -6.23, 1.17]]
# 第 46 輪前的 perfHTML 對 test_iter23 四組輸入的輸出雜湊（股票版一字不變）
STOCK_SHA = "c2dc8dcf8799"


def _perf(stk=STK, calls=""):
    js = "\n".join(T._grab(APP, n) for n in ("fmt", "sgn", "cls", "md", "noteHTML")) + "\n" + \
        "\n".join(T._grab(stk, n) for n in ("PF_NAME", "perfHTML")) + "\nconst App = { latest: { date: '2026-11-20' } };\n" + \
        f"const PF = {json.dumps(PF)}, FRESH = {json.dumps(FRESH)};\n" + """
const full = [[5, '2026-11-06', 7.2, 10.01, -2.81], [20, '2026-10-14', -21.64, -10.18, -11.46], [60, '2026-08-14', -8.22, -4.66, -3.56],
  [120, '2026-05-20', -3.11, 9.13, -12.25], ['y', '2025-12-31', -13.06, 50.79, -63.86], ['w', '2025-11-13', -24.17, 56.52, -80.69]];
const fresh = [[5, '2026-11-06', -1.45, 10.01, -11.46], [120, '2026-05-20', null, null, null], ['y', '2025-12-31', null, null, null],
  ['w', '2025-11-13', null, null, null], ['s', '2026-07-23', -21.42, -2.62, -18.8]];
App.latest.date = '2026-11-13';
const stock = [perfHTML(full, 'TWSE', null), perfHTML(fresh, 'TWSE', null), perfHTML(full, 'TPEx', '2026-11-05'), perfHTML(fresh, 'TPEx', null)];
const stock2 = [perfHTML(full, 'TWSE', null, false), perfHTML(fresh, 'TWSE', null, false), perfHTML(full, 'TPEx', '2026-11-05', false), perfHTML(fresh, 'TPEx', null, false)];
App.latest.date = '2026-11-20';
const etf = {};
for (const [c, m, nt, pf] of [['0050', 'TWSE', null, PF], ['00679B', 'TPEx', null, PF], ['00631L', 'TWSE', null, PF], ['00632R', 'TWSE', null, PF],
  ['00642U', 'TWSE', null, PF], ['00878', 'TWSE', null, PF], ['00625K', 'TPEx', null, PF], ['009833', 'TWSE', null, FRESH], ['00986B', 'TPEx', '2026-11-12', FRESH]])
  etf[c] = perfHTML(pf, m, nt, c);
console.log(JSON.stringify([stock, stock2, etf]));"""
    return T._node(js)


def check_card(stk=STK):
    o = _perf(stk)
    if o is None:
        return True
    stock, stock2, etf = o
    try:
        assert stock == stock2 and hashlib.sha1(json.dumps(stock, ensure_ascii=False).encode()).hexdigest()[:12] == STOCK_SHA
        for c, h in etf.items():
            assert "<h2>近期表現（含息）</h2>" in h and "<th>區間</th><th>本檔</th><th>加權指數</th><th>差距</th>" in h, c
            assert "櫃買指數" not in h and "本股" not in h and "承銷價" not in h, c
            assert f"<summary>{PM_SHORT}<i>說明</i></summary>" in h, c
            tip = PM_TIP.get({"R": "L"}.get(c[-1], c[-1]))
            assert (f'</div><div class="muted small">{tip}</div>' in h) if tip else h.count('class="muted small"') == 2, c
        full = PM_FULL.replace("${at('y')}", "2025-12-31").replace("${at('w')}", "2025-11-20")
        assert "<div>" + full.replace(S_EXPR, "") + "</div>" in etf["0050"]                                          # 沒有 s 列
        assert "<div>" + full.replace(S_EXPR, "；上櫃以來從本站第一個成交日 2026-11-19 的收盤起算，不是發行價（本站日線從 2025-10-30 起）") + "</div>" in etf["00986B"]
        assert "<td>上櫃以來<span>11/19 起</span></td>" in etf["00986B"] and "至 11/20，本檔最後成交 11/12</span>" in etf["00986B"]
        assert "<td>上市以來<span>11/19 起</span></td>" in etf["009833"] and "，本檔最後成交" not in etf["0050"]
        assert '<tr><td>5 日</td><td class="num up">+1.27%</td><td class="num dn">-17.50%</td><td class="num up">+18.76</td></tr>' in etf["00679B"]
    except AssertionError:
        return False
    return True


def test_card():
    assert check_card()
    # 位置：K 線卡之後、配息卡之前；股票那一行不動；ETF 版用代號（尾碼提示）
    line = "    ${E && data.epf ? perfHTML(data.epf, data.market, noTrade ? P.d[lt] : null, data.code) : ''}\n"
    assert STK.count(line) == 1
    assert STK.index("${data.pf ? perfHTML(data.pf, data.market, noTrade ? P.d[lt] : null) : ''}\n" + line) < STK.index("${E ? divHTML(data.dv || []")
    assert STK.index('id="mC"') < STK.index(line)
    assert "function perfHTML(pf, mkt, nt, etf = false) {" in STK
    assert len(re.findall(r"noteHTML\((['`])(.+?)\1,", APP + STK)) == 8                                               # test_iter13：短句用變數
    seg = T._grab(STK, "perfHTML")
    for s in (".at(", "replaceAll", "||=", "&&=", "??="):
        assert s not in seg, s


# ─── F46-3：ETF 列表「行情／表現」──────────────────────────
ROWS = {"0050": {"n": "元大台灣50", "m": "TWSE", "c": 84.45, "ch": -5.75, "tv": 748.59, "r20": -21.91, "r60": -19.3, "ry": 31.35, "rw": 39.2},
        "00991A": {"n": "主動A", "m": "TWSE", "c": 10.0, "ch": 0.1, "tv": 1.0, "r20": -40.15, "r60": -41.38, "ry": 2.89},
        "009833": {"n": "新上市", "m": "TWSE", "c": 9.5, "ch": -0.5, "tv": 2.0},
        "00986B": {"n": "債券B", "m": "TPEx", "c": None, "ch": None, "tv": 0, "r20": 3.94, "r60": 0.45, "ry": -0.05, "rw": 1.55}}
IX = {"20": -23.15, "60": -20.32, "y": 24.41, "w": 31.38}


def _list(app=APP):
    js = "\n".join(T._grab(app, n) for n in ("esc", "fmt", "pfmt", "sgn", "cls", "md", "ETF_SORT", "etfDiv", "EPF_COLS", "ETF_PF_NOTE", "holdTag", "etfPerfHTML")) + f"""
const App = {{ latest: {{ date: '2026-11-20', holdings: {{}} }} }};
const rows = {json.dumps(ROWS, ensure_ascii=False)}, list = Object.entries(rows).map(([c, r]) => [c, etfDiv(r, '2026-11-20')]);
const srt = by => {{ const [key, , dir] = ETF_SORT.find(x => x[0] === by); const f = key.replace(/[+-]$/, '');
  return list.slice().sort((a, b) => (a[1][f] == null) - (b[1][f] == null) || dir * ((a[1][f] ?? 0) - (b[1][f] ?? 0))).map(x => x[0]); }};
console.log(JSON.stringify([etfPerfHTML(list, {json.dumps(IX)}), etfPerfHTML(list, {{ '20': -23.15, w: 31.38 }}), etfPerfHTML(list, undefined),
  srt('rw'), srt('r20'), srt('ry'), ETF_PF_NOTE, ETF_SORT.map(x => x[0])]));"""
    return T._node(js)


def check_list(app=APP):
    try:
        assert "  ['r20', '含息 20 日', -1], ['r60', '含息 60 日', -1], ['ry', '含息今年以來', -1], ['rw', '含息 52 週', -1],   // 第 46 輪 F46-3\n" \
               "  ['dvr', '配息率', -1], ['dva', '最近除息', 1]];" in app
        f = app[app.index("function renderEtf()"):app.index("// ─── F7-2")]
        assert "if (perf) keyCol({ r20: 2, r60: 3, ry: 4, rw: 5 }[f]);" in f
        assert f.index("if (perf) keyCol(") < f.index("  else {\n    keyCol({ tv: 4, p: 2, m1: 6, s1: 8, l1: 10, lb: 9 }[f]);\n    keyCol({ dvr: 12, dva: 13 }[f]);")
        assert "${ETF_SORT.filter(x => hasPf || !EPF_COLS.some(c => c[0] === x[0])).map(x =>" in f                    # 舊 latest.json：選單同改前
        assert "perf = hasPf && App.etfCols === 'perf'" in f and "segHTML('etfColSeg', [['flow', '行情'], ['perf', '表現']]" in f
        assert "if (hasPf) onSeg('etfColSeg', v => { App.etfCols = v; renderEtf(); });" in f and "localStore('etfCols'" not in f
        assert "共 ${list.length} 檔。${ETF_PF_NOTE}</div></section>`;" in f
        assert "const hasPf = Object.values(E.rows).some(r => EPF_COLS.some(([k]) => r[k] != null))" in f           # QA46-01：舊資料不顯示欄組
        assert "ETF_SORT.find(x => x[0] === by && (hasPf || !EPF_COLS.some(c => c[0] === x[0]))) || ETF_SORT[0]" in f   # QA46-02
        assert "      ${etfPerfHTML(list, E.ix)}\n      ${more}\n" in f                                              # QA46-01：表現也有「顯示全部」
        o = _list(app)
        if o is None:
            return True
        h, h2, h3, by_w, by_20, by_y, note, keys = o
        assert "共 N 檔。" + note == PM_FOOT
        assert '<div class="muted small" style="margin-bottom:6px">加權指數同期：20 日 -23.15%、60 日 -20.32%、今年以來 +24.41%、52 週 +31.38%（價格指數，不含股息）</div>' in h
        assert "加權指數同期：20 日 -23.15%、52 週 +31.38%（價格指數" in h2 and "加權指數同期" not in h3
        assert "<thead><tr><th>ETF</th><th>收盤</th><th>20 日</th><th>60 日</th><th>今年以來</th><th>52 週</th></tr></thead>" in h
        assert '<td class="num dn">84.45</td><td class="num dn">-21.91%</td><td class="num dn">-19.30%</td><td class="num up">+31.35%</td><td class="num up">+39.20%</td></tr>' in h
        assert '<td class="num up">+2.89%</td><td class="num flat">--</td></tr>' in h                                     # 未滿 52 週
        assert '<td class="num flat">無成交</td><td class="num up">+3.94%</td>' in h and 'class="tbl etf-tbl"' in h
        assert h.count('<tr data-etf="') == 4 and '<tr data-etf="0050"><td class="nm">' in h                       # QA46-01：篩選、點列進 ETF 頁
        assert by_w == ["0050", "00986B", "00991A", "009833"] and by_20 == ["00986B", "0050", "00991A", "009833"] and by_y[-1] == "009833"
        assert keys.index("rw") < keys.index("dvr") and len(keys) == 14
    except (AssertionError, ValueError):
        return False
    return True


def test_list():
    assert check_list()
    f = APP[APP.index("function renderEtf()"):APP.index("function renderWatch()")]
    assert "自選" not in f.split('<div class="muted small" style="margin-top:6px">共 ')[1].split("</div>")[0]   # test_iter20
    assert "自選" not in PM_FOOT


# ─── 用詞、版本、文件 ──────────────────────────────────────
def check_words(stk=STK, app=APP):
    seg = T._grab(stk, "perfHTML") + T._grab(app, "ETF_PF_NOTE") + T._grab(app, "etfPerfHTML") + T._grab(app, "ETF_SORT")
    seg += "".join(l for l in README.splitlines() if "第 46 輪" in l)
    return all(w not in seg.replace("借券賣出", "") for w in ADVICE)


def test_words():
    assert check_words()


def test_version_and_docs():
    for f in ("app.js", "stock.js", "app.css", "tools.js", "help.js"):
        v = hashlib.sha1((SITE / f).read_bytes()).hexdigest()[:8]
        assert f"{f}?v={v}" in HTML, f"index.html 要改成 {f}?v={v}"
    assert "python3 tests/test_iter46.py" in README
    r = next(l for l in README.splitlines() if l.startswith("- ETF 近期表現（第 46 輪"))
    for s in ("`epf`", "`r20`", "`etfs.ix`", "參考價 ÷ 除息前收盤", "加權指數", "價格指數", "上櫃"):
        assert s in r, s
    assert "第 23 輪" not in r
    assert "第 46 輪" in (ROOT / "docs" / "iterations" / "README.md").read_text(encoding="utf-8")


# ─── 反證：原始碼改壞，對應的檢查要失敗 ─────────────────────────
def _mut_fn(old, new):
    src = inspect.getsource(export.etf_perf)
    assert src.count(old) == 1, old
    ns = dict(vars(export))
    exec(src.replace(old, new), ns)
    return ns["etf_perf"]


MUTANTS = [
    ("上櫃不防呆", "fn", 'market == "TPEx" and', 'False and'),
    ("防呆也套用上市", "fn", 'market == "TPEx" and', 'market in ("TPEx", "TWSE") and'),
    ("啟用上櫃反推", "fn", '_price_events(d_, c, ch, "TWSE", ev)', '_price_events(d_, c, ch, market, ev)'),
    ("不採用推測調整", "fn", "if str(d_[i]) in gx - ex]", "if False]"),
    ("防呆門檻改 40%", "fn", "> 0.30", "> 0.40"),
    ("epf 放在 _write 之後", "src", '            _write(p, E)\n', '            _write(p, E)\n            E["epf"] = epf\n'),
    ("對照用各市場指數", "src", 'idx_close["TWSE"], w52_start)) is not None:', 'idx_close[m], w52_start)) is not None:'),
    ("ETF 表頭寫櫃買指數", "stk", "const ix = mkt === 'TWSE' || etf ? '加權指數' : '櫃買指數'", "const ix = mkt === 'TWSE' ? '加權指數' : '櫃買指數'"),
    ("拿掉尾碼提示", "stk", "${tip ? `<div class=\"muted small\">${tip}</div>` : ''}", ""),
    ("R 尾碼沒有提示", "stk", "[etf.slice(-1).replace('R', 'L')]", "[etf.slice(-1)]"),
    ("ETF 標題右側寫本股", "stk", "me = etf ? '本檔' : '本股'", "me = '本股'"),
    ("股票版輸出改變", "stk", "`，${me}最後成交 ${md(nt)}`", "`，${me}最後成交日 ${md(nt)}`"),
    ("ETF 版用承銷價", "stk", "的收盤起算，不是發行價（本站日線從 2025-10-30 起）", "的收盤起算，不是承銷價（本站日線從 2025-10-30 起）"),
    ("表現表套用行情 keyCol", "app", "  if (perf) keyCol({ r20: 2, r60: 3, ry: 4, rw: 5 }[f]);", "  keyCol({ r20: 2, r60: 3, ry: 4, rw: 5 }[f]);"),
    ("欄組寫入 localStorage", "app", "v => { App.etfCols = v; renderEtf(); }", "v => { App.etfCols = v; localStore('etfCols', null, v); renderEtf(); }"),
    ("舊資料也列新排序", "app", "ETF_SORT.filter(x => hasPf || !EPF_COLS.some(c => c[0] === x[0])).map(", "ETF_SORT.map("),
    ("缺值顯示 0", "app", "${v == null ? '--' : sgn(v) + '%'}</td>`;\n  const line", "${sgn(v ?? 0) + '%'}</td>`;\n  const line"),
    ("無成交顯示 --", "app", "'<td class=\"num flat\">無成交</td>'", "'<td class=\"num flat\">--</td>'"),
    ("新排序插在 dvr 那一行", "app", "['rw', '含息 52 週', -1],   // 第 46 輪 F46-3\n  ['dvr'", "['rw', '含息 52 週', -1], ['dvr'"),
    ("頁尾和 PM 不同", "app", "不含手續費與稅；", "不含手續費；"),
    ("用詞", "app", "比較的意義有限。';", "比較的意義有限，不是建議。';"),
    ("QA 列表欄缺值也輸出", "src", "if k in EPF_KEYS and r is not None:", "if k in EPF_KEYS:"),
    ("QA 舊資料也顯示欄組", "app", "const hasPf = Object.values(E.rows).some(r => EPF_COLS.some(([k]) => r[k] != null))", "const hasPf = true"),
    ("QA 表現表列不能點", "app", "list.map(([c, r]) => `<tr data-etf=\"${c}\"><td class=\"nm\"><b>${esc(r.n)}</b><span>${c} ${r.m === 'TWSE' ? '上市' : '上櫃'}</span>${holdTag(c)}</td>\n      ${r.c == null", "list.map(([c, r]) => `<tr><td class=\"nm\"><b>${esc(r.n)}</b><span>${c} ${r.m === 'TWSE' ? '上市' : '上櫃'}</span>${holdTag(c)}</td>\n      ${r.c == null"),
    ("QA 表現沒有顯示全部", "app", "      ${etfPerfHTML(list, E.ix)}\n      ${more}\n", "      ${etfPerfHTML(list, E.ix)}\n"),
    ("QA 舊資料沿用含息排序", "app", "x[0] === by && (hasPf || !EPF_COLS.some(c => c[0] === x[0])))", "x[0] === by)"),
]


def test_contrast():
    node = T._node("console.log('1')") is not None
    for name, kind, a, b in MUTANTS:
        if kind == "fn":
            assert not check_perf(_mut_fn(a, b)), "反證沒有擋下：" + name
            continue
        src = {"src": SRC, "stk": STK, "app": APP}[kind]
        assert src.count(a) == 1, (name, a)
        bad = src.replace(a, b)
        if kind == "src":
            ok = check_wiring(bad)
        elif kind == "stk":
            ok = check_card(bad) and check_words(stk=bad) if node else True
        else:
            ok = check_list(bad) and check_words(app=bad)
        assert not ok or not node, "反證沒有擋下：" + name


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_") and callable(f):
            print("==", n); f()
    print("全部通過")
