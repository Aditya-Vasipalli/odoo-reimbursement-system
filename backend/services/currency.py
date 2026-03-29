from __future__ import annotations

from typing import Any

import httpx


_COUNTRY_CACHE: list[dict[str, str]] | None = None


def get_countries() -> list[dict[str, str]]:
    global _COUNTRY_CACHE
    if _COUNTRY_CACHE is not None:
        return _COUNTRY_CACHE

    url = "https://restcountries.com/v3.1/all?fields=name,currencies"
    with httpx.Client(timeout=10.0) as client:
        response = client.get(url)
        response.raise_for_status()
        raw: list[dict[str, Any]] = response.json()

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

    _COUNTRY_CACHE = countries
    return countries


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
