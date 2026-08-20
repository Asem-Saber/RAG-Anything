import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from rag_anything.db.models.user import UserRole, UserStatus

MIN_PASSWORD_LENGTH = 12

USERNAME_PATTERN = r"^[A-Za-z0-9_-]+$"

class SignupRequest(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=32, pattern=USERNAME_PATTERN)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=256)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1, max_length=512)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Access-token lifetime in seconds.")


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    username: str
    first_name: str
    last_name: str
    role: UserRole
    status: UserStatus
    created_at: datetime