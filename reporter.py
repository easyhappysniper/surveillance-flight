"""报告生成 — Top10按CNY排序 + 行李额度 + 中转签证 + 双币种"""

import json, logging
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import config

log = logging.getLogger("surveillance")
TZ = ZoneInfo(config.TIMEZONE)

def _t(ts: str) -> str:
    if not ts or "T00:00:00" in ts: return "-"
    return ts.replace("T", " ")[:16]

def _dur(m: int) -> str:
    if not m or m <= 0: return "-"
    return f"{m//60}h{m%60:02d}m"

def _route(r) -> str:
    parts = [r.origin] + r.stop_airports + [r.destination]
    return "→".join(parts)

def _visa_tag(airports: list[str]) -> str:
    if not airports: return "直飞✅"
    tags = []
    for a in airports:
        p = config.get_transit_policy(a)
        icon = "⚠" if "⚠" in p or "需" in p or "过境签" in p else "✅"
        tags.append(f"{a}({icon}{p})")
    return " | ".join(tags)

def _baggage(airline_codes: list[str]) -> str:
    bags = []
    for code in airline_codes:
        b = config.get_baggage(code)
        bags.append(f"{code}:{b}")
    return " + ".join(bags) if bags else "待查"

def _price_str(r) -> str:
    orig = f"{r.price_original:,.0f} {r.currency}" if r.price_original > 0 else "-"
    cny = f"{r.price_cny:,.0f} CNY"
    return f"{orig} / {cny}"


# ============================================================
def build_html(report) -> str:
    now = datetime.now(TZ).strftime("%m/%d %H:%M")
    flights = _collect(report)

    rows = ""
    for i, r in enumerate(flights):
        rows += f"""
    <tr>
      <td>{i+1}</td><td>{r.travel_date}</td><td>{_route(r)}</td>
      <td style="font-weight:bold">{_price_str(r)}</td>
      <td>{', '.join(r.airline_names)}</td>
      <td>{' + '.join(r.flight_numbers) if r.flight_numbers else '-'}</td>
      <td>{_t(r.departure_time)}</td><td>{_t(r.arrival_time)}</td>
      <td>{_dur(r.duration_minutes)}</td><td>{r.stops}停</td>
      <td style="font-size:11px">{_baggage(r.airline_codes)}</td>
      <td style="font-size:11px">{_visa_tag(r.stop_airports)}</td>
      <td><a href="{r.booking_url}">{r.booking_url[:55]}{'...' if len(r.booking_url)>55 else ''}</a></td>
    </tr>"""

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
body{{font-family:-apple-system,'Microsoft YaHei',sans-serif;background:#f5f5f5;margin:0;padding:20px}}
.container{{max-width:1200px;margin:0 auto;background:#fff;border-radius:12px;padding:24px;box-shadow:0 2px 12px rgba(0,0,0,.1)}}
h2{{color:#1565c0;margin:0 0 4px 0}}.subtitle{{color:#666;font-size:13px;margin-bottom:16px}}
table{{width:100%;border-collapse:collapse;font-size:12px}}
th{{background:#1565c0;color:#fff;padding:8px 4px;text-align:left;font-weight:600}}
td{{padding:6px 4px;border-bottom:1px solid #eee;vertical-align:top}}
tr:hover{{background:#f8f9fa}}.footer{{color:#999;font-size:11px;margin-top:20px;text-align:center}}
tr.warn{{background:#fff3e0}}
</style></head><body>
<div class="container">
<h2>🛫 北京→巴黎 机票监控 Top{len(flights)}</h2>
<div class="subtitle">2026.8.12-14 | 中转≤{config.MAX_STOPS} | {now} CST | 数据:Google Flights</div>
<table>
<tr><th>#</th><th>日期</th><th>航线</th><th>原币/人民币</th><th>航司</th><th>航班号</th><th>出发</th><th>到达</th><th>时长</th><th>中转</th><th>行李</th><th>过境签证</th><th>预订</th></tr>
{rows}
</table>
<div class="footer">自动监控 · GitHub Actions · 下次: {'/'.join(f'{h:02d}:00' for h in config.REPORT_HOURS)} CST</div>
</div></body></html>"""


# ============================================================
def build_text(report, previous=None) -> str:
    now = datetime.now(TZ).strftime("%m/%d %H:%M")
    flights = _collect(report)

    lines = []
    lines.append("=" * 145)
    lines.append(f"  🛫 北京→巴黎 机票监控 Top{len(flights)} | {now} CST | Google Flights")
    lines.append(f"  {config.DATES[0]} ~ {config.DATES[-1]} | 中转≤{config.MAX_STOPS} | 按人民币价格由低到高")
    lines.append("=" * 145)

    header = f"  {'#':<3} {'日期':<12} {'航线':<22} {'原币价格':>14} {'人民币':>10} {'航司':<16} {'航班号':<16} {'出发':>16} {'到达':>16} {'时长':>8} {'中转':>5} {'行李':<16} 过境签证"
    lines.append(header)
    lines.append("  " + "-" * 143)

    for i, r in enumerate(flights):
        lines.append(
            f"  {i+1:<3} {r.travel_date:<12} {_route(r):<22} "
            f"{r.price_original:>12,.0f} {r.currency:<4} {r.price_cny:>8,.0f} CNY "
            f"{', '.join(r.airline_names)[:15]:<16} "
            f"{'+'.join(r.flight_numbers)[:15]:<16} "
            f"{_t(r.departure_time):>16} {_t(r.arrival_time):>16} "
            f"{_dur(r.duration_minutes):>8} {r.stops:>4}停 "
            f"{_baggage(r.airline_codes):<16} "
            f"{_visa_tag(r.stop_airports)}"
        )

    lines.append("  " + "-" * 143)
    lines.append(f"  🛫 共{len(flights)}个航班 | 数据来源: Google Flights | 下次: {'/'.join(f'{h:02d}:00' for h in config.REPORT_HOURS)} CST")
    lines.append("=" * 145)
    return "\n".join(lines)


# ============================================================
def _collect(report) -> list:
    all_f = []
    for date in config.DATES:
        for r in report.results_by_date.get(date, []):
            all_f.append(r)
    all_f.sort(key=lambda x: x.price_cny)
    return all_f[:config.MAX_RESULTS]


# ============================================================
def save_archive(report) -> Path:
    Path(config.ARCHIVE_DIR).mkdir(parents=True, exist_ok=True)
    now = datetime.now(TZ)
    filepath = Path(config.ARCHIVE_DIR) / now.strftime("prices_%Y%m%d_%H%M.json")
    data = {
        "timestamp": now.isoformat(), "engine_used": report.engine_used,
        "flights": [_result_dict(r) for r in _collect(report)],
    }
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    log.info(f"存档: {filepath}")
    return filepath


def load_previous() -> dict | None:
    archive_dir = Path(config.ARCHIVE_DIR)
    if not archive_dir.exists(): return None
    files = sorted(archive_dir.glob("prices_*.json"), reverse=True)
    if not files: return None
    try:
        with open(files[0], "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _result_dict(r) -> dict | None:
    if r is None: return None
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
