"""
Интеграция функциональности списка покупок в Telegram-бота.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    CommandHandler,
    CallbackQueryHandler,
)

from jarvis.llm.graphs.shopping_graph import ShoppingGraph
from jarvis.storage.relational.shopping import ShoppingListRepository
from jarvis.core.models.shopping import ItemCategory, ItemPriority

logger = logging.getLogger(__name__)


# Клавиатура с категориями товаров
def get_categories_keyboard() -> List[List[str]]:
    """Возвращает клавиатуру с категориями товаров."""
    categories = [
        ["🍞 Хлебобулочные", "🥛 Молочные", "🥩 Мясо/Рыба"],
        ["🥦 Овощи", "🍎 Фрукты", "🥫 Бакалея"],
        ["🧊 Замороженные", "🧴 Бытовая химия", "📝 Другое"]
    ]
    return categories


# Клавиатура для управления списком покупок
def get_shopping_keyboard() -> List[List[str]]:
    """Возвращает клавиатуру для управления списком покупок."""
    keyboard = [
        ["📋 Показать список", "✅ Отметить купленным"],
        ["🗑️ Очистить список", "📊 Статистика покупок"]
    ]
    return keyboard


class ShoppingBotIntegration:
    """Интеграция функциональности списка покупок в Telegram-бота."""
    
    def __init__(self, shopping_repository: Optional[ShoppingListRepository] = None):
        """
        Инициализация интеграции списка покупок.
        
        Args:
            shopping_repository: Репозиторий для работы со списками покупок
        """
        self.repository = shopping_repository or ShoppingListRepository()
        self.shopping_graph = ShoppingGraph(shopping_repository=self.repository)
    
    def register_handlers(self, application):
        """
        Регистрирует обработчики для команд, связанных со списком покупок.
        
        Args:
            application: Экземпляр приложения Telegram бота
        """
        # Регистрируем команды для работы со списком покупок
        application.add_handler(CommandHandler("shopping", self.shopping_command))
        application.add_handler(CommandHandler("add", self.add_item_command))
        application.add_handler(CommandHandler("list", self.show_list_command))
        application.add_handler(CommandHandler("clear_list", self.clear_list_command))
        
        # Регистрируем обработчики колбэков для интерактивных кнопок
        application.add_handler(CallbackQueryHandler(self.handle_shopping_callback, pattern="^shopping_"))
    
    async def process_shopping_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
        """
        Обрабатывает сообщение пользователя, связанное со списком покупок.
        
        Args:
            update: Объект обновления от Telegram
            context: Контекст обработчика
            
        Returns:
            True, если сообщение связано со списком покупок и обработано, иначе False
        """
        user = update.effective_user
        user_id = str(user.id)
        family_id = f"family_{user_id}"  # В будущем будет из базы данных
        message_text = update.message.text
        
        # Обрабатываем сообщение через граф списка покупок
        result = await self.shopping_graph.process_message(
            user_input=message_text,
            user_id=user_id,
            family_id=family_id
        )
        
        # Если сообщение не связано со списком покупок, возвращаем False
        if not result.get("is_shopping_related", False):
            return False
        
        # Отправляем ответ пользователю
        if "response" in result and result["response"]:
            await update.message.reply_text(
                result["response"],
                reply_markup=ReplyKeyboardMarkup(
                    get_shopping_keyboard(),
                    resize_keyboard=True,
                    one_time_keyboard=True
                )
            )
        
        return True
    
    async def shopping_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик команды /shopping для управления списком покупок."""
        keyboard = get_shopping_keyboard()
        
        await update.message.reply_text(
            "Что вы хотите сделать со списком покупок?",
            reply_markup=ReplyKeyboardMarkup(
                keyboard,
                resize_keyboard=True,
                one_time_keyboard=True
            )
        )
    
    async def add_item_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик команды /add для добавления товара в список покупок."""
        args = context.args
        
        if not args:
            # Если аргументы не указаны, показываем подсказку
            await update.message.reply_text(
                "Пожалуйста, укажите товар для добавления в список покупок.\n"
                "Например: /add молоко 1л, хлеб 2 шт, сыр 300г",
                reply_markup=ReplyKeyboardMarkup(
                    get_categories_keyboard(),
                    resize_keyboard=True,
                    one_time_keyboard=True
                )
            )
            return
        
        # Объединяем аргументы в текст
        item_text = " ".join(args)
        
        # Используем граф для обработки добавления товара
        user_id = str(update.effective_user.id)
        family_id = f"family_{user_id}"  # В будущем будет из базы данных
        
        result = await self.shopping_graph.process_message(
            user_input=f"Добавь в список покупок {item_text}",
            user_id=user_id,
            family_id=family_id
        )
        
        # Отправляем ответ пользователю
        if "response" in result and result["response"]:
            await update.message.reply_text(result["response"])
        else:
            await update.message.reply_text("Не удалось добавить товар в список покупок.")
    
    async def show_list_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик команды /list для отображения списка покупок."""
        user_id = str(update.effective_user.id)
        family_id = f"family_{user_id}"  # В будущем будет из базы данных
        
        # Получаем активный список покупок
        active_list = await self.repository.get_active_list_for_family(family_id)
        
        if not active_list:
            await update.message.reply_text(
                "У вас нет активного списка покупок. Добавьте товары командой /add или просто напишите, что хотите купить."
            )
            return
        
        # Группируем товары по категориям
        categorized_items = active_list.sort_by_category()
        
        # Формируем сообщение
        message = f"📋 *Список покупок*\n\n"
        
        if not active_list.items:
            message += "Список пуст. Добавьте товары командой /add или просто напишите, что хотите купить."
        else:
            unpurchased_items = active_list.get_unpurchased_items()
            purchased_items = active_list.get_purchased_items()
            
            message += f"*Осталось купить ({len(unpurchased_items)}):*\n"
            
            # Добавляем товары по категориям
            for category, items in categorized_items.items():
                # Фильтруем только непокупленные
                category_items = [item for item in items if not item.is_purchased]
                if not category_items:
                    continue
                
                category_name = ItemCategory.get_ru_name(category)
                message += f"\n*{category_name}:*\n"
                
                for item in category_items:
                    priority_icon = ""
                    if item.priority == ItemPriority.HIGH:
                        priority_icon = "🔴 "
                    elif item.priority == ItemPriority.URGENT:
                        priority_icon = "❗️ "
                    
                    quantity_str = f"{item.quantity}"
                    if item.unit:
                        quantity_str += f" {item.unit}"
                    
                    message += f"- {priority_icon}{item.name} ({quantity_str})\n"
            
            if purchased_items:
                message += f"\n*Уже куплено ({len(purchased_items)}):*\n"
                for item in purchased_items[:5]:  # Показываем только первые 5
                    message += f"- ✅ {item.name}\n"
                
                if len(purchased_items) > 5:
                    message += f"... и еще {len(purchased_items) - 5}\n"
        
        # Добавляем инлайн-клавиатуру для действий
        keyboard = [
            [
                InlineKeyboardButton("✅ Отметить купленным", callback_data="shopping_mark"),
                InlineKeyboardButton("🗑️ Очистить список", callback_data="shopping_clear")
            ],
            [
                InlineKeyboardButton("📊 Статистика", callback_data="shopping_stats")
            ]
        ]
        
        await update.message.reply_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    
    async def clear_list_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик команды /clear_list для очистки списка покупок."""
        user_id = str(update.effective_user.id)
        family_id = f"family_{user_id}"  # В будущем будет из базы данных
        
        # Используем граф для обработки очистки списка
        result = await self.shopping_graph.process_message(
            user_input="Очисти список покупок",
            user_id=user_id,
            family_id=family_id
        )
        
        # Отправляем ответ пользователю
        if "response" in result and result["response"]:
            await update.message.reply_text(result["response"])
        else:
            await update.message.reply_text("Не удалось очистить список покупок.")
    
    async def handle_shopping_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Обработчик кнопок для списка покупок.
        
        Args:
            update: Объект обновления от Telegram
            context: Контекст обработчика
        """
        query = update.callback_query
        await query.answer()  # Отвечаем на колбэк, чтобы убрать "часики" у кнопки
        
        user_id = str(query.from_user.id)
        family_id = f"family_{user_id}"  # В будущем будет из базы данных
        
        # Определяем действие на основе callback_data
        action = query.data.split("_")[1] if len(query.data.split("_")) > 1 else ""
        
        if action == "mark":
            # Показываем клавиатуру с товарами для отметки
            await self._show_mark_keyboard(query, user_id, family_id)
        
        elif action == "clear":
            # Подтверждение очистки списка
            keyboard = [
                [
                    InlineKeyboardButton("Да, очистить", callback_data="shopping_clear_confirm"),
                    InlineKeyboardButton("Отмена", callback_data="shopping_cancel")
                ]
            ]
            
            await query.edit_message_text(
                "Вы уверены, что хотите очистить список покупок?",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        
        elif action == "clear_confirm":
            # Очищаем список покупок
            result = await self.shopping_graph.process_message(
                user_input="Очисти список покупок",
                user_id=user_id,
                family_id=family_id
            )
            
            if "response" in result and result["response"]:
                await query.edit_message_text(result["response"])
            else:
                await query.edit_message_text("Не удалось очистить список покупок.")
        
        elif action == "stats":
            # Показываем статистику по списку покупок
            await self._show_shopping_stats(query, user_id, family_id)
        
        elif action == "cancel":
            # Отменяем действие, возвращаемся к списку
            await self._refresh_shopping_list(query, user_id, family_id)
        
        elif action.startswith("mark_item_"):
            # Отмечаем товар как купленный
            item_id = action.split("mark_item_")[1]
            await self._mark_item_as_purchased(query, user_id, family_id, item_id)
        
        elif action == "back_to_list":
            # Возвращаемся к списку покупок
            await self._refresh_shopping_list(query, user_id, family_id)
    
    async def _show_mark_keyboard(self, query, user_id: str, family_id: str) -> None:
        """
        Показывает клавиатуру с товарами для отметки как купленные.
        
        Args:
            query: Объект callback_query
            user_id: ID пользователя
            family_id: ID семьи
        """
        # Получаем активный список покупок
        active_list = await self.repository.get_active_list_for_family(family_id)
        
        if not active_list or not active_list.items:
            await query.edit_message_text("В списке покупок нет товаров.")
            return
        
        # Получаем непокупленные товары
        unpurchased_items = active_list.get_unpurchased_items()
        
        if not unpurchased_items:
            await query.edit_message_text(
                "Все товары уже отмечены как купленные! 🎉",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("Вернуться к списку", callback_data="shopping_back_to_list")]
                ])
            )
            return
        
        # Создаем клавиатуру с товарами
        keyboard = []
        for item in unpurchased_items:
            keyboard.append([
                InlineKeyboardButton(
                    f"{item.name} ({item.quantity}{' ' + item.unit if item.unit else ''})",
                    callback_data=f"shopping_mark_item_{item.id}"
                )
            ])
        
        # Добавляем кнопку для возврата к списку
        keyboard.append([
            InlineKeyboardButton("Вернуться к списку", callback_data="shopping_back_to_list")
        ])
        
        await query.edit_message_text(
            "Выберите товар, который вы хотите отметить как купленный:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def _mark_item_as_purchased(self, query, user_id: str, family_id: str, item_id: str) -> None:
        """
        Отмечает товар как купленный.
        
        Args:
            query: Объект callback_query
            user_id: ID пользователя
            family_id: ID семьи
            item_id: ID товара
        """
        # Получаем активный список покупок
        active_list = await self.repository.get_active_list_for_family(family_id)
        
        if not active_list:
            await query.edit_message_text("Не удалось найти список покупок.")
            return
        
        # Ищем товар в списке
        item = active_list.get_item(item_id)
        if not item:
            await query.edit_message_text(
                "Не удалось найти указанный товар в списке.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("Вернуться к списку", callback_data="shopping_back_to_list")]
                ])
            )
            return
        
        # Отмечаем товар как купленный
        success = await self.repository.mark_item_as_purchased(
            list_id=active_list.id,
            item_id=item_id,
            by_user_id=user_id
        )
        
        if success:
            # Проверяем, остались ли непокупленные товары
            unpurchased_items = active_list.get_unpurchased_items()
            
            if not unpurchased_items:
                await query.edit_message_text(
                    f"Товар \"{item.name}\" отмечен как купленный! 🎉\n\n"
                    "Все товары из списка куплены! Поздравляем! 🎊",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("Вернуться к списку", callback_data="shopping_back_to_list")]
                    ])
                )
            else:
                # Предлагаем отметить другие товары
                keyboard = []
                for unpurchased_item in unpurchased_items[:5]:  # Показываем только первые 5
                    keyboard.append([
                        InlineKeyboardButton(
                            f"{unpurchased_item.name} ({unpurchased_item.quantity}{' ' + unpurchased_item.unit if unpurchased_item.unit else ''})",
                            callback_data=f"shopping_mark_item_{unpurchased_item.id}"
                        )
                    ])
                
                # Добавляем кнопку для возврата к списку
                keyboard.append([
                    InlineKeyboardButton("Вернуться к списку", callback_data="shopping_back_to_list")
                ])
                
                await query.edit_message_text(
                    f"Товар \"{item.name}\" отмечен как купленный! ✅\n\n"
                    f"Осталось купить: {len(unpurchased_items)}\n\n"
                    "Выберите следующий товар для отметки:",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
        else:
            await query.edit_message_text(
                "Не удалось отметить товар как купленный. Пожалуйста, попробуйте снова.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("Вернуться к списку", callback_data="shopping_back_to_list")]
                ])
            )
    
    async def _refresh_shopping_list(self, query, user_id: str, family_id: str) -> None:
        """
        Обновляет отображение списка покупок.
        
        Args:
            query: Объект callback_query
            user_id: ID пользователя
            family_id: ID семьи
        """
        # Получаем активный список покупок
        active_list = await self.repository.get_active_list_for_family(family_id)
        
        if not active_list:
            await query.edit_message_text("У вас нет активного списка покупок.")
            return
        
        # Группируем товары по категориям
        categorized_items = active_list.sort_by_category()
        
        # Формируем сообщение
        message = f"📋 *Список покупок*\n\n"
        
        if not active_list.items:
            message += "Список пуст. Добавьте товары командой /add или просто напишите, что хотите купить."
        else:
            unpurchased_items = active_list.get_unpurchased_items()
            purchased_items = active_list.get_purchased_items()
            
            message += f"*Осталось купить ({len(unpurchased_items)}):*\n"
            
            # Добавляем товары по категориям
            for category, items in categorized_items.items():
                # Фильтруем только непокупленные
                category_items = [item for item in items if not item.is_purchased]
                if not category_items:
                    continue
                
                category_name = ItemCategory.get_ru_name(category)
                message += f"\n*{category_name}:*\n"
                
                for item in category_items:
                    priority_icon = ""
                    if item.priority == ItemPriority.HIGH:
                        priority_icon = "🔴 "
                    elif item.priority == ItemPriority.URGENT:
                        priority_icon = "❗️ "
                    
                    quantity_str = f"{item.quantity}"
                    if item.unit:
                        quantity_str += f" {item.unit}"
                    
                    message += f"- {priority_icon}{item.name} ({quantity_str})\n"
            
            if purchased_items:
                message += f"\n*Уже куплено ({len(purchased_items)}):*\n"
                for item in purchased_items[:5]:  # Показываем только первые 5
                    message += f"- ✅ {item.name}\n"
                
                if len(purchased_items) > 5:
                    message += f"... и еще {len(purchased_items) - 5}\n"
        
        # Добавляем инлайн-клавиатуру для действий
        keyboard = [
            [
                InlineKeyboardButton("✅ Отметить купленным", callback_data="shopping_mark"),
                InlineKeyboardButton("🗑️ Очистить список", callback_data="shopping_clear")
            ],
            [
                InlineKeyboardButton("📊 Статистика", callback_data="shopping_stats")
            ]
        ]
        
        await query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    
    async def _show_shopping_stats(self, query, user_id: str, family_id: str) -> None:
        """
        Показывает статистику по списку покупок.
        
        Args:
            query: Объект callback_query
            user_id: ID пользователя
            family_id: ID семьи
        """
        # Получаем активный список покупок
        active_list = await self.repository.get_active_list_for_family(family_id)
        
        if not active_list:
            await query.edit_message_text("У вас нет активного списка покупок.")
            return
        
        # Формируем статистику
        total_items = len(active_list.items)
        purchased_items = len(active_list.get_purchased_items())
        unpurchased_items = len(active_list.get_unpurchased_items())
        
        # Статистика по категориям
        categorized_items = active_list.sort_by_category()
        category_stats = []
        
        for category, items in categorized_items.items():
            category_name = ItemCategory.get_ru_name(category)
            category_total = len(items)
            category_purchased = len([item for item in items if item.is_purchased])
            
            category_stats.append({
                "name": category_name,
                "total": category_total,
                "purchased": category_purchased,
                "progress": category_purchased / category_total if category_total > 0 else 1.0
            })
        
        # Формируем сообщение со статистикой
        message = f"📊 *Статистика списка покупок*\n\n"
        message += f"Всего товаров: {total_items}\n"
        message += f"Куплено: {purchased_items} ({int(purchased_items / total_items * 100) if total_items > 0 else 0}%)\n"
        message += f"Осталось купить: {unpurchased_items}\n\n"
        
        if category_stats:
            message += "*По категориям:*\n"
            for stat in category_stats:
                progress_percentage = int(stat["progress"] * 100)
                progress_bar = "▓" * (progress_percentage // 10) + "░" * (10 - progress_percentage // 10)
                
                message += f"{stat['name']}: {stat['purchased']}/{stat['total']} [{progress_bar}] {progress_percentage}%\n"
        
        # Кнопка для возврата к списку
        keyboard = [
            [InlineKeyboardButton("Вернуться к списку", callback_data="shopping_back_to_list")]
        ]
        
        await query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )