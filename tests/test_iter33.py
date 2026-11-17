"""第 33 輪（不連網、不連資料庫）：F33-1 週／月 K 事件文字改自繪標籤（有底色、避開標籤寬度範圍內的上影線、相近時錯開一層）。
有 node 時逐字取出 stock.js 的 evLabelPos 執行（node 14 可跑：不用 .at()、replaceAll）。"""
import json
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STK = (ROOT / "site" / "stock.js").read_text(encoding="utf-8")
CSS = (ROOT / "site" / "app.css").read_text(encoding="utf-8")


def _grab(src, name):
    m = re.search(rf"^function {name}\(", src, re.M)
    i, n = src.index("{", src.index(")", m.start())), 0
    for j in range(i, len(src)):
        n += {"{": 1, "}": -1}.get(src[j], 0)
        if n == 0:
            return src[m.start():j + 1]


def _node(js):
    node = shutil.which("node")
    if not node:
        print("  （沒有 node，略過執行）")
        return None
    return json.loads(subprocess.run([node, "-e", js], capture_output=True, text=True, check=True).stdout)


def _pos(cases):
    return _node(_grab(STK, "evLabelPos") + f"\nconsole.log(JSON.stringify({json.dumps(cases)}.map(([items, W, bars]) => evLabelPos(items, W, bars))));")


# ─── 位置計算（純函式）────────────────────────────────────
def test_label_position():
    o = _pos([
        [[{"x": 100, "top": 80, "w": 40}], 300],                                  # 置中、底邊對齊 top
        [[{"x": 5, "top": 80, "w": 40}, {"x": 298, "top": 80, "w": 40}], 300],    # 靠左、靠右往內收 2 px
        [[{"x": None, "top": 80, "w": 40}, {"x": -3, "top": 80, "w": 40}, {"x": 301, "top": 80, "w": 40}, {"x": 50, "top": None, "w": 40}], 300],   # 不在可見範圍
        [[{"x": 100, "top": 10, "w": 40}], 300],                                  # 碰到上緣貼齊 0
    ])
    if o is None:
        return
    assert o[0] == [{"left": 80, "top": 62}]
    assert o[1] == [{"left": 2, "top": 62}, {"left": 258, "top": 62}]
    assert o[2] == [None, None, None, None]
    assert o[3] == [{"left": 80, "top": 0}]


def test_label_stacking():
    o = _pos([
        [[{"x": 100, "top": 80, "w": 40}, {"x": 120, "top": 80, "w": 40}], 300],                                  # 重疊 → 往上一層（18 + 2）
        [[{"x": 100, "top": 80, "w": 40}, {"x": 120, "top": 80, "w": 40}, {"x": 140, "top": 80, "w": 40}], 300],  # 第三個還重疊 → 不顯示
        [[{"x": 100, "top": 80, "w": 40}, {"x": 144, "top": 80, "w": 40}], 300],                                  # 間隔 4 px 不算重疊
        [[{"x": 100, "top": 80, "w": 40}, {"x": 143, "top": 80, "w": 40}], 300],                                  # 間隔 3 px（不到 4）算重疊
        [[{"x": 100, "top": 10, "w": 40}, {"x": 120, "top": 10, "w": 40}], 300],                                  # 貼上緣時沒有地方往上 → 不顯示
        [[{"x": 100, "top": 80, "w": 40}, {"x": 120, "top": 140, "w": 40}], 300],                                 # 高度錯開就不重疊
    ])
    if o is None:
        return
    assert o[0] == [{"left": 80, "top": 62}, {"left": 100, "top": 42}]
    assert o[1] == [{"left": 80, "top": 62}, {"left": 100, "top": 42}, None]
    assert o[2][1] == {"left": 124, "top": 62}
    assert o[3][1] == {"left": 123, "top": 42}
    assert o[4] == [{"left": 80, "top": 0}, None]
    assert o[5] == [{"left": 80, "top": 62}, {"left": 100, "top": 122}]


def test_label_bars():
    # QA D33-QA-1：標籤寬度範圍內任何一根 K 棒的最高點都要在標籤之下（不只左右各 2 根）
    o = _pos([
        [[{"x": 100, "top": 80, "w": 40}], 300, [{"l": 60, "r": 70, "y": 10}, {"l": 115, "r": 125, "y": 50}]],   # 範圍外的高 K 棒不管；範圍內的 → 底邊 50 − 2
        [[{"x": 100, "top": 80, "w": 40}], 300, [{"l": 120, "r": 126, "y": 10}, {"l": 74, "r": 80, "y": 10}]],   # 剛好碰到邊不算
        [[{"x": 5, "top": 80, "w": 40}], 300, [{"l": 30, "r": 36, "y": 40}]],                                    # 靠左往內收後，用收進去的範圍找
        [[{"x": 100, "top": 80, "w": 40}], 300, [{"l": 95, "r": 105, "y": 10}]],                                 # 太高就貼齊上緣
        [[{"x": 100, "top": 80, "w": 40}, {"x": 120, "top": 80, "w": 40}], 300, [{"l": 95, "r": 105, "y": 60}]], # 錯開一層也從新的底邊算
        [[{"x": 100, "top": 50, "w": 40}, {"x": 130, "top": 64, "w": 40}], 300],                                 # 後面那個比較低：放到相撞標籤的上方一層，不是固定往上 20 px
    ])
    if o is None:
        return
    assert o[0] == [{"left": 80, "top": 30}]
    assert o[1] == [{"left": 80, "top": 62}]
    assert o[2] == [{"left": 2, "top": 20}]
    assert o[3] == [{"left": 80, "top": 0}]
    assert o[4] == [{"left": 80, "top": 40}, {"left": 100, "top": 20}]
    assert o[5] == [{"left": 80, "top": 32}, {"left": 110, "top": 12}]


# ─── 接到 K 線圖 ─────────────────────────────────────────
def test_wiring():
    b = _grab(STK, "buildCharts")
    # 舊測試鎖定的內容照舊（test_iter23:250-251、test_iter19:151、test_iter14:91）
    assert "const mkPos = mode === '日' ? { position: 'belowBar', shape: 'arrowUp' } : { position: 'aboveBar', shape: 'arrowDown' };" in b
    assert b.count("{ time: T[i], ...mkPos,") == 2 and "kSer.setMarkers(" in b
    assert "const evText = r => [...new Set(r.ev.map(e => (mode === '日' ? '' : mdn(e.d) + ' ') + evMark(e)))].join('・');" in b
    # 日 K 文字照舊；週／月 K 的 setMarkers 不寫文字（只留箭頭）
    assert "text: mode === '日' ? evText(r) : '' }]" in b and "text: mode === '日' ? r.gx : '' }]" in b
    # 只有週／月 K 建標籤；ETF 推測標記同規則（另一個 class）；文字跳脫
    assert "const tags = mode === '日' ? [] : raw.flatMap((r, i) => r.ev.length || r.gx ? [[i, r.ev.length ? evText(r) : r.gx, !r.ev.length]] : []);" in b
    assert '`<span class="ev-lbl${g ? \' gx\' : \'\'}">${esc(t)}</span>`' in b
    # 重畫前清掉上一次的標籤；圖已釋放就不再定位
    assert b.index("$('#kC .ev-lbls')?.remove();") < b.index("if (!raw.length || !window.LightweightCharts) return;")
    assert "if (!lay.isConnected || !charts.includes(kc)) return;" in b
    # 事件那根的箭頭之上；標籤寬度範圍內每根 K 棒的最高價（範圍 = K 棒中心 ± 半個間距）；繪圖區寬 = 容器寬 − 右側刻度寬
    assert "top: y(H[i]) - 18 }))" in b and "H.slice(" not in b
    assert "const s = ts.options().barSpacing / 2, bars = T.flatMap((d, j) => { const x = ts.timeToCoordinate(d); return x == null ? [] : [{ l: x - s, r: x + s, y: y(H[j]) }]; });" in b
    assert "lay.clientWidth - kc.priceScale('right').width(), bars)" in b
    # 捲動、縮放、改變寬度、十字線移動後重新定位（等圖表重畫完）
    assert "ts.subscribeVisibleLogicalRangeChange(later); ts.subscribeSizeChange(later); kc.subscribeCrosshairMove(later); later();" in b
    assert "requestAnimationFrame(() => requestAnimationFrame(place))" in b
    assert "st.visibility = p ? '' : 'hidden'" in b and "st.display" not in b   # display:none 會讓寬度量成 0


def test_css():
    assert ".chart-box{width:100%;cursor:grab;position:relative}" in CSS
    assert ".ev-lbls{position:absolute;inset:0;pointer-events:none;z-index:3;overflow:hidden}" in CSS     # 不擋拖曳、十字線
    lbl = re.search(r"\.ev-lbl\{[^}]*\}", CSS).group(0)
    assert "box-sizing:border-box" in lbl and "height:18px" in lbl                 # 和 evLabelPos 的 h = 18 一致
    assert "background:var(--card)" in lbl and "color:var(--blue)" in lbl and ".ev-lbl.gx{color:var(--text2)}" in CSS


# ─── 第 33 輪補充：自選頁的 1日／5日 移到資金表格說明列（切換欄位組時標題列按鈕不移位）──
def test_watch_span_in_caption():
    import test_iter32 as t32                                   # 沿用第 32 輪的 renderWatch 測試架構
    o = t32._node(t32._js(f"""
const S = {json.dumps(t32.SCREEN, ensure_ascii=False)};
const w = ['2330', '2317'];
console.log(JSON.stringify({{ flow: run(w, {{ screen: S, watchCols: 'flow' }}), perf: run(w, {{ watchCols: 'perf' }}), fund: run(w, {{ watchCols: 'fund' }}),
  none: run([], {{ watchCols: 'flow' }}), rank: stockTable([['2330', App.latest.stocks['2330']]], '1') }}));"""))
    if o is None:
        return
    head = lambda h: re.sub(r' class="(on)?"', '', h.split('<div class="sec-h">', 1)[1].split('<div class="card">', 1)[0])
    # 三種欄位組的標題列完全相同（只差選中的鈕），而且都沒有 1日／5日
    assert head(o["flow"]) == head(o["perf"]) == head(o["fund"]) and "rspanSeg" not in head(o["flow"])
    # 資金：1日／5日在表格說明列；表現、基本面沒有
    f = o["flow"]
    assert '<div class="cap-row"><div class="seg" id="rspanSeg">' in f and '</div><div class="muted small tbl-cap">法人欄位為 11/17 當日買賣超（億）</div></div>' in f   # 放最左邊：說明變長也不移位
    assert f.index('id="rspanSeg"') < f.index('<div class="tbl-wrap">') and "rspanSeg" not in o["perf"] + o["fund"]
    # 沒有自選股時照舊在標題列（test_iter20）；排行頁的表格不加
    assert "rspanSeg" in head(o["none"]) and "cap-row" not in o["rank"] and "rspanSeg" not in o["rank"]
    assert "if ($('#rspanSeg')) onSeg('rspanSeg'," in t32.APP                     # 有這個鈕才綁定
    assert ".cap-row{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:6px}" in t32.CSS


def test_no_advice_words():
    seg = _grab(STK, "evLabelPos") + "".join(l for l in STK.splitlines() + CSS.splitlines() if "第 33 輪" in l)
    for w in ("買進", "賣出", "反彈", "見底", "買點", "超賣", "超買", "推薦", "強勢", "飆股", "勝率", "亮點", "建議", "低估", "高估"):
        assert w not in seg, w


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_") and callable(f):
            print("==", n); f()
    print("全部通過")
