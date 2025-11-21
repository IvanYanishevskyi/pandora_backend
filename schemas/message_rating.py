from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class MessageContent(BaseModel):
    sql: str
    explanation: str

class MessageItem(BaseModel):
    role: str = Field(...)
    content: str | MessageContent = Field(...)

class MessageRatingCreate(BaseModel):
    database_id: int = Field(...)
    is_valid: bool = Field(...)
    messages: List[MessageItem] = Field(...)

class MessageRatingResponse(BaseModel):
    id: int
    user_id: int
    username: str
    database_id: int
    database_name: str
    is_valid: bool
    messages: List[Dict[str, Any]]
    created_at: datetime

    class Config:
        from_attributes = True

class MessageRatingListResponse(BaseModel):
    ratings: List[MessageRatingResponse]
    total: int
