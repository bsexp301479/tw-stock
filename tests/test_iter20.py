"""第 20 輪（不連網、不連資料庫）：F20-1 ETF 加入自選。
有 node 時，逐字取出 app.js 的 renderWatch 與相依函式，用假的 latest 跑四種自選清單。"""
import json
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "site" / "app.js").read_text(encoding="utf-8")
STK = (ROOT / "site" / "stock.js").read_text(encoding="utf-8")
README = (ROOT / "README.md").read_text(encoding="utf-8")


def test_star_on_etf_page():
    # ETF 頁也輸出自選鈕（不再用 E 判斷）；點擊處理不分股票、ETF
    assert re.search(r"^\s*<button class=\"star \$\{watching", STK, re.M)
    assert "${E ? '' : `<button class=\"star" not in STK
    assert "App.watch.has(code) ? App.watch.delete(code) : App.watch.add(code);" in STK


def test_watch_source():
    w = APP[APP.index("function renderWatch()"):APP.index("// ─── 資料新鮮度")]
    assert "App.latest.etfs?.rows || {}" in w and "filter(c => !S[c] && R[c])" in w
    assert "<h2>自選</h2>" in w and "<h2>ETF</h2>" in w
    assert "按名稱旁的「☆ 加入自選」" in w                                       # test_iter13 的舊句保留
    assert "addEventListener('click', onEtfRow)" in w and "addEventListener('click', onRowClick)" in w
    assert "<th>ETF</th><th>收盤</th><th>漲跌</th><th>成交量</th><th>成交額</th>" in w
    # ETF 列表改用同一個具名函式（重複 addEventListener 只登記一次）
    assert APP.count("addEventListener('click', onEtfRow)") == 2
    assert "const onEtfRow = e =>" in APP


def test_texts():
    note = APP[APP.index("function renderEtf()"):APP.index("function renderWatch()")]
    assert "自選" not in note.split("<div class=\"muted small\" style=\"margin-top:6px\">共 ")[1].split("</div>")[0]
    etf = next(l for l in README.splitlines() if l.startswith("- ETF：代號"))
    assert "排行、自選" not in etf and "自選鈕" not in etf and "第 20 輪起可加入自選" in etf


def _grab(name):
    """取出 app.js 的頂層 function 或 const（const 取到結尾為「;」的那一行）。"""
    m = re.search(rf"^function {name}\(", APP, re.M)
    if m:
        i, n = APP.index("{", APP.index(")", m.start())), 0
        for j in range(i, len(APP)):
            n += {"{": 1, "}": -1}.get(APP[j], 0)
            if n == 0:
                return APP[m.start():j + 1]
    m = re.search(rf"^const {name} =", APP, re.M)
    lines = APP[m.start():].splitlines()
    k = next(i for i, l in enumerate(lines) if l.rstrip().endswith(";"))
    return "\n".join(lines[:k + 1])


def test_render_watch():
    node = shutil.which("node")
    if not node:
        print("  （沒有 node，略過 renderWatch 執行）"); return
    names = ["fmt", "pfmt", "sgn", "cls", "pctCell", "yi", "esc", "md", "streakTxt", "holdTag", "alertBadge",
             "segHTML", "onSeg", "flowNote", "stockTable", "spanSeg", "onEtfRow", "renderWatch", "etfWatchTable"]
    latest = {"date": "2026-11-10", "flow_date": "2026-11-10", "holdings": {"00981A": {}},
              "stocks": {"2330": {"n": "台積電", "i": "半導體", "c": 1460, "p": 1.2, "tv": 300.5, "f1": 10, "t1": 1, "d1": 0, "n1": 11, "fs": 2, "ts": 1, "s": 2}},
              "etfs": {"rows": {"0056": {"n": "元大高股息", "m": "TWSE", "c": 36.5, "ch": -0.2, "p": -0.54, "v": 30000, "tv": 11.02},
                                "00981A": {"n": "主動統一台股增長", "m": "TWSE", "c": 15.1, "ch": 0.1, "p": 0.67, "v": 90000, "tv": 13.6},
                                "00625K": {"n": "富邦上証+R", "m": "TWSE", "c": None, "ch": None, "p": None, "v": 0, "tv": 0}}}}
    js = "\n".join(_grab(n) for n in names) + f"""
const App = {{ latest: {json.dumps(latest, ensure_ascii=False)}, watch: new Set() }};
const view = {{ innerHTML: '', n: 0, addEventListener() {{ this.n++; }} }};
const $ = s => s === '#view' ? view : view.innerHTML.includes(`id="${{s.slice(1)}}"`) ? {{ addEventListener() {{}} }} : null;   // 畫面上沒有的元素回傳 null
const localStore = (k, f) => f, onRowClick = () => {{}};
const out = {{}};
for (const [k, w] of Object.entries({{ both: ['2330', '0056', '00981A', '00625K', '9999'], etf: ['0056'], stock: ['2330'], none: [] }})) {{
  App.watch = new Set(w); view.innerHTML = ''; renderWatch(); out[k] = view.innerHTML;
}}
console.log(JSON.stringify(out));"""
    o = json.loads(subprocess.run([node, "-e", js], capture_output=True, text=True, check=True).stdout)
    for k in o:
        assert ("<h2>自選 ETF</h2>" if k == "etf" else "<h2>自選</h2>") in o[k]          # 第 23 輪 F23-4c：只有 ETF 時合併成「自選 ETF」
    b = o["both"]
    assert 'data-code="2330"' in b and b.count("data-etf=") == 3 and "9999" not in b      # 不存在的代號不顯示
    assert '<a class="pill hold" href="#/etf/00981A">持股</a>' in b and "rspanSeg" in b
    assert ">無成交</td>" in b and '<td class="num">11.02億</td>' in b and '<td class="num dn">-0.54%</td>' in b
    assert b.index('data-code="2330"') < b.index('data-etf="0056"')                       # 股票在上
    assert "data-code" not in o["etf"] and "還沒有自選股" not in o["etf"] and "rspanSeg" not in o["etf"]
    assert "<h2>ETF</h2>" not in o["stock"] and "rspanSeg" in o["stock"]
    assert "還沒有自選股" in o["none"] and "<h2>ETF</h2>" not in o["none"] and "rspanSeg" in o["none"]


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_") and callable(f):
            print("==", n); f()
    print("全部通過")
