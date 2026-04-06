"""Главное приложение FastAPI"""

import asyncio
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from dotenv import load_dotenv
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.schemas import (
    # EventListResponse,
    EventSchema,
    RegistrationRequest,
    RegistrationResponse,
    SeatListResponse,
    UnregistrationRequest,
)
from src.infrastructure.client import EventsProviderClient
from src.infrastructure.database import get_db
from src.infrastructure.paginator import EventsPaginator
from src.infrastructure.repos import EventRepository
from src.infrastructure.sync import SyncService

# Глобальная переменная для задачи
sync_task = None
load_dotenv()


BASE_URL = os.getenv("BASE_URL", "https://events-provider.dev-2.python-labs.ru")
API_KEY = os.getenv("API_KEY")


def get_events_client(request: Request) -> EventsProviderClient:
    return EventsProviderClient(BASE_URL, API_KEY)


# Фоновая задача для синхронизации данных
async def background_sync_worker(
    db: AsyncSession = Depends(get_db),
    client: EventsProviderClient = Depends(get_events_client),
):
    changed_at = "2000-01-01"
    while True:
        try:
            paginator = EventsPaginator(client, changed_at)
            repo = EventRepository(db)
            async for event in paginator:
                await repo.upsert(event)
            await db.commit()
        except Exception as e:
            print(f"Sync error: {e}")
        # Спим 24 часа
        await asyncio.sleep(86400)


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.system("alembic upgrade head")
    # Startup: запускаем воркер
    global sync_task
    # app.state.events_client = EventsProviderClient(BASE_URL, API_KEY)
    sync_task = asyncio.create_task(background_sync_worker(db=Depends(get_db)))
    yield
    # Shutdown: отменяем воркер
    if sync_task:
        sync_task.cancel()
        try:
            await sync_task
        except asyncio.CancelledError:
            pass


app = FastAPI()


@app.get(
    "/api/events/",
)
async def get_event_list(
    db: AsyncSession = Depends(get_db),
    date_from: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict:
    """Получить информацию о событиях из БД"""

    repo = EventRepository(db)

    total, events = await repo.get_paginated_events(date_from, page, page_size)

    if not events:
        raise HTTPException(status_code=404, detail="Events not found")
    # return [EventSchema.model_validate(event) for event in events]
    return {
        "count": total,
        "results": [EventSchema.model_validate(event) for event in events],
        "next": f"/api/events?page={page + 1}" if total > page * page_size else None,
        "previous": f"/api/events?page={page - 1}" if page > 1 else None,
    }


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
        seats=seats,
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

    repo = EventRepository(db)

    # event = await repo.get_by_id(event_id=event_id)

    ticket_id = await client.register(
        event_id=event_id,
        first_name=registration.first_name,
        last_name=registration.last_name,
        email=registration.email,
        seat=registration.seat,
    )

    await repo.register(
        event_id=event_id,
        first_name=registration.first_name,
        last_name=registration.last_name,
        email=registration.email,
        seat=registration.seat,
        ticket_id=ticket_id,
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

    repo = EventRepository(db)

    event = await client.get_event_by_id(event_id=event_id)
    event_time = event.get("event_time")

    if datetime.now(timezone.utc) > datetime.fromisoformat(event_time):
        raise HTTPException(status_code=400, detail="Дата не может быть в прошлом")

    request = await client.unregister(
        event_id=event_id,
        ticket_id=unregistration.ticket_id,
    )

    await repo.unregister(
        event_id=event_id,
        ticket_id=unregistration.ticket_id,
    )
    return request


@app.post("/api/sync/trigger/")
async def sync_events(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    client: EventsProviderClient = Depends(get_events_client),
) -> dict:
    """
    Запуск ручной синхронизации.
    Используем BackgroundTasks, чтобы не заставлять пользователя ждать
    завершения долгого процесса по HTTP.
    """

    repo = EventRepository(db)
    service = SyncService(client, repo)
    await service.perform_sync()
    # background_tasks.add_task(service.perform_sync)

    return {
        "status": "sync_started",
        "message": "Процесс синхронизации запущен в фоновом режиме",
    }


@app.get("/api/health")
async def get_health():
    """Проверка работоспособности сервиса"""
    return {"status": "ok"}
