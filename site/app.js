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
// 第 50 輪 F50-1（R73）：有成交且收在漲停價／跌停價（匯出的 lm = 1／-1）時，百分比下面加小字「漲停」「跌停」
const pctCell = s => s.nt ? `<td class="flat small" title="最後成交 ${s.nt}">無成交</td>`
  : `<td class="num ${cls(s.p)}${s.rel ? ' rel' : ''}"${s.rel ? ` title="相對 ${md(s.rel)} 收盤（前一交易日無成交）"` : ''}>${sgn(s.p)}%${s.lm === 1 ? '<span class="sub2">漲停</span>' : s.lm === -1 ? '<span class="sub2">跌停</span>' : ''}</td>`;
// 不到 0.05 億四捨五入後是 0，避免顯示「-0.0億」
// 第 30 輪 D30-10：ycls 是 yi 數字的漲跌色，顯示「0億」時為灰色（顏色跟著顯示的數字）
const yi = n => n == null ? '--' : Math.abs(n) < 0.05 ? '0億' : sgn(n, Math.abs(n) >= 100 ? 0 : 1) + '億', ycls = n => cls(n != null && Math.abs(n) < 0.05 ? 0 : n);
const css = name => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

async function getJSON(url) {
  const r = await fetch(url, { cache: 'no-cache' });
  if (!r.ok) throw new Error(`${url} ${r.status}`);
  return r.json();
}
async function loadStock(code, dir = 'stocks') {     // 第 15 輪 F15-2：ETF 個股頁讀 data/etfp/
  if (!App.stockCache[code]) App.stockCache[code] = await getJSON(`data/${dir}/${code}.json`);
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
  rank: arg => arg && arg.startsWith('screen') ? renderScreen(arg.slice(6)) : arg === 'hl' ? renderHl() : renderRank(arg),   // 第 8 輪：#/rank/screen 條件選股；第 21 輪：#/rank/hl 新訊號
  watch: renderWatch,
  etf: code => code === 'active' ? renderActive() : code ? renderHoldings(code) : renderEtf(),   // 第 7 輪：#/etf/active 彙總排行
  stock: (code, sub) => window.renderStock(code, sub),   // 第 25 輪 D25-08：#/stock/代號/分頁
  tools: arg => window.renderTools(arg),                 // 第 34 輪：試算工具 #/tools/dt|cp|pl（tools.js）
  help: arg => window.renderHelp(arg),                   // 第 45 輪：名詞說明 #/help、#/help/代號（help.js）
  compare: (arg, sub) => window.renderCompare(arg, sub),   // 第 48 輪：報酬率比較 #/compare/代號,代號/區間（compare.js）
};

// 第 28 輪 D28-03：瀏覽器「返回／前進」回到看過的頁面時還原捲動位置；點連結進新頁才回到頂端。
// 每一筆瀏覽紀錄在 history.state.k 有自己的鍵（新紀錄的 state 是 null），捲動時記下位置
const scrollAt = {};
let scrollKey = null;
async function route() {
  const share = location.hash.match(/^#\/watch\?add=([^&#]*)/);   // 第 32 輪 F32-2：分享連結先記下代號、網址換回 #/watch（重新整理不會再問）
  if (share) { App.watchAdd = share[1].split(','); history.replaceState(history.state, '', '#/watch'); }
  const tl = location.hash.match(/^#\/tools(?:\/([^?]*))?(\?.*)?$/);   // 第 34 輪：#/tools、#/tools?c=、不認得的分頁補成 #/tools/dt（保留 ?c=）
  if (tl && !['dt', 'ac', 'cp', 'pl', 'dv'].includes(tl[1])) history.replaceState(history.state, '', '#/tools/dt' + (tl[2] || ''));
  const [, page = 'today', arg, sub] = location.hash.split('/');
  const k = history.state?.k;
  scrollKey = null;                                                     // 換頁中（內容長度改變）的捲動不記
  if ((page === 'watch' || page === 'bubble') && arg) history.replaceState(history.state, '', '#/' + page);   // D28-08：這兩頁沒有子頁
  if (page !== 'watch') App.watchShare = App.watchAdd = App.watchUndo = App.watchEdit = null;   // 離開自選頁：清掉復原、結束編輯
  // 第 27 輪 D27-10：瀏覽器分頁標題帶頁面名稱（個股頁由 renderStock 換成「名稱 代號」）
  document.title = ({ today: '今日', bubble: '泡泡圖', rank: { hl: '新訊號', screen: '選股' }[String(arg).split('?')[0]] || '排行',
    etf: arg === 'active' ? '主動 ETF 彙總' : arg ? arg + ' 持股' : 'ETF', watch: '自選', tools: '工具', help: '名詞說明', compare: '報酬率比較' }[page] || (page === 'stock' ? arg : '今日')) + '｜台股資金流';
  document.querySelectorAll('[data-tab]').forEach(a => a.classList.toggle('on', a.dataset.tab === page));
  const view = $('#view');
  if (window.Plotly && $('#bubble')) Plotly.purge('bubble');
  window.disposeStockCharts?.();
  disposeFuturesChart();
  try {
    await (routes[page] || renderToday)(arg, sub);
  } catch (e) {
    console.error(e);
    view.innerHTML = `<div class="empty">載入失敗：${esc(e.message)}</div>`;
  }
  window.scrollTo(0, k && scrollAt[k] || 0);
  scrollKey = k || Date.now() + Math.random();
  if (history.state?.k !== scrollKey) history.replaceState({ k: scrollKey }, '');   // 不帶網址：保留各頁補正後的網址
}
// QA28-01：同一頁切換分頁、期間、條件時會用 replaceState(null, …) 改網址，順便清掉這筆紀錄的鍵。
// 捲動時記位置並把鍵補回；點擊（離開這頁之前）也補一次，涵蓋「切換後沒捲動就點進個股」。不帶網址，保留切換後的網址
function saveScroll() {
  if (!scrollKey) return;
  scrollAt[scrollKey] = window.scrollY;
  if (history.state?.k !== scrollKey) history.replaceState({ k: scrollKey }, '');
}

// 第 27 輪 D27-01：25 列以上的表格不再關在固定高度的捲動框裡（整頁捲動，不會被畫面底部或底部選單擋住）。
// .tbl-wrap 要保留橫向捲動，CSS sticky 只能貼在框內，所以捲動時把表頭位移到頂欄下方（--th-y，最多到表格最後兩列）
function stickHeads() {
  const top = Math.max($('.top').getBoundingClientRect().bottom, $('#view .pt-stick')?.getBoundingClientRect().bottom ?? 0);   // 第 30 輪 D30-01
  [...document.querySelectorAll('#view .tbl-wrap:not(.panel-list)')].filter(w => w.querySelector('tbody tr:nth-child(25)'))
    .map(w => [w, w.getBoundingClientRect(), w.querySelector('thead')?.offsetHeight || 0])
    .forEach(([w, r, h]) => w.style.setProperty('--th-y', Math.max(0, Math.min(top - r.top, r.height - 2 * h)) + 'px'));
}

// ─── 搜尋 ───────────────────────────────────────────────
function setupSearch() {
  const input = $('#q'), list = $('#qList');
  let hits = [], active = -1;
  const go = code => { list.hidden = true; input.value = ''; input.blur(); location.hash = '#/stock/' + code; };
  const draw = () => {
    list.innerHTML = hits.map(([c, s], i) =>
      `<a href="#/stock/${c}" class="${i === active ? 'on' : ''}"><span class="code">${c}</span><span class="qn">${esc(s.n)}</span><span class="muted small ind" style="margin-left:auto">${esc(s.i ?? 'ETF')}</span>` +
      `<span class="px num ${cls(s.p)}">${pfmt(s.c)}${s.p == null ? '' : ' ' + sgn(s.p) + '%'}</span>` +
      `<span class="qstar${App.watch.has(c) ? ' on' : ''}" role="button" data-w="${c}" title="${App.watch.has(c) ? '從自選移除' : '加入自選'}">${App.watch.has(c) ? '★' : '☆'}</span></a>`).join('') ||   // D27-09
      (input.value.trim() && App.latest ? `<div class="qnone">找不到「${esc(input.value.trim())}」，可輸入代號或名稱的一部分</div>` : '');   // 第 25 輪 D25-11
    list.hidden = !list.innerHTML;
  };
  input.addEventListener('input', () => {
    const q = input.value.trim().toLowerCase();
    if (!q || !App.latest) { hits = []; return draw(); }
    // 第 15 輪 F15-2：股票照舊在前（代號開頭 → 名稱包含），ETF（latest.json etfs.rows）同規則接在後面
    // 第 25 輪 D25-11：名稱開頭符合的排在名稱包含之前，兩組各依成交額由大到小
    const byTv = (a, b) => (b[1].tv ?? 0) - (a[1].tv ?? 0), nm = s => s.n.toLowerCase();
    const pick = all => { const rest = all.filter(([c]) => !c.toLowerCase().startsWith(q));   // 代號轉小寫：00981A
      return all.filter(([c]) => c.toLowerCase().startsWith(q)).concat(rest.filter(([, s]) => nm(s).startsWith(q)).sort(byTv), rest.filter(([, s]) => !nm(s).startsWith(q) && nm(s).includes(q)).sort(byTv)); };
    hits = pick(Object.entries(App.latest.stocks)).concat(pick(Object.entries(App.latest.etfs?.rows || {}))).slice(0, 12);
    active = -1;                                                        // 第 39 輪：預設不選取；Enter 要先用方向鍵選到，或輸入完整代號
    draw();
  });
  input.addEventListener('keydown', e => {
    if (e.isComposing || e.keyCode === 229) return;                     // 第 39 輪：注音、倉頡選字中的 Enter 不送出
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      const n = hits.length;
      if (n) active = e.key === 'ArrowDown' ? (active + 1) % n : (active <= 0 ? n : active) - 1;
      draw(); e.preventDefault();
    } else if (e.key === 'Enter') {                                   // 第 39 輪：選到候選，或輸入的就是某檔完整代號，才送出
      e.preventDefault();
      const q = input.value.trim().toLowerCase(), h = hits[active] || hits.filter(([c]) => c.toLowerCase() === q)[0];
      if (h) go(h[0]);
    }
    else if (e.key === 'Escape') { list.hidden = true; input.blur(); }
  });
  list.addEventListener('click', e => {
    const a = e.target.closest('a'), w = e.target.closest('[data-w]');
    if (w) {   // 第 27 輪 D27-09：☆ 直接加入／移除自選，不進個股頁、清單不關（stopPropagation：重畫後按鈕已不在 .search 裡）
      e.preventDefault(); e.stopPropagation();
      App.watch.has(w.dataset.w) ? App.watch.delete(w.dataset.w) : App.watch.add(w.dataset.w);
      saveWatch(); draw();
      if (location.hash.startsWith('#/watch')) renderWatch();
      const sb = $('#starBtn');   // QA27-01：正在看同一檔的個股頁時，頁首自選鈕跟著同步
      if (sb && location.hash.split('/')[2] === w.dataset.w) { const on = App.watch.has(w.dataset.w); sb.classList.toggle('on', on); sb.textContent = on ? '★ 已加入自選' : '☆ 加入自選'; }
    } else if (a) { e.preventDefault(); go(a.getAttribute('href').split('/')[2]); }
  });
  document.addEventListener('click', e => { if (!e.target.closest('.search')) list.hidden = true; });
}

// ─── 今日 ───────────────────────────────────────────────
const QUADS = [
  ['漲潮', '加速流入'], ['輪動', '流入但放緩'], ['觀望', '流出但放緩'], ['退潮', '加速流出'],
];

function renderToday(t) {
  const L = App.latest, groups = L.groups[App.group];
  // 第 25 輪 D25-08：#/today/分頁。第 27 輪 D27-05：沒指定分頁（#/today）時開總覽，同一次瀏覽中切回才用上次的分頁；網址補成實際顯示的分頁
  const t0 = TODAY_TABS.some(x => x[0] === t) ? t : App.todayTab || 'ov';
  localStore('todayTab', null, App.todayTab = t0);
  if (t !== t0) history.replaceState(null, '', '#/today/' + t0);
  const span = localStore('span', '5');
  const key = span === '1' ? 'net_1d' : 'net_5d';
  const counts = Object.fromEntries(QUADS.map(([q]) => [q, groups.filter(g => g.quadrant === q).length]));
  const sorted = [...groups].sort((a, b) => b[key] - a[key]);
  const inflow = sorted.filter(g => g[key] > 0).slice(0, 8);
  const outflow = sorted.filter(g => g[key] < 0).reverse().slice(0, 8);
  const nFlow = App.flowAll ? 8 : 5, flowMore = inflow.length > 5 || outflow.length > 5;   // 第 13 輪 F13-5：預設各 5 個
  const maxAbs = Math.max(1, ...groups.map(g => Math.abs(g[key])));
  const stocks = Object.entries(L.stocks).filter(([, s]) => s.n1 != null);
  const topBuy = [...stocks].sort((a, b) => b[1].n1 - a[1].n1).slice(0, 10);
  const topSell = [...stocks].sort((a, b) => a[1].n1 - b[1].n1).slice(0, 10);

  // A3：有官方家數時頭條改用官方（含漲停、跌停）；沒有時沿用網站自算
  const mk = (m, label) => { const o = L.breadth?.[m]?.o, x = L.market[m];
    return `<div class="card stat">
      <div class="l">${label}成交額</div>
      <div class="v num">${fmt(x.turnover)}<span class="small muted"> 億</span></div>
      ${o ? `<div class="s num"><span class="nw">漲 <span class="up">${fmt(o.up)}</span>（停 ${fmt(o.ul)}）</span>　<span class="nw">跌 <span class="dn">${fmt(o.dn)}</span>（停 ${fmt(o.dl)}）</span>　<span class="nw">平 <span class="flat">${fmt(o.fl)}</span></span>　<span class="nw">未成交 ${fmt(o.nt)}</span></div>`
      : `<div class="s num">漲 <span class="up">${x.up}</span>　跌 <span class="dn">${x.down}</span>　平 <span class="flat">${x.flat}</span> 家</div>
      <div class="s">一般股票，不含 ETF${L.breadth ? '；官方家數尚未取得，顯示自算' : ''}</div>`}
    </div>`; };
  const bar = (g, color) => `<div class="bar-row" data-group="${esc(g.name)}">
      <span class="nm">${esc(g.name)}</span>
      <span class="bar-track"><span class="bar-fill" style="width:${Math.abs(g[key]) / maxAbs * 100}%;background:${color}"></span></span>
      <span class="val num ${ycls(g[key])}">${yi(g[key])}</span></div>`;
  const rows = list => list.map(([c, s]) => `<tr data-code="${c}">
      <td class="nm"><b>${esc(s.n)}</b>${alertBadge(s)}<span>${c}</span></td>
      <td class="num ${cls(s.p)}${s.lm ? ' lm' : ''}">${pfmt(s.c)}</td>${pctCell(s)}
      <td class="num ${ycls(s.n1)}">${yi(s.n1)}</td></tr>`).join('');

  // 分頁：指數卡永遠顯示，其餘依分頁只輸出該頁的區塊（圖表不會畫在隱藏的容器裡）
  const tab = pageTab('todayTab', TODAY_TABS);
  const fut = `${futuresHTML(L.futures)}${oiHTML(L.futures_oi, L.forecast)}`;
  const body = {
    ov: `${tab === 'ov' ? watchToday(L, rows) : ''}${sumStrip(L)}<section class="sec grid g-stats g-mk">
      <div class="mk-pair"><div class="mk-cards">${mk('TWSE', '上市')}${mk('TPEx', '上櫃')}</div>
      ${L.breadth?.TWSE?.o || L.breadth?.TPEx?.o ? '<div class="muted small">家數為官方（股票）；成交額為網站自算，不含 ETF</div>' : ''}</div>
      ${breadthCard(L)}
    </section>

    <section class="sec">
      <div class="sec-h"><h2>資金象限</h2><span class="sp"></span>${groupSeg()}</div>
      <div class="quads">
        ${QUADS.map(([q, d]) => `<a class="quad q-${q}" href="#/bubble" data-q="${q}"><div class="t">${q}</div><div class="n num">${counts[q]}</div><div class="d">${d}</div></a>`).join('')}
      </div>
    </section>
    ${alertBoard(L)}`,
    credit: `<section class="sec grid ${marginCard(L) && valCard(L) ? 'g2' : 'g-one'}">${marginCard(L)}${valCard(L)}</section>`,   // 信用交易、估值左右並排
    fut: fut.trim() || '<div class="empty">沒有期貨資料</div>',
  };
  body.flow = `<section class="sec grid ${L.insti_official ? 'g2' : 'g-one'}">${instiCard(L)}</section>
    <section class="sec grid g2">
      <div class="card">
        <div class="sec-h"><h2>錢流去哪</h2><span class="muted small">${span === '1' ? '今天' : '近 5 日'}，估算，不含 ETF</span><span class="sp"></span>${segHTML('spanSeg', [['1', '今天'], ['5', '近 5 日']], span)}</div>
        <div class="bars">${inflow.slice(0, nFlow).map(g => bar(g, 'var(--up)')).join('') || '<div class="empty">沒有淨流入的板塊</div>'}</div>
      </div>
      <div class="card">
        <div class="sec-h"><h2>錢從哪裡流出</h2><span class="sp"></span>${flowMore ? `<button class="chip" id="flowMore">${App.flowAll ? '只顯示前 5' : '顯示全部'}</button>` : ''}</div>
        <div class="bars">${outflow.slice(0, nFlow).map(g => bar(g, 'var(--dn)')).join('') || '<div class="empty">沒有淨流出的板塊</div>'}</div>
      </div>
    </section>

    ${sxCard(L)}
    ${flowNote()}<section class="sec grid g2">
      <div class="card"><div class="sec-h"><h2>法人買超</h2><span class="muted small">${md(L.flow_date)}，億，估算，不含 ETF</span></div>
        <div class="tbl-wrap"><table class="tbl"><thead><tr><th>股票</th><th>收盤</th><th>漲跌</th><th>買賣超</th></tr></thead><tbody>${rows(topBuy)}</tbody></table></div></div>
      <div class="card"><div class="sec-h"><h2>法人賣超</h2><span class="muted small">${md(L.flow_date)}，億，估算，不含 ETF</span></div>
        <div class="tbl-wrap"><table class="tbl"><thead><tr><th>股票</th><th>收盤</th><th>漲跌</th><th>買賣超</th></tr></thead><tbody>${rows(topSell)}</tbody></table></div></div>
    </section>
    ${activeCard(L.active_rank)}`;

  $('#view').innerHTML = `
    <section class="sec grid g-stats">${indexCard(L.index?.TAIEX, '加權指數', tab === 'ov')}${indexCard(L.index?.TPEX, '櫃買指數', tab === 'ov')}</section>
    ${pageTabsHTML('todayTabSeg', TODAY_TABS, tab)}
    ${body[tab]}`;

  $('#view .quads')?.addEventListener('click', e => { App.blQ = e.target.closest('[data-q]')?.dataset.q; });   // 第 30 輪 D30-06
  $('#view .w-hold')?.addEventListener('click', () => { App.watchCols = 'hold'; });   // 第 42 輪 F42-2：點持股一行直接看持股表
  onSeg('todayTabSeg', v => { localStore('todayTab', null, App.todayTab = v); history.replaceState(null, '', '#/today/' + v); disposeFuturesChart(); renderToday(); });
  if ($('#grpSeg')) onSeg('grpSeg', v => { setGroup(v); renderToday(); });
  if ($('#spanSeg')) onSeg('spanSeg', v => { localStore('span', null, v); renderToday(); });
  $('#flowMore')?.addEventListener('click', () => { App.flowAll = !App.flowAll; renderToday(); });
  $('#sxMore')?.addEventListener('click', () => { App.sxAll = !App.sxAll; renderToday(); });   // 第 51 輪 F51-3：類股指數表（狀態只存在 App，不寫 localStorage）
  $('#view').querySelectorAll('.sx th.sort').forEach(el => el.addEventListener('click', () => { const k = el.dataset.k, o = App.sxSort || { k: 'p', d: -1 };
    App.sxSort = { k, d: o.k === k ? -o.d : -1 }; renderToday(); }));
  $('#alMore')?.addEventListener('click', () => { App.alertAll = !App.alertAll; renderToday(); });
  $('#view details.al-box')?.addEventListener('toggle', e => { App.alOpen = e.target.open; });
  $('#view').addEventListener('click', onRowClick);
  if (tab === 'fut') { drawFutures(L.futures); drawOI(L.futures_oi); }
}

// 第 25 輪 D25-03：總覽最上方的大盤摘要。數字和口徑沿用各分頁的卡片（官方法人、期貨法人大台淨額、價差、股票融資），點了切到該分頁
function sumStrip(L) {
  const O = L.insti_official, P = L.insti_official_tpex, F = L.futures, k = (F?.d?.length ?? 0) - 1, sp = F?.sp?.[k];
  const X = L.futures_oi?.inv?.find(r => r.k === 'foreign'), M = L.margin || {}, dd = x => x && x !== L.date ? `（${md(x)}）` : '';
  const it = (tab, l, n, v, sub) => `<a class="sum-i" href="#/today/${tab}"><span class="l">${l}</span><b class="${cls(n)}">${v}</b><span class="s">${sub}</span></a>`;
  const ins = (x, m) => x && it('flow', `三大法人 ${m}${dd(x.date)}`, x.total, sgn(x.total, 1) + '億', `外資 ${sgn(x.foreign, 1)}億・官方，含 ETF`);
  const mg = (x, m) => x && it('credit', `融資 ${m}${dd(x.d)}`, x.m1, sgn(x.m1, 0) + ' 張', `${sgn(x.mp)}%・股票，不含 ETF`);
  const html = [ins(O, '上市'), ins(P, '上櫃'), X && it('fut', `外資台指期淨額${dd(L.futures_oi.date)}`, X.net, sgn(X.net, 0) + ' 口', `增減 ${sgn(X.chg, 0)}・大台`),
    sp != null && it('fut', `期現貨價差${dd(F.d[k])}`, sp, sgn(sp) + ' 點', sp > 0 ? '正價差' : sp < 0 ? '逆價差' : '平價'), mg(M.TWSE, '上市'), mg(M.TPEx, '上櫃')].filter(Boolean).join('');
  return html ? `<section class="sec sum">${html}</section>` : '';
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

// 第 51 輪 F51-3：證交所上市類股指數表（latest.json sx；沒有 sx 時回傳空字串）。排序 App.sxSort = {k: p／r5／r20, d: -1 由高到低、1 由低到高}，
// null 不論方向排最後，同值依官方列順序；先顯示 10 列（App.sxAll = 全部）
function sxCard(L) {
  const S = L.sx;
  if (!S) return '';
  const o = App.sxSort || { k: 'p', d: -1 }, K = { p: 3, r5: 4, r20: 5 }[o.k], pv = v => v == null ? '--' : sgn(v) + '%';
  const list = S.r.map((r, i) => [r, i]).sort((a, b) => { const x = a[0][K], y = b[0][K];
    return (x == null || y == null ? (x == null) - (y == null) : (x - y) * o.d) || a[1] - b[1]; }).slice(0, App.sxAll ? S.r.length : 10);
  const th = (k, t) => `<th class="sort" data-k="${k}">${t}${o.k === k ? (o.d < 0 ? ' ▼' : ' ▲') : ''}</th>`;
  const short = '證交所編製的上市類股價格指數，不含股息；和泡泡圖、錢流的本站自算類股不同';      // 短句用變數：test_iter13 數 noteHTML 字面呼叫
  const full = `證交所每天公布的上市類股價格指數：依成分股市值加權，只含上市股票，不含股息；收盤與漲跌點數為官方數字，漲跌 % = 漲跌點數 ÷ 前一日收盤。5 日、20 日 = 從往前第 5、20 個交易日${S.b5 && S.b20 ? `（${md(S.b5)}、${md(S.b20)}）` : ''}的收盤起算，和選股的 5 日、20 日報酬同一個起點；本站沒有那天的指數時寫「--」。「電子工業」「化學生技醫療」兩個合併類別、水泥窯製等綜合類別與大盤、主題指數不列入。泡泡圖、錢流的類股是本站依成分股自算，含上櫃股票，和這裡的數字不會相同。點「漲跌」「5 日」「20 日」可以換排序，再點一次反過來排。`;
  return `<section class="sec card sx"><div class="sec-h"><h2>類股指數</h2><span class="muted small">證交所，上市，${md(S.d)}${S.d < L.date ? '（尚未更新）' : ''}</span><span class="sp"></span>${S.r.length > 10 ? `<button class="chip" id="sxMore">${App.sxAll ? '只顯示前 10' : '顯示全部'}</button>` : ''}</div>
    <div class="tbl-wrap"><table class="tbl"><thead><tr><th>類股</th><th>收盤</th>${th('p', '漲跌')}${th('r5', '5 日')}${th('r20', '20 日')}</tr></thead><tbody>${list.map(([r]) =>
      `<tr><td class="nm"><b>${r[0]}</b></td><td class="num ${cls(r[2])}">${fmt(r[1], 2)}</td><td class="num ${cls(r[3])}">${pv(r[3])}<span class="sub2">${sgn(r[2])}</span></td><td class="num ${cls(r[4])}">${pv(r[4])}</td><td class="num ${cls(r[5])}">${pv(r[5])}</td></tr>`).join('')}</tbody></table></div>
    <div class="muted small" style="margin-top:6px">${noteHTML(short, full)}</div></section>`;
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

function indexCard(x, name, full = true) {   // full = false：省略迷你圖下方的區間漲跌（第 13 輪 F13-4，非總覽分頁）
  if (!x) return `<div class="card stat idx ix"><div class="l">${name}</div><div class="v num">--</div><div class="s">暫無資料</div></div>`;
  const stale = x.date < App.latest.date;
  return `<div class="card stat idx ix">
      <div class="l">${name}<span class="muted">　${md(x.date)}${stale ? '（尚未更新）' : ''}</span></div>
      <div class="v num ${cls(x.ch)}">${fmt(x.c, 2)}</div>
      <div class="s num ${cls(x.ch)}">${x.ch > 0 ? '▲' : x.ch < 0 ? '▼' : ''} ${fmt(Math.abs(x.ch ?? 0), 2)} (${sgn(x.p)}%)</div>
      ${spark(x.s)}
      ${full && x.s.length >= 2 ? `<div class="s"><span class="${x.s.at(-1) >= x.s[0] ? 'up' : 'dn'}">自 ${md(x.from)} 起 ${sgn((x.s.at(-1) / x.s[0] - 1) * 100, 1)}%</span>${x.s.length < 60 ? `（${x.s.length} 個交易日）` : ''}</div>` : ''}
    </div>`;
}

// 第 13 輪 F13-3：說明收合。short = 可見的一行（防誤讀的句子放這裡）；full = 原本的完整說明（逐字保留，預設收合）
const noteHTML = (short, full) => `<details class="note"><summary>${short}<i>說明</i></summary><div>${full}</div></details>`;

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

// 第 30 輪 D30-03：今日頁信用、寬度、估值卡的上市／上櫃數字改成「指標 × 市場」小表（數字與口徑不變，只改排版）
const mxTbl = (cols, rows) => `<table class="mx num"><thead><tr><th></th>${cols.map(c => `<th>${c}</th>`).join('')}</tr></thead><tbody>` +
  rows.filter(Boolean).map(([l, ...v]) => `<tr><th>${l}</th>${v.map(x => `<td>${x}</td>`).join('')}</tr>`).join('') + '</tbody></table>';
const s2 = t => `<div class="s2">${t}</div>`;
// 信用交易卡（B2＋A4）：頭條為股票口徑（不含 ETF）；官方含 ETF 只列融資金額；ETF 另計一行；官方融資、融券張數不顯示
function marginCard(L) {
  const M = L.margin;
  if (!M) return '';
  const T = M.TWSE, O = M.TPEx, d = [T?.d, O?.d].filter(Boolean).sort().at(-1);
  const wan = n => `<b title="${fmt(n)} 張">${fmt(n / 1e4, 1)}</b> 萬張`;
  const lots = n => `<span class="${cls(n)}">${sgn(n, 0)}</span>`;
  const c = f => [T, O].map(x => !x ? '--' : f(x));
  const col = (x, name) => name + (x && x.d < d ? `<span class="muted">（${md(x.d)}）</span>` : '');
  const mr = x => x.mr == null ? '資料不足' : `<b>${fmt(x.mr, 1)}%</b>${s2(`前日 ${x.mr0 == null ? '--' : fmt(x.mr0, 1) + '%'}`)}`;
  const amt = x => `${fmt(x.amt, 1)} 億${s2(`<span class="${cls(x.amt1)}">${x.amt1 > 0 ? '▲' : x.amt1 < 0 ? '▼' : ''}${fmt(Math.abs(x.amt1), 1)} 億</span>`)}`;
  const E = T?.etf;
  // P22：依上市股票口徑 1 日變動較大的一邊，連到融資融券排行
  const X = T || O, rk = !X ? '' : Math.abs(X.sp ?? 0) >= Math.abs(X.mp ?? 0) ? (X.sp < 0 ? 's-' : 's+') : (X.mp < 0 ? 'm-' : 'm+');
  return `<div class="card stat idx margin">
      <div class="l">信用交易 ${md(d)}（股票，不含 ETF）${d < L.date ? '<span class="muted">（尚未更新）</span>' : ''}${rk ? `　<a class="muted small" href="#/rank/${rk}">看排行 →</a>` : ''}</div>
      ${mxTbl([col(T, '上市'), col(O, '上櫃')], [
        ['融資', ...c(x => `${wan(x.mb)}${s2(`${lots(x.m1)}（${sgn(x.mp)}%）`)}`)],
        ['融券', ...c(x => `${wan(x.sb)}${s2(lots(x.s1))}`)],
        ['券資比', ...c(x => `${fmt(x.sr, 2)}%`)],
        ['融資維持率' + s2('自算'), ...c(mr)],
        ['融資金額' + s2('官方，含 ETF'), ...c(amt)],
        sblLine(L)])}
      ${L.sbl ? '<div class="s">借券賣出含避險、套利，不等於看空；晚上 8 點半以後才更新</div>' : ''}
      ${E ? `<div class="s num">ETF 另計（不計入上方）：上市 ETF 融資 ${wan(E.mb)} ${lots(E.m1)}、融券 ${wan(E.sb)} ${lots(E.s1)}</div>` : ''}
      ${etfSblLine(L.sbl_etf)}
      ${T ? `${minibars(T.m20)}<div class="s">上市股票融資增減（張），近 ${T.m20.length} 日（${md(T.d20[0])}～${md(T.d20.at(-1))}）</div>` : ''}
      ${noteHTML('維持率為本站自算、非官方；140% 是經驗值，不是官方門檻', `<div>維持率 = Σ(融資張數 × 1,000 × 收盤) ÷ 官方融資金額，股票＋ETF，自算、非官方；涵蓋率不足 99% 時顯示「資料不足」</div>
      <div>參考（經驗值，非官方門檻）：大盤融資維持率跌到 140% 左右時，常伴隨融資斷頭賣壓。投資人整戶擔保維持率低於 130% 會被追繳，這是官方規定。</div>`)}
    </div>`;
}

// 第 11 輪 B14：借券賣出餘額（股票口徑，張）與融券的倍數；倍數用同一市場信用交易卡的融券合計
function sblLine(L) {   // 第 30 輪 D30-03：回傳信用交易小表的一列
  const B = L.sbl, M = L.margin;
  if (!B) return null;
  const wan = n => `<b title="${fmt(n)} 張">${fmt(n / 1e4, n >= 1e6 ? 0 : 1)}</b> 萬張`;
  const one = (x, m) => !x ? '--' : `${wan(x.lb)}` + s2(`<span class="${cls(x.l1)}">${sgn(x.l1, 0)}</span>` +
    (M?.[m]?.sb ? `<br>融券的 ${fmt(x.lb / M[m].sb, 0)} 倍` : '') + (x.d !== (M?.[m]?.d ?? x.d) ? `<span class="muted">（${md(x.d)}）</span>` : ''));
  return ['借券賣出餘額' + s2('<a class="muted" href="#/rank/l+">看排行 →</a>'), one(B.TWSE, 'TWSE'), one(B.TPEx, 'TPEx')];
}

// 第 12 輪 ETF-借券：ETF 借券賣出合計（上市、上櫃 ETF，張）；多為造市、套利與避險
function etfSblLine(B) {
  if (!B) return '';
  const wan = n => `<b title="${fmt(n)} 張">${fmt(n / 1e4, n >= 1e6 ? 0 : 1)}</b> 萬張`;
  const one = (x, name) => !x ? '' : `${name} ${wan(x.lb)} <span class="${cls(x.l1)}">${sgn(x.l1, 0)}</span>`;
  return `<div class="s num">ETF 借券賣出　${[one(B.TWSE, '上市'), one(B.TPEx, '上櫃')].filter(Boolean).join('　')}　<a class="muted small" href="#/etf">ETF 頁 →</a></div>
      <div class="note-dup">${noteHTML('ETF 借券賣出多為造市、套利與避險，不等於看空', 'ETF 借券賣出多為造市、套利與避險（例如價格高於淨值時借券賣出，申購後還券），不等於看空')}</div>`;
}

// 第 16 輪 F16-3：處置／注意清單（即將處置、處置中、今日注意）；注意預設 10 檔
function alertBoard(L) {
  const A = L.alerts;
  if (!A) return '';
  // 每檔兩行：名稱、代號、市場、處置期間；措施與原因一行（超出截斷，完整內容在提示與個股頁）
  const S = L.stocks, row = (c, span, r) => `<a class="al-row" href="#/stock/${c}" title="${esc(r)}">
      <div class="al-l"><b>${esc(S[c]?.n || c)}</b><span class="muted small">${c}・${S[c]?.m === 'TWSE' ? '上市' : '上櫃'}</span><span class="sp"></span>${span ? `<span class="small num">${span}</span>` : ''}</div>
      <div class="muted small al-why">${esc(r)}</div></a>`;   // 不用 .al-r（期貨「今天換月」已用）
  const dsp = x => row(x[0], `${md(x[1])}～${md(x[2])}`, [x[3], x[4]].filter(Boolean).join('｜'));
  const up = A.d.filter(x => x[1] > L.date), on = A.d.filter(x => x[1] <= L.date);
  const nShow = App.alertAll ? A.n.length : 10;
  const grp = (t, list, n = list.length) => `<div class="al-grp"><h3>${t}　<span class="muted small">${n} 檔</span></h3>${list.join('') || '<div class="muted small">無</div>'}</div>`;
  return `<section class="sec card"><details class="al-box"${App.alOpen ? ' open' : ''}>
      <summary class="sec-h"><h2>處置／注意股</h2><span class="muted small">${md(L.date)}　即將處置 ${up.length}　處置中 ${on.length}　接近處置（推算）${(A.w || []).length}　今日注意 ${A.n.length}</span><span class="sp"></span><i></i></summary>
      ${A.n.length > 10 ? `<button class="chip" id="alMore">${App.alertAll ? '注意只顯示 10 檔' : '注意顯示全部'}</button>` : ''}
      ${grp('即將處置', up.map(dsp))}${grp('處置中', on.map(dsp))}${watchGrp(A.w, S)}${grp('今日注意', A.n.slice(0, nShow).map(x => row(x[0], '', x[1])), A.n.length)}
      <div class="muted small">依證交所、櫃買中心公告；處置期間撮合間隔較長，買賣可能需預收款券。點股票看完整原因</div>
    </details></section>`;
}

// 第 17 輪 F17-2：接近處置（依注意款別推算）；已達條件逐檔一行，差一次只列名稱（提示是條件）
function watchGrp(W, S) {
  if (!W) return '';
  const hit = W.filter(x => x[1]), near = W.filter(x => !x[1]);
  const nm = c => esc(S[c]?.n || c), why = t => esc(t.replace('第一款', '第 1 款'));   // 第 30 輪 D30-07：款別寫法統一
  const mk = c => S[c]?.m === 'TWSE' ? '上市' : '上櫃';
  return `<div class="al-grp"><h3>接近處置（推算）　<span class="muted small">已達條件 ${hit.length} 檔、差一次 ${near.length} 檔</span></h3>
      ${hit.map(x => `<a class="al-row" href="#/stock/${x[0]}"><div class="al-l"><b>${nm(x[0])}</b><span class="muted small">${x[0]}・${mk(x[0])}</span><span class="sp"></span><span class="small">已達條件</span></div>
        <div class="muted small al-why">${why(x[2])}</div></a>`).join('')}
      ${near.length ? `<div class="al-near small muted">差一次：</div>${near.map(x => `<a class="al-row" href="#/stock/${x[0]}"><div class="al-l"><b>${nm(x[0])}</b><span class="muted small">${x[0]}・${mk(x[0])}</span><span class="sp"></span><span class="small">差 1 次</span></div>
        <div class="muted small al-why">目前 ${why(x[2])}</div></a>`).join('')}` : ''}
      ${W.length ? '' : '<div class="muted small">無</div>'}
      <div class="muted small">依注意款別推算（第 1 款連 3 日，或第 1～8 款連 5 日、10 日內 6 次、30 日內 12 次）；是否處置以官方公告為準</div></div>`;
}

// 市場寬度卡（A3＋A8）：全部為網站自算（還原收盤、股票、不含 ETF）；官方家數在成交額卡
function breadthCard(L) {
  const B = L.breadth;
  if (!B) return '';
  const pct = v => v == null ? '--' : fmt(v, 1) + '%';
  const T = B.TWSE, s = T?.s20.filter(v => v != null) || [];
  const c = f => [T, B.TPEx].map(x => !x ? '--' : f(x));
  return `<div class="card stat idx margin">
      <div class="l">市場寬度 ${md(T?.d || B.TPEx?.d)}（自算，股票，不含 ETF）</div>
      ${mxTbl(['上市', '上櫃'], [['站上 MA20', ...c(x => `<b>${pct(x.ma20)}</b>${s2(`前日 ${pct(x.s20.at(-2))}`)}`)], ['站上 MA60', ...c(x => `<b>${pct(x.ma60)}</b>`)],
        ['20 日新高', ...c(x => `<span class="up">${fmt(x.hi)}</span>`)], ['20 日新低', ...c(x => `<span class="dn">${fmt(x.lo)}</span>`)],
        ['量能', ...c(x => `<b>${x.vr == null ? '--' : fmt(x.vr, 2) + ' 倍'}</b>`)]])}
      ${spark(s)}${s.length ? `<div class="s">上市站上 MA20 比例，近 ${s.length} 個交易日（${md(T.from)} 起）</div>` : ''}
      <div class="s">分母 = 當天有收盤、且有 20（MA60 為 60）個以上收盤的股票（上市 ${fmt(T?.n20)}、上櫃 ${fmt(B.TPEx?.n20)} 檔）；新高／新低 = 收盤高於／低於前 20 個收盤；量能 = 成交額 ÷ 前 20 日平均</div>
    </div>`;
}

// 估值位置卡（第 9 輪 F9-4，A10）：上市、上櫃股票的官方本益比、淨值比、殖利率中位數在近一年的位置
function valCard(L) {
  const V = L.valuation;
  if (!V || !(V.TWSE || V.TPEx)) return '';
  const pos = x => !x ? '--' : x.v <= x.lo ? '一年最低' : x.v >= x.hi ? '一年最高' : `一年位置 ${fmt(x.p, 1)}%`;
  const T = V.TWSE || V.TPEx;
  const c = f => [V.TWSE, V.TPEx].map(x => !x ? '--' : f(x));
  return `<div class="card stat idx val">
      <div class="l">估值位置（官方，股票中位數）<span class="muted">　${md(T.d)}</span></div>
      ${mxTbl(['上市', '上櫃'], [['本益比', ...c(x => `<b>${fmt(x.pe?.v, 2)}</b>${s2(pos(x.pe))}`)], ['淨值比', ...c(x => `<b>${fmt(x.pb?.v, 2)}</b>${s2(pos(x.pb))}`)],
        ['殖利率' + s2('一年位置，越高 = 殖利率相對越高'), ...c(x => `<b>${x.dy ? fmt(x.dy.v, 2) + '%' : '--'}</b>${s2(pos(x.dy))}`)],   // 第 14 輪 F14-4：方向和本益比、淨值比相反
        wpeRow(V)])}
      ${wpeLine(V)}
      ${spark(V.TWSE?.s)}${V.TWSE?.s?.length > 1 ? `<div class="s">上市本益比中位數，近 ${V.TWSE.s.length} 個交易日（${md(V.TWSE.sf)} 起）</div>` : ''}
      ${finLine(L.fin_progress)}
      <div class="note-dup">${noteHTML('股票中位數，不是加權指數本益比；只是位置，不是買賣訊號', `一年位置 = 近 ${T.days} 個交易日（${T.from.replaceAll('-', '/')} 起）中，中位數小於或等於今天的天數比例。中位數只計本益比、淨值比大於 0 的股票（上市 ${fmt(V.TWSE?.n)}、上櫃 ${fmt(V.TPEx?.n)} 檔），不是加權指數本益比；本益比用近 4 季 EPS，財報公布期間 EPS 變化也會改變位置；殖利率用去年股利。只是位置，不是買賣訊號`)}</div>
    </div>`;
}

// 第 12 輪 A10-延伸：市值加權本益比（本站以目前股數計算）；和上面的中位數並列
function wpeLine(V) {
  const T = V.TWSE?.wpe, O = V.TPEx?.wpe;
  if (!T && !O) return '';
  const big = T?.t ? `最大的 ${esc(App.latest.stocks?.[T.t[0]]?.n || T.t[0])} 占上市 ${fmt(T.t[1], 1)}%` : '';
  return `<div class="note-dup">${noteHTML(`大型股影響大${big ? `（${big}）` : ''}；本站計算，不是證交所公布的數字`, `加權本益比 = 市值合計 ÷ Σ（市值 ÷ 本益比），大型股影響大${big ? `（${big}）` : ''}；中位數反映一般股票。本站以目前股數計算、不含虧損公司，不是證交所公布的數字`)}</div>`;
}
function wpeRow(V) {   // 第 30 輪 D30-03：加權本益比改成估值小表的一列
  const T = V.TWSE?.wpe, O = V.TPEx?.wpe;
  if (!T && !O) return null;
  const pos = x => x.v <= x.lo ? '一年最低' : x.v >= x.hi ? '一年最高' : `一年位置 ${fmt(x.p, 1)}%`;
  const one = x => !x ? '--' : `<b>${fmt(x.v, 2)}</b>${s2(pos(x))}`;
  return ['加權本益比' + s2('市值加權'), one(T), one(O)];
}

// 第 10 輪 B5：季報公布進度（資料日在季報收集期間、當季已有資料時才有 fin_progress）
function finLine(P) {
  if (!P) return '';
  const q = P.q % 100, name = q === 4 ? `${Math.floor(P.q / 100)} 年報` : `第 ${q} 季財報`;
  return `<div class="s">${name}已收：上市 ${fmt(P.n.TWSE)}、上櫃 ${fmt(P.n.TPEx)} 家（前一季 ${fmt(P.p.TWSE)}、${fmt(P.p.TPEx)} 家${P.due ? '；' + dueTxt(P.due, App.latest.date) + dueWk(P.due, App.latest.date) : ''}）；本益比中位數會隨 EPS 更新而變動</div>`;
}
// 第 14 輪 F14-4：申報截止日 [一般業, 金融業]；相同（年報）只寫一次；資料日已過的寫「已截止」
// 第 15 輪 F15-4：「已截止」改用 dueRoll（週六、週日順延到下週一；平日的國定假日不處理）判斷；星期與可能順延的日期由 dueWk 接在後面
const dueTxt = ([g, f], d) => { const [G, F] = [g, f].map(dueRoll); return g === f ? `${md(g)} ${d > G ? '已截止' : '截止'}`
  : d > F ? `一般業 ${md(g)}、金融業 ${md(f)} 已截止` : d > G ? `一般業 ${md(g)} 已截止、金融業 ${md(f)} 截止` : `一般業 ${md(g)}、金融業 ${md(f)} 截止`; };
const dueRoll = s => { const t = new Date(s + 'T00:00:00Z'), w = t.getUTCDay(); t.setUTCDate(t.getUTCDate() + (w === 6 ? 2 : w === 0 ? 1 : 0)); return t.toISOString().slice(0, 10); };
const dueWk = ([g, f], d) => { const u = g === f ? [g] : [g, f], r = u.filter(x => dueRoll(x) !== x && d <= dueRoll(x));
  const lab = r.length && r.length < u.length ? (r[0] === g ? '一般業' : '金融業') : '';
  return `，${u.length > 1 ? '分別是' : '當天是'}${u.map(x => '週' + '日一二三四五六'[new Date(x + 'T00:00:00Z').getUTCDay()]).join('、')}` +
    (r.length ? `，${lab}遇假日可能順延到 ${r.map(x => md(dueRoll(x))).join('、')}` : ''); };

// 三大法人卡：上市（A2）、上櫃（第 9 輪 F9-1）都用官方金額；上櫃官方還沒有任何資料時退回估算一行；上市也沒有時維持第 1 輪估算卡
function instiCard(L) {
  const O = L.insti_official, P = L.insti_official_tpex, X = L.insti_otc, I = L.insti;
  const yi1 = v => v == null ? '--' : sgn(v, 1) + '億';
  const parts = x => `外資 <span class="${cls(x.foreign)}">${yi1(x.foreign)}</span>　投信 <span class="${cls(x.trust)}">${yi1(x.trust)}</span>　自營 <span class="${cls(x.dealer)}">${yi1(x.dealer)}</span>`;
  const stk = s => s > 0 ? `連買 ${s} 日` : s < 0 ? `連賣 ${-s} 日` : '當日持平';
  if (!O) return `<div class="card stat insti"><div class="l">三大法人（${md(L.flow_date)}）</div>
      <div class="v num ${ycls(I.foreign + I.trust + I.dealer)}">${yi(I.foreign + I.trust + I.dealer)}</div>
      <div class="s num">外資 <span class="${ycls(I.foreign)}">${yi(I.foreign)}</span>　投信 <span class="${ycls(I.trust)}">${yi(I.trust)}</span>　自營 <span class="${ycls(I.dealer)}">${yi(I.dealer)}</span></div>
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
      <div class="s num">外資 <span class="${ycls(X.foreign)}">${yi(X.foreign)}</span>　投信 <span class="${ycls(X.trust)}">${yi(X.trust)}</span>　自營 <span class="${ycls(X.dealer)}">${yi(X.dealer)}</span></div>
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
    const to = from ? new Date(Date.parse(from + 'T00:00:00Z') + 864e5).toISOString().slice(0, 10) : N.date;   // 第 47 輪 F47-4（R61）：開始日的隔一個日曆日，週五夜盤到週六 05:00
    const np = N.ch != null && N.c !== N.ch ? N.ch / (N.c - N.ch) * 100 : null;
    night = `<span class="${old ? 'night-old' : ''}">${old ? '前一夜盤' : '最新夜盤'}（${from ? md(from) + ' 15:00～' : ''}${md(to)} 05:00）　收 <b class="num ${cls(N.ch)}">${fmt(N.c)}</b>
      <span class="num ${cls(N.ch)}">${sgn(N.ch, 0)} (${sgn(np)}%)</span></span>`;
  }
  const roll = k > 0 && F.m[k] !== F.m[k - 1];                 // 第 14 輪 F14-3：近月和前一個交易日不同 = 今天換月
  return `<section class="sec card">
      <div class="sec-h"><h2>${esc(F.name)}</h2><span class="muted small">日盤・契約 ${F.m[k]}${roll ? '<i class="al al-r">今天換月</i>' : ''}</span>
        <span class="sp"></span><span class="muted small hint">拖曳平移、滾輪縮放</span></div>
      <div class="fut-head">
        <span class="s-price num ${cls(ch)}" style="font-size:26px">${fmt(c)}</span>
        <span class="s-chg num ${cls(ch)}">${ch > 0 ? '▲' : ch < 0 ? '▼' : ''} ${fmt(Math.abs(ch ?? 0))} (${sgn(pct)}%)</span>
        <span class="muted small">${F.d[k]}</span>
      </div>
      <div class="fut-sub muted small">${old ? night : ''}<span>成交量 <b class="num">${fmt(F.v[k])}</b> 口</span>
        <span>未平倉 <b class="num">${fmt(F.oi[k])}</b> 口</span>${old ? '' : night}</div>
      ${spreadHTML(F, k, roll)}
      <div class="kleg" id="fLegend"></div>
      <div id="fC" class="chart-box" style="height:300px"></div>
    </section>`;
}

// 第 14 輪 F14-3：期現貨價差（近月日盤收盤 − 同一天加權指數收盤）、下次結算日（本站推算）、近 60 日價差迷你圖
function spreadHTML(F, k, roll) {
  const sp = F.sp?.[k], S = F.stl;
  if (!F.sp && !S) return '';
  const tag = [S?.n === 0 ? '結算日' : '', roll ? '換月' : ''].filter(Boolean).join('、');
  const v = sp == null ? '<span class="nw">價差 --（加權指數沒有同一天的收盤）</span>'
    : `<span class="nw">價差 <b class="num ${cls(sp)}">${sgn(sp)}</b> 點</span><span class="nw">（${sp > 0 ? '正價差' : sp < 0 ? '逆價差' : '平價'}，${fmt(Math.abs(sp / (F.c[k] - sp) * 100), 2)}%${tag ? '，' + tag : ''}）</span>`;
  const wd = S ? '日一二三四五六'[new Date(S.d + 'T00:00:00').getDay()] : '';
  const st = !S ? '' : S.n === 0 ? `<span class="nw">今天結算（${md(S.d)}，週${wd}）</span>`
    : `<span class="nw">${md(S.d)}（週${wd}）結算</span><span class="nw">，還有 ${S.n} 個交易日${wd !== '三' ? '（遇休市順延）' : ''}</span>`;
  const n = Math.min(60, F.d.length), s60 = (F.sp || []).slice(-n), short = '期貨 13:45、加權指數 13:30 收盤，時間不同；結算日是本站推算，以期交所公告為準';
  return `<div class="fut-sp small"><div>${v}　${st}</div>
      ${spreadSpark(s60, F.m.slice(-n))}${s60.filter(x => x != null).length > 1 ? `<div class="muted">價差近 ${n} 個交易日（${md(F.d.at(-n))}～${md(F.d[k])}），虛線 = 換月</div>` : ''}
      ${noteHTML(short, '價差 = 台指期近月日盤收盤 − 同一天加權指數收盤（夜盤不比），正值為正價差、負值為逆價差，百分比 = 價差 ÷ 加權指數。期貨日盤 13:45 收盤、加權指數 13:30 收盤，尾盤變化大時價差會失真。近月 = 當天有成交的最近到期月份：結算日當天仍是到期月份，下一個交易日換到下個月份，換月當天的價差跳動來自契約不同，不是行情。結算日依「每月第三個週三，遇休市順延到下一個交易日」推算，臨時休市或期交所另行公告時以官方為準。')}</div>`;
}
// 價差迷你圖：含 0 軸；換月的日子畫虛線；沒有價差的日子不畫點
function spreadSpark(v, m) {
  const ok = v.filter(x => x != null);
  if (ok.length < 2) return '';
  const lo = Math.min(0, ...ok), hi = Math.max(0, ...ok), n = v.length;
  const X = i => (i / (n - 1) * 100).toFixed(2), Y = x => (2 + (hi - x) / (hi - lo || 1) * 30).toFixed(2);
  const ln = (x1, x2, y1, y2, st) => `<line x1="${x1}" x2="${x2}" y1="${y1}" y2="${y2}" ${st} vector-effect="non-scaling-stroke"/>`;
  return `<svg class="spark" viewBox="0 0 100 34" preserveAspectRatio="none" aria-hidden="true">${ln(0, 100, Y(0), Y(0), 'stroke="var(--text2)"')}` +   // 第 15 輪 F15-3：0 軸用 --text2（對比 ≥ 3:1）
    m.map((c, i) => i && c !== m[i - 1] ? ln(X(i), X(i), 0, 34, 'stroke="var(--text3)" stroke-dasharray="2 2"') : '').join('') +
    `<polyline points="${v.map((x, i) => x == null ? '' : `${X(i)},${Y(x)}`).filter(Boolean).join(' ')}" fill="none" stroke="var(--blue)" stroke-width="1.5" vector-effect="non-scaling-stroke"/></svg>`;
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
  kSer.setMarkers(T.flatMap((t, i) => i && F.m[i] !== F.m[i - 1] ? [{ time: t, position: 'aboveBar', color: css('--text2'), shape: 'arrowDown', text: `換${Number(F.m[i].slice(4))}月` }] : []));   // 第 14 輪 F14-3
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
    const ma = (label, v, color) => v == null ? '' : `<span class="lg"><i style="background:${color}"></i>${label} <b>${fmt(v)}</b></span>`;   // D27-06：線色只放在色塊，數字用正文色
    legend.innerHTML = `<span><b>${T[i]}</b></span><span>開 <b>${fmt(F.o[i])}</b></span><span>高 <b class="up">${fmt(F.h[i])}</b></span>` +
      `<span>低 <b class="dn">${fmt(F.l[i])}</b></span><span>收 <b class="${c}">${fmt(F.c[i])}</b></span>` +
      `<span class="${c}">${sgn(ch, 0)} (${sgn(p)}%)</span><span>量 <b>${fmt(F.v[i])}</b></span>` +
      `<span>契約 ${F.m[i]}${F.sp?.[i] != null ? `　價差 <b>${sgn(F.sp[i])}</b>` : ''}</span>` +
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
    // 第 31 輪 D31-01：模型沒勝過基準時，長條改畫 z 分數本身（±3 截斷、中性藍色），只描述籌碼相對近 60 日的位置
    const bar = f => beat ? [f.effect / maxE, `var(--${f.effect >= 0 ? 'up' : 'dn'})`] : [Math.max(-3, Math.min(3, f.z)) / 3, 'var(--blue)'];
    const factors = `<div class="fc-factors">${FC.factors.map(f => { const [v, c] = bar(f); return `<div class="fc-f" title="z 分數 ${f.z}（相對近 60 日${!beat && Math.abs(f.z) > 3 ? '，長條截在 3' : ''}）">
          <span class="nm">${f.name}</span><span class="num muted">${sgn(f.value, 0)} 口</span>
          <span class="fc-bar"><span style="${v >= 0 ? 'left:50%' : 'right:50%'};width:${Math.abs(v) * 50}%;background:${c}"></span></span></div>`; }).join('')}
        <div class="muted small">${beat ? '長條往右 = 推升上漲機率，往左 = 壓低' : '長條往右 = 比近 60 日平常偏多（水位較高或增加較多），往左 = 偏少，越長越少見；只描述籌碼，不代表隔天漲跌'}</div></div>`;
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
  const u = e.target.closest('[data-unwatch]'), r = e.target.closest('#watchUndo');   // 第 25 輪 D25-09：自選頁移除、復原
  if (u || r) { e.stopImmediatePropagation();   // QA25-01：#view 上累積的其他點擊監聽不再重複執行
    if (u) { App.watchUndo = [...App.watch]; App.watch.delete(u.dataset.unwatch); } else if (App.watchUndo) { App.watch = new Set(App.watchUndo); App.watchUndo = null; }
    saveWatch(); return renderWatch(); }
  const tr = e.target.closest('tr[data-code]');
  if (tr) { location.hash = '#/stock/' + tr.dataset.code; return; }
  const g = e.target.closest('[data-group]');
  if (g) { localStore('focus', null, g.dataset.group); App.blOpen = g.dataset.group; App.blJump = 1; location.hash = '#/bubble'; }   // D28-04：手機清單展開這一列
}

// ─── 泡泡圖 ─────────────────────────────────────────────
const SYMLOG_C = 1;   // 對稱對數軸的線性區間（億），讓大小差很多的板塊能放在同一張圖
const symlog = v => Math.sign(v) * Math.log10(1 + Math.abs(v) / SYMLOG_C);

// 第 28 輪 D28-04：手機（≤720）加「圖｜清單」，預設清單（手機泡泡太小、標籤互相遮住，大小也看不出差別）；選擇只在這次瀏覽記住。
// 清單每列一個族群（最新一天，近 5 日由大到小），點一列在下方展開成分股，不捲走；再點收合
function bubbleList(groups) {
  const L = App.latest, k = L.dates.length - 1, open = App.blOpen;
  const QC = { 漲潮: 'var(--up)', 輪動: 'var(--amber)', 觀望: 'var(--blue)', 退潮: 'var(--dn)' };
  const nHit = App.blHit ? groups.filter(g => g.frames[k] && g.quadrant === App.blHit).length : 0;
  return `${nHit ? `<div class="small bl-hit">已標示「${App.blHit}」${nHit} 個</div>` : ''}<div class="muted small tbl-cap">資料日 ${md(L.dates[k])}。近5日 = 近 5 日法人累計（億）；日均差 = 近 5 日日均 − 20 日日均（億/天），正 = 偏流入；成交 = 成交額（億）。點一列看成分股</div>
    <div class="tbl-wrap"><table class="tbl bl-tbl"><thead><tr><th>${{ industry: '類股', chain: '產業鏈', concept: '概念股' }[App.group]}</th><th>近5日</th><th>日均差</th><th>漲跌</th><th>成交</th></tr></thead><tbody>` +
    groups.filter(g => g.frames[k]).sort((a, b) => b.frames[k][0] - a.frames[k][0]).map(g => { const [n5, dv, ch, tv] = g.frames[k];
      return `<tr data-bl="${esc(g.name)}"${g.name === open || g.quadrant === App.blHit ? ` class="${[g.name === open && 'on', g.quadrant === App.blHit && 'q-hit'].filter(Boolean).join(' ')}"` : ''}><td class="nm"><b>${esc(g.name)}</b><span><i style="color:${QC[g.quadrant]}">${g.quadrant}</i></span></td>
        <td class="num ${ycls(n5)}">${yi(n5)}</td><td class="num ${cls(dv)}">${sgn(dv, 1)}</td><td class="num ${cls(ch)}">${sgn(ch)}%</td><td class="num">${fmt(tv)}</td></tr>` +
        (g.name === open ? `<tr class="bl-x"><td colspan="5"><div class="muted small">${groupMeta(g)}</div><div class="tbl-wrap panel-list"><table class="tbl">${groupRows(g)}</table></div>` +
          (g.codes.filter(c => L.stocks[c]).length > 10 ? `<button class="chip" data-blall="${App.blAll ? 1 : 0}">${App.blAll ? '只顯示前 10 檔' : `顯示全部 ${g.codes.filter(c => L.stocks[c]).length} 檔`}</button>` : '') + '</td></tr>' : ''); }).join('') +
    '</tbody></table></div>';
}

function renderBubble() {
  const L = App.latest, groups = L.groups[App.group];
  const focus = localStore('focus', '');
  const mob = matchMedia('(max-width:720px)').matches, list = mob && App.bubbleView !== 'chart';
  App.blHit = App.blQ; App.blQ = null;                                  // D30-06：從今日頁象限進來才標示，換頁回來不標示
  $('#view').innerHTML = `
    <section class="sec">
      <div class="sec-h"><h2>板塊資金${list ? '' : '泡泡圖'}</h2><span class="muted small">${list ? '近 5 日法人淨流入由大到小' : 'X：近 5 日法人淨流入　Y：近 5 日日均比 20 日日均偏流入或偏流出　大小：成交額　顏色：漲跌幅'}</span>
        <span class="sp"></span>${mob ? segHTML('bvSeg', [['chart', '圖'], ['list', '清單']], list ? 'list' : 'chart') : ''}${groupSeg()}</div>
      ${list ? `<div class="card" id="blBox">${bubbleList(groups)}</div>` : '<div class="card" style="padding:6px"><div id="bubble"></div></div>'}
    </section>
    <section class="sec grid g2">
      ${list ? '' : `<div class="card"><div class="sec-h"><h2 id="gTitle">點泡泡看成分股</h2><span class="sp"></span><span id="gMeta" class="muted small"></span></div>
        <div class="tbl-wrap panel-list"><table class="tbl" id="gTable"></table></div><div class="muted small g-z" id="gZ"></div></div>`}
      <div class="card"><div class="sec-h"><h2>象限說明</h2></div>
        <div class="small" style="line-height:1.9">
          <div><b class="up">漲潮</b>：近 5 日淨流入，而且比 20 日平均更積極 → 資金正在加速進場</div>
          <div><b style="color:var(--amber)">輪動</b>：仍是淨流入，但力道比過去弱 → 可能接近尾聲、資金轉往他處</div>
          <div><b style="color:var(--blue)">觀望</b>：仍是淨流出，但賣壓比過去小 → 可能止跌、留意回流</div>
          <div><b class="dn">退潮</b>：淨流出且賣壓加大 → 資金正在撤出</div>
          ${list ? '' : `<div class="muted" style="margin-top:6px">按圖下方 ▶ 可回放近 ${L.dates.length} 個交易日的變化；軸為對稱對數刻度。</div>`}
        </div></div>
    </section>`;
  onSeg('grpSeg', v => { setGroup(v); renderBubble(); });
  $('#view').addEventListener('click', onRowClick);
  if (mob) onSeg('bvSeg', v => { App.bubbleView = v; if (window.Plotly && $('#bubble')) Plotly.purge('bubble'); renderBubble(); });
  if (list) {
    $('#blBox').addEventListener('click', e => {
      if (e.target.closest('[data-blall]')) { App.blAll = !App.blAll; $('#blBox').innerHTML = bubbleList(groups); return; }   // D30-08
      const tr = e.target.closest('tr[data-bl]');
      if (!tr) return;
      const name = tr.dataset.bl, y0 = tr.getBoundingClientRect().top;
      App.blOpen = App.blOpen === name ? null : name; App.blAll = false;
      if (App.blOpen) localStore('focus', null, name);
      $('#blBox').innerHTML = bubbleList(groups);
      window.scrollBy(0, $(`#blBox tr[data-bl="${CSS.escape(name)}"]`).getBoundingClientRect().top - y0);   // 點的那一列留在原位（上方收合時不跳走）
    });
    if (App.blJump) { App.blJump = 0; requestAnimationFrame(() => $('#blBox tr.on')?.scrollIntoView()); }
    else if (App.blHit) requestAnimationFrame(() => $('#blBox tr.q-hit')?.scrollIntoView());   // 從今日頁點族群進來：捲到展開的那一列（route() 捲到頂端之後）
    return;
  }
  $('#gZ').addEventListener('click', e => { if (e.target.closest('[data-gz]')) { App.gzAll = !App.gzAll; gzFoot(); } });   // 第 49 輪 F47-10
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
    const placed = [], text = gs.map(() => ''), font = d.map(v => Math.max(10, Math.min(14, v * 0.2)));   // D27-04：最小 10px
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
      // 第 28 輪 D28-07：Plotly basic 的 d3-format 不認得 +.1f（會顯示原始數字、正值沒有 +），先格式化成字串；近 5 日和泡泡上的字同一種小數位
      customdata: gs.map(g => { const f = g.frames[k]; return [g.name, amount(f[0]), sgn(f[1], 1) + '億/天', sgn(f[2]) + '%', fmt(f[3]) + '億']; }),
      textfont: { size: lab.font, color: '#fff' },
      hovertemplate: '<b>%{customdata[0]}</b><br>近5日 %{customdata[1]}<br>5日日均−20日日均 %{customdata[2]}<br>漲跌 %{customdata[3]}<br>成交 %{customdata[4]}<extra></extra>',
      marker: {
        size: d, sizemode: 'diameter',
        color: gs.map(g => g.frames[k][2]), cmin: -4, cmax: 4,
        // 色彩壓深，白字才看得清楚
        colorscale: [[0, '#17804a'], [0.5, '#5d636b'], [1, '#c23b3b']],
        line: { width: 1, color: 'rgba(255,255,255,.45)' }, opacity: isDark() ? .82 : 1,   // D27-04：淺色底不透明，白字對比 ≥ 4.5
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
    yaxis: axis(ticksY, limY, '← 偏流出　近 5 日日均 − 20 日日均（億/天）　偏流入 →', ''),   // 第 27 輪 D27-04：左右兩半都成立（原「加速／放緩」在淨流出那半邊意思相反）；Y 軸標題會轉 -90° 直書，←／→ 轉完才是 ↓／↑
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
      if (g) { localStore('focus', null, name); showGroup(g); if (narrow) $('#gTitle').closest('.card').scrollIntoView(); }   // D27-04：手機點了捲到明細
    });
  });
}

const groupMeta = g => `<span class="pill">${g.quadrant}</span>　5日 <span class="${ycls(g.net_5d)}">${yi(g.net_5d)}</span>　連${g.streak >= 0 ? '買' : '賣'} ${Math.abs(g.streak)} 天　法人 ${md(App.latest.flow_date)}`;
function groupRows(g) {   // D28-04：泡泡明細卡與手機清單展開共用
  const S = App.latest.stocks;
  const rows = g.codes.filter(c => S[c]).sort((a, b) => (S[b].n5 ?? 0) - (S[a].n5 ?? 0));
  return `<thead><tr><th>股票</th><th>收盤</th><th>漲跌</th><th>法人1日</th><th>法人5日</th></tr></thead><tbody>` +
    rows.map(c => { const s = S[c]; return `<tr data-code="${c}"${yi(s.n1) === '0億' && yi(s.n5) === '0億' ? ' class="z"' : ''}><td class="nm"><b>${esc(s.n)}</b><span>${c}</span></td>
      <td class="num ${cls(s.p)}${s.lm ? ' lm' : ''}">${pfmt(s.c)}</td>${pctCell(s)}
      <td class="num ${ycls(s.n1)}">${yi(s.n1)}</td><td class="num ${ycls(s.n5)}">${yi(s.n5)}</td></tr>`; }).join('') + '</tbody>';
}
function showGroup(g) {
  if (!g) return;
  $('#gTitle').textContent = g.name;
  $('#gMeta').innerHTML = groupMeta(g);
  $('#gTable').innerHTML = groupRows(g);
  gzFoot();
}
// 第 49 輪 F47-10（R72）：點泡泡看成分股卡，法人 1 日、5 日都顯示 0億 的列（tr.z）預設收起，表尾可展開；只在這次瀏覽記住
function gzFoot() {
  const t = $('#gTable'), z = t.querySelectorAll('tr.z').length, n = t.querySelectorAll('tbody tr').length;
  t.classList.toggle('gz', !App.gzAll);
  $('#gZ').innerHTML = z ? `${App.gzAll ? '含 ' : z < n ? '另有 ' : ''}${z} 檔法人 1 日、5 日都是 0億　<button type="button" class="chip" data-gz>${App.gzAll ? '收合' : '顯示'}</button>` : '';
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
  ['ry', '營收年增', 'ry', -1, 'x'], ['dy', '殖利率', 'dy', -1, 'v'], ['dv', '近期除息', 'dva', 1, 'x'], ['pe', '本益比最低', 'pe', 1, 'v'],   // 第 35 輪 F35-4
  ['m+', '融資增加', 'm*', -1, 'm'], ['m-', '融資減少', 'm*', 1, 'm'], ['mr', '融資增加率', 'mr*', -1, 'm'],
  ['s+', '融券增加', 's*', -1, 'm'], ['s-', '融券減少', 's*', 1, 'm'], ['sr', '券資比', 'sr', -1, 'm'], ['mu', '融資使用率', 'mu', -1, 'm'],
  ['l+', '借券賣出增加', 'la*', -1, 'l'], ['lp', '借券占股本', 'lp', -1, 'l'],     // 第 11 輪 B14：'l' = 借券（需要 screen.json）
];
const RANK_GROUPS = [['法人', ['n+', 'n-', 'f+', 'f-', 't+', 't-', 'd+', 'd-', 'fs', 'ts', 's']], ['價量', ['p+', 'p-', 'tv', 'vr', 'nh', 'rs20', 'to']],
  ['基本面', ['ry', 'dy', 'dv', 'pe']], ['融資融券', ['m+', 'm-', 'mr', 's+', 's-', 'sr', 'mu']], ['借券', ['l+', 'lp']]];
// screen.json 排行的額外篩選與表格欄位
const RANK_FILTER = { ry: x => !(x.rm < revMonth()), nh: x => x.nh > 0, dy: x => isNum(x.pe) && x.pe > 0 && x.cap !== 1, pe: x => x.pe > 0 && x.cap !== 1, dv: x => x.dva <= 90, sr: x => isNum(x.mb) && x.mb >= MARGIN_BASE };
const RANK_COLS = { vr: ['vr'], nh: ['nh'], rs20: ['rs20'], ry: ['ry'], dy: ['dy', 'pe', 'pb', 'dv'], dv: ['dv', 'dy'], pe: ['pe', 'pb', 'dy'], to: ['to', 'mc'] };
// 第 23 輪 F23-4d：匯出的連續天數最多看 30 日（streak(…[-30:])），30 寫「買30+」「賣30+」
const streakTxt = v => v ? (v > 0 ? '買' : '賣') + Math.abs(v) + (Math.abs(v) >= 30 ? '+' : '') : '--';
const modeSeg = v => segHTML('modeSeg', [['rank', '排行'], ['screen', '選股'], ['hl', '新訊號']], v);
const onModeSeg = () => onSeg('modeSeg', v => { location.hash = v === 'rank' ? '#/rank' : '#/rank/' + v; });

function stockTable(list, span = '1', rm = false) {   // rm：自選頁（名稱欄加移除、排序鈕，編輯模式才顯示）
  const k = span === '5' ? '5' : '1', lbl = k === '5' ? '5日' : '1日';
  const amt = v => `<td class="num ${ycls(v)}">${yi(v)}</td>`;
  const fd = md(App.latest.flow_date);
  // 自選頁：1日／5日放在表格說明列的最左邊，切換資金／表現／基本面、1日／5日時按鈕都不移位
  const cap = `<div class="muted small tbl-cap">${k === '5' ? `法人欄位為截至 ${fd} 的近 5 日累計（億）` : `法人欄位為 ${fd} 當日買賣超（億）`}</div>`;
  return `${flowNote()}${rm ? `<div class="cap-row">${spanSeg(span)}${cap}</div>` : cap}
    <div class="tbl-wrap"><table class="tbl"><thead><tr>
      <th>股票</th><th>收盤</th><th>漲跌</th><th>成交額</th><th>外資${lbl}</th><th>投信${lbl}</th><th>自營${lbl}</th><th>法人${lbl}</th>
      <th>外資連</th><th>投信連</th><th>法人連</th></tr></thead><tbody>` +
    list.map(([c, s]) => `<tr data-code="${c}">
      <td class="nm">${rm ? wCtl(c) : ''}<b>${esc(s.n)}</b>${alertBadge(s)}<span>${c} ${esc(s.i)}</span></td>
      <td class="num ${cls(s.p)}${s.lm ? ' lm' : ''}">${pfmt(s.c)}</td>${pctCell(s)}
      <td class="num">${fmt(s.tv, 1)}億</td>
      ${amt(s['f' + k])}${amt(s['t' + k])}${amt(s['d' + k])}${amt(s['n' + k])}
      <td class="num ${cls(s.fs)}">${streakTxt(s.fs)}</td><td class="num ${cls(s.ts)}">${streakTxt(s.ts)}</td>
      <td class="num ${cls(s.s)}">${streakTxt(s.s)}</td></tr>`).join('') +
    '</tbody></table></div>';
}

function spanSeg(span) { return segHTML('rspanSeg', [['1', '1日'], ['5', '5日']], span); }

async function renderRank(arg) {
  // 第 8 輪：#/rank/{排行代號}（例如信用交易卡的 #/rank/s-）→ 記住排行後把網址改回 #/rank
  // 第 25 輪 D25-08：網址保留排行代號（可分享）。第 27 輪 D27-05：#/rank 沒帶代號時開法人買超，同一次瀏覽中才回到上次的排行
  localStore('rank2', null, App.rank2 = RANKS.some(r => r[0] === arg) ? arg : App.rank2 || 'n+');
  const S = await loadScreen();
  const avail = RANKS.filter(r => !r[4] || S);          // screen.json 不存在時，需要它的排行不出現
  const by0 = localStore('rank2', 'n+'), mkt = localStore('mkt', 'all'), span = localStore('rspan', '1');
  const minTv = localStore('rtv', '0.5');   // 成交額門檻（億），套用到所有排行
  const [by, , f, dir, src] = avail.find(r => r[0] === by0) || RANKS[0];
  if (arg !== by) history.replaceState(null, '', '#/rank/' + by);   // D27-05：網址補成實際顯示的排行
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
    } else table = screenTable(list, RANK_COLS[by]) + (by === 'ry' ? revNote(inMkt, Number(minTv)) : '');
  }
  if (!foot) foot = '金額 = 買賣超張數 × 當日收盤，不含 ETF。成交額門檻以資料日成交額篩選，套用到所有排行。「1日／5日」只切換法人、外資、投信、自營買賣超排行與表格法人欄位的天數；漲幅、跌幅、成交額與連買排行不受影響。連買為連續買超天數，天數相同時以近 5 日金額排序。' +
    (by === 'dv' ? '近期除息 = 近 90 天內除息或除權息，依除息日由近到遠。' + DV_NOTE : '') +
    (by === 'p+' || by === 'p-' ? '漲跌欄的「漲停」「跌停」= 收盤等於當天的漲停價、跌停價（本站依參考價 ±10% 與升降單位推算，和官方家數偶爾差 1 檔）；新上市前 5 個交易日沒有漲跌幅限制，不標。' : '') +
    (S ? '量比、創新高、相對強勢、營收、估值排行的資料日見「選股」頁；殖利率、本益比排行已排除虧損（官方本益比空白）與 90 天內股本變動的股票。週轉率 = 今日成交股數 ÷ 目前發行股數，市值 = 收盤 × 目前發行股數；增資、減資前後可能失真。' : '');
  $('#view').innerHTML = `<section class="sec">
      <div class="sec-h">${modeSeg('rank')}<span class="sp"></span>
        ${segHTML('mktSeg', [['all', '全部'], ['TWSE', '上市'], ['TPEx', '上櫃']], mkt)}
        ${spanSeg(span)}
        ${by === 'm+' || by === 'm-' ? segHTML('munitSeg', [['amt', '估算金額'], ['lot', '張數']], unit) : ''}
        <select id="tvSel" class="sel" aria-label="成交額門檻">${[['0', '成交額不限'], ['0.5', '成交額 ≥ 0.5 億'], ['1', '成交額 ≥ 1 億'], ['5', '成交額 ≥ 5 億']]
          .map(([v, t]) => `<option value="${v}"${v === minTv ? ' selected' : ''}>${t}</option>`).join('')}</select>
</div>
      <div class="rk-q"><select id="rankSel" class="sel">${RANK_GROUPS.map(([g, ids]) => { const rs = ids.map(id => avail.find(r => r[0] === id)).filter(Boolean);
          return rs.length ? `<optgroup label="${g}">${rs.map(r => `<option value="${r[0]}"${r[0] === by ? ' selected' : ''}>${r[1]}</option>`).join('')}</optgroup>` : ''; }).join('')}</select>${['n+', 'f+', 't+', 'p+', 'p-', 'tv', 'm+'].filter(id => avail.some(r => r[0] === id)).map(id => `<button class="chip${id === by ? ' on' : ''}" data-rk="${id}">${RANKS.find(r => r[0] === id)[1]}</button>`).join('')}</div>
      <div class="card">${table}</div>
      <div class="muted small" style="margin-top:6px">${foot}</div></section>`;
  keyCol(rankKeyCol(by, field, src, byAmt));
  $('#view').querySelectorAll('[data-rk]').forEach(b => b.addEventListener('click', () => { location.hash = '#/rank/' + b.dataset.rk; }));   // D25-13 常用排行
  $('#rankSel').addEventListener('change', e => { location.hash = '#/rank/' + e.target.value; });
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
      <td class="num ${cls(x.p)}${x.lm ? ' lm' : ''}">${pfmt(x.c)}</td>${pctCell(x)}${sp(x.r5)}
      ${n0(x.mb)}${lots(x['m' + k])}<td class="num ${cls(x['ma' + k])}">${isNum(x['ma' + k]) ? yi(x['ma' + k]) : '--'}</td>${by === 'mr' ? sp(x['mr' + k]) : ''}
      ${n0(x.sb)}${lots(x['s' + k])}${p2(x.sr)}${p2(x.mu)}<td class="num">${fmt(x.tv, 1)}億</td></tr>`).join('') +
    '</tbody></table></div>';
}

// 第 11 輪 B14：借券排行的表格
function sblTable(list, span) {
  const k = span === '5' ? '5' : '1', lbl = k === '5' ? '5日' : '1日';
  return `<div class="tbl-wrap"><table class="tbl"><thead><tr><th>股票</th><th>收盤</th><th>漲跌</th><th>5日漲跌</th><th>借券餘額</th><th>借券${lbl}</th><th>估算（億）</th><th>占股本</th><th>融券餘額</th><th>成交額</th></tr></thead><tbody>` +
    list.map(x => `<tr data-code="${x.code}"><td class="nm"><b>${esc(x.n)}</b>${alertBadge(x)}<span>${x.code} ${esc(x.i)}</span></td>
      <td class="num ${cls(x.p)}${x.lm ? ' lm' : ''}">${pfmt(x.c)}</td>${pctCell(x)}<td class="num ${cls(x.r5)}">${isNum(x.r5) ? sgn(x.r5) + '%' : '--'}</td>
      <td class="num">${isNum(x.lb) ? fmt(x.lb) : '--'}</td><td class="num ${cls(x['l' + k])}">${isNum(x['l' + k]) ? sgn(x['l' + k], 0) : '--'}</td>
      <td class="num ${cls(x['la' + k])}">${isNum(x['la' + k]) ? yi(x['la' + k]) : '--'}</td><td class="num">${isNum(x.lp) ? fmt(x.lp, 2) + '%' : '--'}</td>
      <td class="num">${isNum(x.sb) ? fmt(x.sb) : '--'}</td><td class="num">${fmt(x.tv, 1)}億</td></tr>`).join('') +
    '</tbody></table></div>';
}

// ─── 第 21 輪 F21-1：近期新訊號（latest.json stocks[代號].hl；20 日均額取 screen.json）──────────
// 第 22 輪 F22-11：營收面向改稱「基本面」，加 EPS 事件 et、eg（附加值為季別，標籤前加「26Q3」）
const HL_KINDS = { nh: ['價量', '60 日新高帶量'], vu: ['價量', '量比 ≥ 2 漲 ≥ 3%'], s3: ['法人', '法人連買 3 日'], t3: ['法人', '投信連買 3 日'],
  t5: ['法人', '投信 5 日買超 ≥ 成交額 5%'], rv: ['基本面', '營收年增 ≥ 30% 創新高'], et: ['基本面', 'EPS 轉盈'], eg: ['基本面', 'EPS 年增 ≥ 50%'], ae: ['主動ETF', '主動 ETF 新增'] };
const hlTag = ([k, d, x]) => `<span class="hl-tag">${k === 'rv' ? `${x % 100} 月營收創新高` : k === 'ae' ? `${x} 新增`
  : (k === 'et' || k === 'eg' ? `${String(x).slice(2, 4)}Q${x % 100} ` : '') + HL_KINDS[k][1]} <i>${md(d)}</i></span>`;
const hlDims = x => new Set(x.hl.map(e => HL_KINDS[e[0]]?.[0]).filter(Boolean)).size;
async function renderHl() {
  const S = await loadScreen(), min = localStore('hlmin', '3');
  const base = S ? screenRows().filter(x => x.hl && !x.dsp && !x.nt && isNum(x.a20) && x.a20 >= 0.5).map(x => [x, hlDims(x)]) : [];
  const cnt = n => base.filter(r => r[1] >= n).length;
  const list = base.filter(r => r[1] >= Number(min)).sort((a, b) => b[1] - a[1] || b[0].a20 - a[0].a20);
  const L = App.latest;
  $('#view').innerHTML = `<section class="sec">
      <div class="sec-h">${modeSeg('hl')}<span class="sp"></span>${segHTML('hlSeg', [['3', '面向 ≥ 3'], ['2', '面向 ≥ 2']], min)}</div>
      <div class="muted small tbl-cap">面向 ≥ 3：${fmt(cnt(3))} 檔；≥ 2：${fmt(cnt(2))} 檔（20 日均成交額 ≥ 0.5 億，不含處置股、今日無成交）。行情 ${md(L.date)}、法人 ${md(L.flow_date)}</div>
      <div class="card">${!S ? '<div class="empty">尚未產生選股資料（screen.json），無法計算 20 日均成交額。</div>'
        : !list.length ? '<div class="empty">目前沒有符合的股票。</div>'
        : `<div class="tbl-wrap"><table class="tbl"><thead><tr><th>股票</th><th>面向</th><th class="hl-th">近期新訊號</th><th>收盤</th><th>漲跌</th><th>20日均額</th></tr></thead><tbody>` +
          list.map(([x, n]) => `<tr data-code="${x.code}">
            <td class="nm"><b>${esc(x.n)}</b>${alertBadge(x)}<span>${x.code} ${esc(x.i)}</span></td>
            <td class="num">${n}</td><td class="hl-tags">${x.hl.map(hlTag).join('')}</td>
            <td class="num ${cls(x.p)}${x.lm ? ' lm' : ''}">${pfmt(x.c)}</td>${pctCell(x)}<td class="num">${fmt(x.a20, 1)}億</td></tr>
            <tr class="hl-sub" data-code="${x.code}"><td colspan="6">${x.hl.map(hlTag).join('')}</td></tr>`).join('') + '</tbody></table></div>'}</div>
      <div class="muted small" style="margin-top:6px">列出最近 5 個交易日（營收、EPS 為最近 20 個交易日）在價量、法人、基本面（營收、EPS）、主動 ETF 四個面向新出現的事件；同一面向有多個事件只算 1 個面向。
        「新出現」= 當天符合、前一個交易日不符合，口徑和選股條件相同；60 日新高帶量 = 創 60 日以上新高且量比 ≥ 1.5；營收創新高 = 單月營收創新高且年增 ≥ 30%；
        EPS 只看全市場最新一季的單季 EPS：轉盈 = 去年同季 ≤ 0、本季 > 0，年增 ≥ 50% 不含去年同季 < 0.1 元（基期低）。
        營收、EPS 日期為本站首次收錄日（不一定是公司公布日，財報季會集中出現）；主動 ETF 只涵蓋有持股資料的 ${Object.keys(L.holdings || {}).length} 檔。只描述發生了什麼，不代表之後的走勢。</div></section>`;
  onModeSeg();
  if (S) onSeg('hlSeg', v => { localStore('hlmin', null, v); renderHl(); });
  $('#view').addEventListener('click', onRowClick);
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
  // 第 35 輪 F35-1：除息至今（日曆天，相對選股資料日）；尚未填息時今天原始收盤距除息前收盤 %
  if (x.dvd && S) {
    x.dva = Math.round((Date.parse(S.d) - Date.parse(x.dvd)) / 864e5);
    x.dvg = !isNum(x.dvn) && !x.dvx && isNum(x.c) && x.dvp > 0 ? (x.c / x.dvp - 1) * 100 : null;
  }
  const n = S && App.latest?.nx?.[code];   // 第 49 輪 F47-12（R71）：預告表的下一次除息（日曆天，相對選股資料日）；「權」不算
  if (n && (n[1] === '息' || n[1] === '權息')) { x.nxd = n[0]; x.nxt = n[1]; x.nxa = Math.round((Date.parse(n[0]) - Date.parse(S.d)) / 864e5); }
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

// 第 14 輪 F14-1、F14-2：基期門檻。營收：去年同月 < 1,000 萬元（10,000 千元）；EPS：去年同季單季 EPS > 0 且 < 0.1 元（≤ 0 時年增為 null，照舊「轉盈」或 --）
const REV_BASE = 10000, EPS_BASE = 0.1;
const revLow = x => isNum(x.ry) && isNum(x.rb) && x.rb < REV_BASE;
const epsLow = (v, b) => isNum(v) && isNum(b) && b < EPS_BASE;
const epsTurn = x => isNum(x.eq) && isNum(x.eb) && x.eb <= 0 && x.eq > 0;   // 第 22 輪 F22-11：單季 EPS 轉盈（同季報卡；ey 為 null）
// 營收年增排行表下一行：比欄名月份舊而未列入的檔數（市場、成交額門檻同排行）與基期低的定義
function revNote(inMkt, minTv) {
  const M = revMonth(), n = M ? screenRows().filter(x => isNum(x.ry) && x.rm < M && inMkt(x) && (x.tv ?? 0) >= minTv).length : 0;
  return `<div class="muted small" style="margin-top:6px">${n ? `另有 ${fmt(n)} 檔的最新營收早於 ${Number(M.slice(4))} 月，未列入排行（選股的營收條件仍包含）。` : ''}「基期低」= 去年同月營收不到 1,000 萬元，年增率容易很大。</div>`;
}

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
  k: ['K值', x => x.k, v => fmt(v, 1)], rsi: ['RSI', x => x.rsi, v => fmt(v, 1)],   // 第 18 輪 F18-2
  rs20: ['20日相對', x => x.rs20, v => sgn(v)], rs60: ['60日相對', x => x.rs60, v => sgn(v)],
  s: ['法人連', x => x.s, streakTxt], fs: ['外資連', x => x.fs, streakTxt], ts: ['投信連', x => x.ts, streakTxt],
  f5: ['外資5日', x => x.f5, yi], t5: ['投信5日', x => x.t5, yi], n5: ['法人5日', x => x.n5, yi], n20: ['法人20日', x => x.n20, yi],
  t5r: ['投信5日/額', x => isNum(x.t5) && x.a20 > 0 ? x.t5 / (x.a20 * 5) * 100 : null, spct],
  n5r: ['法人5日/額', x => isNum(x.n5) && x.a20 > 0 ? x.n5 / (x.a20 * 5) * 100 : null, spct],
  m5: ['融資5日', x => x.m5, v => sgn(v, 0)],
  m5p: ['融資5日%', x => isNum(x.m5) && isNum(x.mb) && x.mb - x.m5 > 0 ? x.m5 / (x.mb - x.m5) * 100 : null, spct],
  sr: ['券資比', x => x.sr, v => v == null ? '--' : fmt(v, 2) + '%'], mu: ['使用率', x => x.mu, v => v == null ? '--' : fmt(v, 2) + '%'],
  ry: ['營收年增', x => x.ry, (v, x) => { const old = x.rm && String(x.rm) !== revMonth(), low = revLow(x);     // 第 14 輪：月份小字與基期低放第二行（欄寬）
    return spct(v) + (old || low ? `<span class="sub2">${old ? `（${x.rm % 100}月）` : ''}${low ? `<i class="al al-b" title="去年同月營收 ${fmt(x.rb)} 千元">基期低</i>` : ''}</span>` : ''); }],
  rc: ['累計年增', x => x.rc, spct], rh: ['營收新高(年)', x => x.rh, int0], r3: ['連3月年增', x => x.r3, v => v === 1 ? '✓' : '--'],
  pe: ['本益比', x => x.pe, v => fmt(v, 2), 1], dy: ['殖利率', x => x.dy, spct], pb: ['淨值比', x => x.pb, v => fmt(v, 2), 1],
  pbp: ['淨值比位置', x => x.pbp, v => fmt(v) + '%', 1],
  eq: ['單季EPS', x => x.eq, (v, x) => fmt(v, 2) + finTag(x)], ey: ['EPS年增', x => x.ey, (v, x) => epsLow(v, x.eb) ? `基期低${finTag(x)}<span class="sub2">去年同季 ${fmt(x.eb, 2)} 元</span>` : spct(v) + finTag(x)],
  eb: ['去年同季EPS', x => x.eb, (v, x) => fmt(v, 2) + finTag(x)],   // 第 22 輪 F22-11：「單季 EPS 轉盈」的對照欄（年增無法計算）
  e4: ['近4季EPS', x => x.e4, v => fmt(v, 2)], gm: ['毛利率', x => x.gm, (v, x) => fmt(v, 1) + '%' + finTag(x)],
  gmy: ['毛利率年增', x => x.gmy, (v, x) => sgn(v, 1) + '點' + finTag(x)], eh: ['EPS新高(季)', x => x.eh, int0],
  // 第 35 輪 F35-3：最近除息（排序 = 除息至今天數，近的在前）；第二行為填息狀態
  dv: ['最近除息', x => x.dva, (v, x) => md(x.dvd) + `<span class="sub2">${isNum(x.dvn) ? x.dvn + ' 天填息' : x.dvx ? '中斷（' + x.dvx + '）' : '未填息'}</span>`, 1],
  dvg: ['距填息價', x => x.dvg, spct, 1],
  nx: ['即將除息', x => x.nxa, (v, x) => md(x.nxd) + '<span class="sub2">' + v + ' 天後' + (x.nxt === '權息' ? '（權息）' : '') + '</span>', 1],   // 第 49 輪 F47-12：排序 = 距除息天數，近的在前
  mc: ['市值', x => x.mc, v => fmt(v, 0) + '億'], to: ['週轉率', x => x.to, v => fmt(v, 2) + '%'],   // 第 12 輪 B11
  lb: ['借券餘額', x => x.lb, v => fmt(v)], l5: ['借券5日', x => x.l5, v => sgn(v, 0)], lp: ['借券占股本', x => x.lp, v => fmt(v, 2) + '%'],
};
const CAP_TAG = '<i class="al al-c" title="90 天內有除權、減資或面額變更，官方本益比、殖利率可能尚未調整">股本變動</i>';
// 第 13 輪 F13-1：把第 i 欄（排序欄）移到第 2 欄（名稱之後），手機不用橫向捲動就看得到；整欄移動，th 的 data-k 跟著走
function keyCol(i) {
  const t = $('#view table.tbl');
  if (t && i > 1) for (const tr of t.rows) if (tr.cells.length > i) tr.insertBefore(tr.cells[i], tr.cells[1]);
}
// 各排行表的排序欄位置（stockTable、marginTable、sblTable 的欄序；screenTable 的排序欄固定在第 5 欄 = 4）
const STOCK_KEYS = ['', 'c', 'p', 'tv', 'f', 't', 'd', 'n', 'fs', 'ts', 's'];
const rankKeyCol = (by, field, src, byAmt) => !src ? STOCK_KEYS.indexOf(/^[ftdn][15]$/.test(field) ? field[0] : field)
  : src === 'm' ? { m: byAmt ? 6 : 5, mr: 7, s: 8, sr: 9, mu: 10 }[by.replace(/[+-]$/, '')]
  : src === 'l' ? { 'l+': 6, lp: 7 }[by] : 4;
// 固定欄（股票｜收盤｜漲跌｜成交額）＋ cols；o = {sort: 目前排序欄, cap: 是否標示股本變動, rm: 自選頁（加移除、排序鈕，不列成交額）}；sort 有值時欄名可點排序
function screenTable(list, cols, o = {}) {
  const head = k => { const c = SCR_COLS[k], M = revMonth(), Fq = finQ();
    return k === 'ry' && M ? `營收年增（${Number(M.slice(4))} 月）` : (k === 'eq' || k === 'ey') && Fq ? `${c[0]}（Q${Number(Fq.slice(4))}）` : c[0]; };
  const th = (k, t) => o.sort ? `<th class="sort" data-k="${k}">${t}</th>` : `<th>${t}</th>`;
  return `<div class="tbl-wrap"><table class="tbl"><thead><tr><th>股票</th><th>收盤</th>${th('p', '漲跌')}${o.rm ? '' : th('tv', '成交額')}${cols.map(k => th(k, head(k))).join('')}</tr></thead><tbody>` +
    list.map(x => `<tr data-code="${x.code}"><td class="nm">${o.rm ? wCtl(x.code) : ''}<b>${esc(x.n)}</b>${alertBadge(x)}${o.cap && x.cap === 1 ? CAP_TAG : ''}<span>${x.code} ${esc(x.i)}</span></td>
      <td class="num ${cls(x.p)}${x.lm ? ' lm' : ''}">${pfmt(x.c)}</td>${pctCell(x)}${o.rm ? '' : `<td class="num">${fmt(x.tv, 1)}億</td>`}` +
      cols.map(k => { const [, get, f] = SCR_COLS[k], v = get(x);
        return `<td class="num ${['s', 'fs', 'ts', 'nh', 'nl', 'rh', 'r3', 'vr', 'a20', 'sr', 'mu', 'pe', 'pb', 'hd', 'pbp', 'gm', 'eh', 'lb', 'lp', 'mc', 'to'].includes(k) || k === 'dv' ? '' : cls(v)}">${v == null ? '--' : f(v, x)}</td>`; }).join('') + '</tr>').join('') +
    '</tbody></table></div>';
}

const scrGe = k => (x, v) => isNum(x[k]) && x[k] >= v;
const scrPos = k => x => isNum(x[k]) && x[k] > 0;
const valGuard = (x, st) => !st.xc || x.cap !== 1;
const DV_NOTE = '股利條件只看近 365 天最近一次除息或除權息（純配股不算），季配、半年配只看最近一次：填息 = 除息當天起原始收盤回到除息前收盤，填息天數含除息當天；還沒填息就遇到除權、減資等股本變動，標「中斷」。股價資料起點以前的除息不在範圍內。殖利率用去年股利 ÷ 今天收盤，股價下跌時殖利率會變高。';
const DV_TITLE = '填息 = 除息後原始收盤回到除息前收盤；只看近 365 天最近一次，之後遇到除權、減資等股本變動就停止計算';
const m5Base = x => isNum(x.m5) && isNum(x.mb) ? x.mb - x.m5 : null;
// opts：數字陣列或 [值, 文字]（下拉）、'num'（數字欄）；sw = 開關；val = 估值條件（受 xc 影響）
const SCREEN_CONDS = [
  { id: 'tv', g: '流動性', label: '成交額 ≥ {v} 億', opts: [0.5, 1, 3, 5, 10], def: 0.5, f: scrGe('tv') },
  { id: 'a20', g: '流動性', label: '20 日均成交額 ≥ {v} 億', opts: [0.5, 1, 3, 5], def: 1, f: scrGe('a20'), cols: ['a20'] },
  // 第 12 輪 B11：目前股數計算；null（沒有股數）不符合
  { id: 'mc', g: '流動性', label: '市值 ≥ {v} 億', opts: [50, 100, 500, 1000], def: 100, f: scrGe('mc'), cols: ['mc'], title: '收盤 × 目前發行股數' },
  { id: 'to', g: '流動性', label: '週轉率 ≥ {v}%', opts: [1, 3, 5, 10], def: 3, f: scrGe('to'), cols: ['to'], title: '今日成交股數 ÷ 目前發行股數；增資、減資前後可能失真' },
  { id: 'p', g: '價量', label: '今日漲幅 ≥ {v}%', opts: 'num', def: 3, f: scrGe('p') },
  { id: 'lm', g: '價量', label: '今日收在{v}', opts: [[1, '漲停價'], [-1, '跌停價']], def: 1, f: (x, v) => x.lm === v, title: '收盤等於當天的漲停價或跌停價（本站依參考價 ±10% 與升降單位推算，和官方家數偶爾差 1 檔）；新上市前 5 個交易日沒有漲跌幅限制、今日無成交，都不列入' },   // 第 50 輪 F50-1（R73）
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
  // 第 18 輪 F18-2：KD(9,3,3)、RSI(14)（還原價）；急漲急跌時會大量出現，結果上方列全市場比例
  { id: 'kx', g: '技術', label: 'KD 黃金交叉（K < {v}）', opts: [20, 30, 50], def: 20, f: (x, v) => x.kx === 1 && isNum(x.k) && x.k < v, cols: ['k'], osc: 1,
    title: '今日 K 由下往上穿過 D，且 K 低於門檻；急跌期常一次出現上百檔' },
  { id: 'rl', g: '技術', label: 'RSI(14) ≤ {v}', opts: [20, 30], def: 30, f: (x, v) => isNum(x.rsi) && x.rsi <= v, cols: ['rsi'], osc: 1 },
  { id: 'ru', g: '技術', label: 'RSI(14) ≥ {v}', opts: [70, 80], def: 70, f: (x, v) => isNum(x.rsi) && x.rsi >= v, cols: ['rsi'], osc: 1 },
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
  { id: 'et', g: '基本面', label: '單季 EPS 轉盈', sw: true, f: epsTurn, cols: ['eq', 'eb'], title: '最新一季單季 EPS > 0，去年同季 ≤ 0（年增無法計算）' },
  { id: 'pe', g: '基本面', label: '0 < 本益比 ≤ {v}', opts: [10, 15, 20], def: 15, val: true, f: (x, v, st) => isNum(x.pe) && x.pe > 0 && x.pe <= v && valGuard(x, st), cols: ['pe'] },
  { id: 'dy', g: '基本面', label: '殖利率 ≥ {v}%', opts: [3, 4, 5, 6], def: 5, val: true, f: (x, v, st) => isNum(x.dy) && x.dy >= v && valGuard(x, st), cols: ['dy', 'dv', 'dvg'] },
  // 第 35 輪 F35-2：股利（近 365 天最近一次除息或除權息；null = 沒有 → 不符合）
  { id: 'dvk', g: '基本面', label: '近一年有現金配息', sw: true, f: x => x.dvk >= 1, cols: ['dv'], title: '近 365 天有除息或除權息；純配股不算' },
  { id: 'dvf', g: '基本面', label: '最近一次已填息', sw: true, f: x => isNum(x.dvn), cols: ['dv'], title: DV_TITLE },
  { id: 'dvu', g: '基本面', label: '最近一次尚未填息', sw: true, f: x => !!x.dvd && !isNum(x.dvn) && !x.dvx, cols: ['dv', 'dvg'], title: DV_TITLE },
  { id: 'dvr', g: '基本面', label: '近 {v} 天內除息', opts: [30, 60, 90], def: 60, f: (x, v) => isNum(x.dva) && x.dva <= v, cols: ['dv'] },
  { id: 'nxd', g: '基本面', label: '{v} 天內將除息', opts: [7, 14, 30], def: 14, f: (x, v) => isNum(x.nxa) && x.nxa <= v, cols: ['nx'], title: '證交所、櫃買中心除權除息預告表中，資料日之後的下一次除息或除權息；天數為日曆天；只有除權（多為現金增資）的不算；以公司公告為準' },   // 第 49 輪 F47-12（R71）
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
const SCREEN_GROUPS = ['流動性', '價量', '技術', '法人', '信用', '基本面', '排除'];
// [id, 按鈕, 條件]；套用時取代全部條件並加上 xd、xn、xc；r1、r2 為參考組（風險檢查）
const SCREEN_PRESETS = [
  ['1', '法人連買＋營收創新高', 's=3&rh=1&tv=0.5'], ['2', '投信認養', 'ts=3&t5=1&t5r=5&tv=0.5'], ['3', '帶量突破', 'nh=60&vr=1.5&tv=1'],
  ['4', '多頭排列＋相對強勢', 'ma=3&rs20=0&f5=1&tv=3'], ['5', '價值高息', 'pe=15&dy=5&tv=0.5'], ['6', '營收高成長', 'ry=30&rc=30&rh=1&tv=1'],
  ['7', '籌碼換手', 'n5r=3&m5d=2&ma=1&tv=0.5'], ['8', '財報優於去年', 'ey=20&gmy=0&tv=0.5'],
  ['r1', '融資追價', 'm5u=10&r5=10&tv=0.5'], ['r2', '軋空觀察', 'sr=20&ma=1&tv=0.5'], ['r3', '本益比低但 EPS 下滑', 'pe=15&ed=1&tv=0.5'],
];
const SCREEN_DEFAULT = { xd: 1, xn: 1, xc: 1, o: 'tv' };
// 條件狀態 = {條件 id: 門檻, o: 排序欄, od: 'a' 遞增／'d' 遞減（省略 = 預設方向）, ps: 套用中的預設}
// 第 18 輪 F18-2：選了 KD、RSI 條件時，列今日全市場符合的檔數與比例（分母 = 有 K 或 RSI 值的股票），看得出是不是急漲急跌期
function oscShare(conds, X, cnt, st) {
  const cs = conds.filter(c => c.osc);
  if (!cs.length) return '';
  const base = X.filter(x => isNum(x.k) || isNum(x.rsi)).length;
  return `<div class="flow-note">今日全市場：${cs.map(c => { const n = cnt(c);
    return `${c.label.replace('{v}', fmt(st[c.id]))} ${fmt(n)} 檔（${base ? fmt(n / base * 100, 1) : '--'}%）`; }).join('、')}。` +
    'KD、RSI 在急漲急跌時會大量同時出現；比例比平常高很多時，多半是整體市場的波動，不是個股訊號</div>';
}
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
    // 第 27 輪 D27-03：條件與排除分開計數；收合時列出已選條件（可按 ✕ 移除）
    const nx = conds.filter(c => c.g === '排除').length, cTxt = c => { const v = st[c.id], o = Array.isArray(c.opts) && c.opts.find(x => Array.isArray(x) && x[0] === v);
      return c.label.replace('{v}', o ? o[1] : v.toLocaleString('zh-TW')); };
    const tags = conds.filter(c => c.g !== '排除').map(c => `<button class="chip" data-x="${c.id}" aria-label="移除條件">${cTxt(c)} ✕</button>`).join('');
    const chip = ([id, name], ref) => `<button class="chip${ref ? ' ref' : ''}${st.ps === id ? ' on' : ''}" data-ps="${id}"${ref ? ' title="風險檢查，不是買進訊號"' : ''}>${name}</button>`;
    $('#view').innerHTML = `<section class="sec">
      <div class="sec-h">${modeSeg('screen')}</div>
      <div class="muted small">行情 ${md(S.d)}｜法人 ${md(S.fd)}｜融資融券 上市 ${mdx(S.md.TWSE)}、上櫃 ${mdx(S.md.TPEx)}｜營收 ${Object.entries(S.rmd).sort((a, b) => b[0].localeCompare(a[0])).map(([k, n]) => `${mon(k)} ${fmt(n)} 檔`).join('、') || '--'}${revMixed(S) ? '（每月 1～10 日為公布期間，各股月份不同）' : ''}｜季報 ${Object.entries(S.fqd || {}).sort((a, b) => b[0].localeCompare(a[0])).map(([k, n]) => `${k.slice(0, 4) === S.d.slice(0, 4) ? '' : k.slice(0, 4) + ' '}Q${Number(k.slice(4))} ${fmt(n)} 檔`).join('、') || '--'}${finMixed(S) ? '（財報公布期間，各股季別不同）' : ''}</div>
      <div style="margin-top:8px">${notes}</div>
      <div class="sec-h" style="margin:8px 0 0;gap:6px"><span class="muted small">預設：</span>${SCREEN_PRESETS.filter(p => p[0][0] !== 'r').map(p => chip(p)).join('')}
        <span class="muted small">參考：</span>${SCREEN_PRESETS.filter(p => p[0][0] === 'r').map(p => chip(p, true)).join('')}</div>
      <details class="scr-panel card"${open ? ' open' : ''}><summary>條件 ${conds.length - nx} 個${nx ? `＋排除 ${nx} 個` : ''}
        <button class="chip scr-go" id="scrGo">符合 ${fmt(hits.length)} 檔 ↓</button> <button class="chip" id="scrClear">重設</button> <button class="chip" id="scrCopy">複製條件連結</button>${tags ? `<div class="scr-tags">${tags}</div>` : ''}</summary>
        ${SCREEN_GROUPS.map(g => `<div class="scr-grp"><b>${g}</b><div>${SCREEN_CONDS.filter(c => c.g === g).map(condHTML).join('')}</div></div>`).join('')}
      </details>
      ${oscShare(conds, X, cnt, st)}
      <div class="sec-h" id="scrRes" style="margin:8px 0"><h2>符合 ${fmt(hits.length)} 檔</h2>${hits.length > 100 ? `<span class="muted small">依「${oName}」排序顯示前 100 檔</span>` : ''}</div>
      <div class="card">${hits.length ? screenTable(hits.slice(0, 100), cols, { sort: o, cap: conds.some(c => c.val) })
        : '<div class="empty">沒有同時符合所有條件的股票。參考各條件的「單獨」檔數，放寬最少的那一個。</div>'}</div>
      <div class="muted small" style="margin-top:6px">篩選結果只是條件的機械比對，不是投資建議。報酬、乖離、均線、新高新低、KD、RSI 都用還原價格（除權息、減資、面額變更不會造成跳動）；量比 = 今日成交額 ÷ 前 20 個交易日平均（無成交日以 0 計），不受面額變更影響。法人金額為張數 × 收盤估算，不含 ETF；投信買超會受主動 ETF 申購影響（申購的資金會被動買進股票，個股頁「主動 ETF 持有」卡列出已收主動 ETF 占投信買超的張數）。本益比、殖利率、淨值比為官方值，90 天內有除權、減資或面額變更的股票官方值可能尚未調整，預設排除。營收條件以各股最新公布的月份判斷：每月 1～10 日是公布期間，已公布的公司當天就換成新月份，各股月份不同（營收欄會標出和欄名不同的月份）。季報條件以各股最新一季判斷：單季 EPS 由累計相減，去年同季虧損時不計算年增，金融業沒有毛利率；財報公布期間各股季別不同（欄位會標出和欄名不同的季別）。融資融券為張；融資增加率、券資比只計入融資 1,000 張以上的股票。${DV_NOTE}</div></section>`;
    keyCol($(`#view th.sort[data-k="${o}"]`)?.cellIndex);
    const changed = () => { delete st.ps; save(); draw(); };
    onModeSeg();
    $('#view').querySelectorAll('[data-ps]').forEach(b => b.addEventListener('click', () => {
      st = { ...scrParse(SCREEN_PRESETS.find(p => p[0] === b.dataset.ps)[2]), xd: 1, xn: 1, xc: 1, o: 'tv', ps: b.dataset.ps };
      open = false; save(); draw();                                        // 第 25 輪 D25-14：收合條件，結果緊接在預設鈕下方
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
    $('#scrGo').addEventListener('click', e => { e.preventDefault(); $('#scrRes').scrollIntoView(); });
    $('#view').querySelectorAll('[data-x]').forEach(b => b.addEventListener('click', e => { e.preventDefault(); delete st[b.dataset.x]; changed(); }));
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
  ['l1+', '借券增加', -1], ['l1-', '借券減少', 1], ['lb', '借券餘額', -1],     // 第 12 輪 ETF-借券
  ['r20', '含息 20 日', -1], ['r60', '含息 60 日', -1], ['ry', '含息今年以來', -1], ['rw', '含息 52 週', -1],   // 第 46 輪 F46-3
  ['dvr', '配息率', -1], ['dva', '最近除息', 1]];                                  // 第 36 輪 F36-3
// 第 36 輪 F36-3：ETF 配息欄。dvr 配息率 = 近一年配息 ÷ 收盤（%）；dva 除息至今天數（相對網站資料日，排序用）
const etfDiv = (r, d) => { r.dvr = r.dvc > 0 && r.c > 0 ? r.dvc / r.c * 100 : null; r.dva = r.dvd ? Math.round((Date.parse(d) - Date.parse(r.dvd)) / 864e5) : null; return r; };
// 第 42 輪 F42-7：今天除息（有收盤、官方漲跌為空或 0、除息日是資料日；上市除息日官方漲跌記 0 不比價，QA42-01）的漲跌欄寫「除息」，tooltip 同個股頁
const EX_TIP = '除息日的開盤參考價扣掉配息，收盤減前一日收盤會含配息';
const etfPct = (r, d) => r.c != null && !r.p && r.dvd === d ? `<td class="num flat" title="${EX_TIP}">除息</td>`
  : `<td class="num ${cls(r.ch)}">${r.c == null ? '無成交' : sgn(r.p) + '%'}</td>`;
const ETF_DIV_NOTE = '配息率 = 近一年（365 天）每單位配息合計 ÷ 今日收盤，用過去的配息，不代表未來；股價下跌時配息率會變高。最近除息的第二行：填息 = 除息當天起原始收盤回到除息前收盤，只看最近一次；上市 ETF 填息前遇到推測的其他價格調整（多為分割）標「中斷」。除息資料來自證交所、櫃買中心的除息表。';

// ETF 列（tr[data-etf]）→ ETF 個股頁；列內的「持股」小標（<a>）照舊連到持股頁。第 20 輪：ETF 列表與自選頁共用
const onEtfRow = e => { const tr = e.target.closest('tr[data-etf]'); if (tr && !e.target.closest('a,button')) location.hash = '#/stock/' + tr.dataset.etf; };

const ETF_N = 50;   // 第 30 輪 D30-04：ETF 列表預設顯示的檔數（和排行一樣）
// 第 46 輪 F46-3：ETF 列表「表現」欄組（latest.json ETF 列的 r20、r60、ry、rw = 含息報酬 %，etfs.ix = 加權指數同期 %）
const EPF_COLS = [['r20', '20', '20 日'], ['r60', '60', '60 日'], ['ry', 'y', '今年以來'], ['rw', 'w', '52 週']];
const ETF_PF_NOTE = '含息報酬（%），算法同 ETF 個股頁「近期表現（含息）」：配息在除息日以參考價再投入，不含手續費與稅；「--」= 基準日時本站還沒有這檔的成交；今天無成交時用最後成交的收盤。加權指數是價格指數，不含股息；債券、海外、槓桿／反向、期貨 ETF 和加權指數比較的意義有限。';
function etfPerfHTML(list, ix) {
  const pct = v => `<td class="num ${cls(v)}">${v == null ? '--' : sgn(v) + '%'}</td>`;
  const line = EPF_COLS.filter(([, k]) => ix && ix[k] != null).map(([, k, l]) => `${l} ${sgn(ix[k])}%`).join('、');
  return (line ? `<div class="muted small" style="margin-bottom:6px">加權指數同期：${line}（價格指數，不含股息）</div>` : '') +
    `<div class="card"><div class="tbl-wrap"><table class="tbl etf-tbl"><thead><tr><th>ETF</th><th>收盤</th>${EPF_COLS.map(c => `<th>${c[2]}</th>`).join('')}</tr></thead><tbody>` +
    list.map(([c, r]) => `<tr data-etf="${c}"><td class="nm"><b>${esc(r.n)}</b><span>${c} ${r.m === 'TWSE' ? '上市' : '上櫃'}</span>${holdTag(c)}</td>
      ${r.c == null ? '<td class="num flat">無成交</td>' : `<td class="num ${cls(r.ch)}">${pfmt(r.c)}</td>`}${EPF_COLS.map(([k]) => pct(r[k])).join('')}</tr>`).join('') +
    '</tbody></table></div></div>';
}
function renderEtf() {
  const E = App.latest.etfs;
  if (!E) {
    $('#view').innerHTML = '<div class="empty">尚無 ETF 資料：請在收集資料的電腦執行 python3 -m twstock history --start 2025-10-30 --only etf margin</div>';
    return;
  }
  const by = localStore('etfSort', 'tv'), mkt = localStore('etfMkt', 'all');
  // 第 46 輪 QA46-02：有含息報酬欄（新 latest.json）才顯示「行情／表現」欄組；舊 latest.json 時存下的含息排序改用成交額
  const hasPf = Object.values(E.rows).some(r => EPF_COLS.some(([k]) => r[k] != null)), perf = hasPf && App.etfCols === 'perf';
  const [key, , dir] = ETF_SORT.find(x => x[0] === by && (hasPf || !EPF_COLS.some(c => c[0] === x[0]))) || ETF_SORT[0];
  const f = key.replace(/[+-]$/, '');
  const list = Object.entries(E.rows).map(([c, r]) => [c, etfDiv(r, App.latest.date)]).filter(([, r]) => mkt === 'all' || r.m === mkt)
    .sort((a, b) => (a[1][f] == null) - (b[1][f] == null) || dir * ((a[1][f] ?? 0) - (b[1][f] ?? 0)));
  const lots = v => `<td class="num ${cls(v)}">${v == null ? '--' : sgn(v, 0)}</td>`;
  const dates = Object.entries(E.dates).map(([m, d]) => `${m === 'TWSE' ? '上市' : '上櫃'} ${md(d)}`).join('　');
  // 第 46 輪 F46-3：欄組只記在這次瀏覽（App.etfCols），「行情」輸出不變
  const head = `<div class="sec-h"><h2>ETF</h2><span class="muted small">${dates}</span>${App.latest.active_rank ? '<a class="pill hold" href="#/etf/active">主動 ETF 彙總</a>' : ''}<span class="sp"></span>
        ${segHTML('etfMktSeg', [['all', '全部'], ['TWSE', '上市'], ['TPEx', '上櫃']], mkt)}
        <input id="etfQ" class="sel" type="search" placeholder="篩選代號或名稱" aria-label="篩選 ETF" value="${esc(App.etfQ || '')}">
        <select id="etfSel" class="sel" aria-label="排序">${ETF_SORT.filter(x => hasPf || !EPF_COLS.some(c => c[0] === x[0])).map(x => `<option value="${x[0]}"${x[0] === by ? ' selected' : ''}>${x[1]}</option>`).join('')}</select>${hasPf ? segHTML('etfColSeg', [['flow', '行情'], ['perf', '表現']], perf ? 'perf' : 'flow') : ''}</div>`;
  const more = list.length > ETF_N ? `<button class="chip" id="etfMore" style="margin-top:8px">${App.etfAll ? `只顯示前 ${ETF_N} 檔` : `顯示全部 ${list.length} 檔`}</button>` : '';
  if (perf) $('#view').innerHTML = `<section class="sec">
      ${head}
      ${etfPerfHTML(list, E.ix)}
      ${more}
      <div class="muted small" style="margin-top:6px">共 ${list.length} 檔。${ETF_PF_NOTE}</div></section>`;
  else $('#view').innerHTML = `<section class="sec">
      ${head}
      <div class="card"><div class="tbl-wrap"><table class="tbl etf-tbl"><thead><tr>
        <th>ETF</th><th>收盤</th><th>漲跌</th><th>成交量</th><th>成交額</th><th>融資餘額</th><th>融資增減</th><th>融券餘額</th><th>融券增減</th><th>借券餘額</th><th>借券增減</th><th>近一年配息</th><th>配息率</th><th>最近除息</th></tr></thead><tbody>` +
      list.map(([c, r]) => `<tr data-etf="${c}"><td class="nm"><b>${esc(r.n)}</b><span>${c} ${r.m === 'TWSE' ? '上市' : '上櫃'}</span>${holdTag(c)}</td>
        <td class="num ${cls(r.ch)}">${pfmt(r.c)}</td>
        ${etfPct(r, App.latest.date)}
        <td class="num">${fmt(r.v)}</td><td class="num">${fmt(r.tv, 2)}億</td>
        <td class="num">${r.mb == null ? '--' : fmt(r.mb)}</td>${lots(r.m1)}
        <td class="num">${r.sb == null ? '--' : fmt(r.sb)}</td>${lots(r.s1)}
        <td class="num">${r.lb == null ? '--' : fmt(r.lb)}</td>${lots(r.l1)}
        <td class="num">${r.dvc == null ? '--' : r.dvc.toLocaleString('zh-TW', { maximumFractionDigits: 4 })}</td><td class="num">${r.dvr == null ? '--' : fmt(r.dvr, 2) + '%'}</td>
        <td class="num">${r.dvd ? md(r.dvd) + `<span class="sub2">${r.dvn != null ? r.dvn + ' 天填息' : r.dvx ? '中斷' : '未填息'}</span>` : '--'}</td></tr>`).join('') +
      `</tbody></table></div></div>
      ${more}
      <div class="muted small" style="margin-top:6px">共 ${list.length} 檔。成交量為張、成交額為億元；融資融券為張，增減 = 今日餘額 − 前日餘額，「--」表示不在信用交易清單。借券為借券賣出（張，資料晚上 8 點半以後更新），多為造市、套利與避險，不等於看空。ETF 不計入首頁家數、成交額、類股資金流、排行與股票口徑的融資融券。${ETF_DIV_NOTE}</div></section>`;
  if (perf) keyCol({ r20: 2, r60: 3, ry: 4, rw: 5 }[f]);                    // 第 46 輪 F46-3：「表現」只移含息欄；行情的兩行不作用在表現表
  else {
    keyCol({ tv: 4, p: 2, m1: 6, s1: 8, l1: 10, lb: 9 }[f]);
    keyCol({ dvr: 12, dva: 13 }[f]);                                           // 第 36 輪 F36-3
  }
  $('#etfSel').addEventListener('change', e => { localStore('etfSort', null, e.target.value); renderEtf(); });
  onSeg('etfMktSeg', v => { localStore('etfMkt', null, v); renderEtf(); });
  if (hasPf) onSeg('etfColSeg', v => { App.etfCols = v; renderEtf(); });
  const etfQ = () => { const q = (App.etfQ = $('#etfQ').value.trim()).toLowerCase();   // 第 25 輪 D25-15：只隱藏列，不重畫
    // 第 30 輪 D30-04：沒有篩選字時只顯示前 ETF_N 檔（「顯示全部」後全列）；有篩選字時在全部 ETF 中找
    $('#view').querySelectorAll('tr[data-etf]').forEach((tr, i) => { tr.hidden = q ? !(tr.dataset.etf.toLowerCase() + tr.cells[0].textContent.toLowerCase()).includes(q) : !App.etfAll && i >= ETF_N; });
    if ($('#etfMore')) $('#etfMore').hidden = !!q; };
  $('#etfQ').addEventListener('input', etfQ); etfQ();
  $('#etfMore')?.addEventListener('click', () => { App.etfAll = !App.etfAll; $('#etfMore').textContent = App.etfAll ? `只顯示前 ${ETF_N} 檔` : `顯示全部 ${list.length} 檔`; etfQ(); });
  // 第 15 輪 F15-2：整列 → ETF 個股頁；列內的「持股」小標（<a>）照舊連到持股頁
  $('#view').addEventListener('click', onEtfRow);
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
  return `<details class="note"><summary>各檔單位數 1 日<i>展開</i></summary><div class="small num" style="margin-top:4px">單位數 1 日：${part(cur)}${other.length ? `；跨境（${od}）：${part(other)}` : ''}</div></details>
    <div class="muted small">單位數增加 = 淨申購。申購的資金會由經理人買進股票，所以多檔單位數同時增加的日子，「合計加碼」會偏多，不全是看好。</div>`;
}

// 今日頁小卡：買超、賣超各 5 名
function activeCard(R) {
  if (!R || !R.etfs.length) return '';
  const tbl = (t, list) => `<div class="card"><div class="sec-h"><h2>${t}</h2><span class="muted small">億，估算</span></div>
    <div class="tbl-wrap"><table class="tbl"><thead><tr><th>股票</th><th>估算金額</th><th>張數</th></tr></thead><tbody>${actRows(list.slice(0, 5)) ||
    '<tr><td colspan="3" class="muted">無</td></tr>'}</tbody></table></div></div>`;
  const top = R.etfs.map(x => x.d).sort().pop(), old = R.etfs.filter(x => x.d !== top);   // 第 27 輪 D27-10：各檔持股日可能不同
  return `<section class="sec"><div class="sec-h"><h2>${actTitle(R)}主動 ETF 一起買了什麼</h2><span class="muted small">${R.etfs.length} 檔合計，持股日 ${md(top)}${old.length ? `（${old.length} 檔 ${[...new Set(old.map(x => md(x.d)))].join('、')}）` : ''}</span>
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
  if (!H && App.latest.etfs?.rows?.[code]) { location.replace('#/stock/' + code); return; }     // 第 15 輪 F15-2：沒有持股資料的 ETF 改看 ETF 個股頁
  if (!H) { document.title = 'ETF｜台股資金流'; $('#view').innerHTML = `<div class="empty">找不到 ${esc(code)} 的資料。可用上方搜尋框查代號或名稱，或<a href="#/etf" style="color:var(--blue)">回 ETF 列表</a></div>`; return; }   // 第 28 輪 D28-08：不是 ETF 代號
  const S = H.sum, by = localStore('holdSort', 'pw'), unit = r => r.tw ? '張' : '股';
  const rows = [...H.rows].sort((a, b) => (b[by] ?? -Infinity) - (a[by] ?? -Infinity));
  const prev = H.dates.at(-2), d5 = H.dates.length > 5 ? H.dates.at(-6) : null;
  const chg = (v, d = 0) => `<td class="num ${cls(v)}">${v == null ? '--' : sgn(v, d)}</td>`;
  const name = r => r.tw ? `<b>${esc(r.n)}</b><span>${esc(r.c)}</span>` : `<b>${esc(r.n)}</b><span>${esc(r.c)}（海外）</span>`;
  $('#view').innerHTML = `<section class="sec card">
      <div class="sec-h"><h2>${esc(H.n)}</h2><span class="muted small">${code}　${H.m === 'TWSE' ? '上市' : '上櫃'}　持股日 ${md(S.d)}${H.delay ? '（跨境，晚一個交易日公布）' : ''}</span>
        <span class="sp"></span><a class="muted small" href="#/stock/${code}">行情 →</a>　<a class="muted small" href="#/etf">← ETF 列表</a></div>
      <div class="grid g-stats">
        ${[['淨資產', fmt(S.nav, 1) + ' 億'], ['每單位淨值', fmt(S.nu, 2) + ' 元', S.pm == null ? '' : `${md(S.d)} 收盤 ${fmt(S.pc, 2)}，${S.pm > 0 ? '溢價' : S.pm < 0 ? '折價' : '折溢價'} ${fmt(Math.abs(S.pm), 2)}%`], ['股票權重合計', fmt(S.sw, 2) + '%'], ['持股檔數', fmt(S.n) + ' 檔'],
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
        本基金為現金申購買回：申購進來的資金由經理人買進股票，所以<b>申購多的日子加碼會偏多</b>、贖回多的日子減碼會偏多。${S.u1 == null ? '' : `${S.d === App.latest.date ? '今天' : md(S.d) + ' '}單位數 1 日 ${sgn(S.u1)}%，張數增幅接近這個比例的持股，多半是跟著申購買進；明顯超過的才比較像經理人的判斷。`}權重變化另含股價漲跌的影響（張數不變、權重也會變）。標「新」= 前一持股日沒有持有。${S.pm == null ? '' : '折溢價 = 持股日收盤 ÷ 每單位淨值 − 1，正值為溢價、負值為折價；每單位淨值只有兩位小數，折溢價可能有約 0.1 個百分點的誤差。跨境 ETF 的淨值晚一個交易日公布，比的是同一個持股日的收盤。'}</div></section>`;
  onSeg('holdSeg', v => { localStore('holdSort', null, v); renderHoldings(code); });
  $('#view').addEventListener('click', onRowClick);
}

function renderWatch() {
  const S = App.latest.stocks, span = localStore('rspan', '1'), R = App.latest.etfs?.rows || {};
  const list = [...App.watch].filter(c => S[c]).map(c => [c, S[c]]);
  const etfs = [...App.watch].filter(c => !S[c] && R[c]).map(c => [c, R[c]]);     // 第 20 輪 F20-1：自選的 ETF 另列一張表
  const stk = list.length || !etfs.length;                                         // 只有 ETF 時不顯示股票表與 1 日／5 日
  const ev = list.filter(([, s]) => s.hl || s.dsp || s.ntc);                        // 第 25 輪 D25-09：自選股的近期新訊號、處置／注意
  const wc = App.screen === null && list.length ? 'flow' : App.watchCols || 'flow';   // 第 32 輪 F32-1：欄位組只記在這次瀏覽；screen.json 不存在時只有資金（只有 ETF 時照樣可選持股）
  const HV = wc === 'hold' && (list.length || etfs.length) ? holdView() : null;    // 第 42 輪 F42-1：持股欄組（不載入 screen.json）
  const pf = Object.values(R).some(r => r.r20 != null || r.r60 != null || r.ry != null || r.rw != null), ep = pf && wc === 'perf';   // 第 47 輪 F47-6：同 ETF 列表 hasPf（EPF_COLS 的鍵）
  $('#view').innerHTML = `<section class="sec watch${App.watchEdit ? ' editing' : ''}">
      ${App.watchAdd ? watchAddNote(S, R) : ''}${App.watchShare ? `<div class="flow-note">${App.watchShare.ok ? '已複製分享連結。' : '請複製這個連結，'}在另一台裝置開啟，確認後會加入那裡的自選。<input class="w-url" readonly value="${esc(App.watchShare.url)}"></div>` : ''}
      ${App.watchUndo ? `<div class="flow-note">已從自選移除 ${esc(App.watchUndo.filter(c => !App.watch.has(c)).map(c => (S[c] || R[c])?.n || c).join('、'))}　<button class="chip" id="watchUndo">復原</button></div>` : ''}
      <div class="sec-h">${stk ? '<h2>自選</h2>' : '<h2>自選 ETF</h2>'}<span class="muted small">存在這個瀏覽器裡，換裝置不會同步${stk || HV || ep ? '' : '。當日行情；成交量為張、成交額為億元'}</span><span class="sp"></span>${list.length ? App.screen === null ? '<span class="muted small">表現、基本面資料尚未產生</span>' : segHTML('wcolSeg', [['flow', '資金'], ['perf', '表現'], ['fund', '基本面'], ['hold', '持股']], wc) : etfs.length ? segHTML('wcolSeg', [['flow', '行情'], ...pf ? [['perf', '表現']] : [], ['hold', '持股']], HV ? 'hold' : ep ? 'perf' : 'flow') : ''}${stk && !list.length ? spanSeg(span) : ''}${list.length || etfs.length ? `<button class="chip" id="watchEdit">${App.watchEdit ? '完成' : '編輯'}</button><button class="chip" id="watchShare">分享清單</button>` : ''}</div>
      ${stk ? `<div class="card">${list.length ? HV ? holdCap(HV, App.latest) + holdTable(HV.s, false, HV) : wc === 'flow' ? stockTable(list, span, true) : watchColTable(list, wc)
        : '<div class="empty">還沒有自選股。打開任一檔個股或 ETF，按名稱旁的「☆ 加入自選」；或在上方搜尋，按清單右側的 ☆ 直接加入。<div style="margin-top:10px"><button class="chip" id="watchFind">搜尋股票</button></div></div>'}</div>` : ''}
      ${etfs.length ? `${stk ? '<div class="sec-h" style="margin-top:12px"><h2>ETF</h2>' + (HV || ep ? '' : '<span class="muted small">當日行情；成交量為張、成交額為億元</span>') + '</div>' : ''}
      <div class="card">${HV ? (list.length ? '' : holdCap(HV, App.latest)) + holdTable(HV.e, true, HV) : ep ? etfWatchPerf(etfs, App.latest.etfs.ix) : etfWatchTable(etfs)}</div>` : ''}${App.latest.nx ? watchNx() : ''}
      ${ev.length ? `<div class="card w-ev"><div class="sec-h"><h2>近期新訊號、處置／注意</h2><span class="muted small">只描述發生了什麼，不代表之後的走勢</span></div>${ev.map(([c, s]) => {
        const d = s.dsp, r = s.ntc && App.latest.alerts?.n?.find(x => x[0] === c)?.[1];   // 第 27 輪 D27-08：處置期間（最後一天加註）、注意原因
        return `<a class="al-row" href="#/stock/${c}"><b>${esc(s.n)}</b>${alertBadge(s)}${d ? `　<span class="small num">${d[0] > App.latest.date ? '即將處置' : '處置'} ${md(d[0])}～${md(d[1])}${d[1] === App.latest.date ? '（最後一天）' : ''}</span>` : ''}` +
          `　${s.hl ? s.hl.filter(e => HL_KINDS[e[0]]).map(hlTag).join('') : ''}${r ? `<div class="muted small al-why">注意：${esc(r)}</div>` : ''}</a>`; }).join('')}</div>` : ''}
      ${list.length || etfs.length ? '<div class="muted small w-tip">按「✕」從自選移除；按住「≡」上下拖曳調整順序（也可按上下鍵）。完成後按「完成」</div>' : ''}</section>`;
  if ($('#rspanSeg')) onSeg('rspanSeg', v => { localStore('rspan', null, v); renderWatch(); });
  if ($('#wcolSeg')) onSeg('wcolSeg', v => { App.watchCols = v; renderWatch(); });
  $('#watchShare')?.addEventListener('click', () => shareWatch());
  $('#watchAddOk')?.addEventListener('click', () => { watchAddList(S, R).add.forEach(c => App.watch.add(c)); saveWatch(); App.watchAdd = null; renderWatch(); });
  $('#watchAddNo')?.addEventListener('click', () => { App.watchAdd = null; renderWatch(); });
  watchGestures($('#view .watch'));
  if (HV) holdWire($('#view .watch'));
  $('#watchFind')?.addEventListener('click', () => $('#q').focus());
  $('#view').addEventListener('click', onRowClick);
  $('#view').addEventListener('click', onEtfRow);
}
// 第 32 輪 F32-1：自選頁的「表現」「基本面」欄位組（沿用選股結果表的欄位定義；screen.json 第一次用到時才載入）
const WATCH_COLS = { perf: ['r5', 'r20', 'r60', 'hd', 'b20'], fund: ['ry', 'ey', 'pe', 'dy', 'pbp'] };
function watchColTable(list, wc) {
  const S = App.screen;
  if (!S) { loadScreen().then(() => location.hash === '#/watch' && renderWatch()); return '<div class="empty">載入中…</div>'; }
  return `<div class="muted small tbl-cap">${wc === 'perf' ? `報酬、乖離為 ${md(S.d)} 收盤；距 52 週高 = (52 週高 − 收盤) ÷ 52 週高`
    : '營收、EPS 為各股最新一期，和欄名的月份、季別不同時另外標示；淨值比位置 = 目前淨值比在近一年高低之間的位置（0% 最低）'}</div>` +
    screenTable(list.map(([c, s]) => screenRow(c, s, S)), WATCH_COLS[wc], { rm: true, cap: wc === 'fund' });
}
// 第 32 輪 F32-2：分享連結只帶代號；去重、最多 200 個，只加入認得且還不在自選的（接在後面）
function watchAddList(S, R) {
  const A = [...new Set(App.watchAdd.filter(Boolean).map(c => c.toUpperCase()))], B = A.slice(0, 200);
  const ok = B.filter(c => /^[0-9A-Z]{4,6}$/.test(c) && (S[c] || R[c]));
  return { more: A.length > 200, ok, add: ok.filter(c => !App.watch.has(c)), bad: B.filter(c => !ok.includes(c)) };
}
function watchAddNote(S, R) {
  const { more, ok, add, bad } = watchAddList(S, R), nm = c => esc((S[c] || R[c]).n);
  return `<div class="flow-note">${add.length ? `要把以下 ${add.length} 檔加入自選嗎？${add.map(nm).join('、')}　<button class="chip" id="watchAddOk">加入</button> <button class="chip" id="watchAddNo">取消</button>`
    : `分享連結裡沒有可以加入的股票。　<button class="chip" id="watchAddNo">關閉</button>`}` +
    (ok.length > add.length ? `<div class="muted small">${ok.length - add.length} 檔已在自選</div>` : '') +
    (bad.length ? `<div class="muted small">略過 ${bad.length} 個不認得的代號：${esc(bad.slice(0, 10).map(c => c.slice(0, 12)).join('、'))}${bad.length > 10 ? '…' : ''}</div>` : '') +
    (more ? '<div class="muted small">連結超過 200 個代號，只讀前 200 個</div>' : '') + '</div>';
}
// 有系統分享時用系統分享（取消就不顯示）；否則複製到剪貼簿；都不行時顯示連結讓使用者自己複製
async function shareWatch() {
  const S = App.latest.stocks, R = App.latest.etfs?.rows || {};
  const url = location.href.split('#')[0] + '#/watch?add=' + [...App.watch].filter(c => S[c] || R[c]).join(',');
  let ok = false;
  try {
    if (navigator.share) { await navigator.share({ title: '自選清單', url }); return; }
    await navigator.clipboard.writeText(url); ok = true;
  } catch (e) { if (e.name === 'AbortError') return; }
  App.watchShare = { url, ok };
  renderWatch();
}
// 自選頁每列：「✕」移除（走 onRowClick 的 data-unwatch，可復原）、「≡」拖曳排序；兩顆鈕只在編輯模式顯示
const wCtl = c => `<button class="wdel" data-unwatch="${c}" title="從自選移除" aria-label="從自選移除">✕</button><button class="wh" data-drag="${c}" title="拖曳調整順序（也可按上下鍵）" aria-label="調整順序">≡</button>`;
// 依表格目前的列序存回自選順序：股票表的代號排在前，ETF 表的排在後（兩張表分開顯示，互不影響）
function saveWatchOrder(tb) {
  const codes = [...tb.rows].map(r => r.dataset.code || r.dataset.etf), rest = [...App.watch].filter(c => !codes.includes(c));
  App.watch = new Set(tb.rows[0]?.dataset.code ? [...codes, ...rest] : [...rest, ...codes]);
  saveWatch();
}
// 監聽掛在每次重畫的 section 上（不掛 #view，避免累積）
function watchGestures(sec) {
  if (!sec) return;
  $('#watchEdit')?.addEventListener('click', e => {
    App.watchEdit = sec.classList.toggle('editing');
    e.currentTarget.textContent = App.watchEdit ? '完成' : '編輯';
  });
  // 編輯模式：點表格列不進個股頁（「✕」照常交給 onRowClick）
  sec.addEventListener('click', e => {
    if (sec.classList.contains('editing') && e.target.closest('tbody tr') && !e.target.closest('.wdel')) { e.stopPropagation(); e.preventDefault(); }
  }, true);
  // 換位的相鄰列從原位置滑到新位置（FLIP）
  const flip = (s, move) => {
    const y = s.offsetTop;
    move();
    const d = y - s.offsetTop;
    if (d) s.querySelectorAll('td').forEach(td => td.animate?.([{ transform: `translateY(${d}px)` }, { transform: 'none' }], { duration: 160, easing: 'ease-out' }));
  };
  sec.querySelectorAll('.wh').forEach(h => {
    const tr = h.closest('tr'), tb = tr.parentElement;
    let y0 = 0, top0 = 0, cy = 0, raf = 0;   // y0 用頁面座標（含捲動量）：拖到邊緣自動捲動時，列仍跟著手指
    const move = () => {
      const c = top0 + cy + scrollY - y0 + tr.offsetHeight / 2, mid = r => r.offsetTop + r.offsetHeight / 2;
      let s;            // 搬動相鄰列、不搬被拖的列（被拖的列離開 DOM 會失去 pointer capture）；一次移動很遠時連跳多列
      while ((s = tr.previousElementSibling) && c < mid(s)) flip(s, () => tr.after(s));
      while ((s = tr.nextElementSibling) && c > mid(s)) flip(s, () => tr.before(s));
      tr.style.setProperty('--dy', `${top0 + cy + scrollY - y0 - tr.offsetTop}px`);   // 被拖的列跟著手指走
    };
    // 第 27 輪 D27-09：手指在畫面上下 90px 內時自動捲動（底部有選單、頂部有頂欄）
    const edge = () => { const v = cy < 90 ? -10 : cy > innerHeight - 90 ? 10 : 0;
      raf = v && tr.classList.contains('dragging') ? (scrollBy(0, v), move(), requestAnimationFrame(edge)) : 0; };
    h.addEventListener('pointerdown', e => {
      e.preventDefault(); h.setPointerCapture(e.pointerId);
      cy = e.clientY; y0 = cy + scrollY; top0 = tr.offsetTop;
      tr.classList.add('dragging');
    });
    h.addEventListener('pointermove', e => {
      if (!tr.classList.contains('dragging')) return;
      cy = e.clientY; move();
      if (!raf) edge();
    });
    const end = () => {
      if (!tr.classList.contains('dragging')) return;
      cancelAnimationFrame(raf); raf = 0;
      const d = parseFloat(tr.style.getPropertyValue('--dy')) || 0;
      tr.classList.remove('dragging'); tr.style.removeProperty('--dy');
      if (d) tr.querySelectorAll('td').forEach(td => td.animate?.([{ transform: `translateY(${d}px)` }, { transform: 'none' }], { duration: 160, easing: 'ease-out' }));   // 放開後落回定位
      saveWatchOrder(tb);
    };
    ['pointerup', 'pointercancel', 'lostpointercapture'].forEach(t => h.addEventListener(t, end));
    h.addEventListener('keydown', e => {
      const s = e.key === 'ArrowUp' ? tr.previousElementSibling : e.key === 'ArrowDown' ? tr.nextElementSibling : null;
      if (!s) return;
      e.preventDefault();
      flip(s, () => e.key === 'ArrowUp' ? tr.after(s) : tr.before(s));
      saveWatchOrder(tb);
    });
  });
}
// 第 20 輪 F20-1：自選頁的 ETF 表（ETF 列表的前 4 欄，資料為 latest.etfs.rows）
function etfWatchTable(list) {
  return '<div class="tbl-wrap"><table class="tbl"><thead><tr><th>ETF</th><th>收盤</th><th>漲跌</th><th>成交量</th><th>成交額</th><th>近一年配息</th><th>配息率</th><th>最近除息</th></tr></thead><tbody>' +
    list.map(([c, r]) => `<tr data-etf="${c}"><td class="nm">${wCtl(c)}<b>${esc(r.n)}</b><span>${c} ${r.m === 'TWSE' ? '上市' : '上櫃'}</span>${holdTag(c)}</td>
      <td class="num ${cls(r.ch)}">${pfmt(r.c)}</td>${r.c != null && !r.p && r.dvd === App.latest.date ? '<td class="num flat" title="除息日的開盤參考價扣掉配息，收盤減前一日收盤會含配息">除息</td>'
        : `<td class="num ${cls(r.ch)}">${r.c == null ? '無成交' : sgn(r.p) + '%'}</td>`}
      <td class="num">${fmt(r.v)}</td><td class="num">${fmt(r.tv, 2)}億</td>
      <td class="num">${r.dvc == null ? '--' : r.dvc.toLocaleString('zh-TW', { maximumFractionDigits: 4 })}</td><td class="num">${r.dvc > 0 && r.c > 0 ? fmt(r.dvc / r.c * 100, 2) + '%' : '--'}</td>
      <td class="num">${r.dvd ? md(r.dvd) + `<span class="sub2">${r.dvn != null ? r.dvn + ' 天填息' : r.dvx ? '中斷' : '未填息'}</span>` : '--'}</td></tr>`).join('') + '</tbody></table></div>' +
    '<div class="muted small h-note">配息率 = 近一年配息 ÷ 今日收盤，股價下跌時會變高；最近除息的第二行是填息狀態，算法同 ETF 列表。</div>';   // 第 42 輪 F42-5
}
// 第 47 輪 F47-6：自選 ETF 表「表現」（含息報酬；欄位、加權同期同 ETF 列表的 EPF_COLS）
function etfWatchPerf(list, ix) {
  const line = EPF_COLS.filter(([, k]) => ix && ix[k] != null).map(([, k, l]) => `${l} ${sgn(ix[k])}%`).join('、');
  const nm = (c, r) => `${wCtl(c)}<b>${esc(r.n)}</b><span>${c} ${r.m === 'TWSE' ? '上市' : '上櫃'}</span>${holdTag(c)}`;   // 名稱欄同 etfWatchTable
  return `<div class="muted small tbl-cap">含息報酬為 ${md(App.latest.date)} 收盤${line ? `；加權指數同期：${line}（價格指數，不含股息）` : ''}</div>` +
    `<div class="tbl-wrap"><table class="tbl"><thead><tr><th>ETF</th><th>收盤</th>${EPF_COLS.map(c => `<th>${c[2]}</th>`).join('')}</tr></thead><tbody>` +
    list.map(([c, r]) => `<tr data-etf="${c}"><td class="nm">${nm(c, r)}</td>` +
      (r.c == null ? `<td class="num flat">無成交</td>` : `<td class="num ${cls(r.ch)}">${pfmt(r.c)}</td>`) +
      EPF_COLS.map(([k]) => `<td class="num ${cls(r[k])}">${r[k] == null ? '--' : sgn(r[k]) + '%'}</td>`).join('') + '</tr>').join('') + '</tbody></table></div>' +
    '<div class="muted small h-note">含息報酬 = 配息在除息日以參考價再投入同一檔，算法同 ETF 列表「表現」，不含手續費與稅' +   // 分兩段：test_iter46 的反證要 ETF_PF_NOTE 那句在 app.js 只出現一次
      '；「--」= 基準日時本站還沒有這檔的成交；今天無成交時用最後成交的收盤。加權指數是價格指數，不含股息。</div>';
}
// 第 47 輪 F47-1c：自選頁「即將除權息」卡（latest.nx = {代號: [日期, 類型, 現金]}；依除權息日、同日依自選順序）。沒有就輸出空字串
// 估計可領（R60）= 股數 × 預告每股現金，BigInt 整數運算、元以下捨去（0.29 × 100 用浮點會變 28）；現金超過 8 位小數不估計
const nxKind = t => t === '息' ? '除息' : t === '權' ? '除權' : '除權息';   // 同 stock.js nxText
function watchNx() {
  const L = App.latest, NX = L.nx || {}, R = (L.etfs && L.etfs.rows) || {};
  const W = [...App.watch].filter(c => NX[c] && (L.stocks[c] || R[c])).sort((a, b) => NX[a][0] < NX[b][0] ? -1 : NX[a][0] > NX[b][0] ? 1 : 0);
  if (!W.length) return '';
  const H = holdLoad();
  return '<div class="card w-nx"><div class="sec-h"><h2>即將除權息</h2><span class="muted small">預告，以公司或發行人公告為準</span></div>' + W.map(c => {
    const [d, t, x] = NX[c], q = x > 0 && H[c] ? tlBig(String(x), 8) : null;
    return `<div class="al-row"><a href="#/stock/${c}"><b>${esc((L.stocks[c] || R[c]).n)}</b></a>　<span class="nw">${md(d)} ${nxKind(t)}</span>` +
      (x == null ? '　<span class="nw">金額待公告</span>' : x > 0 ? `　<span class="nw">${L.stocks[c] ? '現金股利' : '配息'} ${dfmt(x, 8)} 元</span>` : '') +
      (q == null ? '' : `　<span class="nw">估計可領 ${fmt(Number(BigInt(H[c][0]) * q / 10n ** 8n))} 元</span>`) + `　<a class="small" href="#/tools/dv?c=${c}">試算 →</a></div>`; }).join('') +
    '<div class="muted small">來自證交所、櫃買中心的除權除息預告表，只列資料日之後的下一次；除權息日當天起改看個股頁的股利卡。估計可領 = 持股股數 × 預告每股現金，元以下捨去；未扣二代健保補充保費與匯費，配股不估算股數，以實際入帳為準。</div></div>';
}
// 第 42 輪 F42-1：持股（tw.hold = {代號: [股數, 平均成本（分）]}）。只存在這個瀏覽器，不放進任何網址、不送出（R40）
// 讀取時丟掉壞的筆；不在自選（也不在這次可復原的移除）裡的代號一併刪掉並寫回
function holdLoad() {
  const raw = localStore('hold', null), H = {}, keep = c => App.watch.has(c) || (App.watchUndo || []).includes(c);
  let o = null;
  try { o = JSON.parse(raw); } catch (e) { /* 壞值當作沒有存 */ }
  if (o && typeof o === 'object' && !Array.isArray(o)) Object.keys(o).forEach(c => { const v = o[c];
    if (/^[0-9A-Z]{4,6}$/.test(c) && keep(c) && Array.isArray(v) && v.length === 2 && v.every(Number.isSafeInteger) && v[0] >= 1 && v[0] < 1e12 && v[1] >= 1 && v[1] < 1e14) H[c] = v; });
  if (raw != null && JSON.stringify(H) !== raw) holdSave(H);
  return H;
}
function holdSave(H) { const s = JSON.stringify(H); localStore('hold', null, s); return localStore('hold', null) === s; }   // 寫入後讀回比對（私密視窗會失敗）
// R41 以收盤全部出售試算：呼叫 tools.js 的 tlSell（整股、零股各自套最低手續費、各自捨去證交稅）；金額為分（BigInt），手續費與證交稅為元
// D110 = A：股票 0.3%、名稱 -DR 結尾的存託憑證 0.1%、ETF 0.1%、代號 B 結尾的債券 ETF 停徵（tlTax 的期限，過期只提醒）
const holdKind = (c, x, e) => e ? (/B$/.test(c) ? 'b' : 'e') : /-DR$/.test(x.n) ? 'e' : 's';
function holdCalc(L, codes, H, fee, today) {
  const f = tlFeePref(fee), o = { dz: Math.round(f.d * 100), m: +f.m, mo: 1 }, R = (L.etfs && L.etfs.rows) || {};
  const row = (c, x, e) => { const h = H[c], P = x.c == null ? null : Math.round(x.c * 100);
    if (!h || P == null) return { c, x, e, h, dt: h && '無成交' };
    const kd = holdKind(c, x, e), S = tlSell(P, h[0], Object.assign({ r: tlTax(kd, false, today).r }, o)), T = BigInt(h[0]) * BigInt(h[1]);
    const dt = e ? (!x.p && x.dvd === L.date ? '除息' : x.ch == null ? '--' : '') : x.nt ? '無成交' : x.ch == null ? '--' : '';
    return { c, x, e, h, kd, v: S.sa, T, u: S.net - T, f: S.f, tx: S.x, dt, d: dt ? null : BigInt(Math.round(x.ch * 100)) * BigInt(h[0]) }; };
  const s = codes.filter(c => L.stocks[c]).map(c => row(c, L.stocks[c], false)), e = codes.filter(c => !L.stocks[c] && R[c]).map(c => row(c, R[c], true));
  return { f, today, s: { rows: s, sum: holdSum(s) }, e: { rows: e, sum: holdSum(e) }, all: holdSum(s.concat(e)) };
}
// 合計只算有持股且有收盤的列；今日損益是無成交、除息、-- 的列不加，k = 這些列的檔數
const holdSum = a => a.filter(x => x.v != null).reduce((S, x) => ({ n: S.n + 1, v: S.v + x.v, u: S.u + x.u, t: S.t + x.T,
  k: S.k + (x.d == null ? 1 : 0), d: S.d + (x.d == null ? 0n : x.d) }), { n: 0, k: 0, v: 0n, d: 0n, u: 0n, t: 0n });
const holdView = () => holdCalc(App.latest, [...App.watch], holdLoad(), localStore('fee', null), tlToday());
const holdY = X => { const n = Number(X); return tlS(n / 100, n % 100 ? 2 : 0); };   // 分 → 帶正負號的元，有角分時 2 位小數
const holdP = (U, T) => tlS(Number(U) / Number(T) * 100, 2) + '%';
const holdTd = (X, t) => `<td class="num ${cls(Number(X))}">${t}</td>`;
const holdQ = x => x.h ? fmt(x.h[0]) : `<button class="chip h-fill" data-hfill="${x.c}">填入</button>`;
const holdK = x => x.h ? fmt(x.h[1] / 100, 2) : '--';
const holdIn = (x, k) => `<input class="h-in" data-h${k}="${x.c}" inputmode="${k === 'q' ? 'numeric' : 'decimal'}" autocomplete="off" placeholder="${k === 'q' ? '股數' : '平均成本'}" aria-label="${esc(x.x.n)} ${k === 'q' ? '股數' : '平均成本'}" value="${!x.h ? '' : k === 'q' ? x.h[0] : Math.floor(x.h[1] / 100) + '.' + String(x.h[1] % 100).padStart(2, '0')}">`;
// 第 5～8 欄：市值、今日損益、未實現損益、報酬率
function holdTds(x) {
  if (x.v == null) return `<td class="num">--</td><td class="num${x.dt ? ' flat' : ''}">${x.dt || '--'}</td><td class="num">--</td><td class="num">--</td>`;
  return `<td class="num">${tlY(Number(x.v))}</td>` + (x.dt ? `<td class="num flat"${x.dt === '除息' ? ` title="${EX_TIP}"` : ''}>${x.dt}</td>` : holdTd(x.d, holdY(x.d))) +
    holdTd(x.u, holdY(x.u)) + holdTd(x.u, holdP(x.u, x.T));
}
const holdFoot = S => !S.n ? '' : `<tr><td class="nm"><b>合計</b><span>${S.n} 檔</span></td><td></td><td></td><td></td><td class="num">${tlY(Number(S.v))}</td>` +
  `<td class="num ${cls(Number(S.d))}">${holdY(S.d)}${S.k ? `<span class="sub2">不含 ${S.k} 檔</span>` : ''}</td>${holdTd(S.u, holdY(S.u))}${holdTd(S.u, holdP(S.u, S.t))}</tr>`;
const holdAll = V => !V.s.sum.n || !V.e.sum.n ? '' : `全部持股（股票＋ETF）　市值 ${tlY(Number(V.all.v))} 元　今日損益 <span class="${cls(Number(V.all.d))}">${holdY(V.all.d)}</span> 元　` +
  `未實現損益 <span class="${cls(Number(V.all.u))}">${holdY(V.all.u)}</span> 元（<span class="${cls(Number(V.all.u))}">${holdP(V.all.u, V.all.t)}</span>）`;
function holdCap(V, L) {
  const x = V.s.rows.concat(V.e.rows).filter(r => r.h), b = tlTax('b', false, V.today);
  return '<div class="muted small tbl-cap h-cap">' + [!x.length && '還沒有填持股。按「編輯」或各列的「填入」，輸入股數與平均成本。',
    `以 ${md(L.date)} 收盤全部出售試算，已扣出售手續費與證交稅（手續費 ${pfmt(V.f.d)} 折、整股最低 ${fmt(V.f.m)} 元、零股最低 1 元；折扣與整股最低值取自「工具 › 交易成本」）。今日損益 = 股數 × 今日漲跌，不含手續費與稅。金額單位：元。`,
    '持股只存在這個瀏覽器，不放進分享連結；換裝置不會同步，清除網站資料會一起清除。平均成本請填含買入手續費的每股成本，可先用「<a href="#/tools/ac">工具 › 平均成本</a>」計算。',
    `證交稅：股票 0.3%、存託憑證 0.1%、ETF 0.1%、債券 ETF 停徵（至 ${b.until.replace(/-/g, '/')}）。`,
    b.over && x.some(r => r.e && /B$/.test(r.c)) && '債券 ETF 證交稅停徵期限已過，請確認最新稅率（本表仍以 0 試算）。',
    x.some(r => r.x.dsp) && '處置、全額交割股的出售方式另有限制，本表只做價格試算。'].filter(Boolean).map(t => `<div>${t}</div>`).join('') + '</div>';
}
function holdTable(T, e, V) {
  return `<div class="tbl-wrap"><table class="tbl h-tbl" data-h="${e ? 'e' : 's'}"><thead><tr><th>${e ? 'ETF' : '股票'}</th><th>股數</th><th>平均成本</th><th>收盤</th><th>市值</th><th>今日損益</th><th>未實現損益</th><th>報酬率</th></tr></thead><tbody>` +
    T.rows.map(x => `<tr data-${e ? 'etf' : 'code'}="${x.c}"><td class="nm h-nm">${wCtl(x.c)}<b>${esc(x.x.n)}</b>${e ? `<span>${x.c} ${x.x.m === 'TWSE' ? '上市' : '上櫃'}</span>` : `${alertBadge(x.x)}<span>${x.c} ${esc(x.x.i)}</span>`}</td>
      <td class="num"><span class="h-v">${holdQ(x)}</span>${holdIn(x, 'q')}</td><td class="num"><span class="h-v">${holdK(x)}</span>${holdIn(x, 'c')}</td>
      <td class="num">${pfmt(x.x.c)}${!e && x.x.nt ? `<span class="sub2">最後成交 ${md(x.x.nt)}</span>` : ''}</td>${holdTds(x)}</tr>`).join('') +
    `</tbody><tfoot>${holdFoot(T.sum)}</tfoot></table></div><div class="h-msg" role="status"></div>${e ? `<div class="small h-all">${holdAll(V)}</div>` : ''}`;
}
// 「填入」進編輯模式、焦點到該列股數（擋下 onRowClick，不進個股頁）；輸入框 change 時驗證、存檔，只更新數字儲存格（輸入框不重畫，焦點不會不見）
function holdWire(sec) {
  if (!sec) return;
  sec.addEventListener('click', e => {
    const b = e.target.closest('[data-hfill]');
    if (!b) return;
    e.stopPropagation();
    App.watchEdit = true; sec.classList.add('editing'); $('#watchEdit').textContent = '完成';
    sec.querySelector(`[data-hq="${b.dataset.hfill}"]`).focus();
  });
  sec.addEventListener('change', e => { const c = e.target.dataset.hq || e.target.dataset.hc; if (c) holdEdit(sec, c); });
}
function holdEdit(sec, c) {
  const L = App.latest, x = L.stocks[c] || L.etfs.rows[c], qi = sec.querySelector(`[data-hq="${c}"]`), ki = sec.querySelector(`[data-hc="${c}"]`);
  const a = qi.value.trim(), b = ki.value.trim(), q = tlNum(a, 0), k = tlC(b), nm = `${x.n} ${c}`, box = qi.closest('.tbl-wrap').nextElementSibling;
  const m = !a !== !b ? `${nm}：請同時填股數與平均成本；兩格都清空即刪除這檔持股` : a && !(q > 0) ? `${nm}：股數請填正整數`
    : b && !(k > 0) ? `${nm}：平均成本請填大於 0 的數字，小數最多 2 位` : '';
  const bad = (el, on) => on ? el.setAttribute('aria-invalid', 'true') : el.removeAttribute('aria-invalid');
  bad(qi, m && (!a || !(q > 0))); bad(ki, m && (!b || !(k > 0)));
  let ok = true;
  if (!m) { const H = holdLoad(); if (a) H[c] = [q, k]; else delete H[c]; ok = holdSave(H); }
  const line = (id, t) => { const d = box.querySelector(`[data-m="${id}"]`); if (d) d.remove(); if (t) box.insertAdjacentHTML('beforeend', `<div data-m="${id}">${esc(t)}</div>`); };
  line(c, m); line('_', ok ? '' : '這個瀏覽器無法儲存持股（可能是私密視窗或封鎖網站資料），重新整理後會消失');
  const V = holdView();
  [['s', V.s], ['e', V.e]].forEach(([t, T]) => { const tb = sec.querySelector(`.h-tbl[data-h="${t}"]`);
    if (!tb) return;
    T.rows.forEach(r => { const tr = [...tb.tBodies[0].rows].find(y => (y.dataset.code || y.dataset.etf) === r.c), v = tr ? tr.querySelectorAll('.h-v') : [];
      if (!tr) return;
      v[0].innerHTML = holdQ(r); v[1].innerHTML = holdK(r);
      while (tr.cells.length > 4) tr.deleteCell(4);
      tr.insertAdjacentHTML('beforeend', holdTds(r)); });
    tb.tFoot.innerHTML = holdFoot(T.sum); });
  sec.querySelector('.h-cap').outerHTML = holdCap(V, L);
  const al = sec.querySelector('.h-all');
  if (al) al.innerHTML = holdAll(V);
  const nx = sec.querySelector('.w-nx');                                           // 第 47 輪 F47-1c：估計可領跟著持股更新
  if (nx) nx.outerHTML = watchNx();
}
const holdLine = (V, L) => !V.n ? '' : `<a class="w-hold" href="#/watch">持股 ${V.n} 檔　今日損益 <b class="${cls(Number(V.d))}">${holdY(V.d)}</b> 元　` +
  `未實現損益 <b class="${cls(Number(V.u))}">${holdY(V.u)}</b> 元（<b class="${cls(Number(V.u))}">${holdP(V.u, V.t)}</b>）${V.k ? `（今日損益不含無成交、除息 ${V.k} 檔）` : ''}</a>` +
  `<div class="muted small">以 ${md(L.date)} 收盤全部出售試算，已扣出售手續費與證交稅</div>`;
// 第 42 輪 F42-2：今日頁總覽「我的自選」小卡（只用 latest.json；股票列沿用 renderToday 的 rows；持股數字和自選頁同一個 holdCalc）
function watchToday(L, rows) {
  const R = (L.etfs && L.etfs.rows) || {}, W = [...App.watch].filter(c => L.stocks[c] || R[c]);
  if (!W.length) return '';
  const S = W.filter(c => L.stocks[c]).map(c => L.stocks[c]), V = holdView().all;
  const a = S.filter(s => s.hl && s.hl.some(e => HL_KINDS[e[0]])).length, b = S.filter(s => s.dsp || s.ntc).length;
  const x = L.nx ? W.filter(c => L.nx[c]).length : 0;                              // 第 47 輪 F47-1d：自選全部（不只前 5 檔）
  const ev = [a && `近期新訊號 ${a} 檔`, b && `處置／注意 ${b} 檔`, x && `即將除權息 ${x} 檔`].filter(Boolean).join('、');
  return `<section class="sec card w-today"><div class="sec-h"><h2>我的自選</h2><span class="muted small">${md(L.date)} 收盤${L.flow_date !== L.date ? `、法人 ${md(L.flow_date)}` : ''}</span><span class="sp"></span><a class="chip" href="#/watch">全部 →</a></div>
    <div class="tbl-wrap"><table class="tbl"><thead><tr><th>自選</th><th>收盤</th><th>漲跌</th><th>法人1日</th></tr></thead><tbody>${W.slice(0, 5).map(c => L.stocks[c] ? rows([[c, L.stocks[c]]])
      : `<tr data-code="${c}"><td class="nm"><b>${esc(R[c].n)}</b><span>${c}</span></td><td class="num ${cls(R[c].ch)}">${pfmt(R[c].c)}</td>${etfPct(R[c], L.date)}<td class="num">--</td></tr>`).join('')}</tbody></table></div>` +
    holdLine(V, L) +
    (ev ? `<a class="w-ev-l" href="#/watch">${ev} →</a>` : '') +
    `<div class="muted small">${W.length > 5 ? `共 ${W.length} 檔，顯示前 5 檔（依自選順序）。` : ''}法人1日 = 三大法人當日買賣超（億，估算），ETF 不計。</div></section>`;
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
  $('#dateBar').innerHTML = `<span class="nw">資料日 ${esc(L.date)}</span><span class="nw${L.flow_date === L.date ? ' fd-eq' : ''}">　法人資料 ${esc(L.flow_date)}</span>　<span class="nw">更新於 ${esc(when)}` +
    (L.status?.collected_src === 'db' ? '（依資料寫入時間）' : '') + '</span>';   // 第 13 輪 F13-5：每段不在中間斷行；D27-10 手機上法人資料日和資料日相同時不重複（.fd-eq）
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

// ─── 色調 ───────────────────────────────────────────────
// 第 26 輪：淺色／深色切換。沒選過就跟系統；選過存在 tw.theme（index.html 開頭先套用，避免閃一下）。
// 圖表的顏色是畫圖當下從 CSS 取的，所以切換後重畫目前頁面，並回到原本的捲動位置。
const isDark = () => (document.documentElement.dataset.theme || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')) === 'dark';
function themeBtn() {
  const b = $('#themeBtn'), d = isDark();
  b.innerHTML = d ? '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>'
    : '<svg viewBox="0 0 24 24"><path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z"/></svg>';
  b.title = d ? '切換為淺色' : '切換為深色';
  b.setAttribute('aria-label', b.title);
}
async function redrawKeepScroll() {
  const y = window.scrollY;
  await route();
  window.scrollTo(0, y);
}
function setupTheme() {
  themeBtn();
  $('#themeBtn').addEventListener('click', () => {
    const t = isDark() ? 'light' : 'dark';
    document.documentElement.dataset.theme = t;
    localStore('theme', null, t);
    themeBtn();
    if (App.latest) redrawKeepScroll();
  });
  matchMedia('(prefers-color-scheme: dark)').addEventListener?.('change', () => {   // 沒選過時，系統切換也跟著重畫
    if (document.documentElement.dataset.theme) return;
    themeBtn();
    if (App.latest) redrawKeepScroll();
  });
}

// ─── 啟動 ───────────────────────────────────────────────
async function init() {
  setupTheme();
  setupSearch();
  try {
    App.latest = await getJSON('data/latest.json');
  } catch (e) {
    $('#view').innerHTML = '<div class="empty">找不到 data/latest.json，請先執行 <code>python -m twstock export</code></div>';
    return;
  }
  renderStatus();
  // 第 27 輪：頂欄高度給固定表頭、選股條件列（--top-h）；畫面重畫、捲動、改變大小時重算表頭位置（D27-01）
  const topH = () => { document.documentElement.style.setProperty('--top-h', $('.top').offsetHeight + 'px'); stickHeads(); };
  topH(); addEventListener('resize', topH); addEventListener('scroll', stickHeads, { passive: true });
  history.scrollRestoration = 'manual';                                 // D28-03：捲動位置由 route() 還原（內容是重畫的，瀏覽器自己還原會被蓋掉）
  addEventListener('scroll', saveScroll, { passive: true }); document.addEventListener('click', saveScroll, true);
  new MutationObserver(stickHeads).observe($('#view'), { childList: true });
  document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible') recheckLatest(); });
  window.addEventListener('hashchange', route);
  route();
}
document.addEventListener('DOMContentLoaded', init);
