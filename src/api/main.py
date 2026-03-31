"""Главное приложение FastAPI"""

import os

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

# from src.app.worker.sync import run_sync_job
from src.domain.schemas import EventListResponse, EventSchema
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
        next=None,
        previous=None,
        results=[EventSchema.model_validate(event) for event in events],
    )


@app.get("/api/health")
async def get_health():
    """Проверка работоспособности сервиса"""
    return {"status": "ok"}
