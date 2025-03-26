from jarvis.storage.relational.dal.user_dal import UserDAO, FamilyDAO
from jarvis.storage.relational.dal.shopping_dal import ShoppingListDAO, ShoppingItemDAO
from jarvis.storage.relational.dal.budget_dal import BudgetDAO, TransactionDAO, CategoryBudgetDAO, FinancialGoalDAO

# Create instances of DAOs for easy import
user_dao = UserDAO()
family_dao = FamilyDAO()
shopping_list_dao = ShoppingListDAO()
shopping_item_dao = ShoppingItemDAO()
budget_dao = BudgetDAO()
transaction_dao = TransactionDAO()
category_budget_dao = CategoryBudgetDAO()
financial_goal_dao = FinancialGoalDAO()

# Export all DAOs for easy import
__all__ = [
    "user_dao", "family_dao",
    "shopping_list_dao", "shopping_item_dao",
    "budget_dao", "transaction_dao", "category_budget_dao", "financial_goal_dao",
    "UserDAO", "FamilyDAO",
    "ShoppingListDAO", "ShoppingItemDAO",
    "BudgetDAO", "TransactionDAO", "CategoryBudgetDAO", "FinancialGoalDAO",
]