"""
Интеграция различных функциональных модулей в основной бот.
"""

import logging

from telegram.ext import Application

from jarvis.bot.bot_shopping_integration import ShoppingBotIntegration
from jarvis.storage.relational.shopping import ShoppingListRepository

logger = logging.getLogger(__name__)


def register_modules(application: Application) -> None:
    """
    Регистрирует модули функциональности в основном приложении бота.
    
    Args:
        application: Экземпляр приложения Telegram бота
    """
    # Инициализация хранилищ
    shopping_repository = ShoppingListRepository()
    
    # Инициализация и регистрация модуля списка покупок
    shopping_integration = ShoppingBotIntegration(shopping_repository=shopping_repository)
    shopping_integration.register_handlers(application)
    
    logger.info("Модули функциональности зарегистрированы")
    
    # Здесь можно регистрировать другие модули по мере их добавления
    # Например, модуль календаря, модуль задач и т.д.