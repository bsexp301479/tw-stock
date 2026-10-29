// 個股頁：K 線 + 均線、成交量、法人買賣超、MACD（四張圖同步拖曳/縮放），以及基本面與月營收
'use strict';

let charts = [], syncLeader = null;
const CHART_IDS = ['kC', 'vC', 'iC', 'mC'];

window.disposeStockCharts = () => { charts.forEach(c => c.remove()); charts = []; };

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
  const fund = data.fund || {};
  const watching = App.watch.has(code);

  $('#view').innerHTML = `
    <section class="sec card">
      <div class="s-head">
        <div>
          <div><span class="s-name">${esc(data.name)}</span><span class="s-code">${code}</span></div>
          <div><span class="s-price num ${cls(change)}">${pfmt(close)}</span>
            ${noTrade ? '<span class="s-chg flat">無成交</span>'
              : `<span class="s-chg num ${cls(change)}">${change > 0 ? '▲' : change < 0 ? '▼' : ''} ${pfmt(Math.abs(change ?? 0))} (${sgn(pct)}%)</span>`}</div>
          <div class="tags">
            <span class="pill">${data.market === 'TWSE' ? '上市' : '上櫃'}</span><span class="pill">${esc(data.industry)}</span>
            ${(data.chains || []).map(([chain, seg, subs]) => `<span class="pill chain" title="${esc(chain)} › ${esc(seg)}${subs.length ? '：' + esc(subs.join('、')) : ''}">${esc(chain)} › ${esc(subs.length ? subs.slice(0, 2).join('、') + (subs.length > 2 ? '…' : '') : seg)}</span>`).join('')}
            ${data.concepts.map(c => `<span class="pill">${esc(c)}</span>`).join('')}
            <span class="muted small">${noTrade ? `${P.d[last]} 無成交，顯示 ${P.d[lt]} 收盤` : `${P.d[last]} 收盤`}</span>
          </div>
        </div>
        <button class="star ${watching ? 'on' : ''}" id="starBtn">${watching ? '★ 已加入自選' : '☆ 加入自選'}</button>
      </div>
    </section>

    <section class="sec metrics">
      ${[['開盤', pfmt(P.o[last])], ['最高', pfmt(P.h[last]), 'up'], ['最低', pfmt(P.l[last]), 'dn'], ['昨收', pfmt(prev)],
         ['成交量', fmt(P.v[last]) + ' 張'], ['本益比', fmt(fund.pe, 2)], ['股價淨值比', fmt(fund.pb, 2)], ['殖利率', fund.dy != null ? fmt(fund.dy, 2) + '%' : '--'],
         ['52週高', pfmt(s?.h52)], ['52週低', pfmt(s?.l52)],
         ['法人1日', yi(s?.n1), cls(s?.n1)], ['法人5日', yi(s?.n5), cls(s?.n5)]]
        .map(([l, v, c]) => `<div class="card stat"><div class="l">${l}</div><div class="v num ${c || ''}" style="font-size:16px">${v}</div></div>`).join('')}
    </section>

    <section class="sec card">
      <div class="sec-h">
        ${segHTML('kSeg', [['日', '日'], ['週', '週'], ['月', '月']], mode)}
        <button class="seg" id="latestBtn" style="padding:4px 12px;font-size:12px">回到最新</button>
        <span class="sp"></span><span class="muted small">拖曳平移、滾輪縮放</span>
      </div>
      <div class="kleg" id="kLegend"></div>
      <div id="kC" class="chart-box" style="height:320px"></div>
      <div class="ch-label">成交量（張）</div>
      <div id="vC" class="chart-box" style="height:80px"></div>
      <div class="ch-label">三大法人買賣超（張）
        <span class="lg"><i style="background:var(--up)"></i>買超</span><span class="lg"><i style="background:var(--dn)"></i>賣超</span></div>
      <div id="iC" class="chart-box" style="height:90px"></div>
      <div class="ch-label">MACD (12, 26, 9)
        <span class="lg"><i style="background:#378ADD"></i>DIF</span><span class="lg"><i style="background:#EF9F27"></i>DEA</span></div>
      <div id="mC" class="chart-box" style="height:120px"></div>
    </section>

    <section class="sec grid g2">
      <div class="card"><div class="sec-h"><h2>月營收</h2><span class="muted small">億元，柱色 = 年增率正負</span></div><div id="revBox"></div></div>
      <div class="card"><div class="sec-h"><h2>技術面訊號</h2></div><div id="sigBox"></div></div>
    </section>`;

  $('#starBtn').addEventListener('click', () => {
    App.watch.has(code) ? App.watch.delete(code) : App.watch.add(code);
    saveWatch();
    const on = App.watch.has(code);
    $('#starBtn').classList.toggle('on', on);
    $('#starBtn').textContent = on ? '★ 已加入自選' : '☆ 加入自選';
  });
  onSeg('kSeg', m => { localStore('kmode', null, m); document.querySelectorAll('#kSeg button').forEach(b => b.classList.toggle('on', b.dataset.v === m)); buildCharts(aggregate(data, m), m); });
  $('#latestBtn').addEventListener('click', () => { syncLeader = charts[0]; charts[0]?.timeScale().scrollToRealTime(); });
  CHART_IDS.forEach((id, idx) => ['mouseenter', 'pointerdown', 'touchstart', 'wheel'].forEach(t =>
    $('#' + id).addEventListener(t, () => { syncLeader = charts[idx]; }, { passive: true })));

  renderRevenue(data.revenue);
  buildCharts(aggregate(data, mode), mode);
};

// ─── 日線 → 週線 / 月線（法人買賣超加總）────────────────────
function aggregate(data, mode) {
  const P = data.prices, I = data.insti;
  // 無成交的日子（開高低收為 --）以前一個收盤價畫一字線，時間軸保持連續；上市前的空值略過
  const rows = [];
  let prevC = null;
  P.d.forEach((d, i) => {
    const net = I.f[i] == null ? null : I.f[i] + I.t[i] + I.dl[i];
    if (P.c[i] != null && P.o[i] != null) {
      rows.push({ d, o: P.o[i], h: P.h[i], l: P.l[i], c: P.c[i], v: P.v[i], net, nt: false });
      prevC = P.c[i];
    } else if (prevC != null) {
      rows.push({ d, o: prevC, h: prevC, l: prevC, c: prevC, v: P.v[i] ?? 0, net, nt: true });
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
    if (!g) out.set(key, { ...r, d: key });
    else {
      g.h = Math.max(g.h, r.h); g.l = Math.min(g.l, r.l); g.c = r.c; g.v += r.v;
      g.nt = g.nt && r.nt;   // 整週/整月都沒成交才算一字線
      g.net = r.net == null ? g.net : (g.net ?? 0) + r.net;
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

function buildCharts(raw, mode) {
  window.disposeStockCharts();
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
  line(kc, ma5, '#888780'); line(kc, ma20, '#EF9F27'); line(kc, ma60, '#7F77DD');

  const vc = mk('vC', false);
  const vSer = vc.addHistogramSeries({ priceFormat: { type: 'volume' }, priceLineVisible: false, lastValueVisible: false });
  vSer.setData(raw.map((r, i) => ({ time: T[i], value: V[i], color: NT[i] ? FLAT + '99' : C[i] >= O[i] ? UP + '99' : DN + '99' })));

  const ic = mk('iC', false);
  const iSer = ic.addHistogramSeries({ priceFormat: { type: 'volume' }, priceLineVisible: false, lastValueVisible: false });
  iSer.setData(N.map((v, i) => v == null ? { time: T[i] } : { time: T[i], value: v, color: v >= 0 ? UP : DN }));

  const mc = mk('mC', true);
  const macdFmt = { type: 'price', precision: 2, minMove: 0.01 };
  const hSer = mc.addHistogramSeries({ priceFormat: macdFmt, priceLineVisible: false, lastValueVisible: false });
  hSer.setData(hist.map((v, i) => ({ time: T[i], value: v, color: v >= 0 ? 'rgba(55,138,221,.65)' : 'rgba(213,90,48,.65)' })));
  const difSer = line(mc, dif, '#378ADD', macdFmt);
  line(mc, dea, '#EF9F27', macdFmt);

  charts = [kc, vc, ic, mc];

  // 同步：只讓滑鼠/手指所在的那張圖帶動其他圖；若每張都互相回寫，拖曳中的事件會彼此抵銷
  syncLeader = kc;
  charts.forEach(src => src.timeScale().subscribeVisibleLogicalRangeChange(r => {
    if (src !== syncLeader || !r) return;
    charts.forEach(dst => dst !== src && dst.timeScale().setVisibleLogicalRange(r));
  }));

  // 十字線同步 + 上方資訊列
  const anchors = [[kc, kSer, i => C[i]], [vc, vSer, i => V[i]], [ic, iSer, i => N[i]], [mc, difSer, i => dif[i]]];
  const legend = $('#kLegend');
  const showLegend = i => {
    const chg = i ? C[i] - C[i - 1] : 0, p = i ? chg / C[i - 1] * 100 : 0, c = cls(chg);
    const ma = (label, v, color) => v == null ? '' : `<span style="color:${color}">${label} <b style="color:${color}">${pfmt(v)}</b></span>`;
    legend.innerHTML = `<span><b>${T[i]}</b></span><span>開 <b>${pfmt(O[i])}</b></span><span>高 <b class="up">${pfmt(H[i])}</b></span>` +
      `<span>低 <b class="dn">${pfmt(L[i])}</b></span><span>收 <b class="${c}">${pfmt(C[i])}</b></span>` +
      (NT[i] ? '<span class="flat">無成交</span>' : `<span class="${c}">${psgn(chg)} (${sgn(p)}%)</span>`) +
      `<span>量 <b>${fmt(V[i])}</b> 張</span>` +
      (N[i] != null ? `<span>法人 <b class="${cls(N[i])}">${sgn(N[i], 0)}</b> 張</span>` : '') +
      ma('MA5', ma5[i], '#888780') + ma('MA20', ma20[i], '#EF9F27') + ma('MA60', ma60[i], '#7F77DD');
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

  renderSignals(C, ma5, ma20, ma60, dif, dea, hist);
}

function renderSignals(C, ma5, ma20, ma60, dif, dea, hist) {
  const i = C.length - 1, c = C[i];
  const bull = [], bear = [];
  const chk = (ok, yes, no) => (ok ? bull : bear).push(ok ? yes : no);
  if (ma5[i] != null) chk(c > ma5[i], '收盤 > MA5', '收盤 < MA5');
  if (ma20[i] != null) chk(c > ma20[i], '收盤 > MA20', '收盤 < MA20');
  if (ma60[i] != null) chk(c > ma60[i], '收盤 > MA60', '收盤 < MA60');
  if (ma5[i] != null && ma20[i] != null) chk(ma5[i] > ma20[i], 'MA5 > MA20', 'MA5 < MA20');
  chk(dif[i] > dea[i], 'DIF > DEA', 'DIF < DEA');
  if (i) chk(hist[i] > hist[i - 1], 'MACD 柱放大', 'MACD 柱縮小');
  const isBull = bull.length >= bear.length;
  $('#sigBox').innerHTML = `<div class="signal ${isBull ? 'bull' : 'bear'}">
      <div style="font-weight:600;margin-bottom:6px">${isBull ? '偏多' : '偏空'}：${bull.length} 多 ${bear.length} 空</div>
      <div>${bull.map(t => `<span class="tag up">${t}</span>`).join('')}${bear.map(t => `<span class="tag dn">${t}</span>`).join('')}</div>
      <div class="muted small" style="margin-top:8px">依均線與 MACD 機械判讀，僅供參考。</div></div>`;
}

function renderRevenue(rows) {
  const box = $('#revBox');
  const list = rows.slice(-12);
  if (!list.length) { box.innerHTML = '<div class="empty">沒有月營收資料</div>'; return; }
  const max = Math.max(...list.map(r => r[2]));
  box.innerHTML = `<div class="rev">` + list.map(([y, m, rev, mom, yoy]) => `
      <div class="col" title="${y}/${m} 營收 ${fmt(rev / 1e5, 2)} 億，月增 ${sgn(mom)}%，年增 ${sgn(yoy)}%">
        <span class="num">${fmt(rev / 1e5, rev >= 1e7 ? 0 : 1)}</span>
        <span class="b" style="height:${Math.max(2, rev / max * 100)}%;background:${yoy == null ? 'var(--flat)' : yoy >= 0 ? 'var(--up)' : 'var(--dn)'}"></span>
        <span>${m}月</span><span class="num ${cls(yoy)}">${yoy == null ? '--' : sgn(yoy, 0) + '%'}</span>
      </div>`).join('') + '</div>';
}
