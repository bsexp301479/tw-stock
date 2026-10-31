"""
collect --catch-up：找出最近 N 個交易日各資料集缺什麼，只補缺的，可一天重複執行。
collect --date：指定日期全部重抓（MERGE 覆寫），與 catch-up 共用同一個執行流程。

流程：取得鎖 → 更新日曆 → 規劃（純函式 make_plan）→ 依序抓取 → 重新讀資料庫判斷狀態 → 需要時匯出 → 寫紀錄 → 通知。
結束代碼：0 = 齊全、尚未公布、休市或另一個程序正在執行；1 = 有異常；2 = 連不上資料庫。
"""
import json
import time
from datetime import date, datetime, timedelta

import pyodbc

from .. import db, fetch, health
from ..config import DB_CONFIG, SITE_DATA_DIR, tw_now
from ..fetch import FetchError
from ..health import Row, due_days, evaluate, load_snapshot, load_state, medians, missing_keys
from ..tradingcal import (add_adhoc, is_adhoc_closure, is_trading_day, load_closed, remove_adhoc, trading_days,
                          update_calendar, warn_uncovered)
from .alerts import collect_alerts
from .chains import chains_age_days, update_chains
from .daily import DAY_KEYS, PARSE_ERRORS, collect_for_date, collect_tpex_index
from .events import LOOKBACK_DAYS, collect_events
from .futures import collect_futures, collect_futures_institutional
from .industry import update_industry
from .revenue import collect_monthly_revenue, revenue_month_for

DEFAULT_DAYS, MAX_DAYS = 10, 30
CHAINS_REFRESH_DAYS = 30
DB_RETRY_SECONDS = 60       # 開機登入時 Docker 可能還沒起來，等一下再試一次
REVENUE_DONE_RATIO = 0.98   # 該月筆數 ≥ 前一月 × 98% 視為公布完成


def month_key(d: date) -> tuple:
    return d.year, d.month


def make_plan(now: datetime, n: int, snap: dict, state: dict, closed: set, revenue_counts=None) -> dict:
    """
    純函式：輸入現在時間、資料現況、執行紀錄、日曆；輸出待抓清單（不連網、不連資料庫）。
    days：評估範圍；by_date：[(日期, 鍵)]；tpex_months；futures、futures_oi：(起, 迄)；alerts：bool；
    events：(起, 迄)；revenue：[(年, 月)]。
    """
    days = due_days(now, n, closed)
    plan = {"days": days, "by_date": [], "tpex_months": [], "futures": None, "futures_oi": None,
            "alerts": False, "events": None, "revenue": []}
    if not days:
        return plan
    med = medians(snap)
    for d in days:
        keys = missing_keys(d, DAY_KEYS, snap, med)
        if keys:
            plan["by_date"].append((d, keys))
    plan["tpex_months"] = sorted({month_key(d) for d in days if missing_keys(d, ("index.TPEX",), snap, med)})
    for key in ("futures", "futures_oi"):
        gap = [d for d in days if missing_keys(d, (key,), snap, med)]
        if gap:
            plan[key] = (gap[0], gap[-1])

    # 沒有日期的資料：以「最後一個應有資料的交易日」為基準
    anchor = days[-1]
    settled = datetime.combine(anchor, health.ALERTS_SETTLED)
    first = datetime.combine(anchor, health.COLLECT_FROM)
    need_after = settled if now.replace(tzinfo=None) >= settled else first
    plan["alerts"] = state["alerts_at"] is None or state["alerts_at"].replace(tzinfo=None) < need_after
    if state["events_to"] is None or state["events_to"] < anchor:
        oldest = plan["by_date"][0][0] if plan["by_date"] else anchor
        since = min(oldest, state["events_to"] or anchor)
        plan["events"] = (since - timedelta(days=LOOKBACK_DAYS), anchor)
    if state["revenue_on"] != now.date() and revenue_counts is not None:
        for y, m in sorted({x for x in map(revenue_month_for, days) if x}):
            prev = (y - 1, 12) if m == 1 else (y, m - 1)
            if revenue_counts.get((y, m), 0) < revenue_counts.get(prev, 0) * REVENUE_DONE_RATIO or not revenue_counts.get((y, m)):
                plan["revenue"].append((y, m))
    return plan


def plan_for_date(d: date, now: datetime, closed_by_calendar: bool) -> dict:
    """collect --date：該日全部重抓；行事曆上的休市日只處理沒有日期的資料。"""
    plan = {"days": [] if closed_by_calendar else [d], "by_date": [] if closed_by_calendar else [(d, DAY_KEYS)],
            "tpex_months": [] if closed_by_calendar else [month_key(d)],
            "futures": None if closed_by_calendar else (d, d), "futures_oi": None if closed_by_calendar else (d, d),
            "alerts": not closed_by_calendar, "events": None if closed_by_calendar else (d - timedelta(days=LOOKBACK_DAYS), d),
            "revenue": []}
    month = revenue_month_for(d)
    if month and not closed_by_calendar:
        plan["revenue"] = [month]
    return plan


def plan_is_empty(plan: dict) -> bool:
    return not (plan["by_date"] or plan["tpex_months"] or plan["futures"] or plan["futures_oi"]
                or plan["alerts"] or plan["events"] or plan["revenue"])


def _guard(key, errors, fn, *args):
    """跑一個資料集；抓取失敗或欄位不符只記錄，不影響其他資料集。回傳 True = 成功。"""
    try:
        fn(*args)
        return True
    except (FetchError, RuntimeError, *PARSE_ERRORS) as e:     # RuntimeError：update_chains 解析不到產業鏈
        errors[key] = e
        print(f"  ⚠️  {key} 失敗：{e}")
        return False


def execute_plan(plan: dict, now: datetime, no_revenue=False) -> tuple:
    """依序抓取；回傳 (written, errors, undated)。written = {鍵: {日期字串: 筆數}}。"""
    written, errors, undated = {}, {}, {}
    wrote_prices = False
    for d, keys in plan["by_date"]:
        w, e = collect_for_date(d, keys)
        for k, v in w.items():
            written.setdefault(k, {})[str(d)] = v
        errors.update({(k, d): x for k, x in e.items()})
        wrote_prices = wrote_prices or any(k.startswith("prices.") and v for k, v in w.items())
    if plan["futures"]:
        _guard("futures", errors, collect_futures, *plan["futures"])
    if plan["futures_oi"]:
        _guard("futures_oi", errors, collect_futures_institutional, *plan["futures_oi"])
    for y, m in plan["tpex_months"]:
        _guard("index.TPEX", errors, collect_tpex_index, y, m)
    if plan["alerts"] and _guard("alerts", errors, collect_alerts):
        undated["alerts"] = now.isoformat(timespec="seconds")
    if plan["events"] and _guard("events", errors, collect_events, *plan["events"]):
        undated["events_to"] = str(plan["events"][1])
    if plan["revenue"] and not no_revenue:
        if all([_guard("revenue", errors, collect_monthly_revenue, y, m) for y, m in plan["revenue"]]):
            undated["revenue"] = str(now.date())
    if wrote_prices:        # 新股票要有產業別；產業鏈 30 天更新一次
        _guard("industry", errors, update_industry)
        age = chains_age_days()
        if age is None or age >= CHAINS_REFRESH_DAYS:
            _guard("chains", errors, update_chains)
    return written, errors, undated


def _undated_counts(cur) -> tuple:
    return tuple(cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("stock_alerts", "price_events", "monthly_revenue"))


def _revenue_counts(cur) -> dict:
    return {(y, m): n for y, m, n in cur.execute(
        "SELECT revenue_year, revenue_month, COUNT(*) FROM monthly_revenue GROUP BY revenue_year, revenue_month").fetchall()}


def status_changed(status_now: list, closed_now=None) -> bool:
    """網站上的 status 與現況不同（尚未公布轉異常、登記臨時休市、官方休市表更新）時，沒有新資料也要匯出，橫幅才會更新。"""
    try:
        old = json.loads((SITE_DATA_DIR / "latest.json").read_text(encoding="utf-8")).get("status", {})
    except (OSError, ValueError):
        return True
    pick = lambda rows: {x["k"]: (x["s"], x["d"]) for x in rows}
    return pick(old.get("datasets", [])) != pick(status_now) or (closed_now is not None and old.get("closed") != closed_now)


def _print_summary(items, days):
    last = days[-1] if days else None
    if last:
        print(f"\n📊 收集結果（{last}）")
        for i in items:
            if i.date == last and i.status == health.OK:
                print(f"  ✅ {i.label} {i.n:,} 筆")
    lines = health.problem_lines(items)
    for ln in lines:
        print(f"  {ln}")


def _connect_or_fail(retry: bool):
    try:
        return db.connect()
    except pyodbc.Error:
        if not retry:
            raise
        print(f"⏳ 連不上資料庫，{DB_RETRY_SECONDS} 秒後再試一次")
        time.sleep(DB_RETRY_SECONDS)
        return db.connect()


def _db_failed(e, notify, now) -> int:
    print(f"\n❌ 連不上資料庫（{DB_CONFIG['server']}）或資料表不存在：{str(e).splitlines()[0][:200]}\n"
          "   1. 確認 Docker Desktop 已啟動、資料庫容器已啟動（例如 docker start MySqlServer）\n"
          "   2. 更新程式後請執行一次 python -m twstock setup-db\n"
          "   資料庫恢復後重跑 collect --catch-up 會自動補齊；網站資料沒有變動。")
    if notify:
        health.notify_once({"db": "連不上資料庫，請確認 Docker 與容器已啟動"}, now.date())
    return 2


def run(days=DEFAULT_DAYS, date_=None, no_revenue=False, no_export=False, notify=False, now=None) -> int:
    """collect 的唯一入口：date_ 有值 = collect --date；否則 = catch-up。"""
    from ..export import export_all
    now = now or tw_now()
    try:
        _connect_or_fail(retry=date_ is None).close()
        lock = db.acquire_lock()
    except pyodbc.Error as e:
        return _db_failed(e, notify, now)
    if lock is None:
        print("⏭️  另一個收集程序正在執行，這次略過")
        return 0
    try:
        return _run_locked(days, date_, no_revenue, no_export, notify, now, export_all)
    except pyodbc.Error as e:
        return _db_failed(e, notify, now)
    finally:
        try:
            db.release_lock(lock)
        except pyodbc.Error:
            pass        # 連線已斷：程序結束時鎖會自動釋放


def _run_locked(days, date_, no_revenue, no_export, notify, now, export_all) -> int:
    t0, n0 = now, fetch.request_count()
    calendar_warning = update_calendar(now)
    conn = db.connect()
    try:
        cur = conn.cursor()
        closed = load_closed(cur)
        warn_uncovered(closed, now)
        state = load_state(cur)
        # 中位數需要 20 個交易日
        base = due_days(now, max(days, health.MEDIAN_DAYS), closed)[0]
        end = date_ or now.date()
        start = min(base, (date_ or base) - timedelta(days=45))
        before = load_snapshot(cur, start, end)
        undated_before = _undated_counts(cur)
        adhoc_dates = {r[0] for r in cur.execute("SELECT holiday_date FROM market_holidays WHERE source = 'adhoc'").fetchall()}
        latest_price = cur.execute("SELECT MAX(trade_date) FROM daily_prices").fetchone()[0]
        if not date_ and not is_trading_day(now.date(), closed):
            print(f"ℹ️  今天 {now.date()} 休市")
        if date_:
            closed_for_run = closed - adhoc_dates       # 復原錯判：--date 可以重新查臨時休市日
            is_closed = not is_trading_day(date_, closed_for_run)
            if is_closed:
                print(f"ℹ️  {date_} 休市，不發行情請求")
            plan = plan_for_date(date_, now, is_closed)
        else:
            plan = make_plan(now, days, before, state, closed, _revenue_counts(cur))
    finally:
        conn.close()

    gap_hint = None
    if not date_ and plan["days"] and latest_price and latest_price < plan["days"][0]:
        between = trading_days(latest_price + timedelta(days=1), plan["days"][0] - timedelta(days=1), closed)
        if between:
            gap_hint = between[0]

    if plan_is_empty(plan):
        print(f"✅ 最近 {len(plan['days'])} 個交易日資料齊全，不需要請求")
        written, errors, undated = {}, {}, {}
    else:
        written, errors, undated = execute_plan(plan, now, no_revenue)

    conn = db.connect()
    try:
        cur = conn.cursor()
        after = load_snapshot(cur, start, end)
        # 臨時休市判定（不含 collect --date：明確指定日期時由使用者判斷）
        day_list = list(plan["days"])
        if not date_:
            for d in list(day_list):
                failed = any(k in errors or (k, d) in errors for k in ("prices.TWSE", "prices.TPEx", "futures"))
                n = [after[k].get(d, Row()).n for k in ("prices.TWSE", "prices.TPEx", "futures")]
                if is_adhoc_closure(d, now.date(), *n, failed):
                    add_adhoc(cur, d, now)
                    day_list.remove(d)
                    print(f"  🌀 {d} 上市、上櫃、期交所都沒有資料，判定為臨時休市")
        elif date_ in adhoc_dates and after["prices.TWSE"].get(date_, Row()).n:
            remove_adhoc(cur, date_)
            print(f"  ↩️  {date_} 有資料，移除臨時休市判定")
        conn.commit()
        closed = load_closed(cur)       # 含剛才登記或移除的臨時休市
        changed = any(before[k] != after[k] for k in before) or _undated_counts(cur) != undated_before
        items = evaluate(day_list, after, now, errors)
        result = health.outcome(items)
        undated_errors = [k for k in errors if k in ("alerts", "events", "revenue", "industry", "chains")]
        if undated_errors:
            result = health.ABNORMAL
    finally:
        conn.close()

    _print_summary(items, day_list)
    for k in undated_errors:
        print(f"  ❌ {k}：{errors[k]}")
    if gap_hint:
        result = health.ABNORMAL
        print(f"  ❌ 資料缺口超過 {days} 個交易日。請補抓：python -m twstock history --start {gap_hint} --end {plan['days'][0]}")

    # 先寫紀錄再匯出：這次有新資料時，匯出的「更新於」才是這次的時間；沒有新資料（new_data=0）不會推進
    finished = tw_now()
    detail = {"written": written, "undated": undated, "errors": {str(k): str(v) for k, v in errors.items()},
              "items": [{"k": i.key, "d": str(i.date), "s": i.status, "n": i.n, "m": i.reason[1]} for i in items if i.status != health.OK]}
    if calendar_warning:
        detail["warnings"] = [calendar_warning]
    conn = db.connect()
    try:
        cur = conn.cursor()
        run_id = health.write_run(cur, "date" if date_ else "catch-up", t0, finished, result, changed, fetch.request_count() - n0, detail)
        conn.commit()
    finally:
        conn.close()

    export_failed = False
    data_date = max((d for d, r in after["prices.TWSE"].items() if r.n), default=None)
    # closed 的起點要和匯出時相同（export 的資料日是兩市場的最新日），否則只有上櫃公布時會誤判為變動
    site_date = max((d for k in ("prices.TWSE", "prices.TPEx") for d, r in after[k].items() if r.n), default=None)
    need_export = not no_export and (date_ is not None or changed or
                                     (data_date is not None and status_changed(health.dataset_status(after, data_date, now),
                                                                               health.site_closed(closed, site_date))))
    if need_export:
        export_seconds = None
        try:
            export_seconds = round(export_all(), 1)
        except (Exception, SystemExit) as e:
            export_failed = True
            result = health.ABNORMAL
            print(f"  ❌ 匯出失敗：{e}")
        conn = db.connect()
        try:
            health.finish_run(conn.cursor(), run_id, result, export_seconds)
            conn.commit()
        finally:
            conn.close()
    elif not no_export:
        print("ℹ️  沒有新資料，不匯出")

    if notify and result == health.ABNORMAL:
        problems = {f"{i.key}:{i.date}": f"{i.label} {i.date:%m/%d} {i.reason[1]}" for i in items if i.status == health.ABNORMAL}
        problems.update({k: f"{k} 失敗" for k in undated_errors})
        if export_failed:
            problems["export"] = "網站資料匯出失敗"
        if gap_hint:
            problems["gap"] = "資料缺口過大，需要 history 補抓"
        health.notify_once(problems, now.date())
    print(f"\n{ {'ok': '✅ 全部齊全', 'pending': '⏳ 部分尚未公布，下次排程會再補', 'abnormal': '❌ 有異常，請看上方訊息'}[result] }")
    return 1 if result == health.ABNORMAL else 0
