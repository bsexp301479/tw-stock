"""
台指期每分鐘 K 線（TAIFEX MIS 行情 API）→ futures_minute_prices。

注意：MIS 的 getChartData 端點並非公開文件化的 API，2026/05 實測曾回 404；
執行前請先用單日測試，確認端點仍可使用。
"""
from datetime import date, timedelta

from .. import db
from ..fetch import FetchError, request

MIS_CHART_URL = "https://mis.taifex.com.tw/futures/api/getChartData"
MIS_HEADERS = {
    "Referer": "https://mis.taifex.com.tw/futures/",
    "Origin":  "https://mis.taifex.com.tw",
    "Content-Type": "application/json",
}
DEFAULT_SYMBOL = "TX00"   # 近月連續合約；歷史資料建議用指定月份，如 TX202606
DAY_SESSION = ("08:45", "13:45")   # 其餘時間為夜盤（15:00 ~ 次日 05:00）


def fetch_minute_bars(symbol: str, d: date) -> list:
    payload = {"SymbolID": symbol, "Resolution": "1",
               "StartTime": f"{d:%Y%m%d}0000", "EndTime": f"{d:%Y%m%d}2359"}
    raw = request("POST", MIS_CHART_URL, json=payload, headers=MIS_HEADERS)
    if str(raw.get("RtCode", "")) != "0":
        return []
    bars = []
    for b in (raw.get("RtData") or {}).get("BarData") or []:
        t = str(b.get("Time", ""))   # YYYYMMDDHHMM
        if len(t) < 12:
            continue
        hhmm = f"{t[8:10]}:{t[10:12]}"
        bars.append({
            "trade_time": hhmm + ":00",
            "session": "DAY" if DAY_SESSION[0] <= hhmm <= DAY_SESSION[1] else "NIGHT",
            "open_price": float(b.get("Open", 0)), "high_price": float(b.get("High", 0)),
            "low_price": float(b.get("Low", 0)), "close_price": float(b.get("Close", 0)),
            "volume": int(b.get("Volume", 0)),
        })
    return bars


def collect_futures(start: date, end: date = None, symbol: str = DEFAULT_SYMBOL):
    end = end or start
    conn = db.connect()
    try:
        cursor = conn.cursor()
        d = start
        while d <= end:
            try:
                bars = fetch_minute_bars(symbol, d)
            except FetchError as e:
                print(f"  ❌ {symbol} {d}：{e}")
                break
            if bars:
                cursor.execute("""
                    MERGE futures_minute_prices AS t
                    USING OPENJSON(?) WITH (
                        trade_time TIME(0), session NVARCHAR(5),
                        open_price DECIMAL(10,2), high_price DECIMAL(10,2),
                        low_price DECIMAL(10,2), close_price DECIMAL(10,2), volume INT
                    ) AS s
                    ON t.symbol = ? AND t.trade_date = ? AND t.trade_time = s.trade_time AND t.session = s.session
                    WHEN NOT MATCHED THEN
                        INSERT (symbol, trade_date, trade_time, session,
                                open_price, high_price, low_price, close_price, volume)
                        VALUES (?, ?, s.trade_time, s.session,
                                s.open_price, s.high_price, s.low_price, s.close_price, s.volume);
                """, db.to_json(bars), symbol, d, symbol, d)
                conn.commit()
            day = sum(b["session"] == "DAY" for b in bars)
            print(f"  {symbol} {d}：{len(bars)} 筆（日盤 {day}、夜盤 {len(bars) - day}）")
            d += timedelta(days=1)
    finally:
        conn.close()
