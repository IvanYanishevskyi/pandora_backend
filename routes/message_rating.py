from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from database.database import get_db
from models.message_rating import MessageRating
from models.user import User
from models.client_database import ClientDatabase
from schemas.message_rating import (
    MessageRatingCreate,
    MessageRatingResponse,
    MessageRatingListResponse
)
from core.dependencies import get_current_user
from typing import List, Optional
from datetime import datetime

router = APIRouter(prefix="/message-ratings", tags=["Message Ratings"])


@router.post("", response_model=MessageRatingResponse, status_code=201)
def create_message_rating(
    rating_data: MessageRatingCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):

    database = db.query(ClientDatabase).filter(
        ClientDatabase.id == rating_data.database_id
    ).first()
    
    if not database:
        raise HTTPException(status_code=404, detail="Database not found")
    messages_json = []
    for msg in rating_data.messages:
        if msg.role == "assistant" and isinstance(msg.content, dict):
            messages_json.append({
                "role": msg.role,
                "content": {
                    "sql": msg.content.get("sql", ""),
                    "explanation": msg.content.get("explanation", "")
                }
            })
        else:
            messages_json.append({
                "role": msg.role,
                "content": str(msg.content)
            })
    
    rating = MessageRating(
        user_id=current_user["id"],
        username=current_user["username"],
        database_id=rating_data.database_id,
        database_name=database.db_name,
        is_valid=rating_data.is_valid,
        messages=messages_json,
        created_at=datetime.utcnow()
    )
    
    db.add(rating)
    db.commit()
    db.refresh(rating)
    
    return rating


@router.get("", response_model=MessageRatingListResponse)
def get_message_ratings(
    database_id: Optional[int] = Query(None),
    is_valid: Optional[bool] = Query(None),
    username: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    query = db.query(MessageRating)
    
    if database_id:
        query = query.filter(MessageRating.database_id == database_id)
    if is_valid is not None:
        query = query.filter(MessageRating.is_valid == is_valid)
    if username:
        query = query.filter(MessageRating.username == username)
    
    total = query.count()
    
    ratings = query.order_by(MessageRating.created_at.desc()).offset(skip).limit(limit).all()
    
    return MessageRatingListResponse(ratings=ratings, total=total)


@router.get("/{rating_id}", response_model=MessageRatingResponse)
def get_message_rating(
    rating_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
   
    rating = db.query(MessageRating).filter(MessageRating.id == rating_id).first()
    
    if not rating:
        raise HTTPException(status_code=404, detail="Rating not found")
    
    return rating


@router.delete("/{rating_id}", status_code=204)
def delete_message_rating(
    rating_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
   
    rating = db.query(MessageRating).filter(MessageRating.id == rating_id).first()
    
    if not rating:
        raise HTTPException(status_code=404, detail="Rating not found")
    
    if rating.user_id != current_user["id"] and current_user["role"] not in ["super_admin", "admin"]:
        raise HTTPException(status_code=403, detail="Not authorized to delete this rating")
    
    db.delete(rating)
    db.commit()
