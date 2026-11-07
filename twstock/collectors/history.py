"""
補抓歷史資料（指定日期範圍）。

資料庫已有的日期會自動跳過，所以中途被封鎖時，稍後用同樣的指令重跑即可接續；
加 force=True 則已存在的日期也重新抓取並覆寫。
"""
import time
from datetime import date, timedelta

from .. import db
from ..config import tw_now
from ..fetch import FetchError
from ..health import load_snapshot, medians, missing_keys
from ..tradingcal import HOLIDAYS, is_trading_day, load_closed, trading_days  # noqa: F401（沿用的對外名稱）
from .daily import (ALL_DATASETS, DATASET_KEYS, DAY_KEYS, HOLDINGS_KEYS, INDEX, PARSE_ERRORS, PRICES, TPEX_INDEX,  # noqa: F401
                    collect_for_date, collect_tpex_index)
from .financials import collect_financials
from .revenue import collect_monthly_revenue, revenue_month_for

FINANCIALS = "financials"       # history --only financials：季報（第 10 輪），不在預設資料集
SECONDS_PER_QUARTER = 4.5       # mopsov 節流 3 秒＋約 1.6 MB 回應

# 依網站節流間隔 + 回應時間的實測值（秒，每個細項）
SECONDS_PER_KEY = {"prices.TWSE": 4, "prices.TPEx": 4, "pe.TWSE": 4, "pe.TPEx": 3.2, "insti.TWSE": 4, "insti.TPEx": 3.2,
                   "index.TAIEX": 4, "amount": 4, "amount.TPEx": 3.2, "etf.TWSE": 4, "etf.TPEx": 1, "margin.TWSE": 4, "margin.TPEx": 0.5,
                   "sbl.TWSE": 4, "sbl.TPEx": 3.2,
                   **{k: 3.2 for k in HOLDINGS_KEYS}}
SHARED = {"etf.TWSE": "prices.TWSE", "etf.TPEx": "prices.TPEx"}   # 同一天也要抓行情時共用回應，不另計時
SECONDS_PER_MONTH = 3.2


def load_status(start: date, end: date) -> tuple:
    """(休市日, 現況快照, 中位數)。中位數要有近期資料，快照多載入 45 天之前的範圍也不影響判斷。"""
    conn = db.connect()
    try:
        cur = conn.cursor()
        closed = load_closed(cur)
        snap = load_snapshot(cur, start, end)
        return closed, snap, medians(snap)
    finally:
        conn.close()


def day_seconds(keys) -> float:
    return sum(SECONDS_PER_KEY[k] for k in keys if SHARED.get(k) not in keys)


def fin_quarters(start: date, end: date, today: date) -> list:
    """季底日落在 start～end、而且收集窗口已開始（季底 + 15 天 ≤ today）的季別 [(年, 季)]，舊到新。"""
    out = []
    for y in range(start.year, end.year + 1):
        for q in range(1, 5):
            qe = date(y, 12, 31) if q == 4 else date(y, q * 3 + 1, 1) - timedelta(days=1)
            if start <= qe <= end and qe + timedelta(days=15) <= today:
                out.append((y, q))
    return out


def load_fin_have() -> set:
    """資料庫已有的 (年, 季, 市場)。"""
    conn = db.connect()
    try:
        return {tuple(r) for r in conn.cursor().execute(
            "SELECT DISTINCT q.fin_year, q.fin_quarter, s.market_type FROM quarterly_financials q "
            "JOIN stocks s ON s.stock_id = q.stock_id").fetchall()}
    finally:
        conn.close()


def run_financials(start: date, end: date, force=False) -> tuple:
    """季報補抓：每季每市場 1 個請求；已有的 (季, 市場) 略過（force 才重抓）；first_seen 一律 NULL。回傳 (完成, 錯誤說明)。"""
    have = set() if force else load_fin_have()
    todo = [(y, q, m) for y, q in fin_quarters(start, end, tw_now().date()) for m in ("TWSE", "TPEx") if (y, q, m) not in have]
    print(f"\n📑 季報：待抓 {len(todo)} 次（季別 × 市場）；⏱️  預估約 {len(todo) * SECONDS_PER_QUARTER / 60:.1f} 分鐘")
    for y, q, m in todo:
        try:
            collect_financials(y, q, None, (m,))
        except FetchError as e:
            return False, f"在 {y}Q{q} {m} 停止：疑似被限流封鎖（{e}）"
        except PARSE_ERRORS as e:
            return False, f"在 {y}Q{q} {m} 停止：官方欄位不符（{e}），需要修改程式"
    return True, ""


def run_history(start: date, end: date, datasets=ALL_DATASETS, force=False,
                revenue=True, delay=0.0) -> bool:
    """回傳 True = 全部完成；False = 中途疑似被封鎖或欄位不符而停止。"""
    if FINANCIALS in datasets:      # 季報不依交易日；只有 --only financials 時才抓
        ok, why = run_financials(start, end, force)
        if not ok:
            print(f"❌ {why}\n   建議等 30 分鐘以上，再用同樣的指令重跑；已寫入的季別會自動跳過。")
            return False
        datasets = tuple(ds for ds in datasets if ds != FINANCIALS)
        if not datasets:
            print("🎉 補抓完成！")
            return True
    closed, snap, med = load_status(start, end)
    days = trading_days(start, end, closed)
    wanted = {k for ds in datasets if ds != TPEX_INDEX for k in DATASET_KEYS[ds]}
    keys = tuple(k for k in DAY_KEYS if k in wanted)
    # 每一天只抓還缺的細項（分市場、看筆數與填充率）；順序一律照 DAY_KEYS（行情先於本益比，ETF 先於融資融券），與 --only 的順序無關
    # 落後公布的持股（delay）以「到今天為止」的交易日判斷，還沒公布的日期不算待抓（第 6 輪 QA-04）
    published = trading_days(start, max(end, tw_now().date()), closed)
    todo = [(d, keys if force else missing_keys(d, keys, snap, med, published)) for d in days]
    todo = [(d, ks) for d, ks in todo if ks]
    months = []
    if TPEX_INDEX in datasets:
        months = sorted({(d.year, d.month) for d in days if force or missing_keys(d, ("index.TPEX",), snap, med)})

    est = (sum(day_seconds(ks) + delay for _, ks in todo) + SECONDS_PER_MONTH * len(months)) / 60
    print(f"📅 補抓範圍：{start} ~ {end}，資料集：{'、'.join(datasets)}")
    print(f"📊 交易日 {len(days)} 天，待抓 {len(todo)} 天；⏱️  預估約 {est:.1f} 分鐘")
    for k in keys:
        n = sum(k in ks for _, ks in todo)
        if n:
            print(f"   {k}：{n} 天")
    if months:
        print(f"   櫃買指數：{len(months)} 個月")

    success, no_data, blocked_at, schema_err = 0, [], None, None
    for i, (d, ks) in enumerate(todo, 1):
        print(f"[{i}/{len(todo)}]", end="")
        written, errors = collect_for_date(d, ks)
        if any(isinstance(e, FetchError) for e in errors.values()):
            # 已退避重試仍失敗 → 幾乎確定被封鎖，繼續打只會延長封鎖時間
            blocked_at = d
            break
        if errors:
            # 欄位不符每天都會失敗：停下來，不要把 242 天的請求都浪費掉
            schema_err = (d, next(iter(errors.values())))
            break
        if any(written.values()):
            success += 1
        else:
            no_data.append(d)
        if delay:
            time.sleep(delay)

    if blocked_at is None and schema_err is None:
        for y, m in months:
            try:
                collect_tpex_index(y, m)
            except FetchError as e:
                print(f"  ❌ {e}")
                blocked_at = date(y, m, 1)
                break
            except PARSE_ERRORS as e:          # QA-04：欄位不符不可出現 Traceback
                schema_err = (date(y, m, 1), e)
                break

    # 月營收：每個月份只抓一次（每市場 1 個請求）
    revenue_months = sorted({m for m in map(revenue_month_for, days) if m})
    if revenue and PRICES in datasets and revenue_months and blocked_at is None and schema_err is None:
        print(f"\n💰 月營收：{len(revenue_months)} 個月份")
        for y, m in revenue_months:
            try:
                collect_monthly_revenue(y, m, force=force)
            except FetchError as e:
                print(f"  ❌ {e}")
                blocked_at = end
                break

    print(f"\n{'=' * 50}\n✅ 成功：{success} 天")
    if no_data:
        print(f"ℹ️  無資料（未列入休市表的休市日或尚未公布）：{', '.join(map(str, no_data))}")
    if schema_err:
        print(f"❌ 在 {schema_err[0]} 停止：官方欄位不符（{schema_err[1]}），需要修改程式")
        return False
    if blocked_at:
        print(f"❌ 在 {blocked_at} 停止：疑似被限流封鎖\n"
              "   建議等 30 分鐘以上，再用同樣的指令重跑；已寫入的日期會自動跳過。")
        return False
    print("🎉 補抓完成！")
    return True
