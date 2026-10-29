"""
補抓歷史資料（指定日期範圍）。

資料庫已有的日期會自動跳過，所以中途被封鎖時，稍後用同樣的指令重跑即可接續；
加 force=True 則已存在的日期也重新抓取並覆寫。
"""
import time
from datetime import date, timedelta

from .. import db
from ..fetch import FetchError
from .daily import ALL_DATASETS, INSTI, PRICES, collect_for_date
from .revenue import collect_monthly_revenue, revenue_month_for

# ─── 台股休市日（來源：證交所公告；不在表內的休市日會被判定為「無資料」）────
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
    date(2026, 7, 10), date(2026, 10, 23),   # 證交所當日無交易資料（臨時休市）
}

_TABLE = {PRICES: "daily_prices", INSTI: "institutional_trades"}
SECONDS_PER_DAY = {PRICES: 8, INSTI: 4}   # 依網站節流間隔 + 回應時間的實測值


def is_trading_day(d: date) -> bool:
    return d.weekday() < 5 and d not in HOLIDAYS


def trading_days(start: date, end: date) -> list:
    return [start + timedelta(n) for n in range((end - start).days + 1)
            if is_trading_day(start + timedelta(n))]


def dates_in_db(dataset: str, start: date, end: date) -> set:
    conn = db.connect()
    try:
        rows = conn.cursor().execute(
            f"SELECT DISTINCT trade_date FROM {_TABLE[dataset]} WHERE trade_date BETWEEN ? AND ?",
            start, end).fetchall()
        return {r[0] for r in rows}
    finally:
        conn.close()


def run_history(start: date, end: date, datasets=ALL_DATASETS, force=False,
                revenue=True, delay=0.0) -> bool:
    """回傳 True = 全部完成；False = 中途疑似被封鎖而停止。"""
    days = trading_days(start, end)
    # 每一天只抓資料庫還缺的資料集
    have = {ds: (set() if force else dates_in_db(ds, start, end)) for ds in datasets}
    todo = [(d, tuple(ds for ds in datasets if d not in have[ds])) for d in days]
    todo = [(d, ds) for d, ds in todo if ds]

    est = sum(sum(SECONDS_PER_DAY[x] for x in ds) + delay for _, ds in todo) / 60
    print(f"📅 補抓範圍：{start} ~ {end}，資料集：{'、'.join(datasets)}")
    print(f"📊 交易日 {len(days)} 天，待抓 {len(todo)} 天；⏱️  預估約 {est:.1f} 分鐘")

    success, no_data, blocked_at = 0, [], None
    for i, (d, ds) in enumerate(todo, 1):
        print(f"[{i}/{len(todo)}]", end="")
        try:
            if collect_for_date(d, ds):
                success += 1
            else:
                no_data.append(d)
        except FetchError as e:
            # 已退避重試仍失敗 → 幾乎確定被封鎖，繼續打只會延長封鎖時間
            print(f"  ❌ {e}")
            blocked_at = d
            break
        if delay:
            time.sleep(delay)

    # 月營收：每個月份只抓一次（每市場 1 個請求）
    months = sorted({m for m in map(revenue_month_for, days) if m})
    if revenue and PRICES in datasets and months and blocked_at is None:
        print(f"\n💰 月營收：{len(months)} 個月份")
        for y, m in months:
            try:
                collect_monthly_revenue(y, m, force=force)
            except FetchError as e:
                print(f"  ❌ {e}")
                blocked_at = end
                break

    print(f"\n{'=' * 50}\n✅ 成功：{success} 天")
    if no_data:
        print(f"ℹ️  無資料（未列入休市表的休市日或尚未公布）：{', '.join(map(str, no_data))}")
    if blocked_at:
        print(f"❌ 在 {blocked_at} 停止：疑似被限流封鎖\n"
              "   建議等 30 分鐘以上，再用同樣的指令重跑；已寫入的日期會自動跳過。")
        return False
    print("🎉 補抓完成！")
    return True
