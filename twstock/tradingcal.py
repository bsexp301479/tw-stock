"""
交易日曆：官方休市表（證交所 holidaySchedule）＋手寫表（備援與歷史）＋臨時休市。

官方表只有「今年」（2026-10-31 實測：queryYear 參數無效，一律回傳今年），每 30 天更新一次；
某年沒有官方資料時用手寫表，手寫表也沒有時平日一律視為交易日並印警告。
"""
from datetime import date, timedelta

from . import db
from .fetch import SchemaError, request

# ─── 手寫表（來源：證交所公告）。有官方資料的年度以官方為準 ────
HOLIDAYS = {
    # 2024
    date(2024, 1, 1), date(2024, 2, 8), date(2024, 2, 9), date(2024, 2, 12), date(2024, 2, 13),
    date(2024, 2, 14), date(2024, 4, 4), date(2024, 4, 5), date(2024, 5, 1), date(2024, 6, 10),
    date(2024, 9, 17), date(2024, 10, 10),
    # 2025
    date(2025, 1, 1), date(2025, 1, 27), date(2025, 1, 28), date(2025, 1, 29), date(2025, 1, 30),
    date(2025, 1, 31), date(2025, 2, 28), date(2025, 4, 3), date(2025, 4, 4), date(2025, 5, 1),
    date(2025, 5, 30), date(2025, 10, 6), date(2025, 10, 10), date(2025, 10, 24), date(2025, 10, 25),
    date(2025, 12, 25),
    # 2026
    date(2026, 1, 1), date(2026, 2, 12), date(2026, 2, 13), date(2026, 2, 16), date(2026, 2, 17),
    date(2026, 2, 18), date(2026, 2, 19), date(2026, 2, 20), date(2026, 2, 27), date(2026, 4, 3),
    date(2026, 4, 6), date(2026, 5, 1), date(2026, 6, 19), date(2026, 9, 25), date(2026, 9, 28),
    date(2026, 10, 9), date(2026, 10, 26), date(2026, 12, 25),
}
AD_HOC = {date(2026, 7, 10), date(2026, 10, 23)}   # 證交所當日無交易資料（臨時休市），官方休市表不會有
CAL_URL = "https://www.twse.com.tw/rwd/zh/holidaySchedule/holidaySchedule"
CAL_REFRESH_DAYS = 30


def closed_from_rows(rows) -> set:
    """rows: market_holidays 的 (日期, source)。有官方資料的年度不用手寫表；AD_HOC 與 adhoc 一律算休市。"""
    official = {d.year for d, source in rows if source == "official"}
    return {h for h in HOLIDAYS if h.year not in official} | AD_HOC | {d for d, _ in rows}


def load_closed(cur) -> set:
    return closed_from_rows([tuple(r) for r in cur.execute("SELECT holiday_date, source FROM market_holidays").fetchall()])


def is_trading_day(d: date, closed=None) -> bool:
    return d.weekday() < 5 and d not in (HOLIDAYS | AD_HOC if closed is None else closed)


def trading_days(start: date, end: date, closed=None) -> list:
    return [start + timedelta(n) for n in range((end - start).days + 1)
            if is_trading_day(start + timedelta(n), closed)]


def parse_holidays(data: dict) -> list:
    """官方休市表 → [(日期, 名稱)]；過濾「開始交易日」「最後交易日」等仍有交易的列。"""
    idx = {f: i for i, f in enumerate(data.get("fields") or [])}
    if not {"日期", "名稱"} <= idx.keys():
        raise SchemaError("holidaySchedule 欄位不符")
    out = []
    for row in data.get("data") or []:
        name = str(row[idx["名稱"]]).strip()
        if "開始交易" in name or "最後交易" in name:
            continue
        out.append((date.fromisoformat(str(row[idx["日期"]]).strip()), name))
    return out


def calendar_due(rows, now) -> bool:
    """rows: [(日期, source, fetched_at)]。今年沒有官方資料，或最後更新超過 30 天。"""
    fetched = [f for d, source, f in rows if source == "official" and d.year == now.year]
    return not fetched or (now.replace(tzinfo=None) - max(fetched)).days > CAL_REFRESH_DAYS


def update_calendar(now):
    """需要時更新官方休市表（1 個請求）。失敗不影響收集：沿用既有日曆，回傳警告文字；沒有失敗回傳 None。"""
    conn = db.connect()
    rows = []
    try:
        cur = conn.cursor()
        rows = [tuple(r) for r in cur.execute("SELECT holiday_date, source, fetched_at FROM market_holidays").fetchall()]
        if calendar_due(rows, now):
            holidays = parse_holidays(request("GET", CAL_URL, isolated=True, params={"response": "json"}))
            years = {d.year for d, _ in holidays}
            for y in years:
                cur.execute("DELETE FROM market_holidays WHERE source = 'official' AND YEAR(holiday_date) = ?", y)
            for d, name in holidays:
                cur.execute("""
                    MERGE market_holidays AS t USING (SELECT ? AS holiday_date) AS s ON t.holiday_date = s.holiday_date
                    WHEN MATCHED THEN UPDATE SET name = ?, source = 'official', fetched_at = ?
                    WHEN NOT MATCHED THEN INSERT (holiday_date, name, source, fetched_at) VALUES (?, ?, 'official', ?);
                """, d, name, now.replace(tzinfo=None), d, name, now.replace(tzinfo=None))
            conn.commit()
            print(f"  🗓️  官方休市表：{sorted(years)} 年 {len(holidays)} 筆")
            if now.year not in years:
                print(f"  ⚠️  官方尚未提供 {now.year} 年休市表")
    except Exception as e:      # FetchError、欄位不符都不可中斷收集；資料庫錯誤下一步就會浮現
        kept = any(source == "official" and d.year == now.year for d, source, _ in rows)
        warning = f"官方休市表更新失敗，{'沿用已存的官方表' if kept else '改用手寫表'}：{e}"
        print(f"  ⚠️  {warning}")
        return warning
    finally:
        conn.close()


def warn_uncovered(closed, now) -> None:
    if not any(d.year == now.year for d in closed):
        print(f"  ⚠️  沒有 {now.year} 年的休市資料，平日一律視為交易日；請更新官方休市表或手寫表")


def is_adhoc_closure(d: date, today: date, n_twse: int, n_tpex: int, n_futures: int, failed: bool) -> bool:
    """
    臨時休市：日期已過、上市與上櫃都沒有行情、期交所也沒有日盤，而且這些查詢都沒有失敗。
    三個來源分屬不同主機；任一查詢失敗（failed）都不判定，官方端點短暫異常不會變成永久缺口。
    """
    return d < today and not failed and n_twse == 0 and n_tpex == 0 and n_futures == 0


def add_adhoc(cur, d: date, now) -> None:
    cur.execute("""
        MERGE market_holidays AS t USING (SELECT ? AS holiday_date) AS s ON t.holiday_date = s.holiday_date
        WHEN NOT MATCHED THEN INSERT (holiday_date, name, source, fetched_at) VALUES (?, N'臨時休市（自動判定）', 'adhoc', ?);
    """, d, d, now.replace(tzinfo=None))


def remove_adhoc(cur, d: date) -> None:
    cur.execute("DELETE FROM market_holidays WHERE holiday_date = ? AND source = 'adhoc'", d)
