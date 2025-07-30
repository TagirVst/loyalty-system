from sqlalchemy import (
    Column, Integer, String, Boolean, Date, DateTime, ForeignKey, Enum, Text, func
)
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.dialects.postgresql import ENUM
import enum

Base = declarative_base()

class RoleEnum(str, enum.Enum):
    client = "client"
    barista = "barista"
    admin = "admin"

class LoyaltyLevelEnum(str, enum.Enum):
    standard = "Стандарт"
    silver = "Серебро"
    gold = "Золото"
    platinum = "Платина"

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    telegram_id = Column(String, unique=True, nullable=False, index=True)
    phone = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    birth_date = Column(Date, nullable=True)
    loyalty_status = Column(
        ENUM(LoyaltyLevelEnum, name="loyaltylevelenum"),
        default=LoyaltyLevelEnum.standard,
        nullable=False,
    )
    points = Column(Integer, default=0, nullable=False)
    drinks_count = Column(Integer, default=0, nullable=False)
    sandwiches_count = Column(Integer, default=0, nullable=False)
    gift_drinks = Column(Integer, default=0, nullable=False)
    gift_sandwiches = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True)
    role = Column(ENUM(RoleEnum, name="roleenum"), default=RoleEnum.client, nullable=False)

    codes = relationship("Code", back_populates="user", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="user", cascade="all, delete-orphan")
    feedbacks = relationship("Feedback", back_populates="user", cascade="all, delete-orphan")
    ideas = relationship("Idea", back_populates="user", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")

class Barista(Base):
    __tablename__ = "baristas"
    id = Column(Integer, primary_key=True)
    telegram_id = Column(String, unique=True, nullable=False, index=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    is_admin = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True)
    actions = relationship("BaristaAction", back_populates="barista", cascade="all, delete-orphan")

class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    barista_id = Column(Integer, ForeignKey("baristas.id"))
    code_id = Column(Integer, ForeignKey("codes.id"))
    receipt_number = Column(String, nullable=False)
    total_sum = Column(Integer, nullable=False)
    drinks_count = Column(Integer, default=0, nullable=False)
    sandwiches_count = Column(Integer, default=0, nullable=False)
    use_points = Column(Boolean, default=False)
    used_points_amount = Column(Integer, default=0)
    date_created = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="orders")
    barista = relationship("Barista")
    code = relationship("Code")

class Code(Base):
    __tablename__ = "codes"
    id = Column(Integer, primary_key=True)
    code = Column(String, unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    is_used = Column(Boolean, default=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    user = relationship("User", back_populates="codes")

class Gift(Base):
    __tablename__ = "gifts"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    type = Column(String, nullable=False)  # drink/sandwich
    amount = Column(Integer, default=1)
    created_by = Column(Integer, ForeignKey("baristas.id"), nullable=True)
    date_created = Column(DateTime(timezone=True), server_default=func.now())
    is_written_off = Column(Boolean, default=False)
    user = relationship("User")
    barista = relationship("Barista")

class Feedback(Base):
    __tablename__ = "feedbacks"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    score = Column(Integer)
    text = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    user = relationship("User", back_populates="feedbacks")

class Idea(Base):
    __tablename__ = "ideas"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    text = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    user = relationship("User", back_populates="ideas")

class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # null = all
    text = Column(Text, nullable=False)
    sent_by = Column(Integer, ForeignKey("baristas.id"), nullable=True)
    date_sent = Column(DateTime(timezone=True), server_default=func.now())
    user = relationship("User", back_populates="notifications")
    barista = relationship("Barista")

class BaristaAction(Base):
    __tablename__ = "barista_actions"
    id = Column(Integer, primary_key=True)
    barista_id = Column(Integer, ForeignKey("baristas.id"))
    action_type = Column(String, nullable=False)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    barista = relationship("Barista", back_populates="actions")
