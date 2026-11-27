"""第 52 輪（不連網、不連資料庫）：資產負債表彙總（F52-1～F52-6）。
解析用 tests/fixtures/t163sb05_*_mini.html（SA 115Q3 上市、上櫃原始回應只刪列）；收集以假請求、假連線執行；匯出測純函式與訊息；
畫面取出 stock.js、app.js 的函式在 node 執行（node 14 可跑）。檢查函式都接受原始碼字串，最後的 test_contrast 把原始碼改壞（反證），確認對應的檢查會失敗。

  python3 tests/test_iter52.py
"""
import contextlib
import hashlib
import io
import json
import re
import sys
from datetime import date
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
from twstock import db, export  # noqa: E402
from twstock.collectors import balance, catchup, daily, financials, history  # noqa: E402
from twstock.fetch import FetchError, SchemaError  # noqa: E402
import test_iter03 as W3  # noqa: E402
import test_iter34 as T  # noqa: E402
import test_iter35 as T35  # noqa: E402
import test_iter45 as T45  # noqa: E402
import test_iter48 as T48  # noqa: E402
import test_iter51 as T51  # noqa: E402

SITE, HTML, APP, STK = T.SITE, T.HTML, T.APP, T.STK
FIX = ROOT / "tests" / "fixtures"
SRC = lambda p: (ROOT / p).read_text(encoding="utf-8")
BAL, FIN, HIS, EXP, DBS, MAIN, README = (SRC(p) for p in ("twstock/collectors/balance.py", "twstock/collectors/financials.py", "twstock/collectors/history.py",
                                                          "twstock/export.py", "twstock/db.py", "twstock/__main__.py", "README.md"))
ADVICE = set(T48.ADVICE) | T45.ADVICE | {"強", "弱", "名次", "安全", "危險", "惡化", "獲利能力"}
_grab = T._grab
page = lambda n: (FIX / f"t163sb05_{n}_mini.html").read_text(encoding="utf-8")
SII, OTC = page("sii_115_03"), page("otc_115_03")
sha = lambda s: hashlib.sha1(s.encode()).hexdigest()[:12]


def _grab_py(src, name):
    return re.search(rf"^def {name}\(.*?(?=^\S|\Z)", src, re.M | re.S).group(0)


def _fn(mod, src, name):
    """從（可能改壞的）原始碼取出頂層函式，在模組名稱空間的複本執行。"""
    ns = dict(vars(mod))
    exec(_grab_py(src, name), ns)
    return ns[name]


def _fns(mod, src, names):
    """同 _fn，但多個函式放進同一個名稱空間（互相呼叫時用改壞的版本）。"""
    ns = dict(vars(mod))
    for n in names:
        exec(_grab_py(src, n), ns)
    return [ns[n] for n in names]


def _node(js):
    try:
        return T48._node(js)
    except ValueError:
        return "ERR"


def _raises(f, err):
    try:
        f()
    except err:
        return True
    except Exception:
        return False
    return False


# ─── 解析（驗收 3～5）───────────────────────────────────────
V2330 = {"total_assets": 10052887514, "total_liab": 3009660084, "parent_equity": 6997901424, "total_equity": 7043227430, "bvps": 269.85}


def check_parse(src=BAL):
    parse = _fn(balance, src, "parse_balance")
    a, b = parse(SII), parse(OTC)
    tr, at = re.findall(r"<tr class='tblHead'>.*?</tr>", SII, re.S)[2], re.search(r"<tr class='\w+'><td[^>]*>2330<", SII).start()
    dup = SII[:at] + tr + SII[at:]                                                   # 一般業表中間插入分頁重複的表頭（原始回應沒有，測試插入）
    again = SII.replace("</table>", re.search(r"<tr class='even'><td[^>]*>1101.*?</tr>", SII, re.S).group(0).replace(" 31.24<", " 99.99<") + "</table>")
    return (len(a) == 16 and len(b) == 7 and a["2330"] == V2330
            and a["2880"] == {"total_assets": 4706062835, "total_liab": 4454087914, "parent_equity": 251972225, "total_equity": 251974921, "bvps": 17.93}
            and a["1413"]["parent_equity"] is None and a["1413"]["total_equity"] == 1117787 and a["2851"]["parent_equity"] is None   # 個體報表：--
            and a["2820"]["parent_equity"] is None and a["2314"]["total_equity"] == -244497 and a["2314"]["bvps"] == -2.25
            and (a["2345"]["bvps"], a["3706"]["bvps"], a["1437"]["bvps"], a["6655"]["bvps"], a["1590"]["bvps"]) == (146.74, 53.84, 43.61, 42.87, 290.23)
            and b["6488"] == {"total_assets": 301635986, "total_liab": 155767745, "parent_equity": 145868241, "total_equity": 145868241, "bvps": 276.21}
            and b["5864"]["parent_equity"] is None and b["1777"]["parent_equity"] is None and b["6015"]["bvps"] is not None
            and a["2855"]["parent_equity"] == 50240073 and b["6015"]["parent_equity"] == 7348632   # QA52-01：證券業表頭「歸屬於母公司業主權益合計」（第 2 個別名）
            and parse(dup) == a and parse(again)["1101"]["bvps"] == 99.99 and len(parse(again)) == 16)   # 同代號後者覆寫


def test_parse():
    assert check_parse()
    assert (FIX / "t163sb05_sii_115_03_mini.html").stat().st_size < 60_000 and "ajax_t163sb05" in SII


def check_abnormal(src=BAL):
    parse = _fn(balance, src, "parse_balance")
    head = SII[:SII.index("<table class='hasBorder'")]
    only = SII.split("<tr class='even'>")[0] + "</table></body></html>"
    nop = SII
    for n in ("歸屬於母公司業主之權益合計", "歸屬於母公司業主權益合計", "歸屬於母公司業主之權益"):
        nop = nop.replace(f">{n}<", ">其他權益項目<")
    got = parse(nop)
    return (parse(head + "</div></body></html>") == {} and parse(only) == {} and parse("<html>查無資料</html>") == {}
            and _raises(lambda: parse("<html>THE REQUESTED URL WAS REJECTED. SECURITY</html>"), FetchError)
            and _raises(lambda: parse("<html>其他</html>"), SchemaError)
            and all(_raises(lambda b=b: parse(SII.replace(b, "XX")), SchemaError) for b in (">每股參考淨值<", ">資產總計<", ">負債總額<", ">權益總計<", "公司<br>代號"))
            and len(got) == 16 and all(r["parent_equity"] is None for r in got.values()) and got["2330"]["total_equity"] == 7043227430)


def test_abnormal():
    assert check_abnormal()


def test_fetch_params():
    resp = mock.Mock(content=OTC.encode("utf-8"))
    with mock.patch.object(balance, "request", return_value=resp) as req:
        got = balance.fetch_balance("TPEx", 2026, 3)
    args, kw = req.call_args
    assert got["6488"]["bvps"] == 276.21 and args == ("POST", "https://mopsov.twse.com.tw/mops/web/ajax_t163sb05") and kw["expect_json"] is False
    assert kw["data"] == {"encodeURIComponent": "1", "step": "1", "firstin": "1", "off": "1", "isQuery": "Y", "TYPEK": "otc", "year": "115", "season": "03"}


# ─── MERGE、DDL、setup-db（驗收 6）───────────────────────────
def test_merge_and_ddl():
    sql = []

    class Cur:
        rowcount = 3

        def execute(self, s, *p):
            sql.append((s, p))
    assert balance.merge_balance(Cur(), 2026, 3, [{"stock_code": "2330", **V2330}], date(2026, 11, 27)) == 3
    s, p = sql[0]
    upd = s[s.index("THEN UPDATE"):s.index("WHEN NOT MATCHED")]
    assert "MERGE quarterly_balance" in s and "JOIN stocks st ON st.stock_code = j.stock_code" in s and "EXCEPT" in s
    assert "updated_at = GETDATE()" in upd and "first_seen" not in upd and "bvps DECIMAL(10,2)" in s
    assert p[1:] == (2026, 3, 2026, 3, date(2026, 11, 27)) and json.loads(p[0])[0]["bvps"] == 269.85
    ddl = "\n".join(db.DDL)
    want = """    IF OBJECT_ID('quarterly_balance') IS NULL
    CREATE TABLE quarterly_balance (
        id            INT IDENTITY(1,1) PRIMARY KEY,
        stock_id      INT            NOT NULL REFERENCES stocks(stock_id),
        fin_year      INT            NOT NULL,
        fin_quarter   TINYINT        NOT NULL CHECK (fin_quarter BETWEEN 1 AND 4),
        total_assets  BIGINT         NULL,
        total_liab    BIGINT         NULL,
        parent_equity BIGINT         NULL,
        total_equity  BIGINT         NULL,
        bvps          DECIMAL(10,2)  NULL,
        first_seen    DATE           NULL,
        created_at    DATETIME       NOT NULL DEFAULT GETDATE(),
        updated_at    DATETIME       NOT NULL DEFAULT GETDATE(),
        CONSTRAINT UQ_quarterly_balance UNIQUE (stock_id, fin_year, fin_quarter)
    )"""
    blk = next(d for d in db.DDL if "quarterly_balance" in d)
    assert want in ddl and all(w not in blk for w in ("twse_index", "CREATE TABLE market_index", "CREATE TABLE etf_events"))
    pos = lambda t: next(k for k, d in enumerate(db.DDL) if f"CREATE TABLE {t} " in d)
    assert db.DDL[pos("quarterly_financials") + 1] is blk and pos("twse_index") - 1 == pos("market_index")
    assert "market_breadth、quarterly_financials、quarterly_balance（第 52 輪）、" in DBS and DBS.count("quarterly_balance（第 52 輪）") == 1
    assert "twse_index（第 51 輪）、etf_holding_gaps\")" in DBS


# ─── 收集：附掛、失敗隔離（驗收 7～10）──────────────────────────
SB04 = {"sii": (FIX / "t163sb04_sii_115_03_mini.html").read_text(encoding="utf-8"), "otc": (FIX / "t163sb04_otc_115_02_mini.html").read_text(encoding="utf-8")}
SB05 = {"sii": SII, "otc": OTC}


class Conn:
    def __init__(self, log):
        self.log, self.rowcount = log, 0

    def cursor(self):
        return self

    def execute(self, s, *p):
        if "MERGE" in s:
            self.rowcount = len(json.loads(p[0]))
            self.log.append(s.split()[1])
        return self

    def fetchall(self):
        return [(c,) for c in ("2330", "2880", "6488", "1101", "1413", "5864", "2408", "1215")]

    def commit(self):
        self.log.append("commit")

    def close(self):
        pass


def _run_fin(fail=None, fin_fail=None, src=None, safe=None):
    """collect_financials(2026, 3, D, 兩市場)：回傳 (回傳值或例外, 請求 [(端點, TYPEK)], DB 紀錄, 輸出)。"""
    reqs, log, out = [], [], io.StringIO()

    def req(method, url, expect_json=True, data=None):
        k = (url.rsplit("_", 1)[1], data["TYPEK"])
        reqs.append(k)
        if k == fin_fail:
            raise FetchError("HTTP 429")
        return mock.Mock(content=(SB04 if k[0] == "t163sb04" else SB05)[k[1]].encode("utf-8"))
    pat = [mock.patch.object(financials, "request", req), mock.patch.object(balance, "request", req),
           mock.patch.object(db, "connect", lambda: Conn(log))]
    if fail and fail[1] == "db":
        pat.append(mock.patch.object(balance, "merge_balance", side_effect=fail[0]))
    elif fail:
        orig = balance.fetch_balance
        pat.append(mock.patch.object(balance, "fetch_balance", lambda m, y, q: (_ for _ in ()).throw(fail[0]) if m == "TWSE" else orig(m, y, q)))
    if safe:
        pat.append(mock.patch.object(balance, "collect_balance_safe", safe))
    with contextlib.ExitStack() as st:
        for p in pat:
            st.enter_context(p)
        st.enter_context(contextlib.redirect_stdout(out))
        fn = _fn(financials, src, "collect_financials") if src else financials.collect_financials
        try:
            r = fn(2026, 3, date(2026, 11, 27), ("TWSE", "TPEx"))
        except Exception as e:
            r = e
    return r, reqs, log, out.getvalue()


def check_attach(src=FIN):
    r, reqs, log, out = _run_fin(src=src)
    lines = [l for l in out.splitlines() if "📑" in l]
    return (reqs == [("t163sb04", "sii"), ("t163sb04", "otc"), ("t163sb05", "sii"), ("t163sb05", "otc")] and r == 4 + 2
            and log == ["quarterly_financials", "commit", "quarterly_financials", "commit", "quarterly_balance", "commit", "quarterly_balance", "commit"]
            and lines[2:] == ["    📑 TWSE 2026Q3 資產負債表：回應 16 家，新增或更正 16 家，略過 12 家",
                              "    📑 TPEx 2026Q3 資產負債表：回應 7 家，新增或更正 7 家，略過 5 家"] and len(lines) == 4)


def test_attach():
    assert check_attach()
    assert sha(re.sub(r"\n    from \.balance.*\n    collect_balance_safe.*", "", re.search(r"^def collect_financials\(.*", FIN, re.M | re.S).group(0))) == "9360e93c10ad"
    assert {n: sha(_grab_py(FIN, n)) for n in ("parse_financials", "merge_financials", "fetch_financials")} == {
        "parse_financials": "9e48f0761021", "merge_financials": "6e435358742f", "fetch_financials": "75033da1478c"}
    assert "from .daily import PARSE_ERRORS" in BAL and balance.PARSE_ERRORS is daily.PARSE_ERRORS


def check_isolation(src=BAL):
    safe = _fn(balance, src, "collect_balance_safe")
    res = []
    for err, kind, warn in ((FetchError("HTTP 429（可能被限流）\n第二行"), "fetch", "    ⚠️  資產負債表 TWSE 2026Q3 未寫入（損益表照常）：HTTP 429（可能被限流）"),
                            (SchemaError("mopsov 資產負債表彙總：表頭不符"), "fetch", "    ⚠️  資產負債表 TWSE 2026Q3 未寫入（損益表照常）：mopsov 資產負債表彙總：表頭不符"),
                            (KeyError("x" * 200), "fetch", "    ⚠️  資產負債表 TWSE 2026Q3 未寫入（損益表照常）：'" + "x" * 119),
                            (db.pyodbc.Error("42S02", "[42S02] Invalid object name 'quarterly_balance'."), "db",
                             "    ⚠️  quarterly_balance 寫入失敗（請確認已執行 setup-db）：('42S02', \"[42S02] Invalid object name 'quarterly_balance'.\")")):
        r, reqs, log, out = _run_fin((err, kind), safe=safe)
        warns = [l for l in out.splitlines() if "⚠️" in l]
        res.append(r == 6 and log[:4] == ["quarterly_financials", "commit", "quarterly_financials", "commit"] and "Traceback" not in out
                   and warns[0] == warn and len(warns) == (2 if kind == "db" else 1)
                   and (kind == "db" or "    📑 TPEx 2026Q3 資產負債表：回應 7 家，新增或更正 7 家，略過 5 家" in out))   # 上市失敗，上櫃照樣抓
    return all(res)


def test_isolation():
    assert check_isolation()
    plan = {"by_date": [], "futures": None, "futures_oi": None, "tpex_months": [], "alerts": False, "events": None, "revenue": [], "financials": (2026, 3)}
    with mock.patch.object(balance, "collect_balance", side_effect=FetchError("x")), mock.patch.object(financials, "fetch_financials", lambda *a: {}), \
            mock.patch.object(db, "connect", lambda: Conn([])), contextlib.redirect_stdout(io.StringIO()):
        written, errors, undated = catchup.execute_plan(plan, W3.T(11, 27))
    assert errors == {} and undated == {"financials": "2026-11-27"}


def test_income_failure():
    r, reqs, log, out = _run_fin(fin_fail=("t163sb04", "sii"))
    assert isinstance(r, FetchError) and reqs == [("t163sb04", "sii")] and log == []


# ─── history --only balance（驗收 11～13）────────────────────────
Q11 = [(y, q) for y in (2024, 2025, 2026) for q in (1, 2, 3, 4) if (y, q) <= (2026, 3)]
ALL = {(y, q, m) for y, q in Q11 for m in ("TWSE", "TPEx")}


def _hist(have, datasets=("balance",), force=False, err=None, ns=None, fin_have=ALL - {(2026, 3, "TWSE")}):
    """ns：history 模組的名稱空間（反證時是執行改壞原始碼的複本）；假資料以 patch.dict 放進 ns。"""
    calls, out, ns = [], io.StringIO(), vars(history) if ns is None else ns
    rec = lambda tag: (lambda *a, **k: calls.append((tag, a, k)) if err is None else (_ for _ in ()).throw(err))
    fake = {"load_balance_have": lambda: have, "load_fin_have": lambda: set(fin_have), "tw_now": lambda: W3.T(11, 27),
            "collect_balance": rec("b"), "collect_financials": lambda *a, **k: calls.append(("f", a, k))}
    with mock.patch.dict(ns, fake), contextlib.redirect_stdout(out):
        ok = ns["run_history"](date(2024, 1, 1), date(2026, 11, 27), datasets=datasets, force=force)
    return ok, calls, out.getvalue()


def check_history(src=HIS):
    ns = dict(vars(history))
    for n in ("run_financials", "run_balance", "run_history"):
        exec(_grab_py(src, n), ns)                         # 同一個名稱空間：假資料以 patch.dict 放進 ns
    h = lambda *a, **k: _hist(*a, ns=ns, **k)  # noqa: E731
    ok, c, o = h(set())
    ok2, c2, _ = h(set(ALL))
    ok3, c3, _ = h(set(ALL) - {(2025, 2, "TPEx")})
    ok4, c4, _ = h(set(ALL), force=True)
    ok5, c5, o5 = h(None)
    f1, _, of1 = h(set(), err=FetchError("HTTP 429"))
    f2, _, of2 = h(set(), err=FetchError("HTTP 429"), force=True)
    f3, _, of3 = h(set(), err=SchemaError("表頭不符"))
    ok6, c6, o6 = h(set(ALL) - {(2026, 3, "TPEx")}, datasets=("financials", "balance"))
    _, c7, o7 = h(set(ALL), datasets=("financials",), fin_have=set())
    hint = "   建議等 30 分鐘以上，再用同樣的指令重跑；已寫入的季別會自動跳過。"
    return (ok and len(c) == 22 and all(a == (y, q, None, (m,)) and k == {} for (_, a, k), (y, q, m) in zip(c, [(y, q, m) for y, q in Q11 for m in ("TWSE", "TPEx")]))
            and "\n📑 資產負債表：待抓 22 次（季別 × 市場）；⏱️  預估約 1.6 分鐘\n" in o and o.rstrip().endswith("🎉 補抓完成！")
            and ok2 and c2 == [] and ok3 and [x[1] for x in c3] == [(2025, 2, None, ("TPEx",))] and ok4 and len(c4) == 22
            and ok5 is False and c5 == [] and o5 == "❌ 尚未建立 quarterly_balance，請先執行 python3 -m twstock setup-db\n"
            and f1 is False and "❌ 在 2024Q1 TWSE 停止：疑似被限流封鎖（HTTP 429）\n" + hint + "\n" in of1 and "--force" not in of1 and "🎉" not in of1
            and f2 is False and of2.endswith(hint + "\n   這次有 --force：重跑會從頭重抓，請改用 --start 2024-01-01 接續。\n")
            and f3 is False and of3.endswith("❌ 在 2024Q1 TWSE 停止：官方欄位不符（表頭不符），需要修改程式\n")
            and ok6 and [t for t, _, _ in c6] == ["f", "b"] and c6[0][1] == (2026, 3, None, ("TWSE",)) and c6[1][1] == (2026, 3, None, ("TPEx",))
            and "\n📑 季報：待抓 22 次（季別 × 市場，每次另抓資產負債表）；⏱️  預估約 3.3 分鐘\n" in o7 and len(c7) == 22 and all(a[2] is None and k == {} for _, a, k in c7))


def test_history():
    assert check_history()
    with mock.patch.object(history, "load_balance_have", lambda: set()), mock.patch.object(history, "tw_now", lambda: W3.T(11, 27)), \
            mock.patch.object(history, "collect_balance", side_effect=FetchError("x")), contextlib.redirect_stdout(io.StringIO()):
        assert history.run_balance(date(2025, 7, 1), date(2025, 9, 30)) == (False, "在 2025Q3 TWSE 停止：疑似被限流封鎖（x）", date(2025, 7, 1))
    assert history.BALANCE == "balance" and "balance" not in daily.DATASET_KEYS and "balance" not in daily.ALL_DATASETS
    assert "            collect_financials(y, q, None, (m,))\n" in HIS
    assert '"tpex_index", "financials", "balance", "etf", "qfii", "margin", "holdings", "sbl"]' in MAIN
    assert "  python -m twstock history --start 2024-01-01 --only balance     只補資產負債表（季底日在範圍內的季別，每季上市、上櫃各 1 個請求；已有的季別自動略過，--force 重抓）\n" in MAIN


# ─── 匯出：純函式（驗收 14～22）────────────────────────────────
CUM = {(2025, 3): (0, 0, 0, 280, 1.0), (2025, 4): (0, 0, 0, 400, 2.0), (2026, 3): (0, 0, 0, 300, 3.0),
       (2024, 3): (0, 0, 0, 100, 1.0), (2024, 4): (0, 0, 0, 300, 1.5), (2023, 3): (0, 0, 0, 150, 0.5)}
B = lambda eq, pe=None, a=1000, l=352, bv=18.5: (a, l, pe, eq, bv)
BAL1 = {(2026, 3): B(2300, 2200), (2025, 3): B(2100, 2000, 1000, 330, 17.2), (2024, 3): B(1800)}


def check_export(src=EXP):
    ni4, _, roe, dr, stk, scr = _fns(export, src, ("fin_ni4", "bs_equity", "bs_roe", "bs_dr", "bs_stock", "bs_screen"))
    one = {(2026, 3): (0, 0, 0, 1, 0), (2025, 4): (0, 0, 0, 0, 0), (2025, 3): (0, 0, 0, 0, 0)}
    ci = stk(CUM, BAL1, "ci")
    no_prev = stk(CUM, {(2026, 3): B(2300, 2200, bv=None)}, "ci")
    return (ni4(CUM, 2026, 3) == 420 and ni4(CUM, 2025, 4) == 400 and ni4(CUM, 2024, 3) is None
            and roe(CUM, BAL1, 2026, 3) == (20.0, None) and roe(one, {(2026, 3): B(6), (2025, 3): B(6)}, 2026, 3) == (16.7, None)
            and roe(CUM, {(2026, 3): B(2200), (2025, 3): B(9999, 2000)}, 2026, 3) == (20.0, None)              # 本季用權益總計、一年前用母公司權益
            and roe(CUM, {(2026, 3): B(None), (2025, 3): None}, 2026, 3) == (None, "c") and roe(CUM, {(2026, 3): B(2200)}, 2026, 3) == (None, "a")
            and roe(CUM, {(2026, 3): B(2200), (2025, 3): B(None)}, 2026, 3) == (None, "a") and roe({(2026, 3): CUM[(2026, 3)]}, BAL1, 2026, 3) == (None, "i")
            and roe(CUM, {(2026, 3): B(300), (2025, 3): B(-500)}, 2026, 3) == (None, "e") and roe({}, {(2026, 3): B(-5)}, 2026, 3) == (None, "a")
            and roe(CUM, {(2026, 3): B(300), (2025, 3): B(-300)}, 2026, 3) == (None, "e")   # QA52-01：平均權益剛好 = 0
            and dr(B(1)) == 35.2 and dr(B(1, l=1125)) == 112.5 and dr(B(1, a=0)) is None and dr(B(1, a=None)) is None and dr(None) is None
            and ci == {"q": 202603, "roe": 20.0, "roep": 25.3, "dr": 35.2, "drp": 33.0, "bv": 18.5, "bvp": 17.2} and list(ci) == ["q", "roe", "roep", "dr", "drp", "bv", "bvp"]
            and list(no_prev) == ["q", "roe", "roep", "rn", "dr", "drp", "bv", "bvp"] and no_prev["rn"] == "a" and no_prev["bv"] is None and no_prev["bvp"] is None
            and all(stk(CUM, BAL1, t) == {"q": 202603, "bv": 18.5, "bvp": 17.2} for t in ("fh", "basi", "bd", "ins", "mim"))
            and stk(CUM, {(2026, 3): B(-10, bv=-3.21)}, "ci")["bv"] == -3.21
            and stk({}, BAL1, "ci") is None and stk(CUM, None, "ci") is None and stk(CUM, {(2025, 3): B(1)}, "ci") is None
            and scr(CUM, BAL1, "ci") == {"roe": 20.0, "dr": 35.2} and scr(CUM, BAL1, "fh") == {"roe": None, "dr": None} and scr(None, None, None) == {"roe": None, "dr": None})


def test_export():
    assert check_export()
    assert {n: sha(_grab_py(EXP, n)) for n in ("fin_e4", "fin_stock", "fin_screen", "fin_base", "fin_cum_base", "fin_single")} == {
        "fin_e4": "6d4d427355a2", "fin_stock": "4505ebf971ae", "fin_screen": "d920e8198864", "fin_base": "c70c3f0a920c", "fin_cum_base": "ad71c4a2e41e", "fin_single": "c4566e055c2e"}
    assert export.bs_equity(None) is None and export.bs_equity(B(5, 0)) == 0 and export.bs_equity(B(5)) == 5
    assert export.SCREEN_KEYS[-2:] == ("roe", "dr") and len(set(export.SCREEN_KEYS)) == len(export.SCREEN_KEYS)


def check_note(src=EXP):
    note = _fn(export, src, "bs_note")
    bs = {"1": {"q": 202603, "roe": 20.0, "dr": 35.2}, "2": {"q": 202603, "roe": None, "rn": "a", "dr": 41.0}, "3": {"q": 202602, "bv": 1.0}, "4": {"q": 202603, "bv": 2.0}}
    return (note(True, bs) == "  📌 資產負債表 2026Q3：個股 4 檔；一般業 ROE 1／2 檔、負債比 2／2 檔"
            and note(True, {}) == "  📌 資產負債表 --：個股 0 檔；一般業 ROE 0／0 檔、負債比 0／0 檔"
            and note(False, {}) == "  📌 資產負債表：尚未建立 quarterly_balance（請執行 setup-db），bs、roe、dr 不輸出")


def test_note_and_wiring():
    assert check_note()
    assert EXP.index('print(f"  📌 類股名稱對不到') < EXP.index("    if miss_all:") < EXP.index("    print(bs_note(bal is not None, bs_all))") < EXP.index('    print(f"✅ 匯出完成')
    fin_line = "               if (fb := fin_stock(fin.get(code), *fin_meta.get(code, (None, None)))) else {}),\n"
    assert fin_line + '            **({"bs": bs_all[code]} if code in bs_all else {}),' in EXP
    assert "                        **fin_screen(fin.get(code)),                                  # 第 10 輪 B5\n                        **bs_screen(fin.get(code), (bal or {}).get(code), fin_meta.get(code, (None,))[0])," in EXP
    assert EXP.index("    fin, fin_meta, fin_counts, fin_seen = _load_financials(cur)") < EXP.index("    bal = _load_balance(cur)") < EXP.index("    conn.close()\n    mlast")
    assert "bs_stock(fin.get(c), (bal or {}).get(c), fin_meta.get(c, (None,))[0])) for c in prices if c in stocks) if x}" in EXP   # QA52-01：個股 bs 用最新一季業別
    assert "SELECT s.stock_code, b.fin_year, b.fin_quarter, b.total_assets, b.total_liab, b.parent_equity, b.total_equity, b.bvps\n" in EXP   # QA52-01：讀表欄序 = bs_equity 的 row[2]、row[3]


Cur = T51.Cur                                                   # OBJECT_ID 回 None／1，列照給


def test_load():
    assert export._load_balance(Cur(None)) is None
    got = export._load_balance(Cur(1, [("2330", 2026, 3, 10, 3, 6, 7, 269.85), ("2330", 2025, 3, 9, 3, None, 6, 220.15)]))
    assert got == {"2330": {(2026, 3): (10, 3, 6, 7, 269.85), (2025, 3): (9, 3, None, 6, 220.15)}}


# ─── 畫面：季報卡 3 格（驗收 23～27、31）──────────────────────────
AT = "if (!Array.prototype.at) Array.prototype.at = function (i) { return this[i < 0 ? this.length + i : i]; };\n"   # node 14：renderFin（既有）用 .at(
BS_RUN = r"""
let box = {};
const $ = s => s === '#finBox > .metrics' ? { insertAdjacentHTML: (w, h) => { const b = box['#finBox'], i = b.innerHTML.indexOf('\n    <div class="ch-label">'); b.innerHTML = b.innerHTML.slice(0, i) + h + b.innerHTML.slice(i); } }
  : (box[s] = box[s] || { insertAdjacentHTML: (w, h) => { box[s].innerHTML += h; } });
const q = [[202503, 2.55, 10, 31.3, 15.6, 6000000, 2.0], [202602, 2.9, 12, 32, 17, 5500000, 2.6], [202603, 3.15, 23.5, 32.7, 18.4, 6142510, 2.55]];
const F = t => ({ t, q, c: { e: 7.93, ey: 40.4 }, e4: 10.22, e4p: 7.25 });
const G = { q: 202603, roe: 25.3, roep: 20.1, dr: 35.2, drp: 33.0, bv: 269.8, bvp: 220.15 };
const CASES = [[G, 'ci'], [{ q: 202603, bv: 81.4, bvp: 74.12 }, 'fh'], ...['a', 'c', 'i', 'e', 'z'].map(rn => [{ q: 202603, roe: null, roep: null, rn, dr: null, drp: null, bv: null, bvp: null }, 'ci']),
  [{ q: 202603, roe: -4.2, roep: null, dr: 112.5, drp: null, bv: -3.21, bvp: 1234.5 }, 'ci'], [{ ...G, q: 202602 }, 'ci'], [null, 'ci']];
const out = CASES.map(([b, t]) => { box = {}; renderFin(F(t)); const before = box['#finBox'].innerHTML; if (b) renderBs(b, F(t)); return [before, box['#finBox'].innerHTML]; });
console.log(JSON.stringify(out));"""
CELL = r'<div class="card stat" title="([^"]*)"><div class="l">([^<]*)</div><div class="v num " style="font-size:16px">([^<]*)</div><div class="s">([^<]*)</div></div>'
T_ROE, T_DR, T_BV = "近 4 季歸屬母公司業主的淨利 ÷ 一年前同季底與本季底權益的平均", "季底的負債總計 ÷ 資產總計", "公開資訊觀測站資產負債表彙總的「每股參考淨值」（元）"
T_NA = "ROE、負債比只計算一般業；金融、保險等業別的負債以存款、保單準備為主，和一般業不能直接比較"
T_A = "ROE 要用一年前同季底與本季底的權益平均；新上市或資料缺季時不計算"
SHORT = "ROE 用近 4 季淨利與平均權益；資產、負債、淨值是季底數字"
FULL = ("ROE（近 4 季）= 近 4 季歸屬母公司業主的淨利 ÷ 平均權益 × 100%；平均權益 =（一年前同季底 + 本季底）歸屬母公司業主權益 ÷ 2，沒有子公司的公司用權益總計。"
        "近 4 季淨利的算法和近 4 季 EPS 相同（本季累計 + 去年全年 − 去年同季累計），用總金額計算，不受期中增資、減資影響。負債比 = 負債總計 ÷ 資產總計 × 100%。"
        "每股淨值是公開資訊觀測站資產負債表彙總的「每股參考淨值」，和頂端股價淨值比用的每股淨值是同一份申報資料；官方換用新一季數字的日子和本站收錄日可能差幾個交易日。"
        "資產、負債、權益是季底的時點數字，不是累計。金融、保險等業別的負債以存款、保單準備為主，不計算 ROE 與負債比。")


def check_card(stk=STK):
    js = AT + "\n".join(_grab(APP, n) for n in ("fmt", "sgn", "cls", "isNum", "REV_BASE", "epsLow", "noteHTML")) + "\n" + \
        "\n".join(_grab(stk, n) for n in ("qName", "qShort", "renderFin", "renderBs")) + BS_RUN
    o = _node(js)
    if o is None or o == "ERR":
        return o is None
    row = lambda h: re.findall(CELL, h[h.index('<div class="metrics bs" style="margin-top:8px">'):]) if "metrics bs" in h else None
    ci, fh, a, c, i, e, z, neg, other, none = o
    note = f'<div class="muted small" style="margin-top:6px"><details class="note"><summary>{SHORT}<i>說明</i></summary><div>{FULL}</div></details></div>'
    sub = lambda r: [x[3] for x in row(r[1])]
    t1 = lambda r: row(r[1])[0][0]
    return (row(ci[1]) == [(T_ROE, "ROE（近 4 季）", "25.3%", "一年前 20.1%"), (T_DR, "負債比", "35.2%", "去年同季 33.0%"), (T_BV, "每股淨值", "269.80", "去年同季 220.15")]
            and ci[1] == ci[0].replace('\n    <div class="ch-label">', ci[1][ci[1].index('<div class="metrics bs"'):ci[1].index('\n    <div class="ch-label">')] + '\n    <div class="ch-label">') + note
            and ci[0].index('<div class="metrics">') == ci[1].index('<div class="metrics">') and ci[1].count('<div class="metrics') == 2
            and row(fh[1]) == [(T_NA, "ROE（近 4 季）", "不適用", "金融、保險等業別不計算"), (T_NA, "負債比", "不適用", "金融、保險等業別不計算"), (T_BV, "每股淨值", "81.40", "去年同季 74.12")]
            and [sub(r)[0] for r in (a, c, i, e, z)] == ["沒有一年前同季的權益資料", "本季沒有權益資料", "近 4 季淨利資料不足", "平均權益為負或零，不計算", "資料不足"]
            and [t1(r) for r in (a, c, i, e, z)] == [T_A, "資產負債表彙總本季的權益欄是空的，不計算 ROE", "近 4 季淨利 = 本季累計 + 去年全年 − 去年同季累計，缺一季就不計算",
                                                   "一年前同季底與本季底權益的平均 ≤ 0 時，ROE 沒有意義，不計算", T_A]
            and row(a[1])[1:] == [("資產負債表彙總本季的資產或負債欄是空的", "負債比", "--", "去年同季 --"), ("資產負債表彙總沒有列出這一季的每股參考淨值", "每股淨值", "--", "去年同季 --")]
            and [x[2:] for x in row(neg[1])] == [("-4.2%", "一年前 --"), ("112.5%", "去年同季 --"), ("-3.21", "去年同季 1,234.50")]
            and other[1] == other[0] and none[1] == none[0] and all(w not in json.dumps(o, ensure_ascii=False) for w in ("--%", "null", "undefined", "NaN")))


def test_card():
    assert check_card()
    assert sha(_grab(STK, "renderFin")) == "bbcdf90c627c"
    assert "  if (tab === 'fund') { renderRevenue(data.revenue); if (F) renderFin(F); }\n  if (tab === 'fund' && F && data.bs) renderBs(data.bs, F);" in STK
    assert STK.index("function renderFin(") < STK.index("function renderBs(") < STK.index("function renderRevenue(")
    assert len(re.findall(r"noteHTML\((['`])(.+?)\1,", APP + STK)) == 8 and "<div id=\"finBox\"></div></div>` : ''}" in STK


# ─── 畫面：選股（驗收 28、29）──────────────────────────────────
COND = {"roe": "  { id: 'roe', g: '基本面', label: 'ROE ≥ {v}%', opts: [10, 15, 20], def: 15, f: scrGe('roe'), cols: ['roe'], title: '最新一季的近 4 季 ROE（近 4 季淨利 ÷ 一年前同季底與本季底權益的平均）；只計一般業，金融、保險等業別不列入' },\n",
        "dr": "  { id: 'dr', g: '基本面', label: '負債比 ≤ {v}%', opts: [30, 50, 70], def: 50, f: (x, v) => isNum(x.dr) && x.dr <= v, cols: ['dr'], title: '最新一季季底的負債總計 ÷ 資產總計；只計一般業，金融、保險等業別不列入' },\n"}
COLS = "  roe: ['ROE', x => x.roe, (v, x) => fmt(v, 1) + '%' + finTag(x)], dr: ['負債比', x => x.dr, (v, x) => fmt(v, 1) + '%' + finTag(x)],   // 第 52 輪 F52-5\n"
B3 = "ROE、負債比只計一般業，用和季報條件同一季的季底資產負債表：ROE = 近 4 季歸屬母公司淨利 ÷ 一年前同季底與本季底權益的平均，負債比 = 負債總計 ÷ 資產總計；新上市沒有一年前同季權益的股票不計算 ROE。"


def check_screen(app=APP):
    if any(v not in app for v in (*COND.values(), COLS)):
        return False
    js = "\n".join(T35._grab(app, n) for n in T35.NAMES + ["scrGe", "scrParse"]) + "\n" + T35.HEAD.replace("fqd: {}", "fqd: { 202603: 9, 202602: 1 }") + \
        f"const SCREEN_CONDS = [\n{COND['roe']}{COND['dr']}];\n" + _grab(app, "scrQuery") + r"""
const X = [{ roe: 15 }, { roe: 14.9 }, { roe: null }, {}, { dr: 50 }, { dr: 50.1 }, { dr: null }, { dr: 0 }];
const [R, D] = SCREEN_CONDS;
console.log(JSON.stringify([X.map(x => R.f(x, 15)), X.map(x => D.f(x, 50)), scrQuery({ roe: 15, dr: 50 }), scrParse('roe=15&dr=50'),
  SCR_COLS.roe[2](15.25, { fq: 202603 }), SCR_COLS.dr[2](112.5, { fq: 202602 }), SCR_COLS.roe.length, SCR_COLS.dr[0]]));"""
    o = _node(js)
    if o is None or o == "ERR":
        return o is None
    return (o[0] == [True, False, False, False, False, False, False, False] and o[1] == [False, False, False, False, True, False, False, True]
            and o[2] == "roe=15&dr=50" and o[3] == {"roe": 15, "dr": 50} and o[4] == "15.3%" and o[5] == '112.5%<span class="muted small">（Q2）</span>'
            and o[6] == 3 and o[7] == "負債比")


def test_screen():
    assert check_screen()
    et, pe = APP.index("  { id: 'et', g: '基本面'"), APP.index("  { id: 'pe', g: '基本面'")
    assert et < APP.index(COND["roe"]) < APP.index(COND["dr"]) < pe
    assert "  // 第 52 輪 F52-5：資產負債表（最新一季；null = 金融等業別、資料不足 → 不符合）\n" + COND["roe"] in APP
    assert "eh: ['EPS新高(季)', x => x.eh, int0],\n" + COLS in APP
    assert "'pbp', 'gm', 'eh', 'roe', 'dr', 'lb', 'lp', 'mc', 'to'].includes(k) || k === 'dv' ? '' : cls(v)" in APP
    assert "（欄位會標出和欄名不同的季別）。" + B3 + "融資融券為張；" in APP


# ─── 用詞、node 14、?v=、文件（驗收 30～35）──────────────────────────
def _new_segs(app=APP, stk=STK):
    segs = [BAL, _grab(stk, "renderBs")] + [l for f in (app, stk) for l in f.splitlines() if "第 52 輪" in l]   # app.js 底部說明另以 B3 檢查（同一行有既有文字）
    segs += [l for f in (EXP, HIS, FIN, DBS, MAIN) for l in f.splitlines() if "第 52 輪" in l or "balance" in l or "資產負債表" in l]
    segs += [_grab_py(EXP, n) for n in ("fin_ni4", "bs_equity", "bs_roe", "bs_dr", "bs_stock", "bs_screen", "bs_note", "_load_balance")]
    segs += [_grab_py(HIS, n) for n in ("load_balance_have", "run_balance")] + list(COND.values()) + [COLS, B3]
    segs += [l for l in README.splitlines() if "第 52 輪" in l]
    return "\n".join(segs)


def check_words(stk=STK, app=APP):
    seg = _new_segs(app, stk)
    js = _grab(stk, "renderBs") + "".join(COND.values()) + COLS
    return all(w not in seg for w in ADVICE) and all(w not in js for w in (".at(", "replaceAll", "||=", "&&=", "??="))


def test_words_node14():
    assert check_words()


def test_version_and_docs():
    for f in ("app.js", "stock.js", "app.css", "tools.js", "help.js", "compare.js"):
        v = hashlib.sha1((SITE / f).read_bytes()).hexdigest()[:8]
        assert f"{f}?v={v}" in HTML, f"index.html 要改成 {f}?v={v}"
    for s in ("app.css?v=d1508f41", "tools.js?v=0a050889", "help.js?v=a5a5a7e8", "compare.js?v=f7e0bca5"):
        assert s in HTML, s
    assert "app.js?v=ce42c6a3" not in HTML and "stock.js?v=c7a90ebc" not in HTML
    assert HTML.count("https://") == 2 and [m.group(1) for m in re.finditer(r'<script src="(\w+)\.js', HTML)] == ["app", "stock", "tools", "help", "compare"]
    assert "python3 tests/test_iter52.py" in README and "第 52 輪" in (ROOT / "docs" / "iterations" / "README.md").read_text(encoding="utf-8")
    r = next(l for l in README.splitlines() if l.startswith("- 第 52 輪資產負債表"))
    for s in ("quarterly_balance", "ajax_t163sb05", "collect_financials", "⚠️", "--only balance", "--force", "backup", "`bs`", "`roe`", "`dr`", "`rn`", "不適用", "ROE ≥ 15%", "負債比 ≤ 50%"):
        assert s in r, s
    assert not re.search(r"第 (?!52 )\d+ 輪", r)


# ─── 實際資料（PG 回補、匯出後；驗收 37）───────────────────────────
def test_site_data():
    f = SITE / "data" / "stocks" / "2330.json"
    S = json.loads((SITE / "data" / "screen.json").read_text(encoding="utf-8")) if (SITE / "data" / "screen.json").exists() else {}
    x = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    if "bs" not in x or "roe" not in S:
        print("  （尚未用第 52 輪匯出或尚未回補，略過實際資料）")
        return
    assert x["bs"]["q"] == x["fin"]["q"][-1][0] and list(x).index("bs") == list(x).index("fin") + 1
    if x["bs"]["q"] == 202603:
        assert 269.63 <= x["bs"]["bv"] <= 269.97 and set(x["bs"]) >= {"roe", "dr", "bv"}
    i = S["codes"].index("2330")
    assert S["roe"][i] == x["bs"].get("roe") and S["dr"][i] == x["bs"].get("dr")


# ─── 反證：原始碼改壞，對應的檢查要失敗 ─────────────────────────
def _mut(src, old, new):
    assert src.count(old) >= 1, old
    return src.replace(old, new, 1)


def test_contrast():
    rows = [
        ("用損益表的業別表頭辨識", check_parse, BAL, '        col = {k: _col(idx, names) for k, names in COLS}\n',
         '        col = {k: _col(idx, names) for k, names in COLS}\n        if not any(n in idx for n in ("營業毛利（毛損）淨額", "淨收益", "利息淨收益")):\n            raise SchemaError("x")\n'),
        ("不略過重複表頭", check_parse, BAL, ' or c[0] == "公司代號"', ""),
        ("母公司權益欄列為必要", check_abnormal, BAL, 'any(col[k] is None for k in NEED)', 'any(i is None for i in col.values())'),
        ("封鎖頁當成 0 家", check_abnormal, BAL, '        if "SECURITY" in text.upper():\n            raise FetchError("mopsov 回傳封鎖頁面（SECURITY）")\n', ""),
        ("資產負債表放在每個市場損益表之後", check_attach, FIN, "        total += len(got)\n", "        total += len(got)\n        from .balance import collect_balance_safe\n        collect_balance_safe(year, quarter, first_seen, (market,))\n"),
        ("資產負債表家數算進回傳值", check_attach, FIN, "    collect_balance_safe(year, quarter, first_seen, markets)", "    total += collect_balance_safe(year, quarter, first_seen, markets) or 2"),
        ("不攔 pyodbc.Error", check_isolation, BAL, "except db.pyodbc.Error as e:", "except ZeroDivisionError as e:"),
        ("只抓第一個市場", check_isolation, BAL, "    for market in markets:\n        try:", "    for market in markets[:1]:\n        try:"),
        ("回補用關鍵字參數", check_history, HIS, "            collect_balance(y, q, None, (m,))", "            collect_balance(y, q, first_seen=None, markets=(m,))"),
        ("資料表不存在仍發請求", check_history, HIS, '        return False, "", None\n    have = set()', '        have = set()\n    have = set()'),
        ("季報預估沒有乘 2", check_history, HIS, "len(todo) * 2 * SECONDS_PER_QUARTER", "len(todo) * SECONDS_PER_QUARTER"),
        ("--force 不提示改用 --start", check_history, HIS, "        if at and force:\n", "        if False:\n"),
        ("ROE 用單季年化", check_export, EXP, "    ni = fin_ni4(cum, y, q)\n", "    ni = fin_single(cum, y, q) and fin_single(cum, y, q)[3] * 4\n"),
        ("ROE 只用期末權益", check_export, EXP, "    return _r1(ni * 2, e0 + e1), None", "    return _r1(ni, e1), None"),
        ("rn 順序反過來", check_export, EXP, '    e1 = bs_equity(bal.get((y, q)))\n    if e1 is None:\n        return None, "c"\n    e0 = bs_equity(bal.get((y - 1, q)))\n    if e0 is None:\n        return None, "a"\n',
         '    e1 = bs_equity(bal.get((y, q)))\n    e0 = bs_equity(bal.get((y - 1, q)))\n    if e0 is None:\n        return None, "a"\n    if e1 is None:\n        return None, "c"\n'),
        ("非一般業也輸出 roe", check_export, EXP, '    if tbl == "ci":\n        roe, rn', '    if True:\n        roe, rn'),
        ("母公司權益 -- 不改用權益總計", check_export, EXP, "row[2] if row[2] is not None else row[3]", "row[2]"),
        ("📌 缺季別寫 0", check_note, EXP, "if top else '--'}", "if top else '0'}"),
        ("fmt(null, 1) + '%'", check_card, STK, "const pc = v => v == null ? '--' : fmt(v, 1) + '%';", "const pc = v => fmt(v, 1) + '%';"),
        ("季別不同仍顯示", check_card, STK, "  if (B.q !== F.q[F.q.length - 1][0]) return;\n", ""),
        ("3 格插在說明之後", check_card, STK, "$('#finBox > .metrics').insertAdjacentHTML('afterend', ", "$('#finBox').insertAdjacentHTML('beforeend', "),
        ("負債比門檻用 <", check_screen, APP, "x.dr <= v, cols: ['dr']", "x.dr < v, cols: ['dr']"),
        ("用詞（清單中的任一詞）", check_words, STK, "沒有一年前同季的權益資料", f"{sorted(ADVICE)[0]}沒有一年前同季的權益資料"),
        ("node 14 不支援的寫法", check_words, STK, "F.q[F.q.length - 1][0]", "F.q.at(-1)[0]"),
    ]
    for name, check, src, old, new in rows:
        bad = _mut(src, old, new)
        try:
            ok = check(bad)
        except Exception:
            ok = False
        assert not ok, f"反證沒有被擋下：{name}"
        print(f"  ✔ 反證擋下：{name}")


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_") and callable(f):
            f()
            print(f"✅ {n}")
