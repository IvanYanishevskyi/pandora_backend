from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class PermissionBase(BaseModel):
    economics: bool = Field(default=False)
    consuntivi: bool = Field(default=False)
    efficienza: bool = Field(default=False)
    risorse: bool = Field(default=False)

class PermissionCreate(PermissionBase):
    user_id: int


class PermissionUpdate(PermissionBase):
    pass


class PermissionResponse(PermissionBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserWithPermissions(BaseModel):
    id: int
    username: str
    email: Optional[str]
    full_name: Optional[str]
    role: str
    is_active: bool
    permissions: Optional[PermissionResponse] = None

    class Config:
        from_attributes = True