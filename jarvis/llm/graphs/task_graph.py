"""
Граф обработки задач для бота Jarvis.
Отвечает за создание, редактирование, просмотр и управление задачами и напоминаниями.
"""

import logging
import json
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from enum import Enum

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, END

from jarvis.llm.models import LLMService
from jarvis.llm.chains.base import TaskExtractor, TaskExtractionChain
from jarvis.llm.chains.task import TaskCreationChain
from jarvis.utils.helpers import generate_uuid, format_timestamp, extract_entities

logger = logging.getLogger(__name__)


class TaskState(str, Enum):
    """Состояния в графе обработки задач."""
    
    START = "start"
    CLASSIFY_INTENT = "classify_intent"
    EXTRACT_TASK = "extract_task"
    CREATE_TASK = "create_task"
    LIST_TASKS = "list_tasks"
    UPDATE_TASK = "update_task"
    DELETE_TASK = "delete_task"
    GENERATE_RESPONSE = "generate_response"
    END = "end"


class TaskGraph:
    """
    Граф для обработки запросов, связанных с задачами.
    Отвечает за создание, редактирование, просмотр и управление задачами и напоминаниями.
    """
    
    def __init__(self, llm_service: LLMService):
        """
        Инициализация графа обработки задач.
        
        Args:
            llm_service: Сервис LLM для использования в графе
        """
        self.llm_service = llm_service
        
        # Инициализация цепочек
        self.task_extraction_chain = TaskExtractionChain(llm_service)
        self.task_creation_chain = TaskCreationChain(llm_service)
        
        # Системное сообщение для общения с LLM
        self.system_message = """
        Ты — семейный ассистент Jarvis, специализирующийся на управлении задачами и напоминаниями.
        Помогаешь пользователям создавать, отслеживать, обновлять и завершать задачи.
        Твоя цель — сделать управление задачами простым и эффективным.
        """
    
    async def process_message(
        self,
        user_input: str,
        user_id: str,
        family_id: Optional[str],
        chat_history: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """
        Обрабатывает запрос пользователя, связанный с задачами.
        
        Args:
            user_input: Текст запроса пользователя
            user_id: ID пользователя
            family_id: ID семьи пользователя
            chat_history: История диалога
            
        Returns:
            Словарь с результатами обработки запроса
        """
        try:
            # Классифицируем запрос для определения конкретного интента внутри домена задач
            task_intent, confidence = await self._classify_task_intent(user_input)
            
            # Если уверенность в том, что запрос связан с задачами, низкая,
            # возвращаем None, чтобы обработка была передана общему графу
            if confidence < 0.6:
                logger.info(f"Запрос не связан с задачами (уверенность: {confidence})")
                return None
            
            # Обрабатываем запрос в зависимости от интента
            result = None
            
            if task_intent == "create_task":
                # Создание новой задачи
                result = await self._handle_create_task(user_input, user_id, family_id)
            elif task_intent == "list_tasks":
                # Просмотр списка задач
                result = await self._handle_list_tasks(user_input, user_id, family_id)
            elif task_intent == "update_task":
                # Обновление задачи
                result = await self._handle_update_task(user_input, user_id, family_id)
            elif task_intent == "delete_task":
                # Удаление задачи
                result = await self._handle_delete_task(user_input, user_id, family_id)
            elif task_intent == "mark_completed":
                # Отметка задачи как выполненной
                result = await self._handle_mark_completed(user_input, user_id, family_id)
            else:
                # Обработка запроса с неизвестным интентом в области задач
                result = await self._handle_general_task_query(user_input, user_id, family_id)
            
            # Если не удалось обработать запрос, возвращаем None
            if not result:
                return None
                
            # Добавляем информацию об интенте
            result.update({
                "domain": "task_management",
                "intent": task_intent,
                "confidence": confidence
            })
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка при обработке запроса в графе задач: {str(e)}")
            # В случае ошибки возвращаем None, чтобы обработка перешла к общему графу
            return None
    
    async def _classify_task_intent(self, user_input: str) -> Tuple[str, float]:
        """
        Классифицирует запрос для определения конкретного интента в области задач.
        
        Args:
            user_input: Текст запроса пользователя
            
        Returns:
            Кортеж (интент, уверенность)
        """
        # Системное сообщение для классификатора
        system_message = """
        Ты — классификатор запросов, связанных с задачами.
        Определи, к какому типу относится запрос пользователя и верни ответ в формате JSON.
        
        Возможные интенты:
        - create_task: Создание новой задачи или напоминания
        - list_tasks: Просмотр списка задач
        - update_task: Обновление существующей задачи
        - delete_task: Удаление задачи
        - mark_completed: Отметка задачи как выполненной
        - task_question: Общий вопрос о задачах
        """
        
        # Промпт для классификации
        prompt = f"""
        Запрос пользователя: {user_input}
        
        Определи интент и верни ответ в формате JSON:
        {{
            "intent": "название_интента",
            "confidence": число_от_0_до_1
        }}
        """
        
        try:
            # Получаем ответ от LLM
            response = await self.llm_service.generate_response(
                prompt=prompt,
                system_message=system_message
            )
            
            # Парсим JSON ответ
            result = json.loads(response)
            
            return result.get("intent", "task_question"), result.get("confidence", 0.0)
        except Exception as e:
            logger.error(f"Ошибка при классификации интента задачи: {str(e)}")
            return "task_question", 0.5
    
    async def _handle_create_task(
        self,
        user_input: str,
        user_id: str,
        family_id: str
    ) -> Dict[str, Any]:
        """
        Обрабатывает запрос на создание новой задачи.
        
        Args:
            user_input: Текст запроса пользователя
            user_id: ID пользователя
            family_id: ID семьи пользователя
            
        Returns:
            Словарь с результатами обработки запроса
        """
        # Извлекаем информацию о задаче из запроса
        task_data = await self.task_extraction_chain.process(user_input)
        
        # Создаем задачу (в реальном приложении здесь будет сохранение в базу)
        task_response = await self.task_creation_chain.process(task_data)
        
        # Формируем ответ пользователю
        response = task_response.message
        
        # Создаем UI-действие для возможных следующих шагов
        ui_action = {
            "type": "show_keyboard",
            "message": "Что вы хотите сделать дальше?",
            "keyboard": [
                ["📋 Показать задачи", "➕ Создать еще задачу"],
                ["🔍 Поиск задач", "📊 Статистика"]
            ],
            "one_time": True
        }
        
        # Возвращаем результат
        return {
            "response": response,
            "task_id": task_response.task_id,
            "task_info": task_data.dict(),
            "success": task_response.success,
            "ui_action": ui_action
        }
    
    async def _handle_list_tasks(
        self,
        user_input: str,
        user_id: str,
        family_id: str
    ) -> Dict[str, Any]:
        """
        Обрабатывает запрос на просмотр списка задач.
        
        Args:
            user_input: Текст запроса пользователя
            user_id: ID пользователя
            family_id: ID семьи пользователя
            
        Returns:
            Словарь с результатами обработки запроса
        """
        # В реальном приложении здесь был бы запрос к базе данных
        # Для демонстрации используем заглушку
        mock_tasks = [
            {"id": "task1", "description": "Купить продукты", "deadline": "сегодня", "priority": "средний"},
            {"id": "task2", "description": "Оплатить счета", "deadline": "завтра", "priority": "высокий"},
            {"id": "task3", "description": "Забрать посылку", "deadline": "3 дня", "priority": "низкий"}
        ]
        
        # Формируем текст ответа
        response = "Вот ваши текущие задачи:\n\n"
        
        for task in mock_tasks:
            priority_icon = "🔴" if task["priority"] == "высокий" else "🟡" if task["priority"] == "средний" else "🟢"
            response += f"{priority_icon} {task['description']} (срок: {task['deadline']})\n"
        
        # Создаем UI-действие для возможных следующих шагов
        ui_action = {
            "type": "show_inline_keyboard",
            "inline_keyboard": [
                [
                    {"text": "✅ Отметить выполненной", "callback_data": "task_mark_completed"},
                    {"text": "🗑️ Удалить", "callback_data": "task_delete"}
                ],
                [
                    {"text": "➕ Создать задачу", "callback_data": "task_create"}
                ]
            ]
        }
        
        # Возвращаем результат
        return {
            "response": response,
            "tasks": mock_tasks,
            "ui_action": ui_action
        }
    
    async def _handle_update_task(
        self,
        user_input: str,
        user_id: str,
        family_id: str
    ) -> Dict[str, Any]:
        """
        Обрабатывает запрос на обновление задачи.
        
        Args:
            user_input: Текст запроса пользователя
            user_id: ID пользователя
            family_id: ID семьи пользователя
            
        Returns:
            Словарь с результатами обработки запроса
        """
        # Заглушка для демонстрации
        # В реальном приложении здесь будет извлечение ID задачи и новых данных,
        # а затем обновление в базе данных
        
        response = "Задача успешно обновлена. Изменения сохранены."
        
        # Возвращаем результат
        return {
            "response": response,
            "success": True
        }
    
    async def _handle_delete_task(
        self,
        user_input: str,
        user_id: str,
        family_id: str
    ) -> Dict[str, Any]:
        """
        Обрабатывает запрос на удаление задачи.
        
        Args:
            user_input: Текст запроса пользователя
            user_id: ID пользователя
            family_id: ID семьи пользователя
            
        Returns:
            Словарь с результатами обработки запроса
        """
        # Заглушка для демонстрации
        # В реальном приложении здесь будет извлечение ID задачи и удаление из базы данных
        
        response = "Задача успешно удалена."
        
        # Возвращаем результат
        return {
            "response": response,
            "success": True
        }
    
    async def _handle_mark_completed(
        self,
        user_input: str,
        user_id: str,
        family_id: str
    ) -> Dict[str, Any]:
        """
        Обрабатывает запрос на отметку задачи как выполненной.
        
        Args:
            user_input: Текст запроса пользователя
            user_id: ID пользователя
            family_id: ID семьи пользователя
            
        Returns:
            Словарь с результатами обработки запроса
        """
        # Заглушка для демонстрации
        # В реальном приложении здесь будет извлечение ID задачи и обновление статуса в базе данных
        
        response = "Отлично! Задача отмечена как выполненная. 🎉"
        
        # Возвращаем результат
        return {
            "response": response,
        }
