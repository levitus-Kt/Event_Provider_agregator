"""Схемы валидации данных для операций с кошельком"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr


class PlaceSchema(BaseModel):
    id: UUID
    name: str
    city: str
    address: str
    seats_pattern: Optional[str] = None
    changed_at: datetime
    created_at: datetime

    class Config:
        from_attributes = True


class EventSchema(BaseModel):
    id: UUID
    name: str
    place: PlaceSchema
    event_time: datetime
    registration_deadline: datetime
    status: str
    number_of_visitors: int
    changed_at: datetime
    created_at: datetime
    status_changed_at: datetime

    class Config:
        from_attributes = True


class EventListResponse(BaseModel):
    next: Optional[str]
    previous: Optional[str]
    results: List[EventSchema]


class RegistrationRequest(BaseModel):
    event_id: UUID
    first_name: str
    last_name: str
    email: EmailStr
    seat: str
