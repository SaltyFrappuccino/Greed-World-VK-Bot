from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
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
    __table_args__ = (
        CheckConstraint(
            "(card_type = 'SPECIAL' AND number IS NOT NULL AND number >= 0 AND number <= 99 AND registry_number IS NULL) "
            "OR (card_type IN ('SPELL', 'CONTOUR') AND number IS NULL AND registry_number IS NOT NULL AND registry_number >= 0) "
            "OR (card_type = 'GM' AND number IS NULL AND registry_number IS NULL)",
            name="ck_card_number_pool",
        ),
        UniqueConstraint("registry_number", name="uq_cards_registry_number"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # Номер Особого слота в отдельном пуле 0–99.
    number: Mapped[int | None] = mapped_column(Integer, unique=True, default=None)
    # Общий игровой номер Заклинаний и Контурных карт, начиная с 0.
    registry_number: Mapped[int | None] = mapped_column(Integer, default=None)
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
    __table_args__ = (
        CheckConstraint("contour_limit >= 2", name="ck_character_contour_limit"),
    )

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
    contour_limit: Mapped[int] = mapped_column(
        Integer, default=2, server_default="2"
    )

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
        CheckConstraint(
            "card_capacity >= 2 AND card_capacity <= 5",
            name="ck_contour_card_capacity",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    character_id: Mapped[int] = mapped_column(
        ForeignKey("characters.id", ondelete="CASCADE"), index=True
    )
    slot: Mapped[int] = mapped_column(Integer)
    card_capacity: Mapped[int] = mapped_column(
        Integer, default=2, server_default="2"
    )
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
    components: Mapped[list[ContourComponent]] = relationship(
        back_populates="contour",
        cascade="all, delete-orphan",
        order_by="ContourComponent.position",
    )


class CardOwnership(Base):
    """Живая копия карты у персонажа.

    Отдельная таблица, а не поле в Card: у лимитированной карты одновременно
    может быть несколько копий у разных персонажей.
    """

    __tablename__ = "card_ownerships"
    id: Mapped[int] = mapped_column(primary_key=True)
    __table_args__ = (
        CheckConstraint(
            "(card_id IS NOT NULL AND ordinary_name IS NULL) OR "
            "(card_id IS NULL AND ordinary_name IS NOT NULL)",
            name="ck_ownership_registered_or_ordinary",
        ),
    )

    card_id: Mapped[int | None] = mapped_column(
        ForeignKey("cards.id", ondelete="CASCADE"), index=True, nullable=True
    )
    character_id: Mapped[int] = mapped_column(
        ForeignKey("characters.id", ondelete="CASCADE"), index=True
    )
    ordinary_name: Mapped[str | None] = mapped_column(String(128), default=None)
    ordinary_kind: Mapped[str | None] = mapped_column(String(64), default=None)
    ordinary_description: Mapped[str | None] = mapped_column(Text, default=None)
    ordinary_usage: Mapped[str | None] = mapped_column(Text, default=None)
    ordinary_rarity: Mapped[Rarity | None] = mapped_column(
        Enum(Rarity, native_enum=False), default=None
    )
    obtained_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    card: Mapped[Card | None] = relationship(back_populates="ownerships")
    character: Mapped[Character] = relationship(back_populates="ownerships")
    contour_component: Mapped[ContourComponent | None] = relationship(
        back_populates="ownership", uselist=False
    )

    @property
    def is_ordinary(self) -> bool:
        return self.card_id is None

    @property
    def display_name(self) -> str:
        return self.card.name if self.card is not None else (self.ordinary_name or "")

    @property
    def display_type(self) -> CardType:
        return self.card.card_type if self.card is not None else CardType.ORDINARY

    @property
    def display_kind(self) -> str:
        return self.card.kind if self.card is not None else (self.ordinary_kind or "Обычная")

    @property
    def display_description(self) -> str:
        return self.card.description if self.card is not None else (self.ordinary_description or "")

    @property
    def display_usage(self) -> str:
        return self.card.usage if self.card is not None else (self.ordinary_usage or "")

    @property
    def display_rarity(self) -> Rarity:
        if self.card is not None:
            return self.card.rarity
        return self.ordinary_rarity or Rarity.H


class ContourComponent(Base):
    """Одна конкретная копия карты, связанная с Контуром."""

    __tablename__ = "contour_components"
    __table_args__ = (
        UniqueConstraint("contour_id", "position", name="uq_contour_component_position"),
        UniqueConstraint("card_ownership_id", name="uq_contour_component_ownership"),
        CheckConstraint(
            "position >= 1 AND position <= 5",
            name="ck_contour_component_position",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    contour_id: Mapped[int] = mapped_column(
        ForeignKey("contours.id", ondelete="CASCADE"), index=True
    )
    card_ownership_id: Mapped[int] = mapped_column(
        ForeignKey("card_ownerships.id", ondelete="RESTRICT"), index=True
    )
    position: Mapped[int] = mapped_column(Integer)

    contour: Mapped[Contour] = relationship(back_populates="components")
    ownership: Mapped[CardOwnership] = relationship(
        back_populates="contour_component"
    )


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
