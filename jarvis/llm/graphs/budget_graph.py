import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Any, Optional, TypedDict, Union
from enum import Enum

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, END

from jarvis.llm.models import LLMService
from jarvis.llm.chains.budget import (
    BudgetIntentClassifier, 
    TransactionExtractor,
    BudgetDataExtractor,
    FinancialGoalExtractor,
    BudgetResponseGenerator
)
from jarvis.storage.relational.budget import (
    TransactionRepository,
    BudgetRepository,
    FinancialGoalRepository
)
from jarvis.core.models.budget import (
    BudgetCategory, TransactionType, RecurringFrequency,
    GoalPriority, Transaction, Budget, FinancialGoal
)

logger = logging.getLogger(__name__)


class BudgetState(str, Enum):
    """Состояния в графе обработки запросов к бюджету."""
    
    START = "start"
    CLASSIFY_INTENT = "classify_intent"
    EXTRACT_TRANSACTION = "extract_transaction"
    EXTRACT_BUDGET_DATA = "extract_budget_data"
    EXTRACT_GOAL_DATA = "extract_goal_data"
    PROCESS_BUDGET_ACTION = "process_budget_action"
    GENERATE_RESPONSE = "generate_response"
    END = "end"


# Определяем схему состояния для StateGraph
class BudgetStateDict(TypedDict, total=False):
    """Определение схемы состояния для графа бюджета."""
    
    user_input: str
    user_id: str
    family_id: str
    chat_history: List[Dict[str, str]]
    intent: str
    intent_confidence: float
    transaction_data: Optional[Dict[str, Any]]
    budget_data: Optional[Dict[str, Any]]
    goal_data: Optional[Dict[str, Any]]
    period: Optional[Dict[str, Any]]
    operation_result: str
    operation_metadata: Dict[str, Any]
    response: str


class BudgetGraph:
    """Граф для обработки запросов к бюджету."""
    
    def __init__(
        self,
        llm_service: Optional[LLMService] = None,
        transaction_repository: Optional[TransactionRepository] = None,
        budget_repository: Optional[BudgetRepository] = None,
        goal_repository: Optional[FinancialGoalRepository] = None
    ):
        """
        Инициализация графа обработки запросов к бюджету.
        
        Args:
            llm_service: Сервис LLM для использования в графе
            transaction_repository: Репозиторий для работы с транзакциями
            budget_repository: Репозиторий для работы с бюджетами
            goal_repository: Репозиторий для работы с финансовыми целями
        """
        self.llm_service = llm_service or LLMService()
        self.transaction_repository = transaction_repository or TransactionRepository()
        self.budget_repository = budget_repository or BudgetRepository()
        self.goal_repository = goal_repository or FinancialGoalRepository()
        
        # Инициализация цепочек
        self.intent_classifier = BudgetIntentClassifier(self.llm_service)
        self.transaction_extractor = TransactionExtractor(self.llm_service)
        self.budget_extractor = BudgetDataExtractor(self.llm_service)
        self.goal_extractor = FinancialGoalExtractor(self.llm_service)
        self.response_generator = BudgetResponseGenerator(self.llm_service)
        
        # Создание графа
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """Создает и возвращает граф состояний для обработки запросов к бюджету."""
        # Определяем граф с начальным состоянием и схемой состояния
        graph = StateGraph(state_schema=BudgetStateDict)
        
        # Добавляем узлы в граф
        graph.add_node(BudgetState.START, self._start_node)
        graph.add_node(BudgetState.CLASSIFY_INTENT, self._classify_intent)
        graph.add_node(BudgetState.EXTRACT_TRANSACTION, self._extract_transaction)
        graph.add_node(BudgetState.EXTRACT_BUDGET_DATA, self._extract_budget_data)
        graph.add_node(BudgetState.EXTRACT_GOAL_DATA, self._extract_goal_data)
        graph.add_node(BudgetState.PROCESS_BUDGET_ACTION, self._process_budget_action)
        graph.add_node(BudgetState.GENERATE_RESPONSE, self._generate_response)
        
        # Определяем ребра (переходы) в графе
        graph.add_edge(BudgetState.START, BudgetState.CLASSIFY_INTENT)
        
        # Условные переходы от классификации намерения
        graph.add_conditional_edges(
            BudgetState.CLASSIFY_INTENT,
            self._route_by_intent,
            {
                # Эти ключи должны точно соответствовать возвращаемым значениям метода _route_by_intent
                "needs_transaction_extraction": BudgetState.EXTRACT_TRANSACTION,
                "needs_budget_extraction": BudgetState.EXTRACT_BUDGET_DATA,
                "needs_goal_extraction": BudgetState.EXTRACT_GOAL_DATA,
                "direct_action": BudgetState.PROCESS_BUDGET_ACTION,
                "not_budget_related": END
            }
        )
        
        # Остальные переходы
        graph.add_edge(BudgetState.EXTRACT_TRANSACTION, BudgetState.PROCESS_BUDGET_ACTION)
        graph.add_edge(BudgetState.EXTRACT_BUDGET_DATA, BudgetState.PROCESS_BUDGET_ACTION)
        graph.add_edge(BudgetState.EXTRACT_GOAL_DATA, BudgetState.PROCESS_BUDGET_ACTION)
        graph.add_edge(BudgetState.PROCESS_BUDGET_ACTION, BudgetState.GENERATE_RESPONSE)
        graph.add_edge(BudgetState.GENERATE_RESPONSE, END)
        
        # Устанавливаем начальный узел
        graph.set_entry_point(BudgetState.START)
        
        return graph.compile()
    
    async def _start_node(self, state: BudgetStateDict) -> BudgetStateDict:
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
    
    async def _classify_intent(self, state: BudgetStateDict) -> BudgetStateDict:
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
            
            # Сохраняем извлеченные данные, если они есть
            if intent_result.transaction_data:
                state["transaction_data"] = intent_result.transaction_data.dict()
            
            if intent_result.budget_data:
                state["budget_data"] = intent_result.budget_data.dict()
            
            if intent_result.goal_data:
                state["goal_data"] = intent_result.goal_data.dict()
            
            if intent_result.period:
                state["period"] = intent_result.period
            
            logger.info(f"Классифицировано намерение: {intent_result.intent} с уверенностью {intent_result.confidence}")
            
            return state
        except Exception as e:
            logger.error(f"Ошибка при классификации намерения: {str(e)}")
            # В случае ошибки устанавливаем базовое намерение
            state["intent"] = "other"
            state["intent_confidence"] = 0.5
            return state
    
    def _route_by_intent(self, state: BudgetStateDict) -> str:
        """
        Определяет следующий узел на основе классифицированного намерения.
        
        Args:
            state: Текущее состояние
            
        Returns:
            Имя следующего узла
        """
        intent = state.get("intent", "other")
        confidence = state.get("intent_confidence", 0.0)
        
        # Если уверенность низкая или намерение не связано с бюджетом, завершаем обработку
        if confidence < 0.6 or intent == "other":
            return "not_budget_related"
        
        # Определяем, требует ли намерение дополнительного извлечения данных
        transaction_intents = ["add_expense", "add_income"]
        budget_intents = ["create_budget", "update_budget"]
        goal_intents = ["create_goal", "update_goal"]
        
        # Проверяем наличие необходимых данных
        if intent in transaction_intents and "transaction_data" not in state:
            return "needs_transaction_extraction"
        elif intent in budget_intents and "budget_data" not in state:
            return "needs_budget_extraction"
        elif intent in goal_intents and "goal_data" not in state:
            return "needs_goal_extraction"
        else:
            return "direct_action"
    
    async def _extract_transaction(self, state: BudgetStateDict) -> BudgetStateDict:
        """
        Узел извлечения информации о транзакции.
        
        Args:
            state: Текущее состояние
            
        Returns:
            Обновленное состояние с извлеченной информацией о транзакции
        """
        try:
            # Получаем текст пользователя из состояния
            user_text = state["user_input"]
            
            # Извлекаем информацию о транзакции
            transaction_data = await self.transaction_extractor.process(user_text)
            
            # Обновляем состояние
            state["transaction_data"] = transaction_data.dict()
            
            logger.info(f"Извлечена информация о транзакции: {transaction_data.description}")
            
            return state
        except Exception as e:
            logger.error(f"Ошибка при извлечении информации о транзакции: {str(e)}")
            # В случае ошибки устанавливаем базовые данные о транзакции
            state["transaction_data"] = {
                "amount": 0.0,
                "transaction_type": TransactionType.EXPENSE.value,
                "description": "Неизвестная транзакция",
                "date": None
            }
            return state
    
    async def _extract_budget_data(self, state: BudgetStateDict) -> BudgetStateDict:
        """
        Узел извлечения информации о бюджете.
        
        Args:
            state: Текущее состояние
            
        Returns:
            Обновленное состояние с извлеченной информацией о бюджете
        """
        try:
            # Получаем текст пользователя из состояния
            user_text = state["user_input"]
            
            # Извлекаем информацию о бюджете
            budget_data = await self.budget_extractor.process(user_text)
            
            # Обновляем состояние
            state["budget_data"] = budget_data.dict()
            
            logger.info(f"Извлечена информация о бюджете: {budget_data.period}")
            
            return state
        except Exception as e:
            logger.error(f"Ошибка при извлечении информации о бюджете: {str(e)}")
            # В случае ошибки устанавливаем базовые данные о бюджете
            state["budget_data"] = {
                "name": None,
                "period": "текущий месяц",
                "income_plan": None,
                "category_limits": {}
            }
            return state
    
    async def _extract_goal_data(self, state: BudgetStateDict) -> BudgetStateDict:
        """
        Узел извлечения информации о финансовой цели.
        
        Args:
            state: Текущее состояние
            
        Returns:
            Обновленное состояние с извлеченной информацией о финансовой цели
        """
        try:
            # Получаем текст пользователя из состояния
            user_text = state["user_input"]
            
            # Извлекаем информацию о финансовой цели
            goal_data = await self.goal_extractor.process(user_text)
            
            # Обновляем состояние
            state["goal_data"] = goal_data.dict()
            
            logger.info(f"Извлечена информация о финансовой цели: {goal_data.name}")
            
            return state
        except Exception as e:
            logger.error(f"Ошибка при извлечении информации о финансовой цели: {str(e)}")
            # В случае ошибки устанавливаем базовые данные о финансовой цели
            state["goal_data"] = {
                "name": "Финансовая цель",
                "target_amount": 0.0,
                "deadline": None,
                "priority": GoalPriority.MEDIUM.value,
                "notes": None
            }
            return state
    
    async def _process_budget_action(self, state: BudgetStateDict) -> BudgetStateDict:
        """
        Узел обработки действия с бюджетом.
        
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
            
            operation_result = "успешно"
            operation_metadata = {}
            
            # Обработка различных намерений
            if intent == "add_expense":
                # Добавление расхода
                transaction_data = state.get("transaction_data", {})
                
                if transaction_data.get("amount", 0.0) <= 0:
                    operation_result = "не удалось определить сумму расхода"
                else:
                    # Создаем транзакцию
                    category = BudgetCategory(transaction_data.get("category", BudgetCategory.OTHER.value))
                    transaction = await self.transaction_repository.create_expense(
                        amount=Decimal(str(transaction_data.get("amount", 0.0))),
                        category=category,
                        description=transaction_data.get("description", "Расход"),
                        family_id=family_id,
                        created_by=user_id,
                        date=datetime.now() if not transaction_data.get("date") else datetime.fromisoformat(transaction_data.get("date")),
                        is_recurring=transaction_data.get("is_recurring", False),
                        recurring_frequency=transaction_data.get("recurring_frequency")
                    )
                    
                    # Добавляем транзакцию в текущий бюджет
                    current_budget = await self.budget_repository.get_current_budget(family_id)
                    if current_budget:
                        await self.budget_repository.add_transaction_to_budget(
                            budget_id=current_budget.id,
                            transaction=transaction
                        )
                        
                        # Получаем оставшийся бюджет по категории
                        if category in current_budget.category_budgets:
                            category_budget = current_budget.category_budgets[category]
                            operation_metadata["category"] = category.value
                            operation_metadata["spent"] = str(category_budget.spent)
                            operation_metadata["limit"] = str(category_budget.limit)
                            operation_metadata["remaining"] = str(category_budget.get_remaining())
                            operation_metadata["is_exceeded"] = category_budget.is_exceeded()
                    
                    operation_metadata["transaction_id"] = transaction.id
                    operation_metadata["amount"] = str(transaction.amount)
                    operation_metadata["description"] = transaction.description
            
            elif intent == "add_income":
                # Добавление дохода
                transaction_data = state.get("transaction_data", {})
                
                if transaction_data.get("amount", 0.0) <= 0:
                    operation_result = "не удалось определить сумму дохода"
                else:
                    # Создаем транзакцию
                    transaction = await self.transaction_repository.create_income(
                        amount=Decimal(str(transaction_data.get("amount", 0.0))),
                        description=transaction_data.get("description", "Доход"),
                        family_id=family_id,
                        created_by=user_id,
                        date=datetime.now() if not transaction_data.get("date") else datetime.fromisoformat(transaction_data.get("date")),
                        is_recurring=transaction_data.get("is_recurring", False),
                        recurring_frequency=transaction_data.get("recurring_frequency")
                    )
                    
                    # Добавляем транзакцию в текущий бюджет
                    current_budget = await self.budget_repository.get_current_budget(family_id)
                    if current_budget:
                        await self.budget_repository.add_transaction_to_budget(
                            budget_id=current_budget.id,
                            transaction=transaction
                        )
                        
                        # Добавляем информацию о бюджете
                        operation_metadata["budget_id"] = current_budget.id
                        operation_metadata["budget_name"] = current_budget.name
                        operation_metadata["income_actual"] = str(current_budget.income_actual)
                        operation_metadata["balance"] = str(current_budget.get_current_balance())
                    
                    operation_metadata["transaction_id"] = transaction.id
                    operation_metadata["amount"] = str(transaction.amount)
                    operation_metadata["description"] = transaction.description
            
            elif intent == "view_budget":
                # Просмотр текущего бюджета
                current_budget = await self.budget_repository.get_current_budget(family_id)
                
                if not current_budget:
                    operation_result = "нет активного бюджета"
                else:
                    # Формируем информацию о бюджете
                    operation_metadata["budget_id"] = current_budget.id
                    operation_metadata["budget_name"] = current_budget.name
                    operation_metadata["period_start"] = current_budget.period_start.isoformat()
                    operation_metadata["period_end"] = current_budget.period_end.isoformat()
                    operation_metadata["income_plan"] = str(current_budget.income_plan)
                    operation_metadata["income_actual"] = str(current_budget.income_actual)
                    operation_metadata["total_spent"] = str(current_budget.get_total_spent())
                    operation_metadata["total_budget"] = str(current_budget.get_total_budget())
                    operation_metadata["balance"] = str(current_budget.get_current_balance())
                    
                    # Добавляем информацию о категориях
                    category_stats = current_budget.get_category_stats()
                    if category_stats:
                        operation_metadata["categories"] = [
                            {
                                "category": stat["category"].value,
                                "category_name": stat["category_name"],
                                "spent": str(stat["spent"]),
                                "limit": str(stat["limit"]),
                                "progress": stat["progress"],
                                "is_exceeded": stat["is_exceeded"]
                            }
                            for stat in category_stats
                        ]
            
            elif intent == "create_budget":
                # Создание нового бюджета
                budget_data = state.get("budget_data", {})
                
                # Определяем период бюджета
                now = datetime.now()
                period = budget_data.get("period", "текущий месяц").lower()
                
                if "текущий месяц" in period or "этот месяц" in period:
                    year, month = now.year, now.month
                elif "следующий месяц" in period:
                    if now.month == 12:
                        year, month = now.year + 1, 1
                    else:
                        year, month = now.year, now.month + 1
                else:
                    # Пытаемся извлечь месяц и год из текста
                    month_names = {
                        "январь": 1, "февраль": 2, "март": 3, "апрель": 4,
                        "май": 5, "июнь": 6, "июль": 7, "август": 8,
                        "сентябрь": 9, "октябрь": 10, "ноябрь": 11, "декабрь": 12
                    }
                    
                    month, year = now.month, now.year
                    for month_name, month_num in month_names.items():
                        if month_name in period.lower():
                            month = month_num
                            break
                
                # Создаем бюджет
                income_plan = Decimal(str(budget_data.get("income_plan", 0.0))) if budget_data.get("income_plan") else Decimal('0')
                category_limits = {}
                
                if "category_limits" in budget_data and budget_data["category_limits"]:
                    for category_value, limit in budget_data["category_limits"].items():
                        try:
                            category = BudgetCategory(category_value)
                            category_limits[category] = Decimal(str(limit))
                        except (ValueError, TypeError):
                            # Игнорируем некорректные категории или лимиты
                            pass
                
                budget = await self.budget_repository.create_monthly_budget(
                    year=year,
                    month=month,
                    family_id=family_id,
                    created_by=user_id,
                    income_plan=income_plan,
                    name=budget_data.get("name"),
                    category_limits=category_limits
                )
                
                operation_metadata["budget_id"] = budget.id
                operation_metadata["budget_name"] = budget.name
                operation_metadata["period_start"] = budget.period_start.isoformat()
                operation_metadata["period_end"] = budget.period_end.isoformat()
                operation_metadata["income_plan"] = str(budget.income_plan)
                
                if category_limits:
                    operation_metadata["category_limits"] = [
                        {
                            "category": category.value,
                            "limit": str(limit)
                        }
                        for category, limit in category_limits.items()
                    ]
            
            elif intent == "update_budget":
                # Обновление бюджета
                budget_data = state.get("budget_data", {})
                
                # Получаем текущий бюджет
                current_budget = await self.budget_repository.get_current_budget(family_id)
                
                if not current_budget:
                    operation_result = "нет активного бюджета"
                else:
                    updates = {}
                    
                    # Обновляем название, если указано
                    if budget_data.get("name"):
                        updates["name"] = budget_data.get("name")
                    
                    # Обновляем планируемый доход, если указан
                    if budget_data.get("income_plan"):
                        updates["income_plan"] = Decimal(str(budget_data.get("income_plan")))
                    
                    # Обновляем бюджет
                    if updates:
                        updated_budget = await self.budget_repository.update_budget(
                            budget_id=current_budget.id,
                            **updates
                        )
                        
                        operation_metadata["budget_id"] = updated_budget.id
                        operation_metadata["updates"] = list(updates.keys())
                    
                    # Обновляем лимиты по категориям, если указаны
                    updated_categories = []
                    if "category_limits" in budget_data and budget_data["category_limits"]:
                        for category_value, limit in budget_data["category_limits"].items():
                            try:
                                category = BudgetCategory(category_value)
                                success = await self.budget_repository.update_category_limit(
                                    budget_id=current_budget.id,
                                    category=category,
                                    limit=Decimal(str(limit))
                                )
                                
                                if success:
                                    updated_categories.append(category.value)
                            except (ValueError, TypeError):
                                # Игнорируем некорректные категории или лимиты
                                pass
                    
                    if updated_categories:
                        operation_metadata["updated_categories"] = updated_categories
            
            elif intent == "view_transactions":
                # Просмотр транзакций
                # Определяем период для фильтрации
                start_date, end_date = None, None
                period = state.get("period", {})
                
                if period:
                    start_date = period.get("start_date")
                    end_date = period.get("end_date")
                
                # По умолчанию показываем транзакции за текущий месяц
                if not start_date:
                    now = datetime.now()
                    start_date = datetime(now.year, now.month, 1, 0, 0, 0)
                    # Конец текущего месяца
                    if now.month == 12:
                        end_date = datetime(now.year + 1, 1, 1, 0, 0, 0)
                    else:
                        end_date = datetime(now.year, now.month + 1, 1, 0, 0, 0)
                    end_date = end_date - timedelta(seconds=1)
                
                # Получаем статистику по транзакциям
                stats = await self.transaction_repository.get_transactions_stats(
                    family_id=family_id,
                    start_date=start_date,
                    end_date=end_date
                )
                
                # Получаем последние транзакции
                transactions = await self.transaction_repository.get_transactions_for_family(
                    family_id=family_id,
                    start_date=start_date,
                    end_date=end_date,
                    limit=10  # Ограничиваем количество транзакций
                )
                
                if not transactions:
                    operation_result = "нет транзакций за указанный период"
                else:
                    operation_metadata["period_start"] = start_date.isoformat()
                    operation_metadata["period_end"] = end_date.isoformat()
                    operation_metadata["transaction_count"] = len(transactions)
                    operation_metadata["total_income"] = str(stats["total_income"])
                    operation_metadata["total_expense"] = str(stats["total_expense"])
                    operation_metadata["balance"] = str(stats["balance"])
                    
                    # Добавляем категории расходов
                    if stats["categories"]:
                        operation_metadata["expense_categories"] = [
                            {
                                "category": category_stat["category"].value,
                                "category_name": category_stat["category_name"],
                                "amount": str(category_stat["amount"]),
                                "percentage": category_stat["percentage"]
                            }
                            for category_stat in stats["categories"]
                        ]
                    
                    # Добавляем последние транзакции
                    operation_metadata["latest_transactions"] = [
                        {
                            "id": transaction.id,
                            "date": transaction.date.isoformat(),
                            "type": transaction.transaction_type.value,
                            "category": transaction.category.value,
                            "description": transaction.description,
                            "amount": str(transaction.amount)
                        }
                        for transaction in transactions[:5]  # Только 5 последних
                    ]
            
            elif intent == "create_goal":
                # Создание финансовой цели
                goal_data = state.get("goal_data", {})
                
                if goal_data.get("target_amount", 0.0) <= 0:
                    operation_result = "не удалось определить целевую сумму"
                else:
                    # Преобразуем дедлайн в datetime, если указан
                    deadline = None
                    if goal_data.get("deadline"):
                        try:
                            deadline = datetime.fromisoformat(goal_data.get("deadline"))
                        except (ValueError, TypeError):
                            # Если не удалось распарсить дедлайн, оставляем None
                            pass
                    
                    # Создаем финансовую цель
                    goal = await self.goal_repository.create_goal(
                        name=goal_data.get("name", "Финансовая цель"),
                        target_amount=Decimal(str(goal_data.get("target_amount", 0.0))),
                        family_id=family_id,
                        created_by=user_id,
                        deadline=deadline,
                        priority=GoalPriority(goal_data.get("priority", GoalPriority.MEDIUM.value)),
                        notes=goal_data.get("notes")
                    )
                    
                    operation_metadata["goal_id"] = goal.id
                    operation_metadata["goal_name"] = goal.name
                    operation_metadata["target_amount"] = str(goal.target_amount)
                    
                    if deadline:
                        operation_metadata["deadline"] = deadline.isoformat()
                        
                        # Рассчитываем ежемесячный взнос
                        monthly_contribution = goal.calculate_monthly_contribution()
                        if monthly_contribution:
                            operation_metadata["monthly_contribution"] = str(monthly_contribution)
            
            elif intent == "update_goal":
                # Обновление финансовой цели
                goal_data = state.get("goal_data", {})
                
                # Получаем список активных целей
                goals = await self.goal_repository.get_goals_for_family(
                    family_id=family_id,
                    include_completed=False
                )
                
                if not goals:
                    operation_result = "нет активных финансовых целей"
                else:
                    # Ищем цель по названию
                    found_goal = None
                    for goal in goals:
                        if goal_data.get("name", "").lower() in goal.name.lower():
                            found_goal = goal
                            break
                    
                    if not found_goal:
                        operation_result = f"не найдена цель с названием '{goal_data.get('name', '')}'"
                    else:
                        updates = {}
                        
                        # Обновляем целевую сумму, если указана и больше 0
                        if goal_data.get("target_amount", 0.0) > 0:
                            updates["target_amount"] = Decimal(str(goal_data.get("target_amount")))
                        
                        # Обновляем дедлайн, если указан
                        if goal_data.get("deadline"):
                            try:
                                deadline = datetime.fromisoformat(goal_data.get("deadline"))
                                updates["deadline"] = deadline
                            except (ValueError, TypeError):
                                # Если не удалось распарсить дедлайн, игнорируем
                                pass
                        
                        # Обновляем приоритет
                        if goal_data.get("priority"):
                            try:
                                updates["priority"] = GoalPriority(goal_data.get("priority"))
                            except ValueError:
                                # Если не удалось преобразовать приоритет, игнорируем
                                pass
                        
                        # Обновляем заметки, если указаны
                        if goal_data.get("notes"):
                            updates["notes"] = goal_data.get("notes")
                        
                        # Обновляем цель
                        if updates:
                            updated_goal = await self.goal_repository.update_goal(
                                goal_id=found_goal.id,
                                **updates
                            )
                            
                            operation_metadata["goal_id"] = updated_goal.id
                            operation_metadata["updates"] = list(updates.keys())
                        else:
                            operation_result = "не указаны параметры для обновления"
            
            elif intent == "view_goals":
                # Просмотр финансовых целей
                # Получаем список целей
                active_goals = await self.goal_repository.get_goals_for_family(
                    family_id=family_id,
                    include_completed=False
                )
                
                completed_goals = await self.goal_repository.get_goals_for_family(
                    family_id=family_id,
                    include_completed=True
                )
                completed_goals = [goal for goal in completed_goals if goal.is_completed()]
                
                if not active_goals and not completed_goals:
                    operation_result = "нет финансовых целей"
                else:
                    operation_metadata["active_goals_count"] = len(active_goals)
                    operation_metadata["completed_goals_count"] = len(completed_goals)
                    
                    # Добавляем информацию об активных целях
                    if active_goals:
                        operation_metadata["active_goals"] = [
                            {
                                "id": goal.id,
                                "name": goal.name,
                                "target_amount": str(goal.target_amount),
                                "current_amount": str(goal.current_amount),
                                "progress": goal.get_progress_percentage(),
                                "deadline": goal.deadline.isoformat() if goal.deadline else None,
                                "priority": goal.priority.value
                            }
                            for goal in active_goals
                        ]
                    
                    # Добавляем информацию о завершенных целях
                    if completed_goals:
                        operation_metadata["completed_goals"] = [
                            {
                                "id": goal.id,
                                "name": goal.name,
                                "target_amount": str(goal.target_amount),
                                "completed_at": goal.updated_at.isoformat() if goal.updated_at else None
                            }
                            for goal in completed_goals[:3]  # Только 3 последних завершенных цели
                        ]
            
            elif intent == "view_reports":
                # Просмотр финансовых отчетов
                # Определяем период для отчета
                start_date, end_date = None, None
                period = state.get("period", {})
                
                if period:
                    start_date = period.get("start_date")
                    end_date = period.get("end_date")
                
                # По умолчанию показываем отчет за текущий месяц
                if not start_date:
                    now = datetime.now()
                    start_date = datetime(now.year, now.month, 1, 0, 0, 0)
                    # Конец текущего месяца
                    if now.month == 12:
                        end_date = datetime(now.year + 1, 1, 1, 0, 0, 0)
                    else:
                        end_date = datetime(now.year, now.month + 1, 1, 0, 0, 0)
                    end_date = end_date - timedelta(seconds=1)
                
                # Получаем статистику по транзакциям
                stats = await self.transaction_repository.get_transactions_stats(
                    family_id=family_id,
                    start_date=start_date,
                    end_date=end_date
                )
                
                if stats["transaction_count"] == 0:
                    operation_result = "нет транзакций за указанный период"
                else:
                    operation_metadata["period_start"] = start_date.isoformat()
                    operation_metadata["period_end"] = end_date.isoformat()
                    operation_metadata["total_income"] = str(stats["total_income"])
                    operation_metadata["total_expense"] = str(stats["total_expense"])
                    operation_metadata["balance"] = str(stats["balance"])
                    
                    # Рассчитываем процент экономии/перерасхода
                    balance = stats["balance"]
                    savings_percentage = 0
                    if stats["total_income"] > 0:
                        savings_percentage = (balance / stats["total_income"]) * 100
                    
                    operation_metadata["savings_percentage"] = savings_percentage
                    operation_metadata["is_overspent"] = balance < 0
                    
                    # Добавляем категории расходов
                    if stats["categories"]:
                        operation_metadata["expense_categories"] = [
                            {
                                "category": category_stat["category"].value,
                                "category_name": category_stat["category_name"],
                                "amount": str(category_stat["amount"]),
                                "percentage": category_stat["percentage"]
                            }
                            for category_stat in stats["categories"]
                        ]
            
            # Обновляем состояние
            state["operation_result"] = operation_result
            state["operation_metadata"] = operation_metadata
            
            logger.info(f"Обработано намерение {intent} с результатом: {operation_result}")
            
            return state
        except Exception as e:
            logger.error(f"Ошибка при обработке действия с бюджетом: {str(e)}")
            state["operation_result"] = "произошла ошибка"
            state["operation_metadata"] = {"error": str(e)}
            return state
    
    async def _generate_response(self, state: BudgetStateDict) -> BudgetStateDict:
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
            
            # Формируем дополнительную информацию в зависимости от намерения
            additional_info = ""
            
            if intent == "add_expense":
                # Информация о добавленном расходе
                if operation_result == "успешно":
                    amount = metadata.get("amount", "0")
                    description = metadata.get("description", "")
                    category = metadata.get("category")
                    
                    additional_info = f"Добавлен расход: {amount} ₽ - {description}\n"
                    
                    if category:
                        category_name = BudgetCategory.get_ru_name(BudgetCategory(category))
                        additional_info += f"Категория: {category_name}\n"
                    
                    # Информация о бюджете
                    if "spent" in metadata and "limit" in metadata:
                        spent = metadata.get("spent", "0")
                        limit = metadata.get("limit", "0")
                        remaining = metadata.get("remaining", "0")
                        is_exceeded = metadata.get("is_exceeded", False)
                        
                        additional_info += f"Потрачено в категории: {spent} из {limit} ₽\n"
                        additional_info += f"Осталось: {remaining} ₽\n"
                        
                        if is_exceeded:
                            additional_info += "⚠️ Внимание: лимит по этой категории превышен!"
            
            elif intent == "add_income":
                # Информация о добавленном доходе
                if operation_result == "успешно":
                    amount = metadata.get("amount", "0")
                    description = metadata.get("description", "")
                    
                    additional_info = f"Добавлен доход: {amount} ₽ - {description}\n"
                    
                    # Информация о бюджете
                    if "income_actual" in metadata and "balance" in metadata:
                        income_actual = metadata.get("income_actual", "0")
                        balance = metadata.get("balance", "0")
                        
                        additional_info += f"Всего доходов в текущем бюджете: {income_actual} ₽\n"
                        additional_info += f"Текущий баланс: {balance} ₽"
            
            elif intent == "view_budget":
                # Информация о текущем бюджете
                if operation_result == "успешно":
                    budget_name = metadata.get("budget_name", "Бюджет")
                    income_plan = metadata.get("income_plan", "0")
                    income_actual = metadata.get("income_actual", "0")
                    total_spent = metadata.get("total_spent", "0")
                    total_budget = metadata.get("total_budget", "0")
                    balance = metadata.get("balance", "0")
                    
                    # Форматируем даты
                    period_start = datetime.fromisoformat(metadata.get("period_start", datetime.now().isoformat()))
                    period_end = datetime.fromisoformat(metadata.get("period_end", datetime.now().isoformat()))
                    
                    additional_info = f"📊 {budget_name}\n"
                    additional_info += f"Период: {period_start.strftime('%d.%m.%Y')} - {period_end.strftime('%d.%m.%Y')}\n\n"
                    
                    additional_info += f"💰 Доходы: {income_actual} из {income_plan} ₽\n"
                    additional_info += f"💸 Расходы: {total_spent} из {total_budget} ₽\n"
                    additional_info += f"📈 Баланс: {balance} ₽\n\n"
                    
                    # Категории расходов
                    categories = metadata.get("categories", [])
                    if categories:
                        additional_info += "Расходы по категориям:\n"
                        for category in categories:
                            category_name = category.get("category_name", "")
                            spent = category.get("spent", "0")
                            limit = category.get("limit", "0")
                            progress = category.get("progress", 0)
                            is_exceeded = category.get("is_exceeded", False)
                            
                            icon = BudgetCategory.get_icon(BudgetCategory(category.get("category")))
                            status = "⚠️" if is_exceeded else ""
                            
                            additional_info += f"{icon} {category_name}: {spent}/{limit} ₽ ({progress:.1f}%) {status}\n"
            
            elif intent == "create_budget":
                # Информация о созданном бюджете
                if operation_result == "успешно":
                    budget_name = metadata.get("budget_name", "Бюджет")
                    income_plan = metadata.get("income_plan", "0")
                    
                    # Форматируем даты
                    period_start = datetime.fromisoformat(metadata.get("period_start", datetime.now().isoformat()))
                    period_end = datetime.fromisoformat(metadata.get("period_end", datetime.now().isoformat()))
                    
                    additional_info = f"✅ Создан новый бюджет: {budget_name}\n"
                    additional_info += f"Период: {period_start.strftime('%d.%m.%Y')} - {period_end.strftime('%d.%m.%Y')}\n"
                    additional_info += f"Планируемый доход: {income_plan} ₽\n\n"
                    
                    # Лимиты по категориям
                    category_limits = metadata.get("category_limits", [])
                    if category_limits:
                        additional_info += "Установлены лимиты по категориям:\n"
                        for category_limit in category_limits:
                            category = BudgetCategory(category_limit.get("category"))
                            limit = category_limit.get("limit", "0")
                            
                            icon = BudgetCategory.get_icon(category)
                            category_name = BudgetCategory.get_ru_name(category)
                            
                            additional_info += f"{icon} {category_name}: {limit} ₽\n"
            
            elif intent == "update_budget":
                # Информация об обновленном бюджете
                if operation_result == "успешно":
                    updates = metadata.get("updates", [])
                    updated_categories = metadata.get("updated_categories", [])
                    
                    additional_info = "✅ Бюджет успешно обновлен\n\n"
                    
                    if "name" in updates:
                        additional_info += f"Новое название: {metadata.get('budget_name', 'Бюджет')}\n"
                    
                    if "income_plan" in updates:
                        additional_info += f"Новый планируемый доход: {metadata.get('income_plan', '0')} ₽\n"
                    
                    if updated_categories:
                        additional_info += "\nОбновлены лимиты по категориям:\n"
                        for category_value in updated_categories:
                            category = BudgetCategory(category_value)
                            icon = BudgetCategory.get_icon(category)
                            category_name = BudgetCategory.get_ru_name(category)
                            
                            additional_info += f"{icon} {category_name}\n"
            
            elif intent == "view_transactions":
                # Информация о транзакциях
                if operation_result == "успешно":
                    # Форматируем даты
                    period_start = datetime.fromisoformat(metadata.get("period_start", datetime.now().isoformat()))
                    period_end = datetime.fromisoformat(metadata.get("period_end", datetime.now().isoformat()))
                    
                    transaction_count = metadata.get("transaction_count", 0)
                    total_income = metadata.get("total_income", "0")
                    total_expense = metadata.get("total_expense", "0")
                    balance = metadata.get("balance", "0")
                    
                    additional_info = f"📊 Транзакции за период: {period_start.strftime('%d.%m.%Y')} - {period_end.strftime('%d.%m.%Y')}\n\n"
                    additional_info += f"Всего транзакций: {transaction_count}\n"
                    additional_info += f"💰 Доходы: {total_income} ₽\n"
                    additional_info += f"💸 Расходы: {total_expense} ₽\n"
                    additional_info += f"📈 Баланс: {balance} ₽\n\n"
                    
                    # Категории расходов
                    expense_categories = metadata.get("expense_categories", [])
                    if expense_categories:
                        additional_info += "Топ категорий расходов:\n"
                        for category in expense_categories[:3]:  # Показываем только топ-3
                            category_name = category.get("category_name", "")
                            amount = category.get("amount", "0")
                            percentage = category.get("percentage", 0)
                            
                            icon = BudgetCategory.get_icon(BudgetCategory(category.get("category")))
                            
                            additional_info += f"{icon} {category_name}: {amount} ₽ ({percentage:.1f}%)\n"
                        
                        additional_info += "\n"
                    
                    # Последние транзакции
                    latest_transactions = metadata.get("latest_transactions", [])
                    if latest_transactions:
                        additional_info += "Последние транзакции:\n"
                        for transaction in latest_transactions:
                            date = datetime.fromisoformat(transaction.get("date", datetime.now().isoformat()))
                            type_value = transaction.get("type", TransactionType.EXPENSE.value)
                            category_value = transaction.get("category", BudgetCategory.OTHER.value)
                            description = transaction.get("description", "")
                            amount = transaction.get("amount", "0")
                            
                            date_str = date.strftime("%d.%m")
                            icon = "💰" if type_value == TransactionType.INCOME.value else BudgetCategory.get_icon(BudgetCategory(category_value))
                            
                            additional_info += f"{date_str} {icon} {description}: {amount} ₽\n"
            
            elif intent == "create_goal":
                # Информация о созданной финансовой цели
                if operation_result == "успешно":
                    goal_name = metadata.get("goal_name", "Финансовая цель")
                    target_amount = metadata.get("target_amount", "0")
                    
                    additional_info = f"✅ Создана финансовая цель: {goal_name}\n"
                    additional_info += f"Целевая сумма: {target_amount} ₽\n"
                    
                    # Дедлайн и ежемесячный взнос
                    if "deadline" in metadata:
                        deadline = datetime.fromisoformat(metadata.get("deadline"))
                        additional_info += f"Дедлайн: {deadline.strftime('%d.%m.%Y')}\n"
                        
                        if "monthly_contribution" in metadata:
                            monthly_contribution = metadata.get("monthly_contribution", "0")
                            additional_info += f"Рекомендуемый ежемесячный взнос: {monthly_contribution} ₽\n"
            
            elif intent == "update_goal":
                # Информация об обновленной финансовой цели
                if operation_result == "успешно":
                    updates = metadata.get("updates", [])
                    
                    additional_info = "✅ Финансовая цель успешно обновлена\n\n"
                    
                    if "target_amount" in updates:
                        additional_info += f"Новая целевая сумма: {metadata.get('target_amount', '0')} ₽\n"
                    
                    if "deadline" in updates:
                        deadline = datetime.fromisoformat(metadata.get("deadline", datetime.now().isoformat()))
                        additional_info += f"Новый дедлайн: {deadline.strftime('%d.%m.%Y')}\n"
                    
                    if "priority" in updates:
                        priority = GoalPriority(metadata.get("priority", GoalPriority.MEDIUM.value))
                        additional_info += f"Новый приоритет: {GoalPriority.get_ru_name(priority)}\n"
                    
                    if "notes" in updates:
                        additional_info += f"Новые заметки: {metadata.get('notes', '')}\n"
            
            elif intent == "view_goals":
                # Информация о финансовых целях
                if operation_result == "успешно":
                    active_goals_count = metadata.get("active_goals_count", 0)
                    completed_goals_count = metadata.get("completed_goals_count", 0)
                    
                    additional_info = f"📊 Финансовые цели\n\n"
                    
                    # Активные цели
                    active_goals = metadata.get("active_goals", [])
                    if active_goals:
                        additional_info += f"Активные цели ({active_goals_count}):\n"
                        for goal in active_goals:
                            name = goal.get("name", "")
                            current_amount = goal.get("current_amount", "0")
                            target_amount = goal.get("target_amount", "0")
                            progress = goal.get("progress", 0)
                            
                            priority = GoalPriority(goal.get("priority", GoalPriority.MEDIUM.value))
                            priority_icon = "🔴" if priority == GoalPriority.URGENT else "🔵" if priority == GoalPriority.HIGH else "🟢"
                            
                            progress_bar = "▓" * int(progress / 10) + "░" * (10 - int(progress / 10))
                            
                            additional_info += f"{priority_icon} {name}: {current_amount}/{target_amount} ₽ [{progress_bar}] {progress:.1f}%\n"
                            
                            # Дедлайн
                            if goal.get("deadline"):
                                deadline = datetime.fromisoformat(goal.get("deadline"))
                                days_left = (deadline - datetime.now()).days
                                
                                if days_left > 0:
                                    additional_info += f"   Осталось дней: {days_left}\n"
                                else:
                                    additional_info += f"   ⚠️ Дедлайн просрочен!\n"
                            
                            additional_info += "\n"
                    
                    # Завершенные цели
                    completed_goals = metadata.get("completed_goals", [])
                    if completed_goals:
                        additional_info += f"\nЗавершенные цели ({completed_goals_count}):\n"
                        for goal in completed_goals:
                            name = goal.get("name", "")
                            target_amount = goal.get("target_amount", "0")
                            
                            additional_info += f"✅ {name}: {target_amount} ₽\n"
            
            elif intent == "view_reports":
                # Информация о финансовом отчете
                if operation_result == "успешно":
                    # Форматируем даты
                    period_start = datetime.fromisoformat(metadata.get("period_start", datetime.now().isoformat()))
                    period_end = datetime.fromisoformat(metadata.get("period_end", datetime.now().isoformat()))
                    
                    total_income = metadata.get("total_income", "0")
                    total_expense = metadata.get("total_expense", "0")
                    balance = metadata.get("balance", "0")
                    savings_percentage = metadata.get("savings_percentage", 0)
                    is_overspent = metadata.get("is_overspent", False)
                    
                    additional_info = f"📊 Финансовый отчет за период: {period_start.strftime('%d.%m.%Y')} - {period_end.strftime('%d.%m.%Y')}\n\n"
                    
                    # Общая статистика
                    additional_info += f"💰 Доходы: {total_income} ₽\n"
                    additional_info += f"💸 Расходы: {total_expense} ₽\n"
                    
                    # Баланс и экономия/перерасход
                    balance_sign = "+" if not is_overspent else ""
                    additional_info += f"📈 Баланс: {balance_sign}{balance} ₽\n"
                    
                    if not is_overspent:
                        additional_info += f"🎯 Экономия: {savings_percentage:.1f}% от доходов\n\n"
                    else:
                        additional_info += f"⚠️ Перерасход: {-savings_percentage:.1f}% от доходов\n\n"
                    
                    # Категории расходов
                    expense_categories = metadata.get("expense_categories", [])
                    if expense_categories:
                        additional_info += "📊 Распределение расходов:\n"
                        for category in expense_categories:
                            category_name = category.get("category_name", "")
                            amount = category.get("amount", "0")
                            percentage = category.get("percentage", 0)
                            
                            icon = BudgetCategory.get_icon(BudgetCategory(category.get("category")))
                            
                            # Визуализация процента
                            progress_bar = "▓" * int(percentage / 10) + "░" * (10 - int(percentage / 10))
                            
                            additional_info += f"{icon} {category_name}: {amount} ₽ ({percentage:.1f}%) [{progress_bar}]\n"
                    
                    # Добавляем рекомендации
                    additional_info += "\n💡 Рекомендации:\n"
                    
                    if is_overspent:
                        # Если расходы превышают доходы
                        additional_info += "- Рассмотрите возможность сокращения расходов в категориях с наибольшими тратами\n"
                        additional_info += "- Установите бюджетные лимиты на следующий период\n"
                    elif savings_percentage < 10:
                        # Если экономия меньше 10%
                        additional_info += "- Старайтесь откладывать не менее 10-20% от доходов\n"
                        additional_info += "- Создайте финансовую цель для мотивации\n"
                    else:
                        # Если всё хорошо
                        additional_info += "- Отлично! Вы эффективно управляете финансами\n"
                        additional_info += "- Рассмотрите возможность инвестирования свободных средств\n"
            
            # Генерируем ответ
            response = await self.response_generator.process(
                intent=intent,
                operation_result=operation_result,
                additional_info=additional_info
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
        Обрабатывает сообщение пользователя через граф бюджета.
        
        Args:
            user_input: Текст пользователя
            user_id: ID пользователя
            family_id: ID семьи (если не указан, будет создан на основе user_id)
            chat_history: История чата
            
        Returns:
            Результат обработки сообщения
        """
        # Создаем начальное состояние
        initial_state: BudgetStateDict = {
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
                # что запрос не связан с бюджетом
                return {
                    "is_budget_related": False,
                    "response": None,
                    "intent": final_state.get("intent", "other"),
                    "confidence": final_state.get("intent_confidence", 0.0)
                }
            
            # Возвращаем результат
            return {
                "is_budget_related": True,
                "response": final_state["response"],
                "intent": final_state.get("intent", ""),
                "operation_result": final_state.get("operation_result", ""),
                "metadata": final_state.get("operation_metadata", {})
            }
        except Exception as e:
            logger.error(f"Ошибка при выполнении графа бюджета: {str(e)}")
            return {
                "is_budget_related": False,
                "response": "Произошла ошибка при обработке вашего запроса. Пожалуйста, попробуйте снова.",
                "error": str(e)
            }
