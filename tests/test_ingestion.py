import json

import azure.functions as func

from src.ingestion import handle_put_sensor



def test_handle_put_sensor_invalid_json():
    req = func.HttpRequest(
        method="PUT",
        body=b"invalid-json",
        url="/api/sensors",
        headers={"Content-Type": "application/json"},
    )

    response = handle_put_sensor(req)

    assert response.status_code == 400



def test_handle_put_sensor_missing_fields():
    req = func.HttpRequest(
        method="PUT",
        body=json.dumps({"machine_id": "PUMP-1001"}).encode(),
        url="/api/sensors",
        headers={"Content-Type": "application/json"},
    )

    response = handle_put_sensor(req)

    assert response.status_code == 400