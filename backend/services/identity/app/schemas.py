from datetime import datetime
from uuid import UUID
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    email: EmailStr
    display_name: str
    is_platform_admin: bool
    avatar_data_url: Optional[str] = None


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: UserResponse


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str

class UserCreate(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=14, max_length=256)
    is_active: bool = True
    is_platform_admin: bool = False
    avatar_data_url: Optional[str] = Field(default=None, max_length=100000)


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    display_name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    password: Optional[str] = Field(default=None, min_length=14, max_length=256)
    is_active: Optional[bool] = None
    is_platform_admin: Optional[bool] = None
    avatar_data_url: Optional[str] = Field(default=None, max_length=100000)


class UserCompanyAssignment(BaseModel):
    company_id: UUID
    role_id: UUID


class UserMembershipsUpdate(BaseModel):
    assignments: list[UserCompanyAssignment]


class CompanyCreate(BaseModel):
    legal_name: str = Field(min_length=1, max_length=200)
    trade_name: Optional[str] = Field(default=None, max_length=200)
    tax_id: Optional[str] = Field(default=None, max_length=24)
    country_code: str = Field(default="PE", min_length=2, max_length=2)
    default_currency: str = Field(default="PEN", min_length=3, max_length=3)
    timezone: str = Field(default="America/Lima", max_length=64)


class CompanyUpdate(BaseModel):
    legal_name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    trade_name: Optional[str] = Field(default=None, max_length=200)
    tax_id: Optional[str] = Field(default=None, max_length=24)
    default_currency: Optional[str] = Field(default=None, min_length=3, max_length=3)
    timezone: Optional[str] = Field(default=None, max_length=64)
    is_active: Optional[bool] = None


class RoleCreate(BaseModel):
    company_id: Optional[UUID] = None
    code: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=120)
    description: Optional[str] = None


class RoleUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    description: Optional[str] = None


class MembershipCreate(BaseModel):
    company_id: UUID
    user_id: UUID
    role_id: UUID
    is_active: bool = True


class MembershipUpdate(BaseModel):
    role_id: Optional[UUID] = None
    is_active: Optional[bool] = None


class DocumentTypeCreate(BaseModel):
    company_id: Optional[UUID] = None
    code: str = Field(min_length=1, max_length=80, pattern="^[A-Z0-9_-]+$")
    name: str = Field(min_length=1, max_length=160)
    category: str = Field(min_length=1, max_length=80)
    description: Optional[str] = None
    prefix: Optional[str] = Field(default=None, max_length=24)
    requires_tax_id: bool = False
    is_active: bool = True


class DocumentTypeUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=160)
    category: Optional[str] = Field(default=None, min_length=1, max_length=80)
    description: Optional[str] = None
    prefix: Optional[str] = Field(default=None, max_length=24)
    requires_tax_id: Optional[bool] = None
    is_active: Optional[bool] = None
