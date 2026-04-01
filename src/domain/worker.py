from cachetools import TTLCache

from src.infrastructure.client import EventsProviderClient


class BookingService:
    def __init__(self, client: EventsProviderClient):
        self.client = client
        self._seats_cache = TTLCache(maxsize=100, ttl=30)
        self.sync_events()

    async def sync_events(self):
        events = await self.client.get_events("2000-01-01T00:00:00+03:00")
        for event in events:
            self._seats_cache[event.id] = event.place.seats_pattern

    # async def get_available_seats(self, event_id: str):
    #     if event_id in self._seats_cache:
    #         return self._seats_cache[event_id]
    #
    #     seats = await self.client.get_seats(event_id)
    #     self._seats_cache[event_id] = seats
    #     return seats

    # async def register(self, data):
    #     # БЛ: Проверка статуса перед запросом (status == published)
    #     # БЛ: Проверка дедлайна
    #     return await self.client.register_on_event(data)
