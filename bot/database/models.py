from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Rarity(str, enum.Enum):
    """Редкость карты, от самой низкой (H) до самой высокой (SS)."""

    H = "H"
    G = "G"
    F = "F"
    E = "E"
    D = "D"
    C = "C"
    B = "B"
    A = "A"
    S = "S"
    SS = "SS"


#: Порядок редкостей от низшей к высшей - для сортировки и валидации ввода.
RARITY_ORDER: tuple[Rarity, ...] = tuple(Rarity)


class CardType(str, enum.Enum):
    SPECIAL = "Особая"
    SPELL = "Заклинание"
    ORDINARY = "Обычная"
    CONTOUR = "Контурная"
    GM = "ГеймМастерская"


class Card(Base):
    __tablename__ = "cards"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Номер Особого слота. У обычных карт номера нет.
    number: Mapped[int | None] = mapped_column(Integer, unique=True, default=None)
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    card_type: Mapped[CardType] = mapped_column(
        Enum(CardType, native_enum=False), default=CardType.ORDINARY,
        server_default=CardType.ORDINARY.name,
    )
    kind: Mapped[str] = mapped_column(String(64))
    description: Mapped[str] = mapped_column(Text, default="")
    usage: Mapped[str] = mapped_column(Text, default="")
    rarity: Mapped[Rarity] = mapped_column(Enum(Rarity, native_enum=False))
    # None - преобразования не ограничены.
    transform_limit: Mapped[int | None] = mapped_column(Integer, default=None)
    # Денормализованный счётчик живых копий; источник истины - CardOwnership.
    copies_count: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    ownerships: Mapped[list[CardOwnership]] = relationship(
        back_populates="card", cascade="all, delete-orphan"
    )


class Character(Base):
    __tablename__ = "characters"

    id: Mapped[int] = mapped_column(primary_key=True)
    vk_id: Mapped[int] = mapped_column(BigInteger, index=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    age: Mapped[int | None] = mapped_column(Integer, default=None)
    gender: Mapped[str] = mapped_column(String(64), default="", server_default="")
    appearance: Mapped[str] = mapped_column(Text, default="", server_default="")
    personality: Mapped[str] = mapped_column(Text, default="")
    biography: Mapped[str] = mapped_column(Text, default="")
    skills: Mapped[str] = mapped_column(Text, default="", server_default="")
    additional: Mapped[str] = mapped_column(Text, default="", server_default="")

    stress_resistance: Mapped[int] = mapped_column(Integer, default=1)  # стрессоустойчивость
    speech: Mapped[int] = mapped_column(Integer, default=1)  # речевой аппарат
    intuition: Mapped[int] = mapped_column(Integer, default=1)  # чуйка
    spine: Mapped[int] = mapped_column(Integer, default=1)  # хребет
    will: Mapped[int] = mapped_column(Integer, default=1)  # воля
    scent: Mapped[int] = mapped_column(Integer, default=1)  # нюх

    overall_rating: Mapped[Rarity] = mapped_column(
        Enum(Rarity, native_enum=False), default=Rarity.H
    )
    shakei_balance: Mapped[int] = mapped_column(Integer, default=0)

    is_approved: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    ownerships: Mapped[list[CardOwnership]] = relationship(
        back_populates="character", cascade="all, delete-orphan"
    )
    contours: Mapped[list[Contour]] = relationship(
        back_populates="character", cascade="all, delete-orphan"
    )


class Contour(Base):
    __tablename__ = "contours"
    __table_args__ = (
        UniqueConstraint("character_id", "slot", name="uq_character_contour_slot"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    character_id: Mapped[int] = mapped_column(
        ForeignKey("characters.id", ondelete="CASCADE"), index=True
    )
    slot: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(128))
    composition: Mapped[str] = mapped_column(Text, default="")
    appearance: Mapped[str] = mapped_column(Text, default="")
    primary_effect: Mapped[str] = mapped_column(Text, default="")
    additional_capabilities: Mapped[str] = mapped_column(Text, default="")
    activation_conditions: Mapped[str] = mapped_column(Text, default="")
    duration: Mapped[str] = mapped_column(Text, default="")
    conductivity: Mapped[str] = mapped_column(Text, default="")
    overload_impact: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    character: Mapped[Character] = relationship(back_populates="contours")


class CardOwnership(Base):
    """Живая копия карты у персонажа.

    Отдельная таблица, а не поле в Card: у лимитированной карты одновременно
    может быть несколько копий у разных персонажей.
    """

    __tablename__ = "card_ownerships"
    __table_args__ = (UniqueConstraint("card_id", "character_id", name="uq_card_character"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    card_id: Mapped[int] = mapped_column(ForeignKey("cards.id", ondelete="CASCADE"), index=True)
    character_id: Mapped[int] = mapped_column(
        ForeignKey("characters.id", ondelete="CASCADE"), index=True
    )
    obtained_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    card: Mapped[Card] = relationship(back_populates="ownerships")
    character: Mapped[Character] = relationship(back_populates="ownerships")


class ShakeiTransaction(Base):
    """Лог операций с Шакеями. Баланс всегда можно пересчитать по этому логу."""

    __tablename__ = "shakei_transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    # None у отправителя - эмиссия админом; None у получателя - списание админом.
    from_character_id: Mapped[int | None] = mapped_column(
        ForeignKey("characters.id", ondelete="SET NULL"), default=None, index=True
    )
    to_character_id: Mapped[int | None] = mapped_column(
        ForeignKey("characters.id", ondelete="SET NULL"), default=None, index=True
    )
    amount: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(Text, default="")
    # Кто из админов провёл операцию; у перевода между игроками - None.
    admin_vk_id: Mapped[int | None] = mapped_column(BigInteger, default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
