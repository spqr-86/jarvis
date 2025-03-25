"""
Модели данных для функциональности семейного бюджета.
"""

from decimal import Decimal
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field, validator

from jarvis.utils.helpers import generate_uuid


class BudgetCategory(str, Enum):
    """Категории финансовых операций."""
    
    FOOD = "food"
    HOUSING = "housing"
    TRANSPORT = "transport"
    UTILITIES = "utilities"
    ENTERTAINMENT = "entertainment"
    HEALTHCARE = "healthcare"
    EDUCATION = "education"
    SHOPPING = "shopping"
    SAVINGS = "savings"
    INCOME = "income"
    OTHER = "other"
    
    @classmethod
    def get_ru_name(cls, category: "BudgetCategory") -> str:
        """Возвращает русское название категории."""
        ru_names = {
            cls.FOOD: "Питание",
            cls.HOUSING: "Жильё",
            cls.TRANSPORT: "Транспорт",
            cls.UTILITIES: "Коммунальные услуги",
            cls.ENTERTAINMENT: "Развлечения",
            cls.HEALTHCARE: "Здоровье",
            cls.EDUCATION: "Образование",
            cls.SHOPPING: "Покупки",
            cls.SAVINGS: "Сбережения",
            cls.INCOME: "Доходы",
            cls.OTHER: "Другое"
        }
        return ru_names.get(category, "Другое")
    
    @classmethod
    def get_icon(cls, category: "BudgetCategory") -> str:
        """Возвращает иконку для категории."""
        icons = {
            cls.FOOD: "🍽️",
            cls.HOUSING: "🏠",
            cls.TRANSPORT: "🚗",
            cls.UTILITIES: "💡",
            cls.ENTERTAINMENT: "🎭",
            cls.HEALTHCARE: "🏥",
            cls.EDUCATION: "📚",
            cls.SHOPPING: "🛒",
            cls.SAVINGS: "💰",
            cls.INCOME: "💵",
            cls.OTHER: "📦"
        }
        return icons.get(category, "📦")
    
    @classmethod
    def get_expense_categories(cls) -> List["BudgetCategory"]:
        """Возвращает список категорий расходов."""
        return [
            cls.FOOD,
            cls.HOUSING,
            cls.TRANSPORT,
            cls.UTILITIES,
            cls.ENTERTAINMENT,
            cls.HEALTHCARE,
            cls.EDUCATION,
            cls.SHOPPING,
            cls.SAVINGS,
            cls.OTHER
        ]


class TransactionType(str, Enum):
    """Типы финансовых транзакций."""
    
    INCOME = "income"
    EXPENSE = "expense"
    
    @classmethod
    def get_ru_name(cls, type_: "TransactionType") -> str:
        """Возвращает русское название типа транзакции."""
        ru_names = {
            cls.INCOME: "Доход",
            cls.EXPENSE: "Расход"
        }
        return ru_names.get(type_, "Неизвестно")


class RecurringFrequency(str, Enum):
    """Частота повторения транзакций."""
    
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"
    
    @classmethod
    def get_ru_name(cls, frequency: "RecurringFrequency") -> str:
        """Возвращает русское название частоты."""
        ru_names = {
            cls.DAILY: "Ежедневно",
            cls.WEEKLY: "Еженедельно",
            cls.MONTHLY: "Ежемесячно",
            cls.QUARTERLY: "Ежеквартально",
            cls.YEARLY: "Ежегодно"
        }
        return ru_names.get(frequency, "Неизвестно")


class GoalPriority(str, Enum):
    """Приоритет финансовой цели."""
    
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"
    
    @classmethod
    def get_ru_name(cls, priority: "GoalPriority") -> str:
        """Возвращает русское название приоритета."""
        ru_names = {
            cls.LOW: "Низкий",
            cls.MEDIUM: "Средний",
            cls.HIGH: "Высокий",
            cls.URGENT: "Срочный"
        }
        return ru_names.get(priority, "Средний")


class Money(BaseModel):
    """Модель для представления денежных сумм."""
    
    amount: Decimal = Field(..., description="Сумма в минимальных единицах (копейках)")
    currency: str = Field("RUB", description="Валюта (ISO код)")
    
    @validator("amount")
    def validate_amount(cls, v):
        """Проверяет, что сумма не отрицательная."""
        if v < 0:
            raise ValueError("Сумма не может быть отрицательной")
        return v
    
    def format(self) -> str:
        """Форматирует сумму для отображения."""
        currency_symbols = {
            "RUB": "₽",
            "USD": "$",
            "EUR": "€"
        }
        symbol = currency_symbols.get(self.currency, self.currency)
        return f"{self.amount:.2f} {symbol}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразует модель в словарь для хранения."""
        return {
            "amount": str(self.amount),  # Преобразуем Decimal в строку для хранения
            "currency": self.currency
        }


class Transaction(BaseModel):
    """Модель финансовой транзакции."""
    
    id: str = Field(default_factory=generate_uuid, description="Уникальный идентификатор транзакции")
    amount: Decimal = Field(..., description="Сумма транзакции")
    currency: str = Field("RUB", description="Валюта транзакции")
    category: BudgetCategory = Field(..., description="Категория транзакции")
    transaction_type: TransactionType = Field(..., description="Тип транзакции (доход/расход)")
    description: str = Field(..., description="Описание транзакции")
    date: datetime = Field(default_factory=datetime.now, description="Дата и время транзакции")
    family_id: str = Field(..., description="ID семьи")
    created_by: str = Field(..., description="ID пользователя, создавшего транзакцию")
    tags: List[str] = Field(default_factory=list, description="Теги для группировки транзакций")
    is_recurring: bool = Field(False, description="Является ли транзакция повторяющейся")
    recurring_frequency: Optional[RecurringFrequency] = Field(None, description="Частота повторения (если повторяющаяся)")
    created_at: datetime = Field(default_factory=datetime.now, description="Время создания записи")
    updated_at: Optional[datetime] = Field(None, description="Время последнего обновления")
    
    @validator("amount")
    def validate_amount(cls, v):
        """Проверяет, что сумма положительная."""
        if v <= 0:
            raise ValueError("Сумма должна быть положительной")
        return v
    
    def format_amount(self) -> str:
        """Форматирует сумму для отображения."""
        currency_symbols = {
            "RUB": "₽",
            "USD": "$",
            "EUR": "€"
        }
        symbol = currency_symbols.get(self.currency, self.currency)
        return f"{self.amount:.2f} {symbol}"
    
    def get_money(self) -> Money:
        """Возвращает сумму транзакции в виде объекта Money."""
        return Money(amount=self.amount, currency=self.currency)
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразует модель в словарь для хранения."""
        return {
            "id": self.id,
            "amount": str(self.amount),  # Преобразуем Decimal в строку для хранения
            "currency": self.currency,
            "category": self.category.value,
            "transaction_type": self.transaction_type.value,
            "description": self.description,
            "date": self.date.isoformat(),
            "family_id": self.family_id,
            "created_by": self.created_by,
            "tags": self.tags,
            "is_recurring": self.is_recurring,
            "recurring_frequency": self.recurring_frequency.value if self.recurring_frequency else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
    
    @classmethod
    def create_expense(
        cls,
        amount: Decimal,
        category: BudgetCategory,
        description: str,
        family_id: str,
        created_by: str,
        currency: str = "RUB",
        **kwargs
    ) -> "Transaction":
        """
        Создает транзакцию расхода.
        
        Args:
            amount: Сумма расхода
            category: Категория расхода
            description: Описание расхода
            family_id: ID семьи
            created_by: ID пользователя, создавшего транзакцию
            currency: Валюта транзакции
            **kwargs: Дополнительные параметры транзакции
        
        Returns:
            Транзакция расхода
        """
        return cls(
            amount=amount,
            currency=currency,
            category=category,
            transaction_type=TransactionType.EXPENSE,
            description=description,
            family_id=family_id,
            created_by=created_by,
            **kwargs
        )
    
    @classmethod
    def create_income(
        cls,
        amount: Decimal,
        description: str,
        family_id: str,
        created_by: str,
        currency: str = "RUB",
        **kwargs
    ) -> "Transaction":
        """
        Создает транзакцию дохода.
        
        Args:
            amount: Сумма дохода
            description: Описание дохода
            family_id: ID семьи
            created_by: ID пользователя, создавшего транзакцию
            currency: Валюта транзакции
            **kwargs: Дополнительные параметры транзакции
        
        Returns:
            Транзакция дохода
        """
        return cls(
            amount=amount,
            currency=currency,
            category=BudgetCategory.INCOME,
            transaction_type=TransactionType.INCOME,
            description=description,
            family_id=family_id,
            created_by=created_by,
            **kwargs
        )


class CategoryBudget(BaseModel):
    """Модель бюджета для категории расходов."""
    
    category: BudgetCategory = Field(..., description="Категория расходов")
    limit: Decimal = Field(..., description="Лимит расходов по категории")
    currency: str = Field("RUB", description="Валюта лимита")
    spent: Decimal = Field(0, description="Уже потрачено по категории")
    
    def get_remaining(self) -> Decimal:
        """Возвращает оставшуюся сумму по бюджету категории."""
        return max(Decimal('0'), self.limit - self.spent)
    
    def get_progress_percentage(self) -> float:
        """Возвращает процент использования бюджета категории."""
        if self.limit == 0:
            return 100.0 if self.spent > 0 else 0.0
        return min(100.0, float(self.spent / self.limit * 100))
    
    def is_exceeded(self) -> bool:
        """Проверяет, превышен ли лимит по категории."""
        return self.spent > self.limit
    
    def add_expense(self, amount: Decimal) -> None:
        """
        Добавляет расход в категорию.
        
        Args:
            amount: Сумма расхода
        """
        self.spent += amount
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразует модель в словарь для хранения."""
        return {
            "category": self.category.value,
            "limit": str(self.limit),
            "currency": self.currency,
            "spent": str(self.spent)
        }


class Budget(BaseModel):
    """Модель бюджета на период."""
    
    id: str = Field(default_factory=generate_uuid, description="Уникальный идентификатор бюджета")
    name: str = Field("Бюджет", description="Название бюджета")
    family_id: str = Field(..., description="ID семьи")
    period_start: datetime = Field(..., description="Начало периода бюджета")
    period_end: datetime = Field(..., description="Конец периода бюджета")
    currency: str = Field("RUB", description="Основная валюта бюджета")
    income_plan: Decimal = Field(0, description="Планируемый доход за период")
    income_actual: Decimal = Field(0, description="Фактический доход за период")
    category_budgets: Dict[BudgetCategory, CategoryBudget] = Field(default_factory=dict, description="Бюджеты по категориям")
    created_by: str = Field(..., description="ID пользователя, создавшего бюджет")
    created_at: datetime = Field(default_factory=datetime.now, description="Время создания бюджета")
    updated_at: Optional[datetime] = Field(None, description="Время последнего обновления")
    
    def get_total_budget(self) -> Decimal:
        """Возвращает общий бюджет расходов на период."""
        return sum(category.limit for category in self.category_budgets.values())
    
    def get_total_spent(self) -> Decimal:
        """Возвращает общую сумму расходов за период."""
        return sum(category.spent for category in self.category_budgets.values())
    
    def get_remaining_budget(self) -> Decimal:
        """Возвращает оставшуюся сумму по бюджету."""
        return max(Decimal('0'), self.get_total_budget() - self.get_total_spent())
    
    def get_current_balance(self) -> Decimal:
        """Возвращает текущий баланс (доходы - расходы)."""
        return self.income_actual - self.get_total_spent()
    
    def add_category_budget(self, category: BudgetCategory, limit: Decimal) -> None:
        """
        Добавляет бюджет по категории.
        
        Args:
            category: Категория расходов
            limit: Лимит расходов по категории
        """
        self.category_budgets[category] = CategoryBudget(
            category=category,
            limit=limit,
            currency=self.currency,
            spent=Decimal('0')
        )
        self.updated_at = datetime.now()
    
    def update_category_limit(self, category: BudgetCategory, limit: Decimal) -> bool:
        """
        Обновляет лимит расходов по категории.
        
        Args:
            category: Категория расходов
            limit: Новый лимит расходов
            
        Returns:
            True, если лимит обновлен, иначе False
        """
        if category not in self.category_budgets:
            return False
        
        self.category_budgets[category].limit = limit
        self.updated_at = datetime.now()
        return True
    
    def add_income(self, amount: Decimal) -> None:
        """
        Добавляет доход в бюджет.
        
        Args:
            amount: Сумма дохода
        """
        self.income_actual += amount
        self.updated_at = datetime.now()
    
    def add_expense(self, category: BudgetCategory, amount: Decimal) -> None:
        """
        Добавляет расход в бюджет.
        
        Args:
            category: Категория расхода
            amount: Сумма расхода
        """
        if category not in self.category_budgets:
            # Если категория не существует, создаем ее с нулевым лимитом
            self.add_category_budget(category, Decimal('0'))
        
        self.category_budgets[category].add_expense(amount)
        self.updated_at = datetime.now()
    
    def process_transaction(self, transaction: Transaction) -> bool:
        """
        Обрабатывает транзакцию, добавляя ее в бюджет.
        
        Args:
            transaction: Транзакция для обработки
            
        Returns:
            True, если транзакция успешно обработана, иначе False
        """
        # Проверяем, что транзакция входит в период бюджета
        if transaction.date < self.period_start or transaction.date > self.period_end:
            return False
        
        # Проверяем, что транзакция принадлежит той же семье
        if transaction.family_id != self.family_id:
            return False
        
        # Обрабатываем транзакцию в зависимости от ее типа
        if transaction.transaction_type == TransactionType.INCOME:
            self.add_income(transaction.amount)
        elif transaction.transaction_type == TransactionType.EXPENSE:
            self.add_expense(transaction.category, transaction.amount)
        
        return True
    
    def get_category_stats(self) -> List[Dict[str, Any]]:
        """
        Возвращает статистику по категориям расходов.
        
        Returns:
            Список словарей со статистикой по каждой категории
        """
        stats = []
        for category, budget in self.category_budgets.items():
            stats.append({
                "category": category,
                "category_name": BudgetCategory.get_ru_name(category),
                "icon": BudgetCategory.get_icon(category),
                "limit": budget.limit,
                "spent": budget.spent,
                "remaining": budget.get_remaining(),
                "progress": budget.get_progress_percentage(),
                "is_exceeded": budget.is_exceeded()
            })
        
        # Сортируем по проценту использования бюджета (от большего к меньшему)
        return sorted(stats, key=lambda x: x["progress"], reverse=True)
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразует модель в словарь для хранения."""
        return {
            "id": self.id,
            "name": self.name,
            "family_id": self.family_id,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "currency": self.currency,
            "income_plan": str(self.income_plan),
            "income_actual": str(self.income_actual),
            "category_budgets": {
                category.value: budget.to_dict()
                for category, budget in self.category_budgets.items()
            },
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
    
    @classmethod
    def create_monthly_budget(
        cls,
        year: int,
        month: int,
        family_id: str,
        created_by: str,
        income_plan: Decimal = Decimal('0'),
        name: Optional[str] = None,
        currency: str = "RUB"
    ) -> "Budget":
        """
        Создает бюджет на указанный месяц.
        
        Args:
            year: Год
            month: Месяц (1-12)
            family_id: ID семьи
            created_by: ID пользователя, создавшего бюджет
            income_plan: Планируемый доход
            name: Название бюджета (если None, генерируется автоматически)
            currency: Валюта бюджета
            
        Returns:
            Бюджет на месяц
        """
        from calendar import monthrange
        
        # Проверяем корректность месяца
        if month < 1 or month > 12:
            raise ValueError("Месяц должен быть от 1 до 12")
        
        # Начало и конец месяца
        days_in_month = monthrange(year, month)[1]
        period_start = datetime(year, month, 1, 0, 0, 0)
        period_end = datetime(year, month, days_in_month, 23, 59, 59)
        
        # Название бюджета
        month_names = {
            1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель",
            5: "Май", 6: "Июнь", 7: "Июль", 8: "Август",
            9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь"
        }
        if name is None:
            name = f"Бюджет на {month_names[month]} {year}"
        
        return cls(
            name=name,
            family_id=family_id,
            period_start=period_start,
            period_end=period_end,
            currency=currency,
            income_plan=income_plan,
            income_actual=Decimal('0'),
            created_by=created_by
        )


class FinancialGoal(BaseModel):
    """Модель финансовой цели."""
    
    id: str = Field(default_factory=generate_uuid, description="Уникальный идентификатор цели")
    name: str = Field(..., description="Название цели")
    target_amount: Decimal = Field(..., description="Целевая сумма")
    current_amount: Decimal = Field(0, description="Текущая сумма накоплений")
    currency: str = Field("RUB", description="Валюта цели")
    start_date: datetime = Field(default_factory=datetime.now, description="Дата начала")
    deadline: Optional[datetime] = Field(None, description="Дата дедлайна")
    family_id: str = Field(..., description="ID семьи")
    created_by: str = Field(..., description="ID пользователя, создавшего цель")
    priority: GoalPriority = Field(GoalPriority.MEDIUM, description="Приоритет цели")
    notes: Optional[str] = Field(None, description="Дополнительные заметки")
    created_at: datetime = Field(default_factory=datetime.now, description="Время создания записи")
    updated_at: Optional[datetime] = Field(None, description="Время последнего обновления")
    
    @validator("target_amount", "current_amount")
    def validate_amount(cls, v):
        """Проверяет, что сумма не отрицательная."""
        if v < 0:
            raise ValueError("Сумма не может быть отрицательной")
        return v
    
    def update_progress(self, amount: Decimal) -> None:
        """
        Обновляет прогресс цели.
        
        Args:
            amount: Сумма, на которую нужно увеличить прогресс
        """
        self.current_amount += amount
        self.updated_at = datetime.now()
    
    def get_progress_percentage(self) -> float:
        """
        Возвращает процент выполнения цели.
        
        Returns:
            Процент выполнения цели от 0 до 100
        """
        if self.target_amount == 0:
            return 100.0
        return min(100.0, float(self.current_amount / self.target_amount * 100))
    
    def get_remaining_amount(self) -> Decimal:
        """
        Возвращает оставшуюся сумму до достижения цели.
        
        Returns:
            Оставшаяся сумма
        """
        return max(Decimal('0'), self.target_amount - self.current_amount)
    
    def is_completed(self) -> bool:
        """
        Проверяет, достигнута ли цель.
        
        Returns:
            True, если цель достигнута, иначе False
        """
        return self.current_amount >= self.target_amount
    
    def calculate_monthly_contribution(self) -> Optional[Decimal]:
        """
        Рассчитывает необходимый ежемесячный взнос для достижения цели в срок.
        
        Returns:
            Ежемесячный взнос или None, если дедлайн не установлен
        """
        if not self.deadline:
            return None
        
        remaining_amount = self.get_remaining_amount()
        if remaining_amount <= 0:
            return Decimal('0')
        
        now = datetime.now()
        if now >= self.deadline:
            return remaining_amount
        
        # Количество месяцев до дедлайна
        months_remaining = (self.deadline.year - now.year) * 12 + self.deadline.month - now.month
        if months_remaining <= 0:
            return remaining_amount
        
        return remaining_amount / Decimal(months_remaining)
    
    def format_amount(self, amount: Decimal) -> str:
        """
        Форматирует сумму для отображения.
        
        Args:
            amount: Сумма для форматирования
            
        Returns:
            Отформатированная строка
        """
        currency_symbols = {
            "RUB": "₽",
            "USD": "$",
            "EUR": "€"
        }
        symbol = currency_symbols.get(self.currency, self.currency)
        return f"{amount:.2f} {symbol}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразует модель в словарь для хранения."""
        return {
            "id": self.id,
            "name": self.name,
            "target_amount": str(self.target_amount),
            "current_amount": str(self.current_amount),
            "currency": self.currency,
            "start_date": self.start_date.isoformat(),
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "family_id": self.family_id,
            "created_by": self.created_by,
            "priority": self.priority.value,
            "notes": self.notes,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
