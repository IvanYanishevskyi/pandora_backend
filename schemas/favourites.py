from typing import List, Optional, Any
from pydantic import BaseModel
from datetime import datetime
from enum import Enum

class DialectEnum(str, Enum):
    mysql = "mysql"
    postgres = "postgres"

class FavoriteBase(BaseModel):
    user_id: Optional[int] = None
    title: str
    question_text: str
    sql_correct: str
    dialect: DialectEnum = DialectEnum.mysql
    tags: Optional[List[str]] = None
    is_pinned: bool = False
    conversation_id: Optional[str] = None  # UUID to group Q&A in favorites

class FavoriteCreate(FavoriteBase):
    pass

class FavoriteUpdate(BaseModel):
    title: Optional[str]
    question_text: Optional[str]
    sql_correct: Optional[str]
    dialect: Optional[DialectEnum]
    tags: Optional[List[str]]
    is_pinned: Optional[bool]
    usage_count: Optional[int]
    last_used_at: Optional[datetime]
    conversation_id: Optional[str]  # UUID to group Q&A in favorites

class FavoriteOut(FavoriteBase):
    id: int
    usage_count: int
    last_used_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True