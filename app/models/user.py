from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, query_expression, relationship

from app.core.roles import SystemRole
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
        String, nullable=False, default=SystemRole.USER
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Relationships (loaded when needed)
    memberships: Mapped[list[OrgMembership]] = relationship(
        back_populates="user", lazy="selectin"
    )

    # Computed via with_expression() in queries that need it (e.g. admin list)
    active_org_count: Mapped[Optional[int]] = query_expression()
