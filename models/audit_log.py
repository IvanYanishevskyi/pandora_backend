from sqlalchemy import Column, Integer, String, Enum, Text, DateTime, JSON
from models.base import Base


class AuditLog(Base):

    __tablename__ = "audit_log"
    
    id = Column(Integer, primary_key=True, index=True)
    
    user_id = Column(Integer, nullable=True, index=True)  
    user_role = Column(Enum('super_admin', 'admin', 'user'), nullable=True)
    
    tenant_id = Column(String(255), nullable=True, index=True)
    
    action = Column(String(255), nullable=True, index=True)
    request_type = Column(Enum('auth', 'admin', 'sql_proxy'), nullable=True, default='sql_proxy', index=True)
    
    target_type = Column(String(100), nullable=True)
    target_id = Column(Integer, nullable=True)
    
    database_name = Column(String(255), nullable=True)
    
    status = Column(String(50), nullable=True, index=True) 
    duration_ms = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    
    details = Column(JSON, nullable=True) 
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    
    created_at = Column(DateTime, nullable=True, index=True)
