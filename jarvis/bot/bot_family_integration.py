"""
Интеграция функциональности управления семьей в Telegram-бота.
"""

import logging
from typing import Dict, Any, List, Optional
from uuid import uuid4
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

from jarvis.services.family import FamilyService
from jarvis.storage.relational.dal.user_dal import UserDAO, FamilyDAO


logger = logging.getLogger(__name__)


class FamilyBotIntegration:
    """Интеграция функциональности управления семьей в Telegram-бота."""
    
    def __init__(self):
        """Инициализация интеграции семьи."""
        self.user_dao = UserDAO()
        self.family_dao = FamilyDAO()
    
    def register_handlers(self, application: Application) -> None:
        """
        Регистрирует обработчики, связанные с семьей.
        
        Args:
            application: Экземпляр приложения Telegram бота
        """
        # Команды
        application.add_handler(CommandHandler("family", self.family_command))
        application.add_handler(CommandHandler("create_family", self.create_family_command))
        application.add_handler(CommandHandler("invite_to_family", self.invite_to_family_command))
        application.add_handler(CommandHandler("leave_family", self.leave_family_command))
        application.add_handler(CommandHandler("rename_family", self.rename_family_command))
        
        # Обработчики колбэков
        application.add_handler(CallbackQueryHandler(self.handle_family_callback, pattern="^family_"))
    
    async def family_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик команды /family для отображения информации о семье."""
        user = update.effective_user
        
        # Получаем информацию о пользователе из базы данных
        db_user = self.user_dao.get_by_telegram_id(str(user.id))
        
        if not db_user or not db_user.family_id:
            await update.message.reply_text(
                "У вас пока нет семьи. Используйте /create_family для создания."
            )
            return
        
        # Получаем семью пользователя
        family = FamilyService.get_family_by_user(db_user.id)
        
        if not family:
            await update.message.reply_text(
                "Произошла ошибка при получении информации о семье."
            )
            return
        
        # Получаем членов семьи
        members = FamilyService.get_family_members(family.id)
        
        # Формируем сообщение
        message = f"*Семья: {family.name}*\n\n"
        message += "Члены семьи:\n"
        
        for member in members:
            member_name = member.first_name or member.username
            if member.id == family.created_by:
                message += f"👑 {member_name} (Создатель)\n"
            else:
                message += f"👥 {member_name}\n"
        
        # Создаем кнопки
        keyboard = [
            [
                InlineKeyboardButton("➕ Добавить участника", callback_data="family_invite"),
                InlineKeyboardButton("➖ Удалить участника", callback_data="family_remove")
            ],
            [
                InlineKeyboardButton("✏️ Переименовать семью", callback_data="family_rename")
            ]
        ]
        
        await update.message.reply_text(
            message, 
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    
    async def create_family_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик команды /create_family для создания семьи."""
        user = update.effective_user
        
        # Проверяем аргументы команды (название семьи)
        if not context.args:
            await update.message.reply_text(
                "Пожалуйста, укажите название семьи.\n"
                "Например: /create_family Семья Ивановых"
            )
            return
        
        # Получаем информацию о пользователе из базы данных
        db_user = self.user_dao.get_by_telegram_id(str(user.id))
        
        if not db_user:
            await update.message.reply_text(
                "Произошла ошибка при регистрации. Пожалуйста, перезапустите бота командой /start"
            )
            return
        
        # Проверяем, нет ли у пользователя уже семьи
        if db_user.family_id:
            await update.message.reply_text(
                "У вас уже есть семья. Сначала выйдите из текущей семьи."
            )
            return
        
        # Создаем семью
        family_name = " ".join(context.args)
        family = FamilyService.create_family(
            name=family_name, 
            created_by=db_user.id
        )
        
        # Добавляем пользователя в созданную семью
        FamilyService.add_member(
            family_id=family.id, 
            user_id=db_user.id
        )
        
        await update.message.reply_text(
            f"Семья '{family_name}' успешно создана! 🎉\n"
            "Теперь вы можете добавлять в нее других участников."
        )
    
    async def invite_to_family_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик команды /invite_to_family для приглашения пользователя в семью."""
        user = update.effective_user
        
        # Проверяем наличие аргументов
        if not context.args or len(context.args) != 1:
            await update.message.reply_text(
                "Пожалуйста, укажите Telegram ID пользователя.\n"
                "Например: /invite_to_family 123456789"
            )
            return
        
        # Получаем информацию о текущем пользователе из базы данных
        db_user = self.user_dao.get_by_telegram_id(str(user.id))
        
        if not db_user or not db_user.family_id:
            await update.message.reply_text(
                "У вас нет семьи. Сначала создайте семью с помощью команды /create_family"
            )
            return
        
        # Получаем Telegram ID приглашаемого пользователя
        invitee_telegram_id = context.args[0]
        
        # Приглашаем пользователя в семью
        result = FamilyService.invite_to_family(
            family_id=db_user.family_id,
            inviter_id=db_user.id,
            invitee_telegram_id=invitee_telegram_id
        )
        
        # Формируем и отправляем ответ
        if result["success"]:
            # Если пользователь уже существует в базе данных
            if "user_id" in result:
                await update.message.reply_text(
                    f"Пользователь добавлен в семью '{result['family_id']}'! 🎉"
                )
            else:
                # Если это новый пользователь, которого еще нужно пригласить
                await update.message.reply_text(
                    f"Приглашение в семью '{result['invite_data']['family_name']}' "
                    f"может быть отправлено новому пользователю. Попросите его "
                    f"зарегистрироваться в боте."
                )
        else:
            await update.message.reply_text(result["message"])
    
    async def leave_family_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик команды /leave_family для выхода из семьи."""
        user = update.effective_user
        
        # Получаем информацию о пользователе из базы данных
        db_user = self.user_dao.get_by_telegram_id(str(user.id))
        
        if not db_user or not db_user.family_id:
            await update.message.reply_text(
                "Вы не состоите ни в одной семье."
            )
            return
        
        # Получаем семью пользователя
        family = self.family_dao.get(db_user.family_id)
        
        # Проверяем, не является ли пользователь единственным и создателем семьи
        members = FamilyService.get_family_members(family.id)
        
        if family.created_by == db_user.id and len(members) > 1:
            await update.message.reply_text(
                "Вы не можете покинуть семью, так как являетесь ее создателем. "
                "Сначала передайте права создателя другому участнику."
            )
            return
        
        # Удаляем пользователя из семьи
        success = FamilyService.remove_member(family.id, db_user.id)
        
        if success:
            # Если пользователь был единственным в семье, удаляем семью
            if len(members) == 1:
                self.family_dao.delete(id=family.id)
            
            await update.message.reply_text(
                "Вы успешно покинули семью. 👋"
            )
        else:
            await update.message.reply_text(
                "Не удалось покинуть семью. Пожалуйста, попробуйте позже."
            )
    
    async def rename_family_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик команды /rename_family для переименования семьи."""
        user = update.effective_user
        
        # Проверяем наличие аргументов
        if not context.args:
            await update.message.reply_text(
                "Пожалуйста, укажите новое название семьи.\n"
                "Например: /rename_family Семья Петровых"
            )
            return
        
        # Получаем информацию о пользователе из базы данных
        db_user = self.user_dao.get_by_telegram_id(str(user.id))
        
        if not db_user or not db_user.family_id:
            await update.message.reply_text(
                "У вас нет семьи. Сначала создайте семью с помощью команды /create_family"
            )
            return
        
        # Получаем семью пользователя
        family = self.family_dao.get(db_user.family_id)
        
        # Проверяем, является ли пользователь создателем семьи
        if family.created_by != db_user.id:
            await update.message.reply_text(
                "Только создатель семьи может переименовать ее."
            )
            return
        
        # Новое название семьи
        new_family_name = " ".join(context.args)
        
        # Обновляем название семьи
        family.name = new_family_name
        family.updated_at = datetime.now()
        self.family_dao.session.commit()
        
        await update.message.reply_text(
            f"Семья успешно переименована в '{new_family_name}'. 🎉"
        )
    
    async def handle_family_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик колбэков, связанных с семьей."""
        query = update.callback_query
        await query.answer()  # Отвечаем на колбэк, чтобы убрать "часики" у кнопки
        
        user = query.from_user
        
        # Получаем информацию о пользователе из базы данных
        db_user = self.user_dao.get_by_telegram_id(str(user.id))
        
        if not db_user or not db_user.family_id:
            await query.edit_message_text("У вас нет семьи.")
            return
        
        action = query.data.split("_")[1] if len(query.data.split("_")) > 1 else ""
        
        # Реализация обработки колбэков будет позже
        # Например, показ списка участников для удаления, 
        # форма для переименования и т.д.
        await query.edit_message_text(f"Выбрано действие: {action}")