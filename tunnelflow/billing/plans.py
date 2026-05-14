"""
TunnelFlow Billing System
Plans, invoices, and payment processing
"""

import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from sqlalchemy.orm import Session
from sqlalchemy import and_

from ..db.models import (
    User, Plan, Subscription, Invoice, Tunnel, Domain, UsageLog,
    PlanType, InvoiceStatus, SubscriptionStatus
)


# Тарифные планы по умолчанию
DEFAULT_PLANS = [
    {
        "name": PlanType.FREE.value,
        "price_usd": 0.0,
        "max_tunnels": 1,
        "max_traffic_gb": 1,
        "max_custom_domains": 0,
        "max_subdomains": 1,
        "priority_level": 1,
        "ssl_enabled": True,
        "stats_retention_days": 3,
    },
    {
        "name": PlanType.STARTER.value,
        "price_usd": 5.0,
        "max_tunnels": 3,
        "max_traffic_gb": 20,
        "max_custom_domains": 1,
        "max_subdomains": 3,
        "priority_level": 2,
        "ssl_enabled": True,
        "stats_retention_days": 7,
    },
    {
        "name": PlanType.PRO.value,
        "price_usd": 15.0,
        "max_tunnels": 10,
        "max_traffic_gb": 100,
        "max_custom_domains": 5,
        "max_subdomains": 10,
        "priority_level": 3,
        "ssl_enabled": True,
        "stats_retention_days": 30,
    },
    {
        "name": PlanType.BUSINESS.value,
        "price_usd": 50.0,
        "max_tunnels": 50,
        "max_traffic_gb": 500,
        "max_custom_domains": 20,
        "max_subdomains": 50,
        "priority_level": 4,
        "ssl_enabled": True,
        "stats_retention_days": 90,
    },
    {
        "name": PlanType.ENTERPRISE.value,
        "price_usd": 0.0,  # Custom pricing
        "max_tunnels": -1,  # Unlimited
        "max_traffic_gb": -1,
        "max_custom_domains": -1,
        "max_subdomains": -1,
        "priority_level": 5,
        "ssl_enabled": True,
        "stats_retention_days": 365,
    },
]


def initialize_plans(db: Session):
    """Инициализация тарифных планов в БД"""
    for plan_data in DEFAULT_PLANS:
        existing = db.query(Plan).filter(Plan.name == plan_data["name"]).first()
        if not existing:
            plan = Plan(**plan_data)
            db.add(plan)
    
    db.commit()
    return db.query(Plan).all()


def get_user_plan(db: Session, user_id: int) -> Optional[Plan]:
    """Получить текущий план пользователя"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return None
    
    subscription = db.query(Subscription).filter(
        and_(
            Subscription.user_id == user_id,
            Subscription.status == SubscriptionStatus.ACTIVE
        )
    ).order_by(Subscription.created_at.desc()).first()
    
    if subscription:
        return subscription.plan
    
    # Fallback to user's current_plan enum
    return db.query(Plan).filter(Plan.name == user.current_plan.value).first()


def get_user_limits(db: Session, user_id: int) -> Dict:
    """Получить лимиты пользователя"""
    plan = get_user_plan(db, user_id)
    if not plan:
        return {
            "max_tunnels": 1,
            "max_traffic_gb": 1,
            "max_custom_domains": 0,
            "max_subdomains": 1,
        }
    
    return {
        "max_tunnels": plan.max_tunnels,
        "max_traffic_gb": plan.max_traffic_gb,
        "max_custom_domains": plan.max_custom_domains,
        "max_subdomains": plan.max_subdomains,
        "priority_level": plan.priority_level,
    }


def get_current_usage(db: Session, user_id: int, period_days: int = 30) -> Dict:
    """Получить текущее использование ресурсов пользователем"""
    cutoff_date = datetime.utcnow() - timedelta(days=period_days)
    
    # Трафик
    usage = db.query(
        UsageLog.bytes_in.label("bytes_in"),
        UsageLog.bytes_out.label("bytes_out"),
        UsageLog.requests_count.label("requests")
    ).filter(
        and_(
            UsageLog.user_id == user_id,
            UsageLog.started_at >= cutoff_date
        )
    ).all()
    
    total_bytes_in = sum(u.bytes_in for u in usage) if usage else 0
    total_bytes_out = sum(u.bytes_out for u in usage) if usage else 0
    total_requests = sum(u.requests_count for u in usage) if usage else 0
    
    # Активные туннели
    active_tunnels = db.query(Tunnel).filter(
        and_(
            Tunnel.user_id == user_id,
            Tunnel.is_active == True
        )
    ).count()
    
    # Домены
    custom_domains = db.query(Domain).filter(
        and_(
            Domain.user_id == user_id,
            Domain.domain_type == "custom",
            Domain.verified == True
        )
    ).count()
    
    subdomains = db.query(Domain).filter(
        and_(
            Domain.user_id == user_id,
            Domain.domain_type == "subdomain",
            Domain.verified == True
        )
    ).count()
    
    return {
        "traffic_gb": (total_bytes_in + total_bytes_out) / (1024 ** 3),
        "total_requests": total_requests,
        "active_tunnels": active_tunnels,
        "custom_domains": custom_domains,
        "subdomains": subdomains,
    }


def check_can_create_tunnel(db: Session, user_id: int) -> tuple[bool, str]:
    """Проверить, может ли пользователь создать новый туннель"""
    limits = get_user_limits(db, user_id)
    usage = get_current_usage(db, user_id)
    
    if limits["max_tunnels"] > 0 and usage["active_tunnels"] >= limits["max_tunnels"]:
        return False, f"Превышен лимит туннелей ({limits['max_tunnels']})"
    
    return True, "OK"


def check_can_add_domain(db: Session, user_id: int, is_custom: bool) -> tuple[bool, str]:
    """Проверить, может ли пользователь добавить домен"""
    limits = get_user_limits(db, user_id)
    usage = get_current_usage(db, user_id)
    
    if is_custom:
        if limits["max_custom_domains"] > 0 and usage["custom_domains"] >= limits["max_custom_domains"]:
            return False, f"Превышен лимит пользовательских доменов ({limits['max_custom_domains']})"
        if limits["max_custom_domains"] == 0:
            return False, "Пользовательские домены недоступны на вашем тарифе"
    else:
        if limits["max_subdomains"] > 0 and usage["subdomains"] >= limits["max_subdomains"]:
            return False, f"Превышен лимит поддоменов ({limits['max_subdomains']})"
    
    return True, "OK"


def generate_invoice(db: Session, user_id: int, amount: float, 
                     description: str = None, due_days: int = 7) -> Invoice:
    """Создать счет на оплату"""
    invoice = Invoice(
        user_id=user_id,
        amount=amount,
        currency="USD",
        status=InvoiceStatus.PENDING,
        due_date=datetime.utcnow() + timedelta(days=due_days),
        description=description or f"Monthly subscription charge",
    )
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    return invoice


def generate_monthly_invoices(db: Session):
    """Генерация ежемесячных счетов для всех активных подписок"""
    subscriptions = db.query(Subscription).filter(
        Subscription.status == SubscriptionStatus.ACTIVE
    ).all()
    
    for sub in subscriptions:
        plan = sub.plan
        if plan.price_usd <= 0:
            continue  # Free или custom
        
        # Проверяем, не был ли уже создан счет за этот месяц
        existing = db.query(Invoice).filter(
            and_(
                Invoice.user_id == sub.user_id,
                Invoice.status == InvoiceStatus.PENDING,
                Invoice.created_at >= datetime.utcnow().replace(day=1)
            )
        ).first()
        
        if not existing:
            generate_invoice(
                db=db,
                user_id=sub.user_id,
                amount=plan.price_usd,
                description=f"Monthly subscription: {plan.name.capitalize()} plan",
                due_days=7
            )


def hash_token(token: str, salt: str = None) -> tuple[str, str]:
    """Хэширование токена с солью"""
    if salt is None:
        salt = secrets.token_hex(16)
    
    salted = f"{salt}:{token}"
    token_hash = hashlib.sha256(salted.encode()).hexdigest()
    return token_hash, salt


def verify_token(token: str, token_hash: str, salt: str) -> bool:
    """Проверка токена"""
    computed_hash, _ = hash_token(token, salt)
    return computed_hash == token_hash


def create_user_tunnel(db: Session, user_id: int, name: str, 
                       local_port: int, subdomain: str = None) -> Tunnel:
    """Создать новый туннель для пользователя"""
    can_create, message = check_can_create_tunnel(db, user_id)
    if not can_create:
        raise ValueError(message)
    
    # Генерируем токен
    raw_token = secrets.token_urlsafe(32)
    token_hash, salt = hash_token(raw_token)
    
    tunnel = Tunnel(
        user_id=user_id,
        name=name,
        token_hash=token_hash,
        local_port=local_port,
        subdomain=subdomain,
        ssl_enabled=True,
        is_active=True,
    )
    
    db.add(tunnel)
    db.commit()
    db.refresh(tunnel)
    
    # Возвращаем туннель с raw_token (только один раз!)
    tunnel.raw_token = raw_token
    return tunnel


def get_tunnel_stats(db: Session, tunnel_id: int, hours: int = 24) -> Dict:
    """Получить статистику туннеля за период"""
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    
    logs = db.query(UsageLog).filter(
        and_(
            UsageLog.tunnel_id == tunnel_id,
            UsageLog.started_at >= cutoff
        )
    ).all()
    
    if not logs:
        return {
            "bytes_in": 0,
            "bytes_out": 0,
            "requests": 0,
            "unique_ips": 0,
        }
    
    bytes_in = sum(log.bytes_in for log in logs)
    bytes_out = sum(log.bytes_out for log in logs)
    requests = sum(log.requests_count for log in logs)
    unique_ips = len(set(log.client_ip for log in logs if log.client_ip))
    
    return {
        "bytes_in": bytes_in,
        "bytes_out": bytes_out,
        "requests": requests,
        "unique_ips": unique_ips,
        "period_hours": hours,
    }
