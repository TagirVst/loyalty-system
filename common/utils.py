from datetime import date, datetime, timedelta

LOYALTY_LEVELS = [
    ("Стандарт", 0),
    ("Серебро", 20),
    ("Золото", 50),
    ("Платина", 100),
]

def get_loyalty_level(drinks_count: int) -> str:
    """Определить уровень лояльности по количеству напитков."""
    level = "Стандарт"
    for lvl, drinks in LOYALTY_LEVELS:
        if drinks_count >= drinks:
            level = lvl
    return level

def is_birthday_today(birth_date: date) -> bool:
    if not birth_date:
        return False
    today = date.today()
    return birth_date.day == today.day and birth_date.month == today.month

def role_permissions(role: str) -> dict:
    base = {
        "client": [
            "view_profile", "generate_code", "send_feedback", "send_idea", "view_points", "get_gifts", "notifications"
        ],
        "barista": [
            "process_order", "make_refund", "give_gift", "writeoff_gift", "send_notification", "view_history"
        ],
        "admin": [
            "process_order", "make_refund", "give_gift", "writeoff_gift", "send_notification", "view_history",
            "view_any_history", "manual_balance", "analytics", "user_management", "view_feedback", "view_ideas", "global_notifications"
        ],
    }
    return base.get(role, [])

def can(role: str, action: str) -> bool:
    return action in role_permissions(role)
