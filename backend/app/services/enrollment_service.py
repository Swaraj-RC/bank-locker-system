"""
Customer Face Enrollment Service for Bank Locker OS.

Handles:
  1. Auto-incrementing customer IDs (customer003, customer004, ...).
  2. Decoding captured face image from base64.
  3. Extracting 128-d facial embedding with face_recognition / dlib.
  4. Persisting embeddings to both local data/embeddings and Project NPN dataset.
  5. Creating customer user record in database.
  6. Assigning available locker (optional).
  7. Recording audit events.
"""
import base64
import binascii
import logging
import os
import re
from pathlib import Path
import numpy as np
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.enums import LockerStatus, UserRole, UserStatus, RequestStatus, RequestType
from app.core.responses import ApiError
from app.core.security import hash_password
from app.models import Locker, User, LockerRequest
from app.services.audit_service import record_event


logger = logging.getLogger("bank_locker_backend")

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_PASSWORD = "Demo@1234"

try:
    import face_recognition
    _AI_AVAILABLE = True
except Exception:
    face_recognition = None
    _AI_AVAILABLE = False


def get_next_customer_id(db: Session) -> str:
    """Calculate the next customer ID based on existing customer users in the database.
    
    Looks for IDs matching 'customer(\\d+)' and increments the highest number.
    Default starting ID is 'customer001' (or 'customer003' if seeded customers customer001 and customer002 exist).
    """
    users = db.query(User.id).filter(User.role == UserRole.CUSTOMER.value).all()
    max_num = 0
    pattern = re.compile(r"^customer(\d+)$", re.IGNORECASE)

    for (user_id,) in users:
        match = pattern.match(user_id)
        if match:
            num = int(match.group(1))
            if num > max_num:
                max_num = num

    # If database has no customerXXX users yet, check existing baseline embeddings on disk
    if max_num == 0:
        candidate_dirs = [
            BASE_DIR / settings.EMBEDDINGS_DIR,
            Path(r"c:\Users\Swaraj\OneDrive\Desktop\project NPN\NPN\data\embeddings"),
        ]
        for d in candidate_dirs:
            if d.exists():
                for f in d.glob("customer*.npy"):
                    match = pattern.match(f.stem)
                    if match:
                        num = int(match.group(1))
                        if num > max_num:
                            max_num = num

    next_num = max_num + 1
    return f"customer{next_num:03d}"



def _decode_face_image(image_data: str) -> np.ndarray:
    """Decode base64 data-URI to RGB numpy array."""
    from app.services.face_verification_service import _decode_image
    from app.ai.real_face_adapter import decode_image_bytes

    image_bytes, _ = _decode_image(image_data)
    rgb_frame = decode_image_bytes(image_bytes)
    return rgb_frame


def extract_and_save_face_embedding(customer_id: str, rgb_frame: np.ndarray, mock_override: bool = False) -> np.ndarray:
    """Detect face, compute 128-d embedding, and save .npy to all configured storage locations."""
    current_ai_mode = os.getenv("AI_MODE", settings.AI_MODE)
    use_mock = mock_override or current_ai_mode == "mock" or not _AI_AVAILABLE or face_recognition is None

    if not use_mock:
        face_locations = face_recognition.face_locations(rgb_frame)
        if len(face_locations) == 0:
            raise ApiError(
                "NO_FACE_DETECTED",
                "No face detected in the captured image. Please align face clearly in the camera frame.",
                400,
            )
        if len(face_locations) > 1:
            raise ApiError(
                "MULTIPLE_FACES_DETECTED",
                f"Multiple faces detected ({len(face_locations)}). Ensure only one person is in front of the camera.",
                400,
            )

        encodings = face_recognition.face_encodings(rgb_frame, face_locations)
        if not encodings:
            raise ApiError(
                "ENCODING_FAILED",
                "Could not extract facial features. Please ensure proper lighting and look directly at camera.",
                400,
            )
        embedding = encodings[0].astype(np.float64)
    else:
        # Development / test / mock mode: generate a deterministic 128-d synthetic vector
        logger.info("AI mode is mock; generating synthetic 128-d face embedding for %s", customer_id)
        rng = np.random.default_rng(seed=abs(hash(customer_id)) % (2**32))
        embedding = rng.standard_normal(128, dtype=np.float64)
        embedding = embedding / np.linalg.norm(embedding)


    # Persist embedding to directories
    target_dirs = [
        BASE_DIR / settings.EMBEDDINGS_DIR,
        Path(r"c:\Users\Swaraj\OneDrive\Desktop\project NPN\NPN\data\embeddings"),
    ]

    saved_locations = []
    for directory in target_dirs:
        try:
            directory.mkdir(parents=True, exist_ok=True)
            out_file = directory / f"{customer_id}.npy"
            np.save(out_file, embedding)
            saved_locations.append(str(out_file))
            logger.info("Saved face embedding for %s to %s", customer_id, out_file)
        except Exception as exc:
            logger.warning("Could not save embedding to %s: %s", directory, exc)

    if not saved_locations:
        raise ApiError("STORAGE_ERROR", "Failed to persist face embedding to storage", 500)

    return embedding


def enroll_customer(
    db: Session,
    full_name: str,
    email: str,
    phone: str,
    face_image: str,
    actor: User,
    locker_id: str | None = None,
    custom_id: str | None = None,
    mock_override: bool = False,
) -> dict:
    """Enroll a new customer with face biometric data, create user record, and optionally assign locker."""
    # 1. Determine customer ID
    customer_id = (custom_id.strip() if custom_id else "") or get_next_customer_id(db)

    # 2. Check for unique constraints
    if db.query(User).filter(User.id == customer_id).first():
        raise ApiError("CUSTOMER_ID_EXISTS", f"Customer ID '{customer_id}' already exists.", 409)

    if db.query(User).filter(User.email == email.lower().strip()).first():
        raise ApiError("EMAIL_EXISTS", f"Email '{email}' is already registered.", 409)

    if db.query(User).filter(User.phone == phone.strip()).first():
        raise ApiError("PHONE_EXISTS", f"Phone number '{phone}' is already registered.", 409)

    # 3. Decode face image and extract embedding
    rgb_frame = _decode_face_image(face_image)
    embedding = extract_and_save_face_embedding(customer_id, rgb_frame, mock_override=mock_override)


    # 4. Create User entity
    new_user = User(
        id=customer_id,
        full_name=full_name.strip(),
        email=email.lower().strip(),
        phone=phone.strip(),
        password_hash=hash_password(DEFAULT_PASSWORD),
        role=UserRole.CUSTOMER.value,
        branch_id=actor.branch_id,
        status=UserStatus.ACTIVE.value,
    )
    db.add(new_user)
    db.flush()

    # 5. Optional locker assignment & automatic initial access request creation
    assigned_locker_info = None
    created_request_info = None
    if locker_id:
        locker = db.query(Locker).filter(Locker.id == locker_id).first()
        if not locker:
            raise ApiError("LOCKER_NOT_FOUND", "Selected locker was not found", 404)
        if locker.status != LockerStatus.AVAILABLE.value:
            raise ApiError("LOCKER_NOT_AVAILABLE", f"Locker {locker.locker_number} is currently {locker.status}", 409)

        locker.customer_id = new_user.id
        locker.status = LockerStatus.OCCUPIED.value
        assigned_locker_info = {
            "id": locker.id,
            "locker_number": locker.locker_number,
            "locker_size": locker.locker_size,
            "status": locker.status,
        }

        # Automatically create initial ACCESS request in SUBMITTED state for face verification
        new_request = LockerRequest(
            locker_id=locker.id,
            customer_id=new_user.id,
            request_type=RequestType.ACCESS.value,
            status=RequestStatus.SUBMITTED.value,
        )
        db.add(new_request)
        db.flush()
        created_request_info = {
            "id": new_request.id,
            "status": new_request.status,
            "request_type": new_request.request_type,
            "locker_id": new_request.locker_id,
            "customer_id": new_request.customer_id,
        }

        record_event(
            db,
            actor=actor,
            action="REQUEST_SUBMITTED_BY_STAFF",
            entity_type="LOCKER_REQUEST",
            entity_id=new_request.id,
            new_state=new_request.status,
            correlation_id=new_request.correlation_id,
            metadata={"created_for_customer_id": new_user.id, "auto_created_on_enrollment": True},
        )

    # 6. Audit Logging
    record_event(
        db,
        actor=actor,
        action="CUSTOMER_ENROLLED",
        entity_type="USER",
        entity_id=new_user.id,
        metadata={
            "customer_id": customer_id,
            "full_name": new_user.full_name,
            "email": new_user.email,
            "phone": new_user.phone,
            "locker_id": locker_id,
            "request_id": created_request_info["id"] if created_request_info else None,
            "embedding_shape": list(embedding.shape),
        },
    )

    db.commit()
    db.refresh(new_user)

    return {
        "customer": {
            "id": new_user.id,
            "full_name": new_user.full_name,
            "email": new_user.email,
            "phone": new_user.phone,
            "role": new_user.role,
            "status": new_user.status,
            "branch_id": new_user.branch_id,
        },
        "assigned_locker": assigned_locker_info,
        "access_request": created_request_info,
        "embedding_registered": True,
        "message": f"Customer {new_user.id} ({new_user.full_name}) successfully enrolled with face biometrics.",
    }

