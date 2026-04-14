# How it works — deep dive

## Request lifecycle (happy path)

```
HTTP request
  → FastAPI router (router.py)
    → Service / use-case class
      → Repository (MongoDB via Motor)
      ↕ External API (httpx)
    → Celery task enqueued (apply_async)
HTTP response returned immediately
                              ↓
                    Celery worker picks up task
                      → Service runs async code (_run helper)
                      → Repository updated
```

The API never waits for external work to complete. It enqueues a Celery task with a `countdown` (delay in seconds), returns the HTTP response, and the worker handles everything asynchronously.

---

## Module-by-module explanation

### `core/`

**`config.py`** — single `Settings` object built from `.env` via Pydantic-Settings.  
Every module imports `settings` from here. No raw `os.getenv` calls elsewhere.

**`database.py`** — Motor (async MongoDB driver) singleton.  
`get_db()` returns the same `AsyncIOMotorDatabase` instance across the app lifetime.  
On startup (`main.py` lifespan), each repository calls `ensure_indexes()` to create MongoDB indexes if they don't exist yet.

**`celery_app.py`** — one Celery app shared by both integrations.  
Broker and backend are both Redis. `task_acks_late=True` + `task_reject_on_worker_lost=True` ensure tasks are not lost if a worker crashes mid-execution.  
Celery beat schedule lives here: `collect_results` runs every 3600 seconds.

---

### `auth/`

**`dependencies.py`** — FastAPI `Depends`-based auth guard.  
`get_current_patient` reads the `Authorization: Bearer <token>` header.  
Currently a **stub** — it accepts any token and returns a mock `CurrentPatient`. Wire real JWT decode + signature verification using `settings.jwt_secret` before going to production.

`require_patient` adds a role check on top: only `ROLE_PATIENTS` is accepted.

---

### Mammoth integration

#### Authentication (`MammothApiService`)

On the first API call the service POSTs credentials to `/auth/email/login` and stores the returned token in a module-level `TTLCache` (14-day TTL, single slot).  
Every subsequent call within those 14 days reuses the cached token — no re-login overhead.

#### Rate limiting (`MammothApiService`)

A simple in-process token-bucket: `_rate_tokens` starts at 60 and is refilled to 60 every 60 seconds by a background asyncio task (`_refill_tokens`).  
Each call to `get_patient_data` consumes one token. If the bucket is empty, the call raises immediately. This mirrors whatever rate limit Mammoth imposes on their API.

#### Empty-value stripping

`_remove_empty_values` walks the entire response tree and removes any string that equals `"n/a"`, `"not specified"`, `"new member"`, or `"unknown"`. This keeps the MongoDB documents clean and avoids false positives in the change-detection hash.

#### Patient registration flow

```
POST /patient/registration
  → MammothCreatePatientService.create()
      → MammothApiService.create_patient()   # POST /patients on Mammoth
  ← Returns MammothPatientCreateResponse
  → Enqueues save_mammoth_patient_data (countdown = MAMMOTH_DATA_SAVE_DELAY seconds)
```

#### Data sync flow (`MammothPatientSaveDataService`)

```
save_mammoth_patient_data task runs
  → get_mammoth_patient_status()        # polls Mammoth for status
  → repo.update_status()                # writes status to MongoDB
  if status == PENDING and retry_count < 2:
      re-enqueue self with countdown 600 s
  if status == SUCCESS:
      _update_patient_data_fields()     # fetch all 13 data types
      enqueue save_mammoth_lab_results (countdown = MAMMOTH_LAB_RESULTS_DELAY)
```

**Change detection** (`MammothDataHashService`): each data type's payload is MD5-hashed and compared against the stored hash in the `hashes` map on the patient document. Only fields that actually changed are written to MongoDB, reducing write amplification.

#### Lab-results flow (`MammothPatientSaveLabResultsService`)

```
save_mammoth_lab_results task runs
  → get_patient_data(uid, "lab-result-groups")   # fetch all groups
  → filter: keep only groups that have location data
  → for each group:
      get_lab_result(uid, "lab-results", group_id)
  → repo.update_field("labResultGroups", ...)
  → repo.update_field("labResults", ...)
```

---

### Quest integration — two separate APIs

Quest exposes two completely different APIs with different auth mechanisms:

#### Booking API (`QuestBookingClient`)

- Transport: **XML over HTTPS**
- Auth: **HMAC-SHA1 digest** — signs `METHOD + content-type + date + endpoint-url` with the secret, sends the signature as `Authorization: yournextagency TOKEN:DIGEST` and the date as `x-yournextagency-date`. The date must match what Quest's server expects so there is no clock skew tolerance.
- Used for: appointment CRUD, available slots, PSC location refresh.

#### Orders / Results API (`QuestApiClient`)

- Transport: **JSON over HTTPS**
- Auth: **OAuth2 client_credentials** — POSTs `client_id` + `client_secret` to the token endpoint, caches the `access_token` for the lifetime of the client instance, then sends it as `Authorization: Bearer`.
- Used for: order submission (HL7 message body), result polling, document retrieval.

#### Appointment slot generation

Quest's booking API only returns slots that are *actually available*. The service also generates the full grid of possible slots based on the location's operating hours, merges the two sets, and marks unavailable slots as `DISABLED`. This lets the frontend render a complete calendar without gaps.

```
_get_location_hours(location, date)   # reads standardized_drug_screen_hours
_generate_slots(date, from, to, length_minutes, site_code, ...)
  → iterates from open to close in `length_minutes` increments
  → if slot exists in Quest API response → use API slot (available)
  → else → synthetic slot with status=DISABLED
```

#### Order submission

Orders are submitted as raw HL7 v2 messages. The Celery task `create_quest_order` receives the pre-built HL7 string from the caller and POSTs it directly to the Quest API. The order document is upserted in MongoDB with status `SENT`.

#### Hourly result collection (`collect_results`)

Celery beat fires this every hour:

```
find_all_sent()                         # all orders with status=SENT
POST /results  {resultType: "HL7"}      # pull results from Quest
for each result:
    match by orderId → QuestOrder
    base64-encode HL7 message
    append QuestOrderResult to order.results
    set order.status = COMPLETED
    repo.save(order)
POST /results/acknowledge               # tell Quest we received them
```

#### Location data lifecycle

`POST /patient-service-centers` is an admin endpoint that:
1. Fetches all Quest PSC locations as XML
2. Parses them into `QuestLocation` objects (`QuestBookingParser.parse_locations_xml`)
3. De-duplicates by `siteCode` and `latitude,longitude`
4. Truncates the `quest_locations` collection and bulk-inserts the fresh data

This should be run periodically (or on demand) to keep the local location cache in sync with Quest's network.

---

## Key design patterns

**Repository pattern** — all MongoDB access goes through `*Repository` classes. The router/service layers never touch the database directly. This makes it straightforward to swap the storage backend or write unit tests with a fake repository.

**Service layer** — business logic lives in `*Service` classes, not in routers. Routers are thin: validate input, call one service method, return the result (or enqueue a task).

**Async throughout, Celery bridge** — FastAPI and Motor are fully async. Celery workers are synchronous. The `_run(coro)` helper in each tasks file creates a fresh event loop, runs the coroutine to completion, then closes the loop. This is necessary because Celery's worker thread does not have a running event loop.

**Enums as API contracts** — `MammothDataTypesEnum`, `QuestAppointmentStatusEnum`, etc. centralize the string constants shared between services, models, and repositories, preventing typos from causing silent bugs.

**Pydantic everywhere** — request bodies, response shapes, and MongoDB document models are all Pydantic models. `populate_by_name = True` allows both camelCase (MongoDB / external API) and snake_case (Python) field names on the same model.
