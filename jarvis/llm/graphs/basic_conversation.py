"""Базовый граф разговора с использованием LangGraph."""

import logging
from typing import Dict, List, Any, Optional, Tuple
from enum import Enum

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, END

from jarvis.llm.models import LLMService
from jarvis.llm.chains.base import IntentClassificationChain, TaskExtractionChain
from jarvis.llm.chains.task import TaskCreationChain

logger = logging.getLogger(__name__)


class ConversationState(Enum):
    """Состояния разговора в графе."""
    
    START = "start"
    INTENT_CLASSIFICATION = "intent_classification"
    TASK_EXTRACTION = "task_extraction"
    TASK_CREATION = "task_creation"
    GENERAL_RESPONSE = "general_response"
    END = "end"


class ConversationGraph:
    """Граф разговора для управления потоком диалога."""
    
    def __init__(self, llm_service: Optional[LLMService] = None):
        """
        Инициализация графа разговора.
        
        Args:
            llm_service: Сервис LLM для использования в графе
        """
        self.llm_service = llm_service or LLMService()
        
        # Инициализация цепочек
        self.intent_chain = IntentClassificationChain(self.llm_service)
        self.task_extraction_chain = TaskExtractionChain(self.llm_service)
        self.task_creation_chain = TaskCreationChain(self.llm_service)
        
        # Создание графа
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """Создает и возвращает граф состояний разговора."""
        # Определяем граф с начальным состоянием
        graph = StateGraph()
        
        # Добавляем узлы в граф
        graph.add_node(ConversationState.START.value, self._start_node)
        graph.add_node(ConversationState.INTENT_CLASSIFICATION.value, self._classify_intent)
        graph.add_node(ConversationState.TASK_EXTRACTION.value, self._extract_task)
        graph.add_node(ConversationState.TASK_CREATION.value, self._create_task)
        graph.add_node(ConversationState.GENERAL_RESPONSE.value, self._generate_general_response)
        
        # Определяем ребра (переходы) в графе
        graph.add_edge(ConversationState.START.value, ConversationState.INTENT_CLASSIFICATION.value)
        
        # Определяем условия перехода от классификации намерения
        graph.add_conditional_edges(
            ConversationState.INTENT_CLASSIFICATION.value,
            self._route_by_intent,
            {
                ConversationState.TASK_EXTRACTION.value: "task_creation",
                ConversationState.GENERAL_RESPONSE.value: "general"
            }
        )
        
        # Определяем переход от извлечения задачи к созданию задачи
        graph.add_edge(ConversationState.TASK_EXTRACTION.value, ConversationState.TASK_CREATION.value)
        
        # Определяем переходы к завершению
        graph.add_edge(ConversationState.TASK_CREATION.value, END)
        graph.add_edge(ConversationState.GENERAL_RESPONSE.value, END)
        
        # Устанавливаем начальный узел
        graph.set_entry_point(ConversationState.START.value)
        
        return graph.compile()
    
    async def _start_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Начальный узел графа.
        
        Args:
            state: Текущее состояние разговора
        
        Returns:
            Обновленное состояние
        """
        # Просто передаем состояние дальше, не изменяя его
        return state
    
    async def _classify_intent(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Узел классификации намерения пользователя.
        
        Args:
            state: Текущее состояние разговора
        
        Returns:
            Обновленное состояние с классифицированным намерением
        """
        try:
            # Получаем текст пользователя из состояния
            user_text = state.get("user_input", "")
            
            # Классифицируем намерение
            intent_result = await self.intent_chain.process(user_text)
            
            # Обновляем состояние
            state["intent"] = intent_result.intent
            state["intent_confidence"] = intent_result.confidence
            state["entities"] = intent_result.entities
            
            return state
        except Exception as e:
            logger.error(f"Ошибка при классификации намерения: {str(e)}")
            # В случае ошибки устанавливаем базовое намерение
            state["intent"] = "general_question"
            state["intent_confidence"] = 0.5
            state["entities"] = {}
            
            return state
    
    def _route_by_intent(self, state: Dict[str, Any]) -> str:
        """
        Определяет следующий узел на основе классифицированного намерения.
        
        Args:
            state: Текущее состояние разговора
        
        Returns:
            Имя следующего узла
        """
        intent = state.get("intent", "general_question")
        
        # Определяем, какое намерение связано с созданием задачи
        task_related_intents = ["task_creation", "event_planning", "shopping_list"]
        
        if intent in task_related_intents:
            return "task_creation"
        else:
            return "general"
    
    async def _extract_task(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Узел извлечения информации о задаче.
        
        Args:
            state: Текущее состояние разговора
        
        Returns:
            Обновленное состояние с извлеченной информацией о задаче
        """
        try:
            # Получаем текст пользователя из состояния
            user_text = state.get("user_input", "")
            
            # Извлекаем информацию о задаче
            task_result = await self.task_extraction_chain.process(user_text)
            
            # Обновляем состояние
            state["task"] = task_result.dict()
            
            return state
        except Exception as e:
            logger.error(f"Ошибка при извлечении задачи: {str(e)}")
            # В случае ошибки устанавливаем базовую задачу
            state["task"] = {
                "task_type": "unknown",
                "task_description": user_text,
                "deadline": None,
                "assignees": None,
                "priority": None
            }
            
            return state
    
    async def _create_task(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Узел создания задачи.
        
        Args:
            state: Текущее состояние разговора
        
        Returns:
            Обновленное состояние с результатом создания задачи
        """
        try:
            # Получаем информацию о задаче из состояния
            task_dict = state.get("task", {})
            task = TaskExtractor(**task_dict)
            
            # Создаем задачу
            task_result = await self.task_creation_chain.process(task)
            
            # Обновляем состояние
            state["response"] = task_result.message
            state["task_id"] = task_result.task_id
            state["success"] = task_result.success
            
            return state
        except Exception as e:
            logger.error(f"Ошибка при создании задачи: {str(e)}")
            # В случае ошибки устанавливаем базовый ответ
            state["response"] = "Произошла ошибка при создании задачи. Пожалуйста, попробуйте снова."
            state["success"] = False
            
            return state
    
    async def _generate_general_response(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Узел для генерации общего ответа на запрос пользователя.
        
        Args:
            state: Текущее состояние разговора
        
        Returns:
            Обновленное состояние с ответом
        """
        try:
            # Получаем текст пользователя из состояния
            user_text = state.get("user_input", "")
            
            # Генерируем ответ с помощью LLM
            response = await self.llm_service.generate_response(
                prompt=user_text,
                system_message="Ты — семейный ассистент Jarvis, помогающий в организации повседневной жизни. Отвечай кратко, информативно и дружелюбно.",
                chat_history=state.get("chat_history", [])
            )
            
            # Обновляем состояние
            state["response"] = response
            
            return state
        except Exception as e:
            logger.error(f"Ошибка при генерации ответа: {str(e)}")
            # В случае ошибки устанавливаем базовый ответ
            state["response"] = "Извините, я не смог обработать ваш запрос. Пожалуйста, попробуйте переформулировать."
            
            return state
    
    async def process_message(self, user_input: str, chat_history: List[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Обрабатывает сообщение пользователя через граф разговора.
        
        Args:
            user_input: Текст от пользователя
            chat_history: История диалога
        
        Returns:
            Результат обработки сообщения
        """
        # Создаем начальное состояние
        initial_state = {
            "user_input": user_input,
            "chat_history": chat_history or []
        }
        
        # Запускаем граф
        try:
            # Выполняем граф со начальным состоянием
            final_state = await self.graph.ainvoke(initial_state)
            
            # Возвращаем результат
            return {
                "response": final_state.get("response", "Извините, я не смог обработать ваш запрос."),
                "success": final_state.get("success", True),
                "task_id": final_state.get("task_id"),
                "intent": final_state.get("intent"),
                "entities": final_state.get("entities")
            }
        except Exception as e:
            logger.error(f"Ошибка при выполнении графа разговора: {str(e)}")
            return {
                "response": "Произошла ошибка при обработке вашего запроса. Пожалуйста, попробуйте снова.",
                "success": False
            }