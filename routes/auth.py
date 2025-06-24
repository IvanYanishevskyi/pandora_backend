# routes/auth.py
from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from core.dependencies import get_current_user
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from models.user import User
from core.security import verify_password, create_access_token, get_password_hash
from database.database import get_db
from pydantic import BaseModel

router = APIRouter()

class LoginRequest(BaseModel):
    username: str
    password: str
class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str

@router.post("/login")
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user: User | None = (
        db.query(User).filter(User.username == body.username).first()
    )
 
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    token_data = {
        "sub": user.username,
        "id":  user.id,
        "role": user.role.value if hasattr(user.role, "value") else user.role,
        "full_name": user.full_name,
        "email": user.email,
          }
    print("⚠️User", user.username, "logged in")
    return {
        "access_token": create_access_token(token_data),
        "token_type": "bearer",
    }
@router.get("/me")
def get_me(current_user=Depends(get_current_user)):
    return current_user
@router.post("/change-password", status_code=status.HTTP_200_OK)
def change_password(
    body: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["id"]
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if not verify_password(body.old_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Incorrect current password")

    user.password_hash = get_password_hash(body.new_password)
    db.commit()
    return {"message": "Password updated successfully"}
