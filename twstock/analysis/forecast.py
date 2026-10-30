"""
依期貨三大法人未平倉預測「下一個交易日台指期日盤」漲跌（羅吉斯迴歸，純 Python）。

特徵（皆以過去 60 個交易日標準化，只用當天以前的資料）：
  外資淨未平倉水位、外資 1 日 / 5 日增減、投信 1 日增減、自營商 1 日增減
  口數為約當大台：大台 + 小台 / 4 + 微台 / 20
標籤：隔天近月台指期日盤的官方漲跌 > 0

回測採 walk-forward：預測第 i 天時只用 i 之前的樣本訓練，每 20 天重新訓練一次，
並和「永遠猜多數方向」的基準比較，避免高估模型。
"""
import math
from collections import defaultdict

WINDOW = 60          # 標準化視窗
MIN_TRAIN = 100      # 開始回測前至少要有的訓練樣本
REFIT_EVERY = 20
L2 = 1.0
THRESHOLD = 0.05     # 機率偏離 50% 超過 5 個百分點才算有方向

EQUIV = {"TXF": 1.0, "MXF": 0.25, "TMF": 0.05}
FEATURES = [
    ("foreign_level", "外資淨未平倉水位"),
    ("foreign_d1", "外資未平倉 1 日增減"),
    ("foreign_d5", "外資未平倉 5 日增減"),
    ("trust_d1", "投信未平倉 1 日增減"),
    ("dealer_d1", "自營商未平倉 1 日增減"),
]


def load_oi(cur) -> dict:
    """
    {日期: {投資人: 約當大台淨未平倉}}。
    契約上市後（微台 2024/7 才有）的日子三種都要有才採用，避免某商品漏抓時失真。
    """
    raw = defaultdict(lambda: defaultdict(dict))
    first = {}
    for d, com, inv, net in cur.execute(
            "SELECT trade_date, commodity_id, investor, net_oi FROM futures_institutional ORDER BY trade_date"):
        raw[d][inv][com] = net or 0
        first.setdefault(com, d)
    out = {}
    for d, invs in raw.items():
        need = {c for c in EQUIV if c in first and first[c] <= d}
        if len(invs) == 3 and all(need <= v.keys() for v in invs.values()):
            out[d] = {inv: sum(v.get(c, 0) * w for c, w in EQUIV.items()) for inv, v in invs.items()}
    return out


def _z(series: list, i: int):
    win = [v for v in series[max(0, i - WINDOW + 1):i + 1] if v is not None]
    if len(win) < WINDOW // 2 or series[i] is None:
        return None
    m = sum(win) / len(win)
    sd = math.sqrt(sum((v - m) ** 2 for v in win) / len(win))
    return (series[i] - m) / sd if sd else 0.0


def _fit(X: list, y: list, iters=400, lr=0.2) -> list:
    w = [0.0] * (len(X[0]) + 1)
    n = len(X)
    for _ in range(iters):
        g = [0.0] * len(w)
        for xi, yi in zip(X, y):
            z = w[0] + sum(a * b for a, b in zip(w[1:], xi))
            p = 1 / (1 + math.exp(-max(-30, min(30, z))))
            e = p - yi
            g[0] += e
            for j, v in enumerate(xi):
                g[j + 1] += e * v
        w[0] -= lr * g[0] / n
        for j in range(1, len(w)):
            w[j] -= lr * (g[j] / n + L2 * w[j] / n)
    return w


def _prob(w: list, x: list) -> float:
    z = w[0] + sum(a * b for a, b in zip(w[1:], x))
    return 1 / (1 + math.exp(-max(-30, min(30, z))))


def build_forecast(oi: dict, tx_dates: list, tx_change: list):
    """tx_dates / tx_change：近月台指期日盤（由舊到新）。回傳網站用的 dict，資料不足時回傳 None。"""
    dates = [d for d in tx_dates if d in oi]
    if len(dates) < WINDOW + MIN_TRAIN // 2:
        return None
    chg = dict(zip(tx_dates, tx_change))
    nxt = {d: tx_dates[i + 1] for i, d in enumerate(tx_dates[:-1])}

    fo = [oi[d]["foreign"] for d in dates]
    tr = [oi[d]["trust"] for d in dates]
    de = [oi[d]["dealer"] for d in dates]
    diff = lambda s, k: [s[i] - s[i - k] if i >= k else None for i in range(len(s))]
    raw = {"foreign_level": fo, "foreign_d1": diff(fo, 1), "foreign_d5": diff(fo, 5),
           "trust_d1": diff(tr, 1), "dealer_d1": diff(de, 1)}

    rows = []      # (日期, 特徵 z, 標籤或 None)
    for i, d in enumerate(dates):
        x = [_z(raw[k], i) for k, _ in FEATURES]
        if any(v is None for v in x):
            continue
        c = chg.get(nxt.get(d)) if d in nxt else None
        rows.append((d, x, None if c is None else 1 if c > 0 else 0))

    labeled = [r for r in rows if r[2] is not None]
    if len(labeled) < MIN_TRAIN + 20:
        return None

    # walk-forward 回測
    preds, w = [], None
    for i in range(MIN_TRAIN, len(labeled)):
        if w is None or (i - MIN_TRAIN) % REFIT_EVERY == 0:
            w = _fit([r[1] for r in labeled[:i]], [r[2] for r in labeled[:i]])
        preds.append((labeled[i][0], _prob(w, labeled[i][1]), labeled[i][2]))
    hits = [(p >= 0.5) == bool(y) for _, p, y in preds]
    up_rate = sum(y for _, _, y in preds) / len(preds)
    conf = [(p >= 0.5) == bool(y) for _, p, y in preds if abs(p - 0.5) >= THRESHOLD]

    # 用全部樣本訓練，預測最新一天的隔日方向
    w = _fit([r[1] for r in labeled], [r[2] for r in labeled])
    d_last, x_last, _ = rows[-1]
    p = _prob(w, x_last)
    k_last = dates.index(d_last)
    return {
        "date": str(d_last),
        "p_up": round(p, 3),
        "view": "偏多" if p >= 0.5 + THRESHOLD else "偏空" if p <= 0.5 - THRESHOLD else "中性",
        "factors": [{"key": k, "name": name, "value": round(raw[k][k_last]),
                     "z": round(x_last[j], 2), "effect": round(w[j + 1] * x_last[j], 3)}
                    for j, (k, name) in enumerate(FEATURES)],
        "backtest": {
            "from": str(preds[0][0]), "to": str(preds[-1][0]), "n": len(preds),
            "acc": round(sum(hits) / len(hits), 3),
            "baseline": round(max(up_rate, 1 - up_rate), 3),
            "conf_n": len(conf), "conf_acc": round(sum(conf) / len(conf), 3) if conf else None,
        },
        "recent": [[str(d), round(p, 3), y] for d, p, y in preds[-10:]],
    }
