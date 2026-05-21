"""航班搜索 — fli (Google Flights) 主引擎 + LetsFG 备用"""

import time
import logging
from dataclasses import dataclass, field
from datetime import datetime
from zoneinfo import ZoneInfo

import config

log = logging.getLogger("surveillance")

# ============================================================
@dataclass
class FlightResult:
    origin: str
    destination: str
    travel_date: str
    price_cny: float
    price_original: float
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
        has_flight = bool(self.flight_numbers and any(f for f in self.flight_numbers))
        midnight = "T00:00:00" in self.departure_time or "T00:00:00" in self.arrival_time
        return (not has_flight and (midnight or self.duration_minutes <= 0))

    def is_plausible(self) -> bool:
        if self.price_cny <= 0 or self.is_teaser():
            return False
        if self.stops > config.MAX_STOPS:
            return False
        return True


@dataclass
class SearchError:
    origin: str
    destination: str
    date: str
    engine: str
    message: str


@dataclass
class SearchReport:
    timestamp: str
    results_by_date: dict[str, list[FlightResult]] = field(default_factory=dict)
    best_by_date: dict[str, FlightResult | None] = field(default_factory=dict)
    errors: list[SearchError] = field(default_factory=list)
    engine_used: str = ""


# ============================================================
class FlightSearcher:

    def __init__(self):
        self.fli_ok = False
        self.letsfg_ok = False

        # fli (Google Flights) — 中国可用
        try:
            from fli.models import (Airport, FlightSearchFilters, FlightSegment,
                                     MaxStops, SeatType, SortBy, PassengerInfo, Airline)
            from fli.search import SearchFlights
            self.Airport = Airport
            self.FlightSearchFilters = FlightSearchFilters
            self.FlightSegment = FlightSegment
            self.MaxStops = MaxStops
            self.SeatType = SeatType
            self.SortBy = SortBy
            self.PassengerInfo = PassengerInfo
            self.Airline = Airline
            self.SearchFlights = SearchFlights
            self.fli_ok = True
            log.info("fli (Google Flights) 引擎就绪")
        except Exception as e:
            log.warning(f"fli 不可用: {e}")

        # LetsFG 备用
        try:
            from letsfg import LetsFG
            self.letsfg = LetsFG()
            self.letsfg_ok = True
            log.info("LetsFG 备用引擎就绪")
        except Exception as e:
            log.warning(f"LetsFG 不可用: {e}")

        if not self.fli_ok and not self.letsfg_ok:
            raise RuntimeError("无可用搜索引擎！pip install flights letsfg")

    # ============================================================
    def search_all(self) -> SearchReport:
        tz = ZoneInfo(config.TIMEZONE)
        report = SearchReport(
            timestamp=datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S %Z"),
            engine_used="fli" if self.fli_ok else "letsfg",
        )

        for date in config.DATES:
            all_results = []

            # 主引擎: fli (Google Flights)
            if self.fli_ok:
                try:
                    results = self._search_fli("PEK", "CDG", date)
                    all_results.extend(results)
                    log.info(f"{date} PEK→CDG (fli): {len(results)}条")
                except Exception as e:
                    log.warning(f"fli 搜索失败 {date}: {e}")

            # 备用: LetsFG
            if len(all_results) < 5 and self.letsfg_ok:
                try:
                    extra = self._search_letsfg("PEK", "CDG", date)
                    valid = [r for r in extra if r.is_plausible()]
                    all_results.extend(valid)
                    log.info(f"{date} PEK→CDG (letsfg): +{len(valid)}条")
                except Exception as e:
                    log.warning(f"LetsFG 搜索失败 {date}: {e}")

            # 过滤 + 排序
            valid = [r for r in all_results if r.is_plausible()]
            fake_count = len(all_results) - len(valid)
            if fake_count:
                log.info(f"  → 剔除{fake_count}条虚假, 保留{len(valid)}条有效")

            in_budget = [r for r in valid if r.price_cny <= config.BUDGET_CNY]
            in_budget.sort(key=lambda r: r.price_cny)
            report.results_by_date[date] = in_budget
            report.best_by_date[date] = in_budget[0] if in_budget else (
                min(valid, key=lambda r: r.price_cny) if valid else None
            )

        return report

    # ============================================================
    # fli (Google Flights) 搜索
    # ============================================================

    def _search_fli(self, origin: str, dest: str, date: str) -> list[FlightResult]:
        origin_ap = getattr(self.Airport, origin)
        dest_ap = getattr(self.Airport, dest)

        filters = self.FlightSearchFilters(
            flight_segments=[self.FlightSegment(
                departure_airport=[[origin_ap, 0]],
                arrival_airport=[[dest_ap, 0]],
                travel_date=date,
            )],
            seat_type=self.SeatType.ECONOMY,
            stops=self.MaxStops.ONE_STOP_OR_FEWER,
            sort_by=self.SortBy.CHEAPEST,
            passenger_info=self.PassengerInfo(adults=config.ADULTS),
        )

        raw = self.SearchFlights().search(filters)
        results = []
        for r in raw:
            try:
                fr = self._norm_fli(r, origin, dest, date)
                results.append(fr)
            except Exception:
                pass
        return results

    def _norm_fli(self, r, origin: str, dest: str, date: str) -> FlightResult:
        legs = r.legs or []
        airline_codes = []
        airline_names = []
        flight_numbers = []
        stop_airports = []

        for i, leg in enumerate(legs):
            # Airline: .name = IATA code (TK), .value = full name (Turkish Airlines)
            code = leg.airline.name
            name = leg.airline.value
            airline_codes.append(code)
            airline_names.append(name)
            flight_numbers.append(leg.flight_number)

            # 中转机场: .name = IATA code (IST)
            if i < len(legs) - 1:
                stop_airports.append(leg.arrival_airport.name)

        # 时间
        dep_time = ""
        arr_time = ""
        if legs:
            dep_time = legs[0].departure_datetime.strftime("%Y-%m-%d %H:%M")
            arr_time = legs[-1].arrival_datetime.strftime("%Y-%m-%d %H:%M")

        # 价格转换
        raw_price = r.price
        currency = r.currency or "CNY"
        price_cny = self._to_cny(raw_price, currency)

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
            duration_minutes=r.duration,
            stops=r.stops,
            stop_airports=stop_airports,
            cabin_class="Economy",
            source="fli",
            booking_url=f"https://www.google.com/travel/flights?q=Flights+to+{dest}+from+{origin}+on+{date}",
        )

    # ============================================================
    # LetsFG 备用
    # ============================================================

    def _search_letsfg(self, origin: str, dest: str, date: str) -> list[FlightResult]:
        result = self.letsfg.search(origin, dest, date, max_stopovers=config.MAX_STOPS, limit=30)
        flights = []
        for offer in result.offers:
            try:
                fr = self._norm_letsfg(offer, origin, dest, date)
                flights.append(fr)
            except Exception:
                pass
        return flights

    def _norm_letsfg(self, offer, origin: str, dest: str, date: str) -> FlightResult:
        ob = offer.outbound
        segments = getattr(ob, "segments", []) or []

        airline_codes, airline_names, flight_numbers, stop_airports = [], [], [], []
        for seg in segments:
            code = getattr(seg, "airline", "")
            name = getattr(seg, "airline_name", "") or config.AIRLINE_NAMES.get(code, code)
            airline_codes.append(code)
            airline_names.append(name)
            flight_numbers.append(getattr(seg, "flight_no", ""))
            seg_dest = getattr(seg, "destination", "")
            if seg_dest and seg_dest != dest:
                stop_airports.append(seg_dest)
        if stop_airports and stop_airports[-1] == dest:
            stop_airports = stop_airports[:-1]

        dep_time = str(getattr(segments[0], "departure", "")) if segments else ""
        arr_time = str(getattr(segments[-1], "arrival", "")) if segments else ""

        raw_price = float(offer.price) if offer.price else 0
        currency = str(offer.currency) if offer.currency else "CNY"
        price_cny = self._to_cny(raw_price, currency)
        duration_s = getattr(ob, "total_duration_seconds", 0) or 0

        return FlightResult(
            origin=origin, destination=dest, travel_date=date,
            price_cny=round(price_cny, 0), price_original=raw_price, currency=currency,
            airline_codes=airline_codes, airline_names=airline_names,
            flight_numbers=flight_numbers,
            departure_time=dep_time, arrival_time=arr_time,
            duration_minutes=duration_s // 60,
            stops=getattr(ob, "stopovers", len(stop_airports)),
            stop_airports=stop_airports,
            cabin_class=getattr(segments[0], "cabin_class", "Economy") if segments else "Economy",
            source="letsfg",
            booking_url=str(getattr(offer, "booking_url", "") or ""),
        )

    # ============================================================
    @staticmethod
    def _to_cny(price: float, currency: str) -> float:
        rate = config.CURRENCY_RATES.get(currency.upper())
        if rate is None:
            log.warning(f"未知货币 {currency}，按 CNY 处理")
            rate = 1.0
        return price * rate
