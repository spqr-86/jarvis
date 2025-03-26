from sqlalchemy import and_

from jarvis.storage.relational.dal.base import BaseDAO
from jarvis.storage.relational.models.shopping import ShoppingList, ShoppingItem


class ShoppingListDAO(BaseDAO[ShoppingList, dict, dict]):
    """Data Access Object for shopping lists."""
    
    def __init__(self, db=None):
        super().__init__(ShoppingList, db)
    
    def get_active_for_family(self, family_id: str):
        """Get the active shopping list for a family."""
        return self._db.query(ShoppingList).filter(
            and_(
                ShoppingList.family_id == family_id,
                ShoppingList.is_active == True
            )
        ).first()
    
    def get_for_family(self, family_id: str):
        """Get all shopping lists for a family."""
        return self._db.query(ShoppingList).filter(
            ShoppingList.family_id == family_id
        ).all()


class ShoppingItemDAO(BaseDAO[ShoppingItem, dict, dict]):
    """Data Access Object for shopping items."""
    
    def __init__(self, db=None):
        super().__init__(ShoppingItem, db)
    
    def get_by_list(self, list_id: str):
        """Get all items in a shopping list."""
        return self._db.query(ShoppingItem).filter(
            ShoppingItem.shopping_list_id == list_id
        ).all()
    
    def get_purchased(self, list_id: str):
        """Get purchased items in a shopping list."""
        return self._db.query(ShoppingItem).filter(
            and_(
                ShoppingItem.shopping_list_id == list_id,
                ShoppingItem.is_purchased == True
            )
        ).all()
    
    def get_unpurchased(self, list_id: str):
        """Get unpurchased items in a shopping list."""
        return self._db.query(ShoppingItem).filter(
            and_(
                ShoppingItem.shopping_list_id == list_id,
                ShoppingItem.is_purchased == False
            )
        ).all()