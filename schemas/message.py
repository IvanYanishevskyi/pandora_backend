from pydantic import BaseModel, field_validator
from typing import Optional, Dict, Any, Literal, Union
from datetime import datetime

class MessageCreate(BaseModel):
    chat_id: int
    role: Literal["user", "bot"]
    content: Union[str, Dict[str, Any]]
    output: Optional[Dict[str, Any]] = None
    sql: Optional[str] = None    
    dialect: Optional[str] = None   
    
    @field_validator('content', mode='before')
    @classmethod
    def extract_question(cls, v):
        """If content is a dict with 'question', extract it as string"""
        if isinstance(v, dict) and 'question' in v:
            return v['question']
        return v

class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    output: Optional[Dict[str, Any]] = None
    sql: Optional[str] = None     
    dialect: Optional[str] = None   
    created_at: datetime

    class Config:
        from_attributes = True
