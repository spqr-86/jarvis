from datetime import datetime
from sqlalchemy import Column, String, DateTime, Numeric, ForeignKey, Enum
from sqlalchemy.orm import relationship
import enum

from jarvis.storage.database import Base

class GoalPriorityEnum(enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class FinancialGoal(Base):
    __tablename__ = "financial_goals"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    target_amount = Column(Numeric(precision=10, scale=2), nullable=False)
    current_amount = Column(Numeric(precision=10, scale=2), default=0)
    currency = Column(String, default="RUB")
    start_date = Column(DateTime, default=datetime.now)
    deadline = Column(DateTime, nullable=True)
    priority = Column(Enum(GoalPriorityEnum), default=GoalPriorityEnum.MEDIUM)
    notes = Column(String, nullable=True)
    
    # Relationships
    family_id = Column(String, ForeignKey("families.id"))
    family = relationship("Family", back_populates="financial_goals")
    
    created_by = Column(String, ForeignKey("users.id"))
    creator = relationship("User")
    
    # Metadata
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, nullable=True, onupdate=datetime.now)