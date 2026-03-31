"""Главное приложение FastAPI"""

import os

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

# from src.app.worker.sync import run_sync_job
from src.domain.schemas import EventListResponse
from src.infrastructure.client import EventsProviderClient
from src.infrastructure.database import get_db

load_dotenv()


app = FastAPI()

# Настройки для клиента (лучше вынести в env)
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
    db: AsyncSession = Depends(get_db),
    client: EventsProviderClient = Depends(get_events_client),
) -> EventListResponse:
    """Получить информацию о событиях"""
    events = await client.get_events(changed_at=changed_at)
    if not events:
        raise HTTPException(status_code=404, detail="Events not found")
    return EventListResponse.model_validate(events)
