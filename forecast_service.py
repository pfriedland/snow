"""Flask service exposing simplified NOAA forecasts via ForecastExtractor."""

import json
import logging
import os

from flask import Flask, Response, request

from forecast_extractor import ForecastExtractor

app = Flask(__name__)


if os.getenv("FORECAST_DEBUG"):
    logging.basicConfig(level=logging.DEBUG)
    logging.getLogger(__name__).debug("Forecast debug mode enabled")


@app.route('/get-forecast', methods=['GET'])
def get_forecast():
    """Fetch and return the simplified forecast for the requested coordinate."""
    try:
        plant_name = request.args.get('plant-prefix')
        longitude = request.args.get('longitude', type=float)
        latitude = request.args.get('latitude', type=float)

        if not plant_name or longitude is None or latitude is None:
            payload = {
                "error": "Missing required parameters: plant-prefix, longitude, or latitude",
                "http_status_code": 400,
            }
            return Response(
                json.dumps(payload, indent=2, default=str),
                status=400,
                mimetype="application/json",
            )

        forecast_extractor = ForecastExtractor(plant_name, longitude, latitude)
        forecast_data = forecast_extractor.get_forecast()
        forecast_data["http_status_code"] = 200
        return Response(
            json.dumps(forecast_data, indent=2, default=str),
            status=200,
            mimetype="application/json",
        )

    except ValueError as exc:
        payload = {"error": f"Input Error: {exc}", "http_status_code": 400}
        return Response(
            json.dumps(payload, indent=2, default=str),
            status=400,
            mimetype="application/json",
        )

    except Exception as exc:  # pragma: no cover - defensive catch for unexpected errors
        payload = {"error": f"An error occurred: {exc}", "http_status_code": 500}
        return Response(
            json.dumps(payload, indent=2, default=str),
            status=500,
            mimetype="application/json",
        )


if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5001)
