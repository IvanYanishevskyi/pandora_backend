from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class DatabaseAccessBase(BaseModel):
    can_read: bool = Field(default=True)
    can_write: bool = Field(default=False)


class DatabaseAccessCreate(DatabaseAccessBase):
    user_id: int = Field(...)
    database_id: int = Field(...)



class DatabaseAccessBulkCreate(BaseModel):
    user_id: int = Field(...)
    database_ids: List[int] = Field(...)
    can_read: bool = Field(default=True)
    can_write: bool = Field(default=False)

class DatabaseAccessUpdate(DatabaseAccessBase):
    pass


class DatabaseAccessResponse(DatabaseAccessBase):
    id: int
    user_id: int
    database_id: int
    created_at: datetime
    updated_at: datetime
    created_by: Optional[int] = None

    class Config:
        from_attributes = True


class DatabaseAccessWithDetails(DatabaseAccessResponse):
    user_username: Optional[str] = None
    database_name: Optional[str] = None
    client_name: Optional[str] = None


class UserDatabaseAccessSummary(BaseModel):
    user_id: int
    username: str
    total_databases: int
    accessible_databases: int
    databases_with_write: int
    databases: List[DatabaseAccessWithDetails]

    class Config:
        from_attributes = True


class DatabaseUserAccessSummary(BaseModel):
    database_id: int
    database_name: str
    client_id: int
    client_name: str
    total_users_with_access: int
    users: List[DatabaseAccessWithDetails]

    class Config:
        from_attributes = True
