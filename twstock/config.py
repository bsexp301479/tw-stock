"""
專案設定：帳密等敏感資訊從專案根目錄的 .env 讀取（不寫進程式碼），
所有路徑都以專案根目錄為基準，Mac / Windows 通用。
"""
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"             # 自己維護的對照表（concepts.csv）
SITE_DIR = ROOT / "site"             # 靜態網站（部署到雲端的就是這個資料夾）
SITE_DATA_DIR = SITE_DIR / "data"    # export 產生的 JSON
OUTPUT_DIR = ROOT / "output"         # 其他產出（纏論 SVG 等）
LOG_DIR = ROOT / "logs"
TW_TZ = timezone(timedelta(hours=8))   # 台灣沒有日光節約時間；固定位移不需要 tzdata（Windows 沒有內建）


def tw_now() -> datetime:
    return datetime.now(TW_TZ)


def _load_env(path: Path):
    """極簡 .env 解析：KEY=VALUE，# 開頭為註解；已存在的環境變數優先。"""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_env(ROOT / ".env")

DB_CONFIG = {
    "server":   os.environ.get("DB_SERVER", "localhost,1433"),
    "database": os.environ.get("DB_NAME", "TwStock"),
    "username": os.environ.get("DB_USER", "sa"),
    "password": os.environ.get("DB_PASSWORD", ""),
    "driver":   os.environ.get("DB_DRIVER", "ODBC Driver 18 for SQL Server"),
}


def connection_string(database: str = None) -> str:
    c = DB_CONFIG
    return (
        f"DRIVER={{{c['driver']}}};"
        f"SERVER={c['server']};"
        f"DATABASE={database or c['database']};"
        f"UID={c['username']};"
        f"PWD={c['password']};"
        "TrustServerCertificate=yes;"
        "Encrypt=yes;"
    )
