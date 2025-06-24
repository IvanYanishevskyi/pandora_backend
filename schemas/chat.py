# schemas/chat.py
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from uuid import UUID
from schemas.message import MessageOut

class ChatCreate(BaseModel):
    external_id: str
    user_id: int
    title: str | None = None
    db_id: str | None = None


class ChatOut(BaseModel):
    id: int
    external_id: str
    db_id: str                    # ← добавили
    title: str | None = None
    created_at: datetime
    messages: List[MessageOut]

    class Config:
        from_attributes = True    # (Pydantic v2)

