import uuid
from unittest.mock import AsyncMock, MagicMock


async def test_list_all_orgs_query_executes():
    """list_all_orgs should execute a query and return results."""
    from app.admin.service import list_all_orgs

    mock_row = MagicMock()
    mock_row.id = uuid.uuid4()
    mock_row.name = "Test Org"
    mock_row.created_at = "2026-03-13T00:00:00+00:00"
    mock_row.owner_email = "owner@test.com"
    mock_row.member_count = 3

    mock_result = MagicMock()
    mock_result.all.return_value = [mock_row]

    mock_db = AsyncMock()
    mock_db.execute.return_value = mock_result

    result = await list_all_orgs(mock_db)

    assert len(result) == 1
    assert result[0]["name"] == "Test Org"
    assert result[0]["owner_email"] == "owner@test.com"
    assert result[0]["member_count"] == 3
