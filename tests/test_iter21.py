"""第 21 輪（不連網、不連資料庫）：F21-1 近期新訊號。
export 的 highlights、highlight_revenue、highlight_active 用自造資料測邊界；
有 node 時，逐字取出 app.js 的 renderHl 與相依函式，用假的 latest、screen 跑篩選與排序。"""
import json
import re
import shutil
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from twstock import export  # noqa: E402

APP = (ROOT / "site" / "app.js").read_text(encoding="utf-8")
CSS = (ROOT / "site" / "app.css").read_text(encoding="utf-8")
README = (ROOT / "README.md").read_text(encoding="utf-8")

D0 = date(2026, 9, 1)


def _days(n):
    out, d = [], D0
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def _run(adj, tv, pct, net, trust, n_flow=None):
    days = _days(len(adj))
    flow = days[:n_flow] if n_flow else days
    return export.highlights(days, adj, tv, pct, net[:len(flow)], trust[:len(flow)], days, flow, {}), days


def test_price_events():
    n = 70
    adj = [100.0] * n
    tv = [1e8] * n                                       # 每天 1 億
    pct = [0.0] * n
    adj[-3], tv[-3], pct[-3] = 110.0, 1.6e8, 10.0        # 倒數第 3 天：60 日新高、量比 1.6 → nh（vu 不成立：量比 < 2）
    adj[-2], tv[-2] = 111.0, 1.6e8                       # 前一天已符合 → 不是新出現
    adj[-1], tv[-1], pct[-1] = 111.0, 2.5e8, 3.0         # 沒有創新高（不大於前高）、量比 ≥ 2 且漲 3% → vu
    ev, d = _run(adj, tv, pct, [0.0] * n, [0.0] * n)
    assert ev == [["nh", str(d[-3])], ["vu", str(d[-1])]], ev
    # 窗口（最後 5 天）以前的事件不列
    adj2, tv2, pct2 = [100.0] * n, [1e8] * n, [0.0] * n
    adj2[-7], tv2[-7], pct2[-7] = 120.0, 3e8, 5.0
    assert _run(adj2, tv2, pct2, [0.0] * n, [0.0] * n)[0] == []


def test_insti_events():
    n = 40
    adj, tv, pct = [100.0] * n, [1e8] * n, [0.0] * n
    net = [-1.0] * n
    net[-4:] = [1.0, 1.0, 1.0, 1.0]                       # 倒數第 2 天連買達 3 日 → s3；最後一天第 4 日不再列
    trust = [0.0] * n
    trust[-1] = 1.3                                       # 5 日買超 1.3 億 ≥ 20 日均額 1 億 × 5 × 5% = 0.25 → t5（連買只有 1 日）
    ev, d = _run(adj, tv, pct, net, trust)
    assert ev == [["s3", str(d[-2])], ["t5", str(d[-1])]], ev
    # 連買在窗口前就達 3 日 → 不列
    net2 = [1.0] * n
    assert _run(adj, tv, pct, net2, [0.0] * n)[0] == []
    # 法人資料晚一天：最後一天沒有法人資料，不產生法人事件
    net3 = [-1.0] * n
    net3[-3:] = [1.0, 1.0, 1.0]
    assert _run(adj, tv, pct, net3, [0.0] * n, n_flow=n - 1)[0] == []


def test_revenue_event():
    rows = [[2026, 10, 1000, 1.0, 35.0, 20.0, 3]]
    seen = {(2026, 10): date(2026, 11, 6)}
    assert export.highlight_revenue(rows, seen, date(2026, 10, 14)) == [["rv", "2026-11-06", 202610]]
    assert export.highlight_revenue(rows, seen, date(2026, 11, 7)) == []                         # 窗口外
    assert export.highlight_revenue([[2026, 10, 1000, 1.0, 29.9, 20.0, 3]], seen, date(2026, 10, 1)) == []   # 年增 < 30
    assert export.highlight_revenue([[2026, 10, 1000, 1.0, 35.0, 20.0, 0]], seen, date(2026, 10, 1)) == []   # 沒有創新高
    # 補抓：收錄日晚於次月 10 日 5 天以上 → 日期改用次月 10 日
    late = {(2026, 9): date(2026, 10, 28)}
    assert export.highlight_revenue([[2026, 9, 1, 1.0, 40.0, 1.0, 2]], late, date(2026, 10, 1)) == [["rv", "2026-10-10", 202609]]
    assert export.highlight_revenue([[2026, 12, 1, 1.0, 40.0, 1.0, 2]], {(2026, 12): date(2027, 1, 8)}, date(2027, 1, 1)) == [["rv", "2027-01-08", 202612]]
    assert export.highlight_revenue([], {}, date(2026, 1, 1)) == []


def test_active_event():
    d1, d2, d3 = date(2026, 11, 6), date(2026, 11, 9), date(2026, 11, 10)
    held = {d1: {("ST", "2330"): 0}, d2: {("ST", "2330"): 0, ("ST", "3044"): 0, ("ST", "AAPL"): 0, ("FU", "TX"): 0},
            d3: {("ST", "2330"): 0, ("ST", "3044"): 0, ("ST", "2317"): 0}}
    H = {"00403A": ([d1, d2, d3], {}, held), "00999A": ([d3], {}, {d3: {("ST", "1101"): 0}})}   # 00999A 只有一個持股日
    out = export.highlight_active(H, {"2330", "3044", "2317", "1101"}, d2)
    assert dict(out) == {"3044": [["ae", "2026-11-09", "00403A"]], "2317": [["ae", "2026-11-10", "00403A"]]}
    assert dict(export.highlight_active(H, {"3044", "2317"}, d3)) == {"2317": [["ae", "2026-11-10", "00403A"]]}


def test_export_source():
    src = (ROOT / "twstock" / "export.py").read_text(encoding="utf-8")
    assert "HL_DAYS, HL_REV_DAYS = 5, 20" in src
    assert "m.revenue_yoy, m.created_at" in src and "rev_seen[r[0]][(r[1], r[2])] = r[6].date()" in src
    assert '**({"hl": hl} if hl else {}),' in src
    assert "st = price_stats(d_[:i + 1], adj[:i + 1], tv[:i + 1]" in src            # 和選股同一套


def test_app_source():
    assert "arg === 'hl' ? renderHl()" in APP
    assert "[['rank', '排行'], ['screen', '選股'], ['hl', '新訊號']]" in APP
    seg = APP[APP.index("// ─── 第 21 輪 F21-1"):APP.index("// ─── 第 8 輪 F8-2")]
    assert "!x.dsp && !x.nt && isNum(x.a20) && x.a20 >= 0.5" in seg
    assert "localStore('hlmin', '3')" in seg and "$('#view').addEventListener('click', onRowClick);" in seg
    assert "只描述發生了什麼，不代表之後的走勢。" in seg
    for w in ("買進", "賣出", "反彈", "見底", "買點", "超賣", "超買", "推薦", "強勢股", "飆股", "勝率"):
        assert w not in seg, w
    assert ".tbl td.hl-tags,.tbl th.hl-th{white-space:normal" in CSS
    assert "近期新訊號（排行頁「新訊號」，`#/rank/hl`，第 21 輪）" in README and "近期新訊號）" in README


def _grab(name):
    """取出 app.js 的頂層 function、async function 或 const（const 取到結尾為「;」的那一行）。"""
    m = re.search(rf"^(?:async )?function {name}\(", APP, re.M)
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


def test_render_hl():
    node = shutil.which("node")
    if not node:
        print("  （沒有 node，略過 renderHl 執行）"); return
    names = ["fmt", "pfmt", "sgn", "cls", "pctCell", "esc", "md", "alertBadge", "segHTML", "onSeg", "modeSeg", "onModeSeg",
             "screenRow", "screenRows", "MARGIN_BASE", "HL_KINDS", "hlTag", "hlDims", "renderHl"]
    st = lambda n, hl, **k: {"n": n, "i": "其他", "c": 10, "p": 1.0, "hl": hl, **k}
    ev = {"p": ["nh", "2026-11-10"], "f": ["s3", "2026-11-09"], "r": ["rv", "2026-11-06", 202610], "a": ["ae", "2026-11-10", "00981A"]}
    stocks = {"1101": st("甲", [ev["p"], ev["f"], ev["r"]]),                         # 3 面向
              "1102": st("乙", [ev["p"], ev["f"], ["t3", "2026-11-10"], ev["a"]]),   # 3 面向（法人 2 個事件只算 1）
              "1103": st("丙", [ev["p"], ev["r"]]),                                  # 2 面向
              "1104": st("丁", [ev["p"], ev["f"], ev["r"], ev["a"]], dsp=["2026-11-01", "2026-11-14"]),   # 處置 → 不列
              "1105": st("戊", [ev["p"], ev["f"], ev["r"]], nt="2026-11-07"),       # 今日無成交 → 不列
              "1106": st("己", [ev["p"], ev["f"], ev["r"]]),                         # 均額 < 0.5 → 不列
              "1107": {"n": "庚", "i": "其他", "c": 10, "p": 0},                     # 沒有 hl
              "1108": st("辛", [ev["p"], ["vu", "2026-11-10"], ev["f"]])}            # 3 個事件但只有 2 個面向
    a20 = {"1101": 5.0, "1102": 9.0, "1103": 50.0, "1104": 9.9, "1105": 9.9, "1106": 0.4, "1107": 99, "1108": 99}
    js = "\n".join(_grab(n) for n in names) + f"""
const isNum = v => typeof v === 'number';
const App = {{ latest: {{ date: '2026-11-10', flow_date: '2026-11-10', holdings: {{ '00981A': {{}} }}, stocks: {json.dumps(stocks, ensure_ascii=False)} }} }};
const A20 = {json.dumps(a20)};
const view = {{ innerHTML: '', addEventListener() {{}} }};
const $ = s => s === '#view' ? view : view.innerHTML.includes(`id="${{s.slice(1)}}"`) ? {{ addEventListener() {{}}, querySelectorAll: () => [] }} : null;
let MIN = '3';
const localStore = (k, f) => k === 'hlmin' ? MIN : f, onRowClick = () => {{}};
const loadScreen = async () => (App.screen = {{ rows: Object.fromEntries(Object.entries(A20).map(([c, v]) => [c, {{ a20: v }}])) }});
(async () => {{
  const out = {{}};
  for (const m of ['3', '2']) {{ MIN = m; App.rows = null; await renderHl(); out[m] = view.innerHTML; }}
  console.log(JSON.stringify(out));
}})();"""
    o = json.loads(subprocess.run([node, "-e", js], capture_output=True, text=True, check=True).stdout)
    rows = lambda h: re.findall(r'<tr data-code="(\d+)">', h)
    assert rows(o["3"]) == ["1102", "1101"], rows(o["3"])            # 依面向數、再依 20 日均額
    assert rows(o["2"]) == ["1102", "1101", "1108", "1103"], rows(o["2"])    # 3 面向在前，2 面向在後
    assert "面向 ≥ 3：2 檔；≥ 2：4 檔" in o["3"]
    assert "00981A 新增 <i>11/10</i>" in o["3"] and "10 月營收創新高 <i>11/06</i>" in o["3"] and "60 日新高帶量 <i>11/10</i>" in o["3"]
    assert 'id="hlSeg"' in o["3"] and 'data-v="hl" class="on"' in o["3"]


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_") and callable(f):
            print("==", n); f()
    print("全部通過")
