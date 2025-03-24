"""
Модели данных для функциональности списка покупок.
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
from uuid import UUID

from pydantic import BaseModel, Field


class ItemCategory(str, Enum):
    """Категории товаров в списке покупок."""
    
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
    
    @classmethod
    def get_ru_name(cls, category: "ItemCategory") -> str:
        """Возвращает русское название категории."""
        ru_names = {
            cls.GROCERY: "Бакалея",
            cls.FRUITS: "Фрукты",
            cls.VEGETABLES: "Овощи",
            cls.DAIRY: "Молочные продукты",
            cls.MEAT: "Мясо и рыба",
            cls.BAKERY: "Хлебобулочные изделия",
            cls.FROZEN: "Замороженные продукты",
            cls.HOUSEHOLD: "Товары для дома",
            cls.PERSONAL_CARE: "Средства личной гигиены",
            cls.OTHER: "Другое"
        }
        return ru_names.get(category, "Другое")


class ItemPriority(str, Enum):
    """Приоритет товара в списке покупок."""
    
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"
    
    @classmethod
    def get_ru_name(cls, priority: "ItemPriority") -> str:
        """Возвращает русское название приоритета."""
        ru_names = {
            cls.LOW: "Низкий",
            cls.MEDIUM: "Средний",
            cls.HIGH: "Высокий",
            cls.URGENT: "Срочно"
        }
        return ru_names.get(priority, "Средний")


class ShoppingItem(BaseModel):
    """Модель элемента списка покупок."""
    
    id: str = Field(description="Уникальный идентификатор товара")
    name: str = Field(description="Название товара")
    quantity: float = Field(1.0, description="Количество")
    unit: Optional[str] = Field(None, description="Единица измерения (кг, шт, л и т.д.)")
    category: ItemCategory = Field(ItemCategory.OTHER, description="Категория товара")
    priority: ItemPriority = Field(default=ItemPriority.MEDIUM, description="Приоритет товара")
    assigned_to: Optional[str] = Field(None, description="ID члена семьи, ответственного за покупку")
    is_purchased: bool = Field(False, description="Статус покупки")
    notes: Optional[str] = Field(None, description="Дополнительные заметки")
    created_at: datetime = Field(default_factory=datetime.now, description="Время создания")
    updated_at: Optional[datetime] = Field(None, description="Время последнего обновления")
    
    def mark_as_purchased(self, by_user_id: Optional[str] = None) -> None:
        """
        Отмечает товар как купленный.
        
        Args:
            by_user_id: ID пользователя, совершившего покупку
        """
        self.is_purchased = True
        self.updated_at = datetime.now()
        if by_user_id and not self.assigned_to:
            self.assigned_to = by_user_id
    
    def update_quantity(self, new_quantity: float) -> None:
        """
        Обновляет количество товара.
        
        Args:
            new_quantity: Новое количество
        """
        self.quantity = new_quantity
        self.updated_at = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразует модель в словарь для хранения."""
        return {
            "id": self.id,
            "name": self.name,
            "quantity": self.quantity,
            "unit": self.unit,
            "category": self.category.value,
            "priority": self.priority.value,
            "assigned_to": self.assigned_to,
            "is_purchased": self.is_purchased,
            "notes": self.notes,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class ShoppingList(BaseModel):
    """Модель списка покупок."""
    
    id: str = Field(description="Уникальный идентификатор списка")
    name: str = Field(description="Название списка")
    family_id: str = Field(description="ID семьи, которой принадлежит список")
    items: List[ShoppingItem] = Field(default_factory=list, description="Элементы списка")
    is_active: bool = Field(True, description="Активен ли список")
    created_at: datetime = Field(default_factory=datetime.now, description="Время создания")
    updated_at: Optional[datetime] = Field(None, description="Время последнего обновления")
    created_by: Optional[str] = Field(None, description="ID пользователя, создавшего список")
    
    def add_item(self, item: ShoppingItem) -> None:
        """
        Добавляет товар в список.
        
        Args:
            item: Товар для добавления
        """
        self.items.append(item)
        self.updated_at = datetime.now()
    
    def remove_item(self, item_id: str) -> bool:
        """
        Удаляет товар из списка по его ID.
        
        Args:
            item_id: ID товара для удаления
            
        Returns:
            True, если товар был удален, иначе False
        """
        initial_length = len(self.items)
        self.items = [item for item in self.items if item.id != item_id]
        
        if len(self.items) < initial_length:
            self.updated_at = datetime.now()
            return True
        return False
    
    def get_item(self, item_id: str) -> Optional[ShoppingItem]:
        """
        Получает товар по его ID.
        
        Args:
            item_id: ID товара
            
        Returns:
            Товар или None, если товар не найден
        """
        for item in self.items:
            if item.id == item_id:
                return item
        return None
    
    def update_item(self, item_id: str, **kwargs) -> bool:
        """
        Обновляет товар по его ID.
        
        Args:
            item_id: ID товара для обновления
            **kwargs: Атрибуты для обновления
            
        Returns:
            True, если товар был обновлен, иначе False
        """
        item = self.get_item(item_id)
        if not item:
            return False
        
        for key, value in kwargs.items():
            if hasattr(item, key):
                setattr(item, key, value)
        
        item.updated_at = datetime.now()
        self.updated_at = datetime.now()
        return True
    
    def get_unpurchased_items(self) -> List[ShoppingItem]:
        """
        Возвращает список непокупленных товаров.
        
        Returns:
            Список непокупленных товаров
        """
        return [item for item in self.items if not item.is_purchased]
    
    def get_purchased_items(self) -> List[ShoppingItem]:
        """
        Возвращает список купленных товаров.
        
        Returns:
            Список купленных товаров
        """
        return [item for item in self.items if item.is_purchased]
    
    def get_items_by_category(self, category: ItemCategory) -> List[ShoppingItem]:
        """
        Возвращает товары по категории.
        
        Args:
            category: Категория товаров
            
        Returns:
            Список товаров выбранной категории
        """
        return [item for item in self.items if item.category == category]
    
    def sort_by_category(self) -> Dict[ItemCategory, List[ShoppingItem]]:
        """
        Сортирует товары по категориям.
        
        Returns:
            Словарь с категориями и списками товаров
        """
        result = {category: [] for category in ItemCategory}
        
        for item in self.items:
            result[item.category].append(item)
        
        # Удаляем пустые категории
        return {k: v for k, v in result.items() if v}
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразует модель в словарь для хранения."""
        return {
            "id": self.id,
            "name": self.name,
            "family_id": self.family_id,
            "items": [item.to_dict() for item in self.items],
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "created_by": self.created_by
        }
    
    def mark_all_as_purchased(self, by_user_id: Optional[str] = None) -> None:
        """
        Отмечает все товары как купленные.
        
        Args:
            by_user_id: ID пользователя, совершившего покупки
        """
        for item in self.items:
            if not item.is_purchased:
                item.mark_as_purchased(by_user_id)
        
        self.updated_at = datetime.now()
    
    def clear_purchased_items(self) -> int:
        """
        Удаляет все купленные товары из списка.
        
        Returns:
            Количество удаленных товаров
        """
        purchased_count = len(self.get_purchased_items())
        self.items = self.get_unpurchased_items()
        
        if purchased_count > 0:
            self.updated_at = datetime.now()
        
        return purchased_count
    
    @property
    def is_empty(self) -> bool:
        """Проверяет, пуст ли список."""
        return len(self.items) == 0
    
    @property
    def is_completed(self) -> bool:
        """Проверяет, все ли товары куплены."""
        return all(item.is_purchased for item in self.items) and not self.is_empty
    
    @property
    def progress(self) -> float:
        """
        Возвращает прогресс выполнения списка (процент купленных товаров).
        
        Returns:
            Прогресс от 0.0 до 1.0
        """
        if self.is_empty:
            return 1.0
        
        purchased = len(self.get_purchased_items())
        total = len(self.items)
        
        return purchased / total