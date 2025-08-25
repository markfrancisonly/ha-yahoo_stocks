from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_FAST_INTERVAL,
    CONF_INCLUDE_PREPOST,
    CONF_SLOW_INTERVAL,
    CONF_TICKERS,
    CONF_USER_AGENT,
    DEFAULT_FAST_INTERVAL,
    DEFAULT_INCLUDE_PREPOST,
    DEFAULT_SLOW_INTERVAL,
    DEFAULT_USER_AGENT,
    DOMAIN,
    SIGNAL_SYMBOLS_UPDATED,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]

YF_URL = (
    "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?"
    "region=US&lang=en-US&includePrePost={include_prepost}&interval=2m&useYfid=true&range=1d&"
    "corsDomain=finance.yahoo.com&.tsrc=finance"
)


def _parse_tickers(raw: str) -> list[str]:
    return [t.strip().upper() for t in raw.split(",") if t.strip()]


def _is_market_open(now: datetime) -> bool:
    # Market hours 09:30–16:00 America/New_York, Mon–Fri (no holiday calendar here)
    ny = now.astimezone(ZoneInfo("America/New_York"))
    if ny.weekday() >= 5:
        return False
    open_ = ny.replace(hour=9, minute=30, second=0, microsecond=0)
    close = ny.replace(hour=16, minute=0, second=0, microsecond=0)
    return open_ <= ny <= close


class StocksCoordinator(DataUpdateCoordinator[dict]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        session = async_get_clientsession(hass)
        self._session: aiohttp.ClientSession = session

        data = entry.data
        options = entry.options
        self.include_prepost: bool = options.get(
            CONF_INCLUDE_PREPOST,
            data.get(CONF_INCLUDE_PREPOST, DEFAULT_INCLUDE_PREPOST),
        )
        self.fast_interval: int = options.get(
            CONF_FAST_INTERVAL, data.get(CONF_FAST_INTERVAL, DEFAULT_FAST_INTERVAL)
        )
        self.slow_interval: int = options.get(
            CONF_SLOW_INTERVAL, data.get(CONF_SLOW_INTERVAL, DEFAULT_SLOW_INTERVAL)
        )
        self.symbols: list[str] = _parse_tickers(
            options.get(CONF_TICKERS, data.get(CONF_TICKERS, ""))
        )
        self.user_agent: str = options.get(
            CONF_USER_AGENT, data.get(CONF_USER_AGENT, DEFAULT_USER_AGENT)
        )

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} coordinator",
            update_interval=timedelta(seconds=self._current_interval_seconds()),
        )

    @property
    def headers(self) -> dict:
        return {
            "User-Agent": self.user_agent,
            "Accept": "application/json",
            "Referer": "https://finance.yahoo.com/",
        }

    def _current_interval_seconds(self) -> int:
        return (
            self.fast_interval
            if _is_market_open(datetime.now(ZoneInfo("America/New_York")))
            else self.slow_interval
        )

    async def _async_update_data(self) -> dict:
        # Adjust polling cadence dynamically
        self.update_interval = timedelta(seconds=self._current_interval_seconds())

        if not self.symbols:
            return {}

        now = datetime.now(ZoneInfo("America/New_York"))
        market_open_now = _is_market_open(now)
        market_open_recent = _is_market_open(now - timedelta(minutes=30))

        if not market_open_now and not market_open_recent and self.data:
            return self.data  # type: ignore[return-value]

        async def fetch_symbol(sym: str) -> tuple[str, dict | None]:
            url = YF_URL.format(
                symbol=sym, include_prepost=str(self.include_prepost).lower()
            )
            try:
                async with self._session.get(
                    url, headers=self.headers, timeout=aiohttp.ClientTimeout(total=15)
                ) as resp:
                    if resp.status != 200:
                        _LOGGER.warning("Yahoo response %s for %s", resp.status, sym)
                        return sym, None
                    js = await resp.json()
            except Exception as exc:
                _LOGGER.exception("Error fetching %s: %s", sym, exc)
                return sym, None

            try:
                chart = js.get("chart") or {}
                if chart.get("error"):
                    return sym, None
                results = chart.get("result") or []
                if not results:
                    return sym, None
                meta = results[0].get("meta") or {}
                # normalize payload
                data = {
                    "symbol": meta.get("symbol", sym),
                    "previousClose": meta.get("previousClose"),
                    "regularMarketPrice": meta.get("regularMarketPrice"),
                    "regularMarketTime": meta.get("regularMarketTime"),
                }
                # compute change
                try:
                    p = float(data["regularMarketPrice"] or 0.0)
                    prev = float(data["previousClose"] or 0.0)
                    change = p - prev if prev else 0.0
                    pct = (change / prev * 100.0) if prev else 0.0
                except Exception:
                    change = 0.0
                    pct = 0.0
                data["change"] = round(change, 4)
                data["change_percent"] = round(pct, 4)
                return sym, data
            except Exception as exc:
                _LOGGER.exception("Parse error for %s: %s", sym, exc)
                return sym, None

        results = await asyncio.gather(*(fetch_symbol(s) for s in self.symbols))
        return {sym: data for sym, data in results if data}

    async def async_set_symbols(self, raw_tickers: str) -> None:
        self.symbols = _parse_tickers(raw_tickers)
        await self.async_request_refresh()


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = StocksCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_options_updated))
    return True


async def _options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    coordinator: StocksCoordinator = hass.data[DOMAIN][entry.entry_id]
    # Re-read options
    coordinator.include_prepost = entry.options.get(
        CONF_INCLUDE_PREPOST, coordinator.include_prepost
    )
    coordinator.fast_interval = entry.options.get(
        CONF_FAST_INTERVAL, coordinator.fast_interval
    )
    coordinator.slow_interval = entry.options.get(
        CONF_SLOW_INTERVAL, coordinator.slow_interval
    )
    coordinator.user_agent = entry.options.get(CONF_USER_AGENT, coordinator.user_agent)
    await coordinator.async_set_symbols(
        entry.options.get(CONF_TICKERS, ",".join(coordinator.symbols))
    )
    # notify platform(s) to reconcile entities
    async_dispatcher_send(hass, f"{SIGNAL_SYMBOLS_UPDATED}_{entry.entry_id}")


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
