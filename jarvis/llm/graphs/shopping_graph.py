"""
Граф для обработки запросов, связанных со списком покупок.
"""

import logging
from typing import Dict, List, Any, Optional, TypedDict
from enum import Enum

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, END

from jarvis.llm.models import LLMService
from jarvis.llm.chains.shopping import (
    ShoppingIntentClassifier, 
    ShoppingItemExtractor,
    ShoppingResponseGenerator,
    ShoppingListManager
)
from jarvis.storage.relational.shopping import ShoppingListRepository

logger = logging.getLogger(__name__)


class ShoppingState(str, Enum):
    """Состояния в графе обработки запросов к списку покупок."""
    
    START = "start"
    CLASSIFY_INTENT = "classify_intent"
    EXTRACT_ITEMS = "extract_items"
    PROCESS_SHOPPING_ACTION = "process_shopping_action"
    GENERATE_RESPONSE = "generate_response"
    END = "end"


# Определяем схему состояния для StateGraph
class ShoppingStateDict(TypedDict, total=False):
    """Определение схемы состояния для графа списка покупок."""
    
    user_input: str
    user_id: str
    family_id: str
    chat_history: List[Dict[str, str]]
    intent: str
    intent_confidence: float
    items: List[Dict[str, Any]]
    active_list_id: Optional[str]
    operation_result: str
    operation_metadata: Dict[str, Any]
    response: str


class ShoppingGraph:
    """Граф для обработки запросов к списку покупок."""
    
    def __init__(
        self,
        llm_service: Optional[LLMService] = None,
        shopping_repository: Optional[ShoppingListRepository] = None
    ):
        """
        Инициализация графа обработки запросов к списку покупок.
        
        Args:
            llm_service: Сервис LLM для использования в графе
            shopping_repository: Репозиторий для работы со списками покупок
        """
        self.llm_service = llm_service or LLMService()
        self.repository = shopping_repository or ShoppingListRepository()
        
        # Инициализация цепочек
        self.intent_classifier = ShoppingIntentClassifier(self.llm_service)
        self.item_extractor = ShoppingItemExtractor(self.llm_service)
        self.response_generator = ShoppingResponseGenerator(self.llm_service)
        
        # Создаем менеджер списков покупок, который объединит репозиторий и цепочки
        self.shopping_manager = ShoppingListManager(self.repository, self.llm_service)
        
        # Создание графа
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """Создает и возвращает граф состояний для обработки запросов к списку покупок."""
        # Определяем граф с начальным состоянием и схемой состояния
        graph = StateGraph(state_schema=ShoppingStateDict)
        
        # Добавляем узлы в граф
        graph.add_node(ShoppingState.START, self._start_node)
        graph.add_node(ShoppingState.CLASSIFY_INTENT, self._classify_intent)
        graph.add_node(ShoppingState.EXTRACT_ITEMS, self._extract_items)
        graph.add_node(ShoppingState.PROCESS_SHOPPING_ACTION, self._process_shopping_action)
        graph.add_node(ShoppingState.GENERATE_RESPONSE, self._generate_response)
        
        # Определяем ребра (переходы) в графе
        graph.add_edge(ShoppingState.START, ShoppingState.CLASSIFY_INTENT)
        
        # Условные переходы от классификации намерения
        graph.add_conditional_edges(
            ShoppingState.CLASSIFY_INTENT,
            self._route_by_intent,
            {
                # Эти ключи должны точно соответствовать возвращаемым значениям метода _route_by_intent
                "needs_extraction": ShoppingState.EXTRACT_ITEMS,
                "direct_action": ShoppingState.PROCESS_SHOPPING_ACTION,
                "not_shopping_related": END
            }
        )
        
        # Остальные переходы
        graph.add_edge(ShoppingState.EXTRACT_ITEMS, ShoppingState.PROCESS_SHOPPING_ACTION)
        graph.add_edge(ShoppingState.PROCESS_SHOPPING_ACTION, ShoppingState.GENERATE_RESPONSE)
        graph.add_edge(ShoppingState.GENERATE_RESPONSE, END)
        
        # Устанавливаем начальный узел
        graph.set_entry_point(ShoppingState.START)
        
        return graph.compile()
    
    async def _start_node(self, state: ShoppingStateDict) -> ShoppingStateDict:
        """
        Начальный узел графа.
        
        Args:
            state: Текущее состояние
        
        Returns:
            Обновленное состояние
        """
        # Проверяем наличие необходимых параметров
        if "user_input" not in state:
            state["user_input"] = ""
        
        if "user_id" not in state:
            state["user_id"] = "unknown_user"
        
        if "family_id" not in state:
            state["family_id"] = f"family_{state['user_id']}"
        
        if "chat_history" not in state:
            state["chat_history"] = []
        
        return state
    
    async def _classify_intent(self, state: ShoppingStateDict) -> ShoppingStateDict:
        """
        Узел классификации намерения пользователя.
        
        Args:
            state: Текущее состояние
            
        Returns:
            Обновленное состояние с классифицированным намерением
        """
        try:
            # Получаем текст пользователя из состояния
            user_text = state["user_input"]
            
            # Классифицируем намерение
            intent_result = await self.intent_classifier.process(user_text)
            
            # Обновляем состояние
            state["intent"] = intent_result.intent
            state["intent_confidence"] = intent_result.confidence
            
            # Если в намерении уже есть товары, добавляем их в состояние
            if intent_result.items:
                state["items"] = [item.dict() for item in intent_result.items]
            
            logger.info(f"Классифицировано намерение: {intent_result.intent} с уверенностью {intent_result.confidence}")
            
            return state
        except Exception as e:
            logger.error(f"Ошибка при классификации намерения: {str(e)}")
            # В случае ошибки устанавливаем базовое намерение
            state["intent"] = "other"
            state["intent_confidence"] = 0.5
            return state
    
    def _route_by_intent(self, state: ShoppingStateDict) -> str:
        """
        Определяет следующий узел на основе классифицированного намерения.
        
        Args:
            state: Текущее состояние
            
        Returns:
            Имя следующего узла
        """
        intent = state.get("intent", "other")
        confidence = state.get("intent_confidence", 0.0)
        
        # Если уверенность низкая или намерение не связано со списком покупок, завершаем обработку
        if confidence < 0.6 or intent == "other":
            return "not_shopping_related"
        
        # Определяем, требует ли намерение извлечения товаров
        intents_requiring_extraction = ["add_item", "mark_purchased", "remove_item", "change_priority"]
        
        if intent in intents_requiring_extraction and "items" not in state:
            # Обратите внимание, что здесь мы возвращаем строку, которая должна точно соответствовать 
            # ключу в словаре переходов в методе _build_graph
            return "needs_extraction"  # Этот ключ должен точно соответствовать ключу в add_conditional_edges
        else:
            return "direct_action"
    
    async def _extract_items(self, state: ShoppingStateDict) -> ShoppingStateDict:
        """
        Узел извлечения информации о товарах.
        
        Args:
            state: Текущее состояние
            
        Returns:
            Обновленное состояние с извлеченной информацией о товарах
        """
        try:
            # Получаем текст пользователя из состояния
            user_text = state["user_input"]
            
            # Извлекаем информацию о товарах
            items_result = await self.item_extractor.process(user_text)
            
            # Обновляем состояние
            state["items"] = [item.dict() for item in items_result.items]
            
            logger.info(f"Извлечено товаров: {len(state['items'])}")
            
            return state
        except Exception as e:
            logger.error(f"Ошибка при извлечении товаров: {str(e)}")
            # В случае ошибки устанавливаем пустой список товаров
            state["items"] = []
            return state
    
    async def _process_shopping_action(self, state: ShoppingStateDict) -> ShoppingStateDict:
            """
            Узел обработки действия со списком покупок.
            
            Args:
                state: Текущее состояние
                
            Returns:
                Обновленное состояние с результатом операции
            """
            try:
                # Получаем необходимые данные из состояния
                user_id = state["user_id"]
                family_id = state["family_id"]
                intent = state["intent"]
                
                # Получаем активный список покупок
                active_list = await self.repository.get_active_list_for_family(family_id)
                
                # Сохраняем ID активного списка в состоянии
                state["active_list_id"] = active_list.id if active_list else None
                
                # Обрабатываем различные намерения
                operation_result = "успешно"
                operation_metadata = {}
                
                if intent == "create_list":
                    # Создание нового списка
                    list_name = "Список покупок"  # По умолчанию
                    new_list = await self.repository.create_list(
                        name=list_name,
                        family_id=family_id,
                        created_by=user_id
                    )
                    state["active_list_id"] = new_list.id
                    operation_metadata["list_name"] = new_list.name
                    
                elif intent == "add_item":
                    # Добавление товаров в список
                    if not active_list:
                        # Создаем список, если его нет
                        active_list = await self.repository.create_list(
                            name="Список покупок",
                            family_id=family_id,
                            created_by=user_id
                        )
                        state["active_list_id"] = active_list.id
                    
                    items = state.get("items", [])
                    if not items:
                        operation_result = "нет товаров для добавления"
                    else:
                        added_items = []
                        for item_data in items:
                            # Очищаем данные перед передачей в репозиторий
                            clean_item_data = {}
                            for key, value in item_data.items():
                                if value is not None:  # Передаем только ненулевые значения
                                    clean_item_data[key] = value
                            
                            # Обязательные поля
                            if "name" not in clean_item_data:
                                continue
                            
                            success, added_item = await self.repository.add_item(
                                list_id=active_list.id,
                                **clean_item_data
                            )
                            if success and added_item:
                                added_items.append(added_item)
                        
                        operation_metadata["added_items"] = [item.name for item in added_items]
                        operation_metadata["added_count"] = len(added_items)
                
                elif intent == "view_list":
                    # Просмотр списка
                    if not active_list:
                        operation_result = "нет активного списка покупок"
                    else:
                        operation_metadata["list_name"] = active_list.name
                        operation_metadata["unpurchased_count"] = len(active_list.get_unpurchased_items())
                        operation_metadata["purchased_count"] = len(active_list.get_purchased_items())
                        operation_metadata["items"] = [
                            {"name": item.name, "is_purchased": item.is_purchased}
                            for item in active_list.items
                        ]
                
                elif intent == "mark_purchased":
                    # Отметка товаров как купленных
                    if not active_list:
                        operation_result = "нет активного списка покупок"
                    else:
                        items = state.get("items", [])
                        if not items:
                            operation_result = "не указаны товары для отметки"
                        else:
                            marked_items = []
                            for item_data in items:
                                # Ищем товар с похожим названием
                                for list_item in active_list.get_unpurchased_items():
                                    if item_data["name"].lower() in list_item.name.lower():
                                        success = await self.repository.mark_item_as_purchased(
                                            list_id=active_list.id,
                                            item_id=list_item.id,
                                            by_user_id=user_id
                                        )
                                        if success:
                                            marked_items.append(list_item.name)
                            
                            operation_metadata["marked_items"] = marked_items
                            operation_metadata["marked_count"] = len(marked_items)
                            
                            if not marked_items:
                                operation_result = "товары не найдены в списке"
                
                elif intent == "remove_item":
                    # Удаление товаров из списка
                    if not active_list:
                        operation_result = "нет активного списка покупок"
                    else:
                        items = state.get("items", [])
                        if not items:
                            operation_result = "не указаны товары для удаления"
                        else:
                            removed_items = []
                            for item_data in items:
                                # Ищем товар с похожим названием
                                for list_item in active_list.items[:]:  # Копируем список для безопасной итерации
                                    if item_data["name"].lower() in list_item.name.lower():
                                        success = await self.repository.remove_item(
                                            list_id=active_list.id,
                                            item_id=list_item.id
                                        )
                                        if success:
                                            removed_items.append(list_item.name)
                            
                            operation_metadata["removed_items"] = removed_items
                            operation_metadata["removed_count"] = len(removed_items)
                            
                            if not removed_items:
                                operation_result = "товары не найдены в списке"
                
                elif intent == "clear_list":
                    # Очистка списка
                    if not active_list:
                        operation_result = "нет активного списка покупок"
                    else:
                        # Удаляем все товары
                        cleared_count = 0
                        for item in active_list.items[:]:  # Копируем список для безопасной итерации
                            success = await self.repository.remove_item(
                                list_id=active_list.id,
                                item_id=item.id
                            )
                            if success:
                                cleared_count += 1
                        
                        operation_metadata["cleared_count"] = cleared_count
                
                elif intent == "change_priority":
                    # Изменение приоритета товара
                    if not active_list:
                        operation_result = "нет активного списка покупок"
                    else:
                        items = state.get("items", [])
                        if not items:
                            operation_result = "не указаны товары для изменения приоритета"
                        else:
                            updated_items = []
                            for item_data in items:
                                if "priority" not in item_data:
                                    continue
                                    
                                # Ищем товар с похожим названием
                                for list_item in active_list.items:
                                    if item_data["name"].lower() in list_item.name.lower():
                                        success = await self.repository.update_item(
                                            list_id=active_list.id,
                                            item_id=list_item.id,
                                            priority=item_data["priority"]
                                        )
                                        if success:
                                            updated_items.append(list_item.name)
                            
                            operation_metadata["updated_items"] = updated_items
                            operation_metadata["updated_count"] = len(updated_items)
                            
                            if not updated_items:
                                operation_result = "товары не найдены в списке"
                
                # Обновляем состояние
                state["operation_result"] = operation_result
                state["operation_metadata"] = operation_metadata
                
                logger.info(f"Обработано намерение {intent} с результатом: {operation_result}")
                
                return state
            except Exception as e:
                logger.error(f"Ошибка при обработке действия со списком покупок: {str(e)}")
                state["operation_result"] = "произошла ошибка"
                state["operation_metadata"] = {"error": str(e)}
                return state
    
    async def _generate_response(self, state: ShoppingStateDict) -> ShoppingStateDict:
        """
        Узел генерации ответа пользователю.
        
        Args:
            state: Текущее состояние
            
        Returns:
            Обновленное состояние с ответом пользователю
        """
        try:
            # Подготавливаем данные для генерации ответа
            intent = state["intent"]
            operation_result = state["operation_result"]
            metadata = state["operation_metadata"]
            
            # Формируем информацию о товарах
            items_info = "нет товаров"
            if intent == "add_item" and "added_items" in metadata:
                items = metadata.get("added_items", [])
                if items:
                    items_info = f"Добавлено в список: {', '.join(items)}"
            
            elif intent == "view_list" and "items" in metadata:
                unpurchased = [item["name"] for item in metadata.get("items", []) if not item["is_purchased"]]
                if unpurchased:
                    items_info = f"Товары к покупке: {', '.join(unpurchased[:5])}"
                    if len(unpurchased) > 5:
                        items_info += f" и еще {len(unpurchased) - 5}"
            
            elif intent == "mark_purchased" and "marked_items" in metadata:
                items = metadata.get("marked_items", [])
                if items:
                    items_info = f"Отмечено как купленное: {', '.join(items)}"
            
            elif intent == "remove_item" and "removed_items" in metadata:
                items = metadata.get("removed_items", [])
                if items:
                    items_info = f"Удалено из списка: {', '.join(items)}"
            
            # Формируем информацию о списке
            list_info = "Список покупок"
            if "list_name" in metadata:
                list_name = metadata["list_name"]
                list_info = f"Список покупок '{list_name}'"
                
                if intent == "view_list":
                    unpurchased_count = metadata.get("unpurchased_count", 0)
                    purchased_count = metadata.get("purchased_count", 0)
                    list_info += f"\nТоваров к покупке: {unpurchased_count}, куплено: {purchased_count}"
            
            # Генерируем ответ
            response = await self.response_generator.process(
                intent=intent,
                items_info=items_info,
                list_info=list_info,
                operation_result=operation_result
            )
            
            # Обновляем состояние
            state["response"] = response
            
            logger.info(f"Сгенерирован ответ для намерения {intent}")
            
            return state
        except Exception as e:
            logger.error(f"Ошибка при генерации ответа: {str(e)}")
            state["response"] = "Извините, произошла ошибка при обработке вашего запроса. Пожалуйста, попробуйте снова."
            return state
    
    async def process_message(
        self,
        user_input: str,
        user_id: str,
        family_id: Optional[str] = None,
        chat_history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        Обрабатывает сообщение пользователя через граф списка покупок.
        
        Args:
            user_input: Текст пользователя
            user_id: ID пользователя
            family_id: ID семьи (если не указан, будет создан на основе user_id)
            chat_history: История чата
            
        Returns:
            Результат обработки сообщения
        """
        # Создаем начальное состояние
        initial_state: ShoppingStateDict = {
            "user_input": user_input,
            "user_id": user_id,
            "family_id": family_id or f"family_{user_id}",
            "chat_history": chat_history or []
        }
        
        # Запускаем граф
        try:
            # Выполняем граф с начальным состоянием
            final_state = await self.graph.ainvoke(initial_state)
            
            # Проверяем, что в ответе есть все необходимые поля
            if "response" not in final_state:
                # Если графу не удалось сгенерировать ответ, это может означать,
                # что запрос не связан со списком покупок
                return {
                    "is_shopping_related": False,
                    "response": None,
                    "intent": final_state.get("intent", "other"),
                    "confidence": final_state.get("intent_confidence", 0.0)
                }
            
            # Возвращаем результат
            return {
                "is_shopping_related": True,
                "response": final_state["response"],
                "intent": final_state.get("intent", ""),
                "list_id": final_state.get("active_list_id", ""),
                "operation_result": final_state.get("operation_result", ""),
                "metadata": final_state.get("operation_metadata", {})
            }
        except Exception as e:
            logger.error(f"Ошибка при выполнении графа списка покупок: {str(e)}")
            return {
                "is_shopping_related": False,
                "response": "Произошла ошибка при обработке вашего запроса. Пожалуйста, попробуйте снова.",
                "error": str(e)
            }