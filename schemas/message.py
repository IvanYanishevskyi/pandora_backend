# schemas/message.py
from pydantic import BaseModel
from typing import Optional, Dict, Any, Literal
from datetime import datetime

class MessageCreate(BaseModel):
    chat_id: int
    role: Literal["user", "bot"]
    content: str
    output: Optional[Dict[str, Any]] = None
    sql: Optional[str] = None        # NEW
    dialect: Optional[str] = None    # NEW

class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    output: Optional[Dict[str, Any]] = None
    sql: Optional[str] = None        # NEW
    dialect: Optional[str] = None    # NEW
    created_at: datetime

    class Config:
        from_attributes = True
