from datetime import datetime
from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship

from jarvis.storage.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True)
    telegram_id = Column(String, unique=True, index=True)
    username = Column(String, index=True)
    first_name = Column(String)
    last_name = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, nullable=True, onupdate=datetime.now)
    
    # Relationship
    family_id = Column(String, ForeignKey("families.id"), nullable=True)
    family = relationship("Family", foreign_keys=[family_id], back_populates="members")
    
    # Created families
    created_families = relationship("Family", back_populates="creator", 
                                   foreign_keys="[Family.created_by]")
    
    transactions = relationship("Transaction", back_populates="user")


class Family(Base):
    __tablename__ = "families"

    id = Column(String, primary_key=True)
    name = Column(String)
    created_by = Column(String, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, nullable=True, onupdate=datetime.now)
    
    # Relationships
    members = relationship("User", foreign_keys="[User.family_id]", back_populates="family")
    creator = relationship("User", foreign_keys=[created_by], back_populates="created_families")
    
    # Other relationships - using strings to avoid circular imports
    budgets = relationship("Budget", back_populates="family")
    shopping_lists = relationship("ShoppingList", back_populates="family")
    financial_goals = relationship("FinancialGoal", back_populates="family")