from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.org_membership import OrgMembership


class Organization(BaseModel):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String, nullable=False)

    # Relationships
    memberships: Mapped[list[OrgMembership]] = relationship(
        back_populates="organization", lazy="selectin"
    )
