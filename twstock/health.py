"""
資料完整性：check、collect --catch-up、history、export 的 status 共用同一張資料集表與同一套判斷。

一個資料集在某交易日「齊全」= 筆數 ≥ max(下限, 近 20 日中位數 × 80%)，且本益比類的三個欄位填充率都 ≥ 50%。
不齊全時：公布日 22:00 前算「尚未公布」，之後算「異常」。公布日通常是當天；跨境 ETF 持股落後 1 個交易日（delay）。
since 之前的日期不算缺（ETF 上市前、開始收集前）。
"""
import json
import statistics
import subprocess
import sys
from collections import namedtuple
from datetime import date, datetime, time, timedelta
from pathlib import Path

from .config import LOG_DIR
from .tradingcal import load_closed, trading_days

COLLECT_FROM = time(15, 0)      # 當天資料最早的收集時間；之前「今天」不列入
DEADLINE = time(22, 0)          # 之前算尚未公布，之後算異常
ALERTS_SETTLED = time(19, 0)    # 處置／注意股當日公告大致底定的時間
COUNT_RATIO, FILL_MIN, MEDIAN_DAYS = 0.8, 0.5, 20
OK, PENDING, ABNORMAL = "ok", "pending", "abnormal"

Row = namedtuple("Row", "n pe pb dy gap", defaults=(0, 0, 0, 0, None))     # gap：投信確定沒有明細（A／B），算齊全
Spec = namedtuple("Spec", "key label min_rows fills since delay", defaults=(None, 0))
Fund = namedtuple("Fund", "fund delay since trust")
Item = namedtuple("Item", "key label date status n reason")
FILLS = (("pe", "本益比"), ("pb", "淨值比"), ("dy", "殖利率"))

# 主動型 ETF 持股（第 5 輪統一、第 7 輪群益）：代號 → Fund(投信的基金代碼, 持股公布落後的交易日數, 上市日, 投信)
# 上市日 = etf_daily 最早一筆（2025-10-30 之前上市的填 None）；跨境 ETF 的持股日是前一個交易日
HOLDINGS = {"00981A": Fund("49YTW", 0, None, "統一"), "00403A": Fund("63YTW", 0, date(2026, 5, 12), "統一"),
            "00411A": Fund("64YTW", 1, date(2026, 8, 26), "統一"), "00988A": Fund("61YTW", 1, date(2025, 11, 5), "統一"),
            "00982A": Fund("399", 0, None, "群益"), "00992A": Fund("500", 0, date(2025, 12, 30), "群益"),
            "00415A": Fund("504", 0, date(2026, 10, 20), "群益"), "00997A": Fund("502", 1, date(2026, 4, 14), "群益")}
BREADTH_FROM = date(2026, 11, 3)        # 官方漲跌家數不補歷史，從這天開始收集
AMOUNT_TPEX_FROM = date(2026, 7, 31)    # 上櫃官方法人金額（第 9 輪）：和上市 insti_amount 同一個起點
REVENUE_DONE_RATIO = 0.98               # 月營收：該月家數 ≥ 前一月 × 98% 視為公布完成（catchup 共用）
REVENUE_DUE_DAY = 10                    # 月營收法定公布期限：每月 10 日

SPECS = (
    Spec("prices.TWSE", "上市行情", 800, False), Spec("prices.TPEx", "上櫃行情", 650, False),
    Spec("pe.TWSE", "上市本益比", 800, True), Spec("pe.TPEx", "上櫃本益比", 650, True),
    Spec("insti.TWSE", "上市法人", 800, False), Spec("insti.TPEx", "上櫃法人", 550, False),
    Spec("amount", "上市法人金額", 6, False), Spec("amount.TPEx", "上櫃法人金額", 6, False, AMOUNT_TPEX_FROM),
    Spec("index.TAIEX", "加權指數", 1, False), Spec("index.TPEX", "櫃買指數", 1, False),
    Spec("futures", "台指期", 1, False), Spec("futures_oi", "期貨法人", 9, False),
    Spec("etf.TWSE", "上市ETF", 150, False), Spec("etf.TPEx", "上櫃ETF", 80, False),
    Spec("margin.TWSE", "上市融資融券", 800, False), Spec("margin.TPEx", "上櫃融資融券", 550, False),
    Spec("breadth.TWSE", "上市漲跌家數", 1, False, BREADTH_FROM), Spec("breadth.TPEx", "上櫃漲跌家數", 1, False, BREADTH_FROM),
) + tuple(Spec(f"holdings.{c}", f"{c}持股", 1, False, f.since, f.delay) for c, f in HOLDINGS.items())
SPEC = {s.key: s for s in SPECS}

_MARKET_SQL = {
    "prices": "SELECT x.trade_date, s.market_type, COUNT(*), 0, 0, 0 FROM daily_prices x",
    "pe": "SELECT x.trade_date, s.market_type, COUNT(*), COUNT(x.pe_ratio), COUNT(x.pb_ratio), COUNT(x.dividend_yield) "
          "FROM stock_fundamentals x",
    "insti": "SELECT x.trade_date, s.market_type, COUNT(*), 0, 0, 0 FROM institutional_trades x",
    "margin": "SELECT x.trade_date, s.market_type, COUNT(*), 0, 0, 0 FROM margin_trades x",
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
    for d, market, n in cur.execute("SELECT x.trade_date, e.market_type, COUNT(*) FROM etf_daily x JOIN etfs e ON e.etf_id = x.etf_id "
                                    "WHERE x.trade_date BETWEEN ? AND ? GROUP BY x.trade_date, e.market_type", start, end).fetchall():
        snap[f"etf.{market}"][d] = Row(n)
    # 持股筆數 = 股票檔數（期貨不算）
    for d, code, n in cur.execute("SELECT h.hold_date, e.etf_code, COUNT(*) FROM etf_holdings h JOIN etfs e ON e.etf_id = h.etf_id "
                                  "WHERE h.asset_type = 'ST' AND h.hold_date BETWEEN ? AND ? GROUP BY h.hold_date, e.etf_code",
                                  start, end).fetchall():
        if f"holdings.{code}" in snap:
            snap[f"holdings.{code}"][d] = Row(n)
    for d, code, reason in cur.execute("SELECT g.hold_date, e.etf_code, g.reason FROM etf_holding_gaps g JOIN etfs e ON e.etf_id = g.etf_id "
                                       "WHERE g.hold_date BETWEEN ? AND ?", start, end).fetchall():
        if f"holdings.{code}" in snap:
            snap[f"holdings.{code}"].setdefault(d, Row(gap=reason))
    for d, market, n in cur.execute("SELECT trade_date, market, COUNT(*) FROM market_breadth WHERE trade_date BETWEEN ? AND ? "
                                    "GROUP BY trade_date, market", start, end).fetchall():
        snap[f"breadth.{market}"][d] = Row(n)
    for key, sql in (("amount", "SELECT trade_date, COUNT(*) FROM insti_amount WHERE market = 'TWSE' AND trade_date BETWEEN ? AND ? GROUP BY trade_date"),
                     ("amount.TPEx", "SELECT trade_date, COUNT(*) FROM insti_amount WHERE market = 'TPEx' AND trade_date BETWEEN ? AND ? GROUP BY trade_date"),
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
    if row.gap:
        return None                     # 來源確定沒有：不算缺
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


def is_due(spec: Spec, d: date, days=None) -> bool:
    """這天該不該有資料：since 之前不算；delay > 0 要等 days（交易日，舊到新）裡再過 delay 天才公布。days=None 不看 delay。"""
    if spec.since and d < spec.since:
        return False
    return not spec.delay or days is None or (d in days and days.index(d) + spec.delay < len(days))


def missing_keys(d: date, keys, snap: dict, med: dict, days=None) -> tuple:
    return tuple(k for k in keys if is_due(SPEC[k], d, days) and assess(SPEC[k], snap[k].get(d, Row()), med[k]))


def due_days(now: datetime, n: int, closed: set) -> list:
    """最近 n 個應該有資料的交易日（舊到新）；今天要過了 COLLECT_FROM 才算。"""
    today = now.date()
    last = today if now.time() >= COLLECT_FROM else today - timedelta(days=1)
    return trading_days(last - timedelta(days=n * 2 + 30), last, closed)[-n:]


def evaluate(days, snap: dict, now: datetime, errors=None) -> list:
    """每個資料集 × 每個交易日的狀態。errors = {(鍵, 日期) 或 鍵: 例外}：抓取失敗一律算異常，不論時間。"""
    errors, med, items = errors or {}, medians(snap), []
    for spec in SPECS:
        for i, d in enumerate(days):
            if not is_due(spec, d, days):
                continue
            row = snap[spec.key].get(d, Row())
            bad = assess(spec, row, med[spec.key])
            # (鍵, 日期)：這天抓取失敗；鍵：範圍查詢失敗（期貨、櫃買指數），只影響還缺資料的日期
            err = errors.get((spec.key, d)) or (errors.get(spec.key) if bad else None)
            if err is not None:
                items.append(Item(spec.key, spec.label, d, ABNORMAL, row.n, ("error", str(err))))
            elif bad is None:
                items.append(Item(spec.key, spec.label, d, OK, row.n, None))
            elif days[i + spec.delay] == now.date() and now.time() < DEADLINE:    # 公布日當天
                items.append(Item(spec.key, spec.label, d, PENDING, row.n, bad))
            else:
                items.append(Item(spec.key, spec.label, d, ABNORMAL, row.n, bad))
    return items


def outcome(items) -> str:
    states = {i.status for i in items}
    return ABNORMAL if ABNORMAL in states else PENDING if PENDING in states else OK


def _day_list(days) -> str:
    return "、".join(map(str, days[:8])) + (f" 等 {len(days)} 天" if len(days) > 8 else "")


def all_missing_days(items) -> list:
    """
    當天公布的資料集全部「異常且 0 筆」的交易日（整天沒有收集）；休市日本來就不在 items 裡。
    落後公布的持股（delay）是隔天才收，不列入判斷。
    """
    by_day = {}
    for i in items:
        if not SPEC[i.key].delay:
            by_day.setdefault(i.date, []).append(i)
    return sorted(d for d, its in by_day.items()
                  if len(its) == sum(is_due(s, d) for s in SPECS if not s.delay) and all(i.status == ABNORMAL and not i.n for i in its))


def problem_lines(items, last_run=None) -> list:
    """把異常與尚未公布的項目彙總成一行一項（同資料集同原因合併）；整天所有資料集都缺的日子合併成一行。"""
    whole = all_missing_days(items)
    lines = []
    if whole:
        why = ""
        if last_run:
            at = last_run["at"]
            why = (f"：最後一次收集是 {at:%m/%d %H:%M}，之後沒有執行收集"
                   if at < datetime.combine(whole[-1], COLLECT_FROM) else f"：最後一次收集 {at:%m/%d %H:%M} 也沒有取得")
        lines.append(f"❌ {_day_list(whole)} 全部資料集都沒有{why}")
    groups = {}
    for i in items:
        if i.status != OK and i.date not in whole:
            groups.setdefault((i.status, i.key, i.reason[0]), []).append(i)
    for (status, _, kind), its in sorted(groups.items(), key=lambda g: (g[0][0] != ABNORMAL, list(SPEC).index(g[0][1]))):
        mark, label = ("❌", its[0].label) if status == ABNORMAL else ("⏳", its[0].label)
        days = [i.date for i in its]
        if status == PENDING:
            lines.append(f"{mark} {label}：{days[-1]} 尚未公布")
        elif kind == "none":
            lines.append(f"{mark} {label}：缺 " + _day_list(days))
        elif len(days) == 1:
            lines.append(f"{mark} {label}：{days[0]} {its[0].reason[1]}")
        else:
            lines.append(f"{mark} {label}：{days[0]} ～ {days[-1]} 共 {len(days)} 天，最新 {its[-1].reason[1]}")
    return lines


# ─── 執行紀錄 ─────────────────────────────────────────────
def load_state(cur) -> dict:
    """
    由最近 200 筆執行紀錄整理：處置注意股、事件、營收最後成功的時間，最後一次有新資料的時間，
    與最後一次收集（last_run：時間、指令、有無新資料）。
    """
    state = {"alerts_at": None, "events_to": None, "revenue_on": None, "collected_at": None, "last_run": None}
    for finished, new_data, detail, *extra in cur.execute(
            "SELECT TOP 200 finished_at, new_data, detail, command FROM collect_runs ORDER BY run_id DESC").fetchall():
        if state["last_run"] is None:
            state["last_run"] = {"at": finished, "command": extra[0] if extra else None, "new_data": bool(new_data)}
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
PLIST = Path("Library/LaunchAgents/com.twstock.collect.plist")      # 相對於使用者家目錄
RUN_LABEL = {"catch-up": "collect --catch-up", "date": "collect --date"}
CATCHUP_DAYS, CATCHUP_MAX = 10, 30      # 與 collectors.catchup 的 DEFAULT_DAYS、MAX_DAYS 相同（health 不匯入 collectors）


def schedule_status(platform=None, home=None) -> str:
    """只看排程檔是否存在（唯讀，不呼叫 launchctl／schtasks）。"""
    if (platform or sys.platform) != "darwin":
        return "無法判斷，請在工作排程器確認"
    path = Path(home or Path.home()) / PLIST
    return f"已安裝（{path}）" if path.exists() else "未安裝（安裝方式見 README，由使用者自行執行）"


def last_run_line(run) -> str:
    if not run:
        return "尚無執行紀錄"
    what = RUN_LABEL.get(run["command"], "收集")
    return f"{run['at']:%Y-%m-%d %H:%M}（{what}，{'有新資料' if run['new_data'] else '沒有新資料'}）"


def suggest(items, days, stale_alerts) -> str:
    """有異常時的建議指令：缺口在 --catch-up 預設範圍內 → collect --catch-up；30 天內 → 加 --days；更早 → history。"""
    bad = sorted({i.date for i in items if i.status == ABNORMAL})
    if not bad and not stale_alerts:
        return ""
    n = len(days) - days.index(bad[0]) if bad else 1
    if n <= CATCHUP_DAYS:
        return "👉 請執行 python3 -m twstock collect --catch-up"
    if n <= CATCHUP_MAX:
        return f"👉 請執行 python3 -m twstock collect --catch-up --days {n}"
    return f"👉 請執行 python3 -m twstock history --start {bad[0]}，再執行 python3 -m twstock collect --catch-up"


def revenue_status(today: date, counts: dict, revenue_on, closed) -> tuple:
    """
    月營收一行（第 9 輪 B15）：(狀態, 文字)。counts = {(年, 月): 家數}；revenue_on = 最後一次成功收集營收的日期。
    ✅ 該月家數 ≥ 前一月 × 98%；⏳ 未達且今天 ≤ 10 日（公布期間），或已過 10 日但 revenue_on 是今天或前一個交易日；
    ❌ 其餘（已過 10 日、收集停了）。月份 = 今天的上一個月（與 collectors.revenue.revenue_month_for 相同）。
    """
    y, m = (today.year - 1, 12) if today.month == 1 else (today.year, today.month - 1)
    prev = counts.get((y - 1, 12) if m == 1 else (y, m - 1), 0)
    n = counts.get((y, m), 0)
    head = f"月營收 {y}/{m:02d}：已收 {n:,} 家" + (f"（前一月 {prev:,} 家的 {n / prev:.0%}）" if prev else "")
    if n and n >= prev * REVENUE_DONE_RATIO:
        return OK, f"{head}，✅ 已齊"
    if today.day <= REVENUE_DUE_DAY:
        return PENDING, f"{head}，⏳ 公布期間（每月 {REVENUE_DUE_DAY} 日前）"
    before = trading_days(today - timedelta(days=30), today - timedelta(days=1), closed)
    if revenue_on and (revenue_on >= today or (before and revenue_on >= before[-1])):
        return PENDING, f"{head}，⏳ 晚交公司陸續補進（最後收集 {revenue_on:%m/%d}）"
    return ABNORMAL, f"{head}，最後一次收集營收 {revenue_on or '尚無紀錄'}"


def check_report(days, snap, now, state, closed, adhoc=(), schedule=None, revenue=None) -> tuple:
    """回傳 (輸出文字, 回傳碼)。純函式：不連資料庫、不發請求；schedule 由呼叫端傳入（schedule_status()）；revenue = 各月營收家數（None 不印營收一行）。"""
    items, med = evaluate(days, snap, now), medians(snap)
    out = [f"📋 資料完整性檢查：近 {len(days)} 個交易日 {days[0]} ～ {days[-1]}（現在 {now:%Y-%m-%d %H:%M}，台灣時間）",
           f"🕘 最後一次收集：{last_run_line(state.get('last_run'))}"]
    if schedule:
        out.append(f"🗓️  排程：{schedule}")
    if now.weekday() >= 5 or now.date() in closed:
        out.append(f"ℹ️  今天 {now.date()} 休市")
    if adhoc:
        out.append("ℹ️  臨時休市（自動判定，判定錯誤可用 collect --date 復原）：" + "、".join(map(str, adhoc)))
    out.append(f"\n{'資料集':<8}{'涵蓋':>7}{'最新日':>12}{'筆數':>7}{'中位數':>7}  本益比/淨值比/殖利率  狀態")
    mark = {OK: "✅ 正常", PENDING: "⏳ 尚未公布", ABNORMAL: "❌ 異常"}
    gaps = []
    for spec in SPECS:
        mine = [i for i in items if i.key == spec.key]
        have = [i for i in mine if i.n]
        last = have[-1] if have else None
        fill = ""
        if spec.fills and last:
            r = snap[spec.key][last.date]
            fill = f"{r.pe / r.n:.0%} / {r.pb / r.n:.0%} / {r.dy / r.n:.0%}"
        worst = outcome(mine)
        gaps += [(spec.label, i.date, snap[spec.key][i.date].gap) for i in mine if snap[spec.key].get(i.date, Row()).gap]
        out.append(f"{spec.label:<8}{len(have) + sum(g[0] == spec.label for g in gaps):>4}/{len(mine):<3}{str(last.date) if last else '--':>12}"
                   f"{last.n if last else 0:>7,}{med[spec.key]:>7,.0f}  {fill:<20}  {mark[worst]}")
    if gaps:
        out.append("ℹ️  投信沒有持股明細（不算缺）：" + "、".join(f"{label} {d}（{'無持股清單' if r == 'A' else '只有彙總'}）"
                                                    for label, d, r in gaps))
    alerts = state.get("alerts_at")
    out.append(f"\n處置／注意股最後成功：{alerts:%Y-%m-%d %H:%M}" if alerts else "\n處置／注意股最後成功：尚無執行紀錄")
    rev = revenue_status(now.date(), revenue, state.get("revenue_on"), closed) if revenue is not None else None
    if rev:
        out.append(rev[1] if rev[0] != ABNORMAL else f"{rev[1]}，❌ 異常")
    lines = problem_lines(items, state.get("last_run"))
    # 處置／注意股端點只有近幾日，錯過無法回補：落後 2 個交易日以上算異常；沒有紀錄不算（還沒跑過）
    stale = alerts and len(trading_days(alerts.date() + timedelta(days=1), days[-1], closed)) >= 2
    if stale:
        lines.insert(0, f"❌ 處置／注意股：最後成功 {alerts.date()}，端點只有近幾日，請盡快執行 collect --catch-up")
    if rev and rev[0] == ABNORMAL:
        lines.append(f"❌ {rev[1]}：已過 {REVENUE_DUE_DAY} 日仍未收齊，收集可能停了")
    abnormal = sum(ln.startswith("❌") for ln in lines)
    out += ["", *lines] if lines else []
    out.append(f"\n結果：異常 {abnormal} 項" if abnormal else "\n結果：無異常")
    if abnormal:
        out.append(suggest(items, days, bool(stale) or bool(rev and rev[0] == ABNORMAL)))
    return "\n".join(out), (1 if abnormal else 0)


def revenue_counts(cur) -> dict:
    """{(年, 月): 家數}；SQL 與 collectors.catchup._revenue_counts 相同。"""
    return {(y, m): n for y, m, n in cur.execute(
        "SELECT revenue_year, revenue_month, COUNT(*) FROM monthly_revenue GROUP BY revenue_year, revenue_month").fetchall()}


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
        revenue = revenue_counts(cur)
        adhoc = [r[0] for r in cur.execute("SELECT holiday_date FROM market_holidays WHERE source = 'adhoc' AND holiday_date BETWEEN ? AND ? "
                                           "ORDER BY holiday_date", start, days[-1]).fetchall()]
    finally:
        conn.close()
    text, rc = check_report(days, snap, now, state, closed, adhoc, schedule_status(), revenue)
    print(text)
    return rc


# ─── 匯出 latest.json 的 status ───────────────────────────
def collected_at(cur, state: dict) -> tuple:
    """(時間字串, 來源)：run = 執行紀錄；db = 尚無紀錄，退回日線最後寫入時間（換算成台灣時間）。"""
    if state["collected_at"]:
        return state["collected_at"].isoformat(timespec="seconds") + "+08:00", "run"
    t = cur.execute("SELECT DATEADD(hour, 8 - DATEDIFF(hour, GETUTCDATE(), GETDATE()), MAX(created_at)) FROM daily_prices").fetchone()[0]
    return (t.isoformat(timespec="seconds") + "+08:00", "db") if t else (None, "db")


def dataset_status(snap: dict, data_date: date, now: datetime, closed=None) -> list:
    """
    以「資料日」為基準判斷各資料集（整站落後由橫幅處理）；m 只在異常時有。
    落後公布的持股（delay）看資料日往前 delay 個交易日（closed = 休市日；未提供時只排除週末與內建休市表）。
    """
    med, out = medians(snap), []
    days = trading_days(data_date - timedelta(days=45), data_date, closed)
    for spec in SPECS:
        target = days[-1 - spec.delay] if spec.delay else data_date
        if not is_due(spec, target):
            continue
        rows = snap[spec.key]
        bad = assess(spec, rows.get(target, Row()), med[spec.key])
        good = [d for d in sorted(rows) if not assess(spec, rows[d], med[spec.key])]
        last = good[-1] if good else None
        item = {"k": spec.key, "n": spec.label, "d": str(last) if last else None, "s": OK}
        if bad:
            item["s"] = PENDING if data_date == now.date() and now.time() < DEADLINE else ABNORMAL
        if item["s"] == ABNORMAL:
            if bad[0].startswith("fill"):
                item["m"] = f"{spec.label} {target:%m/%d} {bad[1].split('（')[0]}"
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
            "datasets": dataset_status(snap, data_date, now, closed),
            "closed": site_closed(closed, data_date)}
