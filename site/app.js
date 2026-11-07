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
// 表格的漲跌欄；今天無成交的股票顯示「無成交」（收盤價為最後成交日）；前一交易日無成交時 tooltip 註明相對日期
const pctCell = s => s.nt ? `<td class="flat small" title="最後成交 ${s.nt}">無成交</td>`
  : `<td class="num ${cls(s.p)}${s.rel ? ' rel' : ''}"${s.rel ? ` title="相對 ${md(s.rel)} 收盤（前一交易日無成交）"` : ''}>${sgn(s.p)}%</td>`;
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
  rank: arg => arg && arg.startsWith('screen') ? renderScreen(arg.slice(6)) : renderRank(arg),   // 第 8 輪：#/rank/screen 條件選股
  watch: renderWatch,
  etf: code => code === 'active' ? renderActive() : code ? renderHoldings(code) : renderEtf(),   // 第 7 輪：#/etf/active 彙總排行
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

  // A3：有官方家數時頭條改用官方（含漲停、跌停）；沒有時沿用網站自算
  const mk = (m, label) => { const o = L.breadth?.[m]?.o, x = L.market[m];
    return `<div class="card stat">
      <div class="l">${label}成交額</div>
      <div class="v num">${fmt(x.turnover)}<span class="small muted"> 億</span></div>
      ${o ? `<div class="s num">漲 <span class="up">${fmt(o.up)}</span>（停 ${fmt(o.ul)}）　跌 <span class="dn">${fmt(o.dn)}</span>（停 ${fmt(o.dl)}）　平 <span class="flat">${fmt(o.fl)}</span>　未成交 ${fmt(o.nt)}</div>
      <div class="s">家數為官方（股票）；成交額為網站自算，不含 ETF</div>`
      : `<div class="s num">漲 <span class="up">${x.up}</span>　跌 <span class="dn">${x.down}</span>　平 <span class="flat">${x.flat}</span> 家</div>
      <div class="s">一般股票，不含 ETF${L.breadth ? '；官方家數尚未取得，顯示自算' : ''}</div>`}
    </div>`; };
  const bar = (g, color) => `<div class="bar-row" data-group="${esc(g.name)}">
      <span class="nm">${esc(g.name)}</span>
      <span class="bar-track"><span class="bar-fill" style="width:${Math.abs(g[key]) / maxAbs * 100}%;background:${color}"></span></span>
      <span class="val num ${cls(g[key])}">${yi(g[key])}</span></div>`;
  const rows = list => list.map(([c, s]) => `<tr data-code="${c}">
      <td class="nm"><b>${esc(s.n)}</b>${alertBadge(s)}<span>${c}</span></td>
      <td class="num ${cls(s.p)}">${pfmt(s.c)}</td>${pctCell(s)}
      <td class="num ${cls(s.n1)}">${yi(s.n1)}</td></tr>`).join('');

  // 分頁：指數卡永遠顯示，其餘依分頁只輸出該頁的區塊（圖表不會畫在隱藏的容器裡）
  const tab = pageTab('todayTab', TODAY_TABS);
  const fut = `${futuresHTML(L.futures)}${oiHTML(L.futures_oi, L.forecast)}`;
  const body = {
    ov: `<section class="sec grid g-stats g-mk">
      ${mk('TWSE', '上市')}${mk('TPEx', '上櫃')}
      ${breadthCard(L)}
    </section>

    <section class="sec">
      <div class="sec-h"><h2>資金象限</h2><span class="sp"></span>${groupSeg()}</div>
      <a class="quads" href="#/bubble">
        ${QUADS.map(([q, d]) => `<div class="quad q-${q}"><div class="t">${q}</div><div class="n num">${counts[q]}</div><div class="d">${d}</div></div>`).join('')}
      </a>
    </section>`,
    credit: `<section class="sec grid ${marginCard(L) && valCard(L) ? 'g2' : 'g-one'}">${marginCard(L)}${valCard(L)}</section>`,   // 信用交易、估值左右並排
    fut: fut.trim() || '<div class="empty">沒有期貨資料</div>',
  };
  body.flow = `<section class="sec grid ${L.insti_official ? 'g2' : 'g-one'}">${instiCard(L)}</section>
    <section class="sec grid g2">
      <div class="card">
        <div class="sec-h"><h2>錢流去哪</h2><span class="muted small">估算，不含 ETF</span><span class="sp"></span>${segHTML('spanSeg', [['1', '今天'], ['5', '近 5 日']], span)}</div>
        <div class="bars">${inflow.map(g => bar(g, 'var(--up)')).join('') || '<div class="empty">沒有淨流入的板塊</div>'}</div>
      </div>
      <div class="card">
        <div class="sec-h"><h2>錢從哪裡流出</h2></div>
        <div class="bars">${outflow.map(g => bar(g, 'var(--dn)')).join('') || '<div class="empty">沒有淨流出的板塊</div>'}</div>
      </div>
    </section>

    ${flowNote()}<section class="sec grid g2">
      <div class="card"><div class="sec-h"><h2>法人買超</h2><span class="muted small">${md(L.flow_date)}，億，估算，不含 ETF</span></div>
        <div class="tbl-wrap"><table class="tbl"><thead><tr><th>股票</th><th>收盤</th><th>漲跌</th><th>買賣超</th></tr></thead><tbody>${rows(topBuy)}</tbody></table></div></div>
      <div class="card"><div class="sec-h"><h2>法人賣超</h2><span class="muted small">${md(L.flow_date)}，億，估算，不含 ETF</span></div>
        <div class="tbl-wrap"><table class="tbl"><thead><tr><th>股票</th><th>收盤</th><th>漲跌</th><th>買賣超</th></tr></thead><tbody>${rows(topSell)}</tbody></table></div></div>
    </section>
    ${activeCard(L.active_rank)}`;

  $('#view').innerHTML = `
    <section class="sec grid g-stats">${indexCard(L.index?.TAIEX, '加權指數')}${indexCard(L.index?.TPEX, '櫃買指數')}</section>
    ${pageTabsHTML('todayTabSeg', TODAY_TABS, tab)}
    ${body[tab]}`;

  onSeg('todayTabSeg', v => { localStore('todayTab', null, v); disposeFuturesChart(); renderToday(); });
  if ($('#grpSeg')) onSeg('grpSeg', v => { setGroup(v); renderToday(); });
  if ($('#spanSeg')) onSeg('spanSeg', v => { localStore('span', null, v); renderToday(); });
  $('#view').addEventListener('click', onRowClick);
  if (tab === 'fut') { drawFutures(L.futures); drawOI(L.futures_oi); }
}

// 首頁、個股頁的分頁（記住上次選的分頁；存的值不在清單裡就用第一個）
const TODAY_TABS = [['ov', '總覽'], ['flow', '法人資金'], ['credit', '信用估值'], ['fut', '期貨']];
function pageTab(key, tabs) {
  const v = localStore(key, tabs[0][0]);
  return tabs.some(t => t[0] === v) ? v : tabs[0][0];
}
function pageTabsHTML(id, tabs, active) { return `<div class="sec page-tabs">${segHTML(id, tabs, active)}</div>`; }

// ─── 台指期日 K（首頁） ─────────────────────────────────
let futChart = null, oiChart = null;
function disposeFuturesChart() { futChart?.remove(); oiChart?.remove(); futChart = oiChart = null; }

const md = d => d.slice(5).replace('-', '/');

// 法人資料比行情晚公布時的提示；兩者同日回傳空字串
function flowNote() {
  const L = App.latest;
  return L.flow_date === L.date ? ''
    : `<div class="flow-note">法人資料尚未更新：收盤、漲跌為 ${md(L.date)}，法人欄位為 ${md(L.flow_date)}</div>`;
}

// 名稱旁的處置／注意小標記（latest.json 只放有效的警示）
const alertBadge = s =>
  (s.dsp ? `<i class="al al-d" title="${s.dsp[0] > App.latest.date ? `即將處置（${md(s.dsp[0])} 起）` : `處置中（至 ${md(s.dsp[1])}）`}">處</i>` : '') +
  (s.ntc ? '<i class="al al-n" title="注意股（當日公布注意交易資訊）">注</i>' : '');

// ─── 加權／櫃買指數卡（首頁） ───────────────────────────
function spark(vals) {
  // 迷你走勢線：不需互動，以 SVG 折線畫在 100×34 的座標內
  if (!vals || vals.length < 2) return '';
  const lo = Math.min(...vals), hi = Math.max(...vals), n = vals.length;
  const pts = vals.map((v, i) => `${(i / (n - 1) * 100).toFixed(2)},${(hi > lo ? 2 + (hi - v) / (hi - lo) * 30 : 17).toFixed(2)}`).join(' ');
  return `<svg class="spark" viewBox="0 0 100 34" preserveAspectRatio="none" aria-hidden="true">
    <polyline points="${pts}" fill="none" stroke="var(--${vals.at(-1) >= vals[0] ? 'up' : 'dn'})" stroke-width="1.5" vector-effect="non-scaling-stroke"/></svg>`;
}

function indexCard(x, name) {
  if (!x) return `<div class="card stat idx"><div class="l">${name}</div><div class="v num">--</div><div class="s">暫無資料</div></div>`;
  const stale = x.date < App.latest.date;
  return `<div class="card stat idx">
      <div class="l">${name}<span class="muted">　${md(x.date)}${stale ? '（尚未更新）' : ''}</span></div>
      <div class="v num ${cls(x.ch)}">${fmt(x.c, 2)}</div>
      <div class="s num ${cls(x.ch)}">${x.ch > 0 ? '▲' : x.ch < 0 ? '▼' : ''} ${fmt(Math.abs(x.ch ?? 0), 2)} (${sgn(x.p)}%)</div>
      ${spark(x.s)}
      ${x.s.length >= 2 ? `<div class="s"><span class="${x.s.at(-1) >= x.s[0] ? 'up' : 'dn'}">${x.s.length >= 60 ? '近 60 個交易日' : `自 ${md(x.from)} 起`} ${sgn((x.s.at(-1) / x.s[0] - 1) * 100, 1)}%</span>${x.s.length < 60 ? `（${x.s.length} 個交易日）` : ''}</div>` : ''}
    </div>`;
}

// 迷你柱狀圖：正值紅（買超）、負值綠（賣超），零軸置中
function minibars(vals) {
  if (!vals?.length) return '';
  const m = Math.max(...vals.map(Math.abs)) || 1, w = 100 / vals.length;
  return `<svg class="spark" viewBox="0 0 100 34" preserveAspectRatio="none" aria-hidden="true">
    <line x1="0" x2="100" y1="17" y2="17" stroke="var(--border2)" stroke-width="1" vector-effect="non-scaling-stroke"/>` +
    vals.map((v, i) => { const h = Math.abs(v) / m * 16;
      return `<rect x="${(i * w + w * 0.15).toFixed(2)}" y="${(v >= 0 ? 17 - h : 17).toFixed(2)}" width="${(w * 0.7).toFixed(2)}" height="${h.toFixed(2)}" fill="var(--${v >= 0 ? 'up' : 'dn'})"/>`; }).join('') +
    '</svg>';
}

// 信用交易卡（B2＋A4）：頭條為股票口徑（不含 ETF）；官方含 ETF 只列融資金額；ETF 另計一行；官方融資、融券張數不顯示
function marginCard(L) {
  const M = L.margin;
  if (!M) return '';
  const T = M.TWSE, O = M.TPEx, d = [T?.d, O?.d].filter(Boolean).sort().at(-1);
  const wan = n => `<b title="${fmt(n)} 張">${fmt(n / 1e4, 1)}</b> 萬張`;
  const lots = n => `<span class="${cls(n)}">${sgn(n, 0)}</span>`;
  const row = (x, name) => !x ? '' : `<div class="s num">${name}　融資 ${wan(x.mb)} ${lots(x.m1)}（${sgn(x.mp)}%）　融券 ${wan(x.sb)} ${lots(x.s1)}　券資比 ${fmt(x.sr, 2)}%${x.d < d ? `<span class="muted">（${md(x.d)}）</span>` : ''}</div>`;
  const mr = x => !x ? '--' : x.mr == null ? '資料不足' : `${fmt(x.mr, 1)}%（前日 ${x.mr0 == null ? '--' : fmt(x.mr0, 1) + '%'}）`;
  const amt = x => !x ? '--' : `${fmt(x.amt, 1)} 億 <span class="${cls(x.amt1)}">${x.amt1 > 0 ? '▲' : x.amt1 < 0 ? '▼' : ''}${fmt(Math.abs(x.amt1), 1)} 億</span>`;
  const E = T?.etf;
  // P22：依上市股票口徑 1 日變動較大的一邊，連到融資融券排行
  const X = T || O, rk = !X ? '' : Math.abs(X.sp ?? 0) >= Math.abs(X.mp ?? 0) ? (X.sp < 0 ? 's-' : 's+') : (X.mp < 0 ? 'm-' : 'm+');
  return `<div class="card stat idx margin">
      <div class="l">信用交易 ${md(d)}（股票，不含 ETF）${d < L.date ? '<span class="muted">（尚未更新）</span>' : ''}${rk ? `　<a class="muted small" href="#/rank/${rk}">看排行 →</a>` : ''}</div>
      ${row(T, '上市')}${row(O, '上櫃')}
      <div class="s num">融資維持率（自算）上市 ${mr(T)}　上櫃 ${mr(O)}</div>
      <div class="s num">融資金額（官方，含 ETF）上市 ${amt(T)}　上櫃 ${amt(O)}</div>
      ${sblLine(L)}
      ${E ? `<div class="s num">ETF 另計（不計入上方）：上市 ETF 融資 ${wan(E.mb)} ${lots(E.m1)}、融券 ${wan(E.sb)} ${lots(E.s1)}</div>` : ''}
      ${etfSblLine(L.sbl_etf)}
      ${T ? `${minibars(T.m20)}<div class="s">上市股票融資增減（張），近 ${T.m20.length} 日（${md(T.d20[0])}～${md(T.d20.at(-1))}）</div>` : ''}
      <div class="s">維持率 = Σ(融資張數 × 1,000 × 收盤) ÷ 官方融資金額，股票＋ETF，自算、非官方；涵蓋率不足 99% 時顯示「資料不足」</div>
      <div class="s">參考（經驗值，非官方門檻）：大盤融資維持率跌到 140% 左右時，常伴隨融資斷頭賣壓。投資人整戶擔保維持率低於 130% 會被追繳，這是官方規定。</div>
    </div>`;
}

// 第 11 輪 B14：借券賣出餘額（股票口徑，張）與融券的倍數；倍數用同一市場信用交易卡的融券合計
function sblLine(L) {
  const B = L.sbl, M = L.margin;
  if (!B) return '';
  const wan = n => `<b title="${fmt(n)} 張">${fmt(n / 1e4, n >= 1e6 ? 0 : 1)}</b> 萬張`;
  const one = (x, m, name) => !x ? '' : `${name} ${wan(x.lb)} <span class="${cls(x.l1)}">${sgn(x.l1, 0)}</span>` +
    (M?.[m]?.sb ? `（融券的 ${fmt(x.lb / M[m].sb, 0)} 倍）` : '') + (x.d !== (M?.[m]?.d ?? x.d) ? `<span class="muted">（${md(x.d)}）</span>` : '');
  return `<div class="s num">借券賣出餘額　${[one(B.TWSE, 'TWSE', '上市'), one(B.TPEx, 'TPEx', '上櫃')].filter(Boolean).join('　')}　<a class="muted small" href="#/rank/l+">看排行 →</a></div>
      <div class="s">借券賣出含避險、套利，不等於看空；晚上 8 點半以後才更新</div>`;
}

// 第 12 輪 ETF-借券：ETF 借券賣出合計（上市、上櫃 ETF，張）；多為造市、套利與避險
function etfSblLine(B) {
  if (!B) return '';
  const wan = n => `<b title="${fmt(n)} 張">${fmt(n / 1e4, n >= 1e6 ? 0 : 1)}</b> 萬張`;
  const one = (x, name) => !x ? '' : `${name} ${wan(x.lb)} <span class="${cls(x.l1)}">${sgn(x.l1, 0)}</span>`;
  return `<div class="s num">ETF 借券賣出　${[one(B.TWSE, '上市'), one(B.TPEx, '上櫃')].filter(Boolean).join('　')}　<a class="muted small" href="#/etf">ETF 頁 →</a></div>
      <div class="s">ETF 借券賣出多為造市、套利與避險（例如價格高於淨值時借券賣出，申購後還券），不等於看空</div>`;
}

// 市場寬度卡（A3＋A8）：全部為網站自算（還原收盤、股票、不含 ETF）；官方家數在成交額卡
function breadthCard(L) {
  const B = L.breadth;
  if (!B) return '';
  const pct = v => v == null ? '--' : fmt(v, 1) + '%';
  const row = (x, name) => !x ? '' : `<div class="s num">${name}　站上 MA20 <b>${pct(x.ma20)}</b>（前日 ${pct(x.s20.at(-2))}）　MA60 <b>${pct(x.ma60)}</b>　20 日新高 <span class="up">${fmt(x.hi)}</span>、新低 <span class="dn">${fmt(x.lo)}</span>　量能 <b>${x.vr == null ? '--' : fmt(x.vr, 2) + ' 倍'}</b></div>`;
  const T = B.TWSE, s = T?.s20.filter(v => v != null) || [];
  return `<div class="card stat idx margin">
      <div class="l">市場寬度 ${md(T?.d || B.TPEx?.d)}（自算，股票，不含 ETF）</div>
      ${row(T, '上市')}${row(B.TPEx, '上櫃')}
      ${spark(s)}${s.length ? `<div class="s">上市站上 MA20 比例，近 ${s.length} 個交易日（${md(T.from)} 起）</div>` : ''}
      <div class="s">分母 = 當天有收盤、且有 20（MA60 為 60）個以上收盤的股票（上市 ${fmt(T?.n20)}、上櫃 ${fmt(B.TPEx?.n20)} 檔）；新高／新低 = 收盤高於／低於前 20 個收盤；量能 = 成交額 ÷ 前 20 日平均</div>
    </div>`;
}

// 估值位置卡（第 9 輪 F9-4，A10）：上市、上櫃股票的官方本益比、淨值比、殖利率中位數在近一年的位置
function valCard(L) {
  const V = L.valuation;
  if (!V || !(V.TWSE || V.TPEx)) return '';
  const pos = x => !x ? '--' : x.v <= x.lo ? '一年最低' : x.v >= x.hi ? '一年最高' : `一年位置 ${fmt(x.p, 1)}%`;
  const row = (x, name) => !x ? '' : `<div class="s num">${name}　本益比 <b>${fmt(x.pe?.v, 2)}</b>（${pos(x.pe)}）　淨值比 <b>${fmt(x.pb?.v, 2)}</b>（${pos(x.pb)}）　殖利率 <b>${x.dy ? fmt(x.dy.v, 2) + '%' : '--'}</b>（${pos(x.dy)}）</div>`;
  const T = V.TWSE || V.TPEx;
  return `<div class="card stat idx val">
      <div class="l">估值位置（官方，股票中位數）<span class="muted">　${md(T.d)}</span></div>
      ${row(V.TWSE, '上市')}${row(V.TPEx, '上櫃')}
      ${wpeLine(V)}
      ${spark(V.TWSE?.s)}${V.TWSE?.s?.length > 1 ? `<div class="s">上市本益比中位數，近 ${V.TWSE.s.length} 個交易日（${md(V.TWSE.sf)} 起）</div>` : ''}
      ${finLine(L.fin_progress)}
      <div class="s">一年位置 = 近 ${T.days} 個交易日（${T.from.replaceAll('-', '/')} 起）中，中位數小於或等於今天的天數比例。中位數只計本益比、淨值比大於 0 的股票（上市 ${fmt(V.TWSE?.n)}、上櫃 ${fmt(V.TPEx?.n)} 檔），不是加權指數本益比；本益比用近 4 季 EPS，財報公布期間 EPS 變化也會改變位置；殖利率用去年股利。只是位置，不是買賣訊號</div>
    </div>`;
}

// 第 12 輪 A10-延伸：市值加權本益比（本站以目前股數計算）；和上面的中位數並列
function wpeLine(V) {
  const T = V.TWSE?.wpe, O = V.TPEx?.wpe;
  if (!T && !O) return '';
  const pos = x => x.v <= x.lo ? '一年最低' : x.v >= x.hi ? '一年最高' : `一年位置 ${fmt(x.p, 1)}%`;
  const one = (x, name) => !x ? '' : `${name} <b>${fmt(x.v, 2)}</b>（${pos(x)}）`;
  const big = T?.t ? `最大的 ${esc(App.latest.stocks?.[T.t[0]]?.n || T.t[0])} 占上市 ${fmt(T.t[1], 1)}%` : '';
  return `<div class="s num">加權本益比（市值加權）　${[one(T, '上市'), one(O, '上櫃')].filter(Boolean).join('　')}</div>
      <div class="s">加權本益比 = 市值合計 ÷ Σ（市值 ÷ 本益比），大型股影響大${big ? `（${big}）` : ''}；中位數反映一般股票。本站以目前股數計算、不含虧損公司，不是證交所公布的數字</div>`;
}

// 第 10 輪 B5：季報公布進度（資料日在季報收集期間、當季已有資料時才有 fin_progress）
function finLine(P) {
  if (!P) return '';
  const q = P.q % 100, name = q === 4 ? `${Math.floor(P.q / 100)} 年報` : `第 ${q} 季財報`;
  return `<div class="s">${name}已收：上市 ${fmt(P.n.TWSE)}、上櫃 ${fmt(P.n.TPEx)} 家（前一季 ${fmt(P.p.TWSE)}、${fmt(P.p.TPEx)} 家）；本益比中位數會隨 EPS 更新而變動</div>`;
}

// 三大法人卡：上市（A2）、上櫃（第 9 輪 F9-1）都用官方金額；上櫃官方還沒有任何資料時退回估算一行；上市也沒有時維持第 1 輪估算卡
function instiCard(L) {
  const O = L.insti_official, P = L.insti_official_tpex, X = L.insti_otc, I = L.insti;
  const yi1 = v => v == null ? '--' : sgn(v, 1) + '億';
  const parts = x => `外資 <span class="${cls(x.foreign)}">${yi1(x.foreign)}</span>　投信 <span class="${cls(x.trust)}">${yi1(x.trust)}</span>　自營 <span class="${cls(x.dealer)}">${yi1(x.dealer)}</span>`;
  const stk = s => s > 0 ? `連買 ${s} 日` : s < 0 ? `連賣 ${-s} 日` : '當日持平';
  if (!O) return `<div class="card stat insti"><div class="l">三大法人（${md(L.flow_date)}）</div>
      <div class="v num ${cls(I.foreign + I.trust + I.dealer)}">${yi(I.foreign + I.trust + I.dealer)}</div>
      <div class="s num">外資 <span class="${cls(I.foreign)}">${yi(I.foreign)}</span>　投信 <span class="${cls(I.trust)}">${yi(I.trust)}</span>　自營 <span class="${cls(I.dealer)}">${yi(I.dealer)}</span></div>
      <div class="s">估算：買賣超張數 × 收盤價，不含 ETF</div></div>`;
  const stale = O.date < L.date, fs = O.fs;
  // 上市、上櫃各一張卡（左右並排；手機上下排），共同說明放在兩張卡下方
  const otc = P ? `<div class="card stat idx insti">
      <div class="l">三大法人　上櫃，官方，含 ETF<span class="muted">　${md(P.date)}${P.date < L.date ? '（尚未更新）' : ''}</span></div>
      <div class="v num ${cls(P.total)}">${yi1(P.total)}</div>
      <div class="s num">${parts(P)}</div>
      ${minibars(P.f)}
      <div class="s">外資近 ${P.f.length} 日（${md(P.d[0])}～${md(P.d.at(-1))}）<b class="${cls(P.fs)}">${stk(P.fs)}</b></div>
    </div>`
    : X ? `<div class="card stat idx insti">
      <div class="l">三大法人　上櫃，估算<span class="muted">　${md(L.flow_date)}</span></div>
      <div class="s num">外資 <span class="${cls(X.foreign)}">${yi(X.foreign)}</span>　投信 <span class="${cls(X.trust)}">${yi(X.trust)}</span>　自營 <span class="${cls(X.dealer)}">${yi(X.dealer)}</span></div>
      <div class="s">上櫃官方金額尚無資料，暫以張數 × 收盤估算、不含 ETF，不可與上市官方值相加</div>
    </div>` : '';
  return `<div class="card stat idx insti">
      <div class="l">三大法人　上市，官方，含 ETF<span class="muted">　${md(O.date)}${stale ? '（尚未更新）' : ''}</span></div>
      <div class="v num ${cls(O.total)}">${yi1(O.total)}</div>
      <div class="s num">${parts(O)}</div>
      ${minibars(O.f)}
      <div class="s">外資近 ${O.f.length} 日（${md(O.d[0])}～${md(O.d.at(-1))}）<b class="${cls(fs)}">${stk(fs)}</b></div>
    </div>${otc}
    <div class="muted small span-all">官方金額含 ETF 與權證避險，外資不含外資自營商（已計入自營）；上市、上櫃同一天時可相加。下方法人買超／賣超表為張數 × 收盤估算、不含 ETF，口徑不同</div>`;
}

function futuresHTML(F) {
  if (!F || !F.d.length) return '';
  const k = F.d.length - 1, c = F.c[k], ch = F.ch[k], pct = ch != null && c !== ch ? ch / (c - ch) * 100 : null;
  const N = F.night;
  // P20：夜盤歸屬日 D = 前一個交易日 15:00 ~ D 05:00；D ≤ 日盤日期 = 日盤收盤之前的夜盤，放最前面並淡化
  const old = N && N.date <= F.d[k];
  let night = '';
  if (N) {
    const from = [...F.d].reverse().find(d => d < N.date);
    const np = N.ch != null && N.c !== N.ch ? N.ch / (N.c - N.ch) * 100 : null;
    night = `<span class="${old ? 'night-old' : ''}">${old ? '前一夜盤' : '最新夜盤'}（${from ? md(from) + ' 15:00～' : ''}${md(N.date)} 05:00）　收 <b class="num ${cls(N.ch)}">${fmt(N.c)}</b>
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
      <div class="fut-sub muted small">${old ? night : ''}<span>成交量 <b class="num">${fmt(F.v[k])}</b> 口</span>
        <span>未平倉 <b class="num">${fmt(F.oi[k])}</b> 口</span>${old ? '' : night}</div>
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
  // 模型未勝過「永遠猜多數方向」基準（acc <= baseline）時降級為「籌碼因子觀察」，機率與回測收進摺疊區
  const beat = FC ? FC.backtest.acc > FC.backtest.baseline : true;
  if (FC) {
    const B = FC.backtest;
    const maxE = Math.max(0.05, ...FC.factors.map(f => Math.abs(f.effect)));
    const vcls = FC.view === '偏多' ? 'up' : FC.view === '偏空' ? 'dn' : 'flat';
    const head = `<div class="fc-head"><span class="fc-view ${vcls}">${FC.view}</span>
        <span>下一交易日上漲機率 <b class="num ${vcls}">${pctTxt(FC.p_up)}</b></span>
        <span class="muted small">依 ${md(FC.date)} 收盤後未平倉</span></div>`;
    const factors = `<div class="fc-factors">${FC.factors.map(f => `<div class="fc-f" title="z 分數 ${f.z}（相對近 60 日）">
          <span class="nm">${f.name}</span><span class="num muted">${sgn(f.value, 0)} 口</span>
          <span class="fc-bar"><span style="${f.effect >= 0 ? 'left:50%' : 'right:50%'};width:${Math.abs(f.effect) / maxE * 50}%;background:var(--${f.effect >= 0 ? 'up' : 'dn'})"></span></span></div>`).join('')}
        <div class="muted small">${beat ? '長條往右 = 推升上漲機率，往左 = 壓低' : '長條往右 = 對隔日上漲有利，往左 = 不利'}</div></div>`;
    const bt = `<div class="fc-bt ${beat ? '' : 'warn'}">回測 ${B.from.slice(0, 7).replace('-', '/')}～${B.to.slice(0, 7).replace('-', '/')} 共 ${B.n} 天：
        命中率 <b>${pctTxt(B.acc)}</b>，「永遠猜多數方向」基準 <b>${pctTxt(B.baseline)}</b>
        ${B.conf_acc != null ? `；機率偏離 5% 以上的 ${B.conf_n} 天命中 <b>${pctTxt(B.conf_acc)}</b>` : ''}。
        ${beat ? '' : '<br>模型目前沒有勝過簡單基準，未平倉對隔日漲跌的預測力很弱，請只當作籌碼面參考。'}</div>
      <div class="fc-recent"><span class="muted small">最近 10 次</span>${FC.recent.map(([d, p, y]) =>
        `<span class="fc-dot ${(p >= 0.5) === !!y ? 'hit' : 'miss'}" title="${d} 預測上漲 ${pctTxt(p)}，實際${y ? '漲' : '跌'}">${(p >= 0.5) === !!y ? '✓' : '✗'}</span>`).join('')}</div>
      <div class="muted small">羅吉斯迴歸，特徵為約當大台淨未平倉水位與增減（相對近 60 日標準化），每 20 天以過去資料重新訓練。僅供研究，非投資建議。</div>`;
    fc = beat ? head + factors + bt
      : `<div class="muted small" style="margin-bottom:8px">依 ${md(FC.date)} 收盤後期貨法人未平倉，各因子相對近 60 日的方向與強弱</div>
         ${factors}
         <details class="fc-more"><summary>模型回測（實驗性，未勝過基準）</summary>${head}${bt}</details>`;
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
      <div class="card"><div class="sec-h"><h2>${beat ? '大盤漲跌預測' : '籌碼因子觀察'}</h2><span class="muted small">台指期近月日盤</span></div>${fc}</div>
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
  $('#gMeta').innerHTML = `<span class="pill">${g.quadrant}</span>　5日 <span class="${cls(g.net_5d)}">${yi(g.net_5d)}</span>　連${g.streak >= 0 ? '買' : '賣'} ${Math.abs(g.streak)} 天　法人 ${md(App.latest.flow_date)}`;
  const rows = g.codes.filter(c => S[c]).sort((a, b) => (S[b].n5 ?? 0) - (S[a].n5 ?? 0));
  $('#gTable').innerHTML = `<thead><tr><th>股票</th><th>收盤</th><th>漲跌</th><th>法人1日</th><th>法人5日</th></tr></thead><tbody>` +
    rows.map(c => { const s = S[c]; return `<tr data-code="${c}"><td class="nm"><b>${esc(s.n)}</b><span>${c}</span></td>
      <td class="num ${cls(s.p)}">${pfmt(s.c)}</td>${pctCell(s)}
      <td class="num ${cls(s.n1)}">${yi(s.n1)}</td><td class="num ${cls(s.n5)}">${yi(s.n5)}</td></tr>`; }).join('') + '</tbody>';
}

// ─── 排行 / 自選 ────────────────────────────────────────
// [代號, 名稱, 欄位, 排序方向, 來源]；欄位 '*' 會換成 1 或 5（依「1日 / 5日」切換）
// 來源（第 8 輪）：省略 = latest.json；'x' = 需要 screen.json；'v' = 估值（需要 screen.json 的 cap）；'m' = 融資融券
const RANKS = [
  ['n+', '法人買超', 'n*', -1], ['n-', '法人賣超', 'n*', 1],
  ['f+', '外資買超', 'f*', -1], ['f-', '外資賣超', 'f*', 1],
  ['t+', '投信買超', 't*', -1], ['t-', '投信賣超', 't*', 1],
  ['d+', '自營買超', 'd*', -1], ['d-', '自營賣超', 'd*', 1],
  ['fs', '外資連買', 'fs', -1], ['ts', '投信連買', 'ts', -1], ['s', '法人連買', 's', -1],
  ['p+', '漲幅', 'p', -1], ['p-', '跌幅', 'p', 1], ['tv', '成交額', 'tv', -1],
  ['vr', '量比', 'vr', -1, 'x'], ['nh', '創新高（N 日）', 'nh', -1, 'x'], ['rs20', '20 日相對強勢', 'rs20', -1, 'x'],
  ['to', '週轉率', 'to', -1, 'x'],                                                  // 第 12 輪 B11
  ['ry', '營收年增', 'ry', -1, 'x'], ['dy', '殖利率', 'dy', -1, 'v'], ['pe', '本益比最低', 'pe', 1, 'v'],
  ['m+', '融資增加', 'm*', -1, 'm'], ['m-', '融資減少', 'm*', 1, 'm'], ['mr', '融資增加率', 'mr*', -1, 'm'],
  ['s+', '融券增加', 's*', -1, 'm'], ['s-', '融券減少', 's*', 1, 'm'], ['sr', '券資比', 'sr', -1, 'm'], ['mu', '融資使用率', 'mu', -1, 'm'],
  ['l+', '借券賣出增加', 'la*', -1, 'l'], ['lp', '借券占股本', 'lp', -1, 'l'],     // 第 11 輪 B14：'l' = 借券（需要 screen.json）
];
const RANK_GROUPS = [['法人', ['n+', 'n-', 'f+', 'f-', 't+', 't-', 'd+', 'd-', 'fs', 'ts', 's']], ['價量', ['p+', 'p-', 'tv', 'vr', 'nh', 'rs20', 'to']],
  ['基本面', ['ry', 'dy', 'pe']], ['融資融券', ['m+', 'm-', 'mr', 's+', 's-', 'sr', 'mu']], ['借券', ['l+', 'lp']]];
// screen.json 排行的額外篩選與表格欄位
const RANK_FILTER = { nh: x => x.nh > 0, dy: x => isNum(x.pe) && x.pe > 0 && x.cap !== 1, pe: x => x.pe > 0 && x.cap !== 1, sr: x => isNum(x.mb) && x.mb >= MARGIN_BASE };
const RANK_COLS = { vr: ['vr'], nh: ['nh'], rs20: ['rs20'], ry: ['ry'], dy: ['dy', 'pe', 'pb'], pe: ['pe', 'pb', 'dy'], to: ['to', 'mc'] };
const streakTxt = v => v ? (v > 0 ? '買' : '賣') + Math.abs(v) : '--';
const modeSeg = v => segHTML('modeSeg', [['rank', '排行'], ['screen', '選股']], v);
const onModeSeg = () => onSeg('modeSeg', v => { location.hash = v === 'screen' ? '#/rank/screen' : '#/rank'; });

function stockTable(list, span = '1') {
  const k = span === '5' ? '5' : '1', lbl = k === '5' ? '5日' : '1日';
  const amt = v => `<td class="num ${cls(v)}">${yi(v)}</td>`;
  const fd = md(App.latest.flow_date);
  return `${flowNote()}<div class="muted small tbl-cap">${k === '5' ? `法人欄位為截至 ${fd} 的近 5 日累計（億）` : `法人欄位為 ${fd} 當日買賣超（億）`}</div>
    <div class="tbl-wrap"><table class="tbl"><thead><tr>
      <th>股票</th><th>收盤</th><th>漲跌</th><th>成交額</th><th>外資${lbl}</th><th>投信${lbl}</th><th>自營${lbl}</th><th>法人${lbl}</th>
      <th>外資連</th><th>投信連</th><th>法人連</th></tr></thead><tbody>` +
    list.map(([c, s]) => `<tr data-code="${c}">
      <td class="nm"><b>${esc(s.n)}</b>${alertBadge(s)}<span>${c} ${esc(s.i)}</span></td>
      <td class="num ${cls(s.p)}">${pfmt(s.c)}</td>${pctCell(s)}
      <td class="num">${fmt(s.tv, 1)}億</td>
      ${amt(s['f' + k])}${amt(s['t' + k])}${amt(s['d' + k])}${amt(s['n' + k])}
      <td class="num ${cls(s.fs)}">${streakTxt(s.fs)}</td><td class="num ${cls(s.ts)}">${streakTxt(s.ts)}</td>
      <td class="num ${cls(s.s)}">${streakTxt(s.s)}</td></tr>`).join('') +
    '</tbody></table></div>';
}

function spanSeg(span) { return segHTML('rspanSeg', [['1', '1日'], ['5', '5日']], span); }

async function renderRank(arg) {
  // 第 8 輪：#/rank/{排行代號}（例如信用交易卡的 #/rank/s-）→ 記住排行後把網址改回 #/rank
  if (arg && RANKS.some(r => r[0] === arg)) { localStore('rank2', null, arg); history.replaceState(null, '', '#/rank'); }
  const S = await loadScreen();
  const avail = RANKS.filter(r => !r[4] || S);          // screen.json 不存在時，需要它的排行不出現
  const by0 = localStore('rank2', 'n+'), mkt = localStore('mkt', 'all'), span = localStore('rspan', '1');
  const minTv = localStore('rtv', '0.5');   // 成交額門檻（億），套用到所有排行
  const [by, , f, dir, src] = avail.find(r => r[0] === by0) || RANKS[0];
  const unit = localStore('munit', 'amt'), byAmt = (by === 'm+' || by === 'm-') && unit === 'amt';
  const field = (byAmt ? 'ma*' : f).replace('*', span);
  let table, foot = '';
  if (!src) {
    // 連買排行同天數再比較該法人的 5 日金額
    const tie = { fs: 'f5', ts: 't5', s: 'n5' }[field];
    const list = Object.entries(App.latest.stocks)
      .filter(([, s]) => s[field] != null && (mkt === 'all' || s.m === mkt) && (s.tv ?? 0) >= Number(minTv))
      .sort((a, b) => dir * (a[1][field] - b[1][field]) || (tie ? (b[1][tie] ?? 0) - (a[1][tie] ?? 0) : 0)).slice(0, 50);
    table = stockTable(list, span);
  } else {
    const inMkt = x => mkt === 'all' || x.m === mkt;
    const list = screenRows().filter(x => isNum(x[field]) && (RANK_FILTER[by] || (() => true))(x) && inMkt(x) && (x.tv ?? 0) >= Number(minTv))
      .sort((a, b) => dir * (a[field] - b[field]) || (src === 'm' ? (a.code < b.code ? -1 : 1) : b.tv - a.tv)).slice(0, 50);
    if (src === 'l') {
      const sds = [...new Set(Object.entries(S.sd || {}).filter(([m]) => mkt === 'all' || m === mkt).map(([, d]) => md(d)))].join('、');
      table = sblTable(list, span);
      foot = `借券資料日：上市 ${S.sd?.TWSE ? md(S.sd.TWSE) : '--'}、上櫃 ${S.sd?.TPEx ? md(S.sd.TPEx) : '--'}（${sds || '--'}）。估算金額 = 借券賣出增減張數 × 1,000 × 收盤，是估算。借券賣出含避險、套利（ETF、權證、可轉債避險），不等於看空，只能當作空方部位的上限。占股本 = 借券賣出餘額 ÷ 目前發行股數（不是當時股數）。資料晚上 8 點半以後才更新。不含 ETF。`;
    } else if (src === 'm') {
      const all = screenRows().filter(inMkt), cnt = (k, sg) => all.filter(x => isNum(x[k]) && sg * x[k] > 0).length;
      const mds = [...new Set(Object.entries(S.md).filter(([m]) => mkt === 'all' || m === mkt).map(([, d]) => md(d)))].join('、');
      table = `<div class="muted small tbl-cap">融資增加 ${fmt(cnt('m' + span, 1))} 家、減少 ${fmt(cnt('m' + span, -1))} 家；融券增加 ${fmt(cnt('s' + span, 1))} 家、減少 ${fmt(cnt('s' + span, -1))} 家（${span} 日，股票，融資融券 ${mds || '--'}）</div>` +
        marginTable(list, span, by);
      foot = `融資融券資料日：上市 ${S.md.TWSE ? md(S.md.TWSE) : '--'}、上櫃 ${S.md.TPEx ? md(S.md.TPEx) : '--'}。估算金額 = 張數 × 1,000 × 收盤，是估算，不是官方融資金額。5 日增減遇到面額變更、減資時，以官方換算後的 5 日前餘額計算。融資增加率的基期（1 日或 5 日前餘額）至少 1,000 張；券資比只列融資 1,000 張以上；使用率不列限額 0 或無限額的股票。不含 ETF。`;
    } else table = screenTable(list, RANK_COLS[by]);
  }
  if (!foot) foot = '金額 = 買賣超張數 × 當日收盤，不含 ETF。成交額門檻以資料日成交額篩選，套用到所有排行。「1日／5日」只切換法人、外資、投信、自營買賣超排行與表格法人欄位的天數；漲幅、跌幅、成交額與連買排行不受影響。連買為連續買超天數，天數相同時以近 5 日金額排序。' +
    (S ? '量比、創新高、相對強勢、營收、估值排行的資料日見「選股」頁；殖利率、本益比排行已排除虧損（官方本益比空白）與 90 天內股本變動的股票。週轉率 = 今日成交股數 ÷ 目前發行股數，市值 = 收盤 × 目前發行股數；增資、減資前後可能失真。' : '');
  $('#view').innerHTML = `<section class="sec">
      <div class="sec-h">${modeSeg('rank')}<span class="sp"></span>
        ${segHTML('mktSeg', [['all', '全部'], ['TWSE', '上市'], ['TPEx', '上櫃']], mkt)}
        ${spanSeg(span)}
        ${by === 'm+' || by === 'm-' ? segHTML('munitSeg', [['amt', '估算金額'], ['lot', '張數']], unit) : ''}
        <select id="tvSel" class="sel" aria-label="成交額門檻">${[['0', '成交額不限'], ['0.5', '成交額 ≥ 0.5 億'], ['1', '成交額 ≥ 1 億'], ['5', '成交額 ≥ 5 億']]
          .map(([v, t]) => `<option value="${v}"${v === minTv ? ' selected' : ''}>${t}</option>`).join('')}</select>
        <select id="rankSel" class="sel">${RANK_GROUPS.map(([g, ids]) => { const rs = ids.map(id => avail.find(r => r[0] === id)).filter(Boolean);
          return rs.length ? `<optgroup label="${g}">${rs.map(r => `<option value="${r[0]}"${r[0] === by ? ' selected' : ''}>${r[1]}</option>`).join('')}</optgroup>` : ''; }).join('')}</select></div>
      <div class="card">${table}</div>
      <div class="muted small" style="margin-top:6px">${foot}</div></section>`;
  $('#rankSel').addEventListener('change', e => { localStore('rank2', null, e.target.value); renderRank(); });
  $('#tvSel').addEventListener('change', e => { localStore('rtv', null, e.target.value); renderRank(); });
  onSeg('rspanSeg', v => { localStore('rspan', null, v); renderRank(); });
  onSeg('mktSeg', v => { localStore('mkt', null, v); renderRank(); });
  if ($('#munitSeg')) onSeg('munitSeg', v => { localStore('munit', null, v); renderRank(); });
  onModeSeg();
  $('#view').addEventListener('click', onRowClick);
}

// F8-3：融資融券排行的表格（和 stockTable 分開）
function marginTable(list, span, by) {
  const k = span === '5' ? '5' : '1', lbl = k === '5' ? '5日' : '1日';
  const lots = v => `<td class="num ${cls(v)}">${isNum(v) ? sgn(v, 0) : '--'}</td>`;
  const n0 = v => `<td class="num">${isNum(v) ? fmt(v) : '--'}</td>`;
  const p2 = v => `<td class="num">${isNum(v) ? fmt(v, 2) + '%' : '--'}</td>`;
  const sp = v => `<td class="num ${cls(v)}">${isNum(v) ? sgn(v) + '%' : '--'}</td>`;
  return `<div class="tbl-wrap"><table class="tbl"><thead><tr><th>股票</th><th>收盤</th><th>漲跌</th><th>5日漲跌</th><th>融資餘額</th><th>融資${lbl}</th><th>估算（億）</th>${by === 'mr' ? '<th>增加率</th>' : ''}
      <th>融券餘額</th><th>融券${lbl}</th><th>券資比</th><th>使用率</th><th>成交額</th></tr></thead><tbody>` +
    list.map(x => `<tr data-code="${x.code}"><td class="nm"><b>${esc(x.n)}</b>${alertBadge(x)}<span>${x.code} ${esc(x.i)}</span></td>
      <td class="num ${cls(x.p)}">${pfmt(x.c)}</td>${pctCell(x)}${sp(x.r5)}
      ${n0(x.mb)}${lots(x['m' + k])}<td class="num ${cls(x['ma' + k])}">${isNum(x['ma' + k]) ? yi(x['ma' + k]) : '--'}</td>${by === 'mr' ? sp(x['mr' + k]) : ''}
      ${n0(x.sb)}${lots(x['s' + k])}${p2(x.sr)}${p2(x.mu)}<td class="num">${fmt(x.tv, 1)}億</td></tr>`).join('') +
    '</tbody></table></div>';
}

// 第 11 輪 B14：借券排行的表格
function sblTable(list, span) {
  const k = span === '5' ? '5' : '1', lbl = k === '5' ? '5日' : '1日';
  return `<div class="tbl-wrap"><table class="tbl"><thead><tr><th>股票</th><th>收盤</th><th>漲跌</th><th>5日漲跌</th><th>借券餘額</th><th>借券${lbl}</th><th>估算（億）</th><th>占股本</th><th>融券餘額</th><th>成交額</th></tr></thead><tbody>` +
    list.map(x => `<tr data-code="${x.code}"><td class="nm"><b>${esc(x.n)}</b>${alertBadge(x)}<span>${x.code} ${esc(x.i)}</span></td>
      <td class="num ${cls(x.p)}">${pfmt(x.c)}</td>${pctCell(x)}<td class="num ${cls(x.r5)}">${isNum(x.r5) ? sgn(x.r5) + '%' : '--'}</td>
      <td class="num">${isNum(x.lb) ? fmt(x.lb) : '--'}</td><td class="num ${cls(x['l' + k])}">${isNum(x['l' + k]) ? sgn(x['l' + k], 0) : '--'}</td>
      <td class="num ${cls(x['la' + k])}">${isNum(x['la' + k]) ? yi(x['la' + k]) : '--'}</td><td class="num">${isNum(x.lp) ? fmt(x.lp, 2) + '%' : '--'}</td>
      <td class="num">${isNum(x.sb) ? fmt(x.sb) : '--'}</td><td class="num">${fmt(x.tv, 1)}億</td></tr>`).join('') +
    '</tbody></table></div>';
}

// ─── 第 8 輪 F8-2：條件選股（screen.json 與 latest.json stocks 合併）──────────
const isNum = v => typeof v === 'number';       // null、undefined 一律不符合（null >= 0 在 JS 是 true）
async function loadScreen() {
  if (App.screen !== undefined) return App.screen;
  try {
    const S = await getJSON('data/screen.json');
    const rows = {};
    S.codes.forEach((c, i) => { const r = rows[c] = {}; for (const k in S) if (Array.isArray(S[k]) && k !== 'codes') r[k] = S[k][i]; });
    S.rows = rows;
    App.screen = S;
  } catch (e) { App.screen = null; }           // 不 console.error：檔案不存在時排行照常、選股頁顯示尚未產生
  return App.screen;
}
const MARGIN_BASE = 1000;
function screenRow(code, st, S) {             // st = latest.json stocks 的一列
  const x = Object.assign({ code }, st, (S && S.rows[code]) || {});
  for (const n of [1, 5]) {
    const v = x['m' + n];
    x['ma' + n] = isNum(v) && isNum(x.c) ? v * 1000 * x.c / 1e8 : null;
    x['mr' + n] = isNum(v) && isNum(x.mb) && x.mb - v >= MARGIN_BASE ? v / (x.mb - v) * 100 : null;
    x['la' + n] = isNum(x['l' + n]) && isNum(x.c) ? x['l' + n] * 1000 * x.c / 1e8 : null;   // 第 11 輪：借券增減估算金額（億）
  }
  return x;
}
function screenRows() {
  if (!App.rows) App.rows = Object.entries(App.latest.stocks).map(([c, s]) => screenRow(c, s, App.screen));
  return App.rows;
}
// 營收欄名的月份：檔數最多的營收月份（YYYYMM）
const revMonth = () => Object.entries(App.screen?.rmd || {}).sort((a, b) => b[1] - a[1])[0]?.[0];
// 第 9 輪 F9-2：營收月份混雜（兩個以上月份，且最多的月份不到 98%）→ 資料日一列加公布期間說明
const revMixed = S => { const n = Object.values(S.rmd || {}), t = n.reduce((a, b) => a + b, 0); return n.length > 1 && Math.max(...n) < t * 0.98; };
// 第 10 輪 B5：季報季別（YYYYQQ，例如 202603）同營收月份的做法：欄名用檔數最多的季別，季別不同的列加小字
const finQ = () => Object.entries(App.screen?.fqd || {}).sort((a, b) => b[1] - a[1])[0]?.[0];
const finMixed = S => revMixed({ rmd: S.fqd });
const finTag = x => x.fq && String(x.fq) !== finQ() ? `<span class="muted small">（Q${x.fq % 100}）</span>` : '';

// 結果表的動態欄：[欄名, 取值, 格式, 預設方向（1 遞增）]
const spct = v => v == null ? '--' : sgn(v) + '%';
const int0 = v => v ? fmt(v) : '--';
const SCR_COLS = {
  a20: ['20日均額', x => x.a20, v => fmt(v, 2) + '億'],
  r5: ['5日報酬', x => x.r5, spct], r20: ['20日報酬', x => x.r20, spct], r60: ['60日報酬', x => x.r60, spct],
  b20: ['MA20乖離', x => x.b20, spct], b60: ['MA60乖離', x => x.b60, spct],
  nh: ['新高(日)', x => x.nh, int0], nl: ['新低(日)', x => x.nl, int0],
  hd: ['距52週高', x => isNum(x.h52) && x.h52 > 0 && isNum(x.c) ? (x.h52 - x.c) / x.h52 * 100 : null, v => v == null ? '--' : fmt(v, 2) + '%', 1],
  vr: ['量比', x => x.vr, v => fmt(v, 2)],
  rs20: ['20日相對', x => x.rs20, v => sgn(v)], rs60: ['60日相對', x => x.rs60, v => sgn(v)],
  s: ['法人連', x => x.s, streakTxt], fs: ['外資連', x => x.fs, streakTxt], ts: ['投信連', x => x.ts, streakTxt],
  f5: ['外資5日', x => x.f5, yi], t5: ['投信5日', x => x.t5, yi], n5: ['法人5日', x => x.n5, yi], n20: ['法人20日', x => x.n20, yi],
  t5r: ['投信5日/額', x => isNum(x.t5) && x.a20 > 0 ? x.t5 / (x.a20 * 5) * 100 : null, spct],
  n5r: ['法人5日/額', x => isNum(x.n5) && x.a20 > 0 ? x.n5 / (x.a20 * 5) * 100 : null, spct],
  m5: ['融資5日', x => x.m5, v => sgn(v, 0)],
  m5p: ['融資5日%', x => isNum(x.m5) && isNum(x.mb) && x.mb - x.m5 > 0 ? x.m5 / (x.mb - x.m5) * 100 : null, spct],
  sr: ['券資比', x => x.sr, v => v == null ? '--' : fmt(v, 2) + '%'], mu: ['使用率', x => x.mu, v => v == null ? '--' : fmt(v, 2) + '%'],
  ry: ['營收年增', x => x.ry, (v, x) => spct(v) + (x.rm && String(x.rm) !== revMonth() ? `<span class="muted small">（${x.rm % 100}月）</span>` : '')],
  rc: ['累計年增', x => x.rc, spct], rh: ['營收新高(年)', x => x.rh, int0], r3: ['連3月年增', x => x.r3, v => v === 1 ? '✓' : '--'],
  pe: ['本益比', x => x.pe, v => fmt(v, 2), 1], dy: ['殖利率', x => x.dy, spct], pb: ['淨值比', x => x.pb, v => fmt(v, 2), 1],
  pbp: ['淨值比位置', x => x.pbp, v => fmt(v) + '%', 1],
  eq: ['單季EPS', x => x.eq, (v, x) => fmt(v, 2) + finTag(x)], ey: ['EPS年增', x => x.ey, (v, x) => spct(v) + finTag(x)],
  e4: ['近4季EPS', x => x.e4, v => fmt(v, 2)], gm: ['毛利率', x => x.gm, (v, x) => fmt(v, 1) + '%' + finTag(x)],
  gmy: ['毛利率年增', x => x.gmy, (v, x) => sgn(v, 1) + '點' + finTag(x)], eh: ['EPS新高(季)', x => x.eh, int0],
  mc: ['市值', x => x.mc, v => fmt(v, 0) + '億'], to: ['週轉率', x => x.to, v => fmt(v, 2) + '%'],   // 第 12 輪 B11
  lb: ['借券餘額', x => x.lb, v => fmt(v)], l5: ['借券5日', x => x.l5, v => sgn(v, 0)], lp: ['借券占股本', x => x.lp, v => fmt(v, 2) + '%'],
};
const CAP_TAG = '<i class="al al-c" title="90 天內有除權、減資或面額變更，官方本益比、殖利率可能尚未調整">股本變動</i>';
// 固定欄（股票｜收盤｜漲跌｜成交額）＋ cols；o = {sort: 目前排序欄, cap: 是否標示股本變動}；sort 有值時欄名可點排序
function screenTable(list, cols, o = {}) {
  const head = k => { const c = SCR_COLS[k], M = revMonth(), Fq = finQ();
    return k === 'ry' && M ? `營收年增（${Number(M.slice(4))} 月）` : (k === 'eq' || k === 'ey') && Fq ? `${c[0]}（Q${Number(Fq.slice(4))}）` : c[0]; };
  const th = (k, t) => o.sort ? `<th class="sort" data-k="${k}">${t}</th>` : `<th>${t}</th>`;
  return `<div class="tbl-wrap"><table class="tbl"><thead><tr><th>股票</th><th>收盤</th>${th('p', '漲跌')}${th('tv', '成交額')}${cols.map(k => th(k, head(k))).join('')}</tr></thead><tbody>` +
    list.map(x => `<tr data-code="${x.code}"><td class="nm"><b>${esc(x.n)}</b>${alertBadge(x)}${o.cap && x.cap === 1 ? CAP_TAG : ''}<span>${x.code} ${esc(x.i)}</span></td>
      <td class="num ${cls(x.p)}">${pfmt(x.c)}</td>${pctCell(x)}<td class="num">${fmt(x.tv, 1)}億</td>` +
      cols.map(k => { const [, get, f] = SCR_COLS[k], v = get(x);
        return `<td class="num ${['s', 'fs', 'ts', 'nh', 'nl', 'rh', 'r3', 'vr', 'a20', 'sr', 'mu', 'pe', 'pb', 'hd', 'pbp', 'gm', 'eh', 'lb', 'lp', 'mc', 'to'].includes(k) ? '' : cls(v)}">${v == null ? '--' : f(v, x)}</td>`; }).join('') + '</tr>').join('') +
    '</tbody></table></div>';
}

const scrGe = k => (x, v) => isNum(x[k]) && x[k] >= v;
const scrPos = k => x => isNum(x[k]) && x[k] > 0;
const valGuard = (x, st) => !st.xc || x.cap !== 1;
const m5Base = x => isNum(x.m5) && isNum(x.mb) ? x.mb - x.m5 : null;
// opts：數字陣列或 [值, 文字]（下拉）、'num'（數字欄）；sw = 開關；val = 估值條件（受 xc 影響）
const SCREEN_CONDS = [
  { id: 'tv', g: '流動性', label: '成交額 ≥ {v} 億', opts: [0.5, 1, 3, 5, 10], def: 0.5, f: scrGe('tv') },
  { id: 'a20', g: '流動性', label: '20 日均成交額 ≥ {v} 億', opts: [0.5, 1, 3, 5], def: 1, f: scrGe('a20'), cols: ['a20'] },
  // 第 12 輪 B11：目前股數計算；null（沒有股數）不符合
  { id: 'mc', g: '流動性', label: '市值 ≥ {v} 億', opts: [50, 100, 500, 1000], def: 100, f: scrGe('mc'), cols: ['mc'], title: '收盤 × 目前發行股數' },
  { id: 'to', g: '流動性', label: '週轉率 ≥ {v}%', opts: [1, 3, 5, 10], def: 3, f: scrGe('to'), cols: ['to'], title: '今日成交股數 ÷ 目前發行股數；增資、減資前後可能失真' },
  { id: 'p', g: '價量', label: '今日漲幅 ≥ {v}%', opts: 'num', def: 3, f: scrGe('p') },
  { id: 'r5', g: '價量', label: '5 日報酬 ≥ {v}%', opts: 'num', def: 10, f: scrGe('r5'), cols: ['r5'] },
  { id: 'r20', g: '價量', label: '20 日報酬 ≥ {v}%', opts: 'num', def: 10, f: scrGe('r20'), cols: ['r20'] },
  { id: 'r60', g: '價量', label: '60 日報酬 ≥ {v}%', opts: 'num', def: 20, f: scrGe('r60'), cols: ['r60'] },
  { id: 'ma', g: '價量', label: '均線 {v}', opts: [[1, '收盤 > MA20'], [2, '收盤 > MA60'], [3, '收盤 > MA20 > MA60']], def: 1, cols: ['b20', 'b60'],
    f: (x, v) => v === 1 ? isNum(x.b20) && x.b20 > 0 : v === 2 ? isNum(x.b60) && x.b60 > 0 : isNum(x.b20) && isNum(x.b60) && x.b20 > 0 && x.b60 > x.b20 },
  { id: 'bx', g: '價量', label: 'MA20 乖離 ≤ {v}%', opts: 'num', def: 10, f: (x, v) => isNum(x.b20) && x.b20 <= v, cols: ['b20'] },
  { id: 'nh', g: '價量', label: '創 {v} 日新高', opts: [20, 60, 120, 240], def: 60, f: scrGe('nh'), cols: ['nh'] },
  { id: 'nl', g: '價量', label: '創 {v} 日新低', opts: [20, 60, 120, 240], def: 20, f: scrGe('nl'), cols: ['nl'] },
  { id: 'hd', g: '價量', label: '距 52 週高 ≤ {v}%', opts: 'num', def: 10, f: (x, v) => { const h = SCR_COLS.hd[1](x); return isNum(h) && h <= v; }, cols: ['hd'] },
  { id: 'vr', g: '價量', label: '量比 ≥ {v} 倍', opts: [1.5, 2, 3], def: 1.5, f: scrGe('vr'), cols: ['vr'] },
  { id: 'rs20', g: '價量', label: '20 日相對大盤 > {v} 百分點', opts: 'num', def: 0, f: (x, v) => isNum(x.rs20) && x.rs20 > v, cols: ['rs20'] },
  { id: 'rs60', g: '價量', label: '60 日相對大盤 > {v} 百分點', opts: 'num', def: 0, f: (x, v) => isNum(x.rs60) && x.rs60 > v, cols: ['rs60'] },
  { id: 's', g: '法人', label: '法人連買 ≥ {v} 日', opts: [3, 5, 10], def: 3, f: scrGe('s'), cols: ['s'] },
  { id: 'fs', g: '法人', label: '外資連買 ≥ {v} 日', opts: [3, 5, 10], def: 3, f: scrGe('fs'), cols: ['fs'] },
  { id: 'ts', g: '法人', label: '投信連買 ≥ {v} 日', opts: [3, 5, 10], def: 3, f: scrGe('ts'), cols: ['ts'] },
  { id: 'f5', g: '法人', label: '外資 5 日買超', sw: true, f: scrPos('f5'), cols: ['f5'] },
  { id: 't5', g: '法人', label: '投信 5 日買超', sw: true, f: scrPos('t5'), cols: ['t5'] },
  { id: 'n5', g: '法人', label: '法人 5 日買超', sw: true, f: scrPos('n5'), cols: ['n5'] },
  { id: 't5r', g: '法人', label: '投信 5 日買超 ≥ 成交額 {v}%', opts: [3, 5, 10], def: 5, title: '5 日成交額以 20 日均額 × 5 估計',
    f: (x, v) => isNum(x.t5) && isNum(x.a20) && x.a20 > 0 && x.t5 >= x.a20 * 5 * v / 100, cols: ['t5r'] },
  { id: 'n5r', g: '法人', label: '法人 5 日買超 ≥ 成交額 {v}%', opts: [3, 5, 10], def: 3, title: '5 日成交額以 20 日均額 × 5 估計',
    f: (x, v) => isNum(x.n5) && isNum(x.a20) && x.a20 > 0 && x.n5 >= x.a20 * 5 * v / 100, cols: ['n5r'] },
  { id: 'n20', g: '法人', label: '法人 20 日買超', sw: true, f: scrPos('n20'), cols: ['n20'] },
  { id: 'm5d', g: '信用', label: '融資 5 日減少 ≥ {v}%', opts: [2, 5, 10], def: 2, f: (x, v) => { const b = m5Base(x); return b > 0 && -x.m5 / b * 100 >= v; }, cols: ['m5', 'm5p'] },
  { id: 'm5u', g: '信用', label: '融資 5 日增加 ≥ {v}%（5 日前 ≥ 1,000 張）', opts: [5, 10, 20], def: 10,
    f: (x, v) => { const b = m5Base(x); return isNum(b) && b >= MARGIN_BASE && x.m5 / b * 100 >= v; }, cols: ['m5', 'm5p'] },
  { id: 'sr', g: '信用', label: '券資比 ≥ {v}%（融資 ≥ 1,000 張）', opts: [10, 20, 30], def: 20, f: (x, v) => isNum(x.mb) && x.mb >= MARGIN_BASE && isNum(x.sr) && x.sr >= v, cols: ['sr'] },
  { id: 'mu', g: '信用', label: '融資使用率 ≥ {v}%', opts: [20, 30, 50], def: 30, f: scrGe('mu'), cols: ['mu'] },
  // 第 11 輪 B14：借券（null = 沒有借券資料或沒有股數 → 不符合）
  { id: 'lp', g: '信用', label: '借券占股本 ≥ {v}%', opts: [3, 5, 8], def: 5, f: scrGe('lp'), cols: ['lb', 'lp'], title: '借券賣出餘額 ÷ 目前發行股數；借券含避險、套利，不等於看空' },
  { id: 'l5', g: '信用', label: '借券 5 日增加 ≥ {v} 張', opts: [500, 1000, 5000], def: 1000, f: scrGe('l5'), cols: ['lb', 'l5'] },
  { id: 'ry', g: '基本面', label: '營收年增 ≥ {v}%', opts: [20, 30, 50], def: 30, f: scrGe('ry'), cols: ['ry'] },
  { id: 'rc', g: '基本面', label: '累計年增 ≥ {v}%', opts: [20, 30, 50], def: 30, f: scrGe('rc'), cols: ['rc'] },
  { id: 'rh', g: '基本面', label: '營收創新高', sw: true, f: scrPos('rh'), cols: ['rh'] },
  { id: 'r3', g: '基本面', label: '連續 3 個月年增', sw: true, f: x => x.r3 === 1, cols: ['r3'] },
  // 第 10 輪 B5：季報（最新一季；null = 沒有季報、去年同季虧損、金融業的毛利率 → 不符合）
  { id: 'ey', g: '基本面', label: '單季 EPS 年增 ≥ {v}%', opts: [0, 20, 50], def: 20, f: scrGe('ey'), cols: ['eq', 'ey'], title: '最新一季單季 EPS 比去年同季；去年同季虧損或為 0 時不計算' },
  { id: 'gmy', g: '基本面', label: '毛利率年增 ≥ {v} 百分點', opts: [0, 1, 3], def: 0, f: scrGe('gmy'), cols: ['gm', 'gmy'], title: '單季毛利率比去年同季；金融業沒有毛利率，不列入' },
  { id: 'e4', g: '基本面', label: '近 4 季 EPS > 0', sw: true, f: scrPos('e4'), cols: ['e4'] },
  { id: 'eh', g: '基本面', label: '單季 EPS 創 {v} 季新高', opts: [4, 8], def: 4, f: scrGe('eh'), cols: ['eq', 'eh'], title: '最新一季單季 EPS 高於之前連續 N 季' },
  { id: 'ed', g: '基本面', label: '單季 EPS 比去年同季下滑', sw: true, f: x => isNum(x.ey) && x.ey < 0, cols: ['eq', 'ey'] },
  { id: 'pe', g: '基本面', label: '0 < 本益比 ≤ {v}', opts: [10, 15, 20], def: 15, val: true, f: (x, v, st) => isNum(x.pe) && x.pe > 0 && x.pe <= v && valGuard(x, st), cols: ['pe'] },
  { id: 'dy', g: '基本面', label: '殖利率 ≥ {v}%', opts: [3, 4, 5, 6], def: 5, val: true, f: (x, v, st) => isNum(x.dy) && x.dy >= v && valGuard(x, st), cols: ['dy'] },
  { id: 'pb', g: '基本面', label: '淨值比 ≤ {v}', opts: [1, 1.5, 2], def: 1, val: true, f: (x, v, st) => isNum(x.pb) && x.pb > 0 && x.pb <= v && valGuard(x, st), cols: ['pb'] },
  { id: 'pbp', g: '基本面', label: '淨值比一年位置 ≤ {v}%', opts: [10, 20, 30], def: 20, val: true, title: '近 242 個交易日中，淨值比小於或等於今天的天數比例',
    f: (x, v, st) => isNum(x.pbp) && x.pbp <= v && valGuard(x, st), cols: ['pb', 'pbp'] },
  { id: 'mk', g: '排除', label: '只看 {v}', opts: [[1, '上市'], [2, '上櫃']], def: 1, f: (x, v) => x.m === (v === 1 ? 'TWSE' : 'TPEx') },
  { id: 'xd', g: '排除', label: '排除處置股（含即將處置）', sw: true, f: x => !x.dsp },
  { id: 'xn', g: '排除', label: '排除今日無成交', sw: true, f: x => !x.nt },
  { id: 'xt', g: '排除', label: '排除注意股', sw: true, f: x => !x.ntc },
  { id: 'xc', g: '排除', label: '估值條件排除 90 天內股本變動', sw: true, f: null, n: x => x.cap === 1 },   // 不單獨篩選
  { id: 'xm', g: '排除', label: '排除停資停券（上市註記 O、X）', sw: true, f: x => !(x.mnt && /[OX]/.test(x.mnt)) },
];
const SCREEN_GROUPS = ['流動性', '價量', '法人', '信用', '基本面', '排除'];
// [id, 按鈕, 條件]；套用時取代全部條件並加上 xd、xn、xc；r1、r2 為參考組（風險檢查）
const SCREEN_PRESETS = [
  ['1', '法人連買＋營收創新高', 's=3&rh=1&tv=0.5'], ['2', '投信認養', 'ts=3&t5=1&t5r=5&tv=0.5'], ['3', '帶量突破', 'nh=60&vr=1.5&tv=1'],
  ['4', '多頭排列＋相對強勢', 'ma=3&rs20=0&f5=1&tv=3'], ['5', '價值高息', 'pe=15&dy=5&tv=0.5'], ['6', '營收高成長', 'ry=30&rc=30&rh=1&tv=1'],
  ['7', '籌碼換手', 'n5r=3&m5d=2&ma=1&tv=0.5'], ['8', '財報優於去年', 'ey=20&gmy=0&tv=0.5'],
  ['r1', '融資追價', 'm5u=10&r5=10&tv=0.5'], ['r2', '軋空觀察', 'sr=20&ma=1&tv=0.5'], ['r3', '本益比低但 EPS 下滑', 'pe=15&ed=1&tv=0.5'],
];
const SCREEN_DEFAULT = { xd: 1, xn: 1, xc: 1, o: 'tv' };
// 條件狀態 = {條件 id: 門檻, o: 排序欄, od: 'a' 遞增／'d' 遞減（省略 = 預設方向）, ps: 套用中的預設}
function scrParse(q) {
  const st = {};
  for (const [k, v] of new URLSearchParams(q)) {
    if (SCREEN_CONDS.some(c => c.id === k)) { if (v !== '' && !isNaN(v)) st[k] = Number(v); }
    else if (k === 'o' || k === 'ps' || (k === 'od' && (v === 'a' || v === 'd'))) st[k] = v;
  }
  return st;
}
const scrQuery = st => [...SCREEN_CONDS.map(c => c.id), 'o', 'od', 'ps'].filter(k => k in st).map(k => `${k}=${encodeURIComponent(st[k])}`).join('&');

async function renderScreen(q) {
  const S = await loadScreen(), L = App.latest;
  if (!S) {
    $('#view').innerHTML = `<section class="sec"><div class="sec-h">${modeSeg('screen')}</div>
      <div class="empty">選股資料尚未產生：請在收集資料的電腦執行 python3 -m twstock export</div></section>`;
    onModeSeg();
    return;
  }
  let st;
  if (q.startsWith('?')) st = scrParse(q.slice(1));                  // 網址有條件：只用網址的條件（不和預設合併）
  else { try { st = JSON.parse(localStore('screen', 'null')); } catch (e) { st = null; } }
  if (!st || typeof st !== 'object') st = { ...SCREEN_DEFAULT };
  let open = matchMedia('(min-width:721px)').matches;                 // 桌面預設展開、手機收合
  const X = screenRows(), M = revMonth();
  const mon = k => k.slice(0, 4) === S.d.slice(0, 4) ? `${Number(k.slice(4))} 月` : `${k.slice(0, 4)}/${k.slice(4)} 月`;
  const mdx = d => d ? md(d) : '--';
  const notes = [S.d !== L.date || S.fd !== L.flow_date
    ? `<div class="flow-note">選股資料（行情 ${md(S.d)}）與網站資料（${md(L.date)}）不同步，請在收集資料的電腦執行 python3 -m twstock export</div>` : '',
    flowNote(),
    ...[...new Set(Object.values(S.md).filter(d => d < S.d))].map(d => `<div class="flow-note">融資融券尚未更新：信用條件與欄位為 ${md(d)} 的資料</div>`)].join('');
  const save = () => localStore('screen', null, JSON.stringify(st));
  const pass = (c, x) => !c.f || c.f(x, st[c.id], st);

  const draw = () => {
    history.replaceState(null, '', '#/rank/screen?' + scrQuery(st));
    const conds = SCREEN_CONDS.filter(c => c.id in st);
    const hits = X.filter(x => conds.every(c => pass(c, x)));
    const cols = [...new Set(conds.flatMap(c => c.cols || []))];
    const o = st.o && (st.o === 'p' || st.o === 'tv' || SCR_COLS[st.o]) ? st.o : 'tv';
    const get = o === 'p' || o === 'tv' ? x => x[o] : SCR_COLS[o][1];
    const dir = st.od === 'a' ? 1 : st.od === 'd' ? -1 : SCR_COLS[o]?.[3] || -1;
    const vals = new Map(hits.map(x => [x, get(x)]));
    hits.sort((a, b) => { const va = vals.get(a), vb = vals.get(b);
      return (!isNum(va)) - (!isNum(vb)) || (isNum(va) && isNum(vb) ? dir * (va - vb) : 0) || (b.tv ?? 0) - (a.tv ?? 0); });
    const oName = o === 'p' ? '漲跌' : o === 'tv' ? '成交額' : o === 'ry' && M ? `營收年增（${Number(M.slice(4))} 月）` : SCR_COLS[o][0];
    const cnt = c => {                                              // 單獨符合（排除類為排除檔數）；目前門檻、對全體計算
      const v = c.id in st ? st[c.id] : c.def;
      if (c.n) return X.filter(c.n).length;
      return c.g === '排除' ? X.filter(x => !c.f(x, v, st)).length : X.filter(x => c.f(x, v, st)).length;
    };
    const ctl = c => {
      const v = c.id in st ? st[c.id] : c.def;
      if (c.sw) return '';
      if (c.opts === 'num') return `<input type="number" step="any" data-v="${c.id}" value="${v}">`;
      return `<select class="sel" data-v="${c.id}">${c.opts.map(x => { const [ov, ol] = Array.isArray(x) ? x : [x, x];
        return `<option value="${ov}"${ov === v ? ' selected' : ''}>${ol}</option>`; }).join('')}</select>`;
    };
    const condHTML = c => { const [pre, post = ''] = c.label.split('{v}');
      return `<label class="scr-c"${c.title ? ` title="${c.title}"` : ''}><input type="checkbox" data-c="${c.id}"${c.id in st ? ' checked' : ''}>${pre}${ctl(c)}${post}` +
        `<span class="scr-n">${c.g === '排除' ? '排除' : '單獨'} ${fmt(cnt(c))}</span></label>`; };
    const chip = ([id, name], ref) => `<button class="chip${ref ? ' ref' : ''}${st.ps === id ? ' on' : ''}" data-ps="${id}"${ref ? ' title="風險檢查，不是買進訊號"' : ''}>${name}</button>`;
    $('#view').innerHTML = `<section class="sec">
      <div class="sec-h">${modeSeg('screen')}</div>
      <div class="muted small">行情 ${md(S.d)}｜法人 ${md(S.fd)}｜融資融券 上市 ${mdx(S.md.TWSE)}、上櫃 ${mdx(S.md.TPEx)}｜營收 ${Object.entries(S.rmd).sort((a, b) => b[0].localeCompare(a[0])).map(([k, n]) => `${mon(k)} ${fmt(n)} 檔`).join('、') || '--'}${revMixed(S) ? '（每月 1～10 日為公布期間，各股月份不同）' : ''}｜季報 ${Object.entries(S.fqd || {}).sort((a, b) => b[0].localeCompare(a[0])).map(([k, n]) => `${k.slice(0, 4) === S.d.slice(0, 4) ? '' : k.slice(0, 4) + ' '}Q${Number(k.slice(4))} ${fmt(n)} 檔`).join('、') || '--'}${finMixed(S) ? '（財報公布期間，各股季別不同）' : ''}</div>
      <div style="margin-top:8px">${notes}</div>
      <div class="sec-h" style="margin:8px 0 0;gap:6px"><span class="muted small">預設：</span>${SCREEN_PRESETS.filter(p => p[0][0] !== 'r').map(p => chip(p)).join('')}
        <span class="muted small">參考：</span>${SCREEN_PRESETS.filter(p => p[0][0] === 'r').map(p => chip(p, true)).join('')}</div>
      <details class="scr-panel card"${open ? ' open' : ''}><summary>條件（已選 ${conds.length} 個）
        <button class="chip" id="scrClear">重設</button> <button class="chip" id="scrCopy">複製條件連結</button></summary>
        ${SCREEN_GROUPS.map(g => `<div class="scr-grp"><b>${g}</b><div>${SCREEN_CONDS.filter(c => c.g === g).map(condHTML).join('')}</div></div>`).join('')}
      </details>
      <div class="sec-h" style="margin:8px 0"><h2>符合 ${fmt(hits.length)} 檔</h2>${hits.length > 100 ? `<span class="muted small">依「${oName}」排序顯示前 100 檔</span>` : ''}</div>
      <div class="card">${hits.length ? screenTable(hits.slice(0, 100), cols, { sort: o, cap: conds.some(c => c.val) })
        : '<div class="empty">沒有同時符合所有條件的股票。參考各條件的「單獨」檔數，放寬最少的那一個。</div>'}</div>
      <div class="muted small" style="margin-top:6px">篩選結果只是條件的機械比對，不是投資建議。報酬、乖離、均線、新高新低都用還原價格（除權息、減資、面額變更不會造成跳動）；量比 = 今日成交額 ÷ 前 20 個交易日平均（無成交日以 0 計），不受面額變更影響。法人金額為張數 × 收盤估算，不含 ETF；投信買超會受主動 ETF 申購影響（申購的資金會被動買進股票，個股頁「主動 ETF 持有」卡列出已收主動 ETF 占投信買超的張數）。本益比、殖利率、淨值比為官方值，90 天內有除權、減資或面額變更的股票官方值可能尚未調整，預設排除。營收條件以各股最新公布的月份判斷：每月 1～10 日是公布期間，已公布的公司當天就換成新月份，各股月份不同（營收欄會標出和欄名不同的月份）。季報條件以各股最新一季判斷：單季 EPS 由累計相減，去年同季虧損時不計算年增，金融業沒有毛利率；財報公布期間各股季別不同（欄位會標出和欄名不同的季別）。融資融券為張；融資增加率、券資比只計入融資 1,000 張以上的股票。</div></section>`;
    const changed = () => { delete st.ps; save(); draw(); };
    onModeSeg();
    $('#view').querySelectorAll('[data-ps]').forEach(b => b.addEventListener('click', () => {
      st = { ...scrParse(SCREEN_PRESETS.find(p => p[0] === b.dataset.ps)[2]), xd: 1, xn: 1, xc: 1, o: 'tv', ps: b.dataset.ps };
      save(); draw();
    }));
    $('#view').querySelectorAll('[data-c]').forEach(el => el.addEventListener('change', () => {
      const c = SCREEN_CONDS.find(x => x.id === el.dataset.c);
      if (!el.checked) delete st[c.id];
      else { const v = $(`[data-v="${c.id}"]`)?.value; st[c.id] = c.sw ? 1 : v !== undefined && v !== '' && !isNaN(v) ? Number(v) : c.def; }
      changed();
    }));
    $('#view').querySelectorAll('[data-v]').forEach(el => el.addEventListener('change', () => {
      if (el.value === '' || isNaN(el.value)) return;
      st[el.dataset.v] = Number(el.value);                              // 改門檻即啟用該條件
      changed();
    }));
    $('#view').querySelectorAll('th.sort').forEach(el => el.addEventListener('click', () => {
      const k = el.dataset.k;
      if (k === o) st.od = dir === 1 ? 'd' : 'a';
      else { st.o = k; delete st.od; }
      save(); draw();
    }));
    const det = $('#view details.scr-panel');
    det.addEventListener('toggle', () => { open = det.open; });
    $('#scrClear').addEventListener('click', e => { e.preventDefault(); st = { ...SCREEN_DEFAULT }; save(); draw(); });   // P23：回到預設（保留共同排除）
    $('#scrCopy').addEventListener('click', e => {
      e.preventDefault();
      const b = e.currentTarget;
      navigator.clipboard?.writeText(location.href).then(() => { b.textContent = '已複製'; setTimeout(() => { b.textContent = '複製條件連結'; }, 1500); })
        .catch(() => prompt('複製這個連結', location.href)) ?? prompt('複製這個連結', location.href);
    });
  };
  draw();
  $('#view').addEventListener('click', onRowClick);
}

// ─── ETF（E1）：與股票完全分開，不計入任何個股統計 ─────────
const ETF_SORT = [['tv', '成交額', -1], ['p+', '漲幅', -1], ['p-', '跌幅', 1], ['m1', '融資增減', -1], ['s1', '融券增減', -1],
  ['l1+', '借券增加', -1], ['l1-', '借券減少', 1], ['lb', '借券餘額', -1]];     // 第 12 輪 ETF-借券

function renderEtf() {
  const E = App.latest.etfs;
  if (!E) {
    $('#view').innerHTML = '<div class="empty">尚無 ETF 資料：請在收集資料的電腦執行 python3 -m twstock history --start 2025-10-30 --only etf margin</div>';
    return;
  }
  const by = localStore('etfSort', 'tv'), mkt = localStore('etfMkt', 'all');
  const [key, , dir] = ETF_SORT.find(x => x[0] === by) || ETF_SORT[0];
  const f = key.replace(/[+-]$/, '');
  const list = Object.entries(E.rows).filter(([, r]) => mkt === 'all' || r.m === mkt)
    .sort((a, b) => (a[1][f] == null) - (b[1][f] == null) || dir * ((a[1][f] ?? 0) - (b[1][f] ?? 0)));
  const lots = v => `<td class="num ${cls(v)}">${v == null ? '--' : sgn(v, 0)}</td>`;
  const dates = Object.entries(E.dates).map(([m, d]) => `${m === 'TWSE' ? '上市' : '上櫃'} ${md(d)}`).join('　');
  $('#view').innerHTML = `<section class="sec">
      <div class="sec-h"><h2>ETF</h2><span class="muted small">${dates}</span>${App.latest.active_rank ? '<a class="pill hold" href="#/etf/active">主動 ETF 彙總</a>' : ''}<span class="sp"></span>
        ${segHTML('etfMktSeg', [['all', '全部'], ['TWSE', '上市'], ['TPEx', '上櫃']], mkt)}
        <select id="etfSel" class="sel" aria-label="排序">${ETF_SORT.map(x => `<option value="${x[0]}"${x[0] === by ? ' selected' : ''}>${x[1]}</option>`).join('')}</select></div>
      <div class="card"><div class="tbl-wrap"><table class="tbl"><thead><tr>
        <th>ETF</th><th>收盤</th><th>漲跌</th><th>成交量</th><th>成交額</th><th>融資餘額</th><th>融資增減</th><th>融券餘額</th><th>融券增減</th><th>借券餘額</th><th>借券增減</th></tr></thead><tbody>` +
      list.map(([c, r]) => `<tr${App.latest.holdings?.[c] ? ` data-etf="${c}"` : ''}><td class="nm"><b>${esc(r.n)}</b><span>${c} ${r.m === 'TWSE' ? '上市' : '上櫃'}</span>${holdTag(c)}</td>
        <td class="num ${cls(r.ch)}">${pfmt(r.c)}</td>
        <td class="num ${cls(r.ch)}">${r.c == null ? '無成交' : sgn(r.p) + '%'}</td>
        <td class="num">${fmt(r.v)}</td><td class="num">${fmt(r.tv, 2)}億</td>
        <td class="num">${r.mb == null ? '--' : fmt(r.mb)}</td>${lots(r.m1)}
        <td class="num">${r.sb == null ? '--' : fmt(r.sb)}</td>${lots(r.s1)}
        <td class="num">${r.lb == null ? '--' : fmt(r.lb)}</td>${lots(r.l1)}</tr>`).join('') +
      `</tbody></table></div></div>
      <div class="muted small" style="margin-top:6px">共 ${list.length} 檔。成交量為張、成交額為億元；融資融券為張，增減 = 今日餘額 − 前日餘額，「--」表示不在信用交易清單。借券為借券賣出（張，資料晚上 8 點半以後更新），多為造市、套利與避險，不等於看空。ETF 不計入首頁家數、成交額、類股資金流、排行、自選與股票口徑的融資融券。</div></section>`;
  $('#etfSel').addEventListener('change', e => { localStore('etfSort', null, e.target.value); renderEtf(); });
  onSeg('etfMktSeg', v => { localStore('etfMkt', null, v); renderEtf(); });
  $('#view').addEventListener('click', e => { const tr = e.target.closest('tr[data-etf]'); if (tr) location.hash = '#/etf/' + tr.dataset.etf; });
}

// ─── F7-2：主動 ETF 彙總排行 ─────────────────────────────
const ACT_NOTE = '估算金額 = 各 ETF 張數增減 × 該 ETF 持股日收盤，不是實際成交金額；只含台股。各 ETF 用自己的最新持股日（跨境 ETF 晚一個交易日）。';
const actDates = R => R.etfs.map(x => `${x.c} ${md(x.d)}`).join('、') +
  (R.stale.length ? `；未更新：${R.stale.map(x => `${x.c}（停在 ${md(x.d)}）`).join('、')}` : '');
const actEtfs = r => r.e.map(x => `<a href="#/etf/${x.e}">${x.e}</a> ${sgn(x.d1, 0)}${x.new ? '<i class="al al-new">新</i>' : x.out ? '<i class="al">清</i>' : ''}`).join('、');
const actRows = (list, full) => list.map(r => `<tr data-code="${r.c}"><td class="nm"><b>${esc(r.n)}</b><span>${r.c}</span></td>
    <td class="num ${cls(r.a)}">${sgn(r.a, 2)}</td><td class="num ${cls(r.l1)}">${sgn(r.l1, 0)}</td>` +
  (full ? `<td class="num ${cls(r.l5)}">${r.l5 == null ? '--' : sgn(r.l5, 0)}</td><td class="small">${actEtfs(r)}</td>` : '') + '</tr>').join('');

// F8-1：標題的投信與檔數、各檔單位數 1 日變化（申購影響）
const actTitle = R => `${[...new Set([...R.etfs, ...R.stale].map(x => x.t))].join('、')} ${Object.keys(App.latest.holdings || {}).length} 檔`;
function unitsLine(L) {
  const H = Object.entries(L.holdings || {});
  if (!H.length) return '';
  const top = H.map(([, h]) => h.d).sort().at(-1);
  const part = list => list.sort((a, b) => (a[1].u1 == null) - (b[1].u1 == null) || (b[1].u1 ?? 0) - (a[1].u1 ?? 0))
    .map(([c, h]) => `<a href="#/etf/${c}">${c}</a> <span class="${cls(h.u1)}">${h.u1 == null ? '--' : sgn(h.u1) + '%'}</span>`).join('、');
  const cur = H.filter(([, h]) => h.d === top), other = H.filter(([, h]) => h.d !== top);
  const od = [...new Set(other.map(([, h]) => md(h.d)))].join('、');
  return `<div class="small num" style="margin-top:4px">單位數 1 日：${part(cur)}${other.length ? `；跨境（${od}）：${part(other)}` : ''}</div>
    <div class="muted small">單位數增加 = 淨申購。申購的資金會由經理人買進股票，所以多檔單位數同時增加的日子，「合計加碼」會偏多，不全是看好。</div>`;
}

// 今日頁小卡：買超、賣超各 5 名
function activeCard(R) {
  if (!R || !R.etfs.length) return '';
  const tbl = (t, list) => `<div class="card"><div class="sec-h"><h2>${t}</h2><span class="muted small">億，估算</span></div>
    <div class="tbl-wrap"><table class="tbl"><thead><tr><th>股票</th><th>估算金額</th><th>張數</th></tr></thead><tbody>${actRows(list.slice(0, 5)) ||
    '<tr><td colspan="3" class="muted">無</td></tr>'}</tbody></table></div></div>`;
  return `<section class="sec"><div class="sec-h"><h2>${actTitle(R)}主動 ETF 一起買了什麼</h2><span class="muted small">${R.etfs.length} 檔合計</span>
      <span class="sp"></span><a class="muted small" href="#/etf/active">完整排行 →</a></div>
    <div style="margin:-6px 0 10px">${unitsLine(App.latest)}</div>
    <div class="grid g2">${tbl('主動 ETF 合計加碼', R.buy)}${tbl('主動 ETF 合計減碼', R.sell)}</div></section>`;
}

function renderActive() {
  const R = App.latest.active_rank;
  if (!R || !R.etfs.length) { $('#view').innerHTML = '<div class="empty">尚無主動 ETF 持股資料</div>'; return; }
  const head = '<thead><tr><th>股票</th><th>估算金額（億）</th><th>1 日張數</th><th>5 日張數</th><th>參與 ETF（張數增減）</th></tr></thead>';
  $('#view').innerHTML = `<section class="sec card">
      <div class="sec-h"><h2>主動 ETF 彙總（${actTitle(R)}）</h2><span class="muted small">${R.etfs.length} 檔</span><span class="sp"></span><a class="muted small" href="#/etf">← ETF 列表</a></div>
      <div class="muted small">持股日：${actDates(R)}</div>${unitsLine(App.latest)}</section>
    ${[['合計加碼', R.buy], ['合計減碼', R.sell]].map(([t, list]) => `<section class="sec card"><div class="sec-h"><h2>${t}</h2></div>
      <div class="tbl-wrap"><table class="tbl">${head}<tbody>${actRows(list, true) || '<tr><td colspan="5" class="muted">無</td></tr>'}</tbody></table></div></section>`).join('')}
    <section class="sec card"><div class="sec-h"><h2>最多檔持有</h2><span class="muted small">市值為估算（億）</span></div>
      <div class="tbl-wrap"><table class="tbl"><thead><tr><th>股票</th><th>檔數</th><th>合計張數</th><th>估算市值</th><th>各 ETF 權重</th></tr></thead><tbody>` +
      R.held.map(r => `<tr data-code="${r.c}"><td class="nm"><b>${esc(r.n)}</b><span>${r.c}</span></td><td class="num">${r.k}</td>
        <td class="num">${fmt(r.l)}</td><td class="num">${fmt(r.v, 1)}</td>
        <td class="small">${r.e.map(x => `<a href="#/etf/${x.e}">${x.e}</a> ${fmt(x.w, 2)}%`).join('、')}</td></tr>`).join('') +
      `</tbody></table></div>
      <div class="muted small" style="margin-top:6px">${ACT_NOTE}標「新」= 前一持股日沒有持有，「清」= 最新持股日已出清。</div></section>`;
  $('#view').addEventListener('click', e => { if (!e.target.closest('a')) onRowClick(e); });   // 列內的 ETF 連結不要被整列的個股連結蓋掉
}

// E2-4：已支援持股的主動 ETF 可點；其他主動型（代號 A 結尾）標示尚未支援
const holdTag = c => App.latest.holdings?.[c] ? `<a class="pill hold" href="#/etf/${c}">持股</a>`
  : /A$/.test(c) ? '<span class="pill muted">持股尚未支援</span>' : '';

const HOLD_SORT = [['pw', '權重'], ['d1', '張數增減'], ['w1', '權重變化']];

async function renderHoldings(code) {
  // 不在支援清單就不請求（避免 404）
  const H = App.latest.holdings?.[code] && await getJSON(`data/etfs/${code}.json`);
  if (!H) { $('#view').innerHTML = `<div class="empty">${esc(code)} 的持股資料尚未支援（目前支援統一、群益投信 8 檔主動 ETF）</div>`; return; }
  const S = H.sum, by = localStore('holdSort', 'pw'), unit = r => r.tw ? '張' : '股';
  const rows = [...H.rows].sort((a, b) => (b[by] ?? -Infinity) - (a[by] ?? -Infinity));
  const prev = H.dates.at(-2), d5 = H.dates.length > 5 ? H.dates.at(-6) : null;
  const chg = (v, d = 0) => `<td class="num ${cls(v)}">${v == null ? '--' : sgn(v, d)}</td>`;
  const name = r => r.tw ? `<b>${esc(r.n)}</b><span>${esc(r.c)}</span>` : `<b>${esc(r.n)}</b><span>${esc(r.c)}（海外）</span>`;
  $('#view').innerHTML = `<section class="sec card">
      <div class="sec-h"><h2>${esc(H.n)}</h2><span class="muted small">${code}　${H.m === 'TWSE' ? '上市' : '上櫃'}　持股日 ${md(S.d)}${H.delay ? '（跨境，晚一個交易日公布）' : ''}</span>
        <span class="sp"></span><a class="muted small" href="#/etf">← ETF 列表</a></div>
      <div class="grid g-stats">
        ${[['淨資產', fmt(S.nav, 1) + ' 億'], ['每單位淨值', fmt(S.nu, 2) + ' 元'], ['股票權重合計', fmt(S.sw, 2) + '%'], ['持股檔數', fmt(S.n) + ' 檔'],
           ['單位數 1 日', S.u1 == null ? '--' : sgn(S.u1) + '%', prev ? `相對 ${md(prev)}` : ''],
           ['期貨', S.fl ? `${fmt(S.fl)} 口（${fmt(S.fa, 1)} 億）` : '無']].map(([l, v, sub]) => `<div class="card stat"><div class="l">${l}</div><div class="v num" style="font-size:16px">${v}</div>${sub ? `<div class="s">${sub}</div>` : ''}</div>`).join('')}
      </div></section>
    <section class="sec card">
      <div class="sec-h"><h2>持股</h2><span class="muted small">${prev ? `1 日：相對 ${md(prev)}` : '只有一個持股日'}${d5 ? `；5 日：相對 ${md(d5)}` : ''}</span><span class="sp"></span>${segHTML('holdSeg', HOLD_SORT, by)}</div>
      <div class="tbl-wrap"><table class="tbl"><thead><tr><th>股票</th><th>持有</th><th>權重</th><th>1 日增減</th><th>1 日權重變化</th><th>5 日增減</th></tr></thead><tbody>` +
      rows.map(r => `<tr${r.tw ? ` data-code="${esc(r.c)}"` : ''}><td class="nm">${name(r)}${r.new ? '<i class="al al-new">新</i>' : ''}</td>
        <td class="num">${fmt(r.l)} ${unit(r)}</td><td class="num">${fmt(r.pw, 2)}%</td>${chg(r.d1)}${chg(r.w1, 2)}${chg(r.d5)}</tr>`).join('') +
      `</tbody></table></div>
      ${H.out.length ? `<div class="sec-h" style="margin-top:12px"><h2>出清</h2><span class="muted small">${md(prev)} 持有、${md(S.d)} 已無</span></div>
        <div class="tbl-wrap"><table class="tbl"><thead><tr><th>股票</th><th>${md(prev)} 持有</th><th>權重</th></tr></thead><tbody>` +
        H.out.map(r => `<tr${r.tw ? ` data-code="${esc(r.c)}"` : ''}><td class="nm">${name(r)}</td><td class="num">${fmt(r.l)} ${unit(r)}</td><td class="num">${fmt(r.pw, 2)}%</td></tr>`).join('') +
        '</tbody></table></div>' : ''}
      <div class="muted small" style="margin-top:6px">資料來源：${esc(H.trust || '統一')}投信每日申購買回清單。台股為張、海外為股；權重為占基金淨資產 %，權重變化為百分點。
        本基金為現金申購買回：申購進來的資金由經理人買進股票，所以<b>申購多的日子加碼會偏多</b>、贖回多的日子減碼會偏多。${S.u1 == null ? '' : `${S.d === App.latest.date ? '今天' : md(S.d) + ' '}單位數 1 日 ${sgn(S.u1)}%，張數增幅接近這個比例的持股，多半是跟著申購買進；明顯超過的才比較像經理人的判斷。`}權重變化另含股價漲跌的影響（張數不變、權重也會變）。標「新」= 前一持股日沒有持有。</div></section>`;
  onSeg('holdSeg', v => { localStore('holdSort', null, v); renderHoldings(code); });
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

// ─── 資料新鮮度（S4）────────────────────────────────────
const FRESH_HOUR = 18;              // 交易日 18:00 後才要求有當天資料
App.now = () => new Date();         // 測試可替換：App.now = () => new Date('2026-11-02T18:30:00+08:00')
App.checkedAt = 0;
App.newDate = null;

function twParts(t) {               // 一律換算成台灣時間，不依賴瀏覽器時區
  const p = Object.fromEntries(new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Taipei', year: 'numeric', month: '2-digit',
    day: '2-digit', hour: '2-digit', hourCycle: 'h23' }).formatToParts(t).map(x => [x.type, x.value]));
  return { date: `${p.year}-${p.month}-${p.day}`, hour: Number(p.hour) };
}
// 依交易日曆，現在應該有哪一天的資料；closed = 平日休市日（YYYY-MM-DD）
function expectedDate(t, closed) {
  const open = d => { const w = new Date(d + 'T00:00:00Z').getUTCDay(); return w > 0 && w < 6 && !closed.has(d); };
  const prev = d => new Date(Date.parse(d + 'T00:00:00Z') - 864e5).toISOString().slice(0, 10);
  const { date, hour } = twParts(t);
  let d = open(date) && hour >= FRESH_HOUR ? date : prev(date);
  while (!open(d)) d = prev(d);
  return d;
}
function freshLines(L, t) {
  const st = L.status;
  if (!st) return [];               // 舊版 latest.json：維持原本的日期列
  const lines = [], exp = expectedDate(t, new Set(st.closed || []));
  if (L.date < exp) lines.push(`資料停在 ${md(L.date)}，最新交易日為 ${md(exp)}，可能尚未收集。請在收集資料的電腦執行 python3 -m twstock collect --catch-up`);
  const bad = (st.datasets || []).filter(x => x.s === 'abnormal' && x.m).map(x => x.m);
  if (bad.length) lines.push(`部分資料異常：${bad.slice(0, 3).join('、')}${bad.length > 3 ? ` 等 ${bad.length} 項` : ''}`);
  return lines;
}
function renderStatus() {
  const L = App.latest, when = (L.updated_at || '').slice(0, 16).replace('T', ' ');
  $('#dateBar').textContent = `資料日 ${L.date}　法人資料 ${L.flow_date}　更新於 ${when}` +
    (L.status?.collected_src === 'db' ? '（依資料寫入時間）' : '');
  const lines = freshLines(L, App.now()).map(x => `<div>${esc(x)}</div>`);
  if (App.newDate) lines.push(`<div>網站資料已更新（資料日 ${md(App.newDate)}）<button id="reloadBtn">重新整理</button></div>`);
  const bar = $('#freshBar');
  bar.innerHTML = lines.join('');
  bar.hidden = !lines.length;
  $('#reloadBtn')?.addEventListener('click', () => location.reload());
}
// 分頁回到前景：重新判斷新鮮度；latest.json 有變就提示重新整理，不自動跳轉
async function recheckLatest() {
  renderStatus();
  if (Date.now() - App.checkedAt < 60000) return;
  App.checkedAt = Date.now();
  let fresh;
  try { fresh = await getJSON('data/latest.json'); } catch (e) { return; }     // 匯出中或離線：下次再檢查
  const key = x => [x.date, x.flow_date, x.updated_at].join('|');
  if (key(fresh) !== key(App.latest)) App.newDate = fresh.date;
  if (fresh.status) App.latest.status = fresh.status;     // 只影響橫幅：登記臨時休市後不用重新整理就會消失
  renderStatus();
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
  renderStatus();
  document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible') recheckLatest(); });
  window.addEventListener('hashchange', route);
  route();
}
document.addEventListener('DOMContentLoaded', init);
