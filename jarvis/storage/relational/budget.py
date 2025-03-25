"""
Репозиторий для работы с финансовыми данными в реляционной базе данных.
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Any, Union, Tuple

from jarvis.core.models.budget import (
    Transaction, Budget, FinancialGoal, 
    BudgetCategory, TransactionType, GoalPriority,
    RecurringFrequency
)
from jarvis.utils.helpers import generate_uuid

logger = logging.getLogger(__name__)


class TransactionRepository:
    """Репозиторий для работы с финансовыми транзакциями."""

    def __init__(self, db_connection=None):
        """
        Инициализация репозитория транзакций.
        
        Args:
            db_connection: Подключение к базе данных (в будущем реализации)
        """
        # В MVP будем использовать in-memory хранилище
        # В будущем здесь будет интеграция с реальной БД
        self._db = {}  # Dict[transaction_id, Transaction]
        self._db_connection = db_connection
    
    async def create_transaction(
        self,
        amount: Decimal,
        category: BudgetCategory,
        transaction_type: TransactionType,
        description: str,
        family_id: str,
        created_by: str,
        date: Optional[datetime] = None,
        currency: str = "RUB",
        tags: Optional[List[str]] = None,
        is_recurring: bool = False,
        recurring_frequency: Optional[RecurringFrequency] = None
    ) -> Transaction:
        """
        Создает новую финансовую транзакцию.
        
        Args:
            amount: Сумма транзакции
            category: Категория транзакции
            transaction_type: Тип транзакции (доход/расход)
            description: Описание транзакции
            family_id: ID семьи
            created_by: ID пользователя, создавшего транзакцию
            date: Дата и время транзакции (если None, используется текущее время)
            currency: Валюта транзакции
            tags: Список тегов для группировки транзакций
            is_recurring: Является ли транзакция повторяющейся
            recurring_frequency: Частота повторения (если повторяющаяся)
            
        Returns:
            Созданная транзакция
        """
        transaction_id = generate_uuid()
        
        # Если дата не указана, используем текущее время
        if date is None:
            date = datetime.now()
        
        # Создаем транзакцию
        transaction = Transaction(
            id=transaction_id,
            amount=amount,
            currency=currency,
            category=category,
            transaction_type=transaction_type,
            description=description,
            date=date,
            family_id=family_id,
            created_by=created_by,
            tags=tags or [],
            is_recurring=is_recurring,
            recurring_frequency=recurring_frequency
        )
        
        # Сохраняем в "базу данных"
        self._db[transaction_id] = transaction
        
        logger.info(f"Создана новая транзакция: {transaction_id} ({transaction_type.value}) для семьи {family_id}")
        return transaction
    
    async def create_expense(
        self,
        amount: Decimal,
        category: BudgetCategory,
        description: str,
        family_id: str,
        created_by: str,
        **kwargs
    ) -> Transaction:
        """
        Создает новую транзакцию расхода.
        
        Args:
            amount: Сумма расхода
            category: Категория расхода
            description: Описание расхода
            family_id: ID семьи
            created_by: ID пользователя, создавшего транзакцию
            **kwargs: Дополнительные параметры транзакции
            
        Returns:
            Созданная транзакция расхода
        """
        return await self.create_transaction(
            amount=amount,
            category=category,
            transaction_type=TransactionType.EXPENSE,
            description=description,
            family_id=family_id,
            created_by=created_by,
            **kwargs
        )
    
    async def create_income(
        self,
        amount: Decimal,
        description: str,
        family_id: str,
        created_by: str,
        **kwargs
    ) -> Transaction:
        """
        Создает новую транзакцию дохода.
        
        Args:
            amount: Сумма дохода
            description: Описание дохода
            family_id: ID семьи
            created_by: ID пользователя, создавшего транзакцию
            **kwargs: Дополнительные параметры транзакции
            
        Returns:
            Созданная транзакция дохода
        """
        return await self.create_transaction(
            amount=amount,
            category=BudgetCategory.INCOME,
            transaction_type=TransactionType.INCOME,
            description=description,
            family_id=family_id,
            created_by=created_by,
            **kwargs
        )
    
    async def get_transaction(self, transaction_id: str) -> Optional[Transaction]:
        """
        Получает транзакцию по ID.
        
        Args:
            transaction_id: ID транзакции
            
        Returns:
            Транзакция или None, если транзакция не найдена
        """
        return self._db.get(transaction_id)
    
    async def get_transactions_for_family(
        self,
        family_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        transaction_type: Optional[TransactionType] = None,
        category: Optional[BudgetCategory] = None,
        limit: Optional[int] = None
    ) -> List[Transaction]:
        """
        Получает список транзакций для семьи с возможностью фильтрации.
        
        Args:
            family_id: ID семьи
            start_date: Начальная дата для фильтрации
            end_date: Конечная дата для фильтрации
            transaction_type: Тип транзакции для фильтрации
            category: Категория для фильтрации
            limit: Максимальное количество транзакций для возврата
            
        Returns:
            Список транзакций, соответствующих условиям фильтрации
        """
        transactions = [
            transaction for transaction in self._db.values()
            if transaction.family_id == family_id
        ]
        
        # Применяем фильтры
        if start_date:
            transactions = [t for t in transactions if t.date >= start_date]
        
        if end_date:
            transactions = [t for t in transactions if t.date <= end_date]
        
        if transaction_type:
            transactions = [t for t in transactions if t.transaction_type == transaction_type]
        
        if category:
            transactions = [t for t in transactions if t.category == category]
        
        # Сортируем по дате (от новых к старым)
        transactions.sort(key=lambda t: t.date, reverse=True)
        
        # Применяем ограничение по количеству, если указано
        if limit is not None:
            transactions = transactions[:limit]
        
        return transactions
    
    async def get_recurring_transactions(self, family_id: str) -> List[Transaction]:
        """
        Получает список повторяющихся транзакций для семьи.
        
        Args:
            family_id: ID семьи
            
        Returns:
            Список повторяющихся транзакций
        """
        return [
            transaction for transaction in self._db.values()
            if transaction.family_id == family_id and transaction.is_recurring
        ]
    
    async def update_transaction(
        self,
        transaction_id: str,
        **kwargs
    ) -> Optional[Transaction]:
        """
        Обновляет транзакцию.
        
        Args:
            transaction_id: ID транзакции
            **kwargs: Атрибуты для обновления
            
        Returns:
            Обновленная транзакция или None, если транзакция не найдена
        """
        transaction = self._db.get(transaction_id)
        if not transaction:
            logger.warning(f"Не удалось найти транзакцию с ID {transaction_id}")
            return None
        
        # Обновляем атрибуты
        for key, value in kwargs.items():
            if hasattr(transaction, key) and key not in ['id', 'family_id', 'created_at']:
                setattr(transaction, key, value)
        
        # Обновляем время изменения
        transaction.updated_at = datetime.now()
        
        # Обновляем в "базе данных"
        self._db[transaction_id] = transaction
        
        logger.info(f"Обновлена транзакция {transaction_id}")
        return transaction
    
    async def delete_transaction(self, transaction_id: str) -> bool:
        """
        Удаляет транзакцию.
        
        Args:
            transaction_id: ID транзакции
            
        Returns:
            True, если транзакция была удалена, иначе False
        """
        if transaction_id not in self._db:
            logger.warning(f"Не удалось найти транзакцию с ID {transaction_id}")
            return False
        
        del self._db[transaction_id]
        logger.info(f"Удалена транзакция {transaction_id}")
        return True
    
    async def get_total_by_category(
        self,
        family_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        transaction_type: Optional[TransactionType] = None
    ) -> Dict[BudgetCategory, Decimal]:
        """
        Получает суммы транзакций по категориям.
        
        Args:
            family_id: ID семьи
            start_date: Начальная дата для фильтрации
            end_date: Конечная дата для фильтрации
            transaction_type: Тип транзакции для фильтрации
            
        Returns:
            Словарь с категориями и суммами
        """
        # Получаем транзакции с фильтрацией
        transactions = await self.get_transactions_for_family(
            family_id=family_id,
            start_date=start_date,
            end_date=end_date,
            transaction_type=transaction_type
        )
        
        # Группируем по категориям и суммируем
        totals = {}
        for transaction in transactions:
            if transaction.category not in totals:
                totals[transaction.category] = Decimal('0')
            
            totals[transaction.category] += transaction.amount
        
        return totals
    
    async def get_transactions_stats(
        self,
        family_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Получает статистику по транзакциям.
        
        Args:
            family_id: ID семьи
            start_date: Начальная дата для фильтрации
            end_date: Конечная дата для фильтрации
            
        Returns:
            Словарь со статистикой
        """
        # Получаем транзакции с фильтрацией
        transactions = await self.get_transactions_for_family(
            family_id=family_id,
            start_date=start_date,
            end_date=end_date
        )
        
        # Разделяем на доходы и расходы
        incomes = [t for t in transactions if t.transaction_type == TransactionType.INCOME]
        expenses = [t for t in transactions if t.transaction_type == TransactionType.EXPENSE]
        
        # Вычисляем общие суммы
        total_income = sum(t.amount for t in incomes)
        total_expense = sum(t.amount for t in expenses)
        balance = total_income - total_expense
        
        # Группируем расходы по категориям
        expense_by_category = {}
        for transaction in expenses:
            if transaction.category not in expense_by_category:
                expense_by_category[transaction.category] = Decimal('0')
            
            expense_by_category[transaction.category] += transaction.amount
        
        # Преобразуем в список для удобства использования
        categories_stats = []
        for category, amount in expense_by_category.items():
            percentage = (amount / total_expense * 100) if total_expense > 0 else 0
            categories_stats.append({
                "category": category,
                "category_name": BudgetCategory.get_ru_name(category),
                "icon": BudgetCategory.get_icon(category),
                "amount": amount,
                "percentage": round(percentage, 2)
            })
        
        # Сортируем по сумме (от большей к меньшей)
        categories_stats.sort(key=lambda x: x["amount"], reverse=True)
        
        return {
            "total_income": total_income,
            "total_expense": total_expense,
            "balance": balance,
            "transaction_count": len(transactions),
            "income_count": len(incomes),
            "expense_count": len(expenses),
            "categories": categories_stats
        }


class BudgetRepository:
    """Репозиторий для работы с бюджетами."""
    
    def __init__(self, db_connection=None):
        """
        Инициализация репозитория бюджетов.
        
        Args:
            db_connection: Подключение к базе данных (в будущем реализации)
        """
        # В MVP будем использовать in-memory хранилище
        # В будущем здесь будет интеграция с реальной БД
        self._db = {}  # Dict[budget_id, Budget]
        self._db_connection = db_connection
    
    async def create_budget(
        self,
        name: str,
        family_id: str,
        period_start: datetime,
        period_end: datetime,
        created_by: str,
        income_plan: Decimal = Decimal('0'),
        currency: str = "RUB",
        category_limits: Optional[Dict[BudgetCategory, Decimal]] = None
    ) -> Budget:
        """
        Создает новый бюджет.
        
        Args:
            name: Название бюджета
            family_id: ID семьи
            period_start: Начало периода бюджета
            period_end: Конец периода бюджета
            created_by: ID пользователя, создавшего бюджет
            income_plan: Планируемый доход за период
            currency: Основная валюта бюджета
            category_limits: Словарь с лимитами по категориям
            
        Returns:
            Созданный бюджет
        """
        budget_id = generate_uuid()
        
        # Создаем бюджет
        budget = Budget(
            id=budget_id,
            name=name,
            family_id=family_id,
            period_start=period_start,
            period_end=period_end,
            currency=currency,
            income_plan=income_plan,
            income_actual=Decimal('0'),
            created_by=created_by
        )
        
        # Добавляем лимиты по категориям, если указаны
        if category_limits:
            for category, limit in category_limits.items():
                budget.add_category_budget(category, limit)
        
        # Сохраняем в "базу данных"
        self._db[budget_id] = budget
        
        logger.info(f"Создан новый бюджет: {name} для семьи {family_id}")
        return budget
    
    async def create_monthly_budget(
        self,
        year: int,
        month: int,
        family_id: str,
        created_by: str,
        income_plan: Decimal = Decimal('0'),
        name: Optional[str] = None,
        currency: str = "RUB",
        category_limits: Optional[Dict[BudgetCategory, Decimal]] = None
    ) -> Budget:
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
            category_limits: Словарь с лимитами по категориям
            
        Returns:
            Бюджет на месяц
        """
        # Используем метод создания месячного бюджета из модели
        budget = Budget.create_monthly_budget(
            year=year,
            month=month,
            family_id=family_id,
            created_by=created_by,
            income_plan=income_plan,
            name=name,
            currency=currency
        )
        
        # Добавляем лимиты по категориям, если указаны
        if category_limits:
            for category, limit in category_limits.items():
                budget.add_category_budget(category, limit)
        
        # Сохраняем в "базу данных"
        self._db[budget.id] = budget
        
        logger.info(f"Создан новый месячный бюджет: {budget.name} для семьи {family_id}")
        return budget
    
    async def get_budget(self, budget_id: str) -> Optional[Budget]:
        """
        Получает бюджет по ID.
        
        Args:
            budget_id: ID бюджета
            
        Returns:
            Бюджет или None, если бюджет не найден
        """
        return self._db.get(budget_id)
    
    async def get_budgets_for_family(
        self,
        family_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Budget]:
        """
        Получает список бюджетов для семьи с возможностью фильтрации по периоду.
        
        Args:
            family_id: ID семьи
            start_date: Начальная дата для фильтрации
            end_date: Конечная дата для фильтрации
            
        Returns:
            Список бюджетов, соответствующих условиям фильтрации
        """
        budgets = [
            budget for budget in self._db.values()
            if budget.family_id == family_id
        ]
        
        # Применяем фильтры
        if start_date:
            budgets = [b for b in budgets if b.period_end >= start_date]
        
        if end_date:
            budgets = [b for b in budgets if b.period_start <= end_date]
        
        # Сортируем по началу периода (от новых к старым)
        budgets.sort(key=lambda b: b.period_start, reverse=True)
        
        return budgets
    
    async def get_current_budget(self, family_id: str) -> Optional[Budget]:
        """
        Получает текущий активный бюджет для семьи.
        
        Args:
            family_id: ID семьи
            
        Returns:
            Текущий бюджет или None, если активный бюджет не найден
        """
        now = datetime.now()
        
        # Ищем бюджет, который включает текущую дату
        for budget in self._db.values():
            if (budget.family_id == family_id and
                budget.period_start <= now <= budget.period_end):
                return budget
        
        return None
    
    async def update_budget(
        self,
        budget_id: str,
        **kwargs
    ) -> Optional[Budget]:
        """
        Обновляет бюджет.
        
        Args:
            budget_id: ID бюджета
            **kwargs: Атрибуты для обновления
            
        Returns:
            Обновленный бюджет или None, если бюджет не найден
        """
        budget = self._db.get(budget_id)
        if not budget:
            logger.warning(f"Не удалось найти бюджет с ID {budget_id}")
            return None
        
        # Обновляем атрибуты
        for key, value in kwargs.items():
            if hasattr(budget, key) and key not in ['id', 'family_id', 'created_at', 'category_budgets']:
                setattr(budget, key, value)
        
        # Обновляем время изменения
        budget.updated_at = datetime.now()
        
        # Обновляем в "базе данных"
        self._db[budget_id] = budget
        
        logger.info(f"Обновлен бюджет {budget_id}")
        return budget
    
    async def update_category_limit(
        self,
        budget_id: str,
        category: BudgetCategory,
        limit: Decimal
    ) -> bool:
        """
        Обновляет лимит расходов по категории.
        
        Args:
            budget_id: ID бюджета
            category: Категория расходов
            limit: Новый лимит расходов
            
        Returns:
            True, если лимит обновлен, иначе False
        """
        budget = self._db.get(budget_id)
        if not budget:
            logger.warning(f"Не удалось найти бюджет с ID {budget_id}")
            return False
        
        success = budget.update_category_limit(category, limit)
        
        if success:
            # Обновляем в "базе данных"
            self._db[budget_id] = budget
            logger.info(f"Обновлен лимит по категории {category.value} в бюджете {budget_id}")
        
        return success
    
    async def add_transaction_to_budget(
        self,
        budget_id: str,
        transaction: Transaction
    ) -> bool:
        """
        Добавляет транзакцию в бюджет.
        
        Args:
            budget_id: ID бюджета
            transaction: Транзакция для добавления
            
        Returns:
            True, если транзакция успешно добавлена, иначе False
        """
        budget = self._db.get(budget_id)
        if not budget:
            logger.warning(f"Не удалось найти бюджет с ID {budget_id}")
            return False
        
        success = budget.process_transaction(transaction)
        
        if success:
            # Обновляем в "базе данных"
            self._db[budget_id] = budget
            logger.info(f"Добавлена транзакция {transaction.id} в бюджет {budget_id}")
        
        return success
    
    async def delete_budget(self, budget_id: str) -> bool:
        """
        Удаляет бюджет.
        
        Args:
            budget_id: ID бюджета
            
        Returns:
            True, если бюджет был удален, иначе False
        """
        if budget_id not in self._db:
            logger.warning(f"Не удалось найти бюджет с ID {budget_id}")
            return False
        
        del self._db[budget_id]
        logger.info(f"Удален бюджет {budget_id}")
        return True


class FinancialGoalRepository:
    """Репозиторий для работы с финансовыми целями."""
    
    def __init__(self, db_connection=None):
        """
        Инициализация репозитория финансовых целей.
        
        Args:
            db_connection: Подключение к базе данных (в будущем реализации)
        """
        # В MVP будем использовать in-memory хранилище
        # В будущем здесь будет интеграция с реальной БД
        self._db = {}  # Dict[goal_id, FinancialGoal]
        self._db_connection = db_connection
    
    async def create_goal(
        self,
        name: str,
        target_amount: Decimal,
        family_id: str,
        created_by: str,
        deadline: Optional[datetime] = None,
        current_amount: Decimal = Decimal('0'),
        currency: str = "RUB",
        priority: GoalPriority = GoalPriority.MEDIUM,
        notes: Optional[str] = None
    ) -> FinancialGoal:
        """
        Создает новую финансовую цель.
        
        Args:
            name: Название цели
            target_amount: Целевая сумма
            family_id: ID семьи
            created_by: ID пользователя, создавшего цель
            deadline: Дата дедлайна
            current_amount: Текущая сумма накоплений
            currency: Валюта цели
            priority: Приоритет цели
            notes: Дополнительные заметки
            
        Returns:
            Созданная финансовая цель
        """
        goal_id = generate_uuid()
        
        # Создаем финансовую цель
        goal = FinancialGoal(
            id=goal_id,
            name=name,
            target_amount=target_amount,
            current_amount=current_amount,
            currency=currency,
            start_date=datetime.now(),
            deadline=deadline,
            family_id=family_id,
            created_by=created_by,
            priority=priority,
            notes=notes
        )
        
        # Сохраняем в "базу данных"
        self._db[goal_id] = goal
        
        logger.info(f"Создана новая финансовая цель: {name} для семьи {family_id}")
        return goal
    
    async def get_goal(self, goal_id: str) -> Optional[FinancialGoal]:
        """
        Получает финансовую цель по ID.
        
        Args:
            goal_id: ID финансовой цели
            
        Returns:
            Финансовая цель или None, если цель не найдена
        """
        return self._db.get(goal_id)
    
    async def get_goals_for_family(
        self,
        family_id: str,
        include_completed: bool = False
    ) -> List[FinancialGoal]:
        """
        Получает список финансовых целей для семьи.
        
        Args:
            family_id: ID семьи
            include_completed: Включать ли завершенные цели
            
        Returns:
            Список финансовых целей
        """
        goals = [
            goal for goal in self._db.values()
            if goal.family_id == family_id
        ]
        
        # Фильтруем завершенные цели, если не нужно их включать
        if not include_completed:
            goals = [goal for goal in goals if not goal.is_completed()]
        
        # Сортируем по приоритету и дедлайну
        def sort_key(goal):
            # Сначала сортируем по приоритету (высокий приоритет в начале)
            priority_value = {
                GoalPriority.URGENT: 0,
                GoalPriority.HIGH: 1,
                GoalPriority.MEDIUM: 2,
                GoalPriority.LOW: 3
            }.get(goal.priority, 4)
            
            # Затем по дедлайну (ближайшие дедлайны в начале)
            # Если дедлайн не указан, используем далекую дату
            deadline = goal.deadline or datetime(9999, 12, 31)
            
            return (priority_value, deadline)
        
        goals.sort(key=sort_key)
        
        return goals
    
    async def update_goal(
        self,
        goal_id: str,
        **kwargs
    ) -> Optional[FinancialGoal]:
        """
        Обновляет финансовую цель.
        
        Args:
            goal_id: ID финансовой цели
            **kwargs: Атрибуты для обновления
            
        Returns:
            Обновленная финансовая цель или None, если цель не найдена
        """
        goal = self._db.get(goal_id)
        if not goal:
            logger.warning(f"Не удалось найти финансовую цель с ID {goal_id}")
            return None
        
        # Обновляем атрибуты
        for key, value in kwargs.items():
            if hasattr(goal, key) and key not in ['id', 'family_id', 'created_at']:
                setattr(goal, key, value)
        
        # Обновляем время изменения
        goal.updated_at = datetime.now()
        
        # Обновляем в "базе данных"
        self._db[goal_id] = goal
        
        logger.info(f"Обновлена финансовая цель {goal_id}")
        return goal
    
    async def update_goal_progress(
        self,
        goal_id: str,
        amount: Decimal
    ) -> Optional[FinancialGoal]:
        """
        Обновляет прогресс финансовой цели.
        
        Args:
            goal_id: ID финансовой цели
            amount: Сумма, на которую нужно увеличить прогресс
            
        Returns:
            Обновленная финансовая цель или None, если цель не найдена
        """
        goal = self._db.get(goal_id)
        if not goal:
            logger.warning(f"Не удалось найти финансовую цель с ID {goal_id}")
            return None
        
        # Обновляем прогресс
        goal.update_progress(amount)
        
        # Обновляем в "базе данных"
        self._db[goal_id] = goal
        
        logger.info(f"Обновлен прогресс финансовой цели {goal_id}")
        return goal
    
    async def delete_goal(self, goal_id: str) -> bool:
        """
        Удаляет финансовую цель.
        
        Args:
            goal_id: ID финансовой цели
            
        Returns:
            True, если цель была удалена, иначе False
        """
        if goal_id not in self._db:
            logger.warning(f"Не удалось найти финансовую цель с ID {goal_id}")
            return False
        
        del self._db[goal_id]
        logger.info(f"Удалена финансовая цель {goal_id}")
        return True