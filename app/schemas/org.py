from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


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
