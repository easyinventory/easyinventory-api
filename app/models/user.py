from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.org_membership import OrgMembership


class User(BaseModel):
    __tablename__ = "users"

    cognito_sub: Mapped[str] = mapped_column(
        String, unique=True, nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String, nullable=False)
    system_role: Mapped[str] = mapped_column(
        String, nullable=False, default="SYSTEM_USER"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Relationships (loaded when needed)
    memberships: Mapped[list[OrgMembership]] = relationship(
        back_populates="user", lazy="selectin"
    )
