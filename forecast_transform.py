"""Transform NOAA forecast payloads into a compact structure for clients."""

import json
from datetime import datetime, timezone

MM_PER_INCH = 25.4


class WeatherDataSimplifier:
    """Condense raw hourly forecast data into a hail/snow-aware snapshot."""

    def __init__(self, weather_data, hail_in_forecast=False, snow_in_forecast=False, snow_accumulation_inches=None):
        """Store the forecast payload and hazard metadata for later use."""
        self.weather_data = weather_data
        self.hail_in_forecast = hail_in_forecast
        self.snow_in_forecast = snow_in_forecast
        self.snow_accumulation_inches = snow_accumulation_inches

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

        simplified_data = {
            "Temperature": current_period['temperature'],
            "TemperatureUnit": current_period['temperatureUnit'],
            "Dewpoint": self.celsius_to_fahrenheit(current_period['dewpoint']['value']),
            "DewpointUnit": "F",
            "RelativeHumidity": current_period['relativeHumidity']['value'],
            "WindSpeed": current_period['windSpeed'],
            "WindDirectionDegrees": self.wind_direction_to_degrees(current_period['windDirection']),
            "ProbabilityOfPrecipitation": current_period['probabilityOfPrecipitation']['value'],
            "ForecastTimestamp": forecast_timestamp,
            "Hail": self.hail_in_forecast,
            "Snow": self.snow_in_forecast,
            "SnowAccumulationInches": self._round_inches(snow_inches),
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

    def _round_inches(self, inches):
        """Round snowfall inches to two decimals, preserving missing data."""
        if inches is None:
            return None
        return round(inches, 2)
