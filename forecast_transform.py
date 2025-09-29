"""Transform NOAA forecast payloads into a compact structure for clients."""

import json
import re
from datetime import datetime, timezone

MM_PER_INCH = 25.4


class WeatherDataSimplifier:
    """Condense raw hourly forecast data into a hail/snow-aware snapshot."""

    def __init__(
        self,
        weather_data,
        hail_in_forecast=False,
        snow_in_forecast=False,
        snow_accumulation_inches=None,
        sky_cover_percent=None,
        wind_gust_mph=None,
        wind_direction_degrees=None,
    ):
        """Store the forecast payload and hazard metadata for later use."""
        self.weather_data = weather_data
        self.hail_in_forecast = hail_in_forecast
        self.snow_in_forecast = snow_in_forecast
        self.snow_accumulation_inches = snow_accumulation_inches
        self.sky_cover_percent = sky_cover_percent
        self.wind_gust_mph = wind_gust_mph
        self.wind_direction_override = wind_direction_degrees

    def celsius_to_fahrenheit(self, celsius):
        """Convert a temperature value from Celsius to Fahrenheit."""
        return (celsius * 9/5) + 32

    def wind_direction_to_degrees(self, direction):
        """Translate NOAA wind direction abbreviations into degrees."""
        directions = {
            "N": 0, "NNE": 22.5, "NE": 45, "ENE": 67.5,
            "E": 90, "ESE": 112.5, "SE": 135, "SSE": 157.5,
            "S": 180, "SSW": 202.5, "SW": 225, "WSW": 247.5,
            "W": 270, "WNW": 292.5, "NW": 315, "NNW": 337.5
        }
        return directions.get(direction, None)

    def find_current_hour_period(self):
        """Locate the forecast period that covers the current UTC hour."""
        current_time = datetime.now(timezone.utc)

        for period in self.weather_data['properties']['periods']:
            period_start_time = datetime.fromisoformat(period['startTime'].replace('Z', '+00:00'))
            period_end_time = datetime.fromisoformat(period['endTime'].replace('Z', '+00:00'))

            if period_start_time <= current_time < period_end_time:
                return period

        return None

    def simplify_weather_data(self):
        """Return a trimmed forecast payload for the current hour and hazards."""
        current_period = self.find_current_hour_period()

        if not current_period:
            return {"error": "No forecast data available for the current hour"}

        forecast_timestamp = current_period['startTime']

        snow_inches = self.snow_accumulation_inches
        if snow_inches is None:
            snow_inches = self._snowfall_to_inches(current_period.get('snowfallAmount'))

        sky_cover_percent = self.sky_cover_percent
        if sky_cover_percent is None:
            sky_cover_percent = self._value_or_none(
                current_period.get('skyCover', {}).get('value')
                if isinstance(current_period.get('skyCover'), dict)
                else current_period.get('skyCover')
            )

        gust_mph = self._parse_speed(current_period.get('windGust'))
        if gust_mph is None and self.wind_gust_mph is not None:
            gust_mph = self.wind_gust_mph

        wind_direction_degrees = self.wind_direction_override
        if wind_direction_degrees is None:
            wind_direction_degrees = self._resolve_wind_direction(current_period.get('windDirection'))

        simplified_data = {
            "Temperature": current_period['temperature'],
            "TemperatureUnit": current_period['temperatureUnit'],
            "Dewpoint": self.celsius_to_fahrenheit(current_period['dewpoint']['value']),
            "DewpointUnit": "F",
            "RelativeHumidity": current_period['relativeHumidity']['value'],
            "WindSpeed": current_period['windSpeed'],
            "WindDirectionDegrees": wind_direction_degrees,
            "ProbabilityOfPrecipitation": current_period['probabilityOfPrecipitation']['value'],
            "ForecastTimestamp": forecast_timestamp,
            "Hail": self.hail_in_forecast,
            "Snow": self.snow_in_forecast,
            "SnowAccumulationInches": self._round_value(snow_inches),
            "WindSpeedMph": self._parse_speed(current_period.get('windSpeed')),
            "WindGustMph": gust_mph,
            "PrecipitationPercent": self._value_or_none(current_period.get('probabilityOfPrecipitation', {}).get('value')),
            "SnowMillimeters": self._round_value(self._snow_inches_to_mm(snow_inches)),
            "SkyCoverPercent": self._value_or_none(sky_cover_percent),
            "HailPercent": None,
            "SignificantHailPercent": None,
        }

        return simplified_data

    def get_simplified_json(self):
        """Serialize the simplified forecast to formatted JSON."""
        simplified_data = self.simplify_weather_data()
        return json.dumps(simplified_data, indent=2)

    def _snowfall_to_inches(self, snowfall_section):
        """Attempt to convert a per-period snowfall block into inches."""
        if not isinstance(snowfall_section, dict):
            return None
        value = snowfall_section.get('value')
        if value is None:
            return None
        unit_code = (snowfall_section.get('unitCode') or '').lower()
        if 'wmo' in unit_code:
            if 'unit:mm' in unit_code:
                return value / MM_PER_INCH
            if 'unit:cm' in unit_code:
                return (value * 10) / MM_PER_INCH
            if 'unit:m' in unit_code:
                return (value * 1000) / MM_PER_INCH
            if 'unit:in' in unit_code or 'unit:inch' in unit_code:
                return value
        return value if snowfall_section.get('unitCode') == 'inches' else None

    def _resolve_wind_direction(self, direction):
        """Return degrees for a wind direction token or numeric value."""
        if direction is None:
            return None
        if isinstance(direction, (int, float)):
            return float(direction)
        if isinstance(direction, str):
            token = direction.strip()
            try:
                return float(token)
            except ValueError:
                return self.wind_direction_to_degrees(token)
        return None

    def _round_value(self, value):
        if value is None:
            return None
        return round(value, 2)

    def _parse_speed(self, value):
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            matches = re.findall(r"[0-9]+\.?[0-9]*", value)
            if matches:
                numbers = [float(m) for m in matches]
                max_value = max(numbers)
                if "km" in value.lower():
                    return max_value * 0.621371
                return max_value
        return None

    def _snow_inches_to_mm(self, inches):
        if inches is None:
            return None
        mm = inches * MM_PER_INCH
        return mm

    def _value_or_none(self, value):
        return value if value is not None else None
