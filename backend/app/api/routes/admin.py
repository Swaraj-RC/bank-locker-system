from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.database import get_db
from app.core.responses import success, ApiError
from app.core.enums import RequestStatus, LockerStatus
from app.api.deps import require_staff, require_manager
from app.models import User, Locker, LockerRequest, AuditEvent, Branch, FaceVerification
from app.schemas.domain import (
    LockerOut, LockerRequestOut, RejectRequest, StaffLockerRequestCreate,
    CustomerEnrollmentRequest, NextCustomerIdResponse,
)
from app.services.audit_service import record_event
from app.services.state_machine import transition_request, transition_locker
from app.services.enrollment_service import get_next_customer_id, enroll_customer

router = APIRouter(prefix="/api/v1/admin", tags=["Admin"])


@router.get("/dashboard", summary="KPI summary for the admin dashboard")
def dashboard(user: User = Depends(require_staff), db: Session = Depends(get_db)):
    q = db.query(Locker)
    if user.role != "SUPER_ADMIN" and user.branch_id:
        q = q.filter(Locker.branch_id == user.branch_id)
    lockers = q.all()

    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    def _is_today(dt: datetime | None) -> bool:
        if not dt:
            return False
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc) >= today_start
        return dt >= today_start

    rq = db.query(LockerRequest)
    if user.role != "SUPER_ADMIN" and user.branch_id:
        rq = rq.join(Locker).filter(Locker.branch_id == user.branch_id)
    requests_all = rq.all()

    active_states = {"SUBMITTED", "VERIFICATION_PENDING", "TOKEN_A_VERIFIED", "TOKEN_B_VERIFIED", "APPROVAL_PENDING"}
    kpis = {
        "total_lockers": len(lockers),
        "occupied": sum(1 for l in lockers if l.status == "OCCUPIED"),
        "available": sum(1 for l in lockers if l.status == "AVAILABLE"),
        "active_requests": sum(1 for r in requests_all if r.status in active_states),
        "access_today": sum(1 for r in requests_all if r.status == "ACCESS_ACTIVE" or _is_today(r.completed_at)),
        "pending_verifications": sum(1 for r in requests_all if r.status == "VERIFICATION_PENDING"),
    }
    return success(kpis)


@router.get("/lockers", summary="Live visual vault grid data, with search/filter")
def list_lockers(
    branch_id: str | None = None,
    status: str | None = None,
    locker_size: str | None = None,
    search: str | None = None,
    user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    q = db.query(Locker)
    if user.role != "SUPER_ADMIN" and user.branch_id:
        q = q.filter(Locker.branch_id == user.branch_id)
    if branch_id:
        q = q.filter(Locker.branch_id == branch_id)
    if status:
        q = q.filter(Locker.status == status)
    if locker_size:
        q = q.filter(Locker.locker_size == locker_size)
    if search:
        q = q.filter(Locker.locker_number.ilike(f"%{search}%"))
    lockers = q.order_by(Locker.locker_number).all()
    return success([LockerOut.model_validate(l).model_dump() for l in lockers])


@router.get("/requests", summary="Request queue for bank staff")
def list_requests(
    status: str | None = None,
    user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    q = db.query(LockerRequest)
    if user.role != "SUPER_ADMIN" and user.branch_id:
        q = q.join(Locker).filter(Locker.branch_id == user.branch_id)
    if status:
        q = q.filter(LockerRequest.status == status)
    reqs = q.order_by(LockerRequest.requested_at.desc()).all()
    return success([LockerRequestOut.model_validate(r).model_dump() for r in reqs])


def _get_request_or_404(db: Session, request_id: str) -> LockerRequest:
    req = db.query(LockerRequest).filter(LockerRequest.id == request_id).first()
    if not req:
        raise ApiError("REQUEST_NOT_FOUND", "Request does not exist", 404)
    return req


@router.post("/requests/{request_id}/approve", summary="Approve a request awaiting approval")
def approve_request(request_id: str, user: User = Depends(require_staff), db: Session = Depends(get_db)):
    req = _get_request_or_404(db, request_id)
    req = transition_request(db, req, RequestStatus.APPROVED.value, user)
    req.approved_by = user.id
    db.commit()
    db.refresh(req)
    return success(LockerRequestOut.model_validate(req).model_dump(), "Request approved")


@router.post("/requests/{request_id}/reject", summary="Reject a request with a reason")
def reject_request(request_id: str, payload: RejectRequest, user: User = Depends(require_staff), db: Session = Depends(get_db)):
    req = _get_request_or_404(db, request_id)
    req.rejection_reason = payload.reason
    req = transition_request(db, req, RequestStatus.REJECTED.value, user, metadata={"reason": payload.reason})
    db.commit()
    db.refresh(req)
    return success(LockerRequestOut.model_validate(req).model_dump(), "Request rejected")


@router.post("/requests/{request_id}/start", summary="Start the operation (locker -> ACCESS_ACTIVE) after approval")
def start_operation(request_id: str, user: User = Depends(require_staff), db: Session = Depends(get_db)):
    req = _get_request_or_404(db, request_id)
    req = transition_request(db, req, RequestStatus.ACCESS_ACTIVE.value, user)
    transition_locker(db, req.locker, LockerStatus.ACCESS_ACTIVE.value, user, correlation_id=req.correlation_id)
    db.commit()
    db.refresh(req)
    return success(LockerRequestOut.model_validate(req).model_dump(), "Operation started — locker access active")


@router.post("/requests/{request_id}/complete", summary="Complete the operation (locker -> OCCUPIED)")
def complete_operation(request_id: str, user: User = Depends(require_staff), db: Session = Depends(get_db)):
    req = _get_request_or_404(db, request_id)
    req.completed_at = datetime.now(timezone.utc)
    req = transition_request(db, req, RequestStatus.COMPLETED.value, user)
    transition_locker(db, req.locker, LockerStatus.OCCUPIED.value, user, correlation_id=req.correlation_id)
    record_event(db, actor=user, action="OPERATION_COMPLETED", entity_type="LOCKER_REQUEST",
                 entity_id=req.id, correlation_id=req.correlation_id)
    db.commit()
    db.refresh(req)
    return success(LockerRequestOut.model_validate(req).model_dump(), "Operation completed")


@router.post("/requests/{request_id}/reset", summary="Reset request back to SUBMITTED state for demonstration/retry")
def reset_request(
    request_id: str,
    target_state: str = Query(default="SUBMITTED"),
    user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    req = _get_request_or_404(db, request_id)
    prev = req.status
    if prev != target_state:
        req = transition_request(db, req, target_state, user, metadata={"reason": "operator_manual_reset"})
    if req.locker and req.locker.status == LockerStatus.ACCESS_ACTIVE.value:
        transition_locker(db, req.locker, LockerStatus.OCCUPIED.value, user, correlation_id=req.correlation_id)
    
    # Clear previous face verification attempts so attempt counter cleanly starts from 0
    db.query(FaceVerification).filter(FaceVerification.request_id == req.id).delete()

    record_event(
        db, actor=user, action="REQUEST_STATE_RESET",
        entity_type="LOCKER_REQUEST", entity_id=req.id,
        previous_state=prev, new_state=target_state,
        metadata={"reset_by": user.email},
        correlation_id=req.correlation_id,
    )
    db.commit()
    db.refresh(req)
    return success(LockerRequestOut.model_validate(req).model_dump(), f"Request reset from {prev} to {target_state}")


@router.post("/requests", summary="Staff creates a locker access request for a physically present customer", status_code=201)
def staff_create_request(
    payload: StaffLockerRequestCreate,
    user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    """Bank operator submits a request on behalf of a customer who is physically present at the branch.

    Since the customer mobile app is removed, all requests originate here.
    The customer must be assigned to the locker.
    """
    locker = db.query(Locker).filter(Locker.id == payload.locker_id).first()
    if not locker:
        raise ApiError("LOCKER_NOT_FOUND", "Locker does not exist", 404)

    if locker.customer_id is None:
        raise ApiError("LOCKER_UNASSIGNED", "This locker has no assigned customer", 422)

    if locker.status not in ("OCCUPIED", "AVAILABLE"):
        raise ApiError("LOCKER_UNAVAILABLE", f"Locker is currently {locker.status} and cannot accept new requests", 409)

    existing = (
        db.query(LockerRequest)
        .filter(
            LockerRequest.locker_id == locker.id,
            LockerRequest.status.notin_([
                RequestStatus.COMPLETED.value, RequestStatus.REJECTED.value,
                RequestStatus.EXPIRED.value, RequestStatus.CANCELLED.value,
            ]),
        )
        .first()
    )
    if existing:
        raise ApiError("DUPLICATE_REQUEST", "An active request already exists for this locker", 409)

    req = LockerRequest(
        locker_id=locker.id,
        customer_id=locker.customer_id,  # always resolved server-side from locker
        request_type=payload.request_type,
        status=RequestStatus.SUBMITTED.value,
        scheduled_at=payload.scheduled_at,
    )
    db.add(req)
    db.flush()
    record_event(
        db, actor=user, action="REQUEST_SUBMITTED_BY_STAFF",
        entity_type="LOCKER_REQUEST", entity_id=req.id,
        new_state=req.status, correlation_id=req.correlation_id,
        metadata={"created_for_customer_id": locker.customer_id},
    )
    db.commit()
    db.refresh(req)
    return success(LockerRequestOut.model_validate(req).model_dump(), "Request created successfully", 201)


@router.get("/customers", summary="List all customers (for staff to look up customers when creating requests)")
def list_customers(
    search: str | None = None,
    user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    q = db.query(User).filter(User.role == "CUSTOMER", User.status == "ACTIVE")
    if search:
        q = q.filter(
            User.full_name.ilike(f"%{search}%") | User.email.ilike(f"%{search}%")
        )
    customers = q.order_by(User.full_name).all()
    from app.schemas.auth import UserOut
    return success([UserOut.model_validate(c).model_dump() for c in customers])


@router.get("/customers/next-id", summary="Get the next auto-incremented customer ID (e.g. customer003)")
def get_next_id(
    user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    next_id = get_next_customer_id(db)
    return success({"next_customer_id": next_id})


@router.post("/customers/enroll", summary="Enroll a new customer with live face capture and biometric embedding", status_code=201)
def enroll_new_customer(
    payload: CustomerEnrollmentRequest,
    user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    """Enroll a new customer by extracting face embedding, saving to database and disk, and assigning locker."""
    result = enroll_customer(
        db=db,
        full_name=payload.full_name,
        email=payload.email,
        phone=payload.phone,
        face_image=payload.face_image,
        actor=user,
        locker_id=payload.locker_id,
        custom_id=payload.custom_id,
        mock_override=payload.mock_override,
    )

    return success(result, "Customer enrolled successfully", 201)

