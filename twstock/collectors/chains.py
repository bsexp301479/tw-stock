"""
產業鏈族群（櫃買中心「產業價值鏈資訊平台」ic.tpex.org.tw）→ industry_chains。

平台沒有下載功能，但每條產業鏈頁面的 HTML 裡直接帶有公司代號：
  <div id="companyList_D300" title="IC/晶圓製造">           區段
    <div id="sc_link_D310">► 晶圓製造 (27家)</div>          細項名稱
    <table id="sc_company_D310"> … stk_code=2330 …           細項公司
同一個區段在頁面上會出現兩次（桌機/手機版），寫入前去重。
"""
import re

from .. import db
from ..fetch import request

BASE = "https://ic.tpex.org.tw/"
SKIP = {"X000"}    # 「其他」產業鏈太雜，不當族群

_TOKEN = re.compile(
    r'id="companyList_(?P<seg>[A-Z0-9]+)" title="(?P<seg_name>[^"]*)"'
    r'|id="sc_link_(?P<link>[A-Z0-9]+)"[^>]*>(?P<link_name>.*?)</div>'
    r'|id="sc_company_(?P<sub>[A-Z0-9]+)"'
    r'|stk_code=(?P<code>\d{4,6})"', re.S)


def _text(s: str) -> str:
    s = re.sub(r"<[^>]+>|&nbsp;|&#9658;|►", " ", s)
    return re.sub(r"\s*\(\d+家\)\s*$", "", re.sub(r"\s+", " ", s)).strip()


def _get(url: str) -> str:
    # 回應標頭沒帶 charset，requests 會誤判成 ISO-8859-1；頁面實際是 UTF-8
    return request("GET", url, expect_json=False).content.decode("utf-8", errors="replace")


def fetch_chain_list() -> dict:
    html = _get(BASE)
    chains = {}
    for cid, name in re.findall(r'introduce\.php\?ic=([A-Z0-9]+)"[^>]*>(.*?)</a>', html, re.S):
        name = _text(name)
        if name and cid not in SKIP:
            chains.setdefault(cid, name)
    return chains


def parse_chain(html: str) -> list:
    """回傳 [(區段代碼, 區段名稱, 細項代碼, 細項名稱, 股票代號)]；沒有細項時細項欄位為空字串。"""
    links, rows, seen = {}, [], set()
    seg = seg_name = sub = None
    for m in _TOKEN.finditer(html):
        if m["seg"]:
            seg, seg_name, sub = m["seg"], m["seg_name"].strip(), None
        elif m["link"]:
            links[m["link"]] = _text(m["link_name"])
        elif m["sub"]:
            sub = m["sub"]
        elif m["code"] and seg:
            key = (seg, sub or "", m["code"])
            if key not in seen:
                seen.add(key)
                rows.append((seg, seg_name, sub or "", links.get(sub, "") if sub else "", m["code"]))
    return rows


def update_chains() -> int:
    chains = fetch_chain_list()
    if not chains:
        raise RuntimeError("產業價值鏈平台首頁解析不到任何產業鏈，網站版面可能改了")
    rows = []
    for cid, name in chains.items():
        html = _get(f"{BASE}introduce.php?ic={cid}")
        parsed = parse_chain(html)
        print(f"  🔗 {name}：{len({r[4] for r in parsed})} 家")
        rows += [{"chain_id": cid, "chain_name": name, "segment_id": s, "segment_name": sn,
                  "sub_id": sub, "sub_name": subn, "stock_code": code}
                 for s, sn, sub, subn, code in parsed]

    # 整批替換：平台會增刪公司，以最新一次抓取為準
    conn = db.connect()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM industry_chains")
        cursor.execute("""
            INSERT INTO industry_chains (chain_id, chain_name, segment_id, segment_name, sub_id, sub_name, stock_code)
            SELECT chain_id, chain_name, segment_id, segment_name, sub_id, sub_name, stock_code
            FROM OPENJSON(?) WITH (
                chain_id NVARCHAR(10), chain_name NVARCHAR(50), segment_id NVARCHAR(10),
                segment_name NVARCHAR(100), sub_id NVARCHAR(10), sub_name NVARCHAR(100), stock_code NVARCHAR(10))
        """, db.to_json(rows))
        conn.commit()
    finally:
        conn.close()
    print(f"  ✅ 產業鏈：{len(chains)} 條、{len({r['stock_code'] for r in rows})} 家公司、{len(rows)} 筆對應")
    return len(rows)


def chains_age_days():
    """距離上次更新的天數；從未更新回傳 None。"""
    conn = db.connect()
    try:
        r = conn.cursor().execute(
            "SELECT DATEDIFF(day, MAX(updated_at), GETDATE()) FROM industry_chains").fetchone()
    finally:
        conn.close()
    return r[0] if r else None
