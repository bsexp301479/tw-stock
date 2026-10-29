"""
板塊資金流向（四象限：漲潮 / 輪動 / 觀望 / 退潮）。

每檔法人買賣超金額 ≈ 三大法人買賣超股數 × 收盤價
板塊每日淨流入 = 板塊內個股加總
X = 近 5 日累計淨流入（億）               → 錢「在不在」這個板塊
Y = 近 5 日平均 − 近 20 日平均（億/天）    → 流入在「加速」還是「放緩」
"""
import csv

from ..config import DATA_DIR

SHORT, LONG = 5, 20


def quadrant(x: float, y: float) -> str:
    if x >= 0:
        return "漲潮" if y >= 0 else "輪動"
    return "觀望" if y >= 0 else "退潮"


def load_concepts() -> dict:
    """concepts.csv → {概念: [代號...]}；一檔可屬於多個概念，# 開頭為註解。"""
    groups = {}
    with open(DATA_DIR / "concepts.csv", encoding="utf-8") as f:
        rows = csv.DictReader(line for line in f if not line.lstrip().startswith("#"))
        for r in rows:
            code, concept = r["code"].strip(), r["concept"].strip()
            if code and concept and code not in groups.setdefault(concept, []):
                groups[concept].append(code)
    return groups


def streak(values: list) -> int:
    """連續同向天數：最近連續買超 n 天回傳 n，連續賣超回傳 -n。"""
    n = 0
    for v in reversed(values):
        if not v:
            break
        if n == 0 or (v > 0) == (n > 0):
            n += 1 if v > 0 else -1
        else:
            break
    return n


def group_flows(groups: dict, daily: dict, dates: list, replay: int) -> list:
    """
    groups: {板塊: [代號...]}
    daily:  {代號: {日期: {"net": 億, "turnover": 億, "pct": %}}}
    dates:  由舊到新的交易日（至少 replay + LONG - 1 天）
    回傳每個板塊的最新指標，以及最近 replay 天的 (x, y, 漲跌%, 成交額) 供泡泡圖回放。
    """
    out = []
    for name, codes in groups.items():
        codes = [c for c in codes if c in daily]
        if not codes:
            continue
        net, turnover, pct = [], [], []
        for d in dates:
            n = t = w = 0.0
            for c in codes:
                r = daily[c].get(d)
                if r:
                    n += r["net"]
                    t += r["turnover"]
                    w += (r["pct"] or 0) * r["turnover"]
            net.append(n)
            turnover.append(t)
            pct.append(w / t if t else 0.0)   # 成交金額加權漲跌幅

        frames = []
        for i in range(len(dates) - replay, len(dates)):
            if i < LONG - 1:
                frames.append(None)
                continue
            x = sum(net[i - SHORT + 1:i + 1])
            y = x / SHORT - sum(net[i - LONG + 1:i + 1]) / LONG
            frames.append([round(x, 2), round(y, 2), round(pct[i], 2), round(turnover[i], 1)])

        last = frames[-1] or [0, 0, 0, 0]
        out.append({
            "name": name,
            "codes": codes,
            "net_1d": round(net[-1], 2),
            "net_5d": round(sum(net[-SHORT:]), 2),
            "net_20d": round(sum(net[-LONG:]), 2),
            "chg_1d": round(pct[-1], 2),
            "turnover": round(turnover[-1], 1),
            "streak": streak(net),
            "quadrant": quadrant(last[0], last[1]),
            "flows": [round(v, 2) for v in net[-LONG:]],
            "frames": frames,
        })
    out.sort(key=lambda g: g["net_5d"], reverse=True)
    return out
