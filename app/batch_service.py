"""The bulk workflow: activate every hospital, or roll the whole batch back.

1. Create all hospitals upstream under one new batch id (several at a time).
2. If every create worked, activate the batch.
3. Otherwise delete the batch, so no inactive half-batch is left upstream.
"""

import asyncio
import time
import uuid

from app.hospital_api import HospitalApiClient, HospitalApiError
from app.models import BatchResult, Hospital, HospitalResult


async def process_batch(hospitals: list[Hospital], client: HospitalApiClient, max_parallel: int = 5) -> BatchResult:
    batch_id = str(uuid.uuid4())
    started = time.perf_counter()
    limit = asyncio.Semaphore(max_parallel)  # at most `max_parallel` upstream calls at once

    async def create(hospital: Hospital) -> HospitalResult:
        async with limit:
            try:
                hospital_id = await client.create_hospital(hospital, batch_id)
                return HospitalResult(row=hospital.row, name=hospital.name, hospital_id=hospital_id, status="created")
            except HospitalApiError as exc:
                return HospitalResult(row=hospital.row, name=hospital.name, status="failed", error=str(exc))

    # Run all creates concurrently; results come back in CSV order.
    results = await asyncio.gather(*(create(hospital) for hospital in hospitals))
    failed = sum(result.status == "failed" for result in results)

    error = f"{failed} hospital(s) could not be created" if failed else None
    if not error:
        try:
            await client.activate_batch(batch_id)
        except HospitalApiError as exc:
            error = f"Activation failed: {exc}"

    if not error:
        status, created_status = "completed", "created_and_activated"
    else:
        try:
            await client.delete_batch(batch_id)
            status, created_status = "failed", "rolled_back"
        except HospitalApiError as exc:
            status, created_status = "cleanup_required", "created"
            error += f"; cleanup failed: {exc}"

    for result in results:
        if result.status == "created":
            result.status = created_status

    return BatchResult(
        batch_id=batch_id,
        status=status,
        total_hospitals=len(results),
        processed_hospitals=len(results) - failed,
        failed_hospitals=failed,
        processing_time_seconds=round(time.perf_counter() - started, 2),
        batch_activated=status == "completed",
        error=error,
        hospitals=results,
    )
