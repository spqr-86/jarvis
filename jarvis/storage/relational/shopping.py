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

    def _to_db_entity(self, item_model: ShoppingItemModel, list_id: str) -> ShoppingItem:
        """Convert domain model to database entity."""
        return ShoppingItem(
            id=item_model.id,
            name=item_model.name,
            quantity=item_model.quantity,
            unit=item_model.unit,
            category=ItemCategoryEnum(item_model.category.value),
            priority=ItemPriorityEnum(item_model.priority.value),
            is_purchased=item_model.is_purchased,
            notes=item_model.notes,
            shopping_list_id=list_id,
            assigned_to=item_model.assigned_to,
            created_at=item_model.created_at,
            updated_at=item_model.updated_at
        )
    
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

    async def get_lists_for_family(self, family_id: str) -> List[ShoppingListModel]:
        """
        Получает все списки покупок для семьи.
        
        Args:
            family_id: ID семьи
            
        Returns:
            Список списков покупок
        """
        db_lists = self._db.query(ShoppingList).filter(
            ShoppingList.family_id == family_id
        ).all()
        
        return [self._to_model(db_list) for db_list in db_lists]
    
    async def add_item(
            self, 
            list_id: str, 
            name: str,
            quantity: float = 1.0,
            unit: Optional[str] = None,
            category: ItemCategory = ItemCategory.OTHER,
            priority: Optional[ItemPriority] = None,
            notes: Optional[str] = None
        ) -> Tuple[bool, Optional[ShoppingItemModel]]:
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
            # Get the database list
            db_list = self._db.query(ShoppingList).filter(ShoppingList.id == list_id).first()
            if not db_list:
                logger.warning(f"Не удалось найти список покупок с ID {list_id}")
                return False, None
            
            # Устанавливаем значение по умолчанию для приоритета
            if priority is None:
                priority = ItemPriority.MEDIUM
            
            # Create a new item in the database
            item_id = str(uuid4())
            db_item = ShoppingItem(
                id=item_id,
                name=name,
                quantity=quantity,
                unit=unit,
                category=ItemCategoryEnum(category.value),
                priority=ItemPriorityEnum(priority.value),
                is_purchased=False,
                notes=notes,
                shopping_list_id=list_id
            )
            
            self._db.add(db_item)
            self._db.commit()
            self._db.refresh(db_item)
            
            # Convert to domain model
            item_model = ShoppingItemModel(
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
            
            logger.info(f"Добавлен товар '{name}' в список покупок {list_id}")
            return True, item_model
    
    async def update_list(self, list_id: str, **kwargs) -> bool:
        """
        Обновляет список покупок.
        
        Args:
            list_id: ID списка покупок
            **kwargs: Атрибуты для обновления
            
        Returns:
            True, если список был обновлен, иначе False
        """
        db_list = self._db.query(ShoppingList).filter(ShoppingList.id == list_id).first()
        if not db_list:
            logger.warning(f"Не удалось найти список покупок с ID {list_id}")
            return False
        
        # Update attributes
        for key, value in kwargs.items():
            if hasattr(db_list, key) and key not in ['id', 'family_id', 'created_at', 'items']:
                setattr(db_list, key, value)
        
        db_list.updated_at = datetime.now()
        
        self._db.add(db_list)
        self._db.commit()
        
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
        db_item = self._db.query(ShoppingItem).filter(
            and_(
                ShoppingItem.shopping_list_id == list_id,
                ShoppingItem.id == item_id
            )
        ).first()
        
        if not db_item:
            logger.warning(f"Не удалось найти товар {item_id} в списке покупок {list_id}")
            return False
        
        # Update attributes
        for key, value in kwargs.items():
            if hasattr(db_item, key) and key not in ['id', 'shopping_list_id', 'created_at']:
                # Handle enums
                if key == 'category' and isinstance(value, ItemCategory):
                    setattr(db_item, key, ItemCategoryEnum(value.value))
                elif key == 'priority' and isinstance(value, ItemPriority):
                    setattr(db_item, key, ItemPriorityEnum(value.value))
                else:
                    setattr(db_item, key, value)
        
        db_item.updated_at = datetime.now()
        
        self._db.add(db_item)
        self._db.commit()
        
        logger.info(f"Обновлен товар {item_id} в списке покупок {list_id}")
        return True
    
    async def remove_item(self, list_id: str, item_id: str) -> bool:
        """
        Удаляет товар из списка покупок.
        
        Args:
            list_id: ID списка покупок
            item_id: ID товара
            
        Returns:
            True, если товар был удален, иначе False
        """
        db_item = self._db.query(ShoppingItem).filter(
            and_(
                ShoppingItem.shopping_list_id == list_id,
                ShoppingItem.id == item_id
            )
        ).first()
        
        if not db_item:
            logger.warning(f"Не удалось найти товар {item_id} в списке покупок {list_id}")
            return False
        
        self._db.delete(db_item)
        self._db.commit()
        
        logger.info(f"Удален товар {item_id} из списка покупок {list_id}")
        return True
    
    async def delete_list(self, list_id: str) -> bool:
        """
        Удаляет список покупок.
        
        Args:
            list_id: ID списка покупок
            
        Returns:
            True, если список был удален, иначе False
        """
        db_list = self._db.query(ShoppingList).filter(ShoppingList.id == list_id).first()
        if not db_list:
            logger.warning(f"Не удалось найти список покупок с ID {list_id}")
            return False
        
        self._db.delete(db_list)
        self._db.commit()
        
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
        db_item = self._db.query(ShoppingItem).filter(
            and_(
                ShoppingItem.shopping_list_id == list_id,
                ShoppingItem.id == item_id
            )
        ).first()
        
        if not db_item:
            logger.warning(f"Не удалось найти товар {item_id} в списке покупок {list_id}")
            return False
        
        db_item.is_purchased = True
        db_item.updated_at = datetime.now()
        
        # Set assigned_to if provided
        if by_user_id and not db_item.assigned_to:
            db_item.assigned_to = by_user_id
        
        self._db.add(db_item)
        self._db.commit()
        
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
        purchased_items = self._db.query(ShoppingItem).filter(
            and_(
                ShoppingItem.shopping_list_id == list_id,
                ShoppingItem.is_purchased == True
            )
        ).all()
        
        count = len(purchased_items)
        
        if count > 0:
            for item in purchased_items:
                self._db.delete(item)
            
            self._db.commit()
            logger.info(f"Удалено {count} купленных товаров из списка покупок {list_id}")
        
        return count