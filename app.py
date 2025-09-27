"""Minimal Flask endpoint for matching GeoJSON geometries by coordinate."""

import json

from flask import Flask, Response, request
from shapely.geometry import shape, Point

app = Flask(__name__)


@app.route('/get-geometries', methods=['POST'])
def get_geometries():
    """Return any GeoJSON geometries that contain or intersect the provided point."""
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

        point = Point(lon, lat)
        matching_geometries = []

        for feature in geojson.get('features', []):
            geometry = feature.get('geometry', None)
            if not geometry:
                continue

            geom_shape = shape(geometry)
            if geom_shape.contains(point) or geom_shape.intersects(point):
                matching_geometries.append(geometry)

        if matching_geometries:
            payload = {"matching_geometries": matching_geometries}
            status = 200
        else:
            payload = {"message": "No geometries found for the given location."}
            status = 404

        return Response(
            json.dumps(payload, indent=2, default=str),
            status=status,
            mimetype="application/json",
        )

    except Exception as e:  # pragma: no cover - defensive catch for unexpected errors
        payload = {"error": str(e)}
        return Response(
            json.dumps(payload, indent=2, default=str),
            status=500,
            mimetype="application/json",
        )


if __name__ == '__main__':
    app.run(debug=True)
