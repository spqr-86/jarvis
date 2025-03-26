import asyncio
from datetime import datetime
import logging

from jarvis.storage.database import Base, engine, session
from jarvis.storage.relational.models.user import User, Family
from jarvis.storage.relational.models.shopping import ShoppingList, ShoppingItem, ItemCategoryEnum
from jarvis.storage.relational.models.budget import Budget, Transaction, CategoryBudget, BudgetCategoryEnum, TransactionTypeEnum
from jarvis.storage.relational.models.financial import FinancialGoal, GoalPriorityEnum

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def init_db():
    """Initialize database with test data."""
    try:
        # Create tables
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
        
        # Create test user
        user = User(
            id="user1",
            telegram_id="12345678",
            username="test_user",
            first_name="Test",
            last_name="User"
        )
        session.add(user)
        session.commit()
        logger.info("Test user created")
        
        # Create family
        family = Family(
            id="family1",
            name="Test Family",
            created_by="user1"
        )
        session.add(family)
        session.commit()
        logger.info("Test family created")
        
        # Update user with family
        user.family_id = "family1"
        session.add(user)
        session.commit()
        logger.info("User updated with family")
        
        # Create shopping list
        shopping_list = ShoppingList(
            id="list1",
            name="Weekly Shopping",
            family_id="family1",
            created_by="user1",
            is_active=True
        )
        session.add(shopping_list)
        session.commit()
        logger.info("Shopping list created")
        
        # Add items to shopping list
        items = [
            ShoppingItem(
                id=f"item{i}",
                name=name,
                quantity=qty,
                unit=unit,
                category=category,
                shopping_list_id="list1"
            )
            for i, (name, qty, unit, category) in enumerate([
                ("Milk", 2, "l", ItemCategoryEnum.DAIRY),
                ("Bread", 1, "loaf", ItemCategoryEnum.BAKERY),
                ("Apples", 1, "kg", ItemCategoryEnum.FRUITS),
                ("Chicken", 500, "g", ItemCategoryEnum.MEAT)
            ])
        ]
        session.add_all(items)
        session.commit()
        logger.info("Shopping items created")
        
        # Create budget
        budget = Budget(
            id="budget1",
            name="April 2023",
            family_id="family1",
            created_by="user1",
            period_start=datetime(2023, 4, 1),
            period_end=datetime(2023, 4, 30),
            currency="RUB",
            income_plan=50000
        )
        session.add(budget)
        session.commit()
        logger.info("Budget created")
        
        # Add category budgets
        category_budgets = [
            CategoryBudget(
                id=f"cat_budget{i}",
                budget_id="budget1",
                category=category,
                limit=limit,
                currency="RUB"
            )
            for i, (category, limit) in enumerate([
                (BudgetCategoryEnum.FOOD, 15000),
                (BudgetCategoryEnum.HOUSING, 10000),
                (BudgetCategoryEnum.TRANSPORT, 5000),
                (BudgetCategoryEnum.ENTERTAINMENT, 3000)
            ])
        ]
        session.add_all(category_budgets)
        session.commit()
        logger.info("Category budgets created")
        
        # Create financial goal
        goal = FinancialGoal(
            id="goal1",
            name="Summer Vacation",
            target_amount=50000,
            current_amount=15000,
            currency="RUB",
            deadline=datetime(2023, 6, 1),
            family_id="family1",
            created_by="user1",
            priority=GoalPriorityEnum.MEDIUM,
            notes="Trip to the beach"
        )
        session.add(goal)
        session.commit()
        logger.info("Financial goal created")
        
        logger.info("Database initialized with test data")
    except Exception as e:
        session.rollback()
        logger.error(f"Error initializing database: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(init_db())