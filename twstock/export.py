"""
把資料庫內容匯出成靜態 JSON（site/data/），網站只讀這些檔案、不需要後端：

  latest.json        今日總覽：大盤統計、類股/概念股資金流（含回放用的每日座標）、每檔股票最新指標
  stocks/{代號}.json 個股：完整日線、法人買賣超、月營收、本益比
"""
import json
from collections import defaultdict
from datetime import datetime, timedelta

from . import db
from .analysis.flow import LONG, group_flows, load_concepts, streak
from .config import SITE_DATA_DIR

REPLAY = 20                    # 泡泡圖回放天數
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
            "code": code, **info, "concepts": concept_of.get(code, []),
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
        net_value = []
        for i, day in enumerate(d_):
            close = float(c[i]) if c[i] is not None else None
            net = (total[i] or 0) * close / YI if close else 0.0
            if day in window:
                daily.setdefault(code, {})[day] = {
                    "net": net, "turnover": (tv[i] or 0) / YI, "pct": _pct(c[i], ch[i])}
            net_value.append(net)

        if d_[-1] != latest_date or c[-1] is None:
            continue    # 今天沒有交易（停牌、下市）的股票不列入今日統計
        pct = _pct(c[-1], ch[-1])
        m = market[info["market"]]
        m["up" if (ch[-1] or 0) > 0 else "down" if (ch[-1] or 0) < 0 else "flat"] += 1
        m["turnover"] += (tv[-1] or 0) / YI
        # 法人指標以「有法人資料的最後一天」為準（法人資料比行情晚公布）
        k = max(i for i, day in enumerate(d_) if day <= dates[-1]) if d_[0] <= dates[-1] else None
        close = float(c[k]) if k is not None and c[k] is not None else 0.0
        net_value = net_value[:k + 1] if k is not None else []
        for key, arr in (("foreign", fn), ("trust", tn), ("dealer", dn)):
            insti_total[key] += ((arr[k] or 0) * close / YI) if k is not None else 0
        w52 = [(float(h[i]), float(l[i])) for i in range(len(d_))
               if d_[i] >= w52_start and h[i] is not None and l[i] is not None]
        snapshot[code] = {
            "n": info["name"], "m": info["market"], "i": info["industry"],
            "c": _f(c[-1]), "ch": _f(ch[-1]), "p": _f(pct),
            "v": round((v[-1] or 0) / 1000), "tv": _f((tv[-1] or 0) / YI),
            "n1": _f(net_value[-1]) if net_value else None,
            "n5": _f(sum(net_value[-5:])), "n20": _f(sum(net_value[-20:])),
            **({"f1": _f((fn[k] or 0) * close / YI), "t1": _f((tn[k] or 0) * close / YI),
                "d1": _f((dn[k] or 0) * close / YI)} if k is not None else {}),
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
        "groups": {
            "industry": group_flows(industries, daily, dates, REPLAY),
            "concept": group_flows(concepts, daily, dates, REPLAY),
        },
        "stocks": snapshot,
    }
    _write(SITE_DATA_DIR / "latest.json", latest)
    size = (SITE_DATA_DIR / "latest.json").stat().st_size / 1024
    print(f"✅ 匯出完成：資料日 {latest_date}，個股 {len(prices)} 檔，"
          f"類股 {len(latest['groups']['industry'])}、概念 {len(latest['groups']['concept'])}，"
          f"latest.json {size:.0f} KB")
    if str(dates[-1]) != str(latest_date):
        print(f"⚠️  法人資料只到 {dates[-1]}，資金流以該日為準")
