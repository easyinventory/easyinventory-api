from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr

# ── Org schemas ──


class CreateOrgRequest(BaseModel):
    name: str
    owner_email: EmailStr


class UpdateOrgRequest(BaseModel):
    name: str


class TransferOwnershipRequest(BaseModel):
    new_owner_email: EmailStr


class OrgListItem(BaseModel):
    id: uuid.UUID
    name: str
    created_at: datetime
    owner_email: str | None
    member_count: int

    model_config = {"from_attributes": True}


# ── User schemas (admin) ──


class UserListItem(BaseModel):
    id: uuid.UUID
    email: str
    system_role: str
    is_active: bool
    created_at: datetime
    org_count: int = 0

    model_config = {"from_attributes": True}
