from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class PermissionBase(BaseModel):
    economics: bool = Field(default=False, description="Access to costs, estimates, materials")
    consuntivi: bool = Field(default=False, description="Access to hours, progress")
    efficienza: bool = Field(default=False, description="Access to KPI, OEE, comparisons")
    risorse: bool = Field(default=False, description="Access to machines, operators, departments")


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