"""Hospital Bulk Processing API.

POST /hospitals/bulk             Upload a CSV; create and activate every hospital, or none
POST /hospitals/bulk/validate    Check a CSV without creating anything
GET  /hospitals/bulk/{batch_id}  Get the result of an earlier upload
"""

import os

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile

from app.batch_service import process_batch
from app.csv_validator import validate_csv
from app.hospital_api import HospitalApiClient
from app.models import BatchResult, Hospital

BASE_URL = os.getenv("HOSPITAL_API_URL", "https://hospital-directory.onrender.com")
MAX_PARALLEL_CREATES = int(os.getenv("MAX_PARALLEL_CREATES", "5"))
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "15"))
MAX_FILE_BYTES = 1024 * 1024  # 1 MB

app = FastAPI(title="Hospital Bulk Processing API")
hospital_api = HospitalApiClient(BASE_URL, REQUEST_TIMEOUT)
batches: dict[str, BatchResult] = {}  # in-memory results; fine for a single instance


def get_hospital_api() -> HospitalApiClient:
    """Dependency, so tests can swap in a fake upstream."""
    return hospital_api


async def read_csv(file: UploadFile) -> tuple[list[Hospital], list[dict]]:
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(415, "Only .csv files are supported")
    content = await file.read(MAX_FILE_BYTES + 1)
    if len(content) > MAX_FILE_BYTES:
        raise HTTPException(413, "File is larger than 1 MB")
    return validate_csv(content)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/hospitals/bulk/validate")
async def validate(file: UploadFile = File(...)):
    hospitals, errors = await read_csv(file)
    return {"valid": not errors, "total_hospitals": len(hospitals), "errors": errors}


@app.post("/hospitals/bulk", response_model=BatchResult)
async def bulk_create(file: UploadFile = File(...), client: HospitalApiClient = Depends(get_hospital_api)):
    hospitals, errors = await read_csv(file)
    if errors:
        raise HTTPException(422, {"message": "CSV validation failed", "errors": errors})
    result = await process_batch(hospitals, client, MAX_PARALLEL_CREATES)
    batches[result.batch_id] = result
    return result


@app.get("/hospitals/bulk/{batch_id}", response_model=BatchResult)
async def get_batch(batch_id: str):
    if batch_id not in batches:
        raise HTTPException(404, "Batch not found")
    return batches[batch_id]
