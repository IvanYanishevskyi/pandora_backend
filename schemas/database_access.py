from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class DatabaseAccessBase(BaseModel):
    """Базовая схема для доступа к БД"""
    can_read: bool = Field(default=True, description="Право на чтение из базы данных")
    can_write: bool = Field(default=False, description="Право на запись в базу данных")


class DatabaseAccessCreate(DatabaseAccessBase):
    """Схема для создания доступа к БД"""
    user_id: int = Field(..., description="ID пользователя")
    database_id: int = Field(..., description="ID базы данных")


class DatabaseAccessBulkCreate(BaseModel):
    """Схема для массового создания доступов"""
    user_id: int = Field(..., description="ID пользователя")
    database_ids: List[int] = Field(..., description="Список ID баз данных")
    can_read: bool = Field(default=True, description="Право на чтение")
    can_write: bool = Field(default=False, description="Право на запись")


class DatabaseAccessUpdate(DatabaseAccessBase):
    """Схема для обновления прав доступа"""
    pass


class DatabaseAccessResponse(DatabaseAccessBase):
    """Схема ответа с информацией о доступе"""
    id: int
    user_id: int
    database_id: int
    created_at: datetime
    updated_at: datetime
    created_by: Optional[int] = None

    class Config:
        from_attributes = True


class DatabaseAccessWithDetails(DatabaseAccessResponse):
    """Расширенная схема с деталями пользователя и БД"""
    user_username: Optional[str] = None
    database_name: Optional[str] = None
    client_name: Optional[str] = None


class UserDatabaseAccessSummary(BaseModel):
    """Сводка по доступам пользователя"""
    user_id: int
    username: str
    total_databases: int
    accessible_databases: int
    databases_with_write: int
    databases: List[DatabaseAccessWithDetails]

    class Config:
        from_attributes = True


class DatabaseUserAccessSummary(BaseModel):
    """Сводка по пользователям, имеющим доступ к БД"""
    database_id: int
    database_name: str
    client_id: int
    client_name: str
    total_users_with_access: int
    users: List[DatabaseAccessWithDetails]

    class Config:
        from_attributes = True
