from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from models.base import Base

class MessageRating(Base):
    __tablename__ = "message_ratings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    username = Column(String(150), nullable=False) 
    database_id = Column(Integer, ForeignKey("client_databases.id"), nullable=False)
    database_name = Column(String(255), nullable=False) 
    is_valid = Column(Boolean, nullable=False) 
    messages = Column(JSON, nullable=False) 
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User")
    database = relationship("ClientDatabase")
