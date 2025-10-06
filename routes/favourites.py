from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime

from core.dependencies import get_current_user
from database.database import get_db
from models.favourites import FavoriteQuestion
from schemas.favourites import FavoriteCreate, FavoriteUpdate, FavoriteOut

router = APIRouter(prefix="/favorites", tags=["favorites"])

@router.get("/me", response_model=List[FavoriteOut])
def get_my_favorites(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    user_id = current_user["id"]
    return db.query(FavoriteQuestion).filter(FavoriteQuestion.user_id == user_id).all()


@router.post("/", response_model=FavoriteOut)
def add_favorite(
    fav: FavoriteCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    new_fav = FavoriteQuestion(
        **fav.dict(exclude={"user_id"}),
        user_id=current_user["id"]
    )
    print("Adding favorite:", new_fav)
    db.add(new_fav)
    db.commit()
    db.refresh(new_fav)
    return new_fav
@router.delete("/{favorite_id}")
def delete_favorite(
    favorite_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    fav = (
        db.query(FavoriteQuestion)
        .filter(
            FavoriteQuestion.id == favorite_id,
            FavoriteQuestion.user_id == current_user["id"],
        )
        .first()
    )
    if not fav:
        raise HTTPException(status_code=404, detail="Favorite not found")

    db.delete(fav)
    db.commit()

    # Можно просто ничего не возвращать, FastAPI сам сформирует 204 без тела
    return {"message": "Deleted successfully"}
