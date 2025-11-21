from sqlalchemy import Column, Integer, String, Boolean, TIMESTAMP, ForeignKey, text
from sqlalchemy.orm import relationship
from models.base import Base


class TenantRegistry(Base):

    __tablename__ = "tenant_registry"
    
    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, unique=True)
    core_url = Column(String(255), nullable=False, comment="URL Core IP")
    is_active = Column(Boolean, default=True)
    health_check_url = Column(String(512), default="/health")
    created_at = Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"))
    
    client = relationship("Client", back_populates="tenant_registry")
