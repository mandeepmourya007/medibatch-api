import asyncio

import httpx
import pytest

from app.batch_service import process_batch
from app.hospital_api import HospitalApiClient, HospitalApiError
from app.models import Hospital
from tests.conftest import FakeHospitalApi

pytestmark = pytest.mark.anyio

HOSPITALS = [Hospital(row=1, name="A", address="1 Street"), Hospital(row=2, name="B", address="2 Street")]


async def test_success_creates_then_activates_the_batch():
    hospital_api = FakeHospitalApi()

    result = await process_batch(HOSPITALS, hospital_api)

    assert result.status == "completed" and result.batch_activated
    assert [h.status for h in result.hospitals] == ["created_and_activated", "created_and_activated"]
    assert {batch_id for _, batch_id in hospital_api.created} == {result.batch_id}  # same batch id for all
    assert hospital_api.activated == [result.batch_id]


@pytest.mark.parametrize(
    "hospital_api, status, row_statuses",
    [
        (FakeHospitalApi(fail_names={"B"}), "failed", ["rolled_back", "failed"]),
        (FakeHospitalApi(fail_activate=True), "failed", ["rolled_back", "rolled_back"]),
        (FakeHospitalApi(fail_names={"A"}, fail_delete=True), "cleanup_required", ["failed", "created"]),
    ],
    ids=["create fails", "activation fails", "rollback fails"],
)
async def test_any_failure_rolls_back_the_batch(hospital_api, status, row_statuses):
    result = await process_batch(HOSPITALS, hospital_api)

    assert result.status == status and not result.batch_activated
    assert [h.status for h in result.hospitals] == row_statuses


async def test_creates_run_concurrently():
    class SlowHospitalApi(FakeHospitalApi):
        async def create_hospital(self, hospital, batch_id):
            await asyncio.sleep(0.2)
            return await super().create_hospital(hospital, batch_id)

    hospitals = [Hospital(row=n, name=f"H{n}", address="St") for n in range(10)]

    result = await process_batch(hospitals, SlowHospitalApi(), max_parallel=5)

    assert result.processing_time_seconds < 1.0  # 10 x 0.2s would be 2s one at a time


async def test_client_returns_id_and_wraps_errors():
    def upstream(request):
        return httpx.Response(200, json={"id": 42}) if request.method == "POST" else httpx.Response(500)

    client = HospitalApiClient("https://directory.test", transport=httpx.MockTransport(upstream))

    assert await client.create_hospital(HOSPITALS[0], "b1") == 42
    with pytest.raises(HospitalApiError, match="HTTP 500"):
        await client.activate_batch("b1")
