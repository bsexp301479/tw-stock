"""
台股資料收集與網站產生工具（Mac / Windows 通用）

  python -m twstock setup-db                         建立資料庫與資料表
  python -m twstock collect [--date 2026-10-28]      收集單日（全部重抓覆寫：行情、本益比、法人、月營收、指數、台指期、處置／注意股、除權息事件、三大法人金額）並匯出網站資料
  python -m twstock collect --catch-up [--days 10]   補齊最近 N 個交易日缺的資料（各資料集獨立判斷，可重複執行），有新資料才匯出；排程用這個
  python -m twstock check [--days 20]                檢查各資料集的完整性（唯讀、不連外）；有異常回傳 1
  python -m twstock history --start 2026-01-01       補抓歷史（只補缺的，可中斷重跑）
  python -m twstock history --start 2025-10-30 --only pe      只補本益比／淨值比／殖利率
  python -m twstock history --start 2026-02-23 --only index   只補加權指數歷史
  python -m twstock history --start 2025-10-30 --only tpex_index  只補櫃買指數（一個月一個請求）
  python -m twstock history --start 2026-07-31 --only amount  只補上市三大法人買賣金額
  python -m twstock revenue --year 2026 --month 9    收集指定月份營收
  python -m twstock events --start 2025-10-30        補抓除權息／減資／面額變更事件（還原價格用）
  python -m twstock export                           從資料庫匯出網站 JSON（site/data）
  python -m twstock serve                            本機預覽網站 http://localhost:8000
  python -m twstock futures --start 2025-01-01       台指期日 K 與期貨三大法人未平倉
  python -m twstock chains                           更新產業鏈族群（櫃買產業價值鏈平台）
  python -m twstock chanlun 2330                     纏論結構圖（output/chanlun_2330.svg）
"""
import argparse
import sys
from datetime import date, datetime

from .config import tw_now


def _utf8_console():
    # Windows 主控台或排程把輸出導向檔案時預設 cp950，印出 emoji 會 UnicodeEncodeError
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def _date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def cmd_setup_db(args):
    from .db import setup_database
    setup_database()


def cmd_collect(args):
    from .collectors.catchup import DEFAULT_DAYS, MAX_DAYS, run
    if args.days is not None and not args.catch_up:
        print("❌ --days 只能和 --catch-up 一起用")
        return 1
    days = DEFAULT_DAYS if args.days is None else args.days
    if not 1 <= days <= MAX_DAYS:
        print(f"❌ --days 上限 {MAX_DAYS}（更早的缺口請用 python -m twstock history）")
        return 1
    # 不帶參數 = 今天（台灣時間）
    date_ = None if args.catch_up else args.date or tw_now().date()
    return run(days=days, date_=date_, no_revenue=args.no_revenue, no_export=args.no_export, notify=args.notify)


def cmd_check(args):
    from .health import run_check
    import pyodbc
    try:
        return run_check(args.days, tw_now())
    except pyodbc.Error as e:
        print(f"❌ 連不上資料庫或資料表不存在（請確認 Docker 與容器已啟動，並執行過 setup-db）：{str(e).splitlines()[0][:200]}")
        return 2


def cmd_history(args):
    from .collectors.daily import ALL_DATASETS
    from .collectors.history import run_history
    from .db import acquire_lock, release_lock
    datasets = tuple(args.only) if args.only else ALL_DATASETS
    lock = acquire_lock()
    if lock is None:
        print("⏭️  另一個收集程序正在執行，請稍後再跑（同時跑會超過網站節流）")
        return 1
    try:
        ok = run_history(args.start, args.end or tw_now().date(), datasets=datasets,
                         force=args.force, revenue=not args.no_revenue, delay=args.delay)
    finally:
        release_lock(lock)
    return 0 if ok else 1


def cmd_revenue(args):
    from .collectors.revenue import collect_monthly_revenue
    collect_monthly_revenue(args.year, args.month, force=args.force)


def cmd_events(args):
    from .collectors.events import collect_events
    from .fetch import FetchError
    try:
        collect_events(args.start, args.end or date.today())
    except FetchError as e:
        print(f"\n❌ {e}\n   稍後用同樣的指令重跑即可（MERGE 覆寫，不會重複）")
        return 1
    return 0


def cmd_export(args):
    from .export import export_all
    export_all()


def cmd_serve(args):
    import errno
    import functools
    import http.server
    import webbrowser
    from .config import SITE_DIR
    class Server(http.server.ThreadingHTTPServer):
        def handle_error(self, request, client_address):
            # 瀏覽器預先開的連線沒用到就關閉，屬正常情況，不印 Traceback
            if isinstance(sys.exc_info()[1], (ConnectionResetError, BrokenPipeError)):
                return
            super().handle_error(request, client_address)

    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(SITE_DIR))
    url = f"http://localhost:{args.port}/"
    try:
        httpd = Server(("127.0.0.1", args.port), handler)
    except OSError as e:
        if e.errno not in (errno.EADDRINUSE, 10048):  # 10048：Windows 的 WSAEADDRINUSE
            raise
        print(f"⚠️  埠 {args.port} 已被使用，可能網站已經在執行：{url}")
        print(f"   要另開一個請指定其他埠，例如：python -m twstock serve --port {args.port + 1}")
        return 1
    with httpd:
        print(f"🌐 本機預覽：{url}（Ctrl+C 停止）")
        if not args.no_browser:
            webbrowser.open(url)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass


def cmd_futures(args):
    from .collectors.futures import collect_futures, collect_futures_institutional
    start = args.date or args.start or date.today()
    end = (args.end or date.today()) if args.start and not args.date else start
    collect_futures(start, end, args.commodity)
    collect_futures_institutional(start, end)


def cmd_chains(args):
    from .collectors.chains import update_chains
    update_chains()


def cmd_chanlun(args):
    from .analysis.chanlun import draw
    draw(args.code, args.days)


def main(argv=None):
    _utf8_console()
    p = argparse.ArgumentParser(prog="python -m twstock", description="台股資料收集與網站產生工具",
                                formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True, metavar="指令")

    sub.add_parser("setup-db", help="建立資料庫與資料表").set_defaults(fn=cmd_setup_db)

    s = sub.add_parser("collect", help="收集資料並匯出網站 JSON（單日，或 --catch-up 補齊最近的缺口）")
    g = s.add_mutually_exclusive_group()
    g.add_argument("--date", type=_date, help="YYYY-MM-DD，預設今天；該日全部重抓覆寫")
    g.add_argument("--catch-up", action="store_true", help="找出最近 N 個交易日各資料集的缺口，只補缺的；有新資料才匯出")
    s.add_argument("--days", type=int, help="--catch-up 回溯的交易日數，預設 10，上限 30")
    s.add_argument("--notify", action="store_true", help="有異常時發 Mac 本機通知（排程用；同一天同一問題只通知一次）")
    s.add_argument("--no-revenue", action="store_true", help="略過月營收")
    s.add_argument("--no-export", action="store_true", help="收集後不匯出網站資料")
    s.set_defaults(fn=cmd_collect)

    s = sub.add_parser("history", help="補抓歷史資料")
    s.add_argument("--start", type=_date, required=True)
    s.add_argument("--end", type=_date, help="預設今天")
    s.add_argument("--only", nargs="+", choices=["prices", "pe", "insti", "index", "amount", "tpex_index"],
                   help="只抓指定資料集（pe = 本益比／淨值比／殖利率，index = 加權指數，tpex_index = 櫃買指數，"
                        "amount = 上市三大法人買賣金額）")
    s.add_argument("--force", action="store_true", help="已存在的日期也重抓覆寫")
    s.add_argument("--no-revenue", action="store_true")
    s.add_argument("--delay", type=float, default=0.0, help="每日之間額外暫停秒數")
    s.set_defaults(fn=cmd_history)

    s = sub.add_parser("revenue", help="收集指定月份營收")
    s.add_argument("--year", type=int, required=True)
    s.add_argument("--month", type=int, required=True)
    s.add_argument("--force", action="store_true", help="已有的資料也覆寫")
    s.set_defaults(fn=cmd_revenue)

    s = sub.add_parser("events", help="補抓除權息／減資／面額變更事件（還原價格用）")
    s.add_argument("--start", type=_date, required=True)
    s.add_argument("--end", type=_date, help="預設今天")
    s.set_defaults(fn=cmd_events)

    s = sub.add_parser("check", help="檢查近 N 個交易日各資料集的完整性（唯讀、不連外）；有異常回傳 1")
    s.add_argument("--days", type=int, default=20, help="預設 20")
    s.set_defaults(fn=cmd_check)

    sub.add_parser("export", help="匯出網站 JSON 到 site/data").set_defaults(fn=cmd_export)

    s = sub.add_parser("serve", help="本機預覽網站")
    s.add_argument("--port", type=int, default=8000)
    s.add_argument("--no-browser", action="store_true", help="不自動開瀏覽器")
    s.set_defaults(fn=cmd_serve)

    s = sub.add_parser("futures", help="期貨日 K（預設台指期 TX）與三大法人未平倉")
    s.add_argument("--date", type=_date, help="單日，預設今天")
    s.add_argument("--start", type=_date, help="補抓起日")
    s.add_argument("--end", type=_date, help="補抓迄日，預設今天")
    s.add_argument("--commodity", default="TX", help="契約代號，如 TX、MTX、TMF")
    s.set_defaults(fn=cmd_futures)

    sub.add_parser("chains", help="更新產業鏈族群").set_defaults(fn=cmd_chains)

    s = sub.add_parser("chanlun", help="纏論結構圖 SVG")
    s.add_argument("code")
    s.add_argument("--days", type=int, default=130)
    s.set_defaults(fn=cmd_chanlun)

    args = p.parse_args(argv)
    return args.fn(args) or 0


if __name__ == "__main__":
    sys.exit(main())
