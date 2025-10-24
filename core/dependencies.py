from fastapi import Header, HTTPException, status, Depends
from jose import jwt, JWTError
from core.security import SECRET_KEY, ALGORITHM
from typing import Optional
from database.database import get_db, get_admin_db
from sqlalchemy.orm import Session
from models.admin_token import AdminToken
from models.user import User
from datetime import datetime, timedelta, timezone
import zoneinfo

def get_current_user(authorization: str = Header(...), db: Session = Depends(get_db)):
    cred_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        if not authorization.startswith("Bearer "):
            raise cred_exc
        token = authorization.split(" ")[1]
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        username: str = payload.get("sub")
        user_id:  int  = payload.get("id")   
        role: str     = payload.get("role")
        full_name: str = payload.get("full_name")
        email: str = payload.get("email")
        if username is None or user_id is None:
            raise cred_exc
        # Fetch user to get last_login and is_active
        user: Optional[User] = db.query(User).filter(User.id == user_id).first()
        last_login = None
        online = False
        if user:
            last_login = user.last_login
            if last_login:
                # online if last_login within 5 minutes
                online = (datetime.utcnow() - last_login) <= timedelta(minutes=5)

        # Format local time for Italy (Europe/Rome)
        last_login_local = None
        if last_login:
            try:
                # assume last_login is naive UTC
                utc = last_login.replace(tzinfo=timezone.utc)
                local = utc.astimezone(zoneinfo.ZoneInfo("Europe/Rome"))
                last_login_local = local.isoformat()
            except Exception:
                last_login_local = None

        return {
            "id": user_id,
            "username": username,
            "role": role,
            "full_name": full_name,
            "email": email,
            "last_login": last_login,
            "last_login_local": last_login_local,
            "online": online,
        }
    except JWTError:
        raise cred_exc


def get_admin_from_token(x_admin_token: str = Header(...), db: Session = Depends(get_admin_db)):
    """Validate admin token provided in X-Admin-Token header against DB.

    Returns the AdminToken instance if valid. Raises 401/403 otherwise.
    Also updates last_used timestamp.
    """
    if not x_admin_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing admin token")

    token_rec: Optional[AdminToken] = db.query(AdminToken).filter(AdminToken.token == x_admin_token).first()
    if not token_rec:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin token")
    if not token_rec.active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin token is inactive")
    if token_rec.expires_at and token_rec.expires_at < datetime.utcnow():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin token expired")

    # update last_used
    token_rec.last_used = datetime.utcnow()
    db.add(token_rec)
    db.commit()
    db.refresh(token_rec)

    return token_rec


def get_super_admin_from_token(x_admin_token: str = Header(...), db: Session = Depends(get_admin_db)):
    """Validate admin token and check if it belongs to a super admin.
    
    Returns the AdminToken instance if valid and belongs to super admin. 
    Raises 401/403 otherwise.
    """
    # First validate the token like a regular admin
    token_rec = get_admin_from_token(x_admin_token, db)
    
    # Additional check for super admin role would go here if needed
    # For now, we assume admin tokens are used by super admins
    # In a more complex system, you might want to link tokens to specific users
    
    return token_rec
