from pydantic import BaseModel, ConfigDict


class LoginRequest(BaseModel):
    email: str
    password: str



class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    full_name: str
    email: str
    phone: str
    role: str
    branch_id: str | None = None
    status: str
