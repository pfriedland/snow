from geojson_processor import GeoJSONProcessor


SIMPLE_FEATURES = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [0, 0],
                        [0, 1],
                        [1, 1],
                        [1, 0],
                        [0, 0],
                    ]
                ],
            },
            "properties": {},
        }
    ],
}


def test_find_matching_geometries():
    processor = GeoJSONProcessor(SIMPLE_FEATURES, lon=0.5, lat=0.5)

    matches = processor.find_matching_geometries()

    assert len(matches) == 1
    assert matches[0]["type"] == "Polygon"


def test_get_response_no_matches():
    processor = GeoJSONProcessor(SIMPLE_FEATURES, lon=2, lat=2)
    processor.find_matching_geometries()

    payload, status = processor.get_response()

    assert status == 404
    assert payload["message"].startswith("No geometries")
