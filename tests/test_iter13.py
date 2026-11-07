"""第 13 輪（純前端，原始碼檢查；不連網、不連資料庫）：
F13-1 表格固定第一欄＋排序欄移到第 2 欄；F13-2 個股走勢分頁去除重複卡；F13-3 說明收合（完整文字逐字保留、防誤讀句可見）；
F13-4 指數與成交額卡；F13-5 小修四項。"""
import json, re, shutil, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "site" / "app.js").read_text(encoding="utf-8")
STK = (ROOT / "site" / "stock.js").read_text(encoding="utf-8")
CSS = (ROOT / "site" / "app.css").read_text(encoding="utf-8")


def test_f13_1_sticky_and_key_column():
    assert ".tbl th:first-child,.tbl td:first-child{position:sticky;left:0;" in CSS
    assert "function keyCol(i)" in APP and "tr.insertBefore(tr.cells[i], tr.cells[1])" in APP
    assert "keyCol(rankKeyCol(by, field, src, byAmt));" in APP
    assert "keyCol($(`#view th.sort[data-k=\"${o}\"]`)?.cellIndex);" in APP
    assert "keyCol({ tv: 4, p: 2, m1: 6, s1: 8, l1: 10, lb: 9 }[f]);" in APP and 'class="tbl etf-tbl"' in APP
    # rankKeyCol 的位置依賴各表的欄序：欄序改了這裡要一起改
    assert "<th>股票</th><th>收盤</th><th>漲跌</th><th>成交額</th><th>外資${lbl}</th><th>投信${lbl}</th><th>自營${lbl}</th><th>法人${lbl}</th>\n      <th>外資連</th><th>投信連</th><th>法人連</th>" in APP
    assert "<th>股票</th><th>收盤</th><th>漲跌</th><th>5日漲跌</th><th>融資餘額</th><th>融資${lbl}</th><th>估算（億）</th>${by === 'mr' ? '<th>增加率</th>' : ''}\n      <th>融券餘額</th><th>融券${lbl}</th><th>券資比</th><th>使用率</th>" in APP
    assert "<th>股票</th><th>收盤</th><th>漲跌</th><th>5日漲跌</th><th>借券餘額</th><th>借券${lbl}</th><th>估算（億）</th><th>占股本</th>" in APP
    assert "<th>ETF</th><th>收盤</th><th>漲跌</th><th>成交量</th><th>成交額</th><th>融資餘額</th><th>融資增減</th><th>融券餘額</th><th>融券增減</th><th>借券餘額</th><th>借券增減</th>" in APP
    if not shutil.which("node"):
        print("  （略過 node 部分：沒有 node）")
        return
    code = APP[APP.index("const STOCK_KEYS"):APP.index("// 固定欄（股票｜收盤｜漲跌｜成交額）")]
    ranks = APP[APP.index("const RANKS = ["):APP.index("const RANK_GROUPS")]
    script = code + "\n" + ranks + """
const out = {};
for (const [by, , f, , src] of RANKS) for (const span of ['1', '5']) for (const byAmt of [false, true]) {
  if (byAmt && !(by === 'm+' || by === 'm-')) continue;
  const field = (byAmt ? 'ma*' : f).replace('*', span);
  out[`${by}|${span}|${byAmt}`] = rankKeyCol(by, field, src, byAmt);
}
console.log(JSON.stringify(out));"""
    got = json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True, timeout=30).stdout)
    exp = {'n+': 7, 'f+': 4, 't+': 5, 'd+': 6, 'fs': 8, 'ts': 9, 's': 10, 'p+': 2, 'tv': 3, 'vr': 4, 'to': 4, 'dy': 4,
           'm+': 5, 'mr': 7, 's+': 8, 'sr': 9, 'mu': 10, 'l+': 6, 'lp': 7}
    for k, v in got.items():
        by, span, amt = k.split("|")
        assert v is not None and v >= 1, k
        if by in exp:
            assert v == (6 if amt == "true" else exp[by]), (k, v)


def test_f13_2_stock_k_cards():
    k = STK[STK.index("${(tab === 'k' ? ["):STK.index(": tab === 'chip' ?")]
    assert "開盤" not in k and "成交量" not in k and "昨收" not in k and "...mtCards]" in k
    assert "hlFrom ? '區間高' : '52週高'" in k and "hlFrom ? '區間低' : '52週低'" in k
    assert '<div class="s-ohlc small num muted">' in STK and "昨收 <b>${pfmt(prev)}</b>" in STK and "量 <b>${fmt(P.v[last])}</b> 張" in STK
    assert "MT.d !== P.d[last] ? md(MT.d) + '，' : ''" in STK


# 第 12 輪的完整說明（逐字），本輪只移進 <details>
FULL = [
    (APP, "維持率 = Σ(融資張數 × 1,000 × 收盤) ÷ 官方融資金額，股票＋ETF，自算、非官方；涵蓋率不足 99% 時顯示「資料不足」"),
    (APP, "參考（經驗值，非官方門檻）：大盤融資維持率跌到 140% 左右時，常伴隨融資斷頭賣壓。投資人整戶擔保維持率低於 130% 會被追繳，這是官方規定。"),
    (APP, "一年位置 = 近 ${T.days} 個交易日（${T.from.replaceAll('-', '/')} 起）中，中位數小於或等於今天的天數比例。"),
    (APP, "殖利率用去年股利。只是位置，不是買賣訊號`)}"),
    (APP, "加權本益比 = 市值合計 ÷ Σ（市值 ÷ 本益比），大型股影響大${big ? `（${big}）` : ''}；中位數反映一般股票。本站以目前股數計算、不含虧損公司，不是證交所公布的數字`)}"),
    (APP, "ETF 借券賣出多為造市、套利與避險（例如價格高於淨值時借券賣出，申購後還券），不等於看空')}"),
    (APP, "單位數 1 日：${part(cur)}"),
    (STK, "一年位置 = 近 ${App.latest.valuation?.TWSE?.days ?? 242} 個交易日中，官方值小於或等於今天的天數比例"),
    (STK, "單季 = 本季累計 − 上一季累計（第 4 季 = 全年 − 前三季）"),
    (STK, "柱：${Y} 年（藍）與 ${Y - 1} 年（灰）同月營收；去年"),
    (STK, "張數增減包含申購贖回的影響：申購多的日子，經理人會用申購資金加碼，不一定代表看好（可對照持股頁的「單位數 1 日」）。權重為占該 ETF 淨資產 %，含股價漲跌影響。')"),
]


def test_f13_3_notes():
    assert "const noteHTML = (short, full) => `<details class=\"note\"><summary>${short}<i>說明</i></summary><div>${full}</div></details>`;" in APP
    assert ".note summary{" in CSS and ".note[open] summary i::after" in CSS
    for src, s in FULL:
        assert s in src, s[:30]
    # 收合後仍可見的短句：防誤讀的意思要在 summary 內
    shorts = re.findall(r"noteHTML\((['`])(.+?)\1,", APP + STK)
    text = " ".join(s for _, s in shorts)
    for must in ["不是買賣訊號", "不是證交所公布的數字", "不等於看空", "不是官方門檻", "不一定代表看好", "位置低不代表股價便宜"]:
        assert must in text, must
    assert len(shorts) == 8, len(shorts)          # 今日頁 4（維持率兩段合一、一年位置、加權本益比、ETF 借券）＋個股頁 4；單位數 1 日另用 <details>
    # 沒有收合的防誤讀句
    assert "借券賣出含避險、套利，不等於看空；晚上 8 點半以後才更新" in APP
    assert "單位數增加 = 淨申購。申購的資金會由經理人買進股票，所以多檔單位數同時增加的日子，「合計加碼」會偏多，不全是看好。" in APP


def test_f13_4_index_cards():
    assert APP.count("家數為官方（股票）；成交額為網站自算，不含 ETF") == 1
    assert '<span class="nw">未成交 ${fmt(o.nt)}</span>' in APP and ".nw{white-space:nowrap}" in CSS
    # QA 後修正：共同說明不可是佔滿整列的格子（會把市場寬度卡擠到下一列），要和兩張成交額卡包在同一組
    assert '<div class="mk-pair"><div class="mk-cards">${mk(\'TWSE\', \'上市\')}${mk(\'TPEx\', \'上櫃\')}</div>' in APP
    assert ".g-mk .mk-pair{grid-column:span 2;" in CSS and "span-all\">家數為官方" not in APP
    assert "function indexCard(x, name, full = true)" in APP and "${full && x.s.length >= 2 ?" in APP
    assert "indexCard(L.index?.TAIEX, '加權指數', tab === 'ov')" in APP
    assert "一般股票，不含 ETF${L.breadth ? '；官方家數尚未取得，顯示自算' : ''}" in APP


def test_f13_5_small_fixes():
    assert "const nFlow = App.flowAll ? 8 : 5" in APP and "$('#flowMore')?.addEventListener('click', () => { App.flowAll = !App.flowAll; renderToday(); });" in APP
    assert ".oi-tbl th:nth-child(n+6),.oi-tbl td:nth-child(n+6){display:none}" in CSS
    assert "按名稱旁的「☆ 加入自選」" in APP and "右上角" not in APP
    assert "$('#dateBar').innerHTML = `<span class=\"nw\">資料日 ${esc(L.date)}</span>" in APP and "（依資料寫入時間）" in APP


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"✅ {name}")
    print("全部通過")
