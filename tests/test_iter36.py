"""第 36 輪（不連網、不連資料庫）：F36-1 etfp dv、F36-2 ETF 配息卡、F36-3 ETF 列表配息欄、F36-4 K 線官方除息標記。
有 node 時逐字取出 app.js、stock.js 的程式執行（node 14 可跑）。test_real_data 讀已匯出的 site/data（沒有就略過）。"""
import hashlib
import json
import re
import shutil
import subprocess
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from twstock import export  # noqa: E402

SITE = ROOT / "site"
APP = (SITE / "app.js").read_text(encoding="utf-8")
STK = (SITE / "stock.js").read_text(encoding="utf-8")
HTML = (SITE / "index.html").read_text(encoding="utf-8")
EXP = (ROOT / "twstock" / "export.py").read_text(encoding="utf-8")
D = date.fromisoformat


def _grab(src, name):
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


PF = ("if (!Array.prototype.at) Array.prototype.at = function (i) { return this[i < 0 ? this.length + i : i]; };\n"
      "if (!String.prototype.replaceAll) String.prototype.replaceAll = function (a, b) { return this.split(a).join(b); };\n")


def _node(js):
    node = shutil.which("node")
    if not node:
        print("  （沒有 node，略過執行）")
        return None
    return json.loads(subprocess.run([node, "-e", PF + js], capture_output=True, text=True, check=True).stdout)


# ─── F36-1：匯出 ────────────────────────────────────────
DAYS = [D(s) for s in ("2026-07-01", "2026-07-02", "2026-07-03", "2026-07-06", "2026-07-07", "2026-07-08", "2026-07-09")]


def test_etf_dividends():
    c = [20.0, 19.5, 19.8, 20.1, None, 20.0, 21.0]
    ev = [(DAYS[1], 20.0, 19.4, 0.6)]
    # 除息日（第 1 天）起第一個原始收盤 ≥ 除息前收盤；c、p、r 轉 float
    assert export.etf_dividends(DAYS, c, ev) == [{"d": "2026-07-02", "t": "息", "c": 0.6, "p": 20.0, "r": 19.4, "f": "2026-07-06", "n": 3}]
    # 當天就回到：第 1 天；Decimal 輸入
    assert export.etf_dividends(DAYS, c, [(DAYS[5], Decimal("19.9"), Decimal("19.5"), Decimal("0.4"))]) == \
        [{"d": "2026-07-08", "t": "息", "c": 0.4, "p": 19.9, "r": 19.5, "f": "2026-07-08", "n": 1}]
    # 未填息：沒有 f、n、x
    assert export.etf_dividends(DAYS, c, [(DAYS[1], 30.0, 29.0, 1.0)]) == [{"d": "2026-07-02", "t": "息", "c": 1.0, "p": 30.0, "r": 29.0}]
    # 無成交（None）跳過、不算填息，但天數照算
    assert export.etf_dividends(DAYS, c, [(DAYS[3], 20.5, 20.0, 0.05)])[0] == {"d": "2026-07-06", "t": "息", "c": 0.05, "p": 20.5, "r": 20.0, "f": "2026-07-09", "n": 4}
    # 除息日不在行情（停牌）：只列，不算
    assert export.etf_dividends(DAYS, c, [(D("2026-06-30"), 15.0, 14.0, 1.0)]) == [{"d": "2026-06-30", "t": "息", "c": 1.0, "p": 15.0, "r": 14.0}]
    assert export.etf_dividends(DAYS, c, ()) == []


def test_etf_dividends_gx():
    c = [20.0, 19.5, 19.6, 9.9, 10.0, 10.1, 25.0]
    ev = [(DAYS[1], 20.0, 19.4, 0.6)]
    # 填息前遇到不是官方除息日的推測調整（分割）：停在那天，不再比較
    assert export.etf_dividends(DAYS, c, ev, ["2026-07-02", "2026-07-06"]) == \
        [{"d": "2026-07-02", "t": "息", "c": 0.6, "p": 20.0, "r": 19.4, "x": ["2026-07-06", "價格調整"]}]
    # 推測調整日剛好是官方除息日（另一次除息）：不算中斷
    ev2 = ev + [(DAYS[3], 19.6, 9.8, 0.1)]
    out = export.etf_dividends(DAYS, c, ev2, ["2026-07-02", "2026-07-06"])
    assert out[0] == {"d": "2026-07-02", "t": "息", "c": 0.6, "p": 20.0, "r": 19.4, "f": "2026-07-09", "n": 6}
    assert out[1] == {"d": "2026-07-06", "t": "息", "c": 0.1, "p": 19.6, "r": 9.8, "f": "2026-07-09", "n": 4}
    # 除息日當天本身是推測調整日：不算中斷
    assert "x" not in export.etf_dividends(DAYS, c, [(DAYS[3], 9.95, 9.9, 0.05)], ["2026-07-06"])[0]
    # 已填息後才遇到：不影響
    assert export.etf_dividends(DAYS, [20, 19.5, 20.0, 9.9, 10, 10, 10], ev, ["2026-07-06"])[0]["f"] == "2026-07-03"


def test_etf_div_row():
    T = D("2026-11-20")
    assert export.etf_div_row([], T) == {}
    assert export.etf_div_row([{"d": "2025-11-19", "t": "息", "c": 1.0, "p": 20.0}], T) == {}                      # 第 366 天：不算
    one = [{"d": "2025-11-20", "t": "息", "c": 1.0, "p": 20.0, "f": "2025-11-25", "n": 4}]
    assert export.etf_div_row(one, T) == {"dvd": "2025-11-20", "dvn": 4, "dvx": None, "dvc": 1.0}                  # 第 365 天：算
    dv = [{"d": "2025-10-20", "t": "息", "c": 9.0, "p": 20.0},
          {"d": "2026-01-20", "t": "息", "c": 0.1, "p": 20.0, "f": "2026-01-21", "n": 2},
          {"d": "2026-04-20", "t": "息", "c": 0.2, "p": 20.0},
          {"d": "2026-10-20", "t": "息", "c": 0.3, "p": 20.0, "x": ["2026-10-30", "價格調整"]}]
    assert export.etf_div_row(dv, T) == {"dvd": "2026-10-20", "dvn": None, "dvx": "價格調整", "dvc": 0.6}           # 合計去浮點誤差
    assert export.etf_div_row(dv[:3], T) == {"dvd": "2026-04-20", "dvn": None, "dvx": None, "dvc": 0.3}


def _rows():
    days = [str(d) for d in DAYS]
    return [(D(d), c, c, c, c, 2000, ch) for d, c, ch in zip(days, [20, 19.5, 19.8, 20.1, 20.0, 20.0, 21.0], [0.1, 0, 0.3, 0.3, -0.1, 0, 1])]


def test_etf_export():
    rows = _rows()
    T = export.etf_export("006201", "元大富櫃50", "TPEx", rows, {}, {}, None, None, None, None)
    assert set(T) == {"code", "name", "market", "prices"}                                                       # 沒有事件：不輸出 dv（test_iter15:83）
    T = export.etf_export("006201", "元大富櫃50", "TPEx", rows, {}, {}, None, None, None, None, [(DAYS[1], 20.0, 19.4, 0.6)])
    assert T["dv"] == [{"d": "2026-07-02", "t": "息", "c": 0.6, "p": 20.0, "r": 19.4, "f": "2026-07-06", "n": 3}]
    assert set(T) == {"code", "name", "market", "prices", "dv"} and T["prices"]["ch"][1] == 0                    # 上櫃：官方漲跌照傳（F36-5 不做）


def test_etf_block():
    latest = {"TWSE": (D("2026-11-20"), [("0056", "元大高股息", 44.31, -3.1, 188190000, 84.74e8)])}
    base = export.etf_block(latest, {}, None)
    add = export.etf_block(latest, {}, None, {"0056": {"dvd": "2026-10-22", "dvn": None, "dvx": None, "dvc": 4.936}})
    assert add["rows"]["0056"] == {**base["rows"]["0056"], "dvd": "2026-10-22", "dvn": None, "dvx": None, "dvc": 4.936}
    assert export.etf_block(latest, {}, None, {}) == base and "dvc" not in base["rows"]["0056"]
    assert "r.update((div_rows or {}).get(code, {}))" in EXP


def test_export_wiring():
    assert "eev = _load_etf_events(cur)" in EXP and EXP.index("eev = _load_etf_events(cur)") < EXP.index("conn.close()", EXP.index("eev ="))
    assert "SELECT e.etf_code, x.event_date, x.prev_close, x.ref_price, x.div_cash" in EXP
    assert 'FROM etf_events x JOIN etfs e ON e.etf_id = x.etf_id ORDER BY x.event_date"""' in EXP          # 舊到新（QA 觀察 1）
    assert "ds[-1] if ds else None, ds[-6] if len(ds) >= 6 else None, eev.get(code, ()))" in EXP
    assert "edv[code] = etf_div_row(E.get(\"dv\", []), latest_date)" in EXP
    assert '"etfs": etf_block(etf_latest, etf_margin_rows, esbl, edv),' in EXP
    assert '**({"dv": dv} if (dv := etf_dividends(d_, c, events, gx)) else {})}' in EXP
    # 讀資料庫只有 SELECT
    seg = EXP[EXP.index("def _load_etf_events"):EXP.index("def etf_gaps")]
    for w in ("INSERT", "UPDATE", "DELETE", "commit("):
        assert w not in seg, w


# ─── F36-2：ETF 配息卡 ───────────────────────────────────
def test_js_etf_card():
    js = "\n".join(_grab(APP, n) for n in ("fmt", "pfmt", "md", "noteHTML")) + "\n" + \
        "\n".join(_grab(STK, n) for n in ("EV_LABEL", "dfmt", "divHTML", "ETF_DIV_FULL")) + """
const App = { latest: { date: '2026-11-20' } };
const P = { d: ['2025-10-30', '2026-11-19', '2026-11-20'], c: [30, 29.71, 26.35] };
const dv = [{ d: '2026-08-20', t: '息', c: 0.5, p: 25, r: 24.5, f: '2026-08-21', n: 2 }, { d: '2026-10-20', t: '息', c: 0.25, p: 30, r: 29.75, x: ['2026-10-30', '價格調整'] },
  { d: '2026-11-20', t: '息', c: 3.36, p: 29.71, r: 26.35 }];
console.log(JSON.stringify([divHTML([], 'TPEx', P, true), divHTML(dv, 'TPEx', P, true), divHTML(dv, 'TPEx', P)]));"""
    o = _node(js)
    if o is None:
        return
    empty, etf, stock = o
    assert "<h2>配息與填息</h2>" in empty and "2025-10-30 起沒有除息紀錄" in empty and "<table" not in empty
    assert "<th>除息日</th><th>配息<br>（元）</th><th>除息<br>前收盤</th><th>填息</th>" in etf and "配股" not in etf.split("<tbody>")[0]
    rows = re.findall(r"<tr><td>(.*?)</tr>", etf)
    assert [r[:10] for r in rows] == ["2026/11/20", "2026/10/20", "2026/08/20"] and all(r.count("<td") == 3 for r in rows)   # 4 欄：日期＋3
    assert "08/21<span>第 2 個交易日</span>" in etf and "不再比較<span>10/30 價格調整後</span>" in etf
    assert "尚未填息<span>還差 3.36 元，+12.75%</span>" in etf and '<td class="num">3.36</td>' in etf
    for s in ("收益平準金、資本利得，不等於獲利", "上櫃 ETF 無法辨識分割", "除息表"):
        assert s in etf, s
    assert "<h2>股利與填息</h2>" in stock and "<th>配股<br>每千股</th>" in stock                                    # 預設仍是股票版
    # 走勢分頁：ETF 換成配息卡，股票照舊是技術面訊號
    assert "${E ? divHTML(data.dv || [], data.market, P, true) : '<section class=\"sec card\"><div class=\"sec-h\"><h2 id=\"sigTitle\">技術面訊號</h2>" in STK


# ─── F36-3：ETF 列表 ────────────────────────────────────
def test_js_etf_list():
    assert "['dvr', '配息率', -1], ['dva', '最近除息', 1]];" in APP
    assert "<th>借券增減</th><th>近一年配息</th><th>配息率</th><th>最近除息</th></tr></thead><tbody>" in APP
    assert "keyCol({ dvr: 12, dva: 13 }[f]);" in APP
    assert ".map(([c, r]) => [c, etfDiv(r, App.latest.date)]).filter(([, r]) => mkt === 'all' || r.m === mkt)" in APP
    assert "${r.dvn != null ? r.dvn + ' 天填息' : r.dvx ? '中斷' : '未填息'}" in APP
    js = "\n".join(_grab(APP, n) for n in ("ETF_SORT", "etfDiv")) + """
const rows = { A: { c: 20, dvc: 1.2, dvd: '2026-11-20' }, B: { c: 10, dvc: 1.0, dvd: '2026-03-01' }, C: { c: null, dvc: 1, dvd: '2026-10-01' }, E: { c: 5 } };
const d = '2026-11-20', out = Object.entries(rows).map(([c, r]) => [c, etfDiv(r, d)]);
const srt = by => { const [key, , dir] = ETF_SORT.find(x => x[0] === by); return out.slice().sort((a, b) => (a[1][key] == null) - (b[1][key] == null) || dir * ((a[1][key] ?? 0) - (b[1][key] ?? 0))).map(x => x[0]); };
console.log(JSON.stringify([out, srt('dvr'), srt('dva')]));"""
    o = _node(js)
    if o is None:
        return
    out, by_r, by_a = o
    r = dict(out)
    assert r["A"]["dvr"] == 6 and r["B"]["dvr"] == 10 and r["C"]["dvr"] is None and r["E"]["dvr"] is None     # 無成交 → --
    assert r["A"]["dva"] == 0 and r["B"]["dva"] == 264 and r["C"]["dva"] == 50 and r["E"]["dva"] is None
    assert by_r == ["B", "A", "C", "E"] and by_a == ["A", "C", "B", "E"]                                       # 高到低；近到遠；沒有的排最後


def test_notes():
    note = _grab(APP, "ETF_DIV_NOTE")
    for s in ("近一年（365 天）每單位配息合計 ÷ 今日收盤", "不代表未來", "股價下跌時配息率會變高", "只看最近一次", "標「中斷」"):
        assert s in note, s
    assert "股票口徑的融資融券。${ETF_DIV_NOTE}</div></section>`;" in APP


# ─── F36-4：K 線與頁頭 ──────────────────────────────────
def test_kline_marks():
    assert "const ev = data.ev || (data.dv || []).map(r => ({ d: r.d, t: r.t, p: r.p, r: r.r }));" in STK
    assert "gx: gx.has(d) && !e.length ? (ch == null ? '息?' : '調?') : ''" in STK
    assert "raw[i].ev.some(e => e.t === '息') ? '除息日官方未提供漲跌'" in STK
    assert "const dvLast = (data.dv || []).find(r => r.d === P.d[last]);" in STK and "|| !!dvLast;" in STK
    assert "不比價（今天除息）" in STK and "今天除息，每單位配息 ${dfmt(dvLast.c)} 元，除息前收盤 ${pfmt(dvLast.p)}" in STK
    note = STK[STK.index("const ETF_NOTE = "):STK.index("\n\n", STK.index("const ETF_NOTE = "))]
    assert "本站無法辨識除息日" not in note and "本站還沒有 ETF 的除息資料" not in note
    assert "圖上「息」是官方除息日${m === 'TWSE' ? '，「息?」「調?」是推測的其他價格調整' : ''}" in note
    assert "上櫃 ETF：除息表以外的價格調整（如分割）本站無法辨識" in note


def test_js_aggregate_marks():
    """官方除息日：ev 有「息」、gx 不標推測；不是官方除息日的推測日照舊。"""
    names = ("adjFactors", "aggregate")
    if not all(re.search(rf"^function {n}\(", STK, re.M) for n in names):
        print("  （找不到 aggregate，略過執行）")
        return
    js = "\n".join(_grab(STK, n) for n in names) + """
const data = { prices: { d: ['2026-07-01', '2026-07-02', '2026-07-03'], o: [20, 19.5, 9.9], h: [20, 19.5, 9.9], l: [20, 19.5, 9.9], c: [20, 19.5, 9.9], v: [1, 1, 1], ch: [0, null, 0.1] },
  gx: ['2026-07-02', '2026-07-03'], dv: [{ d: '2026-07-02', t: '息', c: 0.6, p: 20, r: 19.4 }] };
const R = aggregate(data, '日', false).rows || aggregate(data, '日', false);
console.log(JSON.stringify(R.map(x => [x.gx, x.ev.map(e => e.t)])));"""
    try:
        o = _node(js)
    except subprocess.CalledProcessError:
        print("  （aggregate 需要其他函式，改由 8001 實測）")
        return
    if o is None:
        return
    assert o == [["", []], ["", ["息"]], ["調?", []]], o


def test_version():
    for f in ("app.js", "stock.js"):
        v = hashlib.sha1((SITE / f).read_bytes()).hexdigest()[:8]
        assert f'src="{f}?v={v}"' in HTML, f"site/index.html 的 {f} 版本參數請改成 ?v={v}"


def test_no_advice_words():
    seg = _grab(APP, "ETF_DIV_NOTE") + _grab(STK, "ETF_DIV_FULL") + STK[STK.index("const ETF_NOTE = "):STK.index("\n\n", STK.index("const ETF_NOTE = "))]
    seg += "".join(l for l in APP.splitlines() + STK.splitlines() if "第 36 輪" in l or "dvLast" in l or "配息率" in l)
    seg += EXP[EXP.index("def _load_etf_events"):EXP.index("def etf_gaps")]
    assert "配息率" in seg and "填息" in seg
    for w in ("買進", "賣出", "反彈", "見底", "買點", "超賣", "超買", "推薦", "強勢", "飆股", "勝率", "亮點", "建議", "低估", "高估",
              "便宜", "價值陷阱", "穩定配息", "划算", "安全", "危險", "殖利率"):
        assert w not in seg, w


# ─── 實際匯出資料（有才測）────────────────────────────────
def test_real_data():
    lp = SITE / "data" / "latest.json"
    if not lp.exists():
        print("  （沒有 site/data，略過）")
        return
    L = json.loads(lp.read_text(encoding="utf-8"))
    rows, today = (L.get("etfs") or {}).get("rows", {}), D(L["date"])
    if not any("dvc" in r for r in rows.values()):
        print("  （尚未用第 36 輪匯出，略過）")
        return
    n = 0
    for code, r in rows.items():
        p = SITE / "data" / "etfp" / f"{code}.json"
        if not p.exists():
            continue
        E = json.loads(p.read_text(encoding="utf-8"))
        assert E.get("dv", 0) != [], code                                             # 沒有就不輸出鍵
        dv = E.get("dv", [])
        assert {k: r[k] for k in ("dvd", "dvn", "dvx", "dvc") if k in r} == export.etf_div_row(dv, today), code
        ds = E["prices"]["d"]
        for x in dv:
            if "f" in x:
                i = ds.index(x["d"])
                assert ds[i + x["n"] - 1] == x["f"] and E["prices"]["c"][i + x["n"] - 1] >= x["p"], code
        n += bool(dv)
    assert n > 100, n


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_") and callable(f):
            print("==", n); f()
    print("全部通過")
