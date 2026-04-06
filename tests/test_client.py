from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from dotenv import load_dotenv

from src.infrastructure.client import EventsProviderClient

load_dotenv()
BASE_URL = os.getenv("BASE_URL", "https://events-provider.dev-2.python-labs.ru")
API_KEY = os.getenv("API_KEY")


@pytest.fixture
def api_client():
    """Фикстура для инициализации клиента с тестовыми данными."""
    return EventsProviderClient(base_url=BASE_URL, api_key=API_KEY)


@pytest.mark.asyncio
async def test_get_events_success(api_client, mocker):
    """Тест успешного получения списка событий."""
    # Имитируем ответ от сервера
    mock_response = {
        "next": f"{BASE_URL}/api/events/?cursor=next_token",
        "results": [{"id": "evt_1", "name": "Test Event", "status": "published"}],
    }

    # Мокаем метод get у httpx.AsyncClient
    # Обратите внимание: мы мокаем внутри атрибута .client нашего класса
    mock_get = mocker.patch.object(api_client.client, "get", new_callable=AsyncMock)
    mock_get.return_value = MagicMock(status_code=200, json=lambda: mock_response)

    # Вызываем тестируемый метод
    result = await api_client.get_events(changed_at="2000-01-01", cursor=None)

    # Проверки
    assert result["results"][0]["id"] == "evt_1"
    assert (
        "cursor" not in mock_get.call_args.params
    )  # Если курсор None, его не должно быть в запросе
    mock_get.assert_called_once()


@pytest.mark.asyncio
async def test_get_events_with_cursor(api_client, mocker):
    """Тест того, что курсор правильно передается в параметры запроса."""
    mock_get = mocker.patch.object(api_client.client, "get", new_callable=AsyncMock)
    mock_get.return_value = MagicMock(status_code=200, json=lambda: {"results": []})

    await api_client.get_events(changed_at="2000-01-01", cursor="token_123")

    # Проверяем, что в вызове httpx были правильные params
    args, kwargs = mock_get.call_args
    assert kwargs["params"]["cursor"] == "token_123"
    assert kwargs["params"]["changed_at"] == "2000-01-01"


@pytest.mark.asyncio
async def test_get_seats_caching_logic(api_client, mocker):
    """
    Тест получения мест.
    Если вы решите тестировать BookingService (где кэш),
    то проверьте, что клиент вызывается только один раз.
    """
    mock_get = mocker.patch.object(api_client.client, "get", new_callable=AsyncMock)
    mock_get.return_value = MagicMock(
        status_code=200, json=lambda: [{"id": "seat_1", "is_available": True}]
    )

    result = await api_client.get_seats(event_id="evt_1")

    assert len(result) == 1
    assert "/evt_1/seats" in mock_get.call_args[0][0]


@pytest.mark.asyncio
async def test_client_error_handling(api_client, mocker):
    """Тест поведения клиента при ошибке сервера (например, 500)."""
    mock_get = mocker.patch.object(api_client.client, "get", new_callable=AsyncMock)

    # Имитируем ошибку httpx
    mock_get.side_effect = httpx.HTTPStatusError(
        "Server Error", request=MagicMock(), response=MagicMock(status_code=500)
    )

    with pytest.raises(httpx.HTTPStatusError):
        await api_client.get_events(changed_at="2000-01-01")
