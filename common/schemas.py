from pydantic import BaseModel, Field
from datetime import date, datetime
from typing import Optional, List
import enum

class RoleEnum(str, enum.Enum):
    client = "client"
    barista = "barista"
    admin = "admin"

class LoyaltyLevelEnum(str, enum.Enum):
    standard = "Стандарт"
    silver = "Серебро"
    gold = "Золото"
    platinum = "Платина"

# Users
class UserBase(BaseModel):
    telegram_id: str
    phone: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    birth_date: Optional[date] = None

class UserCreate(UserBase):
    pass

class UserOut(UserBase):
    id: int
    loyalty_status: LoyaltyLevelEnum
    points: int
    drinks_count: int
    sandwiches_count: int
    gift_drinks: int
    gift_sandwiches: int
    is_active: bool
    role: RoleEnum

    class Config:
        from_attributes = True

# Baristas
class BaristaOut(BaseModel):
    id: int
    telegram_id: str
    first_name: Optional[str]
    last_name: Optional[str]
    is_admin: bool
    is_active: bool

    class Config:
        from_attributes = True

# Codes
class CodeOut(BaseModel):
    id: int
    code: str
    is_used: bool
    expires_at: datetime
    created_at: datetime

    class Config:
        from_attributes = True

# Orders
class OrderCreate(BaseModel):
    user_id: int
    barista_id: int
    code_id: int
    receipt_number: str
    total_sum: int
    drinks_count: int
    sandwiches_count: int
    use_points: bool = False
    used_points_amount: int = 0

class OrderOut(BaseModel):
    id: int
    user_id: int
    barista_id: int
    code_id: int
    receipt_number: str
    total_sum: int
    drinks_count: int
    sandwiches_count: int
    use_points: bool
    used_points_amount: int
    date_created: datetime

    class Config:
        from_attributes = True

# Gifts
class GiftCreate(BaseModel):
    user_id: int
    type: str  # "drink" or "sandwich"
    amount: int = 1
    created_by: Optional[int] = None

class GiftOut(BaseModel):
    id: int
    user_id: int
    type: str
    amount: int
    created_by: Optional[int]
    date_created: datetime
    is_written_off: bool

    class Config:
        from_attributes = True

# Feedback
class FeedbackCreate(BaseModel):
    user_id: int
    score: int
    text: Optional[str] = None

class FeedbackOut(BaseModel):
    id: int
    user_id: int
    score: int
    text: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True

# Idea
class IdeaCreate(BaseModel):
    user_id: int
    text: str

class IdeaOut(BaseModel):
    id: int
    user_id: int
    text: str
    created_at: datetime

    class Config:
        from_attributes = True

# Notification
class NotificationCreate(BaseModel):
    user_id: Optional[int]
    text: str
    sent_by: Optional[int]

class NotificationOut(BaseModel):
    id: int
    user_id: Optional[int]
    text: str
    sent_by: Optional[int]
    date_sent: datetime

    class Config:
        from_attributes = True

# Barista Actions
class BaristaActionOut(BaseModel):
    id: int
    barista_id: int
    action_type: str
    details: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True
