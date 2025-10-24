from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

MYSQL_USER = "root"
MYSQL_PASSWORD = ""
MYSQL_HOST = "localhost"
MYSQL_PORT = "3306"
MYSQL_DB = "interno"

DATABASE_URL = (
    f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}"
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db() -> Session: # type: ignore
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Additional admin database connection (admin tokens live in a separate DB)
MYSQL_DB_ADMIN = "interno"

DATABASE_URL_ADMIN = (
    f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB_ADMIN}"
)

engine_admin = create_engine(DATABASE_URL_ADMIN, pool_pre_ping=True)
SessionLocalAdmin = sessionmaker(autocommit=False, autoflush=False, bind=engine_admin)

def get_admin_db() -> Session:  # type: ignore
    db = SessionLocalAdmin()
    try:
        yield db
    finally:
        db.close()
