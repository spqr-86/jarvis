"""
Сервис для управления семьями в приложении Jarvis.
"""

import logging
from typing import Optional, List, Tuple, Dict, Any
from uuid import uuid4

from sqlalchemy.orm import Session

from jarvis.storage.database import session as db_session
from jarvis.storage.relational.models.user import User, Family
from jarvis.storage.relational.dal.user_dal import UserDAO, FamilyDAO

logger = logging.getLogger(__name__)


class FamilyService:
    """Сервис для работы с семьями."""
    
    @classmethod
    def create_family(
        cls, 
        name: str, 
        created_by: str, 
        db: Optional[Session] = None
    ) -> Family:
        """
        Создает новую семью.
        
        Args:
            name: Название семьи
            created_by: ID пользователя, создающего семью
            db: Сессия базы данных
            
        Returns:
            Созданная семья
        """
        if db is None:
            db = db_session
        
        family_dao = FamilyDAO(db)
        
        family = family_dao.create(obj_in={
            "id": str(uuid4()),
            "name": name,
            "created_by": created_by
        })
        
        logger.info(f"Создана новая семья: {family.name}")
        return family
    
    @classmethod
    def add_member(
        cls, 
        family_id: str, 
        user_id: str, 
        db: Optional[Session] = None
    ) -> bool:
        """
        Добавляет пользователя в семью.
        
        Args:
            family_id: ID семьи
            user_id: ID пользователя
            db: Сессия базы данных
            
        Returns:
            True, если пользователь добавлен успешно, иначе False
        """
        if db is None:
            db = db_session
        
        user_dao = UserDAO(db)
        
        # Проверяем существование семьи и пользователя
        family_dao = FamilyDAO(db)
        family = family_dao.get(family_id)
        user = user_dao.get(user_id)
        
        if not family or not user:
            logger.warning(f"Семья {family_id} или пользователь {user_id} не найдены")
            return False
        
        # Обновляем семью пользователя
        user.family_id = family_id
        db.add(user)
        db.commit()
        
        logger.info(f"Пользователь {user_id} добавлен в семью {family_id}")
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
        
        return db.query(User).filter(User.family_id == family_id).all()
    
    @classmethod
    def remove_member(
        cls, 
        family_id: str, 
        user_id: str, 
        db: Optional[Session] = None
    ) -> bool:
        """
        Удаляет пользователя из семьи.
        
        Args:
            family_id: ID семьи
            user_id: ID пользователя
            db: Сессия базы данных
            
        Returns:
            True, если пользователь удален успешно, иначе False
        """
        if db is None:
            db = db_session
        
        user_dao = UserDAO(db)
        
        user = user_dao.get(user_id)
        
        if not user or user.family_id != family_id:
            logger.warning(f"Пользователь {user_id} не найден в семье {family_id}")
            return False
        
        # Удаляем привязку к семье
        user.family_id = None
        db.add(user)
        db.commit()
        
        logger.info(f"Пользователь {user_id} удален из семьи {family_id}")
        return True
    
    @classmethod
    def get_family_by_user(
        cls, 
        user_id: str, 
        db: Optional[Session] = None
    ) -> Optional[Family]:
        """
        Возвращает семью пользователя.
        
        Args:
            user_id: ID пользователя
            db: Сессия базы данных
            
        Returns:
            Семья пользователя или None, если семья не найдена
        """
        if db is None:
            db = db_session
        
        user_dao = UserDAO(db)
        family_dao = FamilyDAO(db)
        
        user = user_dao.get(user_id)
        
        if not user or not user.family_id:
            logger.warning(f"Пользователь {user_id} не состоит ни в одной семье")
            return None
        
        return family_dao.get(user.family_id)
    
    @classmethod
    def invite_to_family(
        cls, 
        family_id: str, 
        inviter_id: str, 
        invitee_telegram_id: str, 
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        """
        Создает приглашение пользователя в семью.
        
        Args:
            family_id: ID семьи
            inviter_id: ID пользователя, отправляющего приглашение
            invitee_telegram_id: Telegram ID приглашаемого пользователя
            db: Сессия базы данных
            
        Returns:
            Словарь с результатом операции
        """
        if db is None:
            db = db_session
        
        user_dao = UserDAO(db)
        family_dao = FamilyDAO(db)
        
        # Проверяем существование семьи и пользователя, отправляющего приглашение
        family = family_dao.get(family_id)
        inviter = user_dao.get(inviter_id)
        
        if not family or not inviter:
            logger.warning(f"Семья {family_id} или пользователь {inviter_id} не найдены")
            return {
                "success": False,
                "message": "Семья или пользователь не найдены"
            }
        
        # Проверяем, есть ли уже пользователь с таким Telegram ID
        invitee = user_dao.get_by_telegram_id(invitee_telegram_id)
        
        # Если пользователь еще не существует, можно отправить приглашение 
        # (в реальном приложении это будет через специальную систему приглашений)
        if not invitee:
            return {
                "success": True,
                "message": "Приглашение может быть отправлено новому пользователю",
                "invite_data": {
                    "family_id": family_id,
                    "family_name": family.name,
                    "inviter_name": inviter.first_name or inviter.username
                }
            }
        
        # Если пользователь уже существует, проверяем его текущую семью
        if invitee.family_id:
            if invitee.family_id == family_id:
                return {
                    "success": False,
                    "message": "Пользователь уже состоит в этой семье"
                }
            else:
                return {
                    "success": False,
                    "message": "Пользователь уже состоит в другой семье"
                }
        
        # Добавляем пользователя в семью
        invitee.family_id = family_id
        db.add(invitee)
        db.commit()
        
        logger.info(f"Пользователь {invitee.id} добавлен в семью {family_id}")
        
        return {
            "success": True,
            "message": "Пользователь успешно добавлен в семью",
            "user_id": invitee.id,
            "family_id": family_id
        }