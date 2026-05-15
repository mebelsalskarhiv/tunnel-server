"""
TunnelFlow Statistics and Monitoring API Routes
Real-time stats for users and admins
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
import redis

from tunnelflow.db.database import get_db
from tunnelflow.db.models import User
from tunnelflow.monitoring.metrics import MetricsCollector, StatsService, ServerMetrics
from tunnelflow.api.routes.auth import get_current_user

router = APIRouter(prefix="/stats", tags=["Statistics"])


@router.get("/global")
def get_global_stats(db: Session = Depends(get_db)):
    """Получить глобальную статистику платформы (только для админов)"""
    stats_service = StatsService(db)
    return stats_service.get_global_stats()


@router.get("/user/me")
def get_my_stats(
    days: int = 30,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получить детальную статистику текущего пользователя"""
    stats_service = StatsService(db)
    user_stats = stats_service.get_user_detailed_stats(current_user.id, days)
    
    if not user_stats:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User stats not found",
        )
    
    return user_stats


@router.get("/user/me/realtime")
def get_my_realtime_stats(
    current_user: User = Depends(get_current_user),
    redis_host: str = "localhost",
    redis_port: int = 6379
):
    """Получить реальную статистику пользователя в реальном времени"""
    try:
        metrics = MetricsCollector(redis_host, redis_port)
        user_stats = metrics.get_user_stats(current_user.id)
        
        if not user_stats:
            return {
                "active_tunnels": 0,
                "current_rps": 0.0,
                "timestamp": 0,
            }
        
        return user_stats
    except redis.ConnectionError:
        # Redis недоступен, возвращаем пустые данные
        return {
            "active_tunnels": 0,
            "current_rps": 0.0,
            "timestamp": 0,
            "warning": "Real-time metrics unavailable",
        }


@router.get("/tunnel/{tunnel_id}/stats")
def get_tunnel_stats(
    tunnel_id: int,
    hours: int = 24,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получить статистику конкретного туннеля"""
    # Проверяем, принадлежит ли туннель пользователю
    from ..db.models import Tunnel
    tunnel = db.query(Tunnel).filter(
        Tunnel.id == tunnel_id,
        Tunnel.user_id == current_user.id
    ).first()
    
    if not tunnel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tunnel not found or access denied",
        )
    
    stats_service = StatsService(db)
    return stats_service._get_tunnel_period_stats(
        tunnel_id,
        cutoff=None  # Будет вычислено внутри
    )


@router.get("/server/realtime")
def get_server_realtime_metrics(
    redis_host: str = "localhost",
    redis_port: int = 6379
):
    """Получить метрики сервера в реальном времени"""
    try:
        metrics = MetricsCollector(redis_host, redis_port)
        current = metrics.get_current_metrics()
        
        if not current:
            return {
                "active_connections": 0,
                "requests_per_second": 0.0,
                "bytes_in_per_second": 0.0,
                "bytes_out_per_second": 0.0,
                "cpu_percent": 0.0,
                "memory_percent": 0.0,
                "tunnels_online": 0,
                "users_online": 0,
            }
        
        return current
    except redis.ConnectionError:
        return {
            "warning": "Real-time metrics unavailable",
        }


@router.get("/server/history")
def get_server_metrics_history(
    minutes: int = 60,
    redis_host: str = "localhost",
    redis_port: int = 6379
):
    """Получить историю метрик сервера"""
    try:
        metrics = MetricsCollector(redis_host, redis_port)
        history = metrics.get_metrics_history(minutes)
        return {"history": history, "count": len(history)}
    except redis.ConnectionError:
        return {"history": [], "count": 0, "warning": "Redis unavailable"}


@router.get("/top-users")
def get_top_users_by_traffic(
    limit: int = 10,
    days: int = 7,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Получить топ пользователей по трафику
    Доступно только пользователям с планом Business или выше
    """
    # Проверка прав доступа
    allowed_plans = ["business", "enterprise"]
    if current_user.current_plan.value not in allowed_plans:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This feature is available only for Business plan and above",
        )
    
    stats_service = StatsService(db)
    return stats_service.get_top_users_by_traffic(limit, days)
