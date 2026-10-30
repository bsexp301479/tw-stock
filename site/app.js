// 台股資金流：單頁網站，只讀 data/ 底下的靜態 JSON（由 python -m twstock export 產生）
'use strict';

const App = {
  latest: null,
  stockCache: {},
  group: localStore('group', 'industry'),   // industry 類股 / chain 產業鏈 / concept 概念股
  watch: new Set(JSON.parse(localStore('watch', '[]'))),
};

// ─── 小工具 ─────────────────────────────────────────────
function localStore(key, fallback, value) {
  // 私密視窗或封鎖網站資料時 localStorage 會丟錯，失敗就當作沒有存
  try {
    if (value === undefined) return localStorage.getItem('tw.' + key) ?? fallback;
    localStorage.setItem('tw.' + key, value);
  } catch (e) { /* 忽略 */ }
  return fallback;
}
const $ = (sel, root = document) => root.querySelector(sel);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const fmt = (n, d = 0) => n == null || isNaN(n) ? '--' : Number(n).toLocaleString('zh-TW', { minimumFractionDigits: d, maximumFractionDigits: d });
// 股價最多兩位小數，尾數的 0 不顯示（2,415、90.9、12.35）
const pfmt = n => n == null || isNaN(n) ? '--' : Number(n).toLocaleString('zh-TW', { maximumFractionDigits: 2 });
const psgn = n => n == null ? '--' : (n > 0 ? '+' : '') + pfmt(n);                 // 價差：+1.2、-10
const sgn = (n, d = 2) => n == null ? '--' : (n > 0 ? '+' : '') + fmt(n, d);
const cls = n => n > 0 ? 'up' : n < 0 ? 'dn' : 'flat';
// 表格的漲跌欄；今天無成交的股票顯示「無成交」（收盤價為最後成交日）
const pctCell = s => s.nt ? `<td class="flat small" title="最後成交 ${s.nt}">無成交</td>` : `<td class="num ${cls(s.p)}">${sgn(s.p)}%</td>`;
// 不到 0.05 億四捨五入後是 0，避免顯示「-0.0億」
const yi = n => n == null ? '--' : Math.abs(n) < 0.05 ? '0億' : sgn(n, Math.abs(n) >= 100 ? 0 : 1) + '億';
const css = name => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

async function getJSON(url) {
  const r = await fetch(url, { cache: 'no-cache' });
  if (!r.ok) throw new Error(`${url} ${r.status}`);
  return r.json();
}
async function loadStock(code) {
  if (!App.stockCache[code]) App.stockCache[code] = await getJSON(`data/stocks/${code}.json`);
  return App.stockCache[code];
}
function saveWatch() { localStore('watch', null, JSON.stringify([...App.watch])); }
function setGroup(g) { App.group = g; localStore('group', null, g); }

function segHTML(id, options, active) {
  return `<div class="seg" id="${id}">` + options.map(([v, label]) =>
    `<button data-v="${v}" class="${v === active ? 'on' : ''}">${label}</button>`).join('') + '</div>';
}
function onSeg(id, fn) {
  $('#' + id).addEventListener('click', e => {
    const b = e.target.closest('button');
    if (b) fn(b.dataset.v);
  });
}
function groupSeg() { return segHTML('grpSeg', [['industry', '類股'], ['chain', '產業鏈'], ['concept', '概念股']], App.group); }

// ─── 路由 ───────────────────────────────────────────────
const routes = {
  today: renderToday,
  bubble: renderBubble,
  rank: renderRank,
  watch: renderWatch,
  stock: code => window.renderStock(code),
};

async function route() {
  const [, page = 'today', arg] = location.hash.split('/');
  document.querySelectorAll('[data-tab]').forEach(a => a.classList.toggle('on', a.dataset.tab === page));
  const view = $('#view');
  if (window.Plotly && $('#bubble')) Plotly.purge('bubble');
  window.disposeStockCharts?.();
  disposeFuturesChart();
  try {
    await (routes[page] || renderToday)(arg);
  } catch (e) {
    console.error(e);
    view.innerHTML = `<div class="empty">載入失敗：${esc(e.message)}</div>`;
  }
  window.scrollTo(0, 0);
}

// ─── 搜尋 ───────────────────────────────────────────────
function setupSearch() {
  const input = $('#q'), list = $('#qList');
  let hits = [], active = 0;
  const go = code => { list.hidden = true; input.value = ''; input.blur(); location.hash = '#/stock/' + code; };
  const draw = () => {
    list.innerHTML = hits.map(([c, s], i) =>
      `<a href="#/stock/${c}" class="${i === active ? 'on' : ''}"><span class="code">${c}</span>${esc(s.n)}<span class="muted small" style="margin-left:auto">${esc(s.i)}</span></a>`).join('');
    list.hidden = !hits.length;
  };
  input.addEventListener('input', () => {
    const q = input.value.trim().toLowerCase();
    if (!q || !App.latest) { hits = []; return draw(); }
    const all = Object.entries(App.latest.stocks);
    hits = all.filter(([c]) => c.startsWith(q))
      .concat(all.filter(([c, s]) => !c.startsWith(q) && s.n.toLowerCase().includes(q)))
      .slice(0, 12);
    active = 0;
    draw();
  });
  input.addEventListener('keydown', e => {
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      active = (active + (e.key === 'ArrowDown' ? 1 : hits.length - 1)) % Math.max(hits.length, 1);
      draw(); e.preventDefault();
    } else if (e.key === 'Enter' && hits[active]) go(hits[active][0]);
    else if (e.key === 'Escape') { list.hidden = true; input.blur(); }
  });
  list.addEventListener('click', e => { const a = e.target.closest('a'); if (a) { e.preventDefault(); go(a.getAttribute('href').split('/')[2]); } });
  document.addEventListener('click', e => { if (!e.target.closest('.search')) list.hidden = true; });
}

// ─── 今日 ───────────────────────────────────────────────
const QUADS = [
  ['漲潮', '加速流入'], ['輪動', '流入但放緩'], ['觀望', '流出但放緩'], ['退潮', '加速流出'],
];

function renderToday() {
  const L = App.latest, groups = L.groups[App.group];
  const span = localStore('span', '5');
  const key = span === '1' ? 'net_1d' : 'net_5d';
  const counts = Object.fromEntries(QUADS.map(([q]) => [q, groups.filter(g => g.quadrant === q).length]));
  const sorted = [...groups].sort((a, b) => b[key] - a[key]);
  const inflow = sorted.filter(g => g[key] > 0).slice(0, 8);
  const outflow = sorted.filter(g => g[key] < 0).reverse().slice(0, 8);
  const maxAbs = Math.max(1, ...groups.map(g => Math.abs(g[key])));
  const stocks = Object.entries(L.stocks).filter(([, s]) => s.n1 != null);
  const topBuy = [...stocks].sort((a, b) => b[1].n1 - a[1].n1).slice(0, 10);
  const topSell = [...stocks].sort((a, b) => a[1].n1 - b[1].n1).slice(0, 10);

  const mk = (m, label) => `<div class="card stat">
      <div class="l">${label}成交額</div>
      <div class="v num">${fmt(L.market[m].turnover)}<span class="small muted"> 億</span></div>
      <div class="s num">漲 <span class="up">${L.market[m].up}</span>　跌 <span class="dn">${L.market[m].down}</span>　平 <span class="flat">${L.market[m].flat}</span> 家</div>
    </div>`;
  const bar = (g, color) => `<div class="bar-row" data-group="${esc(g.name)}">
      <span class="nm">${esc(g.name)}</span>
      <span class="bar-track"><span class="bar-fill" style="width:${Math.abs(g[key]) / maxAbs * 100}%;background:${color}"></span></span>
      <span class="val num ${cls(g[key])}">${yi(g[key])}</span></div>`;
  const rows = list => list.map(([c, s]) => `<tr data-code="${c}">
      <td class="nm"><b>${esc(s.n)}</b><span>${c}</span></td>
      <td class="num ${cls(s.p)}">${pfmt(s.c)}</td>${pctCell(s)}
      <td class="num ${cls(s.n1)}">${yi(s.n1)}</td></tr>`).join('');

  $('#view').innerHTML = `
    <section class="sec grid g-stats">
      ${mk('TWSE', '上市')}${mk('TPEx', '上櫃')}
      <div class="card stat"><div class="l">三大法人（${L.flow_date.slice(5).replace('-', '/')}）</div>
        <div class="v num ${cls(L.insti.foreign + L.insti.trust + L.insti.dealer)}">${yi(L.insti.foreign + L.insti.trust + L.insti.dealer)}</div>
        <div class="s num">外資 <span class="${cls(L.insti.foreign)}">${yi(L.insti.foreign)}</span>　投信 <span class="${cls(L.insti.trust)}">${yi(L.insti.trust)}</span>　自營 <span class="${cls(L.insti.dealer)}">${yi(L.insti.dealer)}</span></div>
      </div>
    </section>

    ${futuresHTML(L.futures)}
    ${oiHTML(L.futures_oi, L.forecast)}

    <section class="sec">
      <div class="sec-h"><h2>資金象限</h2><span class="sp"></span>${groupSeg()}</div>
      <a class="quads" href="#/bubble">
        ${QUADS.map(([q, d]) => `<div class="quad q-${q}"><div class="t">${q}</div><div class="n num">${counts[q]}</div><div class="d">${d}</div></div>`).join('')}
      </a>
    </section>

    <section class="sec grid g2">
      <div class="card">
        <div class="sec-h"><h2>錢流去哪</h2><span class="sp"></span>${segHTML('spanSeg', [['1', '今天'], ['5', '近 5 日']], span)}</div>
        <div class="bars">${inflow.map(g => bar(g, 'var(--up)')).join('') || '<div class="empty">沒有淨流入的板塊</div>'}</div>
      </div>
      <div class="card">
        <div class="sec-h"><h2>錢從哪裡流出</h2></div>
        <div class="bars">${outflow.map(g => bar(g, 'var(--dn)')).join('') || '<div class="empty">沒有淨流出的板塊</div>'}</div>
      </div>
    </section>

    <section class="sec grid g2">
      <div class="card"><div class="sec-h"><h2>法人買超</h2><span class="muted small">當日，億</span></div>
        <div class="tbl-wrap"><table class="tbl"><thead><tr><th>股票</th><th>收盤</th><th>漲跌</th><th>買賣超</th></tr></thead><tbody>${rows(topBuy)}</tbody></table></div></div>
      <div class="card"><div class="sec-h"><h2>法人賣超</h2><span class="muted small">當日，億</span></div>
        <div class="tbl-wrap"><table class="tbl"><thead><tr><th>股票</th><th>收盤</th><th>漲跌</th><th>買賣超</th></tr></thead><tbody>${rows(topSell)}</tbody></table></div></div>
    </section>`;

  onSeg('grpSeg', v => { setGroup(v); renderToday(); });
  onSeg('spanSeg', v => { localStore('span', null, v); renderToday(); });
  $('#view').addEventListener('click', onRowClick);
  drawFutures(L.futures);
  drawOI(L.futures_oi);
}

// ─── 台指期日 K（首頁） ─────────────────────────────────
let futChart = null, oiChart = null;
function disposeFuturesChart() { futChart?.remove(); oiChart?.remove(); futChart = oiChart = null; }

const md = d => d.slice(5).replace('-', '/');

function futuresHTML(F) {
  if (!F || !F.d.length) return '';
  const k = F.d.length - 1, c = F.c[k], ch = F.ch[k], pct = ch != null && c !== ch ? ch / (c - ch) * 100 : null;
  const N = F.night;
  let night = '';
  if (N) {
    // 夜盤歸屬日 D = 前一個交易日 15:00 ~ D 05:00
    const from = [...F.d].reverse().find(d => d < N.date);
    const np = N.ch != null && N.c !== N.ch ? N.ch / (N.c - N.ch) * 100 : null;
    night = `<span>夜盤 ${from ? md(from) + ' 15:00～' : ''}${md(N.date)} 05:00　收 <b class="num ${cls(N.ch)}">${fmt(N.c)}</b>
      <span class="num ${cls(N.ch)}">${sgn(N.ch, 0)} (${sgn(np)}%)</span></span>`;
  }
  return `<section class="sec card">
      <div class="sec-h"><h2>${esc(F.name)}</h2><span class="muted small">日盤・契約 ${F.m[k]}</span>
        <span class="sp"></span><span class="muted small">拖曳平移、滾輪縮放</span></div>
      <div class="fut-head">
        <span class="s-price num ${cls(ch)}" style="font-size:26px">${fmt(c)}</span>
        <span class="s-chg num ${cls(ch)}">${ch > 0 ? '▲' : ch < 0 ? '▼' : ''} ${fmt(Math.abs(ch ?? 0))} (${sgn(pct)}%)</span>
        <span class="muted small">${F.d[k]}</span>
      </div>
      <div class="fut-sub muted small"><span>成交量 <b class="num">${fmt(F.v[k])}</b> 口</span>
        <span>未平倉 <b class="num">${fmt(F.oi[k])}</b> 口</span>${night}</div>
      <div class="kleg" id="fLegend"></div>
      <div id="fC" class="chart-box" style="height:300px"></div>
    </section>`;
}

function drawFutures(F) {
  disposeFuturesChart();
  if (!F || !F.d.length || !$('#fC') || !window.LightweightCharts) return;
  const LC = window.LightweightCharts;
  const UP = css('--up'), DN = css('--dn'), grid = css('--border');
  const T = F.d, n = T.length;
  const ma5 = calcMA(F.c, 5), ma20 = calcMA(F.c, 20);
  const pad = x => String(x).padStart(2, '0');
  const ymd = t => typeof t === 'string' ? t.split('-').map(Number) : [t.year, t.month, t.day];
  const intFmt = { type: 'custom', minMove: 1, formatter: v => fmt(v) };

  futChart = LC.createChart($('#fC'), {
    autoSize: true,
    layout: { background: { type: 'solid', color: 'transparent' }, textColor: css('--text2'), fontSize: 10 },
    grid: { vertLines: { color: grid }, horzLines: { color: grid } },
    crosshair: { mode: LC.CrosshairMode.Normal },
    rightPriceScale: { borderVisible: false, scaleMargins: { top: 0.06, bottom: 0.24 } },
    // autoSize 建立當下寬度為 0，用 setVisibleLogicalRange 會算出極小間距；固定 K 棒間距即可
    timeScale: { borderVisible: false, fixLeftEdge: true, rightOffset: 3, barSpacing: 7,
      tickMarkFormatter: (t, type) => { const [y, m, d] = ymd(t); return type === 0 ? String(y) : type === 1 ? `${m}月` : `${m}/${d}`; } },
    localization: { locale: 'zh-TW', timeFormatter: t => ymd(t).map(pad).join('/') },
  });
  const kSer = futChart.addCandlestickSeries({ upColor: UP, downColor: DN, borderUpColor: UP, borderDownColor: DN, wickUpColor: UP, wickDownColor: DN, priceFormat: intFmt });
  kSer.setData(T.map((t, i) => ({ time: t, open: F.o[i], high: F.h[i], low: F.l[i], close: F.c[i] })));
  const line = (vals, color) => futChart.addLineSeries({ color, lineWidth: 1, priceFormat: intFmt, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false })
    .setData(vals.map((v, i) => v == null ? { time: T[i] } : { time: T[i], value: v }));
  line(ma5, '#888780'); line(ma20, '#EF9F27');
  // 成交量疊在下方 20%
  const vSer = futChart.addHistogramSeries({ priceScaleId: 'vol', priceFormat: { type: 'volume' }, priceLineVisible: false, lastValueVisible: false });
  futChart.priceScale('vol').applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } });
  vSer.setData(T.map((t, i) => ({ time: t, value: F.v[i] ?? 0, color: (F.c[i] >= F.o[i] ? UP : DN) + '66' })));

  const legend = $('#fLegend');
  const show = i => {
    const ch = F.ch[i], c = cls(ch), p = ch != null && F.c[i] !== ch ? ch / (F.c[i] - ch) * 100 : null;
    const ma = (label, v, color) => v == null ? '' : `<span style="color:${color}">${label} <b style="color:${color}">${fmt(v)}</b></span>`;
    legend.innerHTML = `<span><b>${T[i]}</b></span><span>開 <b>${fmt(F.o[i])}</b></span><span>高 <b class="up">${fmt(F.h[i])}</b></span>` +
      `<span>低 <b class="dn">${fmt(F.l[i])}</b></span><span>收 <b class="${c}">${fmt(F.c[i])}</b></span>` +
      `<span class="${c}">${sgn(ch, 0)} (${sgn(p)}%)</span><span>量 <b>${fmt(F.v[i])}</b></span>` +
      ma('MA5', ma5[i], '#888780') + ma('MA20', ma20[i], '#EF9F27');
  };
  show(n - 1);
  futChart.subscribeCrosshairMove(p => {
    const i = p.time ? T.indexOf(typeof p.time === 'string' ? p.time : ymd(p.time).map(pad).join('-')) : -1;
    show(i >= 0 ? i : n - 1);
  });
}

// ─── 期貨三大法人未平倉 + 大盤漲跌預測（首頁） ────────────────
const OI_COLORS = { foreign: '#4C6EF5', trust: '#F08C00', dealer: '#AE3EC9' };
const pctTxt = v => v == null ? '--' : (v * 100).toFixed(1) + '%';

function oiHTML(O, FC) {
  if (!O) return '';
  const lots = v => `<td class="num ${cls(v)}">${v == null ? '--' : sgn(v, 0)}</td>`;
  const rows = O.inv.map(r => `<tr><td><i class="dot" style="background:${OI_COLORS[r.k]}"></i>${r.n}</td>
      <td class="num">${fmt(r.long)}</td><td class="num">${fmt(r.short)}</td>${lots(r.net)}${lots(r.chg)}${lots(r.eq)}${lots(r.eq_chg)}</tr>`).join('');
  let fc = '<div class="empty">期貨法人資料不足，無法預測</div>';
  if (FC) {
    const B = FC.backtest, beat = B.acc > B.baseline;
    const maxE = Math.max(0.05, ...FC.factors.map(f => Math.abs(f.effect)));
    const vcls = FC.view === '偏多' ? 'up' : FC.view === '偏空' ? 'dn' : 'flat';
    fc = `<div class="fc-head"><span class="fc-view ${vcls}">${FC.view}</span>
        <span>下一交易日上漲機率 <b class="num ${vcls}">${pctTxt(FC.p_up)}</b></span>
        <span class="muted small">依 ${md(FC.date)} 收盤後未平倉</span></div>
      <div class="fc-factors">${FC.factors.map(f => `<div class="fc-f" title="z 分數 ${f.z}（相對近 60 日）">
          <span class="nm">${f.name}</span><span class="num muted">${sgn(f.value, 0)} 口</span>
          <span class="fc-bar"><span style="${f.effect >= 0 ? 'left:50%' : 'right:50%'};width:${Math.abs(f.effect) / maxE * 50}%;background:var(--${f.effect >= 0 ? 'up' : 'dn'})"></span></span></div>`).join('')}
        <div class="muted small">長條往右 = 推升上漲機率，往左 = 壓低</div></div>
      <div class="fc-bt ${beat ? '' : 'warn'}">回測 ${B.from.slice(0, 7).replace('-', '/')}～${B.to.slice(0, 7).replace('-', '/')} 共 ${B.n} 天：
        命中率 <b>${pctTxt(B.acc)}</b>，「永遠猜多數方向」基準 <b>${pctTxt(B.baseline)}</b>
        ${B.conf_acc != null ? `；機率偏離 5% 以上的 ${B.conf_n} 天命中 <b>${pctTxt(B.conf_acc)}</b>` : ''}。
        ${beat ? '' : '<br>模型目前沒有勝過簡單基準，未平倉對隔日漲跌的預測力很弱，請只當作籌碼面參考。'}</div>
      <div class="fc-recent"><span class="muted small">最近 10 次</span>${FC.recent.map(([d, p, y]) =>
        `<span class="fc-dot ${(p >= 0.5) === !!y ? 'hit' : 'miss'}" title="${d} 預測上漲 ${pctTxt(p)}，實際${y ? '漲' : '跌'}">${(p >= 0.5) === !!y ? '✓' : '✗'}</span>`).join('')}</div>
      <div class="muted small">羅吉斯迴歸，特徵為約當大台淨未平倉水位與增減（相對近 60 日標準化），每 20 天以過去資料重新訓練。僅供研究，非投資建議。</div>`;
  }
  return `<section class="sec grid g2">
      <div class="card">
        <div class="sec-h"><h2>期貨法人未平倉</h2><span class="muted small">${md(O.date)}，口</span></div>
        <div class="tbl-wrap"><table class="tbl oi-tbl"><thead><tr><th></th><th>大台多單</th><th>大台空單</th><th>淨額</th><th>增減</th><th>約當大台</th><th>增減</th></tr></thead>
          <tbody>${rows}</tbody></table></div>
        <div class="ch-label">約當大台淨未平倉（大台 + 小台/4 + 微台/20）
          ${O.inv.map(r => `<span class="lg"><i style="background:${OI_COLORS[r.k]}"></i>${r.n}</span>`).join('')}</div>
        <div id="oiC" class="chart-box" style="height:160px"></div>
      </div>
      <div class="card"><div class="sec-h"><h2>大盤漲跌預測</h2><span class="muted small">台指期近月日盤</span></div>${fc}</div>
    </section>`;
}

function drawOI(O) {
  if (!O || !$('#oiC') || !window.LightweightCharts) return;
  const LC = window.LightweightCharts, grid = css('--border');
  oiChart = LC.createChart($('#oiC'), {
    autoSize: true,
    layout: { background: { type: 'solid', color: 'transparent' }, textColor: css('--text2'), fontSize: 10, attributionLogo: false },
    grid: { vertLines: { visible: false }, horzLines: { color: grid } },
    rightPriceScale: { borderVisible: false },
    timeScale: { borderVisible: false, fixLeftEdge: true, fixRightEdge: true },
    handleScroll: false, handleScale: false,
    localization: { locale: 'zh-TW', priceFormatter: v => fmt(v) },
  });
  for (const k of ['foreign', 'trust', 'dealer'])
    oiChart.addLineSeries({ color: OI_COLORS[k], lineWidth: k === 'foreign' ? 2 : 1, priceLineVisible: false, lastValueVisible: k === 'foreign' })
      .setData(O.d.map((t, i) => ({ time: t, value: O[k][i] })));
  oiChart.timeScale().fitContent();
}

function onRowClick(e) {
  const tr = e.target.closest('tr[data-code]');
  if (tr) { location.hash = '#/stock/' + tr.dataset.code; return; }
  const g = e.target.closest('[data-group]');
  if (g) { localStore('focus', null, g.dataset.group); location.hash = '#/bubble'; }
}

// ─── 泡泡圖 ─────────────────────────────────────────────
const SYMLOG_C = 1;   // 對稱對數軸的線性區間（億），讓大小差很多的板塊能放在同一張圖
const symlog = v => Math.sign(v) * Math.log10(1 + Math.abs(v) / SYMLOG_C);

function renderBubble() {
  const L = App.latest, groups = L.groups[App.group];
  const focus = localStore('focus', '');
  $('#view').innerHTML = `
    <section class="sec">
      <div class="sec-h"><h2>板塊資金泡泡圖</h2><span class="muted small">X：近 5 日法人淨流入　Y：比 20 日平均加速或放緩　大小：成交額　顏色：漲跌幅</span>
        <span class="sp"></span>${groupSeg()}</div>
      <div class="card" style="padding:6px"><div id="bubble"></div></div>
    </section>
    <section class="sec grid g2">
      <div class="card"><div class="sec-h"><h2 id="gTitle">點泡泡看成分股</h2><span class="sp"></span><span id="gMeta" class="muted small"></span></div>
        <div class="tbl-wrap panel-list"><table class="tbl" id="gTable"></table></div></div>
      <div class="card"><div class="sec-h"><h2>象限說明</h2></div>
        <div class="small" style="line-height:1.9">
          <div><b class="up">漲潮</b>：近 5 日淨流入，而且比 20 日平均更積極 → 資金正在加速進場</div>
          <div><b style="color:var(--amber)">輪動</b>：仍是淨流入，但力道比過去弱 → 可能接近尾聲、資金轉往他處</div>
          <div><b style="color:var(--blue)">觀望</b>：仍是淨流出，但賣壓比過去小 → 可能止跌、留意回流</div>
          <div><b class="dn">退潮</b>：淨流出且賣壓加大 → 資金正在撤出</div>
          <div class="muted" style="margin-top:6px">按圖下方 ▶ 可回放近 ${L.dates.length} 個交易日的變化；軸為對稱對數刻度。</div>
        </div></div>
    </section>`;
  onSeg('grpSeg', v => { setGroup(v); renderBubble(); });
  $('#view').addEventListener('click', onRowClick);
  drawBubble(groups, L.dates);
  showGroup(groups.find(g => g.name === focus) || groups[0]);
}

function drawBubble(groups, dates) {
  const text = css('--text'), text2 = css('--text2'), grid = css('--border');
  const valid = dates.map((d, k) => groups.filter(g => g.frames[k]));
  const all = valid.flatMap((gs, k) => gs.map(g => g.frames[k]));
  if (!all.length) { $('#bubble').innerHTML = '<div class="empty">法人資料不足 20 個交易日，無法計算加速度</div>'; return; }
  if (!window.Plotly) { $('#bubble').innerHTML = '<div class="empty">圖表元件載入失敗，請檢查網路後重新整理</div>'; return; }
  const limX = Math.max(...all.map(f => Math.abs(symlog(f[0])))) * 1.12;
  const limY = Math.max(...all.map(f => Math.abs(symlog(f[1])))) * 1.12;
  // 泡泡直徑：成交額開 0.4 次方後線性映射到 [minD, maxD]。各族群成交額可差上千倍，
  // 若面積直接正比成交額，小族群會縮成一個點；壓縮後仍保留大小順序。
  // 最小直徑要放得下「名稱 + 金額」兩行字
  const P = 0.4, sz = t => Math.max(t, 0) ** P;
  const tMin = sz(Math.min(...all.map(f => f[3]))), tMax = sz(Math.max(...all.map(f => f[3])));
  const width = $('#bubble').clientWidth || 800;
  const narrow = width < 600;
  const maxD = Math.min(104, Math.max(48, width / 10)), minD = narrow ? 34 : 40;
  const diam = t => tMax > tMin ? minD + (maxD - minD) * (sz(t) - tMin) / (tMax - tMin) : maxD;
  const M = { l: 56, r: 12, t: 12, b: narrow ? 112 : 96 };
  const sliderY = narrow ? -0.14 : -0.1;   // 窄螢幕的 X 軸標題離滑桿太近，往下移
  const plotW = width - M.l - M.r, plotH = ($('#bubble').clientHeight || 600) - M.t - M.b;
  const amount = v => (v > 0 ? '+' : '') + (Math.abs(v) >= 10 ? Math.round(v) : v.toFixed(1)) + '億';
  const textW = (s, f) => [...s].reduce((w, ch) => w + (ch.charCodeAt(0) > 255 ? f : f * 0.6), 0);

  // 泡泡內寫「名稱 + 近 5 日金額」，字級隨泡泡大小；名稱太長就截斷加「…」。
  // 大泡泡優先，文字會和已寫的文字重疊時這顆就不寫（滑鼠移上去仍看得到）
  const labels = (gs, xs, ys, d, k) => {
    const px = xs.map(x => M.l + (x + limX) / (2 * limX) * plotW);
    const py = ys.map(y => M.t + (limY - y) / (2 * limY) * plotH);
    const hit = (a, b) => a[0] < b[2] && b[0] < a[2] && a[1] < b[3] && b[1] < a[3];
    const placed = [], text = gs.map(() => ''), font = d.map(v => Math.max(8, Math.min(14, v * 0.2)));
    [...gs.keys()].sort((a, b) => d[b] - d[a]).forEach(i => {
      const f = font[i], room = d[i] - 6;
      let name = gs[i].name;
      if (textW(name, f) > room) {
        while (name.length > 1 && textW(name + '…', f) > room) name = name.slice(0, -1);
        name += '…';
      }
      const amt = amount(gs[i].frames[k][0]);
      const w = Math.max(textW(name, f), textW(amt, f)), h = f * 2.5;
      const box = [px[i] - w / 2, py[i] - h / 2, px[i] + w / 2, py[i] + h / 2];
      if (placed.some(b => hit(b, box))) return;
      placed.push(box);
      text[i] = `<b>${esc(name)}</b><br>${amt}`;
    });
    return { text, font };
  };

  const trace = k => {
    // 大泡泡先畫、小泡泡疊在上面，才點得到小的
    const gs = [...valid[k]].sort((a, b) => b.frames[k][3] - a.frames[k][3]);
    const d = gs.map(g => diam(g.frames[k][3]));
    const xs = gs.map(g => symlog(g.frames[k][0])), ys = gs.map(g => symlog(g.frames[k][1]));
    const lab = labels(gs, xs, ys, d, k);
    return {
      type: 'scatter', mode: 'markers+text',
      ids: gs.map(g => g.name),
      x: xs, y: ys,
      text: lab.text, textposition: 'middle center',
      customdata: gs.map(g => [g.name, ...g.frames[k]]),
      textfont: { size: lab.font, color: '#fff' },
      hovertemplate: '<b>%{customdata[0]}</b><br>近5日 %{customdata[1]:+.1f}億<br>加速度 %{customdata[2]:+.1f}億/天<br>漲跌 %{customdata[3]:+.2f}%<br>成交 %{customdata[4]:,.0f}億<extra></extra>',
      marker: {
        size: d, sizemode: 'diameter',
        color: gs.map(g => g.frames[k][2]), cmin: -4, cmax: 4,
        // 色彩壓深，白字才看得清楚
        colorscale: [[0, '#17804a'], [0.5, '#5d636b'], [1, '#c23b3b']],
        line: { width: 1, color: 'rgba(255,255,255,.45)' }, opacity: .82,
      },
    };
  };
  const last = dates.length - 1;
  // 窄螢幕刻度太密會被轉成斜的，壓到下方滑桿，所以減少刻度
  const ticksX = narrow ? [-500, -20, 0, 20, 500] : [-500, -100, -20, -5, 0, 5, 20, 100, 500];
  const ticksY = [-50, -20, -5, -1, 0, 1, 5, 20, 50];
  const axis = (ticks, lim, title, unit) => ({
    range: [-lim, lim], tickvals: ticks.map(symlog), ticktext: ticks.map(t => (t > 0 ? '+' : '') + t + unit),
    title: { text: title, font: { size: 11, color: text2 } }, zeroline: true, zerolinecolor: text2,
    gridcolor: grid, tickfont: { size: 10, color: text2 }, tickangle: 0, fixedrange: true,
  });
  const quad = (x0, x1, y0, y1, color) => ({ type: 'rect', x0, x1, y0, y1, fillcolor: color, line: { width: 0 }, layer: 'below' });
  const qLabel = (x, y, t, c) => ({ x, y, text: t, showarrow: false, font: { size: 20, color: c }, opacity: .35 });
  const layout = {
    paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)', font: { color: text },
    margin: M, showlegend: false, hovermode: 'closest', dragmode: false,
    xaxis: axis(ticksX, limX, '← 流出　近 5 日法人累計（億）　流入 →', ''),
    yaxis: axis(ticksY, limY, '↓ 放緩　　加速 ↑', ''),
    shapes: [quad(0, limX, 0, limY, css('--q-rise')), quad(0, limX, -limY, 0, css('--q-rot')),
             quad(-limX, 0, 0, limY, css('--q-watch')), quad(-limX, 0, -limY, 0, css('--q-ebb'))],
    annotations: [qLabel(limX * .88, limY * .9, '漲潮', css('--up')), qLabel(limX * .88, -limY * .9, '輪動', css('--amber')),
                  qLabel(-limX * .88, limY * .9, '觀望', css('--blue')), qLabel(-limX * .88, -limY * .9, '退潮', css('--dn'))],
    updatemenus: [{
      type: 'buttons', showactive: false, x: 0, y: sliderY - 0.03, xanchor: 'left', yanchor: 'top', direction: 'left',
      bgcolor: css('--card2'), bordercolor: grid, font: { color: text },
      buttons: [
        { label: '▶ 回放', method: 'animate', args: [null, { frame: { duration: 600, redraw: true }, transition: { duration: 450 }, fromcurrent: false, mode: 'immediate' }] },
        { label: '❚❚', method: 'animate', args: [[null], { mode: 'immediate', frame: { duration: 0 }, transition: { duration: 0 } }] },
      ],
    }],
    sliders: [{
      active: last, x: 0.16, len: 0.84, y: sliderY, yanchor: 'top', pad: { t: 0 },
      currentvalue: { prefix: '資料日 ', font: { size: 12, color: text2 } }, font: { size: 9, color: text2 },
      bgcolor: css('--card2'), bordercolor: grid, tickcolor: grid,
      steps: dates.map(d => ({ label: d.slice(5).replace('-', '/'), method: 'animate',
        args: [[d], { mode: 'immediate', frame: { duration: 300, redraw: true }, transition: { duration: 250 } }] })),
    }],
  };
  Plotly.newPlot('bubble', [trace(last)], layout, { responsive: true, displayModeBar: false }).then(gd => {
    Plotly.addFrames(gd, dates.map((d, k) => ({ name: d, data: [trace(k)] })));
    gd.on('plotly_click', ev => {
      const name = ev.points[0]?.customdata?.[0];
      const g = groups.find(x => x.name === name);
      if (g) { localStore('focus', null, name); showGroup(g); }
    });
  });
}

function showGroup(g) {
  if (!g) return;
  const S = App.latest.stocks;
  $('#gTitle').textContent = g.name;
  $('#gMeta').innerHTML = `<span class="pill">${g.quadrant}</span>　5日 <span class="${cls(g.net_5d)}">${yi(g.net_5d)}</span>　連${g.streak >= 0 ? '買' : '賣'} ${Math.abs(g.streak)} 天`;
  const rows = g.codes.filter(c => S[c]).sort((a, b) => (S[b].n5 ?? 0) - (S[a].n5 ?? 0));
  $('#gTable').innerHTML = `<thead><tr><th>股票</th><th>收盤</th><th>漲跌</th><th>法人1日</th><th>法人5日</th></tr></thead><tbody>` +
    rows.map(c => { const s = S[c]; return `<tr data-code="${c}"><td class="nm"><b>${esc(s.n)}</b><span>${c}</span></td>
      <td class="num ${cls(s.p)}">${pfmt(s.c)}</td>${pctCell(s)}
      <td class="num ${cls(s.n1)}">${yi(s.n1)}</td><td class="num ${cls(s.n5)}">${yi(s.n5)}</td></tr>`; }).join('') + '</tbody>';
}

// ─── 排行 / 自選 ────────────────────────────────────────
// [代號, 名稱, 欄位, 排序方向]；欄位 '*' 會換成 1 或 5（依「1日 / 5日」切換）
const RANKS = [
  ['n+', '法人買超', 'n*', -1], ['n-', '法人賣超', 'n*', 1],
  ['f+', '外資買超', 'f*', -1], ['f-', '外資賣超', 'f*', 1],
  ['t+', '投信買超', 't*', -1], ['t-', '投信賣超', 't*', 1],
  ['d+', '自營買超', 'd*', -1], ['d-', '自營賣超', 'd*', 1],
  ['fs', '外資連買', 'fs', -1], ['ts', '投信連買', 'ts', -1], ['s', '法人連買', 's', -1],
  ['p+', '漲幅', 'p', -1], ['p-', '跌幅', 'p', 1], ['tv', '成交額', 'tv', -1],
];
const streakTxt = v => v ? (v > 0 ? '買' : '賣') + Math.abs(v) : '--';

function stockTable(list, span = '1') {
  const k = span === '5' ? '5' : '1', lbl = k === '5' ? '5日' : '1日';
  const amt = v => `<td class="num ${cls(v)}">${yi(v)}</td>`;
  return `<div class="tbl-wrap"><table class="tbl"><thead><tr>
      <th>股票</th><th>收盤</th><th>漲跌</th><th>成交額</th><th>外資${lbl}</th><th>投信${lbl}</th><th>自營${lbl}</th><th>法人${lbl}</th>
      <th>外資連</th><th>投信連</th><th>法人連</th></tr></thead><tbody>` +
    list.map(([c, s]) => `<tr data-code="${c}">
      <td class="nm"><b>${esc(s.n)}</b><span>${c} ${esc(s.i)}</span></td>
      <td class="num ${cls(s.p)}">${pfmt(s.c)}</td>${pctCell(s)}
      <td class="num">${fmt(s.tv, 1)}億</td>
      ${amt(s['f' + k])}${amt(s['t' + k])}${amt(s['d' + k])}${amt(s['n' + k])}
      <td class="num ${cls(s.fs)}">${streakTxt(s.fs)}</td><td class="num ${cls(s.ts)}">${streakTxt(s.ts)}</td>
      <td class="num ${cls(s.s)}">${streakTxt(s.s)}</td></tr>`).join('') +
    '</tbody></table></div>';
}

function spanSeg(span) { return segHTML('rspanSeg', [['1', '1日'], ['5', '5日']], span); }

function renderRank() {
  const by = localStore('rank2', 'n+'), mkt = localStore('mkt', 'all'), span = localStore('rspan', '1');
  const [, , f, dir] = RANKS.find(r => r[0] === by) || RANKS[0];
  const field = f.replace('*', span);
  // 連買排行同天數再比較該法人的 5 日金額
  const tie = { fs: 'f5', ts: 't5', s: 'n5' }[field];
  const list = Object.entries(App.latest.stocks)
    .filter(([, s]) => s[field] != null && (mkt === 'all' || s.m === mkt))
    .sort((a, b) => dir * (a[1][field] - b[1][field]) || (tie ? (b[1][tie] ?? 0) - (a[1][tie] ?? 0) : 0)).slice(0, 50);
  $('#view').innerHTML = `<section class="sec">
      <div class="sec-h"><h2>排行</h2><span class="sp"></span>
        ${segHTML('mktSeg', [['all', '全部'], ['TWSE', '上市'], ['TPEx', '上櫃']], mkt)}
        ${spanSeg(span)}
        <select id="rankSel" class="sel">${RANKS.map(r => `<option value="${r[0]}"${r[0] === by ? ' selected' : ''}>${r[1]}</option>`).join('')}</select></div>
      <div class="card">${stockTable(list, span)}</div>
      <div class="muted small" style="margin-top:6px">金額 = 買賣超張數 × 當日收盤；1日 / 5日切換會同時改變排序與表格欄位，連買為連續買超天數。</div></section>`;
  $('#rankSel').addEventListener('change', e => { localStore('rank2', null, e.target.value); renderRank(); });
  onSeg('rspanSeg', v => { localStore('rspan', null, v); renderRank(); });
  onSeg('mktSeg', v => { localStore('mkt', null, v); renderRank(); });
  $('#view').addEventListener('click', onRowClick);
}

function renderWatch() {
  const S = App.latest.stocks, span = localStore('rspan', '1');
  const list = [...App.watch].filter(c => S[c]).map(c => [c, S[c]]);
  $('#view').innerHTML = `<section class="sec">
      <div class="sec-h"><h2>自選股</h2><span class="muted small">存在這個瀏覽器裡，換裝置不會同步</span><span class="sp"></span>${spanSeg(span)}</div>
      <div class="card">${list.length ? stockTable(list, span)
        : '<div class="empty">還沒有自選股。打開任一檔個股，按右上角「☆ 加入自選」。</div>'}</div></section>`;
  onSeg('rspanSeg', v => { localStore('rspan', null, v); renderWatch(); });
  $('#view').addEventListener('click', onRowClick);
}

// ─── 啟動 ───────────────────────────────────────────────
async function init() {
  setupSearch();
  try {
    App.latest = await getJSON('data/latest.json');
  } catch (e) {
    $('#view').innerHTML = '<div class="empty">找不到 data/latest.json，請先執行 <code>python -m twstock export</code></div>';
    return;
  }
  const L = App.latest;
  $('#dateBar').innerHTML = `資料日 ${L.date}　法人資料 ${L.flow_date}　更新於 ${L.updated_at.slice(0, 16).replace('T', ' ')}`;
  window.addEventListener('hashchange', route);
  route();
}
document.addEventListener('DOMContentLoaded', init);
