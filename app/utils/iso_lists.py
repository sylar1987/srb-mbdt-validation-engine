"""ISO-Referenz-Codelisten und Missing-Symbole (Legacy-kompatibel)."""

from __future__ import annotations

ISO_4217_CURRENCIES: frozenset[str] = frozenset({
    "EUR", "USD", "GBP", "CHF", "JPY", "SEK", "NOK", "DKK", "PLN", "CZK",
    "HUF", "RON", "BGN", "HRK", "ISK", "TRY", "AUD", "CAD", "CNY", "HKD",
    "SGD", "KRW", "INR", "BRL", "MXN", "ZAR", "RUB", "SAR", "AED", "THB",
    "IDR", "MYR", "NZD", "TWD", "ILS", "EGP", "NGN", "PKR", "BDT", "VND",
    "CLP", "COP", "ARS", "PEN", "UAH", "KZT", "QAR", "KWD", "BHD", "OMR",
    "MAD", "TND", "DZD", "XOF", "XAF", "GHS", "KES", "TZS", "UGX", "ETB",
    "XDR", "XAU", "XAG",
})

ISO_3166_COUNTRIES: frozenset[str] = frozenset({
    "AT", "BE", "BG", "CY", "CZ", "DE", "DK", "EE", "ES", "FI", "FR",
    "GR", "HR", "HU", "IE", "IT", "LT", "LU", "LV", "MT", "NL", "PL",
    "PT", "RO", "SE", "SI", "SK", "AL", "BA", "BY", "CH", "GB", "IS",
    "LI", "MD", "ME", "MK", "NO", "RS", "RU", "TR", "UA", "XK",
    "US", "JP", "CN", "IN", "BR", "CA", "AU", "SG", "HK", "KR",
    "SA", "AE", "ZA", "NG", "EG", "KE", "MA", "MX", "AR", "CL", "CO",
})

MISSING_STRINGS: frozenset[str] = frozenset({
    "", "none", "nan", "nat", "n/a", "na", "not available", "not applicable",
})
