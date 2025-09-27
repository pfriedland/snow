from flask import Flask, request, jsonify
from shapely.geometry import shape, Point
import json

app = Flask(__name__)

# Route to accept GeoJSON and return matching geometries based on lon/lat
@app.route('/get-geometries', methods=['POST'])
def get_geometries():
    try:
        data = request.json

        # Extract geoJSON and lon/lat from the request body
        geojson = data.get('geojson', None)
        lon = data.get('lon', None)
        lat = data.get('lat', None)

        if not geojson or lon is None or lat is None:
            return jsonify({"error": "Missing geoJSON or lon/lat"}), 400

        # Convert lon/lat to a Shapely Point object
        point = Point(lon, lat)

        # Store matching geometries
        matching_geometries = []

        # Iterate through GeoJSON features
        for feature in geojson.get('features', []):
            geometry = feature.get('geometry', None)

            # Check if geometry exists
            if geometry:
                # Create a shapely geometry from the feature's geometry
                geom_shape = shape(geometry)

                # Check if the point is within the geometry
                if geom_shape.contains(point) or geom_shape.intersects(point):
                    matching_geometries.append(geometry)

        # Return matched geometries or message if none were found
        if matching_geometries:
            return jsonify({"matching_geometries": matching_geometries}), 200
        else:
            return jsonify({"message": "No geometries found for the given location."}), 404

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
