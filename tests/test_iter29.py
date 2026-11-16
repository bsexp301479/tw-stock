"""
第 29 輪（不連網、不連資料庫）：
F29-1～3 籌碼分頁法人圖：選一種法人的每日買賣超柱（預設外資）＋同一法人的區間累計小面板（標題寫起算日、跨年寫年份），預設 20 日，
         不新增 localStorage 鍵（有 node 時逐字取出 stock.js 的 buildChip 執行）；
（F29-4 外資持股的測試在階段二加入。）

  python3 tests/test_iter29.py      （也相容 pytest）
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_iter28 as t28  # noqa: E402

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


def test_no_advice_words():
    seg = "\n".join(t28._grab(STK, n) for n in ("CHIP_I", "buildChip"))
    for w in ("買進", "賣出", "反彈", "見底", "買點", "超賣", "超買", "推薦", "強勢股", "飆股", "勝率", "亮點", "低估", "高估", "建議"):
        assert w not in seg.replace("借券賣出", ""), w


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            print("==", name)
            fn()
            print("✅", name)
    print("全部通過")
