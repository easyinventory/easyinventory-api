from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr


class OrgResponse(BaseModel):
    id: uuid.UUID
    name: str
    created_at: datetime

    model_config = {"from_attributes": True}


class OrgMembershipResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    org_role: str
    is_active: bool
    joined_at: datetime
    organization: OrgResponse

    model_config = {"from_attributes": True}


class OrgMemberDetail(BaseModel):
    """Member list item — includes user info alongside membership."""

    id: uuid.UUID
    user_id: uuid.UUID
    email: str
    org_role: str
    is_active: bool
    joined_at: datetime

    model_config = {"from_attributes": True}


class InviteMemberRequest(BaseModel):
    email: EmailStr
    org_role: str = "ORG_EMPLOYEE"


class UpdateRoleRequest(BaseModel):
    org_role: str
