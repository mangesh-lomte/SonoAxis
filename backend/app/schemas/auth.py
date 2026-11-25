from typing import Optional, Literal
from pydantic import BaseModel, Field

DoctorRole = Literal["Radiologist", "Administrator"]


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)


class UserProfileResponse(BaseModel):
    id: str
    username: str
    full_name: str
    display_name: str
    credentials: Optional[str] = None
    designation: Optional[str] = None
    role: DoctorRole
    department: Optional[str] = None
    email: Optional[str] = None
    is_active: bool = True
    is_demo: bool = False
    created_at: str
    last_login_at: Optional[str] = None


class LoginResponse(BaseModel):
    access_token: str
    csrf_token: str
    token_type: str = "bearer"
    user: UserProfileResponse


class UserCreateRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=64)
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str = Field(..., min_length=2, max_length=128)
    credentials: Optional[str] = ""
    designation: Optional[str] = "Consultant Radiologist"
    role: DoctorRole = "Radiologist"
    department: Optional[str] = "Department of Radiology & Imaging"
    email: Optional[str] = None
    is_demo: bool = False


class UserUpdateRequest(BaseModel):
    full_name: Optional[str] = Field(None, min_length=2, max_length=128)
    credentials: Optional[str] = None
    designation: Optional[str] = None
    role: Optional[DoctorRole] = None
    department: Optional[str] = None
    email: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = Field(None, min_length=8, max_length=128)


class ProfileUpdateRequest(BaseModel):
    full_name: Optional[str] = Field(None, min_length=2, max_length=128)
    credentials: Optional[str] = None
    designation: Optional[str] = None
    department: Optional[str] = None
    email: Optional[str] = None


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)
