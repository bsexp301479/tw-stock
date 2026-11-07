"""更新 stocks.industry 與 stocks.shares：證交所 / 櫃買 OpenAPI 公司基本資料的產業別代碼 → 中文名稱、發行股數（第 11 輪）。"""
from .. import db
from ..fetch import clean_number, request

INDUSTRY = {
    "01": "水泥", "02": "食品", "03": "塑膠", "04": "紡織纖維", "05": "電機機械",
    "06": "電器電纜", "08": "玻璃陶瓷", "09": "造紙", "10": "鋼鐵", "11": "橡膠",
    "12": "汽車", "14": "建材營造", "15": "航運", "16": "觀光餐旅", "17": "金融保險",
    "18": "貿易百貨", "19": "綜合", "20": "其他", "21": "化學", "22": "生技醫療",
    "23": "油電燃氣", "24": "半導體", "25": "電腦及週邊", "26": "光電", "27": "通信網路",
    "28": "電子零組件", "29": "電子通路", "30": "資訊服務", "31": "其他電子",
    "32": "文化創意", "33": "農業科技", "34": "電子商務", "35": "綠能環保", "36": "數位雲端",
    "37": "運動休閒", "38": "居家生活",
}


def update_industry() -> int:
    """產業別與發行股數（第 11 輪，借券占股本用；目前股數，不保留歷史）一起更新；只更新有變動的列。"""
    twse = request("GET", "https://openapi.twse.com.tw/v1/opendata/t187ap03_L")
    tpex = request("GET", "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O")
    triples = [(r["公司代號"], r["產業別"], r.get("已發行普通股數或TDR原股發行股數")) for r in twse] + \
              [(r["SecuritiesCompanyCode"], r["SecuritiesIndustryCode"], r.get("IssueShares")) for r in tpex]
    rows = [{"stock_code": c.strip(), "industry": INDUSTRY.get(i.strip(), "其他"), "shares": clean_number(n, int) or None}
            for c, i, n in triples]

    conn = db.connect()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE st SET industry = j.industry, shares = ISNULL(j.shares, st.shares)
            FROM stocks st
            JOIN OPENJSON(?) WITH (stock_code NVARCHAR(10), industry NVARCHAR(50), shares BIGINT) AS j
              ON j.stock_code = st.stock_code
            WHERE ISNULL(st.industry, '') <> j.industry OR (j.shares IS NOT NULL AND ISNULL(st.shares, -1) <> j.shares)
        """, db.to_json(rows))
        changed = cursor.rowcount
        conn.commit()
    finally:
        conn.close()
    print(f"  🏷️  產業別、股數：更新 {changed} 檔")
    return changed
