#!/usr/bin/env python3
"""航班价格监控系统 — 北京→巴黎 2026.8.12-14
用法:
  python surveillance.py            单次搜索 + 控制台报告
  python surveillance.py --email    单次搜索 + 控制台报告 + 发送邮件
  python surveillance.py --loop     持续监控模式
  python surveillance.py --quick    跳过历史对比
"""

import argparse
import logging
import signal
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import config
from searcher import FlightSearcher
from reporter import build_text, build_html, save_archive, load_previous
from mailer import send_report as send_email

# ---- 日志 ----
log_dir = Path(config.LOG_DIR)
log_dir.mkdir(parents=True, exist_ok=True)
log_file = log_dir / "surveillance.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("surveillance")

TZ = ZoneInfo(config.TIMEZONE)

# ---- 信号 ----
_shutdown = False

def _on_shutdown(sig, frame):
    global _shutdown
    _shutdown = True
    log.info("收到退出信号，正在停止...")

signal.signal(signal.SIGINT, _on_shutdown)
signal.signal(signal.SIGTERM, _on_shutdown)


# ============================================================
# 单次运行
# ============================================================

def run_once(quick: bool = False, do_email: bool = False):
    log.info("=" * 50)
    log.info("航班价格监控启动")

    try:
        searcher = FlightSearcher()
    except RuntimeError as e:
        log.error(str(e))
        return

    log.info("开始搜索所有航班...")
    report = searcher.search_all()

    # 历史对比
    prev = None if quick else load_previous()

    # 控制台文本表格
    text = build_text(report, prev)
    print("\n" + text + "\n")

    # 存档
    save_archive(report)

    # 邮件发送
    if do_email:
        html = build_html(report)
        now_str = datetime.now(TZ).strftime("%m/%d %H:%M")
        subject = f"🛫 北京→巴黎 机票监控 {now_str}"
        if send_email(html, subject):
            print("✅ 邮件已发送\n")
        else:
            print("⚠️ 邮件发送失败，请检查 QQ_EMAIL / QQ_SMTP_CODE 环境变量\n")

    # 摘要
    within = sum(1 for d in config.DATES
                 if report.best_by_date.get(d) and report.best_by_date[d].price_cny <= config.BUDGET_CNY)
    total = sum(len(v) for v in report.results_by_date.values())
    log.info(f"搜索完成 — {within}/{len(config.DATES)} 日期在预算内, {total} 个航班, {len(report.errors)} 个错误")

    for date in config.DATES:
        best = report.best_by_date.get(date)
        if best and best.price_cny <= config.BUDGET_CNY:
            log.info(f"  ✅ {date}: {best.price_cny:,.0f} CNY — {', '.join(best.airline_names)}")


# ============================================================
# 循环模式
# ============================================================

def run_loop(quick: bool = False, do_email: bool = False):
    log.info("进入持续监控模式 (Ctrl+C 退出)")
    log.info(f"汇报时段: {[f'{h:02d}:00' for h in config.REPORT_HOURS]} CST")

    last_run: set[int] = set()

    while not _shutdown:
        now = datetime.now(TZ)
        h = now.hour

        if h in config.REPORT_HOURS and h not in last_run:
            log.info(f"\n{'='*50}")
            log.info(f"🕐 定时触发 — {now.strftime('%H:%M')}")
            try:
                run_once(quick=quick, do_email=do_email)
            except Exception as e:
                log.error(f"搜索异常: {e}")
            last_run.add(h)

        if h not in config.REPORT_HOURS:
            last_run.discard(h)

        time.sleep(30)


# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="北京→巴黎 机票价格监控 (2026.8.12-14)")
    parser.add_argument("--loop", action="store_true", help="持续监控模式")
    parser.add_argument("--quick", action="store_true", help="跳过历史对比")
    parser.add_argument("--email", action="store_true", help="发送邮件报告")
    args = parser.parse_args()

    if args.loop:
        run_loop(quick=args.quick, do_email=args.email)
    else:
        run_once(quick=args.quick, do_email=args.email)


if __name__ == "__main__":
    main()
