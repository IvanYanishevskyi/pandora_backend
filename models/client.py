from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from models.base import Base


class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, unique=True)
    contact_email = Column(String(255), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    organization_id = Column(Integer, ForeignKey("organizations.id"), default=1)

    # Relationships
    organization = relationship("Organization", back_populates="clients")
    users = relationship("User", back_populates="client")
    databases = relationship("ClientDatabase", back_populates="client")
    tenant_registry = relationship("TenantRegistry", back_populates="client", uselist=False)
