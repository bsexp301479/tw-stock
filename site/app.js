// 台股資金流：單頁網站，只讀 data/ 底下的靜態 JSON（由 python -m twstock export 產生）
'use strict';

const App = {
  latest: null,
  stockCache: {},
  group: localStore('group', 'industry'),   // industry 類股 / concept 概念股
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
const pfmt = n => fmt(n, 2);                                              // 股價一律兩位小數
const sgn = (n, d = 2) => n == null ? '--' : (n > 0 ? '+' : '') + fmt(n, d);
const cls = n => n > 0 ? 'up' : n < 0 ? 'dn' : 'flat';
const yi = n => n == null ? '--' : sgn(n, Math.abs(n) >= 100 ? 0 : 1) + '億';
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
function groupSeg() { return segHTML('grpSeg', [['industry', '類股'], ['concept', '概念股']], App.group); }

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
      <div class="s num"><span class="up">▲${L.market[m].up}</span>　<span class="dn">▼${L.market[m].down}</span>　<span class="flat">－${L.market[m].flat}</span></div>
    </div>`;
  const bar = (g, color) => `<div class="bar-row" data-group="${esc(g.name)}">
      <span class="nm">${esc(g.name)}</span>
      <span class="bar-track"><span class="bar-fill" style="width:${Math.abs(g[key]) / maxAbs * 100}%;background:${color}"></span></span>
      <span class="val num ${cls(g[key])}">${yi(g[key])}</span></div>`;
  const rows = list => list.map(([c, s]) => `<tr data-code="${c}">
      <td class="nm"><b>${esc(s.n)}</b><span>${c}</span></td>
      <td class="num ${cls(s.p)}">${pfmt(s.c)}</td><td class="num ${cls(s.p)}">${sgn(s.p)}%</td>
      <td class="num ${cls(s.n1)}">${yi(s.n1)}</td></tr>`).join('');

  $('#view').innerHTML = `
    <section class="sec grid g-stats">
      ${mk('TWSE', '上市')}${mk('TPEx', '上櫃')}
      <div class="card stat"><div class="l">三大法人（${L.flow_date.slice(5).replace('-', '/')}）</div>
        <div class="v num ${cls(L.insti.foreign + L.insti.trust + L.insti.dealer)}">${yi(L.insti.foreign + L.insti.trust + L.insti.dealer)}</div>
        <div class="s num">外資 <span class="${cls(L.insti.foreign)}">${yi(L.insti.foreign)}</span>　投信 <span class="${cls(L.insti.trust)}">${yi(L.insti.trust)}</span>　自營 <span class="${cls(L.insti.dealer)}">${yi(L.insti.dealer)}</span></div>
      </div>
    </section>

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
  const maxT = Math.max(...all.map(f => f[3]));
  const labelN = App.group === 'concept' ? 99 : 14;   // 類股多，只在成交額前幾大的泡泡上寫字

  const trace = k => {
    const gs = valid[k];
    const rank = [...gs].sort((a, b) => b.frames[k][3] - a.frames[k][3]).slice(0, labelN).map(g => g.name);
    return {
      type: 'scatter', mode: 'markers+text',
      ids: gs.map(g => g.name),
      x: gs.map(g => symlog(g.frames[k][0])), y: gs.map(g => symlog(g.frames[k][1])),
      text: gs.map(g => rank.includes(g.name) ? g.name : ''),
      customdata: gs.map(g => [g.name, ...g.frames[k]]),
      textfont: { size: 11, color: text },
      hovertemplate: '<b>%{customdata[0]}</b><br>近5日 %{customdata[1]:+.1f}億<br>加速度 %{customdata[2]:+.1f}億/天<br>漲跌 %{customdata[3]:+.2f}%<br>成交 %{customdata[4]:,.0f}億<extra></extra>',
      marker: {
        size: gs.map(g => g.frames[k][3]), sizemode: 'area', sizeref: 2 * maxT / (64 ** 2), sizemin: 4,
        color: gs.map(g => g.frames[k][2]), cmin: -4, cmax: 4,
        colorscale: [[0, '#1f9d5a'], [0.5, '#9a9a9a'], [1, '#d64545']],
        line: { width: 1, color: 'rgba(0,0,0,.35)' }, opacity: .85,
      },
    };
  };
  const last = dates.length - 1;
  const ticksX = [-500, -100, -20, -5, 0, 5, 20, 100, 500], ticksY = [-50, -20, -5, -1, 0, 1, 5, 20, 50];
  const axis = (ticks, lim, title, unit) => ({
    range: [-lim, lim], tickvals: ticks.map(symlog), ticktext: ticks.map(t => (t > 0 ? '+' : '') + t + unit),
    title: { text: title, font: { size: 11, color: text2 } }, zeroline: true, zerolinecolor: text2,
    gridcolor: grid, tickfont: { size: 10, color: text2 }, fixedrange: true,
  });
  const quad = (x0, x1, y0, y1, color) => ({ type: 'rect', x0, x1, y0, y1, fillcolor: color, line: { width: 0 }, layer: 'below' });
  const qLabel = (x, y, t, c) => ({ x, y, text: t, showarrow: false, font: { size: 20, color: c }, opacity: .35 });
  const layout = {
    paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)', font: { color: text },
    margin: { l: 56, r: 12, t: 12, b: 96 }, showlegend: false, hovermode: 'closest', dragmode: false,
    xaxis: axis(ticksX, limX, '← 流出　近 5 日法人累計（億）　流入 →', ''),
    yaxis: axis(ticksY, limY, '↓ 放緩　　加速 ↑', ''),
    shapes: [quad(0, limX, 0, limY, css('--q-rise')), quad(0, limX, -limY, 0, css('--q-rot')),
             quad(-limX, 0, 0, limY, css('--q-watch')), quad(-limX, 0, -limY, 0, css('--q-ebb'))],
    annotations: [qLabel(limX * .88, limY * .9, '漲潮', css('--up')), qLabel(limX * .88, -limY * .9, '輪動', css('--amber')),
                  qLabel(-limX * .88, limY * .9, '觀望', css('--blue')), qLabel(-limX * .88, -limY * .9, '退潮', css('--dn'))],
    updatemenus: [{
      type: 'buttons', showactive: false, x: 0, y: -0.13, xanchor: 'left', yanchor: 'top', direction: 'left',
      bgcolor: css('--card2'), bordercolor: grid, font: { color: text },
      buttons: [
        { label: '▶ 回放', method: 'animate', args: [null, { frame: { duration: 600, redraw: true }, transition: { duration: 450 }, fromcurrent: false, mode: 'immediate' }] },
        { label: '❚❚', method: 'animate', args: [[null], { mode: 'immediate', frame: { duration: 0 }, transition: { duration: 0 } }] },
      ],
    }],
    sliders: [{
      active: last, x: 0.16, len: 0.84, y: -0.1, yanchor: 'top', pad: { t: 0 },
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
      <td class="num ${cls(s.p)}">${pfmt(s.c)}</td><td class="num ${cls(s.p)}">${sgn(s.p)}%</td>
      <td class="num ${cls(s.n1)}">${yi(s.n1)}</td><td class="num ${cls(s.n5)}">${yi(s.n5)}</td></tr>`; }).join('') + '</tbody>';
}

// ─── 排行 / 自選 ────────────────────────────────────────
const RANKS = [
  ['n1', '法人買超', -1], ['n1a', '法人賣超', 1], ['n5', '5日買超', -1], ['p', '漲幅', -1], ['pa', '跌幅', 1], ['tv', '成交額', -1],
];

function stockTable(list) {
  return `<div class="tbl-wrap"><table class="tbl"><thead><tr>
      <th>股票</th><th>收盤</th><th>漲跌</th><th>成交額</th><th>外資</th><th>投信</th><th>自營</th><th>法人1日</th><th>法人5日</th><th>連買賣</th></tr></thead><tbody>` +
    list.map(([c, s]) => `<tr data-code="${c}">
      <td class="nm"><b>${esc(s.n)}</b><span>${c} ${esc(s.i)}</span></td>
      <td class="num ${cls(s.p)}">${pfmt(s.c)}</td><td class="num ${cls(s.p)}">${sgn(s.p)}%</td>
      <td class="num">${fmt(s.tv, 1)}億</td>
      <td class="num ${cls(s.f1)}">${yi(s.f1)}</td><td class="num ${cls(s.t1)}">${yi(s.t1)}</td><td class="num ${cls(s.d1)}">${yi(s.d1)}</td>
      <td class="num ${cls(s.n1)}">${yi(s.n1)}</td><td class="num ${cls(s.n5)}">${yi(s.n5)}</td>
      <td class="num ${cls(s.s)}">${s.s ? (s.s > 0 ? '買' : '賣') + Math.abs(s.s) : '--'}</td></tr>`).join('') +
    '</tbody></table></div>';
}

function renderRank() {
  const by = localStore('rank', 'n1'), mkt = localStore('mkt', 'all');
  const [, , dir] = RANKS.find(r => r[0] === by) || RANKS[0];
  const field = by.replace(/a$/, '');
  const list = Object.entries(App.latest.stocks)
    .filter(([, s]) => s[field] != null && (mkt === 'all' || s.m === mkt))
    .sort((a, b) => dir * (a[1][field] - b[1][field])).slice(0, 50);
  $('#view').innerHTML = `<section class="sec">
      <div class="sec-h"><h2>排行</h2><span class="sp"></span>
        ${segHTML('mktSeg', [['all', '全部'], ['TWSE', '上市'], ['TPEx', '上櫃']], mkt)}
        ${segHTML('rankSeg', RANKS.map(r => [r[0], r[1]]), by)}</div>
      <div class="card">${stockTable(list)}</div></section>`;
  onSeg('rankSeg', v => { localStore('rank', null, v); renderRank(); });
  onSeg('mktSeg', v => { localStore('mkt', null, v); renderRank(); });
  $('#view').addEventListener('click', onRowClick);
}

function renderWatch() {
  const S = App.latest.stocks;
  const list = [...App.watch].filter(c => S[c]).map(c => [c, S[c]]);
  $('#view').innerHTML = `<section class="sec">
      <div class="sec-h"><h2>自選股</h2><span class="muted small">存在這個瀏覽器裡，換裝置不會同步</span></div>
      <div class="card">${list.length ? stockTable(list)
        : '<div class="empty">還沒有自選股。打開任一檔個股，按右上角「☆ 加入自選」。</div>'}</div></section>`;
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
