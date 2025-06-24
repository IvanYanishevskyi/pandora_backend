from sqlalchemy import Column, Integer, String, Boolean, Enum, TIMESTAMP, func
from sqlalchemy.orm import relationship
from models.base import Base
from models.chat import Chat

import enum

class UserRole(enum.Enum):
    admin = "admin"
    user = "user"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(150), unique=True, nullable=False)
    email = Column(String(255), unique=True)
    full_name = Column(String(255))
    password_hash = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), default=UserRole.user)
    is_active = Column(Boolean, default=True)
    last_login = Column(TIMESTAMP, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    # 💡 Указываем строкой "Chat"
    chats = relationship("Chat", back_populates="user")
