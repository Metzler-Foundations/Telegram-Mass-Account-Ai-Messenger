#!/usr/bin/env python3
"""Country code validation for account creation."""

import logging
from typing import List

logger = logging.getLogger(__name__)


class CountryValidator:
    """Validates country codes."""

    # ISO 3166-1 alpha-2 codes (subset of common countries)
    VALID_COUNTRIES = {
        "US",
        "GB",
        "CA",
        "AU",
        "DE",
        "FR",
        "IT",
        "ES",
        "NL",
        "BE",
        "CH",
        "AT",
        "SE",
        "NO",
        "DK",
        "FI",
        "PL",
        "CZ",
        "RO",
        "GR",
        "PT",
        "IE",
        "NZ",
        "SG",
        "HK",
        "JP",
        "KR",
        "TW",
        "IN",
        "BR",
        "MX",
        "AR",
        "CL",
        "CO",
        "PE",
        "VE",
        "ZA",
        "NG",
        "EG",
        "KE",
        "IL",
        "TR",
        "UA",
        "RU",
        "BY",
        "KZ",
        "TH",
        "VN",
        "PH",
        "ID",
    }

    @staticmethod
    def validate(country_code: str) -> bool:
        """Validate country code."""
        if not country_code or not isinstance(country_code, str):
            return False

        code = country_code.upper().strip()

        if len(code) != 2:
            logger.warning(f"Invalid country code length: {country_code}")
            return False

        if code not in CountryValidator.VALID_COUNTRIES:
            logger.warning(f"Unsupported country code: {country_code}")
            return False

        return True

    @staticmethod
    def get_supported_countries() -> List[str]:
        """Get list of supported countries."""
        return sorted(CountryValidator.VALID_COUNTRIES)


def validate_country(code: str) -> bool:
    """Validate country code."""
    return CountryValidator.validate(code)
