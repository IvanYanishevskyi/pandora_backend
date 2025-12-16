from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database.database import get_db
from schemas.message import MessageCreate, MessageOut
from models.chat import Chat
from models.messages import Message as MessageModel
from typing import List
import json
import uuid

router = APIRouter(prefix="/storage/messages", tags=["storage"])

@router.post("", response_model=MessageOut, status_code=201)
def create_message(msg: MessageCreate, db: Session = Depends(get_db)):


    chat = db.query(Chat).filter(Chat.id == msg.chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    sql_val = msg.sql
    if sql_val is None and isinstance(msg.output, dict):
        sql_val = msg.output.get("sql")
    
    # Smart conversation_id generation for Q&A pairing
    if msg.conversation_id:
        # Client provided conversation_id - use it
        conversation_id = msg.conversation_id
    elif msg.role == "user":
        # New user question - generate new conversation_id
        conversation_id = str(uuid.uuid4())
    else:
        # Bot answer without conversation_id - find last unpaired user message
        last_user_msg = (
            db.query(MessageModel)
            .filter(
                MessageModel.chat_id == msg.chat_id,
                MessageModel.role == "user"
            )
            .order_by(MessageModel.created_at.desc())
            .first()
        )
        
        if last_user_msg and last_user_msg.conversation_id:
            # Check if this user message already has a bot response
            has_response = db.query(MessageModel).filter(
                MessageModel.conversation_id == last_user_msg.conversation_id,
                MessageModel.role == "bot"
            ).first()
            
            if not has_response:
                # Use the same conversation_id as the user question
                conversation_id = last_user_msg.conversation_id
            else:
                # User message already has response, create new conversation
                conversation_id = str(uuid.uuid4())
        else:
            # No previous user message found, create new conversation
            conversation_id = str(uuid.uuid4())
    
    # Content is already processed by validator (question extracted if needed)
    db_msg = MessageModel(
        chat_id=msg.chat_id,
        role=msg.role,
        content=msg.content,
        sql_text=sql_val,
        sql_dialect=msg.dialect,
        output=msg.output,
        conversation_id=conversation_id,
    )
    db.add(db_msg)
    db.commit()
    db.refresh(db_msg)



    return db_msg


@router.get("/conversation/{conversation_id}", response_model=List[MessageOut])
def get_messages_by_conversation(
    conversation_id: str,
    db: Session = Depends(get_db)
):
    """Get all messages (Q&A pair) by conversation_id"""
    messages = (
        db.query(MessageModel)
        .filter(MessageModel.conversation_id == conversation_id)
        .order_by(MessageModel.created_at.asc())
        .all()
    )
    
    if not messages:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    return messages

