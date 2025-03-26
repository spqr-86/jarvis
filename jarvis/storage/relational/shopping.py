"""
Репозиторий для работы со списками покупок в реляционной базе данных.
"""

import logging
from datetime import datetime
from uuid import uuid4

from sqlalchemy.orm import Session
from sqlalchemy import and_

from typing import List, Optional, Dict, Any, Tuple

from jarvis.storage.database import get_db_session
from jarvis.storage.relational.models.shopping import ShoppingList, ShoppingItem, ItemCategoryEnum, ItemPriorityEnum
from jarvis.core.models.shopping import ShoppingList as ShoppingListModel
from jarvis.core.models.shopping import ShoppingItem as ShoppingItemModel
from jarvis.core.models.shopping import ItemCategory, ItemPriority

logger = logging.getLogger(__name__)


class ShoppingListRepository:
    """Репозиторий для работы со списками покупок."""
    
    def __init__(self, db: Session = None):
        """
        Initialize the repository with a database session.
        
        Args:
            db: Database session (if None, will use dependency injection)
        """
        self._db = db or next(get_db_session())

    def _to_model(self, db_list: ShoppingList) -> ShoppingListModel:
        """Convert database entity to domain model."""
        items = []
        for db_item in db_list.items:
            item = ShoppingItemModel(
                id=db_item.id,
                name=db_item.name,
                quantity=db_item.quantity,
                unit=db_item.unit,
                category=ItemCategory(db_item.category.value),
                priority=ItemPriority(db_item.priority.value),
                assigned_to=db_item.assigned_to,
                is_purchased=db_item.is_purchased,
                notes=db_item.notes,
                created_at=db_item.created_at
            )
            if db_item.updated_at:
                item.updated_at = db_item.updated_at
            items.append(item)
            
        shopping_list = ShoppingListModel(
            id=db_list.id,
            name=db_list.name,
            family_id=db_list.family_id,
            items=items,
            is_active=db_list.is_active,
            created_at=db_list.created_at,
            created_by=db_list.created_by
        )
        if db_list.updated_at:
            shopping_list.updated_at = db_list.updated_at
            
        return shopping_list
    
    async def create_list(
        self, 
        name: str, 
        family_id: str, 
        created_by: Optional[str] = None
    ) -> ShoppingListModel:
        """Create a new shopping list."""
        list_id = str(uuid4())
        
        db_list = ShoppingList(
            id=list_id,
            name=name,
            family_id=family_id,
            created_by=created_by,
            is_active=True
        )
        
        self._db.add(db_list)
        self._db.commit()
        self._db.refresh(db_list)
        
        return self._to_model(db_list)
    
    async def get_list(self, list_id: str) -> Optional[ShoppingListModel]:
        """Get a shopping list by ID."""
        db_list = self._db.query(ShoppingList).filter(ShoppingList.id == list_id).first()
        
        if not db_list:
            return None
            
        return self._to_model(db_list)
    
    async def get_active_list_for_family(self, family_id: str) -> Optional[ShoppingListModel]:
        """Get the active shopping list for a family."""
        db_list = self._db.query(ShoppingList).filter(
            and_(
                ShoppingList.family_id == family_id,
                ShoppingList.is_active == True
            )
        ).first()
        
        if not db_list:
            return None
            
        return self._to_model(db_list)


    async def get_lists_for_family(self, family_id: str) -> List[ShoppingList]:
        """
        Получает все списки покупок для семьи.
        
        Args:
            family_id: ID семьи
            
        Returns:
            Список списков покупок
        """
        return [
            shopping_list for shopping_list in self._db.values()
            if shopping_list.family_id == family_id
        ]
    
    async def add_item(
            self, 
            list_id: str, 
            name: str,
            quantity: float = 1.0,
            unit: Optional[str] = None,
            category: ItemCategory = ItemCategory.OTHER,
            priority: Optional[ItemPriority] = None,
            notes: Optional[str] = None
        ) -> Tuple[bool, Optional[ShoppingItem]]:
            """
            Добавляет товар в список покупок.
            
            Args:
                list_id: ID списка покупок
                name: Название товара
                quantity: Количество
                unit: Единица измерения
                category: Категория товара
                priority: Приоритет товара
                notes: Дополнительные заметки
                
            Returns:
                Кортеж (успех операции, созданный товар)
            """
            shopping_list = await self.get_list(list_id)
            if not shopping_list:
                logger.warning(f"Не удалось найти список покупок с ID {list_id}")
                return False, None
            
            # Устанавливаем значение по умолчанию для приоритета, если оно не указано
            if priority is None:
                priority = ItemPriority.MEDIUM
            
            item = ShoppingItem(
                id=generate_uuid(),
                name=name,
                quantity=quantity,
                unit=unit,
                category=category,
                priority=priority,
                notes=notes,
                created_at=datetime.now()
            )
            
            shopping_list.add_item(item)
            
            # Обновляем список в "базе данных"
            self._db[list_id] = shopping_list
            
            logger.info(f"Добавлен товар '{name}' в список покупок {list_id}")
            return True, item
    
    async def update_list(self, list_id: str, **kwargs) -> bool:
        """
        Обновляет список покупок.
        
        Args:
            list_id: ID списка покупок
            **kwargs: Атрибуты для обновления
            
        Returns:
            True, если список был обновлен, иначе False
        """
        shopping_list = await self.get_list(list_id)
        if not shopping_list:
            logger.warning(f"Не удалось найти список покупок с ID {list_id}")
            return False
        
        for key, value in kwargs.items():
            if hasattr(shopping_list, key) and key not in ['id', 'family_id', 'created_at', 'items']:
                setattr(shopping_list, key, value)
        
        shopping_list.updated_at = datetime.now()
        
        # Обновляем список в "базе данных"
        self._db[list_id] = shopping_list
        
        logger.info(f"Обновлен список покупок {list_id}")
        return True
    
    async def update_item(self, list_id: str, item_id: str, **kwargs) -> bool:
        """
        Обновляет товар в списке покупок.
        
        Args:
            list_id: ID списка покупок
            item_id: ID товара
            **kwargs: Атрибуты для обновления
            
        Returns:
            True, если товар был обновлен, иначе False
        """
        shopping_list = await self.get_list(list_id)
        if not shopping_list:
            logger.warning(f"Не удалось найти список покупок с ID {list_id}")
            return False
        
        success = shopping_list.update_item(item_id, **kwargs)
        
        if success:
            # Обновляем список в "базе данных"
            self._db[list_id] = shopping_list
            logger.info(f"Обновлен товар {item_id} в списке покупок {list_id}")
        else:
            logger.warning(f"Не удалось найти товар {item_id} в списке покупок {list_id}")
        
        return success
    
    async def remove_item(self, list_id: str, item_id: str) -> bool:
        """
        Удаляет товар из списка покупок.
        
        Args:
            list_id: ID списка покупок
            item_id: ID товара
            
        Returns:
            True, если товар был удален, иначе False
        """
        shopping_list = await self.get_list(list_id)
        if not shopping_list:
            logger.warning(f"Не удалось найти список покупок с ID {list_id}")
            return False
        
        success = shopping_list.remove_item(item_id)
        
        if success:
            # Обновляем список в "базе данных"
            self._db[list_id] = shopping_list
            logger.info(f"Удален товар {item_id} из списка покупок {list_id}")
        else:
            logger.warning(f"Не удалось найти товар {item_id} в списке покупок {list_id}")
        
        return success
    
    async def delete_list(self, list_id: str) -> bool:
        """
        Удаляет список покупок.
        
        Args:
            list_id: ID списка покупок
            
        Returns:
            True, если список был удален, иначе False
        """
        if list_id not in self._db:
            logger.warning(f"Не удалось найти список покупок с ID {list_id}")
            return False
        
        del self._db[list_id]
        logger.info(f"Удален список покупок {list_id}")
        return True
    
    async def mark_item_as_purchased(self, list_id: str, item_id: str, by_user_id: Optional[str] = None) -> bool:
        """
        Отмечает товар как купленный.
        
        Args:
            list_id: ID списка покупок
            item_id: ID товара
            by_user_id: ID пользователя, совершившего покупку
            
        Returns:
            True, если товар был отмечен, иначе False
        """
        shopping_list = await self.get_list(list_id)
        if not shopping_list:
            logger.warning(f"Не удалось найти список покупок с ID {list_id}")
            return False
        
        item = shopping_list.get_item(item_id)
        if not item:
            logger.warning(f"Не удалось найти товар {item_id} в списке покупок {list_id}")
            return False
        
        item.mark_as_purchased(by_user_id)
        shopping_list.updated_at = datetime.now()
        
        # Обновляем список в "базе данных"
        self._db[list_id] = shopping_list
        
        logger.info(f"Товар {item_id} отмечен как купленный в списке покупок {list_id}")
        return True
    
    async def clear_purchased_items(self, list_id: str) -> int:
        """
        Удаляет все купленные товары из списка.
        
        Args:
            list_id: ID списка покупок
            
        Returns:
            Количество удаленных товаров
        """
        shopping_list = await self.get_list(list_id)
        if not shopping_list:
            logger.warning(f"Не удалось найти список покупок с ID {list_id}")
            return 0
        
        count = shopping_list.clear_purchased_items()
        
        if count > 0:
            # Обновляем список в "базе данных"
            self._db[list_id] = shopping_list
            logger.info(f"Удалено {count} купленных товаров из списка покупок {list_id}")
        
        return count