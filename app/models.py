"""Data shapes shared by the app."""

from typing import Literal

from pydantic import BaseModel


class Hospital(BaseModel):
    """One valid row from the uploaded CSV."""

    row: int
    name: str
    address: str
    phone: str | None = None


class HospitalResult(BaseModel):
    """What happened to one hospital."""

    row: int
    name: str
    hospital_id: int | None = None
    status: Literal["created_and_activated", "created", "failed", "rolled_back"]
    error: str | None = None


class BatchResult(BaseModel):
    """What happened to the whole upload."""

    batch_id: str
    status: Literal["completed", "failed", "cleanup_required"]
    total_hospitals: int
    processed_hospitals: int
    failed_hospitals: int
    processing_time_seconds: float
    batch_activated: bool
    error: str | None = None
    hospitals: list[HospitalResult]
