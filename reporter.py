"""报告生成 — 控制台文本表格 + HTML 邮件表格 + JSON 存档"""

import json
import logging
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

import config

log = logging.getLogger("surveillance")

BUDGET = config.BUDGET_CNY
TZ = ZoneInfo(config.TIMEZONE)

# ============================================================
# 工具函数
# ============================================================

def _fmt_time(ts: str) -> str:
    if not ts:
        return "-"
    ts = ts.replace("T", " ").replace("Z", "")
    parts = ts.split(" ")
    if len(parts) >= 2:
        return parts[1][:5]
    return ts[:16]


def _fmt_dur(m: int) -> str:
    if not m:
        return "-"
    return f"{m//60}h{m%60:02d}m"


def _price_tag(price: float) -> str:
    if price <= BUDGET:
        return f"✅ {price:,.0f}"
    return f"❌ {price:,.0f}"


def _route_str(r) -> str:
    if r.stop_airports:
        return f"{r.origin}→{'→'.join(r.stop_airports)}→{r.destination}"
    return f"{r.origin}→{r.destination}"


# ============================================================
# HTML 表格
# ============================================================

def build_html(report) -> str:
    """生成 HTML 邮件内容"""
    now = datetime.now(TZ).strftime("%Y-%m-%d %H:%M")
    rows_html = ""

    for date in config.DATES:
        best = report.best_by_date.get(date)
        if best:
            rows_html += f"""
    <tr>
      <td>{date}</td>
      <td>{_route_str(best)}</td>
      <td style="color:{'#2e7d32' if best.price_cny <= BUDGET else '#c62828'};font-weight:bold">{best.price_cny:,.0f} CNY</td>
      <td>{', '.join(best.airline_names)}</td>
      <td>{' + '.join(best.flight_numbers) if best.flight_numbers else '-'}</td>
      <td>{_fmt_time(best.departure_time)}</td>
      <td>{_fmt_time(best.arrival_time)}</td>
      <td>{_fmt_dur(best.duration_minutes)}</td>
      <td>{best.stops}停</td>
      <td><a href="{best.booking_url}">{best.booking_url[:80]}{'...' if len(best.booking_url) > 80 else ''}</a></td>
    </tr>"""

    # 所有在预算内的航班
    all_rows = ""
    for date in config.DATES:
        for i, r in enumerate(report.results_by_date.get(date, [])[:8]):
            all_rows += f"""
    <tr>
      <td>{date}</td>
      <td>{_route_str(r)}</td>
      <td style="font-weight:bold">{r.price_cny:,.0f} {r.currency}</td>
      <td>{', '.join(r.airline_names)}</td>
      <td>{' + '.join(r.flight_numbers) if r.flight_numbers else '-'}</td>
      <td>{_fmt_time(r.departure_time)}</td>
      <td>{_fmt_time(r.arrival_time)}</td>
      <td>{_fmt_dur(r.duration_minutes)}</td>
      <td>{r.stops}停</td>
      <td><a href="{r.booking_url}">{r.booking_url[:80]}{'...' if len(r.booking_url) > 80 else ''}</a></td>
    </tr>"""

    within = sum(1 for d in config.DATES
                 if report.best_by_date.get(d) and report.best_by_date[d].price_cny <= BUDGET)
    total = sum(len(v) for v in report.results_by_date.values())

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
body {{ font-family: -apple-system, 'Microsoft YaHei', sans-serif; background:#f5f5f5; margin:0; padding:20px; }}
.container {{ max-width:800px; margin:0 auto; background:#fff; border-radius:12px; padding:24px; box-shadow:0 2px 12px rgba(0,0,0,0.1); }}
h2 {{ color:#1565c0; margin:0 0 4px 0; }}
.subtitle {{ color:#666; font-size:13px; margin-bottom:20px; }}
table {{ width:100%; border-collapse:collapse; font-size:13px; }}
th {{ background:#1565c0; color:#fff; padding:10px 8px; text-align:left; font-weight:600; }}
td {{ padding:8px; border-bottom:1px solid #eee; }}
tr:hover {{ background:#f8f9fa; }}
.summary {{ margin-top:20px; padding:12px; background:#e3f2fd; border-radius:8px; font-size:14px; }}
.footer {{ color:#999; font-size:11px; margin-top:20px; text-align:center; }}
</style></head><body>
<div class="container">
<h2>🛫 北京→巴黎 航班价格监控</h2>
<div class="subtitle">
  旅行日期: 2026-08-12 ~ 08-14 | 最多中转: {config.MAX_STOPS}次 | 预算: {BUDGET:,} CNY<br>
  生成时间: {now} CST | 引擎: {report.engine_used}
</div>

<h3>📋 各日期最优航班</h3>
<table>
<tr><th>日期</th><th>航线</th><th>价格</th><th>航司</th><th>航班号</th><th>出发</th><th>到达</th><th>时长</th><th>中转</th><th>预订</th></tr>
{rows_html}
</table>

<h3 style="margin-top:24px">💰 所有预算内航班 ({total}个)</h3>
<table>
<tr><th>日期</th><th>航线</th><th>价格</th><th>航司</th><th>航班号</th><th>出发</th><th>到达</th><th>时长</th><th>中转</th><th>链接</th></tr>
{all_rows}
</table>

<div class="summary">
  ✅ <b>{within}/{len(config.DATES)}</b> 日期在预算内 |
  📊 预算内航班共 <b>{total}</b> 个
</div>

<div class="footer">
  自动监控系统 · 下次报告: {' / '.join(f'{h:02d}:00' for h in config.REPORT_HOURS)} CST
</div>
</div></body></html>"""


# ============================================================
# 控制台文本表格
# ============================================================

def build_text(report, previous: dict | None = None) -> str:
    """生成控制台文本报告"""
    now = datetime.now(TZ).strftime("%Y-%m-%d %H:%M")
    lines = []

    lines.append("=" * 110)
    lines.append("  🛫 北京→巴黎 航班价格监控报告")
    lines.append(f"  日期: 2026.8.12-14 | 中转≤{config.MAX_STOPS} | 预算≤{BUDGET:,} CNY | {now} CST | {report.engine_used}")
    lines.append("=" * 110)

    # 表头
    header = f"  {'日期':<12} {'航线':<22} {'价格':>10} {'航司':<16} {'航班号':<16} {'出发':>6} {'到达':>6} {'时长':>7} {'中转':>4}  🔗预订"
    lines.append(header)
    lines.append("  " + "-" * 106)

    for date in config.DATES:
        best = report.best_by_date.get(date)
        if best:
            status = "✅" if best.price_cny <= BUDGET else "❌"
            lines.append(
                f"  {date:<12} {_route_str(best):<22} {status}{best.price_cny:>8,.0f} "
                f"{', '.join(best.airline_names):<16} {'+'.join(best.flight_numbers)[:15]:<16} "
                f"{_fmt_time(best.departure_time):>6} {_fmt_time(best.arrival_time):>6} "
                f"{_fmt_dur(best.duration_minutes):>7} {best.stops:>3}停 "
                            f"{best.booking_url if best.booking_url else '-'}"
            )
        else:
            lines.append(f"  {date:<12} {'无结果':<22} {'-':>10}")

    # 预算内详细列表
    lines.append("")
    lines.append("  💰 所有预算内航班 (按价格排序)")
    lines.append("  " + "-" * 106)
    lines.append(header)
    lines.append("  " + "-" * 106)

    all_in_budget = []
    for date in config.DATES:
        for r in report.results_by_date.get(date, []):
            all_in_budget.append(r)
    all_in_budget.sort(key=lambda x: x.price_cny)

    for r in all_in_budget[:20]:
        lines.append(
            f"  {r.travel_date:<12} {_route_str(r):<22} ✅{r.price_cny:>8,.0f} "
            f"{', '.join(r.airline_names)[:15]:<16} {'+'.join(r.flight_numbers)[:15]:<16} "
            f"{_fmt_time(r.departure_time):>6} {_fmt_time(r.arrival_time):>6} "
            f"{_fmt_dur(r.duration_minutes):>7} {r.stops:>3}停 "
                        f"{r.booking_url[:80] if r.booking_url else '-'}"
        )

    # 汇总
    within = sum(1 for d in config.DATES
                 if report.best_by_date.get(d) and report.best_by_date[d].price_cny <= BUDGET)
    total = sum(len(v) for v in report.results_by_date.values())
    lines.append("")
    lines.append(f"  📊 {within}/{len(config.DATES)} 日期在预算内 | 共 {total} 个预算内航班")
    lines.append(f"  📅 下次报告: {' / '.join(f'{h:02d}:00' for h in config.REPORT_HOURS)} CST")
    lines.append("=" * 110)

    # 趋势
    if previous:
        lines.append("")
        lines.append("  📈 价格变化")
        for date in config.DATES:
            cur = report.best_by_date.get(date)
            prev = previous.get("best_by_date", {}).get(date)
            if cur and prev:
                d = cur.price_cny - prev["price_cny"]
                if d == 0:
                    lines.append(f"  {date}: {prev['price_cny']:,.0f} → {cur.price_cny:,.0f} CNY  无变化")
                elif d < 0:
                    lines.append(f"  {date}: {prev['price_cny']:,.0f} → {cur.price_cny:,.0f} CNY  ↓{-d:,.0f}")
                else:
                    lines.append(f"  {date}: {prev['price_cny']:,.0f} → {cur.price_cny:,.0f} CNY  ↑{d:,.0f}")
        lines.append("=" * 110)

    return "\n".join(lines)


# ============================================================
# 存档管理 (不变)
# ============================================================

def save_archive(report) -> Path:
    archive_dir = Path(config.ARCHIVE_DIR)
    archive_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(TZ)
    filepath = archive_dir / now.strftime("prices_%Y%m%d_%H%M.json")
    data = {
        "timestamp": now.isoformat(),
        "engine_used": report.engine_used,
        "best_by_date": {
            date: _result_dict(report.best_by_date.get(date))
            for date in config.DATES
        },
        "results_count": {
            date: len(report.results_by_date.get(date, []))
            for date in config.DATES
        },
        "errors": [{"o": e.origin, "d": e.destination, "dt": e.date, "e": e.engine, "msg": e.message}
                   for e in report.errors],
    }
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    log.info(f"存档: {filepath}")
    return filepath


def load_previous() -> dict | None:
    archive_dir = Path(config.ARCHIVE_DIR)
    if not archive_dir.exists():
        return None
    files = sorted(archive_dir.glob("prices_*.json"), reverse=True)
    if not files:
        return None
    try:
        with open(files[0], "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log.warning(f"读取存档失败: {e}")
        return None


def _result_dict(r) -> dict | None:
    if r is None:
        return None
    return {
        "origin": r.origin, "destination": r.destination,
        "travel_date": r.travel_date, "price_cny": r.price_cny,
        "currency": r.currency, "airline_codes": r.airline_codes,
        "airline_names": r.airline_names, "flight_numbers": r.flight_numbers,
        "departure_time": r.departure_time, "arrival_time": r.arrival_time,
        "duration_minutes": r.duration_minutes, "stops": r.stops,
        "stop_airports": r.stop_airports, "source": r.source,
    }
