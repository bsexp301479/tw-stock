"""
第 04 輪純邏輯測試（不連網、不連資料庫、不跳通知、不安裝排程）：
B2＋A4 融資融券解析、資料集、維持率；E1 ETF 分流與資料集；S10 check 開頭、全缺合併、建議指令、QA-04、QA-06；
S11 排程 22:30；橫幅文字。假的官方網站與資料庫沿用 test_iter03 的 World（真實流程，只有 HTTP 與資料庫是假的）。

  python3 tests/test_iter04.py      （也相容 pytest）
"""
import contextlib
import io
import json
import plistlib
import shutil
import subprocess
import sys
import tempfile
from datetime import date, datetime
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_iter03 as t3  # noqa: E402
from twstock import __main__ as cli  # noqa: E402
from twstock import db, export, fetch, health  # noqa: E402
from twstock.collectors import catchup, daily, history  # noqa: E402
from twstock.fetch import SchemaError, is_etf_code, is_valid_stock_code  # noqa: E402
from twstock.health import Row  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
D, T, World, env, run_world, CLOSED = t3.D, t3.T, t3.World, t3.env, t3.run_world, t3.CLOSED
REAL_NOTIFY = health.notify_once

# ─── 2026-11-03 實際回應的樣本列（scratchpad 保存的原始回應，未修改）────
TW_MARGIN_TOTAL = {"title": "115年11月03日 信用交易統計", "fields": ["項目", "買進", "賣出", "現金(券)償還", "前日餘額", "今日餘額"],
                   "data": [["融資(交易單位)", "377,983", "450,131", "16,103", "9,571,090", "9,482,839"],
                            ["融券(交易單位)", "31,896", "103,607", "8,680", "194,930", "257,961"],
                            ["融資金額(仟元)", "21,189,249", "41,240,308", "2,873,840", "622,699,365", "599,774,466"]]}
TW_MARGIN_ROWS = [
    ["00406A", "主動中信台灣收益", "28,884", "14,722", "896", "233,924", "247,190", "4,138,390", "0", "65,270", "0", "0", "65,270", "4,138,390", "3,381", " "],
    ["0050", "元大台灣50", "2,953", "1,345", "53", "27,431", "28,986", "5,922,500", "76", "75", "0", "228", "227", "5,922,500", "23", " "],
    ["1589", "永冠-KY", "0", "0", "32", "37", "5", "0", "0", "0", "0", "0", "0", "0", "0", "OX!"],
    ["2236", "百達-KY", "167", "131", "0", "13,535", "13,571", "15,879", "12", "14", "0", "19", "21", "15,879", "0", "@ "],
    ["2303", "聯電", "6,108", "16,355", "350", "157,064", "146,467", "3,142,523", "574", "258", "104", "1,292", "872", "3,142,523", "145", " "],
    ["2376", "技嘉", "279", "189", "4", "6,688", "6,774", "167,472", "20", "66", "6", "2,241", "2,281", "167,472", "1", " "],
    ["2414", "精技", "6", "6", "0", "252", "252", "40,433", "0", "0", "0", "0", "0", "40,433", "0", "X "],
    ["912000", "晨訊科-DR", "53", "20", "0", "14,486", "14,519", "39,480", "0", "0", "0", "1", "1", "39,480", "0", " "],
]
TPM_ROWS = [
    ["00679B", "元大美債20年", "4,106", "899", "145", "0", "4,860", "27", "0.32", "1,513,298", "25", "0", "1", "0", "24", "0", "0.0", "1,513,298", "1", ""],
    ["006201", "元大富櫃50", "567", "153", "21", "0", "699", "72", "11.2", "6,236", "19", "0", "4", "0", "15", "0", "0.24", "6,236", "4", ""],
    ["2035", "唐榮", "0", "0", "0", "0", "0", "0", "0.0", "0", "0", "0", "0", "0", "0", "0", "0.0", "0", "0", "11OX   C"],
    ["3105", "穩懋", "42,425", "2,464", "2,093", "2", "42,794", "506", "40.37", "105,985", "1,413", "912", "428", "0", "1,897", "47", "1.78", "105,985", "7", ""],
]
TPM_SUMMARY = [["", "合計(張)", "2,308,903", "60,870", "97,921", "2,540", "2,269,312", "", "", "", "36,704", "10,076", "6,584", "1,825", "38,371", "", "", "", "", ""],
               ["", "融資金(仟元)", "204,410,217", "6,397,083", "13,109,481", "1,134,921", "196,562,898", "", "", "", "", "", "", "", "", "", "", "", "", ""]]
MI_ROWS = [   # MI_INDEX 行情表（欄位 = MI_FIELDS_REAL）
    ["0050", "元大台灣50", "302,407,473", "732,782", "30,759,303,345", "102.50", "103.35", "100.50", "100.60", "<p style= color:green>-</p>", "3.50", "100.55", "3,058", "100.60", "970", "0.00"],
    ["00406A", "主動中信台灣收益", "1,608,938,491", "331,206", "13,060,137,327", "8.30", "8.35", "7.96", "7.98", "<p>X</p>", "0.00", "7.98", "6,349", "7.99", "9,238", "0.00"],
    ["00666R", "富邦恒生國企反1", "1", "1", "9", "--", "--", "--", "--", "<p> </p>", "0.00", "9.60", "80", "9.63", "104", "0.00"],
    ["00878", "國泰永續高股息", "192,034,182", "174,043", "6,572,661,708", "34.58", "34.74", "33.77", "33.87", "<p style= color:green>-</p>", "0.93", "33.86", "351", "33.87", "1,295", "0.00"],
    ["01001T", "土銀富邦R1", "18,100", "5", "199,863", "11.04", "11.04", "11.02", "11.02", "<p style= color:green>-</p>", "0.03", "11.02", "2", "11.04", "26", "0.00"],
    ["020000", "富邦特選蘋果N", "0", "0", "0", "--", "--", "--", "--", "<p> </p>", "0.00", "27.85", "10", "27.91", "10", "0.00"],
    ["1101B", "台泥乙特", "9,000", "7", "386,300", "42.95", "42.95", "42.90", "42.90", "<p style= color:green>-</p>", "0.10", "42.90", "4", "43.00", "11", "0.00"],
    ["2330", "台積電", "46,137,336", "518,606", "106,329,297,685", "2,300.00", "2,335.00", "2,280.00", "2,295.00", "<p style= color:green>-</p>", "35.00", "2,290.00", "133", "2,295.00", "843", "26.60"],
    ["910322", "康師傅-DR", "91,611", "64", "2,413,089", "26.05", "26.50", "25.50", "25.50", "<p style= color:green>-</p>", "0.55", "25.65", "1", "26.45", "1", "0.00"],
]
MI_FIELDS_REAL = ["證券代號", "證券名稱", "成交股數", "成交筆數", "成交金額", "開盤價", "最高價", "最低價", "收盤價", "漲跌(+/-)", "漲跌價差",
                  "最後揭示買價", "最後揭示買量", "最後揭示賣價", "最後揭示賣量", "本益比"]
DQ_FIELDS_REAL = ["代號", "名稱", "收盤", "漲跌", "開盤", "最高", "最低", "均價", "成交股數", "成交金額(元)", "成交筆數", "最後買價",
                  "最後買量(張數)", "最後賣價", "最後賣量(張數)", "發行股數", "次日 參考價", "次日 漲停價", "次日 跌停價"]
DQ_ROWS = [
    ["006201", "元大富櫃50", "37.48", "-3.10 ", "40.00", "40.00", "37.44", "38.45", "667,586", "25,665,547", "840", "37.47", "1", "37.48", "16", "24,446,000", "37.48", "41.22", "33.74"],
    ["00679B", "元大美債20年", "26.54", "+0.14", "26.49", "26.60", "26.46", "26.54", "37,322,231", "990,372,248", "8,205", "26.54", "661", "26.55", "183", "6,082,692,000", "26.54", "9999.95", "0.01"],
    ["020001", "富邦存股雙十N", " ---", "--- ", "---", "---", "---", "26.88", "0", "0", "0", "24.95", "50", "25.02", "50", "40,000,000", "25.02", "27.52", "22.52"],
    ["3105", "穩懋", "530.00", "-58.00 ", "555.00", "564.00", "530.00", "544.08", "24,059,926", "13,090,432,968", "36,153", "0.00", "0", "530.00", "2586", "423,940,384", "530.00", "583.00", "477.00"],
    ["710000", "精材群益5C購02", " ---", "--- ", "---", "---", "---", "9.05", "0", "0", "0", "0.00", "0", "5.85", "10", "5,000,000", "5.85", "8.00", "3.70"],
]


def _tw_margin(rows=TW_MARGIN_ROWS, fields=None, groups=None, total=True, stat="OK"):
    detail = {"title": "115年11月03日 融資融券彙總 (全部)", "fields": fields or t3.MGN_FIELDS, "groups": groups or t3.MGN_GROUPS,
              "data": [list(r) for r in rows]}
    return {"stat": stat, "tables": ([TW_MARGIN_TOTAL] if total else []) + [detail]}


def _tp_margin(rows=TPM_ROWS, fields=None, summary=TPM_SUMMARY):
    return {"stat": "ok", "tables": [{"title": "上櫃股票融資融券餘額", "fields": fields or t3.TPM_FIELDS,
                                      "data": [list(r) for r in rows], "summary": summary}]}


def _by_code(rows):
    return {r["stock_code"]: r for r in rows}


# ─── E1：ETF 定義與分流 ───────────────────────────────────
def test_t01_etf_code():
    for c in ("0050", "00878", "00406A", "00679B", "006201", "00687C", "00631L", "00632R", "00635U", "00625K", "00981T", "00982D"):
        assert is_etf_code(c) and not is_valid_stock_code(c), c
    # ETN（02）、受益證券（01）、TDR（91）、特別股、權證、股票都不是 ETF
    for c in ("020000", "02001L", "01001T", "910322", "912000", "1101B", "2881A", "710000", "73000U", "2330", "6467", "0050123"):
        assert not is_etf_code(c), c
    assert is_valid_stock_code("2330") and not is_valid_stock_code("1101B") and not is_valid_stock_code("910322")


def test_t02_quotes_split():
    # 上市：股票只有 2330；ETF 是 0050、00406A、00666R（無成交）、00878；其他證券兩邊都不收
    data = {"stat": "OK", "tables": [{"fields": MI_FIELDS_REAL, "data": MI_ROWS}]}
    with mock.patch.object(daily, "request", lambda *a, **k: data):
        stocks, taiex, raw = daily.fetch_twse_daily(D(11, 3))
    assert [r["stock_code"] for r in stocks] == ["2330"] and stocks[0]["change"] == -35.0 and taiex is None
    etfs = _by_code(daily.parse_etf_quotes(raw, "TWSE"))
    assert sorted(etfs) == ["00406A", "0050", "00666R", "00878"]
    e = etfs["0050"]
    assert (e["close_price"], e["change"], e["volume"], e["trade_value"], e["trade_count"]) == (100.6, -3.5, 302407473, 30759303345, 732782)
    assert etfs["00878"]["close_price"] == 33.87 and etfs["00878"]["change"] == -0.93
    assert etfs["00406A"]["close_price"] == 7.98 and etfs["00406A"]["change"] == 0.0 and etfs["00406A"]["stock_name"] == "主動中信台灣收益"
    assert etfs["00666R"]["close_price"] is None
    # 上櫃
    tdata = {"stat": "ok", "tables": [{"fields": DQ_FIELDS_REAL, "data": DQ_ROWS}]}
    with mock.patch.object(daily, "request", lambda *a, **k: tdata):
        stocks, none, raw = daily.fetch_tpex_daily(D(11, 3))
    assert [r["stock_code"] for r in stocks] == ["3105"] and none is None
    etfs = _by_code(daily.parse_etf_quotes(raw, "TPEx"))
    assert sorted(etfs) == ["006201", "00679B"]
    assert (etfs["00679B"]["close_price"], etfs["00679B"]["change"], etfs["00679B"]["volume"], etfs["00679B"]["trade_value"]) == \
        (26.54, 0.14, 37322231, 990372248)
    assert etfs["006201"]["change"] == -3.1
    # 有股票列卻沒有 ETF 列 → SchemaError（只影響 etf.*）；休市回傳空
    try:
        daily.parse_etf_quotes(({}, []), "TWSE")
        raise AssertionError("沒有 ETF 列要丟 SchemaError")
    except SchemaError:
        pass
    with mock.patch.object(daily, "request", lambda *a, **k: {"stat": "很抱歉，沒有符合條件的資料!"}):
        assert daily.fetch_twse_daily(D(11, 3)) == ([], None, ({}, []))


# ─── B2：融資融券解析 ─────────────────────────────────────
def test_t03_parse_twse_margin():
    rows, total = daily.parse_twse_margin(_tw_margin())
    assert total == {"margin_prev": 9571090, "margin_balance": 9482839, "short_prev": 194930, "short_balance": 257961,
                     "amount_prev": 622699365, "amount_balance": 599774466}
    r = _by_code(rows)
    assert r["2303"] == {"stock_code": "2303", "margin_buy": 6108, "margin_sell": 16355, "margin_redeem": 350, "margin_prev": 157064,
                         "margin_balance": 146467, "margin_limit": 3142523, "short_sell": 258, "short_buy": 574, "short_redeem": 104,
                         "short_prev": 1292, "short_balance": 872, "short_limit": 3142523, "offset_lots": 145, "note": None}
    assert r["2303"]["margin_balance"] - r["2303"]["margin_prev"] == -10597
    assert (r["2236"]["note"], r["2414"]["note"], r["1589"]["note"]) == ("@", "X", "OX!")
    assert r["00406A"]["short_balance"] - r["00406A"]["short_prev"] == 65270
    assert len(rows) == 8        # 股票、ETF、TDR 都在；分流由呼叫端做
    # 無法解析的限額 → None；餘額無法解析 → 略過該列
    bad = [list(x) for x in TW_MARGIN_ROWS]
    bad[4][7] = "N/A"
    bad[5][6] = ""
    rows, _ = daily.parse_twse_margin(_tw_margin(bad))
    assert _by_code(rows)["2303"]["margin_limit"] is None and "2376" not in _by_code(rows)
    # 未公布 → 官方尚無資料
    assert daily.parse_twse_margin({"stat": "很抱歉，沒有符合條件的資料!"}) == ([], None)
    assert daily.parse_twse_margin(_tw_margin(rows=[])) == ([], None)
    # 改版：欄名、groups、統計表
    for kw in ({"fields": t3.MGN_FIELDS[:6] + ["改名"] + t3.MGN_FIELDS[7:]},
               {"groups": [{"title": "股票", "span": 2}, {"title": "融券", "span": 6}, {"title": "融資", "span": 6}]},
               {"total": False}):
        try:
            daily.parse_twse_margin(_tw_margin(**kw))
            raise AssertionError(f"要丟 SchemaError：{kw}")
        except SchemaError:
            pass


def test_t04_parse_tpex_margin():
    rows, total = daily.parse_tpex_margin(_tp_margin())
    assert total == {"margin_prev": 2308903, "margin_balance": 2269312, "short_prev": 36704, "short_balance": 38371,
                     "amount_prev": 204410217, "amount_balance": 196562898}
    r = _by_code(rows)
    assert r["3105"] == {"stock_code": "3105", "margin_buy": 2464, "margin_sell": 2093, "margin_redeem": 2, "margin_prev": 42425,
                         "margin_balance": 42794, "margin_limit": 105985, "short_sell": 912, "short_buy": 428, "short_redeem": 0,
                         "short_prev": 1413, "short_balance": 1897, "short_limit": 105985, "offset_lots": 7, "note": None}
    assert r["2035"]["note"] == "11OX   C" and r["00679B"]["margin_balance"] == 4860
    # summary 是字串化陣列也接受（分析師描述的格式）
    assert daily.parse_tpex_margin(_tp_margin(summary=json.dumps(TPM_SUMMARY, ensure_ascii=False)))[1] == total
    assert daily.parse_tpex_margin({"stat": "ok", "tables": [{"fields": t3.TPM_FIELDS, "data": []}]}) == ([], None)
    for kw in ({"fields": ["改名" if f == "資餘額" else f for f in t3.TPM_FIELDS]}, {"summary": []}):
        try:
            daily.parse_tpex_margin(_tp_margin(**kw))
            raise AssertionError(f"要丟 SchemaError：{kw}")
        except SchemaError:
            pass


def test_t05_ratios():
    assert export.usage(13571, 15879) == 85.46            # 2236（截斷，不是四捨五入的 85.47）
    assert export.usage(42794, 105985) == 40.37           # 3105，與櫃買官方欄位相同
    assert export.usage(5, 0) is None and export.usage(5, None) is None      # 停資（限額 0）
    assert export.short_ratio(2281, 6774) == 33.67        # 2376
    assert export.short_ratio(129630, 6345620) == 2.04    # 上市股票合計
    assert export.short_ratio(1, 0) is None


def test_t06_maint_ratio():
    series = [(D(10, 30), 10), (D(11, 2), None), (D(11, 3), 12)]
    assert export.last_close(series, D(11, 2)) == 10.0 and export.last_close(series, D(11, 3)) == 12.0
    assert export.last_close(series, D(10, 29)) is None
    # 990 張有收盤、10 張沒有：涵蓋率 99%，剛好可以顯示
    mr, cov = export.maint_ratio([(500, 100.0), (490, 50.0), (10, None)], 1000, 60000)
    assert cov == 99.0 and mr == round((500 * 100 + 490 * 50) / 60000 * 100, 2) == 124.17
    assert export.maint_ratio([(989, 100.0), (11, None)], 1000, 60000) == (None, 98.9)       # < 99% → 資料不足
    assert export.maint_ratio([(1, 1.0)], 0, 1)[0] is None and export.maint_ratio([(1, 1.0)], 1, 0)[0] is None


def test_t07_stock_margin():
    d1, d6 = D(10, 27), D(11, 3)
    rows = {d1: (100, 120, 1000, 5, 6, None), d6: (150, 140, 1000, 6, 9, "X")}
    assert export.stock_margin(rows, d6, d1) == {"d": "2026-11-03", "mb": 140, "m1": -10, "m5": 20, "sb": 9, "s1": 3,
                                                  "sr": 6.43, "mu": 14.0, "nt": "X"}
    assert export.stock_margin(rows, d6, None)["m5"] is None              # 不足 6 個融資融券日
    assert export.stock_margin({d6: (0, 0, 0, 0, 0, "OX")}, d6, d1) == {"d": "2026-11-03", "mb": 0, "m1": 0, "m5": None, "sb": 0, "s1": 0,
                                                                        "sr": None, "mu": None, "nt": "OX"}
    assert export.stock_margin(rows, D(11, 4), d6) is None                # 不在信用交易清單


def test_t08_market_margin():
    d1, d2 = D(11, 2), D(11, 3)
    official = {d1: (0, 1000, 0, 50, 0, 60000), d2: (1000, 900, 50, 80, 60000, 45000)}
    stocks = {d1: [("A", 0, 500, 0, 20)], d2: [("A", 500, 450, 20, 30), ("B", 0, 0, 0, 0)]}
    etfs = {d1: [("E", 0, 500, 0, 30)], d2: [("E", 500, 440, 30, 50)]}
    px = {("A", d1): 100, ("A", d2): 90, ("E", d1): 20, ("E", d2): 18}
    close = lambda code, day, is_etf: px.get((code, day))
    m = export.market_margin([d1, d2], official, stocks, etfs, close)
    # 頭條只有股票；ETF 另計；維持率分子股票＋ETF、分母官方金額
    assert (m["mb"], m["m1"], m["mp"], m["sb"], m["s1"], m["sp"], m["sr"]) == (450, -50, -10.0, 30, 10, 50.0, 6.67)
    assert m["etf"] == {"mb": 440, "m1": -60, "sb": 50, "s1": 20}
    assert (m["amt"], m["amt1"]) == (0.5, -0.1)
    assert m["cov"] == 98.89 and m["mr"] is None          # 官方 900 張只涵蓋 890 張（< 99%）→ 資料不足
    assert m["mr0"] == round((500 * 100 + 500 * 20) / 60000 * 100, 2) == 100.0
    assert m["d20"] == ["2026-11-02", "2026-11-03"] and m["m20"] == [500, -50]
    assert export.market_margin([], {}, {}, {}, close) is None


def test_t09_etf_block():
    latest = {"TWSE": (D(11, 3), [("0050", "元大台灣50", 100.6, -3.5, 302407473, 30759303345),
                                  ("00666R", "富邦恒生國企反1", None, 0, 1, 9)]),
              "TPEx": (D(11, 3), [("00679B", "元大美債20年", 26.54, 0.14, 37322231, 990372248)])}
    b = export.etf_block(latest, {"0050": (27431, 28986, 228, 227)})
    assert b["dates"] == {"TWSE": "2026-11-03", "TPEx": "2026-11-03"}
    assert b["rows"]["0050"] == {"n": "元大台灣50", "m": "TWSE", "c": 100.6, "ch": -3.5, "p": -3.36, "v": 302407, "tv": 307.59,
                                 "mb": 28986, "m1": 1555, "sb": 227, "s1": -1}
    assert b["rows"]["00666R"]["c"] is None and b["rows"]["00666R"]["p"] is None and "mb" not in b["rows"]["00666R"]
    assert b["rows"]["00679B"]["m"] == "TPEx" and export.etf_block({}, {}) is None


# ─── E1／B2：真實流程（假的 HTTP 與資料庫）─────────────────
def test_t10_new_day_same_requests():
    # E1-6：新的一天，行情請求數與修改前相同（各 1 次），同時寫入股票與 ETF；融資融券各 1 次
    w = World(D(10, 30))
    w.publish(t3.FIRST_DAY)
    rc, out = run_world(w, T(11, 2, 22, 30))
    assert rc == 0 and "Traceback" not in out
    assert len(t3._hit(w, "MI_INDEX")) == 1 and len(t3._hit(w, "dailyQuotes")) == 1
    assert len(t3._hit(w, "MI_MARGN")) == 1 and len(t3._hit(w, "margin/balance")) == 1
    d = t3.FIRST_DAY
    assert w.rows["prices.TWSE"][d].n == 1100 and w.rows["prices.TPEx"][d].n == 900       # ETF、其他證券沒有混進股票
    assert w.rows["etf.TWSE"][d].n == 250 and w.rows["etf.TPEx"][d].n == 120
    assert w.rows["margin.TWSE"][d].n == 1100 and w.rows["margin.TPEx"][d].n == 900        # 只有股票列
    assert {"etfs", "etf_daily", "etf_margin", "margin_market"} <= set(w.merges)


def test_t11_only_etf_missing():
    # E1-6：股票行情已齊、只缺 ETF：每市場 1 次請求，不寫股票列、不更新 stocks
    w = World(D(10, 30))
    for k in ("etf.TWSE", "etf.TPEx"):
        del w.rows[k][D(10, 30)]
    w.published["MI_INDEX"].add(D(10, 30))
    w.published["dailyQuotes"].add(D(10, 30))
    rc, out = run_world(w, T(10, 31, 12, 0))
    assert rc == 0 and sorted(w.paths()) == ["/rwd/zh/afterTrading/MI_INDEX", "/www/zh-tw/afterTrading/dailyQuotes"]
    assert sorted(set(w.merges)) == ["etf_daily", "etfs"]
    assert w.rows["etf.TWSE"][D(10, 30)].n == 250


def test_t12_no_etf_rows():
    # E1-7：行情回應沒有任何 ETF 列：只有 etf.* 異常，股票行情照常寫入，沒有 Traceback
    w = World(D(10, 30))
    w.publish(t3.FIRST_DAY)
    w.no_etf = True
    rc, out = run_world(w, T(11, 2, 18, 0))
    assert rc == 1 and "Traceback" not in out and "❌ 上市ETF" in out and "❌ 上櫃ETF" in out
    assert w.rows["prices.TWSE"][t3.FIRST_DAY].n == 1100 and w.rows["margin.TWSE"][t3.FIRST_DAY].n == 1100
    assert len(t3._hit(w, "MI_INDEX")) == 1                     # 失敗也不重打同一個回應
    assert set(k.split(":")[0] for k in w.notices[0]) == {"etf.TWSE", "etf.TPEx"}


def test_t13_margin_not_yet():
    # B2-11 #1：11/04 17:30 行情已有、融資融券未公布 → 尚未公布，rc=0；下次只抓融資融券
    w = World(D(11, 3))
    w.publish(D(11, 4), "MI_MARGN", "margin/balance")
    rc, out = run_world(w, T(11, 4, 17, 30))
    assert rc == 0 and "⏳ 上市融資融券：2026-11-04 尚未公布" in out and "⏳ 上櫃融資融券：2026-11-04 尚未公布" in out
    w.requests.clear()
    w.published["MI_MARGN"].add(D(11, 4))
    w.published["margin/balance"].add(D(11, 4))
    rc, out = run_world(w, T(11, 4, 18, 30))            # 18:30：處置／注意股 17:30 已抓過，19:00 前不重抓
    assert rc == 0 and sorted(w.paths()) == ["/rwd/zh/marginTrading/MI_MARGN", "/www/zh-tw/margin/balance"]


def test_t14_margin_deadline_notify_once():
    # B2-11 #2、S11-3：21:45 未公布 → 尚未公布、不通知；22:30 仍未公布 → 異常、通知一次；同日再跑不重複通知
    w = World(D(11, 3))
    w.publish(D(11, 4), "MI_MARGN", "margin/balance")
    with tempfile.TemporaryDirectory() as tmp, mock.patch.object(health, "NOTIFY_FILE", Path(tmp) / "notify.json"), \
            mock.patch.object(health.sys, "platform", "darwin"), mock.patch.object(health.subprocess, "run") as osa:
        def go(hh, mm):
            buf = io.StringIO()
            with env(w), mock.patch.object(health, "notify_once", REAL_NOTIFY), contextlib.redirect_stdout(buf):
                return catchup.run(now=T(11, 4, hh, mm), notify=True), buf.getvalue()
        rc, out = go(21, 45)
        assert rc == 0 and osa.call_count == 0 and "尚未公布" in out
        rc, out = go(22, 30)
        assert rc == 1 and osa.call_count == 1 and "❌ 上市融資融券" in out
        assert "上市融資融券" in osa.call_args[0][0][2]
        rc, out = go(22, 40)
        assert rc == 1 and osa.call_count == 1                  # 同一天同一問題只通知一次


def test_t15_no_margin_request_without_prices():
    # B2-11 #3：當日行情還沒有 → 不發融資融券請求；#4：休市日 → 不發
    w = World(D(11, 3))
    w.published["MI_MARGN"].add(D(11, 4))
    w.published["margin/balance"].add(D(11, 4))
    rc, out = run_world(w, T(11, 4, 17, 30))
    assert rc == 0 and t3._hit(w, "MI_INDEX") and not t3._hit(w, "MI_MARGN", "margin/balance")
    w = World(D(12, 24))
    rc, out = run_world(w, T(12, 25, 22, 30))
    assert rc == 0 and not t3._hit(w, "MI_INDEX", "MI_MARGN", "margin/balance")


def test_t16_margin_schema_change():
    # B2-11 #6：欄位改名 → --catch-up 只有融資融券異常、其他照常；history --only margin 停下、印欄位不符；都沒有 Traceback
    for ep, label in (("MI_MARGN", "上市融資融券"), ("margin/balance", "上櫃融資融券")):
        w = World(D(10, 30))
        w.publish(t3.FIRST_DAY)
        w.renamed.add(ep)
        rc, out = run_world(w, T(11, 2, 18, 0))
        assert rc == 1 and "Traceback" not in out and f"❌ {label}" in out, ep
        assert {k.split(":")[0] for k in w.notices[0]} == {"margin.TWSE" if ep == "MI_MARGN" else "margin.TPEx"}, ep
        assert w.rows["insti.TPEx"][t3.FIRST_DAY].n == 900 and w.rows["etf.TWSE"][t3.FIRST_DAY].n == 250, ep
        w.requests.clear()
        buf = io.StringIO()
        with env(w), contextlib.redirect_stdout(buf):
            assert history.run_history(D(10, 28), t3.FIRST_DAY, ("margin",)) is False
        assert "官方欄位不符" in buf.getvalue() and "Traceback" not in buf.getvalue(), ep


def test_t17_history_order_and_rerun():
    # --only margin etf：同一天一律 ETF 行情先於融資融券（ETF 融資融券列只寫入 etfs 已有的 ETF）；重跑請求 0 次
    days = [D(10, 29), D(10, 30)]
    w = World(D(10, 30))
    for d in days:
        w.publish(d)
        for k in ("etf.TWSE", "etf.TPEx", "margin.TWSE", "margin.TPEx"):
            del w.rows[k][d]
    buf = io.StringIO()
    with env(w), contextlib.redirect_stdout(buf):
        assert history.run_history(days[0], days[1], ("margin", "etf")) is True
    out = buf.getvalue()
    assert "待抓 2 天" in out and "預估約 0.3 分鐘" in out      # (4 + 1 + 4 + 0.5) 秒 × 2 天
    eps = [p.rsplit("/", 1)[-1] for p in w.paths()]
    assert eps == ["MI_INDEX", "dailyQuotes", "MI_MARGN", "balance"] * 2
    assert [f["date"] for p, f in w.requests if "MI_INDEX" in p] == ["20261029", "20261030"]
    w.requests.clear()
    buf = io.StringIO()
    with env(w), contextlib.redirect_stdout(buf):
        assert history.run_history(days[0], days[1], ("etf", "margin")) is True
    assert "待抓 0 天" in buf.getvalue() and w.requests == []
    # 同一天也要抓行情時，ETF 共用回應，不另計時
    assert history.day_seconds(("prices.TWSE", "etf.TWSE")) == 4 and history.day_seconds(("etf.TWSE", "margin.TWSE")) == 8


# ─── S10 核心：check 開頭、全缺合併、建議指令 ─────────────
STATE = {"alerts_at": datetime(2026, 10, 31, 13, 38), "events_to": D(10, 30), "revenue_on": D(10, 31), "collected_at": None,
         "last_run": {"at": datetime(2026, 10, 31, 13, 38), "command": "catch-up", "new_data": True}}


def test_t18_check_whole_day_missing():
    # S10-1：現在 11/03 10:00、資料到 10/30、最後一次收集 10/31 13:38、11/02 全部缺 → 開頭兩行、11/02 一行、建議指令、rc=1
    now = T(11, 3, 10, 0)
    days = health.due_days(now, 20, CLOSED)
    assert days[-1] == D(11, 2)
    snap = t3._full_snapshot(days[:-1])
    with mock.patch.object(fetch._SESSION, "request") as http, mock.patch.object(db, "connect") as conn:
        text, rc = health.check_report(days, snap, now, STATE, CLOSED, schedule="未安裝（安裝方式見 README，由使用者自行執行）")
    assert rc == 1 and http.call_count == 0 and conn.call_count == 0
    lines = text.splitlines()
    assert lines[1] == "🕘 最後一次收集：2026-10-31 13:38（collect --catch-up，有新資料）"
    assert lines[2] == "🗓️  排程：未安裝（安裝方式見 README，由使用者自行執行）"
    bad = [ln for ln in lines if ln.startswith("❌")]
    assert bad == ["❌ 2026-11-02 全部資料集都沒有：最後一次收集是 10/31 13:38，之後沒有執行收集"]
    assert lines[-1] == "👉 請執行 python3 -m twstock collect --catch-up" and "異常 1 項" in text
    # 有收集過但仍全缺（例如被限流）：說明不同
    state = dict(STATE, last_run={"at": datetime(2026, 11, 2, 21, 45), "command": "catch-up", "new_data": False})
    text, _ = health.check_report(days, snap, now, state, CLOSED)
    assert "❌ 2026-11-02 全部資料集都沒有：最後一次收集 11/02 21:45 也沒有取得" in text and "🗓️" not in text
    # 缺口超過 --catch-up 預設 10 天：建議加 --days；超過 30 天：建議 history
    text, _ = health.check_report(days, t3._full_snapshot(days[:-12]), now, STATE, CLOSED)
    assert text.splitlines()[-1] == "👉 請執行 python3 -m twstock collect --catch-up --days 12"
    days40 = health.due_days(now, 40, CLOSED)
    text, _ = health.check_report(days40, t3._full_snapshot(days40[:-35]), now, STATE, CLOSED)
    assert text.splitlines()[-1] == f"👉 請執行 python3 -m twstock history --start {days40[-35]}，再執行 python3 -m twstock collect --catch-up"


def test_t19_check_partial_pending():
    # S10-2：11/03 21:00 只有上市法人缺：不合併、逐項顯示尚未公布，rc=0，沒有建議指令
    now = T(11, 3, 21, 0)
    days = health.due_days(now, 20, CLOSED)
    snap = t3._full_snapshot(days, skip={("insti.TWSE", D(11, 3))})
    state = dict(STATE, alerts_at=datetime(2026, 11, 3, 19, 30))
    text, rc = health.check_report(days, snap, now, state, CLOSED)
    assert rc == 0 and "⏳ 上市法人：2026-11-03 尚未公布" in text and "全部資料集" not in text and "👉" not in text
    # 第 4 輪的資料集在 check 表格中
    for label in ("上市ETF", "上櫃ETF", "上市融資融券", "上櫃融資融券"):
        assert label in text, label


def test_t20_schedule_status_readonly():
    # S10-3：只看檔案是否存在，不呼叫 subprocess
    with tempfile.TemporaryDirectory() as tmp, mock.patch.object(subprocess, "run", side_effect=AssertionError("不可呼叫")), \
            mock.patch.object(subprocess, "Popen", side_effect=AssertionError("不可呼叫")):
        assert health.schedule_status("darwin", tmp) == "未安裝（安裝方式見 README，由使用者自行執行）"
        plist = Path(tmp) / "Library/LaunchAgents/com.twstock.collect.plist"
        plist.parent.mkdir(parents=True)
        plist.write_text("x")
        assert health.schedule_status("darwin", tmp).startswith("已安裝（")
        assert health.schedule_status("win32", tmp) == "無法判斷，請在工作排程器確認"
        assert health.last_run_line(None) == "尚無執行紀錄"


def test_t21_load_state_compat():
    # load_state 多讀 command；相容只有 3 欄的舊假資料
    class Cur:
        def __init__(self, rows):
            self.rows = rows

        def execute(self, *a):
            return self

        def fetchall(self):
            return self.rows
    detail = json.dumps({"undated": {}})
    s = health.load_state(Cur([(datetime(2026, 11, 3, 20, 52), 1, detail, "catch-up")]))
    assert s["last_run"] == {"at": datetime(2026, 11, 3, 20, 52), "command": "catch-up", "new_data": True}
    s = health.load_state(Cur([(datetime(2026, 11, 3, 21, 45), 0, detail), (datetime(2026, 11, 3, 20, 52), 1, detail)]))
    assert s["last_run"]["new_data"] is False and s["last_run"]["command"] is None and s["collected_at"] == datetime(2026, 11, 3, 20, 52)
    assert health.load_state(Cur([]))["last_run"] is None


def test_t22_qa04_history_schema():
    # QA-04：櫃買指數、融資融券、ETF 行情欄位不符時，history 印欄位不符並回傳失敗，沒有 Traceback
    class Renamed(World):
        def _inx(self, form):
            return t3.Resp({"stat": "ok", "tables": [{"fields": ["改名"] + t3.INX_FIELDS[1:], "data": [["2026/09/30"] + ["1"] * 5]}]})
    w = Renamed(D(10, 30))
    del w.rows["index.TPEX"][D(10, 30)]
    buf = io.StringIO()
    with env(w), contextlib.redirect_stdout(buf):
        assert history.run_history(D(10, 30), D(10, 30), ("tpex_index",)) is False
    assert "官方欄位不符" in buf.getvalue() and "indexInfo/inx 欄位不符" in buf.getvalue()
    w = World(D(10, 30))
    w.no_etf = True
    w.publish(D(10, 30))
    del w.rows["etf.TWSE"][D(10, 30)]
    buf = io.StringIO()
    with env(w), contextlib.redirect_stdout(buf):
        assert history.run_history(D(10, 30), D(10, 30), ("etf",)) is False
    assert "官方欄位不符" in buf.getvalue() and "沒有任何 ETF 列" in buf.getvalue()
    # 透過 CLI：回傳 1
    with env(w), contextlib.redirect_stdout(io.StringIO()):
        assert cli.main(["history", "--start", "2026-10-30", "--end", "2026-10-30", "--only", "etf"]) == 1


def test_t23_qa06_check_days():
    for bad in ("0", "-5"):
        buf = io.StringIO()
        with mock.patch.object(db, "connect", side_effect=AssertionError("不可連資料庫")), contextlib.redirect_stdout(buf):
            assert cli.main(["check", "--days", bad]) == 1, bad
        assert "--days 至少 1" in buf.getvalue()


# ─── S11：排程 22:30（只讀檔、只執行 --print）─────────────
def test_t24_schedule_2230():
    sh = (ROOT / "scripts/mac/install_schedule.sh").read_text(encoding="utf-8")
    assert '"22 30"' in sh and "22:30" in sh
    bat = (ROOT / "scripts/windows/install_schedule.bat").read_text(encoding="utf-8")
    assert "/ST 22:30" in bat and "schtasks /Delete /TN %TASK%2230 /F" in bat and bat.count("schtasks /Create") == 4
    if shutil.which("bash"):
        with tempfile.TemporaryDirectory() as tmp:
            r = subprocess.run(["bash", str(ROOT / "scripts/mac/install_schedule.sh"), "--print"], capture_output=True, text=True,
                               timeout=30, env={"HOME": tmp, "PATH": "/usr/bin:/bin"})
            assert r.returncode == 0 and not list(Path(tmp).iterdir())      # 沒有寫任何檔案
            plist = plistlib.loads(r.stdout.encode())
            times = {(x["Hour"], x["Minute"]) for x in plist["StartCalendarInterval"]}
            assert len(plist["StartCalendarInterval"]) == 20 and times == {(17, 30), (19, 30), (21, 45), (22, 30)}
            assert plist["RunAtLoad"] is True and "--notify" in plist["ProgramArguments"]
    assert health.DEADLINE.hour == 22 and health.DEADLINE.minute == 0         # DEADLINE 維持 22:00


# ─── S10 橫幅（node 跑 app.js 真正的 freshLines；沒有 node 略過）────
def test_t25_banner_text():
    latest = {"date": "2026-10-30", "status": {"closed": [], "datasets": []}}
    lines = t3.fresh_lines(latest, "2026-11-02T18:30:00+08:00")
    assert lines is None or lines == [["資料停在 10/30，最新交易日為 11/02，可能尚未收集。請在收集資料的電腦執行 python3 -m twstock collect --catch-up"]]


def test_t26_specs_and_keys():
    keys = [s.key for s in health.SPECS]
    assert keys[keys.index("etf.TWSE"):][:4] == ["etf.TWSE", "etf.TPEx", "margin.TWSE", "margin.TPEx"]     # 第 5 輪之後還有新鍵
    assert daily.DAY_KEYS.index("etf.TWSE") < daily.DAY_KEYS.index("margin.TWSE")
    assert set(daily.DAY_KEYS) | {"index.TPEX", "futures", "futures_oi"} == set(keys)
    assert daily.ALL_DATASETS == ("prices", "pe", "insti", "etf", "margin")


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"✅ {fn.__name__}")
    print("全部通過")
