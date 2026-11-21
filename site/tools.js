// 台股資金流 第 34 輪：試算工具 #/tools/dt 交易成本（含當沖、漲跌停）、#/tools/cp 複利、#/tools/pl 股票質借；第 39 輪 #/tools/dv 除權息。
// 只在瀏覽器計算；網址帶 ?c=代號 時只讀同站 data/（loadStock，個股頁看過的不再請求）。
// 共用 app.js 的 $、esc、fmt、pfmt、md、segHTML、onSeg、pageTabsHTML、localStore、loadStock
'use strict';

// 規則常數（查證 2026-11-19，編號見 docs/iterations/34/01-analyst.md）。期限到了只提醒、不自動改稅率（D48 = A）
const TL_RULES = {
  fee: 1425,                                                       // R1 手續費率 0.1425%（百萬分之 1425），元以下捨去
  minFee: 20,                                                      // R2 每筆最低 20 元（各券商不同，可改）
  tax: { s: [30], dt: [15, '2027-12-31'], e: [10], b: [0, '2026-12-31'] },   // 萬分之：R3 股票 0.3%、R4 現股當沖 0.15%、R3／R5 ETF 0.1%、R6 債券 ETF 停徵
  limit: 10,                                                       // R9 漲跌幅 10%
  pl: { cap: 60, call: 130, back: 166, term: 183, max: 548 },      // P3 成數上限、P9 追繳 130%／補繳至 166%、P2 每次 6 個月（續借 2 次）
};
const TL_TABS = [['dt', '交易成本'], ['cp', '複利'], ['pl', '股票質借'], ['dv', '除權息']];

// R7 升降單位（分）：股票六級、ETF 二級（e 為 true）。≥ 1,000 元改 1 元的新制尚未生效（D49 = A）
const tlTick = (p, e) => e ? (p < 5000 ? 1 : 5) : p < 1000 ? 1 : p < 5000 ? 5 : p < 10000 ? 10 : p < 50000 ? 50 : p < 100000 ? 100 : 500;
const tlNext = (p, e) => p + tlTick(p, e), tlPrev = (p, e) => p - tlTick(p - 1, e);   // 上一檔、下一檔（往下跨級距用下方級距）
const tlPx = (p, e) => { const t = tlTick(p, e); return fmt(p / 100, t < 10 ? 2 : t < 100 ? 1 : 0); };   // 依升降單位的小數位
// R9 漲跌停：參考價 × 1.1 依「漲停價所在級距」捨去、× 0.9 依「跌停價所在級距」進位（本站歷史日線實證，例：參考價 108 → 跌停 97.2）
function tlLimit(r, e) {
  const u = Math.floor(r * (100 + TL_RULES.limit) / 100), d = Math.ceil(r * (100 - TL_RULES.limit) / 100), t = tlTick(d, e);
  return [u - u % tlTick(u, e), d % t ? d - d % t + t : d];
}

// 金額一律用「分」的整數；手續費、證交稅為元（BigInt 避免大金額超過浮點精度）。dz 折扣（千分之，6 折 = 600）
const tlFee = (a, dz, min) => Math.max(min, Number(BigInt(a) * BigInt(TL_RULES.fee * dz) / 100000000000n));
function tlTax(k, dt, today) {
  const [r, until] = TL_RULES.tax[k === 's' && dt ? 'dt' : k];
  return { r, until, over: !!until && today > until };
}
// 一筆交易：b 買價、s 賣價（分），n 股數，k 商品（s 股票、e ETF、b 債券 ETF），dt 現股當沖，min 最低手續費；net 淨損益（分）
function tlTrade(o) {
  const ba = o.b * o.n, sa = o.s * o.n, bf = tlFee(ba, o.dz, o.min), sf = tlFee(sa, o.dz, o.min), t = tlTax(o.k, o.dt, o.today);
  const tax = Number(BigInt(sa) * BigInt(t.r) / 1000000n);
  return { ba, sa, bf, sf, tax, t, net: sa - ba - (bf + sf + tax) * 100 };
}
// 損益兩平（Q34-1）：先買後賣從買價逐檔往上、先賣後買（rev）從賣價逐檔往下，第一個淨損益 ≥ 0 的價位；最多 2,000 檔
function tlBreak(o) {
  const e = o.k !== 's', f = TL_RULES.fee * o.dz / 1e9, t = tlTax(o.k, o.dt, o.today).r / 1e4, p0 = o.rev ? o.s : o.b;
  const th = o.rev ? p0 * (1 - f - t) / (1 + f) : p0 * (1 + f) / (1 - f - t);   // 理論值（不計最低手續費與捨去）
  for (let i = 0, p = p0; i <= 2000 && p > 0; i++, p = o.rev ? tlPrev(p, e) : tlNext(p, e)) {
    const net = tlTrade(Object.assign({}, o, o.rev ? { b: p } : { s: p })).net;
    if (net >= 0) return { th, p, n: i, net };
  }
  return { th, p: null };
}

// 複利：單筆 P 每年複利、每月 M 以 r ÷ 12 按月複利（期初投入多一個月）；y 殖利率：每年底市值 × y 為股利，re 再投入（併入單筆），否則累計為已領股利
function tlCompound(o) {
  const i = o.r / 1200, rows = [];
  let a = o.P, m = 0, paid = 0;
  for (let y = 1; y <= o.n; y++) {
    a *= 1 + o.r / 100;
    for (let k = 0; k < 12; k++) m = o.begin ? (m + o.M) * (1 + i) : m * (1 + i) + o.M;
    const dv = (a + m) * o.y / 100;
    if (o.re) a += dv; else paid += dv;
    rows.push([y, o.P + o.M * 12 * y, a + m, paid]);
  }
  return rows;
}

// 股票質借（單檔）：p1 擔保價格（算上限）、p2 試算價格（算維持率，D57 = A），皆為分；n 股數；cap 成數 %；loan 借款（元，null = 以上限計）；
// rate 年利率（千分之一 %）；base 365／360；call 追繳門檻 %。整數運算：維持率等於門檻不算低於，追繳價無條件進位到分
function tlPledge(o) {
  const B = BigInt, n = B(o.n), call = B(o.call), max = B(o.p1) * n * B(o.cap) / 10000n;   // ⌊市值 × 成數⌋（元）
  const L = o.loan == null || B(o.loan) > max ? max : B(o.loan), id = 100000n * B(o.base);
  const r = { max: Number(max), L: Number(L), over: o.loan != null && B(o.loan) > max, I: Number((2n * L * B(o.rate) * B(o.days) + id) / (2n * id)) };   // 利息四捨五入到元
  if (!L || !o.p2) return r;
  const v = B(o.p2) * n, back = B(Math.max(TL_RULES.pl.back, o.call));                 // 試算市值（分）；補繳目標 166%（門檻改高時不低於門檻）
  Object.assign(r, { ratio: Number((200n * v + L) / (2n * L)), below: v < call * L, eq: v === call * L, pc: Number((call * L + n - 1n) / n), back: Number(back) });
  if (r.below) Object.assign(r, { add: Number((back * L - v + 99n) / 100n), repay: Number(L - v / back) });
  return r;
}

// 第 39 輪 F39-1：R25 除權息參考價（分）。P 前收（分）、C 現金股利（10^-6 元）、S 每千股配股（10^-8 股），皆 BigInt；
// 上市除息捨去、上市有配股與上櫃四捨五入到 0.01（D82-1 = A，本站官方參考價驗算）。整數運算：34.8 − 2.3 不會變成 32.4999…
function tlExRef(P, C, S, tw) {
  const num = (P * 10000n - C) * 10n ** 11n, den = (10n ** 11n + S) * 10000n;
  return tw && !S ? num / den : (2n * num + den) / (2n * den);
}
// 小數字串 → BigInt（× 10^k）；空白 = 0、不合法或小數超過 k 位 = null
const tlBig = (s, k) => { const m = /^(\d{1,12})(?:\.(\d+))?$/.exec(String(s == null ? '' : s).replace(/,/g, '').trim() || '0');
  return m && (m[2] || '').length <= k ? BigInt(m[1] + (m[2] || '').padEnd(k, '0')) : null; };
const tlDec = (v, k) => { const s = v.toString().padStart(k + 1, '0'), i = s.length - k; return (s.slice(0, i) + '.' + s.slice(i)).replace(/\.?0+$/, ''); };   // BigInt（× 10^k）→ 去尾 0 的字串

// ─── 輸入與畫面 ───────────────────────────────────────────
const tlNum = (s, k = 9) => { const t = String(s == null ? '' : s).replace(/,/g, '').trim();
  return new RegExp('^-?\\d+' + (k ? '(\\.\\d{1,' + k + '})?' : '') + '$').test(t) && Math.abs(t) < 1e12 ? +t || 0 : NaN; };   // 太大的數字當作不合法；-0 當作 0（QA34-01）
const tlC = s => { const x = tlNum(s, 2); return x > 0 ? Math.round(x * 100) : NaN; };   // 價格（分）
const tlY = c => fmt(c / 100, c % 100 ? 2 : 0), tlS = (c, d) => { const t = fmt(c, d); return (c > 0 ? '+' : '') + (/^-[0.,]+$/.test(t) ? t.slice(1) : t); };   // 四捨五入後為 0 不顯示負號（QA34-01）
const tlToday = () => { const d = new Date(), z = x => String(x).padStart(2, '0'); return `${d.getFullYear()}-${z(d.getMonth() + 1)}-${z(d.getDate())}`; };
const tlRow = (l, v, c = '') => `<tr><th>${l}</th><td class="num ${c}">${v}</td></tr>`;
const tlMsg = a => `<div class="tl-msg">${a.join('<br>')}</div>`;
const tlNote = a => a.filter(Boolean).map(x => `<div class="muted small tl-note">${x}</div>`).join('');
const tlIn = (k, label, v, ph = '') => `<label class="tl-f"><span>${label}</span><input data-k="${k}" inputmode="decimal" autocomplete="off" value="${esc(v)}"${ph ? ` placeholder="${esc(ph)}"` : ''}></label>`;
const tlSeg = (k, opts, v) => `<div data-g="${k}">${segHTML('tl-' + k, opts, v)}</div>`;
// D46 = B：tw.fee 只存折扣與最低手續費；壞值（非數字、負數、空字串）回到預設 10 折、20 元
function tlFeePref(raw) {
  let o = null;
  try { o = JSON.parse(raw); } catch (e) { /* 壞值當作沒有存 */ }
  const d = tlNum(o && o.d, 2), m = tlNum(o && o.m, 0);
  return { d: d > 0 && d <= 10 ? String(d) : '10', m: m >= 0 ? String(m) : String(TL_RULES.minFee) };
}
const TL = { code: undefined, info: null,
  dt: { mode: 'dt', dir: 'b', k: 's', b: '', s: '', n: '1000', ref: '' },
  cp: { P: '0', M: '5000', at: 'end', r: '', n: '10', dv: '0', y: '' },
  pl: { p1: '', p2: '', q: '1', u: 'lot', cap: '60', loan: '', rate: '', days: '180', base: '365', fee: '0', call: '130' },
  dv: { mk: 'l', k: 's', p: '', c: '', s: '0', n: '1000', cost: '', y1: '' } };   // 第 39 輪：持有成本不帶入（D83-1 = A）

function tlTaxTxt(k, dt, t) {
  const s = k === 'b' ? '債券 ETF 停徵（至 2026/12/31）' : k === 'e' ? 'ETF 0.1%（當沖不減半）' : dt ? '股票現股當沖 0.15%（至 2027/12/31）' : '股票 0.3%';
  return '證交稅：' + s + (t.over ? `；<b class="tl-warn">${k === 'b' ? '停徵' : '減半'}期限已過，請確認最新稅率</b>` : '');
}
function tlDtOut(st, I, today) {
  const e = st.k !== 's', dt = st.mode === 'dt', rev = dt && st.dir === 's', b = tlC(st.b), s = tlC(st.s), n = tlNum(st.n, 0), d = tlNum(st.d, 2), m = tlNum(st.m, 0);
  const p0 = rev ? s : b, ref = tlC(st.ref), msg = [];
  if (!(p0 > 0)) msg.push(`請輸入${rev ? '賣價' : '買價'}`);
  if (!(n > 0)) msg.push('請輸入股數'); else if (dt && n % 1000) msg.push('現股當沖股數須為 1,000 的倍數（零股不能當沖）');
  if (!(d > 0 && d <= 10)) msg.push('手續費折扣請填大於 0、最多 10 的折數，小數最多 2 位（不打折為 10）');
  if (!(m >= 0)) msg.push('最低手續費請輸入 0 以上的整數');
  const t = tlTax(st.k, dt, today), rules = tlNote([tlTaxTxt(st.k, dt, t),
    `手續費：成交金額 × 0.1425% × ${d > 0 && d <= 10 ? pfmt(d) : '--'} 折${d > 0 && d < 10 ? '（以退還後計）' : ''}，元以下捨去，每筆最低 ${m >= 0 ? fmt(m) : '--'} 元`,
    !dt && n > 0 && n % 1000 && m === TL_RULES.minFee ? '零股多數券商每筆最低 1 元，可在「最低手續費」改' : '',   // 第 38 輪 D72 = A：只提示、不改值
    dt ? '當沖需符合券商資格；處置、全額交割股可能不能當沖。' + (rev ? '先賣後買須當日收盤前買回。' : '') : '']);
  if (msg.length) return tlMsg(msg) + rules;
  const o = { b, s, n, dz: Math.round(d * 100), min: m, k: st.k, dt, rev, today }, lim = ref > 0 ? tlLimit(ref, e) : null, out = [];
  let rows = '';
  if ((rev ? b : s) > 0) {
    const r = tlTrade(o);
    rows = tlRow('買方金額', tlY(r.ba)) + tlRow('買方手續費', fmt(r.bf)) + tlRow('賣方金額', tlY(r.sa)) + tlRow('賣方手續費', fmt(r.sf)) +
      tlRow('證交稅', fmt(r.tax)) + tlRow('淨損益', tlS(r.net / 100, r.net % 100 ? 2 : 0) + ' 元', cls(r.net)) + tlRow('報酬率（÷ 買方金額）', tlS(r.net / r.ba * 100, 2) + '%', cls(r.net));
  }
  const tk = tlTick(p0, e), pn = rev ? '賣價' : '買價';
  if (p0 % tk) out.push(`${pn} ${pfmt(p0 / 100)} 不在升降單位上（每檔 ${pfmt(tk / 100)} 元），無法算兩平`);
  else {
    const be = tlBreak(o);
    rows += tlRow(`損益兩平價（理論）`, fmt(be.th / 100, 2)) + (be.p == null ? tlRow('損益兩平價（可成交）', rev ? '無法打平' : '2,000 檔內仍未打平')
      : tlRow(rev ? '兩平買價上限（可成交）' : '損益兩平價（可成交）', `<b class="tl-big">${tlPx(be.p, e)}</b>`) + tlRow(rev ? '需下跌' : '需上漲', `${be.n} 檔`) +
        tlRow('以此價成交淨損益', tlS(be.net / 100, be.net % 100 ? 2 : 0) + ' 元', cls(be.net)));
    if (be.p != null && dt && lim && (rev ? be.p < lim[1] : be.p > lim[0])) out.push(`兩平價${rev ? '低於跌停' : '高於漲停'}，當日無法以此價成交`);
  }
  if (lim) {
    const rd = I && I.d && I.c != null && ref === tlC(String(I.c));   // QA34-03：帶入的收盤是下一交易日的參考價
    out.push(`${rd ? '下一交易日' : ''}漲停 ${tlPx(lim[0], e)}、跌停 ${tlPx(lim[1], e)}（參考價 ${rd ? md(I.d) + ' 收盤 ' : ''}${pfmt(ref / 100)}，±${TL_RULES.limit}%）` + (e ? '；國外成分、槓反 ETF 漲跌幅規定不同' : ''));
    [[b, '買價'], [s, '賣價']].forEach(([p, l]) => { if (p > 0 && (p > lim[0] || p < lim[1])) out.push(`${l}超出漲跌停範圍`); });
  }
  if (I && I.ex) out.push(`${md(I.ex)} 除權息，參考價另計`);
  out.push(`升降單位：${pfmt(p0 / 100)} 元價位每檔 ${pfmt(tk / 100)} 元`);
  return `<table class="tl-kv">${rows}</table>` + tlNote(out) + rules;
}

function tlCpOut(st) {
  const P = tlNum(st.P), M = tlNum(st.M), r = tlNum(st.r), n = tlNum(st.n, 0), dv = st.dv !== '0', y = tlNum(st.y), msg = [];
  if (!(P >= 0 && M >= 0 && P + M > 0)) msg.push('初始金額、每月投入請填 0 以上，至少一項大於 0');
  if (!(r > -100 && r <= 100)) msg.push(`請輸入${dv ? '價格年變動率' : '年報酬率'}（自行假設，-99～100%）`);
  if (!(n >= 1 && n <= 50)) msg.push('年數請輸入 1～50 的整數');
  if (dv && !(y >= 0 && y <= 100)) msg.push('請輸入殖利率（0～100%）');
  const note = tlNote(['未計稅負、二代健保、內扣費用、手續費與通膨；結果依你填的假設計算，不代表本站預期。',
    dv ? '股利以每年年底市值 × 殖利率計算' + (st.dv === 're' ? '，當年底再投入。' : '，領出不再投入。') : '']);
  if (msg.length) return tlMsg(msg) + note;
  const R = tlCompound({ P, M, r, n, begin: st.at === 'begin', y: dv ? y : 0, re: st.dv === 're' }), [, inv, v, paid] = R[R.length - 1], out = st.dv === 'out';
  const A = dv ? tlCompound({ P, M, r, n, begin: st.at === 'begin', y, re: out }) : null;   // 第 38 輪 F38-3a：另一種股利處理方式（對照線）
  const ln = (rows, o) => [P].concat(rows.map(x => o ? x[2] + x[3] : x[2])), fin = (x, o) => fmt(o ? Math.round(x[2]) + Math.round(x[3]) : x[2]);   // 第 0 年 = 初始金額；領出 = 期末金額＋已領股利（與表格兩格相加一致）
  const G = [[out ? '期末金額＋已領股利' : '期末金額', ln(R, out), fin(R[n - 1], out), '', 'stroke="var(--blue)" stroke-width="2"'],
    ['累計投入', [P].concat(R.map(x => x[1])), fmt(inv), 'd', 'stroke="var(--text2)" stroke-width="1.5" stroke-dasharray="5 3"']];
  if (A) G.push([out ? '對照：股利再投入' : '對照：股利領出（期末金額＋已領股利）', ln(A, !out), fin(A[n - 1], !out), 'v', 'stroke="var(--violet)" stroke-width="1.5" stroke-dasharray="1 3" stroke-linecap="round"']);
  return `<table class="tl-kv">${tlRow('期末金額', fmt(v) + ' 元') + (out ? tlRow('已領股利', fmt(paid) + ' 元') : '') + tlRow('投入本金合計', fmt(inv) + ' 元') +
    tlRow(out ? '增加金額（含已領股利）' : '增加金額', tlS(Math.round(v + paid - inv), 0) + ' 元')}</table>` + tlCpGraph(G, n) + note +
    `<div class="tbl-wrap"><table class="tbl tl-yr" id="tlYr"><thead><tr><th>第幾年</th><th>累計投入</th><th>期末金額</th>${out ? '<th>已領股利</th>' : ''}</tr></thead><tbody>` +
    R.map(([k, a, b, c]) => `<tr${k % 5 && k !== n ? ' class="tl-x"' : ''}><td>${k}</td><td class="num">${fmt(a)}</td><td class="num">${fmt(b)}</td>${out ? `<td class="num">${fmt(c)}</td>` : ''}</tr>`).join('') +
    `</tbody></table></div>${n > 5 ? '<button class="chip tl-all" id="tlAll">顯示每一年</button>' : ''}`;
}

// 第 38 輪 F38-3a：複利逐年成長圖。G = [[名稱, 第 0～n 年的值, 第 n 年（與表格同格式）, 圖例樣式, 線的屬性]]；只畫線不塗色（D78-2 = A），
// 數字都在圖下 HTML（SVG 會被拉伸）。縱軸 0 起，格線間距 = 不小於最大值 ÷ 4 的 1、2、5 × 10^k（至少 1 元），1～4 條
function tlCpGraph(G, n) {
  const mx = Math.max(...G.map(g => Math.max(...g[1]))), e = 10 ** Math.floor(Math.log10(mx / 4));
  const step = Math.max(1, [1, 2, 5, 10].map(k => k * e).find(s => s >= mx / 4) || 10 * e), g = Math.ceil(mx / step), top = g * step;
  const X = i => (i / n * 100).toFixed(2), Y = v => (2 + (1 - v / top) * 96).toFixed(2), hl = (y, c) => `<line x1="0" x2="100" y1="${y}" y2="${y}" stroke="var(--${c})" vector-effect="non-scaling-stroke"/>`;
  let s = hl(Y(0), 'border2');
  for (let k = 1; k <= g; k++) s += hl(Y(k * step), 'border');
  [2, 0, 1].forEach(j => { if (G[j]) s += `<polyline points="${G[j][1].map((v, i) => X(i) + ',' + Y(v)).join(' ')}" fill="none" ${G[j][4]} vector-effect="non-scaling-stroke"/>`; });   // 虛線畫在最上面，重疊時仍看得到
  return `<svg class="tl-gr" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">${s}</svg><div class="kleg tl-lg">` +
    G.map(g => `<span class="lg"><i class="${g[3]}"></i>${g[0]} <b>${g[2]}</b> 元</span>`).join('') + `</div><div class="muted small">第 0～${n} 年；縱軸 0～${fmt(top)} 元，每格 ${fmt(step)} 元</div>`;
}

function tlPlOut(st, I) {
  const p1 = tlC(st.p1), p2 = String(st.p2).trim() === '' ? p1 : tlC(st.p2), q = tlNum(st.q, 0), n = st.u === 'lot' ? q * 1000 : q;
  const cap = tlNum(st.cap, 0), loan = String(st.loan).trim() === '' ? null : tlNum(st.loan, 0), rate = tlNum(st.rate, 3), days = tlNum(st.days, 0), fee = tlNum(st.fee, 0), call = tlNum(st.call, 0), msg = [];
  if (!(p1 > 0)) msg.push('請輸入擔保價格');
  if (!(n > 0)) msg.push('請輸入數量');
  if (!(cap >= 0 && cap <= 100)) msg.push('可借成數請輸入 0～100 的整數');
  if (loan !== null && !(loan >= 0)) msg.push('借款金額請輸入 0 以上的整數，或留空');
  if (!(rate >= 0 && rate <= 100)) msg.push('請輸入年利率（各券商不同，本站不預填）');
  if (!(days >= 1 && days <= TL_RULES.pl.max)) msg.push(`借款天數請輸入 1～${TL_RULES.pl.max} 的整數`);
  if (!(fee >= 0)) msg.push('手續費請輸入 0 以上的整數');
  if (!(call >= 100 && call <= 999)) msg.push('追繳門檻請輸入 100～999 的整數');
  const D = TL_RULES.pl, note = tlNote([I && I.al && I.al.some(a => a.t === 'disposal') ? '<b class="tl-warn">處置股可能不適用為擔保品，請洽券商</b>' : '',
    `證券商不限用途借貸：維持率低於 ${D.call}% 須於 2 個營業日內補繳至 ${D.back}%；未補繳且仍低於 ${D.call}%，自第 3 營業日起處分擔保品（俗稱斷頭）。銀行、證券金融公司依各自契約。`,
    `借滿 60% 時追繳價約為現價 −22%，借 40% 時約 −48%。`,
    '維持率 = 擔保品市值 ÷ 借款本金（不含利息），實際每日以收盤價整戶計算；本頁只算單檔，可把試算價格改低看變化；除權息後維持率也會下降。',
    '可借成數上限：得為融資融券的股票為前一營業日收盤價 × 60%，其餘 40%，券商可再調低；全額交割股不得為擔保品，處置股、槓反 ETF 請洽券商。']);
  if (msg.length) return tlMsg(msg) + note;
  const R = tlPledge({ p1, p2: p2 > 0 ? p2 : 0, n, cap, loan, rate: Math.round(rate * 1000), days, base: +st.base, call }), warn = [];
  if (cap > D.cap) warn.push(`成數超過證券商不限用途借貸官方上限 ${D.cap}%（其他管道依各自契約）`);
  if (R.over) warn.push(`超過可借上限，以上限 ${fmt(R.max)} 計算`);
  if (days > D.term) warn.push('每次最長 6 個月，超過需申請續借');
  let rows = tlRow('可借金額上限', fmt(R.max) + ' 元') + tlRow('本次借款', fmt(R.L) + ' 元') +
    tlRow('利息', fmt(R.I) + ` 元<br><span class="muted small">÷${st.base}，四捨五入到元</span>`) + tlRow('手續費', fmt(fee) + ' 元') +
    tlRow('到期應還（本金＋利息）', fmt(R.L + R.I) + ' 元') + tlRow('總成本（利息＋手續費）', fmt(R.I + fee) + ' 元') +
    tlRow('換算年化成本', R.L ? fmt((R.I + fee) / R.L * 365 / days * 100, 2) + '%' : '--');
  if (R.ratio != null) {
    const dp = Math.round((R.pc / p2 - 1) * 1000) / 10 || 0;
    rows += tlRow('目前擔保維持率', `<b class="tl-big">${fmt(R.ratio / 100, 2)}%</b><br><span class="small">${R.below ? '<b class="tl-warn">低於</b>' : R.eq ? '等於' : '高於'}追繳門檻 ${call}%${R.eq ? '（低於才追繳）' : ''}</span>`) +
      tlRow('追繳價', `<b class="tl-big">${fmt(R.pc / 100, 2)}</b><br><span class="small">收盤價低於 ${fmt(R.pc / 100, 2)} 時，維持率低於 ${call}%；與試算價格差 ${tlS(dp, 1)}%${p2 < R.pc ? '（目前已低於）' : ''}</span>`);
    if (R.below) rows += tlRow(`回到 ${R.back}%`, `需補擔保品市值 ${fmt(R.add)} 元<br>或償還本金 ${fmt(R.repay)} 元`);
  } else warn.push(R.L ? '請輸入試算價格（空白 = 擔保價格）' : '借款為 0，不計算維持率與追繳價');
  return (warn.length ? tlMsg(warn) : '') + `<table class="tl-kv">${rows}</table>` + note;
}

function tlDtForm(st) {
  const dt = st.mode === 'dt', rev = dt && st.dir === 's', bs = [tlIn('b', '買價（元）', st.b, rev ? '空白 = 只算兩平' : ''), tlIn('s', '賣價（元）', st.s, rev ? '' : '空白 = 只算兩平')];
  return `<div class="tl-segs">${tlSeg('mode', [['dt', '現股當沖'], ['g', '非當沖']], st.mode)}${dt ? tlSeg('dir', [['b', '先買後賣'], ['s', '先賣後買']], st.dir) : ''}` +
    `${tlSeg('k', [['s', '股票'], ['e', 'ETF'], ['b', '債券 ETF']], st.k)}</div>` + (rev ? bs.reverse() : bs).join('') +
    tlIn('n', '股數', st.n, dt ? '1,000 的倍數' : '零股可填') + tlIn('ref', '參考價（算漲跌停）', st.ref, '可空白') +
    tlIn('d', '手續費折扣（折）', st.d, '不打折 = 10') + tlIn('m', '最低手續費（元）', st.m);
}
function tlCpForm(st, I) {
  const dv = st.dv !== '0';
  return `<div class="tl-segs">${tlSeg('at', [['end', '期末投入'], ['begin', '期初投入']], st.at)}${tlSeg('dv', [['0', '不計股利'], ['re', '股利再投入'], ['out', '股利領出']], st.dv)}</div>` +
    tlIn('P', '初始金額（元）', st.P) + tlIn('M', '每月投入（元）', st.M) + tlIn('r', dv ? '價格年變動率（%）' : '年報酬率（%）', st.r, '自行假設，必填') + tlIn('n', '年數（1～50）', st.n) +
    (dv ? tlIn('y', '殖利率（%）', st.y, '必填') + (I && I.dy != null ? `<div class="muted small tl-f">本站最新殖利率 ${fmt(I.dy, 2)}%</div>` : '') : '');
}
function tlPlForm(st) {
  return `<div class="tl-segs">${tlSeg('u', [['lot', '張'], ['sh', '股']], st.u)}${tlSeg('base', [['365', '計息 ÷365'], ['360', '計息 ÷360']], st.base)}</div>` +
    tlIn('p1', '擔保價格（算可借上限）', st.p1) + tlIn('p2', '試算價格（算維持率）', st.p2, '空白 = 擔保價格') +
    tlIn('q', st.u === 'lot' ? '數量（張）' : '數量（股）', st.q) +
    `<div class="tl-f">${tlIn('cap', '可借成數（%）', st.cap)}<div data-g="cap" class="tl-chips"><button class="chip" data-v="60">60%：得為融資融券</button><button class="chip" data-v="40">40%：其他</button></div></div>` +   // 快捷鈕放在可借成數下方；質借表單改頂端對齊（.tl-pl），不把同列欄位往下推
    tlIn('loan', '借款金額（元）', st.loan, '空白 = 以上限計算') + tlIn('rate', '年利率（%）', st.rate, '必填，各券商不同') +
    tlIn('days', `借款天數（1～${TL_RULES.pl.max}）`, st.days) + tlIn('fee', '手續費（一次，元）', st.fee) + tlIn('call', '追繳門檻（%）', st.call);
}
// 第 39 輪 F39-1：除權息試算。金額都用 BigInt 整數：價格（分）、股利（10^-6 元）、配股（10^-8 股）
function tlDvOut(st, I) {
  const P = tlBig(st.p, 2), C = tlBig(st.c, 6), S = tlBig(st.s, 8), n = tlBig(st.n, 0), cost = tlBig(st.cost, 2), y1 = tlBig(st.y1, 6), msg = [];
  const has = k => String(st[k] == null ? '' : st[k]).trim() !== '', tw = st.mk === 'l', e = st.k === 'e';
  if (!P || !has('p')) msg.push('請輸入除權息前收盤（大於 0，小數最多 2 位）');
  if (C === null) msg.push('現金股利請填 0 以上的數字，小數最多 6 位');
  if (S === null) msg.push('每千股配股請填 0 以上的數字，小數最多 8 位');
  if (!n || !has('n')) msg.push('持有股數請輸入正整數');
  if (has('cost') && !cost) msg.push('持有成本請填大於 0 的數字（小數最多 2 位），或留空');
  if (y1 === null) msg.push('近一年現金股利請填 0 以上的數字（小數最多 6 位），或留空');
  if (C === 0n && S === 0n) msg.push('請輸入現金股利或配股');
  else if (P && C !== null && C >= P * 10000n) msg.push('現金股利須小於除權息前收盤');
  const note = tlNote(['參考價 = (前收 − 現金股利) ÷ (1 + 每千股配股 ÷ 1,000)；上市除息捨去、上市有配股與上櫃四捨五入到 0.01（本站用近一年官方參考價驗算）。',
    '官方以實際每股金額計算（常有小數尾數），只填到元或角時可能和官方差 0.01；有現金增資時參考價請看官方公告。配股 1 元 = 每千股 100 股（面額 10 元時）。',
    '可領現金元以下捨去；不足 1 股依公司公告折付現金，可在期限內湊股；實際以公司發放為準。',
    '二代健保補充保費：單次股利 2 萬元以上扣 2.11%，元以下四捨五入，單次以 1,000 萬元為上限；同一基準日的股票股利以面額一起計入，本頁只算現金股利。']);
  const hint = I && I.dvh ? tlNote(I.dvh) : '';
  if (msg.length) return tlMsg(msg) + hint + note;
  const E11 = 10n ** 11n, r = Number(tlExRef(P, C, S, tw)), lim = tlLimit(r, e), cash = n * C / 1000000n, sh = n * S, w = sh / E11, fr = sh % E11;
  const after = ((n * E11 + sh) * BigInt(r) * 10000n + n * C * E11 + 5n * 10n ** 16n) / 10n ** 17n;   // (股數＋配股) × 參考價＋現金股利，四捨五入到元
  const nhi = cash >= 20000n ? fmt(Number(((cash < 10000000n ? cash : 10000000n) * 211n + 5000n) / 10000n)) + ' 元（2.11%）' : '未達 2 萬元，不扣';
  let rows = tlRow('除權息參考價', `<b class="tl-big">${fmt(r / 100, 2)}</b>`) +
    tlRow('下一交易日漲跌停', `漲停 ${tlPx(lim[0], e)}、跌停 ${tlPx(lim[1], e)}`) +
    tlRow('可領現金股利', fmt(Number(cash)) + ' 元');
  if (S) rows += tlRow('配發股數', fmt(Number(w)) + ' 股' + (fr ? `<br><span class="small">另有不足 1 股 ${tlDec(fr, 11)} 股</span>` : '')) + tlRow('除權後股數', fmt(Number(n + w)) + ' 股');
  rows += tlRow('除權息前市值', tlY(Number(n * P)) + ' 元') + tlRow('除權息後市值＋現金股利', fmt(Number(after)) + ' 元') + tlRow('二代健保補充保費', nhi);
  if (C) rows += tlRow('本次現金股利 ÷ 前收', fmt(Number(C) / Number(P) / 100, 2) + '%');
  if (cost && has('y1')) rows += tlRow('成本殖利率（近一年 ÷ 成本）', fmt(Number(y1) / Number(cost) / 100, 2) + '%');
  return `<table class="tl-kv">${rows}</table>` + hint + tlNote([`漲跌停 = 參考價 ±${TL_RULES.limit}%，依升降單位取到可成交價${e ? '；國外成分、槓反 ETF 漲跌幅規定不同' : ''}。`,
    `除權息前後的總價值相同${fr ? '（不足 1 股以參考價計）' : ''}，差額來自參考價捨入到 0.01。`]) + note;
}
function tlDvForm(st) {
  return `<div class="tl-segs">${tlSeg('mk', [['l', '上市'], ['o', '上櫃']], st.mk)}${tlSeg('k', [['s', '股票'], ['e', 'ETF']], st.k)}</div>` +
    tlIn('p', '除權息前收盤（元）', st.p) + tlIn('c', '現金股利（元／股）', st.c, '空白 = 0') + tlIn('s', '每千股配股（股）', st.s, '空白 = 0') +
    tlIn('n', '持有股數', st.n) + tlIn('cost', '持有成本（元／股）', st.cost, '選填') + tlIn('y1', '近一年現金股利（元／股）', st.y1, '選填');
}
// 第 40 輪 F40-3：下一次除權除息預告（nx 第一筆）→ [帶入？, 提示]；含現增、待公告、超過 6 位小數不帶入（D86-3、D86-4 = A）
function tlNx(n, tw, e) {
  const w = `${md(n.d)} ${n.t === '息' ? '除息' : n.t === '權' ? '除權' : '除權息'}`;
  if (n.sr) return [false, `${w}含現金增資，參考價請看官方公告`];
  if (n.c == null) return [false, `${w}，金額待公告`];
  if (tlBig(String(n.c), 6) === null) return [false, `${w}的預告現金股利 ${n.c} 元超過 6 位小數，請依公告填寫`];
  return [true, `已帶入 ${w}的預告股利（${tw ? '證交所' : '櫃買中心'}預告表，僅供參考，以${e ? '發行人' : '公司'}公告為準）`];
}
// 第 39 輪 F39-2：帶入最近一次股利（D82-3 = A：前收用最新收盤）與近一年現金股利合計；回傳要帶入的欄位與提示。第 40 輪：有預告金額時改帶預告
function tlDvLoad(d, e) {
  const V = d.dv || [], x = V[V.length - 1], tw = d.market !== 'TPEx', D = d.prices.d, n = (d.nx || [])[0], N = n ? tlNx(n, tw, e) : [false, ''];
  const o = { mk: tw ? 'l' : 'o', c: '', s: '0', y1: '', cost: '' }, h = [];   // 換股票時清掉上一檔的持有成本
  if (N[0]) { o.c = String(n.c); o.s = n.s != null ? String(n.s) : '0'; h.push(N[1]); }
  if (!x || !x.t) return [o, h.concat(`${D[0]} 起沒有除權息紀錄，請依公司公告填寫`, n && !N[0] ? N[1] : [])];
  const from = new Date(Date.parse(D[D.length - 1]) - 365 * 864e5).toISOString().slice(0, 10);
  let y = 0n, k = 0, miss = false;
  V.forEach(v => { if (v.d > from && (v.t === '息' || v.t === '權息')) { const c = v.c == null ? null : tlBig(String(v.c), 6); if (c === null) miss = true; else { y += c; k++; } } });
  if (k) o.y1 = tlDec(y, 6);
  if (N[0]) { /* 已帶入預告 */ }
  else if (x.k === 'sc') h.push(`最近一次（${md(x.d)}）含現金增資，參考價請看官方公告；現金股利、配股沒有帶入`);
  else if (tw && x.c == null && x.a != null) h.push(`上市官方表只有 ${md(x.d)} 的權值＋息值合計 ${x.a} 元，請依公告填現金股利與配股`);
  else { o.c = x.c != null ? String(x.c) : '0'; o.s = x.s != null ? String(x.s) : '0'; h.push(`已帶入 ${md(x.d)} 的股利（最近一次），下次請依公司公告修改`); }
  if (n && !N[0]) h.push(N[1]);
  const ev = (d.ev || []).filter(v => v.d === x.d && v.t === x.t)[0], R = x.r != null ? x.r : ev && ev.r;
  if (R != null && x.p != null) h.push(`上次官方參考價 ${pfmt(R)}（${md(x.d)}，前收 ${pfmt(x.p)}）；前收改成 ${pfmt(x.p)} 可對照`);
  h.push(k ? `近一年現金股利 = ${md(from)} 以後 ${k} 次合計${miss ? '；部分缺值，請自行確認' : ''}` : miss ? `${md(from)} 以後的現金股利官方表沒有分項，請自行確認` : `${md(from)} 以後沒有現金股利`);
  return [o, h];
}
const TL_VIEW = { dt: ['交易成本與損益兩平', tlDtForm, tlDtOut], cp: ['複利', tlCpForm, tlCpOut], pl: ['股票質借（單檔擔保品）', tlPlForm, tlPlOut], dv: ['除權息試算', tlDvForm, tlDvOut] };
const TL_FOOT = '試算僅供參考，不代表實際成交、扣款或核貸金額；費率、稅率、折扣與規則以券商與主管機關公告為準。';

// 網址帶代號時讀最新收盤（股票 data/stocks、ETF data/etfp）；不在 latest.json 的代號不發請求
async function tlLoad(code) {
  TL.code = code; TL.info = null;
  if (!code) return;
  const L = App.latest, E = !L.stocks[code] && L.etfs && L.etfs.rows && L.etfs.rows[code];
  let d = null;
  if (/^[0-9A-Za-z]{4,6}$/.test(code) && (L.stocks[code] || E)) try { d = await loadStock(code, E ? 'etfp' : 'stocks'); } catch (e) { /* 讀不到就當作找不到 */ }
  const P = d && d.prices, i = P ? P.c.map(c => c != null).lastIndexOf(true) : -1;
  if (i < 0) { TL.info = { miss: code }; return; }
  const c = String(P.c[i]), last = P.d[P.d.length - 1];
  TL.info = { code, name: d.name, e: !!E, c: P.c[i], d: P.d[i], al: d.alerts || [], dy: d.fund && d.fund.dy, ex: d.nx ? d.nx[0].d : (d.dv || []).map(x => x.d).filter(x => x > last).sort()[0] };   // 第 40 輪：ex = 下一次預告日
  Object.assign(TL.dt, { b: c, s: '', ref: c, k: E ? 'e' : 's' });
  Object.assign(TL.pl, { p1: c, p2: '' });
  TL.cp.y = TL.info.dy != null ? String(TL.info.dy) : '';
  const [o, h] = tlDvLoad(d, !!E);                                                     // 第 39 輪 F39-2；第 40 輪傳 ETF 旗標
  TL.info.dvh = h;
  Object.assign(TL.dv, o, { p: c, k: E ? 'e' : 's' });
}
function tlInfo(I) {
  if (!I) return '';
  if (I.miss) return `<span class="muted small">找不到 ${esc(I.miss)} 的資料，請自行輸入價格</span>`;
  return `<span class="small"><a href="#/stock/${I.code}">${esc(I.name)} ${I.code}</a> ${md(I.d)} 收盤 <b class="num">${pfmt(I.c)}</b></span>${I.e ? '<span class="pill">ETF</span>' : ''}` +
    I.al.map(a => a.t === 'disposal' ? `<span class="pill al-d">${a.s > App.latest.date ? `即將處置（${md(a.s)} 起）` : `處置中（至 ${md(a.e)}）`}</span>` : '<span class="pill al-n">注意</span>').join('');
}
function tlDraw(tab) {
  const [title, form, out] = TL_VIEW[tab], st = TL[tab], I = TL.info, draw = () => out(st, I, tlToday());
  $('#view').innerHTML = pageTabsHTML('toolTabSeg', TL_TABS, tab) +
    `<section class="sec card"><div class="sec-h"><h2>${title}</h2>${tlInfo(I)}</div><div class="tl-form tl-${tab}" id="tlForm">${form(st, I)}</div></section>` +
    `<section class="sec card tl-out tl-o${tab}" id="tlOut">${draw()}</section><div class="muted small tl-foot">${TL_FOOT}${tab === 'pl' ? '成數、利率、計息與追繳門檻依各機構契約為準。本站不提供投資或借貸建議。' : '本站不提供投資建議。'}</div>`;
  onSeg('toolTabSeg', t => { history.replaceState(null, '', '#/tools/' + t + (TL.code ? '?c=' + TL.code : '')); tlDraw(t); });
  $('#tlForm').addEventListener('input', e => {
    const k = e.target.dataset.k;
    if (!k) return;
    st[k] = e.target.value;
    $('#tlOut').innerHTML = draw();
    const d = tlNum(st.d, 2), m = tlNum(st.m, 0);
    if (tab === 'dt' && (k === 'd' || k === 'm') && d > 0 && d <= 10 && m >= 0) localStore('fee', null, JSON.stringify({ d, m }));
  });
  $('#tlForm').addEventListener('click', e => {
    const b = e.target.closest('button'), g = b && b.closest('[data-g]');
    if (g) { st[g.dataset.g] = b.dataset.v; tlDraw(tab); }
  });
  $('#tlOut').addEventListener('click', e => { if (e.target.id === 'tlAll') { $('#tlYr').classList.add('all'); e.target.remove(); } });
}
window.renderTools = async function (arg) {
  const [t0, q = ''] = String(arg || '').split('?'), code = (q.match(/(?:^|&)c=([^&]*)/) || [])[1] || null;
  if (TL.dt.d == null) Object.assign(TL.dt, tlFeePref(localStore('fee', null)));
  if (code !== TL.code) await tlLoad(code);
  tlDraw(TL_VIEW[t0] ? t0 : 'dt');
};
