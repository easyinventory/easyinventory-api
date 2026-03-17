import uuid
import pytest
from unittest.mock import MagicMock
from fastapi import HTTPException
from app.api.deps import require_org_role
from app.models.org_membership import OrgMembership


def _mock_membership(role="ORG_EMPLOYEE"):
    mock = MagicMock(spec=OrgMembership)
    mock.org_role = role
    mock.org_id = uuid.uuid4()
    return mock


async def test_owner_passes():
    checker = require_org_role("ORG_OWNER", "ORG_ADMIN")
    result = await checker(membership=_mock_membership("ORG_OWNER"))
    assert result.org_role == "ORG_OWNER"


async def test_admin_passes():
    checker = require_org_role("ORG_OWNER", "ORG_ADMIN")
    result = await checker(membership=_mock_membership("ORG_ADMIN"))
    assert result.org_role == "ORG_ADMIN"


async def test_employee_fails():
    checker = require_org_role("ORG_OWNER", "ORG_ADMIN")
    with pytest.raises(HTTPException) as exc_info:
        await checker(membership=_mock_membership("ORG_EMPLOYEE"))
    assert exc_info.value.status_code == 403


async def test_viewer_fails():
    checker = require_org_role("ORG_OWNER", "ORG_ADMIN")
    with pytest.raises(HTTPException) as exc_info:
        await checker(membership=_mock_membership("ORG_VIEWER"))
    assert exc_info.value.status_code == 403
