// 個股頁：K 線 + 均線、成交量、法人買賣超、融資融券、MACD（同步拖曳/縮放），以及基本面與月營收
'use strict';

let charts = [], syncLeader = null;
const CHART_IDS = ['kC', 'vC', 'iC', 'gC', 'mC'];   // gC（融資融券）只在有 mg 時存在
// 法人買賣超堆疊柱：外資在最靠近零軸的一層，往外依序投信、自營
const INVESTORS = [['f', '外資', '#4C6EF5'], ['t', '投信', '#F08C00'], ['dl', '自營', '#AE3EC9']];

const disposeKCharts = () => { charts.forEach(c => c.remove()); charts = []; };
// 離開個股頁時一併釋放月營收圖；切換日／週／月只重建 K 線（buildCharts），不動月營收圖
window.disposeStockCharts = () => {
  disposeKCharts();
  if (window.Plotly && $('#revC')) Plotly.purge('revC');
};

const MARGIN_NOTE = { O: '停止融資', X: '停止融券', '@': '融資分配', '%': '融券分配', '!': '停止買賣' };   // 上市註記

const STOCK_TABS = [['k', '走勢'], ['chip', '籌碼'], ['fund', '基本面']];

window.renderStock = async function (code) {
  const s = App.latest.stocks[code];
  let data;
  try { data = await loadStock(code); }
  catch (e) { $('#view').innerHTML = `<div class="empty">找不到 ${esc(code)} 的資料</div>`; return; }
  const P = data.prices, n = P.d.length;
  const last = n - 1;
  // 最新一天沒成交（開高低收為 --）時，改顯示最後成交日的收盤，不算漲跌
  const traded = P.c.map((c, i) => c != null ? i : -1).filter(i => i >= 0);
  const lt = traded.at(-1) ?? last, noTrade = lt !== last;
  const close = P.c[lt];
  const prevClose = P.c[traded.at(-2)] ?? null;
  // 優先用官方漲跌價差（除權息日「收盤 − 昨收」會失真）
  const change = noTrade ? null : s?.ch ?? (prevClose != null ? close - prevClose : null);
  const pct = noTrade ? null : s?.p ?? (change != null && prevClose ? change / prevClose * 100 : null);
  const prev = noTrade ? close : change != null ? close - change : prevClose;   // 昨收（參考價）
  const mode = localStore('kmode', '日');
  const adjMode = localStore('kadj', '還原');
  const fund = data.fund || {};
  // P16：股本變動事件 90 天內，本益比與殖利率加註
  const cap = data.capchg, capSub = cap ? `${md(cap.d)} ${EV_LABEL[cap.t]}，官方值可能尚未調整` : '';
  // P9：本益比、殖利率卡的資料日（與 P16 註記並列）；值為空時說明是官方未提供
  // 第 10 輪 P24：淨值比卡也標資料日（cap = false：股本變動註記照舊只在本益比、殖利率卡）
  const fundSub = (v, cap = true) => [v == null && fund.date ? '官方未提供' : '', fund.date ? '資料 ' + md(fund.date) : '', cap ? capSub : ''].filter(Boolean).join('；');
  // 第 9 輪 F9-4（B7）：估值一年位置；股本變動、虧損、無股利、新上市時匯出沒有該欄
  const VAL = data.val;
  const valSub = (k, v) => { const x = VAL?.[k]; if (!x || v == null) return '';
    const [p, lo, hi] = x, f = n => fmt(n, 2) + (k === 'dy' ? '%' : '');
    return `一年位置 ${v <= lo ? '最低' : v >= hi ? '最高' : p + '%'}（${f(lo)}～${f(hi)}）`; };
  const subs = (...a) => a.filter(Boolean).join('<br>');
  // 第 10 輪 B5：季報（沒有任何季報的股票沒有 fin）；近 4 季 EPS 明顯高於一年前（一年前 ≤ 0 且現在 > 0，或 ≥ 1.5 倍）時加獲利說明一行
  const F = data.fin;
  const finUp = F && isNum(F.e4) && isNum(F.e4p) && F.e4 > 0 && (F.e4p <= 0 || F.e4 >= F.e4p * 1.5);
  const watching = App.watch.has(code);
  const tab = pageTab('stockTab', STOCK_TABS);          // 分頁：走勢／籌碼／基本面（頁首永遠顯示）
  const fd = md(App.latest.flow_date);
  const hlFrom = s?.hf ?? App.latest.hl_from;          // null → 已滿 52 週
  const hlSub = hlFrom ? '自 ' + hlFrom.replaceAll('-', '/') : '';
  // B2：融資融券指標卡。margin 不存在 = 尚無融資融券資料（不顯示）；null = 不在信用交易清單
  const MG = data.margin;
  const mgNote = MG?.nt && data.market === 'TWSE' ? [...MG.nt].map(ch => MARGIN_NOTE[ch]).filter(Boolean).join('、') : '';
  const mgCards = MG === undefined ? [] : MG === null ? [['信用交易', '無信用交易', 'flat', '不在融資融券清單']]
    : [['融資餘額', fmt(MG.mb) + ' 張', '', `1日 ${sgn(MG.m1, 0)}　5日 ${MG.m5 == null ? '--' : sgn(MG.m5, 0)}`],
       ['融券餘額', fmt(MG.sb) + ' 張', '', `1日 ${sgn(MG.s1, 0)}`],
       ['券資比', MG.sr == null ? '--' : fmt(MG.sr, 2) + '%', '', '資料 ' + md(MG.d)],
       ['融資使用率', MG.mu == null ? '--' : fmt(MG.mu, 2) + '%', '', mgNote ? '次一營業日' + mgNote : '資料 ' + md(MG.d)]];
  // 第 11 輪 B14：借券賣出（張；占股本用目前股數）。sbl 不存在 = 該市場最新借券日沒有這檔
  const SL = data.sbl;
  // 第 12 輪 B11：市值、週轉率（目前股數）
  const MT = data.mt, mcTxt = v => v >= 1e4 ? fmt(v / 1e4, 2) + ' 兆' : fmt(v, v >= 100 ? 0 : 1) + ' 億';
  const mtCards = [['市值', MT?.mc == null ? '--' : mcTxt(MT.mc), '', MT ? '收盤 × 目前發行股數' : '沒有發行股數資料'],
    ['週轉率', MT?.to == null ? '--' : fmt(MT.to, 2) + '%', '', MT ? `${MT.d !== P.d[last] ? md(MT.d) + '，' : ''}成交股數 ÷ 目前發行股數` : '沒有發行股數資料']];
  const slCards = !SL ? [] : [['借券賣出餘額', fmt(SL.lb) + ' 張', '', `1日 ${sgn(SL.l1, 0)}　5日 ${SL.l5 == null ? '--' : sgn(SL.l5, 0)}`],
    ['借券占股本', SL.lp == null ? '--' : fmt(SL.lp, 2) + '%', '', (SL.lx == null ? '' : `融券的 ${fmt(SL.lx, 1)} 倍　`) + '資料 ' + md(SL.d)]];

  // E2-4：主動 ETF 持有（統一、群益投信 8 檔；沒有任何一檔持有、也沒有 act 時不顯示）
  const AC = data.active, A = data.act;
  // F8-1（B16）：投信買超中已收的國內主動 ETF 張數；全部 ETF 都出清的股票沒有 active，但仍顯示這一行
  const actLine = !A ? '' : `<div class="num" style="margin-bottom:4px">${A.d === App.latest.date ? '今日' : md(A.d) + ' '}投信 <span class="${cls(A.t)}">${sgn(A.t, 0)}</span> 張，其中已收主動 ETF <span class="${cls(A.e)}">${sgn(A.e, 0)}</span> 張` +
    (A.p != null ? `（${A.p}%）` : !A.t ? '（投信合計為 0）' : (A.t > 0) !== (A.e > 0) ? '（方向與投信合計相反）'
      : `（超過投信合計：其他投信基金為${A.t > 0 ? '賣超' : '買超'}）`) +
    '</div><div class="muted small" style="margin-bottom:8px">只含統一、群益已收的國內主動 ETF（持股日與法人資料日相同）；跨境 ETF 持股日晚一天，不計入。投信合計含所有投信基金與 ETF。</div>';
  const acHTML = !AC && !A ? '' : `<section class="sec card">
      <div class="sec-h"><h2>主動 ETF 持有</h2><span class="muted small">目前只含統一、群益投信 8 檔主動 ETF</span></div>${actLine}` + (!AC ? '</section>' :
      `<div class="tbl-wrap"><table class="tbl"><thead><tr><th>ETF</th><th>張數</th><th>權重</th><th>1 日</th><th>5 日</th><th>持股日</th></tr></thead><tbody>` +
      AC.map(a => `<tr><td class="nm"><a href="#/etf/${a.e}"><b>${esc(App.latest.holdings?.[a.e]?.n || a.e)}</b><span>${a.e}</span></a>${a.new ? '<i class="al al-new">新</i>' : ''}</td>
        <td class="num">${fmt(a.l)}</td><td class="num">${fmt(a.w, 2)}%</td>
        <td class="num ${cls(a.d1)}">${a.d1 == null ? '--' : sgn(a.d1, 0)}</td><td class="num ${cls(a.d5)}">${a.d5 == null ? '--' : sgn(a.d5, 0)}</td>
        <td class="num">${md(a.d)}</td></tr>`).join('') +
      '</tbody></table></div><div class="muted small" style="margin-top:6px">' + noteHTML('張數增減包含申購贖回的影響，不一定代表看好', '張數增減包含申購贖回的影響：申購多的日子，經理人會用申購資金加碼，不一定代表看好（可對照持股頁的「單位數 1 日」）。權重為占該 ETF 淨資產 %，含股價漲跌影響。') + '</div></section>');

  $('#view').innerHTML = `
    <section class="sec card">
      <div class="s-head">
        <div>
          <div><span class="s-name">${esc(data.name)}</span><span class="s-code">${code}</span></div>
          <div><span class="s-price num ${cls(change)}">${pfmt(close)}</span>
            ${noTrade ? '<span class="s-chg flat">無成交</span>'
              : `<span class="s-chg num ${cls(change)}">${change > 0 ? '▲' : change < 0 ? '▼' : ''} ${pfmt(Math.abs(change ?? 0))} (${sgn(pct)}%)</span>`}
            ${!noTrade && s?.rel ? `<span class="muted small">相對 ${md(s.rel)} 收盤（前一交易日無成交）</span>` : ''}</div>
          <div class="tags">
            ${(data.alerts || []).map(a => a.t === 'disposal'
              ? `<span class="pill al-d" title="${esc(`處置期間 ${md(a.s)}～${md(a.e)}（${md(a.a)} 公告）\n原因：${a.r || '--'}\n措施：${a.m || '--'}`)}">${a.s > App.latest.date ? `即將處置（${md(a.s)} 起）` : `處置中（至 ${md(a.e)}）`}</span>`
              : `<span class="pill al-n" title="${esc(`${md(a.a)} 公布注意交易資訊\n${a.r || ''}`)}">注意</span>`).join('')}
            <span class="pill">${data.market === 'TWSE' ? '上市' : '上櫃'}</span><span class="pill">${esc(data.industry)}</span>
            ${(data.chains || []).map(([chain, seg, subs]) => `<span class="pill chain" title="${esc(chain)} › ${esc(seg)}${subs.length ? '：' + esc(subs.join('、')) : ''}">${esc(chain)} › ${esc(subs.length ? subs.slice(0, 2).join('、') + (subs.length > 2 ? '…' : '') : seg)}</span>`).join('')}
            ${data.concepts.map(c => `<span class="pill">${esc(c)}</span>`).join('')}
            <span class="muted small">${noTrade ? `${P.d[last]} 無成交，顯示 ${P.d[lt]} 收盤` : `${P.d[last]} 收盤`}</span>
          </div>
          <div class="s-ohlc small num muted"><span class="nw">開 <b>${pfmt(P.o[last])}</b></span>　<span class="nw">高 <b class="up">${pfmt(P.h[last])}</b></span>　<span class="nw">低 <b class="dn">${pfmt(P.l[last])}</b></span>　<span class="nw">昨收 <b>${pfmt(prev)}</b></span>　<span class="nw">量 <b>${fmt(P.v[last])}</b> 張</span></div>
        </div>
        <button class="star ${watching ? 'on' : ''}" id="starBtn">${watching ? '★ 已加入自選' : '☆ 加入自選'}</button>
      </div>
    </section>

    ${pageTabsHTML('stockTabSeg', STOCK_TABS, tab)}
    <section class="sec metrics">
      ${(tab === 'k' ? [
         [hlFrom ? '區間高' : '52週高', pfmt(s?.h52), '', hlFrom ? hlSub + '，還原' : '還原權值'],
         [hlFrom ? '區間低' : '52週低', pfmt(s?.l52), '', hlFrom ? hlSub + '，還原' : '還原權值'], ...mtCards]
        : tab === 'chip' ? [['法人1日', yi(s?.n1), cls(s?.n1), fd], ['法人5日', yi(s?.n5), cls(s?.n5), '至 ' + fd],
         ['外資5日', yi(s?.f5), cls(s?.f5), '至 ' + fd], ['投信5日', yi(s?.t5), cls(s?.t5), '至 ' + fd], ...mgCards, ...slCards]
        : [['本益比', fmt(fund.pe, 2), '', subs(fundSub(fund.pe), valSub('pe', fund.pe))], ['股價淨值比', fmt(fund.pb, 2), '', subs(fundSub(fund.pb, false), valSub('pb', fund.pb))],
         ['殖利率', fund.dy != null ? fmt(fund.dy, 2) + '%' : '--', '', subs(fundSub(fund.dy), valSub('dy', fund.dy))]])
        .map(([l, v, c, sub]) => `<div class="card stat"><div class="l">${l}</div><div class="v num ${c || ''}" style="font-size:16px">${v}</div>${sub ? `<div class="s">${sub}</div>` : ''}</div>`).join('')}
    </section>
    ${tab === 'chip' ? `${SL ? `<div class="muted small val-note">借券賣出包含避險、套利（例如 ETF、權證、可轉債避險），不等於看空，只能當作空方部位的上限。占股本以目前發行股數計算。借券資料晚上 8 點半以後才更新。</div>` : ''}
    ${acHTML}` : tab === 'fund' ? `${VAL ? `<div class="muted small val-note">${noteHTML('獲利大增時本益比會落到一年低點，位置低不代表股價便宜', `一年位置 = 近 ${App.latest.valuation?.TWSE?.days ?? 242} 個交易日中，官方值小於或等於今天的天數比例（資料 ${md(VAL.d)}）。本益比 = 股價 ÷ 近 4 季 EPS，位置也反映獲利變化：獲利下降時本益比會升高；獲利大增時本益比（淨值比也可能）會落到一年低點，例如景氣循環股在獲利高峰，不代表股價便宜。${F ? '請對照下方季報卡的近 4 季 EPS 與一年前比較。' : ''}`)}</div>` : ''}
    ${finUp ? `<div class="small val-note fin-note">近 4 季 EPS 一年前 ${fmt(F.e4p, 2)} 元 → 現在 ${fmt(F.e4, 2)} 元（${F.e4p <= 0 ? '轉盈' : fmt(F.e4 / F.e4p, 1) + ' 倍'}）：本益比會因獲利增加而下降，位置低不代表股價便宜；請看下方季報卡的單季 EPS 是否已經轉弱。</div>` : ''}
    <section class="sec grid ${F ? 'g2' : 'g-one'}">
      <div class="card"><div class="sec-h"><h2>月營收</h2><span class="sp"></span><span id="revSegBox"></span></div><div id="revBox"></div></div>
      ${F ? `<div class="card"><div class="sec-h"><h2>季報</h2><span class="muted small">${qName(F.q.at(-1)[0])}${F.c.fs ? `｜本站收錄 ${md(F.c.fs)}` : ''}｜${FIN_TBL[F.t] || ''}</span></div><div id="finBox"></div></div>` : ''}
    </section>` : `

    <section class="sec card">
      <div class="sec-h">
        ${segHTML('kSeg', [['日', '日'], ['週', '週'], ['月', '月']], mode)}
        ${segHTML('adjSeg', [['還原', '還原'], ['原始', '原始']], adjMode)}
        <button class="seg" id="latestBtn" style="padding:4px 12px;font-size:12px">回到最新</button>
        <span class="sp"></span><span class="muted small">拖曳平移、滾輪縮放</span>
      </div>
      <div class="kleg" id="kLegend"></div>
      <div id="kC" class="chart-box" style="height:320px"></div>
      <div class="ch-label">成交量（張，未還原）</div>
      <div id="vC" class="chart-box" style="height:80px"></div>
      <div class="ch-label">三大法人買賣超（張，未還原）<span id="iLegend" style="display:contents"></span></div>
      <div id="iC" class="chart-box" style="height:90px"></div>
      ${data.mg ? `<div class="ch-label">融資／融券${data.mg.lb ? '／借券賣出' : ''}餘額<span id="gUnit"></span><span id="gLegend" style="display:contents"></span></div>
      <div id="gC" class="chart-box" style="height:90px"></div>` : ''}
      <div class="ch-label">MACD (12, 26, 9)
        <span class="lg"><i style="background:#378ADD"></i>DIF</span><span class="lg"><i style="background:#EF9F27"></i>DEA</span></div>
      <div id="mC" class="chart-box" style="height:120px"></div>
    </section>

    <section class="sec card"><div class="sec-h"><h2 id="sigTitle">技術面訊號</h2></div><div id="sigBox"></div></section>`}`;

  onSeg('stockTabSeg', v => { localStore('stockTab', null, v); window.disposeStockCharts(); window.renderStock(code); });
  $('#starBtn').addEventListener('click', () => {
    App.watch.has(code) ? App.watch.delete(code) : App.watch.add(code);
    saveWatch();
    const on = App.watch.has(code);
    $('#starBtn').classList.toggle('on', on);
    $('#starBtn').textContent = on ? '★ 已加入自選' : '☆ 加入自選';
  });
  if (tab === 'fund') { renderRevenue(data.revenue); if (F) renderFin(F); }
  if (tab !== 'k') return;
  $('#adjSeg').title = '還原：依除權息、減資、面額變更調整歷史價格，最新收盤不變。均線訊號與 52 週高低一律以還原價格計算';
  // 日／週／月與還原／原始切換都重畫；技術面訊號一律用還原價（P13）
  const draw = () => {
    const m = localStore('kmode', '日'), adj = localStore('kadj', '還原') === '還原';
    buildCharts(aggregate(data, m, adj), m, data.mg, adj);
    renderSignals(aggregate(data, m, true), m);
  };
  onSeg('kSeg', m => { localStore('kmode', null, m); document.querySelectorAll('#kSeg button').forEach(b => b.classList.toggle('on', b.dataset.v === m)); draw(); });
  onSeg('adjSeg', v => { localStore('kadj', null, v); document.querySelectorAll('#adjSeg button').forEach(b => b.classList.toggle('on', b.dataset.v === v)); draw(); });
  $('#latestBtn').addEventListener('click', () => { syncLeader = charts[0]; charts[0]?.timeScale().scrollToRealTime(); });
  CHART_IDS.filter(id => $('#' + id)).forEach((id, idx) => ['mouseenter', 'pointerdown', 'touchstart', 'wheel'].forEach(t =>
    $('#' + id).addEventListener(t, () => { syncLeader = charts[idx]; }, { passive: true })));

  draw();
};

// 每天的還原係數 = 該日之後所有事件（參考價 ÷ 前收）的乘積；事件生效日與之後為 1（向後還原，最新收盤不變）
function adjFactors(dates, ev) {
  const af = new Array(dates.length).fill(1);
  let k = 1, j = ev.length - 1;
  for (let i = dates.length - 1; i >= 0; i--) {
    while (j >= 0 && ev[j].d > dates[i]) { k *= ev[j].r / ev[j].p; j--; }
    af[i] = k;
  }
  return af;
}
const EV_LABEL = { '息': '除息', '權': '除權', '權息': '除權息', '減': '減資', '面': '面額變更', '調': '股本變動' };

// ─── 日線 → 週線 / 月線（法人買賣超加總）；adj = 是否用還原價 ─────
function aggregate(data, mode, adj) {
  const P = data.prices, I = data.insti, ev = data.ev || [], G = data.mg;
  const af = adj ? adjFactors(P.d, ev) : P.d.map(() => 1);
  // F8-3：融資融券餘額；還原時乘上該日之後所有官方換算的 k（面額變更、減資），原始為官方原值
  const gk = d => adj && G?.k ? G.k.reduce((a, x) => x.d > d ? a * x.k : a, 1) : 1;
  const sc = (a, i) => a?.[i] == null ? null : Math.round(a[i] * gk(P.d[i]));
  const mgAt = i => ({ mb: sc(G?.mb, i), sb: sc(G?.sb, i), lb: sc(G?.lb, i) });   // 第 11 輪：借券（lb）同樣依官方換算
  const evAt = Object.fromEntries(ev.map(e => [e.d, e]));
  // 無成交的日子（開高低收為 --）以前一個收盤價畫一字線，時間軸保持連續；上市前的空值略過
  const rows = [];
  let prevC = null, lastD = null;
  P.d.forEach((d, i) => {
    const has = I.f[i] != null;
    const inst = { f: has ? I.f[i] : null, t: has ? I.t[i] ?? 0 : null, dl: has ? I.dl[i] ?? 0 : null };
    inst.net = has ? inst.f + inst.t + inst.dl : null;
    const e = evAt[d] ? [evAt[d]] : [];
    if (P.c[i] != null && P.o[i] != null) {
      const k = af[i], ch = P.ch?.[i] ?? null;
      // P14：上市前一個資料列無成交、中間沒有事件 → 漲跌相對最後成交日
      const rel = data.market === 'TWSE' && i && P.c[i - 1] == null && lastD
        && !ev.some(x => x.d > lastD && x.d <= d) ? lastD : null;
      rows.push({ d, o: P.o[i] * k, h: P.h[i] * k, l: P.l[i] * k, c: P.c[i] * k, v: P.v[i],
        ch: ch == null ? null : ch * k,                                         // 還原後的漲跌（元）
        pc: ch == null || P.c[i] === ch ? null : ch / (P.c[i] - ch) * 100,       // 漲跌幅以原始價計算（不受係數影響）
        rel, ev: e, ...inst, ...mgAt(i), nt: false });
      prevC = P.c[i] * k; lastD = d;
    } else if (prevC != null) {
      rows.push({ d, o: prevC, h: prevC, l: prevC, c: prevC, v: P.v[i] ?? 0, ch: null, pc: null, rel: null, ev: e, ...inst, ...mgAt(i), nt: true });
    }
  });
  if (mode === '日') return rows;
  const out = new Map();
  for (const r of rows) {
    let key = r.d.slice(0, 7) + '-01';
    if (mode === '週') {
      const dt = new Date(r.d + 'T00:00:00Z');
      dt.setUTCDate(dt.getUTCDate() - ((dt.getUTCDay() + 6) % 7));   // 該週星期一
      key = dt.toISOString().slice(0, 10);
    }
    const g = out.get(key);
    if (!g) out.set(key, { ...r, d: key, ev: [...r.ev] });
    else {
      g.h = Math.max(g.h, r.h); g.l = Math.min(g.l, r.l); g.c = r.c; g.v += r.v; g.ev = g.ev.concat(r.ev);
      g.nt = g.nt && r.nt;   // 整週/整月都沒成交才算一字線
      for (const k of ['f', 't', 'dl', 'net']) if (r[k] != null) g[k] = (g[k] ?? 0) + r[k];
      for (const k of ['mb', 'sb', 'lb']) if (r[k] != null) g[k] = r[k];   // 融資融券、借券：期間最後一個有值的餘額
    }
  }
  return [...out.values()];
}

function calcMA(arr, p) {
  return arr.map((_, i) => i < p - 1 ? null : arr.slice(i - p + 1, i + 1).reduce((a, b) => a + b, 0) / p);
}
function calcMACD(closes) {
  const ema = (a, p) => { const k = 2 / (p + 1); let e = a[0]; return a.map((v, i) => i ? (e = v * k + e * (1 - k)) : e); };
  const ef = ema(closes, 12), es = ema(closes, 26);
  const dif = ef.map((v, i) => v - es[i]), dea = ema(dif, 9);
  return { dif, dea, hist: dif.map((v, i) => v - dea[i]) };
}

function buildCharts(raw, mode, G, adj) {
  disposeKCharts();
  if (!raw.length || !window.LightweightCharts) return;
  const LC = window.LightweightCharts;
  const UP = css('--up'), DN = css('--dn'), FLAT = css('--flat'), text2 = css('--text2'), grid = css('--border');
  const T = raw.map(r => r.d), O = raw.map(r => r.o), H = raw.map(r => r.h), L = raw.map(r => r.l), C = raw.map(r => r.c), V = raw.map(r => r.v);
  const N = raw.map(r => r.net), NT = raw.map(r => r.nt);
  const ma5 = calcMA(C, 5), ma20 = calcMA(C, 20), ma60 = calcMA(C, 60);
  const { dif, dea, hist } = calcMACD(C);

  const pad = x => String(x).padStart(2, '0');
  const ymd = t => typeof t === 'string' ? t.split('-').map(Number) : [t.year, t.month, t.day];
  const tickFmt = (t, type) => {
    const [y, m, d] = ymd(t);
    if (type === 0) return String(y);
    if (mode === '月') return `${y}/${pad(m)}`;
    return type === 1 ? `${m}月` : `${m}/${d}`;
  };
  const priceFmt = { type: 'custom', minMove: 0.01, formatter: pfmt };
  const mk = (id, timeVisible, logo = false) => LC.createChart($('#' + id), {
    autoSize: true,
    layout: { background: { type: 'solid', color: 'transparent' }, textColor: text2, fontSize: 10, attributionLogo: logo },
    grid: { vertLines: { color: grid }, horzLines: { color: grid } },
    crosshair: { mode: LC.CrosshairMode.Normal },
    rightPriceScale: { borderVisible: false, minimumWidth: 76 },   // 各圖刻度同寬，K 棒才會上下對齊
    timeScale: { borderVisible: false, visible: timeVisible, fixLeftEdge: true, rightOffset: 3, tickMarkFormatter: tickFmt },
    localization: { locale: 'zh-TW', timeFormatter: t => ymd(t).map(pad).join('/') },
  });
  const line = (chart, vals, color, fmt = priceFmt) => {
    const s = chart.addLineSeries({ color, lineWidth: 1, priceFormat: fmt, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false });
    // 沒有值的位置放空白點，維持各圖每根 K 棒索引一致
    s.setData(vals.map((v, i) => v == null ? { time: T[i] } : { time: T[i], value: v }));
    return s;
  };

  const kc = mk('kC', false, true);   // 圖表庫授權要求的 TradingView 標示，主圖保留一個
  const kSer = kc.addCandlestickSeries({ upColor: UP, downColor: DN, borderUpColor: UP, borderDownColor: DN, wickUpColor: UP, wickDownColor: DN, priceFormat: priceFmt });
  // 無成交的一字線用灰色
  kSer.setData(raw.map((r, i) => ({ time: T[i], open: O[i], high: H[i], low: L[i], close: C[i],
    ...(NT[i] ? { color: FLAT, borderColor: FLAT, wickColor: FLAT } : {}) })));
  // 除權息、減資、面額變更標記（還原／原始都顯示）；週／月線同一根有多筆時合併文字
  kSer.setMarkers(raw.flatMap((r, i) => r.ev.length ? [{ time: T[i], position: 'belowBar', shape: 'arrowUp',
    color: css('--blue'), text: [...new Set(r.ev.map(e => e.t))].join('・') }] : []));
  line(kc, ma5, '#888780'); line(kc, ma20, '#EF9F27'); line(kc, ma60, '#7F77DD');

  const vc = mk('vC', false);
  const vSer = vc.addHistogramSeries({ priceFormat: { type: 'volume' }, priceLineVisible: false, lastValueVisible: false });
  vSer.setData(raw.map((r, i) => ({ time: T[i], value: V[i], color: NT[i] ? FLAT + '99' : C[i] >= O[i] ? UP + '99' : DN + '99' })));

  // 堆疊：買超與賣超各自累加，先畫最外層（合計），再畫內層蓋上去
  const ic = mk('iC', false);
  let iSer = null;
  for (const sign of [1, -1]) {
    for (let k = INVESTORS.length; k >= 1; k--) {
      const ser = ic.addHistogramSeries({ priceFormat: { type: 'volume' }, priceLineVisible: false, lastValueVisible: false });
      ser.setData(raw.map((r, i) => {
        if (r.net == null) return { time: T[i] };
        const v = INVESTORS.slice(0, k).reduce((a, [key]) => a + (sign * r[key] > 0 ? r[key] : 0), 0);
        return { time: T[i], value: v, color: INVESTORS[k - 1][2] };
      }));
      iSer = iSer || ser;
    }
  }

  // F8-3：融資（右軸）／融券（疊加軸、不顯示刻度）餘額；第 11 輪 B14：借券賣出（第三個疊加軸，不顯示刻度）
  // 三條線各自一個座標軸：借券常是融券的上百倍，同軸會把融券壓平
  const MB = raw.map(r => r.mb), SB = raw.map(r => r.sb), LB = raw.map(r => r.lb);
  let gc = null, mbSer = null;
  if (G && $('#gC')) {
    gc = mk('gC', false);
    mbSer = gc.addLineSeries({ color: '#1C7ED6', lineWidth: 1, priceFormat: { type: 'volume' }, priceLineVisible: false, lastValueVisible: false });
    mbSer.setData(MB.map((v, i) => v == null ? { time: T[i] } : { time: T[i], value: v }));
    const sbSer = gc.addLineSeries({ color: '#AE3EC9', lineWidth: 1, priceScaleId: 'sb', priceFormat: { type: 'volume' }, priceLineVisible: false, lastValueVisible: false });
    gc.priceScale('sb').applyOptions({ scaleMargins: { top: 0.1, bottom: 0.1 } });
    sbSer.setData(SB.map((v, i) => v == null ? { time: T[i] } : { time: T[i], value: v }));
    if (G.lb) {
      const lbSer = gc.addLineSeries({ color: '#E8590C', lineWidth: 1, lineStyle: 2, priceScaleId: 'lb', priceFormat: { type: 'volume' }, priceLineVisible: false, lastValueVisible: false });
      gc.priceScale('lb').applyOptions({ scaleMargins: { top: 0.1, bottom: 0.1 } });
      lbSer.setData(LB.map((v, i) => v == null ? { time: T[i] } : { time: T[i], value: v }));
    }
    // 換算事件標在包含該日期的那一根（T 中 ≤ 事件日的最後一根）
    mbSer.setMarkers((G.k || []).map(x => { let j = -1; T.forEach((t, i) => { if (t <= x.d) j = i; }); return [j, x]; }).filter(([j]) => j >= 0)
      .sort((a, b) => a[0] - b[0]).map(([j, x]) => ({ time: T[j], position: 'aboveBar', shape: 'circle', color: css('--blue'), text: EV_LABEL[x.t] + (adj ? ' 已換算' : '') })));
    $('#gUnit').textContent = (adj ? '（張；面額變更、減資前的餘額依官方換算）' : '（張，官方原始）') +
      '　右側刻度只適用融資；融券、借券各自縮放，數值看圖例';     // 第 12 輪 P26
  }

  const mc = mk('mC', true);
  const macdFmt = { type: 'price', precision: 2, minMove: 0.01 };
  const hSer = mc.addHistogramSeries({ priceFormat: macdFmt, priceLineVisible: false, lastValueVisible: false });
  hSer.setData(hist.map((v, i) => ({ time: T[i], value: v, color: v >= 0 ? 'rgba(55,138,221,.65)' : 'rgba(213,90,48,.65)' })));
  const difSer = line(mc, dif, '#378ADD', macdFmt);
  line(mc, dea, '#EF9F27', macdFmt);

  charts = [kc, vc, ic, ...(gc ? [gc] : []), mc];   // 順序與 CHART_IDS 中存在的圖一致

  // 同步：只讓滑鼠/手指所在的那張圖帶動其他圖；若每張都互相回寫，拖曳中的事件會彼此抵銷
  syncLeader = kc;
  charts.forEach(src => src.timeScale().subscribeVisibleLogicalRangeChange(r => {
    if (src !== syncLeader || !r) return;
    charts.forEach(dst => dst !== src && dst.timeScale().setVisibleLogicalRange(r));
  }));

  // 十字線同步 + 上方資訊列
  const anchors = [[kc, kSer, i => C[i]], [vc, vSer, i => V[i]], [ic, iSer, i => N[i]], ...(gc ? [[gc, mbSer, i => MB[i]]] : []), [mc, difSer, i => dif[i]]];
  const legend = $('#kLegend');
  const showLegend = i => {
    // 日線用匯出的漲跌（事件日相對參考價、前一日無成交相對最後成交）；找不到事件的不比價日為 null。週／月線用前一根收盤
    const chg = mode === '日' ? raw[i].ch : i ? C[i] - C[i - 1] : 0;
    const p = mode === '日' ? raw[i].pc : i ? chg / C[i - 1] * 100 : 0;
    const c = cls(chg);
    const ma = (label, v, color) => v == null ? '' : `<span style="color:${color}">${label} <b style="color:${color}">${pfmt(v)}</b></span>`;
    legend.innerHTML = `<span><b>${T[i]}</b></span><span>開 <b>${pfmt(O[i])}</b></span><span>高 <b class="up">${pfmt(H[i])}</b></span>` +
      `<span>低 <b class="dn">${pfmt(L[i])}</b></span><span>收 <b class="${c}">${pfmt(C[i])}</b></span>` +
      (NT[i] ? '<span class="flat">無成交</span>'
        : chg == null ? '<span class="flat" title="官方未提供漲跌，且找不到對應的除權息、減資、面額變更事件">不比價</span>'
        : `<span class="${c}">${psgn(chg)} (${sgn(p)}%)</span>`) +
      (mode === '日' && raw[i].rel ? `<span class="muted">相對 ${md(raw[i].rel)} 收盤</span>` : '') +
      raw[i].ev.map(e => `<span class="ev-note"${e.t === '調' ? ' title="依櫃買官方漲跌反推的參考價調整（減資、面額變更等）"' : ''}>` +
        `${mode === '日' ? '' : md(e.d) + ' '}${EV_LABEL[e.t]}　前收 ${pfmt(e.p)}　參考價 ${pfmt(e.r)}</span>`).join('') +
      `<span>量 <b>${fmt(V[i])}</b> 張</span>` +
      (N[i] != null ? `<span>法人 <b class="${cls(N[i])}">${sgn(N[i], 0)}</b> 張</span>` : '') +
      ma('MA5', ma5[i], '#888780') + ma('MA20', ma20[i], '#EF9F27') + ma('MA60', ma60[i], '#7F77DD');
    // 法人資料比行情晚公布：最新一根還沒有時，改顯示最近有資料的那天
    let j = i;
    if (N[j] == null && i === raw.length - 1) while (j > 0 && N[j] == null) j--;
    const r = raw[j], v = x => x == null ? '--' : sgn(x, 0);
    $('#iLegend').innerHTML = (j !== i && N[j] != null ? `<span class="muted">${T[j]}</span>` : '') +
      INVESTORS.map(([key, name, color]) =>
        `<span class="lg"><i style="background:${color}"></i>${name} <b class="num ${cls(r[key])}">${v(r[key])}</b></span>`).join('') +
      `<span class="lg">合計 <b class="num ${cls(N[j])}">${v(N[j])}</b></span>`;
    if (gc) {   // 融資融券比行情晚公布：最新一根還沒有時，改顯示最近有資料的那天
      let g = i;
      if (MB[g] == null && i === raw.length - 1) while (g > 0 && MB[g] == null) g--;
      $('#gLegend').innerHTML = (g !== i && MB[g] != null ? `<span class="muted">${T[g]}</span>` : '') +
        `<span class="lg"><i style="background:#1C7ED6"></i>融資 <b class="num">${fmt(MB[g])}</b></span>` +
        `<span class="lg"><i style="background:#AE3EC9"></i>融券 <b class="num">${fmt(SB[g])}</b></span>` +
        `<span class="lg">券資比 <b class="num">${MB[g] ? fmt(SB[g] / MB[g] * 100, 2) + '%' : '--'}</b></span>` +
        (G.lb ? `<span class="lg"><i style="background:#E8590C"></i>借券 <b class="num">${fmt(LB[g])}</b></span>` : '');
    }
  };
  let crossSyncing = false;
  anchors.forEach(([src]) => src.subscribeCrosshairMove(p => {
    if (crossSyncing) return;
    crossSyncing = true;
    const i = p.logical == null ? -1 : Math.round(p.logical);
    const inRange = p.time !== undefined && i >= 0 && i < raw.length;
    anchors.forEach(([dst, ser, val]) => {
      if (dst === src) return;
      if (inRange && val(i) != null) dst.setCrosshairPosition(val(i), T[i], ser);
      else dst.clearCrosshairPosition();
    });
    showLegend(inRange ? i : raw.length - 1);
    crossSyncing = false;
  }));
  showLegend(raw.length - 1);

  // 初始畫面：最近 N 根，往左拖曳可看更早的資料
  const VIEW = mode === '日' ? 90 : 60;
  kc.timeScale().setVisibleLogicalRange({ from: Math.max(0, raw.length - VIEW), to: raw.length - 1 + 3 });
}

const SIG_MIN = 3, MACD_MIN = 35;   // 有效訊號至少 3 項才下結論；MACD 需 26 + 9 根

function renderSignals(rows, mode) {
  const period = { '日': '日線', '週': '週線', '月': '月線' }[mode];
  $('#sigTitle').textContent = `技術面訊號（${period}）`;
  let n = rows.length;
  while (n > 0 && rows[n - 1].nt) n--;          // 最後一根無成交的一字線不納入判讀
  const C = rows.slice(0, n).map(r => r.c), i = n - 1, c = C[i];
  const ma5 = calcMA(C, 5), ma20 = calcMA(C, 20), ma60 = calcMA(C, 60);
  const bull = [], bear = [];
  const chk = (ok, yes, no) => (ok ? bull : bear).push(ok ? yes : no);
  if (ma5[i] != null) chk(c > ma5[i], '收盤 > MA5', '收盤 < MA5');
  if (ma20[i] != null) chk(c > ma20[i], '收盤 > MA20', '收盤 < MA20');
  if (ma60[i] != null) chk(c > ma60[i], '收盤 > MA60', '收盤 < MA60');
  if (ma5[i] != null && ma20[i] != null) chk(ma5[i] > ma20[i], 'MA5 > MA20', 'MA5 < MA20');
  if (n >= MACD_MIN) {
    const { dif, dea, hist } = calcMACD(C);
    chk(dif[i] > dea[i], 'DIF > DEA', 'DIF < DEA');
    chk(hist[i] > hist[i - 1], 'MACD 柱放大', 'MACD 柱縮小');
  }
  const total = bull.length + bear.length, lean = bull.length > bear.length ? 'bull' : bull.length < bear.length ? 'bear' : '';
  const tags = `<div>${bull.map(t => `<span class="tag up">${t}</span>`).join('')}${bear.map(t => `<span class="tag dn">${t}</span>`).join('')}</div>`;
  const note = (n < rows.length && n ? `最後一根（${md(rows.at(-1).d)}）無成交，以 ${md(rows[i].d)} 判讀。` : '') +
    '依均線與 MACD 機械判讀（還原價格），僅供參考。';
  $('#sigBox').innerHTML = total < SIG_MIN
    ? `<div class="signal"><div style="font-weight:600;margin-bottom:6px">資料不足，無法判讀</div>${tags}
        <div class="muted small" style="margin-top:8px">${period}只有 ${n} 根 K 棒，有效訊號 ${total} 項（至少需 ${SIG_MIN} 項；MACD 需 ${MACD_MIN} 根以上）。${note}</div></div>`
    : `<div class="signal ${lean}">
        <div style="font-weight:600;margin-bottom:6px">${{ bull: '偏多', bear: '偏空', '': '中性' }[lean]}：${bull.length} 多 ${bear.length} 空</div>
        ${tags}<div class="muted small" style="margin-top:8px">${note}</div></div>`;
}

// ─── 第 10 輪 B5：季報卡（匯出端已把累計相減成單季；q = [季別, 單季 EPS, EPS 年增 %, 毛利率 %, 營益率 %, 單季營收（千元）]）───
const FIN_TBL = { ci: '一般業', fh: '金控', basi: '銀行', bd: '證券', ins: '保險', mim: '其他' };
const qName = k => `${Math.floor(k / 100)} Q${k % 100}`;                 // 202603 → 2026 Q3
const qShort = k => `${String(k).slice(2, 4)}Q${k % 100}`;              // 202603 → 26Q3
function renderFin(F) {
  const Q = F.q, L = Q.at(-1), k = L[0], q = k % 100;
  const base = Q.find(r => r[0] === k - 100);                             // 去年同季（近 8 季內才有）
  const ey = (v, cur, b) => v != null ? sgn(v, 1) + '%' : b != null && b <= 0 && cur > 0 ? '轉盈' : '--';
  const pc1 = v => v == null ? '--' : fmt(v, 1) + '%';
  const stats = [['單季 EPS', fmt(L[1], 2), cls(L[2]), `年增 ${ey(L[2], L[1], base?.[1])}`],
    ['累計 EPS', fmt(F.c.e, 2), '', `${q === 4 ? '全年' : `1～${q * 3} 月`}，年增 ${F.c.ey == null ? '--' : sgn(F.c.ey, 1) + '%'}`],
    ...(F.t === 'ci' ? [['毛利率', pc1(L[3]), '', `去年同季 ${pc1(base?.[3])}`]] : []),
    ...(L[4] != null ? [['營益率', pc1(L[4]), '', `去年同季 ${pc1(base?.[4])}`]] : []),
    ['近 4 季 EPS', fmt(F.e4, 2), '', `一年前 ${fmt(F.e4p, 2)}`]];
  const v = Q.map(r => r[1]).filter(isNum), mx = Math.max(0, ...v), mn = Math.min(0, ...v), span = mx - mn || 1, H = 110;
  const bar = r => { const e = r[1], c = e == null ? '' : r[2] == null ? 'flat' : r[2] >= 0 ? 'up' : 'dn';
    const top = (mx - Math.max(e ?? 0, 0)) / span * H, h = e == null ? 0 : Math.max(Math.abs(e) / span * H, 1);
    return `<div class="fb" title="${qName(r[0])} 單季 EPS ${fmt(e, 2)}，年增 ${ey(r[2], e, r[6])}">
      <div class="fb-v num">${fmt(e, 2)}</div><div class="fb-a" style="height:${H}px"><b style="top:${mx / span * H}px"></b><i class="${c}" style="top:${top}px;height:${h}px"></i></div>
      <div class="fb-l">${qShort(r[0])}</div></div>`; };
  $('#finBox').innerHTML = `<div class="metrics">${stats.map(([l, x, c, sub]) => `<div class="card stat"><div class="l">${l}</div><div class="v num ${c}" style="font-size:16px">${x}</div><div class="s">${sub}</div></div>`).join('')}</div>
    <div class="ch-label">近 ${Q.length} 季單季 EPS（元）；紅／綠 = 比去年同季增加／減少，灰 = 無法比較（去年同季虧損或沒有資料）</div>
    <div class="fin-bars">${Q.map(bar).join('')}</div>
    <div class="muted small" style="margin-top:6px">${noteHTML('單季、近 4 季 EPS 由累計相減，可能和公司公告略有差異', `單季 = 本季累計 − 上一季累計（第 4 季 = 全年 − 前三季）；期中有增資或減資時，相減的 EPS 會和公司公告的單季 EPS 略有差異。近 4 季 EPS = 本季累計 + 去年全年 − 去年同季累計。官方本益比以最新股數計算，期間有增資的公司，近 4 季 EPS 會和「股價 ÷ 本益比」有差異。金融業沒有毛利率。${F.c.fs ? '' : '「本站收錄」日期只有每日收集時才記錄，補抓的季別不顯示。'}`)}</div>`;
}

function renderRevenue(rows) {
  const box = $('#revBox');
  if (!rows.length) { box.innerHTML = '<div class="empty">沒有月營收資料</div>'; return; }
  const ym = r => `${r[0]}/${String(r[1]).padStart(2, '0')}`;
  const amt = v => fmt(v / 1e5, v >= 1e7 ? 0 : v >= 1e5 ? 1 : 2);        // 千元 → 億
  const pc = v => `<td class="num ${cls(v)}">${v == null ? '--' : sgn(v) + '%'}</td>`;
  // 檢視切換：今年 vs 去年同期（預設）／近 36 個月；切換時只重畫營收這一塊
  const view = localStore('revView', 'yoy') === '36' ? '36' : 'yoy';
  $('#revSegBox').innerHTML = segHTML('revSeg', [['yoy', '今年 vs 去年'], ['36', '近 36 個月']], view);
  onSeg('revSeg', v => { localStore('revView', null, v); if (window.Plotly) Plotly.purge('revC'); renderRevenue(rows); });
  if (view === 'yoy') return renderRevenueYoY(rows, amt, pc);
  box.innerHTML = `<div class="muted small">柱：營收（億），紅／綠 = 年增正／負；線：累計年增（%，右軸）</div>
    <div id="revC" style="height:220px"></div>
    <div class="tbl-wrap"><table class="tbl"><thead><tr><th>年月</th><th>營收（億）</th><th>月增</th><th>年增</th><th>累計年增</th></tr></thead><tbody>` +
    rows.slice(-12).reverse().map(r => `<tr><td>${ym(r)}</td>
      <td class="num">${amt(r[2])}${r[6] ? `<span class="hi" title="近 ${r[6]} 年新高">★</span>` : ''}</td>${pc(r[3])}${pc(r[4])}${pc(r[5])}</tr>`).join('') +
    `</tbody></table></div>
    <div class="muted small" style="margin-top:6px">★ 近 N 年新高：營收高於之前所有月份（N 依資料涵蓋年數計算）。累計年增 = 當年 1 月至該月合計 ÷ 去年同期 − 1。</div>`;
  drawRevenue(rows.slice(-36), ym);
}

// 今年 vs 去年同期：最新資料的年度 1～M 月逐月對照去年同月（圖上去年畫滿 12 個月當參考），累計只算兩年都有資料的同期月份
function renderRevenueYoY(rows, amt, pc) {
  const last = rows.at(-1), Y = last[0], M = last[1];
  const by = new Map(rows.map(r => [r[0] * 100 + r[1], r]));
  const cur = m => by.get(Y * 100 + m), prev = m => by.get((Y - 1) * 100 + m);
  const months = Array.from({ length: M }, (_, i) => i + 1);
  const both = months.filter(m => cur(m) && prev(m));
  const sc = both.reduce((a, m) => a + cur(m)[2], 0), sp = both.reduce((a, m) => a + prev(m)[2], 0);
  const cy = sp > 0 ? (sc / sp - 1) * 100 : null;
  const rng = both.length === M ? `1～${M} 月` : `${both.length} 個同期月份`;
  $('#revBox').innerHTML = `<div class="s num" style="margin-bottom:4px">${Y} 年 ${rng}累計 <b>${amt(sc)}</b> 億，去年同期 ${amt(sp)} 億，<span class="${cls(cy)}">${cy == null ? '--' : sgn(cy) + '%'}</span></div>
    <div id="revC" style="height:220px"></div>
    <div class="tbl-wrap"><table class="tbl"><thead><tr><th>月份</th><th>${Y}（億）</th><th>${Y - 1}（億）</th><th>年增</th></tr></thead><tbody>` +
    months.slice().reverse().map(m => `<tr><td>${m} 月</td><td class="num">${cur(m) ? amt(cur(m)[2]) : '--'}</td><td class="num">${prev(m) ? amt(prev(m)[2]) : '--'}</td>${pc(cur(m)?.[4] ?? null)}</tr>`).join('') +
    `<tr><td><b>累計</b></td><td class="num"><b>${amt(sc)}</b></td><td class="num">${amt(sp)}</td>${pc(cy)}</tr></tbody></table></div>
    <div class="muted small" style="margin-top:6px">${noteHTML(`柱：${Y} 年（藍）、${Y - 1} 年（灰）同月營收`, `柱：${Y} 年（藍）與 ${Y - 1} 年（灰）同月營收；去年 ${M + 1 <= 12 ? `${M + 1}～12 月只有去年，供參考` : '全年對照'}。年增 = 今年該月 ÷ 去年同月 − 1；累計只算兩年都有資料的月份。`)}</div>`;
  if (!window.Plotly) { $('#revC').innerHTML = '<div class="empty">圖表元件載入失敗，請檢查網路後重新整理</div>'; return; }
  const x = Array.from({ length: 12 }, (_, i) => `${i + 1}月`), text2 = css('--text2'), grid = css('--border');
  const ys = y => x.map((_, i) => { const r = by.get(y * 100 + i + 1); return r ? r[2] / 1e5 : null; });
  Plotly.newPlot('revC', [
    { type: 'bar', x, y: ys(Y - 1), name: `${Y - 1}`, marker: { color: text2, opacity: 0.55 }, hovertemplate: `${Y - 1} %{y:,.2f} 億<extra></extra>` },
    { type: 'bar', x, y: ys(Y), name: `${Y}`, marker: { color: '#378ADD' }, hovertemplate: `${Y} %{y:,.2f} 億<extra></extra>` },
  ], {
    paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)', font: { size: 10, color: text2 },
    margin: { l: 44, r: 8, t: 24, b: 28 }, barmode: 'group', bargap: 0.25, hovermode: 'x unified', dragmode: false,
    showlegend: true, legend: { orientation: 'h', x: 0, y: 1.15 },
    xaxis: { type: 'category', fixedrange: true }, yaxis: { gridcolor: grid, fixedrange: true, rangemode: 'tozero' },
  }, { responsive: true, displayModeBar: false });
}

function drawRevenue(rows, ym) {
  if (!window.Plotly) { $('#revC').innerHTML = '<div class="empty">圖表元件載入失敗，請檢查網路後重新整理</div>'; return; }
  const x = rows.map(ym), text2 = css('--text2'), grid = css('--border');
  Plotly.newPlot('revC', [
    { type: 'bar', x, y: rows.map(r => r[2] / 1e5), name: '營收',
      marker: { color: rows.map(r => css(r[4] == null ? '--flat' : r[4] >= 0 ? '--up' : '--dn')) },
      hovertemplate: '營收 %{y:,.2f} 億<extra></extra>' },
    { type: 'scatter', mode: 'lines+markers', x, y: rows.map(r => r[5]), yaxis: 'y2', name: '累計年增',
      line: { color: '#378ADD', width: 2 }, marker: { size: 4 }, connectgaps: false,
      // Plotly 的 d3-format 不支援 +.2f，正負號改用 sgn() 先格式化
      customdata: rows.map(r => r[5] == null ? '--' : sgn(r[5]) + '%'),
      hovertemplate: '累計年增 %{customdata}<extra></extra>' },
  ], {
    paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)', font: { size: 10, color: text2 },
    margin: { l: 44, r: 48, t: 8, b: 28 }, showlegend: false, hovermode: 'x unified', dragmode: false,
    xaxis: { type: 'category', tickvals: x.filter(s => /\/(01|07)$/.test(s)), fixedrange: true },
    yaxis: { gridcolor: grid, fixedrange: true, rangemode: 'tozero' },
    yaxis2: { overlaying: 'y', side: 'right', ticksuffix: '%', showgrid: false, zeroline: true, zerolinecolor: grid, fixedrange: true },
  }, { responsive: true, displayModeBar: false });
}
