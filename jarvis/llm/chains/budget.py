"""
Цепочки LangChain для работы с финансовыми данными и бюджетом.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from decimal import Decimal
from datetime import datetime

from langchain.prompts import PromptTemplate
from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field, validator

from jarvis.llm.models import LLMService
from jarvis.llm.chains.base import BaseLangChain
from jarvis.core.models.budget import (
    BudgetCategory, TransactionType, RecurringFrequency,
    GoalPriority, Transaction, Budget, FinancialGoal
)

logger = logging.getLogger(__name__)


class TransactionData(BaseModel):
    """Модель для извлечения информации о финансовой транзакции из текста."""
    amount: Optional[float] = Field(None, description="Сумма транзакции")
    transaction_type: TransactionType = Field(description="Тип транзакции (доход/расход)")
    category: Optional[BudgetCategory] = Field(None, description="Категория транзакции")
    description: Optional[str] = Field(description="Описание транзакции")
    date: Optional[str] = Field(None, description="Дата транзакции (если указана)")
    is_recurring: bool = Field(False, description="Является ли транзакция повторяющейся")
    recurring_frequency: Optional[RecurringFrequency] = Field(None, description="Частота повторения (если повторяющаяся)")
    
    @validator("category", pre=True, always=True)
    def set_default_category(cls, v, values):
        """Устанавливает категорию по умолчанию в зависимости от типа транзакции."""
        if v is None and "transaction_type" in values:
            return BudgetCategory.INCOME if values["transaction_type"] == TransactionType.INCOME else BudgetCategory.OTHER
        return v
    
    def to_decimal_amount(self) -> Decimal:
        """Преобразует сумму в Decimal."""
        return Decimal(str(self.amount))


class BudgetData(BaseModel):
    """Модель для извлечения информации о бюджете из текста."""
    
    name: Optional[str] = Field(None, description="Название бюджета")
    period: str = Field(default="текущий месяц", description="Период бюджета")
    income_plan: Optional[float] = Field(None, description="Планируемый доход")
    category_limits: Dict[BudgetCategory, float] = Field(default_factory=dict, description="Лимиты по категориям")


class FinancialGoalData(BaseModel):
    """Модель для извлечения информации о финансовой цели из текста."""
    
    name: str = Field(description="Название цели")
    target_amount: float = Field(description="Целевая сумма")
    deadline: Optional[str] = Field(None, description="Дата дедлайна (если указана)")
    priority: GoalPriority = Field(GoalPriority.MEDIUM, description="Приоритет цели")
    notes: Optional[str] = Field(None, description="Дополнительные заметки")
    
    def to_decimal_amount(self) -> Decimal:
        """Преобразует сумму в Decimal."""
        return Decimal(str(self.target_amount))


class BudgetIntent(BaseModel):
    """Модель для классификации намерения пользователя относительно бюджета."""
    
    intent: str = Field(description="Намерение пользователя (add_transaction, view_budget, create_goal, etc.)")
    confidence: float = Field(description="Уверенность в классификации (0-1)")
    transaction_data: Optional[TransactionData] = Field(None, description="Данные о транзакции (если есть)")
    budget_data: Optional[BudgetData] = Field(None, description="Данные о бюджете (если есть)")
    goal_data: Optional[FinancialGoalData] = Field(None, description="Данные о финансовой цели (если есть)")
    period: Optional[Dict[str, Any]] = Field(None, description="Информация о периоде (для отчетов)")


class TransactionExtractor(BaseLangChain):
    """Цепочка для извлечения информации о финансовых транзакциях из текста."""
    
    PROMPT_TEMPLATE = """
    Проанализируй следующий текст пользователя и извлеки информацию о финансовой транзакции.
    
    Текст пользователя: {user_text}
    
    Определи тип транзакции (доход или расход), сумму, категорию, описание и дату (если указана).
    Также определи, является ли транзакция повторяющейся, и если да, то с какой частотой.
    
    Типы транзакций:
    - income: Доход (зарплата, подарок, возврат, процент от вклада и т.д.)
    - expense: Расход (покупка, оплата услуг, платеж и т.д.)
    
    Категории расходов:
    - food: Питание
    - housing: Жильё (аренда, ипотека)
    - transport: Транспорт
    - utilities: Коммунальные услуги
    - entertainment: Развлечения
    - healthcare: Здоровье
    - education: Образование
    - shopping: Покупки
    - savings: Сбережения
    - other: Другое
    
    Для доходов используй категорию income.
    
    Частота повторения (для повторяющихся транзакций):
    - daily: Ежедневно
    - weekly: Еженедельно
    - monthly: Ежемесячно
    - quarterly: Ежеквартально
    - yearly: Ежегодно
    
    {format_instructions}
    """
    
    def __init__(self, llm_service: Optional[LLMService] = None):
        """Инициализация цепочки извлечения информации о транзакциях."""
        super().__init__(llm_service)
        
        self.parser = PydanticOutputParser(pydantic_object=TransactionData)
        self.prompt = PromptTemplate(
            template=self.PROMPT_TEMPLATE,
            input_variables=["user_text"],
            partial_variables={"format_instructions": self.parser.get_format_instructions()}
        )
    
    async def process(self, user_text: str) -> TransactionData:
        """
        Извлекает информацию о финансовой транзакции из текста пользователя.
        
        Args:
            user_text: Текст пользователя
            
        Returns:
            Извлеченная информация о транзакции
        """
        try:
            # Форматируем промпт с текстом пользователя
            prompt_text = self.prompt.format(user_text=user_text)
            
            # Получаем ответ от LLM
            response = await self.llm_service.generate_response(
                prompt=prompt_text,
                system_message="Ты — аналитический ассистент, извлекающий информацию о финансовых транзакциях из текста."
            )
            
            # Парсим ответ в модель TransactionData
            return self.parser.parse(response)
        except Exception as e:
            logger.error(f"Ошибка при извлечении информации о транзакции: {str(e)}")
            # Возвращаем базовую информацию в случае ошибки
            return TransactionData(
                amount=0.0,
                transaction_type=TransactionType.EXPENSE,
                description=user_text,
                date=None
            )


class BudgetDataExtractor(BaseLangChain):
    """Цепочка для извлечения информации о бюджете из текста."""
    
    PROMPT_TEMPLATE = """
    Проанализируй следующий текст пользователя и извлеки информацию о бюджете.
    
    Текст пользователя: {user_text}
    
    Определи название бюджета, период бюджета, планируемый доход и лимиты по категориям расходов.
    
    Категории расходов:
    - food: Питание
    - housing: Жильё (аренда, ипотека)
    - transport: Транспорт
    - utilities: Коммунальные услуги
    - entertainment: Развлечения
    - healthcare: Здоровье
    - education: Образование
    - shopping: Покупки
    - savings: Сбережения
    - other: Другое
    
    {format_instructions}
    """
    
    def __init__(self, llm_service: Optional[LLMService] = None):
        """Инициализация цепочки извлечения информации о бюджете."""
        super().__init__(llm_service)
        
        self.parser = PydanticOutputParser(pydantic_object=BudgetData)
        self.prompt = PromptTemplate(
            template=self.PROMPT_TEMPLATE,
            input_variables=["user_text"],
            partial_variables={"format_instructions": self.parser.get_format_instructions()}
        )
    
    async def process(self, user_text: str) -> BudgetData:
        """
        Извлекает информацию о бюджете из текста пользователя.
        
        Args:
            user_text: Текст пользователя
            
        Returns:
            Извлеченная информация о бюджете
        """
        try:
            # Форматируем промпт с текстом пользователя
            prompt_text = self.prompt.format(user_text=user_text)
            
            # Получаем ответ от LLM
            response = await self.llm_service.generate_response(
                prompt=prompt_text,
                system_message="Ты — аналитический ассистент, извлекающий информацию о бюджете из текста."
            )
            
            # Парсим ответ в модель BudgetData
            return self.parser.parse(response)
        except Exception as e:
            logger.error(f"Ошибка при извлечении информации о бюджете: {str(e)}")
            # Возвращаем базовую информацию в случае ошибки
            return BudgetData(
                name=None,
                period="текущий месяц",
                income_plan=None,
                category_limits={}
            )


class FinancialGoalExtractor(BaseLangChain):
    """Цепочка для извлечения информации о финансовой цели из текста."""
    
    PROMPT_TEMPLATE = """
    Проанализируй следующий текст пользователя и извлеки информацию о финансовой цели.
    
    Текст пользователя: {user_text}
    
    Определи название цели, целевую сумму, дедлайн (если указан), приоритет и дополнительные заметки.
    
    Приоритеты:
    - low: Низкий
    - medium: Средний
    - high: Высокий
    - urgent: Срочный
    
    {format_instructions}
    """
    
    def __init__(self, llm_service: Optional[LLMService] = None):
        """Инициализация цепочки извлечения информации о финансовой цели."""
        super().__init__(llm_service)
        
        self.parser = PydanticOutputParser(pydantic_object=FinancialGoalData)
        self.prompt = PromptTemplate(
            template=self.PROMPT_TEMPLATE,
            input_variables=["user_text"],
            partial_variables={"format_instructions": self.parser.get_format_instructions()}
        )
    
    async def process(self, user_text: str) -> FinancialGoalData:
        """
        Извлекает информацию о финансовой цели из текста пользователя.
        
        Args:
            user_text: Текст пользователя
            
        Returns:
            Извлеченная информация о финансовой цели
        """
        try:
            # Форматируем промпт с текстом пользователя
            prompt_text = self.prompt.format(user_text=user_text)
            
            # Получаем ответ от LLM
            response = await self.llm_service.generate_response(
                prompt=prompt_text,
                system_message="Ты — аналитический ассистент, извлекающий информацию о финансовых целях из текста."
            )
            
            # Парсим ответ в модель FinancialGoalData
            return self.parser.parse(response)
        except Exception as e:
            logger.error(f"Ошибка при извлечении информации о финансовой цели: {str(e)}")
            # Возвращаем базовую информацию в случае ошибки
            return FinancialGoalData(
                name="Цель",
                target_amount=0.0,
                deadline=None,
                priority=GoalPriority.MEDIUM,
                notes=user_text
            )


class BudgetIntentClassifier(BaseLangChain):
    """Цепочка для классификации намерения пользователя относительно бюджета."""
    
    PROMPT_TEMPLATE = """
    Проанализируй следующий текст пользователя и определи его намерение относительно бюджета.
    
    Текст пользователя: {user_text}
    
    Возможные намерения:
    - add_expense: Добавить расход
    - add_income: Добавить доход
    - view_budget: Просмотреть бюджет
    - create_budget: Создать бюджет
    - update_budget: Обновить бюджет
    - view_transactions: Просмотреть транзакции
    - delete_transactions: Удалить транзакции
    - create_goal: Создать финансовую цель
    - update_goal: Обновить финансовую цель
    - view_goals: Просмотреть финансовые цели
    - view_reports: Просмотреть финансовые отчеты
    - other: Другое намерение, не связанное с бюджетом
    
    Также извлеки любую информацию о транзакции, бюджете или финансовой цели, если она есть в тексте.
    
    {format_instructions}
    """
    
    def __init__(self, llm_service: Optional[LLMService] = None):
        """
        Инициализация цепочки классификации намерений.
        
        Args:
            llm_service: Сервис LLM для использования в цепочке
        """
        super().__init__(llm_service)
        
        self.parser = PydanticOutputParser(pydantic_object=BudgetIntent)
        self.prompt = PromptTemplate(
            template=self.PROMPT_TEMPLATE,
            input_variables=["user_text"],
            partial_variables={"format_instructions": self.parser.get_format_instructions()}
        )
        
        # Инициализируем экстракторы для более детального извлечения данных
        self.transaction_extractor = TransactionExtractor(llm_service)
        self.budget_extractor = BudgetDataExtractor(llm_service)
        self.goal_extractor = FinancialGoalExtractor(llm_service)
    
    async def process(self, user_text: str) -> BudgetIntent:
        """
        Классифицирует намерение пользователя относительно бюджета.
        
        Args:
            user_text: Текст пользователя
            
        Returns:
            Классификация намерения
        """
        try:
            # Форматируем промпт с текстом пользователя
            prompt_text = self.prompt.format(user_text=user_text)
            
            # Получаем ответ от LLM
            response = await self.llm_service.generate_response(
                prompt=prompt_text,
                system_message="Ты — аналитический ассистент, классифицирующий намерения пользователя относительно бюджета."
            )
            
            # Парсим ответ в модель BudgetIntent
            intent_result = self.parser.parse(response)
            
            # В зависимости от намерения, извлекаем дополнительные данные
            if intent_result.intent in ["add_expense", "add_income"] and (intent_result.transaction_data is None or not intent_result.transaction_data.description):
                transaction_data = await self.transaction_extractor.process(user_text)
                intent_result.transaction_data = transaction_data
            
            elif intent_result.intent in ["create_budget", "update_budget"] and intent_result.budget_data is None:
                budget_data = await self.budget_extractor.process(user_text)
                intent_result.budget_data = budget_data
            
            elif intent_result.intent in ["create_goal", "update_goal"] and intent_result.goal_data is None:
                goal_data = await self.goal_extractor.process(user_text)
                intent_result.goal_data = goal_data
            
            return intent_result
        except Exception as e:
            logger.error(f"Ошибка при классификации намерения: {str(e)}")
            # Возвращаем базовую классификацию в случае ошибки
            return BudgetIntent(
                intent="other",
                confidence=0.5,
                transaction_data=None,
                budget_data=None,
                goal_data=None
            )


class BudgetResponseGenerator(BaseLangChain):
    """Цепочка для генерации ответов на запросы о бюджете."""
    
    PROMPT_TEMPLATE = """
    Пользователь взаимодействует со своим семейным бюджетом. Сгенерируй информативный и полезный ответ.
    
    Намерение пользователя: {intent}
    Результат операции: {operation_result}
    Дополнительная информация:
    {additional_info}
    
    # Инструкции по форматированию
    Формат бюджета:
    - Используй заголовок с эмодзи и период бюджета
    - Представь доходы/расходы в виде сравнения план/факт
    - Для категорий расходов используй прогресс-бары и цветные индикаторы
    - Включи краткую рекомендацию по управлению бюджетом в конце
    """
    
    def __init__(self, llm_service: Optional[LLMService] = None):
        """
        Инициализация цепочки генерации ответов.
        
        Args:
            llm_service: Сервис LLM для использования в цепочке
        """
        super().__init__(llm_service)
        
        self.prompt = PromptTemplate(
            template=self.PROMPT_TEMPLATE,
            input_variables=["intent", "operation_result", "additional_info"]
        )
    
    async def process(
        self,
        intent: str,
        operation_result: str,
        additional_info: str = ""
    ) -> str:
        """
        Генерирует ответ на запрос о бюджете.
        
        Args:
            intent: Намерение пользователя
            operation_result: Результат операции
            additional_info: Дополнительная информация
            
        Returns:
            Текст ответа
        """
        try:
            # Форматируем промпт с информацией
            prompt_text = self.prompt.format(
                intent=intent,
                operation_result=operation_result,
                additional_info=additional_info
            )
            
            # Получаем ответ от LLM
            response = await self.llm_service.generate_response(
                prompt=prompt_text,
                system_message="Ты — семейный финансовый ассистент, помогающий управлять бюджетом. Твои ответы должны быть дружелюбными, информативными и мотивирующими."
            )
            
            return response
        except Exception as e:
            logger.error(f"Ошибка при генерации ответа: {str(e)}")
            return "Извините, произошла ошибка при обработке запроса. Пожалуйста, попробуйте снова."


class BudgetManager:
    """Менеджер для работы с бюджетом, интегрирующий хранилище и LLM-цепочки."""
    
    def __init__(
        self,
        transaction_repository,
        budget_repository,
        goal_repository,
        llm_service: Optional[LLMService] = None
    ):
        """
        Инициализация менеджера бюджета.
        
        Args:
            transaction_repository: Репозиторий для работы с транзакциями
            budget_repository: Репозиторий для работы с бюджетами
            goal_repository: Репозиторий для работы с финансовыми целями
            llm_service: Сервис LLM для использования в цепочках
        """
        self.transaction_repository = transaction_repository
        self.budget_repository = budget_repository
        self.goal_repository = goal_repository
        self.llm_service = llm_service or LLMService()
        
        # Инициализация цепочек
        self.intent_classifier = BudgetIntentClassifier(self.llm_service)
        self.transaction_extractor = TransactionExtractor(self.llm_service)
        self.budget_extractor = BudgetDataExtractor(self.llm_service)
        self.goal_extractor = FinancialGoalExtractor(self.llm_service)
        self.response_generator = BudgetResponseGenerator(self.llm_service)
    
    async def process_message(
        self,
        user_text: str,
        family_id: str,
        user_id: str
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Обрабатывает сообщение пользователя, связанное с бюджетом.
        
        Args:
            user_text: Текст пользователя
            family_id: ID семьи пользователя
            user_id: ID пользователя
            
        Returns:
            Кортеж (ответ пользователю, метаданные операции)
        """
        try:
            # Классифицируем намерение пользователя
            intent_result = await self.intent_classifier.process(user_text)
            
            # Если намерение не связано с бюджетом, возвращаем None
            if intent_result.intent == "other" or intent_result.confidence < 0.6:
                return None, {"intent": "other", "confidence": intent_result.confidence}
            
            # Обработка различных намерений
            operation_result = "успешно"
            additional_info = ""
            metadata = {
                "intent": intent_result.intent,
                "confidence": intent_result.confidence
            }
            
            if intent_result.intent == "add_expense":
                # Добавление расхода
                transaction_data = intent_result.transaction_data
                if not transaction_data:
                    # Если в намерении нет данных о транзакции, пытаемся извлечь их из текста
                    transaction_data = await self.transaction_extractor.process(user_text)
                
                if transaction_data.amount <= 0:
                    operation_result = "не удалось определить сумму расхода"
                else:
                    # Создаем транзакцию
                    transaction = await self.transaction_repository.create_expense(
                        amount=transaction_data.to_decimal_amount(),
                        category=transaction_data.category,
                        description=transaction_data.description,
                        family_id=family_id,
                        created_by=user_id,
                        date=datetime.now() if not transaction_data.date else datetime.fromisoformat(transaction_data.date),
                        is_recurring=transaction_data.is_recurring,
                        recurring_frequency=transaction_data.recurring_frequency
                    )
                    
                    # Добавляем транзакцию в текущий бюджет
                    current_budget = await self.budget_repository.get_current_budget(family_id)
                    if current_budget:
                        await self.budget_repository.add_transaction_to_budget(
                            budget_id=current_budget.id,
                            transaction=transaction
                        )
                        
                        # Получаем оставшийся бюджет по категории
                        if transaction.category in current_budget.category_budgets:
                            category_budget = current_budget.category_budgets[transaction.category]
                            additional_info = f"Категория: {BudgetCategory.get_ru_name(transaction.category)}\n"
                            additional_info += f"Потрачено: {category_budget.spent} из {category_budget.limit} {current_budget.currency}\n"
                            additional_info += f"Осталось: {category_budget.get_remaining()} {current_budget.currency}\n"
                            
                            if category_budget.is_exceeded():
                                additional_info += "Внимание: лимит по этой категории превышен!"
                    
                    metadata["transaction_id"] = transaction.id
                    metadata["amount"] = str(transaction.amount)
                    metadata["category"] = transaction.category.value
                    metadata["description"] = transaction.description
            
            elif intent_result.intent == "add_income":
                # Добавление дохода
                transaction_data = intent_result.transaction_data
                if not transaction_data:
                    # Если в намерении нет данных о транзакции, пытаемся извлечь их из текста
                    transaction_data = await self.transaction_extractor.process(user_text)
                
                if transaction_data.amount <= 0:
                    operation_result = "не удалось определить сумму дохода"
                else:
                    # Создаем транзакцию
                    transaction = await self.transaction_repository.create_income(
                        amount=transaction_data.to_decimal_amount(),
                        description=transaction_data.description,
                        family_id=family_id,
                        created_by=user_id,
                        date=datetime.now() if not transaction_data.date else datetime.fromisoformat(transaction_data.date),
                        is_recurring=transaction_data.is_recurring,
                        recurring_frequency=transaction_data.recurring_frequency
                    )
                    
                    # Добавляем транзакцию в текущий бюджет
                    current_budget = await self.budget_repository.get_current_budget(family_id)
                    if current_budget:
                        await self.budget_repository.add_transaction_to_budget(
                            budget_id=current_budget.id,
                            transaction=transaction
                        )
                        
                        # Добавляем информацию о бюджете
                        additional_info = f"Доход добавлен в бюджет: {current_budget.name}\n"
                        additional_info += f"Текущий баланс: {current_budget.get_current_balance()} {current_budget.currency}"
                    
                    metadata["transaction_id"] = transaction.id
                    metadata["amount"] = str(transaction.amount)
                    metadata["description"] = transaction.description
            
            elif intent_result.intent == "view_budget":
                # Просмотр текущего бюджета
                current_budget = await self.budget_repository.get_current_budget(family_id)
                
                if not current_budget:
                    operation_result = "нет активного бюджета"
                else:
                    # Формируем информацию о бюджете
                    additional_info = f"Бюджет: {current_budget.name}\n"
                    additional_info += f"Период: с {current_budget.period_start.strftime('%d.%m.%Y')} по {current_budget.period_end.strftime('%d.%m.%Y')}\n"
                    additional_info += f"Доходы: {current_budget.income_actual} из {current_budget.income_plan} {current_budget.currency}\n"
                    additional_info += f"Расходы: {current_budget.get_total_spent()} из {current_budget.get_total_budget()} {current_budget.currency}\n"
                    additional_info += f"Баланс: {current_budget.get_current_balance()} {current_budget.currency}\n\n"
                    
                    # Добавляем информацию о категориях
                    category_stats = current_budget.get_category_stats()
                    if category_stats:
                        additional_info += "Расходы по категориям:\n"
                        for stat in category_stats[:5]:  # Показываем топ-5 категорий
                            icon = stat["icon"]
                            category_name = stat["category_name"]
                            spent = stat["spent"]
                            limit = stat["limit"]
                            progress = stat["progress"]
                            
                            additional_info += f"{icon} {category_name}: {spent}/{limit} ({progress:.1f}%)\n"
                    
                    metadata["budget_id"] = current_budget.id
                    metadata["budget_name"] = current_budget.name
                    metadata["income_actual"] = str(current_budget.income_actual)
                    metadata["total_spent"] = str(current_budget.get_total_spent())
                    metadata["balance"] = str(current_budget.get_current_balance())
            
            elif intent_result.intent == "create_budget":
                # Создание нового бюджета
                budget_data = intent_result.budget_data
                if not budget_data:
                    # Если в намерении нет данных о бюджете, пытаемся извлечь их из текста
                    budget_data = await self.budget_extractor.process(user_text)
                
                # Определяем период бюджета
                now = datetime.now()
                period = budget_data.period.lower()
                
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
                income_plan = Decimal(str(budget_data.income_plan)) if budget_data.income_plan else Decimal('0')
                category_limits = {
                    category: Decimal(str(limit))
                    for category, limit in budget_data.category_limits.items()
                }
                
                budget = await self.budget_repository.create_monthly_budget(
                    year=year,
                    month=month,
                    family_id=family_id,
                    created_by=user_id,
                    income_plan=income_plan,
                    name=budget_data.name,
                    category_limits=category_limits
                )
                
                additional_info = f"Создан бюджет: {budget.name}\n"
                additional_info += f"Период: с {budget.period_start.strftime('%d.%m.%Y')} по {budget.period_end.strftime('%d.%m.%Y')}\n"
                additional_info += f"Планируемый доход: {budget.income_plan} {budget.currency}\n"
                
                if category_limits:
                    additional_info += "\nУстановлены лимиты:\n"
                    for category, limit in budget.category_budgets.items():
                        category_name = BudgetCategory.get_ru_name(category)
                        icon = BudgetCategory.get_icon(category)
                        additional_info += f"{icon} {category_name}: {limit.limit} {budget.currency}\n"
                
                metadata["budget_id"] = budget.id
                metadata["budget_name"] = budget.name
                metadata["period_start"] = budget.period_start.isoformat()
                metadata["period_end"] = budget.period_end.isoformat()
            
            elif intent_result.intent == "update_budget":
                # Обновление бюджета
                budget_data = intent_result.budget_data
                if not budget_data:
                    # Если в намерении нет данных о бюджете, пытаемся извлечь их из текста
                    budget_data = await self.budget_extractor.process(user_text)
                
                # Получаем текущий бюджет
                current_budget = await self.budget_repository.get_current_budget(family_id)
                
                if not current_budget:
                    operation_result = "нет активного бюджета"
                else:
                    updates = {}
                    
                    # Обновляем название, если указано
                    if budget_data.name:
                        updates["name"] = budget_data.name
                    
                    # Обновляем планируемый доход, если указан
                    if budget_data.income_plan:
                        updates["income_plan"] = Decimal(str(budget_data.income_plan))
                    
                    # Обновляем бюджет
                    if updates:
                        updated_budget = await self.budget_repository.update_budget(
                            budget_id=current_budget.id,
                            **updates
                        )
                        
                        additional_info = f"Обновлен бюджет: {updated_budget.name}\n"
                        
                        if "income_plan" in updates:
                            additional_info += f"Новый планируемый доход: {updated_budget.income_plan} {updated_budget.currency}\n"
                    
                    # Обновляем лимиты по категориям, если указаны
                    if budget_data.category_limits:
                        for category, limit in budget_data.category_limits.items():
                            await self.budget_repository.update_category_limit(
                                budget_id=current_budget.id,
                                category=category,
                                limit=Decimal(str(limit))
                            )
                        
                        additional_info += "\nОбновлены лимиты по категориям:\n"
                        for category, limit in budget_data.category_limits.items():
                            category_name = BudgetCategory.get_ru_name(category)
                            icon = BudgetCategory.get_icon(category)
                            additional_info += f"{icon} {category_name}: {limit} {current_budget.currency}\n"
                    
                    metadata["budget_id"] = current_budget.id
                    metadata["updates"] = list(updates.keys())
                    if budget_data.category_limits:
                        metadata["updated_categories"] = [c.value for c in budget_data.category_limits.keys()]
            
            elif intent_result.intent == "view_transactions":
                # Просмотр транзакций
                # Определяем период для фильтрации
                start_date, end_date = None, None
                
                if intent_result.period:
                    period_info = intent_result.period
                    start_date = period_info.get("start_date")
                    end_date = period_info.get("end_date")
                
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
                    # Форматируем информацию о транзакциях
                    start_str = start_date.strftime("%d.%m.%Y")
                    end_str = end_date.strftime("%d.%m.%Y")
                    
                    additional_info = f"Транзакции за период: {start_str} - {end_str}\n\n"
                    additional_info += f"Всего доходов: {stats['total_income']} ₽\n"
                    additional_info += f"Всего расходов: {stats['total_expense']} ₽\n"
                    additional_info += f"Баланс: {stats['balance']} ₽\n\n"
                    
                    # Добавляем топ категорий расходов
                    if stats['categories']:
                        additional_info += "Топ категорий расходов:\n"
                        for category_stat in stats['categories'][:3]:  # Показываем топ-3 категории
                            icon = category_stat["icon"]
                            category_name = category_stat["category_name"]
                            amount = category_stat["amount"]
                            percentage = category_stat["percentage"]
                            
                            additional_info += f"{icon} {category_name}: {amount} ₽ ({percentage}%)\n"
                        
                        additional_info += "\n"
                    
                    # Добавляем последние транзакции
                    additional_info += "Последние транзакции:\n"
                    for transaction in transactions[:5]:  # Показываем только 5 последних
                        date_str = transaction.date.strftime("%d.%m")
                        icon = "💰" if transaction.transaction_type == TransactionType.INCOME else BudgetCategory.get_icon(transaction.category)
                        type_text = "Доход" if transaction.transaction_type == TransactionType.INCOME else BudgetCategory.get_ru_name(transaction.category)
                        
                        additional_info += f"{date_str} {icon} {transaction.description}: {transaction.format_amount()} ({type_text})\n"
                    
                    metadata["transaction_count"] = len(transactions)
                    metadata["total_income"] = str(stats['total_income'])
                    metadata["total_expense"] = str(stats['total_expense'])
                    metadata["balance"] = str(stats['balance'])
            
            elif intent_result.intent == "create_goal":
                # Создание финансовой цели
                goal_data = intent_result.goal_data
                if not goal_data:
                    # Если в намерении нет данных о цели, пытаемся извлечь их из текста
                    goal_data = await self.goal_extractor.process(user_text)
                
                if goal_data.target_amount <= 0:
                    operation_result = "не удалось определить целевую сумму"
                else:
                    # Преобразуем дедлайн в datetime, если указан
                    deadline = None
                    if goal_data.deadline:
                        try:
                            deadline = datetime.fromisoformat(goal_data.deadline)
                        except (ValueError, TypeError):
                            # Если не удалось распарсить дедлайн, оставляем None
                            pass
                    
                    # Создаем финансовую цель
                    goal = await self.goal_repository.create_goal(
                        name=goal_data.name,
                        target_amount=goal_data.to_decimal_amount(),
                        family_id=family_id,
                        created_by=user_id,
                        deadline=deadline,
                        priority=goal_data.priority,
                        notes=goal_data.notes
                    )
                    
                    # Рассчитываем ежемесячный взнос, если дедлайн указан
                    monthly_contribution = goal.calculate_monthly_contribution()
                    
                    additional_info = f"Создана финансовая цель: {goal.name}\n"
                    additional_info += f"Целевая сумма: {goal.format_amount(goal.target_amount)}\n"
                    
                    if deadline:
                        additional_info += f"Дедлайн: {deadline.strftime('%d.%m.%Y')}\n"
                        
                        if monthly_contribution:
                            additional_info += f"Рекомендуемый ежемесячный взнос: {goal.format_amount(monthly_contribution)}\n"
                    
                    additional_info += f"Приоритет: {GoalPriority.get_ru_name(goal.priority)}\n"
                    
                    if goal.notes:
                        additional_info += f"Заметки: {goal.notes}\n"
                    
                    metadata["goal_id"] = goal.id
                    metadata["goal_name"] = goal.name
                    metadata["target_amount"] = str(goal.target_amount)
                    if deadline:
                        metadata["deadline"] = deadline.isoformat()
            
            elif intent_result.intent == "update_goal":
                # Обновление финансовой цели
                goal_data = intent_result.goal_data
                if not goal_data:
                    # Если в намерении нет данных о цели, пытаемся извлечь их из текста
                    goal_data = await self.goal_extractor.process(user_text)
                
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
                        if goal_data.name.lower() in goal.name.lower():
                            found_goal = goal
                            break
                    
                    if not found_goal:
                        operation_result = f"не найдена цель с названием '{goal_data.name}'"
                    else:
                        updates = {}
                        
                        # Обновляем целевую сумму, если указана и больше 0
                        if goal_data.target_amount > 0:
                            updates["target_amount"] = goal_data.to_decimal_amount()
                        
                        # Обновляем дедлайн, если указан
                        if goal_data.deadline:
                            try:
                                deadline = datetime.fromisoformat(goal_data.deadline)
                                updates["deadline"] = deadline
                            except (ValueError, TypeError):
                                # Если не удалось распарсить дедлайн, игнорируем
                                pass
                        
                        # Обновляем приоритет
                        updates["priority"] = goal_data.priority
                        
                        # Обновляем заметки, если указаны
                        if goal_data.notes:
                            updates["notes"] = goal_data.notes
                        
                        # Обновляем цель
                        if updates:
                            updated_goal = await self.goal_repository.update_goal(
                                goal_id=found_goal.id,
                                **updates
                            )
                            
                            additional_info = f"Обновлена финансовая цель: {updated_goal.name}\n"
                            
                            if "target_amount" in updates:
                                additional_info += f"Новая целевая сумма: {updated_goal.format_amount(updated_goal.target_amount)}\n"
                            
                            if "deadline" in updates:
                                additional_info += f"Новый дедлайн: {updated_goal.deadline.strftime('%d.%m.%Y')}\n"
                                
                                # Рассчитываем новый ежемесячный взнос
                                monthly_contribution = updated_goal.calculate_monthly_contribution()
                                if monthly_contribution:
                                    additional_info += f"Рекомендуемый ежемесячный взнос: {updated_goal.format_amount(monthly_contribution)}\n"
                            
                            if "priority" in updates:
                                additional_info += f"Новый приоритет: {GoalPriority.get_ru_name(updated_goal.priority)}\n"
                            
                            if "notes" in updates:
                                additional_info += f"Новые заметки: {updated_goal.notes}\n"
                            
                            metadata["goal_id"] = updated_goal.id
                            metadata["updates"] = list(updates.keys())
                        else:
                            operation_result = "не указаны параметры для обновления"
            
            elif intent_result.intent == "view_goals":
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
                    # Форматируем информацию о целях
                    additional_info = f"Финансовые цели:\n\n"
                    
                    if active_goals:
                        additional_info += f"Активные цели ({len(active_goals)}):\n"
                        for goal in active_goals:
                            priority_icon = "🔴" if goal.priority == GoalPriority.URGENT else "🔵" if goal.priority == GoalPriority.HIGH else "🟢"
                            progress = goal.get_progress_percentage()
                            progress_bar = "▓" * int(progress / 10) + "░" * (10 - int(progress / 10))
                            
                            additional_info += f"{priority_icon} {goal.name}: {goal.format_amount(goal.current_amount)} из {goal.format_amount(goal.target_amount)} [{progress_bar}] {progress:.1f}%\n"
                            
                            if goal.deadline:
                                days_left = (goal.deadline - datetime.now()).days
                                if days_left > 0:
                                    additional_info += f"   Осталось дней: {days_left}\n"
                                else:
                                    additional_info += f"   Дедлайн просрочен!\n"
                                
                                # Рассчитываем ежемесячный взнос
                                monthly_contribution = goal.calculate_monthly_contribution()
                                if monthly_contribution:
                                    additional_info += f"   Рекомендуемый ежемесячный взнос: {goal.format_amount(monthly_contribution)}\n"
                            
                            additional_info += "\n"
                    
                    if completed_goals:
                        additional_info += f"\nЗавершенные цели ({len(completed_goals)}):\n"
                        for goal in completed_goals[:3]:  # Показываем только 3 последних завершенных цели
                            additional_info += f"✅ {goal.name}: {goal.format_amount(goal.target_amount)}\n"
                    
                    metadata["active_goals_count"] = len(active_goals)
                    metadata["completed_goals_count"] = len(completed_goals)
            
            elif intent_result.intent == "view_reports":
                # Просмотр финансовых отчетов
                # Определяем период для отчета
                start_date, end_date = None, None
                
                if intent_result.period:
                    period_info = intent_result.period
                    start_date = period_info.get("start_date")
                    end_date = period_info.get("end_date")
                
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
                    # Форматируем информацию для отчета
                    start_str = start_date.strftime("%d.%m.%Y")
                    end_str = end_date.strftime("%d.%m.%Y")
                    
                    additional_info = f"📊 Финансовый отчет за период: {start_str} - {end_str}\n\n"
                    
                    # Общая статистика
                    additional_info += f"💰 Доходы: {stats['total_income']} ₽\n"
                    additional_info += f"💸 Расходы: {stats['total_expense']} ₽\n"
                    
                    # Рассчитываем баланс и его изменение
                    balance = stats["balance"]
                    balance_sign = "+" if balance >= 0 else ""
                    additional_info += f"📈 Баланс: {balance_sign}{balance} ₽\n"
                    
                    # Экономия/перерасход
                    savings_percentage = 0
                    if stats['total_income'] > 0:
                        savings_percentage = (balance / stats['total_income']) * 100
                    
                    if balance >= 0:
                        additional_info += f"🎯 Экономия: {savings_percentage:.1f}% от доходов\n\n"
                    else:
                        additional_info += f"⚠️ Перерасход: {-savings_percentage:.1f}% от доходов\n\n"
                    
                    # Распределение расходов по категориям
                    if stats['categories']:
                        additional_info += "📊 Распределение расходов:\n"
                        for category_stat in stats['categories']:
                            icon = category_stat["icon"]
                            category_name = category_stat["category_name"]
                            amount = category_stat["amount"]
                            percentage = category_stat["percentage"]
                            
                            # Создаем визуальный индикатор процента
                            progress_bar = "▓" * int(percentage / 10) + "░" * (10 - int(percentage / 10))
                            
                            additional_info += f"{icon} {category_name}: {amount} ₽ ({percentage:.1f}%) [{progress_bar}]\n"
                    
                    # Добавляем рекомендации
                    additional_info += "\n💡 Рекомендации:\n"
                    
                    if balance < 0:
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
                    
                    metadata["period_start"] = start_date.isoformat()
                    metadata["period_end"] = end_date.isoformat()
                    metadata["total_income"] = str(stats['total_income'])
                    metadata["total_expense"] = str(stats['total_expense'])
                    metadata["balance"] = str(balance)
                    metadata["savings_percentage"] = float(savings_percentage)
            
            # Генерируем ответ на основе результатов операции
            response = await self.response_generator.process(
                intent=intent_result.intent,
                operation_result=operation_result,
                additional_info=additional_info
            )
            
            return response, metadata
            
        except Exception as e:
            logger.error(f"Ошибка при обработке сообщения пользователя: {str(e)}")
            return "Извините, произошла ошибка при обработке запроса. Пожалуйста, попробуйте снова.", {
                "error": str(e)
            }
