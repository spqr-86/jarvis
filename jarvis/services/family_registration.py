import logging
from typing import Optional, Dict, Any, Tuple, List
from uuid import uuid4
from datetime import datetime

from sqlalchemy.orm import Session

from jarvis.storage.database import session as db_session
from jarvis.storage.relational.models.user import User, Family
from jarvis.storage.relational.dal.user_dal import UserDAO, FamilyDAO

logger = logging.getLogger(__name__)


class FamilyRegistrationService:
    """Сервис для регистрации и управления семьями."""
    
    @classmethod
    def create_or_get_family(
        cls, 
        user_id: str, 
        family_name: Optional[str] = None, 
        db: Optional[Session] = None
    ) -> Tuple[Family, bool]:
        """
        Создает семью для пользователя или возвращает существующую.
        
        Args:
            user_id: ID пользователя
            family_name: Название семьи (если не указано, генерируется автоматически)
            db: Сессия базы данных
            
        Returns:
            Кортеж (созданная/найденная семья, флаг создания)
        """
        if db is None:
            db = db_session
        
        user_dao = UserDAO(db)
        family_dao = FamilyDAO(db)
        
        # Получаем пользователя
        user = user_dao.get(user_id)
        
        if not user:
            raise ValueError(f"Пользователь с ID {user_id} не найден")
        
        # Если у пользователя уже есть семья, возвращаем ее
        if user.family_id:
            family = family_dao.get(user.family_id)
            return family, False
        
        # Создаем новую семью
        if not family_name:
            family_name = f"Семья {user.first_name or user.username}"
        
        family = family_dao.create(obj_in={
            "id": str(uuid4()),
            "name": family_name,
            "created_by": user_id
        })
        
        # Привязываем пользователя к семье
        user.family_id = family.id
        db.add(user)
        db.commit()
        
        logger.info(f"Создана новая семья '{family.name}' для пользователя {user_id}")
        
        return family, True
    
    @classmethod
    def add_user_to_family(
        cls, 
        user_id: str, 
        family_id: str, 
        db: Optional[Session] = None
    ) -> bool:
        """
        Добавляет пользователя в существующую семью.
        
        Args:
            user_id: ID пользователя
            family_id: ID семьи
            db: Сессия базы данных
            
        Returns:
            True, если пользователь успешно добавлен в семью, иначе False
        """
        if db is None:
            db = db_session
        
        user_dao = UserDAO(db)
        family_dao = FamilyDAO(db)
        
        # Проверяем существование семьи и пользователя
        family = family_dao.get(family_id)
        user = user_dao.get(user_id)
        
        if not family or not user:
            logger.warning(f"Семья {family_id} или пользователь {user_id} не найдены")
            return False
        
        # Проверяем, не состоит ли пользователь уже в другой семье
        if user.family_id:
            logger.warning(f"Пользователь {user_id} уже состоит в семье {user.family_id}")
            return False
        
        # Добавляем пользователя в семью
        user.family_id = family_id
        db.add(user)
        db.commit()
        
        logger.info(f"Пользователь {user_id} добавлен в семью {family_id}")
        return True
    
    @classmethod
    def remove_user_from_family(
        cls, 
        user_id: str, 
        family_id: str, 
        db: Optional[Session] = None
    ) -> bool:
        """
        Удаляет пользователя из семьи.
        
        Args:
            user_id: ID пользователя
            family_id: ID семьи
            db: Сессия базы данных
            
        Returns:
            True, если пользователь успешно удален из семьи, иначе False
        """
        if db is None:
            db = db_session
        
        user_dao = UserDAO(db)
        family_dao = FamilyDAO(db)
        
        # Проверяем существование семьи и пользователя
        family = family_dao.get(family_id)
        user = user_dao.get(user_id)
        
        if not family or not user:
            logger.warning(f"Семья {family_id} или пользователь {user_id} не найдены")
            return False
        
        # Проверяем, состоит ли пользователь в указанной семье
        if user.family_id != family_id:
            logger.warning(f"Пользователь {user_id} не состоит в семье {family_id}")
            return False
        
        # Если пользователь - создатель семьи, нельзя его удалить
        if family.created_by == user_id:
            logger.warning(f"Нельзя удалить создателя семьи {family_id}")
            return False
        
        # Удаляем пользователя из семьи
        user.family_id = None
        db.add(user)
        db.commit()
        
        logger.info(f"Пользователь {user_id} удален из семьи {family_id}")
        return True
    
    @classmethod
    def get_family_members(
        cls, 
        family_id: str, 
        db: Optional[Session] = None
    ) -> List[User]:
        """
        Возвращает список членов семьи.
        
        Args:
            family_id: ID семьи
            db: Сессия базы данных
            
        Returns:
            Список пользователей-членов семьи
        """
        if db is None:
            db = db_session
        
        user_dao = UserDAO(db)
        return user_dao.get_multi(family_id=family_id)
    
    @classmethod
    def transfer_family_ownership(
        cls, 
        family_id: str, 
        current_owner_id: str, 
        new_owner_id: str, 
        db: Optional[Session] = None
    ) -> bool:
        """
        Передает права владения семьей другому пользователю.
        
        Args:
            family_id: ID семьи
            current_owner_id: ID текущего владельца
            new_owner_id: ID нового владельца
            db: Сессия базы данных
            
        Returns:
            True, если права переданы успешно, иначе False
        """
        if db is None:
            db = db_session
        
        family_dao = FamilyDAO(db)
        user_dao = UserDAO(db)
        
        # Проверяем существование семьи и пользователей
        family = family_dao.get(family_id)
        current_owner = user_dao.get(current_owner_id)
        new_owner = user_dao.get(new_owner_id)
        
        if not family or not current_owner or not new_owner:
            logger.warning("Семья или один из пользователей не найден")
            return False
        
        # Проверяем, является ли текущий пользователь владельцем семьи
        if family.created_by != current_owner_id:
            logger.warning("Текущий пользователь не является владельцем семьи")
            return False
        
        # Проверяем, состоит ли новый владелец в той же семье
        if new_owner.family_id != family_id:
            logger.warning("Новый владелец не является членом семьи")
            return False
        
        # Передаем права владения
        family.created_by = new_owner_id
        family.updated_at = datetime.now()
        
        db.add(family)
        db.commit()
        
        logger.info(f"Права владения семьей {family_id} переданы от {current_owner_id} к {new_owner_id}")
        return True