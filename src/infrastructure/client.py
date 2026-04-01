from uuid import UUID

import httpx


class EventsProviderClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.headers = {"x-api-key": api_key, "Content-Type": "application/json"}

    async def get_events(
        self,
        changed_at: str,
        cursor: str | None = None,
    ) -> dict:
        """Получить события"""

        params = {"changed_at": changed_at}

        if cursor:
            params["cursor"] = cursor

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/events/",
                params=params,
                headers=self.headers,
                timeout=25,
            )
            response.raise_for_status()
            return response.json()

    async def get_event_by_id(
        self,
        event_id: UUID,
    ) -> dict:
        """Получить информацию о событии по ID"""

        async with httpx.AsyncClient() as client:
            event = await client.get(
                f"{self.base_url}/api/events/{event_id}/", headers=self.headers
            )
            if not event:
                raise Exception(404, "Event not found")
            return event.json()

    async def get_seats(
        self,
        event_id: UUID,
    ) -> dict:
        """Получить информацию о местах для события по ID"""

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/events/{event_id}/seats/",
                headers=self.headers,
            )
            response.raise_for_status()
            return response.json()

    async def register(
        self, event_id: UUID, first_name: str, last_name: str, email: str, seat: str
    ) -> str:
        """Зарегистрировать пользователя на событие"""

        payload = {
            "first_name": first_name,
            "last_name": last_name,
            "seat": seat,
            "email": email,
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/events/{event_id}/register/",
                json=payload,
                headers=self.headers,
            )
            response.raise_for_status()
            return response.json()["ticket_id"]

    async def unregister(self, event_id: UUID, ticket_id: UUID) -> dict:
        """Отменить регистрацию пользователя на событие"""

        async with httpx.AsyncClient() as client:
            response = await client.request(
                method="DELETE",
                url=f"{self.base_url}/api/events/{event_id}/unregister/",
                json={"ticket_id": str(ticket_id)},
                headers=self.headers,
            )
            response.raise_for_status()
            return {"success": True}

    async def events(self, changed_at: str, cursor: str | None = None) -> dict:
        raise NotImplementedError
