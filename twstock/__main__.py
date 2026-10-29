"""
台股資料收集與網站產生工具（Mac / Windows 通用）

  python -m twstock setup-db                         建立資料庫與資料表
  python -m twstock collect [--date 2026-10-28]      收集單日（行情、本益比、法人、月營收）並匯出網站資料
  python -m twstock history --start 2026-01-01       補抓歷史（已有的日期自動跳過）
  python -m twstock revenue --year 2026 --month 9    收集指定月份營收
  python -m twstock export                           從資料庫匯出網站 JSON（site/data）
  python -m twstock serve                            本機預覽網站 http://localhost:8000
  python -m twstock futures --date 2026-10-28        台指期分鐘 K 線
  python -m twstock chanlun 2330                     纏論結構圖（output/chanlun_2330.svg）
"""
import argparse
import sys
from datetime import date, datetime


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
    from .collectors.daily import collect_for_date
    from .collectors.industry import update_industry
    from .collectors.revenue import collect_monthly_revenue, revenue_month_for
    from .fetch import FetchError

    d = args.date or date.today()
    try:
        traded = collect_for_date(d)
        if traded:
            update_industry()
            month = revenue_month_for(d)
            if month and not args.no_revenue:
                print(f"  💰 月營收 {month[0]}/{month[1]:02d}")
                try:
                    collect_monthly_revenue(*month)
                except FetchError as e:
                    print(f"  ⚠️  月營收抓取失敗，下次執行會再補：{e}")
    except FetchError as e:
        print(f"\n❌ {e}")
        return 1
    if not args.no_export:
        from .export import export_all
        export_all()
    return 0


def cmd_history(args):
    from .collectors.daily import ALL_DATASETS
    from .collectors.history import run_history
    datasets = tuple(args.only) if args.only else ALL_DATASETS
    ok = run_history(args.start, args.end or date.today(), datasets=datasets,
                     force=args.force, revenue=not args.no_revenue, delay=args.delay)
    return 0 if ok else 1


def cmd_revenue(args):
    from .collectors.revenue import collect_monthly_revenue
    collect_monthly_revenue(args.year, args.month, force=args.force)


def cmd_export(args):
    from .export import export_all
    export_all()


def cmd_serve(args):
    import functools
    import http.server
    import webbrowser
    from .config import SITE_DIR
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(SITE_DIR))
    with http.server.ThreadingHTTPServer(("127.0.0.1", args.port), handler) as httpd:
        url = f"http://localhost:{args.port}/"
        print(f"🌐 本機預覽：{url}（Ctrl+C 停止）")
        if not args.no_browser:
            webbrowser.open(url)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass


def cmd_futures(args):
    from .collectors.futures import collect_futures
    start = args.date or args.start or date.today()
    collect_futures(start, args.end if args.start else start, args.symbol)


def cmd_chanlun(args):
    from .analysis.chanlun import draw
    draw(args.code, args.days)


def main(argv=None):
    _utf8_console()
    p = argparse.ArgumentParser(prog="python -m twstock", description="台股資料收集與網站產生工具",
                                formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True, metavar="指令")

    sub.add_parser("setup-db", help="建立資料庫與資料表").set_defaults(fn=cmd_setup_db)

    s = sub.add_parser("collect", help="收集單日資料並匯出網站 JSON")
    s.add_argument("--date", type=_date, help="YYYY-MM-DD，預設今天")
    s.add_argument("--no-revenue", action="store_true", help="略過月營收")
    s.add_argument("--no-export", action="store_true", help="收集後不匯出網站資料")
    s.set_defaults(fn=cmd_collect)

    s = sub.add_parser("history", help="補抓歷史資料")
    s.add_argument("--start", type=_date, required=True)
    s.add_argument("--end", type=_date, help="預設今天")
    s.add_argument("--only", nargs="+", choices=["prices", "insti"], help="只抓指定資料集")
    s.add_argument("--force", action="store_true", help="已存在的日期也重抓覆寫")
    s.add_argument("--no-revenue", action="store_true")
    s.add_argument("--delay", type=float, default=0.0, help="每日之間額外暫停秒數")
    s.set_defaults(fn=cmd_history)

    s = sub.add_parser("revenue", help="收集指定月份營收")
    s.add_argument("--year", type=int, required=True)
    s.add_argument("--month", type=int, required=True)
    s.add_argument("--force", action="store_true", help="已有的資料也覆寫")
    s.set_defaults(fn=cmd_revenue)

    sub.add_parser("export", help="匯出網站 JSON 到 site/data").set_defaults(fn=cmd_export)

    s = sub.add_parser("serve", help="本機預覽網站")
    s.add_argument("--port", type=int, default=8000)
    s.add_argument("--no-browser", action="store_true", help="不自動開瀏覽器")
    s.set_defaults(fn=cmd_serve)

    s = sub.add_parser("futures", help="台指期分鐘 K 線")
    s.add_argument("--date", type=_date)
    s.add_argument("--start", type=_date)
    s.add_argument("--end", type=_date)
    s.add_argument("--symbol", default="TX00")
    s.set_defaults(fn=cmd_futures)

    s = sub.add_parser("chanlun", help="纏論結構圖 SVG")
    s.add_argument("code")
    s.add_argument("--days", type=int, default=130)
    s.set_defaults(fn=cmd_chanlun)

    args = p.parse_args(argv)
    return args.fn(args) or 0


if __name__ == "__main__":
    sys.exit(main())
