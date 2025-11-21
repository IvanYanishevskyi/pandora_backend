from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
import os

# Database configuration from environment variables
MYSQL_USER = os.getenv("MYSQL_USER", "api_user")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD")
if not MYSQL_PASSWORD:
    raise ValueError("MYSQL_PASSWORD environment variable is not set!")

MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT = os.getenv("MYSQL_PORT", "3306")
MYSQL_DB = os.getenv("MYSQL_DB", "interno")

DATABASE_URL = (
    f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}"
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db() -> Session: 
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Additional admin database connection (admin tokens live in a separate DB)
MYSQL_DB_ADMIN = os.getenv("MYSQL_DB_ADMIN", "pandora_api")

DATABASE_URL_ADMIN = (
    f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB_ADMIN}"
)

engine_admin = create_engine(DATABASE_URL_ADMIN, pool_pre_ping=True)
SessionLocalAdmin = sessionmaker(autocommit=False, autoflush=False, bind=engine_admin)

def get_admin_db() -> Session: 
    db = SessionLocalAdmin()
    try:
        yield db
    finally:
        db.close()
