from datetime import datetime, timedelta, timezone

import pytest

from forecast_transform import WeatherDataSimplifier


def _iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def _make_weather_data(periods):
    return {
        "properties": {
            "periods": periods,
        }
    }


def test_simplify_weather_data_current_period():
    now = datetime.now(timezone.utc)
    period = {
        "startTime": _iso(now - timedelta(minutes=30)),
        "endTime": _iso(now + timedelta(minutes=30)),
        "temperature": 10,
        "temperatureUnit": "C",
        "dewpoint": {"value": 5.0},
        "relativeHumidity": {"value": 90},
        "windSpeed": "12 mph",
        "windGust": "18 to 24 km/h",
        "windDirection": "NW",
        "probabilityOfPrecipitation": {"value": 80},
        "snowfallAmount": {"unitCode": "wmoUnit:mm", "value": 25.4},
    }
    weather_data = _make_weather_data([period])

    simplifier = WeatherDataSimplifier(
        weather_data,
        hail_in_forecast=True,
        snow_in_forecast=True,
        snow_accumulation_inches=1.0,
        sky_cover_percent=85,
    )

    simplified = simplifier.simplify_weather_data()

    assert simplified["Temperature"] == 10
    assert simplified["Dewpoint"] == pytest.approx(41.0)
    assert simplified["WindDirectionDegrees"] == 315
    assert simplified["Hail"] is True
    assert simplified["Snow"] is True
    assert simplified["SnowAccumulationInches"] == pytest.approx(1.0)
    assert simplified["WindSpeedMph"] == pytest.approx(12.0)
    assert simplified["WindGustMph"] == pytest.approx(24 * 0.621371, rel=1e-6)
    assert simplified["PrecipitationPercent"] == 80
    assert simplified["SnowMillimeters"] == pytest.approx(25.4, rel=1e-6)
    assert simplified["SkyCoverPercent"] == 85
    assert simplified["HailPercent"] is None
    assert simplified["SignificantHailPercent"] is None


def test_simplify_weather_data_handles_missing_period():
    now = datetime.now(timezone.utc)
    period = {
        "startTime": _iso(now - timedelta(hours=2)),
        "endTime": _iso(now - timedelta(hours=1)),
        "temperature": 25,
        "temperatureUnit": "F",
        "dewpoint": {"value": 0.0},
        "relativeHumidity": {"value": 50},
        "windSpeed": "5 mph",
        "windDirection": "N",
        "probabilityOfPrecipitation": {"value": 10},
    }
    weather_data = _make_weather_data([period])

    simplifier = WeatherDataSimplifier(weather_data)

    assert simplifier.simplify_weather_data() == {
        "error": "No forecast data available for the current hour"
    }


def test_snowfall_to_inches_conversions():
    now = datetime.now(timezone.utc)
    period = {
        "startTime": _iso(now - timedelta(minutes=30)),
        "endTime": _iso(now + timedelta(minutes=30)),
        "temperature": 32,
        "temperatureUnit": "F",
        "dewpoint": {"value": 0.0},
        "relativeHumidity": {"value": 100},
        "windSpeed": "3 mph",
        "windDirection": "N",
        "probabilityOfPrecipitation": {"value": 100},
        "snowfallAmount": {"unitCode": "wmoUnit:cm", "value": 5},
    }
    weather_data = _make_weather_data([period])

    simplifier = WeatherDataSimplifier(weather_data)
    result = simplifier.simplify_weather_data()

    assert result["SnowAccumulationInches"] == pytest.approx((5 * 10) / 25.4, rel=1e-3)
    assert result["SnowMillimeters"] == pytest.approx(50, rel=1e-3)
    assert result["WindGustMph"] is None
    assert result["SkyCoverPercent"] is None


def test_wind_gust_fallback_from_constructor():
    now = datetime.now(timezone.utc)
    period = {
        "startTime": _iso(now - timedelta(minutes=30)),
        "endTime": _iso(now + timedelta(minutes=30)),
        "temperature": 70,
        "temperatureUnit": "F",
        "dewpoint": {"value": 10.0},
        "relativeHumidity": {"value": 40},
        "windSpeed": "10 mph",
        "windDirection": "E",
        "probabilityOfPrecipitation": {"value": 10},
    }
    weather_data = _make_weather_data([period])

    simplifier = WeatherDataSimplifier(weather_data, wind_gust_mph=33.5)
    result = simplifier.simplify_weather_data()

    assert result["WindGustMph"] == 33.5


def test_wind_direction_override_takes_precedence():
    now = datetime.now(timezone.utc)
    period = {
        "startTime": _iso(now - timedelta(minutes=30)),
        "endTime": _iso(now + timedelta(minutes=30)),
        "temperature": 55,
        "temperatureUnit": "F",
        "dewpoint": {"value": 10.0},
        "relativeHumidity": {"value": 40},
        "windSpeed": "5 mph",
        "windDirection": "SW",
        "probabilityOfPrecipitation": {"value": 20},
    }
    weather_data = _make_weather_data([period])

    simplifier = WeatherDataSimplifier(weather_data, wind_direction_degrees=340.0)
    result = simplifier.simplify_weather_data()

    assert result["WindDirectionDegrees"] == pytest.approx(340.0)
