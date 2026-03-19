import uuid
from unittest.mock import AsyncMock, MagicMock


async def test_list_all_orgs_query_executes():
    """list_all_orgs should execute a query and return Organization models."""
    from app.admin.service import list_all_orgs

    mock_org = MagicMock()
    mock_org.id = uuid.uuid4()
    mock_org.name = "Test Org"
    mock_org.created_at = "2026-03-13T00:00:00+00:00"

    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [mock_org]

    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars

    mock_db = AsyncMock()
    mock_db.execute.return_value = mock_result

    result = await list_all_orgs(mock_db)

    assert mock_db.execute.await_count == 1
    assert len(result) == 1
    assert result[0].name == "Test Org"
