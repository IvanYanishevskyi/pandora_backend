from sqlalchemy import Column, BigInteger, String, Text, Enum, JSON, Integer, DateTime, Boolean, ForeignKey, func
from sqlalchemy.orm import relationship
from models.base import Base
import enum

class DialectEnum(str, enum.Enum):
    mysql = "mysql"
    postgres = "postgres"

class FavoriteQuestion(Base):
    __tablename__ = "favorite_questions"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    title = Column(String(255), nullable=False)
    question_text = Column(Text, nullable=False)
    sql_correct = Column(Text, nullable=False)
    dialect = Column(Enum(DialectEnum), default=DialectEnum.mysql)
    tags = Column(JSON, nullable=True)
    is_pinned = Column(Boolean, default=False)
    usage_count = Column(Integer, default=0)
    last_used_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="favorites")
