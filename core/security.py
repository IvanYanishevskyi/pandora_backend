
from passlib.context import CryptContext
from jose import jwt
from datetime import datetime, timedelta

SECRET_KEY = "YJNdqRkQdLj8ZHsxzkD_KG8sXae-8fCsoN7V3xmcN90"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password: str) -> str:
    """
    Genera l'hash di una password in chiaro.
    """
    return pwd_context.hash(password)

hash_password = get_password_hash

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifica che la password in chiaro corrisponda all'hash.
    """
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: timedelta = None) -> str:
    """
    Crea un JWT contenente i dati forniti e la data di scadenza.
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
