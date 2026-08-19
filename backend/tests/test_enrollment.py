import io
import base64
import pytest
from PIL import Image
from app.core.security import create_access_token
from app.models import User, Locker
from app.services.enrollment_service import get_next_customer_id


def _create_dummy_image_b64() -> str:
    img = Image.new("RGB", (100, 100), color=(128, 128, 128))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    raw_bytes = buf.getvalue()
    return "data:image/jpeg;base64," + base64.b64encode(raw_bytes).decode("ascii")


def test_next_customer_id_increment(db_session, seeded):
    # Currently seeded has 1 customer with default uuid
    # Let's add customer001 and customer002
    c1 = User(id="customer001", full_name="C1", email="c1@test.com", phone="+9190001", password_hash="x", role="CUSTOMER")
    c2 = User(id="customer002", full_name="C2", email="c2@test.com", phone="+9190002", password_hash="x", role="CUSTOMER")
    db_session.add_all([c1, c2])
    db_session.commit()

    next_id = get_next_customer_id(db_session)
    assert next_id == "customer003"

    # Add customer003
    c3 = User(id="customer003", full_name="C3", email="c3@test.com", phone="+9190003", password_hash="x", role="CUSTOMER")
    db_session.add(c3)
    db_session.commit()

    next_id = get_next_customer_id(db_session)
    assert next_id == "customer004"


def test_get_next_id_api(client, seeded):
    token = create_access_token(seeded["operator"].id, "BANK_OPERATOR")
    headers = {"Authorization": f"Bearer {token}"}

    res = client.get("/api/v1/admin/customers/next-id", headers=headers)
    assert res.status_code == 200
    data = res.json()["data"]
    assert "next_customer_id" in data
    assert data["next_customer_id"].startswith("customer")


def test_enroll_customer_api(client, db_session, seeded):
    token = create_access_token(seeded["operator"].id, "BANK_OPERATOR")
    headers = {"Authorization": f"Bearer {token}"}

    # Create an available locker
    branch = seeded["branch"]
    available_locker = Locker(
        branch_id=branch.id,
        locker_number="L-999",
        locker_size="LARGE",
        status="AVAILABLE",
    )
    db_session.add(available_locker)
    db_session.commit()

    img_b64 = _create_dummy_image_b64()
    payload = {
        "full_name": "Swaraj RC",
        "email": "swaraj.new@bank.com",
        "phone": "+919876543210",
        "face_image": img_b64,
        "locker_id": available_locker.id,
        "mock_override": True,
    }

    res = client.post("/api/v1/admin/customers/enroll", json=payload, headers=headers)
    assert res.status_code == 201
    resp_data = res.json()["data"]
    assert "customer" in resp_data
    assert resp_data["customer"]["full_name"] == "Swaraj RC"
    assert resp_data["customer"]["email"] == "swaraj.new@bank.com"
    assigned_cust_id = resp_data["customer"]["id"]
    assert assigned_cust_id.startswith("customer")

    # Verify user exists in database
    user = db_session.query(User).filter(User.id == assigned_cust_id).first()
    assert user is not None
    assert user.role == "CUSTOMER"

    # Verify locker status updated to OCCUPIED and assigned to new customer
    db_session.refresh(available_locker)
    assert available_locker.status == "OCCUPIED"
    assert available_locker.customer_id == user.id


def test_enroll_customer_duplicate_validation(client, db_session, seeded):
    token = create_access_token(seeded["operator"].id, "BANK_OPERATOR")
    headers = {"Authorization": f"Bearer {token}"}

    img_b64 = _create_dummy_image_b64()
    payload = {
        "full_name": "Duplicate Test",
        "email": "cust@test.com",  # already exists in seeded
        "phone": "+919999999999",
        "face_image": img_b64,
        "mock_override": True,
    }

    res = client.post("/api/v1/admin/customers/enroll", json=payload, headers=headers)
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "EMAIL_EXISTS"

