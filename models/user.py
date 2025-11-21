from sqlalchemy import Column, Integer, String, Boolean, Enum, TIMESTAMP, ForeignKey, func
from sqlalchemy.orm import relationship
from models.base import Base
import enum

class UserRole(enum.Enum):
    super_admin = "super_admin"
    admin = "admin"
    user = "user"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), default=1)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True)
    username = Column(String(150), unique=True, nullable=False)
    email = Column(String(255), unique=True)
    full_name = Column(String(255))
    password_hash = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), default=UserRole.user)
    is_active = Column(Boolean, default=False)
    last_login = Column(TIMESTAMP, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    # Relationships
    organization = relationship("Organization")
    client = relationship("Client", back_populates="users")
    chats = relationship("Chat", back_populates="user")
    favorites = relationship("FavoriteQuestion", back_populates="user", cascade="all, delete")
