from datetime import datetime, timedelta, timezone

import pytest

from forecast_extractor import ForecastExtractor

POINTS_URL = "https://api.weather.gov/points/45.0,-100.0"
FORECAST_URL = "https://api.weather.gov/gridpoints/FGF/96,128/forecast/hourly"
GRID_URL = "https://api.weather.gov/gridpoints/FGF/96,128"


class DummyResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class DummySession:
    def __init__(self, responses):
        self.responses = responses
        self.headers = {}
        self.requested_urls = []

    def get(self, url, timeout=10):
        self.requested_urls.append(url)
        payload = self.responses[url]
        return DummyResponse(payload)


@pytest.fixture
def point_metadata():
    return {
        "properties": {
            "forecastHourly": FORECAST_URL,
            "forecastGridData": GRID_URL,
            "relativeLocation": {
                "properties": {
                    "city": "Stephen",
                    "state": "MN",
                }
            },
        }
    }


def _make_period(now, **overrides):
    base = {
        "startTime": (now - timedelta(minutes=30)).isoformat(),
        "endTime": (now + timedelta(minutes=30)).isoformat(),
        "temperature": 30,
        "temperatureUnit": "F",
        "dewpoint": {"value": -2.0},
        "relativeHumidity": {"value": 80},
        "windSpeed": "10 mph",
        "windDirection": "NW",
        "probabilityOfPrecipitation": {"value": 70},
        "shortForecast": "Snow and hail likely",
        "detailedForecast": "",
    }
    base.update(overrides)
    return base


def test_get_forecast_uses_hourly_snowfall(point_metadata):
    now = datetime.now(timezone.utc)
    forecast_payload = {
        "properties": {
            "periods": [
                _make_period(
                    now,
                    dewpoint={"value": -1.0},
                    snowfallAmount={"unitCode": "wmoUnit:mm", "value": 25.4},
                    windGust="20 km/h",
                )
            ]
        }
    }

    grid_payload = {
        "properties": {
            "snowfallAmount": {
                "uom": "wmoUnit:mm",
                "values": [{"validTime": now.isoformat(), "value": 25.4}],
            },
            "skyCover": {
                "values": [{"validTime": now.isoformat(), "value": 65}],
            },
            "windDirection": {
                "uom": "wmoUnit:degree_(angle)",
                "values": [{"validTime": now.isoformat(), "value": 340}],
            },
        }
    }

    responses = {
        POINTS_URL: point_metadata,
        FORECAST_URL: forecast_payload,
        GRID_URL: grid_payload,
    }

    extractor = ForecastExtractor(
        "TestPlant",
        longitude=-100.0,
        latitude=45.0,
        session=DummySession(responses),
    )

    result = extractor.get_forecast()

    assert result["forecast"]["Snow"] is True
    assert result["forecast"]["Hail"] is True
    assert result["forecast"]["SnowAccumulationInches"] == pytest.approx(1.0)
    assert result["forecast"]["Temperature"] == 30
    assert result["forecast"]["Dewpoint"] == pytest.approx(30.2, rel=1e-3)
    assert result["forecast_source"] == FORECAST_URL
    assert result["location"] == {
        "city": "Stephen",
        "state": "MN",
        "country": "US",
    }
    assert result["forecast"]["WindSpeedMph"] == pytest.approx(10.0)
    assert result["forecast"]["WindGustMph"] == pytest.approx(20 * 0.621371, rel=1e-6)
    assert result["forecast"]["PrecipitationPercent"] == 70
    assert result["forecast"]["SnowMillimeters"] == pytest.approx(25.4, rel=1e-6)
    assert result["forecast"]["SkyCoverPercent"] == pytest.approx(65)
    assert result["forecast"]["HailPercent"] is None
    assert result["forecast"]["SignificantHailPercent"] is None
    assert result["forecast"]["WindDirectionDegrees"] == pytest.approx(340)


def test_get_forecast_falls_back_to_grid_data(point_metadata):
    now = datetime.now(timezone.utc)
    forecast_payload = {
        "properties": {
            "periods": [
                _make_period(now, shortForecast="Partly cloudy", snowfallAmount=None)
            ]
        }
    }

    grid_payload = {
        "properties": {
            "snowfallAmount": {
                "uom": "wmoUnit:mm",
                "values": [
                    {"validTime": now.isoformat(), "value": 12.7},
                ],
            },
            "skyCover": {
                "values": [{"validTime": now.isoformat(), "value": 45}],
            },
            "windGust": {
                "uom": "wmoUnit:km_h-1",
                "values": [{"validTime": now.isoformat(), "value": 30}],
            },
            "windDirection": {
                "uom": "wmoUnit:degree_(angle)",
                "values": [{"validTime": now.isoformat(), "value": 190}],
            },
        }
    }

    responses = {
        POINTS_URL: point_metadata,
        FORECAST_URL: forecast_payload,
        GRID_URL: grid_payload,
    }

    extractor = ForecastExtractor(
        "TestPlant",
        longitude=-100.0,
        latitude=45.0,
        session=DummySession(responses),
    )

    result = extractor.get_forecast()

    assert result["forecast"]["SnowAccumulationInches"] == pytest.approx(0.5, abs=1e-6)
    assert result["forecast"]["Snow"] is False
    assert result["forecast"]["Hail"] is False
    assert GRID_URL in extractor.session.requested_urls
    assert result["location"]["state"] == "MN"
    assert result["forecast"]["SkyCoverPercent"] == pytest.approx(45)
    assert result["forecast"]["SnowMillimeters"] == pytest.approx(12.7, rel=1e-6)
    assert result["forecast"]["WindGustMph"] == pytest.approx(30 * 0.621371, rel=1e-6)
    assert result["forecast"]["WindDirectionDegrees"] == pytest.approx(190)
