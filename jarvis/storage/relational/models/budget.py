from decimal import Decimal
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Numeric, ForeignKey, Boolean, Enum
from sqlalchemy.orm import relationship
import enum

from jarvis.storage.database import Base
from jarvis.core.models.budget import BudgetCategory, TransactionType, GoalPriority, RecurringFrequency


class TransactionTypeEnum(enum.Enum):
    INCOME = "income"
    EXPENSE = "expense"


class BudgetCategoryEnum(enum.Enum):
    FOOD = "food"
    HOUSING = "housing"
    TRANSPORT = "transport"
    UTILITIES = "utilities"
    ENTERTAINMENT = "entertainment"
    HEALTHCARE = "healthcare"
    EDUCATION = "education"
    SHOPPING = "shopping" 
    SAVINGS = "savings"
    INCOME = "income"
    OTHER = "other"


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(String, primary_key=True)
    amount = Column(Numeric(precision=10, scale=2), nullable=False)
    currency = Column(String, default="RUB")
    category = Column(Enum(BudgetCategoryEnum), nullable=False)
    transaction_type = Column(Enum(TransactionTypeEnum), nullable=False)
    description = Column(String)
    date = Column(DateTime, default=datetime.now)
    
    # Relationships
    user_id = Column(String, ForeignKey("users.id"))
    user = relationship("User", back_populates="transactions")
    
    family_id = Column(String, ForeignKey("families.id"))
    family = relationship("Family")
    
    budget_id = Column(String, ForeignKey("budgets.id"), nullable=True)
    budget = relationship("Budget", back_populates="transactions")
    
    # Recurring information
    is_recurring = Column(Boolean, default=False)
    recurring_frequency = Column(String, nullable=True)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, nullable=True, onupdate=datetime.now)


class Budget(Base):
    __tablename__ = "budgets"

    id = Column(String, primary_key=True)
    name = Column(String)
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    currency = Column(String, default="RUB")
    income_plan = Column(Numeric(precision=10, scale=2), default=0)
    income_actual = Column(Numeric(precision=10, scale=2), default=0)
    
    # Relationships
    family_id = Column(String, ForeignKey("families.id"))
    family = relationship("Family", back_populates="budgets")
    
    created_by = Column(String, ForeignKey("users.id"))
    creator = relationship("User")
    
    transactions = relationship("Transaction", back_populates="budget")
    category_budgets = relationship("CategoryBudget", back_populates="budget")
    
    # Metadata
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, nullable=True, onupdate=datetime.now)


class CategoryBudget(Base):
    __tablename__ = "category_budgets"

    id = Column(String, primary_key=True)
    category = Column(Enum(BudgetCategoryEnum), nullable=False)
    limit = Column(Numeric(precision=10, scale=2), nullable=False)
    spent = Column(Numeric(precision=10, scale=2), default=0)
    currency = Column(String, default="RUB")
    
    # Relationships
    budget_id = Column(String, ForeignKey("budgets.id"))
    budget = relationship("Budget", back_populates="category_budgets")