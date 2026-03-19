from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, query_expression, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.org_membership import OrgMembership


class Organization(BaseModel):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String, nullable=False)

    # Computed via with_expression — populated by service queries that use SQL aggregates.
    # Defaults to None / 0 when not loaded via with_expression.
    owner_email: Mapped[Optional[str]] = query_expression()
    member_count: Mapped[int] = query_expression(default_expr=0)

    # Relationships
    memberships: Mapped[list[OrgMembership]] = relationship(
        back_populates="organization", lazy="selectin"
    )
