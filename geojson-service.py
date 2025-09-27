"""Flask service wrapper exposing the GeoJSONProcessor over HTTP."""

import json

from flask import Flask, Response, request

from geojson_processor import GeoJSONProcessor


class GeoJSONService:
    """Configure and run the GeoJSON matching Flask application."""

    def __init__(self):
        """Initialize the Flask app instance and register routes."""
        self.app = Flask(__name__)
        self._set_routes()

    def _set_routes(self):
        """Wire the `/get-geometries` endpoint to the GeoJSONProcessor logic."""

        @self.app.route('/get-geometries', methods=['POST'])
        def get_geometries():
            """Return geometries that contain or intersect the posted coordinate."""
            try:
                data = request.json or {}
                geojson = data.get('geojson', None)
                lon = data.get('lon', None)
                lat = data.get('lat', None)

                if not geojson or lon is None or lat is None:
                    payload = {"error": "Missing geoJSON or lon/lat"}
                    return Response(
                        json.dumps(payload, indent=2, default=str),
                        status=400,
                        mimetype="application/json",
                    )

                processor = GeoJSONProcessor(geojson, lon, lat)
                processor.find_matching_geometries()
                response, status_code = processor.get_response()
                return Response(
                    json.dumps(response, indent=2, default=str),
                    status=status_code,
                    mimetype="application/json",
                )

            except Exception as exc:  # pragma: no cover - defensive catch for unexpected errors
                payload = {"error": str(exc)}
                return Response(
                    json.dumps(payload, indent=2, default=str),
                    status=500,
                    mimetype="application/json",
                )

    def run(self, host='0.0.0.0', port=5000, debug=True):
        """Run the Flask development server with the configured settings."""
        self.app.run(host=host, port=port, debug=debug)


if __name__ == '__main__':
    service = GeoJSONService()
    service.run()
