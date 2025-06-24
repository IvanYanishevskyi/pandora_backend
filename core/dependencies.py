from fastapi import Header, HTTPException, status
from jose import jwt, JWTError
from core.security import SECRET_KEY, ALGORITHM

def get_current_user(authorization: str = Header(...)):
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

        return {"id": user_id, "username": username, "role": role, "full_name": full_name, "email": email}
    except JWTError:
        raise cred_exc
