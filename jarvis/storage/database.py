from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session

from jarvis.config import DATABASE_URL

# Create engine
engine = create_engine(DATABASE_URL)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
session = scoped_session(SessionLocal)

# Create base class for models
Base = declarative_base()

# Dependency to get database session
def get_db_session():
    db = session()
    try:
        yield db
    finally:
        db.close()
