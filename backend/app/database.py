"""
Database configuration and session management.
Handles PostgreSQL connection via SQLAlchemy with Supabase.
"""
import os
from urllib.parse import quote_plus
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

# Database connection - Supabase PostgreSQL
DB_HOST = os.environ.get('DB_HOST', 'aws-1-sa-east-1.pooler.supabase.com')
DB_PORT = os.environ.get('DB_PORT', '6543')
DB_NAME = os.environ.get('POSTGRES_DB', 'postgres')
DB_USER = os.environ.get('DB_USER', 'postgres.ehrfwytvchhrzywnutyf')
DB_PASSWORD = os.environ.get('DB_PASSWORD', '@Mgfj125256')

# URL encode the password to handle special characters like @
DATABASE_URL = os.environ.get('DATABASE_URL', '')
if not DATABASE_URL:
    encoded_password = quote_plus(DB_PASSWORD)
    DATABASE_URL = f"postgresql://{DB_USER}:{encoded_password}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=300)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Dependency that provides a database session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
