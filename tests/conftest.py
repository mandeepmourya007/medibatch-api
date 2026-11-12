import pytest
from fastapi.testclient import TestClient

from app.hospital_api import HospitalApiError
from app.main import app, get_hospital_api


class FakeHospitalApi:
    """Stand-in for the upstream API. Flip the flags to simulate failures."""

    def __init__(self, fail_names=(), fail_activate=False, fail_delete=False):
        self.fail_names = set(fail_names)
        self.fail_activate = fail_activate
        self.fail_delete = fail_delete
        self.created, self.activated, self.deleted = [], [], []

    async def create_hospital(self, hospital, batch_id):
        if hospital.name in self.fail_names:
            raise HospitalApiError("POST /hospitals/ returned HTTP 500")
        self.created.append((hospital.name, batch_id))
        return len(self.created)

    async def activate_batch(self, batch_id):
        if self.fail_activate:
            raise HospitalApiError("PATCH activate returned HTTP 500")
        self.activated.append(batch_id)

    async def delete_batch(self, batch_id):
        if self.fail_delete:
            raise HospitalApiError("DELETE batch failed: ReadTimeout")
        self.deleted.append(batch_id)


@pytest.fixture
def anyio_backend():
    return "asyncio"  # run async tests with asyncio (anyio's pytest plugin ships with FastAPI)


@pytest.fixture
def hospital_api():
    return FakeHospitalApi()


@pytest.fixture
def client(hospital_api):
    app.dependency_overrides[get_hospital_api] = lambda: hospital_api
    yield TestClient(app)
    app.dependency_overrides.clear()


def csv_file(content, filename="hospitals.csv"):
    data = content.encode() if isinstance(content, str) else content
    return {"file": (filename, data, "text/csv")}
