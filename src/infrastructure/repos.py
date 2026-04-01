from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import and_, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models import EventModel, PlaceModel


class EventRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert(self, event_data: dict):
        # Логика Upsert для площадки
        def ensure_datetime(value):
            # Если это уже datetime, возвращаем как есть
            if isinstance(value, datetime):
                return value
            # Если это строка, преобразуем
            if isinstance(value, str):
                return datetime.fromisoformat(value)
            return value

        # Применение в репозитории или перед upsert:
        event_data["place"]["changed_at"] = ensure_datetime(
            event_data["place"].get("changed_at")
        )
        event_data["place"]["created_at"] = ensure_datetime(
            event_data["place"].get("created_at")
        )
        event_data["event_time"] = ensure_datetime(event_data.get("event_time"))
        event_data["registration_deadline"] = ensure_datetime(
            event_data.get("registration_deadline")
        )
        event_data["changed_at"] = ensure_datetime(event_data.get("changed_at"))
        event_data["created_at"] = ensure_datetime(event_data.get("created_at"))
        event_data["status_changed_at"] = ensure_datetime(
            event_data.get("status_changed_at")
        )

        place_stmt = (
            insert(PlaceModel)
            .values(**event_data["place"])
            .on_conflict_do_update(index_elements=["id"], set_=event_data["place"])
        )
        await self.session.execute(place_stmt)

        # Логика Upsert для события
        evt_copy = event_data.copy()
        evt_copy["place_id"] = evt_copy.pop("place")["id"]
        # Удаляем поля, которых нет в нашей БД, но есть в API
        # for extra in ["changed_at", "created_at", "status_changed_at"]:
        #     evt_copy.pop(extra, None)

        event_stmt = (
            insert(EventModel)
            .values(**evt_copy)
            .on_conflict_do_update(index_elements=["id"], set_=evt_copy)
        )
        await self.session.execute(event_stmt)
        await self.session.flush()
        # await self.session.commit()

    async def get_paginated_events(self, date_from=None, page=1, size=20):
        query = select(EventModel)
        if date_from:
            query = query.where(EventModel.event_time >= date_from)

        # Общее количество
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.session.execute(count_query)).scalar() or 0

        # Пагинация
        results = await self.session.execute(
            query.offset((page - 1) * size).limit(size)
        )
        return total, results.scalars().all()

    async def update(self, event_data: dict) -> None:
        # Создаем объект модели из словаря (преобразовав данные)
        event = EventModel(**event_data)

        # merge ищет запись по ID:
        # если находит — обновляет поля, если нет — создает новую.
        await self.session.merge(event)
        await self.session.commit()
        await self.session.refresh(event)

    async def get_by_id(self, event_id: UUID) -> EventModel | None:
        result = await self.session.execute(
            select(EventModel).where(EventModel.id == event_id)
        )
        return result.scalars().first()

    async def get_seat_list(self, event_id: UUID) -> list:
        event = await self.get_by_id(event_id)
        if not event:
            return []

        now = datetime.now(timezone.utc)
        result = await self.session.execute(
            select(PlaceModel.seats_pattern)
            .join(EventModel, EventModel.place_id == PlaceModel.id)
            .where(
                and_(
                    EventModel.id == event_id,
                    EventModel.status == "published",
                    EventModel.event_time > now,
                )
            )
        )
        return result.scalar_one_or_none()


class CreateTicketRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def execute(
        self, event_id: str, first_name: str, last_name: str, email: str, seat: str
    ) -> str:
        # Валидация в нашей БД
        event = await EventRepository(self.session).get_by_id(event_id)
        if not event:
            raise HTTPException(404, detail="Event does not exist")

        # Статус
        if event.status != "published":
            raise HTTPException(500, detail="Event is not published for registration")

        # Делаем запрос (он же проверит seats_pattern)
        ticket_id = await self.client.register(
            event_id=event_id,
            first_name=first_name,
            last_name=last_name,
            email=email,
            seat=seat,
        )

        # Сохраняем в нашей БД
        user_data = {
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "seat": seat,
        }
        await self.tickets.create(event_id, ticket_id, user_data)

        return ticket_id
