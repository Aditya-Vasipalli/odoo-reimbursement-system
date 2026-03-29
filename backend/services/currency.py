from __future__ import annotations

from typing import Any
from threading import Lock
from time import time

import httpx


_COUNTRY_CACHE: list[dict[str, str]] | None = None
_COUNTRY_CACHE_LOCK = Lock()
_COUNTRY_CACHE_TS = 0.0
_COUNTRY_CACHE_TTL_SECONDS = 60 * 60 * 6


def get_countries() -> list[dict[str, str]]:
    global _COUNTRY_CACHE_TS
    global _COUNTRY_CACHE
    with _COUNTRY_CACHE_LOCK:
        if _COUNTRY_CACHE is not None and (time() - _COUNTRY_CACHE_TS) < _COUNTRY_CACHE_TTL_SECONDS:
            return list(_COUNTRY_CACHE)

    url = "https://restcountries.com/v3.1/all?fields=name,currencies"
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url)
            response.raise_for_status()
            raw: list[dict[str, Any]] = response.json()
    except Exception:
        return []

    countries: list[dict[str, str]] = []
    for item in raw:
        currencies = item.get("currencies") or {}
        if not currencies:
            continue
        currency_code = next(iter(currencies.keys()))
        currency = currencies[currency_code] or {}
        countries.append(
            {
                "name": item.get("name", {}).get("common", "Unknown"),
                "currency_code": currency_code,
                "symbol": currency.get("symbol", ""),
            }
        )

    countries.sort(key=lambda c: (c.get("name", ""), c.get("currency_code", "")))
    with _COUNTRY_CACHE_LOCK:
        _COUNTRY_CACHE = countries
        _COUNTRY_CACHE_TS = time()
    return list(countries)


def convert_amount(amount: float, from_currency: str, to_currency: str) -> tuple[float | None, float | None]:
    if from_currency == to_currency:
        return amount, 1.0

    url = f"https://api.exchangerate-api.com/v4/latest/{from_currency.upper()}"
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url)
            response.raise_for_status()
            data = response.json()
    except Exception:
        return None, None

    rate = (data.get("rates") or {}).get(to_currency.upper())
    if rate is None:
        return None, None

    return round(amount * float(rate), 2), float(rate)
