from jarvis.storage.relational.dal.base import BaseDAO
from jarvis.storage.relational.models.user import User, Family


class UserDAO(BaseDAO[User, dict, dict]):
    """Data Access Object for users."""
    
    def __init__(self, db=None):
        super().__init__(User, db)
    
    def get_by_telegram_id(self, telegram_id: str):
        """Get user by Telegram ID."""
        return self._db.query(User).filter(User.telegram_id == telegram_id).first()
    
    def get_family_members(self, family_id: str):
        """Get all members of a family."""
        return self._db.query(User).filter(User.family_id == family_id).all()


class FamilyDAO(BaseDAO[Family, dict, dict]):
    """Data Access Object for families."""
    
    def __init__(self, db=None):
        super().__init__(Family, db)
    
    def get_by_creator(self, user_id: str):
        """Get families created by a specific user."""
        return self._db.query(Family).filter(Family.created_by == user_id).all()