"""
把資料庫內容匯出成靜態 JSON（site/data/），網站只讀這些檔案、不需要後端：

  latest.json        今日總覽：大盤統計、台指期日 K、類股/產業鏈/概念股資金流（含回放用的每日座標）、
                     每檔股票最新指標
  stocks/{代號}.json 個股：完整日線、法人買賣超、月營收、本益比、所屬產業鏈
"""
import json
from collections import defaultdict
from datetime import date, datetime, timedelta

from . import db
from .analysis.flow import LONG, group_flows, load_concepts, streak
from .analysis.forecast import build_forecast, load_oi
from .config import SITE_DATA_DIR

REPLAY = 20                    # 泡泡圖回放天數
FUTURES_DAYS = 500             # 首頁台指期日 K 匯出天數
OI_DAYS = 120                  # 首頁法人未平倉走勢天數
WINDOW = REPLAY + LONG - 1     # 計算回放第一天的 20 日均線所需天數
YI = 1e8                       # 億


def _f(v, nd=2):
    return None if v is None else round(float(v), nd)


def _write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    # separators 去掉空白，檔案小約 15%
    path.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def _pct(close, change):
    if close is None or change is None or close == change:
        return None
    return float(change) / (float(close) - float(change)) * 100


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


def export_all():
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
    conn.close()

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
    w52_start = latest_date - timedelta(days=365)

    for code, rows in prices.items():
        info = stocks.get(code)
        if not info:
            continue
        d_, o, h, l, c, v, tv, ch, fn, tn, dn, total = zip(*rows)

        _write(SITE_DATA_DIR / "stocks" / f"{code}.json", {
            "code": code, **info, "concepts": concept_of.get(code, []), "chains": chain_of.get(code, []),
            "prices": {"d": [str(x) for x in d_], "o": [_f(x) for x in o], "h": [_f(x) for x in h],
                       "l": [_f(x) for x in l], "c": [_f(x) for x in c],
                       "v": [round(x / 1000) if x else 0 for x in v]},           # 張
            "insti": {"f": [round(x / 1000) if x is not None else None for x in fn],   # 張
                      "t": [round(x / 1000) if x is not None else None for x in tn],
                      "dl": [round(x / 1000) if x is not None else None for x in dn]},
            "revenue": revenue.get(code, [])[-24:],
            "fund": dict(zip(("pe", "pb", "dy"), map(_f, fund[code][:3])), date=str(fund[code][3]))
                    if code in fund else None,
        })

        # 板塊計算用的近 WINDOW 天
        net_value, f_value, t_value, d_value = [], [], [], []
        for i, day in enumerate(d_):
            close = float(c[i]) if c[i] is not None else None
            net = (total[i] or 0) * close / YI if close else 0.0
            if day in window:
                daily.setdefault(code, {})[day] = {
                    "net": net, "turnover": (tv[i] or 0) / YI, "pct": _pct(c[i], ch[i])}
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
        pct = None if no_trade else _pct(c[-1], ch[-1])
        m = market[info["market"]]
        if not no_trade:                    # 無成交不計入漲跌家數
            m["up" if (ch[-1] or 0) > 0 else "down" if (ch[-1] or 0) < 0 else "flat"] += 1
        m["turnover"] += (tv[-1] or 0) / YI
        # 法人指標以「有法人資料的最後一天」為準（法人資料比行情晚公布）
        k = max(i for i, day in enumerate(d_) if day <= dates[-1]) if d_[0] <= dates[-1] else None
        n = k + 1 if k is not None else 0
        net_value, f_value, t_value, d_value = net_value[:n], f_value[:n], t_value[:n], d_value[:n]
        if n:
            insti_total["foreign"] += f_value[-1]
            insti_total["trust"] += t_value[-1]
            insti_total["dealer"] += d_value[-1]
        w52 = [(float(h[i]), float(l[i])) for i in range(len(d_))
               if d_[i] >= w52_start and h[i] is not None and l[i] is not None]
        snapshot[code] = {
            "n": info["name"], "m": info["market"], "i": info["industry"],
            # 今天無成交時 c 是最後成交日的收盤，nt 記該日期
            "c": _f(c[j]), "ch": None if no_trade else _f(ch[-1]), "p": _f(pct),
            **({"nt": str(d_[j])} if no_trade else {}),
            "v": round((v[-1] or 0) / 1000), "tv": _f((tv[-1] or 0) / YI),
            "n1": _f(net_value[-1]) if net_value else None,
            "n5": _f(sum(net_value[-5:])), "n20": _f(sum(net_value[-20:])),
            # 外資 f、投信 t、自營 d 的 1 日 / 5 日買賣超（億）
            **({"f1": _f(f_value[-1]), "t1": _f(t_value[-1]), "d1": _f(d_value[-1]),
                "f5": _f(sum(f_value[-5:])), "t5": _f(sum(t_value[-5:])), "d5": _f(sum(d_value[-5:])),
                "fs": streak(f_value[-30:]), "ts": streak(t_value[-30:])} if n else {}),
            "s": streak(net_value[-30:]),
            "h52": max(x[0] for x in w52) if w52 else None,
            "l52": min(x[1] for x in w52) if w52 else None,
            **({"pe": _f(fund[code][0]), "pb": _f(fund[code][1]), "dy": _f(fund[code][2])}
               if code in fund else {}),
        }

    industries = defaultdict(list)
    for code in snapshot:
        industries[snapshot[code]["i"]].append(code)

    replay_dates = [str(d) for d in dates[-REPLAY:]]
    latest = {
        "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "date": str(latest_date),
        "flow_date": str(dates[-1]),
        "dates": replay_dates,
        "market": {k: {**v, "turnover": round(v["turnover"], 1)} for k, v in market.items()},
        "insti": {k: round(v, 1) for k, v in insti_total.items()},
        "futures": futures,
        "futures_oi": futures_oi,
        "forecast": forecast,
        "groups": {
            "industry": group_flows(industries, daily, dates, REPLAY),
            "chain": group_flows(chains, daily, dates, REPLAY),
            "concept": group_flows(concepts, daily, dates, REPLAY),
        },
        "stocks": snapshot,
    }
    _write(SITE_DATA_DIR / "latest.json", latest)
    size = (SITE_DATA_DIR / "latest.json").stat().st_size / 1024
    print(f"✅ 匯出完成：資料日 {latest_date}，個股 {len(prices)} 檔，"
          f"類股 {len(latest['groups']['industry'])}、產業鏈 {len(latest['groups']['chain'])}、"
          f"概念 {len(latest['groups']['concept'])}，台指期 {len(futures['d']) if futures else 0} 天，"
          f"latest.json {size:.0f} KB")
    if str(dates[-1]) != str(latest_date):
        print(f"⚠️  法人資料只到 {dates[-1]}，資金流以該日為準")
