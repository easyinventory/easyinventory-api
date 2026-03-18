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
