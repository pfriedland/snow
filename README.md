# Hail Forecast and GeoJSON Services

This repository bundles two Flask-based microservices:

- **Forecast service** (`forecast-service.py`): pulls hourly forecast data from the US National Weather Service (NOAA) and simplifies it with hail and snow insights.
- **GeoJSON service** (`geojson-service.py`): accepts GeoJSON FeatureCollections and returns geometries that intersect a point.

The code is container-friendly (Dockerfile, docker-compose) and stays dependency-light (`Flask`, `requests`, `shapely`).

---

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run a service (auto reload via `FLASK_ENV=development` is already provided in `docker-compose.yaml`):

```bash
FLASK_APP=forecast-service.py flask run
# or
FLASK_APP=geojson-service.py flask run
```

Docker option:

```bash
docker-compose up --build
```

Both services default to port `5000`.

---

## Forecast Service (`/get-forecast`)

**Request**

```
GET /get-forecast?plant-prefix=MyPlant&longitude=-96.95&latitude=48.38
```

- `plant-prefix` – label used in the JSON response (`plant`).
- `longitude`, `latitude` – decimal degrees.

**Response**

`forecast_source` points to the NOAA hourly forecast that was simplified.
`forecast.SnowAccumulationInches` converts NOAA snowfall fields to inches and falls back to gridpoint data when needed.
Only the period that covers the current UTC hour is used—`WeatherDataSimplifier` walks the hourly `periods` array and selects the entry whose `startTime <= now < endTime`.

```json
{
  "plant": "MyPlant",
  "coordinates": { "latitude": 48.38, "longitude": -96.95 },
  "forecast_source": "https://api.weather.gov/gridpoints/FGF/96,128/forecast/hourly",
  "forecast": {
    "Temperature": 46,
    "TemperatureUnit": "F",
    "Dewpoint": 38.0,
    "DewpointUnit": "F",
    "RelativeHumidity": 73,
    "WindSpeed": "8 mph",
    "WindDirectionDegrees": 270,
    "ProbabilityOfPrecipitation": 0,
    "ForecastTimestamp": "2025-09-27T06:00:00-05:00",
    "Hail": false,
    "Snow": false,
    "SnowAccumulationInches": 0.0
  }
}
```

### Debugging

Set `FORECAST_DEBUG=1` before starting Flask (or when using the test client) to dump raw NOAA JSON payloads and the simplified results to the console. This is invaluable when comparing the simplified output against the upstream data.

```
FORECAST_DEBUG=1 FLASK_APP=forecast-service.py flask run
```

### NOAA Requirements

Requests include a `User-Agent` required by NOAA. Ensure outbound HTTP is permitted when running the service. All network access hits `api.weather.gov`.

---

## GeoJSON Service (`/get-geometries`)

**Request**

```
POST /get-geometries
Content-Type: application/json

{
  "geojson": { "type": "FeatureCollection", "features": [...] },
  "lon": -96.95,
  "lat": 48.38
}
```

**Response**

Lists geometries whose polygon/line contain or intersect the point. If none match, returns a 404 with a helpful message.

---

## Dev Notes

### Forecast Happy Path

1. `GET /get-forecast` reaches `forecast-service.py`, where query params are validated and `ForecastExtractor` is instantiated.
2. `ForecastExtractor` hits `https://api.weather.gov/points/{lat},{lon}` to discover the relevant NOAA endpoints, then downloads the hourly forecast JSON (and grid data if snowfall inches are missing).
3. The raw payload is passed into `WeatherDataSimplifier` (`forecast_transform.py`), which selects the current hour, converts units, decodes wind direction, and adds hail/snow context before returning the slimmed JSON back to the Flask handler.

### GeoJSON Happy Path

1. `POST /get-geometries` lands in `geojson-service.py`, validating the GeoJSON body and target coordinate.
2. `GeoJSONProcessor` iterates each feature with Shapely, collecting geometries that contain or intersect the point.
3. The Flask handler serializes the matches (or a not-found message) to JSON and responds with the appropriate status code.

- `forecast_extractor.py` coordinates all NOAA calls, hazard detection, and snowfall conversion.
- `forecast_transform.py` holds `WeatherDataSimplifier`, responsible for unit conversions and final JSON formatting.
- `geojson-processor.py` encapsulates Shapely point-in-polygon matching.
- `snow-flask-app.tar` is an archival artifact; not required for day-to-day development.

You can also exercise the Flask apps manually via curl or the built-in test client. Example with the forecast service:

### Automated Tests

Unit tests cover key forecast and GeoJSON behaviors. Run them with `pytest`:

```bash
pytest
```


```python
from forecast_service import app

client = app.test_client()
resp = client.get('/get-forecast', query_string={'plant-prefix': 'MyPlant', 'longitude': -96.95, 'latitude': 48.38})
print(resp.status_code)
print(resp.get_data(as_text=True))
```

---

## Troubleshooting

- **`ModuleNotFoundError: forecast_transform`** – ensure `forecast_transform.py` hasn’t been renamed; the loader expects that exact file name.
- **SSL / network errors** – NOAA endpoints require outbound HTTPS. Verify network permissions.
- **Shapely errors** – confirm the posted GeoJSON geometries are valid polygons/lines. For multipolygons, Shapely handles them automatically.
- **Seeing old data?** NOAA caches can take a few minutes to refresh. Check the `updateTime` field in the logged payload when `FORECAST_DEBUG=1` to confirm data freshness.
- **Need to inspect raw NOAA payloads?** Enable `FORECAST_DEBUG=1` to log full JSON bodies. For even deeper inspection, open the `forecast_source` URL (and `forecastGridData` if present) in a browser.
- **Docker networking issues** – ensure the container has outbound internet. Set `FORECAST_DEBUG=1` and look for connection errors in the logs.
- **GeoJSON results missing** – verify the coordinate order (lon, lat) matches GeoJSON specs. The services expect `lon` then `lat`.
