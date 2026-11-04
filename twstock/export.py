"""
把資料庫內容匯出成靜態 JSON（site/data/），網站只讀這些檔案、不需要後端：

  latest.json        今日總覽：大盤統計、台指期日 K、類股/產業鏈/概念股資金流（含回放用的每日座標）、
                     每檔股票最新指標、融資融券（margin）、ETF（etfs，與股票完全分開）
  stocks/{代號}.json 個股：完整日線、法人買賣超、月營收、本益比、所屬產業鏈、最新融資融券
"""
import json
import os
import time
from bisect import bisect_left
from collections import defaultdict
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from . import db
from .analysis.flow import LONG, group_flows, load_concepts, streak
from .analysis.forecast import build_forecast, load_oi
from .config import SITE_DATA_DIR, tw_now
from .health import build_status

REPLAY = 20                    # 泡泡圖回放天數
FUTURES_DAYS = 500             # 首頁台指期日 K 匯出天數
OI_DAYS = 120                  # 首頁法人未平倉走勢天數
INDEX_DAYS = 60                # 首頁加權／櫃買指數走勢線天數
REVENUE_MONTHS = 36            # 個股 JSON 匯出的月營收筆數（累計年增、新高以全部月份計算後再截取）
WINDOW = REPLAY + LONG - 1     # 計算回放第一天的 20 日均線所需天數
YI = 1e8                       # 億
INSTI_DAYS = 20                # 首頁官方三大法人走勢天數
ADJ_MIN, ADJ_MAX = 0.02, 20     # 還原係數合理範圍；超出視為資料錯誤，不採用
_SRC_RANK = {"TWTAUU": 0, "TWTB8U": 0}   # 同一列有多筆官方事件時優先（恢復買賣參考價已含同日除權）
CAP_TYPES = ("權", "權息", "減", "面", "調")
CAP_DAYS = 90
# 升降單位（一般股票）：(價格上限, 單位)
MARGIN_DAYS = 20               # 首頁上市股票融資增減迷你柱天數
COVER_MIN = 99.0               # 維持率分子涵蓋的融資張數 ÷ 官方融資張數（%）低於此值不顯示
_TICKS = ((Decimal(10), Decimal("0.01")), (Decimal(50), Decimal("0.05")), (Decimal(100), Decimal("0.1")),
          (Decimal(500), Decimal("0.5")), (Decimal(1000), Decimal(1)), (Decimal("Infinity"), Decimal(5)))


def _f(v, nd=2):
    return None if v is None else round(float(v), nd)


def _write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    # 先寫暫存檔再取代：匯出途中開網頁、或寫到一半失敗，都不會讀到不完整的 JSON
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        # separators 去掉空白，檔案小約 15%
        tmp.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def _pct(close, change):
    if close is None or change is None or close == change:
        return None
    return float(change) / (float(close) - float(change)) * 100


def _revenue_rows(rows):
    """
    rows: 某股票 [[年, 月, 營收(千元), 月增%, 年增%], ...]（舊到新、資料庫全部月份）
    回傳每列再加兩欄：
      累計年增%：當年 1 月～該月合計 ÷ 前一年同期合計 − 1；兩段任一月份缺資料或去年合計 ≤ 0 → None
      新高年數 N：該月營收 > 之前所有月份，且之前至少已有 24 個月資料時 = 資料涵蓋的整年數；否則 0
    """
    by_month = {(y, m): rev for y, m, rev, *_ in rows}
    first = rows[0][0] * 12 + rows[0][1] if rows else 0
    out, peak = [], None
    for y, m, rev, mom, yoy in rows:
        cur = [by_month.get((y, k)) for k in range(1, m + 1)]
        prev = [by_month.get((y - 1, k)) for k in range(1, m + 1)]
        cum = None
        if None not in cur and None not in prev and sum(prev) > 0:
            cum = round((sum(cur) / sum(prev) - 1) * 100, 2)
        months = y * 12 + m - first + 1                  # 資料涵蓋月數（含當月）
        hi = months // 12 if peak is not None and months > 24 and rev > peak else 0
        peak = rev if peak is None else max(peak, rev)
        out.append([y, m, rev, mom, yoy, cum, hi])
    return out


def _alert_status(kind, announce, start, end, today):
    """處置：迄日 ≥ 資料日才有效，起日 > 資料日為「即將」；注意：公告日 = 資料日才有效。"""
    if kind == "disposal":
        if end is None or end < today:
            return None
        return "upcoming" if start and start > today else "active"
    return "notice" if announce == today else None


def _price_events(d_, c, ch, market, official):
    """
    個股的價格調整事件（舊到新）：[{i, d, t, p, r}]。i = 生效的資料列索引（事件日當天或之後第一列），
    d = 該列日期字串，t = 類型，p = 事件前收盤，r = 參考價。另回傳因係數不合理而略過的 [(日期, 係數)]。
    官方事件在第一筆資料之前或最後一筆之後的略過；上櫃另以「收盤 − 官方漲跌」反推（類型「調」），
    只在前一列有成交、漲跌有數值時計算，與官方事件同一列時以官方為準。
    """
    at, bad = {}, []

    def add(i, t, p, r):
        f = r / p
        if ADJ_MIN <= f <= ADJ_MAX:
            at[i] = {"i": i, "d": str(d_[i]), "t": t, "p": p, "r": r}
        else:
            bad.append((str(d_[i]), round(f, 4)))

    for e in sorted(official, key=lambda e: (e["d"], _SRC_RANK.get(e["src"], 1))):
        i = bisect_left(d_, e["d"])
        if 0 < i < len(d_) and i not in at:
            add(i, e["t"], e["p"], e["r"])
    if market == "TPEx":
        for i in range(1, len(d_)):
            if i in at or c[i] is None or c[i - 1] is None or ch[i] is None:
                continue
            p, r = float(c[i - 1]), round(float(c[i]) - float(ch[i]), 2)
            if abs(r - p) >= 0.005:
                add(i, "調", p, r)
    return [at[i] for i in sorted(at)], bad


def _adj_factors(n, ev):
    """每個資料列的還原係數 = 該列之後所有事件（參考價 ÷ 前收）的乘積；事件當天與之後為 1。"""
    af, k, j = [1.0] * n, 1.0, len(ev) - 1
    for i in range(n - 1, -1, -1):
        while j >= 0 and ev[j]["i"] > i:
            k *= ev[j]["r"] / ev[j]["p"]
            j -= 1
        af[i] = k
    return af


def _tick_round(price: float) -> float:
    """參考價依升降單位四捨五入（half-up）：官方漲跌相對取整後的開盤參考價。升降單位由取整前的價格決定。"""
    p = Decimal(str(price))
    tick = next(t for limit, t in _TICKS if p < limit)
    return float((p / tick).quantize(Decimal(1), rounding=ROUND_HALF_UP) * tick)


def _changes(d_, c, ch, market, ev):
    """
    每日漲跌（P14）。回傳 (chs, rel, miss)：
      chs[i] 漲跌（元），無成交或無法判定為 None；rel[i] 分支 2 所相對的最後成交日（date），其他 None；
      miss   上市「官方漲跌 0、收盤 ≠ 前一個成交收盤」但找不到事件的日期（維持不比價）。
    判斷順序：1. 前一個成交列（不含）到今天（含）之間有事件 → 收盤 − 參考價
              2. 上市且前一個資料列無成交 → 收盤 − 最後成交日收盤
              3. 官方漲跌（上市官方 0 且收盤 ≠ 前收 → None）
    """
    at = {e["i"]: e for e in ev}
    chs, rel, miss, j = [], [], [], None
    for i in range(len(d_)):
        x = r = None
        if c[i] is not None:
            e = next((at[k] for k in range(i, -1 if j is None else j, -1) if k in at), None)
            if e is not None:
                x = round(float(c[i]) - _tick_round(e["r"]), 2)
            elif market == "TWSE" and j is not None and j != i - 1:
                x, r = round(float(c[i]) - float(c[j]), 2), d_[j]
            else:
                x = _f(ch[i])
                if x == 0 and market == "TWSE" and j is not None and c[i] != c[j]:
                    x = None
                    miss.append(d_[i])
            j = i
        chs.append(x)
        rel.append(r)
    return chs, rel, miss


def _side(x):
    """漲跌家數歸類；None（不比價、官方未提供）沿用既有做法算平盤。"""
    return "up" if (x or 0) > 0 else "down" if (x or 0) < 0 else "flat"


def _cap_event(ev, today):
    """P16：最近一次股本變動事件（參考價變動 ≥ 10%）在 CAP_DAYS 天內 → {"d", "t"}；否則 None。"""
    for e in reversed(ev):
        if e["t"] in CAP_TYPES and abs(e["r"] / e["p"] - 1) >= 0.1:
            return {"d": e["d"], "t": e["t"]} if (today - date.fromisoformat(e["d"])).days <= CAP_DAYS else None
    return None


def _insti_official(amount):
    """A2：amount = {日期: {單位: 買賣差額(元)}}；有「合計」的最後一天為資料日。外資 = 外資及陸資（外資自營商已含在自營商）。"""
    days = [d for d in sorted(amount) if amount[d].get("total") is not None]
    if not days:
        return None
    yi = lambda v: round((v or 0) / YI, 1)
    a, recent = amount[days[-1]], days[-INSTI_DAYS:]
    foreign = [amount[d].get("foreign") or 0 for d in days]
    return {"date": str(days[-1]), "foreign": yi(a.get("foreign")), "trust": yi(a.get("trust")),
            "dealer": yi((a.get("dealer_self") or 0) + (a.get("dealer_hedge") or 0)), "total": yi(a["total"]),
            "d": [str(d) for d in recent], "f": [yi(v) for v in foreign[-INSTI_DAYS:]],
            "t": [yi(amount[d]["total"]) for d in recent], "fs": streak(foreign)}


# ─── 融資融券（B2＋A4）與 ETF（E1）────────────────────────
def usage(balance, limit):
    """融資（券）使用率 %：餘額 ÷ 限額，截斷到小數 2 位（與櫃買官方欄位一致）；限額 0 或空 → None。"""
    return balance * 10000 // limit / 100 if limit and balance is not None else None


def short_ratio(short, margin):
    """券資比 %：融券餘額 ÷ 融資餘額，四捨五入到小數 2 位；融資 0 → None。"""
    return round(short / margin * 100, 2) if margin else None


def last_close(series, day):
    """series：[(日期, 收盤)] 舊到新；回傳日期 ≤ day 的最後一個非空收盤（當日無成交用最近收盤）；沒有 → None。"""
    return next((float(c) for d, c in reversed(series) if d <= day and c is not None), None)


def maint_ratio(items, official_lots, amount_k):
    """
    大盤融資維持率（自算）= Σ(融資張數 × 1,000 × 收盤) ÷ (官方融資金額仟元 × 1,000) × 100。
    items：[(融資張數, 收盤或 None)]，股票＋ETF。涵蓋率 = 有收盤的張數 ÷ 官方融資張數（%）。
    回傳 (維持率, 涵蓋率)，各取小數 2 位；涵蓋率 < COVER_MIN 或沒有金額 → 維持率 None。
    """
    covered = sum(n for n, c in items if c is not None)
    cov = round(covered / official_lots * 100, 2) if official_lots else 0.0
    if not amount_k or cov < COVER_MIN:
        return None, cov
    return round(sum(n * c for n, c in items if c is not None) / amount_k * 100, 2), cov


def stock_margin(rows: dict, mdate, d5):
    """
    個股 JSON 的 margin。rows：{日期: (融資前日, 融資餘額, 融資限額, 融券前日, 融券餘額, 註記)}；
    mdate：該市場最新融資融券日；d5：往前第 5 個融資融券日（不足 6 天為 None）。該股當天沒有列 → None（無信用交易）。
    """
    r = rows.get(mdate)
    if r is None:
        return None
    mp, mb, ml, sp, sb, nt = r
    old = rows.get(d5) if d5 else None
    out = {"d": str(mdate), "mb": mb, "m1": mb - mp, "m5": mb - old[1] if old else None,
           "sb": sb, "s1": sb - sp, "sr": short_ratio(sb, mb), "mu": usage(mb, ml)}
    if nt:
        out["nt"] = nt
    return out


def market_margin(dates, official, stocks, etfs, close):
    """
    一個市場的融資融券區塊（latest.json 的 margin.TWSE／margin.TPEx）。
    dates：該市場有官方合計的日期（舊到新）；official：{日期: (資前, 資今, 券前, 券今, 金前, 金今)}；
    stocks、etfs：{日期: [(代號, 融資前日, 融資餘額, 融券前日, 融券餘額)]}；close(代號, 日期, 是否ETF) → 收盤或 None。
    頭條（mb、sb…）只用股票；etf 另計；維持率分子用股票＋ETF、分母用官方融資金額。
    """
    if not dates:
        return None
    d = dates[-1]
    pct = lambda a, b: round(a / b * 100, 2) if b else None
    total = lambda rows, i: sum(r[i] for r in rows)

    def ratio(day):
        items = [(r[2], close(r[0], day, False)) for r in stocks.get(day, [])] + \
                [(r[2], close(r[0], day, True)) for r in etfs.get(day, [])]
        return maint_ratio(items, official[day][1], official[day][5])

    S, E, o = stocks.get(d, []), etfs.get(d, []), official[d]
    mb, mp, sb, sp = total(S, 2), total(S, 1), total(S, 4), total(S, 3)
    mr, cov = ratio(d)
    recent = dates[-MARGIN_DAYS:]
    return {"d": str(d), "mb": mb, "m1": mb - mp, "mp": pct(mb - mp, mp), "sb": sb, "s1": sb - sp, "sp": pct(sb - sp, sp),
            "sr": short_ratio(sb, mb), "amt": round(o[5] / 1e5, 1), "amt1": round((o[5] - o[4]) / 1e5, 1),
            "mr": mr, "mr0": ratio(dates[-2])[0] if len(dates) > 1 else None, "cov": cov,
            "etf": {"mb": total(E, 2), "m1": total(E, 2) - total(E, 1), "sb": total(E, 4), "s1": total(E, 4) - total(E, 3)},
            "d20": [str(x) for x in recent], "m20": [total(stocks.get(x, []), 2) - total(stocks.get(x, []), 1) for x in recent]}


def _load_margin(cur):
    """回傳 (各市場日期, 官方合計, 股票列, ETF 列, 個股 rows)；沒有融資融券資料時日期為空。"""
    mdates = [r[0] for r in cur.execute("SELECT DISTINCT TOP 25 trade_date FROM margin_market ORDER BY trade_date DESC")][::-1]
    dates, official = defaultdict(list), defaultdict(dict)
    stocks, etfs = defaultdict(lambda: defaultdict(list)), defaultdict(lambda: defaultdict(list))
    per_stock = defaultdict(dict)
    if not mdates:
        return dates, official, stocks, etfs, per_stock
    for d, m, *v in cur.execute("SELECT trade_date, market, margin_prev, margin_balance, short_prev, short_balance, "
                                "amount_prev, amount_balance FROM margin_market WHERE trade_date >= ? ORDER BY trade_date", mdates[0]):
        dates[m].append(d)
        official[m][d] = v
    for code, m, d, mp, mb, ml, sp, sb, nt in cur.execute("""
        SELECT s.stock_code, s.market_type, x.trade_date, x.margin_prev, x.margin_balance, x.margin_limit,
               x.short_prev, x.short_balance, x.note
        FROM margin_trades x JOIN stocks s ON s.stock_id = x.stock_id WHERE x.trade_date >= ?""", mdates[0]):
        stocks[m][d].append((code, mp, mb, sp, sb))
        per_stock[code][d] = (mp, mb, ml, sp, sb, nt)
    for code, m, d, mp, mb, sp, sb in cur.execute("""
        SELECT e.etf_code, e.market_type, x.trade_date, x.margin_prev, x.margin_balance, x.short_prev, x.short_balance
        FROM etf_margin x JOIN etfs e ON e.etf_id = x.etf_id WHERE x.trade_date >= ?""", mdates[0]):
        etfs[m][d].append((code, mp, mb, sp, sb))
    return dates, official, stocks, etfs, per_stock


def _load_etfs(cur, since):
    """(ETF 收盤序列 {代號: [(日期, 收盤)]}（since 起）, 最新一天的 ETF 列 {市場: (日期, [列])})。"""
    px = defaultdict(list)
    for code, d, c in cur.execute("""
        SELECT e.etf_code, x.trade_date, x.close_price FROM etf_daily x JOIN etfs e ON e.etf_id = x.etf_id
        WHERE x.trade_date >= ? ORDER BY e.etf_code, x.trade_date""", since):
        px[code].append((d, c))
    latest = {}
    for code, name, m, d, c, ch, v, tv in cur.execute("""
        SELECT e.etf_code, e.etf_name, e.market_type, x.trade_date, x.close_price, x.change, x.volume, x.trade_value
        FROM etf_daily x JOIN etfs e ON e.etf_id = x.etf_id
        WHERE x.trade_date = (SELECT MAX(y.trade_date) FROM etf_daily y JOIN etfs z ON z.etf_id = y.etf_id
                              WHERE z.market_type = e.market_type)
        ORDER BY e.etf_code"""):
        latest.setdefault(m, (d, []))[1].append((code, name, c, ch, v, tv))
    return px, latest


def etf_block(latest, margin_rows):
    """latest.json 的 etfs。margin_rows：{代號: (融資前日, 融資餘額, 融券前日, 融券餘額)}（該市場最新融資融券日）。"""
    if not latest:
        return None
    rows = {}
    for m, (d, items) in latest.items():
        for code, name, c, ch, v, tv in items:
            r = {"n": name, "m": m, "c": _f(c), "ch": _f(ch), "p": _f(_pct(c, ch)) if c is not None else None,
                 "v": round((v or 0) / 1000), "tv": round((tv or 0) / YI, 2)}
            mg = margin_rows.get(code)
            if mg:
                r.update(mb=mg[1], m1=mg[1] - mg[0], sb=mg[3], s1=mg[3] - mg[2])
            rows[code] = r
    return {"dates": {m: str(d) for m, (d, _) in latest.items()}, "rows": rows}


def _load_chains(cur):
    """回傳 ({產業鏈: [代號...]}, {代號: [[產業鏈, 區段, [細項...]], ...]})。"""
    groups, tags = defaultdict(list), defaultdict(dict)
    for chain, seg, sub, code in cur.execute("""
        SELECT chain_name, segment_name, sub_name, stock_code FROM industry_chains
        ORDER BY chain_id, segment_id, sub_id"""):
        if code not in groups[chain]:
            groups[chain].append(code)
        subs = tags[code].setdefault((chain, seg), [])
        if sub and sub not in subs:
            subs.append(sub)
    return dict(groups), {c: [[ch, seg, subs] for (ch, seg), subs in t.items()] for c, t in tags.items()}


def _load_futures(cur, commodity="TX"):
    """近月連續日 K（日盤）＋最近一次夜盤。近月 = 當天有成交價的最近到期月份。"""
    near = {}
    for r in cur.execute("""
        SELECT trade_date, session, contract_month, open_price, high_price, low_price, close_price,
               change, volume, open_interest
        FROM futures_daily_prices
        WHERE commodity_id = ? AND close_price IS NOT NULL
        ORDER BY trade_date, session, contract_month""", commodity):
        near.setdefault((r[0], r[1]), r)     # 同日同時段第一筆 = 最近月份
    day = [v for (d, s), v in sorted(near.items()) if s == "DAY"]
    night = [v for (d, s), v in sorted(near.items()) if s == "NIGHT"]
    if not day:
        return None
    n = night[-1] if night else None
    return {
        "id": commodity, "name": "台指期近月",
        "d": [str(r[0]) for r in day], "m": [r[2] for r in day],
        "o": [_f(r[3]) for r in day], "h": [_f(r[4]) for r in day], "l": [_f(r[5]) for r in day],
        "c": [_f(r[6]) for r in day], "ch": [_f(r[7]) for r in day],
        "v": [r[8] for r in day], "oi": [r[9] for r in day],
        # 夜盤 trade_date 是歸屬日：標示 D 的夜盤 = D 前一個交易日 15:00 ~ D 05:00
        "night": {"date": str(n[0]), "m": n[2], "o": _f(n[3]), "h": _f(n[4]), "l": _f(n[5]),
                  "c": _f(n[6]), "ch": _f(n[7]), "v": n[8]} if n else None,
    }


def _load_futures_oi(cur, oi: dict):
    """最新一天大台的法人多空未平倉、約當大台淨額與增減，及近 OI_DAYS 天的約當大台淨額走勢。"""
    days = sorted(oi)
    if len(days) < 2:
        return None
    d, p = days[-1], days[-2]
    txf = {(r[0], r[1]): r[2:] for r in cur.execute("""
        SELECT trade_date, investor, long_oi, short_oi, net_oi FROM futures_institutional
        WHERE commodity_id = 'TXF' AND trade_date IN (?, ?)""", d, p)}
    inv = []
    for key, name in (("foreign", "外資"), ("trust", "投信"), ("dealer", "自營商")):
        lo, so, net = txf.get((d, key), (None, None, None))
        prev = txf.get((p, key), (None, None, None))[2]
        inv.append({"k": key, "n": name, "long": lo, "short": so, "net": net,
                    "chg": net - prev if net is not None and prev is not None else None,
                    "eq": round(oi[d][key]), "eq_chg": round(oi[d][key] - oi[p][key])})
    recent = days[-OI_DAYS:]
    return {"date": str(d), "prev": str(p), "inv": inv, "d": [str(x) for x in recent],
            **{k: [round(oi[x][k]) for x in recent] for k in ("foreign", "trust", "dealer")}}


def export_all() -> float:
    """回傳完整匯出耗時（秒）。"""
    t0 = time.monotonic()
    now = tw_now()
    conn = db.connect()
    cur = conn.cursor()

    # 有成交也有法人資料的交易日，取最近 WINDOW 天
    dates = [r[0] for r in cur.execute(f"""
        SELECT TOP {WINDOW} d.trade_date FROM (SELECT DISTINCT trade_date FROM daily_prices) d
        WHERE EXISTS (SELECT 1 FROM institutional_trades i WHERE i.trade_date = d.trade_date)
        ORDER BY d.trade_date DESC""").fetchall()][::-1]
    if not dates:
        raise SystemExit("❌ 資料庫沒有同時具備成交與法人資料的交易日，請先執行 collect / history")
    latest_date = max(r[0] for r in cur.execute("SELECT MAX(trade_date) FROM daily_prices").fetchall())

    stocks = {r[0]: {"name": r[1], "market": r[2], "industry": r[3] or "其他"}
              for r in cur.execute("SELECT stock_code, stock_name, market_type, industry FROM stocks")}

    # ── 每檔股票完整日線 + 法人 ──
    prices = defaultdict(list)
    for r in cur.execute("""
        SELECT s.stock_code, d.trade_date, d.open_price, d.high_price, d.low_price, d.close_price,
               d.volume, d.trade_value, d.change,
               i.foreign_net, i.trust_net, i.dealer_net, i.total_net
        FROM daily_prices d
        JOIN stocks s ON s.stock_id = d.stock_id
        LEFT JOIN institutional_trades i ON i.stock_id = d.stock_id AND i.trade_date = d.trade_date
        ORDER BY s.stock_code, d.trade_date"""):
        prices[r[0]].append(r[1:])

    fund = {r[0]: r[1:] for r in cur.execute("""
        SELECT stock_code, pe_ratio, pb_ratio, dividend_yield, trade_date FROM (
            SELECT s.stock_code, f.*, ROW_NUMBER() OVER (PARTITION BY f.stock_id ORDER BY f.trade_date DESC) rn
            FROM stock_fundamentals f JOIN stocks s ON s.stock_id = f.stock_id) x
        WHERE rn = 1""")}

    revenue = defaultdict(list)
    for r in cur.execute("""
        SELECT s.stock_code, m.revenue_year, m.revenue_month, m.revenue, m.revenue_mom, m.revenue_yoy
        FROM monthly_revenue m JOIN stocks s ON s.stock_id = m.stock_id
        ORDER BY s.stock_code, m.revenue_year, m.revenue_month"""):
        revenue[r[0]].append([r[1], r[2], r[3], _f(r[4]), _f(r[5])])
    chains, chain_of = _load_chains(cur)
    futures = _load_futures(cur)
    oi = load_oi(cur)
    futures_oi = _load_futures_oi(cur, oi)
    forecast = build_forecast(oi, [date.fromisoformat(x) for x in futures["d"]], futures["ch"]) \
        if futures else None
    if futures:
        futures.update({k: futures[k][-FUTURES_DAYS:] for k in ("d", "m", "o", "h", "l", "c", "ch", "v", "oi")})
    index_rows = defaultdict(list)
    for code, d, c, ch in cur.execute(
            "SELECT index_code, trade_date, close_price, change FROM market_index ORDER BY index_code, trade_date"):
        index_rows[code].append((d, c, ch))
    amount = defaultdict(dict)
    for d, unit, net in cur.execute("SELECT trade_date, unit, net_amount FROM insti_amount"):
        amount[d][unit] = net
    alerts = defaultdict(list)
    for code, kind, ann, start, end, reason, measure in cur.execute("""
        SELECT s.stock_code, a.alert_type, a.announce_date, a.start_date, a.end_date, a.reason, a.measure
        FROM stock_alerts a JOIN stocks s ON s.stock_id = a.stock_id
        WHERE ISNULL(a.end_date, a.announce_date) >= ?
        ORDER BY a.announce_date""", latest_date):
        if _alert_status(kind, ann, start, end, latest_date):
            alerts[code].append({"t": kind, "a": str(ann), "s": start and str(start), "e": end and str(end),
                                 "r": reason, "m": measure})
    events = defaultdict(list)
    for code, d, t, p, r, src in cur.execute("""
        SELECT s.stock_code, e.event_date, e.event_type, e.prev_close, e.ref_price, e.source
        FROM price_events e JOIN stocks s ON s.stock_id = e.stock_id
        ORDER BY s.stock_code, e.event_date"""):
        events[code].append({"d": d, "t": t, "p": float(p), "r": float(r), "src": src})
    mdates, mofficial, mstocks, metfs, mper = _load_margin(cur)
    first_m = min((ds[0] for ds in mdates.values()), default=latest_date)
    etf_px, etf_latest = _load_etfs(cur, first_m - timedelta(days=60))
    status = build_status(cur, latest_date, now)
    conn.close()
    mlast = {m: ds[-1] for m, ds in mdates.items()}
    m5 = {m: ds[-6] if len(ds) >= 6 else None for m, ds in mdates.items()}

    concepts = load_concepts()
    concept_of = defaultdict(list)
    for name, codes in concepts.items():
        for c in codes:
            concept_of[c].append(name)

    # ── 個股檔 + 最新指標 ──
    window = set(dates)
    daily = {}            # 板塊計算用：{代號: {日期: {net, turnover, pct}}}
    snapshot = {}
    market = {m: {"up": 0, "down": 0, "flat": 0, "turnover": 0.0} for m in ("TWSE", "TPEx")}
    insti_total = {"foreign": 0.0, "trust": 0.0, "dealer": 0.0}
    insti_otc = {"foreign": 0.0, "trust": 0.0, "dealer": 0.0}     # 上櫃估算（張數 × 收盤）
    bad_all, miss_all, n_ev, n_inferred = [], [], 0, 0
    w52_start = latest_date - timedelta(days=365)
    db_first = min(rows[0][0] for rows in prices.values())   # 全市場最早日線

    for code, rows in prices.items():
        info = stocks.get(code)
        if not info:
            continue
        d_, o, h, l, c, v, tv, ch, fn, tn, dn, total = zip(*rows)

        # 還原事件與係數（B1）；漲跌三分支（P14）
        ev, bad = _price_events(d_, c, ch, info["market"], events.get(code, []))
        af = _adj_factors(len(d_), ev)
        chs, rel, miss = _changes(d_, c, ch, info["market"], ev)
        bad_all += [(code, *x) for x in bad]
        miss_all += [(code, x) for x in miss]
        n_ev += len(ev)
        n_inferred += sum(e["t"] == "調" for e in ev)

        _write(SITE_DATA_DIR / "stocks" / f"{code}.json", {
            "code": code, **info, "concepts": concept_of.get(code, []), "chains": chain_of.get(code, []),
            "prices": {"d": [str(x) for x in d_], "o": [_f(x) for x in o], "h": [_f(x) for x in h],
                       "l": [_f(x) for x in l], "c": [_f(x) for x in c],
                       "v": [round(x / 1000) if x else 0 for x in v], "ch": chs},   # 張
            "ev": [{k: e[k] for k in ("d", "t", "p", "r")} for e in ev],
            "insti": {"f": [round(x / 1000) if x is not None else None for x in fn],   # 張
                      "t": [round(x / 1000) if x is not None else None for x in tn],
                      "dl": [round(x / 1000) if x is not None else None for x in dn]},
            "revenue": _revenue_rows(revenue.get(code, []))[-REVENUE_MONTHS:],
            "fund": dict(zip(("pe", "pb", "dy"), map(_f, fund[code][:3])), date=str(fund[code][3]))
                    if code in fund else None,
            **({"capchg": cap} if (cap := _cap_event(ev, latest_date)) else {}),
            **({"alerts": alerts[code]} if code in alerts else {}),
            # 該市場有融資融券資料時才有 margin；null = 不在信用交易清單（無信用交易）
            **({"margin": stock_margin(mper.get(code, {}), mlast[info["market"]], m5[info["market"]])}
               if info["market"] in mlast else {}),
        })

        # 板塊計算用的近 WINDOW 天
        net_value, f_value, t_value, d_value = [], [], [], []
        for i, day in enumerate(d_):
            close = float(c[i]) if c[i] is not None else None
            net = (total[i] or 0) * close / YI if close else 0.0
            if day in window:
                daily.setdefault(code, {})[day] = {
                    "net": net, "turnover": (tv[i] or 0) / YI, "pct": _pct(c[i], chs[i])}
            net_value.append(net)
            for arr, src in ((f_value, fn), (t_value, tn), (d_value, dn)):
                arr.append((src[i] or 0) * close / YI if close else 0.0)

        if d_[-1] != latest_date:
            continue    # 今天沒有資料列（停牌、下市）的股票不列入
        traded = [i for i, x in enumerate(c) if x is not None]
        if not traded:
            continue
        j = traded[-1]                      # 最後一個有成交的日子
        no_trade = j != len(d_) - 1         # 今天有資料列但沒有成交（開高低收為 --）
        pct = None if no_trade else _pct(c[-1], chs[-1])
        m = market[info["market"]]
        if not no_trade:                    # 無成交不計入漲跌家數
            m[_side(chs[-1])] += 1
        m["turnover"] += (tv[-1] or 0) / YI
        # 法人指標以「有法人資料的最後一天」為準（法人資料比行情晚公布）
        k = max(i for i, day in enumerate(d_) if day <= dates[-1]) if d_[0] <= dates[-1] else None
        n = k + 1 if k is not None else 0
        net_value, f_value, t_value, d_value = net_value[:n], f_value[:n], t_value[:n], d_value[:n]
        if n:
            insti_total["foreign"] += f_value[-1]
            insti_total["trust"] += t_value[-1]
            insti_total["dealer"] += d_value[-1]
        if n and info["market"] == "TPEx":
            insti_otc["foreign"] += f_value[-1]
            insti_otc["trust"] += t_value[-1]
            insti_otc["dealer"] += d_value[-1]
        # 52 週高低用還原價（B1）
        w52 = [(float(h[i]) * af[i], float(l[i]) * af[i]) for i in range(len(d_))
               if d_[i] >= w52_start and h[i] is not None and l[i] is not None]
        snapshot[code] = {
            "n": info["name"], "m": info["market"], "i": info["industry"],
            # 今天無成交時 c 是最後成交日的收盤，nt 記該日期
            "c": _f(c[j]), "ch": None if no_trade else chs[-1], "p": _f(pct),
            **({"nt": str(d_[j])} if no_trade else {}),
            **({"rel": str(rel[-1])} if not no_trade and rel[-1] else {}),
            "v": round((v[-1] or 0) / 1000), "tv": _f((tv[-1] or 0) / YI),
            "n1": _f(net_value[-1]) if net_value else None,
            "n5": _f(sum(net_value[-5:])), "n20": _f(sum(net_value[-20:])),
            # 外資 f、投信 t、自營 d 的 1 日 / 5 日買賣超（億）
            **({"f1": _f(f_value[-1]), "t1": _f(t_value[-1]), "d1": _f(d_value[-1]),
                "f5": _f(sum(f_value[-5:])), "t5": _f(sum(t_value[-5:])), "d5": _f(sum(d_value[-5:])),
                "fs": streak(f_value[-30:]), "ts": streak(t_value[-30:])} if n else {}),
            "s": streak(net_value[-30:]),
            "h52": _f(max(x[0] for x in w52)) if w52 else None,
            "l52": _f(min(x[1] for x in w52)) if w52 else None,
            # 個股第一筆日線晚於「全市場起點」與「52 週起點」兩者時，才另外標示高低點起算日
            **({"hf": str(d_[0])} if d_[0] > max(db_first, w52_start) else {}),
            # 有效的處置 [起日, 迄日]（多筆取起日最早者）與資料日當天的注意股
            **({"dsp": min([a["s"], a["e"]] for a in alerts[code] if a["t"] == "disposal")}
               if any(a["t"] == "disposal" for a in alerts.get(code, [])) else {}),
            **({"ntc": 1} if any(a["t"] == "notice" for a in alerts.get(code, [])) else {}),
            **({"pe": _f(fund[code][0]), "pb": _f(fund[code][1]), "dy": _f(fund[code][2])}
               if code in fund else {}),
        }

    industries = defaultdict(list)
    for code in snapshot:
        industries[snapshot[code]["i"]].append(code)

    # 維持率用的收盤：股票取 prices（日期 ≤ 當日最後收盤），ETF 取 etf_daily
    stock_px = {code: [(r[0], r[4]) for r in rows] for code, rows in prices.items()}
    close = lambda code, day, is_etf: last_close((etf_px if is_etf else stock_px).get(code, []), day)
    margin = {m: market_margin(mdates[m], mofficial[m], mstocks[m], metfs[m], close) for m in ("TWSE", "TPEx")
              if mdates.get(m)} or None
    etf_margin_rows = {code: (mp, mb, sp, sb) for m, d in mlast.items() for code, mp, mb, sp, sb in metfs[m].get(d, [])}

    replay_dates = [str(d) for d in dates[-REPLAY:]]
    latest = {
        "updated_at": status["collected_at"],     # 最後成功收集時間，不是匯出時間
        "status": status,
        "date": str(latest_date),
        "flow_date": str(dates[-1]),
        "dates": replay_dates,
        "market": {k: {**v, "turnover": round(v["turnover"], 1)} for k, v in market.items()},
        "insti": {k: round(v, 1) for k, v in insti_total.items()},
        "insti_official": _insti_official(amount),
        "insti_otc": {k: round(v, 1) for k, v in insti_otc.items()},
        "index": {code: {"date": str(rows[-1][0]), "c": _f(rows[-1][1]), "ch": _f(rows[-1][2]),
                         "p": _f(_pct(rows[-1][1], rows[-1][2])), "from": str(rows[-INDEX_DAYS:][0][0]),
                         "s": [_f(r[1]) for r in rows[-INDEX_DAYS:]]}
                  for code, rows in index_rows.items()},
        # 全市場日線未滿 52 週時 = 最早日線日期（高低點標示「區間」）；滿 52 週為 null
        "hl_from": str(db_first) if db_first > w52_start else None,
        "futures": futures,
        "futures_oi": futures_oi,
        "forecast": forecast,
        "margin": margin,
        "etfs": etf_block(etf_latest, etf_margin_rows),
        "groups": {
            "industry": group_flows(industries, daily, dates, REPLAY),
            "chain": group_flows(chains, daily, dates, REPLAY),
            "concept": group_flows(concepts, daily, dates, REPLAY),
        },
        "stocks": snapshot,
    }
    _write(SITE_DATA_DIR / "latest.json", latest)
    size = (SITE_DATA_DIR / "latest.json").stat().st_size / 1024
    print(f"  📌 還原事件 {n_ev} 筆（上櫃反推 {n_inferred} 筆）")
    if bad_all:
        print(f"⚠️  還原係數超出 {ADJ_MIN}～{ADJ_MAX}，未採用 {len(bad_all)} 筆：" +
              "、".join(f"{c} {d}（{f}）" for c, d, f in bad_all[:10]))
    if miss_all:
        print(f"⚠️  上市官方漲跌 0、收盤 ≠ 前收，但找不到除權息／減資事件 {len(miss_all)} 筆（維持「不比價」）：" +
              "、".join(f"{c} {d}" for c, d in miss_all[:10]))
    print(f"✅ 匯出完成：資料日 {latest_date}，個股 {len(prices)} 檔，"
          f"類股 {len(latest['groups']['industry'])}、產業鏈 {len(latest['groups']['chain'])}、"
          f"概念 {len(latest['groups']['concept'])}，台指期 {len(futures['d']) if futures else 0} 天，"
          f"latest.json {size:.0f} KB")
    if str(dates[-1]) != str(latest_date):
        print(f"⚠️  法人資料只到 {dates[-1]}，資金流以該日為準")
    seconds = time.monotonic() - t0
    print(f"⏱️  匯出耗時 {seconds:.1f} 秒")
    return seconds
