import pytest

from tests.conftest import csv_file

VALID_CSV = "name,address,phone\nGeneral Hospital,123 Main Street,5551234\nCity Hospital,456 Park Avenue,\n"


def test_validate_does_not_call_upstream(client, hospital_api):
    response = client.post("/hospitals/bulk/validate", files=csv_file(VALID_CSV))

    assert response.json() == {"valid": True, "total_hospitals": 2, "errors": []}
    assert hospital_api.created == []


def test_bulk_upload_and_fetch_result(client):
    body = client.post("/hospitals/bulk", files=csv_file(VALID_CSV)).json()

    assert body["status"] == "completed" and body["batch_activated"] is True
    assert (body["total_hospitals"], body["processed_hospitals"], body["failed_hospitals"]) == (2, 2, 0)
    assert body["hospitals"][0] == {"row": 1, "name": "General Hospital", "hospital_id": 1, "status": "created_and_activated", "error": None}

    assert client.get(f"/hospitals/bulk/{body['batch_id']}").json() == body
    assert client.get("/hospitals/bulk/unknown").status_code == 404


@pytest.mark.parametrize(
    "file, status_code",
    [
        (csv_file("name,address\n,1 Main St\n"), 422),
        (csv_file("name,address\nA,B\n", "hospitals.txt"), 415),
        (csv_file(b"x" * (1024 * 1024 + 1)), 413),
    ],
    ids=["invalid row", "not csv", "over 1 MB"],
)
def test_bad_uploads_are_rejected_before_any_upstream_call(client, hospital_api, file, status_code):
    assert client.post("/hospitals/bulk", files=file).status_code == status_code
    assert hospital_api.created == []
