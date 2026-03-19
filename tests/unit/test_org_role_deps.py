import uuid
import pytest
from unittest.mock import MagicMock
from fastapi import HTTPException
from app.orgs.deps import require_org_role
from app.core.roles import OrgRole
from app.models.org_membership import OrgMembership


def _mock_membership(role=OrgRole.EMPLOYEE):
    mock = MagicMock(spec=OrgMembership)
    mock.org_role = role
    mock.org_id = uuid.uuid4()
    return mock


async def test_owner_passes():
    checker = require_org_role(OrgRole.OWNER, OrgRole.ADMIN)
    result = await checker(membership=_mock_membership(OrgRole.OWNER))
    assert result.org_role == OrgRole.OWNER


async def test_admin_passes():
    checker = require_org_role(OrgRole.OWNER, OrgRole.ADMIN)
    result = await checker(membership=_mock_membership(OrgRole.ADMIN))
    assert result.org_role == OrgRole.ADMIN


async def test_employee_fails():
    checker = require_org_role(OrgRole.OWNER, OrgRole.ADMIN)
    with pytest.raises(HTTPException) as exc_info:
        await checker(membership=_mock_membership(OrgRole.EMPLOYEE))
    assert exc_info.value.status_code == 403


async def test_viewer_fails():
    checker = require_org_role(OrgRole.OWNER, OrgRole.ADMIN)
    with pytest.raises(HTTPException) as exc_info:
        await checker(membership=_mock_membership(OrgRole.VIEWER))
    assert exc_info.value.status_code == 403
