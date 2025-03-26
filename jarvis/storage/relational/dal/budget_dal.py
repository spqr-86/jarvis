from datetime import datetime
from sqlalchemy import and_

from jarvis.storage.relational.dal.base import BaseDAO
from jarvis.storage.relational.models.budget import Budget, Transaction, CategoryBudget


class BudgetDAO(BaseDAO[Budget, dict, dict]):
    """Data Access Object for budgets."""
    
    def __init__(self, db=None):
        super().__init__(Budget, db)
    
    def get_current_for_family(self, family_id: str):
        """Get the current active budget for a family."""
        now = datetime.now()
        return self._db.query(Budget).filter(
            and_(
                Budget.family_id == family_id,
                Budget.period_start <= now,
                Budget.period_end >= now
            )
        ).first()
    
    def get_for_family(self, family_id: str):
        """Get all budgets for a family."""
        return self._db.query(Budget).filter(
            Budget.family_id == family_id
        ).order_by(Budget.period_start.desc()).all()


class TransactionDAO(BaseDAO[Transaction, dict, dict]):
    """Data Access Object for transactions."""
    
    def __init__(self, db=None):
        super().__init__(Transaction, db)
    
    def get_for_family(self, family_id: str, start_date=None, end_date=None):
        """Get transactions for a family with optional date filtering."""
        query = self._db.query(Transaction).filter(
            Transaction.family_id == family_id
        )
        
        if start_date:
            query = query.filter(Transaction.date >= start_date)
        
        if end_date:
            query = query.filter(Transaction.date <= end_date)
        
        return query.order_by(Transaction.date.desc()).all()
    
    def get_for_budget(self, budget_id: str):
        """Get all transactions for a specific budget."""
        return self._db.query(Transaction).filter(
            Transaction.budget_id == budget_id
        ).order_by(Transaction.date.desc()).all()


class CategoryBudgetDAO(BaseDAO[CategoryBudget, dict, dict]):
    """Data Access Object for category budgets."""
    
    def __init__(self, db=None):
        super().__init__(CategoryBudget, db)
    
    def get_for_budget(self, budget_id: str):
        """Get all category budgets for a specific budget."""
        return self._db.query(CategoryBudget).filter(
            CategoryBudget.budget_id == budget_id
        ).all()