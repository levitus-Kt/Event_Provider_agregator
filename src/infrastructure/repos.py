from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import and_, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.domain.models import EventModel, PlaceModel, RegistrationModel


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
                return datetime.fromisoformat(value.replace("Z", "+03:00"))
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

        place_data = event_data["place"]
        place_stmt = (
            insert(PlaceModel)
            .values(
                # **event_data["place"]
                id=place_data["id"],
                name=place_data["name"],
                city=place_data["city"],
                address=place_data["address"],
                seats_pattern=place_data["seats_pattern"],
                changed_at=place_data["changed_at"],
                created_at=place_data["created_at"],
            )
            .on_conflict_do_update(
                index_elements=["id"],
                # event_data["place"],
                set_={
                    "name": place_data["name"],
                    "city": place_data["city"],
                    "address": place_data["address"],
                    "seats_pattern": place_data["seats_pattern"],
                    "changed_at": place_data["changed_at"],
                    "created_at": place_data["created_at"],
                },
            )
        )
        await self.session.execute(place_stmt)

        # Логика Upsert для события

        event_stmt = (
            insert(EventModel)
            .values(
                # **event_data
                id=event_data["id"],
                name=event_data["name"],
                event_time=event_data["event_time"],
                registration_deadline=event_data["registration_deadline"],
                status=event_data["status"],
                number_of_visitors=event_data["number_of_visitors"],
                place_id=place_data["id"],
            )
            .on_conflict_do_update(
                index_elements=["id"],
                # event_data,
                set_={
                    "name": event_data["name"],
                    "event_time": event_data["event_time"],
                    "status": event_data["status"],
                    "number_of_visitors": event_data["number_of_visitors"],
                    "registration_deadline": event_data["registration_deadline"],
                    "changed_at": event_data["changed_at"],
                    "created_at": event_data["created_at"],
                    "status_changed_at": event_data["status_changed_at"],
                },
            )
        )
        await self.session.execute(event_stmt)
        # await self.session.flush()
        await self.session.commit()

    async def get_paginated_events(self, date_from=None, page=1, size=20):
        query = select(EventModel).options(joinedload(EventModel.place))
        if date_from:
            query = query.where(EventModel.event_time >= date_from)

        # Общее количество
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.session.execute(count_query)).scalar() or 0

        # Пагинация
        results = await self.session.execute(
            query.offset((page - 1) * size).limit(size)
        )
        return total, list(results.scalars().all())

    # async def update(self, event_data: dict) -> None:
    #     # Создаем объект модели из словаря (преобразовав данные)
    #     event = EventModel(**event_data)

    #     # merge ищет запись по ID:
    #     # если находит — обновляет поля, если нет — создает новую.
    #     await self.session.merge(event)
    #     await self.session.commit()
    #     await self.session.refresh(event)

    async def get_by_id(self, event_id: UUID) -> EventModel | None:
        result = await self.session.execute(
            select(EventModel)
            .options(joinedload(EventModel.place))
            .where(EventModel.id == event_id)
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
        seats = result.scalars().all()[0].split(",") if result else []
        return seats

    async def register(
        self,
        event_id: UUID,
        first_name: str,
        last_name: str,
        email: str,
        seat: str,
        ticket_id: str,
    ):
        # Логика регистрации билета в БД (например, сохранение информации о регистрации)

        query = (
            insert(RegistrationModel)
            .values(
                event_id=event_id,
                first_name=first_name,
                last_name=last_name,
                email=email,
                seat=seat,
                ticket_id=ticket_id,
            )
            .on_conflict_do_update(
                index_elements=["id"],
                set_={
                    "first_name": first_name,
                    "last_name": last_name,
                    "email": email,
                    "seat": seat,
                    "ticket_id": ticket_id,
                },
            )
        )
        await self.session.execute(query)

    async def get_registration_by_ticket_id(
        self, ticket_id: str
    ) -> RegistrationModel | None:
        result = await self.session.execute(
            select(RegistrationModel).where(RegistrationModel.ticket_id == ticket_id)
        )
        return result.scalars().first()

    async def unregister(self, event_id: UUID, ticket_id: str):
        query = select(RegistrationModel).where(
            and_(
                RegistrationModel.event_id == event_id,
                RegistrationModel.ticket_id == ticket_id,
            )
        )
        registration = (await self.session.execute(query)).scalars().first()
        if registration:
            await self.session.delete(registration)
            await self.session.commit()


class CreateTicketRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def execute(
        self, event_id: UUID, first_name: str, last_name: str, email: str, seat: str
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
