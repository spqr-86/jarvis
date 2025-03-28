"""
Маршрутизатор диалогов для бота Jarvis.
Отвечает за классификацию запросов и их направление в соответствующие 
специализированные графы обработки.
"""

import logging
import json
from typing import Dict, Any, List, Optional

from jarvis.llm.models import LLMService
from jarvis.llm.graphs.general_graph import GeneralConversationGraph
from jarvis.llm.graphs.task_graph import TaskGraph
from jarvis.llm.graphs.shopping_graph import ShoppingGraph
from jarvis.llm.graphs.budget_graph import BudgetGraph
from jarvis.storage.relational.shopping import ShoppingListRepository
from jarvis.storage.relational.budget import TransactionRepository, BudgetRepository, FinancialGoalRepository

logger = logging.getLogger(__name__)


class ConversationRouter:
    """Маршрутизатор диалогов к специализированным графам."""
    
    def __init__(self, llm_service: LLMService):
        """
        Инициализирует маршрутизатор диалогов.
        
        Args:
            llm_service: Сервис LLM для использования в классификации запросов
        """
        self.llm_service = llm_service
        
        # Инициализация репозиториев
        self.shopping_repository = ShoppingListRepository()
        self.transaction_repository = TransactionRepository()
        self.budget_repository = BudgetRepository()
        self.goal_repository = FinancialGoalRepository()
        
        # Инициализация графов
        self.general_graph = GeneralConversationGraph(llm_service)
        self.task_graph = TaskGraph(llm_service)
        self.shopping_graph = ShoppingGraph(
            llm_service=llm_service,
            shopping_repository=self.shopping_repository
        )
        self.budget_graph = BudgetGraph(
            llm_service=llm_service,
            transaction_repository=self.transaction_repository,
            budget_repository=self.budget_repository,
            goal_repository=self.goal_repository
        )
    
    async def route_message(
        self, 
        user_input: str,
        user_id: str,
        family_id: Optional[str],
        chat_history: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """
        Определяет, какой граф должен обработать запрос и направляет его туда.
        
        Args:
            user_input: Текст запроса пользователя
            user_id: ID пользователя
            family_id: ID семьи пользователя (или None, если нет семьи)
            chat_history: История диалога
            
        Returns:
            Результат обработки запроса соответствующим графом
        """
        # Если пользователь не привязан к семье, используем только общий граф
        if not family_id:
            return await self.general_graph.process_message(
                user_input=user_input,
                user_id=user_id,
                family_id=None,
                chat_history=chat_history
            )
        
        # Классифицируем запрос, чтобы определить домен
        intent_classification = await self._classify_intent(user_input, chat_history)
        
        domain = intent_classification.get("domain", "general")
        confidence = intent_classification.get("confidence", 0.0)
        
        # Логируем результат классификации
        logger.info(f"Запрос '{user_input}' классифицирован как домен '{domain}' с уверенностью {confidence}")
        
        # Если уверенность в классификации низкая, используем общий граф
        if confidence < 0.6:
            logger.info(f"Низкая уверенность в классификации ({confidence}), используем общий граф")
            result = await self.general_graph.process_message(
                user_input=user_input,
                user_id=user_id,
                family_id=family_id,
                chat_history=chat_history
            )
            # Добавляем информацию о классификации
            result.update(intent_classification)
            return result
            
        # Маршрутизация на основе домена
        result = None
        
        if domain == "task_management":
            result = await self.task_graph.process_message(
                user_input=user_input,
                user_id=user_id,
                family_id=family_id,
                chat_history=chat_history
            )
        elif domain == "shopping":
            result = await self.shopping_graph.process_message(
                user_input=user_input,
                user_id=user_id,
                family_id=family_id,
                chat_history=chat_history
            )
        elif domain == "budget":
            result = await self.budget_graph.process_message(
                user_input=user_input,
                user_id=user_id,
                family_id=family_id,
                chat_history=chat_history
            )
        else:
            # Для всех остальных доменов используем общий граф
            result = await self.general_graph.process_message(
                user_input=user_input,
                user_id=user_id,
                family_id=family_id,
                chat_history=chat_history
            )
        
        # Если специализированный граф не вернул результат,
        # или результат не содержит ответа, используем общий граф
        if not result or "response" not in result:
            logger.info(f"Специализированный граф '{domain}' не обработал запрос, используем общий граф")
            result = await self.general_graph.process_message(
                user_input=user_input,
                user_id=user_id,
                family_id=family_id,
                chat_history=chat_history
            )
        
        # Добавляем информацию о классификации к результату
        if result:
            result.update(intent_classification)
        
        return result

    async def _classify_intent(
        self,
        user_input: str,
        chat_history: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """
        Классифицирует запрос пользователя для определения домена.
        
        Args:
            user_input: Текст запроса пользователя
            chat_history: История диалога
            
        Returns:
            Словарь с информацией о классификации (домен, уверенность, объяснение)
        """
        # Формируем системное сообщение для LLM
        system_message = """
        Ты — классификатор текста, который определяет, к какому домену относится запрос пользователя.
        
        Доступные домены:
        - task_management: создание, изменение и отслеживание задач, напоминаний и событий
        - shopping: работа со списком покупок, добавление товаров, управление списками
        - budget: управление бюджетом, расходами, доходами, финансовыми целями
        - family: управление семьей и её участниками
        - general: общие вопросы и разговоры, которые не относятся к перечисленным выше категориям
        
        Верни только JSON-объект с доменом, уверенностью и объяснением.
        """
        
        # Формируем контекст из истории диалога (последних 2 сообщений)
        context = ""
        recent_history = chat_history[-2:] if len(chat_history) >= 2 else chat_history
        if recent_history:
            context = "Недавняя история диалога:\n"
            for msg in recent_history:
                role = "Пользователь" if msg["role"] == "user" else "Ассистент"
                context += f"{role}: {msg['content']}\n"
        
        # Формируем промпт для LLM
        prompt = f"""
        {context}
        
        Запрос пользователя: {user_input}
        
        Определи домен запроса из списка доступных доменов и верни ответ в формате JSON:
        {{
            "domain": "название_домена",
            "confidence": число_от_0_до_1,
            "explanation": "краткое_объяснение"
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
            
            # Проверяем корректность результата
            if "domain" not in result or "confidence" not in result:
                raise ValueError("Неполный результат классификации")
                
            return result
        except Exception as e:
            logger.error(f"Ошибка при классификации запроса: {str(e)}")
            # В случае ошибки возвращаем общий домен с низкой уверенностью
            return {
                "domain": "general",
                "confidence": 0.3,
                "explanation": f"Ошибка классификации: {str(e)}"
            }