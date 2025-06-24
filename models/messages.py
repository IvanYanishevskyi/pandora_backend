from datetime import datetime
from sqlalchemy import Column, Integer, ForeignKey, Enum, Text, JSON, DateTime
from sqlalchemy.orm import relationship
from models.base import Base



class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(Integer, ForeignKey("chats.id"), nullable=False)
    role = Column(Enum("user", "bot", name="message_roles"), nullable=False)
    content = Column(Text, nullable=False)
    output = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    chat = relationship("Chat", back_populates="messages")
