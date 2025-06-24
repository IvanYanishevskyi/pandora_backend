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

    content_to_store = msg.content
    if msg.role == "bot" and isinstance(msg.output, dict):
        content_to_store = json.dumps(msg.output)

    db_msg = MessageModel(
        chat_id=msg.chat_id,
        role=msg.role,
        content=content_to_store,
        output=msg.output,
    )
    db.add(db_msg)
    db.commit()
    db.refresh(db_msg)
    return db_msg
