"""
Conexão canônica com o banco de dados.
Usa settings.DATABASE_URL — obrigatório em produção.
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from .settings import settings

_url = settings.DATABASE_URL
if not _url:
    import os
    from urllib.parse import quote_plus
    _url = (
        f"postgresql://{os.environ.get('DB_USER','postgres')}:"
        f"{quote_plus(os.environ.get('DB_PASSWORD',''))}@"
        f"{os.environ.get('DB_HOST','localhost')}:"
        f"{os.environ.get('DB_PORT','5432')}/"
        f"{os.environ.get('POSTGRES_DB','postgres')}"
    )

engine = create_engine(_url, pool_pre_ping=True, pool_recycle=300)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
