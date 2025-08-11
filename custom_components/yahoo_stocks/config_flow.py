from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback

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
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            raw = user_input.get(CONF_TICKERS, "").strip()
            if not raw:
                errors["base"] = "no_tickers"
            else:
                return self.async_create_entry(
                    title="Yahoo Stocks",
                    data={
                        CONF_TICKERS: raw,
                        CONF_INCLUDE_PREPOST: user_input.get(
                            CONF_INCLUDE_PREPOST, DEFAULT_INCLUDE_PREPOST
                        ),
                        CONF_FAST_INTERVAL: user_input.get(
                            CONF_FAST_INTERVAL, DEFAULT_FAST_INTERVAL
                        ),
                        CONF_SLOW_INTERVAL: user_input.get(
                            CONF_SLOW_INTERVAL, DEFAULT_SLOW_INTERVAL
                        ),
                        CONF_USER_AGENT: user_input.get(
                            CONF_USER_AGENT, DEFAULT_USER_AGENT
                        ),
                    },
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_TICKERS): str,
                vol.Optional(
                    CONF_INCLUDE_PREPOST, default=DEFAULT_INCLUDE_PREPOST
                ): bool,
                vol.Optional(CONF_FAST_INTERVAL, default=DEFAULT_FAST_INTERVAL): int,
                vol.Optional(CONF_SLOW_INTERVAL, default=DEFAULT_SLOW_INTERVAL): int,
                vol.Optional(CONF_USER_AGENT, default=DEFAULT_USER_AGENT): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return OptionsFlow(config_entry)


class OptionsFlow(config_entries.OptionsFlow):
    def __init__(self, entry):
        self.entry = entry

    async def async_step_init(self, user_input=None):
        errors = {}
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        data = {**self.entry.data, **self.entry.options}
        schema = vol.Schema(
            {
                vol.Required(CONF_TICKERS, default=data.get(CONF_TICKERS, "")): str,
                vol.Optional(
                    CONF_INCLUDE_PREPOST,
                    default=data.get(CONF_INCLUDE_PREPOST, DEFAULT_INCLUDE_PREPOST),
                ): bool,
                vol.Optional(
                    CONF_FAST_INTERVAL,
                    default=data.get(CONF_FAST_INTERVAL, DEFAULT_FAST_INTERVAL),
                ): int,
                vol.Optional(
                    CONF_SLOW_INTERVAL,
                    default=data.get(CONF_SLOW_INTERVAL, DEFAULT_SLOW_INTERVAL),
                ): int,
                vol.Optional(
                    CONF_USER_AGENT,
                    default=data.get(CONF_USER_AGENT, DEFAULT_USER_AGENT),
                ): str,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
