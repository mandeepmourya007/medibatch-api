# Hospital Bulk Processing API

Upload a CSV of up to 20 hospitals. The service creates them through the [Hospital Directory API](https://hospital-directory.onrender.com/docs) under one batch ID, and activates the batch only if **every** hospital was created. If anything fails, it deletes the batch, so no half-finished batch is left behind.

## Run locally

Requires Python 3.10+.

```bash
# 1. Set up (first time only)
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Start the API (leave it running)
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000/docs to try every endpoint in the browser. Press `Ctrl + C` to stop.

```bash
# 3. Run the tests (in another terminal, after `source .venv/bin/activate`)
pytest
```

No configuration is needed; the defaults work. To change a setting, create a `.env` file (see [Settings](#settings-env)) and start with `uvicorn app.main:app --reload --env-file .env`.

## API

**Base URL:** `http://127.0.0.1:8000` when running locally. All paths below are relative to it.

Set it once in your terminal to use the `curl` examples:

```bash
BASE_URL=http://127.0.0.1:8000
```

**Interactive docs (Swagger UI):** `$BASE_URL/docs`. Every endpoint has a **Try it out** button with a file picker.

| Method | Path | What it does |
| --- | --- | --- |
| `GET` | `/health` | Health check |
| `POST` | `/hospitals/bulk/validate` | Check a CSV without creating anything |
| `POST` | `/hospitals/bulk` | Upload a CSV, then create and activate all hospitals (or none) |
| `GET` | `/hospitals/bulk/{batch_id}` | Get the result of an earlier upload |

Both `POST` endpoints take **multipart form data** with the CSV in a field named `file`. In Postman: **Body → form-data**, key `file`, type **File**.

### Health check

```bash
curl $BASE_URL/health
```

```json
{"status": "ok"}
```

### Validate a CSV

```bash
curl -F "file=@sample_data/valid_hospitals.csv" $BASE_URL/hospitals/bulk/validate
```

```json
{"valid": true, "total_hospitals": 3, "errors": []}
```

### Bulk create

This calls the real Hospital Directory API.

```bash
curl -F "file=@sample_data/valid_hospitals.csv" $BASE_URL/hospitals/bulk
```

```json
{
  "batch_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "total_hospitals": 3,
  "processed_hospitals": 3,
  "failed_hospitals": 0,
  "processing_time_seconds": 1.42,
  "batch_activated": true,
  "error": null,
  "hospitals": [
    {"row": 1, "name": "General Hospital", "hospital_id": 101, "status": "created_and_activated", "error": null}
  ]
}
```

**Batch `status`:** `completed` (all created and activated), `failed` (something failed and the batch was deleted), or `cleanup_required` (something failed and the delete also failed, so check upstream by hand).

**Hospital `status`:** `created_and_activated`, `failed`, `rolled_back` (created, then deleted with the batch), or `created` (only when cleanup failed).

### Get a batch result

```bash
curl $BASE_URL/hospitals/bulk/550e8400-e29b-41d4-a716-446655440000
```

This returns the same JSON as the bulk create response, or `404` if the batch ID is unknown.

### Errors

| Status | When |
| --- | --- |
| `422` | Invalid CSV (errors listed per row), or no `file` in the request |
| `415` | The file isn't a `.csv` |
| `413` | The file is over 1 MB |
| `404` | Unknown batch ID |

```json
{"detail": {"message": "CSV validation failed", "errors": [{"row": 1, "field": "address", "message": "address is required"}]}}
```

The upstream API runs on Render's free tier and can take about 50 seconds to wake up. If the first upload fails with timeouts, open https://hospital-directory.onrender.com/docs once to wake it, then retry.

## CSV format

```csv
name,address,phone
General Hospital,123 Main Street,5551234
City Hospital,"456 Park Avenue, Block B",
```

- `name` and `address` are required; `phone` is optional.
- At most 20 hospitals and 1 MB per file. UTF-8 only; blank lines are ignored.
- The whole file is checked first. Any error returns `422` with a list of errors per row, and nothing is sent upstream.
- A file that isn't `.csv` gets `415`. A file over 1 MB gets `413`.

Try `sample_data/valid_hospitals.csv` and `sample_data/invalid_hospitals.csv`.

## Code

```text
app/
  main.py              Settings and the HTTP endpoints
  csv_validator.py     Reads and validates the CSV
  batch_service.py     The workflow: create all, then activate or roll back
  hospital_api.py      Calls the upstream Hospital Directory API
  models.py            Data shapes (Pydantic)
tests/                 Tests use a fake upstream, so they need no network
```

## Design decisions

- **All or nothing.** Hospitals are created inactive under one batch ID, and activated together only if all of them succeeded. Otherwise the batch is deleted.
- **Concurrent creates.** The app is async end to end (`httpx.AsyncClient`). Creates run together with `asyncio.gather`, capped at 5 at a time by an `asyncio.Semaphore` (`MAX_PARALLEL_CREATES`). A 20-hospital batch takes about 4 round trips instead of 20, without flooding the upstream API.
- **Validate before calling upstream.** A bad file never creates anything.
- **No retries on create.** Retrying after a timeout could create a duplicate hospital, so a failed batch is rolled back instead.
- **In-memory results.** Batch results live in a dictionary, which is fine for one instance. A restart clears them.

**Scaling further:** for bigger files or many users, the next steps would be:
- return `202` straight away and process in the background, with progress polling;
- keep batch results in a database;
- move the work to a task queue (Celery or RQ with Redis).

## Settings (`.env`)

| Variable | Default |
| --- | --- |
| `HOSPITAL_API_URL` | `https://hospital-directory.onrender.com` |
| `MAX_PARALLEL_CREATES` | `5` |
| `REQUEST_TIMEOUT_SECONDS` | `15` |
