"""第 14 輪（不連網、不連資料庫）：F14-1 營收年增排行（舊月份、基期低、欄寬）；F14-2 單季 EPS 年增基期過小；
F14-3 期現貨價差、結算日、換月；F14-4 殖利率位置方向、說明展開不重複、季報截止日。"""
import json, re, shutil, subprocess, sys
from datetime import date
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from twstock import export  # noqa: E402

APP = (ROOT / "site" / "app.js").read_text(encoding="utf-8")
STK = (ROOT / "site" / "stock.js").read_text(encoding="utf-8")
CSS = (ROOT / "site" / "app.css").read_text(encoding="utf-8")
D = date
# 測試用休市集合：週末以外的休市（2026 年 2 月春節、12/25）
CLOSED = {D(2026, 2, 16), D(2026, 2, 17), D(2026, 2, 18), D(2026, 2, 19), D(2026, 2, 20), D(2026, 12, 25)}


def node(script):
    return json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True, timeout=30).stdout)


def test_f143_settle_day():
    assert export.settle_day(2026, 11, CLOSED) == D(2026, 11, 18)
    assert export.settle_day(2026, 12, CLOSED) == D(2026, 12, 16)
    assert export.settle_day(2026, 2, CLOSED) == D(2026, 2, 23)                     # 2/18 春節 → 順延到週一
    assert export.settle_day(2026, 12, CLOSED | {D(2026, 12, 16)}) == D(2026, 12, 17)
    assert export.settle_day(2026, 12, CLOSED | {D(2026, 12, 16), D(2026, 12, 17)}) == D(2026, 12, 18)
    assert export.settle_day(2026, 10, CLOSED) == D(2026, 10, 21) and export.settle_day(2025, 10, CLOSED) == D(2025, 10, 15)
    assert export.settle_day(2027, 9, set()) == D(2027, 9, 15)                       # 1 日是週三 → 第三個週三是 15 日
    assert export.settle_day(2026, 7, set()) == D(2026, 7, 15) and export.settle_day(2026, 4, set()) == D(2026, 4, 15)


def test_f143_next_settle():
    assert export.next_settle(D(2026, 11, 6), CLOSED) == {"d": "2026-11-18", "n": 8}
    assert export.next_settle(D(2026, 11, 17), CLOSED) == {"d": "2026-11-18", "n": 1}
    assert export.next_settle(D(2026, 11, 18), CLOSED) == {"d": "2026-11-18", "n": 0}     # 今天結算
    assert export.next_settle(D(2026, 11, 19), CLOSED) == {"d": "2026-12-16", "n": 19}
    assert export.next_settle(D(2026, 12, 17), CLOSED)["d"] == "2027-01-20"                # 跨年
    assert export.next_settle(D(2026, 2, 19), CLOSED) == {"d": "2026-02-23", "n": 1}       # 休市日當天（不會是資料日，只驗算法）


def test_f143_spread():
    days = ["2026-02-20", "2026-02-23", "2026-02-24", "2026-11-06", "2026-11-09"]
    taiex = {"2026-02-23": 33773.26, "2026-02-24": 34700.82, "2026-11-06": 39701.64}
    got = export.futures_spread(days, [33000.0, 33840.0, 34827.0, 39786.0, 39900.0], taiex)
    assert got == [None, 66.74, 126.18, 84.36, None]                                 # 沒有加權收盤 → None（不補、不估）
    assert export.futures_spread(["2026-11-06"], [None], taiex) == [None]
    src = (ROOT / "twstock" / "export.py").read_text(encoding="utf-8")
    assert 'futures["sp"] = futures_spread(' in src and 'futures["stl"] = next_settle(' in src and "closed = load_closed(cur)" in src


def test_f141_rev_base():
    rows = export._revenue_rows([[2025, 9, 53, None, None], [2026, 8, 100, None, None], [2026, 9, 1815362, 5.0, 3425111.32]])
    assert export.rev_base(rows) == 53
    assert export.rev_base(export._revenue_rows([[2026, 9, 10, None, 5.0]])) is None          # 沒有去年同月 → None（不算基期低）
    assert export.rev_base([]) is None
    assert set(export.SCREEN_KEYS) >= {"rb", "eb"}
    assert export.revenue_stats(rows) == {"rm": 202609, "ry": 3425111.32, "rc": None, "rh": 0, "r3": 0}   # 既有欄位不變


def test_f142_fin_base():
    E = Decimal          # 資料庫的 eps 是 decimal(10,2)
    cum = {(2025, 2): (0, 0, 0, 0, E("0.30")), (2025, 3): (0, 0, 0, 0, E("0.35")), (2026, 2): (0, 0, 0, 0, E("10.00")), (2026, 3): (0, 0, 0, 0, E("46.96"))}
    assert export.fin_base(cum) == 0.05 and export.fin_screen(cum)["ey"] == 73820.0      # 晶豪科型：0.05 元 → +73,820%
    assert export.fin_base({(2026, 3): (0, 0, 0, 0, 1.0)}) is None                     # 去年同季沒有
    assert export.fin_base({(2025, 1): (0, 0, 0, 0, -0.2), (2026, 1): (0, 0, 0, 0, 1.0)}) == -0.2
    assert export.fin_base({}) is None


def test_f144_fin_due():
    assert export.fin_due_dates(202603) == ["2026-11-14", "2026-11-29"]
    assert export.fin_due_dates(202604) == ["2027-03-31", "2027-03-31"]                  # Q4 在次年，兩者相同
    assert export.fin_due_dates(202601) == ["2026-05-15", "2026-05-30"]
    src = (ROOT / "twstock" / "export.py").read_text(encoding="utf-8")
    assert '{**fp, "due": fin_due_dates(fp["q"])}' in src


def test_f14_site_source():
    # F14-1
    assert "ry: x => !(x.rm < revMonth())" in APP and "revNote(inMkt, Number(minTv))" in APP
    assert "未列入排行（選股的營收條件仍包含）" in APP and "const REV_BASE = 10000, EPS_BASE = 0.1;" in APP
    assert ".tbl .sub2{display:block;" in CSS and 'class="al al-b"' in APP
    assert "{ id: 'ry', g: '基本面', label: '營收年增 ≥ {v}%', opts: [20, 30, 50], def: 30, f: scrGe('ry'), cols: ['ry'] }" in APP   # 選股不排除
    # F14-2
    assert "epsLow(v, x.eb) ? `基期低${finTag(x)}" in APP and "epsLow(v, b) ? `基期低（去年同季 ${fmt(b, 2)} 元）`" in STK
    assert "b != null && b <= 0 && cur > 0 ? '轉盈'" in STK                                # 轉盈照舊
    # F14-3
    assert "function spreadHTML(F, k, roll)" in APP and "今天換月" in APP and "今天結算" in APP and "遇休市順延" in APP
    assert "期貨 13:45、加權指數 13:30 收盤，時間不同" in APP and "kSer.setMarkers(" in APP and "換${Number(F.m[i].slice(4))}月" in APP
    # F14-4
    assert "，越高 = 殖利率相對越高" in APP and "<br>越高 = 殖利率相對越高" in STK
    assert "本益比 <b>${fmt(x.pe?.v, 2)}</b>（${pos(x.pe)}）　淨值比 <b>${fmt(x.pb?.v, 2)}</b>（${pos(x.pb)}）" in APP   # 本益比、淨值比不變
    assert ".note-dup .note[open] summary{font-size:0}" in CSS and ".note-dup .note[open] summary i{font-size:12px" in CSS
    assert "dueTxt(P.due, App.latest.date)" in APP


# F14-4 #2：展開時隱藏短句的 5 處，以及短句中的防誤讀句必須逐字出現在原文中
DUP = [
    (APP, "ETF 借券賣出多為造市、套利與避險，不等於看空", ["不等於看空"]),
    (APP, "股票中位數，不是加權指數本益比；只是位置，不是買賣訊號", ["不是加權指數本益比", "只是位置，不是買賣訊號"]),
    (APP, "大型股影響大${big ? `（${big}）` : ''}；本站計算，不是證交所公布的數字", ["大型股影響大${big ? `（${big}）` : ''}", "不是證交所公布的數字"]),
    (STK, "張數增減包含申購贖回的影響，不一定代表看好", ["張數增減包含申購贖回的影響", "不一定代表看好"]),
    (STK, "柱：${Y} 年（藍）、${Y - 1} 年（灰）同月營收", ["同月營收"]),
]


def test_f144_note_dup():
    for src, short, musts in DUP:
        i = src.index(short)
        head = src[max(0, i - 120):i]
        assert "note-dup" in head, short                                               # 外層有 note-dup
        full = src[i + len(short):src.index("</div>", i)]                             # 同一個 noteHTML 的原文
        for m in musts:
            assert m in full, (short, m)
    assert APP.count('class="note-dup"') == 3 and STK.count("note-dup") == 2
    # 照舊（展開時短句仍顯示）：維持率、個股本益比位置、單季算法
    for s in ("noteHTML('維持率為本站自算", "noteHTML('獲利大增時本益比會落到一年低點", "noteHTML('單季、近 4 季 EPS 由累計相減"):
        src = APP if "維持率" in s else STK
        i = src.index(s)
        assert "note-dup" not in src[max(0, i - 120):i], s


def test_f14_node():
    if not shutil.which("node"):
        print("  （略過 node 部分：沒有 node）")
        return
    fmt = APP[APP.index("const fmt ="):APP.index("\n", APP.index("const sgn ="))]
    md = APP[APP.index("const md ="):APP.index("\n", APP.index("const md ="))]
    due = APP[APP.index("const dueTxt"):APP.index("\n\n", APP.index("const dueTxt"))]
    low = APP[APP.index("const REV_BASE"):APP.index("// 營收年增排行表下一行")]
    got = node(f"const isNum = v => typeof v === 'number';\n{fmt}\n{md}\n{due}\n{low}\n" + """
console.log(JSON.stringify({
  q3: dueTxt(['2026-11-14', '2026-11-29'], '2026-11-06'), q3d: dueTxt(['2026-11-14', '2026-11-29'], '2026-11-14'),
  q3g: dueTxt(['2026-11-14', '2026-11-29'], '2026-11-20'), q3f: dueTxt(['2026-11-14', '2026-11-29'], '2026-12-01'),
  q4: dueTxt(['2027-03-31', '2027-03-31'], '2027-02-01'), q4x: dueTxt(['2027-03-31', '2027-03-31'], '2027-04-01'),
  r: [revLow({ry: 3425111.32, rb: 53}), revLow({ry: 5, rb: 9999}), revLow({ry: 5, rb: 10000}), revLow({ry: 5, rb: null}), revLow({ry: null, rb: 5}), revLow({ry: 583.31, rb: -4135})],
  e: [epsLow(73820, 0.05), epsLow(5, 0.09), epsLow(5, 0.1), epsLow(5080, 0.5), epsLow(null, -0.2), epsLow(null, 0)],
}));""")
    assert got["q3"] == "一般業 11/14、金融業 11/29 截止" and got["q3d"] == got["q3"]
    assert got["q3g"] == "一般業 11/14 已截止、金融業 11/29 截止" and got["q3f"] == "一般業 11/14、金融業 11/29 已截止"
    assert got["q4"] == "03/31 截止" and got["q4"].count("03/31") == 1 and got["q4x"] == "03/31 已截止"
    assert got["r"] == [True, True, False, False, False, True]                  # 剛好 1,000 萬不算；沒有去年同月不算；去年負數算
    assert got["e"] == [True, True, False, False, False, False]                # 剛好 0.1 元不算；≤ 0（年增 null）照舊轉盈


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"✅ {name}")
    print("全部通過")
