from typing import List, Optional, Generic, TypeVar, Type, Dict, Any, Union
from uuid import uuid4

from sqlalchemy.orm import Session
from pydantic import BaseModel

from jarvis.storage.database import Base, get_db_session

# Define generic types for models
ModelType = TypeVar("ModelType", bound=Base)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


class BaseDAO(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """Base Data Access Object with common CRUD operations."""
    
    def __init__(self, model: Type[ModelType], db: Session = None):
        """
        Initialize with model class and database session.
        
        Args:
            model: SQLAlchemy model class
            db: Database session (if None, will use dependency injection)
        """
        self.model = model
        self._db = db or next(get_db_session())
    
    def get(self, id: str) -> Optional[ModelType]:
        """Get a record by ID."""
        return self._db.query(self.model).filter(self.model.id == id).first()
    
    def get_multi(
        self, *, skip: int = 0, limit: int = 100, **filters
    ) -> List[ModelType]:
        """Get multiple records with filtering."""
        query = self._db.query(self.model)
        
        # Apply filters
        for field, value in filters.items():
            if hasattr(self.model, field) and value is not None:
                query = query.filter(getattr(self.model, field) == value)
        
        return query.offset(skip).limit(limit).all()
    
    def create(self, *, obj_in: CreateSchemaType, **extra_data) -> ModelType:
        """Create a new record."""
        obj_data = obj_in.dict() if isinstance(obj_in, BaseModel) else obj_in
        
        # Add extra data
        for field, value in extra_data.items():
            if hasattr(self.model, field):
                obj_data[field] = value
        
        # Generate ID if not provided
        if "id" not in obj_data:
            obj_data["id"] = str(uuid4())
        
        db_obj = self.model(**obj_data)
        self._db.add(db_obj)
        self._db.commit()
        self._db.refresh(db_obj)
        return db_obj
    
    def update(
        self, *, db_obj: ModelType, obj_in: Union[UpdateSchemaType, Dict[str, Any]]
    ) -> ModelType:
        """Update a record."""
        obj_data = obj_in.dict(exclude_unset=True) if isinstance(obj_in, BaseModel) else obj_in
        
        for field, value in obj_data.items():
            if hasattr(db_obj, field):
                setattr(db_obj, field, value)
        
        self._db.add(db_obj)
        self._db.commit()
        self._db.refresh(db_obj)
        return db_obj
    
    def delete(self, *, id: str) -> bool:
        """Delete a record by ID."""
        obj = self.get(id=id)
        if not obj:
            return False
        
        self._db.delete(obj)
        self._db.commit()
        return True