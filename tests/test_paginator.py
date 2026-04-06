import pytest
from unittest.mock import AsyncMock
from src.infrastructure.external_api.paginator import EventsPaginator

@pytest.mark.asyncio
async def test_paginator_iteration():
    mock_client = AsyncMock()
    # Имитируем ответ API с одной страницей
    mock_client.get_events.return_value = {
        "next": None,
        "results": [{"id": "1", "name": "Event 1"}]
    }
    
    paginator = EventsPaginator(mock_client, changed_at="2000-01-01")
    events = []
    async for event in paginator:
        events.append(event)
        
    assert len(events) == 1
    assert events[0]["name"] == "Event 1"
    mock_client.get_events.assert_called_once()