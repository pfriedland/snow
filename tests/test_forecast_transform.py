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
        "windDirection": "NW",
        "probabilityOfPrecipitation": {"value": 80},
        "snowfallAmount": {"unitCode": "wmoUnit:mm", "value": 25.4},
    }
    weather_data = _make_weather_data([period])

    simplifier = WeatherDataSimplifier(
        weather_data,
        hail_in_forecast=True,
        snow_in_forecast=True,
    )

    simplified = simplifier.simplify_weather_data()

    assert simplified["Temperature"] == 10
    assert simplified["Dewpoint"] == pytest.approx(41.0)
    assert simplified["WindDirectionDegrees"] == 315
    assert simplified["Hail"] is True
    assert simplified["Snow"] is True
    assert simplified["SnowAccumulationInches"] == pytest.approx(1.0)


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
