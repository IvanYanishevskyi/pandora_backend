from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, func
from models.base import Base


class AccessAudit(Base):
    __tablename__ = 'access_audit'

    id = Column(Integer, primary_key=True)
    actor_user_id = Column(Integer, nullable=True)
    actor_role = Column(String(64), nullable=True)
    admin_token = Column(String(128), nullable=True)
    action = Column(String(128), nullable=False)
    target_type = Column(String(64), nullable=True)
    target_id = Column(Integer, nullable=True)
    details = Column(Text, nullable=True)
    success = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
