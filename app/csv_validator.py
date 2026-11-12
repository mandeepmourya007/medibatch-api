"""Read and validate the uploaded CSV. Nothing is sent upstream unless this passes."""

import csv
import io

from app.models import Hospital

MAX_HOSPITALS = 20
ALLOWED_COLUMNS = {"name", "address", "phone"}
REQUIRED_COLUMNS = {"name", "address"}


def validate_csv(content: bytes) -> tuple[list[Hospital], list[dict]]:
    """Return (hospitals, errors). If there are any errors, no hospitals are returned."""
    try:
        text = content.decode("utf-8-sig")  # also strips an Excel BOM
        rows = [row for row in csv.reader(io.StringIO(text), strict=True) if any(cell.strip() for cell in row)]
    except (UnicodeDecodeError, csv.Error) as exc:
        return [], [_error(f"Could not read CSV: {exc}")]

    if not rows:
        return [], [_error("CSV is empty")]

    header = [column.strip().lower() for column in rows[0]]
    columns = set(header)
    if len(columns) != len(header) or not columns <= ALLOWED_COLUMNS or not REQUIRED_COLUMNS <= columns:
        return [], [_error("Header must be name,address,phone (phone is optional)", field="header")]

    data = rows[1:]
    if not data:
        return [], [_error("CSV has no hospitals")]
    if len(data) > MAX_HOSPITALS:
        return [], [_error(f"A CSV can have at most {MAX_HOSPITALS} hospitals, got {len(data)}", field="rows")]

    hospitals, errors = [], []
    for number, row in enumerate(data, start=1):
        if len(row) != len(header):
            errors.append(_error("Wrong number of columns", row=number))
            continue
        values = {column: cell.strip() for column, cell in zip(header, row)}
        for field in ("name", "address"):
            if not values[field]:
                errors.append(_error(f"{field} is required", row=number, field=field))
        hospitals.append(Hospital(row=number, name=values["name"], address=values["address"], phone=values.get("phone") or None))

    return ([] if errors else hospitals), errors


def _error(message: str, row: int | None = None, field: str | None = None) -> dict:
    return {"row": row, "field": field, "message": message}
