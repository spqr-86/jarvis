import logging
from typing import Dict, Any, Optional, List, Tuple

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

from jarvis.config import TELEGRAM_BOT_TOKEN
from jarvis.llm.models import LLMService
from jarvis.storage.vector.chroma_store import VectorStoreService
from jarvis.utils.helpers import generate_uuid
from jarvis.llm.graphs.basic_conversation import ConversationGraph


# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Инициализация сервисов
llm_service = LLMService()
vector_store = VectorStoreService()

# Системное сообщение для LLM
SYSTEM_MESSAGE = """
Ты — семейный ассистент Jarvis, помогающий в организации повседневной жизни. 
Твоя задача — помогать с планированием, напоминаниями, составлением списков, управлением бюджетом и другими семейными делами.
Отвечай кратко, информативно и дружелюбно.
"""

# Временное хранилище для сессий пользователей
# В реальном приложении это должно быть реализовано через базу данных
USER_SESSIONS: Dict[int, Dict[str, Any]] = {}


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start."""
    user = update.effective_user
    message = (
        f"Привет, {user.first_name}! Я Jarvis — ваш семейный ассистент. "
        f"Я могу помочь с планированием задач, напоминаниями и другими повседневными делами.\n\n"
        f"Вот несколько вещей, которые я могу сделать:\n"
        f"• Создать напоминание\n"
        f"• Спланировать мероприятие\n"
        f"• Составить список покупок\n"
        f"• Управлять семейным бюджетом\n\n"
        f"Чем я могу помочь вам сегодня?"
    )
    await update.message.reply_text(message)
    
    # Инициализация сессии пользователя
    user_id = update.effective_user.id
    if user_id not in USER_SESSIONS:
        USER_SESSIONS[user_id] = {
            "chat_history": [],
            "family_id": None  # В будущем будет связано с базой данных
        }


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /help."""
    help_text = (
        "Я могу помочь вам с различными задачами:\n\n"
        "• /start - Начать взаимодействие с ботом\n"
        "• /help - Показать это сообщение\n"
        "• /clear - Очистить историю диалога\n\n"
        "Вы также можете просто написать мне, что вам нужно, и я постараюсь помочь!"
    )
    await update.message.reply_text(help_text)


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /clear для очистки истории диалога."""
    user_id = update.effective_user.id
    if user_id in USER_SESSIONS:
        USER_SESSIONS[user_id]["chat_history"] = []
    
    await update.message.reply_text("История диалога очищена.")


async def process_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик текстовых сообщений от пользователя."""
    user_id = update.effective_user.id
    message_text = update.message.text
    
    # Проверяем, есть ли у пользователя активная сессия
    if user_id not in USER_SESSIONS:
        USER_SESSIONS[user_id] = {
            "chat_history": [],
            "family_id": None  # В будущем будет связано с базой данных
        }
    
    # Получение истории диалога
    chat_history = USER_SESSIONS[user_id]["chat_history"]
    
    # Показываем пользователю, что бот печатает
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action="typing"
    )
    
    # Обработка сообщения через граф разговора
    result = await conversation_graph.process_message(
        user_input=message_text,
        chat_history=[{"role": msg["role"], "content": msg["content"]} for msg in chat_history[-5:]]  # Берем последние 5 сообщений
    )
    
    response = result["response"]
    
    # Обновление истории диалога
    chat_history.append({"role": "user", "content": message_text})
    chat_history.append({"role": "assistant", "content": response})
    
    # Временная реализация family_id (в реальном приложении это будет из базы данных)
    family_id = USER_SESSIONS[user_id].get("family_id") or f"family_{user_id}"
    
    # Сохранение взаимодействия в векторной БД
    interaction_id = generate_uuid()
    await vector_store.add_texts(
        texts=[message_text, response], 
        metadatas=[
            {
                "family_id": family_id,
                "user_id": str(user_id),
                "type": "user_message",
                "interaction_id": interaction_id,
                "intent": result.get("intent"),
                "has_task": bool(result.get("task_id"))
            },
            {
                "family_id": family_id,
                "user_id": str(user_id),
                "type": "assistant_response",
                "interaction_id": interaction_id
            }
        ]
    )
    
    # Отправляем ответ пользователю
    await update.message.reply_text(response)


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик ошибок."""
    logger.error(f"Update {update} caused error {context.error}")
    
    # Отправляем пользователю сообщение об ошибке
    if update and update.effective_chat:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Произошла ошибка при обработке вашего запроса. Пожалуйста, попробуйте снова."
        )


def run_bot() -> None:
    """Запускает Telegram-бота."""
    # Создаем экземпляр приложения
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Добавляем обработчики команд
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("clear", clear_command))
    
    # Добавляем обработчик текстовых сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, process_message))
    
    # Добавляем обработчик ошибок
    application.add_error_handler(error_handler)
    
    # Запускаем бота
    application.run_polling()


if __name__ == "__main__":
    run_bot()