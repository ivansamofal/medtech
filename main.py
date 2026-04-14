"""
FastAPI application entry point.
Run with: uvicorn main:app --reload
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.database import close_db, get_db
from mammoth.repositories.mammoth_patient_repository import MammothPatientRepository
from mammoth.router import router as mammoth_router
from quest.repositories.quest_appointment_repository import QuestAppointmentRepository
from quest.repositories.quest_location_repository import QuestLocationRepository
from quest.repositories.quest_order_repository import QuestOrderRepository
from quest.router import router as quest_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup – ensure MongoDB indexes
    db = get_db()
    await MammothPatientRepository(db).ensure_indexes()
    await QuestAppointmentRepository(db).ensure_indexes()
    await QuestOrderRepository(db).ensure_indexes()
    await QuestLocationRepository(db).ensure_indexes()
    yield
    # Shutdown
    await close_db()


app = FastAPI(
    title="JRNYS Integration API (Python)",
    description="Mammoth EHR and Quest Diagnostics integrations",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(mammoth_router)
app.include_router(quest_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
