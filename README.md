# JRNYS Integration API (Python)

FastAPI service that integrates two external health platforms into the JRNYS ecosystem:

- **Mammoth EHR** — patient registration, clinical data sync, lab results
- **Quest Diagnostics** — lab test ordering, PSC appointment booking, result collection

---

## Architecture overview

```
main.py                          # FastAPI app, lifespan startup
├── core/
│   ├── config.py                # Pydantic-Settings, reads .env
│   ├── database.py              # Motor (async MongoDB) singleton
│   └── celery_app.py            # Celery worker + beat schedule
├── auth/
│   └── dependencies.py          # JWT Bearer stub (wire up real decode here)
├── mammoth/
│   ├── router.py                # /integration/mammoth/* endpoints
│   ├── services/
│   │   ├── mammoth_api_service.py          # HTTP client (JSON REST)
│   │   ├── mammoth_create_patient_service.py
│   │   ├── mammoth_patient_save_data_service.py
│   │   ├── mammoth_patient_save_lab_results_service.py
│   │   └── mammoth_data_hash_service.py
│   ├── tasks/mammoth_tasks.py   # Celery tasks
│   ├── repositories/            # MongoDB access layer
│   ├── models/                  # Pydantic ODM models
│   └── schemas/                 # Request / response Pydantic models
└── quest/
    ├── router.py                # /integration/quest/* endpoints
    ├── services/
    │   ├── quest_booking_client.py   # XML API, HMAC-SHA1 auth
    │   ├── quest_booking_service.py  # appointment orchestration
    │   ├── quest_booking_parser.py   # XML ↔ model conversion
    │   ├── quest_api_client.py       # JSON API, OAuth2 client-credentials
    │   ├── quest_order_service.py    # order submit + result collection
    │   └── quest_location_service.py
    ├── tasks/quest_tasks.py     # Celery tasks
    ├── repositories/
    ├── models/
    └── schemas/
```

---

## Requirements

- Python 3.11+
- MongoDB
- Redis (Celery broker + backend)
- External credentials for Mammoth and Quest (see `.env` below)

Install dependencies:

```bash
pip install -r requirements.txt
```

---

## Configuration

Copy `.env.example` to `.env` (or set environment variables directly):

```dotenv
# MongoDB
MONGODB_URL=mongodb://localhost:27017
MONGODB_DB_NAME=jrnys

# Redis
REDIS_URL=redis://localhost:6379/0

# Mammoth EHR
MAMMOTH_API_BASE_URL=https://api.mammoth.example.com
MAMMOTH_API_LOGIN_EMAIL=your@email.com
MAMMOTH_API_LOGIN_PASSWORD=secret
MAMMOTH_DATA_SAVE_DELAY=5          # seconds before data-save task runs
MAMMOTH_LAB_RESULTS_DELAY=10       # seconds before lab-results task runs
MAMMOTH_LAB_RESULTS_PATIENT_DELAY=180

# Quest Booking (XML API)
QUEST_BOOKING_BASE_URL=https://booking.quest.example.com
QUEST_BOOKING_AUTHORIZATION_TOKEN=token
QUEST_BOOKING_SECRET=hmac_secret

# Quest Orders (JSON API)
QUEST_ORDERS_BASE_URL=https://orders.quest.example.com
QUEST_CLIENT_ID=client_id
QUEST_CLIENT_SECRET=client_secret
QUEST_ZIP_SEARCH_RADIUS_METERS=16000

# AWS S3 (requisition documents)
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_REGION=us-east-1
AWS_S3_BUCKET=jrnys-quest-docs

# Auth
JWT_SECRET=changeme
```

---

## Running

**API server**

```bash
uvicorn main:app --reload
```

**Celery worker** (processes background tasks)

```bash
celery -A core.celery_app.celery_app worker --loglevel=info
```

**Celery beat** (scheduled tasks — Quest result polling every hour)

```bash
celery -A core.celery_app.celery_app beat --loglevel=info
```

Interactive API docs are available at `http://localhost:8000/docs`.

---

## API endpoints

### Mammoth `POST /integration/mammoth/...`

| Method | Path | Description |
|--------|------|-------------|
| POST | `/patient/registration` | Register a new patient in Mammoth EHR |
| POST | `/patients/data` | Trigger full data sync for a patient |
| GET | `/patients/my` | Return stored Mammoth data for a patient |
| GET | `/patient/lab-results` | Enqueue lab-results fetch |
| GET | `/patient/fields` | Widget: which EHR fields are filled |
| DELETE | `/patients/{patient_uid}` | Remove Mammoth data (staff action) |

### Quest `/integration/quest/...`

| Method | Path | Description |
|--------|------|-------------|
| POST | `/appointments` | Book a Quest appointment |
| GET | `/appointments` | List patient appointments (upcoming / past) |
| GET | `/appointments/slots` | Available slots by location and date |
| GET | `/appointments/{id}` | Fetch and sync appointment details |
| POST | `/appointments/{id}/modify` | Reschedule appointment |
| DELETE | `/appointments/{id}` | Cancel appointment |
| POST | `/locations` | Search PSC locations by city / state / keyword |
| POST | `/patient-service-centers` | Refresh PSC database from Quest API (admin) |
| GET | `/locations/cities` | Distinct city list, optionally filtered by state |

---

## Background tasks (Celery)

| Task | Trigger | Retries |
|------|---------|---------|
| `save_mammoth_patient_data` | After patient registration or data-sync request | 2 × 10 min |
| `save_mammoth_lab_results` | After successful data sync | 2 × 5 min |
| `create_quest_order` | When an order needs to be submitted | 3 × 1 min |
| `collect_results` | Celery beat, **every hour** | 2 × 5 min |

---

## Health check

```
GET /health  →  {"status": "ok"}
```
