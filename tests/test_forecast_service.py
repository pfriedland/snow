import importlib.util
import json
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "forecast_service.py"
MODULE_SPEC = importlib.util.spec_from_file_location("forecast_service_module", MODULE_PATH)
forecast_service = importlib.util.module_from_spec(MODULE_SPEC)
MODULE_SPEC.loader.exec_module(forecast_service)


class DummyExtractor:
    def __init__(self, plant, lon, lat):
        self.plant = plant
        self.lon = lon
        self.lat = lat
        self.called = True

    def get_forecast(self):
        return {
            "plant": self.plant,
            "coordinates": {"longitude": self.lon, "latitude": self.lat},
            "location": {"city": "Test City", "state": "TS", "country": "US"},
            "forecast_source": "https://example.com/forecast",
            "forecast": {
                "Temperature": 72,
                "WindSpeedMph": 10,
                "WindGustMph": 15,
                "SnowMillimeters": 0,
                "SkyCoverPercent": 50,
                "PrecipitationPercent": 20,
                "HailPercent": None,
                "SignificantHailPercent": None,
            },
        }


class ErrorExtractor(DummyExtractor):
    def get_forecast(self):
        raise RuntimeError("boom")


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(forecast_service, "ForecastExtractor", DummyExtractor)
    return forecast_service.app.test_client()


def test_get_forecast_success(client):
    response = client.get(
        "/get-forecast",
        query_string={"plant-prefix": "Test", "longitude": -90.0, "latitude": 45.0},
    )

    assert response.status_code == 200
    body = json.loads(response.data)
    assert body["plant"] == "Test"
    assert body["forecast"]["Temperature"] == 72
    assert body["location"]["city"] == "Test City"
    assert body["forecast"]["SkyCoverPercent"] == 50
    assert body["forecast"]["SnowMillimeters"] == 0
    assert body["http_status_code"] == 200


def test_get_forecast_missing_params_returns_400(client):
    response = client.get("/get-forecast", query_string={"plant-prefix": "Test"})

    assert response.status_code == 400
    body = json.loads(response.data)
    assert "Missing required parameters" in body["error"]
    assert body["http_status_code"] == 400


def test_get_forecast_handles_exceptions(monkeypatch):
    monkeypatch.setattr(forecast_service, "ForecastExtractor", ErrorExtractor)
    client = forecast_service.app.test_client()

    response = client.get(
        "/get-forecast",
        query_string={"plant-prefix": "Test", "longitude": -90.0, "latitude": 45.0},
    )

    assert response.status_code == 500
    body = json.loads(response.data)
    assert "An error occurred" in body["error"]
    assert body["http_status_code"] == 500
