"""第 18 輪（不連網、不連資料庫）：F18-1 個股頁 KD、RSI；F18-2 選股 KD、RSI 條件與全市場比例。
匯出端（Python）與個股頁（JS）兩套公式要一致：有 node 時直接執行 stock.js 的 calcKD、calcRSI 比對。"""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from twstock import export  # noqa: E402

APP = (ROOT / "site" / "app.js").read_text(encoding="utf-8")
STK = (ROOT / "site" / "stock.js").read_text(encoding="utf-8")
CSS = (ROOT / "site" / "app.css").read_text(encoding="utf-8")
R1 = lambda v: None if v is None else round(v, 1)


def test_kd_formula():
    k, d = export.calc_kd([10] * 12, [10] * 12, [10] * 12)                 # 最高 = 最低：RSV 50，K、D 維持 50
    assert k[:8] == [None] * 8 and d[7] is None and k[8:] == [50.0] * 4 and d[8:] == [50.0] * 4
    k, d = export.calc_kd([10] * 9, [0] * 9, [10] * 9)                     # 收在最高：RSV 100
    assert R1(k[8]) == 66.7 and R1(d[8]) == 55.6                            # 50×2/3 + 100/3；50×2/3 + 66.67/3
    k, d = export.calc_kd([10] * 10, [0] * 10, [10] * 9 + [0])               # 收在最低：RSV 0
    assert R1(k[9]) == 44.4 and R1(d[9]) == 51.9


def test_rsi_formula():
    up = list(range(1, 17))
    assert export.calc_rsi(up)[:14] == [None] * 14 and export.calc_rsi(up)[14:] == [100.0, 100.0]   # 只漲
    assert export.calc_rsi(up[::-1])[14] == 0.0                                                     # 只跌
    assert export.calc_rsi([5] * 15)[14] == 50.0                                                    # 不漲不跌
    assert export.calc_rsi([1] * 14) == [None] * 14                                                 # 根數不足
    c = [10, 11] * 8                                                       # 一漲一跌：前 14 次平均相等 → 50；第 15 根上漲，Wilder 平滑
    r = export.calc_rsi(c)
    assert r[14] == 50.0 and R1(r[15]) == round(100 - 100 / (1 + ((0.5 * 13 + 1) / 14) / (0.5 * 13 / 14)), 1)   # 第 15 根上漲


def test_osc_stats():
    n = 20
    o, h, l, c = [10.0] * n, [11.0 + i % 3 for i in range(n)], [9.0] * n, [10.0 + i % 2 for i in range(n)]
    s = export.osc_stats(o, h, l, c, [1.0] * n)
    assert set(s) == {"k", "kx", "rsi"} and s["kx"] in (0, 1) and 0 <= s["k"] <= 100 and 0 <= s["rsi"] <= 100
    assert export.osc_stats(o, h, l, c[:-1] + [None], [1.0] * n) == {"k": None, "kx": None, "rsi": None}   # 今天無成交
    # 還原：係數 0.5 套到前半段的高、低、收，結果和直接給還原後的價格相同
    af = [0.5] * 10 + [1.0] * 10
    a = export.osc_stats(o, h, l, c, af)
    b = export.osc_stats(o, [x * k for x, k in zip(h, af)], [x * k for x, k in zip(l, af)], [x * k for x, k in zip(c, af)], [1.0] * n)
    assert a == b
    # 中間無成交：以前一個收盤畫一字線（高 = 低 = 收），和直接給一字線相同；上市前的空值略過
    c2 = c[:]; c2[12] = None
    flat = export.osc_stats([None, None] + o, [None, None] + h[:12] + [c[11]] + h[13:], [None, None] + l[:12] + [c[11]] + l[13:],
                            [None, None] + c[:12] + [c[11]] + c[13:], [1.0] * (n + 2))
    assert export.osc_stats(o, h, l, c2, [1.0] * n) == flat
    assert export.osc_stats(o[:5], h[:5], l[:5], c[:5], [1.0] * 5) == {"k": None, "kx": None, "rsi": None}   # 根數不足


def _js(fn_names):
    """逐字取出 stock.js 的函式原始碼。"""
    out = []
    for name in fn_names:
        s = STK.index(f"function {name}(")
        i, n = STK.index("{", s), 0
        for j in range(i, len(STK)):
            n += {"{": 1, "}": -1}.get(STK[j], 0)
            if n == 0:
                out.append(STK[s:j + 1]); break
    return "\n".join(out)


def test_js_matches_python():
    node = shutil.which("node")
    if not node:
        print("  （沒有 node，略過 JS 比對）"); return
    H = [10 + (i * 7) % 5 + (i % 4) * 0.3 for i in range(60)]
    L = [x - 2 - (i % 3) * 0.5 for i, x in enumerate(H)]
    C = [(a + b) / 2 + ((i % 5) - 2) * 0.2 for i, (a, b) in enumerate(zip(H, L))]
    js = _js(["calcKD", "calcRSI"]) + f"\nconst H={H},L={L},C={C};const r=calcKD(H,L,C);" \
        "console.log(JSON.stringify([r.k,r.d,calcRSI(C)]));"
    k, d, r = json.loads(subprocess.run([node, "-e", js], capture_output=True, text=True, check=True).stdout)
    pk, pd = export.calc_kd(H, L, C)
    pr = export.calc_rsi(C)
    assert [R1(x) for x in k] == [R1(x) for x in pk] and [R1(x) for x in d] == [R1(x) for x in pd]
    assert [R1(x) for x in r] == [R1(x) for x in pr]


def test_screen_keys():
    assert {"k", "kx", "rsi"} <= set(export.SCREEN_KEYS)
    src = (ROOT / "twstock" / "export.py").read_text(encoding="utf-8")
    assert "**osc_stats(o, h, l, c, af)}" in src


def test_stock_page_source():
    assert "const OSC_OPTS = [['MACD', 'MACD'], ['KD', 'KD'], ['RSI', 'RSI']];" in STK
    assert "segHTML('oscSeg', OSC_OPTS, localStore('osc', 'MACD'))" in STK          # 預設 MACD
    assert "E ? 'MACD' : localStore('osc', 'MACD'), E);" in STK                       # ETF 只有 MACD
    assert "${E ? '' : segHTML('oscSeg'" in STK and "if (!E) onSeg('oscSeg'" in STK
    assert "[mc, oSer, oVal]" in STK and "difSer" not in STK                          # 十字線同步跟著子圖
    assert "osc === 'KD' ? [k, [20, 80]] : [rsi, [30, 70]]" in STK                   # 參考線
    # 技術面卡：原本 6 項與多空判讀不變，動能一行另列
    assert "chk(c > ma5[i], '收盤 > MA5', '收盤 < MA5');" in STK and "const total = bull.length + bear.length" in STK
    assert "+ oscLine(k, d, rsi, i);" in STK and "動能（不計入多空）" in STK
    assert "KD 資料不足（需 9 根）" in STK and "RSI 資料不足（需 15 根）" in STK
    assert ".osc-line{" in CSS


def test_no_advice_words():
    seg = STK[STK.index("function oscLine("):STK.index("// ─── 第 10 輪 B5")] + APP[APP.index("function oscShare("):APP.index("function scrParse(")]
    seg += "".join(re.findall(r"\{ id: '(?:kx|rl|ru)'.*?\},\n", APP, re.S))
    for w in ("買進", "賣出", "反彈", "見底", "買點", "超賣", "超買"):
        assert w not in seg, w


def test_screen_source():
    assert "const SCREEN_GROUPS = ['流動性', '價量', '技術', '法人', '信用', '基本面', '排除'];" in APP
    for cid, opts in (("kx", "[20, 30, 50], def: 20"), ("rl", "[20, 30], def: 30"), ("ru", "[70, 80], def: 70")):
        assert f"{{ id: '{cid}', g: '技術'" in APP and opts in APP
    assert "x.kx === 1 && isNum(x.k) && x.k < v" in APP
    assert "${oscShare(conds, X, cnt, st)}" in APP and "const cs = conds.filter(c => c.osc);" in APP
    assert "X.filter(x => isNum(x.k) || isNum(x.rsi)).length" in APP                 # 分母
    assert "k: ['K值', x => x.k" in APP and "rsi: ['RSI', x => x.rsi" in APP
    pre = APP[APP.index("const SCREEN_PRESETS"):APP.index("const SCREEN_PRESETS") + 1200]
    assert "kx=" not in pre and "rl=" not in pre and "ru=" not in pre               # 不加預設組合


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"✅ {name}")
    print("全部通過")
