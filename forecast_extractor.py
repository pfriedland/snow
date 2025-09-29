"""Utilities for fetching and simplifying NOAA weather forecasts."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

import requests
from requests import Session

from forecast_transform import WeatherDataSimplifier

# NOAA requires a descriptive User-Agent header for API requests.
DEFAULT_USER_AGENT = "snow-forecast-service/1.0 (+https://www.enel.com/)"
MM_PER_INCH = 25.4

logger = logging.getLogger(__name__)


def _format_json(data: Any) -> str:
    """Return a pretty JSON string for debug logging."""
    try:
        return json.dumps(data, indent=2, default=str)
    except TypeError:
        return str(data)


class ForecastExtractor:
    """Fetch hourly NOAA data for a coordinate and distill it into key insights."""

    POINTS_URL_TEMPLATE = "https://api.weather.gov/points/{lat},{lon}"

    def __init__(
        self,
        plant_prefix: str,
        longitude: float,
        latitude: float,
        *,
        session: Optional[Session] = None,
        request_timeout: int = 10,
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> None:
        """Validate inputs and set up the HTTP session used for NOAA requests."""
        self.plant_prefix = self._validate_plant_prefix(plant_prefix)
        self.longitude = self._validate_longitude(longitude)
        self.latitude = self._validate_latitude(latitude)
        self.timeout = request_timeout
        self.session = session or requests.Session()
        self._ensure_session_headers(user_agent)

    # ---------------------- Validation helpers ----------------------
    def _validate_plant_prefix(self, plant_prefix: str) -> str:
        """Ensure the plant prefix is a non-empty string value."""
        if not isinstance(plant_prefix, str) or not plant_prefix.strip():
            raise ValueError("plant-prefix must be a non-empty string")
        return plant_prefix.strip()

    def _validate_longitude(self, longitude: float) -> float:
        """Ensure longitude is numeric and within the valid geographic bounds."""
        try:
            lon = float(longitude)
        except (TypeError, ValueError) as exc:
            raise ValueError("longitude must be a number") from exc
        if not -180.0 <= lon <= 180.0:
            raise ValueError("longitude must be between -180 and 180 degrees")
        return lon

    def _validate_latitude(self, latitude: float) -> float:
        """Ensure latitude is numeric and within the valid geographic bounds."""
        try:
            lat = float(latitude)
        except (TypeError, ValueError) as exc:
            raise ValueError("latitude must be a number") from exc
        if not -90.0 <= lat <= 90.0:
            raise ValueError("latitude must be between -90 and 90 degrees")
        return lat

    # ---------------------- Session setup ----------------------
    def _ensure_session_headers(self, user_agent: str) -> None:
        """Populate required headers for NOAA API etiquette."""
        headers = self.session.headers
        headers.setdefault("User-Agent", user_agent)
        headers.setdefault("Accept", "application/geo+json, application/json;q=0.9")

    # ---------------------- NOAA integration ----------------------
    def _fetch_points_metadata(self) -> Dict[str, Any]:
        """Return NOAA point metadata including links to forecast resources."""
        url = self.POINTS_URL_TEMPLATE.format(lat=self.latitude, lon=self.longitude)
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        payload = response.json()
        logger.debug("Fetched NOAA point metadata from %s:\n%s", url, _format_json(payload))
        return payload

    def _fetch_forecast_payload(self, forecast_url: str) -> Dict[str, Any]:
        """Retrieve a forecast payload from the provided NOAA forecast URL."""
        response = self.session.get(forecast_url, timeout=self.timeout)
        response.raise_for_status()
        payload = response.json()
        logger.debug("Fetched NOAA forecast payload from %s", forecast_url)
        logger.debug("Forecast payload detail:\n%s", _format_json(payload))
        return payload

    # ---------------------- Public API ----------------------
    def get_forecast(self) -> Dict[str, Any]:
        """Return simplified hourly forecast data for the configured coordinate."""
        try:
            points_metadata = self._fetch_points_metadata()
        except requests.RequestException as exc:
            raise RuntimeError("Failed to retrieve NOAA point metadata") from exc

        # forecast_url = self._extract_forecast_url(points_metadata)
        # try:
        #     forecast_payload = self._fetch_forecast_payload(forecast_url)
        # except requests.RequestException as exc:
        #     raise RuntimeError("Failed to retrieve NOAA forecast data") from exc

        # hail_expected = self._detect_hail(forecast_payload)
        # snow_expected = self._detect_snow(forecast_payload)
        # logger.debug(
        #     "Hazard detection for plant=%s: hail=%s snow=%s",
        #     self.plant_prefix,
        #     hail_expected,
        #     snow_expected,
        # )
        snow_accum_inches = self._extract_snow_accumulation_inches(forecast_payload)
        sky_cover_percent = None
        wind_gust_mph = None
        wind_direction_degrees = None

        grid_payload = None
        grid_url = self._extract_grid_data_url(points_metadata)
        if grid_url:
            try:
                grid_payload = self._fetch_grid_payload(grid_url)
            except requests.RequestException:
                grid_payload = None
                logger.debug("Failed to fetch NOAA grid payload", exc_info=True)

        if grid_payload:
            if snow_accum_inches is None:
                snow_accum_inches = self._extract_snow_from_grid(grid_payload)
                if snow_accum_inches is not None:
                    logger.debug(
                        "Derived snow accumulation %.2f in from grid payload",
                        snow_accum_inches,
                    )
                else:
                    logger.debug("Grid payload did not include snow accumulation values")

            sky_cover_percent = self._extract_sky_cover_from_grid(grid_payload)
            wind_gust_mph = self._extract_wind_gust_from_grid(grid_payload)
            wind_direction_degrees = self._extract_wind_direction_from_grid(grid_payload)

        simplifier = WeatherDataSimplifier(
            forecast_payload,
            hail_in_forecast=hail_expected,
            snow_in_forecast=snow_expected,
            snow_accumulation_inches=snow_accum_inches,
            sky_cover_percent=sky_cover_percent,
            wind_gust_mph=wind_gust_mph,
            wind_direction_degrees=wind_direction_degrees,
        )
        simplified_forecast = simplifier.simplify_weather_data()
        logger.debug(
            "Simplified forecast for plant=%s lat=%s lon=%s:\n%s",
            self.plant_prefix,
            self.latitude,
            self.longitude,
            _format_json(simplified_forecast),
        )

        return {
            "plant": self.plant_prefix,
            "coordinates": {
                "latitude": self.latitude,
                "longitude": self.longitude,
            },
            "location": self._extract_location(points_metadata),
            "forecast_source": forecast_url,
            "forecast": simplified_forecast,
        }

    # ---------------------- Helpers ----------------------
    def _extract_forecast_url(self, metadata: Dict[str, Any]) -> str:
        """Read the forecast URL from the NOAA point metadata response."""
        try:
            properties = metadata["properties"]
        except KeyError as exc:
            raise RuntimeError("Unexpected NOAA point metadata format") from exc

        forecast_url = properties.get("forecastHourly") or properties.get("forecast")
        if not forecast_url:
            raise RuntimeError("NOAA point metadata does not include a forecast URL")
        return forecast_url

    def _extract_location(self, metadata: Dict[str, Any]) -> Dict[str, Optional[str]]:
        properties = metadata.get("properties", {})
        relative = properties.get("relativeLocation", {}).get("properties", {})

        city = relative.get("city")
        state = relative.get("state")

        # NOAA points are US-based. Include country when we have any locality context.
        country = "US" if city or state else None

        return {
            "city": city,
            "state": state,
            "country": country,
        }

    def _detect_hail(self, forecast_payload: Dict[str, Any]) -> bool:
        """Return True when any forecast period mentions hail."""
        try:
            periods = forecast_payload["properties"]["periods"]
        except (KeyError, TypeError):
            return False

        for period in periods:
            if self._period_mentions_hail(period):
                return True
        return False

    def _detect_snow(self, forecast_payload: Dict[str, Any]) -> bool:
        """Return True when any forecast period references snowfall conditions."""
        try:
            periods = forecast_payload["properties"]["periods"]
        except (KeyError, TypeError):
            return False

        for period in periods:
            if self._period_mentions_snow(period):
                return True
        return False

    def _period_mentions_hail(self, period: Dict[str, Any]) -> bool:
        """Identify hail references within textual period descriptions."""
        for key in ("shortForecast", "detailedForecast", "name"):
            text = period.get(key)
            if isinstance(text, str) and "hail" in text.lower():
                return True
        return False

    def _period_mentions_snow(self, period: Dict[str, Any]) -> bool:
        """Identify snow-related terminology within a forecast period."""
        snow_terms = ("snow", "flurries", "blizzard", "wintry mix")
        for key in ("shortForecast", "detailedForecast", "name"):
            text = period.get(key)
            if isinstance(text, str):
                lower = text.lower()
                if any(term in lower for term in snow_terms):
                    return True
        return False

    def _extract_snow_accumulation_inches(self, forecast_payload: Dict[str, Any]) -> Optional[float]:
        """Pull snowfall accumulation from the hourly forecast payload if present."""
        try:
            periods = forecast_payload["properties"]["periods"]
        except (KeyError, TypeError):
            return None

        for period in periods:
            inches = self._snowfall_section_to_inches(period.get("snowfallAmount"))
            if inches is not None:
                return inches
        return None

    def _extract_grid_data_url(self, metadata: Dict[str, Any]) -> Optional[str]:
        """Return the grid data URL, if provided, for richer forecast metrics."""
        return metadata.get("properties", {}).get("forecastGridData")

    def _fetch_grid_payload(self, grid_url: str) -> Dict[str, Any]:
        """Fetch the NOAA gridpoint forecast payload."""
        response = self.session.get(grid_url, timeout=self.timeout)
        response.raise_for_status()
        payload = response.json()
        logger.debug("Fetched NOAA grid payload from %s", grid_url)
        logger.debug("Grid payload detail:\n%s", _format_json(payload))
        return payload

    def _extract_snow_from_grid(self, grid_payload: Dict[str, Any]) -> Optional[float]:
        """Derive snowfall accumulation from the gridpoint payload values."""
        snowfall = grid_payload.get("properties", {}).get("snowfallAmount")
        if not isinstance(snowfall, dict):
            return None
        values = snowfall.get("values")
        if not isinstance(values, list):
            return None
        for entry in values:
            inches = self._snowfall_value_to_inches(entry.get("value"), snowfall.get("uom"))
            if inches is not None:
                return inches
        return None

    def _extract_sky_cover_from_grid(self, grid_payload: Dict[str, Any]) -> Optional[float]:
        sky = grid_payload.get("properties", {}).get("skyCover")
        if not isinstance(sky, dict):
            return None
        values = sky.get("values")
        if not isinstance(values, list):
            return None
        for entry in values:
            value = entry.get("value")
            if value is not None:
                return float(value)
        return None

    def _extract_wind_gust_from_grid(self, grid_payload: Dict[str, Any]) -> Optional[float]:
        wind = grid_payload.get("properties", {}).get("windGust")
        if not isinstance(wind, dict):
            return None
        values = wind.get("values")
        if not isinstance(values, list):
            return None
        uom = wind.get("uom") or ""
        for entry in values:
            value = entry.get("value")
            if value is None:
                continue
            return self._convert_speed_to_mph(value, uom)
        return None

    def _extract_wind_direction_from_grid(self, grid_payload: Dict[str, Any]) -> Optional[float]:
        direction = grid_payload.get("properties", {}).get("windDirection")
        if not isinstance(direction, dict):
            return None
        values = direction.get("values")
        if not isinstance(values, list):
            return None
        for entry in values:
            value = entry.get("value")
            if value is None:
                continue
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
        return None

    def _convert_speed_to_mph(self, value: float, unit_code: str) -> float:
        code = (unit_code or "").lower()
        if "km" in code:
            return float(value) * 0.621371
        if "m_s" in code or "ms-1" in code:
            return float(value) * 2.23694
        if "knot" in code or "kt" in code:
            return float(value) * 1.15078
        # Assume mph by default
        return float(value)

    def _snowfall_section_to_inches(self, section: Optional[Dict[str, Any]]) -> Optional[float]:
        """Convert a snowfall dictionary to inches if units are supported."""
        if not isinstance(section, dict):
            return None
        return self._snowfall_value_to_inches(section.get("value"), section.get("unitCode"))

    def _snowfall_value_to_inches(self, value: Optional[float], unit_code: Optional[str]) -> Optional[float]:
        """Normalize a snowfall value to inches based on the provided unit code."""
        if value is None:
            return None
        code = (unit_code or "").lower()
        if "unit:mm" in code:
            return value / MM_PER_INCH
        if "unit:cm" in code:
            return (value * 10) / MM_PER_INCH
        if "unit:m" in code:
            return (value * 1000) / MM_PER_INCH
        if "unit:in" in code or "unit:inch" in code:
            return value
        return None
