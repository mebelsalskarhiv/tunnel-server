"""
TunnelFlow Monitoring System
Real-time metrics, statistics, and alerting
"""

import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
import redis
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, desc

from ..db.models import User, Tunnel, UsageLog, Domain, Plan, Subscription


@dataclass
class ServerMetrics:
    """Метрики сервера в реальном времени"""
    timestamp: float
    active_connections: int
    requests_per_second: float
    bytes_in_per_second: float
    bytes_out_per_second: float
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    tunnels_online: int = 0
    users_online: int = 0


class MetricsCollector:
    """Сборщик метрик в реальном времени через Redis"""
    
    def __init__(self, redis_host: str = "localhost", redis_port: int = 6379):
        self.redis = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)
        self.metrics_key = "tunnelflow:metrics:current"
        self.history_key = "tunnelflow:metrics:history"
        self.tunnel_stats_key = "tunnelflow:tunnel:{}:stats"
        self.user_stats_key = "tunnelflow:user:{}:stats"
    
    def update_server_metrics(self, metrics: ServerMetrics):
        """Обновить текущие метрики сервера"""
        data = asdict(metrics)
        data["timestamp"] = time.time()
        
        # Сохраняем текущие метрики
        self.redis.set(self.metrics_key, json.dumps(data))
        
        # Добавляем в историю (список последних 1000 записей)
        self.redis.lpush(self.history_key, json.dumps(data))
        self.redis.ltrim(self.history_key, 0, 999)
    
    def get_current_metrics(self) -> Optional[ServerMetrics]:
        """Получить текущие метрики сервера"""
        data = self.redis.get(self.metrics_key)
        if not data:
            return None
        return ServerMetrics(**json.loads(data))
    
    def get_metrics_history(self, minutes: int = 60) -> List[Dict]:
        """Получить историю метрик за последние N минут"""
        # Примерно 1 запись в секунду = 60 * N записей
        max_entries = minutes * 60
        entries = self.redis.lrange(self.history_key, 0, max_entries)
        return [json.loads(e) for e in entries]
    
    def update_tunnel_stats(self, tunnel_id: int, bytes_in: int, bytes_out: int, requests: int):
        """Обновить статистику туннеля в реальном времени"""
        key = self.tunnel_stats_key.format(tunnel_id)
        data = {
            "bytes_in": bytes_in,
            "bytes_out": bytes_out,
            "requests": requests,
            "timestamp": time.time(),
        }
        self.redis.set(key, json.dumps(data), ex=300)  # TTL 5 минут
    
    def get_tunnel_stats(self, tunnel_id: int) -> Optional[Dict]:
        """Получить статистику туннеля"""
        data = self.redis.get(self.tunnel_stats_key.format(tunnel_id))
        if not data:
            return None
        return json.loads(data)
    
    def update_user_stats(self, user_id: int, active_tunnels: int, current_rps: float):
        """Обновить статистику пользователя"""
        key = self.user_stats_key.format(user_id)
        data = {
            "active_tunnels": active_tunnels,
            "current_rps": current_rps,
            "timestamp": time.time(),
        }
        self.redis.set(key, json.dumps(data), ex=300)
    
    def get_user_stats(self, user_id: int) -> Optional[Dict]:
        """Получить статистику пользователя"""
        data = self.redis.get(self.user_stats_key.format(user_id))
        if not data:
            return None
        return json.loads(data)
    
    def increment_connection(self):
        """Увеличить счетчик активных подключений"""
        self.redis.hincrby("tunnelflow:connections", "active", 1)
    
    def decrement_connection(self):
        """Уменьшить счетчик активных подключений"""
        self.redis.hincrby("tunnelflow:connections", "active", -1)
    
    def get_active_connections(self) -> int:
        """Получить количество активных подключений"""
        return int(self.redis.hget("tunnelflow:connections", "active") or 0)


class StatsService:
    """Сервис для работы со статистикой из БД"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_global_stats(self) -> Dict:
        """Получить глобальную статистику платформы"""
        total_users = self.db.query(User).count()
        total_tunnels = self.db.query(Tunnel).count()
        active_tunnels = self.db.query(Tunnel).filter(Tunnel.is_active == True).count()
        total_domains = self.db.query(Domain).count()
        verified_domains = self.db.query(Domain).filter(Domain.verified == True).count()
        
        # Трафик за последние 24 часа
        cutoff = datetime.utcnow() - timedelta(hours=24)
        traffic_24h = self.db.query(
            func.sum(UsageLog.bytes_in + UsageLog.bytes_out).label("total")
        ).filter(
            UsageLog.started_at >= cutoff
        ).scalar() or 0
        
        # Пользователи по тарифам
        users_by_plan = self.db.query(
            User.current_plan, func.count(User.id)
        ).group_by(User.current_plan).all()
        
        return {
            "total_users": total_users,
            "total_tunnels": total_tunnels,
            "active_tunnels": active_tunnels,
            "total_domains": total_domains,
            "verified_domains": verified_domains,
            "traffic_24h_bytes": traffic_24h,
            "traffic_24h_gb": traffic_24h / (1024 ** 3),
            "users_by_plan": {plan.value: count for plan, count in users_by_plan},
        }
    
    def get_user_detailed_stats(self, user_id: int, days: int = 30) -> Dict:
        """Получить детальную статистику пользователя"""
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        # Общая информация о пользователе
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return None
        
        # Туннели
        tunnels = self.db.query(Tunnel).filter(Tunnel.user_id == user_id).all()
        tunnel_stats = []
        for tunnel in tunnels:
            stats = self._get_tunnel_period_stats(tunnel.id, cutoff)
            tunnel_stats.append({
                "id": tunnel.id,
                "name": tunnel.name,
                "subdomain": tunnel.subdomain,
                "custom_domain": tunnel.custom_domain,
                "is_active": tunnel.is_active,
                "last_connected": tunnel.last_connected_at,
                **stats,
            })
        
        # Трафик по дням
        daily_traffic = self.db.query(
            func.date(UsageLog.started_at).label("date"),
            func.sum(UsageLog.bytes_in + UsageLog.bytes_out).label("bytes")
        ).filter(
            and_(
                UsageLog.user_id == user_id,
                UsageLog.started_at >= cutoff
            )
        ).group_by(func.date(UsageLog.started_at)).all()
        
        traffic_by_day = {str(row.date): row.bytes / (1024 ** 3) for row in daily_traffic}
        
        # Запросы по дням
        daily_requests = self.db.query(
            func.date(UsageLog.started_at).label("date"),
            func.sum(UsageLog.requests_count).label("requests")
        ).filter(
            and_(
                UsageLog.user_id == user_id,
                UsageLog.started_at >= cutoff
            )
        ).group_by(func.date(UsageLog.started_at)).all()
        
        requests_by_day = {str(row.date): row.requests for row in daily_requests}
        
        # Топ IP адресов
        top_ips = self.db.query(
            UsageLog.client_ip,
            func.sum(UsageLog.requests_count).label("requests"),
            func.sum(UsageLog.bytes_in + UsageLog.bytes_out).label("bytes")
        ).filter(
            and_(
                UsageLog.user_id == user_id,
                UsageLog.client_ip != None,
                UsageLog.started_at >= cutoff
            )
        ).group_by(UsageLog.client_ip).order_by(desc("requests")).limit(10).all()
        
        return {
            "user_id": user_id,
            "email": user.email,
            "plan": user.current_plan.value,
            "tunnels": tunnel_stats,
            "traffic_by_day_gb": traffic_by_day,
            "requests_by_day": requests_by_day,
            "top_ips": [{"ip": ip, "requests": req, "bytes": b} for ip, req, b in top_ips],
            "period_days": days,
        }
    
    def _get_tunnel_period_stats(self, tunnel_id: int, cutoff: datetime) -> Dict:
        """Получить статистику туннеля за период"""
        stats = self.db.query(
            func.sum(UsageLog.bytes_in).label("bytes_in"),
            func.sum(UsageLog.bytes_out).label("bytes_out"),
            func.sum(UsageLog.requests_count).label("requests"),
            func.count(UsageLog.id).label("sessions")
        ).filter(
            and_(
                UsageLog.tunnel_id == tunnel_id,
                UsageLog.started_at >= cutoff
            )
        ).first()
        
        return {
            "bytes_in": stats.bytes_in or 0,
            "bytes_out": stats.bytes_out or 0,
            "requests": stats.requests or 0,
            "sessions": stats.sessions or 0,
        }
    
    def get_top_users_by_traffic(self, limit: int = 10, days: int = 7) -> List[Dict]:
        """Получить топ пользователей по трафику"""
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        results = self.db.query(
            User.id,
            User.email,
            User.current_plan,
            func.sum(UsageLog.bytes_in + UsageLog.bytes_out).label("total_bytes"),
            func.sum(UsageLog.requests_count).label("total_requests")
        ).join(UsageLog, User.id == UsageLog.user_id).filter(
            UsageLog.started_at >= cutoff
        ).group_by(User.id).order_by(desc("total_bytes")).limit(limit).all()
        
        return [
            {
                "user_id": r.id,
                "email": r.email,
                "plan": r.current_plan.value,
                "traffic_gb": r.total_bytes / (1024 ** 3),
                "requests": r.total_requests,
            }
            for r in results
        ]


class AlertService:
    """Сервис алертов и уведомлений"""
    
    def __init__(self, redis_client: redis.Redis = None):
        self.redis = redis_client or redis.Redis(decode_responses=True)
        self.alerts_key = "tunnelflow:alerts"
    
    def create_alert(self, alert_type: str, message: str, severity: str = "warning",
                     resource_id: int = None):
        """Создать алерт"""
        alert = {
            "id": int(time.time() * 1000),
            "type": alert_type,
            "message": message,
            "severity": severity,  # info, warning, error, critical
            "resource_id": resource_id,
            "created_at": datetime.utcnow().isoformat(),
            "acknowledged": False,
        }
        
        self.redis.lpush(self.alerts_key, json.dumps(alert))
        # Храним последние 1000 алертов
        self.redis.ltrim(self.alerts_key, 0, 999)
        
        return alert
    
    def get_alerts(self, limit: int = 50, unacknowledged_only: bool = False) -> List[Dict]:
        """Получить список алертов"""
        alerts = self.redis.lrange(self.alerts_key, 0, limit)
        result = [json.loads(a) for a in alerts]
        
        if unacknowledged_only:
            result = [a for a in result if not a.get("acknowledged")]
        
        return result
    
    def acknowledge_alert(self, alert_id: int):
        """Подтвердить алерт"""
        alerts = self.redis.lrange(self.alerts_key, 0, -1)
        for i, alert_data in enumerate(alerts):
            alert = json.loads(alert_data)
            if alert["id"] == alert_id:
                alert["acknowledged"] = True
                alert["acknowledged_at"] = datetime.utcnow().isoformat()
                self.redis.lset(self.alerts_key, i, json.dumps(alert))
                break
    
    def check_server_health(self, metrics: ServerMetrics) -> List[Dict]:
        """Проверить метрики на наличие проблем"""
        alerts = []
        
        if metrics.cpu_percent > 80:
            alerts.append(self.create_alert(
                "high_cpu",
                f"High CPU usage: {metrics.cpu_percent:.1f}%",
                "critical" if metrics.cpu_percent > 95 else "warning"
            ))
        
        if metrics.memory_percent > 80:
            alerts.append(self.create_alert(
                "high_memory",
                f"High memory usage: {metrics.memory_percent:.1f}%",
                "critical" if metrics.memory_percent > 95 else "warning"
            ))
        
        if metrics.active_connections > 1000:
            alerts.append(self.create_alert(
                "high_connections",
                f"High number of connections: {metrics.active_connections}",
                "warning"
            ))
        
        return alerts
