"""第 19 輪（不連網、不連資料庫）：F19-1 除權類型（配股／現金增資）；F19-2 週／月 K 的事件標記、圖例與原始價漲跌。
fixture：tests/fixtures/twt49u_rights_mini.json、exdailyq_rights_mini.json（官方原始回應的精簡版：欄位不變，只留幾列；
櫃買保留 1 年內一般股票全部「除權」「除權息」112 列，明細欄位當真值）。數值以 2026-11-09 為準。"""
import json
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from twstock import db, export  # noqa: E402
from twstock.collectors.events import parse_events  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures"
STK = (ROOT / "site" / "stock.js").read_text(encoding="utf-8")
SRC = (ROOT / "twstock" / "collectors" / "events.py").read_text(encoding="utf-8")
T49 = json.loads((FIX / "twt49u_rights_mini.json").read_text(encoding="utf-8"))
TPX = json.loads((FIX / "exdailyq_rights_mini.json").read_text(encoding="utf-8"))["tables"][0]
num = lambda s: float(str(s).replace(",", ""))


def test_parse_div_ref():
    r = {(x["stock_code"], x["event_date"]): x for x in parse_events("TWT49U", T49["fields"], T49["data"])}
    assert r[("2421", "2026-02-24")] == {"stock_code": "2421", "event_date": "2026-02-24", "event_type": "權", "prev_close": 147.0,
                                         "ref_price": 145.96, "source": "TWT49U", "div_ref": 147.0}
    assert r[("6669", "2026-09-02")]["div_ref"] == 2614.99 and r[("8112", "2026-07-06")]["div_ref"] == 89.09
    tp = parse_events("TPEX_EX", TPX["fields"], TPX["data"])
    assert len(tp) == 114 and all("div_ref" in x for x in tp)                       # 112 權／權息 + 2 息；ETF 略過
    # 欄位缺失：少了「減除股利參考價」→ 事件照常回傳、沒有 div_ref，不拋例外
    i = T49["fields"].index("減除股利參考價")
    f2 = T49["fields"][:i] + ["改名"] + T49["fields"][i + 1:]
    r2 = parse_events("TWT49U", f2, T49["data"])
    assert len(r2) == len(r) and all("div_ref" not in x for x in r2)
    # 值無法解析（--、空白、0）→ 沒有 div_ref；列比欄位短 → 沒有 div_ref
    row = T49["data"][0][:]
    for bad in ("--", "", "0.00"):
        row[i] = bad
        assert "div_ref" not in parse_events("TWT49U", T49["fields"], [row])[0]
    assert "div_ref" not in parse_events("TWT49U", T49["fields"], [T49["data"][0][:i]])[0]
    # 減資、面額變更沒有這一欄
    assert all(x is None for x in (export.rights_kind("減", 36.0, 47.14, None), export.rights_kind("面", 1490.0, 74.5, None)))
    # MERGE 多更新一欄；缺值時保留已存的值
    assert "div_ref DECIMAL(10,2)" in SRC and "div_ref = COALESCE(s.div_ref, t.div_ref)" in SRC
    assert '"div_ref":null' not in db.to_json(r2)


def test_rights_kind():
    k = export.rights_kind
    assert k("權", 147.0, 145.96, 147.0) == "c"                  # 2421 2026/02/24：只有現增
    assert k("權", 214.0, 204.83, 214.0) == "c"                  # 3189 2026/01/26
    assert k("權", 7800.0, 2614.99, 2614.99) == "s"              # 6669 2026/09/02：配股
    assert k("權息", 92.9, 87.53, 89.09) == "sc"                 # 8112 2026/07/06：股利＋現增
    assert k("權息", 19.1, 16.13, 17.31) == "sc"                 # 2614 2026/10/06
    assert k("權息", 79.5, 63.75, 63.75) == "s"
    assert k("權", 50.0, 45.0, 47.0) == "sc"                     # 「權」也可能是配股＋現增
    assert k("息", 160.0, 154.75, 154.75) is None                # 只對「權」「權息」
    assert k("權", 147.0, 145.96, None) is None                  # 舊資料、欄位缺失
    assert k("權", 100.0, 100.0, 100.0) is None                  # 參考價 = 前收：無法分辨
    assert k("權", 100.0, 95.0, 100.01) is None                  # 減除股利參考價高於前收：資料異常
    assert k("權", 100.0, 95.0, 100.004) == "c" and k("權", 100.0, 95.0, 95.004) == "s"   # 容差 0.005 元


def test_tpex_truth():
    """櫃買明細（現金增資股數、每仟股無償配股、現金股利）為真值：112／112 一致。"""
    f = {x: i for i, x in enumerate(TPX["fields"])}
    n = 0
    for r in TPX["data"]:
        t = r[f["權/息"]].strip().lstrip("除")
        if t not in ("權", "權息"):
            continue
        ci, sd, cash = (num(r[f[x]] or 0) > 0 for x in ("現金增資股數", "每仟股無償配股", "現金股利"))
        want = "c" if ci and not (sd or cash) else "sc" if ci else "s"
        assert export.rights_kind(t, num(r[3]), num(r[4]), num(r[f["減除股利參考價"]])) == want, r[:5]
        n += 1
    assert n == 112


def test_price_events_k():
    d = [date(2026, 2, x) for x in (23, 24, 25)]
    c, ch = (144.5, 146.0, 147.0), (0.5, 0.05, 1.0)
    off = [{"d": d[1], "t": "權", "p": 147.0, "r": 145.96, "src": "TWT49U", "k": "c"}]
    ev, _ = export._price_events(d, c, ch, "TWSE", off)
    assert ev == [{"i": 1, "d": "2026-02-24", "t": "權", "p": 147.0, "r": 145.96, "k": "c"}]
    off[0]["k"] = None                                                                  # 沒有分類：不輸出 k（和改版前相同）
    assert export._price_events(d, c, ch, "TWSE", off)[0] == [{"i": 1, "d": "2026-02-24", "t": "權", "p": 147.0, "r": 145.96}]
    src = (ROOT / "twstock" / "export.py").read_text(encoding="utf-8")
    assert '{k: e[k] for k in ("d", "t", "p", "r", "k") if k in e}' in src and "e.div_ref" in src


def test_setup_db():
    src = (ROOT / "twstock" / "db.py").read_text(encoding="utf-8")       # 可重複執行：先判斷欄位是否存在
    assert "IF COL_LENGTH('price_events', 'div_ref') IS NULL ALTER TABLE price_events ADD div_ref DECIMAL(10,2) NULL" in src


def _js(names, consts=()):
    """逐字取出 stock.js 的函式與常數（const 改 var，讓 node -e 取得到）。"""
    out = []
    for name in names:
        s = STK.index(f"function {name}(")
        i, n = STK.index("{", s), 0
        for j in range(i, len(STK)):
            n += {"{": 1, "}": -1}.get(STK[j], 0)
            if n == 0:
                out.append(STK[s:j + 1]); break
    for name in consts:
        s = STK.index(f"const {name} = ")
        out.append("var" + STK[s + 5:STK.index(";\n", s) + 1])
    return "\n".join(out)


def test_js_bar_change_and_labels():
    node = shutil.which("node")
    if not node:
        print("  （沒有 node，略過 JS 部分）"); return
    # 週 K：第 1 週收 100；第 2 週二除權（前收 100 → 參考價 50）、收 55；第 3 週沒有事件
    data = {"market": "TWSE", "prices": {"d": ["2026-08-28", "2026-09-01", "2026-09-02", "2026-09-07"],
                                         "o": [100, 100, 50, 55], "h": [100, 100, 56, 56], "l": [100, 100, 50, 54],
                                         "c": [100, 100, 55, 55], "v": [1, 1, 1, 1], "ch": [0, 0, 5, 0]},
            "insti": None, "ev": [{"d": "2026-09-02", "t": "權", "p": 100, "r": 50, "k": "s"}]}
    js = _js(["adjFactors", "aggregate", "barChange"], ["EV_LABEL", "evName", "evMark"]) + f"""
const data = {json.dumps(data)};
const out = [];
for (const mode of ['週', '月', '日']) for (const adj of [false, true]) {{
  const raw = aggregate(data, mode, adj);
  out.push([mode, adj, raw.map((r, i) => barChange(raw, i, mode, adj).map(x => x == null ? null : Math.round(x * 1e6) / 1e6))]);
}}
const gx = [{{ c: 10, ev: [] }}, {{ c: 9, ev: [], gx: '息?' }}];
const multi = [{{ c: 100, ev: [] }}, {{ c: 30, ev: [{{ p: 100, r: 50 }}, {{ p: 40, r: 32 }}] }}];
const E = (t, k) => ({{ t, k }});
console.log(JSON.stringify({{ out, gx: barChange(gx, 1, '週', false), first: barChange(gx, 0, '週', false),
  multi: barChange(multi, 1, '月', false).map(x => Math.round(x * 1e6) / 1e6),
  names: [E('權', 'c'), E('權', 's'), E('權', 'sc'), E('權'), E('權息', 'sc'), E('權息', 's'), E('權息'), E('息')].map(evName),
  marks: [E('權', 'c'), E('權', 's'), E('權息', 'sc'), E('息')].map(evMark) }}));"""
    r = json.loads(subprocess.run([node, "-e", js], capture_output=True, text=True, check=True, timeout=30).stdout)
    got = {(m, a): v for m, a, v in r["out"]}
    assert got[("週", False)][1] == [55 - 100 * 0.5, 10.0, 0.5]          # 原始：55 − 100 × 50/100 = +5（+10%），不是 −45
    assert got[("週", True)][1][1] == 10.0                                # 還原的漲跌幅相同
    assert got[("月", False)][1] == [5.0, 10.0, 0.5] and got[("月", True)][1][1] == 10.0
    assert got[("日", False)][2] == [5, 10, 1]                            # 日線照舊用匯出的漲跌（ch）與 aggregate 的 pc
    assert r["gx"] == [None, None, 1] and r["first"] == [0, 0, 1]        # gx 不比價；第一根 0
    assert r["multi"] == [30 - 100 * 0.5 * 0.8, (30 - 40) / 40 * 100, 0.4]   # 多事件：比值相乘
    assert r["names"] == ["除權（現金增資）", "除權（配股）", "除權（配股＋現金增資）", "除權", "除權息（含現金增資）", "除權息", "除權息", "除息"]
    assert r["marks"] == ["現增", "權", "權息", "息"]


def test_stock_page_source():
    assert "barChange(raw, i, mode, adj)" in STK and "C[i] - C[i - 1] : 0" not in STK
    assert "mode === '月' ? T[i].slice(0, 7) + ' 月' : mode === '週' ? T[i] + ' 當週' : T[i]" in STK
    assert "(mode === '日' ? '' : mdn(e.d) + ' ') + evMark(e)" in STK                 # 週／月標記「M/D 類型」，日 K 不加日期
    assert "${evName(e)}　前收" in STK and "CASH_INC_TIP" in STK
    assert "evName((data.ev || []).find(e => e.d === cap.d) || cap)" in STK           # 股本變動註記用同一套文字
    assert "現金增資除權也依官方參考價調整" in STK
    seg = STK[STK.index("const evName"):STK.index("// ─── 日線 → 週線")]
    for w in ("建議", "應認購", "吃虧", "稀釋", "買進", "賣出"):
        assert w not in seg, w


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"✅ {name}")
    print("全部通過")
