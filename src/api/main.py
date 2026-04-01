"""Главное приложение FastAPI"""

import asyncio
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import List
from uuid import UUID

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.schemas import (
    # EventListResponse,
    EventSchema,
    RegistrationRequest,
    RegistrationResponse,
    SeatListResponse,
    UnregistrationRequest,
)
from src.domain.worker import BookingService
from src.infrastructure.client import EventsProviderClient
from src.infrastructure.database import get_db
from src.infrastructure.paginator import EventsPaginator

# from src.app.worker.sync import run_sync_job
from src.infrastructure.repos import EventRepository

# Глобальная переменная для задачи
sync_task = None
load_dotenv()

sync = BookingService.sync_events


# Фоновая задача для синхронизации данных
async def background_sync_worker():
    while True:
        try:
            ...  # sync()
        except Exception as e:
            print(f"Sync error: {e}")
        # Спим 24 часа
        await asyncio.sleep(86400)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: запускаем воркер
    global sync_task
    sync_task = asyncio.create_task(background_sync_worker())
    yield
    # Shutdown: отменяем воркер
    if sync_task:
        sync_task.cancel()
        try:
            await sync_task
        except asyncio.CancelledError:
            pass


app = FastAPI(lifespan=lifespan)

BASE_URL = os.getenv("BASE_URL")
API_KEY = os.getenv("API_KEY")


def get_events_client() -> EventsProviderClient:
    return EventsProviderClient(base_url=BASE_URL, api_key=API_KEY)


@app.get(
    "/api/events/",
    response_model=List[EventSchema],
)
async def get_event_list(
    changed_at: str = Query(..., description="Дата для фильтрации событий"),
    db: AsyncSession = Depends(get_db),
    client: EventsProviderClient = Depends(get_events_client),
) -> List[EventSchema]:
    """Получить информацию о событиях"""

    repo = EventRepository(db)
    paginator = EventsPaginator(client, changed_at)
    events = []
    async for event in paginator:
        events.append(event)
        await repo.upsert(event)

    if not events:
        raise HTTPException(status_code=404, detail="Events not found")
    return [EventSchema.model_validate(event) for event in events]


@app.get("/api/events/{event_id}", response_model=EventSchema)
async def get_event_by_id(
    event_id: UUID,
    db: AsyncSession = Depends(get_db),
    client: EventsProviderClient = Depends(get_events_client),
) -> EventSchema:
    """Получить информацию о событии по ID"""

    repo = EventRepository(db)

    event = await repo.get_by_id(event_id)
    # event = await client.get_event_by_id(event_id=event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    return EventSchema.model_validate(event)


@app.get(
    "/api/events/{event_id}/seats/",
    response_model=SeatListResponse,
)
async def get_seat_list(
    event_id: UUID,
    db: AsyncSession = Depends(get_db),
    client: EventsProviderClient = Depends(get_events_client),
) -> SeatListResponse:
    """Получить информацию о свободных местах для события"""

    repo = EventRepository(db)

    seats = await repo.get_seat_list(event_id)
    if not seats:
        raise HTTPException(status_code=404, detail="Seats not found")
    return SeatListResponse(
        seats=[seat for seat in seats],
    )


@app.post(
    "/api/events/{event_id}/register/",
    response_model=RegistrationResponse,
    status_code=201,
)
async def register_for_event(
    event_id: UUID,
    registration: RegistrationRequest,
    db: AsyncSession = Depends(get_db),
    client: EventsProviderClient = Depends(get_events_client),
) -> RegistrationResponse:
    """Зарегистрироваться на событие"""

    event = await client.get_event_by_id(event_id=event_id)
    event_time = event.get("event_time")
    registration_deadline = event.get("registration_deadline")

    if "published" not in event.get("status", ""):
        raise HTTPException(status_code=400, detail="Event is not published")
    if datetime.now(timezone.utc) > datetime.fromisoformat(event_time):
        raise HTTPException(status_code=400, detail="Date is in the past")
    if datetime.now(timezone.utc) > datetime.fromisoformat(registration_deadline):
        raise HTTPException(status_code=400, detail="Registration is closed")

    ticket_id = await client.register(
        event_id=event_id,
        first_name=registration.first_name,
        last_name=registration.last_name,
        email=registration.email,
        seat=registration.seat,
    )
    if not ticket_id:
        raise HTTPException(status_code=403, detail="Registration failed")
    return RegistrationResponse(
        ticket_id=ticket_id,
    )


@app.delete(
    "/api/events/{event_id}/unregister/",
    status_code=200,
)
async def unregister_from_event(
    event_id: UUID,
    unregistration: UnregistrationRequest,
    db: AsyncSession = Depends(get_db),
    client: EventsProviderClient = Depends(get_events_client),
) -> dict:
    """Отменить регистрацию на событие"""

    event = await client.get_event_by_id(event_id=event_id)
    event_time = event.get("event_time")

    if datetime.now(timezone.utc) > datetime.fromisoformat(event_time):
        raise HTTPException(status_code=400, detail="Дата не может быть в прошлом")

    request = await client.unregister(
        event_id=event_id,
        ticket_id=unregistration.ticket_id,
    )
    return request


@app.post("/api/sync/trigger/")
async def sync_events(
    db: AsyncSession = Depends(get_db),
    client: EventsProviderClient = Depends(get_events_client),
    changed_at: str = Query(
        "2020-01-01T22:28:35.325302+03:00", description="Дата для фильтрации событий"
    ),
) -> dict:
    """Синхронизация событий"""

    repo = EventRepository(db)
    paginator = EventsPaginator(client, changed_at)
    async for event in paginator:
        await repo.upsert(event)

    return {"status": "ok"}


@app.get("/api/health")
async def get_health():
    """Проверка работоспособности сервиса"""
    return {"status": "ok"}
