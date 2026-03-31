"""Главное приложение FastAPI"""

import os
from datetime import datetime, timezone
from uuid import UUID

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

# from src.app.worker.sync import run_sync_job
from src.domain.schemas import (
    EventListResponse,
    EventResponse,
    EventSchema,
    RegistrationRequest,
    RegistrationResponse,
    SeatListResponse,
    UnregistrationRequest,
)
from src.infrastructure.client import EventsProviderClient
from src.infrastructure.database import get_db
from src.infrastructure.paginator import EventsPaginator

load_dotenv()


app = FastAPI()

BASE_URL = os.getenv("BASE_URL")
API_KEY = os.getenv("API_KEY")


def get_events_client() -> EventsProviderClient:
    return EventsProviderClient(base_url=BASE_URL, api_key=API_KEY)


@app.get(
    "/api/events/",
    response_model=EventListResponse,
)
async def get_event_list(
    changed_at: str = Query(..., description="Дата для фильтрации событий"),
    # date_from: Optional[str] = Query(
    #     datetime.now().astimezone(UTC), description="События после указанной даты"
    # ),
    # page: Optional[int] = Query(1, description="Номер страницы для пагинации"),
    db: AsyncSession = Depends(get_db),
    client: EventsProviderClient = Depends(get_events_client),
) -> EventListResponse:
    """Получить информацию о событиях"""

    paginator = EventsPaginator(client, changed_at)
    events = []
    async for event in paginator:
        events.append(event)
    if not events:
        raise HTTPException(status_code=404, detail="Events not found")
    return EventListResponse(
        results=[EventSchema.model_validate(event) for event in events],
    )


@app.get("/api/events/{event_id}", response_model=EventResponse)
async def get_event_by_id(
    event_id: UUID,
    db: AsyncSession = Depends(get_db),
    client: EventsProviderClient = Depends(get_events_client),
) -> EventResponse:
    """Получить информацию о событии по ID"""

    event = await client.get_event_by_id(event_id=event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return EventResponse.model_validate(event)


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

    event = await client.get_event_by_id(event_id=event_id)

    event_time = event.get("event_time")
    if "published" not in event.get("status", ""):
        raise HTTPException(status_code=400, detail="Event is not published")
    if datetime.now(timezone.utc) > datetime.fromisoformat(event_time):
        raise HTTPException(status_code=400, detail="Дата не может быть в прошлом")

    data = await client.get_seats(event_id=event_id)
    if not data:
        raise HTTPException(status_code=404, detail="Seats not found")
    return SeatListResponse(
        seats=[seat for seat in data.get("seats", [])],
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
        raise HTTPException(status_code=400, detail="Дата не может быть в прошлом")
    if datetime.now(timezone.utc) > datetime.fromisoformat(registration_deadline):
        raise HTTPException(status_code=400, detail="Регистрация закрыта")

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


@app.get("/api/health")
async def get_health():
    """Проверка работоспособности сервиса"""
    return {"status": "ok"}
