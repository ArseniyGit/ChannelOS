from datetime import datetime
from decimal import Decimal

from sqlalchemy import (BigInteger, Boolean, DateTime, ForeignKey, Integer, Numeric,
                        String, Text, func)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    username: Mapped[str | None] = mapped_column(String)
    first_name: Mapped[str | None] = mapped_column(String)
    is_subscribed: Mapped[bool] = mapped_column(default=False)
    subscription_end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    total_subscription_days: Mapped[int] = mapped_column(Integer, default=0) 
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    subscriptions: Mapped[list["Subscription"]] = relationship(back_populates="user")
    payments: Mapped[list["Payment"]] = relationship(back_populates="user")
    user_ranks: Mapped[list["UserRank"]] = relationship(back_populates="user")

    def __repr__(self):
        return f"<User(id={self.id}, telegram_id={self.telegram_id}, username={self.username})>"


class Tariff(Base):
    __tablename__ = "tariffs"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String)
    description: Mapped[str | None] = mapped_column(Text)
    price_usd: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    price_stars: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_days: Mapped[int] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    subscriptions: Mapped[list["Subscription"]] = relationship(back_populates="tariff")

    def __repr__(self):
        return f"<Tariff(id={self.id}, name={self.name}, price_usd={self.price_usd}, duration_days={self.duration_days})>"


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    tariff_id: Mapped[int] = mapped_column(ForeignKey("tariffs.id", ondelete="SET NULL"), nullable=True)
    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    end_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(default=True)
    auto_renewal: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="subscriptions")
    tariff: Mapped["Tariff"] = relationship(back_populates="subscriptions")

    def __repr__(self):
        return f"<Subscription(id={self.id}, user_id={self.user_id}, tariff_id={self.tariff_id}, is_active={self.is_active})>"


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    currency: Mapped[str] = mapped_column(String(10), default="USD")
    payment_system: Mapped[str | None] = mapped_column(String(50))
    transaction_id: Mapped[str | None] = mapped_column(String, unique=True)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="payments")

    def __repr__(self):
        return f"<Payment(id={self.id}, user_id={self.user_id}, amount={self.amount}, status={self.status})>"


class Channel(Base):
    __tablename__ = "channels"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_chat_id: Mapped[str] = mapped_column(String(255), unique=True)
    title: Mapped[str] = mapped_column(String(255))
    type: Mapped[str] = mapped_column(String(20))  # 'channel' | 'group'
    link: Mapped[str | None] = mapped_column(String(500))
    icon: Mapped[str | None] = mapped_column(String(20))
    thread_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    paid_mode_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<Channel(id={self.id}, telegram_chat_id={self.telegram_chat_id}, title={self.title}, type={self.type})>"


class Advertisement(Base):
    __tablename__ = "advertisements"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    payment_id: Mapped[int | None] = mapped_column(ForeignKey("payments.id"))
    title: Mapped[str] = mapped_column(String)
    content: Mapped[str] = mapped_column(Text)
    media_url: Mapped[str | None] = mapped_column(String)
    channel_id: Mapped[str | None] = mapped_column(String)
    message_id: Mapped[int | None] = mapped_column(BigInteger)
    publish_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    delete_after_hours: Mapped[int] = mapped_column(default=24)
    scheduled_delete_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_published: Mapped[bool] = mapped_column(default=False)
    is_deleted: Mapped[bool] = mapped_column(default=False)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    tariff_type: Mapped[str | None] = mapped_column(String(50), default="basic")
    price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<Advertisement(id={self.id}, title={self.title}, is_published={self.is_published})>"


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String)
    category: Mapped[str | None] = mapped_column(String)
    phone: Mapped[str | None] = mapped_column(String)
    address: Mapped[str | None] = mapped_column(String)
    description: Mapped[str | None] = mapped_column(Text)
    icon_emoji: Mapped[str] = mapped_column(String(10), default="🏢")
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<Company(id={self.id}, name={self.name}, category={self.category})>"

class Rank(Base):
    __tablename__ = "ranks"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    icon_emoji: Mapped[str] = mapped_column(String(10), default="🏆")
    required_days: Mapped[int] = mapped_column(Integer)
    color: Mapped[str | None] = mapped_column(String(7), default="#007BFF")
    is_active: Mapped[bool] = mapped_column(default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user_ranks: Mapped[list["UserRank"]] = relationship(back_populates="rank")

    def __repr__(self):
        return f"<Rank(id={self.id}, name={self.name}, required_days={self.required_days})>"


class UserRank(Base):
    __tablename__ = "user_ranks"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    rank_id: Mapped[int] = mapped_column(ForeignKey("ranks.id"))
    awarded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_current: Mapped[bool] = mapped_column(default=True)

    user: Mapped["User"] = relationship(back_populates="user_ranks")
    rank: Mapped["Rank"] = relationship(back_populates="user_ranks")

    def __repr__(self):
        return f"<UserRank(id={self.id}, user_id={self.user_id}, rank_id={self.rank_id}, is_current={self.is_current})>"


class AdvertisementTariff(Base):
    """Модель для тарифов размещения рекламы"""
    __tablename__ = "advertisement_tariffs"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String)
    description: Mapped[str | None] = mapped_column(Text)
    channel_type: Mapped[str] = mapped_column(String(50))  # stores Channel.id as string
    thread_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    duration_hours: Mapped[int] = mapped_column(Integer, default=24)
    price_usd: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    price_stars: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<AdvertisementTariff(id={self.id}, name={self.name}, channel_type={self.channel_type}, price_usd={self.price_usd})>"
