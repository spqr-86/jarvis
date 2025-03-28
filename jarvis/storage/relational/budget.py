"""
Репозиторий для работы с финансовыми данными в реляционной базе данных.
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Any, Union, Tuple
from uuid import uuid4

from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

from jarvis.storage.database import get_db_session
from jarvis.storage.relational.models.budget import (
    Transaction as TransactionEntity, 
    Budget as BudgetEntity,
    CategoryBudget as CategoryBudgetEntity,
    BudgetCategoryEnum, 
    TransactionTypeEnum
)
from jarvis.core.models.budget import (
    Transaction, Budget, CategoryBudget,
    BudgetCategory, TransactionType, RecurringFrequency, GoalPriority
)

logger = logging.getLogger(__name__)


class TransactionRepository:
    """Репозиторий для работы с финансовыми транзакциями."""

    def __init__(self, db_session=None):
        """
        Инициализация репозитория транзакций.
        
        Args:
            db_session: Подключение к базе данных
        """
        self._db = db_session or next(get_db_session())
    
    def _to_model(self, db_transaction: TransactionEntity) -> Transaction:
        """Convert database entity to domain model."""
        transaction = Transaction(
            id=db_transaction.id,
            amount=db_transaction.amount,
            currency=db_transaction.currency,
            category=BudgetCategory(db_transaction.category.value),
            transaction_type=TransactionType(db_transaction.transaction_type.value),
            description=db_transaction.description,
            date=db_transaction.date,
            family_id=db_transaction.family_id,
            created_by=db_transaction.user_id,
            tags=[],  # Tags would be handled separately in a real implementation
            is_recurring=db_transaction.is_recurring,
            recurring_frequency=RecurringFrequency(db_transaction.recurring_frequency) if db_transaction.recurring_frequency else None,
            created_at=db_transaction.created_at
        )
        if db_transaction.updated_at:
            transaction.updated_at = db_transaction.updated_at
        
        return transaction
    
    def _to_db_entity(self, transaction: Transaction, budget_id: Optional[str] = None) -> TransactionEntity:
        """Convert domain model to database entity."""
        return TransactionEntity(
            id=transaction.id,
            amount=transaction.amount,
            currency=transaction.currency,
            category=BudgetCategoryEnum(transaction.category.value),
            transaction_type=TransactionTypeEnum(transaction.transaction_type.value),
            description=transaction.description,
            date=transaction.date,
            family_id=transaction.family_id,
            user_id=transaction.created_by,
            budget_id=budget_id,
            is_recurring=transaction.is_recurring,
            recurring_frequency=transaction.recurring_frequency.value if transaction.recurring_frequency else None,
            created_at=transaction.created_at,
            updated_at=transaction.updated_at
        )
    
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
        recurring_frequency: Optional[RecurringFrequency] = None,
        budget_id: Optional[str] = None
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
            budget_id: ID бюджета (если транзакция привязана к бюджету)
            
        Returns:
            Созданная транзакция
        """
        transaction_id = str(uuid4())
        
        # Если дата не указана, используем текущее время
        if date is None:
            date = datetime.now()
        
        # Создаем запись в базе данных
        db_transaction = TransactionEntity(
            id=transaction_id,
            amount=amount,
            currency=currency,
            category=BudgetCategoryEnum(category.value),
            transaction_type=TransactionTypeEnum(transaction_type.value),
            description=description,
            date=date,
            family_id=family_id,
            user_id=created_by,
            budget_id=budget_id,
            is_recurring=is_recurring,
            recurring_frequency=recurring_frequency.value if recurring_frequency else None
        )
        
        self._db.add(db_transaction)
        self._db.commit()
        self._db.refresh(db_transaction)
        
        logger.info(f"Создана новая транзакция: {transaction_id} ({transaction_type.value}) для семьи {family_id}")
        return self._to_model(db_transaction)
    
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
        db_transaction = self._db.query(TransactionEntity).filter(
            TransactionEntity.id == transaction_id
        ).first()
        
        if not db_transaction:
            return None
            
        return self._to_model(db_transaction)
    
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
        query = self._db.query(TransactionEntity).filter(
            TransactionEntity.family_id == family_id
        )
        
        # Применяем фильтры
        if start_date:
            query = query.filter(TransactionEntity.date >= start_date)
        
        if end_date:
            query = query.filter(TransactionEntity.date <= end_date)
        
        if transaction_type:
            query = query.filter(TransactionEntity.transaction_type == TransactionTypeEnum(transaction_type.value))
        
        if category:
            query = query.filter(TransactionEntity.category == BudgetCategoryEnum(category.value))
        
        # Сортируем по дате (от новых к старым)
        query = query.order_by(desc(TransactionEntity.date))
        
        # Применяем ограничение по количеству, если указано
        if limit is not None:
            query = query.limit(limit)
        
        db_transactions = query.all()
        return [self._to_model(t) for t in db_transactions]
    
    async def get_recurring_transactions(self, family_id: str) -> List[Transaction]:
        """
        Получает список повторяющихся транзакций для семьи.
        
        Args:
            family_id: ID семьи
            
        Returns:
            Список повторяющихся транзакций
        """
        db_transactions = self._db.query(TransactionEntity).filter(
            and_(
                TransactionEntity.family_id == family_id,
                TransactionEntity.is_recurring == True
            )
        ).all()
        
        return [self._to_model(t) for t in db_transactions]
    
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
        db_transaction = self._db.query(TransactionEntity).filter(
            TransactionEntity.id == transaction_id
        ).first()
        
        if not db_transaction:
            logger.warning(f"Не удалось найти транзакцию с ID {transaction_id}")
            return None
        
        # Обновляем атрибуты
        for key, value in kwargs.items():
            if hasattr(db_transaction, key) and key not in ['id', 'family_id', 'created_at']:
                # Handle enum conversions
                if key == 'category' and isinstance(value, BudgetCategory):
                    setattr(db_transaction, key, BudgetCategoryEnum(value.value))
                elif key == 'transaction_type' and isinstance(value, TransactionType):
                    setattr(db_transaction, key, TransactionTypeEnum(value.value))
                elif key == 'recurring_frequency' and isinstance(value, RecurringFrequency):
                    setattr(db_transaction, key, value.value)
                else:
                    setattr(db_transaction, key, value)
        
        # Обновляем время изменения
        db_transaction.updated_at = datetime.now()
        
        # Сохраняем изменения
        self._db.add(db_transaction)
        self._db.commit()
        self._db.refresh(db_transaction)
        
        logger.info(f"Обновлена транзакция {transaction_id}")
        return self._to_model(db_transaction)
    
    async def delete_transaction(self, transaction_id: str) -> bool:
        """
        Удаляет транзакцию.
        
        Args:
            transaction_id: ID транзакции
            
        Returns:
            True, если транзакция была удалена, иначе False
        """
        db_transaction = self._db.query(TransactionEntity).filter(
            TransactionEntity.id == transaction_id
        ).first()
        
        if not db_transaction:
            logger.warning(f"Не удалось найти транзакцию с ID {transaction_id}")
            return False
        
        self._db.delete(db_transaction)
        self._db.commit()
        
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
                "percentage": round(float(percentage), 2)
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
    
    def __init__(self, db_session=None):
        """
        Инициализация репозитория бюджетов.
        
        Args:
            db_session: Подключение к базе данных
        """
        self._db = db_session or next(get_db_session())

    async def get_current_budget(
        self, 
        family_id: str, 
        at_date: Optional[datetime] = None
    ) -> Optional[Budget]:
        """
        Получает текущий активный бюджет для семьи.
        
        Args:
            family_id: ID семьи
            at_date: Дата, на которую ищется бюджет (по умолчанию текущая)
            
        Returns:
            Текущий бюджет или None, если не найден
        """
        if at_date is None:
            at_date = datetime.now()
        
        # Находим бюджет, который действует на указанную дату
        db_budget = self._db.query(BudgetEntity).filter(
            and_(
                BudgetEntity.family_id == family_id,
                BudgetEntity.period_start <= at_date,
                BudgetEntity.period_end >= at_date
            )
        ).first()
        
        if not db_budget:
            logger.info(f"Не найден активный бюджет для семьи {family_id}")
            return None
        
        return self._to_model(db_budget)
    
    async def get_budget(self, budget_id: str) -> Optional[Budget]:
        """
        Получает бюджет по его ID.
        
        Args:
            budget_id: ID бюджета
            
        Returns:
            Бюджет или None, если не найден
        """
        db_budget = self._db.query(BudgetEntity).filter(BudgetEntity.id == budget_id).first()
        
        if not db_budget:
            logger.warning(f"Не найден бюджет с ID {budget_id}")
            return None
        
        return self._to_model(db_budget)
    
    async def get_budgets_for_family(
        self, 
        family_id: str, 
        include_past: bool = False
    ) -> List[Budget]:
        """
        Получает список бюджетов для семьи.
        
        Args:
            family_id: ID семьи
            include_past: Включать ли прошедшие бюджеты
            
        Returns:
            Список бюджетов
        """
        now = datetime.now()
        
        # Базовый запрос для получения бюджетов семьи
        query = self._db.query(BudgetEntity).filter(
            BudgetEntity.family_id == family_id
        )
        
        # Если не включаем прошедшие, фильтруем по текущей дате
        if not include_past:
            query = query.filter(
                BudgetEntity.period_end >= now
            )
        
        # Сортируем по дате начала периода (от новых к старым)
        query = query.order_by(BudgetEntity.period_start.desc())
        
        db_budgets = query.all()
        
        return [self._to_model(budget) for budget in db_budgets]
    
    def _to_model(self, db_budget: BudgetEntity) -> Budget:
        """Convert database budget entity to domain model."""
        # Create category budgets dictionary
        category_budgets = {}
        for db_category_budget in db_budget.category_budgets:
            category = BudgetCategory(db_category_budget.category.value)
            category_budget = CategoryBudget(
                category=category,
                limit=db_category_budget.limit,
                currency=db_category_budget.currency,
                spent=db_category_budget.spent
            )
            category_budgets[category] = category_budget
        
        # Create budget model
        budget = Budget(
            id=db_budget.id,
            name=db_budget.name,
            family_id=db_budget.family_id,
            period_start=db_budget.period_start,
            period_end=db_budget.period_end,
            currency=db_budget.currency,
            income_plan=db_budget.income_plan,
            income_actual=db_budget.income_actual,
            category_budgets=category_budgets,
            created_by=db_budget.created_by,
            created_at=db_budget.created_at
        )
        
        if db_budget.updated_at:
            budget.updated_at = db_budget.updated_at
        
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
            Созданный бюджет
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
        
        # Создаем бюджет в базе данных
        budget_id = str(uuid4())
        
        db_budget = BudgetEntity(
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
        
        self._db.add(db_budget)
        self._db.commit()
        self._db.refresh(db_budget)
        
        # Добавляем лимиты по категориям, если указаны
        if category_limits:
            for category, limit in category_limits.items():
                db_category_budget = CategoryBudgetEntity(
                    id=str(uuid4()),
                    budget_id=budget_id,
                    category=BudgetCategoryEnum(category.value),
                    limit=limit,
                    spent=Decimal('0'),
                    currency=currency
                )
                self._db.add(db_category_budget)
            
            self._db.commit()
            # Refresh to get the category budgets
            db_budget = self._db.query(BudgetEntity).filter(BudgetEntity.id == budget_id).first()
        
        logger.info(f"Создан новый бюджет: {name} для семьи {family_id}")
        return self._to_model(db_budget)
    
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
        budget_id = str(uuid4())
        
        # Создаем бюджет в базе данных
        db_budget = BudgetEntity(
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
        
        self._db.add(db_budget)
        self._db.commit()
        self._db.refresh(db_budget)
        
        # Добавляем лимиты по категориям, если указаны
        if category_limits:
            for category, limit in category_limits.items():
                db_category_budget = CategoryBudgetEntity(
                    id=str(uuid4()),
                    budget_id=budget_id,
                    category=BudgetCategoryEnum(category.value),
                    limit=limit,
                    spent=Decimal('0'),
                    currency=currency
                )
                self._db.add(db_category_budget)
            
            self._db.commit()
            # Refresh to get the category budgets
            db_budget = self._db.query(BudgetEntity).filter(BudgetEntity.id == budget_id).first()
        
        logger.info(f"Создан новый бюджет: {name} для семьи {family_id}")
        return self._to_model(db_budget)
    
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
        db_budget = self._db.query(BudgetEntity).filter(BudgetEntity.id == budget_id).first()
        if not db_budget:
            logger.warning(f"Не удалось найти бюджет с ID {budget_id}")
            return None
        
        # Обновляем атрибуты
        for key, value in kwargs.items():
            if hasattr(db_budget, key) and key not in ['id', 'family_id', 'created_at', 'category_budgets']:
                setattr(db_budget, key, value)
        
        # Обновляем время изменения
        db_budget.updated_at = datetime.now()
        
        # Сохраняем изменения
        self._db.add(db_budget)
        self._db.commit()
        self._db.refresh(db_budget)
        
        logger.info(f"Обновлен бюджет {budget_id}")
        return self._to_model(db_budget)
    
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
        # Проверяем, существует ли бюджет
        db_budget = self._db.query(BudgetEntity).filter(BudgetEntity.id == budget_id).first()
        if not db_budget:
            logger.warning(f"Не удалось найти бюджет с ID {budget_id}")
            return False
        
        # Ищем категорию бюджета
        db_category = BudgetCategoryEnum(category.value)
        db_category_budget = self._db.query(CategoryBudgetEntity).filter(
            and_(
                CategoryBudgetEntity.budget_id == budget_id,
                CategoryBudgetEntity.category == db_category
            )
        ).first()
        
        if db_category_budget:
            # Обновляем существующий лимит
            db_category_budget.limit = limit
            self._db.add(db_category_budget)
        else:
            # Создаем новый лимит
            db_category_budget = CategoryBudgetEntity(
                id=str(uuid4()),
                budget_id=budget_id,
                category=db_category,
                limit=limit,
                spent=Decimal('0'),
                currency=db_budget.currency
            )
            self._db.add(db_category_budget)
        
        self._db.commit()
        logger.info(f"Обновлен лимит по категории {category.value} в бюджете {budget_id}")
        return True
    
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
        # Получаем бюджет
        db_budget = self._db.query(BudgetEntity).filter(BudgetEntity.id == budget_id).first()
        if not db_budget:
            logger.warning(f"Не удалось найти бюджет с ID {budget_id}")
            return False
        
        # Проверяем, что транзакция входит в период бюджета
        if transaction.date < db_budget.period_start or transaction.date > db_budget.period_end:
            logger.warning(f"Транзакция {transaction.id} не входит в период бюджета {budget_id}")
            return False
        
        # Проверяем, что транзакция принадлежит той же семье
        if transaction.family_id != db_budget.family_id:
            logger.warning(f"Транзакция {transaction.id} принадлежит другой семье")
            return False
        
        # Получаем или создаем запись транзакции в базе данных
        db_transaction = self._db.query(TransactionEntity).filter(TransactionEntity.id == transaction.id).first()
        
        if db_transaction:
            # Обновляем связь с бюджетом
            db_transaction.budget_id = budget_id
            self._db.add(db_transaction)
        else:
            # Создаем новую транзакцию
            transaction_repo = TransactionRepository(self._db)
            db_transaction = transaction_repo._to_db_entity(transaction, budget_id)
            self._db.add(db_transaction)
        
        # Обновляем бюджет в зависимости от типа транзакции
        if transaction.transaction_type == TransactionType.INCOME:
            # Увеличиваем фактический доход
            db_budget.income_actual += transaction.amount
        elif transaction.transaction_type == TransactionType.EXPENSE:
            # Увеличиваем расходы по категории
            db_category = BudgetCategoryEnum(transaction.category.value)
            db_category_budget = self._db.query(CategoryBudgetEntity).filter(
                and_(
                    CategoryBudgetEntity.budget_id == budget_id,
                    CategoryBudgetEntity.category == db_category
                )
            ).first()
            
            if not db_category_budget:
                # Создаем запись для категории, если ее еще нет
                db_category_budget = CategoryBudgetEntity(
                    id=str(uuid4()),
                    budget_id=budget_id,
                    category=db_category,
                    limit=Decimal('0'),  # Лимит по умолчанию
                    spent=transaction.amount,
                    currency=db_budget.currency
                )
                self._db.add(db_category_budget)
            else:
                # Увеличиваем расходы по существующей категории
                db_category_budget.spent += transaction.amount
                self._db.add(db_category_budget)
        
        # Обновляем время изменения бюджета
        db_budget.updated_at = datetime.now()
        self._db.add(db_budget)
        
        self._db.commit()
        logger.info(f"Добавлена транзакция {transaction.id} в бюджет {budget_id}")
        return True
    
    async def delete_budget(self, budget_id: str) -> bool:
        """
        Удаляет бюджет.
        
        Args:
            budget_id: ID бюджета
            
        Returns:
            True, если бюджет был удален, иначе False
        """
        db_budget = self._db.query(BudgetEntity).filter(BudgetEntity.id == budget_id).first()
        if not db_budget:
            logger.warning(f"Не удалось найти бюджет с ID {budget_id}")
            return False
        
        # Удаляем бюджет
        self._db.delete(db_budget)
        self._db.commit()
        
        logger.info(f"Удален бюджет {budget_id}")
        return True


class FinancialGoalRepository:
    """Репозиторий для работы с финансовыми целями."""
    
    def __init__(self, db=None):
        """
        Инициализация репозитория финансовых целей.
        
        Args:
            db: Подключение к базе данных (в будущем реализации)
        """
        from jarvis.storage.relational.models.financial import FinancialGoal as FinancialGoalEntity, GoalPriorityEnum
        
        self.FinancialGoalEntity = FinancialGoalEntity
        self.GoalPriorityEnum = GoalPriorityEnum
        self._db = db or next(get_db_session())
    
    def _to_model(self, db_goal):
        """Convert database entity to domain model."""
        from jarvis.core.models.budget import FinancialGoal, GoalPriority
        
        goal = FinancialGoal(
            id=db_goal.id,
            name=db_goal.name,
            target_amount=db_goal.target_amount,
            current_amount=db_goal.current_amount,
            currency=db_goal.currency,
            start_date=db_goal.start_date,
            deadline=db_goal.deadline,
            family_id=db_goal.family_id,
            created_by=db_goal.created_by,
            priority=GoalPriority(db_goal.priority.value),
            notes=db_goal.notes,
            created_at=db_goal.created_at
        )
        
        if db_goal.updated_at:
            goal.updated_at = db_goal.updated_at
            
        return goal
    
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
    ):
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
        goal_id = str(uuid4())
        
        # Создаем цель в базе данных
        db_goal = self.FinancialGoalEntity(
            id=goal_id,
            name=name,
            target_amount=target_amount,
            current_amount=current_amount,
            currency=currency,
            start_date=datetime.now(),
            deadline=deadline,
            family_id=family_id,
            created_by=created_by,
            priority=self.GoalPriorityEnum(priority.value),
            notes=notes
        )
        
        self._db.add(db_goal)
        self._db.commit()
        self._db.refresh(db_goal)
        
        logger.info(f"Создана новая финансовая цель: {name} для семьи {family_id}")
        return self._to_model(db_goal)
    
    async def get_goal(self, goal_id: str):
        """
        Получает финансовую цель по ID.
        
        Args:
            goal_id: ID финансовой цели
            
        Returns:
            Финансовая цель или None, если цель не найдена
        """
        db_goal = self._db.query(self.FinancialGoalEntity).filter(self.FinancialGoalEntity.id == goal_id).first()
        
        if not db_goal:
            return None
            
        return self._to_model(db_goal)
    
    async def get_goals_for_family(
        self,
        family_id: str,
        include_completed: bool = False
    ):
        """
        Получает список финансовых целей для семьи.
        
        Args:
            family_id: ID семьи
            include_completed: Включать ли завершенные цели
            
        Returns:
            Список финансовых целей
        """
        query = self._db.query(self.FinancialGoalEntity).filter(
            self.FinancialGoalEntity.family_id == family_id
        )
        
        db_goals = query.all()
        goals = [self._to_model(g) for g in db_goals]
        
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
    ):
        """
        Обновляет финансовую цель.
        
        Args:
            goal_id: ID финансовой цели
            **kwargs: Атрибуты для обновления
            
        Returns:
            Обновленная финансовая цель или None, если цель не найдена
        """
        db_goal = self._db.query(self.FinancialGoalEntity).filter(self.FinancialGoalEntity.id == goal_id).first()
        if not db_goal:
            logger.warning(f"Не удалось найти финансовую цель с ID {goal_id}")
            return None
        
        # Обновляем атрибуты
        for key, value in kwargs.items():
            if hasattr(db_goal, key) and key not in ['id', 'family_id', 'created_at']:
                # Handle enum conversions
                if key == 'priority' and isinstance(value, GoalPriority):
                    setattr(db_goal, key, self.GoalPriorityEnum(value.value))
                else:
                    setattr(db_goal, key, value)
        
        # Обновляем время изменения
        db_goal.updated_at = datetime.now()
        
        # Сохраняем изменения
        self._db.add(db_goal)
        self._db.commit()
        self._db.refresh(db_goal)
        
        logger.info(f"Обновлена финансовая цель {goal_id}")
        return self._to_model(db_goal)
    
    async def update_goal_progress(
        self,
        goal_id: str,
        amount: Decimal
    ):
        """
        Обновляет прогресс финансовой цели.
        
        Args:
            goal_id: ID финансовой цели
            amount: Сумма, на которую нужно увеличить прогресс
            
        Returns:
            Обновленная финансовая цель или None, если цель не найдена
        """
        db_goal = self._db.query(self.FinancialGoalEntity).filter(self.FinancialGoalEntity.id == goal_id).first()
        if not db_goal:
            logger.warning(f"Не удалось найти финансовую цель с ID {goal_id}")
            return None
        
        # Обновляем прогресс
        db_goal.current_amount += amount
        db_goal.updated_at = datetime.now()
        
        # Сохраняем изменения
        self._db.add(db_goal)
        self._db.commit()
        self._db.refresh(db_goal)
        
        logger.info(f"Обновлен прогресс финансовой цели {goal_id}")
        return self._to_model(db_goal)
    
    async def delete_goal(self, goal_id: str) -> bool:
        """
        Удаляет финансовую цель.
        
        Args:
            goal_id: ID финансовой цели
            
        Returns:
            True, если цель была удалена, иначе False
        """
        db_goal = self._db.query(self.FinancialGoalEntity).filter(self.FinancialGoalEntity.id == goal_id).first()
        if not db_goal:
            logger.warning(f"Не удалось найти финансовую цель с ID {goal_id}")
            return False
        
        # Удаляем цель
        self._db.delete(db_goal)
        self._db.commit()
        
        logger.info(f"Удалена финансовая цель {goal_id}")
        return True
