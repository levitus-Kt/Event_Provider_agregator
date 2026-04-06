from uuid import UUID

import httpx

from src.domain.interfaces import EventsProviderProtocol


class EventsProviderClient(EventsProviderProtocol):
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.headers = {"x-api-key": api_key, "Content-Type": "application/json"}

    async def get_events(
        self,
        changed_at: str,
        cursor: str = None,
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
                follow_redirects=True,
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
        print(f"DEBUG: Registering for event {event_id} at seat '{seat}'")
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/events/{event_id}/register/",
                json=payload,
                headers=self.headers,
            )
            print(response.json())
            # try:
            #     response.raise_for_status()
            # except httpx.HTTPStatusError as e:
            #     if "404" in str(e):
            #         raise HTTPException(404, detail=str(e).split("\n")[0])
            return response.json()["ticket_id"]

    async def unregister(self, event_id: UUID, ticket_id: str) -> dict:
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
