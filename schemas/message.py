# schemas/message.py
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime

class MessageCreate(BaseModel):
    chat_id:     int          # id чата в БД
    role:        str        # "user" | "bot"
    content:     str
    output:      Optional[Dict[str, Any]] = None

class MessageOut(BaseModel):
    id:          int
    role:        str
    content:     str
    output:      Optional[Dict[str, Any]]
    created_at:  datetime

    class Config:
        from_attributes = True
