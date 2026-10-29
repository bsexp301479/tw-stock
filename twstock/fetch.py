"""
共用 HTTP 請求：依網站節流 + 封鎖偵測 + 退避重試。

證交所/櫃買/公開資訊觀測站對短時間大量請求會封鎖 IP，封鎖時回傳的通常是
HTML 錯誤頁或 403/429，而不是 JSON。這裡把它和「休市沒資料」明確區分：
封鎖 → 退避重試，仍失敗就丟 FetchError，呼叫端不可寫入半套資料。
"""
import ssl
import time
from decimal import InvalidOperation
from urllib.parse import urlparse

import certifi
import requests
import requests.adapters
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class FetchError(Exception):
    """抓取失敗（被封鎖、網路錯誤）；與「休市沒資料」區分。"""


# ─── SSL：證交所/櫃買憑證不符合 Python 3.13 的嚴格檢查 ─────────
def _build_ssl_context() -> ssl.SSLContext:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.load_verify_locations(certifi.where())
    ctx.verify_flags &= ~ssl.VERIFY_X509_STRICT
    if hasattr(ssl, "OP_LEGACY_SERVER_CONNECT"):
        ctx.options |= ssl.OP_LEGACY_SERVER_CONNECT
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    return ctx


class _TLSAdapter(requests.adapters.HTTPAdapter):
    def __init__(self, **kwargs):
        self.ssl_context = _build_ssl_context()
        super().__init__(**kwargs)

    def init_poolmanager(self, *args, **kwargs):
        kwargs["ssl_context"] = self.ssl_context
        super().init_poolmanager(*args, **kwargs)

    def proxy_manager_for(self, proxy, **proxy_kwargs):
        proxy_kwargs["ssl_context"] = self.ssl_context
        return super().proxy_manager_for(proxy, **proxy_kwargs)


_SESSION = requests.Session()
_SESSION.mount("https://", _TLSAdapter())
_SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-TW,zh;q=0.9",
})

# 同一主機兩次請求的最短間隔（秒）
MIN_INTERVAL = {
    "www.twse.com.tw":     3.5,   # 證交所限制最嚴，約 5 秒 3 次以上就可能被封
    "www.tpex.org.tw":     3.0,
    "openapi.twse.com.tw": 1.0,
    "mopsov.twse.com.tw":  3.0,
    "www.taifex.com.tw":   3.0,
    "ic.tpex.org.tw":      2.0,
}
DEFAULT_INTERVAL = 3.0
RETRY_BACKOFF = (30, 60, 120)   # 失敗後依序等待秒數，用完仍失敗就放棄
_last_request: dict = {}


def request(method: str, url: str, expect_json: bool = True, **kwargs):
    host = urlparse(url).hostname
    last_err = None
    for attempt in range(len(RETRY_BACKOFF) + 1):
        wait = MIN_INTERVAL.get(host, DEFAULT_INTERVAL) - (time.monotonic() - _last_request.get(host, 0))
        if wait > 0:
            time.sleep(wait)
        _last_request[host] = time.monotonic()
        try:
            resp = _SESSION.request(method, url, timeout=30, **kwargs)
            if resp.status_code in (403, 429) or resp.status_code >= 500:
                raise FetchError(f"HTTP {resp.status_code}（可能被限流）")
            resp.raise_for_status()
            return resp.json() if expect_json else resp   # 封鎖頁是 HTML → json() 會丟 ValueError
        except (requests.RequestException, ValueError, FetchError) as e:
            last_err = e
            if attempt < len(RETRY_BACKOFF):
                pause = RETRY_BACKOFF[attempt]
                print(f"  ⏳ {host} 請求失敗（{e}），{pause} 秒後重試 [{attempt + 1}/{len(RETRY_BACKOFF)}]")
                time.sleep(pause)
    raise FetchError(f"{host} 連續失敗，可能已被封鎖，請稍後再跑：{last_err}")


# ─── 資料清理 ─────────────────────────────────────────────
def clean_number(val, cast=float):
    """清理數字字串（去除逗號、空白、+ 號）；無法解析回傳 None。"""
    if val is None:
        return None
    try:
        cleaned = str(val).replace(",", "").replace(" ", "").replace("+", "").strip()
        if cleaned in ("--", "-", "", "N/A", "---"):
            return None
        return cast(cleaned)
    except (ValueError, InvalidOperation):
        return None


def is_valid_stock_code(code: str) -> bool:
    """
    只保留上市/上櫃一般公司股票：4~5 碼純數字，且不以 00（上市 ETF）/ 06（上櫃 ETF）開頭。
    權證（6 碼以上）、債券 ETF（英數混合）、指數都會被排除。
    """
    code = code.strip()
    return code.isdigit() and 4 <= len(code) <= 5 and not code.startswith(("00", "06"))
