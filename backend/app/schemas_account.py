from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class GuardianConsentInput(BaseModel):
    terms_version: str = Field(min_length=1, max_length=40)
    privacy_version: str = Field(min_length=1, max_length=40)
    child_policy_version: str = Field(min_length=1, max_length=40)
    consent_scope: dict[str, bool]


class GuardianConsentRead(ORMModel):
    id: str
    guardian_user_id: str
    family_id: str
    student_id: str | None
    terms_version: str
    privacy_version: str
    child_policy_version: str
    consent_scope: dict
    accepted_at: datetime
    revoked_at: datetime | None


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=10, max_length=128)
    revoke_other_sessions: bool = True


class AccountDeactivateRequest(BaseModel):
    password: str = Field(min_length=8, max_length=128)
    confirmation: str


class SessionRead(ORMModel):
    id: str
    user_id: str
    expires_at: datetime
    revoked_at: datetime | None
    user_agent: str | None
    created_at: datetime


class EmailVerificationRequest(BaseModel):
    token: str = Field(min_length=20, max_length=300)


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str = Field(min_length=20, max_length=300)
    new_password: str = Field(min_length=10, max_length=128)
