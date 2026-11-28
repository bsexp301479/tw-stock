// 個股頁：K 線 + 均線、成交量、法人買賣超、融資融券、MACD（同步拖曳/縮放），以及基本面與月營收
'use strict';

let charts = [], syncLeader = null;
const CHART_IDS = ['kC', 'vC', 'iC', 'gC', 'mC'];   // gC（融資融券）只在有 mg 時存在
// 法人買賣超堆疊柱：外資在最靠近零軸的一層，往外依序投信、自營
const INVESTORS = [['f', '外資', '#4C6EF5'], ['t', '投信', '#F08C00'], ['dl', '自營', '#AE3EC9']];
const NET_TIP = '合計 = 官方三大法人合計（股數）換算張數，和外資、投信、自營各自四捨五入後相加可能差 1 張；週／月 K 是每日合計相加，可能和股數加總後四捨五入差 1～2 張';   // 第 24 輪 F24-8

const disposeKCharts = () => { charts.forEach(c => c.remove()); charts = []; };
// 離開個股頁時一併釋放月營收圖；切換日／週／月只重建 K 線（buildCharts），不動月營收圖
window.disposeStockCharts = () => {
  disposeKCharts();
  if (window.Plotly && $('#revC')) Plotly.purge('revC');
};

const MARGIN_NOTE = { O: '停止融資', X: '停止融券', '@': '融資分配', '%': '融券分配', '!': '停止買賣' };   // 上市註記
// 第 22 輪 F22-1：連續天數的文字；|n| < 2 不寫，30 = 最多看 30 日（匯出 streak 的上限）→「30 日以上」
const runTxt = (n, up, dn) => Math.abs(n || 0) < 2 ? '' : `連${n > 0 ? up : dn} ${Math.abs(n) >= 30 ? '30 日以上' : Math.abs(n) + ' 日'}`;
// 融資、借券餘額的連續增減天數（張；面額變更、減資依官方換算 mg.k，同還原模式的融資融券圖）；算到 to（該卡資料日），最多 30 日，增減 0 或缺值中斷
function balStreak(G, D, key, to) {
  const a = G?.[key], gk = d => (G.k || []).reduce((p, x) => x.d > d ? p * x.k : p, 1);
  const v = (a || []).map((x, i) => x == null ? null : Math.round(x * gk(D[i]))).filter((_, i) => D[i] <= to).slice(-31);
  let n = 0;
  for (let i = v.length - 1; i > 0; i--) {
    const x = v[i] == null || v[i - 1] == null ? 0 : v[i] - v[i - 1];
    if (!x || (n && (x > 0) !== (n > 0))) break;
    n += x > 0 ? 1 : -1;
  }
  return n;
}

// 第 23 輪 F23-1：近期表現（匯出端 pf = [[區間, 基準日, 本股 %, 指數 %, 差距]]，和選股 5／20／60 日報酬、相對強度同一套）；停牌、ETF 沒有 pf。nt = 本股最後成交日（今天無成交時）
const PF_NAME = { 5: '5 日', 20: '20 日', 60: '60 日', 120: '120 日', y: '今年以來', w: '52 週' };
// 第 46 輪 F46-2：etf = ETF 代號時為 ETF 版（etfp/ 的 epf：含息、上市上櫃一律對照加權指數、代號尾碼 B／L／R／U 多一行提示），股票輸出不變
function perfHTML(pf, mkt, nt, etf = false) {
  const ix = mkt === 'TWSE' || etf ? '加權指數' : '櫃買指數', ls = mkt === 'TWSE' ? '上市以來' : '上櫃以來', at = k => pf.find(r => r[0] === k)?.[1];
  const td = (v, u) => `<td class="num ${cls(v)}">${v == null ? '--' : sgn(v) + u}</td>`;
  const short = etf ? '含息報酬（配息在除息日再投入）；加權指數不含股息，長區間的差距會偏向 ETF' : '還原價（含股息）；指數不含股息，長區間的差距會偏向個股';      // 短句用變數：test_iter13 數 noteHTML 字面呼叫
  const full = etf ? `差距 = 本檔 − 加權指數（百分點）。本檔用含息還原收盤：除息日依證交所、櫃買中心除息表的參考價 ÷ 除息前收盤，調整之前的價格，等於把配息在除息日以參考價再投入同一檔；上市 ETF 推測的其他價格調整（多為分割、合併）也一起調整，上櫃 ETF 的分割、合併本站無法辨識。K 線、52 週高低仍是原始價。不含手續費、稅與二代健保補充保費。今天無成交時用最後成交的收盤。加權指數是價格指數，不含股息，所以區間越長，差距越偏向 ETF；ETF 追蹤的指數和加權指數不同，債券、海外、槓桿／反向、期貨 ETF 的差距只能當參考。N 日 = 從往前第 N 個交易日的收盤起算（20 日約 1 個月、60 日約 3 個月、120 日約 6 個月）；今年以來從 ${at('y')} 收盤起算；52 週從 ${at('w')} 收盤起算。「--」= 基準日時本站還沒有這檔的成交${at('s') ? `；${ls}從本站第一個成交日 ${at('s')} 的收盤起算，不是發行價（本站日線從 2025-10-30 起）` : ''}。`
    : `差距 = 本股 − ${ix}（百分點）。本股用還原收盤（除權息、減資、現金增資依官方參考價調整，和 K 線、52 週高低、選股相同），今天無成交時用最後成交的收盤；${ix}是價格指數，不含股息，所以區間越長，差距越偏向本股（大約是期間的殖利率）。` +
    `N 日 = 從往前第 N 個交易日的收盤起算，5、20、60 日和選股的 5／20／60 日報酬、20／60 日相對強度相同；今年以來從 ${at('y')} 收盤起算；52 週從 ${at('w')} 收盤起算。` +
    `「--」= 基準日時本站還沒有這檔的成交${at('s') ? `；${ls}從本站第一個成交日 ${at('s')} 的收盤起算，不是承銷價（本站日線從 2025-10-30 起，復牌或轉換為控股公司的股票也從第一個成交日起算）` : ''}。`;
  const tip = etf && { B: '債券 ETF 和股價指數走勢不同，差距只能當參考。', L: '槓桿、反向 ETF 每日追蹤指數報酬的倍數，區間報酬不等於指數報酬乘以倍數。',
    U: '期貨 ETF 追蹤期貨價格，和股價指數走勢不同，差距只能當參考。' }[etf.slice(-1).replace('R', 'L')], me = etf ? '本檔' : '本股';
  const X = App.latest.ixr, xr = X && X.d === App.latest.date && (mkt === 'TWSE' || etf) ? `<div class="muted small" style="margin-top:6px" title="證交所發行量加權股價報酬指數：成分股的現金股利再投入指數計算；表格的加權指數欄是價格指數，不含股息">加權報酬指數（含息）同期：${X.pf.map(([k, , v]) => `${PF_NAME[k]} ${v == null ? '--' : sgn(v) + '%'}`).join('、')}</div>` : '';   // 第 51 輪 F51-5：上市股票與所有 ETF；沒有 latest.ixr 時輸出不變
  return `<section class="sec card"><div class="sec-h"><h2>${etf ? '近期表現（含息）' : '近期表現'}</h2><span class="muted small">至 ${md(App.latest.date)}${nt ? `，${me}最後成交 ${md(nt)}` : ''}</span></div>${tip ? `<div class="muted small">${tip}</div>` : ''}
    <div class="tbl-wrap"><table class="tbl pf-tbl"><thead><tr><th>區間</th><th>${me}</th><th>${ix}</th><th>差距</th></tr></thead><tbody>` +
    pf.map(([k, b, s, i, g]) => `<tr><td>${k === 's' ? `${ls}<span>${md(b)} 起</span>` : PF_NAME[k]}</td>${td(s, '%')}${td(i, '%')}${td(g, '')}</tr>`).join('') +
    `</tbody></table></div>${xr}<div class="muted small" style="margin-top:6px">${noteHTML(short, full)}</div></section>`;
}

// 第 24 輪 F24-6：股利與填息（匯出端 dv：d 除權息日、t 類型、k 分類、c 現金股利、s 每仟股配股、a 權值＋息值（沒有 c 時）、p 除權息前收盤、
// f 填息日、n 第幾個交易日、x = [日期, 原因] 股本變動後不再比較）；填息在匯出端算，這裡只顯示。D36-12：金額最多 4 位小數、去掉尾端 0
const dfmt = (n, d = 4) => n == null ? '--' : Number(n).toLocaleString('zh-TW', { maximumFractionDigits: d });
// 第 36 輪 F36-2：etf = true 時為 ETF 版（標題「配息與填息」、沒有配股欄、說明不同），股票輸出不變
function divHTML(dv, mkt, P, etf = false) {
  const head = `<section class="sec card"><div class="sec-h"><h2>${etf ? '配息與填息' : '股利與填息'}</h2></div>`, from = P.d[0];
  if (!dv.length) return `${head}<div class="muted small">${from} 起沒有${etf ? '除息' : '除權息'}紀錄</div></section>`;
  const tr = P.c.map((c, i) => c != null ? i : -1).filter(i => i >= 0), lt = tr[tr.length - 1], lc = P.c[lt];
  const late = P.d[lt] !== App.latest.date ? `，最後成交 ${md(P.d[lt])}` : '';      // D37-7：停牌股照算，寫最後成交日
  const split = r => mkt === 'TWSE' && r.t === '權息' ? ` title="上市除權息的官方表只有權值＋息值合計 ${dfmt(r.a, 6)} 元，無法拆分現金與配股"` : '';
  const cash = r => r.c > 0 ? dfmt(r.c) : `<span${split(r)}>--</span>`;
  const stock = r => r.s ? fmt(r.s, 2) : mkt === 'TWSE' && (r.t === '權' || r.k === 's')
    ? `<span title="上市的官方表沒有配股數${r.t === '權' && r.a != null ? `；權值＋息值 ${dfmt(r.a, 6)} 元` : ''}">有</span>` : `<span${split(r)}>--</span>`;
  const fill = r => r.t === '權' ? '<span title="純配股不計算填權">--</span>' : r.f ? `${r.n === 1 ? '當天' : md(r.f)}<span>第 ${r.n} 個交易日</span>`
    : r.x ? `不再比較<span>${md(r.x[0])} ${r.x[1]}後</span>` : `尚未填息<span>還差 ${fmt(r.p - lc, 2)} 元，+${fmt((r.p - lc) / lc * 100, 2)}%${late}</span>`;
  const short = `填息 = 收盤回到除息前收盤；天數含除息日當天。資料自 ${from} 起`;     // 短句用變數：test_iter13 數 noteHTML 字面呼叫
  const full = etf ? ETF_DIV_FULL : '填息日 = 除權息日起（含當天）第一個收盤大於或等於除權息前收盤的交易日，用原始價、不設期限；第 N 個交易日從除權息日當天算第 1 天，無成交日也算。' +
    '純配股（除權）不計算填權；只有現金增資的除權不列入。還沒填息就遇到之後的配股、減資或面額變更時，原始價不能再和除權息前收盤比較，寫「不再比較」。' +
    '上市除權息的官方表只有權值＋息值合計，現金股利寫「--」（滑過可看合計）；上櫃的配股是每千股無償配股的股數。還差 = 除權息前收盤 − 最新收盤，% 以最新收盤計算。';
  return `${head}<div class="tbl-wrap"><table class="tbl dv-tbl"><thead><tr>${etf ? '<th>除息日</th><th>配息<br>（元）</th><th>除息<br>前收盤</th>'
    : '<th>除權息日</th><th>現金股利<br>（元）</th><th>配股<br>每千股</th><th>除權息<br>前收盤</th>'}<th>填息</th></tr></thead><tbody>` +
    dv.slice().reverse().map(r => `<tr><td>${r.d.replaceAll('-', '/')}${r.t === '息' ? '' : `<span>${EV_LABEL[r.t]}</span>`}</td><td class="num">${cash(r)}</td>` +
      `${etf ? '' : `<td class="num">${stock(r)}</td>`}<td class="num">${pfmt(r.p)}</td><td>${fill(r)}</td></tr>`).join('') +
    `</tbody></table></div><div class="muted small" style="margin-top:6px">${noteHTML(short, full)}</div></section>`;
}

// 第 40 輪 F40-3：股利卡「即將除權息」一行（nx 一筆；數字照預告值，不另外四捨五入）
function nxText(n, etf) {
  const p = [n.c > 0 ? `${etf ? '配息' : '現金股利'} ${dfmt(n.c, 8)} 元` : '', n.s > 0 ? `每千股配股 ${dfmt(n.s, 8)} 股` : '',
    n.sr ? `含現金增資，認購價${n.sp == null ? '尚未公告' : ` ${dfmt(n.sp, 2)} 元`}` : '', n.c == null ? '金額待公告' : ''].filter(Boolean);
  return `即將${n.t === '息' ? '除息' : n.t === '權' ? '除權' : '除權息'} ${md(n.d)}：${p.join('、')}（預告，以${etf ? '發行人' : '公司'}公告為準）`;
}
// 第 47 輪 F47-1b：頁頭「即將除息 12/03」標籤（nx 第一筆，連到除權息試算、只帶代號）；沒有 nx 輸出空字串
const nxTag = (nx, code, etf) => nx && nx.length ? `<a class="pill pill-nx" href="#/tools/dv?c=${code}" title="${esc(nxText(nx[0], etf))}">即將${nxKind(nx[0].t)} ${md(nx[0].d)}</a>` : '';
const ETF_DIV_FULL = '填息日 = 除息日起（含當天）第一個收盤大於或等於除息前收盤的交易日，用原始價、不設期限；第 N 個交易日從除息日當天算第 1 天，無成交日也算。' +
  '除息日、配息與除息前收盤來自證交所、櫃買中心的除息表。上市 ETF 還沒填息就遇到推測的其他價格調整（多為分割）時，寫「不再比較」；上櫃 ETF 無法辨識分割，照常比較。' +
  '還差 = 除息前收盤 − 最新收盤，% 以最新收盤計算。ETF 的配息來源可能含收益平準金、資本利得，不等於獲利。';

// 第 37 輪 F37-2～4：本益比／淨值比河流圖（原始收盤＋5 條倍數線，不塗色）。倍數線 = 當天反推的 EPS（每股淨值）× 近一年官方值的百分位
const BAND_PCT = [10, 25, 50, 75, 90], BAND_STY = [[2, 1], [0, 1], [0, 2], [0, 1], [2, 1]];   // [lineStyle, 線寬]：10／90 虛線、中位數粗線
const BAND_NM = { pe: ['本益比', '近 4 季 EPS'], pb: ['淨值比', '每股淨值'] };
function bandView(data) {                                                              // 選的那個畫不出來、另一個可以 → 改顯示另一個（今天虧損 → 淨值比）
  const B = data.band || {}, f = data.fund || {}, ok = k => !!(B[k] && f[k] != null);
  const v = localStore('bandV', 'pe') === 'pb' ? 'pb' : 'pe', o = v === 'pe' ? 'pb' : 'pe';
  return ok(v) || !ok(o) ? v : o;
}
const BAND_NOTE = (k, n) => (k === 'pe' ? '倍數線 = 當天的近 4 季 EPS × 近一年官方本益比的百分位。EPS 由證交所、櫃買中心公布的本益比反推（原始收盤 ÷ 本益比），官方換用新財報時倍數線才會跳動。'
  : '倍數線 = 當天的每股淨值 × 近一年官方淨值比的百分位。每股淨值由證交所、櫃買中心公布的淨值比反推（原始收盤 ÷ 淨值比），通常一季更新一次。') +
  `第 P 百分位 = 近 ${n} 個有官方值的交易日由小到大排列，第 P% 的位置（最近序位）；這一年有 P% 的天數小於或等於這個倍數。收盤是原始價，和 K 線預設的還原價不同。` +
  '倍數是用這一年的資料算的，舊日期的線也用到之後的資料；股價約有一半時間在中間兩條線之間是計算方式造成的，不代表股價會回到某條線。只有一年資料，不是長期區間，也不能用來回測。' +
  `河流圖只描述股價和${k === 'pe' ? '近 4 季獲利' : '每股淨值'}的關係，不是股價的評價，也不是投資建議${k === 'pe' ? '；獲利大增時股價會落到低倍數線附近，例如景氣循環股在獲利高峰' : ''}。`;
function bandHTML(data, capSub) {
  const h = '<section class="sec card"><div class="sec-h"><h2 id="bandT">本益比河流圖（近一年）</h2>';
  if (!data.band) return `${h}</div><div class="muted small">${capSub ? capSub + '；股本變動後 90 天內不畫河流圖' : '近一年有官方本益比、淨值比的天數都不足 120 天，不畫河流圖'}</div></section>`;
  return `${h}<span class="sp"></span>${segHTML('bandSeg', [['pe', '本益比'], ['pb', '淨值比']], bandView(data))}</div><div id="bandBox"></div></section>`;
}
function renderBand(data, k) {
  disposeKCharts();                                                                    // 河流圖放在 charts，disposeStockCharts 一併釋放
  const B = data.band[k], f = data.fund || {}, P = data.prices, [nm, base] = BAND_NM[k], box = $('#bandBox'), LC = window.LightweightCharts;
  $('#bandT').textContent = nm + '河流圖（近一年）';
  if (f[k] == null || !B) {
    box.innerHTML = `<div class="muted small">${f[k] != null ? `近一年有官方${nm}的天數不足 120 天，或反推值變動過於頻繁，不畫河流圖`
      : k === 'pe' ? '近 4 季 EPS ≤ 0，官方不計算本益比' : '官方沒有提供今天的淨值比'}</div>`;
    return;
  }
  const T = [], C = [], E = [];
  let j = 0;
  P.d.forEach((d, i) => { if (d < B.s[0][0] || d > data.band.d) return;
    while (j + 1 < B.s.length && B.s[j + 1][0] <= d) j++;
    T.push(d); C.push(P.c[i]); E.push(B.s[j][1]); });
  const lc = P.c.filter(x => x != null), close = lc[lc.length - 1], V = (data.val || {})[k];
  const pos = !V ? '' : f[k] <= V[1] ? '（近一年最低）' : f[k] >= V[2] ? '（近一年最高）' : `（近一年第 ${V[0]} 百分位）`;   // 和頁首一年位置同一個數字
  const ex = [k === 'pe' ? '本卡的 EPS 由官方本益比反推（收盤 ÷ 本益比），和季報卡的近 4 季 EPS（財報累計相減）算法不同，數字可能略有差異。' : '',   // 第 42 輪 F42-6（D109 = A）
    B.s.some(x => x[1] == null) ? `線斷開 = 當時${k === 'pe' ? '近 4 季 EPS ≤ 0，官方不計算本益比' : '官方沒有淨值比'}` : '',
    data.industry === '金融保險' ? '金融業獲利受利率、匯率影響較大，常搭配淨值比觀察' : '', k === 'pe' && f.pe > 100 ? 'EPS 很小時本益比會很大，倍數線間距很寬' : ''];
  const lg = B.k.map((x, i) => `<span class="lg"><i class="${BAND_STY[i][0] ? 'dash' : BAND_STY[i][1] > 1 ? 'mid' : ''}"></i>第 ${BAND_PCT[i]} 百分位 ${fmt(x, 2)} 倍</span>`).reverse().join('');
  const short = '倍數是用近一年的資料算的，不代表股價會回到某條線';                      // 短句用變數：test_iter13 數 noteHTML 字面呼叫
  box.innerHTML = `<div class="kleg" id="bandL"></div><div id="bandC" class="chart-box" style="height:220px"></div>
    <div class="kleg band-lg">${lg}<span class="lg"><i class="cl"></i>收盤（原始價）</span></div>
    <div class="small">${md(f.date)} 收盤 ${pfmt(close)} 元 = ${base} ${fmt(close / f[k], 2)} 元 × ${fmt(f[k], 2)} 倍${pos}</div>
    ${ex.filter(Boolean).map(t => `<div class="muted small">${t}</div>`).join('')}<div class="muted small" style="margin-top:6px">${noteHTML(short, BAND_NOTE(k, B.n))}</div>`;
  if (!LC || !T.length) return;
  const dt = t => typeof t === 'string' ? t : [t.year, t.month, t.day].map(x => String(x).padStart(2, '0')).join('-');
  const c = LC.createChart($('#bandC'), { autoSize: true, handleScroll: false, handleScale: false,
    layout: { background: { type: 'solid', color: 'transparent' }, textColor: css('--text2'), fontSize: 11, attributionLogo: false },
    grid: { vertLines: { visible: false }, horzLines: { color: css('--border') } },
    rightPriceScale: { borderVisible: false, minimumWidth: 76, entireTextOnly: true },
    timeScale: { borderVisible: false, fixLeftEdge: true, fixRightEdge: true,
      tickMarkFormatter: (t, type) => { const [y, m, d] = dt(t).split('-').map(Number); return type === 0 ? String(y) : type === 1 ? `${m}月` : `${m}/${d}`; } },
    localization: { locale: 'zh-TW', timeFormatter: t => dt(t).split('-').join('/') } });
  const px = { type: 'custom', minMove: 0.01, formatter: pfmt };
  const add = (vals, color, st, w) => c.addLineSeries({ color, lineStyle: st, lineWidth: w, priceFormat: px, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false })
    .setData(vals.map((v, i) => v == null ? { time: T[i] } : { time: T[i], value: v }));
  B.k.forEach((x, i) => add(E.map(e => e == null ? null : e * x), css('--blue'), ...BAND_STY[i]));   // 虧損期間 null：線斷開，不補值
  add(C, css('--text'), 0, 2);
  charts = [c];
  c.timeScale().fitContent();
  const show = i => { $('#bandL').innerHTML = `<span><b>${md(T[i])}</b></span><span>收 <b>${pfmt(C[i])}</b></span><span>${base} <b>${E[i] == null ? '--' : fmt(E[i], 2) + ' 元'}</b></span>` +
    `<span>${nm}約 <b>${C[i] == null || E[i] == null ? '--' : fmt(C[i] / E[i], 2) + ' 倍'}</b></span>`; };
  c.subscribeCrosshairMove(p => { const i = p.logical == null ? -1 : Math.round(p.logical); show(p.time !== undefined && i >= 0 && i < T.length ? i : T.length - 1); });
  show(T.length - 1);
}

const STOCK_TABS = [['k', '走勢'], ['chip', '籌碼'], ['fund', '基本面']];
const ETF_TABS = STOCK_TABS.slice(0, 2);       // 第 15 輪 F15-2：ETF 個股頁沒有基本面
// 第 15 輪 F15-2：ETF 個股頁的價格說明（原始價）。短句一定可見，完整說明收合（短句用變數：test_iter13 數 noteHTML 字面呼叫）
// 第 36 輪 F36-4：除息日改用官方除息表（「息」），上櫃也標；「息?」「調?」只留給除息表沒有的推測調整
const ETF_NOTE = m => { const short = `價格未還原除息：配息 ETF 在除息日會向下跳空，不是當天下跌；圖上「息」是官方除息日${m === 'TWSE' ? '，「息?」「調?」是推測的其他價格調整' : ''}`;
  return noteHTML(short, '本頁價格是證交所、櫃買中心公布的原始成交價，沒有依除息調整。配息 ETF 除息日的開盤參考價會扣掉配息，K 線會向下跳空；均線、MACD 與 52 週高低也用原始價計算，除息日前後會失真，所以本頁不提供技術面訊號。' +
  '除息日來自證交所、櫃買中心的除息表，標成「息」，十字線列出前收與參考價；除息日的漲跌顯示「不比價」，週、月 K 用參考價 ÷ 前收換算。' +
  '上市 ETF：除息表沒有的價格調整日（「收盤 − 官方漲跌」和前一日收盤不同），本站標成「息?」（官方漲跌 0）或「調?」（漲跌不是 0，多為分割），只是推測，也可能是合併或資料更正。' +
  '上櫃 ETF：除息表以外的價格調整（如分割）本站無法辨識，不標示。'); };

// 第 25 輪 D25-05：產業鏈、概念股標籤只顯示前 2 個，其餘收在「+N」（點了展開，展開後按「收合」收回）
// 第 27 輪 D27-07：融資融券子圖一次只畫一條線（右側刻度就是這條線）；借券只在有資料時可選
const mgView = G => { const v = localStore('mgv', 'mb'); return v === 'sb' || (v === 'lb' && G?.lb) ? v : 'mb'; };
// 第 42 輪 F42-3：產業、產業鏈、概念股標籤點了跳泡泡圖並展開該族群；名稱不在 groups 時維持原本不可點的 <span>
const GRP_NM = { industry: '類股', concept: '概念股' };
function grpTag(gk, gn, txt, t0 = '') {
  const c = gk === 'chain' ? 'pill chain' : 'pill';
  if (!(App.latest.groups && App.latest.groups[gk] || []).some(g => g.name === gn)) return `<span class="${c}"${t0 ? ` title="${t0}"` : ''}>${txt}</span>`;
  return `<a class="${c} grp" href="#/bubble" data-gk="${gk}" data-gn="${esc(gn)}" title="${gk === 'chain' ? `${t0}（點了看泡泡圖「${esc(gn)}」整條產業鏈）` : `看泡泡圖「${esc(gn)}」${GRP_NM[gk]}`}">${txt}</a>`;
}
const tagFold = t => t.slice(0, 2).join('') + (t.length > 2 ? `<span class="tag-rest" hidden>${t.slice(2).join('')}</span><button class="pill more" id="tagMore" data-n="+${t.length - 2}">+${t.length - 2}</button>` : '');

// 第 42 輪 F42-4：ETF 頁頭的配息、成交額卡（數字同 ETF 列表，來源 latest.json 的 etfs.rows；近一年配息為 0 或沒有時不顯示配息三張）
const etfCards = E => [...E.dvc ? [['近一年配息', E.dvc.toLocaleString('zh-TW', { maximumFractionDigits: 4 }) + ' 元', '', '每單位，近 365 天合計'],
    ['配息率', E.c > 0 ? fmt(E.dvc / E.c * 100, 2) + '%' : '--', '', E.c > 0 ? '近一年配息 ÷ 今日收盤；股價下跌時會變高' : '今天無成交'],
    ['最近除息', E.dvd ? md(E.dvd) : '--', '', E.dvd ? (E.dvn != null ? E.dvn + ' 天填息' : E.dvx ? '中斷' : '未填息') : '']] : [],
  ['成交額', E.tv == null ? '--' : fmt(E.tv, 2) + ' 億', '', '當日']];
const cardsHTML = a => a.map(([l, v, c, sub]) => `<div class="card stat"><div class="l">${l}</div><div class="v num ${v === '0億' ? 'flat' : c || ''}" style="font-size:16px">${v}</div>${sub ? `<div class="s">${sub}</div>` : ''}</div>`).join('');
// 第 28 輪 D28-01：籌碼分頁的圖表區間（只在這次瀏覽記住，不存 localStorage）；第 29 輪 F29-3：預設改 20 個交易日
const CHIP_N = [['20', '20 日'], ['60', '60 日'], ['120', '120 日'], ['all', '全部']];
let chipN = '20';
// 第 29 輪 F29-1：法人圖一次看一種法人的每日買賣超（預設外資；只在這次瀏覽記住）
const CHIP_I = [['f', '外資'], ['t', '投信'], ['dl', '自營'], ['net', '合計']];
let chipI = 'f';

window.renderStock = async function (code, sub) {
  const E = !App.latest.stocks[code] && App.latest.etfs?.rows?.[code];   // 第 15 輪 F15-2：ETF 個股頁（頁首用 etfs.rows，資料 data/etfp/）
  const s = App.latest.stocks[code] || E || undefined;
  let data;
  try { data = await loadStock(code, E ? 'etfp' : 'stocks'); }
  catch (e) { $('#view').innerHTML = `<div class="empty">找不到 ${esc(code)} 的資料。可用上方搜尋框查代號或名稱，或<a href="#/today" style="color:var(--blue)">回今日</a></div>`; return; }
  const P = data.prices, n = P.d.length;
  document.title = `${data.name} ${code}｜台股資金流`;   // 第 27 輪 D27-10
  const last = n - 1;
  // 最新一天沒成交（開高低收為 --）時，改顯示最後成交日的收盤，不算漲跌
  const traded = P.c.map((c, i) => c != null ? i : -1).filter(i => i >= 0);
  const dvLast = (data.dv || []).find(r => r.d === P.d[last]);        // 第 36 輪 F36-4：ETF 最新一天是官方除息日（上櫃官方漲跌為空，收盤 − 前收會含配息）
  const lt = traded.at(-1) ?? last, noTrade = lt !== last, gxLast = (data.gx || []).includes(P.d[last]) || !!dvLast;   // gxLast：最新一天是價格調整日（官方不比價）
  const close = P.c[lt];
  const prevClose = P.c[traded.at(-2)] ?? null;
  // 優先用官方漲跌價差（除權息日「收盤 − 昨收」會失真）
  const change = noTrade || gxLast ? null : s?.ch ?? (prevClose != null ? close - prevClose : null);
  const pct = noTrade || gxLast ? null : s?.p ?? (change != null && prevClose ? change / prevClose * 100 : null);
  const prev = noTrade ? close : change != null ? close - change : prevClose;   // 昨收（參考價）
  const mode = localStore('kmode', '日');
  const adjMode = localStore('kadj', '還原');
  const fund = data.fund || {};
  // P16：股本變動事件 90 天內，本益比與殖利率加註
  const cap = data.capchg, capSub = cap ? `${md(cap.d)} ${evName((data.ev || []).find(e => e.d === cap.d) || cap)}，官方值可能尚未調整` : '';
  // P9：本益比、殖利率卡的資料日（與 P16 註記並列）；值為空時說明是官方未提供
  // 第 10 輪 P24：淨值比卡也標資料日（cap = false：股本變動註記照舊只在本益比、殖利率卡）
  const fundSub = (v, cap = true) => [v == null && fund.date ? '官方未提供' : '', fund.date ? '資料 ' + md(fund.date) : '', cap ? capSub : ''].filter(Boolean).join('；');
  // 第 9 輪 F9-4（B7）：估值一年位置；股本變動、虧損、無股利、新上市時匯出沒有該欄
  const VAL = data.val;
  const valSub = (k, v) => { const x = VAL?.[k]; if (!x || v == null) return '';
    const [p, lo, hi] = x, f = n => fmt(n, 2) + (k === 'dy' ? '%' : '');
    return `一年位置 ${v <= lo ? '最低' : v >= hi ? '最高' : p + '%'}（${f(lo)}～${f(hi)}）${k === 'dy' && v > lo && v < hi ? '<br>越高 = 殖利率相對越高' : ''}`; };   // 第 14 輪 F14-4
  const subs = (...a) => a.filter(Boolean).join('<br>');
  // 第 10 輪 B5：季報（沒有任何季報的股票沒有 fin）；近 4 季 EPS 明顯高於一年前（一年前 ≤ 0 且現在 > 0，或 ≥ 1.5 倍）時加獲利說明一行
  const F = data.fin;
  const finUp = F && isNum(F.e4) && isNum(F.e4p) && F.e4 > 0 && (F.e4p <= 0 || F.e4 >= F.e4p * 1.5);
  const watching = App.watch.has(code);
  // 第 22 輪 F22-12：這檔的近期新訊號（文字共用 app.js 的 hlTag；舊 app.js 沒有 hlTag 或不認得的種類不列；ETF 沒有 hl）
  const HL = typeof hlTag === 'function' ? (s?.hl || []).filter(e => HL_KINDS[e[0]]) : [];
  // 第 25 輪 D25-08：網址有分頁就用網址的；換一檔股票時從「走勢」開始
  if (STOCK_TABS.some(t => t[0] === sub)) localStore('stockTab', null, sub); else if (App.stockCode !== code) localStore('stockTab', null, 'k');
  App.stockCode = code;
  const tab0 = pageTab('stockTab', STOCK_TABS), tab = E && tab0 === 'fund' ? 'k' : tab0;   // 分頁：走勢／籌碼／基本面（頁首永遠顯示）；第 15 輪：ETF 沒有基本面
  if (sub && sub !== tab) history.replaceState(history.state, '', `#/stock/${code}/${tab}`);   // 第 28 輪 D28-08：不認得的分頁（ETF 的 fund）補成實際顯示的分頁
  const fd = md(App.latest.flow_date);
  // 第 15 輪：ETF 的 52 週高低由原始價計算（和匯出端 h52 同樣取資料日往前 365 天）
  const w0 = new Date(Date.parse(P.d[last]) - 365 * 864e5).toISOString().slice(0, 10), inW = (x, i) => x != null && P.d[i] >= w0;
  const eHL = E && P.h.some(inW) ? [Math.max(...P.h.filter(inW)), Math.min(...P.l.filter(inW))] : [];
  const hlFrom = E ? (P.d[0] > w0 ? P.d[0] : null) : s?.hf ?? App.latest.hl_from;          // null → 已滿 52 週
  const hlSub = hlFrom ? '自 ' + hlFrom.replaceAll('-', '/') : '';
  // B2：融資融券指標卡。margin 不存在 = 尚無融資融券資料（不顯示）；null = 不在信用交易清單
  const MG = data.margin;
  const mgNote = MG?.nt && data.market === 'TWSE' ? [...MG.nt].map(ch => MARGIN_NOTE[ch]).filter(Boolean).join('、') : '';
  const mgCards = MG === undefined ? [] : MG === null ? [['信用交易', '無信用交易', 'flat', '不在融資融券清單']]
    : [['融資餘額', fmt(MG.mb) + ' 張', '', subs(`1日 ${sgn(MG.m1, 0)}　5日 ${MG.m5 == null ? '--' : sgn(MG.m5, 0)}`, !E && runTxt(balStreak(data.mg, P.d, 'mb', MG.d), '增', '減'))],
       ['融券餘額', fmt(MG.sb) + ' 張', '', `1日 ${sgn(MG.s1, 0)}`],
       ['券資比', MG.sr == null ? '--' : fmt(MG.sr, 2) + '%', '', ''],
       ['融資使用率', MG.mu == null ? '--' : fmt(MG.mu, 2) + '%', '', mgNote ? '次一營業日' + mgNote : '']];   // 第 28 輪 D28-01：資料日寫在組標題
  // 第 11 輪 B14：借券賣出（張；占股本用目前股數）。sbl 不存在 = 該市場最新借券日沒有這檔
  const SL = data.sbl;
  // 第 12 輪 B11：市值、週轉率（目前股數）
  const MT = data.mt, mcTxt = v => v >= 1e4 ? fmt(v / 1e4, 2) + ' 兆' : fmt(v, v >= 100 ? 0 : 1) + ' 億';
  const mtCards = E ? etfCards(E) : [['市值', MT?.mc == null ? '--' : mcTxt(MT.mc), '', MT ? '收盤 × 目前發行股數' : '沒有發行股數資料'],
    ['週轉率', MT?.to == null ? '--' : fmt(MT.to, 2) + '%', '', MT ? `${MT.d !== P.d[last] ? md(MT.d) + '，' : ''}成交股數 ÷ 目前發行股數` : '沒有發行股數資料']];
  // 頁首關鍵數字列：寬螢幕每個分頁都併進頁首卡，切換分頁時頁首不變（手機只在走勢分頁、放 K 線卡下方）
  const kvCards = [
         [hlFrom ? '區間高' : '52週高', pfmt(E ? eHL[0] : s?.h52), '', hlFrom ? hlSub + (E ? '，原始價' : '，還原') : E ? '原始價' : '還原權值'],
         [hlFrom ? '區間低' : '52週低', pfmt(E ? eHL[1] : s?.l52), '', hlFrom ? hlSub + (E ? '，原始價' : '，還原') : E ? '原始價' : '還原權值'],
         ...E ? [] : [['本益比', fmt(fund.pe, 2), '', fundSub(fund.pe)], ['殖利率', fund.dy != null ? fmt(fund.dy, 2) + '%' : '--', '', fundSub(fund.dy)], ['法人5日', yi(s?.n5), cls(s?.n5), '至 ' + fd]], ...mtCards];
  const slCards = !SL ? [] : [['借券賣出餘額', fmt(SL.lb) + ' 張', '', subs(`1日 ${sgn(SL.l1, 0)}　5日 ${SL.l5 == null ? '--' : sgn(SL.l5, 0)}`, !E && runTxt(balStreak(data.mg, P.d, 'lb', SL.d), '增', '減'))],
    ...E ? [] : [['借券占股本', SL.lp == null ? '--' : fmt(SL.lp, 2) + '%', '', SL.lx == null ? '' : `融券的 ${fmt(SL.lx, 1)} 倍`]]];
  // 第 28 輪 D28-01：籌碼分頁分三組，日期寫在組標題一次；每組下方是同主題的時間序列圖（張），區間共用
  // 第 29 輪 F29-4：外資及陸資持股比率（最近有資料的那天；5 日、20 日變化是百分點）
  const FH = data.fh, fj = FH ? FH.map((v, i) => v == null ? -1 : i).filter(i => i >= 0).pop() : undefined;
  const fhd = k => fj - k >= 0 && FH[fj - k] != null ? sgn(FH[fj] - FH[fj - k], 2) : '--';
  const inCards = E ? [] : [['法人1日', yi(s?.n1), cls(s?.n1), runTxt(s?.s, '買', '賣')], ['法人5日', yi(s?.n5), cls(s?.n5), `自營 ${yi(s?.d5)}`],
    ['外資5日', yi(s?.f5), cls(s?.f5), runTxt(s?.fs, '買', '賣')], ['投信5日', yi(s?.t5), cls(s?.t5), runTxt(s?.ts, '買', '賣')],
    ...fj == null ? [] : [['外資持股比率', fmt(FH[fj], 2) + '%', '', subs(`<span class="nw">5日 ${fhd(5)}</span>　<span class="nw">20日 ${fhd(20)}</span>（百分點）`, md(P.d[fj]) !== fd ? md(P.d[fj]) : '')]]];
  const chipSec = (h, note, cards, chart, foot = '') => !cards.length ? '' : `<section class="sec card chip-g"><div class="sec-h"><h2>${h}</h2><span class="muted small">${note}</span></div>
      <div class="metrics kv">${cardsHTML(cards)}</div>${chart}${foot}</section>`;
  const chLeg = (t, id, h) => `<div class="ch-label">${t}<span id="${id}L" style="display:contents"></span></div><div id="${id}" class="chart-box" style="height:${h}px"></div>`;
  const GK = data.mg?.k ? '，面額變更、減資前依官方換算' : '';
  const SH = data.sh && data.sh.d.length ? data.sh : null, shN = SH ? SH.d.length : 0;   // 第 43 輪 F43-3：集保股權分散（每週）

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
      '</tbody></table></div><div class="muted small note-dup" style="margin-top:6px">' + noteHTML('張數增減包含申購贖回的影響，不一定代表看好', '張數增減包含申購贖回的影響：申購多的日子，經理人會用申購資金加碼，不一定代表看好（可對照持股頁的「單位數 1 日」）。權重為占該 ETF 淨資產 %，含股價漲跌影響。') + '</div></section>');

  $('#view').innerHTML = `
    <section class="sec card">
      <div class="s-head">
        <div>
          <div class="s-nm"><span class="s-name">${esc(data.name)}</span><span class="s-code">${code}</span></div>
          <div class="s-px"><span class="s-price num ${cls(change)}${!noTrade && !gxLast && s?.lm ? ' lm' : ''}">${pfmt(close)}</span>
            ${noTrade ? '<span class="s-chg flat">無成交</span>' : gxLast ? (dvLast ? '<span class="s-chg flat" title="除息日的開盤參考價扣掉配息，收盤減前一日收盤會含配息">不比價（今天除息）</span>'
              : '<span class="s-chg flat" title="官方漲跌為 0、收盤和前一日收盤不同：推測是除息等價格調整">不比價（推測價格調整）</span>')
              : `<span class="s-chg num ${cls(change)}">${change > 0 ? '▲' : change < 0 ? '▼' : ''} ${pfmt(Math.abs(change ?? 0))} (${sgn(pct)}%)</span>`}
            ${!noTrade && !gxLast && s?.lm ? `<span class="small ${s.lm > 0 ? 'up' : 'dn'}" style="white-space:nowrap" title="收盤等於本站依參考價推算的${s.lm > 0 ? '漲停價' : '跌停價'}">${s.lm > 0 ? '收在漲停價' : '收在跌停價'}</span>` : ''}
            ${!noTrade && s?.rel ? `<span class="muted small">相對 ${md(s.rel)} 收盤（前一交易日無成交）</span>` : ''}</div>
          <div class="tags">
            ${(data.alerts || []).map(a => a.t === 'disposal'
              ? `<span class="pill al-d" title="${esc(`處置期間 ${md(a.s)}～${md(a.e)}（${md(a.a)} 公告）\n原因：${a.r || '--'}\n措施：${a.m || '--'}`)}">${a.s > App.latest.date ? `即將處置（${md(a.s)} 起）` : `處置中（至 ${md(a.e)}）`}</span>`
              : `<span class="pill al-n" title="${esc(`${md(a.a)} 公布注意交易資訊\n${a.r || ''}`)}">注意</span>`).join('')}${nxTag(data.nx, code, E)}
            <span class="pill">${data.market === 'TWSE' ? '上市' : '上櫃'}</span>${E ? '<span class="pill">ETF</span>' : grpTag('industry', data.industry, esc(data.industry))}
            ${E && App.latest.holdings?.[code] ? `<a class="pill hold" href="#/etf/${code}">持股 →</a>` : ''}
            ${tagFold([...(data.chains || []).map(([chain, seg, subs]) => grpTag('chain', chain, `${esc(chain)} › ${esc(subs.length ? subs.slice(0, 2).join('、') + (subs.length > 2 ? '…' : '') : seg)}`,
              `${esc(chain)} › ${esc(seg)}${subs.length ? '：' + esc(subs.join('、')) : ''}`)),
            ...(data.concepts || []).map(c => grpTag('concept', c, esc(c)))])}
            <span class="muted small">${noTrade ? `${P.d[last]} 無成交，顯示 ${P.d[lt]} 收盤` : `${P.d[last]} 收盤`}</span>
            ${dvLast ? `<span class="muted small">今天除息，每單位配息 ${dfmt(dvLast.c)} 元，除息前收盤 ${pfmt(dvLast.p)}</span>` : ''}
          </div>
          ${HL.length ? `<div class="s-hl"><a class="muted small" href="#/rank/hl">近期新訊號 →</a>${HL.map(hlTag).join('')}<span class="muted small">只描述發生了什麼，不代表之後的走勢</span>${HL.length > 1 ? `<button class="pill more hl-more" id="hlMore">+${HL.length - 1}</button>` : ''}</div>` : ''}
          <div class="s-ohlc small num muted"><span class="nw">開 <b>${pfmt(P.o[last])}</b></span>　<span class="nw">高 <b class="up">${pfmt(P.h[last])}</b></span>　<span class="nw">低 <b class="dn">${pfmt(P.l[last])}</b></span>　<span class="nw">昨收 <b>${pfmt(prev)}</b></span>　<span class="nw">量 <b>${fmt(P.v[last])}</b> 張</span></div>
        </div>
        <button class="star ${watching ? 'on' : ''}" id="starBtn">${watching ? '★ 已加入自選' : '☆ 加入自選'}</button>
        <a class="tl-go" href="#/tools/dt?c=${code}">試算</a>
      </div>
      ${tab !== 'k' && matchMedia('(min-width:721px)').matches ? `<section class="sec metrics kv">${cardsHTML(kvCards)}</section>` : ''}
    </section>

    ${pageTabsHTML('stockTabSeg', E ? ETF_TABS : STOCK_TABS, tab)}
    ${tab === 'chip' ? '' : `<section class="sec metrics${tab === 'k' ? ' kv' : ' m3'}">
      ${cardsHTML(tab === 'k' ? kvCards
        : [['本益比', fmt(fund.pe, 2), '', subs(fundSub(fund.pe), valSub('pe', fund.pe))], ['股價淨值比', fmt(fund.pb, 2), '', subs(fundSub(fund.pb, false), valSub('pb', fund.pb))],
         ['殖利率', fund.dy != null ? fmt(fund.dy, 2) + '%' : '--', '', subs(fundSub(fund.dy), valSub('dy', fund.dy))]])}
    </section>`}
    ${tab === 'chip' ? `<div class="sec chip-rng"><span class="muted small">圖表區間</span>${segHTML('chipSeg', CHIP_N, chipN)}</div>
    ${chipSec('法人買賣超', `${fd}，億，估算（張數 × 收盤）`, inCards, chLeg(E ? '收盤（原始價）' : '收盤（還原）', 'cpC', 64) + `<div class="chip-inv">${segHTML('chipInv', CHIP_I, chipI)}</div>` + chLeg('每日買賣超（張，未還原）', 'ciC', 120) +
      chLeg('<span id="cuCT">區間累計（張）</span>', 'cuC', 72), '<div class="muted small val-note">累計線的高度取決於起算日，看斜率不看高度；最近每天的買賣看上方柱狀圖。</div>' +
      (FH ? chLeg('外資及陸資持股比率（%，以當日發行股數為分母，增資、減資時會跳動）', 'fhC', 90) : ''))}
    ${SH ? chipSec('股權分散', `資料日 ${md(SH.d[shN - 1])}（每週一次，集保結算所）`, shCards(SH, E), shN >= 2 ? chLeg('持股比例（%，每週）', 'shC', 110) +
      chLeg(`${E ? '受益' : '股東'}人數（人，每週）`, 'snC', 90) : `<div class="muted small">自 ${md(SH.d[0])} 起收錄，累積 2 週後顯示走勢。</div>`,
      `<div class="muted small val-note">${SH_NOTE[E ? 1 : 0]}</div>`) : ''}
    ${chipSec('信用交易', MG ? md(MG.d) : '', mgCards, data.mg ? chLeg(`融資餘額（張${GK}）`, 'cmC', 110) : '')}
    ${chipSec('借券賣出', SL ? `${md(SL.d)}，晚上 8 點半以後更新` : '', slCards, data.mg?.lb ? chLeg(`借券賣出餘額（張${GK}）`, 'clC', 110) : '',
      `<div class="muted small val-note">借券賣出包含避險、套利（例如 ETF、權證、可轉債避險），不等於看空，只能當作空方部位的上限。${E ? '' : '占股本以目前發行股數計算。'}</div>`)}
    ${acHTML}` : tab === 'fund' ? `${VAL ? `<div class="muted small val-note">${noteHTML('獲利大增時本益比會落到一年低點，位置低不代表股價便宜', `一年位置 = 近 ${App.latest.valuation?.TWSE?.days ?? 242} 個交易日中，官方值小於或等於今天的天數比例（資料 ${md(VAL.d)}）。本益比 = 股價 ÷ 近 4 季 EPS，位置也反映獲利變化：獲利下降時本益比會升高；獲利大增時本益比（淨值比也可能）會落到一年低點，例如景氣循環股在獲利高峰，不代表股價便宜。${F ? '請對照下方季報卡的近 4 季 EPS 與一年前比較。' : ''}`)}</div>` : ''}
    ${finUp ? `<div class="small val-note fin-note">近 4 季 EPS 一年前 ${fmt(F.e4p, 2)} 元 → 現在 ${fmt(F.e4, 2)} 元（${F.e4p <= 0 ? '轉盈' : fmt(F.e4 / F.e4p, 1) + ' 倍'}）：本益比會因獲利增加而下降，位置低不代表股價便宜；請看下方季報卡的單季 EPS 是否已經轉弱。</div>` : ''}
    ${bandHTML(data, capSub)}
    <section class="sec grid ${F ? 'g2' : 'g-one'}">
      <div class="card"><div class="sec-h"><h2>月營收</h2><span class="sp"></span><span id="revSegBox"></span></div><div id="revBox"></div></div>
      ${F ? `<div class="card"><div class="sec-h"><h2>季報</h2><span class="muted small">${qName(F.q.at(-1)[0])}${F.c.fs ? `｜本站收錄 ${md(F.c.fs)}` : ''}｜${FIN_TBL[F.t] || ''}</span></div><div id="finBox"></div></div>` : ''}
    </section>
    ${data.dv ? divHTML(data.dv, data.market, P) : ''}` : `

    <section class="sec card">
      <div class="sec-h">
        ${segHTML('kSeg', [['日', '日'], ['週', '週'], ['月', '月']], mode)}
        ${E ? '' : segHTML('adjSeg', [['還原', '還原'], ['原始', '原始']], adjMode)}
        <button class="seg" id="latestBtn" style="padding:4px 12px;font-size:12px">回到最新</button>
        <span class="sp"></span><span class="muted small hint">拖曳平移、滾輪縮放</span>
      </div>
      ${E ? `<div class="muted small val-note">${ETF_NOTE(E.m)}</div>` : ''}
      <div class="kleg" id="kLegend"></div>
      <div id="kC" class="chart-box" style="height:320px"></div>
      <div class="ch-label">成交量（張，未還原）</div>
      <div id="vC" class="chart-box" style="height:80px"></div>
      ${E ? '' : `<div class="ch-label">三大法人買賣超（張，未還原）<span id="iLegend" style="display:contents"></span></div>
      <div id="iC" class="chart-box" style="height:90px"></div>`}
      ${data.mg ? `<div class="ch-label mg-l">${segHTML('mgSeg', [['mb', '融資'], ['sb', '融券'], ...data.mg.lb ? [['lb', '借券賣出']] : []], mgView(data.mg))}<span id="gUnit"></span><span id="gLegend" style="display:contents"></span></div>
      <div id="gC" class="chart-box" style="height:90px"></div>` : ''}
      <div class="ch-label">${E ? '' : segHTML('oscSeg', OSC_OPTS, localStore('osc', 'MACD'))}<span id="oscLeg" style="display:contents"></span></div>
      <div id="mC" class="chart-box" style="height:120px"></div>
    </section>

    ${data.pf ? perfHTML(data.pf, data.market, noTrade ? P.d[lt] : null) : ''}
    ${E && data.epf ? perfHTML(data.epf, data.market, noTrade ? P.d[lt] : null, data.code) : ''}
    ${E ? divHTML(data.dv || [], data.market, P, true) : '<section class="sec card"><div class="sec-h"><h2 id="sigTitle">技術面訊號</h2></div><div id="sigBox"></div></section>'}`}`;   // 第 36 輪 F36-2

  const ptab = $('#view .page-tabs'), topH = () => $('.top').offsetHeight;   // 第 30 輪 D30-01
  ptab.classList.add('pt-stick');
  ptab.insertAdjacentHTML('beforeend', `<span class="pt-nm">${esc(data.name)} <b class="num ${cls(change)}">${pfmt(close)}</b>${noTrade || pct == null ? '' : ` <span class="num ${cls(change)}">${sgn(pct)}%</span>`}</span>`);
  new IntersectionObserver(([e]) => ptab.classList.toggle('stuck', !e.isIntersecting), { rootMargin: `-${topH()}px 0px 0px 0px` }).observe($('#view .s-head'));
  if (App.ptStuck) { App.ptStuck = false; ptab.style.position = 'static'; const y = ptab.getBoundingClientRect().top + scrollY; ptab.style.position = ''; scrollTo(0, y - topH()); }   // 固定狀態換分頁：新分頁從分頁列下方開始
  const dvh = [...document.querySelectorAll('#view .sec-h h2')].filter(h => h.textContent === (E ? '配息與填息' : '股利與填息'))[0];   // 第 39 輪 F39-3：連結加在 divHTML 外，卡片字面不變
  if (dvh) dvh.insertAdjacentHTML('afterend', `<span class="sp"></span><a class="small dv-go" href="#/tools/dv?c=${code}">試算 →</a>`);
  if (dvh && data.nx) dvh.parentElement.insertAdjacentHTML('afterend', data.nx.map(n => `<div class="small dv-nx">${esc(nxText(n, E))}</div>`).join(''));   // 第 40 輪 F40-3：卡片標題列下一行
  const pfh = [...document.querySelectorAll('#view .sec-h h2')].filter(h => h.textContent === (E ? '近期表現（含息）' : '近期表現'))[0];   // 第 48 輪 F48-4：連結加在 perfHTML 外，卡片字面不變
  if (pfh) pfh.parentElement.insertAdjacentHTML('beforeend', `<span class="sp"></span><a class="small cmp-go" href="#/compare/${code}">比較 →</a>`);
  onSeg('stockTabSeg', v => { App.ptStuck = $('#view .s-head').getBoundingClientRect().bottom <= topH(); localStore('stockTab', null, v); history.replaceState(null, '', `#/stock/${code}/${v}`); window.disposeStockCharts(); window.renderStock(code); });
  $('#hlMore')?.addEventListener('click', e => e.currentTarget.parentElement.classList.add('open'));
  $('#tagMore')?.addEventListener('click', e => { const r = $('#view .tag-rest'), b = e.currentTarget; r.hidden = !r.hidden; b.textContent = r.hidden ? b.dataset.n : '收合'; });
  $('#view .tags').addEventListener('click', e => { const a = e.target.closest('a[data-gk]');   // 第 42 輪 F42-3：切到該分組、展開該族群，再由連結跳 #/bubble
    if (a) { setGroup(a.dataset.gk); localStore('focus', null, a.dataset.gn); Object.assign(App, { blOpen: a.dataset.gn, blAll: false, blJump: 1 }); } });
  $('#starBtn')?.addEventListener('click', () => {
    App.watch.has(code) ? App.watch.delete(code) : App.watch.add(code);
    saveWatch();
    const on = App.watch.has(code);
    $('#starBtn').classList.toggle('on', on);
    $('#starBtn').textContent = on ? '★ 已加入自選' : '☆ 加入自選';
  });
  if (tab === 'fund') { renderRevenue(data.revenue); if (F) renderFin(F); }
  if (tab === 'fund' && F && data.bs) renderBs(data.bs, F);                           // 第 52 輪 F52-5：季報卡加一排 3 格（資產負債表）
  if (tab === 'fund' && data.band) { renderBand(data, bandView(data));                // 第 37 輪 F37-3：本益比／淨值比切換
    onSeg('bandSeg', v => { localStore('bandV', null, v); document.querySelectorAll('#bandSeg button').forEach(b => b.classList.toggle('on', b.dataset.v === v)); renderBand(data, v); }); }
  if (tab === 'chip') onSeg('chipSeg', v => { chipN = v; document.querySelectorAll('#chipSeg button').forEach(b => b.classList.toggle('on', b.dataset.v === v)); buildChip(data, E); });
  if (tab === 'chip' && $('#chipInv')) onSeg('chipInv', v => { chipI = v; document.querySelectorAll('#chipInv button').forEach(b => b.classList.toggle('on', b.dataset.v === v)); buildChip(data, E); });
  if (tab === 'chip') buildChip(data, E);
  if (tab !== 'k') return;
  if (!E && data.mn) { $('#view').insertAdjacentHTML('beforeend', mnCard(data.mn, code)); $('#mnMore')?.addEventListener('click', mnShowAll); }   // 第 53 輪 F53-5：走勢分頁最下方
  // 第 25 輪 D25-05：關鍵數字列在寬螢幕併進頁首卡、手機放到 K 線卡下方，主圖進第一屏
  if (matchMedia('(min-width:721px)').matches) $('#view .s-head').after($('#view .metrics.kv')); else $('#vC').after($('#view .metrics.kv'));   // 第 27 輪 D27-06：手機放在主圖下方；第 28 輪 D28-05：改到成交量之後，K 線和成交量相鄰、十字線不斷開
  if (!E) $('#adjSeg').title = '還原：依除權息、減資、面額變更調整歷史價格（現金增資除權也依官方參考價調整），最新收盤不變。均線訊號與 52 週高低一律以還原價格計算';
  // 日／週／月與還原／原始切換都重畫；技術面訊號一律用還原價（P13）
  const draw = () => {
    const m = localStore('kmode', '日'), adj = !E && localStore('kadj', '還原') === '還原';   // ETF 一律原始價、沒有技術面訊號
    buildCharts(aggregate(data, m, adj), m, data.mg, adj, E ? 'MACD' : localStore('osc', 'MACD'), E);   // 第 18 輪 F18-1：子圖 MACD／KD／RSI
    if (!E) renderSignals(aggregate(data, m, true), m);
  };
  onSeg('kSeg', m => { localStore('kmode', null, m); document.querySelectorAll('#kSeg button').forEach(b => b.classList.toggle('on', b.dataset.v === m)); draw(); });
  if (data.mg) onSeg('mgSeg', v => { localStore('mgv', null, v); document.querySelectorAll('#mgSeg button').forEach(b => b.classList.toggle('on', b.dataset.v === v)); draw(); });
  if (!E) onSeg('oscSeg', v => { localStore('osc', null, v); document.querySelectorAll('#oscSeg button').forEach(b => b.classList.toggle('on', b.dataset.v === v)); draw(); });
  if (!E) onSeg('adjSeg', v => { localStore('kadj', null, v); document.querySelectorAll('#adjSeg button').forEach(b => b.classList.toggle('on', b.dataset.v === v)); draw(); });
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
// 第 19 輪 F19-1：「權」「權息」依匯出的 k 細分（s 沒有現增、c 只有現增、sc 股利＋現增）；沒有 k 照舊
const evName = e => e.t === '權' && e.k ? `除權（${{ s: '配股', c: '現金增資', sc: '配股＋現金增資' }[e.k]}）`
  : e.t === '權息' && /c/.test(e.k || '') ? '除權息（含現金增資）' : EV_LABEL[e.t];
const evMark = e => e.t === '權' && e.k === 'c' ? '現增' : e.t;
const CASH_INC_TIP = '現金增資除權：股東可依持股比例出錢認購新股（不是無償配股），參考價依認購價計算';

// ─── 日線 → 週線 / 月線（法人買賣超加總）；adj = 是否用還原價 ─────
function aggregate(data, mode, adj) {
  const P = data.prices, I = data.insti, G = data.mg;
  const ev = data.ev || (data.dv || []).map(r => ({ d: r.d, t: r.t, p: r.p, r: r.r }));   // 第 36 輪 F36-4：ETF 沒有 ev，官方除息（dv）當成「息」事件
  const af = adj ? adjFactors(P.d, ev) : P.d.map(() => 1);
  // F8-3：融資融券餘額；還原時乘上該日之後所有官方換算的 k（面額變更、減資），原始為官方原值
  const gk = d => adj && G?.k ? G.k.reduce((a, x) => x.d > d ? a * x.k : a, 1) : 1;
  const sc = (a, i) => a?.[i] == null ? null : Math.round(a[i] * gk(P.d[i]));
  const mgAt = i => ({ mb: sc(G?.mb, i), sb: sc(G?.sb, i), lb: sc(G?.lb, i) });   // 第 11 輪：借券（lb）同樣依官方換算
  const evAt = Object.fromEntries(ev.map(e => [e.d, e])), gx = new Set(data.gx || []);   // 第 15 輪：ETF 推測的價格調整日
  // 無成交的日子（開高低收為 --）以前一個收盤價畫一字線，時間軸保持連續；上市前的空值略過
  const rows = [];
  let prevC = null, lastD = null;
  P.d.forEach((d, i) => {
    const has = I?.f[i] != null;                     // ETF 沒有法人資料
    const inst = { f: has ? I.f[i] : null, t: has ? I.t[i] ?? 0 : null, dl: has ? I.dl[i] ?? 0 : null };
    inst.net = has ? I.n?.[i] ?? inst.f + inst.t + inst.dl : null;      // 第 24 輪 F24-8：官方合計；舊 JSON 沒有 n 時三者相加
    const e = evAt[d] ? [evAt[d]] : [];
    if (P.c[i] != null && P.o[i] != null) {
      const k = af[i], ch = P.ch?.[i] ?? null;
      // P14：上市前一個資料列無成交、中間沒有事件 → 漲跌相對最後成交日
      const rel = data.market === 'TWSE' && i && P.c[i - 1] == null && lastD
        && !ev.some(x => x.d > lastD && x.d <= d) ? lastD : null;
      rows.push({ d, o: P.o[i] * k, h: P.h[i] * k, l: P.l[i] * k, c: P.c[i] * k, v: P.v[i],
        ch: ch == null ? null : ch * k,                                         // 還原後的漲跌（元）
        pc: ch == null || P.c[i] === ch ? null : ch / (P.c[i] - ch) * 100,       // 漲跌幅以原始價計算（不受係數影響）
        rel, ev: e, gx: gx.has(d) && !e.length ? (ch == null ? '息?' : '調?') : '', ...inst, ...mgAt(i), nt: false });   // 第 36 輪：官方除息日不標推測
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
      g.gx = g.gx || r.gx;
      for (const k of ['f', 't', 'dl', 'net']) if (r[k] != null) g[k] = (g[k] ?? 0) + r[k];
      for (const k of ['mb', 'sb', 'lb']) if (r[k] != null) g[k] = r[k];   // 融資融券、借券：期間最後一個有值的餘額
    }
  }
  return [...out.values()];
}

// 第 19 輪 F19-2（Q19-3）：K 棒的 [漲跌, 漲跌幅 %, 係數]。日線用匯出值；週／月線含推測調整（gx）不比價；
// 原始價的週／月線含官方事件時，前一根收盤先乘上每筆（參考價 ÷ 前收）再相減，漲跌幅與還原價相同
function barChange(raw, i, mode, adj) {
  if (mode === '日') return [raw[i].ch, raw[i].pc, 1];
  if (raw[i].gx) return [null, null, 1];
  if (!i) return [0, 0, 1];
  const f = adj ? 1 : raw[i].ev.reduce((a, e) => a * e.r / e.p, 1), base = raw[i - 1].c * f;
  return [raw[i].c - base, (raw[i].c - base) / base * 100, f];
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

// 第 18 輪 F18-1：KD(9,3,3)、RSI(14)。和 twstock/export.py 的 calc_kd、calc_rsi 同一套公式（改一邊要改另一邊）
const OSC_OPTS = [['MACD', 'MACD'], ['KD', 'KD'], ['RSI', 'RSI']];
function calcKD(H, L, C, n = 9) {
  let K = 50, D = 50;
  const k = [], d = [];
  C.forEach((c, i) => {
    if (i < n - 1) { k.push(null); d.push(null); return; }
    const hh = Math.max(...H.slice(i - n + 1, i + 1)), ll = Math.min(...L.slice(i - n + 1, i + 1));
    const rsv = hh === ll ? 50 : (c - ll) / (hh - ll) * 100;
    K = K * 2 / 3 + rsv / 3; D = D * 2 / 3 + K / 3;
    k.push(K); d.push(D);
  });
  return { k, d };
}
function calcRSI(C, n = 14) {
  const out = C.map(() => null);
  let up = 0, dn = 0;
  for (let i = 1; i < C.length; i++) {
    const u = Math.max(C[i] - C[i - 1], 0), d = Math.max(C[i - 1] - C[i], 0);
    if (i <= n) { up += u / n; dn += d / n; } else { up = (up * (n - 1) + u) / n; dn = (dn * (n - 1) + d) / n; }
    if (i >= n) out[i] = up === 0 && dn === 0 ? 50 : dn === 0 ? 100 : 100 - 100 / (1 + up / dn);
  }
  return out;
}

// 第 33 輪 F33-1：週／月 K 事件標籤的位置（純函式）。items：[{x: K 棒中心, top: 標籤底邊的上限, w: 標籤寬}]，W：繪圖區寬（不含右側刻度）
// bars：[{l, r, y}] 每根 K 棒的左右範圍與最高價位置；標籤底邊也要在「標籤寬度範圍內每根 K 棒的最高點」之上（QA D33-QA-1）
// 水平置中、靠邊往內收；和已放好的標籤重疊時往上一層，還重疊就不顯示（只留箭頭，游標停在 K 棒上時資訊列有說明）；K 棒不在可見範圍回傳 null
function evLabelPos(items, W, bars = [], h = 18) {
  const done = [];
  return items.map(({ x, top, w }) => {
    if (x == null || top == null || x < 0 || x > W) return null;
    const left = Math.max(2, Math.min(x - w / 2, W - w - 2));
    const hits = t => done.filter(p => left < p.left + p.w + 4 && p.left < left + w + 4 && t < p.t + h + 2 && p.t < t + h + 2);
    const under = bars.filter(b => b.l < left + w && b.r > left).map(b => b.y - 2);
    let t = Math.max(Math.min(top, ...under) - h, 0);   // 碰到圖的上緣就貼齊上緣
    const near = hits(t);
    if (near.length) t = Math.min(...near.map(p => p.t)) - h - 2;   // 放到相撞標籤的上方一層
    if (t < 0 || hits(t).length) return null;
    done.push({ left, w, t });
    return { left: Math.round(left), top: Math.round(t) };
  });
}

function buildCharts(raw, mode, G, adj, osc = 'MACD', E = null) {
  disposeKCharts();
  $('#kC .ev-lbls')?.remove();   // 第 33 輪 F33-1：上一次的週／月 K 事件標籤
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
    layout: { background: { type: 'solid', color: 'transparent' }, textColor: text2, fontSize: 11, attributionLogo: logo },
    grid: { vertLines: { color: grid }, horzLines: { color: grid } },
    crosshair: { mode: LC.CrosshairMode.Normal },
    rightPriceScale: { borderVisible: false, minimumWidth: 76, entireTextOnly: true },   // 各圖刻度同寬，K 棒才會上下對齊；第 28 輪 D28-06：刻度文字放不下就不畫（不會只露半截）
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
  const kSer = kc.addCandlestickSeries({ upColor: UP, downColor: DN, borderUpColor: UP, borderDownColor: DN, wickUpColor: UP, wickDownColor: DN, priceFormat: priceFmt,
    lastValueVisible: false, priceLineVisible: false });
  // 第 27 輪 D27-06：最新價標籤依漲跌（日線 = 收盤對昨收，和頁首同色；週／月線 = 對上一根）上色，不依 K 棒（收盤對開盤）
  const [lastCh] = barChange(raw, raw.length - 1, mode, adj);
  kSer.createPriceLine({ price: C[C.length - 1], color: NT[NT.length - 1] || !lastCh ? FLAT : lastCh > 0 ? UP : DN, lineWidth: 1, lineStyle: 2, axisLabelVisible: true, axisLabelTextColor: css('--on-fill'), title: '' });
  // 無成交的一字線用灰色；收盤 = 開盤（十字、T 字、跌停一字）依漲跌上色（日線 = 對昨收，週／月線 = 對上一根），平盤灰色
  const eqC = i => { const [d] = barChange(raw, i, mode, adj); return !d ? FLAT : d > 0 ? UP : DN; };
  kSer.setData(raw.map((r, i) => ({ time: T[i], open: O[i], high: H[i], low: L[i], close: C[i],
    ...(NT[i] ? { color: FLAT, borderColor: FLAT, wickColor: FLAT } : C[i] === O[i] ? (c => ({ color: c, borderColor: c, wickColor: c }))(eqC(i)) : {}) })));
  // 除權息、減資、面額變更標記（還原／原始都顯示）；週／月線同一根有多筆時合併文字，第 19 輪 F19-2：週／月線寫事件日「M/D 類型」
  const mdn = d => `${+d.slice(5, 7)}/${+d.slice(8, 10)}`;
  const mkPos = mode === '日' ? { position: 'belowBar', shape: 'arrowUp' } : { position: 'aboveBar', shape: 'arrowDown' };   // 第 23 輪 F23-4b：週／月 K 標記在 K 棒上方
  const evText = r => [...new Set(r.ev.map(e => (mode === '日' ? '' : mdn(e.d) + ' ') + evMark(e)))].join('・');
  kSer.setMarkers(raw.flatMap((r, i) => r.ev.length ? [{ time: T[i], ...mkPos,
    color: css('--blue'), text: mode === '日' ? evText(r) : '' }]
    : r.gx ? [{ time: T[i], ...mkPos, color: css('--text2'), text: mode === '日' ? r.gx : '' }] : []));   // 第 15 輪：ETF 推測的價格調整日；第 33 輪：週／月 K 的文字改自繪標籤
  line(kc, ma5, '#888780'); line(kc, ma20, '#EF9F27'); line(kc, ma60, '#7F77DD');
  // 第 33 輪 F33-1：週／月 K 的事件文字改成 HTML 標籤（有底色），放在標籤寬度範圍內每根 K 棒的最高價之上，避開上影線；捲動、縮放、改變寬度後重新定位
  const tags = mode === '日' ? [] : raw.flatMap((r, i) => r.ev.length || r.gx ? [[i, r.ev.length ? evText(r) : r.gx, !r.ev.length]] : []);
  if (tags.length) {
    const lay = document.createElement('div'), ts = kc.timeScale(), y = p => kSer.priceToCoordinate(p);
    lay.className = 'ev-lbls';
    lay.innerHTML = tags.map(([, t, g]) => `<span class="ev-lbl${g ? ' gx' : ''}">${esc(t)}</span>`).join('');
    $('#kC').append(lay);
    const els = [...lay.children];
    const place = () => {
      if (!lay.isConnected || !charts.includes(kc)) return;
      const s = ts.options().barSpacing / 2, bars = T.flatMap((d, j) => { const x = ts.timeToCoordinate(d); return x == null ? [] : [{ l: x - s, r: x + s, y: y(H[j]) }]; });
      evLabelPos(tags.map(([i], k) => ({ x: ts.timeToCoordinate(T[i]), w: els[k].offsetWidth, top: y(H[i]) - 18 })),   // 事件那根的箭頭之上
        lay.clientWidth - kc.priceScale('right').width(), bars)   // 主圖沒有時間軸，timeScale().width() 是 0
        .forEach((p, k) => { const st = els[k].style; st.visibility = p ? '' : 'hidden'; if (p) { st.left = p.left + 'px'; st.top = p.top + 'px'; } });   // 用 visibility 隱藏，寬度才量得到
    };
    const later = () => requestAnimationFrame(() => requestAnimationFrame(place));   // 等圖表重畫、價格刻度縮放完才量
    ts.subscribeVisibleLogicalRangeChange(later); ts.subscribeSizeChange(later); kc.subscribeCrosshairMove(later); later();
  }

  const vc = mk('vC', false);
  const vSer = vc.addHistogramSeries({ priceFormat: { type: 'volume' }, priceLineVisible: false, lastValueVisible: false });
  vSer.setData(raw.map((r, i) => ({ time: T[i], value: V[i], color: (NT[i] ? FLAT : C[i] === O[i] ? eqC(i) : C[i] > O[i] ? UP : DN) + '99' })));

  // 堆疊：買超與賣超各自累加，先畫最外層（合計），再畫內層蓋上去
  const ic = $('#iC') ? mk('iC', false) : null;      // 第 15 輪：ETF 頁沒有法人圖
  // 第 28 輪 D28-06：法人子圖刻度上下對稱（0 在中間），正負兩側都有刻度；上下留邊，最上面的刻度不被切
  const symScale = f => { const r = f(), m = r && Math.max(Math.abs(r.priceRange.minValue), Math.abs(r.priceRange.maxValue)); return m ? { ...r, priceRange: { minValue: -m, maxValue: m } } : r; };
  ic?.priceScale('right').applyOptions({ scaleMargins: { top: 0.1, bottom: 0.1 } });
  let iSer = null;
  for (const sign of ic ? [1, -1] : []) {
    for (let k = INVESTORS.length; k >= 1; k--) {
      const ser = ic.addHistogramSeries({ priceFormat: { type: 'volume' }, priceLineVisible: false, lastValueVisible: false, autoscaleInfoProvider: symScale });
      ser.setData(raw.map((r, i) => {
        if (r.net == null) return { time: T[i] };
        const v = INVESTORS.slice(0, k).reduce((a, [key]) => a + (sign * r[key] > 0 ? r[key] : 0), 0);
        return { time: T[i], value: v, color: INVESTORS[k - 1][2] };
      }));
      iSer = iSer || ser;
    }
  }

  // F8-3：融資融券餘額；第 11 輪 B14：借券賣出。第 27 輪 D27-07：一次一條線、用自己的右側刻度（原本三條線各自縮放、只有融資有刻度，量級差很多時會看反）
  const MB = raw.map(r => r.mb), SB = raw.map(r => r.sb), LB = raw.map(r => r.lb);
  let gc = null, mbSer = null, GV = null;
  if (G && $('#gC')) {
    gc = mk('gC', false);
    GV = { mb: [MB, '#1C7ED6'], sb: [SB, '#AE3EC9'], lb: [LB, '#E8590C'] }[mgView(G)];
    mbSer = gc.addLineSeries({ color: GV[1], lineWidth: 1, priceFormat: { type: 'volume' }, priceLineVisible: false, lastValueVisible: false });
    mbSer.setData(GV[0].map((v, i) => v == null ? { time: T[i] } : { time: T[i], value: v }));
    // 換算事件標在包含該日期的那一根（T 中 ≤ 事件日的最後一根）
    mbSer.setMarkers((G.k || []).map(x => { let j = -1; T.forEach((t, i) => { if (t <= x.d) j = i; }); return [j, x]; }).filter(([j]) => j >= 0)
      .sort((a, b) => a[0] - b[0]).map(([j, x]) => ({ time: T[j], position: 'aboveBar', shape: 'circle', color: css('--blue'), text: EV_LABEL[x.t] + (adj ? ' 已換算' : '') })));
    $('#gUnit').textContent = adj ? '餘額（張）' : '餘額（張，官方原始）';     // 第 12 輪 P26；D27-07 刻度即所選的線；第 28 輪 D28-06：換算說明移到 title
    $('#gUnit').title = adj ? '面額變更、減資前的餘額依官方換算' : '';
  }

  const mc = mk('mC', true);
  const lg = (c, t) => `<span class="lg"><i style="background:${c}"></i>${t}</span>`;
  let oSer, oVal;
  if (osc === 'KD' || osc === 'RSI') {   // 第 18 輪 F18-1：KD 20／80、RSI 30／70 參考線
    const f1 = { type: 'price', precision: 1, minMove: 0.1 };
    const { k, d } = calcKD(H, L, C), rsi = calcRSI(C);
    const [vals, refs] = osc === 'KD' ? [k, [20, 80]] : [rsi, [30, 70]];
    oSer = line(mc, vals, osc === 'KD' ? '#378ADD' : '#7F77DD', f1);
    if (osc === 'KD') line(mc, d, '#EF9F27', f1);
    refs.forEach(p => oSer.createPriceLine({ price: p, color: text2, lineWidth: 1, lineStyle: 2, axisLabelVisible: true }));
    oVal = i => vals[i];
    $('#oscLeg').innerHTML = osc === 'KD' ? `KD (9, 3, 3)${lg('#378ADD', 'K')}${lg('#EF9F27', 'D')}`
      : `RSI (14)${lg('#7F77DD', 'RSI')}`;   // 參考線的值標在右側刻度
  } else {
    const macdFmt = { type: 'price', precision: 2, minMove: 0.01 };
    const hSer = mc.addHistogramSeries({ priceFormat: macdFmt, priceLineVisible: false, lastValueVisible: false });
    hSer.setData(hist.map((v, i) => ({ time: T[i], value: v, color: (v >= 0 ? UP : DN) + 'a6' })));
    oSer = line(mc, dif, '#378ADD', macdFmt);
    line(mc, dea, '#EF9F27', macdFmt);
    oVal = i => dif[i];
    $('#oscLeg').innerHTML = `MACD (12, 26, 9)${E ? '，原始價' : ''}${lg('#378ADD', 'DIF')}${lg('#EF9F27', 'DEA')}`;
  }

  charts = [kc, vc, ...(ic ? [ic] : []), ...(gc ? [gc] : []), mc];   // 順序與 CHART_IDS 中存在的圖一致

  // 同步：只讓滑鼠/手指所在的那張圖帶動其他圖；若每張都互相回寫，拖曳中的事件會彼此抵銷
  syncLeader = kc;
  charts.forEach(src => src.timeScale().subscribeVisibleLogicalRangeChange(r => {
    if (src !== syncLeader || !r) return;
    charts.forEach(dst => dst !== src && dst.timeScale().setVisibleLogicalRange(r));
  }));

  // 十字線同步 + 上方資訊列
  const anchors = [[kc, kSer, i => C[i]], [vc, vSer, i => V[i]], ...(ic ? [[ic, iSer, i => N[i]]] : []), ...(gc ? [[gc, mbSer, i => GV[0][i]]] : []), [mc, oSer, oVal]];
  const legend = $('#kLegend');
  const showLegend = i => {
    // 日線用匯出的漲跌（事件日相對參考價、前一日無成交相對最後成交）；找不到事件的不比價日為 null。週／月線用前一根收盤
    // 第 15 輪 QA-01：週／月線含推測價格調整（gx）的那一根不用原始價相減，改寫「不比價」，避免除息、分割被讀成下跌
    const gxBar = mode !== '日' && raw[i].gx, [chg, p, f] = barChange(raw, i, mode, adj);
    const c = cls(chg);
    const ma = (label, v, color) => v == null ? '' : `<span class="lg"><i style="background:${color}"></i>${label} <b>${pfmt(v)}</b></span>`;   // D27-06：線色只放在色塊，數字用正文色（淺色 MA20 原本 2.17）
    legend.innerHTML = `<span><b>${mode === '月' ? T[i].slice(0, 7) + ' 月' : mode === '週' ? T[i] + ' 當週' : T[i]}</b></span><span>開 <b>${pfmt(O[i])}</b></span><span>高 <b class="up">${pfmt(H[i])}</b></span>` +
      `<span>低 <b class="dn">${pfmt(L[i])}</b></span><span>收 <b class="${c}">${pfmt(C[i])}</b></span>` +
      (NT[i] ? '<span class="flat">無成交</span>'
        : chg == null ? `<span class="flat" title="${gxBar ? '期間含推測的價格調整（除息、分割等），原始價相減會失真' : raw[i].ev.some(e => e.t === '息') ? '除息日官方未提供漲跌' : '官方未提供漲跌，且找不到對應的除權息、減資、面額變更事件'}">不比價</span>`
        : `<span class="${c}"${f !== 1 ? ' title="期間含除權息等事件：前一根收盤先乘上參考價 ÷ 前收再相減"' : ''}>${psgn(chg)} (${sgn(p)}%)</span>`) +
      (mode === '日' && raw[i].rel ? `<span class="muted">相對 ${md(raw[i].rel)} 收盤</span>` : '') +
      raw[i].ev.map(e => `<span class="ev-note"${e.t === '調' ? ' title="依櫃買官方漲跌反推的參考價調整（減資、面額變更等）"' : /c/.test(e.k || '') ? ` title="${CASH_INC_TIP}"` : ''}>` +
        `${mode === '日' ? '' : md(e.d) + ' '}${evName(e)}　前收 ${pfmt(e.p)}　參考價 ${pfmt(e.r)}</span>`).join('') +
      (raw[i].gx ? `<span class="ev-note" title="只是推測，可能是除息、分割或合併">${mode === '日' ? '' : '期間含'}${raw[i].gx === '息?' ? '推測除息（官方不比價）' : '推測價格調整（參考價改變）'}</span>` : '') +
      `<span>量 <b>${fmt(V[i])}</b> 張</span>` +
      (N[i] != null ? `<span>法人 <b class="${cls(N[i])}">${sgn(N[i], 0)}</b> 張</span>` : '') +
      ma('MA5', ma5[i], '#888780') + ma('MA20', ma20[i], '#EF9F27') + ma('MA60', ma60[i], '#7F77DD');
    // 法人資料比行情晚公布：最新一根還沒有時，改顯示最近有資料的那天
    let j = i;
    if (N[j] == null && i === raw.length - 1) while (j > 0 && N[j] == null) j--;
    const r = raw[j], v = x => x == null ? '--' : sgn(x, 0);
    if (ic) $('#iLegend').innerHTML = (j !== i && N[j] != null ? `<span class="muted">${T[j]}</span>` : '') +
      INVESTORS.map(([key, name, color]) =>
        `<span class="lg"><i style="background:${color}"></i>${name} <b class="num ${cls(r[key])}">${v(r[key])}</b></span>`).join('') +
      `<span class="lg" title="${NET_TIP}">合計${mode === '日' ? '' : '（每日相加）'} <b class="num ${cls(N[j])}">${v(N[j])}</b></span>`;
    if (gc) {   // 融資融券比行情晚公布：最新一根還沒有時，改顯示最近有資料的那天
      let g = i;
      if (MB[g] == null && i === raw.length - 1) while (g > 0 && MB[g] == null) g--;
      const gv = mgView(G);   // 第 28 輪 D28-06：只列目前那條線（＋券資比），標題區手機 ≤ 60px
      $('#gLegend').innerHTML = (g !== i && MB[g] != null ? `<span class="muted">${T[g]}</span>` : '') +
        `<span class="lg"><i style="background:${GV[1]}"></i>${{ mb: '融資', sb: '融券', lb: '借券' }[gv]} <b class="num">${fmt(GV[0][g])}</b></span>` +
        (gv === 'lb' ? '' : `<span class="lg">券資比 <b class="num">${MB[g] ? fmt(SB[g] / MB[g] * 100, 2) + '%' : '--'}</b></span>`);
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

// 第 43 輪 F43-3：集保股權分散 4 張卡（i = 最新一週；1週、4週 = 和上一筆、往前第 4 筆有資料的週比，沒有那一筆寫 --）
function shCards(sh, etf) {
  const i = sh.d.length - 1, w = (a, k, nd) => i - k < 0 ? '--' : sgn((Math.round((a[i] - a[i - k]) * 100) + 0) / 100, nd);
  const pp = a => `<span class="nw">1週 ${w(a, 1, 2)}</span>　<span class="nw">4週 ${w(a, 4, 2)}</span>（百分點）`;
  return [['持股超過 400 張', fmt(sh.b[i], 2) + '%', '', pp(sh.b) + '<br>' + fmt(sh.bn[i]) + ' 人'], ['持股超過 1,000 張', fmt(sh.k[i], 2) + '%', '', pp(sh.k)],
    ['50 張以下', fmt(sh.r[i], 2) + '%', '', pp(sh.r)],
    [etf ? '受益人數' : '股東人數', fmt(sh.n[i]) + ' 人', '', `<span class="nw">1週 ${w(sh.n, 1, 0)}</span>　<span class="nw">4週 ${w(sh.n, 4, 0)}</span>（人）<br>未滿 1 張 ${fmt(sh.z[i])} 人`]];
}
const SH_NOTE = [
  '以集保戶每週最後一個營業日的餘額，依身分歸戶後分級；大戶包含外資、法人、ETF 與公司大股東，融資、借券以專戶計。比例 = 各級股數 ÷ 集保庫存合計，增資、減資、合併時會跳動。官方每週公布一次，本站通常在下週一晚上更新；本站從上線起逐週累積，之前的週無法回補。比例的變化只描述持股結構，不代表之後的走勢。',
  '以集保戶每週最後一個營業日的餘額，依身分歸戶後分級；人數為受益人數，大額持有人包含法人、壽險與其他基金。比例 = 各級受益權單位 ÷ 集保庫存合計，申購、贖回時會跳動。官方每週公布一次，本站通常在下週一晚上更新；本站從上線起逐週累積，之前的週無法回補。比例的變化只描述持有結構，不代表之後的走勢。'];
// 第 43 輪 F43-3：股權分散週圖（每週一點、固定 sh 全部；不跟圖表區間、不和日資料的籌碼圖十字線同步；兩張圖的圖例一起換週）。mk = buildChip 的建圖函式
function shChart(sh, E, mk) {
  const T = sh.d, last = T.length - 1, B = '#4C6EF5', R = '#DB6E00', N = '#1C7ED6';
  const pct = { type: 'custom', minMove: 0.01, formatter: v => fmt(v, 2) + '%' }, ppl = { type: 'custom', minMove: 1, formatter: v => fmt(v) };
  const line = (c, vals, color, f, style) => { const s = c.addLineSeries({ color, lineWidth: 2, lineStyle: style, priceFormat: f, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false });
    s.setData(vals.map((v, i) => ({ time: T[i], value: v }))); return s; };
  const a = mk('shC', true), b = mk('snC', true);
  line(a, sh.b, B, pct, 0); line(a, sh.r, R, pct, 2); line(b, sh.n, N, ppl, 0);
  const show = i => { const d = `<span><b>${md(T[i])}</b></span>`;
    $('#shCL').innerHTML = `${d}<span class="lg"><i style="background:${B}"></i>超過 400 張 <b class="num">${fmt(sh.b[i], 2)}%</b></span>` +
      `<span class="lg"><i style="background:none;height:0;border-top:2px dashed ${R}"></i>50 張以下 <b class="num">${fmt(sh.r[i], 2)}%</b></span><span>超過 50 至 400 張 <b class="num">${fmt(sh.m[i], 2)}%</b></span>`;
    $('#snCL').innerHTML = `${d}<span class="lg"><i style="background:${N}"></i>${E ? '受益人' : '股東'} <b class="num">${fmt(sh.n[i])} 人</b></span>`; };
  [a, b].forEach(c => c.subscribeCrosshairMove(p => { const i = p.logical == null ? -1 : Math.round(p.logical); show(p.time !== undefined && i >= 0 && i <= last ? i : last); }));
  show(last);
  return [a, b];
}

// 第 28 輪 D28-01：籌碼分頁時間序列（張）。法人：收盤小面板＋外資／投信／自營區間累計（不用雙 Y 軸）；信用：融資餘額；借券：借券賣出餘額。
// 第 29 輪 F29-1、2：法人改成「選一種法人」的每日買賣超柱（主）＋同一法人的區間累計小面板（輔，標題寫起算日）
// 區間由 #chipSeg 決定，不能拖曳縮放（避免手機捲頁時誤拖）；十字線四張圖同步，圖例顯示該日數字
function buildChip(data, E) {
  disposeKCharts();
  const LC = window.LightweightCharts, all = aggregate(data, '日', !E), raw = chipN === 'all' ? all : all.slice(-chipN);
  if (!LC || !raw.length) return;
  const T = raw.map(r => r.d), text2 = css('--text2'), grid = css('--border'), last = raw.length - 1;
  const dt = t => typeof t === 'string' ? t : [t.year, t.month, t.day].map(x => String(x).padStart(2, '0')).join('-');
  const lots = { type: 'custom', minMove: 1, formatter: v => fmt(v) }, px = { type: 'custom', minMove: 0.01, formatter: pfmt };
  const mk = (id, tv) => LC.createChart($('#' + id), {
    autoSize: true, handleScroll: false, handleScale: false,
    layout: { background: { type: 'solid', color: 'transparent' }, textColor: text2, fontSize: 11, attributionLogo: false },
    grid: { vertLines: { visible: false }, horzLines: { color: grid } },
    rightPriceScale: { borderVisible: false, minimumWidth: 76, scaleMargins: { top: 0.12, bottom: 0.08 }, entireTextOnly: true },   // 上下留邊；刻度文字放不下就不畫（不會只露半截）
    timeScale: { borderVisible: false, visible: tv, fixLeftEdge: true, fixRightEdge: true,
      tickMarkFormatter: (t, type) => { const [y, m, d] = dt(t).split('-').map(Number); return type === 0 ? String(y) : type === 1 ? `${m}月` : `${m}/${d}`; } },
    localization: { locale: 'zh-TW', timeFormatter: t => dt(t).split('-').join('/') },
  });
  const line = (c, vals, color, w = 2, f = lots) => { const s = c.addLineSeries({ color, lineWidth: w, priceFormat: f, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false });
    s.setData(vals.map((v, i) => v == null ? { time: T[i] } : { time: T[i], value: v })); return s; };
  const at = (a, i) => { let j = i; if (i === last) while (j > 0 && a[j] == null) j--; return j; };    // 最新一天還沒有資料時，圖例改顯示最近有資料的那天
  const day = (i, j) => `<span><b>${T[j].slice(5).replace('-', '/')}</b></span>`;
  const anchors = [], legs = [];
  if ($('#cpC')) {
    const C = raw.map(r => r.c), cp = mk('cpC', false), ci = mk('ciC', true), cu = mk('cuC', true);
    anchors.push([cp, line(cp, C, text2, 1, px), C]);
    const V = raw.map(r => r[chipI]), up = css('--up'), dn = css('--dn'), name = CHIP_I.find(x => x[0] === chipI)[1];
    let a = 0;
    const cum = V.map(v => v == null ? null : (a += v));
    const bar = ci.addHistogramSeries({ priceFormat: lots, priceLineVisible: false, lastValueVisible: false });
    bar.setData(V.map((v, i) => v == null ? { time: T[i] } : { time: T[i], value: v, color: v >= 0 ? up : dn }));
    bar.createPriceLine({ price: 0, color: text2, lineWidth: 1, lineStyle: 2, axisLabelVisible: false });
    const cl = line(cu, cum, text2, 1);
    cl.createPriceLine({ price: 0, color: text2, lineWidth: 1, lineStyle: 2, axisLabelVisible: false });
    anchors.push([ci, bar, V], [cu, cl, cum]);
    if (data.fh && $('#fhC')) {          // 第 29 輪 F29-4：外資持股比率（水位，不受區間起點影響）
      const fm = Object.fromEntries(data.prices.d.map((d, i) => [d, data.fh[i]])), F = raw.map(r => fm[r.d] ?? null), fh = mk('fhC', true);
      anchors.push([fh, line(fh, F, '#4C6EF5', 2, { type: 'custom', minMove: 0.01, formatter: v => fmt(v, 2) + '%' }), F]);
      legs.push(i => { const j = at(F, i); $('#fhCL').innerHTML = `${j !== i ? `<span class="muted">${T[j].slice(5).replace('-', '/')}</span>` : ''}<span>外資持股 <b class="num">${F[j] == null ? '--' : fmt(F[j], 2) + '%'}</b></span>`; });
    }
    $('#cuCT').textContent = `區間累計（張，自 ${T[0].slice(0, 4) === T[last].slice(0, 4) ? md(T[0]) : T[0].replace(/-/g, '/')} 起加總）`;   // 跨年寫年份
    legs.push(i => { $('#cpCL').innerHTML = `${day(i, i)}<span>收 <b>${pfmt(C[i])}</b></span>`; },
      i => { const j = at(V, i);
        const lag = j !== i ? `<span class="muted">${T[j].slice(5).replace('-', '/')}</span>` : '';
        $('#ciCL').innerHTML = `${lag}<span>${name} <b class="num ${cls(V[j])}">${V[j] == null ? '--' : sgn(V[j], 0)}</b></span>`;
        $('#cuCL').innerHTML = `${lag}<span>累計 <b class="num ${cls(cum[j])}">${cum[j] == null ? '--' : sgn(cum[j], 0)}</b></span>`; });
  }
  if ($('#cmC')) {
    const MB = raw.map(r => r.mb), SB = raw.map(r => r.sb), cm = mk('cmC', true);
    anchors.push([cm, line(cm, MB, '#1C7ED6'), MB]);
    legs.push(i => { const j = at(MB, i);
      $('#cmCL').innerHTML = `${day(i, j)}<span class="lg"><i style="background:#1C7ED6"></i>融資 <b class="num">${fmt(MB[j])}</b></span><span>融券 <b class="num">${fmt(SB[j])}</b></span>` +
        `<span>券資比 <b class="num">${MB[j] ? fmt(SB[j] / MB[j] * 100, 2) + '%' : '--'}</b></span>`; });
  }
  if ($('#clC')) {
    const LB = raw.map(r => r.lb), cl = mk('clC', true);
    anchors.push([cl, line(cl, LB, '#E8590C'), LB]);
    legs.push(i => { const j = at(LB, i); $('#clCL').innerHTML = `${day(i, j)}<span class="lg"><i style="background:#E8590C"></i>借券賣出 <b class="num">${fmt(LB[j])}</b></span>`; });
  }
  charts = anchors.map(a => a[0]);            // disposeStockCharts 一併釋放
  if (data.sh && data.sh.d.length >= 2 && $('#shC')) charts.push(...shChart(data.sh, E, mk));   // 第 43 輪 F43-3：週圖也列入 charts（切換區間時一起釋放、重畫）
  charts.forEach(c => c.timeScale().fitContent());
  const show = i => legs.forEach(f => f(i));
  let busy = false;
  anchors.forEach(([src]) => src.subscribeCrosshairMove(p => {
    if (busy) return;
    busy = true;
    const i = p.logical == null ? -1 : Math.round(p.logical), ok = p.time !== undefined && i >= 0 && i <= last;
    anchors.forEach(([dst, ser, v]) => { if (dst === src) return; if (ok && v[i] != null) dst.setCrosshairPosition(v[i], T[i], ser); else dst.clearCrosshairPosition(); });
    show(ok ? i : last);
    busy = false;
  }));
  show(last);
}

const SIG_MIN = 3, MACD_MIN = 35;   // 有效訊號至少 3 項才下結論；MACD 需 26 + 9 根
// 第 22 輪 F22-10：MACD 柱依昨（a）、今（b）的正負寫看到的變化；多空照舊只看柱值升降（b > a 偏多，持平偏空）
const macdBar = (a, b) => b === a ? 'MACD 柱持平' : b > a ? (a < 0 && b > 0 ? 'MACD 柱由負翻正' : b > 0 ? 'MACD 正柱加長' : 'MACD 負柱縮短')
  : a > 0 && b < 0 ? 'MACD 柱由正翻負' : b < 0 ? 'MACD 負柱加長' : 'MACD 正柱縮短';

// 第 53 輪 F53-5：走勢分頁最下方的重大訊息卡（主旨照官方原文，只跳脫；超過 10 則先藏起來，按「顯示全部」再顯示）
function mnCard(M, code) {
  const late = M.f > M.w, F = M.f.replace(/-/g, '/'), g = mnGap(M.x), sub = late ? md(M.f) + ' 起' : '近 30 天';
  const short = '只列官方主旨，不含說明全文；內容以原文為準', full = '重大訊息是上市櫃公司依規定在公開資訊觀測站發布的公告。本站只列發言日、時間與主旨，不含說明全文，也不分類、不加註解；同一件事的更正或補充，官方會另發一則，兩則都會列出。資料來自證交所、櫃買中心的開放資料，官方每次只提供一天的公告，本站沒收到的日子目前無法補；「沒有收到」是指那個交易日本站一則都沒有收到。時間是公司的發言時間。';
  const rows = M.r.map((r, i) => `<div class="al-row mn-row"${i >= 10 ? ' style="display:none"' : ''}><span class="small muted num">${md(r[0])} ${r[1]}</span>　<span class="mn-s">${esc(r[2])}</span></div>`).join('');
  return `<section class="sec card mn"><div class="sec-h"><h2>重大訊息</h2><span class="muted small">${sub}，公開資訊觀測站</span></div>
${rows || `<div class="muted small">${sub}沒有重大訊息</div>`}
${M.r.length > 10 ? `<button class="chip" id="mnMore" style="margin-top:8px">顯示全部 ${M.r.length} 則</button>` : ''}
<div class="muted small" style="margin-top:6px">本站自 ${F} 起收錄${g ? '；' + g : ''}。官方每次只提供一天的資料，沒收到的日子本站目前無法補</div>
<div class="muted small">原文請到<a href="https://mops.twse.com.tw/" target="_blank" rel="noopener noreferrer">公開資訊觀測站</a>以代號 ${code} 與發言日查詢</div>
<div class="muted small" style="margin-top:6px">${noteHTML(short, full)}</div></section>`;
}
function mnShowAll() {
  document.querySelectorAll('#view .mn-row').forEach(e => { e.style.display = ''; });
  $('#mnMore')?.remove();
}

function renderSignals(rows, mode) {
  const period = { '日': '日線', '週': '週線', '月': '月線' }[mode];
  $('#sigTitle').textContent = `技術面訊號（${period}）`;
  let n = rows.length;
  while (n > 0 && rows[n - 1].nt) n--;          // 最後一根無成交的一字線不納入判讀
  const C = rows.slice(0, n).map(r => r.c), i = n - 1, c = C[i];
  const { k, d } = calcKD(rows.slice(0, n).map(r => r.h), rows.slice(0, n).map(r => r.l), C), rsi = calcRSI(C);   // 第 18 輪 F18-1
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
    chk(hist[i] > hist[i - 1], macdBar(hist[i - 1], hist[i]), macdBar(hist[i - 1], hist[i]));
  }
  const total = bull.length + bear.length, lean = bull.length > bear.length ? 'bull' : bull.length < bear.length ? 'bear' : '';
  const tags = `<div>${bull.map(t => `<span class="tag up">${t}</span>`).join('')}${bear.map(t => `<span class="tag dn">${t}</span>`).join('')}</div>` + oscLine(k, d, rsi, i);
  const note = (n < rows.length && n ? `最後一根（${md(rows.at(-1).d)}）無成交，以 ${md(rows[i].d)} 判讀。` : '') +
    '依均線與 MACD 機械判讀（還原價格），僅供參考。KD、RSI 在急漲急跌時會長時間停在高檔或低檔，交叉也會反覆出現，不計入多空。';
  $('#sigBox').innerHTML = total < SIG_MIN
    ? `<div class="signal"><div style="font-weight:600;margin-bottom:6px">資料不足，無法判讀</div>${tags}
        <div class="muted small" style="margin-top:8px">${period}只有 ${n} 根 K 棒，有效訊號 ${total} 項（至少需 ${SIG_MIN} 項；MACD 需 ${MACD_MIN} 根以上）。${note}</div></div>`
    : `<div class="signal ${lean}">
        <div style="font-weight:600;margin-bottom:6px">${{ bull: '偏多', bear: '偏空', '': '中性' }[lean]}：${bull.length} 多 ${bear.length} 空</div>
        ${tags}<div class="muted small" style="margin-top:8px">${note}</div></div>`;
}

// 第 18 輪 F18-1：技術面卡「動能（不計入多空）」一行；只寫數值、區間與交叉
function oscLine(k, d, rsi, i) {
  const kd = k[i] == null ? 'KD 資料不足（需 9 根）'
    : `K ${fmt(k[i], 1)}／D ${fmt(d[i], 1)}${k[i] < 20 ? '（K 低於 20）' : k[i] > 80 ? '（K 高於 80）' : ''}` +
      (k[i - 1] == null ? '' : k[i - 1] <= d[i - 1] && k[i] > d[i] ? '，今日黃金交叉' : k[i - 1] >= d[i - 1] && k[i] < d[i] ? '，今日死亡交叉' : '');
  const r = rsi[i] == null ? 'RSI 資料不足（需 15 根）' : `RSI ${fmt(rsi[i], 1)}${rsi[i] < 30 ? '（低於 30）' : rsi[i] > 70 ? '（高於 70）' : ''}`;
  return `<div class="small osc-line"><b>動能（不計入多空）</b>　${kd}；${r}</div>`;
}

// ─── 第 10 輪 B5：季報卡（匯出端已把累計相減成單季；q = [季別, 單季 EPS, EPS 年增 %, 毛利率 %, 營益率 %, 單季營收（千元）]）───
const FIN_TBL = { ci: '一般業', fh: '金控', basi: '銀行', bd: '證券', ins: '保險', mim: '其他' };
const qName = k => `${Math.floor(k / 100)} Q${k % 100}`;                 // 202603 → 2026 Q3
const qShort = k => `${String(k).slice(2, 4)}Q${k % 100}`;              // 202603 → 26Q3
function renderFin(F) {
  const Q = F.q, L = Q.at(-1), k = L[0], q = k % 100;
  const base = Q.find(r => r[0] === k - 100);                             // 去年同季（近 8 季內才有）
  const ey = (v, cur, b) => v != null ? (epsLow(v, b) ? `基期低（去年同季 ${fmt(b, 2)} 元）` : sgn(v, 1) + '%') : b != null && b <= 0 && cur > 0 ? '轉盈' : '--';   // 第 14 輪 F14-2
  // 第 15 輪 F15-1：累計 EPS 年增同單季規則（c.eb = 去年同期累計 EPS；舊 JSON 沒有 eb 時照舊）
  const cy = F.c.ey != null ? (epsLow(F.c.ey, F.c.eb) ? `基期低（去年同期 ${fmt(F.c.eb, 2)} 元）` : sgn(F.c.ey, 1) + '%')
    : F.c.eb != null && F.c.eb <= 0 && F.c.e > 0 ? '轉盈' : '--';
  const pc1 = v => v == null ? '--' : fmt(v, 1) + '%';
  const stats = [['單季 EPS', fmt(L[1], 2), cls(L[2]), `年增 ${ey(L[2], L[1], base?.[1])}`],
    ['累計 EPS', fmt(F.c.e, 2), '', `${q === 4 ? '全年' : `1～${q * 3} 月`}，年增 ${cy}`],
    ...(F.t === 'ci' ? [['毛利率', pc1(L[3]), '', `去年同季 ${pc1(base?.[3])}`]] : []),
    ...(L[4] != null ? [['營益率', pc1(L[4]), '', `去年同季 ${pc1(base?.[4])}`]] : []),
    ...(F.t === 'ci' && F.nm ? [['稅後淨利率', pc1(F.nm[F.nm.length - 1]), '', `去年同季 ${pc1(F.nm[Q.indexOf(base)])}`]] : []),   // 第 23 輪 F23-2：nm 和 q 逐季對齊；舊 JSON 沒有 nm 不顯示
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
    <div class="muted small" style="margin-top:6px">${noteHTML('單季、近 4 季 EPS 由累計相減，可能和公司公告略有差異', `單季 = 本季累計 − 上一季累計（第 4 季 = 全年 − 前三季）；期中有增資或減資時，相減的 EPS 會和公司公告的單季 EPS 略有差異。近 4 季 EPS = 本季累計 + 去年全年 − 去年同季累計。官方本益比以最新股數計算，期間有增資的公司，近 4 季 EPS 會和「股價 ÷ 本益比」有差異。金融業沒有毛利率。稅後淨利率（只有一般業）= 單季歸屬母公司業主的淨利 ÷ 單季營收，不含非控制權益；部分網站用合併總淨利，數字會不同。${F.c.fs ? '' : '「本站收錄」日期只有每日收集時才記錄，補抓的季別不顯示。'}`)}</div>`;
}

// ─── 第 52 輪 F52-5：季報卡原 6 格之下加一排 ROE、負債比、每股淨值（B = 匯出的 bs；和季報卡同一季才顯示；renderFin 不改）───
function renderBs(B, F) {
  if (B.q !== F.q[F.q.length - 1][0]) return;
  const pc = v => v == null ? '--' : fmt(v, 1) + '%';
  const NA = ['不適用', '金融、保險等業別不計算', 'ROE、負債比只計算一般業；金融、保險等業別的負債以存款、保單準備為主，和一般業不能直接比較'];
  const RN = { a: ['沒有一年前同季的權益資料', 'ROE 要用一年前同季底與本季底的權益平均；新上市或資料缺季時不計算'],
    c: ['本季沒有權益資料', '資產負債表彙總本季的權益欄是空的，不計算 ROE'],
    i: ['近 4 季淨利資料不足', '近 4 季淨利 = 本季累計 + 去年全年 − 去年同季累計，缺一季就不計算'],
    e: ['平均權益為負或零，不計算', '一年前同季底與本季底權益的平均 ≤ 0 時，ROE 沒有意義，不計算'] };
  const rn = RN[B.rn] || ['資料不足', RN.a[1]], ci = F.t === 'ci';
  const cells = [['ROE（近 4 季）', ...(!ci ? NA : B.roe != null ? [pc(B.roe), `一年前 ${pc(B.roep)}`, '近 4 季歸屬母公司業主的淨利 ÷ 一年前同季底與本季底權益的平均'] : ['--', ...rn])],
    ['負債比', ...(!ci ? NA : [pc(B.dr), `去年同季 ${pc(B.drp)}`, B.dr != null ? '季底的負債總計 ÷ 資產總計' : '資產負債表彙總本季的資產或負債欄是空的'])],
    ['每股淨值', fmt(B.bv, 2), `去年同季 ${fmt(B.bvp, 2)}`, B.bv != null ? '公開資訊觀測站資產負債表彙總的「每股參考淨值」（元）' : '資產負債表彙總沒有列出這一季的每股參考淨值']];
  const short = 'ROE 用近 4 季淨利與平均權益；資產、負債、淨值是季底數字';
  const full = 'ROE（近 4 季）= 近 4 季歸屬母公司業主的淨利 ÷ 平均權益 × 100%；平均權益 =（一年前同季底 + 本季底）歸屬母公司業主權益 ÷ 2，沒有子公司的公司用權益總計。' +
    '近 4 季淨利的算法和近 4 季 EPS 相同（本季累計 + 去年全年 − 去年同季累計），用總金額計算，不受期中增資、減資影響。負債比 = 負債總計 ÷ 資產總計 × 100%。' +
    '每股淨值是公開資訊觀測站資產負債表彙總的「每股參考淨值」，和頂端股價淨值比用的每股淨值是同一份申報資料；官方換用新一季數字的日子和本站收錄日可能差幾個交易日。' +
    '資產、負債、權益是季底的時點數字，不是累計。金融、保險等業別的負債以存款、保單準備為主，不計算 ROE 與負債比。';
  $('#finBox > .metrics').insertAdjacentHTML('afterend', `<div class="metrics bs" style="margin-top:8px">${cells.map(([l, x, sub, t]) => `<div class="card stat" title="${t}"><div class="l">${l}</div><div class="v num " style="font-size:16px">${x}</div><div class="s">${sub}</div></div>`).join('')}</div>`);
  $('#finBox').insertAdjacentHTML('beforeend', `<div class="muted small" style="margin-top:6px">${noteHTML(short, full)}</div>`);
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
    <div class="muted small note-dup" style="margin-top:6px">${noteHTML(`柱：${Y} 年（藍）、${Y - 1} 年（灰）同月營收`, `柱：${Y} 年（藍）與 ${Y - 1} 年（灰）同月營收；去年 ${M + 1 <= 12 ? `${M + 1}～12 月只有去年，供參考` : '全年對照'}。年增 = 今年該月 ÷ 去年同月 − 1；累計只算兩年都有資料的月份。`)}</div>`;
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
