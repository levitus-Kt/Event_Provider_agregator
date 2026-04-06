from src.infrastructure.client import EventsProviderClient
from src.infrastructure.paginator import EventsPaginator
from src.infrastructure.repos import EventRepository


class SyncService:
    def __init__(self, client: EventsProviderClient, repo: EventRepository):
        self.client = client
        self.repo = repo

    async def perform_sync(self, changed_at: str = "2026-03-30"):
        """
        Запускает процесс синхронизации.
        По умолчанию забирает всё (с 2000 года).
        """
        print(f"Starting sync from {changed_at}...")

        processed_ids = set()
        paginator = EventsPaginator(self.client, changed_at=changed_at)
        synced_count = 0
        # event_id = None
        # events = set(())
        async for event_data in paginator:
            e_id = event_data.get("id")
            print(f"DEBUG: Processing event {event_data['id']} - {event_data['name']}")
            # Сохраняем только опубликованные (published) ивенты
            if event_data.get("status") == "published":
                if e_id in processed_ids:
                    print(f"!!! КРИТИЧЕСКАЯ ОШИБКА: ID {e_id} ПРИШЕЛ ПОВТОРНО !!!")
                    # Вместо return или break — кидаем исключение, чтобы увидеть traceback
                    raise RuntimeError(
                        f"Loop detected for event ID: {e_id}. Cursor was: {paginator._next_cursor}"
                    )

                processed_ids.add(e_id)
                print(f"Обработка: {e_id}")

                await self.repo.upsert(event_data)
                # events.add(event_data)
                synced_count += 1
                print(synced_count, event_data)
            # await self.repo.upsert(event_data)
        # Сохраняем метаданные синхронизации (опционально)
        # await self.repo.update_sync_metadata(
        #     last_sync_time=datetime.now(),
        #     last_changed_at=changed_at, status="success"
        # )

        print(f"Sync finished. Processed {synced_count} published events.")
        return synced_count
