from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    system_role: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
