import json

from geojson_service import GeoJSONService


PION_FEAT = {
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


def test_get_geometries_returns_match():
    service = GeoJSONService()
    client = service.app.test_client()

    payload = {
        "geojson": PION_FEAT,
        "lon": 0.5,
        "lat": 0.5,
    }

    response = client.post("/get-geometries", json=payload)

    assert response.status_code == 200
    body = json.loads(response.data)
    assert body["matching_geometries"]
    assert body["matching_geometries"][0]["type"] == "Polygon"


def test_get_geometries_missing_fields_returns_400():
    service = GeoJSONService()
    client = service.app.test_client()

    response = client.post("/get-geometries", json={"lon": 0})

    assert response.status_code == 400
    body = json.loads(response.data)
    assert "error" in body
