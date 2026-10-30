"""
第 01 輪純邏輯測試（不連網、不連資料庫）：
加權指數正負號、月營收累計年增與新高、民國日期、處置／注意股解析與有效判斷。

  python3 tests/test_iter01.py      （也相容 pytest）
"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from twstock.collectors.alerts import _SOURCES, parse_alert, roc_date, roc_period  # noqa: E402
from twstock.collectors.daily import parse_taiex  # noqa: E402
from twstock.export import _alert_status, _revenue_rows  # noqa: E402

D = date(2026, 10, 29)


# ─── A1：加權指數 ─────────────────────────────────────────
def _mi_index(sign, points):
    # 2026-10-29 MI_INDEX 實測片段：價格指數表第 1 列是寶島指數，第 2 列才是加權指數
    return {"tables": [
        {"title": "115年10月29日 大盤統計資訊", "fields": ["成交統計"], "data": [["x"]]},
        {"title": "115年10月29日 價格指數(臺灣證券交易所)",
         "fields": ["指數", "收盤指數", "漲跌(+/-)", "漲跌點數", "漲跌百分比(%)", "特殊處理註記"],
         "data": [["寶島股價指數", "52,000.00", "<p style ='color:green'>-</p>", "700.00", "-1.33", ""],
                  ["發行量加權股價指數", "46,368.33", sign, points, "-1.42", ""]]},
    ]}


def test_parse_taiex():
    r = parse_taiex(_mi_index("<p style ='color:green'>-</p>", "667.25"), D)
    assert r == {"index_code": "TAIEX", "trade_date": "2026-10-29", "close_price": 46368.33, "change": -667.25}
    assert parse_taiex(_mi_index("<p style ='color:red'>+</p>", "667.25"), D)["change"] == 667.25
    assert parse_taiex(_mi_index("<p> </p>", "0.00"), D)["change"] == 0
    assert parse_taiex({"tables": [{"title": "大盤統計資訊", "fields": [], "data": []}]}, D) is None
    assert parse_taiex({}, D) is None
    # 指數表欄位改名、資料列太短 → None（不丟 KeyError／IndexError，個股照寫）
    renamed = {"tables": [{"title": "115年10月29日 價格指數(臺灣證券交易所)",
                           "fields": ["指數名稱", "收盤指數", "漲跌(+/-)", "漲跌點數"],
                           "data": [["發行量加權股價指數", "1", "-", "1"]]}]}
    assert parse_taiex(renamed, D) is None
    short = _mi_index("-", "667.25")
    short["tables"][1]["data"] = [["發行量加權股價指數", "46,368.33"]]
    assert parse_taiex(short, D) is None


# ─── B8：累計年增與新高 ───────────────────────────────────
def _rev(start_year, months, value=lambda i: 100):
    """從 start_year/01 起連續 months 個月的人造營收列。"""
    return [[start_year + i // 12, i % 12 + 1, value(i), None, None] for i in range(months)]


def test_revenue_rows():
    # (a) 前一年完整：2024 每月 100，2025/01～03 為 110、120、130 → 累計年增 = 360/300 − 1 = 20%
    rows = _rev(2024, 12) + [[2025, 1, 110, None, None], [2025, 2, 120, None, None], [2025, 3, 130, None, None]]
    out = _rev_map(_revenue_rows(rows))
    assert out[(2025, 1)][5] == 10.0 and out[(2025, 3)][5] == 20.0
    assert out[(2024, 6)][5] is None                     # 沒有 2023 → None
    # (b) 前一年缺 1 個月 → None；缺的月份之前不受影響
    rows = [r for r in _rev(2024, 15) if (r[0], r[1]) != (2024, 2)]
    out = _rev_map(_revenue_rows(rows))
    assert out[(2025, 1)][5] == 0.0 and out[(2025, 2)][5] is None and out[(2025, 3)][5] is None
    # 去年同期合計為 0 → None
    rows = [[2024, 1, 0, None, None], [2025, 1, 50, None, None]]
    assert _revenue_rows(rows)[1][5] is None
    # (c) 第 25 個月創新高 → N = 2；第 24 個月創新高 → 0
    rows = _rev(2023, 25, lambda i: 200 if i == 24 else 100)
    assert _revenue_rows(rows)[24][6] == 2
    rows = _rev(2023, 24, lambda i: 200 if i == 23 else 100)
    assert _revenue_rows(rows)[23][6] == 0
    # (d) 不是新高（等於之前最高、或低於）→ 0；第 45 個月新高 → N = 3
    rows = _rev(2023, 45, lambda i: 300 if i in (10, 44) else 100)
    out = _revenue_rows(rows)
    assert out[44][6] == 0 and all(r[6] == 0 for r in out)
    rows = _rev(2023, 45, lambda i: i)
    assert _revenue_rows(rows)[44][6] == 3 and _revenue_rows(rows)[24][6] == 2
    assert _revenue_rows([]) == []


def _rev_map(out):
    return {(r[0], r[1]): r for r in out}


# ─── B10：民國日期、警示解析、有效判斷 ─────────────────────
def test_roc_date():
    assert roc_date("1151029") == date(2026, 10, 29)
    assert roc_date("115/10/28") == date(2026, 10, 28)
    assert roc_date("115/1/5") == date(2026, 1, 5)
    assert roc_date("") is None and roc_date(None) is None
    assert roc_date("1151340") is None
    assert roc_period("115/10/28～115/11/03") == (date(2026, 10, 28), date(2026, 11, 3))
    assert roc_period("1151030~1151105") == (date(2026, 10, 30), date(2026, 11, 5))
    assert roc_period("") == (None, None)


# 2026-10-30 實測樣本（只保留必要欄位與長文片段）
_TWSE_DETAIL = ("１處置原因：該有價證券之交易，連續三個營業日達本公司「公布注意交易資訊」標準，"
                "且該股票於最近三十個營業日內曾發布處置交易資訊。\n２處置期間：自民國一百十五年十月三十日起"
                "至一百十五年十一月五日﹝五個營業日〕。\n３處置措施：\nａ以人工管制之撮合終端機執行撮合作業"
                "（約每二分鐘撮合一次）。\nｂ所有投資人每日委託買賣該有價證券時，應就其當日已委託之買賣，"
                "向該投資人收取全部之買進價金或賣出證券。\n")
_TPEX_COND = ("* 公布日期：115/10/29* 證券代號：4577* 證券名稱：達航科技股份有限公司"
              "* 處置原因：連續5個營業日達本中心「公布注意交易資訊」標準。* 處置起訖期間：自115年10月30日起"
              "5個營業日(115年10月30日至115年11月5日)。* 處置措施：(1)以人工管制之撮合終端機執行撮合作業"
              "(約每2分鐘撮合一次)；(2)證券商應就投資人每日已委託買賣該有價證券之數量單筆達10交易單位"
              "或多筆累積達30交易單位以上時，向該投資人收取全部之買進價金或賣出證券。")


def test_parse_alert():
    twse_d, twse_n, tpex_d, tpex_n = (s[1:] for s in _SOURCES)
    # 上市注意股端點無資料時的佔位列
    assert parse_alert({"Number": "0", "Code": "", "Name": "", "TradingInfoForAttention": "", "Date": ""},
                       *twse_n) is None
    # 權證
    assert parse_alert({"Date": "1151027", "Code": "071804", "DispositionPeriod": "115/10/28～115/11/03",
                        "Detail": _TWSE_DETAIL, "ReasonsOfDisposition": "連續三次"}, *twse_d) is None
    a = parse_alert({"Date": "1151029", "SecuritiesCompanyCode": "4577", "DispositionPeriod": "1151030~1151105",
                     "DispositionReasons": "連續5個營業日", "DisposalCondition": _TPEX_COND}, *tpex_d)
    assert a["stock_code"] == "4577" and a["alert_type"] == "disposal" and a["announce_date"] == "2026-10-29"
    assert (a["start_date"], a["end_date"]) == ("2026-10-30", "2026-11-05")
    assert "連續5個營業日" in a["reason"]
    assert a["measure"] == "約每2分鐘撮合一次、預收款券"
    b = parse_alert({"Date": "1151029", "Code": "2466", "DispositionPeriod": "115/10/30～115/11/05",
                     "Detail": _TWSE_DETAIL, "ReasonsOfDisposition": "連續三次"}, *twse_d)
    assert b["measure"].startswith("約每二分鐘撮合一次") and b["start_date"] == "2026-10-30"
    # 處置期間無法解析 → None
    assert parse_alert({"Date": "1151029", "Code": "2466", "DispositionPeriod": "", "Detail": ""}, *twse_d) is None
    n = parse_alert({"Date": "1151029", "SecuritiesCompanyCode": "4577",
                     "TradingInformation": " 最近六個營業日累積之最後成交價漲幅達27.13% "}, *tpex_n)
    assert n["alert_type"] == "notice" and n["start_date"] is None and n["reason"].startswith("最近六個")


def test_alert_status():
    d = lambda m, x: date(2026, m, x)
    assert _alert_status("disposal", d(10, 29), d(10, 30), d(11, 5), D) == "upcoming"
    assert _alert_status("disposal", d(10, 21), d(10, 22), d(10, 29), D) == "active"
    assert _alert_status("disposal", d(10, 28), d(10, 29), d(11, 5), D) == "active"
    assert _alert_status("disposal", d(10, 22), d(10, 23), d(10, 28), D) is None
    assert _alert_status("notice", d(10, 29), None, None, D) == "notice"
    assert _alert_status("notice", d(10, 28), None, None, D) is None


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"✅ {name}")
    print("全部通過")
