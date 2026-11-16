"""第 27 輪：UI/UX 優化（不連網、不連資料庫）。
長表格改整頁捲動＋表頭跟著頂欄、新訊號手機標籤改第二列、選股條件列固定＋符合檔數捷徑、泡泡圖 Y 軸文案、
#/today、#/rank 預設與網址正規化、個股頁 MA 圖例／最新價標籤／融資融券單一序列、處置摘要與自選事件卡、
搜尋清單 ☆ 直接加入自選、分頁標題。有 node 時逐字取出 app.js／stock.js 的函式執行（node 14 可跑）。"""
import json
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "site" / "app.js").read_text(encoding="utf-8")
STK = (ROOT / "site" / "stock.js").read_text(encoding="utf-8")
CSS = (ROOT / "site" / "app.css").read_text(encoding="utf-8")
AT = "if (!Array.prototype.at) Array.prototype.at = function (i) { return this[i < 0 ? this.length + i : i]; };\n"   # node 14


def _grab(src, name):
    m = re.search(rf"^(?:async )?function {name}\(", src, re.M)
    if m:
        i, n = src.index("{", src.index(")", m.start())), 0
        for j in range(i, len(src)):
            n += {"{": 1, "}": -1}.get(src[j], 0)
            if n == 0:
                return src[m.start():j + 1]
    m = re.search(rf"^const {name}\b", src, re.M)          # const 取到去掉行尾註解後結尾為「;」的那一行
    assert m, name
    lines = src[m.start():].splitlines()
    k = next(i for i, l in enumerate(lines) if re.sub(r"\s+//[^'`]*$", "", l).rstrip().endswith(";"))
    return "\n".join(lines[:k + 1])


def _node(js):
    node = shutil.which("node")
    if not node:
        print("  （沒有 node，略過執行）")
        return None
    return json.loads(subprocess.run([node, "-e", AT + js], capture_output=True, text=True, check=True).stdout)


def _lum(c):
    c = [int(c[i:i + 2], 16) / 255 for i in (1, 3, 5)] if isinstance(c, str) else [x / 255 for x in c]
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def _cr(a, b):
    x = sorted([_lum(a), _lum(b)])
    return (x[1] + .05) / (x[0] + .05)


# ─── D27-01：長表格整頁捲動，表頭貼在頂欄下方 ───────────────
def test_long_table_page_scroll():
    assert "max-height:calc(100vh - 140px)" not in CSS and "max-height:calc(100dvh - 170px)" not in CSS   # 不再有框內捲動
    assert ".tbl-wrap:has(tbody tr:nth-child(25)) thead th{transform:translateY(var(--th-y,0px))}" in CSS
    assert "new MutationObserver(stickHeads).observe($('#view'), { childList: true });" in APP
    assert "addEventListener('scroll', stickHeads, { passive: true });" in APP
    js = _grab(APP, "stickHeads") + r"""
const mk = (top, height, rows) => ({ style: { v: null, setProperty(k, v) { this.v = v; } }, top, height,
  getBoundingClientRect() { return { top: this.top, height: this.height }; },
  querySelector(s) { return s === 'thead' ? { offsetHeight: 30 } : rows >= 25 ? {} : null; } });
const long = mk(400, 2000, 40), short = mk(400, 300, 10);
const document = { querySelectorAll: () => [long, short] };
const $ = () => ({ getBoundingClientRect: () => ({ bottom: 56 }) });
const out = [];
for (const t of [400, 56, -500, -1990]) { long.top = t; stickHeads(); out.push(long.style.v); }
console.log(JSON.stringify({ out, short: short.style.v }));"""
    o = _node(js)
    if o is not None:
        # 表格頂端還在頂欄下方 → 0；捲過頂欄 → 位移到頂欄下緣；最多到表格最後兩列（2000 − 2×30）
        assert o == {"out": ["0px", "0px", "556px", "1940px"], "short": None}, o


# ─── D27-02：新訊號手機版標籤放第二列 ────────────────────
def test_hl_second_row():
    hl = APP[APP.index("async function renderHl()"):APP.index("// ─── 第 8 輪 F8-2")]
    assert '<div class="hl-sub">' not in hl
    assert '<tr class="hl-sub" data-code="${x.code}"><td colspan="6">${x.hl.map(hlTag).join(\'\')}</td></tr>' in hl
    assert ".tbl tr:has(+.hl-sub) td{border-bottom:0;padding-bottom:2px}.tbl tr.hl-sub td{padding-top:0;white-space:normal;box-shadow:none}" in CSS
    # 名稱欄的「代號 產業」不撐寬表格（手機 375 不橫捲）
    assert ".tbl td.nm>span{display:block;margin-left:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;width:0;min-width:100%}" in CSS


# ─── D27-03：選股條件列 ─────────────────────────────────
def test_screen_summary():
    assert "<summary>條件 ${conds.length - nx} 個${nx ? `＋排除 ${nx} 個` : ''}" in APP and "條件（已選 ${conds.length} 個）" not in APP
    assert '<button class="chip scr-go" id="scrGo">符合 ${fmt(hits.length)} 檔 ↓</button>' in APP
    assert '<div class="sec-h" id="scrRes"' in APP and "$('#scrRes').scrollIntoView()" in APP
    assert "delete st[b.dataset.x]; changed();" in APP
    assert ".scr-panel>summary{position:sticky;top:var(--top-h,56px);" in CSS and ".scr-panel[open] .scr-tags{display:none}" in CSS


# ─── D27-04：泡泡圖 Y 軸文案與標籤 ──────────────────────
def test_bubble_wording():
    # Y 軸標題由 Plotly 轉 -90° 直書，字元跟著轉：寫 ← → 畫面上才是 ↓ ↑（寫 ↓ ↑ 會變成 → ←）
    assert "'← 偏流出　近 5 日日均 − 20 日日均（億/天）　偏流入 →'" in APP and "'↓ 放緩　　加速 ↑'" not in APP and "偏流入 ↑'" not in APP
    assert "Y：近 5 日日均比 20 日日均偏流入或偏流出" in APP and "比 20 日平均加速或放緩" not in APP
    assert "加速度 %{customdata[2]" not in APP and "5日日均−20日日均 %{customdata[2]}<br>" in APP   # 第 28 輪 D28-07：customdata 先格式化
    assert "Math.max(10, Math.min(14, v * 0.2))" in APP
    assert "opacity: isDark() ? .82 : 1" in APP
    # 淺色底不透明時，最淡的綠色泡泡上白字 ≥ 4.5
    assert _cr("#ffffff", "#17804a") >= 4.5


# ─── D27-05：#/today、#/rank 預設與網址 ─────────────────
def test_default_tab_and_url():
    assert "const t0 = TODAY_TABS.some(x => x[0] === t) ? t : App.todayTab || 'ov';" in APP
    assert "if (t !== t0) history.replaceState(null, '', '#/today/' + t0);" in APP
    assert "localStore('rank2', null, App.rank2 = RANKS.some(r => r[0] === arg) ? arg : App.rank2 || 'n+');" in APP
    assert "if (arg !== by) history.replaceState(null, '', '#/rank/' + by);" in APP
    assert "disposeFuturesChart(); renderToday();" in APP


# ─── D27-06、07：個股頁 ─────────────────────────────────
def test_stock_chart_legend_and_price_line():
    assert "lastValueVisible: false, priceLineVisible: false" in STK
    assert "axisLabelTextColor: css('--on-fill')" in STK                   # 深色時標籤用深字（白字在 #ef5b5b 只有 3.3）
    for blk in re.findall(r'(?::root:not\(\[data-theme="light"\]\)|:root\[data-theme="dark"\])\{(.*?)\}', CSS, re.S):
        on = re.search(r"--on-fill:(#[0-9a-f]{3,6})", blk).group(1)
        on = "#111111" if on == "#111" else on
        for k in ("up", "dn", "flat"):
            assert _cr(on, re.search(rf"--{k}:(#[0-9a-f]{{6}})", blk).group(1)) >= 4.5, k
    assert '<span class="lg"><i style="background:${color}"></i>${label} <b>${fmt(v)}</b></span>' in APP
    assert "<b style=\"color:${color}\">" not in APP
    assert "$('#vC').after(" in STK and "#vC+.kv{" in CSS                  # 第 28 輪 D28-05：改到成交量之後


def test_margin_single_series():
    assert "segHTML('mgSeg'" in STK and "右側刻度只適用融資" not in STK
    js = "let saved = {};\nconst localStore = (k, f) => k in saved ? saved[k] : f;\n" + _grab(STK, "mgView") + r"""
const out = [];
for (const [v, G] of [[undefined, { lb: [1] }], ['sb', {}], ['lb', { lb: [1] }], ['lb', {}], ['xx', { lb: [1] }]]) {
  saved = v === undefined ? {} : { mgv: v }; out.push(mgView(G));
}
console.log(JSON.stringify(out));"""
    o = _node(js)
    if o is not None:
        assert o == ["mb", "sb", "lb", "mb", "mb"], o                          # 沒有借券資料時退回融資


# ─── D27-08：處置摘要與自選事件卡 ───────────────────────
def test_alert_summary_and_reasons():
    S = {"2360": {"n": "致茂", "m": "TWSE"}, "2314": {"n": "台揚", "m": "TWSE"}, "1709": {"n": "和益", "m": "TWSE"}}
    L = {"date": "2026-11-13", "stocks": S,
         "alerts": {"d": [["2360", "2026-11-09", "2026-11-13", "約每二分鐘撮合一次", "連續三日"]],
                    "n": [["1709", "當日沖銷比率高"]], "w": [["2314", 0, "第一款連 2 日"], ["2360", 1, "第一款連 3 日"]]}}
    js = "\n".join(_grab(APP, n) for n in ("esc", "md", "watchGrp", "alertBoard")) + f"""
const App = {{ alertAll: false, alOpen: false }};
console.log(JSON.stringify(alertBoard({json.dumps(L, ensure_ascii=False)})));"""
    o = _node(js)
    if o is not None:
        assert "即將處置 0　處置中 1　接近處置（推算）2　今日注意 1</span>" in o, o
        assert '<a class="al-row" href="#/stock/2314"><div class="al-l"><b>台揚</b>' in o and '目前 第 1 款連 2 日</div>' in o   # 差一次的理由直接顯示（第 30 輪 D30-07：一檔一列）
        assert 'title="第一款連 2 日"' not in o


def test_watch_event_card():
    names = ["fmt", "pfmt", "sgn", "cls", "pctCell", "yi", "esc", "md", "streakTxt", "holdTag", "alertBadge", "hlTag",
             "segHTML", "onSeg", "flowNote", "wCtl", "stockTable", "spanSeg", "onEtfRow", "watchGestures", "renderWatch", "etfWatchTable"]
    st = {"c": 100, "p": 1.0, "tv": 1.5, "f1": 0, "t1": 0, "d1": 0, "n1": 0, "fs": 0, "ts": 0, "s": 0, "i": "電子"}
    latest = {"date": "2026-11-13", "flow_date": "2026-11-13", "holdings": {},
              "alerts": {"n": [["1709", "當日沖銷比率 63%"]]},
              "stocks": {"2360": {**st, "n": "致茂", "dsp": ["2026-11-09", "2026-11-13"]},
                         "3008": {**st, "n": "大立光", "dsp": ["2026-11-14", "2026-11-25"]},
                         "1709": {**st, "n": "和益", "ntc": 1}},
              "etfs": {"rows": {"0050": {"n": "元大台灣50", "m": "TWSE", "c": 70.1, "ch": 0.2, "p": 0.29, "v": 50000, "tv": 35.1}}}}
    js = "\n".join(_grab(APP, n) for n in names) + f"""
const HL_KINDS = {{}};
const App = {{ latest: {json.dumps(latest, ensure_ascii=False)}, watch: new Set(['2360', '3008', '1709', '0050']) }};
const view = {{ innerHTML: '', addEventListener() {{}} }};
const $ = s => s === '#view' ? view : view.innerHTML.includes(`id="${{s.slice(1)}}"`) ? {{ addEventListener() {{}} }} : null;
const localStore = (k, f) => f, onRowClick = () => {{}};
renderWatch(); const a = view.innerHTML;
App.watch = new Set(); view.innerHTML = ''; renderWatch();
console.log(JSON.stringify({{ a, empty: view.innerHTML }}));"""
    o = _node(js)
    if o is None:
        return
    a = o["a"]
    assert "處置 11/09～11/13（最後一天）</span>" in a and "即將處置 11/14～11/25</span>" in a
    assert '<div class="muted small al-why">注意：當日沖銷比率 63%</div>' in a
    assert a.index('data-etf="0050"') < a.index('class="card w-ev"')                 # 事件卡移到 ETF 表之後
    assert '<button class="chip" id="watchFind">搜尋股票</button>' in o["empty"] and "按清單右側的 ☆ 直接加入" in o["empty"]


# ─── D27-09：搜尋清單 ☆、拖曳自動捲動 ─────────────────────
def test_search_star_and_drag():
    assert '<span class="qstar${App.watch.has(c) ? \' on\' : \'\'}" role="button" data-w="${c}"' in APP
    assert "App.watch.has(w.dataset.w) ? App.watch.delete(w.dataset.w) : App.watch.add(w.dataset.w);" in APP
    assert APP.count("list.addEventListener('click'") == 1                          # 合併成一個監聽
    assert "const v = cy < 90 ? -10 : cy > innerHeight - 90 ? 10 : 0;" in APP and "cancelAnimationFrame(raf)" in APP
    assert ".wdel::after,.wh::after{content:'';position:absolute;inset:-10px}" in CSS   # 觸控範圍 ≥ 40px


# ─── D27-10：其他小項 ───────────────────────────────────
def test_titles_and_small_fixes():
    assert "+ '｜台股資金流';" in APP and "document.title = `${data.name} ${code}｜台股資金流`;" in STK
    assert "持股日 ${md(top)}" in APP and ".sort().pop(), old = R.etfs.filter(x => x.d !== top);" in APP
    assert '<span class="nw${L.flow_date === L.date ? \' fd-eq\' : \'\'}">　法人資料 ${esc(L.flow_date)}</span>' in APP
    assert ".datebar .fd-eq{display:none}" in CSS and ".datebar{white-space:nowrap;overflow-x:auto" not in CSS


def test_quads_on_card():
    """象限卡底色疊在卡片底上（不再透出頁面底色），標題字淺／深色都 ≥ 4.5。"""
    col = {"漲潮": ("q-rise", "up"), "輪動": ("q-rot", "amber"), "觀望": ("q-watch", "blue"), "退潮": ("q-ebb", "dn")}
    blocks = [CSS[CSS.index(":root{"):]] + re.findall(r'(?::root:not\(\[data-theme="light"\]\)|:root\[data-theme="dark"\])\{(.*?)\}', CSS, re.S)
    for q, (bgk, fk) in col.items():
        assert f".q-{q}{{background:linear-gradient(var(--{bgk}),var(--{bgk})) var(--card)}}" in CSS, q
        for b in blocks:
            r, g, bb, a = map(float, re.search(rf"--{bgk}:rgba\(([\d.]+),([\d.]+),([\d.]+),([\d.]+)\)", b).groups())
            card = re.search(r"--card:(#[0-9a-f]{6})", b).group(1)
            cc = [int(card[i:i + 2], 16) for i in (1, 3, 5)]
            bg = [round(v * a + w * (1 - a)) for v, w in zip((r, g, bb), cc)]
            assert _cr(re.search(rf"--{fk}:(#[0-9a-f]{{6}})", b).group(1), bg) >= 4.5, (q, b[:20])


def test_search_star_syncs_header():
    """QA27-01：在個股頁用搜尋清單的 ☆ 切換同一檔時，頁首「★ 已加入自選」同步（只同步同一檔）。"""
    i = APP.index("if (w) {   // 第 27 輪 D27-09")
    blk = APP[i:APP.index("} else if (a)", i)]
    assert "$('#starBtn')" in blk and "location.hash.split('/')[2] === w.dataset.w" in blk
    assert "'★ 已加入自選' : '☆ 加入自選'" in blk and "classList.toggle('on', on)" in blk


def test_no_advice_words():
    seg = "".join(l for l in APP.splitlines() + STK.splitlines() + CSS.splitlines() if "第 27 輪" in l or "D27-" in l
                  or "qstar" in l or "scr-go" in l or "watchFind" in l or "偏流" in l or "接近處置（推算）" in l)
    assert seg
    seg = seg.replace("借券賣出", "")                                           # 資料欄名稱（官方「借券賣出餘額」），不是用語
    for w in ("買進", "賣出", "反彈", "見底", "買點", "超賣", "超買", "推薦", "強勢股", "飆股", "勝率", "低估", "高估", "建議"):
        assert w not in seg, w


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            print("==", name)
            fn()
            print("✅", name)
    print("全部通過")
