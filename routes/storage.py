from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database.database import get_db
from schemas.message import MessageCreate, MessageOut
from models.chat import Chat
from models.messages import Message as MessageModel
import json

router = APIRouter(prefix="/storage/messages", tags=["storage"])

@router.post("", response_model=MessageOut, status_code=201)
def create_message(msg: MessageCreate, db: Session = Depends(get_db)):


    chat = db.query(Chat).filter(Chat.id == msg.chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
 # Fallback: берем sql из msg.sql либо из output.sql
    sql_val = msg.sql
    if sql_val is None and isinstance(msg.output, dict):
        sql_val = msg.output.get("sql")
    db_msg = MessageModel(
        chat_id=msg.chat_id,
        role=msg.role,
        content=msg.content,   # <-- оставляем как есть
        sql_text=sql_val,                 # NEW
        sql_dialect=msg.dialect,          # NEW
        output=msg.output,     # <-- JSON как есть
    )
    db.add(db_msg)
    db.commit()
    db.refresh(db_msg)



    return db_msg

