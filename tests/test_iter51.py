"""第 51 輪（不連網、不連資料庫）：證交所類股指數與加權報酬指數（F51-1～F51-6）。
解析用 11/03 MI_INDEX 精簡樣本（內嵌；logs/ 有原檔時另驗完整列數）；收集用 test_iter03 的假世界；匯出測純函式與訊息；畫面取出 app.js、stock.js、compare.js
的函式在 node 執行（node 14 可跑）。檢查函式都接受原始碼字串，最後的 test_contrast 把原始碼改壞（反證），確認對應的檢查會失敗。"""
import contextlib
import hashlib
import inspect
import io
import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
from twstock import db, export, health  # noqa: E402
from twstock.collectors import daily, history  # noqa: E402
from twstock.fetch import SchemaError  # noqa: E402
import test_iter03 as W3  # noqa: E402
import test_iter34 as T  # noqa: E402
import test_iter46 as T46  # noqa: E402
import test_iter47 as T47  # noqa: E402
import test_iter48 as T48  # noqa: E402

SITE, HTML, APP, STK, CMP = T.SITE, T.HTML, T.APP, T.STK, T48.CMP
DATA = SITE / "data"
EXP = (ROOT / "twstock" / "export.py").read_text(encoding="utf-8")
DLY = (ROOT / "twstock" / "collectors" / "daily.py").read_text(encoding="utf-8")
README = (ROOT / "README.md").read_text(encoding="utf-8")
ADVICE = set(T48.ADVICE) | {"強", "弱", "名次"}
_grab = T._grab


def _node(js):
    """node 執行；反證讓程式丟例外（含 async 內的例外：沒有輸出）→ "ERR"，沒有 node → None（略過）。"""
    try:
        return T48._node(js)
    except ValueError:
        return "ERR"
D3 = date(2026, 11, 3)
GREEN, RED = "<p style ='color:green'>-</p>", "<p style ='color:red'>+</p>"
P_TXT = ("發行量加權股價指數 43,307.54 -1,612.60 / 水泥窯製類指數 692.91 +7.23 / 塑膠化工類指數 1,190.59 -77.71 / 機電類指數 14,727.09 -570.90 / "
         "水泥類指數 133.73 -1.61 / 食品類指數 1,967.03 +0.36 / 塑膠類指數 430.01 -41.19 / 紡織纖維類指數 470.69 -5.85 / 電機機械類指數 475.97 -31.73 / "
         "電器電纜類指數 100.53 -5.62 / 化學生技醫療類指數 153.15 -2.19 / 化學類指數 178.91 -8.38 / 生技醫療類指數 86.52 -0.01 / 玻璃陶瓷類指數 158.04 +8.04 / "
         "造紙類指數 270.93 -2.98 / 鋼鐵類指數 122.46 -1.51 / 橡膠類指數 188.95 -2.34 / 汽車類指數 289.25 -2.31 / 電子工業類指數 2,678.03 -102.65 / "
         "半導體類指數 1,446.44 -45.17 / 電腦及週邊設備類指數 414.99 -14.68 / 光電類指數 65.13 -5.57 / 通信網路類指數 224.70 -7.21 / 電子零組件類指數 758.44 -57.27 / "
         "電子通路類指數 348.75 -10.48 / 資訊服務類指數 245.99 -4.34 / 其他電子類指數 249.72 -10.02 / 建材營造類指數 432.37 -6.22 / 航運類指數 216.50 -5.47 / "
         "觀光餐旅類指數 100.99 -0.97 / 金融保險類指數 3,649.86 -95.07 / 貿易百貨類指數 238.61 -3.18 / 油電燃氣類指數 125.13 -9.66 / 綠能環保類指數 112.30 -5.29 / "
         "數位雲端類指數 37.87 -1.45 / 運動休閒類指數 54.72 -0.18 / 居家生活類指數 97.29 -2.30 / 其他類指數 268.39 -3.12 / 臺指反向一倍指數 1,312.25 +45.48 / "
         "電子類兩倍槓桿指數 303,422.73 -24,187.76")
R_TXT = "寶島股價報酬指數 74,311.86 -2,916.33 / 發行量加權股價報酬指數 100,144.27 -3,728.97 / 半導體類報酬指數 2,774.48 -86.63 / 觀光餐旅類報酬指數 161.90 -1.57"
IND = set("水泥 食品 塑膠 紡織纖維 電機機械 電器電纜 化學 生技醫療 玻璃陶瓷 造紙 鋼鐵 橡膠 汽車 半導體 電腦及週邊 光電 通信網路 電子零組件 電子通路 資訊服務 "
          "其他電子 建材營造 航運 觀光餐旅 金融保險 貿易百貨 油電燃氣 綠能環保 數位雲端 運動休閒 居家生活 其他".split())   # 上市 stocks.industry 32 類（11/26 唯讀 SELECT）
FIELDS = ["收盤指數", "漲跌(+/-)", "漲跌點數", "漲跌百分比(%)", "特殊處理註記"]


def _rows(txt):
    return [[n, c, {"-": GREEN, "+": RED}[ch[0]], ch[1:], "", ""] for n, c, ch in (x.rsplit(" ", 2) for x in txt.split(" / "))]


def sample(p=None, r=None, first=("指數", "報酬指數"), title="115年11月03日 價格指數(臺灣證券交易所)"):
    """精簡 MI_INDEX：證交所兩張表＋不該收的跨市場、臺灣指數公司表（同名不同值）。"""
    other = [["半導體類指數", "9,999.99", RED, "1.00", "", ""], ["發行量加權股價報酬指數", "9,999.99", RED, "1.00", "", ""]]
    return {"stat": "OK", "tables": [
        {"title": "價格指數(跨市場)", "fields": ["指數"] + FIELDS, "data": other},
        {"title": title, "fields": [first[0]] + FIELDS, "data": _rows(P_TXT) if p is None else p},
        {"title": "報酬指數(臺灣指數公司)", "fields": ["報酬指數"] + FIELDS, "data": other},
        {"title": "報酬指數(臺灣證券交易所)", "fields": [first[1]] + FIELDS, "data": _rows(R_TXT) if r is None else r}]}


def _fn(mod, src, name):
    """從（可能改壞的）原始碼取出頂層函式，在模組名稱空間的複本執行。"""
    m = re.search(rf"^def {name}\(.*?(?=^\S)", src, re.M | re.S)
    ns = dict(vars(mod))
    exec(m.group(0), ns)
    return ns[name]


def _sxp(P, d=D3):
    return {d: [(r["index_name"], r["close_price"], r["change"]) for r in P if r["index_name"].endswith("類指數")]}


# ─── 解析（驗收 1～3）─────────────────────────────────────────
def check_parse(src=DLY):
    f = _fn(daily, src, "parse_twse_indices")
    g = f(sample(), D3)
    v = lambda k, n: next(((r["close_price"], r["change"]) for r in g[k] if r["index_name"] == n), None)
    ok = (len(g["P"] or []) == 40 and len(g["R"] or []) == 4 and v("P", "發行量加權股價指數") == (43307.54, -1612.6) and v("R", "發行量加權股價報酬指數") == (100144.27, -3728.97)
          and v("P", "半導體類指數") == (1446.44, -45.17) and v("P", "玻璃陶瓷類指數") == (158.04, 8.04) and v("P", "臺指反向一倍指數") == (1312.25, 45.48)
          and v("P", "電子類兩倍槓桿指數") == (303422.73, -24187.76) and [r["seq"] for r in g["P"]] == list(range(40))
          and set(g["P"][0]) == {"trade_date", "kind", "seq", "index_name", "close_price", "change", "note"} and g["R"][1]["kind"] == "R")
    raw = ROOT / "logs" / "iter04_raw_MI_INDEX_20261103.json"
    if ok and raw.exists():                                     # 原檔：完整 56／47 列，32 類的漲跌 % 都等於官方百分比欄
        data = json.loads(raw.read_text(encoding="utf-8"))
        g = f(data, D3)
        off = {r[0].strip(): float(r[4]) for t in data["tables"] if "價格指數(臺灣證券交易所)" in (t.get("title") or "") for r in t["data"]}
        sx = export.sx_export(_sxp(g["P"]), [D3], D3, IND)[0]
        ok = (len(g["P"]) == 56 and len(g["R"]) == 47 and len(sx["r"]) == 32
              and all(r[3] == off[r[0] + "類指數"] for r in sx["r"]))
    return ok


def test_parse():
    assert check_parse()
    assert hashlib.sha1(inspect.getsource(daily.parse_taiex).encode()).hexdigest()[:12] == "0607285b4af3"   # parse_taiex 不改


def check_abnormal(src=DLY):
    f = _fn(daily, src, "parse_twse_indices")
    p = _rows(P_TXT)[:3] + [["短"], ["收盤空白", "", RED, "1", "", ""], ["收盤缺值", "--", RED, "1", "", ""], ["收盤為零", "0.00", RED, "1", "", ""], ["  ", "10", RED, "1", "", ""],
                            ["名" * 41, "10", RED, "1", "", ""], ["名" * 40, "10", "<p>-</p>", "1", "", ""], ["水泥窯製類指數", "1.00", RED, "1", "", ""],
                            ["正號", "10", "+", "2", "", ""], ["空白號", "10", "", "3", "", ""]]
    g = f(sample(p=p, title="114年10月30日 價格指數(臺灣證券交易所)"), D3)
    names = [r["index_name"] for r in g["P"]]
    no_note = sample()
    for t in no_note["tables"]:
        t["fields"], t["data"] = t["fields"][:5], [r[:5] for r in t["data"]]
    a, b, c = f(sample(first=("指標", "報酬指數")), D3), f(sample(first=("指數", "指數")), D3), f(no_note, D3)
    return (names == ["發行量加權股價指數", "水泥窯製類指數", "塑膠化工類指數", "名" * 40, "正號", "空白號"] and g["P"][1]["close_price"] == 692.91
            and [r["change"] for r in g["P"][3:]] == [-1, 2, 3] and a["P"] is None and len(a["R"]) == 4 and b["R"] is None and len(b["P"]) == 40
            and len(c["P"]) == 40 and all(r["note"] == "" for r in c["P"]) and f({"stat": "OK", "tables": []}, D3) == {"P": None, "R": None})


def test_abnormal():
    assert check_abnormal()


# ─── 收集（驗收 4～9、11）────────────────────────────────────
class World(W3.World):
    """MI_INDEX 換成精簡樣本的兩張表（+ 原本的加權列、行情）；記下 twse_index 的 MERGE 列；fail = 讓 MERGE twse_index 丟出的例外。"""

    def __init__(self, *a, data=None, fail=None):
        super().__init__(*a)
        self.data, self.fail, self.tidx = data, fail, []

    def _mi(self, form):
        r = super()._mi(form)
        if self.data is not None and r.data.get("stat") == "OK":
            r.data["tables"] = self.data["tables"] + r.data["tables"][1:]      # 第 0 張（只有加權一列的價格指數表）換成樣本
        return r

    def apply_merge(self, table, sql, params):
        if table == "twse_index":
            if self.fail:
                raise self.fail
            self.tidx.append((sql, json.loads(params[0])))
        super().apply_merge(table, sql, params)


def _collect(data=None, keys=daily.DAY_KEYS, fail=None, src=None, parse=None, publish=True):
    """假世界收集一天；src = （改壞的）daily.py 原始碼：_save_twse_indices、_collect_key 改用它；parse = 換掉 _save_twse_indices 裡的解析函式。"""
    w = World(date(2026, 10, 30), data=data, fail=fail)
    if publish:
        w.publish(W3.FIRST_DAY)
    save, ck = _fn(daily, src or DLY, "_save_twse_indices"), _fn(daily, src or DLY, "_collect_key")
    ck.__globals__["_save_twse_indices"] = save
    if parse:
        save.__globals__["parse_twse_indices"] = parse
    buf = io.StringIO()
    with W3.env(w), contextlib.redirect_stdout(buf), mock.patch.object(daily, "_collect_key", ck):
        written, errors = daily.collect_for_date(W3.FIRST_DAY, keys)
    return w, written, errors, buf.getvalue()


WARN_R = "  ⚠️  MI_INDEX 找不到報酬指數(臺灣證券交易所)表或欄位不符，報酬指數未寫入（個股與加權指數照常）"
WARN_P = "  ⚠️  MI_INDEX 找不到價格指數(臺灣證券交易所)表或欄位不符，類股指數未寫入（個股與加權指數照常）"


def check_once(src=DLY):
    w, wr, er, out = _collect(sample(), src=src)
    w2, *_, out2 = _collect(sample(), keys=("index.TAIEX",), src=src)
    w3, *_, out3 = _collect(None, src=src)                                       # 假世界原本的 MI_INDEX：沒有報酬指數表
    nopx = sample(p=_rows(P_TXT)[1:])                                            # 價格指數表沒有加權那一列 → 加權找不到，新表照寫
    w4, *_, out4 = _collect(nopx, keys=("index.TAIEX",), src=src)
    sql = w.tidx[0][0] if w.tidx else ""
    return (len(w.tidx) == 1 and len(w.tidx[0][1]) == 44 and set(w.tidx[0][1][0]) == {"trade_date", "kind", "seq", "index_name", "close_price", "change"}
            and len(W3._hit(w, "MI_INDEX")) == 1 and wr["prices.TWSE"] == 1100 and wr["index.TAIEX"] == 1 and not er
            and "⚠️  MI_INDEX" not in out and "ℹ️  證交所" not in out and len(w2.tidx) == 1 and len(W3._hit(w2, "MI_INDEX")) == 1
            and len(w3.tidx) == 1 and len(w3.tidx[0][1]) == 1 and out3.count(WARN_R) == 1 and WARN_P not in out3
            and len(w4.tidx) == 1 and "  ⚠️  MI_INDEX 找不到加權指數表" in out4
            and all(s in sql for s in ("MERGE twse_index AS t", "WHEN MATCHED THEN UPDATE SET seq = s.seq, close_price = s.close_price, change = s.change",
                                       "WHEN NOT MATCHED THEN", "ON t.trade_date = s.trade_date AND t.kind = s.kind AND t.index_name = s.index_name")))


def test_once():
    assert check_once()


def check_errors(src=DLY):
    """新表那一步丟 pyodbc.Error（MERGE）、TypeError（報酬指數表的 data 是 null）、SchemaError、KeyError：個股與加權照寫，回傳值相同，印對應 ⚠️，沒有 Traceback。"""
    base = _collect(sample())
    bad = sample()
    bad["tables"][3]["data"] = None
    raise_ = lambda e: lambda *a: (_ for _ in ()).throw(e)
    parse_msg = "  ⚠️  MI_INDEX 證交所指數表解析失敗，類股指數與報酬指數未寫入（個股與加權指數照常）："
    cases = [(dict(data=sample(), fail=db.pyodbc.Error("42S02", "[42S02] Invalid object name 'twse_index'. (208)\n第二行")),
              "  ⚠️  twse_index 寫入失敗（請確認已執行 setup-db）：('42S02', \"[42S02] Invalid object name 'twse_index'. (208)"),
             (dict(data=bad), parse_msg), (dict(data=sample(), parse=raise_(SchemaError("欄位不符"))), parse_msg + "欄位不符"),
             (dict(data=sample(), parse=raise_(KeyError("MI_INDEX"))), parse_msg + "'MI_INDEX'")]
    for kw, msg in cases:
        try:
            w, wr, er, out = _collect(src=src, **kw)
        except Exception:
            return False
        if (wr, er) != base[1:3] or out.count(msg) != 1 or "Traceback" in out or w.rows["prices.TWSE"][W3.FIRST_DAY].n != 1100 \
                or W3.FIRST_DAY not in w.rows["index.TAIEX"] or w.tidx:
            return False
    return True


def test_errors():
    assert check_errors()


def test_closed_and_notes():
    w, wr, _, out = _collect(sample(), publish=False)                        # 休市（stat 非 OK）
    assert w.tidx == [] and "證交所" not in out and "twse_index" not in out and "報酬指數" not in out
    p = _rows(P_TXT)
    p[19][5], p[0][5] = "停止計算", "基期調整"
    w, wr, _, out = _collect(sample(p=p))
    assert "  ℹ️  證交所指數特殊處理註記：發行量加權股價指數（基期調整）、半導體類指數（停止計算）\n" in out and len(w.tidx[0][1]) == 44
    for r in p[1:4]:
        r[5] = "x"
    w, wr, _, out = _collect(sample(p=p))
    assert "、水泥窯製類指數（x）、塑膠化工類指數（x）…等 5 個\n" in out
    # 資料集鍵、SPECS、回補秒數不變（R87）；DDL
    keys = repr((daily.DAY_KEYS, daily.DATASET_KEYS, [s.key for s in health.SPECS], history.SECONDS_PER_KEY, history.SHARED))
    assert hashlib.sha1(keys.encode()).hexdigest()[:12] == "a4d473ff047f"
    ddl = next(x for x in db.DDL if "twse_index" in x)
    for s in ("IF OBJECT_ID('twse_index') IS NULL", "kind        CHAR(1)       NOT NULL", "seq         SMALLINT      NOT NULL",
              "index_name  NVARCHAR(40)  NOT NULL", "close_price DECIMAL(12,2) NOT NULL", "change      DECIMAL(12,2) NULL",
              "CONSTRAINT UQ_twse_index UNIQUE (trade_date, kind, index_name)"):
        assert s in ddl, s
    mi = next(x for x in db.DDL if "CREATE TABLE market_index" in x)
    assert hashlib.sha1(mi.encode()).hexdigest()[:12] == "848829684373" and db.DDL.index(mi) + 1 == db.DDL.index(ddl)
    assert "twse_index（第 51 輪）、etf_holding_gaps\")" in inspect.getsource(db.setup_database)


def test_history_hint():
    src = inspect.getsource(history.run_history)
    a = '        if force:                                       # 第 51 輪 D202：--force 時上一句不成立（重跑會從 --start 重抓）\n'
    b = '            print(f"   這次有 --force：重跑會從頭重抓，請改用 --start {blocked_at} 接續。")\n'
    assert src.count(a + b) == 1 and src.index("已寫入的日期會自動跳過。\")\n" + a) < src.index(b) < src.rindex("    print(\"🎉 補抓完成！\")")
    main = (ROOT / "twstock" / "__main__.py").read_text(encoding="utf-8")
    assert ("只補加權指數歷史\n  python -m twstock history --start 2025-10-30 --only index --force   重抓加權指數並補證交所類股指數、報酬指數"
            "（會覆寫既有加權指數；中斷時改用 --start 停下那天接續）\n") in main


# ─── 匯出（驗收 12～19）──────────────────────────────────────
def check_sx(src=EXP):
    f = _fn(export, src, "sx_export")
    P = daily.parse_twse_indices(sample(), D3)["P"]
    sx, off, site = f(_sxp(P), [D3], D3, IND)
    pct = {r[0]: r[3] for r in sx["r"]}
    ren = [(n.replace("半導體類", "半導體業類"), c, ch) for n, c, ch in _sxp(P)[D3]]
    sx2, off2, site2 = f({D3: ren}, [D3], D3, IND | {"存託憑證"})
    # 5／20 日：25 個交易日，每天 2 類；B 在往前第 5 天沒有列
    days = [date(2026, 10, 1) + timedelta(days=i) for i in range(25)]
    sp = {d: [("A類指數", 100 + i, 1), ("B類指數", 50 + i, -1)] if d != days[-6] else [("A類指數", 100 + i, 1)] for i, d in enumerate(days)}
    s25 = f(sp, days, days[-1], {"A", "B"})[0]
    s10 = f({d: sp[d] for d in days[-10:]}, days[-10:], days[-1], {"A", "B"})[0]
    old = f({d: v for d, v in sp.items() if d < days[-1]}, days, days[-1], {"A", "B"})[0]
    return (len(sx["r"]) == 32 and [r[0] for r in sx["r"]][:3] == ["水泥", "食品", "塑膠"] and "電腦及週邊設備" in pct and "電子工業" not in pct
            and not {"化學生技醫療", "水泥窯製", "塑膠化工", "機電"} & set(pct) and off == [] and site == [] and sx["d"] == "2026-11-03"
            and (pct["半導體"], pct["玻璃陶瓷"], pct["油電燃氣"], pct["塑膠"], pct["食品"], pct["生技醫療"]) == (-3.03, 5.36, -7.17, -8.74, 0.02, -0.01)
            and sx["r"][0] == ["水泥", 133.73, -1.61, -1.19, None, None] and sx["b5"] is None and sx["b20"] is None
            and len(sx2["r"]) == 31 and "半導體" not in [r[0] for r in sx2["r"]] and off2 == ["半導體業"] and site2 == ["半導體", "存託憑證"]
            and len(s25["r"]) == 2 and s25["b5"] == str(days[-6]) and s25["b20"] == str(days[-21]) and s25["r"][0][4:] == [round((124 / 119 - 1) * 100, 2), round((124 / 104 - 1) * 100, 2)]
            and s25["r"][1][4] is None and s25["r"][1][5] == round((74 / 54 - 1) * 100, 2) and s10["b20"] is None and s10["r"][0][5] is None
            and old["d"] == str(days[-2]) and f({}, days, days[-1], {"A"}) == (None, [], [])
            and f({days[0]: [("A類指數", 100, 1), ("B類指數", 50, 1)], days[1]: [("A類指數", 100, None), ("B類指數", 51, None)]}, days[:2], days[1], {"A", "B"})[0]["r"]
            == [["A", 100.0, 0.0, 0.0, None, None], ["B", 51.0, None, None, None, None]])   # QA51-01：平盤 → 0；收盤不同仍是 null


def test_sx():
    assert check_sx()


def check_ixr(src=EXP):
    f, g = _fn(export, src, "ixr_export"), _fn(export, src, "ixr_perf")
    d = [date(2025, 10, 30), date(2025, 10, 31), date(2025, 11, 3)]
    got = f(d, {d[0]: 69852.10, d[2]: 70500.5})
    ok = (list(got) == ["d", "TAIEXR"] and json.dumps(got, separators=(",", ":")) ==
          '{"d":["2025-10-30","2025-10-31","2025-11-03"],"TAIEXR":[69852.1,null,70500.5]}')
    days = [d for d in (date(2025, 10, 30) + timedelta(days=i) for i in range(400)) if d.weekday() < 5]
    w52 = days[-1] - timedelta(days=365)
    idx = {d: 100 + i * 0.7 for i, d in enumerate(days) if d != days[-61]}
    pf = export.stock_perf(days, [1.0] * len(days), days, idx, w52)
    xp = g(days, idx, w52)
    return ok and [r[:2] for r in xp] == [r[:2] for r in pf] and [r[2] for r in xp] == [export._f(export.index_return(idx, r[1] and date.fromisoformat(r[1]), days[-1])) for r in xp] \
        and xp[2][2] is None and len(xp) == 6 and all(r[0] != "s" for r in xp)


def test_ixr():
    assert check_ixr()


MSG = ["  📌 證交所指數 2026-11-03：類股 32 類；加權報酬指數 2／3 天", "  📌 類股名稱對不到：官方 半導體業；本站 --"]


def check_wiring(src=EXP):
    i = src.index('    print(f"  📌 ETF 個股 {n_etf} 檔')
    seg = src[src.index("\n", i) + 1:src.index("    if bad_all:", i)]
    out = []
    run = lambda **ns: exec("\n".join(l[4:] for l in seg.splitlines()), {"print": lambda *a: out.append(" ".join(map(str, a))), **ns})
    days = [date(2026, 10, 30), date(2026, 11, 2), D3]
    run(tx=None)
    run(tx=1, sx={"d": "2026-11-03", "r": [0] * 32}, ixr_close={days[0]: 1, D3: 2}, p_days=days, sx_off=[], sx_site=[])
    run(tx=1, sx={"d": "2026-11-03", "r": [0] * 32}, ixr_close={days[0]: 1, D3: 2}, p_days=days, sx_off=["半導體業"], sx_site=[])
    a = '    _write(SITE_DATA_DIR / "ix.json", ix_export(p_days, idx_close["TWSE"]))   # 第 48 輪 F48-1：比較頁的交易日曆＋加權收盤\n'
    b = '    _write(SITE_DATA_DIR / "ixr.json", ixr_export(p_days, ixr_close))'
    j = src.index('    latest["alerts"]["w"] = alert_watch(')
    return (out == ["  📌 證交所指數：尚未建立 twse_index（請執行 setup-db），類股指數與含息線不輸出", MSG[0], *MSG] and src.count(a + b) == 1
            and src.count("ix_export(") == 2 and j < src.index('        latest["sx"] = sx') < src.index('        latest["ixr"] = {"d": str(latest_date), "pf": ixr_perf(p_days, ixr_close, w52_start)}')
            < src.index("    S = screen_build(") < src.index('    _write(SITE_DATA_DIR / "latest.json", latest)')
            and src.index("index_rows[code].append((d, c, ch))\n    tx = _load_twse_index(cur)") < src.index("    conn.close()\n    mlast = ")
            and src.count("def ixr_export(") == 1 and src.index("def ix_export(") < src.index("def ixr_export(") < src.index("def sx_export(") < src.index("def stock_perf(")
            and "    if latest_date in ixr_close:\n" in src and "ORDER BY trade_date, kind, seq" in src)


def test_wiring():
    assert check_wiring()
    h = lambda f: hashlib.sha1(inspect.getsource(getattr(export, f)).encode()).hexdigest()[:12]
    assert [h(f) for f in ("stock_perf", "period_return", "index_return", "ix_export", "etf_export", "etf_perf")] == \
        ["013dc5a6b765", "6898133f9289", "7de5578d4299", "26f1b6051ca4", "711fa2b7790c", "1149902d31da"]


class Cur:
    """_load_twse_index 用：OBJECT_ID 回 None／1，列照 SQL 的 ORDER BY 給。"""

    def __init__(self, exists, rows=()):
        self.exists, self.rows, self.r = exists, rows, None

    def execute(self, sql, *a):
        self.r = [(self.exists,)] if "OBJECT_ID" in sql else list(self.rows)
        return self

    def fetchone(self):
        return self.r[0]

    def __iter__(self):
        return iter(self.r)


def test_load():
    assert export._load_twse_index(Cur(None)) is None
    rows = [(D3, "P", "水泥類指數", 133.73, -1.61), (D3, "P", "食品類指數", 1967.03, 0.36), (D3, "R", "發行量加權股價報酬指數", 100144.27, -3728.97)]
    assert export._load_twse_index(Cur(1, rows)) == ({D3: 100144.27}, {D3: [("水泥類指數", 133.73, -1.61), ("食品類指數", 1967.03, 0.36)]})


# ─── 畫面：類股指數表（驗收 20～22）───────────────────────────
SX = export.sx_export(_sxp(daily.parse_twse_indices(sample(), D3)["P"]), [D3], D3, IND)[0]
SX_RUN = r"""
const out = [], L = { date: '2026-11-03', sx: SX }, X = { date: '2026-11-04', sx: Object.assign({}, SX, { b5: '2026-10-27', b20: '2026-10-06' }) };
const Y = { date: '2026-11-03', sx: Object.assign({}, SX, { r: SX.r.map((r, i) => r.slice(0, 4).concat([i % 3 ? i % 4 : null, null])) }) };
for (const [st, l] of [[{}, L], [{ sxAll: true }, L], [{ sxSort: { k: 'p', d: 1 }, sxAll: true }, L], [{ sxSort: { k: 'r5', d: -1 }, sxAll: true }, Y], [{}, X], [{}, { date: 'x' }]]) {
  App = st; out.push(sxCard(l)); }
console.log(JSON.stringify(out));"""


def check_sx_card(app=APP):
    js = "\n".join(_grab(app, n) for n in ("fmt", "sgn", "cls", "md", "noteHTML", "sxCard")) + f"\nlet App = {{}};\nconst SX = {json.dumps(SX, ensure_ascii=False)};\n" + SX_RUN
    o = _node(js)
    if o is None or o == "ERR":
        return o is None
    a, b, c, y, x, none = o
    nm = lambda h: re.findall(r'<td class="nm"><b>([^<]+)</b></td>', h)
    short = "證交所編製的上市類股價格指數，不含股息；和泡泡圖、錢流的本站自算類股不同"
    full = ("證交所每天公布的上市類股價格指數：依成分股市值加權，只含上市股票，不含股息；收盤與漲跌點數為官方數字，漲跌 % = 漲跌點數 ÷ 前一日收盤。5 日、20 日 = 從往前第 5、20 個交易日{}"
            "的收盤起算，和選股的 5 日、20 日報酬同一個起點；本站沒有那天的指數時寫「--」。「電子工業」「化學生技醫療」兩個合併類別、水泥窯製等綜合類別與大盤、主題指數不列入。"
            "泡泡圖、錢流的類股是本站依成分股自算，含上櫃股票，和這裡的數字不會相同。點「漲跌」「5 日」「20 日」可以換排序，再點一次反過來排。")
    v = [(i % 4 if i % 3 else None, i, r[0]) for i, r in enumerate(SX["r"])]       # Y：5 日由高到低，null 最後，同值依官方順序
    want = [n for _, _, n in sorted((x for x in v if x[0] is not None), key=lambda x: (-x[0], x[1]))] + [n for x, _, n in v if x is None]
    return (nm(a) == ["玻璃陶瓷", "食品", "生技醫療", "運動休閒", "汽車", "觀光餐旅", "造紙", "其他", "水泥", "鋼鐵"] and len(nm(b)) == 32
            and nm(c)[:3] == ["塑膠", "光電", "油電燃氣"] and nm(b).index("鋼鐵") + 1 == nm(b).index("橡膠") and nm(c).index("鋼鐵") + 1 == nm(c).index("橡膠")
            and '<section class="sec card sx"><div class="sec-h"><h2>類股指數</h2><span class="muted small">證交所，上市，11/03</span><span class="sp"></span><button class="chip" id="sxMore">顯示全部</button></div>' in a
            and '<button class="chip" id="sxMore">只顯示前 10</button>' in b and '<td class="num dn">-3.03%<span class="sub2">-45.17</span></td>' in b
            and '<thead><tr><th>類股</th><th>收盤</th><th class="sort" data-k="p">漲跌 ▼</th><th class="sort" data-k="r5">5 日</th><th class="sort" data-k="r20">20 日</th></tr></thead>' in a
            and '<th class="sort" data-k="p">漲跌 ▲</th><th class="sort" data-k="r5">5 日</th>' in c and '<th class="sort" data-k="r5">5 日 ▼</th>' in y
            and '<td class="num dn">1,446.44</td>' in b and '<td class="num flat">--</td>' in a and "--%" not in "".join(o) and "data-code" not in b and "data-group" not in b
            and f"<summary>{short}<i>說明</i></summary><div>{full.format('')}</div>" in a and f"<div>{full.format('（10/27、10/06）')}</div>" in x
            and "證交所，上市，11/03（尚未更新）" in x and none == "" and nm(y) == want)


def test_sx_card():
    assert check_sx_card()
    flow = "    </section>\n\n    ${sxCard(L)}\n    ${flowNote()}<section class=\"sec grid g2\">"
    assert APP.count(flow) == 1 and APP.index("<h2>錢從哪裡流出</h2>") < APP.index(flow)
    assert len(re.findall(r"noteHTML\((['`])(.+?)\1,", APP + STK)) == 8 and "localStore" not in _grab(APP, "sxCard")
    assert "$('#sxMore')?.addEventListener('click', () => { App.sxAll = !App.sxAll; renderToday(); });" in APP
    assert "$('#view').querySelectorAll('.sx th.sort').forEach(el => el.addEventListener('click', () => { const k = el.dataset.k, o = App.sxSort || { k: 'p', d: -1 };\n" \
           "    App.sxSort = { k, d: o.k === k ? -o.d : -1 }; renderToday(); }));" in APP


# ─── 畫面：比較頁（驗收 23～25）──────────────────────────────
G0 = "async function getJSON(u) { if (u === 'data/ix.json' && IXOK) return IX; throw new Error('404 ' + u); }"
CMP_RUN = r"""
let IXR = null, CB = null; const SER = [];
window.LightweightCharts = { createChart: () => ({ addLineSeries: o => { const s = { o, setData() {}, createPriceLine() {} }; SER.push(s); return s; },
  timeScale: () => ({ fitContent() {} }), subscribeCrosshairMove: f => { CB = f; } }) };
const R = DD.map((_, i) => 200 + 3 * i), cut = (k, v) => ({ d: DD, TAIEXR: R.map((x, i) => i === k ? v : x) });
const CASES = [cut(-1), cut(0, null), cut(29, null), { d: DD.slice(1), TAIEXR: R.slice(1) }, cut(5, null), null];
(async () => { const out = [];
  for (const xr of CASES) { IXR = xr; App.cmpIx = null; App.cmpIxr = null; SER.length = 0; CB = null; location.hash = '#/compare/2330/w';
    await window.renderCompare('2330', 'w'); const legs = [];
    if (CB) for (const i of [5, 6, 29]) { CB({ logical: i, time: 't' }); legs.push(E['#cmpL'].innerHTML); }
    out.push([E['#view'].innerHTML, SER.map(s => [s.o.color, s.o.lineStyle, s.o.lineWidth]), legs]); }
  const e = cmpLine(DD, DD, R, DD[0]); out.push([pc(e.ret), pc(e.dd[0]), e.vol == null ? '--' : fmt(cmpR(e.vol), 2) + '%']);
  console.log(JSON.stringify(out)); })();"""


def check_cmp(cmp=CMP):
    js = "\n".join([_grab(APP, n) for n in ("fmt", "sgn", "cls", "esc", "md")] + [_grab(STK, "adjFactors")]) + "\n"
    dom = T48.DOM.replace(G0, "async function getJSON(u) { if (u === 'data/ix.json') return IX; if (u === 'data/ixr.json' && IXR) return IXR; throw new Error('404 ' + u); }")
    dom = dom.replace("css = () => ''", "css = n => n")
    assert G0 in T48.DOM
    o = _node(js + f"const LL = {json.dumps(T48.NL)};" + dom + cmp + CMP_RUN)
    if o is None or o == "ERR":
        return o is None
    (h0, s0, l0), (h1, s1, l1), (h2, *_), (h3, *_), (h4, s4, l4), (h5, s5, l5), (ret, dd, vol) = o
    ring = "background:none;box-shadow:inset 0 0 0 1.5px var(--text2)"
    leg = ('<span class="lg"><i class="dash"></i>加權指數（不含息）</span><span class="lg">實線 = 各檔（股票還原價、ETF 含息）</span>'
           '<span class="lg"><i style="background:none;height:0;border-top:2px dotted var(--text2);border-radius:0"></i>加權報酬指數（含息）</span></div>')
    row = (f'<b>加權指數（不含息）</b></td>' + "{}" + f'</tr><tr><td><i class="cmp-dot" style="{ring}"></i><b>加權報酬指數（含息）</b></td>'
           f'<td class="num up">{ret}%</td><td class="num">0.00%</td><td class="num">{vol}</td></tr></tbody>')
    note = ("<div class=\"muted small\">點線 = 證交所「發行量加權股價報酬指數」：把成分股的現金股利再投入指數計算，口徑接近股票還原價與 ETF 含息報酬；"
            "兩條加權線起點都是 0%，分開的幅度大致是期間內成分股發放的現金股利。</div>")
    tip = lambda d: f'<div class="muted small">加權報酬指數（含息）在 {d} 沒有資料，這個區間不畫點線。</div>'
    m = re.search(r"<b>加權指數（不含息）</b></td>(.*?)</tr>", h0)
    plain = lambda h: "含息 <b>" not in h and "<b>加權報酬指數（含息）</b>" not in h and "dotted" not in h
    return (leg in h0 and m is not None and row.format(m.group(1)) in h0 and h0.index("（--）。</div>" + note) < h0.index('<details class="note">')
            and s0 == [["--text2", 2, 1], ["--text2", 1, 2], ["--cmp1", 0, 2]] and s1 == [["--text2", 2, 1], ["--cmp1", 0, 2]] and s5 == s1
            and l0[2].endswith(f'加權 <b>+29.00%</b></span><span><i class="cmp-dot" style="{ring}"></i>含息 <b>{ret}%</b></span>')
            and tip("2025-10-30") in h1 and plain(h1) and all(plain(x) for x in l1) and tip("2025-11-28") in h2 and tip("2025-10-30") in h3 and plain(h3)
            and "含息 <b>--</b>" in l4[0] and "含息 <b>+" in l4[1] and s4 == s0 and note in h4
            and plain(h5) and all(plain(x) for x in l5) and "加權報酬指數" not in h5 and "差距" not in h0 + h1 and "名次" not in h0)


def test_cmp():
    assert check_cmp()
    fns = T48.FNS + ("CMP_MAX", "cmpUrl", "pc")
    assert hashlib.sha1("\n".join(_grab(CMP, n) for n in fns).encode()).hexdigest()[:12] == "1dccb16dabca"   # 純函式 0 行改動


# ─── 畫面：近期表現（驗收 26）────────────────────────────────
XPF = [[5, "2026-11-13", 1.95], [20, "2026-10-21", -15.1], [60, "2026-08-21", -14.2], [120, "2026-05-27", -13.05], ["y", "2025-12-31", 38.9], ["w", "2025-11-20", None]]
XLINE = ('</tbody></table></div><div class="muted small" style="margin-top:6px" title="證交所發行量加權股價報酬指數：成分股的現金股利再投入指數計算；表格的加權指數欄是價格指數，不含股息">'
         '加權報酬指數（含息）同期：5 日 +1.95%、20 日 -15.10%、60 日 -14.20%、120 日 -13.05%、今年以來 +38.90%、52 週 --</div><div class="muted small" style="margin-top:6px"><details')


def check_perf(stk=STK):
    js = "\n".join(_grab(APP, n) for n in ("fmt", "sgn", "cls", "md", "noteHTML")) + "\n" + "\n".join(_grab(stk, n) for n in ("PF_NAME", "perfHTML")) + \
        f"\nconst App = {{ latest: {{ date: '2026-11-20', ixr: {{ d: '2026-11-20', pf: {json.dumps(XPF)} }} }} }}, PF = {json.dumps(T46.PF)};\n" + r"""
const a = [perfHTML(PF, 'TWSE', null), perfHTML(PF, 'TPEx', null, '00679B'), perfHTML(PF, 'TWSE', null, '0050'), perfHTML(PF, 'TPEx', null)];
App.latest.ixr.d = '2026-11-19'; a.push(perfHTML(PF, 'TWSE', null)); delete App.latest.ixr; a.push(perfHTML(PF, 'TWSE', null));
console.log(JSON.stringify(a));"""
    o = _node(js)
    if o is None or o == "ERR":
        return o is None
    s, b, e, otc, stale, none = o
    return all(h.count(XLINE) == 1 for h in (s, b, e)) and "加權報酬指數" not in otc + stale + none


def test_perf():
    assert check_perf() and T46.check_card(STK)


# ─── 用詞、node 14、?v=、文件（驗收 27～32）──────────────────────
def _new_segs(app=APP, stk=STK, cmp=CMP, exp=EXP, dly=DLY):
    segs = [_grab(app, "sxCard")] + [l for f in (app, stk, cmp, exp, dly) for l in f.splitlines()
                                     if any(k in l for k in ("第 51 輪", "sxAll", "sxSort", "ixr", "twse_index", "證交所指數", "類股名稱對不到"))]
    segs += [l for l in cmp.splitlines() if any(k in l for k in ("XR", "ixr", "miss", "ring"))]
    for n in ("parse_twse_indices", "merge_twse_index", "_save_twse_indices"):
        segs.append(_grab_py(dly, n))
    for n in ("ixr_export", "ixr_perf", "sx_export", "_load_twse_index"):
        segs.append(_grab_py(exp, n))
    return "\n".join(segs)


def _grab_py(src, name):
    return re.search(rf"^def {name}\(.*?(?=^\S)", src, re.M | re.S).group(0)


def check_words(cmp=CMP, app=APP, stk=STK):
    seg = _new_segs(app, stk, cmp)
    rd = next(l for l in README.splitlines() if l.startswith("- 第 51 輪證交所類股指數與加權報酬指數"))
    cnew = "\n".join(l for l in cmp.splitlines() if any(k in l for k in ("XR", "ixr", "miss", "ring")))
    return all(w not in seg + rd for w in ADVICE) and "差距" not in cnew and all(w not in seg for w in (".at(", "replaceAll", "||=", "&&=", "??="))


def test_words_node14():
    assert check_words()


def test_version_and_docs():
    for f in ("app.js", "stock.js", "app.css", "tools.js", "help.js", "compare.js"):
        v = hashlib.sha1((SITE / f).read_bytes()).hexdigest()[:8]
        assert f"{f}?v={v}" in HTML, f"index.html 要改成 {f}?v={v}"
    for s in ("tools.js?v=0a050889", "help.js?v=a5a5a7e8"):
        assert s in HTML, s
    assert "app.js?v=692538e8" not in HTML and "stock.js?v=e527a385" not in HTML and "compare.js?v=1c11197d" not in HTML
    assert HTML.count("https://") == 2 and [m.group(1) for m in re.finditer(r'<script src="(\w+)\.js', HTML)] == ["app", "stock", "tools", "help", "compare"]
    assert "python3 tests/test_iter51.py" in README and "第 51 輪" in (ROOT / "docs" / "iterations" / "README.md").read_text(encoding="utf-8")
    r = next(l for l in README.splitlines() if l.startswith("- 第 51 輪證交所類股指數與加權報酬指數"))
    for s in ("twse_index", "ixr.json", "TAIEXR", "`sx`", "`ixr`", "R74", "R84", "R87", "--force", "--start", "backup", "上櫃股票不加"):
        assert s in r, s
    assert "第 23 輪" not in r


# ─── 實際資料（PG 回補、匯出後；驗收 35、36）─────────────────────
def test_site_data():
    f = DATA / "ixr.json"
    L = json.loads((DATA / "latest.json").read_text(encoding="utf-8")) if (DATA / "latest.json").exists() else {}
    if not f.exists() or "sx" not in L or "ixr" not in L:
        print("  （尚未用第 51 輪匯出或尚未回補，略過實際資料）")
        return
    x, ix = json.loads(f.read_text(encoding="utf-8")), json.loads((DATA / "ix.json").read_text(encoding="utf-8"))
    assert list(x) == ["d", "TAIEXR"] and x["d"] == ix["d"] and f.stat().st_size <= 8 * 1024 and L["sx"]["d"] == L["date"] == L["ixr"]["d"]
    pf = json.loads((DATA / "stocks" / "2330.json").read_text(encoding="utf-8"))["pf"]
    assert [r[:2] for r in L["ixr"]["pf"]] == [r[:2] for r in pf if r[0] != "s"]
    assert L["sx"]["b5"] == pf[0][1] and L["sx"]["b20"] == pf[1][1] and len(L["sx"]["r"]) == 32
    for k, b, v in L["ixr"]["pf"]:
        i = x["d"].index(b)
        assert v == (None if x["TAIEXR"][i] is None else round((x["TAIEXR"][-1] / x["TAIEXR"][i] - 1) * 100, 2)), k
    if "2026-11-03" in x["d"]:
        assert x["TAIEXR"][x["d"].index("2026-11-03")] == 100144.27


# ─── 反證：原始碼改壞，對應的檢查要失敗 ─────────────────────────
def _mut(src, old, new):
    assert src.count(old) >= 1, old
    return src.replace(old, new, 1)


def test_contrast():
    rows = [
        ("R 表用「指數」定位", check_parse, DLY, 'for kind, title, first, _ in TWSE_INDEX_TABLES:', 'for kind, title, _, _ in TWSE_INDEX_TABLES:\n        first = "指數"'),
        ("不去重", check_abnormal, DLY, "name in seen or ", ""),
        ("收盤 ≤ 0 不略過", check_abnormal, DLY, "close is None or close <= 0", "close is None"),
        ("不設旗標（寫兩次）", check_once, DLY, '    cache["tidx"] = True\n', ""),
        ("新表放到 if taiex 裡", check_once, DLY, '            _save(merge_market_index, [taiex])\n        elif rows:\n            print("  ⚠️  MI_INDEX 找不到加權指數表")\n        if rows:\n',
         '            _save(merge_market_index, [taiex])\n            _save_twse_indices(d, cache)\n        elif rows:\n            print("  ⚠️  MI_INDEX 找不到加權指數表")\n        if False:\n'),
        ("不攔 pyodbc.Error", check_errors, DLY, "except db.pyodbc.Error as e:", "except ZeroDivisionError as e:"),
        ("不攔解析錯誤", check_errors, DLY, "except PARSE_ERRORS as e:", "except ZeroDivisionError as e:"),
        ("寫死 32 類", check_sx, EXP, "        if SX_ALIAS.get(show, show) not in industries:", f"        if SX_ALIAS.get(show, show) not in {sorted(IND)!r}:"),
        ("不做名稱對照", check_sx, EXP, "        if SX_ALIAS.get(show, show) not in industries:", "        if show not in industries:"),
        ("不排除合併類", check_sx, EXP, "        if nm in SX_SKIP:\n            continue\n", ""),
        ("5／20 日用前一天補", check_sx, EXP, "for nm, c, _ in sxp.get(b, ())}", "for nm, c, _ in sxp.get(b, ()) + sxp.get(days[days.index(b) - 1], [])}"),
        ("ixr.pf 基準日差一天", check_ixr, EXP, "[(n, days[-1 - n] if len(days) > n else None) for n in PF_DAYS] + [(\"y\", days[y - 1] if y else None), (\"w\", days[w - 1] if w else None)]\n    return [[k",
         "[(n, days[-n] if len(days) > n else None) for n in PF_DAYS] + [(\"y\", days[y - 1] if y else None), (\"w\", days[w - 1] if w else None)]\n    return [[k"),
        ("函式名用 ix_export2(", check_wiring, EXP, "def ixr_export(", "def ix_export2("),
        ("訊息缺值寫 0", check_wiring, EXP, "'、'.join(sx_site) or '--'", "'、'.join(sx_site) or '0'"),
        ("sgn(null) + '%'", check_sx_card, APP, "pv = v => v == null ? '--' : sgn(v) + '%'", "pv = v => sgn(v) + '%'"),
        ("null 不排最後", check_sx_card, APP, "(x == null || y == null ? (x == null) - (y == null) : (x - y) * o.d)", "((x - y) * o.d)"),
        ("同值不依官方順序", check_sx_card, APP, " || a[1] - b[1]; })", " || b[1] - a[1]; })"),
        ("比較頁起點缺值仍畫線", check_cmp, CMP, "[X.b, X.end].find(d => ixr.TAIEXR[ix.d.indexOf(d)] == null)", "undefined"),
        ("比較頁長度不同也畫", check_cmp, CMP, "ixr.d.length !== ix.d.length || ixr.d[ixr.d.length - 1] !== X.end ? X.b : ", ""),
        ("十字線缺值寫 0", check_cmp, CMP, "XR.line[i][2] ? '--' : pc(XR.line[i][1]) + '%'", "pc(XR.line[i][1]) + '%'"),
        ("perfHTML 引用新頂層常數", check_perf, STK, 'title="證交所發行量加權股價報酬指數：成分股的現金股利再投入指數計算；表格的加權指數欄是價格指數，不含股息"', 'title="${PF_XR_TIP}"'),
        ("上櫃股票也加", check_perf, STK, "(mkt === 'TWSE' || etf)", "true"),
        ("用詞（清單中的任一詞）", check_words, CMP, "這個區間不畫點線。", f"這個區間{sorted(T47.ADVICE)[0]}不畫點線。"),
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
