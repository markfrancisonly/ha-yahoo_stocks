from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict
from zoneinfo import ZoneInfo

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import StocksCoordinator
from .const import (
    ATTR_CHANGE,
    ATTR_CHANGE_PCT,
    ATTR_PREV_CLOSE,
    ATTR_PRICE,
    ATTR_SYMBOL,
    ATTR_TIME,
    DOMAIN,
    ICON_DOWN,
    ICON_FLAT,
    ICON_UP,
    SIGNAL_SYMBOLS_UPDATED,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: StocksCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: Dict[str, TickerPriceSensor] = {}

    def add_missing_symbols() -> None:
        new_symbols = set(coordinator.symbols) - set(entities.keys())
        if new_symbols:
            to_add = [
                TickerPriceSensor(coordinator, entry.entry_id, s)
                for s in sorted(new_symbols)
            ]
            for ent in to_add:
                entities[ent.symbol] = ent
            async_add_entities(to_add)

    @callback
    def remove_stale_symbols() -> None:
        stale = set(entities.keys()) - set(coordinator.symbols)
        for sym in stale:
            ent = entities.pop(sym)
            ent.async_remove()

    # Initial add
    add_missing_symbols()

    # Listen for options changes (symbols updated) and reconcile
    @callback
    def _handle_symbols_update() -> None:
        remove_stale_symbols()
        add_missing_symbols()

    entry_id = entry.entry_id
    unsub = async_dispatcher_connect(
        hass, f"{SIGNAL_SYMBOLS_UPDATED}_{entry_id}", _handle_symbols_update
    )
    entry.async_on_unload(unsub)


class TickerPriceSensor(CoordinatorEntity[StocksCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = "USD"
    _attr_should_poll = False
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self, coordinator: StocksCoordinator, entry_id: str, symbol: str
    ) -> None:
        super().__init__(coordinator)
        self.symbol = symbol.upper()
        self._attr_unique_id = f"{entry_id}_{self.symbol.lower()}_price"
        self._attr_name = f"{self.symbol}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="Yahoo Stocks",
            manufacturer="Yahoo Finance",
            model="Yahoo Finance Multi",
        )

    @property
    def available(self) -> bool:
        return self.coordinator.data.get(self.symbol) is not None

    @property
    def native_value(self) -> float | None:
        data = self.coordinator.data.get(self.symbol)
        if not data:
            return None
        price = data.get(ATTR_PRICE)
        try:
            return round(float(price), 4)
        except (TypeError, ValueError):
            return None

    @property
    def extra_state_attributes(self) -> dict:
        data = self.coordinator.data.get(self.symbol) or {}
        return {
            ATTR_SYMBOL: data.get(ATTR_SYMBOL, self.symbol),
            ATTR_PREV_CLOSE: data.get(ATTR_PREV_CLOSE),
            ATTR_PRICE: data.get(ATTR_PRICE),
            ATTR_CHANGE: data.get(ATTR_CHANGE),
            ATTR_CHANGE_PCT: data.get(ATTR_CHANGE_PCT),
            ATTR_TIME: data.get(ATTR_TIME),
            "market_time_readable": self._format_time(data.get(ATTR_TIME)),
        }

    @property
    def icon(self) -> str:
        data = self.coordinator.data.get(self.symbol) or {}
        chg = data.get(ATTR_CHANGE)
        try:
            chg = float(chg)
        except (TypeError, ValueError):
            chg = 0.0
        if chg > 0:
            return ICON_UP
        if chg < 0:
            return ICON_DOWN
        return ICON_FLAT

    def _format_time(self, t: int | None) -> str | None:
        if not t:
            return None
        try:
            dt = datetime.fromtimestamp(int(t), tz=timezone.utc).astimezone(
                ZoneInfo("America/New_York")
            )
            return dt.strftime("%Y-%m-%d %I:%M %p %Z")
        except Exception:
            return None
