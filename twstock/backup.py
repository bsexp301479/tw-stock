"""
資料庫備份（第 6 輪 S9）：BACKUP DATABASE … COPY_ONLY → RESTORE VERIFYONLY → docker cp 到主機。

COPY_ONLY 不影響其他備份鏈；檔名含日期時間（到秒）、只新增不覆寫；不提供還原指令（還原步驟見 README）。
容器名稱：.env 的 DB_CONTAINER，沒有時找發布 DB_SERVER 埠號的容器（使用者的 MySqlServer、compose 的 twstock-mssql 都適用）。
SQL Server 不在 Docker 裡時用 --direct：由 SQL Server 直接寫到 --out（服務帳號要有該資料夾的寫入權限）。
"""
import os
import subprocess
from datetime import datetime
from pathlib import Path

from .config import DB_CONFIG, ROOT

BACKUP_DIR = ROOT.parent / "_backups"        # 專案上一層，與第 3～5 輪手動備份同一處（不進 repo）
CONTAINER_DIR = "/var/opt/mssql/data"


def _docker(*args) -> str:
    return subprocess.run(["docker", *args], capture_output=True, text=True, check=True).stdout.strip()


def find_container() -> str:
    """DB_CONTAINER 優先；否則找發布 SQL Server 埠號的執行中容器。找不到 → RuntimeError。"""
    name = os.environ.get("DB_CONTAINER")
    if not name:
        port = DB_CONFIG["server"].rpartition(",")[2] if "," in DB_CONFIG["server"] else "1433"
        names = _docker("ps", "--filter", f"publish={port}", "--format", "{{.Names}}").split()
        if len(names) != 1:
            raise RuntimeError(f"找不到唯一一個發布 {port} 埠的 Docker 容器（找到 {len(names)} 個）；"
                               "請在 .env 設定 DB_CONTAINER=容器名稱，SQL Server 不在 Docker 裡時改用 --direct")
        name = names[0]
    # 先確認容器在跑，避免備份寫進容器後才發現複製不出來
    if _docker("inspect", "-f", "{{.State.Running}}", name) != "true":
        raise RuntimeError(f"容器 {name} 沒有在執行")
    return name


def _run_sql(cur, sql: str):
    cur.execute(sql)
    while cur.nextset():            # BACKUP／RESTORE 的進度訊息是多個結果集，要讀完才算執行完
        pass


def backup(out_dir: Path, direct=False, now=None) -> Path:
    """備份並驗證，回傳主機上的檔案路徑。同名檔已存在 → FileExistsError；Docker 問題 → RuntimeError。"""
    from . import db
    name = f"{DB_CONFIG['database']}_{(now or datetime.now()):%Y%m%d_%H%M%S}.bak"
    dest = Path(out_dir).resolve() / name
    if dest.exists():
        raise FileExistsError(f"{dest} 已存在，不覆寫（稍後再執行，或用 --out 指定其他資料夾）")
    container = None if direct else find_container()
    dest.parent.mkdir(parents=True, exist_ok=True)
    disk = str(dest) if direct else f"{CONTAINER_DIR}/{name}"
    try:
        conn = db.connect(autocommit=True)          # BACKUP 不能在交易中執行
        try:
            cur = conn.cursor()
            sql = f"BACKUP DATABASE [{DB_CONFIG['database']}] TO DISK = N'{disk}' WITH COPY_ONLY, INIT"
            try:
                _run_sql(cur, sql + ", COMPRESSION")
            except db.pyodbc.Error as e:
                if "COMPRESSION" not in str(e).upper():
                    raise
                print("ℹ️  這個版本不支援壓縮備份，改用不壓縮")
                _run_sql(cur, sql)
            try:
                _run_sql(cur, f"RESTORE VERIFYONLY FROM DISK = N'{disk}'")      # 只驗證、不還原
            except db.pyodbc.Error as e:
                raise RuntimeError(f"備份檔驗證失敗（RESTORE VERIFYONLY），這份備份不可用：{str(e).splitlines()[0][:200]}") from None
        finally:
            conn.close()
        if not direct:
            _docker("cp", f"{container}:{disk}", str(dest))
    finally:
        if not direct:
            _remove_temp(container, disk)       # 成功或中途失敗都清掉（第 6 輪 QA-03）
    return dest


def _remove_temp(container: str, disk: str):
    """只刪這次自己產生的容器內暫存檔（不存在也不報錯）；刪不掉時印出路徑請使用者處理。"""
    try:
        _docker("exec", container, "rm", "-f", disk)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print(f"⚠️  容器內的暫存備份檔沒有刪除，請自行執行：docker exec {container} rm -f {disk}")


def run(out_dir=None, direct=False) -> int:
    out_dir = Path(out_dir) if out_dir else BACKUP_DIR
    try:
        path = backup(out_dir, direct)
    except FileExistsError as e:
        print(f"❌ {e}")
        return 1
    except FileNotFoundError:
        print("❌ 找不到 docker 指令；SQL Server 不在 Docker 裡時請改用 --direct")
        return 1
    except subprocess.CalledProcessError as e:
        print(f"❌ docker {e.cmd[1]} 失敗（Docker 是否已啟動？）：{(e.stderr or '').strip()[:200]}")
        return 1
    except RuntimeError as e:
        print(f"❌ {e}")
        return 1
    print(f"✅ 備份完成並通過 RESTORE VERIFYONLY：{path}（{path.stat().st_size / 1048576:.1f} MB）")
    return 0
