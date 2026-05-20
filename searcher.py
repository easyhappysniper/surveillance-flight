"""航班搜索核心 — LetsFG 主引擎 + fli 备用引擎"""

import time
import logging
from dataclasses import dataclass, field
from datetime import datetime
from zoneinfo import ZoneInfo

import config

log = logging.getLogger("surveillance")

# ============================================================
# 数据结构
# ============================================================

@dataclass
class FlightResult:
    """标准化搜索结果"""
    origin: str
    destination: str
    travel_date: str
    price_cny: float
    price_original: float        # 原币种价格
    currency: str
    airline_codes: list[str]
    airline_names: list[str]
    flight_numbers: list[str]
    departure_time: str
    arrival_time: str
    duration_minutes: int
    stops: int
    stop_airports: list[str]
    cabin_class: str
    source: str
    booking_url: str

    def is_teaser(self) -> bool:
        """检测虚假/ teaser 票价：无航班号且时间为午夜或时长为0"""
        has_flight = bool(self.flight_numbers and any(f for f in self.flight_numbers))
        midnight = "T00:00:00" in self.departure_time or "T00:00:00" in self.arrival_time
        no_duration = self.duration_minutes <= 0
        return not has_flight and (midnight or no_duration)

    def is_plausible(self) -> bool:
        """数据质量检查：价格合理 + 非虚假"""
        if self.price_cny <= 0:
            return False
        if self.is_teaser():
            return False
        # PEK→CDG 正常直飞 10-12h，中转 14-24h
        if self.duration_minutes > 0 and self.duration_minutes < 300:
            return False  # 少于5小时不可能
        if self.duration_minutes > 2880:
            return False  # 超过48小时不合理
        return True

@dataclass
class SearchError:
    """搜索错误记录"""
    origin: str
    destination: str
    date: str
    engine: str
    message: str

@dataclass
class SearchReport:
    """一次完整搜索的结果汇总"""
    timestamp: str
    results_by_date: dict[str, list[FlightResult]] = field(default_factory=dict)
    best_by_date: dict[str, FlightResult | None] = field(default_factory=dict)
    errors: list[SearchError] = field(default_factory=list)
    engine_used: str = ""


# ============================================================
# 搜索引擎
# ============================================================

class FlightSearcher:
    """多引擎航班搜索器"""

    def __init__(self):
        self.fli_ok = False
        self.letsfg_ok = False

        # 检查 LetsFG
        try:
            from letsfg import LetsFG
            self.letsfg = LetsFG()
            self.letsfg_ok = True
            log.info("LetsFG 引擎就绪")
        except Exception as e:
            log.warning(f"LetsFG 不可用: {e}")

        # 检查 fli
        try:
            from fli.models import Airport, FlightSearchFilters, FlightSegment, MaxStops, SeatType, SortBy, PassengerInfo
            from fli.search import SearchFlights
            self.fli_models = (Airport, FlightSearchFilters, FlightSegment, MaxStops, SeatType, SortBy, PassengerInfo)
            self.fli_search = SearchFlights
            self.fli_ok = True
            log.info("fli (Google Flights) 引擎就绪")
        except Exception as e:
            log.warning(f"fli 不可用: {e}")

        self._engine = "letsfg" if self.letsfg_ok else ("fli" if self.fli_ok else None)
        if self._engine is None:
            raise RuntimeError("无可用搜索引擎！请安装: pip install letsfg flights")

    # --------------------------------------------------------
    # 主入口
    # --------------------------------------------------------

    def search_all(self) -> SearchReport:
        """按日期搜索 PEK→CDG，LetsFG 内 GF 连接器自动覆盖机场群"""
        tz = ZoneInfo(config.TIMEZONE)
        report = SearchReport(
            timestamp=datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S %Z"),
            engine_used=self._engine or "unknown",
        )

        for date in config.DATES:
            all_results = self._search_pair("PEK", "CDG", date)
            # 过滤虚假/teaser数据
            valid_results = [r for r in all_results if r.is_plausible()]
            fake_count = len(all_results) - len(valid_results)
            if fake_count:
                log.info(f"{date} PEK→CDG: {len(all_results)}条原始, 剔除{fake_count}条虚假, 保留{len(valid_results)}条")

            if len(valid_results) < 5:
                log.info(f"{date} 有效结果较少，补充搜索 PKX→ORY...")
                time.sleep(config.SEARCH_DELAY)
                extra = self._search_pair("PKX", "ORY", date)
                valid_results.extend(r for r in extra if r.is_plausible())

            # 预算过滤 + 排序
            in_budget = [r for r in valid_results if r.price_cny <= config.BUDGET_CNY]
            in_budget.sort(key=lambda r: r.price_cny)
            report.results_by_date[date] = in_budget
            report.best_by_date[date] = in_budget[0] if in_budget else (
                min(valid_results, key=lambda r: r.price_cny) if valid_results else None
            )

        return report

    def _search_pair(self, origin: str, dest: str, date: str) -> list[FlightResult]:
        """搜索单对机场，按引擎优先级回退"""
        for engine_name in config.ENGINES:
            engine_func = getattr(self, f"_search_{engine_name}", None)
            if engine_func is None:
                continue
            try:
                results = engine_func(origin, dest, date)
                if results:
                    self._engine = engine_name
                    return results
                log.info(f"{engine_name} 返回空结果: {origin}→{dest} {date}")
            except Exception as e:
                log.warning(f"{engine_name} 搜索失败 {origin}→{dest} {date}: {e}")
        return []

    # --------------------------------------------------------
    # LetsFG 搜索
    # --------------------------------------------------------

    def _search_letsfg(self, origin: str, dest: str, date: str) -> list[FlightResult]:
        """LetsFG 搜索 + 标准化转换"""
        result = self.letsfg.search(origin, dest, date, max_stopovers=config.MAX_STOPS, limit=30)
        flights = []
        for offer in result.offers:
            try:
                fr = self._normalize_letsfg(offer, origin, dest, date)
                flights.append(fr)
            except Exception as e:
                log.debug(f"LetsFG 标准化失败: {e}")
        return flights

    def _normalize_letsfg(self, offer, origin: str, dest: str, date: str) -> FlightResult:
        """LetsFG Offer → FlightResult"""
        ob = offer.outbound
        segments = getattr(ob, "segments", []) or []

        airline_codes = []
        airline_names = []
        flight_numbers = []
        stop_airports = []

        for seg in segments:
            code = getattr(seg, "airline", "")
            name = getattr(seg, "airline_name", "") or config.AIRLINE_NAMES.get(code, code)
            airline_codes.append(code)
            airline_names.append(name)
            flight_numbers.append(getattr(seg, "flight_no", ""))
            # 经停机场: 非起点也非终点的中间机场
            seg_dest = getattr(seg, "destination", "")
            if seg_dest and seg_dest != dest:
                stop_airports.append(seg_dest)

        # 去重经停机场（最后一个seg的destination就是最终目的地）
        if stop_airports and stop_airports[-1] == dest:
            stop_airports = stop_airports[:-1]

        # 起飞/到达时间
        dep_time = ""
        arr_time = ""
        if segments:
            dep_time = str(getattr(segments[0], "departure", ""))
            arr_time = str(getattr(segments[-1], "arrival", ""))

        # 价格
        raw_price = float(offer.price) if offer.price else 0
        currency = str(offer.currency) if offer.currency else "CNY"
        price_cny = self._to_cny(raw_price, currency)

        duration_s = getattr(ob, "total_duration_seconds", 0) or 0

        return FlightResult(
            origin=origin,
            destination=dest,
            travel_date=date,
            price_cny=round(price_cny, 0),
            price_original=raw_price,
            currency=currency,
            airline_codes=airline_codes,
            airline_names=airline_names,
            flight_numbers=flight_numbers,
            departure_time=dep_time,
            arrival_time=arr_time,
            duration_minutes=duration_s // 60,
            stops=getattr(ob, "stopovers", len(stop_airports)),
            stop_airports=stop_airports,
            cabin_class=getattr(segments[0], "cabin_class", "Economy") if segments else "Economy",
            source="letsfg",
            booking_url=str(getattr(offer, "booking_url", "") or ""),
        )

    # --------------------------------------------------------
    # fli (Google Flights) 搜索 — 需要 VPN
    # --------------------------------------------------------

    def _search_fli(self, origin: str, dest: str, date: str) -> list[FlightResult]:
        """fli 搜索 — Google Flights API (需 VPN)"""
        Airport, FlightSearchFilters, FlightSegment, MaxStops, SeatType, SortBy, PassengerInfo = self.fli_models

        # 日期格式转换: "2026-08-12" → fli 所需格式
        year, month, day = date.split("-")
        travel_date = f"{year}-{month}-{day}"

        try:
            origin_airport = getattr(Airport, origin)
            dest_airport = getattr(Airport, dest)
        except AttributeError as e:
            log.warning(f"fli 不支持的机场代码: {e}")
            return []

        filters = FlightSearchFilters(
            flight_segments=[
                FlightSegment(
                    departure_airport=[[origin_airport, 0]],
                    arrival_airport=[[dest_airport, 0]],
                    travel_date=travel_date,
                )
            ],
            seat_type=SeatType.ECONOMY,
            stops=MaxStops.ONE_STOP_OR_FEWER,
            sort_by=SortBy.CHEAPEST,
            passenger_info=PassengerInfo(adults=config.ADULTS),
        )

        raw_results = self.fli_search().search(filters)
        flights = []
        for r in raw_results:
            try:
                fr = self._normalize_fli(r, origin, dest, date)
                flights.append(fr)
            except Exception as e:
                log.debug(f"fli 标准化失败: {e}")
        return flights

    def _normalize_fli(self, r, origin: str, dest: str, date: str) -> FlightResult:
        """fli 结果 → FlightResult"""
        raw_price = float(getattr(r, "price", 0))
        currency = getattr(r, "currency", "CNY") or "CNY"
        price_cny = self._to_cny(raw_price, currency)

        legs = getattr(r, "legs", []) or []
        airline_codes = []
        flight_numbers = []
        stop_airports = []
        dep_time = ""
        arr_time = ""

        for leg in legs:
            airline_codes.append(getattr(leg, "airline", ""))
            flight_numbers.append(getattr(leg, "flight_number", ""))
            if getattr(leg, "departure_time", None):
                dep_time = str(leg.departure_time)
            if getattr(leg, "arrival_time", None):
                arr_time = str(leg.arrival_time)
            # 中转信息
            for seg in getattr(leg, "segments", []) or []:
                seg_dest = getattr(seg, "arrival_airport", "")
                if seg_dest and seg_dest != dest:
                    stop_airports.append(seg_dest)

        if stop_airports and stop_airports[-1] == dest:
            stop_airports = stop_airports[:-1]

        return FlightResult(
            origin=origin,
            destination=dest,
            travel_date=date,
            price_cny=round(price_cny, 0),
            price_original=raw_price,
            currency=currency,
            airline_codes=airline_codes,
            airline_names=[config.AIRLINE_NAMES.get(c, c) for c in airline_codes],
            flight_numbers=flight_numbers,
            departure_time=dep_time,
            arrival_time=arr_time,
            duration_minutes=getattr(r, "duration", 0) or 0,
            stops=getattr(r, "stops", len(stop_airports)),
            stop_airports=stop_airports,
            cabin_class=getattr(r, "cabin_class", "Economy") or "Economy",
            source="fli",
            booking_url=getattr(r, "booking_url", "") or "",
        )

    # --------------------------------------------------------
    # 工具方法
    # --------------------------------------------------------

    @staticmethod
    def _to_cny(price: float, currency: str) -> float:
        rate = config.CURRENCY_RATES.get(currency.upper())
        if rate is None:
            log.warning(f"未知货币 {currency}，按 CNY 处理")
            rate = 1.0
        return price * rate
