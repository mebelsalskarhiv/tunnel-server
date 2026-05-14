"""
TunnelFlow Billing API Routes
Plans, invoices, subscriptions management
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime

from ..db.database import get_db
from ..db.models import User, Invoice, Subscription, Plan
from ..db.models import InvoiceStatus, SubscriptionStatus
from ..billing.plans import (
    initialize_plans,
    get_user_plan,
    get_user_limits,
    get_current_usage,
    generate_invoice,
    generate_monthly_invoices,
)
from ..api.routes.auth import get_current_user

router = APIRouter(prefix="/billing", tags=["Billing"])


@router.get("/plans")
def get_available_plans(db: Session = Depends(get_db)):
    """Получить список доступных тарифных планов"""
    # Инициализируем планы если нужно
    initialize_plans(db)
    
    plans = db.query(Plan).order_by(Plan.price_usd).all()
    return [
        {
            "id": plan.id,
            "name": plan.name,
            "price_usd": plan.price_usd,
            "max_tunnels": plan.max_tunnels if plan.max_tunnels > 0 else "unlimited",
            "max_traffic_gb": plan.max_traffic_gb if plan.max_traffic_gb > 0 else "unlimited",
            "max_custom_domains": plan.max_custom_domains,
            "max_subdomains": plan.max_subdomains,
            "priority_level": plan.priority_level,
            "ssl_enabled": plan.ssl_enabled,
            "stats_retention_days": plan.stats_retention_days,
        }
        for plan in plans
    ]


@router.get("/my-plan")
def get_my_plan(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получить информацию о текущем плане пользователя"""
    plan = get_user_plan(db, current_user.id)
    limits = get_user_limits(db, current_user.id)
    usage = get_current_usage(db, current_user.id)
    
    # Активная подписка
    active_subscription = db.query(Subscription).filter(
        Subscription.user_id == current_user.id,
        Subscription.status == SubscriptionStatus.ACTIVE
    ).order_by(Subscription.created_at.desc()).first()
    
    return {
        "plan": {
            "name": plan.name if plan else "unknown",
            "price_usd": plan.price_usd if plan else 0,
        } if plan else None,
        "limits": limits,
        "usage": usage,
        "subscription": {
            "id": active_subscription.id,
            "start_date": active_subscription.start_date,
            "end_date": active_subscription.end_date,
            "auto_renew": active_subscription.auto_renew,
        } if active_subscription else None,
        "plan_expires_at": current_user.plan_expires_at,
    }


@router.get("/invoices")
def get_my_invoices(
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получить историю счетов пользователя"""
    invoices = db.query(Invoice).filter(
        Invoice.user_id == current_user.id
    ).order_by(Invoice.created_at.desc()).limit(limit).all()
    
    return [
        {
            "id": invoice.id,
            "amount": invoice.amount,
            "currency": invoice.currency,
            "status": invoice.status.value,
            "created_at": invoice.created_at,
            "due_date": invoice.due_date,
            "paid_at": invoice.paid_at,
            "description": invoice.description,
            "pdf_url": invoice.pdf_url,
        }
        for invoice in invoices
    ]


@router.get("/invoices/{invoice_id}")
def get_invoice(
    invoice_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получить детали конкретного счета"""
    invoice = db.query(Invoice).filter(
        Invoice.id == invoice_id,
        Invoice.user_id == current_user.id
    ).first()
    
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found",
        )
    
    return {
        "id": invoice.id,
        "amount": invoice.amount,
        "currency": invoice.currency,
        "status": invoice.status.value,
        "created_at": invoice.created_at,
        "due_date": invoice.due_date,
        "paid_at": invoice.paid_at,
        "description": invoice.description,
        "pdf_url": invoice.pdf_url,
    }


@router.post("/invoices/{invoice_id}/pay")
def pay_invoice(
    invoice_id: int,
    payment_method: str = "card",  # card, crypto, paypal
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Оплатить счет (имитация платежного процесса)
    В продакшене здесь будет интеграция со Stripe/PayPal
    """
    invoice = db.query(Invoice).filter(
        Invoice.id == invoice_id,
        Invoice.user_id == current_user.id
    ).first()
    
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found",
        )
    
    if invoice.status != InvoiceStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invoice is already {invoice.status.value}",
        )
    
    # Имитация успешной оплаты
    # В реальности здесь будет вызов платежного шлюза
    invoice.status = InvoiceStatus.PAID
    invoice.paid_at = datetime.utcnow()
    db.commit()
    
    # Если это счет за подписку - активируем подписку
    if "subscription" in (invoice.description or "").lower():
        # Логика активации подписки
        pass
    
    return {
        "message": "Payment successful",
        "invoice_id": invoice_id,
        "status": "paid",
        "paid_at": invoice.paid_at,
    }


@router.post("/subscribe/{plan_id}")
def subscribe_to_plan(
    plan_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Подписаться на тарифный план"""
    plan = db.query(Plan).filter(Plan.id == plan_id).first()
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found",
        )
    
    # Отменяем предыдущие активные подписки
    db.query(Subscription).filter(
        Subscription.user_id == current_user.id,
        Subscription.status == SubscriptionStatus.ACTIVE
    ).update({"status": SubscriptionStatus.CANCELLED})
    
    # Создаем новую подписку
    from datetime import timedelta
    subscription = Subscription(
        user_id=current_user.id,
        plan_id=plan_id,
        start_date=datetime.utcnow(),
        end_date=datetime.utcnow() + timedelta(days=30),
        status=SubscriptionStatus.ACTIVE,
        auto_renew=True,
    )
    
    db.add(subscription)
    
    # Обновляем план пользователя
    current_user.current_plan = PlanType(plan.name)
    current_user.plan_expires_at = subscription.end_date
    
    db.commit()
    
    # Генерируем счет
    if plan.price_usd > 0:
        generate_invoice(
            db=db,
            user_id=current_user.id,
            amount=plan.price_usd,
            description=f"Subscription: {plan.name} plan",
            due_days=7,
        )
    
    return {
        "message": f"Successfully subscribed to {plan.name} plan",
        "subscription": {
            "id": subscription.id,
            "plan": plan.name,
            "start_date": subscription.start_date,
            "end_date": subscription.end_date,
            "auto_renew": subscription.auto_renew,
        },
    }


# Import PlanType here to avoid circular imports
from ..db.models import PlanType
