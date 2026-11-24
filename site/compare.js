// 第 48 輪 F42-10：報酬率比較 #/compare/代號,代號/區間（最多 4 檔，起點都是 0%）。股票用還原價（ev）、ETF 含息（dv＋gx，同 epf），
// 對照加權指數（data/ix.json：交易日＋加權收盤）。純函式在前（測試用 node 執行），畫面在後；圖表放在 stock.js 的 charts，換頁時 disposeStockCharts 一併釋放
'use strict';

const CMP_MAX = 4, CMP_KEYS = [['20', '20 日'], ['60', '60 日'], ['120', '120 日'], ['y', '今年以來'], ['w', '52 週']];

// 還原事件（R62）：股票 = ev（已是生效的資料列）；ETF = dv ＋ gx 中不在 dv 的日子（參考價 = 收盤 − 官方漲跌，漲跌 null 時 = 收盤；前收 = 前一列收盤）。
// 套用規則同匯出 _price_events：對到事件日當天或之後第一列，第 0 列或最後一列之後略過；同一列只用第一筆（官方先）；係數 0.02～20 以外略過
function cmpEvents(data) {
  const P = data.prices, ev = data.ev || data.dv || [], ex = new Set(ev.map(e => e.d)), at = {};
  const gx = data.ev ? [] : (data.gx || []).filter(g => !ex.has(g)).map(g => { const i = P.d.indexOf(g);
    return { d: g, p: P.c[i - 1], r: P.ch[i] == null ? P.c[i] : Math.round((P.c[i] - P.ch[i]) * 100) / 100 }; });
  ev.map(e => ({ d: e.d, p: e.p, r: e.r })).concat(gx).sort((a, b) => a.d < b.d ? -1 : a.d > b.d ? 1 : 0).forEach(e => {
    const i = P.d.findIndex(d => d >= e.d);
    if (i > 0 && !at[i] && e.r / e.p >= 0.02 && e.r / e.p <= 20) at[i] = { d: P.d[i], p: e.p, r: e.r };
  });
  return Object.keys(at).map(Number).sort((a, b) => a - b).map(i => at[i]);
}
// 還原收盤 = 收盤 × adjFactors（stock.js）；無成交為 null
function cmpAdj(data) {
  const P = data.prices, af = adjFactors(P.d, cmpEvents(data));
  return P.c.map((c, i) => c == null ? null : c * af[i]);
}
// 起點日（R63，同 stock_perf）：N 日 = 往前第 N 個交易日；y = 前一年最後一個交易日；w = 終點往前 365 天（含）以前最後一個交易日
function cmpBase(days, k) {
  const n = days.length, last = days[n - 1];
  if (k !== 'y' && k !== 'w') return n > +k ? days[n - 1 - k] : null;
  const t = k === 'y' ? last.slice(0, 4) + '-01-01' : new Date(Date.parse(last + 'T00:00:00Z') - 365 * 864e5).toISOString().slice(0, 10);
  const b = days.filter(d => k === 'y' ? d < t : d <= t);
  return b.length ? b[b.length - 1] : null;
}
// 某日（含）以前最後一個有成交的 [日期, 還原收盤]；沒有 → null
function cmpAt(d_, adj, b) {
  for (let i = d_.length - 1; i >= 0; i--) if (d_[i] <= b && adj[i] != null) return [d_[i], adj[i]];
  return null;
}
// 統計（R67）：pts = [[日期, 值]]，第一點是起點。區間報酬 %；最大跌幅 [%, 高點日, 低點日]（沒有下跌 → [0, null, null]）；
// 年化波動 = 相鄰兩點報酬的樣本標準差（n − 1）× √250 × 100，日報酬少於 20 個 → null
function cmpStats(pts) {
  const v = pts.map(p => p[1]), r = v.slice(1).map((x, i) => x / v[i] - 1), n = r.length, m = r.reduce((a, b) => a + b, 0) / n;
  let hi = 0, dd = [0, null, null];
  v.forEach((x, i) => { if (x > v[hi]) hi = i; const y = (x / v[hi] - 1) * 100; if (y < dd[0]) dd = [y, pts[hi][0], pts[i][0]]; });
  return { ret: (v[n] / v[0] - 1) * 100, dd, vol: n < 20 ? null : Math.sqrt(r.reduce((a, b) => a + (b - m) * (b - m), 0) / (n - 1)) * Math.sqrt(250) * 100 };
}
// 一條線：起點 b 到終點每個交易日 [日期, %, 無成交]（無成交沿用之前的值，R65）；統計只用起點那一點＋之後有成交的日子
function cmpLine(days, d_, adj, b) {
  const base = cmpAt(d_, adj, b), at = {}, pts = [base];
  d_.forEach((d, i) => { if (adj[i] != null) at[d] = adj[i]; if (adj[i] != null && d > b) pts.push([d, adj[i]]); });
  let v = base[1];
  const line = days.filter(d => d >= b).map(d => { if (d > b && d in at) v = at[d]; return [d, (v / base[1] - 1) * 100, !(d in at)]; });
  return { line, last: pts[pts.length - 1][0], ...cmpStats(pts) };
}
// 比較（R63～R66）：ix = {d, TAIEX}；S = [{c, d_, adj}]（網址順序）。有一檔在起點日（含）以前沒有成交 → 全部從各檔第一個成交日中最晚的那天起算
function cmpCalc(ix, S, k) {
  const D = ix.d, first = S.map(s => s.d_[s.adj.findIndex(a => a != null)]);
  let b = cmpBase(D, k) || D[0];
  const late = first.some(f => f > b) ? first.reduce((a, f) => f > a ? f : a) : null;
  if (late) b = late;
  return { b, end: D[D.length - 1], late: late ? S.filter((s, j) => first[j] === late).map(s => s.c) : [],
    rows: S.map(s => Object.assign({ c: s.c }, cmpLine(D, s.d_, s.adj, b))), ix: cmpLine(D, D, ix.TAIEX, b) };
}
// 搜尋（同頂欄 pick）：代號開頭 → 名稱開頭 → 名稱包含（後兩組依成交額），排除已選的
function cmpPick(all, q, skip) {
  const byTv = (a, b) => (b[1].tv ?? 0) - (a[1].tv ?? 0), nm = s => s.n.toLowerCase(), a = all.filter(([c]) => !skip.includes(c));
  const rest = a.filter(([c]) => !c.toLowerCase().startsWith(q));
  return a.filter(([c]) => c.toLowerCase().startsWith(q)).concat(rest.filter(([, s]) => nm(s).startsWith(q)).sort(byTv), rest.filter(([, s]) => !nm(s).startsWith(q) && nm(s).includes(q)).sort(byTv));
}
// 網址正規化（R68）：轉大寫、去重、去空項、只留今天行情有的代號、最多 4 檔；區間不認得 → w
function cmpNorm(arg, sub, L) {
  try { arg = decodeURIComponent(arg || ''); } catch (e) { }          // 網址列手打的空白、逗號會被編成 %20、%2C（QA48-01）；不合法的 % 照原樣
  const R = L.etfs?.rows || {}, all = [...new Set((arg || '').split(',').map(s => s.trim().toUpperCase()).filter(Boolean))];
  const ok = all.filter(c => L.stocks[c] || R[c]), msg = [];
  if (ok.length < all.length) msg.push(`找不到 ${all.filter(c => !ok.includes(c)).join('、')}，已從比較清單移除`);
  if (ok.length > CMP_MAX) msg.push(`最多比較 ${CMP_MAX} 檔，已保留前 ${CMP_MAX} 檔`);
  return { list: ok.slice(0, CMP_MAX), k: CMP_KEYS.some(([v]) => v === sub) ? sub : 'w', msg };
}
// 顯示用：四捨五入到 2 位，二進位值剛好一半時取偶數（同 Python round，和個股頁近期表現 pf 的數字相同，例 -15.625 → -15.62、2.675 → 2.67）
function cmpR(v) {
  const f = Math.floor(v * 100);
  return /\.\d\d50*$/.test(Math.abs(v).toFixed(20)) ? (f + (f & 1)) / 100 : Number(v.toFixed(2));
}
const pc = v => sgn(v == null ? v : cmpR(v));
const cmpUrl = (list, k) => list.length ? `#/compare/${list.join(',')}/${k}` : '#/compare';

// ─── 畫面 ───────────────────────────────────────────────
window.renderCompare = async (arg, sub) => {
  disposeKCharts();
  const L = App.latest, R = L.etfs?.rows || {}, view = $('#view'), nm = c => (L.stocks[c] || R[c]).n;
  let { list, k, msg } = cmpNorm(arg, sub, L);
  const ix = App.cmpIx || (App.cmpIx = await getJSON('data/ix.json').catch(() => null));
  const data = ix ? await Promise.all(list.map(c => loadStock(c, L.stocks[c] ? 'stocks' : 'etfp'))) : [];
  const no = list.filter((c, j) => ix && !L.stocks[c] && !data[j].epf);       // ETF 沒有 epf（第 46 輪 D138 防呆）不列入
  if (no.length) msg.push(`本站無法確認 ${no.join('、')} 的價格調整，暫不比較`);
  const S = list.map((c, j) => ({ c, d_: ix ? data[j].prices.d : [], adj: ix ? cmpAdj(data[j]) : [] })).filter(s => !no.includes(s.c));
  list = S.map(s => s.c);
  if (location.hash !== cmpUrl(list, k)) history.replaceState(history.state, '', cmpUrl(list, k));
  const go = (l, v) => { history.replaceState(null, '', cmpUrl(l, v)); window.renderCompare(l.join(','), v); };
  const X = ix && S.length ? cmpCalc(ix, S, k) : null, col = j => `var(--cmp${j + 1})`, full = list.length >= CMP_MAX;
  const W = [...App.watch].filter(c => (L.stocks[c] || R[c]) && !list.includes(c)).slice(0, 8);
  const short = '股票用還原價（含股息）、ETF 含配息；加權指數不含股息';      // 短句用變數：test_iter13 數 noteHTML 字面呼叫
  const note = X && `每條線 = 還原收盤 ÷ 起點的還原收盤 − 1。股票的還原價和個股頁 K 線、近期表現相同（除權息、減資、現金增資依官方參考價調整）；ETF 的含息報酬和 ETF 頁「近期表現（含息）」相同（配息在除息日以參考價再投入同一檔，上市 ETF 推測的分割、合併也一起調整）。不含手續費、稅與二代健保補充保費。` +
    'N 日 = 從往前第 N 個交易日的收盤起算（20 日約 1 個月、60 日約 3 個月、120 日約 6 個月）；今年以來從前一年最後一個交易日起算；52 週從一年前那天（含）以前最後一個交易日起算。' +
    `起點那天沒有成交時，用之前最後一個成交日的收盤；有一檔在起點還沒有成交時，全部改從最晚那檔的第一個成交日起算（不是發行價，本站日線從 ${ix.d[0]} 起）。無成交的日子線持平，今天無成交時用最後成交的收盤。` +
    '最大跌幅 = 區間內從之前的最高點往下的最大跌幅（含起點）；年化波動 = 相鄰兩個成交日漲跌幅的標準差 × √250，數字越大代表每天起伏越大，少於 20 個交易日不計算。' +
    '加權指數是價格指數，不含股息，區間越長影響越大；上櫃股票的個股頁對照櫃買指數，這裡一律對照加權指數。債券、海外、槓桿／反向、期貨 ETF 和股價指數走勢不同。以上都是過去區間的數字，不代表之後的走勢。';
  const td = s => `<td class="num ${cls(s.ret)}">${pc(s.ret)}%</td>` + (s.dd[1] ? `<td class="num" title="${s.dd[1]} 高點 → ${s.dd[2]}">${pc(s.dd[0])}%</td>` : '<td class="num">0.00%</td>') +
    `<td class="num">${s.vol == null ? '--' : fmt(cmpR(s.vol), 2) + '%'}</td>`;
  view.innerHTML = `<section class="sec card cmp"><div class="sec-h"><h2>報酬率比較</h2><span class="muted small">至 ${md(ix ? ix.d[ix.d.length - 1] : L.date)}</span></div>
    <div class="muted small">把最多 4 檔股票或 ETF 放在同一段期間比較，起點都是 0%。</div>
    <div class="cmp-pick">${list.map((c, j) => `<span class="chip cmp-c"><i class="cmp-dot" style="background:${col(j)}"></i>${c} ${esc(nm(c))}<button type="button" class="cmp-x" data-x="${c}" aria-label="移除 ${c}">×</button></span>`).join('')}
      <div class="cmp-q">${full ? '<input id="cmpQ" type="search" placeholder="已滿 4 檔" autocomplete="off" disabled>' : '<input id="cmpQ" type="search" placeholder="加入代號或名稱" autocomplete="off">'}<div id="cmpList" class="qlist" hidden></div></div></div>
    ${W.length && !full ? `<div class="cmp-w small"><span class="muted">自選：</span>${W.map(c => `<a href="#" class="chip" data-add="${c}">${c} ${esc(nm(c))}</a>`).join('')}</div>` : ''}
    ${msg.map(t => `<div class="muted small cmp-msg">${esc(t)}</div>`).join('')}
    ${!ix ? '<div class="empty">找不到交易日資料（data/ix.json），重新匯出資料後才能比較</div>' : !X ? '<div class="empty">輸入代號或名稱，加入要比較的股票或 ETF（最多 4 檔）。也可以從個股頁、ETF 頁的「近期表現」卡點「比較 →」進來。</div>' : `
    ${segHTML('cmpSeg', CMP_KEYS, k)}
    <div class="muted small cmp-s">自 ${X.b} 收盤起算，至 ${X.end} 收盤</div>
    ${X.late.length ? `<div class="muted small cmp-late">${X.late.join('、')} 在本站 ${X.b} 才有成交，比較起點改為 ${X.b}（各檔與加權指數都從這天起算）</div>` : ''}
    <div class="kleg" id="cmpL"></div><div id="cmpC" class="chart-box cmp-ch"></div>
    <div class="kleg"><span class="lg"><i class="dash"></i>加權指數（不含息）</span><span class="lg">實線 = 各檔（股票還原價、ETF 含息）</span></div>
    <div class="tbl-wrap"><table class="tbl cmp-tbl"><thead><tr><th>名稱</th><th>區間報酬</th><th>最大跌幅</th><th>年化波動</th></tr></thead><tbody>` +
    X.rows.map((r, j) => `<tr><td><i class="cmp-dot" style="background:${col(j)}"></i><b>${esc(nm(r.c))}</b> <span class="muted small">${r.c}</span>${r.last < X.end ? `<div class="muted small">最後成交 ${md(r.last)}</div>` : ''}</td>${td(r)}</tr>`).join('') +
    `<tr><td><i class="cmp-dot cmp-ix"></i><b>加權指數（不含息）</b></td>${td(X.ix)}</tr></tbody></table></div>
    <div class="muted small">表格依加入順序排列。最大跌幅滑過可看高點與低點日期；年化波動在區間內少於 20 個交易日時不計算（--）。</div>
    <div class="muted small" style="margin-top:6px">${noteHTML(short, note)}</div>`}</section>`;
  const sec = $('#view .cmp'), input = $('#cmpQ'), box = $('#cmpList');
  sec.addEventListener('click', e => { const a = e.target.closest('[data-add]'), x = e.target.closest('[data-x]');
    if (a) { e.preventDefault(); go(list.concat(a.dataset.add), k); } else if (x) go(list.filter(c => c !== x.dataset.x), k); });
  let hits = [], on = -1;
  const draw = () => { const q = input.value.trim();
    box.innerHTML = hits.map(([c, s], i) => `<a href="#" data-add="${c}"${i === on ? ' class="on"' : ''}><span class="code">${c}</span><span class="qn">${esc(s.n)}</span><span class="muted small">${esc(s.i ?? 'ETF')}</span></a>`).join('') ||
      (q ? `<div class="qnone">找不到「${esc(q)}」，可輸入代號或名稱的一部分</div>` : '');
    box.hidden = !box.innerHTML; };
  input.addEventListener('input', () => { const q = input.value.trim().toLowerCase();
    hits = q ? cmpPick(Object.entries(L.stocks), q, list).concat(cmpPick(Object.entries(R), q, list)).slice(0, 8) : []; on = -1; draw(); });
  input.addEventListener('keydown', e => {
    if (e.isComposing || e.keyCode === 229) return;                     // 注音、倉頡選字中的 Enter 不送出
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') { const n = hits.length;
      if (n) on = e.key === 'ArrowDown' ? (on + 1) % n : (on <= 0 ? n : on) - 1;
      draw(); e.preventDefault();
    } else if (e.key === 'Enter') { e.preventDefault();
      const q = input.value.trim().toLowerCase(), h = hits[on] || hits.filter(([c]) => c.toLowerCase() === q)[0];
      if (h) go(list.concat(h[0]), k);
    } else if (e.key === 'Escape') { box.hidden = true; input.blur(); }
  });
  box.addEventListener('mousedown', e => e.preventDefault());           // 點清單時輸入框不失焦，點其他地方才關閉
  input.addEventListener('blur', () => { box.hidden = true; });
  if (!X) return;
  onSeg('cmpSeg', v => go(list, v));
  const show = i => { $('#cmpL').innerHTML = `<span><b>${X.ix.line[i][0].split('-').join('/')}</b></span>` +
    X.rows.map((r, j) => `<span><i class="cmp-dot" style="background:${col(j)}"></i>${r.c} <b>${pc(r.line[i][1])}%</b>${r.line[i][2] ? '（無成交）' : ''}</span>`).join('') +
    `<span><i class="cmp-dot cmp-ix"></i>加權 <b>${pc(X.ix.line[i][1])}%</b></span>`; };
  const LC = window.LightweightCharts, T = X.ix.line.length;
  show(T - 1);
  if (!LC) return;
  const dt = t => typeof t === 'string' ? t : [t.year, t.month, t.day].map(x => String(x).padStart(2, '0')).join('-');
  const c = LC.createChart($('#cmpC'), { autoSize: true, handleScroll: false, handleScale: false,
    layout: { background: { type: 'solid', color: 'transparent' }, textColor: css('--text2'), fontSize: 11, attributionLogo: false },
    grid: { vertLines: { visible: false }, horzLines: { color: css('--border') } },
    rightPriceScale: { borderVisible: false, minimumWidth: 76, entireTextOnly: true },
    timeScale: { borderVisible: false, fixLeftEdge: true, fixRightEdge: true,
      tickMarkFormatter: (t, type) => { const [y, m, d] = dt(t).split('-').map(Number); return type === 0 ? String(y) : type === 1 ? `${m}月` : `${m}/${d}`; } },
    localization: { locale: 'zh-TW', timeFormatter: t => dt(t).split('-').join('/') } });
  const px = { type: 'custom', minMove: 0.01, formatter: v => sgn(v) + '%' };
  const add = (s, color, st, w) => { const x = c.addLineSeries({ color, lineStyle: st, lineWidth: w, priceFormat: px, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false });
    x.setData(s.line.map(([d, v]) => ({ time: d, value: v }))); return x; };
  add(X.ix, css('--text2'), 2, 1).createPriceLine({ price: 0, color: css('--border2'), lineWidth: 1, lineStyle: 0, axisLabelVisible: false, title: '' });
  X.rows.forEach((r, j) => add(r, css(`--cmp${j + 1}`), 0, 2));
  charts = [c];                                                          // stock.js：route() 換頁時 disposeStockCharts 釋放
  c.timeScale().fitContent();
  c.subscribeCrosshairMove(p => { const i = p.logical == null ? -1 : Math.round(p.logical); show(p.time !== undefined && i >= 0 && i < T ? i : T - 1); });
};
