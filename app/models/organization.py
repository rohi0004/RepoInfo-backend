"""Organizations, teams, team membership, and invitations."""

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import AuditedBase
from app.database.types import JSONB, pg_enum
from app.models.enums import InvitationStatusEnum, OrgRoleEnum, UserPlanEnum


class Organization(AuditedBase):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    avatar_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    plan: Mapped[UserPlanEnum] = mapped_column(
        pg_enum(UserPlanEnum, "user_plan", create_type=False), nullable=False, default=UserPlanEnum.FREE
    )
    settings: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    teams: Mapped[list["Team"]] = relationship(back_populates="organization", cascade="all, delete-orphan")
    invitations: Mapped[list["Invitation"]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )


class Team(AuditedBase):
    __tablename__ = "teams"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    organization: Mapped["Organization"] = relationship(back_populates="teams")
    members: Mapped[list["TeamMember"]] = relationship(back_populates="team", cascade="all, delete-orphan")

    __table_args__ = (UniqueConstraint("organization_id", "slug", name="uq_teams_org_slug"),)


class TeamMember(AuditedBase):
    __tablename__ = "team_members"

    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[OrgRoleEnum] = mapped_column(
        pg_enum(OrgRoleEnum, "org_role"), nullable=False, default=OrgRoleEnum.MEMBER
    )

    team: Mapped["Team"] = relationship(back_populates="members")

    __table_args__ = (UniqueConstraint("team_id", "user_id", name="uq_team_members_pair"),)


class Invitation(AuditedBase):
    __tablename__ = "invitations"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    team_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id", ondelete="CASCADE"), nullable=True
    )
    invited_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    role: Mapped[OrgRoleEnum] = mapped_column(
        pg_enum(OrgRoleEnum, "org_role", create_type=False), nullable=False, default=OrgRoleEnum.MEMBER
    )
    status: Mapped[InvitationStatusEnum] = mapped_column(
        pg_enum(InvitationStatusEnum, "invitation_status"), nullable=False, default=InvitationStatusEnum.PENDING
    )
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(nullable=False)
    responded_at: Mapped[datetime | None] = mapped_column(nullable=True)

    organization: Mapped["Organization"] = relationship(back_populates="invitations")

    __table_args__ = (UniqueConstraint("organization_id", "email", name="uq_invitations_org_email"),)
