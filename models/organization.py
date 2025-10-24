from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from models.base import Base


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    is_root = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    clients = relationship("Client", back_populates="organization")
    users = relationship("User", back_populates="organization")
