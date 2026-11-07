"""
把資料庫內容匯出成靜態 JSON（site/data/），網站只讀這些檔案、不需要後端：

  latest.json        今日總覽：大盤統計、台指期日 K、類股/產業鏈/概念股資金流（含回放用的每日座標）、
                     每檔股票最新指標、融資融券（margin）、ETF（etfs，與股票完全分開）、
                     已支援持股的主動 ETF（holdings）、市場寬度（breadth）
  screen.json        條件選股與排行擴充：每檔股票的價量、營收、融資融券欄位（欄式，和 latest.json stocks 合併使用）
  stocks/{代號}.json 個股：完整日線、法人買賣超、月營收、本益比、所屬產業鏈、最新融資融券、主動 ETF 持有（active）、
                     融資融券序列（mg）、投信買超中的主動 ETF（act）、季報（fin，第 10 輪）
  etfs/{代號}.json   主動 ETF 持股：近 HOLD_DAYS 個持股日的張數與權重、最新一天的增減
"""
import json
import os
import statistics
import time
from bisect import bisect_left
from collections import Counter, defaultdict
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from . import db
from .analysis.flow import LONG, group_flows, load_concepts, streak
from .analysis.forecast import build_forecast, load_oi
from .config import SITE_DATA_DIR, tw_now
from .health import HOLDINGS, build_status, fin_quarter_for, prev_quarter

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
HOLD_DAYS = 60                 # ETF 持股 JSON 的持股日數
ACTIVE_TOP = 20                # 主動 ETF 彙總排行（第 7 輪 F7-2）各區塊的列數
BREADTH_DAYS = 60              # 市場寬度走勢天數
NH_DAYS = (240, 120, 60, 20)    # C3：創 N 日新高／新低的 N（由大到小，取符合的最大 N）
CONV_MIN = 0.1                  # 融資融券換算：|k − 1| ≥ 10% 才視為官方已換算
SCREEN_KEYS = ("a20", "vr", "r5", "r20", "r60", "rs20", "rs60", "b20", "b60", "nh", "nl",
               "rm", "ry", "rc", "rh", "r3", "cap", "mb", "m1", "m5", "sb", "s1", "s5", "sr", "mu", "mnt", "pbp",
               "eq", "ey", "e4", "gm", "gmy", "fq", "eh", "lb", "l1", "l5", "lp", "mc", "to")
VAL_DAYS = 242                  # F9-4：估值一年位置的窗口 = 最近 242 個有官方本益比資料的交易日
VAL_MIN = 120                   # 個股窗口內有效天數少於此值不算位置（新上市）
VAL_SPARK = 60                  # 今日頁本益比中位數迷你圖天數
FIN_QUARTERS = 8                # 第 10 輪 B5：個股季報卡的季數
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


def amount_by_market(rows):
    """F9-1：rows = [(日期, 市場, 單位, 買賣差額)] → {"TWSE": {日期: {單位: 差額}}, "TPEx": {…}}；insti_official 只用 TWSE。"""
    out = {"TWSE": defaultdict(dict), "TPEx": defaultdict(dict)}
    for d, m, unit, net in rows:
        out[m][d][unit] = net
    return out


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


# ─── 估值的一年位置（第 9 輪 F9-4，A10＋B7）────────────────────
def position(series, today):
    """位置 % = series 中 ≤ today 的筆數 ÷ 筆數 × 100（series 含 today 當天）；series 空或 today 為 None → None。"""
    if today is None or not series:
        return None
    return sum(v <= today for v in series) / len(series) * 100


def market_valuation(rows, days):
    """
    A10：rows = [(日期, 市場, 本益比, 淨值比, 殖利率)]（float 或 None）；days = 窗口日期（舊到新）。
    每天、分市場取中位數：本益比、淨值比只計入 > 0，殖利率計入非 null（含 0）。
    回傳 {市場: {d, from, days, n, pe, pb, dy, s, sf}}；pe／pb／dy = {v 中位數, p 位置 %（1 位）, lo, hi}；
    s = 最近 VAL_SPARK 天本益比中位數，sf = s 的第一天。
    """
    per = defaultdict(lambda: defaultdict(lambda: ([], [], [])))
    window = set(days)
    for d, m, pe, pb, dy in rows:
        if d not in window:
            continue
        b = per[m][d]
        if pe is not None and pe > 0:
            b[0].append(pe)
        if pb is not None and pb > 0:
            b[1].append(pb)
        if dy is not None:
            b[2].append(dy)
    out = {}
    for m, by_day in per.items():
        ds = [d for d in days if by_day.get(d) and by_day[d][0]]
        if not ds:
            continue
        r = {"d": str(ds[-1]), "from": str(ds[0]), "days": len(ds), "n": len(by_day[ds[-1]][0])}
        for i, k in enumerate(("pe", "pb", "dy")):
            s = [statistics.median(by_day[d][i]) for d in ds if by_day[d][i]]
            v = statistics.median(by_day[ds[-1]][i]) if by_day[ds[-1]][i] else None
            r[k] = None if v is None else {"v": round(v, 2), "p": round(position(s, v), 1), "lo": round(min(s), 2), "hi": round(max(s), 2)}
        r["s"], r["sf"] = [round(statistics.median(by_day[d][0]), 2) for d in ds[-VAL_SPARK:]], str(ds[-VAL_SPARK:][0])
        out[m] = r
    return out


def market_wpe(rows, days):
    """
    第 12 輪 A10-延伸：市值加權本益比 = Σ 市值 ÷ Σ（市值 ÷ 本益比），只計本益比 > 0、有市值（收盤 × 目前股數）的股票。
    rows = [(日期, 市場, 代號, 本益比, 市值)]（float 或 None）；days = 窗口日期（舊到新，同 market_valuation）。
    回傳 {市場: {v, p 位置 %（1 位）, lo, hi, cov 計入市值占比 %（1 位）, t: [最大市值代號, 占計入市值 %（1 位）]}}；某市場沒有資料 → 不輸出。
    """
    per = defaultdict(lambda: defaultdict(lambda: [0.0, 0.0, 0.0, None]))    # 全部市值、計入市值、Σ 市值÷本益比、(最大市值, 代號)
    window = set(days)
    for d, m, code, pe, cap in rows:
        if d not in window or not cap or cap <= 0:
            continue
        b = per[m][d]
        b[0] += cap
        if pe is not None and pe > 0:
            b[1] += cap
            b[2] += cap / pe
            if b[3] is None or cap > b[3][0]:
                b[3] = (cap, code)
    out = {}
    for m, by_day in per.items():
        ds = [d for d in days if by_day.get(d) and by_day[d][2] > 0]
        if not ds:
            continue
        s = [by_day[d][1] / by_day[d][2] for d in ds]
        b = by_day[ds[-1]]
        out[m] = {"v": round(s[-1], 2), "p": round(position(s, s[-1]), 1), "lo": round(min(s), 2), "hi": round(max(s), 2),
                  "cov": round(b[1] / b[0] * 100, 1), "t": [b[3][1], round(b[3][0] / b[1] * 100, 1)]}
    return out


def stock_valuation(series, today):
    """
    B7：series = {"pe"|"pb"|"dy": [窗口內 > 0 的值]}；today = {"pe", "pb", "dy": 窗口最後一天的值（可為 None）}。
    今天值 None 或 ≤ 0（虧損、無股利）或有效天數 < VAL_MIN → 不輸出該欄。回傳 {欄: [位置 %（整數）, lo, hi]}；全部不輸出 → None。
    """
    out = {}
    for k in ("pe", "pb", "dy"):
        s, v = series.get(k, []), today.get(k)
        if v is None or v <= 0 or len(s) < VAL_MIN:
            continue
        out[k] = [round(position(s, v)), round(min(s), 2), round(max(s), 2)]
    return out or None


def _load_valuation(cur, shares=None):
    """
    讀窗口內的 stock_fundamentals（約 47 萬列）→ (市場估值, {代號: 個股估值}, 窗口最後一天)。
    第 12 輪：同一個查詢多讀當天收盤，乘 shares（{代號: 目前股數}）得市值，市場估值加 wpe（市值加權本益比）。
    """
    days = [r[0] for r in cur.execute(f"SELECT DISTINCT TOP {VAL_DAYS} trade_date FROM stock_fundamentals ORDER BY trade_date DESC")][::-1]
    if not days:
        return None, {}, None
    f = lambda x: None if x is None else float(x)
    mrows, wrows, series, today = [], [], defaultdict(lambda: {"pe": [], "pb": [], "dy": []}), {}
    shares = shares or {}
    for d, m, code, pe, pb, dy, close in cur.execute("""
        SELECT f.trade_date, s.market_type, s.stock_code, f.pe_ratio, f.pb_ratio, f.dividend_yield, p.close_price
        FROM stock_fundamentals f JOIN stocks s ON s.stock_id = f.stock_id
        LEFT JOIN daily_prices p ON p.stock_id = f.stock_id AND p.trade_date = f.trade_date
        WHERE f.trade_date BETWEEN ? AND ?""", days[0], days[-1]):
        pe, pb, dy = f(pe), f(pb), f(dy)
        mrows.append((d, m, pe, pb, dy))
        if close is not None and shares.get(code):
            wrows.append((d, m, code, pe, float(close) * shares[code]))
        for k, v in (("pe", pe), ("pb", pb), ("dy", dy)):
            if v is not None and v > 0:
                series[code][k].append(v)
        if d == days[-1]:
            today[code] = {"pe": pe, "pb": pb, "dy": dy}
    mv = market_valuation(mrows, days)
    for m, w in market_wpe(wrows, days).items():          # 第 12 輪
        if m in mv:
            mv[m]["wpe"] = w
    return mv or None, {c: stock_valuation(series[c], today.get(c, {})) for c in series}, days[-1]


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


def stock_margin(rows: dict, mdate, d5, conv=()):
    """
    個股 JSON 的 margin。rows：{日期: (融資前日, 融資餘額, 融資限額, 融券前日, 融券餘額, 註記)}；
    mdate：該市場最新融資融券日；d5：往前第 5 個融資融券日（不足 6 天為 None）。該股當天沒有列 → None（無信用交易）。
    conv：margin_conv 的換算紀錄；m5 以換算後的 5 日前餘額計算（第 9 輪 P23，與 screen_margin 相同）。
    """
    r = rows.get(mdate)
    if r is None:
        return None
    mp, mb, ml, sp, sb, nt = r
    old = rows.get(d5) if d5 else None
    out = {"d": str(mdate), "mb": mb, "m1": mb - mp, "m5": round(mb - old[1] * conv_k(conv, d5)) if old else None,
           "sb": sb, "s1": sb - sp, "sr": short_ratio(sb, mb), "mu": usage(mb, ml)}
    if nt:
        out["nt"] = nt
    return out


def margin_conv(rows, ev):
    """
    融資融券的官方換算（面額變更、減資等）。rows：{日期: (融資前日, 融資餘額, 限額, 融券前日, 融券餘額, 註記)}（該股全部日期）；
    ev：_price_events 的事件。股本事件（CAP_TYPES、參考價變動 ≥ 10%）生效後第一個融資融券日 d：
    k = d 的融資前日餘額 ÷ 前一個融資融券日的融資餘額（融資為 0 改用融券）；|k − 1| ≥ CONV_MIN 才算換算。
    回傳 [{"d", "k"（4 位）, "t"}]（舊到新）；d 之前的餘額乘上 k 即與 d 之後同一單位。
    """
    ds, out = sorted(rows), []
    for e in ev:
        if e["t"] not in CAP_TYPES or abs(e["r"] / e["p"] - 1) < 0.1:
            continue
        j = next((i for i, d in enumerate(ds) if str(d) >= e["d"]), None)
        if not j:                                   # 找不到，或事件在第一筆融資融券之前
            continue
        cur, prev = rows[ds[j]], rows[ds[j - 1]]
        k = cur[0] / prev[1] if prev[1] else cur[3] / prev[4] if prev[4] else None
        if k is not None and abs(k - 1) >= CONV_MIN:
            out.append({"d": str(ds[j]), "k": round(k, 4), "t": e["t"]})
    return out


def conv_k(conv, day):
    """day 的餘額換算到最新單位要乘上的係數 = day 之後所有換算的 k 相乘。"""
    k = 1.0
    for c in conv:
        if c["d"] > str(day):
            k *= c["k"]
    return k


def screen_margin(rows, mdate, d5, conv, market):
    """C3／F8-3 的融資融券欄位（張、%）；5 日增減以換算後的 5 日前餘額計算。該市場沒有資料或該股不在清單 → 全部 None。"""
    r = stock_margin(rows, mdate, d5, conv) if mdate else None
    if r is None:
        return dict.fromkeys(("mb", "m1", "m5", "sb", "s1", "s5", "sr", "mu", "mnt"))
    old = rows.get(d5) if d5 else None
    k = conv_k(conv, d5) if old else 1.0
    return {"mb": r["mb"], "m1": r["m1"], "m5": r["m5"],
            "sb": r["sb"], "s1": r["s1"], "s5": round(r["sb"] - old[4] * k) if old else None,
            "sr": r["sr"], "mu": r["mu"], "mnt": (r.get("nt") or None) if market == "TWSE" else None}


def margin_series(d_, rows, conv, srows=None):
    """
    個股 JSON 的 mg：與 prices.d 對齊的官方原始餘額（張），沒有資料的日期 null；k = 換算紀錄（沒有就不放）。該股沒有任何融資融券列 → None。
    第 11 輪 B14：srows（借券 {日期: (前日, 餘額, 限額, 備註)}，股）有資料時加 lb = 借券賣出餘額（張）；只有借券、沒有融資融券的股票不畫圖。
    """
    if not rows:
        return None
    mg = {"mb": [rows[d][1] if d in rows else None for d in d_], "sb": [rows[d][4] if d in rows else None for d in d_]}
    if srows:
        mg["lb"] = [lots(srows[d][1]) if d in srows else None for d in d_]
    if conv:
        mg["k"] = conv
    return mg


# ─── 市值、週轉率（第 12 輪 B11；目前股數）────────────────────
def cap_turnover(close, volume, shares):
    """(市值 億元（1 位）, 週轉率 % = 成交股數 ÷ 股數 × 100（2 位）)；沒有股數 → (None, None)；沒有收盤 → 市值 None；成交量 None → 週轉率 None。"""
    if not shares:
        return None, None
    return (None if close is None else round(float(close) * shares / YI, 1),
            None if volume is None else round(volume / shares * 100, 2))


# ─── 借券賣出（第 11 輪 B14；資料庫存股，匯出一律換成張）────────────
def lots(shares):
    """股 → 張（四捨五入到整數，half-up；None 照傳）。"""
    return None if shares is None else int((shares + 500) // 1000) if shares >= 0 else -int((-shares + 500) // 1000)


def stock_sbl(rows: dict, sdate, d5, shares, short_lots, conv=()):
    """
    個股 JSON 的 sbl。rows：{日期: (前日餘額, 當日餘額, 限額, 備註)}（股）；sdate：該市場最新借券日；d5：往前第 5 個借券日。
    該股當天沒有列 → None。lb 餘額、l1／l5 增減（張；5 日前餘額依融資融券的官方換算 k 調整）；
    lp 占股本 %（2 位；shares 為 None 或 0 不輸出）；lx = 借券 ÷ 融券（1 位；融券 0 或沒有不輸出）。
    """
    r = rows.get(sdate) if sdate else None
    if r is None:
        return None
    prev, bal, _, nt = r
    old = rows.get(d5) if d5 else None
    out = {"d": str(sdate), "lb": lots(bal), "l1": lots(bal - prev),
           "l5": lots(bal - old[1] * conv_k(conv, d5)) if old else None}
    if shares:
        out["lp"] = round(bal / shares * 100, 2)
    if short_lots:
        out["lx"] = round(bal / (short_lots * 1000), 1)
    if nt:
        out["nt"] = nt
    return out


def market_sbl(sdates, rows_by_market):
    """latest.json 的 sbl.{市場}：股票（不含 ETF）借券賣出餘額合計與 1 日增減（張）。rows_by_market：{日期: [(前日, 餘額)]}。"""
    if not sdates:
        return None
    d = sdates[-1]
    R = rows_by_market.get(d, [])
    bal, prev = sum(r[1] for r in R), sum(r[0] for r in R)
    return {"d": str(d), "lb": lots(bal), "l1": lots(bal - prev), "n": len(R)}


def _load_etf_sbl(cur):
    """第 12 輪：ETF 借券，各市場最新借券日 → ({市場: 日期}, {代號: (前日餘額, 餘額)}（股）)。"""
    by_m = defaultdict(dict)
    for code, m, d, prev, bal in cur.execute("""
        SELECT e.etf_code, e.market_type, x.trade_date, x.sbl_prev, x.sbl_balance
        FROM etf_sbl x JOIN etfs e ON e.etf_id = x.etf_id
        WHERE x.trade_date = (SELECT MAX(y.trade_date) FROM etf_sbl y JOIN etfs z ON z.etf_id = y.etf_id
                              WHERE z.market_type = e.market_type)"""):
        by_m[m][code] = (d, prev, bal)
    dates = {m: next(iter(v.values()))[0] for m, v in by_m.items()}
    return dates, {c: (p, b) for v in by_m.values() for c, (_, p, b) in v.items()}, by_m


def _load_sbl(cur):
    """(各市場借券日期（舊到新，最近 6 天）, 各市場最新日的 [(前日, 餘額)], 個股 {代號: {日期: (前日, 餘額, 限額, 備註)}}（完整歷史）)。"""
    per_stock, by_m = defaultdict(dict), defaultdict(lambda: defaultdict(list))
    for code, m, d, prev, bal, lim, nt in cur.execute("""
        SELECT s.stock_code, s.market_type, x.trade_date, x.sbl_prev, x.sbl_balance, x.sbl_limit, x.note
        FROM sbl_trades x JOIN stocks s ON s.stock_id = x.stock_id"""):
        per_stock[code][d] = (prev, bal, lim, nt)
        by_m[m][d].append((prev, bal))
    sdates = {m: sorted(ds)[-6:] for m, ds in by_m.items()}
    return sdates, {m: {sdates[m][-1]: by_m[m][sdates[m][-1]]} for m in sdates}, per_stock


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
    """回傳 (各市場日期, 官方合計, 股票列, ETF 列, 個股 rows（完整歷史）)；沒有融資融券資料時日期為空。"""
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
        FROM margin_trades x JOIN stocks s ON s.stock_id = x.stock_id"""):     # 個股完整歷史（融資融券圖、換算）
        if d >= mdates[0]:                                                  # 市場彙總仍只用最近 25 天
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


def etf_block(latest, margin_rows, sbl_rows=None):
    """
    latest.json 的 etfs。margin_rows：{代號: (融資前日, 融資餘額, 融券前日, 融券餘額)}（該市場最新融資融券日）。
    第 12 輪：sbl_rows：{代號: (借券前日餘額, 借券餘額)}（股，該市場最新借券日）→ lb、l1（張）。
    """
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
            sl = (sbl_rows or {}).get(code)
            if sl:
                r.update(lb=lots(sl[1]), l1=lots(sl[1] - sl[0]))
            rows[code] = r
    return {"dates": {m: str(d) for m, (d, _) in latest.items()}, "rows": rows}


def _load_holdings(cur):
    """{ETF 代號: (持股日 [舊到新], {持股日: 彙總列}, {持股日: {(類別, 代號): (名稱, 股數, 權重)}})}，各取最近 HOLD_DAYS 個持股日。"""
    summary = defaultdict(dict)
    for code, d, *v in cur.execute("""
        SELECT e.etf_code, s.hold_date, s.nav, s.nav_unit, s.n_stocks, s.stock_weight, s.futures_lots, s.futures_amount, s.units
        FROM etf_holding_summary s JOIN etfs e ON e.etf_id = s.etf_id ORDER BY s.hold_date"""):
        summary[code][d] = v
    if not summary:
        return {}
    since = min(sorted(v)[-HOLD_DAYS:][0] for v in summary.values())
    held = defaultdict(lambda: defaultdict(dict))
    for code, d, kind, c, name, shares, w in cur.execute("""
        SELECT e.etf_code, h.hold_date, h.asset_type, h.code, h.name, h.shares, h.weight
        FROM etf_holdings h JOIN etfs e ON e.etf_id = h.etf_id WHERE h.hold_date >= ?""", since):
        held[code][d][(kind, c)] = (name, shares, w)
    return {code: (sorted(v)[-HOLD_DAYS:], v, held[code]) for code, v in summary.items() if code in HOLDINGS}


def holding_table(dates, held, tw):
    """
    ETF 持股頁的列（最新持股日）。dates：持股日（舊到新）；held：{持股日: {(類別, 代號): (名稱, 股數, 權重)}}；
    tw：台股代號集合（張 = 股 ÷ 1000、可點進個股頁；其他如海外股票單位為股）。
    回傳 (rows, out)：rows 每列 {c, n, tw, s: [各持股日數量，未持有 null], w: [權重], l, pw, d1, w1, d5, new}；
    out：前一持股日有、最新一天沒有（出清）。1 日、5 日以「前 1、前 5 個有資料的持股日」為基準。
    """
    last, prev = dates[-1], dates[-2] if len(dates) > 1 else None
    d5 = dates[-6] if len(dates) > 5 else None
    names = {}
    for d in dates:
        for (kind, c), (name, _, _) in held[d].items():
            if kind == "ST":
                names[c] = name
    qty = lambda c, d: None if d is None or ("ST", c) not in held[d] else (
        round(held[d][("ST", c)][1] / 1000) if c in tw else held[d][("ST", c)][1])
    wt = lambda c, d: None if d is None or ("ST", c) not in held[d] else _f(held[d][("ST", c)][2])
    rows, out = [], []
    for c, name in names.items():
        now, before = qty(c, last), qty(c, prev)
        if now is None:
            if before is not None:
                out.append({"c": c, "n": name, "tw": int(c in tw), "l": before, "pw": wt(c, prev)})
            continue
        r = {"c": c, "n": name, "tw": int(c in tw), "s": [qty(c, d) for d in dates], "w": [wt(c, d) for d in dates],
             "l": now, "pw": wt(c, last), "d1": now - (before or 0) if prev else None,
             "w1": _f(wt(c, last) - (wt(c, prev) or 0)) if prev else None,
             "d5": now - (qty(c, d5) or 0) if d5 else None}
        if prev and before is None:
            r["new"] = 1
        rows.append(r)
    rows.sort(key=lambda r: -(r["pw"] or 0))
    return rows, out


def holding_export(code, dates, summary, held, tw, name, market):
    """etfs/{代號}.json。金額單位：億元；nu 每單位淨值（元）；sw 股票權重合計（%）；fl 期貨口數。"""
    nav, nu, n, sw, fl, fa = summary[dates[-1]][:6]
    rows, out = holding_table(dates, held, tw)
    f = HOLDINGS[code]
    return {"code": code, "n": name, "m": market, "fund": f.fund, "delay": f.delay, "trust": f.trust, "dates": [str(d) for d in dates],
            "sum": {"d": str(dates[-1]), "nav": _f(float(nav) / YI), "nu": _f(nu), "n": n, "sw": _f(sw),
                    "fl": fl, "fa": _f(float(fa) / YI), **({"u1": u} if (u := unit_change(summary, dates)) is not None else {})},
            "rows": rows, "out": out}


def unit_change(summary, dates):
    """P21：單位數 1 日變化（%）= 最新持股日 ÷ 前一持股日 − 1；只有一個持股日、任一天沒有單位數或為 0 → None。"""
    if len(dates) < 2:
        return None
    a, b = (summary[d][6] if d in summary and len(summary[d]) > 6 else None for d in (dates[-1], dates[-2]))
    return round((a / b - 1) * 100, 2) if a and b else None


def active_trust(holdings, tw, flow_date):
    """B16：{股票代號: 國內主動 ETF 在法人資料日的張數增減合計}（含新進、出清；合計 0 不列）。
    只取 delay 0、最新持股日 = flow_date、且有前一持股日的 ETF；跨境 ETF（delay 1）不計入。"""
    out = defaultdict(int)
    for code, (dates, _, held) in holdings.items():
        if HOLDINGS[code].delay or dates[-1] != flow_date or len(dates) < 2:
            continue
        last, prev = dates[-1], dates[-2]
        lots = lambda c, d: round(held[d][("ST", c)][1] / 1000) if ("ST", c) in held[d] else 0
        for c in {c for d in (last, prev) for (kind, c) in held[d] if kind == "ST" and c in tw}:
            out[c] += lots(c, last) - lots(c, prev)
    return {c: v for c, v in out.items() if v}


def trust_share(t, e):
    """B16：主動 ETF 占投信買賣超的 %（四捨五入整數）；同向且 |e| ≤ |t| 才有，其他（投信 0、反向、超過）→ None。"""
    return round(e / t * 100) if t and e and (t > 0) == (e > 0) and abs(e) <= abs(t) else None


def stock_active(holdings, tw):
    """{股票代號: [主動 ETF 持有]}：各 ETF 最新持股日有持有的台股；張、權重（%）、1 日／5 日張數增減。"""
    out = defaultdict(list)
    for code, (dates, _, held) in sorted(holdings.items()):
        for r in holding_table(dates, held, tw)[0]:
            if r["tw"]:
                out[r["c"]].append({"e": code, "d": str(dates[-1]), "l": r["l"], "w": r["pw"], "d1": r["d1"], "d5": r["d5"],
                                    **({"new": 1} if r.get("new") else {})})
    return out


def active_rank(holdings, tw, close):
    """
    latest.json 的 active_rank（第 7 輪 F7-2）：已收持股的主動 ETF 合計，只算台股。
    每檔用自己的最新持股日；同一 delay 的 ETF 中最新持股日落後的（當天還沒收到）不列入，放進 stale。
    張數與 holding_table 相同（股 ÷ 1000 四捨五入）；估算金額 a、市值 v（億）= 張 × 1000 × 該 ETF 持股日收盤
    （無成交用最近收盤，close 回傳 None 的股票不進買賣超排行）。只有一個持股日的 ETF 只計入 held。
    回傳 {etfs, stale: [{c, t, d}], buy, sell: [{c, n, a, l1, l5, e: [{e, d1, new|out}]}], held: [{c, n, k, l, v, e: [{e, w}]}]}。
    """
    newest = {}
    for code, (dates, _, _) in holdings.items():
        k = HOLDINGS[code].delay
        newest[k] = max(newest.get(k, dates[-1]), dates[-1])
    etfs, stale, names = [], [], {}
    flow = defaultdict(lambda: {"a": 0.0, "l1": 0, "l5": None, "e": [], "px": True})
    held_by = defaultdict(lambda: {"k": 0, "l": 0, "v": 0.0, "e": []})
    for code, (dates, _, held) in sorted(holdings.items()):
        last = dates[-1]
        info = {"c": code, "t": HOLDINGS[code].trust, "d": str(last)}
        if last != newest[HOLDINGS[code].delay]:
            stale.append(info)
            continue
        etfs.append(info)
        prev, d5 = dates[-2] if len(dates) > 1 else None, dates[-6] if len(dates) > 5 else None
        lots = lambda c, d: round(held[d][("ST", c)][1] / 1000) if d and ("ST", c) in held[d] else 0
        codes = {c for d in (last, prev) if d for (kind, c) in held[d] if kind == "ST" and c in tw}
        for c in codes:
            names.setdefault(c, (held[last].get(("ST", c)) or held[prev][("ST", c)])[0])
            now, px = lots(c, last), close(c, last)
            if now:
                h = held_by[c]
                h["k"] += 1
                h["l"] += now
                h["v"] += now * 1000 * px / YI if px else 0
                h["e"].append({"e": code, "w": _f(held[last][("ST", c)][2])})
            if d5:                                              # 5 日：當天沒變動的 ETF 也要算（設計規則 5）
                flow[c]["l5"] = (flow[c]["l5"] or 0) + now - lots(c, d5)
            if not prev or now == lots(c, prev):
                continue
            before, f = lots(c, prev), flow[c]
            d1 = now - before
            f["l1"] += d1
            if px:
                f["a"] += d1 * 1000 * px / YI
            else:
                f["px"] = False
            f["e"].append({"e": code, "d1": d1, **({"new": 1} if not before else {"out": 1} if not now else {})})
    out = lambda c, f: {"c": c, "n": names[c], "a": _f(f["a"]), "l1": f["l1"], "l5": f["l5"], "e": f["e"]}
    ok = [(c, f) for c, f in flow.items() if f["px"]]          # 排序、過濾用未四捨五入的金額（小額加減碼不會變成 0 而消失）
    buy = [out(c, f) for c, f in sorted((x for x in ok if x[1]["a"] > 0), key=lambda x: (-x[1]["a"], x[0]))]
    sell = [out(c, f) for c, f in sorted((x for x in ok if x[1]["a"] < 0), key=lambda x: (x[1]["a"], x[0]))]
    held_rows = [{"c": c, "n": names[c], "k": h["k"], "l": h["l"], "v": _f(h["v"]), "e": h["e"]} for c, h in held_by.items()]
    held_rows.sort(key=lambda r: (-r["k"], -r["v"], r["c"]))
    return {"etfs": etfs, "stale": stale, "buy": buy[:ACTIVE_TOP], "sell": sell[:ACTIVE_TOP], "held": held_rows[:ACTIVE_TOP]}


def breadth_calc(series, days, turnover):
    """
    自算市場寬度。series：{市場: [每檔股票 {日期: 還原收盤}]}（只含股票）；days：交易日（舊到新，最後 BREADTH_DAYS 天輸出）；
    turnover：{市場: {日期: 成交額（億）}}。分母 = 當天有收盤、且之前（含當天）至少有 20／60 個收盤的股票。
    回傳 {市場: {d, ma20, ma60（%）, n20, n60（分母）, hi, lo（20 日新高／新低家數）, vr（成交額 ÷ 前 20 日平均）, s20（MA20 比例走勢）, from}}。
    20 日新高／新低：收盤高於（低於）前 20 個收盤的最高（最低）。
    """
    out_days = days[-BREADTH_DAYS:]
    pos = {d: i for i, d in enumerate(out_days)}
    out = {}
    for m, stocks in series.items():
        cnt = {k: [0] * len(out_days) for k in ("a20", "n20", "a60", "n60", "hi", "lo")}
        for closes in stocks:
            ds = sorted(closes)
            px = [closes[d] for d in ds]
            acc = [0.0]
            for x in px:
                acc.append(acc[-1] + x)
            for j, d in enumerate(ds):
                i = pos.get(d)
                if i is None:
                    continue
                for n, a, k in ((20, "a20", "n20"), (60, "a60", "n60")):
                    if j >= n - 1:
                        cnt[k][i] += 1
                        cnt[a][i] += px[j] > (acc[j + 1] - acc[j + 1 - n]) / n
                if j >= 20:
                    window = px[j - 20:j]
                    cnt["hi"][i] += px[j] > max(window)
                    cnt["lo"][i] += px[j] < min(window)
        pct = lambda a, n: round(a / n * 100, 1) if n else None
        tv = [turnover[m].get(d) for d in days]
        prior = tv[-21:-1]
        out[m] = {"d": str(out_days[-1]), "ma20": pct(cnt["a20"][-1], cnt["n20"][-1]), "ma60": pct(cnt["a60"][-1], cnt["n60"][-1]),
                  "n20": cnt["n20"][-1], "n60": cnt["n60"][-1], "hi": cnt["hi"][-1], "lo": cnt["lo"][-1],
                  "vr": round(tv[-1] / (sum(prior) / len(prior)), 2) if tv[-1] and len(prior) == 20 and all(prior) else None,
                  "s20": [pct(a, n) for a, n in zip(cnt["a20"], cnt["n20"])], "from": str(out_days[0])}
    return out


# ─── 條件選股（第 8 輪 F8-2）────────────────────────────
def price_stats(d_, adj, tv, days, idx):
    """
    C3 價量欄位。d_：該股日線日期（舊到新，最後一列 = 資料日）；adj：還原收盤（無成交 None）；tv：成交額（元，None 當 0）；
    days：全市場交易日（舊到新，最後一天 = 資料日）；idx：{日期: 該市場指數收盤}。
    """
    yi = [float(x or 0) / YI for x in tv]
    px = [x for x in adj if x is not None]
    lc = px[-1] if px else None                          # 最後成交的還原收盤（今天無成交時是之前的收盤）
    traded = adj[-1] is not None
    out = {"a20": _f(sum(yi[-20:]) / 20) if len(yi) >= 20 else None}
    prior = yi[-21:-1]
    out["vr"] = _f(yi[-1] / (sum(prior) / 20)) if len(prior) == 20 and sum(prior) > 0 else None
    raw = {}
    for n in (5, 20, 60):
        b = days[-1 - n] if len(days) > n else None
        base = next((a for d, a in zip(reversed(d_), reversed(adj)) if d <= b and a is not None), None) \
            if b is not None and d_[0] <= b else None
        raw[n] = (lc / base - 1) * 100 if base and lc else None
        out[f"r{n}"] = _f(raw[n])
    for n in (20, 60):
        b = days[-1 - n] if len(days) > n else None
        ir = (float(idx[days[-1]]) / float(idx[b]) - 1) * 100 if b in idx and days[-1] in idx else None
        out[f"rs{n}"] = _f(raw[n] - ir) if raw[n] is not None and ir is not None else None
    for n in (20, 60):
        out[f"b{n}"] = _f((lc / (sum(px[-n:]) / n) - 1) * 100) if len(px) >= n else None
    out["nh"] = next((n for n in NH_DAYS if traded and len(px) > n and px[-1] > max(px[-n - 1:-1])), 0)
    out["nl"] = next((n for n in NH_DAYS if traded and len(px) > n and px[-1] < min(px[-n - 1:-1])), 0)
    return out


def revenue_stats(rows):
    """C3 營收欄位。rows：_revenue_rows 的輸出（舊到新）；取該股最新一個月。r3 = 最近 3 個月連續且年增都 > 0。"""
    if not rows:
        return dict.fromkeys(("rm", "ry", "rc", "rh", "r3"))
    y, m, _, _, yoy, cum, hi = rows[-1]
    l3 = rows[-3:]
    r3 = len(l3) == 3 and l3[0][0] * 12 + l3[0][1] + 2 == y * 12 + m and all(r[4] is not None and r[4] > 0 for r in l3)
    return {"rm": y * 100 + m, "ry": yoy, "rc": cum, "rh": hi, "r3": int(r3)}


# ─── 第 10 輪 B5：季報（資料庫存累計值，這裡相減成單季；個股與選股共用）──────
def _r1(a, b):
    """a ÷ b × 100，四捨五入（ROUND_HALF_UP）到 1 位小數。"""
    return float((Decimal(a) * 100 / Decimal(b)).quantize(Decimal("0.1"), ROUND_HALF_UP))


def fin_single(cum: dict, y: int, q: int):
    """
    單季 [營收, 毛利, 營益, 淨利, EPS]：Q1 = 累計；Q2～Q4 = 本季累計 − 上一季累計（Q4 = 全年 − Q3 累計）。
    cum = {(年, 季): (營收, 毛利, 營益, 淨利, EPS)}；該季沒有 → None；上一季沒有或該欄 NULL → 該欄 None（不以累計頂替）。
    """
    cur = cum.get((y, q))
    if cur is None:
        return None
    prev = None if q == 1 else cum.get((y, q - 1))
    if q == 1:
        return list(cur)
    return [a - b if prev is not None and a is not None and b is not None else None for a, b in zip(cur, prev or (None,) * 5)]


def fin_yoy(v, base):
    """年增 %：去年同期 ≤ 0 或任一缺 → None（畫面寫「轉盈」等）。"""
    return None if v is None or base is None or base <= 0 else _r1(v - base, base)


def fin_margin(x, rev):
    """毛利率、營益率 %：單季營收 ≤ 0 或缺 → None。"""
    return None if x is None or rev is None or rev <= 0 else _r1(x, rev)


def fin_e4(cum: dict, y: int, q: int):
    """近 4 季 EPS = 本季累計 + 去年全年 − 去年同季累計（四項缺一 → None）；Q4 = 全年。"""
    if q == 4:
        return cum[(y, 4)][4] if (y, 4) in cum else None
    xs = [cum.get(k, (None,) * 5)[4] for k in ((y, q), (y - 1, 4), (y - 1, q))]
    return None if None in xs else xs[0] + xs[1] - xs[2]


def fin_stock(cum: dict, tbl: str, seen):
    """stocks/{代號}.json 的 fin；沒有任何季報 → None。q：近 8 季（有累計值的季別，舊到新）[季別, 單季 EPS, EPS 年增, 毛利率, 營益率, 單季營收, 去年同季單季 EPS]。"""
    if not cum:
        return None
    y, q = max(cum)
    keys, k = [], (y, q)
    for _ in range(FIN_QUARTERS):
        keys.append(k)
        k = prev_quarter(*k)
    rows = []
    for yy, qq in reversed(keys):
        if (yy, qq) not in cum:
            continue
        s, b = fin_single(cum, yy, qq), fin_single(cum, yy - 1, qq)
        rows.append([yy * 100 + qq, _f(s[4]), fin_yoy(s[4], b and b[4]), fin_margin(s[1], s[0]), fin_margin(s[2], s[0]), s[0],
                     _f(b and b[4])])   # 第 10 輪 QA-01：去年同季單季 EPS（前 4 季的去年同季不在 q 內，畫面靠它判斷「轉盈」）
    e, eb = cum[(y, q)][4], cum.get((y - 1, q), (None,) * 5)[4]
    return {"t": tbl, "q": rows, "c": {"e": _f(e), "ey": fin_yoy(e, eb), **({"fs": str(seen)} if seen else {})},
            "e4": _f(fin_e4(cum, y, q)), "e4p": _f(fin_e4(cum, y - 1, q))}


def fin_screen(cum: dict) -> dict:
    """screen.json 的季報欄（最新一季）：eq 單季 EPS、ey 年增 %、e4 近 4 季、gm 毛利率、gmy 毛利率年增（百分點）、fq 季別、eh 創 N 季新高。"""
    if not cum:
        return dict.fromkeys(("eq", "ey", "e4", "gm", "gmy", "fq", "eh"))
    y, q = max(cum)
    s, b = fin_single(cum, y, q), fin_single(cum, y - 1, q)
    gm, gmb = fin_margin(s[1], s[0]), b and fin_margin(b[1], b[0])
    eh, k = 0, prev_quarter(y, q)          # 單季 EPS 高於之前連續 eh 季
    while s[4] is not None and (p := fin_single(cum, *k)) and p[4] is not None and p[4] < s[4]:
        eh += 1
        k = prev_quarter(*k)
    return {"eq": _f(s[4]), "ey": fin_yoy(s[4], b and b[4]), "e4": _f(fin_e4(cum, y, q)), "gm": gm,
            "gmy": _f(gm - gmb, 1) if gm is not None and gmb is not None else None, "fq": y * 100 + q, "eh": eh}


def fin_progress(counts: dict, d):
    """今日頁一行：資料日在季報窗口內、當季已有資料時 {q, n: {市場: 家數}, p: {市場: 前一季家數}}；否則 None。"""
    fq = fin_quarter_for(d)
    if not fq:
        return None
    n = {m: counts.get((*fq, m), 0) for m in ("TWSE", "TPEx")}
    if not any(n.values()):
        return None
    pq = prev_quarter(*fq)
    return {"q": fq[0] * 100 + fq[1], "n": n, "p": {m: counts.get((*pq, m), 0) for m in ("TWSE", "TPEx")}}


def _load_financials(cur) -> tuple:
    """({代號: {(年, 季): (營收, 毛利, 營益, 淨利, EPS)}}, {代號: (最新一季業別, 最新一季 first_seen)}, {(年, 季, 市場): 家數})。"""
    fin, meta, counts = defaultdict(dict), {}, Counter()
    for code, mkt, y, q, tbl, *vals, seen in cur.execute("""
        SELECT s.stock_code, s.market_type, f.fin_year, f.fin_quarter, f.industry_tbl,
               f.revenue, f.gross_profit, f.op_income, f.net_income, f.eps, f.first_seen
        FROM quarterly_financials f JOIN stocks s ON s.stock_id = f.stock_id
        ORDER BY s.stock_code, f.fin_year, f.fin_quarter"""):
        fin[code][(y, q)] = tuple(vals)
        meta[code] = (tbl, seen)
        counts[(y, q, mkt)] += 1
    return fin, meta, counts


def screen_build(rows, head):
    """screen.json：欄式。rows：{代號: {SCREEN_KEYS…}}（依代號排序）；head：d、fd、md、sd（第 11 輪：各市場借券資料日）。rmd = 各營收月份的檔數。"""
    codes = sorted(rows)
    rmd = Counter(rows[c]["rm"] for c in codes if rows[c]["rm"] is not None)
    fqd = Counter(rows[c]["fq"] for c in codes if rows[c].get("fq") is not None)        # 第 10 輪：各季報季別的檔數
    return {**head, "rmd": {str(k): v for k, v in sorted(rmd.items(), reverse=True)},
            "fqd": {str(k): v for k, v in sorted(fqd.items(), reverse=True)}, "codes": codes,
            **{k: [rows[c][k] for c in codes] for k in SCREEN_KEYS}}


def _load_breadth(cur, d):
    """官方漲跌家數：{市場: {up, ul（漲停）, dn, dl（跌停）, fl（平盤）, nt（未成交）}}，只取資料日當天。"""
    return {m: dict(zip(("up", "ul", "dn", "dl", "fl", "nt"), v)) for m, *v in cur.execute(
        "SELECT market, up, up_limit, down, down_limit, flat, no_trade FROM market_breadth WHERE trade_date = ?", d)}


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
    shares = {c: n for c, n in cur.execute("SELECT stock_code, shares FROM stocks WHERE shares > 0")}     # 第 11 輪

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
    amount = amount_by_market(cur.execute("SELECT trade_date, market, unit, net_amount FROM insti_amount"))
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
    holdings = _load_holdings(cur)
    etf_names = {code: (name, m) for code, name, m in cur.execute("SELECT etf_code, etf_name, market_type FROM etfs")}
    official_breadth = _load_breadth(cur, latest_date)
    # 寬度輸出 BREADTH_DAYS 天，前面多 60 天給 MA60
    b_days = [r[0] for r in cur.execute(f"SELECT DISTINCT TOP {BREADTH_DAYS + 60} trade_date FROM daily_prices ORDER BY trade_date DESC")][::-1]
    status = build_status(cur, latest_date, now)
    valuation, stock_val, val_date = _load_valuation(cur, shares)      # F9-4；第 12 輪加 wpe
    fin, fin_meta, fin_counts = _load_financials(cur)          # 第 10 輪 B5
    sdates, srecent, sper = _load_sbl(cur)                     # 第 11 輪 B14
    edates, esbl, esbl_m = _load_etf_sbl(cur)                  # 第 12 輪 ETF 借券
    conn.close()
    mlast = {m: ds[-1] for m, ds in mdates.items()}
    m5 = {m: ds[-6] if len(ds) >= 6 else None for m, ds in mdates.items()}
    slast = {m: ds[-1] for m, ds in sdates.items()}
    s5 = {m: ds[-6] if len(ds) >= 6 else None for m, ds in sdates.items()}

    concepts = load_concepts()
    concept_of = defaultdict(list)
    for name, codes in concepts.items():
        for c in codes:
            concept_of[c].append(name)

    # ── ETF 持股檔（台股 = stocks 表的代號）──
    tw = set(stocks)
    for code, (hdates, summary, held) in holdings.items():
        _write(SITE_DATA_DIR / "etfs" / f"{code}.json", holding_export(code, hdates, summary, held, tw, *etf_names[code]))
    active = stock_active(holdings, tw)
    act_lots = active_trust(holdings, tw, dates[-1])            # B16（第 8 輪 F8-1）
    idx_close = {m: {d: c for d, c, _ in index_rows.get(code, []) if c is not None}
                 for m, code in (("TWSE", "TAIEX"), ("TPEx", "TPEX"))}
    screen = {}           # 條件選股：{代號: SCREEN_KEYS 欄位}

    # ── 個股檔 + 最新指標 ──
    window = set(dates)
    b_from = b_days[0]
    b_series, b_turnover = defaultdict(list), defaultdict(lambda: defaultdict(float))
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
        cap = _cap_event(ev, latest_date)
        rev_rows = _revenue_rows(revenue.get(code, []))
        mrows = mper.get(code, {})
        conv = margin_conv(mrows, ev)
        srows = sper.get(code, {})
        mg = margin_series(d_, mrows, conv, srows)
        mk_ = info["market"]
        sbl = stock_sbl(srows, slast.get(mk_), s5.get(mk_), shares.get(code),
                        (mrows.get(slast.get(mk_)) or (None,) * 5)[4], conv)
        # 第 12 輪 B11：最新收盤（無成交日用最後一個收盤）× 目前股數；週轉率只在最後一根是資料日時計算
        lc = next((x for x in reversed(c) if x is not None), None)
        mc, to = cap_turnover(lc, v[-1] if d_[-1] == latest_date else None, shares.get(code))
        act = None
        if code in act_lots and dates[-1] in d_ and tn[d_.index(dates[-1])] is not None:
            t_lots = round(tn[d_.index(dates[-1])] / 1000)
            act = {"d": str(dates[-1]), "t": t_lots, "e": act_lots[code], "p": trust_share(t_lots, act_lots[code])}

        _write(SITE_DATA_DIR / "stocks" / f"{code}.json", {
            "code": code, **info, "concepts": concept_of.get(code, []), "chains": chain_of.get(code, []),
            "prices": {"d": [str(x) for x in d_], "o": [_f(x) for x in o], "h": [_f(x) for x in h],
                       "l": [_f(x) for x in l], "c": [_f(x) for x in c],
                       "v": [round(x / 1000) if x else 0 for x in v], "ch": chs},   # 張
            "ev": [{k: e[k] for k in ("d", "t", "p", "r")} for e in ev],
            "insti": {"f": [round(x / 1000) if x is not None else None for x in fn],   # 張
                      "t": [round(x / 1000) if x is not None else None for x in tn],
                      "dl": [round(x / 1000) if x is not None else None for x in dn]},
            "revenue": rev_rows[-REVENUE_MONTHS:],
            **({"fin": fb} if (fb := fin_stock(fin.get(code), *fin_meta.get(code, (None, None)))) else {}),   # 第 10 輪 B5
            "fund": dict(zip(("pe", "pb", "dy"), map(_f, fund[code][:3])), date=str(fund[code][3]))
                    if code in fund else None,
            **({"capchg": cap} if cap else {}),
            # F9-4：估值一年位置；股本變動（cap）時官方值可能尚未調整，不輸出；只有窗口最後一天有官方值的股票才有
            **({"val": {"d": str(val_date), **stock_val[code]}} if stock_val.get(code) and not cap else {}),
            **({"alerts": alerts[code]} if code in alerts else {}),
            # 該市場有融資融券資料時才有 margin；null = 不在信用交易清單（無信用交易）
            **({"margin": stock_margin(mrows, mlast[info["market"]], m5[info["market"]], conv)}
               if info["market"] in mlast else {}),
            **({"active": active[code]} if code in active else {}),
            **({"sbl": sbl} if sbl else {}),                                     # 第 11 輪 B14：該股最新借券日沒有列 → 不輸出
            **({"mt": {"d": str(latest_date), "mc": mc, "to": to}} if mc is not None else {}),   # 第 12 輪 B11
            **({"mg": mg} if mg else {}),
            **({"act": act} if act else {}),
        })
        # 市場寬度：還原收盤（無成交日不列入）、成交額
        b_series[info["market"]].append({d_[i]: float(c[i]) * af[i] for i in range(len(d_)) if d_[i] >= b_from and c[i] is not None})
        for i in range(len(d_)):
            if d_[i] >= b_from:
                b_turnover[info["market"]][d_[i]] += (tv[i] or 0) / YI

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
        mkt = info["market"]
        screen[code] = {**price_stats(d_, [float(c[i]) * af[i] if c[i] is not None else None for i in range(len(d_))],
                                      tv, b_days, idx_close[mkt]),
                        **revenue_stats(rev_rows), "cap": int(cap is not None),
                        **screen_margin(mrows, mlast.get(mkt), m5.get(mkt), conv, mkt),
                        "pbp": (stock_val.get(code) or {}).get("pb", [None])[0],     # F9-4：淨值比一年位置（cap 由前端估值規則排除）
                        **fin_screen(fin.get(code)),                                  # 第 10 輪 B5
                        **{k: (sbl or {}).get(k) for k in ("lb", "l1", "l5", "lp")},   # 第 11 輪 B14
                        "mc": mc, "to": to}                                               # 第 12 輪 B11

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
        "insti_official": _insti_official(amount["TWSE"]),
        "insti_official_tpex": _insti_official(amount["TPEx"]),      # 第 9 輪 F9-1：上櫃官方（結構同 insti_official）
        "valuation": valuation,                                      # 第 9 輪 F9-4：市場估值一年位置
        "fin_progress": fin_progress(fin_counts, latest_date),       # 第 10 輪 B5：季報公布進度（窗口外 null）
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
        "sbl": {m: market_sbl(sdates[m], srecent[m]) for m in ("TWSE", "TPEx") if sdates.get(m)} or None,   # 第 11 輪 B14
        "sbl_etf": {m: market_sbl([d], {d: [(p, b) for _, p, b in esbl_m[m].values()]}) for m, d in edates.items()} or None,   # 第 12 輪
        "etfs": etf_block(etf_latest, etf_margin_rows, esbl),
        "holdings": {code: {"d": str(hd[-1]), "n": etf_names[code][0],
                            **({"u1": u} if (u := unit_change(hs, hd)) is not None else {})}
                     for code, (hd, hs, _) in holdings.items()},
        "active_rank": active_rank(holdings, tw, lambda c, d: close(c, d, False)) if holdings else None,   # 第 7 輪 F7-2
        # o：官方家數（資料日當天沒有為 null）；其餘為自算
        "breadth": {m: {"o": official_breadth.get(m), **b} for m, b in breadth_calc(b_series, b_days, b_turnover).items()},
        "groups": {
            "industry": group_flows(industries, daily, dates, REPLAY),
            "chain": group_flows(chains, daily, dates, REPLAY),
            "concept": group_flows(concepts, daily, dates, REPLAY),
        },
        "stocks": snapshot,
    }
    # screen.json 在 latest.json 之前寫：中途失敗時前端比對 d／fd 會顯示不同步
    S = screen_build(screen, {"d": str(latest_date), "fd": str(dates[-1]), "md": {m: str(d) for m, d in mlast.items()},
                              "sd": {m: str(d) for m, d in slast.items()}})
    _write(SITE_DATA_DIR / "screen.json", S)
    _write(SITE_DATA_DIR / "latest.json", latest)
    size = (SITE_DATA_DIR / "latest.json").stat().st_size / 1024
    print(f"  📌 screen.json {(SITE_DATA_DIR / 'screen.json').stat().st_size / 1024:.0f} KB（營收月份 " +
          "、".join(f"{k[:4]}/{k[4:]} {v:,} 檔" for k, v in S["rmd"].items()) + "；季報 " +
          ("、".join(f"{k[:4]}Q{k[5]} {v:,} 檔" for k, v in S["fqd"].items()) or "無") + "）")
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
