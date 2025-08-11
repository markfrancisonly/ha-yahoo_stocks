from __future__ import annotations

DOMAIN = "yahoo_stocks"

CONF_TICKERS = "tickers"
CONF_INCLUDE_PREPOST = "include_prepost"
CONF_FAST_INTERVAL = "fast_interval"  # seconds during market hours
CONF_SLOW_INTERVAL = "slow_interval"  # seconds off-hours
CONF_USER_AGENT = "user_agent"

DEFAULT_INCLUDE_PREPOST = True
DEFAULT_FAST_INTERVAL = 60
DEFAULT_SLOW_INTERVAL = 900  # 15 minutes
DEFAULT_USER_AGENT = "Mozilla/5.0"

ATTR_PREV_CLOSE = "previousClose"
ATTR_PRICE = "regularMarketPrice"
ATTR_TIME = "regularMarketTime"
ATTR_SYMBOL = "symbol"
ATTR_CHANGE = "change"
ATTR_CHANGE_PCT = "change_percent"

ICON_UP = "mdi:trending-up"
ICON_DOWN = "mdi:trending-down"
ICON_FLAT = "mdi:minus"

SIGNAL_SYMBOLS_UPDATED = "yahoo_stocks_symbols_updated"
