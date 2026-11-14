"""第 25 輪 QA 後修正（不連網、不連資料庫）：
QA25-01 自選移除／復原在 #view 累積多個點擊監聽時只執行一次、QA25-02「清」標記有底色、個股頁產業鏈／概念股標籤可展開也可收合。
有 node 時，逐字取出 app.js 的 onRowClick、stock.js 的 tagFold 執行。"""
import json
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "site" / "app.js").read_text(encoding="utf-8")
STK = (ROOT / "site" / "stock.js").read_text(encoding="utf-8")
CSS = (ROOT / "site" / "app.css").read_text(encoding="utf-8")


def _grab(src, name):
    m = re.search(rf"^(?:async )?function {name}\(", src, re.M)
    if m:
        i, n = src.index("{", src.index(")", m.start())), 0
        for j in range(i, len(src)):
            n += {"{": 1, "}": -1}.get(src[j], 0)
            if n == 0:
                return src[m.start():j + 1]
    m = re.search(rf"^const {name}\b.*$", src, re.M)
    assert m, name
    return m.group(0)


def _node(js):
    node = shutil.which("node")
    if not node:
        return None
    return json.loads(subprocess.run([node, "-e", js], capture_output=True, text=True, check=True).stdout)


def test_unwatch_undo_once():
    """主動 ETF 彙總頁進過 2 次後（#view 上有 onRowClick 與 2 個匿名監聽），移除、復原都只生效一次，清單不會被清空。"""
    js = _grab(APP, "onRowClick") + """
const App = { watch: new Set(['2330', '2421', '0050']), watchUndo: null };
let saved = [];
const saveWatch = () => saved.push([...App.watch]), renderWatch = () => {};
const listeners = [onRowClick, e => onRowClick(e), e => onRowClick(e)];   // 對應 app.js 累積的監聽
function fire(target) {
  const e = { target, stop: false, stopImmediatePropagation() { this.stop = true; } };
  for (const f of listeners) { f(e); if (e.stop) break; }
}
const el = attr => ({ dataset: { unwatch: attr }, closest: s => s === '[data-unwatch]' ? (attr ? { dataset: { unwatch: attr } } : null)
  : s === '#watchUndo' ? (attr ? null : {}) : null });
fire(el('2421'));
const afterRm = { w: [...App.watch], u: App.watchUndo };
fire(el(null));
const afterUndo = [...App.watch];
fire(el(null));                                  // 再按一次復原（已無可復原）也不會清空
console.log(JSON.stringify({ afterRm, afterUndo, again: [...App.watch], n: saved.length }));"""
    o = _node(js)
    if o is None:
        print("  （沒有 node，略過執行）")
        assert "e.stopImmediatePropagation()" in _grab(APP, "onRowClick")
        return
    assert o["afterRm"] == {"w": ["2330", "0050"], "u": ["2330", "2421", "0050"]}, o
    assert o["afterUndo"] == ["2330", "2421", "0050"], o
    assert o["again"] == ["2330", "2421", "0050"], o
    assert o["n"] == 3, o                                                        # 每次點擊只存一次


def test_out_tag_has_background():
    assert '.al:not([class*="al-"]){background:var(--flat)}' in CSS
    assert "<i class=\"al\">清</i>" in APP                                       # 「清」沒有類別，靠上一條規則取得底色


def test_tag_fold_toggle():
    seg = _grab(STK, "tagFold")
    assert seg.index("tag-rest") < seg.index('id="tagMore"')                       # 收合鈕在展開內容之後
    line = next(l for l in STK.splitlines() if "$('#tagMore')" in l)
    assert "r.hidden = !r.hidden" in line and "收合" in line and "b.dataset.n" in line
    assert ".remove()" not in line                                               # 展開後按鈕仍在，可以收回
    o = _node(seg + "\nconsole.log(JSON.stringify([tagFold(['a','b']), tagFold(['a','b','c','d'])]));")
    if o is None:
        return
    assert o[0] == "ab", o
    assert o[1] == 'ab<span class="tag-rest" hidden>cd</span><button class="pill more" id="tagMore" data-n="+2">+2</button>', o


def test_watch_edit_mode_source():
    """自選頁：按「編輯」才顯示「✕」移除與「≡」排序（不再左滑）；拖曳中的列跟著手指走、相鄰列以動畫換位；監聽掛在 section 上（不掛 #view）。"""
    assert 'title="從自選移除" aria-label="從自選移除">✕</button>' in APP and ".wx{" not in CSS
    assert "swiped" not in APP + CSS and "touch-action:pan-y" not in CSS                       # 左滑已移除
    assert APP.count("rm ? wCtl(c) : ''") == 1 and APP.count('<td class="nm">${wCtl(c)}') == 1     # 股票表、ETF 表各一
    assert 'id="watchEdit">${App.watchEdit ? \'完成\' : \'編輯\'}' in APP
    assert "App.watchUndo = App.watchEdit = null" in APP                                       # 離開自選頁結束編輯
    w = APP[APP.index("function watchGestures(sec)"):APP.index("// 第 20 輪 F20-1：自選頁的 ETF 表")]
    assert "$('#view').addEventListener" not in w and "sec.addEventListener('click'" in w
    assert "sec.classList.contains('editing')" in w and "!e.target.closest('.wdel')" in w      # 編輯中點列不進個股頁
    assert "setPointerCapture" in w and "'ArrowUp'" in w and "'ArrowDown'" in w and "saveWatchOrder(tb)" in w
    assert "--dy" in w and ".animate?.(" in w                                                    # 動態拖曳
    assert "watchGestures($('#view .watch'));" in APP and "<section class=\"sec watch${App.watchEdit ? ' editing' : ''}\">" in APP
    assert ".watch:not(.editing) .wdel,.watch:not(.editing) .wh" in CSS and "touch-action:none" in CSS
    assert ".watch tr.dragging td{transform:translateY(var(--dy,0))" in CSS
    assert ".watch tr.dragging td:not(:first-child){position:relative}" in CSS                 # 名稱欄維持 sticky


def test_watch_order():
    """saveWatchOrder：股票表的新順序排前、ETF 表的新順序排後，另一張表與不存在的代號保留。"""
    js = _grab(APP, "wCtl") + "\n" + _grab(APP, "saveWatchOrder") + """
const App = { watch: new Set(['2330', '0050', '2421', '9999', '00878', '2317']) };
let saved = [];
const saveWatch = () => saved.push([...App.watch]);
const tb = (k, codes) => ({ rows: codes.map(c => ({ dataset: { [k]: c } })) });
saveWatchOrder(tb('code', ['2317', '2330', '2421']));
const a = [...App.watch];
saveWatchOrder(tb('etf', ['00878', '0050']));
console.log(JSON.stringify({ a, b: [...App.watch], n: saved.length, h: wCtl('2330') }));"""
    o = _node(js)
    if o is None:
        return
    assert o["a"] == ["2317", "2330", "2421", "0050", "9999", "00878"], o
    assert o["b"] == ["2317", "2330", "2421", "9999", "00878", "0050"], o
    assert o["n"] == 2, o
    assert 'class="wh" data-drag="2330"' in o["h"] and 'class="wdel" data-unwatch="2330"' in o["h"] and ">✕</button>" in o["h"]


def test_no_advice_words():
    seg = "".join(l for l in APP.splitlines() + STK.splitlines() + CSS.splitlines() if "QA25" in l or "收合" in l or "編輯" in l or "拖曳" in l)
    for w in ("買進", "賣出", "反彈", "見底", "買點", "超賣", "超買", "推薦", "強勢股", "飆股", "勝率"):
        assert w not in seg, w


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            print("==", name)
            fn()
            print("✅", name)
    print("全部通過")
