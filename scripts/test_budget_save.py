import asyncio
import sys
from pathlib import Path
from datetime import datetime
from decimal import Decimal

# Добавление корневой директории проекта в sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

from jarvis.storage.relational.budget import BudgetRepository
from jarvis.core.models.budget import BudgetCategory
from jarvis.storage.database import Base, engine
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
# Включите подробное логирование SQL-запросов
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

async def test_budget_save():
    print("Создание таблиц в базе данных...")
    Base.metadata.create_all(bind=engine)
    
    print("Инициализация репозитория бюджета...")
    repo = BudgetRepository()
    
    print("Создание тестового бюджета...")
    try:
        test_budget = await repo.create_budget(
            name="Тестовый бюджет",
            family_id="1",
            period_start=datetime(2025, 3, 1),
            period_end=datetime(2025, 3, 31),
            created_by="test_user",
            income_plan=Decimal('50000'),
            category_limits={
                BudgetCategory.FOOD: Decimal('15000'),
                BudgetCategory.TRANSPORT: Decimal('5000')
            }
        )
        
        print(f"Создан бюджет: {test_budget.id}, {test_budget.name}")
        
        # Проверяем, что бюджет сохранен
        print("Проверка сохранения бюджета...")
        saved_budget = await repo.get_budget(test_budget.id)
        if saved_budget:
            print(f"УСПЕХ: Получен сохраненный бюджет: {saved_budget.name}")
            print(f"Лимиты категорий: {len(saved_budget.category_budgets)}")
            
            # Проверяем лимиты
            if BudgetCategory.FOOD in saved_budget.category_budgets:
                food_limit = saved_budget.category_budgets[BudgetCategory.FOOD].limit
                print(f"Лимит на питание: {food_limit}")
            else:
                print("ПРЕДУПРЕЖДЕНИЕ: Категория FOOD не найдена")
                
        else:
            print("ОШИБКА: Бюджет не найден после сохранения!")
    
    except Exception as e:
        print(f"ОШИБКА при создании/получении бюджета: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_budget_save())