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
    sql_val = msg.sql
    if sql_val is None and isinstance(msg.output, dict):
        sql_val = msg.output.get("sql")
    # Content is already processed by validator (question extracted if needed)
    db_msg = MessageModel(
        chat_id=msg.chat_id,
        role=msg.role,
        content=msg.content,
        sql_text=sql_val,
        sql_dialect=msg.dialect,
        output=msg.output,
    )
    db.add(db_msg)
    db.commit()
    db.refresh(db_msg)



    return db_msg

