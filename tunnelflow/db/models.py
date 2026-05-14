"""
TunnelFlow Database Models
PostgreSQL schema for users, subscriptions, invoices, tunnels, domains, and usage logs
"""

from datetime import datetime
from enum import Enum
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Enum as SQLEnum, Text, BigInteger
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class PlanType(str, Enum):
    FREE = "free"
    STARTER = "starter"
    PRO = "pro"
    BUSINESS = "business"
    ENTERPRISE = "enterprise"


class InvoiceStatus(str, Enum):
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SubscriptionStatus(str, Enum):
    ACTIVE = "active"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Profile
    current_plan = Column(SQLEnum(PlanType), default=PlanType.FREE, nullable=False)
    plan_expires_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    is_blocked = Column(Boolean, default=False, nullable=False)
    blocked_reason = Column(Text, nullable=True)
    
    # Relations
    tunnels = relationship("Tunnel", back_populates="user", cascade="all, delete-orphan")
    domains = relationship("Domain", back_populates="user", cascade="all, delete-orphan")
    subscriptions = relationship("Subscription", back_populates="user", cascade="all, delete-orphan")
    invoices = relationship("Invoice", back_populates="user", cascade="all, delete-orphan")
    usage_logs = relationship("UsageLog", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}', plan='{self.current_plan.value}')>"


class Subscription(Base):
    __tablename__ = "subscriptions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    plan_id = Column(Integer, ForeignKey("plans.id"), nullable=False)
    start_date = Column(DateTime(timezone=True), nullable=False)
    end_date = Column(DateTime(timezone=True), nullable=True)
    status = Column(SQLEnum(SubscriptionStatus), default=SubscriptionStatus.ACTIVE, nullable=False)
    auto_renew = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relations
    user = relationship("User", back_populates="subscriptions")
    plan = relationship("Plan", back_populates="subscriptions")
    
    def __repr__(self):
        return f"<Subscription(id={self.id}, user_id={self.user_id}, status='{self.status.value}')>"


class Plan(Base):
    __tablename__ = "plans"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), unique=True, nullable=False)  # free, starter, pro, business, enterprise
    price_usd = Column(Float, nullable=False, default=0.0)
    
    # Limits
    max_tunnels = Column(Integer, nullable=False, default=1)
    max_traffic_gb = Column(Integer, nullable=False, default=1)
    max_custom_domains = Column(Integer, nullable=False, default=0)
    max_subdomains = Column(Integer, nullable=False, default=1)
    priority_level = Column(Integer, nullable=False, default=1)  # 1=low, 5=vip
    
    # Features
    ssl_enabled = Column(Boolean, default=True, nullable=False)
    stats_retention_days = Column(Integer, default=7, nullable=False)
    
    # Relations
    subscriptions = relationship("Subscription", back_populates="plans")
    
    def __repr__(self):
        return f"<Plan(name='{self.name}', price=${self.price_usd})>"


class Invoice(Base):
    __tablename__ = "invoices"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String(3), default="USD", nullable=False)
    status = Column(SQLEnum(InvoiceStatus), default=InvoiceStatus.PENDING, nullable=False)
    pdf_url = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    due_date = Column(DateTime(timezone=True), nullable=False)
    paid_at = Column(DateTime(timezone=True), nullable=True)
    description = Column(Text, nullable=True)
    
    # Relations
    user = relationship("User", back_populates="invoices")
    
    def __repr__(self):
        return f"<Invoice(id={self.id}, user_id={self.user_id}, amount=${self.amount}, status='{self.status.value}')>"


class Tunnel(Base):
    __tablename__ = "tunnels"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(100), nullable=False)
    token_hash = Column(String(255), unique=True, nullable=False, index=True)
    
    # Configuration
    local_port = Column(Integer, nullable=False)
    subdomain = Column(String(100), nullable=True)  # e.g., "abc123" for abc123.yourservice.com
    custom_domain = Column(String(255), nullable=True)  # e.g., "app.example.com"
    ssl_enabled = Column(Boolean, default=True, nullable=False)
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    last_connected_at = Column(DateTime(timezone=True), nullable=True)
    last_disconnect_at = Column(DateTime(timezone=True), nullable=True)
    connection_count = Column(BigInteger, default=0, nullable=False)
    
    # Stats (cached from usage_logs)
    total_bytes_in = Column(BigInteger, default=0, nullable=False)
    total_bytes_out = Column(BigInteger, default=0, nullable=False)
    total_requests = Column(BigInteger, default=0, nullable=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relations
    user = relationship("User", back_populates="tunnels")
    domains = relationship("Domain", back_populates="tunnel", cascade="all, delete-orphan")
    usage_logs = relationship("UsageLog", back_populates="tunnel", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Tunnel(id={self.id}, name='{self.name}', user_id={self.user_id})>"


class Domain(Base):
    __tablename__ = "domains"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    tunnel_id = Column(Integer, ForeignKey("tunnels.id"), nullable=True)
    domain_name = Column(String(255), unique=True, nullable=False, index=True)
    domain_type = Column(String(20), nullable=False)  # "custom" or "subdomain"
    
    # SSL
    ssl_enabled = Column(Boolean, default=True, nullable=False)
    ssl_status = Column(String(50), default="pending", nullable=False)  # pending, active, failed, expired
    ssl_expires_at = Column(DateTime(timezone=True), nullable=True)
    
    # Verification
    verified = Column(Boolean, default=False, nullable=False)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    verification_token = Column(String(100), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relations
    user = relationship("User", back_populates="domains")
    tunnel = relationship("Tunnel", back_populates="domains")
    
    def __repr__(self):
        return f"<Domain(id={self.id}, name='{self.domain_name}', type='{self.domain_type}')>"


class UsageLog(Base):
    __tablename__ = "usage_logs"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    tunnel_id = Column(Integer, ForeignKey("tunnels.id"), nullable=False, index=True)
    
    # Traffic
    bytes_in = Column(BigInteger, default=0, nullable=False)
    bytes_out = Column(BigInteger, default=0, nullable=False)
    requests_count = Column(BigInteger, default=0, nullable=False)
    
    # Time window
    started_at = Column(DateTime(timezone=True), nullable=False, index=True)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    
    # Metadata
    client_ip = Column(String(45), nullable=True)  # IPv6 compatible
    user_agent = Column(String(500), nullable=True)
    country = Column(String(2), nullable=True)  # ISO country code
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relations
    user = relationship("User", back_populates="usage_logs")
    tunnel = relationship("Tunnel", back_populates="usage_logs")
    
    def __repr__(self):
        return f"<UsageLog(id={self.id}, tunnel_id={self.tunnel_id}, bytes_in={self.bytes_in})>"


class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String(100), nullable=False)  # e.g., "tunnel_created", "plan_changed"
    resource_type = Column(String(50), nullable=True)  # e.g., "tunnel", "user", "invoice"
    resource_id = Column(Integer, nullable=True)
    details = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    
    def __repr__(self):
        return f"<AuditLog(id={self.id}, action='{self.action}', user_id={self.user_id})>"
