"""
資料完整性：check、collect --catch-up、history、export 的 status 共用同一張資料集表與同一套判斷。

一個資料集在某交易日「齊全」= 筆數 ≥ max(下限, 近 20 日中位數 × 80%)，且本益比類的三個欄位填充率都 ≥ 50%。
不齊全時：當天 22:00 前算「尚未公布」，之後算「異常」。
"""
import json
import statistics
import subprocess
import sys
from collections import namedtuple
from datetime import date, datetime, time, timedelta

from .config import LOG_DIR
from .tradingcal import load_closed, trading_days

COLLECT_FROM = time(15, 0)      # 當天資料最早的收集時間；之前「今天」不列入
DEADLINE = time(22, 0)          # 之前算尚未公布，之後算異常
ALERTS_SETTLED = time(19, 0)    # 處置／注意股當日公告大致底定的時間
COUNT_RATIO, FILL_MIN, MEDIAN_DAYS = 0.8, 0.5, 20
OK, PENDING, ABNORMAL = "ok", "pending", "abnormal"

Row = namedtuple("Row", "n pe pb dy", defaults=(0, 0, 0, 0))
Spec = namedtuple("Spec", "key label min_rows fills")
Item = namedtuple("Item", "key label date status n reason")
FILLS = (("pe", "本益比"), ("pb", "淨值比"), ("dy", "殖利率"))

SPECS = (
    Spec("prices.TWSE", "上市行情", 800, False), Spec("prices.TPEx", "上櫃行情", 650, False),
    Spec("pe.TWSE", "上市本益比", 800, True), Spec("pe.TPEx", "上櫃本益比", 650, True),
    Spec("insti.TWSE", "上市法人", 800, False), Spec("insti.TPEx", "上櫃法人", 550, False),
    Spec("amount", "上市法人金額", 6, False),
    Spec("index.TAIEX", "加權指數", 1, False), Spec("index.TPEX", "櫃買指數", 1, False),
    Spec("futures", "台指期", 1, False), Spec("futures_oi", "期貨法人", 9, False),
)
SPEC = {s.key: s for s in SPECS}

_MARKET_SQL = {
    "prices": "SELECT x.trade_date, s.market_type, COUNT(*), 0, 0, 0 FROM daily_prices x",
    "pe": "SELECT x.trade_date, s.market_type, COUNT(*), COUNT(x.pe_ratio), COUNT(x.pb_ratio), COUNT(x.dividend_yield) "
          "FROM stock_fundamentals x",
    "insti": "SELECT x.trade_date, s.market_type, COUNT(*), 0, 0, 0 FROM institutional_trades x",
}


def load_snapshot(cur, start: date, end: date) -> dict:
    """{鍵: {日期: Row}}，一個資料庫查詢一張表，不發外部請求。"""
    snap = {s.key: {} for s in SPECS}
    for name, sql in _MARKET_SQL.items():
        for d, market, n, pe, pb, dy in cur.execute(
                f"{sql} JOIN stocks s ON s.stock_id = x.stock_id WHERE x.trade_date BETWEEN ? AND ? "
                "GROUP BY x.trade_date, s.market_type", start, end).fetchall():
            snap[f"{name}.{market}"][d] = Row(n, pe, pb, dy)
    for d, code, n in cur.execute("SELECT trade_date, index_code, COUNT(*) FROM market_index "
                                  "WHERE trade_date BETWEEN ? AND ? GROUP BY trade_date, index_code", start, end).fetchall():
        snap[f"index.{code}"][d] = Row(n)
    for key, sql in (("amount", "SELECT trade_date, COUNT(*) FROM insti_amount WHERE trade_date BETWEEN ? AND ? GROUP BY trade_date"),
                     # 只看日盤：夜盤的日期是歸屬日，不代表該日資料已齊
                     ("futures", "SELECT trade_date, COUNT(*) FROM futures_daily_prices WHERE commodity_id = 'TX' AND session = 'DAY' "
                                 "AND trade_date BETWEEN ? AND ? GROUP BY trade_date"),
                     ("futures_oi", "SELECT trade_date, COUNT(*) FROM futures_institutional WHERE trade_date BETWEEN ? AND ? GROUP BY trade_date")):
        for d, n in cur.execute(sql, start, end).fetchall():
            snap[key][d] = Row(n)
    return snap


def medians(snap: dict) -> dict:
    """每個資料集最近 MEDIAN_DAYS 個有資料日期的筆數中位數；完全沒有資料為 0。"""
    out = {}
    for key, rows in snap.items():
        recent = [rows[d].n for d in sorted(rows)[-MEDIAN_DAYS:] if rows[d].n]
        out[key] = statistics.median(recent) if recent else 0
    return out


def assess(spec: Spec, row: Row, median: float):
    """齊全回傳 None；否則回傳 (種類, 說明)。種類：none 無資料 / count 筆數偏低 / fill:欄位 填充率偏低。"""
    if not row.n:
        return ("none", "無資料")
    need = max(spec.min_rows, median * COUNT_RATIO)
    if row.n < need:
        return ("count", f"筆數 {row.n:,}（近 {MEDIAN_DAYS} 日中位數 {median:,.0f}，門檻 {need:,.0f}）")
    if spec.fills:
        for f, label in FILLS:
            rate = getattr(row, f) / row.n
            if rate < FILL_MIN:
                return (f"fill:{label}", f"{label}填充率 {rate:.1%}（下限 {FILL_MIN:.0%}）")
    return None


def missing_keys(d: date, keys, snap: dict, med: dict) -> tuple:
    return tuple(k for k in keys if assess(SPEC[k], snap[k].get(d, Row()), med[k]))


def due_days(now: datetime, n: int, closed: set) -> list:
    """最近 n 個應該有資料的交易日（舊到新）；今天要過了 COLLECT_FROM 才算。"""
    today = now.date()
    last = today if now.time() >= COLLECT_FROM else today - timedelta(days=1)
    return trading_days(last - timedelta(days=n * 2 + 30), last, closed)[-n:]


def evaluate(days, snap: dict, now: datetime, errors=None) -> list:
    """每個資料集 × 每個交易日的狀態。errors = {(鍵, 日期) 或 鍵: 例外}：抓取失敗一律算異常，不論時間。"""
    errors, med, items = errors or {}, medians(snap), []
    for spec in SPECS:
        for d in days:
            row = snap[spec.key].get(d, Row())
            bad = assess(spec, row, med[spec.key])
            # (鍵, 日期)：這天抓取失敗；鍵：範圍查詢失敗（期貨、櫃買指數），只影響還缺資料的日期
            err = errors.get((spec.key, d)) or (errors.get(spec.key) if bad else None)
            if err is not None:
                items.append(Item(spec.key, spec.label, d, ABNORMAL, row.n, ("error", str(err))))
            elif bad is None:
                items.append(Item(spec.key, spec.label, d, OK, row.n, None))
            elif d == now.date() and now.time() < DEADLINE:
                items.append(Item(spec.key, spec.label, d, PENDING, row.n, bad))
            else:
                items.append(Item(spec.key, spec.label, d, ABNORMAL, row.n, bad))
    return items


def outcome(items) -> str:
    states = {i.status for i in items}
    return ABNORMAL if ABNORMAL in states else PENDING if PENDING in states else OK


def problem_lines(items) -> list:
    """把異常與尚未公布的項目彙總成一行一項（同資料集同原因合併）。"""
    groups = {}
    for i in items:
        if i.status != OK:
            groups.setdefault((i.status, i.key, i.reason[0]), []).append(i)
    lines = []
    for (status, _, kind), its in sorted(groups.items(), key=lambda g: (g[0][0] != ABNORMAL, list(SPEC).index(g[0][1]))):
        mark, label = ("❌", its[0].label) if status == ABNORMAL else ("⏳", its[0].label)
        days = [i.date for i in its]
        if status == PENDING:
            lines.append(f"{mark} {label}：{days[-1]} 尚未公布")
        elif kind == "none":
            lines.append(f"{mark} {label}：缺 " + "、".join(map(str, days[:8])) + (f" 等 {len(days)} 天" if len(days) > 8 else ""))
        elif len(days) == 1:
            lines.append(f"{mark} {label}：{days[0]} {its[0].reason[1]}")
        else:
            lines.append(f"{mark} {label}：{days[0]} ～ {days[-1]} 共 {len(days)} 天，最新 {its[-1].reason[1]}")
    return lines


# ─── 執行紀錄 ─────────────────────────────────────────────
def load_state(cur) -> dict:
    """由最近 200 筆執行紀錄整理：處置注意股、事件、營收最後成功的時間，與最後一次有新資料的時間。"""
    state = {"alerts_at": None, "events_to": None, "revenue_on": None, "collected_at": None}
    for finished, new_data, detail in cur.execute(
            "SELECT TOP 200 finished_at, new_data, detail FROM collect_runs ORDER BY run_id DESC").fetchall():
        if new_data and state["collected_at"] is None:
            state["collected_at"] = finished
        und = json.loads(detail).get("undated", {})
        if und.get("alerts") and state["alerts_at"] is None:
            state["alerts_at"] = datetime.fromisoformat(und["alerts"])
        if und.get("events_to") and state["events_to"] is None:
            state["events_to"] = date.fromisoformat(und["events_to"])
        if und.get("revenue") and state["revenue_on"] is None:
            state["revenue_on"] = date.fromisoformat(und["revenue"])
    return state


def write_run(cur, command, started, finished, result, new_data, requests, detail) -> int:
    """收集完成、匯出之前寫入（finished 也是這個時間），匯出才讀得到這次的「更新於」。回傳 run_id。"""
    return cur.execute("INSERT INTO collect_runs (command, started_at, finished_at, outcome, new_data, requests, detail) "
                       "OUTPUT INSERTED.run_id VALUES (?, ?, ?, ?, ?, ?, ?)", command, started.replace(tzinfo=None), finished.replace(tzinfo=None),
                       result, 1 if new_data else 0, requests, json.dumps(detail, ensure_ascii=False, default=str)).fetchone()[0]


def finish_run(cur, run_id, result, export_seconds) -> None:
    """匯出後補上結果（匯出失敗時 result 會變成異常）。不動 finished_at：它是網站「更新於」的依據，之後重新匯出也不可改變。"""
    cur.execute("UPDATE collect_runs SET outcome = ?, export_seconds = ? WHERE run_id = ?", result, export_seconds, run_id)


# ─── 通知（只有 Mac；同一天同一問題只通知一次）──────────────
NOTIFY_FILE = LOG_DIR / "notify_state.json"


def notify_once(problems, today: date) -> bool:
    """problems: {問題鍵: 說明}。回傳是否真的發了通知。"""
    if not problems or sys.platform != "darwin":
        return False
    try:
        state = json.loads(NOTIFY_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        state = {}
    seen = set(state.get("keys", [])) if state.get("date") == str(today) else set()
    new = {k: v for k, v in problems.items() if k not in seen}
    if not new:
        return False
    text = "；".join(list(new.values())[:3]).replace('"', "'").replace("\\", "")
    try:
        subprocess.run(["/usr/bin/osascript", "-e", f'display notification "{text}" with title "台股資料收集異常"'],
                       timeout=10, check=False)
    except (OSError, subprocess.SubprocessError) as e:
        print(f"  ⚠️  通知失敗：{e}")
    NOTIFY_FILE.parent.mkdir(parents=True, exist_ok=True)
    NOTIFY_FILE.write_text(json.dumps({"date": str(today), "keys": sorted(seen | set(new))}), encoding="utf-8")
    return True


# ─── check 指令 ───────────────────────────────────────────
def check_report(days, snap, now, state, closed, adhoc=()) -> tuple:
    """回傳 (輸出文字, 回傳碼)。純函式：不連資料庫、不發請求。"""
    items, med = evaluate(days, snap, now), medians(snap)
    out = [f"📋 資料完整性檢查：近 {len(days)} 個交易日 {days[0]} ～ {days[-1]}（現在 {now:%Y-%m-%d %H:%M}，台灣時間）"]
    if now.weekday() >= 5 or now.date() in closed:
        out.append(f"ℹ️  今天 {now.date()} 休市")
    if adhoc:
        out.append("ℹ️  臨時休市（自動判定，判定錯誤可用 collect --date 復原）：" + "、".join(map(str, adhoc)))
    out.append(f"\n{'資料集':<8}{'涵蓋':>7}{'最新日':>12}{'筆數':>7}{'中位數':>7}  本益比/淨值比/殖利率  狀態")
    mark = {OK: "✅ 正常", PENDING: "⏳ 尚未公布", ABNORMAL: "❌ 異常"}
    for spec in SPECS:
        mine = [i for i in items if i.key == spec.key]
        have = [i for i in mine if i.n]
        last = have[-1] if have else None
        fill = ""
        if spec.fills and last:
            r = snap[spec.key][last.date]
            fill = f"{r.pe / r.n:.0%} / {r.pb / r.n:.0%} / {r.dy / r.n:.0%}"
        worst = outcome(mine)
        out.append(f"{spec.label:<8}{len(have):>4}/{len(mine):<3}{str(last.date) if last else '--':>12}"
                   f"{last.n if last else 0:>7,}{med[spec.key]:>7,.0f}  {fill:<20}  {mark[worst]}")
    alerts = state.get("alerts_at")
    out.append(f"\n處置／注意股最後成功：{alerts:%Y-%m-%d %H:%M}" if alerts else "\n處置／注意股最後成功：尚無執行紀錄")
    lines = problem_lines(items)
    # 處置／注意股端點只有近幾日，錯過無法回補：落後 2 個交易日以上算異常；沒有紀錄不算（還沒跑過）
    stale = alerts and len(trading_days(alerts.date() + timedelta(days=1), days[-1], closed)) >= 2
    if stale:
        lines.insert(0, f"❌ 處置／注意股：最後成功 {alerts.date()}，端點只有近幾日，請盡快執行 collect --catch-up")
    abnormal = sum(ln.startswith("❌") for ln in lines)
    out += ["", *lines] if lines else []
    out.append(f"\n結果：異常 {abnormal} 項" if abnormal else "\n結果：無異常")
    return "\n".join(out), (1 if abnormal else 0)


def run_check(n: int, now: datetime) -> int:
    from . import db
    conn = db.connect()
    try:
        cur = conn.cursor()
        closed = load_closed(cur)
        days = due_days(now, n, closed)
        # 至少載入 MEDIAN_DAYS 個交易日，--days 小於 20 時中位數才有意義
        start = due_days(now, max(n, MEDIAN_DAYS), closed)[0]
        snap, state = load_snapshot(cur, start, days[-1]), load_state(cur)
        adhoc = [r[0] for r in cur.execute("SELECT holiday_date FROM market_holidays WHERE source = 'adhoc' AND holiday_date BETWEEN ? AND ? "
                                           "ORDER BY holiday_date", start, days[-1]).fetchall()]
    finally:
        conn.close()
    text, rc = check_report(days, snap, now, state, closed, adhoc)
    print(text)
    return rc


# ─── 匯出 latest.json 的 status ───────────────────────────
def collected_at(cur, state: dict) -> tuple:
    """(時間字串, 來源)：run = 執行紀錄；db = 尚無紀錄，退回日線最後寫入時間（換算成台灣時間）。"""
    if state["collected_at"]:
        return state["collected_at"].isoformat(timespec="seconds") + "+08:00", "run"
    t = cur.execute("SELECT DATEADD(hour, 8 - DATEDIFF(hour, GETUTCDATE(), GETDATE()), MAX(created_at)) FROM daily_prices").fetchone()[0]
    return (t.isoformat(timespec="seconds") + "+08:00", "db") if t else (None, "db")


def dataset_status(snap: dict, data_date: date, now: datetime) -> list:
    """以「資料日」為基準判斷各資料集（整站落後由橫幅處理）；m 只在異常時有。"""
    med, out = medians(snap), []
    for spec in SPECS:
        rows = snap[spec.key]
        bad = assess(spec, rows.get(data_date, Row()), med[spec.key])
        good = [d for d in sorted(rows) if not assess(spec, rows[d], med[spec.key])]
        last = good[-1] if good else None
        item = {"k": spec.key, "n": spec.label, "d": str(last) if last else None, "s": OK}
        if bad:
            item["s"] = PENDING if data_date == now.date() and now.time() < DEADLINE else ABNORMAL
        if item["s"] == ABNORMAL:
            if bad[0].startswith("fill"):
                item["m"] = f"{spec.label} {data_date:%m/%d} {bad[1].split('（')[0]}"
            else:
                item["m"] = f"{spec.label}停在 {last:%m/%d}" if last else f"{spec.label}近期資料不足"
        out.append(item)
    return out


def site_closed(closed, data_date: date) -> list:
    """網站判斷「最新交易日」用的休市日：只列平日；往回 45 天夠找到上一個交易日。"""
    return sorted(str(d) for d in closed if d.weekday() < 5 and d >= data_date - timedelta(days=45))


def build_status(cur, data_date: date, now: datetime) -> dict:
    closed, state = load_closed(cur), load_state(cur)
    at, src = collected_at(cur, state)
    snap = load_snapshot(cur, data_date - timedelta(days=45), data_date)
    return {"collected_at": at, "collected_src": src, "exported_at": now.isoformat(timespec="seconds"),
            "datasets": dataset_status(snap, data_date, now),
            "closed": site_closed(closed, data_date)}
