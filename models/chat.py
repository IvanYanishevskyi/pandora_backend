from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from models.base import Base
class Chat(Base):
    __tablename__ = "chats"

    id          = Column(Integer, primary_key=True, index=True)
    external_id = Column(String(36), unique=True, nullable=False)   
    db_id       = Column(String(64), default="self")               

    user_id     = Column(Integer, ForeignKey("users.id"), nullable=False)
    title       = Column(String(255))
    created_at  = Column(DateTime, default=datetime.utcnow)

    user      = relationship("User", back_populates="chats")
    messages  = relationship("Message", back_populates="chat",
                              cascade="all, delete-orphan")

from models.messages import Message  