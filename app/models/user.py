from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


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
    memberships: Mapped[list["OrgMembership"]] = relationship(
        back_populates="user", lazy="selectin"
    )
