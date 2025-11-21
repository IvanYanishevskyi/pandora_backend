# routes/auth.py
from fastapi import APIRouter, Depends
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from core.dependencies import get_current_user
from sqlalchemy import or_
from models.user import User, UserRole
from models.admin_token import AdminToken
from core.security import verify_password, create_access_token, get_password_hash
from database.database import get_db, get_admin_db
import uuid
from pydantic import BaseModel
from datetime import datetime

router = APIRouter()

class LoginRequest(BaseModel):
    username: str
    password: str
class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str

@router.post("/login")
def login(body: LoginRequest, db: Session = Depends(get_db), admin_db: Session = Depends(get_admin_db)):
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
    # update last_login
    try:
        user.last_login = datetime.utcnow()
        # mark user active on successful login
        user.is_active = True
        db.add(user)
        db.commit()
        db.refresh(user)
    except Exception:
        # don't block login if update fails
        db.rollback()

    print("User", user.username, "logged in")
    # If user is admin or super_admin, return or create an admin token from admin DB so frontend can store it
    admin_token_value = None
    role_str = token_data.get("role")
    if role_str in ["admin", "super_admin"]:
        try:
            # try to find an existing active token for this user
            token_rec = (
                admin_db.query(AdminToken)
                .filter(AdminToken.active == True)
                .filter(
                    or_(
                        AdminToken.created_by == user.id,
                        AdminToken.created_by == user.username,
                        AdminToken.created_by == str(user.id),
                    )
                )
                .first()
            )

            if token_rec:
                # if created_by stored as non-numeric (e.g. 'admin'), update to numeric id for future matches
                try:
                    if token_rec.created_by != user.id:
                        token_rec.created_by = user.id
                        admin_db.add(token_rec)
                        admin_db.commit()
                        admin_db.refresh(token_rec)
                except Exception:
                    try:
                        admin_db.rollback()
                    except Exception:
                        pass
                admin_token_value = token_rec.token
            else:
                # create a new token
                admin_token_value = str(uuid.uuid4())
                new_token = AdminToken(
                    token=admin_token_value,
                    name=f"auto-{user.username}",
                    description="Auto-created admin token on login",
                    active=True,
                    created_by=user.id,
                )
                admin_db.add(new_token)
                admin_db.commit()
                admin_db.refresh(new_token)
        except Exception:
            # if admin DB write fails, continue without admin token
            try:
                admin_db.rollback()
            except Exception:
                pass

    response = {
        "access_token": create_access_token(token_data),
        "token_type": "bearer",
    }
    if admin_token_value:
        response["admin_token"] = admin_token_value
    return response
@router.get("/me")
def get_me(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        user_id = current_user.get("id")
        if user_id:
            user = db.query(User).filter(User.id == user_id).first()
            if user:
                user.last_login = datetime.utcnow()
                db.add(user)
                db.commit()
                db.refresh(user)
                current_user["last_login"] = user.last_login
    except Exception:
        db.rollback()

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


@router.post("/logout", status_code=status.HTTP_200_OK)
def logout(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):

    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    try:
        user.is_active = False
        db.add(user)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"message": "Logged out"}


@router.get("/database-access/me")
def auth_get_my_database_access(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
 
    from models.user_database_access import UserDatabaseAccess
    from models.client_database import ClientDatabase

    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    # Load full user object to access client_id/organization_id/role
    user_obj = db.query(User).filter(User.id == user_id).first()
    if not user_obj:
        raise HTTPException(status_code=404, detail="User not found")

    result = []
    # super_admin sees all databases
    if user_obj.role == user_obj.role.__class__.super_admin:
        databases = db.query(ClientDatabase).all()
        for database in databases:
            result.append({
                "id": None,
                "user_id": user_id,
                "database_id": database.id,
                "database_name": database.name,
                "can_read": True,
                "can_write": True,
                "created_at": None,
            })
        return result

    # For admin/user: return their explicit accesses, admin filtered by organization
    accesses = db.query(UserDatabaseAccess).filter(UserDatabaseAccess.user_id == user_id).all()
    for access in accesses:
        database = db.query(ClientDatabase).get(access.database_id)
        if not database:
            continue
        # if requester is admin, ensure database belongs to same organization
        if user_obj.role == UserRole.admin:
            if database.client and database.client.organization_id != user_obj.organization_id:
                continue

        result.append({
            "id": access.id,
            "user_id": access.user_id,
            "database_id": access.database_id,
            "database_name": database.name,
            "can_read": access.can_read,
            "can_write": access.can_write,
            "created_at": access.created_at.isoformat() if access.created_at else None,
        })

    return result
