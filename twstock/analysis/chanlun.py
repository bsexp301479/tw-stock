"""
纏論結構圖：K 線包含處理 → 分型 → 筆 → 中樞，加上 MACD，輸出 SVG 到 output/。

日線優先取自資料庫；資料庫不足 min_bars 根時改抓 Yahoo Finance。
"""
import datetime
import html
import json
import urllib.request

from .. import db
from ..config import OUTPUT_DIR


def load_bars(code: str, days: int = 130, min_bars: int = 60):
    """回傳 (名稱, [{d, o, h, l, c, v}...])。"""
    conn = db.connect()
    try:
        cur = conn.cursor()
        info = cur.execute("SELECT stock_name, market_type FROM stocks WHERE stock_code = ?", code).fetchone()
        rows = cur.execute(f"""
            SELECT TOP {int(days)} d.trade_date, d.open_price, d.high_price, d.low_price, d.close_price, d.volume
            FROM daily_prices d JOIN stocks s ON s.stock_id = d.stock_id
            WHERE s.stock_code = ? AND d.close_price IS NOT NULL AND d.open_price IS NOT NULL
            ORDER BY d.trade_date DESC""", code).fetchall()[::-1]
    finally:
        conn.close()
    name = f"{info[0]} {code}" if info else code
    if len(rows) >= min_bars:
        return name, [{"d": str(r[0]), "o": float(r[1]), "h": float(r[2]), "l": float(r[3]),
                       "c": float(r[4]), "v": r[5] or 0} for r in rows]

    # 資料庫歷史不夠 → Yahoo Finance（上市 .TW、上櫃 .TWO）
    suffix = ".TWO" if info and info[1] == "TPEx" else ".TW"
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{code}{suffix}?range=6mo&interval=1d"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    res = json.load(urllib.request.urlopen(req, timeout=20))["chart"]["result"][0]
    q = res["indicators"]["quote"][0]
    bars = []
    for i, ts in enumerate(res["timestamp"]):
        o, h, l, c = q["open"][i], q["high"][i], q["low"][i], q["close"][i]
        if None in (o, h, l, c):
            continue
        d = datetime.datetime.fromtimestamp(ts + 28800, datetime.timezone.utc).strftime("%Y-%m-%d")
        bars.append({"d": d, "o": o, "h": h, "l": l, "c": c, "v": q["volume"][i] or 0})
    return name, bars


def draw(code: str, days: int = 130):
    name, bars = load_bars(code, days)
    if len(bars) < 30:
        raise SystemExit(f"❌ {code} 日線不足 30 根，無法畫纏論結構")
    out = OUTPUT_DIR / f"chanlun_{code}.svg"
    out.parent.mkdir(parents=True, exist_ok=True)

    N = len(bars)
    for i, b in enumerate(bars):
        b["idx"] = i
    print(f"取得 {N} 根日線：{bars[0]['d']} ~ {bars[-1]['d']}")

    # ---------- 2. K線包含處理 ----------
    proc = []  # 每根: hi, lo, hidx, lidx
    for b in bars:
        cur = {"hi": b["h"], "lo": b["l"], "hidx": b["idx"], "lidx": b["idx"]}
        if not proc:
            proc.append(cur); continue
        last = proc[-1]
        contained = (cur["hi"] <= last["hi"] and cur["lo"] >= last["lo"]) or \
                    (cur["hi"] >= last["hi"] and cur["lo"] <= last["lo"])
        if contained:
            direction = "up"
            if len(proc) >= 2:
                direction = "up" if proc[-1]["hi"] > proc[-2]["hi"] else "down"
            if direction == "up":
                if cur["hi"] >= last["hi"]: last["hi"], last["hidx"] = cur["hi"], cur["hidx"]
                if cur["lo"] >= last["lo"]: last["lo"], last["lidx"] = cur["lo"], cur["lidx"]
            else:
                if cur["hi"] <= last["hi"]: last["hi"], last["hidx"] = cur["hi"], cur["hidx"]
                if cur["lo"] <= last["lo"]: last["lo"], last["lidx"] = cur["lo"], cur["lidx"]
        else:
            proc.append(cur)

    # ---------- 3. 分型 ----------
    fractals = []  # type: 'top'/'bottom', price, oidx, p(=proc index)
    for i in range(1, len(proc) - 1):
        a, m, z = proc[i - 1], proc[i], proc[i + 1]
        if m["hi"] > a["hi"] and m["hi"] > z["hi"] and m["lo"] > a["lo"] and m["lo"] > z["lo"]:
            fractals.append({"t": "top", "price": m["hi"], "oidx": m["hidx"], "p": i})
        elif m["lo"] < a["lo"] and m["lo"] < z["lo"] and m["hi"] < a["hi"] and m["hi"] < z["hi"]:
            fractals.append({"t": "bottom", "price": m["lo"], "oidx": m["lidx"], "p": i})

    # ---------- 4. 筆（交替頂底 + 最小間隔）----------
    GAP = 4  # 處理後K線最小間隔（老筆精神）
    pts = []
    for f in fractals:
        if not pts:
            pts.append(f); continue
        last = pts[-1]
        if f["t"] == last["t"]:
            if (f["t"] == "top" and f["price"] >= last["price"]) or \
               (f["t"] == "bottom" and f["price"] <= last["price"]):
                pts[-1] = f
        else:
            if f["p"] - last["p"] >= GAP:
                pts.append(f)

    # ---------- 5. 中樞（連續三筆重疊區，可延伸）----------
    n_st = len(pts) - 1
    los = [min(pts[s]["price"], pts[s + 1]["price"]) for s in range(n_st)]
    his = [max(pts[s]["price"], pts[s + 1]["price"]) for s in range(n_st)]
    zhongshu = []
    s = 0
    while s <= n_st - 3:
        ZD = max(los[s], los[s + 1], los[s + 2])
        ZG = min(his[s], his[s + 1], his[s + 2])
        if ZD < ZG:
            last = s + 2
            k = s + 3
            while k < n_st and los[k] < ZG and his[k] > ZD:
                last = k; k += 1
            zhongshu.append({"a": pts[s], "b": pts[last + 1], "ZD": ZD, "ZG": ZG})
            s = last + 1
        else:
            s += 1

    # ---------- 6. MACD ----------
    def ema(vals, n):
        k = 2 / (n + 1); out = []; prev = vals[0]
        for v in vals:
            prev = v * k + prev * (1 - k); out.append(prev)
        return out
    closes = [b["c"] for b in bars]
    e12, e26 = ema(closes, 12), ema(closes, 26)
    dif = [a - b for a, b in zip(e12, e26)]
    dea = ema(dif, 9)
    macd = [2 * (a - b) for a, b in zip(dif, dea)]

    # ---------- 7. SVG ----------
    W, H = 1280, 820
    ML, MR, MT = 70, 24, 70
    main_top, main_h = MT, 470
    macd_top, macd_h = main_top + main_h + 56, 150
    PX0, PX1 = ML, W - MR
    prices = [b["h"] for b in bars] + [b["l"] for b in bars]
    pmax, pmin = max(prices), min(prices)
    pad = (pmax - pmin) * 0.06
    pmax += pad; pmin -= pad

    def x(i): return PX0 + i * (PX1 - PX0) / (N - 1)
    def yp(p): return main_top + (pmax - p) / (pmax - pmin) * main_h
    cw = max(2.0, (PX1 - PX0) / N * 0.62)

    mmax = max(max(dif), max(dea), max(macd)); mmin = min(min(dif), min(dea), min(macd))
    mpad = (mmax - mmin) * 0.1 or 1; mmax += mpad; mmin -= mpad
    def ym(v): return macd_top + (mmax - v) / (mmax - mmin) * macd_h

    UP, DOWN = "#d0312d", "#2e8b57"  # 台股：紅漲綠跌
    S = []
    S.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
             f'font-family="\'PingFang TC\',\'Microsoft JhengHei\',sans-serif">')
    S.append(f'<rect width="{W}" height="{H}" fill="#ffffff"/>')
    S.append(f'<text x="{W/2}" y="34" text-anchor="middle" font-size="24" font-weight="700" fill="#111">'
             f'{html.escape(name)} 纏論結構圖（日線 {bars[0]["d"]} ~ {bars[-1]["d"]}）</text>')
    S.append(f'<text x="{W/2}" y="56" text-anchor="middle" font-size="13" fill="#777">'
             f'K線包含處理 → 分型 → 筆 → 中樞　｜　收盤 {closes[-1]:.2f}</text>')

    # price grid + y labels
    for i in range(6):
        p = pmin + (pmax - pmin) * i / 5
        yy = yp(p)
        S.append(f'<line x1="{PX0}" y1="{yy:.1f}" x2="{PX1}" y2="{yy:.1f}" stroke="#eee" stroke-width="1"/>')
        S.append(f'<text x="{PX0-8}" y="{yy+4:.1f}" text-anchor="end" font-size="11" fill="#999">{p:.1f}</text>')

    # date ticks (~ monthly)
    seen = set()
    for i, b in enumerate(bars):
        ym_ = b["d"][:7]
        if ym_ not in seen:
            seen.add(ym_)
            S.append(f'<line x1="{x(i):.1f}" y1="{main_top}" x2="{x(i):.1f}" y2="{main_top+main_h}" stroke="#f4f4f4"/>')
            S.append(f'<text x="{x(i):.1f}" y="{main_top+main_h+16}" text-anchor="middle" font-size="11" fill="#999">{b["d"][2:]}</text>')

    # 中樞 boxes (draw first, behind candles)
    for z in zhongshu:
        x0, x1 = x(z["a"]["oidx"]), x(z["b"]["oidx"])
        y0, y1 = yp(z["ZG"]), yp(z["ZD"])
        S.append(f'<rect x="{x0:.1f}" y="{y0:.1f}" width="{(x1-x0):.1f}" height="{(y1-y0):.1f}" '
                 f'fill="#f5a623" fill-opacity="0.16" stroke="#f5a623" stroke-width="1.4" stroke-dasharray="6 4"/>')
        S.append(f'<text x="{(x0+x1)/2:.1f}" y="{y0-5:.1f}" text-anchor="middle" font-size="11" '
                 f'font-weight="600" fill="#c77f12">中樞 {z["ZD"]:.1f}~{z["ZG"]:.1f}</text>')

    # candles
    for b in bars:
        xx = x(b["idx"]); col = UP if b["c"] >= b["o"] else DOWN
        S.append(f'<line x1="{xx:.1f}" y1="{yp(b["h"]):.1f}" x2="{xx:.1f}" y2="{yp(b["l"]):.1f}" stroke="{col}" stroke-width="1"/>')
        yo, yc = yp(b["o"]), yp(b["c"]); top = min(yo, yc); hgt = max(abs(yo - yc), 1)
        S.append(f'<rect x="{xx-cw/2:.1f}" y="{top:.1f}" width="{cw:.1f}" height="{hgt:.1f}" fill="{col}"/>')

    # 筆 polyline
    poly = " ".join(f'{x(p["oidx"]):.1f},{yp(p["price"]):.1f}' for p in pts)
    S.append(f'<polyline points="{poly}" fill="none" stroke="#1f5fbf" stroke-width="2.2" stroke-opacity="0.9"/>')

    # 分型 markers on stroke endpoints
    for p in pts:
        xx, yy = x(p["oidx"]), yp(p["price"])
        if p["t"] == "top":
            S.append(f'<rect x="{xx-4:.1f}" y="{yy-4:.1f}" width="8" height="8" fill="#c0392b"/>')
        else:
            S.append(f'<circle cx="{xx:.1f}" cy="{yy:.1f}" r="4.5" fill="#1e8449"/>')

    # ---------- MACD panel ----------
    S.append(f'<text x="{PX0}" y="{macd_top-12}" font-size="13" font-weight="600" fill="#444">'
             f'MACD（DIF / DEA / 柱）— 觀察背馳</text>')
    y0 = ym(0)
    S.append(f'<line x1="{PX0}" y1="{y0:.1f}" x2="{PX1}" y2="{y0:.1f}" stroke="#ddd"/>')
    bw = max(1.5, (PX1 - PX0) / N * 0.6)
    for i in range(N):
        v = macd[i]; col = UP if v >= 0 else DOWN
        yy = ym(v)
        S.append(f'<rect x="{x(i)-bw/2:.1f}" y="{min(yy,y0):.1f}" width="{bw:.1f}" height="{abs(yy-y0):.1f}" fill="{col}" fill-opacity="0.55"/>')
    def mline(vals, col):
        return '<polyline points="' + " ".join(f'{x(i):.1f},{ym(vals[i]):.1f}' for i in range(N)) + f'" fill="none" stroke="{col}" stroke-width="1.6"/>'
    S.append(mline(dif, "#e67e22"))
    S.append(mline(dea, "#2980b9"))

    # ---------- legend ----------
    lx, ly = PX1 - 250, main_top + 8
    S.append(f'<rect x="{lx}" y="{ly}" width="244" height="92" fill="#fff" stroke="#e0e0e0" rx="6"/>')
    S.append(f'<rect x="{lx+12}" y="{ly+14}" width="9" height="9" fill="#c0392b"/><text x="{lx+28}" y="{ly+23}" font-size="12" fill="#444">頂分型</text>')
    S.append(f'<circle cx="{lx+135}" cy="{ly+18}" r="4.5" fill="#1e8449"/><text x="{lx+146}" y="{ly+23}" font-size="12" fill="#444">底分型</text>')
    S.append(f'<line x1="{lx+12}" y1="{ly+40}" x2="{lx+34}" y2="{ly+40}" stroke="#1f5fbf" stroke-width="2.2"/><text x="{lx+40}" y="{ly+44}" font-size="12" fill="#444">筆</text>')
    S.append(f'<rect x="{lx+90}" y="{ly+34}" width="20" height="12" fill="#f5a623" fill-opacity="0.2" stroke="#f5a623" stroke-dasharray="4 3"/><text x="{lx+116}" y="{ly+44}" font-size="12" fill="#444">中樞</text>')
    S.append(f'<rect x="{lx+12}" y="{ly+60}" width="9" height="9" fill="#d0312d"/><text x="{lx+28}" y="{ly+69}" font-size="12" fill="#444">紅漲</text>')
    S.append(f'<rect x="{lx+90}" y="{ly+60}" width="9" height="9" fill="#2e8b57"/><text x="{lx+106}" y="{ly+69}" font-size="12" fill="#444">綠跌</text>')

    S.append("</svg>")
    out.write_text("\n".join(S), encoding="utf-8")   # Windows 預設 cp950，必須指定
    print(f"處理後K線 {len(proc)} 根；分型 {len(fractals)} 個；筆端點 {len(pts)} 個；中樞 {len(zhongshu)} 個")
    print(f"輸出：{out}")
    return out
