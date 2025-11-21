from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from models.base import Base


class ClientDatabase(Base):
    __tablename__ = "client_databases"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    db_host = Column(String(255), default="localhost")
    db_port = Column(Integer, default=3306)
    db_user = Column(String(255), nullable=True)
    db_password = Column(String(255), nullable=True)
    db_name = Column(String(255), nullable=True)
    
    created_at = Column(DateTime, server_default=func.now())

    # Relationship
    client = relationship("Client", back_populates="databases")
