import uuid
from datetime import datetime

from sqlalchemy import (
    String, Boolean, ForeignKey, DateTime, Text, Integer, JSON,
    UniqueConstraint, Index, func
)
# Portable UUID handling: PostgreSQL in prod, string PK works identically on SQLite for tests
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.enums import (
    UserRole, UserStatus, BranchStatus, LockerSize, LockerStatus,
    RequestType, RequestStatus, TokenType, TokenStatus, NotificationType,
)

# ---------------------------------------------------------------------------
# FaceVerification — imported here so Alembic env.py picks it up on metadata
# ---------------------------------------------------------------------------


def gen_uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    phone: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(30), nullable=False, default=UserRole.CUSTOMER.value)
    branch_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("branches.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=UserStatus.ACTIVE.value)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    branch: Mapped["Branch | None"] = relationship(back_populates="staff", foreign_keys=[branch_id])
    locker: Mapped["Locker | None"] = relationship(back_populates="customer", uselist=False, foreign_keys="Locker.customer_id")

    __table_args__ = (Index("ix_users_role", "role"),)


class Branch(Base):
    __tablename__ = "branches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    branch_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    address: Mapped[str] = mapped_column(String(255), nullable=False)
    city: Mapped[str] = mapped_column(String(80), nullable=False)
    state: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=BranchStatus.ACTIVE.value)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    staff: Mapped[list["User"]] = relationship(back_populates="branch", foreign_keys="User.branch_id")
    lockers: Mapped[list["Locker"]] = relationship(back_populates="branch")


class Locker(Base):
    __tablename__ = "lockers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    branch_id: Mapped[str] = mapped_column(String(36), ForeignKey("branches.id"), nullable=False)
    locker_number: Mapped[str] = mapped_column(String(20), nullable=False)
    locker_size: Mapped[str] = mapped_column(String(20), nullable=False, default=LockerSize.MEDIUM.value)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default=LockerStatus.AVAILABLE.value)
    customer_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    last_operation_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    branch: Mapped["Branch"] = relationship(back_populates="lockers")
    customer: Mapped["User | None"] = relationship(back_populates="locker", foreign_keys=[customer_id])
    requests: Mapped[list["LockerRequest"]] = relationship(back_populates="locker")

    __table_args__ = (
        UniqueConstraint("branch_id", "locker_number", name="uq_branch_locker_number"),
        Index("ix_lockers_status", "status"),
    )


class LockerRequest(Base):
    __tablename__ = "locker_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    locker_id: Mapped[str] = mapped_column(String(36), ForeignKey("lockers.id"), nullable=False)
    customer_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    request_type: Mapped[str] = mapped_column(String(20), nullable=False, default=RequestType.ACCESS.value)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default=RequestStatus.SUBMITTED.value)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    correlation_id: Mapped[str] = mapped_column(String(36), default=gen_uuid, index=True)

    locker: Mapped["Locker"] = relationship(back_populates="requests")
    customer: Mapped["User"] = relationship(foreign_keys=[customer_id])
    approver: Mapped["User | None"] = relationship(foreign_keys=[approved_by])
    tokens: Mapped[list["VerificationToken"]] = relationship(back_populates="request")

    @property
    def locker_number(self) -> str | None:
        return self.locker.locker_number if self.locker else None

    @property
    def customer_name(self) -> str | None:
        return self.customer.full_name if self.customer else None

    __table_args__ = (
        Index("ix_requests_status", "status"),
        Index("ix_requests_requested_at", "requested_at"),
    )



class VerificationToken(Base):
    __tablename__ = "verification_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    request_id: Mapped[str] = mapped_column(String(36), ForeignKey("locker_requests.id"), nullable=False)
    token_type: Mapped[str] = mapped_column(String(20), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=TokenStatus.PENDING.value)

    request: Mapped["LockerRequest"] = relationship(back_populates="tokens")


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    actor_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    actor_role: Mapped[str | None] = mapped_column(String(30), nullable=True)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    previous_state: Mapped[str | None] = mapped_column(String(40), nullable=True)
    new_state: Mapped[str | None] = mapped_column(String(40), nullable=True)
    event_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_audit_created_at", "created_at"),
        Index("ix_audit_actor", "actor_id"),
        Index("ix_audit_entity", "entity_type", "entity_id"),
    )


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(150), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(String(30), nullable=False, default=NotificationType.SYSTEM.value)
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("ix_notifications_user", "user_id"),)


class FaceVerification(Base):
    """
    Stores derived signals from one face-capture attempt by a staff member.

    IMPORTANT — DATA HANDLING:
    - raw_response holds the AI module's structured output dict, NOT image bytes.
    - Image bytes are never persisted anywhere in this system.
    - TODO (follow-up): evaluate encryption-at-rest for this table before
      production deployment. Biometric-derived data may require it under
      applicable banking / data-protection regulations.
    - TODO (follow-up): establish a retention policy and purge schedule for
      rows in this table. Confirm regulatory requirements with compliance.
    """
    __tablename__ = "face_verifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    request_id: Mapped[str] = mapped_column(String(36), ForeignKey("locker_requests.id"), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    actor_role: Mapped[str] = mapped_column(String(30), nullable=False)
    face_match: Mapped[bool] = mapped_column(Boolean, nullable=False)
    confidence: Mapped[float] = mapped_column(nullable=False)
    liveness_passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    spoof_probability: Mapped[float] = mapped_column(nullable=False)
    # Structured AI output — not the raw image.  Not logged at INFO level or above.
    raw_response: Mapped[dict] = mapped_column(JSON, nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    request: Mapped["LockerRequest"] = relationship(foreign_keys=[request_id])
    actor: Mapped["User"] = relationship(foreign_keys=[actor_id])

    __table_args__ = (
        Index("ix_face_verifications_request_id", "request_id"),
        Index("ix_face_verifications_actor_id", "actor_id"),
    )
