from typing import Any, AsyncIterator, Dict
from urllib.parse import parse_qs, urlparse

from src.infrastructure.client import EventsProviderClient


class EventsPaginator:
    def __init__(self, client: EventsProviderClient, changed_at: str):
        self.client = client
        self.changed_at = changed_at
        self._next_cursor: str | None = None
        self._is_first_request = True
        self._buffer = []

    def __aiter__(self) -> AsyncIterator[Dict[str, Any]]:
        return self

    async def __anext__(self) -> Dict[str, Any]:
        if not self._buffer:
            if not self._is_first_request and not self._next_cursor:
                raise StopAsyncIteration

            data = await self.client.get_events(
                changed_at=self.changed_at, cursor=self._next_cursor
            )

            self._is_first_request = False
            self._buffer = data.get("results", [])

            # Извлекаем cursor из URL 'next'
            next_url = data.get("next")
            if next_url:
                parsed_url = urlparse(next_url)
                self._next_cursor = parse_qs(parsed_url.query).get("cursor", [None])[0]
            else:
                self._next_cursor = None
            print(f"Requesting cursor: {self._next_cursor}")
            if not self._buffer:
                raise StopAsyncIteration

        return self._buffer.pop(0)
