"""
第 29 輪（不連網、不連資料庫）：
F29-1～3 籌碼分頁法人圖：選一種法人的每日買賣超柱（預設外資）＋同一法人的區間累計小面板（標題寫起算日、跨年寫年份），預設 20 日，
         不新增 localStorage 鍵（有 node 時逐字取出 stock.js 的 buildChip 執行）；
F29-4 外資及陸資持股：MI_QFIIS（上市）、insti/qfii（上櫃）解析（日期不符＝尚未公布、欄位不符、只留股票）、DDL、資料集鍵與 check、
      收集（行情保護、尚未公布）、history --only qfii、匯出 fh（對齊 prices.d）、個股頁卡片與持股比率圖。
fixture：tests/fixtures/mi_qfiis_20261116_mini.json、insti_qfii_20261116_mini.json（官方原始回應的精簡版：欄位不變，只留幾列）。

  python3 tests/test_iter29.py      （也相容 pytest）
"""
import contextlib
import inspect
import io
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_iter03 as t3  # noqa: E402
import test_iter28 as t28  # noqa: E402
from twstock import db, export, health  # noqa: E402
from twstock.collectors import daily, history  # noqa: E402
from twstock.fetch import SchemaError  # noqa: E402

D = t3.D
FIX = Path(__file__).resolve().parent / "fixtures"
ROOT = Path(__file__).resolve().parent.parent
load = lambda name: json.loads((FIX / name).read_text(encoding="utf-8"))
TW, OT = load("mi_qfiis_20261116_mini.json"), load("insti_qfii_20261116_mini.json")
N16 = date(2026, 11, 16)
STK, CSS = t28.STK, t28.CSS


# ─── F29-1～3：原始碼 ──────────────────────────────────
def test_chip_source():
    assert "let chipN = '20';" in STK and "localStore('chipN'" not in STK                         # F29-3 預設 20 日
    assert "const CHIP_I = [['f', '外資'], ['t', '投信'], ['dl', '自營'], ['net', '合計']];" in STK
    assert "let chipI = 'f';" in STK and "localStore('chipI'" not in STK                          # 預設外資，只在這次瀏覽記住
    assert "segHTML('chipInv', CHIP_I, chipI)" in STK
    assert "  if (tab === 'chip' && $('#chipInv')) onSeg('chipInv', v => { chipI = v;" in STK            # 切換有綁定（QA29-01 補強）
    assert "chLeg('每日買賣超（張，未還原）', 'ciC', 120)" in STK and "'cuC', 72)" in STK
    assert "累計線的高度取決於起算日，看斜率不看高度；最近每天的買賣看上方柱狀圖。" in STK             # F29-2 讀法
    assert ".chip-inv{margin:8px 0 0}" in CSS


def _run(chipN, chipI, data, extra=""):
    js = t28.HELPERS + "\n" + "\n".join(t28._grab(STK, n) for n in ("INVESTORS", "CHIP_I", "disposeKCharts", "adjFactors", "aggregate", "buildChip")) + r"""
let charts = [], chipN = '%s', chipI = '%s';
const css = v => v, created = [], els = {};
const $ = s => s in els ? els[s] : (els[s] = { innerHTML: '', textContent: '' });
const window = { LightweightCharts: { createChart: (el, opt) => {
  const c = { el, opt, ser: [], addHistogramSeries(o) { return this.addLineSeries(Object.assign({ hist: true }, o)); },
    addLineSeries(o) { const s = { o, setData(d) { this.data = d; }, createPriceLine(p) { this.pl = p; } }; this.ser.push(s); return s; },
    timeScale: () => ({ fitContent() {} }), subscribeCrosshairMove(f) { this.cb = f; }, setCrosshairPosition(v, t) { this.cross = [v, t]; },
    clearCrosshairPosition() { this.cross = null; }, remove() {} };
  created.push(c); return c; } } };
const data = %s;
%s
buildChip(data, false);
const id = c => Object.keys(els).find(k => els[k] === c.el);
console.log(JSON.stringify({ ids: created.map(id), ser: created.map(c => c.ser.map(s => ({ hist: !!s.o.hist, v: s.data.map(p => p.value ?? null), col: s.data.map(p => p.color || null) }))),
  ci: els['#ciCL'].innerHTML, cu: els['#cuCL'].innerHTML, cuT: els['#cuCT'].textContent, fh: els['#fhCL'] ? els['#fhCL'].innerHTML : null }));""" % (chipN, chipI, json.dumps(data), extra)
    return t28._node(js)


DATES = ['2025-12-30', '2025-12-31', '2026-01-02', '2026-01-05', '2026-01-06']
DATA = {"market": "TWSE", "prices": {"d": DATES, "o": [10] * 5, "h": [10] * 5, "l": [10] * 5, "c": [10, 11, 12, 13, 14], "v": [1] * 5, "ch": [0, 1, 1, 1, 1]},
        "insti": {"f": [10, -20, 30, 5, -4], "t": [1, 2, 0, -3, 1], "dl": [0, 0, 0, -2, 0], "n": [11, -18, 30, 0, -5]}, "ev": []}


def test_chip_bars_node():
    o = _run("all", "f", DATA)
    if o is None:
        return
    assert o["ids"] == ["#cpC", "#ciC", "#cuC", "#cmC", "#clC"], o["ids"]       # 沒有 fh：不畫持股比率圖
    bar, cum = o["ser"][1][0], o["ser"][2][0]
    assert bar["hist"] and bar["v"] == [10, -20, 30, 5, -4] and bar["col"] == ["--up", "--dn", "--up", "--up", "--dn"]   # 每日柱：正紅負綠
    assert not cum["hist"] and cum["v"] == [10, -10, 20, 25, 21]                                                     # 區間累計
    assert o["cuT"] == "區間累計（張，自 2025/12/30 起加總）"                                                         # 跨年寫年份
    assert '外資 <b class="num dn">-4</b>' in o["ci"] and '累計 <b class="num up">+21</b>' in o["cu"]
    o = _run("2", "net", DATA)                                    # 合計用官方 n（最後一天 -5，三者相加是 -3；QA29-01 補強）、近 2 日
    assert o["ser"][1][0]["v"] == [0, -5] and o["ser"][2][0]["v"] == [0, -5] and o["cuT"] == "區間累計（張，自 01/05 起加總）"
    assert '合計 <b class="num dn">-5</b>' in o["ci"]
    o = _run("3", "t", DATA)
    assert o["ser"][1][0]["v"] == [0, -3, 1] and o["ser"][2][0]["v"] == [0, -3, -2] and '投信 <b class="num up">+1</b>' in o["ci"]


def test_fh_chart_node():
    data = dict(DATA, fh=[None, 30.5, 30.75, None, 31.2])
    o = _run("all", "f", data, "els['#fhC'] = { innerHTML: '' };")
    if o is None:
        return
    assert o["ids"] == ["#cpC", "#ciC", "#cuC", "#fhC", "#cmC", "#clC"], o["ids"]
    assert o["ser"][3][0]["v"] == [None, 30.5, 30.75, None, 31.2]                                    # 缺值不補
    assert '外資持股 <b class="num">31.20%</b>' in o["fh"]


# ─── F29-4：解析 ───────────────────────────────────────
def test_parse_twse():
    rows = daily.parse_qfii(TW, N16, "TWSE")
    by = {r["stock_code"]: r for r in rows}
    assert len(rows) == 6 and "0050" in by and "00400A" in by                     # 含 ETF，由呼叫端只留股票
    assert by["2421"] == {"stock_code": "2421", "issued": 286943669, "fh_shares": 103759627, "fh_ratio": 36.16, "avail_ratio": 63.83, "limit_ratio": 100.0}
    assert by["2330"]["fh_ratio"] == 68.06
    assert daily.parse_qfii(TW, date(2026, 11, 13), "TWSE") == []                # 回應日期不是 d → 尚未公布
    assert daily.parse_qfii({"stat": "很抱歉，沒有符合條件的資料!"}, N16, "TWSE") == []
    bad = json.loads(json.dumps(TW))
    bad["fields"][7] = "持股比率"
    try:
        daily.parse_qfii(bad, N16, "TWSE")
        assert False
    except SchemaError as e:
        assert "7:全體外資及陸資持股比率" in str(e)


def test_parse_tpex():
    rows = daily.parse_qfii(OT, N16, "TPEx")
    by = {r["stock_code"]: r for r in rows}
    assert set(by) == {"8455", "3105", "6488", "8349A"}                           # 第 0 欄是排行，代號在第 1 欄
    assert by["6488"] == {"stock_code": "6488", "issued": 528113725, "fh_shares": 157789488, "fh_ratio": 29.87, "avail_ratio": 70.12, "limit_ratio": 100.0}
    assert daily.parse_qfii(OT, date(2026, 11, 13), "TPEx") == []
    assert daily.parse_qfii({"date": "20261116", "stat": "ok", "tables": [{"fields": OT["tables"][0]["fields"], "data": []}]}, N16, "TPEx") == []


# ─── F29-4：資料表、資料集、check、history ─────────────────
def test_keys_and_ddl():
    src = "\n".join(db.DDL)
    assert "IF OBJECT_ID('foreign_holdings') IS NULL" in src and "CONSTRAINT UQ_foreign_holdings UNIQUE (stock_id, trade_date)" in src
    assert "fh_ratio     DECIMAL(6,2)  NOT NULL" in src and "IX_foreign_holdings_date" in src
    assert daily.DATASET_KEYS["qfii"] == ("qfii.TWSE", "qfii.TPEx") and "qfii" not in daily.ALL_DATASETS     # 只有 --only qfii 才補
    k = list(daily.DAY_KEYS)
    assert k.index("sbl.TPEx") < k.index("qfii.TWSE") < k.index("qfii.TPEx") < k.index("breadth.TWSE")
    assert health.SPEC["qfii.TWSE"].min_rows == 800 and health.SPEC["qfii.TPEx"].min_rows == 650
    assert "foreign_holdings x" in health._MARKET_SQL["qfii"]
    assert set(history.SECONDS_PER_KEY) >= {"qfii.TWSE", "qfii.TPEx"}
    assert "WHEN MATCHED THEN UPDATE SET" in inspect.getsource(daily.merge_qfii)         # 同一天重抓 = 覆寫（QA29-03 補強）
    main = (ROOT / "twstock" / "__main__.py").read_text(encoding="utf-8")
    assert '"qfii"' in main and "--only qfii" in main and "qfii = 外資及陸資持股" in main


# ─── F29-4：收集 ───────────────────────────────────────
def test_collect():
    w = t3.World(D(10, 30))
    w.publish(D(11, 2))
    with t3.env(w), contextlib.redirect_stdout(io.StringIO()):
        written, errors = daily.collect_for_date(D(11, 2), ("prices.TWSE", "prices.TPEx", "qfii.TWSE", "qfii.TPEx"))
    assert errors == {} and written["qfii.TWSE"] == written["prices.TWSE"] and written["qfii.TPEx"] == written["prices.TPEx"]   # 只留股票（ETF、其他證券略過）
    assert w.merges.count("foreign_holdings") == 2 and len(t3._hit(w, "MI_QFIIS")) == 1 and len(t3._hit(w, "insti/qfii")) == 1
    # 行情 0 列（尚未公布）→ 不發外資持股請求；外資持股尚未公布 → 0 筆、不是錯誤
    w2 = t3.World(D(10, 30))
    w2.publish(D(11, 2), "MI_INDEX", "MI_QFIIS")
    with t3.env(w2), contextlib.redirect_stdout(io.StringIO()):
        written, errors = daily.collect_for_date(D(11, 2), ("prices.TWSE", "prices.TPEx", "qfii.TWSE", "qfii.TPEx"))
    assert written["prices.TWSE"] == 0 and "qfii.TWSE" not in written and t3._hit(w2, "MI_QFIIS") == []
    w2.published["insti/qfii"].discard(D(11, 2))
    with t3.env(w2), contextlib.redirect_stdout(io.StringIO()):
        written, errors = daily.collect_for_date(D(11, 2), ("prices.TPEx", "qfii.TPEx"))
    assert errors == {} and written["qfii.TPEx"] == 0


# ─── F29-4：匯出與畫面 ─────────────────────────────────
def test_export_source():
    src = (ROOT / "twstock" / "export.py").read_text(encoding="utf-8")
    assert "def _load_qfii(cur):" in src and "fh = _load_qfii(cur)" in src
    assert '**({"fh": [fhr.get(x) for x in d_]} if (fhr := fh.get(code)) else {}),' in src     # 對齊 prices.d；沒有資料不輸出

    class Cur:
        def execute(self, sql):
            assert "x.trade_date, x.fh_ratio FROM foreign_holdings x JOIN stocks s" in sql      # 匯出的是持股比率（QA29-03 補強）
            return [("2421", N16, 36.16), ("2421", date(2026, 11, 13), 36.2), ("6488", N16, 29.87)]
    out = export._load_qfii(Cur())
    assert out == {"2421": {N16: 36.16, date(2026, 11, 13): 36.2}, "6488": {N16: 29.87}}


def test_fh_card_node():
    """QA29-03 補強：逐字取出卡片的 fj／fhd 執行：最近有值那天（跳過尾端 null）、往前 5／20 筆的差（百分點）、前面不夠或為 null 時 --。"""
    seg = STK[STK.index("const FH = data.fh"):STK.index("const inCards")]
    fh = [30 + i / 10 for i in range(24)] + [None]                  # 25 筆，最後一筆沒有資料；fj = 23（32.30）
    fh[3] = None                                                    # 20 日前（23 − 20 = 3）是 null → --
    js = t28.HELPERS + "\nconst data = %s;\n" % json.dumps({"fh": fh}) + seg + \
        "\nconsole.log(JSON.stringify({ fj, v: FH[fj], d5: fhd(5), d20: fhd(20), d1: fhd(1), d30: fhd(30) }));"
    o = t28._node(js)
    if o is None:
        return
    assert o == {"fj": 23, "v": 32.3, "d5": "+0.50", "d20": "--", "d1": "+0.10", "d30": "--"}, o
    fh[3] = 29.0
    o = t28._node(t28.HELPERS + "\nconst data = %s;\n" % json.dumps({"fh": fh}) + seg + "\nconsole.log(JSON.stringify({ d20: fhd(20) }));")
    assert o == {"d20": "+3.30"}, o


def test_fh_card_source():
    assert "['外資持股比率', fmt(FH[fj], 2) + '%', '', subs(`5日 ${fhd(5)}　20日 ${fhd(20)}（百分點）`, md(P.d[fj]) !== fd ? md(P.d[fj]) : '')]" in STK
    assert "(FH ? chLeg('外資及陸資持股比率（%，以當日發行股數為分母，增資、減資時會跳動）', 'fhC', 90) : '')" in STK
    assert "if (data.fh && $('#fhC'))" in STK


def test_no_advice_words():
    seg = "\n".join(t28._grab(STK, n) for n in ("CHIP_I", "buildChip"))
    seg += STK[STK.index("// 第 29 輪 F29-4：外資及陸資持股比率（最近有資料的那天"):STK.index("const chipSec")]
    for w in ("買進", "賣出", "反彈", "見底", "買點", "超賣", "超買", "推薦", "強勢股", "飆股", "勝率", "亮點", "低估", "高估", "建議"):
        assert w not in seg.replace("借券賣出", ""), w


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            print("==", name)
            fn()
            print("✅", name)
    print("全部通過")
