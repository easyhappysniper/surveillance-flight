"""报告生成 — 双币种表格 + 紧急提醒 + 中转签证 + JSON存档"""

import json
import logging
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

import config

log = logging.getLogger("surveillance")

BUDGET = config.BUDGET_CNY
URGENT = config.URGENT_THRESHOLD
TZ = ZoneInfo(config.TIMEZONE)

# ============================================================
# 工具
# ============================================================

def _t(ts: str) -> str:
    if not ts or "T00:00:00" in ts:
        return "-"
    return ts.replace("T", " ")[:16]


def _dur(m: int) -> str:
    if not m or m <= 0:
        return "-"
    return f"{m//60}h{m%60:02d}m"


def _route(r) -> str:
    parts = [r.origin] + r.stop_airports + [r.destination]
    return "→".join(parts)


def _visa_tag(airports: list[str]) -> str:
    """中转签证标注"""
    if not airports:
        return "直飞✅"
    tags = []
    for a in airports:
        p = config.get_transit_policy(a)
        icon = "⚠" if "⚠" in p or "需" in p or "过境签" in p else "✅"
        tags.append(f"{a}({icon}{p})")
    return " | ".join(tags)


def _alert(r) -> str:
    if r.price_cny <= 2000:
        return "🔴🔴 超低价!"
    if r.price_cny <= URGENT:
        return "🔴 紧急"
    if r.price_cny <= BUDGET:
        return "🟢 预算内"
    return "⚪ 超预算"


def _price_str(r) -> str:
    """原币种 + CNY 双显示"""
    orig = f"{r.price_original:,.0f} {r.currency}" if r.price_original > 0 else "-"
    cny = f"{r.price_cny:,.0f} CNY"
    return f"{orig} / {cny}"


# ============================================================
# HTML 邮件表格
# ============================================================

def build_html(report) -> str:
    now = datetime.now(TZ).strftime("%m/%d %H:%M")
    all_flights = _collect_all(report)

    rows = ""
    for r in all_flights:
        alert = _alert(r)
        alert_color = "#c62828" if "🔴" in alert else "#2e7d32" if "🟢" in alert else "#666"
        rows += f"""
    <tr>
      <td>{r.travel_date}</td>
      <td>{_route(r)}</td>
      <td style="font-weight:bold">{_price_str(r)}</td>
      <td>{', '.join(r.airline_names)}</td>
      <td>{' + '.join(r.flight_numbers) if r.flight_numbers else '-'}</td>
      <td>{_t(r.departure_time)}</td>
      <td>{_t(r.arrival_time)}</td>
      <td>{_dur(r.duration_minutes)}</td>
      <td>{r.stops}停</td>
      <td style="font-size:11px">{_visa_tag(r.stop_airports)}</td>
      <td style="color:{alert_color};font-weight:bold">{alert}</td>
      <td><a href="{r.booking_url}">{r.booking_url[:60]}{'...' if len(r.booking_url)>60 else ''}</a></td>
    </tr>"""

    within = sum(1 for d in config.DATES
                 if report.best_by_date.get(d) and report.best_by_date[d].price_cny <= BUDGET)
    urgent_count = sum(1 for r in all_flights if r.price_cny <= URGENT)

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
body{{font-family:-apple-system,'Microsoft YaHei',sans-serif;background:#f5f5f5;margin:0;padding:20px}}
.container{{max-width:1100px;margin:0 auto;background:#fff;border-radius:12px;padding:24px;box-shadow:0 2px 12px rgba(0,0,0,.1)}}
h2{{color:#1565c0;margin:0 0 4px 0}} .subtitle{{color:#666;font-size:13px;margin-bottom:16px}}
.urgent{{background:#fff3e0;border-left:4px solid #e65100;padding:10px 14px;margin:12px 0;border-radius:4px;font-weight:bold}}
table{{width:100%;border-collapse:collapse;font-size:12px}}
th{{background:#1565c0;color:#fff;padding:8px 4px;text-align:left;font-weight:600}}
td{{padding:6px 4px;border-bottom:1px solid #eee;vertical-align:top}}
tr:hover{{background:#f8f9fa}}
.summary{{margin-top:20px;padding:12px;background:#e3f2fd;border-radius:8px;font-size:14px}}
.footer{{color:#999;font-size:11px;margin-top:20px;text-align:center}}
</style></head><body>
<div class="container">
<h2>🛫 北京→巴黎 航班价格监控</h2>
<div class="subtitle">2026.8.12-14 | 中转≤{config.MAX_STOPS} | 预算≤{BUDGET:,} CNY | 紧急≤{URGENT:,} CNY | {now} CST | {report.engine_used}</div>
{f'<div class="urgent">🔴 紧急提醒: {urgent_count} 个航班低于 {URGENT:,} CNY！</div>' if urgent_count else ''}
<table>
<tr><th>日期</th><th>航线</th><th>原币/人民币</th><th>航司</th><th>航班号</th><th>出发</th><th>到达</th><th>时长</th><th>中转</th><th>过境签证</th><th>提醒</th><th>预订</th></tr>
{rows}
</table>
<div class="summary">✅ {within}/{len(config.DATES)} 日期在预算内 | 🛫 共 {len(all_flights)} 个航班 | 🔴 {urgent_count} 个紧急</div>
<div class="footer">自动监控 · GitHub Actions · 下次: {'/'.join(f'{h:02d}:00' for h in config.REPORT_HOURS)} CST</div>
</div></body></html>"""


# ============================================================
# 控制台文本表格
# ============================================================

def build_text(report, previous: dict | None = None) -> str:
    now = datetime.now(TZ).strftime("%m/%d %H:%M")
    all_flights = _collect_all(report)
    urgent_count = sum(1 for r in all_flights if r.price_cny <= URGENT)

    lines = []
    lines.append("=" * 130)
    lines.append(f"  🛫 北京→巴黎 航班监控 | {now} CST | {report.engine_used}")
    lines.append(f"  {config.DATES[0]} ~ {config.DATES[-1]} | 中转≤{config.MAX_STOPS} | 预算≤{BUDGET:,} | 🔴紧急≤{URGENT:,} CNY")
    if urgent_count:
        lines.append(f"  🔴🔴 紧急提醒: {urgent_count} 个航班低于 {URGENT:,} CNY！🔴🔴")
    lines.append("=" * 130)

    header = f"  {'日期':<12} {'航线':<24} {'原币价格':>14} {'人民币':>10} {'航司':<14} {'航班号':<14} {'出发':>16} {'到达':>16} {'时长':>8} {'中转':>5} {'提醒':<16} 预订链接"
    lines.append(header)
    lines.append("  " + "-" * 126)

    for r in all_flights:
        alert = _alert(r)
        lines.append(
            f"  {r.travel_date:<12} {_route(r):<24} "
            f"{r.price_original:>12,.0f} {r.currency:<4} {r.price_cny:>8,.0f} CNY "
            f"{', '.join(r.airline_names)[:13]:<14} "
            f"{'+'.join(r.flight_numbers)[:13]:<14} "
            f"{_t(r.departure_time):>16} {_t(r.arrival_time):>16} "
            f"{_dur(r.duration_minutes):>8} {r.stops:>4}停 "
            f"{alert:<16} "
            f"{r.booking_url[:60] if r.booking_url else '-'}"
        )
        # 中转签证单独一行
        if r.stop_airports:
            lines.append(f"  {'':>12} 🛂 过境签证: {_visa_tag(r.stop_airports)}")

    within = sum(1 for d in config.DATES
                 if report.best_by_date.get(d) and report.best_by_date[d].price_cny <= BUDGET)
    lines.append("  " + "-" * 126)
    lines.append(f"  ✅ {within}/{len(config.DATES)} 日期在预算内 | 🛫 共{len(all_flights)}个航班 | 🔴 {urgent_count}个紧急")
    lines.append(f"  📅 下次报告: {'/'.join(f'{h:02d}:00' for h in config.REPORT_HOURS)} CST")
    lines.append("=" * 130)
    return "\n".join(lines)


# ============================================================
# 汇总所有航班 (排序过滤)
# ============================================================

def _collect_all(report) -> list:
    """汇总所有有效航班，按CNY排序，最多取MAX_RESULTS个"""
    all_f = []
    for date in config.DATES:
        for r in report.results_by_date.get(date, []):
            all_f.append(r)
    # 按CNY价格升序
    all_f.sort(key=lambda x: x.price_cny)
    # 只取预算内航班
    in_budget = [r for r in all_f if r.price_cny <= BUDGET]
    return in_budget[:config.MAX_RESULTS]


# ============================================================
# 存档
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
        "all_flights": [_result_dict(r) for r in _collect_all(report)],
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
        "price_original": r.price_original, "currency": r.currency,
        "airline_codes": r.airline_codes, "airline_names": r.airline_names,
        "flight_numbers": r.flight_numbers,
        "departure_time": r.departure_time, "arrival_time": r.arrival_time,
        "duration_minutes": r.duration_minutes, "stops": r.stops,
        "stop_airports": r.stop_airports, "source": r.source,
    }
