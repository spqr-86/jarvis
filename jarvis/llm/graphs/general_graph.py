"""
Граф обработки общих диалогов для бота Jarvis.
Отвечает за обработку запросов, которые не относятся к специфическим функциональным областям.
"""

import logging
from typing import Dict, Any, List, Optional

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from jarvis.llm.models import LLMService
from jarvis.utils.helpers import generate_uuid

logger = logging.getLogger(__name__)


class GeneralConversationGraph:
    """
    Граф для обработки общих диалогов, не связанных со специфическими функциями.
    Обрабатывает общие вопросы, запросы информации, светскую беседу и т.д.
    """
    
    def __init__(self, llm_service: LLMService):
        """
        Инициализация графа обработки общих диалогов.
        
        Args:
            llm_service: Сервис LLM для генерации ответов
        """
        self.llm_service = llm_service
        self.system_message = """
        Ты — семейный ассистент Jarvis, помогающий в организации повседневной жизни.
        Отвечай кратко, информативно и дружелюбно. Предлагай конкретные решения, когда это уместно.
        
        Ты можешь помочь с:
        - Общими вопросами и светской беседой
        - Информацией о своих возможностях
        - Рекомендациями по организации семейного быта
        - Советами для эффективного планирования
        
        Если запрос касается специфических функций (задачи, списки покупок, бюджет),
        расскажи пользователю, как он может использовать соответствующие команды.
        """
    
    async def process_message(
        self,
        user_input: str,
        user_id: str,
        family_id: Optional[str],
        chat_history: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """
        Обрабатывает запрос пользователя и генерирует ответ.
        
        Args:
            user_input: Текст запроса пользователя
            user_id: ID пользователя
            family_id: ID семьи пользователя (или None, если нет семьи)
            chat_history: История диалога
            
        Returns:
            Словарь с результатами обработки запроса
        """
        try:
            # Преобразуем историю диалога в формат, понятный LLM
            messages = []
            
            # Добавляем системное сообщение
            messages.append(SystemMessage(content=self.system_message))
            
            # Добавляем историю диалога (до 5 последних сообщений)
            recent_history = chat_history[-5:] if len(chat_history) >= 5 else chat_history
            for msg in recent_history:
                if msg["role"] == "user":
                    messages.append(HumanMessage(content=msg["content"]))
                elif msg["role"] == "assistant":
                    messages.append(AIMessage(content=msg["content"]))
            
            # Добавляем текущий запрос пользователя
            messages.append(HumanMessage(content=user_input))
            
            # Генерируем ответ
            response = await self.llm_service.model.ainvoke(messages)
            
            # Проверяем, не нужно ли добавить пользовательский интерфейс
            ui_action = None
            
            # Здесь может быть логика для определения необходимости добавления кнопок
            # Например, если запрос содержит вопрос о возможностях бота
            if any(keyword in user_input.lower() for keyword in ["что ты умеешь", "помощь", "функции", "возможности"]):
                ui_action = {
                    "type": "show_keyboard",
                    "message": "Вот что я могу сделать:",
                    "keyboard": [
                        ["📋 Список покупок", "💰 Бюджет"],
                        ["📅 Задачи", "👨‍👩‍👧‍👦 Семья"],
                        ["ℹ️ Помощь"]
                    ],
                    "one_time": True
                }
            
            # Формируем результат
            result = {
                "response": response.content,
                "domain": "general",
                "intent": "general_conversation",
                "confidence": 1.0,
                "entities": {}
            }
            
            # Добавляем UI-действие, если есть
            if ui_action:
                result["ui_action"] = ui_action
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка при обработке запроса в общем графе: {str(e)}")
            # В случае ошибки возвращаем базовый ответ
            return {
                "response": "Извините, я не смог обработать ваш запрос. Попробуйте переформулировать или задать другой вопрос.",
                "domain": "general",
                "intent": "error",
                "confidence": 1.0,
                "entities": {}
            }