from typing import Any, AsyncIterator, Dict
from urllib.parse import parse_qs, urlparse

from src.infrastructure.client import EventsProviderClient


class EventsPaginator:
    def __init__(
        self,
        client: EventsProviderClient,
        changed_at: str = "2000-01-01",
    ):
        self.client = client
        self.changed_at = changed_at
        self._next_cursor: str | None = None
        self._is_first_request = True
        self._buffer = []
        self._seen_cursors = set()

    def __aiter__(self) -> AsyncIterator[Dict[str, Any]]:
        return self

    async def __anext__(self) -> Dict[str, Any]:
        if not self._buffer:
            if not self._is_first_request and not self._next_cursor:
                raise StopAsyncIteration
            print("1")
            print(
                f"--- FETCHING DATA | Cursor: {self._next_cursor} | ChangedAt: {self.changed_at} ---"
            )
            data = await self.client.get_events(
                changed_at=self.changed_at, cursor=self._next_cursor
            )
            print("2")
            self._is_first_request = False
            self._buffer = data.get("results", [])
            print("3")
            # Извлекаем cursor из URL 'next'
            next_url = data.get("next")
            print(f"RAW NEXT URL FROM SERVER: {next_url}")
            if next_url:
                parsed_url = urlparse(next_url)
                new_cursor = parse_qs(parsed_url.query).get("cursor", [None])[0]
                print("4")
                #  ЗАЩИТА ОТ ЗАЦИКЛИВАНИЯ:
                # Если новый курсор такой же, как старый — прерываемся
                if new_cursor == self._next_cursor:
                    print(f"API returned circular pagination at cursor: {new_cursor}")
                    self._next_cursor = None
                elif new_cursor in self._seen_cursors:
                    print(f"Already seen cursor: {new_cursor}, stopping iteration.")
                    self._next_cursor = None
                else:
                    self._next_cursor = new_cursor
                    if new_cursor:
                        self._seen_cursors.add(new_cursor)
            else:
                self._next_cursor = None
            if not self._buffer:
                raise StopAsyncIteration

        return self._buffer.pop(0)
