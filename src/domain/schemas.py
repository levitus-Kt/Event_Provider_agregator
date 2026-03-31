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
    results: List[EventSchema]


class EventResponse(BaseModel):
    event: EventSchema

    # @field_validator("created_at")
    # @classmethod
    # def check_future_date(cls, future: datetime) -> datetime:
    #     # Приводим всё к UTC для честного сравнения
    #     now = datetime.now(future.tzinfo) if future.tzinfo else datetime.now()
    #     if future < now:
    #         raise ValueError("Дата не может быть в прошлом")
    #     return future


class RegistrationRequest(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    seat: str


class RegistrationResponse(BaseModel):
    ticket_id: UUID


class SeatListResponse(BaseModel):
    seats: List[str]
