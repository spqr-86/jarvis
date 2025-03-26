from datetime import datetime
from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, Float, Enum
from sqlalchemy.orm import relationship
import enum

from jarvis.storage.database import Base
from jarvis.core.models.shopping import ItemCategory, ItemPriority


class ItemCategoryEnum(enum.Enum):
    GROCERY = "grocery"
    FRUITS = "fruits"
    VEGETABLES = "vegetables"
    DAIRY = "dairy"
    MEAT = "meat"
    BAKERY = "bakery"
    FROZEN = "frozen"
    HOUSEHOLD = "household"
    PERSONAL_CARE = "personal_care"
    OTHER = "other"


class ItemPriorityEnum(enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class ShoppingList(Base):
    __tablename__ = "shopping_lists"

    id = Column(String, primary_key=True)
    name = Column(String)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    family_id = Column(String, ForeignKey("families.id"))
    family = relationship("Family", back_populates="shopping_lists")
    
    created_by = Column(String, ForeignKey("users.id"))
    creator = relationship("User")
    
    items = relationship("ShoppingItem", back_populates="shopping_list")
    
    # Metadata
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, nullable=True, onupdate=datetime.now)


class ShoppingItem(Base):
    __tablename__ = "shopping_items"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    quantity = Column(Float, default=1.0)
    unit = Column(String, nullable=True)
    category = Column(Enum(ItemCategoryEnum), default=ItemCategoryEnum.OTHER)
    priority = Column(Enum(ItemPriorityEnum), default=ItemPriorityEnum.MEDIUM)
    is_purchased = Column(Boolean, default=False)
    notes = Column(String, nullable=True)
    
    # Relationships
    shopping_list_id = Column(String, ForeignKey("shopping_lists.id"))
    shopping_list = relationship("ShoppingList", back_populates="items")
    
    assigned_to = Column(String, ForeignKey("users.id"), nullable=True)
    assignee = relationship("User")
    
    # Metadata
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, nullable=True, onupdate=datetime.now)