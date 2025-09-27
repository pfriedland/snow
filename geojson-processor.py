"""Utility helpers for filtering GeoJSON features by coordinate containment."""

from shapely.geometry import shape, Point


class GeoJSONProcessor:
    """Identify GeoJSON geometries that contain or intersect a target point."""

    def __init__(self, geojson, lon, lat):
        """Store the GeoJSON payload and pre-compute the query point."""
        self.geojson = geojson
        self.point = Point(lon, lat)
        self.matching_geometries = []

    def find_matching_geometries(self):
        """Populate and return geometries that overlap the stored point."""
        for feature in self.geojson.get('features', []):
            geometry = feature.get('geometry')
            if not geometry:
                continue

            geom_shape = shape(geometry)
            if geom_shape.contains(self.point) or geom_shape.intersects(self.point):
                self.matching_geometries.append(geometry)

        return self.matching_geometries

    def get_response(self):
        """Return a tuple of response payload and status code for Flask handlers."""
        if self.matching_geometries:
            return {"matching_geometries": self.matching_geometries}, 200
        return {"message": "No geometries found for the given location."}, 404
