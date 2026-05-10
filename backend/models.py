"""SQLAlchemy models for the integration database with Multi-Tenancy."""

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    Text,
    Enum,
    Boolean,
    ForeignKey,
    JSON,
    Index,
)
from sqlalchemy.orm import relationship

from database import Base


# ========== Enums ==========

class SyncStatus(str, enum.Enum):
    SYNCED = "synced"
    PENDING = "pending"
    ERROR = "error"


class OrderStatus(str, enum.Enum):
    NEW = "Новый"
    PROCESSING = "В обработке"
    SHIPPED = "Отгружен"
    IN_TRANSIT = "В пути"
    DELIVERED = "Доставлен"
    CANCELLED = "Отменен"


class ClientType(str, enum.Enum):
    WHOLESALE = "Опт"
    RETAIL = "Розница"


class LogType(str, enum.Enum):
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


# ========== Tenant (Multi-Tenancy) ==========

class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    phone = Column(String(50), nullable=True)

    # MoySklad OAuth
    moysklad_access_token = Column(Text, nullable=True)
    moysklad_refresh_token = Column(Text, nullable=True)
    moysklad_token_expires = Column(DateTime, nullable=True)
    moysklad_account_id = Column(String(100), nullable=True)

    # Sales Doctor API (JSON-RPC login/token auth)
    salesdoctor_base_url = Column(String(255), nullable=True)
    salesdoctor_login = Column(String(255), nullable=True)
    salesdoctor_password = Column(Text, nullable=True)    # stored to re-login if token expires
    salesdoctor_user_id = Column(String(100), nullable=True)
    salesdoctor_token = Column(Text, nullable=True)
    salesdoctor_filial_id = Column(Integer, default=0)

    is_active = Column(Boolean, default=True)
    sync_interval_seconds = Column(Integer, default=60)

    # Webhook
    webhook_url = Column(String(500), nullable=True)
    webhook_secret = Column(String(255), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    users = relationship("User", back_populates="tenant")
    orders = relationship("Order", back_populates="tenant")
    clients = relationship("Client", back_populates="tenant")
    stock_items = relationship("StockItem", back_populates="tenant")
    debt_records = relationship("DebtRecord", back_populates="tenant")
    deliveries = relationship("Delivery", back_populates="tenant")
    sync_logs = relationship("SyncLog", back_populates="tenant")


# ========== User ==========

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    email = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    role = Column(String(50), default="agent")  # admin, manager, agent
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="users")

    __table_args__ = (Index("ix_users_tenant_email", "tenant_id", "email", unique=True),)


# ========== Order ==========

class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    order_id = Column(String(50), index=True, nullable=False)
    moysklad_id = Column(String(100), nullable=True)
    salesdoctor_id = Column(String(100), nullable=True)

    client_name = Column(String(255), nullable=False)
    client_phone = Column(String(50), nullable=False)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True)

    agent_name = Column(String(255), nullable=False)
    comment = Column(Text, nullable=True)

    total_amount = Column(Float, default=0)
    status = Column(Enum(OrderStatus), default=OrderStatus.NEW)
    sync_status = Column(Enum(SyncStatus), default=SyncStatus.PENDING)

    items = Column(JSON, default=list)
    raw_data = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    synced_at = Column(DateTime, nullable=True)

    tenant = relationship("Tenant", back_populates="orders")
    client = relationship("Client", back_populates="orders")
    logs = relationship("SyncLog", back_populates="order")

    __table_args__ = (Index("ix_orders_tenant_order_id", "tenant_id", "order_id", unique=True),)


# ========== Client ==========

class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    moysklad_id = Column(String(100), nullable=True)
    salesdoctor_id = Column(String(100), nullable=True)

    name = Column(String(255), nullable=False, index=True)
    phone = Column(String(50), nullable=False, index=True)
    address = Column(Text, nullable=True)
    location = Column(String(255), nullable=True)
    client_type = Column(Enum(ClientType), default=ClientType.RETAIL)

    debt = Column(Float, default=0)
    debt_limit = Column(Float, default=0)
    total_paid = Column(Float, default=0)

    is_active = Column(Boolean, default=True)
    is_duplicate = Column(Boolean, default=False)
    merged_into_id = Column(Integer, ForeignKey("clients.id"), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_order_at = Column(DateTime, nullable=True)

    tenant = relationship("Tenant", back_populates="clients")
    orders = relationship("Order", back_populates="client")

    __table_args__ = (Index("ix_clients_tenant_phone", "tenant_id", "phone"),)


# ========== StockItem ==========

class StockItem(Base):
    __tablename__ = "stock_items"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    moysklad_id = Column(String(100), nullable=True)
    sku = Column(String(100), nullable=False)
    name = Column(String(255), nullable=False)
    qty = Column(Float, default=0)
    price = Column(Float, default=0)
    warehouse = Column(String(255), default="Основной склад")
    warehouse_id = Column(String(100), nullable=True)

    last_sync = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="stock_items")

    __table_args__ = (Index("ix_stock_tenant_sku", "tenant_id", "sku", unique=True),)


# ========== DebtRecord ==========

class DebtRecord(Base):
    __tablename__ = "debt_records"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True)
    client_name = Column(String(255), nullable=False)
    client_phone = Column(String(50), nullable=False)

    total_debt = Column(Float, default=0)
    paid = Column(Float, default=0)
    remaining = Column(Float, default=0)
    last_payment_date = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="debt_records")


# ========== Delivery ==========

class Delivery(Base):
    __tablename__ = "deliveries"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True)
    order_number = Column(String(50), nullable=False)

    client_name = Column(String(255), nullable=False)
    address = Column(Text, nullable=False)
    courier_name = Column(String(255), nullable=False)

    status = Column(String(50), default="В пути")
    dispatched_at = Column(DateTime, default=datetime.utcnow)
    delivered_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="deliveries")


# ========== SyncLog ==========

class SyncLog(Base):
    __tablename__ = "sync_logs"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    log_type = Column(Enum(LogType), default=LogType.INFO)
    module = Column(String(100), nullable=False)
    message = Column(Text, nullable=False)

    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    is_resolved = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="sync_logs")
    order = relationship("Order", back_populates="logs")


# ========== WebhookEvent ==========

class WebhookEvent(Base):
    __tablename__ = "webhook_events"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    source = Column(String(50), nullable=False)
    event_type = Column(String(100), nullable=False)
    payload = Column(JSON, nullable=False)
    processed = Column(Boolean, default=False)
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)

