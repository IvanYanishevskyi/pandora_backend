# routes/chats.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database.database import get_db
from models.chat import Chat
from schemas.chat import ChatCreate, ChatOut
from typing import List
from pydantic import BaseModel
from models.messages import Message as MessageModel
router = APIRouter(prefix="/chats", tags=["chats"])
class UpdateChatTitle(BaseModel):
    title: str
@router.delete("/{chat_id}", status_code=204)
def delete_chat(chat_id: int, db: Session = Depends(get_db)):
    chat = db.query(Chat).filter(Chat.id == chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    db.query(MessageModel).filter(MessageModel.chat_id == chat_id).delete()

    db.delete(chat)
    db.commit()
@router.post("", response_model=ChatOut)
def create_chat(body: ChatCreate, db: Session = Depends(get_db)):
    chat = Chat(
        external_id = body.external_id,   
        user_id     = body.user_id,
        db_id       = body.db_id or "primo",
        title       = body.title or ""
    )
    db.add(chat)
    db.commit()
    db.refresh(chat)
    return chat


@router.get("/{user_id}", response_model=List[ChatOut])
def get_chats_by_user(user_id: int, db: Session = Depends(get_db)):
    return (
        db.query(Chat)
          .filter(Chat.user_id == user_id)
          .order_by(Chat.created_at.desc())
          .all()
    )

@router.post("/{chat_id}/update-title", status_code=200)
def update_chat_title(chat_id: int, body: UpdateChatTitle, db: Session = Depends(get_db)):
    chat = db.query(Chat).filter(Chat.id == chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    chat.title = body.title
    db.commit()
    db.refresh(chat)
    return {"success": True, "title": chat.title}
