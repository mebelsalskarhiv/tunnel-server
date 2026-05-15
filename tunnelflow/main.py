"""
TunnelFlow Main Application Entry Point
FastAPI application setup and configuration
"""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from .db.database import init_database
from .billing.plans import initialize_plans
from .api.routes import auth, billing, stats, tunnels


# Конфигурация из переменных окружения
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://tunnelflow:tunnelflow@localhost:5432/tunnelflow")
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
DEBUG = os.getenv("DEBUG", "false").lower() == "true"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Жизненный цикл приложения"""
    # Startup
    print("🚀 Starting TunnelFlow Server...")
    
    # Инициализация БД
    print(f"📦 Connecting to database: {DATABASE_URL}")
    init_database(DATABASE_URL)
    
    # Инициализация тарифных планов
    from .db.database import db_manager
    if db_manager:
        with db_manager.get_session() as session:
            initialize_plans(session)
            print("✅ Tariff plans initialized")
    
    print("✅ TunnelFlow Server is ready!")
    
    yield
    
    # Shutdown
    print("👋 Shutting down TunnelFlow Server...")


def create_app() -> FastAPI:
    """Создать и настроить FastAPI приложение"""
    
    app = FastAPI(
        title="TunnelFlow API",
        description="Professional tunneling platform with billing and monitoring",
        version="2.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        lifespan=lifespan,
    )
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # В продакшене указать конкретные домены
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Подключение роутов
    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(billing.router, prefix="/api/v1")
    app.include_router(stats.router, prefix="/api/v1")
    app.include_router(tunnels.router, prefix="/api/v1")
    
    # Health check endpoint
    @app.get("/health")
    def health_check():
        return {"status": "healthy", "service": "tunnelflow-api"}
    
    # Root endpoint
    @app.get("/")
    def root():
        return {
            "service": "TunnelFlow",
            "version": "2.0.0",
            "docs": "/api/docs",
            "health": "/health",
        }
    
    return app


# Создаем экземпляр приложения
app = create_app()


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "tunnelflow.main:app",
        host="0.0.0.0",
        port=8000,
        reload=DEBUG,
        workers=1,
    )
