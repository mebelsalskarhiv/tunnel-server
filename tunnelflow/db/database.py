"""
TunnelFlow Database Configuration and Session Management
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
from typing import Generator

from .models import Base


class DatabaseManager:
    """Менеджер подключений к базе данных"""
    
    def __init__(self, database_url: str):
        """
        Инициализация подключения к БД
        
        Args:
            database_url: URL подключения PostgreSQL
                         например: postgresql://user:password@localhost:5432/tunnelflow
        """
        self.database_url = database_url
        self.engine = create_engine(
            database_url,
            pool_size=20,
            max_overflow=40,
            pool_recycle=3600,
            pool_pre_ping=True,
            echo=False,  # Включить для отладки SQL запросов
        )
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine,
            class_=Session,
        )
    
    def init_db(self):
        """Создать все таблицы в БД"""
        Base.metadata.create_all(bind=self.engine)
    
    def drop_db(self):
        """Удалить все таблицы (ОСТОРОЖНО!)"""
        Base.metadata.drop_all(bind=self.engine)
    
    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """
        Контекстный менеджер для сессии БД
        
        Usage:
            with db_manager.get_session() as session:
                users = session.query(User).all()
        """
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    def get_session_direct(self) -> Session:
        """
        Получить сессию напрямую (не забудьте закрыть!)
        
        Лучше использовать get_session() как контекстный менеджер
        """
        return self.SessionLocal()


# Глобальный экземпляр (будет инициализирован в main.py)
db_manager: DatabaseManager = None


def get_db() -> Generator[Session, None, None]:
    """
    Dependency для FastAPI endpoints
    
    Usage in API:
        @app.get("/users")
        def get_users(db: Session = Depends(get_db)):
            return db.query(User).all()
    """
    if db_manager is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    
    with db_manager.get_session() as session:
        yield session


def init_database(database_url: str) -> DatabaseManager:
    """Инициализировать глобальный db_manager"""
    global db_manager
    db_manager = DatabaseManager(database_url)
    db_manager.init_db()
    return db_manager
