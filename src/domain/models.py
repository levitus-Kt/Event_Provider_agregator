"""Модели в таблице"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class PlaceModel(Base):
    __tablename__ = "places"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    city: Mapped[str] = mapped_column(String)
    address: Mapped[str] = mapped_column(String)
    seats_pattern: Mapped[str] = mapped_column(String)

    events: Mapped[list["EventModel"]] = relationship(back_populates="place")


class EventModel(Base):
    __tablename__ = "events"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    registration_deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String)
    number_of_visitors: Mapped[int] = mapped_column(Integer, default=0)

    place_id: Mapped[str] = mapped_column(ForeignKey("places.id"))
    place: Mapped["PlaceModel"] = relationship(back_populates="events", lazy="joined")


class SyncMetadata(Base):
    __tablename__ = "sync_metadata"
    id: Mapped[int] = mapped_column(primary_key=True)
    last_sync_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_changed_at: Mapped[str] = mapped_column(String)  # Дата для API: YYYY-MM-DD
    sync_status: Mapped[str] = mapped_column(String)
