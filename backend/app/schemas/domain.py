from datetime import datetime
from pydantic import BaseModel, ConfigDict


class BranchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    branch_code: str
    name: str
    address: str
    city: str
    state: str
    status: str


class LockerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    branch_id: str
    locker_number: str
    locker_size: str
    status: str
    customer_id: str | None = None
    last_operation_at: datetime | None = None


class LockerRequestCreate(BaseModel):
    locker_id: str
    request_type: str = "ACCESS"
    scheduled_at: datetime | None = None


class StaffLockerRequestCreate(BaseModel):
    """Schema for bank operators creating a request on behalf of a physically present customer."""
    locker_id: str
    request_type: str = "ACCESS"   # ACCESS | INSPECTION | MAINTENANCE | CLOSURE
    scheduled_at: datetime | None = None


class LockerRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    locker_id: str
    customer_id: str
    request_type: str
    status: str
    requested_at: datetime
    scheduled_at: datetime | None = None
    approved_by: str | None = None
    completed_at: datetime | None = None
    rejection_reason: str | None = None
    correlation_id: str
    locker_number: str | None = None
    customer_name: str | None = None



class RejectRequest(BaseModel):
    reason: str


class VerifyTokenRequest(BaseModel):
    token: str


class FaceVerifyRequest(BaseModel):
    image: str  # base64 data-URI ("data:image/jpeg;base64,...") or raw base64
    blink_frame: str | None = None
    nod_frame: str | None = None
    # mock_override is accepted but only honoured outside production
    mock_override: str | None = None


class FaceVerificationOut(BaseModel):
    """Public representation of a FaceVerification row.

    raw_response is deliberately excluded — it holds biometric-derived
    signals and should not appear in API responses or logs.
    """
    model_config = ConfigDict(from_attributes=True)
    id: str
    request_id: str
    actor_id: str
    actor_role: str
    face_match: bool
    confidence: float
    liveness_passed: bool
    spoof_probability: float
    attempt_number: int
    created_at: datetime


class AuditEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    actor_id: str | None = None
    actor_role: str | None = None
    action: str
    entity_type: str
    entity_id: str | None = None
    previous_state: str | None = None
    new_state: str | None = None
    event_metadata: dict | None = None
    correlation_id: str | None = None
    created_at: datetime


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    title: str
    message: str
    type: str
    read: bool
    created_at: datetime


class CustomerEnrollmentRequest(BaseModel):
    full_name: str
    email: str
    phone: str
    face_image: str  # base64 data-URI or base64 string
    locker_id: str | None = None
    custom_id: str | None = None
    mock_override: bool = False



class NextCustomerIdResponse(BaseModel):
    next_customer_id: str

